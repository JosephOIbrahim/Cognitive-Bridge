"""Provenance engine — audit trail queries over the event log.

Events are appended via CompositionStage.record_event(). This module
provides query functions to inspect the audit trail: filtering by type,
target, actor, time range, and producing human-readable audit summaries.

All functions are pure — they read the stage's event list and return
results without modifying any state.
"""

from datetime import datetime
from typing import Optional

from cognitive_bridge.models.arcs import AssertionAuthor, EventType
from cognitive_bridge.models.event import Event
from cognitive_bridge.models.stage import CompositionStage


def get_events_for_target(stage: CompositionStage, target_id: str) -> list[Event]:
    """Get all events related to a specific target (assertion, conflict, etc.).

    This function serves as the implementation of assertion lifecycle history
    (patent: state_history). Rather than storing a denormalized state_history
    field on each assertion, lifecycle transitions are recorded as immutable
    Event objects in the append-only audit log. This approach provides richer
    provenance (actor, timestamp, detail) than a simple state list would.

    Args:
        stage: The composition stage to query.
        target_id: The ID of the target entity.

    Returns:
        List of events for that target, ordered by timestamp (oldest first).
    """
    return sorted(
        [e for e in stage.events if e.target_id == target_id],
        key=lambda e: e.timestamp,
    )


def get_events_by_type(stage: CompositionStage, event_type: EventType) -> list[Event]:
    """Get all events of a specific type.

    Args:
        stage: The composition stage to query.
        event_type: The EventType to filter by.

    Returns:
        List of matching events, ordered by timestamp (oldest first).
    """
    return sorted(
        [e for e in stage.events if e.event_type == event_type],
        key=lambda e: e.timestamp,
    )


def get_events_by_actor(stage: CompositionStage, actor: AssertionAuthor) -> list[Event]:
    """Get all events performed by a specific actor.

    Args:
        stage: The composition stage to query.
        actor: The actor to filter by.

    Returns:
        List of matching events, ordered by timestamp (oldest first).
    """
    return sorted(
        [e for e in stage.events if e.actor == actor],
        key=lambda e: e.timestamp,
    )


def get_events_in_range(
    stage: CompositionStage,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
) -> list[Event]:
    """Get events within a time range.

    Both bounds are exclusive. Timezone info is stripped before comparison
    so naive and aware datetimes can be mixed safely.

    Args:
        stage: The composition stage to query.
        after: Only events strictly after this timestamp (exclusive).
        before: Only events strictly before this timestamp (exclusive).

    Returns:
        List of matching events, ordered by timestamp (oldest first).
    """
    events = list(stage.events)
    if after is not None:
        after_naive = after.replace(tzinfo=None)
        events = [
            e for e in events
            if e.timestamp.replace(tzinfo=None) > after_naive
        ]
    if before is not None:
        before_naive = before.replace(tzinfo=None)
        events = [
            e for e in events
            if e.timestamp.replace(tzinfo=None) < before_naive
        ]
    return sorted(events, key=lambda e: e.timestamp)


def get_cascade_history(stage: CompositionStage, assertion_id: str) -> list[Event]:
    """Get the cascade history for an assertion.

    Returns all CHALLENGED, FALSIFIED, and ORPHANED events for the given
    assertion ID. Useful for understanding why an assertion's assumption
    status changed.

    Args:
        stage: The composition stage to query.
        assertion_id: The assertion to trace.

    Returns:
        List of cascade-related events for that assertion, oldest first.
    """
    cascade_types = {
        EventType.ASSERTION_CHALLENGED,
        EventType.ASSERTION_FALSIFIED,
        EventType.ASSERTION_ORPHANED,
    }
    return sorted(
        [
            e for e in stage.events
            if e.target_id == assertion_id and e.event_type in cascade_types
        ],
        key=lambda e: e.timestamp,
    )


def format_audit_trail(stage: CompositionStage, target_id: str) -> str:
    """Format a human-readable audit trail for a target entity.

    Args:
        stage: The composition stage to query.
        target_id: The ID of the entity to audit.

    Returns:
        Formatted string with the full event history for that entity.
        Returns a "no events" message if the target has no events.
    """
    events = get_events_for_target(stage, target_id)
    if not events:
        return f"No events found for {target_id}."

    lines = [f"Audit trail for {target_id} ({len(events)} events):"]
    for evt in events:
        ts = evt.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        detail_str = ""
        if evt.detail:
            detail_items = [f"{k}={v}" for k, v in evt.detail.items()]
            detail_str = f" [{', '.join(detail_items)}]"
        lines.append(
            f"  [{ts}] {evt.event_type.value} by {evt.actor.value}{detail_str}"
        )

    return "\n".join(lines)


def count_events_by_type(stage: CompositionStage) -> dict[EventType, int]:
    """Count events grouped by event type.

    Keys are EventType enum instances (not their string values). Callers that
    pattern-match on EventType members get correct hits without round-tripping
    through .value.

    Args:
        stage: The composition stage to query.

    Returns:
        Dict mapping EventType enum members to their occurrence counts.
        Types with zero events are omitted.
    """
    counts: dict[EventType, int] = {}
    for evt in stage.events:
        counts[evt.event_type] = counts.get(evt.event_type, 0) + 1
    return counts


def get_conflict_resolution_history(stage: CompositionStage) -> list[Event]:
    """Get all conflict detection and resolution events in chronological order.

    Covers CONFLICT_DETECTED, CONFLICT_RESOLVED, CONFLICT_EXPERIMENT_PROPOSED,
    and CONFLICT_EXPERIMENT_RESOLVED. Useful for reviewing the full
    argumentation history of the stage.

    Args:
        stage: The composition stage to query.

    Returns:
        Conflict-related events in chronological order (oldest first).
    """
    conflict_types = {
        EventType.CONFLICT_DETECTED,
        EventType.CONFLICT_RESOLVED,
        EventType.CONFLICT_EXPERIMENT_PROPOSED,
        EventType.CONFLICT_EXPERIMENT_RESOLVED,
    }
    return sorted(
        [e for e in stage.events if e.event_type in conflict_types],
        key=lambda e: e.timestamp,
    )
