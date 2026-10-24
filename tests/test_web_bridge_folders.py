"""ENG-07: opaque item uids and the folder primitives in web/bridge.py.

rename_folder / move_items / merge_folders change only folder names,
membership and order. Every item keeps its uid, its edits, its exclusion and
its pinned style wherever it goes, and export_zip writes each item in the
folder it is in NOW, numbered by the folders' current order.
"""

from __future__ import annotations

import io
import json
import random
import re
import sys
import zipfile
from pathlib import Path

import pytest

from cairn.io.onx_gpx import read_onx_gpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402

FX = Path(__file__).parent / "fixtures"
BITTERROOTS = [FX / "bitterroots" / "Bitterroots__Complete_.json"]
ONX_PAIR = [FX / "onx_dialect" / "onx_dialect.gpx", FX / "onx_dialect" / "onx_dialect.kml"]
AREAS_PAIR = [FX / "onx_exports" / "areas-after-edit.gpx", FX / "onx_exports" / "areas-after-edit.kml"]
DARK_DIVIDE = [FX / "dark_divide_100" / "caltopo" / "2027_Dark_Divide_100_Mile_Endurance_Run.json"]
CALTOPO_KML = [FX / "caltopo-random" / "onx-test-random.kml"]
# Several sources at once: one CalTopo map and one onX pair, each its own folders.
MIXED = BITTERROOTS + ONX_PAIR


def _load(paths) -> dict:
    files = [{"name": p.name, "text": p.read_text(encoding="utf-8")} for p in paths]
    return json.loads(bridge.load_files(json.dumps(files)))


def _groups() -> list:
    return bridge._STATE["groups"]


def _key(name: str) -> str:
    (g,) = [g for g in _groups() if g["name"] == name]
    return g["key"]


def _group(name: str) -> dict:
    (g,) = [g for g in _groups() if g["name"] == name]
    return g


def _uids(name: str, kind: str | None = None) -> list:
    return [i["uid"] for i in _group(name)["items"] if kind is None or i["kind"] == kind]


def _item(uid: str) -> dict:
    (it,) = [i for g in _groups() for i in g["items"] if i["uid"] == uid]
    return it


def _folder_of(uid: str) -> str:
    (name,) = [g["name"] for g in _groups() for i in g["items"] if i["uid"] == uid]
    return name


def _move(uids, key=None, name=None) -> dict:
    return json.loads(bridge.move_items(json.dumps(list(uids)), key, name))


def _layout() -> list:
    return [(g["key"], g["name"], g["safe"], [i["uid"] for i in g["items"]]) for g in _groups()]


def _export() -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(bridge.export_zip()))


def _markups(text: str) -> int:
    return text.count("<wpt ") + text.count("<trk>") + text.count("<rte>")


def _members(zf: zipfile.ZipFile) -> dict:
    return {n: zf.read(n) for n in zf.namelist()}


def _check_export(zf: zipfile.ZipFile) -> None:
    """Each manifest entry is the folder at its position, its files sit under
    NN_<safe>/, hold exactly its included items, and instructions.txt says so."""
    manifest = bridge._STATE["manifest"]
    lines = zf.read("instructions.txt").decode("utf-8").split("\r\n")
    by_n = {n: g for n, g in enumerate(_groups(), 1)}
    listed = set()
    for e in manifest:
        g = by_n[e["n"]]
        assert e["folder"] == g["name"]
        included = sum(1 for i in g["items"] if i.get("included", True))
        assert e["expected"] == included
        prefix = f"{e['n']:02d}_{g['safe']}/"
        assert e["files"] and all(f["path"].startswith(prefix) for f in e["files"])
        assert sum(_markups(zf.read(f["path"]).decode()) for f in e["files"]) == e["count"]
        # instructions.txt (round 4): the zip folder and the name to type, then
        # each file and every item written to it, by name.
        at = lines.index(f"{e['dir']}/    rename to: {g['name']}")
        for f in e["files"]:
            assert len(f["items"]) == f["count"]
            assert "    " + f["path"].split("/")[-1] in lines[at:]
        listed.update(f["path"] for f in e["files"])
    # Nothing else in the zip, and no folder with an included item left unlisted.
    assert set(zf.namelist()) == listed | {"instructions.txt"}
    for n, g in by_n.items():
        if any(i.get("included", True) for i in g["items"]):
            assert any(e["n"] == n for e in manifest), g["name"]


def _check_invariants(all_uids: set) -> None:
    seen = [i["uid"] for g in _groups() for i in g["items"]]
    assert len(seen) == len(set(seen)), "an item is in two folders"
    assert set(seen) == all_uids, "an item was lost or invented"
    assert all(g["items"] for g in _groups()), "an empty folder survived"
    names = [g["name"].strip().casefold() for g in _groups()]
    assert len(names) == len(set(names)), "two folders share a name"
    assert all(g["name"] == g["name"].strip() and g["name"] for g in _groups())
    order = {"waypoints": 0, "tracks": 1, "shapes": 2}
    feats = bridge._STATE["features"]
    folders = bridge.doc_folders()
    assert list(folders) == [g["key"] for g in _groups()]
    for g in _groups():
        kinds = [order[i["kind"]] for i in g["items"]]
        assert kinds == sorted(kinds), f"{g['name']}: kinds are not in runs"
        assert g["safe"] == bridge._safe(g["name"])
        fdata = folders[g["key"]]
        assert fdata["name"] == g["name"]
        for kind in order:
            want = [feats[i["uid"]] for i in g["items"] if i["kind"] == kind]
            assert [id(f) for f in fdata[kind]] == [id(f) for f in want]


