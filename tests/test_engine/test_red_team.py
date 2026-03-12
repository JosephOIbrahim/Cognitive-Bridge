"""Tests for engine/red_team.py — RED_TEAMING anti-echo-chamber engine.

Covers:
- should_trigger_red_team(): empty stage, below threshold, at threshold with
  zero conflicts and exchange_count > 0, at threshold with active conflicts,
  at threshold but exchange_count == 0, custom threshold.
- find_unchallenged_locals(): no LOCALs, LOCAL with conflict history excluded,
  LOCAL without conflict history included, sorted oldest first, non-LOCAL
  excluded, inactive LOCAL excluded.
- find_unfalsifiable_locals(): LIVE with falsifiable_if included, CHALLENGED
  excluded, no falsifiable_if excluded (defensive), non-LOCAL excluded.
- find_missing_dependencies(): has depends_on_paths excluded, INHERITS with
  parent in stage included, SPECIALIZES excluded, single-segment path excluded.
- generate_red_team_report(): clean stage, unchallenged shown, falsifiable shown,
  missing deps shown, TRIGGERED/MONITORING header.
- record_red_team_trigger(): event appended with correct type and detail.
"""

from datetime import datetime, timezone, timedelta

import pytest

from cognitive_bridge.engine.red_team import (
    find_missing_dependencies,
    find_unchallenged_locals,
    find_unfalsifiable_locals,
    generate_red_team_report,
    record_red_team_trigger,
    should_trigger_red_team,
)
from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
    EventType,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.parameters import CognitiveParameters
from cognitive_bridge.models.stage import CompositionStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage(
    exchange_count: int = 0,
    red_team_threshold: int = 8,
) -> CompositionStage:
    """Return a fresh empty stage with the given exchange_count and threshold."""
    params = CognitiveParameters(red_team_threshold=red_team_threshold)
    return CompositionStage(
        project_id="rt_test",
        project_name="Red Team Tests",
        parameters=params,
        exchange_count=exchange_count,
    )


def _local(
    path: str,
    content: str = "A local claim.",
    falsifiable: str = "Test condition.",
    assumption_status: AssumptionStatus = AssumptionStatus.LIVE,
    created_at: datetime | None = None,
    depends_on_paths: list[str] | None = None,
) -> Assertion:
    """Create a LOCAL assertion.  All LOCALs require falsifiable_if by schema."""
    kwargs: dict = dict(
        topic_path=path,
        content=content,
        arc=CompositionArc.LOCAL,
        author=AssertionAuthor.AI,
        falsifiable_if=falsifiable,
        assumption_status=assumption_status,
        depends_on_paths=depends_on_paths or [],
    )
    if created_at is not None:
        kwargs["created_at"] = created_at
    return Assertion(**kwargs)


def _inherits(
    path: str,
    content: str = "An inherited claim.",
    depends_on_paths: list[str] | None = None,
) -> Assertion:
    """Create an INHERITS assertion (no falsifiable_if required)."""
    return Assertion(
        topic_path=path,
        content=content,
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        depends_on_paths=depends_on_paths or [],
    )


def _specializes(path: str, content: str = "A specialization.") -> Assertion:
    """Create a SPECIALIZES assertion."""
    return Assertion(
        topic_path=path,
        content=content,
        arc=CompositionArc.SPECIALIZES,
        author=AssertionAuthor.AI,
    )


def _add_assertions(stage: CompositionStage, *assertions: Assertion) -> None:
    """Insert assertions into the stage by their ID."""
    for a in assertions:
        stage.assertions[a.id] = a


def _make_conflict(
    a_id: str,
    b_id: str,
    path: str = "/test",
    status: ConflictStatus = ConflictStatus.ACTIVE,
) -> Conflict:
    """Create a minimal Conflict."""
    return Conflict(
        assertion_a_id=a_id,
        assertion_b_id=b_id,
        topic_path=path,
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
        status=status,
    )


def _add_conflicts(stage: CompositionStage, *conflicts: Conflict) -> None:
    """Insert conflicts into the stage by their ID."""
    for c in conflicts:
        stage.conflicts[c.id] = c


# ---------------------------------------------------------------------------
# TestShouldTriggerRedTeam
# ---------------------------------------------------------------------------

