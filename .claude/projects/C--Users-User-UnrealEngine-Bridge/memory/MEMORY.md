# UnrealEngine_Bridge Memory

## Viewport Perception
- `ue_viewport_percept` returns cached/stale frames when editor FPS is low (e.g. 3 FPS)
- For fresh renders: spawn `SceneCapture2D` at camera position, `capture_scene()`, `export_render_target()` — file is PNG despite no extension
- Copy exported file with `.png` extension to view via Read tool

## Niagara Systems
- `NS_CRT_DotGrid` won't activate (active=False always). Use `NS_DotGrid` instead.
- `NS_DotGrid` auto-deactivates after spawning. Need `reset_system()` + `activate(True)` before each use.
- Tiling many Niagara actors (66+) kills FPS. Not viable for dense coverage.
- Niagara systems carry their own material in the sprite renderer — external dot materials (M_CRT_Dot etc.) are not referenced.

## Material Editing via Python
- `MaterialEditingLibrary` (mel) works for creating nodes, connecting expressions, recompiling
- Complex node graphs are fragile to build — simple flat-color materials are reliable
- `delete_all_material_expressions()` then rebuild is cleaner than modifying existing graphs
- `recompile_material()` is required after changes

## Scene Layout
- CRT screen area: X -2155 to +2155, Z 625 to 2375, screen backing at Y=275
- CRT_Camera: CineCameraActor, FOV 59.1, faces +Y (yaw=90)
- Scene lighting is natural (window + cloudy weather), NOT from CRT_KeyLight/FillLight
- 560 actors total, 483 StaticMeshActors (apartment environment)

## User Preferences
- Typography is the HERO, environment is BACKGROUND
- Direct feedback style — "blocked" means abandon approach immediately
- Natural diffuse lighting, not dramatic spot/point lights
