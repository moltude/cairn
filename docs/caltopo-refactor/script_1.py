
import json

with open('test-OnX-export.json', 'r') as f:
    data = json.load(f)

# Look at actual values in the data to spot duplicates
print("=== Examining features for duplicates ===\n")

points = [f for f in data['features'] if f['geometry']['type'] == 'Point']
lines = [f for f in data['features'] if f['geometry']['type'] == 'LineString']

print(f"POINTS: Looking for exact duplicate coordinates or properties\n")
# Check for duplicate coordinates
coords_seen = {}
duplicates = []

for i, point in enumerate(points[:10]):  # Sample first 10
    coords = tuple(point['geometry']['coordinates'])
    props = point['properties']

    # Create a unique key from coordinates + important properties
    key = (coords, props.get('title', ''), props.get('description', ''))

    if key in coords_seen:
        duplicates.append((i, coords_seen[key], props))
        print(f"[{i}] DUPLICATE: Coords {coords}")
        print(f"    Title: {props.get('title', 'N/A')}")
        print(f"    Desc: {props.get('description', 'N/A')}")
        print(f"    Symbol: {props.get('marker-symbol', 'N/A')}")
        print(f"    First seen at index: {coords_seen[key]}")
        print()
    else:
        coords_seen[key] = i

# Look at property structure more carefully
print("\n=== Detailed property analysis (first 5 points) ===\n")
for i, point in enumerate(points[:5]):
    props = point['properties']
    coords = point['geometry']['coordinates']
    print(f"[{i}] Point at {coords}")
    print(f"    title: {props.get('title')}")
    print(f"    description: {props.get('description')}")
    print(f"    marker-symbol: {props.get('marker-symbol')}")
    print(f"    stroke: {props.get('stroke')}")
    print(f"    class: {props.get('class')}")
    print(f"    creator: {props.get('creator')}")
    print()

# Check for features with same coordinates
print("\n=== Checking for exact coordinate matches ===\n")
coord_map = {}
for i, feature in enumerate(data['features']):
    if feature['geometry']['type'] == 'Point':
        coords = tuple(feature['geometry']['coordinates'])
        if coords not in coord_map:
            coord_map[coords] = []
        coord_map[coords].append(i)

duplicate_coords = {k: v for k, v in coord_map.items() if len(v) > 1}
if duplicate_coords:
    print(f"Found {len(duplicate_coords)} coordinates with multiple features:\n")
    for coords, indices in list(duplicate_coords.items())[:5]:
        print(f"Coordinates {coords}:")
        for idx in indices:
            feat = data['features'][idx]
            print(f"  [{idx}] title='{feat['properties'].get('title')}' desc='{feat['properties'].get('description')}'")
else:
    print("No exact coordinate duplicates found")

# Now check line duplicates
print("\n\n=== Checking LineString features for duplicates ===\n")
for i, line in enumerate(lines[:5]):
    coords = line['geometry']['coordinates']
    props = line['properties']
    print(f"[{i}] LineString with {len(coords)} points")
    print(f"    First point: {coords[0]}, Last point: {coords[-1]}")
    print(f"    title: {props.get('title')}")
    print(f"    description: {props.get('description')}")
    print()
