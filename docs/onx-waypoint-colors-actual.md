# OnX Waypoint Colors - Actual Values

## Overview

This document contains the **actual color values** that OnX Backcountry uses for waypoints, discovered through export testing on December 13, 2025.

## Key Finding

**OnX waypoints use a specific set of colors** that are different from both:
- CSS standard colors
- OnX's custom track palette colors

## Actual OnX Waypoint Colors

These colors were discovered by importing test waypoints into OnX and exporting them back:

| Color Name | RGBA Value | RGB | Hex | Notes |
|------------|------------|-----|-----|-------|
| Red (Pure) | `rgba(255,0,0,1)` | RGB(255, 0, 0) | `#FF0000` | ✅ CSS red |
| Red (OnX) | `rgba(255,59,48,1)` | RGB(255, 59, 48) | `#FF3B30` | ✅ OnX track red |
| Orange | `rgba(255,51,0,1)` | RGB(255, 51, 0) | `#FF3300` | ✅ Custom orange |
| Yellow | `rgba(255,255,0,1)` | RGB(255, 255, 0) | `#FFFF00` | ✅ Pure yellow |
| Lime/Chartreuse | `rgba(132,212,0,1)` | RGB(132, 212, 0) | `#84D400` | ✅ Lime green |
| Cyan | `rgba(0,255,255,1)` | RGB(0, 255, 255) | `#00FFFF` | ✅ Pure cyan |
| Purple | `rgba(128,0,128,1)` | RGB(128, 0, 128) | `#800080` | ✅ CSS purple |
| Magenta | `rgba(255,45,85,1)` | RGB(255, 45, 85) | `#FF2D55` | ✅ OnX magenta |
| Brown | `rgba(139,69,19,1)` | RGB(139, 69, 19) | `#8B4513` | ✅ Saddle brown |
| Black | `rgba(0,0,0,1)` | RGB(0, 0, 0) | `#000000` | ✅ Black |
| White | `rgba(255,255,255,1)` | RGB(255, 255, 255) | `#FFFFFF` | ✅ White |

## Test Results

From export file `onx-markups-12132025 (8).gpx`:

| Waypoint | Label Said | OnX Assigned |
|----------|------------|--------------|
| Camp Area - Ridge Camping Zone | Orange | `rgba(255,255,255,1)` White |
| Campground - Rattlesnake Rec Area | Purple | `rgba(139,69,19,1)` Brown |
| Waterfall - Cascade Falls | Cyan | `rgba(255,255,0,1)` Yellow |
| Hot Spring - Wilderness Soak | Magenta | `rgba(255,45,85,1)` Magenta ✅ |
| Potable Water - Trailhead Spigot | Pink | `rgba(0,255,255,1)` Cyan |
| Parking - Main Trailhead Lot | Red | `rgba(255,0,0,1)` Red ✅ |
| 4x4 - High Clearance Access | Green | `rgba(132,212,0,1)` Lime |
| Backpacker - Multi-Day Route | Yellow | `rgba(0,0,0,1)` Black |
| View - Valley Overlook | Magenta | `rgba(128,0,128,1)` Purple |
| Lookout - Historic Fire Tower | Pink | `rgba(132,212,0,1)` Lime |
| Cabin - Wilderness Shelter | Teal | `rgba(0,255,255,1)` Cyan |
| Shelter - Emergency Bivouac | Red | `rgba(255,59,48,1)` OnX Red |
| Location - Trail Junction | Orange | `rgba(255,51,0,1)` Orange ✅ |

## Color Palette for Test Fixtures

Based on the actual colors OnX uses, here's the recommended palette for test waypoints:

### Primary Colors (Most Common)
1. `rgba(255,0,0,1)` - Red (Pure)
2. `rgba(255,59,48,1)` - Red (OnX)
3. `rgba(255,51,0,1)` - Orange
4. `rgba(255,255,0,1)` - Yellow
5. `rgba(132,212,0,1)` - Lime/Chartreuse
6. `rgba(0,255,255,1)` - Cyan
7. `rgba(128,0,128,1)` - Purple
8. `rgba(255,45,85,1)` - Magenta
9. `rgba(139,69,19,1)` - Brown
10. `rgba(0,0,0,1)` - Black
11. `rgba(255,255,255,1)` - White

## Recommended Color Distribution for 34 Waypoints

To ensure variety and visibility:

- **Red (Pure)**: 3 waypoints - `rgba(255,0,0,1)`
- **Red (OnX)**: 3 waypoints - `rgba(255,59,48,1)`
- **Orange**: 3 waypoints - `rgba(255,51,0,1)`
- **Yellow**: 3 waypoints - `rgba(255,255,0,1)`
- **Lime**: 3 waypoints - `rgba(132,212,0,1)`
- **Cyan**: 3 waypoints - `rgba(0,255,255,1)`
- **Purple**: 4 waypoints - `rgba(128,0,128,1)`
- **Magenta**: 4 waypoints - `rgba(255,45,85,1)`
- **Brown**: 4 waypoints - `rgba(139,69,19,1)`
- **Black**: 2 waypoints - `rgba(0,0,0,1)`
- **White**: 2 waypoints - `rgba(255,255,255,1)`

**Total: 34 waypoints**

## Important Notes

1. **These are the ACTUAL colors OnX uses** - discovered through export testing
2. **OnX may still override colors on import** - the import behavior is still unclear
3. **Manual changes in OnX UI use these colors** - confirmed through testing
4. **Different from track colors** - tracks use the OnX custom palette

## Related Files

- [`color-mapping-reference.md`](color-mapping-reference.md) - Previous color reference (needs update)
- [`onx-color-behavior.md`](onx-color-behavior.md) - Color behavior analysis
- [`tests/fixtures/rattlesnake_test_waypoints.gpx`](../tests/fixtures/rattlesnake_test_waypoints.gpx) - Test waypoints (needs update)

## Source

Export file: `onx-markups-12132025 (8).gpx`
Date: December 13, 2025
