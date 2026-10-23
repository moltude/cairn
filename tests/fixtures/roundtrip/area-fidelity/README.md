# `area-fidelity`: what onX keeps of an area's line colour, fill, style and weight

Run 2026-10-23, onX Backcountry Web Map, in the owner's account. Findings, tables and the
list of everything created are in
[`docs/ONX_ROUND_TRIP.md`](../../../../docs/ONX_ROUND_TRIP.md#area-fidelity).

Only this README is tracked. The raw files are gitignored and kept locally (sha-256 prefixes
in the doc):

- `palette.upload.gpx`: 12 areas made by Cairn's export path (`bridge.load_files` →
  `export_zip`) from a CalTopo-style GeoJSON, all red line, CalTopo fill red at 0.1.
- `palette.export.{gpx,kml}`: onX's export after areas 01–11 were set in onX to every Area
  Color swatch, a different Line Color each, and every style and weight.
- `palette-reimport.upload.gpx`: `palette.export.gpx`, byte for byte.
- `fill-encoding.upload.gpx`: areas 01–08 of `palette.upload.gpx`, renamed, with the
  `<onx:fill_color>` line replaced by text replacement only (eight encodings, listed in the doc).
- `stage-*.upload.gpx` / `stage-*.export.{gpx,kml}`: the round-trip set (see the doc).
- `*.import-response.json`, `*.shapes-after-import.json`, `palette.edit-01.*.json`: response
  bodies of the page's own `POST /v1/markups/import`, `GET /v1/markups/shapes` and one
  `PUT /v1/markups/shapes/{uuid}` (an in-onX edit), saved read-only from DevTools.
