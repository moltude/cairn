# Run id1, 2026-10-23: onX markup identity

Findings are folded into `docs/ONX_ROUND_TRIP.md` as the tests `new-folder-gpx-with-ids`,
`new-folder-kml-with-ids` and `new-folder-cairn-output`. The original id1 write-up, with the
stage table, sha256 values, excerpts and diffs, is in git history at commit `8799cbf`
(`docs/ONX_ROUND_TRIP_IDENTITY.md`).

Only this README is tracked. The raw files are gitignored and kept locally:

- `a_originals/`: upload and onX exports.
- `b_v1/` and `b_v2/`: Cairn's copy and the same-id variants.
- `d_reexport/`: onX re-exports.
- `net_id1/`: the id1 records from the Web Map's API traffic.
