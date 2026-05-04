"""Integration tests for the cb_tune_parameters tool.

Blueprint reference: Section 3.8, Section 6.1.
Constitution rules C8 (event-log audit), G2 (validator-rejection symmetry).

CognitiveParameters field constraints:
- semantic_threshold: ge=0.5, le=0.99
- red_team_threshold: ge=3, le=20
- exploration_budget: ge=1, le=20
- conflict_sensitivity: ge=0.0, le=1.0
"""

import pytest

from cognitive_bridge.models import CompositionArc, CompositionStage, EventType
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.parameters_tool import cb_tune_parameters


class _MockCtx:
    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx(store: SQLiteStore | None = None, active_stages: dict | None = None) -> _MockCtx:
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


def _make_ctx_with_stage(project_id: str = "proj_params_test") -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Params Test Project")
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    return _make_ctx(store=store, active_stages=active_stages), stage, store


class TestReadOnlyMode:
    @pytest.mark.asyncio
    async def test_no_args_returns_current_settings(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        initial = len(stage.events)
        result = await cb_tune_parameters(ctx=ctx)
        assert "conflict_sensitivity" in result
        assert "semantic_threshold" in result
        assert "exploration_budget" in result
        assert len(stage.events) == initial

    @pytest.mark.asyncio
    async def test_no_args_shows_default_values(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(ctx=ctx)
        assert "0.5" in result
        assert "0.8" in result


class TestIndividualKnobs:
    @pytest.mark.asyncio
    async def test_tune_conflict_sensitivity(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(conflict_sensitivity=0.9, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.conflict_sensitivity == 0.9
        assert EventType.PARAMETERS_TUNED in [e.event_type for e in stage.events]

    @pytest.mark.asyncio
    async def test_tune_semantic_threshold(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(semantic_threshold=0.75, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.semantic_threshold == 0.75
        assert EventType.PARAMETERS_TUNED in [e.event_type for e in stage.events]

    @pytest.mark.asyncio
    async def test_tune_cross_path_detection(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(cross_path_detection=True, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.cross_path_detection is True

    @pytest.mark.asyncio
    async def test_tune_exploration_budget(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(exploration_budget=10, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.exploration_budget == 10

    @pytest.mark.asyncio
    async def test_tune_ai_default_arc_to_local(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(ai_default_arc=10, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.ai_default_arc == CompositionArc.LOCAL

    @pytest.mark.asyncio
    async def test_tune_ai_default_arc_to_references(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(ai_default_arc=40, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.ai_default_arc == CompositionArc.REFERENCES

    @pytest.mark.asyncio
    async def test_tune_payload_surfacing(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(payload_surfacing=False, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.payload_surfacing is False

    @pytest.mark.asyncio
    async def test_tune_red_team_threshold(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(red_team_threshold=12, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.red_team_threshold == 12

    @pytest.mark.asyncio
    async def test_tune_cascade_auto_challenge(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(cascade_auto_challenge=False, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.cascade_auto_challenge is False

    @pytest.mark.asyncio
    async def test_multiple_knobs_updated_atomically(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(
            conflict_sensitivity=0.8, cross_path_detection=True, exploration_budget=7, ctx=ctx,
        )
        assert "ERROR" not in result
        assert stage.parameters.conflict_sensitivity == 0.8
        assert stage.parameters.cross_path_detection is True
        assert stage.parameters.exploration_budget == 7
        events = [e for e in stage.events if e.event_type == EventType.PARAMETERS_TUNED]
        assert len(events) == 1


class TestOutOfRangeRejections:
    @pytest.mark.asyncio
    async def test_semantic_threshold_below_minimum_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(semantic_threshold=0.4, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_semantic_threshold_at_minimum_boundary_succeeds(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(semantic_threshold=0.5, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.semantic_threshold == 0.5

    @pytest.mark.asyncio
    async def test_semantic_threshold_above_maximum_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(semantic_threshold=1.0, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_red_team_threshold_below_minimum_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(red_team_threshold=2, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_red_team_threshold_at_minimum_boundary_succeeds(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(red_team_threshold=3, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.red_team_threshold == 3

    @pytest.mark.asyncio
    async def test_red_team_threshold_above_maximum_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(red_team_threshold=21, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_red_team_threshold_at_maximum_boundary_succeeds(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(red_team_threshold=20, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.red_team_threshold == 20

    @pytest.mark.asyncio
    async def test_exploration_budget_zero_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(exploration_budget=0, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_exploration_budget_above_maximum_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(exploration_budget=21, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_exploration_budget_at_minimum_boundary_succeeds(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(exploration_budget=1, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.exploration_budget == 1

    @pytest.mark.asyncio
    async def test_exploration_budget_at_maximum_boundary_succeeds(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(exploration_budget=20, ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.exploration_budget == 20

    @pytest.mark.asyncio
    async def test_conflict_sensitivity_above_maximum_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(conflict_sensitivity=1.5, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_conflict_sensitivity_below_minimum_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(conflict_sensitivity=-0.1, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_invalid_ai_default_arc_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(ai_default_arc=99, ctx=ctx)
        assert result.startswith("ERROR:")
        assert "ai_default_arc" in result

    @pytest.mark.asyncio
    async def test_no_event_when_validation_fails(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        initial = len(stage.events)
        await cb_tune_parameters(semantic_threshold=0.1, ctx=ctx)
        assert EventType.PARAMETERS_TUNED not in [e.event_type for e in stage.events]
        assert len(stage.events) == initial


class TestInjectionProfiles:
    @pytest.mark.asyncio
    async def test_profile_none_applies_defaults(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(profile="none", ctx=ctx)
        assert "ERROR" not in result
        assert "none" in result.lower() or "Profile" in result
        assert EventType.PARAMETERS_TUNED in [e.event_type for e in stage.events]

    @pytest.mark.asyncio
    async def test_profile_microdose_applies(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(profile="microdose", ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.conflict_sensitivity == 0.6
        assert stage.parameters.exploration_budget == 4

    @pytest.mark.asyncio
    async def test_profile_classical_applies(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(profile="classical", ctx=ctx)
        assert "ERROR" not in result
        assert stage.parameters.conflict_sensitivity == 0.9
        assert stage.parameters.exploration_budget == 8

    @pytest.mark.asyncio
    async def test_invalid_profile_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(profile="overdose", ctx=ctx)
        assert result.startswith("ERROR:")
        assert "overdose" in result

    @pytest.mark.asyncio
    async def test_profile_with_individual_override(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_tune_parameters(
            profile="microdose", conflict_sensitivity=0.85, ctx=ctx,
        )
        assert "ERROR" not in result
        assert stage.parameters.conflict_sensitivity == 0.85
        assert stage.parameters.exploration_budget == 4


class TestErrorConditions:
    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        ctx = _make_ctx()
        result = await cb_tune_parameters(conflict_sensitivity=0.7, ctx=ctx)
        assert result.startswith("ERROR:")
