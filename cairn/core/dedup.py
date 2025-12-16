"""
Deduplication utilities.

Primary goal: collapse duplicate items that arise from OnX export variance or
user workflows that cause repeated elements to appear with different IDs but the
same location/name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from cairn.core.normalization import normalize_key
from cairn.model import MapDocument, Waypoint


@dataclass(frozen=True)
class DedupKey:
    name_key: str
    lat6: float
    lon6: float


@dataclass
class DedupGroupReport:
    key: DedupKey
    kept_id: str
    dropped_ids: List[str]
    reason: str
    conflicts: Dict[str, Any]


@dataclass
class DedupReport:
    groups: List[DedupGroupReport]

    @property
    def dropped_count(self) -> int:
        return sum(len(g.dropped_ids) for g in self.groups)

    @property
    def group_count(self) -> int:
        return len(self.groups)


def waypoint_dedup_key(wp: Waypoint) -> DedupKey:
    return DedupKey(
        name_key=normalize_key(wp.name),
        lat6=round(float(wp.lat), 6),
        lon6=round(float(wp.lon), 6),
    )


def _waypoint_score(wp: Waypoint) -> Tuple[int, int, int]:
    """
    Calculate a score for waypoint quality to determine which duplicate to keep.

    Higher scores are better. Scoring criteria (in order of importance):
    1. Total metadata presence (icon + color): Prefer waypoints with both
    2. Icon presence: Prefer waypoints with an OnX icon
    3. Notes length: Prefer waypoints with longer descriptions

    Args:
        wp: Waypoint to score

    Returns:
        Tuple of (total_metadata, has_icon, notes_length) for comparison
    """
    has_icon = 1 if (wp.style.OnX_icon or "").strip() else 0
    has_color = 1 if (wp.style.OnX_color_rgba or "").strip() else 0
    notes_len = len((wp.notes or "").strip())
    return (has_icon + has_color, has_icon, notes_len)


def dedupe_waypoints(
    waypoints: List[Waypoint],
    *,
    trace: Any = None,
) -> Tuple[List[Waypoint], List[Waypoint], DedupReport]:
    """
    Deduplicate waypoints by (rounded lat/lon + normalized name).

    Algorithm:
    1. Group waypoints by normalized name + lat/lon rounded to 6 decimals (~0.1m precision)
    2. For each group with duplicates, select the "best" waypoint using scoring:
       - Prefer waypoints with OnX icon + color (more complete metadata)
       - Prefer waypoints with longer notes
    3. Merge source IDs from dropped waypoints into kept waypoint for traceability
    4. Track conflicts (different icons/colors within a group) in waypoint.extra

    Args:
        waypoints: List of waypoints to deduplicate
        trace: Optional trace context for debugging

    Returns:
        Tuple of (kept_waypoints, dropped_waypoints, dedup_report)

    Example:
        >>> kept, dropped, report = dedupe_waypoints(all_waypoints)
        >>> print(f"Kept {len(kept)}, dropped {len(dropped)} duplicates")
        >>> print(f"Found {report.group_count} duplicate groups")

    Notes:
        - Coordinates are rounded to 6 decimal places (~0.1 meter precision)
        - Name matching is case-insensitive and removes special characters
        - Source IDs are preserved for forensic analysis
    """
    groups: Dict[DedupKey, List[Waypoint]] = {}
    for wp in waypoints:
        k = waypoint_dedup_key(wp)
        groups.setdefault(k, []).append(wp)

    kept: List[Waypoint] = []
    dropped: List[Waypoint] = []
    reports: List[DedupGroupReport] = []

    for key, members in groups.items():
        if len(members) == 1:
            kept.append(members[0])
            continue

        # Determine a canonical waypoint.
        best = members[0]
        best_score = _waypoint_score(best)
        for wp in members[1:]:
            sc = _waypoint_score(wp)
            if sc > best_score:
                best = wp
                best_score = sc

        conflicts: Dict[str, Any] = {}
        icons = sorted(
            {
                (m.style.OnX_icon or "").strip()
                for m in members
                if (m.style.OnX_icon or "").strip()
            }
        )
        colors = sorted(
            {
                (m.style.OnX_color_rgba or "").strip()
                for m in members
                if (m.style.OnX_color_rgba or "").strip()
            }
        )
        if len(icons) > 1:
            conflicts["OnX_icons"] = icons
        if len(colors) > 1:
            conflicts["OnX_colors"] = colors

        # Merge source IDs into the kept waypoint for forensic traceability.
        for wp in members:
            if wp is best:
                continue
            dropped.append(wp)
            if wp.id and wp.id != best.id:
                if wp.id not in best.source_ids:
                    best.source_ids.append(wp.id)
            for sid in wp.source_ids:
                if sid not in best.source_ids and sid != best.id:
                    best.source_ids.append(sid)

        if conflicts:
            best.extra.setdefault("dedup_conflicts", conflicts)

        dropped_ids = [m.id for m in members if m is not best]
        report = DedupGroupReport(
            key=key,
            kept_id=best.id,
            dropped_ids=dropped_ids,
            reason="prefer_has_OnX_style_or_notes",
            conflicts=conflicts,
        )
        reports.append(report)
        kept.append(best)

        if trace is not None:
            trace.emit(
                {
                    "event": "dedup.group",
                    "key": {"name": key.name_key, "lat6": key.lat6, "lon6": key.lon6},
                    "member_ids": [m.id for m in members],
                    "kept_id": best.id,
                    "dropped_ids": dropped_ids,
                    "conflicts": conflicts,
                }
            )

    return kept, dropped, DedupReport(groups=reports)


def apply_waypoint_dedup(doc: MapDocument, *, trace: Any = None) -> DedupReport:
    """
    Deduplicate waypoints in-place on a MapDocument.
    """
    wps = doc.waypoints()
    kept, dropped, report = dedupe_waypoints(wps, trace=trace)
    dropped_ids = {w.id for w in dropped}
    doc.items = [
        i for i in doc.items if not (isinstance(i, Waypoint) and i.id in dropped_ids)
    ]
    # Replace kept versions (which may now have merged source_ids)
    # Ensure stable order: keep original order of appearance.
    kept_map = {w.id: w for w in kept}
    new_items = []
    for i in doc.items:
        if isinstance(i, Waypoint) and i.id in kept_map:
            new_items.append(kept_map[i.id])
        else:
            new_items.append(i)
    doc.items = new_items
    return report
