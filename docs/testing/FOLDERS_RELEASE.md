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

## Hardening (engine + export) (2026-10-23)

Branch `test/folders-hardening` (on `feat/folders-release`, 1139 tests). Adversarial pass over
`rename_folder` / `move_items` / `merge_folders` and the Download all / Download this folder export.

### What was run
- **Map generator** (`tests/hardening_maps.py`, tracked; scratch drivers in the gitignored
  `tests/output/hardening/`): CalTopo GeoJSON with 0, 1, 30 and 200 folders; empty folders;
  lines-only and areas-only folders; 28 hostile names (case/whitespace twins, `A/B` vs `A_B` vs
  `A:B`, `..`, `.`, `CON`, `NUL`, trailing dots, blank, unicode, RTL, emoji, emoji-only, 300-char
  and 200-`ä` names, a right-to-left override, tabs, newlines, quotes, `../../etc/passwd`);
  items with no coordinates (null geometry, empty line, empty point); polygons with 2 holes;
  3 KB notes; a 5,200-item and a 6,000-item folder (GPX splits at 3.75 MiB into 3 files).
  Also the Bitterroots map, the onX dialect pair, the onX areas pair and CalTopo + onX mixed.
- **Bridge fuzzer** (`tests/output/hardening/fuzz.py`): 13 maps x 4 seeds x 40 random steps of
  apply_edits (names, notes, icon, colour, style/weight, exclusion), move to an existing folder,
  move to a new folder (hostile names, clashes), rename (hostile names, case/space variants),
  merge, export, and six error-path calls (each must raise ValueError and leave the layout
  unchanged). After every step: no item lost or duplicated, unique keys, no new duplicate folder
  name. After every export: no duplicate or unsafe zip paths (no `..`, absolute, backslash, NUL,
  component over 255 bytes), zip members = manifest files + RUNBOOK.md exactly, folder prefix and
  name match the folder at that position, items in files + dropped = included items, each file's
  element count = its manifest count, every file named in RUNBOOK.md, and every
  `export_folder_zip(n)` byte-equal to Download all's copies. 52 sessions, 0 failures after the fixes.
- **Real browser** (headless Chromium, `tests/output/hardening/browser.py`, port 8785): 7 maps
  (1, 30, 200 folders; empties; no-coordinate items; hostile names; 5,200 items). Each: load,
  Export, Download all, click EVERY "Download this folder" and unzip (names and bytes vs the full
  zip), Back, Export again, Download this folder, Start over, load a second map, export,
  download a folder, reload. 0 console or page errors, 0 mismatches. 5,200 items: load 4.2 s,
  export 0.7 s, JS heap 81 MB, 5,211 rows rendered. Python side (CPython): 6,000 items load
  0.4 s, export 0.1 s, ~290 MB peak RSS.
- Full suite: `BASE_URL=http://127.0.0.1:8785/ uv run pytest`: **1159 passed** (1139 + 20).

### Bugs
| # | Severity | Repro | Status |
|---|----------|-------|--------|
| 1 | High | Load or rename a folder to a name over ~250 bytes (CalTopo allows it; 300 `x`, or 100 CJK characters) and press Export: `OSError: File name too long` from `export_zip`; nothing exports. | Fixed: `_safe` caps the file-system name at 80 UTF-8 bytes (display name untouched, `NN_` still keeps folders apart). |
| 2 | High | Load map A, export, load map B (no export yet), call `export_folder_zip(1)`: serves map A's files. `load_files` left `manifest` / `blobs` / `runbook` from the last export. | Fixed: `load_files` clears them; `export_folder_zip` then raises "Export again." The shipped UI can't reach this (the buttons exist only after an export), but any caller of the bridge could. |
| 3 | Low | `_safe` could end in `_` after truncation. | Fixed with #1. |
| 4 | Info | Two folders whose names differ only in case/whitespace in the SOURCE file (CalTopo allows "Camp" and "camp") both load; the no-duplicate rule only binds renames and new folders. Renaming one onto the other reports a duplicate and offers merge, as designed. | Open by design; worth stating in ENG-07. |
| 5 | Low | With 100+ folders the prefix is `100_x`, which sorts before `11_x` in a file manager. 200-folder map exports correctly otherwise. | Open (cosmetic; needs a padded width, changes names only above 99 folders). |
| 6 | Info | After a move/rename/merge, `export_folder_zip(n)` still serves the LAST export whole and self-consistent until the UI exports again (pinned by a test). | Open by design. |

