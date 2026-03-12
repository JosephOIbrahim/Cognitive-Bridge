"""Integration tests for cb_manage_project tool and server storage helpers.

Two test strategies are used:

1. Direct helper tests — call save_stage_to_db / load_stage_from_db directly
   against an in-memory SQLiteStore. These are fast and self-contained.

2. Tool handler tests — call cb_manage_project directly using a minimal mock
   Context whose lifespan_context contains an in-memory store and an isolated
   active_stages dict. This avoids MCP transport overhead while still exercising
   all tool branches.

No shared mutable state exists between tests: each test builds its own
SQLiteStore(":memory:") and active_stages dict.
"""

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    EventType,
)
from cognitive_bridge.server import (
    cb_manage_project,
    load_stage_from_db,
    save_stage_to_db,
)
from cognitive_bridge.storage.sqlite_store import SQLiteStore


# ═══════════════════════════════════════════════════════════════
# Mock Context
# ═══════════════════════════════════════════════════════════════


class _MockLifespanContext:
    """Minimal lifespan_context dict wrapper that also acts as the context."""

    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {
            "store": store,
            "active_stages": active_stages,
        }


def _make_ctx(
    store: SQLiteStore | None = None,
    active_stages: dict | None = None,
) -> _MockLifespanContext:
    """Build a mock context with optional overrides."""
    return _MockLifespanContext(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


# ═══════════════════════════════════════════════════════════════
# Helper function tests: save_stage_to_db / load_stage_from_db
# ═══════════════════════════════════════════════════════════════


class TestSaveAndLoadRoundTrip:
    """Round-trip tests for the internal persistence helpers."""

    def test_empty_stage_round_trip(self) -> None:
        """An empty stage (no assertions/conflicts/events) survives a full round-trip."""
        store = SQLiteStore(":memory:")
        stage = CompositionStage(
            project_id="proj_rt001",
            project_name="Round-Trip Test",
        )

        save_stage_to_db(store, stage)
        recovered = load_stage_from_db(store, "proj_rt001")

        assert recovered.project_id == "proj_rt001"
        assert recovered.project_name == "Round-Trip Test"
        assert len(recovered.assertions) == 0
        assert len(recovered.conflicts) == 0
        assert len(recovered.events) == 0
        assert len(recovered.decisions) == 0

    def test_stage_with_assertions_round_trip(self) -> None:
        """A stage with assertions persists and recovers assertion content and arc."""
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_rt002", project_name="With Assertions")

        ast = Assertion(
            topic_path="/architecture/database",
            content="PostgreSQL is the primary datastore",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast

        save_stage_to_db(store, stage)
        recovered = load_stage_from_db(store, "proj_rt002")

        assert len(recovered.assertions) == 1
        loaded_ast = recovered.assertions[ast.id]
        assert loaded_ast.topic_path == "/architecture/database"
        assert loaded_ast.content == "PostgreSQL is the primary datastore"
        assert loaded_ast.arc == CompositionArc.INHERITS
        assert loaded_ast.author == AssertionAuthor.AI

    def test_stage_with_events_round_trip(self) -> None:
        """Events recorded on the stage are persisted and recovered in full."""
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_rt003", project_name="With Events")
        stage.record_event(
            EventType.PROJECT_LOADED,
            AssertionAuthor.SYSTEM,
            "proj_rt003",
            {"action": "created"},
        )

        save_stage_to_db(store, stage)
        recovered = load_stage_from_db(store, "proj_rt003")

        assert len(recovered.events) == 1
        evt = recovered.events[0]
        assert evt.event_type == EventType.PROJECT_LOADED
        assert evt.actor == AssertionAuthor.SYSTEM
        assert evt.target_id == "proj_rt003"
        assert evt.detail == {"action": "created"}

    def test_upsert_updates_project_name(self) -> None:
        """Calling save_stage_to_db twice with a changed project_name updates the row."""
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_rt004", project_name="Original Name")
        save_stage_to_db(store, stage)

        stage.project_name = "Updated Name"
        save_stage_to_db(store, stage)

        recovered = load_stage_from_db(store, "proj_rt004")
        assert recovered.project_name == "Updated Name"

    def test_events_are_append_only_no_duplicates(self) -> None:
        """Saving the same stage twice does not duplicate events in the database."""
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_rt005", project_name="No Dup Events")
        stage.record_event(
            EventType.PROJECT_LOADED,
            AssertionAuthor.SYSTEM,
            "proj_rt005",
            {},
        )

        save_stage_to_db(store, stage)
        save_stage_to_db(store, stage)  # second save — same event, must not duplicate

        recovered = load_stage_from_db(store, "proj_rt005")
        assert len(recovered.events) == 1

    def test_load_nonexistent_project_raises_value_error(self) -> None:
        """load_stage_from_db raises ValueError when the project does not exist."""
        store = SQLiteStore(":memory:")
        with pytest.raises(ValueError, match="not found"):
            load_stage_from_db(store, "does_not_exist")

    def test_exchange_count_persisted(self) -> None:
        """exchange_count is persisted and recovered correctly."""
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_rt006", project_name="Exchange Count")
        stage.exchange_count = 42
        save_stage_to_db(store, stage)

        recovered = load_stage_from_db(store, "proj_rt006")
        assert recovered.exchange_count == 42


# ═══════════════════════════════════════════════════════════════
# cb_manage_project tool tests
# ═══════════════════════════════════════════════════════════════


class TestCbManageProjectCreate:
    """Tests for action='create'."""

    @pytest.mark.asyncio
    async def test_create_returns_success_message(self) -> None:
        """create action returns a success message containing the project_id."""
        ctx = _make_ctx()
        result = await cb_manage_project(
            action="create",
            ctx=ctx,
            project_id="proj_c001",
            project_name="Test Project",
        )
        assert "proj_c001" in result
        assert "created" in result.lower()

    @pytest.mark.asyncio
    async def test_create_persists_to_store(self) -> None:
        """After create, the project_id appears in store.list_projects()."""
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store)
        await cb_manage_project(
            action="create",
            ctx=ctx,
            project_id="proj_c002",
        )
        assert "proj_c002" in store.list_projects()

    @pytest.mark.asyncio
    async def test_create_adds_to_active_stages(self) -> None:
        """After create, the project appears in active_stages."""
        active_stages: dict = {}
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages=active_stages)
        await cb_manage_project(
            action="create",
            ctx=ctx,
            project_id="proj_c003",
        )
        assert "proj_c003" in active_stages

    @pytest.mark.asyncio
    async def test_create_uses_project_id_as_name_when_name_omitted(self) -> None:
        """When project_name is not provided, project_id is used as the name."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)
        await cb_manage_project(
            action="create",
            ctx=ctx,
            project_id="proj_c004",
        )
        stage = active_stages["proj_c004"]
        assert stage.project_name == "proj_c004"

    @pytest.mark.asyncio
    async def test_create_missing_project_id_returns_error(self) -> None:
        """create without a project_id returns an error string."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="create", ctx=ctx)
        assert "ERROR" in result
        assert "project_id" in result

    @pytest.mark.asyncio
    async def test_create_duplicate_project_id_returns_error(self) -> None:
        """create with an already-active project_id returns an error string."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)
        await cb_manage_project(
            action="create", ctx=ctx, project_id="proj_c005"
        )
        result = await cb_manage_project(
            action="create", ctx=ctx, project_id="proj_c005"
        )
        assert "ERROR" in result
        assert "already active" in result.lower()


class TestCbManageProjectLoad:
    """Tests for action='load'."""

    @pytest.mark.asyncio
    async def test_load_returns_stage_summary(self) -> None:
        """load returns a summary string with assertion count and event count."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        # Create a project first
        await cb_manage_project(
            action="create", ctx=ctx, project_id="proj_l001", project_name="Load Test"
        )
        # Remove from active_stages so we can test load
        del active_stages["proj_l001"]

        result = await cb_manage_project(
            action="load", ctx=ctx, project_id="proj_l001"
        )

        assert "proj_l001" in result
        assert "Assertions:" in result
        assert "Events:" in result

    @pytest.mark.asyncio
    async def test_load_populates_active_stages(self) -> None:
        """After load, the project appears in active_stages."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(
            action="create", ctx=ctx, project_id="proj_l002"
        )
        del active_stages["proj_l002"]

        assert "proj_l002" not in active_stages
        await cb_manage_project(action="load", ctx=ctx, project_id="proj_l002")
        assert "proj_l002" in active_stages

    @pytest.mark.asyncio
    async def test_load_missing_project_id_returns_error(self) -> None:
        """load without a project_id returns an error string."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="load", ctx=ctx)
        assert "ERROR" in result
        assert "project_id" in result

    @pytest.mark.asyncio
    async def test_load_nonexistent_project_returns_error(self) -> None:
        """load of a project that doesn't exist returns an error string."""
        ctx = _make_ctx()
        result = await cb_manage_project(
            action="load", ctx=ctx, project_id="ghost_project"
        )
        assert "ERROR" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_load_recovers_assertions(self) -> None:
        """load recovers assertions that were previously created and saved."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(
            action="create", ctx=ctx, project_id="proj_l003"
        )
        stage = active_stages["proj_l003"]
        ast = Assertion(
            topic_path="/test/path",
            content="test assertion",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)

        # Reload
        del active_stages["proj_l003"]
        await cb_manage_project(action="load", ctx=ctx, project_id="proj_l003")
        loaded_stage = active_stages["proj_l003"]

        assert ast.id in loaded_stage.assertions
        assert loaded_stage.assertions[ast.id].content == "test assertion"


class TestCbManageProjectSave:
    """Tests for action='save'."""

    @pytest.mark.asyncio
    async def test_save_returns_success_message(self) -> None:
        """save returns a confirmation message."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)
        await cb_manage_project(
            action="create", ctx=ctx, project_id="proj_s001"
        )

        result = await cb_manage_project(
            action="save", ctx=ctx, project_id="proj_s001"
        )
        assert "proj_s001" in result
        assert "saved" in result.lower()

    @pytest.mark.asyncio
    async def test_save_missing_project_id_returns_error(self) -> None:
        """save without a project_id returns an error."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="save", ctx=ctx)
        assert "ERROR" in result
        assert "project_id" in result

    @pytest.mark.asyncio
    async def test_save_not_loaded_project_returns_error(self) -> None:
        """save of a project that is not in active_stages returns an error."""
        ctx = _make_ctx()
        result = await cb_manage_project(
            action="save", ctx=ctx, project_id="not_loaded"
        )
        assert "ERROR" in result
        assert "not loaded" in result.lower()

    @pytest.mark.asyncio
    async def test_save_persists_changes(self) -> None:
        """Changes made to the in-memory stage are persisted after save."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(
            action="create", ctx=ctx, project_id="proj_s002", project_name="Original"
        )
        active_stages["proj_s002"].project_name = "Modified"
        await cb_manage_project(action="save", ctx=ctx, project_id="proj_s002")

        recovered = load_stage_from_db(store, "proj_s002")
        assert recovered.project_name == "Modified"


