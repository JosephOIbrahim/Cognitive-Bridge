---
name: agent-team-dispatch
description: Generate Claude Code Agent Team dispatch prompts with MOE (Mixture of Experts) roles, exclusive file ownership, phased gates, and live ASCII status bar reporting. Use this skill whenever the user wants to implement code changes using parallel Claude Code agents, run a sprint with multiple specialist agents, create a dispatch prompt for Claude Code Task tool, or coordinate multi-agent implementation with status tracking. Triggers include "agent team", "dispatch", "MOE agents", "status bar", "sprint", "parallel agents", "Task tool", or any request to break implementation work into specialist roles with progress reporting.
---

# Agent Team Dispatch

Generate self-contained Claude Code prompts that orchestrate parallel agent teams with MOE specialization, file-conflict prevention, hard phase gates, and real-time ASCII status reporting.

## When to Use

- User has a implementation plan / blueprint and wants it executed by Claude Code
- User wants to parallelize work across specialist agents
- User wants live progress tracking during Claude Code execution
- Any multi-file code change that benefits from role specialization

## Workflow

1. **Read the reference template** at `references/DISPATCH_TEMPLATE.md`
2. **Gather context** from the user about what needs to be built
3. **Fill the template** with project-specific agents, tasks, files, and gates
4. **Output a single .md file** the user pastes into Claude Code

## Key Principles

### File Ownership Prevents Conflicts
Every source file is owned by exactly ONE agent. Other agents can read it but never write. If an agent needs changes in another agent's file, it generates a patch — the orchestrator applies it after the owning agent completes.

### Phases Are Hard Gates
No agent in Phase N+1 starts until ALL Phase N tasks pass their gate checks. Gates are concrete bash commands that return pass/fail. No subjective gates.

### MOE Roles Are Specific
Each agent has a named expertise that determines HOW it approaches problems, not just WHAT files it touches. The MOE role affects code style, error handling patterns, and what the agent prioritizes.

### Status Bars Are Mandatory
After every completed task, the executing agent prints the full sprint status bar. This is the user's only visibility into progress. Never skip it.

## Reference Files

- `references/DISPATCH_TEMPLATE.md` — The parameterized template. Read this first, always.
- `references/STATUS_FORMAT.md` — Status bar format specification and examples.
- `references/EXAMPLES.md` — Example dispatches for common sprint types.
