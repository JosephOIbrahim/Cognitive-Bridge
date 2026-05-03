"""Tests for storage/converters.py — Pydantic ↔ SQLModel round-trip identity.

Satisfies CLAUDE.md requirement:
  "Round-trip identity — for every converter pair, assert
   pydantic_obj == row_to_pydantic(pydantic_to_row(pydantic_obj))
   field-by-field. Verify NO field is lost."

Blueprint reference: Section 7.1 (SQLite schema) and Sections 3.3–3.9 (model specs).

All tests are deterministic: no random, no sleeps, no network calls.
Every converter pair has a fully-populated round-trip test (all fields at
non-default values) plus targeted edge-case tests for JSON-encoded fields.
"""

from datetime import datetime, timezone

import pytest

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
    EventType,
    EvidenceType,
    ResolutionPath,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.decision import Decision
from cognitive_bridge.models.event import Event
from cognitive_bridge.models.kernel import IndividualKernel
from cognitive_bridge.models.parameters import CognitiveParameters
from cognitive_bridge.models.variant_set import Variant, VariantSet
from cognitive_bridge.storage.converters import (
    assertion_to_row,
    conflict_to_row,
    decision_to_row,
    event_to_row,
    kernel_to_row,
    parameters_to_row,
    row_to_assertion,
    row_to_conflict,
    row_to_decision,
    row_to_event,
    row_to_kernel,
    row_to_parameters,
    row_to_variant_set,
    variant_set_to_row,
)

_TS = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_TS2 = datetime(2025, 7, 1, 9, 30, 0, tzinfo=timezone.utc)
_PROJECT_ID = "proj_test"


