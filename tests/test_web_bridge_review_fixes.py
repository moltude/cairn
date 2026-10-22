"""Non-polygon defects from the 2026-10-22 review of web/bridge.py and the
engine. Each test failed before its fix."""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402

BROWN = "rgba(139,69,19,1)"
BLUE = "rgba(8,122,255,1)"


def _doc(*features):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "f1", "geometry": None,
         "properties": {"class": "Folder", "title": "Camp"}},
        *features,
    ]}


def _marker(fid, title, **props):
    return {"type": "Feature", "id": fid,
            "geometry": {"type": "Point", "coordinates": [-114.1, 46.2]},
            "properties": {"class": "Marker", "title": title, "folderId": "f1", **props}}


def _load(doc):
    data = json.loads(bridge.load_document(json.dumps(doc), "camp.json"))
    return {i["name"]: i for g in data["groups"] for i in g["items"]}


def _export_colors(edits=None):
    if edits:
        bridge.apply_edits(json.dumps(edits))
    z = zipfile.ZipFile(io.BytesIO(bridge.export_zip()))
    gpx = "".join(z.read(n).decode() for n in z.namelist() if n.endswith("_Waypoints.gpx"))
    return dict(re.findall(r"<wpt [^>]*>\s*<name>(.*?)</name>.*?<onx:color>(.*?)</onx:color>", gpx, re.S))


# ---- (f) colourless waypoints: UI and export agree --------------------------

def test_colorless_waypoint_shows_and_exports_its_icon_color():
    # "hut" -> Shelter by keyword; Shelter's conventional colour is Brown. The
    # UI used to show Blue while the writer exported Brown.
    items = _load(_doc(_marker("w1", "Elk Hut")))
    assert items["Elk Hut"]["icon"] == "Shelter"
    assert items["Elk Hut"]["color"] == BROWN
    assert _export_colors()["Elk Hut"] == BROWN


def test_icon_edit_on_colorless_waypoint_keeps_the_shown_color():
    # The UI does not recolour a pin when its icon changes, so neither may the
    # export (the writer used to recompute from the NEW icon: Hazard -> orange).
    items = _load(_doc(_marker("w1", "Elk Hut")))
    shown = items["Elk Hut"]["color"]
    assert _export_colors({items["Elk Hut"]["uid"]: {"icon": "Hazard"}})["Elk Hut"] == shown


def test_source_color_still_quantized_and_unknown_icon_falls_back_to_blue():
    items = _load(_doc(
        _marker("w1", "Odd", **{"marker-color": "#FE0101"}),
        _marker("w2", "Nothing here"),
    ))
    assert items["Odd"]["color"] == "rgba(255,0,0,1)"
    assert items["Nothing here"]["color"] == BLUE
    exported = _export_colors()
    assert exported == {"Odd": "rgba(255,0,0,1)", "Nothing here": BLUE}


# ---- (g) 1,500 is an account ceiling ---------------------------------------

def _manifest(count, expected=None):
    return [{"n": 1, "folder": "Big", "count": count,
             "expected": count if expected is None else expected,
             "dropped": max(0, (expected or count) - count),
             "files": [{"path": "01_Big/Big_Waypoints.gpx", "count": count, "kml": False}]}]


def test_over_limit_warning_says_remove_not_split():
    rb = bridge.build_runbook(_manifest(1600))
    assert "onX accounts hold at most 1,500 markups; this map has\n> 1,600." in rb
    assert "Remove or exclude some before importing." in rb
    assert "split" not in rb.lower()


def test_over_limit_uses_max_of_written_and_expected():
    # 1,400 written but 1,600 shown: still over the account ceiling.
    s = bridge.runbook_summary(_manifest(1400, expected=1600))
    assert (s["markups"], s["over_limit"], s["dropped"]) == (1600, True, 200)
    assert "this map has\n> 1,600." in bridge.build_runbook(_manifest(1400, expected=1600))
    assert not bridge.runbook_summary(_manifest(1500))["over_limit"]


def test_on_screen_runbook_reads_the_shared_summary():
    # web/app.js renderRunbook must use bridge.runbook_summary_json (the same
    # numbers as RUNBOOK.md) instead of re-deriving its own count.
    js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")
    body = js.split("function renderRunbook()", 1)[1].split("\nfunction ", 1)[0]
    assert "bridge.runbook_summary_json()" in body
    assert "S.dropped" in body and "S.over_limit" in body
    assert "e.count, 0)" not in body


# ---- (i) explicit symbol -> default pin explanation -------------------------

def test_symbol_explicitly_mapped_to_default_pin_is_explained_honestly(tmp_path, monkeypatch):
    cfg = tmp_path / "cairn_config.yaml"
    cfg.write_text("symbol_mappings:\n  flag-1: Location\n", encoding="utf-8")
    monkeypatch.setattr(bridge, "CONFIG_PATH", cfg)
    items = _load(_doc(_marker("w1", "Somewhere", **{"marker-symbol": "flag-1"})))
    it = items["Somewhere"]
    assert it["icon"] == "Location" and it["needs_attention"]
    assert "maps to this icon" not in it["why"]
    assert "default pin" in it["why"]
    assert "flag-1" in it["why"]
