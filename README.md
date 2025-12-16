# Cairn

**Work in progress, buyer beware.**

### Why?

I'm an advocate for open data and being able to exchange map data between platforms. GPX/KML/GeoJSON are meant to be platform-agnostic interchange formats (or at least that's how I understand them). Cairn is my attempt to make that promise feel real for backcountry mapping: move between OnX and CalTopo while taking *all the map customization with you* (icons, colors, notes, and organization), not just raw shapes.

This tool started as an experiment and it surfaced a number of challenges. I'm not an expert — if my assumptions are wrong, I want to find out and correct them. The goal is a faithful migration, not "a file that happens to import."

### So what?

In theory, these formats should make it easy to move between map platforms. In practice, platforms tend to:

- support only a subset of each format
- add non-standard fields or extensions
- rewrite data during import/export (sometimes subtly)

I built Cairn to make migration between systems easier *without losing the customization that makes a map valuable* (names, notes, colors, icons, and organizational intent) — not just the raw shapes. I have only developed this for **OnX Backcountry** and **CalTopo** but there are other platforms out there.

### Story

*Heard you were heading up my way, here is a GPX file with some choice spots!*
[cool-spots.gpx](cool-spots.gpx)

That GPX file contains details of an area and lots of information, hiking and backpacking routes, great rock climbing, a cool tower and fishing spots. There are important waypoints that indicate hazards, water sources and approaches. When they constructed this dataset they took the time to assign colors, icons and other metadata beyond the lines, dots and polygons to help you and others make the most of this map.

This is what they built 😍
---
<!-- ![good onx](demo/bitterroots/hd-onx.png) -->
<img src="./docs/screenshots/hd-onx.png" alt="Alt text" style="width:75%; height:auto;">

Or maybe this
<!-- ![good caltopo](demo/bitterroots/hd-caltopo.png) -->
<img src="./docs/screenshots/hd-caltopo.png" alt="Alt text" style="width:75%; height:auto;">


🤬 **But this is what you got when you tried to use it** 🤬
---
Sure it will work but it lost a lot of value while passing through the pipes and there is some garbage thrown in as a nice cherry on top. The data isn't lost, it just didn't make it from the GPX file into the mapping software. That is where Cairn comes in, it takes as much of that data as possible and drops it into your map.

<!-- ![bad onx](demo/bitterroots/export-from-caltopo-into-onx-poor.png) -->
<img src="./docs/screenshots/export-from-caltopo-into-onx-poor.png" alt="Alt text" style="width:75%; height:auto;">

Be sure to swing by and checkout the awesome cool `Import track markup` after visiting the **Very cool tower** 🤘!
<!-- ![bad caltopo](demo/bitterroots/export-from-onx-import-into-caltopo-poor.png) -->
<img src="./docs/screenshots/export-from-onx-import-into-caltopo-poor.png" alt="Alt text" style="width:75%; height:auto;">
---

## Installation

```shell
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/moltude/cairn.git
cd cairn

uv sync # Or if that fails then 'uv pip install -e .'

# cairn is available
cairn --help

# To run directly
uv run cairn
```

## Quick start

### CalTopo --> OnX

```shell
cairn migrate onx ~/Downloads/my-caltopo-map.json
```

Cairn will guide you through:
- Selecting which file to convert
- Previewing waypoints with their icons/colors
- Editing any waypoints before export
- Handling unmapped icons

Output goes to `onx_ready/` folder (GPX for waypoints/tracks, KML for polygons).

### OnX --> CalTopo

```shell
cairn migrate caltopo ~/Downloads/my-onx-exports/
```

Cairn will:
- Find your GPX and KML files
- Merge them (preferring polygons)
- Deduplicate shapes automatically
- Generate CalTopo-ready GeoJSON

Output goes to `caltopo_ready/` folder.

## Icon, Symbol and Color Mapping

The real value of Cairn is migrating the colors, icons, names and descriptions from one place to another. Cairn solves this challenge by allowing users to preview and edit all of that data ahead of time.

