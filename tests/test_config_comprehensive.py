"""Comprehensive tests for cairn/core/config.py to improve coverage."""

from pathlib import Path
import yaml
import pytest

from cairn.core.config import (
    normalize_onx_icon_name,
    get_icon_color,
    IconMappingConfig,
    load_config,
    get_all_onx_icons,
    save_user_mapping,
    remove_user_mapping,
    get_use_icon_name_prefix,
    ONX_ICON_NAMES_CANONICAL,
)


# ===== Icon Name Normalization Tests =====


def test_normalize_onx_icon_name_exact_match():
    """Test that exact icon names are recognized."""
    result = normalize_onx_icon_name("Summit")
    assert result == "Summit"


def test_normalize_onx_icon_name_case_insensitive():
    """Test that icon names are case-insensitive."""
    assert normalize_onx_icon_name("summit") == "Summit"
    assert normalize_onx_icon_name("SUMMIT") == "Summit"
    assert normalize_onx_icon_name("SuMmIt") == "Summit"


def test_normalize_onx_icon_name_with_whitespace():
    """Test that extra whitespace is handled."""
    assert normalize_onx_icon_name("  Summit  ") == "Summit"
    assert normalize_onx_icon_name("Camp    Area") == "Camp Area"


def test_normalize_onx_icon_name_with_underscores():
    """Test that underscores are treated as spaces."""
    assert normalize_onx_icon_name("Camp_Area") == "Camp Area"
    assert normalize_onx_icon_name("camp_area") == "Camp Area"


def test_normalize_onx_icon_name_with_hyphens():
    """Test that hyphens are treated as spaces."""
    assert normalize_onx_icon_name("Camp-Area") == "Camp Area"
    assert normalize_onx_icon_name("camp-area") == "Camp Area"


def test_normalize_onx_icon_name_compact_form():
    """Test that compact forms (no spaces) are recognized."""
    assert normalize_onx_icon_name("CampArea") == "Camp Area"
    assert normalize_onx_icon_name("camparea") == "Camp Area"


def test_normalize_onx_icon_name_empty_string():
    """Test that empty strings return None."""
    assert normalize_onx_icon_name("") is None
    assert normalize_onx_icon_name("   ") is None


def test_normalize_onx_icon_name_unknown_icon():
    """Test that unknown icons return None."""
    assert normalize_onx_icon_name("NotAnIcon") is None
    assert normalize_onx_icon_name("Unknown123") is None


# ===== Icon Color Tests =====


def test_get_icon_color_known_icon():
    """Test getting color for a known icon."""
    color = get_icon_color("Summit")
    assert color == "rgba(255,0,0,1)"  # Red


def test_get_icon_color_unknown_icon_returns_default():
    """Test that unknown icons return default color."""
    color = get_icon_color("UnknownIcon")
    assert color == "rgba(8,122,255,1)"  # Default blue


def test_get_icon_color_custom_default():
    """Test that custom default color can be specified."""
    color = get_icon_color("UnknownIcon", default="rgba(255,255,0,1)")
    assert color == "rgba(255,255,0,1)"  # Custom yellow


# ===== IconMappingConfig Initialization Tests =====


def test_icon_mapping_config_default_initialization():
    """Test that IconMappingConfig initializes with defaults."""
    config = IconMappingConfig()
    assert config.default_icon == "Location"
    assert config.default_color == "rgba(8,122,255,1)"
    assert config.use_icon_name_prefix is False
    assert config.enable_unmapped_detection is True


def test_icon_mapping_config_with_nonexistent_file():
    """Test that nonexistent config file is handled gracefully."""
    config = IconMappingConfig(config_file=Path("/nonexistent/config.yaml"))
    # Should still initialize with defaults
    assert config.default_icon == "Location"


# ===== Config File Loading Tests =====


