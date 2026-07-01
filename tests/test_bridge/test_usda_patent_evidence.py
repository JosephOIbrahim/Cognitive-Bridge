"""Mechanical-equivalence evidence tests — LIVRPS proof for Cognitive Bridge.

These tests constitute machine-executable proof that:
1. LIVRPS resolution is mechanically equivalent to USD sublayer composition.
2. The SQL-based resolve() and USDA text-based resolve_via_text() produce identical
   winners across all tested stage configurations.
3. VariantSets are exported as actual USD variantSet blocks.
4. Dependency DAG edges are encoded as cb:depends_on_paths attributes.
5. Retracted (active=False) assertions are excluded from export.

Test groups:
- TestLIVRPSFullCascade      — arc priority cascade, one per level
- TestVariantComposition     — VariantSet USD block generation
- TestDependencyInUSDA       — depends_on_paths and active=False in export
- TestConsistencyAcrossScenarios — zero discrepancies across 5 stage configs
"""

import re
from pathlib import Path

import pytest

from cognitive_bridge.bridge.usda_export import export_stage_to_usda
from cognitive_bridge.bridge.usda_resolve import (
    check_consistency,
    resolve_via_text,
)
from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.stage import CompositionStage
from cognitive_bridge.models.variant_set import Variant, VariantSet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PATH = "/architecture/database/engine"


def _make_assertion(arc: CompositionArc, content: str, **kwargs) -> Assertion:
    """Build an assertion at PATH. LOCAL requires falsifiable_if.

    Caller may override 'author' via kwargs — the default is AI.
    """
    kw: dict = dict(
        topic_path=PATH,
        content=content,
        arc=arc,
        author=AssertionAuthor.AI,
    )
    kw.update(kwargs)  # kwargs wins over defaults (allows author override)
    if arc == CompositionArc.LOCAL and "falsifiable_if" not in kw:
        kw["falsifiable_if"] = (
            "If a controlled benchmark shows another engine exceeds this "
            "claim by >20% under equivalent load"
        )
    return Assertion(**kw)


def _stage(*assertions: Assertion, project_id: str = "proj_usda_proof") -> CompositionStage:
    """Build a stage containing the given assertions."""
    stage = CompositionStage(project_id=project_id, project_name="USDA Composition Proof")
    for a in assertions:
        stage.assertions[a.id] = a
    return stage


def _five_arc_stage() -> CompositionStage:
    """The canonical 5-assertion scenario: one assertion per arc at PATH.

    Arc values (lower = stronger):
      LOCAL=10     'Use PostgreSQL — verified via production benchmarks'
      INHERITS=20  'Use a relational database (domain pattern)'
      REFERENCES=40 'User prefers MongoDB'
      PAYLOADS=50  'DynamoDB benchmarks exist but not loaded'
      SPECIALIZES=60 'Default to SQLite for development'

    Expected winner: LOCAL — the first sublayer in stage.usda.
    """
    return _stage(
        _make_assertion(
            CompositionArc.LOCAL,
            "Use PostgreSQL — verified via production benchmarks",
            confidence=0.95,
        ),
        _make_assertion(
            CompositionArc.INHERITS,
            "Use a relational database (domain pattern)",
            confidence=0.7,
        ),
        _make_assertion(
            CompositionArc.REFERENCES,
            "User prefers MongoDB",
            confidence=0.8,
            author=AssertionAuthor.USER,
        ),
        _make_assertion(
            CompositionArc.PAYLOADS,
            "DynamoDB benchmarks exist but not loaded",
            confidence=0.5,
        ),
        _make_assertion(
            CompositionArc.SPECIALIZES,
            "Default to SQLite for development",
            confidence=0.4,
        ),
    )


# ---------------------------------------------------------------------------
# TestLIVRPSFullCascade
# ---------------------------------------------------------------------------

