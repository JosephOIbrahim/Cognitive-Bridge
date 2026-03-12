# P4: MoE → Tools Validation Layer

## Context

The MoE pipeline (Intent Agent, Verify Agent, Router) operates in pure reasoning
space with model profiles. It generates parameter mutations and quality judgments
without checking if those parameters actually exist in real ComfyUI nodes. P4 adds
a non-blocking validation layer in the orchestrator (`iterative_refine.py`) that
grounds reasoning against real ComfyUI state.

The agents stay pure reasoning. All validation lives in the orchestrator.

## Files Modified

| File | Change |
|------|--------|
| `agent/brain/iterative_refine.py` | Add 3 helper functions, wire into 4 pipeline paths, add `validation` key to all results |
| `tests/test_iterative_refine.py` | Add ~20 new tests for validation helpers and integration |

No other files modified. `comfy_api.py`, `intent_agent.py`, `verify_agent.py` are read-only references.

## Implementation

### Step 1: Add `tools_handle` import + 3 helper functions

```python
from ..tools import handle as tools_handle
```

**`_is_comfyui_available() -> bool`** — Fire-and-forget. Calls `tools_handle("is_comfyui_running", {})`, returns True/False. Exception → False.

**`_validate_intent_mutations(intent_spec) -> list[dict]`** — For each `ParameterMutation.target` (format `"KSampler.cfg"`):
- Split into node_class + input_name
- Call `tools_handle("get_node_info", {"node_type": node_class})`
- Check node exists (no `"error"` key) and input exists in `required` or `optional`
- Cache node info per node_class within the call
- Return list of `{"target", "node_class", "input_name", "node_exists", "input_exists", "status", "message?"}`
- Entire function wrapped in try/except → empty list on failure

**`_extract_parameters_from_workflow(workflow_state) -> dict | None`** — Walk workflow nodes, extract literal values for `cfg`, `steps`, `denoise`, `sampler_name`, `scheduler`. Skip connection inputs (`[node_id, idx]` lists). Returns flat dict or None.

### Step 2: Add `"validation": []` to all result dicts

Every `_safe_to_json({...})` return gets `"validation": validation_results` (or `[]`). This ensures consistent schema across all paths (error, planned, accepted, escalated, evaluated, exploration).

### Step 3: Wire validation into `_handle_generation_or_modification`

After `intent_spec = router.intent_agent.translate(...)`, before confidence check:
```python
validation_results = []
if _is_comfyui_available():
    validation_results = _validate_intent_mutations(intent_spec)
    for vr in validation_results:
        if vr.get("status") == "warning":
            precondition_warnings.append(f"Validation: {vr.get('message', '')}")
```

Before `verify_agent.evaluate()` calls in the loop:
```python
parameters_used = _extract_parameters_from_workflow(workflow_state)
# Pass parameters_used= to evaluate()
```

### Step 4: Wire validation into `_handle_exploration`

Same pattern as step 3, but only the Intent validation (no Verify loop in exploration).

### Step 5: Enrich `_handle_evaluation` with workflow params

- Add `workflow_state` param to `_handle_evaluation` signature
- Thread it from `_dispatch_by_intent_type`
- Extract `parameters_used` and pass to `verify_agent.evaluate()`

## Tests (~20 new tests in `tests/test_iterative_refine.py`)

All mock `agent.brain.iterative_refine.tools_handle`.

| Group | Tests | What |
|-------|-------|------|
| `TestIsComfyuiAvailable` | 3 | running=True, running=False, exception |
| `TestValidateIntentMutations` | 5 | valid node+input, unknown node, unknown input, cached calls, exception→empty |
| `TestExtractParameters` | 4 | extracts params, skips connections, None/empty input |
| `TestValidationIntegration` | 5 | result has `validation` key, warnings surface, skipped offline, non-blocking |
| `TestVerifyEnrichment` | 3 | parameters_used passed, None without workflow, evaluation path |

## Verification

1. `python -m pytest tests/test_iterative_refine.py -v` — all new + existing tests pass
2. `python -m pytest tests/test_moe_integration.py -v` — existing tests unbroken
3. `python -m pytest tests/ -v` — full suite 1217+ tests pass
4. `ruff check agent/brain/iterative_refine.py` — no lint warnings
