# Cairn

**The CalTopo to onX Backcountry Migration Tool**

Cairn converts CalTopo GeoJSON exports into onX Backcountry-compatible GPX/KML files with intelligent icon mapping, natural sorting, and a beautiful terminal UI.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Basic Conversion](#basic-conversion)
  - [Preview Mode](#preview-mode)
  - [Review Mode](#review-mode)
  - [CLI Options](#cli-options)
- [Icon Mapping](#icon-mapping)
  - [How It Works](#how-it-works)
  - [Icon Reference Table](#icon-reference-table)
  - [Available onX Icons](#available-onx-icons)
- [Configuration](#configuration)
  - [Config File Location](#config-file-location)
  - [Config Structure](#config-structure)
  - [Symbol Mappings](#symbol-mappings)
  - [Keyword Mappings](#keyword-mappings)
  - [Adding Custom Mappings](#adding-custom-mappings)
  - [Config Commands](#config-commands)
- [Output Files](#output-files)
- [onX GPX Extensions](#onx-gpx-extensions)
- [Sorting and Preview](#sorting-and-preview)
- [Importing to onX](#importing-to-onx)
- [Limitations](#limitations)
- [Development](#development)

---

## Features

- **Intelligent Icon Mapping** - Two-tier system: CalTopo symbols → onX icons, then keyword matching
- **Natural Sorting** - Items sorted in human-friendly order (01, 02... 10, 11)
- **Visual Preview** - See sorted order with color squares and icon emojis before export
- **Color & Style Preservation** - Track colors, line styles (solid/dash/dot), and weights
- **YAML Configuration** - User-editable config with inline comments
- **Unmapped Symbol Detection** - Reports CalTopo symbols needing mapping
- **Auto-Splitting** - Handles large datasets by splitting at onX's 3,000 item limit
- **Folder Support** - Preserves CalTopo folder structure
- **Interactive Review** - Review and adjust icon mappings before conversion

---

## Installation

```bash
git clone https://github.com/yourusername/cairn.git
cd cairn
uv sync
```

**Requirements:** Python 3.9+

---

## Quick Start

```bash
# Convert a CalTopo export
uv run cairn convert my_map.json

# Preview without creating files
uv run cairn convert my_map.json --dry-run

# Export a config template
uv run cairn config export
```

---

## Usage

### Basic Conversion

```bash
uv run cairn convert INPUT_FILE.json
```

### Preview Mode

See what will be created without making files:

```bash
uv run cairn convert INPUT_FILE.json --dry-run
```

Shows: icon distribution, unmapped symbols, files to be created.

### Review Mode

Interactively review and adjust icon mappings:

```bash
uv run cairn convert INPUT_FILE.json --review
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview without creating files |
| `--review` | Interactive icon mapping review |
| `--yes` | Skip confirmation prompts |
| `--no-sort` | Preserve original CalTopo order |
| `--output DIR` | Specify output directory |
| `--config FILE` | Use custom config file |

```bash
# Examples
uv run cairn convert map.json --output ./onx_ready
uv run cairn convert map.json --config my_config.yaml
uv run cairn convert map.json --yes --no-sort  # Fully automated
```

---

## Icon Mapping

### How It Works

```
CalTopo Waypoint
       │
       ▼
┌──────────────────┐
│ 1. Symbol Match  │ ← Checks "marker-symbol" field (e.g., "skull" → Hazard)
└────────┬─────────┘
         │ No match?
         ▼
┌──────────────────┐
│ 2. Keyword Match │ ← Searches title/description (e.g., "avalanche" → Hazard)
└────────┬─────────┘
         │ No match?
         ▼
┌──────────────────┐
│ 3. Default Icon  │ ← Falls back to "Location" (blue pin)
└──────────────────┘
```

### Icon Reference Table

| CalTopo Symbol | onX Icon | Visual | Color |
|----------------|----------|--------|-------|
| `skull`, `danger`, `warning` | Hazard | ⚠️ | Red |
| `tent`, `camp`, `campsite` | Campsite | ⛺ | Orange |
| `water`, `spring`, `creek` | Water Source | 💧 | Cyan |
| `car`, `parking`, `lot` | Parking | 🅿️ | Gray |
| `trailhead`, `trail` | Trailhead | 🥾 | Green |
| `ski`, `skiing`, `xc-skiing` | XC Skiing | ⛷️ | White |
| `summit`, `peak`, `mountain` | Summit | 🏔️ | Red |
| `camera`, `photo` | Photo | 📷 | Yellow |
| `viewpoint`, `vista` | View | 👁️ | Yellow |
| `cabin`, `hut`, `yurt` | Cabin | 🏠 | Brown |
| *(default)* | Location | 📍 | Blue |

### Available onX Icons

Run `uv run cairn icon list` to see all 100+ icons organized by category:

**Camping:** Campsite, Camp, Camp Backcountry, Campground
**Water:** Water Source, Waterfall, Hot Spring, Potable Water
**Winter:** XC Skiing, Ski Touring, Ski, Skin Track, Snowboarder
**Transportation:** Parking, Trailhead, 4x4, ATV
**Terrain:** Summit, Cave, Couloir, Cornice
**Hazards:** Hazard, Barrier
**Observation:** Photo, View, Lookout
**Facilities:** Cabin, Shelter, Food Source

---

## Configuration

### Config File Location

Cairn looks for `cairn_config.yaml` in the current directory, or specify one:

```bash
uv run cairn convert input.json --config my_config.yaml
```

### Config Structure

```yaml
# cairn_config.yaml

# Add icon type prefix to names (e.g., "Hazard - Avalanche Zone")
use_icon_name_prefix: false

# Report unmapped symbols after conversion
enable_unmapped_detection: true

# CalTopo symbol → onX icon mappings
symbol_mappings:
  skull: Hazard
  tent: Campsite
  water: Water Source
  car: Parking

# Keyword fallback mappings (searched in title/description)
keyword_mappings:
  Hazard: [danger, avy, avalanche, caution]
  Campsite: [tent, camp, sleep, overnight]
  Water Source: [water, spring, creek, refill]
```

### Symbol Mappings

Symbol mappings have **highest priority**. They match the CalTopo `marker-symbol` field:

```yaml
symbol_mappings:
  skull: Hazard        # CalTopo skull icon → onX Hazard
  my-custom: Summit    # Your custom symbol → onX Summit
```

### Keyword Mappings

Keyword mappings are the **fallback** when no symbol matches. They search waypoint titles and descriptions:

```yaml
keyword_mappings:
  Hazard: [danger, avalanche, avy, slide]
  Campsite: [tent, camp, sleep, bivy]
  Water Source: [water, spring, creek, stream]
```

### Adding Custom Mappings

1. **Run conversion** to find unmapped symbols:
   ```bash
   uv run cairn convert my_map.json
   ```

2. **Check the report** for unmapped symbols:
   ```
   ⚠️  Found 2 unmapped CalTopo symbol(s):
   │ Symbol     │ Count │ Example Waypoint    │
   │ my-marker  │    12 │ Start/Finish Line   │
   │ circle-x   │     8 │ Aid Station 1       │

   💡 Add these to cairn_config.yaml
   ```

3. **Add to config**:
   ```yaml
   symbol_mappings:
     my-marker: Location
     circle-x: Food Source
   ```

4. **Re-run conversion**.

### Config Commands

```bash
# Export a config template
uv run cairn config export

# Show current configuration
uv run cairn config show

# Validate a config file
uv run cairn config validate my_config.yaml

# Set default icon for unmapped symbols
uv run cairn config set-default-icon "Campsite"

# Set default color
uv run cairn config set-default-color "rgba(255,0,0,1)"

# List all available onX icons
uv run cairn icon list

# Map a symbol via CLI
uv run cairn icon map "my-symbol" "Summit"
```

---

## Output Files

Cairn generates separate files for each feature type:

| File Pattern | Content |
|--------------|---------|
| `FolderName_Waypoints.gpx` | Point markers |
| `FolderName_Tracks.gpx` | Lines/routes |
| `FolderName_Shapes.kml` | Polygons (KML, since GPX doesn't support polygons) |

For large datasets (3,000+ items), files are automatically split:
- `FolderName_Waypoints_Part1.gpx`
- `FolderName_Waypoints_Part2.gpx`

---

## onX GPX Extensions

Cairn uses GPX with onX's custom namespace to preserve icons, colors, and styles:

```xml
<wpt lat="45.123" lon="-114.456">
  <name>Trailhead parking</name>
  <extensions>
    <onx:icon>Parking</onx:icon>
    <onx:color>rgba(128,128,128,1)</onx:color>
  </extensions>
</wpt>

<trk>
  <name>Trail Section 01</name>
  <extensions>
    <onx:color>rgba(255,0,0,1)</onx:color>
    <onx:style>dash</onx:style>
    <onx:weight>4.0</onx:weight>
  </extensions>
</trk>
```

| Element | Extension | Values |
|---------|-----------|--------|
| Waypoint | `onx:icon` | Location, Campsite, Hazard, etc. |
| Waypoint/Track | `onx:color` | `rgba(r,g,b,1)` |
| Track | `onx:style` | `solid`, `dash`, `dot` |
| Track | `onx:weight` | `4.0` (standard), `6.0` (thick) |

---

## Sorting and Preview

### Natural Sorting

Cairn sorts items in human-friendly order:

| Original | Sorted |
|----------|--------|
| 01, 07, 04, 02, 10 | 01, 02, 04, 07, 10 |
| Item 2, Item 10, Item 1 | Item 1, Item 2, Item 10 |

**Why this matters:** onX doesn't allow reordering after import.

### Visual Preview

Before exporting, Cairn shows a preview:

```
Sorted Tracks (11)
────────────────────────────────────────
  1. ■ 01 - Start to Juniper Ridge
  2. ■ 02 - Juniper Ridge to Sunrise Peak
  3. ■ 03 - Sunrise Peak to Dark Creek

Sorted Waypoints (9)
────────────────────────────────────────
  1. 📍 01 - Start/Finish
  2. 💧 02 - Water Source
  3. 🥾 03 - Trailhead
```

Use `--no-sort` to preserve original CalTopo order.

---

## Importing to onX

1. Run Cairn: `uv run cairn convert myfile.json`
2. Go to [onX Backcountry Web Map](https://www.onxmaps.com/backcountry/app)
3. Click **Import**
4. Drag and drop the generated GPX/KML files
5. Your waypoints appear with correct icons!

---

## Limitations

- **No reordering in onX** - Items appear in import order (Cairn sorts automatically)
- **3,000 item limit** - onX limit per file (Cairn auto-splits)
- **4MB file limit** - onX Web Map limit (Cairn splits conservatively)
- **Plain text only** - HTML descriptions converted to plain text
- **9 colors** - Track colors mapped to closest onX palette color
- **3 line styles** - `solid`, `dash`, `dot` only

---

## Development

### Running Tests

```bash
uv run pytest -v
```

### Project Structure

```
cairn/
├── cli.py              # CLI entry point
├── commands/
│   ├── convert_cmd.py  # Convert command
│   ├── config_cmd.py   # Config management
│   └── icon_cmd.py     # Icon management
├── core/
│   ├── parser.py       # GeoJSON parsing
│   ├── mapper.py       # Icon mapping
│   ├── config.py       # Configuration
│   └── writers.py      # GPX/KML generation
└── utils/
    └── utils.py        # Helpers
```

---

## License

MIT License - see [LICENSE](LICENSE)

---

**Happy trails!** 🥾
