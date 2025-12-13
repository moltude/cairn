"""Unit tests for cairn.core.parser module."""

import pytest
import json
import tempfile
from pathlib import Path
from cairn.core.parser import (
    ParsedFeature,
    ParsedData,
    parse_geojson,
    get_file_summary,
)


@pytest.fixture
def sample_marker_feature():
    """Sample CalTopo marker feature."""
    return {
        "id": "marker-1",
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [-114.5, 45.5]
        },
        "properties": {
            "class": "Marker",
            "title": "Test Waypoint",
            "description": "<b>Bold description</b>",
            "marker-color": "FF0000",
            "marker-symbol": "tent",
            "folderId": "folder-1"
        }
    }


@pytest.fixture
def sample_line_feature():
    """Sample CalTopo line/track feature."""
    return {
        "id": "line-1",
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[-114.5, 45.5], [-114.6, 45.6]]
        },
        "properties": {
            "class": "Line",
            "title": "Test Track",
            "stroke": "0000FF",
            "folderId": "folder-1"
        }
    }


@pytest.fixture
def sample_shape_feature():
    """Sample CalTopo shape/polygon feature."""
    return {
        "id": "shape-1",
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-114.5, 45.5], [-114.6, 45.5], [-114.6, 45.6], [-114.5, 45.5]]]
        },
        "properties": {
            "class": "Shape",
            "title": "Test Area",
            "stroke": "00FF00",
            "folderId": "folder-1"
        }
    }


@pytest.fixture
def sample_folder_feature():
    """Sample CalTopo folder feature."""
    return {
        "id": "folder-1",
        "type": "Feature",
        "geometry": None,
        "properties": {
            "class": "Folder",
            "title": "My Folder"
        }
    }


class TestParsedFeature:
    """Tests for ParsedFeature class."""

    def test_marker_detection(self, sample_marker_feature):
        """Markers correctly identified."""
        feature = ParsedFeature(sample_marker_feature)
        assert feature.is_marker() is True
        assert feature.is_line() is False
        assert feature.is_shape() is False
        assert feature.is_folder() is False

    def test_line_detection(self, sample_line_feature):
        """Lines/tracks correctly identified."""
        feature = ParsedFeature(sample_line_feature)
        assert feature.is_marker() is False
        assert feature.is_line() is True
        assert feature.is_shape() is False

    def test_shape_detection(self, sample_shape_feature):
        """Shapes/polygons correctly identified."""
        feature = ParsedFeature(sample_shape_feature)
        assert feature.is_marker() is False
        assert feature.is_line() is False
        assert feature.is_shape() is True

    def test_folder_detection(self, sample_folder_feature):
        """Folders correctly identified."""
        feature = ParsedFeature(sample_folder_feature)
        assert feature.is_folder() is True
        assert feature.is_marker() is False

    def test_title_extraction(self, sample_marker_feature):
        """Title extracted correctly."""
        feature = ParsedFeature(sample_marker_feature)
        assert feature.title == "Test Waypoint"

    def test_description_html_stripped(self, sample_marker_feature):
        """HTML stripped from description."""
        feature = ParsedFeature(sample_marker_feature)
        assert "<b>" not in feature.description
        assert "Bold description" in feature.description

    def test_symbol_extraction(self, sample_marker_feature):
        """Symbol extracted correctly."""
        feature = ParsedFeature(sample_marker_feature)
        assert feature.symbol == "tent"

    def test_color_extraction_marker(self, sample_marker_feature):
        """Color extracted from marker-color."""
        feature = ParsedFeature(sample_marker_feature)
        assert feature.color == "FF0000"

    def test_color_extraction_stroke(self, sample_line_feature):
        """Color extracted from stroke for lines."""
        feature = ParsedFeature(sample_line_feature)
        assert feature.color == "0000FF"

    def test_geometry_type(self, sample_marker_feature):
        """Geometry type accessible."""
        feature = ParsedFeature(sample_marker_feature)
        assert feature.geometry_type == "Point"

    def test_coordinates(self, sample_marker_feature):
        """Coordinates accessible."""
        feature = ParsedFeature(sample_marker_feature)
        assert feature.coordinates == [-114.5, 45.5]