# --- uids ---------------------------------------------------------------------------


@pytest.mark.parametrize("paths", [BITTERROOTS, MIXED], ids=["bitterroots", "mixed"])
def test_uids_are_opaque_unique_and_each_maps_to_its_own_feature(paths):
    data = _load(paths)
    items = [i for g in data["groups"] for i in g["items"]]
    uids = [i["uid"] for i in items]
    assert len(uids) == len(set(uids)) == len(bridge._STATE["features"])
    assert all(re.fullmatch(r"i\d+", u) for u in uids)
    keys = [g["key"] for g in data["groups"]]
    assert not [u for u in uids if any(k in u for k in keys if len(k) > 2)]
    feats = bridge._STATE["features"]
    assert len({id(feats[u]) for u in uids}) == len(uids)
    for g in data["groups"]:
        fdata = bridge._STATE["doc"].folders[g["key"]]
        for kind in ("waypoints", "tracks", "shapes"):
            assert [feats[i["uid"]] for i in g["items"] if i["kind"] == kind] == fdata[kind]


def test_the_same_file_gets_the_same_uids_each_load():
    first = [i["uid"] for g in _load(BITTERROOTS)["groups"] for i in g["items"]]
    assert first == [i["uid"] for g in _load(BITTERROOTS)["groups"] for i in g["items"]]


# --- rename -------------------------------------------------------------------------


def test_rename_trims_renames_and_exports_under_the_new_safe_name():
    _load(BITTERROOTS)
    key = _key("Lost Trail Pass")
    res = json.loads(bridge.rename_folder(key, "  Lost Trail #2 & Co.  "))
    folders = res.pop("folders")
    assert res == {"ok": True, "key": key, "name": "Lost Trail #2 & Co.",
                   "safe": bridge._safe("Lost Trail #2 & Co."), "unorganized": False}
    assert [(f["key"], f["name"], f["safe"], f["uids"]) for f in folders] == _layout()
    assert res["safe"] == "Lost_Trail_2_Co"
    assert _layout()[1][:3] == (key, "Lost Trail #2 & Co.", "Lost_Trail_2_Co")
    zf = _export()
    names = zf.namelist()
    assert "02_Lost_Trail_2_Co/Lost_Trail_2_Co_Waypoints.gpx" in names
    assert not [n for n in names if "Lost_Trail_Pass" in n]
    assert "<name>Lost Trail #2 &amp; Co.</name>" in zf.read(
        "02_Lost_Trail_2_Co/Lost_Trail_2_Co_Tracks.gpx").decode()
    _check_export(zf)


def test_rename_to_its_own_name_in_another_case_is_allowed():
    _load(BITTERROOTS)
    key = _key("North Roots")
    assert json.loads(bridge.rename_folder(key, " NORTH roots"))["ok"] is True
    assert _group("NORTH roots")["key"] == key


def test_rename_onto_another_folders_name_is_reported_not_merged():
    _load(BITTERROOTS)
    before = _layout()
    res = json.loads(bridge.rename_folder(_key("Lost Trail Pass"), "  north ROOTS "))
    assert res == {"ok": False, "name": "north ROOTS",
                   "duplicate": {"key": _key("North Roots"), "name": "North Roots", "count": 22}}
    assert _layout() == before


@pytest.mark.parametrize("name", ["", "   ", "\t\n", None])
def test_rename_to_an_empty_name_raises(name):
    _load(BITTERROOTS)
    before = _layout()
    with pytest.raises(ValueError, match="needs a name"):
        bridge.rename_folder(_key("Blodgett"), name)
    assert _layout() == before


def test_rename_an_unknown_folder_raises():
    _load(BITTERROOTS)
    with pytest.raises(ValueError, match="no folder"):
        bridge.rename_folder("nope", "Anything")


def test_unorganized_is_renamable():
    _load(BITTERROOTS)
    key = _key("Unorganized")
    assert json.loads(bridge.rename_folder(key, "Misc"))["ok"]
    zf = _export()
    assert "01_Misc/Misc_Waypoints.gpx" in zf.namelist()
    assert not [n for n in zf.namelist() if "Unorganized" in n]
    _check_export(zf)


# --- move ---------------------------------------------------------------------------


