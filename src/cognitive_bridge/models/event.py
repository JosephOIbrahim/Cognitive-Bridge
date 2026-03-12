"""Event model — immutable entries in the append-only audit log."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    EventType,
    _new_id,
    _now_utc,
)


class Event(BaseModel):
    """Immutable event in the audit log.

    Events are never modified or deleted. They form an append-only provenance
    trail for every mutation that occurs in the composition stage.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: _new_id("evt"))
    event_type: EventType
    timestamp: datetime = Field(default_factory=_now_utc)
    actor: AssertionAuthor
    target_id: str
    detail: dict[str, Any] = Field(default_factory=dict)
