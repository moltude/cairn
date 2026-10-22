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

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "bitterroots"


class TestCaltopoGpxParser:
    """Basic parsing tests for CalTopo GPX files."""

    def test_parse_bitterroots_gpx(self) -> None:
        """Test parsing the bitterroots demo GPX file."""
        gpx_path = FIXTURES_DIR / "bitterroots_subet.gpx"
        if not gpx_path.exists():
            pytest.skip("Fixture GPX file not found")

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
        gpx_path = FIXTURES_DIR / "bitterroots_subet.gpx"
        if not gpx_path.exists():
            pytest.skip("Fixture GPX file not found")

        parsed = parse_caltopo_gpx(gpx_path)
        folder = parsed.folders["default"]

        for wp in folder["waypoints"]:
            # CalTopo GPX does not contain symbol or color info
            assert wp.symbol == "", f"Expected empty symbol, got: {wp.symbol}"
            assert wp.color == "", f"Expected empty color, got: {wp.color}"

    def test_gpx_waypoints_have_names(self) -> None:
        """Test that GPX waypoints preserve their names."""
        gpx_path = FIXTURES_DIR / "bitterroots_subet.gpx"
        if not gpx_path.exists():
            pytest.skip("Fixture GPX file not found")

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
        gpx_path = FIXTURES_DIR / "bitterroots_subet.gpx"
        json_path = FIXTURES_DIR / "bitterroots_subset.json"

        if not gpx_path.exists() or not json_path.exists():
            pytest.skip("Fixture files not found")

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
        gpx_path = FIXTURES_DIR / "bitterroots_subet.gpx"
        json_path = FIXTURES_DIR / "bitterroots_subset.json"

        if not gpx_path.exists() or not json_path.exists():
            pytest.skip("Fixture files not found")

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
        gpx_path = FIXTURES_DIR / "bitterroots_subet.gpx"
        json_path = FIXTURES_DIR / "bitterroots_subset.json"

        if not gpx_path.exists() or not json_path.exists():
            pytest.skip("Fixture files not found")

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

    def test_camp_keyword_maps_to_camp(self) -> None:
        """Test that 'camp' in title maps to Camp icon."""
        from cairn.core.mapper import map_icon

        # GPX has empty symbol, so keyword mapping should trigger
        icon = map_icon("Camp spot", "", "")
        assert icon == "Camp"

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


# --- Garmin DisplayColor and <sym> (roadmap Phase 7) -----------------------------------

from cairn.io.caltopo_gpx import GARMIN_DISPLAY_COLORS  # noqa: E402

_GPX_HEAD = ('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1" '
             'xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" creator="CALTOPO" '
             'version="1.1">')


def _gpx(tmp_path: Path, body: str):
    p = tmp_path / "c.gpx"
    p.write_text(_GPX_HEAD + body + "</gpx>", encoding="utf-8")
    return parse_caltopo_gpx(p).folders["default"]


def _trk(name: str, color: str = "") -> str:
    ext = (f"<extensions><gpxx:TrackExtension><gpxx:DisplayColor>{color}</gpxx:DisplayColor>"
           "</gpxx:TrackExtension></extensions>" if color else "")
    return (f"<trk><name>{name}</name>{ext}<trkseg><trkpt lat=\"1\" lon=\"1\"/>"
            "<trkpt lat=\"2\" lon=\"2\"/></trkseg></trk>")


def test_garmin_table_is_the_schemas_16_colours():
    # The DisplayColor_t enumeration in GpxExtensionsv3.xsd, minus Transparent.
    assert sorted(GARMIN_DISPLAY_COLORS) == sorted([
        "Black", "DarkRed", "DarkGreen", "DarkYellow", "DarkBlue", "DarkMagenta", "DarkCyan",
        "LightGray", "DarkGray", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White"])
    # GPSBabel stores BGR; spot-check the byte order was flipped.
    assert (GARMIN_DISPLAY_COLORS["DarkRed"], GARMIN_DISPLAY_COLORS["DarkBlue"],
            GARMIN_DISPLAY_COLORS["Yellow"], GARMIN_DISPLAY_COLORS["Cyan"]) == (
        "#8B0000", "#00008B", "#FFFF00", "#00FFFF")


@pytest.mark.parametrize("name, rgb", sorted(GARMIN_DISPLAY_COLORS.items()))
def test_track_display_color_becomes_stroke(tmp_path, name, rgb):
    (t,) = _gpx(tmp_path, _trk("t", name))["tracks"]
    assert t.stroke == rgb


@pytest.mark.parametrize("value", ["", "Transparent", "red", "Chartreuse"])
def test_missing_transparent_or_unknown_display_color_is_no_colour(tmp_path, value):
    (t,) = _gpx(tmp_path, _trk("t", value))["tracks"]
    assert t.stroke == ""


def test_route_display_color_becomes_stroke(tmp_path):
    body = ('<rte><name>r</name><extensions><gpxx:RouteExtension><gpxx:DisplayColor>Magenta'
            '</gpxx:DisplayColor></gpxx:RouteExtension></extensions>'
            '<rtept lat="1" lon="1"/><rtept lat="2" lon="2"/></rte>')
    (r,) = _gpx(tmp_path, body)["tracks"]
    assert r.stroke == "#FF00FF"


def test_waypoint_sym_becomes_marker_symbol(tmp_path):
    body = ('<wpt lat="1" lon="1"><name>a</name><sym>Campground</sym></wpt>'
            '<wpt lat="1" lon="1"><name>b</name></wpt>')
    a, b = _gpx(tmp_path, body)["waypoints"]
    assert (a.symbol, b.symbol) == ("Campground", "")
    assert (a.color, b.color) == ("", "")


def test_dark_divide_gpx_track_colours_and_notes():
    dd = Path(__file__).parent / "fixtures" / "dark_divide_100" / "caltopo"
    folder = parse_caltopo_gpx(dd / "2027_Dark_Divide_100_Mile_Endurance_Run.gpx").folders["default"]
    strokes = {t.title: t.stroke for t in folder["tracks"]}
    # Every line is red in CalTopo; the one written as lower-case "#ff0000"
    # has no DisplayColor in the GPX.
    assert strokes.pop("10 - Sunrise Peak #2 AS to Juniper Ridge #2 AS") == ""
    assert set(strokes.values()) == {"#FF0000"} and len(strokes) == 11
    # CalTopo GPX does carry notes, newlines included.
    notes = [f.description for k in ("waypoints", "tracks") for f in folder[k]]
    assert sum("\n" in n for n in notes) == 21
