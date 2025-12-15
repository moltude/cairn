from pathlib import Path

import yaml
from rich.console import Console

import cairn.commands.icon_cmd as icon_cmd


def _write_minimal_mappings(path: Path) -> None:
    data = {
        "version": 1,
        "policies": {"unknown_icon_handling": "keep_point_and_append_to_description"},
        "caltopo_to_onx": {
            "default_icon": "Location",
            "generic_symbols": ["point"],
            "symbol_map": {"skull": "Hazard", "camp": "Camp"},
            "keyword_map": {"Campsite": ["camp"]},
        },
        "onx_to_caltopo": {
            "default_symbol": "point",
            "icon_map": {"Hazard": "danger", "Camp": "camping"},
        },
    }
    path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_show_mappings_table_yaml_json_markdown_do_not_crash(tmp_path: Path, monkeypatch):
    mappings = tmp_path / "icon_mappings.yaml"
    _write_minimal_mappings(mappings)

    # Capture rich output.
    c = Console(record=True, width=120)
    monkeypatch.setattr(icon_cmd, "console", c)

    # table (default)
    icon_cmd.show_mappings(mappings_path=mappings)
    out = c.export_text()
    assert "Icon mapping configuration" in out
    assert "CalTopo → OnX" in out
    assert "OnX → CalTopo" in out

    # yaml
    c.clear()
    icon_cmd.show_mappings(mappings_path=mappings, format="yaml")
    out = c.export_text()
    assert "caltopo_to_onx" in out
    assert "onx_to_caltopo" in out

    # json
    c.clear()
    icon_cmd.show_mappings(mappings_path=mappings, format="json")
    out = c.export_text()
    assert '"caltopo_to_onx"' in out

    # markdown
    c.clear()
    icon_cmd.show_mappings(mappings_path=mappings, format="markdown")
    out = c.export_text()
    assert "## Icon mappings summary" in out


def test_show_mappings_direction_filter(tmp_path: Path, monkeypatch):
    mappings = tmp_path / "icon_mappings.yaml"
    _write_minimal_mappings(mappings)

    c = Console(record=True, width=120)
    monkeypatch.setattr(icon_cmd, "console", c)

    icon_cmd.show_mappings(mappings_path=mappings, direction="onx-to-caltopo")
    out = c.export_text()
    assert "OnX → CalTopo" in out
    assert "CalTopo → OnX" not in out
