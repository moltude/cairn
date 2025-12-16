# Edge Case Test Results

Generated: 2025-12-16 12:39:45

## Summary

- Total Tests: 24
- Passed: 21
- Failed: 3
- Warnings: 0

## FAILED (3)

### CalTopo→OnX: empty

- **Description:** Empty GeoJSON
- **Input:** `empty.json`
- **Output:** `empty_onx_output`
- **Time:** 0.136s
- **Error:** Conversion failed: ╭────────────────────────────────╮
│    [1mCAIRN[0m v1.0.0                │
│    [3mThe CalTopo → OnX Bridge[0m    │
╰────────────────────────────────╯

[1m📂[0m Input file: empty.json
[2m   Siz

### Malformed: malformed_gpx

- **Description:** Malformed XML
- **Input:** `malformed.gpx`
- **Output:** `malformed_to_caltopo_geojson.json`
- **Time:** 0.134s
- **Error:** Conversion failed: [1m❌ Error reading GPX file:[0m
Invalid GPX file [1m([0mXML parse error[1m)[0m: mismatched tag: line [1m5[0m, column [1m6[0m
File: /Users/scott/_code/cairn/tests/fixtures/edge_cases/malforme

### Malformed: malformed_json

- **Description:** Malformed JSON
- **Input:** `malformed.json`
- **Output:** `malformed_onx_output`
- **Time:** 0.157s
- **Error:** Conversion failed: ╭────────────────────────────────╮
│    [1mCAIRN[0m v1.0.0                │
│    [3mThe CalTopo → OnX Bridge[0m    │
╰────────────────────────────────╯

[1m📂[0m Input file: malformed.json
[2m  

## PASSED (21)

### GPX→CalTopo: poles

- **Description:** Waypoints at North and South Poles
- **Input:** `poles.gpx`
- **Output:** `poles_to_caltopo_geojson.json`
- **Time:** 0.179s

### GPX→CalTopo: dateline

- **Description:** Waypoints at International Date Line
- **Input:** `dateline.gpx`
- **Output:** `dateline_to_caltopo_geojson.json`
- **Time:** 0.163s

### GPX→CalTopo: prime_meridian

- **Description:** Waypoint at Prime Meridian
- **Input:** `prime_meridian.gpx`
- **Output:** `prime_meridian_to_caltopo_geojson.json`
- **Time:** 0.185s

### GPX→CalTopo: equator

- **Description:** Waypoint at Equator
- **Input:** `equator.gpx`
- **Output:** `equator_to_caltopo_geojson.json`
- **Time:** 0.169s

### GPX→CalTopo: elevations

- **Description:** Extreme elevation values
- **Input:** `elevations.gpx`
- **Output:** `elevations_to_caltopo_geojson.json`
- **Time:** 0.173s

### GPX→CalTopo: unicode

- **Description:** Unicode characters and emoji
- **Input:** `unicode.gpx`
- **Output:** `unicode_to_caltopo_geojson.json`
- **Time:** 0.172s

### GPX→CalTopo: xml_chars

- **Description:** XML special characters
- **Input:** `xml_chars.gpx`
- **Output:** `xml_chars_to_caltopo_geojson.json`
- **Time:** 0.166s

### GPX→CalTopo: quotes

- **Description:** Various quote types
- **Input:** `quotes.gpx`
- **Output:** `quotes_to_caltopo_geojson.json`
- **Time:** 0.171s

### GPX→CalTopo: long_name

- **Description:** Very long name (1000+ chars)
- **Input:** `long_name.gpx`
- **Output:** `long_name_to_caltopo_geojson.json`
- **Time:** 0.171s

### GPX→CalTopo: empty_names

- **Description:** Empty/missing names
- **Input:** `empty_names.gpx`
- **Output:** `empty_names_to_caltopo_geojson.json`
- **Time:** 0.161s

### GPX→CalTopo: empty

- **Description:** Empty GPX file
- **Input:** `empty.gpx`
- **Output:** `empty_to_caltopo_geojson.json`
- **Time:** 0.153s

### GPX→CalTopo: single_waypoint

- **Description:** Single waypoint
- **Input:** `single_waypoint.gpx`
- **Output:** `single_waypoint_to_caltopo_geojson.json`
- **Time:** 0.159s

### GPX→CalTopo: single_point_track

- **Description:** Track with 1 point
- **Input:** `single_point_track.gpx`
- **Output:** `single_point_track_to_caltopo_geojson.json`
- **Time:** 0.147s

### GPX→CalTopo: colors

- **Description:** Various color specifications
- **Input:** `colors.gpx`
- **Output:** `colors_to_caltopo_geojson.json`
- **Time:** 0.156s

### GPX→CalTopo: duplicates

- **Description:** Duplicate waypoints
- **Input:** `duplicates.gpx`
- **Output:** `duplicates_to_caltopo_geojson.json`
- **Time:** 0.185s

### CalTopo→OnX: single_marker

- **Description:** Single marker
- **Input:** `single_marker.json`
- **Output:** `single_marker_onx_output`
- **Time:** 0.190s

### CalTopo→OnX: mixed_features

- **Description:** All feature types
- **Input:** `mixed_features.json`
- **Output:** `mixed_features_onx_output`
- **Time:** 0.167s

### Stress: many_waypoints_1000

- **Description:** 1000 waypoints
- **Input:** `many_waypoints_1000.gpx`
- **Output:** `many_waypoints_1000_to_caltopo_geojson.json`
- **Time:** 0.181s

### Stress: many_waypoints_10000

- **Description:** 10,000 waypoints
- **Input:** `many_waypoints_10000.gpx`
- **Output:** `many_waypoints_10000_to_caltopo_geojson.json`
- **Time:** 0.416s

### Stress: long_track_1000

- **Description:** Track with 1000 points
- **Input:** `long_track_1000.gpx`
- **Output:** `long_track_1000_to_caltopo_geojson.json`
- **Time:** 0.159s

### Stress: long_track_10000

- **Description:** Track with 10,000 points
- **Input:** `long_track_10000.gpx`
- **Output:** `long_track_10000_to_caltopo_geojson.json`
- **Time:** 0.198s

