# OnX Backcountry GPX/KML Import)

This document is written to summarize reproducible issues I've encountered when importing/exporting GPX/KML into onX Backcountry, especially around **sorting**.

For deeper, raw notes and sample artifacts, see:
- [`docs/onx-sorting-behavior.md`](onx-sorting-behavior.md)
- [`docs/onx-import-export-fidelity-notes.md`](onx-import-export-fidelity-notes.md)
- [`docs/onx-waypoint-colors-definitive.md`](onx-waypoint-colors-definitive.md)
- [`docs/onx-color-behavior.md`](onx-color-behavior.md)

---

## 1) Summary of key issues

### 1.1 Waypoint ordering in UI
- **During the first step of the  flow**, after a user as selected the file and OnX has rendered those objects on the map. The UI shows waypoints  in the same order they appear in the GPX file.
- **After import completes, the user has pressed `Save`**, when viewing a folder in the UI, the waypoint order becomes **unpredictable**:
  - Waypoints appeared to be mostly grouped by icon type.
  - Ordering is not alphabetical nor  numeric, although there are circumstances where it is within a group. See example image.
  - Ordering  can change after removing/re-adding items.
- **Exported GPX order generally matches the original import order** for unmodified waypoints, which suggests:
  - the original ordering is stored, but
  - UI order is computed from internal criteria.

### 1.2 Track ordering is predictable, but “reverse alphabetical”
- Tracks appear to sort **reverse alphabetically (Z→A)** in UI.
- This is predictable but opposite of what most users expect.

### 1.3 Waypoint colors are a fixed 10-color palette
- Waypoints support **10 specific RGBA values** (see definitive list in [`docs/onx-waypoint-colors-definitive.md`](onx-waypoint-colors-definitive.md)).
- Track colors use a **different palette** than waypoint colors.
- If an imported waypoint uses a non-supported color, OnX may ignore/normalize it.

---

## 2) Reproduction steps (fast, deterministic)

### 2.1 Sorting behavior (waypoints + tracks)
1. Import these GPX files into onX Backcountry Web:
   - Waypoints: `tests/fixtures/test_onx_order_debug.gpx`
   - Tracks: `tests/fixtures/test_sort_order.gpx`
2. Observe ordering:
   - During pre-import/import confirmation (order is correct)
   - After import completes, in folder UI
3. Remove some waypoints from the folder and add them back.
   - Observe that waypoint ordering changes in a way that is not predictable.

Expected observations:
- Waypoints grouped by icon type; order inside group shifts.
- Tracks appear in reverse alphabetical order.

### 2.2 KML fidelity loss
1. Import CalTopo KML:
   - `sample-maps/dark-divide-100/Dark_Divide_100_Miler.kml`
2. Export KML from onX.
3. Compare:
   - CalTopo KML has folders + styles + `<description>`.
   - onX-exported KML has flattened structure, no styles, notes in `<ExtendedData>`.

### 2.3 GPX export variance (tracks vs routes)
1. Import:
   - `sample-maps/dark-divide-100/Dark_Divide_100_Miler.gpx`
2. Export GPX from onX using the export flows you support.
3. Compare exported structure:
   - do you get `<trk>` only, or `<rte>` only, or both?
   - is `<ele>` preserved?

Artifacts showing the variance:
- `sample-maps/dark-divide-100/onx-export-dark-divide.gpx`
- `sample-maps/dark-divide-100/onx-export-dark-divide-gpx-to-gpx.gpx`

---

## 3) Impact on users and tooling

### 3.1 Users can’t rely on numbering/name-based ordering for waypoints in folders
Even if a GPX is imported in a perfect order, the folder UI can re-order it. This breaks:
- race/aid-station sequencing
- “section 01..N” waypoint lists
- any workflow relying on deterministic lists

### 3.2 KML is not viable for style-preserving interchange
If users care about styling or organization, the KML round-trip strips too much to be considered a faithful interchange format.

### 3.3 GPX export variance complicates external workflows
If onX exports the same logical linework sometimes as routes (and drops elevation), it becomes difficult to:
- maintain elevation-aware analytics outside onX
- verify that an import/export cycle preserved data
- build reliable converters targeting onX’s expected structures

---

## 4) Concrete requests / questions for onX

### 4.1 Waypoint ordering
- Is there a supported way to request folder UI ordering by:
  - original import order
  - name (ascending)
  - name (natural sort)
  - created_at
  - explicit sort key in GPX extensions
?

### 4.2 Stable export structure
- Can onX document when it exports lines as `<trk>` vs `<rte>`?
- If both are supported, can the export flow let the user choose “tracks with elevation” vs “routes”?

### 4.3 Waypoint colors
- Can onX document the official 10 waypoint RGBA values (and whether non-matching RGBA values are accepted/quantized/ignored)?

---

## 5) Notes on Cairn’s current approach (for context)

Cairn aims to generate GPX files that match onX’s observed GPX extensions:
- `<onx:icon>` and `<onx:color>` for waypoints
- `<onx:color>`, `<onx:style>`, `<onx:weight>` for tracks

However, we strive  preserve ordering and styling **up to onX’s import/UI behaviors** described above.
