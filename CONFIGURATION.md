# Cairn Configuration Guide

## Overview

Cairn uses a two-tier icon mapping system to convert CalTopo markers to onX Backcountry icons:

1. **Symbol Mapping** (Priority 1): Direct CalTopo `marker-symbol` → onX icon
2. **Keyword Mapping** (Priority 2): Keywords in title/description → onX icon

This allows for accurate, customizable icon conversion with automatic detection of unmapped symbols.

## Configuration File

### Location

Cairn looks for `cairn_config.json` in the current directory. You can also specify a custom config file:

```bash
python main.py convert INPUT.json --config my_config.json
```

### Creating a Configuration File

Generate a template configuration file:

```bash
python main.py config --export
```

This creates `cairn_config.json` with default mappings that you can customize.

### Configuration Structure

```json
{
  "symbol_mappings": {
    "skull": "Danger",
    "tent": "Campsite",
    "water": "Water Source"
  },
  "keyword_mappings": {
    "Campsite": ["tent", "camp", "sleep"],
    "Water Source": ["water", "spring", "refill"]
  },
  "enable_unmapped_detection": true
}
```

## Symbol Mappings

### How It Works

CalTopo exports include a `marker-symbol` field for each waypoint. Cairn checks this field first:

**CalTopo Export:**
```json
{
  "title": "Avy hazard area",
  "marker-symbol": "skull",
  "marker-color": "FF0000"
}
```

**Cairn Mapping:**
- Checks `symbol_mappings` for "skull"
- Finds `"skull": "Danger"`
- Maps to onX "Danger" icon ⚠️

### Default Symbol Mappings

| CalTopo Symbol | onX Icon | Emoji |
|----------------|----------|-------|
| skull, danger, warning, hazard | Danger | ⚠️ |
| tent, campsite, shelter | Campsite | ⛺ |
| water, droplet, spring | Water Source | 💧 |
| car, parking, trailhead | Parking | 🅿️ |
| ski, skiing | Skiing | ⛷️ |
| summit, peak, triangle-u | Summit | 🏔️ |
| restaurant, food | Food | 🍎 |
| hospital, cross, first-aid | Medical | 🏥 |
| binoculars, viewpoint | Scenic View | 👁️ |
| fork, junction | Trail Junction | 🔀 |

### Adding Custom Symbol Mappings

1. Export the config template:
   ```bash
   python main.py config --export
   ```

2. Edit `cairn_config.json`:
   ```json
   {
     "symbol_mappings": {
       "skull": "Danger",
       "custom-marker": "Summit",
       "my-icon": "Campsite"
     }
   }
   ```

3. Run conversion with your config:
   ```bash
   python main.py convert INPUT.json
   ```

## Keyword Mappings

### How It Works

If no symbol mapping is found, Cairn searches the waypoint's title and description for keywords:

**Example:**
- Title: "Aid Station 5"
- Description: "Full aid with food and water"
- Keywords matched: "aid", "food" → Maps to "Food" icon 🍎

### Default Keyword Mappings

```json
{
  "Campsite": ["tent", "camp", "sleep", "camping", "bivy", "shelter"],
  "Water Source": ["water", "spring", "refill", "creek", "stream", "lake"],
  "Parking": ["parking", "trailhead", "car", "vehicle", "lot"],
  "Skiing": ["ski", "skin", "tour", "skiing", "backcountry"],
  "Summit": ["summit", "peak", "top", "mountain top"],
  "Danger": ["danger", "hazard", "warning", "caution", "avalanche", "avy"],
  "Trail Junction": ["junction", "intersection", "fork", "split"],
  "Scenic View": ["view", "viewpoint", "vista", "overlook", "scenic"],
  "Food": ["food", "snack", "aid station", "nutrition"],
  "Medical": ["medical", "first aid", "emergency", "rescue"]
}
```

### Customizing Keyword Mappings

Add or modify keywords in `cairn_config.json`:

```json
{
  "keyword_mappings": {
    "Campsite": ["tent", "camp", "sleep", "bivouac"],
    "Water Source": ["water", "spring", "creek", "hydration"],
    "Custom Icon": ["my", "custom", "keywords"]
  }
}
```

## Unmapped Symbol Detection

### What It Does

Cairn tracks CalTopo symbols that don't have mappings and reports them after conversion:

```
⚠️  Found 2 unmapped CalTopo symbol(s):
┌──────────┬───────┬─────────────────────────────────┐
│ Symbol   │ Count │ Example Waypoint                │
├──────────┼───────┼─────────────────────────────────┤
│ circle-s │    12 │ Start/Finish Line               │
│ circle-t │     8 │ Turn-Around Point               │
└──────────┴───────┴─────────────────────────────────┘

💡 Add these to cairn_config.json to map them to onX icons
```

### Using Unmapped Symbol Reports

1. Run conversion and note unmapped symbols
2. Add them to your config:
   ```json
   {
     "symbol_mappings": {
       "circle-s": "Waypoint",
       "circle-t": "Trail Junction"
     }
   }
   ```
