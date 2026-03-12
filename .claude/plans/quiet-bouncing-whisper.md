# Plan: Wire MOE Infrastructure into SYNAPSE Request Pipeline

## Context

SYNAPSE has two parallel worlds that have never been connected:

1. **Production pipeline** — Artist message goes straight to Anthropic API with all 108 tools, Claude decides everything, tools execute via `handler.handle()` with no routing, no undo wrapping, no integrity checks.
2. **MOE infrastructure** (`shared/`) — `bridge.py` (700 lines), `router.py` (271 lines), `evolution.py` (600 lines), `types.py` (250 lines) — fully implemented, zero callers.

The result: requests aren't classified, tool lists aren't filtered, operations aren't undo-wrapped, and memory evolution never triggers. The current flow is:

```
Panel._on_send_chat() → build_system_prompt() → ClaudeWorker(all 108 tools)
  → Anthropic API → Claude picks tools blindly → handler.handle() direct → done
```

This plan wires the existing MOE infrastructure into production at 3 precise insertion points, using agent teams to implement each phase.

---

## Phase 1: Tool Filtering via MOE Router

**Agents:** INTEGRATOR (primary) + SUBSTRATE (advisory)

**Goal:** Classify artist messages using `shared/router.extract_features()` and filter the 108-tool list down to domain-relevant subsets.

### New file: `python/synapse/panel/tool_filter.py` (~150 lines)

```python
# Core function:
def filter_tools(user_text: str, all_tools: list[dict]) -> tuple[list[dict], RoutingDecision]:
    features = extract_features(user_text)
    decision = router.route(features)
    # Map primary agent → relevant tool domains
    # Always include base tools (ping, scene_info, context, get_selection)
    # Return filtered subset + routing decision
```

- Import `shared.router.extract_features` and `MOERouter`
- Build `TOOL_DOMAIN_MAP` from `_tool_registry.TOOL_DEFS` annotations + `sparse_router._detect_domain()` patterns
- Map each `AgentID` to tool subsets:
  - OBSERVER → read/inspect tools (scene_info, get_parm, network_explain, stage_info, etc.)
  - HANDS → USD/material/APEX/COPs tools (create_material, assign_material, create_usd_prim, etc.)
  - CONDUCTOR → PDG/render/batch tools (tops_*, render_*, wedge, etc.)
  - BRAINSTEM → execution/recovery tools (execute_python, execute_vex, undo, redo)
  - SUBSTRATE → MCP/server tools (connect_nodes, create_node, set_parm, delete_node)
  - INTEGRATOR → all tools (fallback for complex/research queries)

### Modify: `python/synapse/panel/claude_worker.py` (~5 lines)

- Add optional `tools` parameter to `__init__()` (default: `None`)
- If `tools` is provided, use it; otherwise fall back to `get_anthropic_tools()`

### Modify: `houdini/python_panels/synapse_panel.pypanel` (`_on_send_chat`, ~10 lines)

- Before `_launch_worker()`, call `filter_tools(user_text, get_anthropic_tools())`
- Pass filtered tools + routing decision to worker
- Wrap in try/except — if import fails, use full tool list (zero regression)

### Verification
- `extract_features("build a karma render with hdri lighting")` → HANDS primary, CONDUCTOR advisory
- `extract_features("inspect my geometry attributes")` → OBSERVER primary
- Panel works identically if `tool_filter.py` import fails

---

## Phase 2: Specialized System Prompts per Agent Role

**Agents:** HANDS (primary) + OBSERVER (advisory)

**Goal:** Inject agent-specific expertise into the system prompt based on Phase 1's routing decision.

### New file: `python/synapse/panel/agent_prompts.py` (~200 lines)

