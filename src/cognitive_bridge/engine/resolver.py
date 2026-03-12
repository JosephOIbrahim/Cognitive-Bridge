"""Resolution engine — LIVRPS resolution with shadow stacks, winner tracking, and cascade triggers.

This is the orchestration layer that ties together conflict detection, cascading,
and provenance into a coherent assertion lifecycle. It is the primary entry point
for all assertion mutations: add, promote, retract, falsify, and resolve conflict.

Design notes:
- get_current_winner() is a pure function: stage in, Assertion out (or None).
- add_assertion(), promote_assertion(), retract_assertion(), falsify_assertion()
  all mutate the stage (assertions dict, conflicts dict, events list). Side effects
  are intentional and documented per function.
- resolve_conflict() mutates the Conflict object in stage.conflicts.
- Winner change detection is critical: old_winner captured before mutation,
  new_winner computed after. If they differ, cascade fires.
"""

from dataclasses import dataclass, field
from typing import Optional

from cognitive_bridge.engine.cascade import check_falsification, detect_cascading_conflicts
from cognitive_bridge.engine.conflict_detector import detect_structural_conflict
from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictStatus,
    EventType,
    ResolutionPath,
    _now_utc,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage


@dataclass
class ResolutionResult:
    """Result of adding or modifying an assertion in the stage.

    Captures everything that happened: the assertion itself, any structural
    conflict detected, any cascading conflicts triggered, whether the winner
    at the path changed, and semantic warnings for Claude to evaluate.

    Attributes:
        assertion: The assertion that was added or modified.
        structural_conflict: Layer 1 conflict, if detected.
        cascading_conflicts: Layer 4 conflicts triggered by a winner change.
        winner_changed: True if the dominant assertion at the path shifted.
        previous_winner_id: ID of the winner before the operation (None if path was empty).
        new_winner_id: ID of the winner after the operation (None if path is now empty).
        semantic_warnings: Layer 2 warning dicts for Claude to evaluate (populated
            by the tool layer when cross_path_detection is enabled).
    """

    assertion: Assertion
    structural_conflict: Optional[Conflict] = None
    cascading_conflicts: list[Conflict] = field(default_factory=list)
    winner_changed: bool = False
    previous_winner_id: Optional[str] = None
    new_winner_id: Optional[str] = None
    semantic_warnings: list[dict] = field(default_factory=list)


def get_current_winner(stage: CompositionStage, topic_path: str) -> Optional[Assertion]:
    """Get the current winning assertion at a topic path.

    The winner is the strongest active assertion by LIVRPS ordering:
    lowest arc integer first, then highest confidence, then newest created_at.
    This mirrors sorted(active_at_path)[0] using Assertion.__lt__.

    Pure function: does not modify the stage.

    Args:
        stage: The composition stage to query.
        topic_path: The path to check.

    Returns:
        The winning Assertion, or None if no active assertions exist at this path.
    """
    active_at_path = [
        a for a in stage.assertions.values()
        if a.active and a.topic_path == topic_path
    ]
    if not active_at_path:
        return None
    return sorted(active_at_path)[0]


def add_assertion(stage: CompositionStage, assertion: Assertion) -> ResolutionResult:
    """Add an assertion to the stage and run the full detection pipeline.

    This is the primary entry point for the assertion lifecycle:
    1. Record the old winner at the assertion's path (if any).
    2. Add the assertion to stage.assertions.
    3. Record an ASSERTION_CREATED event.
    4. Run Layer 1 structural conflict detection.
    5. Determine the new winner.
    6. If the winner changed, run Layer 4 cascading conflict detection.
    7. Store any new Conflict objects in stage.conflicts.
    8. Return the full ResolutionResult.

    Side effects:
        - Adds assertion to stage.assertions.
        - May add Conflict objects to stage.conflicts.
        - Appends events to stage.events.
        - May set assumption_status=CHALLENGED on dependent assertions
          (via detect_cascading_conflicts when cascade_auto_challenge is True).

    Args:
        stage: The composition stage to modify.
        assertion: The assertion to add. Must not already be in stage.assertions.

    Returns:
        ResolutionResult with all detected conflicts and winner change info.
    """
    result = ResolutionResult(assertion=assertion)

    # 1. Record old winner before insertion.
    old_winner = get_current_winner(stage, assertion.topic_path)
    if old_winner:
        result.previous_winner_id = old_winner.id

    # 2. Add assertion to stage.
    stage.assertions[assertion.id] = assertion

    # 3. Record ASSERTION_CREATED event.
    stage.record_event(
        EventType.ASSERTION_CREATED,
        assertion.author,
        assertion.id,
        {
            "topic_path": assertion.topic_path,
            "arc": assertion.arc.value,
            "content": assertion.content[:100],
        },
    )

    # 4. Layer 1: structural conflict detection.
    structural = detect_structural_conflict(stage, assertion)
    if structural:
        result.structural_conflict = structural
        stage.conflicts[structural.id] = structural
        stage.record_event(
            EventType.CONFLICT_DETECTED,
            AssertionAuthor.SYSTEM,
            structural.id,
            {
                "layer": "structural",
                "assertion_a": structural.assertion_a_id,
                "assertion_b": structural.assertion_b_id,
                "topic_path": structural.topic_path,
            },
        )

    # 5. Determine new winner after insertion.
    new_winner = get_current_winner(stage, assertion.topic_path)
    if new_winner:
        result.new_winner_id = new_winner.id

    # 6. If winner changed, trigger Layer 4 cascading conflicts.
    if old_winner and new_winner and old_winner.id != new_winner.id:
        result.winner_changed = True
        cascades = detect_cascading_conflicts(
            stage, assertion.topic_path, new_winner.id
        )
        result.cascading_conflicts = cascades
        for cascade in cascades:
            stage.conflicts[cascade.id] = cascade
            stage.record_event(
                EventType.CONFLICT_DETECTED,
                AssertionAuthor.SYSTEM,
                cascade.id,
                {
                    "layer": "cascading",
                    "source_path": assertion.topic_path,
                    "dependent_id": cascade.assertion_b_id,
                },
            )

    return result


