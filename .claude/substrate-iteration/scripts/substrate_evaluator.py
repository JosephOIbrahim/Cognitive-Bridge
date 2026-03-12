"""
substrate_evaluator.py — Evaluate substrate effectiveness against session data.

Takes:
- Parsed session captures (from session_parser.py)
- Current substrate (from USD source)

Produces:
- Evaluation report with scored improvement opportunities
- Each opportunity has: type, severity, evidence, suggested action

This is the ANALYSIS layer. It doesn't make changes — it identifies WHERE
changes might be needed. The proposer (substrate_proposer.py) turns these
into concrete edit proposals.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from session_parser import SessionAnalysis, SessionCapture
from usd_ops import UsdStage, read_stage


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class EvalFinding:
    """A single evaluation finding."""
    category: str       # routing, constitutional, momentum, expert, stuck, energy, missing_rule
    severity: str       # low, medium, high, critical
    evidence: str       # What session data supports this finding
    substrate_path: str # Which substrate section is affected (USD prim path)
    description: str    # Human-readable description
    suggested_action: str  # What kind of change might help
    proposal_type: str  # TUNE, ADD, MODIFY, RESTRUCTURE, DEPRECATE
    
    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "evidence": self.evidence,
            "substrate_path": self.substrate_path,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "proposal_type": self.proposal_type,
        }


@dataclass
class EvalReport:
    """Complete evaluation report."""
    timestamp: str = ""
    sessions_analyzed: int = 0
    date_range: tuple = ("", "")
    findings: list = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "sessions_analyzed": self.sessions_analyzed,
            "date_range": list(self.date_range),
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
        }
    
    @property
    def critical_findings(self) -> list:
        return [f for f in self.findings if f.severity == "critical"]
    
    @property
    def high_findings(self) -> list:
        return [f for f in self.findings if f.severity == "high"]


# ── Evaluation Rules ─────────────────────────────────────────────────────────

def evaluate(analysis: SessionAnalysis, substrate: UsdStage) -> EvalReport:
    """
    Run all evaluation rules against session analysis and current substrate.
    Returns an EvalReport with findings.
    """
    report = EvalReport(
        sessions_analyzed=analysis.session_count,
        date_range=analysis.date_range,
    )
    
    # Run each evaluator
    report.findings.extend(_eval_expert_routing(analysis, substrate))
    report.findings.extend(_eval_crash_patterns(analysis, substrate))
    report.findings.extend(_eval_stuck_patterns(analysis, substrate))
    report.findings.extend(_eval_momentum_patterns(analysis, substrate))
    report.findings.extend(_eval_novel_signals(analysis, substrate))
    report.findings.extend(_eval_constitutional(analysis, substrate))
    report.findings.extend(_eval_energy_alignment(analysis, substrate))
    
    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    report.findings.sort(key=lambda f: severity_order.get(f.severity, 4))
    
    # Generate summary
    counts = {}
    for f in report.findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    parts = [f"{v} {k}" for k, v in sorted(counts.items(), key=lambda x: severity_order.get(x[0], 4))]
    report.summary = f"Analyzed {analysis.session_count} sessions. Found {len(report.findings)} issues: {', '.join(parts)}."
    
    return report


# ── Individual Evaluators ────────────────────────────────────────────────────

def _eval_expert_routing(analysis: SessionAnalysis, substrate: UsdStage) -> list:
    """Check expert routing effectiveness."""
    findings = []
    
    # Expert overuse detection
    total = sum(analysis.expert_frequency.values()) or 1
    for expert, count in analysis.expert_frequency.items():
        ratio = count / total
        if ratio > 0.5 and analysis.session_count >= 3:
            findings.append(EvalFinding(
                category="routing",
                severity="medium",
                evidence=f"{expert} activated {count}/{total} times ({ratio:.0%}) across {analysis.session_count} sessions",
                substrate_path="/CognitiveSubstrate/RoutingCascade",
                description=f"Expert '{expert}' is dominating routing — may indicate over-broad trigger conditions or under-specified alternatives",
                suggested_action=f"Review trigger conditions for {expert}. Consider if signals are being correctly discriminated or if another expert should handle some of these cases.",
                proposal_type="TUNE",
            ))
    
    # Missing expert activations
    expected_experts = {"Validator", "Scaffolder", "Restorer", "Direct", "Socratic", "Grounding"}
    activated = set(analysis.expert_frequency.keys())
    never_activated = expected_experts - activated
    if never_activated and analysis.session_count >= 5:
        for expert in never_activated:
            findings.append(EvalFinding(
                category="routing",
                severity="low",
                evidence=f"{expert} never activated across {analysis.session_count} sessions",
                substrate_path="/CognitiveSubstrate/SignalResponse",
                description=f"Expert '{expert}' has no activations — either trigger conditions are too narrow or the signal genuinely doesn't occur",
                suggested_action=f"Verify {expert} trigger conditions are reachable. If the expert is genuinely unused, consider if its signals are being captured by another expert.",
                proposal_type="TUNE",
            ))
    
    return findings


def _eval_crash_patterns(analysis: SessionAnalysis, substrate: UsdStage) -> list:
    """Evaluate crash patterns against substrate's crash prediction and recovery."""
    findings = []
    
    # Recurring crash triggers not in substrate
    known_triggers_prim = substrate.get_prim("CognitiveSubstrate/EnergySignature") if substrate else None
    # We check crash frequency regardless
    for trigger, count in analysis.crash_trigger_frequency.items():
        if count >= 3:
            findings.append(EvalFinding(
                category="momentum",
                severity="high",
                evidence=f"Crash trigger '{trigger}' appeared {count} times",
                substrate_path="/CognitiveSubstrate/EnergySignature",
                description=f"Recurring crash trigger '{trigger}' — substrate crash prediction may not be catching this early enough",
                suggested_action="Add this trigger to crash prediction warning signs if not already present, or lower the intervention threshold for this signal.",
                proposal_type="ADD" if count >= 4 else "TUNE",
            ))
    
    # High crash rate
    sessions_with_crash = sum(1 for p in analysis.momentum_patterns if p.get("had_crash"))
    if analysis.session_count >= 3 and sessions_with_crash / analysis.session_count > 0.5:
        findings.append(EvalFinding(
            category="momentum",
            severity="critical",
            evidence=f"{sessions_with_crash}/{analysis.session_count} sessions ended with a crash",
            substrate_path="/CognitiveSubstrate/MomentumEngine",
            description="More than half of sessions are ending in crashes — momentum management or energy alignment may be failing",
            suggested_action="Review energy curve alignment: is hard work being scheduled too late? Are crash prediction signals being missed? Is the recovery menu effective?",
            proposal_type="MODIFY",
        ))
    
    return findings


