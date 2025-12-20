from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tests.tui_harness import copy_fixture_to_tmp, move_datatable_cursor_to_row_key


def _dismiss_post_save_prompt_if_present(pilot, app) -> None:
    """
    Tests often need to continue interacting with the Save screen after export.
    We skip the post-save prompt by pre-setting the flag.
    """
    try:
        app._post_save_prompt_shown = True
    except Exception:
        pass


def test_tui_save_change_folder_then_export(tmp_path: Path) -> None:
    """
    E2E: on Save screen, navigate into a subfolder, select it as output dir, then export.
    This exercises the Save browser navigation + Enter behavior.
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

            # Parse + navigate to Save deterministically.
            app._goto("List_data")
            await pilot.pause()
            await pilot.press("enter")  # -> Folder
            await pilot.pause()
            # Continue from Folder (infer selection) -> Routes/Waypoints -> Preview -> Save
            app.action_continue()
            await pilot.pause()
            app._goto("Preview")
            await pilot.pause()
            await pilot.press("enter")  # -> Save
            await pilot.pause()
            assert app.step == "Save"

            # Save browser should show sub_out; cursor defaults to first directory row.
            # Enter should navigate into the directory.
            await pilot.press("enter")
            await pilot.pause()
            assert str(getattr(app, "_save_browser_dir", "")) == str(sub)

            # Use this folder
            move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__use__")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.model.output_dir == sub

            # Export
            move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__export__")
            await pilot.pause()
            await pilot.press("enter")  # open confirm
            await pilot.pause()
            await pilot.press("enter")  # confirm
            await pilot.pause()

            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

            assert app._export_error is None
            assert sub.exists()
            assert list(sub.glob("*.gpx")), "Expected at least one GPX in chosen output folder"

    asyncio.run(_run())


def test_tui_save_prefix_persists_across_folder_navigation(tmp_path: Path) -> None:
    """
    E2E: set output prefix, navigate folders, and confirm the prefix persists.
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
            app._goto("Save")
            await pilot.pause()
            assert app.step == "Save"

            # Set prefix programmatically (avoids needing to Tab-focus in tests).
            prefix = "MY_PREFIX"
            inp = app.query_one("#output_prefix", Input)
            inp.value = prefix
            await pilot.pause()

            # Navigate into subfolder and back out.
            await pilot.press("enter")  # enter sub_out (first directory)
            await pilot.pause()
            assert str(getattr(app, "_save_browser_dir", "")) == str(sub)

            move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__up__")
            await pilot.pause()
            await pilot.press("enter")  # go up
            await pilot.pause()
            assert str(getattr(app, "_save_browser_dir", "")) == str(base)

            # Prefix should persist after re-render.
            inp2 = app.query_one("#output_prefix", Input)
            assert (inp2.value or "").strip() == prefix

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
            app._goto("Save")
            await pilot.pause()

            # Export
            move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__export__")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)

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
            app._goto("Save")
            await pilot.pause()

            # Export
            move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__export__")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
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

            assert app.step == "Save"
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


@pytest.mark.parametrize(
    "change_folder,nav_before_export,nav_after_export,set_prefix,rename_strategy",
    [
        # Baseline: no folder change, export only
        (False, False, False, False, "none"),
        # Change folder then export
        (True, False, False, False, "none"),
        # Navigate around (but keep folder), then export
        (False, True, False, False, "none"),
        # Prefix set before export (should persist through folder nav)
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
    set_prefix: bool,
    rename_strategy: str,
) -> None:
    """
    Combinatorial E2E coverage for Save step to catch state bugs:
    - changing output folder vs keeping it
    - navigating folders before/after export
    - keeping prefix stable across renders
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
            app._goto("Save")
            await pilot.pause()
            assert app.step == "Save"

            # Optionally set prefix up-front (should survive folder navigation / re-renders).
            prefix_val = "SCENARIO_PREFIX" if set_prefix else ""
            if set_prefix:
                app.query_one("#output_prefix", Input).value = prefix_val
                await pilot.pause()

            # Optionally navigate within save browser before export.
            if nav_before_export:
                # Enter first dir (sub_out by name sort); then back up; then into sib_out; then back up.
                await pilot.press("enter")
                await pilot.pause()
                move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__up__")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                # Move to sib_out explicitly by key (dir:PATH)
                move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key=f"dir:{sib}")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__up__")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

            # Optionally change the output folder.
            expected_out_dir = base
            if change_folder:
                # Enter sub_out (first directory row), then select it as output.
                await pilot.press("enter")
                await pilot.pause()
                assert str(getattr(app, "_save_browser_dir", "")) == str(sub)
                move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__use__")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                expected_out_dir = sub
                assert app.model.output_dir == expected_out_dir
            else:
                assert app.model.output_dir == base

            # Prefix should persist (even after folder navigation + selection).
            if set_prefix:
                assert (app.query_one("#output_prefix", Input).value or "").strip() == prefix_val

            # Export
            move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__export__")
            await pilot.pause()
            await pilot.press("enter")  # open confirm
            await pilot.pause()
            await pilot.press("enter")  # confirm
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
                manifest = list(app._export_manifest or [])
                assert manifest

                if rename_strategy == "first":
                    old0 = manifest[0][0]
                    ext0 = Path(old0).suffix
                    new0 = f"RENAMED_0{ext0}"
                    app.query_one("#rename_0", Input).value = new0
                    await pilot.pause()
                    await pilot.press("r")
                    await pilot.pause()
                    assert (expected_out_dir / new0).exists()
                    assert not (expected_out_dir / old0).exists()
                else:
                    # Rename every file to a deterministic, unique name.
                    new_names: list[tuple[str, str]] = []
                    for i, (fn, _fmt, _cnt, _sz) in enumerate(manifest):
                        ext = Path(fn).suffix
                        new_fn = f"RENAMED_{i}{ext}"
                        app.query_one(f"#rename_{i}", Input).value = new_fn
                        new_names.append((fn, new_fn))
                    await pilot.pause()
                    await pilot.press("r")
                    await pilot.pause()
                    for old_fn, new_fn in new_names:
                        assert (expected_out_dir / new_fn).exists()
                        assert not (expected_out_dir / old_fn).exists()

            # Optionally navigate after export and ensure rename fields/prefix persist.
            if nav_after_export:
                # Navigate into a folder and back up; ensure prefix field is still present and stable.
                move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key=f"dir:{sub if expected_out_dir == base else base}")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__up__")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                if set_prefix:
                    assert (app.query_one("#output_prefix", Input).value or "").strip() == prefix_val

    asyncio.run(_run())