class TestAssertionConverter:
    """Round-trip tests for assertion_to_row / row_to_assertion."""

    def _make_full_assertion(self, **overrides) -> Assertion:
        defaults = dict(
            id="ast_aabbccddeeff",
            topic_path="/architecture/database/engine",
            content="PostgreSQL outperforms MySQL at high concurrency.",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            evidence=["src1", "src2"],
            evidence_type=EvidenceType.CITED,
            depends_on_paths=["/x", "/y"],
            falsifiable_if="A benchmark showing MySQL matches this throughput.",
            assumption_status=AssumptionStatus.CHALLENGED,
            active=False,
            created_at=_TS,
            retracted_at=_TS2,
            confidence=0.9,
            embedding=[0.1, 0.2, 0.3],
            tags=["a", "b"],
        )
        defaults.update(overrides)
        return Assertion(**defaults)

    def test_full_round_trip_field_by_field(self) -> None:
        original = self._make_full_assertion()
        row = assertion_to_row(original, _PROJECT_ID)
        recovered = row_to_assertion(row)
        assert recovered.id == original.id
        assert recovered.topic_path == original.topic_path
        assert recovered.content == original.content
        assert recovered.arc == original.arc
        assert recovered.author == original.author
        assert recovered.evidence == original.evidence
        assert recovered.evidence_type == original.evidence_type
        assert recovered.depends_on_paths == original.depends_on_paths
        assert recovered.falsifiable_if == original.falsifiable_if
        assert recovered.assumption_status == original.assumption_status
        assert recovered.active == original.active
        assert recovered.created_at == original.created_at
        assert recovered.retracted_at == original.retracted_at
        assert recovered.confidence == original.confidence
        assert recovered.embedding == original.embedding
        assert recovered.tags == original.tags

    def test_project_id_stored_in_row(self) -> None:
        original = self._make_full_assertion()
        row = assertion_to_row(original, "my_project")
        assert row.project_id == "my_project"

    def test_json_lists_survive_round_trip(self) -> None:
        original = self._make_full_assertion(
            evidence=["src1", "src2"], tags=["a", "b"],
            depends_on_paths=["/x", "/y"], embedding=[0.1, 0.2, 0.3],
        )
        recovered = row_to_assertion(assertion_to_row(original, _PROJECT_ID))
        assert recovered.evidence == ["src1", "src2"]
        assert recovered.tags == ["a", "b"]
        assert recovered.depends_on_paths == ["/x", "/y"]
        assert recovered.embedding == [0.1, 0.2, 0.3]

    def test_embedding_none_round_trips_as_none(self) -> None:
        original = self._make_full_assertion(
            embedding=None, arc=CompositionArc.SPECIALIZES, falsifiable_if=None,
        )
        recovered = row_to_assertion(assertion_to_row(original, _PROJECT_ID))
        assert recovered.embedding is None

    def test_empty_lists_round_trip_as_empty_lists_not_none(self) -> None:
        original = self._make_full_assertion(
            evidence=[], tags=[], depends_on_paths=[],
            arc=CompositionArc.SPECIALIZES, falsifiable_if=None, embedding=None,
        )
        recovered = row_to_assertion(assertion_to_row(original, _PROJECT_ID))
        assert recovered.evidence == []
        assert recovered.tags == []
        assert recovered.depends_on_paths == []

    def test_arc_stored_as_int_and_recovered_as_enum(self) -> None:
        for arc in CompositionArc:
            overrides: dict = {"arc": arc}
            if arc != CompositionArc.LOCAL:
                overrides["falsifiable_if"] = None
            else:
                overrides["falsifiable_if"] = "Some falsification condition."
            original = self._make_full_assertion(**overrides)
            recovered = row_to_assertion(assertion_to_row(original, _PROJECT_ID))
            assert recovered.arc == arc
            assert isinstance(recovered.arc, CompositionArc)

    def test_author_recovered_as_enum(self) -> None:
        for author in AssertionAuthor:
            original = self._make_full_assertion(author=author)
            recovered = row_to_assertion(assertion_to_row(original, _PROJECT_ID))
            assert recovered.author == author
            assert isinstance(recovered.author, AssertionAuthor)

    def test_assumption_status_recovered_as_enum(self) -> None:
        for status in AssumptionStatus:
            original = self._make_full_assertion(assumption_status=status)
            recovered = row_to_assertion(assertion_to_row(original, _PROJECT_ID))
            assert recovered.assumption_status == status
            assert isinstance(recovered.assumption_status, AssumptionStatus)

    def test_retracted_at_none_round_trips(self) -> None:
        original = self._make_full_assertion(retracted_at=None)
        recovered = row_to_assertion(assertion_to_row(original, _PROJECT_ID))
        assert recovered.retracted_at is None


