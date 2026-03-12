"""cb_decide tool — record decisions with alternatives and second-order effects.

This module implements the decision recording tool for the Cognitive Bridge MCP
server. It binds to the shared FastMCP instance via the @mcp.tool decorator
and is imported by server.py to trigger decorator registration.

Design notes:
- alternatives_rejected (min 1) and second_order_effects (min 1) are enforced by
  parsing and early-return error responses. This forces Claude to enumerate what
  it is giving up and what downstream constraints it is creating.
- Each second_order_effect auto-creates an INHERITS assertion at the decision
  path, making future composition aware of the decision's constraints.
- Pending PAYLOADS at/below the decision path are surfaced as a warning to
  encourage loading evidence before committing.
- A DECISION_RECORDED event plus one ASSERTION_CREATED event per constraint are
  appended to the stage audit log on every successful call.
"""

from typing import Optional

from fastmcp import Context

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    Decision,
    EventType,
)
from cognitive_bridge.server import mcp, save_stage_to_db


# ═══════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════


def _get_active_stage(
    ctx: Context, project_id: Optional[str] = None
) -> tuple[str, CompositionStage]:
    """Get the active stage from the lifespan context.

    Args:
        ctx: FastMCP context carrying lifespan_context with store and active_stages.
        project_id: Optional explicit project to look up.

    Returns:
        Tuple of (project_id, CompositionStage).

    Raises:
        ValueError: If no projects are active, the named project is not active,
            or multiple projects are active and project_id was not provided.
    """
    active_stages: dict[str, CompositionStage] = ctx.lifespan_context["active_stages"]
    if not active_stages:
        raise ValueError(
            "No active project. Call cb_manage_project(action='create') first."
        )
    if project_id:
        if project_id not in active_stages:
            raise ValueError(
                f"Project '{project_id}' is not active. Load it first with "
                f"cb_manage_project(action='load', project_id='{project_id}')."
            )
        return project_id, active_stages[project_id]
    if len(active_stages) == 1:
        pid = next(iter(active_stages))
        return pid, active_stages[pid]
    raise ValueError(
        f"Multiple active projects. Specify project_id. "
        f"Active: {list(active_stages.keys())}"
    )


# ═══════════════════════════════════════════════════════════════
# Tool
# ═══════════════════════════════════════════════════════════════


