# OnX Sorting Behavior

## Overview

This document describes observed behavior of OnX Backcountry's waypoint sorting and ordering, based on testing and user reports.

## The Problem

Waypoints appear in the **correct order during pre-import preview and import** into OnX, but the order **changes to unpredictable/random ordering after import completes** when viewing items in folders. Additionally, waypoints can be moved to any position in the list when removed from a folder and re-added.

## Observed Behavior

### Key Finding: Storage vs Display

**OnX preserves GPX element order in storage** but **re-sorts for UI display**.

When waypoints or tracks are exported from OnX, they appear in the same order as the original GPX file. However, the OnX UI displays them in a different order:

- **Waypoints**: Grouped by icon type, with unpredictable order within groups
- **Tracks**: Sorted in **reverse alphabetical order** (Z-A)

### During Pre-Import and Import
- **Pre-import preview shows correct order** - Waypoints appear in GPX file order
- **Import process respects GPX element order** - Waypoints are imported in the order they appear in the GPX file
- **Import summary shows correct order** - The import confirmation screen displays items in the expected order
- This confirms that OnX correctly reads and processes GPX element order during import

### Storage (GPX Export)
- **OnX preserves the original GPX element order in storage** (for unmodified waypoints)
- Exported GPX files match the order of imported GPX files (except for waypoints that were modified in OnX)
- **Modified waypoints may change position** - If a waypoint is renamed or its icon is changed in OnX, it may be reordered in the exported GPX
- This confirms the issue is primarily a UI display problem, not a storage problem

### UI Display (After Import)

#### Waypoints - Unpredictable Ordering
- **Order reverts to unpredictable/random after import completes**
- OnX groups waypoints by icon type (Hazard first, then Location/Campsite)
- **Within each icon group, the sorting order is UNPREDICTABLE and can change**
- Observed patterns (from Crazy Mountain 100M test case):
  1. `Hazard` icons appear first (e.g., `Deadfall` entries grouped together)
  2. Then `Location` and `Campsite` icons appear together
  3. Within the Location group, order varies and is inconsistent:
     - First observation: `#06`, `#09`, `#08`, `CONICAL PASS`, `#10`, `#07`, `#03`, `#0`, `#02`, `#04`, `#01`, `#0`
     - After remove/re-add: `07`, `08`, `09`, `CONICAL PASS`, `06`, `10`, `01`, `0`, `02`, `03`, `04`

- **The sorting is NOT alphabetical, NOT numerical, and NOT by coordinates**
- **The sorting appears to be based on unknown internal criteria** (possibly OnX waypoint IDs, timestamps, or other metadata)
- **Icon grouping is approximate** - `Campsite` icons may appear mixed within `Location` groups

#### Waypoints - Reordering When Removed/Re-added
- **Waypoints can appear anywhere in the list when removed from folder and re-added**
- Removing waypoints from a folder and adding them back causes unpredictable reordering
- The same waypoint may appear in different positions each time it's removed and re-added
- This confirms that OnX uses internal metadata (not GPX order) for UI display sorting

#### Tracks
- **Tracks are sorted in REVERSE ALPHABETICAL ORDER (Z-A)**
- This is **predictable and consistent**
- Example: `Sunlight Lake Trail` appears first, `CM100 #01 Start to Porcupine` appears last
- Icon colors do not affect track sorting (unlike waypoints where icon type groups items)

## Test Case: Crazy Mountain 100M

### Files Analyzed
- **Original Waypoints GPX**: `onx_ready/Crazy_Mountain_100M_Waypoints.gpx` (created by Cairn)
- **Original Tracks GPX**: `onx_ready/Crazy_Mountain_100M_Tracks.gpx` (created by Cairn)
- **Exported GPX**: `onx-markups-12132025 (1).gpx` and `onx-markups-12132025 (2).gpx` (exported from OnX)
- **UI Screenshots**: OnX display after import completion and after remove/re-add operations

### Original GPX Order (what Cairn wrote)

Testing with `Crazy_Mountain_100M_Waypoints.gpx` containing 17 waypoints:

