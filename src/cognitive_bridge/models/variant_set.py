"""VariantSet model — competing hypotheses coexisting without premature collapse."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from cognitive_bridge.models.arcs import _new_id, _now_utc


class Variant(BaseModel):
    """A single named hypothesis within a VariantSet."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(...)
    content: str = Field(...)
    supporting_assertion_ids: list[str] = Field(default_factory=list)
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    activation_condition: Optional[str] = Field(default=None)
    active: bool = Field(default=True)


class VariantSet(BaseModel):
    """Multiple competing hypotheses coexisting without premature collapse.

    Requires at least 2 variants — a single hypothesis is just an assertion,
    not a variant set. The min_length constraint enforces this at the schema level.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: _new_id("var"))
    name: str = Field(...)
    topic_path: str = Field(...)
    variants: list[Variant] = Field(..., min_length=2)
    source_conflict_id: Optional[str] = Field(default=None)
    source_red_team: bool = Field(
        default=False,
        description="v3.0: True if produced by RED_TEAMING posture (devil's advocate)",
    )
    resolved: bool = Field(default=False)
    resolved_variant_name: Optional[str] = Field(default=None)
    resolution_evidence: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now_utc)
    resolved_at: Optional[datetime] = Field(default=None)
