from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Input, Static, DirectoryTree
import threading
import os
import time

from rich.text import Text

from cairn.core.color_mapper import ColorMapper
from cairn.core.mapper import map_icon
from cairn.commands.convert_cmd import collect_unmapped_caltopo_symbols, process_and_write_files

from cairn.core.config import (
    get_all_onx_icons,
    get_icon_color,
    load_config,
    normalize_onx_icon_name,
)
from cairn.core.parser import ParsedData, parse_geojson
from cairn.ui.state import UIState, load_state
from cairn.tui.edit_screens import (
    ActionsModal,
    ColorPickerModal,
    DescriptionModal,
    EditContext,
    IconOverrideModal,
    InfoModal,
    RenameModal,
)


STEPS = [
    "Select_file",
    "List_data",
    "Folder",
    "Routes",
    "Edit_routes",
    "Waypoints",
    "Edit_waypoints",
    "Preview",
    "Save",
]


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
            if s == self.current:
                lines.append(f" ▸ {s}")
            elif s in self.done:
                lines.append(f" ✓ {s}")
            else:
                lines.append(f"   {s}")
        return "\n".join(lines)


class CairnTuiApp(App):
    """
    CalTopo → OnX v1 TUI.

    This is intentionally a guided, linear flow with a visible stepper and
    warm theme. It reuses existing parsing + export logic.
    """

    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "focus_next", "Next field"),
        Binding("/", "focus_search", "Search"),
        Binding("t", "focus_table", "Table"),
        Binding("a", "actions", "Actions"),
        Binding("e", "export", "Export"),
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
                table.add_columns("Sel", "Name", "Symbol", "Mapped icon", "Color")
        except Exception:
            try:
                table.add_columns("Sel", "Name", "Symbol", "Mapped icon", "Color")
            except Exception:
                pass

        for i, wp in enumerate(waypoints):
            key = str(i)
            title0 = str(getattr(wp, "title", "") or "Untitled")
            if q and q not in title0.lower():
                continue
            sel = "●" if key in self._selected_waypoint_keys else " "
            sym = str(getattr(wp, "symbol", "") or "")
            mapped = self._resolved_waypoint_icon(wp)
            rgba = self._resolved_waypoint_color(wp, mapped)
            try:
                table.add_row(sel, title0, sym, mapped, self._color_chip(rgba), key=key)
            except Exception:
                name = ColorMapper.get_color_name(rgba).replace("-", " ").upper()
                table.add_row(sel, title0, sym, mapped, f"■ {name}", key=key)

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
                table.add_columns("Sel", "Name", "Stroke", "Pattern", "Width")
        except Exception:
            try:
                table.add_columns("Sel", "Name", "Stroke", "Pattern", "Width")
            except Exception:
                pass

        for i, trk in enumerate(tracks):
            key = str(i)
            name = str(getattr(trk, "title", "") or "Untitled")
            if q and q not in name.lower():
                continue
            sel = "●" if key in self._selected_route_keys else " "
            table.add_row(
                sel,
                name,
                str(getattr(trk, "stroke", "") or ""),
                str(getattr(trk, "pattern", "") or ""),
                str(getattr(trk, "stroke_width", "") or ""),
                key=key,
            )

    def _refresh_edit_routes_table(self) -> None:
        """Refresh Edit_routes table in-place (avoid remounting + DuplicateIds)."""
        if self.step != "Edit_routes":
            return
        try:
            table = self.query_one("#edit_routes_table", DataTable)
        except Exception:
            return
        if self.model.parsed is None or not self.model.selected_folder_id:
            return
        fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
        tracks = list((fd or {}).get("tracks", []) or [])
        sel = sorted(k for k in self._selected_route_keys if str(k).isdigit())

        self._datatable_clear_rows(table)
        try:
            if not getattr(table, "columns", None):  # type: ignore[attr-defined]
                table.add_columns("Name", "Stroke", "Pattern", "Width")
        except Exception:
            try:
                table.add_columns("Name", "Stroke", "Pattern", "Width")
            except Exception:
                pass

        for k in sel:
            i = int(k)
            if i < 0 or i >= len(tracks):
                continue
            trk = tracks[i]
            table.add_row(
                str(getattr(trk, "title", "") or "Untitled"),
                str(getattr(trk, "stroke", "") or ""),
                str(getattr(trk, "pattern", "") or ""),
                str(getattr(trk, "stroke_width", "") or ""),
                key=str(k),
            )

    def _refresh_edit_waypoints_table(self) -> None:
        """Refresh Edit_waypoints table in-place (avoid remounting + DuplicateIds)."""
        if self.step != "Edit_waypoints":
            return
        try:
            table = self.query_one("#edit_waypoints_table", DataTable)
        except Exception:
            return
        if self.model.parsed is None or not self.model.selected_folder_id:
            return
        fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
        waypoints = list((fd or {}).get("waypoints", []) or [])
        sel = sorted(k for k in self._selected_waypoint_keys if str(k).isdigit())

        self._datatable_clear_rows(table)
        try:
            if not getattr(table, "columns", None):  # type: ignore[attr-defined]
                table.add_columns("Name", "OnX icon", "OnX color")
        except Exception:
            try:
                table.add_columns("Name", "OnX icon", "OnX color")
            except Exception:
                pass

        for k in sel:
            i = int(k)
            if i < 0 or i >= len(waypoints):
                continue
            wp = waypoints[i]
            name0 = str(getattr(wp, "title", "") or "Untitled")
            icon = self._resolved_waypoint_icon(wp)
            rgba = self._resolved_waypoint_color(wp, icon)
            try:
                table.add_row(name0, icon, self._color_chip(rgba), key=str(k))
            except Exception:
                table.add_row(
                    name0,
                    icon,
                    f"■ {ColorMapper.get_color_name(rgba).replace('-', ' ').upper()}",
                    key=str(k),
                )

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
                yield Static("Keys:", classes="muted")
                yield Static("Enter: Continue", classes="muted")
                yield Static("Esc: Back", classes="muted")
                yield Static("a: Actions", classes="muted")
                yield Static("q: Quit", classes="muted")
            with Container(classes="main"):
                yield Static("", id="main_title", classes="title")
                yield Static("", id="main_subtitle", classes="muted")
                yield Container(id="main_body")
        yield Footer()

    def on_mount(self) -> None:
        self._goto("Select_file")

    # -----------------------
    # Navigation
    # -----------------------
    def _reset_focus_for_step(self) -> None:
        """
        Ensure focus is on an on-screen widget after step transitions.

        This fixes a subtle real-world issue: when we auto-advance from Select_file
        (DirectoryTree focused) to List_data, focus may remain on the removed tree,
        causing Enter key presses to be swallowed / not reach the app-level flow.
        """
        try:
            if self.step == "List_data":
                # Clear focus so Enter/Escape route to app handlers.
                self.set_focus(None)  # type: ignore[arg-type]
                return
            if self.step == "Folder":
                self.query_one("#folder_table", DataTable).focus()
                return
            if self.step == "Save":
                # Don't auto-focus the output dir input: it would swallow the 'e' binding
                # (export) and make the default flow confusing. Users can Tab to focus it.
                self.set_focus(None)  # type: ignore[arg-type]
                return
        except Exception:
            return

    def _goto(self, step: str) -> None:
        if step not in STEPS:
            return
        self.step = step
        self._render_sidebar()
        self._render_main()
        try:
            self.call_after_refresh(self._reset_focus_for_step)
        except Exception:
            # If call_after_refresh isn't available for some reason, fall back to best effort.
            self._reset_focus_for_step()

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

    def action_continue(self) -> None:
        # Step-specific gating + actions.
        if self.step == "Select_file":
            # Rely on selecting a file in the tree (or submitting the input field) to advance.
            # Enter is often consumed by DirectoryTree, and also makes it too easy to
            # accidentally advance with an old selection when navigating back.
            return

        if self.step == "List_data":
            self._done_steps.add("List_data")
            self._goto("Folder")
            return

        if self.step == "Folder":
            if not self.model.selected_folder_id:
                inferred = self._infer_folder_selection()
                # Some Textual versions don't support query_one(..., expect_none=True).
                table_obj = None
                try:
                    table_obj = self.query_one("#folder_table", DataTable)
                except Exception:
                    table_obj = None
                if inferred:
                    self.model.selected_folder_id = inferred
                else:
                    return
            self._done_steps.add("Folder")
            self._goto("Routes")
            return

        if self.step == "Routes":
            self._done_steps.add("Routes")
            self._goto("Edit_routes")
            return

        if self.step == "Edit_routes":
            self._done_steps.add("Edit_routes")
            self._goto("Waypoints")
            return

        if self.step == "Waypoints":
            self._done_steps.add("Waypoints")
            self._goto("Edit_waypoints")
            return

        if self.step == "Edit_waypoints":
            self._done_steps.add("Edit_waypoints")
            self._goto("Preview")
            return

        if self.step == "Preview":
            self._done_steps.add("Preview")
            self._goto("Save")
            return

        if self.step == "Save":
            # In Save step, Enter is a no-op by default (export is explicit via 'e')
            # so users can type in the output dir input without accidental exports.
            return

    def action_export(self) -> None:
        if self.step == "Save":
            self._start_export()

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

    def _selected_keys_for_step(self) -> Optional[EditContext]:
        if self.step in ("Routes", "Edit_routes"):
            if not self._selected_route_keys:
                return None
            return EditContext(kind="route", selected_keys=tuple(sorted(self._selected_route_keys)))
        if self.step in ("Waypoints", "Edit_waypoints"):
            if not self._selected_waypoint_keys:
                return None
            return EditContext(kind="waypoint", selected_keys=tuple(sorted(self._selected_waypoint_keys)))
        return None

    def _selected_features(self, ctx: EditContext) -> list:
        tracks, waypoints = self._current_folder_features()
        out = []
        for k in ctx.selected_keys:
            if not str(k).isdigit():
                continue
            idx = int(k)
            if ctx.kind == "route":
                if 0 <= idx < len(tracks):
                    out.append(tracks[idx])
            elif ctx.kind == "waypoint":
                if 0 <= idx < len(waypoints):
                    out.append(waypoints[idx])
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
        # Textual's Screen API: push_screen(screen, callback) where callback receives dismiss() value.
        self.push_screen(ActionsModal(ctx=ctx), self._on_action_chosen)

    def _on_action_chosen(self, action: object) -> None:
        act = str(action or "").strip().lower()
        ctx = self._selected_keys_for_step()
        if ctx is None:
            return
        if act in ("", "cancel"):
            return
        if act == "rename":
            self.push_screen(RenameModal(ctx=ctx), self._apply_edit_payload)
            return
        if act == "description":
            self.push_screen(DescriptionModal(ctx=ctx), self._apply_edit_payload)
            return
        if act == "color":
            if ctx.kind == "route":
                palette = [
                    (p.rgba, (p.name or "").replace("-", " ").upper())
                    for p in ColorMapper.TRACK_PALETTE
                ]
                self.push_screen(
                    ColorPickerModal(
                        ctx=ctx,
                        title="Select route color",
                        palette=palette,
                    ),
                    self._apply_edit_payload,
                )
                return
            if ctx.kind == "waypoint":
                palette = [
                    (p.rgba, (p.name or "").replace("-", " ").upper())
                    for p in ColorMapper.WAYPOINT_PALETTE
                ]
                self.push_screen(
                    ColorPickerModal(
                        ctx=ctx,
                        title="Select waypoint color",
                        palette=palette,
                    ),
                    self._apply_edit_payload,
                )
                return
        if act == "icon" and ctx.kind == "waypoint":
            self.push_screen(
                IconOverrideModal(ctx=ctx, icons=get_all_onx_icons()),
                self._apply_edit_payload,
            )
            return

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

        # Refresh current step tables so edits are visible immediately.
        if self.step == "Routes":
            self._refresh_routes_table()
        elif self.step == "Waypoints":
            self._refresh_waypoints_table()
        elif self.step == "Edit_routes":
            self._refresh_edit_routes_table()
        elif self.step == "Edit_waypoints":
            self._refresh_edit_waypoints_table()
        elif self.step == "Preview":
            self._render_main()

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
            subtitle.update("Choose a CalTopo GeoJSON export (.json/.geojson)")
            body = self._clear_main_body()
            default_root = Path(self._state.default_root).expanduser() if self._state.default_root else Path.cwd()
            body.mount(Static("Pick a file (tree) or paste a path:", classes="muted"))
            body.mount(
                DirectoryTree(
                    str(default_root),
                    id="file_tree",
                )
            )
            body.mount(Input(placeholder="Path to .json/.geojson", id="input_path"))
            body.mount(Static("Enter: continue", classes="muted"))
            # Prefer focusing the tree so arrow keys + Enter work immediately.
            try:
                tree = self.query_one("#file_tree", DirectoryTree)
                self.call_after_refresh(tree.focus)
            except Exception:
                pass
            return

        if self.step == "List_data":
            title.update("List data")
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
            else:
                body.mount(Static("Unmapped symbols: 0", classes="ok"))

            body.mount(Static("Press Enter to continue.", classes="muted"))
            return

        if self.step == "Folder":
            title.update("Folder")
            subtitle.update("Pick a folder to inspect routes/waypoints")
            body = self._clear_main_body()
            if self.model.parsed is None:
                body.mount(Static("No parsed data. Go back.", classes="err"))
                return
            folders = list((getattr(self.model.parsed, "folders", {}) or {}).items())
            if not folders:
                body.mount(Static("No folders found.", classes="err"))
                return
            table = DataTable(id="folder_table")
            table.add_columns("Folder", "Waypoints", "Routes", "Shapes")
            for folder_id, fd in folders:
                name = str((fd or {}).get("name") or folder_id)
                w = len((fd or {}).get("waypoints", []) or [])
                t = len((fd or {}).get("tracks", []) or [])
                s = len((fd or {}).get("shapes", []) or [])
                table.add_row(name, str(w), str(t), str(s), key=folder_id)
            body.mount(table)
            body.mount(Static("Use arrows to highlight. Enter: continue", classes="muted"))
            return

        if self.step == "Routes":
            title.update("Routes")
            subtitle.update("Browse routes (Space to toggle selection, / to search)")
            body = self._clear_main_body()
            if self.model.parsed is None or not self.model.selected_folder_id:
                body.mount(Static("No folder selected. Go back.", classes="err"))
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            tracks = list((fd or {}).get("tracks", []) or [])
            body.mount(Input(placeholder="Filter routes…", id="routes_search"))
            table = DataTable(id="routes_table")
            table.add_columns("Sel", "Name", "Stroke", "Pattern", "Width")
            q = (self._routes_filter or "").strip().lower()
            for i, trk in enumerate(tracks):
                name = str(getattr(trk, "title", "") or "Untitled")
                if q and q not in name.lower():
                    continue
                key = str(i)
                sel = "●" if key in self._selected_route_keys else " "
                table.add_row(
                    sel,
                    name,
                    str(getattr(trk, "stroke", "") or ""),
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

        if self.step == "Edit_routes":
            title.update("Edit routes")
            subtitle.update("Review selected routes (press 'a' for Actions, Enter to continue)")
            body = self._clear_main_body()
            if self.model.parsed is None or not self.model.selected_folder_id:
                body.mount(Static("No folder selected. Go back.", classes="err"))
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            tracks = list((fd or {}).get("tracks", []) or [])

            sel = sorted(k for k in self._selected_route_keys if str(k).isdigit())
            body.mount(
                Static(
                    f"Selected routes: {len(sel)}  (Space toggles on Routes screen)",
                    classes="muted",
                )
            )
            if not sel:
                body.mount(Static("No routes selected. Press Enter to continue.", classes="muted"))
                return

            table = DataTable(id="edit_routes_table")
            table.add_columns("Name", "Stroke", "Pattern", "Width")
            body.mount(table)
            # Populate rows via in-place refresher (also used after edits).
            self._refresh_edit_routes_table()
            body.mount(Static("a: Actions  Enter: continue to Waypoints", classes="muted"))
            try:
                self.call_after_refresh(table.focus)
            except Exception:
                pass
            return

        if self.step == "Waypoints":
            title.update("Waypoints")
            subtitle.update("Browse waypoints (Space to toggle selection, / to search)")
            body = self._clear_main_body()
            if self.model.parsed is None or not self.model.selected_folder_id:
                body.mount(Static("No folder selected. Go back.", classes="err"))
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            waypoints = list((fd or {}).get("waypoints", []) or [])
            body.mount(Input(placeholder="Filter waypoints…", id="waypoints_search"))
            table = DataTable(id="waypoints_table")
            table.add_columns("Sel", "Name", "Symbol", "Mapped icon", "Color")

            q = (self._waypoints_filter or "").strip().lower()
            for i, wp in enumerate(waypoints):
                key = str(i)
                sel = "●" if key in self._selected_waypoint_keys else " "
                title0 = str(getattr(wp, "title", "") or "Untitled")
                if q and q not in title0.lower():
                    continue
                sym = str(getattr(wp, "symbol", "") or "")
                mapped = self._resolved_waypoint_icon(wp)
                rgba = self._resolved_waypoint_color(wp, mapped)
                try:
                    table.add_row(sel, title0, sym, mapped, self._color_chip(rgba), key=key)
                except Exception as e:
                    # Some Textual versions are picky about cell renderables; fall back to plain text.
                    self._dbg(
                        event="waypoints.table.add_row_error",
                        data={"err": str(e), "rgba": rgba, "name": title0},
                    )
                    name = ColorMapper.get_color_name(rgba).replace("-", " ").upper()
                    table.add_row(sel, title0, sym, mapped, f"■ {name}", key=key)
            body.mount(table)
            body.mount(Static("Space: toggle select  /: filter  t: focus table  Enter: continue", classes="muted"))
            try:
                self.call_after_refresh(table.focus)
            except Exception:
                pass
            return

        if self.step == "Edit_waypoints":
            title.update("Edit waypoints")
            subtitle.update("Review selected waypoints (press 'a' for Actions, Enter to continue)")
            body = self._clear_main_body()
            if self.model.parsed is None or not self.model.selected_folder_id:
                body.mount(Static("No folder selected. Go back.", classes="err"))
                return
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(self.model.selected_folder_id)
            waypoints = list((fd or {}).get("waypoints", []) or [])

            sel = sorted(k for k in self._selected_waypoint_keys if str(k).isdigit())
            body.mount(
                Static(
                    f"Selected waypoints: {len(sel)}  (Space toggles on Waypoints screen)",
                    classes="muted",
                )
            )
            if not sel:
                body.mount(Static("No waypoints selected. Press Enter to continue.", classes="muted"))
                return

            table = DataTable(id="edit_waypoints_table")
            table.add_columns("Name", "OnX icon", "OnX color")
            body.mount(table)
            # Populate rows via in-place refresher (also used after edits).
            self._refresh_edit_waypoints_table()
            body.mount(Static("a: Actions  Enter: continue to Preview", classes="muted"))
            try:
                self.call_after_refresh(table.focus)
            except Exception:
                pass
            return

        if self.step == "Preview":
            title.update("Preview")
            subtitle.update("What will be exported (folder, routes, waypoints, files)")
            body = self._clear_main_body()
            if self.model.parsed is None:
                body.mount(Static("No parsed data. Go back.", classes="err"))
                return
            fid = self.model.selected_folder_id
            if not fid:
                body.mount(Static("No folder selected. Go back.", classes="err"))
                return
            folder_name = self._folder_name_by_id.get(fid, fid)
            fd = (getattr(self.model.parsed, "folders", {}) or {}).get(fid) or {}
            tracks = list(fd.get("tracks", []) or [])
            waypoints = list(fd.get("waypoints", []) or [])

            body.mount(Static(f"Folder: {folder_name}", classes="ok"))

            # Waypoint preview table (selected first, then rest).
            wp_table = DataTable(id="preview_waypoints")
            wp_table.add_columns("Name", "OnX icon", "OnX color")
            for i, wp in enumerate(waypoints):
                key = str(i)
                if self._selected_waypoint_keys and key not in self._selected_waypoint_keys:
                    continue
                name0 = str(getattr(wp, "title", "") or "Untitled")
                icon = self._resolved_waypoint_icon(wp)
                rgba = self._resolved_waypoint_color(wp, icon)
                try:
                    wp_table.add_row(name0, icon, self._color_chip(rgba))
                except Exception as e:
                    self._dbg(event="preview.wp_row_error", data={"err": str(e), "rgba": rgba})
                    wp_table.add_row(name0, icon, f"■ {ColorMapper.get_color_name(rgba).replace('-', ' ').upper()}")
            body.mount(Static("Waypoints (selected)", classes="accent"))
            body.mount(wp_table)

            trk_table = DataTable(id="preview_routes")
            trk_table.add_columns("Name", "OnX color", "Style", "Weight")
            for i, trk in enumerate(tracks):
                key = str(i)
                if self._selected_route_keys and key not in self._selected_route_keys:
                    continue
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
            body.mount(Static("Routes (selected)", classes="accent"))
            body.mount(trk_table)

            body.mount(Static("Enter to continue to Save", classes="muted"))
            return

        if self.step == "Save":
            title.update("Save")
            subtitle.update("Choose output directory and export")
            # IMPORTANT: don't re-mount a new Input with the same ID on re-render.
            # Textual enforces globally unique IDs and can raise DuplicateIds if a widget
            # is still in the DOM while we're rebuilding this screen (e.g., during export
            # status updates). We keep/reuse the existing output_dir Input if present.
            body = self.query_one("#main_body", Container)
            existing_out: Optional[Input] = None
            try:
                existing_out = body.query_one("#output_dir", Input)
            except Exception:
                existing_out = None

            # Remove everything except the output_dir input (if it already exists).
            try:
                for child in list(getattr(body, "children", []) or []):
                    if existing_out is not None and child is existing_out:
                        continue
                    try:
                        child.remove()
                    except Exception:
                        pass
            except Exception:
                pass

            if existing_out is None:
                body.mount(Input(placeholder="Output directory (default: ./onx_ready)", id="output_dir"))
            if self._export_in_progress:
                body.mount(Static("Exporting… (please wait)", classes="accent"))
            if self._export_error:
                body.mount(Static(self._export_error, classes="err"))
            if self._export_manifest:
                tbl = DataTable(id="manifest")
                tbl.add_columns("File", "Format", "Items", "Bytes")
                for fn, fmt, cnt, sz in self._export_manifest:
                    tbl.add_row(fn, fmt, str(cnt), str(sz))
                body.mount(Static("Export manifest", classes="accent"))
                body.mount(tbl)
                body.mount(Static("Done. q to quit.", classes="muted"))
            else:
                body.mount(Static("Press 'e' to export", classes="muted"))
            return

    # -----------------------
    # Events
    # -----------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "input_path":
            raw = (event.value or "").strip()
            if not raw:
                return
            p = Path(raw).expanduser()
            try:
                p = p.resolve()
            except Exception:
                pass
            self.model.input_path = p
            self._render_sidebar()
            if self.step == "Select_file" and p.suffix.lower() in (".json", ".geojson") and p.exists() and p.is_file():
                self._done_steps.add("Select_file")
                self._goto("List_data")
        elif event.input.id == "output_dir":
            raw = (event.value or "").strip()
            if not raw:
                self.model.output_dir = Path.cwd() / "onx_ready"
            else:
                self.model.output_dir = Path(raw).expanduser()
            self._render_sidebar()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "folder_table":
            try:
                self.model.selected_folder_id = str(event.row_key.value)
            except Exception:
                self.model.selected_folder_id = None
            self._dbg(
                event="folder.row_selected",
                data={"folder_id": self.model.selected_folder_id},
            )

    def action_focus_search(self) -> None:
        # Best-effort: focus the search input on routes/waypoints screens.
        try:
            if self.step == "Routes":
                self.query_one("#routes_search", Input).focus()
            elif self.step == "Waypoints":
                self.query_one("#waypoints_search", Input).focus()
        except Exception:
            return

    def action_focus_table(self) -> None:
        """Focus the main table for the current step (so Space toggles selection)."""
        try:
            if self.step == "Routes":
                tbl = self.query_one("#routes_table", DataTable)
                tbl.focus()
            elif self.step == "Waypoints":
                tbl = self.query_one("#waypoints_table", DataTable)
                tbl.focus()
        except Exception as e:
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

        # IMPORTANT: When a modal is open (editing dialogs), let the modal handle
        # Enter/Escape/etc. Otherwise our global step-navigation hijacks Enter and
        # makes modals unusable.
        try:
            from textual.screen import ModalScreen

            if isinstance(getattr(self, "screen", None), ModalScreen):
                return
        except Exception:
            pass

        # Make navigation reliable regardless of focused widget.
        # Some widgets may consume Enter/Escape depending on focus state.
        if event.key == "escape":
            self.action_back()
            try:
                event.stop()
            except Exception:
                pass
            return

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
                self._refresh_routes_table()
            elif self.step == "Waypoints":
                table = self.query_one("#waypoints_table", DataTable)
                rk = self._table_cursor_row_key(table)
                idx = int(getattr(table, "cursor_row", 0) or 0)
                k = rk if rk is not None else str(idx)
                if k in self._selected_waypoint_keys:
                    self._selected_waypoint_keys.remove(k)
                else:
                    self._selected_waypoint_keys.add(k)
                self._refresh_waypoints_table()
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

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        p = Path(str(event.path))
        if p.suffix.lower() not in (".json", ".geojson"):
            return
        self.model.input_path = p
        # Update input box if present.
        try:
            inp = self.query_one("#input_path", Input)
            inp.value = str(p)
        except Exception:
            pass
        self._render_sidebar()

        # Auto-advance: in many terminals the DirectoryTree consumes Enter, so relying on a
        # second Enter to trigger the app-level "continue" is unreliable.
        if self.step == "Select_file":
            self._done_steps.add("Select_file")
            self._goto("List_data")

    def on_input_changed(self, event: Input.Changed) -> None:
        try:
            if event.input.id == "routes_search":
                self._routes_filter = event.value or ""
                self._refresh_routes_table()
            elif event.input.id == "waypoints_search":
                self._waypoints_filter = event.value or ""
                self._refresh_waypoints_table()
        except Exception as e:
            self._ui_error = str(e)
