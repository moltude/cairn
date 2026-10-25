"""Browser adapter over Cairn's transformation engine.

This is the ONLY new Python in the web app. Everything it calls -- parsing,
icon/color mapping, GPX/KML writing, splitting -- is the existing engine,
imported unmodified from the `cairn-maps` wheel. That is the point of the
prototype: prove the engine runs untouched in the browser.
"""

from __future__ import annotations

import io
import json
import re
import struct
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from cairn.core.config import get_all_onx_icons, load_config
from cairn.core.color_mapper import (
    AREA_FILL_KEY,
    AREA_STYLE_KEY,
    AREA_WEIGHT_KEY,
    LINE_STYLE_KEY,
    LINE_WEIGHT_KEY,
    ColorMapper,
)
from cairn.core.config import GENERIC_SYMBOLS, resolve_waypoint_color
from cairn.core.icon_resolver import IconResolver
from cairn.core.mapper import map_icon
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.core.parser import UNORGANIZED_FOLDER_NAME, ParsedData, parse_geojson
from cairn.io import input_check
from cairn.io.caltopo_gpx import parse_caltopo_gpx
from cairn.io.caltopo_kml import parse_caltopo_kml
from cairn.io.document_adapter import ONX_ICON_KEY, ONX_ID_KEY, ONX_KIND_KEY, to_parsed_data
from cairn.io.input_check import detect, guard_input
from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.utils.utils import PLAIN_NOTES_KEY, natural_sort_key
from cairn.core.writers import (
    clear_areas_without_holes,
    clear_name_changes,
    get_areas_without_holes,
    get_name_changes,
    _polygon_rings,
    area_onx_style,
    line_onx_style_weight,
    write_gpx_areas_maybe_split,
    write_gpx_tracks_maybe_split,
    write_gpx_waypoints_maybe_split,
)

# onX's per-ACCOUNT markup ceiling. Splitting a
# map into more files or imports does not get around it.
ONX_ACCOUNT_MARKUP_LIMIT = 3000  # onX help 360052239052, updated 2026-09-16 (was 1,500)
# Longest note onX keeps on import, in UTF-8 BYTES (verified 2026-10-22, r1):
# onX keeps the first 512 bytes. A 513/600/1000/3000-character ASCII note (waypoint
# and line) arrived cut to 512; a 512-character note whose last character was a
# 3-byte em dash (514 bytes) arrived as 510 characters. One earlier 3,000+ character
# note from an onX export was dropped outright, for a reason not yet known.
# Notes typed in onX itself can be much longer.
ONX_IMPORT_NOTE_LIMIT = 512

# onX's waypoint palette (10). Track/line adds Fuchsia -> 11. See ColorMapper.WAYPOINT_PALETTE.
ONX_COLORS = [
    ("Red-Orange", "rgba(255,51,0,1)", "#FF3300"),
    ("Blue", "rgba(8,122,255,1)", "#087AFF"),
    ("Cyan", "rgba(0,255,255,1)", "#00FFFF"),
    ("Lime", "rgba(132,212,0,1)", "#84D400"),
    ("Black", "rgba(0,0,0,1)", "#000000"),
    ("White", "rgba(255,255,255,1)", "#FFFFFF"),
    ("Purple", "rgba(128,0,128,1)", "#800080"),
    ("Yellow", "rgba(255,255,0,1)", "#FFFF00"),
    ("Red", "rgba(255,0,0,1)", "#FF0000"),
    ("Brown", "rgba(139,69,19,1)", "#8B4513"),
]
# Fuchsia: ColorMapper.TRACK_PALETTE's 11th color (track-only).
FUCHSIA = ("Fuchsia", "rgba(255,0,255,1)", "#FF00FF")
LINE_COLORS = ONX_COLORS + [FUCHSIA]
_RGBA_TO_HEX = {rgba: hex_ for _n, rgba, hex_ in LINE_COLORS}

# What an edit may set on a track or an area: the two styles and two weights
# Cairn offers. onX also has dot and 2.0 (thin); an onX file's dot / 2.0 line or
# area keeps it unless the user changes it (pinned at export: LINE_STYLE_KEY /
# LINE_WEIGHT_KEY for tracks, AREA_STYLE_KEY / AREA_WEIGHT_KEY for areas).
LINE_STYLES = AREA_STYLES = ("solid", "dash")
LINE_WEIGHTS = AREA_WEIGHTS = ("4.0", "6.0")

# "edited": uids with any UI edit. "color_edited": uids whose edit set a colour.
# Both are bookkeeping only now: export_zip pins EVERY item to the colour the UI
# shows, so the colour no longer depends on whether it was edited.
#
# Item identity (ENG-07): every item's "uid" is an opaque id ("i0", "i1", ...)
# handed out at load and never changed or reused while the map is open. It says
# nothing about the item's folder or position, so an item can move between
# folders without its edits, selection or exclusion losing track of it.
# "features" maps each uid to the ParsedFeature the writers read; "groups" (in
# order, and each group's "items" in order) is the ONLY record of which folder
# an item is in and where it sits. export_zip reads nothing else. doc.folders
# stays as parsed (the folders as loaded).
_STATE: dict = {"doc": None, "groups": [], "features": {}, "config": None,
                "from_onx": False,
                "edited": set(), "color_edited": set(), "next_folder": 1, "loose": set()}

# What export_zip leaves in _STATE for the export screen and export_folder_zip.
_EXPORT_KEYS = ("manifest", "unlisted_dropped", "zip")

# Path the UI writes the user's cairn_config.yaml to before loading a document.
CONFIG_PATH = Path("/cairn_config.yaml")


def _config():
    """Load mappings from the user's config if the UI wrote one, else defaults.

    load_config(None) used to look for ./cairn_config.yaml relative to the
    process CWD. In Pyodide the CWD is /home/pyodide, so the browser silently
    loaded 144 default mappings while the CLI (run from the repo) loaded 152 --
    and the two then produced DIFFERENT icons for the same map. Verified:
    `circle-p` mapped to Parking on the CLI and to nothing in the browser, so
    five waypoint files diverged. The CWD lookup is gone (None is defaults
    only); the path is still passed explicitly.
    """
    return load_config(CONFIG_PATH if CONFIG_PATH.exists() else None)


# Longest safe name, in UTF-8 bytes. A folder name feeds a directory ("NN_<safe>")
# and file names ("<safe>_Waypoints_partNN.gpx"); filesystems cap one component at
# 255 bytes, so an uncapped 300-character name made export_zip die with OSError.
_SAFE_MAX_BYTES = 80


def _safe(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", (name or "").strip()).strip()
    s = re.sub(r"[-\s]+", "_", s)
    raw = s.encode("utf-8")
    if len(raw) <= _SAFE_MAX_BYTES:
        return s or "Unnamed"          # not cut: the name as it always was ("Trip -" -> "Trip_")
    # The longest whole-character prefix that fits: "ignore" drops a character
    # the byte cut split. Only a cut name loses a trailing "_": the cut may
    # have landed just after one.
    s = raw[:_SAFE_MAX_BYTES].decode("utf-8", "ignore")
    return s.rstrip("_") or "Unnamed"


# Control characters (newlines, tabs, NUL, ...) in a folder name: a name is one
# line everywhere it is shown, and it goes into instructions.txt's "rename to:".
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]+")


