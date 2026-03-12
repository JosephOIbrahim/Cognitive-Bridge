"""Integration tests for cb_manage_conflict tool.

Strategy: each test builds its own in-memory SQLiteStore and isolated
active_stages dict, pre-populates the stage with the assertions and/or
conflicts required for that scenario, then calls cb_manage_conflict
directly using a minimal mock Context.

No shared mutable state exists between tests.
"""

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    Conflict,
    ConflictDetectionLayer,
    ConflictStatus,
    CompositionStage,
    ResolutionPath,
)
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.conflict_tool import cb_manage_conflict


# ═══════════════════════════════════════════════════════════════
# Mock Context
# ═══════════════════════════════════════════════════════════════


class _MockCtx:
    """Minimal context that exposes lifespan_context with store + active_stages."""

    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx(
    store: SQLiteStore | None = None,
    active_stages: dict | None = None,
) -> _MockCtx:
    """Build a mock context, creating an in-memory store if not provided."""
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_stage_with_assertions(project_id: str = "proj_cfl_test") -> CompositionStage:
    """Build a stage pre-populated with two assertions at the same path."""
    stage = CompositionStage(project_id=project_id, project_name="Conflict Tool Tests")
    ast_a = Assertion(
        topic_path="/architecture/database",
        content="PostgreSQL is the primary datastore",
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
    )
    ast_b = Assertion(
        topic_path="/architecture/database",
        content="MongoDB is the primary datastore",
        arc=CompositionArc.SPECIALIZES,
        author=AssertionAuthor.USER,
    )
    stage.assertions[ast_a.id] = ast_a
    stage.assertions[ast_b.id] = ast_b
    return stage, ast_a, ast_b


def _make_stage_with_conflict(
    project_id: str = "proj_cfl_test",
) -> tuple[CompositionStage, Conflict, Assertion, Assertion]:
    """Build a stage pre-populated with two assertions and a manual conflict."""
    stage, ast_a, ast_b = _make_stage_with_assertions(project_id)
    cfl = Conflict(
        assertion_a_id=ast_a.id,
        assertion_b_id=ast_b.id,
        topic_path="/architecture/database",
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )
    stage.conflicts[cfl.id] = cfl
    return stage, cfl, ast_a, ast_b


def _active_stages_for(stage: CompositionStage) -> dict:
    return {stage.project_id: stage}


# ═══════════════════════════════════════════════════════════════
# Tests: action='resolve'
# ═══════════════════════════════════════════════════════════════


