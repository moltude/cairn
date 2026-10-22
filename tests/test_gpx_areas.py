"""Areas are exported as onX Area routes in GPX (ENG-05).

Verified 2026-10-22 in a real onX Web Map import: onX ignores an area's colour
and fill in KML, but a GPX <rte> with <type>Area</type> and <onx:color> /
<onx:fill_color> imports as an Area with its colour. These tests pin the
writer's output shape, the web export's switch to it, the RUNBOOK's "Holes not
kept in onX" list, and that Cairn reads its own (and onX's) area GPX back.
"""

from __future__ import annotations

import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from cairn.core import writers as W
from cairn.core.parser import ParsedFeature
from cairn.io.input_check import CAIRN, GPX, detect
from cairn.io.onx_gpx import read_onx_gpx
from cairn.model import Shape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402

NS = {"g": "http://www.topografix.com/GPX/1/1", "onx": "https://wwww.onxmaps.com/"}
SQUARE = [[-114.0, 45.0], [-114.1, 45.0], [-114.1, 45.1], [-114.0, 45.1], [-114.0, 45.0]]
HOLE = [[-114.03, 45.03], [-114.06, 45.03], [-114.06, 45.06], [-114.03, 45.03]]
ONX_EXPORT = ROOT / "tests/fixtures/caltopo-random/onx_roundtrip/from_geojson/onx_export.gpx"


def _shape(title="Area", rings=None, **props):
    p = {"class": "Shape", "title": title, **props}
    return ParsedFeature(
        {"type": "Feature", "properties": p,
         "geometry": {"type": "Polygon", "coordinates": rings if rings is not None else [SQUARE]}}
    )


def _write(tmp_path, feats, **kw):
    W.clear_name_changes()
    W.clear_areas_without_holes()
    return W.write_gpx_areas_maybe_split(feats, tmp_path / "Z_Areas.gpx", "Zones", **kw)


def _rtes(path: Path):
    return ET.parse(path).getroot().findall("g:rte", NS)


# ---- writer ----------------------------------------------------------------

def test_area_is_an_onx_area_route_in_onx_element_order(tmp_path):
    (path, _s, count), = _write(tmp_path, [_shape(
        "Burn", stroke="#FF0000", description="line one\nline two", **{"fill-opacity": 0.1})])
    assert count == 1
    (rte,) = _rtes(path)
    tags = [c.tag.split("}")[1] for c in rte]
    assert tags[:4] == ["name", "desc", "type", "extensions"]
    assert set(tags[4:]) == {"rtept"}
    assert rte.findtext("g:type", namespaces=NS) == "Area"
    assert rte.findtext("g:desc", namespaces=NS) == "line one\nline two"
    ext = rte.find("g:extensions", NS)
    assert ext.findtext("onx:color", namespaces=NS) == "rgba(255,0,0,1)"
    assert ext.findtext("onx:fill_color", namespaces=NS) == "rgba(255,0,0,0.1)"
    assert [c.tag.split("}")[1] for c in ext] == ["color", "fill_color"]
    pts = [(float(p.get("lon")), float(p.get("lat"))) for p in rte.findall("g:rtept", NS)]
    assert pts == [tuple(p) for p in SQUARE]


def test_desc_is_the_note_only_and_omitted_when_empty(tmp_path):
    # onX does NOT parse a key=value <desc> on import -- it becomes the note
    # verbatim -- so no machine state may go there.
    (path, _s, _c), = _write(tmp_path, [_shape("Bare")])
    (rte,) = _rtes(path)
    assert rte.find("g:desc", NS) is None
    assert "name=" not in path.read_text()


def test_fill_alpha_defaults_to_half_and_follows_the_area_colour(tmp_path):
    (path, _s, _c), = _write(tmp_path, [
        _shape("a", stroke="#FF0000", fill="#00FF00"),
        _shape("b", stroke="#FF0000", **{"fill-opacity": 0}),
        _shape("c"),
    ])
    fills = [r.findtext("g:extensions/onx:fill_color", namespaces=NS) for r in _rtes(path)]
    assert fills == ["rgba(255,0,0,0.5)", "rgba(255,0,0,0)", "rgba(8,122,255,0.5)"]


