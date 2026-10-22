# onX dialect fixtures (synthetic)

**These are not real onX exports.** No real onX export is in the repo yet (roadmap probe P2,
FIDELITY W6). They are hand-written to match the onX Web Map export code as decoded in
`docs/research/KML_GPX_INPUT_2026-10-22.md` (KG) §3.4 and §3.5, extending the KG §6 scratch
fixtures:

- `onx_dialect.gpx`: `creator="onXmaps backcountry web"`, the `wwww.onxmaps.com` namespace,
  `<desc>` key=value blocks (`name`, `notes`, `id`, `color`, `icon`/`style`/`weight`,
  `type`, `fill_color`), `onx:` extensions, a recorded `<trk>` with `<time>`, an
  `<rte>` with `<type>Line</type>` and an `<rte>` with `<type>Area</type>`. One waypoint
  carries a multi-line note with a URL containing `#` and `&` (including `&copy`, `&notes`
  and `&para`, which are HTML legacy entity names) as the Avalanche Bridge will write.
- `onx_dialect.kml`: mapbox tokml style: flat `<Placemark>`s, every property in
  `<ExtendedData><Data>`, no `<Style>`, no `<description>`, a polygon with a hole, and a
  two-part `MultiGeometry`.

`tests/test_onx_round_trip_fidelity.py` reads both, merges them, writes them with Cairn's
writers and re-reads the output, and asserts per-field agreement. Replace these with the
real files from probe P2 when they exist (roadmap Phase 4), and re-check that test.