def _one_line(text: str) -> str:
    """Control characters (a run of them) become one space."""
    return _CONTROL.sub(" ", text)


def _clean_name(name) -> str:
    """A folder name as stored: control characters become one space, trimmed."""
    return _one_line(name).strip() if isinstance(name, str) else ""


def _hex_for(rgba: str) -> str:
    return _RGBA_TO_HEX.get(rgba, "#087AFF")


def _explain(decision, symbol: str, default_icon: str = "Location") -> str:
    """Turn the engine's IconDecision into a sentence a hiker can act on.

    IconResolver already records WHY it chose an icon (icon_resolver.py:24-32)
    and every caller throws it away, so the UI could only ever say "needs
    attention" without saying why. The engine's own strings are terse and
    developer-facing ("symbol exact match 'circle-p' -> 'Parking'"), so they are
    rephrased here rather than shown raw.
    """
    sym = (symbol or "").strip()
    src = getattr(decision, "source", "default")
    if src == "onx-file":
        # The icon (or colour) was read from an onX file: nothing was matched
        # or guessed, so don't claim a keyword match that never happened.
        return KEPT_FROM_ONX
    if src == "file":
        return KEPT_FROM_FILE
    if src == "symbol":
        if getattr(decision, "icon", "") == default_icon:
            # A mapping (e.g. `flag-1: Location`) explicitly sends this symbol
            # to the default pin. The UI flags it "Default pin", so saying it
            # "maps to this icon" contradicted the flag.
            return (f"Your mappings send CalTopo\u2019s \u201c{sym}\u201d symbol to "
                    f"onX\u2019s default pin, so it carries no specific icon. "
                    f"Pick one if it should be something.")
        return f"Your CalTopo symbol \u201c{sym}\u201d maps to this icon."
    if src == "keyword":
        terms = ", ".join(getattr(decision, "matched_terms", ()) or ())
        where = "note" if getattr(decision, "field", "") == "description" else "name"
        return (f"Matched \u201c{terms}\u201d in the {where}."
                if terms else f"Matched a keyword in the {where}.")
    # default / fell through
    if sym and sym.lower() not in {g.lower() for g in GENERIC_SYMBOLS}:
        return (f"Your CalTopo symbol \u201c{sym}\u201d has no onX equivalent, and "
                f"nothing in the name matched. Using the default pin \u2014 pick an "
                f"icon to keep the meaning.")
    if sym:
        return (f"CalTopo\u2019s generic \u201c{sym}\u201d pin carries no meaning to "
                f"copy, and nothing in the name matched. Using the default pin.")
    return ("No CalTopo icon was set and nothing in the name matched. "
            "Using the default pin \u2014 pick an icon if this should be something.")


# What an item's icon/colour came from when the file already carried onX styling.
# The sentence is the UI's whole explanation (item["why"]), so it is exact text.
KEPT_FROM_ONX = "Kept from your onX file."
KEPT_FROM_FILE = "Kept from the file you loaded."

# load_files' routes, chosen from input_check.detect()'s (kind, dialect).
_ROUTE_GEOJSON = "geojson"          # parse_geojson, unchanged
_ROUTE_CALTOPO_GPX = "caltopo-gpx"  # parse_caltopo_gpx (already ParsedData)
_ROUTE_CALTOPO_KML = "caltopo-kml"  # parse_caltopo_kml (already ParsedData)
_ROUTE_ONX_GPX = "onx-gpx"          # read_onx_gpx -> to_parsed_data
_ROUTE_ONX_KML = "onx-kml"          # read_onx_kml -> to_parsed_data

_EXT = {input_check.GEOJSON: ".json", input_check.GPX: ".gpx", input_check.KML: ".kml"}


# What Cairn opens, said the same way by every "can't read this" message.
_READS = "Cairn reads CalTopo GeoJSON, and GPX or KML exported from onX or CalTopo."


def _route(kind: str, dialect: str) -> str:
    """Which reader a detected file goes to.

    - GeoJSON of any dialect, and an empty or unparseable file, go to
      parse_geojson exactly as before this dispatch existed (same errors).
    - CalTopo GPX and CalTopo KML keep the CalTopo path, as GeoJSON does:
      their readers build the same ParsedData parse_geojson does, and icons and
      colours come from the same symbol/keyword resolver and colour rules.
    - Every other GPX (onX, onX-like, Cairn's own, generic) goes to the onX
      GPX reader, which reads onX's extensions when present and plain GPX
      otherwise. Every other KML goes to the onX KML reader, which falls back
      to <description> for notes.
    """
    if kind == input_check.GPX:
        return _ROUTE_CALTOPO_GPX if dialect == input_check.CALTOPO else _ROUTE_ONX_GPX
    if kind == input_check.KML:
        return _ROUTE_CALTOPO_KML if dialect == input_check.CALTOPO else _ROUTE_ONX_KML
    if kind == input_check.UNKNOWN and dialect == input_check.NOT_A_MAP:
        raise ValueError(
            "This isn't a map file Cairn can read. " + _READS
        )
    return _ROUTE_GEOJSON


def _origin(dialect: str) -> str:
    """Whose styling an onX-reader file carries: "onx", "cairn" or "file"."""
    if dialect in (input_check.ONX, input_check.ONX_LIKE):
        return "onx"
    return "cairn" if dialect == input_check.CAIRN else "file"


class _Kept:
    """An IconDecision-shaped record for styling read from the file itself."""

    def __init__(self, origin: str, icon: str = ""):
        self.source = "onx-file" if origin == "onx" else "file"
        self.icon = icon


def _kept_why(origin: str) -> str:
    return _explain(_Kept(origin), "")


def _unknown_icon_why(icon: str, origin: str) -> str:
    where = "Your onX file" if origin == "onx" else "The file you loaded"
    return (f"{where} uses the icon “{icon}”, which Cairn doesn’t know. It goes "
            f"out unchanged; pick one from the list if onX doesn’t show it.")


def _read_one(path: Path, route: str, display_name: str):
    """Run one reader, turning its multi-line errors into one sentence.

    The XML readers' errors end with a "File: /tmp/..." line, which is what
    web/app.js's humanError would show. parse_geojson's errors are passed
    through untouched (their last line is already a hint for the user).
    """
    if route == _ROUTE_GEOJSON:
        return parse_geojson(path)
    try:
        if route == _ROUTE_CALTOPO_GPX:
            return parse_caltopo_gpx(path)
        if route == _ROUTE_CALTOPO_KML:
            return parse_caltopo_kml(path)
        if route == _ROUTE_ONX_GPX:
            return read_onx_gpx(path)
        return read_onx_kml(path)
    except ValueError as e:
        first = str(e).strip().splitlines()[0] if str(e).strip() else "unreadable"
        raise ValueError(f"{display_name} couldn’t be read: {first}") from None