def test_move_into_an_existing_folder_goes_to_the_end_of_each_kind():
    data = _load(BITTERROOTS)
    all_uids = {i["uid"] for g in data["groups"] for i in g["items"]}
    src, dst = _key("Lost Trail Pass"), _key("North Roots")
    wps, trk = _uids("Lost Trail Pass", "waypoints"), _uids("Lost Trail Pass", "tracks")[0]
    old_dst = _uids("North Roots")
    # Given out of order: they move in the map's order.
    res = _move([trk, wps[1], wps[0]], dst)
    assert res["ok"] and res["key"] == dst and res["created"] is False
    assert res["moved"] == 3 and res["removed"] == []
    assert res["folders"] == [{"key": k, "name": n, "safe": s, "unorganized": n == "Unorganized",
                               "uids": u} for k, n, s, u in _layout()]
    got = _uids("North Roots")
    n_wp = len([u for u in old_dst if _item(u)["kind"] == "waypoints"])
    assert got[:n_wp] == old_dst[:n_wp] and got[n_wp:n_wp + 2] == wps
    n_trk = len([u for u in old_dst if _item(u)["kind"] == "tracks"])
    assert got[n_wp + 2 + n_trk] == trk
    assert len(_group("Lost Trail Pass")["items"]) == 28 and len(got) == 25
    assert [g["key"] for g in _groups()][:3] == ["orphaned_features", src, dst]
    _check_invariants(all_uids)


def test_move_into_a_new_folder_creates_it_at_the_end():
    data = _load(BITTERROOTS)
    all_uids = {i["uid"] for g in data["groups"] for i in g["items"]}
    uids = _uids("Trapper area")[:3]
    res = _move(uids, name="  Camps ")
    assert res["created"] is True and res["moved"] == 3
    assert _groups()[-1]["key"] == res["key"] and _groups()[-1]["name"] == "Camps"
    assert _uids("Camps") == uids
    assert res["key"] not in {g["key"] for g in data["groups"]}
    _check_invariants(all_uids)
    zf = _export()
    assert "11_Camps/Camps_Waypoints.gpx" in zf.namelist()
    _check_export(zf)


def test_a_second_new_folder_gets_its_own_key():
    _load(BITTERROOTS)
    a = _move(_uids("Blodgett")[:1], name="A")["key"]
    b = _move(_uids("Blodgett")[:1], name="B")["key"]
    assert a != b and [g["name"] for g in _groups()][-2:] == ["A", "B"]


def test_a_new_folder_named_like_an_existing_one_is_reported():
    _load(BITTERROOTS)
    before = _layout()
    res = _move(_uids("Blodgett")[:2], name=" paddling")
    assert res == {"ok": False, "name": "paddling",
                   "duplicate": {"key": _key("Paddling"), "name": "Paddling", "count": 5}}
    assert _layout() == before


def test_moving_a_folders_last_item_removes_the_folder_and_renumbers_export():
    data = _load(BITTERROOTS)
    all_uids = {i["uid"] for g in data["groups"] for i in g["items"]}
    mill = _key("Mill Creek Canyon")
    res = _move(_uids("Mill Creek Canyon"), _key("Blodgett"))
    assert res["removed"] == [mill]
    assert mill not in {g["key"] for g in _groups()}
    assert mill not in bridge.doc_folders()
    assert mill not in {f["key"] for f in res["folders"]}
    with pytest.raises(ValueError):
        bridge.rename_folder(mill, "Back")
    _check_invariants(all_uids)
    zf = _export()
    assert not [n for n in zf.namelist() if n.startswith("10_")]
    assert len(bridge._STATE["manifest"]) == 9
    _check_export(zf)


def test_a_folder_empty_at_load_survives_other_moves():
    """Only a folder a move empties is removed, and `removed` names exactly it."""
    def pt(fid, title, folder):
        return {"type": "Feature", "id": fid, "geometry": {"type": "Point", "coordinates": [-114, 46]},
                "properties": {"class": "Marker", "title": title, "folderId": folder}}
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": f, "geometry": None, "properties": {"class": "Folder", "title": t}}
        for f, t in (("fa", "A"), ("fb", "B"), ("fe", "Empty"))
    ] + [pt("p1", "One", "fa"), pt("p2", "Two", "fa"), pt("p3", "Three", "fb")]}
    data = json.loads(bridge.load_document(json.dumps(doc), "m.json"))
    if "Empty" not in [g["name"] for g in data["groups"]]:
        pytest.skip("parse_geojson no longer keeps an empty folder")
    res = _move([_uids("A")[0]], _key("B"))
    assert res["removed"] == [] and "Empty" in [g["name"] for g in _groups()]
    res = _move(_uids("A"), _key("B"))
    assert res["removed"] == ["fa"] and [g["name"] for g in _groups()] == ["B", "Empty"]
    assert set(bridge.doc_folders()) == {"fb", "fe"}


def test_emptying_a_middle_folder_closes_the_gap_in_numbering():
    _load(BITTERROOTS)
    _move(_uids("North Roots"), _key("Paddling"))
    zf = _export()
    assert "03_Trapper_area/Trapper_area_Waypoints.gpx" in zf.namelist()
    assert "08_Paddling/Paddling_Areas.gpx" in zf.namelist()
    _check_export(zf)


