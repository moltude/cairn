"""Regression tests for empirically-verified TUI usability bugs.

One test per bug:

1. '/' search input must keep focus while typing (refresh must not steal it).
2. Esc on the post-export "Migrate another file?" prompt must NOT quit the app.
3. Esc must close the topmost ModalScreen without rewinding the workflow step
   behind it.
4. Space-toggle selection must not be quadratic in cursor position on large
   tables (cursor restore sets the coordinate directly, scheduled once).
5. Export must not silently overwrite existing output files (confirm first).
6. Enter on the multi-folder Folder step with nothing selected must tell the
   user to press Space.
7. Ctrl+N with unsaved edits must ask for confirmation before discarding.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Static

from tests.tui_harness import (
    get_bitterroots_complete_fixture,
    get_tui_two_waypoints_fixture,
    repo_root,
    select_folder_for_test,
)

MANY_WAYPOINTS_10K_FIXTURE = Path("tests/fixtures/edge_cases/many_waypoints_10000.gpx")


def _first_folder_id(app) -> str:
    assert app.model.parsed is not None, "Expected parsed data"
    folders = getattr(app.model.parsed, "folders", {}) or {}
    assert folders, "Expected at least one folder"
    return next(iter(folders.keys()))


async def _load_to_step(app, pilot, step: str) -> None:
    """Parse the input, select the first folder, and go to the given step."""
    app._goto("List_data")
    await pilot.pause()
    select_folder_for_test(app, _first_folder_id(app))
    app._goto(step)
    await pilot.pause()
    assert app.step == step


async def _wait_export_done(app, *, max_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        if not app._export_in_progress:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("Timed out waiting for export to finish")


# ---------------------------------------------------------------------------
# Bug 1: search box steals its own focus after one keystroke
# ---------------------------------------------------------------------------
def test_waypoints_search_keeps_focus_while_typing(tmp_path: Path) -> None:
    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        app = CairnTuiApp()
        app.model.input_path = get_tui_two_waypoints_fixture()

        async with app.run_test() as pilot:
            await _load_to_step(app, pilot, "Waypoints")

            search = app.query_one("#waypoints_search", Input)
            search.focus()
            await pilot.pause()

            for ch in "campi":
                await pilot.press(ch)
                await pilot.pause()
            # Give any deferred cursor-restore callbacks a chance to run
            # (the old bug stole focus from a scheduled restore).
            await asyncio.sleep(0.15)
            await pilot.pause()

            assert search.value == "campi", (
                f"Search input should hold the full query, got {search.value!r}"
            )
            focused_id = getattr(getattr(app, "focused", None), "id", None)
            assert focused_id == "waypoints_search", (
                f"Focus must stay on the search input while typing, got {focused_id!r}"
            )
            # The filter must actually have applied ('campi' matches only 'Camping').
            table = app.query_one("#waypoints_table", DataTable)
            assert int(table.row_count) == 1, (
                f"Expected 1 filtered row for 'campi', got {table.row_count}"
            )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bug 2: Esc after a successful export quits the whole app
# ---------------------------------------------------------------------------
def test_escape_on_post_export_prompt_does_not_quit(tmp_path: Path) -> None:
    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from cairn.tui.edit_screens.overlays import ConfirmOverlay

        app = CairnTuiApp()
        app.model.input_path = get_tui_two_waypoints_fixture()

        async with app.run_test() as pilot:
            await _load_to_step(app, pilot, "Preview")

            # Open the post-export prompt exactly as _on_export_done does
            # (no pending _confirm_callback).
            overlay = app.query_one("#confirm_overlay", ConfirmOverlay)
            overlay.open(title="Export complete", message="Migrate another file?")
            await pilot.pause()
            assert overlay.has_class("open")

            await pilot.press("escape")
            await pilot.pause()

            assert not overlay.has_class("open"), "Esc should dismiss the prompt"
            assert app.is_running, "Esc on the post-export prompt must NOT quit the app"
            assert app.step == "Preview", "User must remain on the Preview step"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bug 3: Esc cannot close ModalScreens and silently rewinds the step behind them
# ---------------------------------------------------------------------------
def test_escape_closes_modal_without_rewinding_step(tmp_path: Path) -> None:
    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        app = CairnTuiApp()
        app.model.input_path = get_tui_two_waypoints_fixture()

        async with app.run_test() as pilot:
            await _load_to_step(app, pilot, "Preview")

            await pilot.press("question_mark")
            await pilot.pause()
            assert isinstance(app.screen, ModalScreen), "Help modal should be open"

            await pilot.press("escape")
            await pilot.pause()

            assert not isinstance(app.screen, ModalScreen), (
                "Esc must close the help modal"
            )
            assert app.step == "Preview", (
                f"Esc on a modal must not rewind the workflow step, got {app.step!r}"
            )

            # With no modal open, Esc acts as normal 'back' again.
            await pilot.press("escape")
            await pilot.pause()
            assert app.step != "Preview", "Esc with no modal open should navigate back"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bug 4: Space-toggle was quadratic in cursor position (5.8s at row 6000)
# ---------------------------------------------------------------------------
def test_selection_toggle_fast_on_10k_row_table(tmp_path: Path) -> None:
    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        fixture = repo_root() / MANY_WAYPOINTS_10K_FIXTURE
        assert fixture.exists(), f"Missing fixture: {fixture}"

        app = CairnTuiApp()
        app.model.input_path = fixture

        async with app.run_test() as pilot:
            await _load_to_step(app, pilot, "Waypoints")

            table = app.query_one("#waypoints_table", DataTable)
            assert int(table.row_count) >= 10_000, (
                f"Stress fixture should yield >=10k rows, got {table.row_count}"
            )
            table.focus()
            await pilot.pause()

            target_row = 6000
            table.cursor_coordinate = Coordinate(target_row, 0)
            await pilot.pause()
            assert int(table.cursor_row) == target_row

            before_selected = len(app._selected_waypoint_keys)
            t0 = time.perf_counter()
            app.action_toggle_select()
            await pilot.pause()
            # Allow any deferred restore callbacks to complete before stopping the clock.
            await asyncio.sleep(0.1)
            await pilot.pause()
            elapsed = time.perf_counter() - t0

            assert len(app._selected_waypoint_keys) == before_selected + 1, (
                "Space toggle should have selected exactly one waypoint"
            )
            table_after = app.query_one("#waypoints_table", DataTable)
            assert int(table_after.cursor_row) == target_row, (
                f"Cursor should be restored to row {target_row}, got {table_after.cursor_row}"
            )
            # Old behavior: ~5.8s at row 6000 (cursor restored via ~12,000
            # cursor_up/cursor_down actions, scheduled twice). New behavior sets
            # the coordinate directly: measured ~0.5s locally (dominated by the
            # 10k-row rebuild) but 3.3s on GitHub's py3.10 ubuntu runner — the
            # environment alone costs ~7x. The threshold must separate the fixed
            # path (<~4s even on a slow runner) from the quadratic one (~6s on a
            # fast machine, ~30s+ on that same slow runner), so 8s: past any
            # honest constant-time run, well under any quadratic return.
            assert elapsed < 8.0, (
                f"Toggling selection at row {target_row} of a 10k-row table took "
                f"{elapsed:.2f}s; quadratic cursor restore has likely returned"
            )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bug 5: export silently overwrites existing output files
# ---------------------------------------------------------------------------
def test_export_overwrite_requires_confirmation(tmp_path: Path) -> None:
    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        async def run_session(*, expect_prompt: bool) -> None:
            app = CairnTuiApp()
            app.model.input_path = get_tui_two_waypoints_fixture()
            app.model.output_dir = out_dir

            async with app.run_test() as pilot:
                app._post_save_prompt_shown = True  # keep the post-save prompt out of the way
                await _load_to_step(app, pilot, "Preview")

                filename_input = app.query_one("#export_filename_input", Input)
                filename_input.value = "overwrite_check"
                await pilot.pause()

                app.action_export()
                await pilot.pause()

                if not expect_prompt:
                    # Fresh directory: no confirmation, export just runs.
                    assert not app._overlay_open("#confirm_overlay"), (
                        "No overwrite prompt expected for a fresh output directory"
                    )
                    await _wait_export_done(app)
                    assert app._export_error is None, app._export_error
                    assert app._export_manifest, "Export should produce a manifest"
                    return

                # Second export into the same directory: must prompt, not write.
                assert app._overlay_open("#confirm_overlay"), (
                    "Exporting over existing files must show a confirmation"
                )
                assert not app._export_in_progress, (
                    "Export must not start while the overwrite prompt is open"
                )

                # Esc cancels: nothing written.
                mtimes_before = {p.name: p.stat().st_mtime_ns for p in out_dir.iterdir()}
                await pilot.press("escape")
                await pilot.pause()
                assert not app._overlay_open("#confirm_overlay")
                assert not app._export_in_progress
                assert app._export_manifest is None, "Cancelled export must not run"
                mtimes_after = {p.name: p.stat().st_mtime_ns for p in out_dir.iterdir()}
                assert mtimes_after == mtimes_before, (
                    "Cancelling the overwrite prompt must not touch existing files"
                )

                # Trigger again and confirm: export proceeds.
                app.action_export()
                await pilot.pause()
                assert app._overlay_open("#confirm_overlay")
                await pilot.press("enter")  # Yes
                await pilot.pause()
                await _wait_export_done(app)
                assert app._export_error is None, app._export_error
                assert app._export_manifest, "Confirmed export should produce a manifest"

        await run_session(expect_prompt=False)
        assert any(out_dir.iterdir()), "First export should have written files"
        await run_session(expect_prompt=True)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bug 6: multi-folder Folder step, Enter with nothing selected says nothing
# ---------------------------------------------------------------------------
def test_folder_enter_without_selection_shows_message(tmp_path: Path) -> None:
    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        app = CairnTuiApp()
        app.model.input_path = get_bitterroots_complete_fixture()

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()
            folders = getattr(app.model.parsed, "folders", {}) or {}
            assert len(folders) > 1, "Fixture must have multiple folders for this test"

            app._goto("Folder")
            await pilot.pause()
            assert app.step == "Folder"
            assert not app._selected_folders

            subtitle_before = str(app.query_one("#main_subtitle", Static).render())

            await pilot.press("enter")
            await pilot.pause()

            assert app.step == "Folder", "Enter with no selection must not advance"
            subtitle = str(app.query_one("#main_subtitle", Static).render())
            assert subtitle != subtitle_before, (
                "Pressing Enter with no folder selected must surface feedback "
                f"(subtitle unchanged: {subtitle!r})"
            )
            assert "No folder selected" in subtitle and "Space" in subtitle, (
                f"Subtitle should say nothing is selected and to press Space, got {subtitle!r}"
            )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bug 7: Ctrl+N discards every unsaved edit instantly, no confirmation
# ---------------------------------------------------------------------------
def test_ctrl_n_with_unsaved_edits_requires_confirmation(tmp_path: Path) -> None:
    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        app = CairnTuiApp()
        app.model.input_path = get_tui_two_waypoints_fixture()

        async with app.run_test() as pilot:
            await _load_to_step(app, pilot, "Waypoints")

            # Mark the session as edited (the same flag a real applied edit sets).
            app._waypoints_edited = True

            await pilot.press("ctrl+n")
            await pilot.pause()

            assert app._overlay_open("#confirm_overlay"), (
                "Ctrl+N with unsaved edits must ask for confirmation"
            )
            assert app.step == "Waypoints", "Session must not be reset before confirming"
            assert app.model.parsed is not None, "Parsed data must survive until confirmed"

            # Esc cancels: nothing is lost.
            await pilot.press("escape")
            await pilot.pause()
            assert not app._overlay_open("#confirm_overlay")
            assert app.step == "Waypoints"
            assert app.model.parsed is not None

            # Ctrl+N again, confirm Yes: session resets.
            await pilot.press("ctrl+n")
            await pilot.pause()
            assert app._overlay_open("#confirm_overlay")
            await pilot.press("enter")  # Yes
            await pilot.pause()
            assert app.step == "Select_file", "Confirmed Ctrl+N should start a new file"
            assert app.model.parsed is None

    asyncio.run(_run())


def test_ctrl_n_without_edits_needs_no_confirmation(tmp_path: Path) -> None:
    """Companion to bug 7: no edits -> no prompt (unchanged fast path)."""

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        app = CairnTuiApp()
        app.model.input_path = get_tui_two_waypoints_fixture()

        async with app.run_test() as pilot:
            await _load_to_step(app, pilot, "Waypoints")
            assert not app._routes_edited and not app._waypoints_edited

            await pilot.press("ctrl+n")
            await pilot.pause()

            assert not app._overlay_open("#confirm_overlay"), (
                "Ctrl+N without edits must not prompt"
            )
            assert app.step == "Select_file"
            assert app.model.parsed is None

    asyncio.run(_run())