1. `#0 Finish Line` (Location)
2. `#0 Start Line` (Location)
3. `#01 Porcupine Mile 6.1` (Location)
4. `#02 Ibex Mile 19.4` (Location)
5. `#03 & #05 Cow Camp Mile 31.9 & 54.8` (Campsite)
6. `#04 Halfmoon Mile 43.4` (Location)
7. `#06 Sunlight Mile 63.3` (Location)
8. `#07 Crandall Mile 70.4` (Location)
9. `#08 Forest Lake Mile 78.3` (Location)
10. `#09 Honey Trail Mile 85.4` (Location)
11. `#10 Hunting Camp Mile 92.8` (Campsite)
12. `CONICAL PASS CUTOFF 12:45 AM` (Location)
13. `Dead fall` (Hazard)
14-17. `Deadfall` x4 (Hazard)

### OnX Exported GPX Order (storage)

- ✅ **Matches original order exactly** (for unmodified waypoints) - OnX preserves GPX element order in storage
- ⚠️ **Modified waypoints may change position** - Example: `0 Finish Line` renamed to `12 Finish Line` moved in exported GPX

### OnX UI Display Order (from screenshots)

**First observation (after initial import):**

Within the Location icon group, the order was:
1. `#06 Sunlight Mile 63.3` (Location)
2. `#09 Honey Trail Mile 85.4` (Location)
3. `#08 Forest Lake Mile 78.3` (Location)
4. `CONICAL PASS CUTOFF 12:45 AM` (Location)
5. `#10 Hunting Camp Mile 92.8` (Campsite - appears in Location group)
6. `#07 Crandall Mile 70.4` (Location)
7. `#03 & #05 Cow Camp Mile 31.9 & 54.8` (Campsite - appears in Location group)
8. `#0 Start Line` (Location)
9. `#02 Ibex Mile 19.4` (Location)
10. `#04 Halfmoon Mile 43.4` (Location)
11. `#01 Porcupine Mile 6.1` (Location)
12. `#0 Finish Line` (Location)

**After removing waypoints from folder and re-adding:**

The order changed to:
1. `07 Crandall Mile 70.4` (Location)
2. `08 Forest Lake Mile 78.3` (Location)
3. `09 Honey Trail Mile 85.4` (Location)
4. `CONICAL PASS CUTOFF 12:45 AM` (Location)
5. `06 Sunlight Mile 63.3` (Location)
6. `10 Hunting Camp Mile 92.8` (Campsite)
7. `01 Porcupine Mile 6.1` (Location)
8. `0 Start Line` (Location)
9. `02 Ibex Mile 19.4` (Location)
10. `03 05 Cow Camp Mile 31.9 54.8` (Campsite)
11. `04 Halfmoon Mile 43.4` (Location)
12. `12 Finish Line` (Location - renamed from `0 Finish Line`)

**Note:** The order is completely different after remove/re-add, confirming unpredictable sorting behavior.

**Key Observations:**

1. **Sorting is NOT alphabetical**
   - Order: `#06`, `#09`, `#08`, `CONICAL`, `#10`, `#07`, `#03`, `#0`, `#02`, `#04`, `#01`, `#0`
   - Alphabetical would be: `#0`, `#01`, `#02`, `#03`, `#04`, `#06`, `#07`, `#08`, `#09`, `#10`, `CONICAL`

2. **Sorting is NOT numerical**
   - Order: `#06`, `#09`, `#08`, `#10`, `#07`, `#03`, `#0`, `#02`, `#04`, `#01`, `#0`
   - Numerical would be: `#0`, `#01`, `#02`, `#03`, `#04`, `#06`, `#07`, `#08`, `#09`, `#10`

3. **Sorting is NOT by mile marker**
   - Order: 63.3, 85.4, 78.3, (none), 92.8, 70.4, 31.9, 0, 19.4, 43.4, 6.1, 0
   - Mile marker order would be: 0, 0, 6.1, 19.4, 31.9, 43.4, 63.3, 70.4, 78.3, 85.4, 92.8

4. **Icon grouping is approximate, not strict**
   - Waypoints are grouped by icon type (Hazard first, then Location/Campsite)
   - But within icon groups, the sorting appears **random or based on an unknown internal criterion**
   - `Campsite` icons (`#10`, `#03 & #05`) appear mixed within the `Location` group

