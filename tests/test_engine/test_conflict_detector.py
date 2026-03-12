"""Tests for engine/conflict_detector.py — Layer 1 structural detection and Layer 2 stub.

Test matrix for detect_structural_conflict:
1.  No existing assertions at path → None
2.  Same content, same path → None (agreement, not conflict)
3.  Different content, same path → Conflict with STRUCTURAL layer
4.  New assertion is stronger (lower arc) → new assertion is assertion_a_id
5.  Existing assertion is stronger → existing is assertion_a_id
6.  Inactive assertions are ignored entirely
7.  Different paths do not conflict
8.  Multiple existing assertions at path → conflict against the strongest one
9.  Same content modulo whitespace → treated as different strings (are different)
10. Tie on arc → tiebreaker (confidence, then recency) determines assertion_a_id

Test matrix for detect_semantic_conflicts (Phase 2 stub):
1.  Always returns empty list regardless of input
"""

from datetime import timedelta

import pytest

from cognitive_bridge.engine.conflict_detector import (
    detect_semantic_conflicts,
    detect_structural_conflict,
)
from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    ConflictDetectionLayer,
    _now_utc,
)
from cognitive_bridge.models.assertion import Assertion
from cognitive_bridge.models.stage import CompositionStage


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_stage() -> CompositionStage:
    """Return a fresh, empty CompositionStage."""
    return CompositionStage(project_id="test-project")


def make_assertion(
    topic_path: str = "/db/engine",
    content: str = "Use PostgreSQL",
    arc: CompositionArc = CompositionArc.REFERENCES,
    author: AssertionAuthor = AssertionAuthor.AI,
    active: bool = True,
    confidence: float = 0.5,
    created_at=None,
    **kwargs,
) -> Assertion:
    """Construct a valid non-LOCAL assertion with sensible defaults."""
    kw = dict(
        topic_path=topic_path,
        content=content,
        arc=arc,
        author=author,
        active=active,
        confidence=confidence,
    )
    if created_at is not None:
        kw["created_at"] = created_at
    kw.update(kwargs)
    return Assertion(**kw)


def make_local(
    topic_path: str = "/db/engine",
    content: str = "PostgreSQL outperforms MySQL at >1000 concurrent writes.",
    confidence: float = 0.9,
    created_at=None,
) -> Assertion:
    """Construct a valid LOCAL assertion (requires falsifiable_if)."""
    kw = dict(
        topic_path=topic_path,
        content=content,
        arc=CompositionArc.LOCAL,
        author=AssertionAuthor.USER,
        confidence=confidence,
        falsifiable_if="A benchmark showing MySQL matches or exceeds this throughput.",
    )
    if created_at is not None:
        kw["created_at"] = created_at
    return Assertion(**kw)


