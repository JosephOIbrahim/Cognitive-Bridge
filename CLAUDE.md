# Cognitive Bridge MCP Server

## Project Identity
- **Name:** cognitive-bridge
- **Package:** `cognitive_bridge_mcp`  
- **Purpose:** FastMCP server implementing USD-inspired LIVRPS composition arcs as a formal argumentation framework for AI critical thinking
- **Language:** Python 3.11+
- **Key Dependencies:** `fastmcp`, `sqlmodel`, `pydantic>=2.0`, `sentence-transformers`
- **Transport:** stdio (Claude Desktop) / streamable HTTP (remote)
- **Blueprint:** See `docs/blueprint-v3.md` for the complete architectural specification

## Architecture Overview

This is NOT a standard CRUD server. It implements a **compositional mind** where:
- Assertions are epistemic claims with hierarchical topic paths (USD prim paths)
- Composition arcs (LIVRPS) determine strength ordering via IntEnum
- Conflicts are first-class composition events, not errors
- A dependency DAG enables cascading re-evaluation when foundations shift
- Popperian falsifiability is enforced by schema validation on LOCAL assertions
- Steelman summaries are required before challenges (Pydantic enforces this)

**Critical invariant:** No assertion is ever deleted. Retracted assertions stay in the DB. The composition stage is non-destructive — "winning" is computed dynamically via `resolve()`, not by overwriting.

## Code Conventions

### Python Style
- Type hints on every function signature and return value
- Pydantic v2 patterns: `model_config`, `field_validator`, `model_validator`, `model_dump()`
- `async def` for all tool implementations
- Constants in UPPER_SNAKE_CASE at module level
- Docstrings on every class and public function
- Imports grouped: stdlib → third-party → local

### Naming
- Files: `snake_case.py`
- Classes: `PascalCase`  
- Functions: `snake_case`
- MCP tool names: `cb_{verb}_{noun}` (e.g., `cb_manage_assertion`)
- Topic paths: lowercase, forward-slash separated, no trailing slash (e.g., `/architecture/database/engine`)
- IDs: `{prefix}_{uuid_hex[:12]}` (e.g., `ast_4f8a2c1b9e03`)

### Testing
- pytest with async support (`pytest-asyncio`)
- Test files mirror src structure: `tests/test_models/test_assertion.py` → `src/cognitive_bridge/models/assertion.py`
- Every model validator MUST have a test that triggers it
- Integration tests use in-memory SQLite (`:memory:`)
- Each test is independent — no shared mutable state between tests

### Commits
- Atomic: one logical unit per commit
- Format: `[phase.task] description` (e.g., `[P0.T2] implement Assertion model with falsifiability validator`)
- Tests included in same commit as the code they test

## Directory Structure

```
cognitive-bridge/
├── CLAUDE.md                          ← You are here
├── pyproject.toml
├── docs/
│   └── blueprint-v3.md               ← Full architectural specification
├── src/
│   └── cognitive_bridge/
│       ├── __init__.py
│       ├── server.py                  # FastMCP entry point + lifespan
│       ├── models/
│       │   ├── __init__.py            # Re-exports all models
│       │   ├── arcs.py                # CompositionArc (IntEnum), enums
│       │   ├── assertion.py           # Assertion + validators
│       │   ├── conflict.py            # Conflict, ConflictStatus, ResolutionPath
│       │   ├── variant_set.py         # VariantSet, Variant
│       │   ├── event.py               # Event, EventType
│       │   ├── decision.py            # Decision (v3.0 with 2nd-order effects)
│       │   ├── parameters.py          # CognitiveParameters
│       │   ├── kernel.py              # Individual Kernel (COS)
│       │   └── stage.py               # CompositionStage + resolve() + DAG
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── conflict_detector.py   # Layers 1-4 detection
│       │   ├── resolver.py            # LIVRPS resolution + shadow stacks
│       │   ├── cascade.py             # DAG traversal + cascading conflicts
│       │   └── provenance.py          # Event log + audit trail
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── assertion_tool.py      # cb_manage_assertion
│       │   ├── conflict_tool.py       # cb_manage_conflict
│       │   ├── variant_tool.py        # cb_manage_variant
│       │   ├── project_tool.py        # cb_manage_project
│       │   ├── parameters_tool.py     # cb_tune_parameters
│       │   ├── decision_tool.py       # cb_decide
│       │   ├── probe_tool.py          # cb_probe_user
│       │   └── payload_tool.py        # cb_payload_check
│       ├── resources/
│       │   ├── __init__.py
│       │   └── stage_resources.py     # MCP resource endpoints
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── negotiation_prompts.py # coworker_posture, conflict_negotiation, stage_summary
│       └── storage/
│           ├── __init__.py
│           ├── sqlite_store.py        # SQLModel tables + CRUD
│           └── converters.py          # Pydantic ↔ SQLModel conversion
├── tests/
│   ├── conftest.py                    # Fixtures: in-memory SQLite, test stages
│   ├── test_models/
│   ├── test_engine/
│   ├── test_tools/
│   └── test_integration/
└── examples/
    ├── basic_walkthrough.py
    ├── conflict_scenario.py
    └── mongodb_scenario.py            # The full v3.0 showcase
```

