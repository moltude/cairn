import yaml
import pytest
from pathlib import Path

from cairn.core.config_manager import ConfigManager, get_config_path
from cairn.core.config import ICON_COLOR_MAP, get_all_OnX_icons


def test_get_config_path_uses_home_and_creates_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    p = get_config_path()
    assert p == tmp_path / ".cairn" / "config.yaml"
    assert (tmp_path / ".cairn").exists()


def test_load_missing_file_returns_default(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    assert mgr.get_default_icon() == "Location"
    assert mgr.get_default_color().startswith("rgba(")


def test_load_empty_yaml_returns_default(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("", encoding="utf-8")
    mgr = ConfigManager(config_path=cfg_path)
    assert mgr.get_default_icon() == "Location"


def test_load_null_yaml_returns_default(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("null\n", encoding="utf-8")
    mgr = ConfigManager(config_path=cfg_path)
    assert mgr.get_default_icon() == "Location"


def test_load_invalid_yaml_returns_default_and_warns(tmp_path: Path, capsys):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(":\n- [\n", encoding="utf-8")  # invalid YAML
    mgr = ConfigManager(config_path=cfg_path)
    assert mgr.get_default_icon() == "Location"
    out = capsys.readouterr().out
    assert "Warning: Could not load config" in out


def test_save_writes_yaml(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    mgr.config["default_icon"] = "Location"
    mgr.save()
    assert cfg_path.exists()
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["default_icon"] == "Location"


def test_set_default_icon_valid_and_invalid(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)

    valid_icon = get_all_OnX_icons()[0]
    mgr.set_default_icon(valid_icon)
    assert mgr.get_default_icon() == valid_icon

    with pytest.raises(ValueError):
        mgr.set_default_icon("DefinitelyNotAnIcon")


def test_set_default_color_valid_and_invalid(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)

    mgr.set_default_color("#FF0000")
    assert mgr.get_default_color() == "rgba(255,0,0,1)"

    # Note: ColorMapper.parse_color does not raise; it falls back to blue.
    mgr.set_default_color("not-a-color")
    assert mgr.get_default_color() == "rgba(8,122,255,1)"


def test_set_default_color_forced_failure_raises_value_error(tmp_path: Path, monkeypatch):
    # Cover error path by forcing ColorMapper.parse_color to raise.
    from cairn.core import config_manager as cm

    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)

    monkeypatch.setattr(cm.ColorMapper, "parse_color", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")))
    with pytest.raises(ValueError):
        mgr.set_default_color("#FF0000")


def test_add_remove_mapping_and_color_override(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)

    valid_icon = get_all_OnX_icons()[0]
    mgr.add_mapping("symbol-1", valid_icon)
    assert mgr.get_mapping("symbol-1") == valid_icon
    assert mgr.get_all_mappings()["symbol-1"] == valid_icon

    mgr.add_mapping("symbol-2", valid_icon, color="#00FF00")
    # 00FF00 is closest to OnX lime
    assert mgr.get_color_for_symbol("symbol-2") == "rgba(132,212,0,1)"

    with pytest.raises(ValueError):
        mgr.add_mapping("symbol-3", "DefinitelyNotAnIcon")

    # Cover error path by forcing ColorMapper.transform_color to raise.
    from cairn.core import config_manager as cm
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(cm.ColorMapper, "transform_color", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("boom")))
        with pytest.raises(ValueError):
            mgr.add_mapping("symbol-4", valid_icon, color="bad-color")
    finally:
        monkeypatch.undo()

    mgr.remove_mapping("symbol-1")
    assert mgr.get_mapping("symbol-1") is None

    mgr.remove_mapping("symbol-2")
    assert mgr.get_mapping("symbol-2") is None
    assert mgr.get_color_for_symbol("symbol-2") is None


def test_get_all_keyword_mappings_default_empty(tmp_path: Path):
    mgr = ConfigManager(config_path=tmp_path / "config.yaml")
    assert mgr.get_all_keyword_mappings() == {}


def test_get_color_for_icon_prefers_icon_color_map_and_falls_back(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)

    # Guaranteed key in ICON_COLOR_MAP
    icon = next(iter(ICON_COLOR_MAP.keys()))
    assert mgr.get_color_for_icon(icon) == ICON_COLOR_MAP[icon]

    # Unknown icon falls back to default color
    mgr.set_default_color("#000000")
    assert mgr.get_color_for_icon("NotInMap") == "rgba(0,0,0,1)"


def test_reset_to_defaults_and_summary_counts(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    valid_icon = get_all_OnX_icons()[0]
    mgr.add_mapping("s1", valid_icon)
    mgr.add_mapping("s2", valid_icon, color="#FF0000")

    summary = mgr.get_summary()
    assert summary["symbol_mappings_count"] == 2
    assert summary["custom_colors_count"] == 1

    mgr.reset_to_defaults()
    assert mgr.get_all_mappings() == {}
    assert mgr.get_color_for_symbol("s2") is None
    assert mgr.get_default_icon() == "Location"


def test_add_mapping_creates_missing_dicts(tmp_path: Path):
    """
    Cover branches where ConfigManager creates missing `symbol_mappings`/`symbol_colors` dicts.
    """
    cfg_path = tmp_path / "config.yaml"
    mgr = ConfigManager(config_path=cfg_path)
    valid_icon = get_all_OnX_icons()[0]

    # Remove keys to force creation paths.
    mgr.config.pop("symbol_mappings", None)
    mgr.config.pop("symbol_colors", None)

    mgr.add_mapping("s1", valid_icon)
    assert mgr.get_mapping("s1") == valid_icon

    mgr.add_mapping("s2", valid_icon, color="#FF0000")
    assert mgr.get_color_for_symbol("s2") == "rgba(255,0,0,1)"
