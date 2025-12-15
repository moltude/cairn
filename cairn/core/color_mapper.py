"""
Color and style transformation system for mapping CalTopo values to onX-supported values.

onX Backcountry uses **different color systems** in GPX:

- **Tracks**: use an onX custom palette (brighter/saturated RGBA values)
- **Waypoints**: support only 10 specific colors (official onX picker values)

This module provides explicit mapping functions for both, plus line style/weight mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import re


def pattern_to_style(caltopo_pattern: str) -> str:
    """
    Map CalTopo line pattern to OnX style.

    Args:
        caltopo_pattern: CalTopo pattern value (e.g., "solid", "dash", "dot", "dotted")

    Returns:
        OnX style value: "solid", "dash", or "dot"
    """
    if not caltopo_pattern:
        return "solid"

    pattern_lower = caltopo_pattern.lower().strip()

    # Direct mappings
    if pattern_lower in ("solid", ""):
        return "solid"
    elif pattern_lower in ("dash", "dashed"):
        return "dash"
    elif pattern_lower in ("dot", "dotted"):
        return "dot"
    else:
        # Default to solid for unknown patterns
        return "solid"


def stroke_width_to_weight(stroke_width) -> str:
    """
    Map CalTopo stroke-width to OnX weight.

    OnX typically uses 4.0 (standard) or 6.0 (thick).

    Args:
        stroke_width: CalTopo stroke-width value (usually 1-10)

    Returns:
        OnX weight as string: "4.0" or "6.0"
    """
    try:
        width = float(stroke_width)
        # CalTopo widths > 4 map to thick (6.0), otherwise standard (4.0)
        if width > 4:
            return "6.0"
        else:
            return "4.0"
    except (ValueError, TypeError):
        return "4.0"


_RGB_REGEX = re.compile(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


@dataclass(frozen=True)
class _PaletteColor:
    """An RGB color with its onX GPX RGBA string representation."""

    name: str
    r: int
    g: int
    b: int
    rgba: str


class ColorMapper:
    """
    Transform colors to onX-supported values.

    Prefer calling `map_track_color()` or `map_waypoint_color()` instead of the older
    `transform_color()` name (which remains for backwards compatibility).
    """

    # Track palette (onX official colors). Source: onx-markups-12142025.gpx
    # Note: Tracks support 11 colors (waypoints only support 10)
    # The first 10 colors are IDENTICAL to the waypoint palette
    TRACK_PALETTE: tuple[_PaletteColor, ...] = (
        _PaletteColor("red-orange", 255, 51, 0, "rgba(255,51,0,1)"),
        _PaletteColor("blue", 8, 122, 255, "rgba(8,122,255,1)"),
        _PaletteColor("cyan", 0, 255, 255, "rgba(0,255,255,1)"),
        _PaletteColor("lime", 132, 212, 0, "rgba(132,212,0,1)"),
        _PaletteColor("black", 0, 0, 0, "rgba(0,0,0,1)"),
        _PaletteColor("white", 255, 255, 255, "rgba(255,255,255,1)"),
        _PaletteColor("purple", 128, 0, 128, "rgba(128,0,128,1)"),
        _PaletteColor("yellow", 255, 255, 0, "rgba(255,255,0,1)"),
        _PaletteColor("red", 255, 0, 0, "rgba(255,0,0,1)"),
        _PaletteColor("brown", 139, 69, 19, "rgba(139,69,19,1)"),
        _PaletteColor("fuchsia", 255, 0, 255, "rgba(255,0,255,1)"),  # 11th color - track-only
    )

    # Waypoint palette (official 10 colors). Source: docs/onx-waypoint-colors-definitive.md
    WAYPOINT_PALETTE: tuple[_PaletteColor, ...] = (
        _PaletteColor("red-orange", 255, 51, 0, "rgba(255,51,0,1)"),
        _PaletteColor("blue", 8, 122, 255, "rgba(8,122,255,1)"),
        _PaletteColor("cyan", 0, 255, 255, "rgba(0,255,255,1)"),
        _PaletteColor("lime", 132, 212, 0, "rgba(132,212,0,1)"),
        _PaletteColor("black", 0, 0, 0, "rgba(0,0,0,1)"),
        _PaletteColor("white", 255, 255, 255, "rgba(255,255,255,1)"),
        _PaletteColor("purple", 128, 0, 128, "rgba(128,0,128,1)"),
        _PaletteColor("yellow", 255, 255, 0, "rgba(255,255,0,1)"),
        _PaletteColor("red", 255, 0, 0, "rgba(255,0,0,1)"),
        _PaletteColor("brown", 139, 69, 19, "rgba(139,69,19,1)"),
    )

    # Default color when no match or indeterminate
    DEFAULT_TRACK_COLOR = "rgba(8,122,255,1)"  # Track blue
    DEFAULT_WAYPOINT_COLOR = "rgba(8,122,255,1)"  # Waypoint blue

    # Back-compat alias used in existing call sites
    DEFAULT_COLOR = DEFAULT_TRACK_COLOR

    @classmethod
    def _find_closest_in_palette(cls, r: int, g: int, b: int, palette: Iterable[_PaletteColor]) -> _PaletteColor:
        """Find closest palette color using squared-distance (no sqrt)."""
        best: _PaletteColor | None = None
        best_dist: int | None = None

        for p in palette:
            dr = r - p.r
            dg = g - p.g
            db = b - p.b
            dist = (dr * dr) + (dg * dg) + (db * db)
            if best is None or best_dist is None or dist < best_dist:
                best = p
                best_dist = dist

        return best  # type: ignore[return-value]

    @classmethod
    def find_closest_color(cls, r: int, g: int, b: int) -> str:
        """
        Backwards-compatible RGB → nearest onX **track** color mapping.

        Prefer `map_track_color()` or `map_waypoint_color()` for new code.
        """
        return cls._find_closest_in_palette(r, g, b, cls.TRACK_PALETTE).rgba

    @classmethod
    def map_track_color(cls, color_str: str) -> str:
        """Map a color to the closest onX **track** palette color."""
        r, g, b = cls.parse_color(color_str)
        return cls._find_closest_in_palette(r, g, b, cls.TRACK_PALETTE).rgba

    @classmethod
    def map_waypoint_color(cls, color_str: str) -> str:
        """Map a color to the closest onX **waypoint** palette color."""
        r, g, b = cls.parse_color(color_str)
        return cls._find_closest_in_palette(r, g, b, cls.WAYPOINT_PALETTE).rgba

    @classmethod
    def parse_color(cls, color_str: str) -> Tuple[int, int, int]:
        """
        Parse various color formats to RGB tuple.

        Supports:
        - Hex: #FF0000, #ff0000, FF0000
        - RGB: rgb(255, 0, 0)
        - RGBA: rgba(255, 0, 0, 1)
        - CalTopo hex (6 digits without #)

        Args:
            color_str: Color string in various formats

        Returns:
            RGB tuple (r, g, b) with values 0-255
        """
        if not color_str:
            # Default to onX blue
            return (8, 122, 255)

        color_str = color_str.strip()

        # Handle hex colors
        if color_str.startswith('#'):
            color_str = color_str.lstrip('#')

        # If it's a 6-character hex string
        if len(color_str) == 6 and all(c in '0123456789ABCDEFabcdef' for c in color_str):
            try:
                return tuple(int(color_str[i:i+2], 16) for i in (0, 2, 4))
            except ValueError:
                pass

        # Handle rgba() or rgb() format
        if color_str.startswith(('rgba', 'rgb')):
            match = _RGB_REGEX.search(color_str)
            if match:
                return tuple(map(int, match.groups()))

        # Default to onX blue if parsing fails
        return (8, 122, 255)

    @classmethod
    def transform_color(cls, color_str: str) -> str:
        """
        Backwards-compatible alias for track color mapping.

        Prefer calling `map_track_color()` explicitly.
        """
        return cls.map_track_color(color_str)

    @classmethod
    def get_color_name(cls, rgba_str: str) -> str:
        """
        Get the human-readable name of an onX color.

        Args:
            rgba_str: RGBA string like "rgba(255,0,0,1)"

        Returns:
            Color name like "red", "blue", etc., or "custom" if not a standard color
        """
        # Parse the rgba string
        r, g, b = cls.parse_color(rgba_str)

        for p in cls.TRACK_PALETTE:
            if (r, g, b) == (p.r, p.g, p.b):
                return p.name
        for p in cls.WAYPOINT_PALETTE:
            if (r, g, b) == (p.r, p.g, p.b):
                return p.name

        return "custom"
