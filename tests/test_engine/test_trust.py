"""Tests for engine/trust.py — per-subtree trust calibration.

Covers:
- compute_trust_scores(): empty stage, single override conflict, single active
  conflict, multiple stable resolutions, mixed, deferred, experiment, clamping
  at 0.0 and 1.0, multiple paths with separate scores.
- get_trust_for_path(): path with history, path without history.
- get_subtree_trust(): no matching paths, single matching path, multiple
  matching paths averaged, prefix filtering.
- format_trust_report(): empty stage, output structure, HIGH/MODERATE/LOW labels.
"""

import pytest

from cognitive_bridge.engine.trust import (
    TrustScore,
    compute_trust_scores,
    format_trust_report,
    get_subtree_trust,
    get_trust_for_path,
)
from cognitive_bridge.models.arcs import ConflictDetectionLayer, ConflictStatus
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage() -> CompositionStage:
    """Return a fresh empty stage."""
    return CompositionStage(project_id="test", project_name="Trust Tests")


def _make_conflict(
    topic_path: str,
    status: ConflictStatus = ConflictStatus.ACTIVE,
) -> Conflict:
    """Construct a minimal Conflict at the given path with the given status."""
    c = Conflict(
        assertion_a_id="ast_aaa000000001",
        assertion_b_id="ast_bbb000000002",
        topic_path=topic_path,
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
        status=status,
    )
    return c


def _add_conflicts(stage: CompositionStage, *conflicts: Conflict) -> None:
    """Insert each conflict into the stage by its ID."""
    for c in conflicts:
        stage.conflicts[c.id] = c


# ---------------------------------------------------------------------------
# TestComputeTrustScores
# ---------------------------------------------------------------------------

class TestComputeTrustScores:

    def test_empty_stage_returns_empty_dict(self):
        """Stage with no conflicts → empty dict, no KeyError."""
        stage = _make_stage()
        result = compute_trust_scores(stage)
        assert result == {}

    def test_single_override_conflict_raises_trust_above_half(self):
        """RESOLVED_OVERRIDE adds +0.03 → 0.53 > 0.5."""
        stage = _make_stage()
        c = _make_conflict("/db/engine", ConflictStatus.RESOLVED_OVERRIDE)
        _add_conflicts(stage, c)

        scores = compute_trust_scores(stage)

        assert "/db/engine" in scores
        ts = scores["/db/engine"]
        assert ts.score == pytest.approx(0.53, abs=1e-4)
        assert ts.total_conflicts == 1
        assert ts.resolved_conflicts == 1
        assert ts.overrides == 1
        assert ts.stable_resolutions == 0
        assert ts.challenges == 0

    def test_single_active_conflict_lowers_trust_below_half(self):
        """ACTIVE conflict subtracts -0.08 → 0.42 < 0.5."""
        stage = _make_stage()
        c = _make_conflict("/api/auth", ConflictStatus.ACTIVE)
        _add_conflicts(stage, c)

        scores = compute_trust_scores(stage)

        ts = scores["/api/auth"]
        assert ts.score == pytest.approx(0.42, abs=1e-4)
        assert ts.challenges == 1
        assert ts.resolved_conflicts == 0

    def test_multiple_stable_resolutions_increase_trust(self):
        """Three RESOLVED_SYNTHESIZED conflicts → 0.5 + 3*0.05 = 0.65."""
        stage = _make_stage()
        for _ in range(3):
            _add_conflicts(stage, _make_conflict("/architecture", ConflictStatus.RESOLVED_SYNTHESIZED))

        scores = compute_trust_scores(stage)

        ts = scores["/architecture"]
        assert ts.score == pytest.approx(0.65, abs=1e-4)
        assert ts.stable_resolutions == 3

    def test_mixed_active_and_resolved_balanced_score(self):
        """Two stable resolutions and one active conflict:
        0.5 + 2*0.05 - 1*0.08 = 0.52."""
        stage = _make_stage()
        _add_conflicts(
            stage,
            _make_conflict("/service/cache", ConflictStatus.RESOLVED_SYNTHESIZED),
            _make_conflict("/service/cache", ConflictStatus.RESOLVED_SYNTHESIZED),
            _make_conflict("/service/cache", ConflictStatus.ACTIVE),
        )

        scores = compute_trust_scores(stage)

        ts = scores["/service/cache"]
        assert ts.score == pytest.approx(0.52, abs=1e-4)
        assert ts.stable_resolutions == 2
        assert ts.challenges == 1
        assert ts.total_conflicts == 3

    def test_deferred_conflict_slightly_lowers_trust(self):
        """DEFERRED subtracts -0.03 → 0.47."""
        stage = _make_stage()
        c = _make_conflict("/orm", ConflictStatus.DEFERRED)
        _add_conflicts(stage, c)

        scores = compute_trust_scores(stage)

        ts = scores["/orm"]
        assert ts.score == pytest.approx(0.47, abs=1e-4)
        assert ts.resolved_conflicts == 0

    def test_experiment_resolution_strong_trust_boost(self):
        """RESOLVED_EXPERIMENT counts as stable (+0.05) AND experiment (+0.07).
        0.5 + 0.05 + 0.07 = 0.62."""
        stage = _make_stage()
        c = _make_conflict("/data/pipeline", ConflictStatus.RESOLVED_EXPERIMENT)
        _add_conflicts(stage, c)

        scores = compute_trust_scores(stage)

        ts = scores["/data/pipeline"]
        assert ts.score == pytest.approx(0.62, abs=1e-4)
        assert ts.experiments == 1
        assert ts.stable_resolutions == 1  # experiment also counts as stable
        assert ts.resolved_conflicts == 1

    def test_trust_clamped_to_zero_minimum(self):
        """7 ACTIVE conflicts: 0.5 - 7*0.08 = -0.06 → clamped to 0.0."""
        stage = _make_stage()
        for _ in range(7):
            _add_conflicts(stage, _make_conflict("/unstable", ConflictStatus.ACTIVE))

        scores = compute_trust_scores(stage)

        assert scores["/unstable"].score == 0.0

    def test_trust_clamped_to_one_maximum(self):
        """11 RESOLVED_SYNTHESIZED: 0.5 + 11*0.05 = 1.05 → clamped to 1.0."""
        stage = _make_stage()
        for _ in range(11):
            _add_conflicts(stage, _make_conflict("/stable", ConflictStatus.RESOLVED_SYNTHESIZED))

        scores = compute_trust_scores(stage)

        assert scores["/stable"].score == 1.0

    def test_multiple_paths_produce_separate_scores(self):
        """Conflicts at different paths produce independent TrustScore objects."""
        stage = _make_stage()
        # /db has a stable resolution
        _add_conflicts(stage, _make_conflict("/db", ConflictStatus.RESOLVED_SYNTHESIZED))
        # /api has an active conflict
        _add_conflicts(stage, _make_conflict("/api", ConflictStatus.ACTIVE))

        scores = compute_trust_scores(stage)

        assert len(scores) == 2
        assert scores["/db"].score > 0.5
        assert scores["/api"].score < 0.5
        # Scores are independent
        assert scores["/db"].challenges == 0
        assert scores["/api"].stable_resolutions == 0

    def test_promoted_conflict_counts_as_override(self):
        """RESOLVED_PROMOTED adds +0.03 (same as OVERRIDE) → 0.53."""
        stage = _make_stage()
        c = _make_conflict("/infra", ConflictStatus.RESOLVED_PROMOTED)
        _add_conflicts(stage, c)

        scores = compute_trust_scores(stage)

        ts = scores["/infra"]
        assert ts.score == pytest.approx(0.53, abs=1e-4)
        assert ts.overrides == 1

    def test_dismissed_conflict_counts_as_stable(self):
        """DISMISSED adds +0.05 (same as SYNTHESIZED) → 0.55."""
        stage = _make_stage()
        c = _make_conflict("/config", ConflictStatus.DISMISSED)
        _add_conflicts(stage, c)

        scores = compute_trust_scores(stage)

        ts = scores["/config"]
        assert ts.score == pytest.approx(0.55, abs=1e-4)
        assert ts.stable_resolutions == 1


