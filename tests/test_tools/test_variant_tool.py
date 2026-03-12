"""Integration tests for cb_manage_variant tool.

Each test is independent — no shared mutable state. Every test builds its own
in-memory SQLiteStore and isolated active_stages dict via the mock context helper.
"""

import pytest

from cognitive_bridge.models import (
    CompositionStage,
    EventType,
    Variant,
    VariantSet,
)
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.variant_tool import cb_manage_variant


# ═══════════════════════════════════════════════════════════════
# Mock Context
# ═══════════════════════════════════════════════════════════════


class _MockLifespanContext:
    """Minimal context wrapper exposing lifespan_context for tool handlers."""

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
    if store is None:
        store = SQLiteStore(":memory:")
    if active_stages is None:
        active_stages = {}
    return _MockLifespanContext(store=store, active_stages=active_stages)


def _make_active_project(
    project_id: str = "test_project",
    store: SQLiteStore | None = None,
) -> tuple[SQLiteStore, dict, _MockLifespanContext]:
    """Create a store, stage, and context with one active project ready to use."""
    if store is None:
        store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Test Project")
    save_stage_to_db(store, stage)
    active_stages = {project_id: stage}
    ctx = _make_ctx(store=store, active_stages=active_stages)
    return store, active_stages, ctx


# ═══════════════════════════════════════════════════════════════
# action: create
# ═══════════════════════════════════════════════════════════════


