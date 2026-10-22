# Round r1 — 2026-10-22, real onX account

Harness: `scripts/onx_roundtrip.py` (see `docs/ONX_TESTING.md`). Results: `SUMMARY.md`;
per set: `<stage>/<set>/verify_report.md`. `onx_export/` holds onX's own GPX + KML export of
each test folder — the only non-regenerable files here.

## onX folders created (owner deletes; markups first, then the folder)

| Folder | Items |
|---|---|
| `ZZTEST · r1 · i1 · random · geojson` / `gpx` / `kml` | 6 each |
| `ZZTEST · r1 · i1 · dd100 · geojson` / `gpx` / `kml` | 21 each |
| `ZZTEST · r1 · i1 · edge · geojson` | 23 |
| `ZZTEST · r1 · probe · names` | 3 |
| `ZZTEST · r1 · i2 · random · geojson` / `gpx` / `kml` | 6 each |
| `ZZTEST · r1 · i2 · dd100 · geojson` / `gpx` / `kml` | 21 each |
| `ZZTEST · r1 · i2 · edge · geojson` | 23 |

211 markups in all (104 per stage + 3 probe). Markup names start with `[r1i1]` / `[r1i2]` (edge and probe also contain
`ZZTEST`): search All Content for `[r1` to find leftovers.

## Findings

- **i1 (CalTopo → Cairn → onX): 0 FAIL** in all 7 sets. Only known onX limits: line point
  thinning (15–25%, end points kept) and notes over 512 cut.
- **i2 (onX export → Cairn edits → onX): every edit survived** — rename, note append, waypoint
  icon + colour, line colour + solid↔dash + weight 4↔6, area colour. onX does not thin a line
  a second time.
- **The 14 i2 FAILs share one cause: onX's 512 note limit counts UTF-8 bytes, not characters.**
  The edit suffix `— edited r1i2` starts with an em dash (3 bytes); every note the harness
  fitted to exactly 512 characters (514 bytes) came back 510 characters (`— edited r1`).
  Cairn's long-note warning and the harness counted characters. Fixed after this round.
- **A 3,000-character note is cut to 512, not dropped** (waypoint and line, i1 edge). The
  earlier dropped 3,000+ note came from re-importing an onX export; cause unknown.
- **Names (probe):** onX imports and exports `# & ! @ $ % ^ * ' " ( ) < >` in names unchanged,
  so Cairn's stripping of `! @ # $ % ^ * &` only altered user data. Removed after this round.
- Harness hazard found and fixed in the operator script: an export that silently fails can let a
  stale download from `~/Downloads` be verified instead (an i2 KML from 13:58 produced a false
  "extra Route" FAIL); `scripts/onx_fetch_export.sh` now takes only downloads under 3 minutes old.
