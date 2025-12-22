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
        self._save_browser_dir: Optional[Path] = None

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

    def get_save_browser_dir(self) -> Optional[Path]:
        """Get current save browser directory."""
        return self._save_browser_dir

    def set_save_browser_dir(self, path: Optional[Path]) -> None:
        """Set current save browser directory."""
        self._save_browser_dir = path

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

    def refresh_export_dir_table(self) -> None:
        """Populate export directory table (DataTable mode)."""
        try:
            table = self.app.query_one("#export_dir_table", DataTable)
        except Exception:
            return

        out_dir = self.app.model.output_dir or Path.cwd()

        TableManager.clear_rows(table)

        # Parent row
        try:
            parent = out_dir.parent
            if parent != out_dir:
                table.add_row(Text("..", style="dim"), Text("dir", style="dim"), key="__up__")
        except Exception:
            pass

        # Subdirectories
        try:
            entries = list(out_dir.iterdir())
            dirs = sorted([p for p in entries if p.is_dir() and not p.name.startswith(".")], key=lambda p: p.name.lower())
            for p in dirs:
                table.add_row(Text(p.name, style="bold #C48A4A"), Text("dir", style="dim"), key=f"dir:{p}")
        except Exception:
            pass

    def export_dir_table_enter(self) -> None:
        """Handle Enter on export directory table."""
        try:
            table = self.app.query_one("#export_dir_table", DataTable)
        except Exception:
            return

        rk = TableManager.cursor_row_key(table)
        if not rk:
            return

        out_dir = self.app.model.output_dir or Path.cwd()

        if rk == "__up__":
            self.app.model.output_dir = out_dir.parent if out_dir.parent != out_dir else out_dir
            self.refresh_export_dir_table()
            self.app._render_main()
        elif rk.startswith("dir:"):
            self.app.model.output_dir = Path(rk[4:])
            self.refresh_export_dir_table()
            self.app._render_main()

    def refresh_save_browser(self) -> None:
        """Populate Save output directory browser table (directories only)."""
        if self.app.step != "Save":
            return
        try:
            table = self.app.query_one("#save_browser", DataTable)
        except Exception:
            return

        base = self._save_browser_dir
        if base is None:
            return

        t0 = time.perf_counter()
        self.app._dbg(event="save.refresh.start", data={"base": str(base)})
        entries_count: int = 0
        dirs_count: int = 0
        entries_err: Optional[str] = None

        # Prevent selection events from triggering actions while we rebuild rows / set cursor.
        if hasattr(self.app, "_suppress_save_browser_select"):
            self.app._suppress_save_browser_select = True
        try:
            TableManager.clear_rows(table)
            try:
                if not getattr(table, "columns", None):  # type: ignore[attr-defined]
                    table.add_columns("Name", "Type")
            except Exception:
                try:
                    table.add_columns("Name", "Type")
                except Exception:
                    pass

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
            except Exception as e:
                entries = []
                entries_err = str(e)
            entries_count = int(len(entries))

            dirs = sorted(
                [p for p in entries if p.is_dir() and not p.name.startswith(".")],
                key=lambda p: p.name.lower(),
            )
            dirs_count = int(len(dirs))
            for p in dirs:
                table.add_row(Text(p.name, style="bold #C48A4A"), Text("dir", style="dim"), key=f"dir:{p}")

            # Action rows (kept at the bottom so the browser reads like a normal dir listing).
            table.add_row(Text("[Use this folder]", style="bold"), Text("select", style="dim"), key="__use__")
            table.add_row(Text("[Export]", style="bold"), Text("export", style="dim"), key="__export__")

            # Default cursor: first directory entry (not the parent '..' row).
            try:
                if getattr(table, "row_count", 0):
                    first_dir_row = (1 if has_parent_row else 0)
                    if len(dirs) > 0:
                        # Textual 6.x: cursor_row is a read-only property; use cursor_coordinate.
                        table.cursor_coordinate = Coordinate(first_dir_row, 0)  # type: ignore[attr-defined]
                    else:
                        # No sub-dirs; fall back to [Use this folder] (2nd-to-last row).
                        target = max(int(getattr(table, "row_count", 0) or 0) - 2, 0)
                        table.cursor_coordinate = Coordinate(target, 0)  # type: ignore[attr-defined]
            except Exception:
                pass
        finally:
            self.app._dbg(
                event="save.refresh.end",
                data={
                    "base": str(base),
                    "entries_count": entries_count,
                    "dirs_count": dirs_count,
                    "duration_ms": float((time.perf_counter() - t0) * 1000.0),
                    "error_if_any": entries_err,
                },
            )
            if hasattr(self.app, "_suppress_save_browser_select"):
                self.app._suppress_save_browser_select = False

    def save_browser_enter(self) -> None:
        """Handle Enter on Save output directory browser table."""
        if self.app.step != "Save":
            return
        base = self._save_browser_dir
        if base is None:
            return
        try:
            table = self.app.query_one("#save_browser", DataTable)
        except Exception:
            return
        rk = TableManager.cursor_row_key(table)
        if not rk:
            return

        next_dir: Optional[str] = None
        try:
            if rk == "__up__":
                try:
                    p = base.parent if base.parent != base else base
                except Exception:
                    p = base
                next_dir = str(p)
            elif rk.startswith("dir:"):
                next_dir = str(rk[4:])
        except Exception:
            next_dir = None
        self.app._dbg(
            event="save.enter",
            data={
                "base": str(base),
                "rk": str(rk),
                "next_dir": next_dir,
                "cursor_row": getattr(table, "cursor_row", None),
                "cursor_row_key": str(rk),
            },
        )

        if rk == "__up__":
            try:
                self._save_browser_dir = base.parent if base.parent != base else base
            except Exception:
                self._save_browser_dir = base
            try:
                # Update UI in-place (avoid re-mounting widgets / DuplicateIds).
                self.refresh_save_browser()
            except Exception:
                # Fallback: full re-render (best-effort).
                self.app._render_main()
            return
        if rk == "__use__":
            self.app.model.output_dir = base
            self.app._render_sidebar()
            return
        if rk == "__export__":
            # Export uses the global confirm modal (Enter to confirm, Esc to cancel).
            self.app.action_export()
            return
        if rk.startswith("dir:"):
            try:
                p = Path(rk[4:])
            except Exception:
                return
            self._save_browser_dir = p
            try:
                self.refresh_save_browser()
            except Exception:
                self.app._render_main()
            return


__all__ = ["FileBrowserManager"]
