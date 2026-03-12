# Agent SDK Extraction

## Context

Phase 2 (unified discovery, 60 tools, 475 tests) is complete. The brain layer has 6 modules in `agent/brain/` with 20 tools total. Every module is tightly coupled to the parent package via hard imports (`..tools._util`, `..config`, `..rate_limiter`). This makes it impossible to instantiate a brain module standalone — e.g., for testing without the full agent, running as an independent service, or reusing in another project.

**Goal:** Extract brain modules into SDK-ready agents with dependency injection, while preserving 100% backward compatibility (all 475 tests pass unchanged).

**Net effect:** 1 new file (`_sdk.py`), 8 modified files (6 brain modules + `_protocol.py` + `__init__.py`), 1 new test file. Zero functional changes. Zero test breakage.

---

## Design: BrainConfig + BrainAgent

### `BrainConfig` (dataclass)

Dependency injection container. When integrated: auto-populated from `agent.config` / `agent.tools._util`. When standalone: caller provides values or uses defaults.

Fields:
- `to_json: Callable` — defaults to `json.dumps(obj, sort_keys=True)`
- `validate_path: Callable` — defaults to permissive (standalone) or `_util.validate_path` (integrated)
- `sessions_dir: Path` — defaults to `./sessions`
- `comfyui_url: str` — defaults to `http://127.0.0.1:8188`
- `custom_nodes_dir: Path` — defaults to `./Custom_Nodes`
- `models_dir: Path` — defaults to `./models`
- `agent_model: str` — defaults to `claude-opus-4-6-20250929`
- `vision_limiter` — defaults to no-op limiter
- `tool_dispatcher: Callable | None` — for orchestrator/optimizer (calls other tools)
- `get_workflow_state: Callable | None` — for optimizer (reads workflow_patch._state)
- `patch_handle: Callable | None` — for optimizer (calls workflow_patch.handle)

### `BrainAgent` (base class)

```python
class BrainAgent:
    TOOLS: list[dict] = []

    def __init__(self, config: BrainConfig | None = None):
        if config is None:
            config = get_integrated_config()
        self.cfg = config
        self.to_json = config.to_json

    def handle(self, name: str, tool_input: dict) -> str:
        raise NotImplementedError
```

### `get_integrated_config()` (lazy singleton)

Builds a `BrainConfig` from the full agent package imports. Called once, cached. Lazy closures for optimizer deps:

```python
def _lazy_tool_dispatcher(name, tool_input):
    from ..tools import handle
    return handle(name, tool_input)

def _lazy_get_workflow_state():
    from ..tools.workflow_patch import _state
    return _state

def _lazy_patch_handle(name, tool_input):
    from ..tools.workflow_patch import handle
    return handle(name, tool_input)
```

---

## Migration Pattern (applied to each module)

Each module gets a class wrapping its existing logic. Module-level `TOOLS` and `handle()` are preserved via lazy singleton.

**Key constraint:** Tests directly access module-level state (`demo._demo_state`, `orchestrator._active_tasks`) and patch module-level names (`agent.brain.optimizer.CUSTOM_NODES_DIR`). These must remain accessible at module level.

### Pattern (demo.py example):

```python
from ._sdk import BrainAgent, BrainConfig

class DemoAgent(BrainAgent):
    TOOLS = [...]  # same schemas

    def __init__(self, config=None):
        super().__init__(config)
        self._demo_state = {"active": False, ...}
        self._demo_lock = threading.Lock()

    def handle(self, name, tool_input):
        ...  # existing logic, using self.to_json, self._demo_state

# === Backward compat (lazy singleton) ===
_instance: DemoAgent | None = None

def _get_instance() -> DemoAgent:
    global _instance
    if _instance is None:
        _instance = DemoAgent()
    return _instance

TOOLS = DemoAgent.TOOLS
DEMO_SCENARIOS = DemoAgent.DEMO_SCENARIOS  # class constant exposed at module level

def handle(name: str, tool_input: dict) -> str:
    return _get_instance().handle(name, tool_input)

def __getattr__(name):
    """Proxy module-level state access to singleton (tests use demo._demo_state)."""
    if name == "_demo_state":
        return _get_instance()._demo_state
    if name == "_demo_lock":
        return _get_instance()._demo_lock
    raise AttributeError(name)
```

### State exposure via `__getattr__`

Tests directly mutate `demo._demo_state`, `orchestrator._active_tasks` etc. Module-level `__getattr__` proxies these reads to the singleton instance, so `demo._demo_state["active"] = False` works transparently.

### Optimizer special case

