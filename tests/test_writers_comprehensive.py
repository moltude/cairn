"""Comprehensive tests for cairn/core/writers.py to improve coverage."""

from pathlib import Path
from unittest.mock import patch
import logging
import xml.etree.ElementTree as ET

import pytest

from cairn.core.parser import ParsedFeature
from cairn.core.writers import (
    get_name_changes,
    clear_name_changes,
    track_name_change,
    verify_gpx_waypoint_order,
    log_waypoint_order,
    format_waypoint_name,
    prettify_xml,
    _utf8_joined_size,
    _split_gpx_lines_by_bytes,
    _write_gpx_parts,
    write_gpx_waypoints_maybe_split,
    write_gpx_tracks_maybe_split,
    write_kml_shapes,
    verify_sanitization_preserves_sort_order,
)
from cairn.core.config import load_config


# ===== Name Change Tracking Tests =====


def test_get_name_changes_returns_copy():
    """Test that get_name_changes returns a copy, not a reference."""
    clear_name_changes()
    track_name_change("waypoints", "Test/Name", "Test_Name")
    changes1 = get_name_changes()
    changes2 = get_name_changes()
    assert changes1 is not changes2
    assert changes1 == changes2


def test_track_name_change_only_tracks_when_different():
    """Test that identical names are not tracked as changes."""
    clear_name_changes()
    track_name_change("waypoints", "Same Name", "Same Name")
    changes = get_name_changes()
    assert len(changes["waypoints"]) == 0


def test_track_name_change_tracks_waypoints_and_tracks_separately():
    """Test that waypoint and track changes are tracked separately."""
    clear_name_changes()
    track_name_change("waypoints", "WP/Name", "WP_Name")
    track_name_change("tracks", "Track/Name", "Track_Name")
    changes = get_name_changes()
    assert len(changes["waypoints"]) == 1
    assert len(changes["tracks"]) == 1
    assert ("WP/Name", "WP_Name") in changes["waypoints"]
    assert ("Track/Name", "Track_Name") in changes["tracks"]


def test_clear_name_changes_resets_both_types():
    """Test that clear_name_changes resets both waypoints and tracks."""
    track_name_change("waypoints", "A", "B")
    track_name_change("tracks", "C", "D")
    clear_name_changes()
    changes = get_name_changes()
    assert len(changes["waypoints"]) == 0
    assert len(changes["tracks"]) == 0


# ===== GPX Waypoint Order Verification Tests =====


def test_verify_gpx_waypoint_order_basic(tmp_path):
    """Test basic waypoint order verification from GPX file."""
    gpx_path = tmp_path / "test.gpx"
    gpx_content = """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <wpt lat="45.0" lon="-114.0">
    <name>First</name>
  </wpt>
  <wpt lat="45.1" lon="-114.1">
    <name>Second</name>
  </wpt>
  <wpt lat="45.2" lon="-114.2">
    <name>Third</name>
  </wpt>
</gpx>"""
    gpx_path.write_text(gpx_content, encoding="utf-8")

    order = verify_gpx_waypoint_order(gpx_path)
    assert order == ["First", "Second", "Third"]


def test_verify_gpx_waypoint_order_max_items(tmp_path):
    """Test that max_items parameter limits returned waypoints."""
    gpx_path = tmp_path / "test.gpx"
    gpx_content = """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <wpt lat="45.0" lon="-114.0"><name>WP1</name></wpt>
  <wpt lat="45.1" lon="-114.1"><name>WP2</name></wpt>
  <wpt lat="45.2" lon="-114.2"><name>WP3</name></wpt>
  <wpt lat="45.3" lon="-114.3"><name>WP4</name></wpt>
</gpx>"""
    gpx_path.write_text(gpx_content, encoding="utf-8")

    order = verify_gpx_waypoint_order(gpx_path, max_items=2)
    assert len(order) == 2
    assert order == ["WP1", "WP2"]


def test_verify_gpx_waypoint_order_invalid_file(tmp_path):
    """Test that verify_gpx_waypoint_order handles invalid files gracefully."""
    gpx_path = tmp_path / "invalid.gpx"
    gpx_path.write_text("not valid xml", encoding="utf-8")

    order = verify_gpx_waypoint_order(gpx_path)
    assert order == []


