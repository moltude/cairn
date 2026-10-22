"""CalTopo areas (class "Shape", Polygon geometry) end to end: parser ->
web/bridge.load_document -> edits -> export -> RUNBOOK.md.

Each test here pins one defect found in the 2026-10-22 review; each failed
before its fix.
"""

from __future__ import annotations

import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from cairn.core.parser import ParsedFeature
from cairn.core import writers as W

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402

BLUE_KML = "ffff7a08"  # onX Blue rgba(8,122,255) as aabbggrr
RED_KML = "ff0000ff"
FUCHSIA = "rgba(255,0,255,1)"

SQUARE = [[-114.0, 45.0], [-114.1, 45.0], [-114.1, 45.1], [-114.0, 45.1], [-114.0, 45.0]]
HOLE = [[-114.03, 45.03], [-114.06, 45.03], [-114.06, 45.06], [-114.03, 45.03]]


def _shape(title="Area", rings=None, **props):
    p = {"class": "Shape", "title": title, **props}
    return ParsedFeature(
        {"type": "Feature", "properties": p,
         "geometry": {"type": "Polygon", "coordinates": rings if rings is not None else [SQUARE]}}
    )


def _xml(text: str) -> ET.Element:
    """Parse KML with the default namespace stripped, so paths stay readable."""
    return ET.fromstring(text.replace(' xmlns="http://www.opengis.net/kml/2.2"', "", 1))


def _kml(features, tmp_path) -> str:
    out = tmp_path / "areas.kml"
    W.write_kml_shapes(features, out, "Test")
    return out.read_text(encoding="utf-8")


def _styles(kml: str):
    """[(line_color, width, poly_color)] per placemark."""
    root = _xml(kml)
    res = []
    for pm in root.iter("Placemark"):
        ls, ps = pm.find("Style/LineStyle"), pm.find("Style/PolyStyle")
        res.append((ls.findtext("color"), ls.findtext("width"), ps.findtext("color")))
    return res


# ---- (a) area colours are quantized to onX's track palette -----------------

def test_area_color_is_nearest_track_palette_color(tmp_path):
    # #FE0101 is not an onX colour; nearest is Red. The old writer passed the
    # raw hex through as ff0101fe.
    (line, _w, poly), = _styles(_kml([_shape(stroke="#FE0101")], tmp_path))
    assert line == RED_KML
    assert poly[2:] == RED_KML[2:]


def test_missing_or_malformed_area_color_is_blue_like_the_ui(tmp_path):
    # The old writer emitted white (ffffffff) here while the UI showed Blue.
    styles = _styles(_kml([_shape("none"), _shape("bad", stroke="#zzz")], tmp_path))
    assert [s[0] for s in styles] == [BLUE_KML, BLUE_KML]


def _doc(*features):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "f1", "geometry": None,
         "properties": {"class": "Folder", "title": "Zones"}},
        *features,
    ]}


def _poly_feature(fid, title, rings, **props):
    return {"type": "Feature", "id": fid,
            "geometry": {"type": "Polygon", "coordinates": rings},
            "properties": {"class": "Shape", "title": title, "folderId": "f1", **props}}


def _load(doc, name="zones.json"):
    data = json.loads(bridge.load_document(json.dumps(doc), name))
    return [i for g in data["groups"] for i in g["items"]]


def _export(edits=None):
    if edits:
        bridge.apply_edits(json.dumps(edits))
    return zipfile.ZipFile(io.BytesIO(bridge.export_zip()))


GPX_NS = {"g": "http://www.topografix.com/GPX/1/1", "onx": "https://wwww.onxmaps.com/"}


def _gpx_areas(z):
    """Every <rte> in the export's *_Areas.gpx files."""
    return [r for n in z.namelist() if n.endswith("_Areas.gpx")
            for r in ET.fromstring(z.read(n)).findall("g:rte", GPX_NS)]


def test_ui_area_color_equals_exported_area_color():
    items = _load(_doc(
        _poly_feature("a", "Odd red", [SQUARE], stroke="#FE0101"),
        _poly_feature("b", "No colour", [SQUARE]),
    ))
    shown = {i["name"]: i["color"] for i in items}
    # Areas are exported as GPX onX Area routes (ENG-05), so the colour that
    # matters is <onx:color>.
    exported = {r.findtext("g:name", namespaces=GPX_NS): r.findtext("g:extensions/onx:color", namespaces=GPX_NS)
                for r in _gpx_areas(_export())}
    assert shown == {"Odd red": "rgba(255,0,0,1)", "No colour": "rgba(8,122,255,1)"}
    assert exported == shown


def test_user_area_color_edit_wins_on_line_and_fill():
    items = _load(_doc(_poly_feature("a", "Zone", [SQUARE], stroke="#FF0000", fill="#FF0000")))
    (rte,) = _gpx_areas(_export({items[0]["uid"]: {"color": FUCHSIA}}))
    assert rte.findtext("g:extensions/onx:color", namespaces=GPX_NS) == FUCHSIA
    assert rte.findtext("g:extensions/onx:fill_color", namespaces=GPX_NS) == "rgba(255,0,255,0.5)"


# ---- (b) holes ------------------------------------------------------------

def test_inner_rings_are_written_as_inner_boundaries(tmp_path):
    kml = _kml([_shape("Donut", rings=[SQUARE, HOLE])], tmp_path)
    poly = _xml(kml).find(".//Polygon")
    inner = poly.findall("innerBoundaryIs")
    assert len(poly.findall("outerBoundaryIs")) == 1
    assert len(inner) == 1
    assert "-114.06,45.06,0" in inner[0].findtext("LinearRing/coordinates")


