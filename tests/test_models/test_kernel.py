"""Tests for the IndividualKernel model."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cognitive_bridge.models.kernel import IndividualKernel


class TestIndividualKernelDefaults:
    def test_default_construction_succeeds(self) -> None:
        k = IndividualKernel()
        assert k.entropy_tolerance == 0.5
        assert k.process_purity == 0.5
        assert k.autonomy_boundary == 0.5
        assert k.energy_level == 0.5

    def test_probe_count_defaults_to_zero(self) -> None:
        k = IndividualKernel()
        assert k.probe_count == 0

    def test_last_probed_defaults_to_none(self) -> None:
        k = IndividualKernel()
        assert k.last_probed is None

    def test_created_at_is_utc_aware(self) -> None:
        k = IndividualKernel()
        assert k.created_at.tzinfo == timezone.utc

    def test_updated_at_is_utc_aware(self) -> None:
        k = IndividualKernel()
        assert k.updated_at.tzinfo == timezone.utc

    def test_id_auto_generated_with_ker_prefix(self) -> None:
        k = IndividualKernel()
        assert k.id.startswith("ker_")
        # prefix "ker_" = 4 chars + 12 hex = 16 total
        assert len(k.id) == 16

    def test_id_uniqueness(self) -> None:
        ids = {IndividualKernel().id for _ in range(50)}
        assert len(ids) == 50


class TestEntropyToleranceBounds:
    def test_lower_bound_zero_accepted(self) -> None:
        k = IndividualKernel(entropy_tolerance=0.0)
        assert k.entropy_tolerance == 0.0

    def test_upper_bound_one_accepted(self) -> None:
        k = IndividualKernel(entropy_tolerance=1.0)
        assert k.entropy_tolerance == 1.0

    def test_below_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            IndividualKernel(entropy_tolerance=-0.01)
        errors = exc_info.value.errors()
        assert any("entropy_tolerance" in str(e) for e in errors)

    def test_above_upper_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            IndividualKernel(entropy_tolerance=1.01)
        errors = exc_info.value.errors()
        assert any("entropy_tolerance" in str(e) for e in errors)


class TestProcessPurityBounds:
    def test_lower_bound_zero_accepted(self) -> None:
        k = IndividualKernel(process_purity=0.0)
        assert k.process_purity == 0.0

    def test_upper_bound_one_accepted(self) -> None:
        k = IndividualKernel(process_purity=1.0)
        assert k.process_purity == 1.0

    def test_below_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            IndividualKernel(process_purity=-0.01)
        errors = exc_info.value.errors()
        assert any("process_purity" in str(e) for e in errors)

    def test_above_upper_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            IndividualKernel(process_purity=1.01)
        errors = exc_info.value.errors()
        assert any("process_purity" in str(e) for e in errors)


class TestAutonomyBoundaryBounds:
    def test_lower_bound_zero_accepted(self) -> None:
        k = IndividualKernel(autonomy_boundary=0.0)
        assert k.autonomy_boundary == 0.0

    def test_upper_bound_one_accepted(self) -> None:
        k = IndividualKernel(autonomy_boundary=1.0)
        assert k.autonomy_boundary == 1.0

    def test_below_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            IndividualKernel(autonomy_boundary=-0.01)
        errors = exc_info.value.errors()
        assert any("autonomy_boundary" in str(e) for e in errors)

    def test_above_upper_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            IndividualKernel(autonomy_boundary=1.01)
        errors = exc_info.value.errors()
        assert any("autonomy_boundary" in str(e) for e in errors)


class TestEnergyLevelBounds:
    def test_lower_bound_zero_accepted(self) -> None:
        k = IndividualKernel(energy_level=0.0)
        assert k.energy_level == 0.0

    def test_upper_bound_one_accepted(self) -> None:
        k = IndividualKernel(energy_level=1.0)
        assert k.energy_level == 1.0

    def test_below_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            IndividualKernel(energy_level=-0.01)
        errors = exc_info.value.errors()
        assert any("energy_level" in str(e) for e in errors)

    def test_above_upper_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            IndividualKernel(energy_level=1.01)
        errors = exc_info.value.errors()
        assert any("energy_level" in str(e) for e in errors)


class TestIndividualKernelMutation:
    def test_last_probed_can_be_set(self) -> None:
        ts = datetime.now(timezone.utc)
        k = IndividualKernel(last_probed=ts)
        assert k.last_probed == ts

    def test_probe_count_can_be_set(self) -> None:
        k = IndividualKernel(probe_count=5)
        assert k.probe_count == 5

    def test_all_dimensions_settable(self) -> None:
        k = IndividualKernel(
            entropy_tolerance=0.1,
            process_purity=0.9,
            autonomy_boundary=0.3,
            energy_level=0.7,
        )
        assert k.entropy_tolerance == 0.1
        assert k.process_purity == 0.9
        assert k.autonomy_boundary == 0.3
        assert k.energy_level == 0.7
