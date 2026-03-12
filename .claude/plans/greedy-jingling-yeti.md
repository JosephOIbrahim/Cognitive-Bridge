# Plan: Native screenshot attach button for SYNAPSE chat

## Context
The SYNAPSE chat input now supports multi-line text (QSplitter + QPlainTextEdit), but there's no way to attach a reference screenshot for visual context. The user wants a native-feeling attach button — not a clunky file dialog, but something that fits naturally into the input row like a paperclip icon in a messaging app.

## Files
- `SYNAPSE/houdini/python_panels/synapse_panel.pypanel` — UI + send logic
- `SYNAPSE/design/synapse_styles.py` — QSS for the attach button

## Exploration Findings
- **Message format**: `_chat()` appends `{"role": "user", "content": text_string}` to `self._messages` and sends via `_FallbackClaudeWorker` to Anthropic API (`/v1/messages`). Currently text-only strings.
- **Anthropic API** already supports multi-part content: `[{"type": "text", "text": "..."}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}]` — no API version bump needed.
- **No image handling exists** in the panel today — no QFileDialog, no base64, no `<img>` rendering.
- **Clipboard is broken** in Houdini 21 PySide6 (`QApplication.instance()` returns None) — file picker is the reliable path.

## Changes

### 1. Attach button in `_build_chat_area()` (~line 487)

Add a small icon-style button **left of the input** in the bottom input row:

```
[📎] [  multi-line input area  ] [Send]
```

- `QPushButton("📎")` or unicode clip char — objectName `"attach_button"`
- Fixed size (~36x36), no text expansion — sits flush with the input height
- On click → `_on_attach_image()` opens `QFileDialog.getOpenFileName()` filtered to images (`*.png *.jpg *.jpeg *.exr *.bmp`)
- Store the selected path in `self._pending_image_path` (None when no image attached)
- Show a small preview strip below the input (thumbnail + "x" to remove) when an image is pending

### 2. Preview strip widget

- A `QWidget` holding: `QLabel` (thumbnail, 48px tall, aspect-ratio scaled) + file name label + `QPushButton("x")` to clear
- Hidden by default (`setVisible(False)`), shown when `_pending_image_path` is set
- Sits between the splitter input widget and the input row (inside the bottom splitter widget's layout)
- Clicking "x" clears `_pending_image_path` and hides the strip

### 3. `_on_send_chat()` — include image in message

- If `self._pending_image_path` is set:
  - Read the file, base64-encode it
  - Build multi-part content: `[{"type": "image", ...}, {"type": "text", "text": user_text}]`
  - Append to `self._messages` with the content list instead of a plain string
- If no image: send as before (plain text string) — zero change to existing behavior
- Clear `_pending_image_path` and hide preview strip after send

### 4. `_chat()` — render image in chat display

- When the user message includes an attached image, render a small `<img>` thumbnail in the chat bubble using a base64 data URI
- Keep it compact — max 200px wide inline preview above the text

### 5. `_FallbackClaudeWorker` — no changes needed

The worker already does `json.dumps(body)` where `body["messages"]` is the messages list. If `content` is a list of dicts instead of a string, it serializes correctly. The Anthropic API accepts both formats.

### 6. Stylesheet (`synapse_styles.py`)

Add `QPushButton#attach_button` style:
- Transparent background, SILVER icon color, no border
- Hover: CARBON bg, white icon
- Pressed: GRAPHITE bg, SIGNAL (cyan) icon
- Fixed 36x36, border-radius 8px

## Verification
- Sync to `~/.synapse/houdini/` and `~/houdini21.0/python_panels/`
- Reload panel in Houdini
- Test: click attach → file picker → select PNG → see preview → send with text → verify image appears in chat and Claude receives it
- Test: attach then click "x" to remove before sending
- Test: send text-only message still works unchanged