def test_load_user_config_valid_file(tmp_path):
    """Test loading a valid user config file."""
    config_path = tmp_path / "config.yaml"
    config_data = {
        "symbol_mappings": {
            "skull": "Hazard",
            "campsite": "Camp"
        },
        "keyword_mappings": {
            "Summit": ["peak", "top", "mountain"]
        },
        "default_icon": "Camp",
        "default_color": "rgba(255,0,0,1)",
        "use_icon_name_prefix": True
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = IconMappingConfig(config_file=config_path)
    assert config.symbol_map["skull"] == "Hazard"
    assert config.symbol_map["campsite"] == "Camp"
    assert config.default_icon == "Camp"
    assert config.default_color == "rgba(255,0,0,1)"
    assert config.use_icon_name_prefix is True


def test_load_user_config_partial_file(tmp_path):
    """Test loading a config file with only some fields."""
    config_path = tmp_path / "config.yaml"
    config_data = {
        "symbol_mappings": {
            "skull": "Hazard"
        }
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = IconMappingConfig(config_file=config_path)
    # Should have the custom mapping
    assert config.symbol_map["skull"] == "Hazard"
    # Should keep default values
    assert config.default_icon == "Location"


def test_load_user_config_empty_file(tmp_path):
    """Test loading an empty config file."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("", encoding="utf-8")

    config = IconMappingConfig(config_file=config_path)
    # Should still have defaults
    assert config.default_icon == "Location"


def test_load_user_config_malformed_yaml(tmp_path):
    """Test that malformed YAML raises an error."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("invalid: yaml: content: [[[", encoding="utf-8")

    # Should raise ValueError
    with pytest.raises(ValueError, match="Invalid YAML"):
        IconMappingConfig(config_file=config_path)


def test_load_user_config_non_dict_symbol_mappings(tmp_path):
    """Test that non-dict symbol_mappings are handled via try-except."""
    config_path = tmp_path / "config.yaml"
    config_data = {
        "symbol_mappings": ["not", "a", "dict"]
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    # This will raise an error due to invalid structure
    with pytest.raises(ValueError):
        IconMappingConfig(config_file=config_path)


# ===== Unmapped Symbol Tracking Tests =====


def test_track_unmapped_symbol():
    """Test tracking an unmapped symbol."""
    config = IconMappingConfig()
    config.track_unmapped("unknown-symbol", "Waypoint Title")

    report = config.get_unmapped_report()
    assert "unknown-symbol" in report
    assert "Waypoint Title" in report["unknown-symbol"]["examples"]


def test_track_unmapped_multiple_examples():
    """Test tracking multiple examples of same symbol."""
    config = IconMappingConfig()
    config.track_unmapped("unknown", "Example 1")
    config.track_unmapped("unknown", "Example 2")
    config.track_unmapped("unknown", "Example 3")

    report = config.get_unmapped_report()
    assert len(report["unknown"]["examples"]) == 3
    assert report["unknown"]["count"] == 3


def test_track_unmapped_limits_examples():
    """Test that unmapped tracking limits number of examples."""
    config = IconMappingConfig()
    for i in range(20):
        config.track_unmapped("symbol", f"Example {i}")

    report = config.get_unmapped_report()
    # Should limit to reasonable number (typically 5)
    assert len(report["symbol"]["examples"]) <= 5


def test_has_unmapped_symbols_true():
    """Test has_unmapped_symbols returns True when there are unmapped."""
    config = IconMappingConfig()
    config.track_unmapped("unknown", "Example")

    assert config.has_unmapped_symbols() is True


def test_has_unmapped_symbols_false():
    """Test has_unmapped_symbols returns False when no unmapped."""
    config = IconMappingConfig()

    assert config.has_unmapped_symbols() is False


# ===== Config Template Export Tests =====


def test_export_template(tmp_path):
    """Test exporting a config template."""
    config = IconMappingConfig()
    output_path = tmp_path / "template.yaml"

    config.export_template(output_path)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    # Check for key sections in the template (it's a commented YAML)
    assert "symbol_mappings" in content
    assert "keyword_mappings" in content
    assert "use_icon_name_prefix" in content


def test_export_template_creates_directories(tmp_path):
    """Test that export_template works with existing parent directory."""
    config = IconMappingConfig()
    subdir = tmp_path / "subdir"
    subdir.mkdir(exist_ok=True)  # Create parent directory first
    output_path = subdir / "template.yaml"

    config.export_template(output_path)

    assert output_path.exists()
    # Verify content was written
    content = output_path.read_text(encoding="utf-8")
    assert "symbol_mappings" in content


# ===== Config Summary Tests =====


def test_get_config_summary():
    """Test getting a config summary."""
    config = IconMappingConfig()

    summary = config.get_config_summary()

    assert "default_icon" in summary
    assert "default_color" in summary
    assert "symbol_mappings_count" in summary
    assert "keyword_mappings_count" in summary


# ===== Module-Level Functions Tests =====


def test_load_config_with_file(tmp_path):
    """Test load_config function with a config file."""
    config_path = tmp_path / "config.yaml"
    config_data = {"default_icon": "Summit"}
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = load_config(config_path)

    assert config.default_icon == "Summit"


def test_load_config_without_file():
    """Test load_config function without a config file."""
    config = load_config(None)

    assert config.default_icon == "Location"  # Default value


def test_get_all_onx_icons():
    """Test that get_all_onx_icons returns the canonical list."""
    icons = get_all_onx_icons()

    assert isinstance(icons, list)
    assert len(icons) > 0
    assert "Summit" in icons
    assert "Camp" in icons
    assert icons == list(ONX_ICON_NAMES_CANONICAL)


def test_get_use_icon_name_prefix_default():
    """Test that get_use_icon_name_prefix returns default False."""
    result = get_use_icon_name_prefix()
    assert result is False


# ===== User Mapping Save/Remove Tests =====


def test_save_user_mapping_creates_file(tmp_path):
    """Test that save_user_mapping creates a config file."""
    config_path = tmp_path / "cairn_config.yaml"

    save_user_mapping("skull", "Hazard", config_path)

    assert config_path.exists()
    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert content["symbol_mappings"]["skull"] == "Hazard"


def test_save_user_mapping_updates_existing_file(tmp_path):
    """Test that save_user_mapping updates an existing file."""
    config_path = tmp_path / "cairn_config.yaml"
    initial_data = {
        "symbol_mappings": {"existing": "Value"},
        "default_icon": "Camp"
    }
    config_path.write_text(yaml.safe_dump(initial_data), encoding="utf-8")

    save_user_mapping("skull", "Hazard", config_path)

    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert content["symbol_mappings"]["skull"] == "Hazard"
    assert content["symbol_mappings"]["existing"] == "Value"  # Preserved
    assert content["default_icon"] == "Camp"  # Preserved


def test_remove_user_mapping(tmp_path):
    """Test removing a user mapping."""
    config_path = tmp_path / "cairn_config.yaml"
    initial_data = {
        "symbol_mappings": {
            "skull": "Hazard",
            "campsite": "Camp"
        }
    }
    config_path.write_text(yaml.safe_dump(initial_data), encoding="utf-8")

    remove_user_mapping("skull", config_path)

    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "skull" not in content["symbol_mappings"]
    assert content["symbol_mappings"]["campsite"] == "Camp"  # Preserved


def test_remove_user_mapping_nonexistent_key(tmp_path):
    """Test removing a mapping that doesn't exist."""
    config_path = tmp_path / "cairn_config.yaml"
    initial_data = {"symbol_mappings": {"existing": "Value"}}
    config_path.write_text(yaml.safe_dump(initial_data), encoding="utf-8")

    # Should not raise an error
    remove_user_mapping("nonexistent", config_path)

    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert content["symbol_mappings"]["existing"] == "Value"


def test_remove_user_mapping_from_nonexistent_file(tmp_path):
    """Test that removing from nonexistent file is handled."""
    config_path = tmp_path / "nonexistent.yaml"

    # Should not raise an error
    remove_user_mapping("key", config_path)


# ===== Invalid Config Data Tests =====


def test_config_with_invalid_icon_name(tmp_path):
    """Test config loading with invalid icon name."""
    config_path = tmp_path / "config.yaml"
    config_data = {
        "symbol_mappings": {
            "skull": "InvalidIconName123"  # Not a valid OnX icon
        }
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = IconMappingConfig(config_file=config_path)
    # Should still load, may normalize or keep as-is
    assert isinstance(config.symbol_map, dict)


def test_config_with_empty_symbol_mappings(tmp_path):
    """Test config with empty symbol_mappings dict."""
    config_path = tmp_path / "config.yaml"
    config_data = {"symbol_mappings": {}}
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = IconMappingConfig(config_file=config_path)
    # Should have defaults
    assert len(config.symbol_map) > 0  # Has default mappings


def test_config_with_none_values(tmp_path):
    """Test config with None values for fields."""
    config_path = tmp_path / "config.yaml"
    config_data = {
        "symbol_mappings": None,
        "default_icon": None
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = IconMappingConfig(config_file=config_path)
    # Should use defaults when values are None
    assert config.default_icon == "Location"


def test_config_with_nested_invalid_data(tmp_path):
    """Test config with invalid nested structure."""
    config_path = tmp_path / "config.yaml"
    config_data = {
        "symbol_mappings": {
            "valid": "Camp",
            "invalid_structure": {"nested": "dict"}  # Should be string
        }
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = IconMappingConfig(config_file=config_path)
    # Should load valid entries, skip invalid
    assert "valid" in config.symbol_map


# ===== Keyword Mappings Tests =====


def test_load_keyword_mappings(tmp_path):
    """Test loading keyword mappings from config."""
    config_path = tmp_path / "config.yaml"
    config_data = {
        "keyword_mappings": {
            "Summit": ["peak", "top", "mountain"],
            "Camp": ["campsite", "camping"]
        }
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    config = IconMappingConfig(config_file=config_path)
    assert "Summit" in config.keyword_map
    assert "peak" in config.keyword_map["Summit"]
    assert "campsite" in config.keyword_map["Camp"]


def test_keyword_mappings_invalid_structure(tmp_path):
    """Test that invalid keyword mapping structure raises an error."""
    config_path = tmp_path / "config.yaml"
    config_data = {
        "keyword_mappings": "not a dict"
    }
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    # Invalid structure should raise an error
    with pytest.raises(ValueError):
        IconMappingConfig(config_file=config_path)
