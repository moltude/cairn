from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from tests.tui_harness import copy_fixture_to_tmp, move_datatable_cursor_to_row_key


# Disable tree browser by default for most tests in this module.
# Tree mode causes timeouts due to async DirectoryTree.watch_path coroutines.
# Tests that specifically test tree functionality should enable it explicitly.
@pytest.fixture(autouse=True)
def disable_tree_browser_for_tests():
    """Disable tree browser for tests that don't specifically test tree mode."""
    old_value = os.environ.get("CAIRN_USE_TREE_BROWSER")
    os.environ["CAIRN_USE_TREE_BROWSER"] = "0"
    yield
    if old_value is None:
        os.environ.pop("CAIRN_USE_TREE_BROWSER", None)
    else:
        os.environ["CAIRN_USE_TREE_BROWSER"] = old_value


def _dismiss_post_save_prompt_if_present(pilot, app) -> None:
    """
    Tests often need to continue interacting with the Save screen after export.
    We skip the post-save prompt by pre-setting the flag.
    """
    try:
        app._post_save_prompt_shown = True
    except Exception:
        pass


async def _open_save_target_overlay(app, pilot) -> None:
    """Open the SaveTargetOverlay via the Preview & Export step 'c' key."""
    await pilot.press("c")
    await pilot.pause()


async def _activate_save_target_row(app, pilot, *, row_key: str) -> None:
    """
    Deterministic SaveTargetOverlay activation without relying on Pilot's Enter handling.

    Textual's Pilot can time out waiting for screens to fully drain call_later callbacks
    during heavy re-render/unmount cycles. For Save target editing, we move the cursor
    to a row key in the overlay and invoke the overlay activation method directly.
    """
    ov = app.query_one("#save_target_overlay")
    if row_key == "__done__":
        # Done is now a dedicated control outside the scrolling DataTable.
        ov._apply_done()  # type: ignore[attr-defined]
    else:
        # Check if overlay is using tree mode or table mode
        use_tree = getattr(ov, "_use_tree", False)
        if use_tree:
            # Tree mode: For tree navigation, we update _cur_dir directly
            # DO NOT call _refresh_tree() as it creates new tree widgets with unawaited coroutines
            # which causes pilot.pause() to time out. The model update is sufficient for tests.
            if row_key.startswith("dir:"):
                try:
                    target_path = Path(row_key[4:])
                    ov._cur_dir = target_path.resolve() if target_path.exists() else target_path
                    # Just update the path display, don't reload tree
                    try:
                        from textual.widgets import Static
                        ov.query_one("#save_target_path", Static).update(f"Directory: {ov._cur_dir}")
                    except Exception:
                        pass
                except Exception:
                    pass
            elif row_key == "__up__":
                try:
                    ov._cur_dir = ov._cur_dir.parent if ov._cur_dir.parent != ov._cur_dir else ov._cur_dir
                    # Just update the path display, don't reload tree
                    try:
                        from textual.widgets import Static
                        ov.query_one("#save_target_path", Static).update(f"Directory: {ov._cur_dir}")
                    except Exception:
                        pass
                except Exception:
                    pass
        else:
            # Table mode: use DataTable cursor movement
            move_datatable_cursor_to_row_key(app, table_id="save_target_browser", target_row_key=row_key)
            await pilot.pause()
            ov.activate()
    await pilot.pause()


