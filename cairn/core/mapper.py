"""
Icon and symbol mapping for CalTopo to OnX Backcountry conversion.

This module handles the translation of CalTopo's generic marker symbols
to OnX Backcountry's specific icon IDs for better visual representation.
"""

from __future__ import annotations

from typing import Optional

from cairn.core.config import GENERIC_SYMBOLS, IconMappingConfig
from cairn.core.icon_resolver import IconResolver


# Fallback keyword mapping (when no config provided)
# Kept in sync with DEFAULT_KEYWORD_MAP in config.py
ICON_MAP = {
    "Camp": ["tent", "camp", "sleep", "overnight", "camping"],
    "Water Source": ["water", "spring", "refill", "creek", "stream"],
    "Parking": ["car", "parking", "lot", "vehicle"],
    "Trailhead": ["trailhead", "trail head", "th"],
    "XC Skiing": ["ski", "skin", "tour", "uptrack", "skiing", "xc"],
    "Summit": ["summit", "peak", "top", "mt"],
    "Hazard": [
        "danger",
        "avy",
        "avalanche",
        "slide",
        "caution",
        "warning",
        "deadfall",
        "dead fall",
    ],
    "Photo": ["camera", "photo"],
    "View": ["view", "viewpoint", "vista", "overlook", "scenic"],
    "Cabin": ["cabin", "hut", "yurt"],
}

_LEGACY_RESOLVER = IconResolver(
    symbol_map={},
    keyword_map=ICON_MAP,
    default_icon="Location",
    generic_symbols=set(),
)


def map_icon(
    title: str,
    description: str = "",
    caltopo_symbol: str = "",
    config: Optional[IconMappingConfig] = None,
) -> str:
    """
    Map a CalTopo marker to an OnX Backcountry icon ID.

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
        The OnX Backcountry icon ID (e.g., "Camp", "Water Source")
        Defaults to "Location" if no match is found.
    """
    # Config-based mode (preferred): use an explainable resolver and cache it on the config instance.
    if config is not None:
        resolver = getattr(config, "_icon_resolver", None)
        if resolver is None:
            resolver = IconResolver(
                symbol_map=config.symbol_map,
                keyword_map=config.keyword_map,
                default_icon=config.default_icon,
                generic_symbols=set(GENERIC_SYMBOLS),
            )
            setattr(config, "_icon_resolver", resolver)

        decision = resolver.resolve(title, description or "", caltopo_symbol or "")

        # Track unmapped symbols for reporting (even if keywords matched).
        symbol_norm = (caltopo_symbol or "").strip().lower()
        if (
            symbol_norm
            and symbol_norm not in GENERIC_SYMBOLS
            and symbol_norm not in config.symbol_map
        ):
            config.track_unmapped(symbol_norm, title)

        return decision.icon

    # Legacy mode (no config): keep behavior close to the old keyword-only mapping.
    return _LEGACY_RESOLVER.resolve(title, description or "", caltopo_symbol or "").icon


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
    if not caltopo_color:
        return "ffffffff"  # Default to white with full opacity

    caltopo_color = caltopo_color.strip()
    if caltopo_color.startswith("#"):
        caltopo_color = caltopo_color[1:]

    if len(caltopo_color) != 6:
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
