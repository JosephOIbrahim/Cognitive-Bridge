# mcp_server.py v2.0 — Latency Overhaul

## Context

The MCP bridge (`mcp_server.py`) is the stdio process Claude Code spawns to relay tool calls to Houdini via WebSocket. Every ms of bridge overhead is felt on every tool call. v1 has several latency bottlenecks, the worst being a **2-second dead wait** on every new connection when no auth is configured.

This overhaul also incorporates the recv-task race condition fix from the previous session and bumps the protocol to v2.

## Latency Bottlenecks

| Issue | Impact | Fix |
|-------|--------|-----|
| Auth handshake 2s timeout (no auth configured) | **+2000ms per reconnect** | Skip recv wait when no local key exists |
| `orjson.dumps().decode()` str roundtrip | ~0.1ms/cmd | Send bytes directly (websockets accepts bytes) |
| `asyncio.Lock` on every command (hot path) | ~0.05ms/cmd | Lock-free fast path: check before lock |
| `asyncio.wait_for()` internal task per cmd | ~0.05ms/cmd | `asyncio.wait()` on future set directly |
| `asyncio.get_event_loop()` deprecated | micro | `get_running_loop()` everywhere |
| Recv task race (stale task blocks new loop) | **infinite hang** | Explicit cancel + cleanup |
| No `max_size` bypass for localhost | overhead | `max_size=None` |
| Warmup blocks startup | delays first tool | Fire-and-forget task |

## Changes to `mcp_server.py`

### 1. Auth handshake — skip when no key configured

Check for a local key first. If none exists, skip the 2s recv wait entirely. If the server requires auth, the first command will fail with a clear error (acceptable trade-off for 2s savings).

### 2. orjson bytes passthrough

`_dumps` returns `bytes` instead of `str`. websockets sends bytes directly — zero copy. Only `.decode()` at the final `TextContent` return.

Stdlib `json` fallback still returns `str`, websockets handles both transparently.

### 3. Lock-free fast path for `_get_connection`

Volatile check `_is_connected()` before acquiring `_ws_lock`. The common case (connection alive) skips the lock entirely. Double-check inside lock for safety.

### 4. Replace `asyncio.wait_for` with direct future wait

`asyncio.wait({future}, timeout=T)` avoids creating an internal wrapper task. Extract result from the done set.

### 5. Recv task lifecycle — race condition fix

Already implemented in v1 patch. Consolidate into v2: `_get_connection` explicitly cancels stale `_recv_task` before creating a new one.

### 6. Warmup — fire-and-forget

`asyncio.create_task(_warmup())` instead of `await _warmup()`. The stdio server starts accepting immediately.

### 7. `max_size=None` for localhost

Skip WebSocket frame size validation on localhost. Removes overhead for large payloads (introspection, stage dumps).

## Files Modified

| File | Change |
|------|--------|
| `mcp_server.py` | Rewrite WebSocket client section (~lines 60-360). Tool defs and dispatch unchanged. |

## NOT Changed

- Tool definitions (`list_tools`) — identical
- Dispatch table (`TOOL_DISPATCH`) — identical
- `call_tool` handler — only `.decode()` added for TextContent where `_dumps` returns bytes
- Server-side code — no changes
- Tests — existing suite covers handler behavior, not bridge transport

## Verification

1. `python -m pytest tests/ -v` — full suite passes (1427+ tests)
2. Kill MCP server processes, let Claude Code respawn with v2
3. `synapse_ping` — verify instant response
4. `houdini_scene_info` — verify scene data returns
5. Rapid-fire 5 commands — verify no lockups
6. After: commit all changes (v1 deadlock fix + v2 latency) and push to GitHub
