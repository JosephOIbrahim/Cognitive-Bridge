# Plan: Top 3 Audit Fixes

## Context

Deep codebase audit identified 12 improvement areas. This plan addresses the top 3:

1. **Dual tool registry consolidation** — payload builders duplicated between `mcp_server.py` (stdio bridge) and `python/synapse/mcp/tools.py` (Streamable HTTP)
2. **Tier-pin key normalization** — pin keys use raw `input_text` without normalization, causing cache misses on whitespace/case differences (tier-pin limit IS already enforced via FIFO eviction at line 474)
3. **WebSocket origin validation** — no origin header checking on either transport, vulnerable to DNS rebinding on non-localhost deployments

---

## 1. Consolidate Payload Builders

**Problem:** 6 named payload builders + 14 inline lambdas in `mcp_server.py` duplicate logic from `mcp/tools.py`. Behavioral differences exist (`_identity` returns reference vs copy, `_decide_payload` has subtle string-splitting differences).

**Approach:** Extract shared payload builders into `mcp/tools.py` (which already has the cleaner implementations) and import them in `mcp_server.py`.

### Files to modify

- **`python/synapse/mcp/tools.py`** — Make payload builders public (remove `_` prefix on the 6 named builders, keep `_filter_keys` as factory)
- **`mcp_server.py`** — Replace local payload builder definitions (lines 2307-2348) with imports from `synapse.mcp.tools`. Replace inline lambdas with `_filter_keys()` factory calls imported from same module.

### Changes

**`mcp/tools.py`** — Add public exports at bottom:
```python
# Public API for payload builders (used by both stdio and HTTP bridges)
passthrough = _passthrough
identity = _identity  # Note: returns dict copy, not reference
execute_python_payload = _execute_python_payload
stage_info_payload = _stage_info_payload
decide_payload = _decide_payload
add_memory_payload = _add_memory_payload
filter_keys = _filter_keys
```

**`mcp_server.py`** — Replace lines 2307-2348 with:
```python
from synapse.mcp.tools import (
    passthrough as _passthrough,
    identity as _identity,
    execute_python_payload as _execute_python_payload,
    stage_info_payload as _stage_info_payload,
    decide_payload as _decide_payload,
    add_memory_payload as _add_memory_payload,
    filter_keys as _filter_keys,
)
```

Replace inline lambdas in TOOL_DISPATCH with `_filter_keys()`:
```python
"houdini_delete_node":       ("delete_node",     _filter_keys(["node"])),
"houdini_get_parm":          ("get_parm",        _filter_keys(["node", "parm"])),
"houdini_set_parm":          ("set_parm",        _filter_keys(["node", "parm", "value"])),
"houdini_get_usd_attribute": ("get_usd_attribute", _filter_keys(["node", "prim_path", "attribute_name"])),
# ... etc for all inline lambdas
```

Special cases that can't use `_filter_keys`:
- `houdini_network_explain` — has key rename (`root_path` → `node`), keep as lambda
- `synapse_search` / `synapse_recall` / `synapse_knowledge_lookup` — extract single key `query`, use `_filter_keys(["query"])`

### Import concern

`mcp_server.py` runs outside Houdini (as a standalone stdio process). It already does `sys.path.insert(0, ...)` to find the `synapse` package (line ~50). The import `from synapse.mcp.tools import ...` will work because `mcp/tools.py` only imports `json`, `time`, `orjson` (optional), and `..core.protocol.SynapseCommand`. None of these require `hou`.

---

## 2. Normalize Tier-Pin Keys

**Problem:** `pin_key = f"{input_text}|{context_hash}"` at `router.py:197,471` — identical queries with leading/trailing whitespace or different casing won't match.

### File to modify

- **`python/synapse/routing/router.py`** — Normalize `input_text` before building pin key

### Changes

At line 197 (route method) and line 471 (_pin_tier method), normalize input_text:
```python
pin_key = f"{input_text.strip().lower()}|{context_hash}"
```

Also update the same normalization in `_pin_tier()` (line 471) to ensure consistency:
```python
def _pin_tier(self, input_text: str, context_hash: str, tier_value: str,
              pin_key: Optional[str] = None):
    if pin_key is None:
        pin_key = f"{input_text.strip().lower()}|{context_hash}"
    ...
```

### Test update

Existing tests in `test_pipeline_efficiency.py` construct pin keys manually (e.g., `"create a sphere at /obj|"`). Update these to use lowered/stripped keys, or pass through the same normalization.

---

