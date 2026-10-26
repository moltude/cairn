"""onX's limits on names and the name an export needs, in the browser (UI-40's
L1 and N1, 2026-10-25). The bridge side is tests/test_onx_limits.py.

L1: a caution mark beside an included item's name over onX's 255 UTF-8 bytes, and
beside a folder's name in its header over onX's 50 characters; the export screen lists
them in the long-note warning's words; instructions.txt marks them. Warn, never cut.
N1: an included item with a blank name is marked "Needs a name to export."; Export asks
"N items need a name" (Cancel · Name them Untitled) after the merge offer and "Save your
note?"; Name them Untitled names each one and exports; Cancel says how many and goes to
the first one.
"""
from __future__ import annotations

import io
import json
import re
import zipfile

from playwright.sync_api import Page, expect

from tests.hardening_maps import _folder, _line, _poly, _pt
from tests.web.helpers import (
    NAME_IT, NAME_THEM, ROW, _click_export, _export_zip, _gpx_names, _load_text, _names_confirm_open, _set,
    export_zip_bytes,
)

NEEDS = "Needs a name to export."
NAME_CUT = "(over the length limit; onX will cut this name)"
FOLDER_CUT = "(over the length limit; onX will cut this folder name)"


def _geojson(folders: dict) -> str:
    """{folder name: [(kind, name, note), ...]} as a CalTopo GeoJSON map."""
    feats, i = [], 0
    for k, (fname, rows) in enumerate(folders.items()):
        feats.append(_folder(f"f{k}", fname))
        for kind, name, note in rows:
            i += 1
            f = _pt(i, f"f{k}") if kind == "w" else _line(i, f"f{k}") if kind == "l" else _poly(i, f"f{k}", holes=0)
            f["properties"].update(title=name, description=note)
            feats.append(f)
    return json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False)


def _map(page: Page, folders: dict) -> dict:
    """Load the map; {name: uid} (names unique in these tests; "" for a blank one)."""
    _load_text(page, _geojson(folders), "limits.json")
    return {i["name"]: i["uid"] for i in page.evaluate("allItems().map(i => ({name: i.name, uid: i.uid}))")}


def _name_mark(page: Page, uid: str):
    return page.locator(f'tr[data-uid="{uid}"] .name-caution')


def _folder_mark(page: Page, name: str):
    return page.locator("#folders section.folder", has=page.get_by_role(
        "button", name=name, exact=True)).locator(".folder-head .folder-caution")


def _zip_now(page: Page) -> zipfile.ZipFile:
    """The zip the last export left in the page (ZIP)."""
    data = page.evaluate("async () => Array.from(new Uint8Array(await ZIP.arrayBuffer()))")
    return zipfile.ZipFile(io.BytesIO(bytes(data)))


def _long(n: int, unit: str = "x") -> str:
    return "Long " + unit * (n - 5)


def _sentence(n: int) -> str:
    return f"onX imports only the first 255 bytes of a name. About {n} character{'s' if n != 1 else ''} will be cut."


def _folder_sentence(n: int) -> str:
    return f"onX keeps only the first 50 characters of a folder name. About {n} character{'s' if n != 1 else ''} will be cut."


def test_the_limits_are_read_from_the_bridge_at_boot(fresh_page: Page):
    assert fresh_page.evaluate("[NOTE_LIMIT, NAME_LIMIT, FOLDER_NAME_LIMIT]") == [512, 255, 50]


# --- L1: names over 255 bytes ------------------------------------------------------


def test_a_name_over_255_bytes_gets_a_caution_beside_it_measured_in_bytes(fresh_page: Page):
    page = fresh_page
    names = {
        "ascii-255": _long(255),                                 # 255 bytes: no mark
        "ascii-256": _long(256),                                 # 1 character cut
        "ascii-300": _long(300),                                 # 45 cut
        "accented-128": "é" * 128,                          # 256 bytes, 128 characters: 1 cut
        "emoji-straddling": "x" * 252 + "\U0001F525",            # 256 bytes: the emoji goes
        "cjk-86": "山" * 86,                                 # 258 bytes: 1 cut
    }
    want = {"ascii-255": None, "ascii-256": 1, "ascii-300": 45, "accented-128": 1,
            "emoji-straddling": 1, "cjk-86": 1}
    uids = _map(page, {"Trip": [("w", n, "") for n in names.values()]})
    for label, name in names.items():
        mark = _name_mark(page, uids[name])
        if want[label] is None:
            expect(mark).to_have_count(0)
        else:
            expect(mark).to_have_attribute("aria-label", _sentence(want[label]))
    # Measured on the name as stored, the screen and instructions.txt agree.
    zf = _export_zip(page)
    lines = zf.read("instructions.txt").decode("utf-8").split("\r\n")
    marked = {lines[k - 1].strip() for k, ln in enumerate(lines) if ln.strip() == NAME_CUT}
    assert marked == {n for label, n in names.items() if want[label]}
    assert sorted(_gpx_names(zf)) == sorted(names.values())          # every name whole: never cut


