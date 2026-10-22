"""Generate tests/fixtures/edge_cases_onx/edge.json: CalTopo-dialect GeoJSON edge cases
for the onX round-trip harness (scripts/onx_roundtrip.py).

    uv run python scripts/generate_edge_dataset.py          # (re)write the fixture
    uv run python scripts/generate_edge_dataset.py --check  # exit 1 if it would change

Deterministic: no clocks, no randomness; the output is byte-identical on every run.
Every markup is named "ZZTEST ..." so leftovers in an onX account are findable.
See tests/fixtures/edge_cases_onx/README.md for what each item probes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "edge_cases_onx" / "edge.json"

FOLDER_ID = "zztest-edge-folder-0001"
FOLDER_NAME = "Edge Cases"
# Fixed timestamp (2026-10-22T00:00:00Z) so the file never changes between runs.
TS = 1792627200000

# Note lengths straddling the 512 bytes onX keeps on import (2026-10-22).
NOTE_LENGTHS = (500, 511, 512, 513, 600, 1000, 3000)
TRACK_NOTE_LENGTHS = (511, 512, 513, 3000)
# That limit is 512 UTF-8 *bytes* (round r1: an em dash cost 3), so multibyte notes are
# probed by byte length. "mid-char" puts byte 512 inside a 2-byte "é".
UTF8_NOTE_BYTES = (511, 512, 513)

WORDS = ("granite ridge above the north fork, snow until July, water at the outlet, "
         "bear hang near the larches, trail fades past the second cairn").split()


def numbered_note(length: int) -> str:
    """Readable text with numbered lines, exactly `length` characters.

    Lines look like "Line 07: granite ridge ..." -- never "word=value", which onX's
    own key=value <desc> export could confuse with a field. Ends in a non-space so
    no reader's outer-whitespace trim can change the length.
    """
    lines, n = [], 1
    while sum(len(x) + 1 for x in lines) < length:
        words = " ".join(WORDS[(n + k) % len(WORDS)] for k in range(6))
        lines.append(f"Line {n:02d}: {words}.")
        n += 1
    text = "\n".join(lines)[:length]
    if text[-1].isspace():
        text = text[:-1] + "."
    assert len(text) == length, (len(text), length)
    return text


def utf8_note(nbytes: int) -> str:
    """Readable multibyte text ("é" is 2 bytes, "—" 3) of exactly `nbytes` UTF-8 bytes."""
    lines, n = [], 1
    while len("\n".join(lines).encode()) < nbytes:
        lines.append(f"Line {n:02d}: névé — café at the col, 2 km.")
        n += 1
    text = "\n".join(lines)
    while len(text.encode()) > nbytes - 1:          # cut on a character boundary
        text = text[:-1]
    text = text.rstrip() + "." * (nbytes - len(text.rstrip().encode()))
    assert len(text.encode()) == nbytes, (len(text.encode()), nbytes)
    return text


def mid_char_note() -> str:
    """511 ASCII bytes then "é": onX's 512-byte cut lands inside the "é"."""
    text = numbered_note(511) + "é."
    assert len(text.encode()[:512].decode("utf-8", "replace")) == 512
    return text


def _base(fid: str, title: str, cls: str, **props) -> dict:
    p = {"title": title, "class": cls, "folderId": FOLDER_ID, "creator": "ZZTEST",
         "-created-on": TS, "-updated-on": TS, "updated": TS}
    p.update(props)
    return {"type": "Feature", "id": fid, "properties": p}


def marker(n: int, title: str, description: str = "", symbol: str = "point",
           color: str = "#FF0000") -> dict:
    f = _base(f"zztest-wpt-{n:03d}", title, "Marker", **{
        "marker-symbol": symbol, "marker-color": color, "marker-size": 1,
        "description": description})
    # A grid well apart from each other, in the Dark Divide area.
    lon = -121.90 + (n % 6) * 0.01
    lat = 46.20 + (n // 6) * 0.01
    f["geometry"] = {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6), 0, 0]}
    return f


