"""Areas keep their onX line colour, style, weight and fill through Cairn.

onX's own exports of four areas (tests/fixtures/onx_exports/areas-*.{gpx,kml},
the owner's test data) cover every onX area property: style solid / dash / dot,
weight 2.0 / 4.0 / 6.0, three fill swatches and the "none" fill. Loaded through
web/bridge.py and exported with export_zip, each must come out byte for value
as onX wrote it, unless the user edited it. CalTopo areas get onX values by
mapping. docs/ONX_ROUND_TRIP.md#area-fidelity has the live onX results: onX's
importer keeps the colour, style and weight, and ignores the fill.
"""

from __future__ import annotations

import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from cairn.core import writers as W
from cairn.core.color_mapper import ColorMapper
from cairn.core.parser import ParsedFeature
from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402

FX = ROOT / "tests" / "fixtures" / "onx_exports"
NS = {"g": "http://www.topografix.com/GPX/1/1", "onx": "https://wwww.onxmaps.com/"}
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
PROPS = ("color", "style", "weight", "fill_color")

# The four areas exactly as onX exported them (and as onX's web app shows them).
BEFORE = {
    "temp": ("rgba(255,255,0,1)", "solid", "2.0", "rgba(232,118,255,0.1)"),
    "Area 10/23/26 10:09": ("rgba(255,51,0,1)", "solid", "4.0", "rgba(238,255,125,0.1)"),
    "Area 10/23/26 10:10": ("rgba(0,0,0,1)", "solid", "4.0", "rgba(232,118,255,0.1)"),
    "test 4": ("rgba(132,212,0,1)", "solid", "4.0", "rgba(0,0,0,0)"),
}
AFTER = {
    **BEFORE,
    "Area 10/23/26 10:10": ("rgba(0,0,0,1)", "dash", "6.0", "rgba(232,118,255,0.1)"),
    "test 4": ("rgba(132,212,0,1)", "dot", "4.0", "rgba(232,118,255,0.1)"),
}


def _file(path: Path) -> dict:
    return {"name": path.name, "text": path.read_text(encoding="utf-8")}


def _onx_values(path: Path) -> dict:
    """{name: (color, style, weight, fill_color, n_points)} from an onX/Cairn area GPX."""
    out = {}
    for rte in ET.parse(path).getroot().findall("g:rte", NS):
        ext = rte.find("g:extensions", NS)
        out[rte.findtext("g:name", namespaces=NS)] = tuple(
            ext.findtext(f"onx:{k}", namespaces=NS) for k in PROPS) + (len(rte.findall("g:rtept", NS)),)
    return out


def _export_areas(tmp_path: Path) -> tuple[Path, str]:
    z = zipfile.ZipFile(io.BytesIO(bridge.export_zip()))
    (name,) = [n for n in z.namelist() if n.endswith("_Areas.gpx")]
    out = tmp_path / Path(name).name
    out.write_bytes(z.read(name))
    return out, out.read_text(encoding="utf-8")


def _load(*paths: Path) -> list:
    data = json.loads(bridge.load_files(json.dumps([_file(p) for p in paths])))
    return [i for g in data["groups"] for i in g["items"]]


@pytest.mark.parametrize("stem,want", [("areas-before-edit", BEFORE), ("areas-after-edit", AFTER)])
@pytest.mark.parametrize("files", ["gpx", "kml", "pair"])
def test_onx_area_values_survive_load_and_export_exactly(tmp_path, stem, want, files):
    paths = {"gpx": [FX / f"{stem}.gpx"], "kml": [FX / f"{stem}.kml"],
             "pair": [FX / f"{stem}.gpx", FX / f"{stem}.kml"]}[files]
    items = _load(*paths)
    # The UI shows what will be written.
    assert {i["name"]: (i["color"], i["style"], i["weight"], i["fill"]) for i in items} == want
    out, text = _export_areas(tmp_path)
    src = _onx_values(FX / f"{stem}.gpx")
    got = _onx_values(out)
    assert got == {n: v + (src[n][4],) for n, v in want.items()}
    # Element order is onX's own.
    for rte in ET.parse(out).getroot().findall("g:rte", NS):
        assert [c.tag.split("}")[1] for c in rte.find("g:extensions", NS)] == list(PROPS)
    # <desc> is the note only; no onX id is written anywhere.
    assert "id=" not in text and "fill_color=" not in text
    assert not UUID_RE.search(text)
    notes = {r.findtext("g:name", namespaces=NS): r.findtext("g:desc", namespaces=NS)
             for r in ET.parse(out).getroot().findall("g:rte", NS)}
    assert notes["test 4"] == "wfwef\n\nwef\n\nwfwef\n\n\nwef"
    assert notes["temp"] is None


