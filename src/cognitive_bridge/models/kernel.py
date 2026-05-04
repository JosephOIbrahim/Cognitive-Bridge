"""IndividualKernel — Cognitive Operating Signature (COS) for user profiling."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from cognitive_bridge.models.arcs import _new_id, _now_utc


class IndividualKernel(BaseModel):
    """The user's Cognitive Operating Signature (COS).

    Captures user preferences along four dimensions that tune how the
    argumentation protocol adapts to the user's working style. Stored
    as a singleton per project in SQLite. Updated via cb_probe_user.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: _new_id("ker"))

    # Core COS dimensions (0.0 to 1.0)
    entropy_tolerance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much ambiguity/chaos the user tolerates. "
            "Low = wants certainty. High = embraces uncertainty."
        ),
    )
    process_purity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much the user values following process. "
            "Low = pragmatic shortcuts. High = strict methodology."
        ),
    )
    autonomy_boundary: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much autonomy the AI should take. "
            "Low = check everything. High = act independently."
        ),
    )
    energy_level: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "User's current energy/capacity. "
            "Low = depleted, be gentle. High = energized, push harder."
        ),
    )

    # Metadata
    probe_count: int = Field(
        default=0,
        ge=0,
        description="How many probes have updated this kernel.",
    )
    last_probed: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