class TestCbManageProjectList:
    """Tests for action='list'."""

    @pytest.mark.asyncio
    async def test_list_empty_store_returns_no_projects_message(self) -> None:
        """list on an empty store returns a 'no projects' message."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="list", ctx=ctx)
        assert "No projects found" in result

    @pytest.mark.asyncio
    async def test_list_shows_created_projects(self) -> None:
        """list shows all projects that have been created."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(action="create", ctx=ctx, project_id="proj_a")
        await cb_manage_project(action="create", ctx=ctx, project_id="proj_b")

        result = await cb_manage_project(action="list", ctx=ctx)
        assert "proj_a" in result
        assert "proj_b" in result

    @pytest.mark.asyncio
    async def test_list_marks_active_projects(self) -> None:
        """list marks projects that are currently in active_stages with '(active)'."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(action="create", ctx=ctx, project_id="proj_active")

        result = await cb_manage_project(action="list", ctx=ctx)
        # The active project should be marked
        assert "(active)" in result

    @pytest.mark.asyncio
    async def test_list_does_not_mark_unloaded_projects(self) -> None:
        """Projects that exist in the DB but not in active_stages have no (active) marker."""
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        await cb_manage_project(action="create", ctx=ctx, project_id="proj_inactive")
        del active_stages["proj_inactive"]

        result = await cb_manage_project(action="list", ctx=ctx)
        assert "proj_inactive" in result
        # Must appear without active marker
        lines = result.splitlines()
        inactive_lines = [l for l in lines if "proj_inactive" in l]
        assert len(inactive_lines) == 1
        assert "(active)" not in inactive_lines[0]


class TestCbManageProjectUnknownAction:
    """Tests for unknown action error handling."""

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self) -> None:
        """An unrecognized action string returns an error message."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="delete", ctx=ctx)
        assert "ERROR" in result
        assert "delete" in result

    @pytest.mark.asyncio
    async def test_unknown_action_names_valid_options(self) -> None:
        """The error message for an unknown action lists valid options."""
        ctx = _make_ctx()
        result = await cb_manage_project(action="xyz", ctx=ctx)
        # All four valid actions should appear in the error
        assert "create" in result
        assert "load" in result
        assert "save" in result
        assert "list" in result
