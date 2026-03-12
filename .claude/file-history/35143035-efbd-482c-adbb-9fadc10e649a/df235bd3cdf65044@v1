<p align="center">
  <img src="https://img.shields.io/badge/Version-7.1.0-blue?style=for-the-badge" alt="Version 7.1.0"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License"/>
  <img src="https://img.shields.io/badge/Tests-1047+-brightgreen?style=for-the-badge" alt="1047+ Tests"/>
  <img src="https://img.shields.io/badge/Determinism-100%25-gold?style=for-the-badge" alt="100% Determinism"/>
</p>

<h1 align="center">USD Cognitive Substrate</h1>

<p align="center">
  <strong>Deterministic AI State Management via VFX Composition Semantics</strong>
</p>

<p align="center">
  <em>Same input + Same state = Same output. Always.</em>
</p>

<p align="center">
  <a href="#the-insight">The Insight</a> •
  <a href="#key-features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#validation">Validation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#documentation">Docs</a>
</p>

---

## The Insight

> **What if the technology that manages trillion-polygon VFX scenes could manage AI cognitive state?**

Pixar's **USD (Universal Scene Description)** solves a hard problem: when hundreds of artists edit the same 3D scene, whose opinion wins? USD's answer is **LIVRPS**—a deterministic composition system that resolves conflicts the same way, every time.

We discovered this same problem exists in AI: when safety, emotion, task, and domain all "vote" on how an AI should respond, whose opinion wins?

**USD Cognitive Substrate** applies VFX composition semantics to create the first **fully deterministic cognitive architecture** for LLM applications.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│    VFX PROBLEM                          AI PROBLEM                          │
│    ───────────────────────────────────────────────────────────────────────  │
│                                                                             │
│    Multiple departments disagree        Multiple subsystems disagree        │
│    about scene data                     about AI behavior                   │
│                                                                             │
│    Model says: "sphere radius = 5"      Safety says: "stop"                 │
│    Anim says:  "sphere radius = 3"      Task says:   "continue"             │
│    Light says: "sphere radius = 4"      Mood says:   "slow down"            │
│                                                                             │
│    USD LIVRPS resolves it               USD LIVRPS resolves it              │
│    deterministically                    deterministically                   │
│                                                                             │
│                     SAME SOLUTION. DIFFERENT DOMAIN.                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Why Determinism Matters

| Without Determinism | With USD Cognitive Substrate |
|---------------------|------------------------------|
| Same prompt → different outputs | Same prompt → **identical** outputs |
| Can't reproduce bugs | Full session replay |
| Flaky behavioral tests | **100% reliable** tests |
| No audit trail | Complete decision traces |
| Learning is noisy | Verifiable adaptation |
| Safety can't be guaranteed | **Provable safety bounds** |

---

## Key Features

### Core Architecture (v5.0+)

| Feature | Description |
|---------|-------------|
| **LIVRPS Composition** | USD's conflict resolution for cognitive state |
| **7 Intervention Experts** | Validator, Scaffolder, Restorer, Refocuser, Celebrator, Socratic, Direct |
| **Mycelium Learning** | Bounded neuroplasticity with safety floors |
| **8-Phase NEXUS Pipeline** | Deterministic routing from signal to response |

### v7.0.0 Extensions

| Feature | Description | Validation |
|---------|-------------|------------|
| **Grounding Layer (L7.5)** | ACCESS over LEARN—route to oracles when ground truth exists | 730/730 (100%) |
| **BCM Stigmergic Learning** | Trail-based confidence with batch-invariance | Queued updates |
| **Plasticity Auto-Triggers** | Adaptive learning windows on crash/recovery | State-driven |
| **Knowledge Prims** | O(1) factual retrieval | 168,000× speedup |

### v7.1.0 Extensions (Cognitive Batch Invariance)

| Feature | Description | ThinkingMachines Compliance |
|---------|-------------|----------------------------|
| **Fixed Tile Size** | `COGNITIVE_TILE_SIZE=32` for all memory operations | ✅ Fixed split-size strategy |
| **Aggregation Strategies** | 5 deterministic strategies with Kahan summation | ✅ Batch-invariant accumulation |
| **Retrieval Invariance** | Same query → same results regardless of batch | ✅ Fixed reduction order |
| **Cross-Instance Refs** | supersedes, derivedFrom, contradicts, supports | Graph structure for cognition |
| **Compression Profiles** | context_injection, persistent_storage, api_transport, archive | Optimized for use case |
| **Verification Tools** | round_trip_test, determinism_test, batch_invariance_test | Formal verification |

