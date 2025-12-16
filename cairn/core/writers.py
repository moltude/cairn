"""
GPX and KML file writers for OnX Backcountry format.

This module generates valid GPX 1.1 files with OnX custom namespace extensions
for waypoints and tracks, and KML 2.2 files for shapes (polygons).
"""

from __future__ import annotations

from typing import List, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import uuid
import logging
from datetime import datetime
import math

from cairn.core.parser import ParsedFeature
from cairn.core.mapper import map_icon, map_color
from cairn.utils.utils import strip_html, natural_sort_key, sanitize_name_for_onx
from cairn.core.config import IconMappingConfig, get_icon_color
from cairn.core.color_mapper import (
    ColorMapper,
    pattern_to_style,
    stroke_width_to_weight,
)

# Register the OnX namespace (note: 4 'w's is required)
# IMPORTANT: OnX exports use **lowercase prefix** `onx:` and lowercase domain in the namespace URI.
# While XML namespace prefixes are technically arbitrary, OnX import appears to be prefix-sensitive.
ET.register_namespace("onx", "https://wwww.onxmaps.com/")

# Set up logger for debug output
logger = logging.getLogger(__name__)


# region agent log
def _agent_ndjson_log(payload: dict) -> None:
    """
    Debug-mode NDJSON logger (append-only).
    Writes one JSON object per line to .cursor/debug.log.
    """
    try:
        import json, os  # noqa: E401

        payload = dict(payload or {})
        # Convert Python timestamp (seconds) to JavaScript timestamp (milliseconds)
        payload.setdefault("timestamp", int(datetime.utcnow().timestamp() * 1000))
        payload.setdefault("sessionId", "debug-session")
        payload.setdefault("runId", os.environ.get("CAIRN_RUN_ID", "pre-fix"))
        with open(
            "/Users/scott/_code/cairn/.cursor/debug.log", "a", encoding="utf-8"
        ) as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


# endregion

# OnX import max GPX size is 4MB. Use a slightly lower default to avoid edge cases.
DEFAULT_MAX_GPX_BYTES = int(math.floor(3.75 * 1024 * 1024))

# Global change tracker for name sanitization
# Format: {feature_type: [(original_name, sanitized_name), ...]}
_name_changes: dict[str, list[tuple[str, str]]] = {"waypoints": [], "tracks": []}


def get_name_changes() -> dict[str, list[tuple[str, str]]]:
    """Get all tracked name changes."""
    return _name_changes.copy()


def clear_name_changes() -> None:
    """Clear tracked name changes (call before processing new folder)."""
    _name_changes["waypoints"] = []
    _name_changes["tracks"] = []


def track_name_change(feature_type: str, original: str, sanitized: str) -> None:
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
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        waypoint_names = []
        for wpt in root.findall(".//gpx:wpt", ns):
            name_elem = wpt.find("gpx:name", ns)
            if name_elem is not None and name_elem.text:
                waypoint_names.append(name_elem.text)

        return waypoint_names[:max_items] if max_items else waypoint_names
    except Exception as e:
        logger.warning(f"Could not verify GPX order: {e}")
        return []


def log_waypoint_order(
    features: List[ParsedFeature], label: str = "Waypoint order", max_items: int = 20
) -> None:
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
    sanitized_name, was_changed = sanitize_name_for_onx(name_with_prefix)

    # Track changes for reporting
    if was_changed:
        track_name_change("waypoints", name_with_prefix, sanitized_name)

    return sanitized_name