```python
AGENT_EXPERTISE: dict[AgentID, str] = {
    AgentID.HANDS: """## Solaris/USD Expert Context
    - Sublayer for simple imports, Reference for modular composition with hierarchy control
    - Material Library with subnets preferred over separate matlib + assign nodes
    - Canonical chain: merge → matlib → camera → render_settings → karma
    - Component Builder is the standard way to create properly structured USD assets
    - Purpose (render/proxy/guide) for scene performance
    - Always use HDRI on dome light; intensity=1.0, brightness via exposure only
    ...""",
    AgentID.OBSERVER: """## Scene Observation Context
    - Use houdini_inspect_node to discover parameter names before setting
    - Network explain for understanding node graphs
    - Stage info for USD hierarchy traversal
    ...""",
    # ... condensed expertise from agents/*.md + tokeru patterns
}

def build_specialized_prompt(base: str, decision: RoutingDecision, context: dict) -> str:
    # Append primary agent expertise
    # Add advisory perspective hint
    # Include Solaris patterns when USD domain detected
```

**Solaris patterns to embed** (from tokeru.com + artist learnings):
- Sublayer vs Reference vs Payload decision tree
- Material Library assignment patterns (drag geo paths, not separate assign nodes)
- Camera/light setup (HDRI + exposure, not intensity)
- Render pipeline: Karma LOP in /stage → usdrender ROP in /out, `soho_foreground=1`
- Component Builder for clean USD assets with variants + purpose
- VEX patterns for USD attribute manipulation (`usd_setrelationshiptargets`, `xformOpOrder`)

### Modify: `houdini/python_panels/synapse_panel.pypanel` (~5 lines)

- After `build_system_prompt(context)`, call `build_specialized_prompt(base, decision, context)`
- Try/except fallback to base prompt

### Verification
- USD request → prompt includes Solaris composition rules + tokeru patterns
- Geometry request → prompt includes SOP inspection patterns
- Total prompt stays under 8K tokens

---

## Phase 3: LosslessExecutionBridge at Tool Dispatch

**Agents:** SUBSTRATE (primary) + BRAINSTEM (advisory)

**Goal:** Wrap `handler.handle()` in `LosslessExecutionBridge` for undo groups, thread safety, consent gates, and integrity verification — without changing handlers.py.

### New file: `python/synapse/panel/bridge_adapter.py` (~150 lines)

```python
_bridge: LosslessExecutionBridge | None = None

def get_bridge() -> LosslessExecutionBridge:
    global _bridge
    if _bridge is None:
        _bridge = LosslessExecutionBridge()
    return _bridge

def execute_through_bridge(tool_name: str, handler, command) -> SynapseResponse:
    bridge = get_bridge()
    op = Operation(
        agent_id=_infer_agent(tool_name),  # from routing decision or tool domain
        operation_type=_tool_to_operation(tool_name),  # map MCP name → bridge op type
        summary=f"{tool_name}: {command.payload}",
        fn=handler.handle,
        args=(command,),
        kwargs={"node_path": command.payload.get("path", "")},
    )
    result = bridge.execute(op)
    return _to_synapse_response(result)
```

- Map MCP tool names to `OPERATION_GATES` operation types
- Read-only tools (flagged in `_tool_registry.py`) skip bridge entirely (fast path)
- Bridge consent callback delegates to existing `synapse.core.gates.HumanGate`

### Modify: `python/synapse/mcp/tools.py` (`dispatch_tool`, ~15 lines)

- After building `SynapseCommand`, try bridge dispatch
- If bridge unavailable, fall through to direct `handler.handle()` (zero regression)
- Attach `IntegrityBlock.to_dict()` to response for Claude to see

### Modify: `python/synapse/panel/tool_executor.py` (`execute_tool`, ~10 lines)

- Same pattern: wrap `handler.handle(command)` through bridge adapter
- Qt signal path gets undo/integrity for free

### Verification
- `create_node` through bridge → `IntegrityBlock` with `undo_group_active=True`, `fidelity=1.0`
- `execute_python` through bridge → requires CRITICAL gate
- Read-only tools bypass bridge (<1ms overhead)
- All tools still work if bridge import fails

---

## Phase 4: Integrity Feedback + Memory Evolution Triggers

**Agents:** CONDUCTOR (primary) + INTEGRATOR (advisory)

