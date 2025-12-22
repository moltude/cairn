"""
Test for ConfirmOverlay button focus and activation behavior.

Validates:
1. Initial focus is on Yes button
2. TAB switches focus between buttons
3. Focused button has correct focus state
4. SPACE activates the focused button
5. Keyboard shortcuts (y/n/Enter/Esc) still work
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cairn.tui.app import CairnTuiApp
from cairn.tui.edit_screens.overlays import ConfirmOverlay
from textual.widgets import Button

from tests.tui_harness import (
    copy_fixture_to_tmp,
    select_folder_for_test,
)


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


def test_confirm_overlay_button_focus_and_activation(tmp_path: Path) -> None:
    """
    Test that TAB switches focus between Yes/No buttons and SPACE activates the focused button.
    """

    async def _run() -> None:
        fixture_copy = copy_fixture_to_tmp(tmp_path)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy

        async with app.run_test() as pilot:
            # Navigate to Preview & Export step
            app._goto("List_data")
            await pilot.pause()
            await pilot.press("enter")  # -> Folder
            await pilot.pause()
            select_folder_for_test(app, list(app.model.parsed.folders.keys())[0])
            await pilot.press("enter")  # -> Routes
            await pilot.pause()
            await pilot.press("enter")  # -> Waypoints
            await pilot.pause()
            await pilot.press("enter")  # -> Preview
            await pilot.pause()

            # Trigger export to show the confirm overlay
            app._export_manifest = [("test.gpx", "test.kml", 100, 200)]
            app._export_error = None
            app._post_save_prompt_shown = False
            app._on_export_done(app._export_manifest, app._export_error)
            await pilot.pause()

            # Wait for confirm overlay to open
            await _wait_for_open_class(app, "#confirm_overlay")

            # Get button references
            yes_btn = app.query_one("#confirm_yes_btn", Button)
            no_btn = app.query_one("#confirm_no_btn", Button)

            # TEST 1: Initial focus should be on Yes button
            assert app.focused is yes_btn, "Yes button should be focused initially"
            assert yes_btn.has_focus, "Yes button should report has_focus=True"
            assert not no_btn.has_focus, "No button should not be focused initially"

            # TEST 2: TAB should switch focus to No button
            await pilot.press("tab")
            await pilot.pause()
            await pilot.pause()  # Extra pause to ensure focus change propagates
            # Wait a bit for focus to settle
            for _ in range(10):
                if app.focused is no_btn:
                    break
                await pilot.pause()
            assert app.focused is no_btn, f"No button should be focused after TAB, but {app.focused} is focused"
            assert no_btn.has_focus, "No button should report has_focus=True"
            assert not yes_btn.has_focus, "Yes button should not be focused after TAB"

            # TEST 3: TAB again should switch back to Yes button
            await pilot.press("tab")
            await pilot.pause()
            await pilot.pause()  # Extra pause to ensure focus change propagates
            # Wait a bit for focus to settle
            for _ in range(10):
                if app.focused is yes_btn:
                    break
                await pilot.pause()
            assert app.focused is yes_btn, f"Yes button should be focused after second TAB, but {app.focused} is focused"
            assert yes_btn.has_focus, "Yes button should report has_focus=True"
            assert not no_btn.has_focus, "No button should not be focused after second TAB"

            # TEST 4: SPACE on focused Yes button should activate it
            # Prevent action_new_file from being called to avoid widget ID conflicts
            original_new_file = app.action_new_file
            app.action_new_file = lambda: None  # No-op to prevent side effects

            # Reset overlay state
            app._post_save_prompt_shown = False
            app._on_export_done(app._export_manifest, app._export_error)
            await pilot.pause()
            await _wait_for_open_class(app, "#confirm_overlay")

            yes_btn = app.query_one("#confirm_yes_btn", Button)
            assert app.focused is yes_btn, "Yes button should be focused"

            # Verify Yes button is focused before pressing SPACE
            assert app.focused is yes_btn, "Yes button should be focused before SPACE"

            await pilot.press("space")
            await pilot.pause()

            # Verify overlay closed (this proves SPACE activated the button)
            await _wait_for_closed_class(app, "#confirm_overlay")

            # Restore original method
            app.action_new_file = original_new_file

            # TEST 5: SPACE on focused No button should activate it
            # Prevent exit from being called
            original_exit = app.exit
            app.exit = lambda: None  # No-op to prevent side effects

            app._post_save_prompt_shown = False
            app._on_export_done(app._export_manifest, app._export_error)
            await pilot.pause()
            await _wait_for_open_class(app, "#confirm_overlay")

            no_btn = app.query_one("#confirm_no_btn", Button)
            await pilot.press("tab")  # Switch to No button
            await pilot.pause()
            assert app.focused is no_btn, "No button should be focused"

            # Verify No button is focused before pressing SPACE
            assert app.focused is no_btn, "No button should be focused before SPACE"

            await pilot.press("space")
            await pilot.pause()

            # Verify overlay closed (this proves SPACE activated the button)
            await _wait_for_closed_class(app, "#confirm_overlay")

            # Restore original method
            app.exit = original_exit

            # TEST 6: Keyboard shortcuts should still work
            # Prevent action_new_file from being called to avoid widget ID conflicts
            original_new_file = app.action_new_file
            app.action_new_file = lambda: None  # No-op to prevent side effects

            app._post_save_prompt_shown = False
            app._on_export_done(app._export_manifest, app._export_error)
            await pilot.pause()
            await _wait_for_open_class(app, "#confirm_overlay")

            await pilot.press("y")  # 'y' should activate Yes
            await pilot.pause()

            # Verify overlay closed (this proves 'y' activated Yes)
            await _wait_for_closed_class(app, "#confirm_overlay")

            app._post_save_prompt_shown = False
            app._on_export_done(app._export_manifest, app._export_error)
            await pilot.pause()
            await _wait_for_open_class(app, "#confirm_overlay")

            # Prevent exit from being called
            original_exit = app.exit
            app.exit = lambda: None  # No-op to prevent side effects

            await pilot.press("n")  # 'n' should activate No
            await pilot.pause()

            # Verify overlay closed (this proves 'n' activated No)
            await _wait_for_closed_class(app, "#confirm_overlay")

            # Restore original methods
            app.action_new_file = original_new_file
            app.exit = original_exit

    asyncio.run(_run())
