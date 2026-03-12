"""Integration tests for the cb_manage_assertion tool.

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
)
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.assertion_tool import cb_manage_assertion


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


def _make_ctx(
    store: SQLiteStore | None = None,
    active_stages: dict | None = None,
) -> _MockCtx:
    """Build a mock context with optional overrides."""
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


def _make_stage(project_id: str = "proj_test") -> CompositionStage:
    """Create a minimal in-memory stage for testing."""
    return CompositionStage(project_id=project_id, project_name="Test Project")


def _make_ctx_with_stage(
    project_id: str = "proj_test",
) -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    """Create a context, stage, and store pre-wired together."""
    store = SQLiteStore(":memory:")
    stage = _make_stage(project_id)
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    ctx = _make_ctx(store=store, active_stages=active_stages)
    return ctx, stage, store


# ═══════════════════════════════════════════════════════════════
# Test: assert action
# ═══════════════════════════════════════════════════════════════


class TestAssertAction:
    """Tests for action='assert'."""

    @pytest.mark.asyncio
    async def test_assert_basic_specializes(self) -> None:
        """Assert at SPECIALIZES arc returns 'ASSERT', path, and content."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=60,
            ctx=ctx,
        )
        assert "ASSERT" in result
        assert "/architecture/database" in result
        assert "PostgreSQL is the primary datastore" in result

    @pytest.mark.asyncio
    async def test_assert_local_without_falsifiable_if_returns_error(self) -> None:
        """LOCAL (arc=10) assertion without falsifiable_if returns an ERROR response."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="The DB is PostgreSQL",
            arc=10,
            evidence="ran pg_version()",
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "falsifiable_if" in result.lower() or "local" in result.lower()

    @pytest.mark.asyncio
    async def test_assert_local_with_falsifiable_if_succeeds(self) -> None:
        """LOCAL assertion with falsifiable_if succeeds and returns ASSERT."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="The DB engine is PostgreSQL 15",
            arc=10,
            evidence="SELECT version() returned PostgreSQL 15.2",
            falsifiable_if="If SELECT version() returns a non-PostgreSQL string",
            ctx=ctx,
        )
        assert "ASSERT" in result
        assert "/architecture/database" in result

    @pytest.mark.asyncio
    async def test_assert_detects_structural_conflict(self) -> None:
        """Two different assertions at the same path triggers structural conflict detection."""
        ctx, stage, store = _make_ctx_with_stage()

        # First assertion
        await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=60,
            ctx=ctx,
        )

        # Second assertion at same path with different content
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="MySQL is the primary datastore",
            arc=60,
            ctx=ctx,
        )

        assert "STRUCTURAL CONFLICT" in result

    @pytest.mark.asyncio
    async def test_assert_with_depends_on_paths_stored_correctly(self) -> None:
        """depends_on_paths are parsed from comma-separated string and stored."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/api",
            content="REST API uses database engine",
            arc=20,
            depends_on_paths="/architecture/database,/architecture/cache",
            ctx=ctx,
        )
        assert "ASSERT" in result
        # Verify the assertion was stored with correct deps
        created_ast = next(iter(stage.assertions.values()))
        assert "/architecture/database" in created_ast.depends_on_paths
        assert "/architecture/cache" in created_ast.depends_on_paths

    @pytest.mark.asyncio
    async def test_assert_with_tags_stored_correctly(self) -> None:
        """tags are parsed from comma-separated string and stored on the assertion."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=60,
            tags="backend,storage,critical",
            ctx=ctx,
        )
        assert "ASSERT" in result
        created_ast = next(iter(stage.assertions.values()))
        assert "backend" in created_ast.tags
        assert "storage" in created_ast.tags
        assert "critical" in created_ast.tags

    @pytest.mark.asyncio
    async def test_assert_requires_content(self) -> None:
        """assert without content returns an ERROR."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            arc=60,
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "content" in result

    @pytest.mark.asyncio
    async def test_assert_requires_arc(self) -> None:
        """assert without arc returns an ERROR."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="PostgreSQL",
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "arc" in result


