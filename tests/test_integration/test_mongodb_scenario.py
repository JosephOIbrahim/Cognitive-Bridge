"""Integration test: The MongoDB scenario from Blueprint v3.0 Appendix A.

This test exercises the complete LIVRPS argumentation flow end-to-end:
Assert -> Detect -> Steelman -> Challenge -> Experiment -> Decide

The scenario: An AI asserts PostgreSQL. The user pushes back with MongoDB.
Cascading conflicts propagate to ORM and GDPR claims that depended on the
database choice. The debate is resolved via an experiment protocol.
"""

import pytest

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    CompositionStage,
    ConflictDetectionLayer,
    ConflictStatus,
    Decision,
    EventType,
    ResolutionPath,
)
from cognitive_bridge.engine.resolver import (
    ResolutionResult,
    add_assertion,
    falsify_assertion,
    get_current_winner,
    promote_assertion,
    resolve_conflict,
    retract_assertion,
)
from cognitive_bridge.engine.cascade import detect_cascading_conflicts
from cognitive_bridge.engine.provenance import (
    count_events_by_type,
    format_audit_trail,
    get_events_for_target,
)
from cognitive_bridge.engine.trust import compute_trust_scores
from cognitive_bridge.engine.red_team import (
    generate_red_team_report,
    should_trigger_red_team,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage(project_id: str = "mongodb-test") -> CompositionStage:
    return CompositionStage(
        project_id=project_id,
        project_name="MongoDB Scenario",
        exchange_count=1,
    )


# ===========================================================================
# TestMongoDBScenario
# ===========================================================================

class TestMongoDBScenario:
    """The full MongoDB scenario as described in Blueprint v3.0 Appendix A.

    Tests the complete argumentation pipeline step by step. Each step is
    an independent assertion so failures are easy to localise.
    """

    @pytest.fixture
    def stage(self) -> CompositionStage:
        return _make_stage()

    # -----------------------------------------------------------------------
    # Step 1: AI asserts PostgreSQL at LOCAL
    # -----------------------------------------------------------------------

    def test_step1_postgres_asserted_at_local(self, stage):
        """AI asserts 'Use PostgreSQL' at LOCAL with falsifiable_if. No conflict yet."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if=(
                "Falsified if P99 latency exceeds 200ms under 1000 concurrent connections"
            ),
            evidence=["ACID compliance", "mature ecosystem"],
        )
        result = add_assertion(stage, pg)

        assert result.structural_conflict is None
        assert result.winner_changed is False
        assert result.new_winner_id == pg.id

        winner = get_current_winner(stage, "/architecture/database/engine")
        assert winner is not None
        assert winner.content == "Use PostgreSQL"

    # -----------------------------------------------------------------------
    # Step 2: Prisma depends on database choice
    # -----------------------------------------------------------------------

    def test_step2_prisma_depends_on_database(self, stage):
        """AI asserts Prisma at /architecture/orm, depending on the database path."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        prisma = Assertion(
            topic_path="/architecture/orm",
            content="Use Prisma",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/database/engine"],
        )
        result = add_assertion(stage, prisma)

        assert result.structural_conflict is None
        assert prisma.id in stage.assertions
        assert prisma.assumption_status == AssumptionStatus.LIVE

    # -----------------------------------------------------------------------
    # Step 3: GDPR compliance depends on database
    # -----------------------------------------------------------------------

    def test_step3_gdpr_depends_on_database(self, stage):
        """AI asserts GDPR at /compliance/gdpr, depending on the database path."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        gdpr = Assertion(
            topic_path="/compliance/gdpr/strict_deletion",
            content="Row-level deletion guaranteed by PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if=(
                "Falsified if the chosen database cannot perform row-level deletion"
            ),
            depends_on_paths=["/architecture/database/engine"],
        )
        result = add_assertion(stage, gdpr)

        assert result.structural_conflict is None
        assert gdpr.assumption_status == AssumptionStatus.LIVE

    # -----------------------------------------------------------------------
    # Step 4: User asserts MongoDB — structural conflict
    # -----------------------------------------------------------------------

    def test_step4_mongodb_triggers_structural_conflict(self, stage):
        """User asserts MongoDB at REFERENCES. Structural conflict detected against PostgreSQL."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        result = add_assertion(stage, mongo)

        assert result.structural_conflict is not None
        conflict = result.structural_conflict
        assert conflict.detection_layer == ConflictDetectionLayer.STRUCTURAL
        assert conflict.topic_path == "/architecture/database/engine"
        ids = {conflict.assertion_a_id, conflict.assertion_b_id}
        assert pg.id in ids
        assert mongo.id in ids

    def test_step4_postgres_still_wins_at_references(self, stage):
        """LOCAL (10) beats REFERENCES (40): PostgreSQL is still the winner."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        result = add_assertion(stage, mongo)

        assert result.winner_changed is False
        winner = get_current_winner(stage, "/architecture/database/engine")
        assert winner.content == "Use PostgreSQL"

    def test_step4_no_cascade_because_winner_unchanged(self, stage):
        """Winner unchanged at REFERENCES arc → no cascading conflicts yet."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        prisma = Assertion(
            topic_path="/architecture/orm",
            content="Use Prisma",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/database/engine"],
        )
        add_assertion(stage, prisma)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        result = add_assertion(stage, mongo)

        assert result.cascading_conflicts == []
        assert prisma.assumption_status == AssumptionStatus.LIVE

    # -----------------------------------------------------------------------
    # Step 5: Promote MongoDB to LOCAL — winner changes, cascades fire
    # -----------------------------------------------------------------------

    def test_step5_promote_mongodb_changes_winner(self, stage):
        """Promoting MongoDB to LOCAL changes the winner (newer = tiebreak)."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, mongo)

        # Promote MongoDB: now both are LOCAL (10). MongoDB is newer → wins.
        mongo.falsifiable_if = "Falsified if MongoDB cannot satisfy GDPR deletion requirements"
        result = promote_assertion(
            stage,
            mongo.id,
            CompositionArc.LOCAL,
            evidence="MongoDB benchmarks show 3x write throughput for our use case",
        )

        new_winner = get_current_winner(stage, "/architecture/database/engine")
        assert new_winner.id == mongo.id
        assert result.winner_changed is True

    def test_step5_cascades_fire_when_winner_changes(self, stage):
        """After MongoDB wins, ORM and GDPR assertions are CHALLENGED."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        prisma = Assertion(
            topic_path="/architecture/orm",
            content="Use Prisma",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/database/engine"],
        )
        add_assertion(stage, prisma)

        gdpr = Assertion(
            topic_path="/compliance/gdpr/strict_deletion",
            content="Row-level deletion guaranteed by PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if chosen database cannot perform row-level deletion",
            depends_on_paths=["/architecture/database/engine"],
        )
        add_assertion(stage, gdpr)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, mongo)

        mongo.falsifiable_if = "Falsified if MongoDB cannot satisfy GDPR deletion requirements"
        result = promote_assertion(
            stage,
            mongo.id,
            CompositionArc.LOCAL,
            evidence="MongoDB benchmarks show 3x write throughput",
        )

        # Both dependents must be CHALLENGED
        assert prisma.assumption_status == AssumptionStatus.CHALLENGED
        assert gdpr.assumption_status == AssumptionStatus.CHALLENGED
        # At least two cascading conflicts
        assert len(result.cascading_conflicts) >= 2
        cascade_b_ids = {c.assertion_b_id for c in result.cascading_conflicts}
        assert prisma.id in cascade_b_ids
        assert gdpr.id in cascade_b_ids

    # -----------------------------------------------------------------------
    # Step 6: Steelman gate — challenge requires steelman_summary
    # -----------------------------------------------------------------------

    def test_step6_challenge_without_steelman_rejected(self, stage):
        """CHALLENGE resolution without steelman_summary raises ValueError."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        result = add_assertion(stage, mongo)
        conflict = result.structural_conflict
        assert conflict is not None

        with pytest.raises(ValueError, match="steelman_summary"):
            resolve_conflict(stage, conflict.id, ResolutionPath.CHALLENGE)

    def test_step6_challenge_with_steelman_stores_summary(self, stage):
        """CHALLENGE with steelman_summary stores it on the conflict and keeps ACTIVE."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        result = add_assertion(stage, mongo)
        conflict = result.structural_conflict

        steelman = (
            "MongoDB offers superior write throughput for document-heavy workloads. "
            "The user's benchmark data shows 3x improvement, which is significant "
            "for our expected write patterns."
        )
        resolved = resolve_conflict(
            stage,
            conflict.id,
            ResolutionPath.CHALLENGE,
            steelman_summary=steelman,
            note="However, ACID guarantees are critical for our compliance requirements.",
        )

        assert resolved.status == ConflictStatus.ACTIVE
        assert resolved.steelman_of_opponent == steelman
        assert resolved.resolved_at is None

    # -----------------------------------------------------------------------
    # Step 7: Propose experiment
    # -----------------------------------------------------------------------

    def test_step7_experiment_without_protocol_rejected(self, stage):
        """PROPOSE_EXPERIMENT without experiment_protocol raises ValueError."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        result = add_assertion(stage, mongo)
        conflict = result.structural_conflict

        with pytest.raises(ValueError, match="experiment_protocol"):
            resolve_conflict(
                stage, conflict.id, ResolutionPath.PROPOSE_EXPERIMENT
            )

    def test_step7_experiment_with_protocol_deferred(self, stage):
        """PROPOSE_EXPERIMENT with protocol sets RESOLVED_EXPERIMENT and stores protocol."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        result = add_assertion(stage, mongo)
        conflict = result.structural_conflict

        protocol = (
            "Run both PostgreSQL and MongoDB against our production write pattern "
            "(1000 concurrent connections, mixed read/write) for 24 hours. "
            "Measure P99 latency, throughput, and verify GDPR deletion compliance."
        )
        resolved = resolve_conflict(
            stage,
            conflict.id,
            ResolutionPath.PROPOSE_EXPERIMENT,
            experiment_protocol=protocol,
        )

        assert resolved.status == ConflictStatus.RESOLVED_EXPERIMENT
        assert resolved.experiment_protocol == protocol
        assert resolved.resolved_at is not None

    # -----------------------------------------------------------------------
    # Step 8: Decision recorded
    # -----------------------------------------------------------------------

    def test_step8_decision_requires_alternatives_and_second_order_effects(self):
        """Decision model raises ValueError when alternatives_rejected is empty."""
        with pytest.raises(Exception):
            Decision(
                topic_path="/architecture/database/engine",
                decision="Use MongoDB",
                rationale="Better throughput",
                alternatives_rejected=[],          # must be min_length=1
                second_order_effects=["Dual DB"],
            )

    def test_step8_decision_requires_second_order_effects(self):
        """Decision model raises ValueError when second_order_effects is empty."""
        with pytest.raises(Exception):
            Decision(
                topic_path="/architecture/database/engine",
                decision="Use MongoDB",
                rationale="Better throughput",
                alternatives_rejected=["PostgreSQL only — rejected because latency"],
                second_order_effects=[],           # must be min_length=1
            )

    def test_step8_valid_decision_stored_on_stage(self, stage):
        """A complete Decision with alternatives and second-order effects is stored."""
        decision = Decision(
            topic_path="/architecture/database/engine",
            decision="Use MongoDB with PostgreSQL for compliance-critical tables",
            rationale="MongoDB wins on throughput; PostgreSQL wins on compliance.",
            alternatives_rejected=[
                "PostgreSQL only — rejected because 3x throughput penalty",
                "MongoDB only — rejected because GDPR compliance risk",
            ],
            second_order_effects=[
                "Must maintain two database connections in the application layer",
                "ORM strategy must support both document and relational patterns",
            ],
            reversibility="costly",
        )
        stage.decisions.append(decision)

        assert len(stage.decisions) == 1
        assert stage.decisions[0].decision == decision.decision
        assert len(stage.decisions[0].alternatives_rejected) == 2
        assert len(stage.decisions[0].second_order_effects) == 2

    # -----------------------------------------------------------------------
    # Full scenario (steps combined)
    # -----------------------------------------------------------------------

    def test_full_scenario_end_to_end(self, stage):
        """Run all eight steps of the MongoDB scenario in sequence."""
        # --- Step 1: AI asserts PostgreSQL ---
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if=(
                "Falsified if P99 latency exceeds 200ms under 1000 concurrent connections"
            ),
            evidence=["ACID compliance", "mature ecosystem"],
        )
        r1 = add_assertion(stage, pg)
        assert r1.structural_conflict is None
        assert r1.winner_changed is False

        # --- Step 2: AI asserts Prisma ---
        prisma = Assertion(
            topic_path="/architecture/orm",
            content="Use Prisma",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/database/engine"],
        )
        r2 = add_assertion(stage, prisma)
        assert r2.structural_conflict is None

        # --- Step 3: AI asserts GDPR row-deletion ---
        gdpr = Assertion(
            topic_path="/compliance/gdpr/strict_deletion",
            content="Row-level deletion guaranteed by PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if=(
                "Falsified if the chosen database cannot perform row-level deletion"
            ),
            depends_on_paths=["/architecture/database/engine"],
        )
        r3 = add_assertion(stage, gdpr)
        assert r3.structural_conflict is None

        # --- Step 4: User asserts MongoDB at REFERENCES ---
        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        r4 = add_assertion(stage, mongo)

        # Structural conflict detected
        assert r4.structural_conflict is not None
        assert r4.structural_conflict.detection_layer == ConflictDetectionLayer.STRUCTURAL

        # PostgreSQL (LOCAL=10) still wins over MongoDB (REFERENCES=40)
        assert r4.winner_changed is False
        winner = get_current_winner(stage, "/architecture/database/engine")
        assert winner.content == "Use PostgreSQL"

        # No cascades yet — winner did not change
        assert r4.cascading_conflicts == []

        # --- Step 5: Promote MongoDB to LOCAL (winner changes, cascades fire) ---
        mongo.falsifiable_if = (
            "Falsified if MongoDB cannot satisfy GDPR deletion requirements"
        )
        r5 = promote_assertion(
            stage,
            mongo.id,
            CompositionArc.LOCAL,
            evidence="MongoDB benchmarks show 3x write throughput",
        )

        # MongoDB (newer LOCAL) wins
        new_winner = get_current_winner(stage, "/architecture/database/engine")
        assert new_winner.id == mongo.id
        assert r5.winner_changed is True

        # Cascades: Prisma and GDPR are CHALLENGED
        assert prisma.assumption_status == AssumptionStatus.CHALLENGED
        assert gdpr.assumption_status == AssumptionStatus.CHALLENGED
        assert len(r5.cascading_conflicts) >= 2

        # --- Step 6: AI steelmans and challenges ---
        db_conflict = r4.structural_conflict
        steelman = (
            "MongoDB offers superior write throughput for document-heavy workloads "
            "with 3x improvement in our benchmark."
        )
        challenged = resolve_conflict(
            stage,
            db_conflict.id,
            ResolutionPath.CHALLENGE,
            steelman_summary=steelman,
        )
        assert challenged.status == ConflictStatus.ACTIVE  # debate continues
        assert challenged.steelman_of_opponent == steelman

        # --- Step 7: Propose experiment ---
        protocol = (
            "Run both PostgreSQL and MongoDB against production write pattern "
            "for 24 hours. Measure P99 latency and GDPR deletion compliance."
        )
        exp_conflict = resolve_conflict(
            stage,
            db_conflict.id,
            ResolutionPath.PROPOSE_EXPERIMENT,
            experiment_protocol=protocol,
        )
        assert exp_conflict.status == ConflictStatus.RESOLVED_EXPERIMENT

        # --- Step 8: Decision recorded ---
        decision = Decision(
            topic_path="/architecture/database/engine",
            decision="Use MongoDB with PostgreSQL for compliance-critical tables",
            rationale="MongoDB wins on throughput; PostgreSQL on compliance.",
            alternatives_rejected=[
                "PostgreSQL only — rejected because 3x throughput penalty",
                "MongoDB only — rejected because GDPR compliance risk",
            ],
            second_order_effects=[
                "Must maintain two DB connections",
                "ORM must support document + relational patterns",
            ],
            reversibility="costly",
        )
        stage.decisions.append(decision)

        # --- Final state assertions ---
        assert len(stage.assertions) >= 4
        assert len(stage.conflicts) >= 3  # structural + 2 cascading
        assert len(stage.decisions) == 1
        assert len(stage.events) >= 5

        # Trust scores for contested path
        trust_scores = compute_trust_scores(stage)
        assert "/architecture/database/engine" in trust_scores

        # Audit trail for PostgreSQL assertion
        pg_trail = get_events_for_target(stage, pg.id)
        assert len(pg_trail) >= 1

        # Event counts sanity
        counts = count_events_by_type(stage)
        assert "assertion_created" in counts
        assert "conflict_detected" in counts

    # -----------------------------------------------------------------------
    # Provenance and audit trail
    # -----------------------------------------------------------------------

    def test_audit_trail_non_empty_for_pg_assertion(self, stage):
        """PostgreSQL assertion has at least one event in its audit trail."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        trail = get_events_for_target(stage, pg.id)
        assert len(trail) >= 1
        assert trail[0].event_type == EventType.ASSERTION_CREATED

    def test_format_audit_trail_returns_string(self, stage):
        """format_audit_trail returns a non-empty string after assertions are added."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        trail = format_audit_trail(stage, pg.id)
        assert isinstance(trail, str)
        assert "assertion_created" in trail

    def test_conflict_event_recorded_in_counts(self, stage):
        """count_events_by_type includes conflict_detected after a structural conflict."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, mongo)

        counts = count_events_by_type(stage)
        assert "conflict_detected" in counts
        assert counts["conflict_detected"] >= 1

    # -----------------------------------------------------------------------
    # Trust calibration
    # -----------------------------------------------------------------------

    def test_trust_score_present_after_conflict(self, stage):
        """A conflict at a path creates a trust score entry for that path."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, mongo)

        scores = compute_trust_scores(stage)
        assert "/architecture/database/engine" in scores

    def test_trust_score_increases_after_experiment_resolution(self, stage):
        """Resolving a conflict via PROPOSE_EXPERIMENT increases trust score."""
        pg = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        add_assertion(stage, pg)

        mongo = Assertion(
            topic_path="/architecture/database/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        result = add_assertion(stage, mongo)
        conflict = result.structural_conflict

        score_before = compute_trust_scores(stage)["/architecture/database/engine"]

        resolve_conflict(
            stage,
            conflict.id,
            ResolutionPath.PROPOSE_EXPERIMENT,
            experiment_protocol="24hr benchmark with P99 measurement",
        )

        score_after = compute_trust_scores(stage)["/architecture/database/engine"]
        assert score_after.score > score_before.score


# ===========================================================================
# TestCascadeChain
# ===========================================================================

class TestCascadeChain:
    """Test cascading through a linear dependency chain: A -> B -> C."""

    def test_linear_chain_a_change_challenges_b_not_c_directly(self):
        """A -> B -> C: changing A challenges B. C is not a direct dependent of A."""
        stage = CompositionStage(project_id="chain-test", project_name="Chain Test")

        a = Assertion(
            topic_path="/foundation",
            content="Foundation claim",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if foundation is disproved",
        )
        b = Assertion(
            topic_path="/midlayer",
            content="Mid-layer claim",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/foundation"],
        )
        c = Assertion(
            topic_path="/leaf",
            content="Leaf claim",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/midlayer"],
        )

        for ast in (a, b, c):
            stage.assertions[ast.id] = ast

        # Insert a competing claim at /foundation to displace A
        a2 = Assertion(
            topic_path="/foundation",
            content="New foundation claim",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="Falsified if new foundation is disproved",
        )
        result = add_assertion(stage, a2)

        # a2 is newer LOCAL — wins over a
        assert result.winner_changed is True

        # B depends on /foundation — must be CHALLENGED
        assert b.assumption_status == AssumptionStatus.CHALLENGED
        # C depends on /midlayer (not /foundation) — not yet CHALLENGED
        assert c.assumption_status == AssumptionStatus.LIVE

    def test_linear_chain_b_change_challenges_c(self):
        """After B changes, C is CHALLENGED."""
        stage = CompositionStage(project_id="chain-test", project_name="Chain Test")

        b = Assertion(
            topic_path="/midlayer",
            content="Mid-layer claim",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        c = Assertion(
            topic_path="/leaf",
            content="Leaf claim",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/midlayer"],
        )
        for ast in (b, c):
            stage.assertions[ast.id] = ast

        b2 = Assertion(
            topic_path="/midlayer",
            content="New mid-layer claim",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="Falsified if new mid-layer is disproved",
        )
        result = add_assertion(stage, b2)

        assert result.winner_changed is True
        assert c.assumption_status == AssumptionStatus.CHALLENGED

    def test_five_level_deep_chain_first_level_cascades(self):
        """A 5-level chain: changing level 1 directly challenges only level 2."""
        stage = CompositionStage(project_id="deep-chain", project_name="Deep Chain")
        paths = [f"/level{i}" for i in range(1, 6)]

        assertions = []
        for i, path in enumerate(paths):
            dep = [paths[i - 1]] if i > 0 else []
            a = Assertion(
                topic_path=path,
                content=f"Claim at level {i + 1}",
                arc=CompositionArc.INHERITS,
                author=AssertionAuthor.AI,
                depends_on_paths=dep,
            )
            stage.assertions[a.id] = a
            assertions.append(a)

        # Insert a competing claim at level 1 that displaces the current winner
        new_l1 = Assertion(
            topic_path="/level1",
            content="New level 1 claim",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            falsifiable_if="Falsified if new L1 claim is disproved",
        )
        result = add_assertion(stage, new_l1)

        # Level 2 depends on /level1 — must be CHALLENGED
        assert assertions[1].assumption_status == AssumptionStatus.CHALLENGED
        # Deeper levels are not direct dependents of /level1
        for lvl in assertions[2:]:
            assert lvl.assumption_status == AssumptionStatus.LIVE


# ===========================================================================
# TestFalsificationCascade
# ===========================================================================

class TestFalsificationCascade:
    """Falsifying an assertion orphans all dependents."""

    def test_falsify_foundation_orphans_dependents(self):
        """Falsifying a LOCAL assertion with dependents marks all dependents ORPHANED."""
        stage = CompositionStage(project_id="falsify-test", project_name="Falsify Test")

        foundation = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        orm = Assertion(
            topic_path="/architecture/orm",
            content="Use Prisma",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/database/engine"],
        )
        gdpr = Assertion(
            topic_path="/compliance/gdpr/strict_deletion",
            content="Row-level deletion guaranteed by PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if chosen database cannot perform row-level deletion",
            depends_on_paths=["/architecture/database/engine"],
        )
        for ast in (foundation, orm, gdpr):
            stage.assertions[ast.id] = ast

        result = falsify_assertion(
            stage,
            foundation.id,
            "P99 latency measured at 450ms under 1000 concurrent connections",
        )

        # Foundation is now FALSIFIED and inactive
        assert foundation.assumption_status == AssumptionStatus.FALSIFIED
        assert foundation.active is False

        # Dependents are ORPHANED
        assert orm.assumption_status == AssumptionStatus.ORPHANED
        assert gdpr.assumption_status == AssumptionStatus.ORPHANED

    def test_falsify_records_falsified_and_orphaned_events(self):
        """ASSERTION_FALSIFIED and ASSERTION_ORPHANED events are recorded."""
        stage = CompositionStage(project_id="falsify-test", project_name="Falsify Test")

        foundation = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        orm = Assertion(
            topic_path="/architecture/orm",
            content="Use Prisma",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
            depends_on_paths=["/architecture/database/engine"],
        )
        for ast in (foundation, orm):
            stage.assertions[ast.id] = ast

        falsify_assertion(
            stage, foundation.id, "P99 latency exceeded 200ms threshold"
        )

        event_types = {e.event_type for e in stage.events}
        assert EventType.ASSERTION_FALSIFIED in event_types
        assert EventType.ASSERTION_ORPHANED in event_types

    def test_falsify_non_falsifiable_assertion_raises(self):
        """Calling falsify_assertion on an assertion with no falsifiable_if raises ValueError."""
        stage = CompositionStage(project_id="falsify-test", project_name="Falsify Test")
        a = Assertion(
            topic_path="/service/cache",
            content="Use Redis",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        stage.assertions[a.id] = a

        with pytest.raises(ValueError, match="no falsifiable_if"):
            falsify_assertion(stage, a.id, "Redis was slow")

    def test_falsified_assertion_remains_in_stage(self):
        """Non-destructive invariant: falsified assertions stay in stage.assertions."""
        stage = CompositionStage(project_id="falsify-test", project_name="Falsify Test")
        a = Assertion(
            topic_path="/architecture/database/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.AI,
            falsifiable_if="Falsified if P99 latency exceeds 200ms",
        )
        stage.assertions[a.id] = a

        falsify_assertion(stage, a.id, "P99 exceeded 200ms")

        assert a.id in stage.assertions
        assert stage.assertions[a.id].assumption_status == AssumptionStatus.FALSIFIED


# ===========================================================================
# TestSteelmanGateEnforcement
# ===========================================================================

class TestSteelmanGateEnforcement:
    """The steelman gate must reject challenges without comprehension of the opponent."""

    def _stage_with_active_conflict(self) -> tuple[CompositionStage, object]:
        stage = CompositionStage(
            project_id="steelman-test", project_name="Steelman Test"
        )
        a = Assertion(
            topic_path="/tech/framework",
            content="Use React",
            arc=CompositionArc.INHERITS,
            author=AssertionAuthor.AI,
        )
        b = Assertion(
            topic_path="/tech/framework",
            content="Use Vue",
            arc=CompositionArc.REFERENCES,
            author=AssertionAuthor.USER,
        )
        add_assertion(stage, a)
        result = add_assertion(stage, b)
        return stage, result.structural_conflict

    def test_challenge_without_steelman_raises_value_error(self):
        """CHALLENGE without steelman_summary raises ValueError with descriptive message."""
        stage, conflict = self._stage_with_active_conflict()

        with pytest.raises(ValueError) as exc_info:
            resolve_conflict(stage, conflict.id, ResolutionPath.CHALLENGE)

        assert "steelman_summary" in str(exc_info.value)
        assert "Comprehension before critique" in str(exc_info.value)

    def test_challenge_with_empty_steelman_raises_value_error(self):
        """CHALLENGE with an empty string steelman_summary also raises ValueError."""
        stage, conflict = self._stage_with_active_conflict()

        with pytest.raises(ValueError, match="steelman_summary"):
            resolve_conflict(
                stage,
                conflict.id,
                ResolutionPath.CHALLENGE,
                steelman_summary="",
            )

    def test_challenge_with_valid_steelman_succeeds(self):
        """CHALLENGE with a non-empty steelman_summary succeeds and stores the steelman."""
        stage, conflict = self._stage_with_active_conflict()
        steelman = "Vue offers a simpler learning curve and reactivity model than React."

        resolved = resolve_conflict(
            stage,
            conflict.id,
            ResolutionPath.CHALLENGE,
            steelman_summary=steelman,
        )

        assert resolved.steelman_of_opponent == steelman
        assert resolved.status == ConflictStatus.ACTIVE  # debate continues

    def test_experiment_without_protocol_raises_value_error(self):
        """PROPOSE_EXPERIMENT without protocol raises ValueError with descriptive message."""
        stage, conflict = self._stage_with_active_conflict()

        with pytest.raises(ValueError) as exc_info:
            resolve_conflict(stage, conflict.id, ResolutionPath.PROPOSE_EXPERIMENT)

        assert "experiment_protocol" in str(exc_info.value)
        assert "empirically" in str(exc_info.value)

    def test_experiment_with_valid_protocol_resolves_experiment(self):
        """PROPOSE_EXPERIMENT with a valid protocol closes the conflict as RESOLVED_EXPERIMENT."""
        stage, conflict = self._stage_with_active_conflict()
        protocol = "Build identical features in React and Vue. Measure dev velocity over 2 sprints."

        resolved = resolve_conflict(
            stage,
            conflict.id,
            ResolutionPath.PROPOSE_EXPERIMENT,
            experiment_protocol=protocol,
        )

        assert resolved.status == ConflictStatus.RESOLVED_EXPERIMENT
        assert resolved.experiment_protocol == protocol


# ===========================================================================
# TestDecisionAntiConvergence
# ===========================================================================

class TestDecisionAntiConvergence:
    """Decisions must account for alternatives and second-order effects."""

    def test_decision_without_alternatives_rejected_raises(self):
        """Creating a Decision with empty alternatives_rejected raises validation error."""
        with pytest.raises(Exception):
            Decision(
                topic_path="/architecture/database/engine",
                decision="Use PostgreSQL",
                rationale="Best fit for ACID requirements",
                alternatives_rejected=[],
                second_order_effects=["Need DBA expertise"],
            )

    def test_decision_without_second_order_effects_raises(self):
        """Creating a Decision with empty second_order_effects raises validation error."""
        with pytest.raises(Exception):
            Decision(
                topic_path="/architecture/database/engine",
                decision="Use PostgreSQL",
                rationale="Best fit for ACID requirements",
                alternatives_rejected=["MongoDB — rejected because ACID"],
                second_order_effects=[],
            )

    def test_valid_decision_succeeds(self):
        """A Decision with both fields populated is created without error."""
        decision = Decision(
            topic_path="/architecture/database/engine",
            decision="Use PostgreSQL",
            rationale="Best fit for ACID and compliance requirements",
            alternatives_rejected=[
                "MongoDB — rejected because eventual consistency risk",
                "MySQL — rejected because weaker JSON support",
            ],
            second_order_effects=[
                "Need DBA expertise on team",
                "GDPR deletion must be validated with row-level delete tests",
            ],
            reversibility="costly",
        )

        assert len(decision.alternatives_rejected) == 2
        assert len(decision.second_order_effects) == 2
        assert decision.reversibility == "costly"

    def test_decision_auto_stored_on_stage(self):
        """Appending a valid Decision to stage.decisions works correctly."""
        stage = CompositionStage(
            project_id="decision-test", project_name="Decision Test"
        )
        decision = Decision(
            topic_path="/architecture/database/engine",
            decision="Use PostgreSQL",
            rationale="ACID compliance required",
            alternatives_rejected=["MongoDB — rejected because eventual consistency"],
            second_order_effects=["Requires DBA on team"],
        )
        stage.decisions.append(decision)

        assert len(stage.decisions) == 1
        assert stage.decisions[0].id == decision.id