5. **The sorting pattern is NOT predictable**
   - No clear alphabetical, numerical, or coordinate-based pattern
   - May be based on:
     - Internal OnX waypoint IDs
     - Import/creation timestamps
     - Some other internal metadata
     - Or a combination of factors that's not obvious from the GPX data

**Conclusion**: OnX groups waypoints by icon type, but **within each icon group, the sorting order is unpredictable** and does not follow any standard sorting algorithm (alphabetical, numerical, or by coordinates). The order can change when waypoints are removed and re-added to folders.

## GPX File Structure

Cairn writes GPX files with waypoints in natural sort order (using `natural_sort_key`):
- `#0 Start Line`
- `#0 Finish Line`
- `#01 Porcupine Mile 6.1`
- `#02 Ibex Mile 19.4`
- `#03 & #05 Cow Camp Mile 31.9 & 54.8`
- `#04 Halfmoon Mile 43.4`
- ... etc.

The GPX file order is verified and logged during conversion (when debug logging is enabled).

## Debugging Tools

Cairn includes several debugging tools to help investigate sorting issues:

### 1. Debug Logging

Enable debug logging to see waypoint order before and after GPX write:

```bash
# Set environment variable to enable debug logging
export PYTHONPATH=.
python -m logging.basicConfig level=DEBUG
cairn convert input.json --output ./output
```

This will show:
- Waypoint order before write
- Waypoint order in GPX file (verified after write)
- Any mismatches between expected and actual GPX order

### 2. Order Verification Function

Use `cairn.utils.debug.verify_gpx_waypoint_order()` to read back waypoint order from a GPX file:

```python
from cairn.utils.debug import verify_gpx_waypoint_order
from pathlib import Path

gpx_path = Path("output/Waypoints.gpx")
order = verify_gpx_waypoint_order(gpx_path)
print("Waypoint order in GPX:", order)
```

### 3. Order Comparison Utility

Compare expected vs actual order:

```python
from cairn.utils.debug import display_order_comparison

expected = ["#01 First", "#02 Second", "#03 Third"]
actual = ["#01 First", "#03 Third", "#02 Second"]  # From OnX after import

display_order_comparison(expected, actual, "Expected vs OnX Order")
```

### 4. Test GPX File

A test GPX file is available at `tests/fixtures/test_onx_order_debug.gpx` with waypoints in explicit order. Import this into OnX to observe sorting behavior:

- Waypoints numbered #0, #01-#10
- Unnumbered waypoints
- Different icon types (Location vs Hazard)

## Potential Workarounds

### Waypoints

### ⚠️ Important Note
Since OnX re-sorts waypoints for UI display with unpredictable order within icon groups, **there is no way to preserve exact numerical order in the OnX UI**. However, the following strategies may help:

### 1. Icon Type Grouping (Only Predictable Factor)
Since OnX groups by icon type:
- **Use the same icon type** for waypoints that should appear together
- **Accept that different icon types will be grouped separately**
- **Note**: Even within icon groups, the order is unpredictable

### 2. No Reliable Sorting Strategy
Since OnX's sorting within icon groups is unpredictable:
- **There is no way to control the exact order** within icon groups
- **Naming conventions don't help** - alphabetical, numerical, or coordinate-based naming won't produce predictable results
- **Users must accept OnX's sorting** as-is

### 3. Workaround: Use Consistent Icon Types
The only reliable way to group waypoints is by icon type:
- All waypoints with the same icon will appear together
- But their order within that group will be unpredictable
- Consider using the same icon type for related waypoints if grouping is more important than order

### Tracks

### ⚠️ Important Note
Since OnX sorts tracks in **reverse alphabetical order (Z-A)**, you can control track order by naming them appropriately.

### 1. Reverse Alphabetical Naming Strategy
To get tracks to appear in a specific order, name them so they sort correctly in reverse alphabetical order:
- If you want `Track A` to appear before `Track B`, name it so it comes later alphabetically
- Example: To get `Start` → `Middle` → `Finish`, name them:
  - `Z - Start` (appears first - last alphabetically)
  - `M - Middle` (appears middle)
  - `A - Finish` (appears last - first alphabetically)

### 2. Numbered Tracks Strategy
For numbered tracks, use reverse numbering or prefix with letters:
- `Track 10`, `Track 9`, `Track 8`... `Track 1` will appear in reverse order
- Or use: `Z Track 1`, `Y Track 2`, `X Track 3`... to control exact order

