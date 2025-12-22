"""File and directory browsing operations for the TUI module.

This module manages all file system browsing logic extracted from app.py,
consolidating duplicate directory listing implementations.
"""

import os
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from textual.coordinate import Coordinate
from textual.widgets import DataTable, Static
from rich.text import Text

from cairn.tui.models import _PARSEABLE_INPUT_EXTS, _VISIBLE_INPUT_EXTS
from cairn.tui.debug import agent_log
from cairn.tui.tables import TableManager

if TYPE_CHECKING:
    from cairn.tui.app import CairnTuiApp

# Import profiling
try:
    from cairn.tui.profiling import profile_operation
except ImportError:
    # Fallback if profiling module not available
    from contextlib import nullcontext as profile_operation


class FileBrowserManager:
    """Handles all file/directory browsing operations."""

    def __init__(self, app: "CairnTuiApp") -> None:
        """Initialize file browser manager.

        Args:
            app: The CairnTuiApp instance (for accessing model, config, etc.)
        """
        self.app: "CairnTuiApp" = app
        self._file_browser_dir: Optional[Path] = None

    def use_tree_browser(self) -> bool:
        """Check if tree browser A/B test is enabled."""
        return self.app._use_tree_browser()

    def get_initial_directory(self) -> Path:
        """Get initial directory for file browser, respecting default_path config.

        Returns:
            Path to use as initial directory (default_path if set and valid, else home)
        """
        # Check for default_path in config (takes precedence)
        default_path_str = getattr(self.app._config, "default_path", None)
        if default_path_str:
            try:
                default_path = Path(default_path_str).expanduser().resolve()

                # Validation 1: Path must exist
                if not default_path.exists():
                    return Path.home()
                # Validation 2: Must be a directory
                if not default_path.is_dir():
                    return Path.home()
                # Validation 3: Must be readable
                if not os.access(default_path, os.R_OK):
                    return Path.home()
                # Validation 4: Must be listable (can iterate contents)
                try:
                    list(default_path.iterdir())
                    # All validations passed - use this path
                    return default_path
                except (PermissionError, OSError):
                    return Path.home()
            except Exception:
                return Path.home()

        # Fallback to state.default_root or home
        if hasattr(self.app, "_state") and self.app._state.default_root:
            try:
                return Path(self.app._state.default_root).expanduser()
            except Exception:
                pass
        return Path.home()

    def get_file_browser_dir(self) -> Optional[Path]:
        """Get current file browser directory."""
        return self._file_browser_dir

    def set_file_browser_dir(self, path: Optional[Path]) -> None:
        """Set current file browser directory."""
        self._file_browser_dir = path


    def refresh_file_browser(self) -> None:
        """Populate Select_file file browser table with dirs + allowed extensions only."""
        with profile_operation("file_browser_refresh"):
            if self.app.step != "Select_file":
                return
            try:
                table = self.app.query_one("#file_browser", DataTable)
            except Exception:
                return
            base = self._file_browser_dir
            if base is None:
                return

            # Clear rows without nuking columns (compat).
            TableManager.clear_rows(table)
            try:
                if not getattr(table, "columns", None):  # type: ignore[attr-defined]
                    table.add_columns("Name", "Type")
            except Exception:
                try:
                    table.add_columns("Name", "Type")
                except Exception:
                    pass

            # Parent entry
            has_parent_row = False
            try:
                parent = base.parent
                if parent != base:
                    table.add_row(Text("..", style="dim"), Text("dir", style="dim"), key="__up__")
                    has_parent_row = True
            except Exception:
                pass

            entries: list[Path] = []
            try:
                entries = list(base.iterdir())
            except Exception:
                entries = []

            dirs = sorted(
                [p for p in entries if p.is_dir() and not p.name.startswith(".")],
                key=lambda p: p.name.lower(),
            )
            files = sorted(
                [
                    p
                    for p in entries
                    if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in _VISIBLE_INPUT_EXTS
                ],
                key=lambda p: p.name.lower(),
            )

            for p in dirs:
                # Subtle distinction: folders get the muted accent; files keep base foreground.
                table.add_row(Text(p.name, style="bold #C48A4A"), Text("dir", style="dim"), key=f"dir:{p}")
            for p in files:
                ext = p.suffix.lower().lstrip(".")
                table.add_row(Text(p.name), Text(ext, style="dim"), key=f"file:{p}")

            # Default cursor: first real entry (not the parent '..' row).
            try:
                if getattr(table, "row_count", 0):
                    table.cursor_row = (1 if has_parent_row and getattr(table, "row_count", 0) > 1 else 0)  # type: ignore[attr-defined]
            except Exception:
                pass

    def file_browser_enter(self) -> None:
        """Handle Enter on Select_file file browser table."""
        with profile_operation("file_browser_enter"):
            if self.app.step != "Select_file":
                return
            base = self._file_browser_dir
            if base is None:
                return
            try:
                table = self.app.query_one("#file_browser", DataTable)
            except Exception:
                return
            rk = TableManager.cursor_row_key(table)
            if not rk:
                return
            if rk == "__up__":
                try:
                    self._file_browser_dir = base.parent if base.parent != base else base
                except Exception:
                    self._file_browser_dir = base
                self.refresh_file_browser()
                return
            if rk.startswith("dir:"):
                p = Path(rk[4:])
                self._file_browser_dir = p
                self.refresh_file_browser()
                return
            if rk.startswith("file:"):
                p = Path(rk[5:])
                suf = p.suffix.lower()
                if suf in _PARSEABLE_INPUT_EXTS and p.exists() and p.is_file():
                    self.app._set_input_path(p)
                    self.app._done_steps.add("Select_file")
                    self.app._goto("List_data")
                    return
                if suf in _VISIBLE_INPUT_EXTS:
                    from cairn.tui.edit_screens import InfoModal

                    self.app.push_screen(
                        InfoModal(
                            "This TUI currently supports CalTopo GeoJSON inputs only (.json/.geojson).\n\n"
                            "GPX/KML inputs are not supported in the TUI yet."
                        )
                    )
                return




__all__ = ["FileBrowserManager"]
