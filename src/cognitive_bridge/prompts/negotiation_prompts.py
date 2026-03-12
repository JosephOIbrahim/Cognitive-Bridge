"""MCP Prompts — structured prompt templates for the argumentation protocol.

Three prompts guide Claude through the composition stage:
- coworker_posture: determines current engagement level (LEARNING / ENGAGED /
  AUTHORITATIVE / RED_TEAMING) based on stage depth and conflict state.
- conflict_negotiation: structured frame for working through a specific conflict.
- stage_summary: comprehensive snapshot of current stage state.

Prompts are read-only — they never modify stage state.
"""

from fastmcp import Context

from cognitive_bridge.models import (
    CompositionArc,
    CompositionStage,
    ConflictStatus,
)
from cognitive_bridge.server import mcp

# ═══════════════════════════════════════════════════════════════
# Internal Helper
# ═══════════════════════════════════════════════════════════════


def _get_stage_summary(stage: CompositionStage) -> dict:
    """Compute summary statistics for a composition stage.

    Args:
        stage: The stage to summarise.

    Returns:
        Dict with keys: paths, assertions, active_conflicts, local_count,
        payload_count, decisions.
    """
    resolved = stage.resolve()
    active_conflicts = sum(
        1 for c in stage.conflicts.values() if c.status == ConflictStatus.ACTIVE
    )
    local_count = sum(
        1
        for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.LOCAL
    )
    payload_count = sum(
        1
        for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.PAYLOADS
    )
    return {
        "paths": len(resolved),
        "assertions": len([a for a in stage.assertions.values() if a.active]),
        "active_conflicts": active_conflicts,
        "local_count": local_count,
        "payload_count": payload_count,
        "decisions": len(stage.decisions),
    }


# ═══════════════════════════════════════════════════════════════
# coworker_posture
# ═══════════════════════════════════════════════════════════════


@mcp.prompt(name="coworker_posture")
async def coworker_posture(project_id: str, ctx: Context) -> str:
    """Determine the current coworker posture based on stage state.

    Four postures:
    - LEARNING: Few assertions, building understanding.
    - ENGAGED: Active conflicts present, negotiating positions.
    - AUTHORITATIVE: Many LOCAL assertions, no active conflicts.
    - RED_TEAMING: LOCAL count exceeds red_team_threshold with zero conflicts —
      echo chamber risk, hunt blind spots.
    """
    active_stages = ctx.lifespan_context.get("active_stages", {})
    stage = active_stages.get(project_id)
    if not stage:
        return (
            f"Project '{project_id}' not loaded. "
            "Use cb_manage_project action='load' first."
        )

    stats = _get_stage_summary(stage)

    if stats["assertions"] < 3:
        posture = "LEARNING"
        guidance = (
            "You are in LEARNING mode. Focus on understanding the problem space.\n"
            "- Ask clarifying questions before asserting.\n"
            "- Use SPECIALIZES or INHERITS arc, not LOCAL.\n"
            "- Do not challenge yet — you do not have enough context to hold a position.\n"
            "- Listen to the user's framing. Record what you observe, not conclusions.\n"
            "Critical thinking directives still apply:\n"
            "- Identify implicit assumptions in every claim you hear.\n"
            "- Map what you do not know (assert as PAYLOADS).\n"
            "- Prefer asking one focused question over asserting prematurely."
        )
    elif stats["active_conflicts"] > 0:
        posture = "ENGAGED"
        guidance = (
            f"You are in ENGAGED mode. {stats['active_conflicts']} active "
            f"conflict(s) require resolution.\n"
            "- BEFORE challenging: articulate the strongest version of the opposing view.\n"
            "- Look for synthesis: can both positions be partially correct?\n"
            "- Prefer PROPOSE_EXPERIMENT when empirical data could settle the debate.\n"
            "- Do not defer indefinitely. Deferring is acceptable only "
            "with a stated revisit condition.\n"
            "Critical thinking directives:\n"
            "- Steelman the view you disagree with. Disagreement is mechanical, not personal.\n"
            "- Second-order effects: what does resolving this conflict break downstream?\n"
            "- Charity: assume the other position is coherent before attacking it."
        )
    elif (
        stats["local_count"] >= stage.parameters.red_team_threshold
        and stats["active_conflicts"] == 0
    ):
        posture = "RED_TEAMING"
        guidance = (
            f"You are in RED_TEAMING mode. {stats['local_count']} LOCAL assertions "
            f"with zero active conflicts. This may indicate a consensus echo chamber.\n"
            "Your job is to hunt blind spots:\n"
            "1. Challenge your strongest LOCAL assertions. What evidence would falsify them?\n"
            "2. Create variant sets for alternatives you have not considered.\n"
            "3. Review falsifiable_if conditions — has any evidence emerged?\n"
            "4. Look for missing dependencies in the DAG.\n"
            "5. Ask: what would a hostile expert say about this stage?\n"
            "RED_TEAMING directives:\n"
            "- Devil's advocate is a mechanical requirement, not a personality trait.\n"
            "- Suspiciously stable stages are dangerous. Conflict-free does not mean correct.\n"
            "- Generate at least one VariantSet for a path you are currently certain about."
        )
    else:
        posture = "AUTHORITATIVE"
        guidance = (
            "You are in AUTHORITATIVE mode. Strong positions established.\n"
            "- Assert with confidence at LOCAL arc when you have verified evidence.\n"
            "- Surface payloads: what evidence have you not gathered yet?\n"
            "- Record decisions with alternatives_rejected and second_order_effects.\n"
            "- Remain open to new evidence — confidence is not certainty.\n"
            "Critical thinking directives:\n"
            "- Map second-order effects before every decision.\n"
            "- Ensure every LOCAL assertion has a falsifiable_if condition.\n"
            "- Check: which assumptions in this stage have never been challenged?"
        )

    return (
        f"Project: {project_id}\n"
        f"Posture: {posture}\n"
        f"Assertions: {stats['assertions']} ({stats['local_count']} LOCAL)\n"
        f"Active conflicts: {stats['active_conflicts']}\n"
        f"Pending payloads: {stats['payload_count']}\n"
        f"Decisions: {stats['decisions']}\n"
        f"\n"
        f"{guidance}"
    )


