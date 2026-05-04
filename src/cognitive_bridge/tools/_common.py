"""Shared utilities for Cognitive Bridge MCP tool modules."""

import logging
import os
import re
from pathlib import Path
from typing import Optional

from fastmcp import Context

from cognitive_bridge.models import CompositionStage

logger = logging.getLogger(__name__)

# Project IDs are stored as filesystem directories (CB_DB_DIR/{project_id}/) and
# as SQLite primary keys. Pattern is intentionally narrower than topic_path —
# no slashes, no leading digits — because project IDs become path segments.
# Matches the conventions used throughout the test suite ("proj_test",
# "mongodb_choice", "trust-test", etc.).
_PROJECT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def validate_project_id(project_id: str) -> None:
    """Validate project_id syntax. Used at every filesystem and SQLite entry point.

    Raises ValueError with a descriptive message if project_id contains characters
    that could enable path traversal ("../etc"), command injection, or storage
    corruption (NULs, whitespace, mixed case).

    Args:
        project_id: The user-supplied project identifier.

    Raises:
        ValueError: If project_id is not a string, is empty, or contains
            characters outside [a-z0-9_-] (with a leading lowercase letter).
    """
    if not isinstance(project_id, str):
        raise ValueError(
            f"project_id must be a string, got {type(project_id).__name__}"
        )
    if not _PROJECT_ID_PATTERN.match(project_id):
        raise ValueError(
            f"Invalid project_id '{project_id}': must match "
            f"{_PROJECT_ID_PATTERN.pattern} "
            "(lowercase letter prefix, 1-64 characters, [a-z0-9_-] only)."
        )


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
    CB_DB_DIR directory. USDA export is a derived layer, not critical path:
    failures are LOGGED (not silently swallowed) but never raise so they
    do not interrupt tool execution.

    project_id is validated against _PROJECT_ID_PATTERN before any path is
    constructed — closes the path-traversal vector that existed when stages
    were created with arbitrary project_id strings.

    Args:
        stage: The composition stage to export. Must have a valid project_id.
    """
    try:
        validate_project_id(stage.project_id)
        from cognitive_bridge.bridge.usda_export import export_stage_to_usda

        db_dir = Path(
            os.environ.get(
                "CB_DB_DIR",
                str(Path.home() / ".cognitive_bridge" / "projects"),
            )
        )
        usda_dir = db_dir / stage.project_id / "usda"
        export_stage_to_usda(stage, usda_dir)
    except Exception as exc:
        logger.warning(
            "USDA export failed for project '%s': %s",
            stage.project_id, exc, exc_info=True,
        )
