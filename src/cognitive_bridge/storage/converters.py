"""Converters between Pydantic models and SQLModel table rows.

Each model type has a pair of converter functions:
- {model}_to_row(model, project_id) -> Row
- row_to_{model}(row) -> Model

JSON fields are explicitly serialized/deserialized so the storage layer
never sees raw Python objects in column values.
"""

import json

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
    EvidenceType,
    EventType,
    ResolutionPath,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.decision import Decision
from cognitive_bridge.models.event import Event
from cognitive_bridge.models.kernel import IndividualKernel
from cognitive_bridge.models.parameters import CognitiveParameters
from cognitive_bridge.models.variant_set import Variant, VariantSet
from cognitive_bridge.storage.sqlite_store import (
    AssertionRow,
    ConflictRow,
    DecisionRow,
    EventRow,
    KernelRow,
    ParametersRow,
    VariantSetRow,
)


# ═══════════════════════════════════════════════════════════════
# Assertion converters
# ═══════════════════════════════════════════════════════════════


def assertion_to_row(assertion: Assertion, project_id: str) -> AssertionRow:
    """Convert Pydantic Assertion to SQLModel AssertionRow."""
    return AssertionRow(
        id=assertion.id,
        project_id=project_id,
        topic_path=assertion.topic_path,
        content=assertion.content,
        arc=int(assertion.arc),
        author=assertion.author.value,
        evidence_json=json.dumps(assertion.evidence),
        evidence_type=assertion.evidence_type.value,
        depends_on_paths_json=json.dumps(assertion.depends_on_paths),
        falsifiable_if=assertion.falsifiable_if,
        assumption_status=assertion.assumption_status.value,
        active=assertion.active,
        created_at=assertion.created_at,
        retracted_at=assertion.retracted_at,
        confidence=assertion.confidence,
        embedding_json=json.dumps(assertion.embedding) if assertion.embedding is not None else None,
        tags_json=json.dumps(assertion.tags),
    )


def row_to_assertion(row: AssertionRow) -> Assertion:
    """Convert SQLModel AssertionRow to Pydantic Assertion."""
    return Assertion(
        id=row.id,
        topic_path=row.topic_path,
        content=row.content,
        arc=CompositionArc(row.arc),
        author=AssertionAuthor(row.author),
        evidence=json.loads(row.evidence_json),
        evidence_type=EvidenceType(row.evidence_type),
        depends_on_paths=json.loads(row.depends_on_paths_json),
        falsifiable_if=row.falsifiable_if,
        assumption_status=AssumptionStatus(row.assumption_status),
        active=row.active,
        created_at=row.created_at,
        retracted_at=row.retracted_at,
        confidence=row.confidence,
        embedding=json.loads(row.embedding_json) if row.embedding_json is not None else None,
        tags=json.loads(row.tags_json),
    )


# ═══════════════════════════════════════════════════════════════
# Conflict converters
# ═══════════════════════════════════════════════════════════════


def conflict_to_row(conflict: Conflict, project_id: str) -> ConflictRow:
    """Convert Pydantic Conflict to SQLModel ConflictRow."""
    return ConflictRow(
        id=conflict.id,
        project_id=project_id,
        assertion_a_id=conflict.assertion_a_id,
        assertion_b_id=conflict.assertion_b_id,
        topic_path=conflict.topic_path,
        detection_layer=conflict.detection_layer.value,
        similarity_score=conflict.similarity_score,
        status=conflict.status.value,
        available_paths_json=json.dumps([p.value for p in conflict.available_paths]),
        resolution_chosen=conflict.resolution_chosen.value if conflict.resolution_chosen else None,
        resolution_evidence=conflict.resolution_evidence,
        resolution_note=conflict.resolution_note,
        steelman_of_opponent=conflict.steelman_of_opponent,
        experiment_protocol=conflict.experiment_protocol,
        experiment_result=conflict.experiment_result,
        cascade_source_path=conflict.cascade_source_path,
        produced_variant_set_id=conflict.produced_variant_set_id,
        created_at=conflict.created_at,
        resolved_at=conflict.resolved_at,
    )


