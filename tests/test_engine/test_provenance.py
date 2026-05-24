"""Tests for engine/provenance.py — audit trail queries over the event log.

Blueprint reference: Section 3.7, 6.x / Phase 1 (P1.T4 Provenance engine).
Constitution rules C8 (event-log audit), G4 (behavioral assertions).
"""

from datetime import datetime, timezone

import pytest

from cognitive_bridge.engine.provenance import (
    count_events_by_type, format_audit_trail, get_cascade_history,
    get_conflict_resolution_history, get_events_by_actor, get_events_by_type,
    get_events_for_target, get_events_in_range,
)
from cognitive_bridge.models.arcs import AssertionAuthor, EventType
from cognitive_bridge.models.stage import CompositionStage


def _make_stage() -> CompositionStage:
    return CompositionStage(project_id="prov-test", project_name="Provenance Tests")


def _record(stage, event_type, actor, target_id, detail=None):
    stage.record_event(event_type, actor, target_id, detail or {})


_T0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2025, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
_T2 = datetime(2025, 1, 1, 12, 0, 2, tzinfo=timezone.utc)
_T3 = datetime(2025, 1, 1, 12, 0, 3, tzinfo=timezone.utc)


def _record_at(stage, event_type, actor, target_id, timestamp):
    stage.record_event(event_type, actor, target_id)
    stage.events[-1].timestamp = timestamp


