"""
onX Backcountry KML adapter.

Reads an onX-exported KML file into Cairn's canonical MapDocument model.

Important observations (captured in docs):
- onX KML export typically contains no Folder structure.
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
    Parse KML coordinate lists.

    KML coordinates are: lon,lat[,alt] separated by whitespace/newlines.
    """
    text = (text or "").strip()
    if not text:
        return []
    pts: List[Tuple[float, float, Optional[float]]] = []
    for token in text.replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        lon = float(parts[0])
        lat = float(parts[1])
        alt = float(parts[2]) if len(parts) >= 3 and parts[2] != "" else None
        pts.append((lon, lat, alt))
    return pts


def read_onx_kml(path: str | Path, *, trace: Any = None) -> MapDocument:
    p = Path(path)
    root = ET.parse(p).getroot()

    doc = MapDocument(metadata={"source": "onx_kml", "path": str(p)})
    doc.ensure_folder("onx_import", "OnX Import")
    doc.ensure_folder("onx_waypoints", "Waypoints", parent_id="onx_import")
    doc.ensure_folder("onx_tracks", "Tracks", parent_id="onx_import")
    doc.ensure_folder("onx_shapes", "Areas", parent_id="onx_import")

    placemarks = root.findall(".//kml:Placemark", _NS)
    for idx, pm in enumerate(placemarks):
        name_raw = _text(pm.find("kml:name", _NS))
        name = normalize_name(name_raw)

        kv = _parse_extended_data(pm)
        onx_id = kv.get("id") or kv.get("onx:id")
        onx_icon = kv.get("icon")
        onx_color = kv.get("color")
        notes = kv.get("notes", "")

        style = Style(onx_id=onx_id, onx_icon=onx_icon, onx_color_rgba=onx_color)
        style.extra["extended_data"] = dict(kv)

        # Geometry dispatch
        if pm.find(".//kml:Point", _NS) is not None:
            coord_text = _text(pm.find(".//kml:Point/kml:coordinates", _NS))
            pts = _parse_kml_coords_list(coord_text)
            if not pts:
                continue
            lon, lat, _alt = pts[0]
            wp = Waypoint(
                id=onx_id or _uuid_fallback(),
                folder_id="onx_waypoints",
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
                        "onx": {"id": onx_id, "icon": onx_icon, "color": onx_color},
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
                id=onx_id or _uuid_fallback(),
                folder_id="onx_tracks",
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
                        "onx": {"id": onx_id, "color": onx_color},
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
                id=onx_id or _uuid_fallback(),
                folder_id="onx_shapes",
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
                        "onx": {"id": onx_id, "color": onx_color},
                    }
                )
            continue

    return doc
