"""CognitiveParameters — runtime parameters that tune the argumentation protocol."""

from pydantic import BaseModel, ConfigDict, Field

from cognitive_bridge.models.arcs import CompositionArc


class CognitiveParameters(BaseModel):
    """Runtime parameters that tune the argumentation protocol.

    All values have sensible defaults. Use cb_tune_parameters to adjust
    these at runtime. Changes are recorded as PARAMETERS_TUNED events.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # Conflict detection
    conflict_sensitivity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How aggressively to flag potential conflicts. 0=permissive, 1=strict.",
    )
    semantic_threshold: float = Field(
        default=0.80,
        ge=0.5,
        le=0.99,
        description="Cosine similarity threshold for semantic conflict detection.",
    )
    cross_path_detection: bool = Field(
        default=False,
        description="Whether to run semantic detection across different topic paths.",
    )

    # Exploration
    exploration_budget: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of active VARIANT_SET branches allowed per topic path.",
    )

    # Assertiveness
    ai_default_arc: CompositionArc = Field(
        default=CompositionArc.INHERITS,
        description="Default composition arc applied to AI-authored assertions.",
    )
    payload_surfacing: bool = Field(
        default=True,
        description="Whether to surface PAYLOADS assertions as warnings in tool responses.",
    )

    # v3.0: Anti-echo-chamber controls
    red_team_threshold: int = Field(
        default=8,
        ge=3,
        le=20,
        description=(
            "Number of LOCAL assertions with zero active conflicts before "
            "RED_TEAMING posture activates."
        ),
    )
    cascade_auto_challenge: bool = Field(
        default=True,
        description=(
            "Automatically mark dependent assertions as CHALLENGED when "
            "a dependency shifts."
        ),
    )
