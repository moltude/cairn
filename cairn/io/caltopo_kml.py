# Web engine: imported by web/bridge.py and run in the browser via Pyodide.
# Keep it free of terminal/UI imports (tests/test_web_engine_surface.py).
"""CalTopo KML reader (roadmap Phase 7).

Reads a CalTopo KML export into the SAME ``ParsedData``/``ParsedFeature`` shape
``parse_geojson`` builds from CalTopo's GeoJSON, so the icon resolver, the colour
rules and the bridge treat both formats identically -- including their
inconsistencies. The goal is parity, not a better KML reader.

The dialect, as verified on real exports (Dark Divide 100, tests/fixtures/
dark_divide_100/caltopo/, plus nine public CalTopo KMLs from 2016-2026; see
tests/fixtures/caltopo_synthetic/README.md for the list):

- ``<Document>`` opens with ``<name>CalTopo Export</name>`` and
  ``<description>Export from CalTopo</description>`` (input_check detects it).
- One ``<Folder>`` per CalTopo folder, never nested. Items in no folder go into
  folders CalTopo names after the geometry type ("Points", "LineStrings",
  "Polygons"; 2016 exports: "Markers", "Lines and Polygons"). Those are read as
  ordinary folders: the name alone can't tell them from a user's folder.
- Each ``<Placemark>`` carries an INLINE ``<Style>`` (no ``styleUrl``), child order
  varies, and ``<description>`` is plain text with real newlines.
- A marker's icon is ``<IconStyle><Icon><href>http://caltopo.com/icon.png?cfg=
  <symbol>[%2C<RRGGBB>]%23<n></href>``: the cfg is GeoJSON's ``marker-symbol`` and,
  when present, ``marker-color`` (see ``parse_icon_cfg``).
- A line's ``<LineStyle><color>`` is ``AABBGGRR`` built by slicing GeoJSON's
  ``stroke`` string (``#ff0000`` -> ``FF0000ff``: the case survives), ``<width>`` is
  ``stroke-width`` as a float.
- An area is ``<MultiGeometry><Point/><Polygon/></MultiGeometry>`` with
  ``<IconStyle><scale>0</scale>``: the Point is CalTopo's label anchor, not a
  marker, and is dropped. ``<PolyStyle><color>`` alpha is ``fill-opacity``.
- Coordinates are ``lon,lat,alt``; CalTopo writes ``0.0`` where GeoJSON has no
  elevation, so an altitude of exactly 0 is read as "none".
- Line patterns (dashes, arrows) are not in the KML at all: every line reads as
  ``solid``. That is a loss of the format, documented in docs/FAQ.md.

Shared styles (``styleUrl`` -> ``<Style id>`` / ``<StyleMap>``'s ``normal`` pair)
are resolved too: CalTopo doesn't write them, but a CalTopo KML re-saved by
Google Earth does.

Folders: one per ``<Folder>``, in document order, including empty ones (as
parse_geojson keeps an empty CalTopo Folder feature). A nested folder (never
CalTopo's own; a re-saved file can have them) is flattened into a folder named
by its path, ``"Parent / Child"``; the parent keeps only its direct items.
Placemarks outside every folder go to "Unorganized", or, when the file has no
folder at all, to one folder named after the file -- parse_geojson's rules.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from cairn.core.parser import (
    UNORGANIZED_FOLDER_NAME,
    ParsedData,
    ParsedFeature,
    _split_multipolygon,
)

FOLDER_PATH_SEPARATOR = " / "
# CalTopo never nests folders; a re-saved file nests a few levels. Each nested
# folder's name is its whole path, so the work grows with depth squared: an
# unbounded depth lets a 16 MB file (the input cap) take hours. Deeper is refused.
MAX_FOLDER_DEPTH = 64

_HEX6 = re.compile(r"^[0-9A-Fa-f]{6}$")
_KML_COLOR = re.compile(r"^\s*([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})\s*$")
_SCALE_SUFFIX = re.compile(r"#[0-9.]*$")


def _ln(tag: Any) -> str:
    """Local name of an element tag (namespace dropped)."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _child(el: Optional[ET.Element], name: str) -> Optional[ET.Element]:
    if el is None:
        return None
    for c in el:
        if _ln(c.tag) == name:
            return c
    return None


