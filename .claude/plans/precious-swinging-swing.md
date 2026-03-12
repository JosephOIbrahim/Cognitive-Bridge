# Copernicus (COPs) Integration — 4-Phase MOE Agent Team Sprint Plan

## Context

Synapse has excellent RAG knowledge for Copernicus (8 files, ~85KB) but zero operational handlers. This plan adds 20-21 new MCP tools across 4 phases, each executed by a dedicated MOE agent team. Phases are sequential — each phase completes, gates pass, then the next begins.

**Current state:** 87 MCP tools, 86 handlers across 8 handler files, 48 recipes, 2022 tests passing.
**Target state:** ~107 MCP tools, ~106 handlers across 9 handler files, ~58 recipes, ~2100+ tests.

## Registration Chain (5 touch points per tool)

Every new tool requires edits to:
1. `python/synapse/core/protocol.py` — `CommandType` enum
2. `python/synapse/server/handlers_cops.py` — handler method (NEW file in Phase 1)
3. `python/synapse/server/handlers.py` — import mixin, MRO, `_register_handlers()`, `_CMD_CATEGORY`, `_READ_ONLY_COMMANDS`
4. `mcp_server.py` — `Tool()` in `list_tools()`, entry in `TOOL_DISPATCH`
5. `python/synapse/mcp/tools.py` — entry in `_TOOL_DEFS`

Plus: `mcp_tools_cops.py` (new tool group module), `core/aliases.py`, `tests/test_cops.py`

---

## PHASE 1: Foundation (5 tools)

**Tools:** `cops_create_network`, `cops_create_node`, `cops_connect`, `cops_set_opencl`, `cops_read_layer_info`

### Agent Team (3 agents, sequential: A → B → C)

| Agent | Icon | MOE Role | Exclusive Write |
|-------|------|----------|-----------------|
| **HANDLER** | ◆ | COP2/Copernicus API Specialist | `handlers_cops.py` (CREATE) |
| **WIRE** | ⟡ | Registration Chain Integrator | `protocol.py`, `handlers.py`, `mcp_server.py`, `mcp/tools.py`, `mcp_tools_cops.py` (CREATE) |
| **TEST** | ◈ | Test & Alias Engineer | `tests/test_cops.py` (CREATE), `core/aliases.py` |

### Tasks

**HANDLER (4 tasks):**
1. Create `handlers_cops.py` with `CopsHandlerMixin` class — standard mixin pattern (hou try/except, resolve_param, run_on_main, hou.undos.group for mutations)
2. Implement `_handle_cops_create_network` — creates `cop2net` container at parent, optional initial nodes, returns network path
3. Implement `_handle_cops_create_node`, `_handle_cops_connect`, `_handle_cops_set_opencl` — create/wire/configure COP nodes, set OpenCL kernel code on `kernelcode` parm
4. Implement `_handle_cops_read_layer_info` — read-only: query resolution, data type, channel count, cook status

**WIRE (3 tasks):**
1. Add 5 `CommandType` entries to `protocol.py`, create `mcp_tools_cops.py` with GROUP_KNOWLEDGE
2. In `handlers.py`: import CopsHandlerMixin, add to SynapseHandler MRO, register 5 handlers, add to `_CMD_CATEGORY` (PIPELINE), add `cops_read_layer_info` to `_READ_ONLY_COMMANDS`
3. Add 5 `Tool()` objects + TOOL_DISPATCH entries in `mcp_server.py`, add 5 `_TOOL_DEFS` entries in `mcp/tools.py`

**TEST (2 tasks):**
1. Add COPs aliases to `aliases.py`: `cop_network`, `kernel_code`, `cop_type`, `layer`, `resolution`, `precision`
2. Create `tests/test_cops.py` with hou stub (mock cop2net, COP nodes), importlib bootstrap, 15-20 tests across 5 handlers

### Phase Gate
```bash
python -c "from synapse.server.handlers_cops import CopsHandlerMixin; print('OK')"
grep -c "cops_" python/synapse/server/handlers.py    # ≥5
python -m pytest tests/test_cops.py -v --tb=short
python -m pytest tests/ -v --tb=short                 # full suite, 0 failures
```

---

## PHASE 2: Pipeline Integration (4 tools)

**Tools:** `cops_to_materialx`, `cops_composite_aovs`, `cops_analyze_render`, `cops_slap_comp`

