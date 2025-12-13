"""
Configuration management for Cairn icon mappings.

This module handles loading and managing user-customizable icon mappings,
allowing users to override defaults and extend mappings as needed.
"""

from typing import Dict, List, Set, Optional
from pathlib import Path
import json
from collections import defaultdict


# onX Backcountry icon color mappings (RGBA format)
# Based on actual onX GPX analysis and color palette
ICON_COLOR_MAP = {
    # From GPX analysis - actual onX colors
    "Location": "rgba(8,122,255,1)",        # Default blue (confirmed from GPX)
    "Hazard": "rgba(255,51,0,1)",           # Orange-red (confirmed from GPX)
    "Campsite": "rgba(255,165,0,1)",        # Orange
    "Water Source": "rgba(0,255,255,1)",    # Cyan
    "Parking": "rgba(128,128,128,1)",       # Gray
    "XC Skiing": "rgba(255,255,255,1)",     # White
    "Ski Touring": "rgba(255,255,255,1)",   # White
    "Ski": "rgba(255,255,255,1)",           # White
    "Summit": "rgba(255,0,0,1)",            # Red
    "Photo": "rgba(255,255,0,1)",           # Yellow
    "Cabin": "rgba(139,69,19,1)",           # Brown
    "Trailhead": "rgba(132,212,0,1)",       # Green
    "Cave": "rgba(8,122,255,1)",            # Blue
    "Barrier": "rgba(255,0,0,1)",           # Red
    "Camp": "rgba(255,165,0,1)",            # Orange
    "Camp Area": "rgba(255,165,0,1)",       # Orange
    "Camp Backcountry": "rgba(255,165,0,1)", # Orange
    "Campground": "rgba(255,165,0,1)",      # Orange
    "View": "rgba(255,255,0,1)",            # Yellow
    "Lookout": "rgba(255,255,0,1)",         # Yellow
}


def get_icon_color(icon_name: str) -> str:
    """
    Get the appropriate RGBA color for an icon type.

    Args:
        icon_name: The onX icon name (e.g., "Hazard", "Campsite")

    Returns:
        RGBA color string (e.g., "rgba(255,0,0,1)")
    """
    return ICON_COLOR_MAP.get(icon_name, "rgba(8,122,255,1)")


