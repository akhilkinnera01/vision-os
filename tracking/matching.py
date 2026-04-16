"""Matching helpers for deterministic track assignment."""

from __future__ import annotations

from math import dist

from common.models import BoundingBox


def bbox_iou(left: BoundingBox, right: BoundingBox) -> float:
    intersection_x1 = max(left.x1, right.x1)
    intersection_y1 = max(left.y1, right.y1)
    intersection_x2 = min(left.x2, right.x2)
    intersection_y2 = min(left.y2, right.y2)

    intersection_width = max(0, intersection_x2 - intersection_x1)
    intersection_height = max(0, intersection_y2 - intersection_y1)
    intersection_area = intersection_width * intersection_height
    union_area = left.area + right.area - intersection_area
    if union_area <= 0:
        return 0.0
    return intersection_area / union_area


def normalized_center_distance(left: BoundingBox, right: BoundingBox, frame_shape: tuple[int, int]) -> float:
    diagonal = max((frame_shape[0] ** 2 + frame_shape[1] ** 2) ** 0.5, 1.0)
    return dist(left.center, right.center) / diagonal
