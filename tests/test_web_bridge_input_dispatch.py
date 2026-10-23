"""Roadmap Phase 2: web/bridge.py reads GPX and KML, not just CalTopo GeoJSON.

load_files / load_document dispatch on cairn.io.input_check.detect():
CalTopo GeoJSON -> parse_geojson (unchanged, checked byte for byte against the
output of the commit before this phase), CalTopo GPX -> parse_caltopo_gpx,
onX / Cairn / other GPX and KML -> the onX readers -> to_parsed_data, and a GPX
+ KML pair from one onX export -> merge_onx_gpx_and_kml first. onX styling is
kept, not re-guessed.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

from cairn.core.parser import ParsedFeature
from cairn.core.writers import write_kml_shapes_maybe_split
from cairn.io.document_adapter import to_parsed_data
from cairn.io.input_check import detect
from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.model import MapDocument
from tests.test_onx_round_trip_fidelity import (
    ALLOWED_LOSSES,
    FIDELITY_FIGURE,
    SOURCE,
    _diff,
    _norm_name,
    _read_source,
    _snap,
    fidelity_figure,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402

FX = Path(__file__).parent / "fixtures"
ONX_GPX = FX / "onx_dialect" / "onx_dialect.gpx"
ONX_KML = FX / "onx_dialect" / "onx_dialect.kml"
BITTERROOTS = FX / "bitterroots" / "Bitterroots__Complete_.json"
BASELINE = FX / "bitterroots" / "export_zip_sha256_e927aa9.json"


def _file(path: Path, name: str | None = None) -> dict:
    return {"name": name or path.name, "text": path.read_text(encoding="utf-8")}


def _load(*files) -> dict:
    return json.loads(bridge.load_files(json.dumps(list(files))))


def _counts(data: dict) -> list:
    return [
        (g["name"], tuple(sum(1 for i in g["items"] if i["kind"] == k)
                          for k in ("waypoints", "tracks", "shapes")))
        for g in data["groups"]
    ]


def _items(data: dict) -> list:
    return [i for g in data["groups"] for i in g["items"]]


def _zip(data_bytes: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data_bytes))


# --- the GeoJSON path is unchanged --------------------------------------------------


def test_sources_report_each_files_detected_kind_and_dialect_in_input_order():
    """Phase 3: the UI reads this to label the map and show the CalTopo GPX notice."""
    caltopo = FX / "bitterroots" / "bitterroots_subet.gpx"
    data = _load(_file(ONX_KML), _file(caltopo), _file(ONX_GPX))
    assert data["sources"] == [
        {"name": ONX_KML.name, "kind": "kml", "dialect": "onx"},
        {"name": caltopo.name, "kind": "gpx", "dialect": "caltopo"},
        {"name": ONX_GPX.name, "kind": "gpx", "dialect": "onx"},
    ]


def test_bitterroots_geojson_export_is_byte_identical_to_before_phase_2():
    """Every file in the zip, and the UI's JSON, match what commit e927aa9 produced,
    except one intended change: CalTopo's dashed pattern ("M0 -1 L0 1,,8,F", 6
    lines) now exports as onx:style dash instead of solid (roadmap Phase 7); and
    4 titles with a trailing space ("Stimson ", ...) are now stripped on load, so
    GeoJSON names match KML/GPX (caltopo-random fixture); the export already
    stripped them. Both are put back before hashing, so nothing else may move.
    Re-pinned for ENG-05: the 6 *_Areas.kml members are now *_Areas.gpx (onX Area
    routes) and RUNBOOK.md lists those names and no KML warning; see the
    baseline's notes. Lines also carry their onX style and weight for the line-style
    editor (2026-10-23); those two keys are taken off before hashing, and the export
    is unchanged by them."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    raw = bridge.load_document(BITTERROOTS.read_text(encoding="utf-8"), BITTERROOTS.name)
    loaded = json.loads(raw)
    # The new top-level keys; everything else is the old JSON, in the old order.
    assert loaded.pop("filenames") == [BITTERROOTS.name]
    assert loaded.pop("sources") == [
        {"name": BITTERROOTS.name, "kind": "geojson", "dialect": "caltopo"}
    ]
    padded = {"Stimson", "Parking", "Ingress", "Sample run"}
    stripped = [i for g in loaded["groups"] for i in g["items"] if i["name"] in padded]
    assert len(stripped) == 4
    for i in stripped:
        i["name"] += " "
    tracks = [i for g in loaded["groups"] for i in g["items"] if i["kind"] == "tracks"]
    assert tracks and all(i["style"] in ("solid", "dash", "dot") and i["weight"] in ("4.0", "6.0") for i in tracks)
    assert sum(i.pop("style") == "dash" for i in tracks) == 6   # the 6 dashed lines, as exported
    for i in tracks:
        i.pop("weight")
    # Areas carry their onX style, weight and fill (2026-10-23, area fidelity).
    areas = [i for g in loaded["groups"] for i in g["items"] if i["kind"] == "shapes"]
    assert len(areas) == 17
    assert {(i.pop("style"), i.pop("weight")) for i in areas} == {("solid", "4.0")}
    assert sum(i.pop("fill") == "rgba(0,0,0,0)" for i in areas) == 1  # CalTopo fill-opacity 0
    assert hashlib.sha256(json.dumps(loaded).encode()).hexdigest() == baseline["load_document_json"]
    zf = _zip(bridge.export_zip())
    assert zf.namelist() == list(baseline["members"])
    assert not [n for n in zf.namelist() if n.endswith(".kml")]
    dash, solid = b"<onx:style>dash</onx:style>", b"<onx:style>solid</onx:style>"
    assert sum(zf.read(n).count(dash) for n in zf.namelist()) == 6
    for name, digest in baseline["members"].items():
        data = zf.read(name).replace(dash, solid)  # exported names were already stripped
        assert hashlib.sha256(data).hexdigest() == digest, name


