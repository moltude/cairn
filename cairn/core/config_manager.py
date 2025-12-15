"""
Enhanced configuration management for Cairn.

⚠️  NOTE: This module is currently UNUSED in the production codebase.
It was designed for future programmatic config management but the current
implementation uses cairn/core/config.py with YAML-based configuration instead.

This module is kept for potential future use or as a reference implementation.
If you're looking for the active config system, see cairn/core/config.py.

This module provides comprehensive configuration management including
default icon/color settings, validation, and persistence.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import yaml

from cairn.core.config import get_all_OnX_icons, ICON_COLOR_MAP
from cairn.core.color_mapper import ColorMapper


def get_config_path() -> Path:
    """Get config file path in user home directory."""
    config_dir = Path.home() / ".cairn"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "config.yaml"


class ConfigManager:
    """Enhanced configuration management with defaults and validation."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file (defaults to ~/.cairn/config.yaml)
        """
        self.config_path = config_path or get_config_path()
        self.config = self.load()

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.

        Returns:
            Configuration dictionary
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config if config else self._default_config()
            except (yaml.YAMLError, IOError) as e:
                print(f"Warning: Could not load config: {e}")
                return self._default_config()
        return self._default_config()

    def save(self):
        """Save configuration to file."""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def _default_config(self) -> Dict[str, Any]:
        """
        Get default configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "default_icon": "Location",
            "default_color": "rgba(8,122,255,1)",
            "use_icon_name_prefix": False,
            "symbol_mappings": {},
            "keyword_mappings": {},
            "symbol_colors": {},
            "enable_unmapped_detection": True
        }

    def get_default_icon(self) -> str:
        """
        Get configured default icon.

        Returns:
            Default icon name
        """
        return self.config.get("default_icon", "Location")

    def set_default_icon(self, icon: str):
        """
        Set default icon with validation.

        Args:
            icon: OnX icon name

        Raises:
            ValueError: If icon is not valid
        """
        valid_icons = get_all_OnX_icons()
        if icon not in valid_icons:
            raise ValueError(
                f"Invalid icon: '{icon}'. "
                f"Must be one of {len(valid_icons)} valid OnX icons. "
                f"Run 'python main.py config --icons' to see all options."
            )
        self.config["default_icon"] = icon
        self.save()

    def get_default_color(self) -> str:
        """
        Get configured default color.

        Returns:
            Default color in rgba format
        """
        return self.config.get("default_color", "rgba(8,122,255,1)")

    def set_default_color(self, color: str):
        """
        Set default color with validation.

        Args:
            color: Color in rgba or hex format

        Raises:
            ValueError: If color format is invalid
        """
        try:
            # Validate color format by parsing it
            ColorMapper.parse_color(color)
            # Transform to OnX format
            OnX_color = ColorMapper.transform_color(color)
            self.config["default_color"] = OnX_color
            self.save()
        except Exception as e:
            raise ValueError(f"Invalid color format: {e}")

    def add_mapping(self, symbol: str, icon: str, color: Optional[str] = None):
        """
        Add a symbol mapping.

        Args:
            symbol: CalTopo symbol
            icon: OnX icon name
            color: Optional color override

        Raises:
            ValueError: If icon is invalid
        """
        # Validate icon
        valid_icons = get_all_OnX_icons()
        if icon not in valid_icons:
            raise ValueError(f"Invalid icon: '{icon}'")

        # Add symbol mapping
        if "symbol_mappings" not in self.config:
            self.config["symbol_mappings"] = {}
        self.config["symbol_mappings"][symbol] = icon

        # Add color if provided
        if color:
            try:
                OnX_color = ColorMapper.transform_color(color)
                if "symbol_colors" not in self.config:
                    self.config["symbol_colors"] = {}
                self.config["symbol_colors"][symbol] = OnX_color
            except Exception as e:
                raise ValueError(f"Invalid color format: {e}")

        self.save()

    def remove_mapping(self, symbol: str):
        """
        Remove a symbol mapping.

        Args:
            symbol: CalTopo symbol to remove
        """
        if "symbol_mappings" in self.config and symbol in self.config["symbol_mappings"]:
            del self.config["symbol_mappings"][symbol]

        if "symbol_colors" in self.config and symbol in self.config["symbol_colors"]:
            del self.config["symbol_colors"][symbol]

        self.save()

    def get_mapping(self, symbol: str) -> Optional[str]:
        """
        Get icon mapping for a symbol.

        Args:
            symbol: CalTopo symbol

        Returns:
            Icon name or None if not mapped
        """
        return self.config.get("symbol_mappings", {}).get(symbol)

    def get_all_mappings(self) -> Dict[str, str]:
        """
        Get all symbol mappings.

        Returns:
            Dictionary of symbol -> icon mappings
        """
        return self.config.get("symbol_mappings", {})

    def get_all_keyword_mappings(self) -> Dict[str, list]:
        """
        Get all keyword mappings.

        Returns:
            Dictionary of icon -> keywords mappings
        """
        return self.config.get("keyword_mappings", {})

    def get_color_for_symbol(self, symbol: str) -> Optional[str]:
        """
        Get color override for a symbol.

        Args:
            symbol: CalTopo symbol

        Returns:
            Color in rgba format or None
        """
        return self.config.get("symbol_colors", {}).get(symbol)

    def get_color_for_icon(self, icon: str) -> str:
        """
        Get color for an icon (from config or defaults).

        Args:
            icon: OnX icon name

        Returns:
            Color in rgba format
        """
        # Check if there's a custom color in ICON_COLOR_MAP
        if icon in ICON_COLOR_MAP:
            return ICON_COLOR_MAP[icon]
        # Fall back to default color
        return self.get_default_color()

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self.config = self._default_config()
        self.save()

    def get_summary(self) -> Dict[str, Any]:
        """
        Get configuration summary.

        Returns:
            Dictionary with configuration statistics
        """
        return {
            "default_icon": self.get_default_icon(),
            "default_color": self.get_default_color(),
            "use_icon_name_prefix": self.config.get("use_icon_name_prefix", False),
            "symbol_mappings_count": len(self.config.get("symbol_mappings", {})),
            "keyword_mappings_count": len(self.config.get("keyword_mappings", {})),
            "custom_colors_count": len(self.config.get("symbol_colors", {})),
            "unmapped_detection_enabled": self.config.get("enable_unmapped_detection", True)
        }
