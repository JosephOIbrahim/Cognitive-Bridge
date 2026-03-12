# Plan: Sidebar Workflow Context Injection

## Context

The SUPER DUPER sidebar agent doesn't know what workflow is currently open in ComfyUI. When the user asks "describe this workflow," the agent asks for a file path instead of just knowing. The sidebar JS runs *inside* ComfyUI's frontend and has access to `app.graphToPrompt()` which returns the current graph in API format — we just need to pipe it through.

Two problems to solve:
1. **Workflow awareness** — agent needs the current graph automatically
2. **Node inventory** — agent should know all installed nodes and detect missing ones

## Approach: Extend `load_workflow` to accept raw JSON + context injection

No temp files. No filesystem I/O. Extend the internal loader to accept a dict, then pipe the frontend graph through the WebSocket to populate agent state.

## Changes

### 1. `agent/tools/workflow_patch.py` — Add `load_workflow_from_data()`

New public function (not a tool — called by the backend directly):

```python
def load_workflow_from_data(data: dict, source: str = "<sidebar>") -> str | None:
```

- Calls existing `_extract_api_format(data)` from `workflow_parse.py`
- Populates `_state` (base_workflow, current_workflow, format, loaded_path=source, history=[])
- Returns None on success, error string on failure
- Reuse: `_extract_api_format` from `workflow_parse.py`, `_state_lock` and `_state` from this module

### 2. `agent/tools/workflow_parse.py` — Add `summarize_workflow_data()`

New public function that takes a raw dict and returns a structured summary:

```python
def summarize_workflow_data(data: dict) -> dict:
```

- Reuses existing internal functions: `_extract_api_format`, `_trace_connections`, `_find_editable_fields`, `_build_summary`
- Returns: `{format, node_count, connection_count, summary, nodes, editable_fields}`
- This summary goes into the system prompt so the agent can reason without tool calls on the first message

### 3. `ui/web/js/sidebar.js` — Capture workflow on send

Make `sendMessage()` async. Before sending, call:

```javascript
const { output } = await app.graphToPrompt();
```

Attach `output` (API-format dict) to the WebSocket payload:

```javascript
conn.send("chat", { content: text, workflow: output });
```

Called on every message so the agent always has the latest graph state.

### 4. `ui/server/routes.py` — Receive workflow + inject context

**Extend `ConversationState`** with `workflow_summary` and `missing_nodes` fields.

**New `_inject_workflow(conv, workflow_data)` function:**
1. Compare against current state — skip reload if unchanged (preserves undo history)
2. Call `load_workflow_from_data(workflow_data)` to populate agent's `_state`
3. Call `summarize_workflow_data(workflow_data)` for context
4. On first message only: run `find_missing_nodes` (best-effort, ~100-500ms)
5. Force system prompt rebuild

**Modify `_build_system()`:** Append workflow summary + missing nodes warning to system prompt. Include explicit instruction: "The workflow is already loaded. Use PILOT tools directly without asking for a file path."

**Modify WebSocket `chat` handler:** Extract `workflow` from message, call `_inject_workflow` before running agent.

### 5. Tests — `tests/test_sidebar_workflow.py`

~8 tests:
- `load_workflow_from_data` with API format, UI+API format, empty dict, UI-only (error)
- State populated correctly after data load
- PILOT tools (add_node, set_input) work after data load
- `summarize_workflow_data` returns correct structure
- Unchanged workflow skips reload

## Files Modified

| File | Change |
|------|--------|
| `agent/tools/workflow_patch.py` | Add `load_workflow_from_data()` (~20 lines) |
| `agent/tools/workflow_parse.py` | Add `summarize_workflow_data()` (~25 lines) |
| `ui/web/js/sidebar.js` | Make `sendMessage` async, add `graphToPrompt()` call |
| `ui/server/routes.py` | Add `_inject_workflow()`, extend `ConversationState`, modify WS handler |
| `tests/test_sidebar_workflow.py` | New test file (~8 tests) |

## Verification

1. Run `python -m pytest tests/ -v` — all existing 658 tests pass + new tests
2. Restart ComfyUI, open sidebar
3. Load any workflow in ComfyUI canvas
4. Type "describe this workflow" — agent should respond with details, no file path asked
5. Type "what nodes are missing?" — agent should check and report
6. Type "make it dreamier" — agent should propose patches directly (PILOT tools work)