class TestConflictConverter:
    def _make_full_conflict(self, **overrides) -> Conflict:
        defaults = dict(
            id="cfl_112233445566",
            assertion_a_id="ast_aaaaaaaaaaaa",
            assertion_b_id="ast_bbbbbbbbbbbb",
            topic_path="/architecture/database",
            detection_layer=ConflictDetectionLayer.CASCADING,
            similarity_score=0.87,
            status=ConflictStatus.DEFERRED,
            available_paths=[ResolutionPath.ACCEPT, ResolutionPath.PROPOSE_EXPERIMENT],
            resolution_chosen=ResolutionPath.DEFER,
            resolution_evidence="Deferred pending experiment results.",
            resolution_note="Revisit in sprint 4.",
            steelman_of_opponent="MongoDB has better horizontal scaling for write-heavy workloads.",
            experiment_protocol="Run write benchmark with 10k concurrent clients.",
            experiment_result="PostgreSQL was 20% faster in our environment.",
            cascade_source_path="/architecture/infrastructure",
            produced_variant_set_id="var_cccccccccccc",
            created_at=_TS, resolved_at=_TS2,
        )
        defaults.update(overrides)
        return Conflict(**defaults)

    def test_full_round_trip_field_by_field(self) -> None:
        original = self._make_full_conflict()
        recovered = row_to_conflict(conflict_to_row(original, _PROJECT_ID))
        assert recovered.id == original.id
        assert recovered.assertion_a_id == original.assertion_a_id
        assert recovered.assertion_b_id == original.assertion_b_id
        assert recovered.topic_path == original.topic_path
        assert recovered.detection_layer == original.detection_layer
        assert recovered.similarity_score == original.similarity_score
        assert recovered.status == original.status
        assert recovered.available_paths == original.available_paths
        assert recovered.resolution_chosen == original.resolution_chosen
        assert recovered.resolution_evidence == original.resolution_evidence
        assert recovered.resolution_note == original.resolution_note
        assert recovered.steelman_of_opponent == original.steelman_of_opponent
        assert recovered.experiment_protocol == original.experiment_protocol
        assert recovered.experiment_result == original.experiment_result
        assert recovered.cascade_source_path == original.cascade_source_path
        assert recovered.produced_variant_set_id == original.produced_variant_set_id
        assert recovered.created_at == original.created_at
        assert recovered.resolved_at == original.resolved_at

    def test_available_paths_round_trip_as_enums(self) -> None:
        all_paths = list(ResolutionPath)
        original = self._make_full_conflict(available_paths=all_paths)
        recovered = row_to_conflict(conflict_to_row(original, _PROJECT_ID))
        assert recovered.available_paths == all_paths
        for p in recovered.available_paths:
            assert isinstance(p, ResolutionPath)

    def test_resolution_chosen_none_round_trips(self) -> None:
        original = self._make_full_conflict(resolution_chosen=None)
        recovered = row_to_conflict(conflict_to_row(original, _PROJECT_ID))
        assert recovered.resolution_chosen is None

    def test_detection_layer_recovered_as_enum(self) -> None:
        for layer in ConflictDetectionLayer:
            original = self._make_full_conflict(detection_layer=layer)
            recovered = row_to_conflict(conflict_to_row(original, _PROJECT_ID))
            assert recovered.detection_layer == layer
            assert isinstance(recovered.detection_layer, ConflictDetectionLayer)

    def test_status_recovered_as_enum(self) -> None:
        for status in ConflictStatus:
            original = self._make_full_conflict(status=status)
            recovered = row_to_conflict(conflict_to_row(original, _PROJECT_ID))
            assert recovered.status == status

    def test_empty_available_paths_round_trips(self) -> None:
        original = self._make_full_conflict(available_paths=[])
        recovered = row_to_conflict(conflict_to_row(original, _PROJECT_ID))
        assert recovered.available_paths == []

    def test_similarity_score_none_round_trips(self) -> None:
        original = self._make_full_conflict(similarity_score=None)
        recovered = row_to_conflict(conflict_to_row(original, _PROJECT_ID))
        assert recovered.similarity_score is None


