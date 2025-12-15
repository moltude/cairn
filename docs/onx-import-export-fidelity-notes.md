## OnX import/export fidelity notes (Dark Divide 100)

This document captures what data is present in the Dark Divide sample files and what fidelity is lost (or normalized) when importing into OnX Backcountry and exporting back out.

### Source files referenced

**CalTopo exports (inputs)**
- `sample-maps/dark-divide-100/Dark_Divide_100_Miler.gpx`
- `sample-maps/dark-divide-100/Dark_Divide_100_Miler.kml`
- `sample-maps/dark-divide-100/dark_Divide_100.json` (CalTopo GeoJSON)

**OnX exports (after import)**
- `sample-maps/dark-divide-100/OnX-markups-12132025.kml` (KML export after importing the CalTopo KML)
- `/Users/scott/downloads/OnX-markups-12132025.gpx` (GPX export after importing the CalTopo GPX)

**Other observed OnX export variants (important nuance)**
- `sample-maps/dark-divide-100/OnX-export-dark-divide.gpx` (observed to export lines as routes)
- `sample-maps/dark-divide-100/OnX-export-dark-divide-gpx-to-gpx.gpx` (observed to include duplicated waypoints and both `<rte>` and `<trk>`)

---

## 1) What’s in each CalTopo export (baseline inventory)

### 1.1 CalTopo GPX (`Dark_Divide_100_Miler.gpx`)
- **9 waypoints** (`<wpt>`)
- **11 tracks** (`<trk>`)
- Trackpoints include **per-point elevation** (`<trkpt>…<ele>…</ele>`) and are grouped in `<trkseg>`.
- Contains Garmin GPX extensions on tracks:
  - `gpxx:TrackExtension` / `gpxx:DisplayColor`
- Has GPX metadata name: `Dark Divide 100 Miler`.

### 1.2 CalTopo KML (`Dark_Divide_100_Miler.kml`)
- **20 Placemarks** total:
  - **9 Point** Placemarks
  - **11 LineString** Placemarks
- Includes:
  - Folder structure (`Points`, `LineStrings`)
  - `<Style>` blocks (IconStyle for points, LineStyle for lines)
  - CalTopo icon URLs for points (`http://caltopo.com/icon.png?cfg=...`)
  - `<description>` on all 20 Placemarks
- LineString coordinates are mostly 2D with explicit zero altitudes (`...,0.0`) and are multiline.

### 1.3 CalTopo GeoJSON (`dark_Divide_100.json`)
- **20 GeoJSON Features**
  - **9** points (`class=Marker`, `geometry.type=Point`)
  - **11** lines (`class=Shape`, `geometry.type=LineString`)
- Contains CalTopo styling/metadata as structured fields (`stroke`, `stroke-width`, `marker-symbol`, timestamps, ids).
- No elevation in coordinates (2D).

**Baseline conclusion:** the three CalTopo files represent the same 20 logical features; the only meaningful data uniquely present in GPX is **trackpoint elevation**.

---

## 2) GPX → OnX → GPX: what changes (using `/Users/scott/downloads/OnX-markups-12132025.gpx`)

### 2.1 Structure-level parity
- Exported OnX GPX contains:
  - **9 `<wpt>`**
  - **11 `<trk>`**
  - **0 `<rte>`**

So this export matches the desired “20 elements” expectation.

### 2.2 File header / metadata
- **Creator changes**
  - CalTopo: `creator="CALTOPO"`
  - OnX: `creator="OnXmaps backcountry web"`
- **Metadata is dropped/emptied**
  - CalTopo includes `<metadata><name>…</name></metadata>`
  - OnX export emits `<metadata/>`

**Loss:** GPX document-level name/metadata is not reliably preserved.

### 2.3 Waypoints (9) — notes preserved but normalized
- CalTopo waypoint `<desc>` is just the raw multiline text.
- OnX rewrites `<desc>` into a key/value block:
  - `name=...`
  - `notes=...` (this contains the original multiline description)
  - `id=<uuid>`
  - `color=rgba(...)`
  - `icon=Location`
- OnX also adds explicit waypoint extensions:
  - `<OnX:color>rgba(8,122,255,1)</OnX:color>`
  - `<OnX:icon>Location</OnX:icon>`

**Key point:** waypoint content (name + notes) survives, but the export format becomes “OnX canonical”. If you don’t set icon/color in OnX, it will export defaults (`Location`, default blue).

