"""Tests for the Variant and VariantSet models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cognitive_bridge.models.variant_set import Variant, VariantSet


def _make_variant(name: str = "option_a", content: str = "Hypothesis A.") -> Variant:
    """Return a minimal valid Variant."""
    return Variant(name=name, content=content)


def _make_variant_set(**kwargs) -> VariantSet:
    """Return a minimal valid VariantSet with two variants, merging any overrides."""
    defaults = dict(
        name="Database engine options",
        topic_path="/architecture/database/engine",
        variants=[
            _make_variant("option_a", "Use PostgreSQL."),
            _make_variant("option_b", "Use SQLite."),
        ],
    )
    defaults.update(kwargs)
    return VariantSet(**defaults)


class TestVariantConstruction:
    """Variant model construction and defaults."""

    def test_minimal_construction(self) -> None:
        v = _make_variant()
        assert v.name == "option_a"
        assert v.content == "Hypothesis A."

    def test_list_fields_default_to_empty(self) -> None:
        v = _make_variant()
        assert v.supporting_assertion_ids == []
        assert v.evidence_for == []
        assert v.evidence_against == []
        assert v.implications == []

    def test_activation_condition_defaults_to_none(self) -> None:
        v = _make_variant()
        assert v.activation_condition is None

    def test_active_defaults_to_true(self) -> None:
        v = _make_variant()
        assert v.active is True

    def test_accepts_supporting_assertion_ids(self) -> None:
        v = Variant(
            name="opt",
            content="Some hypothesis.",
            supporting_assertion_ids=["ast_aabbccddee11", "ast_112233445566"],
        )
        assert len(v.supporting_assertion_ids) == 2

    def test_whitespace_stripped_from_name(self) -> None:
        v = Variant(name="  option_a  ", content="Content.")
        assert v.name == "option_a"


class TestVariantSetConstruction:
    """VariantSet model construction and defaults."""

    def test_minimal_construction(self) -> None:
        vs = _make_variant_set()
        assert vs.name == "Database engine options"
        assert vs.topic_path == "/architecture/database/engine"
        assert len(vs.variants) == 2

    def test_id_auto_generated_with_var_prefix(self) -> None:
        vs = _make_variant_set()
        assert vs.id.startswith("var_")
        assert len(vs.id) == 4 + 12  # "var_" + 12 hex chars

    def test_id_uniqueness(self) -> None:
        ids = {_make_variant_set().id for _ in range(50)}
        assert len(ids) == 50

    def test_created_at_is_utc_aware(self) -> None:
        vs = _make_variant_set()
        assert isinstance(vs.created_at, datetime)
        assert vs.created_at.tzinfo is not None
        assert vs.created_at.tzinfo == timezone.utc


class TestVariantSetMinLengthConstraint:
    """variants field requires at least 2 items."""

    def test_one_variant_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            VariantSet(
                name="Single option",
                topic_path="/architecture/database/engine",
                variants=[_make_variant("only_option", "Only hypothesis.")],
            )
        errors = exc_info.value.errors()
        # Must have exactly one error on the variants field
        assert any(
            "variants" in str(e["loc"]) or e["loc"] == ("variants",)
            for e in errors
        )

    def test_zero_variants_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            VariantSet(
                name="Empty set",
                topic_path="/architecture/database/engine",
                variants=[],
            )

    def test_two_variants_passes(self) -> None:
        vs = _make_variant_set()
        assert len(vs.variants) == 2

    def test_three_variants_passes(self) -> None:
        vs = _make_variant_set(
            variants=[
                _make_variant("a", "Alpha."),
                _make_variant("b", "Beta."),
                _make_variant("c", "Gamma."),
            ]
        )
        assert len(vs.variants) == 3


class TestVariantSetDefaults:
    """Default values for optional fields."""

    def test_source_conflict_id_defaults_to_none(self) -> None:
        vs = _make_variant_set()
        assert vs.source_conflict_id is None

    def test_source_red_team_defaults_to_false(self) -> None:
        vs = _make_variant_set()
        assert vs.source_red_team is False

    def test_resolved_defaults_to_false(self) -> None:
        vs = _make_variant_set()
        assert vs.resolved is False

    def test_resolution_fields_default_to_none(self) -> None:
        vs = _make_variant_set()
        assert vs.resolved_variant_name is None
        assert vs.resolution_evidence is None
        assert vs.resolved_at is None


class TestVariantSetResolution:
    """Resolution fields accept values correctly."""

    def test_resolution_fields_accept_values(self) -> None:
        vs = _make_variant_set(
            resolved=True,
            resolved_variant_name="option_a",
            resolution_evidence="Benchmark results showed PostgreSQL 2x faster.",
        )
        assert vs.resolved is True
        assert vs.resolved_variant_name == "option_a"
        assert vs.resolution_evidence == "Benchmark results showed PostgreSQL 2x faster."

    def test_source_conflict_id_accepted(self) -> None:
        vs = _make_variant_set(source_conflict_id="cfl_aabbccddee11")
        assert vs.source_conflict_id == "cfl_aabbccddee11"

    def test_source_red_team_true(self) -> None:
        vs = _make_variant_set(source_red_team=True)
        assert vs.source_red_team is True
