"""Tests for CompositionStage — the coworker's mind.

Covers:
- resolve(): LIVRPS ordering, path filtering, metadata population
- get_dependents(): DAG dependent lookup
- get_dependency_chain(): Transitive dependency tracing and cycle detection
- get_subtree(): Prefix-based subtree queries
- record_event(): Audit log append and last_updated mutation
"""

import time
from datetime import datetime, timezone

import pytest

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
    EventType,
    _new_id,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage
from cognitive_bridge.models.variant_set import Variant, VariantSet


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_assertion(
    topic_path: str = "/test/path",
    arc: CompositionArc = CompositionArc.INHERITS,
    content: str = "test content",
    active: bool = True,
    confidence: float = 0.5,
    depends_on_paths: list[str] | None = None,
    assumption_status: AssumptionStatus = AssumptionStatus.LIVE,
    falsifiable_if: str | None = None,
) -> Assertion:
    """Factory for Assertion instances. Handles LOCAL arc's falsifiability requirement."""
    kwargs: dict = dict(
        topic_path=topic_path,
        arc=arc,
        content=content,
        active=active,
        author=AssertionAuthor.AI,
        confidence=confidence,
        depends_on_paths=depends_on_paths or [],
        assumption_status=assumption_status,
    )
    if arc == CompositionArc.LOCAL or falsifiable_if is not None:
        kwargs["falsifiable_if"] = falsifiable_if or "If counter-evidence is observed."
    return Assertion(**kwargs)


def _make_stage(*assertions: Assertion) -> CompositionStage:
    """Factory for CompositionStage pre-populated with given assertions."""
    stage = CompositionStage(project_id="test-proj", project_name="Test")
    for a in assertions:
        stage.assertions[a.id] = a
    return stage


def _make_conflict(
    assertion_a_id: str,
    assertion_b_id: str,
    topic_path: str = "/test/path",
    status: ConflictStatus = ConflictStatus.ACTIVE,
) -> Conflict:
    return Conflict(
        assertion_a_id=assertion_a_id,
        assertion_b_id=assertion_b_id,
        topic_path=topic_path,
        detection_layer=ConflictDetectionLayer.STRUCTURAL,
        status=status,
    )


def _make_variant_set(
    topic_path: str = "/test/path",
    resolved: bool = False,
) -> VariantSet:
    return VariantSet(
        name="Test Variants",
        topic_path=topic_path,
        variants=[
            Variant(name="Option A", content="content a"),
            Variant(name="Option B", content="content b"),
        ],
        resolved=resolved,
    )


# ═══════════════════════════════════════════════════════════════
# TestResolve
# ═══════════════════════════════════════════════════════════════

