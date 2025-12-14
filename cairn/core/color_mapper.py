"""
Color and style transformation system for mapping CalTopo values to onX-supported values.

This module transforms colors from various formats (hex, rgba) to the closest
onX Backcountry-supported color using Euclidean distance in RGB color space,
and maps line patterns to onX styles.
"""

from typing import Tuple
import math
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


class ColorMapper:
    """Transform colors to closest onX-supported color."""

    # onX supported colors (from GPX analysis and color picker screenshots)
    # These are the actual colors onX uses, confirmed from exported GPX files
    ONX_COLORS = {
        "blue": (8, 122, 255),           # Default blue (confirmed from GPX)
        "red": (255, 0, 0),              # Red
        "orange": (255, 51, 0),          # Orange/Red-orange (confirmed from GPX)
        "yellow": (255, 255, 0),         # Yellow
        "green": (132, 212, 0),          # Light green/lime (confirmed from GPX)
        "purple": (128, 0, 128),         # Purple (confirmed from GPX)
        "magenta": (255, 0, 255),        # Magenta/Pink (confirmed from GPX)
        "black": (0, 0, 0),              # Black (confirmed from GPX)
        "white": (255, 255, 255),        # White (confirmed from GPX)
    }

    # Default color when no match or indeterminate
    DEFAULT_COLOR = "rgba(8,122,255,1)"  # Blue

    @classmethod
    def find_closest_color(cls, r: int, g: int, b: int) -> str:
        """
        Find closest onX color to given RGB values.

        Uses Euclidean distance in RGB color space to find the nearest match.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)

        Returns:
            RGBA string in onX format: "rgba(r,g,b,1)"
        """
        min_distance = float('inf')
        closest_color = None

        for name, (cr, cg, cb) in cls.ONX_COLORS.items():
            # Calculate Euclidean distance in RGB space
            distance = math.sqrt(
                (r - cr) ** 2 +
                (g - cg) ** 2 +
                (b - cb) ** 2
            )

            if distance < min_distance:
                min_distance = distance
                closest_color = (cr, cg, cb)

        # Return in onX format (with spaces after commas, as seen in GPX)
        return f"rgba({closest_color[0]},{closest_color[1]},{closest_color[2]},1)"

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
            match = re.search(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str)
            if match:
                return tuple(map(int, match.groups()))

        # Default to onX blue if parsing fails
        return (8, 122, 255)

    @classmethod
    def transform_color(cls, color_str: str) -> str:
        """
        Transform any color format to closest onX-supported color.

        This is the main entry point for color transformation.

        Args:
            color_str: Color in hex (#FF0000), rgba, or CalTopo format

        Returns:
            onX RGBA string in format "rgba(r,g,b,1)"

        Examples:
            >>> ColorMapper.transform_color("#FF0000")
            'rgba(255,0,0,1)'
            >>> ColorMapper.transform_color("rgba(255, 100, 50, 1)")
            'rgba(255,51,0,1)'  # Closest to onX orange
            >>> ColorMapper.transform_color("00FF00")
            'rgba(132,212,0,1)'  # Closest to onX green
        """
        r, g, b = cls.parse_color(color_str)
        return cls.find_closest_color(r, g, b)

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

        # Check if it matches any onX color exactly
        for name, (cr, cg, cb) in cls.ONX_COLORS.items():
            if (r, g, b) == (cr, cg, cb):
                return name

        return "custom"
