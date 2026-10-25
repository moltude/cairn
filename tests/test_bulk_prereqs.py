"""Layer W for bulk rename and note change: the bridge and the writers, no browser.

docs/plans/BULK_RENAME.md 3.7 ("Remains (C)") and the W ids of section 5 that stop at
the file Cairn writes (the ones that read the file back with the onX reader are in
tests/test_bulk_round_trip.py). The dialog's Save stores the core's `after` through
edit(), and doExport sends EDITS to bridge.apply_edits, which copies name and desc
verbatim; so a bulk change reaches the bridge exactly as apply_edits({uid: {name|desc}}).
The `after` values used here are the core's, derived by hand from 3.1 (they live in
tests/bulk_rename_vectors.py, where tests/web/test_rename_core.py checks them against the
real core).

Maps are generated at test time (bulk_rename_vectors.item_map); nothing is added under
tests/fixtures. bridge writes to /tmp, as the other bridge tests do.
"""
from __future__ import annotations

import functools
import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402

from cairn.core.writers import DEFAULT_MAX_GPX_BYTES  # noqa: E402
from tests.bulk_rename_vectors import CAMPSITES, TWINS, item_map  # noqa: E402
from tests.hardening_maps import _folder, _poly  # noqa: E402
from tests.naughty_strings import NAUGHTY  # noqa: E402

FX = ROOT / "tests" / "fixtures"
BITTERROOTS = FX / "bitterroots" / "Bitterroots__Complete_.json"
ONX_GPX = FX / "onx_exports" / "three-round-trips.gpx"
GPX = "{http://www.topografix.com/GPX/1/1}"
TAG = {"waypoints": "wpt", "tracks": "trk", "shapes": "rte"}
CUT = "(over the length limit; onX will cut this note)"
HOLE = "(its hole is not kept: an onX area has one outline)"


# --- helpers --------------------------------------------------------------------------


def load(rows, folder="Bulk") -> list[dict]:
    """Load a generated map; its items, as the UI gets them."""
    data = json.loads(bridge.load_document(item_map(rows, folder), "bulk.json"))
    return [i for g in data["groups"] for i in g["items"]]


def load_file(path: Path) -> list[dict]:
    data = json.loads(bridge.load_document(path.read_text(encoding="utf-8"), path.name))
    return [i for g in data["groups"] for i in g["items"]]


def stored() -> list[dict]:
    """The bridge's items now (what apply_edits stored)."""
    return [i for g in bridge._STATE["groups"] for i in g["items"]]


def uid(items, name):
    (u,) = [i["uid"] for i in items if i["name"] == name]
    return u


def edit(edits: dict) -> None:
    bridge.apply_edits(json.dumps(edits))


def export() -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(bytes(bridge.export_zip())))


def gpx_items(zf) -> list[tuple[str, str, str, str]]:
    """(member, kind, name, desc) for every item of every GPX member, as ElementTree
    reads them (an empty or missing <name>/<desc> reads as ""). Parsing each member is
    itself the "every GPX parses" check."""
    out = []
    for n in zf.namelist():
        if not n.endswith(".gpx"):
            continue
        root = ET.fromstring(zf.read(n))
        for kind, tag in TAG.items():
            for el in root.iter(GPX + tag):
                out.append((n, kind, el.findtext(GPX + "name") or "", el.findtext(GPX + "desc") or ""))
    return out


def written(zf) -> list[tuple[str, list]]:
    """bridge._written_items for every file the manifest lists (it must not raise)."""
    out = []
    for e in bridge._STATE["manifest"]:
        for f in e["files"]:
            out.append((f["path"], bridge._written_items(zf.read(f["path"]), f["kind"])))
    return out


def instruction_items(zf) -> list[tuple[str, list[str]]]:
    """[(item name as printed, [the mark lines under it])] in file order."""
    lines = zf.read("instructions.txt").decode("utf-8").split("\r\n")
    out = []
    for ln in lines:
        if ln.startswith(" " * 16):
            out[-1][1].append(ln.strip())
        elif ln.startswith(" " * 12):
            out.append((ln[12:], []))
    return out


def names(zf, kind=None) -> Counter:
    return Counter(n for _m, k, n, _d in gpx_items(zf) if kind in (None, k))


def descs(zf, kind=None) -> Counter:
    return Counter(d for _m, k, _n, d in gpx_items(zf) if kind in (None, k))


