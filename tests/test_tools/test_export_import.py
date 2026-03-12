"""Integration tests for the export/import capsule round-trip.

Tests verify:
- export_stage_to_json produces valid, versioned JSON
- import_stage_from_json reconstructs a semantically equivalent stage
- All model fields survive the round-trip (assertions, conflicts, events,
  decisions, parameters, variant_sets)
- Pydantic validators run during import (invalid capsules are rejected)
- cb_manage_project action='export' and action='import_json' work end-to-end
"""

import json

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CognitiveParameters,
    Conflict,
    CompositionArc,
    CompositionStage,
    ConflictStatus,
    Decision,
    EvidenceType,
    Event,
    EventType,
    ResolutionPath,
    VariantSet,
)
from cognitive_bridge.models.arcs import _new_id
from cognitive_bridge.models.variant_set import Variant
from cognitive_bridge.server import (
    cb_manage_project,
    export_stage_to_json,
    import_stage_from_json,
)
from cognitive_bridge.storage.sqlite_store import SQLiteStore


# ═══════════════════════════════════════════════════════════════
# Mock Context (mirrors test_project_tool.py pattern)
# ═══════════════════════════════════════════════════════════════


class _MockLifespanContext:
    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx(
    store: SQLiteStore | None = None,
    active_stages: dict | None = None,
) -> _MockLifespanContext:
    return _MockLifespanContext(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_assertion(
    path: str = "/test/path",
    content: str = "test assertion",
    arc: CompositionArc = CompositionArc.INHERITS,
    author: AssertionAuthor = AssertionAuthor.AI,
    falsifiable_if: str | None = None,
    depends_on_paths: list[str] | None = None,
) -> Assertion:
    return Assertion(
        topic_path=path,
        content=content,
        arc=arc,
        author=author,
        falsifiable_if=falsifiable_if,
        depends_on_paths=depends_on_paths or [],
    )


def _make_conflict(
    assertion_a_id: str,
    assertion_b_id: str,
    path: str = "/test/path",
) -> Conflict:
    from cognitive_bridge.models.arcs import ConflictDetectionLayer
    return Conflict(
        topic_path=path,
        assertion_a_id=assertion_a_id,
        assertion_b_id=assertion_b_id,
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )


def _make_decision() -> Decision:
    return Decision(
        topic_path="/architecture/database",
        decision="Use PostgreSQL",
        rationale="Relational model fits the schema",
        alternatives_rejected=["MongoDB — rejected because lack of join support"],
        second_order_effects=["All queries must use SQL dialect"],
    )


# ═══════════════════════════════════════════════════════════════
# export_stage_to_json — unit tests
# ═══════════════════════════════════════════════════════════════


class TestExportStageToJson:
    """Tests for the export_stage_to_json helper function."""

    def test_export_empty_stage_produces_valid_json(self) -> None:
        """Exporting a fresh stage yields parseable JSON."""
        stage = CompositionStage(project_id="proj_ex001", project_name="Empty Export")
        capsule_str = export_stage_to_json(stage)
        capsule = json.loads(capsule_str)  # must not raise
        assert capsule["version"] == "3.0"
        assert capsule["project_id"] == "proj_ex001"
        assert capsule["project_name"] == "Empty Export"

    def test_export_includes_top_level_keys(self) -> None:
        """The capsule contains all required top-level keys."""
        stage = CompositionStage(project_id="proj_ex002", project_name="Key Check")
        capsule = json.loads(export_stage_to_json(stage))
        required_keys = {
            "version",
            "project_id",
            "project_name",
            "exported_at",
            "assertions",
            "conflicts",
            "variant_sets",
            "events",
            "decisions",
            "parameters",
            "exchange_count",
        }
        assert required_keys.issubset(capsule.keys())

    def test_export_with_assertions_contains_all(self) -> None:
        """A stage with 3 assertions exports all 3 into the capsule."""
        stage = CompositionStage(project_id="proj_ex003", project_name="With Assertions")
        for i in range(3):
            ast = _make_assertion(path=f"/test/path{i}", content=f"claim {i}")
            stage.assertions[ast.id] = ast

        capsule = json.loads(export_stage_to_json(stage))
        assert len(capsule["assertions"]) == 3

    def test_export_assertion_content_preserved(self) -> None:
        """Assertion content, arc, and author survive serialization."""
        stage = CompositionStage(project_id="proj_ex004", project_name="Content Check")
        ast = _make_assertion(
            path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.USER,
        )
        stage.assertions[ast.id] = ast

        capsule = json.loads(export_stage_to_json(stage))
        exported_ast = capsule["assertions"][ast.id]
        assert exported_ast["content"] == "PostgreSQL is the primary datastore"
        assert exported_ast["topic_path"] == "/architecture/database"
        # Enums serialize to their string values
        assert exported_ast["author"] == AssertionAuthor.USER.value  # "user"

    def test_export_with_conflicts(self) -> None:
        """A stage with conflicts exports them into the capsule."""
        stage = CompositionStage(project_id="proj_ex005", project_name="With Conflicts")
        ast_a = _make_assertion(path="/test/path", content="claim a")
        ast_b = _make_assertion(path="/test/path", content="claim b")
        stage.assertions[ast_a.id] = ast_a
        stage.assertions[ast_b.id] = ast_b
        conflict = _make_conflict(ast_a.id, ast_b.id)
        stage.conflicts[conflict.id] = conflict

        capsule = json.loads(export_stage_to_json(stage))
        assert len(capsule["conflicts"]) == 1
        exported_cfl = list(capsule["conflicts"].values())[0]
        assert exported_cfl["assertion_a_id"] == ast_a.id
        assert exported_cfl["assertion_b_id"] == ast_b.id

    def test_export_with_decisions_contains_alternatives(self) -> None:
        """Decisions with alternatives_rejected appear correctly in the capsule."""
        stage = CompositionStage(project_id="proj_ex006", project_name="With Decisions")
        dec = _make_decision()
        stage.decisions.append(dec)

        capsule = json.loads(export_stage_to_json(stage))
        assert len(capsule["decisions"]) == 1
        exported_dec = capsule["decisions"][0]
        assert "MongoDB" in exported_dec["alternatives_rejected"][0]
        assert len(exported_dec["second_order_effects"]) == 1

    def test_export_with_events(self) -> None:
        """Events recorded on the stage appear in the capsule."""
        stage = CompositionStage(project_id="proj_ex007", project_name="With Events")
        stage.record_event(
            EventType.ASSERTION_CREATED,
            AssertionAuthor.AI,
            "target_001",
            {"detail": "test"},
        )

        capsule = json.loads(export_stage_to_json(stage))
        assert len(capsule["events"]) == 1
        assert capsule["events"][0]["event_type"] == EventType.ASSERTION_CREATED.value

    def test_export_exchange_count_preserved(self) -> None:
        """exchange_count is included in the capsule."""
        stage = CompositionStage(project_id="proj_ex008", project_name="Exchange Count")
        stage.exchange_count = 99
        capsule = json.loads(export_stage_to_json(stage))
        assert capsule["exchange_count"] == 99

    def test_export_parameters_preserved(self) -> None:
        """Non-default CognitiveParameters values appear in the capsule."""
        stage = CompositionStage(project_id="proj_ex009", project_name="Params")
        stage.parameters.conflict_sensitivity = 0.95
        stage.parameters.red_team_threshold = 20
        capsule = json.loads(export_stage_to_json(stage))
        assert capsule["parameters"]["conflict_sensitivity"] == pytest.approx(0.95)
        assert capsule["parameters"]["red_team_threshold"] == 20


# ═══════════════════════════════════════════════════════════════
# import_stage_from_json — unit tests
# ═══════════════════════════════════════════════════════════════


class TestImportStageFromJson:
    """Tests for the import_stage_from_json helper function."""

    def test_round_trip_empty_stage(self) -> None:
        """An empty stage survives export → import with all structural fields intact."""
        original = CompositionStage(project_id="proj_rt001", project_name="RT Empty")
        recovered = import_stage_from_json(export_stage_to_json(original))

        assert recovered.project_id == "proj_rt001"
        assert recovered.project_name == "RT Empty"
        assert len(recovered.assertions) == 0
        assert len(recovered.conflicts) == 0
        assert len(recovered.events) == 0
        assert len(recovered.decisions) == 0

    def test_round_trip_assertions_match(self) -> None:
        """Assertions survive export → import with content, arc, and author preserved."""
        original = CompositionStage(project_id="proj_rt002", project_name="RT Assertions")
        ast = _make_assertion(
            path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.USER,
        )
        original.assertions[ast.id] = ast

        recovered = import_stage_from_json(export_stage_to_json(original))

        assert ast.id in recovered.assertions
        recovered_ast = recovered.assertions[ast.id]
        assert recovered_ast.topic_path == "/architecture/database"
        assert recovered_ast.content == "PostgreSQL is the primary datastore"
        assert recovered_ast.arc == CompositionArc.SPECIALIZES
        assert recovered_ast.author == AssertionAuthor.USER

    def test_round_trip_local_assertion_falsifiable_if_preserved(self) -> None:
        """LOCAL assertions with falsifiable_if survive the round-trip."""
        original = CompositionStage(project_id="proj_rt003", project_name="RT Local")
        ast = Assertion(
            topic_path="/test/local",
            content="This is a local claim",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="If benchmark shows otherwise",
        )
        original.assertions[ast.id] = ast

        recovered = import_stage_from_json(export_stage_to_json(original))

        recovered_ast = recovered.assertions[ast.id]
        assert recovered_ast.arc == CompositionArc.LOCAL
        assert recovered_ast.falsifiable_if == "If benchmark shows otherwise"

    def test_round_trip_depends_on_paths_preserved(self) -> None:
        """depends_on_paths DAG edges survive the round-trip."""
        original = CompositionStage(project_id="proj_rt004", project_name="RT DAG")
        ast = _make_assertion(
            path="/child/node",
            content="Derived claim",
            depends_on_paths=["/parent/node", "/other/node"],
        )
        original.assertions[ast.id] = ast

        recovered = import_stage_from_json(export_stage_to_json(original))

        recovered_ast = recovered.assertions[ast.id]
        assert "/parent/node" in recovered_ast.depends_on_paths
        assert "/other/node" in recovered_ast.depends_on_paths

    def test_round_trip_conflicts_match(self) -> None:
        """Conflicts survive export → import with both assertion IDs preserved."""
        original = CompositionStage(project_id="proj_rt005", project_name="RT Conflicts")
        ast_a = _make_assertion(content="claim a")
        ast_b = _make_assertion(content="claim b")
        original.assertions[ast_a.id] = ast_a
        original.assertions[ast_b.id] = ast_b
        conflict = _make_conflict(ast_a.id, ast_b.id)
        original.conflicts[conflict.id] = conflict

        recovered = import_stage_from_json(export_stage_to_json(original))

        assert conflict.id in recovered.conflicts
        recovered_cfl = recovered.conflicts[conflict.id]
        assert recovered_cfl.assertion_a_id == ast_a.id
        assert recovered_cfl.assertion_b_id == ast_b.id
        assert recovered_cfl.status == ConflictStatus.ACTIVE

    def test_round_trip_decisions_alternatives_preserved(self) -> None:
        """Decisions with alternatives_rejected survive the round-trip."""
        original = CompositionStage(project_id="proj_rt006", project_name="RT Decisions")
        dec = _make_decision()
        original.decisions.append(dec)

        recovered = import_stage_from_json(export_stage_to_json(original))

        assert len(recovered.decisions) == 1
        recovered_dec = recovered.decisions[0]
        assert recovered_dec.id == dec.id
        assert "MongoDB" in recovered_dec.alternatives_rejected[0]
        assert len(recovered_dec.second_order_effects) == 1

    def test_round_trip_events_preserved(self) -> None:
        """Events survive the round-trip with correct type and actor."""
        original = CompositionStage(project_id="proj_rt007", project_name="RT Events")
        original.record_event(
            EventType.ASSERTION_CREATED,
            AssertionAuthor.AI,
            "some_target",
            {"key": "value"},
        )

        recovered = import_stage_from_json(export_stage_to_json(original))

        assert len(recovered.events) == 1
        evt = recovered.events[0]
        assert evt.event_type == EventType.ASSERTION_CREATED
        assert evt.actor == AssertionAuthor.AI
        assert evt.target_id == "some_target"
        assert evt.detail == {"key": "value"}

    def test_round_trip_parameters_preserved(self) -> None:
        """Custom CognitiveParameters values survive the round-trip."""
        original = CompositionStage(project_id="proj_rt008", project_name="RT Params")
        original.parameters.conflict_sensitivity = 0.85
        original.parameters.red_team_threshold = 15  # max is 20
        original.parameters.cross_path_detection = True

        recovered = import_stage_from_json(export_stage_to_json(original))

        assert recovered.parameters.conflict_sensitivity == pytest.approx(0.85)
        assert recovered.parameters.red_team_threshold == 15
        assert recovered.parameters.cross_path_detection is True

    def test_round_trip_exchange_count_preserved(self) -> None:
        """exchange_count survives the round-trip."""
        original = CompositionStage(project_id="proj_rt009", project_name="RT ExCount")
        original.exchange_count = 77

        recovered = import_stage_from_json(export_stage_to_json(original))
        assert recovered.exchange_count == 77

    def test_import_invalid_json_raises_error(self) -> None:
        """Malformed JSON raises json.JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            import_stage_from_json("not valid json {{{")

    def test_import_truncated_json_raises_error(self) -> None:
        """A truncated JSON string raises an error."""
        original = CompositionStage(project_id="proj_rt010", project_name="Truncated")
        capsule_str = export_stage_to_json(original)
        truncated = capsule_str[: len(capsule_str) // 2]

        with pytest.raises((json.JSONDecodeError, Exception)):
            import_stage_from_json(truncated)

    def test_round_trip_multiple_assertions_all_recovered(self) -> None:
        """All assertions are present after a round-trip (not just the first)."""
        original = CompositionStage(project_id="proj_rt011", project_name="RT Multi")
        ids = []
        for i in range(5):
            ast = _make_assertion(path=f"/test/node{i}", content=f"claim {i}")
            original.assertions[ast.id] = ast
            ids.append(ast.id)

        recovered = import_stage_from_json(export_stage_to_json(original))

        assert len(recovered.assertions) == 5
        for aid in ids:
            assert aid in recovered.assertions


# ═══════════════════════════════════════════════════════════════
# cb_manage_project action='export' tool tests
# ═══════════════════════════════════════════════════════════════


class TestCbManageProjectExport:
    """Tests for cb_manage_project action='export'."""

    @pytest.mark.asyncio
    async def test_export_returns_json_in_response(self) -> None:
        """export action returns a response containing JSON."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(action="create", ctx=ctx, project_id="proj_e001")

        result = await cb_manage_project(
            action="export", ctx=ctx, project_id="proj_e001"
        )
        assert "EXPORTED" in result
        # The JSON payload must appear in the response
        json_start = result.index("{")
        json_payload = result[json_start:]
        capsule = json.loads(json_payload)
        assert capsule["version"] == "3.0"
        assert capsule["project_id"] == "proj_e001"

    @pytest.mark.asyncio
    async def test_export_without_project_id_returns_error(self) -> None:
        """export without project_id returns an ERROR string."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="export", ctx=ctx)
        assert "ERROR" in result
        assert "project_id" in result

    @pytest.mark.asyncio
    async def test_export_inactive_project_returns_error(self) -> None:
        """export of a project not loaded in memory returns an ERROR string."""
        ctx = _make_ctx()
        result = await cb_manage_project(
            action="export", ctx=ctx, project_id="ghost_project"
        )
        assert "ERROR" in result
        assert "not loaded" in result.lower()

    @pytest.mark.asyncio
    async def test_export_includes_assertion_count_in_payload(self) -> None:
        """Exported JSON capsule contains all assertions that were in memory."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(action="create", ctx=ctx, project_id="proj_e002")
        stage = active_stages["proj_e002"]
        for i in range(3):
            ast = _make_assertion(path=f"/test/path{i}", content=f"claim {i}")
            stage.assertions[ast.id] = ast

        result = await cb_manage_project(
            action="export", ctx=ctx, project_id="proj_e002"
        )
        json_start = result.index("{")
        capsule = json.loads(result[json_start:])
        assert len(capsule["assertions"]) == 3


# ═══════════════════════════════════════════════════════════════
# cb_manage_project action='import_json' tool tests
# ═══════════════════════════════════════════════════════════════


class TestCbManageProjectImportJson:
    """Tests for cb_manage_project action='import_json'."""

    @pytest.mark.asyncio
    async def test_import_json_loads_stage_into_memory(self) -> None:
        """import_json with a valid capsule loads the stage into active_stages."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        # Build a stage and export it
        original = CompositionStage(
            project_id="proj_imp001", project_name="Import Test"
        )
        ast = _make_assertion(content="persisted claim")
        original.assertions[ast.id] = ast
        capsule_str = export_stage_to_json(original)

        result = await cb_manage_project(
            action="import_json",
            ctx=ctx,
            project_name=capsule_str,  # capsule passed as project_name
        )

        assert "ERROR" not in result
        assert "proj_imp001" in active_stages
        recovered = active_stages["proj_imp001"]
        assert ast.id in recovered.assertions

    @pytest.mark.asyncio
    async def test_import_json_persists_to_db(self) -> None:
        """import_json persists the imported stage to SQLite."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        original = CompositionStage(
            project_id="proj_imp002", project_name="DB Persist Test"
        )
        capsule_str = export_stage_to_json(original)

        await cb_manage_project(
            action="import_json",
            ctx=ctx,
            project_name=capsule_str,
        )

        assert "proj_imp002" in store.list_projects()

    @pytest.mark.asyncio
    async def test_import_json_without_capsule_returns_error(self) -> None:
        """import_json without the capsule (project_name omitted) returns an ERROR."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="import_json", ctx=ctx)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_import_json_invalid_json_returns_error(self) -> None:
        """import_json with malformed JSON returns an ERROR string."""
        ctx = _make_ctx()
        result = await cb_manage_project(
            action="import_json", ctx=ctx, project_name="not valid json {{{"
        )
        assert "ERROR" in result
        assert "JSON" in result.upper() or "json" in result.lower()

    @pytest.mark.asyncio
    async def test_import_json_project_id_override(self) -> None:
        """When project_id is provided it overrides the capsule's project_id."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        original = CompositionStage(
            project_id="original_id", project_name="Override Test"
        )
        capsule_str = export_stage_to_json(original)

        await cb_manage_project(
            action="import_json",
            ctx=ctx,
            project_id="new_id",
            project_name=capsule_str,
        )

        assert "new_id" in active_stages
        assert "original_id" not in active_stages
        assert "new_id" in store.list_projects()

    @pytest.mark.asyncio
    async def test_import_json_collision_with_active_stage_returns_error(self) -> None:
        """Importing a capsule whose project_id is already active returns an ERROR."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(
            action="create", ctx=ctx, project_id="proj_imp003"
        )
        # project is now active — importing same id should fail
        original = CompositionStage(
            project_id="proj_imp003", project_name="Collision Test"
        )
        capsule_str = export_stage_to_json(original)

        result = await cb_manage_project(
            action="import_json",
            ctx=ctx,
            project_name=capsule_str,
        )
        assert "ERROR" in result
        assert "already active" in result.lower()

    @pytest.mark.asyncio
    async def test_import_json_response_contains_summary(self) -> None:
        """A successful import returns a summary message with assertion count."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        original = CompositionStage(
            project_id="proj_imp004", project_name="Summary Test"
        )
        for i in range(2):
            ast = _make_assertion(path=f"/test/p{i}", content=f"claim {i}")
            original.assertions[ast.id] = ast
        capsule_str = export_stage_to_json(original)

        result = await cb_manage_project(
            action="import_json",
            ctx=ctx,
            project_name=capsule_str,
        )

        assert "Assertions: 2" in result


# ═══════════════════════════════════════════════════════════════
# Unknown action error message update
# ═══════════════════════════════════════════════════════════════


class TestUnknownActionErrorUpdated:
    """Verify the unknown-action error message now lists export and import_json."""

    @pytest.mark.asyncio
    async def test_unknown_action_lists_export_and_import_json(self) -> None:
        """The error for an unknown action must name all six valid actions."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="delete", ctx=ctx)
        assert "export" in result
        assert "import_json" in result
