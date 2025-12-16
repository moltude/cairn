"""Unit tests for cairn.core.mapper module."""

import pytest
from cairn.core.mapper import (
    map_icon,
    map_color,
)
from cairn.core.config import load_config


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
        assert map_icon("Deadfall", "") == "Hazard"
        assert map_icon("Dead fall ahead", "") == "Hazard"

    def test_photo_keyword(self):
        """Photo keywords matched."""
        assert map_icon("Camera spot", "") == "Photo"
        assert map_icon("Photo opportunity", "") == "Photo"

    def test_view_keyword(self):
        """View keywords matched (separate from Photo)."""
        assert map_icon("Good view", "") == "View"
        assert map_icon("Vista point", "") == "View"
        assert map_icon("Scenic overlook", "") == "View"

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

    def test_hash_prefixed_input(self):
        """CalTopo exports often include leading #."""
        result = map_color("#FF0000")
        assert result == "ff0000ff"


class TestSymbolMappingsWithConfig:
    """Tests for CalTopo symbol -> OnX icon mappings using config."""

    @pytest.fixture
    def config(self):
        """Load the actual config file."""
        return load_config()

    # -------------------------------------------------------------------------
    # HAZARD SYMBOLS
    # -------------------------------------------------------------------------
    def test_hazard_symbols(self, config):
        """Various hazard symbols map to Hazard icon."""
        assert map_icon("", "", "skull", config) == "Hazard"
        assert map_icon("", "", "danger", config) == "Hazard"
        assert map_icon("", "", "warning", config) == "Hazard"
        assert map_icon("", "", "caution", config) == "Hazard"
        assert map_icon("", "", "hazard", config) == "Hazard"
        assert map_icon("", "", "alert", config) == "Hazard"

    def test_hazard_symbols_case_insensitive(self, config):
        """Symbol matching is case-insensitive."""
        assert map_icon("", "", "SKULL", config) == "Hazard"
        assert map_icon("", "", "Danger", config) == "Hazard"
        assert map_icon("", "", "WARNING", config) == "Hazard"
        assert map_icon("", "", "CauTion", config) == "Hazard"

    # -------------------------------------------------------------------------
    # CAMPING SYMBOLS
    # -------------------------------------------------------------------------
    def test_camping_symbols(self, config):
        """Camping symbols map to appropriate camp icons."""
        assert map_icon("", "", "tent", config) == "Campsite"
        assert map_icon("", "", "campsite", config) == "Campsite"
        assert map_icon("", "", "camp", config) == "Camp"
        assert map_icon("", "", "camping", config) == "Campsite"
        assert map_icon("", "", "bivy", config) == "Camp Backcountry"
        assert map_icon("", "", "campground", config) == "Campground"

    def test_camping_symbols_case_insensitive(self, config):
        """Camping symbol matching is case-insensitive."""
        assert map_icon("", "", "TENT", config) == "Campsite"
        assert map_icon("", "", "Campsite", config) == "Campsite"
        assert map_icon("", "", "BIVY", config) == "Camp Backcountry"

    # -------------------------------------------------------------------------
    # WATER SYMBOLS
    # -------------------------------------------------------------------------
    def test_water_symbols(self, config):
        """Water symbols map to appropriate water icons."""
        assert map_icon("", "", "water", config) == "Water Source"
        assert map_icon("", "", "droplet", config) == "Water Source"
        assert map_icon("", "", "spring", config) == "Water Source"
        assert map_icon("", "", "creek", config) == "Water Source"
        assert map_icon("", "", "lake", config) == "Water Source"
        assert map_icon("", "", "river", config) == "Water Source"
        assert map_icon("", "", "waterfall", config) == "Waterfall"
        assert map_icon("", "", "hot-spring", config) == "Hot Spring"

    def test_water_symbols_case_insensitive(self, config):
        """Water symbol matching is case-insensitive."""
        assert map_icon("", "", "WATER", config) == "Water Source"
        assert map_icon("", "", "Spring", config) == "Water Source"
        assert map_icon("", "", "WATERFALL", config) == "Waterfall"

    # -------------------------------------------------------------------------
    # PARKING & VEHICLE SYMBOLS
    # -------------------------------------------------------------------------
    def test_parking_symbols(self, config):
        """Parking symbols map to Parking icon."""
        assert map_icon("", "", "car", config) == "Parking"
        assert map_icon("", "", "parking", config) == "Parking"
        assert map_icon("", "", "vehicle", config) == "Parking"
        assert map_icon("", "", "lot", config) == "Parking"

    def test_vehicle_symbols(self, config):
        """Vehicle symbols map to appropriate icons."""
        assert map_icon("", "", "4x4", config) == "4x4"
        assert map_icon("", "", "atv", config) == "ATV"

    # -------------------------------------------------------------------------
    # WINTER SPORTS SYMBOLS
    # -------------------------------------------------------------------------
    def test_winter_sports_symbols(self, config):
        """Winter sports symbols map correctly."""
        assert map_icon("", "", "ski", config) == "Ski"
        assert map_icon("", "", "skiing", config) == "XC Skiing"
        assert map_icon("", "", "xc-skiing", config) == "XC Skiing"
        assert map_icon("", "", "ski-touring", config) == "Ski Touring"
        assert map_icon("", "", "skin", config) == "Skin Track"
        assert map_icon("", "", "snowboard", config) == "Snowboarder"
        assert map_icon("", "", "snowmobile", config) == "Snowmobile"

    def test_winter_symbols_case_insensitive(self, config):
        """Winter symbol matching is case-insensitive."""
        assert map_icon("", "", "SKI", config) == "Ski"
        assert map_icon("", "", "SKIING", config) == "XC Skiing"
        assert map_icon("", "", "Snowboard", config) == "Snowboarder"

    # -------------------------------------------------------------------------
    # HIKING & TRAIL SYMBOLS
    # -------------------------------------------------------------------------
    def test_hiking_symbols(self, config):
        """Hiking symbols map correctly."""
        assert map_icon("", "", "trailhead", config) == "Trailhead"
        assert map_icon("", "", "trail", config) == "Trailhead"
        assert map_icon("", "", "hike", config) == "Hike"
        assert map_icon("", "", "hiking", config) == "Hike"
        assert map_icon("", "", "backpack", config) == "Backpacker"
        assert map_icon("", "", "backpacker", config) == "Backpacker"

    # -------------------------------------------------------------------------
    # SUMMIT & PEAK SYMBOLS
    # -------------------------------------------------------------------------
    def test_summit_symbols(self, config):
        """Summit symbols map correctly."""
        assert map_icon("", "", "summit", config) == "Summit"
        assert map_icon("", "", "peak", config) == "Summit"
        assert map_icon("", "", "mountain", config) == "Summit"
        assert map_icon("", "", "top", config) == "Summit"

    def test_summit_symbols_case_insensitive(self, config):
        """Summit symbol matching is case-insensitive."""
        assert map_icon("", "", "SUMMIT", config) == "Summit"
        assert map_icon("", "", "Peak", config) == "Summit"
        assert map_icon("", "", "MOUNTAIN", config) == "Summit"

    # -------------------------------------------------------------------------
    # VIEW & PHOTO SYMBOLS
    # -------------------------------------------------------------------------
    def test_photo_view_symbols(self, config):
        """Photo and view symbols map correctly."""
        assert map_icon("", "", "camera", config) == "Photo"
        assert map_icon("", "", "photo", config) == "Photo"
        assert map_icon("", "", "binoculars", config) == "View"
        assert map_icon("", "", "viewpoint", config) == "View"
        assert map_icon("", "", "vista", config) == "View"
        assert map_icon("", "", "overlook", config) == "View"
        assert map_icon("", "", "lookout", config) == "Lookout"

    # -------------------------------------------------------------------------
    # FACILITY SYMBOLS
    # -------------------------------------------------------------------------
    def test_facility_symbols(self, config):
        """Facility symbols map correctly."""
        assert map_icon("", "", "cabin", config) == "Cabin"
        assert map_icon("", "", "hut", config) == "Cabin"
        assert map_icon("", "", "yurt", config) == "Cabin"
        assert map_icon("", "", "shelter", config) == "Shelter"
        assert map_icon("", "", "house", config) == "House"


