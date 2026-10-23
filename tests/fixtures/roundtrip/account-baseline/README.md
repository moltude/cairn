# `account-baseline`: account-wide state for the 2026-10-23 round-trip run

Supports [`docs/ONX_ROUND_TRIP.md`](../../../../docs/ONX_ROUND_TRIP.md#method). Only this README
is tracked. The raw files are gitignored and kept locally:

- `net/{waypoints,shapes,lines,collections,tracks_p0..p3}.json`: the Web Map's own page-load
  `GET /v1/markups/*` and `GET /v1/content-collections` responses at 14:35:18Z. There were 445
  waypoints, 188 tracks over 4 pages, 12 areas, 1 line and 14 folders. They hold the whole
  account, so they stay local.
- `net/snap.final.json`: the store snapshot at 15:16Z, after a fresh reload. There were 705
  markups and 27 folders, and the digest of the 648 non-test markups was unchanged.
