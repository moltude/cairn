"""CalTopo GeoJSON, KML and GPX of the same map give the same review screen.

Roadmap Phase 7. The owner's goal: whichever of the three CalTopo exports a
user drops in, Cairn hands onX the same thing -- "even if there are
inconsistencies, they are the same inconsistencies" -- so one onX import test
covers all three. Each test loads the GeoJSON as the reference and pins the
EXACT set of differences the other format shows, each with its reason. A new
difference, or a documented one disappearing, fails.

Maps: Dark Divide 100 (real, tests/fixtures/dark_divide_100/caltopo/) and the
synthetic map from scripts/generate_caltopo_synthetic.py
(tests/fixtures/caltopo_synthetic/), which adds built-in symbols, colours,
widths, a dashed line, areas with a hole and two parts, a nested folder and
special characters.
"""

from __future__ import annotations

import difflib
import io
import json
import zipfile
from pathlib import Path

import pytest

from tests.caltopo_parity_helpers import ROOT, bridge, differences, review_items

FIX = ROOT / "tests" / "fixtures"
SYN = FIX / "caltopo_synthetic" / "caltopo_synthetic"
DD = FIX / "dark_divide_100" / "caltopo" / "2027_Dark_Divide_100_Mile_Endurance_Run"

DD_CUSTOM_ICON_MARKERS = [
    "01 - Cispus Learning Center Start/Finish", "02 - Juniper Ridge AS (Used Twice)",
    "03 - Sunrise AS (Used Twice)", "04 - Dark Creek AS", "05 - Wilderness Crossing AS",
    "06 - Wright Meadow AS", "07 - Lewis River AS", "08 - Quartz Butte AS",
    # Was equal by chance while its name mapped to Summit (red, like CalTopo's);
    # since 2026-10-24 "AS" maps it to Food Source like the other aid stations.
    "09 - Summit Prairie AS",
]


def _every(path: Path, field: str, kinds=("waypoints", "tracks")) -> set:
    return {(i["kind"], i["name"], field) for i in review_items(path) if i["kind"] in kinds}


def _expected(case: str) -> set:
    if case == "synthetic-kml":
        # KML has no line pattern: CalTopo's dashed line reads as solid.
        return {("tracks", "Green dashed skin track", "style")}
    if case == "synthetic-gpx":
        return (
            # No folders in a CalTopo GPX: one folder named after the file.
            _every(Path(f"{SYN}.json"), "folder")
            # No areas: no CalTopo GPX with one has been seen (fixture README).
            | {("shapes", "Burn area with island", "missing"),
               ("shapes", "Two-part closure", "missing")}
            # No pattern in GPX either.
            | {("tracks", "Green dashed skin track", "style")}
            # Line colour: GPX names only Garmin's 16 colours, exactly. #00CD00
            # isn't one; "#ff0000" is lower case (Dark Divide's line 10 shows
            # CalTopo then writes no DisplayColor). Both fall to onX blue.
            | {("tracks", "Green dashed skin track", "color"),
               ("tracks", "Note test: a <b> & #c", "color")}
            # No waypoint colour in GPX (Garmin's schema has none): the colour
            # comes from the icon instead. Equal by chance where the icon's
            # colour matches CalTopo's (North summit, Old cabin, the uncoloured
            # point).
            | {("waypoints", n, "color") for n in (
                "Camp #3 & <Lake> spring", "Cornice", "Green flag", "Plain red point",
                "Trailhead lot")}
            # No <sym>: the icon is a name guess. "camping" and "danger" carried
            # the meaning; the names don't match a keyword.
            | {("waypoints", "Camp #3 & <Lake> spring", "icon"),
               ("waypoints", "Cornice", "icon")}
        )
    if case == "darkdivide-kml":
        # The custom icon's colour: GeoJSON gives these markers stroke #FF0000;
        # the KML icon cfg carries none (PARITY.md "Why").
        return {("waypoints", n, "color") for n in DD_CUSTOM_ICON_MARKERS}
    if case == "darkdivide-gpx":
        return (
            _every(Path(f"{DD}.json"), "folder")
            | {("waypoints", n, "color") for n in DD_CUSTOM_ICON_MARKERS}
            | {("tracks", "10 - Sunrise Peak #2 AS to Juniper Ridge #2 AS", "color")}
        )
    raise AssertionError(case)


CASES = {
    "synthetic-kml": (SYN, "kml"),
    "synthetic-gpx": (SYN, "gpx"),
    "darkdivide-kml": (DD, "kml"),
    "darkdivide-gpx": (DD, "gpx"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_review_items_match_geojson_except_documented_losses(case):
    base, ext = CASES[case]
    ref = review_items(Path(f"{base}.json"))
    other = review_items(Path(f"{base}.{ext}"))
    assert differences(ref, other) == _expected(case)


def test_synthetic_files_are_what_the_generator_writes(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gen", ROOT / "scripts" / "generate_caltopo_synthetic.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    monkeypatch.setattr(gen, "OUT", tmp_path)
    gen.main()
    for ext in ("json", "kml", "gpx"):
        assert (tmp_path / f"caltopo_synthetic.{ext}").read_bytes() == \
            Path(f"{SYN}.{ext}").read_bytes(), f"rerun scripts/generate_caltopo_synthetic.py ({ext})"


def test_synthetic_map_covers_what_dark_divide_lacks():
    items = review_items(Path(f"{SYN}.json"))
    kinds = {i["kind"] for i in items}
    assert kinds == {"waypoints", "tracks", "shapes"}
    assert "Fuchsia" in {c["name"] for c in json.loads(_load(f"{SYN}.json"))["line_colors"]}
    assert "rgba(255,0,255,1)" in {i["color"] for i in items if i["kind"] == "tracks"}
    assert {i["style"] for i in items if i["kind"] == "tracks"} == {"solid", "dash"}
    burn = next(i for i in items if i["name"] == "Burn area with island")
    assert len(burn["geometry"]) == 2  # outer ring + hole
    assert [i["name"] for i in items].count("Two-part closure") == 2
    assert "Routes / Spur lines" in {i["folder"] for i in items}
    camp = next(i for i in items if i["name"] == "Camp #3 & <Lake> spring")
    assert "https://example.com/trail?a=1&b=2#camp" in camp["notes"]
    assert "\n\n" in camp["notes"]


def _load(path: str) -> str:
    p = Path(path)
    return bridge.load_files(json.dumps([{"name": p.name, "text": p.read_text(encoding="utf-8")}]))


def _export(path: str) -> dict:
    _load(path)
    with zipfile.ZipFile(io.BytesIO(bytes(bridge.export_zip()))) as z:
        return {n: z.read(n).decode("utf-8") for n in sorted(z.namelist())}


def test_synthetic_kml_exports_byte_identical_to_geojson_but_the_dash():
    """What onX would be handed: the same files, the same bytes, except the one
    style line KML can't carry."""
    a, b = _export(f"{SYN}.json"), _export(f"{SYN}.kml")
    assert a.keys() == b.keys()
    changed = {n for n in a if a[n] != b[n]}
    assert changed == {"03_Routes/Routes_Tracks.gpx"}   # Areas, Camps & Water #1, Routes, …
    delta = [ln for ln in difflib.unified_diff(
        a["03_Routes/Routes_Tracks.gpx"].splitlines(), b["03_Routes/Routes_Tracks.gpx"].splitlines(),
        lineterm="", n=0) if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
    assert delta == ["-      <onx:style>dash</onx:style>", "+      <onx:style>solid</onx:style>"]
