from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Static


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


class InfoModal(ModalScreen[None]):
    """Simple OK modal (used for errors / empty selection)."""

    def __init__(self, message: str, *, title: str = "Info") -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="info_modal"):
            yield Static(self._title, classes="title")
            yield Static(self._message)
            with Horizontal():
                yield Button("OK", id="ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss(None)


class ActionsModal(ModalScreen[None]):
    """
    Pick an edit action for the current selection.

    Emits one of:
      - "rename"
      - "description"
      - "color"
      - "icon" (waypoints only)
      - "cancel"
    """

    def __init__(self, *, ctx: EditContext) -> None:
        super().__init__()
        self._ctx = ctx

    def compose(self) -> ComposeResult:
        with Vertical(id="actions_modal"):
            yield Static("Actions", classes="title")
            yield Static(
                f"Selected: {len(self._ctx.selected_keys)} {self._ctx.kind}(s)",
                classes="muted",
            )
            tbl = DataTable(id="actions_table")
            tbl.add_columns("Action")
            tbl.add_row("Rename", key="rename")
            tbl.add_row("Set description", key="description")
            if self._ctx.kind == "waypoint":
                tbl.add_row("Set/clear icon override", key="icon")
                tbl.add_row("Set waypoint color", key="color")
            else:
                tbl.add_row("Set route color", key="color")
            tbl.add_row("Cancel", key="cancel")
            yield tbl
            yield Static("Enter: choose  Esc: cancel", classes="muted")

    def on_mount(self) -> None:
        try:
            self.query_one("#actions_table", DataTable).focus()
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "actions_table":
            return
        try:
            action = str(event.row_key.value)
        except Exception:
            action = "cancel"
        self.dismiss(action)

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        if key == "escape":
            self.dismiss("cancel")
            try:
                event.stop()
            except Exception:
                pass
            return
        if key in ("enter", "return") or getattr(event, "character", None) == "\r":
            try:
                tbl = self.query_one("#actions_table", DataTable)
            except Exception:
                return
            act = (_table_cursor_row_key(tbl) or "cancel").strip() or "cancel"
            self.dismiss(act)
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
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        try:
            self.query_one("#new_title", Input).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id != "apply":
            return
        raw = ""
        try:
            raw = (self.query_one("#new_title", Input).value or "").strip()
        except Exception:
            raw = ""
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
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        try:
            self.query_one("#new_description", Input).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id != "apply":
            return
        raw = ""
        try:
            raw = (self.query_one("#new_description", Input).value or "").strip()
        except Exception:
            raw = ""
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
            tbl.add_columns("Name", "RGBA")
            yield tbl
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel")
            yield Static("Enter: choose  Esc: cancel", classes="muted")

    def on_mount(self) -> None:
        self._refresh_table()
        try:
            self.query_one("#palette_table", DataTable).focus()
        except Exception:
            pass

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
            tbl.add_row(str(name), str(rgba), key=str(rgba))
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "apply":
            rgba = (self._selected_rgba or "").strip()
            if not rgba:
                # Best-effort default to the cursor row if nothing was selected.
                try:
                    tbl = self.query_one("#palette_table", DataTable)
                    rgba = (_table_cursor_row_key(tbl) or "").strip()
                except Exception:
                    rgba = ""
            if not rgba:
                return
            self.dismiss({"action": "color", "value": rgba, "ctx": self._ctx})
            return

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
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
            yield Input(placeholder="Filter icons…", id="icon_search")
            tbl = DataTable(id="icon_table")
            tbl.add_columns("Icon")
            yield tbl
            with Horizontal():
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Clear", id="clear")
                yield Button("Cancel", id="cancel")
            yield Static("Enter: choose  Esc: cancel", classes="muted")

    def on_mount(self) -> None:
        self._refresh_table()
        try:
            self.query_one("#icon_table", DataTable).focus()
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "clear":
            self.dismiss({"action": "icon", "value": "__clear__", "ctx": self._ctx})
            return
        if event.button.id == "apply":
            icon = (self._current_icon() or "").strip()
            if not icon:
                return
            self.dismiss({"action": "icon", "value": icon, "ctx": self._ctx})
            return

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
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
