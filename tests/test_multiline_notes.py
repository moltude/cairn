"""Multi-line notes survive parse -> write -> read; names never contain newlines."""

import json
from pathlib import Path

from cairn.core.parser import UNORGANIZED_FOLDER_NAME, ParsedFeature, parse_geojson
from cairn.core.writers import write_gpx_waypoints
from cairn.io.onx_gpx import read_onx_gpx

FIXTURE = Path(__file__).parent / "fixtures/bitterroots/Bitterroots__Complete_.json"


def _all_features(doc):
    for fdata in doc.folders.values():
        for kind in ("waypoints", "tracks", "shapes"):
            yield from fdata.get(kind) or []


def test_trapper_note_keeps_blank_line():
    doc = parse_geojson(FIXTURE)
    notes = [f.description for f in _all_features(doc) if f.title == "Trapper"]
    assert any(
        n.startswith("https://www.summitpost.org/trapper-peak/353250\n\nGnarly")
        for n in notes
    )


def test_names_never_contain_newlines():
    doc = parse_geojson(FIXTURE)
    for f in _all_features(doc):
        assert "\n" not in f.title and "\r" not in f.title


def test_multiline_note_round_trips_through_gpx(tmp_path):
    feat = ParsedFeature(
        {
            "id": "wp-ml",
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-114.5, 45.5]},
            "properties": {
                "class": "Marker",
                "title": "Camp",
                "description": "line one<br>line two\r\nline three",
                "marker-color": "FF0000",
                "marker-symbol": "campsite",
            },
        }
    )
    assert feat.description == "line one\nline two\nline three"
    out = tmp_path / "w.gpx"
    write_gpx_waypoints([feat], out, "F", sort=False)
    assert "<desc>line one\nline two\nline three</desc>" in out.read_text()
    doc = read_onx_gpx(out)
    wps = doc.waypoints()
    assert wps and wps[0].notes == "line one\nline two\nline three"


def test_unorganized_constant_used_for_orphans(tmp_path):
    assert UNORGANIZED_FOLDER_NAME == "Unorganized"
    gj = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "f1",
                "geometry": None,
                "properties": {"class": "Folder", "title": "Real folder"},
            },
            {
                "type": "Feature",
                "id": "a",
                "geometry": {"type": "Point", "coordinates": [-114.5, 45.5]},
                "properties": {"class": "Marker", "title": "Loose"},
            }
        ],
    }
    p = tmp_path / "x.json"
    p.write_text(json.dumps(gj))
    doc = parse_geojson(p)
    names = [f.get("name") for f in doc.folders.values()]
    assert UNORGANIZED_FOLDER_NAME in names


# --- web/bridge.py surface -------------------------------------------------
import io  # noqa: E402
import sys  # noqa: E402
import zipfile  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402


def test_bridge_exposes_kinds_line_colors_and_unorganized():
    data = json.loads(bridge.load_document(FIXTURE.read_text(encoding="utf-8"), FIXTURE.name))
    assert [c["name"] for c in data["colors"]] == [c["name"] for c in data["line_colors"]][:10]
    assert len(data["colors"]) == 10 and len(data["line_colors"]) == 11
    assert data["line_colors"][-1] == {
        "name": "Fuchsia", "rgba": "rgba(255,0,255,1)", "hex": "#FF00FF"
    }
    kinds = {i["kind"] for g in data["groups"] for i in g["items"]}
    assert kinds <= {"waypoints", "tracks", "shapes"} and "waypoints" in kinds
    assert "Uncategorized" not in {g["name"] for g in data["groups"]}
    for g in data["groups"]:
        for i in g["items"]:
            assert "\n" not in i["name"]


def test_fuchsia_line_color_exports():
    gj = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "id": "f1", "geometry": None,
             "properties": {"class": "Folder", "title": "Real folder"}},
            {"type": "Feature", "id": "t1",
             "geometry": {"type": "LineString", "coordinates": [[-114.5, 45.5], [-114.6, 45.6]]},
             "properties": {"class": "Shape", "title": "Line", "stroke": "#FF0000"}},
        ],
    }
    data = json.loads(bridge.load_document(json.dumps(gj), "fx.json"))
    assert data["groups"][-1]["name"] == "Unorganized"   # the loose items sort last
    (item,) = [i for g in data["groups"] for i in g["items"]]
    assert item["kind"] == "tracks"
    bridge.apply_edits(json.dumps({item["uid"]: {"color": "rgba(255,0,255,1)"}}))
    z = zipfile.ZipFile(io.BytesIO(bridge.export_zip()))
    gpx = "".join(z.read(n).decode() for n in z.namelist() if n.endswith(".gpx"))
    assert "rgba(255,0,255,1)" in gpx
    assert "Unorganized" in "".join(z.read(n).decode() for n in z.namelist() if n == "instructions.txt")