def _pair(entries: list) -> list:
    """Group onX-reader files into merge units: [(gpx_entry|None, kml_entry|None)].

    A GPX and a KML from the same onX export describe the same markups (the
    KML keeps the areas' holes, the GPX the tracks' times), so they are merged
    with merge_onx_gpx_and_kml and shown as ONE folder. They pair when their
    stems match (case-insensitive); failing that, a lone unpaired GPX and a
    lone unpaired KML pair anyway, because onX names both exports
    onx-markups-<date> and a browser may rename one to "... (1)". Anything
    else is a folder of its own.
    """
    gpxs = [e for e in entries if e["route"] == _ROUTE_ONX_GPX]
    kmls = [e for e in entries if e["route"] == _ROUTE_ONX_KML]
    units, used_k = [], set()
    unpaired_g = []
    for g in gpxs:
        match = next((k for k in kmls if id(k) not in used_k
                      and k["stem"].lower() == g["stem"].lower()), None)
        if match is None:
            unpaired_g.append(g)
            continue
        used_k.add(id(match))
        units.append((g, match))
    unpaired_k = [k for k in kmls if id(k) not in used_k]
    if len(unpaired_g) == 1 and len(unpaired_k) == 1:
        units.append((unpaired_g[0], unpaired_k[0]))
    else:
        units += [(g, None) for g in unpaired_g] + [(None, k) for k in unpaired_k]
    return units


def _require_items(parsed: ParsedData, unit: list) -> None:
    """Refuse a GPX/KML file that yields nothing, as parse_geojson does for JSON.

    Without this an empty or unreadable-dialect file (GPX 1.0, a GPX or KML
    with no namespace or an older KML namespace: the readers look for one
    namespace each) opened as a map of 0 items with an empty folder, and the
    export then wrote nothing.
    """
    if any(fdata.get(k) for fdata in parsed.folders.values()
           for k in ("waypoints", "tracks", "shapes")):
        return
    names = " or ".join(e["name"] or "the file" for e in unit)
    raise ValueError(
        f"Cairn found no waypoints, lines or areas in {names}. " + _READS
    )


def _folder_name(stem: str) -> str:
    # The rule parse_caltopo_gpx uses for its one folder: the (safe) stem with
    # underscores as spaces.
    return stem.replace("_", " ")


def load_files(files_json: str) -> str:
    """Parse one or more map files given together. Returns the UI's JSON.

    files_json is a JSON list of {"name": filename, "text": content}. Each
    file is guarded, detected by content and read by its own reader; onX
    GPX/KML files become one folder per file named from the file's stem, and
    a GPX + KML pair from the same onX export is merged into one folder (see
    _pair). With a single file the result is exactly what load_document
    returned before multi-file input existed.
    """
    files = json.loads(files_json)
    if not isinstance(files, list) or not files:
        raise ValueError("No file was given to open.")

    multi = len(files) > 1
    entries = []
    for n, f in enumerate(files):
        text, filename = f.get("text") or "", f.get("name") or ""
        # Before anything is written or parsed: refuse DTD-bearing or oversized
        # XML with a sentence the UI can show as-is.
        try:
            guard_input(text)
            kind, dialect = detect(filename, text)
            route = _route(kind, dialect)
        except ValueError as e:
            # Several files: say WHICH one was refused, or the user can't tell
            # which of the dropped files to take out.
            if multi:
                raise ValueError(f"{filename or 'One of the files'}: {e}") from None
            raise
        # The filename is load-bearing, not cosmetic: a CalTopo export with no
        # folder features, a CalTopo GPX and every onX file are named after
        # the file's stem. Writing to a fixed /tmp/in.json made every such map
        # produce a folder called "in" -- including in instructions.txt's
        # "rename to:" line. Several files get a directory each, so two files with
        # the same stem can't overwrite each other.
        stem = _safe(Path(filename).stem) or "Map"
        base = Path(f"/tmp/cairn_in/{n}") if multi else Path("/tmp")
        base.mkdir(parents=True, exist_ok=True)
        tmp = base / f"{stem}{_EXT.get(kind, '.json')}"
        tmp.write_text(text, encoding="utf-8")
        entries.append({"name": filename, "stem": stem, "path": tmp, "route": route,
                        "kind": kind, "dialect": dialect, "n": n})

    # (ParsedData, origin) per folder source, in input order. origin is None for
    # the CalTopo paths (styling resolved as before), else "onx"/"cairn"/"file".
    sources: list = []
    onx_units = {}
    for g, k in _pair(entries):
        first = min((e for e in (g, k) if e), key=lambda e: e["n"])
        onx_units[first["n"]] = (g, k)
    for e in entries:
        if e["route"] in (_ROUTE_GEOJSON, _ROUTE_CALTOPO_GPX, _ROUTE_CALTOPO_KML):
            # GeoJSON and GPX raise their own error for a file with no
            # features; a CalTopo KML of empty folders is refused here.
            parsed = _read_one(e["path"], e["route"], e["name"])
            if e["route"] == _ROUTE_CALTOPO_KML:
                _require_items(parsed, [e])
            sources.append((parsed, None))
            continue
        if e["n"] not in onx_units:
            continue  # the second file of a pair, read with the first
        g, k = onx_units[e["n"]]
        gdoc = _read_one(g["path"], g["route"], g["name"]) if g else None
        kdoc = _read_one(k["path"], k["route"], k["name"]) if k else None
        doc = merge_onx_gpx_and_kml(gdoc, kdoc) if (gdoc and kdoc) else (gdoc or kdoc)
        stem = (g or k)["stem"]
        origin = "onx" if any(x and _origin(x["dialect"]) == "onx" for x in (g, k)) \
            else _origin((g or k)["dialect"])
        parsed = to_parsed_data(doc, _folder_name(stem))
        _require_items(parsed, [x for x in (g, k) if x])
        sources.append((parsed, origin))

    cfg = _config()
    resolver = IconResolver(
        symbol_map=cfg.symbol_map,
        keyword_map=cfg.keyword_map,
        default_icon=cfg.default_icon,
        generic_symbols=set(GENERIC_SYMBOLS),
    )
    catalog = get_all_onx_icons()

    # One ParsedData for export_zip. With one file its folder keys are kept
    # as-is (the uid format, and Bitterroots' output, are unchanged); with
    # several, each key is prefixed with the file's position so two files'
    # "default" folders can't collide.
    doc = ParsedData()
    groups = []
    features: dict = {}
    for si, (parsed, origin) in enumerate(sources):
        for okey, fdata in parsed.folders.items():
            fkey = f"{si}:{okey}" if multi else okey
            doc.folders[fkey] = fdata
            groups.append(_group(fkey, okey, fdata, origin, resolver, cfg, catalog, features))

    _STATE.update(doc=doc, groups=groups, features=features, config=cfg,
                  # Any file of this load from onX: instructions.txt then opens
                  # with the replace steps (onX imports everything as new
                  # markups). A Cairn-made or generic file is not an onX export.
                  from_onx=any(origin == "onx" for _, origin in sources),
                  edited=set(), color_edited=set(), next_folder=1,
                  loose={g["key"] for g in groups if g["unorganized"]})
    _sort_folders()
    groups = _STATE["groups"]
    # The last export belonged to the previous map: forget it, or
    # export_folder_zip(n) would hand out that map's files for this one.
    for k in _EXPORT_KEYS:
        _STATE.pop(k, None)

    filename = files[0].get("name") or ""
    return json.dumps(
        {
            "filename": filename,
            "filenames": [f.get("name") or "" for f in files],
            # What each file was detected as, in input order, so the UI can say
            # what it is looking at (the rail label).
            "sources": [
                {"name": e["name"], "kind": e["kind"], "dialect": e["dialect"]}
                for e in entries
            ],
            "groups": groups,
            "icons": sorted(get_all_onx_icons()),
            "colors": [{"name": n, "rgba": r, "hex": h} for n, r, h in ONX_COLORS],
            # 11-color palette for lines: the 10 waypoint colors plus Fuchsia.
            "line_colors": [{"name": n, "rgba": r, "hex": h} for n, r, h in LINE_COLORS],
            "totals": {
                "folders": len(groups),
                "items": sum(len(g["items"]) for g in groups),
                "attention": sum(
                    1 for g in groups for i in g["items"] if i["needs_attention"]
                ),
            },
        }
    )


