"""Tests for engine/red_team.py — RED_TEAMING anti-echo-chamber posture escalation.

Blueprint reference: Section 3.4, 4.x / Phase 3 (P3.T4 RED_TEAMING auto-trigger).
Constitution rules C8 (event-log audit), G5 (test isolation).
"""

import pytest

from cognitive_bridge.engine.red_team import (
    find_missing_dependencies, find_unchallenged_locals, find_unfalsifiable_locals,
    generate_red_team_report, record_red_team_trigger, should_trigger_red_team,
)
from cognitive_bridge.models.arcs import (
    AssertionAuthor, AssumptionStatus, CompositionArc,
    ConflictDetectionLayer, ConflictStatus, EventType,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage


def _make_stage(exchange_count: int = 0) -> CompositionStage:
    s = CompositionStage(project_id="rt-test", project_name="Red Team Tests")
    s.exchange_count = exchange_count
    return s


def _make_local(
    topic_path: str, content: str,
    falsifiable_if: str | None = None,
    assumption_status: AssumptionStatus = AssumptionStatus.LIVE,
) -> Assertion:
    return Assertion(
        topic_path=topic_path, content=content,
        arc=CompositionArc.LOCAL, author=AssertionAuthor.AI,
        falsifiable_if=falsifiable_if or f"Falsified if {content} fails",
        assumption_status=assumption_status,
    )


def _make_inherits(topic_path: str, content: str, depends_on_paths: list[str] | None = None) -> Assertion:
    return Assertion(
        topic_path=topic_path, content=content,
        arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
        depends_on_paths=depends_on_paths or [],
    )


def _add_local(stage: CompositionStage, topic_path: str, content: str) -> Assertion:
    a = _make_local(topic_path, content)
    stage.assertions[a.id] = a
    return a


def _add_active_conflict(stage: CompositionStage, a_id: str, b_id: str, topic_path: str) -> Conflict:
    c = Conflict(
        assertion_a_id=a_id, assertion_b_id=b_id,
        topic_path=topic_path, detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )
    stage.conflicts[c.id] = c
    return c


class TestShouldTriggerRedTeam:
    def test_false_on_empty_stage(self):
        assert should_trigger_red_team(_make_stage()) is False

    def test_false_when_exchange_count_is_zero(self):
        stage = _make_stage(exchange_count=0)
        threshold = stage.parameters.red_team_threshold
        for i in range(threshold + 2):
            _add_local(stage, f"/feature/{i}", f"Claim {i}")
        assert should_trigger_red_team(stage) is False

    def test_false_when_local_count_below_threshold(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        for i in range(threshold - 1):
            _add_local(stage, f"/feature/{i}", f"Claim {i}")
        assert should_trigger_red_team(stage) is False

    def test_true_when_all_conditions_met(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        for i in range(threshold):
            _add_local(stage, f"/feature/{i}", f"Claim {i}")
        assert should_trigger_red_team(stage) is True

    def test_true_with_extra_locals_above_threshold(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        for i in range(threshold + 5):
            _add_local(stage, f"/feature/{i}", f"Claim {i}")
        assert should_trigger_red_team(stage) is True

    def test_false_when_active_conflict_exists(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        assertions = [_add_local(stage, f"/feature/{i}", f"Claim {i}") for i in range(threshold)]
        _add_active_conflict(stage, assertions[0].id, assertions[1].id, "/feature/0")
        assert should_trigger_red_team(stage) is False

    def test_deferred_conflict_does_not_block_trigger(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        assertions = [_add_local(stage, f"/feature/{i}", f"Claim {i}") for i in range(threshold)]
        c = Conflict(
            assertion_a_id=assertions[0].id, assertion_b_id=assertions[1].id,
            topic_path="/feature/0", detection_layer=ConflictDetectionLayer.STRUCTURAL,
        )
        c.status = ConflictStatus.DEFERRED
        stage.conflicts[c.id] = c
        assert should_trigger_red_team(stage) is True

    def test_lower_threshold_triggers_earlier(self):
        stage = _make_stage(exchange_count=1)
        stage.parameters = stage.parameters.model_copy(update={"red_team_threshold": 3})
        for i in range(3):
            _add_local(stage, f"/feature/{i}", f"Claim {i}")
        assert should_trigger_red_team(stage) is True

    def test_inactive_locals_not_counted(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        for i in range(threshold):
            a = _make_local(f"/feature/{i}", f"Claim {i}")
            a.active = False
            stage.assertions[a.id] = a
        _add_local(stage, "/active/one", "Active claim")
        assert should_trigger_red_team(stage) is False

    def test_exactly_at_threshold_triggers(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        for i in range(threshold):
            _add_local(stage, f"/feature/{i}", f"Claim {i}")
        assert should_trigger_red_team(stage) is True


class TestFindUnchallengedLocals:
    def test_empty_stage_returns_empty_list(self):
        assert find_unchallenged_locals(_make_stage()) == []

    def test_local_with_no_conflicts_is_unchallenged(self):
        stage = _make_stage()
        a = _add_local(stage, "/arch/db", "Use PostgreSQL")
        assert a in find_unchallenged_locals(stage)

    def test_local_in_conflict_is_not_unchallenged(self):
        stage = _make_stage()
        a = _add_local(stage, "/arch/db", "Use PostgreSQL")
        b = _add_local(stage, "/arch/api", "Use REST")
        _add_active_conflict(stage, a.id, b.id, "/arch/db")
        result = find_unchallenged_locals(stage)
        assert a not in result
        assert b not in result

    def test_inactive_locals_excluded(self):
        stage = _make_stage()
        a = _make_local("/arch/db", "Use PostgreSQL")
        a.active = False
        stage.assertions[a.id] = a
        assert a not in find_unchallenged_locals(stage)

    def test_non_local_arcs_excluded(self):
        stage = _make_stage()
        a = _make_inherits("/arch/db", "Use PostgreSQL")
        stage.assertions[a.id] = a
        assert a not in find_unchallenged_locals(stage)

    def test_resolved_conflict_still_marks_assertion_as_challenged(self):
        stage = _make_stage()
        a = _add_local(stage, "/arch/db", "Use PostgreSQL")
        b = _add_local(stage, "/arch/api", "Use REST")
        c = Conflict(
            assertion_a_id=a.id, assertion_b_id=b.id,
            topic_path="/arch/db", detection_layer=ConflictDetectionLayer.STRUCTURAL,
        )
        c.status = ConflictStatus.RESOLVED_OVERRIDE
        stage.conflicts[c.id] = c
        result = find_unchallenged_locals(stage)
        assert a not in result
        assert b not in result


class TestFindUnfalsifiableLocals:
    def test_empty_stage_returns_empty_list(self):
        assert find_unfalsifiable_locals(_make_stage()) == []

    def test_local_with_falsifiable_if_and_live_status_returned(self):
        stage = _make_stage()
        a = _add_local(stage, "/arch/db", "Use PostgreSQL")
        assert a.falsifiable_if is not None
        assert a.assumption_status == AssumptionStatus.LIVE
        assert a in find_unfalsifiable_locals(stage)

    def test_challenged_local_excluded(self):
        stage = _make_stage()
        a = _make_local("/arch/db", "Use PostgreSQL", assumption_status=AssumptionStatus.CHALLENGED)
        stage.assertions[a.id] = a
        assert a not in find_unfalsifiable_locals(stage)

    def test_falsified_local_excluded(self):
        stage = _make_stage()
        a = _make_local("/arch/db", "Use PostgreSQL", assumption_status=AssumptionStatus.FALSIFIED)
        stage.assertions[a.id] = a
        assert a not in find_unfalsifiable_locals(stage)

    def test_inactive_local_excluded(self):
        stage = _make_stage()
        a = _make_local("/arch/db", "Use PostgreSQL")
        a.active = False
        stage.assertions[a.id] = a
        assert a not in find_unfalsifiable_locals(stage)

    def test_inherits_arc_excluded(self):
        stage = _make_stage()
        a = _make_inherits("/arch/db", "Use PostgreSQL")
        stage.assertions[a.id] = a
        assert a not in find_unfalsifiable_locals(stage)

    def test_multiple_live_locals_all_returned(self):
        stage = _make_stage()
        assertions = [_add_local(stage, f"/arch/service/{i}", f"Claim {i}") for i in range(4)]
        result = find_unfalsifiable_locals(stage)
        for a in assertions:
            assert a in result


class TestFindMissingDependencies:
    def test_empty_stage_returns_empty_list(self):
        assert find_missing_dependencies(_make_stage()) == []

    def test_shallow_path_no_parent_not_flagged(self):
        stage = _make_stage()
        a = _make_local("/arch", "Architecture claim")
        stage.assertions[a.id] = a
        assert a not in find_missing_dependencies(stage)

    def test_local_with_parent_in_stage_and_no_deps_flagged(self):
        stage = _make_stage()
        parent = _make_inherits("/arch", "Architecture decision")
        child = _make_local("/arch/db", "Use PostgreSQL")
        stage.assertions[parent.id] = parent
        stage.assertions[child.id] = child
        assert child in find_missing_dependencies(stage)

    def test_assertion_with_depends_on_not_flagged(self):
        stage = _make_stage()
        parent = _make_inherits("/arch", "Architecture decision")
        child = Assertion(
            topic_path="/arch/db", content="Use PostgreSQL",
            arc=CompositionArc.LOCAL, author=AssertionAuthor.AI,
            falsifiable_if="Falsified if PostgreSQL fails",
            depends_on_paths=["/arch"],
        )
        stage.assertions[parent.id] = parent
        stage.assertions[child.id] = child
        assert child not in find_missing_dependencies(stage)

    def test_parent_not_in_stage_not_flagged(self):
        stage = _make_stage()
        child = _make_local("/arch/db", "Use PostgreSQL")
        stage.assertions[child.id] = child
        assert child not in find_missing_dependencies(stage)

    def test_inherits_arc_with_parent_also_flagged(self):
        stage = _make_stage()
        parent = _make_inherits("/arch", "Architecture")
        child = _make_inherits("/arch/db", "Use PostgreSQL")
        stage.assertions[parent.id] = parent
        stage.assertions[child.id] = child
        assert child in find_missing_dependencies(stage)

    def test_references_arc_not_flagged(self):
        stage = _make_stage()
        parent = _make_inherits("/arch", "Architecture")
        child = Assertion(
            topic_path="/arch/db", content="Use PostgreSQL",
            arc=CompositionArc.REFERENCES, author=AssertionAuthor.AI,
        )
        stage.assertions[parent.id] = parent
        stage.assertions[child.id] = child
        assert child not in find_missing_dependencies(stage)

    def test_inactive_assertions_excluded_from_suspects(self):
        stage = _make_stage()
        parent = _make_inherits("/arch", "Architecture")
        child = _make_local("/arch/db", "Use PostgreSQL")
        child.active = False
        stage.assertions[parent.id] = parent
        stage.assertions[child.id] = child
        assert child not in find_missing_dependencies(stage)


class TestGenerateRedTeamReport:
    def test_returns_string(self):
        assert isinstance(generate_red_team_report(_make_stage()), str)

    def test_report_contains_status_header(self):
        report = generate_red_team_report(_make_stage())
        assert "TRIGGERED" in report or "MONITORING" in report

    def test_report_shows_triggered_when_conditions_met(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        for i in range(threshold):
            _add_local(stage, f"/feature/{i}", f"Claim {i}")
        assert "TRIGGERED" in generate_red_team_report(stage)

    def test_report_shows_monitoring_when_below_threshold(self):
        assert "MONITORING" in generate_red_team_report(_make_stage(exchange_count=1))

    def test_report_contains_unchallenged_section_when_present(self):
        stage = _make_stage()
        _add_local(stage, "/arch/db", "Use PostgreSQL")
        assert "UNCHALLENGED" in generate_red_team_report(stage).upper()

    def test_report_contains_falsification_section_when_present(self):
        stage = _make_stage()
        _add_local(stage, "/arch/db", "Use PostgreSQL")
        report = generate_red_team_report(stage).upper()
        assert "FALSIFICATION" in report or "TESTABLE" in report

    def test_report_contains_missing_deps_section_when_present(self):
        stage = _make_stage()
        parent = _make_inherits("/arch", "Architecture")
        child = _make_local("/arch/db", "Use PostgreSQL")
        stage.assertions[parent.id] = parent
        stage.assertions[child.id] = child
        report = generate_red_team_report(stage).upper()
        assert "MISSING" in report or "DEPEND" in report

    def test_report_no_blind_spots_message_on_clean_stage(self):
        stage = _make_stage()
        a = Assertion(
            topic_path="/arch/db", content="Prefer PostgreSQL",
            arc=CompositionArc.REFERENCES, author=AssertionAuthor.AI,
        )
        stage.assertions[a.id] = a
        report = generate_red_team_report(stage)
        assert "no blind spots" in report.lower() or "well-tested" in report.lower()

    def test_report_contains_local_count_and_threshold(self):
        stage = _make_stage()
        assert str(stage.parameters.red_team_threshold) in generate_red_team_report(stage)


class TestRecordRedTeamTrigger:
    def test_appends_event_to_stage(self):
        stage = _make_stage(exchange_count=1)
        before = len(stage.events)
        record_red_team_trigger(stage)
        assert len(stage.events) == before + 1

    def test_event_type_is_red_team_triggered(self):
        stage = _make_stage(exchange_count=1)
        record_red_team_trigger(stage)
        assert stage.events[-1].event_type == EventType.RED_TEAM_TRIGGERED

    def test_event_actor_is_system(self):
        stage = _make_stage(exchange_count=1)
        record_red_team_trigger(stage)
        assert stage.events[-1].actor == AssertionAuthor.SYSTEM

    def test_event_detail_contains_local_count(self):
        stage = _make_stage(exchange_count=1)
        threshold = stage.parameters.red_team_threshold
        for i in range(threshold):
            _add_local(stage, f"/feature/{i}", f"Claim {i}")
        record_red_team_trigger(stage)
        evt = stage.events[-1]
        assert "local_count" in evt.detail
        assert evt.detail["local_count"] == threshold

    def test_event_detail_contains_threshold(self):
        stage = _make_stage(exchange_count=1)
        record_red_team_trigger(stage)
        evt = stage.events[-1]
        assert "threshold" in evt.detail
        assert evt.detail["threshold"] == stage.parameters.red_team_threshold

    def test_multiple_calls_append_multiple_events(self):
        stage = _make_stage(exchange_count=1)
        record_red_team_trigger(stage)
        record_red_team_trigger(stage)
        rt_events = [e for e in stage.events if e.event_type == EventType.RED_TEAM_TRIGGERED]
        assert len(rt_events) == 2
