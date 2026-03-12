"""cb_manage_conflict tool — resolve, challenge, defer, create, propose_experiment.

This tool is the primary interface for the argumentation protocol. Every conflict
lifecycle event — challenge, deferral, experiment proposal, or resolution — flows
through here. The steelman and experiment gates are hard gates: the function returns
an error string when required fields are absent, forcing proper epistemics before
action.
"""

from typing import Optional

from fastmcp import Context

from cognitive_bridge.models import (
    AssertionAuthor,
    Conflict,
    ConflictDetectionLayer,
    EventType,
    ResolutionPath,
    CompositionStage,
)
from cognitive_bridge.engine.resolver import resolve_conflict
from cognitive_bridge.server import mcp, save_stage_to_db


# ═══════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════


def _get_active_stage(
    ctx: Context, project_id: Optional[str] = None
) -> tuple[str, CompositionStage]:
    """Return the (project_id, stage) pair for the active project.

    Raises ValueError if no project is active, the specified project is not
    active, or multiple projects are active without a project_id to disambiguate.
    """
    active_stages = ctx.lifespan_context["active_stages"]
    if not active_stages:
        raise ValueError(
            "No active project. Call cb_manage_project(action='create') first."
        )
    if project_id:
        if project_id not in active_stages:
            raise ValueError(f"Project '{project_id}' is not active.")
        return project_id, active_stages[project_id]
    if len(active_stages) == 1:
        pid = next(iter(active_stages))
        return pid, active_stages[pid]
    raise ValueError(
        f"Multiple active projects ({', '.join(active_stages)}). "
        "Specify project_id to disambiguate."
    )


# ═══════════════════════════════════════════════════════════════
# cb_manage_conflict Tool
# ═══════════════════════════════════════════════════════════════


