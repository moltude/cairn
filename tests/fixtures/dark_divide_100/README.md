# Dark Divide 100: a real CalTopo map in three formats

`caltopo/` holds one real CalTopo map (the 2027 Dark Divide 100 Mile Endurance Run course),
exported by the owner on 2026-10-22 as GeoJSON (`.json`), GPX and KML. Unedited.

It is the project's most complex real source: 3 folders, 9 aid-station waypoints with a custom
CalTopo icon, 12 course lines with thousands of points each, and **21 multi-line notes**
(mileage, cutoffs, `#` in text). No areas.

Since roadmap Phase 7 the KML reads with its 3 folders and red lines, like the GeoJSON, and the
GPX reads its line colours from Garmin's `DisplayColor`. `PARITY.md` lists the differences that
remain, and why each one exists.

`cairn_output/from_<format>/` is what Cairn produces for each input with no edits: the exact
unzipped contents of the download, ready to import into onX one numbered folder at a time.
`PARITY.md` compares source, review screen, export and the three formats.

Regenerate both (deterministic):

    uv run python scripts/dark_divide_parity.py

`tests/test_dark_divide_parity.py` fails if the committed outputs or report drift from what the
current code produces, and pins the parity invariants.
