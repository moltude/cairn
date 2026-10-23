# Folders feature: release log

A running log of what was tested and found for each part of the folders feature
(rename, merge on a duplicate name, drag ticked rows to a folder, + New folder,
More ▸ Move to…). Design: `docs/design/DECISIONS.md` ENG-07. Mockups (not tracked):
DragToFolder, DragToNewFolder, NameNewFolder, RenameMerge, KeyboardMove.

- **PR-A** (`feat/stable-item-ids`): stable item ids and engine primitives, no UI.
- **PR-C**: the folders UI on top of PR-A. (Each later PR adds its own section.)

## PR-A: stable item ids and folder primitives (2026-10-23)

### What changed
- `web/bridge.py`: item `uid` is an opaque per-load id (`i0`, `i1`, …).
  `_STATE["features"]` maps uid → feature; `export_zip` pushes edits and drops exclusions
  through it while iterating each folder's current items. New `rename_folder`,
  `move_items`, `merge_folders` (ENG-07 has the API and rules).
- `web/app.js`: a comment only. Nothing in it parsed a uid (checked every `uid` use: Map/Set
  keys, `data-uid` / `data-fk` attributes, `CSS.escape` selectors, the note editor's element id
  `"note-" + uid.replace(/[^\w-]/g, "_")`); all work with any string without `|`.
- Uid parsers outside the app, all updated: `tests/caltopo_parity_helpers.py`,
  `scripts/onx_roundtrip.py` (`_feature`), `tests/web/test_web_app.py`
  (`test_uids_encode_a_per_kind_index` replaced by `test_uids_are_opaque_and_unique`).
- `tests/test_web_bridge_input_dispatch.py`: the Bitterroots baseline test rebuilds the old
  uid strings before hashing the load JSON (the baseline file is unchanged); the export
  members are pinned with no adjustment and still match.

### Tested
- `tests/test_web_bridge_folders.py` (69 tests): uids opaque, unique and mapped to their own
  features (single file and CalTopo + onX mixed); same ids on reload; rename (trim, unsafe
  characters → `_safe` file names, export dir and runbook use the new name); rename to own name
  in another case; rename onto a duplicate is reported and changes nothing; empty / whitespace /
  `None` names and unknown keys raise; Unorganized renamable; move into an existing folder (end
  of each kind's run, map order not argument order); move into a new folder (created last, new
  key, numbered last in export); duplicate new-folder name reported; emptying a folder removes
  it and closes the export numbering gap; moving to the current folder is a no-op, partly-own
  moves move only the others; unknown uids (alone or mixed with real ones) and malformed
  arguments raise and change nothing; mixed kinds keep kind runs; everything into one folder
  (1 folder, 177 markups, runbook says so); out of Unorganized into a new folder; merge (target
  keeps name and place) and rename-clash → merge; merge into itself / unknown keys; edits
  (name, icon, colour, note, track style/weight, area style/weight) and exclusions survive a
  move whether made before or after it; onX track and area colour/style/weight pinned from the
  file survive a move (re-read from the exported GPX); no-op calls leave every export member
  unchanged (Bitterroots, onX pair, mixed).
- Property test: 24 randomized sessions (6 fixture sets × 4 seeds: Bitterroots, onX dialect
  pair, onX areas pair, Dark Divide GeoJSON, CalTopo KML, CalTopo + onX mixed), 40 random
  moves / new folders / renames (with clashing names, ~70% merged) / merges / exclusion
  toggles each. After every step: no item lost or in two folders, no empty folder, unique
  trimmed case-insensitive names, `safe` = `_safe(name)`, kinds in runs, `doc.folders` in step.
  After the session: each manifest entry is the folder at its position, its files are under
  `NN_<safe>/` and hold exactly its included items, every runbook heading and "Rename it to:"
  line matches, nothing extra in the zip, and the export's markup count equals the included
  count.
- Mutation check: making `_move` append without keeping kind runs fails 24 tests; leaving
  emptied folders in place fails 29.
- In the browser: `test_folder_primitives_run_in_pyodide_and_an_edit_follows_a_moved_item`
  calls `bridge.move_items` in Pyodide after a UI edit and checks the export puts the edited
  item only in the new folder's file.
- Full suite with the dev server (port 8781): **1130 passed** (main: 1060; +69 bridge tests,
  +1 web test; the replaced uid web test is net zero).
- Manual (headless Chromium via Playwright against localhost:8781): Bitterroots, the onX
  dialect GPX+KML pair and the onX areas GPX+KML pair. For each: name edit through the row's
  input, two rows excluded through the checkboxes and More ▸ Leave out of export, a note and a
  line colour/style/weight through the app's `edit()`, and the area-fill warning on the onX
  maps (Leave these out / Keep them). The browser's export zip was compared with main's
  `web/bridge.py` run in CPython on the same files with the same edits (uids translated to the
  old format): **every member byte-identical** on all three maps; no page errors.

### Found
- `scripts/onx_roundtrip.py` also decoded uids (not in the original list); fixed.
- Review caught that the first `_move` dropped EVERY empty folder, not just the ones it
  emptied. `parse_geojson` keeps a CalTopo folder with no members, so such a folder vanished on
  the first unrelated move without appearing in `removed`. Fixed; pinned by
  `test_a_folder_empty_at_load_survives_other_moves` (fails on the old code). No fixture set in
  the property test has an empty folder, which is why it passed.
- The load-JSON half of the Bitterroots pin necessarily changes with any opaque id; handled by
  rebuilding the old strings in the test, not by re-pinning.
