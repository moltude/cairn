# OnX Sorting Behavior

## Overview

This document describes observed sorting/ordering behavior in OnX Backcountry.

**Important:** all concrete examples in this document use only the two fixture files:

- `tests/fixtures/test_sort_order_waypoints.gpx`
- `tests/fixtures/test_sort_order_tracks.gpx`

## Terminology (for this doc)

OnX’s UI labels don’t perfectly match how I want to describe test phases. For clarity:

- **Import**: after selecting a file and clicking Import; the import UI shows **Complete** (upper-left). At this stage I can still add imported items to a new folder.
- **Post-import**: after closing the import window (from a user perspective, “the import is finished”).


## Test Cases (Fixtures)

This section describes the structure of each fixture GPX, and what each is designed to test.

### `tests/fixtures/test_sort_order_waypoints.gpx`

**GPX structure**

- **Root**: GPX 1.1 `<gpx>` with namespaces:
  - `xmlns="http://www.topografix.com/GPX/1/1"`
  - `xmlns:onx="https://wwww.onxmaps.com/"`
- **Metadata**: `<metadata><name>…</name><desc>…</desc></metadata>` describing the intent.
- **Waypoints only**:
  - 14 `<wpt>` elements
  - no `<trk>` and no `<rte>`
- Each waypoint includes:
  - `<name>` with intentionally mixed naming patterns (two `#0 …`, then `#01…#10 …`, then an unnumbered name, plus two “Dead fall/Deadfall” variants)
  - `<extensions>` with:
    - `<onx:icon>`: mostly `Location`, plus `Hazard` for the last two
    - `<onx:color>`: provided to demonstrate not relying on OnX defaults

**Intended XML waypoint order (ground truth)**

1. `#0 Finish Line`
2. `#0 Start Line`
3. `#01 Porcupine Mile 6.1`
4. `#02 Ibex Mile 19.4`
5. `#03 & #05 Cow Camp Mile 31.9 & 54.8`
6. `#04 Halfmoon Mile 43.4`
7. `#06 Sunlight Mile 63.3`
8. `#07 Crandall Mile 70.4`
9. `#08 Forest Lake Mile 78.3`
10. `#09 Honey Trail Mile 85.4`
11. `#10 Hunting Camp Mile 92.8`
12. `CONICAL PASS CUTOFF 12:45 AM`
13. `Dead fall`
14. `Deadfall`

### `tests/fixtures/test_sort_order_tracks.gpx`

**GPX structure**

- **Root**: GPX 1.1 `<gpx>` with namespaces:
  - `xmlns="http://www.topografix.com/GPX/1/1"`
  - `xmlns:onx="https://wwww.onxmaps.com/"`
- **Metadata**: `<metadata><name>…</name><desc>…</desc></metadata>` describing the intent.
- **Tracks only**:
  - 5 `<trk>` elements
  - no `<wpt>` and no `<rte>`
- Each track includes:
  - `<name>` (numbered 01–05)
  - `<desc>`
  - `<extensions><onx:color>…</onx:color></extensions>`
  - one `<trkseg>` containing **two** `<trkpt/>` points (minimal valid geometry)
  - intentionally **no timestamps** (to keep the test focused on ordering)

**Intended XML track order (ground truth)**

This may seem counter intuitive but part of this test is to determine if ordering within the GPX file itself has any impact on how the data is processed and stored in OnX.

1. `05 - Bottom (First in XML)`
2. `04 - Fourth`
3. `03 - Middle`
4. `02 - Second`
5. `01 - Top (Last in XML)`

## Observed Behavior

### Key finding: different views use different ordering

OnX shows the same dataset in multiple places (e.g. **My Content** list vs a **Folder** view), and ordering can differ between those surfaces even when they reference the same items. The only interface to test sorting is My Content so all behaviors are tested there. I enabled `Filter list as map moves` to restrict my testing to only the objects from the fixture GPX files.