class TestShouldTriggerRedTeam:

    def test_empty_stage_returns_false(self):
        """No assertions, no conflicts, exchange_count=0 → False."""
        stage = _make_stage()
        assert should_trigger_red_team(stage) is False

    def test_below_threshold_local_count_returns_false(self):
        """7 LOCAL assertions below default threshold of 8 → False."""
        stage = _make_stage(exchange_count=5)
        for i in range(7):
            _add_assertions(stage, _local(f"/claim/{chr(ord('a') + i)}"))
        assert should_trigger_red_team(stage) is False

    def test_at_threshold_zero_conflicts_exchange_count_gt_zero_returns_true(self):
        """8 LOCAL assertions, zero active conflicts, exchange_count=1 → True."""
        stage = _make_stage(exchange_count=1)
        for i in range(8):
            _add_assertions(stage, _local(f"/claim/{chr(ord('a') + i)}"))
        assert should_trigger_red_team(stage) is True

    def test_at_threshold_but_active_conflicts_returns_false(self):
        """8 LOCAL assertions but 1 active conflict → False.

        Active conflicts mean the stage IS being challenged — RED_TEAMING
        should not pile on while conflicts are already live.
        """
        stage = _make_stage(exchange_count=5)
        assertions = []
        for i in range(8):
            a = _local(f"/claim/{chr(ord('a') + i)}")
            _add_assertions(stage, a)
            assertions.append(a)
        cfl = _make_conflict(assertions[0].id, assertions[1].id, "/claim/a")
        _add_conflicts(stage, cfl)
        assert should_trigger_red_team(stage) is False

    def test_at_threshold_but_exchange_count_zero_returns_false(self):
        """8 LOCAL assertions, zero conflicts, but exchange_count=0 → False.

        A fresh stage (no exchanges yet) should not trigger RED_TEAMING
        even if it was pre-populated with LOCAL assertions.
        """
        stage = _make_stage(exchange_count=0)
        for i in range(8):
            _add_assertions(stage, _local(f"/claim/{chr(ord('a') + i)}"))
        assert should_trigger_red_team(stage) is False

    def test_custom_threshold_triggers_at_three_locals(self):
        """With threshold=3, exactly 3 LOCAL assertions + 0 conflicts + exchange → True."""
        stage = _make_stage(exchange_count=2, red_team_threshold=3)
        for i in range(3):
            _add_assertions(stage, _local(f"/claim/{chr(ord('a') + i)}"))
        assert should_trigger_red_team(stage) is True


# ---------------------------------------------------------------------------
# TestFindUnchallengedLocals
# ---------------------------------------------------------------------------

class TestFindUnchallengedLocals:

    def test_no_local_assertions_returns_empty(self):
        """Stage with only SPECIALIZES assertions → empty list."""
        stage = _make_stage()
        _add_assertions(stage, _specializes("/background/info"))
        result = find_unchallenged_locals(stage)
        assert result == []

    def test_local_with_conflict_history_excluded(self):
        """A LOCAL assertion that appears in a conflict (even DISMISSED) is excluded."""
        stage = _make_stage()
        a = _local("/db/engine")
        _add_assertions(stage, a)
        cfl = _make_conflict(
            a.id, "ast_other000001", "/db/engine", ConflictStatus.DISMISSED
        )
        _add_conflicts(stage, cfl)

        result = find_unchallenged_locals(stage)
        assert result == []

    def test_local_without_conflict_history_included(self):
        """A LOCAL assertion with no conflicts → in the result."""
        stage = _make_stage()
        a = _local("/db/engine")
        _add_assertions(stage, a)

        result = find_unchallenged_locals(stage)
        assert len(result) == 1
        assert result[0].id == a.id

    def test_sorted_oldest_first(self):
        """Three LOCAL assertions → sorted by created_at ascending."""
        now = datetime.now(timezone.utc)
        stage = _make_stage()
        a_old = _local("/claim/alpha", created_at=now - timedelta(hours=3))
        a_mid = _local("/claim/beta", created_at=now - timedelta(hours=1))
        a_new = _local("/claim/gamma", created_at=now)
        _add_assertions(stage, a_new, a_old, a_mid)  # inserted out of order

        result = find_unchallenged_locals(stage)
        assert len(result) == 3
        assert result[0].id == a_old.id
        assert result[1].id == a_mid.id
        assert result[2].id == a_new.id

    def test_non_local_assertions_excluded_even_without_conflicts(self):
        """INHERITS and SPECIALIZES assertions are not included even with no conflicts."""
        stage = _make_stage()
        _add_assertions(
            stage,
            _inherits("/arch/design"),
            _specializes("/arch/background"),
        )

        result = find_unchallenged_locals(stage)
        assert result == []

    def test_inactive_local_excluded(self):
        """LOCAL assertion with active=False is excluded."""
        stage = _make_stage()
        a = _local("/db/engine")
        a.active = False
        _add_assertions(stage, a)

        result = find_unchallenged_locals(stage)
        assert result == []