class TestKeywordMappingsWithConfig:
    """Tests for title/description keyword -> OnX icon mappings using config."""

    @pytest.fixture
    def config(self):
        """Load the actual config file."""
        return load_config()

    # -------------------------------------------------------------------------
    # CAMPING KEYWORDS
    # -------------------------------------------------------------------------
    def test_camping_keywords(self, config):
        """Camping keywords match correctly."""
        assert map_icon("Tent Site Alpha", "", "", config) == "Campsite"
        assert map_icon("Base Camp", "", "", config) == "Campsite"
        assert map_icon("Sleep spot", "", "", config) == "Campsite"
        assert map_icon("Overnight location", "", "", config) == "Campsite"
        assert map_icon("Camping area", "", "", config) == "Campsite"

    def test_camping_keywords_case_insensitive(self, config):
        """Camping keyword matching is case-insensitive."""
        assert map_icon("TENT SITE", "", "", config) == "Campsite"
        assert map_icon("base CAMP", "", "", config) == "Campsite"
        assert map_icon("Cow Camp Mile 31.9", "", "", config) == "Campsite"
        assert map_icon("hunting camp mile 92.8", "", "", config) == "Campsite"

    # -------------------------------------------------------------------------
    # WATER KEYWORDS
    # -------------------------------------------------------------------------
    def test_water_keywords(self, config):
        """Water keywords match correctly."""
        assert map_icon("Water source here", "", "", config) == "Water Source"
        assert map_icon("Cold spring", "", "", config) == "Water Source"
        assert map_icon("Refill point", "", "", config) == "Water Source"
        assert map_icon("Creek crossing", "", "", config) == "Water Source"
        assert map_icon("Stream junction", "", "", config) == "Water Source"

    def test_water_keywords_case_insensitive(self, config):
        """Water keyword matching is case-insensitive."""
        assert map_icon("WATER SOURCE", "", "", config) == "Water Source"
        assert map_icon("Cold SPRING", "", "", config) == "Water Source"
        assert map_icon("Creek Crossing", "", "", config) == "Water Source"

    # -------------------------------------------------------------------------
    # PARKING KEYWORDS
    # -------------------------------------------------------------------------
    def test_parking_keywords(self, config):
        """Parking keywords match correctly."""
        assert map_icon("Car access point", "", "", config) == "Parking"
        assert map_icon("Parking area", "", "", config) == "Parking"
        assert map_icon("Parking lot", "", "", config) == "Parking"
        assert map_icon("Vehicle staging", "", "", config) == "Parking"

    # -------------------------------------------------------------------------
    # HAZARD KEYWORDS
    # -------------------------------------------------------------------------
    def test_hazard_keywords(self, config):
        """Hazard keywords match correctly."""
        assert map_icon("Danger zone", "", "", config) == "Hazard"
        assert map_icon("Avy zone", "", "", config) == "Hazard"  # avoid "path" which has "th"
        assert map_icon("Avalanche runout", "", "", config) == "Hazard"
        assert map_icon("Slide area", "", "", config) == "Hazard"
        assert map_icon("Caution needed", "", "", config) == "Hazard"
        assert map_icon("Warning sign", "", "", config) == "Hazard"
        assert map_icon("Deadfall", "", "", config) == "Hazard"
        assert map_icon("Dead fall ahead", "", "", config) == "Hazard"

    def test_hazard_keywords_case_insensitive(self, config):
        """Hazard keyword matching is case-insensitive."""
        assert map_icon("DANGER ZONE", "", "", config) == "Hazard"
        assert map_icon("Avalanche Terrain", "", "", config) == "Hazard"
        assert map_icon("DEADFALL", "", "", config) == "Hazard"
        assert map_icon("Dead Fall", "", "", config) == "Hazard"
        assert map_icon("DEAD FALL", "", "", config) == "Hazard"

    # -------------------------------------------------------------------------
    # SUMMIT KEYWORDS
    # -------------------------------------------------------------------------
    def test_summit_keywords(self, config):
        """Summit keywords match correctly."""
        assert map_icon("Summit marker", "", "", config) == "Summit"
        assert map_icon("Peak elevation", "", "", config) == "Summit"
        assert map_icon("Mt. Hood", "", "", config) == "Summit"
        # Note: "top" removed as keyword - causes false matches (e.g., "stop")

    def test_summit_keywords_case_insensitive(self, config):
        """Summit keyword matching is case-insensitive."""
        assert map_icon("SUMMIT MARKER", "", "", config) == "Summit"
        assert map_icon("Peak Elevation", "", "", config) == "Summit"
        assert map_icon("MT. RAINIER", "", "", config) == "Summit"

    # -------------------------------------------------------------------------
    # WINTER SPORTS KEYWORDS
    # -------------------------------------------------------------------------
    def test_skiing_keywords(self, config):
        """Skiing keywords match correctly."""
        assert map_icon("Ski descent", "", "", config) == "XC Skiing"
        assert map_icon("Skin track start", "", "", config) == "XC Skiing"
        assert map_icon("Tour route", "", "", config) == "XC Skiing"
        assert map_icon("Uptrack begin", "", "", config) == "XC Skiing"
        assert map_icon("XC trail", "", "", config) == "XC Skiing"

    # -------------------------------------------------------------------------
    # VIEW & PHOTO KEYWORDS
    # -------------------------------------------------------------------------
    def test_photo_keywords(self, config):
        """Photo keywords match correctly."""
        assert map_icon("Camera spot", "", "", config) == "Photo"
        assert map_icon("Photo opportunity", "", "", config) == "Photo"

    def test_view_keywords(self, config):
        """View keywords match correctly."""
        assert map_icon("View point", "", "", config) == "View"
        assert map_icon("Viewpoint marker", "", "", config) == "View"
        assert map_icon("Vista here", "", "", config) == "View"
        assert map_icon("Overlook area", "", "", config) == "View"
        assert map_icon("Scenic area", "", "", config) == "View"

    # -------------------------------------------------------------------------
    # CABIN KEYWORDS
    # -------------------------------------------------------------------------
    def test_cabin_keywords(self, config):
        """Cabin keywords match correctly."""
        assert map_icon("Cabin location", "", "", config) == "Cabin"
        assert map_icon("Mountain hut", "", "", config) == "Cabin"
        assert map_icon("Yurt site", "", "", config) == "Cabin"

    # -------------------------------------------------------------------------
    # TRAILHEAD KEYWORDS
    # -------------------------------------------------------------------------
    def test_trailhead_keywords(self, config):
        """Trailhead keywords match correctly."""
        assert map_icon("Trailhead start", "", "", config) == "Trailhead"
        assert map_icon("Trail head here", "", "", config) == "Trailhead"
        # Note: "Trail head parking" would match "parking" first due to keyword order

    # -------------------------------------------------------------------------
    # DESCRIPTION MATCHING
    # -------------------------------------------------------------------------
    def test_description_keywords(self, config):
        """Keywords in description also match."""
        assert map_icon("Random Point", "Good tent site here", "", config) == "Campsite"
        assert map_icon("Waypoint 5", "Water refill available", "", config) == "Water Source"
        assert map_icon("Point 3", "Danger - avalanche terrain", "", config) == "Hazard"

    def test_description_keywords_case_insensitive(self, config):
        """Description keyword matching is case-insensitive."""
        assert map_icon("Point A", "TENT SITE", "", config) == "Campsite"
        assert map_icon("Point B", "Water SOURCE", "", config) == "Water Source"

    # -------------------------------------------------------------------------
    # PRIORITY: SYMBOL OVER KEYWORD
    # -------------------------------------------------------------------------
    def test_symbol_takes_priority_over_keyword(self, config):
        """Symbol mapping takes priority over keyword matching."""
        # Title says "camp" but symbol says "hazard"
        assert map_icon("Camp with danger", "", "skull", config) == "Hazard"
        # Title says "water" but symbol says "campsite"
        assert map_icon("Water camp", "", "tent", config) == "Campsite"

    # -------------------------------------------------------------------------
    # DEFAULT FALLBACK
    # -------------------------------------------------------------------------
    def test_no_match_returns_location(self, config):
        """No match returns Location as default."""
        assert map_icon("Random waypoint", "No keywords here", "", config) == "Location"
        assert map_icon("Mile 45.2", "", "", config) == "Location"
        assert map_icon("Checkpoint Alpha", "", "", config) == "Location"

    def test_empty_inputs_return_location(self, config):
        """Empty inputs return Location."""
        assert map_icon("", "", "", config) == "Location"

    def test_generic_symbols_allow_keyword_matching(self, config):
        """Generic symbols like 'point' don't block keyword matching."""
        # 'point' is a generic CalTopo symbol - should fall through to keywords
        assert map_icon("Cow Camp Mile 31.9", "", "point", config) == "Campsite"
        assert map_icon("Deadfall ahead", "", "point", config) == "Hazard"
        assert map_icon("Water refill", "", "point", config) == "Water Source"


class TestIconEmojiConfigRemoved:
    """Regression tests: `icon_emojis` config is no longer supported."""

    def test_icon_emojis_key_is_rejected(self, tmp_path):
        cfg = tmp_path / "cairn_config.yaml"
        cfg.write_text('icon_emojis:\n  Location: "📍"\n', encoding="utf-8")

        with pytest.raises(ValueError) as e:
            load_config(cfg)

        assert "icon_emojis" in str(e.value)