---

## Architecture

```
                              USER INPUT
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         8-PHASE NEXUS PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐       │
│  │RETRIEVE │ → │CLASSIFY │ → │ GROUND  │ → │ DETECT  │ → │ CASCADE │       │
│  │Knowledge│   │LEARN/   │   │ Oracle  │   │ PRISM   │   │ MoE     │       │
│  │O(1)     │   │ACCESS   │   │ Query   │   │ Signals │   │ Routing │       │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘       │
│       │                                                        │            │
│       ▼                                                        ▼            │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                     │
│  │  LOCK   │ → │ EXECUTE │ → │ UPDATE  │ → │  FLUSH  │ ──→ RESPONSE        │
│  │ Params  │   │ Expert  │   │Mycelium │   │  BCM    │                     │
│  │ Fixed   │   │ Action  │   │ +Queue  │   │ Apply   │                     │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                              RESPONSE
                     (Deterministic, Reproducible)
```

### LIVRPS Cognitive Mapping

```
USD Layer          Priority    Cognitive Mapping              Example
─────────────────────────────────────────────────────────────────────────────
LOCAL              Highest     Session state + Oracle results  Current energy level
INHERITS                       Context inheritance             Parent task state
VARIANTSETS                    Mode switching                  focused/exploring
REFERENCES                     Calibration data                Learned preferences
PAYLOADS                       Domain expertise                VFX knowledge
SPECIALIZES        Lowest      Base profile                    Safety constraints
```

### Expert Hierarchy

```
Priority  Expert       Role                          Safety Floor
────────────────────────────────────────────────────────────────────
1         Validator    Safety-first, emotional       0.10 (HARD)
2         Scaffolder   Break down complexity         0.05 (HARD)
3         Restorer     Recovery facilitation         0.05 (HARD)
4         Refocuser    Attention management          0.00
5         Celebrator   Progress recognition          0.00
6         Socratic     Discovery facilitation        0.00
7         Direct       Task execution                0.00
```

---

## Validation

### Determinism Benchmarks

| Metric | Result | Method |
|--------|--------|--------|
| **Routing Determinism** | 100% | Same signal → same expert, every time |
| **Grounding Determinism** | 730/730 | Oracle queries bit-identical |
| **BCM Batch-Invariance** | 100% | Queued updates preserve determinism |
| **CogRoute-Bench** | 94.6% accuracy | 37 routing tasks, 8 categories |

### Performance

| Operation | USD Substrate | LLM Inference | Speedup |
|-----------|---------------|---------------|---------|
| Fact retrieval | 0.001ms | 150ms | **168,000×** |
| Oracle query | 15-26ms | N/A | Deterministic |
| Routing decision | 0.13ms | N/A | Deterministic |

### Formal Guarantees

```
Theorem 1 (Safety Floor Invariant)
  ∀w ∈ W, ∀update U: U(w) ∈ W
  Safety floors can NEVER be violated.

Theorem 2 (Bounded Learning)
  |U(w)_i - w_i| ≤ 0.2
  Weight updates are bounded.

Theorem 3 (BCM Batch-Invariance)
  Same inputs → Same routing
  BCM trails are metadata only.

Theorem 4 (Grounding Determinism)
  Oracle queries are bit-identical.
  Composition of deterministic functions is deterministic.
```

---

## Quick Start

### Installation

```bash
# Reference implementation
pip install cognitive-orchestra

# Or from source
git clone https://github.com/JosephOIbrahim/Orchestra.git
cd Orchestra
pip install -e ".[dev]"
```

### Basic Usage

```python
from orchestra import CognitiveEngine, Signal

# Initialize
engine = CognitiveEngine()

# Report a signal
engine.signal(Signal(
    category="emotional",
    content="frustrated",
    source="user_input"
))

# Get deterministic routing
expert = engine.route()  # Always returns same expert for same state

# Report outcome for learning
engine.outcome(expert=expert, result=0.8)
```

