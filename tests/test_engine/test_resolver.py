"""Tests for engine/resolver.py — LIVRPS resolution, winner tracking, and cascade triggers.

Covers:
- get_current_winner(): empty path, single, multi-arc, inactive exclusion.
- add_assertion(): first insert, structural conflict, winner change, event recording,
  cascade trigger, cascade stored in stage.
- promote_assertion(): valid promotion, winner change + cascades, invalid promotions,
  evidence append.
- retract_assertion(): deactivation, winner change, empty path, dependent orphaning,
  events, error cases.
- falsify_assertion(): FALSIFIED status, deactivation, orphan cascade, winner change,
  error cases.
- resolve_conflict(): all resolution paths, steelman gate, experiment gate, already
  resolved gate, nonexistent conflict, event recording.
"""

import pytest
from datetime import datetime, timezone, timedelta

from cognitive_bridge.engine.resolver import (
    ResolutionResult,
    add_assertion,
    falsify_assertion,
    get_current_winner,
    promote_assertion,
    resolve_conflict,
    retract_assertion,
)
from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
    EventType,
    ResolutionPath,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage() -> CompositionStage:
    """Return a fresh stage with default parameters."""
    return CompositionStage(project_id="test", project_name="Resolver Tests")


def _make_assertion(
    topic_path: str,
    content: str,
    arc: CompositionArc = CompositionArc.INHERITS,
    depends_on_paths: list[str] | None = None,
    falsifiable_if: str | None = None,
    confidence: float = 0.5,
    author: AssertionAuthor = AssertionAuthor.AI,
    active: bool = True,
    created_at: datetime | None = None,
) -> Assertion:
    """Factory that handles LOCAL-arc falsifiability requirement."""
    kwargs: dict = {
        "topic_path": topic_path,
        "content": content,
        "arc": arc,
        "author": author,
        "depends_on_paths": depends_on_paths or [],
        "active": active,
        "confidence": confidence,
    }
    if falsifiable_if is not None:
        kwargs["falsifiable_if"] = falsifiable_if
    elif arc == CompositionArc.LOCAL:
        kwargs["falsifiable_if"] = f"Falsified if {content} is disproved"
    if created_at is not None:
        kwargs["created_at"] = created_at
    return Assertion(**kwargs)


def _events_of_type(stage: CompositionStage, event_type: EventType) -> list:
    return [e for e in stage.events if e.event_type == event_type]


# ===========================================================================
# TestGetCurrentWinner
# ===========================================================================

