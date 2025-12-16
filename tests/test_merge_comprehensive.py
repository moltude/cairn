"""
Comprehensive tests for merge logic.

Tests cover:
- Merging GPX + KML with different OnX_id values
- Shape/Track conflicts (prefer polygon)
- Metadata preservation and transfer
- Empty document handling
- Folder structure creation
- Waypoint/Track/Shape enrichment
"""

import pytest
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.model import MapDocument, Waypoint, Track, Shape, Style


def test_merge_adds_items_with_unique_onx_id():
    """Test that items with unique OnX_id are added from KML."""
    gpx = MapDocument()
    gpx.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Waypoint(
            id="w2",
            folder_id="f1",
            name="Peak",
            lon=-121.0,
            lat=46.0,
            style=Style(OnX_id="ID2"),  # Different ID
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert len(merged.waypoints()) == 2
    assert any(wp.name == "Camp" for wp in merged.waypoints())
    assert any(wp.name == "Peak" for wp in merged.waypoints())


def test_merge_prefers_polygon_over_track():
    """Test that Shape (polygon) is preferred over Track for same OnX_id."""
    gpx = MapDocument()
    gpx.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None), (-120.1, 45.1, None, None)],
            notes="Track notes",
            style=Style(
                OnX_id="SAME_ID",
                OnX_color_rgba="rgba(255,0,0,1)",
                OnX_style="dash",
                OnX_weight="6.0",
            ),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Shape(
            id="s1",
            folder_id="f1",
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]],
            style=Style(OnX_id="SAME_ID"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    # Should have Shape, not Track
    assert len(merged.shapes()) == 1
    assert len(merged.tracks()) == 0

    # Shape should have metadata from Track
    shape = merged.shapes()[0]
    assert shape.notes == "Track notes"
    assert shape.style.OnX_color_rgba == "rgba(255,0,0,1)"
    assert shape.style.OnX_style == "dash"
    assert shape.style.OnX_weight == "6.0"


def test_merge_transfers_track_metadata_to_shape():
    """Test that metadata is transferred from Track to Shape."""
    gpx = MapDocument()
    gpx.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            notes="Detailed notes",
            style=Style(OnX_id="ID1", OnX_color_rgba="rgba(0,255,0,1)"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Shape(
            id="s1",
            folder_id="f1",
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.0, 45.0)]],
            notes="",  # Empty
            style=Style(OnX_id="ID1"),  # No color
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    shape = merged.shapes()[0]
    assert shape.notes == "Detailed notes"
    assert shape.style.OnX_color_rgba == "rgba(0,255,0,1)"


def test_merge_does_not_overwrite_existing_shape_metadata():
    """Test that existing Shape metadata is not overwritten."""
    gpx = MapDocument()
    gpx.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            notes="Track notes",
            style=Style(OnX_id="ID1", OnX_color_rgba="rgba(255,0,0,1)"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Shape(
            id="s1",
            folder_id="f1",
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.0, 45.0)]],
            notes="Shape notes",  # Already has notes
            style=Style(OnX_id="ID1", OnX_color_rgba="rgba(0,255,0,1)"),  # Already has color
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    shape = merged.shapes()[0]
    # Should keep Shape's original metadata
    assert shape.notes == "Shape notes"
    assert shape.style.OnX_color_rgba == "rgba(0,255,0,1)"


