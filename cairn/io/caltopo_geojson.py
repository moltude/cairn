"""
CalTopo GeoJSON adapter.

Write a CalTopo-importable GeoJSON FeatureCollection from Cairn's MapDocument.

Important notes:
- CalTopo uses `class` in properties to indicate feature type:
  - Folder: class="Folder", geometry=null
  - Marker: class="Marker", geometry.type="Point"
  - Linework: class often "Shape" with geometry.type="LineString"
- CalTopo commonly uses hex colors with a leading '#', e.g. '#FF0000'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from cairn.core.color_mapper import ColorMapper
from cairn.model import Folder, MapDocument, Shape, Track, Waypoint


_ONX_ICON_TO_CALTOPO_SYMBOL: Dict[str, str] = {
    # Best-effort mapping. Unknown icons fall back to "point".
    "Location": "point",
    "Hazard": "danger",
    "Barrier": "danger",
    "Parking": "car",
    "Trailhead": "circle-p",
    "Water Source": "water",
    "Waterfall": "water",
    "Hot Spring": "water",
    "Potable Water": "water",
    "Campsite": "camp",
    "Camp": "camp",
    "Camp Backcountry": "camp",
    "Campground": "camp",
    "Summit": "peak",
    "Cabin": "hut",
    "Shelter": "hut",
    "Photo": "camera",
    "View": "star",
    # Some onX icons appear in exports directly
    "4x4": "car",
    "ATV": "car",
    "XC Skiing": "skiing",
    "Ski": "skiing",
    "Horseback": "horse-riding",
    "Cave": "cave",
}


def _rgba_to_caltopo_hex(rgba: Optional[str]) -> Optional[str]:
    if not rgba:
        return None
    r, g, b = ColorMapper.parse_color(rgba)
    return f"#{r:02X}{g:02X}{b:02X}"


def _map_onx_icon_to_caltopo_symbol(onx_icon: Optional[str]) -> str:
    icon = (onx_icon or "").strip()
    if not icon:
        return "point"
    return _ONX_ICON_TO_CALTOPO_SYMBOL.get(icon, "point")


def _build_description(
    *,
    title: str,
    notes: str,
    onx_id: Optional[str],
    onx_color: Optional[str],
    onx_icon: Optional[str],
    onx_style: Optional[str] = None,
    onx_weight: Optional[str] = None,
    source: str = "onx_gpx",
) -> str:
    lines: List[str] = []
    notes = (notes or "").strip()
    if notes:
        lines.append(notes)
        lines.append("")

    # Parseable metadata block.
    lines.append(f"cairn:source={source}")
    lines.append(f"name={title}")
    if onx_id:
        lines.append(f"onx:id={onx_id}")
    if onx_color:
        lines.append(f"onx:color={onx_color}")
    if onx_icon:
        lines.append(f"onx:icon={onx_icon}")
    if onx_style:
        lines.append(f"onx:style={onx_style}")
    if onx_weight:
        lines.append(f"onx:weight={onx_weight}")

    return "\n".join(lines).strip("\n")


def write_caltopo_geojson(doc: MapDocument, output_path: str | Path, *, trace: Any = None) -> Path:
    """
    Write CalTopo GeoJSON to output_path.
    """
    out = Path(output_path)
    features: List[Dict[str, Any]] = []

    # Write folders first (CalTopo exports folders as geometry=null features).
    for folder in doc.folders:
        features.append(
            {
                "type": "Feature",
                "id": folder.id,
                "geometry": None,
                "properties": {
                    "class": "Folder",
                    "title": folder.name,
                },
            }
        )
        if trace is not None:
            trace.emit({"event": "output.folder", "id": folder.id, "title": folder.name})

    # Items
    for item in doc.items:
        if isinstance(item, Waypoint):
            onx_color = item.style.onx_color_rgba
            onx_icon = item.style.onx_icon
            symbol = item.style.caltopo_marker_symbol or _map_onx_icon_to_caltopo_symbol(onx_icon)
            marker_color = item.style.caltopo_marker_color or _rgba_to_caltopo_hex(onx_color) or "#FF0000"
            desc = _build_description(
                title=item.name,
                notes=item.notes,
                onx_id=item.style.onx_id,
                onx_color=onx_color,
                onx_icon=onx_icon,
                source=str(doc.metadata.get("source", "onx_gpx")),
            )

            feat = {
                "type": "Feature",
                "id": item.id,
                "geometry": {"type": "Point", "coordinates": [item.lon, item.lat]},
                "properties": {
                    "class": "Marker",
                    "title": item.name,
                    "description": desc,
                    "marker-symbol": symbol,
                    "marker-color": marker_color,
                    "folderId": item.folder_id,
                },
            }
            features.append(feat)
            if trace is not None:
                trace.emit(
                    {
                        "event": "output.feature",
                        "feature_type": "Marker",
                        "id": item.id,
                        "folderId": item.folder_id,
                        "title": item.name,
                        "marker-symbol": symbol,
                        "marker-color": marker_color,
                    }
                )

        elif isinstance(item, Track):
            onx_color = item.style.onx_color_rgba
            stroke = item.style.caltopo_stroke or _rgba_to_caltopo_hex(onx_color) or "#0000FF"
            # Best-effort mapping from onX style/weight.
            pattern = item.style.caltopo_pattern or item.style.onx_style or "solid"
            stroke_width = item.style.caltopo_stroke_width or 2

            desc = _build_description(
                title=item.name,
                notes=item.notes,
                onx_id=item.style.onx_id,
                onx_color=onx_color,
                onx_icon=None,
                onx_style=item.style.onx_style,
                onx_weight=item.style.onx_weight,
                source=str(doc.metadata.get("source", "onx_gpx")),
            )

            # Preserve elevation/time if present anywhere.
            any_ele = any(p[2] is not None for p in item.points)
            any_time = any(p[3] is not None for p in item.points)
            coords: List[List[float]] = []
            for lon, lat, ele, t_ms in item.points:
                if any_ele or any_time:
                    coords.append([lon, lat, float(ele or 0.0), float(t_ms or 0)])
                else:
                    coords.append([lon, lat])

            feat = {
                "type": "Feature",
                "id": item.id,
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "class": "Shape",
                    "title": item.name,
                    "description": desc,
                    "stroke": stroke,
                    "stroke-width": stroke_width,
                    "pattern": pattern,
                    "folderId": item.folder_id,
                },
            }
            features.append(feat)
            if trace is not None:
                trace.emit(
                    {
                        "event": "output.feature",
                        "feature_type": "Shape",
                        "id": item.id,
                        "folderId": item.folder_id,
                        "title": item.name,
                        "stroke": stroke,
                        "stroke-width": stroke_width,
                        "pattern": pattern,
                        "point_count": len(coords),
                        "coord_dim": 4 if (any_ele or any_time) else 2,
                    }
                )

        elif isinstance(item, Shape):
            # Not currently produced by onX GPX ingest, but supported for completeness.
            stroke = item.style.caltopo_stroke or _rgba_to_caltopo_hex(item.style.onx_color_rgba) or "#00FF00"
            stroke_width = item.style.caltopo_stroke_width or 2
            pattern = item.style.caltopo_pattern or item.style.onx_style or "solid"
            desc = _build_description(
                title=item.name,
                notes=item.notes,
                onx_id=item.style.onx_id,
                onx_color=item.style.onx_color_rgba,
                onx_icon=item.style.onx_icon,
                source=str(doc.metadata.get("source", "onx_gpx")),
            )

            # GeoJSON polygon: list of rings, each ring list of [lon,lat]
            coords = [[[lon, lat] for (lon, lat) in ring] for ring in item.rings]
            feat = {
                "type": "Feature",
                "id": item.id,
                "geometry": {"type": "Polygon", "coordinates": coords},
                "properties": {
                    "class": "Shape",
                    "title": item.name,
                    "description": desc,
                    "stroke": stroke,
                    "stroke-width": stroke_width,
                    "pattern": pattern,
                    "folderId": item.folder_id,
                },
            }
            features.append(feat)
            if trace is not None:
                trace.emit(
                    {
                        "event": "output.feature",
                        "feature_type": "Polygon",
                        "id": item.id,
                        "folderId": item.folder_id,
                        "title": item.name,
                    }
                )

    fc = {"type": "FeatureCollection", "features": features}
    out.write_text(json.dumps(fc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out