def test_tui_save_change_folder_then_export(tmp_path: Path) -> None:
    """
    E2E: on Preview & Export screen, navigate into a subfolder, select it as output dir, then export.
    This exercises SaveTargetOverlay navigation + Enter behavior.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        base = tmp_path / "out_base"
        sub = base / "sub_out"
        sub.mkdir(parents=True, exist_ok=True)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = base

        async with app.run_test() as pilot:
            _dismiss_post_save_prompt_if_present(pilot, app)

            # Parse + navigate to Save deterministically.
            app._goto("List_data")
            await pilot.pause()
            await pilot.press("enter")  # -> Folder
            await pilot.pause()
            # Continue from Folder (infer selection) -> Routes/Waypoints -> Preview
            app.action_continue()
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()
            assert app.step == "Preview"

            # Change output folder to sub_out via overlay, then Done.
            await _open_save_target_overlay(app, pilot)
            await _activate_save_target_row(app, pilot, row_key=f"dir:{sub}")
            await _activate_save_target_row(app, pilot, row_key="__done__")
            assert app.model.output_dir == sub

            # Set filename before exporting
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "test_export"
            await pilot.pause()

            # Export
            await pilot.press("enter")
            await pilot.pause()

            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            assert app._export_error is None
            assert sub.exists()
            assert list(sub.glob("*.gpx")), "Expected at least one GPX in chosen output folder"

    asyncio.run(_run())


def test_tui_save_filename_persists_across_folder_navigation(tmp_path: Path) -> None:
    """
    E2E: set output filename, navigate folders, and confirm the filename persists.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        base = tmp_path / "out_base"
        sub = base / "sub_out"
        sub.mkdir(parents=True, exist_ok=True)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = base

        async with app.run_test() as pilot:
            _dismiss_post_save_prompt_if_present(pilot, app)

            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()
            assert app.step == "Preview"

            # Set filename in main UI (filename is no longer in overlay)
            filename = "MY_FILENAME"
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = filename
            await pilot.pause()

            # Navigate folders via overlay (filename should persist)
            await _open_save_target_overlay(app, pilot)
            await _activate_save_target_row(app, pilot, row_key=f"dir:{sub}")
            await _activate_save_target_row(app, pilot, row_key="__up__")
            await _activate_save_target_row(app, pilot, row_key="__done__")

            # Filename should persist after applying directory changes.
            assert (app._output_filename or "").strip() == filename

    asyncio.run(_run())


def test_tui_save_rename_outputs_and_apply(tmp_path: Path) -> None:
    """
    E2E: export, edit rename fields, press 'r' to apply renames, verify files renamed.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "onx_ready"

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = out_dir

        async with app.run_test() as pilot:
            # Skip the post-save prompt so we can keep interacting with Save.
            _dismiss_post_save_prompt_if_present(pilot, app)

            # Parse first (export requires parsed data).
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()

            # Set filename before exporting
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "test_export"
            await pilot.pause()

            # Export - call action_export directly (no confirm dialog anymore)
            app.action_export()
            await pilot.pause()

            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            # Extra pause to let UI update after export completes
            await pilot.pause()

            assert app._export_error is None
            assert app._export_manifest, "Expected export manifest after export"

            # Set rename for the first manifest file.
            first_fn = app._export_manifest[0][0]
            first_ext = Path(first_fn).suffix
            new_fn = f"RENAMED_0{first_ext}"

            inp = app.query_one("#rename_0", Input)
            inp.value = new_fn
            await pilot.pause()

            # Apply renames
            await pilot.press("r")
            await pilot.pause()

            assert (out_dir / new_fn).exists(), "Expected renamed file to exist"
            assert not (out_dir / first_fn).exists(), "Expected original file name to be renamed away"

    asyncio.run(_run())


@pytest.mark.parametrize(
    "mode",
    [
        "empty",
        "duplicate",
        "ext_mismatch",
        "path_component",
    ],
)
def test_tui_save_rename_negative_cases_then_recover(tmp_path: Path, mode: str) -> None:
    """
    Negative E2E: validate rename input guardrails on Save:
    - empty filename
    - duplicate filename
    - extension mismatch
    - directory/path components

    Then recover by fixing the names and applying successfully.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "onx_ready"

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = out_dir

        async with app.run_test() as pilot:
            _dismiss_post_save_prompt_if_present(pilot, app)

            # Parse first (export requires parsed data) then go to Save.
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()

            # Set filename before exporting
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "test_export"
            await pilot.pause()

            # Export
            await pilot.press("enter")
            await pilot.pause()

            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            assert app._export_error is None
            assert app._export_manifest

            manifest = list(app._export_manifest or [])
            assert len(manifest) >= 1
            old0 = manifest[0][0]
            ext0 = Path(old0).suffix

            # If we need a second filename (duplicate), ensure we have one; if not, skip.
            if mode == "duplicate" and len(manifest) < 2:
                pytest.skip("Need at least 2 exported files to test duplicate rename")

            # Create invalid rename edits.
            if mode == "empty":
                app.query_one("#rename_0", Input).value = ""
            elif mode == "duplicate":
                old1 = manifest[1][0]
                ext1 = Path(old1).suffix
                dup = f"DUPLICATE{ext0}"
                app.query_one("#rename_0", Input).value = dup
                app.query_one("#rename_1", Input).value = dup if ext0 == ext1 else f"DUPLICATE{ext1}"
            elif mode == "ext_mismatch":
                # Keep a filename but change extension.
                bad_ext = ".kml" if ext0.lower() != ".kml" else ".gpx"
                app.query_one("#rename_0", Input).value = f"BAD_EXT{bad_ext}"
            elif mode == "path_component":
                app.query_one("#rename_0", Input).value = f"nested{Path('/').as_posix()}bad{ext0}"
            else:
                raise AssertionError(f"Unknown mode: {mode}")

            await pilot.pause()

            # Apply should fail and set an error (but app should remain responsive).
            await pilot.press("r")
            await pilot.pause()

            assert app.step == "Preview"
            assert app._export_error is not None
            assert "Rename error:" in app._export_error

            # Files should not have been renamed away on failure (no partial rename).
            assert (out_dir / old0).exists(), "Expected no partial rename when validation fails"

            # Recover: set a valid unique rename and apply.
            new0 = f"RECOVERED_0{ext0}"
            app.query_one("#rename_0", Input).value = new0
            if mode == "duplicate":
                # Ensure second is also valid + unique
                old1 = manifest[1][0]
                ext1 = Path(old1).suffix
                new1 = f"RECOVERED_1{ext1}"
                app.query_one("#rename_1", Input).value = new1
            await pilot.pause()

            await pilot.press("r")
            await pilot.pause()

            assert app._export_error is None
            assert (out_dir / new0).exists()
            assert not (out_dir / old0).exists()

    asyncio.run(_run())