def test_the_name_caution_follows_edits_and_exclusion(fresh_page: Page):
    page = fresh_page
    long = _long(300)
    uids = _map(page, {"Trip": [("w", long, ""), ("l", "Line", "")]})
    u = uids[long]
    expect(_name_mark(page, u)).to_have_count(1)
    _set(page, u, included=False)                               # not exported: no mark
    expect(_name_mark(page, u)).to_have_count(0)
    _set(page, u, included=True)
    expect(_name_mark(page, u)).to_have_count(1)
    field = page.locator(f'tr[data-uid="{u}"] .name-in')
    field.fill("Short now")
    field.press("Enter")
    expect(_name_mark(page, u)).to_have_count(0)
    _set(page, uids["Line"], name="y" * 256)                    # a line too
    expect(_name_mark(page, uids["Line"])).to_have_attribute("aria-label", _sentence(1))


def test_the_name_caution_shows_its_sentence_on_hover_and_keyboard_focus(fresh_page: Page):
    page = fresh_page
    long = _long(260)
    uids = _map(page, {"Trip": [("w", long, "")]})
    mark = _name_mark(page, uids[long])
    mark.hover()
    expect(page.locator("#tip")).to_have_text(_sentence(5))
    page.mouse.move(0, 0)
    page.wait_for_timeout(350)
    mark.focus()
    expect(page.locator("#tip")).to_have_text(_sentence(5))


# --- L1: folder names over 50 characters --------------------------------------------


def test_a_folder_name_over_50_characters_gets_a_caution_in_its_header(fresh_page: Page):
    page = fresh_page
    folders = {
        "f" * 50: None,                                          # exactly 50: none
        "g" * 51: 1,
        "h" * 70: 20,
        "x" * 49 + "\U0001F525": 1,                              # 51 characters as onX's field counts them
        "\U0001F525" * 25: None,                                 # 50 as it counts them
    }
    _map(page, {name: [("w", f"Item {k}", "")] for k, name in enumerate(folders)})
    for name, cut in folders.items():
        mark = _folder_mark(page, name)
        if cut is None:
            expect(mark).to_have_count(0)
        else:
            expect(mark).to_have_attribute("aria-label", _folder_sentence(cut))
    mark = _folder_mark(page, "h" * 70)
    mark.hover()
    expect(page.locator("#tip")).to_have_text(_folder_sentence(20))


def test_a_folder_that_exports_nothing_gets_no_folder_caution(fresh_page: Page):
    page = fresh_page
    uids = _map(page, {"q" * 60: [("w", "Only", "")], "Short": [("w", "Kept", "")]})
    expect(_folder_mark(page, "q" * 60)).to_have_count(1)
    _set(page, uids["Only"], included=False)
    expect(_folder_mark(page, "q" * 60)).to_have_count(0)


def test_renaming_a_folder_under_50_clears_its_caution(fresh_page: Page):
    page = fresh_page
    _map(page, {"r" * 55: [("w", "A", "")], "Short": [("w", "B", "")]})
    expect(_folder_mark(page, "r" * 55)).to_have_count(1)
    page.get_by_role("button", name="r" * 55, exact=True).click()
    inp = page.locator(".folder-head .folder-name-in")
    inp.fill("Ridge")
    inp.press("Enter")
    expect(page.locator(".folder-caution")).to_have_count(0)


# --- the export screen and instructions.txt -----------------------------------------


def test_the_export_screen_lists_long_names_and_long_folder_names(fresh_page: Page):
    page = fresh_page
    one = "Camp " + "z" * 300
    _map(page, {"Ridge camps and the long approach from the north trailhead": [("w", one, "")],
                "Short": [("w", "Fine", "")]})
    _click_export(page)
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    warns = page.locator("#runbook .note.warn")
    expect(warns).to_have_count(2)
    expect(warns.nth(0)).to_have_text(
        "Name “Camp " + "z" * 42 + "…” is over the length limit and will be truncated by onX.")
    expect(warns.nth(1)).to_have_text(
        "Folder name “Ridge camps and the long approach from the nort…” is over the length "
        "limit and will be truncated by onX.")