class TestVariantSetConverter:
    def _make_variant(self, name: str) -> Variant:
        return Variant(
            name=name, content=f"Content for {name}",
            supporting_assertion_ids=["ast_111111111111", "ast_222222222222"],
            evidence_for=["evidence_for_1"], evidence_against=["evidence_against_1"],
            implications=["Implication A", "Implication B"],
            activation_condition="Condition X is met", active=True,
        )

    def _make_full_variant_set(self, **overrides) -> VariantSet:
        defaults = dict(
            id="var_aabbccddeeff", name="DB Engine Options",
            topic_path="/architecture/database",
            variants=[self._make_variant("PostgreSQL"), self._make_variant("MongoDB")],
            source_conflict_id="cfl_112233445566", source_red_team=True,
            resolved=True, resolved_variant_name="PostgreSQL",
            resolution_evidence="Benchmark confirmed PostgreSQL wins.",
            created_at=_TS, resolved_at=_TS2,
        )
        defaults.update(overrides)
        return VariantSet(**defaults)

    def test_full_round_trip_field_by_field(self) -> None:
        original = self._make_full_variant_set()
        recovered = row_to_variant_set(variant_set_to_row(original, _PROJECT_ID))
        assert recovered.id == original.id
        assert recovered.name == original.name
        assert recovered.topic_path == original.topic_path
        assert recovered.source_conflict_id == original.source_conflict_id
        assert recovered.source_red_team == original.source_red_team
        assert recovered.resolved == original.resolved
        assert recovered.resolved_variant_name == original.resolved_variant_name
        assert recovered.resolution_evidence == original.resolution_evidence
        assert recovered.created_at == original.created_at
        assert recovered.resolved_at == original.resolved_at

    def test_variants_round_trip_with_all_inner_fields(self) -> None:
        original = self._make_full_variant_set()
        recovered = row_to_variant_set(variant_set_to_row(original, _PROJECT_ID))
        assert len(recovered.variants) == 2
        for orig_v, rec_v in zip(original.variants, recovered.variants):
            assert rec_v.name == orig_v.name
            assert rec_v.content == orig_v.content
            assert rec_v.supporting_assertion_ids == orig_v.supporting_assertion_ids
            assert rec_v.evidence_for == orig_v.evidence_for
            assert rec_v.evidence_against == orig_v.evidence_against
            assert rec_v.implications == orig_v.implications
            assert rec_v.activation_condition == orig_v.activation_condition
            assert rec_v.active == orig_v.active

    def test_variant_with_empty_optional_lists_round_trips(self) -> None:
        vs = VariantSet(
            id="var_000000000000", name="Minimal VS", topic_path="/some/path",
            variants=[Variant(name="A", content="content A"), Variant(name="B", content="content B")],
            created_at=_TS,
        )
        recovered = row_to_variant_set(variant_set_to_row(vs, _PROJECT_ID))
        assert recovered.variants[0].supporting_assertion_ids == []
        assert recovered.variants[0].evidence_for == []
        assert recovered.variants[0].evidence_against == []
        assert recovered.variants[0].implications == []
        assert recovered.variants[0].activation_condition is None

    def test_source_conflict_id_none_round_trips(self) -> None:
        original = self._make_full_variant_set(source_conflict_id=None)
        recovered = row_to_variant_set(variant_set_to_row(original, _PROJECT_ID))
        assert recovered.source_conflict_id is None

    def test_resolved_at_none_round_trips(self) -> None:
        original = self._make_full_variant_set(resolved_at=None)
        recovered = row_to_variant_set(variant_set_to_row(original, _PROJECT_ID))
        assert recovered.resolved_at is None


class TestEventConverter:
    def _make_full_event(self, **overrides) -> Event:
        defaults = dict(
            id="evt_aabbccddeeff", event_type=EventType.CONFLICT_DETECTED,
            timestamp=_TS, actor=AssertionAuthor.SYSTEM, target_id="cfl_112233445566",
            detail={
                "message": "Structural conflict detected", "count": 3, "score": 0.95,
                "active": True, "nullable_field": None,
                "nested": {"key": "value"}, "list_field": [1, 2, 3],
            },
        )
        defaults.update(overrides)
        return Event(**defaults)

    def test_full_round_trip_field_by_field(self) -> None:
        original = self._make_full_event()
        recovered = row_to_event(event_to_row(original, _PROJECT_ID))
        assert recovered.id == original.id
        assert recovered.event_type == original.event_type
        assert recovered.timestamp == original.timestamp
        assert recovered.actor == original.actor
        assert recovered.target_id == original.target_id
        assert recovered.detail == original.detail

    def test_detail_with_mixed_types_round_trips(self) -> None:
        detail = {
            "str_field": "hello", "int_field": 42, "float_field": 3.14,
            "bool_field": False, "none_field": None,
            "nested_dict": {"inner": "value"}, "nested_list": [1, "two", 3.0],
        }
        original = self._make_full_event(detail=detail)
        recovered = row_to_event(event_to_row(original, _PROJECT_ID))
        assert recovered.detail == detail

    def test_empty_detail_round_trips(self) -> None:
        original = self._make_full_event(detail={})
        recovered = row_to_event(event_to_row(original, _PROJECT_ID))
        assert recovered.detail == {}

    def test_event_type_recovered_as_enum(self) -> None:
        for et in EventType:
            original = self._make_full_event(event_type=et)
            recovered = row_to_event(event_to_row(original, _PROJECT_ID))
            assert recovered.event_type == et
            assert isinstance(recovered.event_type, EventType)

    def test_actor_recovered_as_enum(self) -> None:
        for actor in AssertionAuthor:
            original = self._make_full_event(actor=actor)
            recovered = row_to_event(event_to_row(original, _PROJECT_ID))
            assert recovered.actor == actor
            assert isinstance(recovered.actor, AssertionAuthor)


