#!/usr/bin/env python3
"""The MongoDB Scenario -- full v3.0 showcase.

From Blueprint v3.0 Appendix A:
A project starts with PostgreSQL assumptions. The user proposes MongoDB.
This triggers cascading conflicts across the dependency DAG, steelman-gated
challenges, and eventually a hybrid experiment proposal.

This is the definitive integration demonstration of the Cognitive Bridge.
It exercises every v3.0 mechanic:
- Falsifiability gate (LOCAL assertions)
- Dependency DAG construction
- Layer 1 structural conflict detection
- Layer 4 cascading conflict detection (winner change propagates)
- Steelman gate (CHALLENGE requires articulating the opposing view)
- Experiment gate (PROPOSE_EXPERIMENT requires concrete protocol)
- Falsification (GDPR scoping decision kills a LOCAL claim)
- Decision recording with alternatives and second-order effects
- Trust scoring after conflict resolution history
- RED TEAM analysis (anti-echo-chamber posture check)

Run with: python examples/mongodb_scenario.py
"""

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    CompositionStage,
    Decision,
    ResolutionPath,
)
from cognitive_bridge.engine.resolver import (
    add_assertion,
    falsify_assertion,
    resolve_conflict,
)
from cognitive_bridge.engine.provenance import (
    count_events_by_type,
    format_audit_trail,
    get_conflict_resolution_history,
)
from cognitive_bridge.engine.trust import format_trust_report
from cognitive_bridge.engine.red_team import (
    generate_red_team_report,
    record_red_team_trigger,
    should_trigger_red_team,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def step(n: int, title: str) -> None:
    width = 70
    print(f"\n{'=' * width}")
    print(f"  Step {n}: {title}")
    print(f"{'=' * width}")


def show_stage_summary(stage: CompositionStage) -> None:
    resolved = stage.resolve()
    active_conflicts = [c for c in stage.conflicts.values() if c.status.value == "active"]
    print(f"  Stage snapshot: {len(resolved)} paths | "
          f"{sum(1 for a in stage.assertions.values() if a.active)} active assertions | "
          f"{len(active_conflicts)} active conflicts")


def show_assumption_health(stage: CompositionStage) -> None:
    challenged = [
        a for a in stage.assertions.values()
        if a.active and a.assumption_status == AssumptionStatus.CHALLENGED
    ]
    orphaned = [
        a for a in stage.assertions.values()
        if a.active and a.assumption_status == AssumptionStatus.ORPHANED
    ]
    falsified = [
        a for a in stage.assertions.values()
        if a.assumption_status == AssumptionStatus.FALSIFIED
    ]
    if challenged or orphaned or falsified:
        print(f"  Assumption health issues:")
        for a in challenged:
            print(f"    CHALLENGED: {a.topic_path} -- '{a.content}'")
        for a in orphaned:
            print(f"    ORPHANED  : {a.topic_path} -- '{a.content}'")
        for a in falsified:
            print(f"    FALSIFIED : {a.topic_path} -- '{a.content}'")
    else:
        print(f"  Assumption health: all LIVE")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  The MongoDB Scenario -- Blueprint v3.0 Appendix A")
    print("  Full integration demonstration of the Cognitive Bridge")
    print("=" * 70)
    print()
    print("  Scenario: The AI has been designing a user-profiles service.")
    print("  The stage encodes the current architectural state. The user")
    print("  proposes switching from PostgreSQL to MongoDB for faster iteration.")
    print("  This is not a simple preference -- it cascades through three")
    print("  downstream architectural dependencies.")

    # -- Create the composition stage ----------------------------------------
    stage = CompositionStage(
        project_id="user-profiles-service",
        project_name="User Profiles Service",
        exchange_count=5,  # Several exchanges have already occurred
    )

    # -- Step 1: AI builds the PostgreSQL foundation -------------------------
    step(1, "AI asserts PostgreSQL as the database engine (LOCAL -- verified)")

    db_engine = Assertion(
        topic_path="/architecture/database/engine",
        content="Use PostgreSQL for the user-profiles service",
        arc=CompositionArc.LOCAL,
        author=AssertionAuthor.AI,
        falsifiable_if="P99 latency exceeds 200ms at 1000 concurrent connections",
        evidence=["Benchmark: 50k reads/sec at P99 < 100ms on PostgreSQL 15"],
        confidence=0.9,
        tags=["database", "foundation"],
    )
    add_assertion(stage, db_engine)
    print(f"  [{db_engine.arc.name}] {db_engine.topic_path}")
    print(f"  Content       : '{db_engine.content}'")
    print(f"  Falsifiable if: '{db_engine.falsifiable_if}'")
    print(f"  Evidence      : {db_engine.evidence}")
    show_stage_summary(stage)

    # -- Step 2: AI asserts Prisma ORM (depends on database engine) ----------
    step(2, "AI asserts Prisma ORM -- depends on database engine choice")

    orm = Assertion(
        topic_path="/architecture/orm",
        content="Use Prisma ORM for type-safe database access",
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        depends_on_paths=["/architecture/database/engine"],
        evidence=["Prisma generates TypeScript types from schema -- zero-runtime overhead"],
        confidence=0.8,
        tags=["orm", "database"],
    )
    add_assertion(stage, orm)
    print(f"  [{orm.arc.name}] {orm.topic_path}")
    print(f"  Content    : '{orm.content}'")
    print(f"  depends_on : {orm.depends_on_paths}")
    show_stage_summary(stage)

    # -- Step 3: AI asserts GDPR compliance (depends on database engine) -----
    step(3, "AI asserts GDPR strict-deletion requirement -- depends on database engine")

    gdpr = Assertion(
        topic_path="/compliance/gdpr/strict_deletion",
        content="Must support guaranteed row-level deletion for GDPR",
        arc=CompositionArc.LOCAL,
        author=AssertionAuthor.AI,
        falsifiable_if="GDPR compliance is de-scoped from MVP requirements",
        evidence=[
            "GDPR Art. 17 requires deletion within 30 days of user request",
            "PostgreSQL row-level DELETE is atomic and immediately reflected in backups",
        ],
        depends_on_paths=["/architecture/database/engine"],
        confidence=0.95,
        tags=["compliance", "gdpr"],
    )
    add_assertion(stage, gdpr)
    print(f"  [{gdpr.arc.name}] {gdpr.topic_path}")
    print(f"  Content       : '{gdpr.content}'")
    print(f"  Falsifiable if: '{gdpr.falsifiable_if}'")
    print(f"  depends_on    : {gdpr.depends_on_paths}")
    show_stage_summary(stage)

    # -- Step 4: AI asserts GraphQL schema (depends on ORM) ------------------
    step(4, "AI asserts Prisma-generated GraphQL schema -- transitive dependency")

    gql_schema = Assertion(
        topic_path="/architecture/api/schema",
        content="Use Prisma-generated GraphQL schema",
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        depends_on_paths=["/architecture/orm"],
        evidence=["Prisma + nexus-prisma generates schema from DB types automatically"],
        confidence=0.75,
        tags=["api", "graphql"],
    )
    add_assertion(stage, gql_schema)
    print(f"  [{gql_schema.arc.name}] {gql_schema.topic_path}")
    print(f"  Content   : '{gql_schema.content}'")
    print(f"  depends_on: {gql_schema.depends_on_paths}")

    print()
    print("  Full dependency graph:")
    print("    /architecture/database/engine  (PostgreSQL -- LOCAL, no deps)")
    print("         |")
    print("         +---> /architecture/orm        (Prisma -- INHERITS)")
    print("         |          |")
    print("         |          +---> /architecture/api/schema  (GraphQL -- INHERITS)")
    print("         |")
    print("         +---> /compliance/gdpr/strict_deletion  (LOCAL)")
    print()

    dep_chain = stage.get_dependency_chain(gql_schema.id)
    print(f"  Dependency chain for GraphQL schema: {dep_chain}")
    show_stage_summary(stage)
    show_assumption_health(stage)

    # -- Step 5: User proposes MongoDB ---------------------------------------
    step(5, "User proposes MongoDB -- Layer 1 structural conflict + Layer 4 cascade")

    print('  User: "Let\'s rip out Postgres and use MongoDB for user-profiles.')
    print('         We need to ship fast -- schema migrations are killing us."')
    print()

    user_mongodb = Assertion(
        topic_path="/architecture/database/engine",
        content="Use MongoDB for user-profiles",
        arc=CompositionArc.REFERENCES,
        author=AssertionAuthor.USER,
        evidence=["Need to iterate fast on schema -- MongoDB allows rapid evolution without migrations"],
        confidence=0.7,
        tags=["database", "mongodb"],
    )
    result = add_assertion(stage, user_mongodb)

    print(f"  Added: [{user_mongodb.arc.name}] '{user_mongodb.content}'")
    print()

    # Show the structural conflict
    if result.structural_conflict:
        cfl = result.structural_conflict
        side_a = stage.assertions[cfl.assertion_a_id]
        side_b = stage.assertions[cfl.assertion_b_id]
        print(f"  LAYER 1 -- Structural conflict at {cfl.topic_path}:")
        print(f"    [{side_a.arc.name} | arc={side_a.arc.value}] {side_a.content}")
        print(f"    [{side_b.arc.name} | arc={side_b.arc.value}] {side_b.content}")
        print(f"    Current winner: [{side_a.arc.name}] (LOCAL=10 beats REFERENCES=40)")
        print()

    # Show winner status
    print(f"  Winner changed: {result.winner_changed}")
    if not result.winner_changed:
        print("  PostgreSQL LOCAL(10) still wins. MongoDB REFERENCES(40) is shadowed.")
        print("  A structural conflict is registered but PostgreSQL remains dominant.")
    print()

    # Show cascading (or lack thereof when winner does not change)
    if result.cascading_conflicts:
        print(f"  LAYER 4 -- Cascading conflicts ({len(result.cascading_conflicts)}):")
        for cfl in result.cascading_conflicts:
            dep = stage.assertions[cfl.assertion_b_id]
            print(f"    {dep.topic_path}: '{dep.content}'")
            print(f"      assumption_status -> {dep.assumption_status.value}")
    else:
        print("  LAYER 4 -- No cascades: winner at /architecture/database/engine did NOT change.")
        print("  Cascades fire only when the WINNER shifts, not when a weaker claim is added.")
        print("  PostgreSQL is still winning.")

    structural_conflict_id = result.structural_conflict.id if result.structural_conflict else None

    show_stage_summary(stage)

    # -- Step 6: Steelman gate -----------------------------------------------
    step(6, "Steelman gate -- AI must articulate MongoDB's strongest case before challenging")

    if structural_conflict_id:
        print("  The conflict requires AI to comprehend the opposing view before challenging.")
        print()
        print("  Attempting CHALLENGE without steelman_summary:")
        try:
            resolve_conflict(
                stage,
                structural_conflict_id,
                ResolutionPath.CHALLENGE,
            )
            print("  ERROR: Should have been rejected!")
        except ValueError as exc:
            print(f"  Gate enforced: {exc}")

        print()
        print("  AI articulates the steelman of the MongoDB argument:")
        steelman = (
            "MongoDB's schemaless document model allows rapid iteration on user-profile "
            "structures without migration overhead. For an MVP where the data model is "
            "evolving weekly, this eliminates a real friction point. The velocity argument "
            "is legitimate -- schema migrations are a measurable cost that MongoDB avoids. "
            "Embedded documents also simplify profile queries that otherwise require "
            "joins in PostgreSQL. The user is not wrong about the iteration speed benefit."
        )
        print()
        print(f"  Steelman: '{steelman[:100]}...'")

        resolve_conflict(
            stage,
            structural_conflict_id,
            ResolutionPath.CHALLENGE,
            steelman_summary=steelman,
            note=(
                "However, the PostgreSQL choice is structurally tied to three downstream "
                "decisions: Prisma ORM (does not support MongoDB), GDPR row-level deletion "
                "guarantee, and GraphQL schema generation. Switching cascades through all three."
            ),
        )
        cfl = stage.conflicts[structural_conflict_id]
        print(f"\n  Conflict status after CHALLENGE: {cfl.status.value}")
        print("  (Conflict remains ACTIVE -- the debate is open, not closed)")

    # -- Step 7: AI maps the blast radius ------------------------------------
    step(7, "AI maps the blast radius and presents two paths forward")

    print("  AI presents to user:")
    print()
    print('  "I completely agree that MongoDB\'s schemaless nature will let us iterate')
    print('   on profiles much faster for the MVP -- that\'s a real velocity win, not')
    print('   just a preference."')
    print()
    print('  "However, our PostgreSQL choice is structurally tied to three downstream')
    print('   decisions:"')
    print()

    orm_status = orm.assumption_status.value
    gdpr_status = gdpr.assumption_status.value
    gql_status = gql_schema.assumption_status.value
    print(f"    1. /architecture/orm        ({orm.content})")
    print(f"       Status: {orm_status} | Prisma does not support MongoDB")
    print(f"    2. /compliance/gdpr/strict_deletion ({gdpr.content})")
    print(f"       Status: {gdpr_status} | MongoDB lacks atomic row-level deletion")
    print(f"    3. /architecture/api/schema ({gql_schema.content})")
    print(f"       Status: {gql_status} | Depends transitively on ORM")
    print()
    print('  "I see two paths forward:"')
    print('  "- If GDPR compliance is de-scoped from MVP, that falsifies my GDPR claim')
    print('     and I will retract the PostgreSQL assertion."')
    print('  "- If GDPR stays in scope, I propose a benchmark experiment: measure')
    print('     PostgreSQL JSONB columns vs MongoDB for schema-flexible user profiles."')

    # -- Step 8: User de-scopes GDPR -----------------------------------------
    step(8, "User de-scopes GDPR -- falsification condition met, claim is falsified")

    print('  User: "GDPR is out of scope for MVP. We\'ll add it post-launch."')
    print()
    print(f"  GDPR assertion falsifiable_if: '{gdpr.falsifiable_if}'")
    print()

    falsify_assertion(
        stage,
        gdpr.id,
        observed_condition="User confirmed: GDPR compliance de-scoped from MVP. Post-launch feature.",
    )

    gdpr_updated = stage.assertions[gdpr.id]
    print(f"  GDPR assertion assumption_status: {gdpr_updated.assumption_status.value}")
    print(f"  GDPR assertion active            : {gdpr_updated.active}")
    print(f"  (Assertion deactivated but retained in stage -- non-destructive invariant)")
    print()

    # Show the audit trail for the GDPR assertion
    print("  Audit trail for GDPR assertion:")
    trail = format_audit_trail(stage, gdpr.id)
    print(trail)

    show_assumption_health(stage)

    # -- Step 9: Propose benchmark experiment --------------------------------
    step(9, "Propose benchmark experiment to settle the database question empirically")

    if structural_conflict_id:
        cfl = stage.conflicts[structural_conflict_id]
        if cfl.status.value == "active":
            protocol = (
                "72-hour parallel benchmark: identical user-profile workload on "
                "PostgreSQL 15 (JSONB columns for flexible fields) vs MongoDB 7. "
                "Workload: 80% reads (profile fetch by user_id), 20% writes (profile updates). "
                "Schema evolution test: add 3 new profile fields mid-benchmark. "
                "Metrics: migration time (PostgreSQL), query P50/P99, write throughput, "
                "developer iteration speed (story-point comparison). "
                "Decision criterion: MongoDB adopted if schema evolution overhead > 2 dev-days/week "
                "AND MongoDB P99 latency within 20% of PostgreSQL."
            )
            resolve_conflict(
                stage,
                structural_conflict_id,
                ResolutionPath.PROPOSE_EXPERIMENT,
                experiment_protocol=protocol,
                evidence="GDPR blocker removed. Benchmark can now settle the performance/velocity tradeoff.",
            )
            cfl = stage.conflicts[structural_conflict_id]
            print(f"  Conflict [{structural_conflict_id[:20]}...] status: {cfl.status.value}")
            print(f"  Experiment protocol length: {len(cfl.experiment_protocol)} chars")
            print()
            print(f"  Protocol summary:")
            print(f"    {protocol[:120]}...")

    # -- Step 10: Resolve the remaining cascading conflicts ------------------
    step(10, "Resolve cascading conflicts on Prisma ORM and GraphQL schema")

    # After GDPR falsification and experiment proposal, resolve the ORM cascade.
    # Defer them -- pending the benchmark experiment result.

    for conflict in list(stage.conflicts.values()):
        if conflict.status.value == "active":
            dep = stage.assertions.get(conflict.assertion_b_id)
            if dep:
                print(f"  Deferring conflict on {dep.topic_path}: '{dep.content}'")
            resolve_conflict(
                stage,
                conflict.id,
                ResolutionPath.DEFER,
                note="Awaiting benchmark experiment result before resolving ORM and schema implications.",
            )

    active_remaining = [c for c in stage.conflicts.values() if c.status.value == "active"]
    print(f"\n  Active conflicts remaining: {len(active_remaining)}")

    # -- Step 11: Record the final decision ----------------------------------
    step(11, "Record the architectural decision")

    resolved_conflict_ids = [c.id for c in stage.conflicts.values()]
    decision = Decision(
        topic_path="/architecture/database/engine",
        decision=(
            "Run 72-hour benchmark (PostgreSQL JSONB vs MongoDB) before committing. "
            "Interim: unblock MVP development with PostgreSQL. "
            "Post-benchmark: adopt winning platform permanently."
        ),
        rationale=(
            "MongoDB's velocity argument (schema evolution without migrations) is legitimate. "
            "PostgreSQL's GDPR blocker is removed (de-scoped from MVP). "
            "An empirical benchmark is the most rigorous way to settle this -- "
            "both platforms have production advocates with real evidence. "
            "We avoid premature convergence by running the experiment first."
        ),
        assertion_ids=[db_engine.id, user_mongodb.id, orm.id, gql_schema.id],
        conflict_ids=resolved_conflict_ids[:3],  # Core conflicts
        alternatives_rejected=[
            "Immediately adopt MongoDB -- rejected because Prisma migration risk is unquantified",
            "Reject MongoDB outright -- rejected because velocity argument is legitimate and tested",
            "Use both (polyglot persistence) -- rejected due to operational complexity for MVP",
        ],
        second_order_effects=[
            "If MongoDB wins benchmark: Prisma must be replaced (Mongoose, Prisma preview, or raw driver)",
            "If MongoDB wins: GraphQL schema generation approach changes (pothos or manual)",
            "If PostgreSQL wins with JSONB: JSONB indexing strategy must be documented",
            "Either outcome: benchmark results become evidence record for future similar decisions",
            "GDPR deletion approach must be re-evaluated post-MVP regardless of DB choice",
        ],
        reversibility="costly",
    )
    stage.decisions.append(decision)
    print(f"  Decision: '{decision.decision[:60]}...'")
    print(f"  Alternatives rejected : {len(decision.alternatives_rejected)}")
    for alt in decision.alternatives_rejected:
        print(f"    - {alt}")
    print(f"  Second-order effects  : {len(decision.second_order_effects)}")
    for effect in decision.second_order_effects:
        print(f"    -> {effect}")
    print(f"  Reversibility         : {decision.reversibility}")

    # -- Step 12: Trust report -----------------------------------------------
    step(12, "Trust scores -- conflict resolution history shapes confidence")

    print(format_trust_report(stage))

    # -- Step 13: RED TEAM analysis ------------------------------------------
    step(13, "RED TEAM analysis -- anti-echo-chamber posture check")

    # Bump exchange count to make RED_TEAMING checks meaningful
    stage.exchange_count = 10

    triggered = should_trigger_red_team(stage)
    print(f"  RED_TEAMING triggered: {triggered}")
    print(f"  Threshold: {stage.parameters.red_team_threshold} LOCAL assertions with 0 active conflicts")
    print()

    local_count = sum(
        1 for a in stage.assertions.values()
        if a.active and a.arc == CompositionArc.LOCAL
    )
    active_conflicts_count = sum(
        1 for c in stage.conflicts.values()
        if c.status.value == "active"
    )
    print(f"  Current LOCAL assertions (active): {local_count}")
    print(f"  Current active conflicts: {active_conflicts_count}")
    print()

    if triggered:
        record_red_team_trigger(stage)
    print(generate_red_team_report(stage))

    # -- Step 14: Final stage summary ----------------------------------------
    step(14, "Final stage summary")

    resolved_map = stage.resolve()
    print(f"  Active paths: {len(resolved_map)}")
    for path in sorted(resolved_map.keys()):
        slot = resolved_map[path]
        winner = slot["winning"]
        health = slot["health_issues"]
        health_str = f" [{len(health)} health issue(s)]" if health else ""
        print(f"    {path}")
        print(f"      [{winner.arc.name}] {winner.content}{health_str}")

    print()
    all_a = list(stage.assertions.values())
    active_a = [a for a in all_a if a.active]
    retracted_a = [a for a in all_a if not a.active]
    print(f"  Assertions: {len(all_a)} total | {len(active_a)} active | {len(retracted_a)} retracted (retained)")
    print(f"  Conflicts : {len(stage.conflicts)} total")
    for label, status_val in [
        ("active", "active"),
        ("resolved via experiment", "experiment"),
        ("deferred", "deferred"),
        ("dismissed", "dismissed"),
    ]:
        count = sum(1 for c in stage.conflicts.values() if c.status.value == status_val)
        if count:
            print(f"    {count} {label}")
    print(f"  Decisions : {len(stage.decisions)}")
    print(f"  Events    : {len(stage.events)}")

    print()
    print("  Event breakdown:")
    counts = count_events_by_type(stage)
    for event_type, count in sorted(counts.items()):
        print(f"    {event_type:45s}: {count}")

    print()
    print("  Conflict resolution history:")
    history = get_conflict_resolution_history(stage)
    for evt in history:
        resolution = evt.detail.get("resolution", "detected")
        print(f"    [{evt.timestamp.strftime('%H:%M:%S')}] {evt.event_type.value:<40} {resolution}")

    print()
    print("=" * 70)
    print("  SCENARIO COMPLETE")
    print()
    print("  What happened:")
    print("  1. AI staked LOCAL claims with falsifiability conditions")
    print("  2. User proposed MongoDB -- structural conflict detected automatically")
    print("  3. Winner did NOT change (LOCAL beats REFERENCES) -- no cascade yet")
    print("  4. AI steelmanned MongoDB before challenging (gate enforced)")
    print("  5. User de-scoped GDPR -- falsification condition met, claim retracted")
    print("  6. Benchmark experiment proposed -- empirical resolution path chosen")
    print("  7. Decision recorded with explicit alternatives and second-order effects")
    print()
    print("  This is the difference between a system that capitulates, one that")
    print("  stonewalls, and one that reasons rigorously while respecting the")
    print("  user's argument at its strongest.")
    print("=" * 70)


if __name__ == "__main__":
    main()