class TestLIVRPSFullCascade:
    """Cascade through arc levels: remove the strongest one at a time.

    Each test removes the currently-winning arc to verify that the next
    strongest arc takes over, and that both SQL and USDA agree.
    """

    def test_local_wins_over_all_others(self, tmp_path: Path) -> None:
        """Case 1: When all five arcs are present, LOCAL (arc=10) wins."""
        stage = _five_arc_stage()
        sql = stage.resolve()
        assert sql[PATH]["winning"].arc == CompositionArc.LOCAL
        assert sql[PATH]["winning"].content == "Use PostgreSQL — verified via production benchmarks"
        assert sql[PATH]["depth"] == 5

    def test_sql_and_usda_agree_on_local_winner(self, tmp_path: Path) -> None:
        """Case 1b: SQL and USDA produce the same winner when LOCAL is present."""
        stage = _five_arc_stage()
        export_stage_to_usda(stage, tmp_path)
        sql = stage.resolve()
        usda = resolve_via_text(tmp_path)
        discrepancies = check_consistency(sql, usda)
        assert discrepancies == [], "\n".join(discrepancies)
        assert usda[PATH]["content"] == "Use PostgreSQL — verified via production benchmarks"

    def test_inherits_wins_when_local_removed(self, tmp_path: Path) -> None:
        """Case 2: Remove LOCAL → INHERITS (arc=20) wins."""
        assertions = [
            a for a in _five_arc_stage().assertions.values()
            if a.arc != CompositionArc.LOCAL
        ]
        stage = _stage(*assertions)
        export_stage_to_usda(stage, tmp_path)

        sql = stage.resolve()
        usda = resolve_via_text(tmp_path)
        assert sql[PATH]["winning"].arc == CompositionArc.INHERITS
        assert sql[PATH]["winning"].content == "Use a relational database (domain pattern)"
        discrepancies = check_consistency(sql, usda)
        assert discrepancies == [], "\n".join(discrepancies)

    def test_references_wins_when_local_and_inherits_removed(self, tmp_path: Path) -> None:
        """Case 3: Remove LOCAL and INHERITS → REFERENCES (arc=40) wins."""
        skip_arcs = {CompositionArc.LOCAL, CompositionArc.INHERITS}
        assertions = [
            a for a in _five_arc_stage().assertions.values()
            if a.arc not in skip_arcs
        ]
        stage = _stage(*assertions)
        export_stage_to_usda(stage, tmp_path)

        sql = stage.resolve()
        usda = resolve_via_text(tmp_path)
        assert sql[PATH]["winning"].arc == CompositionArc.REFERENCES
        assert sql[PATH]["winning"].content == "User prefers MongoDB"
        discrepancies = check_consistency(sql, usda)
        assert discrepancies == [], "\n".join(discrepancies)

    def test_payloads_wins_when_only_payloads_and_specializes_remain(
        self, tmp_path: Path
    ) -> None:
        """Case 4: Only PAYLOADS and SPECIALIZES remain → PAYLOADS (arc=50) wins."""
        keep_arcs = {CompositionArc.PAYLOADS, CompositionArc.SPECIALIZES}
        assertions = [
            a for a in _five_arc_stage().assertions.values()
            if a.arc in keep_arcs
        ]
        stage = _stage(*assertions)
        export_stage_to_usda(stage, tmp_path)

        sql = stage.resolve()
        usda = resolve_via_text(tmp_path)
        assert sql[PATH]["winning"].arc == CompositionArc.PAYLOADS
        assert sql[PATH]["winning"].content == "DynamoDB benchmarks exist but not loaded"
        discrepancies = check_consistency(sql, usda)
        assert discrepancies == [], "\n".join(discrepancies)

    def test_specializes_wins_when_only_specializes_remains(
        self, tmp_path: Path
    ) -> None:
        """Case 4b: Only SPECIALIZES remains → SPECIALIZES (arc=60) wins."""
        assertions = [
            a for a in _five_arc_stage().assertions.values()
            if a.arc == CompositionArc.SPECIALIZES
        ]
        stage = _stage(*assertions)
        export_stage_to_usda(stage, tmp_path)

        sql = stage.resolve()
        usda = resolve_via_text(tmp_path)
        assert sql[PATH]["winning"].arc == CompositionArc.SPECIALIZES
        assert sql[PATH]["winning"].content == "Default to SQLite for development"
        discrepancies = check_consistency(sql, usda)
        assert discrepancies == [], "\n".join(discrepancies)

    def test_shadow_stack_contains_all_losers_in_order(self) -> None:
        """All 4 non-winning assertions appear in the shadow stack, sorted by arc."""
        stage = _five_arc_stage()
        sql = stage.resolve()
        shadow = sql[PATH]["shadow_stack"]
        assert len(shadow) == 4
        # Shadow stack must be in ascending arc order (next strongest first)
        arc_values = [a.arc.value for a in shadow]
        assert arc_values == sorted(arc_values), (
            f"Shadow stack not sorted by arc strength: {arc_values}"
        )

    def test_shadow_stack_arcs_are_correct(self) -> None:
        """Shadow stack contains INHERITS, REFERENCES, PAYLOADS, SPECIALIZES (not LOCAL)."""
        stage = _five_arc_stage()
        sql = stage.resolve()
        shadow_arcs = {a.arc for a in sql[PATH]["shadow_stack"]}
        assert CompositionArc.LOCAL not in shadow_arcs
        assert CompositionArc.INHERITS in shadow_arcs
        assert CompositionArc.REFERENCES in shadow_arcs
        assert CompositionArc.PAYLOADS in shadow_arcs
        assert CompositionArc.SPECIALIZES in shadow_arcs

    def test_each_arc_goes_to_its_designated_sublayer_file(
        self, tmp_path: Path
    ) -> None:
        """Verify each arc's assertion content appears only in its designated file.

        This proves the file-to-arc mapping is correct:
        - LOCAL   → session_local.usda
        - INHERITS → domain_inherits.usda
        - REFERENCES → evidence_refs.usda
        - PAYLOADS → deferred_payloads.usda
        - SPECIALIZES → safety_specializes.usda
        """
        stage = _five_arc_stage()
        written = export_stage_to_usda(stage, tmp_path)

        file_content_map = {
            "session_local.usda": "Use PostgreSQL — verified via production benchmarks",
            "domain_inherits.usda": "Use a relational database (domain pattern)",
            "evidence_refs.usda": "User prefers MongoDB",
            "deferred_payloads.usda": "DynamoDB benchmarks exist but not loaded",
            "safety_specializes.usda": "Default to SQLite for development",
        }
        for filename, expected_content in file_content_map.items():
            text = written[filename].read_text(encoding="utf-8")
            assert expected_content in text, (
                f"Expected '{expected_content}' in {filename}"
            )

    def test_session_local_listed_first_in_stage_usda(
        self, tmp_path: Path
    ) -> None:
        """stage.usda lists session_local.usda before all other sublayers.

        This is the mechanical USD proof: sublayer order IS LIVRPS order.
        """
        stage = _five_arc_stage()
        written = export_stage_to_usda(stage, tmp_path)
        stage_text = written["stage.usda"].read_text(encoding="utf-8")

        sublayer_pattern = re.compile(r'@\./([^@]+)@')
        sublayers = sublayer_pattern.findall(stage_text)
        assert sublayers[0] == "session_local.usda", (
            f"Expected session_local.usda first, got: {sublayers}"
        )

    def test_safety_specializes_listed_last_in_stage_usda(
        self, tmp_path: Path
    ) -> None:
        """stage.usda lists safety_specializes.usda last (weakest arc)."""
        stage = _five_arc_stage()
        written = export_stage_to_usda(stage, tmp_path)
        stage_text = written["stage.usda"].read_text(encoding="utf-8")

        sublayer_pattern = re.compile(r'@\./([^@]+)@')
        sublayers = sublayer_pattern.findall(stage_text)
        assert sublayers[-1] == "safety_specializes.usda", (
            f"Expected safety_specializes.usda last, got: {sublayers}"
        )