def _children(el: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in el if _ln(c.tag) == name]


def _text(el: Optional[ET.Element]) -> str:
    return "" if el is None or el.text is None else el.text


# --- colours and icons -------------------------------------------------------------


def kml_color(value: str) -> Tuple[Optional[str], Optional[float]]:
    """KML ``AABBGGRR`` -> (``#RRGGBB``, opacity 0-1 rounded to 2 places).

    The hex digits keep their case: CalTopo builds the KML colour by slicing its
    GeoJSON hex string, so ``#ff0000`` comes back as ``#ff0000``. (None, None) for
    anything that isn't eight hex digits.
    """
    m = _KML_COLOR.match(value or "")
    if not m:
        return None, None
    aa, bb, gg, rr = m.groups()
    return f"#{rr}{gg}{bb}", round(int(aa, 16) / 255, 2)


def _is_caltopo_icon_url(url: str) -> bool:
    try:
        u = urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return (host == "caltopo.com" or host.endswith(".caltopo.com")) and u.path.lower() == "/icon.png"


def parse_icon_cfg(href: str) -> Tuple[str, Optional[str]]:
    """A CalTopo icon href -> (marker-symbol, marker-color or None).

    ``cfg`` decodes to ``<symbol>[,<RRGGBB>]#<n>``. Verified forms:
    ``point#1.0`` (no colour), ``point,FF0000#1.0``, ``flag-1,00CD00#1.0``,
    ``circle-p,009090#1.0``, custom icons ``icon-P9JLNVA6-24-0.5-0.5-ff#1.0``
    (equal to GeoJSON's marker-symbol, no colour), ``c:target2,FF0000#1.0`` (the
    ``c:`` prefix is kept raw: no GeoJSON sample shows how CalTopo spells it
    there), ``null#1.0`` (-> no symbol), a plain icon URL as the symbol, and a
    CalTopo icon URL nested inside cfg by a re-import (read once more). The
    trailing ``#<n>`` is dropped; what it means is unverified (always 1.0 in every
    sample, even where GeoJSON's marker-size is 0.75).

    A non-CalTopo href is returned whole as the symbol, with no colour.
    """
    href = (href or "").strip()
    if not _is_caltopo_icon_url(href):
        return href, None
    cfg = (parse_qs(urlparse(href).query).get("cfg") or [""])[0]
    for _ in range(3):  # nested re-imports: icon.png?cfg=http://caltopo.com/icon.png?cfg=...
        inner = _SCALE_SUFFIX.sub("", cfg)
        if _is_caltopo_icon_url(inner):
            cfg = (parse_qs(urlparse(inner).query).get("cfg") or [""])[0]
            continue
        break
    body = _SCALE_SUFFIX.sub("", unquote(cfg) if "%" in cfg else cfg)
    symbol, color = body, None
    if "," in body:
        head, tail = body.rsplit(",", 1)
        if _HEX6.match(tail):
            symbol, color = head, f"#{tail}"
    if symbol == "null":
        symbol = ""
    return symbol, color


# --- styles ------------------------------------------------------------------------


def _shared_styles(root: ET.Element) -> Dict[str, ET.Element]:
    """id -> <Style> for every shared Style, with each StyleMap resolved to the
    Style its ``normal`` pair points at."""
    styles: Dict[str, ET.Element] = {}
    maps: Dict[str, str] = {}
    for el in root.iter():
        name = _ln(el.tag)
        sid = el.attrib.get("id")
        if not sid:
            continue
        if name == "Style":
            styles[sid] = el
        elif name == "StyleMap":
            for pair in _children(el, "Pair"):
                if _text(_child(pair, "key")).strip() == "normal":
                    maps[sid] = _text(_child(pair, "styleUrl")).strip().lstrip("#")
    for sid, target in maps.items():
        if target in styles:
            styles.setdefault(sid, styles[target])
    return styles


def _style_of(pm: ET.Element, shared: Dict[str, ET.Element]) -> Optional[ET.Element]:
    inline = _child(pm, "Style")
    if inline is not None:
        return inline
    url = _text(_child(pm, "styleUrl")).strip()
    if url.startswith("#"):
        return shared.get(url[1:])
    return None


