---
name: handover
description: End a session by capturing what was done, decisions made, blockers hit, and next steps into a handover document. Invoke at the end of any working session to prevent context amnesia. Also works mid-session to checkpoint progress.
argument-hint: 'optional: notes to highlight or project name'
allowed-tools: Bash, Read, Write, Glob, Grep
---

# /handover: Session Handover

Capture the current session's context into a structured handover document so the next session starts informed, not blank.

## Step 1: Gather Context

Run these in parallel to understand what happened this session:

**Git state** (if in a repo):
```bash
git log --oneline --since="8 hours ago" --no-walk=unsorted 2>/dev/null || echo "Not a git repo or no recent commits"
```
```bash
git diff --stat HEAD 2>/dev/null || echo "No git diff available"
```

**Recently modified files** (last 4 hours):
```bash
find . -maxdepth 3 -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.md" -o -name "*.toml" -o -name "*.json" | xargs ls -lt 2>/dev/null | head -20
```

**Check existing handover** (to build on, not duplicate):
- Read `~/.claude/handovers/latest.md` if it exists

## Step 2: Reflect on the Session

From your conversation history, extract:

1. **What was accomplished** - Concrete outcomes, not vague summaries. "Added /handover skill" not "worked on skills."
2. **Decisions made and why** - Every non-obvious choice with reasoning. Future-you needs the WHY.
3. **Blockers or issues hit** - What went wrong, what workaround was used, what's still broken.
4. **Open threads** - Anything started but not finished. Anything the user mentioned wanting to do next.
5. **Key files touched** - Specific paths that matter for continuity.

## Step 3: Write the Handover

Write to `~/.claude/handovers/latest.md` (always overwrite latest; archive previous first).

```bash
mkdir -p ~/.claude/handovers
```

If `latest.md` exists, archive it first:
```bash
if [ -f ~/.claude/handovers/latest.md ]; then
  mv ~/.claude/handovers/latest.md ~/.claude/handovers/$(date +%Y%m%d_%H%M%S).md
fi
```

Then write `~/.claude/handovers/latest.md` in this exact format:

```markdown
# Session Handover
**Date:** {YYYY-MM-DD HH:MM}
**Project:** {project name or "multi-project"}
**Working directory:** {cwd}

## What Was Done
- {concrete outcome 1}
- {concrete outcome 2}
- {concrete outcome 3}

## Decisions Made
| Decision | Why | Alternatives Considered |
|----------|-----|------------------------|
| {decision} | {reasoning} | {what else was considered} |

## Blockers / Issues
- {blocker and its status: resolved/workaround/open}

## Open Threads
- [ ] {unfinished task or next step}
- [ ] {thing user mentioned wanting to do}

## Key Files
- `{path}` - {what changed or why it matters}

## Session Notes
{any freeform context that doesn't fit above — user preferences observed, environment quirks, things to remember}
```

## Step 4: Update Auto-Memory (if warranted)

If any decisions or patterns from this session are **durable** (will matter beyond the next session), also append them to the appropriate memory file in `~/.claude/projects/*/memory/`. Follow the auto-memory guidelines — only save stable, verified patterns.

## Step 5: Confirm to User

After writing, display:

```
Handover saved to ~/.claude/handovers/latest.md

Captured:
- {N} outcomes
- {N} decisions
- {N} open threads

Next session: I'll pick up from the handover automatically.
```

## Loading a Handover (for the NEXT session)

When starting a new session, if `~/.claude/handovers/latest.md` exists, read it at the start to restore context. This happens naturally through CLAUDE.md or can be triggered by the user saying "load handover" or "pick up where we left off."
