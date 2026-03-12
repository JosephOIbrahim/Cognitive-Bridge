"""Shared utilities for Cognitive Bridge MCP tool modules."""

import os
from pathlib import Path
from typing import Optional

from fastmcp import Context

from cognitive_bridge.models import CompositionStage


def get_active_stage(
    ctx: Context, project_id: Optional[str] = None
) -> tuple[str, CompositionStage]:
    """Get the active stage from the lifespan context.

    If project_id is None and exactly one project is active, returns it.
    Otherwise requires an explicit project_id.

    Args:
        ctx: FastMCP context carrying lifespan_context.
        project_id: Optional explicit project to look up.

    Returns:
        Tuple of (project_id, CompositionStage).

    Raises:
        ValueError: If no projects are active, the named project is not
            active, or multiple projects are active without project_id.
    """
    active_stages: dict[str, CompositionStage] = ctx.lifespan_context[
        "active_stages"
    ]
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


def auto_export_usda(stage: CompositionStage) -> None:
    """Best-effort USDA export after stage mutation.

    Generates .usda files in the project's usda/ subdirectory under the
    CB_DB_DIR directory. Never raises — USDA export is a derived layer,
    not critical path. Failures are silently discarded so that USDA issues
    never interrupt tool execution.

    Args:
        stage: The composition stage to export. Must have a valid project_id.
    """
    try:
        from cognitive_bridge.bridge.usda_export import export_stage_to_usda

        db_dir = Path(
            os.environ.get(
                "CB_DB_DIR",
                str(Path.home() / ".cognitive_bridge" / "projects"),
            )
        )
        usda_dir = db_dir / stage.project_id / "usda"
        export_stage_to_usda(stage, usda_dir)
    except Exception:
        pass  # Best-effort — never block the tool
