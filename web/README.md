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

## Measured (2026-08-30, real Chromium, 1.7 MB / 177-item map)

| | | Gate |
|---|---|---|
| Pyodide cold boot + engine load | **2.8 s** | ≤5 s ✅ |
| Total transferred | **11.6 MB** | ≤15 MB ✅ |
| Parse | 0.13 s | |
| Export (10 batches, 25 files) | 0.19 s | |

These predate the folders release and the micropip-free boot; re-measure before quoting them.

## Architecture

```
index.html / app.js / styles.css     UI only, no map logic
bridge.py                            the only Python outside cairn/: the adapter
dist/cairn_maps-*.whl                the engine, as a wheel
```

`bridge.py` routes each file on `cairn.io.input_check.detect()` to a reader, keeps the edit
and folder state, and calls `cairn.core.writers` for every exported byte. Modules it reaches
carry a `# Web engine:` header (`tests/test_web_engine_surface.py`). Deployment is in
[`docs/DEPLOY.md`](../docs/DEPLOY.md).

## Scope

No undo, no map preview, no saved sessions, no onX → CalTopo direction, no merging of a second
map into one already loaded (DECISIONS UI-12). Open ideas are in [`TODO.md`](../TODO.md).

## Engine bugs the prototype found (2026-08-30)

Building the web app surfaced engine defects that reading the code had not. All are fixed or
moot now except the first, which the web app sidesteps:

- **`load_config(None)` reads `cairn_config.yaml` from the current directory**
  (`cairn/core/config.py:load_config`). In the browser that silently loaded 144 symbol mappings
  instead of 152. `bridge.py` passes an explicit path; the fallback is still open in `TODO.md`.
- KML areas came out in a different order than the CLI's. Moot: export writes no KML now.
- Colour edits were discarded: no writer read the override. Fixed in `bridge.py`.
- A CalTopo export with no folders got a folder named after the temp file (`in`). Fixed.
- Items dropped for having no coordinates could hide the account-limit warning. The check now
  uses max(written, expected).
- `typer`/`rich`/`textual` were hard dependencies. Gone with the CLI (git tag `cli-final`);
  `pyyaml` is the only runtime dependency.
