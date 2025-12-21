"""State management for the TUI module.

This module manages workflow state, navigation, and selection tracking.
The reactive `step` property remains on CairnTuiApp for automatic UI updates.
"""

from typing import Optional, Set
from textual.widgets import DataTable

from cairn.tui.models import STEPS
from cairn.tui.debug import agent_log
from cairn.tui.widgets import FilteredFileTree, StepAwareFooter


class StateManager:
    """Manages workflow state and navigation.

    Key constraint: The reactive `step` property MUST stay on CairnTuiApp
    for automatic UI updates. StateManager handles logic; App holds the reactive property.
    """

    def __init__(self, app):
        """Initialize state manager.

        Args:
            app: The CairnTuiApp instance (for accessing model, config, etc.)
        """
        self.app = app
        self._done_steps: Set[str] = set()
        self._selected_route_keys: Set[str] = set()
        self._selected_waypoint_keys: Set[str] = set()
        self._selected_folders: Set[str] = set()

    def goto(self, step: str) -> None:
        """Navigate to a step. Updates app.step reactive property.

        Args:
            step: Step name to navigate to (must be in STEPS)
        """
        if step not in STEPS:
            return

        # Mark current as done
        if self.app.step in STEPS:
            self._done_steps.add(self.app.step)

        # Update reactive (triggers UI refresh)
        self.app.step = step

        # Clear per-step edit hints when leaving the step.
        if step != "Routes":
            self.app._routes_edited = False
        if step != "Waypoints":
            self.app._waypoints_edited = False

        # Sync UI
        self.app._render_sidebar()
        self.app._render_main()
        self.update_footer()

        # Reset focus after step change
        try:
            self.app.call_after_refresh(self.reset_focus_for_step)
        except Exception:
            # If call_after_refresh isn't available for some reason, fall back to best effort.
            self.reset_focus_for_step()

    def reset_focus_for_step(self) -> None:
        """Set focus to appropriate widget for current step.

        Ensures focus is on an on-screen widget after step transitions.
        This fixes a subtle real-world issue: when we auto-advance from Select_file
        to List_data, focus may remain on a removed widget, causing Enter key presses
        to be swallowed / not reach the app-level flow.
        """
        try:
            if self.app.step == "Select_file":
                if self.app._use_tree_browser():
                    self.app.query_one("#file_browser", FilteredFileTree).focus()
                else:
                    self.app.query_one("#file_browser", DataTable).focus()
                return
            if self.app.step == "List_data":
                # Clear focus so Enter/Escape route to app handlers.
                self.app.set_focus(None)  # type: ignore[arg-type]
                return
            if self.app.step == "Folder":
                self.app.query_one("#folder_table", DataTable).focus()
                return
            if self.app.step == "Preview":
                # Preview uses read-only tables; avoid focusing them so Enter/q reach app handlers.
                self.app.set_focus(None)  # type: ignore[arg-type]
                return
        except Exception:
            return

    def update_footer(self) -> None:
        """Update the step-aware footer with current step's shortcuts."""
        try:
            footer = self.app.query_one("#step_footer", StepAwareFooter)
            footer.set_step(self.app.step)
        except Exception:
            pass

    def infer_folder_selection(self) -> Optional[str]:
        """Best-effort: infer current folder selection from the folder table cursor.

        Textual's DataTable APIs vary a bit across versions; we try a few approaches.

        Returns:
            Folder ID string if found, None otherwise
        """
        try:
            table = self.app.query_one("#folder_table", DataTable)
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

    def get_next_step_after_folder(self) -> str:
        """Determine next step after Folder, skipping empty Routes/Waypoints steps.

        Returns:
            Next step name ("Routes", "Waypoints", or "Preview")
        """
        if self.app.model.parsed is None or not self.app.model.selected_folder_id:
            return "Preview"
        fd = (getattr(self.app.model.parsed, "folders", {}) or {}).get(self.app.model.selected_folder_id)
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

    def has_real_folders(self) -> bool:
        """Check if there are real folders (not just default folder).

        Returns:
            True if there are real folders to process, False otherwise
        """
        if self.app.model.parsed is None:
            return False
        folders = getattr(self.app.model.parsed, "folders", {}) or {}
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

    @property
    def done_steps(self) -> Set[str]:
        """Get the set of completed steps (read-only)."""
        return self._done_steps.copy()

    def add_done_step(self, step: str) -> None:
        """Mark a step as done."""
        if step in STEPS:
            self._done_steps.add(step)

    def clear_done_steps(self) -> None:
        """Clear all done steps."""
        self._done_steps.clear()

    @property
    def selected_route_keys(self) -> Set[str]:
        """Get the set of selected route keys (read-only)."""
        return self._selected_route_keys.copy()

    def clear_selected_route_keys(self) -> None:
        """Clear all selected route keys."""
        self._selected_route_keys.clear()

    def add_selected_route_key(self, key: str) -> None:
        """Add a route key to selection."""
        self._selected_route_keys.add(key)

    def remove_selected_route_key(self, key: str) -> None:
        """Remove a route key from selection."""
        self._selected_route_keys.discard(key)

    def toggle_selected_route_key(self, key: str) -> None:
        """Toggle a route key in selection."""
        if key in self._selected_route_keys:
            self._selected_route_keys.remove(key)
        else:
            self._selected_route_keys.add(key)

    @property
    def selected_waypoint_keys(self) -> Set[str]:
        """Get the set of selected waypoint keys (read-only)."""
        return self._selected_waypoint_keys.copy()

    def clear_selected_waypoint_keys(self) -> None:
        """Clear all selected waypoint keys."""
        self._selected_waypoint_keys.clear()

    def add_selected_waypoint_key(self, key: str) -> None:
        """Add a waypoint key to selection."""
        self._selected_waypoint_keys.add(key)

    def remove_selected_waypoint_key(self, key: str) -> None:
        """Remove a waypoint key from selection."""
        self._selected_waypoint_keys.discard(key)

    def toggle_selected_waypoint_key(self, key: str) -> None:
        """Toggle a waypoint key in selection."""
        if key in self._selected_waypoint_keys:
            self._selected_waypoint_keys.remove(key)
        else:
            self._selected_waypoint_keys.add(key)

    @property
    def selected_folders(self) -> Set[str]:
        """Get the set of selected folder IDs (read-only)."""
        return self._selected_folders.copy()

    def clear_selected_folders(self) -> None:
        """Clear all selected folders."""
        self._selected_folders.clear()

    def add_selected_folder(self, folder_id: str) -> None:
        """Add a folder ID to selection."""
        self._selected_folders.add(folder_id)

    def remove_selected_folder(self, folder_id: str) -> None:
        """Remove a folder ID from selection."""
        self._selected_folders.discard(folder_id)

    def toggle_selected_folder(self, folder_id: str) -> None:
        """Toggle a folder ID in selection."""
        if folder_id in self._selected_folders:
            self._selected_folders.remove(folder_id)
        else:
            self._selected_folders.add(folder_id)


__all__ = ["StateManager"]
