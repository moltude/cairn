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
import zipfile
from pathlib import Path

from cairn.core.config import get_all_onx_icons, load_config
from cairn.core.color_mapper import ColorMapper
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
    kml_area_color,
    write_gpx_areas_maybe_split,
    write_gpx_tracks_maybe_split,
    write_gpx_waypoints_maybe_split,
)

# onX's per-ACCOUNT markup ceiling (FIDELITY_MODEL_2026-08-29.md). Splitting a
# map into more files or imports does not get around it.
ONX_ACCOUNT_MARKUP_LIMIT = 3000  # onX help 360052239052, updated 2026-09-16 (was 1,500)
# Longest note onX kept on import in testing (2026-10-22): a 617-character
# waypoint note arrived cut to 512; a 3,000+ character line note was dropped.
# Notes typed in onX itself can be much longer.
ONX_IMPORT_NOTE_LIMIT = 512

# onX's waypoint palette (10). Track/line adds Fuchsia -> 11. See README.md's color reference.
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
# Fuchsia: README.md color table row 11 / ColorMapper.TRACK_PALETTE (track-only).
FUCHSIA = ("Fuchsia", "rgba(255,0,255,1)", "#FF00FF")
LINE_COLORS = ONX_COLORS + [FUCHSIA]
_RGBA_TO_HEX = {rgba: hex_ for _n, rgba, hex_ in LINE_COLORS}

# onX line styles and weights an edit may set on a track (onx:style / onx:weight,
# the values onX's own GPX export writes). Weight -> the CalTopo stroke-width
# the track writer's stroke_width_to_weight maps back to that weight.
LINE_STYLES = ("solid", "dash", "dot")
LINE_WEIGHTS = {"4.0": 4, "6.0": 6}

# "edited": uids with any UI edit. "color_edited": uids whose edit set a colour.
# Both are bookkeeping only now: export_zip pins EVERY item to the colour the UI
# shows, so the colour no longer depends on whether it was edited.
_STATE: dict = {"doc": None, "groups": [], "config": None, "edited": set(), "color_edited": set()}

# Path the UI writes the user's cairn_config.yaml to before loading a document.
CONFIG_PATH = Path("/cairn_config.yaml")


def _config():
    """Load mappings from an EXPLICIT path, never the working directory.

    load_config(None) looks for ./cairn_config.yaml relative to the process CWD.
    In Pyodide the CWD is /home/pyodide, so the browser silently loaded 144
    default mappings while the CLI (run from the repo) loaded 152 -- and the two
    then produced DIFFERENT icons for the same map. Verified: `circle-p` mapped
    to Parking on the CLI and to nothing in the browser, so five waypoint files
    diverged. Passing the path explicitly removes the ambient dependency.
    """
    return load_config(CONFIG_PATH if CONFIG_PATH.exists() else None)