@mcp.tool(
    name="cb_manage_conflict",
    annotations={
        "title": "Manage Conflicts",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def cb_manage_conflict(
    action: str,
    ctx: Context,
    conflict_id: Optional[str] = None,
    resolution: Optional[str] = None,
    evidence: Optional[str] = None,
    note: Optional[str] = None,
    steelman_summary: Optional[str] = None,
    experiment_protocol: Optional[str] = None,
    experiment_result: Optional[str] = None,
    assertion_a_id: Optional[str] = None,
    assertion_b_id: Optional[str] = None,
    topic_path: Optional[str] = None,
    project_id: Optional[str] = None,
) -> str:
    """CRITICAL: Use this tool for every conflict lifecycle event. Do NOT ignore active conflicts.

    Conflicts are first-class composition events, not errors. An unresolved
    conflict means two assertions are fighting for the same epistemic territory.
    You MUST engage with every active conflict before making decisions at the
    affected path.

    STEELMAN GATE (action='challenge'): You MUST provide steelman_summary — the
    strongest, most charitable version of the opposing view. If you cannot
    articulate why someone might hold the opposing position, you have not
    understood it well enough to challenge it. Comprehension before critique.

    EXPERIMENT GATE (action='propose_experiment'): You MUST provide
    experiment_protocol — a concrete, testable protocol (observable outcome,
    measurement, threshold) that could settle the debate empirically.

    Actions:
    - resolve: Close a conflict with a chosen resolution path. resolution must be
      one of: accept, promote, synthesize, dismiss, defer.
    - challenge: Register a formal challenge. The conflict stays ACTIVE for
      further negotiation. Requires steelman_summary.
    - defer: Mark a conflict as deferred (to be resolved later).
    - create: Manually create a conflict between two existing assertions at a path.
      Used when Layer 3 (Claude) detects a semantic conflict not caught by Layer 1.
    - propose_experiment: Propose an empirical experiment to settle the debate.
      Requires experiment_protocol.

    Args:
        action: resolve | challenge | defer | create | propose_experiment
        conflict_id: Required for resolve, challenge, defer, propose_experiment.
        resolution: Resolution path for 'resolve': accept | promote | synthesize |
            dismiss. (Use action='defer' to defer; action='challenge' to challenge.)
        evidence: Supporting evidence for the resolution or challenge.
        note: Additional free-text context.
        steelman_summary: Required for challenge. The strongest version of the
            opposing view. Must be substantive — not a strawman.
        experiment_protocol: Required for propose_experiment. Concrete testable
            protocol: what will you measure, what threshold decides the outcome.
        experiment_result: Result of a completed experiment (optional, for record-keeping).
        assertion_a_id: Required for create. The stronger/newer assertion.
        assertion_b_id: Required for create. The weaker/dependent assertion.
        topic_path: Required for create. The path where the conflict occurs.
        project_id: Optional when only one project is active in memory.
    """
    try:
        pid, stage = _get_active_stage(ctx, project_id)
    except ValueError as exc:
        return f"ERROR: {exc}"

    store = ctx.lifespan_context["store"]

    # ── resolve ──────────────────────────────────────────────
    if action == "resolve":
        if not conflict_id:
            return "ERROR: 'conflict_id' is required for action='resolve'."
        if not resolution:
            return (
                "ERROR: 'resolution' path is required for action='resolve'. "
                "Valid paths: accept, promote, synthesize, dismiss."
            )
        try:
            path = ResolutionPath(resolution)
        except ValueError:
            valid = ", ".join(r.value for r in ResolutionPath)
            return (
                f"ERROR: Invalid resolution '{resolution}'. "
                f"Valid resolution paths: {valid}"
            )
        # Prevent using 'challenge' and 'defer' via 'resolve' — they have dedicated actions.
        if path in (ResolutionPath.CHALLENGE, ResolutionPath.DEFER):
            return (
                f"ERROR: Use action='{path.value}' directly instead of "
                f"action='resolve' with resolution='{path.value}'."
            )
        try:
            conflict = resolve_conflict(
                stage,
                conflict_id,
                path,
                evidence=evidence,
                note=note,
                steelman_summary=steelman_summary,
                experiment_protocol=experiment_protocol,
            )
        except ValueError as exc:
            return f"ERROR: {exc}"

        save_stage_to_db(store, stage)
        lines = [
            f"Conflict {conflict_id} resolved.",
            f"Resolution: {path.value}",
            f"Status: {conflict.status.value}",
        ]
        if evidence:
            lines.append(f"Evidence: {evidence}")
        if note:
            lines.append(f"Note: {note}")
        return "\n".join(lines)

    # ── challenge ─────────────────────────────────────────────
    elif action == "challenge":
        if not conflict_id:
            return "ERROR: 'conflict_id' is required for action='challenge'."
        if not steelman_summary:
            return (
                "ERROR: 'steelman_summary' is required for action='challenge'.\n"
                "You MUST articulate the strongest, most charitable version of the "
                "opposing view before you can challenge it. "
                "Comprehension before critique. What is the best possible reason "
                "someone would hold the position you are challenging?"
            )
        try:
            conflict = resolve_conflict(
                stage,
                conflict_id,
                ResolutionPath.CHALLENGE,
                evidence=evidence,
                note=note,
                steelman_summary=steelman_summary,
            )
        except ValueError as exc:
            return f"ERROR: {exc}"

        save_stage_to_db(store, stage)
        lines = [
            f"Challenge registered for conflict {conflict_id}.",
            f"Steelman: {steelman_summary}",
            "The conflict remains ACTIVE for further negotiation.",
        ]
        if evidence:
            lines.append(f"Challenge evidence: {evidence}")
        if note:
            lines.append(f"Note: {note}")
        return "\n".join(lines)

    # ── defer ─────────────────────────────────────────────────
    elif action == "defer":
        if not conflict_id:
            return "ERROR: 'conflict_id' is required for action='defer'."
        try:
            conflict = resolve_conflict(
                stage,
                conflict_id,
                ResolutionPath.DEFER,
                evidence=evidence,
                note=note,
            )
        except ValueError as exc:
            return f"ERROR: {exc}"

        save_stage_to_db(store, stage)
        lines = [
            f"Conflict {conflict_id} deferred.",
            f"Status: {conflict.status.value}",
        ]
        if note:
            lines.append(f"Reason: {note}")
        else:
            lines.append("No reason provided.")
        return "\n".join(lines)

    # ── create ────────────────────────────────────────────────
    elif action == "create":
        if not assertion_a_id or not assertion_b_id:
            return (
                "ERROR: Both 'assertion_a_id' and 'assertion_b_id' are required "
                "for action='create'."
            )
        if not topic_path:
            return "ERROR: 'topic_path' is required for action='create'."
        if assertion_a_id not in stage.assertions:
            return f"ERROR: Assertion '{assertion_a_id}' not found in the active stage."
        if assertion_b_id not in stage.assertions:
            return f"ERROR: Assertion '{assertion_b_id}' not found in the active stage."

        new_conflict = Conflict(
            assertion_a_id=assertion_a_id,
            assertion_b_id=assertion_b_id,
            topic_path=topic_path,
            detection_layer=ConflictDetectionLayer.DELEGATED,
        )
        stage.conflicts[new_conflict.id] = new_conflict
        stage.record_event(
            EventType.CONFLICT_DETECTED,
            AssertionAuthor.AI,
            new_conflict.id,
            {
                "layer": "delegated",
                "assertion_a": assertion_a_id,
                "assertion_b": assertion_b_id,
                "manual": True,
                "topic_path": topic_path,
            },
        )
        save_stage_to_db(store, stage)
        return (
            f"Conflict created: {new_conflict.id}\n"
            f"Between: {assertion_a_id} vs {assertion_b_id}\n"
            f"At path: {topic_path}\n"
            f"Layer: DELEGATED (manually created by Claude)\n"
            f"Status: {new_conflict.status.value}\n"
            "Use cb_manage_conflict(action='resolve'|'challenge'|'defer'|'propose_experiment') to act."
        )

    # ── propose_experiment ────────────────────────────────────
    elif action == "propose_experiment":
        if not conflict_id:
            return "ERROR: 'conflict_id' is required for action='propose_experiment'."
        if not experiment_protocol:
            return (
                "ERROR: 'experiment_protocol' is required for action='propose_experiment'.\n"
                "You MUST define a concrete, testable protocol before proposing an experiment. "
                "Specify: what will you measure, how, and what observable threshold "
                "decides the outcome between the two conflicting assertions?"
            )
        try:
            conflict = resolve_conflict(
                stage,
                conflict_id,
                ResolutionPath.PROPOSE_EXPERIMENT,
                evidence=evidence,
                note=note,
                experiment_protocol=experiment_protocol,
            )
        except ValueError as exc:
            return f"ERROR: {exc}"

        save_stage_to_db(store, stage)
        lines = [
            f"Experiment proposed for conflict {conflict_id}.",
            f"Protocol: {experiment_protocol}",
            f"Status: {conflict.status.value}",
            (
                f"Next step: run the experiment, then call "
                f"cb_manage_conflict(action='resolve', conflict_id='{conflict_id}', "
                f"resolution='accept', evidence='<results>') to close."
            ),
        ]
        if experiment_result:
            lines.append(f"Experiment result recorded: {experiment_result}")
        return "\n".join(lines)

    # ── unknown action ────────────────────────────────────────
    else:
        return (
            f"ERROR: Unknown action '{action}'. "
            "Valid actions: resolve, challenge, defer, create, propose_experiment."
        )
