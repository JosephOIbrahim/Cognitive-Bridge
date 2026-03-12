# Cognitive Bridge MCP Server

A FastMCP server that gives an AI a **compositional mind** — a persistent, layered stage
where assertions accumulate, conflicts surface automatically, and disagreement between AI
and user becomes a generative force rather than a conversational obstacle.

---

## What is This?

Most AI systems treat beliefs as ephemeral conversation state. A claim made in turn 3 is
forgotten or quietly contradicted by turn 30. Cognitive Bridge solves this by implementing
a **composition stage**: a structured, append-only store of epistemic claims (assertions)
with explicit strength ordering, conflict detection, and dependency tracking.

The core concept is borrowed from USD (Universal Scene Description): just as USD layers
override each other in a defined strength order, Cognitive Bridge assertions at different
composition arcs (LOCAL, INHERITS, REFERENCES, etc.) resolve to a winner per topic path
via LIVRPS ordering. Stronger arcs (lower integer) override weaker ones. No assertion is
ever deleted — retracted claims remain in the database, and the composition stage
recomputes winners dynamically on every `resolve()` call.

Version 3.0 elevates the system beyond belief management to **active reasoning** by
embedding formal epistemology directly into the Pydantic schemas. The LLM cannot execute
a tool call without engaging the required thinking — falsifiability conditions, steelman
summaries, rejected alternatives — because those fields are enforced at the schema level,
not by prompt instruction.

---

## The Four Critical Thinking Pillars

**Epistemic causality** — Assertions declare logical dependencies as a DAG; when a root
assumption shifts, all downstream claims are automatically flagged CHALLENGED.

**Popperian falsifiability** — LOCAL assertions (highest strength) must state what
observable condition would prove them wrong; a claim without a falsification condition
is rejected by schema validation.

**Socratic steelman** — Before the AI can formally challenge the user's position, it must
articulate the strongest version of that position; comprehension before critique, enforced
by the tool interface.

**Empirical grounding** — When neither party has data, the protocol can pause abstract
debate and propose a concrete experiment with a measurable threshold to settle the
question objectively.

---

## Key Features

- 8 MCP tools covering the full argumentation lifecycle
- 6 read-only MCP resources exposing stage state (resolved, conflicts, variants, audit,
  dependencies, payloads)
- 3 MCP prompts for posture assessment, conflict negotiation, and stage summaries
- Four-layer conflict detection: structural (same path), semantic (embedding similarity),
  delegated (boomeranged to Claude for evaluation), cascading (DAG propagation)
- LIVRPS composition arc ordering via IntEnum — lower integer wins, no string comparisons
- Non-destructive resolution — assertions accumulate, winners computed dynamically
- Four coworker postures: LEARNING, ENGAGED, AUTHORITATIVE, RED_TEAMING (anti-echo-chamber)
- SQLite storage via SQLModel — no external database required
- JSON capsule export/import for project portability across Cognitive Bridge instances
- Cognitive Operating Signature (COS) kernel: user profiling via naturalistic probes
  tunes conflict sensitivity without changing protocol mechanics
- 831+ tests covering models, engine, tools, and integration scenarios

---

## Quick Start

**Install**

```bash
# Core (no semantic detection)
pip install -e .

# With Layer 2 semantic detection (requires sentence-transformers)
pip install -e ".[semantic]"

# Full install including dev dependencies
pip install -e ".[all]"
```

**Run the server**

```bash
python -m cognitive_bridge.server
```

The server starts in stdio mode, ready for Claude Desktop. Database files are written to
`~/.cognitive_bridge/projects/cognitive_bridge.db` by default.

**First tool call**

```
cb_manage_project(action="create", project_id="my-project", project_name="My Project")
```

All other tools require an active project. Call `cb_manage_project` with `action="load"`
at the start of every session to resume prior state.

---

## Claude Desktop Configuration

