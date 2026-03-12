# Status Bar Format Specification

## Purpose
The status bar is the user's ONLY visibility into agent progress during Claude Code execution. It must be printed after every task completion — no exceptions.

## Symbol Legend

| Symbol | Meaning | When to Use |
|--------|---------|-------------|
| ✓ | Done | Task completed successfully |
| ▶ | Active | Task currently being worked on |
| ○ | Pending | Task not yet started |
| ✗ | Failed | Task failed (include error before status bar) |
| █ | Progress fill | Filled portion of progress bar |
| ░ | Progress empty | Unfilled portion of progress bar |

## Progress Bar Calculation

```
total_tasks = sum of all tasks across all agents
done_tasks = count of ✓ tasks
active_tasks = count of ▶ tasks
pct = round((done_tasks / total_tasks) * 100)

bar_width = 20 characters
filled = round(pct / 100 * bar_width)
empty = bar_width - filled
bar = "█" * filled + "░" * empty
```

Per-phase calculation is the same but scoped to tasks within that phase.

## Format

```
╔══════════════════════════════════════════════════════════════╗
║  {PROJECT} — {SPRINT} STATUS                                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase {N}: {NAME}          [{bar}] {pct}%                  ║
║    {AGENT}  {icon} {T1} {sym}  {T2} {sym}  ...              ║
║                                                              ║
║  Overall: [{bar}] {pct}%  ({done}/{total} tasks)            ║
║                                                              ║
║  Legend: ✓ done  ▶ active  ○ pending  ✗ failed              ║
╚══════════════════════════════════════════════════════════════╝
```

## Rules

1. **Print after EVERY task** — not just phases or milestones
2. **Show ALL phases** — including future ones (they show all ○)
3. **On failure** — print error details ABOVE the status bar, then the bar with ✗
4. **On gate check** — print the bar showing gate result
5. **Final bar** — on sprint completion, show the complete bar with summary stats

## Scaling

For sprints with many tasks (30+), abbreviate:

```
║    AGENT  ◆ [8/10 ✓, 1 ▶, 1 ○]                             ║
```

For sprints with few tasks (<10), show every task ID individually.

## Agent Icons

Assign each agent a unique Unicode symbol for visual scanning:

```
◆ ⟡ ◈ ⬡ ◇ ○ ◉ ▣ △ ☆
```

Pick icons that are visually distinct from each other. Consistency matters — once assigned, an agent keeps its icon for the entire sprint.