---

## Agent Orchestration

### Routing Rules

When delegating tasks, use these routing rules to select the right subagent:

| Task Pattern | Route To | Run Mode |
|---|---|---|
| Pydantic models, enums, validators, SQLModel tables | `schema-architect` | Background OK |
| Conflict detection, resolution, DAG traversal, cascading | `engine-developer` | Background OK |
| MCP tools, resources, prompts, server.py, FastMCP wiring | `surface-developer` | Sequential (depends on models + engine) |
| pytest files, fixtures, test scenarios | `test-engineer` | Background OK (after code exists) |
| End-to-end scenarios, README, examples, config guides | `integration-validator` | Sequential (last) |

### Parallel Execution Rules

**CAN run in parallel** (no write conflicts):
- Schema Architect + Engine Developer (different directories)
- Multiple Test Engineer instances (different test files)
- Test Engineer + Integration Validator (different directories)

**MUST run sequentially:**
- Schema Architect → Engine Developer (engine imports models)
- Schema Architect + Engine Developer → Surface Developer (tools import both)
- All code → Test Engineer (tests import implementation)
- Everything → Integration Validator (end-to-end needs everything)

### Invocation Protocol

Every subagent dispatch MUST include:
1. **Scope:** Exact files to create/modify
2. **Blueprint Reference:** Which blueprint section applies
3. **Dependencies:** What must exist before this task starts
4. **Output Contract:** What the subagent delivers
5. **Validation:** How to verify the output is correct

Example:
```
Task: Schema Architect — Build Assertion model
Scope: src/cognitive_bridge/models/assertion.py
Blueprint: Section 3.3 (Assertion Model)
Dependencies: arcs.py must exist (CompositionArc, AssertionAuthor, EvidenceType enums)
Output: Assertion class with __lt__, falsifiability validator, dependency validator
Validation: pytest tests/test_models/test_assertion.py passes
```

---

## Build Execution Plan (Task DAG)

### Phase 0: Foundation (Tasks P0.T1 – P0.T8)

```
P0.T1: Project scaffolding ──────────────────────────────────── [orchestrator]
  │    pyproject.toml, src layout, __init__.py files, conftest.py
  │
  ├──► P0.T2: Core enums (arcs.py) ──────────────────────────── [schema-architect]
  │    CompositionArc(IntEnum), AssertionAuthor, EvidenceType, 
  │    AssumptionStatus, ConflictStatus, ResolutionPath,
  │    ConflictDetectionLayer, EventType
  │      │
  │      ├──► P0.T3: Assertion model ─────────────────────────── [schema-architect]
  │      │    Assertion + __lt__ + falsifiability validator + 
  │      │    dependency validator + tests
  │      │      │
  │      ├──► P0.T4: Conflict + VariantSet + Event models ───── [schema-architect] 
  │      │    Conflict, Variant, VariantSet, Event + tests
  │      │    (can parallel with P0.T3)
  │      │      │
  │      └──► P0.T5: Decision + Parameters + Kernel models ──── [schema-architect]
  │           Decision (w/ alternatives_rejected, second_order_effects),
  │           CognitiveParameters, IndividualKernel + tests
  │
  ├──► P0.T6: CompositionStage ───────────────────────────────── [schema-architect]
  │    (depends on P0.T3, P0.T4, P0.T5)
  │    resolve(), get_dependents(), get_dependency_chain(), 
  │    get_subtree(), record_event() + tests
  │
  ├──► P0.T7: SQLModel tables + storage ──────────────────────── [schema-architect]
  │    (depends on P0.T3, P0.T4, P0.T5)
  │    AssertionRow, ConflictRow, VariantSetRow, EventRow,
  │    DecisionRow, ParametersRow, KernelRow, converters.py + tests
  │
  └──► P0.T8: Minimal server.py ──────────────────────────────── [surface-developer]
       (depends on P0.T6, P0.T7)
       FastMCP init, lifespan, cb_manage_project (create/load/save/list)
       Verify: server starts via `python -m cognitive_bridge.server`
```