def row_to_conflict(row: ConflictRow) -> Conflict:
    """Convert SQLModel ConflictRow to Pydantic Conflict."""
    return Conflict(
        id=row.id,
        assertion_a_id=row.assertion_a_id,
        assertion_b_id=row.assertion_b_id,
        topic_path=row.topic_path,
        detection_layer=ConflictDetectionLayer(row.detection_layer),
        similarity_score=row.similarity_score,
        status=ConflictStatus(row.status),
        available_paths=[ResolutionPath(p) for p in json.loads(row.available_paths_json)],
        resolution_chosen=ResolutionPath(row.resolution_chosen) if row.resolution_chosen else None,
        resolution_evidence=row.resolution_evidence,
        resolution_note=row.resolution_note,
        steelman_of_opponent=row.steelman_of_opponent,
        experiment_protocol=row.experiment_protocol,
        experiment_result=row.experiment_result,
        cascade_source_path=row.cascade_source_path,
        produced_variant_set_id=row.produced_variant_set_id,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


# ═══════════════════════════════════════════════════════════════
# VariantSet converters
# ═══════════════════════════════════════════════════════════════


def variant_set_to_row(vs: VariantSet, project_id: str) -> VariantSetRow:
    """Convert Pydantic VariantSet to SQLModel VariantSetRow."""
    return VariantSetRow(
        id=vs.id,
        project_id=project_id,
        name=vs.name,
        topic_path=vs.topic_path,
        variants_json=json.dumps([v.model_dump() for v in vs.variants]),
        source_conflict_id=vs.source_conflict_id,
        source_red_team=vs.source_red_team,
        resolved=vs.resolved,
        resolved_variant_name=vs.resolved_variant_name,
        resolution_evidence=vs.resolution_evidence,
        created_at=vs.created_at,
        resolved_at=vs.resolved_at,
    )


def row_to_variant_set(row: VariantSetRow) -> VariantSet:
    """Convert SQLModel VariantSetRow to Pydantic VariantSet."""
    variants_data = json.loads(row.variants_json)
    return VariantSet(
        id=row.id,
        name=row.name,
        topic_path=row.topic_path,
        variants=[Variant(**v) for v in variants_data],
        source_conflict_id=row.source_conflict_id,
        source_red_team=row.source_red_team,
        resolved=row.resolved,
        resolved_variant_name=row.resolved_variant_name,
        resolution_evidence=row.resolution_evidence,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


# ═══════════════════════════════════════════════════════════════
# Event converters
# ═══════════════════════════════════════════════════════════════


def event_to_row(event: Event, project_id: str) -> EventRow:
    """Convert Pydantic Event to SQLModel EventRow."""
    return EventRow(
        id=event.id,
        project_id=project_id,
        event_type=event.event_type.value,
        timestamp=event.timestamp,
        actor=event.actor.value,
        target_id=event.target_id,
        detail_json=json.dumps(event.detail),
    )


def row_to_event(row: EventRow) -> Event:
    """Convert SQLModel EventRow to Pydantic Event."""
    return Event(
        id=row.id,
        event_type=EventType(row.event_type),
        timestamp=row.timestamp,
        actor=AssertionAuthor(row.actor),
        target_id=row.target_id,
        detail=json.loads(row.detail_json),
    )


# ═══════════════════════════════════════════════════════════════
# Decision converters
# ═══════════════════════════════════════════════════════════════


def decision_to_row(dec: Decision, project_id: str) -> DecisionRow:
    """Convert Pydantic Decision to SQLModel DecisionRow."""
    return DecisionRow(
        id=dec.id,
        project_id=project_id,
        topic_path=dec.topic_path,
        decision=dec.decision,
        rationale=dec.rationale,
        assertion_ids_json=json.dumps(dec.assertion_ids),
        conflict_ids_json=json.dumps(dec.conflict_ids),
        alternatives_rejected_json=json.dumps(dec.alternatives_rejected),
        second_order_effects_json=json.dumps(dec.second_order_effects),
        reversibility=dec.reversibility,
        created_at=dec.created_at,
    )


def row_to_decision(row: DecisionRow) -> Decision:
    """Convert SQLModel DecisionRow to Pydantic Decision."""
    return Decision(
        id=row.id,
        topic_path=row.topic_path,
        decision=row.decision,
        rationale=row.rationale,
        assertion_ids=json.loads(row.assertion_ids_json),
        conflict_ids=json.loads(row.conflict_ids_json),
        alternatives_rejected=json.loads(row.alternatives_rejected_json),
        second_order_effects=json.loads(row.second_order_effects_json),
        reversibility=row.reversibility,
        created_at=row.created_at,
    )


# ═══════════════════════════════════════════════════════════════
# Parameters converters
# ═══════════════════════════════════════════════════════════════


def parameters_to_row(params: CognitiveParameters, project_id: str) -> ParametersRow:
    """Convert Pydantic CognitiveParameters to SQLModel ParametersRow."""
    return ParametersRow(
        project_id=project_id,
        conflict_sensitivity=params.conflict_sensitivity,
        semantic_threshold=params.semantic_threshold,
        cross_path_detection=params.cross_path_detection,
        exploration_budget=params.exploration_budget,
        ai_default_arc=int(params.ai_default_arc),
        payload_surfacing=params.payload_surfacing,
        red_team_threshold=params.red_team_threshold,
        cascade_auto_challenge=params.cascade_auto_challenge,
    )


def row_to_parameters(row: ParametersRow) -> CognitiveParameters:
    """Convert SQLModel ParametersRow to Pydantic CognitiveParameters."""
    return CognitiveParameters(
        conflict_sensitivity=row.conflict_sensitivity,
        semantic_threshold=row.semantic_threshold,
        cross_path_detection=row.cross_path_detection,
        exploration_budget=row.exploration_budget,
        ai_default_arc=CompositionArc(row.ai_default_arc),
        payload_surfacing=row.payload_surfacing,
        red_team_threshold=row.red_team_threshold,
        cascade_auto_challenge=row.cascade_auto_challenge,
    )


# ═══════════════════════════════════════════════════════════════
# Kernel converters
# ═══════════════════════════════════════════════════════════════


def kernel_to_row(kernel: IndividualKernel, project_id: str) -> KernelRow:
    """Convert Pydantic IndividualKernel to SQLModel KernelRow."""
    return KernelRow(
        id=kernel.id,
        project_id=project_id,
        entropy_tolerance=kernel.entropy_tolerance,
        process_purity=kernel.process_purity,
        autonomy_boundary=kernel.autonomy_boundary,
        energy_level=kernel.energy_level,
        probe_count=kernel.probe_count,
        last_probed=kernel.last_probed,
        created_at=kernel.created_at,
        updated_at=kernel.updated_at,
    )


def row_to_kernel(row: KernelRow) -> IndividualKernel:
    """Convert SQLModel KernelRow to Pydantic IndividualKernel."""
    return IndividualKernel(
        id=row.id,
        entropy_tolerance=row.entropy_tolerance,
        process_purity=row.process_purity,
        autonomy_boundary=row.autonomy_boundary,
        energy_level=row.energy_level,
        probe_count=row.probe_count,
        last_probed=row.last_probed,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
