**A dumping ground for ideas, known bugs and functionality I need to implement**

> Consolidated 2026-08-29. Absorbed the live backlog from `cairn/Instructions for agent.md`
> (a Dec 2025 document whose status header said "ALL PHASES COMPLETED / Production ready!"
> and which linked six `docs/*.md` files that no longer exist). Verified findings live in
> `docs/CODEBASE_AUDIT_2026-08-29.md` and `docs/UX_AUDIT_2026-08-29.md`; this file stays a
> dumping ground.

---

## Confirmed bugs (verified 2026-08-29 by running the tool)

* **Saved config silently vanishes depending on your working directory.** `load_config()` resolves
  `Path("cairn_config.yaml")` relative to CWD (`core/config.py:877,906`), and the TUI passes
  `load_config(None)` with no override (`tui/app.py:189,1566`) so `--config` never reaches it.
  Proved: 152 symbol mappings load from the repo root, **144 from another directory** — 8 saved
  mappings gone, no warning. Fix: `--config` → `$CAIRN_CONFIG` → `~/.config/cairn/config.yaml` →
  directory-local, merged, and print which file loaded.
* **Cairn ships an icon onX does not accept.** `Cabin` is absent from onX's 95-icon vocabulary
  (`normalize_onx_icon_name("Cabin")` → `None`), but `DEFAULT_SYMBOL_MAP` maps `cabin`/`hut`/`yurt`
  to it. 4 waypoints in the Bitterroots fixture export `<onx:icon>Cabin</onx:icon>` and will land
  as the default pin. `save_user_mapping()` already rejects icons that fail this check — the
  validation exists and isn't applied to Cairn's own defaults. `Shelter` is the right target.
  A full audit of all three default tables found exactly one such name.
* **Numbered waypoints defeat keyword matching.** `_TOKEN_RE = r"[a-z0-9]+"`
  (`core/icon_resolver.py:35`) merges trailing digits: `Chute1` → `chute1`, which never matches
  the keyword `chute`. `Camp 2` resolves; `Camp2` doesn't. Strip trailing digits before tokenizing.
* **Two dead config entries.** `ICON_COLOR_MAP` and `DEFAULT_KEYWORD_MAP` each define `"Camp"`
  twice (AST-verified); Python keeps the last silently.
* **Polygons cannot be edited at all.** There is no `_selected_shape_keys` anywhere in the
  codebase, so shapes pass through the TUI untouched — 17 of 177 items (9.6%) in the real fixture.

* ~~**`<desc>` is a debug dump in every exported waypoint.**~~ **Fixed 2026-08-29.**
  `<desc>` now carries only the user's own note (omitted entirely when there is no note);
  icons/colors/styles still travel in the `<onx:>` extensions. The old key=value block is
  available via `--debug` on `migrate onx` / `migrate caltopo-to-onx` (and
  `--description-mode debug` on `convert`). Covered by `tests/test_desc_output.py`.
* **`--no-interactive` still prompts, then aborts** on empty stdin, so Cairn can't be scripted
  or run in CI. (Known since Dec 2025; never fixed.)
* **"Order confirmed (--yes flag)"** prints for a flag that doesn't exist on `migrate onx`, and
  prints twice, around a summary block that also prints twice.
* **The success path wraps the output directory mid-character**, so the one thing the user needs
  at the end is unreadable.
* **NO_COLOR is not respected.** (Known since Dec 2025.) Cause now confirmed: Textual has
  supported it since 0.80.0, but `cairn/tui/theme.tcss` has **zero** uses of the `nocolor`
  pseudoclass and **75 hardcoded color literals**, and nothing in the Python reads `NO_COLOR`.
  Routing those literals through theme tokens is the same job as "use color labels to ensure
  theme migration" below — do them together.
* **`set-default-color` help text is incomplete.** (Known since Dec 2025.)
* **Running the tool wrote into its own installed package.** Every `migrate` run — and every
  test run — appended to the version-controlled `cairn/data/icon_catalog.yaml`, leaking test
  fixture names ("Test Waypoint", "JsonWaypoint") into shipped data and dirtying the git tree.
  On a real `pip`/`brew` install that path is inside site-packages and may be read-only.
  **Fixed 2026-08-29**: recording is opt-in via `CAIRN_ICON_CATALOG`; the data is write-only
  telemetry that nothing reads back.
* TUI bugs — see `docs/UX_AUDIT_2026-08-29.md` §2.2 for the verified list with file:line, and
  `docs/TUI_DESIGN_2026-08-29.md` for the ranked fix plan.