### 3. Accept Reverse Alphabetical Order
- The sorting is predictable and consistent
- Users can learn to navigate tracks in reverse alphabetical order
- This is OnX's default behavior and cannot be changed

## Testing Strategy

To debug OnX sorting behavior:

1. **Generate GPX with known order**
   ```bash
   cairn convert input.json --output ./test_output
   ```

2. **Enable debug logging**
   ```bash
   export PYTHONPATH=.
   python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
   ```

3. **Verify GPX file order**
   ```python
   from cairn.utils.debug import analyze_gpx_order
   analyze_gpx_order(Path("test_output/Waypoints.gpx"))
   ```

4. **Import into OnX**
   - Note the order during import (should match GPX)
   - Note the order after import completes
   - Note the order when viewing in folder

5. **Compare orders**
   - GPX file order (from step 3)
   - OnX import order (from step 4)
   - OnX post-import order (from step 4)

6. **Identify sorting criteria**
   - Group by icon type?
   - Sort by name alphabetically?
   - Parse numbers differently?
   - Use timestamps?

## Known Limitations

- **OnX does not provide documentation on its sorting behavior**
- **OnX does not allow manual reordering of waypoints** - The UI sort is automatic
- **Import order is correct** - Waypoints appear in expected order during pre-import and import
- **Folder view order is unpredictable** - Order becomes random/unpredictable when viewing in folders
- **Remove/re-add causes reordering** - Waypoints can appear anywhere when removed and re-added
- **Storage order is preserved** - Exported GPX files match imported order (for unmodified waypoints)
- **UI display order differs from storage** - Waypoints are grouped by icon type with unpredictable order within groups
- Sorting behavior may vary between OnX Web and OnX Mobile apps
- Sorting behavior may change with OnX app updates

## Conclusion

Based on real-world testing:

1. ✅ **Cairn writes GPX files correctly** - Waypoints are in natural sort order
2. ✅ **OnX correctly reads GPX order during import** - Pre-import preview and import process show correct order
3. ✅ **OnX preserves storage order** - Exported GPX matches imported GPX (for unmodified waypoints)
4. ⚠️ **OnX re-sorts for UI display** - Order becomes unpredictable/random when viewing in folders
5. ⚠️ **Removing/re-adding waypoints causes reordering** - Waypoints can appear anywhere in the list
6. ⚠️ **No workaround exists** - This is OnX's default behavior and cannot be changed

**Key Findings:**
- **Import order is correct** - Users see waypoints in the expected order during import
- **Folder view order is unpredictable** - Order changes to random/unpredictable after import
- **Modifications cause reordering** - Renaming or changing icons can move waypoints
- **Remove/re-add causes reordering** - Waypoints can appear in any position when re-added

**Recommendation:** Document this behavior for users. The GPX file order is preserved in storage and respected during import, but OnX's folder view uses unpredictable internal sorting that cannot be controlled. Users should expect waypoints to appear in random order when viewing folders, even though they were imported in the correct order.

## Key Takeaways

1. **Import order is correct** - Waypoints appear in expected order during pre-import preview and import process
2. **Folder view order is unpredictable** - Order reverts to random/unpredictable ordering when viewing data in folders
3. **Remove/re-add causes reordering** - Waypoints get moved around when removed from folders and added back - they can appear anywhere in the list
4. **Storage order is preserved** - Exported GPX files maintain original order (for unmodified waypoints)
5. **No workaround exists** - This is OnX's default behavior and cannot be changed

**Recommendation:** Set expectations for users that waypoints will appear in correct order during import, but will be randomly ordered when viewing in folders. The GPX file order is preserved in storage and respected during import, but OnX's folder view uses unpredictable internal sorting that cannot be controlled.

## Related Files

- `cairn/core/writers.py` - GPX writing with order verification
- `cairn/commands/convert_cmd.py` - Debug output for sort order
- `cairn/utils/debug.py` - Order comparison utilities
- `tests/fixtures/test_onx_order_debug.gpx` - Test GPX file

## References

- [GPX 1.1 Specification](https://www.topografix.com/GPX/1/1/)
- OnX Backcountry import documentation (if available)
- User reports and testing observations
