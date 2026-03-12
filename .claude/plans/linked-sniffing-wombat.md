# Plan: ComfyUI Integration via MOE Agent Teams

## Context

The comfyui_3D_viewport has a working standalone viewport (GL rendering, physical cameras, AOV export, ControlNet bridge) and its sibling comfyui-agent has shipped Grafts A-D (3D type recognition, partner nodes, splat-to-mesh knowledge, viewport tool discovery). The EXECUTION_SPEC.md defines 5 phases to verify, fix, extend, and design the full integration. This plan executes Phases 1-4 using 4 parallel MOE agent teams. Phase 5 (architecture design doc) is deferred as director-led.

## Current State

- **comfyui-agent**: Grafts A-D shipped, 665+ tests, `source_tier` implemented, 3D triggers registered
- **comfyui_3D_viewport**: 187 tests, depth/normal AOV, ControlNet bridge, LOAD3D_CAMERA export, camera database
- **Gap**: No `LOAD3D_CAMERA` type in agent's type registry, no camera pipeline knowledge file, workflow_parse doesn't describe 3D connection types, Graft E demo tests not written

## MOE Agent Teams

### Team 1: Audit Expert (Phase 1) — RUNS FIRST
**Goal**: Verify graft knowledge is usable, identify gaps

Tasks:
1. Run `python -m pytest tests/ -v` in comfyui-agent — confirm 665+ green
2. Count 3D-related tests: `pytest tests/ --co -q | grep -i "3d\|mesh\|partner\|splat"`
3. Trace `_KNOWLEDGE_TRIGGERS` for 4 queries:
   - "3D mesh generation" → should hit `3d_partner_nodes`
   - "gaussian splat to mesh" → should hit `3d_workflows` + `3d_partner_nodes`
   - "camera angle for ControlNet" → should hit `3d_workflows`
   - Workflow with `Hunyuan3DLoader` → should trigger `3d_workflows`
4. Verify `source_tier` in discover result schema (`comfy_discover.py` line 376)
5. Check if `_build_summary` in `workflow_parse.py` labels 3D connection types

**Output**: Gap list → feeds Teams 2 and 3

### Team 2: Knowledge Expert (Phases 2+4) — AFTER Team 1
**Goal**: Fix routing gaps + add camera pipeline knowledge

Phase 2 (conditional on audit):
- Add missing trigger keywords to `_KNOWLEDGE_TRIGGERS` if audit reveals gaps
- Add 3D type descriptions to `workflow_parse.py _build_summary` if connections show "unknown type"

Phase 4 (LOAD3D_CAMERA):
- Create `agent/knowledge/3d_camera_pipeline.md` documenting:
  - Load3D → LOAD3D_CAMERA output schema (position, target, up, fov, focal_length)
  - `carwash_` extension fields for cinematographic cameras
  - AdvancedCameraControlNode as consumer
  - When to recommend camera pipeline to users
- Add triggers to `system_prompt.py`:
  ```python
  "3d_camera_pipeline": [
      "camera control", "camera position", "camera settings",
      "load3d camera", "LOAD3D_CAMERA", "cinematic", "focal length",
      "camera pipeline", "shot type", "framing", "camera rig",
  ],
  ```
- Add `LOAD3D_CAMERA` to type system in `agent/knowledge/comfyui_core.md`

Files modified:
- `C:\Users\User\comfyui-agent\agent\system_prompt.py`
- `C:\Users\User\comfyui-agent\agent\knowledge\comfyui_core.md`
- `C:\Users\User\comfyui-agent\agent\knowledge\3d_camera_pipeline.md` (NEW)
- `C:\Users\User\comfyui-agent\agent\tools\workflow_parse.py` (if needed)

### Team 3: Test Expert (Phase 3) — PARALLEL with Team 2
**Goal**: Create Graft E demo test infrastructure

Tasks:
1. Create `tests/fixtures/` directory in comfyui-agent
2. Create 3 mock workflow JSONs (ComfyUI API format):
   - `workflow_splat_to_mesh.json` — Load3DGaussian → MarchingCubes → SaveGLB
   - `workflow_controlnet_3d.json` — VNCCSPoseLoader → depth render → ControlNet → KSampler
   - `workflow_partner_comparison.json` — Hunyuan3D vs Meshy vs Tripo side-by-side
3. Create `tests/test_3d_demos.py` with 4+ tests:
   - `test_splat_to_mesh_discovery` — triggers surface conversion knowledge
   - `test_controlnet_3d_tool_discovery` — triggers surface viewport tools
   - `test_partner_node_comparison` — partner nodes ranked above community
   - `test_splat_to_mesh_workflow_parse` — UNDERSTAND categorizes 3D nodes

Files created:
- `C:\Users\User\comfyui-agent\tests\fixtures\workflow_splat_to_mesh.json`
- `C:\Users\User\comfyui-agent\tests\fixtures\workflow_controlnet_3d.json`
- `C:\Users\User\comfyui-agent\tests\fixtures\workflow_partner_comparison.json`
- `C:\Users\User\comfyui-agent\tests\test_3d_demos.py`

### Team 4: Architecture Expert (Phase 5) — AFTER Teams 2+3
**Goal**: Design integration contract document

Creates `C:\Users\User\comfyui_3D_viewport\docs\` with:
- **architecture_decision.md** — Custom node vs standalone vs hybrid (hybrid recommended based on existing code)
- **integration_contract.md** — LOAD3D_CAMERA schema, `carwash_` extensions, bridge message types (camera_update, aov_update)

## Execution Flow

```
Team 1: Audit Expert (Phase 1)
         │
         ├──→ Team 2: Knowledge Expert (Phases 2+4)
         │
         └──→ Team 3: Test Expert (Phase 3)  ← runs in parallel
                      │
                      └──→ Team 4: Architecture Expert (Phase 5)
```

## Verification

After each team completes:
```bash
# Verify agent tests (from comfyui-agent/)
cd C:\Users\User\comfyui-agent && python -m pytest tests/ -v

# Verify viewport tests (from comfyui_3D_viewport/)
cd C:\Users\User\comfyui_3D_viewport && .venv\Scripts\python -m pytest tests/ -v
```

**Success criteria**:
- All existing 665+ agent tests still green
- 4+ new demo tests green (test_3d_demos.py)
- All 187 viewport tests still green
- `3d_camera_pipeline.md` knowledge file created
- `LOAD3D_CAMERA` in agent type registry
- Architecture docs in `docs/`
