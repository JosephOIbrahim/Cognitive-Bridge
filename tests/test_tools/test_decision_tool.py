"""Integration tests for the cb_decide tool.

Tests call the tool handler directly using a minimal mock Context whose
lifespan_context carries an in-memory SQLiteStore and an isolated
active_stages dict. This avoids MCP transport overhead while exercising
every action branch, validation gate, and response formatting path.

No shared mutable state: every test builds its own store + stage.
"""

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    EventType,
)
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.decision_tool import cb_decide


# ═══════════════════════════════════════════════════════════════
# Mock Context
# ═══════════════════════════════════════════════════════════════


class _MockCtx:
    """Minimal context mock that satisfies ctx.lifespan_context access."""

    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {
            "store": store,
            "active_stages": active_stages,
        }


def _make_ctx_with_stage(
    project_id: str = "proj_test",
) -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    """Create a context, stage, and store pre-wired together."""
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Test Project")
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    ctx = _MockCtx(store=store, active_stages=active_stages)
    return ctx, stage, store


def _make_empty_ctx() -> _MockCtx:
    """Create a context with no active projects."""
    store = SQLiteStore(":memory:")
    return _MockCtx(store=store, active_stages={})


# ═══════════════════════════════════════════════════════════════
# Test: basic happy path
# ═══════════════════════════════════════════════════════════════


