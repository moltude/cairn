# Synthetic CalTopo map: one map as GeoJSON, KML and GPX

`caltopo_synthetic.{json,kml,gpx}` are ONE invented map written three ways by
`scripts/generate_caltopo_synthetic.py` (deterministic; regenerate with
`uv run python scripts/generate_caltopo_synthetic.py`). The generator follows CalTopo's
three export dialects as far as real files show them. It covers what the real Dark Divide
export (`../dark_divide_100/`) lacks:

- built-in symbols with colours (`camping`, `circle-p`, `peak`, `danger`, `point`, `flag-1`,
  `hut`) and a `point` with no colour;
- line colours red, blue, black, CalTopo green `#00CD00`, magenta `#FF00FF` (onX Fuchsia) and
  a lower-case `#ff0000`; widths 1, 2, 3, 4 and 6; one dashed line;
- an area with a fill and a hole, and a two-part area (GeoJSON MultiPolygon);
- a nested folder (`Routes / Spur lines`);
- a waypoint and a line whose name or note contains `#`, `&`, `<`, `>`, a URL and blank lines.

`tests/test_caltopo_format_parity.py` loads all three through the web bridge and pins
exactly where KML and GPX differ from the GeoJSON, with the reason for each difference.

## What is verified, and where

Real CalTopo exports read on 2026-10-22:

- **Dark Divide 100.** The owner's export of one map as GeoJSON, KML and GPX.
- **Nine public CalTopo KMLs (2016 to 2026), on GitHub.**
  - `d-otto/jif_lapse_rate` `JIFLR.kml`
  - `smHooper/gnarnana` `gnarnana.kml`
  - `river-corridors-sfa/rc_sfa-fire-watch` `Retreat_Fire.kml`
  - `sfregosi-noaa/glider-CalCurCEAS` `CalCurCEAS_2024_DASBR_and_effort_thru_Sep26.kml`
  - `Velin-walk/MapMine` `ibu7voxr-Sursing.kml`
  - `jessekauppila/Weather_Web_App` `doc.kml`
  - `jaanga/terrain3` `DLRT_Disposable_Master_Plan_.kml`
  - `jaanga/terrain3` `Wildland_drill_2016.kml`
  - `Cyberes/geovault` `Test Items.kml` (re-saved by Google Earth)
- **60 public CalTopo GPX files** (`creator="CALTOPO"`), found with a GitHub code search.

**Verified (seen in real files):**

**KML**

- *Document.* The `<Document>` opens with `<name>CalTopo Export</name>` and
  `<description>Export from CalTopo</description>`. All 10 KML files have both.
- *Folders.*
  - There is one flat `<Folder>` per CalTopo folder.
  - Items in no folder go into folders CalTopo names after the type:
    - current exports: "Points", "LineStrings", "Polygons";
    - 2016 exports: "Markers", "Lines and Polygons".
  - A map with user folders AND unfoldered markers gets both (`JIFLR.kml`: four user folders
    plus "Points").
- *Placemarks.*
  - The style is an inline `<Style>`, with no `styleUrl`. The only exception is the file
    re-saved by Google Earth.
  - Child order varies.
  - The description is plain text with real newlines.
- *Marker icons.* The icon is a `<href>` of `http://caltopo.com/icon.png?cfg=...`. The `cfg`
  decodes to `<symbol>[,<RRGGBB>]#1.0`, for example:
  - `point#1.0`
  - `point,FF0000#1.0`
  - `flag-1,00CD00#1.0`
  - `circle-p,009090#1.0`
  - `c:target2,FF0000#1.0`
  - `null#1.0`
  - an external icon URL
  - a nested CalTopo href, left by a re-import

  The symbol equals GeoJSON's `marker-symbol`; this is checked on Dark Divide's custom icon.
- *Lines.*
  - `<LineStyle><color>` is `AABBGGRR`, sliced from GeoJSON's hex with the case kept
    (`#ff0000` becomes `FF0000ff`).
  - `<width>` is GeoJSON's `stroke-width` as a float.
- *Areas.*
  - An area is `<MultiGeometry><Point/><Polygon/></MultiGeometry>` with
    `<IconStyle><scale>0</scale>`. That's the current form; 2016 exports write a bare
    `<Polygon>`.
  - `<PolyStyle><color>` alpha `1A` is GeoJSON's `fill-opacity` 0.1.
- *Coordinates.* They're written as `lon,lat,alt`. Where GeoJSON has no elevation, the
  altitude is `0.0`, and integer metres are written as `392.0`.

**GPX**

- *File.* The file has `creator="CALTOPO"` and the `gpxx` namespace, with the
  `<metadata><name>` in CDATA.
- *Waypoints.* A `<wpt>` has `<name>` and `<desc>`, with the note verbatim and multi-line.
- *Tracks.*
  - A `<trk>` has `<name>`, `<desc>`, `<gpxx:TrackExtension><gpxx:DisplayColor>` and
    `<trkseg>`.
  - DisplayColor values seen: Red, Magenta and DarkBlue.
  - 26 of 96 tracks have no DisplayColor. In Dark Divide that's exactly the one line whose
    colour is the lower-case `#ff0000`.
- *Never seen.* No `<sym>` in any of the 61 files, and no waypoint colour. Garmin's
  `GpxExtensionsv3.xsd` defines DisplayColor only for tracks and routes.

**GeoJSON**

- *Line patterns.* Two `pattern` values have been seen: `solid` and `M0 -1 L0 1,,8,F`, a dashed
  line (Bitterroots).

**Not verified (inferred or invented here; check against the owner's styled re-export):**

**KML**

- *Escaping.* Escaping `&` and `<` in names and notes as `&amp;` / `&lt;` is standard XML;
  CalTopo could use CDATA instead. Either way the reader gets the same text.
- *Multi-part areas.* Writing a two-part area as one `<MultiGeometry>` holding the label
  `<Point>` and two `<Polygon>`s is invented: no multi-part CalTopo area has been seen.
- *Holes.* Writing an area's hole as an `<innerBoundaryIs>` is standard KML but unseen in a
  CalTopo export.
- *Nested folders.* A nested `<Folder>` is never written by CalTopo, whose folders are flat.
  The fixture models a KML re-saved elsewhere, and the GeoJSON side carries the reader's
  flattened name (`Routes / Spur lines`).

**GPX**

- *Colour names.* Writing a DisplayColor only for an exact upper-case match to Garmin's
  16 RGB values is a guess from Dark Divide's line 10, and the real exports show `DarkBlue`
  too, so CalTopo may map to the nearest colour instead. The RGB per name is GPSBabel's
  table (`garmin_tables.cc`); Garmin's schema gives names only.
- *Areas.* Leaving areas out of the GPX is a choice: no CalTopo GPX with an area has been
  seen, and CalTopo may write them as closed tracks.
- *Track elevation.* Writing `<ele>` only where the GeoJSON has an elevation is a
  simplification: CalTopo fills in elevation for every track point (Dark Divide's GPX has
  19,516 `<ele>`).

**GeoJSON**

- *Other line patterns.* CalTopo's GeoJSON `pattern` values for its dotted and arrow styles are
  unknown, so this fixture uses only the dashed one.
- *Folder properties.* The folder features' `visible` and the markers' `marker-size: 1` are
  copied from real exports. The fixture has no `-created-on` / `creator` fields, which Cairn
  ignores anyway.
