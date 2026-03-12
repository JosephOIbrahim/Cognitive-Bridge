# Synapse Session Memory

## Houdini 21 + PySide6
- Houdini 21.0 uses **PySide6** (Qt6), not PySide2. Always use try/except import pattern.
- `QApplication.instance()` returns **None** in Houdini 21's PySide6 -- clipboard via Qt is broken.
- **Use `clip.exe`** on Windows as primary clipboard method (`subprocess.run(["clip"], input=text.encode("utf-8"), creationflags=0x08000000)`).
- Qt clipboard fallback: try `QGuiApplication.instance()` after `QApplication.instance()`.

## .synapse / houdini21.0 Sync
- Source of truth: `~/.synapse/houdini/` (panel, shelf, toolbar)
- Installed to: `~/houdini21.0/` (python_panels, scripts/python, toolbar)
- **Auto-sync**: git post-commit hook in `~/.synapse/.git/hooks/post-commit` copies 3 files on every commit.
- Houdini loads `synapse_shelf.py` from `~/houdini21.0/scripts/python/` (takes priority over `~/.synapse/` path).

## Design System
- Background palette aligned to Houdini 21 dark theme: NEAR_BLACK=#3C3C3C, CARBON=#333333, VOID=#252525, GRAPHITE=#222222
- Font scale at 2x for 4K displays: LABEL/SMALL=22px, UI=24px, BODY=26px, TITLE=32px, HERO=44px
- Button hover uses explicit #484848 (GRAPHITE is now darker than CARBON, can't reuse for hover)
- `synapse_styles.py` generates QSS from `tokens.py` -- change tokens, not the stylesheet directly.

## Houdini Install Paths
- Latest: `C:\Program Files\Side Effects Software\Houdini 21.0.596\`
- Prefs: `C:\Users\User\houdini21.0\`
- Multiple versions installed: 20.5.684, 21.0.440, 21.0.512, 21.0.559, 21.0.596

## Scene Building Patterns (learned from artist)

### Solaris Scene Assembly
- **For Karma rendering**: use **sublayer** LOP (not assetreference) -- assetreference is invisible to Karma
- Use **Asset Reference** nodes for viewport-only work or production geo (not inline sphere/cube prims)
- Houdini ships test assets at `$HFS/houdini/usd/assets/` (rubbertoy, pig, etc.)
- Wire order in merge: geometry first, then lights, then referenced assets
- **Material library** with multiple subnets preferred over separate matlib + assign nodes
- Assign geo paths directly in matlib (`geopath1`, `geopath2`) -- no separate assign nodes
- Material prim patterns must match exact USD prim paths (`/rubbertoy/geo/shape`, NOT `/rubbertoy/*`)

### Lighting Setup
- **Always use HDRI** on dome light (Greyscale Gorilla HDRIs at `D:\GreyscaleGorillaAssetLibrary\`)
- Dome light exposure ~0.25 for studio HDRI (HDRI provides its own range)
- Key light: enable **color temperature** for natural warmth, exposure ~1.0
- Intensity always 1.0 (Lighting Law) -- brightness via exposure only

### Render Pipeline
- Karma LOP in /stage feeds usdrender ROP in /out
- Set `picture` on Karma LOP AND `outputimage` on ROP for reliable output
- **soho_foreground=1** on usdrender ROP required for synchronous file write (default=0 returns before done)
- Karma node `camera` parm defaults to `/cameras/camera1` -- must set explicitly
- Camera LOP `focalLength` in mm (e.g., 25 = wide, 50 = standard); `focalLengthConverted` = scene units
- Use `iconvert.exe` from `$HFS/bin/` to convert EXR to JPEG for preview
- Sticky notes on render_settings for LPE tag pass splitting

### Network Organization
- Clean chain: merge -> matlib -> camera -> render_settings -> karma
- No orphan assign nodes -- keep material assignments inside matlib

## FORGE Self-Improvement Loop
- Cycles 1-3 complete: 18 scenarios, 100% pass rate, 23 corpus entries, 11 backlog items
- **NaN/Inf** persist in Houdini parms -- no guard (BL-009)
- **execute_python** nested functions lose top-level variable scope -- use inline code
- **create_material** returns wrong USD path -- `_shader` suffix not captured (BL-011)

## RAG Folder Config
- Persisted at `~/.synapse/rag_path` (single-line text file)
- Auto-sets `SYNAPSE_RAG_ROOT` env var on shelf import
- Panel button opens folder picker, supports change/clear

## MCP Resilience Upgrade (2026-03-05)
- **Phase A done**: `mcp/server.py` — circuit breaker, rate limiter, stall detection, read-only fast path
- **Phase B done**: `mcp/session.py` — 30-min TTL, `reap_expired()`, Living Memory hooks
- **Phase C done**: `mcp/tools.py` — journal logging in `dispatch_tool()` finally block
- **Phase D TODO**: SSE for server-initiated events (render progress, gate approvals)
- **Phase E TODO**: Route panel ToolExecutor through MCP

## Panel Fixes (2026-03-05)
- Fallback model: `claude-sonnet-4-6`; context bar logs errors; tool_status 3-arg signal
- `shot_login.py` checks evolution triggers, returns `evolution_recommended` flags
- WS URL button: hover underline + pointer cursor
