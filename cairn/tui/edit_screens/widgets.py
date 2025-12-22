"""Custom input widgets for edit screens."""

from __future__ import annotations

from typing import Optional

from textual.widgets import DataTable, Input

from cairn.tui.edit_screens.shared import EditContext, _table_cursor_row_key


class _IconSearchInput(Input):
    """
    Icon filter input that supports arrow navigation without requiring focus changes.

    Textual's Input consumes Up/Down when focused; this widget instead uses those keys
    to move the icon list selection while still allowing normal typing.
    """

    def _get_icon_table(self) -> Optional[DataTable]:
        """Get the icon table from the parent screen."""
        screen = getattr(self, "screen", None)
        if screen is None:
            return None
        try:
            return screen.query_one("#icon_table", DataTable)  # type: ignore[no-any-return]
        except Exception:
            return None

    def _move_table_cursor(self, delta: int) -> None:
        """Move the icon table cursor by delta rows."""
        tbl = self._get_icon_table()
        if tbl is None:
            return
        try:
            row_count = int(getattr(tbl, "row_count", 0) or 0)
        except Exception:
            row_count = 0
        if row_count <= 0:
            return

        # Use action methods if available (preferred), otherwise try move_cursor
        if delta > 0:
            for _ in range(abs(delta)):
                try:
                    tbl.action_cursor_down()
                except Exception:
                    break
        elif delta < 0:
            for _ in range(abs(delta)):
                try:
                    tbl.action_cursor_up()
                except Exception:
                    break

    async def _on_key(self, event) -> None:
        """Override _on_key to intercept arrow keys before Input handles them."""
        key = str(getattr(event, "key", "") or "")

        # Handle up/down arrows for table navigation
        if key in ("up", "down"):
            delta = -1 if key == "up" else 1
            self._move_table_cursor(delta)
            event.stop()
            event.prevent_default()
            return

        screen = getattr(self, "screen", None)

        # Escape closes the modal
        if key == "escape" and screen is not None:
            try:
                screen.dismiss(None)
            except Exception:
                pass
            event.stop()
            event.prevent_default()
            return

        # Enter applies the current selection - but DON'T block Input's submit action
        # Let the modal handle enter via its own on_key handler
        if key in ("enter", "return"):
            # Don't call super() for enter - let it bubble to modal
            event.stop()
            if screen is not None:
                ctx = getattr(screen, "_ctx", None)
                tbl = self._get_icon_table()
                if isinstance(ctx, EditContext) and tbl is not None:
                    icon = (_table_cursor_row_key(tbl) or "").strip()
                    if icon:
                        try:
                            screen.dismiss({"action": "icon", "value": icon, "ctx": ctx})
                        except Exception:
                            pass
            return

        # All other keys go to the default Input handler for typing
        await super()._on_key(event)

    def on_key(self, event) -> None:
        """Backup handler for keys not caught by _on_key."""
        key = str(getattr(event, "key", "") or "")

        # Handle up/down arrows for table navigation
        if key in ("up", "down"):
            delta = -1 if key == "up" else 1
            self._move_table_cursor(delta)
            try:
                event.stop()
            except Exception:
                pass
            return


class _SymbolSearchInput(Input):
    """Custom input that lets arrow keys pass through for table navigation."""

    def on_key(self, event) -> None:  # type: ignore[override]
        key = str(getattr(event, "key", "") or "")
        # Let up/down/enter/escape propagate to parent modal
        if key in ("up", "down", "escape", "enter", "return"):
            return
        # All other keys are handled by the input for typing
        pass

