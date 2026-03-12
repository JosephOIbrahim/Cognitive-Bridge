"""RED_TEAMING engine — anti-echo-chamber posture escalation.

When the composition stage becomes suspiciously stable (many LOCAL assertions,
zero active conflicts), the AI should challenge its own strongest positions.

Conditions for activation (ALL must be true):
1. Number of active LOCAL assertions >= red_team_threshold
2. Zero active conflicts in the stage
3. At least one exchange has occurred (not a fresh stage)

This module provides:
- Detection of when RED_TEAMING should activate
- Identification of unchallenged assumptions
- Generation of devil's advocate analysis reports
- Audit event recording
"""

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictStatus,
    EventType,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.stage import CompositionStage


def should_trigger_red_team(stage: CompositionStage) -> bool:
    """Check if RED_TEAMING posture should activate.

    Conditions (ALL must be true):
    1. Number of active LOCAL assertions >= red_team_threshold
    2. Zero active conflicts in the stage
    3. At least one exchange has occurred (not a fresh stage)

    Args:
        stage: The composition stage to check.

    Returns:
        True if RED_TEAMING should activate.
    """
    local_count = sum(
        1 for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.LOCAL
    )

    active_conflicts = sum(
        1 for c in stage.conflicts.values()
        if c.status == ConflictStatus.ACTIVE
    )

    threshold = stage.parameters.red_team_threshold

    return (
        local_count >= threshold
        and active_conflicts == 0
        and stage.exchange_count > 0
    )


def find_unchallenged_locals(stage: CompositionStage) -> list[Assertion]:
    """Find LOCAL assertions that have never been involved in a conflict.

    These are the most dangerous — strongly held positions that have
    never been tested. They may be correct, or they may be blind spots.

    An assertion is "unchallenged" if its ID does not appear as either
    assertion_a_id or assertion_b_id in any conflict (regardless of
    that conflict's current status).

    Args:
        stage: The composition stage.

    Returns:
        List of active LOCAL assertions with no conflict history, sorted
        by created_at ascending (oldest first — the longer unchallenged,
        the more suspicious).
    """
    conflicted_ids: set[str] = set()
    for c in stage.conflicts.values():
        conflicted_ids.add(c.assertion_a_id)
        conflicted_ids.add(c.assertion_b_id)

    unchallenged = [
        a for a in stage.assertions.values()
        if a.active
        and a.arc == CompositionArc.LOCAL
        and a.id not in conflicted_ids
    ]

    return sorted(unchallenged, key=lambda a: a.created_at)


def find_unfalsifiable_locals(stage: CompositionStage) -> list[Assertion]:
    """Find LOCAL assertions whose falsifiable_if conditions could be checked.

    Returns active LOCAL assertions that have falsifiable_if set and are
    still in LIVE assumption status. These are candidates for falsification
    checking — the condition is declared but may not have been tested yet.

    Note: Due to the schema validator, all LOCAL assertions must have
    falsifiable_if. This function additionally filters for LIVE status
    to surface only those that have not yet been challenged or falsified.

    Args:
        stage: The composition stage.

    Returns:
        List of active LOCAL assertions with testable falsification conditions.
    """
    return [
        a for a in stage.assertions.values()
        if a.active
        and a.arc == CompositionArc.LOCAL
        and a.falsifiable_if
        and a.assumption_status == AssumptionStatus.LIVE
    ]


def find_missing_dependencies(stage: CompositionStage) -> list[Assertion]:
    """Find assertions that probably should have dependencies but don't.

    Heuristic: LOCAL and INHERITS assertions at paths that have a parent
    path also represented in the stage but declare no depends_on_paths.
    These assertions may form logical chains that aren't captured in the
    DAG, creating invisible coupling.

    Only LOCAL and INHERITS are checked — stronger arcs, more likely
    to carry logical dependencies. SPECIALIZES and weaker arcs are
    too general to require explicit dependency declarations.

    Args:
        stage: The composition stage.

    Returns:
        List of assertions that may be missing dependency declarations.
        No particular sort order guaranteed.
    """
    all_paths = {
        a.topic_path for a in stage.assertions.values() if a.active
    }

    suspects: list[Assertion] = []
    for a in stage.assertions.values():
        if not a.active:
            continue
        if a.arc not in (CompositionArc.LOCAL, CompositionArc.INHERITS):
            continue
        if a.depends_on_paths:
            continue  # Already has dependencies declared

        parts = a.topic_path.strip("/").split("/")
        if len(parts) < 2:
            continue  # Single-segment paths have no meaningful parent

        # Check whether the immediate parent path has active assertions
        parent = "/" + "/".join(parts[:-1])
        if parent in all_paths:
            suspects.append(a)

    return suspects


