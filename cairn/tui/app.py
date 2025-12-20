from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Header, Input, Static
import threading
import os
import time
import re

from rich.text import Text

from cairn.core.color_mapper import ColorMapper
from cairn.core.mapper import map_icon
from cairn.commands.convert_cmd import collect_unmapped_caltopo_symbols, process_and_write_files

from cairn.core.config import (
    get_all_onx_icons,
    get_icon_color,
    load_config,
    normalize_onx_icon_name,
    save_user_mapping,
)
from cairn.core.matcher import FuzzyIconMatcher
from cairn.core.parser import ParsedData, parse_geojson
from cairn.ui.state import UIState, load_state
from cairn.utils.utils import sanitize_filename
from cairn.tui.edit_screens import (
    ColorPickerOverlay,
    ConfirmOverlay,
    ConfirmModal,
    DescriptionOverlay,
    EditContext,
    HelpModal,
    IconPickerOverlay,
    InlineEditOverlay,
    InfoModal,
    RenameOverlay,
    UnmappedSymbolModal,
)

# File types shown in Select_file tree. (Parsing support may be narrower than visibility.)
_VISIBLE_INPUT_EXTS = {".json", ".geojson", ".kml", ".gpx"}
_PARSEABLE_INPUT_EXTS = {".json", ".geojson"}


STEPS = [
    "Select_file",
    "List_data",
    "Folder",
    "Routes",
    "Waypoints",
    "Preview",
    "Save",
]

# Display labels for steps (internal names use underscores for code references)
STEP_LABELS = {
    "Select_file": "Select file",
    "List_data": "Summary of mapping data",
    "Folder": "Folder",
    "Routes": "Routes",
    "Waypoints": "Waypoints",
    "Preview": "Preview",
    "Save": "Save",
}


@dataclass
class TuiModel:
    input_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    parsed: Optional[ParsedData] = None
    selected_folder_id: Optional[str] = None


class Stepper(Static):
    """Left-side stepper with current step highlighted."""

    def __init__(self, *, steps: list[str], **kwargs) -> None:
        # Accept standard Textual widget kwargs (id, classes, name, etc.).
        super().__init__(**kwargs)
        self.steps = steps
        self.current: str = steps[0]
        self.done: set[str] = set()

    def set_state(self, *, current: str, done: set[str]) -> None:
        self.current = current
        self.done = set(done)
        self.refresh()

    def render(self) -> str:
        lines: list[str] = []
        for s in self.steps:
            label = STEP_LABELS.get(s, s)
            if s == self.current:
                lines.append(f" ▸ {label}")
            elif s in self.done:
                lines.append(f" ✓ {label}")
            else:
                lines.append(f"   {label}")
        return "\n".join(lines)


