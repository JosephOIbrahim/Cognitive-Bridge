"""Tests for the Conflict model."""

from datetime import datetime, timezone

import pytest

from cognitive_bridge.models.arcs import (
    ConflictDetectionLayer,
    ConflictStatus,
    ResolutionPath,
)
from cognitive_bridge.models.conflict import Conflict


def _make_conflict(**kwargs) -> Conflict:
    """Return a minimal valid Conflict, merging any overrides."""
    defaults = dict(
        assertion_a_id="ast_aaaaaaaaaaaa",
        assertion_b_id="ast_bbbbbbbbbbbb",
        topic_path="/architecture/database/engine",
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
    )
    defaults.update(kwargs)
    return Conflict(**defaults)


class TestConflictConstruction:
    """Default construction and required fields."""

    def test_minimal_construction(self) -> None:
        c = _make_conflict()
        assert c.assertion_a_id == "ast_aaaaaaaaaaaa"
        assert c.assertion_b_id == "ast_bbbbbbbbbbbb"
        assert c.topic_path == "/architecture/database/engine"
        assert c.detection_layer == ConflictDetectionLayer.STRUCTURAL

    def test_id_is_auto_generated(self) -> None:
        c = _make_conflict()
        assert c.id.startswith("cfl_")
        assert len(c.id) == 4 + 12  # "cfl_" + 12 hex chars

    def test_id_uniqueness(self) -> None:
        ids = {_make_conflict().id for _ in range(50)}
        assert len(ids) == 50

    def test_created_at_is_utc_aware(self) -> None:
        c = _make_conflict()
        assert isinstance(c.created_at, datetime)
        assert c.created_at.tzinfo is not None
        assert c.created_at.tzinfo == timezone.utc


class TestConflictDefaults:
    """Default field values."""

    def test_default_status_is_active(self) -> None:
        c = _make_conflict()
        assert c.status == ConflictStatus.ACTIVE

    def test_available_paths_defaults_to_all_resolution_paths(self) -> None:
        c = _make_conflict()
        assert set(c.available_paths) == set(ResolutionPath)

    def test_similarity_score_defaults_to_none(self) -> None:
        c = _make_conflict()
        assert c.similarity_score is None

    def test_resolution_fields_default_to_none(self) -> None:
        c = _make_conflict()
        assert c.resolution_chosen is None
        assert c.resolution_evidence is None
        assert c.resolution_note is None
        assert c.resolved_at is None

    def test_steelman_and_experiment_fields_default_to_none(self) -> None:
        c = _make_conflict()
        assert c.steelman_of_opponent is None
        assert c.experiment_protocol is None
        assert c.experiment_result is None

    def test_cascade_fields_default_to_none(self) -> None:
        c = _make_conflict()
        assert c.cascade_source_path is None
        assert c.produced_variant_set_id is None


class TestConflictCascadingLayer:
    """CASCADING detection layer and associated fields."""

    def test_cascading_layer_accepted(self) -> None:
        c = _make_conflict(
            detection_layer=ConflictDetectionLayer.CASCADING,
            cascade_source_path="/architecture/database",
        )
        assert c.detection_layer == ConflictDetectionLayer.CASCADING
        assert c.cascade_source_path == "/architecture/database"

    def test_cascade_source_path_is_optional_even_for_cascading(self) -> None:
        # Schema does not enforce cascade_source_path on CASCADING layer —
        # that is an engine-level concern, not a model validator.
        c = _make_conflict(detection_layer=ConflictDetectionLayer.CASCADING)
        assert c.cascade_source_path is None


class TestConflictResolutionMetadata:
    """Steelman and experiment fields accept values correctly."""

    def test_steelman_field_accepts_value(self) -> None:
        c = _make_conflict(
            steelman_of_opponent="The strongest argument for the opposing view is..."
        )
        assert c.steelman_of_opponent == "The strongest argument for the opposing view is..."

    def test_experiment_protocol_accepts_value(self) -> None:
        c = _make_conflict(
            experiment_protocol="Run benchmark X under conditions Y and compare latency."
        )
        assert c.experiment_protocol == "Run benchmark X under conditions Y and compare latency."

    def test_experiment_result_accepts_value(self) -> None:
        c = _make_conflict(
            experiment_result="Approach A was 30% faster under load."
        )
        assert c.experiment_result == "Approach A was 30% faster under load."

    def test_resolution_chosen_accepts_enum_value(self) -> None:
        c = _make_conflict(resolution_chosen=ResolutionPath.CHALLENGE)
        assert c.resolution_chosen == ResolutionPath.CHALLENGE

    def test_similarity_score_accepts_float(self) -> None:
        c = _make_conflict(similarity_score=0.87)
        assert c.similarity_score == pytest.approx(0.87)


class TestConflictStrip:
    """str_strip_whitespace removes leading/trailing whitespace from string fields."""

    def test_topic_path_whitespace_stripped(self) -> None:
        c = _make_conflict(topic_path="  /architecture/database/engine  ")
        assert c.topic_path == "/architecture/database/engine"

    def test_assertion_id_whitespace_stripped(self) -> None:
        c = _make_conflict(assertion_a_id="  ast_aaaaaaaaaaaa  ")
        assert c.assertion_a_id == "ast_aaaaaaaaaaaa"
