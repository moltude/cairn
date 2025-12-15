"""
OnX Backcountry GPX adapter.

Reads an OnX-exported GPX file into Cairn's canonical MapDocument model.

Notes:
- OnX exports often include a key/value block in <desc> for both waypoints and tracks.
- OnX also includes custom extensions in namespace https://wwww.OnXmaps.com/
- OnX GPX export structure can vary (tracks vs routes), so we read <trk> and <rte>.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re
import uuid
import xml.etree.ElementTree as ET

from cairn.core.normalization import iso8601_to_epoch_ms, normalize_name
from cairn.model import MapDocument, Style, Track, TrackPoint, Waypoint


_OnX_NS = "https://wwww.OnXmaps.com/"
_GPX_NS = "http://www.topografix.com/GPX/1/1"
_NS = {"gpx": _GPX_NS, "OnX": _OnX_NS}


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


def parse_OnX_desc_kv(desc_text: str) -> Tuple[Dict[str, str], str]:
    """
    Parse an OnX <desc> key/value block.

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


def _get_OnX_extension_text(elem: ET.Element, local_name: str) -> Optional[str]:
    """
    Read OnX extension element by local name from an <extensions> element.
    """
    if elem is None:
        return None
    child = elem.find(f"OnX:{local_name}", _NS)
    if child is not None and child.text:
        return child.text.strip()
    return None


