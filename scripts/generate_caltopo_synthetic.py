"""Generate ONE synthetic CalTopo map as GeoJSON, KML and GPX, in CalTopo's dialects.

Output: tests/fixtures/caltopo_synthetic/caltopo_synthetic.{json,kml,gpx}

Dark Divide 100 (tests/fixtures/dark_divide_100/) is a real CalTopo map in all
three formats, but it has one custom icon, one colour, no areas and no special
characters. This map covers what it lacks: built-in symbols with colours, a
marker with no colour, several line colours (magenta -> onX Fuchsia), widths 1-6,
a dashed line, a polygon with a fill and a hole, a two-part area, a nested
folder, and a name and note containing #, &, <, a URL and blank lines.

Each format is written the way the real exports are, as far as they have been
seen (tests/fixtures/caltopo_synthetic/README.md lists what is verified and what
is not):

- GeoJSON: Folder features with geometry null; items link by folderId; markers
  carry marker-symbol / marker-color and [lon, lat, 0, 0]; lines stroke,
  stroke-width, stroke-opacity, pattern; areas also fill, fill-opacity.
- KML: <Document><name>CalTopo Export</name><description>Export from
  CalTopo</description>, one <Folder> per folder, inline <Style> first in each
  <Placemark>, then <description>, <name>, geometry; icon href
  http://caltopo.com/icon.png?cfg=<symbol>[%2C<RRGGBB>]%231.0; LineStyle colour
  AABBGGRR sliced from the GeoJSON hex (case kept); areas as
  <MultiGeometry><Point/><Polygon/></MultiGeometry> with IconStyle scale 0;
  "lon,lat,alt" with 0.0 for no elevation.
- GPX: creator="CALTOPO" with the gpxx namespace, <metadata><name> in CDATA,
  <wpt> with <name> and <desc> only, <trk> with <name>, <desc>, a
  <gpxx:DisplayColor> ONLY when the stroke is exactly (upper-case) one of
  Garmin's 16 colours, and one <trkseg>. Areas are left out: no CalTopo GPX with
  an area has been seen.

Deterministic: run it twice and the files are byte-identical.

    uv run python scripts/generate_caltopo_synthetic.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cairn.io.caltopo_gpx import GARMIN_DISPLAY_COLORS  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "caltopo_synthetic"
STEM = "caltopo_synthetic"
DASH = "M0 -1 L0 1,,8,F"  # the one non-solid CalTopo pattern seen in a real export

NOTE_SPECIAL = (
    "Water: filter it & boil it.\n"
    "\n"
    "Map: https://example.com/trail?a=1&b=2#camp\n"
    "\n"
    "\n"
    "< 2 mi from the TH; site #3 of 5 > the rest"
)

# (id, title)
FOLDERS = [
    ("f-camps", "Camps & Water #1"),
    ("f-routes", "Routes"),
    ("f-spurs", "Routes / Spur lines"),  # KML: <Folder>Spur lines</Folder> inside Routes
    ("f-areas", "Areas"),
]

# (folder, title, note, symbol, color or None, lon, lat)
MARKERS = [
    ("f-camps", "Camp #3 & <Lake> spring", NOTE_SPECIAL, "camping", "#000000", -114.2701, 46.1101),
    ("f-camps", "Trailhead lot", "Room for 6 cars.", "circle-p", "#0000FF", -114.2602, 46.1023),
    ("f-camps", "North summit", "", "peak", "#FF0000", -114.2905, 46.1302),
    ("f-camps", "Cornice", "Avoid after noon.\nLooker's left is safer.", "danger", "#FF0000", -114.2851, 46.1255),
    ("f-camps", "Plain red point", "", "point", "#FF0000", -114.2750, 46.1150),
    ("f-camps", "Green flag", "", "flag-1", "#00CD00", -114.2760, 46.1160),
    ("f-camps", "Old cabin", "", "hut", "#8B4513", -114.2770, 46.1170),
    ("f-camps", "Point with no colour", "", "point", None, -114.2780, 46.1180),
]

# (folder, title, note, stroke, width, pattern, coords) -- coords [lon, lat(, ele)]
LINES = [
    ("f-routes", "Red approach", "Section 1.\nSection 2.", "#FF0000", 2, "solid",
     [[-114.2602, 46.1023, 1500], [-114.2650, 46.1060, 1612], [-114.2701, 46.1101, 1704]]),
    ("f-routes", "Blue ridge", "", "#0000FF", 4, "solid",
     [[-114.2701, 46.1101], [-114.2800, 46.1200], [-114.2905, 46.1302]]),
    ("f-routes", "Magenta ski line", "", "#FF00FF", 6, "solid",
     [[-114.2905, 46.1302, 2210.5], [-114.2880, 46.1280, 2150.25], [-114.2851, 46.1255, 2088]]),
    ("f-routes", "Green dashed skin track", "Dashed in CalTopo.", "#00CD00", 1, DASH,
     [[-114.2851, 46.1255], [-114.2760, 46.1160]]),
    ("f-routes", "Note test: a <b> & #c", NOTE_SPECIAL, "#ff0000", 2, "solid",
     [[-114.2760, 46.1160], [-114.2701, 46.1101]]),
    ("f-spurs", "Spur to cabin", "", "#000000", 2, "solid",
     [[-114.2750, 46.1150], [-114.2770, 46.1170]]),
]

_SQ = [[-114.30, 46.10], [-114.28, 46.10], [-114.28, 46.12], [-114.30, 46.12], [-114.30, 46.10]]
_HOLE = [[-114.295, 46.105], [-114.295, 46.115], [-114.285, 46.115], [-114.285, 46.105], [-114.295, 46.105]]
_PART_A = [[-114.26, 46.13], [-114.25, 46.13], [-114.25, 46.14], [-114.26, 46.13]]
_PART_B = [[-114.24, 46.13], [-114.23, 46.13], [-114.23, 46.14], [-114.24, 46.13]]

# (folder, title, note, stroke, width, fill, fill_opacity, polygons) -- polygons: [rings]
AREAS = [
    ("f-areas", "Burn area with island", "Burned 2025.\n\nIsland unburned.", "#FF0000", 2,
     "#FF0000", 0.1, [[_SQ, _HOLE]]),
    ("f-areas", "Two-part closure", "Both parts closed.", "#0000FF", 3, "#0000FF", 0.25,
     [[_PART_A], [_PART_B]]),
]


# --- GeoJSON ------------------------------------------------------------------------


def geojson() -> str:
    feats = [{"type": "Feature", "id": fid, "geometry": None,
              "properties": {"title": title, "class": "Folder", "visible": True}}
             for fid, title in FOLDERS]
    for n, (folder, title, note, sym, color, lon, lat) in enumerate(MARKERS):
        props = {"title": title, "description": note, "marker-symbol": sym,
                 "marker-size": 1, "folderId": folder, "class": "Marker"}
        if color:
            props["marker-color"] = color
        feats.append({"type": "Feature", "id": f"m-{n}", "properties": props,
                      "geometry": {"type": "Point", "coordinates": [lon, lat, 0, 0]}})
    for n, (folder, title, note, stroke, width, pattern, coords) in enumerate(LINES):
        feats.append({"type": "Feature", "id": f"l-{n}", "geometry": {
            "type": "LineString", "coordinates": coords}, "properties": {
            "title": title, "description": note, "stroke": stroke, "stroke-width": width,
            "stroke-opacity": 1, "pattern": pattern, "folderId": folder, "class": "Shape"}})
    for n, (folder, title, note, stroke, width, fill, fop, polys) in enumerate(AREAS):
        geom = ({"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1
                else {"type": "MultiPolygon", "coordinates": polys})
        feats.append({"type": "Feature", "id": f"a-{n}", "geometry": geom, "properties": {
            "title": title, "description": note, "stroke": stroke, "stroke-width": width,
            "stroke-opacity": 1, "fill": fill, "fill-opacity": fop, "pattern": "solid",
            "folderId": folder, "class": "Shape"}})
    return json.dumps({"features": feats, "type": "FeatureCollection"}, indent=1) + "\n"


# --- KML ----------------------------------------------------------------------------


def _kml_color(hex_: str, opacity: float) -> str:
    """GeoJSON '#RRGGBB' -> KML 'AABBGGRR', sliced so the hex case survives."""
    h = hex_.lstrip("#")
    return f"{round(opacity * 255):02X}{h[4:6]}{h[2:4]}{h[0:2]}"


def _num(v: float) -> str:
    return repr(float(v))


def _kml_coords(coords) -> str:
    return "\n".join(f"{_num(c[0])},{_num(c[1])},{_num(c[2]) if len(c) > 2 else '0.0'}"
                     for c in coords)


def _kml_polygon(rings) -> str:
    out = ("<Polygon><altitudeMode>clampToGround</altitudeMode><tessellate>1</tessellate>"
           f"<outerBoundaryIs><LinearRing><coordinates>{_kml_coords(rings[0])}</coordinates>"
           "</LinearRing></outerBoundaryIs>")
    for r in rings[1:]:
        out += (f"<innerBoundaryIs><LinearRing><coordinates>{_kml_coords(r)}</coordinates>"
                "</LinearRing></innerBoundaryIs>")
    return out + "</Polygon>"


def _placemark(style: str, note: str, title: str, geometry: str) -> str:
    return (f"<Placemark><Style>{style}</Style><description>{escape(note)}</description>"
            f"<name>{escape(title)}</name>{geometry}</Placemark>")


def _kml_items(fid: str) -> list[str]:
    out = []
    for folder, title, note, sym, color, lon, lat in MARKERS:
        if folder != fid:
            continue
        cfg = sym + (f"%2C{color.lstrip('#')}" if color else "") + "%231.0"
        style = ('<IconStyle><hotSpot x="0.5" xunits="fraction" y="0.5" yunits="fraction"/>'
                 f"<Icon><href>http://caltopo.com/icon.png?cfg={cfg}</href></Icon></IconStyle>")
        out.append(_placemark(style, note, title,
                              f"<Point><coordinates>{_num(lon)},{_num(lat)},0</coordinates></Point>"))
    for folder, title, note, stroke, width, _pattern, coords in LINES:
        if folder != fid:
            continue
        style = (f"<LineStyle><color>{_kml_color(stroke, 1)}</color><width>{_num(width)}</width>"
                 "<gx:labelVisibility>1</gx:labelVisibility></LineStyle>")
        out.append(_placemark(style, note, title,
                              "<LineString><altitudeMode>clampToGround</altitudeMode><tessellate>1"
                              f"</tessellate><coordinates>{_kml_coords(coords)}</coordinates>"
                              "</LineString>"))
    for folder, title, note, stroke, width, fill, fop, polys in AREAS:
        if folder != fid:
            continue
        style = (f"<LineStyle><color>{_kml_color(stroke, 1)}</color><width>{_num(width)}</width>"
                 "<gx:labelVisibility>1</gx:labelVisibility></LineStyle>"
                 f"<PolyStyle><color>{_kml_color(fill, fop)}</color><fill>1</fill>"
                 f"<outline>1</outline><width>{_num(width)}</width></PolyStyle>"
                 "<IconStyle><scale>0</scale></IconStyle>")
        lon, lat = polys[0][0][0]
        geom = (f"<MultiGeometry><Point><coordinates>{_num(lon)},{_num(lat)},0</coordinates>"
                "</Point>" + "".join(_kml_polygon(r) for r in polys) + "</MultiGeometry>")
        out.append(_placemark(style, note, title, geom))
    return out


def kml() -> str:
    def folder(name: str, body: list[str]) -> str:
        return f"<Folder><open>1</open><name>{escape(name)}</name>{''.join(body)}</Folder>"

    names = dict(FOLDERS)
    spurs = folder("Spur lines", _kml_items("f-spurs"))
    parts = [
        folder(names["f-camps"], _kml_items("f-camps")),
        folder(names["f-routes"], _kml_items("f-routes") + [spurs]),
        folder(names["f-areas"], _kml_items("f-areas")),
    ]
    return ('<?xml version="1.0"?>\n<kml xmlns="http://www.opengis.net/kml/2.2" '
            'xmlns:gx="http://www.google.com/kml/ext/2.2"><Document><name>CalTopo Export</name>'
            f"<description>Export from CalTopo</description>{''.join(parts)}</Document></kml>\n")


# --- GPX ----------------------------------------------------------------------------

_GARMIN_BY_HEX = {v: k for k, v in GARMIN_DISPLAY_COLORS.items()}


def gpx() -> str:
    out = ['<?xml version="1.0"?>\n<gpx xmlns="http://www.topografix.com/GPX/1/1" '
           'xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" creator="CALTOPO" '
           f'version="1.1"><metadata><name><![CDATA[{STEM}]]></name></metadata>']
    for _f, title, note, _sym, _color, lon, lat in MARKERS:
        desc = f"<desc>{escape(note)}</desc>" if note else ""
        out.append(f'<wpt lat="{_num(lat)}" lon="{_num(lon)}"><name>{escape(title)}</name>{desc}</wpt>')
    for _f, title, note, stroke, _w, _p, coords in LINES:
        desc = f"<desc>{escape(note)}</desc>" if note else ""
        garmin = _GARMIN_BY_HEX.get(stroke)  # exact, case-sensitive: "#ff0000" gets none
        ext = (f"<extensions><gpxx:TrackExtension><gpxx:DisplayColor>{garmin}</gpxx:DisplayColor>"
               "</gpxx:TrackExtension></extensions>" if garmin else "")
        pts = "".join(f'<trkpt lat="{_num(c[1])}" lon="{_num(c[0])}">'
                      + (f"<ele>{_num(c[2])}</ele>" if len(c) > 2 else "") + "</trkpt>"
                      for c in coords)
        out.append(f"<trk><name>{escape(title)}</name>{desc}{ext}<trkseg>{pts}</trkseg></trk>")
    out.append("</gpx>\n")
    return "".join(out)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext, text in (("json", geojson()), ("kml", kml()), ("gpx", gpx())):
        (OUT / f"{STEM}.{ext}").write_text(text, encoding="utf-8")
        print(OUT / f"{STEM}.{ext}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
