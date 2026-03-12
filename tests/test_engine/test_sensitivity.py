"""Tests for engine/sensitivity.py — COS kernel to CognitiveParameters auto-tuning.

Covers:
- compute_suggested_parameters(): default kernel, entropy/process/autonomy/energy
  extremes and midpoints, all boundary crossings.
- apply_kernel_tuning(): changes dict populated correctly, no-op when already tuned,
  returns valid CognitiveParameters, all Pydantic constraints satisfied.
- format_tuning_report(): report structure, changes shown, no-changes message,
  kernel dimensions visible in output.
"""

import pytest

from cognitive_bridge.engine.sensitivity import (
    apply_kernel_tuning,
    compute_suggested_parameters,
    format_tuning_report,
)
from cognitive_bridge.models.kernel import IndividualKernel
from cognitive_bridge.models.parameters import CognitiveParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kernel(**kwargs) -> IndividualKernel:
    """Construct an IndividualKernel with the given dimension overrides."""
    return IndividualKernel(**kwargs)


def _default_params() -> CognitiveParameters:
    """Return default CognitiveParameters."""
    return CognitiveParameters()


# ---------------------------------------------------------------------------
# TestComputeSuggestedParameters
# ---------------------------------------------------------------------------

class TestComputeSuggestedParameters:

    def test_default_kernel_produces_mid_sensitivity(self):
        """Default kernel (all 0.5) → conflict_sensitivity = 0.5."""
        kernel = _kernel()
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["conflict_sensitivity"] == pytest.approx(0.5, abs=1e-4)

    def test_default_kernel_cascade_auto_challenge_off(self):
        """Default kernel process_purity=0.5 (not > 0.5) → cascade_auto_challenge = False."""
        kernel = _kernel()
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["cascade_auto_challenge"] is False

    def test_default_kernel_ai_arc_references(self):
        """Default autonomy_boundary=0.5 (in (0.3, 0.7]) → ai_default_arc = 40 (REFERENCES)."""
        kernel = _kernel()
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["ai_default_arc"] == 40

    def test_default_kernel_energy_medium_budget_and_threshold(self):
        """Default energy_level=0.5 → exploration_budget=3, red_team_threshold=8."""
        kernel = _kernel()
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["exploration_budget"] == 3
        assert suggestions["red_team_threshold"] == 8

    def test_high_entropy_tolerance_lowers_conflict_sensitivity(self):
        """entropy_tolerance=0.9 → conflict_sensitivity ≈ 0.1."""
        kernel = _kernel(entropy_tolerance=0.9)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["conflict_sensitivity"] == pytest.approx(0.1, abs=1e-4)

    def test_low_entropy_tolerance_raises_conflict_sensitivity(self):
        """entropy_tolerance=0.1 → conflict_sensitivity ≈ 0.9."""
        kernel = _kernel(entropy_tolerance=0.1)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["conflict_sensitivity"] == pytest.approx(0.9, abs=1e-4)

    def test_entropy_tolerance_zero_clamps_sensitivity_to_one(self):
        """entropy_tolerance=0.0 → conflict_sensitivity clamped to 1.0."""
        kernel = _kernel(entropy_tolerance=0.0)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["conflict_sensitivity"] == pytest.approx(1.0, abs=1e-4)

    def test_entropy_tolerance_one_clamps_sensitivity_to_zero(self):
        """entropy_tolerance=1.0 → conflict_sensitivity clamped to 0.0."""
        kernel = _kernel(entropy_tolerance=1.0)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["conflict_sensitivity"] == pytest.approx(0.0, abs=1e-4)

    def test_high_process_purity_enables_cascade_auto_challenge(self):
        """process_purity=0.8 (> 0.5) → cascade_auto_challenge = True."""
        kernel = _kernel(process_purity=0.8)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["cascade_auto_challenge"] is True

    def test_low_process_purity_disables_cascade_auto_challenge(self):
        """process_purity=0.2 (not > 0.5) → cascade_auto_challenge = False."""
        kernel = _kernel(process_purity=0.2)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["cascade_auto_challenge"] is False

    def test_process_purity_exactly_half_disables_auto_challenge(self):
        """process_purity=0.5 is not > 0.5 → cascade_auto_challenge = False."""
        kernel = _kernel(process_purity=0.5)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["cascade_auto_challenge"] is False

    def test_high_autonomy_maps_to_inherits_arc(self):
        """autonomy_boundary=0.9 (> 0.7) → ai_default_arc = 20 (INHERITS)."""
        kernel = _kernel(autonomy_boundary=0.9)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["ai_default_arc"] == 20

    def test_low_autonomy_maps_to_specializes_arc(self):
        """autonomy_boundary=0.1 (< 0.3) → ai_default_arc = 60 (SPECIALIZES)."""
        kernel = _kernel(autonomy_boundary=0.1)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["ai_default_arc"] == 60

    def test_medium_autonomy_maps_to_references_arc(self):
        """autonomy_boundary=0.5 (in (0.3, 0.7]) → ai_default_arc = 40 (REFERENCES)."""
        kernel = _kernel(autonomy_boundary=0.5)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["ai_default_arc"] == 40

    def test_autonomy_at_boundary_0_7_maps_to_references(self):
        """autonomy_boundary=0.7 (not > 0.7) → REFERENCES (40), not INHERITS."""
        kernel = _kernel(autonomy_boundary=0.7)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["ai_default_arc"] == 40

    def test_autonomy_at_boundary_0_3_maps_to_specializes(self):
        """autonomy_boundary=0.3 (not > 0.3) → SPECIALIZES (60), not REFERENCES."""
        kernel = _kernel(autonomy_boundary=0.3)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["ai_default_arc"] == 60

    def test_high_energy_raises_budget_and_lowers_threshold(self):
        """energy_level=0.9 → exploration_budget=5, red_team_threshold=5."""
        kernel = _kernel(energy_level=0.9)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["exploration_budget"] == 5
        assert suggestions["red_team_threshold"] == 5

    def test_low_energy_lowers_budget_and_raises_threshold(self):
        """energy_level=0.1 → exploration_budget=1, red_team_threshold=15."""
        kernel = _kernel(energy_level=0.1)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["exploration_budget"] == 1
        assert suggestions["red_team_threshold"] == 15

    def test_medium_energy_uses_default_budget_and_threshold(self):
        """energy_level=0.5 → exploration_budget=3, red_team_threshold=8."""
        kernel = _kernel(energy_level=0.5)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["exploration_budget"] == 3
        assert suggestions["red_team_threshold"] == 8

    def test_energy_at_boundary_0_7_maps_to_medium(self):
        """energy_level=0.7 (not > 0.7) → medium bucket: budget=3, threshold=8."""
        kernel = _kernel(energy_level=0.7)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["exploration_budget"] == 3
        assert suggestions["red_team_threshold"] == 8

    def test_energy_at_boundary_0_3_maps_to_low(self):
        """energy_level=0.3 (not > 0.3) → low bucket: budget=1, threshold=15."""
        kernel = _kernel(energy_level=0.3)
        suggestions = compute_suggested_parameters(kernel)

        assert suggestions["exploration_budget"] == 1
        assert suggestions["red_team_threshold"] == 15

    def test_returns_all_expected_keys(self):
        """compute_suggested_parameters always returns all 5 parameter keys."""
        kernel = _kernel()
        suggestions = compute_suggested_parameters(kernel)

        expected_keys = {
            "conflict_sensitivity",
            "cascade_auto_challenge",
            "ai_default_arc",
            "exploration_budget",
            "red_team_threshold",
        }
        assert set(suggestions.keys()) == expected_keys


