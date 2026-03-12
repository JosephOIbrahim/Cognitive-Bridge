"""PostToolUse hook: warn when a .py file is written without explicit encoding.

Fires after Write/Edit on Python files. Reads the file content from
tool_input and checks for open() calls missing encoding='utf-8'.
Outputs a reminder to Claude via stdout (non-blocking, informational).

This is a PostToolUse hook so it cannot block -- it just reminds Claude
to fix the issue in a follow-up edit.
"""
import json
import re
import sys


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".py"):
        sys.exit(0)

    # Check content for open() without encoding
    # For Edit tool, check new_string; for Write tool, check content
    content = data.get("tool_input", {}).get("content", "")
    if not content:
        content = data.get("tool_input", {}).get("new_string", "")
    if not content:
        sys.exit(0)

    # Find open() calls that write/read without explicit encoding
    # Match open(...) that has 'w', 'r', 'a' mode but no encoding=
    open_calls = re.findall(r'\bopen\s*\([^)]+\)', content)
    missing_encoding = []
    for call in open_calls:
        # Skip if it already has encoding=
        if "encoding" in call:
            continue
        # Skip binary mode (rb, wb, ab)
        if re.search(r"""['"]([rawx+]*b[rawx+]*)['"]""", call):
            continue
        missing_encoding.append(call.strip())

    if missing_encoding:
        msg = (
            f"ENCODING REMINDER: {file_path} has open() calls without "
            f"explicit encoding='utf-8'. On Windows, default cp1252 "
            f"will crash on Unicode characters. Found: "
            + "; ".join(missing_encoding[:3])
        )
        # Output as additional context for Claude
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": msg,
            }
        }
        json.dump(result, sys.stdout)

    sys.exit(0)


if __name__ == "__main__":
    main()