def test_merge_empty_gpx_with_kml():
    """Test merging empty GPX with KML containing items."""
    gpx = MapDocument()

    kml = MapDocument()
    kml.add_item(
        Shape(
            id="s1",
            folder_id="f1",
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.0, 45.0)]],
            style=Style(OnX_id="ID1"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert len(merged.shapes()) == 1
    assert merged.shapes()[0].name == "Area"


def test_merge_gpx_with_empty_kml():
    """Test merging GPX with empty KML."""
    gpx = MapDocument()
    gpx.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert len(merged.waypoints()) == 1
    assert merged.waypoints()[0].name == "Camp"


def test_merge_ensures_standard_folders():
    """Test that merge ensures standard OnX folder structure exists."""
    gpx = MapDocument()
    kml = MapDocument()

    merged = merge_onx_gpx_and_kml(gpx, kml)

    # Check that standard folders are created
    folder_names = [f.name for f in merged.folders]
    assert "OnX Import" in folder_names
    assert "Waypoints" in folder_names
    assert "Tracks" in folder_names
    assert "Areas" in folder_names


def test_merge_enriches_track_notes():
    """Test that Track notes are enriched from KML if empty in GPX."""
    gpx = MapDocument()
    gpx.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            notes="",
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Track(
            id="t2",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            notes="KML notes",
            style=Style(OnX_id="ID1"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert len(merged.tracks()) == 1
    assert merged.tracks()[0].notes == "KML notes"


def test_merge_enriches_track_color():
    """Test that Track color is enriched from KML if missing in GPX."""
    gpx = MapDocument()
    gpx.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            style=Style(OnX_id="ID1"),  # No color
        )
    )

    kml = MapDocument()
    kml.add_item(
        Track(
            id="t2",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            style=Style(OnX_id="ID1", OnX_color_rgba="rgba(255,0,0,1)"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert merged.tracks()[0].style.OnX_color_rgba == "rgba(255,0,0,1)"


def test_merge_enriches_waypoint_icon():
    """Test that Waypoint icon is enriched from KML if missing in GPX."""
    gpx = MapDocument()
    gpx.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            style=Style(OnX_id="ID1"),  # No icon
        )
    )

    kml = MapDocument()
    kml.add_item(
        Waypoint(
            id="w2",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            style=Style(OnX_id="ID1", OnX_icon="camp"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert merged.waypoints()[0].style.OnX_icon == "camp"


def test_merge_enriches_waypoint_color():
    """Test that Waypoint color is enriched from KML if missing in GPX."""
    gpx = MapDocument()
    gpx.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Waypoint(
            id="w2",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            style=Style(OnX_id="ID1", OnX_color_rgba="rgba(255,0,0,1)"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert merged.waypoints()[0].style.OnX_color_rgba == "rgba(255,0,0,1)"


def test_merge_enriches_waypoint_notes():
    """Test that Waypoint notes are enriched from KML if empty in GPX."""
    gpx = MapDocument()
    gpx.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            notes="",
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Waypoint(
            id="w2",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            notes="KML notes",
            style=Style(OnX_id="ID1"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert merged.waypoints()[0].notes == "KML notes"


def test_merge_enriches_shape_rings():
    """Test that Shape rings are enriched if empty in GPX."""
    gpx = MapDocument()
    gpx.add_item(
        Shape(
            id="s1",
            folder_id="f1",
            name="Area",
            rings=[],  # Empty
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Shape(
            id="s2",
            folder_id="f1",
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.0, 45.0)]],
            style=Style(OnX_id="ID1"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert len(merged.shapes()[0].rings) > 0


def test_merge_adds_items_without_onx_id():
    """Test that items without OnX_id are added from KML."""
    gpx = MapDocument()
    kml = MapDocument()
    kml.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Unmarked",
            lon=-120.0,
            lat=45.0,
            style=Style(),  # No OnX_id
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert len(merged.waypoints()) == 1
    assert merged.waypoints()[0].name == "Unmarked"


def test_merge_records_metadata():
    """Test that merge records metadata about the merge."""
    gpx = MapDocument(metadata={"path": "test.gpx"})
    kml = MapDocument(metadata={"path": "test.kml"})

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert merged.metadata["merged_kml"] is True
    assert merged.metadata["kml_path"] == "test.kml"
    assert merged.metadata["path"] == "test.gpx"  # Preserved from GPX


def test_merge_records_prefer_polygon_decision():
    """Test that merge decision is recorded in extra field."""
    gpx = MapDocument()
    gpx.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Shape(
            id="s1",
            folder_id="f1",
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.0, 45.0)]],
            style=Style(OnX_id="ID1"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    shape = merged.shapes()[0]
    assert "merge_decisions" in shape.extra
    assert shape.extra["merge_decisions"][0]["action"] == "prefer_polygon"


def test_merge_ignores_conflicting_types_waypoint_track():
    """Test that conflicting types (not Shape) are handled."""
    gpx = MapDocument()
    gpx.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Point",
            lon=-120.0,
            lat=45.0,
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            style=Style(OnX_id="ID1"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    # Waypoint should be kept (existing), Track ignored
    assert len(merged.waypoints()) == 1
    assert len(merged.tracks()) == 0
    assert "merge_conflicts" in merged.waypoints()[0].extra


def test_merge_multiple_items():
    """Test merging with multiple items of different types."""
    gpx = MapDocument()
    gpx.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Camp",
            lon=-120.0,
            lat=45.0,
            style=Style(OnX_id="ID1"),
        )
    )
    gpx.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            style=Style(OnX_id="ID2"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Waypoint(
            id="w2",
            folder_id="f1",
            name="Peak",
            lon=-121.0,
            lat=46.0,
            style=Style(OnX_id="ID3"),
        )
    )
    kml.add_item(
        Shape(
            id="s1",
            folder_id="f1",
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.0, 45.0)]],
            style=Style(OnX_id="ID4"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert len(merged.waypoints()) == 2
    assert len(merged.tracks()) == 1
    assert len(merged.shapes()) == 1


def test_merge_prefers_shape_over_track_from_kml_first():
    """Test that Shape from GPX is kept when Track in KML has same OnX_id."""
    gpx = MapDocument()
    gpx.add_item(
        Shape(
            id="s1",
            folder_id="f1",
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.0, 45.0)]],
            notes="",
            style=Style(OnX_id="ID1"),
        )
    )

    kml = MapDocument()
    kml.add_item(
        Track(
            id="t1",
            folder_id="f1",
            name="Trail",
            points=[(-120.0, 45.0, None, None)],
            notes="Track notes",
            style=Style(OnX_id="ID1", OnX_color_rgba="rgba(255,0,0,1)"),
        )
    )

    merged = merge_onx_gpx_and_kml(gpx, kml)

    # Shape from GPX should be kept, Track from KML dropped
    assert len(merged.shapes()) == 1
    assert len(merged.tracks()) == 0

    # Track metadata IS transferred to Shape even though Shape was in GPX
    shape = merged.shapes()[0]
    assert shape.notes == "Track notes"
    assert shape.style.OnX_color_rgba == "rgba(255,0,0,1)"
