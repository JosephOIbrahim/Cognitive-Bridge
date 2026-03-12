# CC↔UE5 Bridge v2.0.0

**USD Cognitive Substrate Integration with ThinkingMachines [He2025] Batch-Invariance Compliance**

A bidirectional communication bridge between Claude Code and Unreal Engine 5.7+ using USD (Universal Scene Description) composition semantics for cognitive state management.

---

## The Novel Thesis

**USD composition semantics (LIVRPS) can describe cognitive state, not just 3D scenes.**

Pixar invented USD to resolve conflicting opinions in complex 3D pipelines. We repurpose these semantics for cognitive state management in LLM-game engine integration:

| USD Concept | Cognitive Mapping |
|-------------|-------------------|
| Scene graph | Cognitive architecture |
| Prim attributes | Behavioral parameters |
| Composition arcs | Priority resolution (emotional > mode > domain > task) |
| VariantSets | State machine (sync_status, message_type) |
| Layers | Cognitive subsystems |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     USD-NATIVE BRIDGE (v2.0.0)                               │
│                                                                              │
│   ~/.translators/                                                            │
│   └── bridge_state.usda    ← Single file, bidirectional, USD VariantSets   │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CLAUDE CODE                           UNREAL ENGINE 5.7+                   │
│   ───────────                           ─────────────────                    │
│   usd_bridge.py                         BridgeComponent.cpp                  │
│   - write_question_usda()               - ProcessBridgeStateUsda()           │
│   - read_answer_usda()                  - SendAnswerUsda()                   │
│   - set_variant()                       - UpdateBehavioralSignals()          │
│   - write_finale_usda()                 - ADHD_MoE expert routing            │
│                                                                              │
│   bridge_orchestrator.py                                                     │
│   - Question sequencing                                                      │
│   - Profile generation                                                       │
│   - Checksum computation                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Fallback Mode

If USD is unavailable, the bridge falls back to JSON protocol (v1.0.0):
- `state.json` - Claude writes, UE5 reads
- `answer.json` - UE5 writes, Claude reads

---

## ThinkingMachines [He2025] Compliance

Per [Defeating Nondeterminism in LLM Inference](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/):

> "The primary reason nearly all LLM inference endpoints are nondeterministic is that the load (and thus batch-size) nondeterministically varies."

### Batch-Invariance Guarantees

| Requirement | Implementation |
|-------------|----------------|
| **Fixed reduction order** | 5-phase execution: DETECT → CASCADE → LOCK → EXECUTE → UPDATE |
| **Consistent processing** | FIXED thresholds (10000ms hesitation, 500ms rapid click) |
| **Fixed split-size** | FIXED expert priority (first match wins, no reordering) |
| **Same input → Same output** | DJB2 checksum with sorted keys |

### 5-Phase Execution Protocol

```
1. DETECT    → PRISM extracts signals (emotional, mode, domain, task)
2. CASCADE   → ADHD_MoE routes via FIXED priority
3. LOCK      → Parameters locked before generation
4. EXECUTE   → Generate response with locked params
5. UPDATE    → Update session state, compute convergence
```

### ADHD_MoE Expert Routing (FIXED Priority)

First match wins - NEVER skip or reorder:

| Priority | Expert | Triggers | Response |
|----------|--------|----------|----------|
| 1 | **Validator** | frustrated, RED burnout, rapid clicks >3 | Empathy first, normalize |
| 2 | **Scaffolder** | stuck, overwhelmed, hesitations >2 | Break down, reduce scope |
| 3 | **Restorer** | depleted, ORANGE burnout | Easy wins, rest is OK |
| 4 | **Refocuser** | distracted, tangent signals | Gentle redirect |
| 5 | **Celebrator** | completing milestone | Acknowledge win |
| 6 | **Socratic** | exploring, thoughtful pace | Guide discovery |
| 7 | **Direct** | focused, flow state | Stay out of way (DEFAULT) |

### Burnout Level Detection

| Level | Signals | Expert Route |
|-------|---------|--------------|
| GREEN | Normal pace, clear requests | Direct |
| YELLOW | Slow responses, mild hesitation | Direct + checkpoint |
| ORANGE | Frustration signals, high avg response time | Restorer |
| RED | Rapid clicking, extreme frustration | Validator |

---

## [EXEC:...] Anchor Format

Every profile includes a ThinkingMachines-compliant anchor encoding routing parameters:

```
[EXEC:{checksum}|{expert}|{paradigm}|{altitude}|{verbosity}|{think_depth}]
```

**Example:**
```
[EXEC:40d7a7a4|Scaffolder|Cortex|5000ft|standard|standard]
```

This enables:
1. **Reproducibility verification** - Same checksum = same profile
2. **Routing traceability** - Know which expert handled the response
3. **Debugging** - Full parameter state captured

---

## USD Protocol Reference

### bridge_state.usda Structure

```usda
def Xform "BridgeState" (
    variants = {
        string sync_status = "question_pending"  # State machine
        string message_type = "question"         # Message type
    }
    prepend variantSets = ["sync_status", "message_type"]
)
{
    # State machine variants
    variantSet "sync_status" = {
        "idle" { }
        "question_pending" { double timeout_seconds = 300.0 }
        "answer_received" { }
        "transition" { }
        "complete" { }
        "error" { string error_message = "" }
    }

    # Message payload
    def Xform "Message" {
        string type = "question"
        int index = 0
        int total = 8
        string question_id = "load"
        string text = "When working on a complex problem..."
    }

    # User's answer
    def Xform "Answer" {
        string question_id = ""
        int option_index = -1
        double response_time_ms = 0.0
    }

    # Behavioral signals for ADHD_MoE routing
    def Xform "BehavioralSignals" {
        double last_response_time_ms = 0.0
        int hesitation_count = 0
        int rapid_click_count = 0
        string detected_state = "focused"
        string recommended_expert = "Direct"
        string burnout_level = "GREEN"
        string momentum_phase = "rolling"
    }
}
```

