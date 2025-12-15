"""
Explainable icon selection for CalTopo → OnX mapping.

Historically Cairn used a simple "layered" approach:
1) try symbol match
2) otherwise try keyword match (first match wins)
3) otherwise default

This module keeps the same high-level precedence, but makes keyword selection
deterministic and explainable by producing a structured decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Sequence, Set, Tuple

import re


IconSource = Literal["symbol", "keyword", "default"]


@dataclass(frozen=True)
class IconDecision:
    """Result of icon resolution with explanation."""

    icon: str
    score: float
    source: IconSource
    reasons: Tuple[str, ...] = ()
    matched_terms: Tuple[str, ...] = ()


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class IconResolver:
    """
    Resolve the best OnX icon for a waypoint.

    Inputs:
    - CalTopo marker symbol (strongest signal when non-generic)
    - waypoint title/description (keyword scoring)

    Determinism:
    - keyword ties break by the configured keyword map order, then alphabetically
    """

    def __init__(
        self,
        *,
        symbol_map: Dict[str, str],
        keyword_map: Dict[str, List[str]],
        default_icon: str = "Location",
        generic_symbols: Set[str] | None = None,
    ):
        self._symbol_map = symbol_map
        self._keyword_map = keyword_map
        self._default_icon = default_icon
        self._generic_symbols = generic_symbols or set()

        # Preserve dict insertion order as an explicit priority list.
        self._keyword_priority: List[str] = list(keyword_map.keys())

        # Pre-normalize keyword lists for speed.
        normalized: Dict[str, Tuple[str, ...]] = {}
        for icon, kws in keyword_map.items():
            cleaned = []
            for kw in kws or []:
                kw_norm = str(kw).strip().lower()
                if kw_norm:
                    cleaned.append(kw_norm)
            normalized[icon] = tuple(cleaned)
        self._normalized_keywords = normalized

    def resolve(self, title: str, description: str = "", symbol: str = "") -> IconDecision:
        title = title or ""
        description = description or ""
        symbol = symbol or ""

        symbol_norm = symbol.strip().lower()

        # 1) Symbol match (if non-generic).
        if symbol_norm and symbol_norm not in self._generic_symbols:
            # Exact match
            if symbol_norm in self._symbol_map:
                icon = self._symbol_map[symbol_norm]
                return IconDecision(
                    icon=icon,
                    score=1.0,
                    source="symbol",
                    reasons=(f"symbol exact match '{symbol_norm}' → '{icon}'",),
                    matched_terms=(symbol_norm,),
                )

            # Substring match: pick the most specific (longest key).
            substring_matches: List[Tuple[int, str, str]] = []
            for key, icon in self._symbol_map.items():
                if key and key in symbol_norm:
                    substring_matches.append((len(key), key, icon))
            if substring_matches:
                substring_matches.sort(key=lambda t: (t[0], t[1]), reverse=True)
                _, key, icon = substring_matches[0]
                return IconDecision(
                    icon=icon,
                    score=0.9,
                    source="symbol",
                    reasons=(f"symbol substring match '{key}' in '{symbol_norm}' → '{icon}'",),
                    matched_terms=(key,),
                )

        # 2) Keyword scoring.
        text = f"{title} {description}".lower()
        tokens = set(_TOKEN_RE.findall(text))

        best: IconDecision | None = None
        best_points: int = 0
        best_matches: Tuple[str, ...] = ()

        for icon in self._keyword_priority:
            kws = self._normalized_keywords.get(icon, ())
            if not kws:
                continue

            matched: List[str] = []
            points = 0
            for kw in kws:
                if " " in kw:
                    # Phrase match: simple substring
                    if kw in text:
                        matched.append(kw)
                        points += 1
                else:
                    # Token match: avoids false positives like 'th' in 'path'
                    if kw in tokens:
                        matched.append(kw)
                        points += 1

            if points <= 0:
                continue

            # Construct decision; score is a stable, explainable "points" value.
            decision = IconDecision(
                icon=icon,
                score=float(points),
                source="keyword",
                reasons=(f"keyword matches for '{icon}': {', '.join(matched)}",),
                matched_terms=tuple(matched),
            )

            if best is None:
                best = decision
                best_points = points
                best_matches = decision.matched_terms
                continue

            # Prefer higher points, then more distinct matches, then priority order already ensures stability.
            if points > best_points:
                best = decision
                best_points = points
                best_matches = decision.matched_terms
            elif points == best_points:
                if len(decision.matched_terms) > len(best_matches):
                    best = decision
                    best_matches = decision.matched_terms

        if best is not None:
            return best

        # 3) Default
        return IconDecision(
            icon=self._default_icon,
            score=0.0,
            source="default",
            reasons=(f"default icon '{self._default_icon}'",),
        )
