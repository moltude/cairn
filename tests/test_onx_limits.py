"""onX's limits on names and the name an export needs (UI-40's L1 and N1,
2026-10-25), at the bridge: export_zip, its manifest, runbook_summary and
instructions.txt. The browser side is tests/web/test_onx_limits_ui.py.

L1: onX keeps the first 255 UTF-8 bytes of an imported name, and its folder rename
dialog stops at 50 characters (measured live, docs/testing/ONX_LIMITS_2026-10-25.md).
Cairn warns, like it does for notes over 512 bytes, and never cuts.
N1: a name is required to export: export_zip refuses an included item whose name is
blank as written. The app names such items "Untitled" first; this is the net.

Maps are generated here; nothing is added under tests/fixtures.
"""
from __future__ import annotations

import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402

from tests.blank_names import blank_uids, name_blanks  # noqa: E402
from tests.hardening_maps import _folder, _line, _poly, _pt  # noqa: E402

GPX = "{http://www.topografix.com/GPX/1/1}"
NAME_CUT = "(over the length limit; onX will cut this name)"
NOTE_CUT = "(over the length limit; onX will cut this note)"
FOLDER_CUT = "(over the length limit; onX will cut this folder name)"


def _feature(kind: str, i: int, folder: str, name: str, note: str = "") -> dict:
    f = _pt(i, folder) if kind == "w" else _line(i, folder) if kind == "l" else _poly(i, folder, holes=0)
    f["properties"].update(title=name, description=note)
    return f


def _load(folders: dict) -> list[dict]:
    """{folder name: [(kind, name, note), ...]} -> the items as the UI gets them."""
    feats, i = [], 0
    for k, (fname, rows) in enumerate(folders.items()):
        feats.append(_folder(f"f{k}", fname))
        for kind, name, note in rows:
            i += 1
            feats.append(_feature(kind, i, f"f{k}", name, note))
    text = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False)
    data = json.loads(bridge.load_document(text, "limits.json"))
    return [it for g in data["groups"] for it in g["items"]]


def _export() -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(bytes(bridge.export_zip())))


def _lines(zf) -> list[str]:
    return zf.read("instructions.txt").decode("utf-8").split("\r\n")


def _marks(zf) -> list[tuple[str, list[str]]]:
    """[(item line, [mark lines under it])] in file order."""
    out = []
    for ln in _lines(zf):
        if ln.startswith(" " * 16):
            out[-1][1].append(ln.strip())
        elif ln.startswith(" " * 12):
            out.append((ln[12:], []))
    return out


def _gpx_names(zf) -> list[str]:
    out = []
    for n in zf.namelist():
        if n.endswith(".gpx"):
            root = ET.fromstring(zf.read(n))
            for tag in ("wpt", "trk", "rte"):
                out += [el.findtext(GPX + "name") or "" for el in root.iter(GPX + tag)]
    return out


# --- the measured limits -----------------------------------------------------------


def test_the_limits_are_the_ones_measured_live():
    assert bridge.ONX_IMPORT_NAME_LIMIT == 255
    assert bridge.ONX_FOLDER_NAME_LIMIT == 50
    assert bridge.ONX_IMPORT_NOTE_LIMIT == 512
    run = ROOT / "docs" / "testing" / "ONX_LIMITS_2026-10-25.md"
    assert run.is_file()
    src = (ROOT / "web" / "bridge.py").read_text(encoding="utf-8")
    assert src.count("docs/testing/ONX_LIMITS_2026-10-25.md") >= 2   # both constants cite the run


# --- N1: a name is required to export ----------------------------------------------


@pytest.mark.parametrize("kind", ["w", "l", "a"], ids=["waypoint", "line", "area"])
def test_export_refuses_an_included_item_with_a_blank_name(kind):
    items = _load({"Trip": [(kind, "", "a note"), ("w", "Named", "")]})
    assert [i["name"] for i in items if i["name"] == ""] == [""]
    with pytest.raises(ValueError) as e:
        bridge.export_zip()
    assert str(e.value) == "An item needs a name."


@pytest.mark.parametrize("name", [
    "", " ", "   ", "\t", "\n\r\n", " ", "　", "  ", "\x85",
    "\x01\x02", "\x00 \x1f", " \x0b ",
], ids=["empty", "space", "spaces", "tab", "newlines", "nbsp", "ideographic-space",
        "em-and-thin-space", "nel", "control-chars-only", "nul-space-unit-sep", "vt-between-spaces"])
