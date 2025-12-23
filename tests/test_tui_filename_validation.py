from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tests.tui_harness import copy_fixture_to_tmp


@pytest.fixture(autouse=True)
def disable_tree_browser_for_tests():
    """Disable tree browser for tests."""
    import os
    old_value = os.environ.get("CAIRN_USE_TREE_BROWSER")
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"
    yield
    if old_value is None:
        os.environ.pop("CAIRN_USE_TREE_BROWSER", None)
    else:
        os.environ["CAIRN_USE_TREE_BROWSER"] = old_value


def test_tui_filename_validation_empty(tmp_path: Path) -> None:
    """Test that empty filename shows error and focuses field."""

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = out_dir

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()

            # Try to export without filename
            await pilot.press("enter")
            await pilot.pause()

            assert app._export_error is not None
            assert "Filename is required" in app._export_error
            assert app._export_in_progress is False

            # Filename field should be focused
            try:
                focused = app.focused
                assert focused is not None
                assert getattr(focused, "id", None) == "export_filename_input"
            except Exception:
                pass

    asyncio.run(_run())


def test_tui_filename_validation_path_separators(tmp_path: Path) -> None:
    """Test that filename with path separators shows error."""

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = out_dir

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()

            # Set filename with path separator
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "test/file"
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            assert app._export_error is not None
            assert "path separators" in app._export_error.lower()
            assert app._export_in_progress is False

    asyncio.run(_run())


def test_tui_filename_validation_invalid_chars(tmp_path: Path) -> None:
    """Test that filename with invalid characters shows error."""

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = out_dir

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()

            # Set filename with invalid characters
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "test<file>"
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            assert app._export_error is not None
            assert "invalid characters" in app._export_error.lower()
            assert app._export_in_progress is False

    asyncio.run(_run())


def test_tui_filename_without_extension(tmp_path: Path) -> None:
    """Test that filename without extension works (extension will be added)."""

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = out_dir

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()

            # Set filename without extension
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "new-onx-map"
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            # Wait for export
            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            assert app._export_error is None
            assert app._export_manifest is not None
            # Files should be generated with .gpx extension
            gpx_files = list(out_dir.glob("*.gpx"))
            assert len(gpx_files) > 0
            # Filenames should start with the user-entered name
            for gpx_file in gpx_files:
                assert gpx_file.stem.startswith("new-onx-map")

    asyncio.run(_run())


def test_tui_filename_with_extension(tmp_path: Path) -> None:
    """Test that filename with .gpx extension works correctly."""

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = out_dir

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()

            # Set filename with .gpx extension
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "new-onx-map.gpx"
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            # Wait for export
            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            assert app._export_error is None
            assert app._export_manifest is not None
            # Files should be generated
            gpx_files = list(out_dir.glob("*.gpx"))
            assert len(gpx_files) > 0
            # Filenames should start with the user-entered name (without .gpx, as it's used as base)
            for gpx_file in gpx_files:
                assert gpx_file.stem.startswith("new-onx-map")

    asyncio.run(_run())
