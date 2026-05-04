"""Tests for engine/sensitivity.py — kernel → CognitiveParameters auto-tuning.

Blueprint reference: Section 3.8 / Phase 3 (P3.T2 Sensitivity auto-tuning).
Constitution rules G2, G4.
"""

import pytest

from cognitive_bridge.engine.sensitivity import (
    apply_kernel_tuning, compute_suggested_parameters, format_tuning_report,
)
from cognitive_bridge.models.kernel import IndividualKernel
from cognitive_bridge.models.parameters import CognitiveParameters


def _kernel(
    entropy_tolerance: float = 0.5, process_purity: float = 0.5,
    autonomy_boundary: float = 0.5, energy_level: float = 0.5,
    probe_count: int = 1,
) -> IndividualKernel:
    return IndividualKernel(
        entropy_tolerance=entropy_tolerance, process_purity=process_purity,
        autonomy_boundary=autonomy_boundary, energy_level=energy_level,
        probe_count=probe_count,
    )


def _default_params() -> CognitiveParameters:
    return CognitiveParameters()


class TestComputeSuggestedParameters:
    def test_returns_dict(self):
        assert isinstance(compute_suggested_parameters(_kernel()), dict)

    def test_high_entropy_tolerance_lowers_conflict_sensitivity(self):
        result = compute_suggested_parameters(_kernel(entropy_tolerance=0.9))
        assert result["conflict_sensitivity"] == pytest.approx(0.1, abs=1e-4)

    def test_low_entropy_tolerance_raises_conflict_sensitivity(self):
        result = compute_suggested_parameters(_kernel(entropy_tolerance=0.1))
        assert result["conflict_sensitivity"] == pytest.approx(0.9, abs=1e-4)

    def test_mid_entropy_tolerance_mid_sensitivity(self):
        result = compute_suggested_parameters(_kernel(entropy_tolerance=0.5))
        assert result["conflict_sensitivity"] == pytest.approx(0.5, abs=1e-4)

    def test_entropy_zero_sensitivity_clamped_to_one(self):
        result = compute_suggested_parameters(_kernel(entropy_tolerance=0.0))
        assert result["conflict_sensitivity"] == pytest.approx(1.0, abs=1e-4)

    def test_entropy_one_sensitivity_clamped_to_zero(self):
        result = compute_suggested_parameters(_kernel(entropy_tolerance=1.0))
        assert result["conflict_sensitivity"] == pytest.approx(0.0, abs=1e-4)

    def test_high_process_purity_enables_auto_challenge(self):
        assert compute_suggested_parameters(_kernel(process_purity=0.8))["cascade_auto_challenge"] is True

    def test_low_process_purity_disables_auto_challenge(self):
        assert compute_suggested_parameters(_kernel(process_purity=0.3))["cascade_auto_challenge"] is False

    def test_process_purity_at_boundary_0_5_disables_auto_challenge(self):
        assert compute_suggested_parameters(_kernel(process_purity=0.5))["cascade_auto_challenge"] is False

    def test_process_purity_just_above_boundary_enables_auto_challenge(self):
        assert compute_suggested_parameters(_kernel(process_purity=0.51))["cascade_auto_challenge"] is True

    def test_high_autonomy_maps_to_inherits_arc(self):
        assert compute_suggested_parameters(_kernel(autonomy_boundary=0.9))["ai_default_arc"] == 20

    def test_medium_autonomy_maps_to_references_arc(self):
        assert compute_suggested_parameters(_kernel(autonomy_boundary=0.5))["ai_default_arc"] == 40

    def test_low_autonomy_maps_to_specializes_arc(self):
        assert compute_suggested_parameters(_kernel(autonomy_boundary=0.1))["ai_default_arc"] == 60

    def test_autonomy_at_high_boundary_is_references(self):
        assert compute_suggested_parameters(_kernel(autonomy_boundary=0.7))["ai_default_arc"] == 40

    def test_autonomy_just_above_high_boundary_is_inherits(self):
        assert compute_suggested_parameters(_kernel(autonomy_boundary=0.71))["ai_default_arc"] == 20

    def test_autonomy_at_low_boundary_is_references(self):
        assert compute_suggested_parameters(_kernel(autonomy_boundary=0.3))["ai_default_arc"] == 40

    def test_autonomy_just_below_low_boundary_is_specializes(self):
        assert compute_suggested_parameters(_kernel(autonomy_boundary=0.29))["ai_default_arc"] == 60

    def test_high_energy_expands_budget_and_lowers_threshold(self):
        result = compute_suggested_parameters(_kernel(energy_level=0.9))
        assert result["exploration_budget"] == 7
        assert result["red_team_threshold"] == 5

    def test_medium_energy_normal_budget_and_threshold(self):
        result = compute_suggested_parameters(_kernel(energy_level=0.5))
        assert result["exploration_budget"] == 3
        assert result["red_team_threshold"] == 8

    def test_low_energy_shrinks_budget_and_raises_threshold(self):
        result = compute_suggested_parameters(_kernel(energy_level=0.1))
        assert result["exploration_budget"] == 1
        assert result["red_team_threshold"] == 15

    def test_energy_at_high_boundary_0_7_is_medium(self):
        result = compute_suggested_parameters(_kernel(energy_level=0.7))
        assert result["exploration_budget"] == 3
        assert result["red_team_threshold"] == 8

    def test_energy_at_low_boundary_0_3_is_medium(self):
        result = compute_suggested_parameters(_kernel(energy_level=0.3))
        assert result["exploration_budget"] == 3
        assert result["red_team_threshold"] == 8