Add the following block to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cognitive-bridge": {
      "command": "python",
      "args": ["-m", "cognitive_bridge.server"],
      "env": {
        "CB_DB_DIR": "~/.cognitive_bridge/projects"
      }
    }
  }
}
```

The `CB_DB_DIR` environment variable controls where SQLite database files are stored.
Omit it to use the default (`~/.cognitive_bridge/projects`).

Configuration file locations:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    COGNITIVE BRIDGE MCP v3.0                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               COMPOSITION STAGE (Core)                    │   │
│  │                                                           │   │
│  │  Assertions  ── topic_path  (/architecture/database/...)  │   │
│  │                  arc        (LIVRPS IntEnum — lower wins)  │   │
│  │                  depends_on_paths  (DAG edges)            │   │
│  │                  falsifiable_if   (Popperian condition)   │   │
│  │                  assumption_status (live/challenged/...)  │   │
│  │                                                           │   │
│  │  Conflicts   ── L1: Structural  (same topic_path)        │   │
│  │                  L2: Semantic   (embedding similarity)    │   │
│  │                  L3: Delegated  (boomeranged to Claude)   │   │
│  │                  L4: Cascading  (DAG propagation)         │   │
│  │                                                           │   │
│  │  VariantSets ── Competing hypotheses in parallel          │   │
│  │  Decisions   ── alternatives_rejected + second_order      │   │
│  │  Events      ── Append-only provenance log                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                        │
│  ┌─────────────┐  ┌─────┴──────┐  ┌────────────────────────┐   │
│  │  RESOLUTION  │  │  CONFLICT  │  │  COS KERNEL            │   │
│  │  ENGINE      │  │  DETECTOR  │  │                        │   │
│  │              │  │            │  │  Entropy tolerance     │   │
│  │  LIVRPS sort │  │  L1: Path  │  │  Process purity        │   │
│  │  Per-path    │  │  L2: Embed │  │  Autonomy boundary     │   │
│  │  Shadow stack│  │  L3: LLM   │  │  Energy level          │   │
│  │  DAG cascade │  │  L4: DAG   │  │  -> Tunes sensitivity  │   │
│  └─────────────┘  └────────────┘  └────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         MCP SURFACE (8 Tools, 6 Resources, 3 Prompts)     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  STORAGE:   SQLite via SQLModel  (~/.cognitive_bridge/projects/) │
│  TRANSPORT: stdio (local) | streamable HTTP (remote)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tool Reference

All tools use the `cb_` prefix. Every mutating tool records events to the append-only
audit log and persists the updated stage to SQLite.

| Tool | Actions | Description |
|------|---------|-------------|
| `cb_manage_project` | create, load, save, list, export, import_json | Create or resume a composition stage. Must be called before any other tool. `export` produces a self-contained JSON capsule; `import_json` reconstitutes it. |
| `cb_manage_assertion` | assert, promote, retract, falsify | Record an epistemic claim at a topic path and run full conflict detection. LOCAL arc (10) requires `falsifiable_if`. `falsify` marks a falsification condition as met and cascades ORPHANED status to dependents. |
| `cb_manage_conflict` | resolve, challenge, defer, create, propose_experiment | Act on a detected conflict. `challenge` is a hard gate: requires `steelman_summary`. `propose_experiment` is a hard gate: requires `experiment_protocol`. `create` manually escalates a Layer 3 (delegated) conflict. |
| `cb_manage_variant` | create, add_evidence, resolve | Manage parallel hypothesis exploration. Requires minimum 2 variants on create. `add_evidence` accumulates evidence per variant before `resolve` locks in the winner. |
| `cb_decide` | (single action) | Record a decision with full accountability. `alternatives_rejected` (pipe-separated, min 1) and `second_order_effects` (pipe-separated, min 1) are hard-gated. Second-order effects auto-create INHERITS constraint assertions at the decision path. |
| `cb_tune_parameters` | (single action) | Inspect or update CognitiveParameters. Call with no arguments to read current settings. Tunable knobs: conflict_sensitivity, semantic_threshold, cross_path_detection, exploration_budget, ai_default_arc, payload_surfacing, red_team_threshold, cascade_auto_challenge. |
| `cb_probe_user` | (single action) | Update the COS kernel. Probe types: `entropy`, `process`, `autonomy`, `energy`. Values 0.0–1.0, smoothed via exponential moving average (alpha=0.7). Call at session start and after observable state changes. |
| `cb_payload_check` | (read-only) | Surface active PAYLOADS-arc assertions at or below a given path. Use before `cb_decide` to ensure available evidence has not been ignored. |

### Composition Arcs (LIVRPS)

Lower integer value overrides higher at the same topic path.

| Arc | Value | Meaning |
|-----|-------|---------|
| LOCAL | 10 | Directly observed, highest strength. Requires `falsifiable_if`. |
| INHERITS | 20 | Pattern inherited from parent scope or domain expertise. |
| VARIANT_SET | 30 | One branch of a VariantSet exploration. |
| REFERENCES | 40 | External authoritative source or stated preference. |
| PAYLOADS | 50 | Known unknown — evidence exists but has not been loaded. |
| SPECIALIZES | 60 | Domain-specific override of broader baseline knowledge. |

---

## The Argumentation Protocol

```
User asserts /architecture/database/engine = "MongoDB"  (arc=40, REFERENCES)
        |
        v
