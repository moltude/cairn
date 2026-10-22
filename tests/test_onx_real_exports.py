"""Real onX Web Map exports (tests/fixtures/onx_real/) load faithfully.

Until 2026-10-22 every onX-reader test ran on synthetic files. These two are
real: their icons, colors (written by onX with spaces), notes and ids must
survive the bridge whether loaded as GPX, as KML, or as a pair.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "onx_real"
GPX = (FIX / "onx_web_export_2_waypoints.gpx").read_text(encoding="utf-8")
KML = (FIX / "onx_web_export_2_waypoints.kml").read_text(encoding="utf-8")

EXPECTED = [
    ("ZZTEST A", "Summit", "rgba(255,0,0,1)", "1bbcfa70-9920-4d83-ad03-8b3f9b54da52"),
    ("ZZTEST B", "Camp", "rgba(8,122,255,1)", "ff14e786-518c-478f-a61a-9474322b3432"),
]


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(bridge, "CONFIG_PATH", ROOT / "web" / "cairn_config.yaml")


@pytest.mark.parametrize("files", [
    [("onx-markups.gpx", GPX)],
    [("onx-markups.kml", KML)],
    [("onx-markups.gpx", GPX), ("onx-markups.kml", KML)],
], ids=["gpx", "kml", "pair"])
def test_real_onx_export_keeps_icons_colors_notes_and_ids(files):
    doc = json.loads(bridge.load_files(json.dumps([{"name": n, "text": t} for n, t in files])))
    assert {s["dialect"] for s in doc["sources"]} == {"onx"}
    items = [i for g in doc["groups"] for i in g["items"]]
    got = sorted((i["name"], i["icon"], i["color"], i["onx_id"]) for i in items)
    assert got == EXPECTED
    for i in items:
        assert i["desc"] == "Cairn re-import probe. Safe to delete."
        assert not i["needs_attention"]
