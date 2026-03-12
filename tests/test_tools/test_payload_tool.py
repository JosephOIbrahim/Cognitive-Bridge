"""Integration tests for the cb_payload_check tool.

Tests call the tool handler directly using a minimal mock Context whose
lifespan_context carries an in-memory SQLiteStore and an isolated
active_stages dict. This avoids MCP transport overhead while exercising
every branch, filter path, and response formatting path.

No shared mutable state: every test builds its own store + stage.
"""

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    Decision,
)
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.payload_tool import cb_payload_check


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


def _add_assertion(
    stage: CompositionStage,
    topic_path: str,
    content: str,
    arc: CompositionArc,
    evidence: list[str] | None = None,
    tags: list[str] | None = None,
) -> Assertion:
    """Add an assertion directly to the stage for test setup."""
    a = Assertion(
        topic_path=topic_path,
        content=content,
        arc=arc,
        author=AssertionAuthor.USER,
        evidence=evidence or [],
        tags=tags or [],
    )
    stage.assertions[a.id] = a
    return a


def _add_decision(
    stage: CompositionStage,
    topic_path: str,
    decision_text: str = "Use PostgreSQL",
) -> Decision:
    """Add a decision directly to the stage for test setup."""
    d = Decision(
        topic_path=topic_path,
        decision=decision_text,
        rationale="ACID required",
        alternatives_rejected=["MongoDB — no ACID"],
        second_order_effects=["Migrations needed"],
    )
    stage.decisions.append(d)
    return d


# ═══════════════════════════════════════════════════════════════
# Test: no payloads
# ═══════════════════════════════════════════════════════════════