def _safe(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", (name or "").strip()).strip()
    return re.sub(r"[-\s]+", "_", s) or "Unnamed"


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
        return (f"Matched \u201c{terms}\u201d in the name."
                if terms else "Matched a keyword in the name.")
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
            "This isn't a map file Cairn can read. Cairn opens CalTopo GeoJSON, "
            "and GPX or KML exported from onX or CalTopo."
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
    return (f"{where} uses the icon “{icon}”, which isn’t in Cairn’s "
            f"list of onX icons. It will be exported unchanged; pick an icon from "
            f"the list if onX doesn’t show it.")


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
        f"Cairn found no waypoints, lines or areas in {names}. It reads GPX 1.1 "
        f"and KML 2.2 as exported by onX and CalTopo."
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
        # produce a folder called "in" -- including in the runbook's "rename
        # it to" line. Several files get a directory each, so two files with
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
    for si, (parsed, origin) in enumerate(sources):
        for okey, fdata in parsed.folders.items():
            fkey = f"{si}:{okey}" if multi else okey
            doc.folders[fkey] = fdata
            groups.append(_group(fkey, okey, fdata, origin, resolver, cfg, catalog))

    groups.sort(key=lambda g: -len(g["items"]))
    _STATE.update(doc=doc, groups=groups, config=cfg, edited=set(), color_edited=set())

    filename = files[0].get("name") or ""
    return json.dumps(
        {
            "filename": filename,
            "filenames": [f.get("name") or "" for f in files],
            # What each file was detected as, in input order, so the UI can say
            # what it is looking at (the rail label, the CalTopo GPX notice).
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


def _group(fkey, okey, fdata, origin, resolver, cfg, catalog) -> dict:
    """One folder's UI group. okey is the reader's own folder key."""
    # doc.folders is keyed by CalTopo's folder UUID, not its name. The
    # display name is inside the folder dict. Using the key here put raw
    # UUIDs in the runbook's "rename it to:" instruction.
    fname = (fdata.get("name") or "").strip()
    if not fname or okey == "orphaned_features":
        fname = UNORGANIZED_FOLDER_NAME
    items = []
    for kind in ("waypoints", "tracks", "shapes"):
        # Index PER KIND. This used to be len(items), a running total across
        # all three kinds, so a folder's tracks were numbered from 23 and its
        # shapes from 40. Anything decoding the uid back to a position -- the
        # export's include/exclude filter does -- then addressed the wrong
        # feature, or an index past the end of the list.
        for kind_index, feat in enumerate(fdata.get(kind) or []):
            items.append(_item(fkey, kind, kind_index, feat, origin, resolver, cfg, catalog))
    return {"key": fkey, "name": fname, "safe": _safe(fname), "items": items}


def _item(fkey, kind, kind_index, feat, origin, resolver, cfg, catalog) -> dict:
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
        # Same function the KML writer uses (11-colour track palette).
        color = kml_area_color(feat)
    else:
        # Lines use the 11-color track palette (keeps Fuchsia).
        color = ColorMapper.map_track_color(feat.stroke or feat.color or "")
    item = {
        "uid": f"{fkey}::{kind}::{kind_index}",
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
    """Apply {uid: {icon,color,name,desc,included,confirmed,style,weight}} from the UI.

    style ("solid" | "dash" | "dot") and weight ("4.0" | "6.0") apply to tracks
    and are ignored for waypoints and areas; any other value raises ValueError.
    """
    edits = json.loads(edits_json)
    # Validate before touching anything, so a bad edit applies nothing.
    for uid, e in edits.items():
        e = e or {}
        if e.get("style") is not None and e["style"] not in LINE_STYLES:
            raise ValueError(f"Unknown line style {e['style']!r} for {uid}: "
                             f"use one of {', '.join(LINE_STYLES)}.")
        if e.get("weight") is not None and str(e["weight"]) not in LINE_WEIGHTS:
            raise ValueError(f"Unknown line weight {e['weight']!r} for {uid}: "
                             f"use one of {', '.join(LINE_WEIGHTS)}.")
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
            if item["kind"] == "tracks":
                # Line style / weight: tracks only (onX has no such thing for a
                # waypoint, and Cairn's area export writes neither -- ENG-05).
                # Stored on the item only when edited, so an unedited map's
                # load JSON and export are byte-for-byte what they were.
                if e.get("style") is not None:
                    item["style"] = e["style"]
                if e.get("weight") is not None:
                    item["weight"] = str(e["weight"])
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


def export_zip() -> bytes:
    """Run the real engine writers; return a .zip of the onX-ready files."""
    doc, cfg = _STATE["doc"], _STATE["config"]
    groups = _STATE["groups"]

    # Push UI edits onto the ParsedFeature objects the writers read.
    for g in groups:
        by_kind: dict = {}
        for item in g["items"]:
            by_kind.setdefault(item["kind"], []).append(item)
        fdata = doc.folders[g["key"]]
        for kind, items in by_kind.items():
            feats = fdata.get(kind) or []
            for item, feat in zip(items, feats):
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
                    # Track GPX and area KML both read feature.stroke first
                    # (track palette, so Fuchsia round-trips).
                    feat.stroke = _hex_for(item["color"])
                if item["kind"] == "tracks":
                    # The track writer reads feat.pattern / feat.stroke_width
                    # (pattern_to_style / stroke_width_to_weight), whichever
                    # reader built the feature (CalTopo or onX).
                    if item.get("style"):
                        feat.pattern = item["style"]
                    if item.get("weight"):
                        feat.stroke_width = LINE_WEIGHTS[item["weight"]]

    out = Path("/tmp/out")
    buf = io.BytesIO()
    manifest = []
    unlisted_dropped = 0  # dropped items in folders that produced no file at all
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, g in enumerate(groups, 1):
            fdata = doc.folders[g["key"]]
            safe = g["safe"]
            d = out / f"{n:02d}_{safe}"
            d.mkdir(parents=True, exist_ok=True)
            files = []
            clear_name_changes()
            clear_areas_without_holes()

            # Drop anything the user excluded. Done by position because the
            # UI's uid encodes the feature's index within its kind.
            def _keep(kind, feats):
                dropped = {
                    int(i["uid"].rsplit("::", 1)[1])
                    for i in g["items"]
                    if i["kind"] == kind and not i.get("included", True)
                }
                return [f for n, f in enumerate(feats) if n not in dropped]

            wps = _keep("waypoints", fdata.get("waypoints") or [])
            trks = _keep("tracks", fdata.get("tracks") or [])
            shapes = _keep("shapes", fdata.get("shapes") or [])

            if wps:
                for p, size, cnt in write_gpx_waypoints_maybe_split(
                    wps, d / f"{safe}_Waypoints.gpx", g["name"], config=cfg
                ):
                    files.append((p, cnt))
            if trks:
                for p, size, cnt in write_gpx_tracks_maybe_split(
                    trks, d / f"{safe}_Tracks.gpx", g["name"]
                ):
                    files.append((p, cnt))
            if shapes:
                shapes = sorted(shapes, key=lambda f: natural_sort_key(f.title or ""))
                # GPX <rte type=Area>, not KML: onX ignores area colour and
                # fill in KML but keeps them from GPX (verified 2026-10-22,
                # ENG-05). The count is areas actually WRITTEN, so a polygon
                # with no usable ring shows up as dropped, not written.
                for p, size, cnt in write_gpx_areas_maybe_split(
                    shapes, d / f"{safe}_Areas.gpx", g["name"]
                ):
                    files.append((p, cnt))

            entry = {"n": n, "folder": g["name"], "files": [], "count": 0}
            for p, cnt in files:
                if not cnt:
                    # Every item of this kind was unusable: an empty file would
                    # be an import step that imports nothing.
                    continue
                rel = f"{n:02d}_{safe}/{p.name}"
                zf.writestr(rel, p.read_bytes())
                entry["files"].append({"path": rel, "count": cnt, "kml": p.suffix == ".kml"})
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
            # onX cut a 617-character note to 512 on import and dropped a
            # 3,000+ character one entirely (owner's tests, 2026-10-22).
            entry["long_notes"] = [
                [i["name"], len(i.get("desc") or "")]
                for i in g["items"]
                if i.get("included", True) and len(i.get("desc") or "") > ONX_IMPORT_NOTE_LIMIT
            ]
            if entry["files"]:
                manifest.append(entry)
            else:
                unlisted_dropped += entry["dropped"]

        runbook = build_runbook(manifest, unlisted_dropped=unlisted_dropped)
        zf.writestr("RUNBOOK.md", runbook)

    _STATE["manifest"] = manifest
    _STATE["unlisted_dropped"] = unlisted_dropped
    _STATE["runbook"] = runbook
    return buf.getvalue()


def runbook_summary(manifest, unlisted_dropped: int = 0) -> dict:
    """The numbers BOTH runbooks report (RUNBOOK.md and the on-screen one in
    web/app.js renderRunbook), computed once so they cannot disagree."""
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
        "kml_batches": sum(1 for e in manifest if any(f["kml"] for f in e["files"])),
    }


def runbook_summary_json() -> str:
    """runbook_summary for the last export, for the on-screen runbook."""
    return json.dumps(
        runbook_summary(_STATE.get("manifest") or [], _STATE.get("unlisted_dropped", 0))
    )


def build_runbook(manifest, unlisted_dropped: int = 0) -> str:
    """The artifact that was missing: how to actually get this INTO onX.

    onX creates one folder per import BATCH, and a batch accepts several files
    at once. The folder is named "Import <timestamp>" -- never from the file --
    so the user must rename it. That is why this document has to exist.
    """
    s = runbook_summary(manifest, unlisted_dropped)
    total_items = s["written"]
    kml_batches = s["kml_batches"]
    L = [
        "# Import checklist",
        "",
        f"**{len(manifest)} folders · {total_items} markups · {len(manifest)} imports**",
        "",
        "Before you start:",
        "- onX **Premium or Elite** is required to import.",
        f"- Use the **Web Map** at webmap.onxmaps.com on a computer."
        + (f" {kml_batches} of these batches contain KML, which the phone app cannot import." if kml_batches else ""),
        "- Each numbered step is ONE import. Drag in **all** the files for that step together.",
        "",
    ]
    if s["dropped"]:
        L += [
            f"> **{s['dropped']} item(s) could not be exported** because they have no usable",
            f"> coordinates. {total_items} of {s['expected']} were written.",
            "",
        ]
    if s["over_limit"]:
        # The 3,000 limit is an ACCOUNT ceiling: splitting into more files or imports
        # does not help, so the only advice that works is to send fewer.
        L += [
            f"> **Warning:** onX accounts hold at most {s['limit']:,} markups; this map has",
            f"> {s['markups']:,}. Remove or exclude some before importing.",
            "",
        ]
    for e in manifest:
        flist = ", ".join(f["path"].split("/")[-1] for f in e["files"])
        L += [
            f"### {e['n']}. {e['folder']}  ({e['count']} markups)",
            "",
            f"- [ ] My Content → **Import** → select **{flist}**",
            "- [ ] Tick **“Import map data to a new folder”**",
            "- [ ] Click **Import**",
            f"- [ ] The new folder appears at the top named `Import <today>`. "
            f"**Rename it to:** `{e['folder']}`",
            "",
        ]
    renamed = [(e["folder"], o, nw) for e in manifest for o, nw in e.get("renamed", ())]
    if renamed:
        L += [
            "### Renamed for onX",
            "",
            "These names had `! @ # $ % ^ * &` removed. Search onX for the new name.",
            "",
        ]
        L += [f"- `{o}` → `{nw}`  ({folder})" for folder, o, nw in renamed]
        L += [""]
    holes = [(e["folder"], name) for e in manifest for name in e.get("holes", ())]
    if holes:
        L += [
            "### Holes not kept in onX",
            "",
            "onX areas have one outline, so these areas were exported without their holes.",
            "",
        ]
        L += [f"- `{name}`  ({folder})" for folder, name in holes]
        L += [""]
    long_notes = [(e["folder"], n, c) for e in manifest for n, c in e.get("long_notes", ())]
    if long_notes:
        L += [
            f"### Notes longer than onX keeps on import ({ONX_IMPORT_NOTE_LIMIT} characters)",
            "",
            f"onX cut a longer imported note to {ONX_IMPORT_NOTE_LIMIT} characters, and dropped a "
            "much longer one entirely. Shorten these, or paste the rest into onX after import.",
            "",
        ]
        L += [f"- `{n}`: {c} characters  ({folder})" for folder, n, c in long_notes]
        L += [""]
    L += [
        "---",
        "",
        f"When finished, My Content should show **{len(manifest)} folders** "
        f"and **{total_items} markups**.",
        "",
        "If a folder is missing items, delete that folder and redo just its step.",
    ]
    return "\n".join(L)
