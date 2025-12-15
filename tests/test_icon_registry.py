import json
from pathlib import Path

import yaml

from cairn.core.icon_registry import IconRegistry
from cairn.core.config import IconMappingConfig
from cairn.core.parser import parse_geojson
from cairn.model import MapDocument, Style, Waypoint


def _write_minimal_mappings(path: Path) -> None:
    data = {
        "version": 1,
        "policies": {"unknown_icon_handling": "keep_point_and_append_to_description"},
        "caltopo_to_onx": {
            "default_icon": "Location",
            "generic_symbols": ["point"],
            "symbol_map": {"skull": "Hazard"},
            "keyword_map": {"Campsite": ["camp"]},
        },
        "onx_to_caltopo": {
            "default_symbol": "point",
            "icon_map": {"Hazard": "danger"},
        },
    }
    path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_collect_onx_icon_inventory_counts_and_examples(tmp_path: Path):
    mappings = tmp_path / "icon_mappings.yaml"
    catalog = tmp_path / "icon_catalog.yaml"
    _write_minimal_mappings(mappings)

    reg = IconRegistry(mappings_path=mappings, catalog_path=catalog)

    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_waypoints", "Waypoints")
    doc.add_item(Waypoint(id="1", folder_id="OnX_waypoints", name="A1", lon=0.0, lat=0.0, style=Style(OnX_icon="Hazard")))
    doc.add_item(Waypoint(id="2", folder_id="OnX_waypoints", name="A2", lon=0.0, lat=0.0, style=Style(OnX_icon="Hazard")))
    doc.add_item(Waypoint(id="3", folder_id="OnX_waypoints", name="B1", lon=0.0, lat=0.0, style=Style(OnX_icon=None)))

    inv = reg.collect_onx_icon_inventory(doc)
    assert [(e.label, e.count) for e in inv] == [("Hazard", 2), ("(missing)", 1)]


def test_map_onx_icon_to_caltopo_symbol_direct_and_default(tmp_path: Path):
    mappings = tmp_path / "icon_mappings.yaml"
    catalog = tmp_path / "icon_catalog.yaml"
    _write_minimal_mappings(mappings)

    reg = IconRegistry(mappings_path=mappings, catalog_path=catalog)

    sym, src = reg.map_onx_icon_to_caltopo_symbol("Hazard")
    assert sym == "danger"
    assert src == "direct"

    sym, src = reg.map_onx_icon_to_caltopo_symbol("Unknown")
    assert sym == "point"
    assert src == "default"


def test_catalog_merge_appends_counts(tmp_path: Path):
    mappings = tmp_path / "icon_mappings.yaml"
    catalog = tmp_path / "icon_catalog.yaml"
    _write_minimal_mappings(mappings)

    reg = IconRegistry(mappings_path=mappings, catalog_path=catalog)

    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_waypoints", "Waypoints")
    doc.add_item(Waypoint(id="1", folder_id="OnX_waypoints", name="A1", lon=0.0, lat=0.0, style=Style(OnX_icon="Hazard")))

    inv = reg.collect_onx_icon_inventory(doc)
    reg.append_onx_icon_inventory_to_catalog(inv)

    # Append again
    reg.append_onx_icon_inventory_to_catalog(inv)

    data = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["observed_onx_icons"]["Hazard"]["count"] == 2


def test_collect_caltopo_to_onx_rows_uses_config_and_emits_onx_colors(tmp_path: Path):
    # Minimal GeoJSON with two markers, one with a marker-color.
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "f1",
                "geometry": None,
                "properties": {"class": "Folder", "title": "Folder", "folderId": None},
            },
            {
                "type": "Feature",
                "id": "w1",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                "properties": {
                    "class": "Marker",
                    "title": "Test 1",
                    "description": "",
                    "marker-symbol": "skull",
                    "marker-color": "#FF0000",
                    "folderId": "f1",
                },
            },
            {
                "type": "Feature",
                "id": "w2",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                "properties": {
                    "class": "Marker",
                    "title": "Test 2",
                    "description": "",
                    "marker-symbol": "point",
                    "folderId": "f1",
                },
            },
        ],
    }
    p = tmp_path / "in.json"
    p.write_text(json.dumps(geojson), encoding="utf-8")
    parsed = parse_geojson(p)

    cfg = IconMappingConfig(None)
    cfg.symbol_map = {"skull": "Hazard"}
    cfg.keyword_map = {"Campsite": ["camp"]}
    cfg.default_icon = "Location"
    cfg.default_color = "rgba(8,122,255,1)"

    mappings = tmp_path / "icon_mappings.yaml"
    catalog = tmp_path / "icon_catalog.yaml"
    _write_minimal_mappings(mappings)
    reg = IconRegistry(mappings_path=mappings, catalog_path=catalog)

    rows = reg.collect_caltopo_to_onx_mapping_rows_using_config(parsed, cfg)

    # Expect a skull -> Hazard row with red quantized to OnX waypoint palette.
    skull_rows = [r for r in rows if r.incoming == "skull" and r.mapped == "Hazard"]
    assert skull_rows
    assert "rgba(255,0,0,1)" in skull_rows[0].colors
