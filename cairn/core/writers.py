"""
GPX and KML file writers for OnX Backcountry format.

This module generates valid GPX 1.1 files with OnX custom namespace extensions
for waypoints and tracks, and KML 2.2 files for shapes (polygons).
"""

from typing import List, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import uuid
import logging
from datetime import datetime

from cairn.core.parser import ParsedFeature
from cairn.core.mapper import map_icon, map_color
from cairn.utils.utils import strip_html, natural_sort_key, sanitize_name_for_OnX
from cairn.core.config import IconMappingConfig, get_icon_color
from cairn.core.color_mapper import ColorMapper, pattern_to_style, stroke_width_to_weight

# Register the OnX namespace (note: 4 'w's is required)
ET.register_namespace('OnX', 'https://wwww.OnXmaps.com/')

# Set up logger for debug output
logger = logging.getLogger(__name__)

# Global change tracker for name sanitization
# Format: {feature_type: [(original_name, sanitized_name), ...]}
_name_changes: dict[str, list[tuple[str, str]]] = {
    'waypoints': [],
    'tracks': []
}


def get_name_changes() -> dict[str, list[tuple[str, str]]]:
    """Get all tracked name changes."""
    return _name_changes.copy()


def clear_name_changes():
    """Clear tracked name changes (call before processing new folder)."""
    _name_changes['waypoints'] = []
    _name_changes['tracks'] = []


def track_name_change(feature_type: str, original: str, sanitized: str):
    """Track a name change for reporting."""
    if original != sanitized:
        _name_changes[feature_type].append((original, sanitized))


def verify_gpx_waypoint_order(gpx_path: Path, max_items: int = 20) -> List[str]:
    """
    Read back waypoint order from a GPX file to verify it matches expected order.

    Args:
        gpx_path: Path to the GPX file to read
        max_items: Maximum number of waypoint names to return (for logging)

    Returns:
        List of waypoint names in the order they appear in the GPX file
    """
    try:
        tree = ET.parse(gpx_path)
        root = tree.getroot()

        # Handle namespace
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}

        waypoint_names = []
        for wpt in root.findall('.//gpx:wpt', ns):
            name_elem = wpt.find('gpx:name', ns)
            if name_elem is not None and name_elem.text:
                waypoint_names.append(name_elem.text)

        return waypoint_names[:max_items] if max_items else waypoint_names
    except Exception as e:
        logger.warning(f"Could not verify GPX order: {e}")
        return []


def log_waypoint_order(features: List[ParsedFeature], label: str = "Waypoint order", max_items: int = 20) -> None:
    """
    Log the order of waypoints for debugging purposes.

    Args:
        features: List of waypoint features
        label: Label for the log message
        max_items: Maximum number of items to log
    """
    if not logger.isEnabledFor(logging.DEBUG):
        return

    waypoint_names = [f.title for f in features[:max_items]]

    logger.debug(f"[DEBUG] {label}:")
    for i, name in enumerate(waypoint_names, 1):
        logger.debug(f"  {i}. {name}")

    if len(features) > max_items:
        logger.debug(f"  ... and {len(features) - max_items} more waypoints")


def format_waypoint_name(
    original_name: str,
    icon_type: str,
    *,
    use_prefix: bool,
    default_icon: str = "Location",
) -> str:
    """
    Format waypoint name with optional icon prefix based on config,
    and sanitize for OnX sorting compatibility.

    Args:
        original_name: Original name from CalTopo
        icon_type: Mapped icon type (e.g., "Parking", "Caution", "Waypoint")

    Returns:
        Formatted and sanitized name
    """
    if use_prefix and icon_type != default_icon:
        # Add icon type prefix for non-default icons
        name_with_prefix = f"{icon_type} - {original_name}"
    else:
        name_with_prefix = original_name

    # Sanitize name for OnX sorting compatibility
    sanitized_name, was_changed = sanitize_name_for_OnX(name_with_prefix)

    # Track changes for reporting
    if was_changed:
        track_name_change('waypoints', name_with_prefix, sanitized_name)

    return sanitized_name


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


