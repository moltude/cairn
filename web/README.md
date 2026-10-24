# Cairn web prototype

A working, client-side web version of Cairn. It runs the **existing Python engine unmodified**
in the browser via Pyodide — no server, no upload, no rewrite of the transformation logic.

## Run it

```bash
uv run python web/serve.py      # http://127.0.0.1:8765
```

If the wheel is stale, rebuild it: `uv build --no-sources && cp dist/*.whl web/dist/`

## What it demonstrates

Three things that justified moving off the terminal, all working end to end:

1. **Visual editing.** Real colour swatches and icon names, with the items that need a human
   decision marked in amber. In the TUI these are the strings `"Water Source"` and
   `"rgba(8,122,255,1)"`.
2. **Bulk edit.** Filter to "only items needing attention", select, set an icon on all of them at
   once, and watch the attention count fall.
3. **The import instructions.** The missing artifact — onX creates one folder per import *batch* and
   names it `Import <timestamp>`, so the export screen and `instructions.txt` (plain text, since
   2026-10-23 round 4; it was RUNBOOK.md) tell the user which files to import together and
   exactly what to rename each folder to. Every file is GPX: areas go out as onX Area routes
   (`<rte><type>Area</type>`) since 2026-10-22, because onX ignores area colours in KML
   (ENG-05). The KML-batch warning is still wired up but no web export triggers it.

## What the numbers mean

Each row cites the code that produces the number. "Item" means one waypoint, track/line or
shape/polygon as read by the parser. Line numbers refer to the files as of this commit.

| Number | Where shown | What it counts | Source |
|---|---|---|---|
| Folders | Stats card, "Folders" (`app.js:108`) | Every folder group loaded from the file, including folders whose items are all excluded or empty. Groups are sorted by size. | `bridge.py:187` (`len(groups)`), `bridge.py:177` |
| Markups | Stats card, "Markups" (`app.js:109`). A separate number, the export-side total in the runbook's "N markups" (`bridge.py:335`, `bridge.py:342`), counts only items actually written, so it can differ from the card. | Sum of `waypoints + tracks + shapes` across all folders at load. Waypoints are `Marker` + `Point`; tracks are `Line` or `Shape` with `LineString` geometry; shapes are `Shape` with `Polygon` geometry (`parser.py:65-78`). Excluded items **are** counted, because exclusion is applied only at export. Features that fit none of those classes (e.g. `geometry: null` non-folder features, or other geometry types) are never stored, so they are not counted. Routes are not classified, so they are not counted either. | `bridge.py:188` (`totals.items`), `bridge.py:108-115`, `parser.py:65-112` |
| onX imports | Stats card, "onX imports" (`app.js:110`) | This is **the same value as Folders** (`t.folders`), not a separate count of import batches. In the export, one batch (one `Import mm/dd/yy H:MM` folder in onX) is produced per folder that has at least one file. Folders with no exported files are dropped from the manifest, so the runbook's count can be lower than this card. | `app.js:110`, `bridge.py:318` (`manifest.append` only when `entry["files"]`), `bridge.py:335-342` (checklist "N folders · N imports") |
| N items (per folder pill) | Each folder header pill, "N items" (`app.js:142`) | Count of rows **currently visible** after the search box, "only needs attention" toggle and type filter (`visibleItems`, `app.js:118-124`). It is not the folder's total. Excluded rows are included in the count if visible. | `app.js:134`, `app.js:142` |
| N default pin (per folder pill) | Folder header pill, "N default pin" (`app.js:136`, `app.js:143`) | Count of **visible** rows in that folder that have `needs_attention` set. Because it is computed from `visibleItems`, it changes when a filter is applied. | `app.js:136`, `app.js:143` |
| Using default pin (stats card) | Stats card, warn-coloured tile (`app.js:111`) | Initially `totals.attention` from load: all waypoints across all folders whose icon resolved to `Location` (the `default_icon`) and was not confirmed. It counts **excluded** items too. After any edit, the UI recomputes it across all groups (`app.js:276-277`). | `bridge.py:189-193`, `bridge.py:169-170`, `app.js:276-277`, `config.py:508`, `icon_mappings.yaml:23` |

What makes an item "default pin" (`needs_attention`):

- It must be a **waypoint** (`kind == "waypoints"`).
- Its resolved onX icon must equal `Location`. That is the default icon from `icon_mappings.yaml:23`
  (`config.py:508`), which is what the resolver falls back to when no symbol or keyword matches.