def test_single_file_load_document_is_load_files_with_one_file():
    text = ONX_GPX.read_text(encoding="utf-8")
    one = json.loads(bridge.load_document(text, ONX_GPX.name))
    many = _load({"name": ONX_GPX.name, "text": text})
    assert one == many
    assert one["filename"] == ONX_GPX.name and one["filenames"] == [ONX_GPX.name]


# --- dispatch: every dialect loads, one folder per file -----------------------------


def _cairn_kml(tmp_path: Path) -> Path:
    feat = ParsedFeature({
        "id": "a1",
        "geometry": {"type": "Polygon", "coordinates": [[[-114.0, 46.0], [-114.0, 46.1],
                                                          [-113.9, 46.1], [-114.0, 46.0]]]},
        "properties": {"class": "Shape", "title": "Burn scar", "stroke": "#FFFF00",
                       "description": "2024 fire"},
    })
    (path, _size, count), = write_kml_shapes_maybe_split([feat], tmp_path / "Burn_Areas.kml", "Burns")
    assert count == 1
    return path


@pytest.mark.parametrize(
    "paths,dialects,expected",
    [
        # onX GPX alone: the <rte type=Area> is an area; the Line stays linework.
        ([ONX_GPX], [("gpx", "onx")], [("onx dialect", (3, 2, 1))]),
        # onX KML alone: the hole is kept and each MultiGeometry part is an area.
        ([ONX_KML], [("kml", "onx")], [("onx dialect", (1, 1, 3))]),
        # The pair merges into ONE folder: 3 waypoints, 2 tracks (one a Line),
        # 3 areas (Hunt unit + the two-part area's two parts).
        ([ONX_GPX, ONX_KML], [("gpx", "onx"), ("kml", "onx")], [("onx dialect", (3, 2, 3))]),
        # CalTopo GPX: coordinates and names only.
        ([FX / "bitterroots" / "bitterroots_subet.gpx"], [("gpx", "caltopo")],
         [("bitterroots subet", (10, 0, 0))]),
        # CalTopo KML: its folders (largest first), like the GeoJSON (Phase 7).
        ([FX / "caltopo_synthetic" / "caltopo_synthetic.kml"], [("kml", "caltopo")],
         [("Camps & Water #1", (8, 0, 0)), ("Routes", (0, 5, 0)), ("Areas", (0, 0, 3)),
          ("Routes / Spur lines", (0, 1, 0))]),
        # Cairn's own GPX output.
        ([FX / "rattlesnake_test_waypoints.gpx"], [("gpx", "cairn")],
         [("rattlesnake test waypoints", (34, 0, 0))]),
        # onX-namespaced GPX + a KML without onX ids, same stem: still one export.
        ([FX / "onx_export_with_tracks.gpx", FX / "onx_export_with_tracks.kml"],
         [("gpx", "onx-like"), ("kml", "generic")], [("onx export with tracks", (2, 2, 1))]),
    ],
    ids=["onx-gpx", "onx-kml", "onx-pair", "caltopo-gpx", "caltopo-kml", "cairn-gpx",
         "onx-like-pair"],
)
def test_each_dialect_loads_with_expected_counts_by_kind_and_folder(paths, dialects, expected):
    files = [_file(p) for p in paths]
    assert [detect(f["name"], f["text"]) for f in files] == dialects
    assert _counts(_load(*files)) == expected


