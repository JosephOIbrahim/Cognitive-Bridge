# USD Composition — Mechanical Equivalence Proof

Generated: 2026-03-12

This document provides concrete evidence that the Cognitive Bridge
argumentation framework resolves epistemic state through mechanical
USD (Universal Scene Description) composition, not metaphorical
analogy.

The proof is machine-executable. Every claim in this document is
verified by `tests/test_bridge/test_usda_patent_evidence.py` (28 tests,
zero skips). Run with:

```
python -m pytest tests/test_bridge/test_usda_patent_evidence.py -v
```

---

## 1. LIVRPS Resolution Proof

### Setup

Five assertions at the same topic path `/architecture/database/engine`,
across five of the six arc levels (VARIANT_SET, arc=30, is handled
separately as variant sets in Section 2):

| Arc | IntEnum Value | Content |
|-----|---------------|---------|
| LOCAL | 10 | "Use PostgreSQL — verified via production benchmarks" |
| INHERITS | 20 | "Use a relational database (domain pattern)" |
| REFERENCES | 40 | "User prefers MongoDB" |
| PAYLOADS | 50 | "DynamoDB benchmarks exist but not loaded" |
| SPECIALIZES | 60 | "Default to SQLite for development" |

### Generated USDA Files

The following is the actual output of `export_stage_to_usda()` for this
scenario, captured by running the test suite.

#### stage.usda (root composition file)

```usda
#usda 1.0
(
    doc = "Cognitive Bridge Composition Stage — USDA Composition Proof (proj_usda_proof)"
    subLayers = [
        @./session_local.usda@,
        @./domain_inherits.usda@,
        @./hypothesis_variants.usda@,
        @./evidence_refs.usda@,
        @./deferred_payloads.usda@,
        @./safety_specializes.usda@,
    ]
)

# USD composition resolves opinions in sublayer order.
# session_local.usda (LOCAL, arc=10) is listed first and
# therefore strongest — matching LIVRPS semantics exactly.
#
# When two sublayers define the same attribute on the same
# prim path, the earlier sublayer wins. This is mechanically
# identical to the IntEnum sorting in CompositionStage.resolve().
```

#### session_local.usda (LOCAL, arc=10, strongest)

```usda
#usda 1.0
(
    doc = "LOCAL assertions (arc=10) — verified, high-confidence"
)

def Scope "architecture" {
    def Scope "database" {
        def Scope "engine" (
            doc = "Use PostgreSQL — verified via production benchmarks"
        ) {
            custom string cb:content = "Use PostgreSQL — verified via production benchmarks"
            custom string cb:assertion_id = "ast_f648a96e45b3"
            custom string cb:author = "ai"
            custom float cb:confidence = 0.95
            custom string cb:assumption_status = "live"
            custom string cb:falsifiable_if = "If a controlled benchmark shows another engine exceeds PostgreSQL throughput by more than 20% at our write load profile"
        }

    }

}
```

Note: `cb:falsifiable_if` is present because LOCAL assertions are required by
schema to declare how they can be proven wrong (Popperian falsifiability gate).
The Pydantic validator on `Assertion` rejects LOCAL assertions that omit this
field — it is not a soft warning, it is a hard schema rejection.

#### domain_inherits.usda (INHERITS, arc=20)

```usda
#usda 1.0
(
    doc = "INHERITS assertions (arc=20) — domain patterns"
)

def Scope "architecture" {
    def Scope "database" {
        def Scope "engine" (
            doc = "Use a relational database (domain pattern)"
        ) {
            custom string cb:content = "Use a relational database (domain pattern)"
            custom string cb:assertion_id = "ast_e3774c68f1b2"
            custom string cb:author = "ai"
            custom float cb:confidence = 0.7
            custom string cb:assumption_status = "live"
        }

    }

}
```

#### hypothesis_variants.usda (VARIANT_SET, arc=30)

```usda
#usda 1.0
(
    doc = "VARIANT_SET assertions (arc=30) — competing hypotheses"
)

# No variant sets or variant-arc assertions.
```

The scenario has no VARIANT_SET-arc assertions, so this sublayer is
empty. When VariantSets exist, this file contains actual USD `variantSet`
blocks — see Section 2.

#### evidence_refs.usda (REFERENCES, arc=40)

```usda
#usda 1.0
(
    doc = "REFERENCES assertions (arc=40) — external citations"
)

def Scope "architecture" {
    def Scope "database" {
        def Scope "engine" (
            doc = "User prefers MongoDB"
        ) {
            custom string cb:content = "User prefers MongoDB"
            custom string cb:assertion_id = "ast_619e462bd7fe"
            custom string cb:author = "user"
            custom float cb:confidence = 0.8
            custom string cb:assumption_status = "live"
        }

    }

}
```

