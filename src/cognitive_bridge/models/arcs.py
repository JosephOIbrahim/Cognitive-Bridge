"""Core enums and utilities for the Cognitive Bridge composition system.

All enums used across models are defined here to avoid circular imports.
Composition arcs follow USD-inspired LIVRPS ordering where lower integer = stronger.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum, IntEnum

# ═══════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════

def _now_utc() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def _new_id(prefix: str = "ast") -> str:
    """Generate a prefixed UUID-based ID. Format: {prefix}_{uuid_hex[:12]}."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ═══════════════════════════════════════════════════════════════
# Composition Arcs (LIVRPS)
# ═══════════════════════════════════════════════════════════════

class CompositionArc(IntEnum):
    """LIVRPS ordering. Lower integer = stronger arc = harder to override.

    Spaced values (10, 20, ...) leave room for future intermediate arcs.
    """

    LOCAL = 10        # Verified, high-confidence. Requires falsifiability.
    INHERITS = 20     # Domain expertise, structural priors.
    VARIANT_SET = 30  # Active hypothesis branches (multiple coexist).
    REFERENCES = 40   # Stated preferences, external citations.
    PAYLOADS = 50     # Known unknowns — evidence exists but isn't loaded.
    SPECIALIZES = 60  # Baseline training knowledge. Always overridable.


# ═══════════════════════════════════════════════════════════════
# Assertion Enums
# ═══════════════════════════════════════════════════════════════

class AssertionAuthor(str, Enum):
    """Who made the assertion."""

    AI = "ai"
    USER = "user"
    SYSTEM = "system"
    EXTERNAL = "external"


class EvidenceType(str, Enum):
    """How the evidence was obtained."""

    COMPUTED = "computed"
    OBSERVED = "observed"
    CITED = "cited"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"


class AssumptionStatus(str, Enum):
    """Tracks the health of an assertion's logical foundations."""

    LIVE = "live"              # All dependencies hold. Structurally sound.
    CHALLENGED = "challenged"  # A dependency has shifted. Needs re-evaluation.
    FALSIFIED = "falsified"    # Falsification condition was met. Should retract.
    ORPHANED = "orphaned"      # A dependency was retracted entirely. No foundation.


# ═══════════════════════════════════════════════════════════════
# Conflict Enums
# ═══════════════════════════════════════════════════════════════

class ConflictStatus(str, Enum):
    """Current state of a conflict."""

    ACTIVE = "active"
    RESOLVED_OVERRIDE = "override"
    RESOLVED_PROMOTED = "promoted"
    RESOLVED_SYNTHESIZED = "synthesized"
    RESOLVED_EXPERIMENT = "experiment"  # v3.0: Settled by empirical test
    DEFERRED = "deferred"
    DISMISSED = "dismissed"


class ResolutionPath(str, Enum):
    """Available resolution strategies for conflicts."""

    ACCEPT = "accept"
    PROMOTE = "promote"
    CHALLENGE = "challenge"
    DEFER = "defer"
    SYNTHESIZE = "synthesize"
    DISMISS = "dismiss"
    PROPOSE_EXPERIMENT = "propose_experiment"  # v3.0


class ConflictDetectionLayer(str, Enum):
    """Which detection mechanism found the conflict."""

    STRUCTURAL = "structural"    # Same topic_path, different content
    SEMANTIC = "semantic"        # Embedding similarity across paths
    DELEGATED = "delegated"      # Boomeranged to Claude for evaluation
    CASCADING = "cascading"      # v3.0: Dependency DAG propagation


# ═══════════════════════════════════════════════════════════════
# Event Log Enums
# ═══════════════════════════════════════════════════════════════

class EventType(str, Enum):
    """Types of events in the append-only audit log."""

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
