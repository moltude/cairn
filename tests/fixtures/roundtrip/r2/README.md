# Round r2 — 2026-10-22, real onX account

Re-run of round r1 (see `../r1/README.md`) after #23: onX's note limit is counted in UTF-8
bytes, and names pass through unchanged (ENG-06). The `edge` dataset gained UTF-8 note probes
and a non-ASCII name (28 markups). Results: `SUMMARY.md`; per set:
`<stage>/<set>/verify_report.md`.

**0 FAIL in all 14 stage/set runs.** Every remaining KNOWN_ONX_LIMIT is line thinning or a
note longer than 512 bytes, cut.

## What r2 established

- **The fixes hold in onX.** i2 edge: 28/28 PASS (r1: 11 FAIL). Every note fitted to 512
  bytes survived with its em dash.
- **onX's limit is 512 UTF-8 bytes, confirmed directly:** accented/em-dash notes of 511 and 512
  bytes (~450 characters) arrive whole; 513 bytes is cut to 512.
- **onX cuts on a character boundary:** a note whose byte 512 falls inside an `é` arrives as 511
  bytes, without the partial character.
- **Names keep their characters:** `ZZTEST Peak #3`, `Rock & Roll`, `Wow!`, and
  `ZZTEST Névé Café — Lac des Îles 🏔` round-trip unchanged through both stages; Dark Divide
  track names keep `#1` / `#2`.
- onX thins a line on its first import only (i2: at most 1 point of 8,089 dropped).

## onX folders created (owner deletes; markups first, then the folder)

| Folder | Items |
|---|---|
| `ZZTEST · r2 · i1 · random · geojson` / `gpx` / `kml` | 6 each |
| `ZZTEST · r2 · i1 · dd100 · geojson` / `gpx` / `kml` | 21 each |
| `ZZTEST · r2 · i1 · edge · geojson` | 28 |
| `ZZTEST · r2 · i2 · random · geojson` / `gpx` / `kml` | 6 each |
| `ZZTEST · r2 · i2 · dd100 · geojson` / `gpx` / `kml` | 21 each |
| `ZZTEST · r2 · i2 · edge · geojson` | 28 |
| `ZZTEST · r2 · aborted import (empty)` | 0 — the browser extension disconnected mid-import; All Content confirmed no markups were created |

218 markups in all (109 per stage). Search All Content for `[r2` to find leftovers.

## Where the data is

Only the findings are tracked (this README, `SUMMARY.md`, each set's `verify_report.md`). The upload files, onX's own GPX/KML exports and the per-set JSON are gitignored and kept locally; they are also in git history at `4582dfa` (PR #24).
