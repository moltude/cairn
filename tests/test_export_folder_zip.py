"""Export screen (UI-31): Download all and Download this folder.

bridge.export_folder_zip(n) hands out one folder of the LAST export_zip: the
same NN_Name/ path and the same bytes, nothing else. Download all's layout is
unchanged (one NN_Name/ subfolder per folder, then RUNBOOK.md).
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402

FX = Path(__file__).parent / "fixtures"
BITTERROOTS = FX / "bitterroots" / "Bitterroots__Complete_.json"
ONX_PAIR = [FX / "onx_dialect" / "onx_dialect.gpx", FX / "onx_dialect" / "onx_dialect.kml"]


def _zip(b) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(bytes(b)))


def _bitterroots() -> zipfile.ZipFile:
    bridge.load_document(BITTERROOTS.read_text(encoding="utf-8"), BITTERROOTS.name)
    return _zip(bridge.export_zip())


def test_download_all_layout_is_one_numbered_subfolder_per_folder_then_the_runbook():
    zf = _bitterroots()
    manifest = bridge._STATE["manifest"]
    names = zf.namelist()
    assert names[-1] == "RUNBOOK.md"
    want = [f["path"] for e in manifest for f in e["files"]]
    assert names[:-1] == want
    # NN_ prefixes in screen order, every file inside its folder's directory.
    for e in manifest:
        prefix = f"{e['n']:02d}_{e['safe']}/"
        assert e["files"] and all(f["path"].startswith(prefix) for f in e["files"])
    assert [e["n"] for e in manifest] == sorted(e["n"] for e in manifest)


def test_each_folder_zip_holds_exactly_its_files_byte_identical_to_download_all():
    full = _bitterroots()
    manifest = bridge._STATE["manifest"]
    assert len(manifest) == 10
    seen = []
    for e in manifest:
        one = _zip(bridge.export_folder_zip(e["n"]))
        assert one.testzip() is None
        assert one.namelist() == [f["path"] for f in e["files"]]
        assert "RUNBOOK.md" not in one.namelist()
        for name in one.namelist():
            assert one.read(name) == full.read(name), name
        seen += one.namelist()
    # Together the folder zips are Download all minus RUNBOOK.md.
    assert seen == full.namelist()[:-1]


def test_folder_zip_needs_no_second_export_and_follows_the_latest_one():
    full = _bitterroots()
    first = bridge._STATE["manifest"][0]
    before = _zip(bridge.export_folder_zip(first["n"]))
    again = _zip(bridge.export_folder_zip(first["n"]))
    assert [again.read(n) for n in again.namelist()] == [before.read(n) for n in before.namelist()]
    # Exclude everything but one waypoint of folder 1 and export again: the
    # folder zip follows, with no stale Tracks/Areas file left from before.
    g = bridge._STATE["groups"][0]
    keep = next(i for i in g["items"] if i["kind"] == "waypoints")
    edits = {i["uid"]: {"included": False} for i in g["items"] if i is not keep}
    bridge.apply_edits(json.dumps(edits))
    bridge.export_zip()
    after = _zip(bridge.export_folder_zip(first["n"]))
    assert after.namelist() == [f"01_{first['safe']}/{first['safe']}_Waypoints.gpx"]
    assert full.namelist() != after.namelist()


def test_folder_numbers_are_the_screen_numbers_not_list_positions(tmp_path):
    """A folder that wrote no file is skipped on screen but keeps its number,
    so export_folder_zip looks folders up by n."""
    bridge.load_files(json.dumps([{"name": p.name, "text": p.read_text(encoding="utf-8")} for p in ONX_PAIR]))
    bridge.export_zip()
    (e,) = bridge._STATE["manifest"]
    one = _zip(bridge.export_folder_zip(e["n"]))
    assert sorted(one.namelist()) == [
        "01_onx_dialect/onx_dialect_Areas.gpx",
        "01_onx_dialect/onx_dialect_Tracks.gpx",
        "01_onx_dialect/onx_dialect_Waypoints.gpx",
    ]
    assert e["safe"] == "onx_dialect"
    with pytest.raises(ValueError, match="No exported folder 2"):
        bridge.export_folder_zip(2)


def _one(files: int, count: int) -> list:
    return [{"n": 1, "folder": "Solo", "count": count, "expected": count, "dropped": 0,
             "files": [{"path": f"01_Solo/Solo_{k}.gpx", "count": 1, "kml": False}
                       for k in ("Waypoints", "Tracks", "Areas")[:files]]}]


def test_runbook_wording_is_singular_for_one_and_matches_the_screen():
    one = bridge.build_runbook(_one(1, 1))
    assert "**1 folder · 1 markup · 1 import**" in one
    assert "### 1. Solo  (1 markup · 1 file)" in one
    assert "1. In onX, choose **Import** and add this file: **Solo_Waypoints.gpx**" in one
    assert "2. Tick **Import map data to a new folder**." in one
    assert "3. onX names the folder by date. **Rename it to:** `Solo`" in one
    assert "My Content should show **1 folder** and **1 markup**." in one
    assert "together" not in one and "- [ ]" not in one
    three = bridge.build_runbook(_one(3, 31))
    assert "### 1. Solo  (31 markups · 3 files)" in three
    assert "add these 3 files together: **Solo_Waypoints.gpx, Solo_Tracks.gpx, Solo_Areas.gpx**" in three
    assert "Import each folder into onX's **Web Map** (webmap.onxmaps.com), one at a time." in three
