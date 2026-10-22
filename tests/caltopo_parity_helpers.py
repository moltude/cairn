"""Load one CalTopo map's GeoJSON / KML / GPX through web/bridge.py and compare
what the review screen shows (shared by the CalTopo parity tests)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402

from cairn.core.color_mapper import pattern_to_style  # noqa: E402

FIELDS = ("kind", "folder", "name", "notes", "icon", "color", "style", "geometry")


def _geometry(feat) -> tuple:
    g = feat.geometry or {}
    c = g.get("coordinates")
    if g.get("type") == "Point":
        rings = [[c]]
    elif g.get("type") == "LineString":
        rings = [c]
    else:
        rings = c or []
    return tuple(tuple((round(p[0], 6), round(p[1], 6)) for p in r) for r in rings)


def review_items(path: Path) -> list[dict]:
    """The review screen's items for one file, plus line style and geometry
    from the engine document, sorted by (kind, name)."""
    bridge.CONFIG_PATH = ROOT / "web" / "cairn_config.yaml"
    data = json.loads(bridge.load_files(json.dumps(
        [{"name": path.name, "text": path.read_text(encoding="utf-8")}])))
    doc = bridge._STATE["doc"]
    out = []
    for g in data["groups"]:
        for it in g["items"]:
            fkey, kind, idx = it["uid"].rsplit("::", 2)
            feat = doc.folders[fkey][kind][int(idx)]
            out.append({
                "kind": kind, "folder": g["name"], "name": it["name"], "notes": it["notes"],
                "icon": it["icon"], "color": it["color"],
                "style": "" if kind == "waypoints" else pattern_to_style(feat.pattern),
                "geometry": _geometry(feat),
            })
    return sorted(out, key=lambda i: (i["kind"], i["name"]))


def _keyed(items: list[dict]) -> dict:
    """(kind, name, n) -> item; n numbers items sharing a name (the parts of a
    multi-part area all keep the area's name)."""
    seen: dict = {}
    out = {}
    for i in items:
        k = (i["kind"], i["name"])
        seen[k] = seen.get(k, 0) + 1
        out[k + (seen[k],)] = i
    return out


def differences(ref: list[dict], other: list[dict]) -> set[tuple]:
    """{(kind, name, field)} where `other` differs from `ref`; an item missing
    from `other` is (kind, name, "missing"), one only in `other` "extra"."""
    a_by, b_by = _keyed(ref), _keyed(other)
    out = set()
    for key, a in a_by.items():
        b = b_by.get(key)
        if b is None:
            out.add((key[0], key[1], "missing"))
            continue
        out |= {(key[0], key[1], f) for f in FIELDS if a[f] != b[f]}
    out |= {(k[0], k[1], "extra") for k in b_by if k not in a_by}
    return out