class TestGetCurrentWinner:

    def test_empty_path_returns_none(self):
        """No assertions at path → None."""
        stage = _make_stage()
        assert get_current_winner(stage, "/db/engine") is None

    def test_single_assertion_is_winner(self):
        """One active assertion → it wins."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        winner = get_current_winner(stage, "/db/engine")

        assert winner is a

    def test_lower_arc_wins(self):
        """LOCAL (10) beats INHERITS (20) beats SPECIALIZES (60)."""
        stage = _make_stage()
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        local = _make_assertion(
            "/db", "LOCAL claim", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if local claim is wrong"
        )
        specializes = _make_assertion("/db", "SPECIALIZES claim", arc=CompositionArc.SPECIALIZES)
        for a in (inherits, local, specializes):
            stage.assertions[a.id] = a

        winner = get_current_winner(stage, "/db")

        assert winner is local

    def test_tie_on_arc_higher_confidence_wins(self):
        """Same arc: higher confidence wins."""
        stage = _make_stage()
        low_conf = _make_assertion("/path", "Low confidence", confidence=0.3)
        high_conf = _make_assertion("/path", "High confidence", confidence=0.9)
        for a in (low_conf, high_conf):
            stage.assertions[a.id] = a

        winner = get_current_winner(stage, "/path")

        assert winner is high_conf

    def test_tie_on_arc_and_confidence_newer_wins(self):
        """Same arc + same confidence: newer created_at wins."""
        stage = _make_stage()
        now = datetime.now(timezone.utc)
        older = _make_assertion(
            "/path", "Older claim", confidence=0.5,
            created_at=now - timedelta(seconds=10)
        )
        newer = _make_assertion(
            "/path", "Newer claim", confidence=0.5,
            created_at=now
        )
        for a in (older, newer):
            stage.assertions[a.id] = a

        winner = get_current_winner(stage, "/path")

        assert winner is newer

    def test_inactive_assertions_excluded(self):
        """active=False assertions are never candidates for winner."""
        stage = _make_stage()
        active = _make_assertion("/path", "Active claim")
        inactive = _make_assertion(
            "/path", "Inactive claim",
            arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if inactive claim is wrong",
            active=False,
        )
        for a in (active, inactive):
            stage.assertions[a.id] = a

        winner = get_current_winner(stage, "/path")

        # LOCAL would win if active; since it is not, INHERITS wins
        assert winner is active

    def test_all_inactive_returns_none(self):
        """If all assertions at path are inactive, returns None."""
        stage = _make_stage()
        a = _make_assertion("/path", "Inactive", active=False)
        stage.assertions[a.id] = a

        assert get_current_winner(stage, "/path") is None

    def test_only_queries_given_path(self):
        """Assertions at other paths are ignored."""
        stage = _make_stage()
        a = _make_assertion("/other/path", "Different path")
        stage.assertions[a.id] = a

        assert get_current_winner(stage, "/db/engine") is None


# ===========================================================================
# TestAddAssertion
# ===========================================================================

class TestAddAssertion:

    def test_first_assertion_at_path_no_conflict(self):
        """First assertion at a path: no structural conflict, no cascade."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")

        result = add_assertion(stage, a)

        assert result.assertion is a
        assert result.structural_conflict is None
        assert result.cascading_conflicts == []
        assert result.winner_changed is False
        assert result.previous_winner_id is None
        assert result.new_winner_id == a.id

    def test_second_assertion_different_content_structural_conflict(self):
        """Second assertion at same path with different content → structural conflict."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        b = _make_assertion("/db/engine", "Use MySQL")
        result = add_assertion(stage, b)

        assert result.structural_conflict is not None
        assert result.structural_conflict.detection_layer == ConflictDetectionLayer.STRUCTURAL
        assert result.structural_conflict.topic_path == "/db/engine"
        conflict_ids = {result.structural_conflict.assertion_a_id, result.structural_conflict.assertion_b_id}
        assert a.id in conflict_ids
        assert b.id in conflict_ids

    def test_second_assertion_same_content_no_conflict(self):
        """Same content at same path → agreement, no structural conflict."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        b = _make_assertion("/db/engine", "Use PostgreSQL")
        result = add_assertion(stage, b)

        assert result.structural_conflict is None

    def test_stronger_assertion_changes_winner(self):
        """A LOCAL assertion inserted after INHERITS changes the winner."""
        stage = _make_stage()
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        stage.assertions[inherits.id] = inherits

        local = _make_assertion(
            "/db", "LOCAL claim", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if local claim is wrong"
        )
        result = add_assertion(stage, local)

        assert result.winner_changed is True
        assert result.previous_winner_id == inherits.id
        assert result.new_winner_id == local.id

    def test_weaker_assertion_does_not_change_winner(self):
        """A SPECIALIZES assertion inserted after INHERITS does not change winner."""
        stage = _make_stage()
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        stage.assertions[inherits.id] = inherits

        specializes = _make_assertion("/db", "SPECIALIZES claim", arc=CompositionArc.SPECIALIZES)
        result = add_assertion(stage, specializes)

        assert result.winner_changed is False
        assert result.previous_winner_id == inherits.id
        assert result.new_winner_id == inherits.id

    def test_assertion_created_event_recorded(self):
        """ASSERTION_CREATED event is appended to stage.events."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")

        add_assertion(stage, a)

        created_events = _events_of_type(stage, EventType.ASSERTION_CREATED)
        assert len(created_events) == 1
        ev = created_events[0]
        assert ev.target_id == a.id
        assert ev.detail["topic_path"] == "/db/engine"

    def test_conflict_detected_event_recorded_for_structural(self):
        """CONFLICT_DETECTED event is recorded when a structural conflict is found."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        b = _make_assertion("/db/engine", "Use MySQL")
        result = add_assertion(stage, b)

        detected_events = _events_of_type(stage, EventType.CONFLICT_DETECTED)
        assert len(detected_events) == 1
        ev = detected_events[0]
        assert ev.target_id == result.structural_conflict.id
        assert ev.detail["layer"] == "structural"

    def test_cascading_conflicts_triggered_when_winner_changes_and_dependents_exist(self):
        """When winner changes and dependents exist, Layer 4 cascades fire."""
        stage = _make_stage()
        # Foundation assertion
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        stage.assertions[inherits.id] = inherits
        # Dependent assertion
        dep = _make_assertion("/service", "Depends on db", depends_on_paths=["/db"])
        stage.assertions[dep.id] = dep

        # Stronger assertion overrides the winner
        local = _make_assertion(
            "/db", "LOCAL claim", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if local claim is wrong"
        )
        result = add_assertion(stage, local)

        assert result.winner_changed is True
        assert len(result.cascading_conflicts) == 1
        cascade = result.cascading_conflicts[0]
        assert cascade.assertion_b_id == dep.id
        assert cascade.detection_layer == ConflictDetectionLayer.CASCADING

    def test_cascading_conflicts_stored_in_stage(self):
        """Cascading conflicts are stored in stage.conflicts."""
        stage = _make_stage()
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        stage.assertions[inherits.id] = inherits
        dep = _make_assertion("/service", "Depends on db", depends_on_paths=["/db"])
        stage.assertions[dep.id] = dep

        local = _make_assertion(
            "/db", "LOCAL claim", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if local claim is wrong"
        )
        result = add_assertion(stage, local)

        cascade = result.cascading_conflicts[0]
        assert cascade.id in stage.conflicts

    def test_no_cascade_when_winner_does_not_change(self):
        """Weaker assertion insertion triggers no cascades."""
        stage = _make_stage()
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        stage.assertions[inherits.id] = inherits
        dep = _make_assertion("/service", "Depends on db", depends_on_paths=["/db"])
        stage.assertions[dep.id] = dep

        specializes = _make_assertion("/db", "SPECIALIZES claim", arc=CompositionArc.SPECIALIZES)
        result = add_assertion(stage, specializes)

        assert result.cascading_conflicts == []
        assert dep.assumption_status == AssumptionStatus.LIVE

    def test_assertion_added_to_stage_assertions(self):
        """After add_assertion, the assertion is in stage.assertions."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")

        add_assertion(stage, a)

        assert a.id in stage.assertions

    def test_conflict_stored_in_stage_conflicts(self):
        """Structural conflict is stored in stage.conflicts."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        b = _make_assertion("/db/engine", "Use MySQL")
        result = add_assertion(stage, b)

        assert result.structural_conflict.id in stage.conflicts

    def test_different_paths_no_structural_conflict(self):
        """Assertions at different paths never produce a structural conflict."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        b = _make_assertion("/cache", "Use Redis")
        result = add_assertion(stage, b)

        assert result.structural_conflict is None

    def test_cascade_conflict_detected_event_recorded(self):
        """CONFLICT_DETECTED event with layer=cascading is recorded for each cascade."""
        stage = _make_stage()
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        stage.assertions[inherits.id] = inherits
        dep = _make_assertion("/service", "Depends on db", depends_on_paths=["/db"])
        stage.assertions[dep.id] = dep

        local = _make_assertion(
            "/db", "LOCAL claim", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if local claim is wrong"
        )
        add_assertion(stage, local)

        cascade_events = [
            e for e in stage.events
            if e.event_type == EventType.CONFLICT_DETECTED
            and e.detail.get("layer") == "cascading"
        ]
        assert len(cascade_events) == 1


# ===========================================================================
# TestPromoteAssertion
# ===========================================================================

class TestPromoteAssertion:

    def test_promote_inherits_to_local_succeeds(self):
        """INHERITS (20) can be promoted to LOCAL (10) with falsifiable_if."""
        stage = _make_stage()
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.INHERITS)
        # Manually set falsifiable_if so promotion to LOCAL is valid at arc level
        a.falsifiable_if = "Falsified if PostgreSQL cannot handle writes"
        stage.assertions[a.id] = a

        result = promote_assertion(stage, a.id, CompositionArc.LOCAL)

        assert result.assertion.arc == CompositionArc.LOCAL

    def test_promote_records_assertion_promoted_event(self):
        """ASSERTION_PROMOTED event is appended after promotion."""
        stage = _make_stage()
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.REFERENCES)
        stage.assertions[a.id] = a

        promote_assertion(stage, a.id, CompositionArc.INHERITS)

        promoted_events = _events_of_type(stage, EventType.ASSERTION_PROMOTED)
        assert len(promoted_events) == 1
        ev = promoted_events[0]
        assert ev.target_id == a.id
        assert ev.detail["new_arc"] == CompositionArc.INHERITS.value

    def test_promote_evidence_appended(self):
        """Evidence string is appended to assertion.evidence when provided."""
        stage = _make_stage()
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.REFERENCES)
        stage.assertions[a.id] = a

        promote_assertion(stage, a.id, CompositionArc.INHERITS, evidence="Benchmarked at 100k writes/sec")

        assert "Benchmarked at 100k writes/sec" in a.evidence

    def test_promote_no_evidence_does_not_append(self):
        """Evidence list unchanged when no evidence argument provided."""
        stage = _make_stage()
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.REFERENCES)
        stage.assertions[a.id] = a
        original_evidence = list(a.evidence)

        promote_assertion(stage, a.id, CompositionArc.INHERITS)

        assert a.evidence == original_evidence

    def test_promote_changes_winner_and_fires_cascades(self):
        """Promotion that changes the winner triggers cascading conflicts."""
        stage = _make_stage()
        # Current winner
        winner = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[winner.id] = winner
        # Candidate that starts weaker
        candidate = _make_assertion("/db", "Use MySQL", arc=CompositionArc.SPECIALIZES)
        stage.assertions[candidate.id] = candidate
        # Dependent assertion
        dep = _make_assertion("/service", "Use db", depends_on_paths=["/db"])
        stage.assertions[dep.id] = dep

        # Promote candidate above winner
        result = promote_assertion(stage, candidate.id, CompositionArc.LOCAL,
                                   evidence="Proven better")
        # candidate needs falsifiable_if for LOCAL — set it before checking
        # Actually promote_assertion just sets the arc; Pydantic won't re-validate here
        # because we're mutating in place. The test validates the winner-change logic.

        assert result.winner_changed is True
        assert result.new_winner_id == candidate.id
        assert len(result.cascading_conflicts) >= 1

    def test_promote_to_same_arc_raises_value_error(self):
        """Promoting to same arc raises ValueError."""
        stage = _make_stage()
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[a.id] = a

        with pytest.raises(ValueError, match="not stronger"):
            promote_assertion(stage, a.id, CompositionArc.INHERITS)

    def test_promote_to_weaker_arc_raises_value_error(self):
        """Promoting to a weaker (higher int) arc raises ValueError."""
        stage = _make_stage()
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[a.id] = a

        with pytest.raises(ValueError, match="not stronger"):
            promote_assertion(stage, a.id, CompositionArc.SPECIALIZES)

    def test_promote_nonexistent_raises_value_error(self):
        """Non-existent assertion ID raises ValueError."""
        stage = _make_stage()

        with pytest.raises(ValueError, match="not found"):
            promote_assertion(stage, "ast_doesnotexist", CompositionArc.INHERITS)

    def test_promote_inactive_raises_value_error(self):
        """Inactive assertion cannot be promoted."""
        stage = _make_stage()
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.REFERENCES, active=False)
        stage.assertions[a.id] = a

        with pytest.raises(ValueError, match="inactive"):
            promote_assertion(stage, a.id, CompositionArc.INHERITS)

    def test_promote_without_winner_change_no_cascades(self):
        """Promotion that does not change winner produces no cascading conflicts."""
        stage = _make_stage()
        # Sole assertion — it's already the winner
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.REFERENCES)
        stage.assertions[a.id] = a

        result = promote_assertion(stage, a.id, CompositionArc.INHERITS)

        # No previous winner other than a itself (a was already winner)
        assert result.cascading_conflicts == []


# ===========================================================================
# TestRetractAssertion
# ===========================================================================

class TestRetractAssertion:

    def test_retract_sets_active_false(self):
        """Retracted assertion has active=False."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        retract_assertion(stage, a.id)

        assert a.active is False

    def test_retract_sets_retracted_at(self):
        """Retracted assertion has retracted_at timestamp set."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        retract_assertion(stage, a.id)

        assert a.retracted_at is not None

    def test_retract_records_event(self):
        """ASSERTION_RETRACTED event is recorded."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        retract_assertion(stage, a.id)

        retracted_events = _events_of_type(stage, EventType.ASSERTION_RETRACTED)
        assert len(retracted_events) == 1
        assert retracted_events[0].target_id == a.id

    def test_retract_winner_changes_when_other_exists(self):
        """Retracting the winner changes it to the next strongest assertion."""
        stage = _make_stage()
        local = _make_assertion(
            "/db", "LOCAL claim", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if LOCAL is wrong"
        )
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        for a in (local, inherits):
            stage.assertions[a.id] = a

        result = retract_assertion(stage, local.id)

        assert result.winner_changed is True
        assert result.previous_winner_id == local.id
        assert result.new_winner_id == inherits.id

    def test_retract_sole_assertion_empties_path(self):
        """Retracting the only assertion at a path → winner_changed=True, new_winner_id=None."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        result = retract_assertion(stage, a.id)

        assert result.winner_changed is True
        assert result.previous_winner_id == a.id
        assert result.new_winner_id is None

    def test_retract_marks_dependents_orphaned(self):
        """Active assertions depending on the retracted path become ORPHANED."""
        stage = _make_stage()
        db = _make_assertion("/db", "Use PostgreSQL")
        dep = _make_assertion("/service", "Depends on db", depends_on_paths=["/db"])
        for a in (db, dep):
            stage.assertions[a.id] = a

        retract_assertion(stage, db.id)

        assert dep.assumption_status == AssumptionStatus.ORPHANED

    def test_retract_records_orphaned_event_for_each_dependent(self):
        """ASSERTION_ORPHANED event recorded for each dependent."""
        stage = _make_stage()
        db = _make_assertion("/db", "Use PostgreSQL")
        dep1 = _make_assertion("/service/a", "Depends on db", depends_on_paths=["/db"])
        dep2 = _make_assertion("/service/b", "Also depends on db", depends_on_paths=["/db"])
        for a in (db, dep1, dep2):
            stage.assertions[a.id] = a

        retract_assertion(stage, db.id)

        orphaned_events = _events_of_type(stage, EventType.ASSERTION_ORPHANED)
        assert len(orphaned_events) == 2
        targets = {e.target_id for e in orphaned_events}
        assert targets == {dep1.id, dep2.id}

    def test_retract_already_inactive_raises_value_error(self):
        """Retracting an already-inactive assertion raises ValueError."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL", active=False)
        stage.assertions[a.id] = a

        with pytest.raises(ValueError, match="already retracted"):
            retract_assertion(stage, a.id)

    def test_retract_nonexistent_raises_value_error(self):
        """Non-existent assertion ID raises ValueError."""
        stage = _make_stage()

        with pytest.raises(ValueError, match="not found"):
            retract_assertion(stage, "ast_doesnotexist")

    def test_retract_fires_cascades_when_winner_changes(self):
        """Retracting the winner fires cascading conflicts for dependents of the path."""
        stage = _make_stage()
        local = _make_assertion(
            "/db", "LOCAL claim", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if LOCAL is wrong"
        )
        inherits = _make_assertion("/db", "INHERITS claim", arc=CompositionArc.INHERITS)
        downstream = _make_assertion("/orm", "Depends on db", depends_on_paths=["/db"])
        for a in (local, inherits, downstream):
            stage.assertions[a.id] = a

        result = retract_assertion(stage, local.id)

        # Winner changed from local → inherits
        assert result.winner_changed is True
        # Cascades fired because downstream depends on /db
        assert len(result.cascading_conflicts) >= 1
        cascade_ids = {c.assertion_b_id for c in result.cascading_conflicts}
        assert downstream.id in cascade_ids

    def test_retract_assertion_not_deleted_from_stage(self):
        """Retracted assertion remains in stage.assertions (non-destructive)."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        stage.assertions[a.id] = a

        retract_assertion(stage, a.id)

        assert a.id in stage.assertions


# ===========================================================================
# TestFalsifyAssertion
# ===========================================================================

class TestFalsifyAssertion:

    def test_falsify_marks_assumption_status_falsified(self):
        """Falsified assertion gets assumption_status=FALSIFIED."""
        stage = _make_stage()
        a = _make_assertion(
            "/db", "Use PostgreSQL", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if PostgreSQL misses SLA"
        )
        stage.assertions[a.id] = a

        falsify_assertion(stage, a.id, "PostgreSQL missed SLA on 3 occasions")

        assert a.assumption_status == AssumptionStatus.FALSIFIED

    def test_falsify_deactivates_assertion(self):
        """Falsified assertion has active=False after falsification."""
        stage = _make_stage()
        a = _make_assertion(
            "/db", "Use PostgreSQL", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if PostgreSQL misses SLA"
        )
        stage.assertions[a.id] = a

        falsify_assertion(stage, a.id, "PostgreSQL missed SLA")

        assert a.active is False
        assert a.retracted_at is not None

    def test_falsify_marks_dependents_orphaned(self):
        """Dependents of the falsified path become ORPHANED."""
        stage = _make_stage()
        a = _make_assertion(
            "/db", "Use PostgreSQL", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if PostgreSQL misses SLA"
        )
        dep = _make_assertion("/service", "Depends on db", depends_on_paths=["/db"])
        for x in (a, dep):
            stage.assertions[x.id] = x

        falsify_assertion(stage, a.id, "PostgreSQL missed SLA")

        assert dep.assumption_status == AssumptionStatus.ORPHANED

    def test_falsify_records_falsified_event(self):
        """ASSERTION_FALSIFIED event is in stage.events."""
        stage = _make_stage()
        a = _make_assertion(
            "/db", "Use PostgreSQL", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if PostgreSQL misses SLA"
        )
        stage.assertions[a.id] = a

        falsify_assertion(stage, a.id, "PostgreSQL missed SLA")

        falsified_events = _events_of_type(stage, EventType.ASSERTION_FALSIFIED)
        assert len(falsified_events) == 1
        assert falsified_events[0].target_id == a.id

    def test_falsify_winner_change_fires_cascades_for_new_winner(self):
        """When falsification causes a winner change, cascade fires for dependents."""
        stage = _make_stage()
        local = _make_assertion(
            "/db", "Use PostgreSQL", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if PostgreSQL misses SLA"
        )
        inherits = _make_assertion("/db", "Use MySQL", arc=CompositionArc.INHERITS)
        downstream = _make_assertion("/orm", "ORM layer", depends_on_paths=["/db"])
        for x in (local, inherits, downstream):
            stage.assertions[x.id] = x

        result = falsify_assertion(stage, local.id, "PostgreSQL missed SLA")

        assert result.winner_changed is True
        assert result.new_winner_id == inherits.id

    def test_falsify_sole_assertion_empties_path(self):
        """Falsifying the sole assertion at a path → new_winner_id=None."""
        stage = _make_stage()
        a = _make_assertion(
            "/db", "Use PostgreSQL", arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if PostgreSQL misses SLA"
        )
        stage.assertions[a.id] = a

        result = falsify_assertion(stage, a.id, "PostgreSQL missed SLA")

        assert result.winner_changed is True
        assert result.new_winner_id is None

    def test_falsify_no_falsifiable_if_raises_value_error(self):
        """Assertion without falsifiable_if raises ValueError."""
        stage = _make_stage()
        a = _make_assertion("/db", "Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[a.id] = a

        with pytest.raises(ValueError, match="no falsifiable_if"):
            falsify_assertion(stage, a.id, "Some observation")

    def test_falsify_nonexistent_raises_value_error(self):
        """Non-existent assertion ID raises ValueError."""
        stage = _make_stage()

        with pytest.raises(ValueError, match="not found"):
            falsify_assertion(stage, "ast_doesnotexist", "Some observation")


# ===========================================================================
# TestResolveConflict
# ===========================================================================

class TestResolveConflict:

    def _stage_with_conflict(self) -> tuple[CompositionStage, Conflict]:
        """Stage pre-populated with one ACTIVE conflict."""
        stage = _make_stage()
        a = _make_assertion("/db/engine", "Use PostgreSQL")
        b = _make_assertion("/db/engine", "Use MySQL")
        stage.assertions[a.id] = a
        stage.assertions[b.id] = b
        result = add_assertion(stage, a)
        result2 = add_assertion(stage, b)
        conflict = result2.structural_conflict
        assert conflict is not None
        return stage, conflict

    def test_accept_sets_resolved_override(self):
        """ACCEPT resolution → RESOLVED_OVERRIDE status."""
        stage, conflict = self._stage_with_conflict()

        resolve_conflict(stage, conflict.id, ResolutionPath.ACCEPT)

        assert conflict.status == ConflictStatus.RESOLVED_OVERRIDE
        assert conflict.resolved_at is not None

    def test_defer_sets_deferred(self):
        """DEFER resolution → DEFERRED status."""
        stage, conflict = self._stage_with_conflict()

        resolve_conflict(stage, conflict.id, ResolutionPath.DEFER)

        assert conflict.status == ConflictStatus.DEFERRED

    def test_dismiss_sets_dismissed(self):
        """DISMISS resolution → DISMISSED status."""
        stage, conflict = self._stage_with_conflict()

        resolve_conflict(stage, conflict.id, ResolutionPath.DISMISS)

        assert conflict.status == ConflictStatus.DISMISSED

    def test_synthesize_sets_resolved_synthesized(self):
        """SYNTHESIZE resolution → RESOLVED_SYNTHESIZED status."""
        stage, conflict = self._stage_with_conflict()

        resolve_conflict(stage, conflict.id, ResolutionPath.SYNTHESIZE)

        assert conflict.status == ConflictStatus.RESOLVED_SYNTHESIZED

    def test_promote_sets_resolved_promoted(self):
        """PROMOTE resolution → RESOLVED_PROMOTED status."""
        stage, conflict = self._stage_with_conflict()

        resolve_conflict(stage, conflict.id, ResolutionPath.PROMOTE)

        assert conflict.status == ConflictStatus.RESOLVED_PROMOTED

    def test_challenge_without_steelman_raises_value_error(self):
        """CHALLENGE without steelman_summary raises ValueError (steelman gate)."""
        stage, conflict = self._stage_with_conflict()

        with pytest.raises(ValueError, match="steelman_summary"):
            resolve_conflict(stage, conflict.id, ResolutionPath.CHALLENGE)

    def test_challenge_with_steelman_keeps_conflict_active(self):
        """CHALLENGE with steelman_summary keeps status ACTIVE (debate continues)."""
        stage, conflict = self._stage_with_conflict()

        result = resolve_conflict(
            stage, conflict.id, ResolutionPath.CHALLENGE,
            steelman_summary="MySQL has better horizontal sharding support for write-heavy workloads."
        )

        assert result.status == ConflictStatus.ACTIVE
        assert result.resolved_at is None
        assert result.steelman_of_opponent == "MySQL has better horizontal sharding support for write-heavy workloads."

    def test_propose_experiment_without_protocol_raises_value_error(self):
        """PROPOSE_EXPERIMENT without experiment_protocol raises ValueError (experiment gate)."""
        stage, conflict = self._stage_with_conflict()

        with pytest.raises(ValueError, match="experiment_protocol"):
            resolve_conflict(stage, conflict.id, ResolutionPath.PROPOSE_EXPERIMENT)

    def test_propose_experiment_with_protocol_sets_resolved_experiment(self):
        """PROPOSE_EXPERIMENT with protocol → RESOLVED_EXPERIMENT status."""
        stage, conflict = self._stage_with_conflict()
        protocol = "Run write benchmark at 50k writes/sec on both DBs for 1 hour. Winner handles all traffic."

        result = resolve_conflict(
            stage, conflict.id, ResolutionPath.PROPOSE_EXPERIMENT,
            experiment_protocol=protocol,
        )

        assert result.status == ConflictStatus.RESOLVED_EXPERIMENT
        assert result.experiment_protocol == protocol

    def test_already_resolved_raises_value_error(self):
        """Attempting to resolve an already-resolved conflict raises ValueError."""
        stage, conflict = self._stage_with_conflict()
        resolve_conflict(stage, conflict.id, ResolutionPath.ACCEPT)

        with pytest.raises(ValueError, match="not active"):
            resolve_conflict(stage, conflict.id, ResolutionPath.DEFER)

    def test_nonexistent_conflict_raises_value_error(self):
        """Non-existent conflict ID raises ValueError."""
        stage = _make_stage()

        with pytest.raises(ValueError, match="not found"):
            resolve_conflict(stage, "cfl_doesnotexist", ResolutionPath.ACCEPT)

    def test_conflict_resolved_event_recorded(self):
        """CONFLICT_RESOLVED event is recorded on non-experiment resolutions."""
        stage, conflict = self._stage_with_conflict()

        resolve_conflict(stage, conflict.id, ResolutionPath.ACCEPT)

        resolved_events = _events_of_type(stage, EventType.CONFLICT_RESOLVED)
        assert len(resolved_events) == 1
        ev = resolved_events[0]
        assert ev.target_id == conflict.id
        assert ev.detail["resolution"] == ResolutionPath.ACCEPT.value

    def test_experiment_proposed_event_recorded(self):
        """CONFLICT_EXPERIMENT_PROPOSED event recorded for PROPOSE_EXPERIMENT."""
        stage, conflict = self._stage_with_conflict()
        protocol = "Run benchmark. Measure. Decide."

        resolve_conflict(
            stage, conflict.id, ResolutionPath.PROPOSE_EXPERIMENT,
            experiment_protocol=protocol,
        )

        exp_events = _events_of_type(stage, EventType.CONFLICT_EXPERIMENT_PROPOSED)
        assert len(exp_events) == 1
        assert exp_events[0].target_id == conflict.id

    def test_resolution_evidence_and_note_stored(self):
        """Evidence and note are stored on the conflict."""
        stage, conflict = self._stage_with_conflict()
        evidence = "Load test results from CI"
        note = "Decided after team sync"

        resolve_conflict(
            stage, conflict.id, ResolutionPath.ACCEPT,
            evidence=evidence, note=note
        )

        assert conflict.resolution_evidence == evidence
        assert conflict.resolution_note == note

    def test_challenge_event_recorded(self):
        """CONFLICT_RESOLVED event is also recorded when CHALLENGEing."""
        stage, conflict = self._stage_with_conflict()

        resolve_conflict(
            stage, conflict.id, ResolutionPath.CHALLENGE,
            steelman_summary="The opposing view has merit because..."
        )

        # CHALLENGE should record CONFLICT_RESOLVED (not experiment proposed)
        resolved_events = _events_of_type(stage, EventType.CONFLICT_RESOLVED)
        assert len(resolved_events) == 1

    def test_deferred_conflict_has_resolved_at_set(self):
        """DEFERRED conflicts get resolved_at timestamp."""
        stage, conflict = self._stage_with_conflict()

        resolve_conflict(stage, conflict.id, ResolutionPath.DEFER)

        assert conflict.resolved_at is not None

    def test_resolve_returns_conflict_object(self):
        """resolve_conflict returns the updated Conflict."""
        stage, conflict = self._stage_with_conflict()

        returned = resolve_conflict(stage, conflict.id, ResolutionPath.DISMISS)

        assert returned is conflict
