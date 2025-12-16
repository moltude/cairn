from pathlib import Path

import pytest

from cairn.io.onx_gpx import read_onx_gpx


class _Trace:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event: dict) -> None:
        self.events.append(event)


def test_read_OnX_gpx_empty_file_raises(tmp_path: Path):
    p = tmp_path / "empty.gpx"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        read_onx_gpx(p)


def test_read_OnX_gpx_invalid_xml_raises(tmp_path: Path):
    p = tmp_path / "bad.gpx"
    p.write_text("not xml", encoding="utf-8")
    with pytest.raises(ValueError, match="XML parse error"):
        read_onx_gpx(p)


def test_read_OnX_gpx_wrong_root_raises(tmp_path: Path):
    p = tmp_path / "wrong.gpx"
    p.write_text("<nope></nope>", encoding="utf-8")
    with pytest.raises(ValueError, match="does not appear to be a GPX"):
        read_onx_gpx(p)


def test_read_OnX_gpx_skips_invalid_waypoint_coordinates(tmp_path: Path):
    # Invalid float for lat should be skipped (not fatal).
    p = tmp_path / "bad_coords.gpx"
    p.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <wpt lat="nope" lon="-120.0"><name>Bad</name></wpt>
</gpx>
""",
        encoding="utf-8",
    )
    doc = read_onx_gpx(p)
    assert doc.waypoints() == []


def test_read_OnX_gpx_out_of_range_coords_emits_warning_and_skips(tmp_path: Path):
    p = tmp_path / "oor.gpx"
    p.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <wpt lat="91.0" lon="0.0"><name>OOR</name></wpt>
</gpx>
""",
        encoding="utf-8",
    )
    trace = _Trace()
    doc = read_onx_gpx(p, trace=trace)
    assert doc.waypoints() == []
    assert any(e.get("event") == "input.wpt.warning" for e in trace.events)


def test_read_OnX_gpx_reads_routes_and_preserves_time_when_present(tmp_path: Path):
    p = tmp_path / "route.gpx"
    p.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <rte>
    <name>Route 1</name>
    <rtept lat="45.0" lon="-120.0"><time>2020-01-01T00:00:00Z</time></rtept>
    <rtept lat="45.1" lon="-120.1"></rtept>
  </rte>
</gpx>
""",
        encoding="utf-8",
    )
    doc = read_onx_gpx(p)
    tracks = doc.tracks()
    assert len(tracks) == 1
    assert tracks[0].name == "Route 1"
    assert len(tracks[0].points) == 2
    assert tracks[0].points[0][3] is not None  # epoch_ms


def test_read_OnX_gpx_reads_onx_extensions_from_fixture() -> None:
    """
    Regression: OnX-exported GPX typically declares `xmlns:onx="https://wwww.onxmaps.com/"`
    and uses `<onx:color>` / `<onx:icon>`. We must reliably parse those extensions.
    """
    fixture = Path(__file__).parent / "fixtures" / "onx_waypoint_color_test.gpx"
    doc = read_onx_gpx(fixture)
    wpts = doc.waypoints()
    assert len(wpts) > 0

    # First waypoint in the fixture includes both color and icon in <extensions>.
    assert wpts[0].style.OnX_color_rgba is not None
    assert wpts[0].style.OnX_icon is not None
