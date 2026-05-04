"""Integration tests for export_stage_to_json / import_stage_from_json.

Blueprint reference: Section 7.1, CLAUDE.md Phase 4 / P4.T1.
Constitution rule C10 (project capsule round-trip).
"""

import json

import pytest
from pydantic import ValidationError

from cognitive_bridge.models import (
    Assertion, AssertionAuthor, CompositionArc, Conflict, ConflictDetectionLayer,
    Decision, EventType, Variant, VariantSet,
)
from cognitive_bridge.models.stage import CompositionStage
from cognitive_bridge.server import export_stage_to_json, import_stage_from_json


def _empty_stage(project_id: str = "proj_export") -> CompositionStage:
    return CompositionStage(project_id=project_id, project_name="Export Test")


def _build_populated_stage() -> CompositionStage:
    stage = CompositionStage(project_id="proj_populated", project_name="Populated")
    ast1 = Assertion(
        topic_path="/arch/database", content="PostgreSQL is the primary store",
        arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
        embedding=[0.1, 0.2, 0.3],
    )
    stage.assertions[ast1.id] = ast1
    ast2 = Assertion(
        topic_path="/arch/orm", content="SQLAlchemy ORM is used for DB access",
        arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
        depends_on_paths=["/arch/database"],
    )
    stage.assertions[ast2.id] = ast2
    ast3 = Assertion(
        topic_path="/arch/database", content="PostgreSQL version is 15",
        arc=CompositionArc.LOCAL, author=AssertionAuthor.AI,
        evidence=["SELECT version() confirmed 15.2"],
        falsifiable_if="If SELECT version() returns a non-PG15 string",
    )
    stage.assertions[ast3.id] = ast3
    cfl = Conflict(
        assertion_a_id=ast1.id, assertion_b_id=ast3.id,
        topic_path="/arch/database", detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )
    stage.conflicts[cfl.id] = cfl
    vs = VariantSet(
        name="DB Engine Choice", topic_path="/arch/database",
        variants=[
            Variant(name="postgres", content="Use PostgreSQL"),
            Variant(name="mysql", content="Use MySQL"),
        ],
        source_conflict_id=cfl.id,
    )
    stage.variant_sets[vs.id] = vs
    dec = Decision(
        topic_path="/arch/database", decision="Use PostgreSQL",
        rationale="ACID guarantees required",
        alternatives_rejected=["MongoDB — no ACID"],
        second_order_effects=["Schema migrations required"],
    )
    stage.decisions.append(dec)
    for i in range(5):
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, ast1.id, {"seq": i})
    return stage


class TestEmptyStageRoundTrip:
    def test_empty_stage_project_id_preserved(self) -> None:
        stage = _empty_stage("proj_empty_rt")
        restored = import_stage_from_json(export_stage_to_json(stage))
        assert restored.project_id == "proj_empty_rt"

    def test_empty_stage_project_name_preserved(self) -> None:
        stage = _empty_stage()
        stage.project_name = "Export Test Name"
        restored = import_stage_from_json(export_stage_to_json(stage))
        assert restored.project_name == "Export Test Name"

    def test_empty_stage_has_empty_assertions(self) -> None:
        restored = import_stage_from_json(export_stage_to_json(_empty_stage()))
        assert len(restored.assertions) == 0

    def test_empty_stage_has_empty_conflicts(self) -> None:
        restored = import_stage_from_json(export_stage_to_json(_empty_stage()))
        assert len(restored.conflicts) == 0

    def test_empty_stage_has_empty_events(self) -> None:
        restored = import_stage_from_json(export_stage_to_json(_empty_stage()))
        assert len(restored.events) == 0

    def test_empty_stage_has_empty_decisions(self) -> None:
        restored = import_stage_from_json(export_stage_to_json(_empty_stage()))
        assert len(restored.decisions) == 0

    def test_empty_stage_has_empty_variant_sets(self) -> None:
        restored = import_stage_from_json(export_stage_to_json(_empty_stage()))
        assert len(restored.variant_sets) == 0