def line(n: int, title: str, description: str = "", pattern: str = "solid",
         width: int = 2, stroke: str = "#0000FF") -> dict:
    f = _base(f"zztest-trk-{n:03d}", title, "Shape", **{
        "stroke": stroke, "stroke-width": width, "stroke-opacity": 1,
        "pattern": pattern, "description": description})
    lat0 = 46.25 + n * 0.004
    pts = [[round(-121.95 + k * 0.002, 6), round(lat0 + (k % 3) * 0.0007, 6)] for k in range(12)]
    f["geometry"] = {"type": "LineString", "coordinates": pts}
    return f


def polygon(n: int, title: str, description: str = "") -> dict:
    f = _base(f"zztest-shp-{n:03d}", title, "Shape", **{
        "stroke": "#FF00FF", "stroke-width": 2, "stroke-opacity": 1,
        "fill": "#FF00FF", "fill-opacity": 0.3, "description": description})
    ring = [[-121.80, 46.30], [-121.78, 46.30], [-121.78, 46.32], [-121.80, 46.32], [-121.80, 46.30]]
    f["geometry"] = {"type": "Polygon", "coordinates": [ring]}
    return f


def build() -> dict:
    folder = {"type": "Feature", "id": FOLDER_ID, "geometry": None,
              "properties": {"title": FOLDER_NAME, "class": "Folder", "visible": True,
                             "creator": "ZZTEST", "updated": TS}}
    feats = [folder]
    n = 0
    for length in NOTE_LENGTHS:
        n += 1
        feats.append(marker(n, f"ZZTEST note {length}", numbered_note(length), "summit"))
    n += 1
    feats.append(marker(n, "ZZTEST blank lines",
                        "First paragraph.\n\nSecond, after one blank line.\n\n\n"
                        "Third, after two blank lines.", "camping"))
    n += 1
    feats.append(marker(n, "ZZTEST url",
                        "Trail report: https://example.com/trails?id=42&view=map#section-3 "
                        "(see the map).", "info"))
    n += 1
    feats.append(marker(n, "ZZTEST literal tags",
                        "Plain text, not markup: <desc> and <Lake> must survive.\n"
                        "Also 5 < 6 and 7 > 4.", "water"))
    names = ("ZZTEST Peak #3", "ZZTEST Rock & Roll", "ZZTEST Wow!", "ZZTEST Camp (lower)",
             "ZZTEST O'Neil's Spring", "ZZTEST trailing space ")
    for name in names:
        n += 1
        feats.append(marker(n, name, f"Name probe: {name.strip()}", "point", "#00FF00"))
    for nbytes in UTF8_NOTE_BYTES:
        n += 1
        feats.append(marker(n, f"ZZTEST utf8 note {nbytes}B", utf8_note(nbytes), "summit", "#0000FF"))
    n += 1
    feats.append(marker(n, "ZZTEST utf8 note mid-char", mid_char_note(), "summit", "#0000FF"))
    n += 1
    feats.append(marker(n, "ZZTEST Névé Café — Lac des Îles 🏔", "Name probe: accents, em dash, emoji.",
                        "point", "#00FF00"))

    t = 0
    for length in TRACK_NOTE_LENGTHS:
        t += 1
        feats.append(line(t, f"ZZTEST line note {length}", numbered_note(length)))
    t += 1
    feats.append(line(t, "ZZTEST dashed line", "CalTopo dash pattern.",
                      pattern="M0 -1 L0 1,,8,F", stroke="#FF0000"))
    t += 1
    feats.append(line(t, "ZZTEST wide line", "CalTopo stroke-width 6.", width=6, stroke="#000000"))

    feats.append(polygon(1, "ZZTEST filled area", "Fill #FF00FF at opacity 0.3."))
    return {"type": "FeatureCollection", "features": feats}


def render() -> str:
    return json.dumps(build(), indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT} is stale: run scripts/generate_edge_dataset.py")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(build()['features']) - 1} markups)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
