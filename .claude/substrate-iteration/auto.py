"""
auto.py — One-command substrate iteration.

Chains: ingest → evaluate → propose → review → apply

Usage:
    # Full loop with a new capture (paste or pipe)
    python auto.py

    # Full loop with a capture file
    python auto.py --capture session.txt

    # Full loop from clipboard (Windows)
    powershell Get-Clipboard | python auto.py

    # Full loop from clipboard (Mac)
    pbpaste | python auto.py

    # Skip ingest — just iterate on existing captures
    python auto.py --skip-ingest

    # Non-interactive — iterate + list proposals (no review prompt)
    python auto.py --skip-ingest --no-review

    # Nuclear: iterate + auto-approve + auto-apply everything (DANGEROUS)
    python auto.py --skip-ingest --auto-approve
"""

import sys
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
CAPTURES_DIR = BASE_DIR / "captures"
PROPOSALS_DIR = BASE_DIR / "proposals"
HISTORY_DIR = BASE_DIR / "history"

# Add local modules
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scripts"))


def run(
    capture_text: str = None,
    capture_file: str = None,
    skip_ingest: bool = False,
    no_review: bool = False,
    auto_approve: bool = False,
    date: str = None,
):
    """
    Full automation loop. Returns summary dict for Claude Code to read.
    """
    summary = {
        "ingested": None,
        "sessions_parsed": 0,
        "findings": 0,
        "proposals_generated": 0,
        "proposals_approved": 0,
        "proposals_applied": 0,
        "proposals_rejected": 0,
        "errors": [],
    }

    # ── Step 1: Ingest ──────────────────────────────────────────────────────
    if not skip_ingest:
        from ingest import ingest
        
        text = None
        if capture_file:
            try:
                text = Path(capture_file).read_text(encoding="utf-8")
            except Exception as e:
                summary["errors"].append(f"Can't read {capture_file}: {e}")
                return summary
        elif capture_text:
            text = capture_text
        elif not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            print("\n  Paste session capture below.")
            print("  Press Ctrl+D (Mac/Linux) or Ctrl+Z then Enter (Windows) when done:\n")
            try:
                text = sys.stdin.read()
            except KeyboardInterrupt:
                print("\n  Cancelled.")
                return summary
        
        if text and text.strip():
            result = ingest(text, date)
            if result["success"]:
                summary["ingested"] = result["filepath"]
                _step("INGEST", f"Saved → {result['filepath']}")
                if result["goal"]:
                    print(f"          Goal: {result['goal']}")
                for w in result["warnings"]:
                    print(f"          ⚠ {w}")
            else:
                for w in result["warnings"]:
                    summary["errors"].append(w)
                _step("INGEST", "⚠ Failed — continuing with existing captures")
        else:
            _step("INGEST", "No input — using existing captures")

    else:
        _step("INGEST", "Skipped")

    # ── Step 2: Iterate (parse → evaluate → propose) ────────────────────────
    from session_parser import parse_capture_dir, analyze_sessions, save_analysis
    from substrate_evaluator import evaluate, save_report, load_analysis
    from substrate_proposer import generate_proposals
    from substrate_deployer import load_config
    from usd_ops import read_stage, UsdStage

    config = load_config()
    
    # Parse
    captures = parse_capture_dir(str(CAPTURES_DIR))
    summary["sessions_parsed"] = len(captures)
    
    if not captures:
        _step("EVALUATE", "No captures found. Drop .txt files in captures/ first.")
        return summary
    
    _step("EVALUATE", f"Parsed {len(captures)} sessions")
    
    # Analyze
    analysis = analyze_sessions(captures)
    save_analysis(analysis, str(CAPTURES_DIR / "_analysis.json"))
    
    # Load substrate
    substrate = _load_substrate(config)
    
    # Evaluate
    report = evaluate(analysis, substrate)
    report.timestamp = datetime.now().isoformat()
    save_report(report, str(BASE_DIR / "_eval_report.json"))
    
    summary["findings"] = len(report.findings)
    
    if not report.findings:
        _step("EVALUATE", "No issues detected — substrate is tracking well. ✓")
        return summary
    
    _step("EVALUATE", f"{len(report.findings)} findings")
    for f in report.findings:
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(f.severity, "⚪")
        print(f"          {icon} {f.description}")
    
    # Propose
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Clear old pending proposals to avoid stale accumulation
    _clear_pending_proposals()
    
    proposals = generate_proposals(report.findings, substrate, str(PROPOSALS_DIR))
    summary["proposals_generated"] = len(proposals)
    
    _step("PROPOSE", f"Generated {len(proposals)} proposals")

    # ── Step 3: Review ──────────────────────────────────────────────────────
    if no_review and not auto_approve:
        _step("REVIEW", "Skipped (--no-review)")
        print(f"\n  Proposals in {PROPOSALS_DIR}/")
        print("  Run: python review.py")
        return summary

    from review import list_pending, approve, reject

    pending = list_pending()
    
    if not pending:
        _step("REVIEW", "No pending proposals")
        return summary

    if auto_approve:
        _step("REVIEW", f"Auto-approving {len(pending)} proposals (--auto-approve)")
        for p in pending:
            result = approve(p["id"], auto_apply=True)
            if result["success"]:
                summary["proposals_approved"] += 1
                if result.get("applied", {}).get("success"):
                    summary["proposals_applied"] += 1
                    print(f"          ✅ {p['id']}: applied")
                else:
                    print(f"          ✅ {p['id']}: approved (apply failed)")
            else:
                summary["errors"].append(result["message"])
        return summary

    # Interactive review
    _step("REVIEW", f"{len(pending)} proposals to review")
    print()
    
    severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
    
    for i, p in enumerate(pending, 1):
        icon = severity_icon.get(p["severity"], "⚪")
        
        print(f"  ─── {i}/{len(pending)} ─────────────────────────────")
        print(f"  {icon} {p['title']}")
        print(f"  Type: {p['proposal_type']}  Severity: {p['severity']}")
        print(f"  {p['description']}")
        print(f"  Evidence: {p['evidence']}")
        if p.get("risk_assessment"):
            print(f"  Risk: {p['risk_assessment']}")
        print()
        
        while True:
            try:
                choice = input("  [y]es / [n]o / [s]kip / [q]uit? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Ending review.")
                return summary
            
            if choice in ("y", "yes", "a", "approve"):
                result = approve(p["id"], auto_apply=True)
                if result["success"]:
                    summary["proposals_approved"] += 1
                    applied_info = result.get("applied", {})
                    if applied_info.get("success"):
                        summary["proposals_applied"] += 1
                        print(f"  ✅ Approved + applied\n")
                    else:
                        print(f"  ✅ Approved (apply needs manual run)\n")
                break
            elif choice in ("n", "no", "r", "reject"):
                reason = input("  Reason (optional): ").strip()
                reject(p["id"], reason)
                summary["proposals_rejected"] += 1
                print(f"  ❌ Rejected\n")
                break
            elif choice in ("s", "skip"):
                print(f"  ⏭ Skipped\n")
                break
            elif choice in ("q", "quit"):
                print("  Ending review.")
                return summary
            else:
                print("  y/n/s/q")
    
    # ── Done ────────────────────────────────────────────────────────────────
    print(f"\n{'═' * 50}")
    print(f"  Done. {summary['proposals_approved']} approved, "
          f"{summary['proposals_applied']} applied, "
          f"{summary['proposals_rejected']} rejected")
    print(f"{'═' * 50}\n")
    
    return summary


