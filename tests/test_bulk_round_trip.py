"""Layer W, round trip: what a bulk change stores, what the writer writes, and what the
onX reader reads back (docs/plans/BULK_RENAME.md 6.6).

The `after` values come from tests/bulk_rename_vectors.py: hand-derived from the core's
rules (3.1) and checked against the real core by tests/web/test_rename_core.py. They are
stored with bridge.apply_edits (what Save + export do), exported, and read back two ways:
ElementTree on every GPX member (the headline invariant: the <name>/<desc> text equals the
core's after exactly), and cairn/io/onx_gpx.read_onx_gpx (what a re-import sees). The
reader cleans on its own: normalize_name strips the ends and decodes entities a second
time ("&amp;" typed as text comes back "&"), and a note whose first line is an onX
"key=value" line is read as onX's desc block. Those are the reader's behaviour, compared
after its own cleaning and pinned where they differ.

The GPX carries no uid (ENG-07), so items are compared as multisets per folder and kind;
the per-uid chain is layer E's job.
"""
from __future__ import annotations

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

from cairn.core.normalization import normalize_name  # noqa: E402
from cairn.io.onx_gpx import parse_onx_desc_kv, read_onx_gpx  # noqa: E402
from tests.bulk_rename_vectors import (  # noqa: E402
    ROUND_TRIP_NAMES, ROUND_TRIP_NOTES, item_map, py_clean_note,
)
from tests.blank_names import blank_uids, name_blanks  # noqa: E402
from tests.hardening_maps import _folder, _line, _poly, _pt  # noqa: E402
from tests.naughty_strings import NAUGHTY  # noqa: E402

GPX = "{http://www.topografix.com/GPX/1/1}"
TAG = {"waypoints": "wpt", "tracks": "trk", "shapes": "rte"}
READER_KIND = {"Waypoint": "waypoints", "Track": "tracks", "Shape": "shapes"}
KINDS = ["w", "l", "a"]


def load_files(text: str, name: str = "naughty.json") -> list[dict]:
    data = json.loads(bridge.load_files(json.dumps([{"name": name, "text": text}])))
    return [i for g in data["groups"] for i in g["items"]]


def stored() -> list[dict]:
    return [i for g in bridge._STATE["groups"] for i in g["items"]]


def stored_by_folder() -> list[tuple[str, dict]]:
    return [(g["name"], i) for g in bridge._STATE["groups"] for i in g["items"]]


def export() -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(bytes(bridge.export_zip())))


def gpx_items(zf) -> list[tuple[str, str, str, str]]:
    """(folder dir, kind, name, desc) per item element, as ElementTree reads it."""
    out = []
    for n in zf.namelist():
        if n.endswith(".gpx"):
            root = ET.fromstring(zf.read(n))
            for kind, tag in TAG.items():
                for el in root.iter(GPX + tag):
                    out.append((n.split("/")[0], kind, el.findtext(GPX + "name") or "",
                                el.findtext(GPX + "desc") or ""))
    return out


def reader_items(zf, tmp_path: Path) -> list[tuple[str, str, str, str]]:
    """(folder dir, kind, name, notes) per item, as the onX GPX reader reads each file."""
    out = []
    for n in zf.namelist():
        if n.endswith(".gpx"):
            p = tmp_path / n.replace("/", "__")
            p.write_bytes(zf.read(n))
            for it in read_onx_gpx(p).items:
                out.append((n.split("/")[0], READER_KIND[type(it).__name__], it.name, it.notes))
    return out


def reader_name(name: str) -> str:
    """What the onX reader makes of a <name> text."""
    return normalize_name(name)


def reader_note(desc: str) -> str:
    """What the onX reader makes of a <desc> text (onx_gpx: parse_onx_desc_kv, then
    normalize_name on the notes)."""
    _kv, notes = parse_onx_desc_kv(desc)
    return normalize_name(notes) if notes else ""


def instruction_names(zf) -> Counter:
    lines = zf.read("instructions.txt").decode("utf-8").split("\r\n")
    return Counter(ln[12:] for ln in lines if ln.startswith(" " * 12) and not ln.startswith(" " * 16))


# =====================================================================================
# 6.6 The round trip
# =====================================================================================


def _naughty_map(names_vectors, notes_vectors) -> str:
    """One item per vector, kinds in turn. A name vector's item loads with its `before`
    as the name and a tag as the note; a note vector's item with a tag as the name and
    its `before` as the note. The tags find the items again after the load."""
    rows = []
    for k, (_label, before, _sp, _after) in enumerate(names_vectors):
        rows.append((KINDS[k % 3], before, f"name-vector-{k}"))
    for k, (_label, before, _sp, _after) in enumerate(notes_vectors):
        rows.append((KINDS[k % 3], f"note-vector-{k}", before))
    return item_map(rows, folder="Naughty")