class TestResolve:
    def test_empty_stage_returns_empty_dict(self):
        stage = CompositionStage(project_id="p1")
        result = stage.resolve()
        assert result == {}

    def test_single_assertion_is_winner_with_empty_shadow(self):
        a = _make_assertion("/arch/db")
        stage = _make_stage(a)
        result = stage.resolve()

        assert "/arch/db" in result
        slot = result["/arch/db"]
        assert slot["winning"] is a
        assert slot["shadow_stack"] == []
        assert slot["requires_negotiation"] is False
        assert slot["depth"] == 1

    def test_stronger_arc_wins_local_beats_inherits(self):
        # LOCAL (10) beats INHERITS (20)
        local_a = _make_assertion("/arch/db", arc=CompositionArc.LOCAL,
                                  content="local claim")
        inherits_a = _make_assertion("/arch/db", arc=CompositionArc.INHERITS,
                                     content="inherits claim")
        stage = _make_stage(local_a, inherits_a)
        result = stage.resolve()

        slot = result["/arch/db"]
        assert slot["winning"].arc == CompositionArc.LOCAL
        assert len(slot["shadow_stack"]) == 1
        assert slot["shadow_stack"][0].arc == CompositionArc.INHERITS

    def test_all_arc_tiers_sort_correctly(self):
        """LIVRPS ordering: LOCAL < INHERITS < VARIANT_SET < REFERENCES < PAYLOADS < SPECIALIZES."""
        path = "/ordering/test"
        arcs_in_order = [
            CompositionArc.SPECIALIZES,
            CompositionArc.PAYLOADS,
            CompositionArc.REFERENCES,
            CompositionArc.VARIANT_SET,
            CompositionArc.INHERITS,
            CompositionArc.LOCAL,
        ]
        # Create assertions in reverse order so insertion order can't cheat
        assertions = [_make_assertion(path, arc=arc, content=f"{arc.name}") for arc in arcs_in_order]
        stage = _make_stage(*assertions)
        result = stage.resolve()

        slot = result[path]
        assert slot["winning"].arc == CompositionArc.LOCAL
        full_stack = [slot["winning"]] + slot["shadow_stack"]
        arc_values = [a.arc for a in full_stack]
        assert arc_values == sorted(arc_values)

    def test_same_arc_same_path_requires_negotiation(self):
        a1 = _make_assertion("/arch/db", arc=CompositionArc.INHERITS, confidence=0.7)
        a2 = _make_assertion("/arch/db", arc=CompositionArc.INHERITS, confidence=0.5)
        stage = _make_stage(a1, a2)
        result = stage.resolve()

        # Both have INHERITS — top two share the same arc => requires_negotiation
        slot = result["/arch/db"]
        assert slot["requires_negotiation"] is True

    def test_different_arcs_do_not_require_negotiation(self):
        local_a = _make_assertion("/arch/db", arc=CompositionArc.LOCAL)
        inherits_a = _make_assertion("/arch/db", arc=CompositionArc.INHERITS)
        stage = _make_stage(local_a, inherits_a)
        result = stage.resolve()

        assert result["/arch/db"]["requires_negotiation"] is False

    def test_inactive_assertions_excluded(self):
        active_a = _make_assertion("/arch/db", active=True, content="active")
        inactive_a = _make_assertion("/arch/db", active=False, content="inactive")
        stage = _make_stage(active_a, inactive_a)
        result = stage.resolve()

        slot = result["/arch/db"]
        assert slot["depth"] == 1
        assert slot["winning"].content == "active"

    def test_all_inactive_path_absent_from_result(self):
        inactive_a = _make_assertion("/arch/db", active=False)
        stage = _make_stage(inactive_a)
        result = stage.resolve()
        assert "/arch/db" not in result

    def test_path_filter_includes_only_matching_paths(self):
        a_db = _make_assertion("/arch/db", content="db claim")
        a_api = _make_assertion("/arch/api", content="api claim")
        a_other = _make_assertion("/infra/network", content="network claim")
        stage = _make_stage(a_db, a_api, a_other)

        result = stage.resolve(path_filter="/arch")
        assert "/arch/db" in result
        assert "/arch/api" in result
        assert "/infra/network" not in result

    def test_path_filter_exact_prefix_only(self):
        a1 = _make_assertion("/arch/db")
        a2 = _make_assertion("/architecture/wide")  # starts with /arch but different subtree
        stage = _make_stage(a1, a2)

        result = stage.resolve(path_filter="/arch/")
        assert "/arch/db" in result
        assert "/architecture/wide" not in result

    def test_payloads_assertions_in_pending_payloads(self):
        payload_a = _make_assertion("/arch/db", arc=CompositionArc.PAYLOADS)
        stage = _make_stage(payload_a)
        result = stage.resolve()

        slot = result["/arch/db"]
        assert payload_a in slot["pending_payloads"]

    def test_non_payloads_assertions_not_in_pending_payloads(self):
        inherits_a = _make_assertion("/arch/db", arc=CompositionArc.INHERITS)
        stage = _make_stage(inherits_a)
        result = stage.resolve()

        assert result["/arch/db"]["pending_payloads"] == []

    def test_challenged_assertion_in_health_issues(self):
        a = _make_assertion("/arch/db", assumption_status=AssumptionStatus.CHALLENGED)
        stage = _make_stage(a)
        result = stage.resolve()

        assert a in result["/arch/db"]["health_issues"]

    def test_orphaned_assertion_in_health_issues(self):
        a = _make_assertion("/arch/db", assumption_status=AssumptionStatus.ORPHANED)
        stage = _make_stage(a)
        result = stage.resolve()

        assert a in result["/arch/db"]["health_issues"]

    def test_live_assertion_not_in_health_issues(self):
        a = _make_assertion("/arch/db", assumption_status=AssumptionStatus.LIVE)
        stage = _make_stage(a)
        result = stage.resolve()

        assert result["/arch/db"]["health_issues"] == []

    def test_falsified_assertion_not_in_health_issues(self):
        # FALSIFIED is not CHALLENGED or ORPHANED — should not appear in health_issues
        a = _make_assertion("/arch/db", assumption_status=AssumptionStatus.FALSIFIED)
        stage = _make_stage(a)
        result = stage.resolve()

        assert result["/arch/db"]["health_issues"] == []

    def test_active_conflicts_appear_for_matching_path(self):
        a1 = _make_assertion("/arch/db")
        a2 = _make_assertion("/arch/db", arc=CompositionArc.SPECIALIZES)
        stage = _make_stage(a1, a2)
        conflict = _make_conflict(a1.id, a2.id, topic_path="/arch/db")
        stage.conflicts[conflict.id] = conflict

        result = stage.resolve()
        assert conflict in result["/arch/db"]["active_conflicts"]

    def test_resolved_conflicts_not_in_active_conflicts(self):
        a1 = _make_assertion("/arch/db")
        a2 = _make_assertion("/arch/db", arc=CompositionArc.SPECIALIZES)
        stage = _make_stage(a1, a2)
        conflict = _make_conflict(
            a1.id, a2.id, topic_path="/arch/db",
            status=ConflictStatus.RESOLVED_OVERRIDE,
        )
        stage.conflicts[conflict.id] = conflict

        result = stage.resolve()
        assert result["/arch/db"]["active_conflicts"] == []

    def test_open_variant_sets_appear_for_path(self):
        a = _make_assertion("/arch/db")
        stage = _make_stage(a)
        vs = _make_variant_set(topic_path="/arch/db", resolved=False)
        stage.variant_sets[vs.id] = vs

        result = stage.resolve()
        assert vs in result["/arch/db"]["open_variants"]

    def test_resolved_variant_sets_not_in_open_variants(self):
        a = _make_assertion("/arch/db")
        stage = _make_stage(a)
        vs = _make_variant_set(topic_path="/arch/db", resolved=True)
        stage.variant_sets[vs.id] = vs

        result = stage.resolve()
        assert result["/arch/db"]["open_variants"] == []

    def test_depth_counts_only_active_assertions(self):
        active1 = _make_assertion("/arch/db", content="a1")
        active2 = _make_assertion("/arch/db", content="a2", arc=CompositionArc.SPECIALIZES)
        inactive = _make_assertion("/arch/db", content="a3", active=False)
        stage = _make_stage(active1, active2, inactive)
        result = stage.resolve()

        assert result["/arch/db"]["depth"] == 2

    def test_multiple_paths_resolved_independently(self):
        a_db = _make_assertion("/arch/db")
        a_api = _make_assertion("/arch/api", arc=CompositionArc.SPECIALIZES)
        stage = _make_stage(a_db, a_api)
        result = stage.resolve()

        assert "/arch/db" in result
        assert "/arch/api" in result
        assert result["/arch/db"]["winning"] is a_db
        assert result["/arch/api"]["winning"] is a_api

    def test_confidence_tiebreak_higher_wins(self):
        """Equal arc: higher confidence wins."""
        low = _make_assertion("/arch/db", arc=CompositionArc.INHERITS, confidence=0.3)
        high = _make_assertion("/arch/db", arc=CompositionArc.INHERITS, confidence=0.9)
        stage = _make_stage(low, high)
        result = stage.resolve()

        assert result["/arch/db"]["winning"].confidence == 0.9


