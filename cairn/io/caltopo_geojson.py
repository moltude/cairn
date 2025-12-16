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
from typing import Any, Dict, List, Literal, Optional, Tuple
import hashlib
import json

from cairn.core.color_mapper import ColorMapper
from cairn.core.icon_registry import IconRegistry
from cairn.model import MapDocument, Shape, Track, Waypoint


_OnX_ICON_TO_CALTOPO_SYMBOL: Dict[str, str] = {
    # Best-effort mapping. Unknown icons fall back to "point".
    "Location": "point",
    "Hazard": "danger",
    "Barrier": "danger",
    # Vehicles / access
    "Parking": "automobile",
    "Trailhead": "circle-p",
    "4x4": "automobile",
    "ATV": "automobile",
    "Car": "automobile",
    # Water
    # CalTopo’s symbol set differs from OnX; `repair-streamcrossing` is a close, widely-supported icon.
    "Water Source": "repair-streamcrossing",
    "Waterfall": "repair-streamcrossing",
    "Hot Spring": "repair-streamcrossing",
    "Potable Water": "repair-streamcrossing",
    # Camping
    "Campsite": "camping",
    "Camp": "camping",
    "Camp Backcountry": "camping",
    "Campground": "camping",
    "Summit": "peak",
    "Cabin": "hut",
    "Shelter": "hut",
    "House": "hut",
    # Camera/star aren’t present in our CalTopo exports; use a safe, non-default icon.
    "Photo": "flag-1",
    "View": "flag-1",
    # Winter
    "XC Skiing": "snowboarding",
    "Ski": "snowboarding",
    "Snowboarder": "snowboarding",
    # Activities
    "Climbing": "climbing-2",
    "Scrambling": "scrambling",
    # Other
    "Horseback": "point",
    "Cave": "cave",
}


def _rgba_to_caltopo_hex(rgba: Optional[str]) -> Optional[str]:
    if not rgba:
        return None
    r, g, b = ColorMapper.parse_color(rgba)
    return f"#{r:02X}{g:02X}{b:02X}"


_ICON_REGISTRY: Optional[IconRegistry] = None


def _get_icon_registry() -> Optional[IconRegistry]:
    """
    Best-effort load of the repo-versioned icon registry.

    This should never crash conversion; if the YAML cannot be loaded (e.g. in a
    stripped-down environment), we fall back to the legacy in-module mapping.
    """
    global _ICON_REGISTRY
    if _ICON_REGISTRY is not None:
        return _ICON_REGISTRY
    try:
        _ICON_REGISTRY = IconRegistry()
        return _ICON_REGISTRY
    except Exception:
        return None


def _map_onx_icon_to_caltopo_symbol(
    onx_icon: Optional[str],
) -> Tuple[Optional[str], str]:
    """
    Returns:
      (mapped_symbol_or_None, mapping_source)

    mapping_source is one of: 'direct', 'default', 'legacy'
    """
    icon = (onx_icon or "").strip()
    reg = _get_icon_registry()
    if reg is not None:
        symbol, src = reg.map_onx_icon_to_caltopo_symbol(icon or None)
        return (symbol or None), src
    if not icon:
        return None, "legacy"
    return _OnX_ICON_TO_CALTOPO_SYMBOL.get(icon), "legacy"


DescriptionMode = Literal["notes_only", "debug"]
RouteColorStrategy = Literal["palette", "default_blue", "none"]

# A small, high-contrast set. Chosen to look good on topo and satellite bases.
_ROUTE_COLOR_PALETTE: List[str] = [
    "#FFAA00",  # orange
    "#4CB36E",  # green
    "#EF00FF",  # magenta
    "#00CD00",  # bright green
    "#C659A9",  # purple
    "#B9AC91",  # tan
    "#FF0000",  # red
    "#000000",  # black
    "#00A3FF",  # azure
    "#8B4513",  # brown
]


