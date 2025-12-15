# Cairn

## This is a work in progress

### Why I built this

I'm an advocate for open data and being able to exchange map data between platforms. GPX/KML/GeoJSON are meant to be platform-agnostic interchange formats (or at least that's how I understand them). Cairn is my attempt to make that promise feel real for backcountry mapping: move between onX and CalTopo while taking *all the map customization with you* (icons, colors, notes, and organization), not just raw shapes.

This tool started as an experiment and it surfaced a number of challenges. I'm not an expert — if my assumptions are wrong, I want to find out and correct them. The goal is a faithful migration, not "a file that happens to import."

### What this tool is for

In theory, these formats should make it easy to move between map platforms. In practice, each platform:

- supports only a subset of each format
- adds proprietary fields or extensions
- rewrites data during import/export (sometimes subtly)

I built Cairn to make migration between **onX Backcountry** and **CalTopo** easier *without losing the customization that makes a map valuable* (names, notes, colors, icons, and organizational intent) — not just the raw shapes.

Right now, the most reliable direction is **onX → CalTopo**.

---

## Quick start (onX → CalTopo)

### 1) Export from onX (export both files)

Export the same map from onX in **both** formats and save them to a directory:

- **GPX**: best source for waypoint metadata (name/notes) plus onX-specific icon/color extensions
- **KML**: best source for areas/polygons (onX often exports areas as polygons in KML but as tracks/routes in GPX)

You want both files from the same export session so they represent the same content.

### 2) Convert with Cairn

Point Cairn at the directory containing your exports:

```bash
# Interactive mode - will prompt for directory and let you select files
uv run cairn migrate onx-to-caltopo

# Or specify the directory directly
uv run cairn migrate onx-to-caltopo ~/Downloads/onx-exports

# With custom output location
uv run cairn migrate onx-to-caltopo ~/Downloads/onx-exports -o ./my-output
```

Cairn will:
1. Show you the GPX and KML files it found
2. Let you select which files to use
3. Display a summary of what will be created
4. Ask for confirmation before processing

The output files will be created in `<input-directory>/caltopo_ready/` by default.

### 3) Import into CalTopo

Import `./caltopo_ready/most_usable.json` into CalTopo using CalTopo's GeoJSON import.

---

## What Cairn writes (onX → CalTopo)

Cairn creates these files in the output directory:

- **`<name>.json`**: primary CalTopo-importable GeoJSON (deduped by default)
- **`<name>_dropped_shapes.json`**: everything that was removed by shape dedup (so nothing is lost)
- **`<name>_SUMMARY.md`**: human-readable explanation of dedup decisions
- **`<name>_trace.jsonl`** (enabled by default): machine-parseable trace events for debugging and replay

The base name defaults to your GPX filename (without extension), or you can specify it with `--name`.

---

## Why dedup exists (and what it means)

During this experiment I found cases where onX exports include many distinct objects (different IDs) with identical names and identical geometry. CalTopo will happily import them all, which can look like "duplicates everywhere".

By default, Cairn produces a **"most usable"** CalTopo file by:

- **preferring polygons** (from KML) over track/route representations (from GPX) when they refer to the same onX object
- **deduplicating shapes** using a fuzzy geometry match (rotation/direction tolerant, coordinate rounding tolerant)

Nothing is deleted permanently: every dropped duplicate is preserved in the secondary GeoJSON, and the summary explains the choices.

---

## Known quirks / blockers I ran into

- **onX export variance**: similar "linework" can export as `<trk>` vs `<rte>`. Areas/polygons often only appear as polygons in KML.
- **CalTopo's exported "GeoJSON" is CalTopo-flavored**: it may include extra properties and 4D coordinate arrays like `[lon, lat, ele, time]`. I treat this as normal normalization, not automatically a bug.
- **Standards aren't fully standard in practice**: GPX/KML/GeoJSON are interchange formats, but platform behavior still matters more than file validity.

If any of my assumptions are wrong, I want to know — the goal is a faithful migration, not "a file that happens to import".

---

## Challenges I found migrating from CalTopo → onX (secondary)

I still care about proving out migration in both directions, but in practice **CalTopo → onX** is harder to keep the  fidelity because of how onX behaves on import and in the UI.

Here are the blockers I ran into:

- **Ordering is not reliable after import**: even if I carefully write GPX/KML in a particular order, onX may re-order items in folders after import and there isn't a stable user-visible "sort by name" / "sort by import order" workflow that guarantees the same outcome every time.

- **Waypoints and tracks use the same base colors, but tracks have one extra**: OnX Backcountry waypoints support 10 colors, while tracks/lines support 11 colors. The first 10 colors are identical between waypoints and tracks. Tracks have one additional color (Fuchsia) that waypoints don't support.

  ### Waypoint Colors (10 Official Colors)

  OnX waypoints support exactly **10 specific RGBA values**. Any other color values may be ignored or normalized on import.

  **Note:** Tracks/lines use these exact same 10 colors, plus one additional color (Fuchsia).