ONE_OF_EACH = [("w", "Wp", "note w"), ("l", "Line", "note l"), ("a", "Area", "note a")]


# =====================================================================================
# 3.7 prerequisites: the remaining bridge-level checks
# =====================================================================================


def test_apply_edits_with_control_characters_exports_clean_gpx():
    """3.7(a): a name "\\x01Camp\\x00" and a note "a\\x02b" stored by apply_edits."""
    items = load([("w", "Wp", "")])
    edit({items[0]["uid"]: {"name": "\x01Camp\x00", "desc": "a\x02b"}})
    zf = export()
    assert [(n, d) for _m, _k, n, d in gpx_items(zf)] == [("Camp", "ab")]
    assert written(zf) == [("01_Bulk/Bulk_Waypoints.gpx", [["Camp", 2]])]


def test_an_empty_name_exports_an_empty_name_element_and_instructions_say_untitled():
    """3.7(f): names are optional (decision 17). The <name> element is written and
    empty; instructions.txt prints "Untitled" for it (bridge._plain)."""
    items = load(ONE_OF_EACH)
    edit({i["uid"]: {"name": ""} for i in items})
    zf = export()
    got = gpx_items(zf)
    assert len(got) == 3 and all(n == "" for _m, _k, n, _d in got)
    for m in {m for m, *_ in got}:
        root = ET.fromstring(zf.read(m))
        for el in root.iter():
            if el.tag in {GPX + t for t in TAG.values()}:
                name = el.find(GPX + "name")
                assert name is not None and (name.text or "") == ""
    assert sorted(n for _p, its in written(zf) for n, _b in its) == ["", "", ""]
    assert [n for n, _marks in instruction_items(zf)] == ["Untitled"] * 3


def _areas_map(spec):
    """Areas named from spec [(name, note, holes)]: one folder, unique names."""
    feats = [_folder("f0", "Areas")]
    for i, (name, note, holes) in enumerate(spec, 1):
        f = _poly(i, "f0", holes=holes)
        f["properties"].update(title=name, description=note)
        feats.append(f)
    return json.dumps({"type": "FeatureCollection", "features": feats})


def test_split_parts_keep_each_items_note_bytes_and_hole_mark(monkeypatch):
    """3.7(b), optional: when the areas file splits into parts, every item's cut line and
    hole line in instructions.txt still sits under that very item (marks go by position,
    across parts). Split forced small, as tests/test_export_instructions.py does."""
    spec = [(f"Area {k:02d}{' long' if k % 3 == 0 else ''}{' hole' if k % 4 == 0 else ''}",
             ("ü" * 300 if k % 3 == 0 else "short"), 1 if k % 4 == 0 else 0) for k in range(1, 25)]
    monkeypatch.setattr(bridge, "write_gpx_areas_maybe_split",
                        functools.partial(bridge.write_gpx_areas_maybe_split, max_bytes=2500))
    bridge.load_document(_areas_map(spec), "areas.json")
    zf = export()
    parts = [f for e in bridge._STATE["manifest"] for f in e["files"] if f["kind"] == "shapes"]
    assert len(parts) >= 2
    seen = instruction_items(zf)
    assert sorted(n for n, _m in seen) == sorted(n for n, _note, _h in spec)
    for name, marks in seen:
        assert (CUT in marks) == ("long" in name), name
        assert (HOLE in marks) == ("hole" in name), name
    for _p, its in written(zf):
        for name, nbytes in its:
            assert nbytes == (600 if "long" in name else 5), name


# =====================================================================================
# 5.1 Length and limits
# =====================================================================================


def test_a_four_byte_emoji_straddling_512_is_reported_not_split():
    note = "a" * 510 + "🔥"
    items = load([("w", "Wp", "")])
    edit({items[0]["uid"]: {"desc": note}})
    zf = export()
    ((_m, _k, _n, desc),) = gpx_items(zf)
    assert desc == note
    assert "🔥".encode("utf-8") in zf.read("01_Bulk/Bulk_Waypoints.gpx")
    assert written(zf)[0][1] == [["Wp", 514]]
    assert instruction_items(zf) == [("Wp", [CUT])]