### Why is icon and color mapping important for OnX?

OnX supports discovery by searching across everything or within a specific content type. However, the only way to filter is by **Color** and **Icon** for waypoints.

Color is a key filtering property in OnX's "My Content" feature. When importing waypoints from CalTopo, having colors correctly mapped allows you to:
- Filter large sets of imported waypoints by color and icon
- Quickly find waypoints by combining text + filtering
- Maintain an organizational structure

OnX only allows specific colors and icon terms to be used.

See the tables below for the allowed OnX colors. If the data you want to import provides color information, Cairn will convert it to the closest OnX color. If no color is provided then OnX will use the default blue.

For icons and symbols, OnX accepts a set of ~40 icons but CalTopo exports a much larger set. Even when the icons are visually identical the text labels used may not match and the icon doesn't transfer. When the icon does not match in OnX the default <img src="./docs/screenshots/onx-logo.png" alt="Alt text" height=15px> will be used.


Cairn maintains a default mapping of common CalTopo --> OnX icons, and it will warn you when it sees an icon it can't map.

Example warning output:

```shell
⚠️  Found 3 unmapped CalTopo symbol(s):

Symbol      Count  Example Waypoint
climbing-2  3      Main Wall - Lost horse canyon
circle-p    1      Parking- Main Wall and Starlight Lounge
climbing-1  1      Pullout boulders

💡 Add these to your config (default: cairn_config.yaml) to map them to OnX icons
   Run 'cairn config export' to create a template
   Run 'cairn config show' to see valid OnX icons already used in your mappings
```

To permanently map `climbing-1` to the OnX climber icon, add this to your `cairn_config.yaml`:

```yaml
symbol_mappings:
  climbing-1: Climbing
```

## Configuration

Cairn uses `cairn_config.yaml` to store custom icon mappings and preferences.

### Structure

```yaml
symbol_mappings:
  # CalTopo symbol → OnX icon name
  climbing-1: Climbing
  climbing-2: Climbing
  campsite-1: Campground
  circle-p: Parking

# Add more mappings as you encounter unmapped symbols
```

### Commands

```shell
# See what's in your current config (shows active mappings)
cairn config show

# Generate a template config file in your current directory
cairn config export

# Validate your config file
cairn config validate cairn_config.yaml
```

## Color reference

There are 10(ish) official OnX colors. Waypoints support **10** colors and Tracks/Lines support **11**, all of the previous 10 plus Fuchsia.

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

## Known quirks, blockers and things I learned along the way

*If any of my assumptions are wrong, I want to know — the goal is a faithful migration.*

- **OnX export variance**: similar "linework" can export as `<trk>` vs `<rte>`. Areas/polygons often only appear as polygons in KML.
- **CalTopo's exported "GeoJSON" is CalTopo-flavored**: it may include extra properties and 4D coordinate arrays like `[lon, lat, ele, time]`. I treat this as normal normalization, not automatically a bug.
- **Standards aren't fully standard in practice**: GPX/KML/GeoJSON are interchange formats, but platform behavior still matters more than file validity.

- **Ordering is not reliable after import**: even if I carefully write GPX/KML in a particular order, OnX may re-order items in folders after import and there isn't a stable user-visible "sort by name" / "sort by import order" workflow that guarantees the same outcome every time.

- **Waypoints and tracks use the same base colors, but tracks have one extra**: OnX waypoints support 10 colors, while tracks/lines support 11 colors. The first 10 colors are identical between waypoints and tracks. Tracks have one additional color (Fuchsia) that waypoints don't support.

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

### Chaos demo

If you want to *watch* a full CalTopo → OnX migration run (including intentional bad inputs to exercise error handling, bulk edits, and re-editing a folder) without interacting, run the included replay script:

```bash
./scripts/run_chaos_demo.sh
```

This runs `cairn migrate onx` against `demo/bitterroots/` and writes outputs to `demo/bitterroots/onx_ready_chaos_watch/` by default.

## License

MIT License - see [LICENSE](LICENSE)