class TestPopulatedStageRoundTrip:
    def test_assertion_count_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        assert len(restored.assertions) == len(stage.assertions)

    def test_conflict_count_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        assert len(restored.conflicts) == len(stage.conflicts)

    def test_variant_set_count_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        assert len(restored.variant_sets) == len(stage.variant_sets)

    def test_decision_count_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        assert len(restored.decisions) == len(stage.decisions)

    def test_event_count_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        assert len(restored.events) == len(stage.events)

    def test_assertion_content_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for ast_id, original in stage.assertions.items():
            assert ast_id in restored.assertions
            assert restored.assertions[ast_id].content == original.content

    def test_assertion_arc_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for ast_id, original in stage.assertions.items():
            assert restored.assertions[ast_id].arc == original.arc

    def test_assertion_topic_path_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for ast_id, original in stage.assertions.items():
            assert restored.assertions[ast_id].topic_path == original.topic_path

    def test_assertion_depends_on_paths_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for ast_id, original in stage.assertions.items():
            assert restored.assertions[ast_id].depends_on_paths == original.depends_on_paths

    def test_assertion_falsifiable_if_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for ast_id, original in stage.assertions.items():
            assert restored.assertions[ast_id].falsifiable_if == original.falsifiable_if

    def test_conflict_status_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for cfl_id, original in stage.conflicts.items():
            assert restored.conflicts[cfl_id].status == original.status

    def test_conflict_detection_layer_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for cfl_id, original in stage.conflicts.items():
            assert restored.conflicts[cfl_id].detection_layer == original.detection_layer

    def test_variant_set_variants_count_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for vs_id, original in stage.variant_sets.items():
            assert len(restored.variant_sets[vs_id].variants) == len(original.variants)

    def test_variant_set_name_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for vs_id, original in stage.variant_sets.items():
            assert restored.variant_sets[vs_id].name == original.name

    def test_decision_alternatives_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for original, restored_dec in zip(stage.decisions, restored.decisions):
            assert restored_dec.alternatives_rejected == original.alternatives_rejected

    def test_decision_second_order_effects_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        for original, restored_dec in zip(stage.decisions, restored.decisions):
            assert restored_dec.second_order_effects == original.second_order_effects

    def test_event_types_preserved(self) -> None:
        stage = _build_populated_stage()
        restored = import_stage_from_json(export_stage_to_json(stage))
        original_types = [e.event_type for e in stage.events]
        restored_types = [e.event_type for e in restored.events]
        assert original_types == restored_types


class TestEmbeddingPreservation:
    def test_embedding_preserved_after_round_trip(self) -> None:
        stage = _empty_stage("proj_embed")
        ast = Assertion(
            topic_path="/embed/test", content="Embedding test assertion",
            arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
            embedding=[0.1, 0.2, 0.3],
        )
        stage.assertions[ast.id] = ast
        restored = import_stage_from_json(export_stage_to_json(stage))
        restored_ast = restored.assertions[ast.id]
        assert restored_ast.embedding is not None
        assert len(restored_ast.embedding) == 3
        assert abs(restored_ast.embedding[0] - 0.1) < 1e-9
        assert abs(restored_ast.embedding[1] - 0.2) < 1e-9
        assert abs(restored_ast.embedding[2] - 0.3) < 1e-9

    def test_none_embedding_preserved_after_round_trip(self) -> None:
        stage = _empty_stage("proj_embed_none")
        ast = Assertion(
            topic_path="/embed/none", content="No embedding assertion",
            arc=CompositionArc.INHERITS, author=AssertionAuthor.AI,
        )
        stage.assertions[ast.id] = ast
        restored = import_stage_from_json(export_stage_to_json(stage))
        assert restored.assertions[ast.id].embedding is None


class TestVersionField:
    def test_version_field_is_3_0(self) -> None:
        capsule = json.loads(export_stage_to_json(_empty_stage()))
        assert capsule["version"] == "3.0"

    def test_version_field_preserved_after_import(self) -> None:
        capsule = json.loads(export_stage_to_json(_empty_stage("proj_version")))
        assert capsule.get("version") == "3.0"


class TestCycleIdentity:
    def test_cycle_produces_identical_structure(self) -> None:
        stage = _build_populated_stage()
        capsule1_json = export_stage_to_json(stage)
        restored = import_stage_from_json(capsule1_json)
        capsule2_json = export_stage_to_json(restored)
        capsule1 = json.loads(capsule1_json)
        capsule2 = json.loads(capsule2_json)
        for cap in (capsule1, capsule2):
            cap.pop("exported_at", None)
        assert capsule1 == capsule2


class TestImportErrorCases:
    def test_empty_json_object_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            import_stage_from_json("{}")

    def test_invalid_json_raises_json_decode_error(self) -> None:
        import json as _json
        with pytest.raises(_json.JSONDecodeError):
            import_stage_from_json("not json at all ][")

    def test_capsule_too_large_raises_value_error(self) -> None:
        oversized = "x" * (10 * 1024 * 1024 + 1)
        with pytest.raises(ValueError, match="too large"):
            import_stage_from_json(oversized)

    def test_invalid_pydantic_content_raises_validation_error(self) -> None:
        stage = _empty_stage("proj_corrupt")
        ast = Assertion(
            topic_path="/corrupt/test", content="This is a LOCAL assertion",
            arc=CompositionArc.LOCAL, author=AssertionAuthor.AI,
            evidence=["observed it"], falsifiable_if="If X happens",
        )
        stage.assertions[ast.id] = ast
        capsule = json.loads(export_stage_to_json(stage))
        capsule["assertions"][ast.id]["falsifiable_if"] = None
        with pytest.raises(ValidationError):
            import_stage_from_json(json.dumps(capsule))

    def test_partially_valid_capsule_missing_project_id_raises_key_error(self) -> None:
        partial = json.dumps({
            "version": "3.0", "project_name": "Partial",
            "assertions": {}, "conflicts": {}, "variant_sets": {},
            "events": [], "decisions": [], "parameters": {}, "exchange_count": 0,
        })
        with pytest.raises(KeyError):
            import_stage_from_json(partial)
