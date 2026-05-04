"""Tests for models/kernel.py — IndividualKernel COS dimension validation.

Blueprint reference: Section 3.9 (IndividualKernel / COS profiling) and
Phase 3.1 (cb_probe_user — Kernel stored as singleton per project).
Constitution rule G2 (validator-rejection symmetry).
"""

from datetime import datetime, timezone
from typing import Optional

import pytest
from pydantic import ValidationError

from cognitive_bridge.models.kernel import IndividualKernel

_TS = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_TS2 = datetime(2025, 7, 1, 9, 30, 0, tzinfo=timezone.utc)


def _make_kernel(**overrides) -> IndividualKernel:
    defaults = dict(
        id="ker_aabbccddeeff",
        entropy_tolerance=0.7, process_purity=0.3,
        autonomy_boundary=0.6, energy_level=0.8,
        probe_count=2, last_probed=_TS2,
        created_at=_TS, updated_at=_TS2,
    )
    defaults.update(overrides)
    return IndividualKernel(**defaults)


class TestIndividualKernelDefaults:
    def test_all_dimension_defaults_at_half(self) -> None:
        k = IndividualKernel()
        assert k.entropy_tolerance == 0.5
        assert k.process_purity == 0.5
        assert k.autonomy_boundary == 0.5
        assert k.energy_level == 0.5

    def test_probe_count_default_zero(self) -> None:
        assert IndividualKernel().probe_count == 0

    def test_last_probed_default_none(self) -> None:
        assert IndividualKernel().last_probed is None

    def test_id_prefix_ker(self) -> None:
        k = IndividualKernel()
        assert k.id.startswith("ker_")
        assert len(k.id) == 16

    def test_id_uniqueness(self) -> None:
        ids = {IndividualKernel().id for _ in range(30)}
        assert len(ids) == 30

    def test_created_at_is_timezone_aware_utc(self) -> None:
        assert IndividualKernel().created_at.tzinfo == timezone.utc

    def test_updated_at_is_timezone_aware_utc(self) -> None:
        assert IndividualKernel().updated_at.tzinfo == timezone.utc


class TestLastProbed:
    def test_last_probed_none_is_allowed(self) -> None:
        assert _make_kernel(last_probed=None).last_probed is None

    def test_last_probed_datetime_accepted(self) -> None:
        assert _make_kernel(last_probed=_TS).last_probed == _TS

    def test_last_probed_stored_as_provided(self) -> None:
        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert _make_kernel(last_probed=ts).last_probed == ts


class TestEntropyTolerance:
    def test_zero_accepted(self) -> None:
        assert _make_kernel(entropy_tolerance=0.0).entropy_tolerance == 0.0

    def test_one_accepted(self) -> None:
        assert _make_kernel(entropy_tolerance=1.0).entropy_tolerance == 1.0

    def test_midpoint_accepted(self) -> None:
        assert _make_kernel(entropy_tolerance=0.5).entropy_tolerance == 0.5

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(entropy_tolerance=-0.01)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(entropy_tolerance=1.01)


class TestProcessPurity:
    def test_zero_accepted(self) -> None:
        assert _make_kernel(process_purity=0.0).process_purity == 0.0

    def test_one_accepted(self) -> None:
        assert _make_kernel(process_purity=1.0).process_purity == 1.0

    def test_midpoint_accepted(self) -> None:
        assert _make_kernel(process_purity=0.5).process_purity == 0.5

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(process_purity=-0.01)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(process_purity=1.01)


class TestAutonomyBoundary:
    def test_zero_accepted(self) -> None:
        assert _make_kernel(autonomy_boundary=0.0).autonomy_boundary == 0.0

    def test_one_accepted(self) -> None:
        assert _make_kernel(autonomy_boundary=1.0).autonomy_boundary == 1.0

    def test_midpoint_accepted(self) -> None:
        assert _make_kernel(autonomy_boundary=0.5).autonomy_boundary == 0.5

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(autonomy_boundary=-0.01)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(autonomy_boundary=1.01)


class TestEnergyLevel:
    def test_zero_accepted(self) -> None:
        assert _make_kernel(energy_level=0.0).energy_level == 0.0

    def test_one_accepted(self) -> None:
        assert _make_kernel(energy_level=1.0).energy_level == 1.0

    def test_midpoint_accepted(self) -> None:
        assert _make_kernel(energy_level=0.5).energy_level == 0.5

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(energy_level=-0.01)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(energy_level=1.01)


class TestProbeCount:
    def test_zero_accepted(self) -> None:
        assert _make_kernel(probe_count=0).probe_count == 0

    def test_positive_accepted(self) -> None:
        assert _make_kernel(probe_count=100).probe_count == 100

    def test_negative_rejected(self) -> None:
        """probe_count cannot be negative — the field has ge=0 (P0 fix)."""
        with pytest.raises(ValidationError):
            _make_kernel(probe_count=-1)

    def test_large_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_kernel(probe_count=-1000)
