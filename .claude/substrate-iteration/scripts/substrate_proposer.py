"""
substrate_proposer.py — Generate concrete edit proposals from evaluation findings.

Takes:
- EvalReport (from substrate_evaluator.py)
- Current substrate (USD source)

Produces:
- Individual proposal files (one per finding, or grouped by related findings)
- Each proposal includes: before/after, rationale, evidence, risk assessment

The key principle: proposals are REVIEWABLE. The user sees exactly what
changes, why, and what evidence supports it. One concern per proposal.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from usd_ops import UsdStage, UsdPrim, UsdAttribute, read_stage


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class ProposalEdit:
    """A single edit within a proposal."""
    target_path: str     # USD prim path
    target_attr: str     # Attribute name (empty for prim-level)
    operation: str       # set, add, remove, modify
    old_value: any = None
    new_value: any = None
    attr_type: str = ""  # USD type for new attributes
    
    def to_dict(self) -> dict:
        return {
            "target_path": self.target_path,
            "target_attr": self.target_attr,
            "operation": self.operation,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "attr_type": self.attr_type,
        }


@dataclass 
class Proposal:
    """A complete edit proposal for user review."""
    id: str = ""
    timestamp: str = ""
    category: str = ""
    proposal_type: str = ""    # TUNE, ADD, MODIFY, RESTRUCTURE, DEPRECATE
    severity: str = ""
    title: str = ""
    description: str = ""
    rationale: str = ""
    evidence: str = ""
    risk_assessment: str = ""
    edits: list = field(default_factory=list)  # List of ProposalEdit
    status: str = "pending"    # pending, approved, rejected, applied
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "proposal_type": self.proposal_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "risk_assessment": self.risk_assessment,
            "edits": [e.to_dict() for e in self.edits],
            "status": self.status,
        }
    
    def to_markdown(self) -> str:
        """Render as a human-readable markdown proposal."""
        lines = []
        lines.append(f"# Proposal: {self.title}")
        lines.append(f"")
        lines.append(f"**ID:** {self.id}  ")
        lines.append(f"**Type:** {self.proposal_type} | **Severity:** {self.severity} | **Category:** {self.category}  ")
        lines.append(f"**Status:** {self.status}  ")
        lines.append(f"**Generated:** {self.timestamp}")
        lines.append(f"")
        lines.append(f"## What")
        lines.append(f"{self.description}")
        lines.append(f"")
        lines.append(f"## Why")
        lines.append(f"{self.rationale}")
        lines.append(f"")
        lines.append(f"## Evidence")
        lines.append(f"{self.evidence}")
        lines.append(f"")
        lines.append(f"## Risk")
        lines.append(f"{self.risk_assessment}")
        lines.append(f"")
        lines.append(f"## Edits")
        lines.append(f"")
        
        for i, edit in enumerate(self.edits, 1):
            lines.append(f"### Edit {i}: `{edit.target_path}`")
            lines.append(f"- **Operation:** {edit.operation}")
            if edit.target_attr:
                lines.append(f"- **Attribute:** `{edit.target_attr}`")
            if edit.old_value is not None:
                lines.append(f"- **Before:** `{edit.old_value}`")
            if edit.new_value is not None:
                lines.append(f"- **After:** `{edit.new_value}`")
            if edit.attr_type:
                lines.append(f"- **Type:** `{edit.attr_type}`")
            lines.append(f"")
        
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"**To approve:** Run `python substrate_deployer.py apply {self.id}`  ")
        lines.append(f"**To reject:** Delete this file or change status to 'rejected'")
        
        return "\n".join(lines)


# ── Proposal Generation ─────────────────────────────────────────────────────

def generate_proposals(findings: list, substrate: UsdStage, output_dir: str) -> list:
    """
    Generate proposal files from evaluation findings.
    One proposal per finding (not bundled — user reviews individually).
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    proposals = []
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    
    for i, finding in enumerate(findings, 1):
        proposal = _finding_to_proposal(finding, substrate)
        proposal.id = f"{date_str}_proposal_{i:03d}"
        proposal.timestamp = now.isoformat()
        
        # Save as both JSON (machine-readable) and MD (human-readable)
        json_path = output_path / f"{proposal.id}.json"
        md_path = output_path / f"{proposal.id}.md"
        
        json_path.write_text(json.dumps(proposal.to_dict(), indent=2), encoding="utf-8")
        md_path.write_text(proposal.to_markdown(), encoding="utf-8")
        
        proposals.append(proposal)
    
    return proposals


def _finding_to_proposal(finding, substrate: UsdStage) -> Proposal:
    """Convert a single evaluation finding into a proposal with concrete edits."""
    
    proposal = Proposal(
        category=finding.category,
        proposal_type=finding.proposal_type,
        severity=finding.severity,
        evidence=finding.evidence,
    )
    
    # Route to specific proposal generators based on category + type
    generator = PROPOSAL_GENERATORS.get(
        (finding.category, finding.proposal_type),
        _generate_generic_proposal
    )
    
    generator(proposal, finding, substrate)
    
    return proposal


# ── Specific Proposal Generators ─────────────────────────────────────────────

