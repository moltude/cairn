# Web engine: imported by web/bridge.py and run in the browser via Pyodide.
# Keep it free of terminal/UI imports (tests/test_web_engine_surface.py).
"""MapDocument -> ParsedData: the one bridge between the onX readers and the writers.

The onX readers (``read_onx_gpx``, ``read_onx_kml``, ``merge_onx_gpx_and_kml``)
return Cairn's canonical ``MapDocument``. The web bridge and the GPX/KML writers
work on CalTopo-shaped ``ParsedData``/``ParsedFeature``. ``to_parsed_data``
converts one into the other (roadmap Phase 2; KG section 6's adapter plus
folder handling, section 5.2).

- **Folders.** The readers' hard-coded ``OnX Import/Waypoints/Tracks/Areas``
  scaffold is ignored: an onX export carries no folders (FM; KG section 2), so
  the scaffold is invented structure. The whole document becomes ONE folder,
  named by the caller from the input file's stem, as ``parse_caltopo_gpx``
  already does.
- **Kinds.** Waypoint -> ``waypoints``, Track -> ``tracks``, Shape ->
  ``shapes``, in document order, so the bridge's ``"<folder>::<kind>::<index>"``
  uid still decodes to a position in each list.
- **Styling is carried, not re-guessed** (KG section 5.3). onX's own rgba goes
  into ``marker-color``/``stroke``, the icon into ``cairn_onx_icon_override``
  (the waypoint writer reads it first), ``OnX_style`` into ``pattern`` and
  ``OnX_weight`` into ``stroke-width``. The fill colour's alpha becomes
  ``fill-opacity``.
- **Kept in memory only.** The onX id (``properties["cairn_onx_id"]`` and the
  feature id) and the sub-kind (``properties["cairn_onx_kind"]``: ``line``,
  ``track`` or ``area``). No writer emits either yet: writing the id back is
  roadmap Phase 6, pending probe P1.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from cairn.core.parser import ParsedData, ParsedFeature
from cairn.model import MapDocument, Shape, Track, Waypoint

# onX weight -> the stroke-width the writers' stroke_width_to_weight reads back.
# "2.0" (thin) still comes back as "4.0": the thin bucket is roadmap Phase 1
# item 5, an owner decision.
_WEIGHT_TO_WIDTH = {"2.0": 2, "4.0": 4, "6.0": 6}
_DEFAULT_WIDTH = 4

_ALPHA_RE = re.compile(
    r"rgba\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*,\s*([\d.]+)\s*\)", re.IGNORECASE
)

ONX_ID_KEY = "cairn_onx_id"
ONX_KIND_KEY = "cairn_onx_kind"
ONX_ICON_KEY = "cairn_onx_icon_override"


def _alpha(rgba: Optional[str]) -> Optional[float]:
    m = _ALPHA_RE.match((rgba or "").strip())
    return float(m.group(1)) if m else None


def sub_kind(item: Any) -> str:
    """``line``, ``track`` or ``area`` (``waypoint`` for a Waypoint)."""
    if isinstance(item, Waypoint):
        return "waypoint"
    if isinstance(item, Shape):
        return "area"
    return "line" if item.extra.get("onx_kind") == "line" else "track"


def to_parsed_feature(item: Any) -> ParsedFeature:
    """One MapDocument item as the ParsedFeature the bridge and writers read."""
    s = item.style
    props: Dict[str, Any] = {"title": item.name, "description": item.notes}
    if isinstance(item, Waypoint):
        props.update({
            "class": "Marker",
            "marker-color": s.OnX_color_rgba or "",
            "marker-symbol": "",
        })
        if (s.OnX_icon or "").strip():
            props[ONX_ICON_KEY] = s.OnX_icon.strip()
        geom = {"type": "Point", "coordinates": [item.lon, item.lat]}
    else:
        props.update({
            "class": "Shape",
            "stroke": s.OnX_color_rgba or "",
            "stroke-width": _WEIGHT_TO_WIDTH.get((s.OnX_weight or "").strip(), _DEFAULT_WIDTH),
            "pattern": s.OnX_style or "solid",
        })
        if isinstance(item, Track):
            # All four slots [lon, lat, ele, epoch_ms]: the track writer skips a
            # None elevation and writes <time> for a positive time.
            geom = {"type": "LineString", "coordinates": [list(p) for p in item.points]}
        else:
            alpha = _alpha(s.extra.get("fill_color"))
            if alpha is not None:
                props["fill-opacity"] = alpha
            geom = {"type": "Polygon",
                    "coordinates": [[list(p) for p in ring] for ring in item.rings]}
    if s.OnX_id:
        props[ONX_ID_KEY] = s.OnX_id
    props[ONX_KIND_KEY] = sub_kind(item)
    return ParsedFeature({"id": item.id, "geometry": geom, "properties": props})


def to_parsed_data(
    doc: MapDocument, folder_name: str, folder_key: str = "default"
) -> ParsedData:
    """The whole document as ONE folder named ``folder_name`` (see module doc)."""
    parsed = ParsedData()
    parsed.add_folder(folder_key, folder_name)
    folder = parsed.folders[folder_key]
    for item in doc.items:
        kind = ("waypoints" if isinstance(item, Waypoint)
                else "shapes" if isinstance(item, Shape) else "tracks")
        folder[kind].append(to_parsed_feature(item))
    return parsed