def test_tui_save_target_overlay_done_applies_output_dir(tmp_path: Path) -> None:
    """
    Unit-style: ensure SaveTargetOverlay Done applies to app model state.
    Filename is handled in main UI, not overlay.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        base = tmp_path / "out_base"
        sub = base / "sub_out"
        sub.mkdir(parents=True, exist_ok=True)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = base

        async with app.run_test() as pilot:
            _dismiss_post_save_prompt_if_present(pilot, app)
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()

            await _open_save_target_overlay(app, pilot)
            # Navigate into subfolder, then Done.
            await _activate_save_target_row(app, pilot, row_key=f"dir:{sub}")
            await pilot.pause()
            await _activate_save_target_row(app, pilot, row_key="__done__")

            assert app.model.output_dir == sub

    asyncio.run(_run())


@pytest.mark.parametrize(
    "change_folder,nav_before_export,nav_after_export,set_filename,rename_strategy",
    [
        # Baseline: no folder change, export only
        (False, False, False, False, "none"),
        # Change folder then export
        (True, False, False, False, "none"),
        # Navigate around (but keep folder), then export
        (False, True, False, False, "none"),
        # Filename set before export (should persist through folder nav)
        (True, True, False, True, "none"),
        # Rename first file only + apply
        (False, False, False, False, "first"),
        # Change folder + rename first + apply
        (True, False, False, False, "first"),
        # Rename all outputs + apply
        (False, False, False, True, "all"),
        # Change folder + rename all + apply + navigate after export
        (True, True, True, True, "all"),
    ],
)
def test_tui_save_flow_permutations(
    tmp_path: Path,
    change_folder: bool,
    nav_before_export: bool,
    nav_after_export: bool,
    set_filename: bool,
    rename_strategy: str,
) -> None:
    """
    Combinatorial E2E coverage for Save step to catch state bugs:
    - changing output folder vs keeping it
    - navigating folders before/after export
    - keeping filename stable across renders
    - renaming outputs (first/all) + applying via 'r'
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import Input

        fixture_copy = copy_fixture_to_tmp(tmp_path)

        base = tmp_path / "out_base"
        sub = base / "sub_out"
        base.mkdir(parents=True, exist_ok=True)
        sub.mkdir(parents=True, exist_ok=True)

        # A second sibling folder to exercise more navigation.
        sib = base / "sib_out"
        sib.mkdir(parents=True, exist_ok=True)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = base

        async with app.run_test() as pilot:
            _dismiss_post_save_prompt_if_present(pilot, app)

            # Parse first (export requires parsed data).
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()
            assert app.step == "Preview"

            # Optionally set filename up-front (should survive folder navigation / re-renders).
            filename_val = "SCENARIO_FILENAME" if set_filename else "test_export"
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = filename_val
            await pilot.pause()

            # Optionally change the output folder.
            expected_out_dir = base
            if nav_before_export or change_folder:
                await _open_save_target_overlay(app, pilot)

                if nav_before_export:
                    # Browse around, but return to base.
                    await _activate_save_target_row(app, pilot, row_key=f"dir:{sub}")
                    await _activate_save_target_row(app, pilot, row_key="__up__")
                    await _activate_save_target_row(app, pilot, row_key=f"dir:{sib}")
                    await _activate_save_target_row(app, pilot, row_key="__up__")

                if change_folder:
                    await _activate_save_target_row(app, pilot, row_key=f"dir:{sub}")
                    expected_out_dir = sub

                await _activate_save_target_row(app, pilot, row_key="__done__")

            assert app.model.output_dir == expected_out_dir
            if set_filename:
                assert (app._output_filename or "").strip() == filename_val

            # Export
            await pilot.press("enter")
            await pilot.pause()

            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            assert app._export_error is None
            assert app._export_manifest
            assert expected_out_dir.exists()
            exported = sorted(expected_out_dir.glob("*.gpx"))
            assert exported, "Expected at least one GPX output"

            # Optionally rename outputs + apply
            if rename_strategy in {"first", "all"}:
                # Wait for UI to update and create rename inputs
                await pilot.pause()
                await pilot.pause()

                manifest = list(app._export_manifest or [])
                assert manifest

                if rename_strategy == "first":
                    old0 = manifest[0][0]
                    ext0 = Path(old0).suffix
                    new0 = f"RENAMED_0{ext0}"
                    # Wait for rename input to be available
                    for _ in range(10):
                        try:
                            app.query_one("#rename_0", Input)
                            break
                        except Exception:
                            await pilot.pause()
                    app.query_one("#rename_0", Input).value = new0
                    await pilot.pause()
                    await pilot.press("r")
                    await pilot.pause()
                    assert (expected_out_dir / new0).exists()
                    assert not (expected_out_dir / old0).exists()
                else:
                    # Rename every file to a deterministic, unique name.
                    # Wait for all rename inputs to be available
                    for i in range(len(manifest)):
                        for _ in range(10):
                            try:
                                app.query_one(f"#rename_{i}", Input)
                                break
                            except Exception:
                                await pilot.pause()

                    new_names: list[tuple[str, str]] = []
                    for i, (fn, _fmt, _cnt, _sz) in enumerate(manifest):
                        ext = Path(fn).suffix
                        new_fn = f"RENAMED_{i}{ext}"
                        app.query_one(f"#rename_{i}", Input).value = new_fn
                        new_names.append((fn, new_fn))
                    await pilot.pause()
                    await pilot.press("r")
                    await pilot.pause()

                    # Check if there was an error
                    if app._export_error:
                        pytest.fail(f"Rename failed with error: {app._export_error}")

                    for old_fn, new_fn in new_names:
                        assert (expected_out_dir / new_fn).exists(), \
                            f"Renamed file {new_fn} should exist. Error: {app._export_error}. Files in dir: {list(expected_out_dir.glob('*'))}"
                        assert not (expected_out_dir / old_fn).exists(), \
                            f"Original file {old_fn} should not exist after rename"

            # Optionally navigate after export and ensure rename fields/filename persist.
            if nav_after_export:
                # Open overlay, browse a bit, then cancel; ensure filename stays stable.
                await _open_save_target_overlay(app, pilot)
                await _activate_save_target_row(app, pilot, row_key=f"dir:{sub if expected_out_dir == base else base}")
                await _activate_save_target_row(app, pilot, row_key="__up__")
                await pilot.press("escape")
                await pilot.pause()
                if set_filename:
                    assert (app._output_filename or "").strip() == filename_val

    asyncio.run(_run())