# ---------------------------------------------------------------------------
# TestApplyKernelTuning
# ---------------------------------------------------------------------------

class TestApplyKernelTuning:

    def test_default_kernel_default_params_sensitivity_unchanged(self):
        """Default kernel → conflict_sensitivity = 0.5 = same as default params.
        Only fields that differ from defaults should appear in changes."""
        kernel = _kernel()
        params = _default_params()
        updated, changes = apply_kernel_tuning(kernel, params)

        # conflict_sensitivity stays at 0.5 — no change expected for that field
        assert "conflict_sensitivity" not in changes

    def test_depleted_kernel_changes_exploration_budget(self):
        """Low energy (0.1) → exploration_budget changes from 3 to 1."""
        kernel = _kernel(energy_level=0.1)
        params = _default_params()
        updated, changes = apply_kernel_tuning(kernel, params)

        assert "exploration_budget" in changes
        assert updated.exploration_budget == 1

    def test_depleted_kernel_changes_red_team_threshold(self):
        """Low energy (0.1) → red_team_threshold changes from 8 to 15."""
        kernel = _kernel(energy_level=0.1)
        params = _default_params()
        updated, changes = apply_kernel_tuning(kernel, params)

        assert "red_team_threshold" in changes
        assert updated.red_team_threshold == 15

    def test_changes_dict_uses_arrow_notation(self):
        """Changes dict values use 'old → new' format."""
        kernel = _kernel(energy_level=0.1)
        params = _default_params()
        _, changes = apply_kernel_tuning(kernel, params)

        for change_str in changes.values():
            assert "→" in change_str

    def test_non_default_kernel_populates_changes(self):
        """Kernel with non-default dimensions produces at least one change vs defaults."""
        kernel = _kernel(
            entropy_tolerance=0.1,  # → sensitivity 0.9 (default 0.5, changes)
            process_purity=0.9,     # → cascade_auto_challenge True (default True, no change)
            autonomy_boundary=0.1,  # → SPECIALIZES (default INHERITS, changes)
            energy_level=0.1,       # → budget 1, threshold 15 (both change)
        )
        params = _default_params()
        _, changes = apply_kernel_tuning(kernel, params)

        assert len(changes) >= 1

    def test_already_tuned_params_produce_no_changes(self):
        """When params already match the kernel suggestions, changes dict is empty."""
        kernel = _kernel(
            entropy_tolerance=0.5,   # → sensitivity 0.5 = default
            process_purity=0.5,      # → cascade_auto_challenge False
            autonomy_boundary=0.5,   # → ai_default_arc 40 (REFERENCES)
            energy_level=0.5,        # → budget 3, threshold 8
        )
        # Build parameters that already match what the kernel would suggest.
        from cognitive_bridge.models.arcs import CompositionArc
        params = CognitiveParameters(
            conflict_sensitivity=0.5,
            cascade_auto_challenge=False,
            ai_default_arc=CompositionArc.REFERENCES,
            exploration_budget=3,
            red_team_threshold=8,
        )
        _, changes = apply_kernel_tuning(kernel, params)

        assert changes == {}

    def test_returns_valid_cognitive_parameters(self):
        """apply_kernel_tuning always returns a valid CognitiveParameters instance."""
        for energy in [0.1, 0.5, 0.9]:
            for autonomy in [0.1, 0.5, 0.9]:
                kernel = _kernel(energy_level=energy, autonomy_boundary=autonomy)
                params = _default_params()
                updated, _ = apply_kernel_tuning(kernel, params)
                assert isinstance(updated, CognitiveParameters)

    def test_updated_params_respect_exploration_budget_bounds(self):
        """All kernel combinations produce exploration_budget within [1, 10]."""
        for energy in [0.0, 0.3, 0.5, 0.7, 1.0]:
            kernel = _kernel(energy_level=energy)
            params = _default_params()
            updated, _ = apply_kernel_tuning(kernel, params)
            assert 1 <= updated.exploration_budget <= 10

    def test_updated_params_respect_red_team_threshold_bounds(self):
        """All kernel combinations produce red_team_threshold within [3, 20]."""
        for energy in [0.0, 0.3, 0.5, 0.7, 1.0]:
            kernel = _kernel(energy_level=energy)
            params = _default_params()
            updated, _ = apply_kernel_tuning(kernel, params)
            assert 3 <= updated.red_team_threshold <= 20

    def test_updated_params_respect_conflict_sensitivity_bounds(self):
        """All entropy_tolerance values produce conflict_sensitivity within [0.0, 1.0]."""
        for et in [0.0, 0.25, 0.5, 0.75, 1.0]:
            kernel = _kernel(entropy_tolerance=et)
            params = _default_params()
            updated, _ = apply_kernel_tuning(kernel, params)
            assert 0.0 <= updated.conflict_sensitivity <= 1.0

    def test_high_energy_kernel_increases_exploration_budget(self):
        """High energy kernel sets exploration_budget=5 on default params."""
        kernel = _kernel(energy_level=0.9)
        params = _default_params()
        updated, changes = apply_kernel_tuning(kernel, params)

        assert updated.exploration_budget == 5
        assert "exploration_budget" in changes

    def test_original_params_not_mutated(self):
        """apply_kernel_tuning does not modify the input CognitiveParameters."""
        kernel = _kernel(energy_level=0.1)
        params = _default_params()
        original_budget = params.exploration_budget
        apply_kernel_tuning(kernel, params)
        assert params.exploration_budget == original_budget


