# Color Mapping Reference

## Overview

This document provides a quick reference for color values used in Cairn for OnX Backcountry GPX exports.

**Source**: Official onX GPX export (`onx-markups-12142025.gpx`) containing all available colors.

## Color System - Key Finding

OnX Backcountry uses the **same base color palette** for both tracks and waypoints:

- **Waypoints**: Support exactly 10 official colors (fixed RGBA values)
- **Tracks**: Support 11 official colors (the same 10 as waypoints + Fuchsia)

**All 10 waypoint colors are available in tracks with identical RGBA values!** Tracks simply have one additional color (Fuchsia) that waypoints don't support.

## Color Value Tables

### Track Colors (11 Official Colors)

**Tracks support 11 colors** (waypoints only support 10).

**IMPORTANT:** The first 10 colors are IDENTICAL to the waypoint palette. Only Fuchsia is track-exclusive.

| # | Color Name | RGBA Value | RGB | Hex | In Waypoints? |
|---|------------|------------|-----|-----|---------------|
| 1 | Red-Orange | `rgba(255,51,0,1)` | RGB(255, 51, 0) | `#FF3300` | ✅ Yes |
| 2 | Blue | `rgba(8,122,255,1)` | RGB(8, 122, 255) | `#087AFF` | ✅ Yes |
| 3 | Cyan | `rgba(0,255,255,1)` | RGB(0, 255, 255) | `#00FFFF` | ✅ Yes |
| 4 | Lime | `rgba(132,212,0,1)` | RGB(132, 212, 0) | `#84D400` | ✅ Yes |
| 5 | Black | `rgba(0,0,0,1)` | RGB(0, 0, 0) | `#000000` | ✅ Yes |
| 6 | White | `rgba(255,255,255,1)` | RGB(255, 255, 255) | `#FFFFFF` | ✅ Yes |
| 7 | Purple | `rgba(128,0,128,1)` | RGB(128, 0, 128) | `#800080` | ✅ Yes |
| 8 | Yellow | `rgba(255,255,0,1)` | RGB(255, 255, 0) | `#FFFF00` | ✅ Yes |
| 9 | Red | `rgba(255,0,0,1)` | RGB(255, 0, 0) | `#FF0000` | ✅ Yes |
| 10 | Brown | `rgba(139,69,19,1)` | RGB(139, 69, 19) | `#8B4513` | ✅ Yes |
| 11 | Fuchsia | `rgba(255,0,255,1)` | RGB(255, 0, 255) | `#FF00FF` | ❌ No (track-only) |

### Waypoint Colors (Official 10-color Palette)

These 10 values are the **only** waypoint colors onX Backcountry supports reliably on import:

| # | Color Name | RGBA Value | Hex |
|---|------------|------------|-----|
| 1 | Red-Orange | `rgba(255,51,0,1)` | `#FF3300` |
| 2 | Blue | `rgba(8,122,255,1)` | `#087AFF` |
| 3 | Cyan | `rgba(0,255,255,1)` | `#00FFFF` |
| 4 | Lime | `rgba(132,212,0,1)` | `#84D400` |
| 5 | Black | `rgba(0,0,0,1)` | `#000000` |
| 6 | White | `rgba(255,255,255,1)` | `#FFFFFF` |
| 7 | Purple | `rgba(128,0,128,1)` | `#800080` |
| 8 | Yellow | `rgba(255,255,0,1)` | `#FFFF00` |
| 9 | Red | `rgba(255,0,0,1)` | `#FF0000` |
| 10 | Brown | `rgba(139,69,19,1)` | `#8B4513` |

**Important:** All 10 waypoint colors use the exact same RGBA values as the first 10 track colors. Tracks have one additional color (Fuchsia) that waypoints don't support.

For historical details (including picker layout), see [`docs/onx-waypoint-colors-definitive.md`](onx-waypoint-colors-definitive.md).

## Test Files

### Comprehensive Test Files

- **[`tests/fixtures/rattlesnake_test_waypoints.gpx`](../tests/fixtures/rattlesnake_test_waypoints.gpx)**
  - 34 waypoints with all icon types
  - Uses the official 10-color waypoint palette

- **[`tests/fixtures/rattlesnake_test_tracks.gpx`](../tests/fixtures/rattlesnake_test_tracks.gpx)**
  - 10 tracks with different colors
  - Uses OnX custom palette colors
  - Verified working correctly

### Color Testing File

- **[`tests/fixtures/onx_waypoint_color_test.gpx`](../tests/fixtures/onx_waypoint_color_test.gpx)**
  - 12 test waypoints, one for each color
  - For manual testing: import, change colors in OnX UI, export, and verify
  - Helps confirm OnX's actual color values

## Usage in Cairn

### For Tracks
```python
# Use OnX custom palette colors
track_color = "rgba(255,0,0,1)"  # Red (same as waypoint red)
```

### For Waypoints
```python
# Use ONLY the official 10 waypoint colors (same as first 10 track colors)
waypoint_color = "rgba(255,0,0,1)"  # Red (works for both waypoints and tracks)
# Note: Cannot use rgba(255,0,255,1) - Fuchsia is track-only
```

## Related Documentation

- [`onx-color-behavior.md`](onx-color-behavior.md) - Detailed behavior analysis
- [`cairn/core/mapper.py`](../cairn/core/mapper.py) - Color mapping implementation
- [`cairn_config.yaml`](../cairn_config.yaml) - Color configuration

## Testing Instructions

1. Import `tests/fixtures/onx_waypoint_color_test.gpx` into OnX
2. For each waypoint, manually change its color in OnX UI to match the description
3. Export the waypoints from OnX
4. Compare exported color values to this reference table
5. Update this document with any discrepancies

## Changelog

- **2025-12-13**: Initial documentation
- **2025-12-13**: Added track palette reference table
- **2025-12-13**: Superseded by definitive waypoint palette measurements
