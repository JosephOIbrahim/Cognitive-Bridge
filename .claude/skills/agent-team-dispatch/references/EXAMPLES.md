# Examples: Common Sprint Patterns

## How to Use

These are copy-paste starters. Pick the pattern closest to your sprint,
fill in the blanks, paste into Claude Code.

---

## Pattern 1: Feature Build (3 agents, 2 phases)

Use for: Adding a new feature to an existing codebase.
Agents: Backend, Frontend, Test.

```markdown
# {PROJECT} — {FEATURE} Sprint

## PRE-FLIGHT
```bash
cat CLAUDE.md                    # Project conventions
cat {main_source_file}           # Understand current code
ls {directory}/                  # See what exists
pytest tests/ -q --tb=short      # Baseline: all green
```

Report findings. Do NOT proceed until you understand existing patterns.

## STATUS BAR — Print after EVERY task

╔══════════════════════════════════════════════════════════════╗
║  {PROJECT} — {FEATURE} STATUS                               ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: BUILD               [░░░░░░░░░░]  0%              ║
║    BACK   ◆ B1 ○  B2 ○  B3 ○                                ║
║    FRONT  ◈ F1 ○  F2 ○  F3 ○                                ║
║                                                              ║
║  Phase 2: TEST + WIRE         [░░░░░░░░░░]  0%              ║
║    WIRE   ◇ W1 ○  W2 ○                                      ║
║    TEST   ○ X1 ○  X2 ○  X3 ○                                ║
║                                                              ║
║  Overall: [░░░░░░░░░░░░░░░░░░░░]  0%  (0/11 tasks)         ║
║  Legend: ✓ done  ▶ active  ○ pending  ✗ failed              ║
╚══════════════════════════════════════════════════════════════╝

## FILE OWNERSHIP
| Agent | MOE Role | Exclusive Write | Read Only |
|-------|----------|-----------------|-----------|
| BACK  | {domain} Backend Expert | {backend_files} | frontend, tests |
| FRONT | UI/UX Implementation Expert | {frontend_files} | backend, tests |
| WIRE  | Integration Engineer | {integration_files} | back, front |
| TEST  | Test Coverage Expert | tests/{test_files} | everything |

## PHASE 1: BUILD (parallel)

### Agent BACK — {domain} Backend Expert
You OWN: {backend_files}
DO NOT TOUCH: {frontend_files}, tests/

Task B1: {first_backend_task}
{implementation details}

Task B2: {second_backend_task}
{implementation details}

Task B3: {third_backend_task}
{implementation details}

### Agent FRONT — UI/UX Implementation Expert
You OWN: {frontend_files}
DO NOT TOUCH: {backend_files}, tests/

Task F1: {first_frontend_task}
{implementation details}

Task F2: {second_frontend_task}
{implementation details}

Task F3: {third_frontend_task}
{implementation details}

### PHASE 1 GATE
```bash
# Backend imports clean
python -c "from {module} import {new_class}; print('Backend: OK')"

# Frontend imports clean  
python -c "from {module} import {new_widget}; print('Frontend: OK')"

# Zero regressions
pytest tests/ -q --tb=short
```
ALL must pass. Fix before Phase 2.

## PHASE 2: TEST + WIRE (parallel)

### Agent WIRE — Integration Engineer
You OWN: {integration_files}
DEPENDS ON: BACK, FRONT

Task W1: Wire backend to frontend
{implementation details}

Task W2: Register in {main_registry}
{implementation details}

### Agent TEST — Test Coverage Expert
You OWN: tests/{test_files}

Task X1: Unit tests for backend
Task X2: Unit tests for frontend  
Task X3: E2E integration test

### PHASE 2 GATE (FINAL)
```bash
pytest tests/ -q --tb=short
python -c "from {module} import *; print('All imports: OK')"
```

## SAFETY RULES
1. Read before write — match existing conventions
2. File ownership — NEVER write to another agent's files
3. Regression zero — existing tests must keep passing
4. Status bar — print after EVERY task
```

---

## Pattern 2: Refactor Sprint (4 agents, 3 phases)

Use for: Restructuring existing code without changing behavior.
Agents: Analyst, Mover, Updater, Verifier.