def test_moving_to_the_folder_it_is_in_does_nothing():
    _load(BITTERROOTS)
    before = _layout()
    res = _move(_uids("Blodgett")[:4], _key("Blodgett"))
    assert res["ok"] and res["moved"] == 0 and res["removed"] == []
    assert _layout() == before


def test_a_move_partly_into_its_own_folder_moves_only_the_others():
    _load(BITTERROOTS)
    own, other = _uids("Blodgett")[0], _uids("Paddling")[0]
    res = _move([own, other], _key("Blodgett"))
    assert res["moved"] == 1 and _uids("Blodgett")[0] == own and _folder_of(other) == "Blodgett"


@pytest.mark.parametrize("bad", [["nope"], ["i0", "nope"], ["i0", "i99999"]])
def test_unknown_uids_raise_and_apply_nothing(bad):
    _load(BITTERROOTS)
    before = _layout()
    with pytest.raises(ValueError, match="Unknown item"):
        _move(bad, _key("Paddling"))
    with pytest.raises(ValueError, match="Unknown item"):
        _move(bad, name="Fresh")
    assert _layout() == before


@pytest.mark.parametrize("uids,key,name", [
    ([], "Paddling", None), ("i0", "Paddling", None), ([1], "Paddling", None),
    (["i0"], None, None), (["i0"], "", None), (["i0"], "Paddling", "Both"),
    (["i0"], None, "  "), (["i0"], "no-such-folder", None),
])
def test_bad_move_arguments_raise_and_apply_nothing(uids, key, name):
    _load(BITTERROOTS)
    before = _layout()
    key = _key(key) if key == "Paddling" else key
    with pytest.raises(ValueError):
        bridge.move_items(json.dumps(uids), key, name)
    assert _layout() == before


def test_move_mixed_kinds_keeps_each_kind_in_its_run():
    data = _load(BITTERROOTS)
    all_uids = {i["uid"] for g in data["groups"] for i in g["items"]}
    picks = [_uids("North Roots", k)[0] for k in ("shapes", "waypoints", "tracks")]
    _move(picks, _key("Trapper area"))   # Trapper area had no areas
    kinds = [i["kind"] for i in _group("Trapper area")["items"]]
    assert kinds == ["waypoints"] * 9 + ["tracks"] * 14 + ["shapes"]
    _check_invariants(all_uids)
    zf = _export()
    assert "04_Trapper_area/Trapper_area_Areas.gpx" in zf.namelist()
    _check_export(zf)


def test_moving_everything_into_one_folder():
    data = _load(BITTERROOTS)
    all_uids = [i["uid"] for g in data["groups"] for i in g["items"]]
    res = _move(all_uids, _key("Paddling"))
    assert len(res["removed"]) == 9 and [f["key"] for f in res["folders"]] == [_key("Paddling")]
    _check_invariants(set(all_uids))
    zf = _export()
    (entry,) = bridge._STATE["manifest"]
    assert entry["n"] == 1 and entry["count"] == 177 == len(all_uids)
    assert sorted(zf.namelist()) == ["01_Paddling/Paddling_Areas.gpx",
                                     "01_Paddling/Paddling_Tracks.gpx",
                                     "01_Paddling/Paddling_Waypoints.gpx", "instructions.txt"]
    text = zf.read("instructions.txt").decode("utf-8")
    assert text.count("rename to:") == 1 and "01_Paddling/    rename to: Paddling\r\n" in text
    _check_export(zf)


def test_moving_out_of_unorganized_into_a_new_folder():
    data = _load(BITTERROOTS)
    all_uids = {i["uid"] for g in data["groups"] for i in g["items"]}
    unorg = _key("Unorganized")
    res = _move(_uids("Unorganized"), name="Sorted")
    assert res["removed"] == [unorg] and _groups()[-1]["name"] == "Sorted"
    _check_invariants(all_uids)
    zf = _export()
    assert "01_Lost_Trail_Pass/Lost_Trail_Pass_Tracks.gpx" in zf.namelist()
    assert "10_Sorted/Sorted_Waypoints.gpx" in zf.namelist()
    _check_export(zf)


# --- merge --------------------------------------------------------------------------


def test_merge_moves_everything_and_keeps_the_targets_name_and_place():
    data = _load(BITTERROOTS)
    all_uids = {i["uid"] for g in data["groups"] for i in g["items"]}
    src, dst = _key("Paddling"), _key("Blodgett")
    moved = _uids("Paddling")
    res = json.loads(bridge.merge_folders(src, dst))
    assert res["ok"] and res["key"] == dst and res["moved"] == 5 and res["removed"] == [src]
    assert [g["name"] for g in _groups()].index("Blodgett") == 5
    assert set(moved) < set(_uids("Blodgett")) and len(_uids("Blodgett")) == 22
    _check_invariants(all_uids)
    _check_export(_export())


def test_rename_clash_then_merge_is_the_ui_flow():
    _load(BITTERROOTS)
    src = _key("Lost Trail Pass")
    dup = json.loads(bridge.rename_folder(src, "North Roots"))["duplicate"]
    res = json.loads(bridge.merge_folders(src, dup["key"]))
    assert res["removed"] == [src] and len(_uids("North Roots")) == 53


