from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


GPX_NS = "http://www.topografix.com/GPX/1/1"


def _read_names_and_times(gpx_path: Path) -> tuple[list[str], list[str | None], str]:
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


def test_generated_onx_sort_fixtures_shape_and_order() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixtures_dir = repo_root / "tests" / "fixtures"

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

    for fname, spec in expected.items():
        path = fixtures_dir / fname
        assert path.exists(), f"Missing fixture file: {path}"

        names, times, kind = _read_names_and_times(path)
        assert kind == spec["kind"], f"{fname}: expected kind {spec['kind']}, got {kind}"
        assert len(names) == spec["count"], f"{fname}: expected {spec['count']} items, got {len(names)}"
        assert names == spec["names"], f"{fname}: unexpected XML order"

        has_time = bool(spec["has_time"])
        if has_time:
            assert all(t is not None for t in times), f"{fname}: expected <time> on all items"
            unique_times = {t for t in times if t is not None}
            assert len(unique_times) == 5, f"{fname}: expected 5 unique times"
        else:
            assert all(t is None for t in times), f"{fname}: did not expect <time>"
