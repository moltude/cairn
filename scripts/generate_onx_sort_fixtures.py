#!/usr/bin/env python3
"""Generate GPX fixtures for OnX sorting analysis.

I use these fixtures to isolate whether OnX orders Waypoints/Tracks by:
- name sorting (A–Z / Z–A)
- GPX element order (XML order)
- embedded timestamps (Old→New / New→Old)

To regenerate all fixtures, I run:

    python3 scripts/generate_onx_sort_fixtures.py

This script overwrites the generated files under `tests/fixtures/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape


GPX_NS = "http://www.topografix.com/GPX/1/1"
ONX_NS = "https://wwww.onxmaps.com/"  # yes, 4 w's


@dataclass(frozen=True)
class Waypoint:
    name: str
    lat: float
    lon: float
    time: str | None


@dataclass(frozen=True)
class Track:
    name: str
    color: str
    start_lat: float
    start_lon: float
    time: str | None


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_gpx_header(*, creator: str, name: str, desc: str) -> list[str]:
    creator = xml_escape(creator)
    name = xml_escape(name)
    desc = xml_escape(desc)
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<gpx xmlns="{GPX_NS}" xmlns:onx="{ONX_NS}" version="1.1" creator="{creator}">',
        "  <metadata>",
        f"    <name>{name}</name>",
        f"    <desc>{desc}</desc>",
        "  </metadata>",
    ]


def build_gpx_footer() -> list[str]:
    return ["</gpx>"]


def wpt_lines(wpt: Waypoint, *, icon: str, color: str) -> list[str]:
    name = xml_escape(wpt.name)
    icon = xml_escape(icon)
    color = xml_escape(color)
    lines = [
        f'  <wpt lat="{wpt.lat:.6f}" lon="{wpt.lon:.6f}">',
        f"    <name>{name}</name>",
    ]

    if wpt.time:
        lines.append(f"    <time>{wpt.time}</time>")

    lines.extend(
        [
            "    <extensions>",
            f"      <onx:icon>{icon}</onx:icon>",
            f"      <onx:color>{color}</onx:color>",
            "    </extensions>",
            "  </wpt>",
        ]
    )

    return lines


def trk_lines(trk: Track) -> list[str]:
    # Two points only; optional time at track-level and per-point.
    pt1_time = trk.time
    pt2_time = iso_z(datetime.fromisoformat(trk.time.replace("Z", "+00:00")) + timedelta(seconds=30)) if trk.time else None

    name = xml_escape(trk.name)
    color = xml_escape(trk.color)
    lines = [
        "  <trk>",
        f"    <name>{name}</name>",
    ]

    if trk.time:
        lines.append(f"    <time>{trk.time}</time>")

    lines.extend(
        [
            "    <extensions>",
            f"      <onx:color>{color}</onx:color>",
            "    </extensions>",
            "    <trkseg>",
            f'      <trkpt lat="{trk.start_lat:.6f}" lon="{trk.start_lon:.6f}">',
        ]
    )

    if pt1_time:
        lines.append(f"        <time>{pt1_time}</time>")

    lines.append("      </trkpt>")

    lines.append(
        f'      <trkpt lat="{(trk.start_lat + 0.010000):.6f}" lon="{(trk.start_lon + 0.010000):.6f}">'
    )

    if pt2_time:
        lines.append(f"        <time>{pt2_time}</time>")

    lines.extend(["      </trkpt>", "    </trkseg>", "  </trk>"])
    return lines


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def parse_names_and_times(gpx_path: Path) -> tuple[list[str], list[str | None], str]:
    tree = ET.parse(gpx_path)
    root = tree.getroot()
    ns = {"gpx": GPX_NS}

    wpts = root.findall("gpx:wpt", ns)
    if wpts:
        names: list[str] = []
        times: list[str | None] = []
        for wpt in wpts:
            name_el = wpt.find("gpx:name", ns)
            time_el = wpt.find("gpx:time", ns)
            names.append((name_el.text or "").strip() if name_el is not None else "")
            times.append((time_el.text or "").strip() if time_el is not None else None)
        return names, times, "wpt"

    trks = root.findall("gpx:trk", ns)
    names = []
    times = []
    for trk in trks:
        name_el = trk.find("gpx:name", ns)
        time_el = trk.find("gpx:time", ns)
        names.append((name_el.text or "").strip() if name_el is not None else "")
        times.append((time_el.text or "").strip() if time_el is not None else None)
    return names, times, "trk"


def generate() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[1]
    fixtures_dir = repo_root / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    creator = "Cairn - OnX Sort Fixtures"
    base_lat = 45.500000
    base_lon = -114.500000

    # Shared visual metadata: keep these constant to isolate sorting.
    wpt_icon = "Location"
    wpt_color = "rgba(8,122,255,1)"
    trk_colors = [
        "rgba(255,0,0,1)",
        "rgba(255,128,0,1)",
        "rgba(255,255,0,1)",
        "rgba(0,255,0,1)",
        "rgba(0,0,255,1)",
    ]

    az_names = [
        "A - A-Z First (Expect_AZ_01)",
        "B - A-Z Second (Expect_AZ_02)",
        "C - A-Z Third (Expect_AZ_03)",
        "D - A-Z Fourth (Expect_AZ_04)",
        "E - A-Z Fifth (Expect_AZ_05)",
    ]

    time_names = [
        "T1 - Oldest (Expect_Time_01)",
        "T2 - Older (Expect_Time_02)",
        "T3 - Middle (Expect_Time_03)",
        "T4 - Newer (Expect_Time_04)",
        "T5 - Newest (Expect_Time_05)",
    ]

    # Deterministic non-sequential ordering for "random in file" variants.
    order_random = [2, 0, 4, 1, 3]

    start_dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    time_values = [iso_z(start_dt + timedelta(minutes=i)) for i in range(5)]

    generated: list[Path] = []

    # --- Waypoints fixtures (5 wpt each) ---

    def waypoints_for(names: list[str], *, include_time: bool) -> list[Waypoint]:
        wpts: list[Waypoint] = []
        for i, name in enumerate(names):
            wpts.append(
                Waypoint(
                    name=name,
                    lat=base_lat + (i * 0.010000),
                    lon=base_lon - (i * 0.010000),
                    time=(time_values[i] if include_time else None),
                )
            )
        return wpts

    def write_waypoints_fixture(filename: str, *, title: str, desc: str, wpts: list[Waypoint]) -> Path:
        lines = build_gpx_header(creator=creator, name=title, desc=desc)
        for wpt in wpts:
            lines.extend(wpt_lines(wpt, icon=wpt_icon, color=wpt_color))
        lines.extend(build_gpx_footer())
        out = fixtures_dir / filename
        write_text(out, "\n".join(lines) + "\n")
        generated.append(out)
        return out

    # A–Z sequential in file
    write_waypoints_fixture(
        "test_sort_wp_az_sequential_in_file.gpx",
        title="Waypoints A–Z (XML Sequential)",
        desc="5 waypoints named A–E in the same XML order. No timestamps.",
        wpts=waypoints_for(az_names, include_time=False),
    )

    # A–Z random order in file
    wpts_az = waypoints_for(az_names, include_time=False)
    write_waypoints_fixture(
        "test_sort_wp_az_random_in_file.gpx",
        title="Waypoints A–Z (XML Random)",
        desc="5 waypoints named A–E, but in a shuffled XML order. No timestamps.",
        wpts=[wpts_az[i] for i in order_random],
    )

    # Time sequential
    write_waypoints_fixture(
        "test_sort_wp_time_sequential.gpx",
        title="Waypoints Time (XML Sequential, Time Sequential)",
        desc="5 waypoints with <time> increasing Oldest→Newest in the same XML order.",
        wpts=waypoints_for(time_names, include_time=True),
    )

    # Time random (timestamps are valid but appear in non-chronological order in the file)
    wpts_time = waypoints_for(time_names, include_time=True)
    write_waypoints_fixture(
        "test_sort_wp_time_random.gpx",
        title="Waypoints Time (XML Random, Time Random-in-File)",
        desc="5 waypoints with <time> Oldest→Newest, but placed in a shuffled XML order so times are not sequential in-file.",
        wpts=[wpts_time[i] for i in order_random],
    )

    # --- Tracks fixtures (5 trk each) ---

    def tracks_for(names: list[str], *, include_time: bool) -> list[Track]:
        trks: list[Track] = []
        for i, name in enumerate(names):
            trks.append(
                Track(
                    name=name,
                    color=trk_colors[i],
                    start_lat=base_lat + (i * 0.020000),
                    start_lon=base_lon,
                    time=(time_values[i] if include_time else None),
                )
            )
        return trks

    def write_tracks_fixture(filename: str, *, title: str, desc: str, trks: list[Track]) -> Path:
        lines = build_gpx_header(creator=creator, name=title, desc=desc)
        for trk in trks:
            lines.extend(trk_lines(trk))
        lines.extend(build_gpx_footer())
        out = fixtures_dir / filename
        write_text(out, "\n".join(lines) + "\n")
        generated.append(out)
        return out

    write_tracks_fixture(
        "test_sort_trk_az_sequential_in_file.gpx",
        title="Tracks A–Z (XML Sequential)",
        desc="5 tracks named A–E in the same XML order. No timestamps.",
        trks=tracks_for(az_names, include_time=False),
    )

    trks_az = tracks_for(az_names, include_time=False)
    write_tracks_fixture(
        "test_sort_trk_az_random_in_file.gpx",
        title="Tracks A–Z (XML Random)",
        desc="5 tracks named A–E, but in a shuffled XML order. No timestamps.",
        trks=[trks_az[i] for i in order_random],
    )

    write_tracks_fixture(
        "test_sort_trk_time_sequential.gpx",
        title="Tracks Time (XML Sequential, Time Sequential)",
        desc="5 tracks with <time> increasing Oldest→Newest in the same XML order (track + trackpoint times).",
        trks=tracks_for(time_names, include_time=True),
    )

    trks_time = tracks_for(time_names, include_time=True)
    write_tracks_fixture(
        "test_sort_trk_time_random.gpx",
        title="Tracks Time (XML Random, Time Random-in-File)",
        desc="5 tracks with <time> Oldest→Newest, but placed in a shuffled XML order so times are not sequential in-file.",
        trks=[trks_time[i] for i in order_random],
    )

    return generated


def validate(generated_paths: list[Path]) -> None:
    """Lightweight validation: counts + expected XML order + expected time presence."""

    expected: dict[str, dict[str, object]] = {
        "test_sort_wp_az_sequential_in_file.gpx": {
            "kind": "wpt",
            "count": 5,
            "names": [
                "A - A-Z First (Expect_AZ_01)",
                "B - A-Z Second (Expect_AZ_02)",
                "C - A-Z Third (Expect_AZ_03)",
                "D - A-Z Fourth (Expect_AZ_04)",
                "E - A-Z Fifth (Expect_AZ_05)",
            ],
            "has_time": False,
        },
        "test_sort_wp_az_random_in_file.gpx": {
            "kind": "wpt",
            "count": 5,
            "names": [
                "C - A-Z Third (Expect_AZ_03)",
                "A - A-Z First (Expect_AZ_01)",
                "E - A-Z Fifth (Expect_AZ_05)",
                "B - A-Z Second (Expect_AZ_02)",
                "D - A-Z Fourth (Expect_AZ_04)",
            ],
            "has_time": False,
        },
        "test_sort_wp_time_sequential.gpx": {
            "kind": "wpt",
            "count": 5,
            "names": [
                "T1 - Oldest (Expect_Time_01)",
                "T2 - Older (Expect_Time_02)",
                "T3 - Middle (Expect_Time_03)",
                "T4 - Newer (Expect_Time_04)",
                "T5 - Newest (Expect_Time_05)",
            ],
            "has_time": True,
        },
        "test_sort_wp_time_random.gpx": {
            "kind": "wpt",
            "count": 5,
            "names": [
                "T3 - Middle (Expect_Time_03)",
                "T1 - Oldest (Expect_Time_01)",
                "T5 - Newest (Expect_Time_05)",
                "T2 - Older (Expect_Time_02)",
                "T4 - Newer (Expect_Time_04)",
            ],
            "has_time": True,
        },
        "test_sort_trk_az_sequential_in_file.gpx": {
            "kind": "trk",
            "count": 5,
            "names": [
                "A - A-Z First (Expect_AZ_01)",
                "B - A-Z Second (Expect_AZ_02)",
                "C - A-Z Third (Expect_AZ_03)",
                "D - A-Z Fourth (Expect_AZ_04)",
                "E - A-Z Fifth (Expect_AZ_05)",
            ],
            "has_time": False,
        },
        "test_sort_trk_az_random_in_file.gpx": {
            "kind": "trk",
            "count": 5,
            "names": [
                "C - A-Z Third (Expect_AZ_03)",
                "A - A-Z First (Expect_AZ_01)",
                "E - A-Z Fifth (Expect_AZ_05)",
                "B - A-Z Second (Expect_AZ_02)",
                "D - A-Z Fourth (Expect_AZ_04)",
            ],
            "has_time": False,
        },
        "test_sort_trk_time_sequential.gpx": {
            "kind": "trk",
            "count": 5,
            "names": [
                "T1 - Oldest (Expect_Time_01)",
                "T2 - Older (Expect_Time_02)",
                "T3 - Middle (Expect_Time_03)",
                "T4 - Newer (Expect_Time_04)",
                "T5 - Newest (Expect_Time_05)",
            ],
            "has_time": True,
        },
        "test_sort_trk_time_random.gpx": {
            "kind": "trk",
            "count": 5,
            "names": [
                "T3 - Middle (Expect_Time_03)",
                "T1 - Oldest (Expect_Time_01)",
                "T5 - Newest (Expect_Time_05)",
                "T2 - Older (Expect_Time_02)",
                "T4 - Newer (Expect_Time_04)",
            ],
            "has_time": True,
        },
    }

    missing = []
    for path in generated_paths:
        spec = expected.get(path.name)
        if spec is None:
            continue

        names, times, kind = parse_names_and_times(path)
        if kind != spec["kind"]:
            raise AssertionError(f"{path.name}: expected kind={spec['kind']} got kind={kind}")

        if len(names) != spec["count"]:
            raise AssertionError(f"{path.name}: expected {spec['count']} items, got {len(names)}")

        if names != spec["names"]:
            raise AssertionError(
                f"{path.name}: unexpected XML order\nExpected: {spec['names']}\nActual:   {names}"
            )

        has_time = bool(spec["has_time"])
        if has_time and any(t is None for t in times):
            raise AssertionError(f"{path.name}: expected all items to have <time>")
        if (not has_time) and any(t is not None for t in times):
            raise AssertionError(f"{path.name}: did not expect any <time>")

        if spec["has_time"]:
            # Ensure times are unique and ISO-like.
            unique_times = {t for t in times if t is not None}
            if len(unique_times) != 5:
                raise AssertionError(f"{path.name}: expected 5 unique times, got {len(unique_times)}")
            for t in unique_times:
                if not t.endswith("Z"):
                    raise AssertionError(f"{path.name}: time not Zulu: {t}")

    # Ensure all expected files were generated.
    for fname in expected.keys():
        if not any(p.name == fname for p in generated_paths):
            missing.append(fname)

    if missing:
        raise AssertionError(f"Did not generate expected fixture(s): {missing}")


def main() -> int:
    generated = generate()
    validate(generated)

    print("Generated OnX sort fixtures:")
    for p in generated:
        print(f"- {p.relative_to(Path(__file__).resolve().parents[1])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
