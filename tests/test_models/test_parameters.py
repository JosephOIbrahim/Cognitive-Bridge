"""Tests for the CognitiveParameters model."""

import pytest
from pydantic import ValidationError

from cognitive_bridge.models.arcs import CompositionArc
from cognitive_bridge.models.parameters import CognitiveParameters


class TestCognitiveParametersDefaults:
    def test_default_construction_succeeds(self) -> None:
        p = CognitiveParameters()
        assert p.conflict_sensitivity == 0.5
        assert p.semantic_threshold == 0.80
        assert p.cross_path_detection is False
        assert p.exploration_budget == 3
        assert p.ai_default_arc == CompositionArc.INHERITS
        assert p.payload_surfacing is True
        assert p.red_team_threshold == 8
        assert p.cascade_auto_challenge is True

    def test_ai_default_arc_is_inherits(self) -> None:
        p = CognitiveParameters()
        assert p.ai_default_arc == CompositionArc.INHERITS
        assert p.ai_default_arc == 20  # INHERITS integer value


class TestConflictSensitivityBounds:
    def test_lower_bound_zero_accepted(self) -> None:
        p = CognitiveParameters(conflict_sensitivity=0.0)
        assert p.conflict_sensitivity == 0.0

    def test_upper_bound_one_accepted(self) -> None:
        p = CognitiveParameters(conflict_sensitivity=1.0)
        assert p.conflict_sensitivity == 1.0

    def test_midrange_accepted(self) -> None:
        p = CognitiveParameters(conflict_sensitivity=0.75)
        assert p.conflict_sensitivity == 0.75

    def test_below_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            CognitiveParameters(conflict_sensitivity=-0.1)
        errors = exc_info.value.errors()
        assert any("conflict_sensitivity" in str(e) for e in errors)

    def test_above_upper_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            CognitiveParameters(conflict_sensitivity=1.1)
        errors = exc_info.value.errors()
        assert any("conflict_sensitivity" in str(e) for e in errors)


class TestSemanticThresholdBounds:
    def test_lower_bound_half_accepted(self) -> None:
        p = CognitiveParameters(semantic_threshold=0.5)
        assert p.semantic_threshold == 0.5

    def test_upper_bound_099_accepted(self) -> None:
        p = CognitiveParameters(semantic_threshold=0.99)
        assert p.semantic_threshold == 0.99

    def test_below_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            CognitiveParameters(semantic_threshold=0.49)
        errors = exc_info.value.errors()
        assert any("semantic_threshold" in str(e) for e in errors)

    def test_at_one_raises(self) -> None:
        # Upper bound is le=0.99, so 1.0 should fail
        with pytest.raises(ValidationError) as exc_info:
            CognitiveParameters(semantic_threshold=1.0)
        errors = exc_info.value.errors()
        assert any("semantic_threshold" in str(e) for e in errors)


class TestRedTeamThresholdBounds:
    def test_lower_bound_three_accepted(self) -> None:
        p = CognitiveParameters(red_team_threshold=3)
        assert p.red_team_threshold == 3

    def test_upper_bound_twenty_accepted(self) -> None:
        p = CognitiveParameters(red_team_threshold=20)
        assert p.red_team_threshold == 20

    def test_below_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            CognitiveParameters(red_team_threshold=2)
        errors = exc_info.value.errors()
        assert any("red_team_threshold" in str(e) for e in errors)

    def test_above_upper_bound_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            CognitiveParameters(red_team_threshold=21)
        errors = exc_info.value.errors()
        assert any("red_team_threshold" in str(e) for e in errors)


class TestExplorationBudgetBounds:
    def test_lower_bound_one_accepted(self) -> None:
        p = CognitiveParameters(exploration_budget=1)
        assert p.exploration_budget == 1

    def test_upper_bound_twenty_accepted(self) -> None:
        p = CognitiveParameters(exploration_budget=20)
        assert p.exploration_budget == 20

    def test_below_lower_bound_raises(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(exploration_budget=0)

    def test_above_upper_bound_raises(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(exploration_budget=21)


class TestAiDefaultArc:
    def test_accepts_all_composition_arcs(self) -> None:
        for arc in CompositionArc:
            p = CognitiveParameters(ai_default_arc=arc)
            assert p.ai_default_arc == arc

    def test_accepts_arc_by_integer_value(self) -> None:
        p = CognitiveParameters(ai_default_arc=10)
        assert p.ai_default_arc == CompositionArc.LOCAL
