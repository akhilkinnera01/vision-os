"""Unit tests for the reasoning pipeline that avoid webcam dependencies."""

from __future__ import annotations

from common.models import BoundingBox, ContextLabel, Detection
from context.rules import ContextRulesEngine
from decision.engine import DecisionEngine
from explain.explain import ExplanationEngine
from features.builder import FeatureBuilder


def make_detection(label: str, confidence: float = 0.9) -> Detection:
    """Create a small synthetic detection for test scenarios."""
    return Detection(
        label=label,
        confidence=confidence,
        bbox=BoundingBox(0, 0, 10, 10),
        area_ratio=0.05,
    )


def test_focused_work_context() -> None:
    builder = FeatureBuilder()
    rules = ContextRulesEngine()

    features = builder.build(
        [
            make_detection("person"),
            make_detection("laptop"),
            make_detection("keyboard"),
            make_detection("mouse"),
        ],
        (720, 1280),
    )
    scene_context = rules.infer(features)

    assert scene_context.label == ContextLabel.FOCUSED_WORK
    assert scene_context.confidence > 0.6


def test_group_activity_context() -> None:
    builder = FeatureBuilder()
    rules = ContextRulesEngine()

    features = builder.build(
        [
            make_detection("person"),
            make_detection("person"),
            make_detection("person"),
            make_detection("chair"),
        ],
        (720, 1280),
    )
    scene_context = rules.infer(features)

    assert scene_context.label == ContextLabel.GROUP_ACTIVITY
    assert "3 people are visible" in scene_context.signals


def test_casual_use_context() -> None:
    builder = FeatureBuilder()
    rules = ContextRulesEngine()

    features = builder.build(
        [make_detection("cell phone"), make_detection("remote")],
        (720, 1280),
    )
    scene_context = rules.infer(features)

    assert scene_context.label == ContextLabel.CASUAL_USE


def test_decision_and_explanation_are_human_readable() -> None:
    builder = FeatureBuilder()
    rules = ContextRulesEngine()
    decision_engine = DecisionEngine()
    explanation_engine = ExplanationEngine()

    features = builder.build(
        [make_detection("person"), make_detection("laptop"), make_detection("book")],
        (720, 1280),
    )
    scene_context = rules.infer(features)
    decision = decision_engine.decide(scene_context, features)
    explanation = explanation_engine.explain(decision, scene_context, features)

    assert decision.action == "Enable productivity-oriented monitoring"
    assert explanation.summary.startswith("Focused Work:")
    assert "people=1" in explanation.summary


def test_decision_engine_requires_confirmation_before_switching() -> None:
    builder = FeatureBuilder()
    rules = ContextRulesEngine()
    decision_engine = DecisionEngine(switch_confirmations=2)

    focused_features = builder.build(
        [make_detection("person"), make_detection("laptop"), make_detection("keyboard")],
        (720, 1280),
    )
    casual_features = builder.build(
        [make_detection("cell phone"), make_detection("remote")],
        (720, 1280),
    )

    focused_context = rules.infer(focused_features)
    casual_context = rules.infer(casual_features)

    first_decision = decision_engine.decide(focused_context, focused_features)
    second_decision = decision_engine.decide(casual_context, casual_features)
    third_decision = decision_engine.decide(casual_context, casual_features)

    assert first_decision.label == ContextLabel.FOCUSED_WORK
    assert second_decision.label == ContextLabel.FOCUSED_WORK
    assert third_decision.label == ContextLabel.CASUAL_USE
