"""Tests for engine/cascade.py — Layer 4 cascading conflict detection and falsification.

Covers:
- detect_cascading_conflicts(): no deps, single, multiple, CHALLENGED mutation,
  cascade_auto_challenge=False gate, event recording, cascade_source_path,
  resolution_note content, inactive exclusion, multi-level chain.
- check_falsification(): valid/invalid assertions, event recording, orphan cascade,
  orphan events, no-dependent case.
"""

import pytest

from cognitive_bridge.engine.cascade import check_falsification, detect_cascading_conflicts
from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    EventType,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.stage import CompositionStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage() -> CompositionStage:
    """Return an empty stage with default parameters."""
    return CompositionStage(project_id="test", project_name="Cascade Tests")


def _make_assertion(
    topic_path: str,
    content: str,
    arc: CompositionArc = CompositionArc.INHERITS,
    depends_on_paths: list[str] | None = None,
    falsifiable_if: str | None = None,
    active: bool = True,
) -> Assertion:
    """Convenience factory that handles LOCAL-arc requirements."""
    kwargs: dict = {
        "topic_path": topic_path,
        "content": content,
        "arc": arc,
        "author": AssertionAuthor.AI,
        "depends_on_paths": depends_on_paths or [],
        "active": active,
    }
    if falsifiable_if is not None:
        kwargs["falsifiable_if"] = falsifiable_if
    elif arc == CompositionArc.LOCAL:
        # LOCAL requires falsifiable_if — provide a default
        kwargs["falsifiable_if"] = f"Falsified if {content} is disproved"
    return Assertion(**kwargs)


def _stage_with_dependency() -> tuple[CompositionStage, Assertion, Assertion]:
    """Stage where /orm depends on /db/engine."""
    stage = _make_stage()

    db = _make_assertion(
        topic_path="/db/engine",
        content="Use PostgreSQL",
        arc=CompositionArc.LOCAL,
        falsifiable_if="Falsified if PostgreSQL cannot handle required write throughput",
    )
    stage.assertions[db.id] = db

    orm = _make_assertion(
        topic_path="/orm",
        content="Use Prisma",
        arc=CompositionArc.INHERITS,
        depends_on_paths=["/db/engine"],
    )
    stage.assertions[orm.id] = orm

    return stage, db, orm


# ===========================================================================
# TestDetectCascadingConflicts
# ===========================================================================

