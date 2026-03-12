# Project Memory

## Key Decisions
- **Renderer**: Direct GL, not Hydra Storm. `usd-core` pip wheels exclude `UsdImagingGL`. Storm upgrade deferred to Sprint 7+.
- **Python**: Must use 3.12 venv (usd-core has no 3.14 wheels). Venv at `.venv/`.
- **Dependencies**: usd-core 25.11, PySide6 6.10.2, PyOpenGL 3.1.10, numpy
- **Two parallel tracks**: Viewport track (this repo) and Agent track (comfyui-agent). Don't modify SUPERDUPER_3D_GRAFT.md -- agent track handles that.

## Sprint Status
- Sprint 1: USD + Qt + GL cube + depth AOV -- DONE
- Sprint 1.5: Orbit camera (Alt+LMB/MMB/RMB, scroll, F) -- DONE
- Sprint 2: Physical camera projection (sensor+lens->matrix, LOAD3D_CAMERA export) -- DONE
- Sprint 3: AOV render-to-texture + Grid + HUD + USD loader + Camera JSON export -- DONE

## Project Structure
- `src/config.py` -- Centralized constants (window, camera, rendering, bridge). Override via env vars.
- `src/math_utils.py` -- Shared math: mat4 ops, look_at, normals. Single source for all modules.
- `src/viewport.py` -- Main app: QMainWindow + StormViewport (QOpenGLWidget) + shaders
- `src/camera.py` -- OrbitCamera with optional PhysicalProjection
- `src/projection.py` -- Physical camera: SensorGate + Lens -> projection matrices
- `src/stage_builder.py` -- USD stage factory (cube, ground, dome light)
- `src/grid.py` -- World grid (21x21 XZ lines) + RGB axis gizmo
- `src/hud.py` -- Camera info overlay, FPS counter, shortcut hints (QPainter)
- `src/aov_renderer.py` -- FBO depth + normal AOV passes, minimal PNG writer
- `src/usd_loader.py` -- USD file loading, mesh extraction, triangulation, normals
- `data/camera_lens_database.json` -- 6 cameras, 12 lenses, 4 presets (ARRI/RED/Sony + Cooke/Atlas)

## Run Command
```bash
cd comfyui_3D_viewport && .venv/Scripts/python src/viewport.py
cd comfyui_3D_viewport && .venv/Scripts/python src/viewport.py path/to/model.usd
```

## Keyboard Shortcuts
- Alt+LMB: Orbit | Alt+MMB: Pan | Alt+RMB/Scroll: Zoom | F: Frame
- 0: Simple FOV | 1: Alexa35+Cooke Ana 40 | 2: V-RAPTOR+Atlas 65 | 3: VENICE2+Cooke S7/i 50 | 4: Alexa35 S35+Cooke 25
- H: Toggle HUD | P: Save depth+normal AOV PNGs | L: Export LOAD3D_CAMERA JSON

## Code Quality Improvements (done)
- Deduplicated 3x matrix math (viewport/selection/environment) -> math_utils.py
- Deduplicated 2x normal computation (usd_loader/mesh_importers) -> math_utils.py
- Cached GL uniform locations (was per-frame string lookup, now initializeGL cache)
- Added resource cleanup: MainWindow.closeEvent -> grid/environment/aov cleanup + bridge disconnect
- Created config.py with all magic numbers (camera speeds, colors, window size, bridge URL)

## Test Suite
- **187 tests**, 14 test files, runs in ~0.3s. All fully mocked (no GL, no USD files, no network).
- Run: `.venv/Scripts/python -m pytest tests/ -v`
- pytest installed in .venv; config in `pytest.ini`
- Mocking strategy: pxr/trimesh/OpenGL.GL/PySide6 injected into `sys.modules` before imports
- `conftest.py` inserts `src/` into `sys.path` (src/ has no `__init__.py`, uses bare imports)
- Config env override tests use `monkeypatch.setenv()` + `importlib.reload(config)`
- Float comparisons: `pytest.approx(val, rel=1e-6)`, matrix roundtrips use `abs=1e-10`

| Test File | Tests | Covers |
|-----------|-------|--------|
| test_math_utils | 22 | vec3, mat4 multiply/inverse/roundtrip, look_at, vertex normals |
| test_config | 10 | defaults + env var overrides |
| test_undo | 14 | 4 Command subclasses + UndoStack |
| test_animation | 22 | lerp, lerp_angle (360 wrap), CameraAnimator |
| test_selection | 14 | ray-AABB, world AABB, SelectionManager |
| test_camera | 13 | OrbitCamera orbit/pan/dolly/frame/export |
| test_projection | 13 | SensorGate, Lens, PhysicalProjection, database |
| test_lighting | 12 | Light clamping/exposure, LightRig, uniforms |
| test_usd_loader | 11 | _triangulate, scene bounds, MeshData |
| test_mesh_importers | 11 | _extract_color, dispatch, errors |
| test_file_drop | 13 | normalize_path, detect_format |
| test_shading | 7 | ShadingMode, ShadingManager cycle |
| test_hud | 3 | HUD toggle/enabled |

## Known Remaining Debt
- viewport.py still 950+ LOC (god object). Could split into SceneManager + InputManager.
- print() logging throughout (no Python logging module yet)
- Several unintegrated modules: texture_manager.py, controlnet_bridge.py, gizmo.py, outliner.py, screenshot.py

## Gotchas
- MSAA disabled (samples=0) to enable direct depth buffer readback. Re-enable with render-to-texture later.
- Qt silently swallows exceptions in `initializeGL` -- always wrap in try/except with explicit print.
- Output buffering: use `PYTHONUNBUFFERED=1` or `-u` flag when capturing subprocess output.
- `from __future__ import annotations` in camera.py for TYPE_CHECKING import of PhysicalProjection.
- `glLineWidth(>1.0)` not supported in GL 3.3 Core Profile -- removed from grid.py.
- `GL_CHECK_FRAMEBUFFER_STATUS` is not a valid GL constant -- use the function `glCheckFramebufferStatus` instead.