### Agent Team (2 agents, sequential: D → E)

| Agent | Icon | MOE Role | Exclusive Write |
|-------|------|----------|-----------------|
| **BRIDGE** | ◆ | Render Pipeline Interop Specialist | `handlers_cops.py` |
| **INTEGRATE** | ⟡ | Registration + Autonomy Integrator | `protocol.py`, `handlers.py`, `mcp_server.py`, `mcp/tools.py`, `mcp_tools_cops.py`, `autonomy/validator.py`, `tests/test_cops.py`, `aliases.py` |

### Tasks

**BRIDGE (4 tasks):**
1. `_handle_cops_to_materialx` — configure `op:` path from COP output to MaterialX texture input
2. `_handle_cops_composite_aovs` — build COP network loading Karma AOV layers (beauty, diffuse, specular, depth), merge/recombine
3. `_handle_cops_analyze_render` — quality analysis: black pixels, NaN/Inf, dynamic range, noise, clipping → structured report for FORGE
4. `_handle_cops_slap_comp` — configure live viewport compositing overlay

**INTEGRATE (4 tasks):**
1. Add 4 CommandType entries, register in handlers.py, add to _CMD_CATEGORY (RENDER for analyze/composite, PIPELINE for materialx/slap_comp)
2. Add 4 tools to mcp_server.py + mcp/tools.py, update mcp_tools_cops.py
3. Add optional `_check_cops_pipeline()` to `autonomy/validator.py` for COP-based texture validation
4. Write 12-16 tests for Phase 2 handlers, add aliases (`exr_path`, `aov_list`, `material_input`, `comp_mode`)

### Phase Gate
```bash
grep -c "cops_" python/synapse/mcp/tools.py           # ≥9
python -m pytest tests/test_cops.py -v --tb=short
python -m pytest tests/ -v --tb=short                  # full suite, 0 failures
```

---

## PHASE 3: Procedural & Motion Design (6 tools)

**Tools:** `cops_create_solver`, `cops_procedural_texture`, `cops_growth_propagation`, `cops_reaction_diffusion`, `cops_pixel_sort`, `cops_stylize`

### Agent Team (3 agents, sequential: F → G → H)

| Agent | Icon | MOE Role | Exclusive Write |
|-------|------|----------|-----------------|
| **SOLVER** | ◆ | Block Solver & Simulation Specialist | `handlers_cops.py` (3 solver methods only) |
| **STYLE** | ⟡ | Motion Design & Stylization Specialist | `handlers_cops.py` (3 style methods only) |
| **INTEGRATE** | ◈ | Registration + Recipe Author | `protocol.py`, `handlers.py`, `mcp_server.py`, `mcp/tools.py`, `mcp_tools_cops.py`, `recipes.py`, `tests/test_cops.py`, `aliases.py` |

### Tasks

**SOLVER (3 tasks):**
1. `_handle_cops_create_solver` — Block Begin/End pair with feedback wiring, configurable iterations
2. `_handle_cops_growth_propagation` — solver loop with dilate/blur/threshold for seed growth
3. `_handle_cops_reaction_diffusion` — Gray-Scott R-D via OpenCL kernel in solver

**STYLE (3 tasks):**
1. `_handle_cops_procedural_texture` — noise generation (perlin/worley/simplex), ramp mapping, tiling
2. `_handle_cops_pixel_sort` — OpenCL pixel sorting by luminance/hue, configurable threshold/direction
3. `_handle_cops_stylize` — NPR effects: toon (quantize), risograph (halftone+palette), posterize, edge detect

**INTEGRATE (4 tasks):**
1. Add 6 CommandType entries, register in handlers.py
2. Add 6 tools to mcp_server.py + mcp/tools.py, update mcp_tools_cops.py
3. Add 5 new recipes to `recipes.py`: `copernicus_procedural_texture`, `copernicus_pixel_sort`, `copernicus_reaction_diffusion`, `copernicus_growth`, `copernicus_stylize`
4. Write 18-24 tests, add aliases (`seed_mask`, `growth_rate`, `feed_rate`, `kill_rate`, `noise_type`, `sort_direction`, `style_type`, `iterations`)

### Phase Gate
```bash
grep -c "cops_" python/synapse/mcp/tools.py           # ≥15
grep -c "copernicus_" python/synapse/routing/recipes.py # ≥6 (1 existing + 5 new)
python -m pytest tests/test_cops.py -v --tb=short
python -m pytest tests/ -v --tb=short                  # full suite, 0 failures
```