class TestBasicDecide:
    """Tests for the core happy-path behavior."""

    @pytest.mark.asyncio
    async def test_basic_decision_success(self) -> None:
        """A complete decision call returns a response containing the decision ID."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL as the primary datastore",
            rationale="ACID guarantees required for financial transactions",
            alternatives_rejected="MongoDB — rejected because no multi-document ACID | Redis — rejected because persistence model wrong",
            second_order_effects="Schema migrations required on every model change",
            ctx=ctx,
        )
        assert "DECISION RECORDED" in result
        assert "dec_" in result  # decision ID appears somewhere
        assert "/architecture/database" in result

    @pytest.mark.asyncio
    async def test_response_contains_decision_text(self) -> None:
        """Response includes the decision text and rationale."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migrations needed",
            ctx=ctx,
        )
        assert "Use PostgreSQL" in result
        assert "ACID required" in result

    @pytest.mark.asyncio
    async def test_reversibility_stored_and_shown(self) -> None:
        """Reversibility value appears in the response."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migrations needed",
            reversibility="costly",
            ctx=ctx,
        )
        assert "costly" in result
        # Also verify it was stored in the decision object
        assert len(stage.decisions) == 1
        assert stage.decisions[0].reversibility == "costly"


# ═══════════════════════════════════════════════════════════════
# Test: validation gates
# ═══════════════════════════════════════════════════════════════


class TestValidationGates:
    """Tests that confirm hard gates reject invalid inputs."""

    @pytest.mark.asyncio
    async def test_empty_alternatives_returns_error(self) -> None:
        """Whitespace-only alternatives_rejected returns an ERROR response."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="   ",  # only whitespace
            second_order_effects="Migrations needed",
            ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "alternatives_rejected" in result

    @pytest.mark.asyncio
    async def test_empty_effects_returns_error(self) -> None:
        """Whitespace-only second_order_effects returns an ERROR response."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="   ",  # only whitespace
            ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "second_order_effects" in result

    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        """Calling without an active project returns an ERROR."""
        ctx = _make_empty_ctx()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migrations needed",
            ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "No active project" in result


# ═══════════════════════════════════════════════════════════════
# Test: pipe-separated parsing
# ═══════════════════════════════════════════════════════════════


class TestParsing:
    """Tests for pipe-separated list parsing."""

    @pytest.mark.asyncio
    async def test_two_alternatives_parsed_correctly(self) -> None:
        """Pipe-separated alternatives produce two items in the decision."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID | Redis — wrong persistence",
            second_order_effects="Migrations needed",
            ctx=ctx,
        )
        assert len(stage.decisions) == 1
        dec = stage.decisions[0]
        assert len(dec.alternatives_rejected) == 2
        assert "MongoDB — no ACID" in dec.alternatives_rejected
        assert "Redis — wrong persistence" in dec.alternatives_rejected

    @pytest.mark.asyncio
    async def test_two_effects_parsed_correctly(self) -> None:
        """Pipe-separated effects produce two items in the decision."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required | Horizontal scaling needs sharding",
            ctx=ctx,
        )
        assert len(stage.decisions) == 1
        dec = stage.decisions[0]
        assert len(dec.second_order_effects) == 2

    @pytest.mark.asyncio
    async def test_extra_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace around pipe delimiters is stripped."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="  MongoDB — no ACID  |  Redis — wrong model  ",
            second_order_effects="Migrations needed",
            ctx=ctx,
        )
        dec = stage.decisions[0]
        assert dec.alternatives_rejected[0] == "MongoDB — no ACID"
        assert dec.alternatives_rejected[1] == "Redis — wrong model"


# ═══════════════════════════════════════════════════════════════
# Test: auto-constraint creation
# ═══════════════════════════════════════════════════════════════


class TestConstraintCreation:
    """Tests that second_order_effects create INHERITS assertions."""

    @pytest.mark.asyncio
    async def test_single_effect_creates_one_constraint(self) -> None:
        """One second_order_effect creates exactly one INHERITS assertion."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        constraints = [
            a for a in stage.assertions.values()
            if a.arc == CompositionArc.INHERITS and "decision_constraint" in a.tags
        ]
        assert len(constraints) == 1

    @pytest.mark.asyncio
    async def test_two_effects_create_two_constraints(self) -> None:
        """Two second_order_effects create exactly two INHERITS assertions."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required | Sharding strategy needed",
            ctx=ctx,
        )
        constraints = [
            a for a in stage.assertions.values()
            if a.arc == CompositionArc.INHERITS and "decision_constraint" in a.tags
        ]
        assert len(constraints) == 2

    @pytest.mark.asyncio
    async def test_constraint_assertions_have_correct_tags(self) -> None:
        """Constraint assertions carry both 'decision_constraint' tag and the decision ID."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        dec = stage.decisions[0]
        constraints = [
            a for a in stage.assertions.values()
            if "decision_constraint" in a.tags
        ]
        assert len(constraints) == 1
        assert dec.id in constraints[0].tags

    @pytest.mark.asyncio
    async def test_constraint_arc_is_inherits(self) -> None:
        """Auto-created constraints use the INHERITS arc."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        constraints = [
            a for a in stage.assertions.values()
            if "decision_constraint" in a.tags
        ]
        assert all(c.arc == CompositionArc.INHERITS for c in constraints)

    @pytest.mark.asyncio
    async def test_constraint_author_is_system(self) -> None:
        """Auto-created constraints have SYSTEM as author."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        constraints = [
            a for a in stage.assertions.values()
            if "decision_constraint" in a.tags
        ]
        assert all(c.author == AssertionAuthor.SYSTEM for c in constraints)

    @pytest.mark.asyncio
    async def test_constraint_content_includes_effect_text(self) -> None:
        """Constraint content wraps the effect text with a prefix."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required on every model change",
            ctx=ctx,
        )
        constraints = [
            a for a in stage.assertions.values()
            if "decision_constraint" in a.tags
        ]
        assert "Schema migrations required on every model change" in constraints[0].content


# ═══════════════════════════════════════════════════════════════
# Test: event log
# ═══════════════════════════════════════════════════════════════


class TestEventLog:
    """Tests that the correct events are appended to the stage."""

    @pytest.mark.asyncio
    async def test_decision_recorded_event_appended(self) -> None:
        """A DECISION_RECORDED event is added to the stage event log."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        event_types = [e.event_type for e in stage.events]
        assert EventType.DECISION_RECORDED in event_types

    @pytest.mark.asyncio
    async def test_assertion_created_event_per_constraint(self) -> None:
        """One ASSERTION_CREATED event is appended for each second_order_effect."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Effect one | Effect two",
            ctx=ctx,
        )
        created_events = [
            e for e in stage.events if e.event_type == EventType.ASSERTION_CREATED
        ]
        assert len(created_events) == 2

    @pytest.mark.asyncio
    async def test_total_events_for_two_effects(self) -> None:
        """Two effects produce 1 DECISION_RECORDED + 2 ASSERTION_CREATED = 3 events."""
        ctx, stage, store = _make_ctx_with_stage()
        initial_event_count = len(stage.events)
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Effect one | Effect two",
            ctx=ctx,
        )
        new_events = stage.events[initial_event_count:]
        assert len(new_events) == 3  # 1 DECISION_RECORDED + 2 ASSERTION_CREATED


# ═══════════════════════════════════════════════════════════════
# Test: payload warning
# ═══════════════════════════════════════════════════════════════


class TestPayloadWarning:
    """Tests for the pending payload warning behavior."""

    @pytest.mark.asyncio
    async def test_payload_warning_when_payloads_exist(self) -> None:
        """When PAYLOADS assertions exist at the path, response contains a warning."""
        ctx, stage, store = _make_ctx_with_stage()
        # Add a PAYLOADS-arc assertion at the same path
        payload_assertion = Assertion(
            topic_path="/architecture/database",
            content="Known unknown: performance benchmarks not yet run",
            arc=CompositionArc.PAYLOADS,
            author=AssertionAuthor.USER,
        )
        stage.assertions[payload_assertion.id] = payload_assertion

        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        assert "WARNING" in result
        assert "payload" in result.lower()

    @pytest.mark.asyncio
    async def test_no_payload_warning_when_none_exist(self) -> None:
        """When no PAYLOADS assertions exist at the path, response has no warning."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        assert "WARNING" not in result

    @pytest.mark.asyncio
    async def test_payload_warning_for_child_path(self) -> None:
        """PAYLOADS at a child path of the decision path also trigger a warning."""
        ctx, stage, store = _make_ctx_with_stage()
        payload_assertion = Assertion(
            topic_path="/architecture/database/engine",  # child of /architecture/database
            content="Benchmark data pending",
            arc=CompositionArc.PAYLOADS,
            author=AssertionAuthor.USER,
        )
        stage.assertions[payload_assertion.id] = payload_assertion

        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        assert "WARNING" in result

    @pytest.mark.asyncio
    async def test_payload_at_unrelated_path_no_warning(self) -> None:
        """PAYLOADS at an unrelated path do NOT trigger a warning."""
        ctx, stage, store = _make_ctx_with_stage()
        payload_assertion = Assertion(
            topic_path="/infrastructure/networking",  # unrelated path
            content="Network topology unknown",
            arc=CompositionArc.PAYLOADS,
            author=AssertionAuthor.USER,
        )
        stage.assertions[payload_assertion.id] = payload_assertion

        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )
        assert "WARNING" not in result


