"""Tests for Layer 2 semantic conflict detection.

Test matrix:
    Gate / always-run (no sentence-transformers required):
    1.  cross_path_detection disabled → returns []
    2.  Same-path assertions ignored (Layer 1 domain)
    3.  Inactive assertions ignored
    4.  Self comparison excluded
    5.  Warning dict has required keys
    6.  Warnings sorted by similarity descending
    7.  _SEMANTIC_AVAILABLE=False → returns [] with warning log

    Require sentence-transformers (@needs_semantic):
    8.  Similar content at different paths → warning above default threshold
    9.  Dissimilar content at different paths → no warning
    10. Lower threshold → more warnings; higher threshold → fewer warnings
    11. Embedding cached on assertion after detection
    12. _cosine_similarity with known vectors

    _cosine_similarity pure-function tests (always run):
    13. Identical unit vectors → 1.0
    14. Orthogonal vectors → 0.0
    15. Opposite vectors → -1.0
    16. Zero vector → 0.0
"""

import logging
from unittest.mock import patch

import pytest

try:
    import sentence_transformers  # noqa: F401
    HAS_SEMANTIC = True
except ImportError:
    HAS_SEMANTIC = False

needs_semantic = pytest.mark.skipif(
    not HAS_SEMANTIC,
    reason="sentence-transformers not installed",
)

from cognitive_bridge.engine.conflict_detector import (
    _cosine_similarity,
    detect_semantic_conflicts,
)
from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.parameters import CognitiveParameters
from cognitive_bridge.models.stage import CompositionStage


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_stage(
    *,
    cross_path: bool = False,
    threshold: float = 0.80,
) -> CompositionStage:
    """Return a stage with controllable semantic detection parameters."""
    params = CognitiveParameters(
        cross_path_detection=cross_path,
        semantic_threshold=threshold,
    )
    return CompositionStage(project_id="test-project", parameters=params)


def make_assertion(
    topic_path: str = "/db/engine",
    content: str = "Use PostgreSQL",
    arc: CompositionArc = CompositionArc.REFERENCES,
    active: bool = True,
) -> Assertion:
    """Return a valid non-LOCAL assertion with sensible defaults."""
    return Assertion(
        topic_path=topic_path,
        content=content,
        arc=arc,
        author=AssertionAuthor.AI,
        active=active,
        confidence=0.5,
    )


def add(stage: CompositionStage, assertion: Assertion) -> Assertion:
    """Add an assertion to the stage and return it."""
    stage.assertions[assertion.id] = assertion
    return assertion


# ─────────────────────────────────────────────────────────────────────────────
# _cosine_similarity — pure function tests (always run)
# ─────────────────────────────────────────────────────────────────────────────