def test_tui_preview_tree_navigate_to_tmp_onx_export(tmp_path: Path) -> None:
    """
    E2E: Navigate directory tree in Preview step to change export directory to /tmp/onx-export/.

    Verifies:
    - Tree receives focus when Preview step loads (tree mode)
    - Directory selection via tree updates output_dir
    - Export works with the new directory
    - Files are written to the correct location
    """
    import os
    from pathlib import Path

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import DirectoryTree

        # Enable tree mode
        os.environ["CAIRN_USE_TREE_BROWSER"] = "1"

        fixture_copy = copy_fixture_to_tmp(tmp_path)

        # Create test directories
        base = tmp_path / "out_base"
        base.mkdir(parents=True, exist_ok=True)

        # Target directory: /tmp/onx-export (use resolve for macOS symlink handling)
        target_dir = Path("/tmp/onx-export").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = base

        async with app.run_test() as pilot:
            _dismiss_post_save_prompt_if_present(pilot, app)

            # Navigate to Preview
            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()
            assert app.step == "Preview"
            assert app._use_tree_browser() == True, "Tree mode should be enabled"

            # Verify tree is present and focused
            tree = app.query_one("#export_dir_tree", DirectoryTree)
            focused = app.focused
            assert focused is tree, f"Tree should be focused, but {focused} is focused instead"

            # Verify initial directory
            initial_dir = app.model.output_dir
            assert initial_dir == base, f"Initial dir should be {base}, got {initial_dir}"

            # Simulate directory selection via tree's DirectorySelected event
            # This simulates what happens when user navigates tree and presses Enter on a directory
            event = DirectoryTree.DirectorySelected(tree, str(target_dir))
            app.on_directory_tree_directory_selected(event)
            await pilot.pause()

            # Verify directory was updated (use resolve for macOS symlink handling)
            assert app.model.output_dir.resolve() == target_dir.resolve(), \
                f"Export directory should be {target_dir}, got {app.model.output_dir}"

            # Set filename before exporting
            from textual.widgets import Input
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "test_export"
            await pilot.pause()

            # Trigger export directly (bypasses focus issues with tree mode)
            app.action_export()
            await pilot.pause()

            # Wait for export to complete
            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            assert not app._export_in_progress, "Export should complete"
            assert app._export_manifest is not None, "Export should produce manifest"
            assert app._export_error is None, f"Export should not error: {app._export_error}"

            # Verify files were exported to the correct directory
            manifest = app._export_manifest
            for filename, _, _, _ in manifest:
                # Manifest contains just filenames, not full paths
                # Verify the file exists in the target directory
                assert (target_dir / filename).exists(), \
                    f"File {filename} should exist in {target_dir}"

            # Clean up
            try:
                os.environ.pop("CAIRN_USE_TREE_BROWSER", None)
            except Exception:
                pass

    asyncio.run(_run())