def promote_assertion(
    stage: CompositionStage,
    assertion_id: str,
    new_arc: CompositionArc,
    evidence: Optional[str] = None,
) -> ResolutionResult:
    """Promote an assertion to a stronger composition arc.

    Promotion means the arc integer decreases (e.g., INHERITS=20 → LOCAL=10).
    If promotion changes the winner at the path, Layer 4 cascades fire.

    Side effects:
        - Mutates assertion.arc on the target assertion.
        - Appends evidence to assertion.evidence if provided.
        - Records an ASSERTION_PROMOTED event.
        - May add Conflict objects to stage.conflicts.
        - Appends cascade events if the winner changes.

    Args:
        stage: The composition stage to modify.
        assertion_id: ID of the assertion to promote.
        new_arc: The target arc. Must be numerically lower (stronger) than current arc.
        evidence: Optional new evidence string to append to assertion.evidence.

    Returns:
        ResolutionResult capturing any winner changes and cascading conflicts.

    Raises:
        ValueError: If the assertion is not found, is inactive, or new_arc is not stronger.
    """
    assertion = stage.assertions.get(assertion_id)
    if not assertion:
        raise ValueError(f"Assertion '{assertion_id}' not found")
    if not assertion.active:
        raise ValueError(f"Cannot promote inactive assertion '{assertion_id}'")
    if new_arc >= assertion.arc:
        raise ValueError(
            f"New arc {new_arc.name} ({new_arc.value}) is not stronger than "
            f"current arc {assertion.arc.name} ({assertion.arc.value}). "
            f"Promotion requires a lower arc integer."
        )

    result = ResolutionResult(assertion=assertion)

    # Capture old winner before promotion.
    old_winner = get_current_winner(stage, assertion.topic_path)
    if old_winner:
        result.previous_winner_id = old_winner.id

    # Apply promotion.
    assertion.arc = new_arc
    if evidence:
        assertion.evidence.append(evidence)

    stage.record_event(
        EventType.ASSERTION_PROMOTED,
        AssertionAuthor.SYSTEM,
        assertion_id,
        {
            "new_arc": new_arc.value,
            "evidence": evidence,
        },
    )

    # Check for winner change after promotion.
    new_winner = get_current_winner(stage, assertion.topic_path)
    if new_winner:
        result.new_winner_id = new_winner.id

    if old_winner and new_winner and old_winner.id != new_winner.id:
        result.winner_changed = True
        cascades = detect_cascading_conflicts(
            stage, assertion.topic_path, new_winner.id
        )
        result.cascading_conflicts = cascades
        for cascade in cascades:
            stage.conflicts[cascade.id] = cascade

    return result


