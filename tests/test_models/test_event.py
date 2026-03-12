"""Tests for the Event model."""

from datetime import datetime, timezone

import pytest

from cognitive_bridge.models.arcs import AssertionAuthor, EventType
from cognitive_bridge.models.event import Event


def _make_event(**kwargs) -> Event:
    """Return a minimal valid Event, merging any overrides."""
    defaults = dict(
        event_type=EventType.ASSERTION_CREATED,
        actor=AssertionAuthor.AI,
        target_id="ast_aaaaaaaaaaaa",
    )
    defaults.update(kwargs)
    return Event(**defaults)


class TestEventConstruction:
    """Basic construction with required fields."""

    def test_minimal_construction(self) -> None:
        e = _make_event()
        assert e.event_type == EventType.ASSERTION_CREATED
        assert e.actor == AssertionAuthor.AI
        assert e.target_id == "ast_aaaaaaaaaaaa"

    def test_id_auto_generated_with_evt_prefix(self) -> None:
        e = _make_event()
        assert e.id.startswith("evt_")
        assert len(e.id) == 4 + 12  # "evt_" + 12 hex chars

    def test_id_uniqueness(self) -> None:
        ids = {_make_event().id for _ in range(50)}
        assert len(ids) == 50

    def test_timestamp_auto_generated(self) -> None:
        e = _make_event()
        assert isinstance(e.timestamp, datetime)

    def test_timestamp_is_utc_aware(self) -> None:
        e = _make_event()
        assert e.timestamp.tzinfo is not None
        assert e.timestamp.tzinfo == timezone.utc


class TestEventDefaults:
    """Default field values."""

    def test_detail_defaults_to_empty_dict(self) -> None:
        e = _make_event()
        assert e.detail == {}

    def test_detail_is_independent_per_instance(self) -> None:
        """Two events must not share the same detail dict."""
        e1 = _make_event()
        e2 = _make_event()
        e1.detail["key"] = "value"
        assert "key" not in e2.detail


class TestEventDetail:
    """Detail field accepts arbitrary dict content."""

    def test_detail_accepts_nested_data(self) -> None:
        e = _make_event(
            detail={
                "arc": "LOCAL",
                "confidence": 0.95,
                "topic_path": "/architecture/database/engine",
                "metadata": {"source": "benchmark"},
            }
        )
        assert e.detail["arc"] == "LOCAL"
        assert e.detail["confidence"] == pytest.approx(0.95)
        assert e.detail["metadata"]["source"] == "benchmark"

    def test_detail_accepts_list_values(self) -> None:
        e = _make_event(detail={"paths": ["/a", "/b", "/c"]})
        assert e.detail["paths"] == ["/a", "/b", "/c"]


class TestEventTypes:
    """Events accept all EventType values."""

    def test_all_event_types_accepted(self) -> None:
        for event_type in EventType:
            e = _make_event(event_type=event_type)
            assert e.event_type == event_type

    def test_v3_cascading_event_type(self) -> None:
        e = _make_event(event_type=EventType.ASSERTION_FALSIFIED)
        assert e.event_type == EventType.ASSERTION_FALSIFIED


class TestEventActors:
    """Events accept all AssertionAuthor values."""

    def test_all_actors_accepted(self) -> None:
        for actor in AssertionAuthor:
            e = _make_event(actor=actor)
            assert e.actor == actor

    def test_user_actor(self) -> None:
        e = _make_event(actor=AssertionAuthor.USER)
        assert e.actor == AssertionAuthor.USER

    def test_system_actor(self) -> None:
        e = _make_event(actor=AssertionAuthor.SYSTEM)
        assert e.actor == AssertionAuthor.SYSTEM
