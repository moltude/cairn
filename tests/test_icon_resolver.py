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

