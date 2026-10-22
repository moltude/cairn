"""Roadmap Phase 1 (docs/ROADMAP_ONX_ROUND_TRIP.md): reader and writer fidelity fixes.

One test group per item, plus notes text (URLs with '#', '&', line breaks) surviving
every writer and reader unchanged. The whole-file round trip lives in
tests/test_onx_round_trip_fidelity.py.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.core.normalization import normalize_entities
from cairn.core.parser import ParsedFeature, parse_geojson
from cairn.core.writers import (
    write_gpx_tracks,
    write_gpx_tracks_maybe_split,
    write_gpx_waypoints_maybe_split,
    write_kml_shapes_maybe_split,
)
from cairn.io.caltopo_gpx import parse_caltopo_gpx
from cairn.io.onx_gpx import parse_onx_desc_kv, read_onx_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.model import Shape, Track, Waypoint

GPX_NS = {"g": "http://www.topografix.com/GPX/1/1"}
KML_NS = {"k": "http://www.opengis.net/kml/2.2"}

AVY_NOTES = (
    "Avalanche D2 · N · 8200 ft · trigger AS (skier, unintentional)\n"
    "Problem: Wind Slab · Zone: Bitterroot & Rattlesnake #2\n"
    "Full report: https://missoulaavalanche.org/observations/#/avalanche/123\n"
    "Also: https://example.org/obs?zone=1&copy=2&notes=3&para=4&lt=5#frag\n"
    "Source: West Central Montana Avalanche Center. Not a forecast — check today's\n"
    "advisory at missoulaavalanche.org before you go."
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _gpx(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx xmlns:onx="https://wwww.onxmaps.com/" xmlns="http://www.topografix.com/GPX/1/1"'
        ' version="1.1" creator="onXmaps backcountry web">\n' + body + "\n</gpx>"
    )


def _kml(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>' + body + "</Document></kml>"
    )


# --- Item 1: read_onx_gpx dispatches on <type> / type= ----------------------------

AREA_RTE = """<rte><name>Unit 9</name><desc>name=Unit 9
notes=area notes
id=area-1
type=Area
color=rgba(255,255,0,1)
style=dash
weight=4.0
fill_color=rgba(255,255,0,0.3)</desc><type>Area</type><extensions><onx:color>rgba(255,255,0,1)</onx:color><onx:style>dash</onx:style><onx:weight>4.0</onx:weight><onx:fill_color>rgba(255,255,0,0.3)</onx:fill_color></extensions>
<rtept lat="46.12" lon="-114.28"/><rtept lat="46.12" lon="-114.29"/><rtept lat="46.13" lon="-114.29"/><rtept lat="46.13" lon="-114.28"/></rte>"""

LINE_RTE = """<rte><name>Ridge</name><desc>name=Ridge
notes=
id=line-1
type=Line
color=rgba(0,0,0,1)
style=solid
weight=6.0</desc><type>Line</type><extensions><onx:color>rgba(0,0,0,1)</onx:color></extensions>
<rtept lat="46.110" lon="-114.270"/><rtept lat="46.112" lon="-114.272"/></rte>"""


def test_gpx_area_rte_becomes_a_closed_shape(tmp_path):
    doc = read_onx_gpx(_write(tmp_path, "a.gpx", _gpx(AREA_RTE)))
    (shape,) = doc.items
    assert isinstance(shape, Shape)
    assert shape.rings == [[(-114.28, 46.12), (-114.29, 46.12), (-114.29, 46.13),
                            (-114.28, 46.13), (-114.28, 46.12)]]  # closed by the reader
    assert shape.notes == "area notes"
    assert (shape.style.OnX_color_rgba, shape.style.OnX_style, shape.style.OnX_weight,
            shape.style.OnX_id) == ("rgba(255,255,0,1)", "dash", "4.0", "area-1")
    assert shape.style.extra["fill_color"] == "rgba(255,255,0,0.3)"
    assert shape.folder_id == "OnX_shapes" and doc.get_folder("OnX_shapes") is not None


def test_gpx_area_from_desc_kv_alone(tmp_path):
    """No <type> element: the desc block's type=Area decides (onX writes both)."""
    body = AREA_RTE.replace("<type>Area</type>", "")
    (shape,) = read_onx_gpx(_write(tmp_path, "a.gpx", _gpx(body))).items
    assert isinstance(shape, Shape)
    # fill_color is a known desc key now, so it no longer bleeds into weight
    assert shape.style.extra["desc_kv"]["weight"] == "4.0"


