"""Protocol definitions for manager interfaces.

This module defines Protocol types for manager classes to enable
type checking and future extensibility without tight coupling.
"""

from typing import Protocol, Set, Optional
from collections.abc import MutableSet
from pathlib import Path

from textual.widgets import DataTable
from rich.text import Text


class StateManagerProtocol(Protocol):
    """Protocol for StateManager interface."""

    def goto(self, step: str) -> None:
        """Navigate to a step."""
        ...

    def get_next_step_after_folder(self) -> str:
        """Determine next step after Folder."""
        ...

    def has_real_folders(self) -> bool:
        """Check if there are real folders."""
        ...

    @property
    def done_steps(self) -> Set[str]:
        """Get the set of completed steps."""
        ...

    @property
    def done_steps_mutable(self) -> MutableSet[str]:
        """Get a mutable proxy for done steps."""
        ...

    def add_done_step(self, step: str) -> None:
        """Mark a step as done."""
        ...

    def clear_done_steps(self) -> None:
        """Clear all done steps."""
        ...

    def set_done_steps(self, steps: Set[str]) -> None:
        """Set the entire set of done steps."""
        ...

    @property
    def selected_route_keys(self) -> Set[str]:
        """Get the set of selected route keys."""
        ...

    @property
    def selected_route_keys_mutable(self) -> MutableSet[str]:
        """Get a mutable proxy for selected route keys."""
        ...

    def clear_selected_route_keys(self) -> None:
        """Clear all selected route keys."""
        ...

    def set_selected_route_keys(self, keys: Set[str]) -> None:
        """Set the entire set of selected route keys."""
        ...

    def add_selected_route_key(self, key: str) -> None:
        """Add a route key to selection."""
        ...

    def remove_selected_route_key(self, key: str) -> None:
        """Remove a route key from selection."""
        ...

    def toggle_selected_route_key(self, key: str) -> None:
        """Toggle a route key in selection."""
        ...

    @property
    def selected_waypoint_keys(self) -> Set[str]:
        """Get the set of selected waypoint keys."""
        ...

    @property
    def selected_waypoint_keys_mutable(self) -> MutableSet[str]:
        """Get a mutable proxy for selected waypoint keys."""
        ...

    def clear_selected_waypoint_keys(self) -> None:
        """Clear all selected waypoint keys."""
        ...

    def set_selected_waypoint_keys(self, keys: Set[str]) -> None:
        """Set the entire set of selected waypoint keys."""
        ...

    def add_selected_waypoint_key(self, key: str) -> None:
        """Add a waypoint key to selection."""
        ...

    def remove_selected_waypoint_key(self, key: str) -> None:
        """Remove a waypoint key from selection."""
        ...

    def toggle_selected_waypoint_key(self, key: str) -> None:
        """Toggle a waypoint key in selection."""
        ...

    @property
    def selected_folders(self) -> Set[str]:
        """Get the set of selected folder IDs."""
        ...

    @property
    def selected_folders_mutable(self) -> MutableSet[str]:
        """Get a mutable proxy for selected folders."""
        ...

    def clear_selected_folders(self) -> None:
        """Clear all selected folders."""
        ...

    def set_selected_folders(self, folder_ids: Set[str]) -> None:
        """Set the entire set of selected folder IDs."""
        ...

    def add_selected_folder(self, folder_id: str) -> None:
        """Add a folder ID to selection."""
        ...

    def remove_selected_folder(self, folder_id: str) -> None:
        """Remove a folder ID from selection."""
        ...

    def toggle_selected_folder(self, folder_id: str) -> None:
        """Toggle a folder ID in selection."""
        ...


class TableManagerProtocol(Protocol):
    """Protocol for TableManager interface."""

    @staticmethod
    def cursor_row_key(table: DataTable) -> Optional[str]:
        """Get row key at cursor position."""
        ...

    @staticmethod
    def clear_rows(table: DataTable) -> None:
        """Clear all rows from a DataTable."""
        ...

    def color_chip(self, rgba: str) -> Text:
        """Create a color chip widget for display in tables."""
        ...

    def resolved_waypoint_icon(self, wp: object) -> str:
        """Resolve the OnX icon for a waypoint."""
        ...

    def resolved_waypoint_color(self, wp: object, icon: str) -> str:
        """Resolve the OnX color for a waypoint."""
        ...

    def refresh_folder_table(self) -> Optional[int]:
        """Refresh the folder table."""
        ...

    def refresh_waypoints_table(self) -> None:
        """Refresh the waypoints table."""
        ...

    def refresh_routes_table(self) -> None:
        """Refresh the routes table."""
        ...


class FileBrowserManagerProtocol(Protocol):
    """Protocol for FileBrowserManager interface."""

    def use_tree_browser(self) -> bool:
        """Check if tree browser A/B test is enabled."""
        ...

    def get_initial_directory(self) -> Path:
        """Get initial directory for file browser."""
        ...

    def get_file_browser_dir(self) -> Optional[Path]:
        """Get current file browser directory."""
        ...

    def set_file_browser_dir(self, path: Optional[Path]) -> None:
        """Set current file browser directory."""
        ...

    def refresh_file_browser(self) -> None:
        """Populate Select_file file browser table."""
        ...

    def file_browser_enter(self) -> None:
        """Handle Enter on Select_file file browser table."""
        ...


__all__ = [
    "StateManagerProtocol",
    "TableManagerProtocol",
    "FileBrowserManagerProtocol",
]