No other violation was found: moves, merges, renames and exclusions never lost or duplicated an
item, error paths never changed state, and per-folder zips were byte-identical in all runs.

### UI observations (not edited)
- Download file name is `${e.safe}.zip`; two folders with the same safe form ("A/B", "A_B") both
  download as `A_B.zip` (the browser adds " (1)"). Harmless, but could use the `NN_` prefix.
- `window.__cairnLoaded` stays true after Start over (test hook only; a test must reset it).

Regression tests: `tests/test_web_bridge_hardening.py` (20 tests; 12 fail on the pre-fix bridge).

## PR-C: the folders UI (UI-32) (2026-10-23)

Branch `feat/folders-ui` (on `feat/folders-release`, merged again after the hardening pass
`eafb1f6`). Design: `docs/design/DECISIONS.md` UI-32.

### What changed
- `web/app.js`: drag rows onto a rail folder or "+ New folder" (pointer events, a "Move N items"
  label, "here now", rail auto-scroll); new-folder naming in the rail; rename by clicking a
  folder's name in its table header; the merge offer on a taken name; More ▸ Move to… with arrow
  keys; `applyLayout` rebuilds DATA.groups from the bridge's layout; Start over counts moves and
  renames; a renamed "Unorganized" is an ordinary folder. Per-folder download named
  `NN_<safe>.zip` (hardening note).
- `web/index.html`: "Move to…" first in More, `#move-pop`, Help section "4 · Folders".
- `web/styles.css`, `web/icons.js` (the move glyph).
- `web/bridge.py`: `merge_folders` removes the source folder even when it is empty.

### Automated
`BASE_URL=http://127.0.0.1:8784/ uv run pytest`: **1179 passed** (1159 + 20).

- `tests/web/test_web_app.py` (19 new): drag one row (label, here now, drop highlight, dimmed
  row, counts, status, UI and bridge layouts equal); drag several ticked rows, then an unticked
  row alone; drag from an unfocused name but not from a focused one; drag onto + New folder and
  name it, Esc keeps "New folder", the next default is "New folder 2", click-away keeps it; drop on
  its own folder, on the list, the search box and "All" (no-op, no stray click); Esc cancels a
  drag (and the release over a folder doesn't filter); rename (empty, same name, Esc, other case,
  click-away); rename onto a taken name (dialog text, Cancel default, Enter and Esc cancel, Move
  them merges and the target keeps its place); keyboard Move to… end to end (Esc returns focus,
  arrows skip here now and wrap, Home/End, + New folder…); Move to… unfolds a folded Folders
  section to name; an emptied folder disappears with its folder filter; a merged-away folder's
  collapsed state is forgotten; moved items keep their edits and exclusion through export; the
  export after moves and renames (box names, counts, order, every per-folder zip unzipped and
  checked, Back, move, export again); Start over counts moves and renames; regression tests for
  bugs 3–6 below; a 60-folder rail auto-scrolls to + New folder.
- `tests/test_web_bridge_folders.py`: `test_merging_an_empty_folder_removes_it`.
- Two existing download tests now expect `NN_<safe>.zip`.

### Manual / break-it (headless Chromium 1440×900, port 8784)
Scripts in the gitignored scratch area. Maps: Bitterroots, the onX areas pair, and generated
CalTopo GeoJSON from `tests/hardening_maps.py`: 34 hostile names with 3 empty folders, 200
folders / 1,100 items, and case twins ("Camp", "camp", "Camp", " Camp ", "A/B", "A_B", emoji,
CJK). On each map: 15 rapid drags to random targets (naming or Esc-ing new folders), a drag during
a search, renames to `a/b`, `..`, 300 × `x`, emoji, padded and accented names, a merge by case
variant, exclude then move the excluded rows to a new folder, export and download the first and
last folder zips, Back, drag to a new folder, export again, everything into one folder (Ctrl+A,
Move to…), export, Start over, next map. After every step: UI layout == bridge layout, rail
entries == folders, no item lost or doubled, totals, no stale filter, no leftover drag label, no
error status, no console or page errors; after every export, manifest names and counts == the
folders with included items, folder zips == their manifest files, zip names `NN_…`, no path part
over 255 bytes. Also: a note draft on a row dragged out of a folder filter, a popover open on a
dragged row, switching from one header name to another, the area-fill dialog blocking a drag,
keyboard Tab order, rail auto-scroll down and up on 200 folders. Final run: 0 problems.

