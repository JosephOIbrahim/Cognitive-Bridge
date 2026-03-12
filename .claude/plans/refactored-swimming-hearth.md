# Pentagram Redesign — SYNAPSE Panel

## Context

The panel is cluttered. Seven sections compete for attention, a 6-button grid wastes ~176px on rarely-used tools, duplicate messages spam the chat, and the activity log eats space for dev-only info. The chat — the actual product — gets squeezed into whatever's left.

Goal: Make the chat dominant, reduce non-chat overhead from ~516px to ~132px, and give every remaining element clear hierarchy.

## New Layout (4 zones)

```
+------------------------------------------+
| SYNAPSE  * Connected          port 9999 ⋯|  header (40px)
+------------------------------------------+
| /stage > geo1  structured  * Ready  f24  |  context bar (~56px)
| [Stage Info] [Materials] [Preflight]     |
+------------------------------------------+
|                                          |
| Chat                                     |  chat (stretch=1, DOMINANT)
|                                          |
| [__input________________________] [Send] |
+------------------------------------------+
| ▶ ACTIVITY                               |  collapsible (0px default)
+------------------------------------------+
| [Disconnect]        v6.1.0  ws://...     |  footer (36px)
+------------------------------------------+
```

## Changes

### 1. Merge title + status → unified header
**File:** `synapse_panel.pypanel` — replace `_build_title_bar()` + `_build_status_bar()` with `_build_header()`

Single `QWidget#panel_header` row:
- "SYNAPSE" label (SIZE_TITLE, weight 600, letter-spacing 2px)
- Status dot (inline, 8px)
- Status label ("Connected", SIZE_SMALL)
- stretch
- Status detail ("port 9999", SIZE_LABEL, SLATE)
- QToolButton overflow "..." → opens QMenu with the 6 tool actions

**File:** `synapse_styles.py` — remove `QFrame#title_bar`, `QFrame#status_bar` rules. Add `QWidget#panel_header` and `QMenu#overflow_menu` rules.

### 2. Remove tool grid → overflow menu
**File:** `synapse_panel.pypanel` — delete `_build_tool_grid()`, add `_build_overflow_menu()` returning QMenu

All 6 buttons (Project Setup, RAG Folder, Inspect Selection, Inspect Scene, Health Check, Last Result) become menu items on the "..." QToolButton.

### 3. Refine context bar
**File:** `context_bar.py` — align horizontal margins to MD (16px), transparent background, drop bottom border

### 4. Activity log → collapsible, hidden by default
**File:** `synapse_panel.pypanel` — rewrite `_build_activity_log()`

QPushButton toggle "▶ ACTIVITY" / "▼ ACTIVITY", log QTextEdit hidden by default, max-height 150px when expanded.

**File:** `synapse_styles.py` — add `QPushButton#activity_toggle` flat style

### 5. Compact footer
**File:** `synapse_panel.pypanel` — simplify `_build_connection_bar()`

Move version label from header to footer (low-priority info). Keep Disconnect + ws URL.

### 6. Chat area polish
**File:** `synapse_panel.pypanel` — adjust `_build_chat_area()` margins

Increase top margin to MD, add border-radius 6px on input, focus border color SIGNAL.

**File:** `synapse_styles.py` — add `QLineEdit#chat_input` and `QPushButton#send_button` rules with border-radius, focus state, hover state.

### 7. Message deduplication
**File:** `synapse_panel.pypanel` — add `_should_show_message()` method, apply in `_sys()` and diagnostic/preflight output

Hash-based dedup with 5-second window prevents identical messages from repeating.

### 8. Reassemble layout
**File:** `synapse_panel.pypanel` — update `_build_ui()` assembly order:
1. `_build_header()`
2. context bar widget
3. `_build_chat_area()` (stretch=1)
4. `_build_activity_log()` (collapsible)
5. `_build_connection_bar()`

## Files Modified

| File | What Changes |
|------|-------------|
| `houdini/python_panels/synapse_panel.pypanel` | Layout restructure (steps 1,2,4,5,6,7,8) |
| `design/synapse_styles.py` | QSS rules for new header, overflow menu, toggle, input polish (steps 1,2,4,6) |
| `python/synapse/panel/context_bar.py` | Margin/background alignment (step 3) |

After editing repo source, copy pypanel to `~/houdini21.0/python_panels/`.

## Space Budget

| Section | Before | After |
|---------|--------|-------|
| Title + Status bars | 112px | 40px (merged header) |
| Tool grid | 176px | 0px (overflow menu) |
| Context bar | 56px | 56px |
| Activity log | 120px | 0px (collapsed) |
| Connection bar | 52px | 36px |
| **Total overhead** | **~516px** | **~132px** |

Chat gains ~384px — roughly 3x more space on a typical docked panel.

## Verification

1. Restart Houdini, open Synapse panel
2. Confirm header shows "SYNAPSE * Connected port 9999" in one line
3. Click "..." — verify all 6 tools appear in dropdown menu
4. Context bar shows breadcrumb + quick actions
5. Chat area dominates the panel
6. Activity log hidden — click "▶ ACTIVITY" to expand
7. Run `/preflight` twice — verify no duplicate messages
8. Run `/diagnose` — verify no duplicate messages
9. Test all 6 overflow menu items work (Project Setup, RAG Folder, etc.)
