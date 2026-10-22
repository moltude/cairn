"""cairn/io/caltopo_kml.py: CalTopo KML -> the ParsedData parse_geojson builds.

The Dark Divide tests compare the reader to parse_geojson feature by feature on
one real map exported both ways; the rest pin each dialect rule on small
hand-written KML (forms seen in real CalTopo exports unless noted).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cairn.core.parser import UNORGANIZED_FOLDER_NAME, parse_geojson
from cairn.io.caltopo_kml import MAX_FOLDER_DEPTH, kml_color, parse_caltopo_kml, parse_icon_cfg

ROOT = Path(__file__).resolve().parents[1]
DD = ROOT / "tests" / "fixtures" / "dark_divide_100" / "caltopo" / "2027_Dark_Divide_100_Mile_Endurance_Run"

HEAD = ('<?xml version="1.0"?>\n<kml xmlns="http://www.opengis.net/kml/2.2" '
        'xmlns:gx="http://www.google.com/kml/ext/2.2"><Document><name>CalTopo Export</name>'
        '<description>Export from CalTopo</description>')
TAIL = "</Document></kml>"


def _kml(tmp_path: Path, body: str, name: str = "map.kml"):
    p = tmp_path / name
    p.write_text(HEAD + body + TAIL, encoding="utf-8")
    return parse_caltopo_kml(p)


def _all(parsed, kind):
    return [f for d in parsed.folders.values() for f in d[kind]]


# --- Dark Divide: the same map as GeoJSON and as KML --------------------------------


@pytest.fixture(scope="module")
def dd():
    return parse_geojson(Path(f"{DD}.json")), parse_caltopo_kml(Path(f"{DD}.kml"))


def _by_folder(parsed):
    return {d["name"]: d for d in parsed.folders.values()}


def test_dark_divide_kml_has_the_geojsons_folders_and_items(dd):
    g, k = dd
    assert sorted(_by_folder(g)) == sorted(_by_folder(k))
    for name, gd in _by_folder(g).items():
        kd = _by_folder(k)[name]
        for kind in ("waypoints", "tracks", "shapes"):
            assert sorted(f.title for f in gd[kind]) == sorted(f.title for f in kd[kind]), (name, kind)


def _pairs(dd, kind):
    g, k = dd
    gk = {f.title: f for f in _all(g, kind)}
    return [(gk[f.title], f) for f in _all(k, kind)]


def test_dark_divide_every_marker_symbol_and_note_matches_the_geojson(dd):
    pairs = _pairs(dd, "waypoints")
    assert len(pairs) == 9
    for a, b in pairs:
        assert b.symbol == a.symbol == "icon-P9JLNVA6-24-0.5-0.5-ff"
        assert b.description == a.description
        assert b.coordinates[:2] == a.coordinates[:2]


def test_dark_divide_custom_icon_markers_carry_no_colour_in_kml(dd):
    """The one remaining difference: GeoJSON's red is a `stroke` on the Marker;
    the custom icon's cfg has no colour segment."""
    for a, b in _pairs(dd, "waypoints"):
        assert (a.color, b.color) == ("#FF0000", "")


def test_dark_divide_every_line_matches_colour_width_note_and_points(dd):
    pairs = _pairs(dd, "tracks")
    assert len(pairs) == 12
    for a, b in pairs:
        assert (b.stroke, b.stroke_width, b.description) == (a.stroke, a.stroke_width, a.description)
        # Every point, elevation included: GeoJSON's 2-D points come back 2-D
        # (CalTopo's 0.0 is dropped) and its integer metres stay integers.
        assert b.coordinates == [p[:3] for p in a.coordinates], a.title


def test_dark_divide_lower_case_stroke_survives_with_its_case(dd):
    line10 = {a.title: (a, b) for a, b in _pairs(dd, "tracks")}[
        "10 - Sunrise Peak #2 AS to Juniper Ridge #2 AS"]
    assert line10[0].stroke == line10[1].stroke == "#ff0000"


# --- colours and icon hrefs -----------------------------------------------------------


