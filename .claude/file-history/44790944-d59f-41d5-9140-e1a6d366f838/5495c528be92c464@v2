"""PreToolUse hook: block Edit/Write to deployed or installed copies.

Reads JSON from stdin (Claude Code hook protocol), checks file_path
against known deployed-copy patterns. Outputs JSON deny decision if
the path matches a deployed copy, otherwise exits 0 silently.

Exit codes:
  0 = allow (or deny via JSON hookSpecificOutput)
  2 = block (stderr fed to Claude as error)
"""
import json
import sys


# Patterns that indicate a deployed/installed copy — NEVER edit these.
# Matches anywhere in the normalized (forward-slash) path.
DEPLOYED_PATTERNS = [
    "/.synapse/",
    "/.orchestra/",
    "/node_modules/",
    "/site-packages/",
    "/dist/",
    "/__pycache__/",
    "/.venv/",
    "/venv/",
]

# Exact directory prefixes that are SOURCES (not deployed), even if
# they live under ~/.claude. These override the patterns above.
SOURCE_OVERRIDES = [
    "/.claude/commands/",
    "/.claude/skills/",
    "/.claude/hooks/",
    "/.claude/handovers/",
]


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        # Write tool uses file_path, Edit uses file_path — both covered.
        # If neither, nothing to guard.
        sys.exit(0)

    # Normalize to forward slashes for consistent matching
    normalized = file_path.replace("\\", "/")

    # Check source overrides first — these are always allowed
    for override in SOURCE_OVERRIDES:
        if override in normalized:
            sys.exit(0)

    # Check deployed patterns
    for pattern in DEPLOYED_PATTERNS:
        if pattern in normalized:
            reason = (
                f"BLOCKED: '{file_path}' is a deployed/installed copy "
                f"(matched '{pattern.strip('/')}/'). "
                f"Edit the repo source instead. "
                f"See ~/CLAUDE.md 'Source vs Deployed' table."
            )
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
            json.dump(result, sys.stdout)
            sys.exit(0)

    # Not a deployed path — allow
    sys.exit(0)


if __name__ == "__main__":
    main()
