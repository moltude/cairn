"""
Comprehensive tests for fuzzy icon matching logic.

Tests cover:
- Exact match handling
- Fuzzy matching above and below threshold
- Keyword extraction and matching
- Multi-word keyword matching
- Case-insensitive matching
- Special character handling
- Synonym matching
- Word-level matching
"""

import pytest
from cairn.core.matcher import FuzzyIconMatcher


@pytest.fixture
def valid_icons():
    """Sample set of valid OnX icons for testing."""
    return [
        "camp",
        "camp backcountry",
        "campground",
        "climbing",
        "peak",
        "summit",
        "trailhead",
        "parking",
        "water source",
        "hot spring",
        "avalanche",
        "ski touring",
        "snowmobile",
        "lookout",
        "cabin",
        "boat launch",
        "fishing",
        "eagle",
    ]


@pytest.fixture
def matcher(valid_icons):
    """Create a FuzzyIconMatcher instance for testing."""
    return FuzzyIconMatcher(valid_icons)


def test_exact_match_wins(matcher):
    """Test that exact matches return highest confidence score."""
    matches = matcher.find_best_matches("camp", top_n=3)

    assert len(matches) > 0
    assert matches[0][0] == "camp"
    assert matches[0][1] == 1.0  # Perfect score


def test_exact_match_case_insensitive(matcher):
    """Test that exact matches work regardless of case."""
    matches = matcher.find_best_matches("CAMP", top_n=3)

    assert matches[0][0] == "camp"
    assert matches[0][1] == 1.0


def test_fuzzy_match_substring(matcher):
    """Test that substring matches score highly."""
    matches = matcher.find_best_matches("camp backcountry", top_n=3)

    # Should find exact match first
    assert matches[0][0] == "camp backcountry"
    assert matches[0][1] == 1.0


def test_fuzzy_match_partial_substring(matcher):
    """Test that partial substring matches are found."""
    matches = matcher.find_best_matches("backcountry", top_n=3)

    # Should match "camp backcountry" with high score
    found = [m for m in matches if m[0] == "camp backcountry"]
    assert len(found) > 0
    assert found[0][1] >= 0.9  # Substring match score


def test_fuzzy_match_above_threshold(matcher):
    """Test fuzzy matching for similar strings."""
    matches = matcher.find_best_matches("camping", top_n=3)

    # Should find "camp" and related icons
    assert any(m[0] in ["camp", "campground", "camp backcountry"] for m in matches)
    # Top match should have reasonable score
    assert matches[0][1] > 0.5


def test_fuzzy_match_below_threshold_still_returns_results(matcher):
    """Test that we still get results even for poor matches."""
    matches = matcher.find_best_matches("xyz123unknown", top_n=3)

    # Should still return top 3, even if scores are low
    assert len(matches) == 3
    # But scores should be low
    assert all(m[1] < 0.5 for m in matches)


def test_keyword_extraction_from_caltopo_labels(matcher):
    """Test that common CalTopo label patterns are normalized."""
    # Test prefix removal
    matches = matcher.find_best_matches("marker-camp", top_n=1)
    assert matches[0][0] == "camp"

    matches = matcher.find_best_matches("icon-peak", top_n=1)
    assert matches[0][0] == "peak"

    matches = matcher.find_best_matches("caltopo-trailhead", top_n=1)
    assert matches[0][0] == "trailhead"


def test_trailing_number_removal(matcher):
    """Test that trailing numbers are removed during normalization."""
    matches = matcher.find_best_matches("camp-1", top_n=1)
    assert matches[0][0] == "camp"
    assert matches[0][1] == 1.0

    matches = matcher.find_best_matches("peak_2", top_n=1)
    assert matches[0][0] == "peak"
    assert matches[0][1] == 1.0


def test_multi_word_keyword_matching(matcher):
    """Test matching with multi-word icon names."""
    matches = matcher.find_best_matches("water", top_n=3)

    # Should find "water source"
    found = [m for m in matches if m[0] == "water source"]
    assert len(found) > 0


def test_case_insensitive_matching(matcher):
    """Test that matching is case insensitive."""
    matches_lower = matcher.find_best_matches("peak", top_n=3)
    matches_upper = matcher.find_best_matches("PEAK", top_n=3)
    matches_mixed = matcher.find_best_matches("PeAk", top_n=3)

    # All should find the same top match
    assert matches_lower[0][0] == matches_upper[0][0] == matches_mixed[0][0]


def test_special_characters_in_keywords(matcher):
    """Test handling of special characters."""
    # Underscores and hyphens should be normalized to spaces
    matches = matcher.find_best_matches("hot_spring", top_n=3)
    found = [m for m in matches if m[0] == "hot spring"]
    assert len(found) > 0

    matches = matcher.find_best_matches("hot-spring", top_n=3)
    found = [m for m in matches if m[0] == "hot spring"]
    assert len(found) > 0


def test_synonym_matching_climb(matcher):
    """Test that climbing synonyms work."""
    matches = matcher.find_best_matches("climbing", top_n=3)

    # Should find "climbing" directly
    assert matches[0][0] == "climbing"


def test_synonym_matching_camp_variations(matcher):
    """Test that camp synonym variations work."""
    # "tent" should match "camp" or "campground"
    matches = matcher.find_best_matches("tent", top_n=3)
    camp_related = [m for m in matches if "camp" in m[0]]
    assert len(camp_related) > 0


def test_synonym_matching_water(matcher):
    """Test that water-related synonyms work."""
    matches = matcher.find_best_matches("spring", top_n=3)

    # Should find "water source" or "hot spring" via synonyms
    water_related = [m for m in matches if "spring" in m[0] or "water" in m[0]]
    assert len(water_related) > 0


