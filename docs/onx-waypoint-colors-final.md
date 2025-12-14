# OnX Waypoint Colors - Final Investigation

## Key Finding

OnX waypoint colors are **very particular** - they only accept specific exact RGBA values. Colors that don't match exactly appear to get rejected or assigned a default.

## Test Results

From import test showing checkmarks (= color not accepted):

| Color Label | RGBA Value Sent | Result |
|-------------|-----------------|---------|
| Red | `rgba(255,0,0,1)` | ✅ **Works** |
| Red-OnX | `rgba(255,59,48,1)` | ✅ **Works** (seen in exports) |
| Orange | `rgba(255,51,0,1)` | ❌ **Rejected** (checkmark) |
| Yellow | `rgba(255,255,0,1)` | ✅ **Works** |
| Lime | `rgba(132,212,0,1)` | ❌ **Rejected** (checkmark) |
| Cyan | `rgba(0,255,255,1)` | ✅ **Works** |
| Purple | `rgba(128,0,128,1)` | ✅ **Works** (confirmed) |
| Magenta | `rgba(255,45,85,1)` | ✅ **Works** (seen in exports) |
| Brown | `rgba(139,69,19,1)` | ✅ **Works** (seen in exports) |
| Black | `rgba(0,0,0,1)` | ✅ **Works** |
| White | `rgba(255,255,255,1)` | ❌ **Rejected** (checkmark) |

## OnX Color Picker Analysis

From the UI screenshot, OnX offers 10 colors:

**Row 1 (left to right):**
1. Red/Orange - bright red-orange
2. Blue - bright blue
3. Cyan - bright cyan/turquoise
4. Green/Lime - bright lime green
5. Black

**Row 2 (left to right):**
6. White (outline only)
7. Purple - dark purple
8. Yellow - bright yellow
9. Red - bright red
10. Brown - dark brown

## Problem Colors

### 1. White `rgba(255,255,255,1)`
- Shows as **outlined circle** in color picker
- May not be a valid color for import (only for manual selection?)
- Gets rejected on import

### 2. Orange `rgba(255,51,0,1)`
- Not exactly matching OnX's orange value
- OnX might use a different orange (possibly `rgba(255,149,0,1)` or `rgba(255,95,31,1)`)
- Gets rejected on import

### 3. Lime/Green `rgba(132,212,0,1)`
- Appears in exports but gets rejected on import
- OnX might only accept it when manually set, not on import
- May need different green value like `rgba(0,128,0,1)` or `rgba(50,215,75,1)`

### 4. Pink
- **Not available in OnX waypoint colors at all!**
- Pink doesn't exist in OnX's waypoint color picker
- Any pink values will be rejected

## Colors That Definitely Work

Based on successful imports and exports:

| Color | RGBA Value | Status |
|-------|------------|--------|
| Red | `rgba(255,0,0,1)` | ✅ Confirmed |
| Red-OnX | `rgba(255,59,48,1)` | ✅ Confirmed (from exports) |
| Blue | Unknown (need to test) | ⚠️ Need value |
| Yellow | `rgba(255,255,0,1)` | ✅ Confirmed |
| Cyan | `rgba(0,255,255,1)` | ✅ Confirmed |
| Purple | `rgba(128,0,128,1)` | ✅ Confirmed |
| Magenta | `rgba(255,45,85,1)` | ✅ Confirmed (from exports) |
| Brown | `rgba(139,69,19,1)` | ✅ Confirmed (from exports) |
| Black | `rgba(0,0,0,1)` | ✅ Confirmed |

## Recommendation

I need to:
1. **Remove White** - appears to not work for imports
2. **Fix Orange** - find OnX's actual orange value
3. **Fix Lime/Green** - find OnX's actual green value
4. **Never use Pink** - doesn't exist in OnX waypoints
5. **Add Blue** - missing from my palette but exists in OnX

## Next Steps

1. Manually change waypoints to Orange, Green/Lime, Blue, and White in OnX
2. Export them to discover exact RGBA values OnX uses
3. Update test fixture with only confirmed working colors
4. Document the 8-9 colors that actually work

## Source

- Import test with checkmarks: Screenshots from Dec 13, 2025
- OnX color picker: UI screenshot
- Export analysis: Previous GPX exports