def test_multipolygon_shaped_coordinates_write_real_positions(tmp_path):
    # Used to emit Python list reprs ("[-114.0, 45.0]") as coordinates.
    kml = _kml([_shape("Nested", rings=[[SQUARE]])], tmp_path)
    coords = _xml(kml).find(".//outerBoundaryIs/LinearRing/coordinates").text
    assert coords.split()[0] == "-114.0,45.0,0"
    assert "[" not in coords


# ---- (c) stroke width / fill opacity ---------------------------------------

def test_caltopo_stroke_width_and_fill_opacity_are_carried(tmp_path):
    # Properties exactly as Bitterroots__Complete_.json exports them.
    feats = [
        _shape("thin", stroke="#FF0000", fill="#FF0000", **{"stroke-width": 1, "fill-opacity": 0.1, "stroke-opacity": 1}),
        _shape("outline", stroke="#FF0000", fill="#FF0000", **{"stroke-width": 2, "fill-opacity": 0, "stroke-opacity": 1}),
        _shape("defaults", stroke="#FF0000"),
    ]
    styles = _styles(_kml(feats, tmp_path))
    assert styles[0] == (RED_KML, "1", "1a0000ff")
    assert styles[1] == (RED_KML, "2", "000000ff")
    # Nothing provided -> the writer's historical width 2 and 50% fill.
    assert styles[2] == (RED_KML, "2", "7f0000ff")


# ---- (d) unusable polygons are dropped, and counted as dropped --------------

def test_writer_does_not_count_unusable_polygons(tmp_path):
    feats = [_shape("ok"), _shape("empty", rings=[]), _shape("degenerate", rings=[[[-114, 45]]])]
    (path, _size, count), = W.write_kml_shapes_maybe_split(feats, tmp_path / "a.kml", "T")
    assert count == 1
    assert [pm.findtext("name") for pm in _xml(path.read_text()).iter("Placemark")] == ["ok"]


def test_runbook_reports_dropped_polygons():
    _load(_doc(
        _poly_feature("a", "Good", [SQUARE]),
        _poly_feature("b", "Broken", []),
    ))
    z = _export()
    runbook = z.read("RUNBOOK.md").decode()
    assert "**1 item(s) could not be exported**" in runbook
    assert "1 of 2 were written" in runbook
    summary = json.loads(bridge.runbook_summary_json())
    assert (summary["written"], summary["expected"], summary["dropped"]) == (1, 2, 1)


def test_folder_whose_only_polygon_is_unusable_still_counts_as_dropped():
    _load(_doc(_poly_feature("b", "Broken", [])))
    z = _export()
    assert not [n for n in z.namelist() if n.endswith((".kml", "_Areas.gpx"))], "empty area file written"
    assert json.loads(bridge.runbook_summary_json())["dropped"] == 1
    assert "**1 item(s) could not be exported**" in z.read("RUNBOOK.md").decode()


# ---- (e) KML is size-split like GPX ----------------------------------------

def test_large_area_files_split_into_numbered_parts(tmp_path):
    feats = [_shape(f"Zone {i:02d}", stroke="#FF0000") for i in range(30)]
    one = tmp_path / "one.kml"
    W.write_kml_shapes(feats, one, "T")
    cap = one.stat().st_size // 3
    parts = W.write_kml_shapes_maybe_split(feats, tmp_path / "Areas.kml", "T", max_bytes=cap)
    assert len(parts) >= 3
    assert [p.name for p, _s, _c in parts][:2] == ["Areas_1.kml", "Areas_2.kml"]
    names = []
    for p, size, cnt in parts:
        assert size <= cap
        pms = list(_xml(p.read_text()).iter("Placemark"))
        assert len(pms) == cnt
        names += [pm.findtext("name") for pm in pms]
    assert names == [f"Zone {i:02d}" for i in range(30)]


# ---- (h) area names pass through unchanged (ENG-06) ------------------------

def test_area_names_pass_through_unchanged(tmp_path):
    W.clear_name_changes()
    kml = _kml([_shape("Zone #1 & 2!")], tmp_path)
    assert _xml(kml).find(".//Placemark/name").text == "Zone #1 & 2!"
    assert W.get_name_changes()["shapes"] == []


def test_runbook_has_no_renamed_section_for_special_characters():
    _load(_doc(
        _poly_feature("a", "Zone #1", [SQUARE]),
        {"type": "Feature", "id": "w", "geometry": {"type": "Point", "coordinates": [-114.0, 45.0]},
         "properties": {"class": "Marker", "title": "#01 Porcupine", "folderId": "f1"}},
    ))
    runbook = _export().read("RUNBOOK.md").decode()
    assert "Renamed for onX" not in runbook


def test_runbook_has_no_renamed_section_when_nothing_changed():
    _load(_doc(_poly_feature("a", "Plain", [SQUARE])))
    assert "Renamed for onX" not in _export().read("RUNBOOK.md").decode()


def test_bad_first_vertex_drops_only_that_vertex(tmp_path):
    # Depth detection must not mistake this for a MultiPolygon-shaped array
    # (which would drop the whole polygon).
    ring = [[None, 45.0]] + SQUARE
    (path, _size, count), = W.write_kml_shapes_maybe_split([_shape("Edgy", rings=[ring])], tmp_path / "a.kml", "T")
    assert count == 1
    coords = _xml(path.read_text()).find(".//outerBoundaryIs/LinearRing/coordinates").text
    assert coords.split()[0] == "-114.0,45.0,0"
