from pathlib import Path

import pytest

from cairn.io.onx_gpx import read_OnX_gpx


class _Trace:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event: dict) -> None:
        self.events.append(event)


def test_read_OnX_gpx_empty_file_raises(tmp_path: Path):
    p = tmp_path / "empty.gpx"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        read_OnX_gpx(p)


def test_read_OnX_gpx_invalid_xml_raises(tmp_path: Path):
    p = tmp_path / "bad.gpx"
    p.write_text("not xml", encoding="utf-8")
    with pytest.raises(ValueError, match="XML parse error"):
        read_OnX_gpx(p)


def test_read_OnX_gpx_wrong_root_raises(tmp_path: Path):
    p = tmp_path / "wrong.gpx"
    p.write_text("<nope></nope>", encoding="utf-8")
    with pytest.raises(ValueError, match="does not appear to be a GPX"):
        read_OnX_gpx(p)


def test_read_OnX_gpx_rejects_legacy_OnX_namespace(tmp_path: Path):
    """
    Strict behavior: reject any legacy/case-variant OnX namespace declarations.
    """
    p = tmp_path / "legacy_ns.gpx"
    p.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:OnX="https://wwww.OnXmaps.com/" version="1.1">
  <wpt lat="45.0" lon="-120.0"><name>Test</name></wpt>
</gpx>
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unsupported OnX namespace URI"):
        read_OnX_gpx(p)


def test_read_OnX_gpx_skips_invalid_waypoint_coordinates(tmp_path: Path):
    # Invalid float for lat should be skipped (not fatal).
    p = tmp_path / "bad_coords.gpx"
    p.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1">
  <wpt lat="nope" lon="-120.0"><name>Bad</name></wpt>
</gpx>
""",
        encoding="utf-8",
    )
    doc = read_OnX_gpx(p)
    assert doc.waypoints() == []


def test_read_OnX_gpx_out_of_range_coords_emits_warning_and_skips(tmp_path: Path):
    p = tmp_path / "oor.gpx"
    p.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1">
  <wpt lat="91.0" lon="0.0"><name>OOR</name></wpt>
</gpx>
""",
        encoding="utf-8",
    )
    trace = _Trace()
    doc = read_OnX_gpx(p, trace=trace)
    assert doc.waypoints() == []
    assert any(e.get("event") == "input.wpt.warning" for e in trace.events)


def test_read_OnX_gpx_reads_routes_and_preserves_time_when_present(tmp_path: Path):
    p = tmp_path / "route.gpx"
    p.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1">
  <rte>
    <name>Route 1</name>
    <rtept lat="45.0" lon="-120.0"><time>2020-01-01T00:00:00Z</time></rtept>
    <rtept lat="45.1" lon="-120.1"></rtept>
  </rte>
</gpx>
""",
        encoding="utf-8",
    )
    doc = read_OnX_gpx(p)
    tracks = doc.tracks()
    assert len(tracks) == 1
    assert tracks[0].name == "Route 1"
    assert len(tracks[0].points) == 2
    assert tracks[0].points[0][3] is not None  # epoch_ms
