from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import Input

from cairn.core.color_mapper import ColorMapper
from cairn.core.config import get_all_onx_icons, normalize_onx_icon_name

from tests.tui_harness import ArtifactRecorder, copy_fixture_to_tmp


def _pick_first_folder_id(app) -> str:
    assert app.model.parsed is not None, "Expected parsed data after List_data render"
    folders = getattr(app.model.parsed, "folders", {}) or {}
    assert folders, "Expected at least one folder in fixture"
    return next(iter(folders.keys()))

def _pick_folder_id_with_min_waypoints(app, *, min_waypoints: int = 2) -> str:
    assert app.model.parsed is not None, "Expected parsed data after List_data render"
    folders = getattr(app.model.parsed, "folders", {}) or {}
    for folder_id, fd in (folders or {}).items():
        waypoints = list((fd or {}).get("waypoints", []) or [])
        if len(waypoints) >= int(min_waypoints):
            return str(folder_id)
    assert False, f"No folder found with >= {min_waypoints} waypoints"


def _pick_preferred_icon() -> str:
    icons = get_all_onx_icons()
    # Prefer a commonly-known one if present for readability in assertions/artifacts.
    for preferred in ("Parking", "Camp", "Summit", "View", "Location"):
        canon = normalize_onx_icon_name(preferred)
        if canon and canon in icons:
            return canon
    return icons[0]