# ═══════════════════════════════════════════════════════════════
# conflict_negotiation
# ═══════════════════════════════════════════════════════════════


@mcp.prompt(name="conflict_negotiation")
async def conflict_negotiation(
    project_id: str, conflict_id: str, ctx: Context
) -> str:
    """Generate a negotiation frame for a specific conflict.

    Presents both positions, their provenance, and all available resolution
    paths with their requirements. Call this at the start of any conflict
    resolution session to orient both parties.
    """
    active_stages = ctx.lifespan_context.get("active_stages", {})
    stage = active_stages.get(project_id)
    if not stage:
        return (
            f"Project '{project_id}' not loaded. "
            "Use cb_manage_project action='load' first."
        )

    conflict = stage.conflicts.get(conflict_id)
    if not conflict:
        return f"Conflict '{conflict_id}' not found in project '{project_id}'."

    ast_a = stage.assertions.get(conflict.assertion_a_id)
    ast_b = stage.assertions.get(conflict.assertion_b_id)

    a_desc = (
        f"[{ast_a.arc.name}] {ast_a.content}"
        if ast_a
        else "(assertion not found)"
    )
    b_desc = (
        f"[{ast_b.arc.name}] {ast_b.content}"
        if ast_b
        else "(assertion not found)"
    )

    a_conf = f" (confidence={ast_a.confidence})" if ast_a else ""
    b_conf = f" (confidence={ast_b.confidence})" if ast_b else ""

    cascade_note = ""
    if conflict.cascade_source_path:
        cascade_note = (
            f"\nCascade origin: This conflict was triggered by a change at "
            f"'{conflict.cascade_source_path}'."
        )

    steelman_note = ""
    if conflict.steelman_of_opponent:
        steelman_note = (
            f"\nSteelman on record: {conflict.steelman_of_opponent}"
        )

    return (
        f"CONFLICT NEGOTIATION -- {conflict.id}\n"
        f"{'=' * 60}\n"
        f"Path: {conflict.topic_path}\n"
        f"Detection layer: {conflict.detection_layer.value}\n"
        f"Status: {conflict.status.value}\n"
        f"{cascade_note}"
        f"\n"
        f"Position A (assertion_a, stronger): {a_desc}{a_conf}\n"
        f"  ID: {conflict.assertion_a_id}\n"
        f"\n"
        f"Position B (assertion_b, weaker): {b_desc}{b_conf}\n"
        f"  ID: {conflict.assertion_b_id}\n"
        f"{steelman_note}\n"
        f"\n"
        f"Available resolution paths:\n"
        f"  ACCEPT         — Accept the stronger position as-is.\n"
        f"  PROMOTE        — Promote the weaker position with new evidence.\n"
        f"  CHALLENGE      — Challenge (REQUIRES steelman_summary of the view you oppose).\n"
        f"  SYNTHESIZE     — Merge both positions into a new unified claim.\n"
        f"  PROPOSE_EXPERIMENT — Settle with data (REQUIRES experiment_protocol).\n"
        f"  DEFER          — Table for later (state when and why you will revisit).\n"
        f"  DISMISS        — False alarm: these do not actually conflict.\n"
        f"\n"
        f"RULES:\n"
        f"1. Before CHALLENGE: call cb_manage_conflict with action='challenge' and\n"
        f"   provide steelman_summary articulating the strongest version of the\n"
        f"   position you disagree with.\n"
        f"2. Before PROPOSE_EXPERIMENT: define what you will measure and what threshold\n"
        f"   decides the outcome.\n"
        f"3. SYNTHESIZE should produce a VariantSet exploring the merged hypothesis.\n"
        f"4. DEFER is not avoidance — state a concrete revisit condition."
    )


