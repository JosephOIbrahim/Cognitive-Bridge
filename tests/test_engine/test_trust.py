"""Tests for engine/trust.py — per-subtree trust scores from conflict resolution history.

Blueprint reference: Section 3.8 / Phase 3 Quality Gate (P3.T3 Trust calibration).
Constitution rules G1, G4.
"""

import pytest

from cognitive_bridge.engine.trust import (
    TrustScore, compute_trust_scores, format_trust_report,
    get_subtree_trust, get_trust_for_path,
)
from cognitive_bridge.models.arcs import (
    AssertionAuthor, CompositionArc, ConflictDetectionLayer, ConflictStatus,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage


def _make_stage() -> CompositionStage:
    return CompositionStage(project_id="trust-test", project_name="Trust Tests")


def _make_assertion(topic_path: str, content: str, arc: CompositionArc = CompositionArc.INHERITS, falsifiable_if: str | None = None) -> Assertion:
    kwargs: dict = {"topic_path": topic_path, "content": content, "arc": arc, "author": AssertionAuthor.AI}
    if falsifiable_if is not None:
        kwargs["falsifiable_if"] = falsifiable_if
    elif arc == CompositionArc.LOCAL:
        kwargs["falsifiable_if"] = f"Falsified if {content} is disproved"
    return Assertion(**kwargs)


def _make_conflict(a_id: str, b_id: str, topic_path: str, status: ConflictStatus = ConflictStatus.ACTIVE) -> Conflict:
    c = Conflict(
        assertion_a_id=a_id, assertion_b_id=b_id,
        topic_path=topic_path, detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )
    c.status = status
    return c


def _add_conflict(stage: CompositionStage, topic_path: str, status: ConflictStatus) -> Conflict:
    a1 = _make_assertion(topic_path, "Option A")
    a2 = _make_assertion(topic_path, "Option B")
    stage.assertions[a1.id] = a1
    stage.assertions[a2.id] = a2
    c = _make_conflict(a1.id, a2.id, topic_path, status)
    stage.conflicts[c.id] = c
    return c


class TestComputeTrustScores:
    def test_empty_stage_returns_empty_dict(self):
        assert compute_trust_scores(_make_stage()) == {}

    def test_single_active_conflict_lowers_trust_below_neutral(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.ACTIVE)
        scores = compute_trust_scores(stage)
        assert "/arch/db" in scores
        ts = scores["/arch/db"]
        assert ts.score < 0.5
        assert ts.challenges == 1
        assert ts.total_conflicts == 1
        assert ts.resolved_conflicts == 0

    def test_resolved_override_increases_trust(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_OVERRIDE)
        ts = compute_trust_scores(stage)["/arch/db"]
        assert ts.score == pytest.approx(0.53, abs=1e-4)
        assert ts.overrides == 1
        assert ts.resolved_conflicts == 1
        assert ts.stable_resolutions == 0

    def test_resolved_promoted_increases_trust_same_as_override(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_PROMOTED)
        ts = compute_trust_scores(stage)["/arch/db"]
        assert ts.score == pytest.approx(0.53, abs=1e-4)
        assert ts.overrides == 1

    def test_resolved_synthesized_increases_trust_by_005(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_SYNTHESIZED)
        ts = compute_trust_scores(stage)["/arch/db"]
        assert ts.score == pytest.approx(0.55, abs=1e-4)
        assert ts.stable_resolutions == 1
        assert ts.overrides == 0

    def test_dismissed_is_stable_resolution(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.DISMISSED)
        ts = compute_trust_scores(stage)["/arch/db"]
        assert ts.score == pytest.approx(0.55, abs=1e-4)
        assert ts.stable_resolutions == 1
        assert ts.overrides == 0

    def test_resolved_experiment_adds_both_stable_and_experiment_bonus(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_EXPERIMENT)
        ts = compute_trust_scores(stage)["/arch/db"]
        assert ts.score == pytest.approx(0.62, abs=1e-4)
        assert ts.experiments == 1
        assert ts.stable_resolutions == 1

    def test_deferred_conflict_lowers_trust_slightly(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.DEFERRED)
        ts = compute_trust_scores(stage)["/arch/db"]
        assert ts.score == pytest.approx(0.47, abs=1e-4)
        assert ts.challenges == 0
        assert ts.resolved_conflicts == 0

    def test_score_clamped_to_zero_on_excessive_actives(self):
        stage = _make_stage()
        for i in range(8):
            a1 = _make_assertion("/arch/db", f"Option {i}A")
            a2 = _make_assertion("/arch/db", f"Option {i}B")
            stage.assertions[a1.id] = a1
            stage.assertions[a2.id] = a2
            c = _make_conflict(a1.id, a2.id, "/arch/db", ConflictStatus.ACTIVE)
            stage.conflicts[c.id] = c
        scores = compute_trust_scores(stage)
        assert scores["/arch/db"].score >= 0.0

    def test_score_clamped_to_one_on_excessive_experiments(self):
        stage = _make_stage()
        for i in range(10):
            a1 = _make_assertion("/arch/db", f"Option {i}A")
            a2 = _make_assertion("/arch/db", f"Option {i}B")
            stage.assertions[a1.id] = a1
            stage.assertions[a2.id] = a2
            c = _make_conflict(a1.id, a2.id, "/arch/db", ConflictStatus.RESOLVED_EXPERIMENT)
            stage.conflicts[c.id] = c
        scores = compute_trust_scores(stage)
        assert scores["/arch/db"].score <= 1.0

    def test_multiple_paths_computed_independently(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.ACTIVE)
        _add_conflict(stage, "/arch/api", ConflictStatus.RESOLVED_SYNTHESIZED)
        scores = compute_trust_scores(stage)
        assert "/arch/db" in scores
        assert "/arch/api" in scores
        assert scores["/arch/db"].score < 0.5
        assert scores["/arch/api"].score > 0.5

    def test_trust_score_dataclass_fields_present(self):
        stage = _make_stage()
        _add_conflict(stage, "/x", ConflictStatus.RESOLVED_PROMOTED)
        ts = compute_trust_scores(stage)["/x"]
        for attr in ("path", "score", "total_conflicts", "resolved_conflicts",
                     "overrides", "stable_resolutions", "challenges", "experiments"):
            assert hasattr(ts, attr)

    def test_all_promoted_high_trust(self):
        stage = _make_stage()
        for _ in range(3):
            _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_PROMOTED)
        ts = compute_trust_scores(stage)["/arch/db"]
        assert ts.score == pytest.approx(0.59, abs=1e-4)
        assert ts.score > 0.5

    def test_all_dismissed_high_trust(self):
        stage = _make_stage()
        for _ in range(3):
            _add_conflict(stage, "/arch/db", ConflictStatus.DISMISSED)
        ts = compute_trust_scores(stage)["/arch/db"]
        assert ts.score == pytest.approx(0.65, abs=1e-4)