* **The import gap — now fully characterised.** onX *does* have folders; they are created at
  import time, one per import *batch*, and a batch accepts multiple files of mixed format. The
  folder is named `"Import mm/dd/yy H:MM"` — a timestamp — so no filename or metadata Cairn writes
  can ever set it; the user must rename after import. Verified by reading onX's shipped Web Map
  JS (`multiple:""`, `accept=".gpx,.kml"`, `addCollection({name:"Import"+...})`) plus the Zendesk
  API. Consequence: the real Bitterroots map needs **10 import batches, not 24 imports**, and the
  missing artifact is a generated RUNBOOK telling the user the batches, the order, and the exact
  name to type. See `docs/FIDELITY_MODEL_2026-08-29.md` and
  `docs/PLATFORM_CONSTRAINTS_2026-08-29.md`.
* Workflow redesign — `docs/WORKFLOW_REDESIGN_2026-08-29.md` reconciles three design proposals
  against `docs/DECISION_SURFACE_2026-08-29.md`, which measures that the tool makes users walk
  68 waypoints to answer ~24 questions.

## Features

* **Bulk edit is the killer feature and is half-built.** Multi-select works in the TUI, but the
  only bulk operation is "give everything the same literal name." Prefix/suffix rename exists
  only in the legacy CLI (`core/preview.py:67`). Needs: range syntax (`1,3,5-9`, `all`),
  filter-then-select-all, prefix/suffix + find-replace, a preview of resulting names, and undo.
  Use case: select every water waypoint → Name: Water, Icon: Water, Color: Blue. onX makes this
  either impossible or very painful, which is the whole reason to reach for Cairn.
* Add a feature to include the CalTopo Folder name in either the Name or Description for all elements.
* Make `tui` the default when `cairn` is run with no arguments.
* Support for polygons/areas.
* Configurable default map directory (e.g. `/Users/scott/maps/`) so the file browser starts
  somewhere useful.
* Stop writing the `ICON_REPORT.md` summary file by default — it was a debugging artifact.
* **Move the unmapped-symbol warning to the START of the process**, not the end. Right now you
  learn which icons failed to map only after the files are already written.
* Investigate line styling in onX.
* Investigate: can onX data be exported, modified, and re-imported so it *updates* the same
  objects rather than creating duplicates? (Skeptical this is possible — worth 30 minutes to
  find out, not more.)

## CLI shape

* The subcommand tree is bigger than it needs to be.
  * `convert` — registered `hidden=True`, 36% covered, 1115 lines. Determine what it's actually
    for; if `migrate` covers it, delete it.
  * `icon` — managing icon mappings belongs in the config file, not the CLI.
  * `config` — a config subcommand is useful, but this isn't the one. Revisit what should be
    configurable at all.
* Generalize the naming: it's really "migrate to onX" / "migrate to CalTopo" regardless of
  whether the source is GPX, KML or GeoJSON. (Partly done — `migrate onx` / `migrate caltopo`
  aliases exist, and `migrate onx` now accepts `.gpx` as of 2026-08-29.)
* **Invalid input should never abort the process.** A missing directory, or a directory with no
  map files, should re-prompt rather than exit.

## Styling

* Increase the font size of the 'Folder' name on all screens.
* Make the scrollbar brown(ish) to match the theme.
* Use color labels so theme migration works.
* Change the label `Choose the GPX or JSON data you want to migrate to onX`.
* Remove `TUI` from app labels and text — still present in at least 3 places
  (`app.py:423`, `app.py:2861`, `file_browser.py:202`).
* Export Complete screen should show `File written to: <path>` above `Another file?`.

## Housekeeping

* Reduce the 280 silently-swallowed exceptions in `cairn/tui/` (264 are bare `except: pass`).
  A crash and a no-op currently look identical from the user's chair.
* Fix the 35 TUI tests that swallow exceptions and assert nothing — start with the 15 in
  `tests/tui_harness.py`, which every TUI test inherits.
* Add tests for `core/preview.py` (16% covered, 1946 lines, on the primary user path).
* Re-enable the 2 skipped regression tests, or delete them if the behavior is intentionally gone.
* `TECH_DETAIILS.md` is misspelled.
* `pyproject.toml` pins `textual>=0.58.0` — a range spanning 0.58 to 8.2.8 that has never been
  tested. A grep for every API removed/renamed across those versions found zero hits in `cairn/`
  and `tests/`, so the upgrade is low-risk; tighten the pin to what is actually verified
  (`>=6.11,<9`).
