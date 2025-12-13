"""Unit tests for cairn.core.mapper module."""

import pytest
from cairn.core.mapper import (
    map_icon,
    map_color,
    get_icon_emoji,
)


class TestMapIcon:
    """Tests for map_icon function (legacy mode without config)."""

    def test_campsite_keyword(self):
        """Campsite keywords matched."""
        assert map_icon("Tent site", "") == "Campsite"
        assert map_icon("Camp location", "") == "Campsite"
        assert map_icon("Sleep here", "") == "Campsite"

    def test_water_keyword(self):
        """Water source keywords matched."""
        assert map_icon("Water source", "") == "Water Source"
        assert map_icon("Spring", "") == "Water Source"
        assert map_icon("Creek crossing", "") == "Water Source"

    def test_parking_keyword(self):
        """Parking keywords matched."""
        assert map_icon("Parking lot", "") == "Parking"
        assert map_icon("Car access", "") == "Parking"

    def test_summit_keyword(self):
        """Summit keywords matched."""
        assert map_icon("Summit marker", "") == "Summit"
        assert map_icon("Peak viewpoint", "") == "Summit"
        assert map_icon("Mt. Hood", "") == "Summit"

    def test_hazard_keyword(self):
        """Hazard keywords matched."""
        assert map_icon("Danger zone", "") == "Hazard"
        assert map_icon("Avalanche terrain", "") == "Hazard"
        assert map_icon("Avy debris", "") == "Hazard"

    def test_photo_keyword(self):
        """Photo keywords matched."""
        assert map_icon("Camera spot", "") == "Photo"
        assert map_icon("Photo opportunity", "") == "Photo"
        assert map_icon("Good view", "") == "Photo"

    def test_cabin_keyword(self):
        """Cabin keywords matched."""
        assert map_icon("Cabin location", "") == "Cabin"
        assert map_icon("Mountain hut", "") == "Cabin"
        assert map_icon("Yurt site", "") == "Cabin"

    def test_trailhead_keyword(self):
        """Trailhead keywords matched."""
        # Note: "Trailhead parking" matches "parking" first, so returns Parking
        assert map_icon("Trailhead start", "") == "Trailhead"
        assert map_icon("Trail head", "") == "Trailhead"

    def test_skiing_keyword(self):
        """Skiing keywords matched."""
        assert map_icon("Ski descent", "") == "XC Skiing"
        assert map_icon("Skin track start", "") == "XC Skiing"
        assert map_icon("Tour route", "") == "XC Skiing"

    def test_description_match(self):
        """Keywords in description also match."""
        assert map_icon("Random Point", "Good tent site") == "Campsite"

    def test_no_match_returns_location(self):
        """No keyword match returns Location."""
        assert map_icon("Random waypoint", "No keywords here") == "Location"

    def test_empty_inputs(self):
        """Empty inputs return Location."""
        assert map_icon("", "") == "Location"

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        assert map_icon("CAMPING SPOT", "") == "Campsite"
        assert map_icon("water SOURCE", "") == "Water Source"


class TestMapColor:
    """Tests for map_color function (CalTopo to KML)."""

    def test_red_color(self):
        """Red hex converted correctly."""
        # CalTopo: FF0000 (RGB) -> KML: ff0000ff (AABBGGRR)
        result = map_color("FF0000")
        assert result == "ff0000ff"

    def test_green_color(self):
        """Green hex converted correctly."""
        result = map_color("00FF00")
        assert result == "ff00ff00"

    def test_blue_color(self):
        """Blue hex converted correctly."""
        result = map_color("0000FF")
        assert result == "ffff0000"

    def test_white_color(self):
        """White hex converted correctly."""
        result = map_color("FFFFFF")
        assert result == "ffffffff"

    def test_empty_input(self):
        """Empty input returns white."""
        assert map_color("") == "ffffffff"

    def test_invalid_length(self):
        """Invalid length returns white."""
        assert map_color("FF00") == "ffffffff"
        assert map_color("FF0000FF") == "ffffffff"

    def test_lowercase_input(self):
        """Lowercase input works."""
        result = map_color("ff0000")
        assert result == "ff0000ff"


class TestGetIconEmoji:
    """Tests for get_icon_emoji function."""

    def test_campsite_emoji(self):
        assert get_icon_emoji("Campsite") == "⛺"

    def test_water_source_emoji(self):
        assert get_icon_emoji("Water Source") == "💧"

    def test_parking_emoji(self):
        assert get_icon_emoji("Parking") == "🅿️"

    def test_summit_emoji(self):
        assert get_icon_emoji("Summit") == "🏔️"

    def test_hazard_emoji(self):
        assert get_icon_emoji("Hazard") == "⚠️"

    def test_location_emoji(self):
        assert get_icon_emoji("Location") == "📍"

    def test_unknown_icon(self):
        """Unknown icons get default pin emoji."""
        assert get_icon_emoji("Unknown Icon") == "📍"