def test_a_name_blank_as_written_counts_as_blank(name):
    """Blank after the writers drop the characters XML forbids and trim: what the file
    would hold is an empty <name>."""
    assert bridge._blank_name(name)
    items = _load({"Trip": [("w", "Wp", "")]})
    bridge.apply_edits(json.dumps({items[0]["uid"]: {"name": name}}))
    assert blank_uids(bridge) == [items[0]["uid"]]
    with pytest.raises(ValueError, match=r"^An item needs a name\.$"):
        bridge.export_zip()


@pytest.mark.parametrize("name", ["x", "Untitled", "(no name)", ".", "\u200b", "\ufeffA", "\x01a\x02", "\ufeff"],
                         ids=["one-letter", "untitled", "no-name-text", "dot", "zwsp", "bom-a", "a-in-controls",
                              "bom-only"])
def test_a_name_with_anything_left_as_written_is_a_name(name):
    assert not bridge._blank_name(name)
    items = _load({"Trip": [("w", "Wp", "")]})
    bridge.apply_edits(json.dumps({items[0]["uid"]: {"name": name}}))
    assert not blank_uids(bridge)
    _export()


def test_an_excluded_blank_named_item_does_not_block_and_is_not_written():
    items = _load({"Trip": [("w", "", ""), ("w", "Keep", "")]})
    blank = next(i for i in items if i["name"] == "")
    bridge.apply_edits(json.dumps({blank["uid"]: {"included": False}}))
    assert not blank_uids(bridge)
    assert _gpx_names(_export()) == ["Keep"]


def test_a_blank_named_item_with_no_coordinates_does_not_block():
    """The writers skip it (it is reported as not exported), so no empty <name> can
    reach the file; app.js counts it out the same way."""
    feats = [_folder("f0", "Trip"), _feature("w", 1, "f0", "Keep"),
             {"type": "Feature", "id": "nc", "geometry": {"type": "Point", "coordinates": []},
              "properties": {"title": "", "class": "Marker", "folderId": "f0"}}]
    data = json.loads(bridge.load_document(json.dumps({"type": "FeatureCollection", "features": feats}), "nc.json"))
    items = [i for g in data["groups"] for i in g["items"]]
    assert [(i["name"], bool(i.get("no_coords"))) for i in items] == [("Keep", False), ("", True)]
    assert not blank_uids(bridge)
    zf = _export()
    assert _gpx_names(zf) == ["Keep"]
    assert bridge._STATE["manifest"][0]["dropped"] == 1


def test_a_refused_export_leaves_the_last_export_as_it_was():
    items = _load({"Trip": [("w", "A", ""), ("w", "B", "")]})
    first = bridge.export_zip()
    manifest = json.dumps(bridge._STATE["manifest"])
    bridge.apply_edits(json.dumps({items[0]["uid"]: {"name": "  "}}))
    with pytest.raises(ValueError, match="An item needs a name"):
        bridge.export_zip()
    assert bridge._STATE["zip"] == first
    assert json.dumps(bridge._STATE["manifest"]) == manifest
    assert bridge.export_folder_zip(1)                     # the last export's folders still download


def test_naming_the_blanks_untitled_exports_them_as_untitled():
    items = _load({"Trip": [("w", "", ""), ("l", " ", ""), ("a", "\t", ""), ("w", "Kept", "")]})
    assert len(name_blanks(bridge)) == 3
    zf = _export()
    assert sorted(_gpx_names(zf)) == ["Kept", "Untitled", "Untitled", "Untitled"]
    assert [n for n, _m in _marks(zf)].count("Untitled") == 3
    assert {i["uid"] for i in items} >= bridge._STATE["edited"]


# --- L1: names over 255 UTF-8 bytes --------------------------------------------------


NAMES = {
    "ascii-255": ("x" * 255, False),
    "ascii-256": ("x" * 256, True),
    "accented-127-and-x": ("é" * 127 + "x", False),       # 255 bytes
    "accented-128": ("é" * 128, True),                     # 256 bytes, 128 characters
    "emoji-ending-at-255": ("x" * 251 + "\U0001F525", False),   # 255 bytes
    "emoji-straddling-255": ("x" * 252 + "\U0001F525", True),   # 256 bytes: onX drops the emoji
    "cjk-86": ("山" * 86, True),                            # 258 bytes, 86 characters
}


@pytest.mark.parametrize("label", list(NAMES))
def test_a_name_over_255_utf8_bytes_is_listed_and_marked_under_its_item(label):
    name, over = NAMES[label]
    _load({"Trip": [("w", "Before", ""), ("w", name, ""), ("w", "After", "")]})
    zf = _export()
    assert name in _gpx_names(zf)                              # exported whole: never cut
    (entry,) = bridge._STATE["manifest"]
    nbytes = len(name.encode("utf-8"))
    assert entry["long_names"] == ([[name, nbytes]] if over else [])
    marks = dict(_marks(zf))
    assert marks == {"Before": [], name: [NAME_CUT] if over else [], "After": []}
    summary = bridge.runbook_summary(bridge._STATE["manifest"])
    assert (summary["long_names"], summary["name_limit"]) == (int(over), 255)