def test_the_export_screen_says_names_for_several_and_and_n_more(fresh_page: Page):
    page = fresh_page
    longs = [f"N{k:02d} " + "w" * 260 for k in range(1, 11)]
    folders = {f"F{k} " + "v" * 60: [("w", n, "")] for k, n in enumerate(longs[:2])}
    folders["Rest"] = [("w", n, "") for n in longs[2:]]
    _map(page, folders)
    _click_export(page)
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    manifest_order = [n for e in page.evaluate("MANIFEST") for n, _b in e["long_names"]]
    shown = [f"“{n[:47]}…”" for n in manifest_order]
    expect(page.locator("#runbook .note.warn", has_text=re.compile(r"^Names "))).to_have_text(
        f"Names {', '.join(shown[:8])} and 2 more are over the length limit and will be truncated by onX.")
    folders_shown = [f"“{e['folder'][:47]}…”" for e in page.evaluate("MANIFEST") if e["long_folder"]]
    assert len(folders_shown) == 2
    expect(page.locator("#runbook .note.warn", has_text="Folder names")).to_have_text(
        f"Folder names {', '.join(folders_shown)} are over the length limit and will be truncated by onX.")


def test_marks_on_screen_match_the_export_warning_and_instructions_txt(fresh_page: Page):
    page = fresh_page
    uids = _map(page, {"Trail notes for the whole season, every day of it all": [("w", "a" * 256, ""),
                                                                              ("w", "Fine", "")],
                       "Short": [("l", "b" * 300, "n" * 600), ("w", "Also fine", "")]})
    marked = {n for n, u in uids.items() if _name_mark(page, u).count()}
    assert marked == {"a" * 256, "b" * 300}
    zb = export_zip_bytes(page)
    listed = {n for e in page.evaluate("MANIFEST") for n, _b in e["long_names"]}
    assert listed == marked
    lines = zipfile.ZipFile(io.BytesIO(zb)).read("instructions.txt").decode("utf-8").split("\r\n")
    under = {lines[k - 1].strip() for k, ln in enumerate(lines) if ln.strip() == NAME_CUT}
    assert under == marked
    # The folder: 53 characters, marked under its rename line.
    at = next(k for k, ln in enumerate(lines) if ln.endswith("rename to: Trail notes for the whole season, every day of it all"))
    assert lines[at + 1] == "    " + FOLDER_CUT
    # The line with both: the name's mark first, then the note's.
    k = lines.index("            " + "b" * 300)
    assert [lines[k + 1].strip(), lines[k + 2].strip()] == [NAME_CUT, "(over the length limit; onX will cut this note)"]


# --- N1: a name is required to export -----------------------------------------------


def test_a_blank_name_is_marked_needs_a_name_and_an_excluded_one_is_not(fresh_page: Page):
    page = fresh_page
    uids = _map(page, {"Trip": [("w", "", ""), ("w", "Named", "")]})
    blank = uids[""]
    expect(_name_mark(page, blank)).to_have_attribute("aria-label", NEEDS)
    expect(_name_mark(page, uids["Named"])).to_have_count(0)
    _set(page, blank, included=False)
    expect(_name_mark(page, blank)).to_have_count(0)
    _set(page, blank, included=True)
    field = page.locator(f'tr[data-uid="{blank}"] .name-in')
    field.fill("Spring")
    field.press("Enter")
    expect(_name_mark(page, blank)).to_have_count(0)
    # Emptying a name while editing is allowed; the mark comes back.
    field.fill("   ")
    field.press("Enter")
    assert page.evaluate(f"allItems().find(i => i.uid === {json.dumps(blank)}).name") == ""
    expect(_name_mark(page, blank)).to_have_attribute("aria-label", NEEDS)
    expect(page.locator("#status")).not_to_have_class(re.compile(r"\berr\b"))


def test_the_needs_a_name_mark_trims_as_the_export_does(fresh_page: Page):
    """A BOM-only name is not blank in the file, like a ZWSP-only one: no mark, and Export
    doesn't ask about it. A NEL-only one is (Python's strip() takes U+0085)."""
    page = fresh_page
    uids = _map(page, {"Trip": [("w", "\ufeff", ""), ("w", "\u200b", ""), ("w", "Camp", "")]})
    expect(_name_mark(page, uids["\ufeff"])).to_have_count(0)
    expect(_name_mark(page, uids["\u200b"])).to_have_count(0)
    field = page.locator(f'tr[data-uid="{uids["Camp"]}"] .name-in')
    field.fill("\x85")
    field.press("Enter")
    expect(_name_mark(page, uids["Camp"])).to_have_attribute("aria-label", NEEDS)