# ═══════════════════════════════════════════════════════════════
# Test: linked IDs
# ═══════════════════════════════════════════════════════════════


class TestLinkedIds:
    """Tests that assertion_ids and conflict_ids are stored correctly."""

    @pytest.mark.asyncio
    async def test_assertion_ids_stored(self) -> None:
        """Comma-separated assertion_ids are stored in the decision."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migrations needed",
            assertion_ids="ast_aaa111, ast_bbb222",
            ctx=ctx,
        )
        dec = stage.decisions[0]
        assert "ast_aaa111" in dec.assertion_ids
        assert "ast_bbb222" in dec.assertion_ids

    @pytest.mark.asyncio
    async def test_conflict_ids_stored(self) -> None:
        """Comma-separated conflict_ids are stored in the decision."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migrations needed",
            conflict_ids="cfl_ccc333, cfl_ddd444",
            ctx=ctx,
        )
        dec = stage.decisions[0]
        assert "cfl_ccc333" in dec.conflict_ids
        assert "cfl_ddd444" in dec.conflict_ids

    @pytest.mark.asyncio
    async def test_no_assertion_ids_defaults_to_empty_list(self) -> None:
        """When assertion_ids is omitted, stored decision has empty list."""
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migrations needed",
            ctx=ctx,
        )
        dec = stage.decisions[0]
        assert dec.assertion_ids == []

    @pytest.mark.asyncio
    async def test_assertion_ids_shown_in_response(self) -> None:
        """Linked assertion IDs appear in the tool response."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migrations needed",
            assertion_ids="ast_aaa111",
            ctx=ctx,
        )
        assert "ast_aaa111" in result


# ═══════════════════════════════════════════════════════════════
# Test: persistence round-trip
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """Tests that the stage is correctly saved after a decision."""

    @pytest.mark.asyncio
    async def test_decision_survives_save_load_roundtrip(self) -> None:
        """Decision and its constraint assertions survive a DB save/load cycle."""
        from cognitive_bridge.server import save_stage_to_db
        from cognitive_bridge.storage.sqlite_store import SQLiteStore
        from cognitive_bridge.storage.converters import row_to_decision, row_to_assertion
        from cognitive_bridge.storage.sqlite_store import DecisionRow, AssertionRow
        from sqlmodel import select

        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required",
            ctx=ctx,
        )

        dec_before = stage.decisions[0]
        dec_id = dec_before.id

        # Reload from DB
        with store.get_session() as session:
            dec_rows = session.exec(select(DecisionRow)).all()
            ast_rows = session.exec(select(AssertionRow)).all()

        dec_ids_in_db = [r.id for r in dec_rows]
        assert dec_id in dec_ids_in_db

        # At least one constraint assertion was persisted
        constraint_ids = [
            a.id for a in stage.assertions.values()
            if "decision_constraint" in a.tags
        ]
        ast_ids_in_db = [r.id for r in ast_rows]
        for cid in constraint_ids:
            assert cid in ast_ids_in_db

    @pytest.mark.asyncio
    async def test_stage_decisions_list_updated(self) -> None:
        """After cb_decide, stage.decisions contains exactly one entry."""
        ctx, stage, store = _make_ctx_with_stage()
        assert len(stage.decisions) == 0

        await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL",
            rationale="ACID required",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migrations needed",
            ctx=ctx,
        )
        assert len(stage.decisions) == 1