# ---------------------------------------------------------------------------
# TestFindUnfalsifiableLocals  (find_unfalsifiable_locals)
# ---------------------------------------------------------------------------

class TestFindUnfalsifiableLocals:

    def test_live_local_with_falsifiable_if_included(self):
        """LIVE LOCAL with falsifiable_if → in result."""
        stage = _make_stage()
        a = _local("/db/engine", falsifiable="If query latency > 100ms.")
        _add_assertions(stage, a)

        result = find_unfalsifiable_locals(stage)
        assert len(result) == 1
        assert result[0].id == a.id

    def test_challenged_local_excluded(self):
        """CHALLENGED LOCAL is excluded — already under re-evaluation."""
        stage = _make_stage()
        a = _local(
            "/db/engine",
            assumption_status=AssumptionStatus.CHALLENGED,
        )
        _add_assertions(stage, a)

        result = find_unfalsifiable_locals(stage)
        assert result == []

    def test_local_without_falsifiable_if_excluded_defensively(self):
        """Defensive test: if falsifiable_if is somehow None, exclude it.

        In practice the schema validator prevents this for LOCAL, but
        the function should not crash or include such an assertion.
        """
        stage = _make_stage()
        # Build via model_construct to bypass validator
        a = Assertion.model_construct(
            id="ast_fake000001",
            topic_path="/db/raw",
            content="No falsifiability.",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if=None,
            assumption_status=AssumptionStatus.LIVE,
            active=True,
            depends_on_paths=[],
            evidence=[],
            tags=[],
        )
        stage.assertions[a.id] = a

        result = find_unfalsifiable_locals(stage)
        assert result == []

    def test_non_local_assertion_excluded(self):
        """INHERITS assertions are excluded regardless of assumption_status."""
        stage = _make_stage()
        _add_assertions(stage, _inherits("/arch/design"))

        result = find_unfalsifiable_locals(stage)
        assert result == []


# ---------------------------------------------------------------------------
# TestFindMissingDependencies
# ---------------------------------------------------------------------------

class TestFindMissingDependencies:

    def test_assertion_with_existing_depends_on_excluded(self):
        """Assertion that already declares depends_on_paths is excluded."""
        stage = _make_stage()
        parent = _local("/db", content="Parent claim.")
        child = _local(
            "/db/engine",
            content="Child claim.",
            depends_on_paths=["/db"],
        )
        _add_assertions(stage, parent, child)

        result = find_missing_dependencies(stage)
        # child already has dependencies; parent is single-segment equivalent → /db
        assert not any(a.id == child.id for a in result)

    def test_inherits_at_child_path_with_parent_in_stage_included(self):
        """INHERITS at /db/engine when /db has an active assertion → suspect."""
        stage = _make_stage()
        parent = _inherits("/db", content="Database layer.")
        child = _inherits("/db/engine", content="Engine specifics.")
        _add_assertions(stage, parent, child)

        result = find_missing_dependencies(stage)
        ids = [a.id for a in result]
        assert child.id in ids

    def test_specializes_assertion_excluded(self):
        """SPECIALIZES arc is not checked — too weak to require dependency declarations."""
        stage = _make_stage()
        parent = _specializes("/db")
        child = _specializes("/db/engine")
        _add_assertions(stage, parent, child)

        result = find_missing_dependencies(stage)
        assert result == []

    def test_single_segment_path_excluded(self):
        """Assertions at /db (one segment) have no meaningful parent → excluded."""
        stage = _make_stage()
        a = _local("/db", content="Top-level database claim.")
        _add_assertions(stage, a)

        result = find_missing_dependencies(stage)
        assert result == []

    def test_local_at_child_path_with_parent_in_stage_included(self):
        """LOCAL at /db/engine when /db has assertions and no depends_on_paths → suspect."""
        stage = _make_stage()
        parent = _local("/db", content="DB parent.")
        child = _local("/db/engine", content="Engine child without deps.")
        _add_assertions(stage, parent, child)

        result = find_missing_dependencies(stage)
        ids = [a.id for a in result]
        assert child.id in ids

    def test_no_parent_in_stage_not_included(self):
        """LOCAL at /db/engine but /db has no assertions → not a suspect."""
        stage = _make_stage()
        child = _local("/db/engine", content="Orphan child.")
        _add_assertions(stage, child)

        result = find_missing_dependencies(stage)
        assert result == []


