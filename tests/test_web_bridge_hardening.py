"""Hardening of the folder primitives and the export (ENG-07 / UI-31).

Each test pins a bug found by driving web/bridge.py with synthetic maps
(tests/hardening_maps.py): hostile folder names, many folders, big folders,
and state left over from a previous map or export.
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402
from tests.hardening_maps import NASTY_NAMES, make_map  # noqa: E402

FX = Path(__file__).parent / "fixtures"


def _load_text(text: str, name: str = "m.json") -> dict:
    return json.loads(bridge.load_files(json.dumps([{"name": name, "text": text}])))


def _export() -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(bridge.export_zip()))


def _check_export(zf: zipfile.ZipFile) -> None:
    """The invariants every export must hold, whatever the folder names."""
    names = zf.namelist()
    assert len(names) == len(set(names)), "duplicate zip entries"
    for n in names:
        parts = n.split("/")
        assert not n.startswith("/") and ".." not in parts and "\\" not in n and "\x00" not in n
        assert all(len(p.encode("utf-8")) <= 255 for p in parts), f"component too long: {n[:60]}"
    manifest = bridge._STATE["manifest"]
    listed = {f["path"] for e in manifest for f in e["files"]}
    assert set(names) == listed | {"RUNBOOK.md"}
    included = sum(1 for g in bridge._STATE["groups"] for i in g["items"] if i.get("included", True))
    dropped = sum(e["dropped"] for e in manifest) + bridge._STATE["unlisted_dropped"]
    assert sum(e["count"] for e in manifest) + dropped == included
    for e in manifest:
        fz = zipfile.ZipFile(io.BytesIO(bridge.export_folder_zip(e["n"])))
        assert sorted(fz.namelist()) == sorted(f["path"] for f in e["files"])
        for n in fz.namelist():
            assert fz.read(n) == zf.read(n)
        for f in e["files"]:
            body = zf.read(f["path"]).decode("utf-8")
            assert len(re.findall(r"<wpt[ >]|<trk[ >]|<rte[ >]", body)) == f["count"]


def test_a_second_load_forgets_the_previous_export():
    """export_folder_zip(n) must not serve the previous map's files."""
    _load_text(make_map(3, seed=1, names=["One", "Two", "Three"]))
    bridge.export_zip()
    assert bridge._STATE["manifest"]
    _load_text(make_map(1, seed=2, names=["Other"]))
    with pytest.raises(ValueError, match="Export again"):
        bridge.export_folder_zip(1)
    zf = _export()
    # and after the new export it serves the NEW map
    fz = zipfile.ZipFile(io.BytesIO(bridge.export_folder_zip(1)))
    assert all("One" not in n for n in fz.namelist())
    _check_export(zf)


def test_export_folder_zip_without_any_export_is_a_value_error():
    _load_text(make_map(1, seed=3))
    with pytest.raises(ValueError):
        bridge.export_folder_zip(1)
    with pytest.raises(ValueError):
        bridge.export_folder_zip("x")


@pytest.mark.parametrize("length", [90, 255, 300, 5000])
def test_a_very_long_folder_name_exports(length):
    """A 300-character name made the directory name too long for the
    filesystem (OSError) and killed the export."""
    _load_text(make_map(2, seed=4, names=["x" * length, "ä" * length]))
    zf = _export()
    _check_export(zf)
    for e in bridge._STATE["manifest"]:
        assert len(e["safe"].encode("utf-8")) <= 80
    # the display name is untouched; only the file-system name is shortened
    assert any(e["folder"] == "x" * length for e in bridge._STATE["manifest"])


def test_renaming_to_a_very_long_name_still_exports():
    j = _load_text(make_map(2, seed=5, names=["Aa", "Bb"]))
    key = j["groups"][0]["key"]
    r = json.loads(bridge.rename_folder(key, "日本語" * 100))
    assert r["ok"] and len(r["safe"].encode("utf-8")) <= 80
    _check_export(_export())


def test_safe_never_ends_in_the_separator_or_empties():
    assert bridge._safe("a" * 79 + " b") == "a" * 79
    assert bridge._safe("🏔️") == "Unnamed"
    assert bridge._safe("..") == "Unnamed"
    assert bridge._safe("short name") == "short_name"


