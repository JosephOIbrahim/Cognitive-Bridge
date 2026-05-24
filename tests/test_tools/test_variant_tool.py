"""Integration tests for the cb_manage_variant tool.

Blueprint reference: Section 6.1 (cb_manage_variant tool), Section 3.5 (VariantSet).
Constitution rules C8 (event-log audit), G2 (validator-rejection symmetry).
"""

import pytest

from cognitive_bridge.models import (
    AssertionAuthor, CompositionStage, EventType, Variant, VariantSet,
)
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.variant_tool import cb_manage_variant


class _MockCtx:
    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx(store: SQLiteStore | None = None, active_stages: dict | None = None) -> _MockCtx:
    return _MockCtx(
        store=store or SQLiteStore(":memory:"),
        active_stages=active_stages if active_stages is not None else {},
    )


def _make_ctx_with_stage(project_id: str = "proj_variant_test") -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Variant Test Project")
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    return _make_ctx(store=store, active_stages=active_stages), stage, store


def _make_variant_set_on_stage(
    stage: CompositionStage, store: SQLiteStore,
    topic_path: str = "/architecture/database",
    name: str = "DB Engine Choice",
    variant_names: list[str] | None = None,
) -> VariantSet:
    if variant_names is None:
        variant_names = ["PostgreSQL", "MongoDB"]
    variants = [Variant(name=n, content=f"Use {n} as database engine") for n in variant_names]
    vs = VariantSet(name=name, topic_path=topic_path, variants=variants)
    stage.variant_sets[vs.id] = vs
    save_stage_to_db(store, stage)
    return vs


class TestCreateAction:
    @pytest.mark.asyncio
    async def test_create_happy_path_appends_to_stage(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Engine Choice",
            variant_names="PostgreSQL,MongoDB",
            variant_contents="Use PostgreSQL as DB,Use MongoDB as DB", ctx=ctx,
        )
        assert "ERROR" not in result
        assert len(stage.variant_sets) == 1

    @pytest.mark.asyncio
    async def test_create_fires_variant_set_created_event(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        initial = len(stage.events)
        await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Engine Choice",
            variant_names="PostgreSQL,MongoDB",
            variant_contents="Use PostgreSQL as DB,Use MongoDB as DB", ctx=ctx,
        )
        assert EventType.VARIANT_SET_CREATED in [e.event_type for e in stage.events]
        assert len(stage.events) > initial

    @pytest.mark.asyncio
    async def test_create_response_includes_variant_set_id(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Engine Choice",
            variant_names="PostgreSQL,MongoDB",
            variant_contents="Use PostgreSQL as DB,Use MongoDB as DB", ctx=ctx,
        )
        assert "var_" in result

    @pytest.mark.asyncio
    async def test_create_with_three_variants(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Engine Choice",
            variant_names="PostgreSQL,MongoDB,CockroachDB",
            variant_contents="Use PG,Use Mongo,Use Cockroach", ctx=ctx,
        )
        assert "ERROR" not in result
        vs = next(iter(stage.variant_sets.values()))
        assert len(vs.variants) == 3

    @pytest.mark.asyncio
    async def test_create_with_one_variant_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Choice",
            variant_names="PostgreSQL", variant_contents="Use PostgreSQL", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "2" in result or "least" in result

    @pytest.mark.asyncio
    async def test_create_mismatched_names_and_contents_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Choice",
            variant_names="PostgreSQL,MongoDB", variant_contents="Use PostgreSQL", ctx=ctx,
        )
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_create_missing_topic_path_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="create", name="DB Choice", variant_names="PostgreSQL,MongoDB",
            variant_contents="Use PG,Use Mongo", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "topic_path" in result

    @pytest.mark.asyncio
    async def test_create_missing_name_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="create", topic_path="/architecture/database",
            variant_names="PostgreSQL,MongoDB", variant_contents="Use PG,Use Mongo", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "name" in result

    @pytest.mark.asyncio
    async def test_create_missing_variant_names_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Choice",
            variant_contents="Use PG,Use Mongo", ctx=ctx,
        )
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_create_no_event_when_validation_fails(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        initial = len(stage.events)
        await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Choice",
            variant_names="PostgreSQL", variant_contents="Use PostgreSQL", ctx=ctx,
        )
        assert EventType.VARIANT_SET_CREATED not in [e.event_type for e in stage.events]
        assert len(stage.events) == initial


