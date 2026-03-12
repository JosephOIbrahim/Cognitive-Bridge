"""cb_probe_user tool — update the Cognitive Operating Signature (COS) kernel.

This module implements the user-profiling probe tool for the Cognitive Bridge MCP
server. It binds to the shared FastMCP instance via the @mcp.tool decorator
and is imported by server.py to trigger decorator registration.

Design notes:
- The kernel is stored as a module-level dict keyed by project_id (_KERNELS)
  and persisted to SQLite via KernelRow. This avoids modifying CompositionStage.
- Probe values are smoothed via an exponential moving average (alpha=0.7) so a
  single extreme probe cannot violently shift the kernel. The most recent probe
  carries 70% weight; history carries 30%.
- probe_count and last_probed track calibration history for the posture prompt.
- The public get_kernel() accessor lets the sensitivity auto-tuner (P3.T2) read
  the current kernel without knowing about the cache internals.
- This tool performs naturalistic observation — it records what the user tells
  us, not quiz answers. Call it any time the user's state is observable.
"""

from typing import Optional

from fastmcp import Context

from cognitive_bridge.tools._common import get_active_stage
from cognitive_bridge.engine.sensitivity import apply_kernel_tuning, format_tuning_report
from cognitive_bridge.models import (
    CompositionStage,
    IndividualKernel,
    _now_utc,
)
from cognitive_bridge.server import mcp, save_stage_to_db
from cognitive_bridge.storage.converters import kernel_to_row, row_to_kernel
from cognitive_bridge.storage.sqlite_store import KernelRow, SQLiteStore

# ═══════════════════════════════════════════════════════════════
# Module-level kernel cache
# ═══════════════════════════════════════════════════════════════

# Keyed by project_id. Populated on first access, written through on every probe.
_KERNELS: dict[str, IndividualKernel] = {}

# Smoothing weight: new probe carries this fraction of the final value.
_EMA_ALPHA: float = 0.7

# Maps tool-facing probe type names to IndividualKernel field names.
_PROBE_MAP: dict[str, str] = {
    "entropy": "entropy_tolerance",
    "process": "process_purity",
    "autonomy": "autonomy_boundary",
    "energy": "energy_level",
}


# ═══════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════


def _get_or_create_kernel(store: SQLiteStore, project_id: str) -> IndividualKernel:
    """Return the kernel for project_id, loading from DB or creating fresh.

    The kernel is cached in _KERNELS after the first access. Subsequent calls
    within the same server process return the cached object directly.

    Args:
        store: SQLiteStore instance for persistence.
        project_id: Project to look up.

    Returns:
        IndividualKernel for the given project, initialised to defaults if new.
    """
    if project_id in _KERNELS:
        return _KERNELS[project_id]

    # Try loading from DB — the KernelRow.project_id column is indexed.
    with store.get_session() as session:
        from sqlmodel import select as _select

        rows = session.exec(
            _select(KernelRow).where(KernelRow.project_id == project_id)
        ).all()
        if rows:
            kernel = row_to_kernel(rows[0])
            _KERNELS[project_id] = kernel
            return kernel

    # No DB record — create a fresh kernel with neutral defaults (all 0.5).
    kernel = IndividualKernel()
    _KERNELS[project_id] = kernel
    return kernel


def _save_kernel(store: SQLiteStore, kernel: IndividualKernel, project_id: str) -> None:
    """Write-through: persist kernel to SQLite, inserting or updating as needed.

    Args:
        store: SQLiteStore instance.
        kernel: Current in-memory kernel state.
        project_id: Project this kernel belongs to.
    """
    with store.get_session() as session:
        from sqlmodel import select as _select

        existing = session.exec(
            _select(KernelRow).where(KernelRow.project_id == project_id)
        ).all()
        row = kernel_to_row(kernel, project_id)
        if existing:
            old = existing[0]
            for col in (
                "entropy_tolerance",
                "process_purity",
                "autonomy_boundary",
                "energy_level",
                "probe_count",
                "last_probed",
                "updated_at",
            ):
                setattr(old, col, getattr(row, col))
        else:
            session.add(row)
        session.commit()


# ═══════════════════════════════════════════════════════════════
# Public accessor
# ═══════════════════════════════════════════════════════════════


def get_kernel(store: SQLiteStore, project_id: str) -> IndividualKernel:
    """Return the current IndividualKernel for project_id.

    Used by the sensitivity auto-tuner (P3.T2) and the coworker_posture
    prompt to read kernel dimensions without importing the cache directly.

    Args:
        store: SQLiteStore instance (used for lazy DB load if not cached).
        project_id: Project whose kernel to retrieve.

    Returns:
        IndividualKernel, loaded from cache or DB, or freshly initialised.
    """
    return _get_or_create_kernel(store, project_id)


