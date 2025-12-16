#!/usr/bin/env python3
"""Generate edge case test fixtures for QA validation.

This script creates a comprehensive set of edge case test files to ensure
Cairn handles unusual, extreme, or pathological inputs gracefully.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

# Determine fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "edge_cases"
FIXTURES_DIR.mkdir(exist_ok=True, parents=True)


def create_gpx_base(version: str = "1.1") -> ET.Element:
    """Create a base GPX element with proper namespace."""
    gpx = ET.Element(
        "gpx",
        xmlns="http://www.topografix.com/GPX/1/1",
        version=version,
        creator="Cairn Edge Case Generator"
    )
    return gpx


def write_gpx(gpx: ET.Element, filename: str) -> None:
    """Write GPX element to file with proper formatting."""
    tree = ET.ElementTree(gpx)
    ET.indent(tree, space="  ")
    filepath = FIXTURES_DIR / filename
    tree.write(filepath, encoding="utf-8", xml_declaration=True)
    print(f"✓ Generated: {filename}")


def write_json(data: dict, filename: str) -> None:
    """Write JSON data to file."""
    filepath = FIXTURES_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✓ Generated: {filename}")


# ==============================================================================
# Geographic Edge Cases
# ==============================================================================

def generate_poles_gpx():
    """Generate GPX with waypoints at North and South Poles."""
    gpx = create_gpx_base()

    # North Pole
    wpt = ET.SubElement(gpx, "wpt", lat="90.0", lon="0.0")
    ET.SubElement(wpt, "name").text = "North Pole"
    ET.SubElement(wpt, "desc").text = "True North - 90°N"
    ET.SubElement(wpt, "ele").text = "0"

    # South Pole
    wpt = ET.SubElement(gpx, "wpt", lat="-90.0", lon="0.0")
    ET.SubElement(wpt, "name").text = "South Pole"
    ET.SubElement(wpt, "desc").text = "True South - 90°S"
    ET.SubElement(wpt, "ele").text = "2835"  # Ice surface elevation

    write_gpx(gpx, "poles.gpx")


def generate_dateline_gpx():
    """Generate GPX with waypoints at International Date Line."""
    gpx = create_gpx_base()

    wpt = ET.SubElement(gpx, "wpt", lat="0.0", lon="180.0")
    ET.SubElement(wpt, "name").text = "Dateline East"
    ET.SubElement(wpt, "desc").text = "180°E"

    wpt = ET.SubElement(gpx, "wpt", lat="0.0", lon="-180.0")
    ET.SubElement(wpt, "name").text = "Dateline West"
    ET.SubElement(wpt, "desc").text = "180°W (same meridian)"

    write_gpx(gpx, "dateline.gpx")


def generate_prime_meridian_gpx():
    """Generate GPX with waypoint at Prime Meridian."""
    gpx = create_gpx_base()

    wpt = ET.SubElement(gpx, "wpt", lat="51.4778", lon="0.0")
    ET.SubElement(wpt, "name").text = "Greenwich Observatory"
    ET.SubElement(wpt, "desc").text = "Prime Meridian - 0°"

    write_gpx(gpx, "prime_meridian.gpx")


def generate_equator_gpx():
    """Generate GPX with waypoint at Equator."""
    gpx = create_gpx_base()

    wpt = ET.SubElement(gpx, "wpt", lat="0.0", lon="-78.4545")
    ET.SubElement(wpt, "name").text = "Equator Crossing"
    ET.SubElement(wpt, "desc").text = "Latitude 0° in Ecuador"

    write_gpx(gpx, "equator.gpx")


# ==============================================================================
# Elevation Edge Cases
# ==============================================================================

def generate_elevations_gpx():
    """Generate GPX with extreme elevation values."""
    gpx = create_gpx_base()

    # Sea level
    wpt = ET.SubElement(gpx, "wpt", lat="0.0", lon="0.0")
    ET.SubElement(wpt, "name").text = "Sea Level"
    ET.SubElement(wpt, "ele").text = "0.0"

    # Below sea level (Dead Sea)
    wpt = ET.SubElement(gpx, "wpt", lat="31.5", lon="35.5")
    ET.SubElement(wpt, "name").text = "Dead Sea Shore"
    ET.SubElement(wpt, "ele").text = "-430"

    # Mount Everest
    wpt = ET.SubElement(gpx, "wpt", lat="27.9881", lon="86.9250")
    ET.SubElement(wpt, "name").text = "Mount Everest Summit"
    ET.SubElement(wpt, "ele").text = "8849"

    # Missing elevation
    wpt = ET.SubElement(gpx, "wpt", lat="45.0", lon="-120.0")
    ET.SubElement(wpt, "name").text = "No Elevation Data"
    # Intentionally no <ele> tag

    write_gpx(gpx, "elevations.gpx")


# ==============================================================================
# Text/Unicode Edge Cases
# ==============================================================================

def generate_unicode_gpx():
    """Generate GPX with Unicode characters and emoji."""
    gpx = create_gpx_base()

    # Emoji
    wpt = ET.SubElement(gpx, "wpt", lat="45.0", lon="-120.0")
    ET.SubElement(wpt, "name").text = "Camp 🏕️"
    ET.SubElement(wpt, "desc").text = "Great camping spot with views! 🌲⛰️"

    # Various languages
    wpt = ET.SubElement(gpx, "wpt", lat="45.1", lon="-120.1")
    ET.SubElement(wpt, "name").text = "Montaña del Oso"
    ET.SubElement(wpt, "desc").text = "Café au sommet ☕"

    # Chinese
    wpt = ET.SubElement(gpx, "wpt", lat="45.2", lon="-120.2")
    ET.SubElement(wpt, "name").text = "登山口"
    ET.SubElement(wpt, "desc").text = "Trailhead in Japanese/Chinese"

    # Cyrillic
    wpt = ET.SubElement(gpx, "wpt", lat="45.3", lon="-120.3")
    ET.SubElement(wpt, "name").text = "Вершина"
    ET.SubElement(wpt, "desc").text = "Peak in Russian"

    # Arabic (RTL)
    wpt = ET.SubElement(gpx, "wpt", lat="45.4", lon="-120.4")
    ET.SubElement(wpt, "name").text = "قمة الجبل"
    ET.SubElement(wpt, "desc").text = "Mountain peak in Arabic"

    write_gpx(gpx, "unicode.gpx")


def generate_xml_chars_gpx():
    """Generate GPX with XML special characters."""
    gpx = create_gpx_base()

    wpt = ET.SubElement(gpx, "wpt", lat="45.0", lon="-120.0")
    # ElementTree will automatically escape these
    ET.SubElement(wpt, "name").text = '<Trail> & "Path"'
    ET.SubElement(wpt, "desc").text = 'Use > or < signs, plus "quotes" & ampersands'

    write_gpx(gpx, "xml_chars.gpx")


def generate_quotes_gpx():
    """Generate GPX with various quote types."""
    gpx = create_gpx_base()

    wpt = ET.SubElement(gpx, "wpt", lat="45.0", lon="-120.0")
    ET.SubElement(wpt, "name").text = 'He said "hello"'
    ET.SubElement(wpt, "desc").text = "It's a trail with 'single' and \"double\" quotes"

    write_gpx(gpx, "quotes.gpx")


def generate_long_name_gpx():
    """Generate GPX with very long name (1000+ characters)."""
    gpx = create_gpx_base()

    wpt = ET.SubElement(gpx, "wpt", lat="45.0", lon="-120.0")
    long_name = "Very Long Name " + "X" * 1000 + " End"
    ET.SubElement(wpt, "name").text = long_name
    ET.SubElement(wpt, "desc").text = "Testing maximum name length handling"

    write_gpx(gpx, "long_name.gpx")


def generate_empty_name_gpx():
    """Generate GPX with empty/missing names."""
    gpx = create_gpx_base()

    # Waypoint with empty name
    wpt = ET.SubElement(gpx, "wpt", lat="45.0", lon="-120.0")
    ET.SubElement(wpt, "name").text = ""

    # Waypoint with no name tag at all
    wpt = ET.SubElement(gpx, "wpt", lat="45.1", lon="-120.1")
    ET.SubElement(wpt, "desc").text = "No name tag"

    # Waypoint with only whitespace
    wpt = ET.SubElement(gpx, "wpt", lat="45.2", lon="-120.2")
    ET.SubElement(wpt, "name").text = "   "

    write_gpx(gpx, "empty_names.gpx")


# ==============================================================================
# Size Edge Cases
# ==============================================================================

def generate_empty_gpx():
    """Generate valid but empty GPX file."""
    gpx = create_gpx_base()
    # No waypoints, tracks, or routes
    write_gpx(gpx, "empty.gpx")


def generate_single_waypoint_gpx():
    """Generate GPX with exactly one waypoint."""
    gpx = create_gpx_base()

    wpt = ET.SubElement(gpx, "wpt", lat="45.0", lon="-120.0")
    ET.SubElement(wpt, "name").text = "Solo Waypoint"

    write_gpx(gpx, "single_waypoint.gpx")


def generate_many_waypoints_gpx(count: int = 1000):
    """Generate GPX with many waypoints for stress testing."""
    gpx = create_gpx_base()

    for i in range(count):
        lat = 45.0 + (i % 100) * 0.01  # Spread across ~1 degree
        lon = -120.0 + (i // 100) * 0.01

        wpt = ET.SubElement(gpx, "wpt", lat=str(lat), lon=str(lon))
        ET.SubElement(wpt, "name").text = f"Waypoint {i+1:04d}"
        ET.SubElement(wpt, "ele").text = str(1000 + i)

    filename = f"many_waypoints_{count}.gpx"
    write_gpx(gpx, filename)


# ==============================================================================
# Track Edge Cases
# ==============================================================================

def generate_single_point_track_gpx():
    """Generate GPX with track containing only one point."""
    gpx = create_gpx_base()

    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = "Single Point Track"
    trkseg = ET.SubElement(trk, "trkseg")

    trkpt = ET.SubElement(trkseg, "trkpt", lat="45.0", lon="-120.0")
    ET.SubElement(trkpt, "ele").text = "1000"

    write_gpx(gpx, "single_point_track.gpx")


def generate_long_track_gpx(points: int = 10000):
    """Generate GPX with very long track."""
    gpx = create_gpx_base()

    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = f"Long Track ({points} points)"
    trkseg = ET.SubElement(trk, "trkseg")

    for i in range(points):
        lat = 45.0 + (i * 0.0001)  # Move north gradually
        lon = -120.0 + ((i % 100) * 0.0001)  # Zigzag east-west

        trkpt = ET.SubElement(trkseg, "trkpt", lat=str(lat), lon=str(lon))
        ET.SubElement(trkpt, "ele").text = str(1000 + i * 0.5)

    filename = f"long_track_{points}.gpx"
    write_gpx(gpx, filename)


# ==============================================================================
# Color Edge Cases
# ==============================================================================

def generate_colors_gpx():
    """Generate GPX with various color specifications."""
    gpx = create_gpx_base()

    # OnX namespace for extensions
    ns_prefix = "onx"
    ns_uri = "http://www.onxmaps.com/gpx/1/0"
    ET.register_namespace(ns_prefix, ns_uri)

    colors = [
        ("White Waypoint", "White"),
        ("Black Waypoint", "Black"),
        ("Red Waypoint", "Red"),
        ("No Color", None),
    ]

    for i, (name, color) in enumerate(colors):
        wpt = ET.SubElement(gpx, "wpt", lat=str(45.0 + i * 0.1), lon="-120.0")
        ET.SubElement(wpt, "name").text = name

        if color:
            ext = ET.SubElement(wpt, "extensions")
            onx_ext = ET.SubElement(ext, f"{{{ns_uri}}}onx_waypoint_ext")
            color_elem = ET.SubElement(onx_ext, f"{{{ns_uri}}}color")
            color_elem.text = color

    write_gpx(gpx, "colors.gpx")


# ==============================================================================
# Duplicate Edge Cases
# ==============================================================================

def generate_duplicates_gpx():
    """Generate GPX with duplicate waypoints."""
    gpx = create_gpx_base()

    # Create same waypoint 5 times
    for i in range(5):
        wpt = ET.SubElement(gpx, "wpt", lat="45.0", lon="-120.0")
        ET.SubElement(wpt, "name").text = "Duplicate Camp"
        ET.SubElement(wpt, "ele").text = "1500"

    # Different waypoints with same name
    for i in range(3):
        wpt = ET.SubElement(gpx, "wpt", lat=str(45.0 + i * 0.1), lon="-120.0")
        ET.SubElement(wpt, "name").text = "Water Source"

    write_gpx(gpx, "duplicates.gpx")


# ==============================================================================
# CalTopo GeoJSON Edge Cases
# ==============================================================================

def generate_empty_geojson():
    """Generate empty CalTopo GeoJSON."""
    data = {
        "type": "FeatureCollection",
        "features": []
    }
    write_json(data, "empty.json")


def generate_single_marker_geojson():
    """Generate GeoJSON with single marker."""
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-120.0, 45.0]
                },
                "properties": {
                    "title": "Solo Marker",
                    "class": "Marker",
                    "marker-symbol": "circle",
                    "marker-color": "#FF0000"
                }
            }
        ]
    }
    write_json(data, "single_marker.json")


def generate_mixed_geojson():
    """Generate GeoJSON with all feature types."""
    data = {
        "type": "FeatureCollection",
        "features": [
            # Marker
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-120.0, 45.0]
                },
                "properties": {
                    "title": "Test Waypoint",
                    "class": "Marker",
                    "marker-symbol": "circle"
                }
            },
            # Line
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-120.0, 45.0],
                        [-120.1, 45.1],
                        [-120.2, 45.2]
                    ]
                },
                "properties": {
                    "title": "Test Track",
                    "class": "Shape",
                    "stroke": "#0000FF",
                    "stroke-width": 3
                }
            },
            # Polygon
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-120.0, 45.0],
                        [-120.1, 45.0],
                        [-120.1, 45.1],
                        [-120.0, 45.1],
                        [-120.0, 45.0]
                    ]]
                },
                "properties": {
                    "title": "Test Area",
                    "class": "Shape",
                    "stroke": "#00FF00",
                    "fill": "#00FF00",
                    "fill-opacity": 0.3
                }
            }
        ]
    }
    write_json(data, "mixed_features.json")


# ==============================================================================
# Malformed Files
# ==============================================================================

def generate_malformed_xml():
    """Generate intentionally malformed XML."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
    <wpt lat="45.0" lon="-120.0">
        <name>Unclosed Tag
    </wpt>
    <!-- Missing closing </gpx> tag -->
