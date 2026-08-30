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
from cairn.core.config import GENERIC_SYMBOLS
from cairn.core.icon_resolver import IconResolver
from cairn.core.mapper import map_icon
from cairn.core.parser import parse_geojson
from cairn.utils.utils import natural_sort_key
from cairn.core.writers import (
    write_gpx_tracks_maybe_split,
    write_gpx_waypoints_maybe_split,
    write_kml_shapes,
)

# onX's waypoint palette (10). Track/line adds Fuchsia -> 11. TECH_DETAIILS.md
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
_RGBA_TO_HEX = {rgba: hex_ for _n, rgba, hex_ in ONX_COLORS}

_STATE: dict = {"doc": None, "groups": [], "config": None, "edited": set()}

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


def _explain(decision, symbol: str) -> str:
    """Turn the engine's IconDecision into a sentence a hiker can act on.

    IconResolver already records WHY it chose an icon (icon_resolver.py:24-32)
    and every caller throws it away, so the UI could only ever say "needs
    attention" without saying why. The engine's own strings are terse and
    developer-facing ("symbol exact match 'circle-p' -> 'Parking'"), so they are
    rephrased here rather than shown raw.
    """
    sym = (symbol or "").strip()
    src = getattr(decision, "source", "default")
    if src == "symbol":
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


def load_document(text: str, filename: str) -> str:
    """Parse a CalTopo export. Returns JSON describing folders and items."""
    # The filename is load-bearing, not cosmetic: for a CalTopo export with no
    # folder features, cairn/core/parser.py falls back to `filepath.stem` as the
    # folder name. Writing to a fixed /tmp/in.json made every such map produce a
    # folder called "in" -- including in the runbook's "rename it to" line.
    stem = _safe(Path(filename).stem) or "Map"
    tmp = Path(f"/tmp/{stem}.json")
    tmp.write_text(text, encoding="utf-8")
    cfg = _config()
    resolver = IconResolver(
        symbol_map=cfg.symbol_map,
        keyword_map=cfg.keyword_map,
        default_icon=cfg.default_icon,
        generic_symbols=set(GENERIC_SYMBOLS),
    )
    doc = parse_geojson(tmp)

    groups = []
    for fkey, fdata in doc.folders.items():
        # doc.folders is keyed by CalTopo's folder UUID, not its name. The
        # display name is inside the folder dict. Using the key here put raw
        # UUIDs in the runbook's "rename it to:" instruction.
        fname = (fdata.get("name") or "").strip()
        if not fname or fkey == "orphaned_features":
            fname = "Uncategorized"
        items = []
        for kind in ("waypoints", "tracks", "shapes"):
            # Index PER KIND. This used to be len(items), a running total across
            # all three kinds, so a folder's tracks were numbered from 23 and its
            # shapes from 40. Anything decoding the uid back to a position -- the
            # export's include/exclude filter does -- then addressed the wrong
            # feature, or an index past the end of the list.
            for kind_index, feat in enumerate(fdata.get(kind) or []):
                title = feat.title or ""
                why = ""
                if kind == "waypoints":
                    decision = resolver.resolve(title, feat.description or "", feat.symbol or "")
                    icon = decision.icon
                    why = _explain(decision, feat.symbol or "")
                else:
                    icon = ""
                    why = "Tracks and areas don\u2019t take an icon in onX."
                # NOT cairn.core.mapper.map_color -- that converts to KML's
                # AABBGGRR. The onX waypoint palette mapper is what writers.py:429
                # uses, and it is what the <onx:color> element needs.
                color = ColorMapper.map_waypoint_color(feat.color or feat.stroke or "")
                items.append(
                    {
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
                        # default pin is an ANSWER, not an outstanding question.
                        "confirmed": False,
                        # Unticking this drops the item from the onX export.
                        "included": True,
                        "color": color,
                        "hex": _hex_for(color),
                        # An item whose icon fell back to the generic pin AND whose
                        # source symbol carried no intent is one only a human can fix.
                        "needs_attention": kind == "waypoints"
                        and icon == "Location",
                    }
                )
        groups.append(
            {"key": fkey, "name": fname, "safe": _safe(fname), "items": items}
        )

    groups.sort(key=lambda g: -len(g["items"]))
    _STATE.update(doc=doc, groups=groups, config=cfg, edited=set())

    return json.dumps(
        {
            "filename": filename,
            "groups": groups,
            "icons": sorted(get_all_onx_icons()),
            "colors": [{"name": n, "rgba": r, "hex": h} for n, r, h in ONX_COLORS],
            "totals": {
                "folders": len(groups),
                "items": sum(len(g["items"]) for g in groups),
                "attention": sum(
                    1 for g in groups for i in g["items"] if i["needs_attention"]
                ),
            },
        }
    )