def load_document(text: str, filename: str) -> str:
    """Parse one map file (CalTopo GeoJSON, CalTopo GPX, onX/Cairn GPX or KML).

    Kept for the single-file call web/app.js makes; load_files takes several.
    """
    return load_files(json.dumps([{"name": filename, "text": text}]))


def _group(fkey, okey, fdata, origin, resolver, cfg, catalog, features) -> dict:
    """One folder's UI group. okey is the reader's own folder key.

    features is the load's uid -> ParsedFeature map; each new item's opaque uid
    is the next number in it (ENG-07), so ids are unique across every folder
    and file of one load, and the same file always gets the same ids.
    """
    # doc.folders is keyed by CalTopo's folder UUID, not its name. The
    # display name is inside the folder dict. Using the key here put raw
    # UUIDs in instructions.txt's "rename to:" line.
    fname = _clean_name(fdata.get("name") or "")
    # The items outside any folder of the file. Flagged here, by where they
    # came from, never by name: a real CalTopo folder may be called
    # "Unorganized" too (and gets no such styling).
    loose = not fname or okey == "orphaned_features"
    if loose:
        fname = UNORGANIZED_FOLDER_NAME
    items = []
    for kind in ("waypoints", "tracks", "shapes"):
        # A group's items are always waypoints, then tracks, then areas, each
        # kind in the reader's order (the folder primitives keep it so), and
        # export_zip writes each kind in that order.
        for feat in fdata.get(kind) or []:
            uid = f"i{len(features)}"
            features[uid] = feat
            items.append(_item(uid, kind, feat, origin, resolver, cfg, catalog))
    return {"key": fkey, "name": fname, "safe": _safe(fname), "unorganized": loose,
            "items": items}


def _has_coordinates(kind, feat) -> bool:
    """Whether the writers will find something to write: the same tests they use."""
    c = feat.coordinates
    if kind == "waypoints":
        return bool(c) and len(c) >= 2
    if kind == "shapes":
        return bool(_polygon_rings(c))
    return bool(c)


def _item(uid, kind, feat, origin, resolver, cfg, catalog) -> dict:
    title = feat.title or ""
    props = feat.properties
    kept_icon = (props.get(ONX_ICON_KEY) or "").strip() if origin else ""
    confirmed = False
    unknown_icon = False
    if kind == "waypoints" and kept_icon:
        # The file already says which onX icon this is: the user's own earlier
        # choice, shown and exported unchanged and never re-guessed (KG 5.3).
        # An icon outside the catalogue is still kept, but flagged.
        icon = kept_icon
        unknown_icon = icon not in catalog
        confirmed = not unknown_icon
        why = _unknown_icon_why(icon, origin) if unknown_icon else _kept_why(origin)
    elif kind == "waypoints":
        decision = resolver.resolve(title, feat.description or "", feat.symbol or "")
        icon = decision.icon
        why = _explain(decision, feat.symbol or "", cfg.default_icon)
    else:
        icon = ""
        why = "Tracks and areas don’t take an icon in onX."
        if origin and (feat.stroke or "").strip():
            # The colour (and line style) came from the file.
            confirmed = True
            why = _kept_why(origin)
    # The colour shown here is the colour exported: export_zip pins
    # every item to item["color"]. Waypoints use the engine's one
    # rule (config.resolve_waypoint_color): the CalTopo colour
    # quantized to onX's 10, else the icon's conventional colour
    # (Shelter -> Brown), else the default. It is fixed at load --
    # a later icon change does NOT recolour the pin, because the
    # UI would not show that change.
    if kind == "waypoints" and kept_icon:
        # onX's own rgba is already a palette value (it maps to itself). With
        # none, the default -- not the icon's conventional colour, which would
        # be a guess the file never made.
        source = (feat.color or "").strip()
        color = ColorMapper.map_waypoint_color(source) if source else cfg.default_color
    elif kind == "waypoints":
        color = resolve_waypoint_color(
            feat.color or feat.stroke or "", icon, default=cfg.default_color
        )
    elif kind == "shapes":
        # Same function the area writers use (11-colour track palette).
        color = area_onx_style(feat)[0]
    else:
        # Lines use the 11-color track palette (keeps Fuchsia).
        color = ColorMapper.map_track_color(feat.stroke or feat.color or "")
    item = {
        "uid": uid,
        "kind": kind,
        "name": title,
        "notes": feat.description or "",
        "desc": feat.description or "",
        "symbol": feat.symbol or "",
        "icon": icon,
        "why": why,
        # Set once the user explicitly picks an icon -- including
        # picking "Location" on purpose. A deliberate choice of the
        # default pin is an ANSWER, not an outstanding question. An icon kept
        # from an onX file is the user's earlier answer.
        "confirmed": confirmed,
        # Unticking this drops the item from the onX export.
        "included": True,
        "color": color,
        "hex": _hex_for(color),
        # An item whose icon fell back to the generic pin AND whose
        # source symbol carried no intent is one only a human can fix.
        "needs_attention": kind == "waypoints" and icon == "Location" and not confirmed,
    }
    if kind == "tracks":
        # The onX line style and weight this line exports with (the track
        # writer's own rule). An onX file's dot / 2.0 comes through as is.
        item["style"], item["weight"] = line_onx_style_weight(feat)
    elif kind == "shapes":
        # The onX line style, weight and fill this area exports with (the area
        # writers' own rule). An onX file's dot / 2.0 / none comes through as is.
        # fill can be set only to onX's default blue (apply_edits): onX's importer
        # gives every area that fill (ONX_ROUND_TRIP.md #area-fidelity).
        _c, item["style"], item["weight"], item["fill"] = area_onx_style(feat)
    if not _has_coordinates(kind, feat):
        # The writers skip it (the export counts it as dropped); the UI says so.
        item["no_coords"] = True
    if origin:
        # Items read by the onX readers only: the GeoJSON path's JSON is unchanged.
        # onx_id is held for roadmap Phase 6 (nothing writes it yet); subkind is
        # line / track / area / waypoint.
        item["onx_id"] = props.get(ONX_ID_KEY) or ""
        item["subkind"] = props.get(ONX_KIND_KEY) or ""
        if kind == "waypoints":
            item["unknown_icon"] = unknown_icon
    return item