def _eval_stuck_patterns(analysis: SessionAnalysis, substrate: UsdStage) -> list:
    """Evaluate stuck patterns against stuck taxonomy."""
    findings = []
    
    # Dominant stuck type
    if analysis.stuck_type_frequency:
        dominant = max(analysis.stuck_type_frequency, key=analysis.stuck_type_frequency.get)
        count = analysis.stuck_type_frequency[dominant]
        if count >= 3:
            findings.append(EvalFinding(
                category="stuck",
                severity="medium",
                evidence=f"Stuck type '{dominant}' occurred {count} times across sessions",
                substrate_path="/CognitiveSubstrate/StuckTaxonomy",
                description=f"Recurring '{dominant}' stuck state — current intervention may not be resolving it",
                suggested_action=f"Review the intervention for '{dominant}' stuck type. Is the current strategy effective? Consider adding alternative interventions or adjusting the MicroCommitment routing.",
                proposal_type="MODIFY",
            ))
    
    # Stuck types not in taxonomy
    known_types = {"confused", "overwhelmed", "avoidance", "perfectionism", "energy", "fear"}
    for st in analysis.stuck_type_frequency:
        if st not in known_types:
            findings.append(EvalFinding(
                category="stuck",
                severity="medium",
                evidence=f"Unrecognized stuck type: '{st}'",
                substrate_path="/CognitiveSubstrate/StuckTaxonomy",
                description=f"Stuck type '{st}' not in current taxonomy — may need a new entry",
                suggested_action=f"Evaluate whether '{st}' is a genuine new stuck type or a variant of an existing one. If new, add to taxonomy with signals, intervention, and NEVER constraints.",
                proposal_type="ADD",
            ))
    
    return findings


def _eval_momentum_patterns(analysis: SessionAnalysis, substrate: UsdStage) -> list:
    """Evaluate momentum engine effectiveness."""
    findings = []
    
    # Sessions with burst but no crash vs burst then crash
    bursts = [p for p in analysis.momentum_patterns if p.get("had_burst")]
    burst_crashes = [p for p in bursts if p.get("had_crash")]
    
    if len(bursts) >= 3 and len(burst_crashes) / len(bursts) > 0.5:
        findings.append(EvalFinding(
            category="momentum",
            severity="high",
            evidence=f"{len(burst_crashes)}/{len(bursts)} burst sessions ended in crash",
            substrate_path="/CognitiveSubstrate/BurstProtocol",
            description="Bursts are frequently leading to crashes — exit management may be failing",
            suggested_action="Review burst winding and exit_prep phases. Are the body checks landing? Is the exit suggestion frequency appropriate?",
            proposal_type="TUNE",
        ))
    
    return findings


