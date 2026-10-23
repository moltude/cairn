# `originals-folder-gpx-with-ids`: Edited GPX copy added to the originals' own folder

Run 2026-10-23, onX Backcountry Web Map. Steps, findings, sha256 of every file, the record
tables and the full-file diffs are in
[`docs/ONX_ROUND_TRIP.md`](../../../../docs/ONX_ROUND_TRIP.md#originals-folder-gpx-with-ids).

Only this README is tracked. The raw files are gitignored and kept locally:

- `originals-folder-gpx-with-ids.original.gpx`: the hand-written upload, in Cairn's GPX dialect.
- `originals-folder-gpx-with-ids.export-1.{gpx,kml}`, `.export-2.…`, `.export-3.…`: onX's own exports, unmodified.
- `originals-folder-gpx-with-ids.edited*.{gpx,kml}` / `.stripped.gpx`: the test variant, derived from an export by
  text replacement only.
- `originals-folder-gpx-with-ids.reimported-export.{gpx,kml}`: onX's export of the copies the test created.
- `net/`: the page's import request and response (test 1 only) and `snap.*.json`. Each
  snapshot is a read-only dump of the Web Map's in-memory markup store, taken before and after
  the import: uuid, timestamps, notes, colour and geometry for this run's markups, plus a
  digest of every other markup in the account.