@pytest.mark.parametrize("value, expected", [
    ("FF0000FF", ("#FF0000", 1.0)),
    ("FF0000ff", ("#ff0000", 1.0)),     # Dark Divide line 10
    ("1A0000FF", ("#FF0000", 0.1)),     # CalTopo's default area fill
    ("440000FF", ("#FF0000", 0.27)),
    ("ffff0000", ("#0000ff", 1.0)),     # blue: BGR order
    ("", (None, None)),
    ("red", (None, None)),
])
def test_kml_color(value, expected):
    assert kml_color(value) == expected


ICON = "http://caltopo.com/icon.png?cfg="


@pytest.mark.parametrize("href, expected", [
    (ICON + "point%231.0", ("point", None)),
    (ICON + "point%2CFF0000%231.0", ("point", "#FF0000")),
    (ICON + "flag-1%2C00CD00%231.0", ("flag-1", "#00CD00")),
    (ICON + "circle-p%2C009090%231.0", ("circle-p", "#009090")),
    (ICON + "icon-P9JLNVA6-24-0.5-0.5-ff%231.0", ("icon-P9JLNVA6-24-0.5-0.5-ff", None)),
    (ICON + "c%3Atarget2%2CFF0000%231.0", ("c:target2", "#FF0000")),
    (ICON + "null%231.0", ("", None)),
    (ICON + "http%3A%2F%2Fmaps.google.com%2Fmapfiles%2Fkml%2Fshapes%2Ftoilets.png%231.0",
     ("http://maps.google.com/mapfiles/kml/shapes/toilets.png", None)),
    # A re-import nests the old href inside cfg (Cyberes/geovault test file).
    (ICON + "http%3A%2F%2Fcaltopo.com%2Ficon.png%3Fcfg%3Dpoint%252C0000FF%25231.0%231.0",
     ("point", "#0000FF")),
    ("https://caltopo.com/icon.png?cfg=point%2CFF0000", ("point", "#FF0000")),
    ("http://maps.google.com/mapfiles/kml/paddle/red-circle.png",
     ("http://maps.google.com/mapfiles/kml/paddle/red-circle.png", None)),
    ("http://caltopo.com.evil.example/icon.png?cfg=point%2CFF0000",
     ("http://caltopo.com.evil.example/icon.png?cfg=point%2CFF0000", None)),
])
def test_parse_icon_cfg(href, expected):
    assert parse_icon_cfg(href) == expected


# --- placemarks -------------------------------------------------------------------------


def _marker(name, href="", extra_style=""):
    icon = f"<IconStyle><Icon><href>{href}</href></Icon>{extra_style}</IconStyle>" if href or extra_style else ""
    return (f"<Placemark><Style>{icon}</Style><name>{name}</name>"
            "<Point><coordinates>-114.1,46.1,0</coordinates></Point></Placemark>")


def test_marker_symbol_and_colour_come_from_the_icon_href(tmp_path):
    p = _kml(tmp_path, "<Folder><name>F</name>" + _marker("a", ICON + "camping%2C000000%231.0") + "</Folder>")
    (w,) = _all(p, "waypoints")
    assert (w.title, w.symbol, w.color, w.properties["class"]) == ("a", "camping", "#000000", "Marker")
    assert w.coordinates == [-114.1, 46.1]  # altitude 0 read as none


def test_iconstyle_color_is_used_when_the_href_has_none(tmp_path):
    p = _kml(tmp_path, "<Folder><name>F</name>" + _marker(
        "a", ICON + "point%231.0", "<color>ff00ff00</color>") + "</Folder>")
    assert _all(p, "waypoints")[0].color == "#00ff00"


