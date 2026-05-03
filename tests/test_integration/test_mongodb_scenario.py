"""Integration test: the canonical Cognitive Bridge MongoDB scenario.

Blueprint reference: Appendix A. CLAUDE.md Phase 4 / P4.T2.
Constitution rules C3 (steelman gate), C5 (alternatives + effects), C7 (cascade),
C8 (event-log audit), G4 (behavioral assertions).

Full Assert -> Detect -> Steelman -> Challenge -> Resolve -> Cascade -> Decide flow.
"""

import pytest

from cognitive_bridge.models import (
    AssumptionStatus, CompositionArc, ConflictDetectionLayer,
    ConflictStatus, EventType,
)
from cognitive_bridge.models.stage import CompositionStage
from cognitive_bridge.server import save_stage_to_db
from cognitive_bridge.storage.sqlite_store import SQLiteStore
from cognitive_bridge.tools.assertion_tool import cb_manage_assertion
from cognitive_bridge.tools.conflict_tool import cb_manage_conflict
from cognitive_bridge.tools.decision_tool import cb_decide


class _MockCtx:
    def __init__(self, store: SQLiteStore, active_stages: dict) -> None:
        self.lifespan_context = {"store": store, "active_stages": active_stages}


def _make_ctx_with_stage(project_id: str = "proj_test") -> tuple[_MockCtx, CompositionStage, SQLiteStore]:
    store = SQLiteStore(":memory:")
    stage = CompositionStage(project_id=project_id, project_name="Test Project")
    active_stages: dict = {project_id: stage}
    save_stage_to_db(store, stage)
    return _MockCtx(store=store, active_stages=active_stages), stage, store


def _event_count(stage: CompositionStage, event_type: EventType) -> int:
    return sum(1 for e in stage.events if e.event_type == event_type)


DB_PATH = "/architecture/database/engine"
ORM_PATH = "/architecture/orm/choice"