class TestGetTrustForPath:
    def test_returns_neutral_default_for_unknown_path(self):
        stage = _make_stage()
        ts = get_trust_for_path(stage, "/nonexistent/path")
        assert ts.score == 0.5
        assert ts.total_conflicts == 0
        assert ts.path == "/nonexistent/path"

    def test_returns_correct_score_for_known_path(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_EXPERIMENT)
        ts = get_trust_for_path(stage, "/arch/db")
        assert ts.score > 0.5
        assert ts.path == "/arch/db"
        assert ts.experiments == 1

    def test_exact_path_match_only(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db/engine", ConflictStatus.ACTIVE)
        ts = get_trust_for_path(stage, "/arch/db")
        assert ts.score == 0.5
        assert ts.total_conflicts == 0


class TestGetSubtreeTrust:
    def test_no_paths_under_prefix_returns_neutral(self):
        stage = _make_stage()
        _add_conflict(stage, "/unrelated/path", ConflictStatus.ACTIVE)
        assert get_subtree_trust(stage, "/arch") == 0.5

    def test_aggregates_all_matching_paths(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.ACTIVE)
        _add_conflict(stage, "/arch/api", ConflictStatus.RESOLVED_SYNTHESIZED)
        result = get_subtree_trust(stage, "/arch")
        assert result == pytest.approx(0.485, abs=1e-4)

    def test_prefix_matches_deeper_paths(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db/engine", ConflictStatus.RESOLVED_SYNTHESIZED)
        assert get_subtree_trust(stage, "/arch") > 0.5

    def test_empty_stage_returns_neutral(self):
        assert get_subtree_trust(_make_stage(), "/arch") == 0.5

    def test_return_value_is_float_rounded_to_4(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_EXPERIMENT)
        _add_conflict(stage, "/arch/api", ConflictStatus.ACTIVE)
        result = get_subtree_trust(stage, "/arch")
        assert isinstance(result, float)
        assert result == round(result, 4)


class TestFormatTrustReport:
    def test_empty_stage_returns_sentinel_message(self):
        report = format_trust_report(_make_stage())
        assert "neutral" in report.lower() or "no conflict" in report.lower()

    def test_report_contains_path_names(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.ACTIVE)
        _add_conflict(stage, "/arch/api", ConflictStatus.RESOLVED_SYNTHESIZED)
        report = format_trust_report(stage)
        assert "/arch/db" in report
        assert "/arch/api" in report

    def test_report_contains_score_values(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_SYNTHESIZED)
        report = format_trust_report(stage)
        assert "0.55" in report

    def test_high_score_labeled_high(self):
        stage = _make_stage()
        for _ in range(3):
            _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_EXPERIMENT)
        assert "HIGH" in format_trust_report(stage)

    def test_low_score_labeled_low(self):
        stage = _make_stage()
        for _ in range(2):
            _add_conflict(stage, "/arch/db", ConflictStatus.ACTIVE)
        assert "LOW" in format_trust_report(stage)

    def test_moderate_score_labeled_moderate(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.ACTIVE)
        assert "MODERATE" in format_trust_report(stage)

    def test_experiment_count_highlighted(self):
        stage = _make_stage()
        _add_conflict(stage, "/arch/db", ConflictStatus.RESOLVED_EXPERIMENT)
        report = format_trust_report(stage)
        assert "Experiments" in report or "experiment" in report.lower()

    def test_report_is_string(self):
        assert isinstance(format_trust_report(_make_stage()), str)

    def test_paths_sorted_alphabetically(self):
        stage = _make_stage()
        _add_conflict(stage, "/z/path", ConflictStatus.ACTIVE)
        _add_conflict(stage, "/a/path", ConflictStatus.ACTIVE)
        report = format_trust_report(stage)
        assert report.index("/a/path") < report.index("/z/path")
