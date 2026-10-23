"""Per-field round-trip fidelity on the synthetic onX dialect fixtures (roadmap Phase 1).

onx_dialect.gpx + onx_dialect.kml -> read_onx_gpx / read_onx_kml -> merge ->
MapDocument->ParsedFeature (a test-only adapter; Phase 2 owns the real one) ->
Cairn's GPX/KML writers -> re-read with the same onX readers -> per-field diff.

Two checks, so a loss can't hide in either half:

1. What the READERS produce is compared with SOURCE, a table written by hand from the
   fixture files. (KG section 6's scratch scorer snapshotted the reader output as its
   baseline, so losses at read time -- the dropped hole, the dropped second polygon --
   never showed up in its 54/66.)
2. What survives Cairn's writers is compared field by field with that, and every
   difference must be on ALLOWED_LOSSES. A new loss, or an allowed loss that stops
   happening, fails the test; update the allow-list deliberately.

Fixtures are synthetic: see tests/fixtures/onx_dialect/README.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cairn.core.color_mapper import AREA_FILL_KEY, AREA_STYLE_KEY, AREA_WEIGHT_KEY
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.core.parser import ParsedFeature
from cairn.core.writers import (
    write_gpx_tracks_maybe_split,
    write_gpx_waypoints_maybe_split,
    write_kml_shapes_maybe_split,
)
from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.model import MapDocument, Shape, Track, Waypoint
from cairn.utils.utils import sanitize_name_for_onx

FX = Path(__file__).parent / "fixtures" / "onx_dialect"

FIELDS = ("kind", "line", "notes", "icon", "color", "style", "weight", "fill",
          "id", "pts", "ele", "time", "rings")

SLIDE_NOTES = (
    "Avalanche D2 · N · 8200 ft · trigger AS (skier, unintentional)\n"
    "Problem: Wind Slab · Zone: Bitterroot & Rattlesnake #2\n"
    "Full report: https://missoulaavalanche.org/observations/#/avalanche/123"
    "?a=1&copy=2&notes=3&para=4\n"
    "Source: West Central Montana Avalanche Center. Not a forecast — check today's advisory."
)

_ID = "0b6d8e0a-1111-4c4c-9a9a-00000000000"
_T0 = 1782918000000  # 2026-07-01T15:00:00Z in epoch ms

# What the onX files say, field by field (None = the field doesn't apply / is absent).
SOURCE = {
    "Main Wall": [dict(kind="Waypoint", notes="Approach from the north.\nSecond line of notes.",
                       icon="Climbing", color="rgba(255,51,0,1)", id=_ID + "1")],
    "Camp & water": [dict(kind="Waypoint", notes="a=b inside notes", icon="Campsite",
                        color="rgba(8,122,255,1)", id=_ID + "2")],
    "Slide obs": [dict(kind="Waypoint", notes=SLIDE_NOTES, icon="Hazard",
                       color="rgba(255,0,0,1)", id=_ID + "7")],
    "Recorded hike": [dict(kind="Track", notes="", color="rgba(255,0,255,1)", style="dash",
                           weight="2.0", id=_ID + "3", pts=3,
                           ele=(1500.5, 1510.0, 1522.0),
                           time=(_T0, _T0 + 300000, _T0 + 600000))],
    "Ridge line": [dict(kind="Track", line=True, notes="drawn line", color="rgba(0,0,0,1)",
                        style="solid", weight="6.0", id=_ID + "4", pts=3,
                        ele=(None, None, None), time=(None, None, None))],
    "Hunt unit": [dict(kind="Shape", notes="has a hole", color="rgba(255,255,0,1)",
                       style="solid", weight="4.0", fill="rgba(238,255,125,0.1)",
                       id=_ID + "5", pts=10, rings=2)],
    "Two-part area": [
        dict(kind="Shape", notes="north & south parcels", color="rgba(132,212,0,1)",
             style="dash", weight="6.0", fill="rgba(42,139,97,0.1)", id=_ID + "6",
             pts=4, rings=1),
        dict(kind="Shape", notes="north & south parcels", color="rgba(132,212,0,1)",
             style="dash", weight="6.0", fill="rgba(42,139,97,0.1)", id=_ID + "6",
             pts=4, rings=1),
    ],
}

# Every field Cairn's round trip is still allowed to lose, and why.
ALLOWED_LOSSES = {
    # The onX id is never written (writers.py:_desc_text). Whether writing it back would
    # make onX update instead of duplicate is probe P1; until then it stays out.
    *{(name, i, "id") for name, items in SOURCE.items() for i in range(len(items))},
    # Item 5 of Phase 1 (a "thin" weight bucket) is an owner decision: it also changes
    # CalTopo output. stroke_width_to_weight can only return "4.0"/"6.0" until then.
    ("Recorded hike", 0, "weight"),
    # An onX Line is read as a Track tagged as a line, but no writer emits
    # <rte><type>Line</type> yet (not a Phase 1 item), so it comes back as a <trk>.
    ("Ridge line", 0, "line"),
}
# Names: "Camp & water" comes back unchanged. sanitize_name_for_onx used to strip & and #;
# names now pass through (onX verified 2026-10-22, DECISIONS.md ENG-06).


def _norm_name(name: str) -> str:
    return sanitize_name_for_onx(name)[0]  # identity since ENG-06; kept so the pass-through is exercised


def _snap(doc: MapDocument) -> dict:
    out: dict = {}
    for it in doc.items:
        s = it.style
        d = dict(kind=type(it).__name__, notes=it.notes, icon=s.OnX_icon,
                 color=s.OnX_color_rgba, style=s.OnX_style, weight=s.OnX_weight,
                 id=s.OnX_id)
        if isinstance(it, Track):
            d.update(line=it.extra.get("onx_kind") == "line" or None, pts=len(it.points),
                     ele=tuple(p[2] for p in it.points), time=tuple(p[3] for p in it.points))
        if isinstance(it, Shape):
            d.update(rings=len(it.rings), pts=sum(len(r) for r in it.rings),
                     fill=s.extra.get("fill_color"))
        out.setdefault(_norm_name(it.name), []).append({f: d.get(f) for f in FIELDS})
    return out


def _alpha(rgba: str | None):
    m = re.match(r"rgba\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*,\s*([\d.]+)\s*\)", rgba or "")
    return float(m.group(1)) if m else None


def _to_parsed(it) -> ParsedFeature:
    """Test-only MapDocument -> ParsedFeature adapter (KG section 6, plus time and fill)."""
    s = it.style
    width = {"2.0": 2, "4.0": 4, "6.0": 6}.get(s.OnX_weight or "", 4)
    if isinstance(it, Waypoint):
        props = {"class": "Marker", "title": it.name, "description": it.notes,
                 "marker-color": s.OnX_color_rgba or "", "marker-symbol": "",
                 "cairn_onx_icon_override": s.OnX_icon or ""}
        geom = {"type": "Point", "coordinates": [it.lon, it.lat]}
    elif isinstance(it, Track):
        props = {"class": "Shape", "title": it.name, "description": it.notes,
                 "stroke": s.OnX_color_rgba or "", "stroke-width": width,
                 "pattern": s.OnX_style or "solid"}
        geom = {"type": "LineString", "coordinates": [list(p) for p in it.points]}
    else:
        props = {"class": "Shape", "title": it.name, "description": it.notes,
                 "stroke": s.OnX_color_rgba or "", "stroke-width": width,
                 "pattern": s.OnX_style or "solid"}
        if _alpha(s.extra.get("fill_color")) is not None:
            props["fill-opacity"] = _alpha(s.extra.get("fill_color"))
        # As cairn.io.document_adapter does: the area's onX values, exactly.
        props.update({AREA_STYLE_KEY: s.OnX_style or "", AREA_WEIGHT_KEY: s.OnX_weight or "",
                      AREA_FILL_KEY: s.extra.get("fill_color") or ""})
        geom = {"type": "Polygon", "coordinates": [[list(p) for p in r] for r in it.rings]}
    return ParsedFeature({"id": it.id, "geometry": geom, "properties": props})


def _read_source() -> MapDocument:
    return merge_onx_gpx_and_kml(read_onx_gpx(FX / "onx_dialect.gpx"),
                                 read_onx_kml(FX / "onx_dialect.kml"))


def _round_trip(doc: MapDocument, out: Path) -> MapDocument:
    wps = [_to_parsed(i) for i in doc.items if isinstance(i, Waypoint)]
    trs = [_to_parsed(i) for i in doc.items if isinstance(i, Track)]
    shs = [_to_parsed(i) for i in doc.items if isinstance(i, Shape)]
    write_gpx_waypoints_maybe_split(wps, out / "W.gpx", "ZZ Cairn Test")
    write_gpx_tracks_maybe_split(trs, out / "T.gpx", "ZZ Cairn Test")
    write_kml_shapes_maybe_split(shs, out / "A.kml", "ZZ Cairn Test")
    back = MapDocument()
    for d in (read_onx_gpx(out / "W.gpx"), read_onx_gpx(out / "T.gpx"),
              read_onx_kml(out / "A.kml")):
        back.items.extend(d.items)
    return back


def _expected_source() -> dict:
    return {name: [{f: item.get(f) for f in FIELDS} for item in items]
            for name, items in SOURCE.items()}


def test_readers_recover_every_field_in_the_onx_files():
    assert _snap(_read_source()) == _expected_source()


def _diff(before: dict, after: dict) -> set:
    diffs = set()
    assert sorted(before) == sorted(after), "items lost or gained in the round trip"
    for name, items in before.items():
        assert len(after[name]) == len(items), name
        for i, (b, a) in enumerate(zip(items, after[name])):
            diffs |= {(name, i, f) for f in FIELDS if b[f] != a[f]}
    return diffs


def test_round_trip_loses_only_the_allowed_fields(tmp_path):
    before = _snap(_read_source())
    after = _snap(_round_trip(_read_source(), tmp_path))
    assert _diff(before, after) == ALLOWED_LOSSES


def test_round_trip_fidelity_figure(tmp_path):
    """The headline number: fields that reach the far side of the round trip intact,
    scored against SOURCE (the files), so losses at read time count as well as losses
    at write time. Only the fields each item kind has are counted; an item that is
    lost counts all its fields as lost. A regression shows up as a smaller figure."""
    after = _snap(_round_trip(_read_source(), tmp_path))
    # 10 misses: 7 onX ids, the thin weight (item 5) and the Line kind; see ALLOWED_LOSSES.
    assert fidelity_figure(after) == FIDELITY_FIGURE


# Phase 1's headline figure. tests/test_web_bridge_input_dispatch.py holds the web
# bridge's export (roadmap Phase 2) to the same number.
FIDELITY_FIGURE = (52, 62)

_APPLICABLE = {
    "Waypoint": ("kind", "notes", "icon", "color", "id"),
    "Track": ("kind", "line", "notes", "color", "style", "weight", "id", "pts", "ele", "time"),
    "Shape": ("kind", "notes", "color", "style", "weight", "fill", "id", "pts", "rings"),
}


def fidelity_figure(after: dict) -> tuple[int, int]:
    """(fields intact, fields in SOURCE) for a _snap of the re-read output."""
    total = same = 0
    for name, items in _expected_source().items():
        got = after.get(name, [])
        for i, b in enumerate(items):
            a = got[i] if i < len(got) else None
            for f in _APPLICABLE[b["kind"]]:
                total += 1
                same += a is not None and b[f] == a[f]
    return same, total


@pytest.mark.parametrize("name", ["Slide obs", "Main Wall"])
def test_multiline_notes_with_url_survive_the_round_trip(tmp_path, name):
    after = _snap(_round_trip(_read_source(), tmp_path))
    assert after[name][0]["notes"] == SOURCE[name][0]["notes"]
