"""Tests for core enums and utilities in arcs.py."""

from datetime import datetime, timezone

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
    EventType,
    EvidenceType,
    ResolutionPath,
    _new_id,
    _now_utc,
)


class TestCompositionArc:
    """CompositionArc IntEnum ordering and values."""

    def test_livrps_ordering(self) -> None:
        assert CompositionArc.LOCAL < CompositionArc.INHERITS
        assert CompositionArc.INHERITS < CompositionArc.VARIANT_SET
        assert CompositionArc.VARIANT_SET < CompositionArc.REFERENCES
        assert CompositionArc.REFERENCES < CompositionArc.PAYLOADS
        assert CompositionArc.PAYLOADS < CompositionArc.SPECIALIZES

    def test_integer_values(self) -> None:
        assert CompositionArc.LOCAL == 10
        assert CompositionArc.INHERITS == 20
        assert CompositionArc.VARIANT_SET == 30
        assert CompositionArc.REFERENCES == 40
        assert CompositionArc.PAYLOADS == 50
        assert CompositionArc.SPECIALIZES == 60

    def test_sortable(self) -> None:
        arcs = [
            CompositionArc.SPECIALIZES,
            CompositionArc.LOCAL,
            CompositionArc.REFERENCES,
        ]
        assert sorted(arcs) == [
            CompositionArc.LOCAL,
            CompositionArc.REFERENCES,
            CompositionArc.SPECIALIZES,
        ]

    def test_constructible_from_int(self) -> None:
        assert CompositionArc(10) == CompositionArc.LOCAL
        assert CompositionArc(60) == CompositionArc.SPECIALIZES


class TestAssertionAuthor:
    def test_values(self) -> None:
        assert AssertionAuthor.AI.value == "ai"
        assert AssertionAuthor.USER.value == "user"
        assert AssertionAuthor.SYSTEM.value == "system"
        assert AssertionAuthor.EXTERNAL.value == "external"

    def test_constructible_from_string(self) -> None:
        assert AssertionAuthor("ai") == AssertionAuthor.AI


class TestEvidenceType:
    def test_all_values(self) -> None:
        expected = {"computed", "observed", "cited", "inferred", "unverified"}
        assert {e.value for e in EvidenceType} == expected


class TestAssumptionStatus:
    def test_all_values(self) -> None:
        expected = {"live", "challenged", "falsified", "orphaned"}
        assert {s.value for s in AssumptionStatus} == expected


class TestConflictStatus:
    def test_count(self) -> None:
        assert len(ConflictStatus) == 7

    def test_v3_experiment_status(self) -> None:
        assert ConflictStatus.RESOLVED_EXPERIMENT.value == "experiment"


class TestResolutionPath:
    def test_count(self) -> None:
        assert len(ResolutionPath) == 7

    def test_v3_propose_experiment(self) -> None:
        assert ResolutionPath.PROPOSE_EXPERIMENT.value == "propose_experiment"


class TestConflictDetectionLayer:
    def test_all_layers(self) -> None:
        expected = {"structural", "semantic", "delegated", "cascading"}
        assert {l.value for l in ConflictDetectionLayer} == expected


class TestEventType:
    def test_v3_event_types_present(self) -> None:
        v3_types = {
            EventType.ASSERTION_CHALLENGED,
            EventType.ASSERTION_FALSIFIED,
            EventType.ASSERTION_ORPHANED,
            EventType.CONFLICT_EXPERIMENT_PROPOSED,
            EventType.CONFLICT_EXPERIMENT_RESOLVED,
            EventType.RED_TEAM_TRIGGERED,
        }
        all_types = set(EventType)
        assert v3_types.issubset(all_types)

    def test_total_count(self) -> None:
        assert len(EventType) == 17


class TestUtilities:
    def test_now_utc_is_aware(self) -> None:
        ts = _now_utc()
        assert isinstance(ts, datetime)
        assert ts.tzinfo is not None
        assert ts.tzinfo == timezone.utc

    def test_new_id_format(self) -> None:
        id_ = _new_id("ast")
        assert id_.startswith("ast_")
        assert len(id_) == 4 + 12  # prefix_ + 12 hex chars

    def test_new_id_custom_prefix(self) -> None:
        id_ = _new_id("cfl")
        assert id_.startswith("cfl_")

    def test_new_id_uniqueness(self) -> None:
        ids = {_new_id("ast") for _ in range(100)}
        assert len(ids) == 100
