"""Tests for injection profiles and their integration with cb_tune_parameters.

Each test is independent — no shared mutable state. Every test builds its own
in-memory SQLiteStore and isolated active_stages dict via the mock context helper.
"""

import pytest

from cognitive_bridge.models import (
    CompositionArc,
    CompositionStage,
    CognitiveParameters,
)
from cognitive_bridge.models.injection import InjectionProfile, PROFILE_PARAMS
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.parameters_tool import cb_tune_parameters


# ═══════════════════════════════════════════════════════════════
# Mock Context
# ═══════════════════════════════════════════════════════════════


class _MockLifespanContext:
    """Minimal context wrapper exposing lifespan_context for tool handlers."""

    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {
            "store": store,
            "active_stages": active_stages,
        }


def _make_active_project(
    project_id: str = "test_project",
    store: SQLiteStore | None = None,
) -> tuple[SQLiteStore, dict, _MockLifespanContext]:
    """Create a store, stage, and context with one active project ready to use."""
    if store is None:
        store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Test Project")
    save_stage_to_db(store, stage)
    active_stages = {project_id: stage}
    ctx = _MockLifespanContext(store=store, active_stages=active_stages)
    return store, active_stages, ctx


# ═══════════════════════════════════════════════════════════════
# Enum Completeness
# ═══════════════════════════════════════════════════════════════


class TestInjectionProfileEnum:
    """Tests for InjectionProfile enum structure."""

    def test_all_five_profiles_exist(self) -> None:
        """InjectionProfile contains exactly the 5 expected members."""
        expected = {"none", "microdose", "perceptual", "classical", "mdma"}
        actual = {p.value for p in InjectionProfile}
        assert actual == expected

    def test_profile_values_are_strings(self) -> None:
        """InjectionProfile members have str values for JSON compatibility."""
        for profile in InjectionProfile:
            assert isinstance(profile.value, str)

    def test_none_profile_exists(self) -> None:
        """InjectionProfile.NONE resolves from string 'none'."""
        assert InjectionProfile("none") is InjectionProfile.NONE

    def test_classical_profile_exists(self) -> None:
        """InjectionProfile.CLASSICAL resolves from string 'classical'."""
        assert InjectionProfile("classical") is InjectionProfile.CLASSICAL

    def test_mdma_profile_exists(self) -> None:
        """InjectionProfile.MDMA resolves from string 'mdma'."""
        assert InjectionProfile("mdma") is InjectionProfile.MDMA


# ═══════════════════════════════════════════════════════════════
# PROFILE_PARAMS Structure
# ═══════════════════════════════════════════════════════════════


class TestProfileParamsStructure:
    """Tests for the PROFILE_PARAMS mapping completeness and correctness."""

    EXPECTED_KEYS = {
        "conflict_sensitivity",
        "semantic_threshold",
        "exploration_budget",
        "cross_path_detection",
        "ai_default_arc",
        "red_team_threshold",
        "cascade_auto_challenge",
        "payload_surfacing",
    }

    def test_all_profiles_have_entries(self) -> None:
        """Every InjectionProfile member has an entry in PROFILE_PARAMS."""
        for profile in InjectionProfile:
            assert profile in PROFILE_PARAMS, f"Missing entry for {profile}"

    def test_all_profiles_have_eight_keys(self) -> None:
        """Each PROFILE_PARAMS entry contains all 8 CognitiveParameters fields."""
        for profile, preset in PROFILE_PARAMS.items():
            assert set(preset.keys()) == self.EXPECTED_KEYS, (
                f"Profile {profile.value} has wrong keys: {set(preset.keys())}"
            )

    def test_none_profile_matches_defaults(self) -> None:
        """PROFILE_PARAMS[NONE] values match CognitiveParameters field defaults."""
        defaults = CognitiveParameters()
        preset = PROFILE_PARAMS[InjectionProfile.NONE]
        assert preset["conflict_sensitivity"] == defaults.conflict_sensitivity
        assert preset["semantic_threshold"] == defaults.semantic_threshold
        assert preset["exploration_budget"] == defaults.exploration_budget
        assert preset["cross_path_detection"] == defaults.cross_path_detection
        # ai_default_arc stored as int in preset, as enum on model
        assert preset["ai_default_arc"] == defaults.ai_default_arc.value
        assert preset["red_team_threshold"] == defaults.red_team_threshold
        assert preset["cascade_auto_challenge"] == defaults.cascade_auto_challenge
        assert preset["payload_surfacing"] == defaults.payload_surfacing

    def test_all_profile_presets_produce_valid_parameters(self) -> None:
        """CognitiveParameters(**preset) succeeds for every profile without raising."""
        for profile, preset in PROFILE_PARAMS.items():
            try:
                params = CognitiveParameters(**preset)
            except Exception as exc:
                pytest.fail(
                    f"Profile '{profile.value}' preset raised {type(exc).__name__}: {exc}"
                )
            assert isinstance(params, CognitiveParameters)

    def test_mdma_profile_arc_is_references(self) -> None:
        """MDMA profile sets ai_default_arc to 40 (REFERENCES)."""
        preset = PROFILE_PARAMS[InjectionProfile.MDMA]
        assert preset["ai_default_arc"] == 40

    def test_classical_profile_values(self) -> None:
        """CLASSICAL profile has sensitivity=0.9, budget=8, cross_path=True."""
        preset = PROFILE_PARAMS[InjectionProfile.CLASSICAL]
        assert preset["conflict_sensitivity"] == 0.9
        assert preset["exploration_budget"] == 8
        assert preset["cross_path_detection"] is True


