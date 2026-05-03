# Test Constitution — Cognitive Bridge

*Binding rules for the test-coverage initiative. All test code in this branch is authored against this constitution.*

---

## Why a constitution

Generic test guidelines ("write good tests") fail to encode this codebase's specific invariants. The Cognitive Bridge is not CRUD — it is a non-destructive composition stage with a dependency DAG, an append-only event log, and Popperian schema gates. Tests that ignore those properties produce false greens.

This document encodes the invariants as enforceable rules. Every new test file in `tests/` MUST cite the constitution rule(s) it satisfies in its module docstring.

---

## Part I — Codebase-specific invariants (derived from CLAUDE.md)

### Rule C1: Non-destruction

No assertion is ever deleted. Retraction sets `active=False` and `retracted_at=now`; the row stays in `stage.assertions`.

**Test obligation:** Any test that retracts MUST assert (a) the assertion still exists in `stage.assertions`, (b) `active is False`, (c) `retracted_at is not None`. Tests that use `del stage.assertions[...]` violate this rule.

### Rule C2: LIVRPS ordering

`CompositionArc` is an `IntEnum` where lower integer = stronger. `Assertion.__lt__` sorts by arc, then descending confidence, then descending recency.

**Test obligation:** Any test about resolution MUST verify the winner via `get_current_winner()` or `stage.resolve()[path]["winning"]`, not by reaching into a sorted list. Sorted lists test the implementation; the winner functions test the contract.

### Rule C3: Steelman before challenge

`resolve_conflict(..., resolution=ResolutionPath.CHALLENGE, steelman_summary=None)` MUST raise `ValueError`. CHALLENGE without a steelman is forbidden by the resolver.

**Test obligation:** Every tool/resolver test that exercises CHALLENGE MUST have a paired test that omits `steelman_summary` and asserts the error. The gate is not optional.

### Rule C4: Experiment protocol gate

`PROPOSE_EXPERIMENT` without `experiment_protocol` MUST raise `ValueError`.

**Test obligation:** Same shape as C3 — paired accept/reject tests.

### Rule C5: Decisions require enumeration of rejected alternatives + second-order effects

`Decision.alternatives_rejected` and `Decision.second_order_effects` both have `min_length=1`. Empty lists or omitted fields MUST raise `ValidationError`.

**Test obligation:** `tests/test_models/test_decision.py` MUST include explicit `pytest.raises(ValidationError)` cases for both fields, both empty and omitted.

### Rule C6: LOCAL requires falsifiability

An `Assertion` with `arc=CompositionArc.LOCAL` and `falsifiable_if=None` MUST raise `ValidationError` (per the model_validator in `assertion.py`).

**Test obligation:** Any test that constructs LOCAL assertions MUST also have a paired reject-test for the missing falsifier. Falsifiability is a Popperian gate, not a recommendation.

### Rule C7: Cascade propagation through the DAG

When the winner at a topic_path changes, `detect_cascading_conflicts` runs against all assertions whose `depends_on_paths` include that path. With `cascade_auto_challenge=True`, dependents' `assumption_status` becomes `CHALLENGED`.

**Test obligation:** Cascade tests MUST verify both the immediate effect (cascading Conflict added to `stage.conflicts`) AND downstream propagation (`assumption_status` mutation on dependents). Shallow verification of deep state hides regressions.

### Rule C8: Append-only event log

Every state mutation appends to `stage.events`. The list is never reordered, edited, or pruned.

**Test obligation:** Every tool test that mutates state MUST assert the corresponding `EventType` was appended. Search by `event_type` and `target_id` — assert at least one match exists. Missing event-log assertions silently allow regressions in the audit trail.

### Rule C9: Round-trip identity for storage

Every model has converter pair `{model}_to_row` ↔ `row_to_{model}`. The composition `row_to_X(X_to_row(obj))` MUST equal `obj` field-by-field, including JSON-encoded fields (lists, nested dicts, embeddings, enums-as-int).

**Test obligation:** `tests/test_storage/test_converters.py` MUST include a populated round-trip test for EVERY model type. Defaults-only tests don't catch JSON-encoding bugs in non-default values.

