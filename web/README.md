# Cairn web app

The client-side web version of Cairn, and its only interface. It runs the **existing Python engine unmodified**
in the browser via Pyodide — no server, no upload, no rewrite of the transformation logic.

## Run it

```bash
uv run python web/serve.py      # http://127.0.0.1:8765
```

If the wheel is stale, rebuild it: `uv build --no-sources && cp dist/*.whl web/dist/`

## What it does

1. **Review.** Each waypoint is drawn as the marker onX will show, with its icon name; lines and
   areas show their color, style and weight. Waypoints that fell back to onX's default pin are
   marked **Default pin**, and a caution mark flags what onX won't keep as is (a note over 512
   bytes, an area fill onX resets, an item with no coordinates).
2. **Bulk edit.** Filter (search, Type, Folders, Icon; tick **Default pin** for just those),
   select, and set an icon, color or line style on all of them at once.
3. **Folders.** Drag rows onto a folder or **+ New folder**, rename and merge folders, or use
   More → Move to…. The bridge owns folder membership and names (`rename_folder`,
   `move_items`, `merge_folders`, `create_folder`, `remove_empty_folder`; DECISIONS.md ENG-07).
4. **Export.** onX creates one folder per import *batch* and names it `Import <timestamp>`, so
   the export screen shows one box per folder (its files and a Download button) plus Download
   all, and the zip carries `instructions.txt` (plain text: each folder's name to rename to, its
   files and every item). Every file is GPX: areas go out as onX Area routes
   (`<rte><type>Area</type>`), because onX ignores area colors in KML (ENG-05).

## What the numbers mean

| Number | Where | What it counts |
|---|---|---|
| Type counts | Rail, Type | Every item of that kind across all folders, excluded ones too (exclusion applies only at export). |
| Folder counts | Rail, Folders | Every item in that folder. An empty folder shows 0. |
| Icon counts | Rail, Icon | Waypoints with that icon; **Default pin** counts waypoints whose icon fell back to `Location` and that nobody has picked an icon for. |
| "N items" / "N of M shown" | Folder header | The folder's items, or how many of them pass the current filters. |
| Export warnings | Export screen | From `bridge.runbook_summary`: items dropped for having no coordinates (expected − written), notes over 512 bytes (named), and the 3,000-markup account limit, checked on max(written, expected) so dropped items can't hide it. |

An item is **Default pin** (`needs_attention`) when it is a waypoint, its resolved icon is
`Location` (the resolver's fallback), and no icon has been chosen for it. Choosing any icon,
`Location` included, clears it.

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
index.html / app.js / styles.css     UI only, no map logic
bridge.py                            the only Python outside cairn/: the adapter
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
