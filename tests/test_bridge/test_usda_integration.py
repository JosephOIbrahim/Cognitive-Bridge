"""Integration tests for USDA auto-export lifecycle wiring.

Covers:
1. assert action triggers auto-export — usda/ dir is created with all 7 files
2. retract action triggers re-export — usda files are updated
3. conflict resolve action triggers export
4. variant create action triggers export
5. composition resource shows layer structure after export
6. composition resource shows consistency PASS after export
7. cb_manage_project(action='usda_export') generates files on demand
8. composition resource returns helpful message before any export exists
"""

import os
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

from cognitive_bridge.bridge.usda_export import SUBLAYER_ORDER, export_stage_to_usda
from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    Conflict,
    ConflictDetectionLayer,
    Variant,
    VariantSet,
)
from cognitive_bridge.resources.stage_resources import get_composition_view
from cognitive_bridge.server import cb_manage_project, save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.assertion_tool import cb_manage_assertion
from cognitive_bridge.tools.conflict_tool import cb_manage_conflict
from cognitive_bridge.tools.variant_tool import cb_manage_variant


# ─────────────────────────────────────────────────────────────────────────────
# Shared test infrastructure
# ─────────────────────────────────────────────────────────────────────────────


class _MockCtx:
    """Minimal FastMCP context mock for direct tool/resource invocation."""

    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {
            "store": store,
            "active_stages": active_stages,
        }


def _make_ctx(
    store: Optional[SQLiteStore] = None,
    active_stages: Optional[dict] = None,
) -> _MockCtx:
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


def _make_ctx_with_stage(
    project_id: str = "proj_usda_test",
    tmp_path: Optional[Path] = None,
) -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    """Wire context, stage, and store together. Optionally pin CB_DB_DIR."""
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="USDA Test Project")
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    ctx = _make_ctx(store=store, active_stages=active_stages)
    return ctx, stage, store


def _usda_dir(tmp_path: Path, project_id: str) -> Path:
    """Return the expected USDA output directory for a project."""
    return tmp_path / project_id / "usda"


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: assert action triggers auto-export
# ─────────────────────────────────────────────────────────────────────────────


class TestAssertTriggersExport:
    @pytest.mark.asyncio
    async def test_assert_creates_usda_directory(self, tmp_path: Path) -> None:
        """After an assert call, the usda/ directory must exist."""
        project_id = "proj_assert_export"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content="PostgreSQL is the chosen engine.",
                arc=CompositionArc.SPECIALIZES.value,
                ctx=ctx,
                project_id=project_id,
            )

        usda_dir = _usda_dir(tmp_path, project_id)
        assert usda_dir.exists(), "usda/ directory was not created after assert"

    @pytest.mark.asyncio
    async def test_assert_writes_all_seven_usda_files(self, tmp_path: Path) -> None:
        """All 7 .usda files (6 arc layers + stage.usda) must be written."""
        project_id = "proj_assert_files"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content="PostgreSQL is production-grade.",
                arc=CompositionArc.SPECIALIZES.value,
                ctx=ctx,
                project_id=project_id,
            )

        usda_dir = _usda_dir(tmp_path, project_id)
        expected_files = set(SUBLAYER_ORDER) | {"stage.usda"}
        actual_files = {f.name for f in usda_dir.iterdir() if f.suffix == ".usda"}
        assert expected_files == actual_files, (
            f"Expected {expected_files}, got {actual_files}"
        )

    @pytest.mark.asyncio
    async def test_assert_content_appears_in_specializes_layer(
        self, tmp_path: Path
    ) -> None:
        """SPECIALIZES content must appear in safety_specializes.usda."""
        project_id = "proj_assert_content"
        ctx, stage, store = _make_ctx_with_stage(project_id)
        unique_content = "Unique assertion content for USDA test XYZ."

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content=unique_content,
                arc=CompositionArc.SPECIALIZES.value,
                ctx=ctx,
                project_id=project_id,
            )

        usda_dir = _usda_dir(tmp_path, project_id)
        specializes_text = (usda_dir / "safety_specializes.usda").read_text(
            encoding="utf-8"
        )
        assert unique_content in specializes_text


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: retract triggers re-export (usda files updated)
# ─────────────────────────────────────────────────────────────────────────────


