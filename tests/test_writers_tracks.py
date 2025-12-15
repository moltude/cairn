"""Integration tests for GPX track writer behavior."""

from cairn.core.parser import ParsedFeature
from cairn.core.writers import write_gpx_tracks


def test_write_gpx_tracks_palette_color_round_trips(tmp_path):
    # Use an exact OnX palette RGB in stroke so mapping is deterministic.
    feature_dict = {
        "id": "trk-1",
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-114.5, 45.5], [-114.6, 45.6]]},
        "properties": {
            "class": "Shape",
            "title": "My Track",
            "description": "Hello",
            "stroke": "#FF00FF",  # fuchsia
            "stroke-width": 4,
            "pattern": "solid",
        },
    }
    feature = ParsedFeature(feature_dict)

    out_path = tmp_path / "out.gpx"
    write_gpx_tracks([feature], out_path, "Folder", sort=False)
    gpx = out_path.read_text(encoding="utf-8")

    assert "<onx:color>rgba(255,0,255,1)</onx:color>" in gpx
    assert "<onx:style>solid</onx:style>" in gpx
    assert "<onx:weight>4.0</onx:weight>" in gpx
    assert "color=rgba(255,0,255,1)" in gpx
