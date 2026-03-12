"""cb_tune_parameters tool — expose all CognitiveParameters knobs.

Tuning parameters at runtime lets the argumentation protocol adapt to the
current project context without restarting the server. Every change is recorded
as a PARAMETERS_TUNED event in the audit trail so parameter drift is always
traceable. Call with no arguments to inspect current settings.
"""

from typing import Optional

from fastmcp import Context

from cognitive_bridge.models import (
    AssertionAuthor,
    CognitiveParameters,
    CompositionArc,
    CompositionStage,
    EventType,
)
from cognitive_bridge.server import mcp, save_stage_to_db

# ═══════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════


def _get_active_stage(
    ctx: Context, project_id: Optional[str] = None
) -> tuple[str, CompositionStage]:
    """Resolve the active stage from context.

    Returns (project_id, CompositionStage). Raises ValueError when no active
    project is found or when project_id is ambiguous.
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
        f"Multiple active projects: {list(active_stages.keys())}. Specify project_id."
    )


# ═══════════════════════════════════════════════════════════════
# cb_tune_parameters Tool
# ═══════════════════════════════════════════════════════════════


@mcp.tool(
    name="cb_tune_parameters",
    annotations={
        "title": "Tune Cognitive Parameters",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def cb_tune_parameters(
    ctx: Context,
    conflict_sensitivity: Optional[float] = None,
    semantic_threshold: Optional[float] = None,
    cross_path_detection: Optional[bool] = None,
    exploration_budget: Optional[int] = None,
    ai_default_arc: Optional[int] = None,
    payload_surfacing: Optional[bool] = None,
    red_team_threshold: Optional[int] = None,
    cascade_auto_challenge: Optional[bool] = None,
    project_id: Optional[str] = None,
) -> str:
    """ALWAYS call this tool when the argumentation protocol needs calibration.

    Pass no parameters to inspect current settings — use this at session start
    to understand the active tuning before asserting.

    YOU MUST tune parameters when:
    - The default conflict_sensitivity (0.5) generates too many or too few
      conflicts for the current project's risk profile.
    - semantic_threshold needs adjustment because the domain has high
      surface-level similarity between distinct concepts.
    - cross_path_detection should be enabled when cross-domain semantic
      conflicts are architecturally relevant.
    - RED_TEAMING activates too early or too late for the project's depth.

    Only supplied parameters are updated. All others remain unchanged. Every
    update is recorded as a PARAMETERS_TUNED event in the audit trail.

    Parameters:
    - conflict_sensitivity (0.0–1.0): How aggressively to flag potential
      conflicts. 0 = permissive, 1 = strict. Default: 0.5.
    - semantic_threshold (0.5–0.99): Cosine similarity threshold for Layer 2
      semantic conflict detection. Higher = fewer false positives. Default: 0.80.
    - cross_path_detection (bool): Enable Layer 2 detection across different
      topic paths. Default: False.
    - exploration_budget (1–10): Max active variant sets per topic path.
      Default: 3.
    - ai_default_arc (int): Default arc strength for AI assertions as a
      CompositionArc integer value. Valid values: 10 (LOCAL), 20 (INHERITS),
      30 (VARIANT_SET), 40 (REFERENCES), 50 (PAYLOADS), 60 (SPECIALIZES).
      Default: 20 (INHERITS).
    - payload_surfacing (bool): Auto-surface PAYLOADS assertions as warnings
      in tool responses. Default: True.
    - red_team_threshold (3–20): Number of LOCAL assertions with zero active
      conflicts before RED_TEAMING posture activates. Default: 8.
    - cascade_auto_challenge (bool): Automatically mark dependent assertions
      as CHALLENGED when a dependency shifts. Default: True.
    - project_id: Disambiguates when multiple projects are active.
    """
    try:
        pid, stage = _get_active_stage(ctx, project_id)
    except ValueError as exc:
        return f"ERROR: {exc}"

    store = ctx.lifespan_context["store"]
    params = stage.parameters

    # Collect which parameters were explicitly provided
    updates: dict = {}
    if conflict_sensitivity is not None:
        updates["conflict_sensitivity"] = conflict_sensitivity
    if semantic_threshold is not None:
        updates["semantic_threshold"] = semantic_threshold
    if cross_path_detection is not None:
        updates["cross_path_detection"] = cross_path_detection
    if exploration_budget is not None:
        updates["exploration_budget"] = exploration_budget
    if ai_default_arc is not None:
        # Validate arc value before attempting to construct CompositionArc so
        # the error message is clear.
        try:
            arc_enum = CompositionArc(ai_default_arc)
        except ValueError:
            valid = ", ".join(
                f"{a.value} ({a.name})" for a in CompositionArc
            )
            return (
                f"ERROR: Invalid ai_default_arc value '{ai_default_arc}'. "
                f"Valid values: {valid}."
            )
        updates["ai_default_arc"] = arc_enum
    if payload_surfacing is not None:
        updates["payload_surfacing"] = payload_surfacing
    if red_team_threshold is not None:
        updates["red_team_threshold"] = red_team_threshold
    if cascade_auto_challenge is not None:
        updates["cascade_auto_challenge"] = cascade_auto_challenge

    # No updates requested — return current settings as a read-only view
    if not updates:
        lines = [
            f"Current parameters for project '{pid}':",
            f"  conflict_sensitivity:  {params.conflict_sensitivity}",
            f"  semantic_threshold:    {params.semantic_threshold}",
            f"  cross_path_detection:  {params.cross_path_detection}",
            f"  exploration_budget:    {params.exploration_budget}",
            f"  ai_default_arc:        "
            f"{params.ai_default_arc.name} ({params.ai_default_arc.value})",
            f"  payload_surfacing:     {params.payload_surfacing}",
            f"  red_team_threshold:    {params.red_team_threshold}",
            f"  cascade_auto_challenge:{params.cascade_auto_challenge}",
        ]
        return "\n".join(lines)

    # Apply updates via model reconstruction so Pydantic validators fire
    try:
        current_dict = params.model_dump()
        current_dict.update(updates)
        new_params = CognitiveParameters(**current_dict)
    except ValueError as exc:
        return f"ERROR: Invalid parameter value — {exc}"

    stage.parameters = new_params

    stage.record_event(
        EventType.PARAMETERS_TUNED,
        AssertionAuthor.AI,
        pid,
        {"updates": {k: str(v) for k, v in updates.items()}},
    )
    save_stage_to_db(store, stage)

    # Format response showing only the changed keys
    lines = [f"Parameters updated for project '{pid}':"]
    for key, value in updates.items():
        if isinstance(value, CompositionArc):
            lines.append(f"  {key}: {value.name} ({value.value})")
        else:
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)
