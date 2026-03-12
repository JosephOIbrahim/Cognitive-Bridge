#!/usr/bin/env python3
"""Conflict scenario demonstrating steelman gates, experiment proposals, and cascading.

This example shows:
1. Building a dependency DAG with interconnected assertions
2. Layer 1 structural conflict detection (same path, different content)
3. Layer 4 cascading conflicts (dependency shift flags downstream claims)
4. Steelman gate enforcement -- CHALLENGE requires articulating the opposing view
5. Experiment gate -- PROPOSE_EXPERIMENT requires a concrete protocol
6. All five non-experiment resolution paths demonstrated
7. VariantSet creation via SYNTHESIZE resolution
8. Decision recording with mandatory alternatives_rejected and second_order_effects

Run with: python examples/conflict_scenario.py
"""

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    Decision,
    EventType,
    ResolutionPath,
    Variant,
    VariantSet,
)
from cognitive_bridge.engine.resolver import (
    add_assertion,
    promote_assertion,
    resolve_conflict,
    retract_assertion,
)
from cognitive_bridge.engine.provenance import (
    count_events_by_type,
    format_audit_trail,
    get_conflict_resolution_history,
)
from cognitive_bridge.engine.trust import format_trust_report, get_trust_for_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    width = 65
    print(f"\n{'-' * width}")
    print(f"  {title}")
    print(f"{'-' * width}")


