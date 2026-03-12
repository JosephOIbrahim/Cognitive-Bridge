"""Integration tests for cb_tune_parameters tool.

Each test is independent — no shared mutable state. Every test builds its own
in-memory SQLiteStore and isolated active_stages dict via the mock context helper.
"""

import pytest

from cognitive_bridge.models import (
    CompositionArc,
    CompositionStage,
    EventType,
)
from cognitive_bridge.server import load_stage_from_db, save_stage_to_db
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


def _make_ctx(
    store: SQLiteStore | None = None,
    active_stages: dict | None = None,
) -> _MockLifespanContext:
    """Build a mock context with optional overrides."""
    if store is None:
        store = SQLiteStore(":memory:")
    if active_stages is None:
        active_stages = {}
    return _MockLifespanContext(store=store, active_stages=active_stages)


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
    ctx = _make_ctx(store=store, active_stages=active_stages)
    return store, active_stages, ctx


# ═══════════════════════════════════════════════════════════════
# View Current Parameters
# ═══════════════════════════════════════════════════════════════


class TestViewCurrentParameters:
    """Tests for calling cb_tune_parameters with no update arguments."""

    @pytest.mark.asyncio
    async def test_no_params_returns_current_settings(self) -> None:
        """Calling with no parameters returns all current settings without error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx)
        assert "ERROR" not in result
        assert "conflict_sensitivity" in result
        assert "semantic_threshold" in result
        assert "cross_path_detection" in result
        assert "exploration_budget" in result
        assert "ai_default_arc" in result
        assert "payload_surfacing" in result
        assert "red_team_threshold" in result
        assert "cascade_auto_challenge" in result

    @pytest.mark.asyncio
    async def test_view_shows_defaults(self) -> None:
        """Default parameter values appear in the view output."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx)
        # Default conflict_sensitivity is 0.5
        assert "0.5" in result
        # Default ai_default_arc is INHERITS (20)
        assert "INHERITS" in result
        # Default red_team_threshold is 8
        assert "8" in result

    @pytest.mark.asyncio
    async def test_no_params_does_not_record_event(self) -> None:
        """Read-only view does not append a PARAMETERS_TUNED event."""
        store, active_stages, ctx = _make_active_project()
        await cb_tune_parameters(ctx=ctx)
        stage = active_stages["test_project"]
        event_types = [e.event_type for e in stage.events]
        assert EventType.PARAMETERS_TUNED not in event_types


# ═══════════════════════════════════════════════════════════════
# Update Single Parameter
# ═══════════════════════════════════════════════════════════════


class TestUpdateSingleParameter:
    """Tests for updating one parameter at a time."""

    @pytest.mark.asyncio
    async def test_update_conflict_sensitivity(self) -> None:
        """Setting conflict_sensitivity=0.8 updates the stage and appears in response."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, conflict_sensitivity=0.8)
        assert "ERROR" not in result
        assert "conflict_sensitivity" in result
        assert "0.8" in result
        stage = active_stages["test_project"]
        assert stage.parameters.conflict_sensitivity == 0.8

    @pytest.mark.asyncio
    async def test_update_semantic_threshold(self) -> None:
        """Setting semantic_threshold=0.9 updates the stage."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, semantic_threshold=0.9)
        assert "ERROR" not in result
        assert "0.9" in result
        stage = active_stages["test_project"]
        assert stage.parameters.semantic_threshold == 0.9

    @pytest.mark.asyncio
    async def test_update_exploration_budget(self) -> None:
        """Setting exploration_budget=5 updates the stage."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, exploration_budget=5)
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.exploration_budget == 5

    @pytest.mark.asyncio
    async def test_update_red_team_threshold(self) -> None:
        """Setting red_team_threshold=12 updates the stage."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, red_team_threshold=12)
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.red_team_threshold == 12


# ═══════════════════════════════════════════════════════════════
# Update Multiple Parameters
# ═══════════════════════════════════════════════════════════════


