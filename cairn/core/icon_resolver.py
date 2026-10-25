# Web engine: imported by web/bridge.py and run in the browser via Pyodide.
# Keep it free of terminal/UI imports (tests/test_web_engine_surface.py).
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

from dataclasses import dataclass, replace
from typing import Dict, List, Literal, Set, Tuple

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
    # Where a keyword matched: "title" or "description" ("" for symbol/default).
    field: str = ""


_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Title abbreviations, matched case-sensitively as whole words ("AS" but not
# the word "as"). Race maps label aid stations "Juniper Ridge AS".
_TITLE_ABBREVIATIONS = ((re.compile(r"\bAS\b"), "aid station"),)


def _expand_abbreviations(title: str) -> str:
    for pattern, phrase in _TITLE_ABBREVIATIONS:
        title = pattern.sub(phrase, title)
    return title


def _as_written(term: str, title: str) -> str:
    """A matched term as the title spells it: "AS" rather than "aid station"."""
    if term in title.lower():
        return term
    for pattern, phrase in _TITLE_ABBREVIATIONS:
        found = pattern.search(title)
        if phrase == term and found:
            return found.group()
    return term


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

    def resolve(
        self, title: str, description: str = "", symbol: str = ""
    ) -> IconDecision:
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
                    reasons=(
                        f"symbol substring match '{key}' in '{symbol_norm}' → '{icon}'",
                    ),
                    matched_terms=(key,),
                )

        # 2) Keyword scoring. The title decides when it matches anything; the
        # description is only consulted when it doesn't. Within the title, a tie
        # goes to the later match: place names end in what the place is ("Dark
        # Creek AS" is an aid station, "Camp Creek" is a creek).
        best = self._best_keyword(_expand_abbreviations(title).lower(), by_position=True)
        if best is not None:
            terms = tuple(_as_written(t, title) for t in best.matched_terms)
            return replace(best, matched_terms=terms, field="title")
        best = self._best_keyword(description.lower(), by_position=False)
        if best is not None:
            return replace(best, field="description")

        # 3) Default
        return IconDecision(
            icon=self._default_icon,
            score=0.0,
            source="default",
            reasons=(f"default icon '{self._default_icon}'",),
        )

    def _best_keyword(self, text: str, *, by_position: bool) -> IconDecision | None:
        """Best keyword decision for one text, or None if nothing matches.

        Ranks by number of matches; with by_position, a tie goes to the icon
        whose last match ends later. Remaining ties go to the configured
        keyword order.
        """
        if not text:
            return None
        token_ends: Dict[str, int] = {}
        for m in _TOKEN_RE.finditer(text):
            token = m.group()
            token_ends[token] = m.end()
            # "Camp2" is the word camp with a number on it: register the word
            # too, at the same end, so the tie rule above still sees its
            # position. The token itself stays, for a keyword with digits of
            # its own ("4x4"); a bare number strips to nothing and adds nothing.
            word = token.rstrip("0123456789")
            if word and word != token:
                token_ends[word] = m.end()

        best: IconDecision | None = None
        best_rank: Tuple[int, int] = (-1, 0)
        for icon in self._keyword_priority:
            matched: List[str] = []
            last_end = -1
            for kw in self._normalized_keywords.get(icon, ()):
                if " " in kw:
                    # Phrase match: simple substring
                    at = text.rfind(kw)
                    end = at + len(kw) if at >= 0 else -1
                else:
                    # Token match: avoids false positives like 'th' in 'path'
                    end = token_ends.get(kw, -1)
                if end >= 0:
                    matched.append(kw)
                    last_end = max(last_end, end)
            if not matched:
                continue
            rank = (len(matched), last_end if by_position else 0)
            if best is None or rank > best_rank:
                best_rank = rank
                best = IconDecision(
                    icon=icon,
                    score=float(len(matched)),
                    source="keyword",
                    reasons=(f"keyword matches for '{icon}': {', '.join(matched)}",),
                    matched_terms=tuple(matched),
                )
        return best
