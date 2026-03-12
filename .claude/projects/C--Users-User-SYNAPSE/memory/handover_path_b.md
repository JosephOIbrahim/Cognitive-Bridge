# Path B Handover — Agent Team Architecture

## Session Date: 2026-03-06

## What Was Done
- Full demo readiness audit of Synapse MCP server (108 tools, Streamable HTTP, all 8 demo steps confirmed ready)
- Strategic options analysis (Path A: productize, Path B: agent team, Path C: FORGE flywheel)
- User chose Path B: complete Agent Team Architecture (Phases 4-6)
- Deep read of all shared/ files: types.py (250L), bridge.py (778L), evolution.py (~600L), router.py (272L)
- Read agent_state.py (254L) — the v0.1 that Phase 4 upgrades
- Detailed execution plan created

## Current State of Agent Team

### Built (Phases 1-3)
- `shared/types.py` — AgentID, TaskSpec, ExecutionResult, RoutingFeatures, NodeManifest, GeoSummary, ChainSpec, FILE_OWNERSHIP
- `shared/bridge.py` — LosslessExecutionBridge with all 4 anchors (undo, thread, consent, integrity), R1/R2/R4/R7/R8, AgentHandoff, EmergencyProtocol
- `shared/evolution.py` — Charmander->Charmeleon->Charizard memory evolution, R3/R10
- `shared/router.py` — MOERouter with extract_features(), FAST_PATHS, session learning, R5 word-boundary matching
- `agents/*.md` — 6 agent definition files (SUBSTRATE, BRAINSTEM, OBSERVER, HANDS, CONDUCTOR, INTEGRATOR)
- `python/synapse/memory/agent_state.py` — v0.1.0 basic: tasks, sessions, verification_log

### Not Built (Phases 4-6)

#### Phase 4: agent.usd Schema v2.0.0
**Owner:** HANDS (primary), CONDUCTOR (advisory)
**File to modify:** `python/synapse/memory/agent_state.py`
**New test:** `tests/test_agent_state_v2.py`

Missing prims to add:
- `/SYNAPSE/agent/integrity/` — session_fidelity (Float), operations_total (Int), operations_verified (Int), anchor_violations (Int)
- `/SYNAPSE/agent/routing_log/decision_NNNN` — fingerprint (String), primary_agent (String), advisory_agent (String), method (String), timestamp (String)
- `/SYNAPSE/agent/handoff_chain/handoff_NNNN` — from_agent (String), to_agent (String), task_id (String), fidelity_at_handoff (Float)
- `/SYNAPSE/agent/dispatched_agents` — agent list with status tracking
- `current_plan` prim needs: plan_text (String), and_or_tree (String/JSON), hardest_subtask (String)
- Schema version bump 0.1.0 -> 2.0.0
- Exit gate: agent.usd round-trips with zero data loss

#### Phase 5: Routing Log Persistence
**Owner:** INTEGRATOR (primary), SUBSTRATE (advisory)
**File to modify:** `shared/router.py`
**New test:** `tests/test_routing_persistence.py`

Add to MOERouter:
- Internal decision log (list of RoutingDecision)
- `persist(agent_usd_path)` — writes routing_log to agent.usd via agent_state functions
- `replay(agent_usd_path)` — reconstructs decisions from USD, rebuilds session_fast_paths
- `history()` — returns decision log for audit
- Session learning: 3+ same fingerprint auto-promotes to fast path AND persists
- Exit gate: 50 tasks routed, history reconstructed, replay deterministic

#### Phase 6: E2E Pipeline Orchestrator
**Owner:** ALL agents, orchestrated by INTEGRATOR
**New files:** `shared/orchestrator.py`, `shared/task_tree.py`
**New test:** `tests/test_pipeline_e2e.py`

The orchestrator implements:
- 5-stage pipeline: OBSERVE -> CONSTRAINT CHECK -> PLAN/SPECIALIZE -> EXECUTE -> VERIFY
- AND/OR task decomposition with "hardest subtask" identification
- Agent dispatch via TaskSpec + AgentDispatch
- Sequential/Parallel/Pipeline execution modes
- Merge protocol: collect deliverables, check fidelity, resolve file ownership conflicts
- Session state tracking (as described in CLAUDE.md Section 10)
- Full persistence to agent.usd
- Exit gate: complex multi-agent task with all verifications passing, undo restores scene

## Key Architecture Notes
- `shared/` imports use `from shared.types import ...` (not relative)
- bridge.py has both sync `execute()` and async `execute_async()` paths
- All code must work standalone (no hou) AND inside Houdini (with hou)
- Import guards: `_HOU_AVAILABLE`, `_PXR_AVAILABLE`, `_GATES_AVAILABLE`
- Determinism: sort_keys=True, no uuid4 in hot paths, sequential counters
- Tests use pytest, Python 3.14

## Execution Order
Phase 4 first (both 5 and 6 write to agent.usd)
Phase 5 next (orchestrator needs persistent routing)
Phase 6 last (integration of everything)

## Next Action
Start Phase 4: extend agent_state.py with v2.0.0 schema prims + write tests