class TestParsedData:
    """Tests for ParsedData class."""

    def test_add_folder(self):
        """Folders added correctly."""
        data = ParsedData()
        data.add_folder("folder-1", "Test Folder")
        assert "folder-1" in data.folders
        assert data.folders["folder-1"]["name"] == "Test Folder"

    def test_add_feature_to_folder(self, sample_marker_feature, sample_line_feature):
        """Features added to correct lists."""
        data = ParsedData()
        data.add_folder("folder-1", "Test Folder")

        marker = ParsedFeature(sample_marker_feature)
        data.add_feature_to_folder("folder-1", marker)
        assert len(data.folders["folder-1"]["waypoints"]) == 1

        line = ParsedFeature(sample_line_feature)
        data.add_feature_to_folder("folder-1", line)
        assert len(data.folders["folder-1"]["tracks"]) == 1

    def test_orphaned_features(self, sample_marker_feature):
        """Features without folder go to orphans."""
        data = ParsedData()
        marker = ParsedFeature(sample_marker_feature)
        data.add_feature_to_folder("nonexistent", marker)
        assert len(data.orphaned_features) == 1

    def test_folder_stats(self, sample_marker_feature, sample_line_feature, sample_shape_feature):
        """Folder stats calculated correctly."""
        data = ParsedData()
        data.add_folder("folder-1", "Test Folder")

        data.add_feature_to_folder("folder-1", ParsedFeature(sample_marker_feature))
        data.add_feature_to_folder("folder-1", ParsedFeature(sample_line_feature))
        data.add_feature_to_folder("folder-1", ParsedFeature(sample_shape_feature))

        stats = data.get_folder_stats("folder-1")
        assert stats["waypoints"] == 1
        assert stats["tracks"] == 1
        assert stats["shapes"] == 1
        assert stats["total"] == 3

    def test_nonexistent_folder_stats(self):
        """Stats for nonexistent folder return zeros."""
        data = ParsedData()
        stats = data.get_folder_stats("nonexistent")
        assert stats["total"] == 0


class TestParseGeojson:
    """Tests for parse_geojson function."""

    def test_file_not_found(self):
        """FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_geojson(Path("/nonexistent/file.json"))

    def test_empty_features(self):
        """ValueError for empty features list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"type": "FeatureCollection", "features": []}, f)
            f.flush()

            with pytest.raises(ValueError, match="No features found"):
                parse_geojson(Path(f.name))

    def test_parse_with_folder(
        self,
        sample_folder_feature,
        sample_marker_feature
    ):
        """Features organized under folder."""
        geojson = {
            "type": "FeatureCollection",
            "features": [sample_folder_feature, sample_marker_feature]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(geojson, f)
            f.flush()

            result = parse_geojson(Path(f.name))
            assert "folder-1" in result.folders
            assert len(result.folders["folder-1"]["waypoints"]) == 1

    def test_parse_without_folder(self, sample_marker_feature):
        """Default folder created when none exist."""
        geojson = {
            "type": "FeatureCollection",
            "features": [sample_marker_feature]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(geojson, f)
            f.flush()

            result = parse_geojson(Path(f.name))
            # Should have a default folder
            assert len(result.folders) == 1


class TestGetFileSummary:
    """Tests for get_file_summary function."""

    def test_summary_counts(
        self,
        sample_folder_feature,
        sample_marker_feature,
        sample_line_feature
    ):
        """Summary counts features correctly."""
        geojson = {
            "type": "FeatureCollection",
            "features": [
                sample_folder_feature,
                sample_marker_feature,
                sample_line_feature
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(geojson, f)
            f.flush()

            parsed = parse_geojson(Path(f.name))
            summary = get_file_summary(parsed)

            assert summary["folder_count"] == 1
            assert summary["total_waypoints"] == 1
            assert summary["total_tracks"] == 1
            assert summary["total_features"] == 2