Tests `patch("agent.brain.optimizer.CUSTOM_NODES_DIR", tmp_path)` — setting module-level attributes. The `OptimizerAgent` class methods reference these module-level names directly (not `self.cfg`) for the integrated path. Standalone mode uses `self.cfg`. This is pragmatic: zero test changes now, full decoupling can come later when tests are migrated to config injection.

---

## Changes

### 1. `agent/brain/_sdk.py` (NEW — ~100 lines)

- `BrainConfig` dataclass with all dependency fields + sensible defaults
- `_default_to_json()` — `json.dumps(sort_keys=True)`
- `_default_validate_path()` — permissive, just checks existence if `must_exist`
- `_NullLimiter` — no-op rate limiter
- `BrainAgent` base class with `__init__(config)`, `TOOLS`, `handle()`
- `get_integrated_config()` — lazy singleton, imports from parent package
- Lazy closures for tool_dispatcher, get_workflow_state, patch_handle

### 2. `agent/brain/_protocol.py` (MODIFY — small)

Replace:
```python
from ..tools._util import to_json
```
With:
```python
from ._sdk import _default_to_json as to_json
```

This breaks the only `_protocol.py → ..tools._util` dependency. The behavior is identical (`json.dumps(sort_keys=True)`).

### 3. `agent/brain/demo.py` (MODIFY — wrap in class)

- Create `DemoAgent(BrainAgent)` with `_demo_state`, `_demo_lock` as instance attributes
- Move `DEMO_SCENARIOS` to class constant
- Move handler functions to methods
- Module-level `TOOLS`, `handle()`, `DEMO_SCENARIOS` via lazy singleton
- Module `__getattr__` for `_demo_state`, `_demo_lock` access from tests

### 4. `agent/brain/planner.py` (MODIFY — wrap in class)

- Create `PlannerAgent(BrainAgent)`
- Replace `SESSIONS_DIR` with `self.cfg.sessions_dir`
- Move `GOAL_PATTERNS`, `_GENERIC_STEPS` to class constants
- Module-level backward compat shim
- Module `__getattr__` for `GOAL_PATTERNS`

### 5. `agent/brain/memory.py` (MODIFY — wrap in class)

- Create `MemoryAgent(BrainAgent)`
- Replace `SESSIONS_DIR` with `self.cfg.sessions_dir`
- Move constants (`DECAY_HALF_LIFE_S` etc.) to class constants
- Module-level backward compat shim

### 6. `agent/brain/vision.py` (MODIFY — wrap in class)

- Create `VisionAgent(BrainAgent)`
- Replace `AGENT_MODEL` with `self.cfg.agent_model`
- Replace `VISION_LIMITER()` with `self.cfg.vision_limiter`
- Replace `validate_path` import with `self.cfg.validate_path`
- Keep `import anthropic` at module level (tests patch `agent.brain.vision.anthropic.Anthropic`)
- Module-level backward compat shim

### 7. `agent/brain/orchestrator.py` (MODIFY — wrap in class)

- Create `OrchestratorAgent(BrainAgent)`
- `_active_tasks`, `_tasks_lock` as instance attributes
- Replace lazy `from ..tools import handle as handle_tool` with `self.cfg.tool_dispatcher`
- `_TOOL_PROFILES` as class constant
- Module `__getattr__` for `_active_tasks`, `_tasks_lock`, `_TOOL_PROFILES`

### 8. `agent/brain/optimizer.py` (MODIFY — wrap in class, keep module imports)

- Create `OptimizerAgent(BrainAgent)`
- **Keep** `from ..config import COMFYUI_URL, CUSTOM_NODES_DIR, MODELS_DIR` at module level (tests patch these)
- Methods continue referencing module-level imports for integrated mode
- Standalone mode uses `self.cfg` values
- `GPU_PROFILES`, `_OPTIMIZATIONS` as class constants
- Replace lazy workflow_patch imports with `self.cfg.get_workflow_state` / `self.cfg.patch_handle` (with fallback to lazy import for integrated mode)
- Module-level backward compat shim

### 9. `agent/brain/__init__.py` (MODIFY — add re-exports)

Keep existing module-iteration dispatch unchanged. Add:
```python
from ._sdk import BrainAgent, BrainConfig
from .vision import VisionAgent
from .planner import PlannerAgent
from .memory import MemoryAgent
from .orchestrator import OrchestratorAgent
from .optimizer import OptimizerAgent
from .demo import DemoAgent
```

### 10. `tests/test_brain_sdk.py` (NEW — ~15 tests)

- `TestBrainConfig`: default values, custom values, null limiter
- `TestBrainAgent`: base class, subclass receives config
- `TestStandaloneInstantiation`: create DemoAgent/PlannerAgent/MemoryAgent with custom BrainConfig (no parent imports needed at call time)
- `TestIntegratedConfig`: `get_integrated_config()` caching, real values
- `TestBackwardCompat`: module-level TOOLS match class TOOLS, module handle delegates to instance