def test_merge_into_itself_does_nothing_and_unknown_keys_raise():
    _load(BITTERROOTS)
    before = _layout()
    assert json.loads(bridge.merge_folders(_key("Paddling"), _key("Paddling")))["moved"] == 0
    with pytest.raises(ValueError):
        bridge.merge_folders("nope", _key("Paddling"))
    with pytest.raises(ValueError):
        bridge.merge_folders(_key("Paddling"), "nope")
    assert _layout() == before


# --- edits, exclusions and pinned styles travel with the item ------------------------


@pytest.mark.parametrize("edit_first", [True, False], ids=["edit-then-move", "move-then-edit"])
def test_edits_and_exclusions_survive_a_move(edit_first):
    _load(BITTERROOTS)
    wp, wp2 = _uids("Lost Trail Pass", "waypoints")
    trk = _uids("Lost Trail Pass", "tracks")[0]
    area = _uids("Lost Trail Pass", "shapes")[0]
    edits = {
        wp: {"name": "Moved Camp", "icon": "Camp", "color": "rgba(128,0,128,1)", "desc": "moved note"},
        wp2: {"included": False},
        trk: {"name": "Moved Line", "color": "rgba(255,0,255,1)", "style": "dash", "weight": "6.0"},
        area: {"name": "Moved Area", "style": "dash", "weight": "6.0"},
    }
    excluded_name = _item(wp2)["name"]
    if edit_first:
        bridge.apply_edits(json.dumps(edits))
    _move([wp, wp2, trk, area], name="Moved")
    if not edit_first:
        assert json.loads(bridge.apply_edits(json.dumps(edits)))["applied"] == 4
    zf = _export()
    _check_export(zf)
    moved_n = len(_groups())
    wps = zf.read(f"{moved_n:02d}_Moved/Moved_Waypoints.gpx").decode()
    assert _markups(wps) == 1
    assert "<name>Moved Camp</name>" in wps and "moved note" in wps
    assert "Camp" in wps and "rgba(128,0,128,1)" in wps
    blob = "".join(zf.read(n).decode() for n in zf.namelist() if n.endswith(".gpx"))
    assert f"<name>{excluded_name}</name>" not in blob
    assert blob.count("<name>Moved Camp</name>") == 1
    trks = zf.read(f"{moved_n:02d}_Moved/Moved_Tracks.gpx").decode()
    assert "<name>Moved Line</name>" in trks
    assert "<onx:style>dash</onx:style>" in trks and "<onx:weight>6.0</onx:weight>" in trks
    assert "rgba(255,0,255,1)" in trks
    areas = zf.read(f"{moved_n:02d}_Moved/Moved_Areas.gpx").decode()
    assert "<name>Moved Area</name>" in areas and "<onx:style>dash</onx:style>" in areas
    assert not [n for n in zf.namelist() if n.startswith("02_") and "Areas" in n]
    entry = bridge._STATE["manifest"][-1]
    assert entry["folder"] == "Moved" and entry["count"] == 3 and entry["excluded"] == 1


@pytest.mark.parametrize("paths", [ONX_PAIR, AREAS_PAIR], ids=["onx", "areas"])
def test_onx_track_and_area_styles_survive_a_move(paths, tmp_path):
    data = _load(paths)
    lines = [i for g in data["groups"] for i in g["items"] if i["kind"] != "waypoints"]
    shown = sorted((i["name"], i["color"], i["style"], i["weight"]) for i in lines)
    _move([i["uid"] for i in lines], name="Lines")
    n = len(_groups())
    zf = _export()
    _check_export(zf)
    got = []
    for member in zf.namelist():
        if member.startswith(f"{n:02d}_Lines/"):
            out = tmp_path / Path(member).name
            out.write_bytes(zf.read(member))
            got += [(it.name, it.style.OnX_color_rgba, it.style.OnX_style, it.style.OnX_weight)
                    for it in read_onx_gpx(out).items]
    assert sorted(got) == shown


# --- unchanged maps export unchanged ------------------------------------------------


@pytest.mark.parametrize("paths", [BITTERROOTS, ONX_PAIR, MIXED], ids=["bitterroots", "onx", "mixed"])
def test_no_op_folder_calls_leave_the_export_unchanged(paths):
    _load(paths)
    before = _members(_export())
    g = _groups()[0]
    _move([i["uid"] for i in g["items"]][:3], g["key"])
    name = g["name"]
    bridge.rename_folder(g["key"], name.upper() + " x")
    bridge.rename_folder(g["key"], name)
    bridge.merge_folders(g["key"], g["key"])
    assert _members(_export()) == before


# --- property: random moves, renames and merges lose nothing ---------------------------


