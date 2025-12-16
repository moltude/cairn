import yaml

import pytest

from cairn.core.config import (
    ONX_ICON_NAMES_CANONICAL,
    get_all_onx_icons,
    normalize_onx_icon_name,
    save_user_mapping,
)


def test_get_all_OnX_icons_is_canonical_list():
    assert get_all_onx_icons() == list(ONX_ICON_NAMES_CANONICAL)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("xc skiing", "XC Skiing"),
        ("XC Skiing", "XC Skiing"),
        ("xcskiing", "XC Skiing"),
        ("  Water   Source  ", "Water Source"),
        ("DOG SLEDDING", "Dog Sledding"),
        ("road-barrier", "Road Barrier"),
        ("mountain_biking", "Mountain Biking"),
    ],
)
def test_normalize_onx_icon_name(raw, expected):
    assert normalize_onx_icon_name(raw) == expected


def test_save_user_mapping_writes_canonical_icon(tmp_path):
    cfg_path = tmp_path / "cairn_config.yaml"
    save_user_mapping("skull", "xc skiing", config_path=cfg_path)
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["symbol_mappings"]["skull"] == "XC Skiing"


def test_save_user_mapping_rejects_invalid_icon(tmp_path):
    cfg_path = tmp_path / "cairn_config.yaml"
    with pytest.raises(ValueError):
        save_user_mapping("skull", "NotARealIcon", config_path=cfg_path)
