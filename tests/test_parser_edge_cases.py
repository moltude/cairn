"""Edge case tests for cairn/core/parser.py to improve coverage."""

import pytest
from cairn.core.parser import ParsedFeature, ParsedData
from pathlib import Path
import json


# ===== ParsedFeature Edge Cases =====


def test_parsed_feature_with_null_geometry():
    """Test that ParsedFeature handles null geometry."""
    feature = {
        "id": "test-1",
        "geometry": None,
        "properties": {"title": "Test"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.geometry is None
    assert parsed.geometry_type is None
    assert parsed.coordinates is None


def test_parsed_feature_with_invalid_geometry():
    """Test that ParsedFeature handles non-dict geometry."""
    feature = {
        "id": "test-1",
        "geometry": "not a dict",
        "properties": {"title": "Test"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.geometry is None


def test_parsed_feature_with_null_properties():
    """Test that ParsedFeature handles null properties."""
    feature = {
        "id": "test-1",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": None
    }
    parsed = ParsedFeature(feature)
    assert parsed.properties == {}
    assert parsed.title == "Untitled"


def test_parsed_feature_with_invalid_properties():
    """Test that ParsedFeature handles non-dict properties."""
    feature = {
        "id": "test-1",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": "not a dict"
    }
    parsed = ParsedFeature(feature)
    assert parsed.properties == {}


def test_parsed_feature_is_folder():
    """Test is_folder method."""
    feature = {
        "properties": {"class": "Folder", "title": "My Folder"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.is_folder() is True


def test_parsed_feature_is_marker():
    """Test is_marker method."""
    feature = {
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"class": "Marker", "title": "Waypoint"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.is_marker() is True


def test_parsed_feature_is_line():
    """Test is_line method with Line class."""
    feature = {
        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        "properties": {"class": "Line", "title": "Track"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.is_line() is True


def test_parsed_feature_is_line_with_shape_class():
    """Test is_line method with Shape class and LineString geometry."""
    feature = {
        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        "properties": {"class": "Shape", "title": "Track"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.is_line() is True


def test_parsed_feature_is_shape():
    """Test is_shape method."""
    feature = {
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        "properties": {"class": "Shape", "title": "Area"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.is_shape() is True


def test_parsed_feature_color_from_marker_color():
    """Test that color is extracted from marker-color."""
    feature = {
        "properties": {"marker-color": "#FF0000"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.color == "#FF0000"


def test_parsed_feature_color_from_stroke():
    """Test that color falls back to stroke when marker-color is missing."""
    feature = {
        "properties": {"stroke": "#00FF00"}
    }
    parsed = ParsedFeature(feature)
    assert parsed.color == "#00FF00"


def test_parsed_feature_stroke_properties():
    """Test extraction of stroke properties."""
    feature = {
        "properties": {
            "stroke": "#0000FF",
            "stroke-width": 8,
            "pattern": "dash"
        }
    }
    parsed = ParsedFeature(feature)
    assert parsed.stroke == "#0000FF"
    assert parsed.stroke_width == 8
    assert parsed.pattern == "dash"


# ===== ParsedData Edge Cases =====


def test_parsed_data_add_folder():
    """Test adding a folder to ParsedData."""
    data = ParsedData()
    data.add_folder("folder-1", "My Folder")

    assert "folder-1" in data.folders
    assert data.folders["folder-1"]["name"] == "My Folder"
    assert "waypoints" in data.folders["folder-1"]
    assert "tracks" in data.folders["folder-1"]
    assert "shapes" in data.folders["folder-1"]


def test_parsed_data_add_feature_to_folder():
    """Test adding a feature to a specific folder."""
    data = ParsedData()
    data.add_folder("folder-1", "My Folder")

    marker = ParsedFeature({
        "id": "marker-1",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"class": "Marker", "title": "Test"}
    })

    data.add_feature_to_folder("folder-1", marker)
    assert len(data.folders["folder-1"]["waypoints"]) == 1


def test_parsed_data_add_feature_to_nonexistent_folder():
    """Test adding a feature to a nonexistent folder adds to orphaned."""
    data = ParsedData()
    marker = ParsedFeature({
        "id": "marker-1",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"class": "Marker", "title": "Test"}
    })

    data.add_feature_to_folder("nonexistent", marker)
    assert len(data.orphaned_features) == 1


def test_parsed_data_get_folder_stats():
    """Test getting folder statistics."""
    data = ParsedData()
    data.add_folder("folder-1", "My Folder")

    marker = ParsedFeature({
        "id": "m1",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"class": "Marker", "title": "M1"}
    })
    line = ParsedFeature({
        "id": "l1",
        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        "properties": {"class": "Line", "title": "L1"}
    })

    data.add_feature_to_folder("folder-1", marker)
    data.add_feature_to_folder("folder-1", line)

    stats = data.get_folder_stats("folder-1")
    assert stats["waypoints"] == 1
    assert stats["tracks"] == 1
    assert stats["total"] == 2


def test_parsed_data_get_folder_stats_nonexistent():
    """Test getting stats for nonexistent folder returns zeros."""
    data = ParsedData()
    stats = data.get_folder_stats("nonexistent")

    assert stats["waypoints"] == 0
    assert stats["tracks"] == 0
    assert stats["shapes"] == 0
    assert stats["total"] == 0


def test_parsed_data_get_all_folders():
    """Test getting all folders."""
    data = ParsedData()
    data.add_folder("folder-1", "Folder One")
    data.add_folder("folder-2", "Folder Two")

    folders = data.get_all_folders()
    assert len(folders) == 2
    assert ("folder-1", "Folder One") in folders
    assert ("folder-2", "Folder Two") in folders