@mcp.tool(
    name="cb_decide",
    annotations={
        "title": "Record a Decision",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def cb_decide(
    topic_path: str,
    decision: str,
    rationale: str,
    alternatives_rejected: str,
    second_order_effects: str,
    ctx: Context,
    assertion_ids: Optional[str] = None,
    conflict_ids: Optional[str] = None,
    reversibility: str = "unknown",
    project_id: Optional[str] = None,
) -> str:
    """CRITICAL: Record a project decision with FULL accountability.

    YOU MUST NOT call this tool without naming:
    1. What alternatives you considered and rejected (alternatives_rejected).
    2. What downstream constraints this decision creates (second_order_effects).

    If you cannot name what you are giving up, you have not thought enough.
    If you cannot name what you are committing the project to, stop and think.

    Every decision constrains the future. Both fields are required gates — the
    tool returns an error if either is empty. This is not a soft suggestion.

    Second-order effects become INHERITS assertions at the decision path,
    permanently encoding the constraint in the composition stage.

    PAYLOAD WARNING: If pending PAYLOADS exist at this path, you will be warned.
    Load that evidence first — committing before reading known unknowns is
    an epistemically indefensible shortcut.

    Arguments:
        topic_path: The hierarchical path this decision governs (e.g., '/architecture/database').
        decision: What was decided (state the outcome clearly).
        rationale: Why this was decided (the reasoning, not a restatement of the decision).
        alternatives_rejected: Pipe-separated alternatives. Each entry should read
            'Alternative description — rejected because reason'. Minimum 1 required.
            Example: 'MongoDB — rejected because ACID guarantees needed | Redis — rejected because persistence model wrong'.
        second_order_effects: Pipe-separated downstream effects. Each entry describes
            a constraint or risk this decision creates. Minimum 1 required.
            Example: 'Schema migrations required on every model change | Horizontal scaling requires sharding strategy'.
        assertion_ids: Optional comma-separated assertion IDs that informed this decision.
        conflict_ids: Optional comma-separated conflict IDs resolved by this decision.
        reversibility: How reversible is this decision?
            'trivial' | 'moderate' | 'costly' | 'irreversible' | 'unknown'.
        project_id: Optional — omit if only one project is active.
    """
    try:
        pid, stage = _get_active_stage(ctx, project_id)
    except ValueError as e:
        return f"ERROR: {e}"

    store = ctx.lifespan_context["store"]

    # Parse pipe-separated lists — strip whitespace, drop empty entries
    alt_list = [a.strip() for a in alternatives_rejected.split("|") if a.strip()]
    effect_list = [e.strip() for e in second_order_effects.split("|") if e.strip()]
    ast_id_list = (
        [a.strip() for a in assertion_ids.split(",") if a.strip()]
        if assertion_ids
        else []
    )
    cfl_id_list = (
        [c.strip() for c in conflict_ids.split(",") if c.strip()]
        if conflict_ids
        else []
    )

    # Enforce anti-convergence gates — hard errors, not warnings
    if not alt_list:
        return (
            "ERROR: 'alternatives_rejected' must contain at least one alternative. "
            "Use pipe-separated format: 'Option A — rejected because X | Option B — rejected because Y'. "
            "If you cannot name what you are giving up, you have not thought enough."
        )
    if not effect_list:
        return (
            "ERROR: 'second_order_effects' must contain at least one downstream effect. "
            "Use pipe-separated format: 'Effect one | Effect two'. "
            "Every decision constrains the future. What does this commit the project to?"
        )

    # Check for pending PAYLOADS at/below this path before committing
    payloads = [
        a
        for a in stage.assertions.values()
        if a.active
        and a.arc == CompositionArc.PAYLOADS
        and a.topic_path.startswith(topic_path)
    ]

    # Create and validate the Decision model
    try:
        dec = Decision(
            topic_path=topic_path,
            decision=decision,
            rationale=rationale,
            alternatives_rejected=alt_list,
            second_order_effects=effect_list,
            assertion_ids=ast_id_list,
            conflict_ids=cfl_id_list,
            reversibility=reversibility,
        )
    except ValueError as e:
        return f"ERROR: Validation failed — {e}"

    stage.decisions.append(dec)
    stage.record_event(
        EventType.DECISION_RECORDED,
        AssertionAuthor.AI,
        dec.id,
        {
            "topic_path": topic_path,
            "decision": decision[:100],
            "alternatives_count": len(alt_list),
            "effects_count": len(effect_list),
            "reversibility": reversibility,
        },
    )

    # Auto-create INHERITS assertions from second_order_effects, encoding constraints
    created_constraints: list[Assertion] = []
    for effect in effect_list:
        constraint = Assertion(
            topic_path=topic_path,
            content=f"[Decision constraint] {effect}",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.SYSTEM,
            depends_on_paths=[],
            tags=["decision_constraint", dec.id],
        )
        stage.assertions[constraint.id] = constraint
        stage.record_event(
            EventType.ASSERTION_CREATED,
            AssertionAuthor.SYSTEM,
            constraint.id,
            {
                "source": "decision_second_order_effect",
                "decision_id": dec.id,
                "effect": effect[:100],
            },
        )
        created_constraints.append(constraint)

    save_stage_to_db(store, stage)

    # Build response
    lines: list[str] = [
        f"DECISION RECORDED: {dec.id}",
        f"Path:         {topic_path}",
        f"Decision:     {decision}",
        f"Rationale:    {rationale}",
        f"Reversibility: {reversibility}",
        "",
        f"Alternatives rejected ({len(alt_list)}):",
    ]
    for alt in alt_list:
        lines.append(f"  - {alt}")

    lines.append(f"\nSecond-order effects ({len(effect_list)}) — encoded as INHERITS constraints:")
    for effect, constraint in zip(effect_list, created_constraints):
        lines.append(f"  -> {effect}")
        lines.append(f"     Constraint assertion: {constraint.id}")

    if ast_id_list:
        lines.append(f"\nInformed by assertions: {', '.join(ast_id_list)}")
    if cfl_id_list:
        lines.append(f"Resolves conflicts: {', '.join(cfl_id_list)}")

    if payloads:
        lines.append(f"\nWARNING: {len(payloads)} pending payload(s) at/below {topic_path}:")
        for p in payloads:
            lines.append(f"  PAYLOAD [{p.id}] {p.topic_path}: {p.content}")
        lines.append(
            "You committed before loading known unknowns. "
            "Consider whether these payloads change your decision."
        )

    return "\n".join(lines)
