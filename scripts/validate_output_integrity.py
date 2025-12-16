#!/usr/bin/env python3
"""Validate converted files maintain data integrity.

This script validates that output files from Cairn conversions:
- Have valid structure (proper GeoJSON/GPX/KML format)
- Contain expected data fields
- Have valid coordinate ranges
- Preserve feature counts
- Don't have structural errors
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional


class ValidationError:
    """Represents a validation error."""

    def __init__(self, level: str, message: str, context: Optional[str] = None):
        self.level = level  # 'error', 'warning', 'info'
        self.message = message
        self.context = context

    def __str__(self):
        prefix = {
            'error': '❌ ERROR',
            'warning': '⚠️  WARNING',
            'info': 'ℹ️  INFO'
        }.get(self.level, '•')

        result = f"{prefix}: {self.message}"
        if self.context:
            result += f"\n  Context: {self.context}"
        return result


class ValidationResult:
    """Results from validation."""

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.stats: Dict[str, Any] = {}

    def add_error(self, level: str, message: str, context: Optional[str] = None):
        """Add a validation error."""
        self.errors.append(ValidationError(level, message, context))

    def has_errors(self) -> bool:
        """Check if there are any errors (not warnings)."""
        return any(e.level == 'error' for e in self.errors)

    def print_report(self):
        """Print validation report."""
        print("\n" + "="*70)
        print("VALIDATION REPORT")
        print("="*70)

        if self.stats:
            print("\nStatistics:")
            print("-"*70)
            for key, value in self.stats.items():
                print(f"  {key}: {value}")

        if self.errors:
            print("\nValidation Issues:")
            print("-"*70)
            for error in self.errors:
                print(f"{error}\n")
        else:
            print("\n✅ No validation issues found!")

        print("="*70)

        # Summary
        error_count = sum(1 for e in self.errors if e.level == 'error')
        warning_count = sum(1 for e in self.errors if e.level == 'warning')

        if error_count > 0:
            print(f"\n❌ FAILED: {error_count} error(s), {warning_count} warning(s)")
            return False
        elif warning_count > 0:
            print(f"\n⚠️  PASSED with warnings: {warning_count} warning(s)")
            return True
        else:
            print("\n✅ PASSED: All validation checks passed!")
            return True


def validate_geojson(path: Path) -> ValidationResult:
    """Validate GeoJSON structure and return results."""
    result = ValidationResult()

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error('error', f"Invalid JSON: {e}")
        return result
    except Exception as e:
        result.add_error('error', f"Failed to read file: {e}")
        return result

    # Validate top-level structure
    if not isinstance(data, dict):
        result.add_error('error', "GeoJSON must be a JSON object")
        return result

    if data.get("type") != "FeatureCollection":
        result.add_error('error',
                        f"Expected type 'FeatureCollection', got '{data.get('type')}'")

    if "features" not in data:
        result.add_error('error', "Missing 'features' array")
        return result

    if not isinstance(data["features"], list):
        result.add_error('error', "'features' must be an array")
        return result

    # Initialize stats
    stats = {
        "total_features": len(data["features"]),
        "markers": 0,
        "lines": 0,
        "shapes": 0,
        "folders": 0,
        "features_without_geometry": 0,
        "features_without_properties": 0
    }

    # Validate each feature
    for i, feat in enumerate(data["features"]):
        feat_id = f"Feature #{i+1}"

        if not isinstance(feat, dict):
            result.add_error('error', f"Feature {i+1} is not an object")
            continue

        # Check type
        if feat.get("type") != "Feature":
            result.add_error('warning',
                           f"Feature has type '{feat.get('type')}', expected 'Feature'",
                           feat_id)

        # Check geometry
        if "geometry" not in feat:
            stats["features_without_geometry"] += 1
            # Folders don't have geometry in CalTopo
            if feat.get("properties", {}).get("class") != "Folder":
                result.add_error('warning', "Feature missing geometry", feat_id)
        else:
            geom = feat["geometry"]
            if geom is not None:  # Allow null geometry
                geom_type = geom.get("type")

                # Count geometry types
                if geom_type == "Point":
                    stats["markers"] += 1
                elif geom_type in ("LineString", "MultiLineString"):
                    stats["lines"] += 1
                elif geom_type in ("Polygon", "MultiPolygon"):
                    stats["shapes"] += 1

                # Validate coordinates
                if "coordinates" in geom:
                    validate_coordinates(geom["coordinates"], geom_type, result, feat_id)

        # Check properties
        if "properties" not in feat:
            stats["features_without_properties"] += 1
            result.add_error('warning', "Feature missing properties", feat_id)
        else:
            props = feat["properties"]

            # Check for folder
            if props.get("class") == "Folder":
                stats["folders"] += 1

    result.stats = stats

    # Summary warnings
    if stats["features_without_geometry"] > 0:
        result.add_error('info',
                        f"{stats['features_without_geometry']} feature(s) without geometry")

    if stats["features_without_properties"] > 0:
        result.add_error('warning',
                        f"{stats['features_without_properties']} feature(s) without properties")

    return result


def validate_coordinates(coords: Any, geom_type: str, result: ValidationResult,
                        context: str) -> None:
    """Validate coordinate arrays."""

    def check_point(point: List[float]) -> bool:
        """Check a single [lon, lat] point."""
        if not isinstance(point, list) or len(point) < 2:
            result.add_error('error',
                           f"Invalid coordinate format: {point}",
                           context)
            return False

        lon, lat = point[0], point[1]

        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            result.add_error('error',
                           f"Non-numeric coordinates: [{lon}, {lat}]",
                           context)
            return False

        if not -180 <= lon <= 180:
            result.add_error('error',
                           f"Longitude out of range: {lon}",
                           context)
            return False

        if not -90 <= lat <= 90:
            result.add_error('error',
                           f"Latitude out of range: {lat}",
                           context)
            return False

        return True

    if geom_type == "Point":
        check_point(coords)

    elif geom_type == "LineString":
        if not isinstance(coords, list):
            result.add_error('error', "LineString coordinates must be array", context)
            return

        if len(coords) < 2:
            result.add_error('warning',
                           f"LineString has only {len(coords)} point(s)",
                           context)

        for point in coords:
            check_point(point)

    elif geom_type == "Polygon":
        if not isinstance(coords, list) or len(coords) == 0:
            result.add_error('error', "Polygon coordinates must be non-empty array", context)
            return

        for ring_idx, ring in enumerate(coords):
            if not isinstance(ring, list):
                result.add_error('error', f"Polygon ring {ring_idx} must be array", context)
                continue

            if len(ring) < 4:
                result.add_error('error',
                               f"Polygon ring {ring_idx} must have at least 4 points (closed)",
                               context)
                continue

            # Check if ring is closed
            if ring[0] != ring[-1]:
                result.add_error('warning',
                               f"Polygon ring {ring_idx} may not be closed",
                               context)

            for point in ring:
                check_point(point)

    elif geom_type == "MultiLineString":
        if not isinstance(coords, list):
            result.add_error('error', "MultiLineString coordinates must be array", context)
            return

        for line_idx, line in enumerate(coords):
            if not isinstance(line, list):
                result.add_error('error',
                               f"MultiLineString line {line_idx} must be array",
                               context)
                continue

            for point in line:
                check_point(point)

    elif geom_type == "MultiPolygon":
        if not isinstance(coords, list):
            result.add_error('error', "MultiPolygon coordinates must be array", context)
            return

        for poly_idx, poly in enumerate(coords):
            if not isinstance(poly, list):
                result.add_error('error',
                               f"MultiPolygon polygon {poly_idx} must be array",
                               context)
                continue

            for ring in poly:
                if isinstance(ring, list):
                    for point in ring:
                        check_point(point)


def validate_gpx(path: Path) -> ValidationResult:
    """Validate GPX structure and return results."""
    result = ValidationResult()

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        result.add_error('error', f"Invalid XML: {e}")
        return result
    except Exception as e:
        result.add_error('error', f"Failed to read file: {e}")
        return result

    # Check namespace
    expected_ns = "http://www.topografix.com/GPX/1/1"
    if expected_ns not in root.tag:
        result.add_error('warning',
                        f"GPX namespace may be incorrect: {root.tag}")

    ns = {"gpx": expected_ns}

    # Count elements
    waypoints = root.findall(".//gpx:wpt", ns)
    tracks = root.findall(".//gpx:trk", ns)
    routes = root.findall(".//gpx:rte", ns)

    stats = {
        "waypoints": len(waypoints),
        "tracks": len(tracks),
        "routes": len(routes),
        "track_points": 0,
        "route_points": 0
    }

    # Validate waypoints
    for i, wpt in enumerate(waypoints):
        wpt_id = f"Waypoint #{i+1}"

        if "lat" not in wpt.attrib or "lon" not in wpt.attrib:
            result.add_error('error', "Missing lat/lon attributes", wpt_id)
            continue

        try:
            lat = float(wpt.attrib["lat"])
            lon = float(wpt.attrib["lon"])

            if not -90 <= lat <= 90:
                result.add_error('error', f"Invalid latitude: {lat}", wpt_id)
            if not -180 <= lon <= 180:
                result.add_error('error', f"Invalid longitude: {lon}", wpt_id)
        except ValueError:
            result.add_error('error', "Non-numeric coordinates", wpt_id)

        # Check for name
        name_elem = wpt.find("gpx:name", ns)
        if name_elem is None or not name_elem.text:
            result.add_error('warning', "Waypoint missing name", wpt_id)

    # Validate tracks
    for i, trk in enumerate(tracks):
        trk_id = f"Track #{i+1}"

        # Check for name
        name_elem = trk.find("gpx:name", ns)
        if name_elem is None or not name_elem.text:
            result.add_error('warning', "Track missing name", trk_id)

        # Count track points
        trkpts = trk.findall(".//gpx:trkpt", ns)
        stats["track_points"] += len(trkpts)

        if len(trkpts) == 0:
            result.add_error('warning', "Track has no points", trk_id)
        elif len(trkpts) == 1:
            result.add_error('warning', "Track has only 1 point", trk_id)

        # Validate track points
        for j, trkpt in enumerate(trkpts):
            if "lat" not in trkpt.attrib or "lon" not in trkpt.attrib:
                result.add_error('error',
                               f"Track point #{j+1} missing lat/lon",
                               trk_id)

    # Validate routes
    for i, rte in enumerate(routes):
        rte_id = f"Route #{i+1}"

        rtepts = rte.findall("gpx:rtept", ns)
        stats["route_points"] += len(rtepts)

        if len(rtepts) == 0:
            result.add_error('warning', "Route has no points", rte_id)

    result.stats = stats

    # Summary info
    total_features = stats["waypoints"] + stats["tracks"] + stats["routes"]
    if total_features == 0:
        result.add_error('info', "GPX file contains no features")

    return result


def validate_kml(path: Path) -> ValidationResult:
    """Validate KML structure and return results."""
    result = ValidationResult()

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        result.add_error('error', f"Invalid XML: {e}")
        return result
    except Exception as e:
        result.add_error('error', f"Failed to read file: {e}")
        return result

    # Check namespace
    expected_ns = "http://www.opengis.net/kml/2.2"
    if expected_ns not in root.tag:
        result.add_error('warning',
                        f"KML namespace may be incorrect: {root.tag}")

    ns = {"kml": expected_ns}

    # Count elements
    placemarks = root.findall(".//kml:Placemark", ns)

    stats = {
        "placemarks": len(placemarks),
        "points": 0,
        "linestrings": 0,
        "polygons": 0,
        "other": 0
    }

    # Validate placemarks
    for i, placemark in enumerate(placemarks):
        pm_id = f"Placemark #{i+1}"

        # Check for name
        name_elem = placemark.find("kml:name", ns)
        if name_elem is None or not name_elem.text:
            result.add_error('warning', "Placemark missing name", pm_id)

        # Check for geometry
        point = placemark.find(".//kml:Point", ns)
        linestring = placemark.find(".//kml:LineString", ns)
        polygon = placemark.find(".//kml:Polygon", ns)

        if point is not None:
            stats["points"] += 1
        elif linestring is not None:
            stats["linestrings"] += 1
        elif polygon is not None:
            stats["polygons"] += 1
        else:
            stats["other"] += 1
            result.add_error('warning', "Placemark has no recognized geometry", pm_id)

    result.stats = stats

    if stats["placemarks"] == 0:
        result.add_error('info', "KML file contains no placemarks")

    return result


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python validate_output_integrity.py <file>")
        print("\nSupported file types: .json (GeoJSON), .gpx, .kml")
        sys.exit(1)

    path = Path(sys.argv[1])

    if not path.exists():
        print(f"❌ ERROR: File not found: {path}")
        sys.exit(1)

    print(f"Validating: {path.name}")
    print(f"File size: {path.stat().st_size:,} bytes")

    # Determine file type and validate
    suffix = path.suffix.lower()

    if suffix == ".json":
        result = validate_geojson(path)
    elif suffix == ".gpx":
        result = validate_gpx(path)
    elif suffix == ".kml":
        result = validate_kml(path)
    else:
        print(f"❌ ERROR: Unsupported file type: {suffix}")
        print("Supported types: .json, .gpx, .kml")
        sys.exit(1)

    # Print report
    success = result.print_report()

    # Exit with appropriate code
    sys.exit(0 if success and not result.has_errors() else 1)


if __name__ == "__main__":
    main()
