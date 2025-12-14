"""
Configuration management for Cairn icon mappings.

This module handles loading and managing user-customizable icon mappings,
allowing users to override defaults and extend mappings as needed.
"""

from typing import Dict, List, Optional
from pathlib import Path
import yaml
from collections import defaultdict


# Generic CalTopo symbols that should NOT be mapped to specific icons.
# These are default markers that don't convey semantic meaning.
# Mapping them would bypass keyword matching for all waypoints using them.
GENERIC_SYMBOLS = frozenset([
    "point",
    "marker",
    "pin",
    "dot",
    "circle",
])


# onX Backcountry waypoint icon color mappings (RGBA format).
#
# IMPORTANT:
# - Waypoints support ONLY the official 10-color waypoint palette.
# - These defaults must stay within that palette to avoid onX ignoring colors on import.
# - See docs/onx-waypoint-colors-definitive.md for the canonical list.
ICON_COLOR_MAP = {
    # Official waypoint palette colors (10 total)
    "Location": "rgba(8,122,255,1)",          # Blue
    "Hazard": "rgba(255,51,0,1)",             # Red-Orange
    "Barrier": "rgba(255,0,0,1)",             # Red

    # Camping (no true "orange" in waypoint palette; closest is Red-Orange)
    "Campsite": "rgba(255,51,0,1)",           # Red-Orange
    "Camp": "rgba(255,51,0,1)",               # Red-Orange
    "Camp Area": "rgba(255,51,0,1)",          # Red-Orange
    "Camp Backcountry": "rgba(255,51,0,1)",   # Red-Orange
    "Campground": "rgba(0,0,0,1)",            # Black

    # Water
    "Water Source": "rgba(0,255,255,1)",      # Cyan
    "Waterfall": "rgba(0,255,255,1)",         # Cyan
    "Hot Spring": "rgba(255,255,0,1)",        # Yellow
    "Potable Water": "rgba(0,255,255,1)",     # Cyan
    "Water Crossing": "rgba(139,69,19,1)",    # Brown

    # Transportation (no gray; use black)
    "Parking": "rgba(0,0,0,1)",               # Black
    "Trailhead": "rgba(132,212,0,1)",         # Lime
    "4x4": "rgba(132,212,0,1)",               # Lime
    "ATV": "rgba(132,212,0,1)",               # Lime

    # Winter
    "XC Skiing": "rgba(255,255,255,1)",       # White
    "Ski Touring": "rgba(255,255,255,1)",     # White
    "Ski": "rgba(255,255,255,1)",             # White
    "Skin Track": "rgba(255,255,255,1)",      # White
    "Snowboarder": "rgba(255,255,255,1)",     # White
    "Snowmobile": "rgba(255,255,255,1)",      # White

    # Terrain / observation / facilities
    "Summit": "rgba(255,0,0,1)",              # Red
    "Cave": "rgba(8,122,255,1)",              # Blue
    "Photo": "rgba(255,255,0,1)",             # Yellow
    "View": "rgba(255,255,0,1)",              # Yellow
    "Lookout": "rgba(255,255,0,1)",           # Yellow
    "Cabin": "rgba(139,69,19,1)",             # Brown
    "Shelter": "rgba(139,69,19,1)",           # Brown
    "House": "rgba(139,69,19,1)",             # Brown
    "Food Source": "rgba(139,69,19,1)",       # Brown
}


