"""Protocol interfaces that keep each pipeline module easy to swap."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from common.models import Decision, Detection, Explanation, SceneContext, SceneFeatures


class Detector(Protocol):
    """Contract for modules that convert frames into detections."""

    def detect(self, frame: np.ndarray) -> list[Detection]:
        ...


class FeatureBuilderProtocol(Protocol):
    """Contract for modules that turn detections into scene features."""

    def build(self, detections: list[Detection], frame_shape: tuple[int, int]) -> SceneFeatures:
        ...


class RuleEngine(Protocol):
    """Contract for modules that infer context labels from features."""

    def infer(self, features: SceneFeatures) -> SceneContext:
        ...


class DecisionEngineProtocol(Protocol):
    """Contract for modules that convert context into final decisions."""

    def decide(self, scene_context: SceneContext, features: SceneFeatures) -> Decision:
        ...


class Explainer(Protocol):
    """Contract for modules that produce human-readable reasoning."""

    def explain(
        self,
        decision: Decision,
        scene_context: SceneContext,
        features: SceneFeatures,
    ) -> Explanation:
        ...


class Renderer(Protocol):
    """Contract for modules that render an annotated frame."""

    def render(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        decision: Decision,
        explanation: Explanation,
    ) -> np.ndarray:
        ...
