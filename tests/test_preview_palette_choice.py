from cairn.core.color_mapper import ColorMapper
from cairn.core.preview import _match_palette_color_choice


def test_match_palette_color_choice_accepts_color_names_case_insensitive():
    assert _match_palette_color_choice("BLUE", ColorMapper.WAYPOINT_PALETTE) == "rgba(8,122,255,1)"
    assert _match_palette_color_choice("orange", ColorMapper.WAYPOINT_PALETTE) == "rgba(255,51,0,1)"
    assert _match_palette_color_choice("Orange", ColorMapper.WAYPOINT_PALETTE) == "rgba(255,51,0,1)"
    assert _match_palette_color_choice("ORANGE", ColorMapper.WAYPOINT_PALETTE) == "rgba(255,51,0,1)"


def test_match_palette_color_choice_returns_none_for_unknown():
    assert _match_palette_color_choice("notacolor", ColorMapper.WAYPOINT_PALETTE) is None