def test_caltopo_kml_takes_the_caltopo_path_not_the_onx_one():
    """CalTopo KML is resolved like CalTopo GeoJSON: icons from the symbol
    resolver (no onX-reader fields on the items), colours from CalTopo's."""
    data = _load(_file(FX / "caltopo_synthetic" / "caltopo_synthetic.kml"))
    assert data["sources"] == [{"name": "caltopo_synthetic.kml", "kind": "kml", "dialect": "caltopo"}]
    items = {i["name"]: i for i in _items(data)}
    assert not any("onx_id" in i or "subkind" in i for i in items.values())
    assert items["Trailhead lot"]["icon"] == "Parking"  # CalTopo symbol circle-p
    assert items["Trailhead lot"]["why"] == "Your CalTopo symbol “circle-p” maps to this icon."
    assert items["Magenta ski line"]["color"] == "rgba(255,0,255,1)"  # Fuchsia


def test_caltopo_kml_with_only_empty_folders_is_refused_by_name():
    text = ('<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            '<name>CalTopo Export</name><Folder><name>x</name></Folder></Document></kml>')
    with pytest.raises(ValueError, match=r"^Cairn found no waypoints, lines or areas in empty\.kml"):
        _load({"name": "empty.kml", "text": text})


def test_cairn_kml_loads_and_keeps_its_colour(tmp_path):
    path = _cairn_kml(tmp_path)
    f = _file(path)
    assert detect(f["name"], f["text"]) == ("kml", "cairn")
    data = _load(f)
    assert _counts(data) == [("Burn Areas", (0, 0, 1))]
    (area,) = _items(data)
    assert (area["name"], area["notes"], area["color"]) == ("Burn scar", "2024 fire", "rgba(255,255,0,1)")
    assert area["confirmed"] is True and area["why"] == bridge.KEPT_FROM_FILE


def test_reader_folders_are_ignored_for_one_folder_named_from_the_file():
    data = _load(_file(ONX_GPX, "My Hunt Unit 2026.gpx"))
    assert [g["name"] for g in data["groups"]] == ["My Hunt Unit 2026"]
    for name in ("OnX Import", "Waypoints", "Tracks", "Areas"):
        assert name not in {g["name"] for g in data["groups"]}


def test_to_parsed_data_keeps_document_order_per_kind_and_carries_subkinds():
    doc = _read_source()
    parsed = to_parsed_data(doc, "ZZ Cairn Test")
    (fdata,) = parsed.folders.values()
    assert fdata["name"] == "ZZ Cairn Test"
    assert [f.title for f in fdata["waypoints"]] == ["Main Wall", "Camp & water", "Slide obs"]
    assert [(f.title, f.properties["cairn_onx_kind"]) for f in fdata["tracks"]] == [
        ("Recorded hike", "track"), ("Ridge line", "line")]
    assert [f.properties["cairn_onx_kind"] for f in fdata["shapes"]] == ["area"] * 3


# --- onX styling is kept, not re-guessed --------------------------------------------


def test_every_onx_icon_and_colour_is_shown_unchanged_and_confirmed():
    data = _load(_file(ONX_GPX), _file(ONX_KML))
    for item in _items(data):
        want = SOURCE[_norm_name(item["name"])][0]
        assert item["color"] == want["color"], item["name"]
        if item["kind"] == "waypoints":
            assert item["icon"] == want["icon"], item["name"]
        if item["name"] == "Camp & water":
            continue  # its icon is not in onX's list: see the next test
        assert item["confirmed"] is True, item["name"]
        assert item["needs_attention"] is False, item["name"]
        assert item["why"] == "Kept from your onX file.", item["name"]
    assert data["totals"]["attention"] == 0


def test_icon_not_in_onx_list_is_kept_but_flagged():
    # The synthetic fixture's "Campsite" is not in get_all_onx_icons() (onX's
    # camp icons are "Camp", "Camp Area", "Camp Backcountry", "Campground").
    data = _load(_file(ONX_GPX))
    item = next(i for i in _items(data) if i["name"] == "Camp & water")
    assert item["icon"] == "Campsite"
    assert item["unknown_icon"] is True
    assert item["confirmed"] is False
    assert "“Campsite”" in item["why"] and "isn’t in Cairn’s list" in item["why"]
    others = [i for i in _items(data) if i["kind"] == "waypoints" and i is not item]
    assert all(i["unknown_icon"] is False for i in others)
    # Kept means exported unchanged, too.
    zf = _zip(bridge.export_zip())
    wpts = next(n for n in zf.namelist() if n.endswith("_Waypoints.gpx"))
    assert "<onx:icon>Campsite</onx:icon>" in zf.read(wpts).decode()


def test_picking_a_listed_icon_clears_the_unknown_icon_flag():
    data = _load(_file(ONX_GPX))
    item = next(i for i in _items(data) if i["name"] == "Camp & water")
    bridge.apply_edits(json.dumps({item["uid"]: {"icon": "Camp"}}))
    edited = next(i for g in bridge._STATE["groups"] for i in g["items"] if i["uid"] == item["uid"])
    assert edited["unknown_icon"] is False and edited["confirmed"] is True


def _gpx(body: str, creator: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/"'
            f' version="1.1" creator="{creator}">{body}</gpx>')


def test_onx_waypoint_without_a_colour_gets_the_default_not_the_icon_convention():
    # resolve_waypoint_color would turn a colourless Shelter Brown: a guess the
    # onX file never made.
    text = _gpx('<wpt lat="46.1" lon="-114.2"><name>Hut</name><extensions>'
                '<onx:icon>Shelter</onx:icon></extensions></wpt>', "onXmaps backcountry web")
    (item,) = _items(_load({"name": "hut.gpx", "text": text}))
    assert (item["icon"], item["color"], item["confirmed"]) == ("Shelter", "rgba(8,122,255,1)", True)


def test_gpx_without_onx_icons_still_goes_through_the_resolver():
    text = _gpx('<wpt lat="46.1" lon="-114.2"><name>Blodgett Trailhead</name></wpt>', "Garmin")
    (item,) = _items(_load({"name": "garmin.gpx", "text": text}))
    assert item["icon"] == "Trailhead"
    assert item["confirmed"] is False
    assert item["why"] != bridge.KEPT_FROM_ONX and item["why"] != bridge.KEPT_FROM_FILE


def test_caltopo_geojson_items_gain_no_onx_fields():
    data = _load(_file(BITTERROOTS))
    for item in _items(data):
        assert not {"onx_id", "subkind", "unknown_icon"} & set(item)


# --- the onX id is kept in memory, and still not written ----------------------------


def test_onx_id_is_kept_on_every_item_in_memory_but_not_written():
    data = _load(_file(ONX_GPX), _file(ONX_KML))
    for item in _items(data):
        assert item["onx_id"] == SOURCE[_norm_name(item["name"])][0]["id"], item["name"]
    for g in bridge._STATE["groups"]:
        fdata = bridge._STATE["doc"].folders[g["key"]]
        for kind in ("waypoints", "tracks", "shapes"):
            for feat in fdata[kind]:
                assert feat.properties["cairn_onx_id"]
    zf = _zip(bridge.export_zip())
    blob = b"".join(zf.read(n) for n in zf.namelist())
    for name in SOURCE:
        assert SOURCE[name][0]["id"].encode() not in blob


def test_subkind_reaches_the_ui():
    data = _load(_file(ONX_GPX), _file(ONX_KML))
    got = {(i["name"], i["subkind"]) for i in _items(data)}
    assert ("Ridge line", "line") in got and ("Recorded hike", "track") in got
    assert ("Hunt unit", "area") in got and ("Main Wall", "waypoint") in got


# --- export: an onX input re-reads to the same items ---------------------------------


def _reread(zip_bytes: bytes, tmp_path: Path) -> MapDocument:
    back = MapDocument()
    zf = _zip(zip_bytes)
    for name in zf.namelist():
        if name.endswith(".md"):
            continue
        path = tmp_path / Path(name).name
        path.write_bytes(zf.read(name))
        back.items.extend((read_onx_kml(path) if name.endswith(".kml") else read_onx_gpx(path)).items)
    return back


# The web export writes areas as GPX onX Area routes (ENG-05), not KML, so on top
# of Phase 1's allowed losses (which the KML writer still meets) it loses:
WEB_ALLOWED_LOSSES = ALLOWED_LOSSES | {
    # An onX area is single-ring: "Hunt unit"'s hole is not written (its ring
    # count and point total drop; RUNBOOK.md lists it under "Holes not kept").
    ("Hunt unit", 0, "rings"),
    ("Hunt unit", 0, "pts"),
    # (Area line style, weight and fill used to be lost here too: the area GPX
    # writer wrote only <onx:color>. They now pass through, 2026-10-23.)
}
# FIDELITY_FIGURE (53, 62) less the 2 extra losses above.
WEB_FIDELITY_FIGURE = (51, 62)


def test_export_of_an_onx_pair_rereads_to_phase_1_fidelity(tmp_path):
    _load(_file(ONX_GPX), _file(ONX_KML))
    after = _snap(_reread(bridge.export_zip(), tmp_path))
    assert _diff(_snap(_read_source()), after) == WEB_ALLOWED_LOSSES
    assert fidelity_figure(after) == WEB_FIDELITY_FIGURE
    assert FIDELITY_FIGURE[0] - WEB_FIDELITY_FIGURE[0] == len(WEB_ALLOWED_LOSSES - ALLOWED_LOSSES)


# --- several files at once ------------------------------------------------------------


def test_a_gpx_kml_pair_with_different_names_still_merges():
    # onX names both exports onx-markups-<date>; a browser may rename the second.
    data = _load(_file(ONX_GPX, "onx-markups-2026-10-22.gpx"),
                 _file(ONX_KML, "onx-markups-2026-10-22 (1).kml"))
    assert _counts(data) == [("onx markups 2026 10 22", (3, 2, 3))]


def test_unpaired_files_are_one_folder_each_with_distinct_uids():
    data = _load(_file(FX / "rattlesnake_test_tracks.gpx"), _file(ONX_GPX),
                 _file(FX / "rattlesnake_test_waypoints.gpx"))
    assert sorted(_counts(data)) == sorted([
        ("rattlesnake test tracks", (0, 10, 0)),
        ("onx dialect", (3, 2, 1)),
        ("rattlesnake test waypoints", (34, 0, 0)),
    ])
    uids = [i["uid"] for i in _items(data)]
    assert len(uids) == len(set(uids))


def test_excluding_an_item_in_the_second_file_drops_exactly_that_item():
    data = _load(_file(FX / "rattlesnake_test_tracks.gpx"), _file(ONX_GPX))
    onx = next(g for g in data["groups"] if g["name"] == "onx dialect")
    ridge = next(i for i in onx["items"] if i["name"] == "Ridge line")
    bridge.apply_edits(json.dumps({ridge["uid"]: {"included": False}}))
    zf = _zip(bridge.export_zip())
    tracks = [n for n in zf.namelist() if n.endswith("onx_dialect_Tracks.gpx")]
    assert len(tracks) == 1
    text = zf.read(tracks[0]).decode()
    assert "Ridge line" not in text and "Recorded hike" in text
    others = b"".join(zf.read(n) for n in zf.namelist() if "rattlesnake" in n)
    assert others.count(b"<trk>") == 10


def test_two_files_with_the_same_name_do_not_overwrite_each_other():
    gpx = _file(ONX_GPX, "export.gpx")
    other = _file(FX / "rattlesnake_test_waypoints.gpx", "export.gpx")
    data = _load(gpx, other)
    assert sorted(c for _n, c in _counts(data)) == [(3, 2, 1), (34, 0, 0)]


def test_load_files_needs_at_least_one_file():
    with pytest.raises(ValueError, match="No file"):
        bridge.load_files("[]")


# --- errors stay one readable sentence -------------------------------------------------


def test_a_file_that_is_not_a_map_says_so():
    with pytest.raises(ValueError) as e:
        bridge.load_document("hello, this is a text file", "notes.txt")
    assert str(e.value) == (
        "This isn't a map file Cairn can read. Cairn opens CalTopo GeoJSON, "
        "and GPX or KML exported from onX or CalTopo."
    )


def test_unparseable_gpx_error_is_one_line_without_the_temp_path():
    with pytest.raises(ValueError) as e:
        bridge.load_document((FX / "edge_cases" / "malformed.gpx").read_text(), "malformed.gpx")
    msg = str(e.value)
    assert msg.startswith("malformed.gpx couldn’t be read: Invalid GPX file")
    assert "\n" not in msg and "/tmp" not in msg


def test_empty_and_invalid_json_keep_their_geojson_errors():
    with pytest.raises(ValueError, match="GeoJSON file is empty"):
        bridge.load_document("", "empty.json")
    with pytest.raises(ValueError, match="Invalid GeoJSON file"):
        bridge.load_document("{ not json", "bad.json")


def test_dtd_is_refused_before_any_reader_runs_in_a_multi_file_load():
    ok = _file(ONX_GPX)
    bad = {"name": "evil.kml", "text": (FX / "attacks" / "quadratic_blowup.kml").read_text()}
    with pytest.raises(ValueError, match="DOCTYPE"):
        bridge.load_files(json.dumps([ok, bad]))


# --- review fixes: which file, and files that hold nothing -------------------------

_EMPTY_GPX = ('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1" '
              'version="1.1" creator="onXmaps backcountry web"></gpx>')
_GPX10 = ('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/0" version="1.0" '
          'creator="x"><wpt lat="46.1" lon="-114.1"><name>a</name></wpt></gpx>')
_EMPTY_KML = ('<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
              '<Folder><name>x</name></Folder></Document></kml>')
_DTD_KML = ('<?xml version="1.0"?>\n<!DOCTYPE kml [<!ENTITY a "aaaa">]>\n'
            '<kml xmlns="http://www.opengis.net/kml/2.2"><Document/></kml>')


@pytest.mark.parametrize("name,text", [
    ("empty.gpx", _EMPTY_GPX),
    ("old.gpx", _GPX10),
    ("empty.kml", _EMPTY_KML),
])
def test_a_gpx_or_kml_with_nothing_readable_is_refused_by_name(name, text):
    """It used to open as a map of 0 items (an empty folder, an export that writes
    nothing), where an empty GeoJSON already says "No features found"."""
    with pytest.raises(ValueError, match=rf"^Cairn found no waypoints, lines or areas in {name}\."):
        bridge.load_document(text, name)


def test_an_empty_file_among_several_is_named():
    with pytest.raises(ValueError, match=r"in blank\.gpx\."):
        _load(_file(ONX_GPX), {"name": "blank.gpx", "text": _EMPTY_GPX})


@pytest.mark.parametrize("bad,expect", [
    ({"name": "evil.kml", "text": _DTD_KML}, r"^evil\.kml: This file contains a <!DOCTYPE>"),
    ({"name": "notes.txt", "text": "hello"}, r"^notes\.txt: This isn't a map file"),
])
def test_a_refused_file_among_several_is_named(bad, expect):
    """Several files dropped together: the error must say which one to take out."""
    with pytest.raises(ValueError, match=expect):
        _load(_file(ONX_GPX), bad)


def test_a_refused_single_file_keeps_its_unprefixed_message():
    with pytest.raises(ValueError, match=r"^This file contains a <!DOCTYPE>"):
        bridge.load_document(_DTD_KML, "evil.kml")