def test_gpx_line_rte_is_a_track_tagged_as_a_line(tmp_path):
    (trk,) = read_onx_gpx(_write(tmp_path, "l.gpx", _gpx(LINE_RTE))).items
    assert isinstance(trk, Track)
    assert trk.extra["onx_kind"] == "line"


def test_gpx_untyped_rte_and_trk_stay_plain_tracks(tmp_path):
    body = (LINE_RTE.replace("<type>Line</type>", "").replace("type=Line\n", "")
            + '<trk><name>Hike</name><trkseg><trkpt lat="46.1" lon="-114.2"/>'
              '<trkpt lat="46.2" lon="-114.3"/></trkseg></trk>')
    items = read_onx_gpx(_write(tmp_path, "t.gpx", _gpx(body))).items
    assert [type(i) for i in items] == [Track, Track]
    assert all("onx_kind" not in i.extra for i in items)


def test_a_note_line_reading_type_area_does_not_turn_a_cairn_track_into_an_area(tmp_path):
    """Cairn's own <desc> is the bare note. A user note that happens to contain
    'type=Area' must not change the geometry kind."""
    body = ('<trk><name>Hike</name><desc>type=Area\nmore</desc><trkseg>'
            '<trkpt lat="46.1" lon="-114.2"/><trkpt lat="46.2" lon="-114.3"/>'
            '<trkpt lat="46.3" lon="-114.2"/></trkseg></trk>')
    (trk,) = read_onx_gpx(_write(tmp_path, "t.gpx", _gpx(body))).items
    assert isinstance(trk, Track)


def test_gpx_area_with_too_few_points_stays_a_track(tmp_path):
    body = AREA_RTE.split("<rtept")[0] + '<rtept lat="46.12" lon="-114.28"/><rtept lat="46.13" lon="-114.29"/></rte>'
    (item,) = read_onx_gpx(_write(tmp_path, "a.gpx", _gpx(body))).items
    assert isinstance(item, Track)


def test_merge_keeps_the_kml_hole_over_the_gpx_area_ring(tmp_path):
    gpx = read_onx_gpx(_write(tmp_path, "a.gpx", _gpx(AREA_RTE)))
    kml = read_onx_kml(_write(tmp_path, "a.kml", _kml(
        '<Placemark><name>Unit 9</name><ExtendedData><Data name="id"><value>area-1</value></Data>'
        '</ExtendedData><Polygon><outerBoundaryIs><LinearRing><coordinates>'
        '-114.28,46.12 -114.29,46.12 -114.29,46.13 -114.28,46.13 -114.28,46.12'
        '</coordinates></LinearRing></outerBoundaryIs><innerBoundaryIs><LinearRing><coordinates>'
        '-114.283,46.123 -114.287,46.123 -114.287,46.127 -114.283,46.123'
        '</coordinates></LinearRing></innerBoundaryIs></Polygon></Placemark>')))
    (shape,) = merge_onx_gpx_and_kml(gpx, kml).items
    assert len(shape.rings) == 2
    assert shape.notes == "area notes" and shape.style.OnX_style == "dash"


# --- Item 2: read_onx_kml ---------------------------------------------------------

HOLED = ('<Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 4,0 4,4 0,4 0,0</coordinates>'
         '</LinearRing></outerBoundaryIs><innerBoundaryIs><LinearRing><coordinates>'
         '1,1 2,1 2,2 1,1</coordinates></LinearRing></innerBoundaryIs><innerBoundaryIs>'
         '<LinearRing><coordinates>3,3 3.5,3 3.5,3.5 3,3</coordinates></LinearRing>'
         '</innerBoundaryIs></Polygon>')


def test_kml_reads_inner_rings(tmp_path):
    (shape,) = read_onx_kml(_write(tmp_path, "h.kml", _kml(
        f"<Placemark><name>Holes</name>{HOLED}</Placemark>"))).items
    assert [len(r) for r in shape.rings] == [5, 4, 4]


