"""
Fuzzy matching system for mapping CalTopo symbols to OnX Backcountry icons.

This module provides intelligent symbol matching using string similarity algorithms
and semantic keyword matching to suggest the best OnX icon for unmapped CalTopo symbols.
"""

from difflib import SequenceMatcher
from typing import List, Tuple, Optional, Dict
import re


class FuzzyIconMatcher:
    """Intelligent fuzzy matching for unmapped CalTopo symbols to OnX icons."""

    def __init__(self, valid_icons: List[str]):
        """
        Initialize the fuzzy matcher.

        Args:
            valid_icons: List of valid OnX icon names
        """
        self.valid_icons = valid_icons
        self.synonyms = self._build_synonym_map()

    def find_best_matches(self, symbol: str, top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Find best matching OnX icons for a CalTopo symbol.

        Args:
            symbol: CalTopo symbol to match
            top_n: Number of top matches to return

        Returns:
            List of (icon_name, confidence_score) tuples, sorted by confidence
        """
        # Normalize input
        normalized = self._normalize_symbol(symbol)

        # Calculate scores for all icons
        scores = []
        for icon in self.valid_icons:
            score = self._calculate_similarity(normalized, icon)
            scores.append((icon, score))

        # Sort by score (descending) and return top N
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol for matching.

        Removes common prefixes/suffixes and standardizes format.

        Args:
            symbol: Raw symbol string

        Returns:
            Normalized symbol string
        """
        # Remove common prefixes
        symbol = re.sub(r'^(marker-|icon-|symbol-|caltopo-)', '', symbol, flags=re.IGNORECASE)

        # Remove trailing numbers (e.g., "climb-1" -> "climb")
        symbol = re.sub(r'(-\d+|_\d+)$', '', symbol)

        # Replace underscores and hyphens with spaces
        symbol = symbol.replace('_', ' ').replace('-', ' ')

        return symbol.lower().strip()

    def _calculate_similarity(self, symbol: str, icon: str) -> float:
        """
        Calculate similarity score between symbol and icon.

        Uses multiple scoring methods and combines them with weights.

        Args:
            symbol: Normalized symbol string
            icon: OnX icon name

        Returns:
            Similarity score between 0.0 and 1.0
        """
        icon_lower = icon.lower()

        # 1. Exact match
        if symbol == icon_lower:
            return 1.0

        # 2. Substring match
        if symbol in icon_lower:
            return 0.95
        if icon_lower in symbol:
            return 0.9

        # 3. Sequence matching (Levenshtein-like)
        seq_score = SequenceMatcher(None, symbol, icon_lower).ratio()

        # 4. Keyword/synonym matching
        keyword_score = self._keyword_match(symbol, icon)

        # 5. Word-level matching (for multi-word icons)
        word_score = self._word_match(symbol, icon_lower)

        # Weighted combination
        return (seq_score * 0.4) + (keyword_score * 0.4) + (word_score * 0.2)

    def _keyword_match(self, symbol: str, icon: str) -> float:
        """
        Match based on semantic keywords and synonyms.

        Args:
            symbol: Normalized symbol string
            icon: OnX icon name

        Returns:
            Keyword match score between 0.0 and 1.0
        """
        icon_lower = icon.lower()

        # Check if symbol matches any synonym group that includes the icon
        for key, related in self.synonyms.items():
            if key in symbol or symbol in key:
                if any(term in icon_lower for term in related):
                    return 0.85

        # Check if icon matches any synonym group that includes the symbol
        for key, related in self.synonyms.items():
            if key in icon_lower or icon_lower in key:
                if any(term in symbol for term in related):
                    return 0.8

        return 0.0

    def _word_match(self, symbol: str, icon_lower: str) -> float:
        """
        Match based on individual words in multi-word strings.

        Args:
            symbol: Normalized symbol string
            icon_lower: Lowercase icon name

        Returns:
            Word match score between 0.0 and 1.0
        """
        symbol_words = set(symbol.split())
        icon_words = set(icon_lower.split())

        if not symbol_words or not icon_words:
            return 0.0

        # Calculate Jaccard similarity
        intersection = symbol_words & icon_words
        union = symbol_words | icon_words

        if union:
            return len(intersection) / len(union)

        return 0.0

    def _build_synonym_map(self) -> Dict[str, List[str]]:
        """
        Build a map of semantic synonyms and related terms.

        Returns:
            Dictionary mapping keywords to lists of related terms
        """
        return {
            # Climbing
            'climb': ['climbing', 'rappel', 'caving', 'ascent'],

            # Camping
            'camp': ['campsite', 'campground', 'camping', 'camp area', 'camp backcountry'],
            'tent': ['campsite', 'camping', 'camp'],
            'bivy': ['camp backcountry', 'bivouac'],

            # Water
            'water': ['creek', 'stream', 'lake', 'river', 'spring', 'water source'],
            'spring': ['water source', 'water'],
            'falls': ['waterfall'],
            'hot': ['hot spring', 'thermal', 'geyser'],

            # Winter sports
            'ski': ['skiing', 'xc skiing', 'ski touring', 'backcountry'],
            'skin': ['ski touring', 'skin track', 'uptrack'],
            'tour': ['ski touring', 'touring'],
            'snowboard': ['snowboarder', 'boarding'],
            'snow': ['snowmobile', 'snowpark', 'snow pit'],

            # Hazards
            'danger': ['hazard', 'caution', 'warning'],
            'avy': ['avalanche', 'hazard', 'slide'],
            'avalanche': ['hazard', 'avy', 'slide path'],

            # Transportation
            'car': ['parking', 'vehicle', 'lot'],
            'parking': ['lot', 'trailhead'],
            'bike': ['bicycle', 'mountain biking', 'dirt bike'],
            'atv': ['quad', '4x4'],

            # Trails
            'trail': ['trailhead', 'hike', 'path'],
            'trailhead': ['trail head', 'th', 'parking'],
            'hike': ['hiking', 'backpacker', 'mountaineer'],

            # Peaks
            'peak': ['summit', 'mountain', 'top'],
            'summit': ['peak', 'top', 'mountain'],

            # Observation
            'view': ['viewpoint', 'vista', 'overlook', 'lookout'],
            'camera': ['photo', 'picture'],
            'lookout': ['observation', 'tower', 'view'],

            # Shelters
            'cabin': ['hut', 'yurt', 'shelter'],
            'shelter': ['refuge', 'cabin', 'house'],

            # Water activities
            'boat': ['canoe', 'kayak', 'raft'],
            'paddle': ['canoe', 'kayak'],
            'raft': ['rafting', 'put in', 'take out'],

            # Wildlife
            'bird': ['eagle'],
            'fish': ['fishing'],

            # Facilities
            'food': ['restaurant', 'food source', 'aid station'],
            'emergency': ['phone', 'sos', 'rescue'],
        }