def prettify_xml(elem: ET.Element) -> str:
    """
    Return a pretty-printed XML string for the Element.

    Args:
        elem: XML Element to prettify

    Returns:
        Formatted XML string
    """
    rough_string = ET.tostring(elem, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def _utf8_joined_size(lines: List[str]) -> int:
    """
    Compute the exact UTF-8 byte size of '\\n'.join(lines) (no trailing newline).
    """
    if not lines:
        return 0
    total = 0
    for s in lines:
        total += len((s or "").encode("utf-8"))
    # newline between each adjacent pair
    total += len(lines) - 1
    return total


def _split_gpx_lines_by_bytes(
    *,
    header_lines: List[str],
    item_blocks: List[List[str]],
    footer_line: str,
    max_bytes: int,
) -> List[List[str]]:
    """
    Split a GPX payload represented as header + item blocks + footer into parts
    that are each <= max_bytes when joined with '\\n'.join(...), preserving order.
    """
    footer_bytes = len((footer_line or "").encode("utf-8"))
    header_size = _utf8_joined_size(header_lines)

    parts: List[List[str]] = []
    cur_lines: List[str] = list(header_lines)
    cur_size = header_size  # bytes of '\\n'.join(cur_lines)
    cur_items = 0

    def finalize_current() -> None:
        nonlocal cur_lines, cur_size, cur_items
        if not cur_lines:
            cur_lines = list(header_lines)
            cur_size = header_size
        cur_lines.append(footer_line)
        parts.append(cur_lines)
        cur_lines = list(header_lines)
        cur_size = header_size
        cur_items = 0

    def total_size_if_add_block(block: List[str]) -> int:
        """
        Compute total file size if we add block lines to current body.
        """
        block_size = _utf8_joined_size(block)
        # size of joined body lines after appending block (includes newline between body and block)
        new_body_size = cur_size + (1 if cur_lines else 0) + block_size
        # add newline between body and footer, then footer bytes
        return new_body_size + 1 + footer_bytes

    # If header+footer already exceeds max, we still write at least one part.
    header_footer_total = header_size + (1 if header_lines else 0) + footer_bytes
    if header_footer_total > max_bytes:
        logger.warning(
            f"GPX header/footer alone exceeds max_bytes={max_bytes} ({header_footer_total} bytes). "
            f"Proceeding anyway."
        )

    for block in item_blocks:
        if not block:
            continue

        candidate_total = total_size_if_add_block(block)

        # If adding would exceed and we already have at least one item, finalize and start a new part.
        if candidate_total > max_bytes and cur_items > 0:
            finalize_current()
            candidate_total = total_size_if_add_block(block)

        # If even a single-item part exceeds max, accept it and warn.
        if candidate_total > max_bytes and cur_items == 0:
            logger.warning(
                f"A single GPX item exceeds max_bytes={max_bytes} ({candidate_total} bytes). "
                f"Writing it as a single-part file anyway."
            )

        # Append block to current body and update size.
        if cur_lines:
            cur_size += 1  # newline between existing body and block
        cur_size += _utf8_joined_size(block)
        cur_lines.extend(block)
        cur_items += 1

    # If we added any items (or even if none), finalize one output.
    if cur_items > 0 or not parts:
        finalize_current()

    return parts


def _write_gpx_parts(
    *,
    parts: List[List[str]],
    output_path: Path,
) -> List[tuple[Path, int]]:
    """
    Write one or more GPX parts to disk.
    Returns list of (path, size_bytes).
    """
    written: List[tuple[Path, int]] = []
    if len(parts) == 1:
        output_path.write_text("\n".join(parts[0]), encoding="utf-8")
        written.append((output_path, output_path.stat().st_size))
        return written

    for i, lines in enumerate(parts, 1):
        part_path = output_path.with_name(f"{output_path.stem}_{i}{output_path.suffix}")
        part_path.write_text("\n".join(lines), encoding="utf-8")
        written.append((part_path, part_path.stat().st_size))
    return written


def write_gpx_waypoints_maybe_split(
    features: List[ParsedFeature],
    output_path: Path,
    folder_name: str,
    *,
    sort: bool = True,
    add_timestamps: bool = False,
    config: Optional[IconMappingConfig] = None,
    split: bool = True,
    max_bytes: int = DEFAULT_MAX_GPX_BYTES,
) -> List[tuple[Path, int, int]]:
    """
    Write waypoints to GPX, automatically splitting into multiple files if the output
    would exceed max_bytes. Preserves order.

    Returns list of (path, size_bytes, written_waypoint_count) for manifest.
    """
    # Keep existing behavior: optional sort.
    if sort:
        features = sorted(features, key=lambda f: natural_sort_key(f.title))

    from xml.sax.saxutils import escape

    header_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1" creator="Cairn - CalTopo to OnX Migration Tool">',
        "  <metadata>",
        f"    <name>{escape(folder_name)}</name>",
        "  </metadata>",
    ]
    footer_line = "</gpx>"

    # region agent log
    _agent_ndjson_log(
        {
            "hypothesisId": "A",
            "location": "cairn/core/writers.py:write_gpx_waypoints_maybe_split",
            "message": "Waypoints GPX header namespace",
            "data": {
                "output_path": str(output_path),
                "folder_name": folder_name,
                "header_gpx_line": header_lines[1],
                "registered_ns_uri": "https://wwww.onxmaps.com/",
            },
        }
    )
    # endregion

    item_blocks: List[List[str]] = []
    written_count = 0
    for feature in features:
        if not feature.coordinates or len(feature.coordinates) < 2:
            continue

        lat, lon = feature.coordinates[1], feature.coordinates[0]

        # Map the icon (respect user config if provided), with optional per-feature override.
        mapped_icon = None
        try:
            if isinstance(getattr(feature, "properties", None), dict):
                mapped_icon = (
                    feature.properties.get("cairn_onx_icon_override") or ""
                ).strip() or None
        except Exception:
            mapped_icon = None
        if not mapped_icon:
            mapped_icon = map_icon(
                feature.title, feature.description or "", feature.symbol, config
            )

        # Format the name (optional icon prefix + sanitization)
        formatted_name = format_waypoint_name(
            feature.title,
            mapped_icon,
            use_prefix=bool(getattr(config, "use_icon_name_prefix", False)),
            default_icon=(
                getattr(config, "default_icon", "Location") if config else "Location"
            ),
        )
        formatted_name = escape(formatted_name)

        # Waypoint color policy (unchanged)
        if feature.color:
            onx_color = ColorMapper.map_waypoint_color(feature.color)
        else:
            onx_color = get_icon_color(
                mapped_icon,
                default=(
                    config.default_color
                    if config
                    else ColorMapper.DEFAULT_WAYPOINT_COLOR
                ),
            )

        # region agent log
        if written_count < 3:
            _agent_ndjson_log(
                {
                    "hypothesisId": "B",
                    "location": "cairn/core/writers.py:write_gpx_waypoints_maybe_split",
                    "message": "Waypoint style mapping prior to write",
                    "data": {
                        "idx": written_count,
                        "title": feature.title,
                        "symbol": getattr(feature, "symbol", None),
                        "feature_color_raw": getattr(feature, "color", None),
                        "mapped_icon": mapped_icon,
                        "onx_color": onx_color,
                        "used_feature_color": bool(feature.color),
                        "extensions_tag_sample": "<onx:icon>/<onx:color>",
                    },
                }
            )
        # endregion

        wp_id = (getattr(feature, "id", "") or "").strip() or str(uuid.uuid4())
        notes_clean = strip_html(feature.description or "")
        desc_kv = "\n".join(
            [
                f"name={feature.title}",
                f"notes={notes_clean}",
                f"id={wp_id}",
                f"color={onx_color}",
                f"icon={mapped_icon}",
            ]
        )

        block: List[str] = []
        block.append(f'  <wpt lat="{lat}" lon="{lon}">')
        block.append(f"    <name>{formatted_name}</name>")
        if add_timestamps:
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            block.append(f"    <time>{timestamp}</time>")
        block.append(f"    <desc>{escape(desc_kv)}</desc>")
        block.append("    <extensions>")
        block.append(f"      <onx:icon>{mapped_icon}</onx:icon>")
        block.append(f"      <onx:color>{onx_color}</onx:color>")
        block.append("    </extensions>")
        block.append("  </wpt>")

        # region agent log
        if written_count < 2:
            _agent_ndjson_log(
                {
                    "hypothesisId": "D",
                    "location": "cairn/core/writers.py:write_gpx_waypoints_maybe_split",
                    "message": "Waypoint extensions exact lines (prefix + order)",
                    "data": {
                        "title": feature.title,
                        "extensions_lines": [
                            f"<onx:icon>{mapped_icon}</onx:icon>",
                            f"<onx:color>{onx_color}</onx:color>",
                        ],
                        "xmlns_decl": header_lines[1],
                    },
                }
            )
        # endregion

        item_blocks.append(block)
        written_count += 1

    # If splitting disabled, keep legacy single-file behavior
    if not split:
        payload = (
            header_lines + [ln for blk in item_blocks for ln in blk] + [footer_line]
        )
        output_path.write_text("\n".join(payload), encoding="utf-8")
        # region agent log
        _agent_ndjson_log(
            {
                "hypothesisId": "E",
                "location": "cairn/core/writers.py:write_gpx_waypoints_maybe_split",
                "message": "Waypoints GPX written (no split)",
                "data": {
                    "output_path": str(output_path),
                    "size_bytes": int(output_path.stat().st_size),
                    "written_count": written_count,
                },
            }
        )
        # endregion
        return [(output_path, output_path.stat().st_size, written_count)]

    # First check: would a single file exceed threshold?
    full_payload = (
        header_lines + [ln for blk in item_blocks for ln in blk] + [footer_line]
    )
    if _utf8_joined_size(full_payload) <= max_bytes:
        output_path.write_text("\n".join(full_payload), encoding="utf-8")
        # region agent log
        _agent_ndjson_log(
            {
                "hypothesisId": "E",
                "location": "cairn/core/writers.py:write_gpx_waypoints_maybe_split",
                "message": "Waypoints GPX written (single part)",
                "data": {
                    "output_path": str(output_path),
                    "size_bytes": int(output_path.stat().st_size),
                    "written_count": written_count,
                    "max_bytes": int(max_bytes),
                },
            }
        )
        # endregion
        return [(output_path, output_path.stat().st_size, written_count)]

    parts = _split_gpx_lines_by_bytes(
        header_lines=header_lines,
        item_blocks=item_blocks,
        footer_line=footer_line,
        max_bytes=max_bytes,
    )
    written = _write_gpx_parts(parts=parts, output_path=output_path)

    # Distribute counts across parts based on item_blocks packing.
    # We approximate by re-parsing: count <wpt> occurrences per part.
    out: List[tuple[Path, int, int]] = []
    for pth, sz in written:
        try:
            txt = pth.read_text(encoding="utf-8")
            cnt = txt.count("<wpt ")
        except Exception:
            cnt = 0
        out.append((pth, sz, cnt))
    # region agent log
    _agent_ndjson_log(
        {
            "hypothesisId": "E",
            "location": "cairn/core/writers.py:write_gpx_waypoints_maybe_split",
            "message": "Waypoints GPX written (split parts)",
            "data": {
                "base_output_path": str(output_path),
                "parts": [
                    {"path": str(p), "size_bytes": int(s), "wpt_count": int(c)}
                    for (p, s, c) in out
                ],
                "total_written_count": written_count,
                "max_bytes": int(max_bytes),
            },
        }
    )
    # endregion
    return out