# ═══════════════════════════════════════════════════════════════
# Test: promote action
# ═══════════════════════════════════════════════════════════════


class TestPromoteAction:
    """Tests for action='promote'."""

    @pytest.mark.asyncio
    async def test_promote_succeeds(self) -> None:
        """Promote INHERITS to LOCAL succeeds and returns PROMOTE."""
        ctx, stage, store = _make_ctx_with_stage()

        # Create an INHERITS assertion directly on the stage
        ast = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        result = await cb_manage_assertion(
            action="promote",
            topic_path="/architecture/database",
            assertion_id=ast.id,
            arc=10,
            evidence="Confirmed via pg_version() query",
            falsifiable_if="If pg_version returns non-PG string",
            ctx=ctx,
        )
        assert "PROMOTE" in result

    @pytest.mark.asyncio
    async def test_promote_to_weaker_arc_returns_error(self) -> None:
        """Promoting to a weaker (higher-integer) arc returns an ERROR."""
        ctx, stage, store = _make_ctx_with_stage()

        ast = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        result = await cb_manage_assertion(
            action="promote",
            topic_path="/architecture/database",
            assertion_id=ast.id,
            arc=60,  # SPECIALIZES = 60, weaker than INHERITS = 20
            ctx=ctx,
        )
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_promote_without_assertion_id_returns_error(self) -> None:
        """promote without assertion_id returns an ERROR."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="promote",
            topic_path="/architecture/database",
            arc=10,
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "assertion_id" in result


# ═══════════════════════════════════════════════════════════════
# Test: retract action
# ═══════════════════════════════════════════════════════════════


class TestRetractAction:
    """Tests for action='retract'."""

    @pytest.mark.asyncio
    async def test_retract_succeeds(self) -> None:
        """Retract an active assertion returns RETRACT and deactivates it."""
        ctx, stage, store = _make_ctx_with_stage()

        ast = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        result = await cb_manage_assertion(
            action="retract",
            topic_path="/architecture/database",
            assertion_id=ast.id,
            ctx=ctx,
        )
        assert "RETRACT" in result
        assert stage.assertions[ast.id].active is False

    @pytest.mark.asyncio
    async def test_retract_without_assertion_id_returns_error(self) -> None:
        """retract without assertion_id returns an ERROR."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="retract",
            topic_path="/architecture/database",
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "assertion_id" in result

    @pytest.mark.asyncio
    async def test_retract_already_retracted_returns_error(self) -> None:
        """Retracting an already-retracted assertion returns an ERROR."""
        ctx, stage, store = _make_ctx_with_stage()

        ast = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        # Retract once
        await cb_manage_assertion(
            action="retract",
            topic_path="/architecture/database",
            assertion_id=ast.id,
            ctx=ctx,
        )

        # Retract again — must fail
        result = await cb_manage_assertion(
            action="retract",
            topic_path="/architecture/database",
            assertion_id=ast.id,
            ctx=ctx,
        )
        assert "ERROR" in result


# ═══════════════════════════════════════════════════════════════
# Test: falsify action
# ═══════════════════════════════════════════════════════════════