# Default CalTopo marker-symbol to onX Backcountry icon mappings
# Based on actual onX GPX analysis and icon screenshots (100+ icons)
DEFAULT_SYMBOL_MAP = {
    # Hazards and warnings - onX uses "Hazard" (confirmed from GPX)
    "danger": "Hazard",
    "skull": "Hazard",
    "warning": "Hazard",
    "caution": "Hazard",
    "hazard": "Hazard",
    "alert": "Hazard",

    # Camping - Multiple onX camp icons
    "campsite": "Campsite",
    "tent": "Campsite",
    "camp": "Camp",
    "camping": "Campsite",
    "bivy": "Camp Backcountry",
    "campground": "Campground",
    "camp-area": "Camp Area",

    # Water sources and features
    "water": "Water Source",
    "droplet": "Water Source",
    "spring": "Water Source",
    "creek": "Water Source",
    "lake": "Water Source",
    "river": "Water Source",
    "waterfall": "Waterfall",
    "hot-spring": "Hot Spring",
    "geyser": "Geyser",
    "rapids": "Rapids",
    "wetland": "Wetland",
    "potable": "Potable Water",
    "water-crossing": "Water Crossing",

    # Vehicles and transportation
    "car": "Parking",
    "parking": "Parking",
    "vehicle": "Parking",
    "lot": "Parking",
    "4x4": "4x4",
    "atv": "ATV",
    "bike": "Bike",
    "bicycle": "Bike",
    "dirt-bike": "Dirt Bike",
    "motorcycle": "Dirt Bike",
    "overland": "Overland",
    "rv": "RV",
    "suv": "SUV",
    "truck": "Truck",

    # Winter sports - onX uses "XC Skiing" (confirmed from GPX)
    "skiing": "XC Skiing",
    "ski": "Ski",
    "xc-skiing": "XC Skiing",
    "backcountry": "Ski Touring",
    "skin": "Skin Track",
    "tour": "Ski Touring",
    "ski-touring": "Ski Touring",
    "ski-area": "Ski Areas",
    "snowboard": "Snowboarder",
    "snowmobile": "Snowmobile",
    "snowpark": "Snowpark",
    "snow-pit": "Snow Pit",

    # Hiking and trails
    "trailhead": "Trailhead",
    "trail": "Trailhead",
    "hike": "Hike",
    "hiking": "Hike",
    "backpack": "Backpacker",
    "backpacker": "Backpacker",
    "mountaineer": "Mountaineer",

    # Climbing
    "climbing": "Climbing",
    "climb": "Climbing",
    "rappel": "Rappel",
    "cave": "Cave",
    "caving": "Caving",

    # Summits and terrain
    "summit": "Summit",
    "peak": "Summit",
    "triangle-u": "Summit",
    "mountain": "Summit",
    "top": "Summit",
    "cornice": "Cornice",
    "couloir": "Couloir",
    "slide-path": "Slide Path",
    "steep": "Steep Trail",
    "log": "Log Obstacle",

    # Infrastructure and barriers
    "barrier": "Barrier",
    "road-barrier": "Road Barrier",
    "gate": "Gate",
    "closed-gate": "Closed Gate",
    "open-gate": "Open Gate",
    "footbridge": "Footbridge",
    "bridge": "Footbridge",
    "crossing": "Crossing",

    # Facilities and amenities
    "fuel": "Fuel",
    "gas": "Fuel",
    "food": "Food Source",
    "restaurant": "Food Source",
    "food-storage": "Food Storage",
    "picnic": "Picnic Area",
    "shelter": "Shelter",
    "house": "House",
    "cabin": "Cabin",
    "hut": "Cabin",
    "yurt": "Cabin",
    "kennels": "Kennels",
    "visitor": "Visitor Center",
    "gear": "Gear",

    # Water activities
    "canoe": "Canoe",
    "kayak": "Kayak",
    "raft": "Raft",
    "rafting": "Raft",
    "swimming": "Swimming",
    "swim": "Swimming",
    "windsurf": "Windsurfing",
    "hand-launch": "Hand Launch",
    "put-in": "Put In",
    "take-out": "Take Out",
    "marina": "Marina",

    # Observation and views
    "camera": "Photo",
    "photo": "Photo",
    "binoculars": "View",
    "viewpoint": "View",
    "vista": "View",
    "overlook": "View",
    "lookout": "Lookout",
    "observation": "Observation Towers",
    "tower": "Observation Towers",
    "webcam": "Webcam",
    "lighthouse": "Lighthouses",

    # Wildlife and nature
    "eagle": "Eagle",
    "bird": "Eagle",
    "fish": "Fish",
    "fishing": "Fish",
    "mushroom": "Mushroom",
    "wildflower": "Wildflower",
    "flower": "Wildflower",
    "feeding": "Feeding Area",
    "dog-sled": "Dog Sledding",

    # Activities
    "horse": "Horseback",
    "horseback": "Horseback",
    "mountain-bike": "Mountain Biking",
    "mtb": "Mountain Biking",
    "foraging": "Foraging",
    "surfing": "Surfing Area",
    "surf": "Surfing Area",
    "hang-gliding": "Hang Gliding",

    # Miscellaneous
    "access": "Access Point",
    "access-point": "Access Point",
    "emergency": "Emergency Phone",
    "phone": "Emergency Phone",
    "ruins": "Ruins",
    "stock-tank": "Stock Tank",
    "washout": "Washout",
    "sasquatch": "Sasquatch",
    "bigfoot": "Sasquatch",
}