| #  | Color Name   | RGBA Value           | RGB              | Hex                                                                                  |
|----|--------------|----------------------|------------------|--------------------------------------------------------------------------------------|
| 1  | Red-Orange   | `rgba(255,51,0,1)`   | RGB(255, 51, 0)  | ![brand-ff3300](https://readme-swatches.vercel.app/FF3300?style=square&size=20) `#FF3300` |
| 2  | Blue         | `rgba(8,122,255,1)`  | RGB(8, 122, 255) | ![brand-087aff](https://readme-swatches.vercel.app/087AFF?style=square&size=20) `#087AFF` |
| 3  | Cyan         | `rgba(0,255,255,1)`  | RGB(0, 255, 255) | ![brand-00ffff](https://readme-swatches.vercel.app/00FFFF?style=square&size=20) `#00FFFF` |
| 4  | Lime         | `rgba(132,212,0,1)`  | RGB(132, 212, 0) | ![brand-84d400](https://readme-swatches.vercel.app/84D400?style=square&size=20) `#84D400` |
| 5  | Black        | `rgba(0,0,0,1)`      | RGB(0, 0, 0)     | ![brand-000000](https://readme-swatches.vercel.app/000000?style=square&size=20) `#000000` |
| 6  | White        | `rgba(255,255,255,1)`| RGB(255, 255, 255)| ![brand-ffffff](https://readme-swatches.vercel.app/FFFFFF?style=square&size=20) `#FFFFFF` |
| 7  | Purple       | `rgba(128,0,128,1)`  | RGB(128, 0, 128) | ![brand-800080](https://readme-swatches.vercel.app/800080?style=square&size=20) `#800080` |
| 8  | Yellow       | `rgba(255,255,0,1)`  | RGB(255, 255, 0) | ![brand-ffff00](https://readme-swatches.vercel.app/FFFF00?style=square&size=20) `#FFFF00` |
| 9  | Red          | `rgba(255,0,0,1)`    | RGB(255, 0, 0)   | ![brand-ff0000](https://readme-swatches.vercel.app/FF0000?style=square&size=20) `#FF0000` |
| 10 | Brown        | `rgba(139,69,19,1)`  | RGB(139, 69, 19) | ![brand-8b4513](https://readme-swatches.vercel.app/8B4513?style=square&size=20) `#8B4513` |

  ### Track/Line Colors (11 Official Colors)

  **Tracks support 11 colors** (waypoints only support 10). The first 10 colors are **identical** to the waypoint colors above. Tracks have one additional color: Fuchsia.

| #  | Color Name   | RGBA Value           | RGB              | Hex                                                                                  | In Waypoints? |
|----|--------------|----------------------|------------------|--------------------------------------------------------------------------------------|---------------|
| 1  | Red-Orange   | `rgba(255,51,0,1)`   | RGB(255, 51, 0)  | ![brand-ff3300](https://readme-swatches.vercel.app/FF3300?style=square&size=20) `#FF3300` | ✅ Yes |
| 2  | Blue         | `rgba(8,122,255,1)`  | RGB(8, 122, 255) | ![brand-087aff](https://readme-swatches.vercel.app/087AFF?style=square&size=20) `#087AFF` | ✅ Yes |
| 3  | Cyan         | `rgba(0,255,255,1)`  | RGB(0, 255, 255) | ![brand-00ffff](https://readme-swatches.vercel.app/00FFFF?style=square&size=20) `#00FFFF` | ✅ Yes |
| 4  | Lime         | `rgba(132,212,0,1)`  | RGB(132, 212, 0) | ![brand-84d400](https://readme-swatches.vercel.app/84D400?style=square&size=20) `#84D400` | ✅ Yes |
| 5  | Black        | `rgba(0,0,0,1)`      | RGB(0, 0, 0)     | ![brand-000000](https://readme-swatches.vercel.app/000000?style=square&size=20) `#000000` | ✅ Yes |
| 6  | White        | `rgba(255,255,255,1)`| RGB(255, 255, 255)| ![brand-ffffff](https://readme-swatches.vercel.app/FFFFFF?style=square&size=20) `#FFFFFF` | ✅ Yes |
| 7  | Purple       | `rgba(128,0,128,1)`  | RGB(128, 0, 128) | ![brand-800080](https://readme-swatches.vercel.app/800080?style=square&size=20) `#800080` | ✅ Yes |
| 8  | Yellow       | `rgba(255,255,0,1)`  | RGB(255, 255, 0) | ![brand-ffff00](https://readme-swatches.vercel.app/FFFF00?style=square&size=20) `#FFFF00` | ✅ Yes |
| 9  | Red          | `rgba(255,0,0,1)`    | RGB(255, 0, 0)   | ![brand-ff0000](https://readme-swatches.vercel.app/FF0000?style=square&size=20) `#FF0000` | ✅ Yes |
| 10 | Brown        | `rgba(139,69,19,1)`  | RGB(139, 69, 19) | ![brand-8b4513](https://readme-swatches.vercel.app/8B4513?style=square&size=20) `#8B4513` | ✅ Yes |
| 11 | Fuchsia      | `rgba(255,0,255,1)`  | RGB(255, 0, 255) | ![brand-ff00ff](https://readme-swatches.vercel.app/FF00FF?style=square&size=20) `#FF00FF` | ❌ No (track-only) |

  ### Why Color Preservation Matters

  Color is a key filtering property in onX's "My Content" feature. When importing waypoints from CalTopo, having colors correctly mapped allows you to:
  - Filter large sets of imported waypoints by color
  - Organize and find waypoints quickly after import
  - Maintain your organizational system from CalTopo

  This makes color mapping especially important when migrating large datasets between platforms.

  ### Import Behavior

  **Tracks** ✅
  - All 11 colors are imported and preserved correctly
  - Colors can be manually changed in OnX UI
  - Must use one of the 11 official RGBA values listed above

  **Waypoints** ✅
  - All 10 colors are imported and preserved correctly
  - Colors can be manually changed in OnX UI
  - Must use one of the 10 official RGBA values listed above
  - Cannot use Fuchsia (track-only color)
  - OnX will assign the default ![brand-087aff](https://readme-swatches.vercel.app/087AFF?style=square&size=20) `#087AFF` blue color on import for non-matching values
  - After manual edit, OnX exports using the exact 10 waypoint colors

- **KML round-trip fidelity is limited**: styles, structure, and metadata may be reduced when moving through onX import/export cycles.

These constraints don't make the direction impossible — they just make it easier to lose "polish" compared to onX → CalTopo.

---

## Demo

There's a recorded CLI demo script at `demo.tape` using:

- `demo/onx-to-caltopo/onx-export/` (source exports)
- `demo/onx-to-caltopo/caltopo-ready/` (generated outputs)

---

## Advanced Options

The `migrate onx-to-caltopo` command supports several options:

- **`-o, --output-dir PATH`**: Custom output directory (default: `<input-dir>/caltopo_ready`)
- **`--name TEXT`**: Custom base name for output files (default: GPX filename)
- **`--dedupe-waypoints` / `--no-dedupe-waypoints`**: Enable/disable waypoint deduplication (default: enabled)
- **`--dedupe-shapes` / `--no-dedupe-shapes`**: Enable/disable shape deduplication (default: enabled)
- **`--trace` / `--no-trace`**: Enable/disable trace log generation (default: enabled)
- **`--trace-path PATH`**: Specify a custom path for the trace log file

Example with options:

```bash
uv run cairn migrate onx-to-caltopo ~/Downloads/onx-exports \
  -o ./output \
  --name my_custom_name \
  --no-dedupe-shapes \
  --trace-path ./debug/trace.jsonl
```

---

## CalTopo → onX

Cairn also supports migrating from CalTopo to onX Backcountry. This direction is more experimental due to onX's import behavior (see "Challenges" section above), but the workflow is similar to onX → CalTopo.

### Quick start

Export your map from CalTopo as GeoJSON, then:

```bash
# Interactive mode - will prompt for directory and let you select file
uv run cairn migrate caltopo-to-onx

# Or specify the directory directly
uv run cairn migrate caltopo-to-onx ~/Downloads/caltopo-exports

# With custom output location
uv run cairn migrate caltopo-to-onx ~/Downloads/caltopo-exports -o ./output
```

Cairn will:
1. Show you the GeoJSON files it found
2. Let you select which file to convert
3. Display a summary of the content (folders, waypoints, tracks, shapes)
4. Ask for confirmation before processing
5. Create GPX files (for waypoints and tracks) and KML files (for polygons/areas)

The output files will be created in `<input-directory>/onx_ready/` by default.

### What gets created

- **GPX files**: One per folder, containing waypoints or tracks
- **KML files**: One per folder, containing shapes/polygons
- **Summary files**: If icon name prefixes are enabled in config

### Options

- **`-o, --output-dir PATH`**: Custom output directory (default: `<input-dir>/onx_ready`)
- **`-c, --config PATH`**: Custom icon mapping configuration file
- **`--no-sort`**: Preserve original order instead of natural sorting (default: sorts naturally)

### Icon mapping

CalTopo symbols are automatically mapped to onX icons using `cairn_config.yaml`. You can customize these mappings or use a custom config file with `--config`.

### Note about ordering

By default, Cairn sorts items using natural sort order (e.g., "01", "02", "10" instead of "01", "10", "02") which helps with logical organization in onX. However, onX may still reorder items after import based on its own logic.

---

## Development

### Running tests

```bash
uv run --with pytest pytest -q
```

---

## License

MIT License - see [LICENSE](LICENSE)
