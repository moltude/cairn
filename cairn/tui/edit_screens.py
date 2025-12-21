from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from textual.app import ComposeResult
from textual.coordinate import Coordinate
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Static
from rich.text import Text

from cairn.core.color_mapper import ColorMapper

# Import debug utilities
from cairn.tui.debug import agent_log as _agent_log

def validate_folder_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate folder name for security and filesystem compatibility.

    Returns:
        (is_valid, error_message) - error_message is None if valid
    """
    if not name or not name.strip():
        return False, "Folder name cannot be empty"

    # Check for leading/trailing spaces or dots BEFORE stripping (problematic on some filesystems)
    if name != name.strip() or name.strip().startswith('.') or name.strip().endswith('.'):
        return False, "Folder name cannot start/end with spaces or dots"

    name = name.strip()

    # Check for path traversal attempts
    if ".." in name:
        return False, "Folder name cannot contain '..'"

    # Check for path separators (both Unix and Windows)
    if "/" in name or "\\" in name:
        return False, "Folder name cannot contain path separators (/ or \\)"

    # Check for other problematic characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
    for char in invalid_chars:
        if char in name:
            return False, f"Folder name cannot contain '{char}'"

    # Check for names that are reserved on Windows
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                      'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                      'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
    if name.upper() in reserved_names:
        return False, f"'{name}' is a reserved name and cannot be used"

    return True, None


from textual.widgets import Button


class NewFolderModal(ModalScreen[Optional[str]]):
    """Modal dialog for creating a new folder with validation."""

    def compose(self) -> ComposeResult:
        with Vertical(id="new_folder_modal"):
            yield Static("Create New Folder", classes="title")
            yield Input(placeholder="Folder name", id="new_folder_input")
            with Horizontal():
                yield Button("Create", variant="primary", id="create_btn")
                yield Button("Cancel", id="cancel_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create_btn":
            inp = self.query_one("#new_folder_input", Input)
            self.dismiss(inp.value)
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:  # type: ignore[override]
        if event.key == "escape":
            self.dismiss(None)
        elif event.key in ("enter", "return"):
            inp = self.query_one("#new_folder_input", Input)
            if inp.value:
                self.dismiss(inp.value)


@dataclass(frozen=True)
class EditContext:
    kind: str  # "route" | "waypoint"
    selected_keys: tuple[str, ...]


def _table_cursor_row_key(table: DataTable) -> Optional[str]:
    """Best-effort current row key at cursor for Textual version-compat."""
    try:
        coord = getattr(table, "cursor_coordinate", None)
        if coord is not None and hasattr(table, "coordinate_to_cell_key"):
            cell_key = table.coordinate_to_cell_key(coord)
            rk = getattr(cell_key, "row_key", None)
            if rk is not None:
                return str(getattr(rk, "value", rk))
    except Exception:
        pass
    try:
        row_idx = getattr(table, "cursor_row", None)
        if row_idx is not None and hasattr(table, "get_row_key"):
            rk = table.get_row_key(row_idx)
            if rk is not None:
                return str(getattr(rk, "value", rk))
    except Exception:
        pass
    return None


def _datatable_clear_rows(table: DataTable) -> None:
    """Clear DataTable rows without relying on a single Textual version API."""
    try:
        table.clear()  # type: ignore[no-untyped-call]
        return
    except Exception:
        pass
    try:
        rows = getattr(table, "rows", None) or {}
        for rk in list(rows.keys()):
            try:
                table.remove_row(rk)  # type: ignore[no-untyped-call]
            except Exception:
                pass
    except Exception:
        pass


class InfoModal(ModalScreen[None]):
    """Simple info modal (Enter/Esc to dismiss)."""

    def __init__(self, message: str, *, title: str = "Info") -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="info_modal"):
            yield Static(self._title, classes="title")
            yield Static(self._message)
            yield Static("Enter/Esc: close", classes="muted")

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        if key == "escape" or key in ("enter", "return") or getattr(event, "character", None) == "\r":
            self.dismiss(None)
            try:
                event.stop()
            except Exception:
                pass
            return


class HelpModal(ModalScreen[None]):
    """Context-sensitive help modal showing keyboard shortcuts for the current step."""

    # Step-specific help content
    STEP_HELP = {
        "Select_file": [
            ("↑/↓", "Navigate file list"),
            ("Enter", "Open directory or select file"),
            ("Esc", "Go back"),
            ("q", "Quit application"),
        ],
        "List_data": [
            ("m", "Map unmapped symbols to OnX icons"),
            ("Enter", "Continue to folder selection"),
            ("Esc", "Go back to file selection"),
            ("q", "Quit application"),
        ],
        "Folder": [
            ("↑/↓", "Navigate folder list"),
            ("Enter", "Select folder and continue"),
            ("Esc", "Go back"),
            ("q", "Quit application"),
        ],
        "Routes": [
            ("↑/↓", "Navigate route list"),
            ("Space", "Toggle selection on current row"),
            ("Ctrl+A", "Select all routes"),
            ("/", "Focus search/filter input"),
            ("t", "Focus table (for Space selection)"),
            ("a", "Open actions menu for selected"),
            ("x", "Clear all selections"),
            ("Enter", "Continue to waypoints"),
            ("Esc", "Go back"),
            ("q", "Quit application"),
        ],
        "Waypoints": [
            ("↑/↓", "Navigate waypoint list"),
            ("Space", "Toggle selection on current row"),
            ("Ctrl+A", "Select all waypoints"),
            ("/", "Focus search/filter input"),
            ("t", "Focus table (for Space selection)"),
            ("a", "Open actions menu for selected"),
            ("x", "Clear all selections"),
            ("Enter", "Continue to preview"),
            ("Esc", "Go back"),
            ("q", "Quit application"),
        ],
        "Preview": [
            ("y", "Change directory/prefix"),
            ("Enter", "Export (with confirmation)"),
            ("r", "Apply rename edits (after export)"),
            ("Ctrl+N", "Start a new migration"),
            ("Esc", "Go back to make changes"),
            ("q", "Quit application"),
        ],
    }

    GLOBAL_HELP = [
        ("?", "Show this help"),
        ("Tab", "Move to next input/field"),
    ]

    def __init__(self, *, step: str) -> None:
        super().__init__()
        self._step = step

    def compose(self) -> ComposeResult:
        with Vertical(id="help_modal"):
            yield Static("Keyboard Shortcuts", classes="title")
            yield Static(f"Current step: {self._step}", classes="muted")
            yield Static("")

            # Step-specific shortcuts
            step_help = self.STEP_HELP.get(self._step, [])
            if step_help:
                yield Static("Step-specific:", classes="accent")
                for key, desc in step_help:
                    yield Static(f"  {key:12}  {desc}")
                yield Static("")

            # Global shortcuts
            yield Static("Global:", classes="accent")
            for key, desc in self.GLOBAL_HELP:
                yield Static(f"  {key:12}  {desc}")

            yield Static("")
            yield Static("Press Enter or Esc to close", classes="muted")

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        if key == "escape" or key in ("enter", "return", "question_mark") or getattr(event, "character", None) in ("\r", "?"):
            self.dismiss(None)
            try:
                event.stop()
            except Exception:
                pass
            return


class ConfirmModal(ModalScreen[bool]):
    """Confirmation dialog modal (returns True/False)."""

    def __init__(self, message: str, *, title: str = "Confirm") -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm_modal"):
            yield Static(self._title, classes="title")
            yield Static(self._message)
            yield Static("")
            yield Static("y/Enter: Yes    n/Esc: No", classes="muted")

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        char = getattr(event, "character", "") or ""
        if key == "escape" or char.lower() == "n":
            self.dismiss(False)
            try:
                event.stop()
            except Exception:
                pass
            return
        if key in ("enter", "return") or char == "\r" or char.lower() == "y":
            self.dismiss(True)
            try:
                event.stop()
            except Exception:
                pass
            return


class SaveTargetOverlay(Container):
    """
    Save target editor overlay (directory browser + filename prefix).

    Opened from the Save step via the inline \"Change? Y/n\" prompt.
    """

    class Done(Message):
        bubble = True

        def __init__(self, *, directory: Path, prefix: str, cancelled: bool = False) -> None:
            super().__init__()
            self.directory = directory
            self.prefix = prefix
            self.cancelled = cancelled

    class _DoneControl(Static):
        """Focusable Done control so it remains accessible even when the table scrolls."""

        can_focus = True

    def __init__(self, *, id: str = "save_target_overlay", classes: str = "", use_tree: bool = False) -> None:
        super().__init__(id=id, classes=classes)
        self._cur_dir: Path = Path.cwd()
        self._prefix: str = ""
        self._use_tree: bool = use_tree

    def compose(self) -> ComposeResult:
        _agent_log(
            hypothesisId="H_overlay_visibility",
            location="cairn/tui/edit_screens.py:SaveTargetOverlay.compose",
            message="compose",
            data={"id": getattr(self, "id", None), "classes": str(getattr(self, "classes", None))},
        )
        with Vertical(id="save_target_dialog", classes="overlay_dialog"):
            yield Static("", id="save_target_path", classes="muted")

            if self._use_tree:
                # Import FilteredDirectoryTree to show only directories (no files, no hidden)
                try:
                    from cairn.tui.widgets import FilteredDirectoryTree
                    yield FilteredDirectoryTree(str(Path.home()), id="save_target_browser_tree")
                except ImportError:
                    # Fallback to base DirectoryTree if import fails
                    from textual.widgets import DirectoryTree
                    yield DirectoryTree(str(Path.home()), id="save_target_browser_tree")
            else:
                tbl = DataTable(id="save_target_browser")
                tbl.add_columns("Name", "Type")
                yield tbl

            yield Static("File name prefix", classes="accent")
            yield Input(placeholder="Filename prefix", id="save_target_prefix")
            yield self._DoneControl("[Done]", id="save_target_done", classes="accent")

            if self._use_tree:
                yield Static("Enter: select  •  Ctrl+N: new folder  •  d/Tab→Enter: done  •  Esc: cancel", classes="muted")
            else:
                yield Static("Enter: open/select  •  d/Tab→Enter: done  •  Esc: cancel", classes="muted")

    def open(self, *, directory: Path, prefix: str) -> None:
        _agent_log(
            hypothesisId="H_overlay_visibility",
            location="cairn/tui/edit_screens.py:SaveTargetOverlay.open",
            message="open_called",
            data={"directory": str(directory), "prefix": str(prefix), "prior_classes": str(getattr(self, "classes", None))},
        )
        try:
            self._cur_dir = Path(directory).expanduser()
        except Exception:
            self._cur_dir = directory
        self._prefix = str(prefix or "")
        try:
            self.add_class("open")
        except Exception:
            pass

        # Refresh based on mode
        try:
            if self._use_tree:
                self._refresh_tree()
            else:
                self._refresh()
        except Exception:
            pass

        # Focus appropriate widget
        try:
            if self._use_tree:
                self.query_one("#save_target_browser_tree").focus()
            else:
                self.query_one("#save_target_browser", DataTable).focus()
        except Exception:
            pass

        # Best-effort debug hook
        try:
            getattr(self.app, "_dbg")(event="save.change.open", data={"dir": str(self._cur_dir), "prefix": self._prefix})
        except Exception:
            pass

    def close(self) -> None:
        _agent_log(
            hypothesisId="H_overlay_visibility",
            location="cairn/tui/edit_screens.py:SaveTargetOverlay.close",
            message="close_called",
            data={"classes": str(getattr(self, "classes", None))},
        )
        try:
            self.remove_class("open")
        except Exception:
            pass

    def _refresh(self) -> None:
        try:
            self.query_one("#save_target_path", Static).update(f"Directory: {self._cur_dir}")
        except Exception:
            pass
        try:
            inp = self.query_one("#save_target_prefix", Input)
            inp.value = self._prefix
        except Exception:
            pass
        try:
            tbl = self.query_one("#save_target_browser", DataTable)
        except Exception:
            return

        _datatable_clear_rows(tbl)
        # Parent row
        has_parent_row = False
        try:
            parent = self._cur_dir.parent
            if parent != self._cur_dir:
                tbl.add_row(Text("..", style="dim"), Text("dir", style="dim"), key="__up__")
                has_parent_row = True
        except Exception:
            has_parent_row = False

        entries: list[Path] = []
        try:
            entries = list(self._cur_dir.iterdir())
        except Exception:
            entries = []
        dirs = sorted([p for p in entries if p.is_dir() and not p.name.startswith(".")], key=lambda p: p.name.lower())
        for p in dirs:
            tbl.add_row(Text(p.name, style="bold #C48A4A"), Text("dir", style="dim"), key=f"dir:{p}")

        # Default cursor: first directory (or parent if no dirs)
        first_dir_row = 1 if has_parent_row else 0
        try:
            if len(dirs) > 0:
                tbl.cursor_coordinate = Coordinate(first_dir_row, 0)  # type: ignore[attr-defined]
            elif has_parent_row and int(getattr(tbl, "row_count", 0) or 0) > 0:
                tbl.cursor_coordinate = Coordinate(0, 0)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _refresh_tree(self) -> None:
        """Refresh tree browser display."""
        try:
            self.query_one("#save_target_path", Static).update(f"Directory: {self._cur_dir}")
        except Exception:
            pass

        try:
            inp = self.query_one("#save_target_prefix", Input)
            inp.value = self._prefix
        except Exception:
            pass

        # Reload tree at current directory
        self._reload_tree()

    def _apply_done(self) -> None:
        try:
            self._prefix = str(self.query_one("#save_target_prefix", Input).value or "")
        except Exception:
            pass
        self.post_message(self.Done(directory=self._cur_dir, prefix=self._prefix, cancelled=False))
        self.close()

    def activate(self) -> None:
        """Deterministic activation used by tests (same as Enter on the browser)."""
        try:
            tbl = self.query_one("#save_target_browser", DataTable)
        except Exception:
            return
        # Preserve any typed prefix while navigating the directory browser.
        try:
            self._prefix = str(self.query_one("#save_target_prefix", Input).value or "")
        except Exception:
            pass
        rk = _table_cursor_row_key(tbl)
        if not rk:
            return
        if rk == "__up__":
            try:
                self._cur_dir = self._cur_dir.parent if self._cur_dir.parent != self._cur_dir else self._cur_dir
            except Exception:
                pass
            try:
                getattr(self.app, "_dbg")(event="save.change.navigate", data={"rk": "__up__", "dir": str(self._cur_dir)})
            except Exception:
                pass
            self._refresh()
            return
        if rk.startswith("dir:"):
            try:
                self._cur_dir = Path(rk[4:])
            except Exception:
                return
            try:
                getattr(self.app, "_dbg")(event="save.change.navigate", data={"rk": rk, "dir": str(self._cur_dir)})
            except Exception:
                pass
            self._refresh()
            return

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        ch = str(getattr(event, "character", "") or "")

        # Handle Ctrl+N for creating new folder (tree mode only)
        if self._use_tree and key == "ctrl+n":
            self._create_new_folder()
            try:
                event.stop()
            except Exception:
                pass
            return

        if key == "escape":
            try:
                getattr(self.app, "_dbg")(event="save.change.cancel", data={"dir": str(self._cur_dir)})
            except Exception:
                pass
            self.post_message(self.Done(directory=self._cur_dir, prefix=self._prefix, cancelled=True))
            self.close()
            try:
                event.stop()
            except Exception:
                pass
            return
        if ch.lower() == "d":
            self._apply_done()
            try:
                event.stop()
            except Exception:
                pass
            return
        if key in ("enter", "return") or ch == "\r":
            focused_id = None
            try:
                focused_id = getattr(getattr(self.app, "focused", None), "id", None)
            except Exception:
                focused_id = None
            if focused_id == "save_target_done":
                self._apply_done()
            else:
                self.activate()
            try:
                event.stop()
            except Exception:
                pass
            return

    def _create_new_folder(self) -> None:
        """Prompt user to create a new folder in the current directory."""
        def handle_folder_name(folder_name: Optional[str]) -> None:
            if not folder_name:
                return

            # Validate folder name for security
            is_valid, error_msg = validate_folder_name(folder_name)
            if not is_valid:
                self.app.push_screen(InfoModal(f"Invalid folder name: {error_msg}"))
                return

            folder_name = folder_name.strip()
            new_path = self._cur_dir / folder_name

            try:
                new_path.mkdir(parents=False, exist_ok=False)
                # Success - reload tree to show new folder
                self._reload_tree(new_path)
            except FileExistsError:
                self.app.push_screen(InfoModal(f"Folder '{folder_name}' already exists."))
            except PermissionError:
                self.app.push_screen(InfoModal(f"Permission denied: cannot create folder in {self._cur_dir}"))
            except OSError as e:
                # Catch filesystem-specific errors (invalid names, etc.)
                self.app.push_screen(InfoModal(f"Cannot create folder: {e}"))
            except Exception as e:
                # Unexpected errors - log details but show generic message
                import logging
                logging.error(f"Unexpected error creating folder '{folder_name}': {e}")
                self.app.push_screen(InfoModal("An unexpected error occurred while creating the folder."))

        self.app.push_screen(NewFolderModal(), handle_folder_name)

    def _reload_tree(self, select_path: Optional[Path] = None) -> None:
        """Reload the directory tree and optionally select a specific path."""
        if not self._use_tree:
            return

        try:
            # Import FilteredDirectoryTree to show only directories
            try:
                from cairn.tui.widgets import FilteredDirectoryTree
                TreeClass = FilteredDirectoryTree
            except ImportError:
                from textual.widgets import DirectoryTree
                TreeClass = DirectoryTree

            tree = self.query_one("#save_target_browser_tree")
            # DirectoryTree doesn't have a built-in reload, so we need to:
            # 1. Remove the old tree
            tree.remove()

            # 2. Create a new tree at the current directory
            new_tree = TreeClass(str(self._cur_dir), id="save_target_browser_tree")

            # 3. Mount it in the right place
            dialog = self.query_one("#save_target_dialog")
            path_label = self.query_one("#save_target_path")
            dialog.mount(new_tree, after=path_label)

            # 4. Focus the tree
            new_tree.focus()
        except Exception:
            pass

    def on_directory_tree_directory_selected(self, event) -> None:  # type: ignore[override]
        """Handle directory selection from tree browser."""
        if not self._use_tree:
            return

        # Update current directory
        try:
            self._cur_dir = Path(event.path)
        except Exception:
            return

        # Update display
        try:
            self.query_one("#save_target_path", Static).update(f"Directory: {self._cur_dir}")
        except Exception:
            pass

        # Preserve prefix
        try:
            self._prefix = str(self.query_one("#save_target_prefix", Input).value or "")
        except Exception:
            pass


class InlineEditOverlay(Container):
    """
    Inline editor overlay that renders inside the current screen (not a ModalScreen).

    This is the "true popup" behavior: the underlying step UI remains visible because
    we aren't switching Screens.
    """

    class FieldChosen(Message):
        bubble = True
        def __init__(self, field_key: Optional[str]) -> None:
            super().__init__()
            self.field_key = field_key

    def __init__(
        self,
        *,
        id: str = "inline_edit_overlay",
        classes: str = "",
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._ctx: Optional[EditContext] = None
        self._features: list = []
        self._get_color_chip = None
        self._get_waypoint_icon = None
        self._get_waypoint_color = None
        self._get_route_color = None

    def compose(self) -> ComposeResult:
        with Container(id="inline_edit_dialog"):
            yield Static("Edit Record", id="inline_edit_title", classes="title")
            yield Static("", id="inline_edit_subtitle", classes="muted")
            yield Static("")

            tbl = DataTable(id="fields_table")
            tbl.add_columns("Field", "Value")
            yield tbl
            yield Static("↑/↓: navigate  Enter: edit  Esc: close", classes="muted")

    def open(
        self,
        *,
        ctx: EditContext,
        features: list,
        get_color_chip=None,
        get_waypoint_icon=None,
        get_waypoint_color=None,
        get_route_color=None,
    ) -> None:
        self._ctx = ctx
        self._features = list(features or [])
        self._get_color_chip = get_color_chip
        self._get_waypoint_icon = get_waypoint_icon
        self._get_waypoint_color = get_waypoint_color
        self._get_route_color = get_route_color
        self.add_class("open")
        self._refresh()
        try:
            tbl = self.query_one("#fields_table", DataTable)
            tbl.focus()
            # Reset cursor to the first row (Name) whenever the overlay opens.
            # This avoids surprising navigation where the cursor is left on "Color"/"Done"
            # after returning from a sub-editor.
            for _ in range(10):
                try:
                    tbl.action_cursor_up()  # type: ignore[attr-defined]
                except Exception:
                    break
        except Exception:
            pass

    def close(self) -> None:
        self.remove_class("open")

    def _send(self, message: Message) -> None:
        """Send a message to the App (preferred) so it always gets handled."""
        try:
            app = getattr(self, "app", None)
            if app is not None:
                app.post_message(message)
                return
        except Exception:
            pass
        try:
            self.post_message(message)
        except Exception:
            pass

    def _refresh(self) -> None:
        # Subtitle
        try:
            subtitle = self.query_one("#inline_edit_subtitle", Static)
            if self._ctx is None:
                subtitle.update("")
            elif len(self._features) > 1:
                subtitle.update(f"Editing {len(self._features)} {self._ctx.kind}(s)")
            else:
                subtitle.update("")
        except Exception:
            pass

        # Table rows
        try:
            tbl = self.query_one("#fields_table", DataTable)
        except Exception:
            return
        _datatable_clear_rows(tbl)
        try:
            # Name
            tbl.add_row("Name", self._get_name_summary(), key="name")
            # Description
            tbl.add_row("Description", self._get_description_summary(), key="description")
            # Icon (waypoints)
            if self._ctx is not None and self._ctx.kind == "waypoint":
                tbl.add_row("Icon", self._get_icon_summary(), key="icon")
            # Color
            tbl.add_row("Color", self._get_color_summary(), key="color")
            # Done
            tbl.add_row("Done", "", key="done")
        except Exception:
            pass

    def _get_name_summary(self) -> str:
        if len(self._features) == 1:
            return str(getattr(self._features[0], "title", "") or "Untitled")
        names = {str(getattr(f, "title", "") or "Untitled") for f in self._features}
        return list(names)[0] if len(names) == 1 else "[varies]"

    def _get_description_summary(self) -> str:
        def _snip(s: str) -> str:
            if len(s) > 50:
                return s[:47] + "..."
            return s

        if len(self._features) == 1:
            return _snip(str(getattr(self._features[0], "description", "") or "(none)"))
        descs = {str(getattr(f, "description", "") or "(none)") for f in self._features}
        return _snip(list(descs)[0]) if len(descs) == 1 else "[varies]"

    def _get_icon_summary(self) -> str:
        if not self._get_waypoint_icon:
            return "(unknown)"
        if len(self._features) == 1:
            return str(self._get_waypoint_icon(self._features[0]))
        icons = {str(self._get_waypoint_icon(f)) for f in self._features}
        return list(icons)[0] if len(icons) == 1 else "[varies]"

    def _get_color_summary(self):
        if self._ctx is None:
            return "(unknown)"
        if self._ctx.kind == "waypoint":
            if not self._get_waypoint_color or not self._get_color_chip:
                return "(unknown)"
            if len(self._features) == 1:
                wp = self._features[0]
                icon = self._get_waypoint_icon(wp) if self._get_waypoint_icon else "Location"
                rgba = self._get_waypoint_color(wp, icon)
                return self._get_color_chip(rgba)
            colors = []
            for f in self._features:
                icon = self._get_waypoint_icon(f) if self._get_waypoint_icon else "Location"
                colors.append(self._get_waypoint_color(f, icon))
            return self._get_color_chip(colors[0]) if len(set(colors)) == 1 else "[varies]"

        # route
        if not self._get_route_color or not self._get_color_chip:
            return "(unknown)"
        if len(self._features) == 1:
            rgba = self._get_route_color(self._features[0])
            return self._get_color_chip(rgba)
        colors = [self._get_route_color(f) for f in self._features]
        return self._get_color_chip(colors[0]) if len(set(colors)) == 1 else "[varies]"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "fields_table":
            return
        try:
            field_key = str(event.row_key.value)
        except Exception:
            field_key = "done"
        if field_key == "done":
            self.close()
            self._send(self.FieldChosen(None))
        else:
            # Close overlay while we open a field editor.
            self.close()
            self._send(self.FieldChosen(field_key))

    def on_key(self, event) -> None:  # type: ignore[override]
        if not self.has_class("open"):
            return
        key = str(getattr(event, "key", "") or "")
        if key == "escape":
            self.close()
            self._send(self.FieldChosen(None))
            try:
                event.stop()
            except Exception:
                pass
            return
        if key in ("enter", "return") or getattr(event, "character", None) == "\r":
            try:
                tbl = self.query_one("#fields_table", DataTable)
            except Exception:
                return
            field_key = (_table_cursor_row_key(tbl) or "done").strip() or "done"
            if field_key == "done":
                self.close()
                self._send(self.FieldChosen(None))
            else:
                self.close()
                self._send(self.FieldChosen(field_key))
            try:
                event.stop()
            except Exception:
                pass
            return


class ColorPickerOverlay(Container):
    """In-screen overlay for choosing a color from a palette (no Screen navigation)."""

    class ColorPicked(Message):
        bubble = True
        def __init__(self, rgba: Optional[str]) -> None:
            super().__init__()
            self.rgba = rgba

    def __init__(self, *, id: str = "color_picker_overlay", classes: str = "") -> None:
        super().__init__(id=id, classes=classes)
        self._title: str = "Select color"
        self._palette: list[tuple[str, str]] = []
        self._filter: str = ""
        self._selected_rgba: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Container(id="color_picker_dialog"):
            yield Static("", id="color_picker_title", classes="title")
            yield Input(placeholder="Filter colors…", id="color_search")
            tbl = DataTable(id="palette_table")
            tbl.add_columns("Color")
            yield tbl
            yield Static("Enter: apply  Esc: cancel  /: filter", classes="muted")

    def open(self, *, title: str, palette: list[tuple[str, str]]) -> None:
        self._title = str(title or "Select color")
        self._palette = [(str(rgba), str(name)) for rgba, name in (palette or [])]
        self._filter = ""
        self._selected_rgba = None
        self.add_class("open")
        self._refresh()
        # Default focus on table for arrow navigation.
        try:
            self.query_one("#palette_table", DataTable).focus()
        except Exception:
            pass

    def close(self) -> None:
        self.remove_class("open")

    def _send(self, message: Message) -> None:
        try:
            app = getattr(self, "app", None)
            if app is not None:
                app.post_message(message)
                return
        except Exception:
            pass
        try:
            self.post_message(message)
        except Exception:
            pass

    def _chip(self, rgba: str, name: str) -> Text:
        r, g, b = ColorMapper.parse_color(str(rgba))
        nm = (name or "").replace("-", " ").upper()
        chip = Text("■ ", style=f"rgb({r},{g},{b})")
        chip.append(nm, style="bold")
        return chip

    def _refresh(self) -> None:
        try:
            self.query_one("#color_picker_title", Static).update(self._title)
        except Exception:
            pass
        try:
            tbl = self.query_one("#palette_table", DataTable)
        except Exception:
            return
        _datatable_clear_rows(tbl)
        q = (self._filter or "").strip().lower()
        for rgba, name in self._palette:
            if q and q not in (name or "").lower():
                continue
            tbl.add_row(self._chip(rgba, name), key=str(rgba))
        # Ensure a predictable cursor row.
        try:
            if getattr(tbl, "row_count", 0):
                tbl.cursor_row = 0  # type: ignore[attr-defined]
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "color_search":
            return
        self._filter = event.value or ""
        self._refresh()

    def on_key(self, event) -> None:  # type: ignore[override]
        if not self.has_class("open"):
            return
        key = str(getattr(event, "key", "") or "")
        if key in ("/", "slash"):
            try:
                self.query_one("#color_search", Input).focus()
            except Exception:
                pass
            try:
                event.stop()
            except Exception:
                pass
            return
        if key == "escape":
            self.close()
            self._send(self.ColorPicked(None))
            try:
                event.stop()
            except Exception:
                pass
            return
        if key in ("enter", "return") or getattr(event, "character", None) == "\r":
            rgba = (self._selected_rgba or "").strip()
            if not rgba:
                try:
                    tbl = self.query_one("#palette_table", DataTable)
                    rgba = (_table_cursor_row_key(tbl) or "").strip()
                except Exception:
                    rgba = ""
            if not rgba:
                return
            self.close()
            self._send(self.ColorPicked(rgba))
            try:
                event.stop()
            except Exception:
                pass
            return

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "palette_table":
            return
        if not self.has_class("open"):
            return
        try:
            rgba = str(event.row_key.value)
        except Exception:
            rgba = ""
        self._selected_rgba = rgba or None
        # Treat row selection as "apply" (Enter/click) so this works even if the
        # DataTable consumes Enter and the overlay doesn't receive the Key event.
        if rgba:
            self.close()
            self._send(self.ColorPicked(rgba))
            try:
                event.stop()
            except Exception:
                pass


class IconPickerOverlay(Container):
    """In-screen overlay for choosing an OnX icon (no Screen navigation)."""

    class IconPicked(Message):
        bubble = True
        def __init__(self, icon: Optional[str]) -> None:
            super().__init__()
            self.icon = icon

    def __init__(self, *, id: str = "icon_picker_overlay", classes: str = "") -> None:
        super().__init__(id=id, classes=classes)
        self._icons: list[str] = []
        self._filter: str = ""
        self._selected_icon: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Container(id="icon_picker_dialog"):
            yield Static("OnX icon override", classes="title")
            yield Static("Type to filter, ↑/↓ to navigate", classes="muted")
            yield Input(placeholder="Filter icons…", id="icon_search")
            tbl = DataTable(id="icon_table")
            tbl.add_columns("Icon")
            yield tbl
            yield Static("Enter: apply  Esc: cancel  /: filter", classes="muted")

    def open(self, *, icons: list[str]) -> None:
        self._icons = [str(x) for x in (icons or [])]
        self._filter = ""
        self._selected_icon = None
        self.add_class("open")
        self._refresh()
        # Default focus on table for arrow navigation.
        try:
            self.query_one("#icon_table", DataTable).focus()
        except Exception:
            pass

    def close(self) -> None:
        self.remove_class("open")

    def _send(self, message: Message) -> None:
        try:
            app = getattr(self, "app", None)
            if app is not None:
                app.post_message(message)
                return
        except Exception:
            pass
        try:
            self.post_message(message)
        except Exception:
            pass

    def _refresh(self) -> None:
        try:
            tbl = self.query_one("#icon_table", DataTable)
        except Exception:
            return
        _datatable_clear_rows(tbl)
        q = (self._filter or "").strip().lower()
        for icon in self._icons:
            if q and q not in icon.lower():
                continue
            tbl.add_row(icon, key=icon)
        try:
            if getattr(tbl, "row_count", 0):
                tbl.cursor_row = 0  # type: ignore[attr-defined]
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "icon_search":
            return
        self._filter = event.value or ""
        self._refresh()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "icon_table":
            return
        if not self.has_class("open"):
            return
        try:
            icon = str(event.row_key.value)
        except Exception:
            icon = ""
        self._selected_icon = icon or None
        if icon:
            self.close()
            self._send(self.IconPicked(icon))
            try:
                event.stop()
            except Exception:
                pass

    def on_key(self, event) -> None:  # type: ignore[override]
        if not self.has_class("open"):
            return


class RenameOverlay(Container):
    """In-screen overlay for renaming selected records (no Screen navigation)."""

    class Submitted(Message):
        bubble = True

        def __init__(self, ctx: EditContext, value: Optional[str]) -> None:
            super().__init__()
            self.ctx = ctx
            self.value = value

    def __init__(self, *, id: str = "rename_overlay", classes: str = "") -> None:
        super().__init__(id=id, classes=classes)
        self._ctx: Optional[EditContext] = None
        self._title: str = "Rename"
        self._placeholder: str = "New title (applies to selected)"

    def compose(self) -> ComposeResult:
        with Container(id="rename_dialog"):
            yield Static(self._title, classes="title")
            yield Static("", id="rename_subtitle", classes="muted")
            yield Input(placeholder=self._placeholder, id="rename_value")
            yield Static("Enter: apply  Esc: cancel", classes="muted")

    def open(self, *, ctx: EditContext, title: str = "Rename") -> None:
        self._ctx = ctx
        self._title = title
        try:
            self.query_one("#rename_subtitle", Static).update(
                f"Selected: {len(ctx.selected_keys)} {ctx.kind}(s)"
            )
        except Exception:
            pass
        self.add_class("open")
        try:
            inp = self.query_one("#rename_value", Input)
            inp.value = ""
            inp.focus()
        except Exception:
            pass

    def close(self) -> None:
        self.remove_class("open")

    def _send(self, message: Message) -> None:
        """Send a message to the App (preferred) so it always gets handled."""
        try:
            app = getattr(self, "app", None)
            if app is not None:
                app.post_message(message)
                return
        except Exception:
            pass
        try:
            self.post_message(message)
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "rename_value":
            return
        if self._ctx is None:
            return
        raw = (event.value or "").strip()
        self.close()
        self._send(self.Submitted(self._ctx, raw or None))
        try:
            event.stop()
        except Exception:
            pass

    def on_key(self, event) -> None:  # type: ignore[override]
        if not self.has_class("open"):
            return
        key = str(getattr(event, "key", "") or "")
        if key == "escape":
            if self._ctx is None:
                self.close()
                return
            self.close()
            self._send(self.Submitted(self._ctx, None))
            try:
                event.stop()
            except Exception:
                pass


class DescriptionOverlay(Container):
    """In-screen overlay for setting description (no Screen navigation)."""

    class Submitted(Message):
        bubble = True

        def __init__(self, ctx: EditContext, value: Optional[str]) -> None:
            super().__init__()
            self.ctx = ctx
            self.value = value

    def __init__(self, *, id: str = "description_overlay", classes: str = "") -> None:
        super().__init__(id=id, classes=classes)
        self._ctx: Optional[EditContext] = None

    def compose(self) -> ComposeResult:
        with Container(id="description_dialog"):
            yield Static("Set description", classes="title")
            yield Static("", id="description_subtitle", classes="muted")
            yield Input(placeholder="New description (applies to selected)", id="description_value")
            yield Static("Enter: apply  Esc: cancel  (use \\n for new lines)", classes="muted")

    def open(self, *, ctx: EditContext) -> None:
        self._ctx = ctx
        try:
            self.query_one("#description_subtitle", Static).update(
                f"Selected: {len(ctx.selected_keys)} {ctx.kind}(s)"
            )
        except Exception:
            pass
        self.add_class("open")
        try:
            inp = self.query_one("#description_value", Input)
            inp.value = ""
            inp.focus()
        except Exception:
            pass

    def close(self) -> None:
        self.remove_class("open")

    def _send(self, message: Message) -> None:
        try:
            app = getattr(self, "app", None)
            if app is not None:
                app.post_message(message)
                return
        except Exception:
            pass
        try:
            self.post_message(message)
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "description_value":
            return
        if self._ctx is None:
            return
        raw = (event.value or "").strip()
        self.close()
        self._send(self.Submitted(self._ctx, raw or None))
        try:
            event.stop()
        except Exception:
            pass

    def on_key(self, event) -> None:  # type: ignore[override]
        if not self.has_class("open"):
            return
        key = str(getattr(event, "key", "") or "")
        if key == "escape":
            if self._ctx is None:
                self.close()
                return
            self.close()
            self._send(self.Submitted(self._ctx, None))
            try:
                event.stop()
            except Exception:
                pass


class ConfirmOverlay(Container):
    """In-screen overlay confirmation (no Screen navigation)."""
    can_focus = True

    class Result(Message):
        bubble = True

        def __init__(self, confirmed: bool) -> None:
            super().__init__()
            self.confirmed = bool(confirmed)

    def __init__(self, *, id: str = "confirm_overlay", classes: str = "") -> None:
        super().__init__(id=id, classes=classes)
        self._title: str = "Confirm"
        self._message: str = ""

    def compose(self) -> ComposeResult:
        with Container(id="confirm_dialog"):
            yield Static("", id="confirm_title", classes="title")
            yield Static("", id="confirm_message")
            yield Static("")
            yield Static("y/Enter: Yes    n/Esc: No", classes="muted")

    def open(self, *, title: str, message: str) -> None:
        self._title = str(title or "Confirm")
        self._message = str(message or "")
        try:
            self.query_one("#confirm_title", Static).update(self._title)
            self.query_one("#confirm_message", Static).update(self._message)
        except Exception:
            pass
        self.add_class("open")
        try:
            # Focus this container so it receives key events.
            self.focus()
        except Exception:
            pass

    def close(self) -> None:
        self.remove_class("open")

    def _send(self, message: Message) -> None:
        try:
            app = getattr(self, "app", None)
            if app is not None:
                app.post_message(message)
                return
        except Exception:
            pass
        try:
            self.post_message(message)
        except Exception:
            pass

    def on_key(self, event) -> None:  # type: ignore[override]
        if not self.has_class("open"):
            return
        key = str(getattr(event, "key", "") or "")
        char = getattr(event, "character", "") or ""
        if key == "escape" or char.lower() == "n":
            self.close()
            self._send(self.Result(False))
            try:
                event.stop()
            except Exception:
                pass
            return
        if key in ("enter", "return") or char == "\r" or char.lower() == "y":
            self.close()
            self._send(self.Result(True))
            try:
                event.stop()
            except Exception:
                pass
            return
        key = str(getattr(event, "key", "") or "")
        if key in ("/", "slash"):
            try:
                self.query_one("#icon_search", Input).focus()
            except Exception:
                pass
            try:
                event.stop()
            except Exception:
                pass
            return
        if key == "escape":
            self.close()
            self._send(self.IconPicked(None))
            try:
                event.stop()
            except Exception:
                pass
            return
        if key in ("enter", "return") or getattr(event, "character", None) == "\r":
            icon = (self._selected_icon or "").strip()
            if not icon:
                try:
                    tbl = self.query_one("#icon_table", DataTable)
                    icon = (_table_cursor_row_key(tbl) or "").strip()
                except Exception:
                    icon = ""
            if not icon:
                return
            self.close()
            self._send(self.IconPicked(icon))
            try:
                event.stop()
            except Exception:
                pass
            return

class RenameModal(ModalScreen[None]):
    def __init__(
        self,
        *,
        ctx: EditContext,
        title: str = "Rename",
        placeholder: str = "New title (applies to selected)",
    ) -> None:
        super().__init__()
        self._ctx = ctx
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="rename_modal"):
            yield Static(self._title, classes="title")
            yield Static(
                f"Selected: {len(self._ctx.selected_keys)} {self._ctx.kind}(s)",
                classes="muted",
            )
            yield Input(placeholder=self._placeholder, id="new_title")
            yield Static("Enter: apply  Esc: cancel", classes="muted")

    def on_mount(self) -> None:
        try:
            self.query_one("#new_title", Input).focus()
        except Exception:
            pass

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        if key == "escape":
            self.dismiss(None)
            try:
                event.stop()
            except Exception:
                pass
            return

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "new_title":
            return
        raw = (event.value or "").strip()
        if not raw:
            self.dismiss(None)
            return
        self.dismiss({"action": "rename", "value": raw, "ctx": self._ctx})


class DescriptionModal(ModalScreen[None]):
    def __init__(
        self,
        *,
        ctx: EditContext,
        title: str = "Set description",
        placeholder: str = r"Description (use \n for newlines)",
    ) -> None:
        super().__init__()
        self._ctx = ctx
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="description_modal"):
            yield Static(self._title, classes="title")
            yield Static(
                f"Selected: {len(self._ctx.selected_keys)} {self._ctx.kind}(s)",
                classes="muted",
            )
            yield Input(placeholder=self._placeholder, id="new_description")
            yield Static("Enter: apply  Esc: cancel", classes="muted")

    def on_mount(self) -> None:
        try:
            self.query_one("#new_description", Input).focus()
        except Exception:
            pass

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        if key == "escape":
            self.dismiss(None)
            try:
                event.stop()
            except Exception:
                pass
            return

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "new_description":
            return
        raw = (event.value or "").strip()
        if not raw:
            self.dismiss(None)
            return
        self.dismiss({"action": "description", "value": raw, "ctx": self._ctx})


class ColorPickerModal(ModalScreen[None]):
    def __init__(
        self,
        *,
        ctx: EditContext,
        title: str,
        palette: Sequence[tuple[str, str]],
    ) -> None:
        """
        palette: [(rgba, name), ...]
        """
        super().__init__()
        self._ctx = ctx
        self._title = title
        self._palette = list(palette)
        self._filter: str = ""
        self._selected_rgba: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="color_modal"):
            yield Static(self._title, classes="title")
            yield Input(placeholder="Filter colors…", id="color_search")
            tbl = DataTable(id="palette_table")
            tbl.add_columns("Color")
            yield tbl
            yield Static("Enter: apply  Esc: cancel  /: filter", classes="muted")

    def on_mount(self) -> None:
        self._refresh_table()
        try:
            self.query_one("#palette_table", DataTable).focus()
        except Exception:
            pass

    def _chip(self, rgba: str, name: str) -> Text:
        r, g, b = ColorMapper.parse_color(str(rgba))
        nm = (name or "").replace("-", " ").upper()
        chip = Text("■ ", style=f"rgb({r},{g},{b})")
        chip.append(nm, style="bold")
        return chip

    def _refresh_table(self) -> None:
        try:
            tbl = self.query_one("#palette_table", DataTable)
        except Exception:
            return
        # Clear rows (Textual version differences)
        try:
            tbl.clear(columns=False)  # type: ignore[call-arg]
        except Exception:
            try:
                tbl.clear()  # type: ignore[call-arg]
            except Exception:
                pass
        q = (self._filter or "").strip().lower()
        for rgba, name in self._palette:
            if q and q not in (name or "").lower():
                continue
            tbl.add_row(self._chip(str(rgba), str(name)), key=str(rgba))
        # Keep selection stable when filtering.
        if self._selected_rgba:
            try:
                # If still present, keep it; otherwise clear.
                _ = tbl.get_row(self._selected_rgba)  # type: ignore[misc]
            except Exception:
                self._selected_rgba = None

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "color_search":
            return
        self._filter = event.value or ""
        self._refresh_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "palette_table":
            return
        try:
            rgba = str(event.row_key.value)
        except Exception:
            rgba = ""
        if not rgba:
            return
        # Select; user can Apply or hit Enter.
        self._selected_rgba = rgba

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        if key in ("/", "slash"):
            try:
                self.query_one("#color_search", Input).focus()
            except Exception:
                pass
            try:
                event.stop()
            except Exception:
                pass
            return
        if key == "escape":
            self.dismiss(None)
            try:
                event.stop()
            except Exception:
                pass
            return
        if key in ("enter", "return") or getattr(event, "character", None) == "\r":
            rgba = (self._selected_rgba or "").strip()
            if not rgba:
                try:
                    tbl = self.query_one("#palette_table", DataTable)
                    rgba = (_table_cursor_row_key(tbl) or "").strip()
                except Exception:
                    rgba = ""
            if not rgba:
                return
            self.dismiss({"action": "color", "value": rgba, "ctx": self._ctx})
            try:
                event.stop()
            except Exception:
                pass
            return


class _IconSearchInput(Input):
    """
    Icon filter input that supports arrow navigation without requiring focus changes.

    Textual's Input consumes Up/Down when focused; this widget instead uses those keys
    to move the icon list selection while still allowing normal typing.
    """

    def _get_icon_table(self) -> Optional[DataTable]:
        """Get the icon table from the parent screen."""
        screen = getattr(self, "screen", None)
        if screen is None:
            return None
        try:
            return screen.query_one("#icon_table", DataTable)  # type: ignore[no-any-return]
        except Exception:
            return None

    def _move_table_cursor(self, delta: int) -> None:
        """Move the icon table cursor by delta rows."""
        tbl = self._get_icon_table()
        if tbl is None:
            return
        try:
            row_count = int(getattr(tbl, "row_count", 0) or 0)
        except Exception:
            row_count = 0
        if row_count <= 0:
            return

        # Use action methods if available (preferred), otherwise try move_cursor
        if delta > 0:
            for _ in range(abs(delta)):
                try:
                    tbl.action_cursor_down()
                except Exception:
                    break
        elif delta < 0:
            for _ in range(abs(delta)):
                try:
                    tbl.action_cursor_up()
                except Exception:
                    break

    async def _on_key(self, event) -> None:
        """Override _on_key to intercept arrow keys before Input handles them."""
        key = str(getattr(event, "key", "") or "")

        # Handle up/down arrows for table navigation
        if key in ("up", "down"):
            delta = -1 if key == "up" else 1
            self._move_table_cursor(delta)
            event.stop()
            event.prevent_default()
            return

        screen = getattr(self, "screen", None)

        # Escape closes the modal
        if key == "escape" and screen is not None:
            try:
                screen.dismiss(None)
            except Exception:
                pass
            event.stop()
            event.prevent_default()
            return

        # Enter applies the current selection - but DON'T block Input's submit action
        # Let the modal handle enter via its own on_key handler
        if key in ("enter", "return"):
            # Don't call super() for enter - let it bubble to modal
            event.stop()
            if screen is not None:
                ctx = getattr(screen, "_ctx", None)
                tbl = self._get_icon_table()
                if isinstance(ctx, EditContext) and tbl is not None:
                    icon = (_table_cursor_row_key(tbl) or "").strip()
                    if icon:
                        try:
                            screen.dismiss({"action": "icon", "value": icon, "ctx": ctx})
                        except Exception:
                            pass
            return

        # All other keys go to the default Input handler for typing
        await super()._on_key(event)

    def on_key(self, event) -> None:
        """Backup handler for keys not caught by _on_key."""
        key = str(getattr(event, "key", "") or "")

        # Handle up/down arrows for table navigation
        if key in ("up", "down"):
            delta = -1 if key == "up" else 1
            self._move_table_cursor(delta)
            try:
                event.stop()
            except Exception:
                pass
            return


class IconOverrideModal(ModalScreen[None]):
    def __init__(
        self,
        *,
        ctx: EditContext,
        icons: Sequence[str],
    ) -> None:
        super().__init__()
        self._ctx = ctx
        self._icons = [str(x) for x in icons]
        self._filter: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="icon_modal"):
            yield Static("OnX icon override", classes="title")
            yield Static("Type to filter, ↑/↓ to navigate", classes="muted")
            yield _IconSearchInput(placeholder="Filter icons…", id="icon_search")
            tbl = DataTable(id="icon_table")
            tbl.add_columns("Icon")
            yield tbl
            yield Static("Enter: apply  Esc: cancel  Tab then c: clear", classes="muted")

    def on_mount(self) -> None:
        self._refresh_table()
        try:
            # Default focus: search input so typing works immediately.
            self.query_one("#icon_search", Input).focus()
        except Exception:
            pass

    def _refresh_table(self) -> None:
        try:
            tbl = self.query_one("#icon_table", DataTable)
        except Exception:
            return
        try:
            tbl.clear(columns=False)  # type: ignore[call-arg]
        except Exception:
            try:
                tbl.clear()  # type: ignore[call-arg]
            except Exception:
                pass
        q = (self._filter or "").strip().lower()
        for icon in self._icons:
            if q and q not in icon.lower():
                continue
            tbl.add_row(icon, key=icon)
        # Ensure a predictable cursor row for Enter/apply + arrow navigation.
        try:
            if getattr(tbl, "row_count", 0):
                tbl.cursor_row = 0  # type: ignore[attr-defined]
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "icon_search":
            return
        self._filter = event.value or ""
        self._refresh_table()

    def _current_icon(self) -> Optional[str]:
        try:
            tbl = self.query_one("#icon_table", DataTable)
        except Exception:
            return None
        # Prefer row key at cursor
        try:
            coord = getattr(tbl, "cursor_coordinate", None)
            if coord is not None and hasattr(tbl, "coordinate_to_cell_key"):
                ck = tbl.coordinate_to_cell_key(coord)
                rk = getattr(ck, "row_key", None)
                if rk is not None:
                    return str(getattr(rk, "value", rk))
        except Exception:
            pass
        try:
            row_idx = getattr(tbl, "cursor_row", None)
            if row_idx is not None and hasattr(tbl, "get_row_key"):
                rk = tbl.get_row_key(row_idx)
                if rk is not None:
                    return str(getattr(rk, "value", rk))
        except Exception:
            pass
        return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "icon_table":
            return
        # Enter selects + applies immediately (same as Apply button).
        icon = ""
        try:
            icon = str(event.row_key.value)
        except Exception:
            icon = ""
        if not icon:
            return
        self.dismiss({"action": "icon", "value": icon, "ctx": self._ctx})

    def _is_input_focused(self) -> bool:
        """Check if the search input is currently focused."""
        try:
            inp = self.query_one("#icon_search", Input)
            return self.focused is inp
        except Exception:
            return False

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        input_focused = self._is_input_focused()

        # When input is focused, only intercept navigation keys, not typing keys
        if input_focused:
            # Allow up/down to navigate the table even when input is focused
            if key in ("up", "down"):
                try:
                    tbl = self.query_one("#icon_table", DataTable)
                    if key == "down":
                        tbl.action_cursor_down()
                    else:
                        tbl.action_cursor_up()
                except Exception:
                    return
                try:
                    event.stop()
                except Exception:
                    pass
                return

            # Allow escape to close modal
            if key == "escape":
                self.dismiss(None)
                try:
                    event.stop()
                except Exception:
                    pass
                return

            # Allow enter to apply current selection
            if key in ("enter", "return") or getattr(event, "character", None) == "\r":
                icon = (self._current_icon() or "").strip()
                if icon:
                    self.dismiss({"action": "icon", "value": icon, "ctx": self._ctx})
                    try:
                        event.stop()
                    except Exception:
                        pass
                return

            # Let all other keys (including 'c', '/', etc.) go to the input for typing
            return

        # Input is NOT focused - handle shortcut keys
        if key in ("/", "slash"):
            try:
                self.query_one("#icon_search", Input).focus()
            except Exception:
                pass
            try:
                event.stop()
            except Exception:
                pass
            return

        if key == "c":
            self.dismiss({"action": "icon", "value": "__clear__", "ctx": self._ctx})
            try:
                event.stop()
            except Exception:
                pass
            return

        if key in ("up", "down"):
            try:
                tbl = self.query_one("#icon_table", DataTable)
                if key == "down":
                    tbl.action_cursor_down()
                else:
                    tbl.action_cursor_up()
            except Exception:
                return
            try:
                event.stop()
            except Exception:
                pass
            return

        if key == "escape":
            self.dismiss(None)
            try:
                event.stop()
            except Exception:
                pass
            return

        if key in ("enter", "return") or getattr(event, "character", None) == "\r":
            icon = (self._current_icon() or "").strip()
            if not icon:
                return
            self.dismiss({"action": "icon", "value": icon, "ctx": self._ctx})
            try:
                event.stop()
            except Exception:
                pass
            return


class _SymbolSearchInput(Input):
    """Custom input that lets arrow keys pass through for table navigation."""

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        # Let up/down/enter/escape propagate to parent modal
        if key in ("up", "down", "escape", "enter", "return"):
            return
        # All other keys are handled by the input for typing
        pass


class UnmappedSymbolModal(ModalScreen[Optional[str]]):
    """Modal for mapping a single unmapped CalTopo symbol to an OnX icon.

    Shows suggested matches at the top, allows filtering, and returns
    the selected icon name or None if skipped.
    """

    def __init__(
        self,
        *,
        symbol: str,
        example: str,
        suggestions: List[Tuple[str, float]],
        all_icons: Sequence[str],
        current_index: int = 1,
        total_count: int = 1,
    ) -> None:
        super().__init__()
        self._symbol = symbol
        self._example = example
        self._suggestions = suggestions  # List of (icon_name, confidence) tuples
        self._all_icons = [str(x) for x in all_icons]
        self._filter: str = ""
        self._current_index = current_index
        self._total_count = total_count

    def compose(self) -> ComposeResult:
        with Vertical(id="unmapped_symbol_modal"):
            yield Static(f"Map unmapped symbol ({self._current_index}/{self._total_count})", classes="title")
            yield Static(f"Symbol: [cyan]{self._symbol}[/cyan]", classes="ok")
            yield Static(f"Example: [dim]{self._example}[/dim]", classes="muted")
            yield Static("─" * 40, classes="muted")
            yield Static("Type to filter, ↑/↓ to navigate", classes="muted")
            yield _SymbolSearchInput(placeholder="Filter icons…", id="symbol_icon_search")
            tbl = DataTable(id="symbol_icon_table")
            tbl.add_columns("Icon", "Match")
            yield tbl
            yield Static("Enter: apply  s: skip  Esc: cancel all", classes="muted")

    def on_mount(self) -> None:
        self._refresh_table()
        try:
            self.query_one("#symbol_icon_search", Input).focus()
        except Exception:
            pass

    def _refresh_table(self) -> None:
        try:
            tbl = self.query_one("#symbol_icon_table", DataTable)
        except Exception:
            return
        try:
            tbl.clear(columns=False)  # type: ignore[call-arg]
        except Exception:
            try:
                tbl.clear()  # type: ignore[call-arg]
            except Exception:
                pass

        q = (self._filter or "").strip().lower()

        # Add suggestions first (if not filtering, or if they match filter)
        suggested_icons = set()
        for icon, confidence in self._suggestions:
            if q and q not in icon.lower():
                continue
            conf_pct = int(confidence * 100)
            tbl.add_row(icon, f"★ {conf_pct}%", key=f"__suggest__{icon}")
            suggested_icons.add(icon)

        # Add separator if we have suggestions and are showing all
        if not q and self._suggestions:
            tbl.add_row("─" * 20, "─" * 8, key="__separator__")

        # Add all other icons
        for icon in self._all_icons:
            if icon in suggested_icons:
                continue
            if q and q not in icon.lower():
                continue
            tbl.add_row(icon, "", key=icon)

        # Set cursor to first row
        try:
            if getattr(tbl, "row_count", 0):
                tbl.cursor_row = 0  # type: ignore[attr-defined]
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "symbol_icon_search":
            return
        self._filter = event.value or ""
        self._refresh_table()

    def _current_icon(self) -> Optional[str]:
        try:
            tbl = self.query_one("#symbol_icon_table", DataTable)
        except Exception:
            return None
        # Get row key at cursor
        try:
            coord = getattr(tbl, "cursor_coordinate", None)
            if coord is not None and hasattr(tbl, "coordinate_to_cell_key"):
                ck = tbl.coordinate_to_cell_key(coord)
                rk = getattr(ck, "row_key", None)
                if rk is not None:
                    key = str(getattr(rk, "value", rk))
                    # Handle suggested icons (remove prefix)
                    if key.startswith("__suggest__"):
                        return key[len("__suggest__"):]
                    if key == "__separator__":
                        return None
                    return key
        except Exception:
            pass
        try:
            row_idx = getattr(tbl, "cursor_row", None)
            if row_idx is not None and hasattr(tbl, "get_row_key"):
                rk = tbl.get_row_key(row_idx)
                if rk is not None:
                    key = str(getattr(rk, "value", rk))
                    if key.startswith("__suggest__"):
                        return key[len("__suggest__"):]
                    if key == "__separator__":
                        return None
                    return key
        except Exception:
            pass
        return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "symbol_icon_table":
            return
        key = ""
        try:
            key = str(event.row_key.value)
        except Exception:
            key = ""
        if key == "__separator__":
            return
        if key.startswith("__suggest__"):
            key = key[len("__suggest__"):]
        if not key:
            return
        self.dismiss(key)

    def _is_input_focused(self) -> bool:
        try:
            inp = self.query_one("#symbol_icon_search", Input)
            return self.focused is inp
        except Exception:
            return False

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        input_focused = self._is_input_focused()

        # Handle up/down for table navigation (works in both focused states)
        if key in ("up", "down"):
            try:
                tbl = self.query_one("#symbol_icon_table", DataTable)
                # Move cursor
                if key == "down":
                    tbl.action_cursor_down()
                else:
                    tbl.action_cursor_up()
                # Skip separator row if we landed on it
                try:
                    cur = int(getattr(tbl, "cursor_row", 0) or 0)
                    rk = tbl.get_row_key(cur)
                    if str(getattr(rk, "value", rk)) == "__separator__":
                        # Move again in the same direction
                        if key == "down":
                            tbl.action_cursor_down()
                        else:
                            tbl.action_cursor_up()
                except Exception:
                    pass
            except Exception:
                return
            try:
                event.stop()
            except Exception:
                pass
            return

        # Escape cancels all mapping
        if key == "escape":
            self.dismiss(None)
            try:
                event.stop()
            except Exception:
                pass
            return

        # Enter applies current selection
        if key in ("enter", "return") or getattr(event, "character", None) == "\r":
            icon = (self._current_icon() or "").strip()
            if icon:
                self.dismiss(icon)
                try:
                    event.stop()
                except Exception:
                    pass
            return

        # Only handle skip when input is not focused (so user can type 's')
        if not input_focused and key == "s":
            self.dismiss("__skip__")
            try:
                event.stop()
            except Exception:
                pass
            return

        # Focus input with /
        if not input_focused and key in ("/", "slash"):
            try:
                self.query_one("#symbol_icon_search", Input).focus()
            except Exception:
                pass
            try:
                event.stop()
            except Exception:
                pass
            return
