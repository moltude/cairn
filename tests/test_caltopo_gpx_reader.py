"""
Tests for CalTopo GPX parser.

These tests verify that CalTopo GPX exports are correctly parsed into
ParsedData structures compatible with the TUI workflow.
"""

from pathlib import Path
import tempfile
import pytest

from cairn.io.caltopo_gpx import parse_caltopo_gpx
from cairn.core.parser import parse_geojson


class TestCaltopoGpxParser:
    """Basic parsing tests for CalTopo GPX files."""

    def test_parse_bitterroots_gpx(self) -> None:
        """Test parsing the bitterroots demo GPX file."""
        gpx_path = Path("demo/bitterroots/bitterroots_subet.gpx")
        if not gpx_path.exists():
            pytest.skip("Demo GPX file not found")
        
        parsed = parse_caltopo_gpx(gpx_path)
        
        # Should have a single default folder
        assert "default" in parsed.folders
        assert len(parsed.folders) == 1
        
        # Check stats
        stats = parsed.get_folder_stats("default")
        assert stats["waypoints"] == 10  # 10 waypoints in the demo file
        assert stats["tracks"] == 0
        assert stats["shapes"] == 0
    
    def test_gpx_waypoints_have_empty_symbol_and_color(self) -> None:
        """Test that GPX waypoints have empty symbol and color (triggers OnX defaults)."""
        gpx_path = Path("demo/bitterroots/bitterroots_subet.gpx")
        if not gpx_path.exists():
            pytest.skip("Demo GPX file not found")
        
        parsed = parse_caltopo_gpx(gpx_path)
        folder = parsed.folders["default"]
        
        for wp in folder["waypoints"]:
            # CalTopo GPX does not contain symbol or color info
            assert wp.symbol == "", f"Expected empty symbol, got: {wp.symbol}"
            assert wp.color == "", f"Expected empty color, got: {wp.color}"
    
    def test_gpx_waypoints_have_names(self) -> None:
        """Test that GPX waypoints preserve their names."""
        gpx_path = Path("demo/bitterroots/bitterroots_subet.gpx")
        if not gpx_path.exists():
            pytest.skip("Demo GPX file not found")
        
        parsed = parse_caltopo_gpx(gpx_path)
        folder = parsed.folders["default"]
        
        names = [wp.title for wp in folder["waypoints"]]
        
        # Check some expected names from the demo file
        assert "Main Wall- Lost horse canyon" in names
        assert "Camp spot" in names
        assert "Camping" in names


class TestCaltopoGpxJsonParity:
    """Tests comparing GPX and JSON parsing of the same map."""

    def test_same_waypoint_count(self) -> None:
        """Test that GPX and JSON have the same number of waypoints."""
        gpx_path = Path("demo/bitterroots/bitterroots_subet.gpx")
        json_path = Path("demo/bitterroots/bitterroots_subset.json")
        
        if not gpx_path.exists() or not json_path.exists():
            pytest.skip("Demo files not found")
        
        gpx_parsed = parse_caltopo_gpx(gpx_path)
        json_parsed = parse_geojson(json_path)
        
        gpx_stats = gpx_parsed.get_folder_stats("default")
        
        # Sum waypoints across all JSON folders
        json_wp_count = sum(
            len(folder.get("waypoints", []))
            for folder in json_parsed.folders.values()
        )
        
        assert gpx_stats["waypoints"] == json_wp_count
    
    def test_same_waypoint_names(self) -> None:
        """Test that GPX and JSON have the same waypoint names."""
        gpx_path = Path("demo/bitterroots/bitterroots_subet.gpx")
        json_path = Path("demo/bitterroots/bitterroots_subset.json")
        
        if not gpx_path.exists() or not json_path.exists():
            pytest.skip("Demo files not found")
        
        gpx_parsed = parse_caltopo_gpx(gpx_path)
        json_parsed = parse_geojson(json_path)
        
        gpx_names = {wp.title for wp in gpx_parsed.folders["default"]["waypoints"]}
        
        json_names = set()
        for folder in json_parsed.folders.values():
            for wp in folder.get("waypoints", []):
                json_names.add(wp.title)
        
        assert gpx_names == json_names
    
    def test_json_has_icons_gpx_does_not(self) -> None:
        """Test that JSON has icons but GPX does not."""
        gpx_path = Path("demo/bitterroots/bitterroots_subet.gpx")
        json_path = Path("demo/bitterroots/bitterroots_subset.json")
        
        if not gpx_path.exists() or not json_path.exists():
            pytest.skip("Demo files not found")
        
        gpx_parsed = parse_caltopo_gpx(gpx_path)
        json_parsed = parse_geojson(json_path)
        
        # GPX has empty symbols
        gpx_symbols = {wp.symbol for wp in gpx_parsed.folders["default"]["waypoints"]}
        assert gpx_symbols == {""}, "GPX should have empty symbols"
        
        # JSON has actual symbols
        json_symbols = set()
        for folder in json_parsed.folders.values():
            for wp in folder.get("waypoints", []):
                json_symbols.add(wp.symbol)
        
        # JSON should have at least some non-empty symbols
        assert "" not in json_symbols or len(json_symbols) > 1, "JSON should have symbols"
        assert any(s for s in json_symbols), "JSON should have non-empty symbols"


