"""Injection profiles — preset parameter configurations for cognitive exploration.

Each profile maps to a specific set of CognitiveParameters values that tune
the argumentation protocol's sensitivity, exploration breadth, and challenge
thresholds. Profiles can be applied via cb_tune_parameters(profile="...").

The profiles represent different intensities of cognitive exploration:
- none: Default conservative settings
- microdose: Slightly elevated sensitivity and exploration
- perceptual: Moderate cross-path detection and wider exploration
- classical: High sensitivity, deep exploration, aggressive red-teaming
- mdma: Elevated empathy mode — wider acceptance arc, moderate sensitivity
"""

from enum import Enum


class InjectionProfile(str, Enum):
    """Available injection profiles for cognitive parameter presets."""

    NONE = "none"
    MICRODOSE = "microdose"
    PERCEPTUAL = "perceptual"
    CLASSICAL = "classical"
    MDMA = "mdma"


# Parameter presets for each profile.
# Keys match CognitiveParameters field names exactly.
PROFILE_PARAMS: dict[InjectionProfile, dict] = {
    InjectionProfile.NONE: {
        "conflict_sensitivity": 0.5,
        "semantic_threshold": 0.80,
        "exploration_budget": 3,
        "cross_path_detection": False,
        "ai_default_arc": 20,  # INHERITS
        "red_team_threshold": 8,
        "cascade_auto_challenge": True,
        "payload_surfacing": True,
    },
    InjectionProfile.MICRODOSE: {
        "conflict_sensitivity": 0.6,
        "semantic_threshold": 0.78,
        "exploration_budget": 4,
        "cross_path_detection": False,
        "ai_default_arc": 20,
        "red_team_threshold": 8,
        "cascade_auto_challenge": True,
        "payload_surfacing": True,
    },
    InjectionProfile.PERCEPTUAL: {
        "conflict_sensitivity": 0.7,
        "semantic_threshold": 0.75,
        "exploration_budget": 5,
        "cross_path_detection": True,
        "ai_default_arc": 20,
        "red_team_threshold": 7,
        "cascade_auto_challenge": True,
        "payload_surfacing": True,
    },
    InjectionProfile.CLASSICAL: {
        "conflict_sensitivity": 0.9,
        "semantic_threshold": 0.65,
        "exploration_budget": 8,
        "cross_path_detection": True,
        "ai_default_arc": 20,
        "red_team_threshold": 5,
        "cascade_auto_challenge": True,
        "payload_surfacing": True,
    },
    InjectionProfile.MDMA: {
        "conflict_sensitivity": 0.6,
        "semantic_threshold": 0.78,
        "exploration_budget": 5,
        "cross_path_detection": True,
        "ai_default_arc": 40,  # REFERENCES — more accepting
        "red_team_threshold": 10,
        "cascade_auto_challenge": True,
        "payload_surfacing": True,
    },
}
