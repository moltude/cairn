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

    assert "<OnX:color>rgba(255,0,255,1)</OnX:color>" in gpx
    assert "<OnX:style>solid</OnX:style>" in gpx
    assert "<OnX:weight>4.0</OnX:weight>" in gpx
    assert "color=rgba(255,0,255,1)" in gpx
