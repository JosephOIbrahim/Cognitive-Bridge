"""Tests for models/event.py — Event immutable audit log entry.

Blueprint reference: Section 3.7 (Event log types) and Section 4.4 (Provenance engine).
Constitution rule C8 (append-only event log), G2 (validator-rejection symmetry).

Events are effectively immutable in practice. The model uses frozen=False (Pydantic
default) but the stage protocol never mutates events after creation.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cognitive_bridge.models.arcs import AssertionAuthor, EventType
from cognitive_bridge.models.event import Event

_TS = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_event(**overrides) -> Event:
    defaults = dict(
        id="evt_aabbccddeeff",
        event_type=EventType.ASSERTION_CREATED,
        timestamp=_TS,
        actor=AssertionAuthor.AI,
        target_id="ast_112233445566",
        detail={"message": "test event"},
    )
    defaults.update(overrides)
    return Event(**defaults)


class TestEventConstruction:
    def test_basic_construction_succeeds(self) -> None:
        e = _make_event()
        assert e.event_type == EventType.ASSERTION_CREATED
        assert e.actor == AssertionAuthor.AI
        assert e.target_id == "ast_112233445566"

    def test_id_prefix_evt(self) -> None:
        e = Event(event_type=EventType.CONFLICT_DETECTED, actor=AssertionAuthor.SYSTEM, target_id="cfl_aabbccddeeff")
        assert e.id.startswith("evt_")
        assert len(e.id) == 16

    def test_id_uniqueness(self) -> None:
        ids = {
            Event(event_type=EventType.ASSERTION_CREATED, actor=AssertionAuthor.AI, target_id="ast_111111111111").id
            for _ in range(30)
        }
        assert len(ids) == 30

    def test_timestamp_is_timezone_aware_utc(self) -> None:
        e = Event(event_type=EventType.ASSERTION_CREATED, actor=AssertionAuthor.AI, target_id="ast_111111111111")
        assert e.timestamp.tzinfo == timezone.utc

    def test_timestamp_explicit_value_stored(self) -> None:
        assert _make_event(timestamp=_TS).timestamp == _TS

    def test_detail_defaults_to_empty_dict(self) -> None:
        e = Event(event_type=EventType.ASSERTION_CREATED, actor=AssertionAuthor.AI, target_id="ast_111111111111")
        assert e.detail == {}

    def test_detail_custom_dict_stored(self) -> None:
        detail = {"key": "value", "count": 42}
        assert _make_event(detail=detail).detail == detail

    def test_explicit_id_accepted(self) -> None:
        assert _make_event(id="evt_custom123456").id == "evt_custom123456"


class TestEventTypeAcceptance:
    @pytest.mark.parametrize("et", list(EventType))
    def test_each_event_type_accepted(self, et: EventType) -> None:
        e = _make_event(event_type=et)
        assert e.event_type == et
        assert isinstance(e.event_type, EventType)

    def test_invalid_event_type_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_event(event_type="not_a_real_event_type")

    def test_none_event_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_event(event_type=None)


class TestActorAcceptance:
    @pytest.mark.parametrize("author", list(AssertionAuthor))
    def test_each_author_accepted_as_actor(self, author: AssertionAuthor) -> None:
        e = _make_event(actor=author)
        assert e.actor == author
        assert isinstance(e.actor, AssertionAuthor)

    def test_invalid_actor_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_event(actor="not_a_valid_author")

    def test_none_actor_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_event(actor=None)


class TestDetailDictContent:
    def test_string_value_in_detail(self) -> None:
        assert _make_event(detail={"msg": "hello world"}).detail["msg"] == "hello world"

    def test_int_value_in_detail(self) -> None:
        assert _make_event(detail={"count": 42}).detail["count"] == 42

    def test_float_value_in_detail(self) -> None:
        assert _make_event(detail={"score": 0.95}).detail["score"] == 0.95

    def test_bool_value_in_detail(self) -> None:
        e = _make_event(detail={"active": True, "retracted": False})
        assert e.detail["active"] is True
        assert e.detail["retracted"] is False

    def test_none_value_in_detail(self) -> None:
        assert _make_event(detail={"nullable": None}).detail["nullable"] is None

    def test_nested_dict_in_detail(self) -> None:
        assert _make_event(detail={"nested": {"inner_key": "inner_value"}}).detail["nested"] == {"inner_key": "inner_value"}

    def test_nested_list_in_detail(self) -> None:
        assert _make_event(detail={"items": [1, "two", 3.0, True, None]}).detail["items"] == [1, "two", 3.0, True, None]

    def test_all_mixed_types_together(self) -> None:
        detail = {
            "str_field": "hello", "int_field": 7, "float_field": 3.14,
            "bool_field": False, "none_field": None,
            "nested_dict": {"key": "val"}, "nested_list": [1, 2, 3],
        }
        assert _make_event(detail=detail).detail == detail

    def test_empty_detail_dict_accepted(self) -> None:
        assert _make_event(detail={}).detail == {}


class TestRequiredFieldRejection:
    def test_missing_event_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            Event(actor=AssertionAuthor.AI, target_id="ast_111111111111")

    def test_missing_actor_raises(self) -> None:
        with pytest.raises(ValidationError):
            Event(event_type=EventType.ASSERTION_CREATED, target_id="ast_111111111111")

    def test_missing_target_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Event(event_type=EventType.ASSERTION_CREATED, actor=AssertionAuthor.AI)

    def test_none_event_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            Event(event_type=None, actor=AssertionAuthor.AI, target_id="ast_111111111111")

    def test_none_actor_raises(self) -> None:
        with pytest.raises(ValidationError):
            Event(event_type=EventType.ASSERTION_CREATED, actor=None, target_id="ast_111111111111")

    def test_none_target_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            Event(event_type=EventType.ASSERTION_CREATED, actor=AssertionAuthor.AI, target_id=None)


class TestSerializationStability:
    def test_model_dump_consistent(self) -> None:
        e = _make_event()
        assert e.model_dump() == e.model_dump()

    def test_all_expected_fields_in_dump(self) -> None:
        dumped = _make_event().model_dump()
        expected_keys = {"id", "event_type", "timestamp", "actor", "target_id", "detail"}
        assert expected_keys.issubset(set(dumped.keys()))

    def test_field_access_is_stable(self) -> None:
        e = _make_event(detail={"x": 1})
        assert e.event_type == EventType.ASSERTION_CREATED
        assert e.event_type == EventType.ASSERTION_CREATED
        assert e.detail == {"x": 1}
        assert e.detail == {"x": 1}

    def test_event_type_count_matches_parametrized_tests(self) -> None:
        all_types = list(EventType)
        assert len(all_types) >= 16
