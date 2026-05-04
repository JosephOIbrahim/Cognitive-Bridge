"""Integration tests for server.py lifespan and cb_manage_project tool.

Blueprint reference: Section 6 (cb_manage_project), CLAUDE.md Phase 4 / P4.T2.
Constitution rules C8 (event-log audit), G5 (test isolation via tmp_path).
"""

import pytest

from cognitive_bridge.models import (
    Assertion, AssertionAuthor, CompositionArc, CompositionStage, EventType,
)
from cognitive_bridge.server import (
    cb_manage_project, lifespan, load_stage_from_db, mcp, save_stage_to_db,
)
from cognitive_bridge.storage.sqlite_store import SQLiteStore


class _MockCtx:
    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx(store: SQLiteStore | None = None, active_stages: dict | None = None) -> _MockCtx:
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_yields_store_and_active_stages(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("CB_DB_DIR", str(tmp_path))
        async with lifespan(mcp) as ctx:
            assert "store" in ctx
            assert "active_stages" in ctx
            assert isinstance(ctx["store"], SQLiteStore)
            assert isinstance(ctx["active_stages"], dict)

    @pytest.mark.asyncio
    async def test_lifespan_creates_db_file(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("CB_DB_DIR", str(tmp_path))
        async with lifespan(mcp):
            assert (tmp_path / "cognitive_bridge.db").exists()

    @pytest.mark.asyncio
    async def test_lifespan_disposes_store_on_exit(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("CB_DB_DIR", str(tmp_path))
        captured_store = None
        async with lifespan(mcp) as ctx:
            captured_store = ctx["store"]
        assert captured_store is not None

    @pytest.mark.asyncio
    async def test_lifespan_active_stages_shared_dict(self, tmp_path, monkeypatch) -> None:
        from cognitive_bridge import server as server_module
        monkeypatch.setenv("CB_DB_DIR", str(tmp_path))
        async with lifespan(mcp) as ctx:
            assert ctx["active_stages"] is server_module._ACTIVE_STAGES


class TestCreateAction:
    @pytest.mark.asyncio
    async def test_create_returns_success_message_with_project_id(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})
        result = await cb_manage_project(
            action="create", project_id="proj_alpha", project_name="Alpha Project", ctx=ctx,
        )
        assert "proj_alpha" in result
        assert "ERROR" not in result

    @pytest.mark.asyncio
    async def test_create_populates_active_stages(self) -> None:
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        await cb_manage_project(
            action="create", project_id="proj_beta", project_name="Beta Project", ctx=ctx,
        )
        assert "proj_beta" in active_stages
        assert isinstance(active_stages["proj_beta"], CompositionStage)

    @pytest.mark.asyncio
    async def test_create_persists_project_row_to_sqlite(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _MockCtx(store=store, active_stages={})
        await cb_manage_project(
            action="create", project_id="proj_gamma", project_name="Gamma", ctx=ctx,
        )
        assert "proj_gamma" in store.list_projects()

    @pytest.mark.asyncio
    async def test_create_without_project_id_returns_error(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})
        result = await cb_manage_project(action="create", ctx=ctx)
        assert result.startswith("ERROR")

    @pytest.mark.asyncio
    async def test_create_already_active_project_returns_error(self) -> None:
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_dup", project_name="Dup")
        active_stages: dict = {"proj_dup": stage}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        result = await cb_manage_project(action="create", project_id="proj_dup", ctx=ctx)
        assert result.startswith("ERROR")

    @pytest.mark.asyncio
    async def test_create_records_project_loaded_event(self) -> None:
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        await cb_manage_project(
            action="create", project_id="proj_evt", project_name="Event Test", ctx=ctx,
        )
        stage = active_stages["proj_evt"]
        assert EventType.PROJECT_LOADED in [e.event_type for e in stage.events]

    @pytest.mark.asyncio
    async def test_create_uses_project_id_as_name_when_name_omitted(self) -> None:
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        await cb_manage_project(action="create", project_id="proj_noname", ctx=ctx)
        assert active_stages["proj_noname"].project_name == "proj_noname"


class TestLoadAction:
    @pytest.mark.asyncio
    async def test_load_nonexistent_project_returns_error(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})
        result = await cb_manage_project(action="load", project_id="proj_ghost", ctx=ctx)
        assert result.startswith("ERROR")

    @pytest.mark.asyncio
    async def test_load_without_project_id_returns_error(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})
        result = await cb_manage_project(action="load", ctx=ctx)
        assert result.startswith("ERROR")

    @pytest.mark.asyncio
    async def test_load_existing_project_populates_active_stages(self) -> None:
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_load", project_name="Load Me")
        save_stage_to_db(store, stage)
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        result = await cb_manage_project(action="load", project_id="proj_load", ctx=ctx)
        assert "ERROR" not in result
        assert "proj_load" in active_stages

    @pytest.mark.asyncio
    async def test_load_returns_assertion_count(self) -> None:
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_counts", project_name="Counts")
        ast = Assertion(
            topic_path="/test/path", content="Some claim",
            arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        save_stage_to_db(store, stage)
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        result = await cb_manage_project(action="load", project_id="proj_counts", ctx=ctx)
        assert "1" in result


class TestSaveAction:
    @pytest.mark.asyncio
    async def test_save_persists_stage(self) -> None:
        store = SQLiteStore(":memory:")
        stage = CompositionStage(project_id="proj_save", project_name="Save Test")
        active_stages: dict = {"proj_save": stage}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        save_stage_to_db(store, stage)
        ast = Assertion(
            topic_path="/db/engine", content="PostgreSQL",
            arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        result = await cb_manage_project(action="save", project_id="proj_save", ctx=ctx)
        assert "ERROR" not in result
        loaded = load_stage_from_db(store, "proj_save")
        assert ast.id in loaded.assertions

    @pytest.mark.asyncio
    async def test_save_without_project_id_returns_error(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})
        result = await cb_manage_project(action="save", ctx=ctx)
        assert result.startswith("ERROR")

    @pytest.mark.asyncio
    async def test_save_project_not_loaded_returns_error(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})
        result = await cb_manage_project(action="save", project_id="proj_missing", ctx=ctx)
        assert result.startswith("ERROR")