# ═══════════════════════════════════════════════════════════════
# Profile Application via Tool
# ═══════════════════════════════════════════════════════════════


class TestProfileApplicationViaTool:
    """Tests for applying profiles through cb_tune_parameters."""

    @pytest.mark.asyncio
    async def test_classical_profile_applies_correct_values(self) -> None:
        """Applying 'classical' profile sets sensitivity=0.9 and budget=8."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, profile="classical")
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.conflict_sensitivity == 0.9
        assert stage.parameters.exploration_budget == 8
        assert stage.parameters.cross_path_detection is True

    @pytest.mark.asyncio
    async def test_profile_response_contains_profile_name(self) -> None:
        """Applying a profile includes 'Profile applied: classical' in the response."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, profile="classical")
        assert "Profile applied: classical" in result

    @pytest.mark.asyncio
    async def test_mdma_profile_sets_arc_to_references(self) -> None:
        """Applying 'mdma' profile sets ai_default_arc to REFERENCES (40)."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, profile="mdma")
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.ai_default_arc == CompositionArc.REFERENCES

    @pytest.mark.asyncio
    async def test_perceptual_profile_enables_cross_path(self) -> None:
        """Applying 'perceptual' profile enables cross_path_detection."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, profile="perceptual")
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.cross_path_detection is True

    @pytest.mark.asyncio
    async def test_none_profile_resets_to_defaults(self) -> None:
        """Applying 'none' after 'classical' resets parameters to default values."""
        store, active_stages, ctx = _make_active_project()
        # First raise sensitivity via classical
        await cb_tune_parameters(ctx=ctx, profile="classical")
        assert active_stages["test_project"].parameters.conflict_sensitivity == 0.9
        # Then reset to none
        result = await cb_tune_parameters(ctx=ctx, profile="none")
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.conflict_sensitivity == 0.5
        assert stage.parameters.exploration_budget == 3
        assert stage.parameters.cross_path_detection is False

    @pytest.mark.asyncio
    async def test_microdose_profile_applies(self) -> None:
        """Applying 'microdose' profile sets sensitivity=0.6 and budget=4."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, profile="microdose")
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.conflict_sensitivity == 0.6
        assert stage.parameters.exploration_budget == 4


# ═══════════════════════════════════════════════════════════════
# Individual Parameter Overrides on Top of Profile
# ═══════════════════════════════════════════════════════════════


class TestProfileWithIndividualOverrides:
    """Tests for combining a profile with individual parameter overrides."""

    @pytest.mark.asyncio
    async def test_individual_param_overrides_profile_value(self) -> None:
        """conflict_sensitivity=0.5 overrides classical's 0.9 while budget stays 8."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(
            ctx=ctx,
            profile="classical",
            conflict_sensitivity=0.5,
        )
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        # Individual override wins
        assert stage.parameters.conflict_sensitivity == 0.5
        # Profile value preserved for non-overridden fields
        assert stage.parameters.exploration_budget == 8

    @pytest.mark.asyncio
    async def test_override_shows_in_response(self) -> None:
        """Response includes both 'Profile applied' and the overridden key."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(
            ctx=ctx,
            profile="classical",
            conflict_sensitivity=0.5,
        )
        assert "Profile applied: classical" in result
        assert "conflict_sensitivity" in result

    @pytest.mark.asyncio
    async def test_multiple_overrides_on_profile(self) -> None:
        """Multiple individual overrides all apply on top of the profile base."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(
            ctx=ctx,
            profile="classical",
            conflict_sensitivity=0.55,
            exploration_budget=6,
        )
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.conflict_sensitivity == 0.55
        assert stage.parameters.exploration_budget == 6
        # Non-overridden classical value: cross_path_detection = True
        assert stage.parameters.cross_path_detection is True