class TestCosineSimilarity:
    """Direct tests for the _cosine_similarity helper with known vectors."""

    def test_identical_unit_vectors(self) -> None:
        """[1,0,0] · [1,0,0] = 1.0 (identical direction)."""
        assert _cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self) -> None:
        """[1,0,0] · [0,1,0] = 0.0 (perpendicular, no similarity)."""
        assert _cosine_similarity([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self) -> None:
        """[1,0,0] · [-1,0,0] = -1.0 (exactly opposite)."""
        assert _cosine_similarity([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]) == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector_a(self) -> None:
        """Zero magnitude on a → returns 0.0 (no division by zero)."""
        assert _cosine_similarity([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(0.0, abs=1e-6)

    def test_zero_vector_b(self) -> None:
        """Zero magnitude on b → returns 0.0."""
        assert _cosine_similarity([1.0, 0.0, 0.0], [0.0, 0.0, 0.0]) == pytest.approx(0.0, abs=1e-6)

    def test_non_unit_vectors_same_direction(self) -> None:
        """Scaling does not change direction: [2,0,0] · [3,0,0] = 1.0."""
        assert _cosine_similarity([2.0, 0.0, 0.0], [3.0, 0.0, 0.0]) == pytest.approx(1.0, abs=1e-6)

    def test_diagonal_vectors(self) -> None:
        """[1,1] · [1,-1] = 0.0 (45° vs -45° → orthogonal after normalisation)."""
        assert _cosine_similarity([1.0, 1.0], [1.0, -1.0]) == pytest.approx(0.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# Gate / always-run tests (no sentence-transformers required)
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticDetectionGates:
    """Tests that exercise gate logic and filtering — no model inference needed."""

    # ── 1. cross_path_detection disabled ─────────────────────────────────────

    def test_gate_disabled_returns_empty_list(self) -> None:
        """When cross_path_detection is False (default), the function must
        return [] immediately without touching sentence-transformers."""
        stage = make_stage(cross_path=False)
        new = add(stage, make_assertion("/a", "Postgres is fast"))
        add(stage, make_assertion("/b", "Postgres is the fastest database"))

        result = detect_semantic_conflicts(stage, new)

        assert result == []

    # ── 2. Same-path assertions ignored ──────────────────────────────────────

    @needs_semantic
    def test_same_path_assertions_not_flagged(self) -> None:
        """Two assertions at the same topic_path must never produce a semantic
        warning — same-path conflicts belong to Layer 1 (structural).
        Uses threshold=0.5 (the minimum) to catch any cross-path matches."""
        stage = make_stage(cross_path=True, threshold=0.5)
        new = add(stage, make_assertion("/db/engine", "PostgreSQL is excellent"))
        add(stage, make_assertion("/db/engine", "PostgreSQL is very good"))  # same path

        result = detect_semantic_conflicts(stage, new)

        assert result == []

    # ── 3. Inactive assertions ignored ───────────────────────────────────────

    @needs_semantic
    def test_inactive_assertion_not_flagged(self) -> None:
        """Retracted (active=False) assertions must not appear in warnings."""
        stage = make_stage(cross_path=True, threshold=0.5)
        inactive = add(
            stage,
            make_assertion("/other/path", "PostgreSQL is the best database", active=False),
        )
        new = add(stage, make_assertion("/db/engine", "PostgreSQL is excellent"))

        result = detect_semantic_conflicts(stage, new)

        assert not any(w["assertion_id"] == inactive.id for w in result)

    # ── 4. Self comparison excluded ───────────────────────────────────────────

    @needs_semantic
    def test_self_not_compared(self) -> None:
        """The new assertion must not appear in its own warnings list."""
        stage = make_stage(cross_path=True, threshold=0.5)
        new = add(stage, make_assertion("/db/engine", "Use PostgreSQL"))

        result = detect_semantic_conflicts(stage, new)

        assert not any(w["assertion_id"] == new.id for w in result)

    # ── 5. Warning dict shape ─────────────────────────────────────────────────

    @needs_semantic
    def test_warning_dict_has_required_keys(self) -> None:
        """Every warning dict must contain assertion_id, topic_path, content,
        and similarity_score.  Uses very similar content and threshold=0.5 to
        ensure at least one warning is produced."""
        stage = make_stage(cross_path=True, threshold=0.5)
        add(stage, make_assertion("/other/path", "Relational databases are solid"))
        new = add(stage, make_assertion("/db/engine", "Relational databases are reliable"))

        result = detect_semantic_conflicts(stage, new)

        assert len(result) >= 1
        for w in result:
            assert "assertion_id" in w, "missing assertion_id"
            assert "topic_path" in w, "missing topic_path"
            assert "content" in w, "missing content"
            assert "similarity_score" in w, "missing similarity_score"
            assert isinstance(w["similarity_score"], float)

    # ── 6. Warnings sorted by similarity descending ───────────────────────────

    @needs_semantic
    def test_warnings_sorted_by_similarity_descending(self) -> None:
        """When multiple warnings are returned they must be ordered highest
        similarity first so that Claude sees the most likely conflicts first."""
        stage = make_stage(cross_path=True, threshold=0.5)
        # Add several semantically related assertions at different paths
        add(stage, make_assertion("/a", "PostgreSQL is an excellent relational database"))
        add(stage, make_assertion("/b", "The sky is blue and clouds are white"))
        add(stage, make_assertion("/c", "PostgreSQL outperforms MySQL for OLAP workloads"))
        new = add(stage, make_assertion("/d", "PostgreSQL is the best relational database"))

        result = detect_semantic_conflicts(stage, new)

        if len(result) >= 2:
            scores = [w["similarity_score"] for w in result]
            assert scores == sorted(scores, reverse=True), (
                f"Warnings not sorted descending: {scores}"
            )

    # ── 7. _SEMANTIC_AVAILABLE=False → empty list + warning log ──────────────

    def test_graceful_degradation_when_package_unavailable(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When _SEMANTIC_AVAILABLE is patched to False the function must return
        [] and log a warning directing the user to the install command."""
        import cognitive_bridge.engine.conflict_detector as cd

        stage = make_stage(cross_path=True)  # gate open
        new = add(stage, make_assertion("/db/engine", "Use PostgreSQL"))

        with patch.object(cd, "_SEMANTIC_AVAILABLE", False):
            with caplog.at_level(logging.WARNING, logger="cognitive_bridge.engine.conflict_detector"):
                result = detect_semantic_conflicts(stage, new)

        assert result == []
        assert any("sentence-transformers" in msg for msg in caplog.messages), (
            "Expected a warning mentioning sentence-transformers"
        )


# ─────────────────────────────────────────────────────────────────────────────
# sentence-transformers required tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticDetectionWithModel:
    """Tests that require an installed sentence-transformers package."""

    # ── 8. Similar content different paths → warning ─────────────────────────

    @needs_semantic
    def test_similar_content_different_paths_produces_warning(self) -> None:
        """Two semantically similar assertions at different paths must produce
        at least one warning when cross_path_detection is enabled.
        Uses threshold=0.60 (below the typical ~0.85+ similarity for near-
        identical database sentences) to ensure a robust signal."""
        stage = make_stage(cross_path=True, threshold=0.60)
        existing = add(
            stage,
            make_assertion(
                "/db/engine",
                "Use PostgreSQL for the database",
            ),
        )
        new = add(
            stage,
            make_assertion(
                "/recommendations/db",
                "PostgreSQL is the best database choice",
            ),
        )

        result = detect_semantic_conflicts(stage, new)

        # We expect at least the existing assertion to appear
        ids = [w["assertion_id"] for w in result]
        assert existing.id in ids, (
            f"Expected {existing.id!r} in warnings but got {result}"
        )

    # ── 9. Dissimilar content → no warning ───────────────────────────────────

    @needs_semantic
    def test_dissimilar_content_no_warning(self) -> None:
        """Semantically unrelated assertions must not produce false positives."""
        stage = make_stage(cross_path=True, threshold=0.80)
        add(stage, make_assertion("/db/engine", "Use PostgreSQL"))
        new = add(stage, make_assertion("/weather", "The sky is blue today"))

        result = detect_semantic_conflicts(stage, new)

        assert result == [], f"Unexpected warnings for dissimilar content: {result}"

    # ── 10. Threshold tuning ──────────────────────────────────────────────────

    @needs_semantic
    def test_lower_threshold_produces_more_warnings(self) -> None:
        """Lowering semantic_threshold must produce at least as many warnings."""
        content_a = "Relational databases support ACID transactions"
        content_b = "ACID-compliant relational databases are reliable"

        stage_high = make_stage(cross_path=True, threshold=0.99)
        add(stage_high, make_assertion("/a", content_a))
        new_h = add(stage_high, make_assertion("/b", content_b))
        high_count = len(detect_semantic_conflicts(stage_high, new_h))

        stage_low = make_stage(cross_path=True, threshold=0.50)
        add(stage_low, make_assertion("/a", content_a))
        new_l = add(stage_low, make_assertion("/b", content_b))
        low_count = len(detect_semantic_conflicts(stage_low, new_l))

        assert low_count >= high_count, (
            f"Lower threshold should produce >= warnings: low={low_count} high={high_count}"
        )

    @needs_semantic
    def test_threshold_at_max_produces_no_warnings(self) -> None:
        """Threshold of 0.99 (the maximum allowed) must produce no warnings for
        semantically similar but non-identical texts at different paths.
        Perfect cosine similarity (1.0) is only possible for identical vectors."""
        stage = make_stage(cross_path=True, threshold=0.99)
        add(stage, make_assertion("/a", "Use PostgreSQL for the database"))
        new = add(stage, make_assertion("/b", "PostgreSQL is the best database choice"))

        result = detect_semantic_conflicts(stage, new)

        assert result == [], (
            f"Threshold 0.99 should reject near-similar content but got {result}"
        )

    # ── 11. Embedding cached on assertion ────────────────────────────────────

    @needs_semantic
    def test_embedding_cached_on_new_assertion(self) -> None:
        """After detect_semantic_conflicts runs, the new assertion's embedding
        field must be populated (not None)."""
        stage = make_stage(cross_path=True)
        new = add(stage, make_assertion("/db/engine", "Use PostgreSQL"))

        assert new.embedding is None, "embedding should start as None"

        detect_semantic_conflicts(stage, new)

        assert new.embedding is not None
        assert isinstance(new.embedding, list)
        assert len(new.embedding) > 0

    @needs_semantic
    def test_embedding_cached_on_existing_assertion(self) -> None:
        """Existing assertions that lack embeddings must be populated during
        semantic detection so subsequent calls avoid re-encoding."""
        stage = make_stage(cross_path=True)
        existing = add(stage, make_assertion("/other", "PostgreSQL is great"))
        new = add(stage, make_assertion("/db/engine", "Use PostgreSQL"))

        assert existing.embedding is None, "embedding should start as None"

        detect_semantic_conflicts(stage, new)

        assert existing.embedding is not None

    @needs_semantic
    def test_pre_cached_embedding_not_recomputed(self) -> None:
        """If the new assertion already has an embedding, it must be reused —
        not recomputed.  We verify by pre-loading a sentinel embedding and
        confirming the function still runs without overwriting it.

        The sentinel is all-zeros so it has similarity 0 with everything and
        will not exceed the minimum threshold (0.5), meaning no warnings are
        produced.  The key assertion is that the embedding is preserved."""
        stage = make_stage(cross_path=True, threshold=0.5)
        add(stage, make_assertion("/other", "Some other content"))

        # Pre-populate the new assertion's embedding with the all-zeros sentinel
        # (a valid, though unusual, embedding that gives similarity 0 with everything)
        sentinel = [0.0] * 384
        new = add(stage, make_assertion("/db/engine", "Use PostgreSQL"))
        new.embedding = list(sentinel)  # set before calling

        detect_semantic_conflicts(stage, new)

        # The sentinel must still be present — not replaced
        assert new.embedding == sentinel

    # ── 12. Warning content field matches source assertion ───────────────────

    @needs_semantic
    def test_warning_content_matches_existing_assertion(self) -> None:
        """The 'content' field in each warning dict must equal the content of
        the referenced assertion."""
        stage = make_stage(cross_path=True, threshold=0.5)
        existing = add(
            stage,
            make_assertion("/other", "PostgreSQL is a relational database"),
        )
        new = add(stage, make_assertion("/db/engine", "Use a relational database"))

        result = detect_semantic_conflicts(stage, new)

        matching = [w for w in result if w["assertion_id"] == existing.id]
        assert len(matching) == 1
        assert matching[0]["content"] == existing.content
        assert matching[0]["topic_path"] == existing.topic_path

    # ── Warning score precision ───────────────────────────────────────────────

    @needs_semantic
    def test_similarity_score_rounded_to_4_decimal_places(self) -> None:
        """similarity_score must be rounded to 4 decimal places."""
        stage = make_stage(cross_path=True, threshold=0.5)
        add(stage, make_assertion("/other", "PostgreSQL is reliable"))
        new = add(stage, make_assertion("/db/engine", "PostgreSQL is dependable"))

        result = detect_semantic_conflicts(stage, new)

        for w in result:
            score = w["similarity_score"]
            assert round(score, 4) == score, (
                f"Score {score} has more than 4 decimal places"
            )
