"""Tests for the Assertion model.

Covers:
- Basic construction and defaults
- Topic path pattern validation
- LOCAL falsifiability enforcement (schema gate)
- Dependency path validation (self-reference, missing leading slash)
- __lt__ ordering (arc → confidence → recency)
- Confidence bounds
- Retraction lifecycle fields
- Embedding excluded from serialization
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from cognitive_bridge.models.arcs import (
    AssertionAuthor,
    AssumptionStatus,
    CompositionArc,
    EvidenceType,
    _now_utc,
)
from cognitive_bridge.models.assertion import Assertion


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def make_assertion(**overrides) -> Assertion:
    """Construct a valid SPECIALIZES assertion with sensible defaults.

    SPECIALIZES (arc=60) does not require falsifiable_if, making it the
    simplest valid assertion type for tests that aren't focused on LOCAL rules.
    """
    defaults = dict(
        topic_path="/architecture/database/engine",
        content="PostgreSQL is a relational database.",
        arc=CompositionArc.SPECIALIZES,
        author=AssertionAuthor.AI,
    )
    defaults.update(overrides)
    return Assertion(**defaults)


def make_local(**overrides) -> Assertion:
    """Construct a valid LOCAL assertion (includes required falsifiable_if)."""
    defaults = dict(
        topic_path="/architecture/database/engine",
        content="PostgreSQL outperforms MySQL at >1000 concurrent writes.",
        arc=CompositionArc.LOCAL,
        author=AssertionAuthor.USER,
        falsifiable_if="A benchmark showing MySQL matches or exceeds this throughput.",
    )
    defaults.update(overrides)
    return Assertion(**defaults)


# ─────────────────────────────────────────────────────────────────
# Construction and defaults
# ─────────────────────────────────────────────────────────────────

class TestAssertionConstruction:
    def test_minimal_valid_assertion(self) -> None:
        a = make_assertion()
        assert a.topic_path == "/architecture/database/engine"
        assert a.content == "PostgreSQL is a relational database."
        assert a.arc == CompositionArc.SPECIALIZES
        assert a.author == AssertionAuthor.AI

    def test_id_generated_with_prefix(self) -> None:
        a = make_assertion()
        assert a.id.startswith("ast_")
        assert len(a.id) == 16  # "ast_" (4) + 12 hex chars

    def test_id_unique_per_instance(self) -> None:
        ids = {make_assertion().id for _ in range(50)}
        assert len(ids) == 50

    def test_defaults(self) -> None:
        a = make_assertion()
        assert a.active is True
        assert a.confidence == 0.5
        assert a.evidence == []
        assert a.evidence_type == EvidenceType.UNVERIFIED
        assert a.depends_on_paths == []
        assert a.falsifiable_if is None
        assert a.assumption_status == AssumptionStatus.LIVE
        assert a.retracted_at is None
        assert a.embedding is None
        assert a.tags == []

    def test_created_at_is_utc_aware(self) -> None:
        a = make_assertion()
        assert a.created_at.tzinfo is not None
        assert a.created_at.tzinfo == timezone.utc

    def test_all_arc_types_constructible_without_falsifiable_if(self) -> None:
        """Every non-LOCAL arc must work without falsifiable_if."""
        non_local_arcs = [
            CompositionArc.INHERITS,
            CompositionArc.VARIANT_SET,
            CompositionArc.REFERENCES,
            CompositionArc.PAYLOADS,
            CompositionArc.SPECIALIZES,
        ]
        for arc in non_local_arcs:
            a = make_assertion(arc=arc)
            assert a.arc == arc

    def test_evidence_and_tags_stored(self) -> None:
        a = make_assertion(
            evidence=["https://example.com/benchmark"],
            evidence_type=EvidenceType.CITED,
            tags=["performance", "database"],
        )
        assert a.evidence == ["https://example.com/benchmark"]
        assert a.evidence_type == EvidenceType.CITED
        assert a.tags == ["performance", "database"]


# ─────────────────────────────────────────────────────────────────
# Topic path pattern validation
# ─────────────────────────────────────────────────────────────────

class TestTopicPathValidation:
    def test_valid_simple_path(self) -> None:
        a = make_assertion(topic_path="/architecture")
        assert a.topic_path == "/architecture"

    def test_valid_nested_path(self) -> None:
        a = make_assertion(topic_path="/architecture/database/engine")
        assert a.topic_path == "/architecture/database/engine"

    def test_valid_path_with_underscores(self) -> None:
        a = make_assertion(topic_path="/project/sub_module/config")
        assert a.topic_path == "/project/sub_module/config"

    def test_valid_path_with_numbers(self) -> None:
        a = make_assertion(topic_path="/layer1/component2")
        assert a.topic_path == "/layer1/component2"

    def test_invalid_no_leading_slash(self) -> None:
        with pytest.raises(ValidationError):
            make_assertion(topic_path="architecture/database")

    def test_invalid_uppercase_segment(self) -> None:
        with pytest.raises(ValidationError):
            make_assertion(topic_path="/Architecture/Database")

    def test_invalid_trailing_slash(self) -> None:
        with pytest.raises(ValidationError):
            make_assertion(topic_path="/architecture/database/")

    def test_invalid_empty_string(self) -> None:
        with pytest.raises(ValidationError):
            make_assertion(topic_path="")

    def test_invalid_root_only_slash(self) -> None:
        """Bare '/' is not a valid prim path — must have at least one segment."""
        with pytest.raises(ValidationError):
            make_assertion(topic_path="/")

    def test_invalid_spaces_in_path(self) -> None:
        with pytest.raises(ValidationError):
            make_assertion(topic_path="/architecture/my component")

    def test_invalid_hyphen_in_path(self) -> None:
        """Hyphens are not in the allowed character set [a-z0-9_/]."""
        with pytest.raises(ValidationError):
            make_assertion(topic_path="/architecture/my-component")


# ─────────────────────────────────────────────────────────────────
# LOCAL falsifiability enforcement
# ─────────────────────────────────────────────────────────────────

class TestLocalFalsifiabilityValidator:
    def test_local_without_falsifiable_if_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Assertion(
                topic_path="/architecture/database/engine",
                content="PostgreSQL is best.",
                arc=CompositionArc.LOCAL,
                author=AssertionAuthor.AI,
                # falsifiable_if omitted — must be rejected
            )
        assert "falsifiable_if" in str(exc_info.value) or "dogma" in str(exc_info.value)

    def test_local_with_empty_string_falsifiable_if_raises(self) -> None:
        """Empty string is falsy — should be treated the same as None."""
        with pytest.raises(ValidationError):
            Assertion(
                topic_path="/architecture/database/engine",
                content="PostgreSQL is best.",
                arc=CompositionArc.LOCAL,
                author=AssertionAuthor.AI,
                falsifiable_if="",
            )

    def test_local_with_falsifiable_if_succeeds(self) -> None:
        a = make_local()
        assert a.arc == CompositionArc.LOCAL
        assert a.falsifiable_if is not None

    def test_inherits_without_falsifiable_if_succeeds(self) -> None:
        a = make_assertion(arc=CompositionArc.INHERITS)
        assert a.falsifiable_if is None

    def test_specializes_without_falsifiable_if_succeeds(self) -> None:
        a = make_assertion(arc=CompositionArc.SPECIALIZES)
        assert a.falsifiable_if is None

    def test_non_local_can_have_falsifiable_if(self) -> None:
        """Non-LOCAL arcs may optionally include falsifiable_if."""
        a = make_assertion(
            arc=CompositionArc.INHERITS,
            falsifiable_if="If domain expert consensus shifts.",
        )
        assert a.falsifiable_if == "If domain expert consensus shifts."


# ─────────────────────────────────────────────────────────────────
# Dependency path validation
# ─────────────────────────────────────────────────────────────────

class TestDependencyPathValidation:
    def test_self_referential_dependency_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            make_assertion(
                topic_path="/architecture/database/engine",
                depends_on_paths=["/architecture/database/engine"],
            )
        assert "own path" in str(exc_info.value)

    def test_dependency_without_leading_slash_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            make_assertion(
                depends_on_paths=["architecture/database"],
            )
        assert "must match topic_path pattern" in str(exc_info.value)

    def test_valid_single_dependency(self) -> None:
        a = make_assertion(
            topic_path="/architecture/database/engine",
            depends_on_paths=["/architecture/database"],
        )
        assert a.depends_on_paths == ["/architecture/database"]

    def test_valid_multiple_dependencies(self) -> None:
        a = make_assertion(
            topic_path="/architecture/database/engine",
            depends_on_paths=[
                "/architecture/database",
                "/infrastructure/hardware",
            ],
        )
        assert len(a.depends_on_paths) == 2

    def test_empty_dependencies_valid(self) -> None:
        a = make_assertion(depends_on_paths=[])
        assert a.depends_on_paths == []

    def test_mixed_valid_and_invalid_deps_raises(self) -> None:
        """If any dep is invalid, the whole assertion must be rejected."""
        with pytest.raises(ValidationError):
            make_assertion(
                topic_path="/architecture/database/engine",
                depends_on_paths=[
                    "/architecture/database",  # valid
                    "architecture/database/engine",  # invalid: no leading slash
                ],
            )


# ─────────────────────────────────────────────────────────────────
# __lt__ ordering
# ─────────────────────────────────────────────────────────────────

class TestAssertionOrdering:
    def test_local_beats_inherits(self) -> None:
        """LOCAL (10) < INHERITS (20) — LOCAL is stronger and sorts first."""
        local = make_local()
        inherits = make_assertion(arc=CompositionArc.INHERITS)
        assert local < inherits
        assert not (inherits < local)

    def test_inherits_beats_specializes(self) -> None:
        inherits = make_assertion(arc=CompositionArc.INHERITS)
        specializes = make_assertion(arc=CompositionArc.SPECIALIZES)
        assert inherits < specializes

    def test_full_livrps_sort_order(self) -> None:
        """sorted(assertions)[0] must be the LOCAL winner."""
        now = _now_utc()
        local = make_local(created_at=now)
        inherits = make_assertion(arc=CompositionArc.INHERITS, created_at=now)
        variant = make_assertion(arc=CompositionArc.VARIANT_SET, created_at=now)
        references = make_assertion(arc=CompositionArc.REFERENCES, created_at=now)
        payloads = make_assertion(arc=CompositionArc.PAYLOADS, created_at=now)
        specializes = make_assertion(arc=CompositionArc.SPECIALIZES, created_at=now)

        shuffled = [specializes, references, local, payloads, variant, inherits]
        result = sorted(shuffled)

        assert result[0].arc == CompositionArc.LOCAL
        assert result[1].arc == CompositionArc.INHERITS
        assert result[2].arc == CompositionArc.VARIANT_SET
        assert result[3].arc == CompositionArc.REFERENCES
        assert result[4].arc == CompositionArc.PAYLOADS
        assert result[5].arc == CompositionArc.SPECIALIZES

    def test_same_arc_higher_confidence_wins(self) -> None:
        """With identical arc, the assertion with higher confidence sorts first."""
        low_conf = make_assertion(arc=CompositionArc.INHERITS, confidence=0.3)
        high_conf = make_assertion(arc=CompositionArc.INHERITS, confidence=0.9)
        assert high_conf < low_conf
        assert sorted([low_conf, high_conf])[0] == high_conf

    def test_same_arc_same_confidence_newer_wins(self) -> None:
        """With identical arc and confidence, the newer assertion sorts first."""
        now = _now_utc()
        older = make_assertion(
            arc=CompositionArc.INHERITS,
            confidence=0.7,
            created_at=now - timedelta(hours=1),
        )
        newer = make_assertion(
            arc=CompositionArc.INHERITS,
            confidence=0.7,
            created_at=now,
        )
        assert newer < older
        assert sorted([older, newer])[0] == newer

    def test_sort_is_stable_winner_is_first(self) -> None:
        """sorted()[0] should always be the composition winner."""
        now = _now_utc()
        a1 = make_local(confidence=0.9, created_at=now)
        a2 = make_assertion(arc=CompositionArc.SPECIALIZES, confidence=1.0, created_at=now)
        # LOCAL always beats SPECIALIZES regardless of confidence
        assert sorted([a2, a1])[0] == a1

    def test_three_way_tiebreak_by_recency(self) -> None:
        now = _now_utc()
        a1 = make_assertion(
            arc=CompositionArc.REFERENCES, confidence=0.5,
            created_at=now - timedelta(minutes=10),
        )
        a2 = make_assertion(
            arc=CompositionArc.REFERENCES, confidence=0.5,
            created_at=now - timedelta(minutes=5),
        )
        a3 = make_assertion(
            arc=CompositionArc.REFERENCES, confidence=0.5,
            created_at=now,
        )
        result = sorted([a1, a3, a2])
        assert result[0] == a3
        assert result[1] == a2
        assert result[2] == a1


# ─────────────────────────────────────────────────────────────────
# Confidence bounds
# ─────────────────────────────────────────────────────────────────

class TestConfidenceBounds:
    def test_confidence_zero_is_valid(self) -> None:
        a = make_assertion(confidence=0.0)
        assert a.confidence == 0.0

    def test_confidence_one_is_valid(self) -> None:
        a = make_assertion(confidence=1.0)
        assert a.confidence == 1.0

    def test_confidence_midpoint_is_valid(self) -> None:
        a = make_assertion(confidence=0.5)
        assert a.confidence == 0.5

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_assertion(confidence=-0.1)

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_assertion(confidence=1.1)

    def test_confidence_exactly_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_assertion(confidence=-1.0)


# ─────────────────────────────────────────────────────────────────
# Retraction lifecycle
# ─────────────────────────────────────────────────────────────────

class TestRetraction:
    def test_retraction_sets_active_false(self) -> None:
        a = make_assertion()
        assert a.active is True
        a.active = False
        assert a.active is False

    def test_retracted_at_defaults_to_none(self) -> None:
        a = make_assertion()
        assert a.retracted_at is None

    def test_retracted_at_can_be_set(self) -> None:
        now = _now_utc()
        a = make_assertion(active=False, retracted_at=now)
        assert a.retracted_at == now
        assert a.active is False

    def test_retracted_assertion_still_has_content(self) -> None:
        """Non-destructive: retracted assertions keep all their data."""
        a = make_assertion(active=False, retracted_at=_now_utc())
        assert a.content == "PostgreSQL is a relational database."
        assert a.topic_path == "/architecture/database/engine"


# ─────────────────────────────────────────────────────────────────
# Embedding excluded from serialization
# ─────────────────────────────────────────────────────────────────

class TestEmbeddingExclusion:
    def test_embedding_excluded_from_model_dump(self) -> None:
        a = make_assertion(embedding=[0.1, 0.2, 0.3])
        dumped = a.model_dump()
        assert "embedding" not in dumped

    def test_embedding_accessible_on_instance(self) -> None:
        """Exclusion from dump doesn't mean it's unavailable on the object."""
        a = make_assertion(embedding=[0.1, 0.2, 0.3])
        assert a.embedding == [0.1, 0.2, 0.3]

    def test_none_embedding_also_excluded(self) -> None:
        a = make_assertion()
        dumped = a.model_dump()
        assert "embedding" not in dumped

    def test_model_dump_contains_expected_fields(self) -> None:
        a = make_assertion()
        dumped = a.model_dump()
        required_fields = {
            "id", "topic_path", "content", "arc", "author",
            "evidence", "evidence_type", "depends_on_paths",
            "falsifiable_if", "assumption_status", "active",
            "created_at", "retracted_at", "confidence", "tags",
        }
        assert required_fields.issubset(set(dumped.keys()))