class TestResolveAction:
    """Tests for action='resolve'."""

    @pytest.mark.asyncio
    async def test_resolve_accept_sets_resolved_status(self) -> None:
        """Resolving with 'accept' sets conflict status to resolved_override."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra001")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
            resolution="accept",
        )

        assert "ERROR" not in result
        assert "resolved" in result.lower()
        assert stage.conflicts[cfl.id].status == ConflictStatus.RESOLVED_OVERRIDE

    @pytest.mark.asyncio
    async def test_resolve_response_contains_conflict_id(self) -> None:
        """The resolve response includes the conflict ID."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra002")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
            resolution="accept",
        )

        assert cfl.id in result

    @pytest.mark.asyncio
    async def test_resolve_dismiss_sets_dismissed_status(self) -> None:
        """Resolving with 'dismiss' sets conflict status to dismissed."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra003")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
            resolution="dismiss",
        )

        assert "ERROR" not in result
        assert stage.conflicts[cfl.id].status == ConflictStatus.DISMISSED

    @pytest.mark.asyncio
    async def test_resolve_invalid_resolution_path_returns_error(self) -> None:
        """An unrecognized resolution path returns an error listing valid paths."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra004")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
            resolution="destroy",
        )

        assert "ERROR" in result
        assert "destroy" in result

    @pytest.mark.asyncio
    async def test_resolve_without_conflict_id_returns_error(self) -> None:
        """resolve without a conflict_id returns an error."""
        store = SQLiteStore(":memory:")
        stage, _, _, _ = _make_stage_with_conflict("proj_ra005")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            resolution="accept",
        )

        assert "ERROR" in result
        assert "conflict_id" in result

    @pytest.mark.asyncio
    async def test_resolve_without_resolution_returns_error(self) -> None:
        """resolve without a resolution path returns an error."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra006")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
        )

        assert "ERROR" in result
        assert "resolution" in result

    @pytest.mark.asyncio
    async def test_resolve_already_resolved_conflict_returns_error(self) -> None:
        """Attempting to resolve a conflict that is not ACTIVE returns an error."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra007")
        # Pre-mark it as resolved
        cfl.status = ConflictStatus.RESOLVED_OVERRIDE
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
            resolution="accept",
        )

        assert "ERROR" in result
        assert "not active" in result.lower()

    @pytest.mark.asyncio
    async def test_resolve_synthesize_path(self) -> None:
        """Resolving with 'synthesize' sets RESOLVED_SYNTHESIZED status."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra008")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
            resolution="synthesize",
        )

        assert "ERROR" not in result
        assert stage.conflicts[cfl.id].status == ConflictStatus.RESOLVED_SYNTHESIZED

    @pytest.mark.asyncio
    async def test_resolve_challenge_via_resolve_action_returns_error(self) -> None:
        """Using action='resolve' with resolution='challenge' is blocked."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra009")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
            resolution="challenge",
        )

        assert "ERROR" in result
        assert "action='challenge'" in result

    @pytest.mark.asyncio
    async def test_resolve_defer_via_resolve_action_returns_error(self) -> None:
        """Using action='resolve' with resolution='defer' is blocked."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ra010")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id=cfl.id,
            resolution="defer",
        )

        assert "ERROR" in result
        assert "action='defer'" in result


# ═══════════════════════════════════════════════════════════════
# Tests: action='challenge'
# ═══════════════════════════════════════════════════════════════


class TestChallengeAction:
    """Tests for action='challenge'."""

    @pytest.mark.asyncio
    async def test_challenge_without_steelman_returns_error(self) -> None:
        """challenge without steelman_summary returns an error naming the requirement."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ch001")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="challenge",
            ctx=ctx,
            conflict_id=cfl.id,
        )

        assert "ERROR" in result
        assert "steelman_summary" in result

    @pytest.mark.asyncio
    async def test_challenge_with_steelman_registers_challenge(self) -> None:
        """challenge with steelman_summary records the challenge and keeps conflict ACTIVE."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ch002")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="challenge",
            ctx=ctx,
            conflict_id=cfl.id,
            steelman_summary="MongoDB offers better horizontal scaling for large write workloads.",
        )

        assert "ERROR" not in result
        assert "Challenge registered" in result
        # Conflict must remain ACTIVE after a challenge
        assert stage.conflicts[cfl.id].status == ConflictStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_challenge_response_includes_steelman(self) -> None:
        """The challenge response echoes the steelman back so it's visible in the log."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ch003")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))
        summary = "MongoDB's document model eliminates expensive JOINs for nested data."

        result = await cb_manage_conflict(
            action="challenge",
            ctx=ctx,
            conflict_id=cfl.id,
            steelman_summary=summary,
        )

        assert summary in result

    @pytest.mark.asyncio
    async def test_challenge_without_conflict_id_returns_error(self) -> None:
        """challenge without conflict_id returns an error."""
        store = SQLiteStore(":memory:")
        stage, _, _, _ = _make_stage_with_conflict("proj_ch004")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="challenge",
            ctx=ctx,
            steelman_summary="Some steelman text.",
        )

        assert "ERROR" in result
        assert "conflict_id" in result

    @pytest.mark.asyncio
    async def test_challenge_stores_steelman_on_conflict(self) -> None:
        """After challenge, conflict.steelman_of_opponent is populated."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_ch005")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))
        summary = "The team has years of MongoDB expertise, reducing operational risk."

        await cb_manage_conflict(
            action="challenge",
            ctx=ctx,
            conflict_id=cfl.id,
            steelman_summary=summary,
        )

        assert stage.conflicts[cfl.id].steelman_of_opponent == summary


# ═══════════════════════════════════════════════════════════════
# Tests: action='defer'
# ═══════════════════════════════════════════════════════════════


class TestDeferAction:
    """Tests for action='defer'."""

    @pytest.mark.asyncio
    async def test_defer_sets_deferred_status(self) -> None:
        """defer sets conflict status to DEFERRED."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_df001")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="defer",
            ctx=ctx,
            conflict_id=cfl.id,
        )

        assert "ERROR" not in result
        assert stage.conflicts[cfl.id].status == ConflictStatus.DEFERRED

    @pytest.mark.asyncio
    async def test_defer_response_contains_conflict_id(self) -> None:
        """The defer response includes the conflict ID."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_df002")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="defer",
            ctx=ctx,
            conflict_id=cfl.id,
            note="Will decide after performance benchmarks.",
        )

        assert cfl.id in result
        assert "Will decide after performance benchmarks." in result

    @pytest.mark.asyncio
    async def test_defer_without_conflict_id_returns_error(self) -> None:
        """defer without conflict_id returns an error."""
        store = SQLiteStore(":memory:")
        stage, _, _, _ = _make_stage_with_conflict("proj_df003")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="defer",
            ctx=ctx,
        )

        assert "ERROR" in result
        assert "conflict_id" in result


# ═══════════════════════════════════════════════════════════════
# Tests: action='create'
# ═══════════════════════════════════════════════════════════════


class TestCreateAction:
    """Tests for action='create'."""

    @pytest.mark.asyncio
    async def test_create_valid_conflict_returns_conflict_id(self) -> None:
        """create with two valid assertions creates a new conflict and returns its ID."""
        store = SQLiteStore(":memory:")
        stage, ast_a, ast_b = _make_stage_with_assertions("proj_cr001")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="create",
            ctx=ctx,
            assertion_a_id=ast_a.id,
            assertion_b_id=ast_b.id,
            topic_path="/architecture/database",
        )

        assert "ERROR" not in result
        assert "cfl_" in result  # ID prefix
        assert len(stage.conflicts) == 1

    @pytest.mark.asyncio
    async def test_create_conflict_is_delegated_layer(self) -> None:
        """Manually created conflicts use the DELEGATED detection layer."""
        store = SQLiteStore(":memory:")
        stage, ast_a, ast_b = _make_stage_with_assertions("proj_cr002")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        await cb_manage_conflict(
            action="create",
            ctx=ctx,
            assertion_a_id=ast_a.id,
            assertion_b_id=ast_b.id,
            topic_path="/architecture/database",
        )

        cfl = next(iter(stage.conflicts.values()))
        assert cfl.detection_layer == ConflictDetectionLayer.DELEGATED

    @pytest.mark.asyncio
    async def test_create_missing_assertion_a_returns_error(self) -> None:
        """create with a non-existent assertion_a_id returns an error."""
        store = SQLiteStore(":memory:")
        stage, ast_a, ast_b = _make_stage_with_assertions("proj_cr003")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="create",
            ctx=ctx,
            assertion_a_id="ast_does_not_exist",
            assertion_b_id=ast_b.id,
            topic_path="/architecture/database",
        )

        assert "ERROR" in result
        assert "ast_does_not_exist" in result

    @pytest.mark.asyncio
    async def test_create_missing_assertion_b_returns_error(self) -> None:
        """create with a non-existent assertion_b_id returns an error."""
        store = SQLiteStore(":memory:")
        stage, ast_a, ast_b = _make_stage_with_assertions("proj_cr004")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="create",
            ctx=ctx,
            assertion_a_id=ast_a.id,
            assertion_b_id="ast_ghost",
            topic_path="/architecture/database",
        )

        assert "ERROR" in result
        assert "ast_ghost" in result

    @pytest.mark.asyncio
    async def test_create_without_topic_path_returns_error(self) -> None:
        """create without topic_path returns an error."""
        store = SQLiteStore(":memory:")
        stage, ast_a, ast_b = _make_stage_with_assertions("proj_cr005")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="create",
            ctx=ctx,
            assertion_a_id=ast_a.id,
            assertion_b_id=ast_b.id,
        )

        assert "ERROR" in result
        assert "topic_path" in result

    @pytest.mark.asyncio
    async def test_create_without_both_assertion_ids_returns_error(self) -> None:
        """create without both assertion IDs returns an error."""
        store = SQLiteStore(":memory:")
        stage, ast_a, ast_b = _make_stage_with_assertions("proj_cr006")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="create",
            ctx=ctx,
            assertion_a_id=ast_a.id,
            topic_path="/architecture/database",
        )

        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_create_records_event_in_stage(self) -> None:
        """Manually created conflict appends a CONFLICT_DETECTED event to the stage."""
        store = SQLiteStore(":memory:")
        stage, ast_a, ast_b = _make_stage_with_assertions("proj_cr007")
        initial_event_count = len(stage.events)
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        await cb_manage_conflict(
            action="create",
            ctx=ctx,
            assertion_a_id=ast_a.id,
            assertion_b_id=ast_b.id,
            topic_path="/architecture/database",
        )

        assert len(stage.events) == initial_event_count + 1


# ═══════════════════════════════════════════════════════════════
# Tests: action='propose_experiment'
# ═══════════════════════════════════════════════════════════════


class TestProposeExperimentAction:
    """Tests for action='propose_experiment'."""

    @pytest.mark.asyncio
    async def test_propose_experiment_without_protocol_returns_error(self) -> None:
        """propose_experiment without experiment_protocol returns an error."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_pe001")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="propose_experiment",
            ctx=ctx,
            conflict_id=cfl.id,
        )

        assert "ERROR" in result
        assert "experiment_protocol" in result

    @pytest.mark.asyncio
    async def test_propose_experiment_with_protocol_sets_experiment_status(self) -> None:
        """propose_experiment with a protocol sets conflict status to RESOLVED_EXPERIMENT."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_pe002")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))
        protocol = (
            "Run YCSB workload B (50% reads, 50% updates) on both datastores. "
            "If PostgreSQL p99 latency > 2x MongoDB's, MongoDB wins."
        )

        result = await cb_manage_conflict(
            action="propose_experiment",
            ctx=ctx,
            conflict_id=cfl.id,
            experiment_protocol=protocol,
        )

        assert "ERROR" not in result
        assert stage.conflicts[cfl.id].status == ConflictStatus.RESOLVED_EXPERIMENT

    @pytest.mark.asyncio
    async def test_propose_experiment_response_includes_protocol(self) -> None:
        """The response echoes the experiment protocol."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_pe003")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))
        protocol = "Measure write throughput at 10k concurrent connections for 1 hour."

        result = await cb_manage_conflict(
            action="propose_experiment",
            ctx=ctx,
            conflict_id=cfl.id,
            experiment_protocol=protocol,
        )

        assert protocol in result

    @pytest.mark.asyncio
    async def test_propose_experiment_without_conflict_id_returns_error(self) -> None:
        """propose_experiment without conflict_id returns an error."""
        store = SQLiteStore(":memory:")
        stage, _, _, _ = _make_stage_with_conflict("proj_pe004")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="propose_experiment",
            ctx=ctx,
            experiment_protocol="Some protocol.",
        )

        assert "ERROR" in result
        assert "conflict_id" in result

    @pytest.mark.asyncio
    async def test_propose_experiment_stores_protocol_on_conflict(self) -> None:
        """After propose_experiment, conflict.experiment_protocol is populated."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_pe005")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))
        protocol = "Deploy both in staging, run benchmark suite, compare p50/p95/p99."

        await cb_manage_conflict(
            action="propose_experiment",
            ctx=ctx,
            conflict_id=cfl.id,
            experiment_protocol=protocol,
        )

        assert stage.conflicts[cfl.id].experiment_protocol == protocol


# ═══════════════════════════════════════════════════════════════
# Tests: no active project
# ═══════════════════════════════════════════════════════════════


class TestNoActiveProject:
    """Tests for the no-active-project error path."""

    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        """All actions return an error when no project is active."""
        ctx = _make_ctx(active_stages={})

        result = await cb_manage_conflict(
            action="resolve",
            ctx=ctx,
            conflict_id="cfl_abc",
            resolution="accept",
        )

        assert "ERROR" in result
        assert "No active project" in result

    @pytest.mark.asyncio
    async def test_specified_project_not_active_returns_error(self) -> None:
        """Specifying a project_id that is not in active_stages returns an error."""
        store = SQLiteStore(":memory:")
        stage, cfl, _, _ = _make_stage_with_conflict("proj_other")
        ctx = _make_ctx(store=store, active_stages=_active_stages_for(stage))

        result = await cb_manage_conflict(
            action="defer",
            ctx=ctx,
            conflict_id=cfl.id,
            project_id="proj_does_not_exist",
        )

        assert "ERROR" in result
        assert "proj_does_not_exist" in result


# ═══════════════════════════════════════════════════════════════
# Tests: unknown action
# ═══════════════════════════════════════════════════════════════


class TestUnknownAction:
    """Tests for unknown action handling."""

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self) -> None:
        """An unknown action string returns an error."""
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_ua001", project_name="Unknown Action")
        ctx = _make_ctx(store=store, active_stages={"proj_ua001": stage})

        result = await cb_manage_conflict(
            action="destroy",
            ctx=ctx,
        )

        assert "ERROR" in result
        assert "destroy" in result

    @pytest.mark.asyncio
    async def test_unknown_action_lists_valid_actions(self) -> None:
        """The error for an unknown action lists all valid action names."""
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_ua002", project_name="Unknown Action")
        ctx = _make_ctx(store=store, active_stages={"proj_ua002": stage})

        result = await cb_manage_conflict(
            action="explode",
            ctx=ctx,
        )

        assert "resolve" in result
        assert "challenge" in result
        assert "defer" in result
        assert "create" in result
        assert "propose_experiment" in result
