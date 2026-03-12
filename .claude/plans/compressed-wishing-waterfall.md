# Plan: Add Async Tool Tests with mock_ue

## Context

The UnrealEngine_Bridge has 39 MCP tools across 11 modules with 146 passing tests, but all tests are synchronous — they only cover validation logic and `ast.parse()` code generation. The `mock_ue` fixture in `conftest.py` is defined but unused. This adds async tests that exercise the full tool registration → call → mock response path.

## Approach

Use `@pytest.mark.asyncio` (strict mode — pytest-asyncio 0.26 default, no config change) with `FastMCP("test")` server instances. Call inner tool functions via `server._tool_manager._tools["tool_name"].fn`. This tests actual async closures including validation, code generation, and `ue.execute_python()` / `ue.*` dispatch.

## Files

| File | Action |
|------|--------|
| `tests/test_scene.py` | Modify — add async test classes |
| `tests/test_materials.py` | Modify — add async test classes |
| `tests/test_editor.py` | Modify — add async test classes |
| `tests/test_actors_async.py` | **Create** — actors module async tests |
| `tests/test_assets_async.py` | **Create** — assets module async tests |
| `tests/test_level_async.py` | **Create** — level module async tests |

## Test Pattern

Each file gets a fixture creating `FastMCP("test")` + `register(server, mock_ue)`. A helper `_call(server, name)` returns the inner async function. Each tool gets:

1. **Happy path** — valid inputs → mock called → JSON result without `"error"`
2. **Validation gate** — bad inputs → `"error"` in result, mock NOT called
3. **Code inspection** (for `execute_python` tools) — verify generated code contains expected strings

### Key details:
- `server._tool_manager._tools["name"].fn` gives the raw async function
- Default `mock_ue.execute_python` returns `{"output": "", "success": True}`
- `mock_ue.execute_python.call_args[0][0]` inspects the generated Python code
- Tools NOT using `execute_python`: `ue_spawn_actor`, `ue_delete_actor`, `ue_list_actors`, `ue_set_transform`, `ue_save_level`, `ue_get_level_info`, `ue_find_assets` — they call named `ue.*` methods

## Estimated ~60 new async tests

- `test_scene.py`: +12 (4 tools × 3)
- `test_materials.py`: +12 (4 tools × 3)
- `test_editor.py`: +12 (5 tools × ~2.5)
- `test_actors_async.py`: +10 (6 tools)
- `test_assets_async.py`: +6 (3 tools)
- `test_level_async.py`: +8 (4 tools)

## Verification

```bash
python -m pytest tests/ -v           # All 200+ tests pass
python -m pytest tests/ -v -k "Async"  # Only new async tests
```
