"""Tests for models/decision.py — Decision with anti-convergence enforcement.

Blueprint reference: Section 3.6 (Decision model with alternatives + second-order effects).
Constitution rule C5 (alternatives + effects required), G2 (validator-rejection symmetry).
"""

from datetime import timezone

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
        assert len(d.alternatives_rejected) == 1
        assert len(d.second_order_effects) == 1

    def test_id_auto_generated_with_dec_prefix(self) -> None:
        d = Decision(**MINIMAL_VALID)
        assert d.id.startswith("dec_")
        assert len(d.id) == 16

    def test_id_uniqueness_across_instances(self) -> None:
        ids = {Decision(**MINIMAL_VALID).id for _ in range(50)}
        assert len(ids) == 50

    def test_reversibility_defaults_to_unknown(self) -> None:
        assert Decision(**MINIMAL_VALID).reversibility == "unknown"

    def test_reversibility_explicit_trivial(self) -> None:
        assert Decision(**MINIMAL_VALID, reversibility="trivial").reversibility == "trivial"

    def test_reversibility_explicit_irreversible(self) -> None:
        assert Decision(**MINIMAL_VALID, reversibility="irreversible").reversibility == "irreversible"

    def test_assertion_ids_default_empty_list(self) -> None:
        assert Decision(**MINIMAL_VALID).assertion_ids == []

    def test_conflict_ids_default_empty_list(self) -> None:
        assert Decision(**MINIMAL_VALID).conflict_ids == []

    def test_created_at_is_timezone_aware_utc(self) -> None:
        d = Decision(**MINIMAL_VALID)
        assert d.created_at.tzinfo == timezone.utc

    def test_explicit_assertion_ids_stored(self) -> None:
        d = Decision(**MINIMAL_VALID, assertion_ids=["ast_aabbccddeeff", "ast_112233445566"])
        assert d.assertion_ids == ["ast_aabbccddeeff", "ast_112233445566"]

    def test_explicit_conflict_ids_stored(self) -> None:
        d = Decision(**MINIMAL_VALID, conflict_ids=["cfl_aabbccddeeff"])
        assert d.conflict_ids == ["cfl_aabbccddeeff"]

    def test_multiple_alternatives_and_effects(self) -> None:
        base = {k: v for k, v in MINIMAL_VALID.items() if k not in ("alternatives_rejected", "second_order_effects")}
        d = Decision(
            **base,
            alternatives_rejected=[
                "MySQL — rejected because weaker JSON support.",
                "MongoDB — rejected because project requires relational integrity.",
                "DynamoDB — rejected because cost prohibitive at our scale.",
            ],
            second_order_effects=[
                "Schema migrations required for every model change.",
                "ORM must support async drivers.",
            ],
        )
        assert len(d.alternatives_rejected) == 3
        assert len(d.second_order_effects) == 2

    def test_whitespace_stripped_from_string_fields(self) -> None:
        d = Decision(
            topic_path="  /architecture/database  ",
            decision="  Use PostgreSQL.  ",
            rationale="  Best option.  ",
            alternatives_rejected=["  MySQL — rejected.  "],
            second_order_effects=["  Migration cost.  "],
        )
        assert d.topic_path == "/architecture/database"
        assert d.decision == "Use PostgreSQL."
        assert d.rationale == "Best option."

    def test_id_can_be_explicitly_provided(self) -> None:
        assert Decision(**MINIMAL_VALID, id="dec_explicit123456").id == "dec_explicit123456"


class TestAlternativesRejectedValidation:
    def test_empty_list_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Decision(**{**MINIMAL_VALID, "alternatives_rejected": []})
        assert any("alternatives_rejected" in str(e) for e in exc_info.value.errors())

    def test_missing_field_raises_validation_error(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "alternatives_rejected"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_single_item_list_accepted(self) -> None:
        d = Decision(**{**MINIMAL_VALID, "alternatives_rejected": ["Option X — rejected because Y."]})
        assert len(d.alternatives_rejected) == 1

    def test_multiple_item_list_accepted(self) -> None:
        d = Decision(**{**MINIMAL_VALID, "alternatives_rejected": ["A", "B", "C"]})
        assert len(d.alternatives_rejected) == 3

    def test_none_value_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "alternatives_rejected": None})

    def test_whitespace_only_alternative_rejected(self) -> None:
        """Whitespace-only items must be rejected (P0 fix).

        Without the per-item validator, ['  '] would pass min_length=1 and the
        anti-convergence gate would be satisfied without enumerating any real
        alternative.
        """
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "alternatives_rejected": ["   "]})

    def test_empty_string_alternative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "alternatives_rejected": [""]})

    def test_alternatives_stripped_in_place(self) -> None:
        """Surviving items have leading/trailing whitespace removed."""
        d = Decision(**{
            **MINIMAL_VALID,
            "alternatives_rejected": ["  MySQL — rejected.  "],
        })
        assert d.alternatives_rejected == ["MySQL — rejected."]

    def test_one_blank_one_real_rejected(self) -> None:
        """Even one blank entry among real ones causes rejection."""
        with pytest.raises(ValidationError):
            Decision(**{
                **MINIMAL_VALID,
                "alternatives_rejected": ["MySQL — rejected.", "   "],
            })


class TestSecondOrderEffectsValidation:
    def test_empty_list_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Decision(**{**MINIMAL_VALID, "second_order_effects": []})
        assert any("second_order_effects" in str(e) for e in exc_info.value.errors())

    def test_missing_field_raises_validation_error(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "second_order_effects"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_single_item_list_accepted(self) -> None:
        d = Decision(**{**MINIMAL_VALID, "second_order_effects": ["All teams must adopt SQL."]})
        assert len(d.second_order_effects) == 1

    def test_multiple_item_list_accepted(self) -> None:
        d = Decision(**{**MINIMAL_VALID, "second_order_effects": ["A", "B", "C", "D"]})
        assert len(d.second_order_effects) == 4

    def test_none_value_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "second_order_effects": None})

    def test_whitespace_only_effect_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "second_order_effects": ["   "]})

    def test_empty_string_effect_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "second_order_effects": [""]})

    def test_effects_stripped_in_place(self) -> None:
        d = Decision(**{
            **MINIMAL_VALID,
            "second_order_effects": ["  Migration cost.  "],
        })
        assert d.second_order_effects == ["Migration cost."]


class TestRequiredFieldValidation:
    def test_missing_topic_path_raises(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "topic_path"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_missing_decision_field_raises(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "decision"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_missing_rationale_raises(self) -> None:
        payload = {k: v for k, v in MINIMAL_VALID.items() if k != "rationale"}
        with pytest.raises(ValidationError):
            Decision(**payload)

    def test_none_topic_path_raises(self) -> None:
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "topic_path": None})

    def test_none_decision_raises(self) -> None:
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "decision": None})

    def test_none_rationale_raises(self) -> None:
        with pytest.raises(ValidationError):
            Decision(**{**MINIMAL_VALID, "rationale": None})

    def test_all_five_required_fields_present_succeeds(self) -> None:
        d = Decision(**MINIMAL_VALID)
        assert d.topic_path is not None
        assert d.decision is not None
        assert d.rationale is not None
        assert d.alternatives_rejected is not None
        assert d.second_order_effects is not None
