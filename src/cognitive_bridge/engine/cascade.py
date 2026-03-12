"""Layer 4: Cascading conflict detection and falsification checking.

When the winning assertion at a topic_path changes, all assertions that
depend on that path (via depends_on_paths) are flagged as CHALLENGED.
This is the "compiler" for the reasoning DAG.

Side effects (documented):
- detect_cascading_conflicts() mutates assumption_status on dependent
  assertions when stage.parameters.cascade_auto_challenge is True.
- check_falsification() mutates assumption_status on the target assertion
  (→ FALSIFIED) and on all dependents of that assertion's topic_path
  (→ ORPHANED).
"""

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    ConflictDetectionLayer,
    EventType,
)
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage


def detect_cascading_conflicts(
    stage: CompositionStage,
    changed_path: str,
    new_winning_id: str,
) -> list[Conflict]:
    """When a foundation shifts, flag all dependent assertions.

    This is the "compiler" for the reasoning DAG. If an assumption
    changes, every downstream claim must be re-evaluated.

    Fires automatically when:
    - A new assertion overrides the previous winner at a path
    - An assertion is promoted past the current winner
    - An assertion is retracted, changing which claim wins

    Side effect (when cascade_auto_challenge is True):
        Sets assumption_status = CHALLENGED on each dependent assertion
        and appends an ASSERTION_CHALLENGED event for each one.

    Args:
        stage: The current composition stage.
        changed_path: The topic_path where the winner changed.
        new_winning_id: The ID of the new winning assertion.

    Returns:
        List of Conflict objects, one per dependent assertion found.
        Returns an empty list if there are no active dependents.
    """
    dependents = stage.get_dependents(changed_path)

    if not dependents:
        return []

    cascades: list[Conflict] = []
    for dep_assertion in dependents:
        # Mutate assumption_status when auto-challenge is enabled.
        if stage.parameters.cascade_auto_challenge:
            dep_assertion.assumption_status = AssumptionStatus.CHALLENGED
            stage.record_event(
                EventType.ASSERTION_CHALLENGED,
                AssertionAuthor.SYSTEM,
                dep_assertion.id,
                {
                    "reason": "dependency_shifted",
                    "source_path": changed_path,
                    "new_winner_id": new_winning_id,
                },
            )

        cascades.append(
            Conflict(
                assertion_a_id=new_winning_id,
                assertion_b_id=dep_assertion.id,
                topic_path=dep_assertion.topic_path,
                detection_layer=ConflictDetectionLayer.CASCADING,
                cascade_source_path=changed_path,
                resolution_note=(
                    f"EPISTEMIC CASCADE: The winning assertion at {changed_path} "
                    f"changed. This assertion depends on that path and must be "
                    f"re-evaluated. Is '{dep_assertion.content}' still valid "
                    f"given the new reality?"
                ),
            )
        )

    return cascades


def check_falsification(
    stage: CompositionStage,
    assertion_id: str,
    observed_condition: str,
) -> bool:
    """Check if an assertion's falsification condition has been met.

    If the assertion has a falsifiable_if field, marks it FALSIFIED and
    cascades ORPHANED status to all active assertions whose depends_on_paths
    includes the falsified assertion's topic_path.

    The server marks the status; semantic matching (does the observation
    meet the falsification criterion?) is delegated to Claude. Only call
    this function when Claude has determined the condition is genuinely met.

    Side effects:
        - Sets assumption_status = FALSIFIED on the target assertion.
        - Appends an ASSERTION_FALSIFIED event.
        - Sets assumption_status = ORPHANED on each dependent.
        - Appends an ASSERTION_ORPHANED event for each dependent.

    Args:
        stage: The current composition stage.
        assertion_id: ID of the assertion to check.
        observed_condition: The observation that meets the falsification
            criterion (stored in the provenance event).

    Returns:
        True if the assertion was falsified; False if the assertion was not
        found, has no falsifiable_if, or is already falsified/orphaned.
    """
    assertion = stage.assertions.get(assertion_id)
    if not assertion or not assertion.falsifiable_if:
        return False

    # Mark the assertion itself as FALSIFIED.
    assertion.assumption_status = AssumptionStatus.FALSIFIED
    stage.record_event(
        EventType.ASSERTION_FALSIFIED,
        AssertionAuthor.SYSTEM,
        assertion_id,
        {
            "falsifiable_if": assertion.falsifiable_if,
            "observed": observed_condition,
        },
    )

    # Cascade: all active assertions depending on this path become ORPHANED.
    dependents = stage.get_dependents(assertion.topic_path)
    for dep in dependents:
        dep.assumption_status = AssumptionStatus.ORPHANED
        stage.record_event(
            EventType.ASSERTION_ORPHANED,
            AssertionAuthor.SYSTEM,
            dep.id,
            {"reason": "dependency_falsified", "source": assertion_id},
        )

    return True