def test_verify_gpx_waypoint_order_nonexistent_file(tmp_path):
    """Test that verify_gpx_waypoint_order handles missing files gracefully."""
    gpx_path = tmp_path / "nonexistent.gpx"

    order = verify_gpx_waypoint_order(gpx_path)
    assert order == []


# ===== Log Waypoint Order Tests =====


def test_log_waypoint_order_with_debug_enabled(caplog):
    """Test that log_waypoint_order logs when debug is enabled."""
    features = [
        ParsedFeature({"properties": {"title": f"WP{i}"}, "geometry": {"coordinates": [0, 0]}})
        for i in range(3)
    ]

    with caplog.at_level(logging.DEBUG):
        log_waypoint_order(features, label="Test Order", max_items=10)

    assert "Test Order" in caplog.text
    assert "WP0" in caplog.text
    assert "WP1" in caplog.text
    assert "WP2" in caplog.text


def test_log_waypoint_order_truncates_long_lists(caplog):
    """Test that log_waypoint_order truncates long lists."""
    features = [
        ParsedFeature({"properties": {"title": f"WP{i}"}, "geometry": {"coordinates": [0, 0]}})
        for i in range(25)
    ]

    with caplog.at_level(logging.DEBUG):
        log_waypoint_order(features, label="Long List", max_items=3)

    assert "Long List" in caplog.text
    assert "and 22 more waypoints" in caplog.text


def test_log_waypoint_order_skips_when_debug_disabled(caplog):
    """Test that log_waypoint_order skips logging when debug is disabled."""
    features = [
        ParsedFeature({"properties": {"title": "WP1"}, "geometry": {"coordinates": [0, 0]}})
    ]

    with caplog.at_level(logging.INFO):  # Not DEBUG
        log_waypoint_order(features, label="Test")

    # Should not log anything at INFO level
    assert "Test" not in caplog.text


# ===== Format Waypoint Name Tests =====


def test_format_waypoint_name_with_prefix():
    """Test format_waypoint_name adds icon prefix when enabled."""
    clear_name_changes()
    result = format_waypoint_name("My Campsite", "Camp", use_prefix=True)
    assert result == "Camp - My Campsite"


def test_format_waypoint_name_without_prefix():
    """Test format_waypoint_name omits prefix when disabled."""
    clear_name_changes()
    result = format_waypoint_name("My Campsite", "Camp", use_prefix=False)
    assert result == "My Campsite"


def test_format_waypoint_name_no_prefix_for_default_icon():
    """Test that default icon doesn't get prefix even when enabled."""
    clear_name_changes()
    result = format_waypoint_name("My Point", "Location", use_prefix=True, default_icon="Location")
    assert result == "My Point"


def test_format_waypoint_name_sanitizes_special_chars():
    """Test that format_waypoint_name sanitizes special characters."""
    clear_name_changes()
    result = format_waypoint_name("Name@With#Special$Chars", "Camp", use_prefix=False)
    # Should remove @, #, $ characters per sanitize_name_for_onx
    assert "@" not in result
    assert "#" not in result
    assert "$" not in result


def test_format_waypoint_name_tracks_changes():
    """Test that format_waypoint_name tracks sanitization changes."""
    clear_name_changes()
    format_waypoint_name("Bad@Name", "Camp", use_prefix=False)
    changes = get_name_changes()
    assert len(changes["waypoints"]) > 0


# ===== XML Prettify Tests =====


def test_prettify_xml_basic():
    """Test that prettify_xml formats XML correctly."""
    elem = ET.Element("root")
    child = ET.SubElement(elem, "child")
    child.text = "value"

    result = prettify_xml(elem)
    assert '<?xml version="1.0" ?>' in result
    assert "<root>" in result
    assert "<child>value</child>" in result
    assert result.count("\n") > 1  # Should be multi-line


# ===== UTF-8 Size Calculation Tests =====


def test_utf8_joined_size_empty():
    """Test _utf8_joined_size with empty list."""
    assert _utf8_joined_size([]) == 0