def _stable_palette_color(name: str, palette: List[str] = _ROUTE_COLOR_PALETTE) -> str:
    """
    Pick a deterministic color from a palette based on a name.
    """
    n = (name or "").strip().lower()
    if not n:
        return palette[0]
    digest = hashlib.md5(n.encode("utf-8")).digest()
    idx = int.from_bytes(digest[:4], "big") % len(palette)
    return palette[idx]


def _build_description(
    *,
    title: str,
    notes: str,
    onx_id: Optional[str],
    onx_color: Optional[str],
    onx_icon: Optional[str],
    onx_style: Optional[str] = None,
    onx_weight: Optional[str] = None,
    source: str = "OnX_gpx",
    mode: DescriptionMode = "notes_only",
) -> str:
    notes_clean = (notes or "").strip()
    if mode == "notes_only":
        return notes_clean

    lines: List[str] = []
    if notes_clean:
        lines.append(notes_clean)
        lines.append("")

    # Parseable metadata block.
    lines.append(f"cairn:source={source}")
    lines.append(f"name={title}")
    if onx_id:
        lines.append(f"OnX:id={onx_id}")
    if onx_color:
        lines.append(f"OnX:color={onx_color}")
    if onx_icon:
        lines.append(f"OnX:icon={onx_icon}")
    if onx_style:
        lines.append(f"OnX:style={onx_style}")
    if onx_weight:
        lines.append(f"OnX:weight={onx_weight}")

    return "\n".join(lines).strip("\n")


