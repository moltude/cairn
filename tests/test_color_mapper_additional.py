from cairn.core.color_mapper import ColorMapper, pattern_to_style, stroke_width_to_weight


def test_pattern_to_style_basic_mappings():
    assert pattern_to_style("") == "solid"
    assert pattern_to_style("solid") == "solid"
    assert pattern_to_style("dash") == "dash"
    assert pattern_to_style("dashed") == "dash"
    assert pattern_to_style("dot") == "dot"
    assert pattern_to_style("dotted") == "dot"


def test_pattern_to_style_unknown_defaults_to_solid():
    assert pattern_to_style("zigzag") == "solid"


def test_stroke_width_to_weight_threshold_and_errors():
    assert stroke_width_to_weight(1) == "4.0"
    assert stroke_width_to_weight(4) == "4.0"
    assert stroke_width_to_weight(4.1) == "6.0"
    assert stroke_width_to_weight("5") == "6.0"
    assert stroke_width_to_weight(None) == "4.0"
    assert stroke_width_to_weight("nope") == "4.0"


def test_parse_color_hex_rgb_rgba_and_fallbacks():
    assert ColorMapper.parse_color("") == (8, 122, 255)  # default
    assert ColorMapper.parse_color("#FF0000") == (255, 0, 0)
    assert ColorMapper.parse_color("FF0000") == (255, 0, 0)
    assert ColorMapper.parse_color("rgba(1,2,3,1)") == (1, 2, 3)
    assert ColorMapper.parse_color("rgb(4, 5, 6)") == (4, 5, 6)
    assert ColorMapper.parse_color("not-a-color") == (8, 122, 255)  # fallback


def test_color_mapper_get_color_name_known_and_custom():
    assert ColorMapper.get_color_name("rgba(8,122,255,1)") == "blue"
    assert ColorMapper.get_color_name("rgba(255,0,255,1)") == "fuchsia"  # track-only color
    assert ColorMapper.get_color_name("rgba(123,123,123,1)") == "custom"


# --- CalTopo line patterns (roadmap Phase 7) ----------------------------------------

import pytest  # noqa: E402

from cairn.core.color_mapper import CALTOPO_PATTERN_STYLES, pattern_to_style  # noqa: E402


@pytest.mark.parametrize("pattern, style", [
    ("solid", "solid"),
    # CalTopo's dashed line as its GeoJSON writes it (6 Bitterroots lines).
    ("M0 -1 L0 1,,8,F", "dash"),
    (" M0 -1 L0 1,,8,F ", "dash"),
    # Cairn's own names, written to and read back from onX.
    ("dash", "dash"), ("dashed", "dash"), ("dot", "dot"), ("dotted", "dot"),
    # Unverified CalTopo values (arrows, dots) and anything else: solid.
    ("M-3 3 L0 0 L3 3,,20,F", "solid"),
    ("", "solid"), (None, "solid"), ("unknown", "solid"),
])
def test_pattern_to_style(pattern, style):
    assert pattern_to_style(pattern) == style


def test_every_verified_caltopo_pattern_maps_to_an_onx_style():
    assert set(CALTOPO_PATTERN_STYLES.values()) <= {"solid", "dash", "dot"}


def test_bitterroots_dashed_lines_export_as_onx_dash(tmp_path):
    """End to end: the 6 dashed CalTopo lines reach the GPX as onx:style dash."""
    import json
    from pathlib import Path

    from cairn.core.parser import parse_geojson
    from cairn.core.writers import write_gpx_tracks_maybe_split

    src = Path(__file__).parent / "fixtures" / "bitterroots" / "Bitterroots__Complete_.json"
    dashed = {f["properties"]["title"] for f in json.loads(src.read_text())["features"]
              if (f.get("properties") or {}).get("pattern") == "M0 -1 L0 1,,8,F"}
    assert len(dashed) == 6
    tracks = [t for d in parse_geojson(src).folders.values() for t in d["tracks"] if t.title in dashed]
    (path, _s, n), = write_gpx_tracks_maybe_split(tracks, tmp_path / "t.gpx", "x")
    assert n == 6
    assert path.read_text().count("<onx:style>dash</onx:style>") == 6
