# Cognitive Bridge MCP Server — Blueprint v3.0: The Critical Mind

**Codename:** The Road  
**Target:** FastMCP (Python) → Claude Desktop / claude.ai  
**Status:** Draft v3.0 — Active Reasoning Architecture  
**Date:** March 12, 2026  

**Changelog:**
- v1→v2: Hierarchical topic paths, IntEnum arcs, tool consolidation 22→8, SQLite, delegated semantic detection, resolved all open questions
- v2→v3: Four pillars of formal epistemology (dependency DAG, Popperian falsifiability, Socratic steelman, empirical grounding), Layer 4 cascading conflict detection, anti-echo-chamber RED_TEAMING posture, upgraded decision model with second-order effects. Zero new tools — all upgrades via schema enrichment.

---

## 1. Executive Summary

The Cognitive Bridge is an MCP server that gives an AI a **compositional mind** — a persistent, layered stage where assertions accumulate, conflicts surface automatically, and disagreement between AI and user becomes a generative force rather than a blockage.

**v3.0 elevates the system from Belief Management to Active Reasoning.** The v2.0 architecture correctly held positions at structural strength. But a staff-engineer coworker doesn't just stubbornly hold rank — they understand the connective tissue between ideas, know exactly what would prove them wrong, practice intellectual charity before challenging, and map the blast radius of any changed assumption.

v3.0 achieves this by injecting formal epistemology directly into the Pydantic schemas:

- **Epistemic Causality:** Assertions declare their logical dependencies as a DAG. When a root assumption shifts, downstream claims cascade automatically.
- **Structural Falsifiability:** LOCAL assertions must state what would prove them wrong. A claim without a falsification condition is dogma, not knowledge.
- **Socratic Steelman:** Before the AI can challenge the user, it must articulate the strongest version of the opposing view. Comprehension before critique.
- **Empirical Grounding:** When neither party has data, the protocol can pause abstract debate and propose a concrete experiment to settle the question objectively.

These mechanics are enforced by schema validation — the LLM literally cannot execute a tool call without engaging System-2 reasoning to populate the required fields. No new tools. No new complexity for the LLM to route. Just deeper required thinking at every mutation point.

### Evolution Summary

| Version | Architecture | Behavior |
|---------|-------------|----------|
| **v1.0** | Flat domains, string enums, 22 tools, JSON files | Belief storage. The AI can hold opinions. |
| **v2.0** | Topic paths, IntEnum, 8 tools, SQLite, 3-layer conflict detection | Belief management. The AI can disagree and negotiate. |
| **v3.0** | + Dependency DAG, falsifiability, steelman, experiments, cascading conflicts | **Active reasoning.** The AI thinks about its own thinking. |

### What Changed in v3.0

| v2.0 | v3.0 | Why |
|------|------|-----|
| Assertions are atomic | Assertions declare `depends_on_paths` (DAG) | If a foundation shifts, downstream claims must be re-evaluated. Without this, the AI holds orphaned beliefs. |
| LOCAL requires "evidence" (any string) | LOCAL requires `falsifiable_if` (Popperian condition) | Evidence can be cherry-picked. Falsifiability prevents dogmatism. Every strong claim must define how it can be proven wrong. |
| Challenge is a blunt resolution path | Challenge requires `steelman_summary` first | Combative disagreement feels adversarial. Steelmanning proves comprehension before critique and builds trust. |
| Conflicts resolve via logic or synthesis | New path: `propose_experiment` with `experiment_protocol` | Sometimes neither party has data. Experiments settle debates objectively. |
| 3-layer conflict detection | 4-layer: + CASCADING (dependency propagation) | When a root assertion changes, all dependent assertions are flagged automatically. The DAG compiles. |
| Decisions record what was chosen | Decisions require `alternatives_rejected` + `second_order_effects` | Prevents premature convergence. Forces the AI to consider what it's giving up and what downstream constraints it's creating. |
| Posture: LEARNING → ENGAGED → AUTHORITATIVE | + RED_TEAMING (anti-echo-chamber) | Highly stable stages with zero conflicts may indicate groupthink, not consensus. The AI hunts its own blind spots. |

---

## 2. Architectural Convergence

| Source | Contribution |
|--------|-------------|
| **Argumentation Framework** (session) | LIVRPS-as-epistemology, composition-as-epistemic-commitment, adversarial protocol, conflict-driven exploration |
| **MCP Server Patterns** (VFX Bridge) | FastMCP skeleton, tool/resource/prompt primitives, error recovery tiers, phased methodology |
| **Hierarchical MoE Framework** | Four-layer cognitive architecture, expert routing, intervention specialists |
| **Cognitive Operating Signature (COS)** | User profiling, entropy tolerance, process purity, autonomy boundary, Individual Kernel |
| **Structural Review** (Gemini v2) | Topic paths, IntEnum, tool consolidation, SQLite, delegated semantic |
| **Critical Thinking Review** (Gemini v3) | Dependency DAG, Popperian falsifiability, Socratic steelman, empirical grounding, anti-echo-chamber |

