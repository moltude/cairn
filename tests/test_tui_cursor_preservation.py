from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from textual.widgets import DataTable

from tests.tui_harness import copy_fixture_to_tmp, get_tui_two_waypoints_fixture, select_folder_for_test


def _row_key_at_cursor(table: DataTable) -> str | None:
    """Best-effort row key at the cursor for Textual version compatibility."""
    try:
        idx = int(getattr(table, "cursor_row", 0) or 0)
    except Exception:
        return None
    try:
        rk = table.get_row_key(idx)  # type: ignore[attr-defined]
        return str(getattr(rk, "value", rk))
    except Exception:
        return None


def _pick_folder_with_min_tracks(app, *, min_tracks: int = 2) -> str:
    assert app.model.parsed is not None
    folders = getattr(app.model.parsed, "folders", {}) or {}
    for folder_id, fd in folders.items():
        tracks = list((fd or {}).get("tracks", []) or [])
        if len(tracks) >= int(min_tracks):
            return str(folder_id)
    raise AssertionError(f"No folder found with >= {min_tracks} tracks")


def test_folder_cursor_preserved_on_space_toggle_multifolder(tmp_path: Path) -> None:
    """
    Regression: toggling folder selection with Space should not jump the cursor back to row 0.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        fixture_copy = copy_fixture_to_tmp(tmp_path)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()

            await pilot.press("enter")  # -> Folder
            await pilot.pause()
            assert app.step == "Folder"

            tbl = app.query_one("#folder_table", DataTable)
            tbl.focus()
            await pilot.pause()

            # Move down a few rows so row 0 isn't involved.
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("down")
            await pilot.pause()

            before_row = int(getattr(tbl, "cursor_row", 0) or 0)
            before_key = _row_key_at_cursor(tbl)

            # Toggle selection
            await pilot.press("space")
            await pilot.pause()

            tbl2 = app.query_one("#folder_table", DataTable)
            after_row = int(getattr(tbl2, "cursor_row", 0) or 0)
            after_key = _row_key_at_cursor(tbl2)

            assert after_row == before_row, f"Expected folder cursor_row preserved (before={before_row}, after={after_row})"
            assert after_key == before_key, f"Expected folder cursor row key preserved (before={before_key}, after={after_key})"

    asyncio.run(_run())


def test_routes_cursor_preserved_on_space_toggle(tmp_path: Path) -> None:
    """
    Regression: toggling route selection with Space should not jump the cursor back to row 0.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        fixture_copy = copy_fixture_to_tmp(tmp_path)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()

            folder_id = _pick_folder_with_min_tracks(app, min_tracks=3)
            select_folder_for_test(app, folder_id)

            app._goto("Routes")
            await pilot.pause()
            assert app.step == "Routes"

            tbl = app.query_one("#routes_table", DataTable)
            tbl.focus()
            await pilot.pause()

            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("down")
            await pilot.pause()

            before_row = int(getattr(tbl, "cursor_row", 0) or 0)
            before_key = _row_key_at_cursor(tbl)

            await pilot.press("space")
            await pilot.pause()

            tbl2 = app.query_one("#routes_table", DataTable)
            after_row = int(getattr(tbl2, "cursor_row", 0) or 0)
            after_key = _row_key_at_cursor(tbl2)

            assert after_row == before_row, f"Expected routes cursor_row preserved (before={before_row}, after={after_row})"
            assert after_key == before_key, f"Expected routes cursor row key preserved (before={before_key}, after={after_key})"

    asyncio.run(_run())


def test_waypoints_cursor_preserved_on_space_toggle_single_folder_fixture(tmp_path: Path) -> None:
    """
    Regression: in a single-folder dataset, toggling waypoint selection with Space should not jump
    back to row 0.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        src = get_tui_two_waypoints_fixture(min_bytes=10)
        dst = tmp_path / "two_waypoints_copy.json"
        shutil.copy2(src, dst)

        app = CairnTuiApp()
        app.model.input_path = dst

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()

            # Ensure selected_folder_id is set for this small fixture (usually "default").
            assert app.model.parsed is not None
            folders = getattr(app.model.parsed, "folders", {}) or {}
            assert folders, "Expected at least one folder in parsed fixture"
            app.model.selected_folder_id = list(folders.keys())[0]

            app._goto("Waypoints")
            await pilot.pause()
            assert app.step == "Waypoints"

            tbl = app.query_one("#waypoints_table", DataTable)
            tbl.focus()
            await pilot.pause()

            # Move to second row (we have >=2 waypoints by contract).
            await pilot.press("down")
            await pilot.pause()

            before_row = int(getattr(tbl, "cursor_row", 0) or 0)
            before_key = _row_key_at_cursor(tbl)

            await pilot.press("space")
            await pilot.pause()

            tbl2 = app.query_one("#waypoints_table", DataTable)
            after_row = int(getattr(tbl2, "cursor_row", 0) or 0)
            after_key = _row_key_at_cursor(tbl2)

            assert after_row == before_row, f"Expected waypoints cursor_row preserved (before={before_row}, after={after_row})"
            assert after_key == before_key, f"Expected waypoints cursor row key preserved (before={before_key}, after={after_key})"

    asyncio.run(_run())


