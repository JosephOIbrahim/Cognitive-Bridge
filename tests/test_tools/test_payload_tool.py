"""Integration tests for the cb_payload_check tool.

Blueprint reference: Section 6.1 (cb_payload_check), PAYLOADS arc as known unknowns.
Constitution rules G4 (behavioral over structural), G5 (test isolation).

cb_payload_check is read-only (readOnlyHint=True): no events appended, no mutations.
"""

import pytest

from cognitive_bridge.models import (
    Assertion, AssertionAuthor, CompositionArc, CompositionStage, Decision, EventType,
)
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.payload_tool import cb_payload_check


class _MockCtx:
    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx(store: SQLiteStore | None = None, active_stages: dict | None = None) -> _MockCtx:
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


def _make_ctx_with_stage(project_id: str = "proj_payload_test") -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Payload Test Project")
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    return _make_ctx(store=store, active_stages=active_stages), stage, store


def _add_payload(
    stage: CompositionStage, store: SQLiteStore,
    topic_path: str, content: str = "Pending evidence", active: bool = True,
) -> Assertion:
    payload = Assertion(
        topic_path=topic_path, content=content,
        arc=CompositionArc.PAYLOADS, author=AssertionAuthor.AI, active=active,
    )
    stage.assertions[payload.id] = payload
    save_stage_to_db(store, stage)
    return payload


