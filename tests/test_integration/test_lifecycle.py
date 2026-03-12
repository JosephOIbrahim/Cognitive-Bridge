"""Integration test: Full lifecycle from cold start through RED_TEAMING.

Tests the posture progression and key lifecycle transitions:
- LEARNING: sparse assertions, no conflicts
- ENGAGED: active conflicts present
- AUTHORITATIVE: stable, high-confidence state
- RED_TEAMING: too many unchallenged LOCAL assertions triggers devil's advocate mode

Also covers the RED_TEAMING trigger, generate_red_team_report output, and the
record_red_team_trigger audit event.
"""

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    CompositionStage,
    ConflictStatus,
    Decision,
    EventType,
    ResolutionPath,
)
from cognitive_bridge.engine.resolver import (
    add_assertion,
    get_current_winner,
    promote_assertion,
    resolve_conflict,
    retract_assertion,
    falsify_assertion,
)
from cognitive_bridge.engine.red_team import (
    find_unchallenged_locals,
    find_unfalsifiable_locals,
    generate_red_team_report,
    record_red_team_trigger,
    should_trigger_red_team,
)
from cognitive_bridge.engine.provenance import count_events_by_type


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_local(path: str, content: str, author: AssertionAuthor = AssertionAuthor.AI) -> Assertion:
    """Factory for LOCAL assertions with auto-generated falsifiable_if."""
    return Assertion(
        topic_path=path,
        content=content,
        arc=CompositionArc.LOCAL,
        author=author,
        falsifiable_if=f"Falsified if {content} is disproved by evidence",
    )


def _make_inherits(
    path: str,
    content: str,
    depends_on: list[str] | None = None,
) -> Assertion:
    """Factory for INHERITS assertions."""
    return Assertion(
        topic_path=path,
        content=content,
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        depends_on_paths=depends_on or [],
    )


# ===========================================================================
# TestColdStartToRedTeam
# ===========================================================================