def write_gpx_tracks_maybe_split(
    features: List[ParsedFeature],
    output_path: Path,
    folder_name: str,
    *,
    sort: bool = True,
    split: bool = True,
    max_bytes: int = DEFAULT_MAX_GPX_BYTES,
) -> List[tuple[Path, int, int]]:
    """
    Write tracks to GPX, automatically splitting into multiple files if the output
    would exceed max_bytes. Preserves order.

    Returns list of (path, size_bytes, written_track_count) for manifest.
    """
    from xml.sax.saxutils import escape

    if sort:
        features = sorted(features, key=lambda f: natural_sort_key(f.title))

    header_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1" creator="Cairn - CalTopo to OnX Migration Tool">',
        "  <metadata>",
        f"    <name>{escape(folder_name)}</name>",
        "  </metadata>",
    ]
    footer_line = "</gpx>"

    # region agent log
    _agent_ndjson_log(
        {
            "hypothesisId": "A",
            "location": "cairn/core/writers.py:write_gpx_tracks_maybe_split",
            "message": "Tracks GPX header namespace",
            "data": {
                "output_path": str(output_path),
                "folder_name": folder_name,
                "header_gpx_line": header_lines[1],
                "registered_ns_uri": "https://wwww.onxmaps.com/",
            },
        }
    )
    # endregion

    item_blocks: List[List[str]] = []
    written_count = 0

    for feature in features:
        if not feature.coordinates:
            continue

        sanitized_track_name, was_changed = sanitize_name_for_onx(feature.title)
        if was_changed:
            track_name_change("tracks", feature.title, sanitized_track_name)

        onx_color = (
            ColorMapper.transform_color(feature.stroke)
            if feature.stroke
            else ColorMapper.DEFAULT_COLOR
        )
        onx_style = pattern_to_style(feature.pattern)
        onx_weight = stroke_width_to_weight(feature.stroke_width)

        # region agent log
        if written_count < 3:
            _agent_ndjson_log(
                {
                    "hypothesisId": "B",
                    "location": "cairn/core/writers.py:write_gpx_tracks_maybe_split",
                    "message": "Track style mapping prior to write",
                    "data": {
                        "idx": written_count,
                        "title": feature.title,
                        "stroke_raw": getattr(feature, "stroke", None),
                        "pattern_raw": getattr(feature, "pattern", None),
                        "stroke_width_raw": getattr(feature, "stroke_width", None),
                        "onx": {
                            "color": onx_color,
                            "style": onx_style,
                            "weight": onx_weight,
                        },
                        "extensions_tag_sample": "<onx:color>/<onx:style>/<onx:weight>",
                    },
                }
            )
        # endregion

        trk_id = (getattr(feature, "id", "") or "").strip() or str(uuid.uuid4())
        notes_clean = strip_html(feature.description or "")
        desc_kv = "\n".join(
            [
                f"name={feature.title}",
                f"notes={notes_clean}",
                f"id={trk_id}",
                f"color={onx_color}",
                f"style={onx_style}",
                f"weight={onx_weight}",
            ]
        )

        block: List[str] = []
        block.append("  <trk>")
        block.append(f"    <name>{escape(sanitized_track_name)}</name>")
        block.append(f"    <desc>{escape(desc_kv)}</desc>")
        block.append("    <extensions>")
        block.append(f"      <onx:color>{onx_color}</onx:color>")
        block.append(f"      <onx:style>{onx_style}</onx:style>")
        block.append(f"      <onx:weight>{onx_weight}</onx:weight>")
        block.append("    </extensions>")
        block.append("    <trkseg>")

        for coord in feature.coordinates:
            if len(coord) >= 2:
                lat, lon = coord[1], coord[0]
                block.append(f'      <trkpt lat="{lat}" lon="{lon}">')
                if len(coord) > 2:
                    block.append(f"        <ele>{coord[2]}</ele>")
                block.append("      </trkpt>")

        block.append("    </trkseg>")
        block.append("  </trk>")

        item_blocks.append(block)
        written_count += 1

    if not split:
        payload = (
            header_lines + [ln for blk in item_blocks for ln in blk] + [footer_line]
        )
        output_path.write_text("\n".join(payload), encoding="utf-8")
        return [(output_path, output_path.stat().st_size, written_count)]

    full_payload = (
        header_lines + [ln for blk in item_blocks for ln in blk] + [footer_line]
    )
    if _utf8_joined_size(full_payload) <= max_bytes:
        output_path.write_text("\n".join(full_payload), encoding="utf-8")
        return [(output_path, output_path.stat().st_size, written_count)]

    parts = _split_gpx_lines_by_bytes(
        header_lines=header_lines,
        item_blocks=item_blocks,
        footer_line=footer_line,
        max_bytes=max_bytes,
    )
    written = _write_gpx_parts(parts=parts, output_path=output_path)

    out: List[tuple[Path, int, int]] = []
    for pth, sz in written:
        try:
            txt = pth.read_text(encoding="utf-8")
            cnt = txt.count("<trk>")
        except Exception:
            cnt = 0
        out.append((pth, sz, cnt))
    return out