3. Re-run conversion to apply new mappings

### Disabling Unmapped Detection

Set in `cairn_config.json`:

```json
{
  "enable_unmapped_detection": false
}
```

## Available onX Icons

Cairn supports these onX Backcountry icon types:

| Icon | Use Case | Emoji |
|------|----------|-------|
| **Waypoint** | Generic location (default) | 📍 |
| **Campsite** | Camping, shelters, bivys | ⛺ |
| **Water Source** | Springs, creeks, lakes | 💧 |
| **Parking** | Trailheads, parking lots | 🅿️ |
| **Skiing** | Ski tours, backcountry skiing | ⛷️ |
| **Summit** | Peaks, summits, high points | 🏔️ |
| **Danger** | Hazards, avalanche zones | ⚠️ |
| **Trail Junction** | Intersections, forks | 🔀 |
| **Scenic View** | Viewpoints, overlooks | 👁️ |
| **Food** | Aid stations, food caches | 🍎 |
| **Medical** | First aid, emergency | 🏥 |

## Configuration Management Commands

### Export Template

Create a configuration template file:

```bash
python main.py config --export
```

Creates `cairn_config.json` in the current directory.

### Show Current Config

Display current configuration statistics:

```bash
python main.py config --show
```

Output:
```
Current Configuration:
  Symbol mappings: 47
  Keyword mappings: 10
  Unique onX icons: 10
  Unmapped detection: Enabled

Available onX Icons:
  ⛺ Campsite
  ⚠️ Danger
  ...
```

### Validate Config File

Check if a configuration file is valid:

```bash
python main.py config --validate my_config.json
```

## Examples

### Example 1: Map Avalanche Hazards

**Problem:** CalTopo uses skull symbols for avalanche hazards, but they appear as generic waypoints in onX.

**Solution:**

1. Create config:
   ```json
   {
     "symbol_mappings": {
       "skull": "Danger",
       "hazard": "Danger"
     },
     "keyword_mappings": {
       "Danger": ["avy", "avalanche", "hazard", "danger"]
     }
   }
   ```

2. Run conversion:
   ```bash
   python main.py convert bitterroots.json
   ```

3. Result: Skull symbols → Danger icon ⚠️ in onX

### Example 2: Custom Ski Tour Markers

**Problem:** You use custom CalTopo symbols for ski objectives.

**Solution:**

1. Run conversion to find unmapped symbols:
   ```bash
   python main.py convert ski_tour.json
   ```

2. Note unmapped symbols (e.g., "ski-objective", "skin-track")

3. Add to config:
   ```json
   {
     "symbol_mappings": {
       "ski-objective": "Skiing",
       "skin-track": "Skiing",
       "ski-descent": "Skiing"
     }
   }
   ```

4. Re-run conversion with updated mappings

### Example 3: Override Defaults

**Problem:** You want "aid station" to map to "Medical" instead of "Food".

**Solution:**

```json
{
  "keyword_mappings": {
    "Medical": ["aid station", "medical", "first aid"],
    "Food": ["food", "snack", "nutrition"]
  }
}
```

User config overrides defaults, so "aid station" now maps to Medical.

## Troubleshooting

### Icons Not Mapping Correctly

1. Check symbol name:
   ```bash
   python main.py convert INPUT.json
   ```
   Look for unmapped symbols in the output.

2. Add symbol to config:
   ```json
   {
     "symbol_mappings": {
       "your-symbol": "Desired Icon"
     }
   }
   ```

3. Validate config:
   ```bash
   python main.py config --validate cairn_config.json
   ```

### Config File Not Loading

- Ensure `cairn_config.json` is in the current directory
- Or specify path: `--config /path/to/config.json`
- Validate JSON syntax: `python main.py config --validate cairn_config.json`

### Symbol vs Keyword Priority

Remember the priority order:
1. **Symbol mapping** (highest priority)
2. **Keyword mapping** (fallback)
3. **Default** ("Waypoint")

If a symbol mapping exists, keyword mapping is not checked.

## Best Practices

1. **Start with defaults**: Run conversion first to see what's unmapped
2. **Use symbol mappings**: More accurate than keyword matching
3. **Keep configs organized**: One config per project/area
4. **Document custom mappings**: Add comments in your config
5. **Validate before converting**: Use `--validate` to check syntax
6. **Iterate**: Run, review, adjust, repeat

## Advanced Usage

### Multiple Configs for Different Projects

```bash
# Ski touring project
python main.py convert ski_tour.json --config ski_config.json

# Climbing project
python main.py convert climbing.json --config climbing_config.json
```

### Sharing Configs

Share your `cairn_config.json` with team members for consistent icon mapping across exports.

### Version Control

Add `cairn_config.json` to your repository to track mapping changes over time.

## Support

For issues or feature requests, refer to the main README.md or open an issue on the project repository.
