# OnX Waypoint Colors - DEFINITIVE Reference

## Overview

This document contains the **definitive** list of OnX Backcountry's 10 waypoint colors, discovered through systematic export testing on December 13, 2025.

## The 10 Official OnX Waypoint Colors

| # | Color Name | RGBA Value | RGB | Hex | Position in Picker |
|---|------------|------------|-----|-----|-------------------|
| 1 | Red-Orange | `rgba(255,51,0,1)` | RGB(255, 51, 0) | `#FF3300` | Top row, 1st |
| 2 | Blue | `rgba(8,122,255,1)` | RGB(8, 122, 255) | `#087AFF` | Top row, 2nd |
| 3 | Cyan | `rgba(0,255,255,1)` | RGB(0, 255, 255) | `#00FFFF` | Top row, 3rd |
| 4 | Lime | `rgba(132,212,0,1)` | RGB(132, 212, 0) | `#84D400` | Top row, 4th |
| 5 | Black | `rgba(0,0,0,1)` | RGB(0, 0, 0) | `#000000` | Top row, 5th |
| 6 | White | `rgba(255,255,255,1)` | RGB(255, 255, 255) | `#FFFFFF` | Bottom row, 1st |
| 7 | Purple | `rgba(128,0,128,1)` | RGB(128, 0, 128) | `#800080` | Bottom row, 2nd |
| 8 | Yellow | `rgba(255,255,0,1)` | RGB(255, 255, 0) | `#FFFF00` | Bottom row, 3rd |
| 9 | Red | `rgba(255,0,0,1)` | RGB(255, 0, 0) | `#FF0000` | Bottom row, 4th |
| 10 | Brown | `rgba(139,69,19,1)` | RGB(139, 69, 19) | `#8B4513` | Bottom row, 5th |

## Color Picker Layout

```
Row 1: [Red-Orange] [Blue] [Cyan] [Lime] [Black]
Row 2: [White]      [Purple] [Yellow] [Red] [Brown]
```

## Important Notes

### Color Name Confusion

⚠️ **Be careful with naming!** OnX's color picker has two red-ish colors:
- **Red-Orange** `rgba(255,51,0,1)` - Top-left, vibrant red-orange
- **Red** `rgba(255,0,0,1)` - Bottom row 4th, pure red

### Colors That Work

✅ **ALL 10 colors work correctly on import!**

Previous testing showed checkmarks because I was using incorrect color values. The exact values above are confirmed to work.

### Track vs Waypoint Colors

| Color | Track Palette | Waypoint Palette | Match? |
|-------|---------------|------------------|--------|
| Blue | `rgba(8,122,255,1)` | `rgba(8,122,255,1)` | ✅ Same |
| Red | `rgba(255,59,48,1)` | `rgba(255,0,0,1)` | ❌ Different |
| Orange | `rgba(255,149,0,1)` | `rgba(255,51,0,1)` | ❌ Different |
| Yellow | `rgba(255,204,0,1)` | `rgba(255,255,0,1)` | ❌ Different |
| Purple | `rgba(175,82,222,1)` | `rgba(128,0,128,1)` | ❌ Different |
| Cyan | `rgba(50,173,230,1)` | `rgba(0,255,255,1)` | ❌ Different |

**Only Blue uses the same value for tracks and waypoints!**

## Recommended Distribution for 34 Waypoints

With 10 colors for 34 waypoints:

- **Red-Orange**: 4 waypoints - `rgba(255,51,0,1)`
- **Blue**: 4 waypoints - `rgba(8,122,255,1)`
- **Cyan**: 3 waypoints - `rgba(0,255,255,1)`
- **Lime**: 3 waypoints - `rgba(132,212,0,1)`
- **Black**: 3 waypoints - `rgba(0,0,0,1)`
- **White**: 3 waypoints - `rgba(255,255,255,1)`
- **Purple**: 4 waypoints - `rgba(128,0,128,1)`
- **Yellow**: 3 waypoints - `rgba(255,255,0,1)`
- **Red**: 4 waypoints - `rgba(255,0,0,1)`
- **Brown**: 3 waypoints - `rgba(139,69,19,1)`

**Total: 34 waypoints**

## Usage in Cairn

### For Waypoints - Use These 10 Colors ONLY

```python
ONX_WAYPOINT_COLORS = {
    'red-orange': 'rgba(255,51,0,1)',
    'blue': 'rgba(8,122,255,1)',
    'cyan': 'rgba(0,255,255,1)',
    'lime': 'rgba(132,212,0,1)',
    'black': 'rgba(0,0,0,1)',
    'white': 'rgba(255,255,255,1)',
    'purple': 'rgba(128,0,128,1)',
    'yellow': 'rgba(255,255,0,1)',
    'red': 'rgba(255,0,0,1)',
    'brown': 'rgba(139,69,19,1)',
}
```

### For Tracks - Use OnX Custom Palette

See [`color-mapping-reference.md`](color-mapping-reference.md) for track colors.

## Source

- Export file: `onx-markups-12132025 (9).gpx`
- Date: December 13, 2025
- Method: Manually set each waypoint to each color in OnX UI, exported, analyzed
- Result: 10 colors confirmed, all working correctly

## Related Documentation

- [`color-mapping-reference.md`](color-mapping-reference.md) - Track vs waypoint colors
- [`onx-color-behavior.md`](onx-color-behavior.md) - Color behavior analysis
- [`tests/fixtures/rattlesnake_test_waypoints.gpx`](../tests/fixtures/rattlesnake_test_waypoints.gpx) - Test file (needs update)

## Changelog

- **2025-12-13**: Definitive 10-color list confirmed through systematic testing
- **2025-12-13**: Confirmed all 10 colors work correctly on import with exact values
- **2025-12-13**: Identified Red-Orange vs Red naming confusion