- An areas-only onX map where "Leave these out" excludes every item can't be exported
  ("Everything is excluded…"): existing behaviour, not a regression.

### For PR-C
- Call the primitives through `py.runPython` with `py.globals.set(...)` for arguments (as
  `apply_edits` is called), or `fn.callKwargs` for keywords; a JS object is not kwargs.
- The bridge returns a layout, not item data: the UI's `DATA.groups[*].items` carry local
  edits (`edit()` mutates them) and the bridge's copies are only updated by `apply_edits` at
  export. Rebuild `DATA.groups` from `folders` by uid, keeping the JS item objects.
- `removed` lists folders that vanished: clear a `FILTERS.folder` or `COLLAPSED` entry that
  names one. SEL / EDITS / NOTE_EDIT need nothing (uids don't change).
- `DATA.totals.folders` and per-folder counts are not recomputed by the bridge.
- NameNewFolder flow: `move_items(uids, None, "New folder")` then `rename_folder`; pick a
  default name that isn't taken (the bridge reports a clash, it doesn't number names).

## PR-B: export screen (UI-31)

Branch `feat/export-screen`. Design: `docs/design/DECISIONS.md` UI-31, from the owner-approved
mockup `ExportScreen.dc.html`.

### What changed

- `web/index.html` `#done-stage`, `web/app.js` `renderRunbook`, `web/styles.css` (export
  screen block): header with **Download all** and its hint, Back and Start over on the right;
  one intro line; the warnings; one box per folder with a **Download this folder** button, the
  file chips and three numbered steps. The tick boxes and the boxed paragraph are gone.
- `web/bridge.py`: `export_zip` keeps every member's bytes; new `export_folder_zip(n)` zips one
  folder's `NN_Name/` files from them (no second export, no RUNBOOK.md). Manifest entries gain
  `"safe"` (the sanitized folder name), used to name the folder zip `<safe>.zip`.
- RUNBOOK.md wording matches the screen (intro line, three numbered steps, "· F files", singular
  counts). Every number is unchanged. Re-pinned: the Bitterroots RUNBOOK.md digest in
  `tests/fixtures/bitterroots/export_zip_sha256_e927aa9.json` (note added) and the six
  `cairn_output/*/RUNBOOK.md` files under `tests/fixtures/caltopo-random/` and
  `tests/fixtures/dark_divide_100/` (regenerated with their `scripts/*_parity.py`).
- Status line after export: "Built N folders" (was "Built N import batches").

### Automated

`BASE_URL=http://127.0.0.1:8782/ uv run pytest`: **1069 passed** (main was 1060).

- `tests/test_export_folder_zip.py` (new, 5): Download all's layout (NN_ subfolders in screen
  order, RUNBOOK.md last); each folder zip holds exactly its folder's files, byte-identical to
  Download all, and together they are Download all minus RUNBOOK.md; a re-export with exclusions
  is followed and leaves no stale file; folders are looked up by screen number; RUNBOOK.md
  singular/plural wording and the three steps.
- `tests/web/test_web_app.py` (4 new, 1 extended):
  - `test_export_screen_is_one_box_per_folder_with_three_steps`: no inputs on the screen, no
    boxed paragraph or Copy button, header and intro text, and for every Bitterroots folder the
    heading counts, chips and steps (Paddling and Mill Creek Canyon are one file, "add this file.").
  - `test_download_all_and_each_folder_download`: real downloads of Download all and all 10
    folder buttons, names and bytes compared.
  - `test_export_screen_warnings_sit_above_the_folder_boxes`: dropped item, long note and
    3,002-markup limit warnings, all before the first box.
  - `test_export_screen_back_and_start_over`.
  - `test_onx_pair_export_downloads_a_zip_with_the_kept_icons` (enforced CSP) now also checks
    the box heading and step, no inputs, and Download this folder.
- The KML warning can't be triggered from the UI any more (areas go out as GPX, ENG-05); it is
  kept in the code and RUNBOOK.md.
- Chromium drops an 11th download started within about half a second of ten others, so the
  download test pauses 300 ms between clicks. No person clicks that fast.

### Manual (headless Chromium, 1440×900, 2026-10-23)

Loaded Bitterroots (10 folders on screen; 177 markups), `caltopo-random/onx-test-random.json`
(one folder, 3 files) and the onX pair `onx_dialect.gpx` + `.kml` (one folder). Exported, clicked
Download all and every Download this folder, unzipped each: every folder zip held only its
`NN_Name/` files, byte-identical to Download all's copies; names `Unorganized.zip`,
`Lost_Trail_Pass.zip`, …, `onx_test_random.zip`, `onx_dialect.zip`. No console errors.
Screenshots (gitignored): `tests/output/export-screen/` — `bitterroots.png`,
`bitterroots_end.png`, `bitterroots_full.png`, `one_folder.png`, `onx_pair.png`,
`warnings.png`. They match the mockup apart from the page's contour background (UI-20).

`web/walkthrough/06-export.webp` is replaced with the new Bitterroots export screen (from
`bitterroots.png`, `cwebp -q 82`) and its walkthrough text updated. Still showing the old screen:
`docs/screenshots/web-07-runbook.png` in README.md (follow-up).

### For the owner to check

- [ ] Download all, then import one folder's files in onX's Web Map following the three steps.
- [ ] Download this folder for one folder; the zip holds just that folder.
- [ ] Back returns to the map with edits intact; Start over asks first.