def test_cairn_area_gpx_reads_back_to_the_same_onx_values(tmp_path):
    _load(FX / "areas-after-edit.gpx")
    out, _ = _export_areas(tmp_path)
    back = {s.name: (s.style.OnX_color_rgba, s.style.OnX_style, s.style.OnX_weight,
                     s.style.extra.get("fill_color")) for s in read_onx_gpx(out).items}
    assert back == AFTER


def test_cairn_area_kml_carries_the_same_values(tmp_path):
    _load(FX / "areas-after-edit.gpx")
    feats = next(iter(bridge._STATE["doc"].folders.values()))["shapes"]
    out = tmp_path / "a.kml"
    W.write_kml_shapes_maybe_split(feats, out, "F")
    back = {s.name: (s.style.OnX_color_rgba, s.style.OnX_style, s.style.OnX_weight,
                     s.style.extra.get("fill_color")) for s in read_onx_kml(out).items}
    assert back == AFTER


def test_edits_to_style_and_weight_land_in_the_export(tmp_path):
    items = {i["name"]: i for i in _load(FX / "areas-after-edit.gpx")}
    bridge.apply_edits(json.dumps({
        items["test 4"]["uid"]: {"style": "dash", "weight": "6.0"},     # was dot / 4.0
        items["temp"]["uid"]: {"style": "dash"},                        # was solid / 2.0
        items["Area 10/23/26 10:10"]["uid"]: {"style": "solid", "weight": "4.0"},
        items["Area 10/23/26 10:09"]["uid"]: {"color": "rgba(255,0,255,1)"},
    }))
    out, _ = _export_areas(tmp_path)
    got = {n: v[:4] for n, v in _onx_values(out).items()}
    assert got == {
        "test 4": ("rgba(132,212,0,1)", "dash", "6.0", "rgba(232,118,255,0.1)"),
        "temp": ("rgba(255,255,0,1)", "dash", "2.0", "rgba(232,118,255,0.1)"),   # 2.0 kept
        "Area 10/23/26 10:10": ("rgba(0,0,0,1)", "solid", "4.0", "rgba(232,118,255,0.1)"),
        # A line-colour edit leaves the fill (a separate onX palette) alone.
        "Area 10/23/26 10:09": ("rgba(255,0,255,1)", "solid", "4.0", "rgba(238,255,125,0.1)"),
    }


@pytest.mark.parametrize("edit", [{"style": "dot"}, {"weight": "2.0"}, {"style": "dashed"},
                                  {"weight": "5.0"}])
def test_area_edits_offer_only_solid_dash_and_4_6(edit):
    items = _load(FX / "areas-after-edit.gpx")
    with pytest.raises(ValueError):
        bridge.apply_edits(json.dumps({items[0]["uid"]: edit}))


# ---- CalTopo areas ----------------------------------------------------------

SQUARE = [[-114.0, 45.0], [-114.1, 45.0], [-114.1, 45.1], [-114.0, 45.1], [-114.0, 45.0]]


def _caltopo(*shapes) -> str:
    feats = [{"type": "Feature", "id": "f", "geometry": None,
              "properties": {"class": "Folder", "title": "Zones"}}]
    for k, props in enumerate(shapes):
        feats.append({"type": "Feature", "id": f"s{k}",
                      "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
                      "properties": {"class": "Shape", "folderId": "f", **props}})
    return json.dumps({"type": "FeatureCollection", "features": feats})


def test_caltopo_areas_get_onx_swatch_fills_and_mapped_style_and_weight(tmp_path):
    bridge.load_document(_caltopo(
        {"title": "dashed thick", "stroke": "#FF0000", "fill": "#FF0000", "fill-opacity": 0.1,
         "stroke-width": 6, "pattern": "M0 -1 L0 1,,8,F"},
        {"title": "outline only", "stroke": "#0090ff", "fill": "#0090ff", "fill-opacity": 0,
         "stroke-width": 4},
        {"title": "no fill colour", "stroke": "#00FF00", "stroke-width": 2},
        {"title": "magenta fill", "stroke": "#000000", "fill": "#E080FF", "fill-opacity": 0.3},
    ), "zones.json")
    out, _ = _export_areas(tmp_path)
    got = {n: v[:4] for n, v in _onx_values(out).items()}
    assert got == {
        "dashed thick": ("rgba(255,0,0,1)", "dash", "6.0", "rgba(212,83,47,0.1)"),
        "outline only": ("rgba(8,122,255,1)", "solid", "4.0", "rgba(0,0,0,0)"),
        "no fill colour": ("rgba(132,212,0,1)", "solid", "4.0", "rgba(42,139,97,0.1)"),
        "magenta fill": ("rgba(0,0,0,1)", "solid", "4.0", "rgba(232,118,255,0.1)"),
    }
    fills = {p.rgba for p in ColorMapper.AREA_FILL_PALETTE} | {ColorMapper.AREA_FILL_NONE}
    assert {v[3] for v in got.values()} <= fills