cb_manage_assertion(action="assert", topic_path="/architecture/database/engine",
    content="Use MongoDB", arc=40)
        |
        v
Layer 1: Structural conflict detected
  AI had: /architecture/database/engine = "Use PostgreSQL" at arc=20 (INHERITS)
  PostgreSQL wins by arc strength (20 < 40)
  Conflict recorded: cfl_a1b2c3d4e5f6
        |
        v
cb_manage_conflict(action="challenge",
    conflict_id="cfl_a1b2c3d4e5f6",
    steelman_summary="MongoDB's document model eliminates schema migrations
    which is compelling when the data model is still evolving")
        |
  [GATE: steelman_summary required — no summary, no challenge]
        |
        v
Challenge registered. Conflict stays ACTIVE.
        |
        +-- ACCEPT:   PostgreSQL wins. MongoDB overridden by arc strength.
        |
        +-- PROMOTE:  MongoDB promoted to LOCAL with new evidence. Now wins.
        |
        +-- PROPOSE_EXPERIMENT:
        |   "Run write benchmark: 1000 docs/sec for 60s.
        |    If MongoDB p99 < PostgreSQL p99, MongoDB wins."
        |   [GATE: experiment_protocol required]
        |
        +-- SYNTHESIZE -> cb_manage_variant: both options explored in parallel
        |
        +-- DEFER: table it with a stated revisit condition
        |
        +-- DISMISS: false alarm, no real conflict
```

---

## Resources

Six read-only resources expose stage state. All require the project to be loaded via
`cb_manage_project(action="load")`.

| Resource URI | Description |
|-------------|-------------|
| `stage://{project_id}/resolved` | LIVRPS-resolved winners at each topic path, with shadow stacks, negotiation flags, and health issues. |
| `stage://{project_id}/conflicts` | All conflicts grouped by status (active, resolved, deferred). Includes cascade origin path and steelman when present. |
| `stage://{project_id}/variants` | All variant sets with evidence counts per variant and resolution status. |
| `stage://{project_id}/audit` | Event counts by type and the 10 most recent events in the append-only log. |
| `stage://{project_id}/dependencies` | Dependency DAG — assertions with `depends_on_paths` resolved to what currently wins at each dependency. |
| `stage://{project_id}/payloads` | All active PAYLOADS-arc assertions (known unknowns). |

---

## Prompts

Three prompts generate structured guidance from current stage state.

| Prompt | Arguments | Description |
|--------|-----------|-------------|
| `coworker_posture` | `project_id` | Returns current engagement posture (LEARNING / ENGAGED / AUTHORITATIVE / RED_TEAMING) based on assertion count, active conflicts, and the `red_team_threshold` parameter, with behavioral directives for each state. |
| `conflict_negotiation` | `project_id`, `conflict_id` | Presents both positions with arc provenance, lists all available resolution paths, and states the requirements for CHALLENGE and PROPOSE_EXPERIMENT. |
| `stage_summary` | `project_id` | Comprehensive snapshot: key counters, paths requiring attention (same-arc ties, active conflicts, health issues), open variant sets, and current posture label. |

---

## Examples

The `examples/` directory contains three runnable scripts:

`examples/basic_walkthrough.py` — Creates a project, asserts claims at different arcs,
demonstrates `resolve()` output, shows how retracting an assertion changes the winner,
and verifies persistence across a save-reload cycle.

`examples/conflict_scenario.py` — Demonstrates a structural conflict between AI and user
assertions, walks through each resolution path (accept, promote, synthesize, defer), and
shows how SYNTHESIZE produces a VariantSet for parallel hypothesis exploration.

`examples/mongodb_scenario.py` — Full implementation of Blueprint Appendix A: builds a
PostgreSQL-based architecture stage, receives a MongoDB request from the user, triggers
structural conflict and cascade, works through steelman and challenge, proposes a benchmark
experiment, and resolves with a `cb_decide` call that records second-order effects.

```bash
python examples/basic_walkthrough.py
python examples/conflict_scenario.py
python examples/mongodb_scenario.py
```

---

## Development

**Install with dev dependencies**

```bash
pip install -e ".[all]"
```

**Run the test suite**

```bash
# Full suite
pytest tests/ -v

# Skip semantic tests (faster, no sentence-transformers required)
pytest tests/ -v -k "not semantic"

# Run a specific module
pytest tests/test_models/test_assertion.py -v

# Integration tests only
pytest tests/test_integration/ -v
```

**Lint**

```bash
ruff check src/ tests/
```

**Project structure**

```
src/cognitive_bridge/
├── server.py          FastMCP entry point, lifespan, cb_manage_project
├── models/            Pydantic models: Assertion, Conflict, Decision, ...
├── engine/            Conflict detection, resolution, cascade, provenance
├── tools/             MCP tool implementations (one file per tool)
├── resources/         MCP resource endpoints
├── prompts/           MCP prompt templates
└── storage/           SQLModel tables and Pydantic <-> SQLModel converters
```

---

## Architecture Details

**Models layer** (`src/cognitive_bridge/models/`) defines the Pydantic data model.
`CompositionArc` is an IntEnum so arc strength comparisons are integer comparisons with
no string parsing. `Assertion.__lt__` delegates to arc value, making `sorted()` calls on
assertion stacks naturally produce LIVRPS order. Schema validators enforce falsifiability
requirements and dependency path format at construction time.

**Engine layer** (`src/cognitive_bridge/engine/`) contains pure functions operating on
`CompositionStage` instances. `conflict_detector.py` implements Layers 1 and 2.
`resolver.py` runs the full detection pipeline on every assertion mutation and tracks
winner changes that trigger further cascades. `cascade.py` traverses the dependency DAG
to propagate CHALLENGED status when a foundation shifts. `provenance.py` queries the
append-only event log. `sensitivity.py` maps COS kernel dimensions to `CognitiveParameters`
adjustments. `trust.py` computes per-subtree trust scores from conflict resolution history.
`red_team.py` handles RED_TEAMING posture trigger logic.

**Storage layer** (`src/cognitive_bridge/storage/`) maps each Pydantic model to a SQLModel
table. `converters.py` handles bidirectional translation, storing list and dict fields as
JSON columns. All projects share a single SQLite file in `CB_DB_DIR`. The upsert pattern
in `save_stage_to_db` ensures in-memory mutations propagate to disk without dropping any
row, consistent with the non-destructive invariant.

**Server layer** (`src/cognitive_bridge/server.py`) initializes FastMCP with a lifespan
context that creates the SQLite store and an in-memory active stage registry keyed by
`project_id`. Tool modules are imported at module load time so their `@mcp.tool` decorators
bind to the shared `mcp` instance. The server runs in stdio mode by default (Claude Desktop)
and supports streamable HTTP for remote deployments.

---

## Requirements

- Python 3.11+
- `fastmcp >= 2.0.0`
- `sqlmodel >= 0.0.22`
- `pydantic >= 2.0`
- Optional: `sentence-transformers >= 3.0` and `numpy >= 1.24` for Layer 2 semantic
  conflict detection

---

## The Novel Claim

Cognitive Bridge implements a formal argumentation framework as hierarchical composition
arcs applied to AI epistemic state, incorporating dependency-aware causal reasoning (DAG),
Popperian falsifiability requirements, mandatory intellectual charity (steelman) gates,
and empirical grounding protocols, where AI-user disagreement is a first-class composition
event with explicit strength ordering, non-destructive resolution, and conflict-driven
parallel exploration of solution spaces.

Dependent claims:

1. Composition stage as persistent AI reasoning state — accumulated layered assertions
   constitute the AI's perspective, structurally distinct from conversation history.
2. Hierarchical topic paths (prim paths) as assertion addressing — enabling structural
   conflict detection without NLP.
3. LIVRPS-ordered resolution with IntEnum strength — non-destructive shadow stacks.
4. Four-layer conflict detection — structural, semantic, delegated, and cascading (DAG
   propagation).
5. Epistemic dependency DAG — assertions declare logical dependencies; foundation shifts
   cascade automatically through the reasoning graph.
6. Popperian falsifiability as schema constraint — highest-strength assertions must define
   their own falsification conditions; claims without falsifiability are structurally
   rejected.
7. Socratic steelman as protocol gate — contesting an opposing view requires first
   articulating its strongest form, enforced by schema validation.
8. Empirical grounding protocol — conflicts can be paused and resolved via concrete
   experiments rather than abstract debate.
9. Decision impact mapping — decisions require enumeration of rejected alternatives and
   second-order downstream effects, with automatic constraint propagation.
10. Anti-echo-chamber mechanism — highly stable stages with zero conflicts trigger
    adversarial self-examination (RED_TEAMING).
11. Cognitive Operating Signature integration — user profiling via naturalistic probes
    tunes protocol sensitivity without changing mechanics.

Full architectural specification: `docs/blueprint-v3.md`

---

## License

MIT