def _apply_round_trip(names_vectors, notes_vectors) -> dict:
    """Load the naughty map, store every vector's after; {uid: (field, after)}."""
    items = load_files(_naughty_map(names_vectors, notes_vectors))
    by_tag = {}
    for i in items:
        by_tag[i["desc"]] = i
        by_tag[i["name"]] = i
    plan = {}
    for k, (_l, _b, _s, after) in enumerate(names_vectors):
        plan[by_tag[f"name-vector-{k}"]["uid"]] = ("name", after)
    for k, (_l, _b, _s, after) in enumerate(notes_vectors):
        plan[by_tag[f"note-vector-{k}"]["uid"]] = ("desc", after)
    bridge.apply_edits(json.dumps({u: {f: a} for u, (f, a) in plan.items()}))
    return plan


def test_round_trip_writer_reader_keeps_every_renamed_name(tmp_path):
    plan = _apply_round_trip(ROUND_TRIP_NAMES, ROUND_TRIP_NOTES)
    items = {i["uid"]: i for i in stored()}
    # Save stores the core's after verbatim.
    for u, (field, after) in plan.items():
        assert items[u][field] == after
    # A blank after is stored, but the export needs a name (N1, 2026-10-25): named
    # "Untitled" first, as the app does. DEVIATION: they were exported blank.
    blanks = [u for u, (field, after) in plan.items() if field == "name" and bridge._blank_name(after)]
    assert blanks and sorted(name_blanks(bridge)) == sorted(blanks)
    zf = export()
    got = gpx_items(zf)
    want = [("01_Naughty", i["kind"], i["name"], i["desc"]) for i in stored()]
    # The file holds exactly what was stored: names and notes, per kind, as multisets.
    assert Counter(got) == Counter(want)
    assert len(got) == len(plan)
    # The onX reader: equal after its own cleaning, item for item.
    back = reader_items(zf, tmp_path)
    assert Counter(back) == Counter((d, k, reader_name(n), reader_note(ds)) for d, k, n, ds in want)
    # instructions.txt lists every item once, a blank name as "Untitled".
    assert instruction_names(zf) == Counter(bridge._plain(i["name"]) for i in stored())


def test_the_reader_side_differences_are_pinned(tmp_path):
    """Where the onX reader does not hand back the core's after: a blank after never
    reaches the file (N1: named "Untitled" before export, so no <name> is blank);
    entity-looking text is decoded once more; a note that opens with "name=" is read
    as onX's own desc block.
    DEVIATION (N1, 2026-10-25): a blank <name> was written and read back as ""."""
    names = {label: after for label, _b, _s, after in ROUND_TRIP_NAMES}
    notes = {label: after for label, _b, _s, after in ROUND_TRIP_NOTES}
    _apply_round_trip(ROUND_TRIP_NAMES, ROUND_TRIP_NOTES)
    with pytest.raises(ValueError, match="An item needs a name"):
        bridge.export_zip()
    named = name_blanks(bridge)
    back = reader_items(export(), tmp_path)
    back_names = Counter(n for _d, _k, n, _s in back)
    back_notes = Counter(s for _d, _k, _n, s in back)
    blanks = [label for label, a in names.items() if a == ""]
    typed = sum(a == "Untitled" for a in names.values())
    assert len(blanks) == 3 and len(named) == len(blanks)
    assert back_names[""] == 0 and back_names["Untitled"] == len(blanks) + typed
    assert names["prefix_keeps_entity_text"] == "x&amp; &lt;b&gt;"
    assert back_names["x& <b>"] == 1 and back_names["x&amp; &lt;b&gt;"] == 0
    assert notes["note_prefix_onx_desc_block"] == "name=evil\nnotes=y\nx"
    assert back_notes["y\nx"] == 1
    # Everything else comes back exactly.
    differ = {"prefix_keeps_entity_text"} | {l for l, a in names.items() if a == ""}
    for label, after in names.items():
        if label not in differ:
            assert back_names[after] >= 1, label
    for label, after in notes.items():
        if label != "note_prefix_onx_desc_block":
            assert back_notes[after] >= 1, label


@pytest.mark.parametrize("text", [t for _l, t in NAUGHTY], ids=[label for label, _t in NAUGHTY])
def test_a_naughty_note_round_trips_through_the_onx_reader(text, tmp_path):
    """Replace the note with each naughty string: what the core stores (its cleanNote,
    mirrored in Python and checked against the JS in test_rename_core) is what the file
    holds, exactly, and the reader reads it back without a crash, equal after its own
    cleaning."""
    items = load_files(item_map([("w", "Wp", ""), ("l", "Line", ""), ("a", "Area", "")]))
    after = py_clean_note(text)
    bridge.apply_edits(json.dumps({i["uid"]: {"desc": after} for i in items}))
    zf = export()
    assert Counter(d for _f, _k, _n, d in gpx_items(zf)) == Counter({after: 3})
    back = reader_items(zf, tmp_path)
    assert Counter(s for _f, _k, _n, s in back) == Counter({reader_note(after): 3})


# =====================================================================================
# The round-trip W ids of section 5
# =====================================================================================


