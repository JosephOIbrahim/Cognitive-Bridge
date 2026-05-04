"""Decision model — recorded project decisions with full provenance and impact mapping."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cognitive_bridge.models.arcs import _new_id, _now_utc


class Decision(BaseModel):
    """A recorded project decision with full provenance and impact mapping.

    v3.0: Decisions must account for what was rejected and what downstream
    effects are created. This prevents premature convergence by requiring
    explicit enumeration of alternatives and second-order consequences.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: _new_id("dec"))
    topic_path: str = Field(
        ...,
        description="Hierarchical path of the domain this decision governs",
    )
    decision: str = Field(..., max_length=10000, description="What was decided")
    rationale: str = Field(..., max_length=10000, description="Why this was decided")

    assertion_ids: list[str] = Field(
        default_factory=list,
        description="Assertions that informed this decision",
    )
    conflict_ids: list[str] = Field(
        default_factory=list,
        description="Conflicts that were resolved by this decision",
    )

    # v3.0: Prevent premature convergence — both fields are schema-enforced
    alternatives_rejected: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Which specific alternatives were considered and rejected? "
            "At least one required. Format: 'Alternative X — rejected because Y.'"
        ),
    )
    second_order_effects: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "What downstream constraints, risks, or requirements does this decision create? "
            "At least one required. These become INHERITS assertions at affected paths."
        ),
    )
    reversibility: str = Field(
        default="unknown",
        description=(
            "How reversible? "
            "'trivial' | 'moderate' | 'costly' | 'irreversible' | 'unknown'"
        ),
    )

    created_at: datetime = Field(default_factory=_now_utc)

    @field_validator("alternatives_rejected", "second_order_effects")
    @classmethod
    def _no_blank_items(cls, v: list[str]) -> list[str]:
        """Reject empty or whitespace-only items.

        Pydantic's str_strip_whitespace runs on top-level string fields, not on
        items inside list fields. Without this validator ['  '] would pass
        min_length=1 — satisfying the anti-convergence gate without enumerating
        any real alternative.

        Side effect: items are stripped in-place. This is documented behaviour;
        callers should not rely on preserved leading/trailing whitespace.
        """
        cleaned = [s.strip() for s in v]
        if any(not s for s in cleaned):
            raise ValueError(
                "List items cannot be empty or whitespace-only. "
                "Each entry must describe a concrete alternative or effect."
            )
        return cleaned
