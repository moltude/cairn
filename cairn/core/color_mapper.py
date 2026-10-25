# Web engine: imported by web/bridge.py and run in the browser via Pyodide.
# Keep it free of terminal/UI imports (tests/test_web_engine_surface.py).
"""
Color and style transformation system for mapping CalTopo values to OnX-supported values.

OnX Backcountry uses **different color systems** in GPX:

- **Tracks**: use an OnX custom palette (brighter/saturated RGBA values)
- **Waypoints**: support only 10 specific colors (official OnX picker values)

This module provides explicit mapping functions for both, plus line style/weight mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import re


# CalTopo's GeoJSON `pattern` values that have been SEEN in a real export.
# CalTopo draws non-solid lines as a Google-Maps-style symbol sequence,
# "<SVG path>,<offset>,<repeat>,<flag>". "M0 -1 L0 1" is a 2-unit stroke along
# the line, repeated every 8 units: a dashed line (the Google Maps JS API's own
# dashed-polyline recipe is the same path, 'M 0,-1 0,1'). Seen on 6 lines of
# tests/fixtures/bitterroots/Bitterroots__Complete_.json.
CALTOPO_PATTERN_STYLES = {
    "solid": "solid",
    "M0 -1 L0 1,,8,F": "dash",  # Bitterroots
    "M0 -3 L0 3,,12,F": "dash",  # longer dash (owner's caltopo-random export, 2026-10-22)
    # Chevron arrows that rotate with the line ("T"). onX has no arrow style, so
    # an arrow line exports solid (owner's caltopo-random export, 2026-10-22).
    "M-6 8L0 -8M6 8L0 -8M0 0L-6 8M0 0L6 8,20,40,T": "solid",
}
# CalTopo patterns are Google-Maps-style symbols: "<svg path>,<offset>,<repeat>,<F|T>".
# Any single vertical stroke ("M0 -a L0 a") repeated along the line is a dash.
_CALTOPO_DASH_RE = re.compile(r"^M0 -(\d+(?:\.\d+)?) L0 \1,[^,]*,\d+(?:\.\d+)?,[FT]$")
# What CalTopo writes for its dotted and arrow styles is NOT known: no real
# export with one has been seen (docs/FAQ.md, "line patterns"). They fall back
# to solid until an owner export shows the values. onX's own styles are solid,
# dash and dot; it has no arrows, so a directional CalTopo style will be solid
# (or dash) at best.


def pattern_to_style(caltopo_pattern: str) -> str:
    """
    Map a CalTopo line pattern to an onX style: "solid", "dash" or "dot".

    Accepts CalTopo's verified GeoJSON values (CALTOPO_PATTERN_STYLES) and the
    plain names Cairn itself writes and reads back from onX ("solid", "dash",
    "dashed", "dot", "dotted"). Anything else -- including CalTopo's dotted and
    arrow patterns, whose values are unverified -- is "solid".

    Example:
        >>> pattern_to_style("M0 -1 L0 1,,8,F")
        'dash'
        >>> pattern_to_style("dashed")
        'dash'
        >>> pattern_to_style("dotted")
        'dot'
        >>> pattern_to_style("unknown")
        'solid'
    """
    if not caltopo_pattern:
        return "solid"

    raw = caltopo_pattern.strip()
    if raw in CALTOPO_PATTERN_STYLES:
        return CALTOPO_PATTERN_STYLES[raw]

    if _CALTOPO_DASH_RE.match(raw):
        return "dash"
    pattern_lower = raw.lower()
    if pattern_lower in ("dash", "dashed"):
        return "dash"
    if pattern_lower in ("dot", "dotted"):
        return "dot"
    return "solid"


def stroke_width_to_weight(stroke_width) -> str:
    """
    Map CalTopo stroke-width to OnX weight.

    OnX typically uses 4.0 (standard) or 6.0 (thick).

    Args:
        stroke_width: CalTopo stroke-width value (usually 1-10)

    Returns:
        OnX weight as string: "4.0" or "6.0"

    Example:
        >>> stroke_width_to_weight(2)
        '4.0'
        >>> stroke_width_to_weight(6)
        '6.0'
        >>> stroke_width_to_weight("invalid")
        '4.0'
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


