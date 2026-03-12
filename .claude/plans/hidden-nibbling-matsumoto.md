# Plan: Cinema Camera Rig — Solaris/LOP Integration

## Context

The Cinema Camera Rig v4.0 currently lives entirely in OBJ context (Object-level HDA). The architecture spec (`CINEMA_CAMERA_RIG_v4_PHYSICAL_ARCHITECTURE.md`) explicitly calls this a "LOP HDA" and references Solaris throughout. A `usd_builder.py` already exists with pure-USD functions (`build_usd_camera_rig`, `configure_render_product`) that build the correct Xform hierarchy using `pxr`. The task is to create a LOP-level HDA builder that brings the camera rig into Solaris natively.

## Research Summary

### What Exists
- **OBJ orchestrator** (`build_camera_rig_orchestrator.py`): Object-level HDA with cam, pupil null, biomechanics chopnet, post-processing cop2net, 5-tab parameter interface, 27 sub-HDA expression wirings
- **usd_builder.py**: Pure `pxr` module -- `build_usd_camera_rig()` creates USD Xform hierarchy (RigRoot/FluidHead/Body/Sensor/EntrancePupil), `configure_render_product()` writes Cooke /i + ASWF EXR metadata
- **Architecture spec**: References "LOP HDA" as the intended form, mentions `karma_lens_shader.py` for LOP binding, shader parameter binding via LOP Python

### What's Needed
A new LOP-level HDA builder (`build_camera_rig_lop.py`) that:
1. Creates a LOP HDA (`cinema::camera_rig_lop`) in the Lop context
2. Uses LOP nodes (Camera, Edit Properties, Python Script) to author the USD hierarchy
3. Exposes the same parameter interface as the OBJ version
4. Wires Cooke /i metadata via RenderProduct configuration
5. Optionally references the OBJ rig's CHOPs/COPs via import or keeps them as LOP-native

### Key LOP Nodes to Use
- `camera` -- LOP camera node (authors UsdGeom.Camera)
- `editproperties` -- Set USD attributes (custom cinema: namespace attrs)
- `pythonscript` -- Run usd_builder.py functions to author full hierarchy
- `renderproduct` -- Configure Karma render product with metadata
- `rendersettings` -- Karma XPU configuration

## Implementation Plan

### Step 1: Create `build_camera_rig_lop.py`
New builder file at `scripts/python/cinema_camera/builders/build_camera_rig_lop.py`

Creates `cinema::camera_rig_lop` HDA in Lop context containing:
- **Python Script LOP** calling `usd_builder.build_usd_camera_rig()` to author the full Xform hierarchy with all custom attributes
- **RenderProduct LOP** calling `usd_builder.configure_render_product()` for Cooke /i metadata
- **RenderSettings LOP** for Karma XPU defaults

Same 5-tab parameter interface as OBJ version (can share parm template construction code).

### Step 2: Extract shared parameter template builder
Factor out the parameter template construction from the OBJ orchestrator into a shared function both builders can call, avoiding duplication.

### Step 3: Wire parameter expressions
LOP Python Script node reads HDA-level parms and passes them to `build_usd_camera_rig()` as CameraState/LensState objects, or directly sets USD attributes via expressions.

### Step 4: Rebuild via Synapse, test, commit

## Verification
1. Rebuild LOP HDA via Synapse
2. Create instance in /stage (lopnet)
3. Verify USD hierarchy: /CinemaRig/FluidHead/Body/Sensor/EntrancePupil
4. Verify Karma can render from the LOP camera
5. Verify Cooke /i metadata on RenderProduct
6. Run G6-equivalent propagation check for LOP parms

## Files to Create/Modify
- **CREATE**: `scripts/python/cinema_camera/builders/build_camera_rig_lop.py`
- **MODIFY**: `scripts/python/cinema_camera/builders/build_camera_rig_orchestrator.py` (extract shared parm templates)
- **REFERENCE**: `scripts/python/cinema_camera/usd_builder.py` (reuse as-is)