def verify_sanitization_preserves_sort_order(original_names: List[str], sanitized_names: List[str]) -> bool:
    """
    Verify that sanitization preserves natural sort order.

    Checks that if we sort both lists, items at the same index correspond to each other.

    Args:
        original_names: List of original names (in any order)
        sanitized_names: List of sanitized names (corresponding to original_names)

    Returns:
        True if sort order is preserved, False otherwise
    """
    if len(original_names) != len(sanitized_names):
        return False

    # Create pairs and sort both lists
    pairs = list(zip(original_names, sanitized_names))
    pairs_sorted_by_original = sorted(pairs, key=lambda p: natural_sort_key(p[0]))
    pairs_sorted_by_sanitized = sorted(pairs, key=lambda p: natural_sort_key(p[1]))

    # Check if the pairs are in the same order when sorted by original vs sanitized
    for i, (orig_pair, sanit_pair) in enumerate(zip(pairs_sorted_by_original, pairs_sorted_by_sanitized)):
        if orig_pair[0] != sanit_pair[0] or orig_pair[1] != sanit_pair[1]:
            logger.warning(f"Sort order mismatch at position {i}: original order differs from sanitized order")
            return False

    return True


def write_gpx_waypoints(
    features: List[ParsedFeature],
    output_path: Path,
    folder_name: str,
    sort: bool = True,
    add_timestamps: bool = False,
    config: Optional[IconMappingConfig] = None,
) -> int:
    """
    Write waypoints to a GPX file with OnX namespace extensions.

    Args:
        features: List of waypoint features to write
        output_path: Path to write the GPX file
        folder_name: Name for the GPX metadata
        sort: If True (default), sort features using natural sort order
        add_timestamps: If True, add <time> elements to waypoints (for testing OnX sorting)

    Returns:
        File size in bytes

    Note:
        OnX may re-sort items after import based on name, icon type, or other criteria.
        GPX element order is respected during import but may change post-import.
        Adding timestamps is experimental and may help preserve order if OnX respects them.
    """
    # Sort features by title using natural sort
    if sort:
        features = sorted(features, key=lambda f: natural_sort_key(f.title))
        log_waypoint_order(features, "Waypoint order before write")

    # Collect original and sanitized names for verification
    original_titles = []
    sanitized_titles = []

    # Build GPX manually to ensure proper namespace handling
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:OnX="https://wwww.OnXmaps.com/" version="1.1" creator="Cairn - CalTopo to OnX Migration Tool">',
        f'  <metadata>',
        f'    <name>{folder_name}</name>',
        f'  </metadata>',
    ]

    # Process waypoints
    for feature in features:
        if not feature.coordinates or len(feature.coordinates) < 2:
            continue

        lat, lon = feature.coordinates[1], feature.coordinates[0]

        # Map the icon (respect user config if provided)
        mapped_icon = map_icon(feature.title, feature.description or "", feature.symbol, config)

        # Track original title for verification
        original_titles.append(feature.title)

        # Format the name (optional icon prefix + sanitization)
        formatted_name = format_waypoint_name(
            feature.title,
            mapped_icon,
            use_prefix=bool(getattr(config, "use_icon_name_prefix", False)),
            default_icon=(getattr(config, "default_icon", "Location") if config else "Location"),
        )
        sanitized_titles.append(formatted_name)

        # Escape XML special characters
        from xml.sax.saxutils import escape
        formatted_name = escape(formatted_name)

        lines.append(f'  <wpt lat="{lat}" lon="{lon}">')
        lines.append(f'    <name>{formatted_name}</name>')

        # Add timestamp if requested (for testing OnX sorting behavior)
        # Note: GPX 1.1 spec allows <time> element in waypoints
        # OnX may use this for sorting, but testing is needed
        if add_timestamps:
            # Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
            # Sequential timestamps to preserve order
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            lines.append(f'    <time>{timestamp}</time>')

        # Add description (clean, user notes only)
        if feature.description:
            desc_text = escape(strip_html(feature.description))
            lines.append(f'    <desc>{desc_text}</desc>')

        # Add OnX extensions
        lines.append(f'    <extensions>')
        lines.append(f'      <OnX:icon>{mapped_icon}</OnX:icon>')

        # Waypoint color policy:
        # - If CalTopo provided a marker color, preserve intent but quantize to one of
        #   OnX's official 10 waypoint colors (OnX ignores unsupported values).
        # - Otherwise, fall back to a default color per icon type.
        if feature.color:
            OnX_color = ColorMapper.map_waypoint_color(feature.color)
        else:
            OnX_color = get_icon_color(
                mapped_icon,
                default=(config.default_color if config else ColorMapper.DEFAULT_WAYPOINT_COLOR),
            )

        lines.append(f'      <OnX:color>{OnX_color}</OnX:color>')
        lines.append(f'    </extensions>')
        lines.append(f'  </wpt>')

    lines.append('</gpx>')

    # Write to file
    output_path.write_text('\n'.join(lines), encoding='utf-8')

    # Verify that sanitization preserved sort order
    if sort and len(original_titles) == len(sanitized_titles):
        order_preserved = verify_sanitization_preserves_sort_order(
            [f.title for f in sorted(features, key=lambda f: natural_sort_key(f.title))],
            sanitized_titles
        )
        if not order_preserved:
            logger.warning("Sanitization may have affected sort order - this should not happen")

    # Verify order after write (debug only)
    if logger.isEnabledFor(logging.DEBUG):
        gpx_order = verify_gpx_waypoint_order(output_path)
        if gpx_order:
            logger.debug("[DEBUG] Waypoint order in GPX file:")
            for i, name in enumerate(gpx_order, 1):
                logger.debug(f"  {i}. {name}")

    return output_path.stat().st_size