---

## PHASE 4: Advanced + Polish (5 tools + recipes + RAG + docs)

**Tools:** `cops_wetmap`, `cops_bake_textures`, `cops_temporal_analysis`, `cops_stamp_scatter`, `cops_batch_cook`

### Agent Team (3 agents, sequential: I → J → K)

| Agent | Icon | MOE Role | Exclusive Write |
|-------|------|----------|-----------------|
| **ADVANCED** | ◆ | Wetmap/Baking/Temporal Specialist | `handlers_cops.py` (3 methods: wetmap, bake, temporal) |
| **BATCH** | ⟡ | PDG+COPs Batch Integration Specialist | `handlers_cops.py` (2 methods: stamp_scatter, batch_cook) |
| **POLISH** | ◈ | Registration + RAG + Docs Finalizer | All registration files, `recipes.py`, `semantic_index.json`, `CLAUDE.md`, `README.md`, `tests/test_cops.py`, `aliases.py` |

### Tasks

**ADVANCED (3 tasks):**
1. `_handle_cops_wetmap` — SOP velocity/collision → UV-space COP with blur/decay
2. `_handle_cops_bake_textures` — high-to-low poly UV projection (normal, AO, curvature maps)
3. `_handle_cops_temporal_analysis` — cross-frame coherence: diff maps, flicker detection (read-only)

**BATCH (2 tasks):**
1. `_handle_cops_stamp_scatter` — stamp image scattering with randomized transform per instance
2. `_handle_cops_batch_cook` — TOP network iterating COP operations, follows handlers_tops.py PDG patterns

**POLISH (5 tasks):**
1. Add 5 CommandType entries, register in handlers.py, add to _CMD_CATEGORY
2. Add 5 tools to mcp_server.py + mcp/tools.py, final mcp_tools_cops.py update
3. Add 3-4 recipes: `copernicus_wetmap`, `copernicus_bake_textures`, `copernicus_stamp_scatter`, `copernicus_batch_process`
4. Expand `semantic_index.json` with COPs trigger keywords across all 8 Copernicus RAG files
5. Update `CLAUDE.md` (handler counts, tool counts, COPs section) and `README.md` (badge, tool count, test count)

### Phase Gate
```bash
grep -c "cops_" python/synapse/mcp/tools.py           # ≥20
grep -c "copernicus_" python/synapse/routing/recipes.py # ≥10
python -m pytest tests/test_cops.py -v --tb=short      # 60-80 tests
python -m pytest tests/ -v --tb=short                  # full suite, 0 failures
grep "COPs" CLAUDE.md                                  # docs updated
```

---

## Cross-Phase Summary

| Phase | Agents | Tools | Cumulative | New Files | Recipes |
|-------|--------|-------|------------|-----------|---------|
| 1: Foundation | 3 | 5 | 5 | handlers_cops.py, test_cops.py, mcp_tools_cops.py | 0 |
| 2: Pipeline | 2 | 4 | 9 | — | 0 |
| 3: Procedural | 3 | 6 | 15 | — | +5 |
| 4: Advanced | 3 | 5 | 20 | — | +4 |
| **Total** | **11 roles** | **20** | **107** | **3 new** | **+9 (57 total)** |

## Verification

After each phase: `python -m pytest tests/ -v --tb=short` (full suite, 0 failures).
After Phase 4: final count validation of tools, handlers, recipes, tests in CLAUDE.md.

## Key Files

- `python/synapse/server/handlers_cops.py` — NEW: all 20 COP handler methods as `CopsHandlerMixin`
- `python/synapse/server/handlers.py` — import mixin, MRO, register all handlers
- `python/synapse/core/protocol.py` — 20 new CommandType entries
- `mcp_server.py` — 20 Tool() objects + TOOL_DISPATCH entries
- `python/synapse/mcp/tools.py` — 20 _TOOL_DEFS entries
- `mcp_tools_cops.py` — NEW: GROUP_KNOWLEDGE + TOOL_NAMES
- `python/synapse/core/aliases.py` — COPs parameter aliases
- `python/synapse/routing/recipes.py` — 9 new Copernicus recipes
- `tests/test_cops.py` — NEW: 60-80 tests
- `rag/documentation/_metadata/semantic_index.json` — expanded triggers