### My Content list sorting vs Folder view ordering

#### Waypoints (fixture)

Fixture: `tests/fixtures/test_sort_order_waypoints.gpx`

- **A–Z and Z–A**: behave as expected. See screenshots:

   [A-Z]('docs/screenshots/fixture-waypoints-az-correct.png')

   [Z-A]('docs/screenshots/fixture-waypoints-za-correct.png')
- **New → Old**: I would have expected this to show the waypoints in the reverse order that they were processed by the import, essentially the import would process the elements in sequential order meaning the last one processed in the youngest. However, this is not the case as you can see in the
[new-old]('docs/screenshots/fixture-waypoint-new-old-incorrect.png') screenshot.

```xml
<metadata>
    <name>OnX Order Debug Test</name>
    <desc>Test file to verify OnX sorting behavior. Waypoints are numbered 01-10 in correct order, plus unnumbered entries and different icon types.</desc>
  </metadata>
  <!-- Waypoints are intentionally ordered: #0 entries first, then #01-#10 sequentially, then unnumbered, then hazard icons
  ....
  ....
  The last four items in the GPX file -->
  <wpt lat="45.600000" lon="-114.600000">
    <name>#10 Hunting Camp Mile 92.8</name>
    <desc>Tenth numbered waypoint</desc>
    <extensions>
      <onx:icon>Location</onx:icon>
      <onx:color>rgba(8,122,255,1)</onx:color>
    </extensions>
  </wpt>
  <wpt lat="45.610000" lon="-114.610000">
    <name>CONICAL PASS CUTOFF 12:45 AM</name>
    <desc>Unnumbered waypoint - should appear after numbered waypoints</desc>
    <extensions>
      <onx:icon>Location</onx:icon>
      <onx:color>rgba(8,122,255,1)</onx:color>
    </extensions>
  </wpt>
  <wpt lat="45.620000" lon="-114.620000">
    <name>Dead fall</name>
    <desc>Hazard waypoint with different icon - testing if OnX groups by icon type</desc>
    <extensions>
      <onx:icon>Hazard</onx:icon>
      <onx:color>rgba(255,51,0,1)</onx:color>
    </extensions>
  </wpt>
  <wpt lat="45.630000" lon="-114.630000">
    <name>Deadfall</name>
    <desc>Another hazard waypoint - should be grouped with other hazards if OnX sorts by icon</desc>
    <extensions>
      <onx:icon>Hazard</onx:icon>
      <onx:color>rgba(255,51,0,1)</onx:color>
    </extensions>
  </wpt>
  ````

- **Old → New**: behaves **alphabetically** which is what I would expect given the ordering of the file but the inconsistenty of New -> Old is still curious.

#### Tracks (fixture)

Fixture: `tests/fixtures/test_sort_order_tracks.gpx`

- **Folder view order** (as observed after import into the fixture folder). I have observed this ordering to be somewhat random. I have seen appear in multiple orders after import

| Test 1 |Test 2 | Test 3 |
|---------|----------|----------|
| 04 | 01  | -  |
| 02 | 02  | -  |
| 03 | 03  | -  |
| 01 | 05  | -  |
| 05 | 04  | -  |

- This folder order **cannot be reproduced** by changing the sort options in **My Content → Tracks**.
- **Old → New** in My Content shows `05 → 01` (matches the `<trk>` element order in the GPX file).
- **New → Old** in My Content also shows `05 → 01` (unexpected; not reversed).
- **A–Z / Z–A**: behave as expected.

### Evidence (fixture)

## Related Files

- `tests/fixtures/test_sort_order_waypoints.gpx`
- `tests/fixtures/test_sort_order_tracks.gpx`
- `cairn/core/writers.py` - GPX writer utilities and order verification helpers
- `cairn/commands/convert_cmd.py` - conversion flow that controls sorting before writing

## References

- [GPX 1.1 Specification](https://www.topografix.com/GPX/1/1/)
