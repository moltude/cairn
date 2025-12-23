"""Edit screens module - re-exports for backward compatibility.

This module consolidates edit screen components that were previously in edit_screens.py.
All classes and functions are re-exported here to maintain backward compatibility.
"""

# Re-export shared utilities
from cairn.tui.edit_screens.shared import (
    EditContext,
    _datatable_clear_rows,
    _table_cursor_row_key,
    validate_folder_name,
)

# Re-export custom widgets
from cairn.tui.edit_screens.widgets import _IconSearchInput, _SymbolSearchInput

# Re-export overlays
from cairn.tui.edit_screens.overlays import (
    ColorPickerOverlay,
    ConfirmOverlay,
    DescriptionOverlay,
    IconPickerOverlay,
    InlineEditOverlay,
    RenameOverlay,
    SaveTargetOverlay,
)

# Re-export modals
from cairn.tui.edit_screens.modals import (
    ColorPickerModal,
    ConfirmModal,
    DescriptionModal,
    HelpModal,
    IconOverrideModal,
    InfoModal,
    NewFolderModal,
    RenameModal,
    UnmappedSymbolModal,
)

__all__ = [
    # Shared utilities
    "EditContext",
    "_datatable_clear_rows",
    "_table_cursor_row_key",
    "validate_folder_name",
    # Custom widgets
    "_IconSearchInput",
    "_SymbolSearchInput",
    # Overlays
    "ColorPickerOverlay",
    "ConfirmOverlay",
    "DescriptionOverlay",
    "IconPickerOverlay",
    "InlineEditOverlay",
    "RenameOverlay",
    "SaveTargetOverlay",
    # Modals
    "ColorPickerModal",
    "ConfirmModal",
    "DescriptionModal",
    "HelpModal",
    "IconOverrideModal",
    "InfoModal",
    "NewFolderModal",
    "RenameModal",
    "UnmappedSymbolModal",
]