def apply_edits(edits_json: str) -> str:
    """Apply {uid: {icon,color,name,desc,included,confirmed,style,weight,fill}} from the UI.

    style and weight apply to tracks and areas ("solid" | "dash", "4.0" |
    "6.0") and are ignored for waypoints; any other value raises ValueError.
    fill applies to areas only and takes one value, onX's default
    (ColorMapper.DEFAULT_AREA_FILL): onX gives every imported area that fill,
    so it is the only fill worth choosing (owner feedback 2026-10-24, UI-30).
    Any other fill raises ValueError; it is ignored for waypoints and lines.
    """
    edits = json.loads(edits_json)
    # Validate before touching anything, so a bad edit applies nothing.
    for uid, e in edits.items():
        e = e or {}
        styles, weights = LINE_STYLES, LINE_WEIGHTS
        if e.get("style") is not None and e["style"] not in styles:
            raise ValueError(f"Unknown line style {e['style']!r} for {uid}: "
                             f"use one of {', '.join(styles)}.")
        if e.get("weight") is not None and str(e["weight"]) not in weights:
            raise ValueError(f"Unknown line weight {e['weight']!r} for {uid}: "
                             f"use one of {', '.join(weights)}.")
        if e.get("fill") is not None and e["fill"] != ColorMapper.DEFAULT_AREA_FILL:
            raise ValueError(f"Unsupported area fill {e['fill']!r} for {uid}: "
                             f"onX keeps only its default, {ColorMapper.DEFAULT_AREA_FILL}.")
    _STATE.setdefault("edited", set()).update(edits.keys())
    _STATE.setdefault("color_edited", set()).update(
        uid for uid, e in edits.items() if e and e.get("color") is not None
    )
    n = 0
    for g in _STATE["groups"]:
        for item in g["items"]:
            e = edits.get(item["uid"])
            if not e:
                continue
            for k in ("icon", "color", "name", "desc", "included", "confirmed"):
                if k in e and e[k] is not None:
                    item[k] = e[k]
            if item["kind"] in ("tracks", "shapes"):
                # Line style / weight: tracks and areas (onX has no such thing
                # for a waypoint). A track stores them on the item only when
                # edited, so an unedited map's load JSON and export are
                # byte-for-byte what they were; an area always carries them.
                if e.get("style") is not None:
                    item["style"] = e["style"]
                if e.get("weight") is not None:
                    item["weight"] = str(e["weight"])
            if item["kind"] == "shapes" and e.get("fill") is not None:
                item["fill"] = e["fill"]   # onX's default blue (validated above)
            if "icon" in e and "unknown_icon" in item:
                item["unknown_icon"] = item["icon"] not in get_all_onx_icons()
            if "icon" in e:
                item["why"] = (
                    "You chose the default pin for this one."
                    if e["icon"] == "Location"
                    else "You set this icon."
                )
                item["confirmed"] = True
            item["hex"] = _hex_for(item["color"])
            # A deliberately-chosen Location is resolved; only an UNreviewed
            # fallback still counts as needing a look.
            item["needs_attention"] = (
                item["kind"] == "waypoints"
                and item["icon"] == "Location"
                and not item.get("confirmed")
            )
            n += 1
    return json.dumps({"applied": n})


# --- folders: rename, move, merge (ENG-07) ------------------------------------
#
# Engine primitives for the folders UI. Each takes and returns plain values /
# JSON strings as apply_edits does. They change ONLY folder names, folder
# membership and order: an item's dict (with every edit, its exclusion and its
# pinned style) and its feature travel with it unchanged.
#
# Rules: an item is in exactly one folder; a folder a move or merge leaves
# with no items is removed (one made empty by create_folder, or loaded empty,
# stays until then, or until remove_empty_folder); folder names are trimmed
# and must be non-empty; two folders may not share a name compared trimmed
# and case-insensitively (a clash is REPORTED, never merged silently); moving
# an item to the folder it is in does nothing; an unknown uid or key raises
# ValueError and changes nothing.
#
# Folder order (owner feedback 2026-10-24, ENG-07): folders are sorted by name,
# natural (numbers by value, so "2 - …" before "10 - …") and case-insensitive,
# with the loose items ("Unorganized", by its flag, not its name) last. Loading
# sorts them; a new folder and a renamed one take their sorted place. Twins
# (the same name) keep their load order. The screen and the export's NN_
# numbers both follow this one order.

_KIND_ORDER = {"waypoints": 0, "tracks": 1, "shapes": 2}
DEFAULT_FOLDER_NAME = "New folder"


def _folder_order_key(g: dict) -> tuple:
    """Sort key for a folder: the loose items last, then the name, natural and
    case-insensitive. re.split with a group alternates text and digit runs, so
    every position compares like with like (str with str, int with int)."""
    parts = re.split(r"(\d+)", g["name"].strip().casefold())
    return (bool(g["unorganized"]), [int(p) if k % 2 else p for k, p in enumerate(parts)])


def _sort_folders() -> None:
    """Put _STATE["groups"] in folder order (stable: twins keep their order)."""
    _STATE["groups"].sort(key=_folder_order_key)


def _folder(key: str) -> dict:
    for g in _STATE["groups"]:
        if g["key"] == key:
            return g
    raise ValueError(f"There is no folder {key!r} in this map.")


def _folder_name_of(name) -> str:
    """A folder name as stored: one line, trimmed, and never empty."""
    name = _clean_name(name)
    if not name:
        raise ValueError("A folder needs a name.")
    return name


def _name_taken(name: str, except_key: str | None = None) -> dict | None:
    """The OTHER folder already called `name` (trimmed, any case), if any."""
    want = name.strip().casefold()
    return next((g for g in _STATE["groups"]
                 if g["key"] != except_key and g["name"].strip().casefold() == want), None)


def _duplicate(name: str, dup: dict) -> str:
    """The report for a name another folder has: nothing was changed."""
    return json.dumps({"ok": False, "name": name,
                       "duplicate": {"key": dup["key"], "name": dup["name"],
                                     "count": len(dup["items"])}})


def _done(key: str, created: bool = False, moved: int = 0, removed=()) -> str:
    """move_items' success JSON, which create_folder and merge_folders share."""
    return json.dumps({"ok": True, "key": key, "created": created, "moved": moved,
                       "removed": list(removed), "folders": _layout()})


def _layout() -> list:
    """Every folder in order, with its items' uids in order: what the UI needs
    to rearrange its own copies of the items after a move."""
    return [{"key": g["key"], "name": g["name"], "safe": g["safe"],
             "unorganized": g["unorganized"],
             "uids": [i["uid"] for i in g["items"]]} for g in _STATE["groups"]]


def layout_json() -> str:
    """{"folders": layout}: the UI re-syncs from this when applying a move's
    answer failed, so what it shows is always what export will write."""
    return json.dumps({"folders": _layout()})


def _new_folder(name: str) -> dict:
    """A new, empty folder in its sorted place, under a key no folder has had."""
    taken = {g["key"] for g in _STATE["groups"]} | set(_STATE["doc"].folders)
    while True:
        key = f"new:{_STATE['next_folder']}"
        _STATE["next_folder"] += 1
        if key not in taken:
            break
    g = {"key": key, "name": name, "safe": _safe(name), "unorganized": False, "items": []}
    _STATE["groups"].append(g)
    _sort_folders()
    return g


