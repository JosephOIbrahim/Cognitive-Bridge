# Creative Metadata Layer — All Phases Implementation

## Context

The blueprint defines a Creative Metadata Layer that captures artistic intent, iteration history, and session context in PNG metadata alongside ComfyUI's native workflow data. The user wants all 4 phases implemented using agent teams.

**Key codebase findings (from exploration):**
- PIL is optional (`try/except ImportError` guard in `vision.py`)
- Tool pattern: `TOOLS` list + `handle()` function in `agent/tools/`, registered in `__init__.py`
- `_util.py` provides `to_json()` (deterministic) and `validate_path()` (security)
- `verify_execution.py` has `_resolve_output_path()` and `_extract_key_params()` — exactly what metadata needs
- Test pattern: `tmp_path` fixtures, direct `handle()` calls, `monkeypatch` for `_SAFE_DIRS`
- PNG tEXt chunk key: `comfyui_agent` (distinct from ComfyUI's `prompt` and `workflow`)

## Implementation — 3 Agent Waves

### Wave 1: Phase A — Schema + PNG Reader/Writer (no dependencies)

**Agent 1: `agent/tools/image_metadata.py` + `agent/tools/__init__.py` + tests**

New tool module with 2 tools:
- `write_image_metadata(image_path, metadata)` — writes `comfyui_agent` tEXt chunk to PNG
- `read_image_metadata(image_path)` — reads and parses `comfyui_agent` chunk

Schema defined as a Python dict constant (`METADATA_SCHEMA_V1`). Validation via `jsonschema.validate()` (already a dependency). PIL with optional guard for read/write. Must NOT overwrite ComfyUI native `prompt`/`workflow` chunks — read existing, add ours, re-save.

Register in `agent/tools/__init__.py` `_MODULES`.

Tests in `tests/test_image_metadata.py`: round-trip, native chunk preservation, schema validation, missing/partial metadata, version mismatch handling.

### Wave 2: Phase B (Intent Capture) + Phase C (Iteration History) — parallel after Wave 1

**Agent 2: Phase B — `agent/brain/intent_collector.py`**

New brain module with 2 tools:
- `capture_intent(request, interpretation, style_refs, session_context)` — stores intent for current execution
- `get_current_intent()` — returns the captured intent (for metadata writer to consume)

Module-level state (with thread lock, matching orchestrator/demo pattern). Intent is captured when user issues generation requests. Wire: after successful execution in `verify_execution.py`, call `write_image_metadata` with intent data from `get_current_intent()`.

Register in `agent/brain/__init__.py` `_MODULES`. Tests in `tests/test_intent_collector.py`.

**Agent 3: Phase C — `agent/brain/iteration_accumulator.py`**

New brain module with 3 tools:
- `start_iteration_tracking(intent_summary)` — begins accumulation
- `record_iteration_step(iteration, type, trigger, patches, params, feedback, observation)` — adds a step
- `finalize_iterations(accepted_iteration)` — marks acceptance, returns full history

Module-level state with lock. Each step stores: iteration number, type (initial/refinement/variation/rollback), trigger text, RFC6902 patches (reuse existing patch objects), param snapshot, user feedback, agent observation.

Register in `agent/brain/__init__.py`. Tests in `tests/test_iteration_accumulator.py`.

### Wave 3: Phase D — Reload & Reconstruct — after Waves 1+2

**Agent 4: Phase D — `agent/tools/image_metadata.py` additions + integration**

Add 1 tool to existing `image_metadata.py`:
- `reconstruct_context(image_path)` — reads metadata, returns structured context for agent greeting

Integration points:
- When agent detects an image being loaded/referenced, auto-read metadata
- If `comfyui_agent` metadata present, reconstruct context and brief the agent
- Feed session context (Layer 3) back into memory system via `dispatch_brain_message`

Tests: round-trip generate→reload, partial metadata graceful degradation, schema version mismatch.

## Files Created/Modified

| File | Wave | Action |
|------|------|--------|
| `agent/tools/image_metadata.py` | 1+3 | New — schema, PNG read/write, reconstruct |
| `agent/tools/__init__.py` | 1 | Add `image_metadata` to `_MODULES` |
| `agent/brain/intent_collector.py` | 2 | New — intent capture + retrieval |
| `agent/brain/iteration_accumulator.py` | 2 | New — step tracking + finalization |
| `agent/brain/__init__.py` | 2 | Add both new brain modules to `_MODULES` |
| `tests/test_image_metadata.py` | 1+3 | New — schema, read/write, reconstruct tests |
| `tests/test_intent_collector.py` | 2 | New — intent capture tests |
| `tests/test_iteration_accumulator.py` | 2 | New — iteration tracking tests |

## Verification

1. `python -m pytest tests/test_image_metadata.py tests/test_intent_collector.py tests/test_iteration_accumulator.py -v` — all new tests pass
2. `python -m pytest tests/ -v` — full suite still passes (708+ tests)
3. Round-trip: write metadata to PNG → read back → identical schema object
4. ComfyUI native `prompt`/`workflow` chunks preserved after metadata write