def _style_props(style: Optional[ET.Element]) -> Dict[str, Any]:
    """GeoJSON-named properties from one <Style>."""
    props: Dict[str, Any] = {}
    if style is None:
        return props
    icon = _child(style, "IconStyle")
    if icon is not None:
        href = _text(_child(_child(icon, "Icon"), "href"))
        if href.strip():
            symbol, color = parse_icon_cfg(href)
            props["marker-symbol"] = symbol
            if color:
                props["marker-color"] = color
        if "marker-color" not in props:
            c, _a = kml_color(_text(_child(icon, "color")))
            if c:
                props["marker-color"] = c
    line = _child(style, "LineStyle")
    if line is not None:
        c, a = kml_color(_text(_child(line, "color")))
        if c:
            props["stroke"] = c
            props["stroke-opacity"] = a
        width = _text(_child(line, "width")).strip()
        if width:
            try:
                w = float(width)
                props["stroke-width"] = int(w) if w.is_integer() else w
            except ValueError:
                pass
    poly = _child(style, "PolyStyle")
    if poly is not None:
        c, a = kml_color(_text(_child(poly, "color")))
        if c:
            props["fill"] = c
            props["fill-opacity"] = a
        if _text(_child(poly, "fill")).strip() == "0":
            props["fill-opacity"] = 0
    return props


# --- geometry ----------------------------------------------------------------------


def _coords(el: Optional[ET.Element]) -> List[List[float]]:
    """``lon,lat[,alt]`` tuples -> [lon, lat] or [lon, lat, alt]. An altitude of
    exactly 0 is dropped: CalTopo writes 0.0 where GeoJSON has no elevation (in
    Dark Divide, every 0.0 is a GeoJSON point without one), and the GPX writer
    would otherwise invent sea level."""
    out: List[List[float]] = []
    for token in _text(_child(el, "coordinates")).split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            continue
        pt = [lon, lat]
        if len(parts) >= 3 and parts[2].strip():
            try:
                alt = float(parts[2])
            except ValueError:
                alt = 0.0
            if alt != 0:
                # CalTopo writes GeoJSON's integer metres as "392.0"; keep them
                # integers so the GPX written from either format is identical.
                pt.append(int(alt) if alt.is_integer() else alt)
        out.append(pt)
    return out


def _polygon(el: ET.Element) -> List[List[List[float]]]:
    """[outer ring, *inner rings]; [] without a usable outer ring."""
    def ring(boundary: Optional[ET.Element]) -> List[List[float]]:
        return _coords(_child(boundary, "LinearRing"))

    outer = ring(_child(el, "outerBoundaryIs"))
    if len(outer) < 3:
        return []
    rings = [outer]
    for b in _children(el, "innerBoundaryIs"):
        # KML 2.2 allows several LinearRings in one innerBoundaryIs.
        for lr in _children(b, "LinearRing"):
            r = _coords(lr)
            if len(r) >= 3:
                rings.append(r)
    return rings


def _geometries(el: ET.Element) -> List[Tuple[str, Any]]:
    """(type, coordinates) for every geometry in a Placemark, MultiGeometry
    flattened. Points beside a line or polygon are CalTopo's label anchors and
    are dropped."""
    found: List[Tuple[str, Any]] = []
    # Depth-first in document order with an explicit stack, not recursion: a
    # hostile file can nest MultiGeometry past Python's recursion limit, and
    # the bridge reports only ValueError as a readable error.
    stack = [iter(el)]
    while stack:
        c = next(stack[-1], None)
        if c is None:
            stack.pop()
            continue
        name = _ln(c.tag)
        if name == "Point":
            pts = _coords(c)
            if pts:
                found.append(("Point", pts[0]))
        elif name == "LineString":
            pts = _coords(c)
            if pts:
                found.append(("LineString", pts))
        elif name == "Polygon":
            rings = _polygon(c)
            if rings:
                found.append(("Polygon", rings))
        elif name == "MultiGeometry":
            stack.append(iter(c))
    if any(t != "Point" for t, _ in found):
        found = [g for g in found if g[0] != "Point"]
    return found


# --- placemarks --------------------------------------------------------------------