FIXTURE_SETS = {
    "bitterroots": BITTERROOTS, "onx-pair": ONX_PAIR, "areas-pair": AREAS_PAIR,
    "dark-divide": DARK_DIVIDE, "caltopo-kml": CALTOPO_KML, "mixed": MIXED,
}
NAMES = ["Camps", "camps ", "Water", "Lines", "Unorganized", "North Roots", "Trip #1 / A&B",
         "  Ridge  ", "RIDGE", "ünïcode ✓", "x"]


def _random_session(rng: random.Random, paths) -> None:
    data = _load(paths)
    all_uids = {i["uid"] for g in data["groups"] for i in g["items"]}
    for _ in range(40):
        op = rng.choice(["move", "move", "new", "rename", "merge", "exclude"])
        groups = _groups()
        uids = sorted(all_uids)
        if op == "move":
            picks = rng.sample(uids, rng.randint(1, min(12, len(uids))))
            res = _move(picks, rng.choice(groups)["key"])
            assert res["ok"]
            assert all(_folder_of(u) == next(g["name"] for g in _groups()
                                             if g["key"] == res["key"]) for u in picks)
        elif op == "new":
            picks = rng.sample(uids, rng.randint(1, min(12, len(uids))))
            name = rng.choice(NAMES) + rng.choice(["", f" {rng.randint(0, 3)}"])
            before = _layout()
            res = _move(picks, name=name)
            if res["ok"]:
                assert res["created"] and _groups()[-1]["name"] == name.strip()
                assert set(_uids(name.strip())) == set(picks)
            else:
                assert _layout() == before
                assert res["duplicate"]["name"].casefold() == name.strip().casefold()
        elif op == "rename":
            g = rng.choice(groups)
            res = json.loads(bridge.rename_folder(g["key"], rng.choice(NAMES)))
            if not res["ok"] and rng.random() < 0.7:
                bridge.merge_folders(g["key"], res["duplicate"]["key"])
        elif op == "merge" and len(groups) > 1:
            a, b = rng.sample(groups, 2)
            n = len(a["items"]) + len(b["items"])
            bridge.merge_folders(a["key"], b["key"])
            assert len(_group(b["name"])["items"]) == n
        elif op == "exclude":
            u = rng.choice(uids)
            bridge.apply_edits(json.dumps({u: {"included": not _item(u)["included"]}}))
        _check_invariants(all_uids)
    zf = _export()
    _check_export(zf)
    included = sum(1 for g in _groups() for i in g["items"] if i["included"])
    markups = sum(_markups(zf.read(n).decode()) for n in zf.namelist() if n.endswith(".gpx"))
    summary = bridge.runbook_summary(bridge._STATE["manifest"], bridge._STATE["unlisted_dropped"])
    assert summary["dropped"] == 0
    assert markups == included == summary["written"]


@pytest.mark.parametrize("fixture", list(FIXTURE_SETS))
@pytest.mark.parametrize("seed", range(4))
def test_random_folder_sessions_lose_and_duplicate_nothing(fixture, seed):
    _random_session(random.Random(f"{fixture}:{seed}"), FIXTURE_SETS[fixture])


def test_merging_an_empty_folder_removes_it():
    """PR-C: renaming a folder that loaded empty onto a taken name, then "Move
    them", must not leave the empty folder behind under its old name."""
    def pt(fid, title, folder):
        return {"type": "Feature", "id": fid, "geometry": {"type": "Point", "coordinates": [-114, 46]},
                "properties": {"class": "Marker", "title": title, "folderId": folder}}
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": f, "geometry": None, "properties": {"class": "Folder", "title": t}}
        for f, t in (("fa", "A"), ("fe", "Empty"))
    ] + [pt("p1", "One", "fa")]}
    data = json.loads(bridge.load_document(json.dumps(doc), "m.json"))
    if "Empty" not in [g["name"] for g in data["groups"]]:
        pytest.skip("parse_geojson no longer keeps an empty folder")
    assert json.loads(bridge.rename_folder("fe", "a"))["duplicate"]["key"] == "fa"
    res = json.loads(bridge.merge_folders("fe", "fa"))
    assert res["removed"] == ["fe"] and res["moved"] == 0
    assert [f["name"] for f in res["folders"]] == ["A"]
    assert set(bridge.doc_folders()) == {"fa"}


# --- round 2 (2026-10-23): review and QA findings --------------------------------

from tests.hardening_maps import make_map  # noqa: E402


def _load_text(text: str, name: str = "m.json") -> dict:
    return json.loads(bridge.load_document(text, name))


def test_the_loose_items_are_flagged_by_where_they_came_from_not_by_name():
    """F6 / review #8: a real CalTopo folder called "Unorganized" is an ordinary
    folder; only the items outside every folder are the loose items."""
    doc = json.loads(make_map(2, seed=5, names=["Unorganized", "Trips"]))
    doc["features"].append({"type": "Feature", "id": "loose", "properties": {
        "title": "Loose", "class": "Marker"}, "geometry": {"type": "Point", "coordinates": [-114, 46]}})
    # Two folders would then share the name "Unorganized": rename the real one first.
    data = _load_text(json.dumps(doc))
    flags = {(g["key"], g["name"]): g["unorganized"] for g in data["groups"]}
    assert flags[("f0", "Unorganized")] is False
    assert flags[("orphaned_features", "Unorganized")] is True
    assert [f["unorganized"] for f in json.loads(bridge.layout_json())["folders"]] == \
        [g["unorganized"] for g in data["groups"]]


