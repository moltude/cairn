"""
Edge case tests for shape deduplication logic.

Tests cover:
- Empty shapes
- Single-point lines
- Polygons with <3 vertices
- Clockwise vs counterclockwise polygons
- Rotation invariance
- Line direction invariance
"""

import pytest
from cairn.core.shape_dedup import (
    apply_shape_dedup,
    polygon_signature,
    line_signature,
    _strip_closing_point,
    _min_rotation,
)
from cairn.model import MapDocument, Shape, Track, Style


def test_empty_linestring_not_deduped():
    """Test that tracks with no points are handled gracefully."""
    track1 = Track(
        id="t1",
        folder_id="f1",
        name="Empty Track",
        points=[],
        style=Style(OnX_id="A"),
    )
    track2 = Track(
        id="t2",
        folder_id="f1",
        name="Normal Track",
        points=[(-120.0, 45.0, None, None), (-120.1, 45.1, None, None)],
        style=Style(OnX_id="B"),
    )

    doc = MapDocument(items=[track1, track2])
    report, dropped = apply_shape_dedup(doc)

    # Empty track should be ignored, not cause crash
    assert len(doc.tracks()) == 2  # Both kept
    assert report.dropped_count == 0


def test_single_point_track():
    """Test that tracks with only one point are handled gracefully."""
    track = Track(
        id="t1",
        folder_id="f1",
        name="Single Point",
        points=[(-120.0, 45.0, None, None)],
        style=Style(OnX_id="A"),
    )

    doc = MapDocument(items=[track])
    report, dropped = apply_shape_dedup(doc)

    # Single point track should be kept but not deduplicated
    assert len(doc.tracks()) == 1
    assert report.dropped_count == 0


def test_polygon_area_zero():
    """Test that degenerate polygons (all same points) are handled."""
    # Polygon with all identical points
    ring = [
        (-120.0, 45.0),
        (-120.0, 45.0),
        (-120.0, 45.0),
        (-120.0, 45.0),
    ]

    shape = Shape(
        id="s1",
        folder_id="f1",
        name="Degenerate",
        rings=[ring],
        style=Style(OnX_id="A"),
    )

    doc = MapDocument(items=[shape])
    report, dropped = apply_shape_dedup(doc)

    # Should handle gracefully
    assert len(doc.shapes()) == 1


def test_polygon_less_than_three_vertices():
    """Test that polygons with <3 vertices are handled."""
    # Two-point ring (invalid polygon)
    ring = [(-120.0, 45.0), (-120.1, 45.1)]

    shape = Shape(
        id="s1",
        folder_id="f1",
        name="Invalid Polygon",
        rings=[ring],
        style=Style(OnX_id="A"),
    )

    sig = polygon_signature(shape)
    assert sig is None  # Should return None for invalid polygon


def test_clockwise_vs_counterclockwise_polygons():
    """Test that polygon signatures consider both forward and reverse directions."""
    # Clockwise
    ring_cw = [
        (-120.0, 45.0),
        (-120.1, 45.0),
        (-120.1, 45.1),
        (-120.0, 45.1),
        (-120.0, 45.0),
    ]

    shape1 = Shape(
        id="s1",
        folder_id="f1",
        name="Test Polygon",
        rings=[ring_cw],
        style=Style(OnX_id="A"),
    )

    # Get signature - should include both forward and reverse rotations
    sig = polygon_signature(shape1)

    assert sig is not None
    assert sig[0] == "Polygon"
    # Signature includes both forward and reverse minimal rotations
    assert len(sig) == 3  # (type, forward_rotation, reverse_rotation)


def test_polygon_rotation_invariance():
    """Test that polygons with different start points are matched."""
    # Same polygon, different starting vertex
    ring1 = [
        (-120.0, 45.0),
        (-120.1, 45.0),
        (-120.1, 45.1),
        (-120.0, 45.1),
        (-120.0, 45.0),
    ]

    ring2 = [
        (-120.1, 45.0),  # Start at different vertex
        (-120.1, 45.1),
        (-120.0, 45.1),
        (-120.0, 45.0),
        (-120.1, 45.0),
    ]

    shape1 = Shape(
        id="s1",
        folder_id="f1",
        name="Rotated",
        rings=[ring1],
        style=Style(OnX_id="A"),
    )

    shape2 = Shape(
        id="s2",
        folder_id="f1",
        name="Rotated",
        rings=[ring2],
        style=Style(OnX_id="B"),
    )

    doc = MapDocument(items=[shape1, shape2])
    report, dropped = apply_shape_dedup(doc)

    assert len(doc.shapes()) == 1
    assert report.dropped_count == 1


