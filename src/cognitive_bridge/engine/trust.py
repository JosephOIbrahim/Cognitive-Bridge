"""Trust calibration — per-subtree trust scores from conflict resolution history.

Trust represents the predictive confidence in assertions at a given path.
High trust: assertions at this path have been validated through resolved conflicts.
Low trust: assertions at this path have been contested, overturned, or are unstable.

Trust is computed, not stored — it is derived entirely from the conflict history
present in the composition stage. No mutable state is introduced by this module.

Algorithm summary (per path):
  Base trust:                           0.5 (neutral, no history)
  Each stable resolution (+0.05):       RESOLVED_SYNTHESIZED or DISMISSED
  Each override/promotion (+0.03):      RESOLVED_OVERRIDE or RESOLVED_PROMOTED
  Each active conflict (-0.08):         ACTIVE — contested, reduces confidence
  Each deferred conflict (-0.03):       DEFERRED — unresolved uncertainty
  Each experiment resolution (+0.07):   RESOLVED_EXPERIMENT — empirical grounding
    Note: experiments also count as stable resolutions (+0.05), so the total
    boost per experiment is +0.12 (0.07 experiment + 0.05 stable).
  Final score clamped to [0.0, 1.0].
"""

from dataclasses import dataclass

from cognitive_bridge.models.arcs import ConflictStatus
from cognitive_bridge.models.stage import CompositionStage


# ─────────────────────────────────────────────────────────────────────────────
# Data class
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TrustScore:
    """Trust score for a single topic path, derived from conflict history.

    Attributes:
        path: The topic path this score applies to.
        score: Trust coefficient in [0.0, 1.0].  0.5 is neutral.
        total_conflicts: Total conflicts ever detected at this path.
        resolved_conflicts: Conflicts that reached any resolved status.
        overrides: Resolutions via OVERRIDE or PROMOTED (force, not consensus).
        stable_resolutions: Resolutions via SYNTHESIZED, DISMISSED, or EXPERIMENT.
        challenges: Currently ACTIVE conflicts — ongoing instability.
        experiments: Resolutions via empirical test (RESOLVED_EXPERIMENT).
    """

    path: str
    score: float  # 0.0 to 1.0
    total_conflicts: int
    resolved_conflicts: int
    overrides: int           # RESOLVED_OVERRIDE or RESOLVED_PROMOTED
    stable_resolutions: int  # RESOLVED_SYNTHESIZED, DISMISSED, RESOLVED_EXPERIMENT
    challenges: int          # Currently ACTIVE
    experiments: int         # RESOLVED_EXPERIMENT (subset of stable_resolutions)


# ─────────────────────────────────────────────────────────────────────────────
# Core computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_trust_scores(stage: CompositionStage) -> dict[str, TrustScore]:
    """Compute trust scores for all topic paths that have conflict history.

    Iterates every conflict in the stage and groups them by topic_path.
    For each path, applies the scoring algorithm documented at module level.

    Args:
        stage: The composition stage to analyse.  Read-only — this function
            does not mutate the stage.

    Returns:
        Dict mapping topic_path strings to TrustScore objects.  Only paths
        that appear in at least one conflict are included.  Paths with no
        conflict history have implicit neutral trust of 0.5 (see
        ``get_trust_for_path``).
    """
    # Group conflicts by topic_path
    by_path: dict[str, list] = {}
    for conflict in stage.conflicts.values():
        by_path.setdefault(conflict.topic_path, []).append(conflict)

    scores: dict[str, TrustScore] = {}

    for path, conflicts in by_path.items():
        total = len(conflicts)
        resolved = 0
        overrides = 0
        stable = 0
        challenges = 0
        experiments = 0
        deferred = 0

        for c in conflicts:
            if c.status == ConflictStatus.ACTIVE:
                challenges += 1
            elif c.status == ConflictStatus.DEFERRED:
                deferred += 1
            elif c.status in (
                ConflictStatus.RESOLVED_OVERRIDE,
                ConflictStatus.RESOLVED_PROMOTED,
            ):
                resolved += 1
                overrides += 1
            elif c.status in (
                ConflictStatus.RESOLVED_SYNTHESIZED,
                ConflictStatus.DISMISSED,
            ):
                resolved += 1
                stable += 1
            elif c.status == ConflictStatus.RESOLVED_EXPERIMENT:
                resolved += 1
                experiments += 1
                stable += 1  # Experiments are also stable resolutions

        # Compute trust score from base + contributions
        trust = 0.5
        trust += stable * 0.05
        trust += overrides * 0.03
        trust -= challenges * 0.08
        trust -= deferred * 0.03
        trust += experiments * 0.07

        trust = round(max(0.0, min(1.0, trust)), 4)

        scores[path] = TrustScore(
            path=path,
            score=trust,
            total_conflicts=total,
            resolved_conflicts=resolved,
            overrides=overrides,
            stable_resolutions=stable,
            challenges=challenges,
            experiments=experiments,
        )

    return scores