### Grounding Layer (v7.0.0)

```python
from orchestra import GroundingLayer, OracleRegistry

# Register an oracle
registry = OracleRegistry()
registry.register("physics", HoudiniRBDOracle())

# Query with guaranteed determinism
grounding = GroundingLayer(registry)
result = grounding.query(
    "Where is the ball at frame 48?",
    source_mode="ACCESS"  # Use oracle, not LLM
)
# result.confidence = 1.0 (oracle is authoritative)
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [**USD_COGNITIVE_SUBSTRATE.md**](USD_COGNITIVE_SUBSTRATE.md) | Complete specification (1800+ lines) |
| [**COGNITIVE_BATCH_INVARIANCE.md**](COGNITIVE_BATCH_INVARIANCE.md) | v7.1.0 batch invariance extension |
| [**DETERMINISM.md**](DETERMINISM.md) | Determinism analysis and proofs |
| [**BCM_LEARNING.md**](BCM_LEARNING.md) | BCM stigmergic learning theory |
| [**PERSISTENT_STATE_HYPOTHESIS.md**](PERSISTENT_STATE_HYPOTHESIS.md) | Theoretical foundation |
| [**RECONCILIATION.md**](RECONCILIATION.md) | Spec ↔ Implementation alignment |
| [**PRESENTATION.md**](PRESENTATION.md) | Visual slide deck |

---

## The Science

### ThinkingMachines Compliance

This architecture implements batch-invariant design principles from [He2025]:

> "The source of user-visible nondeterminism is that batch size varies with server load, and most kernels lack batch-invariance."

USD Cognitive Substrate achieves application-level determinism by:
1. **Fixed evaluation order** (8 phases, no reordering)
2. **Fixed expert priority** (Validator > ... > Direct)
3. **Queued updates** (BCM trails applied AFTER processing)
4. **Locked parameters** (no variance during generation)

### The ACCESS Paradigm

> **"LLMs don't need to LEARN physics—they need ACCESS to physics."**

When ground truth exists (physics simulation, knowledge graph, constraint solver), route to the oracle instead of asking the LLM to guess.

```
Query Type              Source Mode    Confidence
─────────────────────────────────────────────────
"Where is the ball?"    ACCESS         1.0 (oracle)
"Why did it bounce?"    HYBRID         0.9 (oracle + reasoning)
"How should I fix it?"  LEARN          0.7 (LLM only)
```

---

## Falsifiability

The thesis would be **FALSIFIED** if:

| Criterion | Threshold | Status |
|-----------|-----------|--------|
| LIVRPS produces paradoxes | >1% of configs | ✅ Not observed |
| Mycelium weights degenerate | Any occurrence | ✅ Not observed |
| Safety floors violated | Any occurrence | ✅ Proven impossible |
| Determinism fails (with TM) | >0.01% of cases | ✅ 0% failure rate |
| Simpler system works as well | Equivalent accuracy | ✅ Not demonstrated |

---

## Citation

```bibtex
@software{ibrahim2026usdcognitive,
  author       = {Ibrahim, Joseph O.},
  title        = {{USD Cognitive Substrate: A Deterministic Architecture
                   for Adaptive AI State Management}},
  version      = {7.0.0},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.18332346},
  url          = {https://github.com/JosephOIbrahim/usd-cognitive-substrate}
}
```

---

## Related Work

| Project | Relationship |
|---------|--------------|
| [**Orchestra**](https://github.com/JosephOIbrahim/Orchestra) | Reference implementation (1047+ tests) |
| [**Pixar USD**](https://graphics.pixar.com/usd/) | Composition semantics source |
| [**ThinkingMachines**](https://thinkingmachines.ai/) | Batch-invariance research |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>USD Cognitive Substrate v7.0.0</strong><br/>
  <em>Deterministic cognition, powered by VFX technology.</em>
</p>

<p align="center">
  <a href="https://doi.org/10.5281/zenodo.18332346">
    <img src="https://zenodo.org/badge/DOI/10.5281/zenodo.18332346.svg" alt="DOI"/>
  </a>
  <a href="https://orcid.org/0009-0009-2689-4966">
    <img src="https://img.shields.io/badge/ORCID-0009--0009--2689--4966-green.svg" alt="ORCID"/>
  </a>
</p>
