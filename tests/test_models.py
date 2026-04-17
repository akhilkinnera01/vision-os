import pytest
from common.models import BoundingBox

def test_bounding_box_properties():
    # Normal case
    bbox = BoundingBox(x1=10, y1=20, x2=30, y2=50)
    assert bbox.width == 20
    assert bbox.height == 30
    assert bbox.area == 600
    assert bbox.center == (20.0, 35.0)

def test_bounding_box_edge_cases():
    # Zero dimensions
    bbox = BoundingBox(x1=10, y1=10, x2=10, y2=10)
    assert bbox.width == 0
    assert bbox.height == 0
    assert bbox.area == 0
    assert bbox.center == (10.0, 10.0)

    # Negative coordinates
    bbox = BoundingBox(x1=-30, y1=-50, x2=-10, y2=-20)
    assert bbox.width == 20
    assert bbox.height == 30
    assert bbox.area == 600
    assert bbox.center == (-20.0, -35.0)

    # Mixed coordinates
    bbox = BoundingBox(x1=-10, y1=-10, x2=10, y2=10)
    assert bbox.width == 20
    assert bbox.height == 20
    assert bbox.area == 400
    assert bbox.center == (0.0, 0.0)

def test_bounding_box_serialization():
    bbox = BoundingBox(x1=1, y1=2, x2=3, y2=4)
    data = bbox.to_dict()
    assert data == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}

    bbox2 = BoundingBox.from_dict(data)
    assert bbox == bbox2
