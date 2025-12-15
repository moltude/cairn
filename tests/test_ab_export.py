#!/usr/bin/env python3
"""
A/B Export Script for Track vs Route Testing

This script reads a GPX track file or CalTopo GeoJSON file and generates two output files:
1. test_variant_track.gpx - Preserves track format with red color
2. test_variant_route.gpx - Converts to route format with blue color

This allows A/B testing to compare how OnX handles high-fidelity geometry
when imported as tracks versus routes.
"""

import sys
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple, Optional


def parse_geojson_lines(input_file: Path) -> tuple:
    """
    Parse all LineString features from a CalTopo GeoJSON file.

    Args:
        input_file: Path to input GeoJSON file

    Returns:
        Tuple of (points, linestring_count) where points is a list of (lat, lon, elevation) tuples

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If no LineString features found in file
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Load the GeoJSON
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get("features", [])

    if not features:
        raise ValueError(f"No features found in {input_file}")

    # Extract all LineString coordinates
    points = []
    linestring_count = 0

    for feature in features:
        if feature is None:
            continue

        geometry = feature.get("geometry")
        if geometry is None:
            continue

        geom_type = geometry.get("type")

        if geom_type == "LineString":
            linestring_count += 1
            coordinates = geometry.get("coordinates", [])

            # GeoJSON coordinates are [lon, lat, elevation (optional)]
            for coord in coordinates:
                if len(coord) >= 2:
                    lon, lat = coord[0], coord[1]
                    elevation = coord[2] if len(coord) > 2 else None
                    points.append((lat, lon, elevation))

    if linestring_count == 0:
        raise ValueError(f"No LineString features found in {input_file}")

    if not points:
        raise ValueError(f"No coordinates found in LineString features in {input_file}")

    return points, linestring_count


def parse_gpx_tracks(input_file: Path) -> List[Tuple[float, float, Optional[float]]]:
    """
    Parse all track points from a GPX file.

    Args:
        input_file: Path to input GPX file

    Returns:
        List of (lat, lon, elevation) tuples. Elevation is None if not present.

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If no tracks found in file
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Parse the GPX file
    tree = ET.parse(input_file)
    root = tree.getroot()

    # Handle namespace - GPX files use the topografix namespace
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}

    # Extract all track points from all tracks and segments
    points = []

    # Find all track elements
    tracks = root.findall('.//gpx:trk', ns)

    if not tracks:
        # Try without namespace (some GPX files don't use it properly)
        tracks = root.findall('.//trk')

    if not tracks:
        raise ValueError(f"No tracks found in {input_file}")

    # Extract points from all track segments
    for track in tracks:
        # Find all track segments
        segments = track.findall('.//gpx:trkseg', ns) if ns else track.findall('.//trkseg')
        if not segments:
            segments = track.findall('.//trkseg')

        for segment in segments:
            # Find all track points
            trkpts = segment.findall('.//gpx:trkpt', ns) if ns else segment.findall('.//trkpt')
            if not trkpts:
                trkpts = segment.findall('.//trkpt')

            for trkpt in trkpts:
                lat = float(trkpt.get('lat'))
                lon = float(trkpt.get('lon'))

                # Try to get elevation
                ele_elem = trkpt.find('gpx:ele', ns) if ns else trkpt.find('ele')
                if ele_elem is None:
                    ele_elem = trkpt.find('ele')

                elevation = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None

                points.append((lat, lon, elevation))

    if not points:
        raise ValueError(f"No track points found in {input_file}")

    return points