class TestDetectCascadingConflicts:

    def test_no_dependents_returns_empty_list(self):
        """When nothing depends on the changed path, return []."""
        stage = _make_stage()
        db = _make_assertion("/db/engine", "Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[db.id] = db

        result = detect_cascading_conflicts(stage, "/db/engine", db.id)

        assert result == []

    def test_single_dependent_returns_one_conflict(self):
        """A single dependent produces exactly one Conflict."""
        stage, db, orm = _stage_with_dependency()
        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)
        stage.assertions[new_winner.id] = new_winner

        conflicts = detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        assert len(conflicts) == 1
        c = conflicts[0]
        assert c.assertion_a_id == new_winner.id
        assert c.assertion_b_id == orm.id
        assert c.topic_path == orm.topic_path
        assert c.detection_layer == ConflictDetectionLayer.CASCADING

    def test_multiple_dependents_returns_multiple_conflicts(self):
        """Each dependent gets its own Conflict object."""
        stage = _make_stage()
        db = _make_assertion("/db/engine", "Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[db.id] = db

        orm = _make_assertion("/orm", "Use Prisma", depends_on_paths=["/db/engine"])
        migration = _make_assertion("/migration", "Use Flyway", depends_on_paths=["/db/engine"])
        stage.assertions[orm.id] = orm
        stage.assertions[migration.id] = migration

        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)
        conflicts = detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        assert len(conflicts) == 2
        dependent_ids = {c.assertion_b_id for c in conflicts}
        assert dependent_ids == {orm.id, migration.id}

    def test_dependent_marked_challenged_when_auto_challenge_true(self):
        """cascade_auto_challenge=True (default) mutates assumption_status."""
        stage, db, orm = _stage_with_dependency()
        assert stage.parameters.cascade_auto_challenge is True

        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)
        detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        assert orm.assumption_status == AssumptionStatus.CHALLENGED

    def test_dependent_not_challenged_when_auto_challenge_false(self):
        """cascade_auto_challenge=False suppresses the status mutation."""
        stage, db, orm = _stage_with_dependency()
        stage.parameters.cascade_auto_challenge = False

        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)
        detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        # Status should remain LIVE — not mutated
        assert orm.assumption_status == AssumptionStatus.LIVE

    def test_events_recorded_for_each_challenged_assertion(self):
        """An ASSERTION_CHALLENGED event is recorded for each dependent."""
        stage = _make_stage()
        db = _make_assertion("/db/engine", "Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[db.id] = db

        orm = _make_assertion("/orm", "Use Prisma", depends_on_paths=["/db/engine"])
        migration = _make_assertion("/migration", "Use Flyway", depends_on_paths=["/db/engine"])
        stage.assertions[orm.id] = orm
        stage.assertions[migration.id] = migration

        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)
        detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        challenged_events = [
            e for e in stage.events
            if e.event_type == EventType.ASSERTION_CHALLENGED
        ]
        assert len(challenged_events) == 2
        event_targets = {e.target_id for e in challenged_events}
        assert event_targets == {orm.id, migration.id}

    def test_no_events_recorded_when_auto_challenge_false(self):
        """When cascade_auto_challenge is False, no events are appended."""
        stage, db, orm = _stage_with_dependency()
        stage.parameters.cascade_auto_challenge = False

        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)
        detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        assert len(stage.events) == 0

    def test_cascade_source_path_set_correctly(self):
        """The cascade_source_path on returned Conflicts matches changed_path."""
        stage, db, orm = _stage_with_dependency()
        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)

        conflicts = detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        assert len(conflicts) == 1
        assert conflicts[0].cascade_source_path == "/db/engine"

    def test_resolution_note_contains_dependent_content(self):
        """The resolution_note text includes the dependent assertion's content."""
        stage, db, orm = _stage_with_dependency()
        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)

        conflicts = detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        assert len(conflicts) == 1
        note = conflicts[0].resolution_note
        assert note is not None
        assert orm.content in note

    def test_inactive_dependents_excluded(self):
        """Assertions with active=False are not returned by get_dependents, so no conflict."""
        stage, db, orm = _stage_with_dependency()
        # Deactivate the dependent
        orm.active = False

        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)
        conflicts = detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        assert conflicts == []

    def test_event_detail_contains_source_path_and_new_winner_id(self):
        """ASSERTION_CHALLENGED events carry source_path and new_winner_id in detail."""
        stage, db, orm = _stage_with_dependency()
        new_winner = _make_assertion("/db/engine", "Use MySQL", arc=CompositionArc.INHERITS)

        detect_cascading_conflicts(stage, "/db/engine", new_winner.id)

        events = [e for e in stage.events if e.event_type == EventType.ASSERTION_CHALLENGED]
        assert len(events) == 1
        detail = events[0].detail
        assert detail["source_path"] == "/db/engine"
        assert detail["new_winner_id"] == new_winner.id
        assert detail["reason"] == "dependency_shifted"

    def test_multi_level_first_level_cascades(self):
        """Linear chain /c → /b → /a: changing /c triggers conflict for /b."""
        stage = _make_stage()

        a = _make_assertion("/a", "Foundation")
        b = _make_assertion("/b", "Mid-tier", depends_on_paths=["/a"])
        c = _make_assertion("/c", "Leaf", depends_on_paths=["/b"])
        for ast in (a, b, c):
            stage.assertions[ast.id] = ast

        new_a = _make_assertion("/a", "New Foundation")
        # Changing /a should cascade to /b (which depends on /a)
        conflicts = detect_cascading_conflicts(stage, "/a", new_a.id)

        dependent_ids = {con.assertion_b_id for con in conflicts}
        assert b.id in dependent_ids
        # /c depends on /b, not /a directly — not in this call
        assert c.id not in dependent_ids

    def test_multi_level_second_level_cascades(self):
        """When /b's winner changes, /c (which depends on /b) is cascaded."""
        stage = _make_stage()

        b = _make_assertion("/b", "Mid-tier")
        c = _make_assertion("/c", "Leaf", depends_on_paths=["/b"])
        for ast in (b, c):
            stage.assertions[ast.id] = ast

        new_b = _make_assertion("/b", "New Mid-tier")
        conflicts = detect_cascading_conflicts(stage, "/b", new_b.id)

        dependent_ids = {con.assertion_b_id for con in conflicts}
        assert c.id in dependent_ids

    def test_diamond_dependency_all_leaves_cascaded(self):
        """Diamond DAG: A→B, A→C, B→D, C→D. Changing A cascades to B and C.
        Then changing B cascades to D, and changing C cascades to D.
        Tested at the first level (only B and C depend on A directly)."""
        stage = _make_stage()

        a = _make_assertion("/a", "Root")
        b = _make_assertion("/b", "Left branch", depends_on_paths=["/a"])
        c = _make_assertion("/c", "Right branch", depends_on_paths=["/a"])
        d = _make_assertion("/d", "Diamond tip", depends_on_paths=["/b", "/c"])
        for ast in (a, b, c, d):
            stage.assertions[ast.id] = ast

        new_a = _make_assertion("/a", "New root")
        first_level = detect_cascading_conflicts(stage, "/a", new_a.id)
        first_ids = {con.assertion_b_id for con in first_level}
        # B and C depend on A directly
        assert first_ids == {b.id, c.id}
        # D is not a direct dependent of A
        assert d.id not in first_ids

        # Simulate B's winner changing (after A changed) — D should cascade
        new_b = _make_assertion("/b", "New left branch")
        second_level = detect_cascading_conflicts(stage, "/b", new_b.id)
        second_ids = {con.assertion_b_id for con in second_level}
        assert d.id in second_ids


# ===========================================================================
# TestCheckFalsification
# ===========================================================================

