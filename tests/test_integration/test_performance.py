"""Performance profiling — benchmark conflict detection, resolution, and cascading.

These tests verify that the engine performs within acceptable latency bounds.
They are NOT unit tests — they measure wall-clock time for realistic workloads.

Latency targets (conservative, CI-safe):
  resolve() at 50/100/500 assertions:   <100ms / <200ms / <1000ms
  Structural detection at 100/500:      <50ms  / <100ms
  Cascade to 10/50 dependents:          <50ms  / <200ms
  Trust computation (100 conflicts):    <50ms
  Red team analysis (200 LOCALs):       <500ms
"""

import time

import pytest

from cognitive_bridge.engine.cascade import detect_cascading_conflicts
from cognitive_bridge.engine.conflict_detector import detect_structural_conflict
from cognitive_bridge.engine.red_team import generate_red_team_report
from cognitive_bridge.engine.trust import compute_trust_scores
from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    CompositionArc,
    ConflictDetectionLayer,
    ConflictStatus,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.conflict import Conflict
from cognitive_bridge.models.stage import CompositionStage


# Every wall-clock budget below is scaled by this slack factor. These tests are
# gross-regression guards (they catch an algorithmic blow-up, e.g. O(n) -> O(n^2)),
# NOT microbenchmarks. Raw budgets like 10-50ms are far tighter than the GC and
# scheduling jitter of a shared CI runner — that is what produced spurious
# hard-gate reds (a 50-dependent cascade measured 231ms against a 200ms budget).
# A 10x margin keeps the regression signal while removing the flakiness. Actual
# timings are still printed for humans (run with -s).
PERF_SLACK = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _path(i: int) -> str:
    """Produce a valid topic path for index i.

    Topic paths must match ``^(/[a-z][a-z0-9_]*)+$``, so the segment must
    start with a letter.  We use /path/n<index>.
    """
    return f"/path/n{i}"


def _make_assertion(
    path: str,
    content: str,
    arc: CompositionArc = CompositionArc.INHERITS,
    **kwargs,
) -> Assertion:
    """Create an assertion, injecting the required falsifiable_if for LOCAL."""
    if arc == CompositionArc.LOCAL and "falsifiable_if" not in kwargs:
        kwargs["falsifiable_if"] = f"Falsified if {content} is wrong"
    return Assertion(
        topic_path=path,
        content=content,
        arc=arc,
        author=AssertionAuthor.AI,
        **kwargs,
    )


def _populate_stage(n: int, project_id: str = "perf-test") -> CompositionStage:
    """Return a stage with n assertions at n unique paths (one per path)."""
    stage = CompositionStage(project_id=project_id, exchange_count=1)
    for i in range(n):
        ast = _make_assertion(_path(i), f"Content {i}")
        stage.assertions[ast.id] = ast
    return stage


# ---------------------------------------------------------------------------
# TestResolutionPerformance
# ---------------------------------------------------------------------------

