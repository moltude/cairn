# onX round trip: markup identity (superseded)

This doc reported run id1 (2026-10-23, 13:58–14:10 UTC), which tested only the import that
creates a new folder. It has been replaced by **[`docs/ONX_ROUND_TRIP.md`](ONX_ROUND_TRIP.md)**,
which reruns the question from scratch on every import path the Web Map offers.

id1's findings are folded in there as
[`new-folder-gpx-with-ids`](ONX_ROUND_TRIP.md#new-folder-gpx-with-ids),
[`new-folder-kml-with-ids`](ONX_ROUND_TRIP.md#new-folder-kml-with-ids) and
[`new-folder-cairn-output`](ONX_ROUND_TRIP.md#new-folder-cairn-output). Its raw files are
still in `tests/fixtures/roundtrip/id1/` (gitignored, kept locally). Its 12 markups and 4
folders were deleted by the owner before the new run.

The conclusion stands and is now broader: an onX import always creates new markups and never
updates an existing one. That holds with or without a folder, for GPX or KML, with or without
onX's ids, for an unmodified re-import, and across repeated cycles.

The previous text of this doc is in git history (commit `8799cbf`).
