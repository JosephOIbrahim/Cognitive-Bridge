"""Integration tests for MCP resources and prompts.

Tests call the underlying async functions directly using a minimal mock
Context. This avoids MCP transport overhead while exercising every code
path, error branch, and formatting pattern.

No shared mutable state: every test builds its own stage.
"""

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    ConflictDetectionLayer,
    ConflictStatus,
    ResolutionPath,
    Variant,
    VariantSet,
)
from cognitive_bridge.models.arcs import EventType
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.resources.stage_resources import (
    get_audit_trail,
    get_conflicts_state,
    get_dependencies_view,
    get_kernel_state,
    get_payloads_view,
    get_resolved_state,
    get_variants_state,
)
from cognitive_bridge.prompts.negotiation_prompts import (
    coworker_posture,
    conflict_negotiation,
    stage_summary,
)


# ═══════════════════════════════════════════════════════════════
# Test Infrastructure
# ═══════════════════════════════════════════════════════════════


class _MockCtx:
    """Minimal context that satisfies ctx.lifespan_context access."""

    def __init__(self, active_stages: dict) -> None:
        self.lifespan_context = {"active_stages": active_stages, "store": None}


def _make_ctx(active_stages: dict | None = None) -> _MockCtx:
    return _MockCtx(active_stages=active_stages or {})


def _make_stage(project_id: str = "proj_test") -> CompositionStage:
    return CompositionStage(project_id=project_id, project_name="Test Project")


def _add_assertion(
    stage: CompositionStage,
    path: str,
    content: str,
    arc: CompositionArc = CompositionArc.INHERITS,
    author: AssertionAuthor = AssertionAuthor.AI,
    falsifiable_if: str | None = None,
    depends_on_paths: list[str] | None = None,
) -> Assertion:
    a = Assertion(
        topic_path=path,
        content=content,
        arc=arc,
        author=author,
        falsifiable_if=falsifiable_if or ("test condition" if arc == CompositionArc.LOCAL else None),
        depends_on_paths=depends_on_paths or [],
    )
    stage.assertions[a.id] = a
    return a


PROJECT_ID = "proj_test"


# ═══════════════════════════════════════════════════════════════
# Resources: get_resolved_state
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_resolved_project_not_loaded():
    ctx = _make_ctx({})
    result = await get_resolved_state(PROJECT_ID, ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_resolved_empty_stage():
    stage = _make_stage()
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_resolved_state(PROJECT_ID, ctx)
    assert "empty" in result.lower()


@pytest.mark.asyncio
async def test_resolved_shows_winner():
    stage = _make_stage()
    _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_resolved_state(PROJECT_ID, ctx)
    assert "/arch/db" in result
    assert "PostgreSQL" in result
    assert "INHERITS" in result


@pytest.mark.asyncio
async def test_resolved_shows_shadow_stack():
    stage = _make_stage()
    _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.SPECIALIZES)
    _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_resolved_state(PROJECT_ID, ctx)
    assert "Shadow stack" in result
    # Both assertions appear in some form
    assert "PostgreSQL" in result
    assert "MySQL" in result


@pytest.mark.asyncio
async def test_resolved_shows_negotiation_flag():
    stage = _make_stage()
    # Two assertions at same arc — forces tie
    _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_resolved_state(PROJECT_ID, ctx)
    assert "NEGOTIATION" in result