def write_gpx_tracks(features: List[ParsedFeature], output_path: Path,
                     folder_name: str, sort: bool = True) -> int:
    """
    Write tracks to a GPX file with OnX namespace extensions for color, style, and weight.

    Args:
        features: List of track features to write
        output_path: Path to write the GPX file
        folder_name: Name for the GPX metadata
        sort: If True (default), sort and reverse features for OnX display order

    Returns:
        File size in bytes

    Note:
        OnX displays items in the same order as the GPX file.
    """
    from xml.sax.saxutils import escape

    # Sort features by title using natural sort
    if sort:
        features = sorted(features, key=lambda f: natural_sort_key(f.title))

    # Build GPX manually with OnX namespace
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:OnX="https://wwww.OnXmaps.com/" version="1.1" creator="Cairn - CalTopo to OnX Migration Tool">',
        f'  <metadata>',
        f'    <name>{escape(folder_name)}</name>',
        f'  </metadata>',
    ]

    # Process tracks
    for feature in features:
        if not feature.coordinates:
            continue

        # Sanitize track name for OnX sorting compatibility
        sanitized_track_name, was_changed = sanitize_name_for_OnX(feature.title)
        if was_changed:
            track_name_change('tracks', feature.title, sanitized_track_name)

        lines.append(f'  <trk>')
        lines.append(f'    <name>{escape(sanitized_track_name)}</name>')

        # Add description if present
        if feature.description:
            desc_text = escape(strip_html(feature.description))
            lines.append(f'    <desc>{desc_text}</desc>')

        # Add OnX extensions for color, style, and weight
        lines.append(f'    <extensions>')

        # Map CalTopo stroke color to closest OnX color
        OnX_color = ColorMapper.transform_color(feature.stroke) if feature.stroke else ColorMapper.DEFAULT_COLOR
        lines.append(f'      <OnX:color>{OnX_color}</OnX:color>')

        # Map CalTopo pattern to OnX style
        OnX_style = pattern_to_style(feature.pattern)
        lines.append(f'      <OnX:style>{OnX_style}</OnX:style>')

        # Map CalTopo stroke-width to OnX weight
        OnX_weight = stroke_width_to_weight(feature.stroke_width)
        lines.append(f'      <OnX:weight>{OnX_weight}</OnX:weight>')

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


def generate_summary_file(
    features: List[ParsedFeature],
    output_path: Path,
    folder_name: str,
    config: Optional[IconMappingConfig] = None,
) -> Path:
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
        icon_name = map_icon(feature.title, feature.description or "", feature.symbol, config)
        # Format name as it will appear in GPX
        display_name = format_waypoint_name(
            feature.title,
            icon_name,
            use_prefix=bool(getattr(config, "use_icon_name_prefix", False)),
            default_icon=(getattr(config, "default_icon", "Location") if config else "Location"),
        )
        icon_groups[icon_name].append(display_name)

    # Generate summary content
    summary_lines = [
        f"{'='*70}",
        f"WAYPOINT ICON REFERENCE: {folder_name}",
        f"{'='*70}",
        "",
        "This file lists all waypoints organized by their recommended icon type.",
        "Use this as a reference when manually setting icons in OnX after import.",
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
        "INSTRUCTIONS FOR SETTING ICONS IN OnX:",
        f"{'='*70}",
        "",
        "1. Import the GPX file into OnX Web Map",
        "2. All waypoints will appear with default icons",
        "3. Waypoint names include icon type prefix (e.g., 'Parking - Trail')",
        "4. Use OnX's filter/search to find waypoints by icon type",
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