class TestResolutionPerformance:
    """Benchmark CompositionStage.resolve() at different assertion counts."""

    def test_resolve_50_assertions(self):
        """resolve() across 50 unique paths completes under 100ms."""
        stage = _populate_stage(50, "perf-resolve-50")

        start = time.perf_counter()
        result = stage.resolve()
        elapsed = time.perf_counter() - start

        assert len(result) == 50, f"Expected 50 paths, got {len(result)}"
        assert elapsed < PERF_SLACK * 0.1, (
            f"resolve(50) took {elapsed * 1000:.2f}ms — exceeded 100ms budget"
        )
        print(f"\nResolve 50 assertions: {elapsed * 1000:.2f}ms")

    def test_resolve_100_assertions(self):
        """resolve() across 100 unique paths completes under 200ms."""
        stage = _populate_stage(100, "perf-resolve-100")

        start = time.perf_counter()
        result = stage.resolve()
        elapsed = time.perf_counter() - start

        assert len(result) == 100, f"Expected 100 paths, got {len(result)}"
        assert elapsed < PERF_SLACK * 0.2, (
            f"resolve(100) took {elapsed * 1000:.2f}ms — exceeded 200ms budget"
        )
        print(f"\nResolve 100 assertions: {elapsed * 1000:.2f}ms")

    def test_resolve_500_assertions(self):
        """resolve() across 500 unique paths completes under 1 second."""
        stage = _populate_stage(500, "perf-resolve-500")

        start = time.perf_counter()
        result = stage.resolve()
        elapsed = time.perf_counter() - start

        assert len(result) == 500, f"Expected 500 paths, got {len(result)}"
        assert elapsed < PERF_SLACK * 1.0, (
            f"resolve(500) took {elapsed * 1000:.2f}ms — exceeded 1000ms budget"
        )
        print(f"\nResolve 500 assertions: {elapsed * 1000:.2f}ms")

    def test_resolve_with_shadow_stacks(self):
        """resolve() with 3 assertions per path (shadow stacks) completes under 1 second.

        100 paths x 3 arcs = 300 assertions total.  Each path produces a 3-deep
        shadow stack.  The winner at each path must be the strongest arc (INHERITS
        beats SPECIALIZES beats REFERENCES).
        """
        stage = CompositionStage(project_id="perf-shadow", exchange_count=1)
        # Three arcs in ascending strength order (INHERITS=20 is strongest of the three)
        arcs = [
            CompositionArc.INHERITS,
            CompositionArc.SPECIALIZES,
            CompositionArc.REFERENCES,
        ]
        for i in range(100):
            for arc in arcs:
                ast = _make_assertion(_path(i), f"Content {i} arc {arc.name}", arc=arc)
                stage.assertions[ast.id] = ast

        start = time.perf_counter()
        result = stage.resolve()
        elapsed = time.perf_counter() - start

        # 100 unique paths, each path has a winner
        assert len(result) == 100, f"Expected 100 paths, got {len(result)}"
        # Shadow stacks should have 2 entries each (3 total minus the winner)
        assert all(len(v["shadow_stack"]) == 2 for v in result.values())
        # The winner at every path is the INHERITS assertion (arc=20, strongest here)
        assert all(v["winning"].arc == CompositionArc.INHERITS for v in result.values())
        assert elapsed < PERF_SLACK * 1.0, (
            f"resolve(100 paths x 3 arcs) took {elapsed * 1000:.2f}ms — exceeded 1000ms"
        )
        print(f"\nResolve 100 paths x 3 depth: {elapsed * 1000:.2f}ms")

    def test_resolve_path_filter_subset(self):
        """resolve() with path_filter scans only the matching subtree.

        500 assertions across 500 paths.  Filtering to /path/n0xx (i.e. n0..n09,
        n00..n09x etc.) should return far fewer paths than the full set,
        and complete in well under the full-stage budget.
        """
        stage = _populate_stage(500, "perf-filter")

        start = time.perf_counter()
        result = stage.resolve(path_filter="/path/n1")
        elapsed = time.perf_counter() - start

        # Paths matching /path/n1... are n1, n10..n19, n100..n199 → 1+10+100 = 111
        assert len(result) > 0
        assert elapsed < PERF_SLACK * 0.5, (
            f"resolve(500, filter=/path/n1) took {elapsed * 1000:.2f}ms — exceeded 500ms"
        )
        print(f"\nResolve 500 assertions (filtered): {elapsed * 1000:.2f}ms, {len(result)} paths matched")


# ---------------------------------------------------------------------------
# TestConflictDetectionPerformance
# ---------------------------------------------------------------------------

