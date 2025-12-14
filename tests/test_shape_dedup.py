from cairn.core.shape_dedup import apply_shape_dedup
from cairn.model import MapDocument, Shape, Style


def test_shape_dedup_polygon_fuzzy_rotation_and_rounding():
    # Same polygon, different start index and tiny coordinate perturbations.
    ring_a = [
        (-114.0, 46.0),
        (-114.1, 46.0),
        (-114.1, 46.1),
        (-114.0, 46.1),
        (-114.0, 46.0),
    ]
    # rotate + small perturbation under 1e-6 rounding tolerance
    ring_b = [
        (-114.1000000004, 46.0000000002),
        (-114.1000000004, 46.1000000001),
        (-114.0000000003, 46.1000000002),
        (-114.0000000001, 46.0000000003),
        (-114.1000000004, 46.0000000002),
    ]

    s1 = Shape(id="s1", folder_id="onx_shapes", name="TestPoly", rings=[ring_a], style=Style(onx_id="A"))
    s2 = Shape(id="s2", folder_id="onx_shapes", name="TestPoly", rings=[ring_b], style=Style(onx_id="B"))

    doc = MapDocument(folders=[], items=[s1, s2], metadata={})
    report, dropped = apply_shape_dedup(doc)

    assert report.dropped_count == 1
    assert len(doc.shapes()) == 1
    assert len(dropped) == 1