class TestGetEventsForTarget:
    def test_empty_stage_returns_empty_list(self):
        assert get_events_for_target(_make_stage(), "ast_abc") == []

    def test_returns_only_events_for_given_target(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_aaa")
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_bbb")
        _record(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "ast_aaa")
        result = get_events_for_target(stage, "ast_aaa")
        assert len(result) == 2
        for evt in result:
            assert evt.target_id == "ast_aaa"

    def test_returns_empty_when_no_events_for_target(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_zzz")
        assert get_events_for_target(stage, "ast_notfound") == []

    def test_results_ordered_by_timestamp_ascending(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_aaa", _T2)
        _record_at(stage, EventType.ASSERTION_PROMOTED, AssertionAuthor.USER, "ast_aaa", _T1)
        result = get_events_for_target(stage, "ast_aaa")
        assert result[0].timestamp <= result[1].timestamp

    def test_all_matching_event_types_returned(self):
        stage = _make_stage()
        types = [EventType.ASSERTION_CREATED, EventType.ASSERTION_CHALLENGED, EventType.ASSERTION_ORPHANED]
        for et in types:
            _record(stage, et, AssertionAuthor.AI, "ast_target")
        result = get_events_for_target(stage, "ast_target")
        assert len(result) == 3
        assert {e.event_type for e in result} == set(types)


class TestGetEventsByType:
    def test_empty_stage_returns_empty_list(self):
        assert get_events_by_type(_make_stage(), EventType.ASSERTION_CREATED) == []

    def test_filters_by_event_type_correctly(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        _record(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001")
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_002")
        result = get_events_by_type(stage, EventType.ASSERTION_CREATED)
        assert len(result) == 2
        for e in result:
            assert e.event_type == EventType.ASSERTION_CREATED

    def test_returns_empty_when_type_not_present(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        assert get_events_by_type(stage, EventType.RED_TEAM_TRIGGERED) == []

    def test_results_ordered_by_timestamp_ascending(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_002", _T2)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001", _T1)
        result = get_events_by_type(stage, EventType.ASSERTION_CREATED)
        assert result[0].timestamp <= result[1].timestamp


class TestGetEventsByActor:
    def test_empty_stage_returns_empty_list(self):
        assert get_events_by_actor(_make_stage(), AssertionAuthor.AI) == []

    def test_filters_by_actor(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_002")
        _record(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001")
        result = get_events_by_actor(stage, AssertionAuthor.AI)
        assert len(result) == 1
        assert result[0].actor == AssertionAuthor.AI

    def test_system_actor_filter(self):
        stage = _make_stage()
        _record(stage, EventType.RED_TEAM_TRIGGERED, AssertionAuthor.SYSTEM, "proj_001")
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        result = get_events_by_actor(stage, AssertionAuthor.SYSTEM)
        assert len(result) == 1
        assert result[0].event_type == EventType.RED_TEAM_TRIGGERED

    def test_results_ordered_by_timestamp_ascending(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_002", _T2)
        _record_at(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.AI, "cfl_001", _T1)
        result = get_events_by_actor(stage, AssertionAuthor.AI)
        assert result[0].timestamp <= result[1].timestamp

    def test_no_match_returns_empty(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        assert get_events_by_actor(stage, AssertionAuthor.EXTERNAL) == []


class TestGetEventsInRange:
    def test_no_bounds_returns_all_events(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001", _T0)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_002", _T2)
        assert len(get_events_in_range(stage)) == 2

    def test_after_bound_exclusive(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T0", _T0)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T1", _T1)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T2", _T2)
        result = get_events_in_range(stage, after=_T1)
        assert len(result) == 1
        assert result[0].target_id == "ast_T2"

    def test_before_bound_exclusive(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T0", _T0)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T1", _T1)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T2", _T2)
        result = get_events_in_range(stage, before=_T1)
        assert len(result) == 1
        assert result[0].target_id == "ast_T0"

    def test_both_bounds_applied(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T0", _T0)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T1", _T1)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T2", _T2)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T3", _T3)
        result = get_events_in_range(stage, after=_T0, before=_T3)
        assert len(result) == 2
        assert {e.target_id for e in result} == {"ast_T1", "ast_T2"}

    def test_empty_window_returns_empty(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T1", _T1)
        assert get_events_in_range(stage, after=_T2, before=_T0) == []

    def test_results_ordered_by_timestamp(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T2", _T2)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T0", _T0)
        _record_at(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_T1", _T1)
        result = get_events_in_range(stage)
        timestamps = [e.timestamp.replace(tzinfo=None) for e in result]
        assert timestamps == sorted(timestamps)

    def test_empty_stage_returns_empty(self):
        assert get_events_in_range(_make_stage(), after=_T0, before=_T3) == []


class TestFormatAuditTrail:
    def test_no_events_returns_sentinel_message(self):
        result = format_audit_trail(_make_stage(), "ast_missing")
        assert "no events" in result.lower() or "not found" in result.lower()

    def test_returns_string(self):
        assert isinstance(format_audit_trail(_make_stage(), "ast_x"), str)

    def test_report_contains_target_id(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_xyz")
        assert "ast_xyz" in format_audit_trail(stage, "ast_xyz")

    def test_report_contains_event_type_value(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_xyz")
        assert EventType.ASSERTION_CREATED.value in format_audit_trail(stage, "ast_xyz")

    def test_report_contains_actor(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_xyz")
        assert AssertionAuthor.USER.value in format_audit_trail(stage, "ast_xyz")

    def test_multiple_events_all_appear(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_xyz")
        _record(stage, EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_xyz")
        result = format_audit_trail(stage, "ast_xyz")
        assert EventType.ASSERTION_CREATED.value in result
        assert EventType.ASSERTION_CHALLENGED.value in result

    def test_detail_appears_in_output(self):
        stage = _make_stage()
        stage.record_event(
            EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_xyz",
            {"reason": "dependency_shifted"},
        )
        assert "dependency_shifted" in format_audit_trail(stage, "ast_xyz")

    def test_only_events_for_target_shown(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_xyz")
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_other")
        assert "ast_other" not in format_audit_trail(stage, "ast_xyz")


class TestGetConflictResolutionHistory:
    def test_empty_stage_returns_empty_list(self):
        assert get_conflict_resolution_history(_make_stage()) == []

    def test_returns_conflict_detected_events(self):
        stage = _make_stage()
        _record(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001")
        result = get_conflict_resolution_history(stage)
        assert len(result) == 1
        assert result[0].event_type == EventType.CONFLICT_DETECTED

    def test_returns_conflict_resolved_events(self):
        stage = _make_stage()
        _record(stage, EventType.CONFLICT_RESOLVED, AssertionAuthor.USER, "cfl_001")
        assert len(get_conflict_resolution_history(stage)) == 1

    def test_returns_experiment_proposed_events(self):
        stage = _make_stage()
        _record(stage, EventType.CONFLICT_EXPERIMENT_PROPOSED, AssertionAuthor.AI, "cfl_001")
        assert len(get_conflict_resolution_history(stage)) == 1

    def test_returns_experiment_resolved_events(self):
        stage = _make_stage()
        _record(stage, EventType.CONFLICT_EXPERIMENT_RESOLVED, AssertionAuthor.AI, "cfl_001")
        assert len(get_conflict_resolution_history(stage)) == 1

    def test_non_conflict_events_excluded(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        _record(stage, EventType.RED_TEAM_TRIGGERED, AssertionAuthor.SYSTEM, "proj_001")
        _record(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001")
        result = get_conflict_resolution_history(stage)
        assert len(result) == 1
        assert result[0].event_type == EventType.CONFLICT_DETECTED

    def test_results_ordered_by_timestamp_ascending(self):
        stage = _make_stage()
        _record_at(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001", _T2)
        _record_at(stage, EventType.CONFLICT_RESOLVED, AssertionAuthor.USER, "cfl_001", _T1)
        result = get_conflict_resolution_history(stage)
        assert result[0].timestamp <= result[1].timestamp

    def test_all_four_conflict_event_types_included(self):
        stage = _make_stage()
        types = [
            EventType.CONFLICT_DETECTED, EventType.CONFLICT_RESOLVED,
            EventType.CONFLICT_EXPERIMENT_PROPOSED, EventType.CONFLICT_EXPERIMENT_RESOLVED,
        ]
        for et in types:
            _record(stage, et, AssertionAuthor.SYSTEM, "cfl_001")
        result = get_conflict_resolution_history(stage)
        assert len(result) == 4
        assert {e.event_type for e in result} == set(types)


class TestGetCascadeHistory:
    def test_empty_stage_returns_empty_list(self):
        assert get_cascade_history(_make_stage(), "ast_none") == []

    def test_returns_challenged_events_for_assertion(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001")
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 1
        assert result[0].event_type == EventType.ASSERTION_CHALLENGED

    def test_returns_falsified_events_for_assertion(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_FALSIFIED, AssertionAuthor.SYSTEM, "ast_001")
        assert len(get_cascade_history(stage, "ast_001")) == 1

    def test_returns_orphaned_events_for_assertion(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_ORPHANED, AssertionAuthor.SYSTEM, "ast_001")
        assert len(get_cascade_history(stage, "ast_001")) == 1

    def test_non_cascade_event_types_excluded(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        _record(stage, EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001")
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 1
        assert result[0].event_type == EventType.ASSERTION_CHALLENGED

    def test_events_for_other_targets_excluded(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001")
        _record(stage, EventType.ASSERTION_ORPHANED, AssertionAuthor.SYSTEM, "ast_002")
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 1
        assert result[0].target_id == "ast_001"

    def test_results_ordered_by_timestamp_ascending(self):
        stage = _make_stage()
        _record_at(stage, EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001", _T2)
        _record_at(stage, EventType.ASSERTION_ORPHANED, AssertionAuthor.SYSTEM, "ast_001", _T1)
        result = get_cascade_history(stage, "ast_001")
        assert result[0].timestamp <= result[1].timestamp


class TestCountEventsByType:
    """Keys are EventType enum members (P0-3 fix — was previously str)."""

    def test_empty_stage_returns_empty_dict(self):
        assert count_events_by_type(_make_stage()) == {}

    def test_counts_single_event_type(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_002")
        assert count_events_by_type(stage)[EventType.ASSERTION_CREATED] == 2

    def test_counts_multiple_event_types(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        _record(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001")
        _record(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_002")
        _record(stage, EventType.RED_TEAM_TRIGGERED, AssertionAuthor.SYSTEM, "proj")
        counts = count_events_by_type(stage)
        assert counts[EventType.ASSERTION_CREATED] == 1
        assert counts[EventType.CONFLICT_DETECTED] == 2
        assert counts[EventType.RED_TEAM_TRIGGERED] == 1

    def test_returns_event_type_keyed_dict(self):
        """P0-3 verification: keys are EventType enum members."""
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        for key in count_events_by_type(stage):
            assert isinstance(key, EventType)

    def test_enum_member_indexes_the_dict(self):
        """Keys are EventType members, not bare ad-hoc strings.

        EventType is a str-backed enum, so a member compares equal to its string
        value; the meaningful regression guard is that every key is an EventType
        instance and the member itself indexes the dict.
        """
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        counts = count_events_by_type(stage)
        assert EventType.ASSERTION_CREATED in counts
        assert all(isinstance(k, EventType) for k in counts)

    def test_types_with_zero_events_omitted(self):
        stage = _make_stage()
        _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        assert EventType.RED_TEAM_TRIGGERED not in count_events_by_type(stage)

    def test_total_count_matches_total_events(self):
        stage = _make_stage()
        for i in range(5):
            _record(stage, EventType.ASSERTION_CREATED, AssertionAuthor.AI, f"ast_{i:03d}")
        for i in range(3):
            _record(stage, EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, f"cfl_{i:03d}")
        assert sum(count_events_by_type(stage).values()) == len(stage.events)