class TestCreateVariantSet:
    """Tests for action='create'."""

    @pytest.mark.asyncio
    async def test_create_valid_two_variants(self) -> None:
        """Creating a variant set with 2 variants succeeds and returns the set id."""
        store, active_stages, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/architecture/database",
            name="Database Engine Choice",
            variant_names="PostgreSQL, MongoDB",
            variant_contents="Relational ACID store, Document store",
        )
        assert "ERROR" not in result
        # ID should appear in result
        stage = active_stages["test_project"]
        assert len(stage.variant_sets) == 1
        vs_id = next(iter(stage.variant_sets))
        assert vs_id in result

    @pytest.mark.asyncio
    async def test_create_response_contains_variant_names(self) -> None:
        """The response lists all variant names."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/cache",
            name="Cache Strategy",
            variant_names="Redis, Memcached, Local",
            variant_contents="In-process Redis, Memcached cluster, In-process map",
        )
        assert "Redis" in result
        assert "Memcached" in result
        assert "Local" in result

    @pytest.mark.asyncio
    async def test_create_records_event(self) -> None:
        """Creating a variant set appends a VARIANT_SET_CREATED event."""
        store, active_stages, ctx = _make_active_project()
        await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="A, B",
            variant_contents="Option A desc, Option B desc",
        )
        stage = active_stages["test_project"]
        event_types = [e.event_type for e in stage.events]
        assert EventType.VARIANT_SET_CREATED in event_types

    @pytest.mark.asyncio
    async def test_create_with_source_conflict_id(self) -> None:
        """source_conflict_id is stored on the variant set."""
        store, active_stages, ctx = _make_active_project()
        await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="A, B",
            variant_contents="Desc A, Desc B",
            source_conflict_id="cfl_abc123",
        )
        stage = active_stages["test_project"]
        vs = next(iter(stage.variant_sets.values()))
        assert vs.source_conflict_id == "cfl_abc123"

    @pytest.mark.asyncio
    async def test_create_with_one_variant_returns_error(self) -> None:
        """Providing only one variant name returns an error about minimum 2."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="OnlyOne",
            variant_contents="Solo description",
        )
        assert "ERROR" in result
        assert "2" in result

    @pytest.mark.asyncio
    async def test_create_mismatched_counts_returns_error(self) -> None:
        """Providing 3 names but 2 contents returns a count mismatch error."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="A, B, C",
            variant_contents="Desc A, Desc B",
        )
        assert "ERROR" in result
        assert "3" in result
        assert "2" in result

    @pytest.mark.asyncio
    async def test_create_without_name_returns_error(self) -> None:
        """Omitting name returns an error referencing 'name'."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            variant_names="A, B",
            variant_contents="Desc A, Desc B",
        )
        assert "ERROR" in result
        assert "name" in result.lower()

    @pytest.mark.asyncio
    async def test_create_without_topic_path_returns_error(self) -> None:
        """Omitting topic_path returns an error referencing 'topic_path'."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            name="DB Choice",
            variant_names="A, B",
            variant_contents="Desc A, Desc B",
        )
        assert "ERROR" in result
        assert "topic_path" in result


# ═══════════════════════════════════════════════════════════════
# action: add_evidence
# ═══════════════════════════════════════════════════════════════


class TestAddEvidence:
    """Tests for action='add_evidence'."""

    async def _create_vs(
        self, ctx: _MockLifespanContext, active_stages: dict
    ) -> str:
        """Helper: create a 2-variant set and return its id."""
        await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="PostgreSQL, MongoDB",
            variant_contents="Relational store, Document store",
        )
        stage = active_stages["test_project"]
        return next(iter(stage.variant_sets))

    @pytest.mark.asyncio
    async def test_add_evidence_for(self) -> None:
        """Adding evidence_for grows the evidence_for list on the variant."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        result = await cb_manage_variant(
            action="add_evidence",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
            evidence_for="Supports ACID transactions natively",
        )
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        vs = stage.variant_sets[vs_id]
        pg = next(v for v in vs.variants if v.name == "PostgreSQL")
        assert len(pg.evidence_for) == 1
        assert "ACID" in pg.evidence_for[0]

    @pytest.mark.asyncio
    async def test_add_evidence_against(self) -> None:
        """Adding evidence_against grows the evidence_against list on the variant."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        result = await cb_manage_variant(
            action="add_evidence",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="MongoDB",
            evidence_against="Eventual consistency model is incompatible with billing",
        )
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        vs = stage.variant_sets[vs_id]
        mongo = next(v for v in vs.variants if v.name == "MongoDB")
        assert len(mongo.evidence_against) == 1

    @pytest.mark.asyncio
    async def test_add_evidence_both_for_and_against(self) -> None:
        """Supplying both evidence_for and evidence_against in one call appends both."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        await cb_manage_variant(
            action="add_evidence",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
            evidence_for="Team has deep PostgreSQL expertise",
            evidence_against="Schema migrations are costly at current scale",
        )
        stage = active_stages["test_project"]
        vs = stage.variant_sets[vs_id]
        pg = next(v for v in vs.variants if v.name == "PostgreSQL")
        assert len(pg.evidence_for) == 1
        assert len(pg.evidence_against) == 1

    @pytest.mark.asyncio
    async def test_add_evidence_records_event(self) -> None:
        """add_evidence appends a VARIANT_SET_EVIDENCE event."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        await cb_manage_variant(
            action="add_evidence",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
            evidence_for="Good fit for relational data",
        )
        stage = active_stages["test_project"]
        event_types = [e.event_type for e in stage.events]
        assert EventType.VARIANT_SET_EVIDENCE in event_types

    @pytest.mark.asyncio
    async def test_add_evidence_no_evidence_returns_error(self) -> None:
        """Calling add_evidence without either evidence_for or evidence_against errors."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        result = await cb_manage_variant(
            action="add_evidence",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
        )
        assert "ERROR" in result
        assert "evidence" in result.lower()

    @pytest.mark.asyncio
    async def test_add_evidence_nonexistent_variant_set(self) -> None:
        """Referencing a non-existent variant_set_id returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="add_evidence",
            ctx=ctx,
            variant_set_id="var_doesnotexist",
            variant_name="X",
            evidence_for="Something",
        )
        assert "ERROR" in result
        assert "var_doesnotexist" in result

    @pytest.mark.asyncio
    async def test_add_evidence_nonexistent_variant_name(self) -> None:
        """Referencing a variant name that does not exist in the set errors and lists available."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        result = await cb_manage_variant(
            action="add_evidence",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="Oracle",
            evidence_for="Enterprise licensing",
        )
        assert "ERROR" in result
        assert "Oracle" in result
        # Should list the available names
        assert "PostgreSQL" in result or "MongoDB" in result

    @pytest.mark.asyncio
    async def test_add_evidence_to_resolved_set_returns_error(self) -> None:
        """Adding evidence to an already-resolved variant set returns an error."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        # Resolve the set first
        await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
        )

        result = await cb_manage_variant(
            action="add_evidence",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
            evidence_for="Still want to add more",
        )
        assert "ERROR" in result
        assert "resolved" in result.lower()


# ═══════════════════════════════════════════════════════════════
# action: resolve
# ═══════════════════════════════════════════════════════════════


class TestResolveVariantSet:
    """Tests for action='resolve'."""

    async def _create_vs(
        self, ctx: _MockLifespanContext, active_stages: dict
    ) -> str:
        """Helper: create a 2-variant set and return its id."""
        await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="PostgreSQL, MongoDB",
            variant_contents="Relational store, Document store",
        )
        stage = active_stages["test_project"]
        return next(iter(stage.variant_sets))

    @pytest.mark.asyncio
    async def test_resolve_valid(self) -> None:
        """Resolving a variant set marks it resolved and sets the winner."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        result = await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
            resolution_evidence="Team expertise and transactional requirements",
        )
        assert "ERROR" not in result
        assert "PostgreSQL" in result
        stage = active_stages["test_project"]
        vs = stage.variant_sets[vs_id]
        assert vs.resolved is True
        assert vs.resolved_variant_name == "PostgreSQL"
        assert vs.resolved_at is not None

    @pytest.mark.asyncio
    async def test_resolve_stores_resolution_evidence(self) -> None:
        """resolution_evidence provided at resolve time is persisted on the variant set."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="MongoDB",
            resolution_evidence="Schema flexibility required by product roadmap",
        )
        stage = active_stages["test_project"]
        vs = stage.variant_sets[vs_id]
        assert vs.resolution_evidence == "Schema flexibility required by product roadmap"

    @pytest.mark.asyncio
    async def test_resolve_records_event(self) -> None:
        """Resolving a variant set appends a VARIANT_SET_RESOLVED event."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
        )
        stage = active_stages["test_project"]
        event_types = [e.event_type for e in stage.events]
        assert EventType.VARIANT_SET_RESOLVED in event_types

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_set_returns_error(self) -> None:
        """Resolving a non-existent variant_set_id returns an error."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id="var_ghost",
            variant_name="X",
        )
        assert "ERROR" in result
        assert "var_ghost" in result

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_variant_name_returns_error(self) -> None:
        """Resolving with a variant name not in the set errors and lists available."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        result = await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="SQLite",
        )
        assert "ERROR" in result
        assert "SQLite" in result
        assert "PostgreSQL" in result or "MongoDB" in result

    @pytest.mark.asyncio
    async def test_resolve_already_resolved_returns_error(self) -> None:
        """Attempting to resolve an already-resolved variant set returns an error."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
        )
        result = await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="MongoDB",
        )
        assert "ERROR" in result
        assert "resolved" in result.lower()

    @pytest.mark.asyncio
    async def test_resolve_without_evidence_still_succeeds(self) -> None:
        """resolution_evidence is optional — omitting it does not cause an error."""
        store, active_stages, ctx = _make_active_project()
        vs_id = await self._create_vs(ctx, active_stages)

        result = await cb_manage_variant(
            action="resolve",
            ctx=ctx,
            variant_set_id=vs_id,
            variant_name="PostgreSQL",
        )
        assert "ERROR" not in result
        stage = active_stages["test_project"]
        vs = stage.variant_sets[vs_id]
        assert vs.resolved is True
        assert vs.resolution_evidence is None


# ═══════════════════════════════════════════════════════════════
# Edge Cases: no active project, unknown action
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for cross-cutting error paths."""

    @pytest.mark.asyncio
    async def test_no_active_project_returns_error(self) -> None:
        """All actions return an error when no project is active."""
        ctx = _make_ctx()  # empty active_stages
        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="A, B",
            variant_contents="Desc A, Desc B",
        )
        assert "ERROR" in result
        assert "No active project" in result

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self) -> None:
        """An unrecognized action string returns an error listing valid actions."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="delete",
            ctx=ctx,
        )
        assert "ERROR" in result
        assert "delete" in result

    @pytest.mark.asyncio
    async def test_unknown_action_lists_valid_actions(self) -> None:
        """The error message for an unknown action names all valid actions."""
        _, _, ctx = _make_active_project()
        result = await cb_manage_variant(
            action="bogus",
            ctx=ctx,
        )
        assert "create" in result
        assert "add_evidence" in result
        assert "resolve" in result

    @pytest.mark.asyncio
    async def test_explicit_project_id_selects_correct_stage(self) -> None:
        """When multiple projects are active, project_id selects the right stage."""
        store = SQLiteStore(":memory:")
        stage_a = CompositionStage(project_id="proj_a", project_name="Project A")
        stage_b = CompositionStage(project_id="proj_b", project_name="Project B")
        save_stage_to_db(store, stage_a)
        save_stage_to_db(store, stage_b)
        active_stages = {"proj_a": stage_a, "proj_b": stage_b}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="A, B",
            variant_contents="Desc A, Desc B",
            project_id="proj_a",
        )
        assert "ERROR" not in result
        # Only proj_a should have a variant set
        assert len(stage_a.variant_sets) == 1
        assert len(stage_b.variant_sets) == 0

    @pytest.mark.asyncio
    async def test_multiple_active_stages_no_project_id_returns_error(self) -> None:
        """When multiple projects are active and project_id is omitted, an error is returned."""
        store = SQLiteStore(":memory:")
        stage_a = CompositionStage(project_id="proj_a", project_name="Project A")
        stage_b = CompositionStage(project_id="proj_b", project_name="Project B")
        save_stage_to_db(store, stage_a)
        save_stage_to_db(store, stage_b)
        active_stages = {"proj_a": stage_a, "proj_b": stage_b}
        ctx = _make_ctx(store=store, active_stages=active_stages)

        result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/db",
            name="DB Choice",
            variant_names="A, B",
            variant_contents="Desc A, Desc B",
        )
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_persistence_round_trip_for_variant_set(self) -> None:
        """A variant set created via the tool survives a save/load round-trip."""
        from cognitive_bridge.server import load_stage_from_db

        store, active_stages, ctx = _make_active_project(store=SQLiteStore(":memory:"))
        vs_id_result = await cb_manage_variant(
            action="create",
            ctx=ctx,
            topic_path="/arch/queue",
            name="Queue Choice",
            variant_names="Kafka, RabbitMQ",
            variant_contents="Distributed log, Message broker",
        )
        assert "ERROR" not in vs_id_result

        # Reload and verify the variant set is present
        recovered = load_stage_from_db(store, "test_project")
        assert len(recovered.variant_sets) == 1
        vs = next(iter(recovered.variant_sets.values()))
        assert vs.name == "Queue Choice"
        assert len(vs.variants) == 2
        names = {v.name for v in vs.variants}
        assert names == {"Kafka", "RabbitMQ"}
