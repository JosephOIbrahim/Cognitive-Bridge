# Plan: Panel Update — Bridge Integration + Gate UI (v5.8.0)

## Context

The `shared/bridge.py` consent system is now wired to `synapse.core.gates.HumanGate`, but the panel has zero UI for gate proposals, integrity display, or emergency halt. The panel version is stale at `4.0.0`. This plan adds the missing UI layer so artists can see and respond to gate proposals.

## Files Modified

| File | Change |
|------|--------|
| `python/synapse/panel/chat_panel.py` | Add gate widget, integrity bar, emergency halt button, version fix, HumanGate callback registration |
| `python/synapse/panel/gate_widget.py` | **New file** — collapsible gate proposals + integrity display widget |
| `python/synapse/panel/styles.py` | Add stylesheet functions for gate levels, integrity bar, halt button |
| `python/synapse/panel/ws_bridge.py` | Add `gate_proposal` and `session_report` signals |
| `python/synapse/ui/panel.py` | Fix version from `4.0.0` → import from `synapse.__init__` |
| `python/synapse/__init__.py` | Bump `5.7.0` → `5.8.0` |
| `VERSION` | Bump `5.7.0` → `5.8.0` |

## Implementation

### Step 1: Create `gate_widget.py` — New File

A single collapsible widget containing two sections:

**Section A: Gate Proposals** (top)
- Shows pending/recent proposals as cards
- Each card: operation name, description, agent_id, gate level badge (color-coded)
- APPROVE/CRITICAL cards have Approve/Reject buttons + countdown timer
- REVIEW cards show as logged (no buttons needed — batch reviewed later)
- INFORM cards hidden by default (too noisy)
- Uses `HumanGate.get_instance().on_proposal(callback)` to receive proposals
- Calls `gate.decide(proposal_id, decision, "panel_artist")` on button click
- Thread safety: callback emits a Qt Signal (proposals arrive from bridge thread)

**Section B: Integrity Status** (bottom)
- Single row: `●  Fidelity 1.0  |  4 ops  |  0 violations`
- Dot color: green (1.0), amber (0.5-0.99), red (<0.5)
- Clicking expands to show last operation's hash_before → hash_after → delta
- Polls `LosslessExecutionBridge.session_report()` via a QTimer (every 5s)

**Color mapping for gate level badges:**
- INFORM → `SIGNAL` (#00D4FF cyan)
- REVIEW → `WARN` (#FFAB00 amber)
- APPROVE → `FIRE` (#FF6B35 orange)
- CRITICAL → `ERROR` (#FF3D71 red) + pulsing border animation

**Class structure:**
```python
class GateWidget(QtWidgets.QWidget):
    """Collapsible gate proposals + integrity display."""
    # Signal to safely relay proposals from gate callback thread → Qt main thread
    _proposal_received = Signal(object)
    _decision_made = Signal(str, str)  # proposal_id, decision

    def __init__(self, parent=None)
    def _build_ui(self)              # chevron + proposals list + integrity row
    def _toggle(self)                # expand/collapse
    def _register_gate_callbacks(self) # HumanGate.on_proposal / on_decision
    def _on_proposal(self, proposal)   # thread-safe relay via signal
    def _add_proposal_card(self, proposal)
    def _on_approve(self, proposal_id)
    def _on_reject(self, proposal_id)
    def update_integrity(self, report: dict)  # called from timer
```

### Step 2: Add Stylesheets to `styles.py`

Add these functions at end of file:

- `get_gate_widget_stylesheet()` — container with graphite border
- `get_gate_card_stylesheet(level_color)` — proposal card with left color stripe
- `get_gate_badge_stylesheet(color)` — small badge (level name)
- `get_gate_approve_btn_stylesheet()` — green outlined button
- `get_gate_reject_btn_stylesheet()` — red outlined button
- `get_integrity_bar_stylesheet()` — single-row status with colored dot
- `get_halt_button_stylesheet()` — red outlined button for emergency halt

### Step 3: Wire into `chat_panel.py`

**In `createInterface()` after line 185 (after quick_actions, before input_container):**
```python
# 2.5. Gate proposals + integrity (collapsible)
self._gate_widget = GateWidget(self._chat_widget)
chat_layout.addWidget(self._gate_widget)
```

**In `_build_connection_bar()` before `layout.addStretch()` (line 556):**
```python
# Emergency halt button
self._halt_btn = QtWidgets.QPushButton("HALT")
self._halt_btn.setStyleSheet(get_halt_button_stylesheet())
self._halt_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
self._halt_btn.setToolTip("Emergency halt — cancel all agent operations")
self._halt_btn.clicked.connect(self._on_emergency_halt)
layout.addWidget(self._halt_btn)
```

**New method `_on_emergency_halt()`:**
```python
def _on_emergency_halt(self):
    from shared.bridge import LosslessExecutionBridge, EmergencyProtocol
    # Best-effort: get bridge instance if one exists
    self._chat.append_system_message("Emergency halt triggered.")
    if self._bridge is not None:
        self._bridge.send_command("emergency_halt", {"reason": "Artist triggered panel halt"})
```

**Integrity polling — in `createInterface()` after bridge wiring:**
```python
self._integrity_timer = QTimer(self._root)
self._integrity_timer.timeout.connect(self._poll_integrity)
self._integrity_timer.setInterval(5000)
self._integrity_timer.start()
```

**New method `_poll_integrity()`:**
- Try to import and call `LosslessExecutionBridge` session_report
- Or request via WebSocket `send_command("get_session_report", {})`
- Update `self._gate_widget.update_integrity(report)`

### Step 4: Add signals to `ws_bridge.py`

After existing signals (line 109):
```python
gate_proposal = Signal(dict)    # Gate proposal for artist decision
session_report = Signal(dict)   # Bridge integrity report
```

In `_dispatch_message()`, add before the default handler:
```python
if msg_type == "gate_proposal":
    self.gate_proposal.emit(data)
    return
if msg_type == "session_report":
    self.session_report.emit(data)
    return
```

### Step 5: Fix Version

- `python/synapse/__init__.py`: `__version__ = "5.8.0"`
- `VERSION`: `5.8.0`
- `python/synapse/ui/panel.py` line 45: replace local `__version__ = "4.0.0"` with `from synapse import __version__`

### Step 6: CRITICAL Gate Level in UI

The `GateWidget` handles CRITICAL specially:
- Red pulsing left border on card (CSS animation via QTimer toggling border color)
- "CRITICAL — Arbitrary code execution" header text
- 300s countdown displayed (vs 120s for APPROVE)
- Approve button requires double-click or shows confirmation

## What We're NOT Changing

- `python/synapse/core/gates.py` — complete as-is
- `shared/bridge.py` — already wired from previous session
- Server-side WebSocket handlers — panel uses existing `send_command` pattern
- Existing panel functionality — all changes are additive

## Verification

1. `python -m pytest tests/ -v` — full suite, no regressions
2. Panel import test: `python -c "from synapse.panel.gate_widget import GateWidget"`
3. Open panel in Houdini — verify HALT button in connection bar
4. Verify gate widget appears (collapsed) between quick actions and input
5. Trigger an APPROVE operation via MCP tool — verify proposal card appears
6. Click Approve — verify proposal.decision updates
7. Check integrity row shows fidelity 1.0 after operations
8. Version string shows 5.8.0 in panel header