def test_kml_reads_every_multigeometry_part(tmp_path):
    body = ('<Placemark><name>Parts</name><ExtendedData><Data name="id"><value>m-1</value></Data>'
            '<Data name="notes"><value>n</value></Data></ExtendedData><MultiGeometry>'
            + HOLED +
            '<Polygon><outerBoundaryIs><LinearRing><coordinates>10,10 11,10 11,11 10,10'
            '</coordinates></LinearRing></outerBoundaryIs></Polygon>'
            '<LineString><coordinates>5,5 6,6</coordinates></LineString>'
            '<Point><coordinates>7,7</coordinates></Point>'
            '</MultiGeometry></Placemark>')
    items = read_onx_kml(_write(tmp_path, "m.kml", _kml(body))).items
    assert [type(i) for i in items] == [Shape, Shape, Track, Waypoint]
    assert [len(i.rings) for i in items[:2]] == [3, 1]
    assert all(i.name == "Parts" and i.notes == "n" and i.style.OnX_id == "m-1" for i in items)
    assert len({i.id for i in items}) == 4  # distinct item ids, one shared onX id


def test_merge_keeps_every_multigeometry_part(tmp_path):
    body = ('<Placemark><name>Parts</name><ExtendedData><Data name="id"><value>m-1</value></Data>'
            '</ExtendedData><MultiGeometry>' + HOLED + HOLED + '</MultiGeometry></Placemark>')
    kml = read_onx_kml(_write(tmp_path, "m.kml", _kml(body)))
    gpx = read_onx_gpx(_write(tmp_path, "e.gpx", _gpx("")))
    assert len(merge_onx_gpx_and_kml(gpx, kml).shapes()) == 2


def test_kml_description_is_the_notes_fallback(tmp_path):
    body = ('<Placemark><name>A</name><description><![CDATA[<p>Line one</p><p>Line two &amp; more</p>]]>'
            '</description><Point><coordinates>1,2</coordinates></Point></Placemark>'
            '<Placemark><name>B</name><description>ignored</description><ExtendedData>'
            '<Data name="notes"><value>from data</value></Data></ExtendedData>'
            '<Point><coordinates>1,2</coordinates></Point></Placemark>')
    a, b = read_onx_kml(_write(tmp_path, "d.kml", _kml(body))).items
    assert a.notes == "Line one\nLine two & more"
    assert b.notes == "from data"


def test_kml_style_and_weight_reach_the_style_fields(tmp_path):
    body = ('<Placemark><name>T</name><ExtendedData><Data name="style"><value>dot</value></Data>'
            '<Data name="weight"><value>6.0</value></Data><Data name="fill_color">'
            '<value>rgba(1,2,3,0.5)</value></Data></ExtendedData>' + HOLED + '</Placemark>')
    (shape,) = read_onx_kml(_write(tmp_path, "s.kml", _kml(body))).items
    assert (shape.style.OnX_style, shape.style.OnX_weight) == ("dot", "6.0")
    assert shape.style.extra["fill_color"] == "rgba(1,2,3,0.5)"


# --- Item 3: Cairn's KML carries onX-style ExtendedData ---------------------------

def _area(**props) -> ParsedFeature:
    base = {"class": "Shape", "title": "Hunt unit", "description": "line 1\nline 2",
            "stroke": "#FF0000", "stroke-width": 6, "pattern": "dash", "fill-opacity": 0.1}
    base.update(props)
    return ParsedFeature({"id": "s1", "properties": base, "geometry": {
        "type": "Polygon", "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 0]],
                                           [[1, 1], [2, 1], [2, 2], [1, 1]]]}})


def test_cairn_kml_writes_onx_extended_data(tmp_path):
    out = tmp_path / "a.kml"
    write_kml_shapes_maybe_split([_area()], out, "F")
    pm = ET.parse(out).getroot().find(".//k:Placemark", KML_NS)
    data = {d.get("name"): d.find("k:value", KML_NS).text
            for d in pm.findall("k:ExtendedData/k:Data", KML_NS)}
    assert data == {"notes": "line 1\nline 2", "color": "rgba(255,0,0,1)", "style": "dash",
                    "weight": "6.0", "fill_color": "rgba(255,0,0,0.1)"}
    assert pm.find("k:Style", KML_NS) is not None  # the KML Style stays alongside


def test_cairn_kml_without_notes_writes_no_notes_data(tmp_path):
    out = tmp_path / "a.kml"
    write_kml_shapes_maybe_split([_area(description="")], out, "F")
    names = [d.get("name") for d in ET.parse(out).getroot().iter(f"{{{KML_NS['k']}}}Data")]
    assert "notes" not in names


