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
