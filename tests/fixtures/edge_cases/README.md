# Edge Case Test Fixtures

This directory contains comprehensive test fixtures for validating Cairn's edge case handling.

## Generated: December 16, 2025

## Test Categories

### Geographic Edge Cases
- `poles.gpx` - Waypoints at North (90°N) and South (-90°S) Poles
- `dateline.gpx` - Waypoints at International Date Line (±180°)
- `prime_meridian.gpx` - Waypoint at Prime Meridian (0° longitude)
- `equator.gpx` - Waypoint at Equator (0° latitude)

### Elevation Edge Cases
- `elevations.gpx` - Sea level (0m), below sea level (-430m), Mt. Everest (8849m), missing elevation

### Text/Unicode Edge Cases
- `unicode.gpx` - Emoji (🏕️), Spanish, Chinese, Cyrillic, Arabic (RTL)
- `xml_chars.gpx` - XML special characters (`<`, `>`, `&`, quotes)
- `quotes.gpx` - Single and double quotes
- `long_name.gpx` - 1000+ character names
- `empty_names.gpx` - Empty, missing, whitespace-only names

### Size Edge Cases
- `empty.gpx` - Valid GPX with no features
- `empty.json` - Valid GeoJSON with no features
- `single_waypoint.gpx` - Minimal valid file (1 waypoint)
- `single_point_track.gpx` - Track with only 1 point
- `many_waypoints_1000.gpx` - 1,000 waypoints
- `many_waypoints_10000.gpx` - 10,000 waypoints

### Track Edge Cases
- `long_track_1000.gpx` - Track with 1,000 points
- `long_track_10000.gpx` - Track with 10,000 points

### Color Edge Cases
- `colors.gpx` - White, Black, Red, missing color

### Duplicate Edge Cases
- `duplicates.gpx` - Exact duplicate waypoints, same-name different-location

### GeoJSON Edge Cases
- `single_marker.json` - Minimal GeoJSON with 1 marker
- `mixed_features.json` - All feature types (Point, LineString, Polygon)

### Malformed Files (Expected Failures)
- `malformed.gpx` - Invalid XML (unclosed tags)
- `malformed.json` - Invalid JSON (syntax errors)

## Usage

### Generate Fixtures
```bash
python3 scripts/generate_edge_case_fixtures.py
```

### Run Tests
```bash
python3 scripts/test_edge_cases.py
```

### Validate Individual File
```bash
python3 scripts/validate_output_integrity.py tests/output/edge_cases/some_file.json
```

## Test Results

See `docs/QA_TEST_RESULTS.md` for comprehensive test results and analysis.

**Summary:** 21/24 tests pass (87.5% success rate)
- All geographic, elevation, text, color, duplicate, and GeoJSON tests pass
- Stress tests with 10,000+ features pass
- Malformed files correctly rejected with clear error messages