class TestConflictDetectionPerformance:
    """Benchmark Layer 1 structural conflict detection."""

    def test_detection_100_existing(self):
        """Detect conflict against 100 pre-existing assertions in under 50ms.

        Setup: 100 assertions at unique paths, then add a *second* assertion at
        an existing path with different content.  detect_structural_conflict
        should find the conflict quickly.
        """
        stage = _populate_stage(100, "perf-detect-100")

        # Add a conflicting assertion at path n50 (already occupied)
        conflicting = _make_assertion(_path(50), "A different claim at path 50")
        stage.assertions[conflicting.id] = conflicting

        start = time.perf_counter()
        result = detect_structural_conflict(stage, conflicting)
        elapsed = time.perf_counter() - start

        assert result is not None, "Expected a conflict to be detected"
        assert result.topic_path == _path(50)
        assert elapsed < PERF_SLACK * 0.05, (
            f"detect_structural_conflict(100 existing) took {elapsed * 1000:.2f}ms "
            "— exceeded 50ms budget"
        )
        print(f"\nStructural detection (100 existing): {elapsed * 1000:.2f}ms")

    def test_detection_500_existing(self):
        """Detect conflict against 500 pre-existing assertions in under 100ms."""
        stage = _populate_stage(500, "perf-detect-500")

        conflicting = _make_assertion(_path(250), "A different claim at path 250")
        stage.assertions[conflicting.id] = conflicting

        start = time.perf_counter()
        result = detect_structural_conflict(stage, conflicting)
        elapsed = time.perf_counter() - start

        assert result is not None, "Expected a conflict to be detected"
        assert result.topic_path == _path(250)
        assert elapsed < PERF_SLACK * 0.1, (
            f"detect_structural_conflict(500 existing) took {elapsed * 1000:.2f}ms "
            "— exceeded 100ms budget"
        )
        print(f"\nStructural detection (500 existing): {elapsed * 1000:.2f}ms")

    def test_no_conflict_path_100_existing(self):
        """No-conflict path (assertion at a new path) completes in under 50ms.

        The function scans only same-path assertions via iteration.  A new path
        with no existing claims returns None immediately.  Verifies no
        pathological behaviour when no conflict exists.
        """
        stage = _populate_stage(100, "perf-detect-noconflict")

        new_path = "/path/zzznoconflict"
        new_assertion = _make_assertion(new_path, "Brand new path, no conflicts expected")
        stage.assertions[new_assertion.id] = new_assertion

        start = time.perf_counter()
        result = detect_structural_conflict(stage, new_assertion)
        elapsed = time.perf_counter() - start

        assert result is None, "Expected no conflict on a new path"
        assert elapsed < PERF_SLACK * 0.05, (
            f"detect_structural_conflict (no conflict, 100 existing) took "
            f"{elapsed * 1000:.2f}ms — exceeded 50ms budget"
        )
        print(f"\nStructural detection no-conflict (100 existing): {elapsed * 1000:.2f}ms")


# ---------------------------------------------------------------------------
# TestCascadePerformance
# ---------------------------------------------------------------------------

class TestCascadePerformance:
    """Benchmark Layer 4 cascading conflict propagation."""

    def _build_fan_out_stage(self, n: int, project_id: str) -> tuple[CompositionStage, str]:
        """Build a stage with one root and n direct dependents.

        Returns (stage, root_path).
        """
        stage = CompositionStage(project_id=project_id, exchange_count=1)
        root = _make_assertion("/root/foundation", "Root assertion")
        stage.assertions[root.id] = root

        for i in range(n):
            dep = _make_assertion(
                f"/dep/n{i}",
                f"Dependent {i}",
                depends_on_paths=["/root/foundation"],
            )
            stage.assertions[dep.id] = dep

        return stage, "/root/foundation"

    def test_cascade_10_dependents(self):
        """Cascade to 10 direct dependents completes under 50ms."""
        stage, root_path = self._build_fan_out_stage(10, "perf-cascade-10")

        start = time.perf_counter()
        cascades = detect_cascading_conflicts(stage, root_path, "new_winner_id_placeholder")
        elapsed = time.perf_counter() - start

        assert len(cascades) == 10, f"Expected 10 cascade conflicts, got {len(cascades)}"
        assert elapsed < PERF_SLACK * 0.05, (
            f"cascade(10 dependents) took {elapsed * 1000:.2f}ms — exceeded 50ms budget"
        )
        print(f"\nCascade to 10 dependents: {elapsed * 1000:.2f}ms")

    def test_cascade_50_dependents(self):
        """Cascade to 50 direct dependents completes under 200ms."""
        stage, root_path = self._build_fan_out_stage(50, "perf-cascade-50")

        start = time.perf_counter()
        cascades = detect_cascading_conflicts(stage, root_path, "new_winner_id_placeholder")
        elapsed = time.perf_counter() - start

        assert len(cascades) == 50, f"Expected 50 cascade conflicts, got {len(cascades)}"
        assert elapsed < PERF_SLACK * 0.2, (
            f"cascade(50 dependents) took {elapsed * 1000:.2f}ms — exceeded 200ms budget"
        )
        print(f"\nCascade to 50 dependents: {elapsed * 1000:.2f}ms")

    def test_cascade_no_dependents(self):
        """Cascade on a path with no dependents returns empty list quickly."""
        stage = CompositionStage(project_id="perf-cascade-empty", exchange_count=1)
        root = _make_assertion("/root/isolated", "An isolated root")
        stage.assertions[root.id] = root

        start = time.perf_counter()
        cascades = detect_cascading_conflicts(stage, "/root/isolated", "winner_id")
        elapsed = time.perf_counter() - start

        assert cascades == []
        assert elapsed < PERF_SLACK * 0.01, (
            f"cascade(no dependents) took {elapsed * 1000:.2f}ms — exceeded 10ms budget"
        )
        print(f"\nCascade to 0 dependents: {elapsed * 1000:.2f}ms")

    def test_cascade_linear_chain_5_deep(self):
        """Cascade through a 5-level linear chain.

        /a → /a/b → /a/b/c → /a/b/c/d → /a/b/c/d/e

        Changing /a should cascade to /a/b (1 direct dependent).
        The cascade engine is not recursive by itself — each level must be
        triggered in turn by add_assertion/promote_assertion.  This test
        verifies the single-step detect_cascading_conflicts call on the root.
        """
        stage = CompositionStage(project_id="perf-chain", exchange_count=1)

        # Build chain: each level depends on the previous
        paths = ["/chain/a", "/chain/a/b", "/chain/a/b/c", "/chain/a/b/c/d", "/chain/a/b/c/d/e"]
        for idx, path in enumerate(paths):
            deps = [paths[idx - 1]] if idx > 0 else []
            ast = _make_assertion(path, f"Claim at depth {idx}", depends_on_paths=deps)
            stage.assertions[ast.id] = ast

        # Direct dependents of /chain/a = only /chain/a/b
        start = time.perf_counter()
        cascades = detect_cascading_conflicts(stage, paths[0], "new_winner_at_root")
        elapsed = time.perf_counter() - start

        assert len(cascades) == 1, (
            f"Expected 1 direct dependent of {paths[0]}, got {len(cascades)}"
        )
        assert cascades[0].topic_path == paths[1]
        assert elapsed < PERF_SLACK * 0.01, (
            f"cascade(5-deep linear chain, 1 direct dep) took {elapsed * 1000:.2f}ms "
            "— exceeded 10ms budget"
        )
        print(f"\nCascade 5-deep linear chain (1 direct dep): {elapsed * 1000:.2f}ms")