def _move(items: list, target: dict) -> list:
    """Move item dicts (already validated, none in target) to the end of their
    kind's run in target; remove emptied folders. Returns the removed keys."""
    moving = {id(i) for i in items}
    sources = []
    for g in _STATE["groups"]:
        if g is not target and any(id(i) in moving for i in g["items"]):
            g["items"] = [i for i in g["items"] if id(i) not in moving]
            sources.append(g)
    # Stable sort: target's own items keep their order, and each moved item
    # lands after the target's items of its kind, in the order given.
    target["items"] = sorted(target["items"] + items, key=lambda i: _KIND_ORDER[i["kind"]])
    # Only folders THIS move emptied go: a folder that loaded empty (a CalTopo
    # folder with no members) is left alone, and `removed` names exactly what went.
    emptied = [g for g in sources if not g["items"]]
    removed = [g["key"] for g in emptied]
    _STATE["groups"] = [g for g in _STATE["groups"] if not any(g is e for e in emptied)]
    return removed


def rename_folder(key: str, name: str) -> str:
    """Rename one folder. Returns JSON:

    {"ok": true, "key", "name", "safe", "unorganized", "folders": layout} on
    success (renaming a folder to its own name in another case or spacing is
    allowed); or, when another folder already
    has that name, {"ok": false, "name", "duplicate": {"key", "name", "count"}}
    and nothing is changed -- the UI offers merge_folders(key, duplicate.key).
    An unknown key or an empty name raises ValueError.
    """
    g = _folder(key)
    name = _folder_name_of(name)
    dup = _name_taken(name, except_key=key)
    if dup:
        return _duplicate(name, dup)
    g["name"], g["safe"] = name, _safe(name)
    # The loose items stay styled as such only under their own name: renamed,
    # they are an ordinary folder (renamed back, the loose items again). "Own
    # name" by the folder-name rule: "unorganized" is the same name.
    g["unorganized"] = (key in _STATE["loose"]
                        and name.casefold() == UNORGANIZED_FOLDER_NAME.casefold())
    _sort_folders()   # a renamed folder takes its sorted place
    return json.dumps({"ok": True, "key": key, "name": name, "safe": g["safe"],
                       "unorganized": g["unorganized"], "folders": _layout()})


def move_items(uids_json: str, target_key: str | None = None, new_name: str | None = None) -> str:
    """Move items to an existing folder (target_key) or to a new one (new_name,
    created in its sorted place). Give exactly one of the two. Returns JSON:

    {"ok": true, "key": <the target folder's key>, "created": bool, "moved": n,
     "removed": [keys of folders this emptied], "folders": layout}
    or, when new_name is already a folder's name, the same "duplicate" report
    rename_folder gives, with nothing changed.

    uids_json is a JSON list of uids. Items move in the map's current order
    (not the list's), each to the end of its kind in the target; ones already in
    the target stay where they are. Unknown uids, an unknown key, an empty list
    or an empty name raise ValueError and change nothing.
    """
    uids = json.loads(uids_json)
    if not isinstance(uids, list) or not uids or not all(isinstance(u, str) for u in uids):
        raise ValueError("No items were given to move.")
    if (target_key is None or target_key == "") == (new_name is None):
        raise ValueError("Move items to one folder: give a folder or a new folder name.")
    unknown = sorted(set(uids) - set(_STATE["features"]))
    if unknown:
        raise ValueError(f"Unknown item(s): {', '.join(unknown)}.")
    want = set(uids)
    if new_name is not None:
        name = _folder_name_of(new_name)
        dup = _name_taken(name)
        if dup:
            return _duplicate(name, dup)
        target = _new_folder(name)
    else:
        target = _folder(target_key)
    items = [i for g in _STATE["groups"] if g is not target
             for i in g["items"] if i["uid"] in want]
    removed = _move(items, target) if items else []
    return _done(target["key"], new_name is not None, len(items), removed)


def default_folder_name() -> str:
    """The first free one of "New folder", "New folder 2", ... (free by the
    same trimmed, case-insensitive rule every folder name follows)."""
    n = 1
    while _name_taken(name := DEFAULT_FOLDER_NAME if n == 1 else f"{DEFAULT_FOLDER_NAME} {n}"):
        n += 1
    return name


def move_to_new_folder(uids_json: str) -> str:
    """move_items into a new folder with default_folder_name(): + New folder."""
    return move_items(uids_json, None, default_folder_name())


def create_folder(name: str | None = None) -> str:
    """An EMPTY new folder, in its sorted place: a click on + New folder with nothing
    ticked. `name` defaults to default_folder_name(). Returns
    move_items' success JSON with "created": true and "moved": 0, or the
    duplicate report when the name is taken (nothing changed). An empty name
    raises ValueError.

    The folder stays, with no items, until items are moved in; like any
    folder, one that a later move empties is removed then. Export skips a
    folder with no items (no files, no number)."""
    name = default_folder_name() if name is None else _folder_name_of(name)
    dup = _name_taken(name)
    if dup:
        return _duplicate(name, dup)
    return _done(_new_folder(name)["key"], created=True)


def remove_empty_folder(key: str) -> str:
    """Remove a folder that has no items (one made empty with create_folder,
    or one that loaded empty). Returns {"ok": true, "removed": [key],
    "folders": layout}. An unknown key, or a folder that still has items,
    raises ValueError and changes nothing: items are never dropped this way."""
    g = _folder(key)
    if g["items"]:
        raise ValueError(f"“{g['name']}” isn’t empty, so it can’t be removed.")
    _STATE["groups"] = [x for x in _STATE["groups"] if x is not g]
    return json.dumps({"ok": True, "removed": [key], "folders": _layout()})


def merge_folders(source_key: str, target_key: str) -> str:
    """Move every item of source into target and remove source. target keeps
    its name and place. Returns move_items' success JSON (source_key == target_key
    moves nothing). Unknown keys raise ValueError."""
    source, target = _folder(source_key), _folder(target_key)
    if source is target:
        return _done(target_key)
    items = list(source["items"])
    removed = _move(items, target) if items else []
    # A merged folder always goes, even one that was empty (loaded empty, or
    # all of it moved out earlier): the user asked for its name to be the
    # other folder's, and two folders may not share a name.
    if any(g is source for g in _STATE["groups"]):
        _STATE["groups"] = [g for g in _STATE["groups"] if g is not source]
        removed.append(source_key)
    return _done(target_key, moved=len(items), removed=removed)