def test_area_colour_is_the_one_the_ui_shows(tmp_path):
    feats = [_shape("odd", stroke="#FE0101"), _shape("none")]
    (path, _s, _c), = _write(tmp_path, feats)
    got = {r.findtext("g:name", namespaces=NS): r.findtext("g:extensions/onx:color", namespaces=NS)
           for r in _rtes(path)}
    assert got == {f.title: W.kml_area_color(f) for f in feats} == {
        "odd": "rgba(255,0,0,1)", "none": "rgba(8,122,255,1)"}


def test_open_ring_is_closed(tmp_path):
    (path, _s, _c), = _write(tmp_path, [_shape("Open", rings=[SQUARE[:-1]])])
    pts = _rtes(path)[0].findall("g:rtept", NS)
    assert len(pts) == 5 and pts[0].attrib == pts[-1].attrib


def test_holes_are_not_written_and_are_recorded(tmp_path):
    (path, _s, count), = _write(tmp_path, [_shape("Donut #1", rings=[SQUARE, HOLE]), _shape("Plain")])
    assert count == 2
    donut = _rtes(path)[0]
    assert len(donut.findall("g:rtept", NS)) == len(SQUARE)
    assert W.get_areas_without_holes() == ["Donut 1"]  # sanitized name, as onX shows it


def test_unusable_polygons_are_skipped_and_not_counted(tmp_path):
    (path, _s, count), = _write(tmp_path, [_shape("ok"), _shape("empty", rings=[]),
                                           _shape("degenerate", rings=[[[-114, 45]]])])
    assert count == 1
    assert [r.findtext("g:name", namespaces=NS) for r in _rtes(path)] == ["ok"]


def test_names_are_sanitized_and_tracked(tmp_path):
    (path, _s, _c), = _write(tmp_path, [_shape("Zone #1 & 2!")])
    assert _rtes(path)[0].findtext("g:name", namespaces=NS) == "Zone 1 2"
    assert W.get_name_changes()["shapes"] == [("Zone #1 & 2!", "Zone 1 2")]


def test_large_area_files_split_into_numbered_parts(tmp_path):
    feats = [_shape(f"Zone {i:02d}", stroke="#FF0000") for i in range(30)]
    (one, size, _c), = _write(tmp_path, feats)
    cap = size // 3
    parts = _write(tmp_path, feats, max_bytes=cap)
    assert len(parts) >= 3
    assert [p.name for p, _s, _c in parts][:2] == ["Z_Areas_1.gpx", "Z_Areas_2.gpx"]
    names = []
    for p, sz, cnt in parts:
        assert sz <= cap
        rtes = _rtes(p)
        assert len(rtes) == cnt
        names += [r.findtext("g:name", namespaces=NS) for r in rtes]
    assert names == [f"Zone {i:02d}" for i in range(30)]


# ---- readers: Cairn's own area GPX, and onX's ----------------------------

def test_cairn_area_gpx_reads_back_as_an_area(tmp_path):
    (path, _s, _c), = _write(tmp_path, [_shape(
        "Burn", stroke="#FF0000", description="two\nlines", **{"fill-opacity": 0.1})])
    assert detect(path.name, path.read_text()) == (GPX, CAIRN)
    (shp,) = read_onx_gpx(path).items
    assert isinstance(shp, Shape)
    assert (shp.name, shp.notes) == ("Burn", "two\nlines")
    assert shp.style.OnX_color_rgba == "rgba(255,0,0,1)"
    assert shp.style.extra["fill_color"] == "rgba(255,0,0,0.1)"
    assert [tuple(p) for p in shp.rings[0]] == [tuple(p) for p in SQUARE]