def _one(kind: str, name: str, note: str = ""):
    items = load_files(item_map([(kind, "Item", "")]))
    bridge.apply_edits(json.dumps({items[0]["uid"]: {"name": name, "desc": note}}))


def test_rtl_names_keep_their_characters_and_order(tmp_path):
    name = "مجلد عربي 2"
    for kind in KINDS:
        _one(kind, name)
        zf = export()
        ((_d, _k, n, _s),) = gpx_items(zf)
        assert n == name and [ord(c) for c in n] == [ord(c) for c in name]
        ((_d, _k, rn, _s),) = reader_items(zf, tmp_path)
        assert rn == name


def test_c1_controls_are_kept_in_names_and_notes(tmp_path):
    _one("w", "xa\x85b", "a\x85b\n!")
    zf = export()
    assert [(n, d) for _f, _k, n, d in gpx_items(zf)] == [("xa\x85b", "a\x85b\n!")]
    assert [(n, s) for _f, _k, n, s in reader_items(zf, tmp_path)] == [("xa\x85b", "a\x85b\n!")]


def test_cdata_terminator_and_entities_survive_as_text(tmp_path):
    name = "x]]> & < > \" '"
    _one("w", name)
    zf = export()
    raw = zf.read("01_Bulk/Bulk_Waypoints.gpx")
    assert b"<name>x]]&gt; &amp; &lt; &gt; \" '</name>" in raw
    assert [n for _f, _k, n, _d in gpx_items(zf)] == [name]
    assert [n for _f, _k, n, _s in reader_items(zf, tmp_path)] == [name]


def _two_folder_map(n_per: int) -> str:
    feats = [_folder("f0", "North"), _folder("f1", "South")]
    i = 0
    for fid in ("f0", "f1"):
        for k in range(n_per):
            i += 1
            kind = KINDS[k % 3]
            f = _pt(i, fid) if kind == "w" else _line(i, fid) if kind == "l" else _poly(i, fid, holes=0)
            f["properties"].update(title=f"{fid}-{k}", description=f"{fid}-note-{k}")
            feats.append(f)
    return json.dumps({"type": "FeatureCollection", "features": feats})


def test_preview_equals_saved_equals_exported_for_names(tmp_path):
    """Two folders, every round-trip name vector's after stored on an item; then a second
    pass blanks every third item. Each time, per folder and kind: stored == after ==
    <name> text; the reader gives its own cleaning of it. A blank name stops the export
    (N1) until it is named "Untitled", as the app does first.
    DEVIATION (N1, 2026-10-25): blank names were exported as "" and read back as ""."""
    n = len(ROUND_TRIP_NAMES)
    items = load_files(_two_folder_map(n))
    afters = [a for _l, _b, _s, a in ROUND_TRIP_NAMES] * 2
    bridge.apply_edits(json.dumps({i["uid"]: {"name": a} for i, a in zip(items, afters)}))
    for pass_ in ("renamed", "blanked"):
        if pass_ == "blanked":
            bridge.apply_edits(json.dumps({i["uid"]: {"name": ""} for i in items[::3]}))
        with pytest.raises(ValueError, match="An item needs a name"):
            bridge.export_zip()
        name_blanks(bridge)
        assert not blank_uids(bridge)
        want = Counter((g, i["kind"], i["name"]) for g, i in stored_by_folder())
        zf = export()
        dirs = {e["dir"]: e["folder"] for e in bridge._STATE["manifest"]}
        got = Counter((dirs[d], k, nm) for d, k, nm, _s in gpx_items(zf))
        assert got == want, pass_
        back = Counter((dirs[d], k, nm) for d, k, nm, _s in reader_items(zf, tmp_path))
        assert back == Counter((g, k, reader_name(nm)) for (g, k, nm), c in want.items() for _ in range(c))
    assert sum(1 for _g, i in stored_by_folder() if i["name"] == "Untitled") >= len(items) // 3


def test_preview_equals_saved_equals_exported_for_notes(tmp_path):
    """Every round-trip note vector's after, stored and exported: <desc> text equals it
    exactly, line breaks kept; a blank note writes no <desc> at all (read as "")."""
    items = load_files(_two_folder_map(len(ROUND_TRIP_NOTES)))
    afters = [a for _l, _b, _s, a in ROUND_TRIP_NOTES] * 2
    bridge.apply_edits(json.dumps({i["uid"]: {"desc": a} for i, a in zip(items, afters)}))
    want = Counter((i["kind"], i["desc"]) for i in stored())
    assert want == Counter((i["kind"], a) for i, a in zip(items, afters))
    zf = export()
    assert Counter((k, d) for _f, k, _n, d in gpx_items(zf)) == want
    raw = b"".join(zf.read(m) for m in zf.namelist() if m.endswith(".gpx"))
    assert raw.count(b"<desc>") == sum(c for (_k, d), c in want.items() if d)
    back = Counter((k, s) for _f, k, _n, s in reader_items(zf, tmp_path))
    assert back == Counter((k, reader_note(d)) for (k, d), c in want.items() for _ in range(c))
