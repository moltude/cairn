"""
GPX and KML file writers for onX Backcountry format.

This module generates valid GPX 1.1 files with onX custom namespace extensions
for waypoints and tracks, and KML 2.2 files for shapes (polygons).
"""

from typing import List
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import uuid

from cairn.core.parser import ParsedFeature
from cairn.core.mapper import map_icon, map_color
from cairn.utils.utils import strip_html, natural_sort_key
from cairn.core.config import get_icon_color, get_use_icon_name_prefix
from cairn.core.color_mapper import ColorMapper, pattern_to_style, stroke_width_to_weight

# Register the onX namespace (note: 4 'w's is required)
ET.register_namespace('onx', 'https://wwww.onxmaps.com/')


def format_waypoint_name(original_name: str, icon_type: str) -> str:
    """
    Format waypoint name with optional icon prefix based on config.

    Args:
        original_name: Original name from CalTopo
        icon_type: Mapped icon type (e.g., "Parking", "Caution", "Waypoint")

    Returns:
        Formatted name (with or without icon prefix based on config)
    """
    # Check if we should add icon prefixes
    use_prefix = get_use_icon_name_prefix()

    if use_prefix and icon_type != "Waypoint":
        # Add icon type prefix for non-default icons
        return f"{icon_type} - {original_name}"

    # Return clean name (no prefix)
    return original_name


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


def write_gpx_waypoints(features: List[ParsedFeature], output_path: Path,
                        folder_name: str, sort: bool = True) -> int:
    """
    Write waypoints to a GPX file with onX namespace extensions.

    Args:
        features: List of waypoint features to write
        output_path: Path to write the GPX file
        folder_name: Name for the GPX metadata
        sort: If True (default), sort features using natural sort order

    Returns:
        File size in bytes
    """
    # Sort features by title using natural sort (default behavior)
    if sort:
        features = sorted(features, key=lambda f: natural_sort_key(f.title))

    # Build GPX manually to ensure proper namespace handling
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1" creator="Cairn - CalTopo to onX Migration Tool">',
        f'  <metadata>',
        f'    <name>{folder_name}</name>',
        f'  </metadata>',
    ]

    # Process waypoints
    for feature in features:
        if not feature.coordinates or len(feature.coordinates) < 2:
            continue

        lat, lon = feature.coordinates[1], feature.coordinates[0]

        # Map the icon
        mapped_icon = map_icon(feature.title, feature.description or "", feature.symbol)

        # Format the name
        formatted_name = format_waypoint_name(feature.title, mapped_icon)

        # Escape XML special characters
        from xml.sax.saxutils import escape
        formatted_name = escape(formatted_name)

        lines.append(f'  <wpt lat="{lat}" lon="{lon}">')
        lines.append(f'    <name>{formatted_name}</name>')

        # Add description (clean, user notes only)
        if feature.description:
            desc_text = escape(strip_html(feature.description))
            lines.append(f'    <desc>{desc_text}</desc>')

        # Add onX extensions
        lines.append(f'    <extensions>')
        lines.append(f'      <onx:icon>{mapped_icon}</onx:icon>')

        # Get color - use icon's default color
        # Only transform if feature has a custom color from CalTopo
        onx_color = get_icon_color(mapped_icon)

        lines.append(f'      <onx:color>{onx_color}</onx:color>')
        lines.append(f'    </extensions>')
        lines.append(f'  </wpt>')

    lines.append('</gpx>')

    # Write to file
    output_path.write_text('\n'.join(lines), encoding='utf-8')

    return output_path.stat().st_size


def write_gpx_tracks(features: List[ParsedFeature], output_path: Path,
                     folder_name: str, sort: bool = True) -> int:
    """
    Write tracks to a GPX file with onX namespace extensions for color, style, and weight.

    Args:
        features: List of track features to write
        output_path: Path to write the GPX file
        folder_name: Name for the GPX metadata
        sort: If True (default), sort features using natural sort order

    Returns:
        File size in bytes
    """
    from xml.sax.saxutils import escape

    # Sort features by title using natural sort (default behavior)
    if sort:
        features = sorted(features, key=lambda f: natural_sort_key(f.title))

    # Build GPX manually with onX namespace
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1" creator="Cairn - CalTopo to onX Migration Tool">',
        f'  <metadata>',
        f'    <name>{escape(folder_name)}</name>',
        f'  </metadata>',
    ]

    # Process tracks
    for feature in features:
        if not feature.coordinates:
            continue

        lines.append(f'  <trk>')
        lines.append(f'    <name>{escape(feature.title)}</name>')

        # Add description if present
        if feature.description:
            desc_text = escape(strip_html(feature.description))
            lines.append(f'    <desc>{desc_text}</desc>')

        # Add onX extensions for color, style, and weight
        lines.append(f'    <extensions>')

        # Map CalTopo stroke color to closest onX color
        onx_color = ColorMapper.transform_color(feature.stroke) if feature.stroke else ColorMapper.DEFAULT_COLOR
        lines.append(f'      <onx:color>{onx_color}</onx:color>')

        # Map CalTopo pattern to onX style
        onx_style = pattern_to_style(feature.pattern)
        lines.append(f'      <onx:style>{onx_style}</onx:style>')

        # Map CalTopo stroke-width to onX weight
        onx_weight = stroke_width_to_weight(feature.stroke_width)
        lines.append(f'      <onx:weight>{onx_weight}</onx:weight>')

        lines.append(f'    </extensions>')

        lines.append(f'    <trkseg>')

        # Add track points
        for coord in feature.coordinates:
            if len(coord) >= 2:
                lat, lon = coord[1], coord[0]
                lines.append(f'      <trkpt lat="{lat}" lon="{lon}">')

                # Add elevation if present
                if len(coord) > 2:
                    lines.append(f'        <ele>{coord[2]}</ele>')

                lines.append(f'      </trkpt>')

        lines.append(f'    </trkseg>')
        lines.append(f'  </trk>')

    lines.append('</gpx>')

    # Write to file
    output_path.write_text('\n'.join(lines), encoding='utf-8')

    return output_path.stat().st_size