def test_a_note_reading_type_area_does_not_make_a_track_an_area(tmp_path):
    # Cairn's desc is the note only, so <type> alone must carry "Area".
    W.write_gpx_tracks_maybe_split(
        [ParsedFeature({"type": "Feature", "properties": {"class": "Shape", "title": "T",
                        "description": "type=Area"},
                        "geometry": {"type": "LineString", "coordinates": SQUARE}})],
        tmp_path / "t.gpx", "T")
    (trk,) = read_onx_gpx(tmp_path / "t.gpx").items
    assert not isinstance(trk, Shape)


def test_onx_own_area_export_reads_as_an_area_with_its_colour():
    shapes = [i for i in read_onx_gpx(ONX_EXPORT).items if isinstance(i, Shape)]
    assert [s.name for s in shapes] == ["Fire zone"]
    assert shapes[0].style.OnX_color_rgba == "rgba(255,51,0,1)"
    assert shapes[0].style.extra["fill_color"] == "rgba(74,144,226,0.1)"
    assert shapes[0].notes == "blue, center opacity"


# ---- web export ------------------------------------------------------------

def _doc(*features):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "f1", "geometry": None,
         "properties": {"class": "Folder", "title": "Zones"}},
        *features,
    ]}


def _poly(fid, title, rings, **props):
    return {"type": "Feature", "id": fid,
            "geometry": {"type": "Polygon", "coordinates": rings},
            "properties": {"class": "Shape", "title": title, "folderId": "f1", **props}}


def _export(doc):
    bridge.load_document(json.dumps(doc), "zones.json")
    return zipfile.ZipFile(io.BytesIO(bridge.export_zip()))


def test_web_export_writes_areas_gpx_and_no_kml():
    z = _export(_doc(_poly("a", "Burn", [SQUARE], stroke="#FF0000")))
    names = z.namelist()
    assert "01_Zones/Zones_Areas.gpx" in names
    assert not [n for n in names if n.endswith(".kml")]
    root = ET.fromstring(z.read("01_Zones/Zones_Areas.gpx"))
    assert root.find("g:rte/g:type", NS).text == "Area"
    summary = json.loads(bridge.runbook_summary_json())
    assert summary["kml_batches"] == 0
    runbook = z.read("RUNBOOK.md").decode()
    assert "**Zones_Areas.gpx**" in runbook
    assert "KML" not in runbook


def test_runbook_lists_areas_whose_holes_were_not_kept():
    z = _export(_doc(_poly("a", "Donut", [SQUARE, HOLE]), _poly("b", "Plain", [SQUARE])))
    runbook = z.read("RUNBOOK.md").decode()
    assert "### Holes not kept in onX" in runbook
    assert "- `Donut`  (Zones)" in runbook
    assert "`Plain`" not in runbook.split("### Holes not kept in onX")[1]
    assert json.loads(bridge.runbook_summary_json())["holes"] == 1


def test_runbook_has_no_holes_section_without_holes():
    z = _export(_doc(_poly("b", "Plain", [SQUARE])))
    assert "Holes not kept" not in z.read("RUNBOOK.md").decode()


def test_web_export_areas_round_trip_through_load_files():
    _ = _export(_doc(_poly("a", "Burn", [SQUARE], stroke="#FF0000", description="note",
                           **{"fill-opacity": 0.2})))
    shown = [i for g in bridge._STATE["groups"] for i in g["items"]]
    z = zipfile.ZipFile(io.BytesIO(bridge.export_zip()))
    files = [{"name": n.split("/")[-1], "text": z.read(n).decode()}
             for n in z.namelist() if n.endswith(".gpx")]
    back = json.loads(bridge.load_files(json.dumps(files)))
    (item,) = [i for g in back["groups"] for i in g["items"]]
    assert item["kind"] == "shapes"
    assert (item["name"], item["desc"], item["color"]) == (
        shown[0]["name"], shown[0]["desc"], shown[0]["color"])
    feat = next(iter(bridge._STATE["doc"].folders.values()))["shapes"][0]
    assert feat.fill_opacity == 0.2
