# Plan: Build `/project-insights` Skill

## Context

The built-in `/insights` command analyzes ALL sessions across ALL projects and dumps the entire cross-project analysis into the current context window. This causes context pollution — Claude starts operating on other projects (editing their CLAUDE.md files, planning Houdini work from a JavaScript project session). This happened twice in today's session.

**Root cause:** `/insights` doesn't filter by current working directory. Session metadata already has a `project_path` field that could be used for scoping.

**Goal:** Build a `/project-insights` skill that reads the same `~/.claude/usage-data/` data but filters to the current project only, preventing cross-project context bleed.

## Data Structure (already exists)

- `~/.claude/usage-data/session-meta/*.json` — Per-session: `project_path`, `duration_minutes`, `tool_counts`, `languages`, `git_commits`, `lines_added/removed`, `first_prompt`, timestamps
- `~/.claude/usage-data/facets/*.json` — Per-session: `underlying_goal`, `goal_categories`, `outcome`, `friction_counts`, `friction_detail`, `primary_success`, `brief_summary`, `user_satisfaction_counts`
- Session IDs match between the two directories (same UUID filenames)

## Implementation

### File to create
`~/.claude/skills/project-insights/SKILL.md`

### What the skill instructs Claude to do

1. **Detect scope** — Get the current working directory (`$PWD` or equivalent)
2. **Read session-meta** — Read all JSON files in `~/.claude/usage-data/session-meta/`
3. **Filter** — Keep only sessions where `project_path` matches the current project (exact match OR current dir is a subdirectory of `project_path`)
4. **Read facets** — For matching sessions, read their corresponding facets from `~/.claude/usage-data/facets/`
5. **Analyze and present** — Synthesize a project-scoped report covering:
   - Session count, total time, message count, commits
   - Top tools used, languages touched
   - Goals and outcomes (from facets)
   - Friction patterns specific to THIS project
   - What's working well
   - Actionable suggestions scoped to this project only
6. **Guardrail** — Explicitly state: "This analysis is scoped to [project name]. Do NOT act on other projects mentioned in session history."

### Filtering logic detail

Project paths observed in data:
- `C:\Users\User` (38 sessions — home dir, catch-all)
- `C:\Users\User\SYNAPSE` (12 sessions)
- `C:\Users\User\JaimeIbrahim` (4 sessions)
- `C:\Users\User\comfyui-agent` (2 sessions)

Filter rule: Match sessions where `project_path` equals or is a parent of `$PWD`. If run from `C:\Users\User\Translators-Game\TranslatorsGame`, it would match sessions with `project_path = C:\Users\User\Translators-Game\TranslatorsGame` (exact) or potentially `C:\Users\User` (parent). Include a flag to control whether parent-path sessions are included (default: strict match only, with option to include parent).

## Verification

1. Run `/project-insights` from the TranslatorsGame directory — should show only TranslatorsGame sessions (likely very few since it's a new project)
2. Verify the output does NOT mention Synapse, Orchestra, Vercel, or other projects
3. Confirm the guardrail statement appears in output
