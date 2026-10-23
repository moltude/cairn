"""Synthetic CalTopo GeoJSON maps for hardening the folder/export engine."""
from __future__ import annotations

import json
import random

NASTY_NAMES = [
    "Camp", "camp", " Camp ", "CAMP",              # differ only in case / whitespace
    "A/B", "A_B", "A:B", "A B", "A-B",             # same-ish safe form
    "..", ".", "CON", "NUL", "trailing...", "   ",  # reserved / dot / blank
    "Zürich Café", "日本語のフォルダ", "مجلد عربي", "עברית",  # unicode + RTL
    "Peak 🏔️🔥", "🏔️", "x" * 300, "ä" * 200,       # emoji, only-emoji, very long
    "a‮b", "tab\there", "new\nline", 'q"uo<te>&', "back\\slash", "../../etc/passwd",
]


def _pt(i, folder, title=None, desc=""):
    p = {"title": title if title is not None else f"WP {i}", "class": "Marker",
         "marker-symbol": "camping", "marker-color": "#FF0000", "description": desc}
    if folder:
        p["folderId"] = folder
    return {"type": "Feature", "id": f"m{i}", "properties": p,
            "geometry": {"type": "Point", "coordinates": [-114.0 + (i % 100) * 1e-3, 46 + (i // 100) * 1e-3, 0, 0]}}


def _line(i, folder, npts=5, desc=""):
    p = {"title": f"Line {i}", "class": "Shape", "stroke": "#0000FF", "stroke-width": 2,
         "pattern": "solid", "description": desc}
    if folder:
        p["folderId"] = folder
    return {"type": "Feature", "id": f"l{i}", "properties": p,
            "geometry": {"type": "LineString",
                         "coordinates": [[-114 + i * 1e-4 + k * 1e-3, 46 + k * 1e-3] for k in range(npts)]}}


def _poly(i, folder, holes=1):
    def ring(d):
        return [[-114 + d, 46 + d], [-114 + d + .1, 46 + d], [-114 + d + .1, 46 + d + .1],
                [-114 + d, 46 + d + .1], [-114 + d, 46 + d]]
    coords = [ring(i * 1e-3)] + [ring(i * 1e-3 + .02)[::-1] for _ in range(holes)]
    p = {"title": f"Area {i}", "class": "Shape", "stroke": "#FF0000", "fill": "#FF0000",
         "fill-opacity": .1, "stroke-width": 2, "pattern": "solid"}
    if folder:
        p["folderId"] = folder
    return {"type": "Feature", "id": f"a{i}", "properties": p,
            "geometry": {"type": "Polygon", "coordinates": coords}}


def _folder(fid, title):
    return {"type": "Feature", "id": fid, "geometry": None,
            "properties": {"title": title, "class": "Folder", "visible": True}}


def make_map(n_folders, *, seed=0, names=None, empty=0, kinds="mixed", per=(1, 6),
             big=0, long_notes=False, no_coords=False, holes=True) -> str:
    rnd = random.Random(seed)
    feats, i = [], 0
    names = names or NASTY_NAMES
    for f in range(n_folders):
        title = names[f % len(names)] + ("" if f < len(names) else f" {f}")
        fid = f"f{f}"
        feats.append(_folder(fid, title))
        if f < empty:
            continue
        n = big if (big and f == n_folders - 1) else rnd.randint(*per)
        for _ in range(n):
            i += 1
            k = kinds if kinds != "mixed" else rnd.choice(["w", "l", "a"])
            if kinds == "w":
                k = "w"
            desc = "long note ü—🔥 " * 200 if long_notes and i % 3 == 0 else ""
            if k == "w":
                feats.append(_pt(i, fid, desc=desc))
            elif k == "l":
                feats.append(_line(i, fid, desc=desc))
            else:
                feats.append(_poly(i, fid, holes=2 if holes else 0))
    if no_coords:
        feats.append({"type": "Feature", "id": "nc", "geometry": None,
                      "properties": {"title": "no coords", "class": "Marker", "folderId": "f0"}})
        feats.append({"type": "Feature", "id": "nc2", "geometry": {"type": "LineString", "coordinates": []},
                      "properties": {"title": "empty line", "class": "Shape", "folderId": "f0"}})
        feats.append({"type": "Feature", "id": "nc3", "geometry": {"type": "Point", "coordinates": []},
                      "properties": {"title": "empty pt", "class": "Marker", "folderId": "f0"}})
    # unfiled items too
    for _ in range(2):
        i += 1
        feats.append(_pt(i, None, title="Loose"))
    return json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False)