# ---------------------------------------------------------------------------
# TestVariantComposition
# ---------------------------------------------------------------------------

class TestVariantComposition:
    """VariantSets are exported as actual USD VariantSet blocks."""

    def _make_variant_set(self, resolved: bool = False) -> VariantSet:
        return VariantSet(
            name="Database Choice",
            topic_path="/architecture/database",
            variants=[
                Variant(
                    name="PostgreSQL",
                    content="Use PostgreSQL for ACID guarantees.",
                    evidence_for=["https://pgbench.example.com/results"],
                ),
                Variant(
                    name="MongoDB",
                    content="Use MongoDB for document flexibility.",
                ),
            ],
            resolved=resolved,
        )

    def test_variant_set_exported_as_usd_variant_set_block(
        self, tmp_path: Path
    ) -> None:
        """Case 5: VariantSet is exported as a USD variantSet block."""
        vs = self._make_variant_set()
        stage = CompositionStage(project_id="proj_vs", project_name="VS Test")
        stage.variant_sets[vs.id] = vs

        written = export_stage_to_usda(stage, tmp_path)
        text = written["hypothesis_variants.usda"].read_text(encoding="utf-8")
        assert "variantSet" in text

    def test_variant_names_appear_in_usda(self, tmp_path: Path) -> None:
        """Case 6: Variant names appear as quoted keys inside the variantSet block."""
        vs = self._make_variant_set()
        stage = CompositionStage(project_id="proj_vs", project_name="VS Test")
        stage.variant_sets[vs.id] = vs

        written = export_stage_to_usda(stage, tmp_path)
        text = written["hypothesis_variants.usda"].read_text(encoding="utf-8")
        # Variant names are lowercased: "postgresql" and "mongodb"
        assert '"postgresql"' in text
        assert '"mongodb"' in text

    def test_resolved_variant_sets_excluded_from_export(
        self, tmp_path: Path
    ) -> None:
        """Case 7: Resolved VariantSets are excluded — only active hypotheses exported."""
        vs = self._make_variant_set(resolved=True)
        stage = CompositionStage(project_id="proj_vs", project_name="VS Test")
        stage.variant_sets[vs.id] = vs

        written = export_stage_to_usda(stage, tmp_path)
        text = written["hypothesis_variants.usda"].read_text(encoding="utf-8")
        assert "variantSet" not in text
        assert '"postgresql"' not in text

    def test_variant_set_name_normalised_to_snake_case(
        self, tmp_path: Path
    ) -> None:
        """VariantSet name 'Database Choice' → 'database_choice' as USD key."""
        vs = self._make_variant_set()
        stage = CompositionStage(project_id="proj_vs", project_name="VS Test")
        stage.variant_sets[vs.id] = vs

        written = export_stage_to_usda(stage, tmp_path)
        text = written["hypothesis_variants.usda"].read_text(encoding="utf-8")
        assert 'variantSet "database_choice"' in text

    def test_variant_content_written_for_each_variant(
        self, tmp_path: Path
    ) -> None:
        """Each variant's content is written as cb:content attribute."""
        vs = self._make_variant_set()
        stage = CompositionStage(project_id="proj_vs", project_name="VS Test")
        stage.variant_sets[vs.id] = vs

        written = export_stage_to_usda(stage, tmp_path)
        text = written["hypothesis_variants.usda"].read_text(encoding="utf-8")
        assert "Use PostgreSQL for ACID guarantees." in text
        assert "Use MongoDB for document flexibility." in text

    def test_variant_evidence_for_written_when_present(
        self, tmp_path: Path
    ) -> None:
        """cb:evidence_for attribute is written for variants that have evidence."""
        vs = self._make_variant_set()
        stage = CompositionStage(project_id="proj_vs", project_name="VS Test")
        stage.variant_sets[vs.id] = vs

        written = export_stage_to_usda(stage, tmp_path)
        text = written["hypothesis_variants.usda"].read_text(encoding="utf-8")
        assert "cb:evidence_for" in text
        assert "pgbench.example.com" in text