def export_zip() -> bytes:
    """Run the real engine writers; return a .zip of the onX-ready files."""
    cfg = _STATE["config"]
    groups = _STATE["groups"]
    features = _STATE["features"]

    # Push UI edits onto the ParsedFeature objects the writers read. Each item
    # reaches its feature through its uid, never by position (ENG-07).
    for g in groups:
        for item in g["items"]:
            feat = features[item["uid"]]
            feat.title = item["name"]
            feat.description = item.get("desc") or ""
            # Already cleaned at load (or typed by the user): plain text now.
            feat.properties[PLAIN_NOTES_KEY] = True
            # Every item is exported in EXACTLY the colour the UI showed
            # (item["color"]: the load-time value, or the user's pick).
            # This used to be gated on "the user edited the colour", which
            # let the writers recompute a colourless item's colour by a
            # different rule than the UI's -- a colourless Shelter showed
            # Blue and exported Brown; a strokeless area showed Blue and
            # exported White. load_document now computes the colour with
            # the engine's own rules, so pinning it is safe and WYSIWYG.
            if item["kind"] == "waypoints":
                # writers.py reads both override keys.
                feat.properties["cairn_onx_icon_override"] = item["icon"]
                feat.properties["cairn_onx_color_override"] = item["color"]
            else:
                # Track GPX and the area writers both read feature.stroke
                # first (track palette, so Fuchsia round-trips).
                feat.stroke = _hex_for(item["color"])
            if item["kind"] == "shapes":
                # Pin the area's style, weight and fill to what the UI shows
                # (edited or as loaded); area_onx_style reads these first.
                feat.properties[AREA_STYLE_KEY] = item["style"]
                feat.properties[AREA_WEIGHT_KEY] = item["weight"]
                feat.properties[AREA_FILL_KEY] = item["fill"]
            if item["kind"] == "tracks":
                # Pin the track's style and weight to what the UI shows
                # (edited or as loaded); line_onx_style_weight reads these first.
                if item.get("style"):
                    feat.properties[LINE_STYLE_KEY] = item["style"]
                if item.get("weight"):
                    feat.properties[LINE_WEIGHT_KEY] = item["weight"]

    out = Path("/tmp/out")
    buf = io.BytesIO()
    manifest = []
    unlisted_dropped = 0  # dropped items in folders that produced no file at all
    # NN_ is two digits, or as many as the largest number needs, so a map of
    # 100+ folders still sorts in order in a file list (010_ before 100_).
    # A folder with no items (made empty with + New folder, or loaded empty)
    # is not part of the export at all: no files, no box, and no number, so
    # the folders after it aren't numbered around a gap. A folder
    # whose items are all excluded still takes its number.
    numbered = [g for g in groups if g["items"]]
    width = max(2, len(str(len(numbered))))
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, g in enumerate(numbered, 1):
            safe = g["safe"]
            dirname = f"{n:0{width}d}_{safe}"
            d = out / dirname
            d.mkdir(parents=True, exist_ok=True)
            files = []
            clear_name_changes()
            clear_areas_without_holes()

            # The folder's CURRENT items of each kind, in order, minus anything
            # the user excluded. Read from the group, so an item moved here is
            # written here and an item moved away is not (ENG-07).
            def _keep(kind):
                return [features[i["uid"]] for i in g["items"]
                        if i["kind"] == kind and i.get("included", True)]

            wps = _keep("waypoints")
            trks = _keep("tracks")
            shapes = _keep("shapes")

            if wps:
                for p, size, cnt in write_gpx_waypoints_maybe_split(
                    wps, d / f"{safe}_Waypoints.gpx", g["name"], config=cfg
                ):
                    files.append((p, "waypoints", cnt))
            if trks:
                for p, size, cnt in write_gpx_tracks_maybe_split(
                    trks, d / f"{safe}_Tracks.gpx", g["name"]
                ):
                    files.append((p, "tracks", cnt))
            if shapes:
                shapes = sorted(shapes, key=lambda f: natural_sort_key(f.title or ""))
                # GPX <rte type=Area>, not KML: onX ignores area styling in KML
                # but keeps the line colour, style and weight from GPX (verified
                # 2026-10-22 / 2026-10-23, ENG-05). The fill is ignored either
                # way: every import stores onX's default rgba(74,144,226,0.1)
                # (docs/ONX_ROUND_TRIP.md#area-fidelity). The count is areas
                # actually WRITTEN, so a polygon with no usable ring shows up as
                # dropped, not written.
                for p, size, cnt in write_gpx_areas_maybe_split(
                    shapes, d / f"{safe}_Areas.gpx", g["name"]
                ):
                    files.append((p, "shapes", cnt))

            entry = {"n": n, "folder": g["name"], "safe": safe, "dir": dirname,
                     "files": [], "count": 0}
            for p, kind, cnt in files:
                if not cnt:
                    # Every item of this kind was unusable: an empty file would
                    # be an import step that imports nothing.
                    continue
                rel = f"{dirname}/{p.name}"
                data = p.read_bytes()
                zf.writestr(rel, data)
                entry["files"].append({"path": rel, "count": cnt,
                                       "kind": kind, "items": _written_items(data, kind)})
                entry["count"] += cnt
            entry["expected"] = len(wps) + len(trks) + len(shapes)
            entry["excluded"] = sum(
                1 for i in g["items"] if not i.get("included", True)
            )
            entry["dropped"] = max(0, entry["expected"] - entry["count"])
            entry["renamed"] = [
                [orig, new]
                for kind in ("waypoints", "tracks", "shapes")
                for orig, new in get_name_changes().get(kind, [])
            ]
            # onX areas are single-ring: these were written outer ring only.
            entry["holes"] = get_areas_without_holes()
            # onX keeps the first 512 UTF-8 bytes of an imported note (2026-10-22),
            # so the test is on bytes: an accented letter, dash or emoji is 2-4.
            # Measured on the <desc> as WRITTEN (what onX actually cuts), under
            # the name as written, so instructions.txt can mark the very item.
            entry["long_notes"] = [
                [name, nbytes]
                for f in entry["files"] for name, nbytes in f["items"]
                if nbytes > ONX_IMPORT_NOTE_LIMIT
            ]
            if entry["files"]:
                manifest.append(entry)
            else:
                unlisted_dropped += entry["dropped"]

        instructions = build_instructions(manifest, from_onx=_STATE.get("from_onx", False))
        zf.writestr(INSTRUCTIONS_NAME, instructions.encode("utf-8"))

    _STATE["manifest"] = manifest
    _STATE["unlisted_dropped"] = unlisted_dropped
    # The zip itself, so export_folder_zip can hand out one folder's files
    # without exporting again (and without re-reading /tmp/out, where a
    # previous export's files may linger). Not a second copy of every file.
    _STATE["zip"] = buf.getvalue()
    return _STATE["zip"]


def _manifest_entry(n) -> dict:
    """The last export's manifest entry numbered `n` (its number on screen)."""
    entry = next((e for e in _STATE.get("manifest") or [] if e["n"] == int(n)), None)
    if entry is None:
        raise ValueError(f"No exported folder {n}. Export again.")
    return entry


