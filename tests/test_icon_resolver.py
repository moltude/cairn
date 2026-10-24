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