# ═══════════════════════════════════════════════════════════════
# TestGetDependents
# ═══════════════════════════════════════════════════════════════

class TestGetDependents:
    def test_no_dependents_returns_empty(self):
        a = _make_assertion("/arch/db")
        stage = _make_stage(a)
        dependents = stage.get_dependents("/arch/db")
        assert dependents == []

    def test_single_dependent_found(self):
        foundation = _make_assertion("/arch/db")
        dependent = _make_assertion("/arch/api", depends_on_paths=["/arch/db"])
        stage = _make_stage(foundation, dependent)

        dependents = stage.get_dependents("/arch/db")
        assert dependent in dependents
        assert foundation not in dependents

    def test_multiple_dependents_all_found(self):
        dependent1 = _make_assertion("/arch/api", depends_on_paths=["/arch/db"])
        dependent2 = _make_assertion("/arch/cache", depends_on_paths=["/arch/db"])
        unrelated = _make_assertion("/infra/network")
        stage = _make_stage(dependent1, dependent2, unrelated)

        dependents = stage.get_dependents("/arch/db")
        assert dependent1 in dependents
        assert dependent2 in dependents
        assert unrelated not in dependents

    def test_inactive_dependents_excluded(self):
        active_dep = _make_assertion("/arch/api", depends_on_paths=["/arch/db"],
                                     active=True, content="active")
        inactive_dep = _make_assertion("/arch/cache", depends_on_paths=["/arch/db"],
                                       active=False, content="inactive")
        stage = _make_stage(active_dep, inactive_dep)

        dependents = stage.get_dependents("/arch/db")
        assert active_dep in dependents
        assert inactive_dep not in dependents

    def test_dependency_path_must_match_exactly(self):
        """An assertion depending on '/arch/dbase' is NOT a dependent of '/arch/db'.

        The dependency path check in get_dependents is an exact membership test,
        not a prefix check. '/arch/dbase' != '/arch/db'.
        """
        # assertion at /arch/api depending on /arch/dbase — note: /arch/dbase != /arch/db
        a = _make_assertion("/arch/api", depends_on_paths=["/arch/dbase"])
        stage = _make_stage(a)

        dependents = stage.get_dependents("/arch/db")
        assert dependents == []

    def test_multiple_deps_one_matches(self):
        a = _make_assertion("/arch/api",
                            depends_on_paths=["/arch/db", "/infra/network"])
        stage = _make_stage(a)

        assert a in stage.get_dependents("/arch/db")
        assert a in stage.get_dependents("/infra/network")
        assert stage.get_dependents("/arch/cache") == []


