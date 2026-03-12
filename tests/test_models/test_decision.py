"""Tests for the Decision model."""

import pytest
from pydantic import ValidationError

from cognitive_bridge.models.decision import Decision


MINIMAL_VALID = dict(
    topic_path="/architecture/database",
    decision="Use PostgreSQL as the primary datastore.",
    rationale="Strongest ACID guarantees among evaluated options.",
    alternatives_rejected=["SQLite — rejected because insufficient concurrency for production."],
    second_order_effects=["All services must speak SQL; NoSQL adapters are out of scope."],
)


class TestDecisionConstruction:
    def test_basic_construction_succeeds(self) -> None:
        d = Decision(**MINIMAL_VALID)
        assert d.topic_path == "/architecture/database"
        assert d.decision == "Use PostgreSQL as the primary datastore."
        assert d.rationale == "Strongest ACID guarantees among evaluated options."
        assert len(d.alternatives_rejected) == 1
        assert len(d.second_order_effects) == 1

    def test_id_auto_generated_with_dec_prefix(self) -> None:
        d = Decision(**MINIMAL_VALID)
        assert d.id.startswith("dec_")
        # prefix "dec_" = 4 chars + 12 hex = 16 total
        assert len(d.id) == 16

    def test_id_uniqueness(self) -> None:
        ids = {Decision(**MINIMAL_VALID).id for _ in range(50)}
        assert len(ids) == 50

    def test_reversibility_defaults_to_unknown(self) -> None:
        d = Decision(**MINIMAL_VALID)
        assert d.reversibility == "unknown"

    def test_reversibility_explicit_value(self) -> None:
        d = Decision(**MINIMAL_VALID, reversibility="irreversible")
        assert d.reversibility == "irreversible"

    def test_assertion_ids_default_empty(self) -> None:
        d = Decision(**MINIMAL_VALID)
        assert d.assertion_ids == []

    def test_conflict_ids_default_empty(self) -> None:
        d = Decision(**MINIMAL_VALID)
        assert d.conflict_ids == []

    def test_created_at_is_set(self) -> None:
        from datetime import timezone
        d = Decision(**MINIMAL_VALID)
        assert d.created_at is not None
        assert d.created_at.tzinfo == timezone.utc

    def test_multiple_alternatives_and_effects(self) -> None:
        base = {k: v for k, v in MINIMAL_VALID.items()
                if k not in ("alternatives_rejected", "second_order_effects")}
        d = Decision(
            **base,
            alternatives_rejected=[
                "MySQL — rejected because weaker JSON support.",
                "MongoDB — rejected because project requires relational integrity.",
            ],
            second_order_effects=[
                "Schema migrations required for every model change.",
                "ORM must support async drivers.",
            ],
        )
        assert len(d.alternatives_rejected) == 2
        assert len(d.second_order_effects) == 2


class TestDecisionValidation:
    def test_alternatives_rejected_empty_list_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Decision(**{**MINIMAL_VALID, "alternatives_rejected": []})
        errors = exc_info.value.errors()
        assert any("alternatives_rejected" in str(e) for e in errors)

    def test_second_order_effects_empty_list_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Decision(**{**MINIMAL_VALID, "second_order_effects": []})
        errors = exc_info.value.errors()
        assert any("second_order_effects" in str(e) for e in errors)

    def test_alternatives_rejected_missing_raises(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "alternatives_rejected"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_second_order_effects_missing_raises(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "second_order_effects"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_topic_path_required(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "topic_path"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_decision_field_required(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "decision"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_rationale_required(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "rationale"}
        with pytest.raises(ValidationError):
            Decision(**payload)