class TestCheckFalsification:

    def test_valid_assertion_with_falsifiable_if_returns_true(self):
        """Assertion with falsifiable_if is falsified; returns True."""
        stage, db, orm = _stage_with_dependency()

        result = check_falsification(
            stage, db.id, "PostgreSQL hit write throughput ceiling at 50k writes/sec"
        )

        assert result is True
        assert db.assumption_status == AssumptionStatus.FALSIFIED

    def test_assertion_without_falsifiable_if_returns_false(self):
        """Assertion lacking falsifiable_if cannot be falsified; returns False."""
        stage = _make_stage()
        ast = _make_assertion("/service/cache", "Use Redis", arc=CompositionArc.INHERITS)
        stage.assertions[ast.id] = ast
        # INHERITS arc has no falsifiable_if by default

        result = check_falsification(stage, ast.id, "Redis was slow")

        assert result is False
        assert ast.assumption_status == AssumptionStatus.LIVE

    def test_nonexistent_assertion_id_returns_false(self):
        """Non-existent ID is handled gracefully; returns False."""
        stage = _make_stage()

        result = check_falsification(stage, "ast_nonexistent", "something observed")

        assert result is False

    def test_falsification_event_recorded(self):
        """An ASSERTION_FALSIFIED event is appended with correct detail."""
        stage, db, orm = _stage_with_dependency()
        observation = "PostgreSQL failed at 50k writes/sec benchmark"

        check_falsification(stage, db.id, observation)

        falsified_events = [
            e for e in stage.events
            if e.event_type == EventType.ASSERTION_FALSIFIED
        ]
        assert len(falsified_events) == 1
        ev = falsified_events[0]
        assert ev.target_id == db.id
        assert ev.detail["observed"] == observation
        assert ev.detail["falsifiable_if"] == db.falsifiable_if

    def test_dependents_marked_orphaned_after_falsification(self):
        """All active dependents of the falsified assertion's path become ORPHANED."""
        stage, db, orm = _stage_with_dependency()

        check_falsification(stage, db.id, "Condition met")

        assert orm.assumption_status == AssumptionStatus.ORPHANED

    def test_orphaned_events_recorded_for_each_dependent(self):
        """An ASSERTION_ORPHANED event is recorded for each dependent."""
        stage = _make_stage()
        db = _make_assertion(
            "/db/engine",
            "Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if PostgreSQL cannot handle write throughput",
        )
        stage.assertions[db.id] = db

        orm = _make_assertion("/orm", "Use Prisma", depends_on_paths=["/db/engine"])
        migration = _make_assertion("/migration", "Use Flyway", depends_on_paths=["/db/engine"])
        stage.assertions[orm.id] = orm
        stage.assertions[migration.id] = migration

        check_falsification(stage, db.id, "PostgreSQL failed benchmark")

        orphaned_events = [
            e for e in stage.events
            if e.event_type == EventType.ASSERTION_ORPHANED
        ]
        assert len(orphaned_events) == 2
        orphan_targets = {e.target_id for e in orphaned_events}
        assert orphan_targets == {orm.id, migration.id}

    def test_assertion_with_no_dependents_still_falsified(self):
        """Falsification works even when there are no dependents to orphan."""
        stage = _make_stage()
        db = _make_assertion(
            "/standalone/service",
            "Use Kafka for messaging",
            arc=CompositionArc.LOCAL,
            falsifiable_if="Falsified if Kafka broker fails SLA consistently",
        )
        stage.assertions[db.id] = db

        result = check_falsification(stage, db.id, "Kafka missed SLA on 3 occasions")

        assert result is True
        assert db.assumption_status == AssumptionStatus.FALSIFIED

        # No ORPHANED events — nothing depended on this path
        orphaned_events = [
            e for e in stage.events
            if e.event_type == EventType.ASSERTION_ORPHANED
        ]
        assert orphaned_events == []

    def test_falsification_actor_is_system(self):
        """ASSERTION_FALSIFIED event actor is SYSTEM."""
        stage, db, orm = _stage_with_dependency()

        check_falsification(stage, db.id, "Observed condition")

        events = [e for e in stage.events if e.event_type == EventType.ASSERTION_FALSIFIED]
        assert len(events) == 1
        assert events[0].actor == AssertionAuthor.SYSTEM

    def test_orphaned_event_detail_references_source_assertion(self):
        """Each ORPHANED event's detail includes the source falsified assertion ID."""
        stage, db, orm = _stage_with_dependency()

        check_falsification(stage, db.id, "Observed condition")

        events = [e for e in stage.events if e.event_type == EventType.ASSERTION_ORPHANED]
        assert len(events) == 1
        assert events[0].detail["source"] == db.id
        assert events[0].detail["reason"] == "dependency_falsified"

    def test_inactive_dependents_not_orphaned(self):
        """Inactive assertions (active=False) are excluded from get_dependents."""
        stage, db, orm = _stage_with_dependency()
        orm.active = False  # deactivated before falsification

        check_falsification(stage, db.id, "Observed condition")

        # orm is inactive — get_dependents won't return it — so its status is unchanged
        assert orm.assumption_status == AssumptionStatus.LIVE

        orphaned_events = [
            e for e in stage.events
            if e.event_type == EventType.ASSERTION_ORPHANED
        ]
        assert orphaned_events == []
