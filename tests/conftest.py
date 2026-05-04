"""Shared pytest fixtures for the Cognitive Bridge test suite.

This conftest centralizes setup that was previously duplicated across test files.
Existing tests that define local _MockCtx classes continue to work unchanged;
these fixtures are additive.

Fixtures:
- empty_stage: a bare CompositionStage (kept for backward compatibility).
- in_memory_store: a fresh SQLiteStore(":memory:") per test.
- mock_ctx: a minimal Context mock carrying lifespan_context.
- ctx_with_stage: factory that builds a (ctx, stage, store) triple wired together.
- make_assertion: factory for Assertion objects with sensible defaults.
- make_conflict: factory for Conflict objects with sensible defaults.
- stage_with_diamond_dag: a stage seeded with a 4-node diamond dependency DAG.

See docs/TEST_CONSTITUTION.md for the binding rules these fixtures support
(particularly Rules G5 — test isolation — and C7 — cascade propagation).
"""

from __future__ import annotations

from typing import Callable, Optional

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    Conflict,
    ConflictDetectionLayer,
)
from cognitive_bridge.storage.sqlite_store import SQLiteStore


# ════════════════════════════════════════════════════════════════════════
# Stage fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def empty_stage() -> CompositionStage:
    """A bare CompositionStage. Kept for backward compatibility."""
    return CompositionStage(project_id="test-project", project_name="Test Project")


# ════════════════════════════════════════════════════════════════════════
# Storage fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def in_memory_store() -> SQLiteStore:
    """A fresh in-memory SQLiteStore per test (Rule G5)."""
    return SQLiteStore(":memory:")


# ════════════════════════════════════════════════════════════════════════
# Mock Context (Rule G5 — fresh per test, not module-level)
# ════════════════════════════════════════════════════════════════════════


class _MockCtx:
    """Minimal FastMCP Context mock satisfying ctx.lifespan_context access.

    Tools only ever read ``ctx.lifespan_context["store"]`` and
    ``ctx.lifespan_context["active_stages"]`` — no other Context attributes
    are touched. This mock is sufficient for direct in-process tool testing.
    """

    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {
            "store": store,
            "active_stages": active_stages,
        }


@pytest.fixture
def mock_ctx(in_memory_store: SQLiteStore) -> _MockCtx:
    """A mock Context with a fresh store and empty active_stages registry."""
    return _MockCtx(store=in_memory_store, active_stages={})


@pytest.fixture
def ctx_with_stage() -> Callable[..., tuple[_MockCtx, CompositionStage, SQLiteStore]]:
    """Factory: build a (ctx, stage, store) triple wired together.

    Imports save_stage_to_db lazily so this fixture works for tests that
    don't need server.py imported.

    Usage:
        def test_thing(ctx_with_stage):
            ctx, stage, store = ctx_with_stage(project_id="proj_x")
    """

    def _factory(
        project_id: str = "proj_test",
        project_name: str = "Test Project",
    ) -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
        from cognitive_bridge.server import save_stage_to_db

        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id=project_id, project_name=project_name)
        active_stages: dict = {project_id: stage}
        save_stage_to_db(store, stage)
        ctx = _MockCtx(store=store, active_stages=active_stages)
        return ctx, stage, store

    return _factory


# ════════════════════════════════════════════════════════════════════════
# Model factories
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def make_assertion() -> Callable[..., Assertion]:
    """Factory for Assertion objects with sensible defaults.

    LOCAL arcs auto-receive a default falsifiable_if so the model validator
    doesn't reject them (Rule C6 — handled by the factory, not skipped).
    """

    def _factory(
        topic_path: str = "/test/path",
        content: str = "Test assertion",
        arc: CompositionArc = CompositionArc.INHERITS,
        author: AssertionAuthor = AssertionAuthor.AI,
        falsifiable_if: Optional[str] = None,
        confidence: float = 0.5,
        depends_on_paths: Optional[list[str]] = None,
        evidence: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
    ) -> Assertion:
        if arc == CompositionArc.LOCAL and falsifiable_if is None:
            falsifiable_if = "observed condition X"
        return Assertion(
            topic_path=topic_path,
            content=content,
            arc=arc,
            author=author,
            falsifiable_if=falsifiable_if,
            confidence=confidence,
            depends_on_paths=depends_on_paths or [],
            evidence=evidence or [],
            tags=tags or [],
        )

    return _factory


@pytest.fixture
def make_conflict() -> Callable[..., Conflict]:
    """Factory for Conflict objects with sensible defaults."""

    def _factory(
        assertion_a_id: str = "ast_a",
        assertion_b_id: str = "ast_b",
        topic_path: str = "/test/path",
        detection_layer: ConflictDetectionLayer = ConflictDetectionLayer.STRUCTURAL,
    ) -> Conflict:
        return Conflict(
            assertion_a_id=assertion_a_id,
            assertion_b_id=assertion_b_id,
            topic_path=topic_path,
            detection_layer=detection_layer,
        )

    return _factory


# ════════════════════════════════════════════════════════════════════════
# Cascade-DAG fixture (supports Rule C7 verification)
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def stage_with_diamond_dag(
    make_assertion: Callable[..., Assertion],
) -> CompositionStage:
    """A stage seeded with a diamond DAG of dependencies.

    Topology:
            /root
           /     \\
      /left      /right
           \\     /
           /merge   (depends on both /left and /right)

    Used by cascade tests that need to verify multi-path propagation.
    """
    stage = CompositionStage(project_id="diamond", project_name="Diamond DAG")

    root = make_assertion(topic_path="/root", content="root claim")
    left = make_assertion(
        topic_path="/left",
        content="left depends on root",
        depends_on_paths=["/root"],
    )
    right = make_assertion(
        topic_path="/right",
        content="right depends on root",
        depends_on_paths=["/root"],
    )
    merge = make_assertion(
        topic_path="/merge",
        content="merge depends on both",
        depends_on_paths=["/left", "/right"],
    )

    for a in (root, left, right, merge):
        stage.assertions[a.id] = a

    return stage