# ---------------------------------------------------------------------------
# TestGenerateRedTeamReport
# ---------------------------------------------------------------------------

class TestGenerateRedTeamReport:

    def test_clean_stage_no_blind_spots(self):
        """Stage with no LOCAL assertions → 'No blind spots detected' message."""
        stage = _make_stage()
        report = generate_red_team_report(stage)
        assert "No blind spots detected" in report

    def test_unchallenged_locals_shown_in_report(self):
        """Unchallenged LOCAL assertions appear in the report body."""
        stage = _make_stage(exchange_count=3)
        a = _local("/db/engine", content="PostgreSQL is the right choice.")
        _add_assertions(stage, a)

        report = generate_red_team_report(stage)

        assert "UNCHALLENGED LOCALS" in report
        assert a.id in report
        assert "PostgreSQL is the right choice." in report

    def test_testable_falsification_conditions_shown(self):
        """LIVE LOCAL assertions with falsifiable_if surface in report."""
        stage = _make_stage()
        a = _local(
            "/db/engine",
            content="PostgreSQL handles 10k req/s.",
            falsifiable="If benchmarks show < 10k req/s under load.",
        )
        _add_assertions(stage, a)

        report = generate_red_team_report(stage)

        assert "TESTABLE FALSIFICATION CONDITIONS" in report
        assert "benchmarks show < 10k req/s" in report

    def test_missing_dependencies_shown(self):
        """Suspects from find_missing_dependencies appear in the report."""
        stage = _make_stage()
        parent = _inherits("/arch", content="Architecture layer.")
        child = _inherits("/arch/api", content="API layer has no deps declared.")
        _add_assertions(stage, parent, child)

        report = generate_red_team_report(stage)

        assert "POTENTIAL MISSING DEPENDENCIES" in report
        assert child.id in report

    def test_report_header_shows_triggered_status(self):
        """When should_trigger_red_team is True, report shows TRIGGERED."""
        stage = _make_stage(exchange_count=2, red_team_threshold=3)
        for i in range(3):
            _add_assertions(stage, _local(f"/claim/{chr(ord('a') + i)}"))

        report = generate_red_team_report(stage)

        assert "TRIGGERED" in report
        assert "MONITORING" not in report

    def test_report_header_shows_monitoring_status(self):
        """When should_trigger_red_team is False, report shows MONITORING."""
        stage = _make_stage(exchange_count=0)  # exchange_count=0 prevents trigger
        for i in range(10):
            _add_assertions(stage, _local(f"/claim/{chr(ord('a') + i)}"))

        report = generate_red_team_report(stage)

        assert "MONITORING" in report
        assert "TRIGGERED" not in report

    def test_report_is_string(self):
        """generate_red_team_report always returns a str."""
        stage = _make_stage()
        assert isinstance(generate_red_team_report(stage), str)

    def test_report_contains_threshold_and_counts(self):
        """Report header includes local count and threshold value."""
        stage = _make_stage(exchange_count=1, red_team_threshold=5)
        for i in range(3):
            _add_assertions(stage, _local(f"/claim/{chr(ord('a') + i)}"))

        report = generate_red_team_report(stage)

        # Local count and threshold should appear
        assert "3" in report   # local count
        assert "5" in report   # threshold


# ---------------------------------------------------------------------------
# TestRecordRedTeamTrigger
# ---------------------------------------------------------------------------

class TestRecordRedTeamTrigger:

    def test_event_appended_with_red_team_triggered_type(self):
        """After calling record_red_team_trigger, a RED_TEAM_TRIGGERED event exists."""
        stage = _make_stage(exchange_count=5)
        for i in range(8):
            _add_assertions(stage, _local(f"/claim/{chr(ord('a') + i)}"))

        assert len(stage.events) == 0

        record_red_team_trigger(stage)

        assert len(stage.events) == 1
        event = stage.events[0]
        assert event.event_type == EventType.RED_TEAM_TRIGGERED

    def test_event_detail_contains_local_count_and_threshold(self):
        """The event detail dict has 'local_count' and 'threshold' keys."""
        stage = _make_stage(exchange_count=1, red_team_threshold=5)
        for i in range(5):
            a = _local(f"/claim/{chr(ord('a') + i)}")
            _add_assertions(stage, a)

        record_red_team_trigger(stage)

        detail = stage.events[0].detail
        assert "local_count" in detail
        assert "threshold" in detail
        assert detail["local_count"] == 5
        assert detail["threshold"] == 5