### VariantSet State Machine

| sync_status | message_type | Meaning |
|-------------|--------------|---------|
| `idle` | `ready` | Bridge initialized, waiting for start |
| `question_pending` | `question` | Question displayed, waiting for answer |
| `answer_received` | `answer` | User answered, Claude processing |
| `transition` | `transition` | Scene transition in progress |
| `complete` | `finale` | All questions answered, profile ready |
| `error` | `*` | Error state with message |

---

## Quick Start

### 1. Test Without UE5

```bash
# Terminal 1: Start orchestrator
cd ue-bridge
python bridge_orchestrator.py

# Terminal 2: Simulate UE5
python test_bridge_roundtrip.py
```

### 2. UE5 Integration

1. Copy `Source/TranslatorsCard/` to your UE5.7+ project
2. Add `BridgeComponent` to an Actor in your level
3. Bind Blueprint events:
   - `OnBridgeReady` - Bridge connected
   - `OnQuestionReceived` - Display question UI
   - `OnTransitionReceived` - Handle scene transition
   - `OnFinaleReceived` - Show completion screen
4. Call `SendAcknowledgeUsda()` when ready
5. Call `SendAnswerUsda(QuestionId, OptionIndex, ResponseTimeMs)` on user selection

### 3. Python API

```python
from usd_bridge import (
    write_question_usda,
    read_answer_usda,
    set_variant,
    compute_checksum,
    generate_exec_anchor,
    get_expert_from_signals
)

# Write a question
write_question_usda(
    question_id="load",
    text="When working on a complex problem, do you prefer to...",
    options=[
        {"label": "Break it into pieces", "direction": "low"},
        {"label": "See the full picture", "direction": "high"},
        {"label": "Jump between both", "direction": "mid"}
    ],
    index=0,
    total=8
)

# Read answer (returns None if not ready)
answer = read_answer_usda()
if answer:
    print(f"Selected: {answer['option_index']}")
    print(f"Response time: {answer['response_time_ms']}ms")

# Generate deterministic checksum
checksum = compute_checksum({"load": 7, "ground": 5, "horizon": 8})
# Returns: "40d7a7a4" (always same for same input)

# Generate EXEC anchor
anchor = generate_exec_anchor(checksum, expert="Scaffolder")
# Returns: "[EXEC:40d7a7a4|Scaffolder|Cortex|Ground|standard|standard]"
```

---

## Files

### Python (Claude Code Side)

| File | Purpose |
|------|---------|
| `usd_bridge.py` | Core USD read/write functions, ThinkingMachines compliance |
| `bridge_orchestrator.py` | Question sequencing, profile generation |
| `test_bridge_roundtrip.py` | UE5 simulator for testing |

### C++ (Unreal Engine Side)

| File | Purpose |
|------|---------|
| `BridgeComponent.cpp/h` | Main bridge component with USD parsing |
| `TranslatorsCard.Build.cs` | Module build configuration |
| `UI/W_QuestionDisplay.*` | Question display widget |
| `UI/W_OptionButton.*` | Answer option button |
| `UI/W_ProgressIndicator.*` | Progress bar widget |

### USD

| File | Purpose |
|------|---------|
| `~/.translators/bridge_state.usda` | Runtime bridge state (auto-generated) |
| `USD/cognitive_substrate_template.usda` | Reference template |

---

## Checksum Algorithm

Deterministic DJB2 hash ensuring **same answers → same checksum**:

```python
def compute_checksum(dimensions: dict) -> str:
    # FIXED: Sort alphabetically for determinism
    sorted_dims = sorted(dimensions.items())

    # FIXED: Serialize format
    serialized = "TRL_v1|" + "|".join(f"{k}:{v}" for k, v in sorted_dims)

    # FIXED: DJB2 hash algorithm
    hash_val = 5381
    for char in serialized:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
        hash_val &= 0xFFFFFFFF

    return format(hash_val, '08x')
```

**Test anchor:** Input `{"load": 7, "ground": 5}` → Checksum `40d7a7a4`

---

## LIVRPS Composition Priority

USD resolves conflicts via LIVRPS (strongest to weakest):

| Priority | USD Composition | Cognitive Mapping |
|----------|-----------------|-------------------|
| 1 (highest) | **Local** | Session state (mutable) |
| 2 | **Inherits** | Inherited context |
| 3 | **VariantSets** | Mode switching |
| 4 | **References** | Calibration data |
| 5 | **Payloads** | Domain knowledge |
| 6 (lowest) | **Specializes** | Base profile (immutable) |

**Resolution rule:** Higher priority wins. Local session state overrides base profile.

---

## Critical Notes

| Issue | Solution |
|-------|----------|
| USD Stage won't auto-reload | Call `SetRootLayer("")` then `SetRootLayer(path)` |
| FDirectoryWatcher is editor-only | Use polling in packaged builds |
| File locking on Windows | Retry with 100ms delay (up to 3x) |
| pxr not installed | Falls back to text-based USDA generation |

---

## References

- **ThinkingMachines Research:** https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- **USD Specification:** https://openusd.org/release/spec.html
- **LIVRPS Composition:** https://openusd.org/release/glossary.html#livrps-strength-ordering
- **Project CLAUDE.md:** See root `CLAUDE.md` for full cognitive substrate specification

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | Jan 2026 | USD-native communication, ThinkingMachines compliance, ADHD_MoE routing |
| 1.0.0 | Jan 2026 | Initial JSON-based bridge |

---

**License:** MIT

**Author:** The Translators Project