def test_description_is_verbatim_with_blank_lines_and_special_characters(tmp_path):
    note = "Line 1\n\nSee https://x.example/a?b=1&amp;c=2#d\n\n\n&lt; 2 mi #3"
    p = _kml(tmp_path, f"<Folder><name>F</name><Placemark><description>{note}</description>"
                       "<name>A &amp; B #1</name><Point><coordinates>1,2</coordinates></Point>"
                       "</Placemark></Folder>")
    (w,) = _all(p, "waypoints")
    assert w.title == "A & B #1"
    # parse_geojson's own rule (strip_html: at most one blank line) applies.
    assert w.description == "Line 1\n\nSee https://x.example/a?b=1&c=2#d\n\n< 2 mi #3"


def test_line_style_becomes_stroke_width_and_opacity(tmp_path):
    p = _kml(tmp_path, "<Folder><name>F</name><Placemark><Style><LineStyle><color>80FF00FF</color>"
                       "<width>6.0</width></LineStyle></Style><name>l</name><LineString><coordinates>"
                       "1,2,0.0 3,4,1500.0 5,6,12.5</coordinates></LineString></Placemark></Folder>")
    (t,) = _all(p, "tracks")
    assert (t.stroke, t.stroke_width, t.stroke_opacity, t.pattern) == ("#FF00FF", 6, 0.5, "solid")
    assert t.coordinates == [[1.0, 2.0], [3.0, 4.0, 1500], [5.0, 6.0, 12.5]]


AREA = ("<Placemark><Style><LineStyle><color>FF0000FF</color><width>2.0</width></LineStyle>"
        "<PolyStyle><color>1A0000FF</color><fill>1</fill><outline>1</outline></PolyStyle>"
        "<IconStyle><scale>0</scale></IconStyle></Style><name>{name}</name><MultiGeometry>"
        "<Point><coordinates>0,0,0</coordinates></Point>{polys}</MultiGeometry></Placemark>")
RING = "0,0,0 1,0,0 1,1,0 0,0,0"
HOLE = "0.2,0.2,0 0.2,0.4,0 0.4,0.4,0 0.2,0.2,0"


def _poly(outer, *inner):
    return ("<Polygon><outerBoundaryIs><LinearRing><coordinates>" + outer
            + "</coordinates></LinearRing></outerBoundaryIs>"
            + "".join("<innerBoundaryIs><LinearRing><coordinates>" + r
                      + "</coordinates></LinearRing></innerBoundaryIs>" for r in inner)
            + "</Polygon>")


def test_area_label_point_is_dropped_and_hole_kept(tmp_path):
    p = _kml(tmp_path, "<Folder><name>F</name>" + AREA.format(name="burn", polys=_poly(RING, HOLE)) + "</Folder>")
    assert _all(p, "waypoints") == []
    (s,) = _all(p, "shapes")
    assert len(s.coordinates) == 2
    assert (s.stroke, s.fill, s.fill_opacity, s.stroke_width) == ("#FF0000", "#FF0000", 0.1, 2)


def test_unwrapped_polygon_reads_too(tmp_path):
    # 2016 CalTopo exports write a bare <Polygon> (jaanga/terrain3 Wildland_drill_2016.kml).
    p = _kml(tmp_path, "<Folder><name>F</name><Placemark><name>fire</name>"
                       + _poly(RING) + "</Placemark></Folder>")
    assert [s.title for s in _all(p, "shapes")] == ["fire"]


def test_fill_0_means_fill_opacity_0(tmp_path):
    body = AREA.format(name="x", polys=_poly(RING)).replace("<fill>1</fill>", "<fill>0</fill>")
    p = _kml(tmp_path, "<Folder><name>F</name>" + body + "</Folder>")
    assert _all(p, "shapes")[0].fill_opacity == 0


def test_multi_polygon_splits_like_parse_geojson(tmp_path):
    p = _kml(tmp_path, "<Folder><name>F</name>" + AREA.format(
        name="two", polys=_poly(RING) + _poly(HOLE)) + "</Folder>")
    parts = _all(p, "shapes")
    assert [s.title for s in parts] == ["two", "two"]
    assert [s.id for s in parts] == ["caltopo_kml_0", "caltopo_kml_0:part2"]


