"""ModalScreen-based modal classes for edit screens."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Static
from rich.text import Text

from cairn.core.color_mapper import ColorMapper
from cairn.tui.edit_screens.shared import EditContext, _table_cursor_row_key
from cairn.tui.edit_screens.widgets import _IconSearchInput, _SymbolSearchInput


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
            ("a", "Open actions menu for selected (set color, rename)"),
            ("x", "Clear all selections"),
            ("Enter", "Continue to waypoints"),
            ("Esc", "Go back"),
            ("q", "Quit application"),
            # GPX tip
            ("", ""),
            ("💡", "GPX imports: Add colors here that GPX cannot store"),
        ],
        "Waypoints": [
            ("↑/↓", "Navigate waypoint list"),
            ("Space", "Toggle selection on current row"),
            ("Ctrl+A", "Select all waypoints"),
            ("/", "Focus search/filter input"),
            ("t", "Focus table (for Space selection)"),
            ("a", "Open actions menu for selected (icon, color, desc)"),
            ("x", "Clear all selections"),
            ("Enter", "Continue to preview"),
            ("Esc", "Go back"),
            ("q", "Quit application"),
            # GPX tip
            ("", ""),
            ("💡", "GPX imports: Add icons/colors/descriptions here"),
        ],
        "Preview": [
            ("c", "Change directory/prefix"),
            ("Enter", "Export (with confirmation)"),
            ("r", "Apply rename edits (after export)"),
            ("Ctrl+N", "New folder (tree mode) / Start new migration"),
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
        char = str(getattr(event, "character", "") or "")
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
