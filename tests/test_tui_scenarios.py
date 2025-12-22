from __future__ import annotations

import asyncio
from pathlib import Path

from tests.tui_harness import ArtifactRecorder, copy_fixture_to_tmp, get_bitterroots_complete_fixture, select_folder_for_test


def _pick_first_folder_id(app) -> str:
    assert app.model.parsed is not None, "Expected parsed data after List_data render"
    folders = getattr(app.model.parsed, "folders", {}) or {}
    assert folders, "Expected at least one folder in Bitterroots Complete fixture"
    return next(iter(folders.keys()))


def _select_first_folder(app) -> str:
    """Pick and select the first folder (handles multi-folder datasets)."""
    folder_id = _pick_first_folder_id(app)
    select_folder_for_test(app, folder_id)
    return folder_id


def test_tui_bitterroots_complete_fixture_is_present_and_large() -> None:
    # Guardrail: fail loudly if this fixture is accidentally deleted or replaced.
    p = get_bitterroots_complete_fixture()
    assert p.exists()
    assert p.stat().st_size >= 1_000_000


def test_tui_e2e_export_real_bitterroots_complete(tmp_path: Path) -> None:
    """
    End-to-end: drive the TUI through Preview (Preview & Export) and run a real export to tmp_path.

    We seed the model input_path directly (rather than driving DirectoryTree) for stability.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "onx_ready"

        rec = ArtifactRecorder("bitterroots_complete_e2e_export_real")

        app = CairnTuiApp()
        app.model.input_path = fixture_copy

        async with app.run_test() as pilot:
            # List_data causes parse + summary rendering.
            app._goto("List_data")
            await pilot.pause()
            rec.snapshot(app, label="list_data")

            # Continue to Folder step.
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="folder")

            # Select a folder deterministically (avoid relying on DataTable cursor inference).
            _select_first_folder(app)
            await pilot.press("enter")  # -> Routes
            await pilot.pause()
            rec.snapshot(app, label="routes")

            assert app.step == "Routes"
            app.action_focus_table()
            await pilot.pause()
            rec.snapshot(app, label="routes")

            await pilot.press("enter")  # -> Waypoints
            await pilot.pause()
            rec.snapshot(app, label="waypoints")
            assert app.step == "Waypoints"

            app.action_focus_table()
            await pilot.pause()
            rec.snapshot(app, label="waypoints")

            await pilot.press("enter")  # -> Preview
            await pilot.pause()
            rec.snapshot(app, label="preview")
            assert app.step == "Preview"

            # Real export into tmp_path.
            app.model.output_dir = out_dir
            await pilot.press("enter")  # Trigger export
            await pilot.pause()
            rec.snapshot(app, label="export_started")

            # Wait for export to complete (background thread updates state).
            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)
            rec.snapshot(app, label="export_done")

            assert app._export_in_progress is False
            assert app._export_error is None
            assert app._export_manifest is not None
            assert out_dir.exists() and out_dir.is_dir()

            # Assert every manifest file exists and matches the manifest size.
            for fn, _fmt, _count, sz in app._export_manifest:
                p = out_dir / fn
                assert p.exists(), f"Missing exported file listed in manifest: {p}"
                assert p.stat().st_size > 0
                assert p.stat().st_size == sz

        rec.write_index()

    asyncio.run(_run())


def test_tui_export_error_when_output_path_is_a_file(tmp_path: Path) -> None:
    """Negative export: if output dir can't be created, Preview & Export should render an error."""

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        not_a_dir = tmp_path / "not_a_dir"
        not_a_dir.write_text("I am a file, not a directory", encoding="utf-8")

        rec = ArtifactRecorder("bitterroots_complete_export_error_output_is_file")

        app = CairnTuiApp()
        app.model.input_path = fixture_copy

        async with app.run_test() as pilot:
            app._goto("List_data")
            await pilot.pause()
            await pilot.press("enter")  # -> Folder
            await pilot.pause()
            _select_first_folder(app)
            await pilot.press("enter")  # -> Routes
            await pilot.pause()
            await pilot.press("enter")  # -> Waypoints
            await pilot.pause()
            await pilot.press("enter")  # -> Preview
            await pilot.pause()
            assert app.step == "Preview"
            rec.snapshot(app, label="preview")

            app.model.output_dir = not_a_dir
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            # Error should be set synchronously (mkdir fails before thread starts).
            rec.snapshot(app, label="export_failed")
            assert app._export_in_progress is False
            assert app._export_manifest is None
            assert app._export_error is not None
            assert "Failed to create output dir" in app._export_error

        rec.write_index()

    asyncio.run(_run())