def test_line_direction_invariance():
    """Test that lines in forward and reverse direction are matched."""
    # Forward direction
    points_fwd = [
        (-120.0, 45.0, None, None),
        (-120.1, 45.1, None, None),
        (-120.2, 45.2, None, None),
    ]

    # Reverse direction
    points_rev = list(reversed(points_fwd))

    track1 = Track(
        id="t1",
        folder_id="f1",
        name="Trail",
        points=points_fwd,
        style=Style(OnX_id="A"),
    )

    track2 = Track(
        id="t2",
        folder_id="f1",
        name="Trail",
        points=points_rev,
        style=Style(OnX_id="B"),
    )

    doc = MapDocument(items=[track1, track2])
    report, dropped = apply_shape_dedup(doc)

    assert len(doc.tracks()) == 1
    assert report.dropped_count == 1


def test_strip_closing_point():
    """Test that _strip_closing_point removes duplicate closing vertex."""
    ring = [
        (-120.0, 45.0),
        (-120.1, 45.0),
        (-120.1, 45.1),
        (-120.0, 45.0),  # Closing point
    ]

    result = _strip_closing_point(ring)

    assert len(result) == 3
    assert result[0] != result[-1]  # No longer closed


def test_strip_closing_point_already_open():
    """Test that _strip_closing_point doesn't modify already open rings."""
    ring = [
        (-120.0, 45.0),
        (-120.1, 45.0),
        (-120.1, 45.1),
    ]

    result = _strip_closing_point(ring)

    assert result == ring  # Unchanged


def test_min_rotation():
    """Test that _min_rotation finds lexicographically smallest rotation."""
    seq = [(3, 4), (1, 2), (5, 6)]

    result = _min_rotation(seq)

    # Should start with smallest tuple
    assert result[0] == (1, 2)


def test_min_rotation_empty():
    """Test that _min_rotation handles empty sequences."""
    result = _min_rotation([])
    assert result == tuple()


def test_line_signature_two_points():
    """Test line signature generation with exactly 2 points."""
    track = Track(
        id="t1",
        folder_id="f1",
        name="Short Line",
        points=[(-120.0, 45.0, None, None), (-120.1, 45.1, None, None)],
    )

    sig = line_signature(track)

    assert sig is not None
    assert sig[0] == "LineString"


def test_line_signature_none_for_empty():
    """Test that line_signature returns None for empty tracks."""
    track = Track(id="t1", folder_id="f1", name="Empty", points=[])

    sig = line_signature(track)

    assert sig is None


def test_polygon_signature_empty_rings():
    """Test that polygon_signature handles empty rings list."""
    shape = Shape(id="s1", folder_id="f1", name="Empty", rings=[])

    sig = polygon_signature(shape)

    assert sig is None


def test_polygon_signature_empty_first_ring():
    """Test that polygon_signature handles empty first ring."""
    shape = Shape(id="s1", folder_id="f1", name="Empty Ring", rings=[[]])

    sig = polygon_signature(shape)

    assert sig is None