"""
    filepath = FIXTURES_DIR / "malformed.gpx"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Generated: malformed.gpx")


def generate_malformed_json():
    """Generate intentionally malformed JSON."""
    content = """{
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature"
            "geometry": {
                "type": "Point"
            }
        }
    ]
    # Missing closing brace
"""
    filepath = FIXTURES_DIR / "malformed.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Generated: malformed.json")


# ==============================================================================
# Main Execution
# ==============================================================================

def main():
    """Generate all edge case fixtures."""
    print(f"Generating edge case fixtures in: {FIXTURES_DIR}\n")

    print("Geographic Edge Cases:")
    print("-" * 50)
    generate_poles_gpx()
    generate_dateline_gpx()
    generate_prime_meridian_gpx()
    generate_equator_gpx()

    print("\nElevation Edge Cases:")
    print("-" * 50)
    generate_elevations_gpx()

    print("\nText/Unicode Edge Cases:")
    print("-" * 50)
    generate_unicode_gpx()
    generate_xml_chars_gpx()
    generate_quotes_gpx()
    generate_long_name_gpx()
    generate_empty_name_gpx()

    print("\nSize Edge Cases:")
    print("-" * 50)
    generate_empty_gpx()
    generate_single_waypoint_gpx()
    generate_many_waypoints_gpx(1000)
    generate_many_waypoints_gpx(10000)

    print("\nTrack Edge Cases:")
    print("-" * 50)
    generate_single_point_track_gpx()
    generate_long_track_gpx(1000)
    generate_long_track_gpx(10000)

    print("\nColor Edge Cases:")
    print("-" * 50)
    generate_colors_gpx()

    print("\nDuplicate Edge Cases:")
    print("-" * 50)
    generate_duplicates_gpx()

    print("\nGeoJSON Edge Cases:")
    print("-" * 50)
    generate_empty_geojson()
    generate_single_marker_geojson()
    generate_mixed_geojson()

    print("\nMalformed Files:")
    print("-" * 50)
    generate_malformed_xml()
    generate_malformed_json()

    print(f"\n{'='*50}")
    print(f"✓ All fixtures generated successfully!")
    print(f"Location: {FIXTURES_DIR}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