def test_tui_preview_tree_navigate_to_home_onx(tmp_path: Path) -> None:
    """
    E2E: Navigate directory tree in Preview step to change export directory to ~/onx.

    Same as test_tui_preview_tree_navigate_to_tmp_onx_export but uses ~/onx as target.
    """
    import os
    from pathlib import Path

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import DirectoryTree

        os.environ["CAIRN_USE_TREE_BROWSER"] = "1"

        fixture_copy = copy_fixture_to_tmp(tmp_path)

        base = tmp_path / "out_base"
        base.mkdir(parents=True, exist_ok=True)

        # Target directory: ~/onx
        target_dir = Path.home() / "onx"
        target_dir.mkdir(parents=True, exist_ok=True)

        app = CairnTuiApp()
        app.model.input_path = fixture_copy
        app.model.output_dir = base

        async with app.run_test() as pilot:
            _dismiss_post_save_prompt_if_present(pilot, app)

            app._goto("List_data")
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()
            assert app.step == "Preview"
            assert app._use_tree_browser() == True

            tree = app.query_one("#export_dir_tree", DirectoryTree)
            assert app.focused is tree, "Tree should be focused"

            assert app.model.output_dir == base

            # Simulate selecting ~/onx directory
            event = DirectoryTree.DirectorySelected(tree, str(target_dir))
            app.on_directory_tree_directory_selected(event)
            await pilot.pause()

            assert app.model.output_dir == target_dir, \
                f"Expected {target_dir}, got {app.model.output_dir}"

            # Set filename before exporting
            from textual.widgets import Input
            filename_input = app.query_one("#export_filename_input", Input)
            filename_input.value = "test_export"
            await pilot.pause()

            # Trigger export directly (bypasses focus issues with tree mode)
            app.action_export()
            await pilot.pause()

            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            assert not app._export_in_progress
            assert app._export_manifest is not None
            assert app._export_error is None

            for filename, _, _, _ in app._export_manifest:
                # Manifest contains just filenames, not full paths
                # Verify the file exists in the target directory
                assert (target_dir / filename).exists(), \
                    f"File {filename} should exist in {target_dir}"

            try:
                os.environ.pop("CAIRN_USE_TREE_BROWSER", None)
            except Exception:
                pass

    asyncio.run(_run())
