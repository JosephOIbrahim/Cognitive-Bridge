"""Cognitive Bridge models — re-exports for convenient imports."""

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
    EventType,
    EvidenceType,
    ResolutionPath,
    _new_id,
    _now_utc,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.decision import Decision
from cognitive_bridge.models.event import Event
from cognitive_bridge.models.kernel import IndividualKernel
from cognitive_bridge.models.parameters import CognitiveParameters
from cognitive_bridge.models.stage import CompositionStage
from cognitive_bridge.models.variant_set import Variant, VariantSet

__all__ = [
    # Enums
    "AssertionAuthor",
    "AssumptionStatus",
    "CompositionArc",
    "ConflictDetectionLayer",
    "ConflictStatus",
    "EvidenceType",
    "EventType",
    "ResolutionPath",
    # Models
    "Assertion",
    "Conflict",
    "Decision",
    "Event",
    "IndividualKernel",
    "CognitiveParameters",
    "CompositionStage",
    "Variant",
    "VariantSet",
    # Utilities
    "_new_id",
    "_now_utc",
]