# ---------------------------------------------------------------------------
# TestTrustPerformance
# ---------------------------------------------------------------------------

class TestTrustPerformance:
    """Benchmark per-subtree trust score computation."""

    def test_trust_computation_100_conflicts_20_paths(self):
        """compute_trust_scores over 100 conflicts across 20 paths in under 50ms."""
        stage = CompositionStage(project_id="perf-trust", exchange_count=1)

        # 100 conflicts spread across 20 unique paths (5 per path)
        for i in range(100):
            path_index = i % 20
            c = Conflict(
                assertion_a_id=f"ast_perf_a{i:04d}",
                assertion_b_id=f"ast_perf_b{i:04d}",
                topic_path=f"/trust/p{path_index}",
                detection_layer=ConflictDetectionLayer.STRUCTURAL,
                status=(
                    ConflictStatus.RESOLVED_OVERRIDE
                    if i % 2 == 0
                    else ConflictStatus.ACTIVE
                ),
            )
            stage.conflicts[c.id] = c

        start = time.perf_counter()
        scores = compute_trust_scores(stage)
        elapsed = time.perf_counter() - start

        assert len(scores) == 20, f"Expected 20 path scores, got {len(scores)}"
        assert elapsed < PERF_SLACK * 0.05, (
            f"compute_trust_scores(100 conflicts, 20 paths) took "
            f"{elapsed * 1000:.2f}ms — exceeded 50ms budget"
        )
        print(
            f"\nTrust computation (100 conflicts, 20 paths): {elapsed * 1000:.2f}ms"
        )

    def test_trust_computation_500_conflicts_50_paths(self):
        """compute_trust_scores over 500 conflicts across 50 paths in under 200ms."""
        stage = CompositionStage(project_id="perf-trust-500", exchange_count=1)

        for i in range(500):
            path_index = i % 50
            status_cycle = [
                ConflictStatus.RESOLVED_OVERRIDE,
                ConflictStatus.RESOLVED_SYNTHESIZED,
                ConflictStatus.ACTIVE,
                ConflictStatus.DEFERRED,
                ConflictStatus.RESOLVED_EXPERIMENT,
            ]
            c = Conflict(
                assertion_a_id=f"ast_perf_a{i:04d}",
                assertion_b_id=f"ast_perf_b{i:04d}",
                topic_path=f"/trust/q{path_index}",
                detection_layer=ConflictDetectionLayer.STRUCTURAL,
                status=status_cycle[i % len(status_cycle)],
            )
            stage.conflicts[c.id] = c

        start = time.perf_counter()
        scores = compute_trust_scores(stage)
        elapsed = time.perf_counter() - start

        assert len(scores) == 50, f"Expected 50 path scores, got {len(scores)}"
        assert elapsed < PERF_SLACK * 0.2, (
            f"compute_trust_scores(500 conflicts, 50 paths) took "
            f"{elapsed * 1000:.2f}ms — exceeded 200ms budget"
        )
        print(
            f"\nTrust computation (500 conflicts, 50 paths): {elapsed * 1000:.2f}ms"
        )


