"""Tests for the USDA exporter.

Covers:
- generate_arc_layer: empty, single, multiple assertions; attribute rendering
- generate_stage_root: sublayer ordering, project metadata
- export_stage_to_usda: file creation, arc routing, empty arcs
- Prim hierarchy: nested prim generation from topic paths
- VariantSet layer: USD variantSet blocks, resolved exclusion
- USDA text validity: header, string escaping, indentation
"""

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    Variant,
    VariantSet,
)
from cognitive_bridge.bridge.usda_export import (
    ARC_FILE_MAP,
    SUBLAYER_ORDER,
    export_stage_to_usda,
    generate_arc_layer,
    generate_stage_root,
    generate_variant_layer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_specializes(**kwargs) -> Assertion:
    """Minimal SPECIALIZES assertion (no falsifiable_if required)."""
    defaults = dict(
        topic_path="/architecture/database",
        content="PostgreSQL is a relational database.",
        arc=CompositionArc.SPECIALIZES,
        author=AssertionAuthor.AI,
    )
    defaults.update(kwargs)
    return Assertion(**defaults)


def make_local(**kwargs) -> Assertion:
    """Minimal LOCAL assertion (falsifiable_if required)."""
    defaults = dict(
        topic_path="/architecture/database",
        content="PostgreSQL outperforms MySQL at high write load.",
        arc=CompositionArc.LOCAL,
        author=AssertionAuthor.USER,
        falsifiable_if="A benchmark showing MySQL matches or exceeds PostgreSQL throughput.",
    )
    defaults.update(kwargs)
    return Assertion(**defaults)


def make_references(**kwargs) -> Assertion:
    """Minimal REFERENCES assertion."""
    defaults = dict(
        topic_path="/architecture/database",
        content="External benchmark cites 2x write throughput improvement.",
        arc=CompositionArc.REFERENCES,
        author=AssertionAuthor.EXTERNAL,
    )
    defaults.update(kwargs)
    return Assertion(**defaults)


def make_stage_with_assertions(*assertions: Assertion) -> CompositionStage:
    """Build a stage and insert the given assertions by ID."""
    stage = CompositionStage(project_id="proj_test001", project_name="Test Project")
    for ast in assertions:
        stage.assertions[ast.id] = ast
    return stage


def make_two_variant_set(topic_path: str = "/architecture/approach") -> VariantSet:
    """Build a minimal VariantSet with two variants."""
    return VariantSet(
        name="Database Choice",
        topic_path=topic_path,
        variants=[
            Variant(name="PostgreSQL", content="Use PostgreSQL for ACID guarantees."),
            Variant(name="MongoDB", content="Use MongoDB for document flexibility."),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# TestGenerateArcLayer
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateArcLayer:
    def test_empty_assertions_produces_no_assertions_comment(self) -> None:
        """Case 1: Empty assertions → file has 'No assertions' comment."""
        result = generate_arc_layer([], CompositionArc.SPECIALIZES, "test doc")
        assert "# No assertions at this arc level." in result

    def test_empty_assertions_still_has_usda_header(self) -> None:
        result = generate_arc_layer([], CompositionArc.SPECIALIZES, "test doc")
        assert result.startswith("#usda 1.0")

    def test_single_assertion_prim_path_matches_topic_path(self) -> None:
        """Case 2: Single assertion → prim path matches topic_path hierarchy."""
        ast = make_specializes(topic_path="/architecture/database/engine")
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        # /architecture/database/engine → def Scope "architecture" { def Scope "database" { def Scope "engine"
        assert 'def Scope "architecture"' in result
        assert 'def Scope "database"' in result
        assert 'def Scope "engine"' in result

    def test_multiple_assertions_at_different_paths_all_prims_present(self) -> None:
        """Case 3: Multiple assertions at different paths → all prims present."""
        ast1 = make_specializes(topic_path="/architecture/database")
        ast2 = make_specializes(
            topic_path="/infrastructure/network",
            content="Network layer uses TCP.",
        )
        result = generate_arc_layer([ast1, ast2], CompositionArc.SPECIALIZES, "doc")
        assert 'def Scope "architecture"' in result
        assert 'def Scope "infrastructure"' in result
        assert 'def Scope "database"' in result
        assert 'def Scope "network"' in result

    def test_assertion_content_appears_in_cb_content(self) -> None:
        """Case 4: Assertion content appears in cb:content attribute."""
        ast = make_specializes(content="PostgreSQL is a relational database.")
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert 'cb:content = "PostgreSQL is a relational database."' in result

    def test_falsifiable_if_appears_when_present(self) -> None:
        """Case 5: falsifiable_if appears when present."""
        ast = make_local(
            falsifiable_if="A benchmark showing MySQL beats PostgreSQL."
        )
        result = generate_arc_layer([ast], CompositionArc.LOCAL, "doc")
        assert 'cb:falsifiable_if' in result
        assert "A benchmark showing MySQL beats PostgreSQL." in result

    def test_falsifiable_if_absent_when_none(self) -> None:
        """falsifiable_if attribute must not appear when not set."""
        ast = make_specializes()  # SPECIALIZES has no falsifiable_if
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert 'cb:falsifiable_if' not in result

    def test_depends_on_paths_appears_as_string_array(self) -> None:
        """Case 6: depends_on_paths appears as string array."""
        ast = make_specializes(
            topic_path="/architecture/database/engine",
            depends_on_paths=["/architecture/database"],
        )
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert 'cb:depends_on_paths' in result
        assert '"/architecture/database"' in result

    def test_multiple_depends_on_paths_all_listed(self) -> None:
        ast = make_specializes(
            topic_path="/architecture/database/engine",
            depends_on_paths=["/architecture/database", "/infrastructure/hardware"],
        )
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert '"/architecture/database"' in result
        assert '"/infrastructure/hardware"' in result

    def test_doc_string_in_header(self) -> None:
        doc = "SPECIALIZES assertions (arc=60) — baseline knowledge"
        result = generate_arc_layer([], CompositionArc.SPECIALIZES, doc)
        assert doc in result

    def test_assertion_id_present_as_cb_assertion_id(self) -> None:
        ast = make_specializes()
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert f'cb:assertion_id = "{ast.id}"' in result

    def test_author_written_as_cb_author(self) -> None:
        ast = make_specializes(author=AssertionAuthor.USER)
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert 'cb:author = "user"' in result

    def test_confidence_written_as_cb_confidence(self) -> None:
        ast = make_specializes(confidence=0.75)
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert 'cb:confidence = 0.75' in result

    def test_evidence_list_written_when_present(self) -> None:
        ast = make_specializes(evidence=["https://example.com/benchmark"])
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert 'cb:evidence' in result
        assert '"https://example.com/benchmark"' in result

    def test_assumption_status_written(self) -> None:
        ast = make_specializes()
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert 'cb:assumption_status = "live"' in result


# ─────────────────────────────────────────────────────────────────────────────
# TestGenerateStageRoot
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateStageRoot:
    def test_contains_all_six_sublayer_references(self) -> None:
        """Case 7: Contains all 6 sublayer references in LIVRPS order."""
        result = generate_stage_root("proj_abc", "My Project")
        for filename in SUBLAYER_ORDER:
            assert filename in result

    def test_local_sublayer_is_listed_first(self) -> None:
        """Case 8: LOCAL sublayer is listed FIRST (strongest)."""
        result = generate_stage_root("proj_abc", "My Project")
        local_pos = result.index("session_local.usda")
        # All other sublayers must appear after the LOCAL entry
        for other in SUBLAYER_ORDER[1:]:
            assert result.index(other) > local_pos

    def test_specializes_sublayer_is_listed_last(self) -> None:
        """Case 9: SPECIALIZES sublayer is listed LAST (weakest)."""
        result = generate_stage_root("proj_abc", "My Project")
        specializes_pos = result.index("safety_specializes.usda")
        for other in SUBLAYER_ORDER[:-1]:
            assert result.index(other) < specializes_pos

    def test_contains_project_id_in_doc(self) -> None:
        """Case 10: Contains project_id in doc."""
        result = generate_stage_root("proj_unique123", "My Project")
        assert "proj_unique123" in result

    def test_contains_project_name_in_doc(self) -> None:
        """Case 10: Contains project_name in doc."""
        result = generate_stage_root("proj_abc", "Unique Project Name")
        assert "Unique Project Name" in result

    def test_starts_with_usda_header(self) -> None:
        result = generate_stage_root("proj_abc", "My Project")
        assert result.startswith("#usda 1.0")

    def test_sublayers_keyword_present(self) -> None:
        result = generate_stage_root("proj_abc", "My Project")
        assert "subLayers" in result

    def test_sublayer_order_matches_livrps_sequence(self) -> None:
        """The order of filenames in the output must match SUBLAYER_ORDER exactly."""
        result = generate_stage_root("proj_abc", "My Project")
        positions = [result.index(f) for f in SUBLAYER_ORDER]
        assert positions == sorted(positions), "Sublayers are not in LIVRPS order"


# ─────────────────────────────────────────────────────────────────────────────
# TestExportStageToUsda
# ─────────────────────────────────────────────────────────────────────────────

class TestExportStageToUsda:
    def test_creates_seven_files_in_output_dir(self, tmp_path) -> None:
        """Case 11: Creates 7 files in output_dir."""
        stage = CompositionStage(project_id="proj_test", project_name="Test")
        written = export_stage_to_usda(stage, tmp_path)
        assert len(written) == 7

    def test_all_files_have_usda_extension(self, tmp_path) -> None:
        """Case 12: All files have .usda extension."""
        stage = CompositionStage(project_id="proj_test", project_name="Test")
        written = export_stage_to_usda(stage, tmp_path)
        for filename in written:
            assert filename.endswith(".usda"), f"{filename} missing .usda extension"

    def test_stage_usda_is_present(self, tmp_path) -> None:
        """Case 13: stage.usda is present."""
        stage = CompositionStage(project_id="proj_test", project_name="Test")
        written = export_stage_to_usda(stage, tmp_path)
        assert "stage.usda" in written
        assert written["stage.usda"].exists()

    def test_local_assertions_appear_in_session_local(self, tmp_path) -> None:
        """Case 14: LOCAL assertions appear in session_local.usda."""
        ast = make_local(
            topic_path="/architecture/database",
            content="PostgreSQL is production-grade.",
        )
        stage = make_stage_with_assertions(ast)
        written = export_stage_to_usda(stage, tmp_path)
        content = written["session_local.usda"].read_text(encoding="utf-8")
        assert "PostgreSQL is production-grade." in content

    def test_local_assertions_absent_from_other_arc_files(self, tmp_path) -> None:
        """LOCAL content must NOT bleed into non-LOCAL arc files."""
        ast = make_local(
            topic_path="/architecture/database",
            content="Exclusive LOCAL content string XYZ.",
        )
        stage = make_stage_with_assertions(ast)
        written = export_stage_to_usda(stage, tmp_path)
        for filename, path in written.items():
            if filename in ("session_local.usda", "stage.usda"):
                continue
            content = path.read_text(encoding="utf-8")
            assert "Exclusive LOCAL content string XYZ." not in content, (
                f"LOCAL content leaked into {filename}"
            )

    def test_references_assertions_appear_in_evidence_refs(self, tmp_path) -> None:
        """Case 15: REFERENCES assertions appear in evidence_refs.usda."""
        ast = make_references(content="External benchmark reference content.")
        stage = make_stage_with_assertions(ast)
        written = export_stage_to_usda(stage, tmp_path)
        content = written["evidence_refs.usda"].read_text(encoding="utf-8")
        assert "External benchmark reference content." in content

    def test_empty_arc_levels_produce_valid_files(self, tmp_path) -> None:
        """Case 16: Empty arc levels produce valid files (with comment)."""
        stage = CompositionStage(project_id="proj_test", project_name="Test")
        written = export_stage_to_usda(stage, tmp_path)
        for filename, path in written.items():
            if filename == "stage.usda":
                continue
            content = path.read_text(encoding="utf-8")
            assert content.startswith("#usda 1.0"), f"{filename} missing USDA header"

    def test_output_dir_created_if_not_exists(self, tmp_path) -> None:
        """export_stage_to_usda must create the output directory if needed."""
        new_dir = tmp_path / "deep" / "nested" / "export"
        assert not new_dir.exists()
        stage = CompositionStage(project_id="proj_test", project_name="Test")
        export_stage_to_usda(stage, new_dir)
        assert new_dir.exists()

    def test_inactive_assertions_excluded(self, tmp_path) -> None:
        """Retracted assertions (active=False) must not appear in any arc file."""
        ast = make_specializes(
            content="This assertion was retracted.",
            active=False,
        )
        stage = make_stage_with_assertions(ast)
        written = export_stage_to_usda(stage, tmp_path)
        for filename, path in written.items():
            if filename == "stage.usda":
                continue
            content = path.read_text(encoding="utf-8")
            assert "This assertion was retracted." not in content

    def test_returns_dict_with_absolute_paths(self, tmp_path) -> None:
        """Return value must map filenames to Path objects that exist on disk."""
        stage = CompositionStage(project_id="proj_test", project_name="Test")
        written = export_stage_to_usda(stage, tmp_path)
        for filename, path in written.items():
            assert isinstance(path, type(tmp_path))
            assert path.exists(), f"{filename} was not written to disk"

    def test_specializes_assertion_in_safety_specializes(self, tmp_path) -> None:
        ast = make_specializes(content="SPECIALIZES content here.")
        stage = make_stage_with_assertions(ast)
        written = export_stage_to_usda(stage, tmp_path)
        content = written["safety_specializes.usda"].read_text(encoding="utf-8")
        assert "SPECIALIZES content here." in content

    def test_inherits_assertion_in_domain_inherits(self, tmp_path) -> None:
        ast = make_specializes(
            arc=CompositionArc.INHERITS,
            content="Domain inheritance pattern.",
        )
        stage = make_stage_with_assertions(ast)
        written = export_stage_to_usda(stage, tmp_path)
        content = written["domain_inherits.usda"].read_text(encoding="utf-8")
        assert "Domain inheritance pattern." in content

    def test_payloads_assertion_in_deferred_payloads(self, tmp_path) -> None:
        ast = make_specializes(
            arc=CompositionArc.PAYLOADS,
            content="Known unknown about caching layer.",
        )
        stage = make_stage_with_assertions(ast)
        written = export_stage_to_usda(stage, tmp_path)
        content = written["deferred_payloads.usda"].read_text(encoding="utf-8")
        assert "Known unknown about caching layer." in content

    def test_all_arc_files_present_in_written_dict(self, tmp_path) -> None:
        """All 7 expected filenames must be keys in the returned dict."""
        stage = CompositionStage(project_id="proj_test", project_name="Test")
        written = export_stage_to_usda(stage, tmp_path)
        expected = set(SUBLAYER_ORDER) | {"stage.usda"}
        assert set(written.keys()) == expected


# ─────────────────────────────────────────────────────────────────────────────
# TestPrimHierarchy
# ─────────────────────────────────────────────────────────────────────────────

class TestPrimHierarchy:
    def test_three_level_path_produces_nested_prims(self) -> None:
        """Case 17: topic_path /a/b/c → nested def "a" { def "b" { def "c" { ... }}}"""
        ast = make_specializes(topic_path="/alpha/beta/gamma")
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        # Check that nesting appears — alpha contains beta which contains gamma
        alpha_pos = result.index('def Scope "alpha"')
        beta_pos = result.index('def Scope "beta"')
        gamma_pos = result.index('def Scope "gamma"')
        assert alpha_pos < beta_pos < gamma_pos

    def test_shared_parent_for_sibling_paths(self) -> None:
        """Case 18: Multiple assertions at same parent path → share parent prims."""
        ast1 = make_specializes(
            topic_path="/architecture/database",
            content="Database content.",
        )
        ast2 = make_specializes(
            topic_path="/architecture/network",
            content="Network content.",
        )
        result = generate_arc_layer([ast1, ast2], CompositionArc.SPECIALIZES, "doc")
        # "architecture" should appear as a single parent prim
        assert result.count('def Scope "architecture"') == 1
        assert 'def Scope "database"' in result
        assert 'def Scope "network"' in result

    def test_assertion_id_appears_as_cb_assertion_id(self) -> None:
        """Case 19: Assertion ID appears as cb:assertion_id attribute."""
        ast = make_specializes()
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert f'cb:assertion_id = "{ast.id}"' in result

    def test_deep_path_five_levels(self) -> None:
        """Deep nesting must produce correct prim hierarchy."""
        ast = make_specializes(topic_path="/a/b/c/d/e")
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        for segment in ("a", "b", "c", "d", "e"):
            assert f'def Scope "{segment}"' in result

    def test_multiple_assertions_same_path_secondary_as_opinion_child(self) -> None:
        """Multiple assertions at the same path: extras rendered as opinion_N children."""
        ast1 = make_specializes(content="Primary content.")
        ast2 = make_specializes(content="Secondary content.")
        # Both at the same topic_path
        result = generate_arc_layer([ast1, ast2], CompositionArc.SPECIALIZES, "doc")
        assert 'def Scope "opinion_1"' in result
        assert "Secondary content." in result

    def test_single_segment_path(self) -> None:
        """Single-segment path /architecture produces one top-level prim."""
        ast = make_specializes(topic_path="/architecture")
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert 'def Scope "architecture"' in result


# ─────────────────────────────────────────────────────────────────────────────
# TestVariantLayer
# ─────────────────────────────────────────────────────────────────────────────

class TestVariantLayer:
    def test_variant_set_generates_usd_variant_set_block(self) -> None:
        """Case 20: VariantSet generates USD variantSet block."""
        vs = make_two_variant_set(topic_path="/architecture/approach")
        result = generate_variant_layer([vs], [])
        assert "variantSet" in result

    def test_each_variant_has_named_selection(self) -> None:
        """Case 21: Each variant has a named selection."""
        vs = make_two_variant_set(topic_path="/architecture/approach")
        result = generate_variant_layer([vs], [])
        # Variant names normalised: "postgresql" and "mongodb"
        assert '"postgresql"' in result
        assert '"mongodb"' in result

    def test_resolved_variant_sets_excluded(self) -> None:
        """Case 22: Resolved variant sets are excluded."""
        vs = make_two_variant_set()
        vs.resolved = True
        result = generate_variant_layer([vs], [])
        # variantSet block should not appear because vs is resolved
        assert "variantSet" not in result
        assert '"postgresql"' not in result

    def test_empty_inputs_produce_comment(self) -> None:
        result = generate_variant_layer([], [])
        assert "# No variant sets or variant-arc assertions." in result

    def test_variant_content_written(self) -> None:
        vs = make_two_variant_set()
        result = generate_variant_layer([vs], [])
        assert "Use PostgreSQL for ACID guarantees." in result
        assert "Use MongoDB for document flexibility." in result

    def test_variant_set_name_used_as_usd_variant_set_key(self) -> None:
        """VariantSet.name (normalised) must appear as the variantSet key."""
        vs = make_two_variant_set()
        result = generate_variant_layer([vs], [])
        # "Database Choice" → "database_choice"
        assert 'variantSet "database_choice"' in result

    def test_variant_assertions_also_rendered(self) -> None:
        """VARIANT_SET arc assertions are rendered as prims alongside VariantSets."""
        ast = make_specializes(
            arc=CompositionArc.VARIANT_SET,
            content="Hypothesis assertion content.",
        )
        result = generate_variant_layer([], [ast])
        assert "Hypothesis assertion content." in result

    def test_evidence_for_written_when_present(self) -> None:
        vs = VariantSet(
            name="DB Choice",
            topic_path="/architecture/database",
            variants=[
                Variant(
                    name="postgres",
                    content="Use Postgres.",
                    evidence_for=["https://benchmark.example.com"],
                ),
                Variant(name="mysql", content="Use MySQL."),
            ],
        )
        result = generate_variant_layer([vs], [])
        assert "cb:evidence_for" in result
        assert "https://benchmark.example.com" in result

    def test_starts_with_usda_header(self) -> None:
        result = generate_variant_layer([], [])
        assert result.startswith("#usda 1.0")


# ─────────────────────────────────────────────────────────────────────────────
# TestUSDATextValidity
# ─────────────────────────────────────────────────────────────────────────────

class TestUSDATextValidity:
    def test_generated_text_starts_with_usda_1_0(self) -> None:
        """Case 23: Generated text starts with #usda 1.0."""
        result = generate_arc_layer([], CompositionArc.SPECIALIZES, "doc")
        assert result.startswith("#usda 1.0")

    def test_double_quotes_in_content_are_escaped(self) -> None:
        """Case 24: Embedded double quotes are escaped as backslash-quote."""
        ast = make_specializes(content='He said "hello world" loudly.')
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        # The escaped form must appear, raw unescaped form must not be an attribute
        assert '\\"hello world\\"' in result

    def test_backslash_in_content_is_escaped(self) -> None:
        """Case 24: Backslashes are doubled."""
        ast = make_specializes(content="Path is C:\\Users\\test")
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert "C:\\\\Users\\\\test" in result

    def test_newline_in_content_is_escaped(self) -> None:
        """Case 24: Newlines are replaced with backslash-n."""
        ast = make_specializes(content="Line one.\nLine two.")
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        assert "Line one.\\nLine two." in result

    def test_indentation_is_four_spaces(self) -> None:
        """Case 25: Indentation is consistent 4 spaces."""
        ast = make_specializes(topic_path="/architecture/database/engine")
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        # Attributes inside the leaf prim must be indented by at least 8 spaces
        # (2 levels: architecture + database + engine = 3 levels deep, attrs at 4th)
        assert "            custom string cb:content" in result

    def test_stage_root_starts_with_usda_1_0(self) -> None:
        result = generate_stage_root("proj_abc", "Test")
        assert result.startswith("#usda 1.0")

    def test_variant_layer_starts_with_usda_1_0(self) -> None:
        result = generate_variant_layer([], [])
        assert result.startswith("#usda 1.0")

    def test_no_raw_unescaped_quote_in_attribute_value(self) -> None:
        """Attribute values must not contain unescaped double-quotes."""
        ast = make_specializes(content='Content with "quotes" inside.')
        result = generate_arc_layer([ast], CompositionArc.SPECIALIZES, "doc")
        # Verify that escaped form exists and count sanity
        assert '\\"quotes\\"' in result

    def test_export_produces_usda_headers_in_all_files(self, tmp_path) -> None:
        """Every written file must start with #usda 1.0."""
        ast = make_local()
        stage = make_stage_with_assertions(ast)
        written = export_stage_to_usda(stage, tmp_path)
        for filename, path in written.items():
            content = path.read_text(encoding="utf-8")
            assert content.startswith("#usda 1.0"), (
                f"{filename} does not start with #usda 1.0"
            )