class TestMongoDBScenario:
    @pytest.mark.asyncio
    async def test_step01_create_project(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        assert stage.project_id == "mongodb_choice"
        assert len(stage.assertions) == 0

    @pytest.mark.asyncio
    async def test_step02_assert_mongodb(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        result = await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="MongoDB is the right choice for this project",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        assert "ASSERT" in result
        assert _event_count(stage, EventType.ASSERTION_CREATED) == 1

    @pytest.mark.asyncio
    async def test_step03_structural_conflict_detected(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="MongoDB is the right choice for this project",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        result = await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="PostgreSQL is the right choice for this project",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        assert "STRUCTURAL CONFLICT" in result
        assert _event_count(stage, EventType.CONFLICT_DETECTED) >= 1

    @pytest.mark.asyncio
    async def test_step03_conflict_has_structural_layer(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="MongoDB is the right choice for this project",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="PostgreSQL is the right choice for this project",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        assert len(stage.conflicts) >= 1
        conflict = next(iter(stage.conflicts.values()))
        assert conflict.detection_layer == ConflictDetectionLayer.STRUCTURAL

    @pytest.mark.asyncio
    async def test_step04_challenge_without_steelman_rejected(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="MongoDB is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        conflict_id = next(iter(stage.conflicts.keys()))
        result = await cb_manage_conflict(action="challenge", conflict_id=conflict_id, ctx=ctx)
        assert "ERROR" in result
        assert "steelman" in result.lower()

    @pytest.mark.asyncio
    async def test_step05_challenge_with_steelman_succeeds(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="MongoDB is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        conflict_id = next(iter(stage.conflicts.keys()))
        result = await cb_manage_conflict(
            action="challenge", conflict_id=conflict_id,
            steelman_summary="MongoDB offers flexible schema design that reduces migration overhead for rapidly evolving domains.",
            ctx=ctx,
        )
        assert "ERROR" not in result
        assert "Challenge registered" in result or "challenge" in result.lower()

    @pytest.mark.asyncio
    async def test_step05_challenge_records_conflict_resolved_event(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="MongoDB is right",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is right",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        conflict_id = next(iter(stage.conflicts.keys()))
        await cb_manage_conflict(
            action="challenge", conflict_id=conflict_id,
            steelman_summary="MongoDB's flexible schema reduces migration overhead.",
            ctx=ctx,
        )
        assert _event_count(stage, EventType.CONFLICT_RESOLVED) >= 1

    @pytest.mark.asyncio
    async def test_step05_challenge_conflict_remains_active(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="MongoDB is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        conflict_id = next(iter(stage.conflicts.keys()))
        await cb_manage_conflict(
            action="challenge", conflict_id=conflict_id,
            steelman_summary="MongoDB's flexible schema is a strong argument for evolving domains.",
            ctx=ctx,
        )
        assert stage.conflicts[conflict_id].status == ConflictStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_step06_dependent_assertion_created(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        result = await cb_manage_assertion(
            action="assert", topic_path=ORM_PATH, content="SQLAlchemy is the chosen ORM",
            arc=CompositionArc.INHERITS.value, depends_on_paths=DB_PATH, ctx=ctx,
        )
        assert "ASSERT" in result
        orm_ast = next(a for a in stage.assertions.values() if a.topic_path == ORM_PATH)
        assert DB_PATH in orm_ast.depends_on_paths

    @pytest.mark.asyncio
    async def test_step07_promote_postgresql_to_local(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="MongoDB is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        pg_ast = next(a for a in stage.assertions.values() if "PostgreSQL" in a.content)
        result = await cb_manage_assertion(
            action="promote", topic_path=DB_PATH, assertion_id=pg_ast.id,
            arc=CompositionArc.LOCAL.value,
            evidence="pg_version() confirmed PostgreSQL 15.2",
            falsifiable_if="If pg_version() returns a non-PostgreSQL string",
            ctx=ctx,
        )
        assert "PROMOTE" in result
        assert _event_count(stage, EventType.ASSERTION_PROMOTED) >= 1

    @pytest.mark.asyncio
    async def test_step08_cascading_conflict_for_orm_assertion(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="MongoDB is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=ORM_PATH, content="SQLAlchemy is the chosen ORM",
            arc=CompositionArc.INHERITS.value, depends_on_paths=DB_PATH, ctx=ctx,
        )
        pg_ast = next(
            a for a in stage.assertions.values()
            if "PostgreSQL" in a.content and a.topic_path == DB_PATH
        )
        await cb_manage_assertion(
            action="promote", topic_path=DB_PATH, assertion_id=pg_ast.id,
            arc=CompositionArc.LOCAL.value, evidence="pg_version() confirmed",
            falsifiable_if="If pg_version() returns a non-PostgreSQL string", ctx=ctx,
        )
        cascading = [
            c for c in stage.conflicts.values()
            if c.detection_layer == ConflictDetectionLayer.CASCADING
        ]
        assert len(cascading) >= 1, "Expected at least one CASCADING conflict"

    @pytest.mark.asyncio
    async def test_step09_orm_assertion_assumption_status_challenged(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="MongoDB is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=ORM_PATH, content="SQLAlchemy is the chosen ORM",
            arc=CompositionArc.INHERITS.value, depends_on_paths=DB_PATH, ctx=ctx,
        )
        pg_ast = next(
            a for a in stage.assertions.values()
            if "PostgreSQL" in a.content and a.topic_path == DB_PATH
        )
        await cb_manage_assertion(
            action="promote", topic_path=DB_PATH, assertion_id=pg_ast.id,
            arc=CompositionArc.LOCAL.value, evidence="confirmed",
            falsifiable_if="If pg_version() returns a non-PostgreSQL string", ctx=ctx,
        )
        orm_ast = next(a for a in stage.assertions.values() if a.topic_path == ORM_PATH)
        assert orm_ast.assumption_status == AssumptionStatus.CHALLENGED
        assert _event_count(stage, EventType.ASSERTION_CHALLENGED) >= 1

    @pytest.mark.asyncio
    async def test_step10_decision_recorded(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        result = await cb_decide(
            topic_path=DB_PATH,
            decision="Use PostgreSQL as the primary database engine",
            rationale="PostgreSQL provides ACID guarantees required by transactional workloads.",
            alternatives_rejected=(
                "MongoDB — rejected because no ACID transaction support across collections | "
                "MySQL — rejected because limited JSON support | "
                "Redis — rejected because no durable persistent primary store semantics"
            ),
            second_order_effects=(
                "ORM migration required: all models must use SQLAlchemy with PG dialect | "
                "Schema redesign required: migrate from document model to relational"
            ),
            reversibility="costly", ctx=ctx,
        )
        assert "DECISION RECORDED" in result
        assert len(stage.decisions) == 1
        dec = stage.decisions[0]
        assert "MongoDB" in dec.alternatives_rejected[0]
        assert _event_count(stage, EventType.DECISION_RECORDED) >= 1

    @pytest.mark.asyncio
    async def test_step10_decision_creates_inherits_constraint_assertions(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is the right choice",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        pre_count = len(stage.assertions)
        await cb_decide(
            topic_path=DB_PATH, decision="Use PostgreSQL",
            rationale="ACID guarantees needed",
            alternatives_rejected="MongoDB — no ACID | Redis — no persistence",
            second_order_effects="ORM migration required | Schema redesign required",
            ctx=ctx,
        )
        assert len(stage.assertions) - pre_count == 2

    @pytest.mark.asyncio
    async def test_full_scenario_state(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("mongodb_choice")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="MongoDB is the right choice for this project",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="PostgreSQL is the right choice for this project",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        conflict_id = next(iter(stage.conflicts.keys()))
        await cb_manage_conflict(
            action="challenge", conflict_id=conflict_id,
            steelman_summary="MongoDB's flexible schema significantly reduces migration overhead.",
            ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=ORM_PATH,
            content="SQLAlchemy is the chosen ORM, depends on DB engine choice",
            arc=CompositionArc.INHERITS.value, depends_on_paths=DB_PATH, ctx=ctx,
        )
        pg_ast = next(
            a for a in stage.assertions.values()
            if "PostgreSQL" in a.content and a.topic_path == DB_PATH
        )
        await cb_manage_assertion(
            action="promote", topic_path=DB_PATH, assertion_id=pg_ast.id,
            arc=CompositionArc.LOCAL.value,
            evidence="pg_version() returned PostgreSQL 15.2",
            falsifiable_if="If pg_version() returns a non-PostgreSQL string", ctx=ctx,
        )
        await cb_decide(
            topic_path=DB_PATH,
            decision="Use PostgreSQL as the primary database engine",
            rationale="ACID guarantees required by transactional workloads",
            alternatives_rejected=(
                "MongoDB — rejected because no ACID transaction support | "
                "MySQL — rejected because limited JSON support"
            ),
            second_order_effects=(
                "ORM migration: all models must use SQLAlchemy PG dialect | "
                "Schema redesign: migrate from document model to relational"
            ),
            reversibility="costly", ctx=ctx,
        )
        assert len(stage.assertions) >= 3
        assert len(stage.conflicts) >= 2
        assert len(stage.decisions) == 1
        assert len(stage.events) >= 10
        event_types = {e.event_type for e in stage.events}
        assert EventType.ASSERTION_CREATED in event_types
        assert EventType.CONFLICT_DETECTED in event_types
        assert EventType.CONFLICT_RESOLVED in event_types
        assert EventType.ASSERTION_PROMOTED in event_types
        assert EventType.ASSERTION_CHALLENGED in event_types
        assert EventType.DECISION_RECORDED in event_types
        assert _event_count(stage, EventType.ASSERTION_CREATED) >= 3
        assert _event_count(stage, EventType.CONFLICT_DETECTED) >= 2
        structural = [
            c for c in stage.conflicts.values()
            if c.detection_layer == ConflictDetectionLayer.STRUCTURAL
        ]
        cascading = [
            c for c in stage.conflicts.values()
            if c.detection_layer == ConflictDetectionLayer.CASCADING
        ]
        assert len(structural) >= 1
        assert len(cascading) >= 1
        orm_assertions = [a for a in stage.assertions.values() if a.topic_path == ORM_PATH]
        assert len(orm_assertions) >= 1
        assert orm_assertions[0].assumption_status == AssumptionStatus.CHALLENGED
        dec = stage.decisions[0]
        assert dec.topic_path == DB_PATH
        assert len(dec.alternatives_rejected) >= 1
        assert any("MongoDB" in alt for alt in dec.alternatives_rejected)
        assert len(dec.second_order_effects) >= 1


class TestGates:
    @pytest.mark.asyncio
    async def test_falsifiability_gate_local_without_falsifiable_if(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("proj_gate")
        result = await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="PostgreSQL version is 15",
            arc=CompositionArc.LOCAL.value, evidence="observed", ctx=ctx,
        )
        assert "ERROR" in result
        assert len(stage.assertions) == 0

    @pytest.mark.asyncio
    async def test_falsifiability_gate_local_with_falsifiable_if(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("proj_gate2")
        result = await cb_manage_assertion(
            action="assert", topic_path=DB_PATH,
            content="PostgreSQL version is 15",
            arc=CompositionArc.LOCAL.value,
            evidence="SELECT version() confirmed 15",
            falsifiable_if="If SELECT version() returns a non-PG15 string", ctx=ctx,
        )
        assert "ASSERT" in result
        assert len(stage.assertions) == 1

    @pytest.mark.asyncio
    async def test_steelman_gate_challenge_without_summary(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("proj_steelman")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="MongoDB is right",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL is right",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        conflict_id = next(iter(stage.conflicts.keys()))
        result = await cb_manage_conflict(action="challenge", conflict_id=conflict_id, ctx=ctx)
        assert "ERROR" in result
        assert "steelman" in result.lower()

    @pytest.mark.asyncio
    async def test_decision_rigor_gate_no_alternatives(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("proj_decide_gate")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        result = await cb_decide(
            topic_path=DB_PATH, decision="Use PostgreSQL", rationale="It is good",
            alternatives_rejected="",
            second_order_effects="Schema migrations required", ctx=ctx,
        )
        assert "ERROR" in result
        assert len(stage.decisions) == 0

    @pytest.mark.asyncio
    async def test_decision_rigor_gate_no_second_order_effects(self) -> None:
        ctx, stage, store = _make_ctx_with_stage("proj_decide_gate2")
        await cb_manage_assertion(
            action="assert", topic_path=DB_PATH, content="PostgreSQL",
            arc=CompositionArc.INHERITS.value, ctx=ctx,
        )
        result = await cb_decide(
            topic_path=DB_PATH, decision="Use PostgreSQL", rationale="It is good",
            alternatives_rejected="MongoDB — no ACID",
            second_order_effects="", ctx=ctx,
        )
        assert "ERROR" in result
        assert len(stage.decisions) == 0
