"""Dark Divide 100: one real CalTopo map exported as GeoJSON, GPX and KML.

Pins what Cairn does with each format (tests/fixtures/dark_divide_100/) and fails
if the committed outputs or PARITY.md drift from what the current code produces.
Regenerate with: uv run python scripts/dark_divide_parity.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "dark_divide_100"

_spec = importlib.util.spec_from_file_location("dark_divide_parity", ROOT / "scripts" / "dark_divide_parity.py")
parity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parity)


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    out = tmp_path_factory.mktemp("dd_out")
    report = out / "PARITY.md"
    saved = parity.OUT, parity.REPORT
    parity.OUT, parity.REPORT = out / "cairn_output", report
    try:
        parity.main()
        res = parity.run()  # second run: proves determinism against the first
    finally:
        parity.OUT, parity.REPORT = saved
    return out, report, res


def test_committed_outputs_match_current_code(results):
    out, report, _ = results
    fresh = {p.relative_to(out / "cairn_output").as_posix(): p.read_bytes()
             for p in (out / "cairn_output").rglob("*") if p.is_file()}
    committed = {p.relative_to(FIX / "cairn_output").as_posix(): p.read_bytes()
                 for p in (FIX / "cairn_output").rglob("*") if p.is_file() and p.name != ".DS_Store"}
    assert fresh.keys() == committed.keys()
    for k in fresh:
        assert fresh[k] == committed[k], f"{k} drifted; rerun scripts/dark_divide_parity.py"
    assert report.read_text() == (FIX / "PARITY.md").read_text()


def _all(review):
    return [i for k in review.values() for i in k]


def test_every_format_reads_the_same_items_notes_and_geometry(results):
    _, _, res = results
    ref, ref_geo = res["geojson"][0], res["geojson"][1]
    for tag, (review, geo, *_r) in res.items():
        assert (len(review["waypoints"]), len(review["tracks"]), len(review["shapes"])) == (9, 12, 0), tag
        items = _all(review)
        assert sum("\n" in (i.get("desc") or "") for i in items) == 21, tag
        for kind in ("waypoints", "tracks"):
            for a, b in zip(ref[kind], review[kind]):
                assert (a["name"], a["desc"]) == (b["name"], b["desc"]), (tag, a["name"])
                assert ref_geo[a["name"]] == geo[b["name"]], (tag, a["name"])
                if kind == "waypoints":
                    assert a["icon"] == b["icon"], (tag, a["name"])


DD_FOLDERS = {
    "1 - Course GPX Dark Divide 100 Miler",
    "2 - Aid Stations Dark Divide 100 Miler",
    "3 - Course Segments Dark Divide 100 Miler",
}
CUSTOM_ICON_MARKERS = {
    "01 - Cispus Learning Center Start/Finish", "02 - Juniper Ridge AS (Used Twice)",
    "03 - Sunrise AS (Used Twice)", "04 - Dark Creek AS", "05 - Wilderness Crossing AS",
    "06 - Wright Meadow AS", "07 - Lewis River AS", "08 - Quartz Butte AS",
    # Was equal by chance while its name mapped to Summit (red, like CalTopo's);
    # since 2026-10-24 "AS" maps it to Food Source like the other aid stations.
    "09 - Summit Prairie AS",
}
LINE_10 = "10 - Sunrise Peak #2 AS to Juniper Ridge #2 AS"


def _cross(res, tag):
    """{(kind, name, field)} where `tag`'s review screen differs from GeoJSON's."""
    out = set()
    for d in parity._diff(res["geojson"][0], res[tag][0], res["geojson"][1], res[tag][1],
                          parity.CROSS_FIELDS):
        head, field = d.split("': ", 1)
        kind, name = head.split(" '", 1)
        out.add((kind, name, field.split(" ", 1)[0]))
    return out


def test_kml_matches_geojson_except_custom_icon_marker_colours(results):
    """CalTopo KML now keeps the folders and line colours (roadmap Phase 7).
    What's left: GeoJSON gives the custom-icon markers a stroke #FF0000 that
    the KML's icon cfg doesn't carry."""
    _, _, res = results
    assert {i["folder"] for i in _all(res["geojson"][0])} == DD_FOLDERS
    assert {i["folder"] for i in _all(res["kml"][0])} == DD_FOLDERS
    assert {i["color"] for i in _all(res["geojson"][0])} == {"rgba(255,0,0,1)"}
    assert {i["color"] for i in res["kml"][0]["tracks"]} == {"rgba(255,0,0,1)"}
    assert _cross(res, "kml") == {("waypoints", n, "color") for n in CUSTOM_ICON_MARKERS}


def test_gpx_differs_only_where_gpx_lacks_the_data(results):
    """GPX losses: folders (none in GPX), waypoint colours (Garmin's schema has
    no waypoint colour) and line 10's colour (its lower-case #ff0000 got no
    DisplayColor). Every other line's red now comes from DisplayColor."""
    _, _, res = results
    gpx = res["gpx"][0]
    assert {i["folder"] for i in _all(gpx)} == {"2027 Dark Divide 100 Mile Endurance Run"}
    assert {i["name"]: i["color"] for i in gpx["tracks"]}[LINE_10] == "rgba(8,122,255,1)"
    assert {i["color"] for i in gpx["tracks"] if i["name"] != LINE_10} == {"rgba(255,0,0,1)"}
    expected = (
        {(k, i["name"], "folder") for k in ("waypoints", "tracks") for i in res["geojson"][0][k]}
        | {("waypoints", n, "color") for n in CUSTOM_ICON_MARKERS}
        | {("tracks", LINE_10, "color")}
    )
    assert _cross(res, "gpx") == expected


def test_kml_export_is_the_geojson_export_but_the_marker_colours(results):
    """What onX is handed from the KML: the same files and bytes as from the
    GeoJSON (folders, line colours, elevations -- CalTopo's 0.0 altitude is not
    written as sea level), except the 9 custom-icon markers' <onx:color>."""
    out, _, _ = results
    a, b = out / "cairn_output" / "from_geojson", out / "cairn_output" / "from_kml"
    fa = {p.relative_to(a): p.read_text() for p in a.rglob("*") if p.is_file()}
    fb = {p.relative_to(b): p.read_text() for p in b.rglob("*") if p.is_file()}
    assert fa.keys() == fb.keys()
    changed = [k for k in fa if fa[k] != fb[k]]
    assert [k.name for k in changed] == ["2_Aid_Stations_Dark_Divide_100_Miler_Waypoints.gpx"]
    la, lb = fa[changed[0]].splitlines(), fb[changed[0]].splitlines()
    assert len(la) == len(lb)
    diff = [(x, y) for x, y in zip(la, lb) if x != y]
    assert len(diff) == len(CUSTOM_ICON_MARKERS) and all("<onx:color>" in x and "<onx:color>" in y for x, y in diff)


def test_export_reread_matches_review_including_special_character_names(results):
    """What Cairn hands onX is identical to the review screen: names such as
    '02 - Juniper Ridge AS #1 ...' keep their '#' (DECISIONS.md ENG-06)."""
    _, _, res = results
    for tag, (review, rgeo, reread, egeo) in res.items():
        assert parity._diff(review, reread, rgeo, egeo) == [], tag