# ═══════════════════════════════════════════════════════════════
# Invalid Profile Input
# ═══════════════════════════════════════════════════════════════


class TestInvalidProfile:
    """Tests for invalid profile values."""

    @pytest.mark.asyncio
    async def test_invalid_profile_returns_error(self) -> None:
        """Passing an unknown profile name returns an ERROR response."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, profile="invalid")
        assert "ERROR" in result
        assert "invalid" in result

    @pytest.mark.asyncio
    async def test_invalid_profile_lists_valid_options(self) -> None:
        """Error response for invalid profile lists valid profile names."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, profile="turbo")
        assert "ERROR" in result
        # At least some valid profile names must appear in the error message
        assert "none" in result or "classical" in result or "mdma" in result

    @pytest.mark.asyncio
    async def test_invalid_profile_does_not_mutate_stage(self) -> None:
        """Stage parameters are unchanged when an invalid profile is rejected."""
        store, active_stages, ctx = _make_active_project()
        original_sensitivity = active_stages["test_project"].parameters.conflict_sensitivity
        await cb_tune_parameters(ctx=ctx, profile="nonexistent")
        assert active_stages["test_project"].parameters.conflict_sensitivity == original_sensitivity

    @pytest.mark.asyncio
    async def test_empty_string_profile_returns_error(self) -> None:
        """Passing an empty string as profile returns an ERROR response."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, profile="")
        assert "ERROR" in result


# ═══════════════════════════════════════════════════════════════
# Backward Compatibility (no profile)
# ═══════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """Tests that existing behavior is unchanged when profile is not provided."""

    @pytest.mark.asyncio
    async def test_no_profile_no_params_shows_current_settings(self) -> None:
        """Calling with no args still returns a read-only view of current settings."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx)
        assert "ERROR" not in result
        assert "conflict_sensitivity" in result
        assert "0.5" in result

    @pytest.mark.asyncio
    async def test_no_profile_single_param_update_works(self) -> None:
        """Individual parameter update without profile still works as before."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, conflict_sensitivity=0.7)
        assert "ERROR" not in result
        assert "Profile applied" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.conflict_sensitivity == 0.7

    @pytest.mark.asyncio
    async def test_no_profile_does_not_appear_in_response(self) -> None:
        """Response does not mention 'Profile applied' when no profile is set."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, conflict_sensitivity=0.8)
        assert "Profile applied" not in result


# ═══════════════════════════════════════════════════════════════
# Profile Switch Mid-Session
# ═══════════════════════════════════════════════════════════════


class TestProfileSwitch:
    """Tests for switching profiles mid-session."""

    @pytest.mark.asyncio
    async def test_profile_switch_classical_to_none(self) -> None:
        """Switching from 'classical' to 'none' fully resets to default values."""
        store, active_stages, ctx = _make_active_project()
        await cb_tune_parameters(ctx=ctx, profile="classical")
        await cb_tune_parameters(ctx=ctx, profile="none")
        stage = active_stages["test_project"]
        defaults = CognitiveParameters()
        assert stage.parameters.conflict_sensitivity == defaults.conflict_sensitivity
        assert stage.parameters.semantic_threshold == defaults.semantic_threshold
        assert stage.parameters.exploration_budget == defaults.exploration_budget
        assert stage.parameters.cross_path_detection == defaults.cross_path_detection
        assert stage.parameters.ai_default_arc == defaults.ai_default_arc
        assert stage.parameters.red_team_threshold == defaults.red_team_threshold

    @pytest.mark.asyncio
    async def test_profile_switch_mdma_to_classical(self) -> None:
        """Switching from 'mdma' to 'classical' replaces all values correctly."""
        store, active_stages, ctx = _make_active_project()
        await cb_tune_parameters(ctx=ctx, profile="mdma")
        assert active_stages["test_project"].parameters.ai_default_arc == CompositionArc.REFERENCES

        await cb_tune_parameters(ctx=ctx, profile="classical")
        stage = active_stages["test_project"]
        # classical has arc=20 (INHERITS) and high sensitivity
        assert stage.parameters.ai_default_arc == CompositionArc.INHERITS
        assert stage.parameters.conflict_sensitivity == 0.9
