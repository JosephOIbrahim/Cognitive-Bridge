# Synapse Chat Panel Redesign

## Context

The current chat panel feels cramped and uninviting. Tight padding (10px 14px), thin margins (4px), single-line QLineEdit input, and a rigid stacked layout make it feel more like a debug console than a chat interface. The user wants it to feel like a hybrid between Houdini 21's native UI and WhatsApp's conversational UX — spacious, warm, and inviting to type into.

## Design Decisions (from user)

- **Context bar**: Integrated as compact chips inside the input area (not a separate fixed bar)
- **WhatsApp features**: All three — message grouping with timestamps, animated typing dots, multi-line growing input
- **Quick actions**: All three approaches — pill chips above input, collapsible toolbar, AND right-click context menu

## Changes by File

### 1. `python/synapse/panel/tokens.py` — New chat tokens

Add chat-specific spacing and sizing tokens:

```python
# Chat layout tokens
CHAT_BUBBLE_PADDING = 14      # Inner bubble padding (was 10)
CHAT_BUBBLE_RADIUS = 12       # Bubble corner radius (was 8)
CHAT_BUBBLE_MARGIN_Y = 2      # Between messages in same group
CHAT_GROUP_MARGIN_Y = 16      # Between different-sender groups
CHAT_BUBBLE_MAX_WIDTH = "85%"  # Bubble max width
CHAT_INPUT_MIN_H = 44         # Minimum input height
CHAT_INPUT_MAX_H = 160        # Maximum input height (grows to ~6 lines)
CHAT_TIMESTAMP_SIZE = 18      # Timestamp font size (small)
CHAT_TYPING_DOT_SIZE = 8      # Typing indicator dot diameter

# Font size control (user-adjustable via icon)
FONT_SCALE_MIN = 0.75
FONT_SCALE_MAX = 1.5
FONT_SCALE_DEFAULT = 1.0
FONT_SCALE_STEP = 0.125
```

### 2. `python/synapse/panel/message_formatter.py` — Spacious bubbles + timestamps + grouping

**Current problems**: padding:10px 14px, margin:4px, border-radius:8px — too tight.

**Changes**:
- Increase bubble padding to 14px 18px, margin to CHAT_GROUP_MARGIN_Y between groups / CHAT_BUBBLE_MARGIN_Y within groups
- Increase border-radius to 12px with WhatsApp-style directional radius (user bubbles: rounded top-left, flat top-right when grouped; synapse bubbles: opposite)
- Add timestamp div below message body — dimmed, right-aligned, SIZE_LABEL font
- Add `format_user_message(text, grouped=False, timestamp=None)` and `format_synapse_message(content, grouped=False, timestamp=None)` parameters
- When `grouped=True`, suppress the sender label ("You" / "SYNAPSE") and reduce top margin
- Move "SYNAPSE" label from `<span>` inside bubble to a standalone label above the first message in a group
- User bubble color stays CARBON; SYNAPSE bubble stays VOID — both get 1px subtle border (GRAPHITE) for definition
- Add `font_scale` parameter to all format functions, multiply all px values by scale

### 3. `python/synapse/panel/chat_display.py` — Message grouping + animated typing dots

**Message grouping logic**:
- Track `_last_sender` ("user" / "synapse" / "system") and `_last_message_time`
- Messages from the same sender within 60s are grouped (no repeated label, tight margin)
- Insert a timestamp divider between groups: centered, dimmed text like "2:34 PM" or "Today 2:34 PM"

**Typing indicator upgrade** (replace static "thinking..." with animated dots):
- Create `_TypingDotsWidget(QWidget)` — 3 circles that pulse with staggered QPropertyAnimation
- Each dot: 8px diameter, SIGNAL color at varying opacity (0.3 -> 1.0 -> 0.3), 300ms stagger
- Insert as a widget into the QTextBrowser via `QTextBrowser.document()` object insertion (or overlay as a floating widget positioned at the bottom)
- Alternative (simpler, more reliable): Use a QTimer to cycle through ".", "..", "..." text with SYNAPSE label, updating the last block every 500ms

**Recommended approach for typing dots**: Use the QTimer text-cycling approach for reliability in QTextBrowser. Three-phase cycle: `SYNAPSE is thinking.` -> `..` -> `...` -> `.` with 500ms interval. Styled with SIGNAL color dots and TEXT_DIM italic text.

### 4. `python/synapse/panel/chat_panel.py` — Major layout changes

**A) Replace QLineEdit with growing QTextEdit for input**:
- Swap `self._input = QtWidgets.QLineEdit(widget)` for `self._input = QtWidgets.QTextEdit(widget)`
- Set `setMinimumHeight(CHAT_INPUT_MIN_H)`, `setMaximumHeight(CHAT_INPUT_MAX_H)`
- Connect `textChanged` signal to `_adjust_input_height()` that calculates document height and resizes
- Enter sends (via event filter), Shift+Enter inserts newline
- Update `_InputEventFilter` to handle Enter/Shift+Enter and Up-arrow on QTextEdit

**B) Integrate context as chips in input area**:
- Remove `self._context_bar = ContextBar(...)` as a separate widget
- Build context chips inline: a small horizontal row of pill-shaped labels ABOVE the text input, inside the input container
- Chips: `[/obj/geo1]` (network path, SIGNAL border), `[3 nodes]` (selection, TEXT_DIM), `[F24]` (frame), `[*]` (connection LED dot only — green/red)
- Chips only appear when data is available (empty chips hidden)
- The context bar module (`context_bar.py`) becomes `ContextChips` — a QWidget with QHBoxLayout of pill labels

