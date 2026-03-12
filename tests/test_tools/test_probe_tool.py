"""Integration tests for the cb_probe_user tool.

Tests call the tool handler directly using a minimal mock Context whose
lifespan_context carries an in-memory SQLiteStore and an isolated
active_stages dict. This avoids MCP transport overhead while exercising
every probe type, smoothing logic, persistence path, and error branch.

The module-level _KERNELS cache is cleared before and after every test via
the autouse fixture to prevent inter-test contamination.
"""

import pytest

from cognitive_bridge.models import CompositionStage
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import KernelRow, SQLiteStore
from cognitive_bridge.tools.probe_tool import (
    _KERNELS,
    _EMA_ALPHA,
    cb_probe_user,
    get_kernel,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def clear_kernel_cache():
    """Clear the module-level _KERNELS cache before and after every test."""
    _KERNELS.clear()
    yield
    _KERNELS.clear()


class _MockCtx:
    """Minimal context mock that satisfies ctx.lifespan_context access."""

    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {
            "store": store,
            "active_stages": active_stages,
        }


def _make_ctx_with_stage(
    project_id: str = "proj_test",
) -> tuple["_MockCtx", CompositionStage, SQLiteStore]:
    """Create a context, stage, and store pre-wired together."""
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Test Project")
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    ctx = _MockCtx(store=store, active_stages=active_stages)
    return ctx, stage, store


def _make_empty_ctx() -> "_MockCtx":
    """Create a context with no active projects."""
    store = SQLiteStore(":memory:")
    return _MockCtx(store=store, active_stages={})


# ═══════════════════════════════════════════════════════════════
# Test: probe types — all four dimensions updated
# ═══════════════════════════════════════════════════════════════


class TestProbeTypes:
    """Verify each of the four probe_type values updates the correct field."""

    @pytest.mark.asyncio
    async def test_probe_entropy(self) -> None:
        """probe_type='entropy' updates entropy_tolerance."""
        ctx, _stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="entropy", value=0.8, ctx=ctx)

        assert "entropy_tolerance" in result
        kernel = get_kernel(store, "proj_test")
        # Smoothed from default 0.5: 0.7*0.8 + 0.3*0.5 = 0.71
        assert kernel.entropy_tolerance == pytest.approx(0.71, abs=1e-4)

    @pytest.mark.asyncio
    async def test_probe_process(self) -> None:
        """probe_type='process' updates process_purity."""
        ctx, _stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="process", value=0.2, ctx=ctx)

        assert "process_purity" in result
        kernel = get_kernel(store, "proj_test")
        # Smoothed from default 0.5: 0.7*0.2 + 0.3*0.5 = 0.29
        assert kernel.process_purity == pytest.approx(0.29, abs=1e-4)

    @pytest.mark.asyncio
    async def test_probe_autonomy(self) -> None:
        """probe_type='autonomy' updates autonomy_boundary."""
        ctx, _stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="autonomy", value=0.9, ctx=ctx)

        assert "autonomy_boundary" in result
        kernel = get_kernel(store, "proj_test")
        # Smoothed from default 0.5: 0.7*0.9 + 0.3*0.5 = 0.78
        assert kernel.autonomy_boundary == pytest.approx(0.78, abs=1e-4)

    @pytest.mark.asyncio
    async def test_probe_energy(self) -> None:
        """probe_type='energy' updates energy_level."""
        ctx, _stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="energy", value=0.1, ctx=ctx)

        assert "energy_level" in result
        kernel = get_kernel(store, "proj_test")
        # Smoothed from default 0.5: 0.7*0.1 + 0.3*0.5 = 0.22
        assert kernel.energy_level == pytest.approx(0.22, abs=1e-4)


# ═══════════════════════════════════════════════════════════════
# Test: validation errors
# ═══════════════════════════════════════════════════════════════


class TestValidationErrors:
    """Verify that invalid inputs are rejected with ERROR responses."""

    @pytest.mark.asyncio
    async def test_invalid_probe_type(self) -> None:
        """An unrecognised probe_type returns an ERROR naming valid types."""
        ctx, _stage, _store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="focus", value=0.5, ctx=ctx)

        assert result.startswith("ERROR:")
        assert "focus" in result
        # All valid types should be mentioned so Claude can self-correct
        for valid in ("entropy", "process", "autonomy", "energy"):
            assert valid in result

    @pytest.mark.asyncio
    async def test_value_too_high(self) -> None:
        """A value > 1.0 returns an ERROR."""
        ctx, _stage, _store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="energy", value=1.5, ctx=ctx)

        assert result.startswith("ERROR:")
        assert "1.5" in result

    @pytest.mark.asyncio
    async def test_value_negative(self) -> None:
        """A negative value returns an ERROR."""
        ctx, _stage, _store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="energy", value=-0.1, ctx=ctx)

        assert result.startswith("ERROR:")
        assert "-0.1" in result

    @pytest.mark.asyncio
    async def test_value_boundary_zero_valid(self) -> None:
        """value=0.0 is valid (on the boundary)."""
        ctx, _stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="energy", value=0.0, ctx=ctx)

        assert not result.startswith("ERROR:")
        kernel = get_kernel(store, "proj_test")
        # Smoothed from 0.5: 0.7*0.0 + 0.3*0.5 = 0.15
        assert kernel.energy_level == pytest.approx(0.15, abs=1e-4)

    @pytest.mark.asyncio
    async def test_value_boundary_one_valid(self) -> None:
        """value=1.0 is valid (on the boundary)."""
        ctx, _stage, store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="entropy", value=1.0, ctx=ctx)

        assert not result.startswith("ERROR:")
        kernel = get_kernel(store, "proj_test")
        # Smoothed from 0.5: 0.7*1.0 + 0.3*0.5 = 0.85
        assert kernel.entropy_tolerance == pytest.approx(0.85, abs=1e-4)