def test_tui_e2e_editing_then_export_real(tmp_path: Path) -> None:
    """
    End-to-end: open edit modals in Routes/Waypoints, apply edits, then export and
    assert output reflects those edits.
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        out_dir = tmp_path / "onx_ready"

        rec = ArtifactRecorder("bitterroots_complete_e2e_editing_export_real")

        app = CairnTuiApp()
        app.model.input_path = fixture_copy

        route_new_title = "TUI_ROUTE_RENAMED"
        wp_new_title = "TUI_WP_RENAMED"
        wp_desc_raw = r"TUI_DESC\nLINE2"
        preferred_icon_choice = _pick_preferred_icon()

        async with app.run_test() as pilot:
            async def _wait_for_selector(selector: str, *, max_steps: int = 80) -> None:
                """
                Wait for a widget selector to exist on the active screen.
                """
                for _ in range(max_steps):
                    try:
                        app.query_one(selector)
                        return
                    except Exception:
                        await pilot.pause()
                        await asyncio.sleep(0)
                raise AssertionError(f"Timed out waiting for selector: {selector} (screen={app.screen!r})")

            # Parse + summary.
            app._goto("List_data")
            await pilot.pause()
            rec.snapshot(app, label="list_data")

            # -> Folder
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="folder")

            # Deterministically pick a folder.
            app.model.selected_folder_id = _pick_first_folder_id(app)
            app._goto("Routes")
            await pilot.pause()
            rec.snapshot(app, label="routes")
            assert app.step == "Routes"

            # Select first route.
            app.action_focus_table()
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            rec.snapshot(app, label="routes_selected_one")
            assert len(app._selected_route_keys) >= 1

            # Actions -> Rename
            await pilot.press("a")
            await pilot.pause()
            rec.snapshot(app, label="routes_actions_modal")
            # Default cursor is Rename; Enter selects.
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="routes_rename_overlay")

            # Fill rename input programmatically; then Tab -> Apply -> Enter.
            await _wait_for_selector("#rename_value")
            app.query_one("#rename_value", Input).value = route_new_title
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="routes_renamed")

            tracks, _ = app._current_folder_features()
            assert any(getattr(t, "title", "") == route_new_title for t in tracks)

            # Actions -> Color
            # We should be back in the inline overlay; move to Color row (Name -> Desc -> Color).
            await pilot.press("down")
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="routes_color_modal")

            # Pick first palette entry.
            await _wait_for_selector("#palette_table")
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="routes_color_applied")

            # Assert stroke was set to a #RRGGBB.
            assert tracks, "Expected at least one track in selected folder"
            assert str(getattr(tracks[0], "stroke", "") or "").startswith("#")

            # Ensure we're back on the Routes screen (modal fully dismissed) before continuing.
            await _wait_for_selector("#routes_table")
            assert app.step == "Routes"

            # -> Waypoints
            # Close inline overlay (if open) so focus returns to the main UI before step change.
            await pilot.press("escape")
            await pilot.pause()
            app._goto("Waypoints")
            await pilot.pause()
            rec.snapshot(app, label="waypoints")
            assert app.step == "Waypoints"

            # Select first waypoint.
            app.action_focus_table()
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_selected_one")
            assert len(app._selected_waypoint_keys) >= 1

            # Actions -> Rename waypoint
            await pilot.press("a")
            await pilot.pause()
            await pilot.press("enter")  # Rename
            await pilot.pause()
            rec.snapshot(app, label="waypoints_rename_modal")
            await _wait_for_selector("#rename_value")
            app.query_one("#rename_value", Input).value = wp_new_title
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_renamed")

            _, waypoints = app._current_folder_features()
            assert waypoints, "Expected at least one waypoint in selected folder"
            assert any(getattr(w, "title", "") == wp_new_title for w in waypoints)

            # Actions -> Set icon override
            # Inline overlay should be open; move to Icon row (Name -> Desc -> Icon).
            await pilot.press("down")  # description
            await pilot.press("down")  # icon
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_icon_modal")

            # Best-effort: filter icons (if change events fire) and pick first match.
            # Even if filtering doesn't apply (Textual version differences), we still
            # accept the selected icon and assert it appears in output.
            await _wait_for_selector("#icon_search")
            app.screen.query_one("#icon_search", Input).value = preferred_icon_choice
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_icon_applied")

            # Actions -> Set waypoint color
            # Back to inline overlay; move to Color row (Desc -> Icon -> Color).
            await pilot.press("down")  # description
            await pilot.press("down")  # icon
            await pilot.press("down")  # color
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_color_modal")
            await _wait_for_selector("#palette_table")
            await pilot.press("enter")  # choose first palette entry
            await pilot.pause()
            rec.snapshot(app, label="waypoints_color_applied")

            # Actions -> Set description
            # Back to inline overlay; move to Description row (Name -> Desc).
            await pilot.press("down")  # description
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_description_modal")
            await _wait_for_selector("#description_value")
            app.query_one("#description_value", Input).value = wp_desc_raw
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_description_applied")

            # Validate edits on the edited waypoint.
            # Note: table display is sorted by name, while the underlying parsed list
            # order is not guaranteed. So we locate the edited record by title.
            edited_wp = next((w for w in waypoints if getattr(w, "title", "") == wp_new_title), None)
            assert edited_wp is not None, f"Expected to find edited waypoint titled {wp_new_title}"
            assert getattr(edited_wp, "description", "") == "TUI_DESC\nLINE2"
            assert isinstance(getattr(edited_wp, "properties", None), dict)
            applied_icon = (edited_wp.properties.get("cairn_onx_icon_override") or "").strip()
            assert applied_icon
            assert applied_icon in set(get_all_onx_icons())
            assert getattr(edited_wp, "color", ""), "Expected waypoint color to be set"
            # Color should be 6 hex chars; we set from palette so it should parse.
            r, g, b = ColorMapper.parse_color(str(getattr(edited_wp, "color", "")))
            assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255

            # -> Preview -> Save
            app._goto("Preview")
            await pilot.pause()
            rec.snapshot(app, label="preview")
            assert app.step == "Preview"

            app._goto("Save")
            await pilot.pause()
            rec.snapshot(app, label="save")
            assert app.step == "Save"

            # Export into tmp output dir.
            app.model.output_dir = out_dir
            # Trigger export via Save browser: move to [Export] row, then Enter.
            from tests.tui_harness import move_datatable_cursor_to_row_key
            app.action_focus_table()
            await pilot.pause()
            move_datatable_cursor_to_row_key(app, table_id="save_browser", target_row_key="__export__")
            await pilot.pause()
            await pilot.press("enter")  # open Confirm Export modal
            await pilot.pause()
            await pilot.press("enter")  # confirm export
            await pilot.pause()
            rec.snapshot(app, label="export_started")

            for _ in range(600):
                if not app._export_in_progress:
                    break
                await asyncio.sleep(0.05)
            rec.snapshot(app, label="export_done")

            assert app._export_in_progress is False
            assert app._export_error is None
            assert out_dir.exists() and out_dir.is_dir()

            # Validate output contains our edits.
            gpx_files = sorted(out_dir.glob("*.gpx"))
            assert gpx_files, "Expected at least one GPX output file"
            contents = [p.read_text(encoding="utf-8", errors="ignore") for p in gpx_files]
            assert any(wp_new_title in c for c in contents), (
                "Expected renamed waypoint title to appear in at least one exported GPX"
            )
            assert any(f"<onx:icon>{applied_icon}</onx:icon>" in c for c in contents), (
                "Expected OnX icon override to appear in at least one exported GPX"
            )

        rec.write_index()

    asyncio.run(_run())


def test_tui_e2e_multiselect_waypoint_color_and_focus_not_frozen(tmp_path: Path) -> None:
    """
    E2E regression test:
    - Multi-select 2 waypoints
    - Apply a color via the overlay color picker
    - Close inline overlay
    - Verify the underlying table has focus and responds to navigation keys (not "frozen")
    """

    async def _run() -> None:
        from cairn.tui.app import CairnTuiApp
        from textual.widgets import DataTable

        fixture_copy = copy_fixture_to_tmp(tmp_path)
        rec = ArtifactRecorder("bitterroots_complete_e2e_multiselect_waypoint_color_focus")

        app = CairnTuiApp()
        app.model.input_path = fixture_copy

        async with app.run_test() as pilot:
            # Parse + summary.
            app._goto("List_data")
            await pilot.pause()
            rec.snapshot(app, label="list_data")

            # -> Folder
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="folder")

            # Pick a folder with enough waypoints for multi-select.
            app.model.selected_folder_id = _pick_folder_id_with_min_waypoints(app, min_waypoints=3)

            # Jump to Waypoints deterministically (routes may be skipped depending on folder).
            app._goto("Waypoints")
            await pilot.pause()
            rec.snapshot(app, label="waypoints")
            assert app.step == "Waypoints"

            # Select 2 waypoints.
            app.action_focus_table()
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_selected_two")
            assert len(app._selected_waypoint_keys) == 2

            # Open inline overlay, choose Color row, open picker.
            await pilot.press("a")
            await pilot.pause()
            rec.snapshot(app, label="inline_overlay_open")

            # Name -> Description -> Icon -> Color
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="color_picker_open")

            # Apply first palette color.
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="color_applied_back_to_inline")

            # Close inline overlay; focus should restore to the main table.
            await pilot.press("escape")
            await pilot.pause()
            rec.snapshot(app, label="inline_closed")

            tbl = app.query_one("#waypoints_table", DataTable)
            assert getattr(app.focused, "id", None) == "waypoints_table"

            # Prove key input is not "frozen": Down should move cursor row.
            before = int(getattr(tbl, "cursor_row", 0) or 0)
            await pilot.press("down")
            await pilot.pause()
            after = int(getattr(tbl, "cursor_row", 0) or 0)
            assert after != before, f"Expected cursor to move after Down (before={before}, after={after})"

            # Space should still toggle selection on the focused row.
            prev_sel = set(app._selected_waypoint_keys)
            await pilot.press("space")
            await pilot.pause()
            assert set(app._selected_waypoint_keys) != prev_sel

        rec.write_index()

    asyncio.run(_run())
