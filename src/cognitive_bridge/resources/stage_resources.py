"""MCP Resources — read-only endpoints exposing composition stage state.

Six resources expose the current project's epistemic state without mutation:
- stage://{project_id}/resolved  — LIVRPS-resolved winners per topic path
- stage://{project_id}/conflicts — All conflicts (active, resolved, deferred)
- stage://{project_id}/variants  — All variant sets (open and resolved)
- stage://{project_id}/audit     — Event counts and recent activity log
- stage://{project_id}/dependencies — Dependency DAG view
- stage://{project_id}/payloads  — Pending PAYLOADS-arc assertions

All resource handlers are read-only and never modify stage state.
"""

from typing import Optional

from fastmcp import Context

from cognitive_bridge.engine.provenance import count_events_by_type
from cognitive_bridge.models import (
    CompositionArc,
    CompositionStage,
    ConflictStatus,
)
from cognitive_bridge.server import mcp


# ═══════════════════════════════════════════════════════════════
# Internal Helper
# ═══════════════════════════════════════════════════════════════


def _get_stage(ctx: Context, project_id: str) -> Optional[CompositionStage]:
    """Retrieve an active stage from the lifespan context registry.

    Args:
        ctx: FastMCP request context.
        project_id: The project identifier to look up.

    Returns:
        The CompositionStage if loaded, otherwise None.
    """
    active_stages = ctx.lifespan_context.get("active_stages", {})
    return active_stages.get(project_id)


# ═══════════════════════════════════════════════════════════════
# stage://{project_id}/resolved
# ═══════════════════════════════════════════════════════════════


