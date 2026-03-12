"""cb_payload_check tool — surface pending payloads at/below a path.

This module implements the payload inspection tool for the Cognitive Bridge MCP
server. It binds to the shared FastMCP instance via the @mcp.tool decorator
and is imported by server.py to trigger decorator registration.

Design notes:
- cb_payload_check is deliberately read-only (readOnlyHint=True). It never
  modifies the stage, records events, or persists anything.
- PAYLOADS assertions (arc=50) represent known unknowns: evidence that exists
  in the world but has not yet been loaded into the composition stage. They are
  epistemic placeholders, not active claims.
- The tool filters by path prefix (topic_path.startswith) so a check at
  '/architecture' surfaces payloads at '/architecture/database', etc.
- When decisions already recorded at overlapping paths are found, a WARNING
  block is emitted. This surfaces the risk of having committed before loading
  available evidence.
"""

from typing import Optional

from fastmcp import Context

from cognitive_bridge.models import (
    CompositionArc,
    CompositionStage,
)
from cognitive_bridge.server import mcp


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
    name="cb_payload_check",
    annotations={
        "title": "Check Pending Payloads",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def cb_payload_check(
    ctx: Context,
    topic_path: Optional[str] = None,
    project_id: Optional[str] = None,
) -> str:
    """CRITICAL: Surface pending PAYLOADS (known unknowns) at or below a path.

    PAYLOADS are assertions at arc=50. They represent evidence that EXISTS in
    the world but has not yet been loaded into the composition stage. They are
    epistemic placeholders — the system knows they are out there.

    YOU MUST call this before cb_decide to ensure you are not committing to a
    decision while ignoring available evidence. Committing before reading known
    unknowns is an epistemically indefensible shortcut.

    If no topic_path is provided, surfaces ALL payloads across the project.
    If topic_path is provided, surfaces only payloads at or below that prefix.

    Arguments:
        topic_path: Optional path prefix to filter. Surfaces payloads at and
            below this path (prefix match). E.g., '/architecture' will match
            '/architecture/database/engine'.
        project_id: Optional — omit if only one project is active.
    """
    try:
        _pid, stage = _get_active_stage(ctx, project_id)
    except ValueError as e:
        return f"ERROR: {e}"

    # Find all active PAYLOADS assertions
    payloads = [
        a
        for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.PAYLOADS
    ]

    # Filter by path prefix if provided
    if topic_path:
        payloads = [p for p in payloads if p.topic_path.startswith(topic_path)]

    # No payloads found — safe to proceed
    if not payloads:
        scope = f"at/below '{topic_path}'" if topic_path else "in the project"
        return f"No pending payloads {scope}. Safe to proceed with decisions."

    # Sort by path for readability
    payloads.sort(key=lambda p: p.topic_path)

    lines: list[str] = [
        f"PENDING PAYLOADS ({len(payloads)}):",
        f"Scope: {'at/below: ' + topic_path if topic_path else 'all paths'}",
        "",
    ]

    for p in payloads:
        lines.append(f"  [{p.id}] {p.topic_path}")
        lines.append(f"    {p.content}")
        if p.evidence:
            lines.append(f"    Evidence hints: {', '.join(p.evidence)}")
        if p.tags:
            lines.append(f"    Tags: {', '.join(p.tags)}")
        lines.append("")

    lines.append(
        "These represent evidence that exists but has not been loaded. "
        "Consider investigating before committing to decisions at these paths."
    )

    # Warn when existing decisions overlap with payload paths
    payload_paths = {p.topic_path for p in payloads}
    decisions_at_risk = [
        d
        for d in stage.decisions
        if any(
            d.topic_path.startswith(pp) or pp.startswith(d.topic_path)
            for pp in payload_paths
        )
    ]
    if decisions_at_risk:
        lines.append(
            f"\nWARNING: {len(decisions_at_risk)} decision(s) overlap with payload paths:"
        )
        for d in decisions_at_risk:
            snippet = d.decision[:60]
            if len(d.decision) > 60:
                snippet += "..."
            lines.append(f"  [{d.id}] {d.topic_path}: {snippet}")

    return "\n".join(lines)
