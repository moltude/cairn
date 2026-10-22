"""The owner's styled CalTopo test map (tests/fixtures/caltopo-random/) in three formats.

KML must map exactly like GeoJSON. GPX may differ only where CalTopo's GPX lacks the
data, and the committed outputs/report must match the current code.
Regenerate with: uv run python scripts/caltopo_random_parity.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "caltopo-random"

_spec = importlib.util.spec_from_file_location("caltopo_random_parity", ROOT / "scripts" / "caltopo_random_parity.py")
rp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rp)


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    out = tmp_path_factory.mktemp("random_out")
    rp.configure(out / "cairn_output", out / "PARITY.md")
    res = rp.run()
    return out, res


def _by_name(review):
    return {i["name"]: i for k in review.values() for i in k}


def test_committed_outputs_and_report_match_current_code(results):
    out, res = results
    fresh = {p.relative_to(out / "cairn_output").as_posix(): p.read_bytes()
             for p in (out / "cairn_output").rglob("*") if p.is_file()}
    committed = {p.relative_to(FIX / "cairn_output").as_posix(): p.read_bytes()
                 for p in (FIX / "cairn_output").rglob("*") if p.is_file() and p.name != ".DS_Store"}
    assert fresh == committed, "rerun scripts/caltopo_random_parity.py"
    assert rp.report(res) == (FIX / "PARITY.md").read_text(encoding="utf-8")


def test_kml_maps_exactly_like_geojson(results):
    _, res = results
    ref, gref = res["geojson"][0], res["geojson"][1]
    assert rp.parity._diff(ref, res["kml"][0], gref, res["kml"][1], rp.parity.CROSS_FIELDS) == []


def test_geojson_review_matches_the_owner_styling(results):
    _, res = results
    got = {n: (i["kind"], i["icon"], i["color"]) for n, i in _by_name(res["geojson"][0]).items()}
    assert got == {
        "blerg": ("waypoints", "Camp", "rgba(132,212,0,1)"),          # campfire, #3ef000 -> Lime
        "Hiker": ("waypoints", "Hike", "rgba(8,122,255,1)"),          # hiking, #009aff -> Blue
        "section 1": ("tracks", "", "rgba(255,0,0,1)"),
        "straight line": ("tracks", "", "rgba(132,212,0,1)"),         # #00cd00 -> Lime
        "Chaos line": ("tracks", "", "rgba(0,0,0,1)"),
        "Fire zone": ("shapes", "", "rgba(8,122,255,1)"),             # #0090ff -> Blue
    }
    assert _by_name(res["geojson"][0])["blerg"]["desc"] == "berg\n\nbelrgb berg"


def test_gpx_losses_are_only_what_caltopo_gpx_lacks(results):
    """CalTopo's GPX: no <sym> (icons -> name guesses/default pin), no waypoint colour,
    a Garmin colour only for an exact match (only #000000 -> Black here), and an area
    written as a closed <trk>."""
    _, res = results
    g = _by_name(res["gpx"][0])
    assert {n: (i["kind"], i["icon"], i["color"]) for n, i in g.items()} == {
        "blerg": ("waypoints", "Location", "rgba(8,122,255,1)"),
        "Hiker": ("waypoints", "Location", "rgba(8,122,255,1)"),
        "section 1": ("tracks", "", "rgba(8,122,255,1)"),
        "straight line": ("tracks", "", "rgba(8,122,255,1)"),
        "Chaos line": ("tracks", "", "rgba(0,0,0,1)"),
        "Fire zone": ("tracks", "", "rgba(8,122,255,1)"),             # area -> closed track
    }
    ref = _by_name(res["geojson"][0])
    for n, i in g.items():
        assert i["desc"] == ref[n]["desc"], n                         # notes survive GPX


def test_every_export_matches_its_review_screen(results):
    _, res = results
    for tag, (review, rgeo, reread, egeo) in res.items():
        assert rp.parity._diff(review, reread, rgeo, egeo) == [], tag