def test_every_written_fill_is_an_onx_swatch_or_none():
    fills = {p.rgba for p in ColorMapper.AREA_FILL_PALETTE} | {ColorMapper.AREA_FILL_NONE}
    for raw in ("#123456", "rgba(0,0,0,0.1)", "rgba(255,255,0,0.3)", "", "garbage",
                "rgba(1,2,3,0)", "rgba(232, 118, 255, 0.1)"):
        f = ParsedFeature({"type": "Feature", "properties": {
            "class": "Shape", "title": "x", W.AREA_FILL_KEY: raw},
            "geometry": {"type": "Polygon", "coordinates": [SQUARE]}})
        assert W.area_onx_style(f)[3] in fills, raw


# --- the Fill row: onX's blue is the only fill an area can be set to (2026-10-24) ---


def _load_areas_pair() -> list:
    files = [{"name": p.name, "text": p.read_text(encoding="utf-8")}
             for p in (FX / "areas-after-edit.gpx", FX / "areas-after-edit.kml")]
    data = json.loads(bridge.load_files(json.dumps(files)))
    return [i for g in data["groups"] for i in g["items"]]


def _area_fills() -> dict:
    """{name: <onx:fill_color>} of every area in the export."""
    zf = zipfile.ZipFile(io.BytesIO(bridge.export_zip()))
    gpx = "".join(zf.read(n).decode() for n in zf.namelist() if n.endswith("_Areas.gpx"))
    return {re.search(r"<name>(.*?)</name>", b, re.S).group(1): re.search(
                r"<onx:fill_color>(.*?)</onx:fill_color>", b).group(1)
            for b in re.findall(r"<rte>.*?</rte>", gpx, re.S)}


def test_an_area_fill_can_be_set_to_onxs_default_blue_and_exports_it():
    items = _load_areas_pair()
    areas = [i for i in items if i["kind"] == "shapes"]
    target = next(a for a in areas if a["fill"] != ColorMapper.DEFAULT_AREA_FILL)
    before = _area_fills()
    assert before[target["name"]] != ColorMapper.DEFAULT_AREA_FILL
    res = json.loads(bridge.apply_edits(json.dumps({target["uid"]: {"fill": ColorMapper.DEFAULT_AREA_FILL}})))
    assert res["applied"] == 1
    item = next(i for g in bridge._STATE["groups"] for i in g["items"] if i["uid"] == target["uid"])
    assert item["fill"] == ColorMapper.DEFAULT_AREA_FILL
    after = _area_fills()
    assert after[target["name"]] == ColorMapper.DEFAULT_AREA_FILL
    assert {k: v for k, v in after.items() if k != target["name"]} == {
        k: v for k, v in before.items() if k != target["name"]}


@pytest.mark.parametrize("fill", ["rgba(212,83,47,0.1)", "rgba(0,0,0,0)", "#4A90E2", "blue", ""])
def test_any_other_area_fill_is_refused_and_nothing_is_applied(fill):
    items = _load_areas_pair()
    area = next(i for i in items if i["kind"] == "shapes")
    with pytest.raises(ValueError, match="onX keeps only its default"):
        bridge.apply_edits(json.dumps({area["uid"]: {"fill": fill, "name": "changed"}}))
    item = next(i for g in bridge._STATE["groups"] for i in g["items"] if i["uid"] == area["uid"])
    assert item["fill"] == area["fill"] and item["name"] == area["name"]


def test_a_fill_on_a_waypoint_or_line_is_ignored():
    pair = [ROOT / "tests" / "fixtures" / "onx_dialect" / f"onx_dialect.{x}" for x in ("gpx", "kml")]
    data = json.loads(bridge.load_files(json.dumps(
        [{"name": p.name, "text": p.read_text(encoding="utf-8")} for p in pair])))
    items = [i for g in data["groups"] for i in g["items"]]
    others = [i for i in items if i["kind"] != "shapes"]
    assert others
    bridge.apply_edits(json.dumps({i["uid"]: {"fill": ColorMapper.DEFAULT_AREA_FILL} for i in others}))
    for i in others:
        live = next(x for g in bridge._STATE["groups"] for x in g["items"] if x["uid"] == i["uid"])
        assert live.get("fill") == i.get("fill")
