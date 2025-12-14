# Color Mapping Reference

## Overview

This document provides a quick reference for color values used in Cairn for OnX Backcountry GPX exports.

## Color System Differences

OnX Backcountry uses **different color systems** for tracks vs waypoints:

- **Tracks**: Use OnX's custom color palette (brighter, more saturated colors)
- **Waypoints**: Support **only 10 official colors** (fixed RGBA values)

## Color Value Tables

### Track Colors (OnX Custom Palette)

| Color Name | RGBA Value | RGB | Hex | Visual |
|------------|------------|-----|-----|--------|
| Red | `rgba(255,59,48,1)` | RGB(255, 59, 48) | `#FF3B30` | 🔴 Bright red |
| Blue | `rgba(8,122,255,1)` | RGB(8, 122, 255) | `#087AFF` | 🔵 Bright blue |
| Green | `rgba(52,199,89,1)` | RGB(52, 199, 89) | `#34C759` | 🟢 Bright green |
| Orange | `rgba(255,149,0,1)` | RGB(255, 149, 0) | `#FF9500` | 🟠 Bright orange |
| Purple | `rgba(175,82,222,1)` | RGB(175, 82, 222) | `#AF52DE` | 🟣 Bright purple |
| Yellow | `rgba(255,204,0,1)` | RGB(255, 204, 0) | `#FFCC00` | 🟡 Bright yellow |
| Cyan | `rgba(50,173,230,1)` | RGB(50, 173, 230) | `#32ADE6` | 🔷 Bright cyan |
| Magenta | `rgba(255,45,85,1)` | RGB(255, 45, 85) | `#FF2D55` | 🔴 Hot pink/magenta |
| Pink | `rgba(255,55,95,1)` | RGB(255, 55, 95) | `#FF375F` | 🌸 Bright pink |
| Teal | `rgba(90,200,250,1)` | RGB(90, 200, 250) | `#5AC8FA` | 🔷 Bright teal |

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

**Important:** Track colors and waypoint colors are different systems. **Only Blue uses the same RGBA value for tracks and waypoints.**

For full details (including picker layout), see [`docs/onx-waypoint-colors-definitive.md`](onx-waypoint-colors-definitive.md).

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
track_color = "rgba(255,59,48,1)"  # Bright red for tracks
```

### For Waypoints
```python
# Use ONLY the official 10 waypoint colors (see docs/onx-waypoint-colors-definitive.md)
waypoint_color = "rgba(255,0,0,1)"  # Red (official waypoint palette)
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