def _build_cairn_metadata(
    *,
    title: str,
    source: str,
    onx_id: Optional[str],
    onx_color: Optional[str],
    onx_icon: Optional[str],
    onx_style: Optional[str] = None,
    onx_weight: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Structured metadata preserved for downstream tooling.
    CalTopo will ignore unknown fields, but we keep provenance for round-trips.
    """
    onx: Dict[str, Any] = {}
    if onx_id:
        onx["id"] = onx_id
    if onx_color:
        onx["color"] = onx_color
    if onx_icon:
        onx["icon"] = onx_icon
    if onx_style:
        onx["style"] = onx_style
    if onx_weight:
        onx["weight"] = onx_weight

    meta: Dict[str, Any] = {"source": source, "name": title}
    if onx:
        meta["OnX"] = onx
    return meta


def write_caltopo_geojson(
    doc: MapDocument,
    output_path: str | Path,
    *,
    trace: Any = None,
    description_mode: DescriptionMode = "notes_only",
    route_color_strategy: RouteColorStrategy = "palette",
) -> Path:
    """
    Write CalTopo GeoJSON to output_path.
    """
    out = Path(output_path)
    features: List[Dict[str, Any]] = []

    # Write folders first (CalTopo exports folders as geometry=null features).
    for folder in doc.folders:
        # This is a convenience root folder we create for internal organization.
        # CalTopo doesn't need it, and it shows up empty because no item has folderId=OnX_import.
        if folder.id == "OnX_import":
            continue
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
            trace.emit(
                {"event": "output.folder", "id": folder.id, "title": folder.name}
            )

    # Items
    for item in doc.items:
        if isinstance(item, Waypoint):
            onx_color = item.style.OnX_color_rgba
            onx_icon = item.style.OnX_icon
            mapped_symbol, mapping_source = _map_onx_icon_to_caltopo_symbol(onx_icon)
            symbol = item.style.caltopo_marker_symbol or mapped_symbol or "point"

            # User preference: if we can't determine an icon, use a dot but keep the provided color.
            # Only fall back to a red dot if neither icon nor color is available.
            marker_color = (
                item.style.caltopo_marker_color
                or _rgba_to_caltopo_hex(onx_color)
                or "#FF0000"
            )
            desc = _build_description(
                title=item.name,
                notes=item.notes,
                onx_id=item.style.OnX_id,
                onx_color=onx_color,
                onx_icon=onx_icon,
                source=str(doc.metadata.get("source", "OnX_gpx")),
                mode=description_mode,
            )

            # If the icon is unknown (not mapped) and we're in notes-only mode, preserve the
            # original OnX icon name in the human-visible description for manual recovery.
            reg = _get_icon_registry()
            unknown_icon_policy = (
                reg.policies.get("unknown_icon_handling") if reg is not None else None
            )
            if (
                description_mode == "notes_only"
                and (onx_icon or "").strip()
                and mapping_source != "direct"
                and item.style.caltopo_marker_symbol is None
                and (
                    unknown_icon_policy
                    in (None, "keep_point_and_append_to_description")
                )
            ):
                # Avoid adding noise if it's already present.
                token = f"OnX icon: {onx_icon}".strip()
                if token and token not in desc:
                    desc = (desc + ("\n\n" if desc else "") + token).strip()
            cairn_meta = _build_cairn_metadata(
                title=item.name,
                source=str(doc.metadata.get("source", "OnX_gpx")),
                onx_id=item.style.OnX_id,
                onx_color=onx_color,
                onx_icon=onx_icon,
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
                    "cairn": cairn_meta,
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
                        "icon_mapping_source": mapping_source,
                    }
                )

        elif isinstance(item, Track):
            onx_color = item.style.OnX_color_rgba
            stroke: Optional[str] = item.style.caltopo_stroke or _rgba_to_caltopo_hex(
                onx_color
            )
            if not stroke:
                if route_color_strategy == "palette":
                    stroke = _stable_palette_color(item.name)
                elif route_color_strategy == "default_blue":
                    stroke = "#0000FF"
                else:
                    stroke = None
            # Best-effort mapping from OnX style/weight.
            pattern = item.style.caltopo_pattern or item.style.OnX_style or "solid"
            stroke_width = item.style.caltopo_stroke_width or 2

            desc = _build_description(
                title=item.name,
                notes=item.notes,
                onx_id=item.style.OnX_id,
                onx_color=onx_color,
                onx_icon=None,
                onx_style=item.style.OnX_style,
                onx_weight=item.style.OnX_weight,
                source=str(doc.metadata.get("source", "OnX_gpx")),
                mode=description_mode,
            )
            cairn_meta = _build_cairn_metadata(
                title=item.name,
                source=str(doc.metadata.get("source", "OnX_gpx")),
                onx_id=item.style.OnX_id,
                onx_color=onx_color,
                onx_icon=None,
                onx_style=item.style.OnX_style,
                onx_weight=item.style.OnX_weight,
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
                    "stroke-width": stroke_width,
                    "pattern": pattern,
                    "folderId": item.folder_id,
                    "cairn": cairn_meta,
                },
            }
            if stroke is not None:
                feat["properties"]["stroke"] = stroke
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
            # Not currently produced by OnX GPX ingest, but supported for completeness.
            onx_color = item.style.OnX_color_rgba
            stroke: Optional[str] = item.style.caltopo_stroke or _rgba_to_caltopo_hex(
                onx_color
            )
            if not stroke:
                if route_color_strategy == "palette":
                    stroke = _stable_palette_color(item.name)
                elif route_color_strategy == "default_blue":
                    stroke = "#0000FF"
                else:
                    stroke = None
            stroke_width = item.style.caltopo_stroke_width or 2
            pattern = item.style.caltopo_pattern or item.style.OnX_style or "solid"
            desc = _build_description(
                title=item.name,
                notes=item.notes,
                onx_id=item.style.OnX_id,
                onx_color=onx_color,
                onx_icon=item.style.OnX_icon,
                source=str(doc.metadata.get("source", "OnX_gpx")),
                mode=description_mode,
            )
            cairn_meta = _build_cairn_metadata(
                title=item.name,
                source=str(doc.metadata.get("source", "OnX_gpx")),
                onx_id=item.style.OnX_id,
                onx_color=onx_color,
                onx_icon=item.style.OnX_icon,
                onx_style=item.style.OnX_style,
                onx_weight=item.style.OnX_weight,
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
                    "stroke-width": stroke_width,
                    "pattern": pattern,
                    "folderId": item.folder_id,
                    "cairn": cairn_meta,
                },
            }
            if stroke is not None:
                feat["properties"]["stroke"] = stroke
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
    out.write_text(
        json.dumps(fc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out
