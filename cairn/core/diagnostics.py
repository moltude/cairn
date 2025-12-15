"""
Diagnostics helpers.

These are designed to make transformation debugging easy and reproducible,
especially when paired with JSONL trace logs.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from cairn.core.dedup import DedupReport
from cairn.model import MapDocument, Track, Waypoint


def document_inventory(doc: MapDocument) -> Dict[str, Any]:
    return {
        "folder_count": len(doc.folders),
        "waypoint_count": len(doc.waypoints()),
        "track_count": len(doc.tracks()),
        "shape_count": len(doc.shapes()),
        "item_count": len(doc.items),
        "metadata": dict(doc.metadata),
    }


def dedup_inventory(report: DedupReport) -> Dict[str, Any]:
    return {
        "dedup_group_count": report.group_count,
        "dedup_dropped_count": report.dropped_count,
        "groups": [
            {
                "key": {"name": g.key.name_key, "lat6": g.key.lat6, "lon6": g.key.lon6},
                "kept_id": g.kept_id,
                "dropped_ids": list(g.dropped_ids),
                "reason": g.reason,
                "conflicts": g.conflicts,
            }
            for g in report.groups
        ],
    }


def check_data_quality(doc: MapDocument) -> Dict[str, Any]:
    """
    Check data quality and return warnings.

    Returns a dict with:
    - empty_names: list of (item_type, item_id, name) with empty/default names
    - duplicate_names: list of (name, count, items) for names appearing multiple times
    - suspicious_coords: list of (item_type, item_id, name, lat, lon, reason) with suspicious coordinates
    """
    warnings: Dict[str, Any] = {
        "empty_names": [],
        "duplicate_names": [],
        "suspicious_coords": [],
        "empty_tracks": [],
    }

    # Check for empty or default names
    for item in doc.items:
        name = getattr(item, "name", "")
        if not name or name.lower() in ["untitled", "unnamed", ""]:
            item_type = type(item).__name__
            item_id = getattr(item, "id", "unknown")
            warnings["empty_names"].append((item_type, item_id, name or "(empty)"))

    # Check for duplicate names (potential duplicates before dedup)
    name_counts: Dict[str, List[Tuple[str, str]]] = {}  # name -> [(type, id)]
    for item in doc.items:
        name = getattr(item, "name", "")
        if name:
            item_type = type(item).__name__
            item_id = getattr(item, "id", "unknown")
            if name not in name_counts:
                name_counts[name] = []
            name_counts[name].append((item_type, item_id))

    for name, items in name_counts.items():
        if len(items) > 1:
            warnings["duplicate_names"].append((name, len(items), items[:3]))  # Show first 3

    # Check for suspicious coordinates (e.g., exactly 0,0 or very close)
    for item in doc.items:
        if isinstance(item, Waypoint):
            lat, lon = item.lat, item.lon
            # Check for null island (0, 0) or very close
            if abs(lat) < 0.001 and abs(lon) < 0.001:
                warnings["suspicious_coords"].append((
                    "Waypoint",
                    item.id,
                    item.name,
                    lat,
                    lon,
                    "Near (0,0) - possible default/invalid coordinate"
                ))
            # Check for out-of-range coordinates
            if not (-90 <= float(lat) <= 90) or not (-180 <= float(lon) <= 180):
                warnings["suspicious_coords"].append((
                    "Waypoint",
                    item.id,
                    item.name,
                    lat,
                    lon,
                    "Out of valid range (-90..90, -180..180)"
                ))
        elif isinstance(item, Track):
            if not getattr(item, "points", None):
                warnings["empty_tracks"].append((item.id, item.name))

    return warnings