class TestListAction:
    @pytest.mark.asyncio
    async def test_list_empty_store_returns_no_projects_message(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})
        result = await cb_manage_project(action="list", ctx=ctx)
        assert "No projects found" in result

    @pytest.mark.asyncio
    async def test_list_shows_both_projects(self) -> None:
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        await cb_manage_project(action="create", project_id="proj_one", project_name="One", ctx=ctx)
        await cb_manage_project(action="create", project_id="proj_two", project_name="Two", ctx=ctx)
        result = await cb_manage_project(action="list", ctx=ctx)
        assert "proj_one" in result
        assert "proj_two" in result

    @pytest.mark.asyncio
    async def test_list_marks_active_projects(self) -> None:
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        await cb_manage_project(action="create", project_id="proj_active", project_name="Active", ctx=ctx)
        stage2 = CompositionStage(project_id="proj_inactive", project_name="Inactive")
        save_stage_to_db(store, stage2)
        result = await cb_manage_project(action="list", ctx=ctx)
        assert "(active)" in result
        lines = result.splitlines()
        active_line = next((l for l in lines if "proj_active" in l), "")
        inactive_line = next((l for l in lines if "proj_inactive" in l), "")
        assert "(active)" in active_line
        assert "(active)" not in inactive_line


class TestInvalidAction:
    @pytest.mark.asyncio
    async def test_invalid_action_returns_error(self) -> None:
        store = SQLiteStore(":memory:")
        ctx = _make_ctx(store=store, active_stages={})
        result = await cb_manage_project(action="delete_all", ctx=ctx)
        assert result.startswith("ERROR")
        assert "create" in result
        assert "load" in result
        assert "save" in result
        assert "list" in result


class TestSaveLoadRoundTrip:
    @pytest.mark.asyncio
    async def test_assertion_survives_save_and_load(self) -> None:
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        await cb_manage_project(
            action="create", project_id="proj_roundtrip", project_name="Round Trip", ctx=ctx,
        )
        stage = active_stages["proj_roundtrip"]
        ast = Assertion(
            topic_path="/roundtrip/claim",
            content="PostgreSQL is the chosen engine",
            arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        stage.record_event(
            EventType.ASSERTION_CREATED, AssertionAuthor.AI, ast.id,
            {"topic_path": ast.topic_path},
        )
        result = await cb_manage_project(action="save", project_id="proj_roundtrip", ctx=ctx)
        assert "ERROR" not in result
        fresh_stages: dict = {}
        fresh_ctx = _MockCtx(store=store, active_stages=fresh_stages)
        load_result = await cb_manage_project(
            action="load", project_id="proj_roundtrip", ctx=fresh_ctx,
        )
        assert "ERROR" not in load_result
        loaded_stage = fresh_stages["proj_roundtrip"]
        assert ast.id in loaded_stage.assertions
        reloaded = loaded_stage.assertions[ast.id]
        assert reloaded.content == "PostgreSQL is the chosen engine"
        assert reloaded.topic_path == "/roundtrip/claim"
        assert reloaded.active is True

    @pytest.mark.asyncio
    async def test_events_survive_save_and_load(self) -> None:
        store = SQLiteStore(":memory:")
        active_stages: dict = {}
        ctx = _MockCtx(store=store, active_stages=active_stages)
        await cb_manage_project(
            action="create", project_id="proj_events", project_name="Events Test", ctx=ctx,
        )
        stage = active_stages["proj_events"]
        initial = len(stage.events)
        await cb_manage_project(action="save", project_id="proj_events", ctx=ctx)
        fresh_stages: dict = {}
        fresh_ctx = _MockCtx(store=store, active_stages=fresh_stages)
        await cb_manage_project(action="load", project_id="proj_events", ctx=fresh_ctx)
        assert len(fresh_stages["proj_events"].events) >= initial
