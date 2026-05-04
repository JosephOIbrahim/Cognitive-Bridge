"""Tests for engine/conflict_detector.py::detect_semantic_conflicts.

ALL TESTS IN THIS FILE ARE GATED BEHIND @pytest.mark.slow.
Run with: pytest -m slow

Blueprint reference: Section 4.2 (Layer 2 semantic conflict detection).
Constitution rule G3 (no mock-only coverage — must exercise real implementation).

Requires: pip install cognitive-bridge[semantic]  (sentence-transformers + numpy)
"""

import pytest

sentence_transformers = pytest.importorskip(
    "sentence_transformers",
    reason="sentence-transformers not installed; skipping semantic detection tests.",
)

pytestmark = pytest.mark.slow

from cognitive_bridge.engine.conflict_detector import detect_semantic_conflicts
from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.parameters import CognitiveParameters
from cognitive_bridge.models.stage import CompositionStage


def _make_stage(cross_path: bool = True, threshold: float = 0.70) -> CompositionStage:
    stage = CompositionStage(project_id="sem-test", project_name="Semantic Tests")
    stage.parameters = CognitiveParameters(
        cross_path_detection=cross_path, semantic_threshold=threshold,
    )
    return stage


def _make_assertion(
    topic_path: str, content: str,
    arc: CompositionArc = CompositionArc.INHERITS,
    falsifiable_if: str | None = None,
) -> Assertion:
    kwargs: dict = {"topic_path": topic_path, "content": content, "arc": arc, "author": AssertionAuthor.AI}
    if falsifiable_if is not None:
        kwargs["falsifiable_if"] = falsifiable_if
    elif arc == CompositionArc.LOCAL:
        kwargs["falsifiable_if"] = f"Falsified if {content} is disproved"
    return Assertion(**kwargs)


_HIGH_SIM_A = "PostgreSQL is the preferred relational database for this project."
_HIGH_SIM_B = "We will use PostgreSQL as our primary relational database system."

_LOW_SIM_A = "PostgreSQL is the preferred relational database for this project."
_LOW_SIM_B = "The sky is blue and the weather is sunny today."


class TestSemanticDetectionEnabled:
    def test_high_similarity_cross_path_produces_warnings(self):
        stage = _make_stage(cross_path=True, threshold=0.70)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        assert len(warnings) >= 1
        assert len([w for w in warnings if w["assertion_id"] == existing.id]) == 1

    def test_warning_dict_has_required_keys(self):
        stage = _make_stage(cross_path=True, threshold=0.70)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        assert len(warnings) >= 1
        w = warnings[0]
        assert "assertion_id" in w
        assert "topic_path" in w
        assert "content" in w
        assert "similarity_score" in w

    def test_warning_similarity_score_above_threshold(self):
        stage = _make_stage(cross_path=True, threshold=0.70)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        for w in warnings:
            assert w["similarity_score"] >= 0.70

    def test_warnings_sorted_by_similarity_descending(self):
        stage = _make_stage(cross_path=True, threshold=0.50)
        e1 = _make_assertion("/arch/db", _HIGH_SIM_A)
        e2 = _make_assertion("/config/store", "We prefer PostgreSQL for data persistence.")
        stage.assertions[e1.id] = e1
        stage.assertions[e2.id] = e2
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        if len(warnings) >= 2:
            scores = [w["similarity_score"] for w in warnings]
            assert scores == sorted(scores, reverse=True)

    def test_low_similarity_pair_produces_no_warnings(self):
        stage = _make_stage(cross_path=True, threshold=0.70)
        existing = _make_assertion("/arch/db", _LOW_SIM_A)
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/weather/report", _LOW_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        assert len([w for w in warnings if w["assertion_id"] == existing.id]) == 0

    def test_threshold_at_0_99_produces_no_warnings_for_paraphrase(self):
        stage = _make_stage(cross_path=True, threshold=0.99)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        assert len(warnings) == 0

    def test_embedding_cached_on_new_assertion(self):
        stage = _make_stage(cross_path=True, threshold=0.70)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        assert new_a.embedding is None
        stage.assertions[new_a.id] = new_a
        detect_semantic_conflicts(stage, new_a)
        assert new_a.embedding is not None
        assert isinstance(new_a.embedding, list)
        assert len(new_a.embedding) > 0

    def test_embedding_cached_on_existing_assertion(self):
        stage = _make_stage(cross_path=True, threshold=0.70)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        assert existing.embedding is None
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        detect_semantic_conflicts(stage, new_a)
        assert existing.embedding is not None


class TestSemanticDetectionGates:
    def test_cross_path_detection_false_returns_empty(self):
        stage = _make_stage(cross_path=False, threshold=0.70)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        assert detect_semantic_conflicts(stage, new_a) == []

    def test_same_path_assertions_excluded_from_semantic_detection(self):
        stage = _make_stage(cross_path=True, threshold=0.50)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/arch/db", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        assert [w for w in warnings if w["assertion_id"] == existing.id] == []

    def test_inactive_assertions_excluded(self):
        stage = _make_stage(cross_path=True, threshold=0.70)
        existing = _make_assertion("/arch/db", _HIGH_SIM_A)
        existing.active = False
        stage.assertions[existing.id] = existing
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        assert all(w["assertion_id"] != existing.id for w in warnings)

    def test_self_not_included_in_warnings(self):
        stage = _make_stage(cross_path=True, threshold=0.50)
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        warnings = detect_semantic_conflicts(stage, new_a)
        assert [w for w in warnings if w["assertion_id"] == new_a.id] == []

    def test_empty_stage_no_existing_returns_no_warnings(self):
        stage = _make_stage(cross_path=True, threshold=0.70)
        new_a = _make_assertion("/data/store", _HIGH_SIM_B)
        stage.assertions[new_a.id] = new_a
        assert detect_semantic_conflicts(stage, new_a) == []
