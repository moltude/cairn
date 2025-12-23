"""Shared utilities and data models for edit screens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from textual.widgets import DataTable


@dataclass(frozen=True)
class EditContext:
    kind: str  # "route" | "waypoint"
    selected_keys: tuple[str, ...]


def validate_folder_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate folder name for security and filesystem compatibility.

    Returns:
        (is_valid, error_message) - error_message is None if valid
    """
    if not name or not name.strip():
        return False, "Folder name cannot be empty"

    # Check for leading/trailing spaces or dots BEFORE stripping (problematic on some filesystems)
    if name != name.strip() or name.strip().startswith('.') or name.strip().endswith('.'):
        return False, "Folder name cannot start/end with spaces or dots"

    name = name.strip()

    # Check for path traversal attempts
    if ".." in name:
        return False, "Folder name cannot contain '..'"

    # Check for path separators (both Unix and Windows)
    if "/" in name or "\\" in name:
        return False, "Folder name cannot contain path separators (/ or \\)"

    # Check for other problematic characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
    for char in invalid_chars:
        if char in name:
            return False, f"Folder name cannot contain '{char}'"

    # Check for names that are reserved on Windows
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                      'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                      'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
    if name.upper() in reserved_names:
        return False, f"'{name}' is a reserved name and cannot be used"

    return True, None


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


def _datatable_clear_rows(table: DataTable) -> None:
    """Clear DataTable rows without relying on a single Textual version API."""
    try:
        table.clear()  # type: ignore[no-untyped-call]
        return
    except Exception:
        pass
    try:
        rows = getattr(table, "rows", None) or {}
        for rk in list(rows.keys()):
            try:
                table.remove_row(rk)  # type: ignore[no-untyped-call]
            except Exception:
                pass
    except Exception:
        pass


