# `area-fidelity`: what onX keeps of an area's line colour, fill, style and weight

Run 2026-10-23, 16:29–17:00 UTC, onX Backcountry Web Map, in the owner's account. Findings,
the per-area tables and the list of everything created are in
[`docs/ONX_ROUND_TRIP.md`](../../../../docs/ONX_ROUND_TRIP.md#area-fidelity).

Only this README is tracked. The raw files are gitignored and kept locally:

| File | sha-256 (first 16) | What |
|---|---|---|
| `palette.upload.gpx` | `fdacdeb589d47832` | 12 areas from Cairn's export path (`bridge.load_files` → `export_zip`) |
| `palette.export.gpx` / `.kml` | `a4081e3ad86a0170` / `eb1d6c6c1217a1ef` | onX's export after every swatch, line colour, style and weight was set in onX |
| `palette-reimport.upload.gpx` | `a4081e3ad86a0170` | `palette.export.gpx`, byte for byte |
| `fill-encoding.upload.gpx` | `f38a53c38e5692ab` | areas 01–08 of `palette.upload.gpx`, renamed, `<onx:fill_color>` replaced by text (eight encodings) |
| `sent.input.*` | — | Cairn's inputs: the owner's two onX area exports moved by text, and a CalTopo-style GeoJSON |
| `sent.ZZTEST_*_Areas.gpx` | `64a2cbfee6725df7`, `a15ec9c795513f47`, `95f27f46c3201e59` | the three files Cairn wrote and onX imported |
| `sent.export.gpx` / `.kml` | `5151ebcfc30c7618` / `9a014feec6467f80` | onX's export of them |
| `modified.upload.gpx` | `b1a5dc4c9b1b2aeb` | `sent.export.{gpx,kml}` through Cairn with 6 areas restyled |
| `modified.export.gpx` / `.kml` | `b7f18d2b1f9967a4` / `9875928d90aef2d8` | onX's export of them |
| `*.edits.json`, `*.manifest.json`, `*.compare.json`, `created.json` | — | the `apply_edits` payloads, what was sent per area, the per-area comparison, and every created markup |
| `*.import-response*.json`, `*.shapes-after-import.json`, `palette.edit-01.*.json` | — | bodies of the page's own `POST /v1/markups/import`, `GET /v1/markups/shapes` and one in-onX `PUT /v1/markups/shapes/{uuid}`, saved read-only from DevTools |
