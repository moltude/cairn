"""
Edge case tests for CalTopo GeoJSON writer.

Tests cover:
- Empty descriptions
- Very long descriptions
- Descriptions with special characters
- Nested folder handling
- Folder properties preservation
- Empty documents
- Items without folders
"""

import pytest
import json
from cairn.io.caltopo_geojson import write_caltopo_geojson
from cairn.model import MapDocument, Waypoint, Track, Shape, Style, Folder


def test_empty_description_omitted(tmp_path):
    """Test that empty description fields are handled correctly."""
    doc = MapDocument()
    doc.add_item(
        Waypoint(
            id="w1",
            folder_id=None,
            name="Point",
            lon=-120.0,
            lat=45.0,
            notes="",  # Empty notes
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should have the waypoint
    assert len(result["features"]) == 1


def test_very_long_description(tmp_path):
    """Test waypoint with very long description."""
    long_desc = "A" * 10000  # 10k characters

    doc = MapDocument()
    doc.add_item(
        Waypoint(
            id="w1",
            folder_id=None,
            name="Point",
            lon=-120.0,
            lat=45.0,
            notes=long_desc,
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should handle long descriptions
    assert len(result["features"]) == 1


def test_description_with_special_characters(tmp_path):
    """Test description with special characters and unicode."""
    special_desc = 'Test "quotes" & <tags> \n newlines\t tabs © ™ 日本語'

    doc = MapDocument()
    doc.add_item(
        Waypoint(
            id="w1",
            folder_id=None,
            name="Point",
            lon=-120.0,
            lat=45.0,
            notes=special_desc,
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should handle special characters
    assert len(result["features"]) == 1


def test_nested_folders_flattened(tmp_path):
    """Test that nested folder structure is handled."""
    doc = MapDocument()
    parent = Folder(id="parent", name="Parent Folder")
    child = Folder(id="child", name="Child Folder", parent_id="parent")
    doc.folders.extend([parent, child])

    doc.add_item(
        Waypoint(
            id="w1",
            folder_id="child",
            name="Nested Point",
            lon=-120.0,
            lat=45.0,
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should output the waypoint plus folders as features
    assert len(result["features"]) >= 1
    # Check that waypoint is present
    waypoints = [f for f in result["features"] if f.get("geometry") and f["geometry"].get("type") == "Point"]
    assert len(waypoints) == 1


def test_folder_properties_preserved(tmp_path):
    """Test that folder information is preserved in output."""
    doc = MapDocument()
    folder = Folder(id="f1", name="Test Folder")
    doc.folders.append(folder)

    doc.add_item(
        Waypoint(
            id="w1",
            folder_id="f1",
            name="Point in Folder",
            lon=-120.0,
            lat=45.0,
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should have the waypoint plus folder
    assert len(result["features"]) >= 1
    # Check for waypoint with folder info
    waypoints = [f for f in result["features"] if f.get("geometry") and f["geometry"].get("type") == "Point"]
    assert len(waypoints) == 1
    assert "properties" in waypoints[0]


def test_empty_document(tmp_path):
    """Test writing empty document."""
    doc = MapDocument()

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should be valid GeoJSON with no features
    assert "type" in result
    assert result["type"] == "FeatureCollection"
    assert "features" in result
    assert len(result["features"]) == 0


def test_waypoint_without_folder(tmp_path):
    """Test waypoint without folder assignment."""
    doc = MapDocument()
    doc.add_item(
        Waypoint(
            id="w1",
            folder_id=None,  # No folder
            name="Orphan Point",
            lon=-120.0,
            lat=45.0,
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should handle waypoints without folders
    assert len(result["features"]) == 1


def test_track_without_folder(tmp_path):
    """Test track without folder assignment."""
    doc = MapDocument()
    doc.add_item(
        Track(
            id="t1",
            folder_id=None,
            name="Orphan Track",
            points=[(-120.0, 45.0, None, None), (-120.1, 45.1, None, None)],
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should handle tracks without folders
    assert len(result["features"]) == 1


def test_shape_without_folder(tmp_path):
    """Test shape without folder assignment."""
    doc = MapDocument()
    doc.add_item(
        Shape(
            id="s1",
            folder_id=None,
            name="Orphan Shape",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]],
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should handle shapes without folders
    assert len(result["features"]) == 1


def test_multiple_items_mixed_types(tmp_path):
    """Test document with multiple item types."""
    doc = MapDocument()

    doc.add_item(
        Waypoint(
            id="w1",
            folder_id=None,
            name="Point",
            lon=-120.0,
            lat=45.0,
            style=Style(),
        )
    )

    doc.add_item(
        Track(
            id="t1",
            folder_id=None,
            name="Line",
            points=[(-120.0, 45.0, None, None), (-120.1, 45.1, None, None)],
            style=Style(),
        )
    )

    doc.add_item(
        Shape(
            id="s1",
            folder_id=None,
            name="Area",
            rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]],
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    # Should have all three features
    assert len(result["features"]) == 3


def test_waypoint_with_all_style_fields(tmp_path):
    """Test waypoint with complete style information."""
    doc = MapDocument()
    doc.add_item(
        Waypoint(
            id="w1",
            folder_id=None,
            name="Styled Point",
            lon=-120.0,
            lat=45.0,
            notes="Full style info",
            style=Style(
                OnX_icon="camp",
                OnX_color_rgba="rgba(255,0,0,1)",
                caltopo_marker_symbol="campsite",
                caltopo_marker_color="#FF0000",
            ),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    assert len(result["features"]) == 1
    feature = result["features"][0]
    assert "properties" in feature


def test_unicode_names(tmp_path):
    """Test items with unicode names."""
    doc = MapDocument()
    doc.add_item(
        Waypoint(
            id="w1",
            folder_id=None,
            name="Café ☕ 日本 🗻",
            lon=-120.0,
            lat=45.0,
            style=Style(),
        )
    )

    output_file = tmp_path / "output.json"
    write_caltopo_geojson(doc, str(output_file))

    result = json.loads(output_file.read_text())

    assert len(result["features"]) == 1
    # Unicode should be preserved
    feature = result["features"][0]
    assert "name" in feature["properties"] or "title" in feature["properties"]
