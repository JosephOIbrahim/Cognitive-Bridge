"""
ingest.py — Ingest a session capture from stdin or file.

Usage:
    # Pipe or paste (Ctrl+D / Ctrl+Z to end)
    python ingest.py

    # From a file
    python ingest.py --file /path/to/capture.txt

    # With explicit date
    python ingest.py --date 2026-02-18

    # From clipboard (Windows)
    powershell Get-Clipboard | python ingest.py

    # From clipboard (Mac)
    pbpaste | python ingest.py

Claude Code usage:
    User pastes session capture → Claude Code writes it to a temp file
    → runs: python ingest.py --file /tmp/capture.txt
    → capture is saved, parsed, and validated.
"""

import sys
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
CAPTURES_DIR = BASE_DIR / "captures"


def ingest(text: str, date: str = None) -> dict:
    """
    Ingest a session capture block.
    
    Returns: {success, filepath, date, goal, warnings}
    """
    result = {
        "success": False,
        "filepath": "",
        "date": "",
        "goal": "",
        "warnings": [],
    }
    
    text = text.strip()
    if not text:
        result["warnings"].append("Empty input — nothing to ingest.")
        return result
    
    # Validate: looks like a session capture?
    is_capture = any(kw in text.lower() for kw in [
        "session capture", "goal:", "progress:", "stopped at:",
        "next steps:", "state:", "momentum"
    ])
    
    if not is_capture:
        result["warnings"].append(
            "This doesn't look like a session capture block. "
            "Expected keywords like 'SESSION CAPTURE', 'Goal:', 'Progress:', etc. "
            "Saving anyway — the parser will do its best."
        )
    
    # Extract or assign date
    if date:
        capture_date = date
    else:
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if date_match:
            capture_date = date_match.group(1)
        else:
            capture_date = datetime.now().strftime("%Y-%m-%d")
            result["warnings"].append(f"No date found in capture — using today: {capture_date}")
    
    result["date"] = capture_date
    
    # Extract goal for confirmation
    goal_match = re.search(r'Goal:\s*(.+?)(?:\n|$)', text)
    if goal_match:
        result["goal"] = goal_match.group(1).strip().rstrip('|').strip()
    
    # Save to captures dir
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Handle duplicate dates — append suffix
    filename = f"session_{capture_date}.txt"
    filepath = CAPTURES_DIR / filename
    suffix = 1
    while filepath.exists():
        filename = f"session_{capture_date}_{suffix}.txt"
        filepath = CAPTURES_DIR / filename
        suffix += 1
    
    filepath.write_text(text, encoding="utf-8")
    result["filepath"] = str(filepath)
    result["success"] = True
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest a session capture")
    parser.add_argument("--file", "-f", help="Read from file instead of stdin")
    parser.add_argument("--date", "-d", help="Override date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        # Read from stdin (pipe or paste)
        if sys.stdin.isatty():
            print("Paste session capture below. Press Ctrl+D (Unix) or Ctrl+Z (Windows) when done:\n")
        text = sys.stdin.read()
    
    result = ingest(text, args.date)
    
    if result["success"]:
        print(f"✅ Captured: {result['filepath']}")
        print(f"   Date: {result['date']}")
        if result["goal"]:
            print(f"   Goal: {result['goal']}")
        for w in result["warnings"]:
            print(f"   ⚠ {w}")
    else:
        print("❌ Ingest failed.")
        for w in result["warnings"]:
            print(f"   {w}")
        sys.exit(1)


if __name__ == "__main__":
    main()
