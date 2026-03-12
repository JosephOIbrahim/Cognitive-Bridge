"""
review.py — Interactive proposal review and approval.

Replaces the manual "edit JSON, set status to approved, run apply" workflow.
Presents each pending proposal, user says yes/no, approved ones apply immediately.

Usage:
    python review.py                    # Interactive review of all pending
    python review.py --auto-apply       # Apply immediately after approval
    python review.py --list             # Just list pending proposals
    python review.py --approve <id>     # Approve specific proposal (non-interactive)
    python review.py --reject <id>      # Reject specific proposal (non-interactive)
    python review.py --approve-all      # Approve all pending (use with caution)

Claude Code usage:
    Claude Code reads proposals, presents them conversationally,
    then runs: python review.py --approve 2026-02-18_proposal_001
    for each one the user accepts.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
PROPOSALS_DIR = BASE_DIR / "proposals"
HISTORY_DIR = BASE_DIR / "history"

# Add scripts to path for deployer
sys.path.insert(0, str(BASE_DIR / "scripts"))


def list_pending() -> list:
    """List all pending proposals."""
    if not PROPOSALS_DIR.exists():
        return []
    
    pending = []
    for f in sorted(PROPOSALS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") == "pending":
                pending.append({
                    "path": str(f),
                    "id": data.get("id", f.stem),
                    "title": data.get("title", "Untitled"),
                    "severity": data.get("severity", "unknown"),
                    "category": data.get("category", "unknown"),
                    "proposal_type": data.get("proposal_type", "unknown"),
                    "description": data.get("description", ""),
                    "rationale": data.get("rationale", ""),
                    "evidence": data.get("evidence", ""),
                    "risk_assessment": data.get("risk_assessment", ""),
                    "edits": data.get("edits", []),
                })
        except Exception:
            pass
    
    return pending


def approve(proposal_id: str, auto_apply: bool = False) -> dict:
    """Approve a proposal by ID. Optionally auto-apply."""
    result = {"success": False, "message": ""}
    
    json_path = _find_proposal(proposal_id)
    if not json_path:
        result["message"] = f"Proposal not found: {proposal_id}"
        return result
    
    data = json.loads(json_path.read_text(encoding="utf-8"))
    data["status"] = "approved"
    data["approved_at"] = datetime.now().isoformat()
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    result["success"] = True
    result["message"] = f"Approved: {proposal_id}"
    
    if auto_apply:
        apply_result = _apply(json_path)
        result["applied"] = apply_result
        if apply_result.get("success"):
            result["message"] += f" → Applied ({len(apply_result.get('changes_made', []))} changes)"
        else:
            result["message"] += f" → Apply FAILED: {apply_result.get('errors', [])}"
    
    return result


def reject(proposal_id: str, reason: str = "") -> dict:
    """Reject a proposal by ID."""
    json_path = _find_proposal(proposal_id)
    if not json_path:
        return {"success": False, "message": f"Proposal not found: {proposal_id}"}
    
    data = json.loads(json_path.read_text(encoding="utf-8"))
    data["status"] = "rejected"
    data["rejected_at"] = datetime.now().isoformat()
    if reason:
        data["rejection_reason"] = reason
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    return {"success": True, "message": f"Rejected: {proposal_id}"}


def interactive_review(auto_apply: bool = False):
    """Interactive review loop — present each proposal, get yes/no."""
    pending = list_pending()
    
    if not pending:
        print("No pending proposals. Run 'python iterate.py iterate' first.")
        return
    
    severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
    
    print(f"\n{'═' * 60}")
    print(f"  PROPOSAL REVIEW — {len(pending)} pending")
    print(f"{'═' * 60}\n")
    
    approved_count = 0
    rejected_count = 0
    
    for i, p in enumerate(pending, 1):
        icon = severity_icon.get(p["severity"], "⚪")
        
        print(f"  ─── Proposal {i}/{len(pending)} ───")
        print(f"  {icon} {p['id']}")
        print(f"  Type: {p['proposal_type']} | Severity: {p['severity']} | Category: {p['category']}")
        print(f"")
        print(f"  WHAT: {p['description']}")
        print(f"  WHY:  {p['rationale']}")
        print(f"  EVIDENCE: {p['evidence']}")
        print(f"  RISK: {p['risk_assessment']}")
        
        if p["edits"]:
            print(f"  EDITS:")
            for edit in p["edits"]:
                print(f"    • {edit['operation']} {edit['target_path']}.{edit.get('target_attr', '')}")
                if edit.get("old_value"):
                    print(f"      was: {edit['old_value']}")
                if edit.get("new_value"):
                    print(f"      now: {edit['new_value']}")
        
        print()
        
        while True:
            try:
                choice = input("  [a]pprove / [r]eject / [s]kip / [q]uit? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Exiting review.")
                return
            
            if choice in ("a", "approve", "y", "yes"):
                result = approve(p["id"], auto_apply=auto_apply)
                print(f"  ✅ {result['message']}")
                approved_count += 1
                break
            elif choice in ("r", "reject", "n", "no"):
                reason = input("  Reason (optional): ").strip()
                result = reject(p["id"], reason)
                print(f"  ❌ {result['message']}")
                rejected_count += 1
                break
            elif choice in ("s", "skip"):
                print("  ⏭ Skipped.")
                break
            elif choice in ("q", "quit"):
                print("  Exiting review.")
                _print_summary(approved_count, rejected_count, len(pending))
                return
            else:
                print("  Enter a, r, s, or q.")
        
        print()
    
    _print_summary(approved_count, rejected_count, len(pending))


def _find_proposal(proposal_id: str) -> Path:
    """Find a proposal JSON file by ID."""
    # Direct path
    if Path(proposal_id).exists():
        return Path(proposal_id)
    
    # By ID in proposals dir
    candidate = PROPOSALS_DIR / f"{proposal_id}.json"
    if candidate.exists():
        return candidate
    
    # Glob
    matches = list(PROPOSALS_DIR.glob(f"*{proposal_id}*.json"))
    if len(matches) == 1:
        return matches[0]
    
    return None


def _apply(json_path: Path) -> dict:
    """Apply an approved proposal."""
    try:
        from substrate_deployer import apply_proposal, load_config
        config = load_config()
        config["history_dir"] = str(HISTORY_DIR)
        return apply_proposal(str(json_path), config)
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def _print_summary(approved: int, rejected: int, total: int):
    skipped = total - approved - rejected
    print(f"\n  Summary: {approved} approved, {rejected} rejected, {skipped} skipped out of {total}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Review substrate proposals")
    parser.add_argument("--list", action="store_true", help="List pending proposals")
    parser.add_argument("--approve", metavar="ID", help="Approve a specific proposal")
    parser.add_argument("--reject", metavar="ID", help="Reject a specific proposal")
    parser.add_argument("--reason", default="", help="Rejection reason (with --reject)")
    parser.add_argument("--approve-all", action="store_true", help="Approve all pending")
    parser.add_argument("--auto-apply", action="store_true", help="Apply immediately after approval")
    
    args = parser.parse_args()
    
    if args.list:
        pending = list_pending()
        if not pending:
            print("No pending proposals.")
        else:
            icon_map = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
            for p in pending:
                icon = icon_map.get(p["severity"], "⚪")
                print(f"  {icon} {p['id']}: {p['title']}")
    
    elif args.approve:
        result = approve(args.approve, auto_apply=args.auto_apply)
        print(result["message"])
    
    elif args.reject:
        result = reject(args.reject, args.reason)
        print(result["message"])
    
    elif args.approve_all:
        pending = list_pending()
        for p in pending:
            result = approve(p["id"], auto_apply=args.auto_apply)
            print(f"  {result['message']}")
    
    else:
        interactive_review(auto_apply=args.auto_apply)


if __name__ == "__main__":
    main()