**C) Font size control icon**:
- Add a small "Aa" button (16x16 or 20x20) in the input area's top-right corner
- Click cycles through 4 sizes: 0.75x, 1.0x, 1.25x, 1.5x
- Store scale in `self._font_scale`, pass to formatter functions
- On change, rebuild the chat display stylesheet with scaled font sizes and re-render

**D) Layout order change** (top to bottom):
1. Mode toolbar (Chat / Create HDA) — unchanged
2. Chat display (expanding) — unchanged structurally
3. Quick actions (pill chips row — collapsible) — NEW design
4. Context chips + Input area (growing QTextEdit + send button + font icon) — MERGED
5. Connection bar — unchanged

### 5. `python/synapse/panel/context_bar.py` — Rebuild as `ContextChips`

Replace the fixed-height horizontal bar with a flow of pill chips:

```python
class ContextChips(QtWidgets.QWidget):
    """Inline context pills for the input area."""

    def __init__(self, parent=None):
        # QHBoxLayout with small spacing
        # Each chip: QLabel with rounded border, small font, GRAPHITE bg, SIGNAL text
        # LED chip: just a 10x10 colored dot
        # setVisible(False) when no data
```

- Chip style: `background: {GRAPHITE}; border: 1px solid {CARBON}; border-radius: 10px; padding: 2px 8px; font-size: {SIZE_LABEL}px; color: {SIGNAL};`
- Height: ~24px total (compact, doesn't steal space from input)
- Same public API (`set_connected`, `set_network_path`, etc.) so `chat_panel.py` wiring changes minimally

### 6. `python/synapse/panel/quick_actions.py` — Three-mode quick actions

**A) Pill chips (always visible, compact row above input)**:
- Keep existing 5 actions but render as small pill chips (not full buttons)
- Pill style: `border-radius: 14px; padding: 4px 12px; font-size: {SIZE_LABEL}px;`
- Row is collapsible — small chevron icon to expand/collapse

**B) Collapsible toolbar**:
- Add a toggle button (chevron) at the left of the pills row
- When collapsed: show only the chevron, pills hidden
- When expanded: show all pills in a wrapping flow layout
- Default: expanded

**C) Right-click context menu**:
- Add `_build_context_menu()` to `chat_panel.py`
- Triggered on right-click in the chat display area
- Same 5 actions plus: "Clear Chat", "Copy Last Response", "Toggle Quick Actions"
- Wire to `ChatDisplay.setContextMenuPolicy(Qt.CustomContextMenu)` and `customContextMenuRequested` signal

### 7. `python/synapse/panel/styles.py` — New/updated stylesheet functions

Add:
- `get_chat_bubble_user_stylesheet(font_scale)` — spacious user bubble
- `get_chat_bubble_synapse_stylesheet(font_scale)` — spacious synapse bubble
- `get_growing_input_stylesheet()` — QTextEdit version of input (replaces QLineEdit style)
- `get_context_chip_stylesheet()` — pill chip for context info
- `get_quick_action_pill_stylesheet()` — smaller pill version of action buttons
- `get_font_size_button_stylesheet()` — the "Aa" font control icon
- `get_typing_indicator_stylesheet()` — animated dots styling

Update:
- `get_chat_display_stylesheet()` — increase padding from SPACE_SM to SPACE_MD for more breathing room
- `get_section_container_stylesheet()` — add subtle top border for visual separation

## Implementation Order

1. **Tokens** — Add new chat tokens to `tokens.py`
2. **Context chips** — Rebuild `context_bar.py` as `ContextChips`
3. **Message formatter** — Update bubbles with grouping, timestamps, font scaling
4. **Chat display** — Add grouping logic, animated typing indicator
5. **Quick actions** — Add pill mode, collapsible toggle, context menu data
6. **Styles** — All new stylesheet functions
7. **Chat panel** — Wire everything together: growing input, context chips in input area, font control, context menu, new layout

## Files Modified

| File | Change Type |
|------|------------|
| `python/synapse/panel/tokens.py` | Add ~15 new tokens |
| `python/synapse/panel/context_bar.py` | Rewrite as ContextChips |
| `python/synapse/panel/message_formatter.py` | Update all 3 format functions |
| `python/synapse/panel/chat_display.py` | Add grouping + typing animation |
| `python/synapse/panel/quick_actions.py` | Add pill/collapse/context menu support |
| `python/synapse/panel/styles.py` | Add ~7 new functions, update 2 |
| `python/synapse/panel/chat_panel.py` | Major layout rewrite (input, context, font control) |

## Reuse

- All existing design tokens from `tokens.py` (colors, fonts, spacing)
- `animate_stack_transition()` in `styles.py` — unchanged
- `SynapseWSBridge`, `HdaController`, HDA views — unchanged
- `format_response()` inner logic (code blocks, node paths, lists) — preserved, just wrapped in new bubble HTML

## Verification

1. Run existing tests: `python -m pytest tests/ -v -k "panel or chat"` (if any exist)
2. Visual verification in Houdini 21:
   - Open Synapse Chat panel
   - Send a few messages — check bubble spacing, timestamps, grouping
   - Verify typing indicator animates
   - Test multi-line input (Shift+Enter), verify auto-grow
   - Check context chips update with selection changes
   - Toggle quick actions collapse
   - Right-click for context menu
   - Cycle font sizes with Aa button
   - Switch to HDA mode and back — verify no layout corruption
3. Full test suite: `python -m pytest tests/ -v` (2,141 tests — no regressions)