#### deferred_payloads.usda (PAYLOADS, arc=50)

```usda
#usda 1.0
(
    doc = "PAYLOADS assertions (arc=50) — known unknowns"
)

def Scope "architecture" {
    def Scope "database" {
        def Scope "engine" (
            doc = "DynamoDB benchmarks exist but not loaded"
        ) {
            custom string cb:content = "DynamoDB benchmarks exist but not loaded"
            custom string cb:assertion_id = "ast_4cf30c5cbb73"
            custom string cb:author = "external"
            custom float cb:confidence = 0.5
            custom string cb:assumption_status = "live"
        }

    }

}
```

#### safety_specializes.usda (SPECIALIZES, arc=60, weakest)

```usda
#usda 1.0
(
    doc = "SPECIALIZES assertions (arc=60) — baseline knowledge"
)

def Scope "architecture" {
    def Scope "database" {
        def Scope "engine" (
            doc = "Default to SQLite for development"
        ) {
            custom string cb:content = "Default to SQLite for development"
            custom string cb:assertion_id = "ast_f2ddcba83147"
            custom string cb:author = "ai"
            custom float cb:confidence = 0.4
            custom string cb:assumption_status = "live"
        }

    }

}
```

### Resolution

Both SQL-based `CompositionStage.resolve()` and USDA text-based
`resolve_via_text()` agree:

**Winner:** LOCAL — "Use PostgreSQL — verified via production benchmarks"

The LOCAL assertion wins because `session_local.usda` is the first
sublayer in `stage.usda`. USD composition resolves sublayer opinions
in order — first listed = strongest. This IS LIVRPS.

The `check_consistency()` function compares both resolutions and returns
an empty discrepancy list for this scenario. Zero discrepancies.

Cascade verified by `TestLIVRPSFullCascade`:

| Arc removed | New winner |
|-------------|------------|
| (none removed) | LOCAL |
| LOCAL removed | INHERITS |
| LOCAL + INHERITS removed | REFERENCES |
| Only PAYLOADS + SPECIALIZES remain | PAYLOADS |
| Only SPECIALIZES remains | SPECIALIZES |

### Overridden Opinions (Shadow Stack)

All other assertions remain in their respective `.usda` files.
They are composed away but not deleted. The SQL shadow stack for this
scenario contains exactly these four entries in arc order:

```
INHERITS(20):  "Use a relational database (domain pattern)"
REFERENCES(40): "User prefers MongoDB"
PAYLOADS(50):  "DynamoDB benchmarks exist but not loaded"
SPECIALIZES(60): "Default to SQLite for development"
```

This matches the non-destructive invariant: retracted assertions stay
in the database, and the composition stage recomputes winners
dynamically. The USDA layer files are the serialized form of this
non-destructive state.

---

## 2. Variant Set Proof

When competing hypotheses exist without a clear winner, the system
creates a `VariantSet`. The USDA exporter renders this as an actual
USD `variantSet` block, not as a plain assertion.

Example: a `VariantSet` named "Database Choice" at
`/architecture/database` with two variants (PostgreSQL, MongoDB)
produces the following in `hypothesis_variants.usda`:

```usda
#usda 1.0
(
    doc = "VARIANT_SET assertions (arc=30) — competing hypotheses"
)

over Scope "architecture" (
) {
    over Scope "database" (
        prepend variantSets = ["database_choice"]
    ) {
        variantSet "database_choice" = {
            "postgresql" {
                custom string cb:content = "Use PostgreSQL for ACID guarantees."
                custom string[] cb:evidence_for = ["https://pgbench.example.com/results"]
            }
            "mongodb" {
                custom string cb:content = "Use MongoDB for document flexibility."
            }
        }
    }
}
```

Key properties:
- The VariantSet name is normalised to snake_case (`database_choice`).
- Each variant becomes a named selection inside the USD `variantSet` block.
- Evidence is written as `cb:evidence_for` string arrays.
- Resolved VariantSets (`resolved=True`) are excluded from the export.
  Only active hypothesis branches appear in the composition stage.

Verified by `TestVariantComposition` (6 tests).

---

## 3. Dependency DAG Proof

Assertions can declare logical dependencies on other topic paths via
`depends_on_paths`. These are exported as `cb:depends_on_paths`
string array attributes in the USDA prim.

Example: an assertion at `/architecture/database/engine` that depends
on the storage layer decision:

```usda
def Scope "architecture" {
    def Scope "database" {
        def Scope "engine" (
            doc = "Engine choice depends on storage layer decision."
        ) {
            custom string cb:content = "Engine choice depends on storage layer decision."
            custom string cb:assertion_id = "ast_abc123"
            custom string cb:author = "ai"
            custom float cb:confidence = 0.5
            custom string cb:assumption_status = "live"
            custom string[] cb:depends_on_paths = ["/architecture/storage"]
        }

    }

}
```

When the winning assertion at `/architecture/storage` changes (e.g.,
a new assertion at a stronger arc overrides the current winner), the
cascade engine traverses the DAG and flags all dependents as
`CHALLENGED`. This maps directly to USD's prim hierarchy: the `cb:depends_on_paths`
attribute encodes the DAG edges in a form that is both machine-readable
by the cascade engine and human-readable in the USDA file.

The `active=False` invariant is also verified here: retracted assertions
(those with `active=False`) are excluded from the USDA export. They
exist in the SQLite database but are not written to any sublayer file.
The USDA stage therefore represents only the currently-active
epistemic state.

Verified by `TestDependencyInUSDA` (5 tests).

---

## 4. Consistency Verification

For every test configuration, SQL and USDA resolution produce identical
winners at every topic path. Zero discrepancies across all tested
scenarios.

| Scenario | Paths | Assertions | Discrepancies |
|----------|-------|------------|---------------|
| All five arcs at same path | 1 | 5 | 0 |
| Three paths, mixed arcs | 3 | 5 | 0 |
| Single assertion, single path | 1 | 1 | 0 |
| Dependency-linked assertions | 2 | 2 | 0 |
| Mix of active and retracted | 1 | 3 (2 active) | 0 |
| **Total** | | | **0** |

Each table row is verified one-to-one by `test_scenario_1` through
`test_scenario_5`. Separately,
`test_zero_discrepancy_invariant_holds_for_all_scenarios` runs its own five
configurations (all-five-arcs, only-SPECIALIZES, only-INHERITS,
two-different-paths, empty-stage) in a single assertion and confirms the
total discrepancy count is zero.

Beyond these configurations, the SQL/USDA equivalence is hardened against
same-path/same-arc opinions, special-character content (the escape round
trip), and VariantSet layers by the resolver's regression suite in
`tests/test_bridge/test_usda_resolve.py`.

---

## 5. Structural Correspondence

| Cognitive Bridge Concept | USD Concept | Mapping |
|--------------------------|-------------|---------|
| `topic_path` | Prim path | 1:1 — the regex `^(/[a-z][a-z0-9_]*)+$` already enforces valid prim path syntax |
| `CompositionArc.LOCAL` | Sublayer opinion (first sublayer) | Strongest sublayer listed first in `subLayers` array |
| `CompositionArc.INHERITS` | Inherits arc | Second sublayer — domain-level inheritance |
| `CompositionArc.VARIANT_SET` | `variantSets` declaration | Competing hypotheses as named variant selections |
| `CompositionArc.REFERENCES` | References arc | External authority — user preferences, citations |
| `CompositionArc.PAYLOADS` | Payload arc | Lazy-loaded evidence — exists but not yet evaluated |
| `CompositionArc.SPECIALIZES` | Specializes arc | Baseline knowledge — always overridable |
| `resolve()` | USD composition | LIVRPS IntEnum ordering = sublayer ordering |
| Shadow stack | Composed-away opinions | Present in sublayer files, not in resolved state |
| Non-destructive invariant | USD layering | Layers accumulate, never overwrite |
| `depends_on_paths` | Prim hierarchy edges | DAG encoded as `cb:depends_on_paths` string arrays |
| `active=False` | Excluded from export | Retracted claims absent from stage; present in DB |
| `VariantSet` | USD `variantSet` block | Competing hypotheses as named variant selections |

---

## 6. Test Inventory

All tests are in `tests/test_bridge/test_usda_patent_evidence.py`.

| Class | Count | What It Proves |
|-------|-------|----------------|
| `TestLIVRPSFullCascade` | 11 | Arc priority cascade, sublayer order, SQL/USDA agreement |
| `TestVariantComposition` | 6 | VariantSet USD block generation, exclusion of resolved sets |
| `TestDependencyInUSDA` | 5 | `depends_on_paths` encoding, `active=False` exclusion |
| `TestConsistencyAcrossScenarios` | 6 | Zero discrepancies across 5 distinct stage configurations |
| **Total** | **28** | |

Run the full suite:

```
python -m pytest tests/test_bridge/test_usda_patent_evidence.py -v
```

Expected output: 28 passed, 0 failed, 0 skipped.