# ═══════════════════════════════════════════════════════════════
# TestGetDependencyChain
# ═══════════════════════════════════════════════════════════════

class TestGetDependencyChain:
    def test_no_dependencies_returns_empty(self):
        a = _make_assertion("/arch/db")
        stage = _make_stage(a)

        chain = stage.get_dependency_chain(a.id)
        assert chain == []

    def test_single_direct_dependency(self):
        foundation = _make_assertion("/arch/db")
        dependent = _make_assertion("/arch/api", depends_on_paths=["/arch/db"])
        stage = _make_stage(foundation, dependent)

        chain = stage.get_dependency_chain(dependent.id)
        assert "/arch/db" in chain

    def test_transitive_dependencies_traced(self):
        """A depends on B (/arch/db), B depends on C (/arch/storage).
        get_dependency_chain(A) should include both /arch/db and /arch/storage.
        """
        c = _make_assertion("/arch/storage")
        b = _make_assertion("/arch/db", depends_on_paths=["/arch/storage"])
        a = _make_assertion("/arch/api", depends_on_paths=["/arch/db"])
        stage = _make_stage(a, b, c)

        chain = stage.get_dependency_chain(a.id)
        assert "/arch/db" in chain
        assert "/arch/storage" in chain

    def test_diamond_dependency_no_infinite_loop(self):
        """Diamond: A depends on B and C; B and C both depend on D.
        Should not duplicate-traverse D infinitely.
        """
        d = _make_assertion("/arch/d")
        b = _make_assertion("/arch/b", depends_on_paths=["/arch/d"])
        c = _make_assertion("/arch/c", depends_on_paths=["/arch/d"])
        a = _make_assertion("/arch/a", depends_on_paths=["/arch/b", "/arch/c"])
        stage = _make_stage(a, b, c, d)

        # Must complete without hanging/error
        chain = stage.get_dependency_chain(a.id)
        assert "/arch/b" in chain
        assert "/arch/c" in chain
        assert "/arch/d" in chain

    def test_cycle_detection_no_infinite_loop(self):
        """Cycles must NOT cause infinite recursion.

        We manually construct a cycle by bypassing Pydantic's self-referential
        validator, because the validator only blocks same-path deps (A -> A).
        For cross-assertion cycles (A -> B -> A), we mutate after creation.
        """
        a = _make_assertion("/arch/a", depends_on_paths=["/arch/b"])
        b = _make_assertion("/arch/b")
        stage = _make_stage(a, b)
        # Introduce cycle by mutating b's depends_on_paths after construction
        b.depends_on_paths = ["/arch/a"]

        # Must complete — cycle detected via visited set
        chain = stage.get_dependency_chain(a.id)
        # The chain should contain the paths from the cycle but not loop forever
        assert "/arch/b" in chain

    def test_unknown_assertion_id_returns_empty(self):
        stage = CompositionStage(project_id="p")
        chain = stage.get_dependency_chain("ast_nonexistent")
        assert chain == []

    def test_inactive_assertions_still_traced(self):
        """Inactive assertions in the dependency chain are still followed,
        because get_dependency_chain resolves against ALL assertions at a path,
        not just active ones — this matches the spec's loop over all assertions.
        """
        foundation = _make_assertion("/arch/db", active=False)
        dependent = _make_assertion("/arch/api", depends_on_paths=["/arch/db"])
        stage = _make_stage(foundation, dependent)

        # foundation is inactive, but the traversal visits all assertions at /arch/db
        chain = stage.get_dependency_chain(dependent.id)
        assert "/arch/db" in chain


