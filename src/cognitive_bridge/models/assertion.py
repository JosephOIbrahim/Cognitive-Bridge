"""Assertion model — the fundamental epistemic claim in the composition stage.

An Assertion is an atomic epistemic claim staked at a hierarchical topic path.
Composition arcs (LIVRPS) determine strength: lower integer = stronger = harder to override.

v3.0 additions:
- depends_on_paths: Creates a DAG. If a dependency shifts, this assertion cascades.
- falsifiable_if: Required for LOCAL. What would prove this wrong?
- assumption_status: Tracks whether this assertion's logical foundations still hold.
"""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    EvidenceType,
    _new_id,
    _now_utc,
)

# Single source of truth for path syntax. Reused for both topic_path validation
# (Field pattern) and dependency-path validation (model_validator).
_TOPIC_PATH_PATTERN = re.compile(r"^(/[a-z][a-z0-9_]*)+$")


class Assertion(BaseModel):
    """A single epistemic claim in the composition stage.

    Assertions occupy a topic_path slot. Multiple assertions at the same path
    compete; resolve() selects the winner by LIVRPS arc strength, then confidence,
    then recency. The loser is not deleted — it is shadowed.

    Critical invariant: Assertions are never deleted from the DB. active=False
    means retracted. The composition stage is non-destructive.
    """

    model_config = ConfigDict(frozen=False, str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: _new_id("ast"))
    topic_path: str = Field(
        ...,
        description="Hierarchical path (USD prim path). E.g., '/architecture/database/engine'",
        pattern=_TOPIC_PATH_PATTERN.pattern,
    )
    content: str = Field(..., max_length=10000, description="The claim itself")
    arc: CompositionArc = Field(..., description="Composition strength (lower int = stronger)")
    author: AssertionAuthor = Field(...)

    # Provenance
    evidence: list[str] = Field(default_factory=list)
    evidence_type: EvidenceType = Field(default=EvidenceType.UNVERIFIED)

    # v3.0: Critical thinking fields
    depends_on_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Topic paths this claim logically relies on. Creates DAG edges. "
            "If the winning assertion at any of these paths changes, this claim "
            "is flagged as CHALLENGED and a Layer 4 cascading conflict fires."
        ),
    )
    falsifiable_if: Optional[str] = Field(
        default=None,
        max_length=2000,
        description=(
            "REQUIRED for arc=LOCAL (10). What specific, observable condition would "
            "prove this assertion wrong? Must be concrete and testable."
        ),
    )
    assumption_status: AssumptionStatus = Field(
        default=AssumptionStatus.LIVE,
        description="Health of this assertion's logical foundations.",
    )

    # Standard fields
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_now_utc)
    retracted_at: Optional[datetime] = Field(default=None)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    # Embeddings are part of canonical state (not excluded from model_dump): the
    # storage converter and JSON capsule export rely on uniform serialisation.
    embedding: Optional[list[float]] = Field(default=None)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_local_requires_falsifiability(self) -> "Assertion":
        """LOCAL assertions MUST declare how they can be proven wrong.

        A claim without falsifiability is dogma, not knowledge (Popper).
        This validator hard-rejects LOCAL assertions that omit falsifiable_if —
        it is not a warning, it is a schema gate.
        """
        if self.arc == CompositionArc.LOCAL and not self.falsifiable_if:
            raise ValueError(
                "LOCAL (arc=10) assertions require 'falsifiable_if'. "
                "What specific condition would prove this wrong? "
                "A claim without falsifiability is dogma, not knowledge."
            )
        return self

    @model_validator(mode="after")
    def validate_dependency_paths(self) -> "Assertion":
        """Dependencies must be valid topic paths and cannot be self-referential.

        Self-referential dependencies would create trivial cycles in the DAG.
        All dependency paths must match the same regex as topic_path — preventing
        traversal sequences, embedded nulls, mixed case, and other unsanitised
        strings from propagating through the DAG via the dependency edge.
        """
        for dep in self.depends_on_paths:
            if dep == self.topic_path:
                raise ValueError(
                    f"Assertion cannot depend on its own path: {dep}"
                )
            if not _TOPIC_PATH_PATTERN.match(dep):
                raise ValueError(
                    f"Dependency path '{dep}' must match topic_path pattern "
                    f"{_TOPIC_PATH_PATTERN.pattern}"
                )
        return self

    def __lt__(self, other: "Assertion") -> bool:
        """Sort by descending priority: arc strength -> confidence -> recency.

        Lower arc integer = stronger = sorts first (wins resolve()).
        Equal arc: higher confidence wins.
        Equal arc + confidence: newer created_at wins.

        This enables: sorted(assertions)[0] = the composition winner.
        """
        if self.arc != other.arc:
            return self.arc < other.arc
        if self.confidence != other.confidence:
            return self.confidence > other.confidence
        return self.created_at > other.created_at
