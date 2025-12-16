from cairn.core.preview import _color_square_from_rgb


def test_color_square_uses_foreground_dot_for_typical_colors():
    s = _color_square_from_rgb(8, 122, 255)
    assert "on rgb(" not in s
    assert "]●[/]" in s


def test_color_square_contrasts_black_and_white():
    assert _color_square_from_rgb(0, 0, 0) == "[rgb(0,0,0)]●[/]"
    assert _color_square_from_rgb(255, 255, 255) == "[rgb(255,255,255)]●[/]"
