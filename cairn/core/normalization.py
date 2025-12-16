"""
Shared normalization utilities.

These exist to make parsing robust across:
- XML entities and HTML entities (including double-escaped sequences like '&amp;apos;')
- Coordinate arrays that may contain extra dimensions (elevation/time)
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Iterable, Optional, Tuple


_WS_RE = re.compile(r"\s+")


def normalize_entities(text: str) -> str:
    """
    Decode XML/HTML entities in a stable way.

    We intentionally run unescape more than once because we have observed inputs like:
    - '&amp;apos;' (double-escaped apostrophe)
    """
    if text is None:
        return ""

    s = str(text)
    # Run twice to collapse double-escaped entities.
    # html.unescape handles &apos; as well as common entities.
    for _ in range(2):
        s2 = html.unescape(s)
        if s2 == s:
            break
        s = s2
    return s


def normalize_name(text: str) -> str:
    """Normalize a display name (decode entities, preserve user whitespace largely)."""
    return normalize_entities(text).strip()


def normalize_key(text: str) -> str:
    """Normalize a key for comparisons (decode entities, lowercase, collapse whitespace)."""
    s = normalize_entities(text).strip().lower()
    s = _WS_RE.sub(" ", s)
    return s


def parse_lon_lat(coords: Iterable[float]) -> Tuple[float, float]:
    """
    Parse lon/lat from coordinate sequences that may include extras:
    - [lon, lat]
    - [lon, lat, 0, 0]
    - [lon, lat, ele, epoch_ms]
    """
    c = list(coords)
    if len(c) < 2:
        raise ValueError("Coordinate sequence must contain at least lon,lat")
    return float(c[0]), float(c[1])


def parse_optional_ele_time(
    coords: Iterable[float],
) -> Tuple[Optional[float], Optional[int]]:
    """
    Extract optional elevation/time (epoch ms) from CalTopo-style coord arrays.
    """
    c = list(coords)
    ele: Optional[float] = None
    t_ms: Optional[int] = None
    if len(c) >= 3:
        try:
            ele = float(c[2])
        except Exception:
            ele = None
    if len(c) >= 4:
        try:
            t_ms = int(c[3])
        except Exception:
            t_ms = None
    return ele, t_ms


def iso8601_to_epoch_ms(value: str) -> Optional[int]:
    """
    Convert an ISO8601 time string (from GPX) to epoch ms.
    Returns None if parsing fails.
    """
    if not value:
        return None
    s = value.strip()
    # Common GPX format ends with Z.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None