def generate_red_team_report(stage: CompositionStage) -> str:
    """Generate a RED_TEAMING analysis report.

    Analyses the stage for three categories of blind spot:
    1. Unchallenged LOCAL assertions — never been in any conflict
    2. Testable falsification conditions — LIVE claims with declared tests
    3. Potential missing DAG dependencies — assertions without depends_on_paths
       that have an active parent path

    The report header shows TRIGGERED or MONITORING status based on
    should_trigger_red_team().

    Args:
        stage: The composition stage.

    Returns:
        Formatted multi-line report string suitable for surface in tool
        responses or audit output.
    """
    unchallenged = find_unchallenged_locals(stage)
    falsifiable = find_unfalsifiable_locals(stage)
    missing_deps = find_missing_dependencies(stage)

    triggered = should_trigger_red_team(stage)

    local_count = sum(
        1 for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.LOCAL
    )
    active_conflicts = sum(
        1 for c in stage.conflicts.values()
        if c.status == ConflictStatus.ACTIVE
    )

    lines = [
        "RED TEAM ANALYSIS",
        f"{'=' * 40}",
        f"Status: {'TRIGGERED' if triggered else 'MONITORING'}",
        f"LOCAL assertions: {local_count} (threshold: {stage.parameters.red_team_threshold})",
        f"Active conflicts: {active_conflicts}",
        "",
    ]

    if unchallenged:
        lines.append(f"UNCHALLENGED LOCALS ({len(unchallenged)}):")
        lines.append("These positions have NEVER been tested by conflict.")
        for a in unchallenged[:5]:
            lines.append(f"  [{a.id}] {a.topic_path}: {a.content}")
            if a.falsifiable_if:
                lines.append(f"    Falsifiable if: {a.falsifiable_if}")
        if len(unchallenged) > 5:
            lines.append(f"  ... and {len(unchallenged) - 5} more")
        lines.append("")

    if falsifiable:
        lines.append(f"TESTABLE FALSIFICATION CONDITIONS ({len(falsifiable)}):")
        lines.append("These claims define how they can be proven wrong. Have conditions been met?")
        for a in falsifiable[:5]:
            lines.append(f"  [{a.id}] {a.topic_path}: {a.content}")
            lines.append(f"    Test: {a.falsifiable_if}")
        lines.append("")

    if missing_deps:
        lines.append(f"POTENTIAL MISSING DEPENDENCIES ({len(missing_deps)}):")
        lines.append("These assertions may need depends_on_paths declarations.")
        for a in missing_deps[:5]:
            lines.append(f"  [{a.id}] {a.topic_path}: {a.content}")
        lines.append("")

    if not unchallenged and not falsifiable and not missing_deps:
        lines.append("No blind spots detected. The stage appears well-tested.")

    return "\n".join(lines)


def record_red_team_trigger(stage: CompositionStage) -> None:
    """Record that RED_TEAMING was triggered.

    Appends a RED_TEAM_TRIGGERED event to the stage audit log. The
    event detail captures the current local_count and the threshold
    that was crossed, for provenance purposes.

    Side effect: mutates stage.events (append-only).

    Args:
        stage: The composition stage to record the event on.
    """
    local_count = sum(
        1 for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.LOCAL
    )

    stage.record_event(
        EventType.RED_TEAM_TRIGGERED,
        AssertionAuthor.SYSTEM,
        stage.project_id,
        {
            "local_count": local_count,
            "threshold": stage.parameters.red_team_threshold,
        },
    )