class TestDecisionConverter:
    def _make_full_decision(self, **overrides) -> Decision:
        defaults = dict(
            id="dec_aabbccddeeff", topic_path="/architecture/database",
            decision="Use PostgreSQL as the primary datastore.",
            rationale="Strongest ACID guarantees among evaluated options.",
            assertion_ids=["ast_111111111111", "ast_222222222222"],
            conflict_ids=["cfl_333333333333"],
            alternatives_rejected=[
                "MySQL — rejected because weaker JSON support.",
                "MongoDB — rejected because project requires relational integrity.",
            ],
            second_order_effects=[
                "All services must speak SQL.",
                "Schema migrations required for every model change.",
            ],
            reversibility="costly", created_at=_TS,
        )
        defaults.update(overrides)
        return Decision(**defaults)

    def test_full_round_trip_field_by_field(self) -> None:
        original = self._make_full_decision()
        recovered = row_to_decision(decision_to_row(original, _PROJECT_ID))
        assert recovered.id == original.id
        assert recovered.topic_path == original.topic_path
        assert recovered.decision == original.decision
        assert recovered.rationale == original.rationale
        assert recovered.assertion_ids == original.assertion_ids
        assert recovered.conflict_ids == original.conflict_ids
        assert recovered.alternatives_rejected == original.alternatives_rejected
        assert recovered.second_order_effects == original.second_order_effects
        assert recovered.reversibility == original.reversibility
        assert recovered.created_at == original.created_at

    def test_assertion_ids_empty_list_round_trips(self) -> None:
        original = self._make_full_decision(assertion_ids=[])
        recovered = row_to_decision(decision_to_row(original, _PROJECT_ID))
        assert recovered.assertion_ids == []

    def test_conflict_ids_empty_list_round_trips(self) -> None:
        original = self._make_full_decision(conflict_ids=[])
        recovered = row_to_decision(decision_to_row(original, _PROJECT_ID))
        assert recovered.conflict_ids == []

    def test_multiple_alternatives_and_effects_preserved(self) -> None:
        alts = [f"Alt {i} — rejected because reason {i}" for i in range(5)]
        effects = [f"Effect {i}" for i in range(4)]
        original = self._make_full_decision(
            alternatives_rejected=alts, second_order_effects=effects,
        )
        recovered = row_to_decision(decision_to_row(original, _PROJECT_ID))
        assert recovered.alternatives_rejected == alts
        assert recovered.second_order_effects == effects