def verify_sanitization_preserves_sort_order(
    original_names: List[str], sanitized_names: List[str]
) -> bool:
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
    for i, (orig_pair, sanit_pair) in enumerate(
        zip(pairs_sorted_by_original, pairs_sorted_by_sanitized)
    ):
        if orig_pair[0] != sanit_pair[0] or orig_pair[1] != sanit_pair[1]:
            logger.warning(
                f"Sort order mismatch at position {i}: original order differs from sanitized order"
            )
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
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1" creator="Cairn - CalTopo to OnX Migration Tool">',
        "  <metadata>",
        f"    <name>{folder_name}</name>",
        "  </metadata>",
    ]

    # Process waypoints
    for feature in features:
        if not feature.coordinates or len(feature.coordinates) < 2:
            continue

        lat, lon = feature.coordinates[1], feature.coordinates[0]

        # Map the icon (respect user config if provided), with optional per-feature override.
        mapped_icon = None
        try:
            if isinstance(getattr(feature, "properties", None), dict):
                mapped_icon = (
                    feature.properties.get("cairn_onx_icon_override") or ""
                ).strip() or None
        except Exception:
            mapped_icon = None
        if not mapped_icon:
            mapped_icon = map_icon(
                feature.title, feature.description or "", feature.symbol, config
            )

        # Track original title for verification
        original_titles.append(feature.title)

        # Format the name (optional icon prefix + sanitization)
        formatted_name = format_waypoint_name(
            feature.title,
            mapped_icon,
            use_prefix=bool(getattr(config, "use_icon_name_prefix", False)),
            default_icon=(
                getattr(config, "default_icon", "Location") if config else "Location"
            ),
        )
        sanitized_titles.append(formatted_name)

        # Escape XML special characters
        from xml.sax.saxutils import escape

        formatted_name = escape(formatted_name)

        lines.append(f'  <wpt lat="{lat}" lon="{lon}">')
        lines.append(f"    <name>{formatted_name}</name>")

        # Add timestamp if requested (for testing OnX sorting behavior)
        # Note: GPX 1.1 spec allows <time> element in waypoints
        # OnX may use this for sorting, but testing is needed
        if add_timestamps:
            # Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
            # Sequential timestamps to preserve order
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            lines.append(f"    <time>{timestamp}</time>")

        # Waypoint color policy:
        # - If CalTopo provided a marker color, preserve intent but quantize to one of
        #   OnX's official 10 waypoint colors (OnX ignores unsupported values).
        # - Otherwise, fall back to a default color per icon type.
        if feature.color:
            onx_color = ColorMapper.map_waypoint_color(feature.color)
        else:
            onx_color = get_icon_color(
                mapped_icon,
                default=(
                    config.default_color
                    if config
                    else ColorMapper.DEFAULT_WAYPOINT_COLOR
                ),
            )

        # Match OnX-exported GPX behavior: include a key/value block in <desc>.
        # OnX exports both <desc> (kv block) and <extensions> (OnX namespace).
        wp_id = (getattr(feature, "id", "") or "").strip() or str(uuid.uuid4())
        notes_clean = strip_html(feature.description or "")
        desc_kv = "\n".join(
            [
                f"name={feature.title}",
                f"notes={notes_clean}",
                f"id={wp_id}",
                f"color={onx_color}",
                f"icon={mapped_icon}",
            ]
        )
        lines.append(f"    <desc>{escape(desc_kv)}</desc>")

        # Add OnX extensions (use lowercase `onx:` prefix to match OnX exports)
        lines.append("    <extensions>")
        lines.append(f"      <onx:icon>{mapped_icon}</onx:icon>")
        lines.append(f"      <onx:color>{onx_color}</onx:color>")
        lines.append("    </extensions>")
        lines.append("  </wpt>")

    lines.append("</gpx>")

    # Write to file
    output_path.write_text("\n".join(lines), encoding="utf-8")

    # Verify that sanitization preserved sort order
    if sort and len(original_titles) == len(sanitized_titles):
        order_preserved = verify_sanitization_preserves_sort_order(
            [
                f.title
                for f in sorted(features, key=lambda f: natural_sort_key(f.title))
            ],
            sanitized_titles,
        )
        if not order_preserved:
            logger.warning(
                "Sanitization may have affected sort order - this should not happen"
            )

    # Verify order after write (debug only)
    if logger.isEnabledFor(logging.DEBUG):
        gpx_order = verify_gpx_waypoint_order(output_path)
        if gpx_order:
            logger.debug("[DEBUG] Waypoint order in GPX file:")
            for i, name in enumerate(gpx_order, 1):
                logger.debug(f"  {i}. {name}")

    return output_path.stat().st_size


