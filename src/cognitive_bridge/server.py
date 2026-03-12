"""Cognitive Bridge MCP Server — FastMCP entry point.

This module is the top-level wiring layer. It owns:
- FastMCP application initialization
- Lifespan: SQLiteStore creation and active stage registry
- Internal helpers for loading/saving stages
- The cb_manage_project tool (create, load, save, list)
- Entry point for `python -m cognitive_bridge.server`

All other tools are registered in their respective tool modules and imported
here so they bind to the shared `mcp` instance.
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastmcp import Context, FastMCP
from sqlmodel import select

from cognitive_bridge.models import (
    AssertionAuthor,
    CognitiveParameters,
    CompositionStage,
    EventType,
    _now_utc,
)
from cognitive_bridge.storage.converters import (
    assertion_to_row,
    conflict_to_row,
    decision_to_row,
    event_to_row,
    parameters_to_row,
    row_to_assertion,
    row_to_conflict,
    row_to_decision,
    row_to_event,
    row_to_parameters,
    row_to_variant_set,
    variant_set_to_row,
)
from cognitive_bridge.storage.sqlite_store import (
    AssertionRow,
    ConflictRow,
    DecisionRow,
    EventRow,
    ParametersRow,
    ProjectRow,
    SQLiteStore,
    VariantSetRow,
)

# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

DEFAULT_DB_DIR: Path = Path.home() / ".cognitive_bridge" / "projects"

MAX_CAPSULE_SIZE = 10 * 1024 * 1024  # 10MB

# Module-level active stage registry. NOT thread-safe — assumes single
# request handler per project (FastMCP processes one request at a time
# per connection). For multi-threaded concurrency, wrap access with
# threading.Lock().
_ACTIVE_STAGES: dict[str, CompositionStage] = {}

# ═══════════════════════════════════════════════════════════════
# Upsert Column Lists
# ═══════════════════════════════════════════════════════════════
# These must be kept in sync with their corresponding SQLModel tables.
# If you add a field to a model and its Row, add the column name here.

_PARAMS_UPDATE_COLS = (
    "conflict_sensitivity", "semantic_threshold", "cross_path_detection",
    "exploration_budget", "ai_default_arc", "payload_surfacing",
    "red_team_threshold", "cascade_auto_challenge",
)

_ASSERTION_UPDATE_COLS = (
    "topic_path", "content", "arc", "author", "evidence_json",
    "evidence_type", "depends_on_paths_json", "falsifiable_if",
    "assumption_status", "active", "retracted_at", "confidence",
    "embedding_json", "tags_json",
)

_CONFLICT_UPDATE_COLS = (
    "status", "resolution_chosen", "resolution_evidence",
    "resolution_note", "steelman_of_opponent", "experiment_protocol",
    "experiment_result", "resolved_at", "produced_variant_set_id",
)

_VARIANT_SET_UPDATE_COLS = (
    "variants_json", "resolved", "resolved_variant_name",
    "resolution_evidence", "resolved_at",
)


# ═══════════════════════════════════════════════════════════════
# Lifespan
# ═══════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(server: Any):
    """Initialize the SQLite store on server startup and yield the context dict.

    The context dict is made available to all tool handlers via
    ``ctx.lifespan_context``. Keys:
    - ``store``: SQLiteStore instance.
    - ``active_stages``: Mutable dict mapping project_id -> CompositionStage
      for in-memory access between calls.

    The database directory is controlled by the CB_DB_DIR environment variable;
    defaults to ~/.cognitive_bridge/projects/.
    """
    db_dir = Path(os.environ.get("CB_DB_DIR", str(DEFAULT_DB_DIR)))
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(db_dir / "cognitive_bridge.db")
    store = SQLiteStore(db_path)
    try:
        yield {
            "store": store,
            "active_stages": _ACTIVE_STAGES,
        }
    finally:
        store.engine.dispose()


# ═══════════════════════════════════════════════════════════════
# FastMCP Application
# ═══════════════════════════════════════════════════════════════

mcp = FastMCP(
    "Cognitive Bridge",
    instructions=(
        "MCP server implementing USD-inspired LIVRPS composition arcs as a "
        "formal argumentation framework for AI critical thinking. "
        "Use cb_manage_project to create or load a project before using "
        "any other tools."
    ),
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════


def _get_store(ctx: Context) -> SQLiteStore:
    """Extract the SQLiteStore from the lifespan context."""
    return ctx.lifespan_context["store"]


def _get_active_stages(ctx: Context) -> dict[str, CompositionStage]:
    """Extract the active stages registry from the lifespan context."""
    return ctx.lifespan_context["active_stages"]


def save_stage_to_db(store: SQLiteStore, stage: CompositionStage) -> None:
    """Persist a CompositionStage to SQLite.

    Uses an upsert pattern: existing rows are updated in-place, new rows are
    inserted. Events and Decisions are append-only — rows that already exist in
    the DB are never re-inserted.

    This function is intentionally public (no leading underscore) so that test
    code and future tool modules can call it directly without going through
    tool-layer plumbing.

    Args:
        store: Open SQLiteStore to write to.
        stage: CompositionStage to persist. Must have a valid project_id.
    """
    with store.get_session() as session:
        # Upsert project metadata row
        existing_project = session.get(ProjectRow, stage.project_id)
        if existing_project:
            existing_project.project_name = stage.project_name
            existing_project.exchange_count = stage.exchange_count
            existing_project.last_updated = stage.last_updated
        else:
            session.add(
                ProjectRow(
                    project_id=stage.project_id,
                    project_name=stage.project_name,
                    exchange_count=stage.exchange_count,
                    created_at=stage.created_at,
                    last_updated=stage.last_updated,
                )
            )

        # Upsert parameters row (one row per project, PK = project_id)
        existing_params = session.get(ParametersRow, stage.project_id)
        params_row = parameters_to_row(stage.parameters, stage.project_id)
        if existing_params:
            for col in _PARAMS_UPDATE_COLS:
                setattr(existing_params, col, getattr(params_row, col))
        else:
            session.add(params_row)

        # Upsert assertions
        for ast in stage.assertions.values():
            row = assertion_to_row(ast, stage.project_id)
            existing_ast = session.get(AssertionRow, ast.id)
            if existing_ast:
                for col in _ASSERTION_UPDATE_COLS:
                    setattr(existing_ast, col, getattr(row, col))
            else:
                session.add(row)

        # Upsert conflicts
        for cfl in stage.conflicts.values():
            row = conflict_to_row(cfl, stage.project_id)
            existing_cfl = session.get(ConflictRow, cfl.id)
            if existing_cfl:
                for col in _CONFLICT_UPDATE_COLS:
                    setattr(existing_cfl, col, getattr(row, col))
            else:
                session.add(row)

        # Upsert variant sets
        for vs in stage.variant_sets.values():
            row = variant_set_to_row(vs, stage.project_id)
            existing_vs = session.get(VariantSetRow, vs.id)
            if existing_vs:
                for col in _VARIANT_SET_UPDATE_COLS:
                    setattr(existing_vs, col, getattr(row, col))
            else:
                session.add(row)

        # Append-only: events (keyed by event id)
        existing_event_ids = {
            e.id
            for e in session.exec(
                select(EventRow).where(EventRow.project_id == stage.project_id)
            ).all()
        }
        for evt in stage.events:
            if evt.id not in existing_event_ids:
                session.add(event_to_row(evt, stage.project_id))

        # Append-only: decisions (keyed by decision id)
        existing_dec_ids = {
            d.id
            for d in session.exec(
                select(DecisionRow).where(DecisionRow.project_id == stage.project_id)
            ).all()
        }
        for dec in stage.decisions:
            if dec.id not in existing_dec_ids:
                session.add(decision_to_row(dec, stage.project_id))

        session.commit()


def load_stage_from_db(store: SQLiteStore, project_id: str) -> CompositionStage:
    """Load a CompositionStage from SQLite by project_id.

    Reconstructs the full in-memory stage from all related table rows.

    Args:
        store: Open SQLiteStore to read from.
        project_id: The project to load.

    Returns:
        A fully populated CompositionStage.

    Raises:
        ValueError: If the project_id does not exist in the database.
    """
    with store.get_session() as session:
        project = session.get(ProjectRow, project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found in database.")

        # Parameters (optional — default if row missing)
        params_row = session.get(ParametersRow, project_id)
        parameters = row_to_parameters(params_row) if params_row else CognitiveParameters()

        # Assertions
        ast_rows = session.exec(
            select(AssertionRow).where(AssertionRow.project_id == project_id)
        ).all()
        assertions = {r.id: row_to_assertion(r) for r in ast_rows}

        # Conflicts
        cfl_rows = session.exec(
            select(ConflictRow).where(ConflictRow.project_id == project_id)
        ).all()
        conflicts = {r.id: row_to_conflict(r) for r in cfl_rows}

        # Variant sets
        vs_rows = session.exec(
            select(VariantSetRow).where(VariantSetRow.project_id == project_id)
        ).all()
        variant_sets = {r.id: row_to_variant_set(r) for r in vs_rows}

        # Events
        evt_rows = session.exec(
            select(EventRow).where(EventRow.project_id == project_id)
        ).all()
        events = [row_to_event(r) for r in evt_rows]

        # Decisions
        dec_rows = session.exec(
            select(DecisionRow).where(DecisionRow.project_id == project_id)
        ).all()
        decisions = [row_to_decision(r) for r in dec_rows]

        return CompositionStage(
            project_id=project.project_id,
            project_name=project.project_name,
            assertions=assertions,
            conflicts=conflicts,
            variant_sets=variant_sets,
            events=events,
            decisions=decisions,
            parameters=parameters,
            exchange_count=project.exchange_count,
            created_at=project.created_at,
            last_updated=project.last_updated,
        )


# ═══════════════════════════════════════════════════════════════
# Export / Import Helpers
# ═══════════════════════════════════════════════════════════════


def export_stage_to_json(stage: CompositionStage) -> str:
    """Serialize a CompositionStage to a JSON capsule string.

    The capsule is a self-contained, version-stamped JSON document that can be
    stored, transmitted, or imported into any Cognitive Bridge instance. All
    Pydantic models are serialized via ``model_dump(mode="json")`` so that enum
    values, datetime objects, and nested structures are JSON-safe.

    Args:
        stage: The in-memory CompositionStage to export.

    Returns:
        A pretty-printed JSON string (indent=2).
    """
    capsule: dict[str, Any] = {
        "version": "3.0",
        "project_id": stage.project_id,
        "project_name": stage.project_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "assertions": {
            k: {**v.model_dump(mode="json"), "embedding": v.embedding}
            for k, v in stage.assertions.items()
        },
        "conflicts": {
            k: v.model_dump(mode="json") for k, v in stage.conflicts.items()
        },
        "variant_sets": {
            k: v.model_dump(mode="json") for k, v in stage.variant_sets.items()
        },
        "events": [e.model_dump(mode="json") for e in stage.events],
        "decisions": [d.model_dump(mode="json") for d in stage.decisions],
        "parameters": stage.parameters.model_dump(mode="json"),
        "exchange_count": stage.exchange_count,
    }
    return json.dumps(capsule, indent=2, default=str)


def import_stage_from_json(json_str: str) -> CompositionStage:
    """Reconstruct a CompositionStage from a JSON capsule string.

    Deserializes all components using their Pydantic model constructors.
    All validators run during reconstruction, so an invalid capsule will
    raise a ``ValidationError`` or ``ValueError`` before the stage is returned.

    Args:
        json_str: A JSON string previously produced by ``export_stage_to_json``.

    Returns:
        A fully populated CompositionStage ready for use.

    Raises:
        json.JSONDecodeError: If ``json_str`` is not valid JSON.
        pydantic.ValidationError: If any component fails schema validation.
        KeyError: If required capsule fields are missing.
    """
    if len(json_str) > MAX_CAPSULE_SIZE:
        raise ValueError(
            f"JSON capsule too large ({len(json_str)} bytes). "
            f"Maximum allowed: {MAX_CAPSULE_SIZE} bytes (10MB)."
        )

    from cognitive_bridge.models import (
        Assertion,
        CognitiveParameters,
        Conflict,
        Decision,
        Event,
        VariantSet,
    )

    capsule: dict[str, Any] = json.loads(json_str)

    assertions = {k: Assertion(**v) for k, v in capsule["assertions"].items()}
    conflicts = {k: Conflict(**v) for k, v in capsule["conflicts"].items()}
    variant_sets = {k: VariantSet(**v) for k, v in capsule["variant_sets"].items()}
    events = [Event(**e) for e in capsule["events"]]
    decisions = [Decision(**d) for d in capsule["decisions"]]
    parameters = CognitiveParameters(**capsule["parameters"])

    return CompositionStage(
        project_id=capsule["project_id"],
        project_name=capsule["project_name"],
        assertions=assertions,
        conflicts=conflicts,
        variant_sets=variant_sets,
        events=events,
        decisions=decisions,
        parameters=parameters,
        exchange_count=capsule.get("exchange_count", 0),
    )


# ═══════════════════════════════════════════════════════════════
# cb_manage_project Tool
# ═══════════════════════════════════════════════════════════════


@mcp.tool(
    name="cb_manage_project",
    annotations={
        "title": "Manage Cognitive Bridge Projects",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def cb_manage_project(
    action: str,
    ctx: Context,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> str:
    """ALWAYS call this tool first. Every session requires an active project.

    Use 'create' to start a new composition stage, or 'load' to resume a
    prior project. Without an active project all other cb_* tools will fail.

    Actions:
    - create: Initialize a new empty CompositionStage and persist it. Fails if
      the project_id is already active in memory (call 'save' first).
    - load: Load an existing project from SQLite into memory. Returns a summary
      of the stage (assertion count, active conflicts, resolved paths).
    - save: Persist the current in-memory state of a loaded project to SQLite.
    - list: List all project IDs stored in the database, marking which are
      currently active in memory.
    - export: Serialize the active stage to a self-contained JSON capsule string.
      The capsule can be stored, transmitted, or imported into any Cognitive
      Bridge instance. Use this to back up a stage or transfer it.
    - import_json: Reconstruct a stage from a JSON capsule (produced by export)
      and persist it to SQLite. The project_id in the capsule is used; pass the
      capsule JSON as the project_name parameter.

    Args:
        action: One of: create, load, save, list, export, import_json.
        project_id: Required for create, load, save, export. Not needed for list.
          For import_json, overrides the project_id stored in the capsule when
          provided; otherwise the capsule's project_id is used.
        project_name: Human-readable label. Used with create; used as the JSON
          capsule payload for import_json.
    """
    store = _get_store(ctx)
    active_stages = _get_active_stages(ctx)

    if action == "create":
        if not project_id:
            return "ERROR: project_id is required for the 'create' action."
        if project_id in active_stages:
            return (
                f"ERROR: Project '{project_id}' is already active in memory. "
                "Use action='save' to persist it or action='load' to reload from disk."
            )

        stage = CompositionStage(
            project_id=project_id,
            project_name=project_name or project_id,
        )
        stage.record_event(
            EventType.PROJECT_LOADED,
            AssertionAuthor.SYSTEM,
            project_id,
            {"action": "created"},
        )
        active_stages[project_id] = stage
        save_stage_to_db(store, stage)

        return (
            f"Project '{project_id}' created and loaded into memory.\n"
            f"Name: {stage.project_name}\n"
            f"The composition stage is empty. Begin asserting with cb_manage_assertion."
        )

    elif action == "load":
        if not project_id:
            return "ERROR: project_id is required for the 'load' action."
        try:
            stage = load_stage_from_db(store, project_id)
        except ValueError as exc:
            return f"ERROR: {exc}"

        active_stages[project_id] = stage
        resolved = stage.resolve()
        active_conflict_count = sum(
            1 for c in stage.conflicts.values() if c.status.value == "active"
        )
        return (
            f"Project '{project_id}' loaded into memory.\n"
            f"Name: {stage.project_name}\n"
            f"Assertions: {len(stage.assertions)}\n"
            f"Active conflicts: {active_conflict_count}\n"
            f"Resolved paths: {len(resolved)}\n"
            f"Events: {len(stage.events)}\n"
            f"Decisions: {len(stage.decisions)}"
        )

    elif action == "save":
        if not project_id:
            return "ERROR: project_id is required for the 'save' action."
        if project_id not in active_stages:
            return (
                f"ERROR: Project '{project_id}' is not loaded in memory. "
                "Use action='load' first."
            )
        stage = active_stages[project_id]
        stage.last_updated = _now_utc()
        save_stage_to_db(store, stage)
        return f"Project '{project_id}' saved to SQLite."

    elif action == "list":
        project_ids = store.list_projects()
        if not project_ids:
            return "No projects found. Use action='create' to start one."
        lines = ["Available projects:"]
        for pid in project_ids:
            marker = " (active)" if pid in active_stages else ""
            lines.append(f"  - {pid}{marker}")
        return "\n".join(lines)

    elif action == "export":
        if not project_id:
            return "ERROR: project_id is required for the 'export' action."
        if project_id not in active_stages:
            return (
                f"ERROR: Project '{project_id}' is not loaded in memory. "
                "Use action='load' first."
            )
        stage = active_stages[project_id]
        capsule = export_stage_to_json(stage)
        return f"EXPORTED ({len(capsule)} bytes):\n{capsule}"

    elif action == "import_json":
        if not project_name:
            return (
                "ERROR: The JSON capsule must be provided as the project_name parameter."
            )
        try:
            stage = import_stage_from_json(project_name)
        except json.JSONDecodeError as exc:
            return f"ERROR: Invalid JSON — {exc}"
        except (ValueError, KeyError, TypeError) as exc:
            return f"ERROR: Failed to parse capsule — {exc}"

        # Allow caller to override the project_id from the capsule
        if project_id:
            stage.project_id = project_id

        # Guard against collisions with an already-active project
        if stage.project_id in active_stages:
            return (
                f"ERROR: Project '{stage.project_id}' is already active in memory. "
                "Use a different project_id or save the existing project first."
            )

        active_stages[stage.project_id] = stage
        save_stage_to_db(store, stage)
        return (
            f"Project '{stage.project_id}' imported from capsule and loaded into memory.\n"
            f"Name: {stage.project_name}\n"
            f"Assertions: {len(stage.assertions)}\n"
            f"Conflicts: {len(stage.conflicts)}\n"
            f"Events: {len(stage.events)}\n"
            f"Decisions: {len(stage.decisions)}"
        )

    else:
        return (
            f"ERROR: Unknown action '{action}'. "
            "Valid actions: create, load, save, list, export, import_json."
        )


# ═══════════════════════════════════════════════════════════════
# Register Tool Modules
# ═══════════════════════════════════════════════════════════════

# Importing these modules causes their @mcp.tool decorators to fire,
# binding each tool to the shared FastMCP instance declared above.
import cognitive_bridge.prompts.negotiation_prompts  # noqa: E402, F401
import cognitive_bridge.resources.stage_resources  # noqa: E402, F401
import cognitive_bridge.tools.assertion_tool  # noqa: E402, F401
import cognitive_bridge.tools.conflict_tool  # noqa: E402, F401
import cognitive_bridge.tools.decision_tool  # noqa: E402, F401
import cognitive_bridge.tools.parameters_tool  # noqa: E402, F401
import cognitive_bridge.tools.payload_tool  # noqa: E402, F401
import cognitive_bridge.tools.probe_tool  # noqa: E402, F401
import cognitive_bridge.tools.variant_tool  # noqa: E402, F401

# ═══════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()