Screenshots (gitignored): `tests/output/folders-ui/` — `1-drag-to-folder.png`,
`2-drag-to-new-folder.png`, `3-name-new-folder.png`, `4a-rename-in-header.png`,
`4b-rename-merge.png`, `5a-more-menu.png`, `5b-keyboard-move.png`, `5c-after-move.png`. They
match the mockups apart from the rail's existing Type and Icon sections and the contour background.

### Bugs found and fixed
| # | Bug | Fix | Test |
|---|-----|-----|------|
| 1 | "+ New folder" did nothing: its drop key `"\u0000new"` went through innerHTML, and the HTML parser turns NUL into U+FFFD, so the bridge was asked for folder "�new". | The key is set as a DOM property. | `test_drag_onto_new_folder_then_name_it` |
| 2 | With the selection kept after a move, dragging one moved row out again dragged every row of the old selection (emptying the new folder). | Moved rows are unticked; other ticks stay (UI-32). | `test_drag_several_ticked_rows_moves_them_all`, `test_export_after_moves_and_renames` |
| 3 | Any re-render while a folder name was open closed it: Chrome fires blur on a focused element as it is removed, which saved and closed the field. Seen when leaving one header name for another (the second closed at once). | Hosts are emptied through `rebuild()`, and a blur during it is ignored. | `test_leaving_one_folder_name_for_another_keeps_the_second_open` |
| 4 | An open note on a row that a move took off screen (folder filter) was closed by the next render and its draft lost. | Its draft is saved as an edit. | `test_an_open_note_moved_out_of_view_keeps_its_draft` |
| 5 | Renamed "Unorganized" kept its italics and "Not in any CalTopo folder" (matched by key); a folder renamed to "Unorganized" turned italic. | Name and key both, and not after a user rename. | `test_a_renamed_unorganized_is_an_ordinary_folder` |
| 6 | Merging a folder that loaded empty (rename onto a taken name, Move them) left it in place under its old name. | `merge_folders` always removes the source. | `test_merging_an_empty_folder_removes_it` |
| 7 | Rail auto-scroll was too slow for 200 folders (~600 px/s, ~9 s to the end). | Speed grows with depth, up to 48 px a frame over the footer (~2.5 s for 8,000 px). | `test_a_long_rail_scrolls_while_dragging_to_new_folder` |
| 9 | Esc pressed twice while still holding a drag: the second Esc cleared the selection, and the release's click was no longer swallowed (it could toggle the folder filter under the pointer). | A cancelled drag stays the drag's until released; a second Esc is ignored. | `test_escape_cancels_a_drag` |
| 8 | Two folders sanitizing alike ("A/B", "A_B", "..", "/") downloaded as the same zip name. | `NN_<safe>.zip` (hardening note). | updated download tests |

### Open
- A 300-character name wraps over many lines in the rail and header (shown in full on purpose;
  the name input caps typing at 100 characters, a loaded name may be longer).
- Folders with identical names from the file ("Camp" twice) are told apart only by their counts
  and order; the merge dialog names the first.
- A folder whose items are all excluded has no export box (existing PR-A/B behaviour).
- Folders can't be dragged to reorder, and an empty folder can't be made up front (owner rules).
- "Merge a folder into itself" can't be reached from the UI (renaming to its own name is a no-op
  or a case change; the bridge's own no-op is pinned by PR-A tests).
