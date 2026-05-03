"""Integration tests for the cb_decide tool.

Satisfies CLAUDE.md requirements:
- Event-log audit rule: every state mutation asserts the corresponding Event.
- Validator-rejection symmetry: anti-convergence gates tested both directions.
- Behavioral assertions over structural call-count assertions.
- No shared mutable state: fresh SQLiteStore + CompositionStage per test.

Blueprint reference: Section 6.1 (cb_decide tool spec), Section 3.6 (Decision model),
CLAUDE.md Phase 2 Quality Gate. Constitution rules C5, C8, G2.
"""

import pytest

from cognitive_bridge.models import (
    Assertion, AssertionAuthor, CompositionArc, CompositionStage, EventType,
)
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.decision_tool import cb_decide


class _MockCtx:
    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx(store: SQLiteStore | None = None, active_stages: dict | None = None) -> _MockCtx:
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


def _make_ctx_with_stage(project_id: str = "proj_decide_test") -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Decide Test Project")
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    return _make_ctx(store=store, active_stages=active_stages), stage, store


class TestDecideHappyPath:
    @pytest.mark.asyncio
    async def test_decision_recorded_in_stage(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database",
            decision="Use PostgreSQL as primary datastore",
            rationale="ACID guarantees and existing team expertise",
            alternatives_rejected="MongoDB — rejected because ACID needed | Redis — rejected because persistence model wrong",
            second_order_effects="Schema migrations required on every model change",
            ctx=ctx,
        )
        assert "ERROR" not in result
        assert len(stage.decisions) == 1
        assert stage.decisions[0].topic_path == "/architecture/database"

    @pytest.mark.asyncio
    async def test_decision_recorded_event_appended(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        initial = len(stage.events)
        await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Schema migrations required", ctx=ctx,
        )
        assert EventType.DECISION_RECORDED in [e.event_type for e in stage.events]
        assert len(stage.events) > initial

    @pytest.mark.asyncio
    async def test_decision_response_contains_id_and_path(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert "DECISION RECORDED" in result
        assert "/architecture/database" in result
        assert "PostgreSQL" in result

    @pytest.mark.asyncio
    async def test_multiple_alternatives_all_listed_in_response(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/cache", decision="Use Redis",
            rationale="Low latency requirement",
            alternatives_rejected="Memcached — rejected because no persistence | Varnish — rejected because HTTP-only",
            second_order_effects="Cache invalidation strategy required", ctx=ctx,
        )
        assert "Memcached" in result
        assert "Varnish" in result

    @pytest.mark.asyncio
    async def test_multiple_effects_create_inherits_assertions(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead | Backup strategy required | DBA expertise needed",
            ctx=ctx,
        )
        inherits_at_path = [
            a for a in stage.assertions.values()
            if a.arc == CompositionArc.INHERITS
            and a.topic_path == "/architecture/database"
            and "[Decision constraint]" in a.content
        ]
        assert len(inherits_at_path) == 3

    @pytest.mark.asyncio
    async def test_constraint_assertions_fire_assertion_created_events(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead | Backup strategy required", ctx=ctx,
        )
        ac_events = [e for e in stage.events if e.event_type == EventType.ASSERTION_CREATED]
        assert len(ac_events) == 2

    @pytest.mark.asyncio
    async def test_response_includes_constraint_assertion_ids(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead required", ctx=ctx,
        )
        assert "Constraint assertion:" in result

    @pytest.mark.asyncio
    async def test_reversibility_stored_on_decision(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead", reversibility="costly", ctx=ctx,
        )
        assert stage.decisions[0].reversibility == "costly"

    @pytest.mark.asyncio
    async def test_optional_assertion_ids_stored_on_decision(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead",
            assertion_ids="ast_abc123,ast_def456", ctx=ctx,
        )
        dec = stage.decisions[0]
        assert "ast_abc123" in dec.assertion_ids
        assert "ast_def456" in dec.assertion_ids

    @pytest.mark.asyncio
    async def test_optional_conflict_ids_stored_on_decision(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead",
            conflict_ids="cfl_aaa111,cfl_bbb222", ctx=ctx,
        )
        dec = stage.decisions[0]
        assert "cfl_aaa111" in dec.conflict_ids
        assert "cfl_bbb222" in dec.conflict_ids


class TestAntiConvergenceGates:
    @pytest.mark.asyncio
    async def test_empty_alternatives_rejected_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "alternatives_rejected" in result

    @pytest.mark.asyncio
    async def test_whitespace_only_alternatives_rejected_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="   |   ",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_empty_second_order_effects_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "second_order_effects" in result

    @pytest.mark.asyncio
    async def test_whitespace_only_effects_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="   |   ", ctx=ctx,
        )
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_no_decision_appended_when_alternatives_empty(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert len(stage.decisions) == 0

    @pytest.mark.asyncio
    async def test_no_decision_appended_when_effects_empty(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="", ctx=ctx,
        )
        assert len(stage.decisions) == 0


class TestPayloadWarning:
    @pytest.mark.asyncio
    async def test_payload_at_exact_path_triggers_warning(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        payload = Assertion(
            topic_path="/architecture/database",
            content="Benchmark data from last quarter not yet reviewed",
            arc=CompositionArc.PAYLOADS, author=AssertionAuthor.AI,
        )
        stage.assertions[payload.id] = payload
        save_stage_to_db(store, stage)
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert "WARNING" in result
        assert payload.id in result

    @pytest.mark.asyncio
    async def test_payload_at_subtree_path_triggers_warning(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        payload = Assertion(
            topic_path="/architecture/database/replication",
            content="Replication lag data not reviewed",
            arc=CompositionArc.PAYLOADS, author=AssertionAuthor.AI,
        )
        stage.assertions[payload.id] = payload
        save_stage_to_db(store, stage)
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert "WARNING" in result

    @pytest.mark.asyncio
    async def test_no_payload_no_warning(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert "WARNING" not in result

    @pytest.mark.asyncio
    async def test_inactive_payload_does_not_trigger_warning(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        payload = Assertion(
            topic_path="/architecture/database",
            content="Old benchmark data",
            arc=CompositionArc.PAYLOADS, author=AssertionAuthor.AI, active=False,
        )
        stage.assertions[payload.id] = payload
        save_stage_to_db(store, stage)
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert "WARNING" not in result

    @pytest.mark.asyncio
    async def test_payload_at_unrelated_path_does_not_trigger_warning(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        payload = Assertion(
            topic_path="/compliance/gdpr",
            content="GDPR assessment pending",
            arc=CompositionArc.PAYLOADS, author=AssertionAuthor.AI,
        )
        stage.assertions[payload.id] = payload
        save_stage_to_db(store, stage)
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert "WARNING" not in result


class TestErrorConditions:
    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        ctx = _make_ctx()
        result = await cb_decide(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID", alternatives_rejected="MongoDB — no ACID",
            second_order_effects="Migration overhead", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "active project" in result.lower() or "No active" in result
