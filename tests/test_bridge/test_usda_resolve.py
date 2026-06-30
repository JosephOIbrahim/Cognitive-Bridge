"""Tests for USDA resolver — pure-text resolution and consistency checking.

Tests are grouped into:
- TestResolveViaText: top-level resolve_via_text() behaviour
- TestParsePrimsFromUsda: internal _parse_prims_from_usda() parsing
- TestCheckConsistency: check_consistency() comparison logic
- TestEndToEndConsistency: full round-trip with a real CompositionStage

Tests 16-20 (end-to-end) require bridge.usda_export, which is built by a
separate agent. If that module is absent the test is skipped automatically.
"""

import pytest
import textwrap
from pathlib import Path

from cognitive_bridge.bridge.usda_resolve import (
    _parse_prims_from_usda,
    check_consistency,
    resolve_via_text,
    resolve_via_usd,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_stage(tmp_path: Path, sublayers: list[str]) -> None:
    """Write a minimal stage.usda that lists the given sublayer filenames."""
    refs = "\n".join(f'        @./{s}@,' for s in sublayers)
    content = textwrap.dedent(f"""\
        #usda 1.0
        (
            subLayers = [
        {refs}
            ]
        )
    """)
    (tmp_path / "stage.usda").write_text(content, encoding="utf-8")


def _write_layer(tmp_path: Path, filename: str, prims: dict[str, dict]) -> None:
    """Write a minimal USDA layer with the given prim paths and cb: attributes.

    prim paths like /db/engine are written as nested def Scope blocks.
    """
    lines = ['#usda 1.0', '']
    for prim_path, attrs in prims.items():
        parts = prim_path.lstrip("/").split("/")
        # Open nested scopes
        for i, part in enumerate(parts):
            indent = "    " * i
            lines.append(f'{indent}def Scope "{part}"')
            lines.append(f'{indent}{{')
        # Write attrs at innermost level
        inner_indent = "    " * len(parts)
        for key, val in attrs.items():
            if isinstance(val, str):
                lines.append(f'{inner_indent}custom string cb:{key} = "{val}"')
            elif isinstance(val, float):
                lines.append(f'{inner_indent}custom double cb:{key} = {val}')
            elif isinstance(val, list):
                items = ", ".join(f'"{v}"' for v in val)
                lines.append(f'{inner_indent}custom string[] cb:{key} = [{items}]')
        # Close nested scopes (innermost first)
        for i in range(len(parts) - 1, -1, -1):
            indent = "    " * i
            lines.append(f'{indent}}}')
        lines.append('')
    (tmp_path / filename).write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# TestResolveViaText
# ---------------------------------------------------------------------------

class TestResolveViaText:
    """Tests for resolve_via_text()."""

    def test_single_sublayer_single_prim(self, tmp_path):
        """A simple sublayer with one prim has its content extracted."""
        _write_layer(tmp_path, "local.usda", {
            "/db/engine": {"content": "PostgreSQL", "assertion_id": "ast_aaa"}
        })
        _write_stage(tmp_path, ["local.usda"])

        result = resolve_via_text(tmp_path)

        assert "/db/engine" in result
        assert result["/db/engine"]["content"] == "PostgreSQL"

    def test_first_sublayer_wins_same_prim(self, tmp_path):
        """When two sublayers define the same prim path, the first wins (LIVRPS)."""
        _write_layer(tmp_path, "local.usda", {
            "/db/engine": {"content": "PostgreSQL"}
        })
        _write_layer(tmp_path, "references.usda", {
            "/db/engine": {"content": "MongoDB"}
        })
        _write_stage(tmp_path, ["local.usda", "references.usda"])

        result = resolve_via_text(tmp_path)

        assert result["/db/engine"]["content"] == "PostgreSQL"

    def test_multiple_prim_paths_resolved_independently(self, tmp_path):
        """Different prim paths are resolved independently."""
        _write_layer(tmp_path, "local.usda", {
            "/db/engine": {"content": "PostgreSQL"},
            "/api/framework": {"content": "FastAPI"},
        })
        _write_stage(tmp_path, ["local.usda"])

        result = resolve_via_text(tmp_path)

        assert result["/db/engine"]["content"] == "PostgreSQL"
        assert result["/api/framework"]["content"] == "FastAPI"

    def test_empty_sublayer_produces_no_prims(self, tmp_path):
        """An empty sublayer contributes nothing to resolution."""
        (tmp_path / "empty.usda").write_text("#usda 1.0\n", encoding="utf-8")
        _write_stage(tmp_path, ["empty.usda"])

        result = resolve_via_text(tmp_path)

        assert result == {}

    def test_nested_prim_hierarchy_path_reconstruction(self, tmp_path):
        """Deeply nested prims have correct prim path reconstruction."""
        _write_layer(tmp_path, "local.usda", {
            "/architecture/database/engine": {"content": "Postgres"}
        })
        _write_stage(tmp_path, ["local.usda"])

        result = resolve_via_text(tmp_path)

        assert "/architecture/database/engine" in result
        assert result["/architecture/database/engine"]["content"] == "Postgres"

    def test_missing_stage_file_raises(self, tmp_path):
        """FileNotFoundError is raised when stage.usda is absent."""
        with pytest.raises(FileNotFoundError, match="stage.usda"):
            resolve_via_text(tmp_path)

    def test_stage_with_no_sublayers_returns_empty(self, tmp_path):
        """A stage.usda that declares no sublayers returns an empty dict."""
        (tmp_path / "stage.usda").write_text("#usda 1.0\n(\n)\n", encoding="utf-8")
        result = resolve_via_text(tmp_path)
        assert result == {}

    def test_missing_sublayer_file_is_skipped(self, tmp_path):
        """A sublayer listed in stage.usda that doesn't exist is skipped silently."""
        _write_layer(tmp_path, "local.usda", {
            "/db/engine": {"content": "PostgreSQL"}
        })
        # stage.usda lists ghost.usda which doesn't exist
        _write_stage(tmp_path, ["ghost.usda", "local.usda"])

        result = resolve_via_text(tmp_path)
        assert result["/db/engine"]["content"] == "PostgreSQL"

    def test_second_sublayer_fills_missing_paths(self, tmp_path):
        """Paths only in the second sublayer are still resolved."""
        _write_layer(tmp_path, "local.usda", {
            "/db/engine": {"content": "PostgreSQL"}
        })
        _write_layer(tmp_path, "inherits.usda", {
            "/api/framework": {"content": "FastAPI"}
        })
        _write_stage(tmp_path, ["local.usda", "inherits.usda"])

        result = resolve_via_text(tmp_path)

        assert result["/db/engine"]["content"] == "PostgreSQL"
        assert result["/api/framework"]["content"] == "FastAPI"


# ---------------------------------------------------------------------------
# TestParsePrimsFromUsda
# ---------------------------------------------------------------------------

class TestParsePrimsFromUsda:
    """Tests for _parse_prims_from_usda()."""

    def test_extracts_cb_content_string(self):
        """cb:content string attribute is extracted correctly."""
        text = textwrap.dedent("""\
            #usda 1.0
            def Scope "db"
            {
                def Scope "engine"
                {
                    custom string cb:content = "PostgreSQL"
                }
            }
        """)
        prims = _parse_prims_from_usda(text)
        assert prims["/db/engine"]["content"] == "PostgreSQL"

    def test_extracts_cb_confidence_float(self):
        """cb:confidence float attribute is extracted as a Python float."""
        text = textwrap.dedent("""\
            #usda 1.0
            def Scope "db"
            {
                custom double cb:confidence = 0.95
            }
        """)
        prims = _parse_prims_from_usda(text)
        assert prims["/db"]["confidence"] == pytest.approx(0.95)

    def test_extracts_cb_depends_on_paths_array(self):
        """cb:depends_on_paths string array is extracted as a list."""
        text = textwrap.dedent("""\
            #usda 1.0
            def Scope "api"
            {
                custom string[] cb:depends_on_paths = ["/db/engine", "/cache/redis"]
            }
        """)
        prims = _parse_prims_from_usda(text)
        assert prims["/api"]["depends_on_paths"] == ["/db/engine", "/cache/redis"]

    def test_extracts_cb_assertion_id(self):
        """cb:assertion_id is extracted as a plain string."""
        text = textwrap.dedent("""\
            #usda 1.0
            def Scope "db"
            {
                custom string cb:assertion_id = "ast_abc123"
            }
        """)
        prims = _parse_prims_from_usda(text)
        assert prims["/db"]["assertion_id"] == "ast_abc123"

    def test_ignores_non_cb_attributes(self):
        """Attributes without the cb: namespace are not included in output."""
        text = textwrap.dedent("""\
            #usda 1.0
            def Scope "db"
            {
                custom string someOtherAttr = "should_be_ignored"
                custom string cb:content = "PostgreSQL"
            }
        """)
        prims = _parse_prims_from_usda(text)
        assert "someOtherAttr" not in prims["/db"]
        assert prims["/db"]["content"] == "PostgreSQL"

    def test_empty_text_returns_empty(self):
        """An empty (or header-only) USDA text produces no prims."""
        prims = _parse_prims_from_usda("#usda 1.0\n")
        assert prims == {}

    def test_multiple_prims_all_extracted(self):
        """Multiple top-level prims in one layer are all extracted."""
        text = textwrap.dedent("""\
            #usda 1.0
            def Scope "db"
            {
                custom string cb:content = "Postgres"
            }
            def Scope "cache"
            {
                custom string cb:content = "Redis"
            }
        """)
        prims = _parse_prims_from_usda(text)
        assert prims["/db"]["content"] == "Postgres"
        assert prims["/cache"]["content"] == "Redis"

    def test_prim_without_cb_attrs_not_in_output(self):
        """A prim that has no cb: attributes does not appear in the output."""
        text = textwrap.dedent("""\
            #usda 1.0
            def Scope "empty_prim"
            {
            }
        """)
        prims = _parse_prims_from_usda(text)
        assert "/empty_prim" not in prims


# ---------------------------------------------------------------------------
# TestCheckConsistency
# ---------------------------------------------------------------------------

class TestCheckConsistency:
    """Tests for check_consistency()."""

    class _FakeAssertion:
        """Minimal stand-in for Assertion with a content field."""
        def __init__(self, content: str):
            self.content = content

    def _sql(self, path_content: dict[str, str]) -> dict:
        """Build a fake sql_resolved dict from {path: content}."""
        return {
            path: {"winning": self._FakeAssertion(content)}
            for path, content in path_content.items()
        }

    def _usda(self, path_content: dict[str, str]) -> dict:
        """Build a fake usda_resolved dict from {path: content}."""
        return {path: {"content": content} for path, content in path_content.items()}

    def test_identical_results_no_discrepancies(self):
        """When SQL and USDA winners match, discrepancy list is empty."""
        sql = self._sql({"/db/engine": "PostgreSQL"})
        usda = self._usda({"/db/engine": "PostgreSQL"})
        assert check_consistency(sql, usda) == []

    def test_missing_path_in_usda_reported(self):
        """A path in SQL but absent from USDA is reported as a discrepancy."""
        sql = self._sql({"/db/engine": "PostgreSQL"})
        usda = self._usda({})
        discrepancies = check_consistency(sql, usda)
        assert len(discrepancies) == 1
        assert "/db/engine" in discrepancies[0]
        assert "SQL" in discrepancies[0]

    def test_different_content_reported(self):
        """Matching paths with different content are reported."""
        sql = self._sql({"/db/engine": "PostgreSQL"})
        usda = self._usda({"/db/engine": "MongoDB"})
        discrepancies = check_consistency(sql, usda)
        assert len(discrepancies) == 1
        assert "PostgreSQL" in discrepancies[0]
        assert "MongoDB" in discrepancies[0]

    def test_extra_path_in_usda_reported(self):
        """A path in USDA but absent from SQL is reported as a discrepancy."""
        sql = self._sql({})
        usda = self._usda({"/db/engine": "PostgreSQL"})
        discrepancies = check_consistency(sql, usda)
        assert len(discrepancies) == 1
        assert "/db/engine" in discrepancies[0]
        assert "USDA" in discrepancies[0]

    def test_both_empty_no_discrepancies(self):
        """Two empty dicts are trivially consistent."""
        assert check_consistency({}, {}) == []

    def test_multiple_paths_all_consistent(self):
        """Multiple matching paths produce no discrepancies."""
        sql = self._sql({
            "/db/engine": "PostgreSQL",
            "/api/framework": "FastAPI",
        })
        usda = self._usda({
            "/db/engine": "PostgreSQL",
            "/api/framework": "FastAPI",
        })
        assert check_consistency(sql, usda) == []

    def test_partial_overlap_multiple_discrepancies(self):
        """Multiple mismatch types all reported in one call."""
        sql = self._sql({
            "/db/engine": "PostgreSQL",
            "/cache": "Redis",
        })
        usda = self._usda({
            "/db/engine": "MongoDB",      # wrong content
            "/search": "Elasticsearch",   # extra in USDA
        })
        discrepancies = check_consistency(sql, usda)
        # /db/engine: content mismatch, /cache: missing from USDA, /search: extra
        assert len(discrepancies) == 3

    def test_entry_without_winning_is_skipped(self):
        """SQL entries with no 'winning' key are silently skipped."""
        sql = {"/db/engine": {"shadow_stack": []}}  # no 'winning' key
        usda = self._usda({})
        assert check_consistency(sql, usda) == []

    def test_usda_entry_without_content_is_skipped(self):
        """USDA entries with no 'content' key are silently skipped."""
        sql = self._sql({})
        usda = {"/db/engine": {"assertion_id": "ast_abc"}}  # no 'content' key
        assert check_consistency(sql, usda) == []


# ---------------------------------------------------------------------------
# TestResolveViaUsd
# ---------------------------------------------------------------------------

class TestResolveViaUsd:
    """Tests for resolve_via_usd()."""

    def test_returns_none_without_pxr(self):
        """resolve_via_usd returns None when pxr is not installed."""
        # Import the module's availability flag to check the actual environment
        import cognitive_bridge.bridge.usda_resolve as mod
        if not mod._USD_AVAILABLE:
            result = resolve_via_usd("/nonexistent/path")
            assert result is None
        else:
            pytest.skip("pxr is installed — skipping None-return test")

    def test_raises_when_stage_missing_and_pxr_available(self, tmp_path):
        """FileNotFoundError is raised when stage.usda is absent (pxr path)."""
        import cognitive_bridge.bridge.usda_resolve as mod
        if not mod._USD_AVAILABLE:
            pytest.skip("pxr not installed")
        with pytest.raises(FileNotFoundError, match="stage.usda"):
            resolve_via_usd(tmp_path)


# ---------------------------------------------------------------------------
# TestEndToEndConsistency
# ---------------------------------------------------------------------------

# Attempt to import usda_export — skip end-to-end tests if not yet available.
_usda_export_available = False
try:
    from cognitive_bridge.bridge.usda_export import (  # type: ignore[import]
        export_stage_to_usda,
    )
    _usda_export_available = True
except ImportError:
    pass

_e2e_skip = pytest.mark.skipif(
    not _usda_export_available,
    reason="bridge.usda_export not available yet (built by another agent)",
)


@_e2e_skip
class TestEndToEndConsistency:
    """End-to-end round-trip: CompositionStage -> USDA export -> text resolve -> check.

    Requires bridge.usda_export (built by a separate agent).

    Scenario:
    - LOCAL assertion at /db/engine ("PostgreSQL")     — wins
    - REFERENCES assertion at /db/engine ("MongoDB")   — loses (LOCAL beats REFERENCES)
    - INHERITS assertion at /api/framework ("FastAPI")  — wins
    - SPECIALIZES assertion at /api/framework ("Flask") — loses (INHERITS beats SPECIALIZES)
    """

    @pytest.fixture()
    def stage_with_assertions(self):
        """Build a CompositionStage with the four assertions described above."""
        from cognitive_bridge.models.stage import CompositionStage
        from cognitive_bridge.models.assertion import Assertion
        from cognitive_bridge.models.arcs import (
            AssertionAuthor,
            CompositionArc,
        )

        stage = CompositionStage(
            project_id="e2e-test",
            project_name="E2E Consistency Test",
        )

        local_pg = Assertion(
            topic_path="/db/engine",
            content="PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If query latency exceeds 1s at p99 under load",
        )
        refs_mongo = Assertion(
            topic_path="/db/engine",
            content="MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        inherits_fastapi = Assertion(
            topic_path="/api/framework",
            content="FastAPI",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        spec_flask = Assertion(
            topic_path="/api/framework",
            content="Flask",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )

        for ast in (local_pg, refs_mongo, inherits_fastapi, spec_flask):
            stage.assertions[ast.id] = ast

        return stage

    def test_sql_winners_are_correct(self, stage_with_assertions):
        """Verify SQL resolution picks the right winners before involving USDA."""
        stage = stage_with_assertions
        resolved = stage.resolve()

        assert resolved["/db/engine"]["winning"].content == "PostgreSQL"
        assert resolved["/api/framework"]["winning"].content == "FastAPI"

    def test_export_and_text_resolve_matches_sql(self, stage_with_assertions, tmp_path):
        """Full round-trip: export -> text resolve -> check_consistency = zero discrepancies.

        This is the key proof that the composition model is mechanically correct.
        """
        stage = stage_with_assertions
        export_stage_to_usda(stage, tmp_path)

        sql_resolved = stage.resolve()
        usda_resolved = resolve_via_text(tmp_path)

        # Verify USDA resolved the correct winners
        assert "/db/engine" in usda_resolved
        assert "/api/framework" in usda_resolved
        assert usda_resolved["/db/engine"]["content"] == "PostgreSQL"
        assert usda_resolved["/api/framework"]["content"] == "FastAPI"

        # The key consistency check — zero discrepancies
        discrepancies = check_consistency(sql_resolved, usda_resolved)
        assert discrepancies == [], (
            f"Consistency check failed — SQL and USDA resolution diverged:\n"
            + "\n".join(discrepancies)
        )

    def test_stage_usda_file_exists_after_export(self, stage_with_assertions, tmp_path):
        """export_stage_to_usda creates stage.usda in the target directory."""
        export_stage_to_usda(stage_with_assertions, tmp_path)
        assert (tmp_path / "stage.usda").exists()

    def test_sublayer_order_strongest_first(self, stage_with_assertions, tmp_path):
        """Stage sublayers are declared strongest-arc-first so text resolver honours LIVRPS."""
        import re as _re

        export_stage_to_usda(stage_with_assertions, tmp_path)
        stage_text = (tmp_path / "stage.usda").read_text(encoding="utf-8")

        # LOCAL layer reference must appear before REFERENCES layer reference
        sublayer_pattern = _re.compile(r'@\./([^@]+)@')
        sublayers = sublayer_pattern.findall(stage_text)

        # Every sublayer should appear in order of increasing arc IntEnum value
        # i.e., local (10) before inherits (20) before ... before specializes (60)
        assert len(sublayers) >= 1, "No sublayers found in stage.usda"

        # Check that local appears before references in the sublayer list
        names_lower = [s.lower() for s in sublayers]
        if "local.usda" in names_lower and "references.usda" in names_lower:
            assert names_lower.index("local.usda") < names_lower.index(
                "references.usda"
            ), "local.usda must come before references.usda in sublayer order"


@_e2e_skip
class TestSamePathSameArcConsistency:
    """Regression: SQL and USDA resolution must agree in two structural cases the
    earlier scenarios never exercised:

    1. Two active assertions at the SAME (topic_path, arc). The export nests the
       loser as an ``opinion_N`` child; the text resolver must surface the winner
       prim and must NOT surface the opinion child as a phantom path.
    2. An asserted path that is also a prefix of another asserted path
       (``/db`` and ``/db/engine``). The parent prim carries ``cb:content`` AND a
       child prim; the resolver must still record the parent.
    """

    def _stage(self):
        from cognitive_bridge.models.stage import CompositionStage

        return CompositionStage(
            project_id="same-arc", project_name="Same-arc regression"
        )

    def test_higher_confidence_inserted_second_wins_both_ways(self, tmp_path):
        from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
        from cognitive_bridge.models.assertion import Assertion

        stage = self._stage()
        # The WINNER (higher confidence) is inserted SECOND, so insertion order
        # deliberately disagrees with resolution order.
        loser = Assertion(
            topic_path="/db/engine",
            content="SQLite",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            confidence=0.4,
            falsifiable_if="If it cannot sustain concurrent writers",
        )
        winner = Assertion(
            topic_path="/db/engine",
            content="PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            confidence=0.9,
            falsifiable_if="If p99 query latency exceeds 1s under load",
        )
        stage.assertions[loser.id] = loser  # inserted first
        stage.assertions[winner.id] = winner  # inserted second, the real winner

        sql_resolved = stage.resolve()
        assert sql_resolved["/db/engine"]["winning"].content == "PostgreSQL"

        export_stage_to_usda(stage, tmp_path)
        usda_resolved = resolve_via_text(tmp_path)

        # USDA surfaces the same winner — not the insertion-order primary — and
        # does not leak the loser as a phantom opinion path.
        assert usda_resolved["/db/engine"]["content"] == "PostgreSQL"
        assert "/db/engine/opinion_1" not in usda_resolved

        discrepancies = check_consistency(sql_resolved, usda_resolved)
        assert discrepancies == [], "SQL/USDA diverged:\n" + "\n".join(discrepancies)

    def test_asserted_parent_with_asserted_child_both_resolve(self, tmp_path):
        from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
        from cognitive_bridge.models.assertion import Assertion

        stage = self._stage()
        parent = Assertion(
            topic_path="/db",
            content="relational",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If a document store replaces it",
        )
        child = Assertion(
            topic_path="/db/engine",
            content="PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If p99 query latency exceeds 1s under load",
        )
        stage.assertions[parent.id] = parent
        stage.assertions[child.id] = child

        sql_resolved = stage.resolve()
        export_stage_to_usda(stage, tmp_path)
        usda_resolved = resolve_via_text(tmp_path)

        # The parent prim must be surfaced even though it has a child prim.
        assert usda_resolved["/db"]["content"] == "relational"
        assert usda_resolved["/db/engine"]["content"] == "PostgreSQL"

        discrepancies = check_consistency(sql_resolved, usda_resolved)
        assert discrepancies == [], "SQL/USDA diverged:\n" + "\n".join(discrepancies)


@_e2e_skip
class TestUsdaConsistencyEdgeCases:
    """Edge cases for the SQL/USDA mechanical-equivalence guarantee surfaced by
    an adversarial sweep: a real ``opinion_N``-named topic path, special
    characters in content, and a USD VariantSet that must not pollute resolution.
    """

    def _stage(self):
        from cognitive_bridge.models.stage import CompositionStage

        return CompositionStage(project_id="edge", project_name="Edge cases")

    def test_real_opinion_named_path_is_not_dropped(self, tmp_path):
        # A legitimate topic path whose final segment is literally "opinion_1",
        # with the same-arc parent asserted. The shadow-opinion skip must key on
        # the cb:shadow marker, not the name, so this real node is preserved.
        from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
        from cognitive_bridge.models.assertion import Assertion

        stage = self._stage()
        parent = Assertion(
            topic_path="/config",
            content="config root",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If config is removed",
        )
        opinion_named = Assertion(
            topic_path="/config/opinion_1",
            content="a real node literally named opinion_1",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If this node is deleted",
        )
        stage.assertions[parent.id] = parent
        stage.assertions[opinion_named.id] = opinion_named

        sql_resolved = stage.resolve()
        export_stage_to_usda(stage, tmp_path)
        usda_resolved = resolve_via_text(tmp_path)

        assert (
            usda_resolved["/config/opinion_1"]["content"]
            == "a real node literally named opinion_1"
        )
        discrepancies = check_consistency(sql_resolved, usda_resolved)
        assert discrepancies == [], "SQL/USDA diverged:\n" + "\n".join(discrepancies)

    def test_special_characters_round_trip(self, tmp_path):
        from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
        from cognitive_bridge.models.assertion import Assertion

        stage = self._stage()
        tricky = 'He said "hi"; path C:\\Users\\db;\nsecond line'
        ast = Assertion(
            topic_path="/x",
            content=tricky,
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If the round-trip mangles it",
        )
        stage.assertions[ast.id] = ast

        sql_resolved = stage.resolve()
        export_stage_to_usda(stage, tmp_path)
        usda_resolved = resolve_via_text(tmp_path)

        # Quotes, backslashes, and newlines must survive the export/parse round trip.
        assert usda_resolved["/x"]["content"] == tricky
        discrepancies = check_consistency(sql_resolved, usda_resolved)
        assert discrepancies == [], "SQL/USDA diverged:\n" + "\n".join(discrepancies)

    def test_variant_set_does_not_pollute_resolution(self, tmp_path):
        from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
        from cognitive_bridge.models.assertion import Assertion
        from cognitive_bridge.models.variant_set import Variant, VariantSet

        stage = self._stage()
        engine = Assertion(
            topic_path="/architecture/database/engine",
            content="PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            confidence=0.9,
            falsifiable_if="If p99 latency exceeds 1s under load",
        )
        baseline = Assertion(
            topic_path="/architecture/database",
            content="any relational DB",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        stage.assertions[engine.id] = engine
        stage.assertions[baseline.id] = baseline

        # An unresolved VariantSet at a path overlapping the assertions above.
        vs = VariantSet(
            name="Engine Choice",
            topic_path="/architecture/database",
            variants=[
                Variant(name="MongoDB", content="MongoDB is the best engine"),
                Variant(name="Postgres", content="Postgres is the best engine"),
            ],
        )
        stage.variant_sets[vs.id] = vs

        sql_resolved = stage.resolve()
        export_stage_to_usda(stage, tmp_path)
        usda_resolved = resolve_via_text(tmp_path)

        # The variant block must not invent /architecture, nor override the real
        # SPECIALIZES winner at /architecture/database with a variant opinion.
        discrepancies = check_consistency(sql_resolved, usda_resolved)
        assert discrepancies == [], "SQL/USDA diverged:\n" + "\n".join(discrepancies)
        assert usda_resolved["/architecture/database"]["content"] == "any relational DB"
        assert (
            usda_resolved["/architecture/database/engine"]["content"] == "PostgreSQL"
        )

    def test_empty_content_assertion_is_consistent(self, tmp_path):
        # An empty-string content is model-valid; check_consistency must gate on
        # presence, not truthiness, or it falsely reports the path as missing.
        from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
        from cognitive_bridge.models.assertion import Assertion

        stage = self._stage()
        empty = Assertion(
            topic_path="/empty/path",
            content="",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        keep = Assertion(
            topic_path="/kept",
            content="non-empty",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        stage.assertions[empty.id] = empty
        stage.assertions[keep.id] = keep

        sql_resolved = stage.resolve()
        export_stage_to_usda(stage, tmp_path)
        usda_resolved = resolve_via_text(tmp_path)

        discrepancies = check_consistency(sql_resolved, usda_resolved)
        assert discrepancies == [], "SQL/USDA diverged:\n" + "\n".join(discrepancies)
        assert usda_resolved["/empty/path"]["content"] == ""

    def test_variant_content_with_brace_does_not_leak_phantom_path(self, tmp_path):
        # A literal "}" inside variant content must not close the variantSet
        # brace-skip early — the exporter does not escape curly braces.
        from cognitive_bridge.models.arcs import AssertionAuthor, CompositionArc
        from cognitive_bridge.models.assertion import Assertion
        from cognitive_bridge.models.variant_set import Variant, VariantSet

        stage = self._stage()
        safe = Assertion(
            topic_path="/safe",
            content="unrelated",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="If safe breaks",
        )
        stage.assertions[safe.id] = safe

        vs = VariantSet(
            name="Config Choice",
            topic_path="/target",
            variants=[
                Variant(name="A", content="use config }"),
                Variant(name="B", content="normal option"),
            ],
        )
        stage.variant_sets[vs.id] = vs

        sql_resolved = stage.resolve()
        export_stage_to_usda(stage, tmp_path)
        usda_resolved = resolve_via_text(tmp_path)

        # /target is a VariantSet, not an assertion: it must not surface as a
        # resolved winner on the USDA side.
        assert "/target" not in usda_resolved
        discrepancies = check_consistency(sql_resolved, usda_resolved)
        assert discrepancies == [], "SQL/USDA diverged:\n" + "\n".join(discrepancies)
