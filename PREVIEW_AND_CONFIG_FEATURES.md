# Preview and Configuration Features

## Overview

Cairn now includes powerful preview and configuration management features to help you review and customize icon mappings before creating import files.

## New Features

### 1. Dry-Run Mode (`--dry-run`)

Preview what files will be created without actually creating them.

**Usage:**
```bash
python main.py convert input.json --dry-run
```

**What it shows:**
- Summary statistics (waypoint/track/shape counts)
- Icon distribution breakdown with percentages
- Unmapped symbols with examples
- List of files that would be created

**Benefits:**
- Verify icon mappings before conversion
- Identify unmapped symbols early
- Understand data distribution
- No file system changes

### 2. Interactive Review Mode (`--review`)

Review and adjust icon mappings interactively before conversion.

**Usage:**
```bash
python main.py convert input.json --review
```

**Features:**
- Group waypoints by assigned icon
- Show sample waypoints for each icon
- Interactively change icon mappings
- Save changes to configuration
- Automatic re-parsing with new mappings

**Workflow:**
1. Tool groups waypoints by icon
2. Shows samples for each icon group
3. Prompts: Keep, Change, Skip, or Quit
4. If you change an icon, it updates the config
5. Re-parses data with new mappings

### 3. Enhanced Config Command

Manage default icons, colors, and view all available options.

#### List All Icons

```bash
python main.py config --list-icons
```

Shows all 100+ onX Backcountry icons organized by category:
- Camping
- Water
- Winter Sports
- Vehicles
- Hiking
- Climbing
- Terrain
- Hazards
- Observation
- Facilities
- And more...

#### Set Default Icon

```bash
python main.py config --set-default-icon "Campsite"
```

Sets the default icon for unmapped symbols. Must be a valid onX icon name.

#### Set Default Color

```bash
python main.py config --set-default-color "rgba(255,0,0,1)"
```

Sets the default color for waypoints. Accepts rgba format.

#### Show Current Configuration

```bash
python main.py config --show
```

Displays:
- Number of symbol mappings
- Number of keyword mappings
- Unique onX icons in use
- Unmapped detection status
- List of all configured icons

#### Export Configuration Template

```bash
python main.py config --export
```

Creates `cairn_config.json` with default structure for customization.

#### Validate Configuration

```bash
python main.py config --validate cairn_config.json
```

Validates a configuration file for correctness.

## Configuration File Structure

The `cairn_config.json` file supports:

```json
{
  "_comment": "Cairn Icon Mapping Configuration",
  "default_icon": "Location",
  "default_color": "rgba(8,122,255,1)",
  "use_icon_name_prefix": false,
  "symbol_mappings": {
    "tent": "Campsite",
    "water": "Water Source"
  },
  "keyword_mappings": {
    "Campsite": ["tent", "camp", "sleep"],
    "Water Source": ["water", "spring", "creek"]
  },
  "symbol_colors": {
    "tent": "rgba(255,165,0,1)"
  },
  "enable_unmapped_detection": true
}
```

### Configuration Options

- **`default_icon`**: Icon to use for unmapped symbols (default: "Location")
- **`default_color`**: Default color in rgba format (default: blue)
- **`use_icon_name_prefix`**: Add icon type to waypoint names (default: false)
- **`symbol_mappings`**: Direct CalTopo symbol → onX icon mappings
- **`keyword_mappings`**: Keyword-based fallback mappings
- **`symbol_colors`**: Custom colors for specific symbols
- **`enable_unmapped_detection`**: Track and report unmapped symbols (default: true)

## Workflow Examples

### Example 1: Preview Before Converting

```bash
# First, see what will be created
python main.py convert my_map.json --dry-run

# Review the output, then convert
python main.py convert my_map.json
```

### Example 2: Interactive Mapping

```bash
# Use review mode to adjust mappings
python main.py convert my_map.json --review

# Tool shows: "Campsite (25 waypoints)"
# Samples: "Base Camp", "Camp 1", "Camp 2"...
# You choose to change "Campsite" to "Camp Backcountry"
# Mapping is saved and data is re-parsed
```

### Example 3: Custom Defaults

```bash
# Set your preferred defaults
python main.py config --set-default-icon "Trailhead"
python main.py config --set-default-color "rgba(132,212,0,1)"

# Now all unmapped symbols will use these defaults
python main.py convert my_map.json
```

### Example 4: Browse Icons

```bash
# See all available onX icons
python main.py config --list-icons

# Find the perfect icon for your use case
# Then add it to your config
```

## Benefits

1. **Confidence**: Preview before creating files
2. **Control**: Customize icon mappings interactively
3. **Efficiency**: Set defaults once, use everywhere
4. **Discovery**: Browse all 100+ onX icons
5. **Validation**: Ensure correct icon names and colors
6. **Flexibility**: Adjust mappings without editing JSON

## Technical Details

### Preview Module (`preview.py`)

- `generate_dry_run_report()`: Analyzes data without file creation
- `display_dry_run_report()`: Rich formatted output
- `interactive_review()`: Interactive mapping adjustment
- `show_mapping_preview()`: Preview icon assignments

### Config Manager (`config_manager.py`)

- `ConfigManager`: Enhanced configuration management
- Validation of icon names and colors
- Persistence to `cairn_config.json`
- Default value management
- Color transformation integration

### Integration

Both features are seamlessly integrated into the main conversion flow:
- Dry-run mode exits after report
- Review mode updates config and re-parses
- Config changes persist across conversions
- Unmapped symbol handling respects new defaults

## Next Steps

1. Try `--dry-run` on your next conversion
2. Explore all icons with `--list-icons`
3. Set your preferred defaults
4. Use `--review` for fine-tuned control
5. Share your `cairn_config.json` with your team

---

**Note**: These features work with all existing Cairn functionality including:
- Fuzzy matching for unmapped symbols
- Interactive CLI prompts
- Color transformation
- Auto-splitting for large files
- GPX/KML format handling
