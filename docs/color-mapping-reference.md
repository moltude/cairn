# Color Mapping Reference

## Overview

This document provides a quick reference for color values used in Cairn for OnX Backcountry GPX exports.

## Color System Differences

OnX Backcountry uses **different color systems** for tracks vs waypoints:

- **Tracks**: Use OnX's custom color palette (brighter, more saturated colors)
- **Waypoints**: Use CSS standard colors (simpler RGB values)

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

### Waypoint Colors (CSS Standard)

| Color Name | RGBA Value | RGB | Hex | Visual | Status |
|------------|------------|-----|-----|--------|--------|
| Red | `rgba(255,0,0,1)` | RGB(255, 0, 0) | `#FF0000` | 🔴 Pure red | ✅ Updated |
| Blue | `rgba(0,0,255,1)` | RGB(0, 0, 255) | `#0000FF` | 🔵 Pure blue | ✅ Updated |
| Green | `rgba(0,128,0,1)` | RGB(0, 128, 0) | `#008000` | 🟢 Standard green | ✅ Updated |
| Orange | `rgba(255,165,0,1)` | RGB(255, 165, 0) | `#FFA500` | 🟠 CSS orange | ✅ Updated |
| Purple | `rgba(128,0,128,1)` | RGB(128, 0, 128) | `#800080` | 🟣 CSS purple | ✅ **Confirmed** |
| Yellow | `rgba(255,255,0,1)` | RGB(255, 255, 0) | `#FFFF00` | 🟡 Pure yellow | ✅ Updated |
| Cyan | `rgba(0,255,255,1)` | RGB(0, 255, 255) | `#00FFFF` | 🔷 Pure cyan | ✅ Updated |
| Magenta | `rgba(255,0,255,1)` | RGB(255, 0, 255) | `#FF00FF` | 💗 Pure magenta | ✅ Updated |
| Pink | `rgba(255,192,203,1)` | RGB(255, 192, 203) | `#FFC0CB` | 🌸 CSS pink | ✅ Updated |
| Teal | `rgba(0,128,128,1)` | RGB(0, 128, 128) | `#008080` | 🔷 CSS teal | ✅ Updated |

**Note:** Purple (`rgba(128,0,128,1)`) is the only color confirmed through export testing. The others are CSS standard values that OnX likely uses.

## Color Conversion Table

For quick reference when converting from OnX track colors to waypoint colors:

| From (Track Palette) | To (Waypoint CSS) | Color |
|---------------------|-------------------|-------|
| `rgba(255,59,48,1)` | `rgba(255,0,0,1)` | Red |
| `rgba(8,122,255,1)` | `rgba(0,0,255,1)` | Blue |
| `rgba(52,199,89,1)` | `rgba(0,128,0,1)` | Green |
| `rgba(255,149,0,1)` | `rgba(255,165,0,1)` | Orange |
| `rgba(175,82,222,1)` | `rgba(128,0,128,1)` | Purple ✅ |
| `rgba(255,204,0,1)` | `rgba(255,255,0,1)` | Yellow |
| `rgba(50,173,230,1)` | `rgba(0,255,255,1)` | Cyan |
| `rgba(255,45,85,1)` | `rgba(255,0,255,1)` | Magenta |
| `rgba(255,55,95,1)` | `rgba(255,192,203,1)` | Pink |
| `rgba(90,200,250,1)` | `rgba(0,128,128,1)` | Teal |

## Test Files

### Comprehensive Test Files

- **[`tests/fixtures/rattlesnake_test_waypoints.gpx`](../tests/fixtures/rattlesnake_test_waypoints.gpx)**
  - 34 waypoints with all icon types
  - Uses CSS standard colors for waypoints
  - Updated to use correct color values

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
# Use CSS standard colors
waypoint_color = "rgba(255,0,0,1)"  # Pure red for waypoints
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
- **2025-12-13**: Confirmed purple waypoint color `rgba(128,0,128,1)` through export testing
- **2025-12-13**: Updated test waypoints file to use CSS standard colors
- **2025-12-13**: Created color testing file for verification
