# Testing imports in a real onX account

How to run Cairn → onX import tests in the owner's onX Backcountry account without leaving a
mess. Written after the 2026-10-22 round (97 test markups, cleaned up by hand).

## Rules

1. **Claude imports; the owner deletes.** Claude may drive onX in the owner's Chrome (Claude in
   Chrome, logged in by the owner) and import files with the owner's approval. Claude never
   deletes: permanent deletion is the owner's.
2. **Every test markup's name starts with `ZZTEST`** where the test file is synthetic, so leftovers
   are findable in All Content by name even after their folder is gone.
3. **Every test import gets a defined folder name, immediately.** onX always names the import
   folder `Import mm/dd/yy H:MM` (verified from onX's code and in every import), and no file
   name or metadata can change that. So right after each import, rename the new folder via
   **folder → "…" → Rename Folder** to:

   ```
   ZZTEST · <dataset> · <source format> · <CalTopo folder or probe>
   ```

   e.g. `ZZTEST · DD100 · geojson · Aid Stations`, `ZZTEST · probe · note-limit`.
   Rename before starting the next import so timestamp folders never pile up.
4. **Cleanup = delete each `ZZTEST · …` folder's markups first, then the folder.** onX keeps a
   folder's markups when the folder is deleted (verified 2026-10-22: 12 tracks survived).
5. **Record the account's All Content count before and after.** It must return to the baseline.

## What the 2026-10-22 round established

| Topic | Result |
|---|---|
| Re-import of an onX export | Always creates new markups with new uuids. Both GPX `<desc>` `id=` and KML `<Data name="id">` are ignored, even when they hold the uuids of live markups in the same account, and the originals are left untouched: unchanged API records, unchanged re-exports. This holds on every import path: with or without "new folder", added afterwards to the originals' own folder or another one, unmodified re-imports, content-identical copies with no id, a stale export after an in-onX edit (not reverted), and two full cycles. onX has no "import into an existing folder" (`docs/ONX_ROUND_TRIP.md`) |
| Waypoint icon / color | Kept (`onx:icon`, `onx:color` in GPX) |
| Track color / style (dash) / weight | Kept |
| Area color / fill | **Only** via GPX `<rte>` + `<type>Area</type>` + `onx:color` / `onx:fill_color`; KML area styles are ignored |
| Area holes | Not representable in onX |
| Multi-line notes | Kept |
| Name characters | Kept: `# & ! @ $ % ^ * ' " ( ) < >`, accents, em dash, emoji (r1 probe, r2 edge set) |
| Line thinning on re-import | None to speak of: a line onX already thinned loses at most 1 point when re-imported (r2) |
| Note length on import | onX keeps the first 512 UTF-8 **bytes** of an imported note, cut on a character boundary (r2: accented notes of 511/512 bytes arrive whole, 513 is cut to 512; a cut landing inside an `é` drops the partial character; r1: ASCII notes of 513-3000 chars were cut to 512, waypoints and lines alike). One earlier 3,000+ char note from an onX export was dropped for an unknown reason. Notes typed in onX can be longer; onX folder notes are capped at 512 |
| `<desc>` key=value blocks | Not parsed on import: shown verbatim as the note |
| Track with 2 `<trkseg>` | Joined into one line with a false connecting segment |
| Long lines | onX thins points by 15–25% |
| Folder naming | Always `Import <timestamp>`; rename afterwards |

Evidence: `tests/fixtures/roundtrip/r1/` and `r2/` (READMEs), `tests/fixtures/onx_real/`, `tests/fixtures/dark_divide_100/onx_roundtrip/`,
`tests/fixtures/caltopo-random/onx_roundtrip/`, `docs/research/ONX_REIMPORT_AND_SHARING_2026-10-22.md`.

## Round-trip harness

`scripts/onx_roundtrip.py` does every offline step of a CalTopo → Cairn → onX → (onX export)
→ Cairn edits → onX round trip; the browser steps (import, rename the import folder, export
the folder) are done in onX between its commands. Everything is deterministic and written
under `tests/fixtures/roundtrip/<run>/` (`--root` elsewhere). Datasets: `random`
(`caltopo-random/onx-test-random.{json,gpx,kml}`), `dd100`
(`dark_divide_100/caltopo/….{json,gpx,kml}`) and `edge`
(`edge_cases_onx/edge.json`, from `scripts/generate_edge_dataset.py`). A **set** is
`<dataset>-<fmt>`, fmt ∈ `geojson|gpx|kml`: 7 sets.

```bash
uv run python scripts/onx_roundtrip.py stage1  --run r1 [--set random-geojson ...]
uv run python scripts/onx_roundtrip.py verify  --run r1 --stage i1 --set random-geojson --onx <export.gpx> [<export.kml>]
uv run python scripts/onx_roundtrip.py stage2  --run r1 --set random-geojson --onx <export.gpx> [<export.kml>]
uv run python scripts/onx_roundtrip.py verify  --run r1 --stage i2 --set random-geojson --onx <export of the i2 import>
uv run python scripts/onx_roundtrip.py summary --run r1
```

1. **stage1** loads each set through `web/bridge.py` exactly as the web app does, renames every
   item to `[r1i1] <name>` (the iteration tag), exports, and writes the upload files **flat**
   into `r1/i1/<set>/` (`NN_<Folder>_{Waypoints,Tracks,Areas}.gpx`, `RUNBOOK.md`,
   `expected.json`). Import **all** of a set's GPX files as ONE import and rename the folder to
   the name printed: `ZZTEST · r1 · i1 · <dataset> · <fmt>`.
2. **verify** reads onX's export of that folder with Cairn's onX readers, matches items by
   (kind, name) — duplicates in coordinate order, leftovers by first point — and compares
   name, notes, icon, colour (spaces ignored), line style and weight, and point count / end
   points against `expected.json`. Writes `verify_report.json` and `verify_report.md` in the
   set's folder; exits 1 on any FAIL. Classes:
   - **PASS** — identical.
   - **KNOWN_ONX_LIMIT** — a note over 512 UTF-8 bytes cut to a prefix or dropped; a line or
     area with fewer points but the same end points (within 1e-5: onX thinning); an area whose
     source had holes (listed in `expected.json` `known_dropped_holes`).
   - **FAIL** — anything else, including an item missing from, or extra in, the export.
3. **stage2** loads the onX export (data out of onX: this is the round trip) and applies the
   edit plan through `bridge.apply_edits`, then writes `r1/i2/<set>/` the same way; rename that
   import to `ZZTEST · r1 · i2 · <set>`. The plan (indices by sorted untagged name, per kind):
   - every item: `[r1i1] X` → `[r1i2] X` (refused if any item lacks the `[r1i1]` tag); note +=
     `\n— edited r1i2` (no newline when the note is empty), truncating the original so the
     result is ≤ 512 UTF-8 bytes (`edits[].note_truncated_to_fit` in `expected.json`);
   - waypoints: icon cycles `Summit, Water Source, Camp, Trailhead, Parking, Hazard, Photo,
     Shelter, View, Lookout`, colour cycles onX's 10 waypoint colours (skipping the current
     value);
   - lines: style solid ↔ dash (dot → solid), weight 4.0 ↔ 6.0, colour cycles onX's 11 line
     colours;
   - areas: colour cycles the 11 line colours.
4. **summary** writes `r1/SUMMARY.md`: items, PASS, KNOWN_ONX_LIMIT and FAIL per stage and set.

Between commands, after exporting a test folder from onX as GPX and then KML,
`scripts/onx_fetch_export.sh <run> <stage> <set>` moves the two fresh downloads into the set's
`onx_export/` and runs verify. It refuses downloads older than 3 minutes (a stale download once
produced a false FAIL) and parks other fresh onX downloads in `tests/output/stale_downloads/`.

`expected.json` is Cairn's own upload files re-read by Cairn, so the writer's own changes
(HTML-cleaned CalTopo notes, colour quantizing) are already in it and verify
measures only what onX changed. `tests/test_onx_roundtrip_harness.py` runs the whole chain
offline with Cairn's output standing in for onX's export: every item must PASS at both stages.
Line style / weight edits (`apply_edits` `style`: solid|dash|dot, `weight`: 4.0|6.0, tracks
only) exist in the bridge for this harness; the web UI has no control for them yet.

Naming caveat: only the `edge` dataset's markups start with `ZZTEST`. `random` and `dd100`
markups carry the iteration tag only (`[r1i1] Hiker`), so after their folder is gone search
All Content for `[r1` (the run id) rather than `ZZTEST` (rule 2).
