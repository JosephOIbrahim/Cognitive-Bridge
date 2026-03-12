# DeepSeek-V3.2 Research Graft — Phase 1 Implementation Plan

## Context

Adding 4 new modules from the DeepSeek-V3.2 research graft (arxiv:2512.02556) to the Synapse agent layer. These implement sparse tool routing, persistent reasoning context, domain specialist modes, and synthetic task generation. **Phase 1 only** — standalone modules with tests, no behavioral changes to existing code.

## Files to Create (8 total)

### Source Files (in `python/synapse/agent/`)

1. **`sparse_router.py`** — Lightweight signal indexer for MCP tool pre-scoring
   - `ToolSignature` (frozen dataclass): name, domain, keywords, param_patterns, cost_tier
   - `RouteCandidate`: tool_name, score, match_signals
   - `SparseRouterConfig`: top_k=3, weight tuning params
   - `SparseToolIndexer`: register_tool(), index(), record_selection(), calibration_accuracy()
   - `build_signatures_from_registry()`: auto-generate signatures from tool definitions
   - Adapt from user's spec with: 61 tools (not 43), `round_float()` for score determinism, `sort_keys=True`

2. **`reasoning_context.py`** — Persistent reasoning trace across multi-tool agent chains
   - `EntryCategory` enum: DECISION, QUESTION, PLAN, OBSERVATION, ANALYSIS, CONTEXT
   - `ReasoningEntry`: category, content, timestamp, tool_call, confidence, compressed
   - `ReasoningContext`: intent, entries, tool_chain, compress_if_needed(), summarize(), to_memory_record()
   - `ReasoningContextManager`: create/get/archive contexts by chain_id
   - Protected categories (DECISION, QUESTION, PLAN) survive compression

3. **`specialist_modes.py`** — Domain-specific specialist configurations
   - `SpecialistMode` (frozen dataclass): domain, system_prompt_extension, parameter_vocabulary, quality_signals
   - 5 built-in specialists: LIGHTING, MATERIAL, RENDER, SCENE, MEMORY
   - `SPECIALIST_REGISTRY` dict + `get_specialist()` + `build_enhanced_prompt()`
   - Lighting specialist includes real USD encoded param names (xn__inputs*)
   - Enforces Lighting Law (intensity always 1.0, brightness via exposure)

4. **`task_synthesizer.py`** — Synthetic test environment generator
   - `Complexity` enum: MINIMAL through PRODUCTION
   - `ConstraintType` enum: TIME_BUDGET, QUALITY_FLOOR, VRAM_CEILING, etc.
   - `FailureMode` enum: NONE, MISSING_ASSET, INVALID_PARAM, etc.
   - `TaskEnvironment`: task_id, description, constraints, expected_tool_chain, success_criteria
   - `TaskSynthesizer`: generate(n, diversity_threshold), deterministic via seed

### Test Files (in `tests/`)

5. **`test_sparse_router.py`** — Indexer top-k, keyword matching, domain detection, calibration accuracy, recency boost, build_signatures
6. **`test_reasoning_context.py`** — Protected categories survive compression, summarize includes all protected, tool chain ordering, memory record export, concurrent contexts
7. **`test_specialist_modes.py`** — All domains have specialists, prompt extension, parameter vocabulary, quality signals
8. **`test_task_synthesizer.py`** — Generates requested count, diversity enforced, all complexity levels, failure modes, deterministic with seed

### Files to Edit (2)

9. **`python/synapse/agent/__init__.py`** — Add imports for new classes to `__all__`
10. **`python/synapse/__init__.py`** — Add new class names to `_agent_names` lazy-load set (if applicable)

## Adaptations from User's Spec

- All paths: `src/agent/` → `python/synapse/agent/`
- Tool count: 43 → 61 in all comments and docstrings
- Feature flag config: user's spec uses YAML but Synapse has no YAML config. Feature flags become simple class defaults (e.g., `SparseRouterConfig(mode="dense")`) — integration wiring deferred to Phase 2
- Test pattern: `sys.path` manipulation + direct imports, no conftest, no hou stub needed (these modules don't touch Houdini)
- Determinism: `sort_keys=True`, sorted iterations before aggregation

## What NOT to Touch

- `router.py`, `executor.py`, `mcp_server.py`, `handlers.py` — no integration wiring
- `RoutingConfig` — no new fields until Phase 2
- No new external dependencies

## Implementation Order

1. `sparse_router.py` + `test_sparse_router.py`
2. `reasoning_context.py` + `test_reasoning_context.py`
3. `specialist_modes.py` + `test_specialist_modes.py`
4. `task_synthesizer.py` + `test_task_synthesizer.py`
5. `__init__.py` updates (both files)

## Verification

```bash
# Each new test file passes
python -m pytest tests/test_sparse_router.py -v
python -m pytest tests/test_reasoning_context.py -v
python -m pytest tests/test_specialist_modes.py -v
python -m pytest tests/test_task_synthesizer.py -v

# Full test suite — no regressions
python -m pytest tests/ -v

# Type check (if mypy available)
python -m mypy python/synapse/agent/sparse_router.py python/synapse/agent/reasoning_context.py python/synapse/agent/specialist_modes.py python/synapse/agent/task_synthesizer.py --config-file pyproject.toml
```