- It has not been confirmed. Choosing any icon, including `Location` on purpose, sets `confirmed`
  and clears the flag (`app.js:266-271`; `bridge.py:214-223`). Tracks and shapes are never default
  pins, since they have no icon (`bridge.py:144-145`).

Notes:

- The "onX imports" card and the number of folders exported can differ. The card uses the folder
  count; the export lists only the folders that produced files.
- "Dropped" items: the export screen says items "could not be exported because they have no usable
  coordinates" (`bridge.py:353`). The count is `expected − written` per folder
  (`bridge.py:312`, `bridge.py:316`). I did not read the writers to confirm exactly which
  geometries are dropped, so that rule is inference from the message and the arithmetic.
- The stats-card numbers are computed once at load and are not recounted from the exported files.

## Measured (real Chromium, 1.7 MB / 177-item map)

| | | Gate |
|---|---|---|
| Pyodide cold boot + engine load | **2.8 s** | ≤5 s ✅ |
| Total transferred | **11.6 MB** | ≤15 MB ✅ |
| Parse | 0.13 s | |
| Export (10 batches, 25 files) | 0.19 s | |
| Import batches required | **10** (not 24 — one batch takes several files) | |

**Output is byte-identical to the CLI: 24 of 24 files**, GPX and KML, on the full
Bitterroots map with no edits applied. That is the proof the engine is genuinely reused
rather than reimplemented — `tests/web/test_web_app.py` keeps it honest.

## Architecture

```
index.html / app.js / styles.css     UI only — no map logic (~370 lines)
bridge.py                            the ONLY new Python: a thin adapter (~250 lines)
dist/cairn_maps-*.whl                the existing engine, unmodified
```

`bridge.py` imports `cairn.core.parser`, `cairn.core.writers`, `cairn.core.mapper`,
`cairn.core.color_mapper` and `cairn.core.config` and calls them exactly as the CLI does. Every
GPX and KML byte is produced by the same writers the 342 engine tests already cover.

## The one change this required in `cairn/`

`cairn/__init__.py` used to be `from cairn.cli import app, main`, which meant importing *any*
submodule pulled in typer, rich and textual — so the engine could not load in a browser at all
(measured: 0 of 13 engine modules importable without the CLI stack). That was first
fixed with a lazy import; since 2026-10 the CLI and TUI are gone entirely (git tag `cli-final`),
so the engine has no terminal dependencies at all. Measurements below that compare against "the
CLI" date from when it still existed.

## Scope

Deliberately not at parity with the former TUI: no undo, no map preview, no session
persistence, no onX → CalTopo direction. Those are on the roadmap in
`docs/PLATFORM_DECISION_2026-08-29.md`.

## Bugs this prototype exposed

Building it surfaced defects that reading the code had not. Recording them because several
are in the engine, not the web layer:

| Bug | Where | Impact |
|---|---|---|
| `load_config()` resolves `cairn_config.yaml` from the **current directory** | `cairn/core/config.py:906` | The browser (cwd `/home/pyodide`) silently loaded **144** symbol mappings while the CLI loaded **152**. `circle-p` failed to map to Parking, and **8 of 24 exported files differed**. Same bug the CLI has when run from another directory. |
| Colour edits were silently discarded *(fixed)* | `web/bridge.py` | No writer reads `cairn_onx_color_override`; `writers.py:429` recomputes colour from `feature.color`. Fixed by writing the picked color onto `feature.color` directly for edited items (`bridge.py:257-272`). |
| KML shapes weren't sorted | `web/bridge.py` | The CLI natural-sorts before `write_kml_shapes` (`convert_cmd.py:458`); the bridge didn't, so placemark order diverged. |
| `typer`/`rich`/`textual` are hard dependencies | `pyproject.toml` | micropip pulled ~2.6 MB the browser never executes, busting the download gate. **Fixed 2026-10**: the CLI was removed, so `pyyaml` is the only dependency. `deps:false` stays as a guard. |
| Fallback folder name came from the temp filename | `web/bridge.py` | A CalTopo export with no folders produced a folder literally named `in`, and a runbook saying "Rename it to `in`". |
| Dropped features masked the 1,500-markup warning | `web/bridge.py` | Items with no coordinates are silently skipped by `writers.py:397`; the limit check ran on the post-drop count, so a 1,601-item map could export 1,400 and never warn. |