class TestUpdateMultipleParameters:
    """Tests for updating multiple parameters simultaneously."""

    @pytest.mark.asyncio
    async def test_update_sensitivity_and_threshold(self) -> None:
        """Setting both conflict_sensitivity and semantic_threshold updates both."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(
            ctx=ctx,
            conflict_sensitivity=0.7,
            semantic_threshold=0.85,
        )
        assert "ERROR" not in result
        assert "conflict_sensitivity" in result
        assert "semantic_threshold" in result
        stage = active_stages["test_project"]
        assert stage.parameters.conflict_sensitivity == 0.7
        assert stage.parameters.semantic_threshold == 0.85

    @pytest.mark.asyncio
    async def test_update_all_parameters(self) -> None:
        """Providing all parameters in a single call updates all of them."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(
            ctx=ctx,
            conflict_sensitivity=0.9,
            semantic_threshold=0.75,
            cross_path_detection=True,
            exploration_budget=7,
            ai_default_arc=20,
            payload_surfacing=False,
            red_team_threshold=10,
            cascade_auto_challenge=False,
        )
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        p = stage.parameters
        assert p.conflict_sensitivity == 0.9
        assert p.semantic_threshold == 0.75
        assert p.cross_path_detection is True
        assert p.exploration_budget == 7
        assert p.ai_default_arc == CompositionArc.INHERITS
        assert p.payload_surfacing is False
        assert p.red_team_threshold == 10
        assert p.cascade_auto_challenge is False


# ═══════════════════════════════════════════════════════════════
# Boolean Toggles
# ═══════════════════════════════════════════════════════════════


