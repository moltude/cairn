"""
Diagnostics helpers.

These are designed to make transformation debugging easy and reproducible,
especially when paired with JSONL trace logs.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from cairn.core.dedup import DedupReport
from cairn.model import MapDocument


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