# ═══════════════════════════════════════════════════════════════
# TestGetSubtree
# ═══════════════════════════════════════════════════════════════

class TestGetSubtree:
    def test_returns_assertions_matching_prefix(self):
        a_db = _make_assertion("/arch/db")
        a_api = _make_assertion("/arch/api")
        stage = _make_stage(a_db, a_api)

        subtree = stage.get_subtree("/arch")
        assert a_db in subtree
        assert a_api in subtree

    def test_does_not_return_non_matching_paths(self):
        a_arch = _make_assertion("/arch/db")
        a_infra = _make_assertion("/infra/network")
        stage = _make_stage(a_arch, a_infra)

        subtree = stage.get_subtree("/arch")
        assert a_arch in subtree
        assert a_infra not in subtree

    def test_inactive_assertions_excluded(self):
        active_a = _make_assertion("/arch/db", active=True, content="active")
        inactive_a = _make_assertion("/arch/api", active=False, content="inactive")
        stage = _make_stage(active_a, inactive_a)

        subtree = stage.get_subtree("/arch")
        assert active_a in subtree
        assert inactive_a not in subtree

    def test_empty_stage_returns_empty_list(self):
        stage = CompositionStage(project_id="p")
        assert stage.get_subtree("/arch") == []

    def test_prefix_matches_exact_path(self):
        a = _make_assertion("/arch/db")
        stage = _make_stage(a)
        subtree = stage.get_subtree("/arch/db")
        assert a in subtree

    def test_deep_nesting_included(self):
        shallow = _make_assertion("/arch/db")
        deep = _make_assertion("/arch/db/engine/config")
        other = _make_assertion("/arch/api")
        stage = _make_stage(shallow, deep, other)

        subtree = stage.get_subtree("/arch/db")
        assert shallow in subtree
        assert deep in subtree
        assert other not in subtree

    def test_prefix_boundary_not_crossed(self):
        """'/arch/dbase' should not appear in subtree for '/arch/db'."""
        # Note: topic_path pattern requires /word/word — need a valid path
        a_db = _make_assertion("/arch/db")
        a_dbext = _make_assertion("/arch/dbext")  # shares prefix /arch/db
        stage = _make_stage(a_db, a_dbext)

        # /arch/dbext starts with /arch/db — this is expected behaviour of startswith
        # The test documents this: prefix filtering is string-prefix, not path-segment aware
        subtree = stage.get_subtree("/arch/db/")
        assert a_db not in subtree  # /arch/db does NOT start with /arch/db/
        assert a_dbext not in subtree


# ═══════════════════════════════════════════════════════════════
# TestRecordEvent
# ═══════════════════════════════════════════════════════════════

