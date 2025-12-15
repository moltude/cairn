"""Unit tests for cairn.core.color_mapper."""

from cairn.core.color_mapper import ColorMapper


def test_track_color_exact_match_roundtrips():
    # Test that exact track colors round-trip correctly
    assert ColorMapper.map_track_color("rgba(255,51,0,1)") == "rgba(255,51,0,1)"  # red-orange
    assert ColorMapper.map_track_color("rgba(8,122,255,1)") == "rgba(8,122,255,1)"  # blue
    assert ColorMapper.map_track_color("rgba(255,0,255,1)") == "rgba(255,0,255,1)"  # fuchsia (track-only)


def test_track_color_quantizes_hex_to_track_palette():
    # Pure green (#00FF00) should map closest to lime in the track palette
    assert ColorMapper.map_track_color("#00FF00") == "rgba(132,212,0,1)"  # lime


def test_waypoint_color_exact_match_roundtrips():
    assert ColorMapper.map_waypoint_color("FF0000") == "rgba(255,0,0,1)"
    assert ColorMapper.map_waypoint_color("rgba(132,212,0,1)") == "rgba(132,212,0,1)"
