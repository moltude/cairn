"""
OnX Backcountry KML adapter.

Reads an OnX-exported KML file into Cairn's canonical MapDocument model.

Important observations (captured in docs):
- OnX KML export typically contains no Folder structure.
- Styling is stripped; metadata lives in <ExtendedData> fields like:
  - name, notes, id, icon, color
- KML is valuable for capturing Polygon geometry (areas) which GPX does not represent as polygons.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid
import xml.etree.ElementTree as ET

from cairn.core.normalization import normalize_name
from cairn.model import MapDocument, Shape, Style, Track, TrackPoint, Waypoint


_KML_NS = "http://www.opengis.net/kml/2.2"
_NS = {"kml": _KML_NS}


def _uuid_fallback() -> str:
    return str(uuid.uuid4())


def _text(elem: Optional[ET.Element]) -> str:
    if elem is None or elem.text is None:
        return ""
    return elem.text


def _parse_extended_data(pm: ET.Element) -> Dict[str, str]:
    kv: Dict[str, str] = {}
    for d in pm.findall(".//kml:ExtendedData//kml:Data", _NS):
        key = d.attrib.get("name")
        if not key:
            continue
        val = _text(d.find("kml:value", _NS)).strip()
        kv[key.strip().lower()] = val
    return kv


def _parse_kml_coords_list(text: str) -> List[Tuple[float, float, Optional[float]]]:
    """
    Parse KML coordinate lists with error handling.

    KML coordinates are: lon,lat[,alt] separated by whitespace/newlines.
    Skips invalid coordinates and continues processing.
    """
    text = (text or "").strip()
    if not text:
        return []
    pts: List[Tuple[float, float, Optional[float]]] = []
    for token in text.replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
            # Validate coordinate ranges
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                continue  # Skip invalid coordinates
            alt = float(parts[2]) if len(parts) >= 3 and parts[2] != "" else None
            pts.append((lon, lat, alt))
        except (ValueError, TypeError):
            # Skip malformed coordinate but continue processing
            continue
    return pts


def read_OnX_kml(path: str | Path, *, trace: Any = None) -> MapDocument:
    """
    Read an OnX KML export.

    Args:
      path: path to KML file
      trace: optional TraceWriter-like object with `emit(event: dict)` method

    Raises:
      ValueError: If the file is not a valid KML file or is empty
    """
    p = Path(path)

    # Validate file is not empty
    if p.stat().st_size == 0:
        raise ValueError(f"KML file is empty: {p}")

    # Parse XML with error handling
    try:
        root = ET.parse(p).getroot()
    except ET.ParseError as e:
        raise ValueError(f"Invalid KML file (XML parse error): {e}\nFile: {p}")
    except Exception as e:
        raise ValueError(f"Failed to read KML file: {e}\nFile: {p}")

    # Validate it's actually a KML file
    if not (root.tag.endswith("kml") or "kml" in root.tag.lower()):
        raise ValueError(f"File does not appear to be a KML file (root element: {root.tag})\nFile: {p}")

    doc = MapDocument(metadata={"source": "OnX_kml", "path": str(p)})
    doc.ensure_folder("OnX_import", "OnX Import")
    doc.ensure_folder("OnX_waypoints", "Waypoints", parent_id="OnX_import")
    doc.ensure_folder("OnX_tracks", "Tracks", parent_id="OnX_import")
    doc.ensure_folder("OnX_shapes", "Areas", parent_id="OnX_import")

    placemarks = root.findall(".//kml:Placemark", _NS)
    for idx, pm in enumerate(placemarks):
        name_raw = _text(pm.find("kml:name", _NS))
        name = normalize_name(name_raw)

        kv = _parse_extended_data(pm)
        OnX_id = kv.get("id") or kv.get("OnX:id")
        OnX_icon = kv.get("icon")
        OnX_color = kv.get("color")
        notes = kv.get("notes", "")

        style = Style(OnX_id=OnX_id, OnX_icon=OnX_icon, OnX_color_rgba=OnX_color)
        style.extra["extended_data"] = dict(kv)

        # Geometry dispatch
        if pm.find(".//kml:Point", _NS) is not None:
            coord_text = _text(pm.find(".//kml:Point/kml:coordinates", _NS))
            pts = _parse_kml_coords_list(coord_text)
            if not pts:
                continue
            lon, lat, _alt = pts[0]
            wp = Waypoint(
                id=OnX_id or _uuid_fallback(),
                folder_id="OnX_waypoints",
                name=name or normalize_name(kv.get("name", "")),
                lon=lon,
                lat=lat,
                notes=normalize_name(notes),
                style=style,
                extra={"name_raw": name_raw},
            )
            doc.add_item(wp)
            if trace is not None:
                trace.emit(
                    {
                        "event": "input.kml.placemark",
                        "idx": idx,
                        "geom": "Point",
                        "name_raw": name_raw,
                        "name_norm": wp.name,
                        "OnX": {"id": OnX_id, "icon": OnX_icon, "color": OnX_color},
                    }
                )
            continue

        if pm.find(".//kml:LineString", _NS) is not None:
            coord_text = _text(pm.find(".//kml:LineString/kml:coordinates", _NS))
            pts = _parse_kml_coords_list(coord_text)
            if not pts:
                continue
            points: List[TrackPoint] = [(lon, lat, alt, None) for (lon, lat, alt) in pts]
            trk = Track(
                id=OnX_id or _uuid_fallback(),
                folder_id="OnX_tracks",
                name=name or normalize_name(kv.get("name", "")),
                points=points,
                notes=normalize_name(notes),
                style=style,
                extra={"name_raw": name_raw, "kml_geom": "LineString"},
            )
            doc.add_item(trk)
            if trace is not None:
                trace.emit(
                    {
                        "event": "input.kml.placemark",
                        "idx": idx,
                        "geom": "LineString",
                        "name_raw": name_raw,
                        "name_norm": trk.name,
                        "point_count": len(points),
                        "OnX": {"id": OnX_id, "color": OnX_color},
                    }
                )
            continue

        if pm.find(".//kml:Polygon", _NS) is not None:
            # Prefer outer boundary ring.
            outer = _text(
                pm.find(
                    ".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates",
                    _NS,
                )
            )
            ring_pts = _parse_kml_coords_list(outer)
            if not ring_pts:
                continue
            ring = [(lon, lat) for (lon, lat, _alt) in ring_pts]
            shp = Shape(
                id=OnX_id or _uuid_fallback(),
                folder_id="OnX_shapes",
                name=name or normalize_name(kv.get("name", "")),
                rings=[ring],
                notes=normalize_name(notes),
                style=style,
                extra={"name_raw": name_raw, "kml_geom": "Polygon"},
            )
            doc.add_item(shp)
            if trace is not None:
                trace.emit(
                    {
                        "event": "input.kml.placemark",
                        "idx": idx,
                        "geom": "Polygon",
                        "name_raw": name_raw,
                        "name_norm": shp.name,
                        "ring_len": len(ring),
                        "OnX": {"id": OnX_id, "color": OnX_color},
                    }
                )
            continue

    return doc