# ---------------------------------------------------------------------------
# TestGetTrustForPath
# ---------------------------------------------------------------------------

class TestGetTrustForPath:

    def test_path_with_conflict_history_returns_computed_score(self):
        """Path that appears in conflict history returns the computed TrustScore."""
        stage = _make_stage()
        c = _make_conflict("/db/engine", ConflictStatus.RESOLVED_SYNTHESIZED)
        _add_conflicts(stage, c)

        ts = get_trust_for_path(stage, "/db/engine")

        assert ts.path == "/db/engine"
        assert ts.score == pytest.approx(0.55, abs=1e-4)
        assert ts.total_conflicts == 1

    def test_path_without_history_returns_neutral_trust(self):
        """Path with no conflict history returns score=0.5, all counters zero."""
        stage = _make_stage()

        ts = get_trust_for_path(stage, "/no/conflicts/here")

        assert ts.path == "/no/conflicts/here"
        assert ts.score == 0.5
        assert ts.total_conflicts == 0
        assert ts.resolved_conflicts == 0
        assert ts.overrides == 0
        assert ts.stable_resolutions == 0
        assert ts.challenges == 0
        assert ts.experiments == 0

    def test_returns_trust_score_instance(self):
        """Return value is always a TrustScore regardless of history."""
        stage = _make_stage()
        result = get_trust_for_path(stage, "/any/path")
        assert isinstance(result, TrustScore)


# ---------------------------------------------------------------------------
# TestGetSubtreeTrust
# ---------------------------------------------------------------------------

