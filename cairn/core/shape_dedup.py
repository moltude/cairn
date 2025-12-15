"""
Shape (line/polygon) deduplication.

Goal: produce a more usable CalTopo dataset by collapsing identical or near-identical
Shapes that appear multiple times in OnX exports.

We keep the dropped features in a separate output and write a human-readable summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from cairn.model import MapDocument, Shape, Track


def _round6(x: float) -> float:
    return round(float(x), 6)


def _norm_point2(pt: Iterable[float]) -> Tuple[float, float]:
    p = list(pt)
    return (_round6(p[0]), _round6(p[1]))


def _strip_closing_point(ring: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(ring) >= 2 and ring[0] == ring[-1]:
        return ring[:-1]
    return ring


def _min_rotation(seq: List[Tuple[float, float]]) -> Tuple[Tuple[float, float], ...]:
    """
    Return lexicographically smallest rotation.
    O(n^2) but rings are small enough for our typical datasets.
    """
    if not seq:
        return tuple()
    best = None
    n = len(seq)
    for i in range(n):
        rot = tuple(seq[i:] + seq[:i])
        if best is None or rot < best:
            best = rot
    return best or tuple()


def polygon_signature(shape: Shape) -> Optional[Tuple]:
    if not shape.rings:
        return None
    ring0 = [_norm_point2(p) for p in shape.rings[0]]
    ring0 = _strip_closing_point(ring0)
    if len(ring0) < 3:
        return None
    fwd = list(ring0)
    rev = list(reversed(ring0))
    return ("Polygon", _min_rotation(fwd), _min_rotation(rev))


def line_signature(track: Track) -> Optional[Tuple]:
    if not track.points:
        return None
    pts = [(_round6(p[0]), _round6(p[1])) for p in track.points]
    if len(pts) < 2:
        return None
    fwd = tuple(pts)
    rev = tuple(reversed(pts))
    return ("LineString", min(fwd, rev))


@dataclass
class ShapeDedupGroup:
    kind: str  # Polygon|LineString
    title: str
    kept_id: str
    dropped_ids: List[str]
    reason: str


@dataclass
class ShapeDedupReport:
    groups: List[ShapeDedupGroup]

    @property
    def dropped_count(self) -> int:
        return sum(len(g.dropped_ids) for g in self.groups)


def apply_shape_dedup(
    doc: MapDocument,
    *,
    trace: Any = None,
) -> Tuple[ShapeDedupReport, List[object]]:
    """
    Deduplicate polygons and lines by fuzzy geometry signature + title.

    - Polygons: normalize to 6 decimals, ignore ring start index and direction.
    - Lines: normalize to 6 decimals, treat reversed as equivalent.

    Returns:
      (report, dropped_items)
    """
    # Build groups
    groups: Dict[Tuple[str, str, Tuple], List[object]] = {}
    for item in list(doc.items):
        if isinstance(item, Shape):
            sig = polygon_signature(item)
            if sig is None:
                continue
            key = ("Polygon", item.name, sig)
            groups.setdefault(key, []).append(item)
        elif isinstance(item, Track):
            sig = line_signature(item)
            if sig is None:
                continue
            key = ("LineString", item.name, sig)
            groups.setdefault(key, []).append(item)

    report_groups: List[ShapeDedupGroup] = []
    dropped: List[object] = []

    def score(it: object) -> Tuple[int, int]:
        # Prefer richer notes, then stable OnX_id presence.
        notes = getattr(it, "notes", "") or ""
        style = getattr(it, "style", None)
        OnX_id = getattr(style, "OnX_id", None) if style is not None else None
        return (len(notes.strip()), 1 if OnX_id else 0)

    for (kind, title, sig), members in groups.items():
        if len(members) <= 1:
            continue

        kept = max(members, key=score)
        dropped_members = [m for m in members if m is not kept]
        for m in dropped_members:
            dropped.append(m)

        # Remove dropped from doc.items
        keep_ids = {id(kept)}
        drop_obj_ids = {id(m) for m in dropped_members}
        doc.items = [i for i in doc.items if id(i) not in drop_obj_ids]

        kept_id = getattr(kept, "id", "")
        dropped_ids = [getattr(m, "id", "") for m in dropped_members]
        report_groups.append(
            ShapeDedupGroup(
                kind=kind,
                title=title,
                kept_id=kept_id,
                dropped_ids=dropped_ids,
                reason="fuzzy_geometry_signature_match",
            )
        )

        if trace is not None:
            trace.emit(
                {
                    "event": "shape_dedup.group",
                    "kind": kind,
                    "title": title,
                    "kept_id": kept_id,
                    "dropped_ids": dropped_ids,
                    "reason": "fuzzy_geometry_signature_match",
                    "group_size": len(members),
                }
            )

    return ShapeDedupReport(groups=report_groups), dropped
