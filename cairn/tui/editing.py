"""Editing operations for the TUI module.

This module consolidates feature editing logic for waypoints and routes.
"""

from typing import Optional, List, Tuple, Any, Callable

from cairn.core.color_mapper import ColorMapper
from cairn.core.config import normalize_onx_icon_name
from cairn.tui.edit_screens import EditContext
from cairn.tui.debug import agent_log as _agent_log


class EditManager:
    """Manages feature editing operations.

    Centralizes edit context tracking, feature selection, and edit application.
    UI overlay interactions remain in app.py for tight Textual integration.
    """

    def __init__(self, app) -> None:
        """Initialize edit manager.

        Args:
            app: The CairnTuiApp instance
        """
        self.app = app
        # Edit state tracking
        self._in_single_item_edit: bool = False
        self._in_inline_edit: bool = False

    @property
    def in_single_item_edit(self) -> bool:
        """Check if we're editing a single item."""
        return self._in_single_item_edit

    @in_single_item_edit.setter
    def in_single_item_edit(self, value: bool) -> None:
        """Set single item edit state."""
        self._in_single_item_edit = value

    @property
    def in_inline_edit(self) -> bool:
        """Check if inline edit overlay is active."""
        return self._in_inline_edit

    @in_inline_edit.setter
    def in_inline_edit(self, value: bool) -> None:
        """Set inline edit state."""
        self._in_inline_edit = value

    def selected_keys_for_step(self) -> Optional[EditContext]:
        """Get EditContext for the current step's selection.

        Returns:
            EditContext if items are selected, None otherwise
        """
        if self.app.step == "Routes":
            if not self.app._selected_route_keys:
                return None
            return EditContext(kind="route", selected_keys=tuple(sorted(self.app._selected_route_keys)))
        if self.app.step == "Waypoints":
            if not self.app._selected_waypoint_keys:
                return None
            return EditContext(kind="waypoint", selected_keys=tuple(sorted(self.app._selected_waypoint_keys)))
        return None

    def selected_features(self, ctx: EditContext) -> List[Any]:
        """Get selected features for context.

        Args:
            ctx: Edit context with kind and selected keys

        Returns:
            List of selected features
        """
        tracks, waypoints = self.app._current_folder_features()
        out: List[Any] = []

        if ctx.kind == "route":
            by_id = {self.app._feature_row_key(t, ""): t for t in tracks}
            sorted_tracks = sorted(tracks, key=lambda trk: str(getattr(trk, "title", "") or "Untitled").lower())
            for k in ctx.selected_keys:
                kk = str(k)
                if kk in by_id:
                    out.append(by_id[kk])
                    continue
                # Back-compat / safety: allow index-based keys if present
                if kk.isdigit():
                    idx = int(kk)
                    if 0 <= idx < len(sorted_tracks):
                        out.append(sorted_tracks[idx])
            return out

        if ctx.kind == "waypoint":
            by_id = {self.app._feature_row_key(w, ""): w for w in waypoints}
            sorted_waypoints = sorted(waypoints, key=lambda wp: str(getattr(wp, "title", "") or "Untitled").lower())
            for k in ctx.selected_keys:
                kk = str(k)
                if kk in by_id:
                    out.append(by_id[kk])
                    continue
                if kk.isdigit():
                    idx = int(kk)
                    if 0 <= idx < len(sorted_waypoints):
                        out.append(sorted_waypoints[idx])
            return out

        return out

    def apply_edit_payload(self, payload: object) -> bool:
        """Apply a bulk edit.

        Args:
            payload: Edit payload dict with action, value, ctx

        Returns:
            True if changes were applied
        """
        if not isinstance(payload, dict):
            return False

        action = str(payload.get("action") or "").strip().lower()
        value = payload.get("value")
        ctx = payload.get("ctx")

        if not isinstance(ctx, EditContext):
            # Defensive: older tests may pass ctx separately
            ctx2 = self.selected_keys_for_step()
            if ctx2 is None:
                return False
            ctx = ctx2

        feats = self.selected_features(ctx)
        if not feats:
            return False

        changed = False

        if action == "rename":
            new_title = str(value or "").strip()
            if not new_title:
                return False
            # For multi-rename, caller should handle confirmation first
            # This method applies unconditionally
            for f in feats:
                setattr(f, "title", new_title)
            changed = True

        elif action == "description":
            new_desc = self.app._decode_multiline_hint(str(value or "").strip())
            if not new_desc:
                return False
            for f in feats:
                setattr(f, "description", new_desc)
            changed = True

        elif action == "color":
            rgba = str(value or "").strip()
            if not rgba:
                return False
            if ctx.kind == "route":
                hex_color = self.app._rgba_to_hex_hash(rgba)
                for f in feats:
                    setattr(f, "stroke", hex_color)
                changed = True
            elif ctx.kind == "waypoint":
                hex_nohash = self.app._rgba_to_hex_nohash(rgba)
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
                    from cairn.tui.edit_screens import InfoModal
                    self.app.push_screen(InfoModal(f"Invalid icon: {raw}"))
                    return False
                for f in feats:
                    try:
                        props = getattr(f, "properties", None)
                        if not isinstance(props, dict):
                            continue
                        props["cairn_onx_icon_override"] = canon
                        changed = True
                    except Exception:
                        continue

        if changed:
            self._mark_edited(ctx)

        return changed

    def _mark_edited(self, ctx: EditContext) -> None:
        """Mark the appropriate step as edited.

        Args:
            ctx: Edit context
        """
        if ctx.kind == "route":
            self.app._routes_edited = True
        elif ctx.kind == "waypoint":
            self.app._waypoints_edited = True

    def apply_rename_to_features(self, feats: List[Any], new_title: str) -> None:
        """Apply rename to a list of features directly.

        Used after confirmation for multi-rename.

        Args:
            feats: Features to rename
            new_title: New title to apply
        """
        for f in list(feats or []):
            try:
                setattr(f, "title", str(new_title))
                # Best-effort keep properties in sync for ParsedFeature
                props = getattr(f, "properties", None)
                if isinstance(props, dict):
                    props["title"] = str(new_title)
            except Exception:
                continue

    def close_edit_mode(self) -> None:
        """Close edit mode and clear selection.

        Resets edit state and clears the selection for the current step.
        """
        self._in_single_item_edit = False
        self._in_inline_edit = False

        try:
            if self.app.step == "Routes":
                self.app._selected_route_keys.clear()
                self.app._refresh_routes_table()
            elif self.app.step == "Waypoints":
                self.app._selected_waypoint_keys.clear()
                self.app._refresh_waypoints_table()
        except Exception:
            pass

    def refresh_after_edit(self, ctx: EditContext) -> None:
        """Refresh tables after an edit.

        Clears selection unless inline edit is active.

        Args:
            ctx: Edit context
        """
        if ctx.kind == "route":
            if not self._in_inline_edit:
                self.app._selected_route_keys.clear()
            self.app._refresh_routes_table()
        elif ctx.kind == "waypoint":
            if not self._in_inline_edit:
                self.app._selected_waypoint_keys.clear()
            self.app._refresh_waypoints_table()
        elif self.app.step == "Preview":
            self.app._render_main()


__all__ = ["EditManager"]