# ─────────────────────────────────────────────────────────────────────────────
# TestDetectStructuralConflict
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectStructuralConflict:

    # ── 1. No existing assertions at path ──────────────────────────────────

    def test_no_existing_assertions_returns_none(self) -> None:
        """Empty stage → no conflict possible."""
        stage = make_stage()
        new = make_assertion(topic_path="/db/engine", content="Use PostgreSQL")
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is None

    # ── 2. Same content, same path → agreement, not conflict ───────────────

    def test_same_content_same_path_returns_none(self) -> None:
        """Two assertions at the same path with identical content reinforce each
        other. Layer 1 must not raise a false conflict for agreement."""
        stage = make_stage()
        existing = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
        )
        stage.assertions[existing.id] = existing

        new = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",  # identical
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is None

    # ── 3. Different content, same path → Conflict ─────────────────────────

    def test_different_content_same_path_creates_conflict(self) -> None:
        """Core Layer 1 trigger: same path + different content = structural conflict."""
        stage = make_stage()
        existing = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
        )
        stage.assertions[existing.id] = existing

        new = make_assertion(
            topic_path="/db/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is not None
        assert result.detection_layer == ConflictDetectionLayer.STRUCTURAL
        assert result.detection_layer.value == "structural"
        assert result.topic_path == "/db/engine"

    # ── 4. New assertion stronger → new assertion is assertion_a_id ─────────

    def test_new_assertion_stronger_becomes_a_id(self) -> None:
        """When the new assertion has a lower (stronger) arc than the existing one,
        it should occupy assertion_a_id (the winner position)."""
        stage = make_stage()
        # Existing: REFERENCES (40) — weaker
        existing = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[existing.id] = existing

        # New: INHERITS (20) — stronger than REFERENCES
        new = make_assertion(
            topic_path="/db/engine",
            content="Use MongoDB",
            arc=CompositionArc.INHERITS,
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is not None
        assert result.assertion_a_id == new.id
        assert result.assertion_b_id == existing.id

    # ── 5. Existing assertion stronger → existing is assertion_a_id ─────────

    def test_existing_assertion_stronger_becomes_a_id(self) -> None:
        """When the existing assertion has a lower (stronger) arc than the new one,
        it should occupy assertion_a_id. This matches the example in the task spec:
        INHERITS (20) < REFERENCES (40), so existing INHERITS assertion wins."""
        stage = make_stage()
        # Existing: INHERITS (20) — stronger
        existing = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
        )
        stage.assertions[existing.id] = existing

        # New: REFERENCES (40) — weaker
        new = make_assertion(
            topic_path="/db/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is not None
        assert result.assertion_a_id == existing.id
        assert result.assertion_b_id == new.id

    # ── 6. Inactive assertions are ignored ───────────────────────────────────

    def test_inactive_assertion_ignored(self) -> None:
        """Retracted (active=False) assertions must not participate in Layer 1.
        A new assertion at a path whose only other assertion is inactive must not
        trigger a conflict."""
        stage = make_stage()
        inactive = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
            active=False,
        )
        stage.assertions[inactive.id] = inactive

        new = make_assertion(
            topic_path="/db/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is None

    def test_inactive_assertion_not_selected_as_strongest(self) -> None:
        """Even if multiple assertions exist, inactive ones are skipped when
        selecting the strongest existing assertion to conflict against."""
        stage = make_stage()
        inactive = make_assertion(
            topic_path="/db/engine",
            content="Use SQLite",
            arc=CompositionArc.LOCAL,
            active=False,
            falsifiable_if="Benchmark shows otherwise.",
        )
        stage.assertions[inactive.id] = inactive

        active_existing = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.REFERENCES,
            active=True,
        )
        stage.assertions[active_existing.id] = active_existing

        new = make_assertion(
            topic_path="/db/engine",
            content="Use MongoDB",
            arc=CompositionArc.SPECIALIZES,
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        # Conflict exists (active_existing vs new)
        assert result is not None
        # The inactive LOCAL must not appear in either slot
        assert result.assertion_a_id != inactive.id
        assert result.assertion_b_id != inactive.id

    # ── 7. Different paths do not conflict ───────────────────────────────────

    def test_different_paths_no_conflict(self) -> None:
        """Layer 1 is path-scoped. Different paths cannot produce a structural
        conflict — that would be Layer 2 (semantic), not Layer 1."""
        stage = make_stage()
        existing = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
        )
        stage.assertions[existing.id] = existing

        new = make_assertion(
            topic_path="/db/cache",  # different path
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is None

    # ── 8. Multiple existing assertions → conflict against the strongest ─────

    def test_multiple_existing_conflicts_against_strongest(self) -> None:
        """When multiple active assertions already exist at a path, Layer 1 must
        select the strongest one (sorted()[0]) as the opponent. The new assertion
        conflicts with the single strongest existing assertion, not all of them."""
        stage = make_stage()
        now = _now_utc()

        # Weakest existing: SPECIALIZES (60)
        weak = make_assertion(
            topic_path="/db/engine",
            content="Use SQLite",
            arc=CompositionArc.SPECIALIZES,
            created_at=now,
        )
        stage.assertions[weak.id] = weak

        # Stronger existing: REFERENCES (40)
        medium = make_assertion(
            topic_path="/db/engine",
            content="Use MySQL",
            arc=CompositionArc.REFERENCES,
            created_at=now,
        )
        stage.assertions[medium.id] = medium

        # Strongest existing: INHERITS (20)
        strong = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
            created_at=now,
        )
        stage.assertions[strong.id] = strong

        new = make_assertion(
            topic_path="/db/engine",
            content="Use MongoDB",
            arc=CompositionArc.PAYLOADS,  # weaker than all three
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is not None
        # The conflict is against INHERITS (the strongest existing), not REFERENCES or SPECIALIZES
        assert strong.id in (result.assertion_a_id, result.assertion_b_id)
        # The weaker existing assertions must not appear
        assert weak.id not in (result.assertion_a_id, result.assertion_b_id)
        assert medium.id not in (result.assertion_a_id, result.assertion_b_id)

    # ── 9. Whitespace differences → different strings → conflict ─────────────

    def test_whitespace_differences_treated_as_different_content(self) -> None:
        """Content comparison is exact string equality. 'Use PostgreSQL' and
        'Use PostgreSQL ' (trailing space) are different strings. The
        str_strip_whitespace=True model config strips leading/trailing
        whitespace on input, so 'Use PostgreSQL ' → 'Use PostgreSQL' after
        Pydantic processing. They become equal and therefore NOT a conflict."""
        stage = make_stage()
        existing = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
        )
        stage.assertions[existing.id] = existing

        # Trailing space will be stripped by Pydantic str_strip_whitespace
        new = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL ",  # trailing space → stripped to same value
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[new.id] = new

        # After stripping, content is identical → no conflict
        assert new.content == "Use PostgreSQL"
        result = detect_structural_conflict(stage, new)
        assert result is None

    def test_internal_whitespace_differences_are_real_conflicts(self) -> None:
        """Internal whitespace differences are NOT stripped by Pydantic.
        'Use  PostgreSQL' (double space) != 'Use PostgreSQL' → these are
        genuinely different strings and produce a conflict."""
        stage = make_stage()
        existing = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
        )
        stage.assertions[existing.id] = existing

        new = make_assertion(
            topic_path="/db/engine",
            content="Use  PostgreSQL",  # double internal space — genuinely different
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)
        assert result is not None
        assert result.detection_layer == ConflictDetectionLayer.STRUCTURAL

    # ── 10. Tie on arc → tiebreaker determines assertion_a_id ────────────────

    def test_tie_on_arc_higher_confidence_wins_a_slot(self) -> None:
        """Two assertions at the same arc: higher confidence sorts first (stronger),
        so the higher-confidence assertion becomes assertion_a_id."""
        stage = make_stage()
        now = _now_utc()

        # Existing: REFERENCES, confidence=0.3 (weaker)
        low_conf = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.REFERENCES,
            confidence=0.3,
            created_at=now,
        )
        stage.assertions[low_conf.id] = low_conf

        # New: REFERENCES, confidence=0.8 (stronger due to higher confidence)
        high_conf = make_assertion(
            topic_path="/db/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            confidence=0.8,
            created_at=now,
        )
        stage.assertions[high_conf.id] = high_conf

        result = detect_structural_conflict(stage, high_conf)

        assert result is not None
        assert result.assertion_a_id == high_conf.id  # higher confidence → stronger → a
        assert result.assertion_b_id == low_conf.id

    def test_tie_on_arc_and_confidence_newer_wins_a_slot(self) -> None:
        """Final tiebreaker: when arc and confidence are identical, newer created_at
        sorts first (stronger), so the newer assertion becomes assertion_a_id."""
        now = _now_utc()
        stage = make_stage()

        # Existing: REFERENCES, confidence=0.5, created 1 hour ago (older = weaker)
        older = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.REFERENCES,
            confidence=0.5,
            created_at=now - timedelta(hours=1),
        )
        stage.assertions[older.id] = older

        # New: REFERENCES, confidence=0.5, created now (newer = stronger)
        newer = make_assertion(
            topic_path="/db/engine",
            content="Use MongoDB",
            arc=CompositionArc.REFERENCES,
            confidence=0.5,
            created_at=now,
        )
        stage.assertions[newer.id] = newer

        result = detect_structural_conflict(stage, newer)

        assert result is not None
        assert result.assertion_a_id == newer.id  # newer → stronger → a
        assert result.assertion_b_id == older.id

    def test_local_assertion_always_wins_a_slot_over_specializes(self) -> None:
        """LOCAL (arc=10) is the strongest possible arc. When LOCAL conflicts with
        SPECIALIZES (arc=60), LOCAL must always be assertion_a_id regardless of
        which was added first or which is 'new'."""
        stage = make_stage()

        specializes = make_assertion(
            topic_path="/db/engine",
            content="Use SQLite",
            arc=CompositionArc.SPECIALIZES,
        )
        stage.assertions[specializes.id] = specializes

        local_assertion = make_local(
            topic_path="/db/engine",
            content="PostgreSQL outperforms SQLite at >1000 concurrent writes.",
        )
        stage.assertions[local_assertion.id] = local_assertion

        result = detect_structural_conflict(stage, local_assertion)

        assert result is not None
        assert result.assertion_a_id == local_assertion.id  # LOCAL is strongest → a
        assert result.assertion_b_id == specializes.id

    # ── Additional edge cases ─────────────────────────────────────────────────

    def test_conflict_id_has_cfl_prefix(self) -> None:
        """Produced Conflict IDs must use the 'cfl_' prefix."""
        stage = make_stage()
        existing = make_assertion(content="Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[existing.id] = existing

        new = make_assertion(content="Use MongoDB", arc=CompositionArc.REFERENCES)
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is not None
        assert result.id.startswith("cfl_")

    def test_conflict_assertion_ids_reference_real_assertions(self) -> None:
        """The IDs in assertion_a_id and assertion_b_id must refer to assertions
        that actually exist in the stage."""
        stage = make_stage()
        existing = make_assertion(content="Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[existing.id] = existing

        new = make_assertion(content="Use MongoDB", arc=CompositionArc.REFERENCES)
        stage.assertions[new.id] = new

        result = detect_structural_conflict(stage, new)

        assert result is not None
        assert result.assertion_a_id in stage.assertions
        assert result.assertion_b_id in stage.assertions

    def test_does_not_compare_assertion_to_itself(self) -> None:
        """The function must exclude the new assertion from the candidate list.
        A single assertion at a path cannot conflict with itself."""
        stage = make_stage()
        only = make_assertion(
            topic_path="/db/engine",
            content="Use PostgreSQL",
            arc=CompositionArc.INHERITS,
        )
        stage.assertions[only.id] = only

        result = detect_structural_conflict(stage, only)

        assert result is None

    def test_function_does_not_mutate_stage(self) -> None:
        """detect_structural_conflict is a pure function (read-only on stage).
        The stage assertions dict and conflict dict must be unchanged after the call."""
        stage = make_stage()
        existing = make_assertion(content="Use PostgreSQL", arc=CompositionArc.INHERITS)
        stage.assertions[existing.id] = existing

        new = make_assertion(content="Use MongoDB", arc=CompositionArc.REFERENCES)
        stage.assertions[new.id] = new

        assertion_count_before = len(stage.assertions)
        conflict_count_before = len(stage.conflicts)

        detect_structural_conflict(stage, new)

        assert len(stage.assertions) == assertion_count_before
        assert len(stage.conflicts) == conflict_count_before


# ─────────────────────────────────────────────────────────────────────────────
# TestDetectSemanticConflictsStub
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectSemanticConflictsGateDisabled:
    """Layer 2 gate tests: cross_path_detection disabled (the default).

    When cross_path_detection is False the function must return [] immediately
    regardless of assertion content or similarity.  These tests cover the gate
    path and do NOT require sentence-transformers.
    """

    def test_returns_empty_list_on_empty_stage(self) -> None:
        """Gate disabled + empty stage → empty list."""
        stage = make_stage()
        new = make_assertion()
        stage.assertions[new.id] = new

        result = detect_semantic_conflicts(stage, new)

        assert result == []
        assert isinstance(result, list)

    def test_returns_empty_list_with_similar_assertions_when_gate_disabled(self) -> None:
        """Gate disabled → empty list even with thematically similar content
        at different paths."""
        stage = make_stage()

        a1 = make_assertion(
            topic_path="/db/engine",
            content="PostgreSQL is a relational database management system.",
            arc=CompositionArc.SPECIALIZES,
        )
        stage.assertions[a1.id] = a1

        new = make_assertion(
            topic_path="/db/primary_store",
            content="We should use a relational database management system.",
            arc=CompositionArc.REFERENCES,
        )
        stage.assertions[new.id] = new

        result = detect_semantic_conflicts(stage, new)

        assert result == []

    def test_returns_list_not_none(self) -> None:
        """Callers iterate the result directly — must never be None."""
        stage = make_stage()
        new = make_assertion()
        stage.assertions[new.id] = new

        result = detect_semantic_conflicts(stage, new)

        assert result is not None
        assert isinstance(result, list)
