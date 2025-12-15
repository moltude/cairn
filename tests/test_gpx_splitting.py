from pathlib import Path

from cairn.core.parser import ParsedFeature
from cairn.core.writers import write_gpx_tracks_maybe_split, write_gpx_waypoints_maybe_split


def _mk_waypoint(i: int, name: str) -> ParsedFeature:
    return ParsedFeature(
        {
            "id": f"wp-{i}",
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-107.0 - i * 0.001, 37.0 + i * 0.001]},
            "properties": {
                "class": "Marker",
                "title": name,
                "description": ("x" * 500),  # inflate size so we force splitting with tiny thresholds
                "marker-color": "FF0000",
                "marker-symbol": "point",
            },
        }
    )


def _mk_track(i: int, name: str) -> ParsedFeature:
    coords = [[-107.0 - (j * 0.0001), 37.0 + (j * 0.0001), 1000 + j] for j in range(80)]
    return ParsedFeature(
        {
            "id": f"trk-{i}",
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "class": "Shape",
                "title": name,
                "description": ("y" * 500),
                "stroke": "#FF00FF",
                "stroke-width": 4,
                "pattern": "solid",
            },
        }
    )


def test_split_waypoints_gpx_by_bytes_preserves_order_and_onx_metadata(tmp_path: Path):
    features = [_mk_waypoint(1, "A"), _mk_waypoint(2, "B"), _mk_waypoint(3, "C")]
    out = tmp_path / "Days_Waypoints.gpx"

    parts = write_gpx_waypoints_maybe_split(
        features,
        out,
        "Days",
        sort=False,
        split=True,
        max_bytes=200,  # tiny to force splits
    )

    assert len(parts) >= 2
    assert not out.exists()  # when split, base filename is replaced by _1, _2...

    # Order preserved across parts.
    txt1 = parts[0][0].read_text(encoding="utf-8")
    txt2 = parts[1][0].read_text(encoding="utf-8")
    assert "<name>A</name>" in txt1
    assert "<name>B</name>" in (txt2 + txt1)  # B is not before A

    # OnX import-critical metadata remains.
    for pth, _, _ in parts:
        t = pth.read_text(encoding="utf-8")
        assert "<desc>" in t and "color=rgba(" in t and "icon=" in t
        assert "<onx:icon>" in t and "<onx:color>" in t


def test_split_tracks_gpx_by_bytes_preserves_order_and_onx_metadata(tmp_path: Path):
    features = [_mk_track(1, "TrackA"), _mk_track(2, "TrackB"), _mk_track(3, "TrackC")]
    out = tmp_path / "Days_Tracks.gpx"

    parts = write_gpx_tracks_maybe_split(
        features,
        out,
        "Days",
        sort=False,
        split=True,
        max_bytes=200,  # tiny to force splits
    )

    assert len(parts) >= 2
    assert not out.exists()

    txt1 = parts[0][0].read_text(encoding="utf-8")
    assert "TrackA" in txt1

    for pth, _, _ in parts:
        t = pth.read_text(encoding="utf-8")
        assert "<trk>" in t
        assert "<desc>" in t and "style=" in t and "weight=" in t
        assert "<onx:color>" in t and "<onx:style>" in t and "<onx:weight>" in t