# Default keyword mappings (used as fallback)
# Based on actual onX icon names from GPX analysis
DEFAULT_KEYWORD_MAP = {
    # Camping
    "Campsite": ["tent", "camp", "sleep", "overnight", "camping"],
    "Camp": ["camp", "camping"],
    "Camp Area": ["camp area", "camping area"],
    "Camp Backcountry": ["backcountry camp", "bivy", "bivouac"],
    "Campground": ["campground", "established camp"],

    # Water
    "Water Source": ["water", "spring", "refill", "creek", "stream"],
    "Waterfall": ["waterfall", "falls"],
    "Hot Spring": ["hot spring", "thermal"],
    "Potable Water": ["potable", "drinking water"],
    "Water Crossing": ["water crossing", "ford"],

    # Transportation
    "Parking": ["car", "parking", "lot", "vehicle"],
    "Trailhead": ["trailhead", "trail head", "th"],
    "4x4": ["4x4", "four wheel"],
    "ATV": ["atv", "quad"],

    # Winter
    "XC Skiing": ["ski", "skin", "tour", "uptrack", "skiing", "xc"],
    "Ski Touring": ["ski touring", "backcountry ski"],
    "Ski": ["ski", "skiing"],
    "Snowboarder": ["snowboard", "boarding"],

    # Hiking
    "Hike": ["hike", "hiking"],
    "Backpacker": ["backpack", "backpacking"],
    "Mountaineer": ["mountaineer", "alpinist"],

    # Terrain
    "Summit": ["summit", "peak", "top", "mt"],
    "Cave": ["cave", "cavern"],

    # Hazards
    "Hazard": ["danger", "avy", "avalanche", "slide", "caution", "warning"],
    "Barrier": ["barrier", "closed"],

    # Observation
    "Photo": ["camera", "photo"],
    "View": ["view", "viewpoint", "vista", "overlook", "scenic"],
    "Lookout": ["lookout", "observation"],

    # Facilities
    "Cabin": ["cabin", "hut", "yurt"],
    "Shelter": ["shelter", "refuge"],
    "Food Source": ["food", "restaurant", "aid station"],
    "Emergency Phone": ["emergency", "phone", "sos"],
}