**Goal:** Feed `IntegrityBlock` results back into conversation, trigger memory evolution checks on session end.

### New file: `python/synapse/panel/session_integrity.py` (~100 lines)

```python
class SessionIntegrityTracker:
    def record(self, block: IntegrityBlock) -> None: ...
    def should_warn(self) -> bool:  # 3+ violations
    def should_evolve(self, login_data: dict) -> bool:  # check triggers
    def format_report(self) -> str:  # HTML for activity log
```

### Modify: `python/synapse/panel/claude_worker.py` (~20 lines)

- In `_execute_tool_block()`: if bridge returns `fidelity < 1.0`, append warning to tool result
- Track session fidelity across conversation loop

### Modify: `houdini/python_panels/synapse_panel.pypanel` (`_on_done`, ~15 lines)

- On conversation completion, check evolution triggers via `shared.evolution`
- Show subtle prompt in activity log if evolution recommended
- Display session fidelity in status bar

### Verification
- 3+ integrity violations → warning signal emitted
- 10+ structured tool calls → evolution recommendation shown
- Evolution check is best-effort, never blocks session

---

## Phase 5: Routing Persistence to agent.usd

**Agents:** CONDUCTOR (primary) + INTEGRATOR (advisory)

**Goal:** Log routing decisions for session replay and cross-session fast-path learning.

### New file: `python/synapse/panel/routing_log.py` (~100 lines)

- Write routing decisions to `agent.usd` schema at `/SYNAPSE/agent/routing_log/`
- Uses native `pxr.Usd` with string-template fallback
- Session-learned fast paths via `MOERouter.learn_fast_path()`

### Verification
- Routing log round-trips through USD
- Same fingerprint 3+ times → session fast path activated

---

## Execution Sequencing

```
Phase 1 (Tool Filtering)     ─┐
                               ├── PARALLEL (independent)
Phase 3 (Bridge Integration) ─┘

Phase 2 (Prompt Specialization) ← depends on Phase 1

Phase 4 (Integrity Feedback)    ← depends on Phase 3

Phase 5 (Routing Persistence)   ← depends on Phase 1 + Phase 4
```

**Wave 1:** Phase 1 + Phase 3 in parallel
**Wave 2:** Phase 2 + Phase 4 in parallel
**Wave 3:** Phase 5

---

## Agent Team Dispatch

### Wave 1 (parallel)

```
@INTEGRATOR
TASK: Build tool domain mapping and filter function
FILES: NEW python/synapse/panel/tool_filter.py
       EDIT python/synapse/panel/claude_worker.py (5 lines)
CONTEXT: _tool_registry.TOOL_DEFS has 108 tools with read_only/destructive flags.
         shared/router.py has extract_features() and MOERouter.
         sparse_router.py has _detect_domain() for domain mapping data.
CONSTRAINT: filter_tools() must return full tool list when routing fails.
DELIVERABLE: tool_filter.py with tests. Worker accepts optional tools param.

@SUBSTRATE
TASK: Build bridge adapter wrapping handler.handle() in LosslessExecutionBridge
FILES: NEW python/synapse/panel/bridge_adapter.py
       EDIT python/synapse/mcp/tools.py (15 lines)
       EDIT python/synapse/panel/tool_executor.py (10 lines)
CONTEXT: shared/bridge.py has LosslessExecutionBridge with all 4 anchors.
         dispatch_tool() in tools.py calls handler.handle(command) directly.
         OPERATION_GATES maps operation types to gate levels.
CONSTRAINT: Read-only tools skip bridge. Bridge failure falls through to direct dispatch.
DELIVERABLE: bridge_adapter.py + modified dispatch paths with tests.
```

### Wave 2 (parallel, after Wave 1)