def retract_assertion(stage: CompositionStage, assertion_id: str) -> ResolutionResult:
    """Retract an assertion (deactivate it; never delete it).

    Per the critical invariant: no assertion is ever deleted. Retraction sets
    active=False and retracted_at=now. The assertion remains in stage.assertions
    and is excluded from resolve() and winner computation.

    If retraction changes the winner at the path (e.g., the winner was retracted),
    Layer 4 cascades fire for the new winner. If the path becomes empty,
    winner_changed=True and new_winner_id=None.

    Dependents of the retracted assertion's path are marked ORPHANED (their
    foundation is gone, not just shifted).

    Side effects:
        - Sets assertion.active = False.
        - Sets assertion.retracted_at = now.
        - Records an ASSERTION_RETRACTED event.
        - Sets assumption_status = ORPHANED on each active dependent.
        - Records ASSERTION_ORPHANED events for each dependent.
        - May add cascading Conflict objects to stage.conflicts.

    Args:
        stage: The composition stage to modify.
        assertion_id: ID of the assertion to retract.

    Returns:
        ResolutionResult capturing any winner changes and cascades.

    Raises:
        ValueError: If the assertion is not found or is already inactive.
    """
    assertion = stage.assertions.get(assertion_id)
    if not assertion:
        raise ValueError(f"Assertion '{assertion_id}' not found")
    if not assertion.active:
        raise ValueError(f"Assertion '{assertion_id}' is already retracted")

    result = ResolutionResult(assertion=assertion)

    # Capture old winner before retraction.
    old_winner = get_current_winner(stage, assertion.topic_path)
    if old_winner:
        result.previous_winner_id = old_winner.id

    # Retract (never delete).
    assertion.active = False
    assertion.retracted_at = _now_utc()

    stage.record_event(
        EventType.ASSERTION_RETRACTED,
        AssertionAuthor.SYSTEM,
        assertion_id,
        {"topic_path": assertion.topic_path},
    )

    # Mark all active dependents as ORPHANED — their foundation was removed entirely.
    dependents = stage.get_dependents(assertion.topic_path)
    for dep in dependents:
        dep.assumption_status = AssumptionStatus.ORPHANED
        stage.record_event(
            EventType.ASSERTION_ORPHANED,
            AssertionAuthor.SYSTEM,
            dep.id,
            {"reason": "dependency_retracted", "source": assertion_id},
        )

    # Check winner after retraction.
    new_winner = get_current_winner(stage, assertion.topic_path)
    if new_winner:
        result.new_winner_id = new_winner.id
        if old_winner and old_winner.id != new_winner.id:
            result.winner_changed = True
            cascades = detect_cascading_conflicts(
                stage, assertion.topic_path, new_winner.id
            )
            result.cascading_conflicts = cascades
            for cascade in cascades:
                stage.conflicts[cascade.id] = cascade
    elif old_winner:
        # Path is now empty — the previous winner was removed.
        result.winner_changed = True
        result.new_winner_id = None

    return result


def falsify_assertion(
    stage: CompositionStage,
    assertion_id: str,
    observed_condition: str,
) -> ResolutionResult:
    """Mark an assertion as falsified based on observed evidence.

    Delegates to check_falsification() from cascade.py (which marks the assertion
    FALSIFIED and its dependents ORPHANED), then deactivates the assertion and
    checks for winner changes.

    Note: The decision that the observed_condition meets the falsifiable_if
    criterion is Claude's responsibility (Layer 3 / delegated). Only call this
    when that determination has already been made.

    Side effects:
        - Calls check_falsification(), which sets assumption_status=FALSIFIED
          and records ASSERTION_FALSIFIED + ASSERTION_ORPHANED events.
        - Sets assertion.active = False.
        - Sets assertion.retracted_at = now.
        - May add cascading Conflict objects to stage.conflicts.

    Args:
        stage: The composition stage to modify.
        assertion_id: ID of the assertion to falsify.
        observed_condition: What was observed that meets the falsification condition.

    Returns:
        ResolutionResult capturing the falsification and any cascading conflicts.

    Raises:
        ValueError: If the assertion is not found or has no falsifiable_if condition.
    """
    assertion = stage.assertions.get(assertion_id)
    if not assertion:
        raise ValueError(f"Assertion '{assertion_id}' not found")
    if not assertion.falsifiable_if:
        raise ValueError(
            f"Assertion '{assertion_id}' has no falsifiable_if condition. "
            f"Only assertions with a declared falsification condition can be falsified. "
            f"LOCAL assertions always have this field; other arcs may omit it."
        )

    result = ResolutionResult(assertion=assertion)

    # Capture old winner before falsification.
    old_winner = get_current_winner(stage, assertion.topic_path)
    if old_winner:
        result.previous_winner_id = old_winner.id

    # Falsify via cascade engine (also marks dependents ORPHANED and records events).
    check_falsification(stage, assertion_id, observed_condition)

    # Deactivate the falsified assertion.
    assertion.active = False
    assertion.retracted_at = _now_utc()

    # Check winner after deactivation.
    new_winner = get_current_winner(stage, assertion.topic_path)
    if new_winner:
        result.new_winner_id = new_winner.id
        if old_winner and old_winner.id != new_winner.id:
            result.winner_changed = True
            cascades = detect_cascading_conflicts(
                stage, assertion.topic_path, new_winner.id
            )
            result.cascading_conflicts = cascades
            for cascade in cascades:
                stage.conflicts[cascade.id] = cascade
    elif old_winner:
        result.winner_changed = True
        result.new_winner_id = None

    return result


