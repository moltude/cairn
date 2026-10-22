"""A non-colour edit (rename, note, icon) must never change an item's exported
colour, and an explicit colour edit must apply.

History: web/bridge.py once rewrote colours only for colour-edited items,
because item["color"] was a parse-time default that disagreed with the
writers. Since 2026-10-22 load_document computes item["color"] with the
engine's own rules and export_zip pins EVERY item to it, so these tests now
guard WYSIWYG colour rather than the old gating."""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402

FUCHSIA = "rgba(255,0,255,1)"
BLUE = "rgba(8,122,255,1)"

DOC = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "id": "f1", "geometry": None,
         "properties": {"class": "Folder", "title": "Camp"}},
        # No marker-color: the engine picks the exported colour itself.
        {"type": "Feature", "id": "w1",
         "geometry": {"type": "Point", "coordinates": [-114.1, 46.2]},
         "properties": {"class": "Marker", "title": "Spring", "folderId": "f1"}},
        {"type": "Feature", "id": "t1",
         "geometry": {"type": "LineString", "coordinates": [[-114.5, 45.5], [-114.6, 45.6]]},
         "properties": {"class": "Shape", "title": "Trail", "stroke": "#FF0000", "folderId": "f1"}},
    ],
}


def _load():
    data = json.loads(bridge.load_document(json.dumps(DOC), "camp.json"))
    items = {i["kind"]: i for g in data["groups"] for i in g["items"]}
    return items["waypoints"], items["tracks"]


def _export(edits=None) -> tuple[str, str]:
    """(waypoint GPX, track GPX) after applying `edits`."""
    if edits:
        bridge.apply_edits(json.dumps(edits))
    z = zipfile.ZipFile(io.BytesIO(bridge.export_zip()))
    read = lambda suffix: "".join(z.read(n).decode() for n in z.namelist() if n.endswith(suffix))
    return read("_Waypoints.gpx"), read("_Tracks.gpx")


def _colors(gpx: str) -> list[str]:
    return re.findall(r"<onx:color>(.*?)</onx:color>", gpx)


def test_renaming_a_colorless_waypoint_keeps_its_exported_color():
    _load()
    baseline_wpt, _ = _export()
    assert _colors(baseline_wpt), "fixture waypoint exported no <onx:color>"

    wp, _ = _load()
    renamed_wpt, _ = _export({wp["uid"]: {"name": "Spring (renamed)"}})
    assert "Spring (renamed)" in renamed_wpt
    assert _colors(renamed_wpt) == _colors(baseline_wpt)

    # A note or icon edit must not touch the colour either.
    wp, _ = _load()
    edited_wpt, _ = _export({wp["uid"]: {"desc": "cold", "icon": "Water Source"}})
    assert _colors(edited_wpt) == _colors(baseline_wpt)


def test_an_explicit_color_edit_still_applies():
    wp, trk = _load()
    baseline_wpt, _ = _export()
    assert _colors(baseline_wpt) != [BLUE]

    wp, trk = _load()
    wpt, tracks = _export({
        wp["uid"]: {"name": "Spring", "color": BLUE},
        trk["uid"]: {"color": FUCHSIA},
    })
    assert _colors(wpt) == [BLUE]
    assert _colors(tracks) == [FUCHSIA]


def test_color_edits_reset_when_a_new_map_is_loaded():
    wp, _ = _load()
    _export({wp["uid"]: {"color": BLUE}})
    _load()
    assert bridge._STATE["color_edited"] == set()