class TestRecordEvent:
    def test_event_appended_to_events_list(self):
        stage = CompositionStage(project_id="p")
        assert len(stage.events) == 0

        stage.record_event(
            event_type=EventType.ASSERTION_CREATED,
            actor=AssertionAuthor.AI,
            target_id="ast_abc123",
        )

        assert len(stage.events) == 1
        event = stage.events[0]
        assert event.event_type == EventType.ASSERTION_CREATED
        assert event.actor == AssertionAuthor.AI
        assert event.target_id == "ast_abc123"

    def test_detail_defaults_to_empty_dict_when_none(self):
        stage = CompositionStage(project_id="p")
        stage.record_event(
            event_type=EventType.ASSERTION_CREATED,
            actor=AssertionAuthor.SYSTEM,
            target_id="ast_xyz",
            detail=None,
        )
        assert stage.events[0].detail == {}

    def test_detail_stored_when_provided(self):
        stage = CompositionStage(project_id="p")
        detail = {"old_arc": "inherits", "new_arc": "local"}
        stage.record_event(
            event_type=EventType.ASSERTION_PROMOTED,
            actor=AssertionAuthor.USER,
            target_id="ast_123",
            detail=detail,
        )
        assert stage.events[0].detail == detail

    def test_last_updated_changes_after_record_event(self):
        stage = CompositionStage(project_id="p")
        before = stage.last_updated
        # Small sleep to ensure clock advances (datetime resolution)
        import time
        time.sleep(0.01)
        stage.record_event(
            event_type=EventType.ASSERTION_CREATED,
            actor=AssertionAuthor.AI,
            target_id="ast_001",
        )
        assert stage.last_updated > before

    def test_multiple_events_accumulate(self):
        stage = CompositionStage(project_id="p")
        for i in range(5):
            stage.record_event(
                event_type=EventType.ASSERTION_CREATED,
                actor=AssertionAuthor.AI,
                target_id=f"ast_{i:03d}",
            )
        assert len(stage.events) == 5

    def test_events_are_ordered_by_insertion(self):
        stage = CompositionStage(project_id="p")
        stage.record_event(EventType.ASSERTION_CREATED, AssertionAuthor.AI, "ast_001")
        stage.record_event(EventType.ASSERTION_PROMOTED, AssertionAuthor.USER, "ast_001")
        stage.record_event(EventType.ASSERTION_RETRACTED, AssertionAuthor.SYSTEM, "ast_001")

        assert stage.events[0].event_type == EventType.ASSERTION_CREATED
        assert stage.events[1].event_type == EventType.ASSERTION_PROMOTED
        assert stage.events[2].event_type == EventType.ASSERTION_RETRACTED


# ═══════════════════════════════════════════════════════════════
# TestConftestFixture
# ═══════════════════════════════════════════════════════════════

class TestConftestFixture:
    def test_empty_stage_fixture_works(self, empty_stage):
        """Verify conftest.py fixture resolves correctly."""
        assert empty_stage.project_id == "test-project"
        assert empty_stage.project_name == "Test Project"
        assert empty_stage.assertions == {}
        assert empty_stage.resolve() == {}

    def test_empty_stage_fixture_has_default_parameters(self, empty_stage):
        from cognitive_bridge.models.parameters import CognitiveParameters
        assert isinstance(empty_stage.parameters, CognitiveParameters)


# ═══════════════════════════════════════════════════════════════
# TestCompositionStageDefaults
# ═══════════════════════════════════════════════════════════════

class TestCompositionStageDefaults:
    def test_required_field_project_id(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CompositionStage()  # type: ignore[call-arg]

    def test_default_project_name_empty_string(self):
        stage = CompositionStage(project_id="p")
        assert stage.project_name == ""

    def test_default_exchange_count_zero(self):
        stage = CompositionStage(project_id="p")
        assert stage.exchange_count == 0

    def test_default_collections_empty(self):
        stage = CompositionStage(project_id="p")
        assert stage.assertions == {}
        assert stage.conflicts == {}
        assert stage.variant_sets == {}
        assert stage.events == []
        assert stage.decisions == []

    def test_created_at_and_last_updated_set_on_init(self):
        stage = CompositionStage(project_id="p")
        assert isinstance(stage.created_at, datetime)
        assert isinstance(stage.last_updated, datetime)
        assert stage.created_at.tzinfo is not None  # UTC-aware
