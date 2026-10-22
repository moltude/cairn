# Web engine: imported by web/bridge.py and run in the browser via Pyodide.
# Keep it free of terminal/UI imports (tests/test_web_engine_surface.py).
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
from cairn.utils.utils import strip_html
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


_GEOM_TAGS = {f"{{{_KML_NS}}}{k}" for k in ("Point", "LineString", "Polygon")}


def _ring(coords_elem: Optional[ET.Element]) -> List[Tuple[float, float]]:
    """A LinearRing's (lon, lat) list, closed; [] if it has under 3 corners."""
    pts = [(lon, lat) for (lon, lat, _alt) in _parse_kml_coords_list(_text(coords_elem))]
    if len(pts) < 3:
        return []
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def read_onx_kml(path: str | Path, *, trace: Any = None) -> MapDocument:
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
        raise ValueError(
            f"File does not appear to be a KML file (root element: {root.tag})\nFile: {p}"
        )

    doc = MapDocument(metadata={"source": "OnX_kml", "path": str(p)})
    doc.ensure_folder("OnX_import", "OnX Import")
    doc.ensure_folder("OnX_waypoints", "Waypoints", parent_id="OnX_import")
    doc.ensure_folder("OnX_tracks", "Tracks", parent_id="OnX_import")
    doc.ensure_folder("OnX_shapes", "Areas", parent_id="OnX_import")

    placemarks = root.findall(".//kml:Placemark", _NS)
    for idx, pm in enumerate(placemarks):
        name_raw = _text(pm.find("kml:name", _NS))

        kv = _parse_extended_data(pm)
        name = normalize_name(name_raw) or normalize_name(kv.get("name", ""))
        onx_id = kv.get("id") or kv.get("onx:id")  # keys are lowercased in _parse_extended_data
        onx_icon = kv.get("icon")
        onx_color = kv.get("color")
        # onX (tokml) and Cairn both put notes in ExtendedData. Other KML -- Google
        # Earth, CalTopo, hand-made -- uses <description>, often HTML.
        if "notes" in kv:
            notes = normalize_name(kv["notes"])
        else:
            notes = strip_html(_text(pm.find("kml:description", _NS)))

        # Every geometry in the Placemark, in document order: a MultiGeometry yields
        # one item per part. Parts share the name, notes, style and onX id; part 2+
        # get their own item id and record their index in extra["kml_part"].
        geoms = [g for g in pm.iter() if g.tag in _GEOM_TAGS]
        part = 0
        for geom in geoms:
            style = Style(
                OnX_id=onx_id,
                OnX_icon=onx_icon,
                OnX_color_rgba=onx_color,
                OnX_style=kv.get("style") or None,
                OnX_weight=kv.get("weight") or None,
            )
            style.extra["extended_data"] = dict(kv)
            if kv.get("fill_color"):
                style.extra["fill_color"] = kv["fill_color"]
            base_id = onx_id or _uuid_fallback()
            item_id = base_id if part == 0 else f"{base_id}:part{part + 1}"
            extra: Dict[str, Any] = {"name_raw": name_raw}
            if len(geoms) > 1:
                extra["kml_part"] = part

            kind = geom.tag.rsplit("}", 1)[-1]
            item: Any = None
            if kind == "Point":
                pts = _parse_kml_coords_list(_text(geom.find("kml:coordinates", _NS)))
                if pts:
                    lon, lat, _alt = pts[0]
                    item = Waypoint(
                        id=item_id, folder_id="OnX_waypoints", name=name, lon=lon,
                        lat=lat, notes=notes, style=style, extra=extra,
                    )
            elif kind == "LineString":
                pts = _parse_kml_coords_list(_text(geom.find("kml:coordinates", _NS)))
                if pts:
                    extra["kml_geom"] = "LineString"
                    item = Track(
                        id=item_id, folder_id="OnX_tracks", name=name,
                        points=[(lon, lat, alt, None) for (lon, lat, alt) in pts],
                        notes=notes, style=style, extra=extra,
                    )
            else:  # Polygon: outer ring, then every inner ring (holes)
                outer = _ring(geom.find("kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", _NS))
                if outer:
                    rings = [outer]
                    for inner in geom.findall("kml:innerBoundaryIs/kml:LinearRing/kml:coordinates", _NS):
                        hole = _ring(inner)
                        if hole:
                            rings.append(hole)
                    extra["kml_geom"] = "Polygon"
                    item = Shape(
                        id=item_id, folder_id="OnX_shapes", name=name, rings=rings,
                        notes=notes, style=style, extra=extra,
                    )
            if item is None:
                continue
            doc.add_item(item)
            part += 1
            if trace is not None:
                trace.emit(
                    {
                        "event": "input.kml.placemark",
                        "idx": idx,
                        "geom": kind,
                        "part": part,
                        "name_raw": name_raw,
                        "name_norm": name,
                        "OnX": {"id": onx_id, "icon": onx_icon, "color": onx_color},
                    }
                )

    return doc
