# Phase 4 — Rich CLI + GitHub Releases + Proactive Surfacing + Housekeeping

## Context

comfyui-agent is at 63 tools, 554 tests. The stretch goal (live iterative_refine) just passed. Three Phase 4 roadmap items remain, plus tool count housekeeping across docs.

Verified tool split: **42 intelligence + 21 brain = 63 total**.

---

## Task 4: Rich CLI Formatting

`rich>=13.0.0` is already a dependency. `Console` and `Panel` are already imported in `cli.py`. The CLI currently uses inline `[bold]`/`[dim]` markup but no Tables, Trees, or structured output.

### Changes to `agent/cli.py`

**Add imports:**
```python
from rich.table import Table
```

**`inspect()` (lines 160-190):** Replace plain `console.print` loops with:
- Models summary → `Table` with columns: Type, Count
- Custom nodes → `Table` with columns: Pack Name, Nodes, Readme

**`sessions()` (lines 279-294):** Replace loop with:
- `Table` with columns: Name, Saved At, Workflow, Notes

**`search()` (lines 334-357):** Replace loop with:
- `Table` with columns: Name, Type, Source, Status (installed/not)
- Description as a second line under each entry is harder in a table — keep inline print for descriptions, OR use a wider table with truncated desc column

**`parse()` (lines 192-276):** Replace node type list with:
- `Table` with columns: Node Type, Count
- Editable fields → `Table` with columns: Node [ID], Field, Value

**`on_text_delta` streaming (line 120):** Leave as-is. Rich `Live` + `Markdown` rendering would buffer output and break the streaming experience. Raw `print()` is correct for streaming.

**`on_tool_call` (lines 122-130):** Subtle styling improvement only — keep it light.

### Tests
No new tests needed — CLI output formatting is visual. Run `ruff check` only.

---

## Task 5: GitHub API Release Tracking

### New file: `agent/tools/github_releases.py`

Follow the `civitai_api.py` pattern:
- Module docstring, imports (logging, os, httpx), constants
- `GITHUB_TOKEN = os.getenv("GITHUB_API_TOKEN")`
- `TOOLS` list with 2 tools
- `handle(name, tool_input) -> str` dispatch

**Tool 1: `check_node_updates`**
```
Input:  {} (no params — checks all installed custom node packs)
Output: {updates: [{name, installed_version, latest_version, tag, published, url, behind_by}], checked, up_to_date, needs_update}
```
- Scans installed custom node packs (via `comfy_inspect.list_custom_nodes`)
- For each pack, checks if it has a `.git` directory → extract remote URL → query GitHub releases API
- Compares local git HEAD with latest release tag
- Rate limit: `GITHUB_LIMITER` in `rate_limiter.py` (1 req/s, burst 5)

**Tool 2: `get_repo_releases`**
```
Input:  {repo: "owner/name", limit: 5}
Output: {repo, releases: [{tag, name, published, body_preview, url}]}
```
- Direct GitHub API query for a specific repo
- Useful when the agent knows a repo name from discovery results

**Headers:**
```python
def _build_headers():
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h
```

### New in `agent/rate_limiter.py`

Add after existing limiter functions:
```python
def GITHUB_LIMITER() -> RateLimiter:
    return GlobalRateLimiter.get("github", rate=1.0, capacity=5)
```

### Register in `agent/tools/__init__.py`

Add `github_releases` to imports and `_MODULES` tuple. Tool count: 63 → 65.

### New file: `tests/test_github_releases.py`

~10 tests: basic release fetch, no token, rate limit header, installed packs scan, no git dir skipped, HTTP error handling, empty releases, repo not found, tool registration.

### Update `tests/test_tools_registry.py` and `tests/test_mcp_server.py`

Count 63 → 65. Add `"check_node_updates"` and `"get_repo_releases"` to expected set.

---

## Task 6: Proactive Surfacing

Inject top memory recommendations into the system prompt at session start.

### Changes to `agent/system_prompt.py`

In `build_system_prompt()`, after the session notes block (line 150), add:

```python
# Proactive recommendations from memory (if outcomes exist)
if session_context and session_context.get("name"):
    try:
        from .brain.memory import handle as memory_handle
        import json as _json
        recs_raw = memory_handle("get_recommendations", {
            "session": session_context["name"],
        })
        recs = _json.loads(recs_raw)
        top_recs = [r for r in recs.get("recommendations", [])
                    if r.get("confidence", 0) >= 0.7][:3]
        if top_recs:
            parts.append("\n--- Recommendations from Past Sessions ---")
            for rec in top_recs:
                parts.append(f"  - [{rec.get('category', '?')}] "
                             f"{rec.get('recommendation', '')}")
            parts.append("")
    except Exception:
        pass  # Memory unavailable — skip silently
```

### Add rule to `_RULES`

After rule 15, add:
```
16. When past outcomes exist, proactively mention relevant patterns without overwhelming.
```

### Tests

Add 2 tests to `tests/test_new_features.py` (TestSessionAwarePrompt class):
- `test_with_recommendations`: mock memory_handle → verify recommendations appear in prompt
- `test_without_recommendations`: no session → no recommendations injected

---

## Task 7: Housekeeping — Tool Count Updates

After Task 5 completes (65 tools: 44 intel + 21 brain), update ALL stale references:

| File | What to fix |
|------|------------|
| `agent/tools/__init__.py` line 7 | docstring: update to actual split |
| `agent/cli.py` line 362 | "60 tools" → correct count |
| `CLAUDE.md` lines 30, 202, 211, 248, 254, 503 | Various stale counts |
| `README.md` lines 105, 107, 116, 166 | Various stale counts |
| `.claude/commands/COMFY_LEAD.md` line 31 | "60 tools" → correct count |

Historical counts in CLAUDE.md Phase sections are left as-is — they describe the state at that time.

---

## Implementation Order

1. **Task 4**: Rich CLI formatting (`cli.py` only)
2. **Task 5**: GitHub releases (new module + tests + registration)
3. **Task 6**: Proactive surfacing (`system_prompt.py` + 2 tests)
4. **Task 7**: Housekeeping counts (all docs, done last since Task 5 changes the count)
5. Run full suite + lint
6. Commit + push

---

## Verification

```bash
python -m pytest tests/ -v                         # full suite (~566+ tests)
python -m pytest tests/test_github_releases.py -v  # new module
python -m pytest tests/test_new_features.py -v     # proactive surfacing tests
python -m pytest tests/test_tools_registry.py -v   # counts
ruff check agent/ tests/                           # lint clean
agent inspect                                      # verify rich tables render
agent sessions                                     # verify rich table
agent search "sdxl"                                # verify rich table
```