def write_track_variant(points: List[Tuple[float, float, Optional[float]]], output_file: Path):
    """
    Write points as a GPX track with red color.

    Args:
        points: List of (lat, lon, elevation) tuples
        output_file: Path to output file
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:OnX="https://wwww.OnXmaps.com/" version="1.1" creator="Cairn A/B Export Tool">',
        '  <metadata>',
        '    <name>Track vs Route A/B Test</name>',
        '    <desc>Testing OnX geometry handling: Track variant (red)</desc>',
        '  </metadata>',
        '  <trk>',
        '    <name>TEST - Track Variant</name>',
        '    <desc>Control: Track format with all original points</desc>',
        '    <extensions>',
        '      <OnX:color>rgba(255,0,0,1)</OnX:color>',
        '    </extensions>',
        '    <trkseg>',
    ]

    # Add all track points
    for lat, lon, elevation in points:
        lines.append(f'      <trkpt lat="{lat}" lon="{lon}">')
        if elevation is not None:
            lines.append(f'        <ele>{elevation}</ele>')
        lines.append('      </trkpt>')

    lines.extend([
        '    </trkseg>',
        '  </trk>',
        '</gpx>',
    ])

    output_file.write_text('\n'.join(lines), encoding='utf-8')


def write_route_variant(points: List[Tuple[float, float, Optional[float]]], output_file: Path):
    """
    Write points as a GPX route with blue color.

    Args:
        points: List of (lat, lon, elevation) tuples
        output_file: Path to output file
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:OnX="https://wwww.OnXmaps.com/" version="1.1" creator="Cairn A/B Export Tool">',
        '  <metadata>',
        '    <name>Track vs Route A/B Test</name>',
        '    <desc>Testing OnX geometry handling: Route variant (blue)</desc>',
        '  </metadata>',
        '  <rte>',
        '    <name>TEST - Route Variant</name>',
        '    <desc>Experiment: Route format with all original points</desc>',
        '    <extensions>',
        '      <OnX:color>rgba(0,0,255,1)</OnX:color>',
        '    </extensions>',
    ]

    # Add all route points (flattened from track segments)
    for lat, lon, elevation in points:
        lines.append(f'    <rtept lat="{lat}" lon="{lon}">')
        if elevation is not None:
            lines.append(f'      <ele>{elevation}</ele>')
        lines.append('    </rtept>')

    lines.extend([
        '  </rte>',
        '</gpx>',
    ])

    output_file.write_text('\n'.join(lines), encoding='utf-8')


def main():
    """Main entry point for the script."""
    if len(sys.argv) != 2:
        print("Usage: python test_ab_export.py <input_file>")
        print("\nSupported input formats:")
        print("  - GPX files (.gpx) containing tracks")
        print("  - CalTopo GeoJSON files (.json) containing LineString features")
        print("\nGenerates two output files:")
        print("  - test_variant_track.gpx (red, track format)")
        print("  - test_variant_route.gpx (blue, route format)")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    try:
        # Detect file type and parse accordingly
        file_ext = input_path.suffix.lower()

        if file_ext == '.json':
            print(f"Reading CalTopo GeoJSON from: {input_path}")
            points, linestring_count = parse_geojson_lines(input_path)
            print(f"  Found {linestring_count} LineString feature(s)")
            print(f"  Total points: {len(points)}")
        elif file_ext == '.gpx':
            print(f"Reading GPX track data from: {input_path}")
            points = parse_gpx_tracks(input_path)
            print(f"  Found {len(points)} track points")
        else:
            raise ValueError(f"Unsupported file type: {file_ext}. Please provide a .gpx or .json file.")

        # Check if elevation data is present
        has_elevation = any(ele is not None for _, _, ele in points)
        if has_elevation:
            print(f"  Elevation data: Present")
        else:
            print(f"  Elevation data: Not present")

        # Generate track variant
        track_output = Path("test_variant_track.gpx")
        print(f"\nGenerating track variant: {track_output}")
        write_track_variant(points, track_output)
        print(f"  ✓ Written: {track_output.stat().st_size:,} bytes")

        # Generate route variant
        route_output = Path("test_variant_route.gpx")
        print(f"\nGenerating route variant: {route_output}")
        write_route_variant(points, route_output)
        print(f"  ✓ Written: {route_output.stat().st_size:,} bytes")

        print("\n" + "="*60)
        print("SUCCESS: A/B test files generated")
        print("="*60)
        print("\nNext steps:")
        print("1. Import both files into OnX Backcountry")
        print("2. Compare geometry fidelity on the map")
        print("3. Red = Track format (control)")
        print("4. Blue = Route format (experiment)")

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