class TestNoPayloads:
    """Tests for the empty / no-payload cases."""

    @pytest.mark.asyncio
    async def test_no_payloads_anywhere(self) -> None:
        """When the stage has no PAYLOADS assertions, response says safe to proceed."""
        ctx, stage, _ = _make_ctx_with_stage()
        result = await cb_payload_check(ctx=ctx)
        assert "No pending payloads" in result
        assert "Safe to proceed" in result
        assert "in the project" in result

    @pytest.mark.asyncio
    async def test_no_payloads_at_path(self) -> None:
        """Payloads at /other do not appear when checking /db."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/other/service", "Some payload", CompositionArc.PAYLOADS)

        result = await cb_payload_check(ctx=ctx, topic_path="/db")
        assert "No pending payloads" in result
        assert "/db" in result
        assert "Safe to proceed" in result

    @pytest.mark.asyncio
    async def test_no_payloads_message_contains_path(self) -> None:
        """The 'no payloads' message mentions the requested path."""
        ctx, stage, _ = _make_ctx_with_stage()
        result = await cb_payload_check(ctx=ctx, topic_path="/architecture/database")
        assert "'/architecture/database'" in result


# ═══════════════════════════════════════════════════════════════
# Test: payloads found
# ═══════════════════════════════════════════════════════════════


class TestPayloadsFound:
    """Tests for when payloads are present and should be surfaced."""

    @pytest.mark.asyncio
    async def test_payload_found_at_path(self) -> None:
        """A PAYLOADS assertion at /db/engine appears when checking /db."""
        ctx, stage, _ = _make_ctx_with_stage()
        ast = _add_assertion(
            stage, "/db/engine", "Benchmark results pending", CompositionArc.PAYLOADS
        )

        result = await cb_payload_check(ctx=ctx, topic_path="/db")
        assert "PENDING PAYLOADS" in result
        assert ast.id in result
        assert "/db/engine" in result
        assert "Benchmark results pending" in result

    @pytest.mark.asyncio
    async def test_all_payloads_no_filter(self) -> None:
        """With no topic_path filter, all active PAYLOADS assertions are shown."""
        ctx, stage, _ = _make_ctx_with_stage()
        a1 = _add_assertion(stage, "/api/auth", "Auth perf data pending", CompositionArc.PAYLOADS)
        a2 = _add_assertion(stage, "/db/engine", "DB bench pending", CompositionArc.PAYLOADS)

        result = await cb_payload_check(ctx=ctx)
        assert "PENDING PAYLOADS (2)" in result
        assert a1.id in result
        assert a2.id in result

    @pytest.mark.asyncio
    async def test_count_in_header(self) -> None:
        """Header shows the exact count of payloads found."""
        ctx, stage, _ = _make_ctx_with_stage()
        for i in range(3):
            _add_assertion(
                stage,
                f"/path/item{i}",
                f"Payload {i}",
                CompositionArc.PAYLOADS,
            )

        result = await cb_payload_check(ctx=ctx)
        assert "PENDING PAYLOADS (3)" in result


# ═══════════════════════════════════════════════════════════════
# Test: path filtering
# ═══════════════════════════════════════════════════════════════


class TestPathFiltering:
    """Tests for the prefix-match path filter."""

    @pytest.mark.asyncio
    async def test_path_filter_excludes_other_subtree(self) -> None:
        """Payloads at /api/auth are excluded when checking /db."""
        ctx, stage, _ = _make_ctx_with_stage()
        db_ast = _add_assertion(stage, "/db/engine", "DB payload", CompositionArc.PAYLOADS)
        _add_assertion(stage, "/api/auth", "API payload", CompositionArc.PAYLOADS)

        result = await cb_payload_check(ctx=ctx, topic_path="/db")
        assert db_ast.id in result
        assert "/api/auth" not in result

    @pytest.mark.asyncio
    async def test_path_filter_includes_nested_paths(self) -> None:
        """Checking /architecture also surfaces /architecture/database/engine."""
        ctx, stage, _ = _make_ctx_with_stage()
        nested = _add_assertion(
            stage,
            "/architecture/database/engine",
            "Deep payload",
            CompositionArc.PAYLOADS,
        )

        result = await cb_payload_check(ctx=ctx, topic_path="/architecture")
        assert nested.id in result
        assert "/architecture/database/engine" in result

    @pytest.mark.asyncio
    async def test_path_filter_exact_match_included(self) -> None:
        """A payload whose path exactly equals topic_path is included."""
        ctx, stage, _ = _make_ctx_with_stage()
        ast = _add_assertion(stage, "/db/engine", "Exact match", CompositionArc.PAYLOADS)

        result = await cb_payload_check(ctx=ctx, topic_path="/db/engine")
        assert ast.id in result


# ═══════════════════════════════════════════════════════════════
# Test: payload details in response
# ═══════════════════════════════════════════════════════════════


class TestPayloadDetails:
    """Tests that evidence hints and tags appear in the response."""

    @pytest.mark.asyncio
    async def test_evidence_hints_shown(self) -> None:
        """Evidence field values appear under the payload entry."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(
            stage,
            "/db/engine",
            "Bench pending",
            CompositionArc.PAYLOADS,
            evidence=["pgbench_results.csv", "flamegraph.svg"],
        )

        result = await cb_payload_check(ctx=ctx)
        assert "Evidence hints" in result
        assert "pgbench_results.csv" in result
        assert "flamegraph.svg" in result

    @pytest.mark.asyncio
    async def test_tags_shown(self) -> None:
        """Tags appear under the payload entry."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(
            stage,
            "/db/engine",
            "Bench pending",
            CompositionArc.PAYLOADS,
            tags=["performance", "blocking"],
        )

        result = await cb_payload_check(ctx=ctx)
        assert "Tags" in result
        assert "performance" in result
        assert "blocking" in result

    @pytest.mark.asyncio
    async def test_no_evidence_no_evidence_line(self) -> None:
        """When a payload has no evidence, the 'Evidence hints' line is absent."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "Bench pending", CompositionArc.PAYLOADS)

        result = await cb_payload_check(ctx=ctx)
        assert "Evidence hints" not in result

    @pytest.mark.asyncio
    async def test_no_tags_no_tags_line(self) -> None:
        """When a payload has no tags, the 'Tags' line is absent."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "Bench pending", CompositionArc.PAYLOADS)

        result = await cb_payload_check(ctx=ctx)
        assert "Tags:" not in result


# ═══════════════════════════════════════════════════════════════
# Test: read-only — stage unchanged
# ═══════════════════════════════════════════════════════════════


class TestReadOnly:
    """Verify the tool does not modify the stage."""

    @pytest.mark.asyncio
    async def test_stage_unchanged_after_call(self) -> None:
        """The stage's assertion count and event log are identical before and after."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "Bench pending", CompositionArc.PAYLOADS)

        assertion_count_before = len(stage.assertions)
        event_count_before = len(stage.events)
        decision_count_before = len(stage.decisions)

        await cb_payload_check(ctx=ctx)

        assert len(stage.assertions) == assertion_count_before
        assert len(stage.events) == event_count_before
        assert len(stage.decisions) == decision_count_before


# ═══════════════════════════════════════════════════════════════
# Test: decisions overlap warning
# ═══════════════════════════════════════════════════════════════


