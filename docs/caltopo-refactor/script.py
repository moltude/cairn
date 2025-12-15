
import json

# Load and analyze the OnX export that was imported to CalTopo and exported back to GeoJSON
with open('test-OnX-export.json', 'r') as f:
    data = json.load(f)

# Get basic structure
print("=== CalTopo GeoJSON Export Structure ===\n")
print(f"Type: {data.get('type')}")
print(f"Number of features: {len(data.get('features', []))}")
print()

# Analyze features
print("=== Feature Summary ===\n")
feature_types = {}
for i, feature in enumerate(data.get('features', [])):
    geom_type = feature.get('geometry', {}).get('type', 'Unknown')
    props = feature.get('properties', {})

    name = props.get('name', 'Unnamed')
    feature_id = props.get('id', 'No ID')

    if geom_type not in feature_types:
        feature_types[geom_type] = []

    feature_types[geom_type].append({
        'index': i,
        'name': name,
        'id': feature_id,
        'properties_keys': list(props.keys())
    })

for geom_type, features in feature_types.items():
    print(f"{geom_type}: {len(features)} features")
    for f in features:
        print(f"  [{f['index']}] {f['name']} | ID: {f['id']}")
        print(f"       Props: {', '.join(f['properties_keys'])}")