**Phase 0 Quality Gate:** All models compile. `resolve()` returns correct LIVRPS ordering. SQLite creates tables. Server starts and responds to project management calls. `pytest tests/test_models/` passes.

### Phase 1: Conflict Protocol (Tasks P1.T1 – P1.T8)

```
P1.T1: Layer 1 structural conflict detection ─────────────────── [engine-developer]
  │    detect_structural_conflict() in engine/conflict_detector.py
  │    + tests
  │
P1.T2: Layer 4 cascading conflict detection ──────────────────── [engine-developer]
  │    (can parallel with P1.T1)
  │    detect_cascading_conflicts(), check_falsification()
  │    in engine/cascade.py + tests
  │
P1.T3: Resolution engine ────────────────────────────────────── [engine-developer]
  │    (depends on P1.T1, P1.T2)
  │    LIVRPS resolution with shadow stacks, winner tracking,
  │    cascade trigger on winner change + tests
  │
P1.T4: Provenance engine ────────────────────────────────────── [engine-developer]
  │    (can parallel with P1.T1-T3)
  │    Event log append, audit trail queries + tests
  │
P1.T5: cb_manage_assertion tool ──────────────────────────────── [surface-developer]
  │    (depends on P1.T1, P1.T2, P1.T3)
  │    assert + promote + retract + falsify actions
  │    Structural + cascading detection integrated
  │    Semantic warnings in response text
  │
P1.T6: cb_manage_conflict tool ───────────────────────────────── [surface-developer]
  │    (depends on P1.T3)
  │    resolve + challenge (w/ steelman gate) + defer + create +
  │    propose_experiment (w/ protocol gate)
  │
P1.T7: cb_manage_variant tool ───────────────────────────────── [surface-developer]
  │    (can parallel with P1.T6)
  │    create + add_evidence + resolve actions
  │
P1.T8: MCP Resources + Prompts ──────────────────────────────── [surface-developer]
       (depends on P1.T5, P1.T6)
       stage_resources.py (resolved, conflicts, variants, audit, 
       dependencies, payloads), coworker_posture prompt (all 4 states),
       conflict_negotiation prompt, stage_summary prompt
```

**Phase 1 Quality Gate:** Full Assert→Detect→Steelman→Challenge→Resolve flow works. Cascading conflicts propagate through DAG. Steelman and experiment protocol gates reject invalid inputs. Resources return formatted state. `pytest tests/test_engine/ tests/test_tools/` passes.

### Phase 2: Decisions + Semantic + Payloads (Tasks P2.T1 – P2.T5)

```
P2.T1: cb_decide tool ───────────────────────────────────────── [surface-developer]
  │    Decision with alternatives_rejected, second_order_effects,
  │    auto-constraint creation, payload warning
  │
P2.T2: Layer 2 semantic detection ───────────────────────────── [engine-developer]
  │    (can parallel with P2.T1)
  │    sentence-transformers embedding, cosine similarity,
  │    threshold-based warnings + tests
  │
P2.T3: Layer 3 delegated pattern ─────────────────────────────── [engine-developer]
  │    (depends on P2.T2)
  │    Semantic warnings formatted in tool response text
  │    for Claude to evaluate
  │
P2.T4: cb_tune_parameters tool ──────────────────────────────── [surface-developer]
  │    (can parallel with P2.T1)
  │    All CognitiveParameters knobs exposed
  │
P2.T5: cb_payload_check tool ────────────────────────────────── [surface-developer]
       (depends on P2.T1)
       Surface pending Payloads at/below a path,
       auto-warning before decisions
```

**Phase 2 Quality Gate:** Decisions require alternatives + second-order effects (Pydantic validates). Semantic detection flags high-similarity cross-path assertions. Delegated warnings appear in tool response text. Parameters tuning affects detection behavior. Payloads surface before decisions. `pytest tests/` all passes.