## 3. WebSocket Origin Validation

**Problem:** Neither the Python `websockets` server nor the `hwebserver` adapter validates the `Origin` header. Remote deployments (studio-lan, studio-vpn) are vulnerable to DNS rebinding.

**Approach:** Add a shared `validate_origin()` function in `auth.py` and call it from both transports.

### Files to modify

- **`python/synapse/server/auth.py`** — Add `validate_origin(origin, host, deploy_mode)` function
- **`python/synapse/server/websocket.py`** — Check origin in `_handle_client()` after connection, before auth
- **`python/synapse/server/hwebserver_adapter.py`** — Check origin in `SynapseWS.connect()` before `accept()`
- **`python/synapse/mcp/server.py`** — Check origin on HTTP POST `/mcp` requests

### Origin validation rules

```python
_LOCALHOST_ORIGINS = frozenset([
    "http://localhost", "https://localhost",
    "http://127.0.0.1", "https://127.0.0.1",
    "http://[::1]", "https://[::1]",
])

def validate_origin(origin: str, *, deploy_mode: str = "local",
                    allowed_origins: Optional[set] = None) -> bool:
    """Check if Origin header is acceptable.

    - No origin header (non-browser client like Claude Code): ALLOW
    - Localhost origins: always ALLOW
    - Studio mode + allowed_origins configured: check allowlist
    - Studio mode + no allowlist: REJECT (fail-safe)
    """
    if not origin:
        return True  # Non-browser clients (curl, Claude Code) don't send Origin

    # Strip port for comparison
    origin_no_port = re.sub(r':\d+$', '', origin.lower().rstrip('/'))

    if origin_no_port in _LOCALHOST_ORIGINS:
        return True

    if deploy_mode == "local":
        return False  # Non-localhost origin on local deployment = reject

    # Studio mode: check allowlist
    if allowed_origins:
        return origin_no_port in allowed_origins

    return False  # No allowlist configured = fail-safe reject
```

### Integration points

**websocket.py `_handle_client()`** — After line 317 (client added to set), before line 322 (auth check):
```python
# Origin validation (DNS rebinding protection)
origin = ""
try:
    origin = websocket.request.headers.get("Origin", "")
except AttributeError:
    pass  # Older websockets versions may not expose request
if not validate_origin(origin, deploy_mode=self._deploy_config.mode):
    logger.warning("Rejected connection from origin: %s", origin)
    websocket.close(4003, "Origin not allowed")
    return
```

**hwebserver_adapter.py `SynapseWS.connect()`** — Before `await self.accept()` (line 106):
```python
origin = ""
try:
    origin = req.headers().get("Origin", "")
except (AttributeError, TypeError):
    pass
if not validate_origin(origin, deploy_mode=_deploy_mode()):
    await self.close(4003, "Origin not allowed")
    return
```

**mcp/server.py `_mcp_url_handler()`** — After auth check, before processing body:
```python
origin = request.headers().get("Origin", "")
if not validate_origin(origin, deploy_mode=_deploy_mode()):
    return hwebserver.Response('{"error":"Origin not allowed"}', status=403)
```

---

## Tests

### New tests to add

**`tests/test_auth.py`** — Add origin validation tests:
- `test_validate_origin_empty_allowed` — No origin header passes
- `test_validate_origin_localhost_allowed` — All localhost variants pass
- `test_validate_origin_remote_rejected_local_mode` — Non-localhost rejected in local mode
- `test_validate_origin_allowlist_studio_mode` — Configured origins pass in studio mode
- `test_validate_origin_no_allowlist_studio_rejected` — Fail-safe reject with no allowlist
- `test_validate_origin_with_port` — Origin with port stripped correctly

**`tests/test_pipeline_efficiency.py`** — Update tier-pin key tests to use normalized keys

**`tests/test_pipeline_efficiency.py`** — Add test for payload builder import from mcp/tools.py (verify no `hou` dependency)

---

## Verification

```bash
# Run full test suite
python -m pytest tests/ -v

# Specifically test affected areas
python -m pytest tests/test_auth.py -v -k "origin"
python -m pytest tests/test_pipeline_efficiency.py -v -k "pin"
python -m pytest tests/test_mcp_protocol.py -v

# Verify mcp_server.py can import payload builders without hou
python -c "from synapse.mcp.tools import passthrough, identity, filter_keys; print('OK')"

# Type check
python -m mypy python/synapse/server/auth.py python/synapse/routing/router.py python/synapse/mcp/tools.py --config-file pyproject.toml
```
