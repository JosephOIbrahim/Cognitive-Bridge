# Session Handover
**Date:** 2026-03-10
**Project:** UnrealEngine_Bridge

## What Was Done
- Executed CRT cleanup dispatch (all phases)
- Restored M_CRT_Screen and M_CRT_Frame from git commit bcb332e (original graphs recovered)
- Deleted orphaned assets: M_CRT_Dot, M_CRT_Dot_Off, M_CRT_Pink
- Re-enabled 6 disabled apartment lights (Apartment_FillLight, Apt_Light_0-3, RectLight)
- Fixed CRT_PostProcess: was Manual exposure with EV bias 10.0 (crushed scene to black and killed FPS). Now Histogram auto-exposure, bias 0.0, warm gain (1.15, 0.9, 0.95)
- FPS recovered from 3 to 25 after PP fix
- Typography material rebuilt: emissive 1.0 warm white, Unlit shading, WorldSize 250
- Screen percentage reset from 50 to 100
- Cleaned up temp SceneCapture2D actor and RT_TempCapture asset

## Decisions Made
| Decision | Why |
|----------|-----|
| CRT_PostProcess exposure was root cause of 3 FPS AND black scene | Manual EV10 = extreme overexposure calibration, renderer working overtime |
| Changed to Histogram auto-exposure, bias 0 | Sane default that adapts to scene lighting |
| Typography WorldSize 250 | At 4760 units camera distance, WorldSize 40 was ~11px. 250 should be readable |
| Emissive 1.0 for typography | 0.08 was invisible, 5.0 blew out HDR. 1.0 is balanced |

## Open Threads
- [ ] Visually verify typography readability in editor viewport (couldn't decode viewport image inline)
- [ ] Fine-tune CRT_PostProcess if auto-exposure doesn't look right
- [ ] Tune composition: camera-to-CRT framing, text position
- [ ] Consider: CRT dot effect as subtle post-process, or clean typography preferred
- [ ] 568 actors total, scene is stable

## Key Files
- `/Game/Materials/M_CRT_Screen` — RESTORED from git
- `/Game/Materials/M_CRT_Frame` — RESTORED from git
- `/Game/Materials/M_CRT_Typography` — Unlit, emissive 1.0 warm white
- `CRT_Typography_Hero` actor — TextRenderActor at (0, 260, 1500), WorldSize 250, yaw -90
- `CRT_PostProcess` — Histogram auto-exposure, bias 0.0, warm gain, bloom 0, vignette 0
