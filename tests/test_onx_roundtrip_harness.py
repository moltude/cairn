"""scripts/onx_roundtrip.py, scripts/generate_edge_dataset.py and the bridge's line
style/weight edits they rely on.

The offline self-test stands in for onX by feeding Cairn's own upload files back as
"the onX export": verify must then find nothing to report, at both stages.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402
from cairn.core.config import get_all_onx_icons  # noqa: E402


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rt = _module("onx_roundtrip")
gen = _module("generate_edge_dataset")

RANDOM = ROOT / "tests" / "fixtures" / "caltopo-random" / "onx-test-random.json"
ONX_DASH = ROOT / "tests" / "fixtures" / "onx_real" / "onx_web_line_dash.gpx"
EDGE = ROOT / "tests" / "fixtures" / "edge_cases_onx" / "edge.json"


def _load(path: Path) -> dict:
    bridge.CONFIG_PATH = ROOT / "web" / "cairn_config.yaml"
    return json.loads(bridge.load_files(json.dumps([{"name": path.name, "text": path.read_text()}])))


def _items(data: dict, kind: str) -> list[dict]:
    return [i for g in data["groups"] for i in g["items"] if i["kind"] == kind]


def _gpx_texts() -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(bytes(bridge.export_zip()))) as z:
        return {n: z.read(n).decode() for n in z.namelist() if n.endswith(".gpx")}


def _track_ext(text: str, name: str) -> tuple[str, str]:
    """(onx:style, onx:weight) of the <trk>/<rte> called `name`."""
    for block in re.findall(r"<(?:trk|rte)>.*?</(?:trk|rte)>", text, re.S):
        if f"<name>{name}</name>" in block:
            return (re.search(r"<onx:style>(.*?)</onx:style>", block).group(1),
                    re.search(r"<onx:weight>(.*?)</onx:weight>", block).group(1))
    raise AssertionError(f"no track {name!r}")


# --- bridge: line style / weight edits ------------------------------------------------------

def test_track_style_and_weight_edits_are_exported_from_caltopo_source():
    data = _load(RANDOM)
    trk = next(i for i in _items(data, "tracks") if i["name"] == "section 1")
    tracks_gpx = lambda: next(t for n, t in _gpx_texts().items() if n.endswith("_Tracks.gpx"))  # noqa: E731
    assert _track_ext(tracks_gpx(), "section 1") == ("solid", "4.0")
    bridge.apply_edits(json.dumps({trk["uid"]: {"style": "dash", "weight": "6.0"}}))
    assert _track_ext(tracks_gpx(), "section 1") == ("dash", "6.0")
    bridge.apply_edits(json.dumps({trk["uid"]: {"style": "dot"}}))
    assert _track_ext(tracks_gpx(), "section 1") == ("dot", "6.0")


def test_track_style_and_weight_edits_are_exported_from_onx_source():
    data = _load(ONX_DASH)
    (trk,) = _items(data, "tracks")
    name = trk["name"]
    (text,) = _gpx_texts().values()
    assert _track_ext(text, name) == ("dash", "6.0")
    bridge.apply_edits(json.dumps({trk["uid"]: {"style": "solid", "weight": "4.0"}}))
    (text,) = _gpx_texts().values()
    assert _track_ext(text, name) == ("solid", "4.0")


def test_unknown_style_or_weight_is_refused_and_applies_nothing():
    data = _load(RANDOM)
    trk = _items(data, "tracks")[0]
    with pytest.raises(ValueError, match="line style"):
        bridge.apply_edits(json.dumps({trk["uid"]: {"style": "dashed-ish", "name": "X"}}))
    with pytest.raises(ValueError, match="line weight"):
        bridge.apply_edits(json.dumps({trk["uid"]: {"weight": "5.0"}}))
    assert trk["name"] != "X" and "style" not in trk and "weight" not in trk


def test_style_and_weight_are_ignored_for_waypoints():
    data = _load(RANDOM)
    wpt = _items(data, "waypoints")[0]
    before = _gpx_texts()
    out = json.loads(bridge.apply_edits(json.dumps({wpt["uid"]: {"style": "dash", "weight": "6.0"}})))
    assert out == {"applied": 1}
    assert "style" not in wpt and "weight" not in wpt
    assert _gpx_texts() == before


# --- edge dataset ---------------------------------------------------------------------------

def test_edge_dataset_is_generated_and_current():
    assert EDGE.read_text(encoding="utf-8") == gen.render(), "run scripts/generate_edge_dataset.py"


def test_edge_dataset_note_lengths_survive_cairn():
    data = _load(EDGE)
    notes = {i["name"]: i["desc"] for g in data["groups"] for i in g["items"]}
    for n in gen.NOTE_LENGTHS:
        assert len(notes[f"ZZTEST note {n}"]) == n
    for n in gen.TRACK_NOTE_LENGTHS:
        assert len(notes[f"ZZTEST line note {n}"]) == n
    assert all(name.startswith("ZZTEST ") for name in notes)
    assert {g["name"] for g in data["groups"]} == {"Edge Cases"}


# --- harness: classification (pure) ---------------------------------------------------------

def _rec(**kw) -> dict:
    base = {"name": "[r1i1] A", "kind": "waypoint", "notes": "", "icon": "Summit",
            "color": "rgba(255,0,0,1)", "style": None, "weight": None, "points": 1,
            "first": [-121.0, 46.0], "last": [-121.0, 46.0], "holes": 0}
    base.update(kw)
    return base


def _status(exp, act, field):
    return {f: s for f, s, _d in rt.classify(exp, act)}[field]


def test_note_cut_to_512_is_a_known_onx_limit():
    note = "x" * 600
    assert _status(_rec(notes=note), _rec(notes=note[:512]), "notes") == rt.KNOWN
    assert _status(_rec(notes=note), _rec(notes=""), "notes") == rt.KNOWN
    assert rt.status_of(rt.classify(_rec(notes=note), _rec(notes=note[:512]))) == rt.KNOWN


def test_note_changes_within_the_limit_fail():
    note = "x" * 512
    assert _status(_rec(notes=note), _rec(notes=note[:511]), "notes") == rt.FAIL
    assert _status(_rec(notes=note), _rec(notes=""), "notes") == rt.FAIL
    assert _status(_rec(notes="y" * 600), _rec(notes="z" * 512), "notes") == rt.FAIL


def test_wrong_icon_fails():
    fields = rt.classify(_rec(icon="Summit"), _rec(icon="Camp"))
    assert {f: s for f, s, _d in fields}["icon"] == rt.FAIL
    assert rt.status_of(fields) == rt.FAIL


def test_color_with_spaces_passes_and_wrong_color_fails():
    assert _status(_rec(), _rec(color="rgba(255, 0, 0, 1)"), "color") == rt.PASS
    assert _status(_rec(), _rec(color="rgba(0,0,0,1)"), "color") == rt.FAIL


def test_thinned_line_is_known_but_moved_end_fails():
    exp = _rec(kind="track", icon="", style="solid", weight="4.0", points=100,
               first=[-121.0, 46.0], last=[-121.1, 46.1])
    thinned = dict(exp, points=80, first=[-121.000004, 46.000003])
    assert _status(exp, thinned, "points") == rt.KNOWN
    assert _status(exp, dict(exp, points=80, last=[-121.2, 46.1]), "points") == rt.FAIL
    assert _status(exp, dict(exp, points=120), "points") == rt.FAIL
    assert _status(exp, dict(exp, style="dash"), "style") == rt.FAIL


def test_area_with_dropped_holes_is_reported_as_known():
    exp = _rec(kind="area", icon="", points=4)
    fields = rt.classify(exp, exp, known_holes=(exp["name"],))
    assert ("holes", rt.KNOWN) in [(f, s) for f, s, _d in fields]


def test_match_reports_missing_and_unexpected_items():
    a, b = _rec(name="[r1i1] A"), _rec(name="[r1i1] B", first=[-120.0, 45.0], last=[-120.0, 45.0])
    pairs, missing, unexpected = rt.match([a, b], [a, _rec(name="[r1i1] C", first=[-110.0, 40.0])])
    assert [p[0]["name"] for p in pairs] == ["[r1i1] A"]
    assert [m["name"] for m in missing] == ["[r1i1] B"]
    assert [u["name"] for u in unexpected] == ["[r1i1] C"]
    # A renamed item at the same place is paired, so the report names the field.
    pairs, missing, unexpected = rt.match([b], [dict(b, name="[r1i1] B2")])
    assert len(pairs) == 1 and not missing and not unexpected


def test_edit_plan_icons_are_in_the_catalogue():
    assert set(rt.ICON_CYCLE) <= set(get_all_onx_icons())
    assert len(rt.WAYPOINT_COLORS) == 10 and len(rt.LINE_COLORS) == 11


def test_stage2_refuses_items_without_the_i1_tag():
    with pytest.raises(ValueError, match=r"\[r1i1\]"):
        rt.edit_plan([_rec(name="untagged", uid="x")], "r1")


# --- harness: offline self-test ---------------------------------------------------------------

def _uploads(d: Path) -> list[Path]:
    return sorted(p for p in d.iterdir() if p.suffix == ".gpx")


def test_offline_round_trip_passes_everything(tmp_path):
    done = rt.stage1("r9", tmp_path)
    sets = {r["set"] for r in done}
    assert {"random-geojson", "random-gpx", "random-kml", "dd100-geojson", "dd100-gpx",
            "dd100-kml", "edge-geojson"} == sets
    for r in done:
        assert r["onx_folder"] == "ZZTEST · r9 · i1 · " + " · ".join(r["set"].rsplit("-", 1))
        d = r["dir"]
        assert (d / "RUNBOOK.md").exists() and r["files"]
        exp1 = json.loads((d / "expected.json").read_text())
        assert exp1["items"] and all(i["name"].startswith("[r9i1] ") for i in exp1["items"])

        rep = rt.verify("r9", "i1", r["set"], _uploads(d), tmp_path)
        assert rep["counts"] == {rt.PASS: len(exp1["items"]), rt.KNOWN: 0, rt.FAIL: 0}, rep

        r2 = rt.stage2("r9", r["set"], _uploads(d), tmp_path)
        assert r2["onx_folder"] == f"ZZTEST · r9 · i2 · {r['set']}"
        exp2 = json.loads((r2["dir"] / "expected.json").read_text())
        rep2 = rt.verify("r9", "i2", r["set"], _uploads(r2["dir"]), tmp_path)
        assert rep2["counts"] == {rt.PASS: len(exp2["items"]), rt.KNOWN: 0, rt.FAIL: 0}, rep2

        # The edit plan really changed every item, and the export carried it.
        before = {i["name"][len("[r9i1] "):]: i for i in exp1["items"]}
        assert len(exp2["items"]) == len(exp1["items"])
        for i in exp2["items"]:
            assert i["name"].startswith("[r9i2] ")
            old = before[i["name"][len("[r9i2] "):]]
            assert i["notes"].endswith("— edited r9i2") and len(i["notes"]) <= 512
            assert i["color"] != old["color"]
            if i["kind"] == "waypoint":
                assert i["icon"] != old["icon"]
            if i["kind"] == "track":
                assert i["style"] != old["style"] and i["weight"] != old["weight"]

    edge = json.loads((tmp_path / "r9" / "i2" / "edge-geojson" / "expected.json").read_text())
    truncated = {e["from"] for e in edge["edits"] if e["note_truncated_to_fit"]}
    assert "[r9i1] ZZTEST note 3000" in truncated and "[r9i1] ZZTEST note 500" in truncated

    table = rt.summary("r9", tmp_path)
    assert table.count("| i1 |") == len(sets) and table.count("| i2 |") == len(sets)
    assert (tmp_path / "r9" / "SUMMARY.md").exists()


def test_verify_cli_exits_nonzero_on_a_wrong_icon(tmp_path):
    (r,) = rt.stage1("r8", tmp_path, ["edge-geojson"])
    fake = tmp_path / "onx_export"
    fake.mkdir()
    for p in _uploads(r["dir"]):
        text = p.read_text()
        if p.name.endswith("_Waypoints.gpx"):
            assert "<onx:icon>Summit</onx:icon>" in text
            text = text.replace("<onx:icon>Summit</onx:icon>", "<onx:icon>Camp</onx:icon>", 1)
        (fake / p.name).write_text(text)
    code = rt.main(["--root", str(tmp_path), "verify", "--run", "r8", "--stage", "i1",
                    "--set", "edge-geojson", "--onx", *map(str, _uploads(fake))])
    assert code == 1
    rep = json.loads((r["dir"] / "verify_report.json").read_text())
    assert rep["counts"][rt.FAIL] == 1
    (bad,) = [x for x in rep["results"] if x["status"] == rt.FAIL]
    assert [f["field"] for f in bad["fields"]] == ["icon"]
    assert "FAIL" in (r["dir"] / "verify_report.md").read_text()