def test_renaming_the_loose_items_clears_the_flag_and_renaming_back_restores_it():
    _load(BITTERROOTS)
    key = _key("Unorganized")
    assert _group("Unorganized")["unorganized"] is True
    res = json.loads(bridge.rename_folder(key, "Misc"))
    assert res["unorganized"] is False and _group("Misc")["unorganized"] is False
    assert [f["unorganized"] for f in res["folders"] if f["key"] == key] == [False]
    assert json.loads(bridge.rename_folder(key, "Unorganized"))["unorganized"] is True
    # Another folder renamed to it (once it is free) is not the loose items.
    bridge.rename_folder(key, "Misc")
    res = json.loads(bridge.rename_folder(_key("Paddling"), "Unorganized"))
    assert res["ok"] and res["unorganized"] is False
    # A new folder never is.
    res = json.loads(bridge.move_to_new_folder(json.dumps(_uids("Blodgett")[:1])))
    assert [f["unorganized"] for f in res["folders"] if f["key"] == res["key"]] == [False]


@pytest.mark.parametrize("name", ["unorganized", "UNORGANIZED", "UnOrganized"])
def test_a_case_only_rename_of_the_loose_items_keeps_their_flag(name):
    """Round 3 #4: renaming "Unorganized" to "unorganized" is the same name by
    the folder-name rule (casefold), so the loose items stay the loose items."""
    _load(BITTERROOTS)
    key = _key("Unorganized")
    res = json.loads(bridge.rename_folder(key, name))
    assert res["ok"] and res["name"] == name and res["unorganized"] is True
    assert _group(name)["unorganized"] is True
    assert [f["unorganized"] for f in res["folders"] if f["key"] == key] == [True]


def test_new_folder_takes_the_first_free_default_name_by_the_bridges_rule():
    """Review #7: the default name is picked by the bridge (casefolded, trimmed),
    not by the UI retrying move_items."""
    data = _load_text(make_map(3, seed=3, names=["New folder", " new FOLDER 2 ", "Camp"]))
    assert bridge.default_folder_name() == "New folder 3"
    uid = data["groups"][0]["items"][0]["uid"]
    res = json.loads(bridge.move_to_new_folder(json.dumps([uid])))
    assert res["ok"] and res["created"] and res["moved"] == 1
    assert [f["name"] for f in res["folders"]][-1] == "New folder 3"
    assert bridge.default_folder_name() == "New folder 4"
    _load(BITTERROOTS)
    assert bridge.default_folder_name() == "New folder"