def _eval_novel_signals(analysis: SessionAnalysis, substrate: UsdStage) -> list:
    """Evaluate accumulated novel signals for fast-path promotion."""
    findings = []
    
    if len(analysis.novel_signals_accumulated) >= 3:
        # Group by similarity (simple: exact dedup)
        unique = list(set(analysis.novel_signals_accumulated))
        findings.append(EvalFinding(
            category="routing",
            severity="medium",
            evidence=f"{len(analysis.novel_signals_accumulated)} novel signals ({len(unique)} unique): {unique[:5]}",
            substrate_path="/CognitiveSubstrate/RoutingCascade",
            description="Accumulated novel signal fingerprints — candidates for permanent fast-path addition",
            suggested_action="Review each unique signal. For signals that appeared 3+ times, propose a new fast-path entry in the Lightning Indexer table.",
            proposal_type="ADD",
        ))
    
    return findings


def _eval_constitutional(analysis: SessionAnalysis, substrate: UsdStage) -> list:
    """Detect constitutional constraint patterns from session behavioral signals."""
    findings = []
    
    # This evaluator works on the per-session captures, not aggregated analysis.
    # It's called with analysis for frequency, but the real signal is in individual captures.
    # For now, check if constitutional keywords appear frequently enough to warrant attention.
    
    return findings


def _eval_energy_alignment(analysis: SessionAnalysis, substrate: UsdStage) -> list:
    """Check if session patterns align with the energy signature model."""
    findings = []
    
    # Check if goals match energy-appropriate work types
    # This is a coarse check — the real signal would come from timestamped data
    if analysis.recurring_goals:
        top_goals = sorted(analysis.recurring_goals.items(), key=lambda x: -x[1])[:5]
        # Flag if debugging/admin-heavy (high activation cost) goals are dominant
        high_cost_keywords = {"debug", "fix", "admin", "plan", "organize", "setup"}
        high_cost_count = sum(count for word, count in top_goals if word in high_cost_keywords)
        if high_cost_count > analysis.session_count * 0.4:
            findings.append(EvalFinding(
                category="energy",
                severity="medium",
                evidence=f"High-activation-cost goals dominate: {top_goals[:3]}",
                substrate_path="/CognitiveSubstrate/EnergySignature",
                description="Sessions are dominated by high-activation-cost work — the dopamine map suggests routing toward low-cost work to build momentum first",
                suggested_action="Consider adding a session-start heuristic: if the primary goal is high-cost (debugging, admin), suggest a 10-min low-cost warm-up (research, creative) to build activation momentum.",
                proposal_type="ADD",
            ))
    
    return findings


# ── File I/O ─────────────────────────────────────────────────────────────────

def save_report(report: EvalReport, filepath: str):
    """Save evaluation report to JSON."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    Path(filepath).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def load_analysis(filepath: str) -> SessionAnalysis:
    """Load a session analysis from JSON."""
    data = json.loads(Path(filepath).read_text(encoding="utf-8"))
    analysis = SessionAnalysis()
    analysis.session_count = data.get("session_count", 0)
    analysis.date_range = tuple(data.get("date_range", ["", ""]))
    analysis.expert_frequency = data.get("expert_frequency", {})
    analysis.crash_trigger_frequency = data.get("crash_trigger_frequency", {})
    analysis.stuck_type_frequency = data.get("stuck_type_frequency", {})
    analysis.momentum_patterns = data.get("momentum_patterns", [])
    analysis.novel_signals_accumulated = data.get("novel_signals_accumulated", [])
    analysis.recurring_goals = data.get("recurring_goals", {})
    analysis.insights = data.get("insights", [])
    return analysis


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from datetime import datetime
    
    if len(sys.argv) < 2:
        print("Usage: substrate_evaluator.py <analysis.json> [substrate.usda]")
        sys.exit(1)
    
    analysis = load_analysis(sys.argv[1])
    
    substrate = None
    if len(sys.argv) >= 3:
        substrate = read_stage(sys.argv[2])
    else:
        substrate = UsdStage()  # Empty stage — evaluate without substrate context
    
    report = evaluate(analysis, substrate)
    report.timestamp = datetime.now().isoformat()
    
    print(f"\n{report.summary}\n")
    for f in report.findings:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(f.severity, "⚪")
        print(f"  {icon} [{f.category}] {f.description}")
        print(f"    Evidence: {f.evidence}")
        print(f"    Action: {f.suggested_action}")
        print(f"    Type: {f.proposal_type} @ {f.substrate_path}")
        print()
    
    out_path = Path(sys.argv[1]).parent / "_eval_report.json"
    save_report(report, str(out_path))
    print(f"Report saved to {out_path}")