def test_every_hostile_name_exports_safely():
    _load_text(make_map(len(NASTY_NAMES), seed=6, per=(1, 2)))
    zf = _export()
    _check_export(zf)
    rb = zf.read("RUNBOOK.md").decode("utf-8")
    for e in bridge._STATE["manifest"]:
        assert f"### {e['n']}. " in rb


def test_names_with_the_same_safe_form_do_not_collide():
    _load_text(make_map(4, seed=7, names=["A/B", "A_B", "A:B", "A B"], per=(2, 2), kinds="w"))
    zf = _export()
    _check_export(zf)
    assert len({n.split("/")[0] for n in zf.namelist() if "/" in n}) == 5  # four folders + Unorganized


@pytest.mark.parametrize("n_folders", [0, 1, 30, 200])
def test_many_or_few_folders(n_folders):
    _load_text(make_map(n_folders, seed=8, per=(1, 3)))
    _check_export(_export())


def test_empty_folders_survive_and_never_break_export():
    j = _load_text(make_map(6, seed=9, empty=3))
    keys = [g["key"] for g in j["groups"]]
    empty = [g["key"] for g in j["groups"] if not g["items"]]
    assert empty
    real = next(g for g in j["groups"] if g["items"])
    bridge.move_items(json.dumps([real["items"][0]["uid"]]), target_key=empty[0])
    assert {g["key"] for g in bridge._STATE["groups"]} >= set(empty)
    _check_export(_export())
    assert len(keys) == len(j["groups"])


def test_a_folder_over_the_gpx_size_cap_splits_and_loses_nothing():
    _load_text(make_map(2, seed=10, big=6000, kinds="w", long_notes=True))
    zf = _export()
    _check_export(zf)
    big = max(bridge._STATE["manifest"], key=lambda e: e["count"])
    assert len(big["files"]) >= 2 and big["count"] == 6000
    # moving a few items out of the big folder and back keeps every item once
    g = max(bridge._STATE["groups"], key=lambda g: len(g["items"]))
    moved = [i["uid"] for i in g["items"][:50]]
    other = next(x for x in bridge._STATE["groups"] if x is not g)
    bridge.move_items(json.dumps(moved), target_key=other["key"])
    zf = _export()
    _check_export(zf)
    assert sum(e["count"] for e in bridge._STATE["manifest"]) == sum(
        len(x["items"]) for x in bridge._STATE["groups"])


def test_items_without_coordinates_are_counted_as_dropped_not_lost():
    _load_text(make_map(3, seed=11, no_coords=True))
    zf = _export()
    _check_export(zf)


def test_polygons_with_holes_and_long_notes_move_and_export():
    j = _load_text(make_map(3, seed=12, kinds="a", long_notes=True, holes=True))
    first, last = j["groups"][0], j["groups"][-1]
    bridge.move_items(json.dumps([i["uid"] for i in first["items"]]), target_key=last["key"])
    _check_export(_export())


def test_a_move_after_an_export_leaves_the_last_export_self_consistent():
    """Until the UI exports again, export_folder_zip serves the LAST export
    whole: its names, its bytes. It never mixes old and new folders."""
    j = _load_text(make_map(4, seed=13, names=["One", "Two", "Three", "Four"], kinds="w"))
    zf = _export()
    bridge.merge_folders(j["groups"][0]["key"], j["groups"][1]["key"])
    fz = zipfile.ZipFile(io.BytesIO(bridge.export_folder_zip(1)))
    for n in fz.namelist():
        assert fz.read(n) == zf.read(n)


def test_the_oldest_state_never_leaks_into_a_fresh_load_after_moves():
    j = _load_text(make_map(3, seed=14, names=["One", "Two", "Three"]))
    uids = [i["uid"] for i in j["groups"][0]["items"]]
    bridge.move_items(json.dumps(uids), new_name="Moved")
    bridge.export_zip()
    j2 = _load_text(make_map(3, seed=14, names=["One", "Two", "Three"]))
    assert [g["name"] for g in j2["groups"]] == [g["name"] for g in j["groups"]]
    assert bridge._STATE["next_folder"] == 1
    assert "Moved" not in {g["name"] for g in bridge._STATE["groups"]}
    assert not bridge._STATE.get("zip")
