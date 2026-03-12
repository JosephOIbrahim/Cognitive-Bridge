"""Sensitivity auto-tuning — maps COS kernel dimensions to CognitiveParameters.

The kernel captures HOW the user thinks. This module translates that into
concrete parameter adjustments for the argumentation protocol.

This is NOT automatic — the tool layer calls apply_kernel_tuning() when
appropriate (e.g., after a probe, at session start). The user always has
final say via cb_tune_parameters.

Mapping overview:
- entropy_tolerance → conflict_sensitivity (inverse: high tolerance = lower sensitivity)
- process_purity    → cascade_auto_challenge (high process = strict cascading)
- autonomy_boundary → ai_default_arc (high autonomy = AI asserts at stronger arcs)
- energy_level      → exploration_budget + red_team_threshold
"""

from cognitive_bridge.models.kernel import IndividualKernel
from cognitive_bridge.models.parameters import CognitiveParameters


def compute_suggested_parameters(
    kernel: IndividualKernel,
) -> dict[str, float | int | bool]:
    """Compute suggested parameter adjustments from kernel dimensions.

    Mapping logic:
    - entropy_tolerance → conflict_sensitivity (inverse: high entropy tolerance
      = lower sensitivity because user accepts ambiguity)
    - process_purity → cascade_auto_challenge (high process purity > 0.5
      = auto-challenge on because user values strict methodology)
    - autonomy_boundary → ai_default_arc (high autonomy > 0.7 = INHERITS (20),
      medium 0.3–0.7 = REFERENCES (40), low < 0.3 = SPECIALIZES (60))
    - energy_level → exploration_budget + red_team_threshold (high energy > 0.7
      = budget 5 / threshold 5; medium 0.3–0.7 = budget 3 / threshold 8;
      low < 0.3 = budget 1 / threshold 15)

    Returns a dict of parameter names to suggested values.
    These are SUGGESTIONS — the caller decides whether to apply them.

    Args:
        kernel: The current COS kernel with four dimension values (0.0–1.0).

    Returns:
        Dict mapping CognitiveParameters field names to suggested values.
    """
    suggestions: dict[str, float | int | bool] = {}

    # Entropy tolerance → conflict_sensitivity (inverse relationship).
    # High entropy tolerance (0.8+) = user is OK with ambiguity = lower sensitivity.
    # Low entropy tolerance (0.2-) = user wants certainty = higher sensitivity.
    sensitivity = round(1.0 - kernel.entropy_tolerance, 2)
    sensitivity = max(0.0, min(1.0, sensitivity))
    suggestions["conflict_sensitivity"] = sensitivity

    # Process purity → cascade_auto_challenge.
    # High process (> 0.5) = strict methodology = auto-challenge on.
    # Low process (<= 0.5) = pragmatic = auto-challenge off.
    suggestions["cascade_auto_challenge"] = kernel.process_purity > 0.5

    # Autonomy boundary → ai_default_arc.
    # High autonomy (> 0.7) = AI can assert strongly = INHERITS (20).
    # Medium (0.3–0.7) = moderate = REFERENCES (40).
    # Low (< 0.3) = check everything = SPECIALIZES (60).
    if kernel.autonomy_boundary > 0.7:
        suggestions["ai_default_arc"] = 20   # CompositionArc.INHERITS
    elif kernel.autonomy_boundary > 0.3:
        suggestions["ai_default_arc"] = 40   # CompositionArc.REFERENCES
    else:
        suggestions["ai_default_arc"] = 60   # CompositionArc.SPECIALIZES

    # Energy level → exploration_budget and red_team_threshold.
    # High energy (> 0.7) = can handle more = larger budget, lower threshold.
    # Medium (0.3–0.7) = normal capacity = default budget and threshold.
    # Low (< 0.3) = depleted = smaller budget, higher threshold (less pressure).
    if kernel.energy_level > 0.7:
        suggestions["exploration_budget"] = 5
        suggestions["red_team_threshold"] = 5
    elif kernel.energy_level > 0.3:
        suggestions["exploration_budget"] = 3
        suggestions["red_team_threshold"] = 8
    else:
        suggestions["exploration_budget"] = 1
        suggestions["red_team_threshold"] = 15

    return suggestions


def apply_kernel_tuning(
    kernel: IndividualKernel,
    parameters: CognitiveParameters,
) -> tuple[CognitiveParameters, dict[str, str]]:
    """Apply kernel-based tuning to parameters.

    Computes suggested parameters from the kernel and applies them,
    returning the updated parameters and a change log.

    Args:
        kernel: The current COS kernel.
        parameters: The current parameters to tune.

    Returns:
        Tuple of (updated CognitiveParameters, dict of changes made).
        Changes dict maps parameter names to "old → new" strings.
        An empty changes dict means the parameters already matched the kernel.
    """
    suggestions = compute_suggested_parameters(kernel)
    changes: dict[str, str] = {}

    current = parameters.model_dump()

    for key, new_value in suggestions.items():
        old_value = current.get(key)
        if old_value != new_value:
            changes[key] = f"{old_value} \u2192 {new_value}"
            current[key] = new_value

    updated = CognitiveParameters(**current)
    return updated, changes


def format_tuning_report(
    kernel: IndividualKernel,
    changes: dict[str, str],
) -> str:
    """Format a human-readable tuning report.

    Args:
        kernel: The kernel that drove the tuning.
        changes: The changes dict from apply_kernel_tuning.

    Returns:
        Formatted multi-line report string.
    """
    lines = [
        "Sensitivity Auto-Tuning Report",
        f"Based on kernel (probe_count={kernel.probe_count}):",
        f"  entropy_tolerance:  {kernel.entropy_tolerance}",
        f"  process_purity:     {kernel.process_purity}",
        f"  autonomy_boundary:  {kernel.autonomy_boundary}",
        f"  energy_level:       {kernel.energy_level}",
        "",
    ]

    if not changes:
        lines.append("No parameter changes needed — current settings match kernel.")
    else:
        lines.append(f"Parameters adjusted ({len(changes)}):")
        for param, change in changes.items():
            lines.append(f"  {param}: {change}")

    return "\n".join(lines)