@pytest.mark.parametrize("kind", ["w", "l", "a"], ids=["waypoint", "line", "area"])
def test_every_kind_of_item_gets_the_long_name_line(kind):
    _load({"Trip": [(kind, "y" * 300, ""), (kind, "Short", "")]})
    zf = _export()
    assert dict(_marks(zf)) == {"y" * 300: [NAME_CUT], "Short": []}
    assert [n for e in bridge._STATE["manifest"] for n, _b in e["long_names"]] == ["y" * 300]


def test_a_long_name_and_a_long_note_on_one_item_are_marked_name_first():
    _load({"Trip": [("w", "z" * 256, "n" * 513), ("w", "Note only", "n" * 600), ("w", "z" * 300, "")]})
    zf = _export()
    assert dict(_marks(zf)) == {"z" * 256: [NAME_CUT, NOTE_CUT], "Note only": [NOTE_CUT], "z" * 300: [NAME_CUT]}
    summary = bridge.runbook_summary(bridge._STATE["manifest"])
    assert (summary["long_names"], summary["long_notes"]) == (2, 2)


def test_twin_long_names_are_each_marked_by_position():
    long = "Camp " + "q" * 260
    _load({"Trip": [("w", long, ""), ("w", "Camp", ""), ("w", long, "")]})
    zf = _export()
    assert _marks(zf) == [("Camp", []), (long, [NAME_CUT]), (long, [NAME_CUT])]
    assert len(bridge._STATE["manifest"][0]["long_names"]) == 2


# --- L1: folder names over 50 characters ---------------------------------------------


FOLDERS = {
    "ascii-50": ("f" * 50, False),
    "ascii-51": ("f" * 51, True),
    "accented-50": ("é" * 50, False),                     # 100 bytes, 50 characters
    "accented-51": ("é" * 51, True),
    "emoji-25": ("\U0001F525" * 25, False),                     # 50 UTF-16 units (25 code points)
    "x49-and-emoji": ("x" * 49 + "\U0001F525", True),           # 51 UTF-16 units, 50 code points
}


@pytest.mark.parametrize("label", list(FOLDERS))
def test_a_folder_name_over_50_characters_is_marked_under_its_rename_line(label):
    """Characters as a browser's maxlength counts them (UTF-16 units), which is what
    stops typing in onX's rename dialog: an emoji is two."""
    folder, over = FOLDERS[label]
    _load({folder: [("w", "Wp", "")], "Short": [("w", "Other", "")]})
    zf = _export()
    lines = _lines(zf)
    by_folder = {e["folder"]: e for e in bridge._STATE["manifest"]}
    assert by_folder[folder]["long_folder"] is over and by_folder["Short"]["long_folder"] is False
    at = lines.index(f"{by_folder[folder]['dir']}/    rename to: {folder}")   # the line holds the name alone
    assert (lines[at + 1] == "    " + FOLDER_CUT) is over
    assert sum(ln.strip() == FOLDER_CUT for ln in lines) == int(over)
    summary = bridge.runbook_summary(bridge._STATE["manifest"])
    assert (summary["long_folders"], summary["folder_name_limit"]) == (int(over), 50)


def test_a_long_folder_with_every_item_excluded_is_not_in_the_export_or_marked():
    items = _load({"g" * 60: [("w", "Gone", "")], "Short": [("w", "Kept", "")]})
    gone = next(i for i in items if i["name"] == "Gone")
    bridge.apply_edits(json.dumps({gone["uid"]: {"included": False}}))
    zf = _export()
    assert FOLDER_CUT not in "\r\n".join(_lines(zf))
    assert bridge.runbook_summary(bridge._STATE["manifest"])["long_folders"] == 0


def test_names_and_folders_within_the_limits_add_no_line():
    """Bitterroots: names up to 47 bytes, folders up to 22 characters."""
    path = ROOT / "tests" / "fixtures" / "bitterroots" / "Bitterroots__Complete_.json"
    data = json.loads(bridge.load_document(path.read_text(encoding="utf-8"), path.name))
    assert max(len(i["name"].encode("utf-8")) for g in data["groups"] for i in g["items"]) <= 47
    assert max(len(g["name"]) for g in data["groups"]) <= 22
    name_blanks(bridge)
    zf = _export()
    text = zf.read("instructions.txt").decode("utf-8")
    assert NAME_CUT not in text and FOLDER_CUT not in text
    summary = bridge.runbook_summary(bridge._STATE["manifest"])
    assert (summary["long_names"], summary["long_folders"]) == (0, 0)
