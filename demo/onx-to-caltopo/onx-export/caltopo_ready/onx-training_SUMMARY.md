## Cairn shape dedup summary

This file explains why some shapes were removed from the primary CalTopo import file.
Nothing is deleted permanently: every dropped feature is preserved in the secondary GeoJSON.

### Inputs
- **GPX**: `/Users/scott/_code/carin/demo/onx-to-caltopo/onx-export/onx-training.gpx`
- **KML**: `/Users/scott/_code/carin/demo/onx-to-caltopo/onx-export/onx-training.kml`

### Outputs
- **Primary (deduped)**: `/Users/scott/_code/carin/demo/onx-to-caltopo/onx-export/caltopo_ready/onx-training.json`
- **Secondary (dropped duplicates)**: `/Users/scott/_code/carin/demo/onx-to-caltopo/onx-export/caltopo_ready/onx-training_dropped_shapes.json`

### Dedup policy
- **Polygon preference**: when the same OnX id exists as both a route/track (GPX) and a polygon (KML), we keep the polygon and drop the line to avoid CalTopo id collisions.
- **Shape dedup default**: enabled (can be disabled via `--no-dedupe-shapes`).
- **Fuzzy match definition**:
  - **Polygons**: round coordinates to 6 decimals; ignore ring start index; ignore ring direction.
  - **Lines**: round coordinates to 6 decimals; treat reversed line as equivalent.

### Dedup results
- **Waypoint dedup dropped**: 0
- **Shape dedup groups**: 0
- **Shape dedup dropped features**: 0

### Per-group decisions

_No shape duplicates were detected under the fuzzy-match policy._