# ─────────────────────────────────────────────────────────────────────────────
# Single-path helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_trust_for_path(stage: CompositionStage, topic_path: str) -> TrustScore:
    """Get the trust score for a specific topic path.

    If the path has no conflict history in the stage, returns a neutral
    TrustScore with score=0.5 and all counters at zero.  This represents
    epistemic silence — we have no evidence either for or against.

    Args:
        stage: The composition stage to query.
        topic_path: The exact topic path to look up.

    Returns:
        TrustScore for the path.
    """
    scores = compute_trust_scores(stage)
    if topic_path in scores:
        return scores[topic_path]
    return TrustScore(
        path=topic_path,
        score=0.5,
        total_conflicts=0,
        resolved_conflicts=0,
        overrides=0,
        stable_resolutions=0,
        challenges=0,
        experiments=0,
    )


def get_subtree_trust(stage: CompositionStage, prefix: str) -> float:
    """Get the aggregate trust for a topic-path subtree.

    Collects all TrustScores for paths whose string starts with ``prefix``
    and returns their arithmetic mean.  Useful for coarse-grained trust
    assessments at a domain level (e.g. "/architecture").

    Args:
        stage: The composition stage to query.
        prefix: The topic path prefix to match, e.g. "/db".

    Returns:
        Average trust score (float) rounded to 4 decimal places.
        Returns 0.5 when no paths under the prefix have conflict history.
    """
    scores = compute_trust_scores(stage)
    matching = [s for p, s in scores.items() if p.startswith(prefix)]
    if not matching:
        return 0.5
    return round(sum(s.score for s in matching) / len(matching), 4)


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

def format_trust_report(stage: CompositionStage) -> str:
    """Format a human-readable trust report for the stage.

    Paths are sorted alphabetically for deterministic output.
    Each path displays its score, a HIGH/MODERATE/LOW label, and a
    breakdown of conflict counts.  Experiment counts are highlighted as
    strong trust signals when non-zero.

    Args:
        stage: The composition stage to report on.

    Returns:
        A formatted multi-line string suitable for MCP tool responses.
        Returns a single-line message when there is no conflict history.
    """
    scores = compute_trust_scores(stage)
    if not scores:
        return "No conflict history — trust is neutral (0.5) everywhere."

    lines = [f"Trust Report ({len(scores)} paths with conflict history):\n"]

    for path in sorted(scores.keys()):
        ts = scores[path]
        if ts.score >= 0.7:
            level = "HIGH"
        elif ts.score >= 0.4:
            level = "MODERATE"
        else:
            level = "LOW"

        lines.append(f"  {path}: {ts.score:.2f} ({level})")
        lines.append(
            f"    Conflicts: {ts.total_conflicts} total, "
            f"{ts.resolved_conflicts} resolved, "
            f"{ts.challenges} active"
        )
        if ts.experiments:
            lines.append(f"    Experiments: {ts.experiments} (strong trust signal)")
        lines.append("")

    return "\n".join(lines)