def test_utf8_joined_size_single_line():
    """Test _utf8_joined_size with single line."""
    size = _utf8_joined_size(["hello"])
    assert size == 5  # "hello" is 5 bytes


def test_utf8_joined_size_multiple_lines():
    """Test _utf8_joined_size with multiple lines."""
    size = _utf8_joined_size(["hello", "world"])
    # "hello" (5) + newline (1) + "world" (5) = 11, but no trailing newline
    # Actually: 5 + 5 = 10 bytes + 1 newline = 11
    assert size == 11


def test_utf8_joined_size_unicode():
    """Test _utf8_joined_size with unicode characters."""
    size = _utf8_joined_size(["Montaña"])  # ñ is 2 bytes in UTF-8
    assert size == 8  # M(1) o(1) n(1) t(1) a(1) ñ(2) a(1) = 8


# ===== GPX Splitting Tests =====


def test_split_gpx_lines_by_bytes_no_split_needed():
    """Test that small content doesn't get split."""
    header = ["<gpx>"]
    items = [["  <wpt>WP1</wpt>"], ["  <wpt>WP2</wpt>"]]
    footer = "</gpx>"

    parts = _split_gpx_lines_by_bytes(
        header_lines=header,
        item_blocks=items,
        footer_line=footer,
        max_bytes=1000
    )

    assert len(parts) == 1


def test_split_gpx_lines_by_bytes_forces_split():
    """Test that large content gets split into multiple parts."""
    header = ["<gpx>"]
    # Create large items that will force splitting
    items = [["  <wpt>" + "x" * 100 + "</wpt>"] for _ in range(10)]
    footer = "</gpx>"

    parts = _split_gpx_lines_by_bytes(
        header_lines=header,
        item_blocks=items,
        footer_line=footer,
        max_bytes=200  # Small limit to force split
    )

    assert len(parts) > 1


def test_split_gpx_lines_by_bytes_empty_items():
    """Test splitting with no items creates one part."""
    header = ["<gpx>"]
    items = []
    footer = "</gpx>"

    parts = _split_gpx_lines_by_bytes(
        header_lines=header,
        item_blocks=items,
        footer_line=footer,
        max_bytes=1000
    )

    assert len(parts) == 1
    assert header[0] in parts[0]
    assert footer in parts[0]


def test_split_gpx_lines_by_bytes_single_item_exceeds_max(caplog):
    """Test that single oversized item generates warning but is still written."""
    header = ["<gpx>"]
    items = [["  <wpt>" + "x" * 1000 + "</wpt>"]]  # Single large item
    footer = "</gpx>"

    with caplog.at_level(logging.WARNING):
        parts = _split_gpx_lines_by_bytes(
            header_lines=header,
            item_blocks=items,
            footer_line=footer,
            max_bytes=100  # Too small for even one item
        )

    assert len(parts) == 1  # Still writes it
    assert "single GPX item exceeds max_bytes" in caplog.text


# ===== Write GPX Parts Tests =====


def test_write_gpx_parts_single_file(tmp_path):
    """Test writing a single GPX part."""
    parts = [["<gpx>", "  <wpt/>", "</gpx>"]]
    output_path = tmp_path / "output.gpx"

    written = _write_gpx_parts(parts=parts, output_path=output_path)

    assert len(written) == 1
    assert written[0][0] == output_path
    assert output_path.exists()


def test_write_gpx_parts_multiple_files(tmp_path):
    """Test writing multiple GPX parts creates numbered files."""
    parts = [
        ["<gpx>", "  <wpt>Part1</wpt>", "</gpx>"],
        ["<gpx>", "  <wpt>Part2</wpt>", "</gpx>"],
    ]
    output_path = tmp_path / "output.gpx"

    written = _write_gpx_parts(parts=parts, output_path=output_path)

    assert len(written) == 2
    assert (tmp_path / "output_1.gpx").exists()
    assert (tmp_path / "output_2.gpx").exists()


# ===== Write GPX Waypoints Maybe Split Tests =====


