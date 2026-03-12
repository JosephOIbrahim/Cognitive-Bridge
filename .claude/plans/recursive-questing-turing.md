# Phase 0, Sprint 1: USD + Qt + Storm Rendering a Cube

## Context

CarWash-2 (comfyui_3D_viewport) needs a Hydra Storm viewport rendering USD geometry in a Qt window as the foundation for all subsequent phases (camera system, AOV passes, ComfyUI bridge). The strategy doc identifies the USD build system on Windows as the #1 risk. We mitigate by using Python (usd-core + PySide6) for Sprint 1, deferring C++ to Sprint 2.

**Decision:** Python-first path. `pip install usd-core` + PySide6. Proves the pipeline works. C++ port follows.

## What We're Building

A single Python application (`viewport.py`) that:
1. Creates a `Usd.Stage` with a `UsdGeom.Cube`
2. Opens a Qt window with an OpenGL widget
3. Renders the cube via Hydra Storm (`HdStorm`) render delegate
4. Renders a depth AOV to buffer (verify pixel values are non-zero)

**Ship criterion:** Screenshot of a grey cube in a Qt window. Depth buffer has valid values.

## Dependencies to Install

```bash
pip install usd-core PySide6
```

- `usd-core` — Official Pixar USD Python wheels (includes pxr.Usd, pxr.UsdGeom, pxr.UsdImaging, Hydra, Storm)
- `PySide6` — Qt6 Python bindings with OpenGL support

## Implementation Plan

### Step 1: Install dependencies and verify imports

```bash
pip install usd-core PySide6
python -c "from pxr import Usd, UsdGeom, UsdImagingGL; print('USD OK')"
python -c "from PySide6.QtWidgets import QApplication; from PySide6.QtOpenGLWidgets import QOpenGLWidget; print('Qt OK')"
```

### Step 2: Create the project structure

```
comfyui_3D_viewport/
  src/
    viewport.py          # Main application — Qt window + Storm viewport
    stage_builder.py     # USD stage creation (cube, ground plane, light)
  requirements.txt       # usd-core, PySide6
```

### Step 3: Implement `stage_builder.py`

Minimal USD stage factory:
- `create_default_stage()` → in-memory `Usd.Stage`
- Add `UsdGeom.Cube` at `/World/Cube` (size 1.0)
- Add `UsdGeom.Xform` at `/World` as root
- Add `UsdLux.DomeLight` at `/World/DomeLight` (so Storm has something to shade with)
- Set up-axis to Y (USD default)
- Return the stage

### Step 4: Implement `viewport.py` — the Storm viewport

This is the core. The pattern for Hydra Storm in Python:

1. **QOpenGLWidget subclass** (`StormViewport`)
   - `initializeGL()`: Create `UsdImagingGLEngine` (this is the Hydra Storm entry point)
   - `paintGL()`: Call `engine.Render()` with camera params + render params
   - `resizeGL()`: Update viewport dimensions

2. **Camera setup** (minimal, no interaction yet — that's Phase 1):
   - Fixed perspective camera looking at origin
   - `GfCamera` with 50mm focal length, reasonable clipping planes
   - `GfFrustum` → view/projection matrices passed to `UsdImagingGLEngine.SetCameraState()`

3. **Render params**:
   - `UsdImagingGLRenderParams()` with frame=1, complexity=1.0
   - Enable Storm (the default GL delegate in UsdImagingGLEngine)

4. **Depth AOV verification**:
   - After first render, read back depth via `glReadPixels` with `GL_DEPTH_COMPONENT`
   - Print min/max depth values to console (non-zero = working)
   - This proves the pipeline for Phase 2's depth pass

5. **Main window**:
   - `QMainWindow` with `StormViewport` as central widget
   - Window title: "CarWash-2 — Storm Viewport"
   - Default size: 800x600

### Step 5: Verify depth AOV

After the cube renders, read back the GL depth buffer and log:
```
Depth AOV: min=0.85, max=1.0, non-zero pixels: 480000/480000
```
This confirms Storm is writing real depth values, not just color.

## Key Technical Details

### UsdImagingGLEngine API

```python
from pxr import UsdImagingGL, UsdGeom, Gf, Sdf

engine = UsdImagingGL.Engine()
engine.SetRendererAov(UsdImagingGL.AovTokens.color)  # or .depth
engine.SetCameraState(viewMatrix, projMatrix)
engine.SetRenderViewport((0, 0, width, height))

params = UsdImagingGL.RenderParams()
params.frame = Usd.TimeCode.Default()
params.complexity = 1.0
params.drawMode = UsdImagingGL.DrawMode.DRAW_SHADED_SMOOTH

engine.Render(stage.GetPseudoRoot(), params)
```

### Qt OpenGL Integration Pattern

```python
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer

class StormViewport(QOpenGLWidget):
    def initializeGL(self):
        self._engine = UsdImagingGL.Engine()
        # ... setup

    def paintGL(self):
        self._engine.Render(self._root, self._params)

    def resizeGL(self, w, h):
        self._engine.SetRenderViewport((0, 0, w, h))
```

### Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| `usd-core` wheels don't include Storm/GL on Windows | Check `UsdImagingGL` import. If missing, fall back to NVIDIA pre-built or Gaffer's bundled USD. |
| OpenGL context sharing between Qt and Storm | Use `QOpenGLWidget` (not `QGLWidget`). Storm expects a current GL context — `paintGL()` guarantees this. |
| Python 3.14 incompatibility with usd-core | If wheels aren't available for 3.14, use `py -3.12` or a venv with compatible Python. |
| PySide6 + usd-core GL conflict | Both bind OpenGL. If crashes occur, ensure single GL context via Qt's surface format. |

## Files to Create

| File | Purpose |
|------|---------|
| `src/viewport.py` | Main app — QMainWindow + StormViewport (QOpenGLWidget) + UsdImagingGLEngine |
| `src/stage_builder.py` | USD stage factory — cube + dome light |
| `requirements.txt` | usd-core, PySide6 |

## Files NOT Modified

No changes to comfyui-agent. This is a standalone app in comfyui_3D_viewport/.

## Verification

1. `pip install -r requirements.txt` succeeds
2. `python src/viewport.py` opens a Qt window
3. A shaded grey cube is visible in the viewport
4. Console prints depth AOV stats with non-zero values
5. Window resizes without crashing
