"""
onX Backcountry GPX adapter.

Reads an onX-exported GPX file into Cairn's canonical MapDocument model.

Notes:
- onX exports often include a key/value block in <desc> for both waypoints and tracks.
- onX also includes custom extensions in namespace https://wwww.onxmaps.com/
- onX GPX export structure can vary (tracks vs routes), so we read <trk> and <rte>.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re
import uuid
import xml.etree.ElementTree as ET

from cairn.core.normalization import iso8601_to_epoch_ms, normalize_key, normalize_name
from cairn.model import MapDocument, Style, Track, TrackPoint, Waypoint


_ONX_NS = "https://wwww.onxmaps.com/"
_GPX_NS = "http://www.topografix.com/GPX/1/1"
_NS = {"gpx": _GPX_NS, "onx": _ONX_NS}


_DESC_KV_KEYS = (
    "name",
    "notes",
    "id",
    "color",
    "icon",
    "style",
    "weight",
    "type",
)

_DESC_KV_RE = re.compile(r"^([a-zA-Z0-9_-]+)=(.*)$")


def _stable_uuid_fallback() -> str:
    return str(uuid.uuid4())


def parse_onx_desc_kv(desc_text: str) -> Tuple[Dict[str, str], str]:
    """
    Parse an onX <desc> key/value block.

    The common structure is:
      name=...
      notes=...   (may be multiline)
      id=...
      color=rgba(...)
      icon=Location

    Returns:
      - kv dict of discovered keys (string values)
      - raw notes (best-effort extracted)
    """
    desc_text = (desc_text or "").strip("\n")
    if not desc_text:
        return {}, ""

    lines = desc_text.splitlines()
    kv: Dict[str, str] = {}
    current_key: Optional[str] = None
    current_value_lines: List[str] = []

    def flush():
        nonlocal current_key, current_value_lines
        if current_key is None:
            return
        kv[current_key] = "\n".join(current_value_lines).strip("\n")
        current_key = None
        current_value_lines = []

    for line in lines:
        m = _DESC_KV_RE.match(line)
        if m:
            key = m.group(1).strip()
            value = m.group(2)
            key_norm = key.lower().strip()
            # If this looks like a known key, start a new field.
            if key_norm in _DESC_KV_KEYS:
                flush()
                current_key = key_norm
                current_value_lines = [value]
                continue

        # Continuation line (commonly notes)
        if current_key is None:
            # If the first line isn't key=value, treat all as notes.
            current_key = "notes"
            current_value_lines = [line]
        else:
            current_value_lines.append(line)

    flush()
    notes = kv.get("notes", "")
    return kv, notes


def _get_onx_extension_text(elem: ET.Element, local_name: str) -> Optional[str]:
    """
    Read onX extension element by local name from an <extensions> element.
    """
    if elem is None:
        return None
    child = elem.find(f"onx:{local_name}", _NS)
    if child is not None and child.text:
        return child.text.strip()
    return None


def read_onx_gpx(path: str | Path, *, trace: Any = None) -> MapDocument:
    """
    Read an onX GPX export.

    Args:
      path: path to GPX
      trace: optional TraceWriter-like object with `emit(event: dict)` method
    """
    p = Path(path)
    tree = ET.parse(p)
    root = tree.getroot()

    doc = MapDocument(metadata={"source": "onx_gpx", "path": str(p)})

    # Default folder structure (value-add for CalTopo)
    doc.ensure_folder("onx_import", "OnX Import")
    doc.ensure_folder("onx_waypoints", "Waypoints", parent_id="onx_import")
    doc.ensure_folder("onx_tracks", "Tracks", parent_id="onx_import")

    # Waypoints
    for idx, wpt in enumerate(root.findall("gpx:wpt", _NS)):
        lat = float(wpt.attrib.get("lat"))
        lon = float(wpt.attrib.get("lon"))

        name_elem = wpt.find("gpx:name", _NS)
        name_raw = name_elem.text if name_elem is not None and name_elem.text else ""
        name = normalize_name(name_raw)

        desc_elem = wpt.find("gpx:desc", _NS)
        desc_raw = desc_elem.text if desc_elem is not None and desc_elem.text else ""
        kv, notes = parse_onx_desc_kv(desc_raw)

        ext = wpt.find("gpx:extensions", _NS)
        onx_color = _get_onx_extension_text(ext, "color") or kv.get("color")
        onx_icon = _get_onx_extension_text(ext, "icon") or kv.get("icon")
        onx_id = kv.get("id")

        style = Style(onx_icon=onx_icon, onx_color_rgba=onx_color, onx_id=onx_id)
        style.extra["desc_kv"] = kv

        wp = Waypoint(
            id=onx_id or _stable_uuid_fallback(),
            folder_id="onx_waypoints",
            name=name,
            lon=lon,
            lat=lat,
            notes=normalize_name(notes) if notes else "",
            style=style,
            extra={"name_raw": name_raw, "desc_raw": desc_raw},
        )
        doc.add_item(wp)

        if trace is not None:
            trace.emit(
                {
                    "event": "input.wpt",
                    "idx": idx,
                    "lat": lat,
                    "lon": lon,
                    "name_raw": name_raw,
                    "name_norm": name,
                    "onx": {"id": onx_id, "icon": onx_icon, "color": onx_color},
                }
            )

    # Tracks
    def read_track_like(track_elem: ET.Element, *, gpx_type: str, idx: int) -> Optional[Track]:
        name_elem = track_elem.find("gpx:name", _NS)
        name_raw = name_elem.text if name_elem is not None and name_elem.text else ""
        name = normalize_name(name_raw)

        desc_elem = track_elem.find("gpx:desc", _NS)
        desc_raw = desc_elem.text if desc_elem is not None and desc_elem.text else ""
        kv, notes = parse_onx_desc_kv(desc_raw)

        ext = track_elem.find("gpx:extensions", _NS)
        onx_color = _get_onx_extension_text(ext, "color") or kv.get("color")
        onx_style = _get_onx_extension_text(ext, "style") or kv.get("style")
        onx_weight = _get_onx_extension_text(ext, "weight") or kv.get("weight")
        onx_id = kv.get("id")

        points: List[TrackPoint] = []

        if gpx_type == "trk":
            for seg in track_elem.findall("gpx:trkseg", _NS):
                for pt in seg.findall("gpx:trkpt", _NS):
                    plat = float(pt.attrib.get("lat"))
                    plon = float(pt.attrib.get("lon"))
                    ele_elem = pt.find("gpx:ele", _NS)
                    ele = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None
                    time_elem = pt.find("gpx:time", _NS)
                    t_ms = iso8601_to_epoch_ms(time_elem.text) if time_elem is not None and time_elem.text else None
                    points.append((plon, plat, ele, t_ms))
        else:
            # Route: treat rtept as points (elevation often absent)
            for pt in track_elem.findall("gpx:rtept", _NS):
                plat = float(pt.attrib.get("lat"))
                plon = float(pt.attrib.get("lon"))
                ele_elem = pt.find("gpx:ele", _NS)
                ele = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None
                time_elem = pt.find("gpx:time", _NS)
                t_ms = iso8601_to_epoch_ms(time_elem.text) if time_elem is not None and time_elem.text else None
                points.append((plon, plat, ele, t_ms))

        if not points:
            return None

        style = Style(
            onx_color_rgba=onx_color,
            onx_style=onx_style,
            onx_weight=onx_weight,
            onx_id=onx_id,
        )
        style.extra["desc_kv"] = kv
        style.extra["gpx_type"] = gpx_type

        trk = Track(
            id=onx_id or _stable_uuid_fallback(),
            folder_id="onx_tracks",
            name=name,
            points=points,
            notes=normalize_name(notes) if notes else "",
            style=style,
            extra={"name_raw": name_raw, "desc_raw": desc_raw},
        )

        if trace is not None:
            trace.emit(
                {
                    "event": "input.trk" if gpx_type == "trk" else "input.rte",
                    "idx": idx,
                    "name_raw": name_raw,
                    "name_norm": name,
                    "point_count": len(points),
                    "onx": {
                        "id": onx_id,
                        "color": onx_color,
                        "style": onx_style,
                        "weight": onx_weight,
                    },
                }
            )

        return trk

    trk_idx = 0
    for trk in root.findall("gpx:trk", _NS):
        t = read_track_like(trk, gpx_type="trk", idx=trk_idx)
        if t is not None:
            doc.add_item(t)
        trk_idx += 1

    rte_idx = 0
    for rte in root.findall("gpx:rte", _NS):
        t = read_track_like(rte, gpx_type="rte", idx=rte_idx)
        if t is not None:
            doc.add_item(t)
        rte_idx += 1

    return doc