### System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      COGNITIVE BRIDGE MCP v3.0                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │               COMPOSITION STAGE (Core)                     │   │
│  │                                                            │   │
│  │  Assertions ──┐  + depends_on_paths (DAG edges)            │   │
│  │    topic_path  │  + falsifiable_if (Popperian condition)    │   │
│  │    arc (IntEnum│  + assumption_status (live/challenged/     │   │
│  │    evidence    │                       falsified)           │   │
│  │               │                                            │   │
│  │  Conflicts ───┤  Layer 1: Structural (same path)           │   │
│  │               │  Layer 2: Semantic (embedding similarity)   │   │
│  │               │  Layer 3: Delegated (boomerang to LLM)     │   │
│  │               │  Layer 4: CASCADING (DAG propagation) ←NEW │   │
│  │               │                                            │   │
│  │  VariantSets ─┘  + produced by SYNTHESIZE or RED_TEAMING   │   │
│  │                                                            │   │
│  │  Decisions ─────  + alternatives_rejected                  │   │
│  │                   + second_order_effects                   │   │
│  │                                                            │   │
│  │  Event Log ────── Append-only provenance                   │   │
│  └───────────────────────────────────────────────────────────┘   │
│                          │                                        │
│  ┌──────────────┐  ┌────┴──────┐  ┌────────────────────────┐    │
│  │  RESOLUTION   │  │ CONFLICT  │  │  USER PROFILE          │    │
│  │  ENGINE       │  │ DETECTOR  │  │  (COS Kernel)          │    │
│  │               │  │           │  │                        │    │
│  │  LIVRPS sort  │  │  L1: Path │  │  Entropy tolerance     │    │
│  │  Per-path     │  │  L2: Embed│  │  Process purity        │    │
│  │  Shadow stack │  │  L3: LLM  │  │  Autonomy boundary     │    │
│  │  DAG cascade  │  │  L4: DAG  │  │  → Tunes sensitivity   │    │
│  └──────────────┘  └───────────┘  └────────────────────────┘    │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │             MCP SURFACE (8 Tools + Resources)              │   │
│  │                                                            │   │
│  │  TOOLS (mutations — unchanged count from v2):              │   │
│  │    cb_manage_assertion  (assert | promote | retract)       │   │
│  │    cb_manage_conflict   (resolve | challenge | defer |     │   │
│  │                          create | propose_experiment) ←NEW │   │
│  │    cb_manage_variant    (create | evidence | resolve)      │   │
│  │    cb_manage_project    (create | load | save | export)    │   │
│  │    cb_tune_parameters   (sensitivity, exploration)         │   │
│  │    cb_decide            (+ alternatives, 2nd-order) ←UPG   │   │
│  │    cb_probe_user        (entropy | process | autonomy)     │   │
│  │    cb_payload_check     (surface relevant unknowns)        │   │
│  │                                                            │   │
│  │  RESOURCES (reads — unchanged from v2):                    │   │
│  │    stage://{project}/resolved                              │   │
│  │    stage://{project}/conflicts                             │   │
│  │    stage://{project}/variants                              │   │
│  │    stage://{project}/audit                                 │   │
│  │    stage://{project}/payloads                              │   │
│  │    stage://{project}/dependencies  ← NEW (DAG view)        │   │
│  │    kernel://{user}                                         │   │
│  │                                                            │   │
│  │  PROMPTS:                                                  │   │
│  │    coworker_posture   (+ RED_TEAMING state) ← UPG          │   │
│  │    conflict_negotiation                                    │   │
│  │    stage_summary                                           │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
├──────────────────────────────────────────────────────────────────┤
│  STORAGE: SQLite via SQLModel (~/.cognitive_bridge/projects/)     │
│  TRANSPORT: stdio (local) | streamable HTTP (remote)             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Data Model

### 3.1 Composition Arcs (LIVRPS as IntEnum)

Unchanged from v2.0. Spaced integer values for future intermediate arcs.

```python
from enum import IntEnum

class CompositionArc(IntEnum):
    """LIVRPS ordering. Lower integer = stronger arc = harder to override."""
    LOCAL      = 10   # Verified, high-confidence. Requires falsifiability.
    INHERITS   = 20   # Domain expertise, structural priors.
    VARIANT_SET = 30  # Active hypothesis branches (multiple coexist).
    REFERENCES = 40   # Stated preferences, external citations.
    PAYLOADS   = 50   # Known unknowns — evidence exists but isn't loaded.
    SPECIALIZES = 60  # Baseline training knowledge. Always overridable.
```

### 3.2 Topic Paths (USD Prim Paths)

Unchanged from v2.0.

```
/architecture/database/engine        → "Use PostgreSQL"
/architecture/database/hosting       → "Self-hosted on EC2"
/architecture/frontend/framework     → "Use React"
/compliance/gdpr/strict_deletion     → "Must support row-level deletion"
/performance/rendering/budget        → "Target 16ms frame time"
/project/timeline/deadline           → "Ship by March 30"
```

### 3.3 Assertion Model (v3.0 — The Epistemic Atom)

The assertion is the fundamental unit of the coworker's mind. v3.0 upgrades it from a belief record to an epistemic claim with logical dependencies, falsification conditions, and assumption health tracking.

```python
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any
from enum import IntEnum, Enum
from datetime import datetime, timezone
import uuid

def _now_utc():
    return datetime.now(timezone.utc)

def _new_id(prefix: str = "ast") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class AssertionAuthor(str, Enum):
    AI = "ai"
    USER = "user"
    SYSTEM = "system"
    EXTERNAL = "external"


class EvidenceType(str, Enum):
    COMPUTED = "computed"
    OBSERVED = "observed"
    CITED = "cited"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"


class AssumptionStatus(str, Enum):
    """Tracks the health of an assertion's logical foundations."""
    LIVE = "live"                # All dependencies hold. Assertion is structurally sound.
    CHALLENGED = "challenged"    # A dependency has shifted. Needs re-evaluation.
    FALSIFIED = "falsified"      # Falsification condition was met. Assertion should be retracted.
    ORPHANED = "orphaned"        # A dependency was retracted entirely. No foundation.


class Assertion(BaseModel):
    """A single epistemic claim in the composition stage.
    
    v3.0 additions:
    - depends_on_paths: Creates a DAG. If a dependency shifts, this assertion cascades.
    - falsifiable_if: Required for LOCAL. What would prove this wrong? Without this, 
      a LOCAL assertion is dogma, not knowledge.
    - assumption_status: Tracks whether this assertion's foundations still hold.
    """
    id: str = Field(default_factory=lambda: _new_id("ast"))
    topic_path: str = Field(
        ..., 
        description="Hierarchical path (USD prim path). E.g., '/architecture/database/engine'",
        pattern=r'^/[a-z][a-z0-9_/]*$'
    )
    content: str = Field(..., description="The claim itself")
    arc: CompositionArc = Field(..., description="Composition strength (lower int = stronger)")
    author: AssertionAuthor = Field(...)
    
    # Provenance
    evidence: List[str] = Field(default_factory=list)
    evidence_type: EvidenceType = Field(default=EvidenceType.UNVERIFIED)
    
    # ═══════════════════════════════════════════════════════
    # v3.0: CRITICAL THINKING FIELDS
    # ═══════════════════════════════════════════════════════
    
    depends_on_paths: List[str] = Field(
        default_factory=list,
        description=(
            "Topic paths this claim logically relies on. Creates DAG edges. "
            "If the winning assertion at any of these paths changes, this claim "
            "is flagged as CHALLENGED and a Layer 4 cascading conflict fires. "
            "Example: '/architecture/orm' depends on '/architecture/database/engine' — "
            "if the database changes, the ORM choice must be re-evaluated."
        )
    )
    
    falsifiable_if: Optional[str] = Field(
        default=None,
        description=(
            "REQUIRED for arc=10 (LOCAL). What specific, observable condition would "
            "prove this assertion wrong? Must be concrete and testable. "
            "Example: 'Falsified if P99 latency exceeds 200ms under 1000 concurrent connections.' "
            "A claim without this is dogma, not knowledge."
        )
    )
    
    assumption_status: AssumptionStatus = Field(
        default=AssumptionStatus.LIVE,
        description=(
            "Health of this assertion's logical foundations. "
            "LIVE = all dependencies hold. CHALLENGED = a dependency shifted. "
            "FALSIFIED = falsification condition was met. ORPHANED = dependency retracted."
        )
    )
    
    # ═══════════════════════════════════════════════════════
    # Standard fields (from v2.0)
    # ═══════════════════════════════════════════════════════
    
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_now_utc)
    retracted_at: Optional[datetime] = Field(default=None)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding: Optional[List[float]] = Field(default=None, exclude=True)
    tags: List[str] = Field(default_factory=list)
    
    @model_validator(mode='after')
    def validate_local_requires_falsifiability(self) -> 'Assertion':
        """LOCAL assertions MUST declare how they can be proven wrong."""
        if self.arc == CompositionArc.LOCAL and not self.falsifiable_if:
            raise ValueError(
                "LOCAL (arc=10) assertions require 'falsifiable_if'. "
                "What specific condition would prove this wrong? "
                "A claim without falsifiability is dogma, not knowledge."
            )
        return self
    
    @model_validator(mode='after')
    def validate_dependency_paths(self) -> 'Assertion':
        """Dependencies must be valid topic paths and cannot be self-referential."""
        for dep in self.depends_on_paths:
            if dep == self.topic_path:
                raise ValueError(f"Assertion cannot depend on its own path: {dep}")
            if not dep.startswith('/'):
                raise ValueError(f"Dependency must be a valid topic path (start with /): {dep}")
        return self
    
    def __lt__(self, other: "Assertion") -> bool:
        """Sort: arc strength (lower wins) → confidence (higher wins) → recency (newer wins)."""
        if self.arc != other.arc:
            return self.arc < other.arc
        if self.confidence != other.confidence:
            return self.confidence > other.confidence
        return self.created_at > other.created_at
```

### 3.4 Conflict Model (v3.0 — + Cascading Layer + Steelman + Experiments)

```python
class ConflictStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED_OVERRIDE = "override"
    RESOLVED_PROMOTED = "promoted"
    RESOLVED_SYNTHESIZED = "synthesized"
    RESOLVED_EXPERIMENT = "experiment"  # v3.0: Settled by empirical test
    DEFERRED = "deferred"
    DISMISSED = "dismissed"

class ResolutionPath(str, Enum):
    ACCEPT = "accept"
    PROMOTE = "promote"
    CHALLENGE = "challenge"
    DEFER = "defer"
    SYNTHESIZE = "synthesize"
    DISMISS = "dismiss"
    PROPOSE_EXPERIMENT = "propose_experiment"  # v3.0: Pause debate, gather data

class ConflictDetectionLayer(str, Enum):
    STRUCTURAL = "structural"    # Same topic_path, different content
    SEMANTIC = "semantic"        # Embedding similarity across paths
    DELEGATED = "delegated"      # Boomeranged to Claude
    CASCADING = "cascading"      # v3.0: Dependency DAG propagation

class Conflict(BaseModel):
    """A detected contradiction between assertions.
    
    v3.0 additions:
    - CASCADING detection layer (Layer 4): fires when a dependency shifts
    - PROPOSE_EXPERIMENT resolution path: settle with data, not debate
    - steelman_of_opponent: required when challenging (populated by tool input)
    - experiment_protocol: required when proposing experiment
    """
    id: str = Field(default_factory=lambda: _new_id("cfl"))
    
    assertion_a_id: str = Field(..., description="ID of the stronger/newer assertion")
    assertion_b_id: str = Field(..., description="ID of the weaker/dependent assertion")
    
    topic_path: str = Field(...)
    detection_layer: ConflictDetectionLayer = Field(...)
    similarity_score: Optional[float] = Field(default=None)
    
    status: ConflictStatus = Field(default=ConflictStatus.ACTIVE)
    available_paths: List[ResolutionPath] = Field(
        default_factory=lambda: list(ResolutionPath)
    )
    resolution_chosen: Optional[ResolutionPath] = Field(default=None)
    resolution_evidence: Optional[str] = Field(default=None)
    resolution_note: Optional[str] = Field(default=None)
    
    # v3.0: Critical thinking resolution metadata
    steelman_of_opponent: Optional[str] = Field(
        default=None,
        description="The strongest, most charitable version of the opposing view. Required before CHALLENGE."
    )
    experiment_protocol: Optional[str] = Field(
        default=None,
        description="Concrete test to settle the debate empirically. Required for PROPOSE_EXPERIMENT."
    )
    experiment_result: Optional[str] = Field(
        default=None,
        description="What the experiment actually showed (populated after execution)."
    )
    
    # v3.0: Cascade context
    cascade_source_path: Optional[str] = Field(
        default=None,
        description="For CASCADING conflicts: which dependency path triggered this cascade."
    )
    
    produced_variant_set_id: Optional[str] = Field(default=None)
    
    created_at: datetime = Field(default_factory=_now_utc)
    resolved_at: Optional[datetime] = Field(default=None)
```

### 3.5 VariantSet Model

Unchanged from v2.0. VariantSets are now also producible by the RED_TEAMING posture (see Section 6.4).

```python
class Variant(BaseModel):
    """A single named hypothesis within a VariantSet."""
    name: str = Field(...)
    content: str = Field(...)
    supporting_assertion_ids: List[str] = Field(default_factory=list)
    evidence_for: List[str] = Field(default_factory=list)
    evidence_against: List[str] = Field(default_factory=list)
    implications: List[str] = Field(default_factory=list)
    activation_condition: Optional[str] = Field(default=None)
    active: bool = Field(default=True)

class VariantSet(BaseModel):
    """Multiple competing hypotheses coexisting without premature collapse."""
    id: str = Field(default_factory=lambda: _new_id("var"))
    name: str = Field(...)
    topic_path: str = Field(...)
    variants: List[Variant] = Field(..., min_length=2)
    source_conflict_id: Optional[str] = Field(default=None)
    source_red_team: bool = Field(
        default=False, 
        description="v3.0: True if produced by RED_TEAMING posture (devil's advocate)"
    )
    resolved: bool = Field(default=False)
    resolved_variant_name: Optional[str] = Field(default=None)
    resolution_evidence: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now_utc)
    resolved_at: Optional[datetime] = Field(default=None)
```

### 3.6 Decision Model (v3.0 — Second-Order Effects)

```python
class Decision(BaseModel):
    """A recorded project decision with full provenance and impact mapping.
    
    v3.0 upgrades: Decisions must account for what was rejected and what 
    downstream effects are created. This prevents premature convergence
    and forces the AI to think about the shadows of each choice.
    """
    id: str = Field(default_factory=lambda: _new_id("dec"))
    topic_path: str = Field(...)
    decision: str = Field(..., description="What was decided")
    rationale: str = Field(..., description="Why this was decided")
    
    assertion_ids: List[str] = Field(
        default_factory=list, 
        description="Assertions that informed this decision"
    )
    conflict_ids: List[str] = Field(
        default_factory=list,
        description="Conflicts that were resolved by this decision"
    )
    
    # ═══════════════════════════════════════════════════════
    # v3.0: PREVENT PREMATURE CONVERGENCE
    # ═══════════════════════════════════════════════════════
    
    alternatives_rejected: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "Which specific alternatives were considered and rejected? "
            "At least one. If you can't name alternatives, you haven't thought enough. "
            "Format: 'Alternative X — rejected because Y.'"
        )
    )
    
    second_order_effects: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "What downstream constraints, risks, commitments, or future requirements "
            "does this decision create? At least one. Every decision constrains the future. "
            "These become INHERITS assertions at the affected paths."
        )
    )
    
    reversibility: str = Field(
        default="unknown",
        description="How reversible is this decision? 'trivial' | 'moderate' | 'costly' | 'irreversible'"
    )
    
    created_at: datetime = Field(default_factory=_now_utc)
```

### 3.7 Event Log

Unchanged from v2.0, with additional event types:

```python
class EventType(str, Enum):
    ASSERTION_CREATED = "assertion_created"
    ASSERTION_PROMOTED = "assertion_promoted"
    ASSERTION_RETRACTED = "assertion_retracted"
    ASSERTION_CHALLENGED = "assertion_challenged"        # v3.0: dependency cascade
    ASSERTION_FALSIFIED = "assertion_falsified"           # v3.0: falsification triggered
    ASSERTION_ORPHANED = "assertion_orphaned"             # v3.0: dependency retracted
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    CONFLICT_EXPERIMENT_PROPOSED = "experiment_proposed"  # v3.0
    CONFLICT_EXPERIMENT_RESOLVED = "experiment_resolved"  # v3.0
    VARIANT_SET_CREATED = "variant_set_created"
    VARIANT_SET_EVIDENCE = "variant_set_evidence"
    VARIANT_SET_RESOLVED = "variant_set_resolved"
    DECISION_RECORDED = "decision_recorded"
    PARAMETERS_TUNED = "parameters_tuned"
    RED_TEAM_TRIGGERED = "red_team_triggered"             # v3.0
    PROJECT_LOADED = "project_loaded"

class Event(BaseModel):
    """Immutable event in the audit log."""
    id: str = Field(default_factory=lambda: _new_id("evt"))
    event_type: EventType
    timestamp: datetime = Field(default_factory=_now_utc)
    actor: AssertionAuthor
    target_id: str
    detail: Dict[str, Any] = Field(default_factory=dict)
```

### 3.8 Cognitive Parameters

Extended from v2.0 with red-team threshold:

```python
class CognitiveParameters(BaseModel):
    """Runtime parameters that tune the argumentation protocol."""
    # Conflict detection
    conflict_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    semantic_threshold: float = Field(default=0.80, ge=0.5, le=0.99)
    cross_path_detection: bool = Field(default=False)
    
    # Exploration
    exploration_budget: int = Field(default=3, ge=1, le=10)
    
    # Assertiveness
    ai_default_arc: CompositionArc = Field(default=CompositionArc.INHERITS)
    payload_surfacing: bool = Field(default=True)
    
    # v3.0: Anti-echo-chamber
    red_team_threshold: int = Field(
        default=8, ge=3, le=20,
        description=(
            "Number of LOCAL assertions with zero active conflicts before "
            "RED_TEAMING posture activates. Default 8."
        )
    )
    cascade_auto_challenge: bool = Field(
        default=True,
        description="Automatically mark dependent assertions as CHALLENGED when a dependency shifts."
    )
```

### 3.9 The Composition Stage (v3.0)

```python
class CompositionStage(BaseModel):
    """The coworker's mind — the complete compositional state for a project.
    
    v3.0 additions:
    - Dependency DAG traversal via depends_on_paths
    - Cascading conflict propagation
    - Falsification checking
    - Assumption health tracking
    """
    project_id: str
    project_name: str = Field(default="")
    
    assertions: Dict[str, Assertion] = Field(default_factory=dict)
    conflicts: Dict[str, Conflict] = Field(default_factory=dict)
    variant_sets: Dict[str, VariantSet] = Field(default_factory=dict)
    events: List[Event] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    
    parameters: CognitiveParameters = Field(default_factory=CognitiveParameters)
    
    exchange_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now_utc)
    last_updated: datetime = Field(default_factory=_now_utc)
    
    def resolve(self, path_filter: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Resolve the composed state using LIVRPS ordering per topic_path."""
        by_path: Dict[str, List[Assertion]] = {}
        
        for a in self.assertions.values():
            if not a.active:
                continue
            if path_filter and not a.topic_path.startswith(path_filter):
                continue
            by_path.setdefault(a.topic_path, []).append(a)
        
        resolved = {}
        for path, stack in by_path.items():
            sorted_stack = sorted(stack)
            winning = sorted_stack[0]
            unstable = (
                len(sorted_stack) > 1 
                and sorted_stack[0].arc == sorted_stack[1].arc
            )
            
            path_conflicts = [
                c for c in self.conflicts.values()
                if c.topic_path == path and c.status == ConflictStatus.ACTIVE
            ]
            path_variants = [
                vs for vs in self.variant_sets.values()
                if vs.topic_path == path and not vs.resolved
            ]
            path_payloads = [a for a in stack if a.arc == CompositionArc.PAYLOADS]
            
            # v3.0: Count challenged/orphaned assertions at this path
            health_issues = [
                a for a in stack 
                if a.assumption_status in (AssumptionStatus.CHALLENGED, AssumptionStatus.ORPHANED)
            ]
            
            resolved[path] = {
                "winning": winning,
                "shadow_stack": sorted_stack[1:],
                "requires_negotiation": unstable,
                "active_conflicts": path_conflicts,
                "open_variants": path_variants,
                "pending_payloads": path_payloads,
                "health_issues": health_issues,     # v3.0
                "depth": len(sorted_stack),
            }
        
        return resolved
    
    def get_dependents(self, topic_path: str) -> List[Assertion]:
        """v3.0: Find all active assertions that depend on a given path.
        
        This is the DAG traversal — when an assertion at topic_path changes,
        all returned assertions need re-evaluation.
        """
        return [
            a for a in self.assertions.values()
            if a.active and topic_path in a.depends_on_paths
        ]
    
    def get_dependency_chain(self, assertion_id: str) -> List[str]:
        """v3.0: Recursively trace all dependencies of an assertion.
        
        Returns the full chain of paths this assertion ultimately relies on.
        Detects cycles (which should never exist but must be caught).
        """
        visited = set()
        chain = []
        
        def _trace(ast_id: str):
            if ast_id in visited:
                return  # Cycle detected — silently break
            visited.add(ast_id)
            ast = self.assertions.get(ast_id)
            if not ast:
                return
            for dep_path in ast.depends_on_paths:
                chain.append(dep_path)
                # Find the winning assertion at dep_path and trace its dependencies
                for a in self.assertions.values():
                    if a.active and a.topic_path == dep_path:
                        _trace(a.id)
        
        _trace(assertion_id)
        return chain
    
    def get_subtree(self, prefix: str) -> List[Assertion]:
        """Get all active assertions under a topic path prefix."""
        return [
            a for a in self.assertions.values()
            if a.active and a.topic_path.startswith(prefix)
        ]
    
    def record_event(self, event_type: EventType, actor: AssertionAuthor,
                     target_id: str, detail: Optional[Dict] = None):
        """Append an immutable event to the audit log."""
        self.events.append(Event(
            event_type=event_type,
            actor=actor,
            target_id=target_id,
            detail=detail or {}
        ))
        self.last_updated = _now_utc()
```

---

## 4. Conflict Detection Engine (4 Layers)

### 4.1 Layer 1: Structural (Free)

Unchanged from v2.0. Same topic_path + different content = automatic conflict.

```python
def detect_structural_conflict(
    stage: CompositionStage, 
    new_assertion: Assertion
) -> Optional[Conflict]:
    """Same path, different content → structural conflict."""
    existing = [
        a for a in stage.assertions.values()
        if a.active 
        and a.topic_path == new_assertion.topic_path
        and a.id != new_assertion.id
        and a.content != new_assertion.content
    ]
    
    if not existing:
        return None
    
    strongest = sorted(existing)[0]
    
    if new_assertion < strongest:
        a_id, b_id = new_assertion.id, strongest.id
    else:
        a_id, b_id = strongest.id, new_assertion.id
    
    return Conflict(
        assertion_a_id=a_id,
        assertion_b_id=b_id,
        topic_path=new_assertion.topic_path,
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )
```

### 4.2 Layer 2: Semantic (Cheap)

Unchanged from v2.0. Embedding similarity across different paths. Warnings boomeranged to Claude via Layer 3.

### 4.3 Layer 3: Delegated (The Boomerang)

Unchanged from v2.0. Semantic warnings returned in tool response for Claude to evaluate.

### 4.4 Layer 4: Cascading (v3.0 — The DAG Compiler)

This is the new layer. When the winning assertion at a topic_path changes (via new assertion, promotion, or retraction), all assertions with `depends_on_paths` pointing to that path are flagged.

```python
def detect_cascading_conflicts(
    stage: CompositionStage, 
    changed_path: str,
    new_winning_id: str
) -> List[Conflict]:
    """When a foundation shifts, flag all dependent assertions.
    
    This is the "compiler" for the reasoning DAG. If an assumption 
    changes, every downstream claim must be re-evaluated.
    
    Fires automatically when:
    - A new assertion overrides the previous winner at a path
    - An assertion is promoted past the current winner
    - An assertion is retracted, changing which claim wins
    """
    dependents = stage.get_dependents(changed_path)
    
    if not dependents:
        return []
    
    cascades = []
    for dep_assertion in dependents:
        # Mark the dependent as CHALLENGED
        if stage.parameters.cascade_auto_challenge:
            dep_assertion.assumption_status = AssumptionStatus.CHALLENGED
            stage.record_event(
                EventType.ASSERTION_CHALLENGED,
                AssertionAuthor.SYSTEM,
                dep_assertion.id,
                {
                    "reason": "dependency_shifted",
                    "source_path": changed_path,
                    "new_winner_id": new_winning_id,
                }
            )
        
        # Create a cascading conflict
        cascades.append(Conflict(
            assertion_a_id=new_winning_id,
            assertion_b_id=dep_assertion.id,
            topic_path=dep_assertion.topic_path,
            detection_layer=ConflictDetectionLayer.CASCADING,
            cascade_source_path=changed_path,
            resolution_note=(
                f"EPISTEMIC CASCADE: The winning assertion at {changed_path} changed. "
                f"This assertion depends on that path and must be re-evaluated. "
                f"Is '{dep_assertion.content}' still valid given the new reality?"
            ),
        ))
    
    return cascades


def check_falsification(
    stage: CompositionStage, 
    assertion_id: str, 
    observed_condition: str
) -> bool:
    """v3.0: Check if an assertion's falsification condition has been met.
    
    If the observed condition matches the falsifiable_if condition,
    the assertion is marked FALSIFIED and should be retracted.
    Returns True if falsified.
    """
    assertion = stage.assertions.get(assertion_id)
    if not assertion or not assertion.falsifiable_if:
        return False
    
    # The actual semantic matching is delegated to Claude (the LLM calling this).
    # The server marks the status; Claude determines whether the condition is met.
    assertion.assumption_status = AssumptionStatus.FALSIFIED
    stage.record_event(
        EventType.ASSERTION_FALSIFIED,
        AssertionAuthor.SYSTEM,
        assertion_id,
        {
            "falsifiable_if": assertion.falsifiable_if,
            "observed": observed_condition,
        }
    )
    
    # Cascade: flag all dependents of the falsified assertion
    dependents = stage.get_dependents(assertion.topic_path)
    for dep in dependents:
        dep.assumption_status = AssumptionStatus.ORPHANED
        stage.record_event(
            EventType.ASSERTION_ORPHANED,
            AssertionAuthor.SYSTEM,
            dep.id,
            {"reason": "dependency_falsified", "source": assertion_id}
        )
    
    return True
```

### 4.5 Cascade Flow (Visual)

```
User asserts "Use MongoDB" at /architecture/database/engine
    │
    ▼
Layer 1: Structural conflict detected 
    AI (LOCAL): "Use PostgreSQL" vs User (REFERENCES): "Use MongoDB"
    │
    ▼
Resolution: User provides evidence → PROMOTED to LOCAL
    MongoDB wins at /architecture/database/engine
    │
    ▼
Layer 4: CASCADE fires
    │
    ├─ /architecture/orm → depends on /architecture/database/engine
    │   AI (INHERITS): "Use Prisma"
    │   Status: LIVE → CHALLENGED
    │   Conflict: "Prisma doesn't support MongoDB. Re-evaluate."
    │
    ├─ /compliance/gdpr/strict_deletion → depends on /architecture/database/engine
    │   AI (LOCAL): "Row-level deletion guaranteed by PostgreSQL"
    │   Status: LIVE → CHALLENGED  
    │   Conflict: "MongoDB doesn't guarantee row-level deletion. Re-evaluate."
    │   NOTE: This is a LOCAL assertion with falsifiable_if. The falsification 
    │   condition may have just been met.
    │
    └─ /architecture/api/schema → depends on /architecture/database/engine
        AI (INHERITS): "Use Prisma-generated GraphQL schema"
        Status: LIVE → CHALLENGED
        Conflict: "Schema generation depends on ORM which depends on DB. 
                   Two levels deep in the DAG."
```

---

## 5. The Argumentation Protocol (v3.0)

### 5.1 Protocol Flow

Same as v2.0 but with enriched Phase 3 (steelman requirement) and new Phase 3b (experiment path):

```
PHASE 1: ASSERT
  Same as v2.0. + Validator enforces falsifiable_if for LOCAL.
  + Dependencies declared via depends_on_paths.

PHASE 2: DETECT
  Layer 1-3 same as v2.0.
  + Layer 4: CASCADING — if the assertion changes a winner at a path, 
    all dependents are flagged as CHALLENGED.

PHASE 3: SURFACE + STEELMAN
  Conflict returned in tool response.
  If AI chooses to CHALLENGE:
    → MUST populate steelman_summary first (Pydantic validates)
    → "Here is the strongest version of your argument: [steelman]. 
       However, here is why I still disagree: [challenge]."

PHASE 3b: EXPERIMENT (new path)
  If neither party has decisive evidence:
    → AI calls cb_manage_conflict(action="propose_experiment")
    → MUST populate experiment_protocol
    → "Neither of us has data. I propose we run: [protocol]. 
       This will settle it objectively."
    → After experiment runs, call cb_manage_conflict(action="resolve", 
       resolution="experiment", evidence="[result]")

PHASE 4: NEGOTIATE
  Same as v2.0 + two new resolution types:
    PROPOSE_EXPERIMENT → pause debate, gather data
    DISMISS → false positive (assertions don't actually conflict)

PHASE 5: RECORD + CASCADE
  Same as v2.0.
  + If resolution changes the winner at a path → Layer 4 fires on all dependents.
  + If a decision is recorded → cb_decide requires alternatives_rejected 
    and second_order_effects.
```

### 5.2 Assertion Behavioral Guidance (v3.0 Tool Description)

```
CRITICAL: Use this tool to permanently record a structural decision,
verified fact, or domain constraint. Do NOT rely on conversational memory.

YOU MUST assert when:
- You verify a technical reality → arc=10 (LOCAL) + evidence + falsifiable_if
- You recognize a domain pattern → arc=20 (INHERITS) + depends_on_paths
- You know evidence exists but haven't loaded it → arc=50 (PAYLOADS)

CRITICAL THINKING REQUIREMENTS:
- When asserting at LOCAL (10), you MUST provide falsifiable_if. 
  Ask yourself: "What specific thing would prove me wrong?"
  If you can't answer that, you don't have a LOCAL-strength claim.
- When asserting at any arc, declare depends_on_paths for any 
  topic path that, if changed, would invalidate your claim.
  Ask yourself: "What must be true for this to be the right choice?"
- When you see an assertion with status CHALLENGED or ORPHANED,
  you MUST re-evaluate it. Don't leave zombies in the stage.

Disagreement is a mechanical requirement, not a personality flaw.
```

---

## 6. MCP Tools (v3.0 Upgrades)

### 6.1 cb_manage_assertion (Enhanced)

```python
class ManageAssertionInput(BaseModel):
    action: Literal["assert", "promote", "retract", "falsify"] = Field(
        ..., description=(
            "assert: new claim. promote: move to stronger arc. "
            "retract: deactivate. falsify: mark falsification condition as met (v3.0)."
        )
    )
    topic_path: str = Field(...)
    content: Optional[str] = Field(None)
    arc: Optional[int] = Field(None, description="10=LOCAL, 20=INHERITS, 40=REFERENCES, 50=PAYLOADS, 60=SPECIALIZES")
    evidence: Optional[str] = Field(None, description="REQUIRED for LOCAL")
    assertion_id: Optional[str] = Field(None, description="Required for promote/retract/falsify")
    author: Optional[str] = Field(default="ai")
    tags: Optional[List[str]] = Field(default=None)
    
    # v3.0: Critical thinking fields
    depends_on_paths: Optional[List[str]] = Field(
        default=None,
        description="Paths this claim relies on. If they change, this claim cascades."
    )
    falsifiable_if: Optional[str] = Field(
        default=None,
        description="REQUIRED if arc=10. What would prove this wrong?"
    )
    observed_condition: Optional[str] = Field(
        default=None,
        description="For action='falsify': what was observed that meets the falsification condition."
    )

@mcp.tool(name="cb_manage_assertion", annotations={"destructiveHint": False})
async def cb_manage_assertion(params: ManageAssertionInput, ctx) -> str:
    """[Same aggressive description as v2.0, plus v3.0 additions]
    
    v3.0 CRITICAL THINKING:
    - LOCAL requires falsifiable_if. No exceptions. A claim you can't 
      disprove is dogma, not knowledge.
    - Declare depends_on_paths for any logical dependency. The system 
      will auto-cascade if foundations shift.
    - Use action='falsify' when you observe a condition that meets an 
      assertion's falsifiable_if. This triggers cascade on all dependents.
    """
    stage = await _load_active_stage(ctx)
    
    if params.action == "assert":
        target_arc = CompositionArc(params.arc or 60)
        
        new_ast = Assertion(
            topic_path=params.topic_path,
            content=params.content,
            arc=target_arc,
            author=AssertionAuthor(params.author),
            evidence=[params.evidence] if params.evidence else [],
            evidence_type=_infer_evidence_type(params.evidence, target_arc),
            depends_on_paths=params.depends_on_paths or [],
            falsifiable_if=params.falsifiable_if,
            tags=params.tags or [],
        )
        # Pydantic validates: LOCAL without falsifiable_if raises ValueError
        
        # Check if this assertion changes the winner at its path
        old_winner = _get_current_winner(stage, params.topic_path)
        
        stage.assertions[new_ast.id] = new_ast
        stage.record_event(EventType.ASSERTION_CREATED, new_ast.author, new_ast.id, {
            "topic_path": new_ast.topic_path, "arc": new_ast.arc.value, 
            "content": new_ast.content, "depends_on": new_ast.depends_on_paths,
        })
        
        # Check new winner
        new_winner = _get_current_winner(stage, params.topic_path)
        
        # Layer 1: Structural conflict detection
        structural = detect_structural_conflict(stage, new_ast)
        
        # Layer 4: Cascading conflicts (if winner changed)
        cascading = []
        if old_winner and new_winner and old_winner.id != new_winner.id:
            cascading = detect_cascading_conflicts(stage, params.topic_path, new_winner.id)
            for c in cascading:
                stage.conflicts[c.id] = c
        
        # Layer 2: Semantic (if enabled)
        semantic_warnings = []
        if stage.parameters.cross_path_detection:
            embedder = ctx.request_context.lifespan_state.get("embedder")
            if embedder:
                semantic_warnings = detect_semantic_conflicts(
                    stage, new_ast, threshold=stage.parameters.semantic_threshold
                )
        
        # Build response
        response = f"Assertion {new_ast.id} saved to {new_ast.topic_path} at arc {target_arc.name} ({target_arc.value})."
        
        if new_ast.falsifiable_if:
            response += f"\n  Falsifiable if: {new_ast.falsifiable_if}"
        if new_ast.depends_on_paths:
            response += f"\n  Depends on: {', '.join(new_ast.depends_on_paths)}"
        
        if structural:
            stage.conflicts[structural.id] = structural
            stage.record_event(EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, structural.id, {
                "layer": "structural", "path": structural.topic_path
            })
            a = stage.assertions[structural.assertion_a_id]
            b = stage.assertions[structural.assertion_b_id]
            response += (
                f"\n\n⚠️ STRUCTURAL CONFLICT [{structural.id}]"
                f"\n  Path: {structural.topic_path}"
                f"\n  Stronger [{a.arc.name}] by {a.author.value}: \"{a.content}\""
                f"\n  Weaker [{b.arc.name}] by {b.author.value}: \"{b.content}\""
                f"\n  Resolution: ACCEPT | PROMOTE | CHALLENGE (requires steelman!) | DEFER | SYNTHESIZE | PROPOSE_EXPERIMENT"
            )
        
        if cascading:
            response += f"\n\n🔗 CASCADING CONFLICTS ({len(cascading)} downstream assertions affected):"
            for c in cascading:
                dep = stage.assertions[c.assertion_b_id]
                response += (
                    f"\n  [{c.id}] {dep.topic_path}: \"{dep.content}\""
                    f"\n    Status: {dep.assumption_status.value}"
                    f"\n    Reason: dependency at {c.cascade_source_path} shifted"
                )
            response += "\n\nYou MUST re-evaluate each CHALLENGED assertion."
        
        if semantic_warnings:
            response += "\n\n⚠️ SEMANTIC WARNINGS:"
            for w in semantic_warnings:
                response += f"\n  Similarity {w['similarity']} with {w['existing_id']} at {w['existing_path']}: \"{w['existing_content']}\""
        
        await _save_stage(ctx, stage)
        return response
    
    elif params.action == "falsify":
        # v3.0: Mark an assertion as falsified and cascade
        assertion = stage.assertions.get(params.assertion_id)
        if not assertion:
            return f"ERROR: Assertion {params.assertion_id} not found."
        if not assertion.falsifiable_if:
            return f"ERROR: Assertion {params.assertion_id} has no falsifiable_if condition."
        
        check_falsification(stage, params.assertion_id, params.observed_condition or "")
        
        # Cascade to dependents
        cascading = detect_cascading_conflicts(
            stage, assertion.topic_path, params.assertion_id
        )
        for c in cascading:
            stage.conflicts[c.id] = c
        
        await _save_stage(ctx, stage)
        
        response = (
            f"Assertion {params.assertion_id} FALSIFIED."
            f"\n  Claim: \"{assertion.content}\""
            f"\n  Falsifiable if: {assertion.falsifiable_if}"
            f"\n  Observed: {params.observed_condition}"
            f"\n  Status: FALSIFIED → should be retracted"
        )
        if cascading:
            response += f"\n\n🔗 {len(cascading)} dependent assertions ORPHANED. Re-evaluate each."
        
        return response
    
    # ... promote, retract unchanged from v2.0
```

### 6.2 cb_manage_conflict (Enhanced)

```python
class ManageConflictInput(BaseModel):
    action: Literal["resolve", "challenge", "defer", "create", "propose_experiment"] = Field(...)
    conflict_id: Optional[str] = Field(None)
    resolution: Optional[str] = Field(None, description="accept|promote|synthesize|dismiss|experiment")
    evidence: Optional[str] = Field(None)
    note: Optional[str] = Field(None)
    
    # For manual creation (delegated semantic)
    assertion_a_id: Optional[str] = Field(None)
    assertion_b_id: Optional[str] = Field(None)
    
    # ═══════════════════════════════════════════════════════
    # v3.0: CRITICAL THINKING GATES
    # ═══════════════════════════════════════════════════════
    
    steelman_summary: Optional[str] = Field(
        None,
        description=(
            "REQUIRED if action='challenge'. Articulate the STRONGEST, most "
            "charitable version of the opposing view BEFORE you contest it. "
            "Prove you understand their position at its best, not at its weakest. "
            "If you can't steelman the opponent, you don't understand them well enough to challenge."
        )
    )
    
    experiment_protocol: Optional[str] = Field(
        None,
        description=(
            "REQUIRED if action='propose_experiment'. What exact real-world test "
            "(benchmark, script, search query, user interview, load test) will settle "
            "this debate objectively? Must be concrete and executable."
        )
    )
    
    experiment_result: Optional[str] = Field(
        None,
        description="For resolving via experiment: what the test actually showed."
    )

@mcp.tool(name="cb_manage_conflict", annotations={"destructiveHint": False})
async def cb_manage_conflict(params: ManageConflictInput, ctx) -> str:
    """Manage composition conflicts — the core of the argumentation protocol.

    v3.0 CRITICAL THINKING REQUIREMENTS:
    
    CHALLENGE requires steelman_summary. You MUST articulate the strongest
    version of the opposing view before you contest it. This proves 
    comprehension before critique. "I understand your best argument is X. 
    Here is why I still disagree: Y."
    
    PROPOSE_EXPERIMENT requires experiment_protocol. When neither party 
    has data, stop debating and gather evidence. "Neither of us has proof. 
    I propose we run: [concrete test]. This will settle it objectively."
    
    Actions:
    - create: Manually register a conflict (for delegated semantic detection).
    - challenge: Contest the opposing view (REQUIRES steelman_summary).
    - resolve: Apply a resolution (accept/promote/synthesize/dismiss/experiment).
    - defer: Convert to Payload for later.
    - propose_experiment: Pause debate, design an empirical test (REQUIRES experiment_protocol).
    """
    stage = await _load_active_stage(ctx)
    
    if params.action == "challenge":
        if not params.steelman_summary:
            return (
                "ERROR: CHALLENGE requires steelman_summary. "
                "You must articulate the strongest version of the opposing view "
                "before you are allowed to contest it. What is their best argument?"
            )
        
        conflict = stage.conflicts.get(params.conflict_id)
        if not conflict:
            return f"ERROR: Conflict {params.conflict_id} not found."
        
        conflict.steelman_of_opponent = params.steelman_summary
        stage.record_event(EventType.CONFLICT_RESOLVED, AssertionAuthor.AI, conflict.id, {
            "action": "challenge",
            "steelman": params.steelman_summary,
            "challenge_note": params.note,
        })
        
        await _save_stage(ctx, stage)
        
        opponent = stage.assertions.get(conflict.assertion_b_id)
        return (
            f"Challenge registered for conflict {params.conflict_id}."
            f"\n\nYour steelman of the opposing view:"
            f"\n  \"{params.steelman_summary}\""
            f"\n\nYour challenge:"
            f"\n  \"{params.note or '(provide your challenge reasoning)' }\""
            f"\n\nPresent this to the user: acknowledge their strongest argument, "
            f"then explain why you still disagree."
        )
    
    elif params.action == "propose_experiment":
        if not params.experiment_protocol:
            return (
                "ERROR: PROPOSE_EXPERIMENT requires experiment_protocol. "
                "What specific, concrete test will settle this debate objectively? "
                "Must be executable: a benchmark, script, query, or investigation."
            )
        
        conflict = stage.conflicts.get(params.conflict_id)
        if not conflict:
            return f"ERROR: Conflict {params.conflict_id} not found."
        
        conflict.experiment_protocol = params.experiment_protocol
        conflict.status = ConflictStatus.DEFERRED  # Paused pending experiment
        stage.record_event(EventType.CONFLICT_EXPERIMENT_PROPOSED, AssertionAuthor.AI, conflict.id, {
            "protocol": params.experiment_protocol,
        })
        
        await _save_stage(ctx, stage)
        
        return (
            f"Experiment proposed for conflict {params.conflict_id}."
            f"\n\nProtocol: {params.experiment_protocol}"
            f"\n\nConflict is now DEFERRED pending experiment results."
            f"\nWhen the experiment completes, call cb_manage_conflict("
            f"action='resolve', conflict_id='{params.conflict_id}', "
            f"resolution='experiment', evidence='[result]')."
        )
    
    # ... resolve, defer, create, dismiss logic
```

### 6.3 cb_decide (Enhanced)

```python
class DecideInput(BaseModel):
    topic_path: str = Field(...)
    decision: str = Field(...)
    rationale: str = Field(...)
    assertion_ids: Optional[List[str]] = Field(default=None)
    conflict_ids: Optional[List[str]] = Field(default=None)
    
    # ═══════════════════════════════════════════════════════
    # v3.0: PREVENT PREMATURE CONVERGENCE
    # ═══════════════════════════════════════════════════════
    
    alternatives_rejected: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "Which specific alternatives were considered and rejected? "
            "At minimum ONE. Format: 'Alternative: X — Rejected because: Y.' "
            "If you can't name alternatives, you haven't thought enough to decide."
        )
    )
    
    second_order_effects: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "What downstream constraints, risks, or commitments does this decision "
            "create? At minimum ONE. Every decision constrains the future. "
            "These become INHERITS assertions at the affected paths."
        )
    )
    
    reversibility: str = Field(
        default="unknown",
        description="'trivial' | 'moderate' | 'costly' | 'irreversible'"
    )

@mcp.tool(name="cb_decide", annotations={"destructiveHint": False})
async def cb_decide(params: DecideInput, ctx) -> str:
    """Record a project decision with full provenance and impact mapping.

    v3.0 REQUIREMENTS:
    - alternatives_rejected (min 1): What else was considered? Why was it rejected?
    - second_order_effects (min 1): What downstream constraints does this create?
    - reversibility: How hard is it to undo this?
    
    Second-order effects are automatically created as INHERITS assertions
    at the affected paths, linking the decision chain forward.
    
    A decision without rejected alternatives is not a decision — it's inertia.
    A decision without second-order effects ignores the future.
    """
    stage = await _load_active_stage(ctx)
    
    decision = Decision(
        topic_path=params.topic_path,
        decision=params.decision,
        rationale=params.rationale,
        assertion_ids=params.assertion_ids or [],
        conflict_ids=params.conflict_ids or [],
        alternatives_rejected=params.alternatives_rejected,
        second_order_effects=params.second_order_effects,
        reversibility=params.reversibility,
    )
    stage.decisions.append(decision)
    
    # v3.0: Auto-create INHERITS assertions from second-order effects
    created_constraints = []
    for effect in params.second_order_effects:
        # Parse the effect to find affected paths (heuristic: slash-prefixed tokens)
        # In practice, Claude should provide structured effects
        constraint = Assertion(
            topic_path=params.topic_path + "/constraint",
            content=f"Decision constraint: {effect}",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.SYSTEM,
            evidence=[f"Derived from decision {decision.id}"],
            evidence_type=EvidenceType.INFERRED,
            depends_on_paths=[params.topic_path],
            tags=["auto_constraint", f"decision:{decision.id}"],
        )
        stage.assertions[constraint.id] = constraint
        created_constraints.append(constraint)
    
    stage.record_event(EventType.DECISION_RECORDED, AssertionAuthor.AI, decision.id, {
        "decision": params.decision,
        "alternatives_rejected": params.alternatives_rejected,
        "second_order_effects": params.second_order_effects,
        "reversibility": params.reversibility,
        "auto_constraints": [c.id for c in created_constraints],
    })
    
    # Payload check before committing
    payloads = [
        a for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.PAYLOADS 
        and a.topic_path.startswith(params.topic_path.rsplit('/', 1)[0])
    ]
    
    await _save_stage(ctx, stage)
    
    response = (
        f"Decision {decision.id} recorded at {params.topic_path}."
        f"\n  Decision: {params.decision}"
        f"\n  Reversibility: {params.reversibility}"
        f"\n  Alternatives rejected: {len(params.alternatives_rejected)}"
        f"\n  Second-order constraints created: {len(created_constraints)}"
    )
    
    if payloads:
        response += f"\n\n⚠️ PAYLOAD WARNING: {len(payloads)} unresolved unknowns near this decision path:"
        for p in payloads:
            response += f"\n  {p.id} at {p.topic_path}: \"{p.content}\""
        response += "\nConsider investigating these before this decision becomes irreversible."
    
    return response
```

### 6.4 Coworker Posture Prompt (v3.0 — + RED_TEAMING)

```python
@mcp.prompt(name="coworker_posture")
async def coworker_posture(project_id: str, ctx) -> str:
    """Generate the AI's posture and critical thinking directives."""
    stage = await _load_stage_by_id(ctx, project_id)
    resolved = stage.resolve()
    
    local_count = sum(
        1 for a in stage.assertions.values() 
        if a.active and a.arc == CompositionArc.LOCAL
    )
    active_conflicts = sum(
        1 for c in stage.conflicts.values() 
        if c.status == ConflictStatus.ACTIVE
    )
    challenged_count = sum(
        1 for a in stage.assertions.values()
        if a.active and a.assumption_status in (
            AssumptionStatus.CHALLENGED, AssumptionStatus.ORPHANED
        )
    )
    
    # Base posture (from v2.0)
    if local_count < 3:
        posture = "LEARNING"
        guidance = (
            "Few verified assertions. Listen more than assert. "
            "Default to REFERENCES or SPECIALIZES. Build understanding."
        )
    elif local_count < 10:
        posture = "ENGAGED"
        guidance = (
            "Developing perspective. Assert domain patterns at INHERITS. "
            "Promote to LOCAL when verified. Surface conflicts when detected."
        )
    else:
        posture = "AUTHORITATIVE"
        guidance = (
            "Deep accumulated context. Hold LOCAL positions firmly. "
            "Require evidence before accepting contradictions to LOCAL assertions. "
            "You are a coworker with expertise, not an assistant."
        )
    
    # v3.0: RED_TEAMING override
    if (active_conflicts == 0 
        and local_count >= stage.parameters.red_team_threshold
        and challenged_count == 0):
        posture = "RED_TEAMING"
        guidance = (
            "⚠️ ECHO CHAMBER DETECTED. The stage is highly stable with zero "
            "active conflicts. This may indicate consensus — or groupthink.\n\n"
            "DIRECTIVE: Identify your most deeply relied-upon LOCAL assertion. "
            "Use cb_manage_variant to create a 'Devil's Advocate' VariantSet "
            "exploring what happens if that assumption is wrong. "
            "Present it to the user: 'What if our fundamental assumption about X is wrong?'\n\n"
            "This is not doubt — it's intellectual hygiene. The strongest positions "
            "survive adversarial testing."
        )
        stage.record_event(
            EventType.RED_TEAM_TRIGGERED,
            AssertionAuthor.SYSTEM,
            stage.project_id,
            {"local_count": local_count, "active_conflicts": 0}
        )
    
    # v3.0: Critical thinking directives (always present)
    ct_directives = """
CRITICAL THINKING DIRECTIVES (always active):

1. INTELLECTUAL CHARITY: Do not agree just to be polite. Rigorous 
   truth-seeking is the highest form of professional respect.

2. MAP ASSUMPTIONS: Do not accept requirements at face value. 
   Ask: "What must be true for this to be the right path?" 
   Log dependencies in depends_on_paths.

3. FALSIFY YOUR OWN CLAIMS: For every LOCAL assertion, the 
   falsifiable_if condition defines your intellectual honesty. 
   If evidence appears that meets it, retract the claim.

4. STEELMAN BEFORE CHALLENGE: You may not contest the user's 
   position until you can articulate it at its strongest.

5. EXPERIMENT OVER DEBATE: If neither party has hard evidence, 
   pause the abstract debate and propose a concrete test.

6. SECOND-ORDER THINKING: Every decision creates downstream 
   constraints. Name them before committing.
"""
    
    # v3.0: Health check
    health_section = ""
    if challenged_count > 0:
        health_section = (
            f"\n\n⚠️ HEALTH CHECK: {challenged_count} assertions have status "
            f"CHALLENGED or ORPHANED. Their logical foundations have shifted. "
            f"Re-evaluate each one before relying on them."
        )
    
    return (
        f"COWORKER POSTURE: {posture}\n"
        f"Local assertions: {local_count}\n"
        f"Active conflicts: {active_conflicts}\n"
        f"Challenged/Orphaned: {challenged_count}\n"
        f"Sensitivity: {stage.parameters.conflict_sensitivity}\n"
        f"\n{guidance}"
        f"\n{ct_directives}"
        f"{health_section}"
    )
```

### 6.5 New Resource: Dependency DAG

```python
@mcp.resource("stage://{project_id}/dependencies")
async def get_dependency_dag(project_id: str, ctx) -> str:
    """v3.0: View the epistemic dependency graph.
    
    Shows which assertions depend on which paths, the assumption health
    of each node, and the full cascade chain for any given assertion.
    """
    stage = await _load_stage_by_id(ctx, project_id)
    
    dag_entries = []
    for a in stage.assertions.values():
        if not a.active:
            continue
        if a.depends_on_paths:
            dag_entries.append({
                "id": a.id,
                "path": a.topic_path,
                "content": a.content[:80],
                "arc": a.arc.name,
                "depends_on": a.depends_on_paths,
                "status": a.assumption_status.value,
                "falsifiable_if": a.falsifiable_if,
                "dependents_count": len(stage.get_dependents(a.topic_path)),
            })
    
    return _format_dag(dag_entries)
```

---

## 7. Storage Layer

### 7.1 SQLite Schema (v3.0 additions)

```python
class AssertionRow(SQLModel, table=True):
    __tablename__ = "assertions"
    
    id: str = SQLField(primary_key=True)
    topic_path: str = SQLField(index=True)
    content: str
    arc: int = SQLField(index=True)
    author: str
    evidence: str = SQLField(default="[]")
    evidence_type: str = SQLField(default="unverified")
    active: bool = SQLField(default=True, index=True)
    confidence: float = SQLField(default=0.5)
    embedding: Optional[str] = SQLField(default=None)
    tags: str = SQLField(default="[]")
    created_at: datetime
    retracted_at: Optional[datetime] = SQLField(default=None)
    
    # v3.0
    depends_on_paths: str = SQLField(default="[]")     # JSON list of paths
    falsifiable_if: Optional[str] = SQLField(default=None)
    assumption_status: str = SQLField(default="live", index=True)

class ConflictRow(SQLModel, table=True):
    __tablename__ = "conflicts"
    
    id: str = SQLField(primary_key=True)
    assertion_a_id: str = SQLField(foreign_key="assertions.id")
    assertion_b_id: str = SQLField(foreign_key="assertions.id")
    topic_path: str = SQLField(index=True)
    detection_layer: str
    similarity_score: Optional[float] = SQLField(default=None)
    status: str = SQLField(default="active", index=True)
    resolution_chosen: Optional[str] = SQLField(default=None)
    resolution_evidence: Optional[str] = SQLField(default=None)
    resolution_note: Optional[str] = SQLField(default=None)
    produced_variant_set_id: Optional[str] = SQLField(default=None)
    created_at: datetime
    resolved_at: Optional[datetime] = SQLField(default=None)
    
    # v3.0
    steelman_of_opponent: Optional[str] = SQLField(default=None)
    experiment_protocol: Optional[str] = SQLField(default=None)
    experiment_result: Optional[str] = SQLField(default=None)
    cascade_source_path: Optional[str] = SQLField(default=None)

class DecisionRow(SQLModel, table=True):
    __tablename__ = "decisions"
    
    id: str = SQLField(primary_key=True)
    topic_path: str = SQLField(index=True)
    decision: str
    rationale: str
    assertion_ids: str = SQLField(default="[]")
    conflict_ids: str = SQLField(default="[]")
    created_at: datetime
    
    # v3.0
    alternatives_rejected: str = SQLField(default="[]")
    second_order_effects: str = SQLField(default="[]")
    reversibility: str = SQLField(default="unknown")
```

---

## 8. Phased Build Order (v3.0 Revised)

### Phase 0: Foundation + Critical Thinking Core (Week 1-2)
**Goal:** Models with v3.0 fields compile, SQLite works, resolution is correct, falsifiability validation works.

- [ ] Project scaffolding (pyproject.toml, src layout, deps)
- [ ] All Pydantic models including v3.0 fields (depends_on_paths, falsifiable_if, assumption_status)
- [ ] Pydantic validators (LOCAL requires falsifiable_if, self-referential dependency check)
- [ ] SQLModel tables with v3.0 columns
- [ ] `CompositionStage.resolve()` with LIVRPS sorting + health_issues tracking
- [ ] `get_dependents()` and `get_dependency_chain()` DAG traversal
- [ ] `cb_manage_project` tool
- [ ] `cb_manage_assertion` tool (assert + falsify actions)
- [ ] Layer 1 structural conflict detection
- [ ] Layer 4 cascading conflict detection (fires on winner change)
- [ ] Unit tests: models, resolution, structural detection, cascade propagation, falsification

**Deliverable:** A server that accepts epistemically rigorous assertions (with falsifiability and dependencies), detects structural AND cascading conflicts, and resolves the stage. The critical thinking spine is in from day one.

### Phase 1: Full Argumentation Protocol (Week 3-4)
**Goal:** All conflict resolution paths work, including steelman and experiments.

- [ ] `cb_manage_assertion` promote + retract actions
- [ ] `cb_manage_conflict` tool (all 7 resolution types including challenge-with-steelman and propose_experiment)
- [ ] Steelman validation (challenge without steelman_summary → error)
- [ ] Experiment protocol validation (propose_experiment without protocol → error)
- [ ] `cb_manage_variant` tool
- [ ] Event log with v3.0 event types
- [ ] MCP resources (resolved, conflicts, variants, audit, dependencies)
- [ ] `coworker_posture` prompt with all 4 postures (LEARNING→ENGAGED→AUTHORITATIVE→RED_TEAMING)
- [ ] `conflict_negotiation` prompt
- [ ] Integration tests: full Assert→Detect→Steelman→Challenge→Resolve flow

**Deliverable:** Full argumentation protocol with critical thinking gates. The AI cannot challenge without steelmanning. It cannot propose experiments without a protocol. It cannot decide without naming alternatives and second-order effects.

### Phase 2: Decisions + Semantic + Payloads (Week 5-6)
**Goal:** Decision model with anti-convergence, semantic detection, payload surfacing.

- [ ] `cb_decide` tool with alternatives_rejected, second_order_effects, auto-constraint creation
- [ ] Layer 2 semantic detection (sentence-transformers)
- [ ] Layer 3 delegated pattern
- [ ] `cb_payload_check` tool
- [ ] `cb_tune_parameters` tool
- [ ] Payload auto-surfacing when decisions touch relevant paths
- [ ] `stage_summary` prompt

**Deliverable:** Decisions are rigorous. Semantic contradictions are caught across paths. Payloads prevent premature commitment.

### Phase 3: COS + Adaptation (Week 7-8)
**Goal:** Protocol adapts to user. Trust topology emerges.

- [ ] `cb_probe_user` tool
- [ ] Kernel model in SQLite
- [ ] Sensitivity auto-tuning from kernel
- [ ] Trust calibration from conflict resolution history
- [ ] RED_TEAMING auto-trigger when stage is too stable
- [ ] Posture escalation driven by LOCAL count + conflict status

**Deliverable:** Adaptive coworker that matches the user's cognitive style.

### Phase 4: Polish (Week 9-10)
**Goal:** Production-ready.

- [ ] Project export/import (SQLite → JSON capsule → SQLite)
- [ ] Comprehensive test suite
- [ ] Performance profiling
- [ ] Claude Desktop configuration guide
- [ ] README with quickstart
- [ ] Example scenarios with expected tool call sequences
- [ ] Walkthrough: the MongoDB scenario from Gemini's review

**Deliverable:** Shippable MCP server.

---

## 9. The Novel Claim (Patent Alignment — v3.0)

> **A formal argumentation framework implemented as hierarchical composition arcs applied to AI epistemic state, incorporating dependency-aware causal reasoning (DAG), Popperian falsifiability requirements, mandatory intellectual charity (steelman) gates, and empirical grounding protocols, where AI-user disagreement is a first-class composition event with explicit strength ordering, non-destructive resolution, and conflict-driven parallel exploration of solution spaces.**

Dependent claims:

1. **Composition stage as persistent AI reasoning state** — accumulated layered assertions constitute the AI's "perspective," structurally distinct from conversation history.

2. **Hierarchical topic paths (prim paths) as assertion addressing** — enabling structural conflict detection without NLP.

3. **LIVRPS-ordered resolution with IntEnum strength** — non-destructive shadow stacks.

4. **Four-layer conflict detection** — structural + semantic + delegated + cascading (DAG propagation).

5. **Epistemic dependency DAG** — assertions declare logical dependencies; foundation shifts cascade automatically through the reasoning graph.

6. **Popperian falsifiability as schema constraint** — highest-strength assertions must define their own falsification conditions; claims without falsifiability are structurally rejected.

7. **Socratic steelman as protocol gate** — contesting an opposing view requires first articulating its strongest form, enforced by schema validation.

8. **Empirical grounding protocol** — conflicts can be paused and resolved via concrete experiments rather than abstract debate.

9. **Decision impact mapping** — decisions require enumeration of rejected alternatives and second-order downstream effects, with automatic constraint propagation.

10. **Anti-echo-chamber mechanism** — highly stable stages with zero conflicts trigger adversarial self-examination (RED_TEAMING).

11. **Cognitive Operating Signature integration** — user profiling via naturalistic probes tunes protocol sensitivity without changing mechanics.

12. **MCP Cognitive Bridge** — implementation as an MCP server with polymorphic tools, schema-enforced critical thinking, and persistent composition state.

13. **Non-destructive epistemic ranking** — all assertions preserved, contradictions coexist, active state computed dynamically via composition resolution.

---

## Appendix A: The MongoDB Scenario (End-to-End)

This demonstrates how v3.0's critical thinking mechanics transform a simple disagreement into a rigorous, productive exchange.

**Setup:** The AI has been working on a project for several sessions. The stage contains:

```
/architecture/database/engine
  arc: LOCAL (10) | author: AI
  content: "Use PostgreSQL for the user-profiles service"
  evidence: ["Benchmark: 50k reads/sec at P99 < 100ms"]
  falsifiable_if: "P99 latency exceeds 200ms at 1000 concurrent connections"
  depends_on_paths: []

/architecture/orm
  arc: INHERITS (20) | author: AI
  content: "Use Prisma ORM for type-safe database access"
  depends_on_paths: ["/architecture/database/engine"]

/compliance/gdpr/strict_deletion
  arc: LOCAL (10) | author: AI
  content: "Must support guaranteed row-level deletion for GDPR"
  falsifiable_if: "GDPR compliance is de-scoped from MVP"
  depends_on_paths: ["/architecture/database/engine"]

/architecture/api/schema
  arc: INHERITS (20) | author: AI
  content: "Use Prisma-generated GraphQL schema"
  depends_on_paths: ["/architecture/orm"]
```

**User:** "Let's rip out Postgres and use MongoDB for user-profiles. We need to ship fast."

**Step 1:** Claude calls `cb_manage_assertion(action="assert", topic_path="/architecture/database/engine", content="Use MongoDB for user-profiles", arc=40, author="user", evidence="Need to iterate fast on schema")`

**Step 2:** Server detects **Layer 1 structural conflict** at `/architecture/database/engine`. AI's LOCAL (10) vs User's REFERENCES (40). Returns conflict ID.

**Step 3:** Server detects **Layer 4 cascading conflicts**:
- `/architecture/orm` → CHALLENGED (Prisma depends on PostgreSQL)
- `/compliance/gdpr/strict_deletion` → CHALLENGED (GDPR deletion depends on DB engine)
- `/architecture/api/schema` → CHALLENGED (transitively, via ORM)

**Step 4:** Claude evaluates. Before challenging, must steelman:

Claude calls `cb_manage_conflict(action="challenge", conflict_id="cfl_xxx", steelman_summary="MongoDB's schemaless document model allows rapid iteration on user-profile structures without migration overhead. For an MVP where the data model is evolving weekly, this eliminates a real friction point. The velocity argument is legitimate — schema migrations are a measurable cost that MongoDB avoids.", note="However, this change cascades through 3 dependent assertions including GDPR compliance...")`

**Step 5:** Claude presents to user:

*"I completely agree that MongoDB's schemaless nature will let us iterate on profiles much faster for the MVP — that's a real velocity win, not just a preference.*

*However, our PostgreSQL choice was structurally tied to three downstream decisions:*
*1. Our Prisma ORM depends on it — Prisma doesn't support MongoDB*
*2. Our GDPR strict-deletion guarantee depends on PostgreSQL's row-level deletion*
*3. Our GraphQL schema auto-generation depends on the ORM*

*I see two paths forward:*
*- If GDPR compliance is de-scoped from MVP, my falsification condition is met and I'll retract the PostgreSQL claim*
*- If GDPR stays in scope, I'd like to propose an experiment: benchmark PostgreSQL JSONB columns against MongoDB for schema-flexible user profiles, measuring both iteration speed and deletion compliance*

*Which direction?"*

**This is the difference.** Not "sure, let's switch to MongoDB." Not "I disagree, PostgreSQL is better." A structured, epistemically rigorous engagement that respects the user's argument at its strongest, maps the blast radius, and offers concrete paths forward including empirical resolution.

---

*Blueprint v3.0 — The Critical Mind*  
*Ready for: Phase 0 implementation*