class StepAwareFooter(Static):
    """Dynamic footer showing step-specific keyboard shortcuts."""

    # Define shortcuts for each step
    STEP_SHORTCUTS = {
        "Select_file": [
            ("↑↓", "Navigate"),
            ("Enter", "Select"),
            ("Tab", "Next field"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "List_data": [
            ("m", "Map unmapped"),
            ("Enter", "Continue"),
            ("Tab", "Next field"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Folder": [
            ("↑↓", "Navigate"),
            ("Space", "Toggle (multi-folder)"),
            ("Enter", "Select"),
            ("Tab", "Next field"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Routes": [
            ("↑↓", "Navigate"),
            ("Space", "Toggle"),
            ("Ctrl+A", "Toggle all"),
            ("/", "Search"),
            ("Tab", "Next field"),
            ("a", "Edit"),
            ("x", "Clear"),
            ("Enter", "Continue"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Waypoints": [
            ("↑↓", "Navigate"),
            ("Space", "Toggle"),
            ("Ctrl+A", "Toggle all"),
            ("/", "Search"),
            ("Tab", "Next field"),
            ("a", "Edit"),
            ("x", "Clear"),
            ("Enter", "Continue"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Preview": [
            ("Enter", "Continue"),
            ("Tab", "Next field"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Save": [
            ("Enter", "Export"),
            ("Tab", "Next field"),
            ("r", "Apply names"),
            ("n", "New file"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_step: str = "Select_file"

    def set_step(self, step: str) -> None:
        self.current_step = step
        self.refresh()

    def render(self) -> str:
        shortcuts = self.STEP_SHORTCUTS.get(self.current_step, [])
        parts = [f"[bold]{key}[/] {desc}" for key, desc in shortcuts]
        return "  ".join(parts)


class CairnTuiApp(App):
    """
    Cairn - CalTopo → OnX TUI.

    This is intentionally a guided, linear flow with a visible stepper and
    warm theme. It reuses existing parsing + export logic.
    """

    CSS_PATH = "theme.tcss"
    TITLE = "Cairn"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "back", "Back", key_display="Esc"),
        Binding("question_mark", "show_help", "Help", key_display="?"),
        Binding("tab", "focus_next", "Next field"),
        Binding("/", "focus_search", "Search"),
        Binding("t", "focus_table", "Table"),
        Binding("a", "actions", "Edit"),
        Binding("x", "clear_selection", "Clear selection"),
        Binding("ctrl+a", "select_all", "Toggle all"),
        Binding("r", "apply_renames", "Apply names"),
        Binding("n", "new_file", "New file"),
        Binding("m", "map_unmapped", "Map unmapped"),
    ]

    step: reactive[str] = reactive(STEPS[0])

    def __init__(self) -> None:
        super().__init__()
        self.model = TuiModel()
        self._done_steps: set[str] = set()
        self._state: UIState = load_state()
        self._config = load_config(None)
        self._folder_name_by_id: dict[str, str] = {}
        self._selected_route_keys: set[str] = set()
        self._selected_waypoint_keys: set[str] = set()
        self._export_manifest: Optional[list[tuple[str, str, int, int]]] = None
        self._export_error: Optional[str] = None
        self._export_in_progress: bool = False
        self._routes_filter: str = ""
        self._waypoints_filter: str = ""
        self._ui_error: Optional[str] = None
        self._debug_events: list[dict[str, object]] = []
        # Select_file browser state
        self._file_browser_dir: Optional[Path] = None
        # Save browser state (output directory picker)
        self._save_browser_dir: Optional[Path] = None
        self._output_prefix: str = ""
        self._rename_overrides_by_idx: dict[int, str] = {}
        self._post_save_prompt_shown: bool = False
        # Unmapped symbol mapping state
        self._unmapped_symbols: list[tuple[str, dict]] = []  # [(symbol, info), ...]
        self._unmapped_index: int = 0
        # Edit flow state
        self._in_single_item_edit: bool = False  # Track if we're editing a single item
        self._in_inline_edit: bool = False  # Track if we're in inline edit mode (single or multiple)
        self._confirm_callback: Optional[Callable[[bool], None]] = None
        # Multi-folder workflow state
        self._folder_iteration_mode: bool = False
        self._folders_to_process: list[str] = []
        self._current_folder_index: int = 0
        self._selected_folders: set[str] = set()  # Folders selected for processing

    def _set_input_path(self, p: Path) -> None:
        """
        Set a new input path and reset all derived UI/model state.

        Without this, switching files can incorrectly reuse previously parsed data.
        """
        try:
            p = Path(p).expanduser()
            try:
                p = p.resolve()
            except Exception:
                pass
        except Exception:
            pass

        # If it's the same file, don't thrash state.
        try:
            cur = self.model.input_path
            if cur is not None:
                try:
                    cur = cur.resolve()
                except Exception:
                    pass
            if cur is not None and str(cur) == str(p):
                self.model.input_path = p
                return
        except Exception:
            pass

        self.model.input_path = p
        self.model.parsed = None
        self.model.selected_folder_id = None
        self._folder_name_by_id = {}
        self._selected_route_keys.clear()
        self._selected_waypoint_keys.clear()
        self._routes_filter = ""
        self._waypoints_filter = ""
        # Reset multi-folder state
        self._folder_iteration_mode = False
        self._folders_to_process = []
        self._current_folder_index = 0
        self._selected_folders.clear()

        # Reset export UI state for the new dataset.
        self._export_manifest = None
        self._export_error = None
        self._export_in_progress = False
        self._rename_overrides_by_idx.clear()
        self._output_prefix = ""
        self._save_browser_dir = None
        self._post_save_prompt_shown = False

        # Reset progress indicator.
        self._done_steps.clear()
        # Track whether edits were applied since last selection clear, to show a hint.
        self._routes_edited: bool = False
        self._waypoints_edited: bool = False

    def _dbg(self, *, event: str, data: Optional[dict[str, object]] = None) -> None:
        """
        Best-effort debug event sink.

        This app uses `_dbg(...)` from various event handlers / error paths; it must
        never crash the UI if debug logging isn't configured.
        """
        try:
            enabled = os.getenv("CAIRN_TUI_DEBUG") or os.getenv("CAIRN_TUI_ARTIFACTS")
            if not enabled:
                return
            payload: dict[str, object] = {
                "t": float(time.time()),
                "event": str(event),
                "step": str(getattr(self, "step", "")),
                "data": data or {},
            }
            self._debug_events.append(payload)
            # Prevent unbounded growth during long sessions/tests.
            if len(self._debug_events) > 500:
                self._debug_events = self._debug_events[-250:]
        except Exception:
            return

    def _color_chip(self, rgba: str) -> Text:
        r, g, b = ColorMapper.parse_color(rgba)
        name = ColorMapper.get_color_name(rgba).replace("-", " ").upper()
        chip = Text("■ ", style=f"rgb({r},{g},{b})")
        chip.append(name, style="bold")
        return chip

    def _resolved_waypoint_icon(self, wp) -> str:
        try:
            props = getattr(wp, "properties", None)
            if isinstance(props, dict):
                ov = (props.get("cairn_onx_icon_override") or "").strip()
                if ov:
                    return ov
        except Exception:
            pass
        title0 = str(getattr(wp, "title", "") or "")
        desc0 = str(getattr(wp, "description", "") or "")
        sym0 = str(getattr(wp, "symbol", "") or "")
        return map_icon(title0, desc0, sym0, self._config)

    def _resolved_waypoint_color(self, wp, icon: str) -> str:
        # Mirror cairn/core/writers.py policy.
        mc_raw = str(getattr(wp, "color", "") or "").strip()
        if mc_raw:
            return ColorMapper.map_waypoint_color(mc_raw)
        return get_icon_color(
            icon,
            default=getattr(self._config, "default_color", ColorMapper.DEFAULT_WAYPOINT_COLOR),
        )

    def _table_cursor_row_key(self, table: DataTable) -> Optional[str]:
        """Best-effort current row key at cursor for version-compat."""
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

    def _datatable_clear_rows(self, table: DataTable) -> None:
        """
        Clear rows without forcing a full screen re-render.

        Textual DataTable APIs vary; we try common variants.
        """
        # Try newer API: clear(columns=False)
        try:
            table.clear(columns=False)  # type: ignore[call-arg]
            return
        except TypeError:
            pass
        except Exception:
            # fall through
            pass

        # Try clear() (may clear columns too)
        try:
            table.clear()  # type: ignore[call-arg]
            return
        except Exception:
            pass

        # Fallback: best-effort remove rows if supported
        try:
            row_keys = list(getattr(table, "rows", {}).keys())  # type: ignore[attr-defined]
            for rk in row_keys:
                table.remove_row(rk)  # type: ignore[call-arg]
        except Exception:
            return

    def _refresh_folder_table(self) -> Optional[int]:
        """Refresh the folder table to show updated selection state.

        Returns the target cursor row index if a row key was saved, None otherwise.
        """
        if self.step != "Folder":
            return None
        try:
            table = self.query_one("#folder_table", DataTable)
        except Exception:
            return None
        if self.model.parsed is None:
            return None

        folders = list((getattr(self.model.parsed, "folders", {}) or {}).items())
        if not folders:
            return None

        # Save current cursor position by row key (more reliable than row index)
        current_row_key = None
        try:
            current_row_key = self._table_cursor_row_key(table)
        except Exception:
            pass

        # Clear rows
        self._datatable_clear_rows(table)

        # Ensure columns exist
        try:
            if not getattr(table, "columns", None):  # type: ignore[attr-defined]
                if len(folders) > 1:
                    table.add_columns("Selected", "Folder", "Waypoints", "Routes", "Shapes")
                else:
                    table.add_columns("Folder", "Waypoints", "Routes", "Shapes")
        except Exception:
            try:
                if len(folders) > 1:
                    table.add_columns("Selected", "Folder", "Waypoints", "Routes", "Shapes")
                else:
                    table.add_columns("Folder", "Waypoints", "Routes", "Shapes")
            except Exception:
                pass

        # Sort folders alphabetically
        folders = sorted(folders, key=lambda x: str((x[1] or {}).get("name") or x[0]).lower())

        # Re-add rows with updated selection state
        target_row_index = None
        for idx, (folder_id, fd) in enumerate(folders):
            name = str((fd or {}).get("name") or folder_id)
            w = len((fd or {}).get("waypoints", []) or [])
            t = len((fd or {}).get("tracks", []) or [])
            s = len((fd or {}).get("shapes", []) or [])
            if len(folders) > 1:
                sel = "●" if folder_id in self._selected_folders else " "
                table.add_row(sel, name, str(w), str(t), str(s), key=folder_id)
            else:
                table.add_row(name, str(w), str(t), str(s), key=folder_id)

            # Track the index of the row we want to restore cursor to
            if current_row_key and str(folder_id) == str(current_row_key):
                target_row_index = idx

        # Return target index for caller to restore cursor
        return target_row_index if current_row_key and target_row_index is not None else None

    def _refresh_waypoints_table(self) -> None:
        if self.step != "Waypoints":
            return
        try:
            table = self.query_one("#waypoints_table", DataTable)
        except Exception:
            return
        if self.model.parsed is None or not self.model.selected_folder_id:
            return
        fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
        waypoints = list((fd or {}).get("waypoints", []) or [])

        q = (self._waypoints_filter or "").strip().lower()
        self._datatable_clear_rows(table)

        # Ensure columns exist if clear() nuked them.
        try:
            if not getattr(table, "columns", None):  # type: ignore[attr-defined]
                table.add_columns("Selected", "Name", "OnX icon", "OnX color")
        except Exception:
            try:
                table.add_columns("Selected", "Name", "OnX icon", "OnX color")
            except Exception:
                pass

        # Sort waypoints alphabetically by name (case-insensitive)
        waypoints = sorted(waypoints, key=lambda wp: str(getattr(wp, "title", "") or "Untitled").lower())

        for i, wp in enumerate(waypoints):
            key = self._feature_row_key(wp, str(i))
            title0 = str(getattr(wp, "title", "") or "Untitled")
            if q and q not in title0.lower():
                continue
            sel = "●" if key in self._selected_waypoint_keys else " "
            mapped = self._resolved_waypoint_icon(wp)
            rgba = self._resolved_waypoint_color(wp, mapped)
            try:
                table.add_row(sel, title0, mapped, self._color_chip(rgba), key=key)
            except Exception:
                name = ColorMapper.get_color_name(rgba).replace("-", " ").upper()
                table.add_row(sel, title0, mapped, f"■ {name}", key=key)

    def _refresh_routes_table(self) -> None:
        if self.step != "Routes":
            return
        try:
            table = self.query_one("#routes_table", DataTable)
        except Exception:
            return
        if self.model.parsed is None or not self.model.selected_folder_id:
            return
        fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
        tracks = list((fd or {}).get("tracks", []) or [])

        q = (self._routes_filter or "").strip().lower()
        self._datatable_clear_rows(table)

        try:
            if not getattr(table, "columns", None):  # type: ignore[attr-defined]
                table.add_columns("Selected", "Name", "Color", "Pattern", "Width")
        except Exception:
            try:
                table.add_columns("Selected", "Name", "Color", "Pattern", "Width")
            except Exception:
                pass

        # Sort routes alphabetically by name (case-insensitive)
        tracks = sorted(tracks, key=lambda trk: str(getattr(trk, "title", "") or "Untitled").lower())

        for i, trk in enumerate(tracks):
            key = self._feature_row_key(trk, str(i))
            name = str(getattr(trk, "title", "") or "Untitled")
            if q and q not in name.lower():
                continue
            sel = "●" if key in self._selected_route_keys else " "
            rgba = ColorMapper.map_track_color(str(getattr(trk, "stroke", "") or ""))
            try:
                color_cell = self._color_chip(rgba)
            except Exception:
                color_cell = f"■ {ColorMapper.get_color_name(rgba).replace('-', ' ').upper()}"
            table.add_row(
                sel,
                name,
                color_cell,
                str(getattr(trk, "pattern", "") or ""),
                str(getattr(trk, "stroke_width", "") or ""),
                key=key,
            )

    # (Edit_routes/Edit_waypoints steps removed; no extra edit tables needed.)

    # -----------------------
    # Compose
    # -----------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            with Vertical(classes="sidebar"):
                yield Static("CAIRN", classes="title")
                yield Static("CalTopo → OnX (TUI v1)", classes="muted")
                yield Static("", id="status", classes="muted")
                yield Static("")
                yield Stepper(steps=STEPS, id="stepper")
                yield Static("")
                yield Static("Instructions", classes="muted")
                yield Static("", id="sidebar_instructions")
                yield Static("")
                yield Static("Shortcuts", classes="muted")
                yield Static("", id="sidebar_shortcuts", classes="muted")
            with Container(classes="main"):
                yield Static("", id="main_title", classes="title")
                yield Static("", id="main_subtitle", classes="muted")
                yield Container(id="main_body")
                # True popup overlay (stays within the current screen, doesn't navigate).
                yield InlineEditOverlay()
                yield ColorPickerOverlay()
                yield IconPickerOverlay()
                yield RenameOverlay()
                yield DescriptionOverlay()
                yield ConfirmOverlay()
        yield StepAwareFooter(id="step_footer", classes="footer")

    def on_mount(self) -> None:
        self._goto("Select_file")

    def on_inline_edit_overlay_field_chosen(self, message: InlineEditOverlay.FieldChosen) -> None:  # type: ignore[name-defined]
        """
        Handle selection events from the in-screen inline editor overlay.

        We route back into the existing edit flow, but without Screen navigation.
        """
        field_key = getattr(message, "field_key", None)
        if field_key is None:
            # Done / Esc
            self._on_inline_edit_action(None)
            return
        self._on_inline_edit_action(field_key)

    def on_color_picker_overlay_color_picked(self, message: ColorPickerOverlay.ColorPicked) -> None:  # type: ignore[name-defined]
        """Handle apply/cancel from ColorPickerOverlay."""
        # Ensure focus doesn't remain on the (now hidden) picker table.
        try:
            self.set_focus(None)  # type: ignore[arg-type]
        except Exception:
            pass
        rgba = getattr(message, "rgba", None)
        if rgba is None:
            # Cancel -> reopen inline edit overlay
            ctx = self._selected_keys_for_step()
            if ctx is not None:
                feats = self._selected_features(ctx)
                if feats:
                    self._show_inline_overlay(ctx=ctx, feats=feats)
            return

        ctx = self._selected_keys_for_step()
        if ctx is None:
            return
        self._apply_edit_payload({"action": "color", "value": rgba, "ctx": ctx})
        # Re-open inline overlay
        feats = self._selected_features(ctx)
        if feats:
            self._show_inline_overlay(ctx=ctx, feats=feats)

    def on_icon_picker_overlay_icon_picked(self, message: IconPickerOverlay.IconPicked) -> None:  # type: ignore[name-defined]
        """Handle apply/cancel from IconPickerOverlay."""
        try:
            self.set_focus(None)  # type: ignore[arg-type]
        except Exception:
            pass
        icon = getattr(message, "icon", None)
        if icon is None:
            ctx = self._selected_keys_for_step()
            if ctx is not None:
                feats = self._selected_features(ctx)
                if feats:
                    self._show_inline_overlay(ctx=ctx, feats=feats)
            return

        ctx = self._selected_keys_for_step()
        if ctx is None:
            return
        self._apply_edit_payload({"action": "icon", "value": icon, "ctx": ctx})
        feats = self._selected_features(ctx)
        if feats:
            self._show_inline_overlay(ctx=ctx, feats=feats)

    def _show_inline_overlay(self, *, ctx: EditContext, feats: list) -> None:
        """(Internal) open InlineEditOverlay with current helpers."""
        self._in_single_item_edit = len(feats) == 1
        self._in_inline_edit = True

        def get_route_color(feat):
            stroke = str(getattr(feat, "stroke", "") or "")
            if stroke:
                return ColorMapper.map_track_color(stroke)
            return ColorMapper.DEFAULT_TRACK_COLOR

        try:
            overlay = self.query_one("#inline_edit_overlay", InlineEditOverlay)
        except Exception:
            return
        overlay.open(
            ctx=ctx,
            features=feats,
            get_color_chip=self._color_chip,
            get_waypoint_icon=self._resolved_waypoint_icon,
            get_waypoint_color=self._resolved_waypoint_color,
            get_route_color=get_route_color,
        )

    def on_rename_overlay_submitted(self, message: RenameOverlay.Submitted) -> None:  # type: ignore[name-defined]
        """Handle apply/cancel from RenameOverlay."""
        # Clear focus so we don't leave focus on a hidden overlay input.
        try:
            self.set_focus(None)  # type: ignore[arg-type]
        except Exception:
            pass

        ctx = getattr(message, "ctx", None)
        value = getattr(message, "value", None)
        if not isinstance(ctx, EditContext) or value is None:
            # Cancel -> return to inline overlay if editing
            if isinstance(ctx, EditContext) and self._in_inline_edit:
                feats = self._selected_features(ctx)
                if feats:
                    self._show_inline_overlay(ctx=ctx, feats=feats)
            else:
                try:
                    self.call_after_refresh(self.action_focus_table)
                except Exception:
                    self.action_focus_table()
            return

        self._apply_edit_payload({"action": "rename", "value": value, "ctx": ctx})
        # If this triggered a confirmation overlay (multi-rename), don't steal focus by
        # reopening the inline overlay yet; `_apply_rename_confirmed` will bring us back.
        try:
            if self.query_one("#confirm_overlay", ConfirmOverlay).has_class("open"):
                return
        except Exception:
            pass
        if self._in_inline_edit:
            feats = self._selected_features(ctx)
            if feats:
                self._show_inline_overlay(ctx=ctx, feats=feats)

    def on_description_overlay_submitted(self, message: DescriptionOverlay.Submitted) -> None:  # type: ignore[name-defined]
        """Handle apply/cancel from DescriptionOverlay."""
        try:
            self.set_focus(None)  # type: ignore[arg-type]
        except Exception:
            pass

        ctx = getattr(message, "ctx", None)
        value = getattr(message, "value", None)
        if not isinstance(ctx, EditContext) or value is None:
            if isinstance(ctx, EditContext) and self._in_inline_edit:
                feats = self._selected_features(ctx)
                if feats:
                    self._show_inline_overlay(ctx=ctx, feats=feats)
            else:
                try:
                    self.call_after_refresh(self.action_focus_table)
                except Exception:
                    self.action_focus_table()
            return

        self._apply_edit_payload({"action": "description", "value": value, "ctx": ctx})
        if self._in_inline_edit:
            feats = self._selected_features(ctx)
            if feats:
                self._show_inline_overlay(ctx=ctx, feats=feats)

    def on_confirm_overlay_result(self, message: ConfirmOverlay.Result) -> None:  # type: ignore[name-defined]
        """Handle result from ConfirmOverlay."""
        cb = self._confirm_callback
        self._confirm_callback = None
        if cb is None:
            return
        try:
            cb(bool(getattr(message, "confirmed", False)))
        except Exception:
            pass

    def _confirm(self, *, title: str, message: str, callback: Callable[[bool], None]) -> None:
        """Show an in-screen confirm overlay and run callback with result."""
        self._confirm_callback = callback
        try:
            ov = self.query_one("#confirm_overlay", ConfirmOverlay)
        except Exception:
            return
        ov.open(title=title, message=message)

    # -----------------------
    # Navigation
    # -----------------------
    def _reset_focus_for_step(self) -> None:
        """
        Ensure focus is on an on-screen widget after step transitions.

        This fixes a subtle real-world issue: when we auto-advance from Select_file
        to List_data, focus may remain on a removed widget, causing Enter key presses
        to be swallowed / not reach the app-level flow.
        """
        try:
            if self.step == "List_data":
                # Clear focus so Enter/Escape route to app handlers.
                self.set_focus(None)  # type: ignore[arg-type]
                return
            if self.step == "Folder":
                self.query_one("#folder_table", DataTable).focus()
                return
            if self.step == "Preview":
                # Preview uses read-only tables; avoid focusing them so Enter/q reach app handlers.
                self.set_focus(None)  # type: ignore[arg-type]
                return
            if self.step == "Save":
                # Default focus on the directory browser so arrows + Enter work immediately,
                # but avoid focusing the output dir input (typing there should be explicit via Tab).
                try:
                    self.query_one("#save_browser", DataTable).focus()
                except Exception:
                    self.set_focus(None)  # type: ignore[arg-type]
                return
        except Exception:
            return

    def _refresh_file_browser(self) -> None:
        """Populate Select_file file browser table with dirs + allowed extensions only."""
        if self.step != "Select_file":
            return
        try:
            table = self.query_one("#file_browser", DataTable)
        except Exception:
            return
        base = self._file_browser_dir
        if base is None:
            return

        # Clear rows without nuking columns (compat).
        self._datatable_clear_rows(table)
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
                if p.is_file() and p.suffix.lower() in _VISIBLE_INPUT_EXTS
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

    def _file_browser_enter(self) -> None:
        """Handle Enter on Select_file file browser table."""
        if self.step != "Select_file":
            return
        base = self._file_browser_dir
        if base is None:
            return
        try:
            table = self.query_one("#file_browser", DataTable)
        except Exception:
            return
        rk = self._table_cursor_row_key(table)
        if not rk:
            return
        if rk == "__up__":
            try:
                self._file_browser_dir = base.parent if base.parent != base else base
            except Exception:
                self._file_browser_dir = base
            self._refresh_file_browser()
            return
        if rk.startswith("dir:"):
            p = Path(rk[4:])
            self._file_browser_dir = p
            self._refresh_file_browser()
            return
        if rk.startswith("file:"):
            p = Path(rk[5:])
            suf = p.suffix.lower()
            if suf in _PARSEABLE_INPUT_EXTS and p.exists() and p.is_file():
                self._set_input_path(p)
                self._done_steps.add("Select_file")
                self._goto("List_data")
                return
            if suf in _VISIBLE_INPUT_EXTS:
                self.push_screen(
                    InfoModal(
                        "This TUI currently supports CalTopo GeoJSON inputs only (.json/.geojson).\n\n"
                        "GPX/KML inputs are not supported in the TUI yet."
                    )
                )
            return

    def _refresh_save_browser(self) -> None:
        """Populate Save output directory browser table (directories only)."""
        if self.step != "Save":
            return
        try:
            table = self.query_one("#save_browser", DataTable)
        except Exception:
            return

        base = self._save_browser_dir
        if base is None:
            return

        self._datatable_clear_rows(table)
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
        except Exception:
            entries = []

        dirs = sorted(
            [p for p in entries if p.is_dir() and not p.name.startswith(".")],
            key=lambda p: p.name.lower(),
        )
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
                    table.cursor_row = first_dir_row  # type: ignore[attr-defined]
                else:
                    # No sub-dirs; fall back to [Use this folder] (2nd-to-last row).
                    table.cursor_row = max(int(getattr(table, "row_count", 0) or 0) - 2, 0)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _save_browser_enter(self) -> None:
        """Handle Enter on Save output directory browser table."""
        if self.step != "Save":
            return
        base = self._save_browser_dir
        if base is None:
            return
        try:
            table = self.query_one("#save_browser", DataTable)
        except Exception:
            return
        rk = self._table_cursor_row_key(table)
        if not rk:
            return
        if rk == "__up__":
            try:
                self._save_browser_dir = base.parent if base.parent != base else base
            except Exception:
                self._save_browser_dir = base
            self._render_main()
            return
        if rk == "__use__":
            self.model.output_dir = base
            self._render_sidebar()
            return
        if rk == "__export__":
            # Export uses the global confirm modal (Enter to confirm, Esc to cancel).
            self.action_export()
            return
        if rk.startswith("dir:"):
            try:
                p = Path(rk[4:])
            except Exception:
                return
            self._save_browser_dir = p
            self._render_main()
            return

    def _goto(self, step: str) -> None:
        if step not in STEPS:
            return
        self.step = step
        # Clear per-step edit hints when leaving the step.
        if step != "Routes":
            self._routes_edited = False
        if step != "Waypoints":
            self._waypoints_edited = False
        self._render_sidebar()
        self._render_main()
        self._update_footer()
        try:
            self.call_after_refresh(self._reset_focus_for_step)
        except Exception:
            # If call_after_refresh isn't available for some reason, fall back to best effort.
            self._reset_focus_for_step()

    def _update_footer(self) -> None:
        """Update the step-aware footer with current step's shortcuts."""
        try:
            footer = self.query_one("#step_footer", StepAwareFooter)
            footer.set_step(self.step)
        except Exception:
            pass

    def action_back(self) -> None:
        idx = STEPS.index(self.step)
        if idx <= 0:
            return
        self._goto(STEPS[idx - 1])

    def _infer_folder_selection(self) -> Optional[str]:
        """
        Best-effort: infer current folder selection from the folder table cursor.

        Textual's DataTable APIs vary a bit across versions; we try a few approaches.
        """
        try:
            table = self.query_one("#folder_table", DataTable)
        except Exception:
            return None

        # Attempt 1: cursor_coordinate -> row_key
        try:
            coord = getattr(table, "cursor_coordinate", None)
            if coord is not None and hasattr(table, "coordinate_to_cell_key"):
                cell_key = table.coordinate_to_cell_key(coord)
                rk = getattr(cell_key, "row_key", None)
                if rk is not None:
                    return str(getattr(rk, "value", rk))
        except Exception:
            pass

        # Attempt 2: cursor_row -> row key lookup (if available)
        try:
            row_idx = getattr(table, "cursor_row", None)
            if row_idx is not None and hasattr(table, "get_row_key"):
                rk = table.get_row_key(row_idx)
                if rk is not None:
                    return str(getattr(rk, "value", rk))
        except Exception:
            pass

        return None

    def _get_next_step_after_folder(self) -> str:
        """Determine next step after Folder, skipping empty Routes/Waypoints steps."""
        if self.model.parsed is None or not self.model.selected_folder_id:
            return "Preview"
        fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
        if not fd:
            return "Preview"
        tracks = list((fd or {}).get("tracks", []) or [])
        waypoints = list((fd or {}).get("waypoints", []) or [])

        # If routes exist, go to Routes
        if tracks:
            return "Routes"
        # If no routes but waypoints exist, go to Waypoints
        if waypoints:
            return "Waypoints"
        # Otherwise go to Preview
        return "Preview"

    def _has_real_folders(self) -> bool:
        """Check if there are real folders (not just default folder)."""
        if self.model.parsed is None:
            return False
        folders = getattr(self.model.parsed, "folders", {}) or {}
        if not folders:
            return False
        # If only one folder and it's "default", treat as no folders
        if len(folders) == 1:
            default_id = list(folders.keys())[0]
            if default_id == "default":
                # Check if default folder has any content
                fd = folders[default_id]
                tracks = list((fd or {}).get("tracks", []) or [])
                waypoints = list((fd or {}).get("waypoints", []) or [])
                return len(tracks) > 0 or len(waypoints) > 0
        return True

    def action_continue(self) -> None:
        # Step-specific gating + actions.
        if self.step == "Select_file":
            # Rely on selecting a file in the browser table (or submitting the input field) to advance.
            return

        if self.step == "List_data":
            self._done_steps.add("List_data")
            # Skip Folder step if no real folders exist
            if not self._has_real_folders():
                # Set default folder if it exists
                folders = getattr(self.model.parsed, "folders", {}) or {}
                if folders:
                    self.model.selected_folder_id = list(folders.keys())[0]
                self._done_steps.add("Folder")
                next_step = self._get_next_step_after_folder()
                self._goto(next_step)
            else:
                self._goto("Folder")
            return

        if self.step == "Folder":
            # Check if we have multiple folders to process
            folders = getattr(self.model.parsed, "folders", {}) or {}
            if len(folders) > 1:
                # Multi-folder workflow: check if folders are selected
                if not self._selected_folders:
                    # No folders selected yet, user needs to select
                    inferred = self._infer_folder_selection()
                    if inferred:
                        # Toggle selection on current folder
                        if inferred in self._selected_folders:
                            self._selected_folders.remove(inferred)
                        else:
                            self._selected_folders.add(inferred)
                        self._refresh_folder_table()  # Refresh to show selection
                        # Restore focus to the table
                        try:
                            self.query_one("#folder_table", DataTable).focus()
                        except Exception:
                            pass
                    return
                # Folders selected, start processing first folder
                if not self._folders_to_process:
                    self._folders_to_process = list(self._selected_folders)
                    self._current_folder_index = 0
                # Set current folder and proceed
                if self._current_folder_index < len(self._folders_to_process):
                    self.model.selected_folder_id = self._folders_to_process[self._current_folder_index]
                    self._folder_iteration_mode = True
                    self._done_steps.add("Folder")
                    next_step = self._get_next_step_after_folder()
                    self._goto(next_step)
                else:
                    # All folders processed, go to final preview
                    self._folder_iteration_mode = False
                    self._goto("Preview")
            else:
                # Single folder workflow (existing behavior)
                if not self.model.selected_folder_id:
                    inferred = self._infer_folder_selection()
                    if inferred:
                        self.model.selected_folder_id = inferred
                    else:
                        return
                self._done_steps.add("Folder")
                next_step = self._get_next_step_after_folder()
                self._goto(next_step)
            return

        if self.step == "Routes":
            # If items are selected, open edit modal directly instead of advancing
            if self._selected_route_keys:
                self.action_actions()
                return
            self._done_steps.add("Routes")
            # Check if waypoints exist, skip if not
            if self.model.parsed is None or not self.model.selected_folder_id:
                # If in multi-folder mode, move to next folder
                if self._folder_iteration_mode and self._folders_to_process:
                    self._current_folder_index += 1
                    if self._current_folder_index < len(self._folders_to_process):
                        self.model.selected_folder_id = self._folders_to_process[self._current_folder_index]
                        self._selected_route_keys.clear()
                        next_step = self._get_next_step_after_folder()
                        self._goto(next_step)
                    else:
                        self._folder_iteration_mode = False
                        self._goto("Preview")
                else:
                    self._goto("Preview")
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            waypoints = list((fd or {}).get("waypoints", []) or []) if fd else []
            if waypoints:
                self._goto("Waypoints")
            else:
                self._done_steps.add("Waypoints")
                # If in multi-folder mode, move to next folder
                if self._folder_iteration_mode and self._folders_to_process:
                    self._current_folder_index += 1
                    if self._current_folder_index < len(self._folders_to_process):
                        self.model.selected_folder_id = self._folders_to_process[self._current_folder_index]
                        self._selected_route_keys.clear()
                        self._selected_waypoint_keys.clear()
                        next_step = self._get_next_step_after_folder()
                        self._goto(next_step)
                    else:
                        self._folder_iteration_mode = False
                        self._goto("Preview")
                else:
                    self._goto("Preview")
            return

        if self.step == "Waypoints":
            # If items are selected, open edit modal directly instead of advancing
            if self._selected_waypoint_keys:
                self.action_actions()
                return
            self._done_steps.add("Waypoints")
            # If in multi-folder mode, move to next folder
            if self._folder_iteration_mode and self._folders_to_process:
                self._current_folder_index += 1
                if self._current_folder_index < len(self._folders_to_process):
                    # Move to next folder
                    self.model.selected_folder_id = self._folders_to_process[self._current_folder_index]
                    self._selected_route_keys.clear()
                    self._selected_waypoint_keys.clear()
                    next_step = self._get_next_step_after_folder()
                    self._goto(next_step)
                else:
                    # All folders processed, go to final preview
                    self._folder_iteration_mode = False
                    self._goto("Preview")
            else:
                self._goto("Preview")
            return

        if self.step == "Preview":
            self._done_steps.add("Preview")
            self._goto("Save")
            return

        if self.step == "Save":
            # Save is driven by the on-screen browser/actions (Enter on [Export]).
            return

    def action_export(self) -> None:
        if self.step == "Save":
            # Show confirmation before export
            self.push_screen(
                ConfirmModal(
                    "Ready to generate map files?\n\n"
                    "This will write GPX/KML files to the output directory.",
                    title="Confirm Export",
                ),
                self._on_export_confirmed,
            )

    def _on_export_confirmed(self, confirmed: bool) -> None:
        if confirmed:
            self._start_export()

    def action_apply_renames(self) -> None:
        """Apply filename edits to exported files (Save step only)."""
        if self.step != "Save":
            return
        if self._export_in_progress:
            return
        if not self._export_manifest:
            return

        out_dir = self.model.output_dir or (Path.cwd() / "onx_ready")
        try:
            out_dir = out_dir.expanduser()
        except Exception:
            pass

        # Validate desired names first (no partial renames).
        desired_by_idx: dict[int, str] = {}
        seen: set[str] = set()
        for i, (fn, fmt, cnt, sz) in enumerate(self._export_manifest):
            raw = str(self._rename_overrides_by_idx.get(i, fn) or "").strip()
            if not raw:
                self._export_error = f"Rename error: filename for '{fn}' is empty."
                self._render_main()
                return
            # Disallow paths; this is a rename within the output directory.
            if Path(raw).name != raw:
                self._export_error = f"Rename error: '{raw}' must be a filename (no directories)."
                self._render_main()
                return
            # Keep extension stable to avoid confusing output types.
            if Path(raw).suffix.lower() != Path(fn).suffix.lower():
                self._export_error = f"Rename error: '{raw}' must keep extension '{Path(fn).suffix}'."
                self._render_main()
                return
            if raw in seen:
                self._export_error = f"Rename error: duplicate filename '{raw}'."
                self._render_main()
                return
            seen.add(raw)
            desired_by_idx[i] = raw

        # Apply renames on disk.
        try:
            for i, (fn, fmt, cnt, sz) in enumerate(list(self._export_manifest)):
                desired = desired_by_idx.get(i, fn)
                src = out_dir / fn
                dst = out_dir / desired
                if desired == fn:
                    continue
                if not src.exists():
                    self._export_error = f"Rename error: missing source file '{src.name}'."
                    self._render_main()
                    return
                if dst.exists():
                    self._export_error = f"Rename error: target already exists '{dst.name}'."
                    self._render_main()
                    return
                os.rename(src, dst)
                # Update manifest entry.
                self._export_manifest[i] = (desired, fmt, cnt, sz)
            self._export_error = None
        except Exception as e:
            self._export_error = f"Rename error: {e}"

        self._render_main()

    def action_new_file(self) -> None:
        """Start a new migration (return to Select file and clear current session state)."""
        if self._export_in_progress:
            return
        # Reset most session state, but keep output_dir and user config/state.
        self.model.input_path = None
        self.model.parsed = None
        self.model.selected_folder_id = None
        self._folder_name_by_id = {}
        self._selected_route_keys.clear()
        self._selected_waypoint_keys.clear()
        self._routes_filter = ""
        self._waypoints_filter = ""
        self._export_manifest = None
        self._export_error = None
        self._rename_overrides_by_idx.clear()
        self._output_prefix = ""
        self._post_save_prompt_shown = False
        self._done_steps.clear()
        self._routes_edited = False
        self._waypoints_edited = False
        # Reinitialize the file browser directory on re-entry.
        self._file_browser_dir = None
        self._save_browser_dir = None
        self._goto("Select_file")

    def action_show_help(self) -> None:
        """Show context-sensitive help modal."""
        self.push_screen(HelpModal(step=self.step))

    def action_select_all(self) -> None:
        """Toggle select-all in the current Routes/Waypoints table (respects filter)."""
        if self.step == "Routes":
            if self.model.parsed is None or not self.model.selected_folder_id:
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            tracks = list((fd or {}).get("tracks", []) or [])
            # Visible keys (respecting filter)
            q = (self._routes_filter or "").strip().lower()
            tracks = sorted(
                tracks,
                key=lambda trk: str(getattr(trk, "title", "") or "Untitled").lower(),
            )
            visible: set[str] = set()
            for i, trk in enumerate(tracks):
                name = str(getattr(trk, "title", "") or "Untitled")
                if q and q not in name.lower():
                    continue
                visible.add(self._feature_row_key(trk, str(i)))
            if visible and visible.issubset(self._selected_route_keys):
                # All visible already selected -> deselect them.
                self._selected_route_keys.difference_update(visible)
            else:
                # Not all selected -> select everything visible.
                self._selected_route_keys.update(visible)
            self._refresh_routes_table()
        elif self.step == "Waypoints":
            if self.model.parsed is None or not self.model.selected_folder_id:
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            waypoints = list((fd or {}).get("waypoints", []) or [])
            # Visible keys (respecting filter)
            q = (self._waypoints_filter or "").strip().lower()
            waypoints = sorted(
                waypoints,
                key=lambda wp: str(getattr(wp, "title", "") or "Untitled").lower(),
            )
            visible: set[str] = set()
            for i, wp in enumerate(waypoints):
                name = str(getattr(wp, "title", "") or "Untitled")
                if q and q not in name.lower():
                    continue
                visible.add(self._feature_row_key(wp, str(i)))
            if visible and visible.issubset(self._selected_waypoint_keys):
                self._selected_waypoint_keys.difference_update(visible)
            else:
                self._selected_waypoint_keys.update(visible)
            self._refresh_waypoints_table()

    def action_map_unmapped(self) -> None:
        """Start the process of mapping unmapped CalTopo symbols to OnX icons."""
        if self.step != "List_data":
            return
        if self.model.parsed is None:
            self.push_screen(InfoModal("No data parsed yet. Select a file first."))
            return

        # Collect unmapped symbols
        unmapped = collect_unmapped_caltopo_symbols(self.model.parsed, self._config)
        if not unmapped:
            self.push_screen(InfoModal("All symbols are already mapped!", title="No Unmapped Symbols"))
            return

        # Sort by count (most common first) for efficient mapping
        sorted_unmapped = sorted(unmapped.items(), key=lambda kv: kv[1]["count"], reverse=True)
        self._unmapped_symbols = sorted_unmapped
        self._unmapped_index = 0

        # Show the first unmapped symbol modal
        self._show_next_unmapped_modal()

    def _show_next_unmapped_modal(self) -> None:
        """Show modal for the next unmapped symbol in the queue."""
        if self._unmapped_index >= len(self._unmapped_symbols):
            # All done
            self.push_screen(
                InfoModal(
                    "All symbols have been processed.\n\n"
                    "Mappings are saved to cairn_config.yaml.\n"
                    "The config has been reloaded.",
                    title="Mapping Complete"
                )
            )
            # Reload config to pick up new mappings
            self._config = load_config(None)
            # Re-render to update unmapped count
            self._render_main()
            return

        symbol, info = self._unmapped_symbols[self._unmapped_index]
        example = (info.get("examples") or [""])[0]
        count = info.get("count", 0)

        # Get fuzzy match suggestions
        all_icons = get_all_onx_icons()
        matcher = FuzzyIconMatcher(all_icons)
        suggestions = matcher.find_best_matches(symbol, top_n=5)

        self.push_screen(
            UnmappedSymbolModal(
                symbol=symbol,
                example=f"{example} ({count} waypoint{'s' if count != 1 else ''})",
                suggestions=suggestions,
                all_icons=all_icons,
                current_index=self._unmapped_index + 1,
                total_count=len(self._unmapped_symbols),
            ),
            self._on_unmapped_symbol_mapped,
        )

    def _on_unmapped_symbol_mapped(self, result: Optional[str]) -> None:
        """Handle the result of mapping an unmapped symbol."""
        if result is None:
            # User pressed Esc - cancel all remaining
            self._unmapped_symbols = []
            self._unmapped_index = 0
            return

        if result == "__skip__":
            # User skipped this symbol, move to next
            self._unmapped_index += 1
            self._show_next_unmapped_modal()
            return

        # User selected an icon - save the mapping
        symbol, _ = self._unmapped_symbols[self._unmapped_index]
        try:
            save_user_mapping(symbol, result)
        except Exception as e:
            self.push_screen(InfoModal(f"Error saving mapping: {e}", title="Error"))
            return

        # Move to next symbol
        self._unmapped_index += 1
        self._show_next_unmapped_modal()

    # -----------------------
    # Editing (TUI)
    # -----------------------
    def _decode_multiline_hint(self, value: str) -> str:
        # Match cairn/core/preview.py behavior: users type "\n" to represent newlines.
        return (value or "").replace("\\n", "\n")

    def _rgba_to_hex_nohash(self, rgba: str) -> str:
        r, g, b = ColorMapper.parse_color(rgba)
        return f"{r:02X}{g:02X}{b:02X}"

    def _rgba_to_hex_hash(self, rgba: str) -> str:
        return "#" + self._rgba_to_hex_nohash(rgba)

    def _current_folder_features(self) -> tuple[list, list]:
        """
        Returns: (tracks, waypoints) for current folder, or ([], []).
        """
        if self.model.parsed is None or not self.model.selected_folder_id:
            return ([], [])
        fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
        tracks = list((fd or {}).get("tracks", []) or [])
        waypoints = list((fd or {}).get("waypoints", []) or [])
        return tracks, waypoints

    def _feature_row_key(self, feat: object, fallback: str) -> str:
        """
        Return a stable row key for a feature.

        Prefer the parsed feature's GeoJSON `id` when present, since table display is
        sorted and indices are not stable under rename/re-sort.
        """
        try:
            fid = str(getattr(feat, "id", "") or "").strip()
            if fid:
                return fid
        except Exception:
            pass
        return str(fallback)

    def _selected_keys_for_step(self) -> Optional[EditContext]:
        if self.step == "Routes":
            if not self._selected_route_keys:
                return None
            return EditContext(kind="route", selected_keys=tuple(sorted(self._selected_route_keys)))
        if self.step == "Waypoints":
            if not self._selected_waypoint_keys:
                return None
            return EditContext(kind="waypoint", selected_keys=tuple(sorted(self._selected_waypoint_keys)))
        return None

    def _selected_features(self, ctx: EditContext) -> list:
        tracks, waypoints = self._current_folder_features()
        out: list = []

        if ctx.kind == "route":
            by_id = {self._feature_row_key(t, ""): t for t in tracks}
            sorted_tracks = sorted(tracks, key=lambda trk: str(getattr(trk, "title", "") or "Untitled").lower())
            for k in ctx.selected_keys:
                kk = str(k)
                if kk in by_id:
                    out.append(by_id[kk])
                    continue
                # Back-compat / safety: allow index-based keys if present.
                if kk.isdigit():
                    idx = int(kk)
                    if 0 <= idx < len(sorted_tracks):
                        out.append(sorted_tracks[idx])
            return out

        if ctx.kind == "waypoint":
            by_id = {self._feature_row_key(w, ""): w for w in waypoints}
            sorted_waypoints = sorted(waypoints, key=lambda wp: str(getattr(wp, "title", "") or "Untitled").lower())
            for k in ctx.selected_keys:
                kk = str(k)
                if kk in by_id:
                    out.append(by_id[kk])
                    continue
                if kk.isdigit():
                    idx = int(kk)
                    if 0 <= idx < len(sorted_waypoints):
                        out.append(sorted_waypoints[idx])
            return out

        return out


    def action_actions(self) -> None:
        # Only available on Routes/Waypoints steps.
        ctx = self._selected_keys_for_step()
        if ctx is None:
            if self.step in ("Routes", "Waypoints"):
                self.push_screen(
                    InfoModal("Select one or more items first (Space toggles selection).")
                )
            return
        # For single item, show inline overlay with current fields
        # For multiple items, show inline overlay (shows summary values)
        feats = self._selected_features(ctx)
        if not feats:
            return
        self._show_inline_overlay(ctx=ctx, feats=feats)

    def _on_inline_edit_action(self, field: object) -> None:
        """Handle field selection from inline overlay."""
        if field is None:
            # Done or Esc pressed - close editing
            self._in_single_item_edit = False
            self._in_inline_edit = False
            # Clear selection when returning to the list so nothing remains highlighted.
            try:
                if self.step == "Routes":
                    self._selected_route_keys.clear()
                    self._refresh_routes_table()
                elif self.step == "Waypoints":
                    self._selected_waypoint_keys.clear()
                    self._refresh_waypoints_table()
            except Exception:
                pass
            # Critical: restore focus to the underlying table. Otherwise focus may remain
            # on the now-hidden overlay DataTable, making the screen feel "frozen".
            try:
                self.set_focus(None)  # type: ignore[arg-type]
            except Exception:
                pass
            try:
                self.call_after_refresh(self.action_focus_table)
            except Exception:
                self.action_focus_table()
            return
        field_key = str(field or "").strip().lower()
        if field_key == "done" or field_key == "":
            self._in_single_item_edit = False
            self._in_inline_edit = False
            # Clear selection when returning to the list so nothing remains highlighted.
            try:
                if self.step == "Routes":
                    self._selected_route_keys.clear()
                    self._refresh_routes_table()
                elif self.step == "Waypoints":
                    self._selected_waypoint_keys.clear()
                    self._refresh_waypoints_table()
            except Exception:
                pass
            try:
                self.set_focus(None)  # type: ignore[arg-type]
            except Exception:
                pass
            try:
                self.call_after_refresh(self.action_focus_table)
            except Exception:
                self.action_focus_table()
            return

        ctx = self._selected_keys_for_step()
        if ctx is None:
            self._in_single_item_edit = False
            return

        # Open appropriate sub-modal for the selected field
        # After picker closes, return to inline overlay
        if field_key == "name":
            try:
                ov = self.query_one("#rename_overlay", RenameOverlay)
            except Exception:
                return
            ov.open(ctx=ctx, title="Rename")
        elif field_key == "description":
            try:
                ov = self.query_one("#description_overlay", DescriptionOverlay)
            except Exception:
                return
            ov.open(ctx=ctx)
        elif field_key == "color":
            try:
                picker = self.query_one("#color_picker_overlay", ColorPickerOverlay)
            except Exception:
                return
            if ctx.kind == "route":
                palette = [
                    (p.rgba, (p.name or "").replace("-", " ").upper())
                    for p in ColorMapper.TRACK_PALETTE
                ]
                picker.open(title="Select route color", palette=palette)
            elif ctx.kind == "waypoint":
                palette = [
                    (p.rgba, (p.name or "").replace("-", " ").upper())
                    for p in ColorMapper.WAYPOINT_PALETTE
                ]
                picker.open(title="Select waypoint color", palette=palette)
        elif field_key == "icon" and ctx.kind == "waypoint":
            try:
                picker = self.query_one("#icon_picker_overlay", IconPickerOverlay)
            except Exception:
                return
            picker.open(icons=list(get_all_onx_icons()))

    def _apply_edit_and_return_to_inline(self, payload: object) -> None:
        """Apply edit payload and return to inline overlay."""
        # Apply the edit
        self._apply_edit_payload(payload)

        # Return to inline overlay (works for both single and multiple entries)
        ctx = self._selected_keys_for_step()
        if ctx is not None:
            feats = self._selected_features(ctx)
            if feats:
                def get_route_color(feat):
                    stroke = str(getattr(feat, "stroke", "") or "")
                    if stroke:
                        return ColorMapper.map_track_color(stroke)
                    return ColorMapper.DEFAULT_TRACK_COLOR

                try:
                    overlay = self.query_one("#inline_edit_overlay", InlineEditOverlay)
                except Exception:
                    return
                overlay.open(
                    ctx=ctx,
                    features=feats,
                    get_color_chip=self._color_chip,
                    get_waypoint_icon=self._resolved_waypoint_icon,
                    get_waypoint_color=self._resolved_waypoint_color,
                    get_route_color=get_route_color,
                )

    # Legacy: previously we used an action-list modal.
    # The edit flow is now driven by the in-screen overlay (`InlineEditOverlay`), so
    # the old callback path is intentionally removed.

    def _apply_edit_payload(self, payload: object) -> None:
        """
        Apply a bulk edit coming back from a modal screen.

        payload shape:
          {"action": "...", "value": "...", "ctx": EditContext(...)}
        """
        if not isinstance(payload, dict):
            return
        action = str(payload.get("action") or "").strip().lower()
        value = payload.get("value")
        ctx = payload.get("ctx")
        if not isinstance(ctx, EditContext):
            # Defensive: older tests may pass ctx separately.
            ctx2 = self._selected_keys_for_step()
            if ctx2 is None:
                return
            ctx = ctx2

        feats = self._selected_features(ctx)
        if not feats:
            return

        changed = False

        if action == "rename":
            new_title = str(value or "").strip()
            if not new_title:
                return
            # Prompt for confirmation if changing name for multiple records
            if len(ctx.selected_keys) > 1:
                self._confirm(
                    title="Confirm Name Change",
                    message="You are changing the name for multiple records. Apply this name change to all selected records?",
                    callback=lambda confirmed, ctx=ctx, feats=feats, new_title=new_title: self._apply_rename_confirmed(
                        confirmed, ctx, feats, new_title
                    ),
                )
                return
            for f in feats:
                setattr(f, "title", new_title)
            changed = True

        elif action == "description":
            new_desc = self._decode_multiline_hint(str(value or "").strip())
            if not new_desc:
                return
            for f in feats:
                setattr(f, "description", new_desc)
            changed = True

        elif action == "color":
            rgba = str(value or "").strip()
            if not rgba:
                return
            if ctx.kind == "route":
                hex_color = self._rgba_to_hex_hash(rgba)
                for f in feats:
                    setattr(f, "stroke", hex_color)
                changed = True
            elif ctx.kind == "waypoint":
                hex_nohash = self._rgba_to_hex_nohash(rgba)
                for f in feats:
                    setattr(f, "color", hex_nohash)
                changed = True

        elif action == "icon" and ctx.kind == "waypoint":
            raw = str(value or "").strip()
            if raw == "__clear__":
                for f in feats:
                    try:
                        props = getattr(f, "properties", None)
                        if not isinstance(props, dict):
                            continue
                        props.pop("cairn_onx_icon_override", None)
                        changed = True
                    except Exception:
                        continue
            else:
                canon = normalize_onx_icon_name(raw)
                if canon is None:
                    self.push_screen(InfoModal(f"Invalid icon: {raw}"))
                    return
                for f in feats:
                    try:
                        props = getattr(f, "properties", None)
                        if not isinstance(props, dict):
                            continue
                        props["cairn_onx_icon_override"] = canon
                        changed = True
                    except Exception:
                        continue

        if not changed:
            return

        # Mark edited so we can show a hint to clear selection and edit another subset.
        if ctx.kind == "route":
            self._routes_edited = True
        elif ctx.kind == "waypoint":
            self._waypoints_edited = True

        # Refresh current step tables so edits are visible immediately.
        # Use call_after_refresh to ensure refresh happens after modal closes
        def refresh_after_modal():
            if ctx.kind == "route":
                # After applying an edit, reset selection so subsequent edits start fresh.
                # But don't clear if we're returning to inline edit modal
                if not self._in_inline_edit:
                    self._selected_route_keys.clear()
                self._refresh_routes_table()
            elif ctx.kind == "waypoint":
                # Don't clear selection if returning to inline edit
                if not self._in_inline_edit:
                    self._selected_waypoint_keys.clear()
                self._refresh_waypoints_table()
            elif self.step == "Preview":
                self._render_main()

        # Refresh tables so edits are visible immediately.
        # For modal-based edits, call_after_refresh ensures the modal is dismissed first.
        # For overlay-based edits, call_after_refresh is still safe and keeps behavior consistent.
        try:
            self.call_after_refresh(refresh_after_modal)
        except Exception:
            refresh_after_modal()

    def _apply_rename_confirmed(self, confirmed: bool, ctx: EditContext, feats: list, new_title: str) -> None:
        """Apply a multi-rename after the confirmation overlay returns."""
        if not confirmed:
            # If we were editing via overlay, return to it so user isn't stranded.
            if self._in_inline_edit:
                try:
                    feats2 = self._selected_features(ctx)
                    if feats2:
                        self._show_inline_overlay(ctx=ctx, feats=feats2)
                except Exception:
                    pass
            return

        # Apply rename to all selected features.
        for f in list(feats or []):
            try:
                setattr(f, "title", str(new_title))
                # Best-effort keep properties in sync for ParsedFeature
                props = getattr(f, "properties", None)
                if isinstance(props, dict):
                    props["title"] = str(new_title)
            except Exception:
                continue

        # Mark edited + refresh table.
        if ctx.kind == "route":
            self._routes_edited = True
        elif ctx.kind == "waypoint":
            self._waypoints_edited = True

        def refresh_after_confirm():
            if ctx.kind == "route":
                self._refresh_routes_table()
            elif ctx.kind == "waypoint":
                self._refresh_waypoints_table()

        try:
            self.call_after_refresh(refresh_after_confirm)
        except Exception:
            refresh_after_confirm()

        # Return to inline overlay if applicable (keeps multi-edit workflow smooth).
        if self._in_inline_edit:
            try:
                feats2 = self._selected_features(ctx)
                if feats2:
                    self._show_inline_overlay(ctx=ctx, feats=feats2)
            except Exception:
                pass

    # -----------------------
    # Rendering
    # -----------------------
    def _render_sidebar(self) -> None:
        stepper = self.query_one("#stepper", Stepper)
        stepper.set_state(current=self.step, done=self._done_steps)

        status = self.query_one("#status", Static)
        parts = []
        if self.model.input_path:
            parts.append(f"Input: {self.model.input_path.name}")
        if self.model.parsed:
            folder_count = len(getattr(self.model.parsed, "folders", {}) or {})
            wp = sum(
                len((f or {}).get("waypoints", []) or [])
                for f in (getattr(self.model.parsed, "folders", {}) or {}).values()
            )
            trk = sum(
                len((f or {}).get("tracks", []) or [])
                for f in (getattr(self.model.parsed, "folders", {}) or {}).values()
            )
            parts.append(f"Folders: {folder_count}  Waypoints: {wp}  Routes: {trk}")
        status.update("\n".join(parts))

        # Step-specific left-column guidance
        try:
            instr = self.query_one("#sidebar_instructions", Static)
            instr.update(self._sidebar_instructions(self.step))
        except Exception:
            pass
        try:
            sc = self.query_one("#sidebar_shortcuts", Static)
            sc.update(self._sidebar_shortcuts(self.step))
        except Exception:
            pass

    def _sidebar_instructions(self, step: str) -> str:
        """Concise, process-oriented guidance shown in the left column per step."""
        step = str(step or "")
        if step == "Select_file":
            return (
                "Choose the CalTopo export you want to migrate to onX.\n"
                "GeoJSON preserves the most detail, but GPX/KML are also supported."
            )
        if step == "List_data":
            return (
                "Review everything found in your export: folders, routes, waypoints, tracks, "
                "shapes, and unmapped symbols.\n\n"
                "onX does not support folders, so this is a good time to bake folder structure "
                "into names/descriptions so you can find items via onX search."
            )
        if step == "Folder":
            return (
                "Pick what you want to edit next.\n"
                "If multiple folders exist, select the ones you want to process."
            )
        if step in {"Routes", "Waypoints"}:
            return (
                "Update the name, description, and color so it’s meaningful once imported.\n"
                "Use selection shortcuts to bulk-update or quickly scan large sets."
            )
        if step == "Preview":
            return (
                "Confirm the mapping data you want to import into onX.\n"
                "If you need to make changes, press Esc to go back."
            )
        if step == "Save":
            return (
                "Choose where to save the GPX output and optionally edit the suggested filename.\n"
                "If the export must be split to stay under 4 MB, each file will be listed with "
                "an editable name and a short explanation."
            )
        return ""

    def _sidebar_shortcuts(self, step: str) -> str:
        """Always-visible shortcut list (mirrors the footer, but formatted for the sidebar)."""
        shortcuts = StepAwareFooter.STEP_SHORTCUTS.get(step, [])
        if not shortcuts:
            return ""
        return "\n".join([f"{key}: {desc}" for key, desc in shortcuts])

    def _suggest_output_name(self, original_filename: str) -> str:
        """
        Suggest a rename target for an output file, based on the current output prefix.

        We keep this intentionally conservative (same extension, no directory components).
        """
        fn = str(original_filename or "").strip()
        if not fn:
            return fn
        prefix = sanitize_filename(str(self._output_prefix or "").strip())
        if not prefix:
            return Path(fn).name
        p = Path(fn)
        stem = p.stem or "output"
        ext = p.suffix
        return f"{prefix}_{stem}{ext}"

    def _clear_main_body(self) -> Container:
        body = self.query_one("#main_body", Container)
        # Important: in some Textual versions, remove_children() alone may leave
        # widget IDs registered briefly, causing DuplicateIds when we re-mount a
        # new widget with the same id during a rapid re-render (e.g. Save step).
        #
        # Using Widget.remove() ensures widgets are properly unmounted and IDs
        # are released.
        try:
            for child in list(getattr(body, "children", ())):
                try:
                    child.remove()
                except Exception:
                    pass
        except Exception:
            # Fall back to the simple approach.
            body.remove_children()
        return body

    def _render_main(self) -> None:
        # Render errors should never hard-crash the app in debug mode; capture and surface.
        try:
            title = self.query_one("#main_title", Static)
            subtitle = self.query_one("#main_subtitle", Static)
        except Exception as e:
            self._dbg(event="render.error", data={"where": "query_title", "err": str(e)})
            return

        if self.step == "Select_file":
            title.update("Select file")
            subtitle.update("Choose an input file (.json/.geojson/.kml/.gpx)")
            body = self._clear_main_body()
            default_root = Path(self._state.default_root).expanduser() if self._state.default_root else Path.cwd()
            body.mount(Static("Pick a file:", classes="muted"))
            # Initialize file browser directory once per visit.
            if self._file_browser_dir is None:
                try:
                    self._file_browser_dir = default_root.resolve()
                except Exception:
                    self._file_browser_dir = default_root

            # Simple in-app file browser: dirs + allowed extensions only.
            table = DataTable(id="file_browser")
            table.add_columns("Name", "Type")
            body.mount(table)
            self._refresh_file_browser()
            body.mount(Static("Enter: open/select", classes="muted"))
            # Prefer focusing the tree so arrow keys + Enter work immediately.
            try:
                self.call_after_refresh(table.focus)
            except Exception:
                pass
            return

        if self.step == "List_data":
            title.update("Summary of mapping data")
            subtitle.update("Parsed counts and summary")
            body = self._clear_main_body()
            if not self.model.input_path:
                body.mount(Static("No input selected. Go back.", classes="err"))
                return
            if self.model.parsed is None:
                try:
                    self.model.parsed = parse_geojson(self.model.input_path)
                except Exception as e:
                    body.mount(Static(f"Parse error: {e}", classes="err"))
                    return

            # Informational header before the first list view
            if self.model.input_path:
                body.mount(Static(f"Loaded: {self.model.input_path.name}", classes="accent"))
                body.mount(Static(""))

            folders = getattr(self.model.parsed, "folders", {}) or {}
            self._folder_name_by_id = {
                fid: str((fd or {}).get("name") or fid) for fid, fd in folders.items()
            }
            folder_count = len(folders)
            wp = sum(len((f or {}).get("waypoints", []) or []) for f in folders.values())
            trk = sum(len((f or {}).get("tracks", []) or []) for f in folders.values())
            shp = sum(len((f or {}).get("shapes", []) or []) for f in folders.values())
            body.mount(Static(f"Folders: {folder_count}", classes="ok"))
            body.mount(Static(f"Waypoints: {wp}", classes="ok"))
            body.mount(Static(f"Routes: {trk}", classes="ok"))
            body.mount(Static(f"Shapes: {shp}", classes="ok"))

            unmapped = collect_unmapped_caltopo_symbols(self.model.parsed, self._config)
            if unmapped:
                body.mount(Static(f"Unmapped symbols: {len(unmapped)}", classes="warn"))
                # Show top few by count.
                top = sorted(unmapped.items(), key=lambda kv: kv[1]["count"], reverse=True)[:6]
                for sym, info in top:
                    ex = (info.get("examples") or [""])[0]
                    body.mount(Static(f"  - {sym} ({info['count']}): {ex}", classes="muted"))
                body.mount(Static(""))  # spacer
                body.mount(Static("Press [bold]m[/] to map these symbols now, or Enter to continue.", classes="muted"))
            else:
                body.mount(Static("Unmapped symbols: 0", classes="ok"))
                body.mount(Static("Press Enter to continue.", classes="muted"))
            return

        if self.step == "Folder":
            folders = list((getattr(self.model.parsed, "folders", {}) or {}).items())
            if len(folders) > 1:
                title.update("Select folder to edit")
                subtitle.update("Space to toggle selection, Enter to process selected folders")
            else:
                title.update("Folder")
                subtitle.update("Pick a folder to inspect routes/waypoints")
            body = self._clear_main_body()
            if self.model.parsed is None:
                body.mount(Static("No parsed data. Go back.", classes="err"))
                return
            if not folders:
                body.mount(Static("No folders found.", classes="err"))
                return
            table = DataTable(id="folder_table")
            if len(folders) > 1:
                table.add_columns("Selected", "Folder", "Waypoints", "Routes", "Shapes")
            else:
                table.add_columns("Folder", "Waypoints", "Routes", "Shapes")
            # Sort folders alphabetically
            folders = sorted(folders, key=lambda x: str((x[1] or {}).get("name") or x[0]).lower())
            for folder_id, fd in folders:
                name = str((fd or {}).get("name") or folder_id)
                w = len((fd or {}).get("waypoints", []) or [])
                t = len((fd or {}).get("tracks", []) or [])
                s = len((fd or {}).get("shapes", []) or [])
                if len(folders) > 1:
                    sel = "●" if folder_id in self._selected_folders else " "
                    table.add_row(sel, name, str(w), str(t), str(s), key=folder_id)
                else:
                    table.add_row(name, str(w), str(t), str(s), key=folder_id)
            body.mount(table)
            if len(folders) > 1:
                body.mount(Static("Space: toggle select  Enter: process selected folders", classes="muted"))
            else:
                body.mount(Static("Use arrows to highlight. Enter: continue", classes="muted"))
            return

        if self.step == "Routes":
            title.update("Routes")
            folder_name = ""
            try:
                if self.model.selected_folder_id:
                    folder_name = self._folder_name_by_id.get(self.model.selected_folder_id, self.model.selected_folder_id)
            except Exception:
                folder_name = ""
            subtitle_msg = "Browse routes (Space to toggle selection, / to search)  •  Edit: a"
            if self._routes_edited:
                subtitle_msg += "  •  Edited. Press x to clear selection and edit another set."
            if folder_name:
                subtitle_msg = f"Folder: {folder_name}  •  {subtitle_msg}"
            subtitle.update(subtitle_msg)
            body = self._clear_main_body()
            if self.model.parsed is None or not self.model.selected_folder_id:
                body.mount(Static("No folder selected. Go back.", classes="err"))
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            tracks = list((fd or {}).get("tracks", []) or [])
            # Sort routes alphabetically by name (case-insensitive)
            tracks = sorted(tracks, key=lambda trk: str(getattr(trk, "title", "") or "Untitled").lower())
            body.mount(Input(placeholder="Filter routes…", id="routes_search"))
            table = DataTable(id="routes_table")
            table.add_columns("Selected", "Name", "Color", "Pattern", "Width")
            q = (self._routes_filter or "").strip().lower()
            for i, trk in enumerate(tracks):
                name = str(getattr(trk, "title", "") or "Untitled")
                if q and q not in name.lower():
                    continue
                key = self._feature_row_key(trk, str(i))
                sel = "●" if key in self._selected_route_keys else " "
                rgba = ColorMapper.map_track_color(str(getattr(trk, "stroke", "") or ""))
                table.add_row(
                    sel,
                    name,
                    self._color_chip(rgba),
                    str(getattr(trk, "pattern", "") or ""),
                    str(getattr(trk, "stroke_width", "") or ""),
                    key=key,
                )
            body.mount(table)
            body.mount(Static("Space: toggle select  /: filter  t: focus table  Enter: continue", classes="muted"))
            try:
                self.call_after_refresh(table.focus)
            except Exception:
                pass
            return

        if self.step == "Waypoints":
            title.update("Waypoints")
            folder_name = ""
            try:
                if self.model.selected_folder_id:
                    folder_name = self._folder_name_by_id.get(self.model.selected_folder_id, self.model.selected_folder_id)
            except Exception:
                folder_name = ""
            subtitle_msg = "Browse waypoints (Space to toggle selection, / to search)  •  Edit: a"
            if self._waypoints_edited:
                subtitle_msg += "  •  Edited. Press x to clear selection and edit another set."
            if folder_name:
                subtitle_msg = f"Folder: {folder_name}  •  {subtitle_msg}"
            subtitle.update(subtitle_msg)
            body = self._clear_main_body()
            if self.model.parsed is None or not self.model.selected_folder_id:
                body.mount(Static("No folder selected. Go back.", classes="err"))
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            waypoints = list((fd or {}).get("waypoints", []) or [])
            # Sort waypoints alphabetically by name (case-insensitive)
            waypoints = sorted(waypoints, key=lambda wp: str(getattr(wp, "title", "") or "Untitled").lower())
            body.mount(Input(placeholder="Filter waypoints…", id="waypoints_search"))
            table = DataTable(id="waypoints_table")
            table.add_columns("Selected", "Name", "OnX icon", "OnX color")

            q = (self._waypoints_filter or "").strip().lower()
            for i, wp in enumerate(waypoints):
                key = self._feature_row_key(wp, str(i))
                sel = "●" if key in self._selected_waypoint_keys else " "
                title0 = str(getattr(wp, "title", "") or "Untitled")
                if q and q not in title0.lower():
                    continue
                mapped = self._resolved_waypoint_icon(wp)
                rgba = self._resolved_waypoint_color(wp, mapped)
                try:
                    table.add_row(sel, title0, mapped, self._color_chip(rgba), key=key)
                except Exception as e:
                    # Some Textual versions are picky about cell renderables; fall back to plain text.
                    self._dbg(
                        event="waypoints.table.add_row_error",
                        data={"err": str(e), "rgba": rgba, "name": title0},
                    )
                    name = ColorMapper.get_color_name(rgba).replace("-", " ").upper()
                    table.add_row(sel, title0, mapped, f"■ {name}", key=key)
            body.mount(table)
            body.mount(Static("Space: toggle select  /: filter  t: focus table  Enter: continue", classes="muted"))
            try:
                self.call_after_refresh(table.focus)
            except Exception:
                pass
            return

        if self.step == "Preview":
            title.update("Preview")
            subtitle.update("Preview of the full export (all routes + waypoints)")
            body = self._clear_main_body()
            if self.model.parsed is None:
                body.mount(Static("No parsed data. Go back.", classes="err"))
                return

            # Collect all items from all folders (for multi-folder projects)
            folders = getattr(self.model.parsed, "folders", {}) or {}
            all_tracks = []
            all_waypoints = []

            if self._folders_to_process:
                # Multi-folder: collect from selected folders
                try:
                    names = [
                        str(self._folder_name_by_id.get(fid, fid))
                        for fid in (self._folders_to_process or [])
                    ]
                    if names:
                        shown = ", ".join(names[:3])
                        if len(names) > 3:
                            shown += f" (+{len(names) - 3} more)"
                        body.mount(Static(f"Folders: {shown}", classes="ok"))
                except Exception:
                    pass
                for fid in self._folders_to_process:
                    fd = folders.get(fid) or {}
                    all_tracks.extend(fd.get("tracks", []) or [])
                    all_waypoints.extend(fd.get("waypoints", []) or [])
            else:
                # Single folder: use current folder
                fid = self.model.selected_folder_id
                if not fid:
                    body.mount(Static("No folder selected. Go back.", classes="err"))
                    return
                fd = folders.get(fid) or {}
                all_tracks = list(fd.get("tracks", []) or [])
                all_waypoints = list(fd.get("waypoints", []) or [])
                folder_name = self._folder_name_by_id.get(fid, fid)
                body.mount(Static(f"Folder: {folder_name}", classes="ok"))

            # Sort all items alphabetically
            tracks = sorted(all_tracks, key=lambda trk: str(getattr(trk, "title", "") or "Untitled").lower())
            waypoints = sorted(all_waypoints, key=lambda wp: str(getattr(wp, "title", "") or "Untitled").lower())

            # Waypoint preview table (full export, capped for UI readability).
            wp_table = DataTable(id="preview_waypoints")
            wp_table.add_columns("Name", "OnX icon", "OnX color")
            max_rows = 50
            for i, wp in enumerate(waypoints[:max_rows]):
                name0 = str(getattr(wp, "title", "") or "Untitled")
                icon = self._resolved_waypoint_icon(wp)
                rgba = self._resolved_waypoint_color(wp, icon)
                try:
                    wp_table.add_row(name0, icon, self._color_chip(rgba))
                except Exception as e:
                    self._dbg(event="preview.wp_row_error", data={"err": str(e), "rgba": rgba})
                    wp_table.add_row(name0, icon, f"■ {ColorMapper.get_color_name(rgba).replace('-', ' ').upper()}")
            note_wp = f"Waypoints ({len(waypoints)})"
            if len(waypoints) > max_rows:
                note_wp += f" [dim](showing first {max_rows})[/]"
            body.mount(Static(note_wp, classes="accent"))
            body.mount(wp_table)

            trk_table = DataTable(id="preview_routes")
            trk_table.add_columns("Name", "OnX color", "Style", "Weight")
            for i, trk in enumerate(tracks[:max_rows]):
                name0 = str(getattr(trk, "title", "") or "Untitled")
                rgba = ColorMapper.map_track_color(str(getattr(trk, "stroke", "") or ""))
                style = str(getattr(trk, "pattern", "") or "solid")
                weight = str(getattr(trk, "stroke_width", "") or "")
                try:
                    trk_table.add_row(name0, self._color_chip(rgba), style, weight)
                except Exception as e:
                    self._dbg(event="preview.trk_row_error", data={"err": str(e), "rgba": rgba})
                    trk_table.add_row(
                        name0,
                        f"■ {ColorMapper.get_color_name(rgba).replace('-', ' ').upper()}",
                        style,
                        weight,
                    )
            note_trk = f"Routes ({len(tracks)})"
            if len(tracks) > max_rows:
                note_trk += f" [dim](showing first {max_rows})[/]"
            body.mount(Static(note_trk, classes="accent"))
            body.mount(trk_table)

            body.mount(Static("Enter to continue to Save", classes="muted"))
            # Ensure app-level keys (Enter/q) work reliably even if a DataTable would grab focus.
            try:
                self.call_after_refresh(lambda: self.set_focus(None))  # type: ignore[arg-type]
            except Exception:
                try:
                    self.set_focus(None)  # type: ignore[arg-type]
                except Exception:
                    pass
            return

        if self.step == "Save":
            title.update("Save")
            subtitle.update("Choose output directory and export")
            body = self._clear_main_body()

            # Initialize save browser directory once per visit.
            if self._save_browser_dir is None:
                try:
                    self._save_browser_dir = (self.model.output_dir or Path.cwd()).expanduser().resolve()
                except Exception:
                    self._save_browser_dir = self.model.output_dir or Path.cwd()

            try:
                body.mount(Static(f"Browse output folder: {self._save_browser_dir}", classes="muted"))
            except Exception:
                body.mount(Static("Browse output folder:", classes="muted"))

            save_tbl = DataTable(id="save_browser")
            save_tbl.add_columns("Name", "Type")
            body.mount(save_tbl)
            self._refresh_save_browser()

            # Output directory (selected): chosen via browser only (no manual path entry).
            out_default = self.model.output_dir or (Path.cwd() / "onx_ready")
            body.mount(Static(f"Output folder: {out_default}", classes="muted"))

            # Default prefix: input file stem (sanitized), if available.
            if not (self._output_prefix or "").strip():
                try:
                    if self.model.input_path:
                        self._output_prefix = sanitize_filename(self.model.input_path.stem)
                except Exception:
                    pass
            prefix_inp = Input(
                placeholder="Output filename prefix (optional)",
                id="output_prefix",
            )
            try:
                prefix_inp.value = str(self._output_prefix or "")
            except Exception:
                pass
            body.mount(prefix_inp)

            if self._export_in_progress:
                body.mount(Static("Exporting… (please wait)", classes="accent"))
            if self._export_error:
                body.mount(Static(self._export_error, classes="err"))

            if self._export_manifest:
                # Detect split parts so we can explain why multiple files exist.
                split_base_counts: dict[str, int] = {}
                for fn, fmt, cnt, sz in self._export_manifest:
                    p = Path(fn)
                    m = re.match(r"^(?P<base>.+)_(?P<num>\d+)$", p.stem)
                    if m:
                        base = f"{m.group('base')}{p.suffix.lower()}"
                        split_base_counts[base] = split_base_counts.get(base, 0) + 1

                tbl = DataTable(id="manifest")
                tbl.add_columns("File", "Format", "Items", "Bytes", "Note")
                for fn, fmt, cnt, sz in self._export_manifest:
                    note = ""
                    p = Path(fn)
                    m = re.match(r"^(?P<base>.+)_(?P<num>\d+)$", p.stem)
                    if m:
                        base = f"{m.group('base')}{p.suffix.lower()}"
                        if split_base_counts.get(base, 0) > 1:
                            note = "Split (4 MB limit)"
                    tbl.add_row(fn, fmt, str(cnt), str(sz), note)
                body.mount(Static("Export manifest", classes="accent"))
                body.mount(tbl)

                if any(v > 1 for v in split_base_counts.values()):
                    body.mount(
                        Static(
                            "Some GPX outputs were split to stay under the 4 MB onX import limit.",
                            classes="muted",
                        )
                    )

                body.mount(Static("Rename outputs (optional): edit names below, then press [bold]r[/] to apply.", classes="muted"))
                # One input per output file, keyed by manifest index.
                for i, (fn, fmt, cnt, sz) in enumerate(self._export_manifest):
                    row = Horizontal()
                    body.mount(row)
                    try:
                        row.mount(Static(fn, classes="muted"))
                    except Exception:
                        row.mount(Static(str(fn), classes="muted"))
                    inp = Input(placeholder="New filename", id=f"rename_{i}")
                    desired = self._rename_overrides_by_idx.get(i)
                    if desired is None:
                        desired = self._suggest_output_name(fn)
                        self._rename_overrides_by_idx[i] = desired
                    try:
                        inp.value = desired
                    except Exception:
                        pass
                    row.mount(inp)

                body.mount(Static("Done. Press [bold]n[/] to migrate another file, or [bold]q[/] to quit.", classes="muted"))
            else:
                body.mount(Static("Select [bold][Export][/] and press Enter (Confirm Export will appear).", classes="muted"))
            return

    # -----------------------
    # Events
    # -----------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "output_prefix":
            self._output_prefix = str(event.value or "")
            # Re-render to update suggested rename defaults (if any).
            self._render_sidebar()
            if self.step == "Save":
                self._render_main()
        elif str(event.input.id or "").startswith("rename_"):
            # Persist edited rename values (used when applying renames with 'r').
            try:
                idx = int(str(event.input.id).split("_", 1)[1])
            except Exception:
                idx = None
            if idx is not None:
                self._rename_overrides_by_idx[idx] = str(event.value or "")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "save_browser":
            # Save browser should be fully operable via Enter even if DataTable consumes Key events.
            if self.step != "Save":
                return
            try:
                self._save_browser_enter()
                try:
                    event.stop()
                except Exception:
                    pass
            except Exception:
                return
            return

        if event.data_table.id == "folder_table":
            try:
                folder_id = str(event.row_key.value)
            except Exception:
                folder_id = None

            # In multi-folder mode, clicking a row should NOT set selected_folder_id
            # or trigger navigation - only Spacebar should toggle selection
            folders = getattr(self.model.parsed, "folders", {}) or {}
            if len(folders) > 1:
                # Multi-folder mode: don't set selected_folder_id on row selection
                # This prevents accidental navigation when clicking rows
                return

            # Single folder mode: set selected_folder_id (existing behavior)
            if folder_id:
                self.model.selected_folder_id = folder_id
            else:
                self.model.selected_folder_id = None
            self._dbg(
                event="folder.row_selected",
                data={"folder_id": self.model.selected_folder_id},
            )

    def action_focus_search(self) -> None:
        # Best-effort: focus the search/filter input on the current screen (including modals).
        try:
            if self.step == "Routes":
                self.query_one("#routes_search", Input).focus()
                return
            if self.step == "Waypoints":
                self.query_one("#waypoints_search", Input).focus()
                return
        except Exception:
            pass

        # Modals (icon/color pickers) use different IDs.
        try:
            self.screen.query_one("#icon_search", Input).focus()
            return
        except Exception:
            pass
        try:
            self.screen.query_one("#color_search", Input).focus()
            return
        except Exception:
            pass

    # (EditMoreModal prompts removed; selection workflow is handled via 'x' to clear selection.)

    def action_focus_table(self) -> None:
        """Focus the main table for the current step (so Space toggles selection)."""
        try:
            if self.step == "Select_file":
                self.query_one("#file_browser", DataTable).focus()
            elif self.step == "Folder":
                self.query_one("#folder_table", DataTable).focus()
            elif self.step == "Routes":
                tbl = self.query_one("#routes_table", DataTable)
                tbl.focus()
            elif self.step == "Waypoints":
                tbl = self.query_one("#waypoints_table", DataTable)
                tbl.focus()
            elif self.step == "Save":
                self.query_one("#save_browser", DataTable).focus()
        except Exception as e:
            return

    def action_clear_selection(self) -> None:
        """Clear selection for the current selection step (Routes/Waypoints)."""
        try:
            if self.step == "Routes":
                self._selected_route_keys.clear()
                self._routes_edited = False
                self._refresh_routes_table()
                return
            if self.step == "Waypoints":
                self._selected_waypoint_keys.clear()
                self._waypoints_edited = False
                self._refresh_waypoints_table()
                return
        except Exception:
            return

    def on_key(self, event) -> None:  # type: ignore[override]
        # Debug: capture keys when enabled (useful for diagnosing "Enter doesn't advance").
        self._dbg(
            event="key",
            data={
                "key": str(getattr(event, "key", "")),
                "character": str(getattr(event, "character", "")),
                "step": str(getattr(self, "step", "")),
                "focused": {
                    "type": type(self.focused).__name__ if self.focused else None,
                    "id": getattr(self.focused, "id", None) if self.focused else None,
                },
            },
        )

        # IMPORTANT: When a modal or overlay is open (editing dialogs), let it handle
        # Enter/Escape/etc. Otherwise our global step-navigation hijacks Enter and
        # makes dialogs unusable.
        try:
            from textual.screen import ModalScreen

            if isinstance(getattr(self, "screen", None), ModalScreen):
                return
        except Exception:
            pass

        # In-screen overlays are Widgets (not Screens), so guard explicitly.
        def _overlay_open(selector: str) -> bool:
            try:
                w = self.query_one(selector)
                return bool(getattr(w, "has_class", lambda _c: False)("open"))
            except Exception:
                return False

        # Special handling: picker overlays focus a DataTable, which can consume Enter/Up/Down
        # such that the overlay container never sees the Key event. Handle those here.
        if _overlay_open("#icon_picker_overlay"):
            key = str(getattr(event, "key", "") or "")
            focused_id = getattr(getattr(self, "focused", None), "id", None)
            try:
                tbl = self.query_one("#icon_table", DataTable)
            except Exception:
                tbl = None
            # IMPORTANT: Avoid double-moving the cursor. When the DataTable is focused,
            # it will already handle Up/Down. We only forward arrows when focus is on
            # a non-table widget (e.g. the filter input).
            if key in ("up", "down") and tbl is not None and focused_id != "icon_table":
                try:
                    (tbl.action_cursor_down() if key == "down" else tbl.action_cursor_up())  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    event.stop()
                except Exception:
                    pass
                return
            if key == "escape":
                try:
                    self.query_one("#icon_picker_overlay", IconPickerOverlay).close()
                except Exception:
                    pass
                try:
                    self.on_icon_picker_overlay_icon_picked(IconPickerOverlay.IconPicked(None))  # type: ignore[arg-type]
                except Exception:
                    pass
                try:
                    event.stop()
                except Exception:
                    pass
                return
            if key in ("enter", "return") or getattr(event, "character", None) == "\r":
                icon = None
                if tbl is not None:
                    icon = (self._table_cursor_row_key(tbl) or "").strip() or None
                try:
                    self.query_one("#icon_picker_overlay", IconPickerOverlay).close()
                except Exception:
                    pass
                try:
                    self.on_icon_picker_overlay_icon_picked(IconPickerOverlay.IconPicked(icon))  # type: ignore[arg-type]
                except Exception:
                    pass
                try:
                    event.stop()
                except Exception:
                    pass
                return
            return

        if _overlay_open("#color_picker_overlay"):
            key = str(getattr(event, "key", "") or "")
            focused_id = getattr(getattr(self, "focused", None), "id", None)
            try:
                tbl = self.query_one("#palette_table", DataTable)
            except Exception:
                tbl = None
            # IMPORTANT: Avoid double-moving the cursor. When the DataTable is focused,
            # it will already handle Up/Down. We only forward arrows when focus is on
            # a non-table widget (e.g. the filter input).
            if key in ("up", "down") and tbl is not None and focused_id != "palette_table":
                try:
                    (tbl.action_cursor_down() if key == "down" else tbl.action_cursor_up())  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    event.stop()
                except Exception:
                    pass
                return
            if key == "escape":
                try:
                    self.query_one("#color_picker_overlay", ColorPickerOverlay).close()
                except Exception:
                    pass
                try:
                    self.on_color_picker_overlay_color_picked(ColorPickerOverlay.ColorPicked(None))  # type: ignore[arg-type]
                except Exception:
                    pass
                try:
                    event.stop()
                except Exception:
                    pass
                return
            if key in ("enter", "return") or getattr(event, "character", None) == "\r":
                rgba = None
                if tbl is not None:
                    rgba = (self._table_cursor_row_key(tbl) or "").strip() or None
                try:
                    self.query_one("#color_picker_overlay", ColorPickerOverlay).close()
                except Exception:
                    pass
                try:
                    self.on_color_picker_overlay_color_picked(ColorPickerOverlay.ColorPicked(rgba))  # type: ignore[arg-type]
                except Exception:
                    pass
                try:
                    event.stop()
                except Exception:
                    pass
                return
            return

        if (
            _overlay_open("#inline_edit_overlay")
            or _overlay_open("#rename_overlay")
            or _overlay_open("#description_overlay")
            or _overlay_open("#confirm_overlay")
        ):
            return

        # Handle ? for help (works from anywhere)
        if event.key == "question_mark" or getattr(event, "character", None) == "?":
            self.action_show_help()
            try:
                event.stop()
            except Exception:
                pass
            return

        # Make navigation reliable regardless of focused widget.
        # Some widgets may consume Enter/Escape depending on focus state.
        if event.key == "escape":
            self.action_back()
            try:
                event.stop()
            except Exception:
                pass
            return

        # Special-case: Select_file file browser (Enter opens dir/selects file).
        if self.step == "Select_file":
            try:
                focused_id = getattr(getattr(self, "focused", None), "id", None)
                if focused_id == "file_browser" and (
                    event.key in ("enter", "return") or getattr(event, "character", None) == "\r"
                ):
                    self._file_browser_enter()
                    try:
                        event.stop()
                    except Exception:
                        pass
                    return
            except Exception:
                pass

        # Special-case: Save output dir browser (Enter navigates/selects folder).
        if self.step == "Save":
            try:
                focused_id = getattr(getattr(self, "focused", None), "id", None)
                if focused_id == "save_browser" and (
                    event.key in ("enter", "return") or getattr(event, "character", None) == "\r"
                ):
                    self._save_browser_enter()
                    try:
                        event.stop()
                    except Exception:
                        pass
                    return
            except Exception:
                pass

        # Accept common Enter variants across terminals/backends.
        if event.key in ("enter", "return") or getattr(event, "character", None) == "\r":
            self.action_continue()
            try:
                event.stop()
            except Exception:
                pass
            return

        # Toggle selection in tables with Space (when table is focused).
        if event.key != "space":
            return
        try:
            focused = {"type": type(self.focused).__name__ if self.focused else None, "id": getattr(self.focused, "id", None) if self.focused else None}

            # If an Input is focused, let Space behave normally (type a space).
            if focused.get("type") == "Input":
                return

            if self.step == "Folder":
                # Toggle folder selection for multi-folder workflow
                table = self.query_one("#folder_table", DataTable)
                rk = self._table_cursor_row_key(table)
                if rk:
                    folder_id = str(rk)
                    if folder_id in self._selected_folders:
                        self._selected_folders.remove(folder_id)
                    else:
                        self._selected_folders.add(folder_id)
                    # Save the row key before refresh
                    saved_row_key = rk
                    # Refresh just the table - it returns the target cursor index
                    target_index = self._refresh_folder_table()

                    # Restore cursor position - use multiple strategies to ensure it sticks
                    if target_index is not None:
                        def restore_cursor():
                            try:
                                table_refreshed = self.query_one("#folder_table", DataTable)
                                current_cursor = getattr(table_refreshed, "cursor_row", None)
                                if current_cursor != target_index:
                                    # Ensure table has focus first
                                    try:
                                        table_refreshed.focus()
                                    except Exception:
                                        pass

                                    # Since cursor_row has no setter, we need to use action methods
                                    # But we need to move from current position to target
                                    # The issue is current_cursor might be wrong, so let's move from 0
                                    try:
                                        # First, move to top (row 0) to establish known position
                                        # Then move down to target
                                        current_pos = current_cursor or 0

                                        # If we're not at the top, move to top first
                                        if current_pos > 0:
                                            for _ in range(current_pos):
                                                try:
                                                    table_refreshed.action_cursor_up()  # type: ignore[attr-defined]
                                                except Exception:
                                                    break

                                        # Now move down to target from row 0
                                        for _ in range(target_index):
                                            try:
                                                table_refreshed.action_cursor_down()  # type: ignore[attr-defined]
                                            except Exception:
                                                break
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                        # Try multiple approaches to ensure cursor is set
                        # 1. Immediate set (might get reset)
                        try:
                            table.cursor_row = target_index  # type: ignore[attr-defined]
                        except Exception:
                            pass

                        # 2. After refresh callback (primary method)
                        try:
                            self.call_after_refresh(restore_cursor)
                        except Exception:
                            restore_cursor()

                        # 3. Timer-based fallback with multiple attempts
                        try:
                            def timer_restore():
                                restore_cursor()
                                # Try again after a longer delay
                                try:
                                    self.set_timer(0.2, restore_cursor, name="restore_folder_cursor_retry")
                                except Exception:
                                    pass
                            self.set_timer(0.05, timer_restore, name="restore_folder_cursor")
                        except Exception:
                            pass
                return

            if self.step == "Routes":
                table = self.query_one("#routes_table", DataTable)
                rk = self._table_cursor_row_key(table)
                idx = int(getattr(table, "cursor_row", 0) or 0)
                # Prefer row key so selection works when filtered.
                k = rk if rk is not None else str(idx)
                if k in self._selected_route_keys:
                    self._selected_route_keys.remove(k)
                else:
                    self._selected_route_keys.add(k)

                # Save target index before refresh
                target_index = idx

                self._refresh_routes_table()

                # Restore cursor position using action methods (cursor_row is read-only)
                # Find target index by key after refresh (in case filtering changed visible rows)
                def restore_routes_cursor():
                    try:
                        table_refreshed = self.query_one("#routes_table", DataTable)
                        table_refreshed.focus()

                        # Find the row index for the saved key after refresh
                        target_idx = None
                        if rk is not None:
                            # Try to find row by key
                            try:
                                row_count = getattr(table_refreshed, "row_count", 0) or 0
                                for i in range(row_count):
                                    try:
                                        row_key = table_refreshed.get_row_key(i)  # type: ignore[attr-defined]
                                        if str(row_key) == str(rk):
                                            target_idx = i
                                            break
                                    except Exception:
                                        continue
                            except Exception:
                                pass

                        # Fallback to saved index if key lookup failed
                        if target_idx is None:
                            target_idx = target_index

                        current_pos = getattr(table_refreshed, "cursor_row", 0) or 0

                        # Move to row 0 first (known position)
                        if current_pos > 0:
                            for _ in range(current_pos):
                                try:
                                    table_refreshed.action_cursor_up()  # type: ignore[attr-defined]
                                except Exception:
                                    break

                        # Then move down to target
                        for _ in range(target_idx):
                            try:
                                table_refreshed.action_cursor_down()  # type: ignore[attr-defined]
                            except Exception:
                                break
                    except Exception:
                        pass

                try:
                    self.call_after_refresh(restore_routes_cursor)
                except Exception:
                    restore_routes_cursor()

                # Timer fallback
                try:
                    self.set_timer(0.05, restore_routes_cursor, name="restore_routes_cursor")
                except Exception:
                    pass
            elif self.step == "Waypoints":
                table = self.query_one("#waypoints_table", DataTable)
                rk = self._table_cursor_row_key(table)
                idx = int(getattr(table, "cursor_row", 0) or 0)
                k = rk if rk is not None else str(idx)
                if k in self._selected_waypoint_keys:
                    self._selected_waypoint_keys.remove(k)
                else:
                    self._selected_waypoint_keys.add(k)

                # Save target index before refresh
                target_index = idx

                self._refresh_waypoints_table()

                # Restore cursor position using action methods (cursor_row is read-only)
                # Find target index by key after refresh (in case filtering changed visible rows)
                def restore_waypoints_cursor():
                    try:
                        table_refreshed = self.query_one("#waypoints_table", DataTable)
                        table_refreshed.focus()

                        # Find the row index for the saved key after refresh
                        target_idx = None
                        if rk is not None:
                            # Try to find row by key
                            try:
                                row_count = getattr(table_refreshed, "row_count", 0) or 0
                                for i in range(row_count):
                                    try:
                                        row_key = table_refreshed.get_row_key(i)  # type: ignore[attr-defined]
                                        if str(row_key) == str(rk):
                                            target_idx = i
                                            break
                                    except Exception:
                                        continue
                            except Exception:
                                pass

                        # Fallback to saved index if key lookup failed
                        if target_idx is None:
                            target_idx = target_index

                        current_pos = getattr(table_refreshed, "cursor_row", 0) or 0

                        # Move to row 0 first (known position)
                        if current_pos > 0:
                            for _ in range(current_pos):
                                try:
                                    table_refreshed.action_cursor_up()  # type: ignore[attr-defined]
                                except Exception:
                                    break

                        # Then move down to target
                        for _ in range(target_idx):
                            try:
                                table_refreshed.action_cursor_down()  # type: ignore[attr-defined]
                            except Exception:
                                break
                    except Exception:
                        pass

                try:
                    self.call_after_refresh(restore_waypoints_cursor)
                except Exception:
                    restore_waypoints_cursor()

                # Timer fallback
                try:
                    self.set_timer(0.05, restore_waypoints_cursor, name="restore_waypoints_cursor")
                except Exception:
                    pass
        except Exception:
            return
        return

    def _start_export(self) -> None:
        self._export_error = None
        self._export_manifest = None
        self._export_in_progress = True
        self._render_main()
        if self.model.parsed is None:
            self._export_error = "No parsed data. Go back."
            self._export_in_progress = False
            self._render_main()
            return
        out_dir = self.model.output_dir or (Path.cwd() / "onx_ready")
        try:
            out_dir = out_dir.expanduser()
        except Exception:
            pass
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._export_error = f"Failed to create output dir: {e}"
            self._export_in_progress = False
            self._render_main()
            return

        # Run export in a background thread to keep UI responsive.
        t = threading.Thread(
            target=self._export_worker,
            args=(out_dir,),
            daemon=True,
        )
        t.start()

    def _export_worker(self, out_dir: Path) -> None:
        try:
            manifest = process_and_write_files(
                self.model.parsed,  # type: ignore[arg-type]
                out_dir,
                sort=True,
                skip_confirmation=True,
                config=self._config,
                split_gpx=True,
                max_gpx_bytes=4 * 1024 * 1024,
            )
            rows = [(a, b, int(c), int(d)) for (a, b, c, d) in manifest]
            self.call_from_thread(self._on_export_done, rows, None)
        except Exception as e:
            self.call_from_thread(self._on_export_done, None, f"Export error: {e}")

    def _on_export_done(
        self,
        manifest: Optional[list[tuple[str, str, int, int]]],
        err: Optional[str],
    ) -> None:
        self._export_in_progress = False
        self._export_manifest = manifest
        self._export_error = err
        self._render_main()

        # After a successful export, prompt for next action (new file vs quit).
        try:
            if err is None and manifest and not self._post_save_prompt_shown:
                self._post_save_prompt_shown = True
                self.push_screen(
                    ConfirmModal(
                        "Export complete.\n\nMigrate another file?",
                        title="Export complete",
                    ),
                    self._on_post_save_choice,
                )
        except Exception:
            pass

    def _on_post_save_choice(self, confirmed: bool) -> None:
        if confirmed:
            self.action_new_file()
        else:
            try:
                self.exit()
            except Exception:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        try:
            if event.input.id == "routes_search":
                self._routes_filter = event.value or ""
                self._refresh_routes_table()
            elif event.input.id == "waypoints_search":
                self._waypoints_filter = event.value or ""
                self._refresh_waypoints_table()
            elif event.input.id == "output_prefix":
                # Keep in sync while typing; pressing Enter will also commit.
                self._output_prefix = str(event.value or "")
            elif str(event.input.id or "").startswith("rename_"):
                try:
                    idx = int(str(event.input.id).split("_", 1)[1])
                except Exception:
                    idx = None
                if idx is not None:
                    self._rename_overrides_by_idx[idx] = str(event.value or "")
        except Exception as e:
            self._ui_error = str(e)
