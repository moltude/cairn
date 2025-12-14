"""
Merge utilities for combining multiple inputs into a single MapDocument.

Primary use:
- Merge onX GPX + onX KML exports from the same onX dataset to recover
  more complete geometry (notably polygons from KML) while keeping track
  elevation/time when present in GPX tracks.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from cairn.model import MapDocument, Shape, Track, Waypoint


def merge_onx_gpx_and_kml(gpx: MapDocument, kml: MapDocument, *, trace: Any = None) -> MapDocument:
    """
    Merge KML-derived items into a GPX-derived document.

    Rules:
    - Start from GPX as the base.
    - Add KML items whose `style.onx_id` isn't present in GPX.
    - If the same onx_id exists with a different geometry class, keep both but
      record the conflict in `extra`.
    - Ensure the standard onX import folders exist (onx_shapes may be missing from GPX-only).
    """
    out = gpx

    out.ensure_folder("onx_import", "OnX Import")
    out.ensure_folder("onx_waypoints", "Waypoints", parent_id="onx_import")
    out.ensure_folder("onx_tracks", "Tracks", parent_id="onx_import")
    out.ensure_folder("onx_shapes", "Areas", parent_id="onx_import")

    by_onx_id: Dict[str, object] = {}
    for item in out.items:
        oid = (getattr(item, "style", None) and getattr(item.style, "onx_id", None)) or None
        if oid:
            by_onx_id[oid] = item

    for item in kml.items:
        oid = (getattr(item, "style", None) and getattr(item.style, "onx_id", None)) or None
        if not oid:
            out.items.append(item)
            if trace is not None:
                trace.emit({"event": "merge.add", "reason": "no_onx_id", "type": type(item).__name__})
            continue

        existing = by_onx_id.get(oid)
        if existing is None:
            out.items.append(item)
            by_onx_id[oid] = item
            if trace is not None:
                trace.emit({"event": "merge.add", "reason": "new_onx_id", "onx_id": oid, "type": type(item).__name__})
            continue

        # If same onx id but different geometry class:
        # Prefer Polygon/Shape for now to avoid CalTopo ID collisions and because onX areas
        # are best represented as polygons in CalTopo. We keep at most one item per onx id.
        if type(existing) is not type(item):
            # If either side is a polygon shape, keep the shape and drop the other.
            keep_shape: Shape | None = None
            drop_item: object | None = None
            if isinstance(existing, Shape):
                keep_shape = existing
                drop_item = item
            elif isinstance(item, Shape):
                keep_shape = item
                drop_item = existing

            if keep_shape is not None and drop_item is not None:
                # Transfer useful metadata from dropped item onto the kept shape.
                # (GPX Track often carries color/style/weight; keep it if polygon lacks it.)
                if isinstance(drop_item, Track):
                    if not (keep_shape.notes or "").strip() and (drop_item.notes or "").strip():
                        keep_shape.notes = drop_item.notes
                    if not (keep_shape.style.onx_color_rgba or "").strip() and (drop_item.style.onx_color_rgba or "").strip():
                        keep_shape.style.onx_color_rgba = drop_item.style.onx_color_rgba
                    if not (keep_shape.style.onx_style or "").strip() and (drop_item.style.onx_style or "").strip():
                        keep_shape.style.onx_style = drop_item.style.onx_style
                    if not (keep_shape.style.onx_weight or "").strip() and (drop_item.style.onx_weight or "").strip():
                        keep_shape.style.onx_weight = drop_item.style.onx_weight

                # Ensure kept shape is present in output items.
                if keep_shape is item:
                    out.items.append(keep_shape)
                    by_onx_id[oid] = keep_shape

                # Remove the dropped item from output if it was already present.
                if drop_item in out.items:
                    out.items = [x for x in out.items if x is not drop_item]

                # Record decision in extras.
                keep_shape.extra.setdefault("merge_decisions", []).append(
                    {"onx_id": oid, "action": "prefer_polygon", "dropped": type(drop_item).__name__}
                )

                if trace is not None:
                    trace.emit(
                        {
                            "event": "merge.prefer_polygon",
                            "onx_id": oid,
                            "kept_type": "Shape",
                            "dropped_type": type(drop_item).__name__,
                        }
                    )
                continue

            # Otherwise, fall back: keep existing (GPX) and ignore this KML item.
            existing.extra.setdefault("merge_conflicts", []).append(
                {"onx_id": oid, "ignored_kml_type": type(item).__name__}
            )
            if trace is not None:
                trace.emit(
                    {
                        "event": "merge.ignore",
                        "onx_id": oid,
                        "kept_type": type(existing).__name__,
                        "ignored_type": type(item).__name__,
                    }
                )
            continue

        # Same type and same onx id: prefer GPX for Tracks (may contain time/ele),
        # but enrich notes/icon/color if missing.
        if isinstance(item, Track) and isinstance(existing, Track):
            if not (existing.notes or "").strip() and (item.notes or "").strip():
                existing.notes = item.notes
            if not (existing.style.onx_color_rgba or "").strip() and (item.style.onx_color_rgba or "").strip():
                existing.style.onx_color_rgba = item.style.onx_color_rgba
            continue

        if isinstance(item, Waypoint) and isinstance(existing, Waypoint):
            if not (existing.notes or "").strip() and (item.notes or "").strip():
                existing.notes = item.notes
            if not (existing.style.onx_icon or "").strip() and (item.style.onx_icon or "").strip():
                existing.style.onx_icon = item.style.onx_icon
            if not (existing.style.onx_color_rgba or "").strip() and (item.style.onx_color_rgba or "").strip():
                existing.style.onx_color_rgba = item.style.onx_color_rgba
            continue

        if isinstance(item, Shape) and isinstance(existing, Shape):
            # Shapes usually only exist in KML; if present in both, keep GPX but merge rings if missing.
            if not existing.rings and item.rings:
                existing.rings = item.rings
            continue

    # Prefer base metadata but record that a merge occurred.
    out.metadata = dict(out.metadata)
    out.metadata["merged_kml"] = True
    out.metadata["kml_path"] = str(kml.metadata.get("path", ""))
    return out
