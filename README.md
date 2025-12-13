# Cairn 🏔️

**The CalTopo to onX Backcountry Migration Tool**

Cairn is a Python CLI tool that converts CalTopo GeoJSON exports into onX Backcountry-compatible GPX and KML files. It intelligently maps icons, handles large datasets with auto-splitting, and provides a beautiful terminal UI.

**Mixed Format Strategy:** Cairn uses GPX with onX's custom namespace extensions (`xmlns:onx="https://wwww.onxmaps.com/"`) for waypoints and tracks, ensuring proper icon and color preservation. Shapes (polygons) use KML format as GPX doesn't support polygons well.

## Features

✨ **Intelligent Icon Mapping** - Two-tier system: CalTopo symbols → onX icons, then keyword matching

⚙️ **Customizable Configuration** - User-editable JSON config for custom icon mappings and name prefix options

🔍 **Unmapped Symbol Detection** - Reports CalTopo symbols that need mapping configuration

📦 **Auto-Splitting** - Handles large datasets by automatically splitting files that exceed onX's 3,000 item limit

📁 **Folder Support** - Preserves CalTopo folder structure and organizes output files accordingly

🗺️ **onX Namespace Extensions** - Uses GPX with onX's custom `<onx:icon>` and `<onx:color>` extensions for proper icon preservation

📝 **Optional Icon Prefixes** - Configurable option to add icon type prefixes to waypoint names (e.g., "Parking - Trailhead")

👁️ **Dry-Run Preview** - Preview conversion results without creating files (`--dry-run`)

🔧 **Interactive Review** - Review and adjust icon mappings before conversion (`--review`)

🎯 **Default Icon/Color Management** - Set custom defaults for unmapped symbols via config command

## Demo

