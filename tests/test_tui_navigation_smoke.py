from __future__ import annotations

import asyncio

from tests.tui_harness import get_bitterroots_complete_fixture


def test_tui_routes_enter_advances_to_waypoints() -> None:
    """
    Minimal non-visual TUI regression: ensure Enter is not swallowed on Routes step.

    We don't try to drive DirectoryTree here; instead we seed the model directly and
    validate that the app-level Enter binding works when a DataTable is focused.
    """
    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        app = CairnTuiApp()
        async with app.run_test() as pilot:
            # Seed minimal state to reach Routes.
            fixture = get_bitterroots_complete_fixture()
            app.model.input_path = fixture
            # Force parse and set folder id by running through List_data render.
            app._goto("List_data")
            await pilot.pause()
            app.action_continue()  # -> Folder
            await pilot.pause()
            # Continue from Folder (should infer selection even without row event).
            app.action_continue()  # -> Routes
            await pilot.pause()

            assert app.step == "Routes"
            # Press Enter via pilot (should advance to Edit_routes).
            await pilot.press("enter")
            await pilot.pause()
            assert app.step == "Edit_routes"

            # Then Enter should advance to Waypoints.
            await pilot.press("enter")
            await pilot.pause()
            assert app.step == "Waypoints"

    asyncio.run(_run())
