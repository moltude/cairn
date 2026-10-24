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


def test_onx_line_long_note_with_tag_like_text_is_kept_verbatim():
    """onX notes are plain text. The owner's 3,000+ character note contains
    "<desc>" and "<description>" as text; HTML stripping used to delete them."""
    text = (FIX / "onx_web_line_long_note.gpx").read_text(encoding="utf-8")
    doc = json.loads(bridge.load_files(json.dumps([{"name": "long.gpx", "text": text}])))
    (item,) = [i for g in doc["groups"] for i in g["items"]]
    assert "`<desc>`" in item["desc"] and "<descriptio\nn>" in item["desc"]
    assert len(item["desc"]) > 3000


@pytest.mark.parametrize("stem, style", [("onx_web_line_solid", "solid"), ("onx_web_line_dash", "dash")])
def test_onx_drawn_lines_keep_style_and_weight_through_export(stem, style):
    import io, re, zipfile
    for ext in ("gpx", "kml"):
        text = (FIX / f"{stem}.{ext}").read_text(encoding="utf-8")
        bridge.load_files(json.dumps([{"name": f"{stem}.{ext}", "text": text}]))
        z = zipfile.ZipFile(io.BytesIO(bytes(bridge.export_zip())))
        gpx = "".join(z.read(n).decode() for n in z.namelist() if n.endswith("Tracks.gpx"))
        assert f"<onx:style>{style}</onx:style>" in gpx and "<onx:weight>6.0</onx:weight>" in gpx, ext


def test_cairn_note_with_tag_like_text_survives_export():
    """A note edited in Cairn is plain text: '<Lake>' must reach the export."""
    import io, zipfile
    src = (ROOT / "tests/fixtures/caltopo-random/onx-test-random.json").read_text(encoding="utf-8")
    doc = json.loads(bridge.load_files(json.dumps([{"name": "r.json", "text": src}])))
    item = next(i for g in doc["groups"] for i in g["items"] if i["name"] == "Hiker")
    bridge.apply_edits(json.dumps({item["uid"]: {"desc": "Meet at <Lake> & go"}}))
    z = zipfile.ZipFile(io.BytesIO(bytes(bridge.export_zip())))
    wpts = "".join(z.read(n).decode() for n in z.namelist() if n.endswith("Waypoints.gpx"))
    assert "<desc>Meet at &lt;Lake&gt; &amp; go</desc>" in wpts


def test_instructions_mark_notes_longer_than_onx_imports():
    import io, zipfile
    src = (ROOT / "tests/fixtures/dark_divide_100/caltopo/2027_Dark_Divide_100_Mile_Endurance_Run.json").read_text(encoding="utf-8")
    bridge.load_files(json.dumps([{"name": "dd.json", "text": src}]))
    z = zipfile.ZipFile(io.BytesIO(bytes(bridge.export_zip())))
    lines = z.read("instructions.txt").decode("utf-8").split("\r\n")
    note = "                (onX keeps only the first 512 bytes of this note, about 512 characters)"
    assert lines[lines.index("            02 - Juniper Ridge AS (Used Twice)") + 1] == note
    assert lines.count(note) == 1
    assert bridge._STATE["manifest"][1]["long_notes"] == [["02 - Juniper Ridge AS (Used Twice)", 617]]
    assert json.loads(bridge.runbook_summary_json())["long_notes"] == 1


def test_multibyte_note_over_512_bytes_is_flagged():
    """onX's limit is 512 UTF-8 bytes: 512 characters ending in an em dash is 514."""
    src = (ROOT / "tests/fixtures/caltopo-random/onx-test-random.json").read_text(encoding="utf-8")
    doc = json.loads(bridge.load_files(json.dumps([{"name": "r.json", "text": src}])))
    item = next(i for g in doc["groups"] for i in g["items"] if i["name"] == "Hiker")
    ok, over = "x" * 512, "x" * 511 + "—"
    assert len(over) == 512 and len(over.encode()) == 514
    bridge.apply_edits(json.dumps({item["uid"]: {"desc": ok}}))
    bridge.export_zip()
    assert json.loads(bridge.runbook_summary_json())["long_notes"] == 0
    bridge.apply_edits(json.dumps({item["uid"]: {"desc": over}}))
    bridge.export_zip()
    assert json.loads(bridge.runbook_summary_json())["long_notes"] == 1
