"""Conflict model — detected contradictions between assertions."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from cognitive_bridge.models.arcs import (
    ConflictDetectionLayer,
    ConflictStatus,
    ResolutionPath,
    _new_id,
    _now_utc,
)


class Conflict(BaseModel):
    """A detected contradiction between assertions.

    v3.0 additions:
    - CASCADING detection layer (Layer 4)
    - PROPOSE_EXPERIMENT resolution path
    - steelman_of_opponent: required context when challenging
    - experiment_protocol: required when proposing experiment
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: _new_id("cfl"))
    assertion_a_id: str = Field(..., description="ID of the stronger/newer assertion")
    assertion_b_id: str = Field(..., description="ID of the weaker/dependent assertion")
    topic_path: str = Field(...)
    detection_layer: ConflictDetectionLayer = Field(...)
    similarity_score: Optional[float] = Field(default=None)

    status: ConflictStatus = Field(default=ConflictStatus.ACTIVE)
    available_paths: list[ResolutionPath] = Field(
        default_factory=lambda: list(ResolutionPath)
    )
    resolution_chosen: Optional[ResolutionPath] = Field(default=None)
    resolution_evidence: Optional[str] = Field(default=None)
    resolution_note: Optional[str] = Field(default=None)

    # v3.0: Critical thinking resolution metadata
    steelman_of_opponent: Optional[str] = Field(
        default=None,
        description="The strongest version of the opposing view. Required before CHALLENGE.",
    )
    experiment_protocol: Optional[str] = Field(
        default=None,
        description=(
            "Concrete test to settle the debate empirically. "
            "Required for PROPOSE_EXPERIMENT."
        ),
    )
    experiment_result: Optional[str] = Field(
        default=None,
        description="What the experiment actually showed (populated after execution).",
    )

    # v3.0: Cascade context
    cascade_source_path: Optional[str] = Field(
        default=None,
        description="For CASCADING conflicts: which dependency path triggered this cascade.",
    )

    produced_variant_set_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now_utc)
    resolved_at: Optional[datetime] = Field(default=None)