# ═══════════════════════════════════════════════════════════════
# Tool
# ═══════════════════════════════════════════════════════════════


@mcp.tool(
    name="cb_probe_user",
    annotations={
        "title": "Probe User Cognitive Style",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
)
async def cb_probe_user(
    probe_type: str,
    value: float,
    ctx: Context,
    project_id: Optional[str] = None,
) -> str:
    """IMPORTANT: Record an observation about the user's cognitive style to calibrate
    the argumentation protocol. Call this whenever you observe the user's working
    state — not as a quiz, but as naturalistic observation.

    This updates the Cognitive Operating Signature (COS) kernel, which governs:
    - How aggressively conflicts are surfaced (sensitivity tuning)
    - Which coworker posture is adopted (LEARNING / ENGAGED / AUTHORITATIVE / RED_TEAMING)
    - How much epistemic pressure is appropriate right now

    Probe types and what to observe:
    - entropy:  How the user reacts to ambiguity. Frustrated by unknowns = low (0.0).
                Energised by open questions = high (1.0). Default 0.5.
    - process:  How strictly the user follows methodology. Takes shortcuts = low.
                Insists on correct process = high. Default 0.5.
    - autonomy: How much independent action the user wants from the AI.
                Wants approval on every step = low. Wants AI to act freely = high.
                Default 0.5.
    - energy:   User's current capacity. Depleted / brief replies = low.
                High engagement / elaborate messages = high. Default 0.5.

    Values are smoothed with an exponential moving average (alpha=0.7) so a
    single observation does not violently shift the kernel.

    YOU MUST call this at session start and after significant state changes
    (frustration, fatigue, shift in topic, sudden increase in engagement).
    The kernel degrades without periodic calibration.

    Args:
        probe_type: One of: entropy, process, autonomy, energy
        value: Observed value, 0.0 (low) to 1.0 (high)
        project_id: Optional — omit if only one project is active.
    """
    try:
        pid, _stage = get_active_stage(ctx, project_id)
    except ValueError as e:
        return f"ERROR: {e}"

    store: SQLiteStore = ctx.lifespan_context["store"]

    # Validate probe_type
    if probe_type not in _PROBE_MAP:
        valid = ", ".join(_PROBE_MAP.keys())
        return f"ERROR: Invalid probe_type '{probe_type}'. Valid types: {valid}"

    # Validate value range
    if not (0.0 <= value <= 1.0):
        return (
            f"ERROR: Value must be between 0.0 and 1.0, got {value}. "
            "Use 0.0 for the lowest observable state and 1.0 for the highest."
        )

    # Retrieve or initialise kernel
    kernel = _get_or_create_kernel(store, pid)

    field_name = _PROBE_MAP[probe_type]
    old_value = getattr(kernel, field_name)

    # Exponential moving average: recent probe weighted at alpha, history at (1 - alpha)
    smoothed = round(_EMA_ALPHA * value + (1.0 - _EMA_ALPHA) * old_value, 4)
    setattr(kernel, field_name, smoothed)

    kernel.probe_count += 1
    kernel.last_probed = _now_utc()
    kernel.updated_at = _now_utc()

    # Write-through to cache and DB
    _KERNELS[pid] = kernel
    _save_kernel(store, kernel, pid)

    # Auto-tune parameters based on updated kernel
    stage = ctx.lifespan_context["active_stages"].get(pid)
    changes: dict[str, str] = {}
    if stage:
        new_params, changes = apply_kernel_tuning(kernel, stage.parameters)
        if changes:
            stage.parameters = new_params
            save_stage_to_db(store, stage)

    response = (
        f"Kernel updated for '{pid}'.\n"
        f"Probe: {probe_type} ({field_name})\n"
        f"Raw value: {value}\n"
        f"Previous: {old_value}\n"
        f"Smoothed: {smoothed}\n"
        f"Probe count: {kernel.probe_count}\n"
        f"\nCurrent kernel:\n"
        f"  entropy_tolerance:  {kernel.entropy_tolerance}\n"
        f"  process_purity:     {kernel.process_purity}\n"
        f"  autonomy_boundary:  {kernel.autonomy_boundary}\n"
        f"  energy_level:       {kernel.energy_level}"
    )

    if stage and changes:
        tuning_lines = ["\nAuto-tuning applied:"]
        for param, change in changes.items():
            tuning_lines.append(f"  {param}: {change}")
        response += "\n".join(tuning_lines)
    else:
        response += "\nNo parameter changes needed."

    return response