# ═══════════════════════════════════════════════════════════════
# Test: smoothing behaviour
# ═══════════════════════════════════════════════════════════════


class TestSmoothing:
    """Verify the EMA smoothing formula is applied correctly."""

    @pytest.mark.asyncio
    async def test_smoothing_applied_first_probe(self) -> None:
        """First probe at 0.8: smoothed = alpha*0.8 + (1-alpha)*0.5 = 0.71."""
        ctx, _stage, store = _make_ctx_with_stage()
        await cb_probe_user(probe_type="entropy", value=0.8, ctx=ctx)

        kernel = get_kernel(store, "proj_test")
        expected = round(_EMA_ALPHA * 0.8 + (1.0 - _EMA_ALPHA) * 0.5, 4)
        assert kernel.entropy_tolerance == pytest.approx(expected, abs=1e-4)

    @pytest.mark.asyncio
    async def test_smoothing_second_probe_uses_previous_smoothed(self) -> None:
        """Second probe uses the smoothed value from the first as its baseline."""
        ctx, _stage, store = _make_ctx_with_stage()

        # First probe
        await cb_probe_user(probe_type="entropy", value=0.8, ctx=ctx)
        after_first = get_kernel(store, "proj_test").entropy_tolerance

        # Second probe
        await cb_probe_user(probe_type="entropy", value=0.6, ctx=ctx)
        after_second = get_kernel(store, "proj_test").entropy_tolerance

        expected = round(_EMA_ALPHA * 0.6 + (1.0 - _EMA_ALPHA) * after_first, 4)
        assert after_second == pytest.approx(expected, abs=1e-4)

    @pytest.mark.asyncio
    async def test_unprobed_dimensions_unchanged(self) -> None:
        """Probing 'entropy' does not alter process_purity, autonomy_boundary, or energy_level."""
        ctx, _stage, store = _make_ctx_with_stage()
        await cb_probe_user(probe_type="entropy", value=0.9, ctx=ctx)

        kernel = get_kernel(store, "proj_test")
        assert kernel.process_purity == pytest.approx(0.5, abs=1e-4)
        assert kernel.autonomy_boundary == pytest.approx(0.5, abs=1e-4)
        assert kernel.energy_level == pytest.approx(0.5, abs=1e-4)


# ═══════════════════════════════════════════════════════════════
# Test: probe_count and last_probed metadata
# ═══════════════════════════════════════════════════════════════


class TestMetadata:
    """Verify probe_count and last_probed are updated correctly."""

    @pytest.mark.asyncio
    async def test_probe_count_increments(self) -> None:
        """Three probes yield probe_count == 3."""
        ctx, _stage, store = _make_ctx_with_stage()
        for pt in ("entropy", "process", "energy"):
            await cb_probe_user(probe_type=pt, value=0.5, ctx=ctx)

        kernel = get_kernel(store, "proj_test")
        assert kernel.probe_count == 3

    @pytest.mark.asyncio
    async def test_last_probed_set_after_probe(self) -> None:
        """last_probed is None on a fresh kernel and is set after a probe."""
        ctx, _stage, store = _make_ctx_with_stage()

        # Fresh kernel should have last_probed = None
        fresh = get_kernel(store, "proj_test")
        assert fresh.last_probed is None

        await cb_probe_user(probe_type="energy", value=0.7, ctx=ctx)

        kernel = get_kernel(store, "proj_test")
        assert kernel.last_probed is not None

    @pytest.mark.asyncio
    async def test_probe_count_in_response(self) -> None:
        """The response includes the updated probe_count."""
        ctx, _stage, _store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="energy", value=0.7, ctx=ctx)

        assert "Probe count: 1" in result


