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
# GPX support: CalTopo GPX exports contain only coordinates and names (no icons/colors/folders)
_PARSEABLE_INPUT_EXTS = {".json", ".geojson", ".gpx"}


@dataclass
class TuiModel:
    """Data model for the TUI application state."""

    input_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    parsed: Optional[ParsedData] = None
    selected_folder_id: Optional[str] = None


# Export constants for use in other modules
__all__ = [
    "STEPS",
    "STEP_LABELS",
    "_VISIBLE_INPUT_EXTS",
    "_PARSEABLE_INPUT_EXTS",
    "TuiModel",
]
