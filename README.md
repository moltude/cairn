# Cairn

## This is a work in progress

### Why?

I'm an advocate for open data and being able to exchange map data between platforms. GPX/KML/GeoJSON are meant to be platform-agnostic interchange formats (or at least that's how I understand them). Cairn is my attempt to make that promise feel real for backcountry mapping: move between OnX and CalTopo while taking *all the map customization with you* (icons, colors, notes, and organization), not just raw shapes.

This tool started as an experiment and it surfaced a number of challenges. I'm not an expert — if my assumptions are wrong, I want to find out and correct them. The goal is a faithful migration, not "a file that happens to import."

### So what?

In theory, these formats should make it easy to move between map platforms. In practice, platforms tend to:

- supports only a subset of each format
- adds non-standard fields or extensions
- rewrites data during import/export (sometimes subtly)

I built Cairn to make migration between systems easier *without losing the customization that makes a map valuable* (names, notes, colors, icons, and organizational intent) — not just the raw shapes. I have only developed this for **OnX Backcountry** and **CalTopo** but there are other platform out there.

### Story

*Heard you were heading up my way, here is a GPX file with some choice spots!*
[cool-spots.gpx](cool-spots.gpx)

That GPX file contains details of an area and lois of information, hiking and backpacking routes, great rocking climbing, a cool tower and fishing spots. There are important waypoints that indicate hazards,  water sources and approaches. When they constructed this dataset they took the time to assign colors, icons and other metadata beyond the lines, dots and polygons to help you and others make the most of this map.

This is what they built 😍
---
![good onx](demo/bitterroots/hd-onx.png)

Or maybe this
![good caltopo](demo/bitterroots/hd-caltopo.png)

🤬 **But this is what you got when you tired to use it** 🤬
---
Sure it will work but it has a lot value while passing through the pipes and there is some garbage thrown in as a nice cherry on top.

![bad onx](demo/bitterroots/export-from-caltopo-into-onx-poor.png)

Be sure to swing by and checkout the awesome cool `Import track markup` after visiting the the **Very cool tower** 🤘!
![bad caltopo](demo/bitterroots/export-from-onx-import-into-caltopo-poor.png)


The data isn't lost, it jsut didn't make it from the file into the mapping software and that is were Cairn comes in. This tool tries to take as much of that data as possible and make sure it finds its way into the map.

---

## Known quirks, blockers and things I learned along the way

*If any of my assumptions are wrong, I want to know — the goal is a faithful migration.*

- **OnX export variance**: similar "linework" can export as `<trk>` vs `<rte>`. Areas/polygons often only appear as polygons in KML.
- **CalTopo's exported "GeoJSON" is CalTopo-flavored**: it may include extra properties and 4D coordinate arrays like `[lon, lat, ele, time]`. I treat this as normal normalization, not automatically a bug.
- **Standards aren't fully standard in practice**: GPX/KML/GeoJSON are interchange formats, but platform behavior still matters more than file validity.

- **Ordering is not reliable after import**: even if I carefully write GPX/KML in a particular order, OnX may re-order items in folders after import and there isn't a stable user-visible "sort by name" / "sort by import order" workflow that guarantees the same outcome every time.

- **Waypoints and tracks use the same base colors, but tracks have one extra**: OnX waypoints support 10 colors, while tracks/lines support 11 colors. The first 10 colors are identical between waypoints and tracks. Tracks have one additional color (Fuchsia) that waypoints don't support.

  ### OnX Waypoint Colors (10 Official Colors)

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

  Color is a key filtering property in OnX's "My Content" feature. When importing waypoints from CalTopo, having colors correctly mapped allows you to:
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

### Dedupping

During this experiment I found cases where OnX exports include many distinct objects (different IDs) with identical names and identical geometry. CalTopo will happily import them all, which can look like "duplicates everywhere".

By default, Cairn produces a **"most usable"** CalTopo file by:

- **preferring polygons** (from KML) over track/route representations (from GPX) when they refer to the same OnX object
- **deduplicating shapes** using a fuzzy geometry match (rotation/direction tolerant, coordinate rounding tolerant)

Nothing is deleted permanently: every dropped duplicate is preserved in the secondary GeoJSON.

### Running tests

```bash
uv run --with pytest pytest -q
```

---

## License

MIT License - see [LICENSE](LICENSE)
