# onX Backcountry Icon Reference

Complete guide to onX Backcountry icon names, colors, and mapping recommendations for Cairn.

## Quick Reference

| onX Icon Name | Color | Emoji | Use Case | CalTopo Symbols |
|---------------|-------|-------|----------|-----------------|
| **Hazard** | Red | ⚠️ | Dangers, avalanche zones | skull, danger, warning, hazard |
| **Camp** | Black | ⛺ | Camping, shelters | tent, campsite, shelter, bivy |
| **Water Source** | Blue | 💧 | Springs, creeks, lakes | water, droplet, spring |
| **Parking** | Gray | 🅿️ | Parking lots, vehicle access | car, parking, vehicle |
| **Trailhead** | Green | 🥾 | Trail starts, access points | trailhead, trail head |
| **Ski Touring** | Light Blue | ⛷️ | Ski tours, backcountry skiing | ski, skiing, skin, tour |
| **Summit** | Purple | 🏔️ | Peaks, high points | summit, peak, top |
| **View** | Orange | 👁️ | Scenic viewpoints | viewpoint, vista, overlook |
| **Food Source** | Yellow/Gold | 🍎 | Aid stations, food caches | food, restaurant, aid station |
| **Emergency Phone** | Red | 🏥 | Medical, emergency | hospital, medical, first aid |
| **Location** | Default Blue | 📍 | Generic waypoint | (default/fallback) |

## Color Scheme

Cairn automatically assigns logical colors to each icon type for better visual distinction:

### Safety & Hazards
- **Hazard**: `rgba(255,0,0,1)` - Bright red for maximum visibility
- **Emergency Phone**: `rgba(244,67,54,1)` - Red for emergency services

### Infrastructure
- **Parking**: `rgba(128,128,128,1)` - Gray for man-made structures
- **Trailhead**: `rgba(76,175,80,1)` - Green for trail access points

### Natural Features
- **Water Source**: `rgba(0,122,255,1)` - Blue for water
- **Summit**: `rgba(156,39,176,1)` - Purple for peaks/goals
- **View**: `rgba(255,152,0,1)` - Orange for scenic points

### Activities
- **Camp**: `rgba(0,0,0,1)` - Black for camping
- **Ski Touring**: `rgba(33,150,243,1)` - Light blue for winter sports
- **Food Source**: `rgba(255,193,7,1)` - Yellow/gold for sustenance

### Default
- **Location/Waypoint**: `rgba(8,122,255,1)` - onX default blue

## Icon Details

### Hazard ⚠️
**Color:** Red
**Use For:** Avalanche zones, dangerous areas, warnings, cautions
**CalTopo Symbols:** skull, danger, warning, caution, hazard, alert
**Keywords:** danger, hazard, warning, caution, avalanche, avy

**Example:**
```json
{
  "symbol_mappings": {
    "skull": "Hazard",
    "danger": "Hazard"
  }
}
```

### Camp ⛺
**Color:** Black
**Use For:** Campsites, shelters, bivouac spots
**CalTopo Symbols:** tent, campsite, shelter, camp, bivy
**Keywords:** tent, camp, sleep, camping, bivy, shelter

**Variants:**
- **Camp**: Standard camping
- **Camp Backcountry**: Backcountry/dispersed camping

### Water Source 💧
**Color:** Blue
**Use For:** Springs, creeks, lakes, water refill points
**CalTopo Symbols:** water, droplet, spring, creek, lake
**Keywords:** water, spring, refill, creek, stream, lake, hydration

### Parking 🅿️
**Color:** Gray
**Use For:** Parking lots, vehicle access
**CalTopo Symbols:** car, parking, vehicle, lot
**Keywords:** parking, car, vehicle, lot

### Trailhead 🥾
**Color:** Green
**Use For:** Trail starts, official trailheads
**CalTopo Symbols:** trailhead
**Keywords:** trailhead, trail head, th

**Note:** Separate from Parking in onX

### Ski Touring ⛷️
**Color:** Light Blue
**Use For:** Ski tours, backcountry skiing, skin tracks
**CalTopo Symbols:** ski, skiing, backcountry, skin, tour
**Keywords:** ski, skin, tour, skiing, backcountry

**Related Icons:**
- **Ski Areas**: Resort skiing
- **Skin Track**: Uptrack routes

### Summit 🏔️
**Color:** Purple
**Use For:** Mountain peaks, high points, objectives
**CalTopo Symbols:** summit, peak, triangle-u, mountain, top
**Keywords:** summit, peak, top, mountain top

