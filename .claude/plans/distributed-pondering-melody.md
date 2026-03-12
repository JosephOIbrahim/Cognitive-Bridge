# SYNAPSE Artist-Friendly Sprint — MOE Agent Dispatch

## Context

Session insights revealed 6 friction points where Synapse breaks artist flow:
rendering pain (materials, output paths, foreground locking), DOP wiring confusion,
source/deployed drift, thin error messages, no progressive workflow, and invisible
MCP tool results. Plus a 7th request: visually align the chat panel to the v5.7.0
pypanel design system.

This sprint implements all 7 suggestions via 5 MOE agents across 3 phases.

---

## PRE-FLIGHT

All agents must read before writing:
- `CLAUDE.md` (project conventions, lighting law, coaching tone, test patterns)
- Their owned files (understand before modifying)

---

## FILE OWNERSHIP

| Agent | MOE Role | Exclusive Write | Read Only |
|-------|----------|-----------------|-----------|
| **RENDER** | Render Safety Expert | `python/synapse/server/handlers_render.py` | handlers.py, autonomy/validator.py |
| **ERROR** | Error UX Expert | `python/synapse/server/handler_helpers.py`, `python/synapse/server/handlers_material.py` | handlers_render.py, handlers.py |
| **RECIPE** | Workflow & Sim Expert | `python/synapse/routing/recipes.py` | handlers_render.py, planner.py |
| **WIRE** | Integration Engineer | `python/synapse/core/protocol.py`, `python/synapse/server/handlers.py` (registration only), `mcp_server.py`, `python/synapse/mcp/tools.py`, `python/synapse/core/aliases.py` | all handler files |
| **DESIGN** | Chat UI/UX Expert | `python/synapse/panel/message_formatter.py`, `python/synapse/panel/chat_display.py`, `python/synapse/panel/styles.py`, `python/synapse/panel/chat_panel.py` | tokens.py, `~/.synapse/houdini/python_panels/synapse_panel.pypanel`, `~/.synapse/design/synapse_styles.py` |

---

## PHASE 1: BUILD (parallel — 3 agents)

### Agent RENDER — Render Safety Expert

**Goal:** Make rendering safe by default. Artists say "render" and get validated, progressive results.

**T1: Add `_handle_safe_render()` handler** (~line 412 in handlers_render.py)
- Pre-validates stage via existing `PreFlightValidator` checks (camera exists, materials bound, output path valid)
- If resolution > 512 on either axis AND `soho_foreground` not explicitly set, force `soho_foreground=0` (background)
- Returns rich diagnostic if pre-flight fails: `{"passed": false, "checks": [...], "suggestion": "..."}`
- If pre-flight passes, delegates to existing `_handle_render()` with the validated settings
- Returns render result enriched with validation summary

**T2: Add `_handle_render_progressively()` handler** (~line 830 in handlers_render.py)
- 3-pass pipeline: test (256x256, 4 samples) -> preview (720p, 16 samples) -> production (user resolution, user samples)
- After each pass, calls existing `_handle_validate_frame()` to check for black frames, NaN, clipping
- If validation fails at any pass, stops and returns diagnostic with the failed frame analysis
- Returns `{"passes": [{"resolution": ..., "quality": ..., "validation": {...}}], "final_image": "..."}`
- Uses `soho_foreground=1` only for test pass (fast), background for preview + production

### Agent ERROR — Error UX Expert

**Goal:** When things go wrong, tell the artist what to try next with specific suggestions.

**T1: Add `_suggest_prim_paths()` to handler_helpers.py**
- Takes a USD stage and an invalid prim path
- Walks the stage hierarchy, scores each prim path by:
  - Path segment overlap (e.g., `/rubbertoy` matches `/scene/rubbertoy/geo`)
  - Levenshtein-style prefix matching on the final segment
- Returns top 3 closest matches: `" Similar prims: /scene/rubbertoy/geo, /scene/rubbertoy/geo/shape"`
- Pattern matches existing `_suggest_parms()` (substring + prefix fallback)

**T2: Add `_render_diagnostic_checklist()` to handler_helpers.py**
- Takes a LOP/ROP node, returns a checklist dict:
  ```python
  {"camera_set": bool, "materials_bound": bool, "output_path_exists": bool,
   "output_dir_writable": bool, "resolution_set": bool, "renderer_valid": bool}
  ```
- Used by safe_render and error messages to give artists actionable next steps

**T3: Enrich material errors in handlers_material.py**
- In `_handle_assign_material()`: when `primpattern1` path doesn't match any prims, call `_suggest_prim_paths()` and append suggestions to error
- In `_handle_read_material()`: when prim path not found, suggest closest prim paths
- In `_handle_create_textured_material()`: when geo_pattern doesn't match, suggest alternatives
- Maintain coaching tone: "Couldn't find a prim at X -- did you mean one of these?"

