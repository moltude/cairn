"""instructions.txt, the guide at the top of Download all (UI-31, round 4).

It replaced RUNBOOK.md: plain text with no Markdown, CRLF line endings, the
general import steps once, then each zip folder with the name to rename it to,
each file, the kind of item in it and every item's name, as written.
"""

from __future__ import annotations

import functools
import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402
from tests.blank_names import export_named  # noqa: E402

FX = Path(__file__).parent / "fixtures"
BITTERROOTS = FX / "bitterroots" / "Bitterroots__Complete_.json"
GPX = "{http://www.topografix.com/GPX/1/1}"

HEAD = [
    "How to import these files into onX",
    "",
    "Import each folder below into onX on a computer (webmap.onxmaps.com), one at a time.",
    "In onX, choose Import and add all of that folder's files together.",
    'Tick "Import map data to a new folder".',
    "onX names the new folder with a datetime stamp.",
    "Rename it to the name shown for that folder below.",
    "Importing needs onX Premium or Elite.",
]


def _export(path: Path = BITTERROOTS) -> zipfile.ZipFile:
    bridge.load_document(path.read_text(encoding="utf-8"), path.name)
    return zipfile.ZipFile(io.BytesIO(bytes(export_named(bridge))))


def _text(zf: zipfile.ZipFile) -> str:
    return zf.read("instructions.txt").decode("utf-8")


def test_it_replaces_the_runbook_and_is_the_last_member():
    zf = _export()
    assert zf.namelist()[-1] == "instructions.txt"
    assert not [n for n in zf.namelist() if n.endswith(".md")]


def test_every_line_ends_in_crlf_and_the_text_is_utf8():
    raw = _export().read("instructions.txt")
    assert raw.endswith(b"\r\n")
    assert raw.count(b"\n") == raw.count(b"\r\n") and raw.count(b"\r") == raw.count(b"\r\n")
    assert not raw.startswith(b"\xef\xbb\xbf")   # no BOM
    raw.decode("utf-8")


def test_no_markdown_at_all():
    """The owner's rule: no #, *, `, ** or - [ ]. Bitterroots' names are plain,
    so anything Markdown-looking came from the template."""
    text = _text(_export())
    for ln in text.split("\r\n"):
        s = ln.lstrip()
        assert not s.startswith(("#", "-", "*", ">", "`", "|")), ln
        assert not re.match(r"\d+\. ", s), ln
    for mark in ("**", "`", "- [ ]", "](", "\\_", "---"):
        assert mark not in text, mark


def test_the_general_steps_come_once_at_the_top():
    lines = _text(_export()).split("\r\n")
    assert lines[:len(HEAD)] == HEAD
    assert sum("Premium or Elite" in ln for ln in lines) == 1
    assert lines[len(HEAD)] == ""


def test_folder_file_kind_and_item_names_are_nested_as_written():
    zf = _export()
    lines = _text(zf).split("\r\n")
    body = lines[len(HEAD) + 1:]
    assert body[-1] == ""       # the final CRLF
    body = body[:-1]
    # Rebuild folder -> file -> kind -> names from the indentation alone.
    tree, folder, file = [], None, None
    for ln in body:
        depth = (len(ln) - len(ln.lstrip(" "))) // 4
        s = ln.strip()
        if not ln:
            continue
        if depth == 0:
            folder = {"line": s, "files": []}
            tree.append(folder)
        elif depth == 1:
            file = {"name": s, "kind": None, "items": []}
            folder["files"].append(file)
        elif depth == 2:
            assert file["kind"] is None
            file["kind"] = s
        elif depth == 3:
            file["items"].append(s)
        else:
            raise AssertionError(f"unexpected depth {depth}: {ln!r}")   # no warnings in Bitterroots
    manifest = bridge._STATE["manifest"]
    assert len(tree) == len(manifest) == 10
    tag = {"Waypoints": "wpt", "Lines": "trk", "Areas": "rte"}
    for e, f in zip(manifest, tree):
        assert f["line"] == f"{e['dir']}/    rename to: {e['folder']}"
        assert [x["name"] for x in f["files"]] == [p["path"].split("/")[-1] for p in e["files"]]
        for x, p in zip(f["files"], e["files"]):
            root = ET_fromstring(zf.read(p["path"]))
            want = [el.findtext(GPX + "name") or "Untitled" for el in root.iter(GPX + tag[x["kind"]])]
            assert x["items"] == want and len(want) == p["count"]
            assert x["name"].endswith({"Waypoints": "_Waypoints.gpx", "Lines": "_Tracks.gpx",
                                       "Areas": "_Areas.gpx"}[x["kind"]])
    assert sum(len(x["items"]) for f in tree for x in f["files"]) == 177


def ET_fromstring(data: bytes):
    import xml.etree.ElementTree as ET
    return ET.fromstring(data)