def read_OnX_gpx(path: str | Path, *, trace: Any = None) -> MapDocument:
    """
    Read an OnX GPX export.

    Args:
      path: path to GPX
      trace: optional TraceWriter-like object with `emit(event: dict)` method

    Raises:
      ValueError: If the file is not a valid GPX file or is empty
    """
    p = Path(path)

    # Validate file is not empty
    if p.stat().st_size == 0:
        raise ValueError(f"GPX file is empty: {p}")

    # Parse XML with error handling
    try:
        tree = ET.parse(p)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"Invalid GPX file (XML parse error): {e}\nFile: {p}")
    except Exception as e:
        raise ValueError(f"Failed to read GPX file: {e}\nFile: {p}")

    # Validate it's actually a GPX file
    if not (root.tag.endswith("gpx") or "gpx" in root.tag.lower()):
        raise ValueError(f"File does not appear to be a GPX file (root element: {root.tag})\nFile: {p}")

    doc = MapDocument(metadata={"source": "OnX_gpx", "path": str(p)})

    # Default folder structure (value-add for CalTopo)
    doc.ensure_folder("OnX_import", "OnX Import")
    doc.ensure_folder("OnX_waypoints", "Waypoints", parent_id="OnX_import")
    doc.ensure_folder("OnX_tracks", "Tracks", parent_id="OnX_import")

    # Waypoints
    for idx, wpt in enumerate(root.findall("gpx:wpt", _NS)):
        try:
            lat = float(wpt.attrib.get("lat"))
            lon = float(wpt.attrib.get("lon"))
        except (ValueError, TypeError) as e:
            # Skip waypoint with invalid coordinates but continue processing
            if trace is not None:
                trace.emit({
                    "event": "input.wpt.error",
                    "idx": idx,
                    "error": f"Invalid coordinates: {e}",
                    "lat_raw": wpt.attrib.get("lat"),
                    "lon_raw": wpt.attrib.get("lon"),
                })
            continue

        # Validate coordinate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            if trace is not None:
                trace.emit({
                    "event": "input.wpt.warning",
                    "idx": idx,
                    "warning": "Coordinates out of valid range",
                    "lat": lat,
                    "lon": lon,
                })
            # Continue processing but log the warning
            continue

        name_elem = wpt.find("gpx:name", _NS)
        name_raw = name_elem.text if name_elem is not None and name_elem.text else ""
        name = normalize_name(name_raw)

        desc_elem = wpt.find("gpx:desc", _NS)
        desc_raw = desc_elem.text if desc_elem is not None and desc_elem.text else ""
        kv, notes = parse_OnX_desc_kv(desc_raw)

        ext = wpt.find("gpx:extensions", _NS)
        OnX_color = _get_OnX_extension_text(ext, "color") or kv.get("color")
        OnX_icon = _get_OnX_extension_text(ext, "icon") or kv.get("icon")
        OnX_id = kv.get("id")

        style = Style(OnX_icon=OnX_icon, OnX_color_rgba=OnX_color, OnX_id=OnX_id)
        style.extra["desc_kv"] = kv

        wp = Waypoint(
            id=OnX_id or _stable_uuid_fallback(),
            folder_id="OnX_waypoints",
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
                    "OnX": {"id": OnX_id, "icon": OnX_icon, "color": OnX_color},
                }
            )

    # Tracks
    def read_track_like(track_elem: ET.Element, *, gpx_type: str, idx: int) -> Optional[Track]:
        name_elem = track_elem.find("gpx:name", _NS)
        name_raw = name_elem.text if name_elem is not None and name_elem.text else ""
        name = normalize_name(name_raw)

        desc_elem = track_elem.find("gpx:desc", _NS)
        desc_raw = desc_elem.text if desc_elem is not None and desc_elem.text else ""
        kv, notes = parse_OnX_desc_kv(desc_raw)

        ext = track_elem.find("gpx:extensions", _NS)
        OnX_color = _get_OnX_extension_text(ext, "color") or kv.get("color")
        OnX_style = _get_OnX_extension_text(ext, "style") or kv.get("style")
        OnX_weight = _get_OnX_extension_text(ext, "weight") or kv.get("weight")
        OnX_id = kv.get("id")

        points: List[TrackPoint] = []

        if gpx_type == "trk":
            for seg in track_elem.findall("gpx:trkseg", _NS):
                for pt in seg.findall("gpx:trkpt", _NS):
                    try:
                        plat = float(pt.attrib.get("lat"))
                        plon = float(pt.attrib.get("lon"))
                        # Skip invalid coordinates
                        if not (-90 <= plat <= 90) or not (-180 <= plon <= 180):
                            continue
                    except (ValueError, TypeError):
                        continue  # Skip invalid point

                    ele_elem = pt.find("gpx:ele", _NS)
                    try:
                        ele = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None
                    except (ValueError, TypeError):
                        ele = None

                    time_elem = pt.find("gpx:time", _NS)
                    t_ms = iso8601_to_epoch_ms(time_elem.text) if time_elem is not None and time_elem.text else None
                    points.append((plon, plat, ele, t_ms))
        else:
            # Route: treat rtept as points (elevation often absent)
            for pt in track_elem.findall("gpx:rtept", _NS):
                try:
                    plat = float(pt.attrib.get("lat"))
                    plon = float(pt.attrib.get("lon"))
                    # Skip invalid coordinates
                    if not (-90 <= plat <= 90) or not (-180 <= plon <= 180):
                        continue
                except (ValueError, TypeError):
                    continue  # Skip invalid point

                ele_elem = pt.find("gpx:ele", _NS)
                try:
                    ele = float(ele_elem.text) if ele_elem is not None and ele_elem.text else None
                except (ValueError, TypeError):
                    ele = None

                time_elem = pt.find("gpx:time", _NS)
                t_ms = iso8601_to_epoch_ms(time_elem.text) if time_elem is not None and time_elem.text else None
                points.append((plon, plat, ele, t_ms))

        if not points:
            return None

        style = Style(
            OnX_color_rgba=OnX_color,
            OnX_style=OnX_style,
            OnX_weight=OnX_weight,
            OnX_id=OnX_id,
        )
        style.extra["desc_kv"] = kv
        style.extra["gpx_type"] = gpx_type

        trk = Track(
            id=OnX_id or _stable_uuid_fallback(),
            folder_id="OnX_tracks",
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
                    "OnX": {
                        "id": OnX_id,
                        "color": OnX_color,
                        "style": OnX_style,
                        "weight": OnX_weight,
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
