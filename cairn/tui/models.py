"""Data models and constants for the TUI module.

This module contains:
- Widget ID constants (for stable test API)
- Workflow step definitions
- Data models (TuiModel)
- File extension constants
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cairn.core.parser import ParsedData


class WidgetIds:
    """Widget ID constants for stable test API.

    All widget IDs used in the TUI are defined here to prevent test breakage
    when refactoring UI structure.
    """

    # Main layout
    STEPPER = "stepper"
    STATUS = "status"
    SIDEBAR_INSTRUCTIONS = "sidebar_instructions"
    SIDEBAR_SHORTCUTS = "sidebar_shortcuts"
    MAIN_BODY = "main_body"
    MAIN_TITLE = "main_title"
    MAIN_SUBTITLE = "main_subtitle"
    FOOTER = "footer"

    # File browser
    FILE_BROWSER = "file_browser"
    DEFAULT_PATH_WARNING = "default_path_warning"

    # Folder table
    FOLDER_TABLE = "folder_table"

    # Routes table
    ROUTES_TABLE = "routes_table"
    ROUTES_SEARCH = "routes_search"

    # Waypoints table
    WAYPOINTS_TABLE = "waypoints_table"
    WAYPOINTS_SEARCH = "waypoints_search"

    # Preview/Export
    PREVIEW_WAYPOINTS = "preview_waypoints"
    PREVIEW_WAYPOINTS_TITLE = "preview_waypoints_title"
    PREVIEW_ROUTES = "preview_routes"
    PREVIEW_ROUTES_TITLE = "preview_routes_title"
    OUTPUT_PREFIX = "output_prefix"
    EXPORT_DIR_TREE = "export_dir_tree"
    EXPORT_TARGET_SECTION = "export_target_section"
    SAVE_TARGET_OVERLAY = "save_target_overlay"

    # Overlays
    INLINE_EDIT_OVERLAY = "inline_edit_overlay"
    ICON_PICKER_OVERLAY = "icon_picker_overlay"
    COLOR_PICKER_OVERLAY = "color_picker_overlay"
    RENAME_OVERLAY = "rename_overlay"
    DESCRIPTION_OVERLAY = "description_overlay"
    CONFIRM_OVERLAY = "confirm_overlay"

    # Modal screens (for edit_screens.py)
    NEW_FOLDER_MODAL = "new_folder_modal"
    NEW_FOLDER_INPUT = "new_folder_input"
    CREATE_BTN = "create_btn"
    CANCEL_BTN = "cancel_btn"

    # Icon/Color picker search
    ICON_SEARCH = "icon_search"
    COLOR_SEARCH = "color_search"


# Workflow steps (ordered)
STEPS = [
    "Select_file",
    "List_data",
    "Folder",
    "Routes",
    "Waypoints",
    "Preview",  # Preview is now the final step with embedded export
]

# Display labels for steps (internal names use underscores for code references)
STEP_LABELS = {
    "Select_file": "Select file",
    "List_data": "Summary of mapping data",
    "Folder": "Folder",
    "Routes": "Routes",
    "Waypoints": "Waypoints",
    "Preview": "Preview & Export",
}

# File types shown in Select_file tree. (Parsing support may be narrower than visibility.)
_VISIBLE_INPUT_EXTS = {".json", ".geojson", ".kml", ".gpx"}
_PARSEABLE_INPUT_EXTS = {".json", ".geojson"}


@dataclass
class TuiModel:
    """Data model for the TUI application state."""

    input_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    parsed: Optional[ParsedData] = None
    selected_folder_id: Optional[str] = None


# Export constants for use in other modules
__all__ = [
    "WidgetIds",
    "STEPS",
    "STEP_LABELS",
    "_VISIBLE_INPUT_EXTS",
    "_PARSEABLE_INPUT_EXTS",
    "TuiModel",
]