### Agent RECIPE — Workflow & Sim Expert

**Goal:** Artist says natural phrases, gets safe multi-step workflows including proper DOP wiring.

**T1: Add `safe_render` recipe** (after existing render recipes ~line 2200)
- Triggers: `r"(?:safe|validated?)\s+render"`, `r"render\s+(?:safe|with\s+validation)"`
- Parameters: `rop_path` (optional, auto-discovered if omitted)
- Steps: 1 step calling `safe_render` command (delegates to the new handler)

**T2: Add `render_progressively` recipe** (after safe_render)
- Triggers: `r"(?:progressive|incremental)\s+render"`, `r"render\s+progressive(?:ly)?"`
- Parameters: `rop_path` (optional)
- Steps: 1 step calling `render_progressively` command

**T3: Add `dop_network_setup` recipe** (in sim/effects section ~line 1600)
- Triggers: `r"(?:set\s*up|create|build)\s+(?:a\s+)?dop\s+(?:network|sim)"`, `r"(?:simulation|dynamics)\s+setup"`
- Uses `execute_python` step with proper DOP wiring:
  - Creates DOP network with dopnet
  - Creates solver (configurable: bullet, vellum, pyro, flip)
  - Creates object nodes
  - Wires via merge nodes (DOP convention, NOT direct connections)
  - Sets SOP path references correctly
- Key insight from session friction: DOPs use merge-based connections, not SOP-style direct wiring

**T4: Add `verify_installation` recipe** (in utility section)
- Triggers: `r"verify\s+(?:install|deployment|sync)"`, `r"check\s+(?:install|drift|sync)"`
- Uses `execute_python` step that compares file checksums between source (`SYNAPSE/`) and deployed (`~/.synapse/houdini/`)
- Returns drift report: which files differ, which are missing

---

### PHASE 1 GATE

```bash
# Verify new handlers exist
python -c "
import sys, types, importlib
hou = types.ModuleType('hou'); sys.modules['hou'] = hou
hou.node = lambda *a: None; hou.frame = lambda: 1.0
spec = importlib.util.spec_from_file_location('hr', 'python/synapse/server/handlers_render.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert hasattr(mod, '_handle_safe_render'), 'safe_render handler missing'
assert hasattr(mod, '_handle_render_progressively'), 'render_progressively handler missing'
print('RENDER: OK')
"

# Verify error helpers exist
python -c "
import sys, types, importlib
hou = types.ModuleType('hou'); sys.modules['hou'] = hou
spec = importlib.util.spec_from_file_location('hh', 'python/synapse/server/handler_helpers.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert hasattr(mod, '_suggest_prim_paths'), '_suggest_prim_paths missing'
assert hasattr(mod, '_render_diagnostic_checklist'), '_render_diagnostic_checklist missing'
print('ERROR: OK')
"

# Verify new recipes
python -c "
import sys, types, importlib
hou = types.ModuleType('hou'); sys.modules['hou'] = hou
spec = importlib.util.spec_from_file_location('rr', 'python/synapse/routing/recipes.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
rb = mod.RecipeBook()
names = [r.name for r in rb._recipes]
for n in ['safe_render', 'render_progressively', 'dop_network_setup', 'verify_installation']:
    assert n in names, f'{n} recipe missing'
print('RECIPE: OK')
"
```

---

## PHASE 2: WIRE + DESIGN (parallel — 2 agents)

### Agent WIRE — Integration Engineer

**Goal:** Register all new handlers in the command system, MCP tools, and aliases.

**T1: Add CommandType entries in protocol.py**
- `SAFE_RENDER = "safe_render"`
- `RENDER_PROGRESSIVELY = "render_progressively"`

**T2: Register handlers in handlers.py `_register_handlers()`**
- `reg.register("safe_render", self._handle_safe_render)` (from RenderHandlerMixin)
- `reg.register("render_progressively", self._handle_render_progressively)` (from RenderHandlerMixin)
- Add both to `_READ_ONLY_COMMANDS` — wait, these are NOT read-only (they render). Don't add to read-only list.

**T3: Add MCP tool entries in mcp_server.py**
- Add `Tool(name="synapse_safe_render", ...)` to `list_tools()` with inputSchema
- Add `Tool(name="synapse_render_progressively", ...)` to `list_tools()`
- Add dispatch entries to `TOOL_DISPATCH` dict
- Add to `_SLOW_COMMANDS` with 120s timeout

**T4: Add tool definitions in mcp/tools.py**
- Add entries to `_TOOL_DEFS` for both tools
- Include proper annotations: `readOnlyHint=False`, `destructiveHint=True`

**T5: Add parameter aliases in aliases.py**
- `"rop_path"` alias for safe_render/render_progressively: `["rop_path", "rop", "render_node"]`
- `"max_resolution"` alias: `["max_resolution", "max_res", "target_res"]`

### Agent DESIGN — Chat UI/UX Alignment Expert