def resolve_conflict(
    stage: CompositionStage,
    conflict_id: str,
    resolution: ResolutionPath,
    evidence: Optional[str] = None,
    note: Optional[str] = None,
    steelman_summary: Optional[str] = None,
    experiment_protocol: Optional[str] = None,
) -> Conflict:
    """Resolve a conflict with a chosen resolution path.

    Validates gate conditions before applying:
    - CHALLENGE requires steelman_summary (Popperian comprehension gate).
    - PROPOSE_EXPERIMENT requires experiment_protocol (empirical gate).

    Resolution path → conflict status mapping:
    - ACCEPT      → RESOLVED_OVERRIDE
    - PROMOTE     → RESOLVED_PROMOTED
    - CHALLENGE   → ACTIVE (challenge continues the debate, doesn't close it)
    - DEFER       → DEFERRED
    - SYNTHESIZE  → RESOLVED_SYNTHESIZED
    - DISMISS     → DISMISSED
    - PROPOSE_EXPERIMENT → RESOLVED_EXPERIMENT

    Side effects:
        - Mutates the Conflict object in stage.conflicts.
        - Records a CONFLICT_RESOLVED or CONFLICT_EXPERIMENT_PROPOSED event.

    Args:
        stage: The composition stage containing the conflict.
        conflict_id: ID of the conflict to resolve.
        resolution: The chosen resolution strategy.
        evidence: Supporting evidence for the resolution (optional).
        note: Additional free-text note (optional).
        steelman_summary: Required for CHALLENGE. Strongest version of the opposing view.
        experiment_protocol: Required for PROPOSE_EXPERIMENT. Concrete testable protocol.

    Returns:
        The updated Conflict object.

    Raises:
        ValueError: If conflict not found, already resolved, steelman gate not met,
            or experiment gate not met.
    """
    conflict = stage.conflicts.get(conflict_id)
    if not conflict:
        raise ValueError(f"Conflict '{conflict_id}' not found")
    if conflict.status != ConflictStatus.ACTIVE:
        raise ValueError(
            f"Conflict '{conflict_id}' is not active (status: {conflict.status.value}). "
            f"Only ACTIVE conflicts can be resolved."
        )

    # Steelman gate: CHALLENGE requires steelman_summary.
    if resolution == ResolutionPath.CHALLENGE and not steelman_summary:
        raise ValueError(
            "CHALLENGE resolution requires steelman_summary. "
            "You must articulate the strongest version of the opposing view "
            "before you can challenge it. Comprehension before critique."
        )

    # Experiment gate: PROPOSE_EXPERIMENT requires experiment_protocol.
    if resolution == ResolutionPath.PROPOSE_EXPERIMENT and not experiment_protocol:
        raise ValueError(
            "PROPOSE_EXPERIMENT resolution requires experiment_protocol. "
            "You must define a concrete, testable protocol to settle this "
            "debate empirically. What observable outcome would decide the question?"
        )

    # Map resolution path to conflict status.
    # CHALLENGE is special: it keeps the conflict ACTIVE (the debate continues).
    status_map: dict[ResolutionPath, ConflictStatus] = {
        ResolutionPath.ACCEPT: ConflictStatus.RESOLVED_OVERRIDE,
        ResolutionPath.PROMOTE: ConflictStatus.RESOLVED_PROMOTED,
        ResolutionPath.CHALLENGE: ConflictStatus.ACTIVE,
        ResolutionPath.DEFER: ConflictStatus.DEFERRED,
        ResolutionPath.SYNTHESIZE: ConflictStatus.RESOLVED_SYNTHESIZED,
        ResolutionPath.DISMISS: ConflictStatus.DISMISSED,
        ResolutionPath.PROPOSE_EXPERIMENT: ConflictStatus.RESOLVED_EXPERIMENT,
    }

    # Apply resolution metadata.
    conflict.resolution_chosen = resolution
    conflict.resolution_evidence = evidence
    conflict.resolution_note = note
    conflict.steelman_of_opponent = steelman_summary
    conflict.experiment_protocol = experiment_protocol

    new_status = status_map.get(resolution, ConflictStatus.RESOLVED_OVERRIDE)
    if resolution != ResolutionPath.CHALLENGE:
        conflict.status = new_status
        conflict.resolved_at = _now_utc()

    # Record event: experiment proposals get their own event type.
    event_type = (
        EventType.CONFLICT_EXPERIMENT_PROPOSED
        if resolution == ResolutionPath.PROPOSE_EXPERIMENT
        else EventType.CONFLICT_RESOLVED
    )
    stage.record_event(
        event_type,
        AssertionAuthor.AI,
        conflict_id,
        {
            "resolution": resolution.value,
            "evidence": evidence,
        },
    )

    return conflict