# ═══════════════════════════════════════════════════════════════
# stage_summary
# ═══════════════════════════════════════════════════════════════


@mcp.prompt(name="stage_summary")
async def stage_summary(project_id: str, ctx: Context) -> str:
    """Generate a comprehensive summary of the current composition stage.

    Intended for session starts and checkpoints. Shows all key counters,
    paths requiring attention, and pending work items.
    """
    active_stages = ctx.lifespan_context.get("active_stages", {})
    stage = active_stages.get(project_id)
    if not stage:
        return (
            f"Project '{project_id}' not loaded. "
            "Use cb_manage_project action='load' first."
        )

    stats = _get_stage_summary(stage)
    resolved = stage.resolve()

    lines = [
        f"COMPOSITION STAGE SUMMARY -- {stage.project_name} ({project_id})",
        "=" * 60,
        "",
        f"Assertions: {stats['assertions']} active",
        f"  LOCAL: {stats['local_count']}",
        f"  Payloads: {stats['payload_count']}",
        f"Conflicts: {stats['active_conflicts']} active / {len(stage.conflicts)} total",
        f"Variant sets: {len(stage.variant_sets)}",
        f"Decisions: {stats['decisions']}",
        f"Events: {len(stage.events)}",
        f"Exchange count: {stage.exchange_count}",
        "",
    ]

    # Determine current posture label for context
    if stats["assertions"] < 3:
        posture = "LEARNING"
    elif stats["active_conflicts"] > 0:
        posture = "ENGAGED"
    elif (
        stats["local_count"] >= stage.parameters.red_team_threshold
        and stats["active_conflicts"] == 0
    ):
        posture = "RED_TEAMING"
    else:
        posture = "AUTHORITATIVE"

    lines.append(f"Current posture: {posture}")
    lines.append("")

    # Paths requiring attention
    attention_paths = [
        (path, entry)
        for path, entry in resolved.items()
        if entry["requires_negotiation"]
        or entry["active_conflicts"]
        or entry["health_issues"]
    ]

    if attention_paths:
        lines.append(f"PATHS REQUIRING ATTENTION ({len(attention_paths)}):")
        for path, entry in sorted(attention_paths, key=lambda x: x[0]):
            reasons = []
            if entry["requires_negotiation"]:
                reasons.append("same-arc tie")
            if entry["active_conflicts"]:
                reasons.append(f"{len(entry['active_conflicts'])} active conflict(s)")
            if entry["health_issues"]:
                reasons.append(
                    f"{len(entry['health_issues'])} health issue(s)"
                )
            lines.append(f"  {path}: {', '.join(reasons)}")
        lines.append("")

    # Open variant sets
    open_vs = [vs for vs in stage.variant_sets.values() if not vs.resolved]
    if open_vs:
        lines.append(f"OPEN VARIANT SETS ({len(open_vs)}):")
        for vs in open_vs:
            lines.append(
                f"  [{vs.id}] {vs.name} at {vs.topic_path}"
                f" ({len(vs.variants)} variants)"
            )
        lines.append("")

    return "\n".join(lines)
