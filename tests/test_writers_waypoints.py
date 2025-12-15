"""Integration tests for GPX waypoint writer behavior."""

import yaml

from cairn.core.config import load_config
from cairn.core.parser import ParsedFeature
from cairn.core.writers import write_gpx_waypoints


def test_write_gpx_waypoints_respects_config_icon_overrides_and_marker_color(tmp_path):
    # Create a minimal CalTopo marker feature with marker-color.
    feature_dict = {
        "id": "marker-1",
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-114.5, 45.5]},
        "properties": {
            "class": "Marker",
            "title": "Test Waypoint",
            "description": "",
            "marker-color": "FF0000",
            "marker-symbol": "skull",
            "folderId": "folder-1",
        },
    }
    feature = ParsedFeature(feature_dict)

    # Override skull → Campsite via a temp config file.
    cfg_path = tmp_path / "cairn_config.yaml"
    cfg_path.write_text(
        yaml.safe_dump({"symbol_mappings": {"skull": "Campsite"}}),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)

    out_path = tmp_path / "out.gpx"
    write_gpx_waypoints([feature], out_path, "Folder", sort=False, config=cfg)

    gpx = out_path.read_text(encoding="utf-8")

    # Config override should be reflected in the exported GPX.
    assert "<OnX:icon>Campsite</OnX:icon>" in gpx

    # Marker-color should be preserved (but quantized to an official waypoint color).
    assert "<OnX:color>rgba(255,0,0,1)</OnX:color>" in gpx

