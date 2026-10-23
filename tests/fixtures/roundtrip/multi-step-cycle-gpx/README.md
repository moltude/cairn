# `multi-step-cycle-gpx`: export → modify → import → export → modify → import → export

Run 2026-10-23, onX Backcountry Web Map. Steps, findings, sha256 of every file, the record
tables and the full-file diffs are in
[`docs/ONX_ROUND_TRIP.md`](../../../../docs/ONX_ROUND_TRIP.md#multi-step-cycle-gpx).

Only this README is tracked. The raw files are gitignored and kept locally:

- `multi-step-cycle-gpx.original.gpx`: the hand-written upload, in Cairn's GPX dialect.
- `multi-step-cycle-gpx.export-1.{gpx,kml}`, `.export-2.…`, `.export-3.…`: onX's own exports, unmodified.
- `multi-step-cycle-gpx.edited*.{gpx,kml}` / `.stripped.gpx`: the test variant, derived from an export by
  text replacement only.
- `multi-step-cycle-gpx.reimported-export.{gpx,kml}`: onX's export of the copies the test created.
- `net/`: the page's import request and response (test 1 only) and `snap.*.json`. Each
  snapshot is a read-only dump of the Web Map's in-memory markup store, taken before and after
  the import: uuid, timestamps, notes, colour and geometry for this run's markups, plus a
  digest of every other markup in the account.