def test_rereading_cairn_kml_keeps_notes_colour_style_weight_and_holes(tmp_path):
    out = tmp_path / "a.kml"
    write_kml_shapes_maybe_split([_area()], out, "F")
    (shape,) = read_onx_kml(out).items
    assert shape.notes == "line 1\nline 2"
    assert (shape.style.OnX_color_rgba, shape.style.OnX_style, shape.style.OnX_weight) == (
        "rgba(255,0,0,1)", "dash", "6.0")
    assert shape.style.extra["fill_color"] == "rgba(255,0,0,0.1)"
    assert len(shape.rings) == 2


# --- Item 4: the track writers emit <time> ----------------------------------------

def _track(coords) -> ParsedFeature:
    return ParsedFeature({"id": "t1", "properties": {"class": "Shape", "title": "Hike"},
                          "geometry": {"type": "LineString", "coordinates": coords}})


T0 = 1782918000000  # 2026-07-01T15:00:00Z


@pytest.mark.parametrize("writer", ["split", "legacy"])
def test_track_writers_emit_time_and_skip_missing_values(tmp_path, writer):
    coords = [[-114.0, 46.0, 1500.5, T0], [-114.1, 46.1, None, T0 + 1500],
              [-114.2, 46.2, 1510.0, 0], [-114.3, 46.3]]
    out = tmp_path / "t.gpx"
    if writer == "split":
        write_gpx_tracks_maybe_split([_track(coords)], out, "F")
    else:
        write_gpx_tracks([_track(coords)], out, "F")
    pts = ET.parse(out).getroot().findall(".//g:trkpt", GPX_NS)
    got = [(p.findtext("g:ele", None, GPX_NS), p.findtext("g:time", None, GPX_NS)) for p in pts]
    assert got == [("1500.5", "2026-07-01T15:00:00.000Z"),
                   (None, "2026-07-01T15:00:01.500Z"),
                   ("1510.0", None),
                   (None, None)]
    # and the onX reader gets the same epoch ms back
    (trk,) = read_onx_gpx(out).items
    assert [p[3] for p in trk.points] == [T0, T0 + 1500, None, None]


# --- Item 6: parse_caltopo_gpx doesn't invent ele=0 -------------------------------

def test_caltopo_gpx_missing_ele_stays_missing_through_the_writer(tmp_path):
    src = _write(tmp_path, "ct.gpx", (
        '<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1" creator="CALTOPO">'
        '<trk><name>T</name><trkseg><trkpt lat="46.0" lon="-114.0"/>'
        '<trkpt lat="46.1" lon="-114.1"><ele>1234.5</ele></trkpt></trkseg></trk>'
        '<rte><name>R</name><rtept lat="46.0" lon="-114.0"/><rtept lat="46.1" lon="-114.1"/></rte>'
        '</gpx>'))
    parsed = parse_caltopo_gpx(src)
    trk, rte = parsed.folders["default"]["tracks"]
    assert trk.coordinates == [[-114.0, 46.0], [-114.1, 46.1, 1234.5]]
    assert rte.coordinates == [[-114.0, 46.0], [-114.1, 46.1]]
    out = tmp_path / "o.gpx"
    write_gpx_tracks_maybe_split([trk, rte], out, "F", sort=False)
    eles = [p.findtext("g:ele", None, GPX_NS) for p in ET.parse(out).getroot().iter(f"{{{GPX_NS['g']}}}trkpt")]
    assert eles == [None, "1234.5", None, None]


# --- Item 7: parser.py handles CalTopo MultiPolygon -------------------------------

def test_multipolygon_becomes_one_area_per_part():
    fx = Path(__file__).parent / "fixtures" / "edge_cases" / "multipolygon.json"
    parsed = parse_geojson(fx)
    shapes = [s for f in parsed.folders.values() for s in f["shapes"]]
    assert [s.title for s in shapes] == ["Two parcels", "Two parcels", "Plain area"]
    assert [s.geometry_type for s in shapes] == ["Polygon"] * 3
    assert len({s.id for s in shapes}) == 3
    assert [len(s.coordinates) for s in shapes] == [2, 1, 1]  # the first part keeps its hole
    assert shapes[0].properties["stroke"] == shapes[1].properties["stroke"] == "#FF0000"
    # each part owns its properties: a per-feature edit to one must not reach the other
    assert shapes[0].properties is not shapes[1].properties