def test_multi_linestring_becomes_one_line_per_part(tmp_path):
    p = _kml(tmp_path, "<Folder><name>F</name><Placemark><name>m</name><MultiGeometry>"
                       "<LineString><coordinates>1,1 2,2</coordinates></LineString>"
                       "<LineString><coordinates>3,3 4,4</coordinates></LineString>"
                       "</MultiGeometry></Placemark></Folder>")
    assert [(t.title, t.id) for t in _all(p, "tracks")] == [("m", "caltopo_kml_0"), ("m", "caltopo_kml_0:part2")]


def test_shared_style_and_stylemap_are_resolved(tmp_path):
    # Google Earth re-saves a CalTopo KML with shared styles (Cyberes/geovault "Test Items.kml").
    body = ('<Style id="s1"><LineStyle><color>ff00ff00</color><width>3</width></LineStyle></Style>'
            '<StyleMap id="m1"><Pair><key>normal</key><styleUrl>#s1</styleUrl></Pair>'
            '<Pair><key>highlight</key><styleUrl>#nope</styleUrl></Pair></StyleMap>'
            "<Folder><name>F</name>"
            "<Placemark><styleUrl>#m1</styleUrl><name>a</name><LineString><coordinates>1,1 2,2"
            "</coordinates></LineString></Placemark>"
            "<Placemark><styleUrl>#s1</styleUrl><name>b</name><LineString><coordinates>1,1 2,2"
            "</coordinates></LineString></Placemark></Folder>")
    p = _kml(tmp_path, body)
    assert [(t.title, t.stroke, t.stroke_width) for t in _all(p, "tracks")] == [
        ("a", "#00ff00", 3), ("b", "#00ff00", 3)]


# --- folders --------------------------------------------------------------------------------


def test_nested_folders_flatten_to_their_path(tmp_path):
    p = _kml(tmp_path, "<Folder><name>Routes</name>" + _marker("top")
             + "<Folder><name>Spurs</name>" + _marker("inner")
             + "<Folder><name>Deep</name>" + _marker("deepest") + "</Folder></Folder></Folder>")
    got = {d["name"]: [w.title for w in d["waypoints"]] for d in p.folders.values()}
    assert got == {"Routes": ["top"], "Routes / Spurs": ["inner"], "Routes / Spurs / Deep": ["deepest"]}


def _nested_folders(depth):
    return "<Folder><name>F</name>" * depth + _marker("deep") + "</Folder>" * depth


def test_folders_nested_to_the_cap_read(tmp_path):
    p = _kml(tmp_path, _nested_folders(MAX_FOLDER_DEPTH))
    assert len(p.folders) == MAX_FOLDER_DEPTH
    [(name, wps)] = [(d["name"], d["waypoints"]) for d in p.folders.values() if d["waypoints"]]
    assert name.count(" / ") == MAX_FOLDER_DEPTH - 1
    assert [w.title for w in wps] == ["deep"]


def test_hostile_folder_nesting_is_refused_with_value_error(tmp_path):
    """Nesting past the cap is a ValueError (the bridge shows only those as a
    message), not a RecursionError past Python's ~1000 limit, and not the
    depth-squared folder-path work that let a 16 MB file run for hours."""
    with pytest.raises(ValueError, match="nested more than 64 deep"):
        _kml(tmp_path, _nested_folders(2000))
    with pytest.raises(ValueError, match="nested more than 64 deep"):
        _kml(tmp_path, _nested_folders(MAX_FOLDER_DEPTH + 1))


def test_hostile_folder_nesting_reaches_the_web_app_as_a_sentence(tmp_path):
    import json
    import sys

    sys.path.insert(0, str(ROOT / "web"))
    import bridge

    text = HEAD + _nested_folders(2000) + TAIL
    with pytest.raises(ValueError, match=r"^deep\.kml couldn’t be read: Its folders are nested"):
        bridge.load_files(json.dumps([{"name": "deep.kml", "text": text}]))


