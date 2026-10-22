# Web engine: imported by web/bridge.py and run in the browser via Pyodide.
# Keep it free of terminal/UI imports (tests/test_web_engine_surface.py).
"""
GeoJSON parser for CalTopo exports.

This module handles parsing CalTopo GeoJSON files and organizing
features by folder and geometry type.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from cairn.utils.utils import strip_html

# Name of the group for items not in any CalTopo folder. PROVISIONAL label --
# a product decision still under review (see docs/design/DECISIONS.md UI-10).
UNORGANIZED_FOLDER_NAME = "Unorganized"


class ParsedFeature:
    """Represents a parsed CalTopo feature."""

    def __init__(self, feature: Dict[str, Any]):
        """Initialize from a GeoJSON feature."""
        self.id = feature.get("id", "")

        geom = feature.get("geometry")
        self.geometry = geom if (geom is None or isinstance(geom, dict)) else None

        props = feature.get("properties") or {}
        self.properties = props if isinstance(props, dict) else {}

        # Extract common properties
        # CalTopo keeps a title's trailing space in GeoJSON but not in KML/GPX;
        # strip it so the three formats agree (caltopo-random fixture).
        title = self.properties.get("title", "Untitled")
        self.title = title.strip() if isinstance(title, str) else title
        self.description = strip_html(self.properties.get("description", ""))
        self.class_type = self.properties.get("class", "Unknown")
        self.color = self.properties.get("marker-color") or self.properties.get(
            "stroke", ""
        )
        self.symbol = self.properties.get("marker-symbol", "")

        # Extract line/track properties for OnX fidelity
        self.stroke = self.properties.get("stroke", "")  # Line color (hex)
        self.stroke_width = self.properties.get("stroke-width", 4)  # Line width
        self.pattern = self.properties.get(
            "pattern", "solid"
        )  # Line pattern (solid, dash, etc.)
        # Area (Polygon) styling as CalTopo exports it. Real exports carry
        # fill, fill-opacity, stroke-opacity and stroke-width on every Shape
        # (tests/fixtures/bitterroots: fill-opacity 0.1 or 0, stroke-opacity 1).
        # None means "not provided" so the KML writer can keep its defaults.
        # `fill` (hue) is parsed for completeness but NOT exported: the KML
        # writer ties fill hue to the area's displayed/edited colour.
        self.fill = self.properties.get("fill") or ""
        self.fill_opacity = self.properties.get("fill-opacity")
        self.stroke_opacity = self.properties.get("stroke-opacity")

    @property
    def geometry_type(self) -> Optional[str]:
        """Get the geometry type (Point, LineString, Polygon, etc.)."""
        if self.geometry:
            return self.geometry.get("type")
        return None

    @property
    def coordinates(self) -> Optional[List]:
        """Get the coordinates from the geometry."""
        if self.geometry:
            return self.geometry.get("coordinates")
        return None

    def is_folder(self) -> bool:
        """Check if this feature represents a folder."""
        return self.class_type == "Folder"

    def is_marker(self) -> bool:
        """Check if this feature is a marker/waypoint."""
        return self.class_type == "Marker" and self.geometry_type == "Point"

    def is_line(self) -> bool:
        """Check if this feature is a line/track."""
        # CalTopo exports both class="Line" and class="Shape" with LineString geometry
        return (
            self.class_type == "Line" or self.class_type == "Shape"
        ) and self.geometry_type == "LineString"

    def is_shape(self) -> bool:
        """Check if this feature is a shape/polygon."""
        return self.class_type == "Shape" and self.geometry_type == "Polygon"


class ParsedData:
    """Organized data structure for parsed CalTopo export."""

    def __init__(self):
        """Initialize empty parsed data structure."""
        self.folders: Dict[str, Dict[str, List[ParsedFeature]]] = {}
        self.orphaned_features: List[ParsedFeature] = []

    def add_folder(self, folder_id: str, folder_name: str) -> None:
        """Add a folder to the structure."""
        if folder_id not in self.folders:
            self.folders[folder_id] = {
                "name": folder_name,
                "waypoints": [],
                "tracks": [],
                "shapes": [],
            }

    def add_feature_to_folder(self, folder_id: str, feature: ParsedFeature) -> None:
        """Add a feature to a specific folder."""
        if folder_id not in self.folders:
            self.orphaned_features.append(feature)
            return

        folder = self.folders[folder_id]

        if feature.is_marker():
            folder["waypoints"].append(feature)
        elif feature.is_line():
            folder["tracks"].append(feature)
        elif feature.is_shape():
            folder["shapes"].append(feature)

    def get_folder_stats(self, folder_id: str) -> Dict[str, int]:
        """Get statistics for a folder."""
        if folder_id not in self.folders:
            return {"waypoints": 0, "tracks": 0, "shapes": 0, "total": 0}

        folder = self.folders[folder_id]
        return {
            "waypoints": len(folder["waypoints"]),
            "tracks": len(folder["tracks"]),
            "shapes": len(folder["shapes"]),
            "total": len(folder["waypoints"])
            + len(folder["tracks"])
            + len(folder["shapes"]),
        }

    def get_all_folders(self) -> List[tuple]:
        """Get list of (folder_id, folder_name) tuples."""
        return [(fid, data["name"]) for fid, data in self.folders.items()]


def _split_multipolygon(feature_dict: Dict[str, Any]) -> List[ParsedFeature]:
    """One Polygon ParsedFeature per part of a MultiPolygon feature.

    Nothing downstream handles MultiPolygon (is_shape() wants a Polygon, and onX
    areas are single polygons), so it used to be dropped without a count. Each part
    keeps the feature's properties and title (so it stays in the same folder with
    the same name, colour and notes); the first part keeps the id, later parts get
    "<id>:part<n>". A part with no rings is skipped; a non-list coordinates value
    yields nothing.
    """
    coords = (feature_dict.get("geometry") or {}).get("coordinates")
    if not isinstance(coords, list):
        return []
    base_id = feature_dict.get("id", "")
    out: List[ParsedFeature] = []
    for polygon in coords:
        if not isinstance(polygon, list) or not polygon:
            continue
        part = dict(feature_dict)
        part["properties"] = dict(feature_dict.get("properties") or {})
        part["geometry"] = {"type": "Polygon", "coordinates": polygon}
        if out:
            part["id"] = f"{base_id}:part{len(out) + 1}"
        out.append(ParsedFeature(part))
    return out


def parse_geojson(filepath: Path) -> ParsedData:
    """
    Parse a CalTopo GeoJSON export file.

    CalTopo exports have a specific structure:
    - Features with class="Folder" and geometry=null represent folders
    - Other features belong to folders (though the linking mechanism varies)
    - Features have class="Marker", "Line", or "Shape"

    Args:
        filepath: Path to the GeoJSON file

    Returns:
        ParsedData object with organized features

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file isn't valid JSON
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Validate file is not empty
    if filepath.stat().st_size == 0:
        raise ValueError(f"GeoJSON file is empty: {filepath}")

    # Load the GeoJSON with error handling
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid GeoJSON file (JSON parse error): {e}\n"
            f"File: {filepath}\n"
            f"Tip: Check that the file is valid JSON format"
        )
    except Exception as e:
        raise ValueError(f"Failed to read GeoJSON file: {e}\nFile: {filepath}")

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid GeoJSON file: expected a JSON object at the top level\n"
            f"File: {filepath}"
        )

    if (data.get("type") or "") != "FeatureCollection":
        raise ValueError(
            f"Invalid GeoJSON file: expected type='FeatureCollection'\n"
            f"File: {filepath}\n"
            f"Tip: Make sure this is a CalTopo export GeoJSON"
        )

    features = data.get("features", [])
    if not isinstance(features, list):
        raise ValueError(
            f"Invalid GeoJSON file: expected 'features' to be a list\nFile: {filepath}"
        )

    if not features:
        raise ValueError(
            f"No features found in GeoJSON file: {filepath}\n"
            f"Tip: Make sure this is a CalTopo export with at least one feature"
        )

    parsed_data = ParsedData()

    # First pass: identify folders
    folder_features = []
    non_folder_features = []

    for feature_dict in features:
        if not isinstance(feature_dict, dict):
            continue
        feature = ParsedFeature(feature_dict)

        if feature.is_folder():
            folder_features.append(feature)
            parsed_data.add_folder(feature.id, feature.title)
        elif feature.geometry_type == "MultiPolygon":
            non_folder_features.extend(_split_multipolygon(feature_dict))
        else:
            non_folder_features.append(feature)

    # If no folders found, create a default folder based on filename
    if not folder_features:
        default_folder_id = "default"
        default_folder_name = filepath.stem.replace("_", " ")
        parsed_data.add_folder(default_folder_id, default_folder_name)

        # Add all features to the default folder
        for feature in non_folder_features:
            parsed_data.add_feature_to_folder(default_folder_id, feature)
    else:
        # Strategy: Use folderId property to assign features to folders
        # CalTopo exports include a folderId property that references the folder's id

        for feature in non_folder_features:
            # Check if feature has a folderId property
            folder_id = feature.properties.get("folderId")

            if folder_id:
                # Add to the specified folder
                parsed_data.add_feature_to_folder(folder_id, feature)
            else:
                # No folderId, this is an orphan
                parsed_data.orphaned_features.append(feature)

    # If we have orphaned features, create a separate folder for them
    # These are features without a folderId (CalTopo's root-level features)
    if parsed_data.orphaned_features:
        orphan_folder_id = "orphaned_features"
        orphan_folder_name = UNORGANIZED_FOLDER_NAME
        parsed_data.add_folder(orphan_folder_id, orphan_folder_name)

        for orphan in parsed_data.orphaned_features:
            parsed_data.add_feature_to_folder(orphan_folder_id, orphan)
        parsed_data.orphaned_features = []

    return parsed_data


def get_file_summary(parsed_data: ParsedData) -> Dict[str, Any]:
    """
    Get a summary of the parsed data.

    Args:
        parsed_data: Parsed data structure

    Returns:
        Dictionary with summary statistics
    """
    total_waypoints = 0
    total_tracks = 0
    total_shapes = 0

    for folder_id in parsed_data.folders:
        stats = parsed_data.get_folder_stats(folder_id)
        total_waypoints += stats["waypoints"]
        total_tracks += stats["tracks"]
        total_shapes += stats["shapes"]

    return {
        "folder_count": len(parsed_data.folders),
        "total_waypoints": total_waypoints,
        "total_tracks": total_tracks,
        "total_shapes": total_shapes,
        "total_features": total_waypoints + total_tracks + total_shapes,
        "orphaned_features": len(parsed_data.orphaned_features),
    }