- If `applyLayout` ever threw after the bridge had moved items, the UI and bridge would disagree
  until the next load (the catch doesn't roll back). Never seen: break-it checked UI == bridge
  after every step.

### For the owner to check
- [ ] Drag ticked rows to a folder, and to + New folder, in a real browser (mouse and trackpad).
- [ ] The decisions listed under UI-32: drag from an unfocused name, moved rows unticked, rename
      in the header vs naming a new folder in the rail, the rail unfolding during a drag.

## Round 2 fixes (2026-10-23)

Inputs (gitignored, `tests/output/`): `round2-findings.md` (F1–F7 from the scripted fuzzer,
H1–H6 from a human-style QA pass, L1), `code-review-round1.md` (red-team review items 1–10),
`qa-round2-human.md` with its `r2-*.png` screenshots, and `qa-fuzz/` (`fuzz_ui.py`, repro
probes `probes/probe1..9.py`, run records, generated maps). Design changes are in DECISIONS.md
UI-32 and ENG-07 ("Round 2").

### Findings, fixes and tests
Tests are in `tests/web/test_web_app.py` (e2e) unless they start with `bridge:`
(`tests/test_web_bridge_folders.py`). Every e2e test below was also run against the previous
`web/app.js`: 27 of the 31 failed, the 4 that passed being the 0 ms-hold cases of F1, which
never reproduced it.

| # | Finding | Fix | Test |
|---|---------|-----|------|
| CR1 | Window blur / pointercancel mid-drag left DRAG cancelled-but-held, waiting for a pointerup that never came: the next press, text selection, Esc and click were swallowed. | `abandonDrag()`: blur and pointercancel drop the drag outright; only Esc keeps the held state (its release still comes). | `test_a_drag_the_window_loses_leaves_nothing_held[window-blur, pointercancel]` |
| CR2 | `move_items` / `merge_folders` change the bridge before `applyLayout` validates; a throw left the screen on the old folders while export wrote the moved ones. | `applyLayout` checks everything before changing anything; `syncLayout` falls back to `bridge.layout_json()`; any failed folder action re-syncs from it and re-renders. | `test_a_failed_layout_apply_shows_the_bridges_layout` |
| CR3 | `_safe` cut one character at a time (O(L²)). | One UTF-8 byte slice, `decode("utf-8", "ignore")`: same result. | bridge: `test_safe_cuts_by_bytes_in_one_step_with_the_same_result` (8 names, against the old loop), `test_safe_of_a_huge_name_is_fast` |
| CR4 | RUNBOOK.md put a raw folder name in a code span: a backtick or newline broke "Rename it to:". | Control characters become a space on load and rename; code spans are fenced with one more backtick than the longest run (item names in the lists too). | bridge: `test_runbook_rename_line_shows_a_name_with_backticks_exactly` (4), `test_control_characters_in_folder_names_become_one_space` |
| CR5 | `d.uids.includes` per row while dragging (rows × dragged). | `d.uidSet` (a Set). | existing `test_drag_several_ticked_rows_moves_them_all` (3 rows dimmed) |
| CR6 | `_STATE["blobs"]` kept a second full copy of the export. | The zip is kept; `export_folder_zip` copies members out of it. | bridge: `test_folder_zip_is_read_from_the_kept_zip_not_a_second_copy` |
| CR7 | The UI picked "New folder N" and retried `move_items` up to 10,000 times. | `bridge.default_folder_name()` / `move_to_new_folder()`, by the bridge's casefold rule. | bridge: `test_new_folder_takes_the_first_free_default_name_by_the_bridges_rule` |
| CR8 | `isUnorganized` was a name regex + key regex + a JS "renamed" set. | Bridge flag `unorganized` per group / layout entry, by origin; cleared by a rename, set again by renaming back. | bridge: `test_the_loose_items_are_flagged_by_where_they_came_from_not_by_name`, `test_renaming_the_loose_items_clears_the_flag_and_renaming_back_restores_it` |
| CR9 | Start over's count (renamed set + moved set) was never cleaned: a move back, a rename back, a merged-away folder all still counted. | `unexportedChanges()` compares with the map as loaded (`LOADED`): items not in their loaded folder, loaded folders with another name, edits. | `test_start_over_counts_changes_against_the_map_as_loaded`; existing Start over tests |
| CR10 | `fkEl` duplicated `refocus`'s lookup; `plural` barely used; `downloadFolder` built Python source; `DATA.totals.folders` "written, never read". | `refocus` uses `fkEl`; `plural` in the bulk dialog and its status; the folder number crosses as a global and the file name comes from `bridge.export_folder_zip_name`. `DATA.totals.folders` stays: the load JSON's totals carry it and tests and the fuzzer read it, so keeping it current is the honest option. | L1 test below (download path); existing tests |
| F1 | A click that leaves a folder or row name field was lost at normal click speed (≥20 ms press): the deferred render rebuilt the list between pointerdown and pointerup. | `deferRender()`: the render after leaving a field waits until the button comes up and runs after its click. The bridge rename itself still happens at once. | `test_a_click_that_leaves_a_name_field_lands` (folder / row name × 0, 20, 80, 150 ms), `test_a_rail_filter_or_collapse_click_that_leaves_a_folder_name_lands`; probes 1–3 |
| F2 | Rename to a taken name, then Export: the export ran with the old name, then the merge offer opened over the export screen and "Move them" changed a hidden edit screen. | Export and Start over flush the waiting render first; a merge offer then opens on the edit screen and nothing is exported. An offer is never shown off the edit screen. | `test_leaving_a_taken_name_by_clicking_export_offers_the_merge_first`, `test_leaving_a_new_folders_taken_name_by_clicking_export_offers_the_merge`; probe 4 |
| F3 | A row drag could start under the merge dialog (it opened between pointerdown and the 6 px move). | No drag starts while a dialog is open. (With F1 the offer no longer opens mid-press: the drag now finishes first and the offer follows.) | `test_a_dialog_that_opens_after_a_press_stops_the_drag`; probe 3 |
| F4 | Ctrl+A under Move to…, the merge dialog or Help changed the selection behind it. | Ctrl+A only with none of them in front. | `test_ctrl_a_does_nothing_behind_what_is_in_front[move-to, merge-offer, help]`; probes 4, 6 |
| F5 | More while Move to… was open opened its menu under the list. | More closes Move to… (and the popover) first. | `test_more_closes_an_open_move_to_list`; probe 8 |
| F6 | A real CalTopo folder named "Unorganized" was styled as the loose items. | The bridge flag (CR8). | `test_a_caltopo_folder_named_unorganized_is_an_ordinary_folder`; probe 5 |
| F7 | Enter / Esc in a row name dropped focus to the page. | Enter saves in place and Esc reverts in place; focus stays in the field. | `test_enter_and_escape_in_a_row_name_keep_focus_there[Enter, Escape]`; probe 6; the fuzzer now checks focus after Enter and Esc too |
| H1 | Cancel on a just-created folder's taken name left a folder called "New folder". | Cancel reopens the rail name with what was typed. Leaving it with that same name keeps "New folder" without asking again (the first fuzzer re-run found the re-offer loop: Cancel, reopen, leave, offer…). A header rename's Cancel is unchanged. | `test_cancel_on_a_new_folders_taken_name_reopens_its_name` |
| H2 | Names over 100 characters were cut silently; long names wrapped badly in the rail, header and export card. | Ellipsis plus a `title` with the whole name in all three; the count and "N items" never wrap. The 100-character `maxlength` stays; reaching it says "A folder name can be up to 100 characters." The export box's "Rename it to" step shows the name whole. | `test_long_folder_names_are_cut_with_an_ellipsis_and_titled` |
| H3 | Stale status: "A folder needs a name." outlived later successes; "Built N folders" after Back; the hidden "Getting ready…" status kept its text all session. | Any later edit, rename or move clears an error; Back clears the line; "Getting ready…" is emptied when hidden. | `test_stale_status_lines_are_cleared`, and the end of `test_an_empty_name_for_a_new_folder_keeps_its_box_open` |
| H4 | Emptying the filtered folder reset the view to All silently. | Kept (the folder is gone), and the status says why: "Moved 1 item to Paddling. “Mill Creek Canyon” is empty now, so it was removed." | `test_an_emptied_folder_disappears_with_its_filter` (updated) |
| H5 | (a) a renamed Unorganized loses its caption; (b) renaming another folder to "Unorganized" gives a plain merge prompt; (c) an empty name on create made "New folder" and closed the box. | (a) as designed (UI-32), and renaming back restores it (CR8). (b) kept: the loose items export as an onX folder called Unorganized, so "Move them into it" is what happens (UI-26: no extra explanation). (c) Enter on an empty new-folder name keeps the box open with the message; leaving it keeps the default. | (c) `test_an_empty_name_for_a_new_folder_keeps_its_box_open` |
| H6 | (Unreproduced) a drop landed on the folder below the target during rail auto-scroll with a search active. | The hit test runs at the pointerup's own position, not the last pointermove's; and with F1 no deferred render can rebuild the rail mid-drag any more. | `test_the_drop_target_is_where_the_button_comes_up` |
| L1 | With 100+ folders `100_` sorted before `11_`. | `NN_` is as wide as the folder count needs from 100 folders on; unchanged below (Bitterroots pin). Manifest entries name their `dir`. | bridge: `test_with_100_or_more_folders_the_number_is_three_digits`; e2e `test_with_100_or_more_folders_a_folder_zip_is_numbered_with_three_digits` |

Found while fixing (by the fuzzer re-run, and by the owner testing live):

| # | Finding | Fix | Test |
|---|---------|-----|------|
| R1 | (H1's own) Cancel on a new folder's taken name reopened the name box; leaving it unchanged re-offered the merge, and Cancel reopened it again: Export never ran. | Leaving it with the declined name keeps the folder's default name, no second offer. | `test_cancel_on_a_new_folders_taken_name_reopens_its_name` (extended) |
| R2 | (F1's own) The render that waits for a click can run after that click opened the icon popover; it replaced the row, and closing the popover then dropped focus to the page. | The popover finds its marker again by its focus key. | `test_a_popover_opened_by_the_click_that_left_a_name_returns_focus_to_its_marker` |
| R3 | (H2's own; owner, live) A new folder "Crew" showed "Cr…" in its table header. Every header lost its last 7px: the name button's `margin-left:-7px` makes its h2 7px narrower than the button, and the H2 change gave the button `max-width:100%`. | The button is sized by flex shrink (no max-width), so it is only cut when the header is really out of room. Screenshot `tests/output/r2-crew-header.png` (gitignored). | `test_a_short_folder_name_is_never_cut_in_its_header` (Dark Divide; "Crew" with 3 items named in the rail under the Lines filter; header renames to 1–5 characters; every loaded header: scrollWidth <= clientWidth) |

Two items from PR-C's "Open" list are closed by these: long names (H2) and the `applyLayout`
failure leaving UI and bridge apart (CR2).

### Automated
`BASE_URL=http://127.0.0.1:8790/ uv run pytest`: **1229 passed** (1179 + 50: 19 bridge tests,
31 e2e test cases).

### Fuzzer re-run
`tests/output/qa-fuzz/fuzz_ui.py` with no `--known` step-overs (round 1 stepped over
`click_lost_after_field`, `move_list_stale`, `drag_under_modal` and `dialog_over_export`), 250
actions a session, the invariants checked after every action and every export verified (screen,
Download all, every per-folder zip, 12 sampled on 200 folders). Harness changes: the `NN_`
width and the manifest's `dir` (L1); focus checked after Enter and Esc in a row name, not only
Tab (F7); `human_press` centres its target and skips a covered one (it could press a low rail
entry through the rail's sticky footer and report a lost click: 2 false positives in pass 1,
and very likely some of round 1's `click_lost_after_field` count too).

| Pass | Sessions (waves 1 + 2) | Result |
|------|------------------------|--------|
| 1 | 24 (12 + 12, 4 per map) | 19 clean; 3 × `export_did_not_finish` (R1), 2 × `click_lost_after_field` (harness, above) |
| 2 | 24, after R1 | 22 clean; 2 × `focus_lost_to_body` (R2) |
| 3 | 24, after R2 | **24 clean**: 6,024 actions, 6,048 invariant checks, 211 verified exports, 0 failures (5 harness timeouts, stepped over as in round 1) |
| 4 | 6 (one per map), after R3 | 6 clean |

Every failing session of passes 1 and 2 replays clean (`--replay`) after its fix. Maps:
Bitterroots, hostile (34 nasty names, 3 empty), twins (case / safe-name twins, a CalTopo
folder called "Unorganized", a 150-character name), big200 (200 folders), and the onX areas and
three-round-trips pairs. Records: `tests/output/qa-fuzz/runs/w{1,2}_seed0{4,5,6}*_r2*.json`,
logs `tests/output/qa-fuzz/r2/`, report `tests/output/qa-fuzz/REPORT.md` (all gitignored).

### Open
- H5 (b): renaming a folder to "Unorganized" keeps the plain merge wording (reason above).
- Leaving a folder name by pressing a control still saves the rename at once; only the redraw
  waits for the release. A press that becomes a drag therefore drags with the new name already
  in the bridge, and a taken name's offer appears after the drop (F3 note).
