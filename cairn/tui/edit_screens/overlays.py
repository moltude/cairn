"""Container-based overlay classes for edit screens."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.coordinate import Coordinate
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Input, Static
from rich.text import Text

from cairn.core.color_mapper import ColorMapper
from cairn.tui.debug import agent_log as _agent_log
from cairn.tui.edit_screens.shared import (
    EditContext,
    _datatable_clear_rows,
    _table_cursor_row_key,
    validate_folder_name,
)


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
            location="cairn/tui/edit_screens/overlays.py:SaveTargetOverlay.compose",
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
            location="cairn/tui/edit_screens/overlays.py:SaveTargetOverlay.open",
            message="open_called",
            data={"directory": str(directory), "prefix": str(prefix), "prior_classes": str(getattr(self, "classes", None))},
        )
        # Initialize _cur_dir with defensive checks
        if directory is None:
            self._cur_dir = Path.cwd()
        else:
            try:
                self._cur_dir = Path(directory).expanduser().resolve()
            except Exception:
                try:
                    self._cur_dir = Path(directory).expanduser()
                except Exception:
                    self._cur_dir = Path.cwd()
        # Initialize _prefix with defensive checks
        self._prefix = str(prefix or "").strip()
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
            location="cairn/tui/edit_screens/overlays.py:SaveTargetOverlay.close",
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
        # Capture prefix from input field
        try:
            self._prefix = str(self.query_one("#save_target_prefix", Input).value or "").strip()
        except Exception:
            pass

        # Ensure _cur_dir is properly set (defensive check)
        if not hasattr(self, "_cur_dir") or self._cur_dir is None:
            self._cur_dir = Path.cwd()

        # Send Done message with current directory and prefix
        self.post_message(self.Done(directory=self._cur_dir, prefix=self._prefix, cancelled=False))
        self.close()

    def activate(self) -> None:
        """Deterministic activation used by tests (same as Enter on the browser)."""
        # Preserve any typed prefix while navigating the directory browser.
        try:
            self._prefix = str(self.query_one("#save_target_prefix", Input).value or "")
        except Exception:
            pass

        # Handle tree mode (DirectoryTree)
        if self._use_tree:
            try:
                tree = self.query_one("#save_target_browser_tree")
                # In tree mode, selection is handled by DirectoryTree.DirectorySelected events
                # activate() is mainly for DataTable mode, but we can handle Enter on tree
                # by getting the currently selected path if available
                # For now, tree mode navigation is handled via event handlers
                return
            except Exception:
                return

        # Handle table mode (DataTable)
        try:
            tbl = self.query_one("#save_target_browser", DataTable)
        except Exception:
            return
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
                new_path = Path(rk[4:])
                # Resolve the path to ensure it's absolute and normalized
                try:
                    self._cur_dir = new_path.resolve()
                except Exception:
                    # If resolve fails (e.g., path doesn't exist), use expanduser
                    try:
                        self._cur_dir = new_path.expanduser()
                    except Exception:
                        self._cur_dir = new_path
            except Exception as e:
                # Log error but don't crash
                try:
                    getattr(self.app, "_dbg")(event="save.change.navigate.error", data={"rk": rk, "error": str(e)})
                except Exception:
                    pass
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
        from cairn.tui.edit_screens.modals import InfoModal, NewFolderModal

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

        # Update current directory with proper resolution
        try:
            new_path = Path(event.path)
            # Resolve the path to ensure it's absolute and normalized
            try:
                self._cur_dir = new_path.resolve()
            except Exception:
                # If resolve fails (e.g., path doesn't exist), use expanduser
                try:
                    self._cur_dir = new_path.expanduser()
                except Exception:
                    self._cur_dir = new_path
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
            with Horizontal(classes="confirm_buttons"):
                yield Button("Yes (Enter)", id="confirm_yes_btn", classes="confirm_button")
                yield Button("No (Esc)", id="confirm_no_btn", classes="confirm_button")

    def open(self, *, title: str, message: str) -> None:
        self._title = str(title or "Confirm")
        self._message = str(message or "")
        try:
            self.query_one("#confirm_title", Static).update(self._title)
            self.query_one("#confirm_message", Static).update(self._message)
        except Exception:
            pass
        self.add_class("open")
        # Use call_after_refresh to ensure the overlay is fully rendered before setting focus
        try:
            def _set_focus_after_refresh():
                try:
                    yes_btn = self.query_one("#confirm_yes_btn", Button)
                    yes_btn.focus()
                except Exception:
                    pass

            self.call_after_refresh(_set_focus_after_refresh)
            # Also try immediately in case call_after_refresh doesn't fire soon enough
            try:
                yes_btn = self.query_one("#confirm_yes_btn", Button)
                yes_btn.focus()
            except Exception:
                pass
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm_yes_btn":
            self.close()
            self._send(self.Result(True))
        elif event.button.id == "confirm_no_btn":
            self.close()
            self._send(self.Result(False))

    def on_key(self, event) -> None:  # type: ignore[override]
        if not self.has_class("open"):
            return
        key = str(getattr(event, "key", "") or "")
        char = str(getattr(event, "character", "") or "")

        # Handle TAB to switch focus between buttons
        if key == "tab":
            try:
                # Get the focused widget from the app, not from self
                app = getattr(self, "app", None)
                if app is None:
                    return
                focused = getattr(app, "focused", None)
                if focused and focused.id == "confirm_yes_btn":
                    # Switch to No button
                    no_btn = self.query_one("#confirm_no_btn", Button)
                    no_btn.focus()
                elif focused and focused.id == "confirm_no_btn":
                    # Switch back to Yes button
                    yes_btn = self.query_one("#confirm_yes_btn", Button)
                    yes_btn.focus()
                else:
                    # If nothing focused or something else, focus Yes button
                    self.query_one("#confirm_yes_btn", Button).focus()
            except Exception:
                pass
            try:
                event.stop()
            except Exception:
                pass
            return

        # Handle SPACE to activate the focused button
        if key == "space":
            try:
                # Get the focused widget from the app, not from self
                app = getattr(self, "app", None)
                if app is None:
                    return
                focused = getattr(app, "focused", None)
                if focused and focused.id == "confirm_yes_btn":
                    self.close()
                    self._send(self.Result(True))
                elif focused and focused.id == "confirm_no_btn":
                    self.close()
                    self._send(self.Result(False))
            except Exception:
                pass
            try:
                event.stop()
            except Exception:
                pass
            return

        # Handle Escape or 'n' for No
        if key == "escape" or char.lower() == "n":
            self.close()
            self._send(self.Result(False))
            try:
                event.stop()
            except Exception:
                pass
            return

        # Handle Enter or 'y' for Yes
        if key in ("enter", "return") or char == "\r" or char.lower() == "y":
            self.close()
            self._send(self.Result(True))
            try:
                event.stop()
            except Exception:
                pass
            return
