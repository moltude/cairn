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


def test_known_format_losses_are_exactly_folders_and_colors(results):
    """GeoJSON keeps 3 folders and CalTopo's red; GPX has neither, and Cairn
    does not read CalTopo KML's <Folder> or LineStyle yet (roadmap Phase 7)."""
    _, _, res = results
    assert {i["folder"] for i in _all(res["geojson"][0])} == {
        "1 - Course GPX Dark Divide 100 Miler",
        "2 - Aid Stations Dark Divide 100 Miler",
        "3 - Course Segments Dark Divide 100 Miler",
    }
    assert {i["color"] for i in _all(res["geojson"][0])} == {"rgba(255,0,0,1)"}
    for tag in ("gpx", "kml"):
        assert len({i["folder"] for i in _all(res[tag][0])}) == 1, tag
        assert {i["color"] for i in res[tag][0]["tracks"]} == {"rgba(8,122,255,1)"}, tag


def test_export_reread_differs_only_by_hash_stripped_from_names(results):
    """What Cairn hands onX matches the review screen except that '#' is removed
    from names (sanitize_name_for_onx; owner probe P5 decides if that stays)."""
    _, _, res = results
    for tag, (review, rgeo, reread, egeo) in res.items():
        diffs = parity._diff(review, reread, rgeo, egeo)
        assert diffs, tag
        for d in diffs:
            assert ": name " in d and "#" in d.split(" vs ")[0], (tag, d)