def test_deeply_nested_multigeometry_reads_without_recursion_error(tmp_path):
    depth = 2000
    p = _kml(tmp_path, "<Folder><name>F</name><Placemark><name>m</name>" + "<MultiGeometry>" * depth
             + "<Point><coordinates>-121,46</coordinates></Point>" + "</MultiGeometry>" * depth
             + "</Placemark></Folder>")
    assert [w.title for w in _all(p, "waypoints")] == ["m"]


def test_empty_folder_is_kept_like_a_geojson_folder_feature(tmp_path):
    p = _kml(tmp_path, "<Folder><name>Empty</name></Folder><Folder><name>F</name>" + _marker("a") + "</Folder>")
    assert [d["name"] for d in p.folders.values()] == ["Empty", "F"]


def test_placemarks_outside_folders_go_to_unorganized(tmp_path):
    p = _kml(tmp_path, _marker("loose") + "<Folder><name>F</name>" + _marker("a") + "</Folder>")
    got = {d["name"]: [w.title for w in d["waypoints"]] for d in p.folders.values()}
    assert got == {"F": ["a"], UNORGANIZED_FOLDER_NAME: ["loose"]}


def test_no_folders_at_all_gives_one_folder_named_after_the_file(tmp_path):
    p = _kml(tmp_path, _marker("a") + _marker("b"), name="My_Trip.kml")
    assert [(d["name"], len(d["waypoints"])) for d in p.folders.values()] == [("My Trip", 2)]


def test_caltopo_type_folders_alone_fall_back_to_the_file_name(tmp_path):
    """CalTopo puts unfoldered items in folders named after their type
    ("Points", "LineStrings", "Polygons"; 2016: "Markers", "Lines and Polygons").
    Owner decision 2026-10-22: read them as "no folder", like GeoJSON. With no
    real folder in the file, that means one folder named after the file."""
    p = _kml(tmp_path, "<Folder><name>Points</name>" + _marker("a") + "</Folder>")
    assert [d["name"] for d in p.folders.values()] != ["Points"]


def test_bad_files_raise_value_error(tmp_path):
    empty = tmp_path / "e.kml"
    empty.write_text("")
    with pytest.raises(ValueError, match="empty"):
        parse_caltopo_kml(empty)
    broken = tmp_path / "b.kml"
    broken.write_text(HEAD + "<Folder>")
    with pytest.raises(ValueError, match="XML parse error"):
        parse_caltopo_kml(broken)
    nothing = tmp_path / "n.kml"
    nothing.write_text(HEAD + TAIL)
    with pytest.raises(ValueError, match="No placemarks"):
        parse_caltopo_kml(nothing)


# --- items in no folder: CalTopo's type folders read as "Unorganized" (2026-10-22) ---

_HEAD = ('<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
         '<name>CalTopo Export</name><description>Export from CalTopo</description>')


def _pm(name, lon=-121.7):
    return f"<Placemark><name>{name}</name><Point><coordinates>{lon},46.3,0</coordinates></Point></Placemark>"


def _folders(xml, tmp_path):
    from cairn.io.caltopo_kml import parse_caltopo_kml

    p = tmp_path / "Map_Name.kml"
    p.write_text(xml, encoding="utf-8")
    doc = parse_caltopo_kml(p)
    return {f["name"]: sorted(x.title for x in f["waypoints"]) for f in doc.folders.values()}


@pytest.mark.parametrize("bucket", ["Points", "LineStrings", "Polygons", "Markers", "Lines and Polygons"])
def test_caltopo_type_folder_beside_real_folders_becomes_unorganized(bucket, tmp_path):
    xml = (_HEAD + f"<Folder><name>Aid Stations</name>{_pm('A')}</Folder>"
           f"<Folder><name>{bucket}</name>{_pm('Loose')}</Folder></Document></kml>")
    assert _folders(xml, tmp_path) == {"Aid Stations": ["A"], "Unorganized": ["Loose"]}


def test_only_type_folders_use_the_file_name_like_geojson(tmp_path):
    xml = _HEAD + f"<Folder><name>Points</name>{_pm('Loose')}</Folder></Document></kml>"
    assert _folders(xml, tmp_path) == {"Map Name": ["Loose"]}
