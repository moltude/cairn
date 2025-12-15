import json
from pathlib import Path

import yaml

from cairn.core.icon_registry import IconRegistry
from cairn.io import caltopo_geojson
from cairn.model import MapDocument, Style, Waypoint


def _write_minimal_mappings(path: Path) -> None:
    data = {
        "version": 1,
        "policies": {"unknown_icon_handling": "keep_point_and_append_to_description"},
        "caltopo_to_onx": {
            "default_icon": "Location",
            "generic_symbols": ["point"],
            "symbol_map": {},
            "keyword_map": {},
        },
        "onx_to_caltopo": {"default_symbol": "point", "icon_map": {}},
    }
    path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_unknown_onx_icon_is_appended_to_description_in_notes_only(tmp_path: Path, monkeypatch):
    mappings = tmp_path / "icon_mappings.yaml"
    catalog = tmp_path / "icon_catalog.yaml"
    _write_minimal_mappings(mappings)

    # Force caltopo_geojson to use our temp registry instead of repo file.
    reg = IconRegistry(mappings_path=mappings, catalog_path=catalog)
    monkeypatch.setattr(caltopo_geojson, "_ICON_REGISTRY", reg)

    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_waypoints", "Waypoints")
    doc.add_item(
        Waypoint(
            id="w1",
            folder_id="OnX_waypoints",
            name="My WP",
            lon=1.0,
            lat=2.0,
            notes="hello",
            style=Style(OnX_icon="MysteryIcon", OnX_color_rgba="rgba(8,122,255,1)"),
        )
    )

    out = tmp_path / "out.json"
    caltopo_geojson.write_caltopo_geojson(doc, out, description_mode="notes_only")

    data = json.loads(out.read_text(encoding="utf-8"))
    markers = [f for f in data["features"] if f.get("properties", {}).get("class") == "Marker"]
    assert len(markers) == 1
    desc = markers[0]["properties"]["description"]
    assert "hello" in desc
    assert "OnX icon: MysteryIcon" in desc