### View 👁️
**Color:** Orange
**Use For:** Scenic viewpoints, overlooks, vistas
**CalTopo Symbols:** binoculars, viewpoint, vista, overlook
**Keywords:** view, viewpoint, vista, overlook, scenic

### Food Source 🍎
**Color:** Yellow/Gold
**Use For:** Aid stations, food caches, restaurants
**CalTopo Symbols:** restaurant, food, aid, nutrition
**Keywords:** food, snack, aid station, nutrition

### Emergency Phone 🏥
**Color:** Red
**Use For:** Medical facilities, emergency services, first aid
**CalTopo Symbols:** hospital, cross, first-aid, medical, emergency
**Keywords:** medical, first aid, emergency, rescue

## Additional onX Icons

From the onX UI, these icons are also available (not all mapped by default):

### Recreation
- **Bike** - Mountain biking
- **Mountain Biking** - MTB trails
- **Hike** - Hiking trails
- **Backpacker** - Backpacking routes
- **Climbing** - Climbing areas
- **Caving** - Cave entrances

### Water Activities
- **Canoe** - Canoeing
- **Kayak** - Kayaking
- **Swimming** - Swimming areas
- **Raft** - Rafting
- **Rapids** - Whitewater

### Winter Sports
- **Snowmobile** - Snowmobiling
- **Snowboarder** - Snowboarding
- **XC Skiing** - Cross-country skiing

### Wildlife & Nature
- **Eagle** - Wildlife viewing
- **Fish** - Fishing spots
- **Mushroom** - Foraging areas
- **Wildflower** - Botanical interest

### Infrastructure
- **Gate** - Gates
- **Closed Gate** - Closed access
- **Barrier** - Road barriers
- **Open Gate** - Open access

### Facilities
- **Campground** - Developed campgrounds
- **RV** - RV camping
- **Picnic Area** - Picnic facilities
- **Potable Water** - Drinking water
- **Washout** - Restrooms

## Customizing Icon Mappings

### Add Custom Mappings

Edit `cairn_config.json`:

```json
{
  "symbol_mappings": {
    "skull": "Hazard",
    "custom-marker": "Summit",
    "my-icon": "Camp"
  }
}
```

### Override Colors

While Cairn sets default colors, onX allows users to change colors after import. The colors are suggestions for better organization.

## Testing Icon Mappings

1. **Convert your file:**
   ```bash
   python main.py convert YOUR_FILE.json
   ```

2. **Check the output:**
   - Look for icon names in the GPX `<sym>` tags
   - Verify ExtendedData has correct icon names
   - Check colors in ExtendedData

3. **Import to onX:**
   - Drag GPX file to onX Web Map
   - Verify icons display correctly
   - Check colors match expectations

4. **Iterate:**
   - Note any unmapped symbols from Cairn's report
   - Add them to `cairn_config.json`
   - Re-convert and test

## Troubleshooting

### Icons Show as Generic Blue Pins

**Problem:** Icons not displaying correctly in onX

**Solutions:**
1. Verify icon name matches onX exactly (case-sensitive)
2. Check that ExtendedData is present in GPX
3. Try importing KML format instead (future feature)
4. Ensure onX Backcountry is up to date

### Wrong Icon Appears

**Problem:** Icon maps to wrong type

**Solutions:**
1. Check symbol mapping in `cairn_config.json`
2. Verify keyword matching isn't overriding symbol
3. Add explicit symbol mapping for your CalTopo symbol

### Colors Don't Match

**Problem:** Colors different than expected

**Note:** onX may apply its own color scheme. Cairn's colors are suggestions that onX may or may not use. Users can always change colors in onX after import.

## Best Practices

1. **Use Symbol Mappings First** - More accurate than keyword matching
2. **Test with Small Files** - Verify mappings before converting large datasets
3. **Document Custom Symbols** - Keep notes on your custom CalTopo symbols
4. **Share Configs** - Share `cairn_config.json` with team for consistency
5. **Report Unmapped** - Pay attention to Cairn's unmapped symbol reports

## Contributing

Found a new onX icon or better mapping? Please contribute:
1. Test the icon name in onX
2. Update `cairn_config.json` with the mapping
3. Share your configuration

## References

- [onX Backcountry Web Map](https://www.onxmaps.com/backcountry/app)
- [CalTopo](https://caltopo.com/)
- [Cairn Documentation](README.md)
- [Configuration Guide](CONFIGURATION.md)
