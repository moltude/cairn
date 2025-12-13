#!/usr/bin/env python3
"""
GPX Sort Order Test for onX Backcountry

This script generates a test GPX file to determine if onX respects the order
of <trk> elements within a GPX file for display sorting in their folder view.

HYPOTHESIS:
-----------
onX may display tracks in "reverse chronological" order (last parsed = top of list).
If true, we can control the visual sort order by controlling XML element order.

TEST METHODOLOGY:
-----------------
1. Generate a GPX file with 5 tracks
2. Place them in REVERSE numerical order in the XML:
   - First in XML:  "05 - Bottom (First in XML)"
   - Second in XML: "04 - Fourth"
   - Third in XML:  "03 - Middle"
   - Fourth in XML: "02 - Second"
   - Last in XML:   "01 - Top (Last in XML)"
3. Do NOT include <time> elements (isolate XML order as the variable)
4. Upload to onX Backcountry and observe folder view order

EXPECTED RESULTS:
-----------------
IF onX respects XML order (reverse):
  → "01 - Top (Last in XML)" appears at TOP of folder view
  → We can control sort order by XML element ordering

IF onX uses different logic:
  → Tracks appear alphabetically, randomly, or in forward XML order
  → We need a different approach (timestamps, metadata, etc.)

USAGE:
------
    python test_sort.py

This will create 'test_sort_order.gpx' in the current directory.
Upload this file to onX Backcountry and check the folder view order.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path


def prettify_xml(elem: ET.Element) -> str:
    """
    Return a pretty-printed XML string for the Element.

    Args:
        elem: XML Element to prettify

    Returns:
        Formatted XML string
    """
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def create_track(name: str, start_lat: float, start_lon: float, color: str = "rgba(255,0,0,1)") -> ET.Element:
    """
    Create a GPX track element with 2 points (simple line).

    Args:
        name: Track name
        start_lat: Starting latitude
        start_lon: Starting longitude
        color: Track color in rgba format

    Returns:
        ET.Element representing a <trk> element
    """
    trk = ET.Element('trk')

    # Track name
    name_elem = ET.SubElement(trk, 'name')
    name_elem.text = name

    # Track description
    desc_elem = ET.SubElement(trk, 'desc')
    desc_elem.text = f"Test track: {name}"

    # Extensions with onX color
    ext = ET.SubElement(trk, 'extensions')
    color_elem = ET.SubElement(ext, '{https://wwww.onxmaps.com/}color')
    color_elem.text = color

    # Track segment with 2 points (creates a short line)
    trkseg = ET.SubElement(trk, 'trkseg')

    # Point 1 (start)
    trkpt1 = ET.SubElement(trkseg, 'trkpt', attrib={
        'lat': f"{start_lat:.6f}",
        'lon': f"{start_lon:.6f}"
    })

    # Point 2 (end - offset by ~0.01 degrees, roughly 1km)
    trkpt2 = ET.SubElement(trkseg, 'trkpt', attrib={
        'lat': f"{start_lat + 0.01:.6f}",
        'lon': f"{start_lon + 0.01:.6f}"
    })

    return trk


def generate_sort_test_gpx(output_path: Path = Path("test_sort_order.gpx")):
    """
    Generate a test GPX file with 5 tracks in specific XML order.

    The tracks are numbered 01-05, but placed in REVERSE order in the XML
    to test if onX displays them in reverse XML order (last = top).

    Args:
        output_path: Path where the GPX file will be written
    """
    # Base coordinates (somewhere in Idaho backcountry)
    base_lat = 45.5
    base_lon = -114.5

    # Define tracks with their order and colors
    # Format: (name, lat_offset, lon_offset, color)
    tracks_data = [
        ("05 - Bottom (First in XML)", 0.00, 0.00, "rgba(255,0,0,1)"),      # Red
        ("04 - Fourth", 0.02, 0.00, "rgba(255,128,0,1)"),                    # Orange
        ("03 - Middle", 0.04, 0.00, "rgba(255,255,0,1)"),                    # Yellow
        ("02 - Second", 0.06, 0.00, "rgba(0,255,0,1)"),                      # Green
        ("01 - Top (Last in XML)", 0.08, 0.00, "rgba(0,0,255,1)"),          # Blue
    ]

    print("Generating test GPX file with tracks in this XML order:")
    print("-" * 60)

    # Build GPX manually as a string to avoid namespace issues
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1" creator="Cairn Sort Order Test">',
        '  <metadata>',
        '    <name>Sort Order Test</name>',
        '    <desc>Testing if onX respects XML element order for track sorting</desc>',
        '  </metadata>',
    ]

    # Create tracks in the specified order (05 first, 01 last)
    for i, (name, lat_offset, lon_offset, color) in enumerate(tracks_data, 1):
        lat1 = base_lat + lat_offset
        lon1 = base_lon + lon_offset
        lat2 = lat1 + 0.01
        lon2 = lon1 + 0.01

        lines.append('  <trk>')
        lines.append(f'    <name>{name}</name>')
        lines.append(f'    <desc>Test track: {name}</desc>')
        lines.append('    <extensions>')
        lines.append(f'      <onx:color>{color}</onx:color>')
        lines.append('    </extensions>')
        lines.append('    <trkseg>')
        lines.append(f'      <trkpt lat="{lat1:.6f}" lon="{lon1:.6f}"/>')
        lines.append(f'      <trkpt lat="{lat2:.6f}" lon="{lon2:.6f}"/>')
        lines.append('    </trkseg>')
        lines.append('  </trk>')

        print(f"  {i}. {name}")

    lines.append('</gpx>')
    print("-" * 60)

    # Write to file
    xml_string = '\n'.join(lines)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_string)

    print(f"\n✓ Test file created: {output_path}")
    print(f"  File size: {output_path.stat().st_size} bytes")
    print(f"  Tracks: {len(tracks_data)}")

    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Upload 'test_sort_order.gpx' to onX Backcountry web app")
    print("2. Open the imported folder and observe track order")
    print("3. Check if '01 - Top (Last in XML)' appears at the TOP")
    print("\nRESULTS INTERPRETATION:")
    print("  ✓ If '01 - Top' is at TOP → onX uses REVERSE XML order")
    print("    → We can control sort order via XML element ordering!")
    print("  ✗ If '05 - Bottom' is at TOP → onX uses FORWARD XML order")
    print("  ✗ If alphabetical → onX sorts by name (need naming strategy)")
    print("  ✗ If random → onX doesn't preserve order (need timestamps)")
    print("=" * 60)


if __name__ == "__main__":
    generate_sort_test_gpx()
