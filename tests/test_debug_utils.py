from pathlib import Path

from rich.console import Console

from cairn.utils.debug import (
    analyze_gpx_order,
    compare_orders,
    display_order_comparison,
    find_order_mismatches,
    read_gpx_waypoint_order,
)


def _write_gpx(path: Path, names: list[str]) -> None:
    ns = "http://www.topografix.com/GPX/1/1"
    wpts = "\n".join(
        f'<wpt lat="0" lon="0"><name>{n}</name></wpt>' for n in names
    )
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<gpx xmlns="{ns}" version="1.1" creator="test">\n'
        f"{wpts}\n"
        f"</gpx>\n",
        encoding="utf-8",
    )


def test_read_gpx_waypoint_order_valid(tmp_path: Path):
    gpx = tmp_path / "a.gpx"
    _write_gpx(gpx, ["A", "B", "C"])
    assert read_gpx_waypoint_order(gpx) == ["A", "B", "C"]


def test_read_gpx_waypoint_order_invalid_xml_returns_empty_and_prints(tmp_path: Path):
    gpx = tmp_path / "bad.gpx"
    gpx.write_text("<gpx>", encoding="utf-8")
    c = Console(record=True)
    assert read_gpx_waypoint_order(gpx, console=c) == []
    assert "Error reading GPX file" in c.export_text()


def test_compare_orders_match_and_mismatch_and_length_warning():
    c = Console(record=True)

    ok, diffs = compare_orders(["A", "B"], ["A", "B"], console=c)
    assert ok is True
    assert diffs == []

    ok, diffs = compare_orders(["A", "B"], ["A", "C"], console=c)
    assert ok is False
    assert diffs == [(2, "B", "C")]

    # Length mismatch warning branch
    c2 = Console(record=True)
    ok, diffs = compare_orders(["A", "B", "C"], ["A"], console=c2)
    assert ok is False
    assert "Length mismatch" in c2.export_text()


def test_compare_orders_max_display_truncates_differences():
    expected = [f"E{i}" for i in range(30)]
    actual = [f"A{i}" for i in range(30)]
    ok, diffs = compare_orders(expected, actual, max_display=5)
    assert ok is False
    assert len(diffs) == 5
    assert diffs[0][0] == 1  # 1-based position


def test_display_order_comparison_match_prints_success():
    c = Console(record=True)
    display_order_comparison(["A"], ["A"], title="Test", console=c)
    out = c.export_text()
    assert "Orders match" in out


def test_display_order_comparison_mismatch_prints_table():
    c = Console(record=True)
    display_order_comparison(["A", "B"], ["A", "C"], title="Test", console=c)
    out = c.export_text()
    assert "Orders differ" in out
    assert "Expected" in out and "Actual" in out


def test_display_order_comparison_shows_truncation_message_when_long():
    expected = [f"E{i}" for i in range(40)]
    actual = [f"A{i}" for i in range(40)]
    c = Console(record=True)
    display_order_comparison(expected, actual, title="Long", console=c)
    assert "showing first 30 of 40" in c.export_text()


def test_analyze_gpx_order_no_waypoints_branch(tmp_path: Path):
    gpx = tmp_path / "empty.gpx"
    _write_gpx(gpx, [])
    c = Console(record=True)
    analyze_gpx_order(gpx, console=c)
    assert "No waypoints found" in c.export_text()


def test_analyze_gpx_order_expected_order_triggers_comparison(tmp_path: Path):
    gpx = tmp_path / "a.gpx"
    _write_gpx(gpx, ["A", "B"])
    c = Console(record=True)
    analyze_gpx_order(gpx, expected_order=["A", "C"], console=c)
    out = c.export_text()
    assert "Expected vs Actual Order" in out


def test_analyze_gpx_order_more_than_20_shows_more_message(tmp_path: Path):
    gpx = tmp_path / "many.gpx"
    _write_gpx(gpx, [f"W{i}" for i in range(25)])
    c = Console(record=True)
    analyze_gpx_order(gpx, console=c)
    assert "... and 5 more waypoints" in c.export_text()


def test_find_order_mismatches_returns_positions(tmp_path: Path):
    gpx = tmp_path / "a.gpx"
    _write_gpx(gpx, ["A", "B", "C"])
    assert find_order_mismatches(gpx, ["A", "X", "C"]) == [2]
