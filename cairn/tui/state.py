"""State management for the TUI module.

This module manages workflow state, navigation, and selection tracking.
The reactive `step` property remains on CairnTuiApp for automatic UI updates.
"""

from typing import Set
from collections.abc import MutableSet

from cairn.tui.models import STEPS


class _MutableSetProxy(MutableSet):
    """Proxy for a set that forwards mutations to StateManager methods.

    This allows the compatibility layer to maintain encapsulation (read-only
    via properties) while still supporting mutations for backward compatibility.
    """

    def __init__(self, manager, getter_name: str, add_method, remove_method, clear_method):
        """Initialize proxy.

        Args:
            manager: The StateManager instance
            getter_name: Name of the getter property (e.g., 'done_steps')
            add_method: Method to call for add operations
            remove_method: Method to call for remove/discard operations
            clear_method: Method to call for clear operations
        """
        self._manager = manager
        self._getter_name = getter_name
        self._add_method = add_method
        self._remove_method = remove_method
        self._clear_method = clear_method

    def __contains__(self, item):
        return item in getattr(self._manager, self._getter_name)

    def __iter__(self):
        return iter(getattr(self._manager, self._getter_name))

    def __len__(self):
        return len(getattr(self._manager, self._getter_name))

    def add(self, item):
        """Add an item to the set."""
        self._add_method(item)

    def discard(self, item):
        """Remove an item from the set if present."""
        self._remove_method(item)

    def remove(self, item):
        """Remove an item from the set, raising KeyError if not present."""
        if item not in self:
            raise KeyError(item)
        self._remove_method(item)

    def clear(self):
        """Remove all items from the set."""
        self._clear_method()

    def update(self, other):
        """Update the set with items from other."""
        for item in other:
            self._add_method(item)

    def __repr__(self):
        return repr(getattr(self._manager, self._getter_name))

    def __eq__(self, other):
        """Compare with another set."""
        return getattr(self._manager, self._getter_name) == other

    def __ne__(self, other):
        """Compare with another set."""
        return not (self == other)


class StateManager:
    """Manages workflow state and navigation.

    Key constraint: The reactive `step` property MUST stay on CairnTuiApp
    for automatic UI updates. StateManager handles logic; App holds the reactive property.

    Import-direction rule: this module must remain logic-only (no Textual/widget imports).
    UI concerns like rendering, focus management, and footer updates must live on the App.
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
        """Get the set of completed steps (read-only copy)."""
        return self._done_steps.copy()

    @property
    def done_steps_mutable(self) -> MutableSet[str]:
        """Get a mutable proxy for done steps (for compatibility layer only)."""
        return _MutableSetProxy(
            self,
            'done_steps',
            self.add_done_step,
            lambda step: self._done_steps.discard(step),
            self.clear_done_steps,
        )

    def add_done_step(self, step: str) -> None:
        """Mark a step as done."""
        if step in STEPS:
            self._done_steps.add(step)

    def clear_done_steps(self) -> None:
        """Clear all done steps."""
        self._done_steps.clear()

    def set_done_steps(self, steps: Set[str]) -> None:
        """Set the entire set of done steps (for compatibility layer)."""
        self._done_steps.clear()
        for step in steps:
            if step in STEPS:
                self._done_steps.add(step)

    @property
    def selected_route_keys(self) -> Set[str]:
        """Get the set of selected route keys (read-only copy)."""
        return self._selected_route_keys.copy()

    @property
    def selected_route_keys_mutable(self) -> MutableSet[str]:
        """Get a mutable proxy for selected route keys (for compatibility layer only)."""
        return _MutableSetProxy(
            self,
            'selected_route_keys',
            self.add_selected_route_key,
            self.remove_selected_route_key,
            self.clear_selected_route_keys,
        )

    def clear_selected_route_keys(self) -> None:
        """Clear all selected route keys."""
        self._selected_route_keys.clear()

    def set_selected_route_keys(self, keys: Set[str]) -> None:
        """Set the entire set of selected route keys (for compatibility layer)."""
        self._selected_route_keys.clear()
        self._selected_route_keys.update(keys)

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
        """Get the set of selected waypoint keys (read-only copy)."""
        return self._selected_waypoint_keys.copy()

    @property
    def selected_waypoint_keys_mutable(self) -> MutableSet[str]:
        """Get a mutable proxy for selected waypoint keys (for compatibility layer only)."""
        return _MutableSetProxy(
            self,
            'selected_waypoint_keys',
            self.add_selected_waypoint_key,
            self.remove_selected_waypoint_key,
            self.clear_selected_waypoint_keys,
        )

    def clear_selected_waypoint_keys(self) -> None:
        """Clear all selected waypoint keys."""
        self._selected_waypoint_keys.clear()

    def set_selected_waypoint_keys(self, keys: Set[str]) -> None:
        """Set the entire set of selected waypoint keys (for compatibility layer)."""
        self._selected_waypoint_keys.clear()
        self._selected_waypoint_keys.update(keys)

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
        """Get the set of selected folder IDs (read-only copy)."""
        return self._selected_folders.copy()

    @property
    def selected_folders_mutable(self) -> MutableSet[str]:
        """Get a mutable proxy for selected folders (for compatibility layer only)."""
        return _MutableSetProxy(
            self,
            'selected_folders',
            self.add_selected_folder,
            self.remove_selected_folder,
            self.clear_selected_folders,
        )

    def clear_selected_folders(self) -> None:
        """Clear all selected folders."""
        self._selected_folders.clear()

    def set_selected_folders(self, folder_ids: Set[str]) -> None:
        """Set the entire set of selected folder IDs (for compatibility layer)."""
        self._selected_folders.clear()
        self._selected_folders.update(folder_ids)

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
