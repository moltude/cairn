# `limits-2026-10-25`: what onX's importer does with long names, long notes and empty names

Run 2026-10-25, 18:29–18:36 MDT, in onX Backcountry's web app, in the owner's account, at the owner's
request. Plan, results and conclusions: [`docs/testing/ONX_LIMITS_2026-10-25.md`](../../../../docs/testing/ONX_LIMITS_2026-10-25.md).

Only this README is tracked. The raw files are gitignored and kept locally:

| File | What |
|---|---|
| `names.input.json`, `empty.input.json` | the CalTopo-style GeoJSON the probes were built from |
| `names.upload.ZZTEST_limits_names_{Waypoints,Tracks,Areas}.gpx` | Cairn's export of them (`bridge.load_document` → `export_zip`), imported together |
| `empty.upload.ZZTEST_empty_name_{Waypoints,Tracks}.gpx` | the empty-`<name>` probe, imported together |
| `names-upload/instructions.txt`, `empty-upload/instructions.txt` | the instructions.txt each export carried |
| `probes.json` | every probe name and its code points / UTF-16 units / UTF-8 bytes |
| `wpts_after_names.response.json`, `tracks_after_names.response.json`, `shapes_after_names.response.json` | the page's own `GET /v1/markups/…` responses after the import, saved read only from DevTools |
