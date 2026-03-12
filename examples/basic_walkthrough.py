#!/usr/bin/env python3
"""Basic walkthrough of the Cognitive Bridge composition system.

This example demonstrates:
1. Creating a composition stage
2. Adding assertions at different LIVRPS arc levels
3. Resolving to see which assertion wins at each path
4. Detecting and resolving a structural conflict
5. Retracting an assertion and observing winner change
6. Reading the audit trail via the provenance engine

Run with: python examples/basic_walkthrough.py
"""

from cognitive_bridge.models import (
    Assertion,
    AssertionAuthor,
    CompositionArc,
    CompositionStage,
    ResolutionPath,
)
from cognitive_bridge.engine.resolver import (
    add_assertion,
    resolve_conflict,
    retract_assertion,
)
from cognitive_bridge.engine.provenance import format_audit_trail, count_events_by_type


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def separator(title: str) -> None:
    width = 60
    print(f"\n{'-' * width}")
    print(f"  {title}")
    print(f"{'-' * width}")


def print_resolution(resolved: dict, path: str) -> None:
    if path not in resolved:
        print(f"  {path}: (no active assertions)")
        return
    slot = resolved[path]
    winner = slot["winning"]
    shadow = slot["shadow_stack"]
    conflicts = slot["active_conflicts"]
    depth = slot["depth"]
    print(f"  {path}")
    print(f"    Winner : [{winner.arc.name:12s}] {winner.content}")
    print(f"    Depth  : {depth} active assertion(s)")
    if shadow:
        print(f"    Shadow : {len(shadow)} shadowed")
        for s in shadow:
            print(f"             [{s.arc.name:12s}] {s.content}")
    if conflicts:
        print(f"    Conflicts: {len(conflicts)} active")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    separator("Cognitive Bridge: Basic Walkthrough")
    print()
    print("LIVRPS arc strength order (lower integer = stronger):")
    for arc in CompositionArc:
        print(f"  {arc.value:3d} = {arc.name}")

    # -- Step 1: Create a composition stage ----------------------------------
    separator("Step 1: Create a composition stage")

    stage = CompositionStage(
        project_id="basic-walkthrough",
        project_name="Basic Walkthrough",
        exchange_count=1,
    )
    print(f"  project_id  : {stage.project_id}")
    print(f"  project_name: {stage.project_name}")
    print(f"  assertions  : {len(stage.assertions)}")
    print(f"  events      : {len(stage.events)}")

    # -- Step 2: Add a SPECIALIZES assertion (weakest arc) -------------------
    separator("Step 2: Add a SPECIALIZES assertion (arc=60 -- baseline knowledge)")

    baseline = Assertion(
        topic_path="/tech/language",
        content="Use Python for the backend",
        arc=CompositionArc.SPECIALIZES,
        author=AssertionAuthor.AI,
        confidence=0.6,
    )
    r1 = add_assertion(stage, baseline)
    print(f"  Added   : [{baseline.arc.name}] '{baseline.content}'")
    print(f"  Conflict: {r1.structural_conflict is not None} (expected: False -- first assertion)")
    print(f"  Winner  : {r1.new_winner_id == baseline.id} (expected: True)")

    # -- Step 3: Add an INHERITS assertion (stronger -- overrides SPECIALIZES)
    separator("Step 3: Add an INHERITS assertion (arc=20 -- domain pattern, stronger)")

    pattern = Assertion(
        topic_path="/tech/language",
        content="Use TypeScript for the backend",
        arc=CompositionArc.INHERITS,
        author=AssertionAuthor.AI,
        confidence=0.7,
    )
    r2 = add_assertion(stage, pattern)
    print(f"  Added    : [{pattern.arc.name}] '{pattern.content}'")
    if r2.structural_conflict:
        cfl = r2.structural_conflict
        print(f"  Conflict : DETECTED [{cfl.id}] at {cfl.topic_path}")
        print(f"             {cfl.detection_layer.value} conflict")
    print(f"  Winner changed: {r2.winner_changed}")
    print(f"  Previous winner: {r2.previous_winner_id}")
    print(f"  New winner     : {r2.new_winner_id}")

    resolved = stage.resolve()
    print()
    print("  Current resolution:")
    print_resolution(resolved, "/tech/language")

    # -- Step 4: Add a LOCAL assertion (strongest arc, requires falsifiable_if)
    separator("Step 4: Add a LOCAL assertion (arc=10 -- verified, requires falsifiable_if)")

    print("  Note: LOCAL assertions REQUIRE 'falsifiable_if' -- Popperian schema gate.")
    print("  Omitting it raises ValueError. Attempting without it first:")
    try:
        Assertion(
            topic_path="/tech/language",
            content="Use Go for the backend",
            arc=CompositionArc.LOCAL,
            author=AssertionAuthor.USER,
            # No falsifiable_if -- this must fail
        )
        print("  ERROR: Should have been rejected!")
    except ValueError as exc:
        print(f"  Correctly rejected: {str(exc)[:80]}...")

    print()
    print("  Now adding with falsifiable_if declared:")
    verified = Assertion(
        topic_path="/tech/language",
        content="Use Go for the backend",
        arc=CompositionArc.LOCAL,
        author=AssertionAuthor.USER,
        falsifiable_if="Falsified if Go cannot handle 10k concurrent connections in benchmark",
        evidence=["Production benchmarks show Go handles 50k connections at P99 < 50ms"],
        confidence=0.9,
    )
    r3 = add_assertion(stage, verified)
    print(f"  Added    : [{verified.arc.name}] '{verified.content}'")
    if r3.structural_conflict:
        cfl = r3.structural_conflict
        print(f"  Conflict : DETECTED [{cfl.id}]")
    if r3.winner_changed:
        print(f"  Winner changed: {r3.previous_winner_id} -> {r3.new_winner_id}")

    resolved = stage.resolve()
    print()
    print("  Resolution after adding LOCAL assertion:")
    print_resolution(resolved, "/tech/language")

    # -- Step 5: Resolve the structural conflict ------------------------------
    separator("Step 5: Resolve conflicts via available resolution paths")

    active_conflicts = [
        c for c in stage.conflicts.values()
        if c.status.value == "active"
    ]
    print(f"  Active conflicts: {len(active_conflicts)}")

    if active_conflicts:
        # Demonstrate the steelman gate -- challenge without steelman must fail
        conflict = active_conflicts[0]
        print(f"\n  Attempting CHALLENGE without steelman_summary (must fail):")
        try:
            resolve_conflict(
                stage,
                conflict.id,
                ResolutionPath.CHALLENGE,
                # No steelman_summary
            )
            print("  ERROR: Should have been rejected!")
        except ValueError as exc:
            print(f"  Correctly rejected: {str(exc)[:80]}...")

        # Defer the conflict -- marks it DEFERRED without requiring steelman
        print(f"\n  Resolving conflict via DEFER:")
        resolved_conflict = resolve_conflict(
            stage,
            conflict.id,
            ResolutionPath.DEFER,
            note="Decision deferred pending benchmark results.",
        )
        print(f"  Conflict [{conflict.id[:20]}...] status: {resolved_conflict.status.value}")

    # -- Step 6: Add a second path with multiple assertions ------------------
    separator("Step 6: Multiple topic paths in the stage")

    db_baseline = Assertion(
        topic_path="/tech/database",
        content="Use SQLite for development",
        arc=CompositionArc.SPECIALIZES,
        author=AssertionAuthor.AI,
    )
    db_strong = Assertion(
        topic_path="/tech/database",
        content="Use PostgreSQL for production",
        arc=CompositionArc.LOCAL,
        author=AssertionAuthor.AI,
        falsifiable_if="Falsified if PostgreSQL fails under load testing at 5k concurrent connections",
        evidence=["PostgreSQL 15 benchmark: 8k TPS at P99 < 20ms"],
    )
    add_assertion(stage, db_baseline)
    add_assertion(stage, db_strong)

    resolved = stage.resolve()
    print(f"  Stage now has {len(resolved)} paths with active assertions:")
    for path in sorted(resolved.keys()):
        print_resolution(resolved, path)

    # -- Step 7: Retract an assertion and observe winner change --------------
    separator("Step 7: Retract the LOCAL Go assertion -- TypeScript re-emerges as winner")

    print(f"  Before retraction:")
    print_resolution(stage.resolve(), "/tech/language")

    retract_result = retract_assertion(stage, verified.id)
    print(f"\n  Retracted: [{verified.arc.name}] '{verified.content}'")
    print(f"  Winner changed: {retract_result.winner_changed}")
    print(f"  New winner: {retract_result.new_winner_id}")
    print(f"  (Assertion still in stage.assertions with active=False -- non-destructive)")
    print(f"  stage.assertions count: {len(stage.assertions)} (retracted ones counted)")

    print(f"\n  After retraction:")
    print_resolution(stage.resolve(), "/tech/language")

    # -- Step 8: Audit trail -------------------------------------------------
    separator("Step 8: Audit trail")

    print(f"  Event counts by type:")
    counts = count_events_by_type(stage)
    for event_type, count in sorted(counts.items()):
        print(f"    {event_type:40s}: {count}")

    print(f"\n  Full audit trail for the Go assertion:")
    trail = format_audit_trail(stage, verified.id)
    print(trail)

    # -- Summary -------------------------------------------------------------
    separator("Summary")

    total = len(stage.assertions)
    active = sum(1 for a in stage.assertions.values() if a.active)
    retracted = total - active
    print(f"  Assertions total    : {total}")
    print(f"  Assertions active   : {active}")
    print(f"  Assertions retracted: {retracted} (non-destructive -- still in stage)")
    print(f"  Conflicts detected  : {len(stage.conflicts)}")
    print(f"  Events recorded     : {len(stage.events)}")
    print()
    print("  Key invariant demonstrated: retracted assertions are NEVER deleted.")
    print("  The composition stage is non-destructive. 'Winning' is computed")
    print("  dynamically by resolve(), not by overwriting.")


if __name__ == "__main__":
    main()
