# Folders release: testing notes

One section per PR of the three-part release.

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

### For the owner to check

- [ ] Download all, then import one folder's files in onX's Web Map following the three steps.
- [ ] Download this folder for one folder; the zip holds just that folder.
- [ ] Back returns to the map with edits intact; Start over asks first.
