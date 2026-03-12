"""Cognitive Bridge engine — conflict detection, resolution, cascading, provenance, trust."""

from cognitive_bridge.engine.cascade import (
    check_falsification,
    detect_cascading_conflicts,
)
from cognitive_bridge.engine.conflict_detector import (
    detect_semantic_conflicts,
    detect_structural_conflict,
)
from cognitive_bridge.engine.provenance import (
    count_events_by_type,
    format_audit_trail,
    get_cascade_history,
    get_conflict_resolution_history,
    get_events_by_actor,
    get_events_by_type,
    get_events_for_target,
    get_events_in_range,
)
from cognitive_bridge.engine.red_team import (
    find_missing_dependencies,
    find_unchallenged_locals,
    find_unfalsifiable_locals,
    generate_red_team_report,
    record_red_team_trigger,
    should_trigger_red_team,
)
from cognitive_bridge.engine.resolver import (
    ResolutionResult,
    add_assertion,
    falsify_assertion,
    get_current_winner,
    promote_assertion,
    resolve_conflict,
    retract_assertion,
)
from cognitive_bridge.engine.sensitivity import (
    apply_kernel_tuning,
    compute_suggested_parameters,
    format_tuning_report,
)
from cognitive_bridge.engine.trust import (
    TrustScore,
    compute_trust_scores,
    format_trust_report,
    get_subtree_trust,
    get_trust_for_path,
)

__all__ = [
    # Conflict detector
    "detect_structural_conflict",
    "detect_semantic_conflicts",
    # Cascade
    "check_falsification",
    "detect_cascading_conflicts",
    # Provenance
    "count_events_by_type",
    "format_audit_trail",
    "get_cascade_history",
    "get_conflict_resolution_history",
    "get_events_by_actor",
    "get_events_by_type",
    "get_events_for_target",
    "get_events_in_range",
    # Resolver
    "ResolutionResult",
    "add_assertion",
    "falsify_assertion",
    "get_current_winner",
    "promote_assertion",
    "resolve_conflict",
    "retract_assertion",
    # Trust calibration
    "TrustScore",
    "compute_trust_scores",
    "format_trust_report",
    "get_subtree_trust",
    "get_trust_for_path",
    # Sensitivity auto-tuning
    "apply_kernel_tuning",
    "compute_suggested_parameters",
    "format_tuning_report",
    # RED_TEAMING auto-trigger
    "find_missing_dependencies",
    "find_unchallenged_locals",
    "find_unfalsifiable_locals",
    "generate_red_team_report",
    "record_red_team_trigger",
    "should_trigger_red_team",
]