class TestFalsifyAction:
    """Tests for action='falsify'."""

    @pytest.mark.asyncio
    async def test_falsify_succeeds(self) -> None:
        """Falsify a LOCAL assertion with observed_condition returns FALSIFY."""
        ctx, stage, store = _make_ctx_with_stage()

        ast = Assertion(
            topic_path="/architecture/database",
            content="The DB engine is PostgreSQL 15",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            evidence=["ran pg_version()"],
            falsifiable_if="If pg_version() returns a non-PostgreSQL string",
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        result = await cb_manage_assertion(
            action="falsify",
            topic_path="/architecture/database",
            assertion_id=ast.id,
            observed_condition="pg_version() returned MySQL 8.0",
            ctx=ctx,
        )
        assert "FALSIFY" in result

    @pytest.mark.asyncio
    async def test_falsify_without_observed_condition_returns_error(self) -> None:
        """falsify without observed_condition returns an ERROR."""
        ctx, stage, store = _make_ctx_with_stage()

        ast = Assertion(
            topic_path="/architecture/database",
            content="The DB engine is PostgreSQL 15",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            evidence=["ran pg_version()"],
            falsifiable_if="If pg_version() returns a non-PostgreSQL string",
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        result = await cb_manage_assertion(
            action="falsify",
            topic_path="/architecture/database",
            assertion_id=ast.id,
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "observed_condition" in result

    @pytest.mark.asyncio
    async def test_falsify_without_assertion_id_returns_error(self) -> None:
        """falsify without assertion_id returns an ERROR."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="falsify",
            topic_path="/architecture/database",
            observed_condition="something observed",
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "assertion_id" in result


# ═══════════════════════════════════════════════════════════════
# Test: error conditions
# ═══════════════════════════════════════════════════════════════


class TestErrorConditions:
    """Tests for error conditions that cut across all actions."""

    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        """Any action with no active project returns an ERROR about active project."""
        ctx = _make_ctx()  # no active_stages
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="PostgreSQL",
            arc=60,
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "active project" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self) -> None:
        """An unknown action string returns an ERROR naming valid actions."""
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_assertion(
            action="delete",
            topic_path="/architecture/database",
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "assert" in result
        assert "promote" in result
        assert "retract" in result
        assert "falsify" in result


# ═══════════════════════════════════════════════════════════════
# Test: cascading conflicts in response
# ═══════════════════════════════════════════════════════════════


class TestCascadingConflictsInResponse:
    """Test that winner changes with dependents surface cascading conflict info."""

    @pytest.mark.asyncio
    async def test_winner_change_with_dependents_shows_cascading(self) -> None:
        """When a winner change triggers cascading conflicts, the response names them."""
        ctx, stage, store = _make_ctx_with_stage()

        # First: create the foundation assertion at SPECIALIZES
        foundation = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL is the DB",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        stage.assertions[foundation.id] = foundation

        # Second: create a dependent assertion at a different path
        dependent = Assertion(
            topic_path="/architecture/api",
            content="The API talks to the DB at /architecture/database",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/database"],
        )
        stage.assertions[dependent.id] = dependent
        save_stage_to_db(store, stage)

        # Now assert a STRONGER assertion at the foundation path — this changes
        # the winner, which should cascade to the dependent.
        result = await cb_manage_assertion(
            action="assert",
            topic_path="/architecture/database",
            content="MySQL is the DB (contradicts earlier claim)",
            arc=20,  # INHERITS = 20, stronger than SPECIALIZES = 60
            ctx=ctx,
        )

        # The winner changed (INHERITS beats SPECIALIZES) → cascade fires
        assert "CASCADING" in result


# ═══════════════════════════════════════════════════════════════
# Test: semantic warnings (Layer 2 + Layer 3 delegated pattern)
# ═══════════════════════════════════════════════════════════════


class TestSemanticWarningsInResponse:
    """Tests for Layer 2 semantic detection surfaced in tool response text (Layer 3 delegated)."""

    @pytest.mark.asyncio
    async def test_semantic_warnings_empty_when_disabled(self) -> None:
        """When cross_path_detection=False, no semantic warnings appear in the response."""
        ctx, stage, store = _make_ctx_with_stage()
        # cross_path_detection defaults to False — confirm no warnings regardless of content
        import cognitive_bridge.tools.assertion_tool as at
        original = at.detect_semantic_conflicts

        call_count = 0

        def tracking_detect(s, a):
            nonlocal call_count
            call_count += 1
            return []

        at.detect_semantic_conflicts = tracking_detect
        try:
            result = await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content="PostgreSQL is the primary datastore",
                arc=60,
                ctx=ctx,
            )
            # The tool must call detect_semantic_conflicts exactly once for "assert"
            assert call_count == 1
            # When it returns [] the warnings block must not appear in the response
            assert "SEMANTIC WARNINGS" not in result
        finally:
            at.detect_semantic_conflicts = original

    @pytest.mark.asyncio
    async def test_semantic_warnings_in_response_when_enabled(self) -> None:
        """When detect_semantic_conflicts returns matches, warnings appear in the response."""
        ctx, stage, store = _make_ctx_with_stage()

        import cognitive_bridge.tools.assertion_tool as at
        original = at.detect_semantic_conflicts

        def mock_detect(s, a):
            return [
                {
                    "assertion_id": "ast_mock123456",
                    "topic_path": "/other/path",
                    "content": "Similar content here",
                    "similarity_score": 0.92,
                }
            ]

        at.detect_semantic_conflicts = mock_detect
        try:
            result = await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content="PostgreSQL is the primary datastore",
                arc=60,
                ctx=ctx,
            )
            assert "SEMANTIC WARNINGS" in result
            assert "cb_manage_conflict" in result
        finally:
            at.detect_semantic_conflicts = original

    @pytest.mark.asyncio
    async def test_semantic_warnings_format(self) -> None:
        """Semantic warning output includes assertion_id, topic_path, content, and similarity_score."""
        ctx, stage, store = _make_ctx_with_stage()

        import cognitive_bridge.tools.assertion_tool as at
        original = at.detect_semantic_conflicts

        def mock_detect(s, a):
            return [
                {
                    "assertion_id": "ast_abc123def456",
                    "topic_path": "/data/storage",
                    "content": "MySQL is the database engine",
                    "similarity_score": 0.87,
                }
            ]

        at.detect_semantic_conflicts = mock_detect
        try:
            result = await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content="PostgreSQL is the primary datastore",
                arc=60,
                ctx=ctx,
            )
            assert "ast_abc123def456" in result
            assert "/data/storage" in result
            assert "MySQL is the database engine" in result
            assert "0.87" in result
        finally:
            at.detect_semantic_conflicts = original

    @pytest.mark.asyncio
    async def test_semantic_detection_not_called_for_promote(self) -> None:
        """detect_semantic_conflicts is NOT called for promote — only assert triggers Layer 2."""
        ctx, stage, store = _make_ctx_with_stage()

        ast = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        import cognitive_bridge.tools.assertion_tool as at
        original = at.detect_semantic_conflicts

        call_count = 0

        def tracking_detect(s, a):
            nonlocal call_count
            call_count += 1
            return []

        at.detect_semantic_conflicts = tracking_detect
        try:
            result = await cb_manage_assertion(
                action="promote",
                topic_path="/architecture/database",
                assertion_id=ast.id,
                arc=10,
                evidence="Confirmed via pg_version()",
                falsifiable_if="If pg_version returns non-PG string",
                ctx=ctx,
            )
            assert "PROMOTE" in result
            assert call_count == 0, (
                "detect_semantic_conflicts must not be called for promote actions"
            )
        finally:
            at.detect_semantic_conflicts = original

    @pytest.mark.asyncio
    async def test_semantic_detection_not_called_for_retract(self) -> None:
        """detect_semantic_conflicts is NOT called for retract."""
        ctx, stage, store = _make_ctx_with_stage()

        ast = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        import cognitive_bridge.tools.assertion_tool as at
        original = at.detect_semantic_conflicts

        call_count = 0

        def tracking_detect(s, a):
            nonlocal call_count
            call_count += 1
            return []

        at.detect_semantic_conflicts = tracking_detect
        try:
            result = await cb_manage_assertion(
                action="retract",
                topic_path="/architecture/database",
                assertion_id=ast.id,
                ctx=ctx,
            )
            assert "RETRACT" in result
            assert call_count == 0, (
                "detect_semantic_conflicts must not be called for retract actions"
            )
        finally:
            at.detect_semantic_conflicts = original