class TestParametersConverter:
    def _make_full_parameters(self, **overrides) -> CognitiveParameters:
        defaults = dict(
            conflict_sensitivity=0.8, semantic_threshold=0.95,
            cross_path_detection=True, exploration_budget=10,
            ai_default_arc=CompositionArc.REFERENCES,
            payload_surfacing=False, red_team_threshold=15,
            cascade_auto_challenge=False,
        )
        defaults.update(overrides)
        return CognitiveParameters(**defaults)

    def test_full_round_trip_field_by_field(self) -> None:
        original = self._make_full_parameters()
        recovered = row_to_parameters(parameters_to_row(original, _PROJECT_ID))
        assert recovered.conflict_sensitivity == original.conflict_sensitivity
        assert recovered.semantic_threshold == original.semantic_threshold
        assert recovered.cross_path_detection == original.cross_path_detection
        assert recovered.exploration_budget == original.exploration_budget
        assert recovered.ai_default_arc == original.ai_default_arc
        assert recovered.payload_surfacing == original.payload_surfacing
        assert recovered.red_team_threshold == original.red_team_threshold
        assert recovered.cascade_auto_challenge == original.cascade_auto_challenge

    def test_ai_default_arc_recovered_as_enum(self) -> None:
        for arc in CompositionArc:
            original = self._make_full_parameters(ai_default_arc=arc)
            recovered = row_to_parameters(parameters_to_row(original, _PROJECT_ID))
            assert recovered.ai_default_arc == arc
            assert isinstance(recovered.ai_default_arc, CompositionArc)

    def test_bool_fields_round_trip(self) -> None:
        for cp_val, pa_val, cac_val in [(True, True, True), (False, False, False), (True, False, True)]:
            original = self._make_full_parameters(
                cross_path_detection=cp_val, payload_surfacing=pa_val, cascade_auto_challenge=cac_val,
            )
            recovered = row_to_parameters(parameters_to_row(original, _PROJECT_ID))
            assert recovered.cross_path_detection == cp_val
            assert recovered.payload_surfacing == pa_val
            assert recovered.cascade_auto_challenge == cac_val

    def test_default_parameters_round_trip(self) -> None:
        original = CognitiveParameters()
        recovered = row_to_parameters(parameters_to_row(original, _PROJECT_ID))
        assert recovered.conflict_sensitivity == original.conflict_sensitivity
        assert recovered.semantic_threshold == original.semantic_threshold
        assert recovered.ai_default_arc == original.ai_default_arc


class TestKernelConverter:
    def _make_full_kernel(self, **overrides) -> IndividualKernel:
        defaults = dict(
            id="ker_aabbccddeeff",
            entropy_tolerance=0.8, process_purity=0.3,
            autonomy_boundary=0.7, energy_level=0.9,
            probe_count=5, last_probed=_TS2,
            created_at=_TS, updated_at=_TS2,
        )
        defaults.update(overrides)
        return IndividualKernel(**defaults)

    def test_full_round_trip_field_by_field(self) -> None:
        original = self._make_full_kernel()
        recovered = row_to_kernel(kernel_to_row(original, _PROJECT_ID))
        assert recovered.id == original.id
        assert recovered.entropy_tolerance == original.entropy_tolerance
        assert recovered.process_purity == original.process_purity
        assert recovered.autonomy_boundary == original.autonomy_boundary
        assert recovered.energy_level == original.energy_level
        assert recovered.probe_count == original.probe_count
        assert recovered.last_probed == original.last_probed
        assert recovered.created_at == original.created_at
        assert recovered.updated_at == original.updated_at

    def test_last_probed_none_round_trips(self) -> None:
        original = self._make_full_kernel(last_probed=None)
        recovered = row_to_kernel(kernel_to_row(original, _PROJECT_ID))
        assert recovered.last_probed is None

    def test_probe_count_zero_round_trips(self) -> None:
        original = self._make_full_kernel(probe_count=0)
        recovered = row_to_kernel(kernel_to_row(original, _PROJECT_ID))
        assert recovered.probe_count == 0

    def test_boundary_dimension_values_round_trip(self) -> None:
        for val in [0.0, 1.0, 0.5]:
            original = self._make_full_kernel(
                entropy_tolerance=val, process_purity=val,
                autonomy_boundary=val, energy_level=val,
            )
            recovered = row_to_kernel(kernel_to_row(original, _PROJECT_ID))
            assert recovered.entropy_tolerance == val
            assert recovered.process_purity == val
            assert recovered.autonomy_boundary == val
            assert recovered.energy_level == val
