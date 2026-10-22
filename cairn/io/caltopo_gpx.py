# Web engine: imported by web/bridge.py and run in the browser via Pyodide.
# Keep it free of terminal/UI imports (tests/test_web_engine_surface.py).
"""
CalTopo GPX adapter.

Reads a CalTopo-exported GPX file into the ParsedData structure used by the TUI.

What a CalTopo GPX carries (verified on the Dark Divide 100 export and 60 public
CalTopo GPX files, 2026-10-22; see tests/fixtures/caltopo_synthetic/README.md):
- names and coordinates, track <ele> (CalTopo fills it in), and <desc> with the
  CalTopo note verbatim, newlines included (Dark Divide: 21 multi-line notes);
- a track's colour as Garmin's ``<gpxx:TrackExtension><gpxx:DisplayColor>``, one
  of 16 names (seen: Red, Magenta, DarkBlue). It is missing on some tracks: in
  Dark Divide exactly on the one line whose CalTopo colour is the lower-case
  ``#ff0000``, so CalTopo apparently only writes a name for an exact match;
- NO folders, NO waypoint colour (Garmin's schema has no DisplayColor for a
  waypoint), NO <sym> (none in 61 files), NO line pattern or width.

This parser produces ParsedData with:
- a single default folder named after the file;
- waypoints with an empty symbol (keyword mapping, then the default pin) unless a
  <sym> is present -- other exporters write one, and it is read as GeoJSON's
  marker-symbol so the same symbol rules apply;
- tracks/routes whose DisplayColor, when present, becomes ``stroke`` (the RGB in
  GARMIN_DISPLAY_COLORS), so onX's nearest-colour rule applies as it does to
  GeoJSON's stroke; without one, the default blue.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from cairn.core.parser import ParsedData, ParsedFeature
from cairn.utils.utils import strip_html


# GPX 1.1 namespace
_GPX_NS = "http://www.topografix.com/GPX/1/1"
_GPXX_NS = "http://www.garmin.com/xmlschemas/GpxExtensions/v3"
_NS = {"gpx": _GPX_NS, "gpxx": _GPXX_NS}

# Garmin's DisplayColor_t, name -> RGB. The 17 names (16 colours + Transparent)
# are the enumeration in Garmin's schema,
# https://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd (DisplayColor_t), which
# defines no RGB. The RGB values are GPSBabel's garmin_tables.cc gt_colors
# (https://github.com/GPSBabel/gpsbabel/blob/master/garmin_tables.cc), which
# stores them as 0xBBGGRR: "Red" 0x0000FF is #FF0000, "DarkRed" 0x00008B is
# #8B0000 -- the X11/CSS colours of the same names ("Green" is CSS green,
# #008000; CSS has no DarkYellow, GPSBabel uses #8B8B00). Transparent carries
# no colour.
GARMIN_DISPLAY_COLORS = {
    "Black": "#000000",
    "DarkRed": "#8B0000",
    "DarkGreen": "#006400",
    "DarkYellow": "#8B8B00",
    "DarkBlue": "#00008B",
    "DarkMagenta": "#8B008B",
    "DarkCyan": "#008B8B",
    "LightGray": "#D3D3D3",
    "DarkGray": "#A9A9A9",
    "Red": "#FF0000",
    "Green": "#008000",
    "Yellow": "#FFFF00",
    "Blue": "#0000FF",
    "Magenta": "#FF00FF",
    "Cyan": "#00FFFF",
    "White": "#FFFFFF",
}


def _display_color(elem: ET.Element) -> str:
    """``#RRGGBB`` from a Garmin DisplayColor anywhere in elem's <extensions>
    (TrackExtension or RouteExtension; read under a waypoint too, though the
    schema doesn't define one there), else "". Unknown names and Transparent
    give ""."""
    ext = elem.find("gpx:extensions", _NS)
    if ext is None:
        return ""
    dc = ext.find(".//gpxx:DisplayColor", _NS)
    return GARMIN_DISPLAY_COLORS.get(_text(dc), "")


def _text(elem: Optional[ET.Element]) -> str:
    """Extract text content from an element, or empty string if None."""
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def _ele(pt: ET.Element) -> List[float]:
    """[ele] when the point has a usable <ele>, else [].

    A missing elevation stays missing: it used to become 0, which the GPX writer
    then emitted as <ele>0</ele>, inventing sea level. A malformed <ele> is
    treated as missing rather than dropping the point.
    """
    text = _text(pt.find("gpx:ele", _NS))
    if not text:
        return []
    try:
        return [float(text)]
    except ValueError:
        return []


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

    # CalTopo writes neither <sym> nor a waypoint colour; other exporters may.
    # Empty values trigger the keyword mapping and onX defaults.

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
            "marker-symbol": _text(wpt.find("gpx:sym", _NS)),
            "marker-color": _display_color(wpt),
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

                coords.append([lon, lat] + _ele(pt))
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
            "stroke": _display_color(trk),  # "" -> onX default blue
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

            coords.append([lon, lat] + _ele(pt))
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
            "stroke": _display_color(rte),  # "" -> onX default blue
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
