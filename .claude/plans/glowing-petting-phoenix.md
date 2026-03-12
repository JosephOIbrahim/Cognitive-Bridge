# Plan: Self-Starting SYNAPSE Chat Panel

## Context

The SYNAPSE Chat panel is a pure WebSocket client — it can't start the server itself. If the user opens Chat without first opening the main SYNAPSE panel and clicking Connect, the chat hangs with no connection. This forces a non-obvious two-panel workflow that shouldn't be necessary.

The fix: give the chat panel the ability to auto-start the server on activate, using the same `hou.session` persistence pattern that already exists in `connection.py`.

## Approach: Self-Starting Chat + Shared Server Discovery

Both panels follow the same 3-step check-or-create hierarchy:

1. **`hou.session._synapse_server`** — fast O(1), survives panel reloads
2. **`gc.get_objects()` sweep** — catches zombie servers from previous sessions
3. **Create + start new `SynapseServer`** — first-open case
4. **Write back to `hou.session`** — so the other panel can discover it

No new files. No new classes. Two focused edits.

## Changes

### 1. `python/synapse/panel/chat_panel.py` — Add `_ensure_server()` + wire it in

Add two module-level helpers (lazy import + gc sweep):
- `_get_server_class()` — lazily imports `SynapseServer` (not at module level)
- `_find_running_server()` — scans `gc.get_objects()` for running `SynapseServer`

Add `_ensure_server()` method to `SynapseChatPanel`:
- Step 1: Check `hou.session._synapse_server`
- Step 2: gc sweep fallback
- Step 3: Create + start + persist to `hou.session`
- On failure: coaching-tone message in chat, no crash

Call `_ensure_server()` from two places:
- `onActivateInterface()` — auto-start on panel open
- `_on_connect_toggle()` — ensure server before manual Connect click

### 2. `~/.synapse/houdini/python_panels/synapse_panel.pypanel` — Add missing `hou.session` write

The main panel starts the server but never writes it to `hou.session`. This is the gap that breaks cross-panel discovery. Two one-line additions:
- After `self._server.start()` in `_start_server()`: write `hou.session._synapse_server = self._server`
- After gc-found server in `_start_server()`: write `hou.session._synapse_server = existing`

### Files Modified

| File | Change |
|------|--------|
| `python/synapse/panel/chat_panel.py` | Add `_ensure_server()`, wire into activate + connect |
| `~/.synapse/houdini/python_panels/synapse_panel.pypanel` | Add `hou.session` write (2 lines) |

### Files Synced After

| Source | Deployed To |
|--------|-------------|
| `~/.synapse/houdini/python_panels/synapse_panel.pypanel` | `~/houdini21.0/python_panels/synapse_panel.pypanel` |
| `~/.synapse/houdini/python_panels/synapse_chat.pypanel` | `~/houdini21.0/python_panels/synapse_chat.pypanel` |

## What Happens in Each Scenario

| Scenario | Behavior |
|----------|----------|
| Open Chat only | `_ensure_server()` creates server, bridge connects |
| Open Main first, then Chat | Main starts server, Chat finds it via `hou.session` |
| Open Chat first, then Main | Chat starts server, Main finds it via gc sweep |
| Both open, Main stops server | Chat shows "Disconnected", bridge retries |
| Panel reload (Houdini) | `hou.session` persists, both panels rediscover |

## Verification

1. `python -m pytest tests/test_chat_panel.py tests/test_hda_panel.py -v` — panel tests pass
2. `python -m pytest tests/ -v` — full regression green
3. hython import check: all panel modules import cleanly
4. Manual test in Houdini: open ONLY the Chat panel, verify server auto-starts and chat connects