def get_icon_color(icon_name: str, *, default: str = "rgba(8,122,255,1)") -> str:
    """
    Get the appropriate RGBA color for an icon type.

    Args:
        icon_name: The onX icon name (e.g., "Hazard", "Campsite")

    Returns:
        RGBA color string (e.g., "rgba(255,0,0,1)")
    """
    return ICON_COLOR_MAP.get(icon_name, default)


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

    # Default emoji map for preview display
    DEFAULT_ICON_EMOJIS = {
        "Campsite": "⛺", "Camp": "⛺", "Camp Backcountry": "⛺", "Camp Area": "⛺", "Campground": "⛺",
        "Water Source": "💧", "Waterfall": "💧", "Hot Spring": "♨️", "Potable Water": "💧",
        "Parking": "🅿️", "Trailhead": "🥾", "4x4": "🚙", "ATV": "🏍️",
        "XC Skiing": "⛷️", "Ski": "⛷️", "Ski Touring": "⛷️", "Skin Track": "⛷️", "Snowboarder": "🏂", "Snowmobile": "🛷",
        "Summit": "🏔️", "Cave": "🕳️",
        "Hazard": "⚠️", "Barrier": "🚧",
        "Hike": "🥾", "Backpacker": "🎒",
        "Photo": "📷", "View": "👁️", "Lookout": "🔭",
        "Cabin": "🏠", "Shelter": "🏚️", "House": "🏠", "Food Source": "🍎",
        "Location": "📍",
    }

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            config_file: Optional path to user config YAML file
        """
        self.symbol_map = DEFAULT_SYMBOL_MAP.copy()
        self.keyword_map = DEFAULT_KEYWORD_MAP.copy()
        self.icon_emojis = self.DEFAULT_ICON_EMOJIS.copy()
        self.unmapped_symbols: Dict[str, List[str]] = defaultdict(list)
        self.enable_unmapped_detection = True
        self.use_icon_name_prefix = False
        self.default_icon = "Location"
        self.default_color = "rgba(8,122,255,1)"

        # Load user config if provided
        if config_file and config_file.exists():
            self.load_user_config(config_file)

    def load_user_config(self, config_file: Path):
        """
        Load user configuration from YAML file.

        User config overrides defaults. Format:
        symbol_mappings:
          skull: Hazard
        keyword_mappings:
          Campsite: [tent, camp, sleep]
        enable_unmapped_detection: true

        Args:
            config_file: Path to YAML config file (.yaml or .yml)
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)

            # Handle empty config file
            if user_config is None:
                user_config = {}

            # Override symbol mappings
            if "symbol_mappings" in user_config:
                normalized = {str(k).lower(): v for k, v in (user_config["symbol_mappings"] or {}).items()}
                self.symbol_map.update(normalized)

            # Override keyword mappings
            if "keyword_mappings" in user_config:
                self.keyword_map.update(user_config["keyword_mappings"])

            # Override icon emojis for preview
            if "icon_emojis" in user_config:
                self.icon_emojis.update(user_config["icon_emojis"])

            # Set icon name prefix behavior
            if "use_icon_name_prefix" in user_config:
                self.use_icon_name_prefix = bool(user_config["use_icon_name_prefix"])

            # Defaults
            if "default_icon" in user_config and user_config["default_icon"]:
                default_icon = str(user_config["default_icon"])
                valid_icons = get_all_onx_icons()
                if default_icon not in valid_icons:
                    raise ValueError(f"Invalid default_icon '{default_icon}' (not a valid onX icon)")
                self.default_icon = default_icon

            if "default_color" in user_config and user_config["default_color"]:
                # Quantize to official waypoint palette for safety.
                from cairn.core.color_mapper import ColorMapper
                self.default_color = ColorMapper.map_waypoint_color(str(user_config["default_color"]))

            # Set detection flag
            if "enable_unmapped_detection" in user_config:
                self.enable_unmapped_detection = user_config["enable_unmapped_detection"]

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading config file: {e}")

    def track_unmapped(self, symbol: str, waypoint_title: str = ""):
        """
        Track a CalTopo symbol that has no mapping.

        Generic symbols (point, marker, etc.) are intentionally skipped
        because mapping them would bypass keyword matching for all waypoints.

        Args:
            symbol: The CalTopo marker-symbol value
            waypoint_title: Optional waypoint title for context
        """
        if not self.enable_unmapped_detection:
            return

        # Skip generic symbols - they should use keyword matching
        if symbol and symbol.lower() in GENERIC_SYMBOLS:
            return

        if symbol and symbol not in self.symbol_map:
            self.unmapped_symbols[symbol].append(waypoint_title)

    def get_icon_emoji(self, icon_id: str) -> str:
        """
        Get emoji representation for an icon (for preview display).

        Args:
            icon_id: The onX icon ID

        Returns:
            Emoji string (defaults to 📍 if not found)
        """
        return self.icon_emojis.get(icon_id, "📍")

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

        YAML format with helpful inline comments.

        Args:
            output_path: Path to write the template file (.yaml)
        """
        yaml_content = '''# =============================================================================
# Cairn Icon Mapping Configuration
# =============================================================================
# This file maps CalTopo symbols to onX Backcountry icons.
# YAML format allows inline comments for easier understanding.
#
# Priority order:
#   1. symbol_mappings (highest) - matches CalTopo marker-symbol
#   2. keyword_mappings - searches title/description for keywords
#   3. Default: "Location" icon
# =============================================================================

# If true, adds icon type prefix to names (e.g., "Hazard - Avalanche Zone")
use_icon_name_prefix: false

# Track symbols that don't have mappings (shows report after conversion)
enable_unmapped_detection: true

# =============================================================================
# SYMBOL MAPPINGS
# =============================================================================
# Format: caltopo_symbol: onX Icon Name
# These match the "marker-symbol" field in CalTopo exports.
#
symbol_mappings:

  # ---------------------------------------------------------------------------
  # HAZARDS & WARNINGS -> Hazard (red icon)
  # ---------------------------------------------------------------------------
  skull: Hazard
  danger: Hazard
  warning: Hazard
  caution: Hazard
  hazard: Hazard
  alert: Hazard

  # ---------------------------------------------------------------------------
  # CAMPING -> Campsite/Camp (orange icon)
  # ---------------------------------------------------------------------------
  tent: Campsite
  campsite: Campsite
  camp: Camp
  camping: Campsite
  bivy: Camp Backcountry
  campground: Campground

  # ---------------------------------------------------------------------------
  # WATER -> Water Source (cyan icon)
  # ---------------------------------------------------------------------------
  water: Water Source
  droplet: Water Source
  spring: Water Source
  creek: Water Source
  lake: Water Source
  river: Water Source
  waterfall: Waterfall
  hot-spring: Hot Spring

  # ---------------------------------------------------------------------------
  # PARKING & VEHICLES -> Parking (gray icon)
  # ---------------------------------------------------------------------------
  car: Parking
  parking: Parking
  vehicle: Parking
  lot: Parking
  4x4: 4x4
  atv: ATV

  # ---------------------------------------------------------------------------
  # WINTER SPORTS -> XC Skiing/Ski Touring (white icon)
  # ---------------------------------------------------------------------------
  ski: Ski
  skiing: XC Skiing
  xc-skiing: XC Skiing
  backcountry: Ski Touring
  skin: Skin Track
  tour: Ski Touring
  ski-touring: Ski Touring
  snowboard: Snowboarder
  snowmobile: Snowmobile

  # ---------------------------------------------------------------------------
  # HIKING & TRAILS -> Trailhead/Hike (green icon)
  # ---------------------------------------------------------------------------
  trailhead: Trailhead
  trail: Trailhead
  hike: Hike
  hiking: Hike
  backpack: Backpacker
  backpacker: Backpacker

  # ---------------------------------------------------------------------------
  # SUMMITS & TERRAIN -> Summit (red icon)
  # ---------------------------------------------------------------------------
  summit: Summit
  peak: Summit
  triangle-u: Summit
  mountain: Summit
  top: Summit

  # ---------------------------------------------------------------------------
  # VIEWS & PHOTOS -> Photo/View (yellow icon)
  # ---------------------------------------------------------------------------
  camera: Photo
  photo: Photo
  binoculars: View
  viewpoint: View
  vista: View
  overlook: View
  lookout: Lookout

  # ---------------------------------------------------------------------------
  # FACILITIES -> Cabin (brown icon)
  # ---------------------------------------------------------------------------
  cabin: Cabin
  hut: Cabin
  yurt: Cabin
  shelter: Shelter
  house: House

  # ---------------------------------------------------------------------------
  # MISC - add your custom mappings here
  # ---------------------------------------------------------------------------
  # my-custom-symbol: Location

# =============================================================================
# KEYWORD MAPPINGS
# =============================================================================
# Format: "onX Icon Name": [list, of, keywords]
# Searches waypoint title and description for these keywords.
# Only used if no symbol_mapping matches.
#
keyword_mappings:

  # Camping keywords
  Campsite:
    - tent
    - camp
    - sleep
    - overnight
    - camping

  # Water keywords
  Water Source:
    - water
    - spring
    - refill
    - creek
    - stream

  # Parking keywords
  Parking:
    - car
    - parking
    - lot
    - vehicle

  # Trailhead keywords
  Trailhead:
    - trailhead
    - trail head
    - th

  # Winter sports keywords
  XC Skiing:
    - ski
    - skin
    - tour
    - uptrack
    - skiing
    - xc

  # Summit keywords
  Summit:
    - summit
    - peak
    - top
    - mt

  # Hazard keywords
  Hazard:
    - danger
    - avy
    - avalanche
    - slide
    - caution
    - warning

  # Photo/View keywords
  Photo:
    - camera
    - photo

  View:
    - view
    - viewpoint
    - vista
    - overlook
    - scenic

  # Cabin keywords
  Cabin:
    - cabin
    - hut
    - yurt
'''
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

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
            "unmapped_detection_enabled": self.enable_unmapped_detection,
            "use_icon_name_prefix": self.use_icon_name_prefix,
            "default_icon": self.default_icon,
            "default_color": self.default_color,
        }


def get_use_icon_name_prefix() -> bool:
    """
    Get whether to add icon type prefixes to waypoint names.

    Returns:
        Boolean indicating if icon prefixes should be added (default: False)
    """
    # Check for user config file
    config_files = [
        Path("cairn_config.yaml"),
        Path("cairn_config.yml"),
    ]

    for config_file in config_files:
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        return user_config.get("use_icon_name_prefix", False)
            except:
                pass
    return False


def load_config(config_file: Optional[Path] = None) -> IconMappingConfig:
    """
    Load icon mapping configuration.

    Args:
        config_file: Optional path to user config file (.yaml or .yml).
                    If None, looks for 'cairn_config.yaml' in current directory.

    Returns:
        IconMappingConfig instance
    """
    # Check for default config file if none specified
    if config_file is None:
        yaml_config = Path("cairn_config.yaml")
        yml_config = Path("cairn_config.yml")

        if yaml_config.exists():
            config_file = yaml_config
        elif yml_config.exists():
            config_file = yml_config

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


def save_user_mapping(symbol: str, icon: str, config_path: Path = Path("cairn_config.yaml")):
    """
    Save user's manual mapping to config file.

    Args:
        symbol: CalTopo symbol to map
        icon: onX icon name to map to
        config_path: Path to YAML config file
    """
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {
            "use_icon_name_prefix": False,
            "enable_unmapped_detection": True,
            "symbol_mappings": {},
            "keyword_mappings": {},
        }

    if "symbol_mappings" not in config:
        config["symbol_mappings"] = {}

    symbol_key = (symbol or "").strip().lower()
    config["symbol_mappings"][symbol_key] = icon

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def remove_user_mapping(symbol: str, config_path: Path = Path("cairn_config.yaml")) -> bool:
    """
    Remove a user's manual mapping from the YAML config file.

    Args:
        symbol: CalTopo symbol to remove
        config_path: Path to YAML config file

    Returns:
        True if a mapping was removed, False if no mapping existed.
    """
    if not config_path.exists():
        return False

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    symbol_key = (symbol or "").strip().lower()
    symbol_mappings = config.get("symbol_mappings") or {}
    if symbol_key not in symbol_mappings:
        return False

    del symbol_mappings[symbol_key]
    config["symbol_mappings"] = symbol_mappings

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return True