### 2.4 Tracks (11) — elevation kept, but time/extensions change
- Trackpoints still include `<ele>` (elevation preserved).
- OnX adds `<time>` elements to trackpoints (often the same timestamp repeated across many points).
- CalTopo’s Garmin extension `gpxx:TrackExtension/gpxx:DisplayColor` does not appear in the OnX export.
- OnX adds track extensions such as:
  - `<OnX:weight>4.0</OnX:weight>`
- Lat/lon and elevation formatting are normalized:
  - fewer coordinate decimals
  - elevations may drop trailing `.0`

**Loss:** CalTopo’s track display color extension (`gpxx:DisplayColor`) does not roundtrip.

---

## 3) KML → OnX → KML: what changes (using `OnX-markups-12132025.kml`)

### 3.1 Structure-level parity
- Both KML files contain:
  - **20 `<Placemark>`**
  - **9 `<Point>`**
  - **11 `<LineString>`**

So geometry items are preserved 1:1.

### 3.2 Foldering and styling are stripped
- CalTopo KML has 2 folders (`Points`, `LineStrings`).
- OnX-exported KML has **no `<Folder>`** elements (flattened).

- CalTopo KML uses `<Style>`, `<IconStyle>`, `<LineStyle>` and CalTopo icon URLs.
- OnX-exported KML contains **no** `<Style>` / `<IconStyle>` / `<LineStyle>` / `<PolyStyle>` and **no** CalTopo icon URLs.

**Loss:** all organization and styling is removed.

### 3.3 Notes move from `<description>` to `<ExtendedData>`
- CalTopo KML uses `<description>` on all 20 Placemarks.
- OnX-exported KML contains **no `<description>`**.
- Instead, OnX stores metadata in `<ExtendedData>`:
  - `Data name="notes"` contains the CalTopo description text
  - additional fields like `id`, and for points `icon` + `color`

**Change:** notes are present but not in `<description>` anymore.

### 3.4 Coordinate formatting is normalized
- CalTopo Point coordinates include `lon,lat,0`.
- OnX Point coordinates export as `lon,lat` (no explicit altitude).
- CalTopo LineString coordinates are multiline.
- OnX LineString coordinates export as a single space-separated list with `lon,lat,0` triplets and rounded precision.

---

## 4) Important nuance: OnX GPX export modes are inconsistent

In addition to the clean 20-element GPX export above, other OnX-exported GPX files in `sample-maps/dark-divide-100/` demonstrate that OnX may export the same logical lines differently depending on export path/settings:

- `OnX-export-dark-divide.gpx` was observed to export the 11 lines as **routes** (`<rte>`) with **no elevation** (`<rtept .../>` only; no `<ele>`).
- `OnX-export-dark-divide-gpx-to-gpx.gpx` was observed to contain duplicated waypoints and both `<rte>` and `<trk>` content.

**Practical takeaway:** if you care about predictable roundtrips, test against the exact export method you intend to use, and prefer the GPX structures OnX itself emits for that workflow.

---

## 5) Recommendations for Cairn (based on observed fidelity)

### 5.1 Don’t depend on KML for anything but geometry
- OnX KML export strips:
  - folders
  - styles/icons/line widths
  - `<description>` (notes are moved to `ExtendedData`)

So: KML is not a reliable carrier for user notes, icons, or styling.

### 5.2 Prefer GPX + OnX namespace extensions for waypoint fidelity
To maximize waypoint fidelity in OnX, generate GPX waypoints with:
- `<desc>` containing user notes
- `<extensions>` containing:
  - `<OnX:icon>…</OnX:icon>`
  - `<OnX:color>…</OnX:color>`

This matches OnX’s own canonical export structure.

### 5.3 For lines, choose output based on your intended OnX export behavior
- If you want the behavior seen in `/Users/scott/downloads/OnX-markups-12132025.gpx`:
  - keep **tracks** (`<trk>`) and include `<ele>` if available
  - optionally include `<OnX:weight>` for consistent line weight
- If your OnX export workflow converts to **routes** (`<rte>`) and drops elevation:
  - consider generating routes directly (or accept that elevation won’t roundtrip)
  - keep a separate “archive” GPX with `<trkpt><ele>` if elevation matters outside OnX.

### 5.4 Expect OnX to normalize formatting
OnX commonly:
- empties GPX `<metadata>`
- rewrites waypoint desc into `name=.../notes=.../id=.../color=.../icon=...`
- rounds coordinate precision
- injects trackpoint `<time>`

Design outputs so that the *semantic content* survives rather than expecting a byte-for-byte stable export.