# ── Helpers ──────────────────────────────────────────────────────────────────

def _step(name: str, msg: str):
    """Print a step header."""
    print(f"\n  [{name}] {msg}")


def _load_substrate(config: dict):
    from usd_ops import read_stage, UsdStage
    path = config.get("substrate_core", "")
    if path and Path(path).exists():
        return read_stage(path)
    local = BASE_DIR.parent / "cognitive_substrate" / "core_substrate_v7.usda"
    if local.exists():
        return read_stage(str(local))
    return UsdStage()


def _clear_pending_proposals():
    """Remove old pending proposals so we don't accumulate stale ones."""
    if not PROPOSALS_DIR.exists():
        return
    for f in PROPOSALS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") == "pending":
                f.unlink()
                # Also remove matching .md
                md = f.with_suffix(".md")
                if md.exists():
                    md.unlink()
        except Exception:
            pass


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="One-command substrate iteration: ingest → evaluate → propose → review → apply"
    )
    parser.add_argument("--capture", "-c", help="Path to capture file to ingest")
    parser.add_argument("--date", "-d", help="Override capture date (YYYY-MM-DD)")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip ingest step")
    parser.add_argument("--no-review", action="store_true", help="Generate proposals but don't review")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve all proposals (DANGEROUS)")
    
    args = parser.parse_args()
    
    summary = run(
        capture_file=args.capture,
        skip_ingest=args.skip_ingest,
        no_review=args.no_review,
        auto_approve=args.auto_approve,
        date=args.date,
    )
    
    if summary["errors"]:
        print("  Errors:")
        for e in summary["errors"]:
            print(f"    ⚠ {e}")


if __name__ == "__main__":
    main()