def test_write_gpx_waypoints_maybe_split_no_split(tmp_path):
    """Test writing waypoints without splitting."""
    features = [
        ParsedFeature({
            "properties": {"title": "WP1", "marker-symbol": "point"},
            "geometry": {"coordinates": [-114.0, 45.0]}
        })
    ]
    output_path = tmp_path / "waypoints.gpx"

    result = write_gpx_waypoints_maybe_split(
        features, output_path, "Test Folder", sort=False, split=False
    )

    assert len(result) == 1
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "WP1" in content


def test_write_gpx_waypoints_maybe_split_with_sorting(tmp_path):
    """Test that sorting is applied when enabled."""
    features = [
        ParsedFeature({
            "properties": {"title": "Zebra"},
            "geometry": {"coordinates": [-114.0, 45.0]}
        }),
        ParsedFeature({
            "properties": {"title": "Alpha"},
            "geometry": {"coordinates": [-114.1, 45.1]}
        }),
    ]
    output_path = tmp_path / "waypoints.gpx"

    write_gpx_waypoints_maybe_split(
        features, output_path, "Test", sort=True, split=False
    )

    order = verify_gpx_waypoint_order(output_path)
    assert order == ["Alpha", "Zebra"]


def test_write_gpx_waypoints_maybe_split_skips_invalid_coordinates(tmp_path):
    """Test that features with invalid coordinates are skipped."""
    features = [
        ParsedFeature({
            "properties": {"title": "Valid"},
            "geometry": {"coordinates": [-114.0, 45.0]}
        }),
        ParsedFeature({
            "properties": {"title": "Invalid"},
            "geometry": {"coordinates": [-114.0]}  # Only one coordinate
        }),
    ]
    output_path = tmp_path / "waypoints.gpx"

    result = write_gpx_waypoints_maybe_split(
        features, output_path, "Test", sort=False, split=False
    )

    assert result[0][2] == 1  # Only 1 waypoint written
    content = output_path.read_text(encoding="utf-8")
    assert "Valid" in content
    assert "Invalid" not in content


def test_write_gpx_waypoints_maybe_split_respects_icon_override(tmp_path):
    """Test that per-feature icon override is respected."""
    features = [
        ParsedFeature({
            "properties": {
                "title": "Special",
                "marker-symbol": "point",
                "cairn_onx_icon_override": "Summit"
            },
            "geometry": {"coordinates": [-114.0, 45.0]}
        })
    ]
    output_path = tmp_path / "waypoints.gpx"

    write_gpx_waypoints_maybe_split(
        features, output_path, "Test", sort=False, split=False
    )

    content = output_path.read_text(encoding="utf-8")
    assert "<onx:icon>Summit</onx:icon>" in content


# ===== Write GPX Tracks Maybe Split Tests =====


def test_write_gpx_tracks_maybe_split_basic(tmp_path):
    """Test basic track writing without splitting."""
    features = [
        ParsedFeature({
            "properties": {"title": "Trail 1", "stroke": "#FF0000"},
            "geometry": {
                "type": "LineString",
                "coordinates": [[-114.0, 45.0], [-114.1, 45.1]]
            }
        })
    ]
    output_path = tmp_path / "tracks.gpx"

    result = write_gpx_tracks_maybe_split(
        features, output_path, "Test Tracks", sort=False, split=False
    )

    assert len(result) == 1
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Trail 1" in content
    assert "<trk>" in content


def test_write_gpx_tracks_maybe_split_skips_empty_coordinates(tmp_path):
    """Test that tracks with no coordinates are skipped."""
    features = [
        ParsedFeature({
            "properties": {"title": "Valid Track"},
            "geometry": {
                "type": "LineString",
                "coordinates": [[-114.0, 45.0], [-114.1, 45.1]]
            }
        }),
        ParsedFeature({
            "properties": {"title": "Empty Track"},
            "geometry": {
                "type": "LineString",
                "coordinates": []
            }
        }),
    ]
    output_path = tmp_path / "tracks.gpx"

    result = write_gpx_tracks_maybe_split(
        features, output_path, "Test", sort=False, split=False
    )

    assert result[0][2] == 1  # Only 1 track written
    content = output_path.read_text(encoding="utf-8")
    assert "Valid Track" in content
    assert "Empty Track" not in content


# ===== Write KML Shapes Tests =====