**Goal:** (a) Show human-readable tool summaries in chat, (b) align chat panel visuals to v5.7.0 pypanel.

**T1: Add `format_tool_summary()` in message_formatter.py**
- Maps tool names to human-readable summaries:
  ```python
  _TOOL_SUMMARIES = {
      "create_node": "Created {type} node at {path}",
      "set_parm": "Set {parm} = {value} on {node}",
      "render": "Rendered frame to {output_file}",
      "create_material": "Created {shader_type} material '{name}'",
      "assign_material": "Assigned material to {primpattern1}",
      "safe_render": "Safe render: {summary}",
      "execute_python": "Ran Python script",
      "execute_vex": "Ran VEX on {node_path}",
      ...
  }
  ```
- Returns formatted HTML: dimmed timestamp + SIGNAL-colored summary line
- Falls back to raw tool name if no template matches

**T2: Wire tool summaries into chat_display.py**
- Add `append_tool_summary(tool_name, result)` method to `ChatDisplay`
- Renders as a compact system-style message (not a full bubble) — subtle, doesn't clutter the chat
- Uses `format_tool_summary()` from message_formatter

**T3: Add tool summary display to chat_panel.py `_on_response()`**
- After showing `commands`, display a tool summary for each executed command
- Use the new `append_tool_summary()` method

**T4: Align chat panel styles to v5.7.0 pypanel aesthetic**
- The v5.7.0 pypanel uses `generate_stylesheet()` from `~/.synapse/design/synapse_styles.py` — a single unified stylesheet with `#title_bar`, `#status_bar`, `#tool_grid`, `#activity_frame`, `#connection_frame` object names
- The chat panel uses many small `get_*_stylesheet()` functions — functional but visually disconnected
- **Changes to styles.py:**
  - Update `get_root_widget_stylesheet()` to match pypanel's `#synapse_panel` bg/font
  - Update `get_connection_frame_stylesheet()` to use same margins as pypanel (SPACE_MD, SPACE_SM)
  - Update `get_mode_toolbar_stylesheet()` to match pypanel's `#title_bar` proportions
  - Add `get_activity_log_stylesheet()` matching pypanel's `#activity_log` for consistency
  - Ensure all stylesheets use `SPACE_*` tokens for margins/padding instead of hardcoded px values
- **Changes to chat_panel.py:**
  - Update connection bar height from `setFixedHeight(44)` to use token-derived value matching pypanel
  - Ensure mode toolbar height matches pypanel title bar proportions
  - Update status dot/label to use same font-size as pypanel (`SIZE_SMALL`)

---

### PHASE 2 GATE

```bash
# Verify MCP registration
python -c "
import sys, types
hou = types.ModuleType('hou'); sys.modules['hou'] = hou
hou.node = lambda *a: None; hou.frame = lambda: 1.0
# Check protocol
import importlib
spec = importlib.util.spec_from_file_location('p', 'python/synapse/core/protocol.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert hasattr(mod.CommandType, 'SAFE_RENDER')
assert hasattr(mod.CommandType, 'RENDER_PROGRESSIVELY')
print('WIRE protocol: OK')
"

# Verify message formatter has tool summaries
python -c "
import sys, types, importlib
for m in ['synapse', 'synapse.panel']:
    pkg = types.ModuleType(m); pkg.__path__ = ['python/synapse'] if m == 'synapse' else ['python/synapse/panel']
    sys.modules[m] = pkg
spec = importlib.util.spec_from_file_location('mf', 'python/synapse/panel/message_formatter.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert hasattr(mod, 'format_tool_summary'), 'format_tool_summary missing'
print('DESIGN formatter: OK')
"
```

---

## PHASE 3: TEST (sequential, after Phase 2)

Run existing test suite to verify no regressions, then run targeted tests for new code.

```bash
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -5
```

---

## SAFETY RULES

1. **Read before write** — every agent reads owned files fully before editing
2. **File ownership** — NEVER write to another agent's files
3. **Regression zero** — existing tests must keep passing
4. **Coaching tone** — all new error messages follow "Couldn't find X -- try Y" pattern
5. **Lighting Law** — any render-related code preserves intensity=1.0 / exposure-only convention
6. **No Houdini required** — all new code must be testable with hou stubs
7. **Determinism** — sort_keys=True in any new JSON serialization, no uuid4() in hot paths
8. **Source only** — edit `SYNAPSE/` repo source, never deployed copies

## Execution Plan

| Phase | Agents | Mode | Expected |
|-------|--------|------|----------|
| 1 | RENDER, ERROR, RECIPE | parallel (3 Task agents in worktrees) | ~3 min |
| 2 | WIRE, DESIGN | parallel (2 Task agents in worktrees) | ~3 min |
| 3 | TEST | sequential (1 Bash run) | ~1 min |

**Total: 5 agents, 3 phases, ~15 tasks.**