# ---------------------------------------------------------------------------
# TestFormatTuningReport
# ---------------------------------------------------------------------------

class TestFormatTuningReport:

    def test_report_with_changes_lists_parameters(self):
        """When changes exist, report lists each modified parameter."""
        kernel = _kernel(energy_level=0.1)
        params = _default_params()
        _, changes = apply_kernel_tuning(kernel, params)

        report = format_tuning_report(kernel, changes)

        for param_name in changes:
            assert param_name in report

    def test_report_with_no_changes_shows_no_changes_message(self):
        """Empty changes dict → report says no changes needed."""
        kernel = _kernel()
        report = format_tuning_report(kernel, {})

        assert "no" in report.lower() or "No" in report
        assert "change" in report.lower()

    def test_report_shows_kernel_dimensions(self):
        """Report includes all four kernel dimension values."""
        kernel = _kernel(
            entropy_tolerance=0.3,
            process_purity=0.7,
            autonomy_boundary=0.4,
            energy_level=0.8,
        )
        report = format_tuning_report(kernel, {})

        assert "entropy_tolerance" in report
        assert "process_purity" in report
        assert "autonomy_boundary" in report
        assert "energy_level" in report

    def test_report_shows_probe_count(self):
        """Report includes probe_count from the kernel metadata."""
        kernel = _kernel(probe_count=5)
        report = format_tuning_report(kernel, {})

        assert "probe_count" in report
        assert "5" in report

    def test_report_shows_kernel_dimension_values(self):
        """The numeric values of kernel dimensions appear in the report."""
        kernel = _kernel(
            entropy_tolerance=0.25,
            process_purity=0.75,
        )
        report = format_tuning_report(kernel, {})

        assert "0.25" in report
        assert "0.75" in report

    def test_report_is_a_string(self):
        """format_tuning_report always returns a str."""
        kernel = _kernel()
        result = format_tuning_report(kernel, {})
        assert isinstance(result, str)

    def test_report_shows_change_count(self):
        """Report header includes number of changed parameters."""
        kernel = _kernel(energy_level=0.1, entropy_tolerance=0.1)
        params = _default_params()
        _, changes = apply_kernel_tuning(kernel, params)

        report = format_tuning_report(kernel, changes)

        assert str(len(changes)) in report

    def test_report_header_present(self):
        """Report always starts with the 'Sensitivity Auto-Tuning Report' header."""
        kernel = _kernel()
        report = format_tuning_report(kernel, {})

        assert "Sensitivity Auto-Tuning Report" in report

    def test_report_contains_arrow_notation_for_changes(self):
        """Change entries in the report use the arrow (→) notation."""
        kernel = _kernel(energy_level=0.1)
        params = _default_params()
        _, changes = apply_kernel_tuning(kernel, params)

        report = format_tuning_report(kernel, changes)

        assert "→" in report