class TestGetSubtreeTrust:

    def test_no_matching_paths_returns_half(self):
        """When no conflict history exists under prefix, returns 0.5."""
        stage = _make_stage()
        # Add a conflict at /api — should not match /db prefix
        _add_conflicts(stage, _make_conflict("/api/auth", ConflictStatus.ACTIVE))

        result = get_subtree_trust(stage, "/db")

        assert result == 0.5

    def test_single_matching_path_returns_that_score(self):
        """Single path under prefix → returns that path's score."""
        stage = _make_stage()
        c = _make_conflict("/db/engine", ConflictStatus.RESOLVED_SYNTHESIZED)
        _add_conflicts(stage, c)

        result = get_subtree_trust(stage, "/db")

        # Should equal the single path's score (0.55)
        assert result == pytest.approx(0.55, abs=1e-4)

    def test_multiple_matching_paths_averaged(self):
        """Multiple paths under prefix → arithmetic mean of their scores."""
        stage = _make_stage()
        # /db/engine: stable → 0.55
        _add_conflicts(stage, _make_conflict("/db/engine", ConflictStatus.RESOLVED_SYNTHESIZED))
        # /db/migrations: active → 0.42
        _add_conflicts(stage, _make_conflict("/db/migrations", ConflictStatus.ACTIVE))

        result = get_subtree_trust(stage, "/db")

        expected = round((0.55 + 0.42) / 2, 4)
        assert result == pytest.approx(expected, abs=1e-4)

    def test_prefix_filters_correctly(self):
        """/db/* paths are not included when querying /api subtree."""
        stage = _make_stage()
        # /db/engine: stable → high trust
        _add_conflicts(stage, _make_conflict("/db/engine", ConflictStatus.RESOLVED_SYNTHESIZED))
        # /api/auth: active → low trust
        _add_conflicts(stage, _make_conflict("/api/auth", ConflictStatus.ACTIVE))

        db_trust = get_subtree_trust(stage, "/db")
        api_trust = get_subtree_trust(stage, "/api")

        assert db_trust > 0.5
        assert api_trust < 0.5
        # The two subtree values should differ
        assert db_trust != api_trust

    def test_empty_stage_returns_half(self):
        """Empty stage → no history anywhere → 0.5 for any prefix."""
        stage = _make_stage()
        assert get_subtree_trust(stage, "/any/prefix") == 0.5


# ---------------------------------------------------------------------------
# TestFormatTrustReport
# ---------------------------------------------------------------------------

class TestFormatTrustReport:

    def test_empty_stage_returns_no_history_message(self):
        """Empty stage produces the 'no conflict history' message."""
        stage = _make_stage()
        report = format_trust_report(stage)
        assert "No conflict history" in report
        assert "0.5" in report

    def test_report_contains_path_score_and_level(self):
        """Report includes the path, numeric score, and level label."""
        stage = _make_stage()
        c = _make_conflict("/db/engine", ConflictStatus.RESOLVED_SYNTHESIZED)
        _add_conflicts(stage, c)

        report = format_trust_report(stage)

        assert "/db/engine" in report
        assert "0.55" in report
        # Score 0.55 falls in MODERATE band (0.4 <= x < 0.7)
        assert "MODERATE" in report

    def test_high_trust_label(self):
        """Score >= 0.7 should produce HIGH label."""
        stage = _make_stage()
        # 5 stable resolutions: 0.5 + 5*0.05 = 0.75
        for _ in range(5):
            _add_conflicts(stage, _make_conflict("/solid", ConflictStatus.RESOLVED_SYNTHESIZED))

        report = format_trust_report(stage)

        assert "HIGH" in report

    def test_moderate_trust_label(self):
        """Score in [0.4, 0.7) produces MODERATE label."""
        stage = _make_stage()
        # 1 override: 0.5 + 0.03 = 0.53
        _add_conflicts(stage, _make_conflict("/mid", ConflictStatus.RESOLVED_OVERRIDE))

        report = format_trust_report(stage)

        assert "MODERATE" in report

    def test_low_trust_label(self):
        """Score < 0.4 produces LOW label."""
        stage = _make_stage()
        # 2 active conflicts: 0.5 - 2*0.08 = 0.34
        for _ in range(2):
            _add_conflicts(stage, _make_conflict("/contested", ConflictStatus.ACTIVE))

        report = format_trust_report(stage)

        assert "LOW" in report

    def test_report_mentions_experiments_when_present(self):
        """Experiment resolutions surface an explicit note in the report."""
        stage = _make_stage()
        c = _make_conflict("/empirical", ConflictStatus.RESOLVED_EXPERIMENT)
        _add_conflicts(stage, c)

        report = format_trust_report(stage)

        assert "Experiment" in report or "experiment" in report

    def test_report_header_includes_path_count(self):
        """Report header states the number of paths with conflict history."""
        stage = _make_stage()
        _add_conflicts(stage, _make_conflict("/a", ConflictStatus.ACTIVE))
        _add_conflicts(stage, _make_conflict("/b", ConflictStatus.ACTIVE))

        report = format_trust_report(stage)

        assert "2" in report  # 2 paths in header

    def test_report_is_string(self):
        """format_trust_report always returns a str."""
        stage = _make_stage()
        result = format_trust_report(stage)
        assert isinstance(result, str)