def show_conflict(stage: CompositionStage, conflict_id: str) -> None:
    cfl = stage.conflicts[conflict_id]
    a_a = stage.assertions[cfl.assertion_a_id]
    a_b = stage.assertions[cfl.assertion_b_id]
    print(f"  Conflict [{cfl.id}]")
    print(f"    Path   : {cfl.topic_path}")
    print(f"    Layer  : {cfl.detection_layer.value}")
    print(f"    Status : {cfl.status.value}")
    print(f"    Side A : [{a_a.arc.name}] {a_a.content}")
    print(f"    Side B : [{a_b.arc.name}] {a_b.content}")
    if cfl.resolution_chosen:
        print(f"    Chosen : {cfl.resolution_chosen.value}")
    if cfl.steelman_of_opponent:
        print(f"    Steelman: {cfl.steelman_of_opponent[:70]}...")
    if cfl.experiment_protocol:
        print(f"    Protocol: {cfl.experiment_protocol[:70]}...")
    if cfl.cascade_source_path:
        print(f"    Cascade source: {cfl.cascade_source_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 65)
    print("  Cognitive Bridge: Full Conflict Protocol Demonstration")
    print("=" * 65)

    stage = CompositionStage(
        project_id="conflict-demo",
        project_name="Conflict Protocol Demo",
        exchange_count=1,
    )

    # -- Phase A: Build the initial state with a dependency DAG --------------
    section("Phase A: Build stage with dependency DAG")

    # Foundation: deployment target (no dependencies).
    # Start at INHERITS -- a strong domain pattern but not yet verified LOCAL.
    # This allows GCP to become the winner when promoted to LOCAL later.
    deploy_target = Assertion(
        topic_path="/deploy/target",
        content="Deploy to AWS ECS containers",
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        evidence=["ECS pricing model fits within $200/month at current scale"],
        confidence=0.85,
    )
    add_assertion(stage, deploy_target)
    print(f"  [1] {deploy_target.arc.name:12s} '{deploy_target.content}'")

    # Service: depends on deployment target
    service_config = Assertion(
        topic_path="/deploy/service",
        content="Run stateless FastAPI service in ECS Fargate tasks",
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        depends_on_paths=["/deploy/target"],
        confidence=0.8,
    )
    add_assertion(stage, service_config)
    print(f"  [2] {service_config.arc.name:12s} '{service_config.content}'")
    print(f"      depends_on: {service_config.depends_on_paths}")

    # CI/CD: also depends on deployment target
    cicd = Assertion(
        topic_path="/deploy/cicd",
        content="Use AWS CodePipeline for CI/CD integration",
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        depends_on_paths=["/deploy/target"],
        confidence=0.75,
    )
    add_assertion(stage, cicd)
    print(f"  [3] {cicd.arc.name:12s} '{cicd.content}'")
    print(f"      depends_on: {cicd.depends_on_paths}")

    # Monitoring: depends on service config
    monitoring = Assertion(
        topic_path="/deploy/monitoring",
        content="Use AWS CloudWatch for container metrics",
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        depends_on_paths=["/deploy/service"],
        confidence=0.7,
    )
    add_assertion(stage, monitoring)
    print(f"  [4] {monitoring.arc.name:12s} '{monitoring.content}'")
    print(f"      depends_on: {monitoring.depends_on_paths}")

    resolved = stage.resolve()
    print(f"\n  Stage has {len(resolved)} active paths, {len(stage.assertions)} assertions")
    print(f"  Dependency chain for monitoring: {stage.get_dependency_chain(monitoring.id)}")

    # -- Phase B: Structural conflict + cascading ----------------------------
    section("Phase B: User requests GCP -- structural conflict + cascade fires")

    print("  User says: 'Switch to GCP Cloud Run -- better cold-start performance.'")
    print()

    user_gcp = Assertion(
        topic_path="/deploy/target",
        content="Deploy to GCP Cloud Run (serverless containers)",
        arc=CompositionArc.REFERENCES,
        author=AssertionAuthor.USER,
        evidence=["GCP Cloud Run cold-start: 200ms vs ECS: 15s"],
        confidence=0.75,
    )
    r = add_assertion(stage, user_gcp)

    print(f"  Added: [{user_gcp.arc.name}] '{user_gcp.content}'")

    if r.structural_conflict:
        print(f"\n  LAYER 1 -- Structural conflict detected:")
        show_conflict(stage, r.structural_conflict.id)

    if r.cascading_conflicts:
        print(f"\n  LAYER 4 -- Cascading conflicts triggered ({len(r.cascading_conflicts)}):")
        for cfl in r.cascading_conflicts:
            dep_assertion = stage.assertions[cfl.assertion_b_id]
            print(f"    [{dep_assertion.id}] {dep_assertion.topic_path}")
            print(f"      '{dep_assertion.content}'")
            print(f"      assumption_status -> {dep_assertion.assumption_status.value}")

    print(f"\n  Winner changed at /deploy/target: {r.winner_changed}")
    if not r.winner_changed:
        print("  INHERITS(20) still wins over REFERENCES(40). No cascade fires yet.")
        print("  Cascade only fires when the WINNER changes, not when a weaker")
        print("  assertion is added.")

    # ECS INHERITS(20) still winning because INHERITS(20) < REFERENCES(40).
    resolved = stage.resolve()
    slot = resolved["/deploy/target"]
    print(f"\n  Current winner at /deploy/target:")
    print(f"    [{slot['winning'].arc.name}] {slot['winning'].content}")
    print(f"    Shadow: {len(slot['shadow_stack'])} assertion(s)")

    # -- Phase C: Steelman gate demonstration --------------------------------
    section("Phase C: Steelman gate -- CHALLENGE requires comprehension first")

    structural_cfl_id = r.structural_conflict.id if r.structural_conflict else None
    if not structural_cfl_id:
        # Find the active conflict manually
        structural_cfl_id = next(
            c.id for c in stage.conflicts.values()
            if c.topic_path == "/deploy/target" and c.status.value == "active"
        )

    print("  Attempting CHALLENGE without steelman_summary (must be rejected):")
    try:
        resolve_conflict(
            stage,
            structural_cfl_id,
            ResolutionPath.CHALLENGE,
        )
        print("  ERROR: Should have been rejected!")
    except ValueError as exc:
        print(f"  Correctly rejected: {exc}")

    print()
    print("  Now challenging WITH a genuine steelman of the GCP argument:")
    steelman = (
        "GCP Cloud Run's serverless model eliminates instance management entirely -- "
        "no task definition updates, no cluster capacity planning, automatic scale-to-zero. "
        "The 200ms cold-start advantage is real and matters for latency-sensitive APIs. "
        "GCP's global Anycast load balancing also provides lower P99 globally than "
        "regional ECS. The velocity and operational simplicity arguments are legitimate."
    )
    print()
    print(f"  Steelman: '{steelman[:80]}...'")

    resolve_conflict(
        stage,
        structural_cfl_id,
        ResolutionPath.CHALLENGE,
        steelman_summary=steelman,
        note=(
            "However, ECS choice is tied to AWS CodePipeline (CI/CD) and "
            "CloudWatch monitoring. Switching to GCP cascades through those."
        ),
    )
    cfl = stage.conflicts[structural_cfl_id]
    print(f"\n  Conflict status after CHALLENGE: {cfl.status.value}")
    print(f"  (CHALLENGE keeps conflict ACTIVE -- the debate continues)")
    print(f"  steelman recorded: {cfl.steelman_of_opponent is not None}")

    # -- Phase D: Promote the user assertion and trigger cascade -------------
    section("Phase D: Promote user GCP assertion -- cascade fires, winner changes")

    print("  User provides benchmark evidence. Promoting GCP from REFERENCES(40) to LOCAL(10).")
    print()
    print("  Note: The schema validator for falsifiable_if runs at construction time.")
    print("  promote_assertion() mutates the arc field directly; we set falsifiable_if")
    print("  before promoting so the object is consistent with LOCAL semantics.")

    # Set falsifiable_if and update confidence before promoting.
    # The Pydantic validator only runs at model construction, not on field mutation.
    # In production the assertion_tool enforces falsifiable_if at the tool layer.
    # ECS is INHERITS(20), GCP will become LOCAL(10) -- LOCAL beats INHERITS.
    user_gcp.falsifiable_if = (
        "Falsified if GCP Cloud Run cost exceeds ECS by more than 20% at production load"
    )
    user_gcp.confidence = 0.88  # Update based on benchmark evidence

    promote_result = promote_assertion(
        stage,
        user_gcp.id,
        CompositionArc.LOCAL,
        evidence="GCP Cloud Run benchmark: P99 < 50ms globally vs ECS: 800ms cross-region",
    )

    print(f"  Promoted to [{user_gcp.arc.name}] (arc={user_gcp.arc.value})")
    print(f"  Winner changed: {promote_result.winner_changed}")

    if promote_result.winner_changed:
        old = stage.assertions.get(promote_result.previous_winner_id)
        new = stage.assertions.get(promote_result.new_winner_id)
        print(f"  Old winner: [{old.arc.name}] {old.content}")
        print(f"  New winner: [{new.arc.name}] {new.content}")
        print(f"\n  Cascading conflicts triggered: {len(promote_result.cascading_conflicts)}")
        for cfl in promote_result.cascading_conflicts:
            dep = stage.assertions[cfl.assertion_b_id]
            print(f"    {dep.topic_path}: '{dep.content}'")
            print(f"      assumption_status -> {dep.assumption_status.value}")

    # -- Phase E: Experiment proposal ----------------------------------------
    section("Phase E: PROPOSE_EXPERIMENT -- empirical gate enforcement")

    # Find the cascading conflict on /deploy/service
    service_cascade = next(
        (c for c in stage.conflicts.values()
         if c.topic_path == "/deploy/service"
         and c.status.value == "active"),
        None,
    )

    if service_cascade:
        print("  Attempting PROPOSE_EXPERIMENT without experiment_protocol (must fail):")
        try:
            resolve_conflict(
                stage,
                service_cascade.id,
                ResolutionPath.PROPOSE_EXPERIMENT,
            )
            print("  ERROR: Should have been rejected!")
        except ValueError as exc:
            print(f"  Correctly rejected: {exc}")

        print()
        print("  Proposing experiment WITH a concrete protocol:")
        protocol = (
            "Run parallel load test for 72 hours: "
            "identical FastAPI workload on ECS Fargate vs GCP Cloud Run. "
            "Measure: P50/P95/P99 latency, cold-start frequency, monthly cost at 1000 req/min. "
            "Decision criterion: GCP wins if (cost delta < 20%) AND (P99 < 100ms). "
            "Neutral party reviews results."
        )
        resolve_conflict(
            stage,
            service_cascade.id,
            ResolutionPath.PROPOSE_EXPERIMENT,
            experiment_protocol=protocol,
        )
        cfl = stage.conflicts[service_cascade.id]
        print(f"  Conflict status: {cfl.status.value}")
        print(f"  Protocol recorded: {cfl.experiment_protocol is not None}")

    # -- Phase F: SYNTHESIZE path -- create a VariantSet ---------------------
    section("Phase F: SYNTHESIZE resolution -- create a VariantSet for both options")

    cicd_cascade = next(
        (c for c in stage.conflicts.values()
         if c.topic_path == "/deploy/cicd"
         and c.status.value == "active"),
        None,
    )

    if cicd_cascade:
        # Resolve via SYNTHESIZE
        resolve_conflict(
            stage,
            cicd_cascade.id,
            ResolutionPath.SYNTHESIZE,
            note="Both CI/CD options are viable -- maintain as live variants.",
        )
        cfl = stage.conflicts[cicd_cascade.id]
        print(f"  Conflict resolved via SYNTHESIZE: {cfl.status.value}")

        # Create a VariantSet to hold both hypotheses
        variant_set = VariantSet(
            name="CI/CD Platform Options",
            topic_path="/deploy/cicd",
            source_conflict_id=cicd_cascade.id,
            variants=[
                Variant(
                    name="aws-codepipeline",
                    content="Use AWS CodePipeline (native ECS integration)",
                    evidence_for=["Zero-config ECS deployments", "IAM unified with existing AWS account"],
                    evidence_against=["Locked to AWS ecosystem", "More expensive than GitHub Actions"],
                    activation_condition="If we stay on ECS",
                ),
                Variant(
                    name="github-actions-cloud-deploy",
                    content="Use GitHub Actions + Cloud Deploy for GCP",
                    evidence_for=["Universal platform", "Better developer experience", "Free tier generous"],
                    evidence_against=["Requires GCP SA key management in GitHub"],
                    activation_condition="If we move to GCP Cloud Run",
                ),
            ],
        )
        stage.variant_sets[variant_set.id] = variant_set
        stage.record_event(
            EventType.VARIANT_SET_CREATED,
            AssertionAuthor.AI,
            variant_set.id,
            {"topic_path": variant_set.topic_path, "variants": len(variant_set.variants)},
        )
        print(f"  VariantSet created: '{variant_set.name}'")
        print(f"  Variants ({len(variant_set.variants)}):")
        for v in variant_set.variants:
            print(f"    '{v.name}': {v.content}")
            print(f"      Activation: {v.activation_condition}")

    # -- Phase G: Record a decision with mandatory provenance ----------------
    section("Phase G: Record a decision -- alternatives_rejected and second_order_effects required")

    print("  Decision models require at LEAST one alternative_rejected and one second_order_effect.")
    print("  Attempting to create without them (must fail):")
    try:
        Decision(
            topic_path="/deploy/target",
            decision="Use GCP Cloud Run",
            rationale="Better cold-start performance and simpler operations",
            alternatives_rejected=[],  # min_length=1 -- must fail
            second_order_effects=["Must migrate CI/CD to Cloud Deploy"],
        )
        print("  ERROR: Should have been rejected!")
    except Exception as exc:
        print(f"  Correctly rejected: {type(exc).__name__}: {str(exc)[:80]}...")

    print()
    print("  Recording properly formed decision:")
    decision = Decision(
        topic_path="/deploy/target",
        decision="Proceed with GCP Cloud Run after successful benchmark",
        rationale=(
            "Benchmark evidence showed GCP Cloud Run P99 < 50ms globally "
            "vs ECS 800ms cross-region, at comparable cost. "
            "Operational simplicity (no cluster management) reduces toil."
        ),
        assertion_ids=[deploy_target.id, user_gcp.id],
        conflict_ids=[structural_cfl_id],
        alternatives_rejected=[
            "AWS ECS Fargate -- rejected due to cross-region P99 latency (800ms)",
            "AWS Lambda -- rejected due to cold-start penalty for API workloads",
        ],
        second_order_effects=[
            "CI/CD pipeline must migrate from CodePipeline to Cloud Deploy or GitHub Actions",
            "CloudWatch monitoring must be replaced with GCP Cloud Monitoring",
            "IAM configuration must be re-evaluated for GCP service accounts",
            "ECS-specific Docker labels and healthcheck configs must be updated",
        ],
        reversibility="costly",
    )
    stage.decisions.append(decision)
    print(f"  Decision recorded: '{decision.decision}'")
    print(f"  Alternatives rejected: {len(decision.alternatives_rejected)}")
    print(f"  Second-order effects : {len(decision.second_order_effects)}")
    print(f"  Reversibility        : {decision.reversibility}")
    for effect in decision.second_order_effects:
        print(f"    -> {effect}")

    # -- Phase H: Trust scores and conflict history --------------------------
    section("Phase H: Trust report and conflict resolution history")

    print(format_trust_report(stage))

    path_trust = get_trust_for_path(stage, "/deploy/target")
    print(f"  /deploy/target trust score: {path_trust.score:.2f}")
    print(f"    total_conflicts: {path_trust.total_conflicts}")
    print(f"    challenges (active): {path_trust.challenges}")
    print(f"    experiments: {path_trust.experiments}")

    print()
    print("  Conflict resolution history (chronological):")
    history = get_conflict_resolution_history(stage)
    for evt in history:
        resolution = evt.detail.get("resolution", "detected")
        print(f"    [{evt.timestamp.strftime('%H:%M:%S')}] {evt.event_type.value} -> {resolution}")

    # -- Summary -------------------------------------------------------------
    section("Summary")

    all_conflicts = list(stage.conflicts.values())
    active = [c for c in all_conflicts if c.status.value == "active"]
    resolved_count = len(all_conflicts) - len(active)

    print(f"  Assertions  : {len(stage.assertions)} total, {sum(1 for a in stage.assertions.values() if a.active)} active")
    print(f"  Conflicts   : {len(all_conflicts)} total, {len(active)} active, {resolved_count} resolved")
    print(f"  Variant sets: {len(stage.variant_sets)}")
    print(f"  Decisions   : {len(stage.decisions)}")
    print(f"  Events      : {len(stage.events)}")
    print()
    print("  Resolution paths demonstrated:")
    print("    CHALLENGE          -- keeps conflict ACTIVE, records steelman")
    print("    PROPOSE_EXPERIMENT -- resolves as RESOLVED_EXPERIMENT, requires protocol")
    print("    SYNTHESIZE         -- resolves as RESOLVED_SYNTHESIZED")
    print()
    print("  Gates enforced:")
    print("    Falsifiability gate : LOCAL arc requires falsifiable_if")
    print("    Steelman gate       : CHALLENGE requires steelman_summary")
    print("    Experiment gate     : PROPOSE_EXPERIMENT requires experiment_protocol")
    print("    Decision gate       : Decision requires alternatives_rejected and second_order_effects")


if __name__ == "__main__":
    main()