See Cairn in action ([made with VHS](https://github.com/charmbracelet/vhs)):

![Made with VHS](https://vhs.charm.sh/vhs-44gEeUfxctwPwDRbC4mT6Z.gif)




## Installation

Clone the repository and install using [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/yourusername/cairn.git
cd cairn
uv sync
```
### Requirements

- Python 3.9 or higher
- Dependencies: `typer`, `rich` (automatically installed)

## Usage

All commands use `uv run` to execute within the project environment:

### Convert Command

Convert a CalTopo GeoJSON export to onX format:

```bash
uv run cairn convert INPUT_FILE.json
```

### Preview Before Converting (Dry-Run)

```bash
uv run cairn convert INPUT_FILE.json --dry-run
```

Shows what files will be created, icon distribution, and unmapped symbols without creating any files.

### Interactive Review Mode

```bash
uv run cairn convert INPUT_FILE.json --review
```

Review and adjust icon mappings interactively before conversion.

### Specify Output Directory

```bash
uv run cairn convert INPUT_FILE.json --output ./my_onx_files
```

### Use Custom Configuration

```bash
uv run cairn convert INPUT_FILE.json --config my_config.json
```

### Configuration Management

```bash
# Show current configuration
uv run cairn config show

# Export configuration template
uv run cairn config export

# Set default icon for unmapped symbols
uv run cairn config set-default-icon "Campsite"

# Set default color
uv run cairn config set-default-color "rgba(255,0,0,1)"

# Validate a config file
uv run cairn config validate my_config.json
```

### Icon Management

```bash
# List all available onX icons
uv run cairn icon list

# Map a CalTopo symbol to an onX icon
uv run cairn icon map "marker-campsite" "Campsite"

# Show current mapping for a symbol
uv run cairn icon show "marker-campsite"

# Remove a symbol mapping
uv run cairn icon unmap "marker-campsite"
```

### Example

```bash
uv run cairn convert Olympic_Mtn_100k.json --output ./onx_ready
```

## How It Works

1. **Parse** - Reads your CalTopo GeoJSON export and organizes features by folder and type
2. **Map** - Intelligently maps CalTopo icons to onX Backcountry icon IDs using symbol and keyword matching
3. **Split** - Automatically chunks large datasets to respect onX's limits
4. **Export** - Generates GPX files with onX namespace extensions for waypoints/tracks, and KML files for shapes

## Icon Mapping

Cairn uses a two-tier system to map CalTopo markers to onX Backcountry icons:

### 1. Symbol Mapping (Priority)
Cairn first checks the CalTopo `marker-symbol` field (e.g., skull → Hazard ⚠️)

### 2. Keyword Mapping (Fallback)
If no symbol match, searches keywords in titles and descriptions:

| Keywords | onX Icon |
|----------|----------|
| tent, camp, sleep, overnight | Campsite ⛺ |
| water, spring, refill, creek | Water Source 💧 |
| car, parking, trailhead, lot | Parking 🅿️ |
| ski, skin, tour, uptrack | Skiing ⛷️ |
| summit, peak, top, mt | Summit 🏔️ |
| danger, avy, avalanche, slide | Caution ⚠️ |
| camera, photo, view | Photo 📷 |
| cabin, hut, yurt | Cabin 🏠 |

If no match found, defaults to "Waypoint" 📍

### Customization

Cairn stores configuration in `~/.cairn/config.json`. Create and customize your icon mappings:

```bash
uv run cairn config export  # Create template in current directory
# Edit cairn_config.json with your custom mappings
# Then copy to ~/.cairn/config.json or use --config flag
uv run cairn convert INPUT.json --config cairn_config.json
```

You can also manage mappings directly via CLI:

```bash
uv run cairn icon map "marker-campsite" "Campsite"
uv run cairn config set-default-icon "Location"
```

See [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration guide.

## onX Namespace Extensions

Cairn uses GPX format with onX's custom namespace extensions to properly preserve icon and color data:

```xml
<gpx xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:onx="https://wwww.onxmaps.com/">
  <wpt lat="45.123" lon="-114.456">
    <name>Trailhead parking</name>
    <desc>Main access point</desc>
    <extensions>
      <onx:icon>Parking</onx:icon>
      <onx:color>rgba(128, 128, 128, 1)</onx:color>
    </extensions>
  </wpt>
</gpx>
```

**Note:** The onX namespace URL has 4 'w's (`wwww`) - this is required by onX's import parser.

## Optional Icon Name Prefixes

By default, Cairn generates clean waypoint names. However, you can optionally enable icon type prefixes in waypoint names for easier manual icon setting in onX.

### Configuration

Set `use_icon_name_prefix` to `true` in `cairn_config.json`:

```json
{
  "use_icon_name_prefix": true
}
```

### With Prefixes Enabled

| Original Name | Mapped Icon | Final Name |
|--------------|-------------|------------|
| Parking for trailhead | Parking | `Parking - Parking for trailhead` |
| Avy hazard area | Caution | `Caution - Avy hazard area` |
| Base camp | Campsite | `Campsite - Base camp` |
| Cool summit | Waypoint | `Cool summit` (no prefix for default) |

### Summary Files

When icon prefixes are enabled, Cairn generates a `_SUMMARY.txt` file for each waypoint GPX file, organizing waypoints by icon type:

**Example: `Trapper_area_Waypoints_SUMMARY.txt`**
```
======================================================================
WAYPOINT ICON REFERENCE: Trapper area
======================================================================

Total Waypoints: 68
Icon Types: 8

CAMPSITE (5 waypoints)
----------------------------------------------------------------------
  • Campsite - Camp spot
  • Campsite - Decent camp site
  ...

CAUTION (3 waypoints)
----------------------------------------------------------------------
  • Caution - Avy hazard area
  • Caution - Avy debris
  ...

WAYPOINT (32 waypoints)
----------------------------------------------------------------------
  • Cool ridge line traverse
  • Main Wall- Lost horse canyon
  ...
```

This is useful if onX's GPX import doesn't properly recognize the custom namespace extensions.

## Output Files

Cairn generates separate files for different feature types:

- **`FolderName_Waypoints.gpx`** - Point markers with onX namespace extensions
- **`FolderName_Waypoints_SUMMARY.txt`** - Icon reference guide (only if `use_icon_name_prefix` is true)
- **`FolderName_Tracks.gpx`** - Line/route features
- **`FolderName_Shapes.kml`** - Polygon/area features (KML used as GPX doesn't support polygons well)

For large datasets exceeding 3,000 items, files are automatically split:
- `FolderName_Waypoints_Part1.gpx` (+ optional `_SUMMARY.txt`)
- `FolderName_Waypoints_Part2.gpx` (+ optional `_SUMMARY.txt`)
- etc.

## Configuration

Cairn supports customizable icon mappings through a JSON configuration file.

### Quick Start

1. **Export template:**
   ```bash
   uv run cairn config export
   ```

2. **Edit `cairn_config.json`:**
   ```json
   {
     "symbol_mappings": {
       "skull": "Danger",
       "tent": "Campsite"
     }
   }
   ```

3. **Use your config:**
   ```bash
   uv run cairn convert INPUT.json
   ```

### Unmapped Symbol Detection

Cairn automatically detects CalTopo symbols that don't have mappings:

```
⚠️  Found 2 unmapped CalTopo symbol(s):
┌──────────┬───────┬─────────────────────────┐
│ Symbol   │ Count │ Example Waypoint        │
├──────────┼───────┼─────────────────────────┤
│ circle-s │    12 │ Start/Finish Line       │
│ skull    │     3 │ Avy hazard area         │
└──────────┴───────┴─────────────────────────┘

💡 Add these to cairn_config.json to map them to onX icons
```

Add unmapped symbols to your config for better icon mapping on future conversions.

**For detailed configuration options, see [CONFIGURATION.md](CONFIGURATION.md)**

## Preview and Review Features

### Dry-Run Mode

Preview conversion results without creating any files:

```bash
uv run cairn convert INPUT.json --dry-run
```

**Shows:**
- Summary statistics (waypoint/track/shape counts)
- Icon distribution breakdown with percentages
- Unmapped symbols with examples
- List of files that would be created

**Benefits:**
- Verify icon mappings before conversion
- Identify unmapped symbols early
- No file system changes

### Interactive Review Mode

Review and adjust icon mappings interactively:

```bash
uv run cairn convert INPUT.json --review
```

**Features:**
- Groups waypoints by assigned icon
- Shows sample waypoints for each icon
- Interactively change icon mappings
- Saves changes to configuration
- Automatic re-parsing with new mappings

### Enhanced Config Management

```bash
# List all 100+ onX icons organized by category
uv run cairn icon list

# Set default icon for unmapped symbols
uv run cairn config set-default-icon "Campsite"

# Set default color
uv run cairn config set-default-color "rgba(255,0,0,1)"
```

**For complete details, see [PREVIEW_AND_CONFIG_FEATURES.md](PREVIEW_AND_CONFIG_FEATURES.md)**

## Importing to onX Backcountry

1. Run Cairn to convert your CalTopo export: `uv run cairn convert myfile.json`
2. Go to [onX Backcountry Web Map](https://www.onxmaps.com/backcountry/app)
3. Click **Import** in the menu
4. Drag and drop the generated GPX/KML files
5. Your waypoints will appear with the correct icons! 🎉

## File Structure

```
cairn/
├── cli.py              # CLI entry point
├── __init__.py         # Package initialization
├── commands/
│   ├── convert_cmd.py  # Convert command
│   ├── config_cmd.py   # Config management
│   └── icon_cmd.py     # Icon management
├── core/
│   ├── parser.py       # GeoJSON parsing
│   ├── mapper.py       # Icon mapping rules
│   ├── matcher.py      # Symbol/keyword matching
│   ├── writers.py      # GPX/KML file generation
│   ├── config.py       # Configuration handling
│   └── preview.py      # Dry-run preview
└── utils/
    └── utils.py        # Helper functions
```

## Development

### Running Tests

```bash
uv run pytest -v
```

### Requirements

- Python 3.9+
- typer
- rich

## Limitations

- onX Backcountry has a 3,000 item limit per file (Cairn handles this automatically)
- onX Web Map can crash with files > 4MB (Cairn splits files conservatively at 2,500 items)
- CalTopo HTML descriptions are converted to plain text for onX compatibility

## Example Output

```
╭────────────────────────────────╮
│    CAIRN v1.0.0                │
│    The CalTopo → onX Bridge    │
╰────────────────────────────────╯

📂 Input file: Olympic_Mtn_100k.json
   Size: 234.9 KB

⠋ Parsing GeoJSON...  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%
⠋ Mapping Icons...    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Found 1 Folder(s):
📂 CalTopo Export
└── 📂 Olympic Mtn 100k (📍 77 Waypoints)
    ├── 📍 Start/Finish Line → 'Waypoint'
    ├── 🍎 Aid Station 9-Full Aid → 'Food'
    └── ... and 75 more waypoints

                     Export Manifest
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━┓
┃ Filename                      ┃ Format         ┃ Items┃  Size ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━┩
│ Olympic_Mtn_100k_Waypoints.kml│ KML (Waypoints)│   77 │11.2 KB│
└───────────────────────────────┴────────────────┴──────┴───────┘

✔ SUCCESS 1 file(s) written to ./onx_ready
Next: Drag these files into onX Web Map → Import
```

## License

This project is provided as-is for personal use.

## Contributing

Found a bug or have a feature request? Feel free to open an issue or submit a pull request!

## Acknowledgments

- Built with [Typer](https://typer.tiangolo.com/) for CLI
- UI powered by [Rich](https://rich.readthedocs.io/)
- Inspired by the need to migrate years of CalTopo data to onX Backcountry

---

**Happy trails!** 🥾