```
@HANDS
TASK: Build agent expertise prompts with Solaris/USD patterns
FILES: NEW python/synapse/panel/agent_prompts.py
       EDIT synapse_panel.pypanel (5 lines)
CONTEXT: agents/*.md have full expertise definitions.
         Solaris patterns: sublayer vs reference, matlib assignment, HDRI+exposure,
         Component Builder, Purpose, Karma XPU, canonical chain.
         build_system_prompt() in system_prompt.py builds the base.
         Phase 1 provides RoutingDecision with primary/advisory agent.
CONSTRAINT: Prompt additions <500 tokens each. Total under 8K. Graceful fallback.
DELIVERABLE: agent_prompts.py with expertise sections + Solaris patterns.

@CONDUCTOR
TASK: Wire integrity feedback and memory evolution triggers
FILES: NEW python/synapse/panel/session_integrity.py
       EDIT python/synapse/panel/claude_worker.py (20 lines)
       EDIT synapse_panel.pypanel (15 lines)
CONTEXT: Phase 3 bridge produces IntegrityBlocks.
         shared/evolution.py has check_evolution_triggers().
         shot_login.py already detects evolution triggers.
CONSTRAINT: Evolution check is advisory only. Never blocks session completion.
DELIVERABLE: session_integrity.py + panel integration with tests.
```

### Wave 3 (after Wave 2)

```
@CONDUCTOR
TASK: Implement routing persistence to agent.usd
FILES: NEW python/synapse/panel/routing_log.py
CONTEXT: Phase 1 routing decisions + Phase 4 session tracker.
         agent.usd schema v2.0.0 at /SYNAPSE/agent/routing_log/.
         shared/evolution.py has native pxr.Usd patterns.
DELIVERABLE: routing_log.py with USD write/read + tests.
```

---

## Critical Files

| File | Role | Lines |
|------|------|-------|
| `shared/router.py` | MOE router (extract_features, MOERouter.route) | 271 |
| `shared/bridge.py` | LosslessExecutionBridge (4 anchors, R1-R8) | 700 |
| `shared/types.py` | AgentID, ExecutionResult, RoutingFeatures | 250 |
| `shared/evolution.py` | Memory evolution pipeline | 600 |
| `python/synapse/panel/claude_worker.py` | Production worker (tool loop) | 427 |
| `python/synapse/panel/tool_executor.py` | Main-thread tool dispatch | 350 |
| `python/synapse/mcp/tools.py` | MCP tool dispatch | ~200 |
| `python/synapse/mcp/_tool_registry.py` | 108 tool definitions (source of truth) | 300+ |
| `python/synapse/panel/system_prompt.py` | Base system prompt builder | 239 |
| `houdini/python_panels/synapse_panel.pypanel` | Panel UI + worker launch | 8000+ |

---

## Design Principles

1. **Additive wiring, not replacement** — Every integration point has try/except fallback to current behavior. If any `shared/` import fails, panel works exactly as today.

2. **Bridge wraps handlers, not replaces them** — The 56KB `handlers.py` is untouched. Bridge wraps the call to `handler.handle()` in an `Operation`, adds undo groups and integrity around existing logic.

3. **`sys.path` bridging** — `shared/` lives at repo root, production code at `python/synapse/`. Adapter modules add SYNAPSE repo root to `sys.path` before importing from `shared/`. This pattern exists in the import guards already.

4. **Two routers complement each other** — `shared/router.py` (MOE agent-level classification) maps agents to tool subsets. `agent/sparse_router.py` (tool pre-scoring) provides tool-to-domain mapping data. They don't compete.

---

## End-to-End Verification

After all phases:

1. **Panel smoke test**: Type "create a sphere with a gold material in Solaris" → verify:
   - Tools filtered to HANDS subset (~30 tools, not 108)
   - System prompt includes Solaris expertise + matlib patterns
   - Each tool call shows `IntegrityBlock` with `fidelity=1.0`
   - Undo group wraps the full operation chain

2. **Fallback test**: Temporarily rename `shared/` → verify panel works identically to current behavior

3. **Routing accuracy**: Run 20 sample prompts through `extract_features()`, verify primary agent matches expected domain

4. **Integrity test**: Trigger a composition violation → verify rollback fires and artist is warned

5. **Evolution trigger**: After 10+ structured tool calls with 5+ node references → verify evolution recommendation appears
