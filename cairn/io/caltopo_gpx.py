"""
CalTopo GPX adapter.

Reads a CalTopo-exported GPX file into the ParsedData structure used by the TUI.

Important notes:
- CalTopo GPX exports contain ONLY coordinates and names
- NO icon/symbol information (no <sym> element)
- NO color information (no extensions)
- NO folder structure
- NO description text (usually)

This parser produces ParsedData with:
- A single default folder named after the file
- Waypoints with empty symbol/color (triggers keyword mapping and OnX defaults)
- Tracks/routes with empty color (uses OnX default blue)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from cairn.core.parser import ParsedData, ParsedFeature
from cairn.utils.utils import strip_html


# GPX 1.1 namespace
_GPX_NS = "http://www.topografix.com/GPX/1/1"
_NS = {"gpx": _GPX_NS}


def _text(elem: Optional[ET.Element]) -> str:
    """Extract text content from an element, or empty string if None."""
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def _parse_waypoint(wpt: ET.Element, idx: int) -> Optional[Dict[str, Any]]:
    """
    Parse a <wpt> element into a GeoJSON-like feature dict.

    Returns None if coordinates are invalid.
    """
    try:
        lat = float(wpt.attrib.get("lat", ""))
        lon = float(wpt.attrib.get("lon", ""))
    except (ValueError, TypeError):
        return None

    # Validate coordinate ranges
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None

    name = _text(wpt.find("gpx:name", _NS))
    desc = _text(wpt.find("gpx:desc", _NS)) or _text(wpt.find("gpx:cmt", _NS))

    # CalTopo GPX does NOT include <sym> or color extensions
    # We explicitly set empty values to trigger OnX defaults (Location icon, Blue color)

    return {
        "type": "Feature",
        "id": f"caltopo_gpx_wpt_{idx}",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "properties": {
            "class": "Marker",
            "title": name or f"Waypoint {idx + 1}",
            "description": strip_html(desc),
            "marker-symbol": "",  # Empty triggers keyword mapping, then OnX default
            "marker-color": "",   # Empty triggers OnX default (blue)
        },
    }


def _parse_track(trk: ET.Element, idx: int) -> Optional[Dict[str, Any]]:
    """
    Parse a <trk> element into a GeoJSON-like feature dict.

    Returns None if no valid points found.
    """
    name = _text(trk.find("gpx:name", _NS))
    desc = _text(trk.find("gpx:desc", _NS)) or _text(trk.find("gpx:cmt", _NS))

    # Collect all track points from all segments
    coords: List[List[float]] = []
    for seg in trk.findall("gpx:trkseg", _NS):
        for pt in seg.findall("gpx:trkpt", _NS):
            try:
                lat = float(pt.attrib.get("lat", ""))
                lon = float(pt.attrib.get("lon", ""))
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    continue

                ele_elem = pt.find("gpx:ele", _NS)
                ele = float(_text(ele_elem)) if ele_elem is not None and _text(ele_elem) else 0
                coords.append([lon, lat, ele, 0])  # [lon, lat, ele, time_ms]
            except (ValueError, TypeError):
                continue

    if not coords:
        return None

    return {
        "type": "Feature",
        "id": f"caltopo_gpx_trk_{idx}",
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
        "properties": {
            "class": "Shape",  # CalTopo uses "Shape" for lines
            "title": name or f"Track {idx + 1}",
            "description": strip_html(desc),
            "stroke": "",       # Empty triggers OnX default (blue)
            "stroke-width": 4,
            "pattern": "solid",
        },
    }


def _parse_route(rte: ET.Element, idx: int) -> Optional[Dict[str, Any]]:
    """
    Parse a <rte> element into a GeoJSON-like feature dict.

    Returns None if no valid points found.
    """
    name = _text(rte.find("gpx:name", _NS))
    desc = _text(rte.find("gpx:desc", _NS)) or _text(rte.find("gpx:cmt", _NS))

    # Collect route points
    coords: List[List[float]] = []
    for pt in rte.findall("gpx:rtept", _NS):
        try:
            lat = float(pt.attrib.get("lat", ""))
            lon = float(pt.attrib.get("lon", ""))
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                continue

            ele_elem = pt.find("gpx:ele", _NS)
            ele = float(_text(ele_elem)) if ele_elem is not None and _text(ele_elem) else 0
            coords.append([lon, lat, ele, 0])
        except (ValueError, TypeError):
            continue

    if not coords:
        return None

    return {
        "type": "Feature",
        "id": f"caltopo_gpx_rte_{idx}",
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
        "properties": {
            "class": "Shape",
            "title": name or f"Route {idx + 1}",
            "description": strip_html(desc),
            "stroke": "",       # Empty triggers OnX default (blue)
            "stroke-width": 4,
            "pattern": "solid",
        },
    }


def parse_caltopo_gpx(filepath: Path) -> ParsedData:
    """
    Parse a CalTopo GPX export file.

    CalTopo GPX exports are minimal:
    - Only coordinates and names
    - No icons, colors, or folder structure

    This returns a ParsedData structure compatible with the TUI,
    with a single default folder containing all features.

    Args:
        filepath: Path to the GPX file

    Returns:
        ParsedData object with organized features

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is invalid or empty
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Validate file is not empty
    if filepath.stat().st_size == 0:
        raise ValueError(f"GPX file is empty: {filepath}")

    # Parse XML
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"Invalid GPX file (XML parse error): {e}\nFile: {filepath}")
    except Exception as e:
        raise ValueError(f"Failed to read GPX file: {e}\nFile: {filepath}")

    # Validate it's a GPX file
    if not (root.tag.endswith("gpx") or "gpx" in root.tag.lower()):
        raise ValueError(
            f"File does not appear to be a GPX file (root element: {root.tag})\nFile: {filepath}"
        )

    # Create ParsedData with a single default folder
    parsed_data = ParsedData()

    # Use filename (without extension) as the folder name
    folder_name = filepath.stem.replace("_", " ")
    folder_id = "default"  # Use "default" to trigger folder step skip
    parsed_data.add_folder(folder_id, folder_name)

    # Parse waypoints
    for idx, wpt in enumerate(root.findall("gpx:wpt", _NS)):
        feature_dict = _parse_waypoint(wpt, idx)
        if feature_dict:
            feature = ParsedFeature(feature_dict)
            parsed_data.add_feature_to_folder(folder_id, feature)

    # Parse tracks
    for idx, trk in enumerate(root.findall("gpx:trk", _NS)):
        feature_dict = _parse_track(trk, idx)
        if feature_dict:
            feature = ParsedFeature(feature_dict)
            parsed_data.add_feature_to_folder(folder_id, feature)

    # Parse routes
    for idx, rte in enumerate(root.findall("gpx:rte", _NS)):
        feature_dict = _parse_route(rte, idx)
        if feature_dict:
            feature = ParsedFeature(feature_dict)
            parsed_data.add_feature_to_folder(folder_id, feature)

    # Validate we found something
    stats = parsed_data.get_folder_stats(folder_id)
    if stats["total"] == 0:
        raise ValueError(
            f"No valid features found in GPX file: {filepath}\n"
            f"Tip: Make sure this is a CalTopo GPX export with waypoints, tracks, or routes"
        )

    return parsed_data