def _features(pm: ET.Element, idx: int, shared: Dict[str, ET.Element]) -> List[ParsedFeature]:
    """One Placemark as ParsedFeatures (several for a multi-part MultiGeometry)."""
    name = _text(_child(pm, "name")).strip()
    base_id = pm.attrib.get("id") or f"caltopo_kml_{idx}"
    style = _style_props(_style_of(pm, shared))
    geoms = _geometries(pm)
    if not geoms:
        return []

    def props(kind: str) -> Dict[str, Any]:
        p: Dict[str, Any] = {"title": name or "Untitled",
                             "description": _text(_child(pm, "description"))}
        if kind == "Point":
            p["class"] = "Marker"
            for k in ("marker-symbol", "marker-color"):
                if k in style:
                    p[k] = style[k]
        else:
            p["class"] = "Shape"
            keys = ["stroke", "stroke-opacity", "stroke-width"]
            if kind == "Polygon":
                keys += ["fill", "fill-opacity"]
            for k in keys:
                if k in style:
                    p[k] = style[k]
        return p

    polygons = [g for t, g in geoms if t == "Polygon"]
    out: List[ParsedFeature] = []
    if len(polygons) > 1:
        # The GeoJSON of the same map has ONE MultiPolygon feature; split it by
        # the very function parse_geojson uses, so ids and titles match.
        out.extend(_split_multipolygon({
            "id": base_id, "properties": props("Polygon"),
            "geometry": {"type": "MultiPolygon", "coordinates": polygons},
        }))
        geoms = [(t, g) for t, g in geoms if t != "Polygon"]
    for t, g in geoms:
        fid = base_id if not out else f"{base_id}:part{len(out) + 1}"
        out.append(ParsedFeature({"type": "Feature", "id": fid, "properties": props(t),
                                  "geometry": {"type": t, "coordinates": g}}))
    return out


def parse_caltopo_kml(filepath: Path) -> ParsedData:
    """Parse a CalTopo KML export into ParsedData (see the module docstring)."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if filepath.stat().st_size == 0:
        raise ValueError(f"KML file is empty: {filepath}")
    try:
        root = ET.parse(filepath).getroot()
    except ET.ParseError as e:
        raise ValueError(f"Invalid KML file (XML parse error): {e}\nFile: {filepath}")
    if _ln(root.tag) != "kml":
        raise ValueError(f"File does not appear to be a KML file (root element: {root.tag})\nFile: {filepath}")

    shared = _shared_styles(root)
    parsed = ParsedData()
    loose: List[ParsedFeature] = []
    counter = 0
    any_folder = False

    # Depth-first in document order with an explicit stack of (children, folder
    # path), not recursion: a hostile file can nest Folders past Python's
    # recursion limit, and the bridge reports only ValueError as a readable error.
    stack = [(iter(root), [])]
    while stack:
        it, path = stack[-1]
        c = next(it, None)
        if c is None:
            stack.pop()
            continue
        name = _ln(c.tag)
        if name == "Folder":
            any_folder = True
            if len(path) >= MAX_FOLDER_DEPTH:
                raise ValueError(
                    f"Its folders are nested more than {MAX_FOLDER_DEPTH} deep, which CalTopo "
                    f"never writes.\nFile: {filepath}")
            fpath = path + [_text(_child(c, "name")).strip() or "Untitled"]
            key = f"kml_folder_{len(parsed.folders)}"
            parsed.add_folder(key, FOLDER_PATH_SEPARATOR.join(fpath))
            for pm in _children(c, "Placemark"):
                for feat in _features(pm, counter, shared):
                    parsed.add_feature_to_folder(key, feat)
                counter += 1
            stack.append((iter(c), fpath))  # its sub-Folders; its Placemarks were read above
        elif name == "Document":
            stack.append((iter(c), path))
        elif name == "Placemark" and not path:
            loose.extend(_features(c, counter, shared))
            counter += 1

    if loose:
        if not any_folder:
            parsed.add_folder("default", filepath.stem.replace("_", " "))
            key = "default"
        else:
            parsed.add_folder("orphaned_features", UNORGANIZED_FOLDER_NAME)
            key = "orphaned_features"
        for feat in loose:
            parsed.add_feature_to_folder(key, feat)

    if not parsed.folders:
        raise ValueError(f"No placemarks found in KML file: {filepath}")
    return parsed