class TestColdStartToRedTeam:
    """Test posture progression from cold-start to RED_TEAMING activation."""

    def test_empty_stage_does_not_trigger_red_team(self):
        """A stage with no assertions and exchange_count=0 never triggers RED_TEAMING."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=0
        )
        assert should_trigger_red_team(stage) is False

    def test_few_local_assertions_no_trigger(self):
        """Below threshold LOCAL assertions: RED_TEAMING does not trigger."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )
        stage.parameters.red_team_threshold = 5

        for label in ("alpha", "beta", "gamma"):
            a = _make_local(f"/topic/{label}", f"Claim {label}")
            add_assertion(stage, a)

        assert should_trigger_red_team(stage) is False

    def test_active_conflict_suppresses_red_team_trigger(self):
        """Even above threshold, an active conflict suppresses RED_TEAMING."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )
        stage.parameters.red_team_threshold = 3

        # Add enough LOCALs to hit the threshold
        for label in ("alpha", "beta", "gamma", "delta"):
            a = _make_local(f"/verified/{label}", f"Verified claim {label}")
            add_assertion(stage, a)

        # Introduce a conflict to simulate ongoing debate
        a1 = Assertion(
            topic_path="/tech/framework",
            content="Use React",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        a2 = Assertion(
            topic_path="/tech/framework",
            content="Use Vue",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, a1)
        add_assertion(stage, a2)  # Creates structural conflict

        active_conflicts = sum(
            1 for c in stage.conflicts.values() if c.status == ConflictStatus.ACTIVE
        )
        assert active_conflicts > 0

        # RED_TEAMING should NOT trigger because there are active conflicts
        assert should_trigger_red_team(stage) is False

    def test_red_team_triggers_above_threshold_zero_conflicts(self):
        """Above threshold LOCALs + zero active conflicts + exchange > 0 → RED_TEAMING."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )
        stage.parameters.red_team_threshold = 5

        labels = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")
        for label in labels:
            a = _make_local(f"/verified/{label}", f"Verified fact {label}")
            add_assertion(stage, a)

        assert should_trigger_red_team(stage) is True

    def test_red_team_does_not_trigger_with_zero_exchange_count(self):
        """exchange_count=0 (fresh stage) prevents RED_TEAMING even above threshold."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=0
        )
        stage.parameters.red_team_threshold = 3

        for label in ("alpha", "beta", "gamma", "delta", "epsilon"):
            a = _make_local(f"/fact/{label}", f"Fact {label}")
            add_assertion(stage, a)

        assert should_trigger_red_team(stage) is False

    def test_posture_progression_learning_to_red_team(self):
        """Run the full lifecycle from LEARNING through RED_TEAMING."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle Test", exchange_count=1
        )
        stage.parameters.red_team_threshold = 5

        # --- LEARNING phase: few assertions ---
        for label in ("alpha", "beta"):
            a = _make_inherits(f"/topic/{label}", f"Claim {label}")
            add_assertion(stage, a)

        local_count = sum(
            1 for a in stage.assertions.values()
            if a.active and a.arc == CompositionArc.LOCAL
        )
        assert local_count < 3  # Still in learning territory

        # --- ENGAGED phase: create and resolve a conflict ---
        react = Assertion(
            topic_path="/tech/framework",
            content="Use React",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        vue = Assertion(
            topic_path="/tech/framework",
            content="Use Vue",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, react)
        result = add_assertion(stage, vue)

        assert result.structural_conflict is not None
        active_conflicts = sum(
            1 for c in stage.conflicts.values() if c.status == ConflictStatus.ACTIVE
        )
        assert active_conflicts > 0  # ENGAGED

        # Resolve the conflict so we can reach AUTHORITATIVE
        conflict_id = result.structural_conflict.id
        resolve_conflict(
            stage, conflict_id, ResolutionPath.ACCEPT,
            evidence="Team prefers React's ecosystem"
        )

        # --- AUTHORITATIVE / RED_TEAMING: add lots of LOCAL assertions ---
        for label in ("alpha", "beta", "gamma", "delta", "epsilon", "zeta"):
            a = _make_local(f"/verified/{label}", f"Verified fact {label}")
            add_assertion(stage, a)

        # Should trigger RED_TEAMING
        assert should_trigger_red_team(stage) is True

    # -----------------------------------------------------------------------
    # RED_TEAMING report
    # -----------------------------------------------------------------------

    def test_red_team_report_contains_triggered_status(self):
        """generate_red_team_report includes 'TRIGGERED' when conditions are met."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )
        stage.parameters.red_team_threshold = 5

        labels = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")
        for label in labels:
            a = _make_local(f"/verified/{label}", f"Verified fact {label}")
            add_assertion(stage, a)

        assert should_trigger_red_team(stage) is True
        report = generate_red_team_report(stage)

        assert "TRIGGERED" in report

    def test_red_team_report_contains_unchallenged_label(self):
        """Report highlights UNCHALLENGED LOCAL assertions when they exist."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )
        stage.parameters.red_team_threshold = 5

        labels = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")
        for label in labels:
            a = _make_local(f"/verified/{label}", f"Verified fact {label}")
            add_assertion(stage, a)

        report = generate_red_team_report(stage)
        assert "UNCHALLENGED" in report

    def test_red_team_report_monitoring_when_below_threshold(self):
        """Report shows MONITORING when RED_TEAMING is not triggered."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )
        stage.parameters.red_team_threshold = 10

        for label in ("alpha", "beta", "gamma"):
            a = _make_local(f"/fact/{label}", f"Fact {label}")
            add_assertion(stage, a)

        report = generate_red_team_report(stage)
        assert "MONITORING" in report

    def test_record_red_team_trigger_appends_event(self):
        """record_red_team_trigger appends RED_TEAM_TRIGGERED event to stage.events."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )
        stage.parameters.red_team_threshold = 3

        for label in ("alpha", "beta", "gamma", "delta"):
            a = _make_local(f"/fact/{label}", f"Fact {label}")
            add_assertion(stage, a)

        assert should_trigger_red_team(stage) is True
        record_red_team_trigger(stage)

        counts = count_events_by_type(stage)
        assert "red_team_triggered" in counts
        assert counts["red_team_triggered"] >= 1

    def test_find_unchallenged_locals_excludes_contested(self):
        """find_unchallenged_locals does not return assertions involved in any conflict."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )

        # Assertion that will be involved in a conflict
        a1 = Assertion(
            topic_path="/arch/db",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if PostgreSQL cannot scale",
        )
        # Assertion that will NOT be involved in any conflict
        a2 = _make_local("/arch/cache", "Use Redis")
        a3 = Assertion(
            topic_path="/arch/db",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )

        add_assertion(stage, a1)
        add_assertion(stage, a2)
        add_assertion(stage, a3)  # Creates conflict involving a1

        unchallenged = find_unchallenged_locals(stage)
        unchallenged_ids = {a.id for a in unchallenged}

        # a2 (Redis at /arch/cache) was never in a conflict
        assert a2.id in unchallenged_ids
        # a1 (PostgreSQL) was involved in the structural conflict
        assert a1.id not in unchallenged_ids

    def test_find_unfalsifiable_locals_returns_live_locals(self):
        """find_unfalsifiable_locals returns LIVE LOCAL assertions with falsifiable_if."""
        stage = CompositionStage(
            project_id="lifecycle", project_name="Lifecycle", exchange_count=1
        )
        a = _make_local("/arch/db", "Use PostgreSQL")
        add_assertion(stage, a)

        # This assertion has falsifiable_if and is LIVE
        results = find_unfalsifiable_locals(stage)
        assert any(r.id == a.id for r in results)


# ===========================================================================
# TestDiamondDAG
# ===========================================================================

class TestDiamondDAG:
    """Diamond dependency: A -> B, A -> C, B -> D, C -> D."""

    def test_diamond_first_level_cascades_to_b_and_c(self):
        """Changing A cascades to B and C (direct dependents). D is not direct."""
        stage = CompositionStage(
            project_id="diamond-test", project_name="Diamond Test"
        )

        a = _make_inherits("/a", "Root claim")
        b = _make_inherits("/b", "Left branch", depends_on=["/a"])
        c = _make_inherits("/c", "Right branch", depends_on=["/a"])
        d = _make_inherits("/d", "Diamond tip", depends_on=["/b", "/c"])

        for ast in (a, b, c, d):
            stage.assertions[ast.id] = ast

        # Introduce a stronger claim at /a to displace the current winner
        a2 = Assertion(
            topic_path="/a",
            content="New root claim",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="Falsified if new root is disproved",
        )
        result = add_assertion(stage, a2)

        assert result.winner_changed is True

        # B and C are direct dependents of /a
        assert b.assumption_status == AssumptionStatus.CHALLENGED
        assert c.assumption_status == AssumptionStatus.CHALLENGED
        # D depends on /b and /c, not /a directly
        assert d.assumption_status == AssumptionStatus.LIVE

    def test_diamond_second_level_b_change_challenges_d(self):
        """After B changes, D (which depends on /b) is CHALLENGED."""
        stage = CompositionStage(
            project_id="diamond-test", project_name="Diamond Test"
        )

        b = _make_inherits("/b", "Left branch")
        c = _make_inherits("/c", "Right branch")
        d = _make_inherits("/d", "Diamond tip", depends_on=["/b", "/c"])

        for ast in (b, c, d):
            stage.assertions[ast.id] = ast

        b2 = Assertion(
            topic_path="/b",
            content="New left branch",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="Falsified if new left is disproved",
        )
        result = add_assertion(stage, b2)

        assert result.winner_changed is True
        assert d.assumption_status == AssumptionStatus.CHALLENGED


# ===========================================================================
# TestConflictResolutionLifecycle
# ===========================================================================

class TestConflictResolutionLifecycle:
    """Exercise all conflict resolution paths and check invariants."""

    def _conflicted_stage(self) -> tuple[CompositionStage, object]:
        """Stage with one active structural conflict."""
        stage = CompositionStage(
            project_id="conflict-lifecycle", project_name="Conflict Lifecycle"
        )
        a = Assertion(
            topic_path="/tech/database",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        b = Assertion(
            topic_path="/tech/database",
            content="Use MySQL",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, a)
        result = add_assertion(stage, b)
        return stage, result.structural_conflict

    def test_accept_removes_conflict_from_active(self):
        """ACCEPT resolution closes the conflict."""
        stage, conflict = self._conflicted_stage()
        resolve_conflict(stage, conflict.id, ResolutionPath.ACCEPT)
        assert conflict.status == ConflictStatus.RESOLVED_OVERRIDE

    def test_synthesize_marks_synthesized(self):
        """SYNTHESIZE resolution marks the conflict as RESOLVED_SYNTHESIZED."""
        stage, conflict = self._conflicted_stage()
        resolve_conflict(
            stage, conflict.id, ResolutionPath.SYNTHESIZE,
            note="Use PostgreSQL with MySQL compatibility mode"
        )
        assert conflict.status == ConflictStatus.RESOLVED_SYNTHESIZED

    def test_defer_keeps_conflict_in_stage_but_deferred(self):
        """DEFER closes the conflict as DEFERRED (not ACTIVE, not deleted)."""
        stage, conflict = self._conflicted_stage()
        resolve_conflict(stage, conflict.id, ResolutionPath.DEFER)

        assert conflict.id in stage.conflicts
        assert conflict.status == ConflictStatus.DEFERRED

    def test_challenge_then_experiment_is_valid_two_step(self):
        """AI can CHALLENGE first (steelman required), then PROPOSE_EXPERIMENT."""
        stage, conflict = self._conflicted_stage()

        # Step A: challenge with steelman
        resolve_conflict(
            stage,
            conflict.id,
            ResolutionPath.CHALLENGE,
            steelman_summary="MySQL has better horizontal sharding for our write pattern.",
        )
        assert conflict.status == ConflictStatus.ACTIVE  # Still active after challenge

        # Step B: propose experiment
        resolve_conflict(
            stage,
            conflict.id,
            ResolutionPath.PROPOSE_EXPERIMENT,
            experiment_protocol="Run write benchmark at 50k writes/sec for 1 hour on both DBs.",
        )
        assert conflict.status == ConflictStatus.RESOLVED_EXPERIMENT

    def test_resolve_already_resolved_raises_value_error(self):
        """Cannot resolve a conflict that is no longer ACTIVE."""
        stage, conflict = self._conflicted_stage()
        resolve_conflict(stage, conflict.id, ResolutionPath.ACCEPT)

        with pytest.raises(ValueError, match="not active"):
            resolve_conflict(stage, conflict.id, ResolutionPath.DEFER)

    def test_retract_winner_transfers_to_next_best(self):
        """Retracting the winning assertion exposes the next-best as the new winner."""
        stage = CompositionStage(
            project_id="retract-test", project_name="Retract Test"
        )
        local_a = _make_local("/arch/db", "Use PostgreSQL")
        inherits_b = _make_inherits("/arch/db", "Use MySQL")

        add_assertion(stage, local_a)
        add_assertion(stage, inherits_b)

        winner_before = get_current_winner(stage, "/arch/db")
        assert winner_before.id == local_a.id  # LOCAL wins

        result = retract_assertion(stage, local_a.id)

        assert result.winner_changed is True
        winner_after = get_current_winner(stage, "/arch/db")
        assert winner_after.id == inherits_b.id

    def test_retract_sole_assertion_leaves_no_winner(self):
        """Retracting the only assertion at a path leaves no winner."""
        stage = CompositionStage(
            project_id="retract-test", project_name="Retract Test"
        )
        a = _make_local("/arch/db", "Use PostgreSQL")
        add_assertion(stage, a)

        result = retract_assertion(stage, a.id)

        assert result.winner_changed is True
        assert result.new_winner_id is None
        assert get_current_winner(stage, "/arch/db") is None

    def test_assertion_never_deleted_after_retract(self):
        """Non-destructive invariant: retracted assertions stay in stage.assertions."""
        stage = CompositionStage(
            project_id="retract-test", project_name="Retract Test"
        )
        a = _make_local("/arch/db", "Use PostgreSQL")
        add_assertion(stage, a)
        retract_assertion(stage, a.id)

        assert a.id in stage.assertions
        assert stage.assertions[a.id].active is False


# ===========================================================================
# TestNoopCases
# ===========================================================================

class TestNoopCases:
    """Edge cases: operations that should NOT trigger cascades."""

    def test_no_dependents_no_cascade_on_winner_change(self):
        """Changing the winner at a path with no dependents fires zero cascades."""
        stage = CompositionStage(
            project_id="noop-test", project_name="Noop Test"
        )
        a = _make_inherits("/isolated/path", "Original claim")
        stage.assertions[a.id] = a

        b = Assertion(
            topic_path="/isolated/path",
            content="New claim",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="Falsified if new claim is disproved",
        )
        result = add_assertion(stage, b)

        assert result.winner_changed is True
        assert result.cascading_conflicts == []

    def test_weaker_assertion_does_not_cascade(self):
        """Inserting a weaker assertion that does not change the winner fires no cascades."""
        stage = CompositionStage(
            project_id="noop-test", project_name="Noop Test"
        )
        strong = _make_local("/arch/db", "Strong claim")
        dep = _make_inherits("/orm", "ORM claim", depends_on=["/arch/db"])
        stage.assertions[strong.id] = strong
        stage.assertions[dep.id] = dep

        weak = Assertion(
            topic_path="/arch/db",
            content="Weak claim",
            arc=CompositionArc.SPECIALIZES,
            author=AssertionAuthor.AI,
        )
        result = add_assertion(stage, weak)

        assert result.winner_changed is False
        assert result.cascading_conflicts == []
        assert dep.assumption_status == AssumptionStatus.LIVE


# ===========================================================================
# TestResolveMethodLIVRPS
# ===========================================================================

class TestResolveMethodLIVRPS:
    """Verify the CompositionStage.resolve() method returns correct LIVRPS ordering."""

    def test_resolve_single_path_returns_winner(self):
        """resolve() returns a dict entry for each path with a 'winning' key."""
        stage = CompositionStage(
            project_id="resolve-test", project_name="Resolve Test"
        )
        a = _make_local("/arch/db", "Use PostgreSQL")
        add_assertion(stage, a)

        resolved = stage.resolve()
        assert "/arch/db" in resolved
        assert resolved["/arch/db"]["winning"] is a

    def test_resolve_shadow_stack_excludes_winner(self):
        """shadow_stack contains the non-winning assertions sorted by strength."""
        stage = CompositionStage(
            project_id="resolve-test", project_name="Resolve Test"
        )
        local_a = _make_local("/arch/db", "Strong claim")
        inherits_b = _make_inherits("/arch/db", "Weaker claim")
        add_assertion(stage, local_a)
        add_assertion(stage, inherits_b)

        resolved = stage.resolve()
        entry = resolved["/arch/db"]

        assert entry["winning"] is local_a
        shadow_ids = [a.id for a in entry["shadow_stack"]]
        assert inherits_b.id in shadow_ids

    def test_resolve_path_filter_restricts_results(self):
        """resolve(path_filter='/arch') returns only paths starting with /arch."""
        stage = CompositionStage(
            project_id="resolve-test", project_name="Resolve Test"
        )
        arch = _make_local("/arch/db", "Use PostgreSQL")
        unrelated = _make_inherits("/compliance/gdpr", "GDPR requirement")
        add_assertion(stage, arch)
        add_assertion(stage, unrelated)

        resolved = stage.resolve(path_filter="/arch")

        assert "/arch/db" in resolved
        assert "/compliance/gdpr" not in resolved

    def test_resolve_excludes_inactive_assertions(self):
        """Retracted assertions are excluded from resolve() results."""
        stage = CompositionStage(
            project_id="resolve-test", project_name="Resolve Test"
        )
        a = _make_local("/arch/db", "Use PostgreSQL")
        add_assertion(stage, a)
        retract_assertion(stage, a.id)

        resolved = stage.resolve()
        # Path should not appear since the only assertion was retracted
        assert "/arch/db" not in resolved

    def test_resolve_active_conflicts_surfaced(self):
        """resolve() includes active conflicts in the result for the relevant path."""
        stage = CompositionStage(
            project_id="resolve-test", project_name="Resolve Test"
        )
        a = _make_inherits("/arch/db", "Use PostgreSQL")
        b = Assertion(
            topic_path="/arch/db",
            content="Use MySQL",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, a)
        add_assertion(stage, b)

        resolved = stage.resolve()
        entry = resolved["/arch/db"]

        assert len(entry["active_conflicts"]) >= 1

    def test_resolve_health_issues_includes_challenged(self):
        """resolve() health_issues includes CHALLENGED assertions."""
        stage = CompositionStage(
            project_id="resolve-test", project_name="Resolve Test"
        )
        a = _make_local("/arch/db", "Use PostgreSQL")
        b = _make_inherits("/arch/orm", "Use Prisma", depends_on=["/arch/db"])
        add_assertion(stage, a)
        add_assertion(stage, b)

        # Force B to be CHALLENGED
        b.assumption_status = AssumptionStatus.CHALLENGED

        resolved = stage.resolve()
        orm_entry = resolved["/arch/orm"]

        health_ids = [a.id for a in orm_entry["health_issues"]]
        assert b.id in health_ids
