"""Event routing for the TUI module.

This module centralizes keyboard event routing, decomposing the massive on_key()
method from app.py into manageable event handling.
"""

from typing import Optional, Any

from textual.widgets import DataTable, Input

from cairn.tui.debug import agent_log as _agent_log


class EventRouter:
    """Centralized keyboard event routing and focus management.

    Handles overlay priority, modal detection, and step-specific shortcuts.
    """

    # Overlay priority order (highest first) - picker overlays need special handling
    PICKER_OVERLAYS = [
        "#icon_picker_overlay",
        "#color_picker_overlay",
    ]

    # These overlays just need to block global key handling (they handle their own)
    PASSTHROUGH_OVERLAYS = [
        "#inline_edit_overlay",
        "#save_target_overlay",
        "#rename_overlay",
        "#description_overlay",
        "#confirm_overlay",
    ]

    def __init__(self, app) -> None:
        """Initialize event router.

        Args:
            app: The CairnTuiApp instance
        """
        self.app = app

    def is_overlay_open(self, selector: str) -> bool:
        """Check if an overlay is currently open.

        Args:
            selector: CSS selector for the overlay

        Returns:
            True if overlay is open, False otherwise
        """
        try:
            w = self.app.query_one(selector)
            return bool(getattr(w, "has_class", lambda _c: False)("open"))
        except Exception:
            return False

    def is_modal_screen_active(self) -> bool:
        """Check if a modal screen is currently active.

        Returns:
            True if modal screen is active, False otherwise
        """
        try:
            from textual.screen import ModalScreen
            return isinstance(getattr(self.app, "screen", None), ModalScreen)
        except Exception:
            return False

    def get_key_info(self, event) -> tuple[str, str]:
        """Extract key and character from event.

        Args:
            event: Textual key event

        Returns:
            Tuple of (key, character)
        """
        key = str(getattr(event, "key", "") or "")
        character = str(getattr(event, "character", "") or "")
        return key, character

    def get_focused_id(self) -> Optional[str]:
        """Get the ID of the currently focused widget.

        Returns:
            Widget ID or None
        """
        return getattr(getattr(self.app, "focused", None), "id", None)

    def is_enter_key(self, event) -> bool:
        """Check if event is an Enter key press.

        Args:
            event: Textual key event

        Returns:
            True if Enter was pressed
        """
        key, character = self.get_key_info(event)
        return key in ("enter", "return") or character == "\r"

    def handle_icon_picker_key(self, event) -> bool:
        """Handle key events when icon picker overlay is open.

        Args:
            event: Textual key event

        Returns:
            True if event was handled
        """
        key, _ = self.get_key_info(event)
        focused_id = self.get_focused_id()

        try:
            tbl = self.app.query_one("#icon_table", DataTable)
        except Exception:
            tbl = None

        # Arrow keys: forward to table only when filter input is focused
        # Avoid double-moving cursor when table is focused
        if key in ("up", "down") and tbl is not None and focused_id != "icon_table":
            try:
                if key == "down":
                    tbl.action_cursor_down()
                else:
                    tbl.action_cursor_up()
            except Exception:
                pass
            return True

        # Escape: close picker, cancel selection
        if key == "escape":
            try:
                from cairn.tui.edit_screens import IconPickerOverlay
                self.app.query_one("#icon_picker_overlay", IconPickerOverlay).close()
            except Exception:
                pass
            try:
                from cairn.tui.edit_screens import IconPickerOverlay
                self.app.on_icon_picker_overlay_icon_picked(IconPickerOverlay.IconPicked(None))
            except Exception:
                pass
            return True

        # Enter: close picker, confirm selection
        if self.is_enter_key(event):
            icon = None
            if tbl is not None:
                icon = (self.app._table_cursor_row_key(tbl) or "").strip() or None
            try:
                from cairn.tui.edit_screens import IconPickerOverlay
                self.app.query_one("#icon_picker_overlay", IconPickerOverlay).close()
            except Exception:
                pass
            try:
                from cairn.tui.edit_screens import IconPickerOverlay
                self.app.on_icon_picker_overlay_icon_picked(IconPickerOverlay.IconPicked(icon))
            except Exception:
                pass
            return True

        # Other keys: let overlay handle them
        return True  # Block global handling

    def handle_color_picker_key(self, event) -> bool:
        """Handle key events when color picker overlay is open.

        Args:
            event: Textual key event

        Returns:
            True if event was handled
        """
        key, _ = self.get_key_info(event)
        focused_id = self.get_focused_id()

        try:
            tbl = self.app.query_one("#palette_table", DataTable)
        except Exception:
            tbl = None

        # Arrow keys: forward to table only when filter input is focused
        if key in ("up", "down") and tbl is not None and focused_id != "palette_table":
            try:
                if key == "down":
                    tbl.action_cursor_down()
                else:
                    tbl.action_cursor_up()
            except Exception:
                pass
            return True

        # Escape: close picker, cancel selection
        if key == "escape":
            try:
                from cairn.tui.edit_screens import ColorPickerOverlay
                self.app.query_one("#color_picker_overlay", ColorPickerOverlay).close()
            except Exception:
                pass
            try:
                from cairn.tui.edit_screens import ColorPickerOverlay
                self.app.on_color_picker_overlay_color_picked(ColorPickerOverlay.ColorPicked(None))
            except Exception:
                pass
            return True

        # Enter: close picker, confirm selection
        if self.is_enter_key(event):
            rgba = None
            if tbl is not None:
                rgba = (self.app._table_cursor_row_key(tbl) or "").strip() or None
            try:
                from cairn.tui.edit_screens import ColorPickerOverlay
                self.app.query_one("#color_picker_overlay", ColorPickerOverlay).close()
            except Exception:
                pass
            try:
                from cairn.tui.edit_screens import ColorPickerOverlay
                self.app.on_color_picker_overlay_color_picked(ColorPickerOverlay.ColorPicked(rgba))
            except Exception:
                pass
            return True

        # Other keys: let overlay handle them
        return True  # Block global handling

    def handle_help_key(self, event) -> bool:
        """Handle ? key for help.

        Args:
            event: Textual key event

        Returns:
            True if help was shown
        """
        key, character = self.get_key_info(event)
        if key == "question_mark" or character == "?":
            self.app.action_show_help()
            return True
        return False

    def handle_escape_key(self, event) -> bool:
        """Handle Escape key for back navigation.

        Args:
            event: Textual key event

        Returns:
            True if back navigation was triggered
        """
        key, _ = self.get_key_info(event)
        if key != "escape":
            return False

        # Debug logging for Preview step
        if self.app.step == "Preview":
            try:
                self.app._dbg(
                    event="save.key",
                    data={
                        "key": key,
                        "character": str(getattr(event, "character", "")),
                        "focused_id": self.get_focused_id(),
                        "output_dir": str(self.app.model.output_dir) if self.app.model.output_dir else None,
                        "prefix": str(getattr(self.app, "_output_prefix", "") or ""),
                    },
                )
            except Exception:
                pass

        self.app.action_back()
        return True

    def handle_select_file_enter(self, event) -> bool:
        """Handle Enter key in Select_file step for DataTable file browser.

        Args:
            event: Textual key event

        Returns:
            True if file browser enter was handled
        """
        if self.app.step != "Select_file":
            return False

        # Only for DataTable-based file browser (not DirectoryTree)
        if self.app._use_tree_browser():
            return False

        try:
            focused_id = self.get_focused_id()
            if focused_id == "file_browser" and self.is_enter_key(event):
                self.app._file_browser_enter()
                return True
        except Exception:
            pass
        return False

    def handle_preview_step_keys(self, event) -> bool:
        """Handle special key handling for Preview step.

        Args:
            event: Textual key event

        Returns:
            True if key was handled
        """
        if self.app.step != "Preview":
            return False

        key, ch = self.get_key_info(event)
        focused_id = self.get_focused_id()

        # Ctrl+N: Create new folder (tree mode only)
        if key == "ctrl+n" and self.app._use_tree_browser():
            self.app._create_export_folder()
            return True

        # Handle Enter on directory table (DataTable mode)
        if focused_id == "export_dir_table" and self.is_enter_key(event):
            self.app._export_dir_table_enter()
            return True

        # Handle Enter to export (when not focused on directory browser or prefix input)
        if focused_id not in ("export_dir_table", "export_dir_tree", "export_prefix_input"):
            if self.is_enter_key(event):
                # Get prefix from input if available
                try:
                    from textual.widgets import Input
                    prefix_input = self.app.query_one("#export_prefix_input", Input)
                    self.app._output_prefix = prefix_input.value or ""
                except Exception:
                    pass

                try:
                    self.app._dbg(
                        event="save.key",
                        data={
                            "key": key,
                            "character": ch,
                            "focused_id": focused_id,
                            "output_dir": str(self.app.model.output_dir) if self.app.model.output_dir else None,
                            "prefix": str(getattr(self.app, "_output_prefix", "") or ""),
                        },
                    )
                except Exception:
                    pass

                try:
                    self.app.action_export()
                except Exception:
                    pass
                return True

        return False

    def handle_generic_enter(self, event) -> bool:
        """Handle generic Enter for step continuation.

        Args:
            event: Textual key event

        Returns:
            True if enter was handled
        """
        if self.is_enter_key(event):
            self.app.action_continue()
            return True
        return False

    def handle_space_toggle(self, event) -> bool:
        """Handle Space for selection toggling in tables.

        Args:
            event: Textual key event

        Returns:
            True if space was handled
        """
        key, _ = self.get_key_info(event)
        if key != "space":
            return False

        try:
            focused = {
                "type": type(self.app.focused).__name__ if self.app.focused else None,
                "id": getattr(self.app.focused, "id", None) if self.app.focused else None,
            }

            # If an Input is focused, let Space behave normally (type a space)
            if focused.get("type") == "Input":
                return False

            if self.app.step == "Folder":
                self._toggle_folder_selection()
                return True

            if self.app.step == "Routes":
                self._toggle_route_selection()
                return True

            if self.app.step == "Waypoints":
                self._toggle_waypoint_selection()
                return True

        except Exception:
            pass
        return False

    def _toggle_folder_selection(self) -> None:
        """Toggle folder selection and refresh table with cursor restoration."""
        table = self.app.query_one("#folder_table", DataTable)
        rk = self.app._table_cursor_row_key(table)
        if not rk:
            return

        folder_id = str(rk)
        if folder_id in self.app._selected_folders:
            self.app._selected_folders.remove(folder_id)
        else:
            self.app._selected_folders.add(folder_id)

        # Refresh table and get target cursor index
        target_index = self.app._refresh_folder_table()

        # Restore cursor position
        if target_index is not None:
            self._restore_table_cursor("#folder_table", target_index, rk)

    def _toggle_route_selection(self) -> None:
        """Toggle route selection and refresh table with cursor restoration."""
        table = self.app.query_one("#routes_table", DataTable)
        rk = self.app._table_cursor_row_key(table)
        idx = int(getattr(table, "cursor_row", 0) or 0)
        k = rk if rk is not None else str(idx)

        if k in self.app._selected_route_keys:
            self.app._selected_route_keys.remove(k)
        else:
            self.app._selected_route_keys.add(k)

        self.app._refresh_routes_table()
        self._restore_table_cursor("#routes_table", idx, rk)

    def _toggle_waypoint_selection(self) -> None:
        """Toggle waypoint selection and refresh table with cursor restoration."""
        table = self.app.query_one("#waypoints_table", DataTable)
        rk = self.app._table_cursor_row_key(table)
        idx = int(getattr(table, "cursor_row", 0) or 0)
        k = rk if rk is not None else str(idx)

        if k in self.app._selected_waypoint_keys:
            self.app._selected_waypoint_keys.remove(k)
        else:
            self.app._selected_waypoint_keys.add(k)

        self.app._refresh_waypoints_table()
        self._restore_table_cursor("#waypoints_table", idx, rk)

    def _restore_table_cursor(self, table_selector: str, target_index: int, row_key: Optional[str]) -> None:
        """Restore cursor position in a table after refresh.

        Args:
            table_selector: CSS selector for the table
            target_index: Target row index
            row_key: Optional row key for lookup
        """
        def restore_cursor():
            try:
                table_refreshed = self.app.query_one(table_selector, DataTable)
                table_refreshed.focus()

                # Find row index by key if provided
                target_idx = target_index
                if row_key is not None:
                    try:
                        row_count = getattr(table_refreshed, "row_count", 0) or 0
                        for i in range(row_count):
                            try:
                                rk = table_refreshed.get_row_key(i)
                                if str(rk) == str(row_key):
                                    target_idx = i
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass

                current_pos = getattr(table_refreshed, "cursor_row", 0) or 0

                # Move to row 0 first (known position)
                if current_pos > 0:
                    for _ in range(current_pos):
                        try:
                            table_refreshed.action_cursor_up()
                        except Exception:
                            break

                # Then move down to target
                for _ in range(target_idx):
                    try:
                        table_refreshed.action_cursor_down()
                    except Exception:
                        break
            except Exception:
                pass

        # Use multiple strategies for cursor restoration
        try:
            self.app.call_after_refresh(restore_cursor)
        except Exception:
            restore_cursor()

        try:
            self.app.set_timer(0.05, restore_cursor, name=f"restore_{table_selector.strip('#')}_cursor")
        except Exception:
            pass

    def route_key(self, event) -> bool:
        """Main entry point: route key event.

        Args:
            event: Textual key event

        Returns:
            True if event was handled and should be stopped
        """
        # Let modal screens handle their own events
        if self.is_modal_screen_active():
            return False

        # Check picker overlays (need special key handling)
        if self.is_overlay_open("#icon_picker_overlay"):
            return self.handle_icon_picker_key(event)

        if self.is_overlay_open("#color_picker_overlay"):
            return self.handle_color_picker_key(event)

        # Check passthrough overlays (just block global handling)
        for overlay_id in self.PASSTHROUGH_OVERLAYS:
            if self.is_overlay_open(overlay_id):
                return False  # Let overlay handle it

        # Global shortcuts
        if self.handle_help_key(event):
            return True

        if self.handle_escape_key(event):
            return True

        # Step-specific handling
        if self.handle_select_file_enter(event):
            return True

        if self.handle_preview_step_keys(event):
            return True

        # Generic Enter for step continuation
        if self.handle_generic_enter(event):
            return True

        # Space for selection toggling
        if self.handle_space_toggle(event):
            return True

        return False


__all__ = ["EventRouter"]