def test_no_counts_metadata_or_other_sections():
    text = _text(_export())
    for gone in ("markups", "Import checklist", "My Content", "Renamed", "Holes not kept",
                 "Notes longer", "1.", "Step"):
        assert gone not in text, gone


def test_no_fill_line_even_for_areas_with_a_non_default_fill():
    """Round 5 (D2): the owner wants instructions.txt basic; the screen's caution mark covers fills."""
    p = Path(__file__).parent / "fixtures" / "onx_exports" / "areas-after-edit.kml"
    assert "fill" not in _text(_export(p)).lower()


def test_a_split_file_lists_each_part_with_its_own_items(monkeypatch):
    """A big file splits into numbered parts; each part lists only the items in it."""
    monkeypatch.setattr(bridge, "write_gpx_waypoints_maybe_split",
                        functools.partial(bridge.write_gpx_waypoints_maybe_split, max_bytes=2000))
    zf = _export()
    (e,) = [e for e in bridge._STATE["manifest"] if e["folder"] == "Unorganized"]
    parts = [f for f in e["files"] if f["kind"] == "waypoints"]
    assert len(parts) >= 2
    lines = _text(zf).split("\r\n")
    seen = []
    for f in parts:
        at = lines.index("    " + f["path"].split("/")[-1])
        assert lines[at + 1] == "        Waypoints"
        names = []
        for ln in lines[at + 2:]:
            if not ln.startswith("            "):
                break
            names.append(ln.strip())
        assert names == [n for n, _ in f["items"]] and len(names) == f["count"]
        seen += names
    assert len(seen) == 23 and len(set(seen)) == 23   # every Unorganized waypoint, once


def test_twin_folder_names_are_told_apart_by_their_zip_folder():
    # Two folders named alike, as a file can bring them (a rename can't: it
    # offers a merge instead).
    src = json.loads(BITTERROOTS.read_text(encoding="utf-8"))
    for f in src["features"]:
        if f["properties"].get("class") == "Folder" and f["properties"].get("title") in ("Paddling", "Blodgett"):
            f["properties"]["title"] = "Camp"
    bridge.load_document(json.dumps(src), BITTERROOTS.name)
    zf = zipfile.ZipFile(io.BytesIO(bytes(export_named(bridge))))
    rename = [ln for ln in _text(zf).split("\r\n") if ln.endswith("/    rename to: Camp")]
    assert len(rename) == 2 and rename[0] != rename[1]


# The replace steps for a map that came from onX. onX imports everything as
# new markups, ids or not (docs/ONX_ROUND_TRIP.md), so a round trip is "back
# up, delete the originals, then import"; docs/FAQ.md says so and this file
# didn't (2026-10-25).
ONX_STEPS = [
    "These files came from onX. onX imports them as new markups; it doesn't update the originals.",
    "Keep your onX export as a backup.",
    "In onX, delete the original markups first, then their folders. Deleting a folder doesn't delete its markups.",
    "Then import as below.",
    "",
]


def _export_files(*paths: Path) -> zipfile.ZipFile:
    bridge.load_files(json.dumps(
        [{"name": p.name, "text": p.read_text(encoding="utf-8")} for p in paths]))
    return zipfile.ZipFile(io.BytesIO(bytes(export_named(bridge))))


def test_a_map_from_onx_gets_the_replace_steps_before_the_import_steps():
    onx = FX / "onx_exports"
    lines = _text(_export_files(onx / "three-round-trips.gpx", onx / "three-round-trips.kml")).split("\r\n")
    assert lines[:2] == HEAD[:2]
    assert lines[2:2 + len(ONX_STEPS)] == ONX_STEPS
    assert lines[2 + len(ONX_STEPS):len(HEAD) + len(ONX_STEPS)] == HEAD[2:]
    assert sum("backup" in ln for ln in lines) == 1


def test_a_map_from_one_onx_file_gets_them_too():
    lines = _text(_export_files(FX / "onx_export_with_tracks.gpx")).split("\r\n")
    assert lines[2:2 + len(ONX_STEPS)] == ONX_STEPS


def test_a_caltopo_map_gets_no_replace_steps():
    # CalTopo exports are byte-identical to before: nothing came from onX.
    for ln in _text(_export()).split("\r\n"):
        assert "onX export" not in ln and "originals" not in ln
    text = _text(_export_files(FX / "caltopo_synthetic" / "caltopo_synthetic.json"))
    assert text.split("\r\n")[:len(HEAD)] == HEAD


def test_a_cairn_made_file_gets_no_replace_steps():
    # A Cairn export loaded again is not an onX export: nothing to delete in onX.
    zf = _export()
    name = next(n for n in zf.namelist() if n.endswith("_Waypoints.gpx"))
    bridge.load_files(json.dumps([{"name": "reload.gpx", "text": zf.read(name).decode("utf-8")}]))
    text = _text(zipfile.ZipFile(io.BytesIO(bytes(export_named(bridge)))))
    assert text.split("\r\n")[:len(HEAD)] == HEAD
