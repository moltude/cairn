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