# ═══════════════════════════════════════════════════════════════
# Resources: get_conflicts_state
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_conflicts_project_not_loaded():
    ctx = _make_ctx({})
    result = await get_conflicts_state(PROJECT_ID, ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_conflicts_empty():
    stage = _make_stage()
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_conflicts_state(PROJECT_ID, ctx)
    assert "No conflicts" in result


@pytest.mark.asyncio
async def test_conflicts_shows_active():
    stage = _make_stage()
    a1 = _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    a2 = _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    conflict = Conflict(
        assertion_a_id=a1.id,
        assertion_b_id=a2.id,
        topic_path="/arch/db",
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
        status=ConflictStatus.ACTIVE,
    )
    stage.conflicts[conflict.id] = conflict
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_conflicts_state(PROJECT_ID, ctx)
    assert "ACTIVE" in result
    assert conflict.id in result
    assert "/arch/db" in result


@pytest.mark.asyncio
async def test_conflicts_shows_resolved():
    stage = _make_stage()
    a1 = _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    a2 = _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    conflict = Conflict(
        assertion_a_id=a1.id,
        assertion_b_id=a2.id,
        topic_path="/arch/db",
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
        status=ConflictStatus.RESOLVED_OVERRIDE,
        resolution_chosen=ResolutionPath.ACCEPT,
    )
    stage.conflicts[conflict.id] = conflict
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_conflicts_state(PROJECT_ID, ctx)
    assert "RESOLVED/OTHER" in result
    assert "accept" in result.lower()


@pytest.mark.asyncio
async def test_conflicts_shows_cascade_source():
    stage = _make_stage()
    a1 = _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    a2 = _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    conflict = Conflict(
        assertion_a_id=a1.id,
        assertion_b_id=a2.id,
        topic_path="/arch/db",
        detection_layer=ConflictDetectionLayer.CASCADING,
        cascade_source_path="/arch",
    )
    stage.conflicts[conflict.id] = conflict
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_conflicts_state(PROJECT_ID, ctx)
    assert "Cascade from" in result
    assert "/arch" in result


# ═══════════════════════════════════════════════════════════════
# Resources: get_variants_state
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_variants_project_not_loaded():
    ctx = _make_ctx({})
    result = await get_variants_state(PROJECT_ID, ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_variants_empty():
    stage = _make_stage()
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_variants_state(PROJECT_ID, ctx)
    assert "No variant sets" in result


@pytest.mark.asyncio
async def test_variants_shows_open_set():
    stage = _make_stage()
    vs = VariantSet(
        name="DB Choice",
        topic_path="/arch/db",
        variants=[
            Variant(name="postgres", content="PostgreSQL for ACID compliance"),
            Variant(name="mongo", content="MongoDB for flexibility"),
        ],
    )
    stage.variant_sets[vs.id] = vs
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_variants_state(PROJECT_ID, ctx)
    assert "DB Choice" in result
    assert "OPEN" in result
    assert "postgres" in result
    assert "mongo" in result


@pytest.mark.asyncio
async def test_variants_shows_resolved_set():
    stage = _make_stage()
    vs = VariantSet(
        name="DB Choice",
        topic_path="/arch/db",
        variants=[
            Variant(name="postgres", content="PostgreSQL for ACID compliance"),
            Variant(name="mongo", content="MongoDB for flexibility"),
        ],
        resolved=True,
        resolved_variant_name="postgres",
    )
    stage.variant_sets[vs.id] = vs
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_variants_state(PROJECT_ID, ctx)
    assert "RESOLVED" in result
    assert "WINNER" in result
    assert "postgres" in result


# ═══════════════════════════════════════════════════════════════
# Resources: get_audit_trail
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_audit_project_not_loaded():
    ctx = _make_ctx({})
    result = await get_audit_trail(PROJECT_ID, ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_audit_empty():
    stage = _make_stage()
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_audit_trail(PROJECT_ID, ctx)
    assert "No events" in result


@pytest.mark.asyncio
async def test_audit_shows_event_counts_and_recent():
    stage = _make_stage()
    stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_abc", {})
    stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.USER, "ast_xyz", {})
    stage.record_event(EventType.CONFLICT_DETECTED, AssertionAuthor.SYSTEM, "cfl_001", {})
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_audit_trail(PROJECT_ID, ctx)
    assert "3 events" in result
    assert "assertion_created" in result
    assert "conflict_detected" in result
    # Recent events section
    assert "Last" in result


# ═══════════════════════════════════════════════════════════════
# Resources: get_dependencies_view
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_dependencies_project_not_loaded():
    ctx = _make_ctx({})
    result = await get_dependencies_view(PROJECT_ID, ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_dependencies_empty():
    stage = _make_stage()
    _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_dependencies_view(PROJECT_ID, ctx)
    assert "No dependency relationships" in result


@pytest.mark.asyncio
async def test_dependencies_shows_dag():
    stage = _make_stage()
    _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    dependent = _add_assertion(
        stage,
        "/arch/app",
        "Use SQLAlchemy ORM",
        CompositionArc.INHERITS,
        depends_on_paths=["/arch/db"],
    )
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_dependencies_view(PROJECT_ID, ctx)
    assert "/arch/app" in result
    assert "/arch/db" in result
    assert "PostgreSQL" in result
    assert "SQLAlchemy" in result


@pytest.mark.asyncio
async def test_dependencies_shows_missing_dependency():
    """An assertion that depends on a path with no assertions shows '(no assertion)'."""
    stage = _make_stage()
    _add_assertion(
        stage,
        "/arch/app",
        "Depends on the cache layer",
        CompositionArc.INHERITS,
        depends_on_paths=["/arch/cache"],
    )
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_dependencies_view(PROJECT_ID, ctx)
    assert "(no assertion)" in result
    assert "/arch/cache" in result


# ═══════════════════════════════════════════════════════════════
# Resources: get_payloads_view
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_payloads_project_not_loaded():
    ctx = _make_ctx({})
    result = await get_payloads_view(PROJECT_ID, ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_payloads_empty():
    stage = _make_stage()
    _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_payloads_view(PROJECT_ID, ctx)
    assert "No pending payloads" in result


@pytest.mark.asyncio
async def test_payloads_shows_payload_assertions():
    stage = _make_stage()
    payload = Assertion(
        topic_path="/arch/perf",
        content="Benchmark query latency under load",
        arc=CompositionArc.PAYLOADS,
        author=AssertionAuthor.AI,
        tags=["benchmark", "performance"],
    )
    stage.assertions[payload.id] = payload
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await get_payloads_view(PROJECT_ID, ctx)
    assert "PAYLOAD" in result
    assert "/arch/perf" in result
    assert "Benchmark query latency" in result
    assert "benchmark" in result
    assert "known unknowns" in result.lower()


# ═══════════════════════════════════════════════════════════════
# Prompts: coworker_posture
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_posture_project_not_loaded():
    ctx = _make_ctx({})
    result = await coworker_posture(PROJECT_ID, ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_posture_learning():
    """Less than 3 assertions -> LEARNING posture."""
    stage = _make_stage()
    _add_assertion(stage, "/arch/db", "Initial thought", CompositionArc.INHERITS)
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await coworker_posture(PROJECT_ID, ctx)
    assert "LEARNING" in result
    assert "Posture: LEARNING" in result


@pytest.mark.asyncio
async def test_posture_engaged():
    """Active conflict present -> ENGAGED posture."""
    stage = _make_stage()
    for i in range(3):
        _add_assertion(stage, f"/arch/comp{i}", f"Claim {i}", CompositionArc.INHERITS)
    a1 = _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    a2 = _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    conflict = Conflict(
        assertion_a_id=a1.id,
        assertion_b_id=a2.id,
        topic_path="/arch/db",
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
        status=ConflictStatus.ACTIVE,
    )
    stage.conflicts[conflict.id] = conflict
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await coworker_posture(PROJECT_ID, ctx)
    assert "ENGAGED" in result
    assert "Posture: ENGAGED" in result


@pytest.mark.asyncio
async def test_posture_authoritative():
    """Many LOCAL assertions, below red_team_threshold, no conflicts -> AUTHORITATIVE."""
    stage = _make_stage()
    # red_team_threshold defaults to 8, so add 5 LOCAL assertions (below threshold)
    # and ensure assertion count >= 3
    for i in range(5):
        _add_assertion(
            stage,
            f"/arch/comp{i}",
            f"Verified decision {i}",
            CompositionArc.LOCAL,
            falsifiable_if="Evidence X emerges",
        )
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await coworker_posture(PROJECT_ID, ctx)
    assert "AUTHORITATIVE" in result
    assert "Posture: AUTHORITATIVE" in result


@pytest.mark.asyncio
async def test_posture_red_teaming():
    """LOCAL count >= red_team_threshold with no active conflicts -> RED_TEAMING."""
    stage = _make_stage()
    threshold = stage.parameters.red_team_threshold  # default 8
    for i in range(threshold):
        _add_assertion(
            stage,
            f"/arch/comp{i}",
            f"Settled decision {i}",
            CompositionArc.LOCAL,
            falsifiable_if="Contradicting evidence",
        )
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await coworker_posture(PROJECT_ID, ctx)
    assert "RED_TEAMING" in result
    assert "Posture: RED_TEAMING" in result
    assert "blind spots" in result.lower()


# ═══════════════════════════════════════════════════════════════
# Prompts: conflict_negotiation
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_conflict_negotiation_project_not_loaded():
    ctx = _make_ctx({})
    result = await conflict_negotiation(PROJECT_ID, "cfl_abc", ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_conflict_negotiation_not_found():
    stage = _make_stage()
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await conflict_negotiation(PROJECT_ID, "cfl_nonexistent", ctx)
    assert "not found" in result


@pytest.mark.asyncio
async def test_conflict_negotiation_shows_positions():
    stage = _make_stage()
    a1 = _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    a2 = _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    conflict = Conflict(
        assertion_a_id=a1.id,
        assertion_b_id=a2.id,
        topic_path="/arch/db",
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )
    stage.conflicts[conflict.id] = conflict
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await conflict_negotiation(PROJECT_ID, conflict.id, ctx)
    assert "CONFLICT NEGOTIATION" in result
    assert "/arch/db" in result
    assert "PostgreSQL" in result
    assert "MySQL" in result
    # All resolution paths present
    assert "ACCEPT" in result
    assert "CHALLENGE" in result
    assert "PROPOSE_EXPERIMENT" in result
    assert "steelman_summary" in result


@pytest.mark.asyncio
async def test_conflict_negotiation_shows_cascade_source():
    stage = _make_stage()
    a1 = _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    a2 = _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    conflict = Conflict(
        assertion_a_id=a1.id,
        assertion_b_id=a2.id,
        topic_path="/arch/db",
        detection_layer=ConflictDetectionLayer.CASCADING,
        cascade_source_path="/arch/infra",
    )
    stage.conflicts[conflict.id] = conflict
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await conflict_negotiation(PROJECT_ID, conflict.id, ctx)
    assert "Cascade origin" in result
    assert "/arch/infra" in result


@pytest.mark.asyncio
async def test_conflict_negotiation_shows_steelman():
    stage = _make_stage()
    a1 = _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    a2 = _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    conflict = Conflict(
        assertion_a_id=a1.id,
        assertion_b_id=a2.id,
        topic_path="/arch/db",
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
        steelman_of_opponent="MySQL has better JSON support and is simpler to operate.",
    )
    stage.conflicts[conflict.id] = conflict
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await conflict_negotiation(PROJECT_ID, conflict.id, ctx)
    assert "Steelman on record" in result
    assert "MySQL has better JSON support" in result


# ═══════════════════════════════════════════════════════════════
# Prompts: stage_summary
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_stage_summary_project_not_loaded():
    ctx = _make_ctx({})
    result = await stage_summary(PROJECT_ID, ctx)
    assert "not loaded" in result


@pytest.mark.asyncio
async def test_stage_summary_shows_stats():
    stage = _make_stage()
    for i in range(3):
        _add_assertion(
            stage, f"/arch/comp{i}", f"Claim {i}", CompositionArc.LOCAL,
            falsifiable_if="Evidence X"
        )
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await stage_summary(PROJECT_ID, ctx)
    assert "COMPOSITION STAGE SUMMARY" in result
    assert "Test Project" in result
    assert "Assertions:" in result
    assert "Conflicts:" in result
    assert "Decisions:" in result
    assert "Exchange count:" in result


@pytest.mark.asyncio
async def test_stage_summary_attention_paths():
    """Paths with active conflicts appear in attention section."""
    stage = _make_stage()
    for i in range(3):
        _add_assertion(
            stage, f"/arch/comp{i}", f"Claim {i}", CompositionArc.INHERITS
        )
    a1 = _add_assertion(stage, "/arch/db", "Use PostgreSQL", CompositionArc.INHERITS)
    a2 = _add_assertion(stage, "/arch/db", "Use MySQL", CompositionArc.INHERITS)
    conflict = Conflict(
        assertion_a_id=a1.id,
        assertion_b_id=a2.id,
        topic_path="/arch/db",
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
        status=ConflictStatus.ACTIVE,
    )
    stage.conflicts[conflict.id] = conflict
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await stage_summary(PROJECT_ID, ctx)
    assert "PATHS REQUIRING ATTENTION" in result
    assert "/arch/db" in result


@pytest.mark.asyncio
async def test_stage_summary_posture_label():
    """Summary includes a posture label computed from stage state."""
    stage = _make_stage()
    # Empty stage -> LEARNING
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await stage_summary(PROJECT_ID, ctx)
    assert "LEARNING" in result


@pytest.mark.asyncio
async def test_stage_summary_open_variant_sets():
    """Open variant sets appear in the summary."""
    stage = _make_stage()
    for i in range(3):
        _add_assertion(
            stage, f"/arch/comp{i}", f"Claim {i}", CompositionArc.INHERITS
        )
    vs = VariantSet(
        name="Caching Strategy",
        topic_path="/arch/cache",
        variants=[
            Variant(name="redis", content="Redis for speed"),
            Variant(name="memcached", content="Memcached for simplicity"),
        ],
    )
    stage.variant_sets[vs.id] = vs
    ctx = _make_ctx({PROJECT_ID: stage})
    result = await stage_summary(PROJECT_ID, ctx)
    assert "OPEN VARIANT SETS" in result
    assert "Caching Strategy" in result


# ═══════════════════════════════════════════════════════════════
# kernel://{project_id}
# ═══════════════════════════════════════════════════════════════


class _MockCtxWithStore:
    """Mock context with a real in-memory SQLiteStore for kernel tests."""

    def __init__(
        self, active_stages: dict, store: "SQLiteStore"
    ) -> None:
        self.lifespan_context = {
            "active_stages": active_stages,
            "store": store,
        }


class TestKernelResource:
    """Tests for the kernel://{project_id} resource."""

    @pytest.fixture(autouse=True)
    def _clear_kernel_cache(self) -> None:
        from cognitive_bridge.tools.probe_tool import _KERNELS
        _KERNELS.clear()
        yield
        _KERNELS.clear()

    def _make_ctx_with_store(
        self, project_id: str = PROJECT_ID
    ) -> _MockCtxWithStore:
        from cognitive_bridge.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(":memory:")
        stage = _make_stage(project_id)
        return _MockCtxWithStore(
            active_stages={project_id: stage}, store=store
        )

    @pytest.mark.asyncio
    async def test_project_not_loaded(self) -> None:
        from cognitive_bridge.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(":memory:")
        ctx = _MockCtxWithStore(active_stages={}, store=store)
        result = await get_kernel_state("missing", ctx)
        assert "not loaded" in result

    @pytest.mark.asyncio
    async def test_fresh_kernel_returns_defaults(self) -> None:
        ctx = self._make_ctx_with_store()
        result = await get_kernel_state(PROJECT_ID, ctx)
        assert "entropy_tolerance" in result
        assert "process_purity" in result
        assert "autonomy_boundary" in result
        assert "energy_level" in result
        assert "0.5" in result  # Default value

    @pytest.mark.asyncio
    async def test_kernel_shows_probe_count(self) -> None:
        ctx = self._make_ctx_with_store()
        result = await get_kernel_state(PROJECT_ID, ctx)
        assert "Probe count:" in result
        assert "0" in result  # No probes yet

    @pytest.mark.asyncio
    async def test_kernel_shows_last_probed_never(self) -> None:
        ctx = self._make_ctx_with_store()
        result = await get_kernel_state(PROJECT_ID, ctx)
        assert "never" in result

    @pytest.mark.asyncio
    async def test_kernel_after_probe(self) -> None:
        import asyncio
        from cognitive_bridge.tools.probe_tool import cb_probe_user

        ctx = self._make_ctx_with_store()
        # Probe to update kernel
        await cb_probe_user(
            probe_type="entropy", value=0.9, ctx=ctx
        )
        result = await get_kernel_state(PROJECT_ID, ctx)
        # Should show smoothed value, not 0.5 default
        assert "0.5" not in result or "Probe count:  1" in result
        assert "Probe count:  1" in result

    @pytest.mark.asyncio
    async def test_kernel_contains_header(self) -> None:
        ctx = self._make_ctx_with_store()
        result = await get_kernel_state(PROJECT_ID, ctx)
        assert f"COS Individual Kernel for '{PROJECT_ID}'" in result

    @pytest.mark.asyncio
    async def test_kernel_mentions_auto_tuning(self) -> None:
        ctx = self._make_ctx_with_store()
        result = await get_kernel_state(PROJECT_ID, ctx)
        assert "auto-tuning" in result
