"""Published performance benchmarks (pytest-benchmark).

These are NOT part of the merge-gate test suite: they live outside
``testpaths = ["tests"]`` so ``pytest -q`` never collects them. They run only
in the dedicated Benchmarks workflow, which publishes the timing history to a
GitHub Pages dashboard and comments on >2x regressions.

Run locally::

    pip install -e ".[bench]"
    pytest benchmarks/ --benchmark-json output.json

Two-tier design: ``tests/test_integration/test_performance.py`` holds fast,
coarse gross-regression guards that run on every PR (with generous budgets);
this file holds the precise, tracked-over-time benchmarks that get published.
"""

from __future__ import annotations

from cognitive_bridge.bridge.usda_export import export_stage_to_usda
from cognitive_bridge.bridge.usda_resolve import resolve_via_text
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


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _path(i: int) -> str:
    return f"/path/n{i}"


def _assertion(
    path: str,
    content: str,
    arc: CompositionArc = CompositionArc.INHERITS,
    **kw,
) -> Assertion:
    if arc == CompositionArc.LOCAL and "falsifiable_if" not in kw:
        kw["falsifiable_if"] = f"Falsified if {content} is wrong"
    return Assertion(
        topic_path=path, content=content, arc=arc, author=AssertionAuthor.AI, **kw
    )


def _stage(n: int, project_id: str = "bench") -> CompositionStage:
    """n assertions at n unique paths (one INHERITS assertion per path)."""
    stage = CompositionStage(project_id=project_id, exchange_count=1)
    for i in range(n):
        a = _assertion(_path(i), f"Content {i}")
        stage.assertions[a.id] = a
    return stage


def _shadow_stage(n_paths: int = 100) -> CompositionStage:
    """n_paths paths x 3 arcs = 3-deep shadow stack per path."""
    stage = CompositionStage(project_id="bench-shadow", exchange_count=1)
    for i in range(n_paths):
        for arc in (
            CompositionArc.INHERITS,
            CompositionArc.SPECIALIZES,
            CompositionArc.REFERENCES,
        ):
            a = _assertion(_path(i), f"Content {i} {arc.name}", arc=arc)
            stage.assertions[a.id] = a
    return stage


def _fan_out(n: int) -> tuple[CompositionStage, str]:
    """One root with n direct dependents. Returns (stage, root_path)."""
    stage = CompositionStage(project_id="bench-cascade", exchange_count=1)
    root = _assertion("/root/foundation", "Root")
    stage.assertions[root.id] = root
    for i in range(n):
        dep = _assertion(
            f"/dep/n{i}", f"Dependent {i}", depends_on_paths=["/root/foundation"]
        )
        stage.assertions[dep.id] = dep
    return stage, "/root/foundation"


def _conflict_stage(n: int, paths: int) -> CompositionStage:
    stage = CompositionStage(project_id="bench-trust", exchange_count=1)
    for i in range(n):
        c = Conflict(
            assertion_a_id=f"ast_a{i:04d}",
            assertion_b_id=f"ast_b{i:04d}",
            topic_path=f"/trust/p{i % paths}",
            detection_layer=ConflictDetectionLayer.STRUCTURAL,
            status=(
                ConflictStatus.RESOLVED_OVERRIDE if i % 2 == 0 else ConflictStatus.ACTIVE
            ),
        )
        stage.conflicts[c.id] = c
    return stage


def _local_stage(n: int) -> CompositionStage:
    stage = CompositionStage(project_id="bench-redteam", exchange_count=1)
    for i in range(n):
        a = _assertion(
            f"/local/n{i}",
            f"Local claim {i}",
            arc=CompositionArc.LOCAL,
            falsifiable_if=f"Falsified if claim {i} refuted",
        )
        stage.assertions[a.id] = a
    return stage


# ---------------------------------------------------------------------------
# resolve()
# ---------------------------------------------------------------------------

def test_resolve_50(benchmark):
    stage = _stage(50)
    result = benchmark(stage.resolve)
    assert len(result) == 50


def test_resolve_100(benchmark):
    stage = _stage(100)
    result = benchmark(stage.resolve)
    assert len(result) == 100


def test_resolve_500(benchmark):
    stage = _stage(500)
    result = benchmark(stage.resolve)
    assert len(result) == 500


def test_resolve_shadow_stacks_100x3(benchmark):
    stage = _shadow_stage(100)
    result = benchmark(stage.resolve)
    assert len(result) == 100


# ---------------------------------------------------------------------------
# conflict detection
# ---------------------------------------------------------------------------

def test_structural_detection_500(benchmark):
    stage = _stage(500)
    probe = _assertion(_path(250), "A competing claim at path 250")
    stage.assertions[probe.id] = probe
    result = benchmark(detect_structural_conflict, stage, probe)
    assert result is not None


# ---------------------------------------------------------------------------
# cascade — mutating target: rebuild fresh state each round via pedantic so the
# measured call always sees an un-cascaded stage (iterations=1 is required).
# ---------------------------------------------------------------------------

def test_cascade_50_dependents(benchmark):
    def setup():
        stage, root = _fan_out(50)
        return (stage, root, "new_winner_id"), {}

    result = benchmark.pedantic(
        detect_cascading_conflicts, setup=setup, rounds=50, iterations=1
    )
    assert len(result) == 50


# ---------------------------------------------------------------------------
# trust + red team
# ---------------------------------------------------------------------------

def test_trust_500_conflicts_50_paths(benchmark):
    stage = _conflict_stage(500, 50)
    scores = benchmark(compute_trust_scores, stage)
    assert len(scores) == 50


def test_red_team_200_locals(benchmark):
    stage = _local_stage(200)
    report = benchmark(generate_red_team_report, stage)
    assert "UNCHALLENGED" in report


# ---------------------------------------------------------------------------
# USDA bridge — export (write) and text-resolve (read) round trip
# ---------------------------------------------------------------------------

def test_usda_export_100(benchmark, tmp_path):
    stage = _stage(100)
    result = benchmark(export_stage_to_usda, stage, tmp_path)
    assert len(result) == 7  # 6 arc sublayers + stage.usda


def test_usda_resolve_via_text_100(benchmark, tmp_path):
    stage = _stage(100)
    export_stage_to_usda(stage, tmp_path)
    result = benchmark(resolve_via_text, tmp_path)
    assert len(result) == 100
