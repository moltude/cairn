"""
Tests that prove the inline editor is a *true overlay* (not a ModalScreen).

Key assertion: while the editor is open, the rendered terminal output should still
contain the underlying step UI (e.g. the word 'Waypoints' or 'Routes').
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from cairn.tui.app import CairnTuiApp
from textual.widgets import DataTable
from tests.tui_harness import copy_fixture_to_tmp


def _rendered_svg(app) -> str:
    # Textual provides export_screenshot() which returns an SVG string of the current UI.
    try:
        return str(app.export_screenshot())
    except Exception:
        return ""


class TestInlineEditOverlayRendering:
    def test_overlay_renders_on_top_of_waypoints(self, tmp_path: Path) -> None:
        fixture_copy = copy_fixture_to_tmp(tmp_path)

        async def _run() -> None:
            app = CairnTuiApp()
            app.model.input_path = fixture_copy

            async with app.run_test() as pilot:
                # Navigate to Waypoints
                app._goto("List_data")
                await pilot.pause()

                if app.model.parsed:
                    folders = getattr(app.model.parsed, "folders", {}) or {}
                    folder_ids = list(folders.keys())
                    if folder_ids:
                        app.model.selected_folder_id = folder_ids[0]

                app._goto("Waypoints")
                await pilot.pause()
                assert app.step == "Waypoints"

                # Select one, open overlay
                app.action_focus_table()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()

                try:
                    overlay = app.screen.query_one("#inline_edit_overlay")
                except Exception:
                    overlay = None
                assert overlay is not None
                assert overlay.has_class("open")

                svg = _rendered_svg(app)
                assert "Waypoints" in svg
                # Overlay-specific tokens (avoid matching footer's "Edit")
                assert "Record" in svg
                assert "Field" in svg
                assert "Value" in svg

        asyncio.run(_run())

    def test_closing_inline_overlay_restores_table_focus(self, tmp_path: Path) -> None:
        """After closing the inline overlay, focus should return to the underlying table."""
        fixture_copy = copy_fixture_to_tmp(tmp_path)

        async def _run() -> None:
            app = CairnTuiApp()
            app.model.input_path = fixture_copy

            async with app.run_test() as pilot:
                app._goto("List_data")
                await pilot.pause()
                if app.model.parsed:
                    folders = getattr(app.model.parsed, "folders", {}) or {}
                    folder_ids = list(folders.keys())
                    if folder_ids:
                        app.model.selected_folder_id = folder_ids[0]
                app._goto("Waypoints")
                await pilot.pause()

                app.action_focus_table()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()

                # Close overlay
                await pilot.press("escape")
                await pilot.pause()

                # Focus should be back on the main waypoints table
                focused = getattr(app, "focused", None)
                assert focused is not None
                assert getattr(focused, "id", None) == "waypoints_table"

        asyncio.run(_run())

    def test_overlay_renders_on_top_of_routes(self, tmp_path: Path) -> None:
        fixture_copy = copy_fixture_to_tmp(tmp_path)

        async def _run() -> None:
            app = CairnTuiApp()
            app.model.input_path = fixture_copy

            async with app.run_test() as pilot:
                # Navigate to Routes
                app._goto("List_data")
                await pilot.pause()

                if app.model.parsed:
                    folders = getattr(app.model.parsed, "folders", {}) or {}
                    folder_ids = list(folders.keys())
                    if folder_ids:
                        app.model.selected_folder_id = folder_ids[0]

                app._goto("Routes")
                await pilot.pause()
                assert app.step == "Routes"

                # Select one, open overlay
                app.action_focus_table()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()

                try:
                    overlay = app.screen.query_one("#inline_edit_overlay")
                except Exception:
                    overlay = None
                assert overlay is not None
                assert overlay.has_class("open")

                svg = _rendered_svg(app)
                assert "Routes" in svg
                assert "Record" in svg
                assert "Field" in svg
                assert "Value" in svg

        asyncio.run(_run())

    def test_color_picker_is_overlay_popup(self, tmp_path: Path) -> None:
        """Color picker should render as an overlay (not navigate away)."""
        fixture_copy = copy_fixture_to_tmp(tmp_path)

        async def _run() -> None:
            app = CairnTuiApp()
            app.model.input_path = fixture_copy

            async with app.run_test() as pilot:
                app._goto("List_data")
                await pilot.pause()
                if app.model.parsed:
                    folders = getattr(app.model.parsed, "folders", {}) or {}
                    fid = list(folders.keys())[0]
                    app.model.selected_folder_id = fid
                app._goto("Waypoints")
                await pilot.pause()

                app.action_focus_table()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()

                # Move to Color row and open picker
                await pilot.press("down")
                await pilot.press("down")
                await pilot.press("down")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                # Overlay should be open
                try:
                    picker = app.query_one("#color_picker_overlay")
                except Exception:
                    picker = None
                assert picker is not None
                assert picker.has_class("open")

                svg = app.export_screenshot()
                # Underlying screen still rendered
                assert "Waypoints" in svg
                # Picker-specific tokens (SVG may split text nodes; avoid full-string matches)
                assert "Color" in svg
                assert "BLUE" in svg

        asyncio.run(_run())

    def test_color_picker_down_arrow_moves_one_row_not_two(self, tmp_path: Path) -> None:
        """
        Regression: Color picker should not skip entries on a single Down key.

        Observed bug: starting at RED ORANGE, one Down jumped to CYAN (skipping BLUE).
        """
        fixture_copy = copy_fixture_to_tmp(tmp_path)

        async def _run() -> None:
            app = CairnTuiApp()
            app.model.input_path = fixture_copy

            async with app.run_test() as pilot:
                app._goto("List_data")
                await pilot.pause()
                if app.model.parsed:
                    folders = getattr(app.model.parsed, "folders", {}) or {}
                    fid = list(folders.keys())[0]
                    app.model.selected_folder_id = fid
                app._goto("Waypoints")
                await pilot.pause()

                # Select one waypoint, open inline overlay, move to Color, open picker
                app.action_focus_table()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()

                # Move to Color row and open picker (Name -> Desc -> Icon -> Color)
                await pilot.press("down")
                await pilot.press("down")
                await pilot.press("down")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                tbl = app.query_one("#palette_table", DataTable)
                # Sanity: first row should be red-orange in the official palette order.
                assert (app._table_cursor_row_key(tbl) or "").strip() == "rgba(255,51,0,1)"

                # One Down should land on BLUE, not skip to CYAN.
                await pilot.press("down")
                await pilot.pause()
                assert (app._table_cursor_row_key(tbl) or "").strip() == "rgba(8,122,255,1)"

        asyncio.run(_run())

    def test_icon_picker_is_overlay_popup(self, tmp_path: Path) -> None:
        """Icon picker should render as an overlay (not navigate away)."""
        fixture_copy = copy_fixture_to_tmp(tmp_path)

        async def _run() -> None:
            app = CairnTuiApp()
            app.model.input_path = fixture_copy

            async with app.run_test() as pilot:
                app._goto("List_data")
                await pilot.pause()
                if app.model.parsed:
                    folders = getattr(app.model.parsed, "folders", {}) or {}
                    fid = list(folders.keys())[0]
                    app.model.selected_folder_id = fid
                app._goto("Waypoints")
                await pilot.pause()

                app.action_focus_table()
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()

                # Move to Icon row and open picker
                await pilot.press("down")
                await pilot.press("down")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                try:
                    picker = app.query_one("#icon_picker_overlay")
                except Exception:
                    picker = None
                assert picker is not None
                assert picker.has_class("open")

                svg = app.export_screenshot()
                assert "Waypoints" in svg
                assert "OnX" in svg
                assert "override" in svg
                assert "Icon" in svg

        asyncio.run(_run())