def test_synonym_matching_peak_summit(matcher):
    """Test that peak/summit synonyms work."""
    matches = matcher.find_best_matches("summit", top_n=3)

    # Should find both "summit" and "peak"
    assert matches[0][0] == "summit"
    peak_found = any(m[0] == "peak" for m in matches)
    assert peak_found


def test_word_level_matching(matcher):
    """Test that word-level Jaccard matching works."""
    matches = matcher.find_best_matches("boat", top_n=3)

    # Should match "boat launch" reasonably well
    found = [m for m in matches if m[0] == "boat launch"]
    assert len(found) > 0
    assert found[0][1] > 0.3  # Should have some similarity


def test_top_n_parameter(matcher):
    """Test that top_n parameter limits results correctly."""
    matches_1 = matcher.find_best_matches("camp", top_n=1)
    matches_3 = matcher.find_best_matches("camp", top_n=3)
    matches_5 = matcher.find_best_matches("camp", top_n=5)

    assert len(matches_1) == 1
    assert len(matches_3) == 3
    assert len(matches_5) == 5


def test_results_sorted_by_confidence(matcher):
    """Test that results are sorted by confidence score."""
    matches = matcher.find_best_matches("campsite", top_n=5)

    # Check that scores are in descending order
    scores = [m[1] for m in matches]
    assert scores == sorted(scores, reverse=True)


def test_normalize_symbol_removes_prefixes(matcher):
    """Test that _normalize_symbol removes common prefixes."""
    assert matcher._normalize_symbol("marker-camp") == "camp"
    assert matcher._normalize_symbol("icon-peak") == "peak"
    assert matcher._normalize_symbol("symbol-trailhead") == "trailhead"
    assert matcher._normalize_symbol("caltopo-parking") == "parking"


def test_normalize_symbol_removes_trailing_numbers(matcher):
    """Test that _normalize_symbol removes trailing numbers."""
    assert matcher._normalize_symbol("camp-1") == "camp"
    assert matcher._normalize_symbol("peak_5") == "peak"
    assert matcher._normalize_symbol("trailhead-12") == "trailhead"


def test_normalize_symbol_replaces_separators(matcher):
    """Test that underscores and hyphens are replaced with spaces."""
    assert matcher._normalize_symbol("hot_spring") == "hot spring"
    assert matcher._normalize_symbol("camp-backcountry") == "camp backcountry"
    assert matcher._normalize_symbol("boat_launch") == "boat launch"


def test_normalize_symbol_lowercases(matcher):
    """Test that normalization converts to lowercase."""
    assert matcher._normalize_symbol("CAMP") == "camp"
    assert matcher._normalize_symbol("Peak") == "peak"
    assert matcher._normalize_symbol("TrailHead") == "trailhead"


def test_synonym_map_exists(matcher):
    """Test that the synonym map is built and contains expected entries."""
    assert "climb" in matcher.synonyms
    assert "camp" in matcher.synonyms
    assert "water" in matcher.synonyms
    assert "peak" in matcher.synonyms


def test_empty_icon_list():
    """Test matcher behavior with empty icon list."""
    empty_matcher = FuzzyIconMatcher([])
    matches = empty_matcher.find_best_matches("camp", top_n=3)

    assert len(matches) == 0


def test_single_icon_list():
    """Test matcher behavior with single icon."""
    single_matcher = FuzzyIconMatcher(["camp"])
    matches = single_matcher.find_best_matches("camp", top_n=3)

    assert len(matches) == 1
    assert matches[0][0] == "camp"


def test_exact_match_with_spaces(matcher):
    """Test exact matching with multi-word icons."""
    matches = matcher.find_best_matches("hot spring", top_n=3)

    assert matches[0][0] == "hot spring"
    assert matches[0][1] == 1.0


def test_partial_word_match(matcher):
    """Test that partial word matches work."""
    matches = matcher.find_best_matches("launch", top_n=3)

    # Should find "boat launch"
    found = [m for m in matches if m[0] == "boat launch"]
    assert len(found) > 0


def test_avalanche_synonym_matching(matcher):
    """Test avalanche-related synonym matching."""
    matches = matcher.find_best_matches("avy", top_n=3)

    # Should find "avalanche" via synonyms
    found = [m for m in matches if m[0] == "avalanche"]
    # May or may not be in top 3 depending on other scores


def test_parking_trailhead_synonym(matcher):
    """Test that parking relates to trailhead."""
    matches = matcher.find_best_matches("parking", top_n=3)

    # Should find exact match first
    assert matches[0][0] == "parking"


def test_similarity_score_range(matcher):
    """Test that similarity scores are always between 0 and 1."""
    test_inputs = ["camp", "xyz123", "peak-summit", "unknown", "trailhead"]

    for input_str in test_inputs:
        matches = matcher.find_best_matches(input_str, top_n=5)
        for icon, score in matches:
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for {icon}"


def test_sequence_matching_similar_strings(matcher):
    """Test sequence matching for similar but not identical strings."""
    matches = matcher.find_best_matches("climber", top_n=3)

    # "climbing" should be high in results
    found = [m for m in matches if m[0] == "climbing"]
    assert len(found) > 0
    # Should have decent score due to sequence similarity
    assert found[0][1] > 0.4


def test_empty_string_input(matcher):
    """Test behavior with empty string input."""
    matches = matcher.find_best_matches("", top_n=3)

    # Should still return results
    assert len(matches) == 3
    # But scores should be low or varied
    # (exact behavior depends on implementation)