def test_write_kml_shapes_basic(tmp_path):
    """Test basic KML shape writing."""
    features = [
        ParsedFeature({
            "properties": {"title": "Area 1", "stroke": "#FF0000"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-114.0, 45.0],
                    [-114.1, 45.0],
                    [-114.1, 45.1],
                    [-114.0, 45.1],
                    [-114.0, 45.0]
                ]]
            }
        })
    ]
    output_path = tmp_path / "shapes.kml"

    size = write_kml_shapes(features, output_path, "Test Shapes")

    assert size > 0
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Area 1" in content
    assert "<Polygon>" in content
    assert "<coordinates>" in content


def test_write_kml_shapes_with_description(tmp_path):
    """Test KML writing includes descriptions."""
    features = [
        ParsedFeature({
            "properties": {
                "title": "Area",
                "description": "Test description"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-114.0, 45.0], [-114.1, 45.0], [-114.0, 45.0]]]
            }
        })
    ]
    output_path = tmp_path / "shapes.kml"

    write_kml_shapes(features, output_path, "Test")

    content = output_path.read_text(encoding="utf-8")
    assert "<description>" in content
    assert "Test description" in content


def test_write_kml_shapes_skips_empty_coordinates(tmp_path):
    """Test that shapes without coordinates are skipped."""
    features = [
        ParsedFeature({
            "properties": {"title": "Valid"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-114.0, 45.0], [-114.1, 45.0], [-114.0, 45.0]]]
            }
        }),
        ParsedFeature({
            "properties": {"title": "Invalid"},
            "geometry": {
                "type": "Polygon",
                "coordinates": []
            }
        }),
    ]
    output_path = tmp_path / "shapes.kml"

    write_kml_shapes(features, output_path, "Test")

    content = output_path.read_text(encoding="utf-8")
    assert "Valid" in content
    assert "Invalid" not in content


def test_write_kml_shapes_handles_nested_coordinates(tmp_path):
    """Test KML writing handles nested coordinate arrays."""
    features = [
        ParsedFeature({
            "properties": {"title": "Nested"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[[-114.0, 45.0], [-114.1, 45.0], [-114.0, 45.0]]]]
            }
        })
    ]
    output_path = tmp_path / "shapes.kml"

    write_kml_shapes(features, output_path, "Test")

    content = output_path.read_text(encoding="utf-8")
    # Check that coordinates are present in some form
    assert "Nested" in content
    assert "<coordinates>" in content


def test_write_kml_shapes_includes_elevation(tmp_path):
    """Test that KML includes elevation when available."""
    features = [
        ParsedFeature({
            "properties": {"title": "With Elevation"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-114.0, 45.0, 1000], [-114.1, 45.0, 1000], [-114.0, 45.0, 1000]]
                ]
            }
        })
    ]
    output_path = tmp_path / "shapes.kml"

    write_kml_shapes(features, output_path, "Test")

    content = output_path.read_text(encoding="utf-8")
    assert "1000" in content


# ===== Verify Sanitization Tests =====


def test_verify_sanitization_preserves_sort_order_same_order():
    """Test that verify_sanitization detects preserved order."""
    original_names = ["Alpha", "Bravo", "Charlie"]
    sanitized_names = ["Alpha", "Bravo", "Charlie"]

    result = verify_sanitization_preserves_sort_order(original_names, sanitized_names)
    assert result is True


def test_verify_sanitization_preserves_sort_order_different_order():
    """Test that verify_sanitization detects changed order."""
    original_names = ["Alpha", "Bravo", "Charlie"]
    sanitized_names = ["Bravo", "Alpha", "Charlie"]

    result = verify_sanitization_preserves_sort_order(original_names, sanitized_names)
    assert result is False


def test_verify_sanitization_preserves_sort_order_empty_lists():
    """Test that empty lists are handled correctly."""
    result = verify_sanitization_preserves_sort_order([], [])
    assert result is True


def test_verify_sanitization_preserves_sort_order_different_lengths():
    """Test that lists of different lengths are detected as different."""
    original_names = ["Alpha", "Bravo"]
    sanitized_names = ["Alpha"]

    result = verify_sanitization_preserves_sort_order(original_names, sanitized_names)
    assert result is False