class TestAddEvidenceAction:
    @pytest.mark.asyncio
    async def test_add_evidence_for_updates_variant(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="add_evidence", variant_set_id=vs.id, variant_name="PostgreSQL",
            evidence_for="Passed ACID compliance test", ctx=ctx,
        )
        assert "ERROR" not in result
        pg = next(v for v in stage.variant_sets[vs.id].variants if v.name == "PostgreSQL")
        assert "Passed ACID compliance test" in pg.evidence_for

    @pytest.mark.asyncio
    async def test_add_evidence_against_updates_variant(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="add_evidence", variant_set_id=vs.id, variant_name="MongoDB",
            evidence_against="No ACID guarantees for multi-document transactions", ctx=ctx,
        )
        assert "ERROR" not in result
        mongo = next(v for v in stage.variant_sets[vs.id].variants if v.name == "MongoDB")
        assert "No ACID guarantees for multi-document transactions" in mongo.evidence_against

    @pytest.mark.asyncio
    async def test_add_evidence_fires_variant_set_evidence_event(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        await cb_manage_variant(
            action="add_evidence", variant_set_id=vs.id, variant_name="PostgreSQL",
            evidence_for="Passed ACID test", ctx=ctx,
        )
        assert EventType.VARIANT_SET_EVIDENCE in [e.event_type for e in stage.events]

    @pytest.mark.asyncio
    async def test_add_both_for_and_against_simultaneously(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="add_evidence", variant_set_id=vs.id, variant_name="PostgreSQL",
            evidence_for="ACID compliant", evidence_against="Higher operational cost", ctx=ctx,
        )
        assert "ERROR" not in result
        pg = next(v for v in stage.variant_sets[vs.id].variants if v.name == "PostgreSQL")
        assert len(pg.evidence_for) == 1
        assert len(pg.evidence_against) == 1

    @pytest.mark.asyncio
    async def test_add_evidence_without_variant_set_id_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="add_evidence", variant_name="PostgreSQL",
            evidence_for="ACID compliant", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "variant_set_id" in result

    @pytest.mark.asyncio
    async def test_add_evidence_without_variant_name_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="add_evidence", variant_set_id=vs.id,
            evidence_for="ACID compliant", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "variant_name" in result

    @pytest.mark.asyncio
    async def test_add_evidence_without_any_evidence_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="add_evidence", variant_set_id=vs.id, variant_name="PostgreSQL", ctx=ctx,
        )
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_add_evidence_nonexistent_variant_set_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="add_evidence", variant_set_id="var_doesnotexist",
            variant_name="PostgreSQL", evidence_for="ACID", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_add_evidence_nonexistent_variant_name_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="add_evidence", variant_set_id=vs.id, variant_name="CockroachDB",
            evidence_for="Distributed ACID", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "CockroachDB" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_add_evidence_to_resolved_set_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        vs.resolved = True
        vs.resolved_variant_name = "PostgreSQL"
        save_stage_to_db(store, stage)
        result = await cb_manage_variant(
            action="add_evidence", variant_set_id=vs.id, variant_name="MongoDB",
            evidence_for="Flexible schema", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "resolved" in result.lower()


class TestResolveAction:
    @pytest.mark.asyncio
    async def test_resolve_happy_path_sets_resolved_flag(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="resolve", variant_set_id=vs.id, variant_name="PostgreSQL",
            resolution_evidence="ACID tests passed", ctx=ctx,
        )
        assert "ERROR" not in result
        resolved_vs = stage.variant_sets[vs.id]
        assert resolved_vs.resolved is True
        assert resolved_vs.resolved_variant_name == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_resolve_fires_variant_set_resolved_event(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        await cb_manage_variant(
            action="resolve", variant_set_id=vs.id, variant_name="PostgreSQL", ctx=ctx,
        )
        assert EventType.VARIANT_SET_RESOLVED in [e.event_type for e in stage.events]

    @pytest.mark.asyncio
    async def test_resolve_stores_resolution_evidence(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        await cb_manage_variant(
            action="resolve", variant_set_id=vs.id, variant_name="PostgreSQL",
            resolution_evidence="ACID tests passed decisively", ctx=ctx,
        )
        assert stage.variant_sets[vs.id].resolution_evidence == "ACID tests passed decisively"

    @pytest.mark.asyncio
    async def test_resolve_response_shows_winner(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="resolve", variant_set_id=vs.id, variant_name="MongoDB", ctx=ctx,
        )
        assert "MongoDB" in result
        assert "Winner" in result or "winner" in result.lower() or "resolved" in result.lower()

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_variant_set_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="resolve", variant_set_id="var_doesnotexist",
            variant_name="PostgreSQL", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_variant_name_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(
            action="resolve", variant_set_id=vs.id, variant_name="CockroachDB", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "PostgreSQL" in result or "MongoDB" in result

    @pytest.mark.asyncio
    async def test_resolve_already_resolved_set_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        await cb_manage_variant(
            action="resolve", variant_set_id=vs.id, variant_name="PostgreSQL", ctx=ctx,
        )
        result = await cb_manage_variant(
            action="resolve", variant_set_id=vs.id, variant_name="MongoDB", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "resolved" in result.lower()

    @pytest.mark.asyncio
    async def test_resolve_without_variant_set_id_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(
            action="resolve", variant_name="PostgreSQL", ctx=ctx,
        )
        assert result.startswith("ERROR:")
        assert "variant_set_id" in result

    @pytest.mark.asyncio
    async def test_resolve_without_variant_name_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        vs = _make_variant_set_on_stage(stage, store)
        result = await cb_manage_variant(action="resolve", variant_set_id=vs.id, ctx=ctx)
        assert result.startswith("ERROR:")
        assert "variant_name" in result


class TestUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self) -> None:
        ctx, stage, store = _make_ctx_with_stage()
        result = await cb_manage_variant(action="delete", ctx=ctx)
        assert result.startswith("ERROR:")
        assert "create" in result
        assert "add_evidence" in result
        assert "resolve" in result

    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        ctx = _make_ctx()
        result = await cb_manage_variant(
            action="create", topic_path="/architecture/database", name="DB Choice",
            variant_names="PostgreSQL,MongoDB", variant_contents="Use PG,Use Mongo", ctx=ctx,
        )
        assert result.startswith("ERROR:")
