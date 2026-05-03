"""Integration tests for the cb_probe_user tool.

Blueprint reference: Section 3.9 (IndividualKernel), Phase 3 (cb_probe_user).
Constitution rules G2, G5 (test isolation via unique project IDs).

Note: cb_probe_user uses a module-level _KERNELS cache keyed by project_id.
Tests use unique project IDs to avoid cross-test cache pollution.
"""

import uuid

import pytest

from cognitive_bridge.models import CompositionStage
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.probe_tool import _KERNELS, cb_probe_user, get_kernel


class _MockCtx:
    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx(store: SQLiteStore | None = None, active_stages: dict | None = None) -> _MockCtx:
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


def _unique_project_id() -> str:
    return f"proj_probe_{uuid.uuid4().hex[:8]}"


def _make_ctx_with_stage(project_id: str | None = None) -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    pid = project_id or _unique_project_id()
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=pid, project_name="Probe Test Project")
    active_stages: dict = {pid: stage}
    save_stage_to_db(store, stage)
    return _make_ctx(store=store, active_stages=active_stages), stage, store


def _evict_kernel_cache(project_id: str) -> None:
    _KERNELS.pop(project_id, None)


class TestProbeDimensions:
    @pytest.mark.asyncio
    async def test_probe_entropy_updates_kernel(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        result = await cb_probe_user(probe_type="entropy", value=0.8, ctx=ctx)
        assert "ERROR" not in result
        assert _KERNELS[pid].entropy_tolerance != 0.5

    @pytest.mark.asyncio
    async def test_probe_process_updates_kernel(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        result = await cb_probe_user(probe_type="process", value=0.9, ctx=ctx)
        assert "ERROR" not in result
        assert _KERNELS[pid].process_purity != 0.5

    @pytest.mark.asyncio
    async def test_probe_autonomy_updates_kernel(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        result = await cb_probe_user(probe_type="autonomy", value=0.3, ctx=ctx)
        assert "ERROR" not in result
        assert _KERNELS[pid].autonomy_boundary != 0.5

    @pytest.mark.asyncio
    async def test_probe_energy_updates_kernel(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        result = await cb_probe_user(probe_type="energy", value=0.1, ctx=ctx)
        assert "ERROR" not in result
        assert _KERNELS[pid].energy_level != 0.5

    @pytest.mark.asyncio
    async def test_probe_response_includes_raw_and_smoothed_values(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        result = await cb_probe_user(probe_type="entropy", value=0.9, ctx=ctx)
        assert "Raw value: 0.9" in result
        assert "Smoothed:" in result
        assert "Previous:" in result

    @pytest.mark.asyncio
    async def test_probe_response_shows_probe_count(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        result = await cb_probe_user(probe_type="energy", value=0.7, ctx=ctx)
        assert "Probe count: 1" in result


class TestEMASmoothing:
    @pytest.mark.asyncio
    async def test_ema_smoothing_applied_correctly(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        await cb_probe_user(probe_type="entropy", value=1.0, ctx=ctx)
        expected = round(0.7 * 1.0 + 0.3 * 0.5, 4)
        assert _KERNELS[pid].entropy_tolerance == expected

    @pytest.mark.asyncio
    async def test_successive_probes_accumulate(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        await cb_probe_user(probe_type="energy", value=1.0, ctx=ctx)
        after_first = _KERNELS[pid].energy_level
        await cb_probe_user(probe_type="energy", value=0.0, ctx=ctx)
        expected = round(0.7 * 0.0 + 0.3 * after_first, 4)
        assert _KERNELS[pid].energy_level == expected

    @pytest.mark.asyncio
    async def test_probe_count_increments_on_each_probe(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        await cb_probe_user(probe_type="entropy", value=0.5, ctx=ctx)
        await cb_probe_user(probe_type="process", value=0.5, ctx=ctx)
        await cb_probe_user(probe_type="autonomy", value=0.5, ctx=ctx)
        assert _KERNELS[pid].probe_count == 3


class TestKernelSingletonPreservation:
    @pytest.mark.asyncio
    async def test_same_kernel_id_preserved_across_probes(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        await cb_probe_user(probe_type="entropy", value=0.6, ctx=ctx)
        first_id = _KERNELS[pid].id
        await cb_probe_user(probe_type="process", value=0.7, ctx=ctx)
        assert _KERNELS[pid].id == first_id

    @pytest.mark.asyncio
    async def test_kernel_last_probed_updates(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        await cb_probe_user(probe_type="entropy", value=0.6, ctx=ctx)
        assert _KERNELS[pid].last_probed is not None

    @pytest.mark.asyncio
    async def test_get_kernel_accessor_returns_same_object(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        await cb_probe_user(probe_type="entropy", value=0.6, ctx=ctx)
        retrieved = get_kernel(store, pid)
        assert retrieved.id == _KERNELS[pid].id
        assert retrieved.entropy_tolerance == _KERNELS[pid].entropy_tolerance


class TestKernelPersistence:
    @pytest.mark.asyncio
    async def test_kernel_persists_to_db_after_probe(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        await cb_probe_user(probe_type="entropy", value=0.9, ctx=ctx)
        in_memory = _KERNELS[pid].entropy_tolerance
        _evict_kernel_cache(pid)
        loaded = get_kernel(store, pid)
        assert abs(loaded.entropy_tolerance - in_memory) < 1e-9

    @pytest.mark.asyncio
    async def test_probe_count_persists_across_cache_eviction(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        await cb_probe_user(probe_type="process", value=0.7, ctx=ctx)
        await cb_probe_user(probe_type="energy", value=0.3, ctx=ctx)
        _evict_kernel_cache(pid)
        loaded = get_kernel(store, pid)
        assert loaded.probe_count == 2


class TestValidationRejection:
    @pytest.mark.asyncio
    async def test_value_above_one_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="entropy", value=1.5, ctx=ctx)
        assert result.startswith("ERROR:")
        assert "0.0" in result or "1.0" in result

    @pytest.mark.asyncio
    async def test_value_below_zero_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="entropy", value=-0.1, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_value_at_zero_boundary_succeeds(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        result = await cb_probe_user(probe_type="energy", value=0.0, ctx=ctx)
        assert "ERROR" not in result

    @pytest.mark.asyncio
    async def test_value_at_one_boundary_succeeds(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        result = await cb_probe_user(probe_type="energy", value=1.0, ctx=ctx)
        assert "ERROR" not in result

    @pytest.mark.asyncio
    async def test_invalid_probe_type_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="mood", value=0.5, ctx=ctx)
        assert result.startswith("ERROR:")
        assert "entropy" in result
        assert "process" in result
        assert "autonomy" in result
        assert "energy" in result

    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        ctx = _make_ctx()
        result = await cb_probe_user(probe_type="entropy", value=0.5, ctx=ctx)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_kernel_not_updated_when_value_invalid(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        pid = next(iter(ctx.lifespan_context["active_stages"]))
        _evict_kernel_cache(pid)
        from cognitive_bridge.tools.probe_tool import _get_or_create_kernel
        kernel = _get_or_create_kernel(store, pid)
        original_entropy = kernel.entropy_tolerance
        original_count = kernel.probe_count
        await cb_probe_user(probe_type="entropy", value=2.0, ctx=ctx)
        assert _KERNELS[pid].entropy_tolerance == original_entropy
        assert _KERNELS[pid].probe_count == original_count