def test_shape_dedup_keeps_better_notes():
    """Test that dedup prefers shapes with longer notes."""
    ring = [(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]

    shape1 = Shape(
        id="s1",
        folder_id="f1",
        name="Area",
        rings=[ring],
        notes="",
        style=Style(OnX_id="A"),
    )

    shape2 = Shape(
        id="s2",
        folder_id="f1",
        name="Area",
        rings=[ring],
        notes="This is a detailed description of the area.",
        style=Style(OnX_id="B"),
    )

    doc = MapDocument(items=[shape1, shape2])
    report, dropped = apply_shape_dedup(doc)

    assert len(doc.shapes()) == 1
    kept = doc.shapes()[0]
    assert kept.id == "s2"  # Has longer notes


def test_shape_dedup_prefers_onx_id():
    """Test that dedup prefers shapes with OnX_id when notes are equal."""
    ring = [(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]

    shape1 = Shape(
        id="s1",
        folder_id="f1",
        name="Area",
        rings=[ring],
        notes="",
        style=Style(),  # No OnX_id
    )

    shape2 = Shape(
        id="s2",
        folder_id="f1",
        name="Area",
        rings=[ring],
        notes="",
        style=Style(OnX_id="UUID123"),
    )

    doc = MapDocument(items=[shape1, shape2])
    report, dropped = apply_shape_dedup(doc)

    assert len(doc.shapes()) == 1
    kept = doc.shapes()[0]
    assert kept.id == "s2"  # Has OnX_id


def test_shape_dedup_different_names_not_deduplicated():
    """Test that shapes with same geometry but different names are kept."""
    ring = [(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]

    shape1 = Shape(id="s1", folder_id="f1", name="Area A", rings=[ring])
    shape2 = Shape(id="s2", folder_id="f1", name="Area B", rings=[ring])

    doc = MapDocument(items=[shape1, shape2])
    report, dropped = apply_shape_dedup(doc)

    # Different names, should not deduplicate
    assert len(doc.shapes()) == 2
    assert report.dropped_count == 0


def test_track_dedup_different_names_not_deduplicated():
    """Test that tracks with same geometry but different names are kept."""
    points = [(-120.0, 45.0, None, None), (-120.1, 45.1, None, None)]

    track1 = Track(id="t1", folder_id="f1", name="Trail A", points=points)
    track2 = Track(id="t2", folder_id="f1", name="Trail B", points=points)

    doc = MapDocument(items=[track1, track2])
    report, dropped = apply_shape_dedup(doc)

    # Different names, should not deduplicate
    assert len(doc.tracks()) == 2
    assert report.dropped_count == 0


def test_shape_dedup_preserves_waypoints():
    """Test that shape dedup doesn't affect waypoints."""
    from cairn.model import Waypoint

    ring = [(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]

    shape = Shape(id="s1", folder_id="f1", name="Area", rings=[ring])
    waypoint = Waypoint(
        id="w1",
        folder_id="f1",
        name="Point",
        lon=-120.0,
        lat=45.0,
    )

    doc = MapDocument(items=[shape, waypoint])
    report, dropped = apply_shape_dedup(doc)

    assert len(doc.waypoints()) == 1
    assert doc.waypoints()[0].id == "w1"


def test_multiple_duplicate_groups():
    """Test deduplication with multiple groups of duplicates."""
    ring1 = [(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]
    ring2 = [(-121.0, 46.0), (-121.1, 46.0), (-121.1, 46.1), (-121.0, 46.0)]

    shapes = [
        # Group 1: Area A duplicates
        Shape(id="s1", folder_id="f1", name="Area A", rings=[ring1]),
        Shape(id="s2", folder_id="f1", name="Area A", rings=[ring1]),
        # Group 2: Area B duplicates
        Shape(id="s3", folder_id="f1", name="Area B", rings=[ring2]),
        Shape(id="s4", folder_id="f1", name="Area B", rings=[ring2]),
        # Unique shape
        Shape(
            id="s5",
            folder_id="f1",
            name="Unique",
            rings=[[(-122.0, 47.0), (-122.1, 47.0), (-122.1, 47.1), (-122.0, 47.0)]],
        ),
    ]

    doc = MapDocument(items=shapes)
    report, dropped = apply_shape_dedup(doc)

    assert len(doc.shapes()) == 3  # One from each group + unique
    assert report.dropped_count == 2
    assert len(report.groups) == 2


def test_coordinate_rounding_tolerance():
    """Test that coordinates are rounded to 6 decimals for comparison."""
    # Exactly same coordinates when rounded to 6 decimals
    ring1 = [
        (-120.123456, 45.987654),
        (-120.223456, 45.987654),
        (-120.223456, 46.087654),
        (-120.123456, 45.987654),
    ]

    ring2 = [
        (-120.1234564, 45.9876544),  # Same at 6 decimals
        (-120.2234564, 45.9876544),
        (-120.2234564, 46.0876544),
        (-120.1234564, 45.9876544),
    ]

    shape1 = Shape(id="s1", folder_id="f1", name="Test", rings=[ring1])
    shape2 = Shape(id="s2", folder_id="f1", name="Test", rings=[ring2])

    doc = MapDocument(items=[shape1, shape2])
    report, dropped = apply_shape_dedup(doc)

    # Should be deduplicated (same after rounding to 6 decimals)
    assert len(doc.shapes()) == 1
    assert report.dropped_count == 1