### 11. `CLAUDE.md` (MODIFY — update architecture section)

- Add BrainAgent/BrainConfig to brain layer description
- Update "What's Built" section
- Move "Agent SDK extraction" from NEXT to BUILT

### 12. Existing test files (NO CHANGES)

All 7 existing brain test files continue working unchanged:
- `test_brain_demo.py` — `demo._demo_state` via `__getattr__`
- `test_brain_orchestrator.py` — `orchestrator._active_tasks` via `__getattr__`
- `test_brain_optimizer.py` — `patch("agent.brain.optimizer.CUSTOM_NODES_DIR")` works on module-level import
- `test_brain_vision.py` — `patch("agent.brain.vision.anthropic.Anthropic")` works on module-level import
- `test_brain_planner.py`, `test_brain_memory.py`, `test_brain_integration.py` — unchanged

---

## Implementation Order

1. Create `agent/brain/_sdk.py` (foundation)
2. Update `agent/brain/_protocol.py` (break upward dependency)
3. Migrate `agent/brain/demo.py` (simplest — only uses `to_json`) → run tests
4. Migrate `agent/brain/planner.py` (uses `sessions_dir`) → run tests
5. Migrate `agent/brain/memory.py` (uses `sessions_dir`) → run tests
6. Migrate `agent/brain/vision.py` (uses `agent_model`, limiter, validate_path) → run tests
7. Migrate `agent/brain/orchestrator.py` (uses `tool_dispatcher`) → run tests
8. Migrate `agent/brain/optimizer.py` (most complex — keeps module imports) → run tests
9. Update `agent/brain/__init__.py` (add re-exports)
10. Add `tests/test_brain_sdk.py`
11. Update `CLAUDE.md`
12. Run full suite + lint

---

## Verification

```bash
# All tests pass (target ~490: 475 existing + ~15 new)
python -m pytest tests/ -v

# Lint clean
python -m ruff check agent/ tests/

# Standalone instantiation works
python -c "
from agent.brain._sdk import BrainConfig, BrainAgent
from agent.brain.demo import DemoAgent
from agent.brain.planner import PlannerAgent

# Standalone with custom config
cfg = BrainConfig(sessions_dir=Path('/tmp/test_sessions'))
agent = PlannerAgent(config=cfg)
print(f'PlannerAgent TOOLS: {len(agent.TOOLS)}')
print(f'Config sessions_dir: {agent.cfg.sessions_dir}')

# Integrated (uses parent package)
demo = DemoAgent()
result = demo.handle('start_demo', {'scenario': 'list'})
print(f'Demo works: {\"count\" in result}')
"

# Module-level API unchanged
python -c "
from agent.brain import demo, planner, memory, vision, orchestrator, optimizer
from agent.tools import ALL_TOOLS
print(f'Total tools: {len(ALL_TOOLS)}')  # Expected: 60
print(f'Demo TOOLS: {len(demo.TOOLS)}')  # Expected: 2
# Module-level handle still works
import json
r = json.loads(demo.handle('start_demo', {'scenario': 'list'}))
print(f'Module handle works: {r[\"count\"] >= 4}')
"

# Agent classes exported from brain package
python -c "
from agent.brain import BrainAgent, BrainConfig, VisionAgent, PlannerAgent
print('All exports available')
"
```

## Critical Files

| File | Change Type | Scope |
|------|-------------|-------|
| `agent/brain/_sdk.py` | NEW | ~100 lines: BrainConfig, BrainAgent, get_integrated_config |
| `agent/brain/_protocol.py` | Minor edit | 1 import change |
| `agent/brain/demo.py` | Medium edit | Wrap in DemoAgent class + backward compat shim |
| `agent/brain/planner.py` | Medium edit | Wrap in PlannerAgent class + backward compat shim |
| `agent/brain/memory.py` | Medium edit | Wrap in MemoryAgent class + backward compat shim |
| `agent/brain/vision.py` | Medium edit | Wrap in VisionAgent class + backward compat shim |
| `agent/brain/orchestrator.py` | Medium edit | Wrap in OrchestratorAgent class + backward compat shim |
| `agent/brain/optimizer.py` | Medium edit | Wrap in OptimizerAgent class + keep module imports |
| `agent/brain/__init__.py` | Minor edit | Add re-exports |
| `tests/test_brain_sdk.py` | NEW | ~15 tests for SDK foundation + standalone use |
| `CLAUDE.md` | Minor edit | Update architecture docs |
