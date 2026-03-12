# Project Memory — TranslatorsGame

## Session Scope Rule (CRITICAL)

**Your working directory defines your scope.** In a TranslatorsGame session, only work on TranslatorsGame files, `~/CLAUDE.md` (global config), and `~/.claude/*` (global tooling). Never edit files in or operate on other repos (Orchestra, Synapse, OTTO, comfyui-agent, etc.).

**Root cause:** The `/insights` report loads context from ALL sessions across ALL projects. This creates context pollution — once cross-project context is in the window, it's easy to follow references to other projects instead of staying scoped. Treat insights output as **read-only reference**, not authorization to operate cross-project.

**What happened (twice in one session):**
1. Insights flagged He2025 attribution across all projects. User said "fix all of them." I edited CLAUDE.md in Orchestra, Synapse, and comfyui-agent — had to `git checkout --` all three.
2. User said "continue to TOPS and building a render farm." I spun up Explore agents against the Synapse codebase and started planning Houdini work from a TranslatorsGame session.

**Rule:** If a request targets another project, say "that belongs in a [project] session" instead of crossing boundaries. Only `~/CLAUDE.md` and `~/.claude/*` are fair game from any session.

## Insights Session (2026-02-14)

Three improvements implemented from /insights report:
1. **Bug Fix Protocol** added to `~/.claude/CLAUDE.md` — enumerate all cases before fixing, fix all in one pass
2. **`/deploy` skill** created at `~/.claude/skills/deploy/SKILL.md` — test → commit → push → deploy pipeline with pre-flight checks
3. **Zombie process cleanup** added to `~/.claude/hooks/session-start-check.py` — auto-kills stale `synapse_bridge` and `mcp_bridge` processes at session start

## He2025 Attribution Fix (pending per-project)

`~/CLAUDE.md` was fixed: renamed "He2025 Determinism" → "Determinism Requirements", application-level patterns no longer attributed to the paper, kernel-level patterns (Orchestra) correctly credited as inspired by it.

Still need fixing when working in each project:
- [ ] `Orchestra/CLAUDE.md` — "ThinkingMachines Compliance" section over-attributes
- [ ] `SYNAPSE/CLAUDE.md` — "He2025 determinism" line and tier pinning reference
- [ ] `comfyui-agent/CLAUDE.md` — "He2025 pattern" and "He2025 determinism audit" labels
- [x] `OTTO_OS/CLAUDE.md` — already honest, no changes needed
