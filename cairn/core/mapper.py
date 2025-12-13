"""
Icon and symbol mapping for CalTopo to onX Backcountry conversion.

This module handles the translation of CalTopo's generic marker symbols
to onX Backcountry's specific icon IDs for better visual representation.
"""

from typing import Optional
import re
from cairn.core.config import IconMappingConfig


# Legacy keyword mapping (kept for backward compatibility)
# Updated to match onX Backcountry actual icon names from GPX analysis
# Use config.py for the authoritative mappings
ICON_MAP = {
    "Campsite": ["tent", "camp", "sleep", "overnight"],
    "Water Source": ["water", "spring", "refill", "creek"],
    "Parking": ["car", "parking", "lot"],
    "XC Skiing": ["ski", "skin", "tour", "uptrack", "skiing"],
    "Summit": ["summit", "peak", "top", "mt"],
    "Hazard": ["danger", "avy", "avalanche", "slide", "caution"],
    "Photo": ["camera", "photo", "view"],
    "Cabin": ["cabin", "hut", "yurt"],
    "Trailhead": ["trailhead", "trail head", "th"],
}


def map_icon(title: str, description: str = "", caltopo_symbol: str = "",
             config: Optional[IconMappingConfig] = None) -> str:
    """
    Map a CalTopo marker to an onX Backcountry icon ID.

    Priority order:
    1. CalTopo marker-symbol (if config provided)
    2. Keywords in title/description
    3. Default to "Waypoint"

    Args:
        title: The marker's title/name
        description: The marker's description text
        caltopo_symbol: The original CalTopo marker-symbol value
        config: Optional IconMappingConfig instance for enhanced mapping

    Returns:
        The onX Backcountry icon ID (e.g., "Campsite", "Water Source")
        Defaults to "Location" if no match is found.
    """
    # Use config-based mapping if available
    if config:
        # 1. PRIORITY: Check CalTopo marker-symbol first
        if caltopo_symbol:
            # Normalize symbol (remove prefixes like "circle-", extract base)
            normalized_symbol = caltopo_symbol.lower().strip()

            # Check direct match
            if normalized_symbol in config.symbol_map:
                return config.symbol_map[normalized_symbol]

            # Check if symbol contains a mapped keyword
            for symbol_key, icon_id in config.symbol_map.items():
                if symbol_key in normalized_symbol:
                    return icon_id

        # 2. FALLBACK: Check keywords in title/description
        search_text = f"{title} {description}".lower()
        for icon_id, keywords in config.keyword_map.items():
            for keyword in keywords:
                if keyword.lower() in search_text:
                    return icon_id

        # Track unmapped symbol for reporting
        if caltopo_symbol:
            config.track_unmapped(caltopo_symbol, title)

        # 3. DEFAULT - "Location" is onX's default icon name (confirmed from GPX analysis)
        return "Location"

    # Legacy mode (no config) - use old keyword-only matching
    search_text = f"{title} {description} {caltopo_symbol}".lower()
    for icon_id, keywords in ICON_MAP.items():
        for keyword in keywords:
            if keyword.lower() in search_text:
                return icon_id

    return "Location"


def map_color(caltopo_color: str) -> str:
    """
    Convert CalTopo hex color to KML color format.

    CalTopo uses RGB hex (e.g., "FF0000" for red).
    KML uses AABBGGRR format (alpha, blue, green, red).

    Args:
        caltopo_color: Hex color string from CalTopo (e.g., "FF0000")

    Returns:
        KML-formatted color string (e.g., "ff0000ff" for red with full opacity)
    """
    if not caltopo_color or len(caltopo_color) != 6:
        return "ffffffff"  # Default to white with full opacity

    try:
        # Extract RGB components
        r = caltopo_color[0:2]
        g = caltopo_color[2:4]
        b = caltopo_color[4:6]

        # Convert to KML format: AABBGGRR (full opacity)
        return f"ff{b}{g}{r}".lower()
    except (ValueError, IndexError):
        return "ffffffff"


def get_icon_emoji(icon_id: str) -> str:
    """
    Get an emoji representation for an icon ID (for Rich UI display).

    Args:
        icon_id: The onX icon ID

    Returns:
        An emoji string representing the icon
    """
    emoji_map = {
        "Campsite": "⛺",
        "Water Source": "💧",
        "Parking": "🅿️",
        "XC Skiing": "⛷️",
        "Summit": "🏔️",
        "Hazard": "⚠️",
        "Photo": "📷",
        "Cabin": "🏠",
        "Trailhead": "🥾",
        "Location": "📍",
    }
    return emoji_map.get(icon_id, "📍")