class TestNoPayloads:
    @pytest.mark.asyncio
    async def test_no_payloads_returns_safe_message(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_payload_check(ctx=ctx)
        assert "no pending payloads" in result.lower() or "No pending payloads" in result

    @pytest.mark.asyncio
    async def test_no_payloads_at_path_returns_safe_message(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_payload_check(topic_path="/architecture/database", ctx=ctx)
        assert "no pending payloads" in result.lower() or "No pending payloads" in result
        assert "/architecture/database" in result

    @pytest.mark.asyncio
    async def test_non_payloads_assertion_not_surfaced(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        a = Assertion(
            topic_path="/architecture/database", content="PostgreSQL chosen",
            arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
        )
        stage.assertions[a.id] = a
        save_stage_to_db(store, stage)
        result = await cb_payload_check(topic_path="/architecture/database", ctx=ctx)
        assert "PENDING PAYLOADS" not in result

    @pytest.mark.asyncio
    async def test_no_event_appended_for_read_only_check(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        initial = len(stage.events)
        await cb_payload_check(ctx=ctx)
        assert len(stage.events) == initial


class TestPayloadsPresent:
    @pytest.mark.asyncio
    async def test_payload_at_exact_path_surfaced(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        payload = _add_payload(stage, store, "/architecture/database", "Benchmark data not yet reviewed")
        result = await cb_payload_check(topic_path="/architecture/database", ctx=ctx)
        assert "PENDING PAYLOADS" in result
        assert payload.id in result
        assert "Benchmark data not yet reviewed" in result

    @pytest.mark.asyncio
    async def test_payload_count_shown_in_response(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        _add_payload(stage, store, "/architecture/database", "Evidence A")
        _add_payload(stage, store, "/architecture/cache", "Evidence B")
        result = await cb_payload_check(ctx=ctx)
        assert "PENDING PAYLOADS (2)" in result

    @pytest.mark.asyncio
    async def test_payload_content_shown_in_response(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        _add_payload(stage, store, "/architecture/database", "GDPR audit results available but not loaded")
        result = await cb_payload_check(ctx=ctx)
        assert "GDPR audit results available but not loaded" in result

    @pytest.mark.asyncio
    async def test_multiple_payloads_all_listed(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        p1 = _add_payload(stage, store, "/arch/db", "DB benchmark")
        p2 = _add_payload(stage, store, "/arch/cache", "Cache benchmark")
        p3 = _add_payload(stage, store, "/compliance/gdpr", "GDPR audit")
        result = await cb_payload_check(ctx=ctx)
        assert p1.id in result
        assert p2.id in result
        assert p3.id in result


class TestSubtreeFiltering:
    @pytest.mark.asyncio
    async def test_subtree_payload_surfaced_when_checking_parent(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        deep = _add_payload(stage, store, "/architecture/database/replication", "Replication lag study pending")
        result = await cb_payload_check(topic_path="/architecture", ctx=ctx)
        assert deep.id in result

    @pytest.mark.asyncio
    async def test_unrelated_path_payload_not_surfaced(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        unrelated = _add_payload(stage, store, "/compliance/gdpr", "GDPR audit pending")
        arch = _add_payload(stage, store, "/architecture/database", "DB benchmark pending")
        result = await cb_payload_check(topic_path="/architecture", ctx=ctx)
        assert arch.id in result
        assert unrelated.id not in result

    @pytest.mark.asyncio
    async def test_no_topic_path_returns_all_payloads(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        p1 = _add_payload(stage, store, "/architecture/database", "DB evidence")
        p2 = _add_payload(stage, store, "/compliance/gdpr", "GDPR evidence")
        result = await cb_payload_check(ctx=ctx)
        assert p1.id in result
        assert p2.id in result

    @pytest.mark.asyncio
    async def test_exact_path_match_does_not_surface_sibling(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        sibling = _add_payload(stage, store, "/architecture/cache", "Cache evidence")
        target = _add_payload(stage, store, "/architecture/database", "DB evidence")
        result = await cb_payload_check(topic_path="/architecture/database", ctx=ctx)
        assert target.id in result
        assert sibling.id not in result

    @pytest.mark.asyncio
    async def test_partial_segment_prefix_does_not_surface(self) -> None:
        """A check at '/arch' must NOT surface '/architecture/...'.

        '/arch' is a distinct path segment, not an ancestor of '/architecture'.
        Regression guard for the segment-aware match (raw str.startswith would
        wrongly match here).
        """
        ctx, stage, store = _make_ctx_with_stage()
        arch = _add_payload(stage, store, "/architecture/database", "DB evidence")
        result = await cb_payload_check(topic_path="/arch", ctx=ctx)
        assert arch.id not in result
        assert "no pending payloads" in result.lower()


class TestInactivePayloadsExcluded:
    @pytest.mark.asyncio
    async def test_inactive_payload_not_surfaced(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        _add_payload(stage, store, "/architecture/database", "Old benchmark data", active=False)
        result = await cb_payload_check(ctx=ctx)
        assert "PENDING PAYLOADS" not in result

    @pytest.mark.asyncio
    async def test_mix_active_and_inactive_only_active_surfaced(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        active_p = _add_payload(stage, store, "/architecture/database", "Active evidence", active=True)
        inactive_p = _add_payload(stage, store, "/architecture/cache", "Old evidence", active=False)
        result = await cb_payload_check(ctx=ctx)
        assert active_p.id in result
        assert inactive_p.id not in result


class TestPayloadSurfacingParameter:
    @pytest.mark.asyncio
    async def test_payloads_surfaced_when_payload_surfacing_disabled(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        stage.parameters.payload_surfacing = False
        save_stage_to_db(store, stage)
        payload = _add_payload(stage, store, "/architecture/database", "Benchmark data pending")
        result = await cb_payload_check(topic_path="/architecture/database", ctx=ctx)
        assert payload.id in result
        assert "PENDING PAYLOADS" in result


class TestDecisionOverlapWarning:
    @pytest.mark.asyncio
    async def test_decision_at_payload_path_triggers_warning(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        _add_payload(stage, store, "/architecture/database", "Evidence pending")
        dec = Decision(
            topic_path="/architecture/database", decision="Use PostgreSQL",
            rationale="ACID guarantees",
            alternatives_rejected=["MongoDB — no ACID"],
            second_order_effects=["Migration overhead"],
        )
        stage.decisions.append(dec)
        save_stage_to_db(store, stage)
        result = await cb_payload_check(topic_path="/architecture/database", ctx=ctx)
        assert "WARNING" in result
        assert dec.id in result

    @pytest.mark.asyncio
    async def test_decision_at_unrelated_path_no_overlap_warning(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        _add_payload(stage, store, "/architecture/database", "Evidence pending")
        dec = Decision(
            topic_path="/compliance/gdpr", decision="GDPR compliant",
            rationale="Audit passed",
            alternatives_rejected=["Non-compliance — unacceptable"],
            second_order_effects=["Annual audit required"],
        )
        stage.decisions.append(dec)
        save_stage_to_db(store, stage)
        result = await cb_payload_check(topic_path="/architecture/database", ctx=ctx)
        assert dec.id not in result

    @pytest.mark.asyncio
    async def test_parent_path_decision_overlaps_with_child_payload(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        _add_payload(stage, store, "/architecture/database", "DB evidence pending")
        dec = Decision(
            topic_path="/architecture", decision="Microservices architecture",
            rationale="Scalability requirements",
            alternatives_rejected=["Monolith — rejected because scaling limits"],
            second_order_effects=["Service discovery required"],
        )
        stage.decisions.append(dec)
        save_stage_to_db(store, stage)
        result = await cb_payload_check(ctx=ctx)
        assert "WARNING" in result
        assert dec.id in result

    @pytest.mark.asyncio
    async def test_partial_segment_decision_does_not_trigger_warning(self) -> None:
        """A decision at '/arch' must not be flagged against a '/architecture/...'
        payload — distinct segments, no tree overlap. Regression guard for the
        segment-aware overlap check.
        """
        ctx, stage, store = _make_ctx_with_stage()
        _add_payload(stage, store, "/architecture/database", "Evidence pending")
        dec = Decision(
            topic_path="/arch", decision="Some unrelated arch decision",
            rationale="reasons",
            alternatives_rejected=["alt — rejected"],
            second_order_effects=["some effect"],
        )
        stage.decisions.append(dec)
        save_stage_to_db(store, stage)
        result = await cb_payload_check(ctx=ctx)
        assert "PENDING PAYLOADS" in result
        assert dec.id not in result


class TestErrorConditions:
    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        ctx = _make_ctx()
        result = await cb_payload_check(ctx=ctx)
        assert result.startswith("ERROR:")