def _old_safe(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", (name or "").strip()).strip()
    s = re.sub(r"[-\s]+", "_", s)
    if len(s.encode("utf-8")) <= bridge._SAFE_MAX_BYTES:
        return s or "Unnamed"
    while len(s.encode("utf-8")) > bridge._SAFE_MAX_BYTES:
        s = s[:-1]
    return s.rstrip("_") or "Unnamed"


def _main_safe(name: str) -> str:
    """main's _safe, verbatim (before the 80-byte cap)."""
    s = re.sub(r"[^\w\s-]", "", (name or "").strip()).strip()
    return re.sub(r"[-\s]+", "_", s) or "Unnamed"


@pytest.mark.parametrize("name", ["Trip -", "Trip_", "___", "_", "-", "a - b -", "_x_", "Camp #2 -",
                                  "Lost Trail #2 & Co.", "Peak 🏔️", "..", "", "x" * 80, "a" * 79 + "_"])
def test_safe_is_mains_for_a_name_that_was_never_cut(name):
    """Round 3 #2: the trailing-"_" strip is for a cut name only; every other
    name gets exactly the file name it got on main ('Trip -' -> 'Trip_')."""
    assert bridge._safe(name) == _main_safe(name)


@pytest.mark.parametrize("name", ["ä" * 200, "x" * 300, "日本語のフォルダ" * 20, "a" * 79 + " b",
                                  "Zürich Café", "a" * 79 + "ä", "🏔️ Peaks 🎿", ".."])
def test_safe_cuts_by_bytes_in_one_step_with_the_same_result(name):
    """Review #3: the char-at-a-time loop was O(L^2); the byte slice gives the same name."""
    assert bridge._safe(name) == _old_safe(name)
    assert len(bridge._safe(name).encode("utf-8")) <= bridge._SAFE_MAX_BYTES


def test_safe_of_a_huge_name_is_fast():
    import time
    t = time.perf_counter()
    assert len(bridge._safe("ä" * 200_000).encode("utf-8")) <= bridge._SAFE_MAX_BYTES
    assert time.perf_counter() - t < 0.5


def _rename_to(text: str, n: int) -> str:
    """The name instructions.txt says to type for folder n."""
    return re.search(rf"^0*{n}_[^\r\n]*/    rename to: ([^\r\n]*)\r?$", text, re.M).group(1)


@pytest.mark.parametrize("name", ["Trip `A`", "`tick", "a``b```c", "plain"])
def test_instructions_rename_line_shows_a_name_with_backticks_exactly(name):
    """Review #4, plain text since round 4: the name to type is the name, as is."""
    _load(BITTERROOTS)
    bridge.rename_folder(_key("Paddling"), name)
    n = [g["name"] for g in _groups()].index(name) + 1
    text = _export().read("instructions.txt").decode("utf-8")
    assert _rename_to(text, n) == name


def test_control_characters_in_folder_names_become_one_space():
    """Review #4: a newline in a name broke the guide's lines."""
    data = _load_text(make_map(2, seed=7, names=["new\nline", "tab\there\r\n"]))
    names = {g["name"] for g in data["groups"]}
    assert "new line" in names and "tab here" in names
    key = data["groups"][0]["key"]
    res = json.loads(bridge.rename_folder(key, "two\nlines\x00here "))
    assert res["name"] == "two lines here"
    text = _export().read("instructions.txt").decode("utf-8")
    assert _rename_to(text, 1) == "two lines here"
    with pytest.raises(ValueError):
        bridge.rename_folder(key, "\n\t\r")


def test_folder_zip_is_read_from_the_kept_zip_not_a_second_copy():
    """Review #6: no per-file copy of the export is kept beside the zip."""
    _load(BITTERROOTS)
    allz = _export()
    assert "blobs" not in bridge._STATE and bridge._STATE["zip"]
    for e in bridge._STATE["manifest"]:
        fz = zipfile.ZipFile(io.BytesIO(bridge.export_folder_zip(e["n"])))
        assert fz.namelist() == [f["path"] for f in e["files"]]
        assert all(fz.read(p) == allz.read(p) for p in fz.namelist())
        assert f"{e['n']:02d}_{e['safe']}" == e["dir"]


def test_with_100_or_more_folders_the_number_is_three_digits():
    """L1: 100_ sorted before 11_; the width grows only past 99 folders."""
    _load_text(make_map(120, seed=9, names=[f"F{i}" for i in range(120)], per=(1, 1)))
    zf = _export()
    dirs = sorted({n.split("/")[0] for n in zf.namelist() if "/" in n})
    assert dirs[0].startswith("001_") and dirs[-1].startswith("12") and len(dirs) == len(_groups())
    assert all(re.match(r"\d{3}_", d) for d in dirs)
    assert [int(d[:3]) for d in dirs] == list(range(1, len(dirs) + 1))   # sorts in order
    e = bridge._STATE["manifest"][0]
    assert e["dir"].startswith("001_")
    _load_text(make_map(98, seed=9, names=[f"F{i}" for i in range(98)], per=(1, 1)))
    assert len(_groups()) <= 99
    dirs = {n.split("/")[0] for n in _export().namelist() if "/" in n}
    assert all(re.match(r"\d{2}_", d) and not re.match(r"\d{3}", d) for d in dirs)


@pytest.mark.parametrize("name", ["*Camp* _x_", "[a](b) <i>x</i>", "A&amp;B ~~s~~", "back\\slash `t`",
                                  "Trip #1 / A&B", "plain"])
def test_instructions_show_a_markdown_looking_folder_name_as_is(name):
    """Round 3 #6 escaped Markdown so "*Camp*" didn't read as an italic Camp;
    instructions.txt (round 4) is plain text, so the name is written as is,
    once, on its folder's line, with nothing escaped."""
    _load_text(make_map(1, seed=11, names=[name], per=(4, 4), long_notes=True))
    n = next(n for n, g in enumerate(_groups(), 1) if not g["unorganized"])
    text = _export().read("instructions.txt").decode("utf-8")
    assert _rename_to(text, n) == name
    assert "\\" not in text.replace(name, "")


def test_folder_moves_leave_the_loaded_document_alone():
    """Round 3 #8: _sync_doc copied every move into doc.folders, a second record
    of membership next to the groups. The document stays as parsed; the current
    folders are derived from the groups on demand (doc_folders)."""
    _load(BITTERROOTS)
    doc = bridge._STATE["doc"]
    before = {k: {kind: list(f.get(kind) or []) for kind in ("waypoints", "tracks", "shapes")}
              for k, f in doc.folders.items()}
    names = {k: f.get("name") for k, f in doc.folders.items()}
    mill = _key("Mill Creek Canyon")
    _move(_uids("Mill Creek Canyon"), _key("Blodgett"))
    _move(_uids("Paddling")[:1], name="Boats")
    bridge.rename_folder(_key("North Roots"), "South Roots")
    assert {k: f.get("name") for k, f in doc.folders.items()} == names
    assert {k: {kind: list(f.get(kind) or []) for kind in before[k]} for k, f in doc.folders.items()} == before
    now = bridge.doc_folders()
    assert list(now) == [g["key"] for g in _groups()] and mill not in now
    assert now[_key("Boats")]["name"] == "Boats" and now[_key("South Roots")]["name"] == "South Roots"