def test_crlf_and_lone_cr_in_a_note_become_lf_before_measure():
    """The core stores "a\\nb\\nc" * 100 (500 bytes); the single note editor may store
    the typed "a\\r\\nb\\rc" * 100. Both are written and counted as 500 bytes, no cut line:
    the dialog's measure and instructions.txt's agree."""
    items = load([("w", "Bulk", ""), ("w", "Typed", "")])
    edit({uid(items, "Bulk"): {"desc": "a\nb\nc" * 100}, uid(items, "Typed"): {"desc": "a\r\nb\rc" * 100}})
    zf = export()
    assert descs(zf) == Counter({"a\nb\nc" * 100: 2})
    assert sorted(written(zf)[0][1]) == [["Bulk", 500], ["Typed", 500]]
    assert all(marks == [] for _n, marks in instruction_items(zf))


def test_note_bytes_in_the_dialog_match_instructions_txt():
    at = "a" * 505 + "<b></b>"
    items = load([("w", "At", ""), ("w", "Over", "")])
    edit({uid(items, "At"): {"desc": at}, uid(items, "Over"): {"desc": at + "a"}})
    zf = export()
    assert sorted(written(zf)[0][1]) == [["At", 512], ["Over", 513]]
    assert dict(instruction_items(zf)) == {"At": [], "Over": [CUT]}
    assert at in descs(zf)


def test_a_3000_character_name_is_stored_whole_and_exported_whole():
    name = "x" * 3000 + "Camp"
    items = load(ONE_OF_EACH)
    edit({i["uid"]: {"name": name} for i in items})
    zf = export()
    assert all(i["name"] == name for i in stored())
    assert names(zf) == Counter({name: 3})
    assert [n for n, _m in instruction_items(zf)] == [name] * 3


def test_set_note_on_1500_rows_with_512_bytes_splits_the_gpx(monkeypatch):
    """1,500 waypoints with a 512-byte note each make about 1.07 MB, under onX's cap, so
    at the real DEFAULT_MAX_GPX_BYTES the file does not split (plan 5.1 expected a split;
    checked first). The split is then forced small: every part stays under it, and
    nothing is lost or measured twice."""
    note = ("Replace the note " * 40)[:512]
    assert len(note.encode("utf-8")) == 512
    items = load([("w", f"Wp {k:04d}", "") for k in range(1500)])
    edit({i["uid"]: {"desc": note} for i in items})
    zf = export()
    (one,) = [n for n in zf.namelist() if n.endswith(".gpx")]
    assert len(zf.read(one)) < DEFAULT_MAX_GPX_BYTES

    limit = 200_000
    monkeypatch.setattr(bridge, "write_gpx_waypoints_maybe_split",
                        functools.partial(bridge.write_gpx_waypoints_maybe_split, max_bytes=limit))
    zf = export()
    parts = [n for n in zf.namelist() if n.endswith(".gpx")]
    assert len(parts) >= 2
    assert all(len(zf.read(p)) <= limit for p in parts)
    per_part = written(zf)
    assert sum(len(its) for _p, its in per_part) == 1500
    assert all(nbytes == 512 for _p, its in per_part for _n, nbytes in its)
    assert names(zf) == Counter(f"Wp {k:04d}" for k in range(1500))
    assert descs(zf) == Counter({note: 1500})
    assert not any(marks for _n, marks in instruction_items(zf))


# =====================================================================================
# 5.2 Non-English and Unicode
# =====================================================================================


def test_bidi_override_is_kept_and_never_breaks_xml():
    items = load([("w", "Wp", "")])
    edit({items[0]["uid"]: {"name": "xa\u202eb", "desc": "a\u202eb"}})
    zf = export()
    assert [(n, d) for _m, _k, n, d in gpx_items(zf)] == [("xa\u202eb", "a\u202eb")]


def test_a_paired_emoji_survives_the_surrogate_strip():
    items = load(ONE_OF_EACH)
    edit({i["uid"]: {"name": "xa🔥b", "desc": "a🔥b"} for i in items})
    zf = export()
    assert names(zf) == Counter({"xa🔥b": 3}) and descs(zf) == Counter({"a🔥b": 3})


def test_zero_width_space_and_bom_are_kept_in_names():
    name = "xCa\ufeffmp\u200b X"
    items = load([("w", "Wp", "")])
    edit({items[0]["uid"]: {"name": name}})
    zf = export()
    assert names(zf) == Counter({name: 1})