class TestDecisionsOverlap:
    """Tests for the decision/payload overlap warning block."""

    @pytest.mark.asyncio
    async def test_decisions_overlap_warning_shown(self) -> None:
        """A decision at /db plus a payload at /db/engine triggers WARNING."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "Bench pending", CompositionArc.PAYLOADS)
        d = _add_decision(stage, "/db")

        result = await cb_payload_check(ctx=ctx)
        assert "WARNING" in result
        assert d.id in result

    @pytest.mark.asyncio
    async def test_decisions_overlap_shows_count(self) -> None:
        """The WARNING line shows the number of at-risk decisions."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "Payload", CompositionArc.PAYLOADS)
        _add_decision(stage, "/db", "Use PostgreSQL")
        _add_decision(stage, "/db/engine", "Use InnoDB")

        result = await cb_payload_check(ctx=ctx)
        assert "2 decision(s)" in result

    @pytest.mark.asyncio
    async def test_no_decisions_no_warning(self) -> None:
        """When no decisions exist, no WARNING block appears."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "Bench pending", CompositionArc.PAYLOADS)

        result = await cb_payload_check(ctx=ctx)
        assert "WARNING" not in result

    @pytest.mark.asyncio
    async def test_decisions_at_unrelated_path_no_warning(self) -> None:
        """A decision at /api does not trigger WARNING for a payload at /db."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "Bench pending", CompositionArc.PAYLOADS)
        _add_decision(stage, "/api")

        result = await cb_payload_check(ctx=ctx)
        assert "WARNING" not in result

    @pytest.mark.asyncio
    async def test_payload_is_ancestor_of_decision_triggers_warning(self) -> None:
        """Payload at /db triggers WARNING when decision is at /db/engine (payload is prefix of decision)."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db", "Top-level DB payload", CompositionArc.PAYLOADS)
        d = _add_decision(stage, "/db/engine")

        result = await cb_payload_check(ctx=ctx)
        assert "WARNING" in result
        assert d.id in result


# ═══════════════════════════════════════════════════════════════
# Test: sorted output
# ═══════════════════════════════════════════════════════════════


class TestSortedOutput:
    """Tests that payloads are sorted alphabetically by path."""

    @pytest.mark.asyncio
    async def test_sorted_by_path(self) -> None:
        """Multiple payloads appear in alphabetical path order in the response."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/z/last", "Z payload", CompositionArc.PAYLOADS)
        _add_assertion(stage, "/a/first", "A payload", CompositionArc.PAYLOADS)
        _add_assertion(stage, "/m/middle", "M payload", CompositionArc.PAYLOADS)

        result = await cb_payload_check(ctx=ctx)
        idx_a = result.index("/a/first")
        idx_m = result.index("/m/middle")
        idx_z = result.index("/z/last")
        assert idx_a < idx_m < idx_z


# ═══════════════════════════════════════════════════════════════
# Test: error cases
# ═══════════════════════════════════════════════════════════════


class TestErrorCases:
    """Tests for error responses."""

    @pytest.mark.asyncio
    async def test_no_active_project(self) -> None:
        """With no active projects, returns an ERROR message."""
        ctx = _make_empty_ctx()
        result = await cb_payload_check(ctx=ctx)
        assert result.startswith("ERROR:")
        assert "No active project" in result

    @pytest.mark.asyncio
    async def test_named_project_not_active(self) -> None:
        """Requesting a project that is not active returns an ERROR."""
        ctx, _, _ = _make_ctx_with_stage("proj_alpha")
        result = await cb_payload_check(ctx=ctx, project_id="proj_beta")
        assert result.startswith("ERROR:")
        assert "proj_beta" in result


# ═══════════════════════════════════════════════════════════════
# Test: non-PAYLOADS assertions excluded
# ═══════════════════════════════════════════════════════════════


class TestNonPayloadsExcluded:
    """Tests that assertions at other arcs are not surfaced."""

    @pytest.mark.asyncio
    async def test_inherits_not_shown(self) -> None:
        """INHERITS assertions at the same path are not included in output."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "Use InnoDB", CompositionArc.INHERITS)

        result = await cb_payload_check(ctx=ctx)
        assert "No pending payloads" in result
        assert "Use InnoDB" not in result

    @pytest.mark.asyncio
    async def test_local_not_shown(self) -> None:
        """LOCAL assertions at the same path are not included in output."""
        ctx, stage, _ = _make_ctx_with_stage()
        # LOCAL requires falsifiable_if by validator
        a = Assertion(
            topic_path="/db/engine",
            content="InnoDB is best",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If benchmark shows < 1000 TPS under load",
        )
        stage.assertions[a.id] = a

        result = await cb_payload_check(ctx=ctx)
        assert "No pending payloads" in result

    @pytest.mark.asyncio
    async def test_retracted_payloads_not_shown(self) -> None:
        """Retracted PAYLOADS assertions (active=False) are excluded."""
        ctx, stage, _ = _make_ctx_with_stage()
        ast = _add_assertion(stage, "/db/engine", "Old payload", CompositionArc.PAYLOADS)
        ast.active = False  # retract it

        result = await cb_payload_check(ctx=ctx)
        assert "No pending payloads" in result
        assert ast.id not in result

    @pytest.mark.asyncio
    async def test_mixed_arcs_only_payloads_shown(self) -> None:
        """With multiple arc types present, only PAYLOADS assertions appear."""
        ctx, stage, _ = _make_ctx_with_stage()
        _add_assertion(stage, "/db/engine", "INHERITS claim", CompositionArc.INHERITS)
        payload = _add_assertion(
            stage, "/db/index", "Index strategy pending", CompositionArc.PAYLOADS
        )

        result = await cb_payload_check(ctx=ctx)
        assert "PENDING PAYLOADS (1)" in result
        assert payload.id in result
        assert "INHERITS claim" not in result