class TestCaltopoGpxEdgeCases:
    """Edge case tests for CalTopo GPX parser."""

    def test_empty_gpx_raises_error(self) -> None:
        """Test that an empty GPX file raises an error."""
        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(b"")
            f.flush()
            
            with pytest.raises(ValueError, match="empty"):
                parse_caltopo_gpx(Path(f.name))
    
    def test_gpx_no_features_raises_error(self) -> None:
        """Test that a GPX with no features raises an error."""
        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False, mode="w") as f:
            f.write('<?xml version="1.0"?>\n')
            f.write('<gpx xmlns="http://www.topografix.com/GPX/1/1"></gpx>')
            f.flush()
            
            with pytest.raises(ValueError, match="No valid features"):
                parse_caltopo_gpx(Path(f.name))
    
    def test_gpx_with_tracks(self) -> None:
        """Test parsing a GPX with tracks."""
        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False, mode="w") as f:
            f.write('''<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" creator="CALTOPO" version="1.1">
  <trk>
    <name>Test Track</name>
    <trkseg>
      <trkpt lat="46.0" lon="-114.0"><ele>1000</ele></trkpt>
      <trkpt lat="46.1" lon="-114.1"><ele>1100</ele></trkpt>
    </trkseg>
  </trk>
</gpx>''')
            f.flush()
            
            parsed = parse_caltopo_gpx(Path(f.name))
            stats = parsed.get_folder_stats("default")
            
            assert stats["waypoints"] == 0
            assert stats["tracks"] == 1
            
            track = parsed.folders["default"]["tracks"][0]
            assert track.title == "Test Track"
    
    def test_gpx_with_routes(self) -> None:
        """Test parsing a GPX with routes."""
        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False, mode="w") as f:
            f.write('''<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" creator="CALTOPO" version="1.1">
  <rte>
    <name>Test Route</name>
    <rtept lat="46.0" lon="-114.0"></rtept>
    <rtept lat="46.1" lon="-114.1"></rtept>
  </rte>
</gpx>''')
            f.flush()
            
            parsed = parse_caltopo_gpx(Path(f.name))
            stats = parsed.get_folder_stats("default")
            
            # Routes are parsed as tracks
            assert stats["tracks"] == 1
            
            track = parsed.folders["default"]["tracks"][0]
            assert track.title == "Test Route"
    
    def test_gpx_invalid_coordinates_skipped(self) -> None:
        """Test that invalid coordinates are skipped."""
        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False, mode="w") as f:
            f.write('''<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" creator="CALTOPO" version="1.1">
  <wpt lat="46.0" lon="-114.0"><name>Valid</name></wpt>
  <wpt lat="999" lon="-114.0"><name>Invalid Lat</name></wpt>
  <wpt lat="46.0" lon="abc"><name>Invalid Lon</name></wpt>
</gpx>''')
            f.flush()
            
            parsed = parse_caltopo_gpx(Path(f.name))
            stats = parsed.get_folder_stats("default")
            
            # Only the valid waypoint should be parsed
            assert stats["waypoints"] == 1
    
    def test_gpx_missing_name_gets_default(self) -> None:
        """Test that waypoints without names get default names."""
        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False, mode="w") as f:
            f.write('''<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" creator="CALTOPO" version="1.1">
  <wpt lat="46.0" lon="-114.0"></wpt>
</gpx>''')
            f.flush()
            
            parsed = parse_caltopo_gpx(Path(f.name))
            wp = parsed.folders["default"]["waypoints"][0]
            
            assert wp.title == "Waypoint 1"
    
    def test_gpx_with_description(self) -> None:
        """Test that descriptions are parsed from <desc> element."""
        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False, mode="w") as f:
            f.write('''<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" creator="CALTOPO" version="1.1">
  <wpt lat="46.0" lon="-114.0">
    <name>Test Point</name>
    <desc>This is a description</desc>
  </wpt>
</gpx>''')
            f.flush()
            
            parsed = parse_caltopo_gpx(Path(f.name))
            wp = parsed.folders["default"]["waypoints"][0]
            
            assert wp.description == "This is a description"


class TestKeywordIconMapping:
    """Test that keyword-based icon mapping works for GPX waypoints."""

    def test_camp_keyword_maps_to_campsite(self) -> None:
        """Test that 'camp' in title maps to Campsite icon."""
        from cairn.core.mapper import map_icon
        
        # GPX has empty symbol, so keyword mapping should trigger
        icon = map_icon("Camp spot", "", "")
        assert icon == "Campsite"
    
    def test_water_keyword_maps_to_water_source(self) -> None:
        """Test that 'water' in title maps to Water Source icon."""
        from cairn.core.mapper import map_icon
        
        icon = map_icon("Water refill point", "", "")
        assert icon == "Water Source"
    
    def test_unknown_title_maps_to_location(self) -> None:
        """Test that unknown titles map to Location icon."""
        from cairn.core.mapper import map_icon
        
        icon = map_icon("Some Random Place", "", "")
        assert icon == "Location"


class TestOnxDefaults:
    """Test that OnX defaults are used for GPX data."""

    def test_location_icon_gets_blue_color(self) -> None:
        """Test that Location icon gets blue color."""
        from cairn.core.config import get_icon_color
        
        color = get_icon_color("Location")
        assert color == "rgba(8,122,255,1)"  # Blue
    
    def test_empty_track_color_defaults_to_blue(self) -> None:
        """Test that empty track color defaults to blue."""
        from cairn.core.color_mapper import ColorMapper
        
        rgba = ColorMapper.map_track_color("")
        assert rgba == "rgba(8,122,255,1)"  # Blue