def write_gpx_tracks(
    features: List[ParsedFeature],
    output_path: Path,
    folder_name: str,
    sort: bool = True,
) -> int:
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
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1" creator="Cairn - CalTopo to OnX Migration Tool">',
        "  <metadata>",
        f"    <name>{escape(folder_name)}</name>",
        "  </metadata>",
    ]

    # Process tracks
    for feature in features:
        if not feature.coordinates:
            continue

        # Sanitize track name for OnX sorting compatibility
        sanitized_track_name, was_changed = sanitize_name_for_onx(feature.title)
        if was_changed:
            track_name_change("tracks", feature.title, sanitized_track_name)

        lines.append("  <trk>")
        lines.append(f"    <name>{escape(sanitized_track_name)}</name>")

        # Map CalTopo stroke color to closest OnX color
        onx_color = (
            ColorMapper.transform_color(feature.stroke)
            if feature.stroke
            else ColorMapper.DEFAULT_COLOR
        )
        onx_style = pattern_to_style(feature.pattern)
        onx_weight = stroke_width_to_weight(feature.stroke_width)

        # Match OnX-exported GPX behavior: include a key/value block in <desc>.
        trk_id = (getattr(feature, "id", "") or "").strip() or str(uuid.uuid4())
        notes_clean = strip_html(feature.description or "")
        desc_kv = "\n".join(
            [
                f"name={feature.title}",
                f"notes={notes_clean}",
                f"id={trk_id}",
                f"color={onx_color}",
                f"style={onx_style}",
                f"weight={onx_weight}",
            ]
        )
        lines.append(f"    <desc>{escape(desc_kv)}</desc>")

        # Add OnX extensions for color, style, and weight (use lowercase `onx:` prefix)
        lines.append("    <extensions>")
        lines.append(f"      <onx:color>{onx_color}</onx:color>")

        # Map CalTopo pattern to OnX style
        lines.append(f"      <onx:style>{onx_style}</onx:style>")

        # Map CalTopo stroke-width to OnX weight
        lines.append(f"      <onx:weight>{onx_weight}</onx:weight>")

        lines.append("    </extensions>")

        lines.append("    <trkseg>")

        # Add track points
        for coord in feature.coordinates:
            if len(coord) >= 2:
                lat, lon = coord[1], coord[0]
                lines.append(f'      <trkpt lat="{lat}" lon="{lon}">')

                # Add elevation if present
                if len(coord) > 2:
                    lines.append(f"        <ele>{coord[2]}</ele>")

                lines.append("      </trkpt>")

        lines.append("    </trkseg>")
        lines.append("  </trk>")

    lines.append("</gpx>")

    # Write to file
    output_path.write_text("\n".join(lines), encoding="utf-8")

    return output_path.stat().st_size


def write_kml_shapes(
    features: List[ParsedFeature], output_path: Path, folder_name: str
) -> int:
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
        coords = (
            feature.coordinates[0]
            if isinstance(feature.coordinates[0][0], list)
            else feature.coordinates
        )
        for coord in coords:
            if len(coord) >= 2:
                lon, lat = coord[0], coord[1]
                elevation = coord[2] if len(coord) > 2 else 0
                coord_strings.append(f"{lon},{lat},{elevation}")

        coordinates_elem.text = " ".join(coord_strings)

    # Write to file
    xml_string = prettify_xml(kml)
    output_path.write_text(xml_string, encoding="utf-8")

    return output_path.stat().st_size