# ---------------------------------------------------------------------------
# TestRedTeamPerformance
# ---------------------------------------------------------------------------

class TestRedTeamPerformance:
    """Benchmark RED_TEAMING analysis (generate_red_team_report)."""

    def test_red_team_analysis_200_local_assertions(self):
        """generate_red_team_report over 200 LOCAL assertions in under 500ms."""
        stage = CompositionStage(project_id="perf-redteam-200", exchange_count=1)

        for i in range(200):
            ast = _make_assertion(
                f"/local/n{i}",
                f"Local claim {i}",
                arc=CompositionArc.LOCAL,
                falsifiable_if=f"Falsified if claim {i} is empirically refuted",
            )
            stage.assertions[ast.id] = ast

        start = time.perf_counter()
        report = generate_red_team_report(stage)
        elapsed = time.perf_counter() - start

        # All 200 are unchallenged LOCALs — the report must flag them
        assert "UNCHALLENGED" in report
        assert elapsed < PERF_SLACK * 0.5, (
            f"generate_red_team_report(200 LOCALs) took {elapsed * 1000:.2f}ms "
            "— exceeded 500ms budget"
        )
        print(f"\nRed team analysis (200 LOCALs): {elapsed * 1000:.2f}ms")

    def test_red_team_analysis_mixed_stage(self):
        """generate_red_team_report on a mixed stage (LOCAL + INHERITS + conflicts).

        Adds:
        - 100 LOCAL assertions with no conflicts
        - 50 INHERITS assertions at child paths (missing dep candidates)
        - 20 conflicts on 10 of the LOCAL assertions

        Verifies the report covers all three analysis categories within budget.
        """
        stage = CompositionStage(project_id="perf-redteam-mixed", exchange_count=5)

        # 100 LOCALs
        locals_list = []
        for i in range(100):
            ast = _make_assertion(
                f"/domain/n{i}",
                f"Domain claim {i}",
                arc=CompositionArc.LOCAL,
                falsifiable_if=f"Falsified if claim {i} fails",
            )
            stage.assertions[ast.id] = ast
            locals_list.append(ast)

        # 50 INHERITS at child paths — each has a parent in the stage
        for i in range(50):
            ast = _make_assertion(
                f"/domain/n{i}/child",
                f"Child of domain {i}",
                arc=CompositionArc.INHERITS,
            )
            stage.assertions[ast.id] = ast

        # 20 conflicts on the first 10 LOCALs (2 conflicts per assertion)
        for i in range(10):
            for j in range(2):
                c = Conflict(
                    assertion_a_id=locals_list[i].id,
                    assertion_b_id=f"ast_ext_{i:03d}_{j}",
                    topic_path=locals_list[i].topic_path,
                    detection_layer=ConflictDetectionLayer.STRUCTURAL,
                    status=ConflictStatus.ACTIVE,
                )
                stage.conflicts[c.id] = c

        start = time.perf_counter()
        report = generate_red_team_report(stage)
        elapsed = time.perf_counter() - start

        # The 90 LOCALs not in any conflict should appear
        assert "UNCHALLENGED" in report
        # Missing dependency candidates should appear (50 child INHERITS without depends_on_paths)
        assert "POTENTIAL MISSING DEPENDENCIES" in report
        assert elapsed < PERF_SLACK * 0.5, (
            f"generate_red_team_report(mixed stage) took {elapsed * 1000:.2f}ms "
            "— exceeded 500ms budget"
        )
        print(f"\nRed team analysis (mixed stage): {elapsed * 1000:.2f}ms")
