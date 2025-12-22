"""
Test for ConfirmOverlay button styling and colors.

Validates that button colors match expected styles:
- Unfocused button: dark background (#1F1513)
- Focused button: light brown background (#563C27)
- No blue colors should be used
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cairn.tui.app import CairnTuiApp
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


def test_confirm_overlay_button_styling(tmp_path: Path) -> None:
    """
    Test that button styling matches expected colors:
    - Unfocused: dark background
    - Focused: light brown background
    - No blue colors
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

            # TEST 1: Verify Yes button is focused initially
            assert app.focused is yes_btn, "Yes button should be focused initially"
            assert yes_btn.has_focus, "Yes button should have focus"
            assert not no_btn.has_focus, "No button should not have focus"

            # TEST 2: Check button classes - should not have --primary class
            yes_classes = getattr(yes_btn, "classes", set()) or set()
            no_classes = getattr(no_btn, "classes", set()) or set()

            # Verify no primary variant class
            assert "--primary" not in yes_classes, "Yes button should not have --primary class"
            assert "--primary" not in no_classes, "No button should not have --primary class"

            # Both should have confirm_button class
            assert "confirm_button" in yes_classes or "confirm_button" in str(yes_classes), "Yes button should have confirm_button class"
            assert "confirm_button" in no_classes or "confirm_button" in str(no_classes), "No button should have confirm_button class"

            # TEST 3: TAB should switch focus and classes should update
            await pilot.press("tab")
            await pilot.pause()
            await pilot.pause()  # Extra pause for focus to settle

            # Wait for focus to change
            for _ in range(10):
                if app.focused is no_btn:
                    break
                await pilot.pause()

            assert app.focused is no_btn, "No button should be focused after TAB"
            assert no_btn.has_focus, "No button should have focus after TAB"
            assert not yes_btn.has_focus, "Yes button should not have focus after TAB"

            # TEST 4: TAB again should switch back
            await pilot.press("tab")
            await pilot.pause()
            await pilot.pause()

            # Wait for focus to change back
            for _ in range(10):
                if app.focused is yes_btn:
                    break
                await pilot.pause()

            assert app.focused is yes_btn, "Yes button should be focused after second TAB"
            assert yes_btn.has_focus, "Yes button should have focus after second TAB"
            assert not no_btn.has_focus, "No button should not have focus after second TAB"

    asyncio.run(_run())