def test_multipolygon_parts_are_written_as_areas(tmp_path):
    fx = Path(__file__).parent / "fixtures" / "edge_cases" / "multipolygon.json"
    shapes = [s for f in parse_geojson(fx).folders.values() for s in f["shapes"]]
    (_, _, count), = write_kml_shapes_maybe_split(shapes, tmp_path / "a.kml", "F")
    assert count == 3


def test_empty_or_malformed_multipolygon_adds_no_area(tmp_path):
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "a", "geometry": {"type": "MultiPolygon", "coordinates": []},
         "properties": {"class": "Shape", "title": "Empty"}},
        {"type": "Feature", "id": "b", "geometry": {"type": "MultiPolygon", "coordinates": "x"},
         "properties": {"class": "Shape", "title": "Bad"}},
        {"type": "Feature", "id": "c", "geometry": {"type": "Point", "coordinates": [1, 2]},
         "properties": {"class": "Marker", "title": "M"}}]}
    p = _write(tmp_path, "m.json", json.dumps(fc))
    parsed = parse_geojson(p)
    assert sum(len(f["shapes"]) for f in parsed.folders.values()) == 0


# --- Notes text: '#', '&', URLs and line breaks survive unchanged -----------------

def test_normalize_entities_leaves_bare_ampersands_alone():
    s = "https://x.org/?a=1&copy=2&notes=3&para=4&lt=5&amp=6"
    assert normalize_entities(s) == s
    # real (semicolon-terminated) references, single or double escaped, still decode
    assert normalize_entities("Tom&amp;apos;s &amp; Jerry&#39;s &#x41;") == "Tom's & Jerry's A"


def test_desc_that_is_not_a_kv_block_is_all_notes():
    """Cairn writes the bare note into <desc>. A later line that looks like a key
    (id=, weight=) belongs to the note, not to the onX key/value block."""
    kv, notes = parse_onx_desc_kv("Slide on the ridge\nid=12 on the map\nweight=heavy")
    assert notes == "Slide on the ridge\nid=12 on the map\nweight=heavy"
    assert set(kv) == {"notes"}


def _wpt(notes: str) -> ParsedFeature:
    return ParsedFeature({"id": "w1", "geometry": {"type": "Point", "coordinates": [-114.0, 46.0]},
                          "properties": {"class": "Marker", "title": "Obs", "description": notes,
                                         "marker-color": "#FF0000", "marker-symbol": ""}})


def test_waypoint_desc_keeps_notes_byte_for_byte(tmp_path):
    out = tmp_path / "w.gpx"
    write_gpx_waypoints_maybe_split([_wpt(AVY_NOTES)], out, "F")
    assert ET.parse(out).getroot().findtext(".//g:wpt/g:desc", None, GPX_NS) == AVY_NOTES
    (wp,) = read_onx_gpx(out).items
    assert wp.notes == AVY_NOTES


def test_track_desc_keeps_notes_byte_for_byte(tmp_path):
    feat = _track([[-114.0, 46.0], [-114.1, 46.1]])
    feat.description = AVY_NOTES
    out = tmp_path / "t.gpx"
    write_gpx_tracks_maybe_split([feat], out, "F")
    assert ET.parse(out).getroot().findtext(".//g:trk/g:desc", None, GPX_NS) == AVY_NOTES
    (trk,) = read_onx_gpx(out).items
    assert trk.notes == AVY_NOTES


def test_kml_description_and_notes_data_keep_notes_byte_for_byte(tmp_path):
    out = tmp_path / "a.kml"
    write_kml_shapes_maybe_split([_area(description=AVY_NOTES)], out, "F")
    pm = ET.parse(out).getroot().find(".//k:Placemark", KML_NS)
    assert pm.findtext("k:description", None, KML_NS) == AVY_NOTES
    data = {d.get("name"): d.findtext("k:value", None, KML_NS)
            for d in pm.findall("k:ExtendedData/k:Data", KML_NS)}
    assert data["notes"] == AVY_NOTES
    (shape,) = read_onx_kml(out).items
    assert shape.notes == AVY_NOTES


def test_onx_kml_notes_with_url_read_unchanged(tmp_path):
    esc = AVY_NOTES.replace("&", "&amp;")
    body = (f'<Placemark><name>Obs</name><ExtendedData><Data name="notes"><value>{esc}</value>'
            '</Data></ExtendedData><Point><coordinates>1,2</coordinates></Point></Placemark>')
    (wp,) = read_onx_kml(_write(tmp_path, "n.kml", _kml(body))).items
    assert wp.notes == AVY_NOTES