def _generate_routing_tune(proposal: Proposal, finding, substrate: UsdStage):
    """Generate a TUNE proposal for routing issues."""
    proposal.title = f"Tune routing: {finding.description[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = "Low risk. Tuning adjusts thresholds/weights, doesn't change structure. Easily reversible."
    
    # The actual edit depends on what the finding identified.
    # For expert overuse: suggest adjusting trigger breadth
    if "dominating" in finding.description.lower():
        expert_name = finding.description.split("'")[1] if "'" in finding.description else "Unknown"
        proposal.edits.append(ProposalEdit(
            target_path=finding.substrate_path,
            target_attr=f"{expert_name.lower()}_trigger_breadth",
            operation="modify",
            old_value="(review current trigger conditions)",
            new_value="(narrow trigger conditions — Claude Code will specify exact change after reviewing substrate)",
            attr_type="string",
        ))
    
    # For never-activated experts: suggest broadening triggers
    elif "no activations" in finding.description.lower():
        expert_name = finding.description.split("'")[1] if "'" in finding.description else "Unknown"
        proposal.edits.append(ProposalEdit(
            target_path=finding.substrate_path,
            target_attr=f"{expert_name.lower()}_trigger_conditions",
            operation="modify",
            old_value="(review current trigger conditions)",
            new_value="(broaden trigger conditions or verify signals exist)",
            attr_type="string",
        ))


def _generate_momentum_tune(proposal: Proposal, finding, substrate: UsdStage):
    """Generate a TUNE proposal for momentum issues."""
    proposal.title = f"Tune momentum: {finding.description[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = "Medium risk. Momentum tuning affects flow experience. Monitor for 3 sessions after applying."


def _generate_momentum_add(proposal: Proposal, finding, substrate: UsdStage):
    """Generate an ADD proposal for new crash prediction signals."""
    proposal.title = f"Add crash trigger: {finding.evidence[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = "Low risk. Adding a new crash prediction signal doesn't remove existing ones."
    
    trigger = finding.evidence.split("'")[1] if "'" in finding.evidence else "unknown"
    proposal.edits.append(ProposalEdit(
        target_path="/CognitiveSubstrate/EnergySignature/CrashPrediction",
        target_attr="warning_signs",
        operation="add",
        old_value="(current list)",
        new_value=f"Add '{trigger}' to warning signs list",
        attr_type="string[]",
    ))


def _generate_momentum_modify(proposal: Proposal, finding, substrate: UsdStage):
    """Generate a MODIFY proposal for momentum structure changes."""
    proposal.title = f"Modify momentum: {finding.description[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = "High risk. Modifying momentum engine affects core flow management. Requires careful testing."


def _generate_stuck_modify(proposal: Proposal, finding, substrate: UsdStage):
    """Generate a MODIFY proposal for stuck taxonomy."""
    proposal.title = f"Modify stuck taxonomy: {finding.description[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = "Medium risk. Modifying stuck interventions affects recovery. Test with next stuck occurrence."


def _generate_stuck_add(proposal: Proposal, finding, substrate: UsdStage):
    """Generate an ADD proposal for new stuck types."""
    proposal.title = f"Add stuck type: {finding.description[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = "Low risk. Adding a new stuck type doesn't affect existing ones."
    
    if "'" in finding.evidence:
        new_type = finding.evidence.split("'")[1]
        proposal.edits.append(ProposalEdit(
            target_path="/CognitiveSubstrate/StuckTaxonomy",
            target_attr=new_type,
            operation="add",
            new_value=f"New stuck type '{new_type}' — needs signals, intervention, and NEVER constraints",
            attr_type="string",
        ))


def _generate_routing_add(proposal: Proposal, finding, substrate: UsdStage):
    """Generate an ADD proposal for new fast-path routing."""
    proposal.title = f"Add fast-path: {finding.description[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = "Low risk. New fast-paths add optimization without changing fallback behavior."


def _generate_energy_add(proposal: Proposal, finding, substrate: UsdStage):
    """Generate an ADD proposal for energy-related rules."""
    proposal.title = f"Add energy rule: {finding.description[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = "Medium risk. Energy routing affects task assignment. Monitor session satisfaction."


def _generate_generic_proposal(proposal: Proposal, finding, substrate: UsdStage):
    """Fallback generator for unmatched category/type combinations."""
    proposal.title = f"{finding.proposal_type}: {finding.description[:60]}"
    proposal.description = finding.description
    proposal.rationale = finding.suggested_action
    proposal.risk_assessment = f"Risk depends on scope. Proposal type '{finding.proposal_type}' at {finding.substrate_path}."


# Generator dispatch table
PROPOSAL_GENERATORS = {
    ("routing", "TUNE"): _generate_routing_tune,
    ("routing", "ADD"): _generate_routing_add,
    ("momentum", "TUNE"): _generate_momentum_tune,
    ("momentum", "ADD"): _generate_momentum_add,
    ("momentum", "MODIFY"): _generate_momentum_modify,
    ("stuck", "MODIFY"): _generate_stuck_modify,
    ("stuck", "ADD"): _generate_stuck_add,
    ("energy", "ADD"): _generate_energy_add,
}


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: substrate_proposer.py <eval_report.json> [substrate.usda] [output_dir]")
        sys.exit(1)
    
    # Load evaluation report
    report_data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    
    # Reconstruct findings as simple objects (duck-typing)
    class Finding:
        pass
    
    findings = []
    for f_data in report_data.get("findings", []):
        f = Finding()
        for k, v in f_data.items():
            setattr(f, k, v)
        findings.append(f)
    
    # Load substrate
    substrate = UsdStage()
    if len(sys.argv) >= 3:
        substrate = read_stage(sys.argv[2])
    
    # Output dir
    output_dir = sys.argv[3] if len(sys.argv) >= 4 else str(Path(sys.argv[1]).parent / "proposals")
    
    proposals = generate_proposals(findings, substrate, output_dir)
    
    print(f"\nGenerated {len(proposals)} proposals in {output_dir}/")
    for p in proposals:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(p.severity, "⚪")
        print(f"  {icon} {p.id}: {p.title}")