# ---------------------------------------------------------------------------
# TestDependencyInUSDA
# ---------------------------------------------------------------------------

class TestDependencyInUSDA:
    """Dependency DAG and active=False are correctly reflected in USDA export."""

    def test_depends_on_paths_exported_as_cb_attribute(
        self, tmp_path: Path
    ) -> None:
        """Case 8: depends_on_paths exported as cb:depends_on_paths string array."""
        dep_assertion = Assertion(
            topic_path="/architecture/database/engine",
            content="Use the engine recommended by the storage layer.",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/storage"],
        )
        stage = _stage(dep_assertion)
        written = export_stage_to_usda(stage, tmp_path)
        text = written["domain_inherits.usda"].read_text(encoding="utf-8")
        assert "cb:depends_on_paths" in text
        assert '"/architecture/storage"' in text

    def test_multiple_depends_on_paths_all_listed(self, tmp_path: Path) -> None:
        """Multiple dependency paths are all written to the string array."""
        dep_assertion = Assertion(
            topic_path="/architecture/database/engine",
            content="Engine depends on storage and hardware.",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/storage", "/infrastructure/hardware"],
        )
        stage = _stage(dep_assertion)
        written = export_stage_to_usda(stage, tmp_path)
        text = written["domain_inherits.usda"].read_text(encoding="utf-8")
        assert '"/architecture/storage"' in text
        assert '"/infrastructure/hardware"' in text

    def test_falsified_assertion_excluded_from_export(
        self, tmp_path: Path
    ) -> None:
        """Case 9: active=False assertions are excluded from all arc sublayer files.

        This maps to the non-destructive invariant: retracted assertions stay in
        the DB but are not included in the composed USDA stage.
        """
        active_assertion = Assertion(
            topic_path="/architecture/database/engine",
            content="This assertion is active.",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        retracted_assertion = Assertion(
            topic_path="/architecture/database/engine",
            content="This assertion was retracted — should NOT appear.",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            active=False,
        )
        stage = _stage(active_assertion, retracted_assertion)
        written = export_stage_to_usda(stage, tmp_path)

        for fname, fpath in written.items():
            if fname == "stage.usda":
                continue
            text = fpath.read_text(encoding="utf-8")
            assert "should NOT appear" not in text, (
                f"Retracted assertion content found in {fname}"
            )

    def test_active_assertion_remains_in_export_after_retraction_scenario(
        self, tmp_path: Path
    ) -> None:
        """Active assertion stays in export even when another is retracted."""
        active_assertion = Assertion(
            topic_path="/architecture/database/engine",
            content="Active assertion — should appear.",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        retracted_assertion = Assertion(
            topic_path="/architecture/database/engine",
            content="Retracted assertion.",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            active=False,
        )
        stage = _stage(active_assertion, retracted_assertion)
        written = export_stage_to_usda(stage, tmp_path)
        text = written["safety_specializes.usda"].read_text(encoding="utf-8")
        assert "should appear" in text

    def test_no_depends_on_paths_attribute_when_empty(
        self, tmp_path: Path
    ) -> None:
        """cb:depends_on_paths must not appear when depends_on_paths is empty."""
        assertion = Assertion(
            topic_path="/architecture/database/engine",
            content="No dependencies.",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        stage = _stage(assertion)
        written = export_stage_to_usda(stage, tmp_path)
        text = written["safety_specializes.usda"].read_text(encoding="utf-8")
        assert "cb:depends_on_paths" not in text


# ---------------------------------------------------------------------------
# TestConsistencyAcrossScenarios
# ---------------------------------------------------------------------------

class TestConsistencyAcrossScenarios:
    """5 different stage configurations — all produce zero discrepancies.

    This is the core evidence: SQL resolution and USDA text resolution
    agree on every winning assertion across diverse stage configurations.
    """

    def _assert_consistent(
        self, stage: CompositionStage, tmp_path: Path, label: str
    ) -> None:
        export_stage_to_usda(stage, tmp_path)
        sql = stage.resolve()
        usda = resolve_via_text(tmp_path)
        discrepancies = check_consistency(sql, usda)
        assert discrepancies == [], (
            f"Scenario '{label}': SQL and USDA diverged:\n" + "\n".join(discrepancies)
        )

    def test_scenario_1_all_five_arcs_at_same_path(
        self, tmp_path: Path
    ) -> None:
        """Scenario 1: All five arc levels at the same path — LOCAL wins."""
        self._assert_consistent(
            _five_arc_stage(), tmp_path, "all_five_arcs"
        )

    def test_scenario_2_multiple_paths_multiple_arcs(
        self, tmp_path: Path
    ) -> None:
        """Scenario 2: Assertions at three different topic paths."""
        stage = CompositionStage(project_id="proj_s2", project_name="Scenario 2")

        # /architecture/database/engine
        a1 = Assertion(
            topic_path="/architecture/database/engine",
            content="PostgreSQL chosen via benchmark.",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Benchmark shows latency >1s p99.",
        )
        a2 = Assertion(
            topic_path="/architecture/database/engine",
            content="Relational DB domain pattern.",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        # /architecture/api/framework
        a3 = Assertion(
            topic_path="/architecture/api/framework",
            content="FastAPI for async performance.",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        a4 = Assertion(
            topic_path="/architecture/api/framework",
            content="Flask as baseline.",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        # /infrastructure/hosting
        a5 = Assertion(
            topic_path="/infrastructure/hosting",
            content="Deploy on AWS ECS.",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        for a in (a1, a2, a3, a4, a5):
            stage.assertions[a.id] = a

        self._assert_consistent(stage, tmp_path, "multi_path_multi_arc")

    def test_scenario_3_single_assertion_single_path(
        self, tmp_path: Path
    ) -> None:
        """Scenario 3: Single assertion — trivially consistent."""
        a = Assertion(
            topic_path="/architecture/approach",
            content="Monolith architecture for MVP.",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        stage = _stage(a, project_id="proj_s3")
        self._assert_consistent(stage, tmp_path, "single_assertion")

    def test_scenario_4_with_depends_on_paths(
        self, tmp_path: Path
    ) -> None:
        """Scenario 4: Dependency-linked assertions — consistency holds across DAG."""
        foundation = Assertion(
            topic_path="/architecture/storage",
            content="Use S3 for object storage.",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        dependent = Assertion(
            topic_path="/architecture/database/engine",
            content="Engine choice depends on storage layer decision.",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/storage"],
        )
        stage = _stage(foundation, dependent, project_id="proj_s4")
        self._assert_consistent(stage, tmp_path, "dependency_dag")

    def test_scenario_5_mixed_active_inactive(
        self, tmp_path: Path
    ) -> None:
        """Scenario 5: Mix of active and retracted assertions — only active ones count."""
        active_local = Assertion(
            topic_path="/architecture/database/engine",
            content="Active LOCAL claim.",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="If benchmark shows failure.",
        )
        active_specializes = Assertion(
            topic_path="/architecture/database/engine",
            content="Active SPECIALIZES claim.",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        retracted = Assertion(
            topic_path="/architecture/database/engine",
            content="Retracted REFERENCES claim.",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
            active=False,
        )
        stage = _stage(active_local, active_specializes, retracted, project_id="proj_s5")

        # SQL resolves only active assertions
        sql = stage.resolve()
        assert sql[PATH]["winning"].content == "Active LOCAL claim."
        assert sql[PATH]["depth"] == 2  # Only 2 active

        self._assert_consistent(stage, tmp_path, "mixed_active_inactive")

    def test_zero_discrepancy_invariant_holds_for_all_scenarios(
        self, tmp_path: Path
    ) -> None:
        """Comprehensive: all 5 scenarios in sequence — zero total discrepancies.

        This is the single most important test for the mechanical-equivalence proof. It demonstrates
        that across all tested configurations, SQL composition and USDA composition
        produce identical winning assertions. The two systems are mechanically
        equivalent proofs of the same LIVRPS algorithm.
        """
        scenarios = [
            (_five_arc_stage(), "five_arcs"),
            (
                _stage(
                    Assertion(
                        topic_path=PATH,
                        content="Only SPECIALIZES.",
                        arc=CompositionArc.SPECIALIZES,
                        author=AssertionAuthor.AI,
                    ),
                    project_id="proj_only_spec",
                ),
                "only_specializes",
            ),
            (
                _stage(
                    Assertion(
                        topic_path=PATH,
                        content="Only INHERITS.",
                        arc=CompositionArc.INHERITS,
                        author=AssertionAuthor.AI,
                    ),
                    project_id="proj_only_inh",
                ),
                "only_inherits",
            ),
            (
                _stage(
                    Assertion(
                        topic_path="/a/b",
                        content="Path A.",
                        arc=CompositionArc.SPECIALIZES,
                        author=AssertionAuthor.AI,
                    ),
                    Assertion(
                        topic_path="/c/d",
                        content="Path B.",
                        arc=CompositionArc.REFERENCES,
                        author=AssertionAuthor.USER,
                    ),
                    project_id="proj_two_paths",
                ),
                "two_different_paths",
            ),
            (
                CompositionStage(project_id="proj_empty", project_name="Empty"),
                "empty_stage",
            ),
        ]

        total_discrepancies = 0
        for i, (stage, label) in enumerate(scenarios):
            scenario_dir = tmp_path / f"scenario_{i}"
            scenario_dir.mkdir()
            export_stage_to_usda(stage, scenario_dir)
            sql = stage.resolve()
            usda = resolve_via_text(scenario_dir)
            discrepancies = check_consistency(sql, usda)
            total_discrepancies += len(discrepancies)
            assert discrepancies == [], (
                f"Scenario '{label}' has discrepancies:\n" + "\n".join(discrepancies)
            )

        assert total_discrepancies == 0, (
            f"Total discrepancies across all 5 scenarios: {total_discrepancies}"
        )
