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
                        app.screen.query_one(selector)
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
            await pilot.press("enter")  # -> Routes
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

            # -> Edit_routes (new step)
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="edit_routes")
            assert app.step == "Edit_routes"

            # Actions -> Rename
            await pilot.press("a")
            await pilot.pause()
            rec.snapshot(app, label="routes_actions_modal")
            # Default cursor is Rename; Enter selects.
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="routes_rename_modal")

            # Fill rename input programmatically; then Tab -> Apply -> Enter.
            await _wait_for_selector("#new_title")
            app.screen.query_one("#new_title", Input).value = route_new_title
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="routes_renamed")

            tracks, _ = app._current_folder_features()
            assert any(getattr(t, "title", "") == route_new_title for t in tracks)

            # Actions -> Color
            await pilot.press("a")
            await pilot.pause()
            # Move to "Set route color" row (rename -> desc -> color).
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

            # Ensure we're back on the Edit_routes screen (modal fully dismissed) before continuing.
            await _wait_for_selector("#edit_routes_table")
            assert app.step == "Edit_routes"

            # -> Waypoints
            await pilot.press("enter")
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

            # -> Edit_waypoints (new step)
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="edit_waypoints")
            assert app.step == "Edit_waypoints"

            # Actions -> Rename waypoint
            await pilot.press("a")
            await pilot.pause()
            await pilot.press("enter")  # Rename
            await pilot.pause()
            rec.snapshot(app, label="waypoints_rename_modal")
            await _wait_for_selector("#new_title")
            app.screen.query_one("#new_title", Input).value = wp_new_title
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_renamed")

            _, waypoints = app._current_folder_features()
            assert waypoints, "Expected at least one waypoint in selected folder"
            assert any(getattr(w, "title", "") == wp_new_title for w in waypoints)

            # Actions -> Set icon override
            await pilot.press("a")
            await pilot.pause()
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
            await pilot.press("a")
            await pilot.pause()
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
            await pilot.press("a")
            await pilot.pause()
            await pilot.press("down")  # description
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_description_modal")
            await _wait_for_selector("#new_description")
            app.screen.query_one("#new_description", Input).value = wp_desc_raw
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="waypoints_description_applied")

            # Validate edits on the first waypoint (selection is index-based).
            wp0 = waypoints[0]
            assert getattr(wp0, "title", "") == wp_new_title
            assert getattr(wp0, "description", "") == "TUI_DESC\nLINE2"
            assert isinstance(getattr(wp0, "properties", None), dict)
            applied_icon = (wp0.properties.get("cairn_onx_icon_override") or "").strip()
            assert applied_icon
            assert applied_icon in set(get_all_onx_icons())
            assert getattr(wp0, "color", ""), "Expected waypoint color to be set"
            # Color should be 6 hex chars; we set from palette so it should parse.
            r, g, b = ColorMapper.parse_color(str(getattr(wp0, "color", "")))
            assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255

            # -> Preview -> Save
            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="preview")
            assert app.step == "Preview"

            await pilot.press("enter")
            await pilot.pause()
            rec.snapshot(app, label="save")
            assert app.step == "Save"

            # Export into tmp output dir.
            app.model.output_dir = out_dir
            await pilot.press("e")
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
