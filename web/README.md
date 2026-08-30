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
3. **The import runbook.** The missing artifact — onX creates one folder per import *batch* and
   names it `Import <timestamp>`, so the checklist tells the user which files to drag together and
   exactly what to rename each folder to. KML-containing batches are flagged, because the phone
   app cannot import KML.

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
(measured: 0 of 13 engine modules importable without the CLI stack). It is now a PEP 562 lazy
`__getattr__`, so `from cairn import app` still works for the CLI while
`import cairn.core.writers` is dependency-free. All 650 existing tests still pass.

## Scope

Prototype, deliberately not at parity with the TUI: no undo, no map preview, no session
persistence, no onX → CalTopo direction. Those are on the roadmap in
`docs/PLATFORM_DECISION_2026-08-29.md`.

## Bugs this prototype exposed

Building it surfaced defects that reading the code had not. Recording them because several
are in the engine, not the web layer:

| Bug | Where | Impact |
|---|---|---|
| `load_config()` resolves `cairn_config.yaml` from the **current directory** | `cairn/core/config.py:906` | The browser (cwd `/home/pyodide`) silently loaded **144** symbol mappings while the CLI loaded **152**. `circle-p` failed to map to Parking, and **8 of 24 exported files differed**. Same bug the CLI has when run from another directory. |
| Colour edits were silently discarded | `web/bridge.py` | No writer reads `cairn_onx_color_override`; `writers.py:429` recomputes colour from `feature.color`. The picker looked like it worked and changed nothing. |
| KML shapes weren't sorted | `web/bridge.py` | The CLI natural-sorts before `write_kml_shapes` (`convert_cmd.py:458`); the bridge didn't, so placemark order diverged. |
| `typer`/`rich`/`textual` are hard dependencies | `pyproject.toml` | micropip pulled ~2.6 MB the browser never executes, busting the download gate. Worked around with `deps:false`; the real fix is an optional `cli` extra. |
| Fallback folder name came from the temp filename | `web/bridge.py` | A CalTopo export with no folders produced a folder literally named `in`, and a runbook saying "Rename it to `in`". |
| Dropped features masked the 1,500-markup warning | `web/bridge.py` | Items with no coordinates are silently skipped by `writers.py:397`; the limit check ran on the post-drop count, so a 1,601-item map could export 1,400 and never warn. |