def apply_edits(edits_json: str) -> str:
    """Apply {uid: {icon,color,name}} from the UI back onto the parsed model."""
    edits = json.loads(edits_json)
    _STATE.setdefault("edited", set()).update(edits.keys())
    n = 0
    for g in _STATE["groups"]:
        for item in g["items"]:
            e = edits.get(item["uid"])
            if not e:
                continue
            for k in ("icon", "color", "name", "desc", "included", "confirmed"):
                if k in e and e[k] is not None:
                    item[k] = e[k]
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
                if item["kind"] == "waypoints":
                    # writers.py:407 reads this key.
                    feat.properties["cairn_onx_icon_override"] = item["icon"]
                # There is NO colour-override key: writers.py:429 recomputes the
                # colour from feature.color through ColorMapper. Setting a
                # "cairn_onx_color_override" property silently did nothing, so a
                # user could pick a colour, see it in the UI, and export the old
                # one. Write the hex onto feature.color instead -- an exact
                # palette hex maps to its own rgba, so this round-trips exactly.
                #
                # ONLY for items the user actually edited. Writing it for every
                # item gave features with no source colour an invented default
                # (a shape with no stroke came out Blue instead of the engine's
                # white), which silently changed output the user never touched.
                if item["uid"] in _STATE.get("edited", ()):
                    hex_ = _hex_for(item["color"])
                    feat.color = hex_
                    if getattr(feat, "stroke", None):
                        feat.stroke = hex_

    out = Path("/tmp/out")
    buf = io.BytesIO()
    manifest = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, g in enumerate(groups, 1):
            fdata = doc.folders[g["key"]]
            safe = g["safe"]
            d = out / f"{n:02d}_{safe}"
            d.mkdir(parents=True, exist_ok=True)
            files = []

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
            trks = _keep("tracks", (fdata.get("tracks") or []) + (fdata.get("routes") or []))
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
                p = d / f"{safe}_Areas.kml"
                write_kml_shapes(shapes, p, g["name"])
                files.append((p, len(shapes)))

            entry = {"n": n, "folder": g["name"], "files": [], "count": 0}
            for p, cnt in files:
                rel = f"{n:02d}_{safe}/{p.name}"
                zf.writestr(rel, p.read_bytes())
                entry["files"].append({"path": rel, "count": cnt, "kml": p.suffix == ".kml"})
                entry["count"] += cnt
            entry["expected"] = len(wps) + len(trks) + len(shapes)
            entry["excluded"] = sum(
                1 for i in g["items"] if not i.get("included", True)
            )
            entry["dropped"] = max(0, entry["expected"] - entry["count"])
            if entry["files"]:
                manifest.append(entry)

        runbook = build_runbook(manifest)
        zf.writestr("RUNBOOK.md", runbook)

    _STATE["manifest"] = manifest
    _STATE["runbook"] = runbook
    return buf.getvalue()


def build_runbook(manifest) -> str:
    """The artifact that was missing: how to actually get this INTO onX.

    onX creates one folder per import BATCH, and a batch accepts several files
    at once. The folder is named "Import <timestamp>" -- never from the file --
    so the user must rename it. That is why this document has to exist.
    """
    total_items = sum(e["count"] for e in manifest)
    total_expected = sum(e.get("expected", e["count"]) for e in manifest)
    total_dropped = sum(e.get("dropped", 0) for e in manifest)
    kml_batches = sum(1 for e in manifest if any(f["kml"] for f in e["files"]))
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
    if total_dropped:
        L += [
            f"> **{total_dropped} item(s) could not be exported** because they have no usable",
            f"> coordinates. {total_items} of {total_expected} were written.",
            "",
        ]
    # Check the limit against what the user was SHOWN, not just what survived --
    # otherwise dropped items can mask a genuine over-limit map.
    if max(total_items, total_expected) > 1500:
        L += [
            f"> **Warning:** this map has {total_expected} markups, which exceeds onX's",
            "> 1,500-markup account limit. The import will fail unless you split it.",
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
    L += [
        "---",
        "",
        f"When finished, My Content should show **{len(manifest)} folders** "
        f"and **{total_items} markups**.",
        "",
        "If a folder is missing items, delete that folder and redo just its step.",
    ]
    return "\n".join(L)
