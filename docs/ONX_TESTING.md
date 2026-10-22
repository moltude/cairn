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
| Re-import of an onX export | Always creates new markups (ids ignored) |
| Waypoint icon / color | Kept (`onx:icon`, `onx:color` in GPX) |
| Track color / style (dash) / weight | Kept |
| Area color / fill | **Only** via GPX `<rte>` + `<type>Area</type>` + `onx:color` / `onx:fill_color`; KML area styles are ignored |
| Area holes | Not representable in onX |
| Multi-line notes | Kept |
| Note length on import | A 617-char note was cut to 512; a 3,000+ char note was dropped entirely. Notes typed in onX can be longer; onX folder notes are capped at 512 |
| `<desc>` key=value blocks | Not parsed on import: shown verbatim as the note |
| Track with 2 `<trkseg>` | Joined into one line with a false connecting segment |
| Long lines | onX thins points by 15–25% |
| Folder naming | Always `Import <timestamp>`; rename afterwards |

Evidence: `tests/fixtures/onx_real/`, `tests/fixtures/dark_divide_100/onx_roundtrip/`,
`tests/fixtures/caltopo-random/onx_roundtrip/`, `docs/research/ONX_REIMPORT_AND_SHARING_2026-10-22.md`.
