"""Tests for models/parameters.py — CognitiveParameters range and type validation.

Blueprint reference: Section 3.8 (CognitiveParameters).
Constitution rule G2 (validator-rejection symmetry).

Range commentary from source:
  semantic_threshold: [0.5, 0.99] — values below 0.5 produce excessive noise;
    values at 1.0 would require exact embedding match (unreachable).
  red_team_threshold: [3, 20] — below 3 triggers on trivial assertion counts;
    above 20 effectively disables red-teaming.
"""

import pytest
from pydantic import ValidationError

from cognitive_bridge.models.arcs import CompositionArc
from cognitive_bridge.models.parameters import CognitiveParameters


class TestCognitiveParametersDefaults:
    def test_all_eight_defaults_correct(self) -> None:
        p = CognitiveParameters()
        assert p.conflict_sensitivity == 0.5
        assert p.semantic_threshold == 0.80
        assert p.cross_path_detection is False
        assert p.exploration_budget == 3
        assert p.ai_default_arc == CompositionArc.INHERITS
        assert p.payload_surfacing is True
        assert p.red_team_threshold == 8
        assert p.cascade_auto_challenge is True

    def test_default_ai_default_arc_is_inherits_enum(self) -> None:
        p = CognitiveParameters()
        assert p.ai_default_arc == CompositionArc.INHERITS
        assert isinstance(p.ai_default_arc, CompositionArc)


class TestConflictSensitivity:
    def test_zero_accepted(self) -> None:
        assert CognitiveParameters(conflict_sensitivity=0.0).conflict_sensitivity == 0.0

    def test_one_accepted(self) -> None:
        assert CognitiveParameters(conflict_sensitivity=1.0).conflict_sensitivity == 1.0

    def test_midpoint_accepted(self) -> None:
        assert CognitiveParameters(conflict_sensitivity=0.5).conflict_sensitivity == 0.5

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(conflict_sensitivity=-0.01)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(conflict_sensitivity=1.01)

    def test_large_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(conflict_sensitivity=-100.0)


class TestSemanticThreshold:
    def test_minimum_accepted(self) -> None:
        assert CognitiveParameters(semantic_threshold=0.5).semantic_threshold == 0.5

    def test_maximum_accepted(self) -> None:
        assert CognitiveParameters(semantic_threshold=0.99).semantic_threshold == 0.99

    def test_midpoint_accepted(self) -> None:
        assert CognitiveParameters(semantic_threshold=0.75).semantic_threshold == 0.75

    def test_below_minimum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(semantic_threshold=0.49)

    def test_exactly_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(semantic_threshold=1.0)

    def test_above_maximum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(semantic_threshold=1.01)

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(semantic_threshold=0.0)


class TestExplorationBudget:
    def test_minimum_accepted(self) -> None:
        assert CognitiveParameters(exploration_budget=1).exploration_budget == 1

    def test_maximum_accepted(self) -> None:
        assert CognitiveParameters(exploration_budget=20).exploration_budget == 20

    def test_midpoint_accepted(self) -> None:
        assert CognitiveParameters(exploration_budget=10).exploration_budget == 10

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(exploration_budget=0)

    def test_above_maximum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(exploration_budget=21)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(exploration_budget=-1)


class TestRedTeamThreshold:
    def test_minimum_accepted(self) -> None:
        assert CognitiveParameters(red_team_threshold=3).red_team_threshold == 3

    def test_maximum_accepted(self) -> None:
        assert CognitiveParameters(red_team_threshold=20).red_team_threshold == 20

    def test_default_accepted(self) -> None:
        assert CognitiveParameters(red_team_threshold=8).red_team_threshold == 8

    def test_below_minimum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(red_team_threshold=2)

    def test_above_maximum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(red_team_threshold=21)

    def test_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(red_team_threshold=1)

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CognitiveParameters(red_team_threshold=0)


class TestAiDefaultArc:
    @pytest.mark.parametrize("arc", list(CompositionArc))
    def test_all_composition_arc_values_accepted(self, arc: CompositionArc) -> None:
        p = CognitiveParameters(ai_default_arc=arc)
        assert p.ai_default_arc == arc

    def test_arc_accepted_by_int_value(self) -> None:
        p = CognitiveParameters(ai_default_arc=10)
        assert p.ai_default_arc == CompositionArc.LOCAL

    def test_invalid_int_not_in_arc_enum_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError)):
            CognitiveParameters(ai_default_arc=99)

    def test_arc_value_is_composition_arc_type(self) -> None:
        p = CognitiveParameters(ai_default_arc=CompositionArc.REFERENCES)
        assert isinstance(p.ai_default_arc, CompositionArc)


class TestBooleanFields:
    def test_cross_path_detection_true(self) -> None:
        assert CognitiveParameters(cross_path_detection=True).cross_path_detection is True

    def test_cross_path_detection_false(self) -> None:
        assert CognitiveParameters(cross_path_detection=False).cross_path_detection is False

    def test_payload_surfacing_true(self) -> None:
        assert CognitiveParameters(payload_surfacing=True).payload_surfacing is True

    def test_payload_surfacing_false(self) -> None:
        assert CognitiveParameters(payload_surfacing=False).payload_surfacing is False

    def test_cascade_auto_challenge_true(self) -> None:
        assert CognitiveParameters(cascade_auto_challenge=True).cascade_auto_challenge is True

    def test_cascade_auto_challenge_false(self) -> None:
        assert CognitiveParameters(cascade_auto_challenge=False).cascade_auto_challenge is False