def _copy_members(data: bytes, paths) -> bytes:
    """A zip of `paths` from the zip `data`, each member's compressed bytes
    copied as they are: nothing is inflated or deflated again. zipfile has no
    raw copy, so the headers are written here from the members' own ZipInfo
    (CRC, sizes, method, date); a folder zip is far below the zip64 limits."""
    out, central = io.BytesIO(), []
    with zipfile.ZipFile(io.BytesIO(data)) as src:
        for path in paths:
            zi = src.getinfo(path)
            # The stored bytes follow the local header (30 bytes, name, extra).
            nlen, xlen = struct.unpack_from("<HH", data, zi.header_offset + 26)
            start = zi.header_offset + 30 + nlen + xlen
            raw = data[start:start + zi.compress_size]
            name = zi.filename.encode("utf-8")
            flags = 0 if zi.filename.isascii() else 0x800   # 0x800: the name is UTF-8
            y, mo, d, h, mi, sec = zi.date_time
            dtime, ddate = (h << 11) | (mi << 5) | (sec // 2), ((y - 1980) << 9) | (mo << 5) | d
            fields = (zi.compress_type, dtime, ddate, zi.CRC, zi.compress_size, zi.file_size, len(name))
            offset = out.tell()
            out.write(struct.pack("<IHH" "HHHIIIHH", 0x04034B50, 20, flags, *fields, 0) + name + raw)
            central.append(struct.pack("<IHHH" "HHHIIIHHHHHII", 0x02014B50, (zi.create_system << 8) | 20,
                                       20, flags, *fields, 0, 0, 0, 0, zi.external_attr, offset) + name)
    cd_at, cd = out.tell(), b"".join(central)
    out.write(cd + struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(central), len(central),
                               len(cd), cd_at, 0))
    return out.getvalue()


def export_folder_zip(n: int) -> bytes:
    """A .zip of ONE folder from the last export_zip: that folder's NN_Name/
    directory with the same files, byte for byte (copied compressed, not
    recompressed), and nothing else (no instructions.txt). `n` is the folder's number
    on screen (manifest "n"), which is not a list index: folders that wrote no
    file are skipped but keep a number. Its download name is the manifest
    entry's "dir" plus ".zip": two names can sanitize alike, their numbers can't.

    Download all's Blob in the page and _STATE["zip"] here are one copy on each
    side: keeping only the Blob would need a zip reader in JS, keeping only this
    one a multi-MB copy across on every Download all."""
    paths = [f["path"] for f in _manifest_entry(n)["files"]]
    return _copy_members(_STATE["zip"], paths)


def runbook_summary(manifest, unlisted_dropped: int = 0) -> dict:
    """The numbers the export screen's warnings report (web/app.js
    renderRunbook), from the same manifest instructions.txt is built from."""
    written = sum(e["count"] for e in manifest)
    expected = sum(e.get("expected", e["count"]) for e in manifest) + unlisted_dropped
    dropped = sum(e.get("dropped", 0) for e in manifest) + unlisted_dropped
    # Check the limit against what the user was SHOWN, not just what survived --
    # otherwise dropped items can mask a genuine over-limit map.
    markups = max(written, expected)
    return {
        "written": written,
        "expected": expected,
        "dropped": dropped,
        "markups": markups,
        "limit": ONX_ACCOUNT_MARKUP_LIMIT,
        "over_limit": markups > ONX_ACCOUNT_MARKUP_LIMIT,
        "renamed": sum(len(e.get("renamed", ())) for e in manifest),
        "holes": sum(len(e.get("holes", ())) for e in manifest),
        "long_notes": sum(len(e.get("long_notes", ())) for e in manifest),
        "note_limit": ONX_IMPORT_NOTE_LIMIT,
    }


def runbook_summary_json() -> str:
    """runbook_summary for the last export, for the export screen."""
    return json.dumps(
        runbook_summary(_STATE.get("manifest") or [], _STATE.get("unlisted_dropped", 0))
    )


# The plain-text guide at the top of Download all (UI-31). Plain text, not
# Markdown: it is opened in Notepad or TextEdit, where # and ** are noise.
INSTRUCTIONS_NAME = "instructions.txt"
# CRLF: Windows' own line ending, so every Notepad shows the lines (versions
# before Windows 10 1809 show an LF-only file as one long line); TextEdit and
# every other editor read CRLF too. The repo's attributes file marks the
# committed copies -text so they are never converted.
_EOL = "\r\n"
_KIND_LABEL = {"waypoints": "Waypoints", "tracks": "Lines", "shapes": "Areas"}
_GPX = "{http://www.topografix.com/GPX/1/1}"
_KIND_TAG = {"waypoints": "wpt", "tracks": "trk", "shapes": "rte"}


def _written_items(data: bytes, kind: str) -> list:
    """[[name, note bytes]] for each item of one file Cairn just wrote, in
    file order, as onX will see it: the name as written and the UTF-8 size of
    its <desc>. Cairn's own output (no DTD, parts under 3.75 MiB), but
    guard_input runs anyway, as before every XML parse (AGENTS.md)."""
    guard_input(data.decode("utf-8"))
    root = ET.fromstring(data)
    return [
        [el.findtext(_GPX + "name") or "", len((el.findtext(_GPX + "desc") or "").encode("utf-8"))]
        for el in root.iter(_GPX + _KIND_TAG[kind])
    ]


def _plain(text) -> str:
    """A name on one line of instructions.txt, as it is typed into onX."""
    return _one_line(str(text or "")) or "(no name)"


def build_instructions(manifest, *, from_onx: bool = False) -> str:
    """instructions.txt: how to get this INTO onX, and what is in each folder.

    onX creates one folder per import BATCH, and a batch accepts several files
    at once. The folder is named with the date and time -- never from the
    file -- so the user must rename it. That is why this file has to exist.

    The general steps once, then each folder (its zip folder and the name to
    type), each file, the kind of item in it, and each item's name. Only the
    two warnings that belong to one item are written, under it: a note onX
    will cut, an area hole onX can't keep. Totals, dropped items and the
    account limit are on the export screen.

    from_onx: the map was loaded from an onX export. onX imports everything as
    new markups, ids or not (docs/ONX_ROUND_TRIP.md), so the replace steps
    come first: back up, delete the originals, then import. Off by default,
    so a CalTopo export's file is byte-identical to before (2026-10-25).
    """
    L = [
        "How to import these files into onX",
        "",
    ]
    if from_onx:
        L += [
            "These files came from onX. onX imports them as new markups; it doesn't update the originals.",
            "Keep your onX export as a backup.",
            "In onX, delete the original markups first, then their folders. Deleting a folder doesn't delete its markups.",
            "Then import as below.",
            "",
        ]
    L += [
        "Import each folder below into onX's Web Map (webmap.onxmaps.com), one at a time.",
        "In onX, choose Import and add all of that folder's files together.",
        'Tick "Import map data to a new folder".',
        "onX names the new folder with a date and time stamp.",
        "Rename it to the name shown for that folder below.",
        "Importing needs onX Premium or Elite.",
    ]
    note_cut = "(over the length limit; onX will cut this note)"
    for e in manifest:
        long_notes = {name for name, _ in e.get("long_notes", ())}
        holes = set(e.get("holes", ()))
        L += ["", f"{e['dir']}/    rename to: {_plain(e['folder'])}"]
        for f in e["files"]:
            L.append("    " + f["path"].split("/")[-1])
            L.append("        " + _KIND_LABEL[f["kind"]])
            for name, _ in f["items"]:
                L.append("            " + _plain(name))
                if name in long_notes:
                    L.append("                " + note_cut)
                if f["kind"] == "shapes" and name in holes:
                    L.append("                (its hole is not kept: an onX area has one outline)")
    return _EOL.join(L) + _EOL