def write_kml_shapes(features: List[ParsedFeature], output_path: Path,
                     folder_name: str) -> int:
    """
    Write shapes (polygons) to a KML file.

    Args:
        features: List of shape features to write
        output_path: Path to write the KML file
        folder_name: Name for the document

    Returns:
        File size in bytes
    """
    # Create KML root element
    kml = ET.Element("kml")
    kml.set("xmlns", "http://www.opengis.net/kml/2.2")

    document = ET.SubElement(kml, "Document")

    # Add document name
    doc_name = ET.SubElement(document, "name")
    doc_name.text = folder_name

    # Process shapes
    for feature in features:
        if not feature.coordinates:
            continue

        placemark = ET.SubElement(document, "Placemark")

        # Add name
        name_elem = ET.SubElement(placemark, "name")
        name_elem.text = feature.title

        # Add description if present
        if feature.description:
            desc = ET.SubElement(placemark, "description")
            desc.text = strip_html(feature.description)

        # Add style
        style = ET.SubElement(placemark, "Style")
        line_style = ET.SubElement(style, "LineStyle")
        line_color = ET.SubElement(line_style, "color")

        # Convert CalTopo hex color to KML format
        line_color.text = map_color(feature.color)
        line_width = ET.SubElement(line_style, "width")
        line_width.text = "2"

        poly_style = ET.SubElement(style, "PolyStyle")
        poly_color = ET.SubElement(poly_style, "color")
        # Make fill semi-transparent
        color_value = map_color(feature.color)
        poly_color.text = "7f" + color_value[2:]  # 50% opacity

        # Add polygon geometry
        polygon = ET.SubElement(placemark, "Polygon")
        outer_boundary = ET.SubElement(polygon, "outerBoundaryIs")
        linear_ring = ET.SubElement(outer_boundary, "LinearRing")
        coordinates_elem = ET.SubElement(linear_ring, "coordinates")

        # Format coordinates (KML format: lon,lat,elevation)
        coord_strings = []
        coords = feature.coordinates[0] if isinstance(feature.coordinates[0][0], list) else feature.coordinates
        for coord in coords:
            if len(coord) >= 2:
                lon, lat = coord[0], coord[1]
                elevation = coord[2] if len(coord) > 2 else 0
                coord_strings.append(f"{lon},{lat},{elevation}")

        coordinates_elem.text = " ".join(coord_strings)

    # Write to file
    xml_string = prettify_xml(kml)
    output_path.write_text(xml_string, encoding='utf-8')

    return output_path.stat().st_size


def generate_summary_file(features: List[ParsedFeature], output_path: Path,
                         folder_name: str) -> Path:
    """
    Generate a summary.txt file listing waypoints organized by icon type.
    Only generated if use_icon_name_prefix is True.

    Args:
        features: List of waypoint features
        output_path: Path where summary file should be written (same dir as GPX)
        folder_name: Name of the folder/dataset

    Returns:
        Path to the generated summary file
    """
    from collections import defaultdict

    # Group waypoints by icon type
    icon_groups = defaultdict(list)

    for feature in features:
        icon_name = map_icon(feature.title, feature.description or "", feature.symbol)
        # Format name as it will appear in GPX
        display_name = format_waypoint_name(feature.title, icon_name)
        icon_groups[icon_name].append(display_name)

    # Generate summary content
    summary_lines = [
        f"{'='*70}",
        f"WAYPOINT ICON REFERENCE: {folder_name}",
        f"{'='*70}",
        "",
        "This file lists all waypoints organized by their recommended icon type.",
        "Use this as a reference when manually setting icons in onX after import.",
        "",
        f"Total Waypoints: {len(features)}",
        f"Icon Types: {len(icon_groups)}",
        "",
        f"{'='*70}",
        ""
    ]

    # Sort icon types alphabetically, but put "Waypoint" last
    sorted_icons = sorted(icon_groups.keys())
    if "Waypoint" in sorted_icons:
        sorted_icons.remove("Waypoint")
        sorted_icons.append("Waypoint")

    for icon_type in sorted_icons:
        waypoints = sorted(icon_groups[icon_type])
        summary_lines.append(f"\n{icon_type.upper()} ({len(waypoints)} waypoints)")
        summary_lines.append("-" * 70)

        for waypoint in waypoints:
            summary_lines.append(f"  • {waypoint}")

        summary_lines.append("")

    # Add instructions
    summary_lines.extend([
        "",
        f"{'='*70}",
        "INSTRUCTIONS FOR SETTING ICONS IN ONX:",
        f"{'='*70}",
        "",
        "1. Import the GPX file into onX Web Map",
        "2. All waypoints will appear with default icons",
        "3. Waypoint names include icon type prefix (e.g., 'Parking - Trail')",
        "4. Use onX's filter/search to find waypoints by icon type",
        "5. Select multiple waypoints and batch-edit to change icons",
        "6. Refer to this summary to see all waypoints by icon type",
        "",
        "Note: Waypoints without a prefix are generic waypoints and can remain",
        "as the default 'Waypoint' icon.",
        ""
    ])

    # Write summary file
    summary_path = output_path.parent / f"{output_path.stem}_SUMMARY.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary_lines))

    return summary_path