# ═══════════════════════════════════════════════════════════════
# Test: persistence
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """Verify the kernel survives a cache clear and is reloaded from SQLite."""

    @pytest.mark.asyncio
    async def test_kernel_persisted_survives_cache_clear(self) -> None:
        """After probing and clearing the cache, the kernel reloads from DB."""
        ctx, _stage, store = _make_ctx_with_stage()
        await cb_probe_user(probe_type="entropy", value=0.8, ctx=ctx)

        # Capture the smoothed value before clearing
        before_clear = get_kernel(store, "proj_test").entropy_tolerance

        # Simulate a server restart by wiping the in-process cache
        _KERNELS.clear()

        # Should reload from SQLite
        reloaded = get_kernel(store, "proj_test")
        assert reloaded.entropy_tolerance == pytest.approx(before_clear, abs=1e-4)

    @pytest.mark.asyncio
    async def test_kernel_persisted_probe_count_survives_reload(self) -> None:
        """probe_count is preserved across a cache clear."""
        ctx, _stage, store = _make_ctx_with_stage()

        await cb_probe_user(probe_type="entropy", value=0.8, ctx=ctx)
        await cb_probe_user(probe_type="process", value=0.3, ctx=ctx)

        _KERNELS.clear()

        reloaded = get_kernel(store, "proj_test")
        assert reloaded.probe_count == 2


# ═══════════════════════════════════════════════════════════════
# Test: fresh kernel defaults
# ═══════════════════════════════════════════════════════════════


class TestFreshKernel:
    """Verify a new project starts with a neutral kernel (all dims at 0.5)."""

    @pytest.mark.asyncio
    async def test_new_project_creates_fresh_kernel(self) -> None:
        """A project with no prior kernel record gets all dimensions at 0.5."""
        _store = SQLiteStore(":memory:")
        kernel = get_kernel(_store, "brand_new_project")

        assert kernel.entropy_tolerance == pytest.approx(0.5, abs=1e-4)
        assert kernel.process_purity == pytest.approx(0.5, abs=1e-4)
        assert kernel.autonomy_boundary == pytest.approx(0.5, abs=1e-4)
        assert kernel.energy_level == pytest.approx(0.5, abs=1e-4)
        assert kernel.probe_count == 0
        assert kernel.last_probed is None

    @pytest.mark.asyncio
    async def test_fresh_kernel_not_in_db(self) -> None:
        """get_kernel for a new project does NOT persist to DB until a probe fires."""
        _store = SQLiteStore(":memory:")
        get_kernel(_store, "ghost_project")

        # The DB should have no kernel row for ghost_project
        with _store.get_session() as session:
            from sqlmodel import select

            rows = session.exec(
                select(KernelRow).where(KernelRow.project_id == "ghost_project")
            ).all()
        assert len(rows) == 0


# ═══════════════════════════════════════════════════════════════
# Test: response formatting
# ═══════════════════════════════════════════════════════════════


class TestResponseFormatting:
    """Verify the tool response contains all expected sections."""

    @pytest.mark.asyncio
    async def test_response_contains_all_four_dimensions(self) -> None:
        """The response shows all four kernel dimensions regardless of which was probed."""
        ctx, _stage, _store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="energy", value=0.6, ctx=ctx)

        assert "entropy_tolerance" in result
        assert "process_purity" in result
        assert "autonomy_boundary" in result
        assert "energy_level" in result

    @pytest.mark.asyncio
    async def test_response_contains_raw_and_smoothed(self) -> None:
        """The response shows both the raw probe value and the smoothed result."""
        ctx, _stage, _store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="entropy", value=0.8, ctx=ctx)

        assert "Raw value: 0.8" in result
        assert "Smoothed: 0.71" in result

    @pytest.mark.asyncio
    async def test_response_contains_probe_type_name(self) -> None:
        """The response names the probe_type that was applied."""
        ctx, _stage, _store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="process", value=0.4, ctx=ctx)

        assert "Probe: process" in result

    @pytest.mark.asyncio
    async def test_response_contains_project_id(self) -> None:
        """The response mentions the project whose kernel was updated."""
        ctx, _stage, _store = _make_ctx_with_stage("my_project")
        result = await cb_probe_user(probe_type="energy", value=0.5, ctx=ctx)

        assert "my_project" in result

    @pytest.mark.asyncio
    async def test_response_contains_previous_value(self) -> None:
        """The response shows the previous (pre-smooth) value for the probed dimension."""
        ctx, _stage, _store = _make_ctx_with_stage()
        result = await cb_probe_user(probe_type="entropy", value=0.8, ctx=ctx)

        # Default starting value is 0.5
        assert "Previous: 0.5" in result


# ═══════════════════════════════════════════════════════════════
# Test: no active project
# ═══════════════════════════════════════════════════════════════


class TestNoActiveProject:
    """Verify error handling when no project is active."""

    @pytest.mark.asyncio
    async def test_no_active_project(self) -> None:
        """With no active stages, cb_probe_user returns an ERROR."""
        ctx = _make_empty_ctx()
        result = await cb_probe_user(probe_type="energy", value=0.5, ctx=ctx)

        assert result.startswith("ERROR:")
        assert "No active project" in result

    @pytest.mark.asyncio
    async def test_named_project_not_active(self) -> None:
        """Specifying a project_id that is not active returns an ERROR."""
        ctx, _stage, _store = _make_ctx_with_stage("proj_alpha")
        result = await cb_probe_user(
            probe_type="energy", value=0.5, ctx=ctx, project_id="proj_beta"
        )

        assert result.startswith("ERROR:")
        assert "proj_beta" in result