def test_bitterroots_seven_blank_names_ask_first_and_name_them_untitled_exports(loaded: Page):
    page = loaded
    blank = page.evaluate("allItems().filter(i => i.name === '').map(i => i.uid)")
    assert len(blank) == 7
    assert sorted(page.locator(".name-caution").evaluate_all("els => els.map(e => e.closest('tr').dataset.uid)")) == sorted(blank)
    page.evaluate("window.__cairnExported = false")
    page.click("#export")
    dlg = page.locator("#confirm")
    expect(dlg).to_be_visible()
    expect(page.locator("#confirm-title")).to_have_text("7 items need a name")
    expect(page.locator("#confirm-body")).to_have_text("")
    expect(page.locator("#confirm-actions button")).to_have_text(["Cancel", NAME_THEM])   # safe first
    expect(page.locator("#confirm-actions button").first).to_be_focused()
    assert page.evaluate("window.__cairnExported") is False
    page.click(f"#confirm-actions button:text-is('{NAME_THEM}')")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    assert page.evaluate("window.__cairnExported") is True
    # Ordinary edits: "Untitled" stored and in EDITS, written by this export.
    got = page.evaluate("uids => uids.map(u => [allItems().find(i => i.uid === u).name, (EDITS[u] || {}).name])", blank)
    assert got == [["Untitled", "Untitled"]] * 7
    assert page.evaluate("unexportedChanges()") == 0
    names = _gpx_names(_zip_now(page))
    assert "" not in names and names.count("Untitled") == 7
    page.click("#back")
    expect(page.locator(".name-caution")).to_have_count(0)
    page.click("#export")                                       # nothing left to ask
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)


def test_name_them_untitled_counts_as_unexported_changes_until_written(loaded: Page):
    """The edits land before the export; if the export then fails they are still there
    to count (here: checked by naming without exporting, through the same path)."""
    page = loaded
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("7 items need a name")
    page.keyboard.press("Escape")
    assert page.evaluate("unexportedChanges()") == 0
    page.click("#export")
    page.click(f"#confirm-actions button:text-is('{NAME_THEM}')")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    page.click("#back")
    assert page.evaluate("Object.values(EDITS).filter(e => e.name === 'Untitled').length") == 7
    assert page.evaluate("unexportedChanges()") == 0


def test_cancel_says_how_many_need_a_name_and_focuses_the_first_one(loaded: Page):
    page = loaded
    page.click("#export")
    page.click("#confirm-actions button:text-is('Cancel')")
    expect(page.locator("#confirm")).to_be_hidden()
    st = page.locator("#status")
    expect(st).to_have_text("7 items need a name.")
    expect(st).to_have_class(re.compile(r"\berr\b"))
    assert page.evaluate("document.body.dataset.stage") == "edit" and page.evaluate("MANIFEST") is None
    first = page.locator(f"{ROW}:has(.name-caution) .name-in").first
    expect(first).to_be_focused()
    assert page.evaluate("Object.keys(EDITS).length") == 0             # nothing named
    # Esc is Cancel.
    page.click("#export")
    page.keyboard.press("Escape")
    expect(page.locator("#confirm")).to_be_hidden()
    expect(st).to_have_text("7 items need a name.")
    expect(first).to_be_focused()


def test_one_blank_name_is_singular_everywhere(fresh_page: Page):
    page = fresh_page
    uids = _map(page, {"Trip": [("w", "", ""), ("w", "Named", "")]})
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("1 item needs a name")
    # One item: "Name it Untitled" (owner 2026-10-26, accepting the suggestion).
    expect(page.locator("#confirm-actions button")).to_have_text(["Cancel", NAME_IT])
    page.click("#confirm-actions button:text-is('Cancel')")
    expect(page.locator("#status")).to_have_text("1 item needs a name.")
    expect(page.locator(f'tr[data-uid="{uids[""]}"] .name-in')).to_be_focused()