@mcp.resource("stage://{project_id}/resolved")
async def get_resolved_state(project_id: str, ctx: Context) -> str:
    """Get the resolved composition state — winning assertions at each path.

    Shows the LIVRPS-resolved view: which assertion wins at each topic path,
    shadow stacks, negotiation flags, and health issues.
    """
    stage = _get_stage(ctx, project_id)
    if not stage:
        return f"Project '{project_id}' not loaded. Use cb_manage_project action='load' first."

    resolved = stage.resolve()
    if not resolved:
        return "Stage is empty. No assertions yet."

    lines = [f"Resolved state for '{project_id}' ({len(resolved)} paths):\n"]
    for path in sorted(resolved.keys()):
        entry = resolved[path]
        winner = entry["winning"]
        lines.append(f"PATH: {path}")
        lines.append(f"  Winner: [{winner.arc.name}] {winner.content}")
        lines.append(f"  ID: {winner.id} | Confidence: {winner.confidence}")
        lines.append(f"  Status: {winner.assumption_status.value}")

        if entry["requires_negotiation"]:
            lines.append("  WARNING: REQUIRES NEGOTIATION (same-arc tie at top)")
        if entry["shadow_stack"]:
            lines.append(f"  Shadow stack ({len(entry['shadow_stack'])}):")
            for s in entry["shadow_stack"]:
                lines.append(
                    f"    - [{s.arc.name}] {s.content} (id={s.id})"
                )
        if entry["active_conflicts"]:
            lines.append(f"  Active conflicts: {len(entry['active_conflicts'])}")
        if entry["pending_payloads"]:
            lines.append(f"  Pending payloads: {len(entry['pending_payloads'])}")
        if entry["health_issues"]:
            lines.append(f"  Health issues: {len(entry['health_issues'])}")
            for h in entry["health_issues"]:
                lines.append(f"    - {h.id}: {h.assumption_status.value}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# stage://{project_id}/conflicts
# ═══════════════════════════════════════════════════════════════


@mcp.resource("stage://{project_id}/conflicts")
async def get_conflicts_state(project_id: str, ctx: Context) -> str:
    """Get all conflicts — active, resolved, and deferred.

    Surfaces every conflict the detection engine has found, grouped by
    status. Active conflicts require resolution before the path is stable.
    """
    stage = _get_stage(ctx, project_id)
    if not stage:
        return f"Project '{project_id}' not loaded. Use cb_manage_project action='load' first."

    if not stage.conflicts:
        return "No conflicts detected."

    active = [
        c for c in stage.conflicts.values() if c.status == ConflictStatus.ACTIVE
    ]
    non_active = [
        c for c in stage.conflicts.values() if c.status != ConflictStatus.ACTIVE
    ]

    lines = [f"Conflicts for '{project_id}' ({len(stage.conflicts)} total):\n"]

    if active:
        lines.append(f"ACTIVE ({len(active)}):")
        for c in active:
            lines.append(f"  [{c.id}] {c.topic_path}")
            lines.append(f"    Layer: {c.detection_layer.value}")
            lines.append(f"    Between: {c.assertion_a_id} vs {c.assertion_b_id}")
            if c.cascade_source_path:
                lines.append(f"    Cascade from: {c.cascade_source_path}")
            if c.steelman_of_opponent:
                lines.append(
                    f"    Steelman: {c.steelman_of_opponent[:80]}"
                    + ("..." if len(c.steelman_of_opponent) > 80 else "")
                )
            lines.append("")

    if non_active:
        lines.append(f"RESOLVED/OTHER ({len(non_active)}):")
        for c in non_active:
            res = c.resolution_chosen.value if c.resolution_chosen else "none"
            lines.append(
                f"  [{c.id}] {c.topic_path} -> {c.status.value} (via {res})"
            )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# stage://{project_id}/variants
# ═══════════════════════════════════════════════════════════════


@mcp.resource("stage://{project_id}/variants")
async def get_variants_state(project_id: str, ctx: Context) -> str:
    """Get all variant sets — open and resolved.

    Variant sets hold competing hypotheses that haven't collapsed to a single
    winner yet. Open sets are live; resolved sets show which variant won.
    """
    stage = _get_stage(ctx, project_id)
    if not stage:
        return f"Project '{project_id}' not loaded. Use cb_manage_project action='load' first."

    if not stage.variant_sets:
        return "No variant sets."

    lines = [f"Variant sets for '{project_id}' ({len(stage.variant_sets)} total):\n"]
    for vs in stage.variant_sets.values():
        status = "RESOLVED" if vs.resolved else "OPEN"
        lines.append(f"[{vs.id}] {vs.name} at {vs.topic_path} -- {status}")
        for v in vs.variants:
            if vs.resolved and vs.resolved_variant_name == v.name:
                marker = "WINNER"
            else:
                marker = "     "
            lines.append(f"  [{marker}] {v.name}: {v.content}")
            lines.append(
                f"    Evidence for: {len(v.evidence_for)} | Against: {len(v.evidence_against)}"
            )
        if vs.resolved:
            lines.append(f"  Resolved winner: {vs.resolved_variant_name}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# stage://{project_id}/audit
# ═══════════════════════════════════════════════════════════════


@mcp.resource("stage://{project_id}/audit")
async def get_audit_trail(project_id: str, ctx: Context) -> str:
    """Get event counts and recent events.

    Shows the full chronological event log aggregated by type, plus the most
    recent 10 individual events for quick inspection.
    """
    stage = _get_stage(ctx, project_id)
    if not stage:
        return f"Project '{project_id}' not loaded. Use cb_manage_project action='load' first."

    if not stage.events:
        return "No events recorded."

    counts = count_events_by_type(stage)
    lines = [f"Audit trail for '{project_id}' ({len(stage.events)} events):\n"]
    lines.append("Event counts:")
    for etype, count in sorted(counts.items()):
        lines.append(f"  {etype}: {count}")

    # Show last 10 events, newest first
    recent = sorted(stage.events, key=lambda e: e.timestamp, reverse=True)[:10]
    lines.append(f"\nLast {len(recent)} events:")
    for evt in recent:
        ts = evt.timestamp.strftime("%H:%M:%S")
        lines.append(
            f"  [{ts}] {evt.event_type.value} -> {evt.target_id} (by {evt.actor.value})"
        )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# stage://{project_id}/dependencies
# ═══════════════════════════════════════════════════════════════


@mcp.resource("stage://{project_id}/dependencies")
async def get_dependencies_view(project_id: str, ctx: Context) -> str:
    """Get the dependency DAG view — which assertions depend on what.

    Shows every active assertion that declares a depends_on_paths list,
    then resolves what assertion currently wins at each dependency path.
    """
    stage = _get_stage(ctx, project_id)
    if not stage:
        return f"Project '{project_id}' not loaded. Use cb_manage_project action='load' first."

    with_deps = [
        a
        for a in stage.assertions.values()
        if a.active and a.depends_on_paths
    ]

    if not with_deps:
        return "No dependency relationships declared."

    lines = [
        f"Dependency DAG for '{project_id}'"
        f" ({len(with_deps)} assertions with dependencies):\n"
    ]
    for a in sorted(with_deps, key=lambda x: x.topic_path):
        lines.append(f"{a.topic_path} [{a.arc.name}]")
        lines.append(f"  Content: {a.content}")
        lines.append(f"  Status: {a.assumption_status.value}")
        lines.append("  Depends on:")
        for dep_path in a.depends_on_paths:
            candidates = [
                w
                for w in stage.assertions.values()
                if w.active and w.topic_path == dep_path
            ]
            if candidates:
                winner = sorted(candidates)[0]
                lines.append(
                    f"    -> {dep_path}: {winner.content} [{winner.arc.name}]"
                )
            else:
                lines.append(f"    -> {dep_path}: (no assertion)")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# stage://{project_id}/payloads
# ═══════════════════════════════════════════════════════════════


@mcp.resource("stage://{project_id}/payloads")
async def get_payloads_view(project_id: str, ctx: Context) -> str:
    """Surface pending payloads — known unknowns that need evidence.

    PAYLOADS-arc assertions mark gaps in the knowledge base. They represent
    things you know you don't know. Call this before making decisions to
    ensure you're not ignoring important open questions.
    """
    stage = _get_stage(ctx, project_id)
    if not stage:
        return f"Project '{project_id}' not loaded. Use cb_manage_project action='load' first."

    payloads = [
        a
        for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.PAYLOADS
    ]

    if not payloads:
        return "No pending payloads."

    lines = [f"Pending payloads for '{project_id}' ({len(payloads)}):\n"]
    for p in sorted(payloads, key=lambda x: x.topic_path):
        lines.append(f"PAYLOAD: {p.topic_path}")
        lines.append(f"  {p.content}")
        lines.append(f"  ID: {p.id}")
        if p.tags:
            lines.append(f"  Tags: {', '.join(p.tags)}")
        lines.append("")

    lines.append(
        "These are known unknowns. Gather evidence to promote or dismiss them."
    )
    return "\n".join(lines)
