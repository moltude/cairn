# OnX Color Behavior

## Overview

OnX Backcountry uses different color systems for tracks vs waypoints when importing and exporting GPX files. This document describes the observed behavior and provides reference color values.

## Key Findings

### Tracks
- ✅ **Colors ARE imported and preserved correctly**
- ✅ **Colors can be manually changed in OnX UI**
- ✅ **Custom color values are supported**
- Uses OnX's custom color palette

### Waypoints
- ⚠️ **Colors use a DIFFERENT palette than tracks**
- ⚠️ **OnX uses standard CSS color values, not the custom palette**
- ⚠️ **Import behavior needs verification** (colors may or may not be imported)
- Uses CSS standard colors (e.g., `rgba(128,0,128,1)` for purple)

## Color Value Comparison

Based on testing with the XC Skiing waypoint:

### Purple Color
| Context | Color Value | Notes |
|---------|-------------|-------|
| **Track (Green Route)** | `rgba(52,199,89,1)` | OnX custom palette green |
| **Track (manually edited to purple)** | `rgba(128,0,128,1)` | CSS standard purple |
| **Waypoint (my test file)** | `rgba(175,82,222,1)` | OnX custom palette purple |
| **Waypoint (OnX exported)** | `rgba(128,0,128,1)` | CSS standard purple ✅ |

### Key Observation
When manually setting a waypoint to "Purple" in OnX's UI, OnX uses **`rgba(128,0,128,1)`** (CSS standard purple), NOT `rgba(175,82,222,1)` (OnX palette purple).

## Track Colors (OnX Custom Palette)

These are the color values Cairn uses for tracks, based on OnX's color palette:

| Color Name | RGBA Value | RGB Values | Usage |
|------------|------------|------------|--------|
| Red | `rgba(255,59,48,1)` | RGB(255, 59, 48) | Tracks |
| Blue | `rgba(8,122,255,1)` | RGB(8, 122, 255) | Tracks |
| Green | `rgba(52,199,89,1)` | RGB(52, 199, 89) | Tracks |
| Orange | `rgba(255,149,0,1)` | RGB(255, 149, 0) | Tracks |
| Purple | `rgba(175,82,222,1)` | RGB(175, 82, 222) | Tracks |
| Yellow | `rgba(255,204,0,1)` | RGB(255, 204, 0) | Tracks |
| Cyan | `rgba(50,173,230,1)` | RGB(50, 173, 230) | Tracks |
| Magenta | `rgba(255,45,85,1)` | RGB(255, 45, 85) | Tracks |
| Pink | `rgba(255,55,95,1)` | RGB(255, 55, 95) | Tracks |
| Teal | `rgba(90,200,250,1)` | RGB(90, 200, 250) | Tracks |

## Waypoint Colors (CSS Standard Values)

Based on observed OnX behavior, waypoints appear to use standard CSS color values:

| Color Name | Expected RGBA Value | RGB Values | Notes |
|------------|---------------------|------------|-------|
| Purple | `rgba(128,0,128,1)` | RGB(128, 0, 128) | ✅ Confirmed from export |
| Red | `rgba(255,0,0,1)` | RGB(255, 0, 0) | ⚠️ Needs verification |
| Blue | `rgba(0,0,255,1)` | RGB(0, 0, 255) | ⚠️ Needs verification |
| Green | `rgba(0,128,0,1)` | RGB(0, 128, 0) | ⚠️ Needs verification |
| Orange | `rgba(255,165,0,1)` | RGB(255, 165, 0) | ⚠️ Needs verification |
| Yellow | `rgba(255,255,0,1)` | RGB(255, 255, 0) | ⚠️ Needs verification |
| Cyan | `rgba(0,255,255,1)` | RGB(0, 255, 255) | ⚠️ Needs verification |
| Magenta | `rgba(255,0,255,1)` | RGB(255, 0, 255) | ⚠️ Needs verification |
| Pink | `rgba(255,192,203,1)` | RGB(255, 192, 203) | ⚠️ Needs verification |
| Teal | `rgba(0,128,128,1)` | RGB(0, 128, 128) | ⚠️ Needs verification |
| White | `rgba(255,255,255,1)` | RGB(255, 255, 255) | ⚠️ Needs verification |
| Black | `rgba(0,0,0,1)` | RGB(0, 0, 0) | ⚠️ Needs verification |

**Note:** These are CSS standard color values. OnX may use slightly different values. Testing required to confirm exact values.

## Testing Results

### Test Case 1: XC Skiing Waypoint (Purple)
- **Sent:** `rgba(175,82,222,1)` (OnX palette purple)
- **OnX Exported:** `rgba(128,0,128,1)` (CSS purple)
- **Result:** OnX uses CSS standard purple, not palette purple

### Test Case 2: 4x4 Waypoint (Green)
- **Sent:** `rgba(52,199,89,1)` (OnX palette green)
- **OnX Exported:** `rgba(132,212,0,1)` (Lime/Chartreuse)
- **Result:** OnX appears to ignore/override the color on import

### Test Case 3: Lookout Waypoint (Pink)
- **Sent:** `rgba(255,55,95,1)` (OnX palette pink)
- **OnX Exported:** `rgba(132,212,0,1)` (Lime/Chartreuse)
- **Result:** OnX appears to ignore/override the color on import

## Import Behavior

### Tracks
1. **Import:** Colors are correctly imported from GPX `<onx:color>` field
2. **Display:** Colors display correctly in both map and legend
3. **Export:** Colors are preserved when exporting
4. **Manual Edit:** Colors can be changed and new colors are saved

### Waypoints
1. **Import:** ⚠️ Colors may NOT be imported correctly (needs more testing)
2. **Display:** OnX may assign default/automatic colors on import
3. **Export:** After manual edit, OnX exports using CSS standard colors
4. **Manual Edit:** Colors can be changed in OnX UI to CSS standard colors

## Recommendations for Cairn

### For Tracks
✅ **Current approach is correct:**
- Use OnX custom palette colors (`rgba(255,59,48,1)`, etc.)
- Colors are preserved and work correctly

### For Waypoints
⚠️ **Needs adjustment:**
- Use CSS standard colors (`rgba(128,0,128,1)`, etc.) instead of OnX palette colors
- Test if this improves import behavior
- Document that OnX may override colors on import

## Next Steps

1. ✅ Document color differences (this file)
2. 🔄 Test all CSS standard colors for waypoints
3. 🔄 Update test waypoint file with correct color values
4. 🔄 Update Cairn color mapper if needed
5. 🔄 Document findings in README

## Related Files

- [`cairn/core/mapper.py`](../cairn/core/mapper.py) - Color mapping logic
- [`cairn_config.yaml`](../cairn_config.yaml) - Icon and color configuration
- [`tests/fixtures/rattlesnake_test_waypoints.gpx`](../tests/fixtures/rattlesnake_test_waypoints.gpx) - Test waypoints
- [`tests/fixtures/rattlesnake_test_tracks.gpx`](../tests/fixtures/rattlesnake_test_tracks.gpx) - Test tracks

## References

- [CSS Standard Colors](https://www.w3.org/TR/css-color-3/#html4)
- [OnX Backcountry](https://www.onxmaps.com/backcountry)
- GPX 1.1 Specification
