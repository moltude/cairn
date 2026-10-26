# onX limits on import: names, folder names, notes (live run, 2026-10-25)

What onX does with a long name, a long folder name, a long note and an empty name when Cairn's
export is imported. It decides the warnings in UI-39 / tracker section 7.4 (L1, N1): Cairn warns
like it does for notes and never cuts.

**Already known before this run.** onX's editor stops typing at 255 characters for a waypoint, line,
track or area name, 50 for a folder name, 512 for a note, and refuses a blank name
(`docs/research/ONX_PUBLIC_DOCS_2026-10-25.md`, from onX's public web app code). On import, onX keeps
the first 512 UTF-8 bytes of a note (2026-10-22 r1, commit `a07f14a`). What onX's **importer** does
with names was unknown: it runs on onX's servers.

**Safety.** The owner asked for this run (2026-10-25) in their own signed-in onX account. Imports
only: nothing is deleted, nothing is shared, no setting changes, no passwords. Every probe markup and
folder is named `ZZTEST …`; the owner deletes them afterwards. The one edit beyond an import is
renaming a ZZTEST folder this run created, to test the 50-character folder cap.

**Payloads.** `tests/fixtures/roundtrip/limits-2026-10-25/` (gitignored, local; its README is
tracked). Written by Cairn's own export path (`bridge.load_document` → `export_zip`) at
`feat/bulk-rename` before the L1/N1 changes, so every name and note is in the file whole.

## Probes

Names are padded with `x` to the exact length. Measures: code points (cp), UTF-16 units (u16, what
onX's editor counts), UTF-8 bytes (b).

| probe | in the file | cp / u16 / b | if onX caps at 255 u16 | at 255 cp | at 255 bytes | no cap |
|---|---|---|---|---|---|---|
| `a255` waypoint | `ZZTEST a255 xxx…` | 255 / 255 / 255 | whole | whole | whole | whole |
| `a256` waypoint | `ZZTEST a256 xxx…` | 256 / 256 / 256 | cut to 255 | cut to 255 | cut to 255 | whole |
| `a300` waypoint | `ZZTEST a300 xxx…` | 300 / 300 / 300 | cut to 255 | cut to 255 | cut to 255 | whole |
| `e139` waypoint | `ZZTEST e139 ` + 127 × é | 139 / 139 / 266 | whole | whole | cut (255 bytes) | whole |
| `u256` waypoint | 254 ASCII + 🔥 | 255 / 256 / 258 | cut (emoji lost or split) | whole | cut | whole |
| line `a300` | `ZZTEST line a300 xxx…` | 300 | cut to 255 | cut | cut | whole |
| area `a300` | `ZZTEST area a300 xxx…` | 300 | cut to 255 | cut | cut | whole |
| note 512 | waypoint `ZZTEST note 512`, 512 × n | 512 bytes | — | — | kept whole (r1) | — |
| note 513 | waypoint `ZZTEST note 513`, 513 × n | 513 bytes | — | — | cut to 512 (r1) | — |
| empty name | waypoint and line with `<name></name>`, notes `ZZTEST empty-name …` | 0 | refused, renamed, or kept blank? | | | |
| folder 60 | rename the imported ZZTEST folder in onX to a 60-character name | 60 | — | — | — | onX's dialog stops at 50? |

A third outcome for any long name: the whole markup (or the whole file) is rejected. Record that too.

## Steps

1. onX Backcountry on a computer (`backcountry.onxmaps.com`), signed in as the owner.
2. Import `names.upload.ZZTEST_limits_names_{Waypoints,Tracks,Areas}.gpx` together (one import,
   "Import map data to a new folder").
3. Read back what onX stored from the page's own `GET /v1/markups/…` responses (DevTools network,
   read only), not from the edit field: an input's `maxlength` only limits typing, so a longer
   stored name would still sit whole in it.
4. Rename the new folder to a 60-character name (`ZZTEST folder sixty …`), read back the stored name.
5. Import `empty.upload.ZZTEST_empty_name_{Waypoints,Tracks}.gpx` (one import, a new folder). Read back.
6. Fill in the observed column below; update Cairn's warnings (tracker 7.4) from it.

## Observed (run 2026-10-25, 18:29–18:36 MDT, onX Backcountry on a computer)

The signed-in account was checked against the owner's email first (read only). Both imports reported
success ("9 Items Imported Successfully", "2 Items Imported Successfully"); no markup and no file was
rejected. Values below are what onX's server stored, read from the page's own
`GET /v1/markups/{waypoints,shapes}` responses and, for the track, from the folder page's text.

| probe | sent cp / b | stored cp / b | result |
|---|---|---|---|
| `a255` waypoint | 255 / 255 | 255 / 255 | whole |
| `a256` waypoint | 256 / 256 | 255 / 255 | cut to 255 |
| `a300` waypoint | 300 / 300 | 255 / 255 | cut to 255 |
| `e139` waypoint (accented) | 139 / 266 | **133 / 254** | cut by **bytes**, on a character boundary (one more é would be 256 bytes) |
| `u256` waypoint (254 ASCII + 🔥) | 255 / 258 | **254 / 254** | the emoji dropped whole; by bytes, not code points or UTF-16 units |
| line `a300` (onX lists it under Tracks) | 300 / 300 | 255 / 255 | cut to 255 |
| area `a300` | 300 / 300 | 255 / 255 | cut to 255 |
| note 512 | 512 bytes | 512 | whole |
| note 513 | 513 bytes | 512 | cut to 512 (r1 confirmed again) |
| empty `<name>` waypoint | "" | **"Imported waypoint markup 2026-10-26T00:34:59.125164Z"** | onX fills in a generated name |
| empty `<name>` track | "" | **"Imported track markup 2026-10-26T00:34:59.194855Z"** | the same |
| folder rename, typed | 60 characters typed | the field held 50 (`maxlength="50"`) | onX's dialog stops typing at 50; no message |

**Conclusions.**
1. **Names: onX's importer keeps the first 255 UTF-8 bytes**, cut on a character boundary, for
   waypoints, lines (tracks) and areas alike. The same rule as notes (512 bytes), so Cairn measures names
   the way it measures notes. onX's *editor* counts 255 characters instead, so a name typed in onX with
   accents can be longer than 255 bytes and is cut if it is ever exported and imported again.
2. **Folder names: 50 characters**, enforced only by the rename dialog (instructions.txt tells the user
   to type Cairn's name there).
3. **Notes: 512 UTF-8 bytes**, as measured on 2026-10-22.
4. **An empty name is never kept**: onX names the markup "Imported waypoint markup <timestamp>" (or
   track). Cairn requiring a name before export (tracker 7.4, N1) avoids that.

**Created in the owner's account** (to delete when convenient; nothing was deleted by this run):
folder **ZZTEST limits-2026-10-25 names** (7 waypoints, 1 track, 1 area) and folder **ZZTEST
limits-2026-10-25 empty name** (1 waypoint, 1 track). Both folders were renamed from onX's
"Import 10/25/26 18:29" / "18:34" so they are easy to find.

## Second run: names and the long note (2026-10-25, 20:43 MDT)

Payloads: `tests/fixtures/roundtrip/names-2026-10-25/` (gitignored; README tracked). One import of two files
into a new folder (renamed **ZZTEST names-2026-10-25**): Cairn's export of 8 waypoints with unusual names, and
`tests/fixtures/onx_real/onx_web_line_long_note.gpx` with its name changed to "ZZTEST long note route"
(its 3,166-character, 3,172-byte note untouched). "9 Items Imported Successfully".

| probe | sent | stored by onX |
|---|---|---|
| RTL | `ZZTEST rtl مجلد عربي` | identical |
| two identical names | `ZZTEST twin` × 2 | both imported, both identical |
| emoji only | `🏔️🔥` | identical |
| NBSP and ZWSP | `ZZTEST nbsp zwsp​name` | identical (both characters kept) |
| bidi override | `ZZTEST bidi a‮b` | identical |
| combining accent | `ZZTEST combining é` | identical (not normalised to é) |
| the long-note route, GPX alone | 3,172-byte note | imported as a **Line**; note cut to **512 bytes**, not dropped |

**Conclusions.** onX keeps unusual names exactly as written: no normalisation, no stripping of NBSP, ZWSP or
bidi controls, and duplicates are fine (the bulk-rename twins and Campsite cases are safe). The 3,000+
character note dropped on 2026-10-22 is cut, not dropped, when its GPX is imported alone, which points at the
KML of that pair (onX ignores KML ExtendedData) rather than at a size rule. onX stored the note with its own
`name=… / notes=…` lines, as the FAQ already says.

**Import Complete → "…" → Add to Folder** (tried once, into ZZTEST limits-2026-10-25 names): "Add 9 Items to
a Folder" lists every folder plus "Create New Folder"; choosing one says "9 item(s) added to folder." The items
are **added, not moved**: they are now in both the new import folder (9) and the chosen one (9 → 18). So a
fresh import can be put into an existing folder; the empty-handed "Import …" folder onX made stays behind.
Whether deleting that folder also deletes its markups was not tested (nothing is deleted in these runs).

**Created by the second run:** folder **ZZTEST names-2026-10-25** (8 waypoints, 1 line); the same 9 items are
also in **ZZTEST limits-2026-10-25 names**. Nothing was deleted.