class IconMappingConfig:
    """Manages icon mapping configuration with user overrides."""

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            config_file: Optional path to user config JSON file
        """
        self.symbol_map = DEFAULT_SYMBOL_MAP.copy()
        self.keyword_map = DEFAULT_KEYWORD_MAP.copy()
        self.unmapped_symbols: Dict[str, List[str]] = defaultdict(list)
        self.enable_unmapped_detection = True

        # Load user config if provided
        if config_file and config_file.exists():
            self.load_user_config(config_file)

    def load_user_config(self, config_file: Path):
        """
        Load user configuration from JSON file.

        User config overrides defaults. Format:
        {
          "symbol_mappings": {"skull": "Danger", ...},
          "keyword_mappings": {"Campsite": ["tent", ...], ...},
          "enable_unmapped_detection": true
        }

        Args:
            config_file: Path to JSON config file
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)

            # Override symbol mappings
            if "symbol_mappings" in user_config:
                self.symbol_map.update(user_config["symbol_mappings"])

            # Override keyword mappings
            if "keyword_mappings" in user_config:
                self.keyword_map.update(user_config["keyword_mappings"])

            # Set detection flag
            if "enable_unmapped_detection" in user_config:
                self.enable_unmapped_detection = user_config["enable_unmapped_detection"]

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading config file: {e}")

    def track_unmapped(self, symbol: str, waypoint_title: str = ""):
        """
        Track a CalTopo symbol that has no mapping.

        Args:
            symbol: The CalTopo marker-symbol value
            waypoint_title: Optional waypoint title for context
        """
        if not self.enable_unmapped_detection:
            return

        if symbol and symbol not in self.symbol_map:
            self.unmapped_symbols[symbol].append(waypoint_title)

    def get_unmapped_report(self) -> Dict[str, Dict]:
        """
        Get a report of unmapped symbols found during processing.

        Returns:
            Dictionary with symbol as key and stats as value:
            {"symbol": {"count": 5, "examples": ["Title 1", "Title 2"]}}
        """
        report = {}
        for symbol, titles in self.unmapped_symbols.items():
            report[symbol] = {
                "count": len(titles),
                "examples": titles[:3]  # First 3 examples
            }
        return report

    def has_unmapped_symbols(self) -> bool:
        """Check if any unmapped symbols were found."""
        return len(self.unmapped_symbols) > 0

    def export_template(self, output_path: Path):
        """
        Export a configuration template file for user customization.

        Args:
            output_path: Path to write the template JSON file
        """
        template = {
            "_comment": "Cairn Icon Mapping Configuration",
            "_instructions": "Add or modify mappings below. Symbol mappings take priority over keyword mappings.",
            "use_icon_name_prefix": False,
            "_use_icon_name_prefix_info": "If true, adds icon type to waypoint names (e.g., 'Parking - Trailhead'). If false, uses clean names.",
            "symbol_mappings": {
                "skull": "Caution",
                "tent": "Campsite",
                "water": "Water Source",
                "car": "Parking",
                "ski": "Skiing",
                "summit": "Summit",
                "camera": "Photo",
                "cabin": "Cabin"
            },
            "keyword_mappings": {
                "Campsite": ["tent", "camp", "sleep", "overnight"],
                "Water Source": ["water", "spring", "refill", "creek"],
                "Parking": ["car", "parking", "trailhead", "lot"],
                "Skiing": ["ski", "skin", "tour", "uptrack"],
                "Summit": ["summit", "peak", "top", "mt"],
                "Caution": ["danger", "avy", "avalanche", "slide"],
                "Photo": ["camera", "photo", "view"],
                "Cabin": ["cabin", "hut", "yurt"]
            },
            "enable_unmapped_detection": True
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2)

    def get_config_summary(self) -> Dict:
        """
        Get a summary of current configuration.

        Returns:
            Dictionary with config statistics
        """
        return {
            "symbol_mappings_count": len(self.symbol_map),
            "keyword_mappings_count": len(self.keyword_map),
            "unique_onx_icons": len(set(self.symbol_map.values())),
            "unmapped_detection_enabled": self.enable_unmapped_detection
        }


def get_use_icon_name_prefix() -> bool:
    """
    Get whether to add icon type prefixes to waypoint names.

    Returns:
        Boolean indicating if icon prefixes should be added (default: False)
    """
    # Check for user config file
    config_file = Path("cairn_config.json")
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                return user_config.get("use_icon_name_prefix", False)
        except:
            pass
    return False


def load_config(config_file: Optional[Path] = None) -> IconMappingConfig:
    """
    Load icon mapping configuration.

    Args:
        config_file: Optional path to user config file.
                    If None, looks for 'cairn_config.json' in current directory.

    Returns:
        IconMappingConfig instance
    """
    # Check for default config file if none specified
    if config_file is None:
        default_config = Path("cairn_config.json")
        if default_config.exists():
            config_file = default_config

    return IconMappingConfig(config_file)


def get_all_onx_icons() -> List[str]:
    """
    Get complete list of all onX Backcountry icon names.

    Returns:
        Sorted list of unique icon names
    """
    # Get all unique icons from symbol map
    icons = set(DEFAULT_SYMBOL_MAP.values())
    # Add any icons from keyword map
    icons.update(DEFAULT_KEYWORD_MAP.keys())
    return sorted(list(icons))


def save_user_mapping(symbol: str, icon: str, config_path: Path = Path("cairn_config.json")):
    """
    Save user's manual mapping to config file.

    Args:
        symbol: CalTopo symbol to map
        icon: onX icon name to map to
        config_path: Path to config file
    """
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {
            "_comment": "Cairn Icon Mapping Configuration",
            "use_icon_name_prefix": False,
            "enable_unmapped_detection": True
        }

    if "symbol_mappings" not in config:
        config["symbol_mappings"] = {}

    config["symbol_mappings"][symbol] = icon

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
