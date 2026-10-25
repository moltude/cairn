# `reimport-unmodified-kml`: onX's own KML export re-imported byte for byte

Run 2026-10-23 in onX Backcountry's web app. Steps, findings, sha256 of every file, the record
tables and the full-file diffs are in
[`docs/ONX_ROUND_TRIP.md`](../../../../docs/ONX_ROUND_TRIP.md#reimport-unmodified-kml).

Only this README is tracked. The raw files are gitignored and kept locally:

- `reimport-unmodified-kml.original.gpx`: the hand-written upload, in Cairn's GPX dialect.
- `reimport-unmodified-kml.export-1.{gpx,kml}`, `.export-2.…`, `.export-3.…`: onX's own exports, unmodified.
- `reimport-unmodified-kml.edited*.{gpx,kml}` / `.stripped.gpx`: the test variant, derived from an export by
  text replacement only.
- `reimport-unmodified-kml.reimported-export.{gpx,kml}`: onX's export of the copies the test created.
- `net/`: the page's import request and response (test 1 only) and `snap.*.json`. Each
  snapshot is a read-only dump of the web app's in-memory markup store, taken before and after
  the import: uuid, timestamps, notes, colour and geometry for this run's markups, plus a
  digest of every other markup in the account.