def test_a_name_typed_as_untitled_or_no_name_is_an_ordinary_name():
    """Typed "Untitled" and "(no name)" are stored and written as typed; a truly blank
    name is written empty. instructions.txt prints the typed "Untitled" and the blank
    one alike ("Untitled", bridge._plain): documented, not a bug."""
    items = load([("w", "A", ""), ("w", "B", ""), ("w", "C", "")])
    edit({uid(items, "A"): {"name": "Untitled"}, uid(items, "B"): {"name": "(no name)"},
          uid(items, "C"): {"name": ""}})
    zf = export()
    assert names(zf) == Counter(["Untitled", "(no name)", ""])
    assert sorted(n for n, _m in instruction_items(zf)) == ["(no name)", "Untitled", "Untitled"]


# =====================================================================================
# 5.3 XML-hostile
# =====================================================================================


def test_a_dirty_stored_name_is_left_alone_by_an_empty_spec():
    """An empty spec saves nothing, so the loaded "\\x01Camp" reaches export untouched
    and the writer drops the control character there."""
    items = load([("w", "\x01Camp", "")])
    assert items[0]["name"] == "\x01Camp"
    zf = export()
    assert names(zf) == Counter({"Camp": 1})


@pytest.mark.parametrize("kind", ["w", "l", "a"])
def test_the_writer_strips_what_the_core_missed(kind):
    """apply_edits directly, bypassing the core: the writer is the net (plan 3.1)."""
    items = load([(kind, "Item", "")])
    edit({items[0]["uid"]: {"name": "\x02Camp", "desc": "a\x02b"}})
    zf = export()
    assert [(n, d) for _m, _k, n, d in gpx_items(zf)] == [("Camp", "ab")]
    written(zf)


@pytest.mark.parametrize("text", [t for _l, t in NAUGHTY], ids=[label for label, _t in NAUGHTY])
def test_every_naughty_string_exports_and_reparses(text):
    """Each naughty string as the name and the note of a waypoint, a line and an area."""
    items = load(ONE_OF_EACH)
    edit({i["uid"]: {"name": text, "desc": text} for i in items})
    zf = export()
    got = gpx_items(zf)
    assert len(got) == 3
    assert sum(len(its) for _p, its in written(zf)) == 3
    zf.read("instructions.txt").decode("utf-8")


def _set_every_note(note: str) -> int:
    items = stored()
    edit({i["uid"]: {"desc": note} for i in items})
    return len(items)


HTML_NOTE = "see <b>north</b> of <Lake>"


def test_a_bulk_note_with_html_looking_text_on_a_caltopo_map_exports_verbatim():
    """Bitterroots is CalTopo: strip_html ran at load, export writes plain notes
    (bridge.export_zip sets PLAIN_NOTES_KEY), so <b> survives as text."""
    load_file(BITTERROOTS)
    n = _set_every_note(HTML_NOTE)
    zf = export()
    assert descs(zf) == Counter({HTML_NOTE: n})
    raw = b"".join(zf.read(m) for m in zf.namelist() if m.endswith(".gpx"))
    assert raw.count(b"<desc>see &lt;b&gt;north&lt;/b&gt; of &lt;Lake&gt;</desc>") == n


def test_a_bulk_note_on_an_onx_map_exports_verbatim():
    load_file(ONX_GPX)
    n = _set_every_note(HTML_NOTE)
    assert n > 0
    zf = export()
    assert descs(zf) == Counter({HTML_NOTE: n})


# =====================================================================================
# 5.4 Replacement-pattern and find traps
# =====================================================================================


def test_replace_with_empty_can_empty_a_name_and_saves_it_blank():
    """Find "Camp" replace with "" on "Camp": the core's after is "" (stored as "", never
    "Untitled"); every kind writes an empty <name> and every GPX parses."""
    items = load([("w", "Camp", ""), ("l", "Camp line", ""), ("a", "Camp area", "")])
    edit({uid(items, "Camp"): {"name": ""}, uid(items, "Camp line"): {"name": "line"},
          uid(items, "Camp area"): {"name": "area"}})
    zf = export()
    assert names(zf, "waypoints") == Counter({"": 1})
    assert names(zf) == Counter(["", "line", "area"])
    assert sorted(n for _p, its in written(zf) for n, _b in its) == ["", "area", "line"]


# =====================================================================================
# 5.5 Incompatible and conflicting bulk operations
# =====================================================================================


