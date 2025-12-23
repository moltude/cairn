"""Tests for TUI Select_file file browser navigation."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from textual.widgets import DataTable

from tests.tui_harness import ArtifactRecorder, get_bitterroots_complete_fixture


def _get_table_row_count(app, table_id: str) -> int:
    """Get the visible row count from a DataTable."""
    try:
        table = app.query_one(f"#{table_id}", DataTable)
        return int(getattr(table, "row_count", 0) or 0)
    except Exception:
        return 0


def test_tui_file_browser_shows_directories_and_files(tmp_path: Path) -> None:
    """Test that the file browser shows directories and valid input files."""
    # Disable tree mode for this test (uses table mode)
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        # Create a directory structure with test files
        test_dir = tmp_path / "test_maps"
        test_dir.mkdir()
        subdir = test_dir / "subdir"
        subdir.mkdir()

        # Create some test files
        (test_dir / "map1.json").write_text("{}", encoding="utf-8")
        (test_dir / "map2.geojson").write_text("{}", encoding="utf-8")
        (test_dir / "tracks.gpx").write_text("<gpx></gpx>", encoding="utf-8")
        (test_dir / "readme.txt").write_text("Not a map file", encoding="utf-8")

        app = CairnTuiApp()

        async with app.run_test() as pilot:
            # Set the browser directory after app is mounted
            app._file_browser_dir = test_dir
            app._refresh_file_browser()
            await pilot.pause()

            assert app.step == "Select_file"

            # Check file browser has content
            row_count = _get_table_row_count(app, "file_browser")
            # Should have: parent (..), subdir, and the map files (json, geojson, gpx)
            # The .txt file should be excluded
            assert row_count >= 4, f"Expected at least 4 entries (parent + subdir + 3 map files), got {row_count}"

    asyncio.run(_run())
    os.environ.pop("CAIRN_USE_TREE_BROWSER", None)


def test_tui_file_browser_navigate_into_directory(tmp_path: Path) -> None:
    """Test navigating into a subdirectory."""
    # Disable tree mode for this test (uses table mode)
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        # Create directory structure
        test_dir = tmp_path / "maps"
        test_dir.mkdir()
        subdir = test_dir / "region"
        subdir.mkdir()
        (subdir / "local_map.json").write_text("{}", encoding="utf-8")

        app = CairnTuiApp()

        async with app.run_test() as pilot:
            # Set the browser directory after app is mounted
            app._file_browser_dir = test_dir
            app._refresh_file_browser()
            await pilot.pause()

            initial_dir = app._file_browser_dir
            assert initial_dir == test_dir

            # Move cursor down to the subdir entry and press enter
            # First row is ".." (parent), second should be "region"
            await pilot.press("down")  # Skip parent ".."
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            # Should now be in the subdirectory
            assert app._file_browser_dir == subdir, (
                f"Expected to navigate to {subdir}, got {app._file_browser_dir}"
            )

    asyncio.run(_run())
    os.environ.pop("CAIRN_USE_TREE_BROWSER", None)


def test_tui_file_browser_navigate_up(tmp_path: Path) -> None:
    """Test navigating up to parent directory."""
    # Disable tree mode for this test (uses table mode)
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        # Create directory structure
        test_dir = tmp_path / "maps"
        test_dir.mkdir()
        subdir = test_dir / "region"
        subdir.mkdir()

        app = CairnTuiApp()

        async with app.run_test() as pilot:
            # Set the browser directory after app is mounted
            app._file_browser_dir = subdir
            app._refresh_file_browser()
            await pilot.pause()

            assert app._file_browser_dir == subdir

            # First row should be ".." - press enter to go up
            await pilot.press("enter")
            await pilot.pause()

            # Should now be in parent directory
            assert app._file_browser_dir == test_dir, (
                f"Expected to navigate to {test_dir}, got {app._file_browser_dir}"
            )

    asyncio.run(_run())
    os.environ.pop("CAIRN_USE_TREE_BROWSER", None)


def test_tui_file_browser_select_json_file_advances_step(tmp_path: Path) -> None:
    """Test that selecting a .json file advances to List_data step."""
    # Disable tree mode for this test (uses table mode)
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        # Create a valid GeoJSON file
        test_dir = tmp_path / "maps"
        test_dir.mkdir()

        # Create a minimal valid CalTopo GeoJSON
        geojson_content = """{
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "test",
                    "properties": {"class": "Folder", "title": "Test"},
                    "geometry": null
                }
            ]
        }"""
        map_file = test_dir / "test_map.json"
        map_file.write_text(geojson_content, encoding="utf-8")

        app = CairnTuiApp()

        async with app.run_test() as pilot:
            # Set the browser directory after app is mounted
            app._file_browser_dir = test_dir
            app._refresh_file_browser()
            await pilot.pause()

            assert app.step == "Select_file"

            # Navigate to the json file (skip parent ..)
            await pilot.press("down")  # Move past ".."
            await pilot.pause()
            await pilot.press("enter")  # Select the json file
            await pilot.pause()

            # Should have advanced to List_data
            assert app.step == "List_data", f"Expected to advance to List_data, got {app.step}"
            assert app.model.input_path is not None

    asyncio.run(_run())
    os.environ.pop("CAIRN_USE_TREE_BROWSER", None)


def test_tui_file_browser_gpx_is_selectable() -> None:
    """Test that selecting a .gpx file is accepted (CalTopo GPX support)."""
    # Disable tree mode for this test (uses table mode)
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        # Use a temporary directory with a valid CalTopo-style GPX
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            test_dir = tmp_path / "maps"
            test_dir.mkdir()
            gpx_file = test_dir / "tracks.gpx"
            # Create a valid GPX with at least one waypoint
            gpx_content = '''<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" creator="CALTOPO" version="1.1">
  <wpt lat="46.0" lon="-114.0"><name>Test Point</name></wpt>
</gpx>'''
            gpx_file.write_text(gpx_content, encoding="utf-8")

            app = CairnTuiApp()

            async with app.run_test() as pilot:
                # Set the browser directory after app is mounted
                app._file_browser_dir = test_dir
                app._refresh_file_browser()
                await pilot.pause()

                # Navigate to the gpx file and select it
                await pilot.press("down")  # Skip ".."
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                # GPX is now supported - should be selected as input
                assert app.model.input_path is not None, "GPX file should be selectable"
                assert app.model.input_path.suffix == ".gpx"

    asyncio.run(_run())
    os.environ.pop("CAIRN_USE_TREE_BROWSER", None)


def test_tui_file_browser_excludes_non_map_files(tmp_path: Path) -> None:
    """Test that the file browser only shows map file extensions."""
    # Disable tree mode for this test (uses table mode)
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        test_dir = tmp_path / "mixed"
        test_dir.mkdir()

        # Create various files - only map files should be visible
        (test_dir / "map.json").write_text("{}", encoding="utf-8")
        (test_dir / "readme.txt").write_text("text", encoding="utf-8")
        (test_dir / "image.png").write_bytes(b"PNG")
        (test_dir / "data.csv").write_text("a,b,c", encoding="utf-8")
        (test_dir / "script.py").write_text("print('hi')", encoding="utf-8")

        app = CairnTuiApp()

        async with app.run_test() as pilot:
            # Set the browser directory after app is mounted
            app._file_browser_dir = test_dir
            app._refresh_file_browser()
            await pilot.pause()

            # Get the file browser table
            try:
                table = app.query_one("#file_browser", DataTable)
                row_count = int(getattr(table, "row_count", 0) or 0)
            except Exception:
                row_count = 0

            # Should only have parent (..) and map.json
            # The other files should be excluded
            assert row_count == 2, (
                f"Expected 2 entries (parent + map.json), got {row_count}"
            )

    asyncio.run(_run())
    os.environ.pop("CAIRN_USE_TREE_BROWSER", None)


def test_tui_file_browser_hides_dot_directories(tmp_path: Path) -> None:
    """Test that directories starting with . are hidden in the file browser."""
    # Disable tree mode for this test (uses table mode)
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        # Create a directory structure with visible and dot-prefixed directories
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()

        # Create visible directories
        (test_dir / "maps").mkdir()
        (test_dir / "data").mkdir()

        # Create dot-prefixed directories (should be hidden)
        (test_dir / ".git").mkdir()
        (test_dir / ".cursor").mkdir()
        (test_dir / ".vscode").mkdir()

        # Create a valid map file
        (test_dir / "map.json").write_text("{}", encoding="utf-8")

        app = CairnTuiApp()

        async with app.run_test() as pilot:
            app._file_browser_dir = test_dir
            app._refresh_file_browser()
            await pilot.pause()

            assert app.step == "Select_file"

            # Get the file browser table
            try:
                table = app.query_one("#file_browser", DataTable)
                row_count = int(getattr(table, "row_count", 0) or 0)

                # Collect visible entries
                visible_entries = []
                for i in range(row_count):
                    try:
                        rk = table.get_row_key(i)
                        visible_entries.append(str(getattr(rk, "value", rk)))
                    except Exception:
                        pass
            except Exception:
                visible_entries = []
                row_count = 0

            # Should have: parent (..) + 2 visible dirs (maps, data) + 1 file (map.json) = 4
            # Should NOT have: .git, .cursor, .vscode
            assert row_count == 4, (
                f"Expected 4 entries (parent + 2 dirs + 1 file), got {row_count}. "
                f"Visible entries: {visible_entries}"
            )

            # Verify dot directories are not in the list
            for entry in visible_entries:
                assert ".git" not in entry, f"Found .git in entries: {visible_entries}"
                assert ".cursor" not in entry, f"Found .cursor in entries: {visible_entries}"
                assert ".vscode" not in entry, f"Found .vscode in entries: {visible_entries}"

    asyncio.run(_run())
    os.environ.pop("CAIRN_USE_TREE_BROWSER", None)


def test_filtered_file_tree_hides_dotfiles(tmp_path: Path) -> None:
    """Test that FilteredFileTree hides dotfiles even if they have valid extensions."""
    from cairn.tui.app import FilteredFileTree

    # Create test directory structure
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()

    # Create visible files with valid extensions
    (test_dir / "map.json").write_text("{}", encoding="utf-8")
    (test_dir / "routes.geojson").write_text("{}", encoding="utf-8")
    (test_dir / "track.gpx").write_text("<gpx></gpx>", encoding="utf-8")

    # Create dotfiles with valid extensions (should be hidden)
    (test_dir / ".claude.json").write_text("{}", encoding="utf-8")
    (test_dir / ".open-vpn.json").write_text("{}", encoding="utf-8")
    (test_dir / ".config.geojson").write_text("{}", encoding="utf-8")

    # Create visible directories
    (test_dir / "maps").mkdir()
    (test_dir / "data").mkdir()

    # Create dot directories (should be hidden)
    (test_dir / ".git").mkdir()
    (test_dir / ".cursor").mkdir()

    # Create the FilteredFileTree and test filtering
    tree = FilteredFileTree(str(test_dir))

    # Get all paths in the directory
    all_paths = list(test_dir.iterdir())

    # Apply the filter
    filtered_paths = list(tree.filter_paths(all_paths))
    filtered_names = {p.name for p in filtered_paths}

    # Verify visible files are included
    assert "map.json" in filtered_names, "map.json should be visible"
    assert "routes.geojson" in filtered_names, "routes.geojson should be visible"
    assert "track.gpx" in filtered_names, "track.gpx should be visible"

    # Verify visible directories are included
    assert "maps" in filtered_names, "maps/ directory should be visible"
    assert "data" in filtered_names, "data/ directory should be visible"

    # Verify dotfiles are hidden (hide always wins, even with valid extensions)
    assert ".claude.json" not in filtered_names, ".claude.json should be hidden"
    assert ".open-vpn.json" not in filtered_names, ".open-vpn.json should be hidden"
    assert ".config.geojson" not in filtered_names, ".config.geojson should be hidden"

    # Verify dot directories are hidden
    assert ".git" not in filtered_names, ".git/ directory should be hidden"
    assert ".cursor" not in filtered_names, ".cursor/ directory should be hidden"

    # Verify we have exactly 5 visible items (3 files + 2 dirs)
    assert len(filtered_paths) == 5, (
        f"Expected 5 visible items (3 files + 2 dirs), got {len(filtered_paths)}. "
        f"Visible: {filtered_names}"
    )


def test_filtered_directory_tree_hides_dotfiles_and_files(tmp_path: Path) -> None:
    """Test that FilteredDirectoryTree hides dotfiles and all regular files (shows only directories)."""
    from cairn.tui.app import FilteredDirectoryTree

    # Create test directory structure
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()

    # Create visible files (should ALL be hidden - FilteredDirectoryTree only shows dirs)
    (test_dir / "map.json").write_text("{}", encoding="utf-8")
    (test_dir / "README.md").write_text("# Test", encoding="utf-8")
    (test_dir / "data.txt").write_text("test", encoding="utf-8")

    # Create dotfiles (should be hidden)
    (test_dir / ".gitignore").write_text("*", encoding="utf-8")
    (test_dir / ".env").write_text("SECRET=123", encoding="utf-8")

    # Create visible directories (should be shown)
    (test_dir / "maps").mkdir()
    (test_dir / "data").mkdir()
    (test_dir / "output").mkdir()

    # Create dot directories (should be hidden)
    (test_dir / ".git").mkdir()
    (test_dir / ".cursor").mkdir()
    (test_dir / ".vscode").mkdir()

    # Create the FilteredDirectoryTree and test filtering
    tree = FilteredDirectoryTree(str(test_dir))

    # Get all paths in the directory
    all_paths = list(test_dir.iterdir())

    # Apply the filter
    filtered_paths = list(tree.filter_paths(all_paths))
    filtered_names = {p.name for p in filtered_paths}

    # Verify visible directories are included
    assert "maps" in filtered_names, "maps/ directory should be visible"
    assert "data" in filtered_names, "data/ directory should be visible"
    assert "output" in filtered_names, "output/ directory should be visible"

    # Verify ALL files are hidden (FilteredDirectoryTree only shows directories)
    assert "map.json" not in filtered_names, "map.json should be hidden (files not shown)"
    assert "README.md" not in filtered_names, "README.md should be hidden (files not shown)"
    assert "data.txt" not in filtered_names, "data.txt should be hidden (files not shown)"

    # Verify dotfiles are hidden
    assert ".gitignore" not in filtered_names, ".gitignore should be hidden"
    assert ".env" not in filtered_names, ".env should be hidden"

    # Verify dot directories are hidden
    assert ".git" not in filtered_names, ".git/ directory should be hidden"
    assert ".cursor" not in filtered_names, ".cursor/ directory should be hidden"
    assert ".vscode" not in filtered_names, ".vscode/ directory should be hidden"

    # Verify we have exactly 3 visible items (only the 3 non-dot directories)
    assert len(filtered_paths) == 3, (
        f"Expected 3 visible directories, got {len(filtered_paths)}. "
        f"Visible: {filtered_names}"
    )