```markdown
# {PROJECT} — {REFACTOR_NAME} Sprint

## PRE-FLIGHT
```bash
cat CLAUDE.md
find {directory} -name "*.py" | head -20  # Map the territory
pytest tests/ -q                           # Baseline green
```

## STATUS BAR — Print after EVERY task

╔══════════════════════════════════════════════════════════════╗
║  {PROJECT} — {REFACTOR} STATUS                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: ANALYZE             [░░░░░░░░░░]  0%              ║
║    ANALYST ◆ A1 ○  A2 ○                                     ║
║                                                              ║
║  Phase 2: RESTRUCTURE         [░░░░░░░░░░]  0%              ║
║    MOVER  ⟡ M1 ○  M2 ○  M3 ○                               ║
║    UPDATE ◈ U1 ○  U2 ○  U3 ○                                ║
║                                                              ║
║  Phase 3: VERIFY              [░░░░░░░░░░]  0%              ║
║    VERIFY ○ V1 ○  V2 ○  V3 ○                                ║
║                                                              ║
║  Overall: [░░░░░░░░░░░░░░░░░░░░]  0%  (0/11 tasks)         ║
║  Legend: ✓ done  ▶ active  ○ pending  ✗ failed              ║
╚══════════════════════════════════════════════════════════════╝

## FILE OWNERSHIP
| Agent | MOE Role | Exclusive Write | Read Only |
|-------|----------|-----------------|-----------|
| ANALYST | Code Archaeology Expert | docs/{analysis}.md | everything |
| MOVER | File Structure Expert | {source_files} | tests, docs |
| UPDATE | Import/Reference Expert | {dependent_files} | source, tests |
| VERIFY | Regression Expert | tests/ | everything |

## PHASE 1: ANALYZE (sequential — one agent)

### Agent ANALYST — Code Archaeology Expert
Task A1: Map all cross-file dependencies for {target_module}
Task A2: Generate move plan with old_path → new_path table

### PHASE 1 GATE
```bash
test -f docs/{analysis}.md && echo "Analysis: OK"
```

## PHASE 2: RESTRUCTURE (parallel)

### Agent MOVER — File Structure Expert
Task M1: Create new directory structure
Task M2: Move files per the move plan
Task M3: Update __init__.py exports

### Agent UPDATE — Import/Reference Expert
Task U1: Update all imports referencing moved files
Task U2: Update config files / registries
Task U3: Update documentation paths

### PHASE 2 GATE
```bash
python -c "import {package}; print('Package: OK')"
pytest tests/ -q --tb=short
```

## PHASE 3: VERIFY (sequential)

### Agent VERIFY — Regression Expert
Task V1: Run full test suite, report any failures
Task V2: Verify no circular imports
Task V3: Verify no dead imports (unused)

### PHASE 3 GATE (FINAL)
```bash
pytest tests/ -q --tb=short
python -c "import {package}; print('Clean import: OK')"
# Verify no test was accidentally deleted
test $(find tests/ -name "test_*.py" | wc -l) -ge {expected_test_count}
```
```

---

## Pattern 3: Knowledge Expansion (2 agents, 2 phases)

Use for: Adding RAG entries, documentation, or knowledge base content.
Agents: Researcher, Integrator.

```markdown
# {PROJECT} — {KNOWLEDGE_AREA} Knowledge Sprint

## PRE-FLIGHT
```bash
ls {rag_directory}/                # Existing knowledge
wc -l {rag_directory}/*.md         # Current coverage
cat {routing_file}                 # How knowledge is accessed
```

## STATUS BAR — Print after EVERY task

╔══════════════════════════════════════════════════════════════╗
║  {PROJECT} — {KNOWLEDGE} STATUS                             ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Phase 1: EXTRACT             [░░░░░░░░░░]  0%              ║
║    RESEARCH ◆ R1 ○  R2 ○  R3 ○  R4 ○                       ║
║                                                              ║
║  Phase 2: INTEGRATE           [░░░░░░░░░░]  0%              ║
║    INTEGRATE ◈ I1 ○  I2 ○  I3 ○                             ║
║                                                              ║
║  Overall: [░░░░░░░░░░░░░░░░░░░░]  0%  (0/7 tasks)          ║
║  Legend: ✓ done  ▶ active  ○ pending  ✗ failed              ║
╚══════════════════════════════════════════════════════════════╝

(fill in agents and tasks as above)
```

---

## Pattern 4: Bug Fix Sprint (3 agents, 2 phases)

Use for: Fixing multiple related bugs in a focused sprint.
Agents: Diagnostician, Surgeon, Validator.

Phase 1: DIAGNOSE — Diagnostician reads code, writes root cause analysis
Phase 2: FIX + VALIDATE — Surgeon fixes (parallel with) Validator writing tests

---

## Pattern 5: Migration Sprint (4 agents, 3 phases)

Use for: Migrating from one system/API/framework to another.
Agents: Mapper, Builder, Migrator, Validator.

Phase 1: MAP — Mapper analyzes old + new APIs, builds translation table
Phase 2: BUILD — Builder creates new implementation, Migrator updates callsites
Phase 3: VALIDATE — Validator runs comparative tests old vs new

---

## Choosing Your Pattern

| Situation | Pattern | Why |
|-----------|---------|-----|
| Adding a feature | Feature Build | Clean backend/frontend/test split |
| Restructuring code | Refactor | Analyze-first prevents breakage |
| Adding docs/RAG | Knowledge | Research then integrate |
| Fixing bugs | Bug Fix | Diagnose before cutting |
| Swapping dependencies | Migration | Map before you move |
| Custom | Start from DISPATCH_TEMPLATE.md | Build your own |

## Sizing Guide

| Sprint Size | Agents | Phases | Tasks | Estimated Time |
|-------------|--------|--------|-------|----------------|
| Small | 2-3 | 2 | 5-10 | 15-30 min |
| Medium | 3-5 | 2-3 | 10-20 | 30-60 min |
| Large | 5-7 | 3-4 | 20-35 | 1-2 hours |
| XL | 6+ | 4+ | 35+ | 2+ hours (consider splitting) |

If you're over 35 tasks, consider splitting into two sequential sprints.
