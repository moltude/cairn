"""Table operations for the TUI module.

This module manages DataTable operations extracted from app.py for better
testability and separation of concerns.
"""

from typing import Optional, TYPE_CHECKING, Any
from textual.widgets import DataTable
from rich.text import Text

from cairn.core.color_mapper import ColorMapper
from cairn.core.mapper import map_icon
from cairn.core.config import get_icon_color

if TYPE_CHECKING:
    from cairn.tui.app import CairnTuiApp

# Import profiling
try:
    from cairn.tui.profiling import profile_operation
except ImportError:
    # Fallback if profiling module not available
    from contextlib import nullcontext as profile_operation


class TableManager:
    """Manages DataTable operations for the TUI."""

    def __init__(self, app: "CairnTuiApp") -> None:
        """Initialize table manager.

        Args:
            app: The CairnTuiApp instance (for accessing model, config, etc.)
        """
        self.app: "CairnTuiApp" = app

    @staticmethod
    def cursor_row_key(table: DataTable) -> Optional[str]:
        """Get row key at cursor position.

        Best-effort current row key at cursor for version-compat.

        Args:
            table: The DataTable to query

        Returns:
            Row key as string, or None if not available
        """
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
            # Textual API version compatibility - fallback if cursor methods don't exist
            pass
        return None

    @staticmethod
    def clear_rows(table: DataTable) -> None:
        """Clear all rows from a DataTable.

        Clear rows without forcing a full screen re-render.
        Textual DataTable APIs vary; we try common variants.

        Args:
            table: The DataTable to clear
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

    def color_chip(self, rgba: str) -> Text:
        """Create a color chip widget for display in tables.

        Args:
            rgba: RGBA color string

        Returns:
            Rich Text object with color chip
        """
        r, g, b = ColorMapper.parse_color(rgba)
        name = ColorMapper.get_color_name(rgba).replace("-", " ").upper()
        chip = Text("■ ", style=f"rgb({r},{g},{b})")
        chip.append(name, style="bold")
        return chip

    def resolved_waypoint_icon(self, wp: Any) -> str:
        """Resolve the OnX icon for a waypoint.

        Checks for override in properties, otherwise uses mapping logic.

        Args:
            wp: Waypoint feature object (ParsedFeature or similar)

        Returns:
            Icon name string
        """
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
        return map_icon(title0, desc0, sym0, self.app._config)

    def resolved_waypoint_color(self, wp: Any, icon: str) -> str:
        """Resolve the OnX color for a waypoint.

        Mirrors cairn/core/writers.py policy.

        Args:
            wp: Waypoint feature object (ParsedFeature or similar)
            icon: Icon name (used for default color lookup)

        Returns:
            RGBA color string
        """
        # Mirror cairn/core/writers.py policy.
        mc_raw = str(getattr(wp, "color", "") or "").strip()
        if mc_raw:
            return ColorMapper.map_waypoint_color(mc_raw)
        return get_icon_color(
            icon,
            default=getattr(self.app._config, "default_color", ColorMapper.DEFAULT_WAYPOINT_COLOR),
        )

    def _feature_row_key(self, feat: Any, index: str) -> str:
        """Generate a stable row key for a feature.

        Creates a unique key for table row identification.

        Args:
            feat: Feature object (route or waypoint, ParsedFeature or similar)
            index: Index string (for uniqueness)

        Returns:
            Row key string
        """
        # Try to use a stable ID if available
        try:
            feat_id = getattr(feat, "id", None)
            if feat_id:
                return str(feat_id)
        except Exception:
            pass

        # Fallback to index-based key
        # Use title + index for uniqueness
        try:
            title = str(getattr(feat, "title", "") or "Untitled")
            return f"{title}_{index}"
        except Exception:
            return f"feature_{index}"

    def refresh_folder_table(self) -> Optional[int]:
        """Refresh the folder table to show updated selection state.

        Returns the target cursor row index if a row key was saved, None otherwise.
        """
        with profile_operation("table_refresh_folder"):
            if self.app.step != "Folder":
                return None
            try:
                table = self.app.query_one("#folder_table", DataTable)
            except Exception:
                return None
            if self.app.model.parsed is None:
                return None

            folders = list((getattr(self.app.model.parsed, "folders", {}) or {}).items())
            if not folders:
                return None

            # Save current cursor position by row key (more reliable than row index)
            current_row_key = None
            try:
                current_row_key = self.cursor_row_key(table)
            except Exception:
                pass

            # Clear rows
            self.clear_rows(table)

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
                    sel = "●" if folder_id in self.app._selected_folders else " "
                    table.add_row(sel, name, str(w), str(t), str(s), key=folder_id)
                else:
                    table.add_row(name, str(w), str(t), str(s), key=folder_id)

                # Track the index of the row we want to restore cursor to
                if current_row_key and str(folder_id) == str(current_row_key):
                    target_row_index = idx

            # Return target index for caller to restore cursor
            return target_row_index if current_row_key and target_row_index is not None else None

    def refresh_waypoints_table(self) -> None:
        """Refresh the waypoints table with current data and filters."""
        with profile_operation("table_refresh_waypoints"):
            if self.app.step != "Waypoints":
                return
            try:
                table = self.app.query_one("#waypoints_table", DataTable)
            except Exception:
                return
            if self.app.model.parsed is None or not self.app.model.selected_folder_id:
                return
            fd = (getattr(self.app.model.parsed, "folders", {}) or {}).get(self.app.model.selected_folder_id)
            waypoints = list((fd or {}).get("waypoints", []) or [])

            q = (self.app._waypoints_filter or "").strip().lower()
            self.clear_rows(table)

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
                sel = "●" if key in self.app._selected_waypoint_keys else " "
                mapped = self.resolved_waypoint_icon(wp)
                rgba = self.resolved_waypoint_color(wp, mapped)
                try:
                    table.add_row(sel, title0, mapped, self.color_chip(rgba), key=key)
                except Exception:
                    name = ColorMapper.get_color_name(rgba).replace("-", " ").upper()
                    table.add_row(sel, title0, mapped, f"■ {name}", key=key)

    def refresh_routes_table(self) -> None:
        """Refresh the routes table with current data and filters."""
        with profile_operation("table_refresh_routes"):
            if self.app.step != "Routes":
                return
            try:
                table = self.app.query_one("#routes_table", DataTable)
            except Exception:
                return
            if self.app.model.parsed is None or not self.app.model.selected_folder_id:
                return
            fd = (getattr(self.app.model.parsed, "folders", {}) or {}).get(self.app.model.selected_folder_id)
            tracks = list((fd or {}).get("tracks", []) or [])

            q = (self.app._routes_filter or "").strip().lower()
            self.clear_rows(table)

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
                sel = "●" if key in self.app._selected_route_keys else " "
                rgba = ColorMapper.map_track_color(str(getattr(trk, "stroke", "") or ""))
                try:
                    color_cell = self.color_chip(rgba)
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


__all__ = ["TableManager"]
