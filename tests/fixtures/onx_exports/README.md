# Real onX exports

`three-round-trips.gpx` and `three-round-trips.kml` are unmodified onX web app exports of one waypoint,
one line and one area after three onX GPX round trips. They come from the
`multi-step-cycle-gpx` test in `docs/ONX_ROUND_TRIP.md`, run on 2026-10-23, and contain only
`ZZTEST` test data.

- In the GPX, every `<desc>` nests the earlier exports' `name=` / `notes=` / `id=` blocks.
- In the KML, the `notes` field nests them one level less. The current onX uuid is in the
  `id` field.

`tests/test_onx_export_round_trip.py` uses these files to check two things: that Cairn reads the
innermost note and the markup's current id, and that no onX uuid reaches Cairn's output.

`areas-before-edit.gpx` / `.kml` and `areas-after-edit.gpx` / `.kml` are the owner's unmodified
web app exports (2026-10-23) of four areas the owner drew in onX as test data: `temp`,
`Area 10/23/26 10:09`, `Area 10/23/26 10:10` and `test 4`. Between the two exports the owner
changed `Area 10/23/26 10:10` from solid / 4.0 to dash / 6.0, and `test 4` from solid to dot and
from no fill (`rgba(0,0,0,0)`) to the purple fill. Together they cover every onX area property:
line colour, `style` solid / dash / dot, `weight` 2.0 / 4.0 / 6.0 and `fill_color` (three of
onX's area swatches plus none). The KML carries the same values only as `ExtendedData`; it has
no `<Style>`. `tests/test_area_fidelity.py` pins that each value survives load → export.
