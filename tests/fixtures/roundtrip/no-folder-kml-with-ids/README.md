# `no-folder-kml-with-ids`: Edited onX KML, ids kept, imported without a folder

Run 2026-10-23, onX Backcountry Web Map. Steps, findings, sha256 of every file, the record
tables and the full-file diffs are in
[`docs/ONX_ROUND_TRIP.md`](../../../../docs/ONX_ROUND_TRIP.md#no-folder-kml-with-ids).

Only this README is tracked. The raw files are gitignored and kept locally:

- `no-folder-kml-with-ids.original.gpx`: the hand-written upload, in Cairn's GPX dialect.
- `no-folder-kml-with-ids.export-1.{gpx,kml}`, `.export-2.…`, `.export-3.…`: onX's own exports, unmodified.
- `no-folder-kml-with-ids.edited*.{gpx,kml}` / `.stripped.gpx`: the test variant, derived from an export by
  text replacement only.
- `no-folder-kml-with-ids.reimported-export.{gpx,kml}`: onX's export of the copies the test created.
- `net/`: the page's import request and response (test 1 only) and `snap.*.json`. Each
  snapshot is a read-only dump of the Web Map's in-memory markup store, taken before and after
  the import: uuid, timestamps, notes, colour and geometry for this run's markups, plus a
  digest of every other markup in the account.