class TestRetractTriggersReexport:
    @pytest.mark.asyncio
    async def test_retract_removes_content_from_usda(self, tmp_path: Path) -> None:
        """After retract, the content must no longer appear in any arc layer."""
        project_id = "proj_retract_export"
        ctx, stage, store = _make_ctx_with_stage(project_id)
        unique_content = "Retractable assertion unique content ABC."

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            # Assert first
            await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content=unique_content,
                arc=CompositionArc.SPECIALIZES.value,
                ctx=ctx,
                project_id=project_id,
            )

            # Capture the assertion_id from the stage
            assertion_id = next(iter(stage.assertions.keys()))

            # Retract it
            await cb_manage_assertion(
                action="retract",
                topic_path="/architecture/database",
                assertion_id=assertion_id,
                ctx=ctx,
                project_id=project_id,
            )

        usda_dir = _usda_dir(tmp_path, project_id)
        for arc_file in SUBLAYER_ORDER:
            file_text = (usda_dir / arc_file).read_text(encoding="utf-8")
            assert unique_content not in file_text, (
                f"Retracted content still present in {arc_file}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: conflict resolve triggers export
# ─────────────────────────────────────────────────────────────────────────────


class TestConflictResolveTriggersExport:
    @pytest.mark.asyncio
    async def test_conflict_resolve_triggers_usda_export(
        self, tmp_path: Path
    ) -> None:
        """Resolving a conflict must regenerate USDA files."""
        project_id = "proj_conflict_export"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        # Build a conflict manually in the stage and save it
        ast_a = Assertion(
            topic_path="/architecture/database",
            content="Use PostgreSQL.",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        ast_b = Assertion(
            topic_path="/architecture/database",
            content="Use MongoDB.",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast_a.id] = ast_a
        stage.assertions[ast_b.id] = ast_b

        conflict = Conflict(
            assertion_a_id=ast_a.id,
            assertion_b_id=ast_b.id,
            topic_path="/architecture/database",
            detection_layer=ConflictDetectionLayer.STRUCTURAL,
        )
        stage.conflicts[conflict.id] = conflict
        save_stage_to_db(store, stage)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await cb_manage_conflict(
                action="resolve",
                conflict_id=conflict.id,
                resolution="accept",
                ctx=ctx,
                project_id=project_id,
            )

        assert "resolved" in result.lower(), f"Unexpected response: {result}"

        usda_dir = _usda_dir(tmp_path, project_id)
        assert usda_dir.exists(), "usda/ directory not created after conflict resolve"
        assert (usda_dir / "stage.usda").exists(), "stage.usda missing"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: variant create triggers export
# ─────────────────────────────────────────────────────────────────────────────


class TestVariantCreateTriggersExport:
    @pytest.mark.asyncio
    async def test_variant_create_triggers_usda_export(self, tmp_path: Path) -> None:
        """Creating a variant set must regenerate USDA files."""
        project_id = "proj_variant_export"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await cb_manage_variant(
                action="create",
                topic_path="/architecture/database",
                name="Database Choice",
                variant_names="PostgreSQL,MongoDB",
                variant_contents="Use PostgreSQL for ACID.,Use MongoDB for docs.",
                ctx=ctx,
                project_id=project_id,
            )

        assert "Variant set created" in result, f"Unexpected response: {result}"

        usda_dir = _usda_dir(tmp_path, project_id)
        assert usda_dir.exists(), "usda/ directory not created after variant create"
        assert (usda_dir / "hypothesis_variants.usda").exists(), (
            "hypothesis_variants.usda missing"
        )

    @pytest.mark.asyncio
    async def test_variant_add_evidence_triggers_export(
        self, tmp_path: Path
    ) -> None:
        """Adding evidence to a variant set must regenerate USDA files."""
        project_id = "proj_variant_evidence_export"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            # Create the variant set first
            await cb_manage_variant(
                action="create",
                topic_path="/architecture/database",
                name="DB Choice",
                variant_names="Postgres,Mongo",
                variant_contents="Postgres approach.,Mongo approach.",
                ctx=ctx,
                project_id=project_id,
            )

            vs_id = next(iter(stage.variant_sets.keys()))

            # Now add evidence — this must also regenerate USDA
            result = await cb_manage_variant(
                action="add_evidence",
                variant_set_id=vs_id,
                variant_name="Postgres",
                evidence_for="Benchmark shows 2x write throughput.",
                ctx=ctx,
                project_id=project_id,
            )

        assert "Evidence recorded" in result, f"Unexpected response: {result}"
        # The export should have run — usda dir still present and updated
        usda_dir = _usda_dir(tmp_path, project_id)
        assert usda_dir.exists(), "usda/ directory missing after add_evidence"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: composition resource shows layer structure after export
# ─────────────────────────────────────────────────────────────────────────────


class TestCompositionResourceStructure:
    @pytest.mark.asyncio
    async def test_composition_resource_lists_all_sublayers(
        self, tmp_path: Path
    ) -> None:
        """Composition resource must list each of the 6 arc sublayers."""
        project_id = "proj_composition_structure"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        # Generate USDA files first
        usda_dir = _usda_dir(tmp_path, project_id)
        export_stage_to_usda(stage, usda_dir)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await get_composition_view(project_id=project_id, ctx=ctx)

        for filename in SUBLAYER_ORDER:
            assert filename in result, (
                f"Sublayer '{filename}' not listed in composition resource output"
            )

    @pytest.mark.asyncio
    async def test_composition_resource_shows_project_id(
        self, tmp_path: Path
    ) -> None:
        """Composition resource must include the project_id in its output."""
        project_id = "proj_composition_id"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        usda_dir = _usda_dir(tmp_path, project_id)
        export_stage_to_usda(stage, usda_dir)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await get_composition_view(project_id=project_id, ctx=ctx)

        assert project_id in result

    @pytest.mark.asyncio
    async def test_composition_resource_shows_prim_counts_after_assert(
        self, tmp_path: Path
    ) -> None:
        """After asserting, prim count for the relevant layer must be > 0."""
        project_id = "proj_composition_prims"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content="PostgreSQL is production-grade.",
                arc=CompositionArc.SPECIALIZES.value,
                ctx=ctx,
                project_id=project_id,
            )

            result = await get_composition_view(project_id=project_id, ctx=ctx)

        # safety_specializes.usda should report 1 prim (the assertion we added)
        assert "safety_specializes.usda" in result
        # The prim count line should show '1 prims' for SPECIALIZES
        assert "1 prims" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: composition resource shows consistency PASS after export
# ─────────────────────────────────────────────────────────────────────────────


class TestCompositionResourceConsistency:
    @pytest.mark.asyncio
    async def test_composition_resource_consistency_pass_empty_stage(
        self, tmp_path: Path
    ) -> None:
        """Empty stage: SQL and USDA resolution agree — consistency PASS."""
        project_id = "proj_consistency_empty"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        usda_dir = _usda_dir(tmp_path, project_id)
        export_stage_to_usda(stage, usda_dir)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await get_composition_view(project_id=project_id, ctx=ctx)

        assert "Consistency: PASS" in result, (
            f"Expected PASS for empty stage, got:\n{result}"
        )

    @pytest.mark.asyncio
    async def test_composition_resource_consistency_pass_with_assertions(
        self, tmp_path: Path
    ) -> None:
        """Stage with assertions: SQL and USDA resolution must agree."""
        project_id = "proj_consistency_asserted"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            await cb_manage_assertion(
                action="assert",
                topic_path="/architecture/database",
                content="PostgreSQL is reliable.",
                arc=CompositionArc.SPECIALIZES.value,
                ctx=ctx,
                project_id=project_id,
            )

            result = await get_composition_view(project_id=project_id, ctx=ctx)

        assert "Consistency: PASS" in result, (
            f"Expected PASS after single assert, got:\n{result}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: cb_manage_project(action='usda_export') generates files on demand
# ─────────────────────────────────────────────────────────────────────────────


class TestUsedaExportProjectAction:
    @pytest.mark.asyncio
    async def test_usda_export_action_creates_files(self, tmp_path: Path) -> None:
        """cb_manage_project usda_export creates 7 .usda files."""
        project_id = "proj_manual_export"
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id=project_id, project_name="Manual Export")
        active_stages: dict = {project_id: stage}
        save_stage_to_db(store, stage)
        ctx = _make_ctx(store=store, active_stages=active_stages)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await cb_manage_project(
                action="usda_export",
                project_id=project_id,
                ctx=ctx,
            )

        assert "USDA export complete" in result, f"Unexpected: {result}"
        assert "Files: 7" in result

        usda_dir = _usda_dir(tmp_path, project_id)
        assert usda_dir.exists()
        expected = set(SUBLAYER_ORDER) | {"stage.usda"}
        actual = {f.name for f in usda_dir.iterdir() if f.suffix == ".usda"}
        assert expected == actual

    @pytest.mark.asyncio
    async def test_usda_export_action_requires_project_id(
        self, tmp_path: Path
    ) -> None:
        """usda_export without project_id returns an error."""
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await cb_manage_project(
                action="usda_export",
                ctx=ctx,
            )

        assert result.startswith("ERROR"), f"Expected ERROR, got: {result}"

    @pytest.mark.asyncio
    async def test_usda_export_action_requires_active_project(
        self, tmp_path: Path
    ) -> None:
        """usda_export on a non-active project_id returns an error."""
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await cb_manage_project(
                action="usda_export",
                project_id="proj_not_active",
                ctx=ctx,
            )

        assert result.startswith("ERROR"), f"Expected ERROR, got: {result}"

    @pytest.mark.asyncio
    async def test_usda_export_action_reports_directory(self, tmp_path: Path) -> None:
        """usda_export response must include the output directory path."""
        project_id = "proj_dir_check"
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id=project_id, project_name="Dir Check")
        active_stages: dict = {project_id: stage}
        save_stage_to_db(store, stage)
        ctx = _make_ctx(store=store, active_stages=active_stages)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await cb_manage_project(
                action="usda_export",
                project_id=project_id,
                ctx=ctx,
            )

        assert str(tmp_path) in result, "Output directory path missing from response"


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: composition resource before any export returns helpful message
# ─────────────────────────────────────────────────────────────────────────────


class TestCompositionResourceBeforeExport:
    @pytest.mark.asyncio
    async def test_composition_resource_before_export_suggests_action(
        self, tmp_path: Path
    ) -> None:
        """When no USDA files exist, resource must suggest usda_export action."""
        project_id = "proj_no_usda"
        ctx, stage, store = _make_ctx_with_stage(project_id)

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await get_composition_view(project_id=project_id, ctx=ctx)

        assert "usda_export" in result, (
            "Composition resource must suggest cb_manage_project action='usda_export' "
            f"when no USDA files exist. Got:\n{result}"
        )

    @pytest.mark.asyncio
    async def test_composition_resource_unloaded_project_returns_error(
        self, tmp_path: Path
    ) -> None:
        """When project is not loaded, resource returns a not-loaded message."""
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})

        with patch.dict(os.environ, {"CB_DB_DIR": str(tmp_path)}):
            result = await get_composition_view(project_id="not_loaded", ctx=ctx)

        assert "not loaded" in result.lower(), (
            f"Expected 'not loaded' message, got:\n{result}"
        )
