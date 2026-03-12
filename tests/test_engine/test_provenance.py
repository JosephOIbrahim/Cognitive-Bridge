"""Tests for the provenance engine — audit trail queries.

All tests populate a CompositionStage via record_event() then exercise
each query function. Tests are independent: every test builds its own
stage from scratch.
"""

import time
from datetime import datetime, timezone, timedelta

import pytest

from cognitive_bridge.models.arcs import AssertionAuthor, EventType
from cognitive_bridge.models.stage import CompositionStage
from cognitive_bridge.engine.provenance import (
    count_events_by_type,
    format_audit_trail,
    get_cascade_history,
    get_conflict_resolution_history,
    get_events_by_actor,
    get_events_by_type,
    get_events_for_target,
    get_events_in_range,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _empty_stage() -> CompositionStage:
    """Return a fresh stage with no events."""
    return CompositionStage(project_id="test_prov")


def _stage_with_mixed_events() -> CompositionStage:
    """Stage with a predictable set of events across multiple targets/actors."""
    stage = _empty_stage()
    stage.record_event(
        EventType.ASSERTION_CREATED,
        AssertionAuthor.AI,
        "ast_001",
        {"content": "PostgreSQL is the right choice"},
    )
    stage.record_event(
        EventType.CONFLICT_DETECTED,
        AssertionAuthor.SYSTEM,
        "cfl_001",
        {"layer": "structural"},
    )
    stage.record_event(
        EventType.ASSERTION_CHALLENGED,
        AssertionAuthor.SYSTEM,
        "ast_001",
        {"reason": "cascade from /db/engine"},
    )
    stage.record_event(
        EventType.ASSERTION_CREATED,
        AssertionAuthor.USER,
        "ast_002",
        {"content": "MongoDB instead"},
    )
    stage.record_event(
        EventType.CONFLICT_RESOLVED,
        AssertionAuthor.AI,
        "cfl_001",
    )
    return stage


# ═══════════════════════════════════════════════════════════════
# TestGetEventsForTarget
# ═══════════════════════════════════════════════════════════════

class TestGetEventsForTarget:
    def test_no_events_returns_empty(self):
        stage = _empty_stage()
        result = get_events_for_target(stage, "ast_nonexistent")
        assert result == []

    def test_single_event_returned(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_111")
        result = get_events_for_target(stage, "ast_111")
        assert len(result) == 1
        assert result[0].target_id == "ast_111"
        assert result[0].event_type == EventType.ASSERTION_CREATED

    def test_multiple_events_for_target_all_returned(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_aaa")
        stage.record_event(EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_aaa")
        stage.record_event(EventType.ASSERTION_FALSIFIED, AssertionAuthor.SYSTEM, "ast_aaa")
        result = get_events_for_target(stage, "ast_aaa")
        assert len(result) == 3
        types = [e.event_type for e in result]
        assert EventType.ASSERTION_CREATED in types
        assert EventType.ASSERTION_CHALLENGED in types
        assert EventType.ASSERTION_FALSIFIED in types

    def test_multiple_events_sorted_oldest_first(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_bbb")
        stage.record_event(EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_bbb")
        result = get_events_for_target(stage, "ast_bbb")
        assert result[0].event_type == EventType.ASSERTION_CREATED
        assert result[1].event_type == EventType.ASSERTION_CHALLENGED

    def test_events_for_other_targets_excluded(self):
        stage = _mixed_two_target_stage()
        result = get_events_for_target(stage, "ast_x")
        for evt in result:
            assert evt.target_id == "ast_x"

    def test_events_for_other_targets_not_in_result(self):
        stage = _mixed_two_target_stage()
        result = get_events_for_target(stage, "ast_x")
        target_ids = {e.target_id for e in result}
        assert "ast_y" not in target_ids


def _mixed_two_target_stage() -> CompositionStage:
    stage = _empty_stage()
    stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_x")
    stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_y")
    stage.record_event(EventType.ASSERTION_PROMOTED, AssertionAuthor.AI, "ast_x")
    return stage


# ═══════════════════════════════════════════════════════════════
# TestGetEventsByType
# ═══════════════════════════════════════════════════════════════

class TestGetEventsByType:
    def test_no_matching_type_returns_empty(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        result = get_events_by_type(stage, EventType.CONFLICT_DETECTED)
        assert result == []

    def test_filter_by_assertion_created(self):
        stage = _stage_with_mixed_events()
        result = get_events_by_type(stage, EventType.ASSERTION_CREATED)
        assert len(result) == 2
        for evt in result:
            assert evt.event_type == EventType.ASSERTION_CREATED

    def test_only_requested_type_returned(self):
        stage = _stage_with_mixed_events()
        result = get_events_by_type(stage, EventType.CONFLICT_RESOLVED)
        assert len(result) == 1
        assert result[0].event_type == EventType.CONFLICT_RESOLVED
        assert result[0].target_id == "cfl_001"

    def test_empty_stage_returns_empty(self):
        stage = _empty_stage()
        result = get_events_by_type(stage, EventType.ASSERTION_CREATED)
        assert result == []

    def test_results_sorted_oldest_first(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_002")
        result = get_events_by_type(stage, EventType.ASSERTION_CREATED)
        assert len(result) == 2
        assert result[0].timestamp <= result[1].timestamp


# ═══════════════════════════════════════════════════════════════
# TestGetEventsByActor
# ═══════════════════════════════════════════════════════════════

class TestGetEventsByActor:
    def test_filter_by_ai_returns_only_ai(self):
        stage = _stage_with_mixed_events()
        result = get_events_by_actor(stage, AssertionAuthor.AI)
        for evt in result:
            assert evt.actor == AssertionAuthor.AI

    def test_filter_by_user_returns_only_user(self):
        stage = _stage_with_mixed_events()
        result = get_events_by_actor(stage, AssertionAuthor.USER)
        assert len(result) == 1
        assert result[0].actor == AssertionAuthor.USER
        assert result[0].target_id == "ast_002"

    def test_filter_by_system_returns_only_system(self):
        stage = _stage_with_mixed_events()
        result = get_events_by_actor(stage, AssertionAuthor.SYSTEM)
        for evt in result:
            assert evt.actor == AssertionAuthor.SYSTEM

    def test_mix_of_actors_correct_filtering(self):
        stage = _stage_with_mixed_events()
        ai_events = get_events_by_actor(stage, AssertionAuthor.AI)
        user_events = get_events_by_actor(stage, AssertionAuthor.USER)
        system_events = get_events_by_actor(stage, AssertionAuthor.SYSTEM)
        total = len(ai_events) + len(user_events) + len(system_events)
        assert total == len(stage.events)

    def test_no_matching_actor_returns_empty(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        result = get_events_by_actor(stage, AssertionAuthor.EXTERNAL)
        assert result == []


# ═══════════════════════════════════════════════════════════════
# TestGetEventsInRange
# ═══════════════════════════════════════════════════════════════

class TestGetEventsInRange:
    def test_no_range_returns_all_events(self):
        stage = _stage_with_mixed_events()
        result = get_events_in_range(stage)
        assert len(result) == len(stage.events)

    def test_after_filter_excludes_older_events(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        cutoff = datetime.now(timezone.utc)
        # Small sleep to ensure next event has a later timestamp
        time.sleep(0.01)
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_002")
        result = get_events_in_range(stage, after=cutoff)
        assert len(result) == 1
        assert result[0].target_id == "ast_002"

    def test_before_filter_excludes_newer_events(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        cutoff = datetime.now(timezone.utc)
        time.sleep(0.01)
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_002")
        result = get_events_in_range(stage, before=cutoff)
        assert len(result) == 1
        assert result[0].target_id == "ast_001"

    def test_both_filters_return_window(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        time.sleep(0.01)
        after_cutoff = datetime.now(timezone.utc)
        time.sleep(0.01)
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_002")
        time.sleep(0.01)
        before_cutoff = datetime.now(timezone.utc)
        time.sleep(0.01)
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.SYSTEM, "ast_003")
        result = get_events_in_range(stage, after=after_cutoff, before=before_cutoff)
        assert len(result) == 1
        assert result[0].target_id == "ast_002"

    def test_result_sorted_oldest_first(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        time.sleep(0.01)
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_002")
        result = get_events_in_range(stage)
        assert result[0].timestamp <= result[1].timestamp

    def test_empty_stage_returns_empty(self):
        stage = _empty_stage()
        result = get_events_in_range(stage)
        assert result == []


# ═══════════════════════════════════════════════════════════════
# TestGetCascadeHistory
# ═══════════════════════════════════════════════════════════════

class TestGetCascadeHistory:
    def test_no_cascade_events_returns_empty(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        result = get_cascade_history(stage, "ast_001")
        assert result == []

    def test_challenged_event_found(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        stage.record_event(
            EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001"
        )
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 1
        assert result[0].event_type == EventType.ASSERTION_CHALLENGED

    def test_falsified_event_found(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_FALSIFIED, AssertionAuthor.SYSTEM, "ast_001")
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 1
        assert result[0].event_type == EventType.ASSERTION_FALSIFIED

    def test_orphaned_event_found(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_ORPHANED, AssertionAuthor.SYSTEM, "ast_001")
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 1
        assert result[0].event_type == EventType.ASSERTION_ORPHANED

    def test_non_cascade_events_excluded(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        stage.record_event(EventType.ASSERTION_PROMOTED, AssertionAuthor.AI, "ast_001")
        stage.record_event(EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "ast_001")
        stage.record_event(EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001")
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 1
        assert result[0].event_type == EventType.ASSERTION_CHALLENGED

    def test_all_cascade_types_collected(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001")
        stage.record_event(EventType.ASSERTION_FALSIFIED, AssertionAuthor.SYSTEM, "ast_001")
        stage.record_event(EventType.ASSERTION_ORPHANED, AssertionAuthor.SYSTEM, "ast_001")
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 3

    def test_only_matching_target_returned(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001")
        stage.record_event(EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_002")
        result = get_cascade_history(stage, "ast_001")
        assert len(result) == 1
        assert result[0].target_id == "ast_001"


# ═══════════════════════════════════════════════════════════════
# TestFormatAuditTrail
# ═══════════════════════════════════════════════════════════════

class TestFormatAuditTrail:
    def test_no_events_returns_no_events_message(self):
        stage = _empty_stage()
        result = format_audit_trail(stage, "ast_ghost")
        assert "No events found" in result
        assert "ast_ghost" in result

    def test_single_event_formatted(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        result = format_audit_trail(stage, "ast_001")
        assert "ast_001" in result
        assert "assertion_created" in result
        assert "ai" in result
        assert "1 events" in result

    def test_multiple_events_all_listed(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        stage.record_event(EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001")
        stage.record_event(EventType.ASSERTION_FALSIFIED, AssertionAuthor.SYSTEM, "ast_001")
        result = format_audit_trail(stage, "ast_001")
        assert "3 events" in result
        assert "assertion_created" in result
        assert "assertion_challenged" in result
        assert "assertion_falsified" in result

    def test_detail_dict_included_in_output(self):
        stage = _empty_stage()
        stage.record_event(
            EventType.ASSERTION_CREATED,
            AssertionAuthor.AI,
            "ast_001",
            {"content": "PostgreSQL"},
        )
        result = format_audit_trail(stage, "ast_001")
        assert "content" in result
        assert "PostgreSQL" in result

    def test_format_contains_timestamp(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        result = format_audit_trail(stage, "ast_001")
        # Timestamps are formatted as YYYY-MM-DD HH:MM:SS
        assert "-" in result and ":" in result

    def test_each_event_on_own_line(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        stage.record_event(EventType.ASSERTION_PROMOTED, AssertionAuthor.AI, "ast_001")
        result = format_audit_trail(stage, "ast_001")
        lines = result.strip().split("\n")
        # Header line + 2 event lines
        assert len(lines) == 3


# ═══════════════════════════════════════════════════════════════
# TestCountEventsByType
# ═══════════════════════════════════════════════════════════════

class TestCountEventsByType:
    def test_empty_stage_returns_empty_dict(self):
        stage = _empty_stage()
        result = count_events_by_type(stage)
        assert result == {}

    def test_single_type_counted(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        result = count_events_by_type(stage)
        assert result == {"assertion_created": 1}

    def test_multiple_types_correct_counts(self):
        stage = _stage_with_mixed_events()
        result = count_events_by_type(stage)
        assert result["assertion_created"] == 2
        assert result["conflict_detected"] == 1
        assert result["assertion_challenged"] == 1
        assert result["conflict_resolved"] == 1

    def test_repeated_type_increments_count(self):
        stage = _empty_stage()
        for _ in range(5):
            stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        result = count_events_by_type(stage)
        assert result["assertion_created"] == 5

    def test_types_with_zero_events_omitted(self):
        stage = _empty_stage()
        stage.record_event(EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001")
        result = count_events_by_type(stage)
        assert "assertion_created" not in result
        assert "conflict_detected" in result


# ═══════════════════════════════════════════════════════════════
# TestGetConflictResolutionHistory
# ═══════════════════════════════════════════════════════════════

class TestGetConflictResolutionHistory:
    def test_no_conflict_events_returns_empty(self):
        stage = _empty_stage()
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        stage.record_event(EventType.ASSERTION_CHALLENGED, AssertionAuthor.SYSTEM, "ast_001")
        result = get_conflict_resolution_history(stage)
        assert result == []

    def test_conflict_detected_included(self):
        stage = _empty_stage()
        stage.record_event(EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001")
        result = get_conflict_resolution_history(stage)
        assert len(result) == 1
        assert result[0].event_type == EventType.CONFLICT_DETECTED

    def test_conflict_resolved_included(self):
        stage = _empty_stage()
        stage.record_event(EventType.CONFLICT_RESOLVED, AssertionAuthor.AI, "cfl_001")
        result = get_conflict_resolution_history(stage)
        assert len(result) == 1
        assert result[0].event_type == EventType.CONFLICT_RESOLVED

    def test_experiment_proposed_included(self):
        stage = _empty_stage()
        stage.record_event(
            EventType.CONFLICT_EXPERIMENT_PROPOSED, AssertionAuthor.AI, "cfl_001"
        )
        result = get_conflict_resolution_history(stage)
        assert len(result) == 1
        assert result[0].event_type == EventType.CONFLICT_EXPERIMENT_PROPOSED

    def test_experiment_resolved_included(self):
        stage = _empty_stage()
        stage.record_event(
            EventType.CONFLICT_EXPERIMENT_RESOLVED, AssertionAuthor.SYSTEM, "cfl_001"
        )
        result = get_conflict_resolution_history(stage)
        assert len(result) == 1
        assert result[0].event_type == EventType.CONFLICT_EXPERIMENT_RESOLVED

    def test_mixed_events_only_conflict_related_returned(self):
        stage = _stage_with_mixed_events()
        result = get_conflict_resolution_history(stage)
        for evt in result:
            assert evt.event_type in {
                EventType.CONFLICT_DETECTED,
                EventType.CONFLICT_RESOLVED,
                EventType.CONFLICT_EXPERIMENT_PROPOSED,
                EventType.CONFLICT_EXPERIMENT_RESOLVED,
            }

    def test_mixed_events_correct_count(self):
        stage = _stage_with_mixed_events()
        result = get_conflict_resolution_history(stage)
        # _stage_with_mixed_events has CONFLICT_DETECTED + CONFLICT_RESOLVED
        assert len(result) == 2

    def test_results_sorted_chronologically(self):
        stage = _empty_stage()
        stage.record_event(EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001")
        stage.record_event(EventType.CONFLICT_RESOLVED, AssertionAuthor.AI, "cfl_001")
        result = get_conflict_resolution_history(stage)
        assert result[0].event_type == EventType.CONFLICT_DETECTED
        assert result[1].event_type == EventType.CONFLICT_RESOLVED

    def test_empty_stage_returns_empty(self):
        stage = _empty_stage()
        result = get_conflict_resolution_history(stage)
        assert result == []