# onX area line styles and weights, as onX's GPX export writes them (<onx:style>,
# <onx:weight>). onX's own names for the weights are thin / normal / thick. All
# three of each are kept on import (live test 2026-10-23, docs/ONX_ROUND_TRIP.md
# #area-fidelity), so an onX file's value passes through unchanged.
ONX_LINE_STYLES = ("solid", "dash", "dot")
ONX_LINE_WEIGHTS = ("2.0", "4.0", "6.0")

# ParsedFeature.properties keys that pin an area's exact onX style, weight and
# fill for the area writers (read first, before CalTopo's pattern / stroke-width /
# fill). Set by the onX readers' adapter (passthrough of the file's values) and by
# web/bridge.py's export (the values the UI shows, edited or not).
AREA_STYLE_KEY = "cairn_onx_style"
AREA_WEIGHT_KEY = "cairn_onx_weight"
AREA_FILL_KEY = "cairn_onx_fill"
# Tracks pin their onX style and weight with the same keys (line_onx_style_weight):
# an onX file's dot / 2.0 track passes through, as an area does.
LINE_STYLE_KEY = AREA_STYLE_KEY
LINE_WEIGHT_KEY = AREA_WEIGHT_KEY


_RGB_REGEX = re.compile(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
_ALPHA_REGEX = re.compile(r"rgba\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([\d.]+)\s*\)", re.I)


@dataclass(frozen=True)
class _PaletteColor:
    """An RGB color with its OnX GPX RGBA string representation."""

    name: str
    r: int
    g: int
    b: int
    rgba: str


class ColorMapper:
    """
    Transform colors to OnX-supported values.

    Prefer calling `map_track_color()` or `map_waypoint_color()` instead of the older
    `transform_color()` name (which remains for backwards compatibility).
    """

    # Track palette (OnX official colors). Source: OnX-markups-12142025.gpx
    # Note: Tracks support 11 colors (waypoints only support 10)
    # The first 10 colors are IDENTICAL to the waypoint palette
    TRACK_PALETTE: tuple[_PaletteColor, ...] = (
        _PaletteColor("orange", 255, 51, 0, "rgba(255,51,0,1)"),
        _PaletteColor("blue", 8, 122, 255, "rgba(8,122,255,1)"),
        _PaletteColor("cyan", 0, 255, 255, "rgba(0,255,255,1)"),
        _PaletteColor("green", 132, 212, 0, "rgba(132,212,0,1)"),
        _PaletteColor("black", 0, 0, 0, "rgba(0,0,0,1)"),
        _PaletteColor("white", 255, 255, 255, "rgba(255,255,255,1)"),
        _PaletteColor("purple", 128, 0, 128, "rgba(128,0,128,1)"),
        _PaletteColor("yellow", 255, 255, 0, "rgba(255,255,0,1)"),
        _PaletteColor("red", 255, 0, 0, "rgba(255,0,0,1)"),
        _PaletteColor("brown", 139, 69, 19, "rgba(139,69,19,1)"),
        _PaletteColor(
            "fuchsia", 255, 0, 255, "rgba(255,0,255,1)"
        ),  # 11th color - track-only
    )

    # Waypoint palette (official 10 colors). Table: README.md "Icon, Symbol and Color Mapping"
    WAYPOINT_PALETTE: tuple[_PaletteColor, ...] = (
        _PaletteColor("orange", 255, 51, 0, "rgba(255,51,0,1)"),
        _PaletteColor("blue", 8, 122, 255, "rgba(8,122,255,1)"),
        _PaletteColor("cyan", 0, 255, 255, "rgba(0,255,255,1)"),
        _PaletteColor("green", 132, 212, 0, "rgba(132,212,0,1)"),
        _PaletteColor("black", 0, 0, 0, "rgba(0,0,0,1)"),
        _PaletteColor("white", 255, 255, 255, "rgba(255,255,255,1)"),
        _PaletteColor("purple", 128, 0, 128, "rgba(128,0,128,1)"),
        _PaletteColor("yellow", 255, 255, 0, "rgba(255,255,0,1)"),
        _PaletteColor("red", 255, 0, 0, "rgba(255,0,0,1)"),
        _PaletteColor("brown", 139, 69, 19, "rgba(139,69,19,1)"),
    )

    # onX's area FILL palette ("Area Color" in onX's area editor): 10 swatches,
    # all at alpha 0.1, plus "None". A separate palette from the line colours.
    # Source: the Web Map's own colour table (keys, labels, dbValue) and an onX
    # export after each swatch was set in onX (2026-10-23, docs/ONX_ROUND_TRIP.md
    # #area-fidelity). onX's GPX/KML importer does NOT read an area's fill -- every
    # imported area gets the default Blue whatever the file says -- so Cairn writes
    # the swatch to match onX's own export, not because onX will keep it.
    AREA_FILL_PALETTE: tuple[_PaletteColor, ...] = (
        _PaletteColor("blue", 74, 144, 226, "rgba(74,144,226,0.1)"),
        _PaletteColor("orange", 212, 83, 47, "rgba(212,83,47,0.1)"),
        _PaletteColor("green_brown", 113, 95, 46, "rgba(113,95,46,0.1)"),
        _PaletteColor("red", 193, 76, 90, "rgba(193,76,90,0.1)"),
        _PaletteColor("yellow", 238, 255, 125, "rgba(238,255,125,0.1)"),
        _PaletteColor("blue_green", 42, 139, 97, "rgba(42,139,97,0.1)"),
        _PaletteColor("white", 255, 255, 255, "rgba(255,255,255,0.1)"),
        _PaletteColor("cyan", 153, 255, 255, "rgba(153,255,255,0.1)"),
        _PaletteColor("gray", 80, 80, 80, "rgba(80,80,80,0.1)"),
        _PaletteColor("magenta", 232, 118, 255, "rgba(232,118,255,0.1)"),
    )
    AREA_FILL_NONE = "rgba(0,0,0,0)"  # onX "None" (outline only)
    DEFAULT_AREA_FILL = "rgba(74,144,226,0.1)"  # what onX gives every imported area

    # Default color when no match or indeterminate
    DEFAULT_TRACK_COLOR = "rgba(8,122,255,1)"  # Track blue
    DEFAULT_WAYPOINT_COLOR = "rgba(8,122,255,1)"  # Waypoint blue

    # Back-compat alias used in existing call sites
    DEFAULT_COLOR = DEFAULT_TRACK_COLOR

    @classmethod
    def _find_closest_in_palette(
        cls, r: int, g: int, b: int, palette: Iterable[_PaletteColor]
    ) -> _PaletteColor:
        """
        Find closest palette color using squared Euclidean distance in RGB space.

        Uses squared distance (no sqrt) for performance since we only need relative ordering.
        Formula: d² = (r₁-r₂)² + (g₁-g₂)² + (b₁-b₂)²

        This is equivalent to Euclidean distance for finding the nearest neighbor
        since sqrt is monotonic: if d₁² < d₂², then √d₁² < √d₂².
        """
        best: _PaletteColor | None = None
        best_dist: int | None = None

        for p in palette:
            # Calculate squared Euclidean distance in RGB color space
            dr = r - p.r
            dg = g - p.g
            db = b - p.b
            dist = (dr * dr) + (dg * dg) + (db * db)
            if best is None or best_dist is None or dist < best_dist:
                best = p
                best_dist = dist

        return best  # type: ignore[return-value]

    @classmethod
    def map_track_color(cls, color_str: str) -> str:
        """
        Map a color to the closest OnX **track** palette color.

        Supports multiple input formats: hex (#FF0000), RGB, RGBA, or 6-digit hex.
        Uses Euclidean distance in RGB space to find nearest match.

        Args:
            color_str: Color in various formats (e.g., "#FF0000", "rgb(255,0,0)", "FF0000")

        Returns:
            OnX track RGBA color string (e.g., "rgba(255,0,0,1)")

        Example:
            >>> ColorMapper.map_track_color("#FF0000")
            'rgba(255,0,0,1)'
            >>> ColorMapper.map_track_color("rgb(0, 122, 255)")
            'rgba(8,122,255,1)'
        """
        r, g, b = cls.parse_color(color_str)
        chosen = cls._find_closest_in_palette(r, g, b, cls.TRACK_PALETTE)
        return chosen.rgba

    @classmethod
    def map_waypoint_color(cls, color_str: str) -> str:
        """
        Map a color to the closest OnX **waypoint** palette color.

        OnX waypoints support only 10 specific colors. This method quantizes
        any input color to the nearest supported waypoint color.

        Args:
            color_str: Color in various formats (e.g., "#FF0000", "rgb(255,0,0)", "FF0000")

        Returns:
            OnX waypoint RGBA color string from the 10-color palette

        Example:
            >>> ColorMapper.map_waypoint_color("#FF0000")
            'rgba(255,0,0,1)'
            >>> ColorMapper.map_waypoint_color("#FF00FF")  # Fuchsia not in waypoint palette
            'rgba(128,0,128,1)'  # Maps to purple (closest match)

        Note:
            Waypoints only support 10 colors (vs 11 for tracks). Fuchsia is track-only.
        """
        r, g, b = cls.parse_color(color_str)
        chosen = cls._find_closest_in_palette(r, g, b, cls.WAYPOINT_PALETTE)
        return chosen.rgba

    @classmethod
    def map_area_fill(cls, color_str: str, opacity=None) -> str:
        """An area fill as onX writes it: the nearest of onX's 10 fill swatches, or None.

        - An onX fill value (a swatch, or "rgba(0,0,0,0)") maps to itself, so an
          onX file's fill passes through unchanged.
        - ``opacity`` is CalTopo's fill-opacity: 0 means no fill, so None. Any
          other opacity gives a swatch, which is always alpha 0.1 in onX.
        - Any rgba with alpha 0 is None. Otherwise the hue is matched by RGB
          only; a missing or unreadable colour is matched as parse_color's blue.

        Example:
            >>> ColorMapper.map_area_fill("#FF0000")
            'rgba(212,83,47,0.1)'
            >>> ColorMapper.map_area_fill("#FF0000", opacity=0)
            'rgba(0,0,0,0)'
        """
        if opacity is not None and not isinstance(opacity, bool):
            try:
                if float(opacity) <= 0:
                    return cls.AREA_FILL_NONE
            except (TypeError, ValueError):
                pass
        raw = (color_str or "").strip()
        compact = re.sub(r"\s+", "", raw)
        if compact == cls.AREA_FILL_NONE or compact in {p.rgba for p in cls.AREA_FILL_PALETTE}:
            return compact
        m = _ALPHA_REGEX.match(raw)
        if m:
            try:
                if float(m.group(1)) <= 0:
                    return cls.AREA_FILL_NONE
            except ValueError:
                pass
        r, g, b = cls.parse_color(raw)
        return cls._find_closest_in_palette(r, g, b, cls.AREA_FILL_PALETTE).rgba

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
            # Default to OnX blue
            return (8, 122, 255)

        color_str = color_str.strip()

        # Handle hex colors
        if color_str.startswith("#"):
            color_str = color_str.lstrip("#")

        # If it's a 6-character hex string
        if len(color_str) == 6 and all(
            c in "0123456789ABCDEFabcdef" for c in color_str
        ):
            try:
                return tuple(int(color_str[i : i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                pass

        # Handle rgba() or rgb() format
        if color_str.startswith(("rgba", "rgb")):
            match = _RGB_REGEX.search(color_str)
            if match:
                return tuple(map(int, match.groups()))

        # Default to OnX blue if parsing fails
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
        Get the human-readable name of an OnX color.

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