### Phase 3: COS + Adaptation (Tasks P3.T1 – P3.T4)

```
P3.T1: cb_probe_user tool ───────────────────────────────────── [surface-developer]
  │    Entropy, process, autonomy, energy probes
  │    Kernel stored in SQLite singleton row
  │
P3.T2: Sensitivity auto-tuning ──────────────────────────────── [engine-developer]
  │    (depends on P3.T1)
  │    Kernel dimensions → CognitiveParameters mapping
  │
P3.T3: Trust calibration ────────────────────────────────────── [engine-developer]
  │    (depends on Phase 1 conflict resolution history)
  │    Per-subtree trust scores from resolution outcomes
  │
P3.T4: RED_TEAMING auto-trigger ─────────────────────────────── [engine-developer]
       (depends on P3.T2)
       Posture escalation when stage too stable
       Devil's advocate VariantSet generation
```

**Phase 3 Quality Gate:** Kernel updates from probes. Sensitivity adapts to kernel values. Trust scores computed per topic subtree. RED_TEAMING triggers when conditions met.

### Phase 4: Polish + Integration (Tasks P4.T1 – P4.T6)

```
P4.T1: Project export/import ────────────────────────────────── [surface-developer]
  │    SQLite → JSON capsule → SQLite round-trip
  │
P4.T2: Integration test suite ───────────────────────────────── [test-engineer]
  │    (depends on ALL prior phases)
  │    End-to-end: MongoDB scenario from blueprint appendix
  │    End-to-end: cold start → AUTHORITATIVE → RED_TEAMING
  │
P4.T3: Examples ──────────────────────────────────────────────── [integration-validator]
  │    basic_walkthrough.py, conflict_scenario.py, mongodb_scenario.py
  │
P4.T4: Claude Desktop configuration guide ───────────────────── [integration-validator]
  │    How to install, configure, and use with Claude Desktop
  │
P4.T5: README ────────────────────────────────────────────────── [integration-validator]
  │    Architecture overview, quickstart, patent alignment
  │
P4.T6: Performance profiling ────────────────────────────────── [test-engineer]
       Conflict detection latency benchmarks
       Stage resolution at 50/100/500 assertions
```

**Phase 4 Quality Gate:** Full test suite passes. Examples run. Server starts and handles the MongoDB scenario correctly. README is accurate.

---

## Quality Standards

### Every Model Must Have
- [ ] Type hints on all fields
- [ ] Docstring explaining purpose
- [ ] Pydantic validators for business rules
- [ ] `__lt__` if sortable
- [ ] Corresponding SQLModel table
- [ ] Converter functions (Pydantic ↔ SQLModel)
- [ ] Unit tests for validators (especially error cases)

### Every Tool Must Have
- [ ] Pydantic input model with Field descriptions
- [ ] Tool annotations (readOnlyHint, destructiveHint, etc.)
- [ ] Aggressive behavioral description (what Claude MUST do)
- [ ] Error messages that guide toward correct usage
- [ ] Event log recording on every mutation
- [ ] Response that surfaces conflicts/warnings/cascades
- [ ] Integration test for the happy path
- [ ] Integration test for validation rejection (e.g., LOCAL without falsifiable_if)

### Every Engine Function Must Have
- [ ] Pure function where possible (stage in, result out)
- [ ] Type hints + docstring
- [ ] Unit tests with edge cases
- [ ] No side effects on the stage unless explicitly documented

---

## Reference: Blueprint v3.0 Key Sections

When implementing, reference these blueprint sections:

| Section | Content |
|---------|---------|
| 3.1 | CompositionArc IntEnum with spaced values |
| 3.2 | Topic path conventions (prim paths) |
| 3.3 | Assertion model with v3.0 critical thinking fields |
| 3.4 | Conflict model with steelman, experiment, cascade fields |
| 3.5 | VariantSet model |
| 3.6 | Decision model with alternatives + second-order effects |
| 3.7 | Event log types |
| 3.8 | CognitiveParameters |
| 3.9 | CompositionStage with resolve() + DAG methods |
| 4.1-4.5 | Four-layer conflict detection engine |
| 5.1-5.3 | Argumentation protocol flow + authority levels |
| 6.1-6.5 | MCP tools, resources, prompts (full implementation specs) |
| 7.1 | SQLite schema |
| Appendix A | MongoDB scenario (end-to-end test case) |