def test_cancel_shows_a_blank_name_that_a_filter_or_a_collapsed_folder_hid(loaded: Page):
    page = loaded
    # A search that hides every blank-named row (they are all in Unorganized).
    page.fill("#filter", "Blodgett")
    expect(page.locator(f"{ROW}:has(.name-caution)")).to_have_count(0)
    page.click("#export")
    page.click("#confirm-actions button:text-is('Cancel')")
    expect(page.locator("#filter")).to_have_value("")
    field = page.locator(f"{ROW}:has(.name-caution) .name-in").first
    expect(field).to_be_focused()
    # A collapsed folder.
    unorg = page.evaluate("DATA.groups.find(g => g.unorganized).key")
    page.evaluate("k => { COLLAPSED.add(k); renderFolders(); }", unorg)
    expect(page.locator(f"{ROW}:has(.name-caution) .name-in").first).to_be_hidden()
    page.click("#export")
    page.click("#confirm-actions button:text-is('Cancel')")
    assert page.evaluate("k => COLLAPSED.has(k)", unorg) is False
    expect(page.locator(f"{ROW}:has(.name-caution) .name-in").first).to_be_focused()


def test_cancel_keeps_a_filter_that_leaves_one_blank_name_on_screen(fresh_page: Page):
    page = fresh_page
    _map(page, {"North": [("w", "", "north spring")], "South": [("w", "", "south spring")]})
    page.fill("#filter", "south")
    page.click("#export")
    page.click("#confirm-actions button:text-is('Cancel')")
    expect(page.locator("#filter")).to_have_value("south")
    expect(page.locator("#status")).to_have_text("2 items need a name.")
    focused = page.evaluate("document.activeElement.closest('tr') && document.activeElement.closest('tr').dataset.uid")
    assert page.evaluate(f"allItems().find(i => i.uid === {json.dumps(focused)}).desc") == "south spring"


def test_a_blank_name_on_an_item_with_no_coordinates_is_not_asked_about(fresh_page: Page):
    page = fresh_page
    feats = [_folder("f0", "Trip"), _pt(1, "f0", title="Keep"),
             {"type": "Feature", "id": "nc", "geometry": {"type": "Point", "coordinates": []},
              "properties": {"title": "", "class": "Marker", "folderId": "f0"}}]
    _load_text(page, json.dumps({"type": "FeatureCollection", "features": feats}), "nc.json")
    nc = page.evaluate("allItems().find(i => i.no_coords).uid")
    expect(_name_mark(page, nc)).to_have_count(0)
    expect(page.locator(f'tr[data-uid="{nc}"] .note-cell .caution')).to_have_attribute(
        "aria-label", "Won't export: it has no coordinates.")
    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)


def test_save_your_note_comes_first_then_the_names(loaded: Page):
    page = loaded
    uid = page.evaluate("allItems().find(i => i.kind === 'waypoints' && i.name).uid")
    page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    page.locator(".desc-in").first.fill("NOTE_THEN_NAMES")
    page.evaluate("window.__cairnExported = false")
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("Save your note?")
    page.click("#confirm-actions button:text-is('Save')")
    expect(page.locator("#confirm-title")).to_have_text("7 items need a name")
    assert page.evaluate(f"allItems().find(i => i.uid === {json.dumps(uid)}).desc") == "NOTE_THEN_NAMES"
    page.click(f"#confirm-actions button:text-is('{NAME_THEM}')")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    # Keep editing stops before the names are asked about.
    page.click("#back")
    _set(page, page.evaluate("allItems().find(i => i.name === 'Untitled').uid"), name="")
    page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    page.locator(".desc-in").first.fill("AGAIN")
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("Save your note?")
    page.click("#confirm-actions button:text-is('Keep editing')")
    expect(page.locator("#confirm")).to_be_hidden()
    assert not _names_confirm_open(page)


def test_a_taken_folder_name_offers_the_merge_before_the_names(loaded: Page):
    page = loaded
    page.locator("#folders section.folder", has=page.get_by_role(
        "button", name="North Roots", exact=True)).locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Paddling")
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("“Paddling” already exists")
    page.click("#confirm-actions button:text-is('Cancel')")
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("7 items need a name")


def test_no_blank_name_ever_reaches_a_gpx_from_the_browser(loaded: Page):
    page = loaded
    zb = export_zip_bytes(page)                    # presses Name them Untitled
    names = _gpx_names(zipfile.ZipFile(io.BytesIO(zb)))
    assert len(names) == 177 and not [n for n in names if not n.strip()]


def test_the_names_confirm_works_under_the_enforced_csp(csp_page: Page):
    """No page-JS evaluation here: DOM only, as under the production CSP."""
    page = csp_page
    _load_text(page, _geojson({"Trip": [("w", "", ""), ("l", "", ""), ("w", "Named", "")]}), "csp.json")
    expect(page.locator(".name-caution")).to_have_count(2)
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("2 items need a name")
    page.click(f"#confirm-actions button:text-is('{NAME_THEM}')")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
