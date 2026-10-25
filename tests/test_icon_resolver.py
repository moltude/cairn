"""Unit tests for cairn.core.icon_resolver."""

from cairn.core.icon_resolver import IconResolver


def test_symbol_exact_match_wins():
    resolver = IconResolver(
        symbol_map={"skull": "Hazard"},
        keyword_map={"Campsite": ["camp"]},
        default_icon="Location",
        generic_symbols=set(),
    )
    decision = resolver.resolve("Base Camp", "", "skull")
    assert decision.icon == "Hazard"
    assert decision.source == "symbol"


def test_generic_symbol_is_ignored_for_symbol_matching():
    resolver = IconResolver(
        symbol_map={"point": "Hazard"},  # would be wrong if used
        keyword_map={"Parking": ["parking"]},
        default_icon="Location",
        generic_symbols={"point"},
    )
    decision = resolver.resolve("Parking lot", "", "point")
    assert decision.icon == "Parking"
    assert decision.source == "keyword"


def test_token_boundary_avoids_th_in_path_false_positive():
    resolver = IconResolver(
        symbol_map={},
        keyword_map={
            "Trailhead": ["th"],
            "Hazard": ["avalanche"],
        },
        default_icon="Location",
        generic_symbols=set(),
    )
    decision = resolver.resolve("Avalanche path", "", "")
    assert decision.icon == "Hazard"


def test_keyword_tie_breaks_by_priority_order():
    # Both icons match one keyword; priority order should win (Parking first).
    resolver = IconResolver(
        symbol_map={},
        keyword_map={
            "Parking": ["parking"],
            "Trailhead": ["trailhead"],
        },
        default_icon="Location",
        generic_symbols=set(),
    )
    decision = resolver.resolve("Trailhead parking", "", "")
    assert decision.icon == "Parking"



def _race_resolver():
    return IconResolver(
        symbol_map={},
        keyword_map={
            "Water Source": ["creek", "spring"],
            "Summit": ["summit", "peak"],
            "Trailhead": ["th", "trailhead"],
            "Food Source": ["food", "aid station"],
        },
        default_icon="Location",
        generic_symbols=set(),
    )


def test_a_tie_in_the_name_goes_to_the_later_word():
    # Place names end in what the place is.
    r = _race_resolver()
    assert r.resolve("Dark Creek AS").icon == "Food Source"
    assert r.resolve("Summit Prairie AS").icon == "Food Source"
    assert r.resolve("Mill Creek TH").icon == "Trailhead"
    assert r.resolve("Trailhead Creek").icon == "Water Source"


def test_as_is_an_aid_station_only_in_capitals():
    r = _race_resolver()
    d = r.resolve("Lewis River AS")
    assert (d.icon, d.matched_terms, d.field) == ("Food Source", ("AS",), "title")
    assert r.resolve("Good as new").icon == "Location"


def test_the_name_decides_before_the_note():
    r = _race_resolver()
    # Before 2026-10-24 name and note were pooled, so a note with more
    # keywords outvoted the name.
    d = r.resolve("Juniper Ridge AS", "Mile 11.9. Water: spring and creek.")
    assert (d.icon, d.field) == ("Food Source", "title")
    d = r.resolve("Point 7", "good spring nearby")
    assert (d.icon, d.field) == ("Water Source", "description")


def _numbered_resolver():
    return IconResolver(
        symbol_map={},
        keyword_map={
            "Camp": ["camp", "tent"],
            "Water Source": ["creek", "lake", "spring"],
            "4x4": ["4x4"],
        },
        default_icon="Location",
        generic_symbols=set(),
    )


def test_trailing_digits_on_a_word_do_not_hide_its_keyword():
    # "Camp2" used to fall back to Location while "Camp 2" resolved to Camp
    # (checked 2026-10-25): the token was "camp2", and no keyword is spelled so.
    r = _numbered_resolver()
    assert r.resolve("Camp2").icon == "Camp"
    assert r.resolve("Camp 2").icon == "Camp"
    assert r.resolve("camp12 west").icon == "Camp"
    d = r.resolve("Point 7", "tent3 here")
    assert (d.icon, d.field) == ("Camp", "description")


def test_pure_numbers_and_keywords_with_digits_still_work():
    r = _numbered_resolver()
    assert r.resolve("2").icon == "Location"
    assert r.resolve("Point 12").icon == "Location"
    assert r.resolve("4x4 road").icon == "4x4"
    assert r.resolve("Old 4x4").icon == "4x4"
    # Leading digits are not trailing digits: "2camp" is not the word camp.
    assert r.resolve("2camp").icon == "Location"


def test_a_numbered_word_keeps_its_position_for_the_tie():
    # ENG-08: a tie goes to the later word, with or without a number on it.
    r = _numbered_resolver()
    assert r.resolve("Camp Lake2").icon == "Water Source"
    assert r.resolve("Lake Camp2").icon == "Camp"