class TestBooleanToggles:
    """Tests for toggling boolean parameters."""

    @pytest.mark.asyncio
    async def test_cross_path_detection_enable(self) -> None:
        """Setting cross_path_detection=True stores True on the stage."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, cross_path_detection=True)
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.cross_path_detection is True

    @pytest.mark.asyncio
    async def test_cross_path_detection_disable(self) -> None:
        """Setting cross_path_detection=False stores False on the stage."""
        store, active_stages, ctx = _make_active_project()
        # Enable first, then disable
        await cb_tune_parameters(ctx=ctx, cross_path_detection=True)
        result = await cb_tune_parameters(ctx=ctx, cross_path_detection=False)
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.cross_path_detection is False

    @pytest.mark.asyncio
    async def test_cascade_auto_challenge_disable(self) -> None:
        """Setting cascade_auto_challenge=False stores False on the stage."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, cascade_auto_challenge=False)
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.cascade_auto_challenge is False

    @pytest.mark.asyncio
    async def test_cascade_auto_challenge_re_enable(self) -> None:
        """Toggling cascade_auto_challenge from False back to True stores True."""
        store, active_stages, ctx = _make_active_project()
        await cb_tune_parameters(ctx=ctx, cascade_auto_challenge=False)
        result = await cb_tune_parameters(ctx=ctx, cascade_auto_challenge=True)
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.cascade_auto_challenge is True

    @pytest.mark.asyncio
    async def test_payload_surfacing_disable(self) -> None:
        """Setting payload_surfacing=False stores False on the stage."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, payload_surfacing=False)
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        assert stage.parameters.payload_surfacing is False


# ═══════════════════════════════════════════════════════════════
# ai_default_arc Integer Mapping
# ═══════════════════════════════════════════════════════════════


class TestAiDefaultArcMapping:
    """Tests for setting ai_default_arc via integer value."""

    @pytest.mark.asyncio
    async def test_ai_default_arc_local(self) -> None:
        """Setting ai_default_arc=10 stores CompositionArc.LOCAL."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, ai_default_arc=10)
        assert "ERROR" not in result
        assert "LOCAL" in result
        stage = active_stages["test_project"]
        assert stage.parameters.ai_default_arc == CompositionArc.LOCAL

    @pytest.mark.asyncio
    async def test_ai_default_arc_inherits(self) -> None:
        """Setting ai_default_arc=20 stores CompositionArc.INHERITS."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, ai_default_arc=20)
        assert "ERROR" not in result
        assert "INHERITS" in result
        stage = active_stages["test_project"]
        assert stage.parameters.ai_default_arc == CompositionArc.INHERITS

    @pytest.mark.asyncio
    async def test_ai_default_arc_specializes(self) -> None:
        """Setting ai_default_arc=60 stores CompositionArc.SPECIALIZES."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, ai_default_arc=60)
        assert "ERROR" not in result
        assert "SPECIALIZES" in result
        stage = active_stages["test_project"]
        assert stage.parameters.ai_default_arc == CompositionArc.SPECIALIZES

    @pytest.mark.asyncio
    async def test_ai_default_arc_invalid_value_returns_error(self) -> None:
        """An integer that maps to no CompositionArc returns an error with valid values."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, ai_default_arc=99)
        assert "ERROR" in result
        assert "99" in result
        # Should list valid values so the caller knows how to fix it
        assert "LOCAL" in result or "10" in result


# ═══════════════════════════════════════════════════════════════
# Validation Rejections (Pydantic field constraints)
# ═══════════════════════════════════════════════════════════════


class TestValidationRejections:
    """Tests for parameter values that violate Pydantic field constraints."""

    @pytest.mark.asyncio
    async def test_conflict_sensitivity_above_max_returns_error(self) -> None:
        """conflict_sensitivity=1.5 violates le=1.0 and returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, conflict_sensitivity=1.5)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_conflict_sensitivity_below_min_returns_error(self) -> None:
        """conflict_sensitivity=-0.1 violates ge=0.0 and returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, conflict_sensitivity=-0.1)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_semantic_threshold_below_min_returns_error(self) -> None:
        """semantic_threshold=0.3 violates ge=0.5 and returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, semantic_threshold=0.3)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_semantic_threshold_above_max_returns_error(self) -> None:
        """semantic_threshold=1.0 violates le=0.99 and returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, semantic_threshold=1.0)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_exploration_budget_below_min_returns_error(self) -> None:
        """exploration_budget=0 violates ge=1 and returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, exploration_budget=0)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_exploration_budget_above_max_returns_error(self) -> None:
        """exploration_budget=21 violates le=20 and returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, exploration_budget=21)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_red_team_threshold_above_max_returns_error(self) -> None:
        """red_team_threshold=25 violates le=20 and returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, red_team_threshold=25)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_red_team_threshold_below_min_returns_error(self) -> None:
        """red_team_threshold=1 violates ge=3 and returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_tune_parameters(ctx=ctx, red_team_threshold=1)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_stage_unchanged_after_validation_error(self) -> None:
        """When a validation error occurs the stage parameters are not mutated."""
        store, active_stages, ctx = _make_active_project()
        original_sensitivity = active_stages["test_project"].parameters.conflict_sensitivity
        await cb_tune_parameters(ctx=ctx, conflict_sensitivity=99.0)
        stage = active_stages["test_project"]
        assert stage.parameters.conflict_sensitivity == original_sensitivity


# ═══════════════════════════════════════════════════════════════
# Event Recording
# ═══════════════════════════════════════════════════════════════


class TestEventRecording:
    """Tests for PARAMETERS_TUNED event recording."""

    @pytest.mark.asyncio
    async def test_update_records_parameters_tuned_event(self) -> None:
        """A successful update appends a PARAMETERS_TUNED event to the stage."""
        store, active_stages, ctx = _make_active_project()
        await cb_tune_parameters(ctx=ctx, conflict_sensitivity=0.8)
        stage = active_stages["test_project"]
        event_types = [e.event_type for e in stage.events]
        assert EventType.PARAMETERS_TUNED in event_types

    @pytest.mark.asyncio
    async def test_event_detail_contains_updated_key(self) -> None:
        """The PARAMETERS_TUNED event detail includes the name of the updated key."""
        store, active_stages, ctx = _make_active_project()
        await cb_tune_parameters(ctx=ctx, semantic_threshold=0.88)
        stage = active_stages["test_project"]
        tuned_events = [
            e for e in stage.events if e.event_type == EventType.PARAMETERS_TUNED
        ]
        assert len(tuned_events) == 1
        detail = tuned_events[0].detail or {}
        updates = detail.get("updates", {})
        assert "semantic_threshold" in updates

    @pytest.mark.asyncio
    async def test_multiple_updates_record_multiple_events(self) -> None:
        """Each separate call records a distinct PARAMETERS_TUNED event."""
        store, active_stages, ctx = _make_active_project()
        await cb_tune_parameters(ctx=ctx, conflict_sensitivity=0.6)
        await cb_tune_parameters(ctx=ctx, exploration_budget=4)
        stage = active_stages["test_project"]
        tuned_events = [
            e for e in stage.events if e.event_type == EventType.PARAMETERS_TUNED
        ]
        assert len(tuned_events) == 2


# ═══════════════════════════════════════════════════════════════
# Persistence Round-Trip
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """Tests that parameter updates survive a save/load cycle."""

    @pytest.mark.asyncio
    async def test_updated_parameters_survive_reload(self) -> None:
        """After updating and saving, reloading the project restores the new values."""
        store = SQLiteStore(":memory:")
        store, active_stages, ctx = _make_active_project(store=store)

        await cb_tune_parameters(
            ctx=ctx,
            conflict_sensitivity=0.9,
            semantic_threshold=0.95,
            cross_path_detection=True,
            exploration_budget=6,
            ai_default_arc=10,
            payload_surfacing=False,
            red_team_threshold=15,
            cascade_auto_challenge=False,
        )

        recovered = load_stage_from_db(store, "test_project")
        p = recovered.parameters
        assert p.conflict_sensitivity == 0.9
        assert p.semantic_threshold == 0.95
        assert p.cross_path_detection is True
        assert p.exploration_budget == 6
        assert p.ai_default_arc == CompositionArc.LOCAL
        assert p.payload_surfacing is False
        assert p.red_team_threshold == 15
        assert p.cascade_auto_challenge is False

    @pytest.mark.asyncio
    async def test_partial_update_leaves_other_fields_intact(self) -> None:
        """Updating one field leaves all other fields at their previous values."""
        store, active_stages, ctx = _make_active_project()

        # First, set a non-default value for a field we will NOT touch next
        await cb_tune_parameters(ctx=ctx, exploration_budget=7)

        # Now update a different field only
        await cb_tune_parameters(ctx=ctx, conflict_sensitivity=0.3)

        stage = active_stages["test_project"]
        # exploration_budget must still be 7
        assert stage.parameters.exploration_budget == 7
        # conflict_sensitivity must be the new value
        assert stage.parameters.conflict_sensitivity == 0.3


# ═══════════════════════════════════════════════════════════════
# Error Paths: No Active Project
# ═══════════════════════════════════════════════════════════════


class TestNoActiveProject:
    """Tests for calls made when no project is active."""

    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        """Calling cb_tune_parameters with no active project returns an error."""
        ctx = _make_ctx()  # empty active_stages
        result = await cb_tune_parameters(ctx=ctx, conflict_sensitivity=0.5)
        assert "ERROR" in result
        assert "No active project" in result

    @pytest.mark.asyncio
    async def test_view_with_no_active_project_returns_error(self) -> None:
        """Even the read-only view returns an error when no project is active."""
        ctx = _make_ctx()
        result = await cb_tune_parameters(ctx=ctx)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_nonexistent_project_id_returns_error(self) -> None:
        """Specifying a project_id that is not active returns an error."""
        _, _, ctx = _make_active_project(project_id="real_project")
        result = await cb_tune_parameters(
            ctx=ctx,
            conflict_sensitivity=0.5,
            project_id="ghost_project",
        )
        assert "ERROR" in result
        assert "ghost_project" in result

    @pytest.mark.asyncio
    async def test_multiple_active_no_project_id_returns_error(self) -> None:
        """With multiple active projects and no project_id, an error is returned."""
        store = SQLiteStore(":memory:")
        stage_a = CompositionStage(project_id="proj_a", project_name="Project A")
        stage_b = CompositionStage(project_id="proj_b", project_name="Project B")
        save_stage_to_db(store, stage_a)
        save_stage_to_db(store, stage_b)
        active_stages = {"proj_a": stage_a, "proj_b": stage_b}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        result = await cb_tune_parameters(ctx=ctx, conflict_sensitivity=0.6)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_explicit_project_id_selects_correct_stage(self) -> None:
        """When multiple projects are active, project_id selects the correct one."""
        store = SQLiteStore(":memory:")
        stage_a = CompositionStage(project_id="proj_a", project_name="Project A")
        stage_b = CompositionStage(project_id="proj_b", project_name="Project B")
        save_stage_to_db(store, stage_a)
        save_stage_to_db(store, stage_b)
        active_stages = {"proj_a": stage_a, "proj_b": stage_b}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        result = await cb_tune_parameters(
            ctx=ctx,
            conflict_sensitivity=0.9,
            project_id="proj_a",
        )
        assert "ERROR" not in result
        # proj_a should be updated
        assert stage_a.parameters.conflict_sensitivity == 0.9
        # proj_b should remain at default
        assert stage_b.parameters.conflict_sensitivity == 0.5