class TestApplyKernelTuning:
    def test_returns_tuple_of_params_and_changes(self):
        result = apply_kernel_tuning(_kernel(), _default_params())
        assert isinstance(result, tuple)
        assert len(result) == 2
        updated, changes = result
        assert isinstance(updated, CognitiveParameters)
        assert isinstance(changes, dict)

    def test_high_entropy_tolerance_lowers_sensitivity_in_returned_params(self):
        updated, changes = apply_kernel_tuning(_kernel(entropy_tolerance=0.9), _default_params())
        assert updated.conflict_sensitivity == pytest.approx(0.1, abs=1e-4)
        assert "conflict_sensitivity" in changes

    def test_no_changes_when_params_already_match_kernel(self):
        k = _kernel(entropy_tolerance=0.5, process_purity=0.8, autonomy_boundary=0.9, energy_level=0.5)
        params = CognitiveParameters(
            conflict_sensitivity=0.5, cascade_auto_challenge=True,
            ai_default_arc=20, exploration_budget=3, red_team_threshold=8,
        )
        _, changes = apply_kernel_tuning(k, params)
        assert changes == {}

    def test_idempotent_second_call_produces_same_params(self):
        k = _kernel(entropy_tolerance=0.9, process_purity=0.8, autonomy_boundary=0.9, energy_level=0.9)
        updated1, _ = apply_kernel_tuning(k, _default_params())
        updated2, changes2 = apply_kernel_tuning(k, updated1)
        assert updated2.model_dump() == updated1.model_dump()
        assert changes2 == {}

    def test_original_params_object_not_mutated(self):
        params = _default_params()
        original_sensitivity = params.conflict_sensitivity
        apply_kernel_tuning(_kernel(entropy_tolerance=0.9), params)
        assert params.conflict_sensitivity == original_sensitivity

    def test_changes_dict_maps_param_name_to_old_arrow_new_string(self):
        _, changes = apply_kernel_tuning(_kernel(entropy_tolerance=0.9), _default_params())
        for change_str in changes.values():
            assert "→" in change_str

    def test_high_process_purity_enables_cascade_auto_challenge(self):
        params = CognitiveParameters(cascade_auto_challenge=False)
        updated, changes = apply_kernel_tuning(_kernel(process_purity=0.9), params)
        assert updated.cascade_auto_challenge is True
        assert "cascade_auto_challenge" in changes

    def test_low_autonomy_sets_specializes_arc(self):
        from cognitive_bridge.models.arcs import CompositionArc
        updated, changes = apply_kernel_tuning(_kernel(autonomy_boundary=0.1), _default_params())
        assert updated.ai_default_arc == CompositionArc.SPECIALIZES
        assert "ai_default_arc" in changes


class TestFormatTuningReport:
    def test_returns_string(self):
        assert isinstance(format_tuning_report(_kernel(), {}), str)

    def test_no_changes_message_in_empty_changes(self):
        report = format_tuning_report(_kernel(), {})
        assert "no parameter changes" in report.lower() or "match" in report.lower()

    def test_report_contains_kernel_dimension_values(self):
        report = format_tuning_report(
            _kernel(entropy_tolerance=0.3, process_purity=0.7, autonomy_boundary=0.2, energy_level=0.9), {},
        )
        assert "0.3" in report
        assert "0.7" in report
        assert "0.2" in report
        assert "0.9" in report

    def test_report_contains_changed_param_names(self):
        changes = {"conflict_sensitivity": "0.5 → 0.1", "cascade_auto_challenge": "True → False"}
        report = format_tuning_report(_kernel(), changes)
        assert "conflict_sensitivity" in report
        assert "cascade_auto_challenge" in report

    def test_report_contains_probe_count(self):
        assert "5" in format_tuning_report(_kernel(probe_count=5), {})

    def test_report_is_multiline(self):
        assert "\n" in format_tuning_report(_kernel(), {})
