# Agent Team Dispatch Template
# ════════════════════════════════════════════════════════════════
# 
# HOW TO USE THIS TEMPLATE:
#   1. Replace all {{PLACEHOLDERS}} with project-specific values
#   2. Define your agents in the AGENT ROSTER section
#   3. Define phases with gate checks
#   4. Fill in task implementations for each agent
#   5. Copy the filled template into Claude Code
#
# The template produces a SELF-CONTAINED prompt. Claude Code needs
# nothing else — no external files, no prior context.
#
# ════════════════════════════════════════════════════════════════


# {{PROJECT_NAME}} — Agent Team Dispatch
# Sprint: {{SPRINT_NAME}}
# Date: {{DATE}}
# Status: READY TO EXECUTE

---

## PRE-FLIGHT: Read Before Anything

Before ANY implementation, read these files and internalize their conventions:

```bash
{{#each PRE_FLIGHT_READS}}
cat {{this}}
{{/each}}
```

Report what you find. Do NOT proceed until you understand:
{{#each PRE_FLIGHT_CHECKLIST}}
- {{this}}
{{/each}}

---

## STATUS REPORTING PROTOCOL

**MANDATORY:** After completing each task, print the status bar in this EXACT format.
This is the user's ONLY visibility into progress. Never skip it.

```
╔══════════════════════════════════════════════════════════════╗
║  {{PROJECT_NAME}} — {{SPRINT_NAME}} STATUS                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
{{#each PHASES}}
║  Phase {{this.num}}: {{this.name}}  [{{this.bar}}] {{this.pct}}%  ║
{{#each this.agents}}
║    {{this.name}}  {{this.icon}} {{#each this.tasks}}{{this.id}} {{this.symbol}}  {{/each}}  ║
{{/each}}
║                                                              ║
{{/each}}
║  Overall: [{{overall_bar}}] {{overall_pct}}%  ({{done}}/{{total}} tasks) ║
║                                                              ║
║  Legend: ✓ done  ▶ active  ○ pending  ✗ failed              ║
╚══════════════════════════════════════════════════════════════╝
```

**Rules:**
- Print after EVERY completed task (not just phases)
- Update symbols: ○ → ▶ (when starting) → ✓ (when done) or ✗ (on failure)
- Calculate percentages: done_tasks / total_tasks × 100
- If a task FAILS (✗), report the error message before the status bar

---

## ARCHITECTURE DECISIONS (NON-NEGOTIABLE)

{{#each ARCHITECTURE_DECISIONS}}
### {{this.title}}
{{this.description}}

```
{{this.diagram}}
```
{{/each}}

---

## FILE OWNERSHIP TABLE

**Every file has exactly ONE owner. Violation = merge conflicts = sprint failure.**

| Agent | Role (MOE) | Exclusive Write | Read Only |
|-------|------------|-----------------|-----------|
{{#each AGENTS}}
| {{this.name}} | {{this.moe_role}} | {{this.owns}} | {{this.reads}} |
{{/each}}

**Patch protocol:** If Agent A needs a change in Agent B's file:
1. Agent A writes the change to a `.patch` description in their task output
2. Orchestrator applies the patch after Agent B's current task completes
3. Agent B's next task incorporates the change

---

{{#each PHASES}}
## PHASE {{this.num}}: {{this.name}}

{{this.description}}

Run these agents {{this.execution_mode}} via Task tool.

{{#each this.agents}}
### ═══ Agent {{this.name}} — {{this.moe_role}} ═══

**MOE Expertise:** {{this.moe_description}}
**You OWN:** {{this.owns}}
**DO NOT TOUCH:** {{this.do_not_touch}}
{{#if this.depends_on}}
**DEPENDS ON:** {{this.depends_on}}
{{/if}}

{{#each this.tasks}}
**Task {{this.id}}: {{this.title}}**

{{this.implementation}}

{{/each}}

After completing all tasks, print the status bar.

---

{{/each}}

### ═══ PHASE {{this.num}} GATE ═══

**Run BEFORE starting Phase {{this.next_phase}}. Gate is HARD — no skip.**

```bash
{{this.gate_commands}}
```

**ALL checks must pass. If ANY fail, fix before proceeding.**

Print status bar after gate check.

---

{{/each}}

## FINAL STATUS BAR

Print after the last phase gate passes:

```
╔══════════════════════════════════════════════════════════════╗
║  {{PROJECT_NAME}} — {{SPRINT_NAME}} — COMPLETE              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
{{#each PHASES}}
║  Phase {{this.num}}: {{this.name}}  [██████████] 100% ✓     ║
{{#each this.agents}}
║    {{this.name}}  {{this.icon}} {{#each this.tasks}}{{this.id}} ✓  {{/each}}  ║
{{/each}}
║                                                              ║
{{/each}}
║  Overall: [████████████████████] 100%  ({{total}}/{{total}} tasks) ║
║                                                              ║
║  New files:    {{NEW_FILES}}                                  ║
║  Modified:     {{MODIFIED_FILES}}                             ║
║  Tests added:  {{TEST_FILES}}                                 ║
║  Regressions:  0                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## SAFETY RULES (ALL AGENTS — NON-NEGOTIABLE)

{{#each SAFETY_RULES}}
{{@index}}. **{{this.name}}:** {{this.description}}
{{/each}}

### Universal Safety (always include these):
1. **Read before write:** Always read existing code and match conventions
2. **File ownership:** NEVER write to another agent's files
3. **Regression zero:** Existing tests must keep passing
4. **Status reporting:** Print status bar after EVERY task completion