### Rule C10: Project capsule round-trip

`export_stage_to_json` → `import_stage_from_json` MUST produce an equivalent stage. The capsule is the long-term storage format; lossy export is data loss.

**Test obligation:** Integration tests cover both empty-stage and populated-stage round-trips. Embeddings, depends_on_paths, falsifiable_if, evidence lists must all survive.

---

## Part II — Generic test-quality rules

### Rule G1: Determinism

No `random` without an explicit seed. No `time.sleep`. No network calls. No filesystem I/O outside `tmp_path`. A test that fails intermittently is worse than no test.

### Rule G2: Validator-rejection symmetry

Every Pydantic `field_validator`, `model_validator`, or `Field(min_length=...)`/`ge=`/`le=` constraint MUST have BOTH an accept-test and a reject-test. Validators are bidirectional contracts; testing only one side proves nothing.

### Rule G3: No mock-only coverage

If module X is mocked in test A, there MUST exist a non-mocking test B that exercises X directly. Mocks test the test, not the code. Slow real-code tests can be gated behind `@pytest.mark.slow`.

### Rule G4: Behavioral over structural

Assert what code DOES (effects, return values, persisted state), not HOW (internal call counts, private method invocations). Structural tests fossilize implementation; behavioral tests survive refactoring.

### Rule G5: Test isolation

Fresh `SQLiteStore(":memory:")` per test. Fresh `CompositionStage` per test. No shared mutable module-level state between tests. Order-independent tests parallelize and shuffle without breaking.

### Rule G6: Async correctness

Every async tool handler test uses `@pytest.mark.asyncio` (or relies on the auto mode). Every awaited call is awaited. Silent missing-await bugs give false greens.

### Rule G7: Citation

Every test file's module docstring cites which constitution rule(s), CLAUDE.md requirement(s), or blueprint section(s) it satisfies. Test rationale should be self-documenting for the next maintainer.

### Rule G8: No production-code edits during a test sprint

This is a test-coverage initiative. If a test reveals a bug, file it as a finding in the PR description and leave the bug. Mixing fixes and tests creates unreviewable diffs and obscures whether the test was written against the bug or against the spec.

### Rule G9: Coverage as floor, not aspiration

The project enforces `--cov-fail-under=85` per the coverage config in `pyproject.toml`. New tests must not drop any source module below 70% line coverage.

---

## Part III — MoE roles for the sprint

For parallel implementation, work is divided by exclusive file ownership. No two experts touch the same file.

| Expert | Owns |
|---|---|
| Tools Expert | `tests/test_tools/test_decide_tool.py`, `test_variant_tool.py`, `test_parameters_tool.py`, `test_probe_tool.py`, `test_payload_tool.py` |
| Storage & Models Expert | `tests/test_storage/test_converters.py`, `test_sqlite_store.py`; `tests/test_models/test_decision.py`, `test_parameters.py`, `test_kernel.py`, `test_event.py` |
| Engine Expert | `tests/test_engine/test_trust.py`, `test_sensitivity.py`, `test_red_team.py`, `test_provenance.py`, `test_semantic_detection.py` |
| Integration Expert | `tests/test_integration/test_server_lifespan.py`, `test_export_import.py`, `test_mongodb_scenario.py` |
| Orchestrator | `pyproject.toml`, `tests/conftest.py`, `docs/TEST_CONSTITUTION.md` |

Phase gates: foundation (orchestrator) commits first; experts then work in parallel against the new fixtures.

---

## Part IV — Verification

```bash
# Default run (excludes slow tests)
pytest -q

# Slow tests (semantic detection with sentence-transformers)
pytest -q -m slow

# Full coverage report
pytest --cov=cognitive_bridge --cov-report=term-missing

# End-to-end MongoDB scenario in isolation
pytest tests/test_integration/test_mongodb_scenario.py -v

# Storage round-trips in isolation
pytest tests/test_storage/ -v
```

A passing run satisfies: all rules in Parts I–II are exercised; coverage ≥ 85% globally; no source module < 70%; the canonical Cognitive Bridge story (assert → detect → steelman → challenge → resolve → cascade → decide) runs green.
