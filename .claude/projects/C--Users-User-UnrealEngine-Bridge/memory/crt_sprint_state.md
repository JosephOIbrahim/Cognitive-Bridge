# CRT-B Sprint State (Paused after Phase 1)
## Date: 2026-03-09

### Phase 1: COMPLETE
- NIAGARA N1-N3: Done. 2-tile approach deployed (TileL x=-1075, TileR x=+1075, scale 12,1,9). Fixed bounds expanded to -150..150. No user params exposed.
- MATERIAL M1-M3: Done. Niagara sprite flags enabled on M_CRT_Dot, M_CRT_Dot_Off, M_CRT_Pink. All OPAQUE blend — MUST change to Masked/Translucent for sprites.
- Gate 1: Not yet run (needs cleanup of test actors)

### Phase 2: NOT STARTED
- N4: Deploy full-coverage dot grid (tiles already placed by N3)
- N5: Verify coverage
- M4: Fix blend mode (OPAQUE → Masked/Translucent) on dot materials
- M5: Boost M_CRT_Screen emissive
- C1: Optimize CRT_Camera framing
- C2: Tune lighting (key:fill ratio)
- C3: Enhance CRT_PostProcess

### Phase 3: NOT STARTED
- C4-C6: Polish, beauty captures, save

### Dispatch File
`.planning/CRT_NIAGARA_DISPATCH.md` — full dispatch prompt with all tasks

### Key Facts
- CRT_Camera: (0, -6764, 1510), yaw=90, FOV 59.1 (fixed this session from pitch=90 bug)
- Screen area: X:-2155 to +2155, Z:625 to 2375, Y~250-275
- CRT_Install_DotGrid: original single actor at (0, 250, 1500)
- CRT_DotGrid_TileL: (-1075, 250, 1500) scale (12,1,9)
- CRT_DotGrid_TileR: (1075, 250, 1500) scale (12,1,9)
- M_CRT_Dot: best for sprites (353 px instructions, DEFAULT_LIT, OPAQUE — needs blend fix)
- Commit c16eb3a pushed to master with camera fix