def test_campsite_normalisation_makes_three_identical_names_and_exports_three_items():
    items = load([("w", n, "") for n in CAMPSITES])
    edit({i["uid"]: {"name": "Campsite"} for i in items})
    zf = export()
    assert names(zf) == Counter({"Campsite": 3})
    raw = zf.read("01_Bulk/Bulk_Waypoints.gpx")
    assert raw.count(b"<name>Campsite</name>") == 3
    assert written(zf)[0][1] == [["Campsite", 0]] * 3


def test_renaming_existing_twins_together_keeps_them_twins():
    """Add before "Base " on the twins Camp, camp, CAMP and " Camp ": the core's results
    (test_rename_core checks them) are stored as they are, and all four export. The rows
    load under stand-in names: the GeoJSON load strips " Camp " to a second "Camp"."""
    items = load([("w", f"T{k}", "") for k in range(4)])
    after = ["Base " + TWINS[0], "Base " + TWINS[1], "Base " + TWINS[2], "Base  Camp"]
    edit({items[k]["uid"]: {"name": after[k]} for k in range(4)})
    zf = export()
    assert names(zf) == Counter(after)
    assert len(written(zf)[0][1]) == 4


def test_a_rename_that_collides_with_an_unselected_name_is_an_ordinary_change():
    items = load([("w", "Camp", ""), ("w", "Camp A", "")])
    edit({uid(items, "Camp A"): {"name": "Camp"}})
    zf = export()
    assert names(zf) == Counter({"Camp": 2})


def test_mixed_waypoints_lines_and_areas_rename_alike():
    items = load(ONE_OF_EACH)
    edit({i["uid"]: {"name": "x" + i["name"]} for i in items})
    zf = export()
    assert {(k, n) for _m, k, n, _d in gpx_items(zf)} == {
        ("waypoints", "xWp"), ("tracks", "xLine"), ("shapes", "xArea")}


def test_exclude_then_rename_then_include_exports_the_new_name():
    items = load([("w", "Keep", ""), ("w", "Toggle", "")])
    t = uid(items, "Toggle")
    edit({t: {"included": False}})
    edit({t: {"name": "Renamed"}})
    zf = export()
    assert names(zf) == Counter({"Keep": 1})
    edit({t: {"included": True}})
    zf = export()
    assert names(zf) == Counter({"Keep": 1, "Renamed": 1})


def test_rename_then_change_note_then_export_agree():
    items = load(ONE_OF_EACH)
    edit({i["uid"]: {"name": "Base " + i["name"]} for i in items})
    edit({i["uid"]: {"desc": "Top\n" + i["desc"]} for i in items})
    zf = export()
    want = {(i["kind"], "Base " + i["name"], "Top\n" + i["desc"]) for i in items}
    assert {(k, n, d) for _m, k, n, d in gpx_items(zf)} == want
    assert {(i["kind"], i["name"], i["desc"]) for i in stored()} == want


def _members(zf) -> dict:
    return {n: zf.read(n) for n in zf.namelist()}


def test_rename_then_rename_back_still_counts_as_edits_and_exports_identically():
    """Prefix "⟦" then find "⟦" replace "": every name is back to what it was, the
    bridge holds two rounds of edits, and every member of the zip is byte-identical to
    the unedited export (the zip's own timestamps aside)."""
    items = load_file(BITTERROOTS)
    baseline = _members(export())
    edit({i["uid"]: {"name": "⟦" + i["name"]} for i in items})
    assert all(i["name"].startswith("⟦") for i in stored())
    edit({i["uid"]: {"name": i["name"]} for i in items})
    assert bridge._STATE["edited"] >= {i["uid"] for i in items}
    assert _members(export()) == baseline


# =====================================================================================
# 5.7 Validation and review
# =====================================================================================


def test_instructions_txt_lists_the_new_names_and_flags_the_right_long_note():
    """Twins plus one long note: instructions.txt lists every new name, and the one cut
    line sits under the item whose written note is over 512 bytes, by position (names
    repeat, so a name can't say which)."""
    items = load([("w", f"T{k}", "") for k in range(4)])
    edit({i["uid"]: {"name": "Camp"} for i in items})
    edit({items[2]["uid"]: {"desc": "ü" * 300}})
    zf = export()
    listed = instruction_items(zf)
    assert [n for n, _m in listed] == ["Camp"] * 4
    ((_path, its),) = written(zf)
    assert [marks == [CUT] for _n, marks in listed] == [nbytes > 512 for _n, nbytes in its]
    assert sum(marks == [CUT] for _n, marks in listed) == 1
