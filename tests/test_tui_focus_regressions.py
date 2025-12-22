from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import Input

from tests.tui_harness import get_tui_two_waypoints_fixture, select_folder_for_test


def _pick_first_folder_id(app) -> str:
    assert app.model.parsed is not None, "Expected parsed data after List_data render"
    folders = getattr(app.model.parsed, "folders", {}) or {}
    assert folders, "Expected at least one folder in parsed data"
    return next(iter(folders.keys()))


def _select_first_folder(app) -> str:
    """Pick and select the first folder (handles multi-folder datasets)."""
    folder_id = _pick_first_folder_id(app)
    select_folder_for_test(app, folder_id)
    return folder_id


async def _wait_for_open_class(app, selector: str, *, max_steps: int = 60) -> None:
    for _ in range(max_steps):
        try:
            w = app.query_one(selector)
            if getattr(w, "has_class", lambda _c: False)("open"):
                return
        except Exception:
            pass
        await asyncio.sleep(0)
    raise AssertionError(f"Timed out waiting for {selector}.open")


async def _wait_for_closed_class(app, selector: str, *, max_steps: int = 60) -> None:
    for _ in range(max_steps):
        try:
            w = app.query_one(selector)
            if not getattr(w, "has_class", lambda _c: False)("open"):
                return
        except Exception:
            # Treat missing widget as closed.
            return
        await asyncio.sleep(0)
    raise AssertionError(f"Timed out waiting for {selector} to close")


def test_multi_waypoint_rename_cancel_restores_inline_field_focus(tmp_path: Path) -> None:
    """
    Regression for reported bug:
    - Multi-select 2 waypoints
    - Rename (with confirm)
    - Accidentally re-enter rename (Enter)
    - Esc cancel should restore focus to inline field list (so ↑/↓ works)
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        app = CairnTuiApp()
        app.model.input_path = get_tui_two_waypoints_fixture()

        async with app.run_test() as pilot:
            # Parse so folders/waypoints are available.
            app._goto("List_data")
            await pilot.pause()
            _select_first_folder(app)

            app._goto("Waypoints")
            await pilot.pause()
            assert app.step == "Waypoints"

            # Select 2 waypoints.
            app.action_focus_table()
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            assert len(app._selected_waypoint_keys) == 2

            # Open inline overlay.
            await pilot.press("a")
            await pilot.pause()
            await _wait_for_open_class(app, "#inline_edit_overlay")

            # Enter on "Name" -> rename overlay.
            await pilot.press("enter")
            await pilot.pause()
            await _wait_for_open_class(app, "#rename_overlay")

            # Submit a multi-rename (triggers confirm overlay).
            app.query_one("#rename_value", Input).value = "Campsite"
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await _wait_for_open_class(app, "#confirm_overlay")

            # Confirm yes (Enter).
            await pilot.press("enter")
            await pilot.pause()
            await _wait_for_open_class(app, "#inline_edit_overlay")

            # Accidental Enter again -> reopen rename overlay.
            await pilot.press("enter")
            await pilot.pause()
            await _wait_for_open_class(app, "#rename_overlay")

            # Esc cancel should return to inline overlay AND restore focus to fields table.
            await pilot.press("escape")
            await pilot.pause()
            await _wait_for_closed_class(app, "#rename_overlay")
            await _wait_for_open_class(app, "#inline_edit_overlay")

            focused = getattr(app, "focused", None)
            assert focused is not None
            assert getattr(focused, "id", None) == "fields_table"

            # Prove navigation works (not "frozen"): Down changes cursor row.
            tbl = app.query_one("#fields_table")
            before = int(getattr(tbl, "cursor_row", 0) or 0)
            await pilot.press("down")
            await pilot.pause()
            after = int(getattr(tbl, "cursor_row", 0) or 0)
            assert after != before, f"Expected cursor to move after Down (before={before}, after={after})"

            # Esc from inline overlay should not navigate steps.
            prev_step = app.step
            await pilot.press("escape")
            await pilot.pause()
            assert app.step == prev_step

    asyncio.run(_run())


def test_escape_does_not_navigate_steps_when_inline_overlay_visible_and_unfocused(tmp_path: Path) -> None:
    """
    Regression: even if focus is lost, Esc/back must not navigate the stepper while
    an inline edit overlay is visible.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        app = CairnTuiApp()
        app.model.input_path = get_tui_two_waypoints_fixture()

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()
            _select_first_folder(app)

            app._goto("Waypoints")
            await pilot.pause()
            assert app.step == "Waypoints"

            # Select one waypoint and open inline overlay.
            app.action_focus_table()
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await _wait_for_open_class(app, "#inline_edit_overlay")

            # Simulate focus loss (the core of the reported "screen feels frozen" state).
            try:
                app.set_focus(None)  # type: ignore[arg-type]
            except Exception:
                pass
            await pilot.pause()

            prev_step = app.step
            await pilot.press("escape")
            await pilot.pause()

            # Must not move through steps (Waypoints -> Folder, etc).
            assert app.step == prev_step

            # Inline overlay should be dismissed (best-effort behavior for Esc/back).
            await _wait_for_closed_class(app, "#inline_edit_overlay")

    asyncio.run(_run())
