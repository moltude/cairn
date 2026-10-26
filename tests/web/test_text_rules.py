"""One rule set for every text edit (UI-39), and four checks the owner asked for, in the real app.

Every edit of a name (the row's name field, Use note as name, Rename...) goes through
CairnRename.cleanName, every edit of a note (the note editor's Save, Change note...) through
cleanNote; folder names keep their own rule. An untouched value is never cleaned, the field
shows the cleaned value after a commit, an edit that cleans back to the stored value is no
edit, and nothing is said when characters go.

- Cairn sets no name length limit (onX's limits are in UI-40).
- Find and replace changes every occurrence in a field (the core's side is in
  tests/web/test_rename_core.py, test_find_and_replace_changes_every_occurrence_in_a_field).
- Leading and trailing whitespace is trimmed on every edit path named above.
- Cairn never cuts a note, and the caution mark, the dialog's flag, the export screen's
  warning and instructions.txt agree on which notes are over 512 bytes.

Maps are generated at test time (tests.bulk_rename_vectors.item_map); nothing under
tests/fixtures.
"""
from __future__ import annotations

import io
import zipfile

import pytest
from playwright.sync_api import Page, expect

from tests.bulk_rename_vectors import item_map
from tests.web.helpers import (
    BASE_URL, ROW, _clear_selection, _export_zip, _load_text, _menu_action, _open_bulk,
    _preview_rows, _save_bulk, _set, _set_mode, _tick, _type_spec,
)

GPX = "{http://www.topografix.com/GPX/1/1}"
CUT = "(over the length limit; onX will cut this note)"


# --- helpers ----------------------------------------------------------------------------


def _map(page: Page, rows, folder: str = "Text") -> None:
    _load_text(page, item_map(rows, folder), "text.json")
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)


def _uid(page: Page, name: str) -> str:
    """The uid of the one item with this name."""
    return page.evaluate("""n => {
        const m = allItems().filter(i => i.name === n);
        if (m.length !== 1) throw new Error(`${m.length} items named ${JSON.stringify(n)}`);
        return m[0].uid; }""", name)


def _item(page: Page, uid: str) -> dict:
    return page.evaluate("u => { const i = allItems().find(i => i.uid === u); return { name: i.name, desc: i.desc }; }", uid)


def _edits(page: Page) -> dict:
    return page.evaluate("JSON.parse(JSON.stringify(EDITS))")


def _changes(page: Page) -> int:
    """What Start over and the leave prompt count."""
    return page.evaluate("unexportedChanges()")


def _store_raw(page: Page, uid: str, **values) -> None:
    """Put a value in the model as if it had been loaded that way: no edit, no EDITS entry
    (the readers trim names and notes, so a padded value can't come from a file)."""
    page.evaluate("([u, v]) => { Object.assign(allItems().find(i => i.uid === u), v); renderFolders(); }",
                  [uid, values])


def _name_field(page: Page, uid: str):
    return page.locator(f'tr[data-uid="{uid}"] .name-in')


def _type_name(page: Page, uid: str, text: str, commit: str = "enter") -> None:
    """Type a whole new name in the row's field and leave it by Enter or by Tab."""
    field = _name_field(page, uid)
    field.click()
    field.fill(text)
    field.press("Enter" if commit == "enter" else "Tab")


def _open_note(page: Page, uid: str):
    page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    ta = page.locator(f'tr[data-uid="{uid}"] .desc-in')
    expect(ta).to_be_focused()
    return ta


def _save_note(page: Page, uid: str, text: str) -> None:
    ta = _open_note(page, uid)
    ta.fill(text)
    page.locator(f'tr[data-uid="{uid}"] .note-apply').click()
    expect(page.locator(".desc-in")).to_have_count(0)


def _quiet_status(page: Page) -> None:
    page.evaluate("setStatus('')")
    expect(page.locator("#status")).to_have_text("")


def _gpx_items(zf: zipfile.ZipFile) -> list:
    """(name, desc) per item of every GPX member."""
    import xml.etree.ElementTree as ET
    out = []
    for n in zf.namelist():
        if n.endswith(".gpx"):
            root = ET.fromstring(zf.read(n))
            for tag in ("wpt", "trk", "rte"):
                for el in root.iter(GPX + tag):
                    out.append((el.findtext(GPX + "name") or "", el.findtext(GPX + "desc") or ""))
    return out


def _instruction_marks(zf: zipfile.ZipFile) -> dict:
    """{item name as printed: [the mark lines under it]} from instructions.txt (names here
    are unique). The same reading as tests/test_bulk_prereqs.instruction_items."""
    out: dict = {}
    last = None
    for ln in zf.read("instructions.txt").decode("utf-8").split("\r\n"):
        if ln.startswith(" " * 16):
            out[last].append(ln.strip())
        elif ln.startswith(" " * 12):
            last = ln[12:]
            out[last] = []
    return out


def _bulk_replace_all(page: Page, uids, which: str, find: str, repl: str, match_case: bool = False) -> list:
    """Tick uids, run Find and replace in Rename... or Change note..., save; the preview rows."""
    _clear_selection(page)
    _tick(page, uids)
    _open_bulk(page, which)
    _set_mode(page, "replace")
    _type_spec(page, find=find, repl=repl, match_case=match_case)
    rows = _preview_rows(page)
    _save_bulk(page)
    return rows


# =====================================================================================
# A nameless item is announced as "Untitled"
# =====================================================================================


def test_a_nameless_items_row_controls_and_popover_are_announced_as_untitled(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "", "a note"), ("l", "", "")])
    wp, line = page.evaluate("['waypoints', 'tracks'].map(k => allItems().find(i => i.kind === k).uid)")
    # DEVIATION (A11Y-11, round 4): the note button's name starts with the words it shows,
    # "{first line}, note for Untitled" or "Add a note for Untitled" (was "Open note for Untitled").
    for uid, note_name in ((wp, "a note, note for Untitled"), (line, "Add a note for Untitled")):
        row = page.locator(f'tr[data-uid="{uid}"]')
        expect(row.get_by_role("checkbox", name="Select Untitled", exact=True)).to_have_count(1)
        expect(row.get_by_role("textbox", name="Name of Untitled", exact=True)).to_have_count(1)
        expect(row.get_by_role("button", name=note_name, exact=True)).to_have_count(1)
    page.locator(f'tr[data-uid="{wp}"] .icon-btn').click()
    expect(page.locator("#mark-pop")).to_have_attribute("aria-label", "Change icon and color for Untitled")
    page.keyboard.press("Escape")
    page.locator(f'tr[data-uid="{line}"] .line-btn').click()
    expect(page.locator("#mark-pop")).to_have_attribute("aria-label", "Change line for Untitled")
    page.keyboard.press("Escape")
    _set(page, wp, included=False)
    expect(page.locator(f'tr[data-uid="{wp}"]').get_by_role(
        "button", name="Include Untitled", exact=True)).to_have_count(1)


def test_an_empty_note_cell_shows_add_a_note_only_on_hover_or_keyboard_focus(fresh_page: Page):
    """Owner, 2026-10-25 (variant C): a missing note is blank but for the pencil until the
    pointer or the keyboard reaches the row. The button's name stays its aria-label."""
    page = fresh_page
    _map(page, [("w", "", ""), ("w", "Excluded", ""), ("w", "Ticked", ""), ("w", "Noted", "a note")])
    bare = page.evaluate("allItems()[0].uid")
    excluded, ticked = _uid(page, "Excluded"), _uid(page, "Ticked")
    _set(page, excluded, included=False)
    _tick(page, [ticked])
    text = lambda u: page.locator(f'tr[data-uid="{u}"] .note-text')   # noqa: E731
    page.mouse.move(0, 0)
    for u in (bare, excluded, ticked):
        expect(text(u)).to_have_text("Add a note")
        expect(text(u)).to_have_css("visibility", "hidden")
        page.locator(f'tr[data-uid="{u}"] .name-in').hover()
        expect(text(u)).to_have_css("visibility", "visible")
        page.mouse.move(0, 0)
        expect(text(u)).to_have_css("visibility", "hidden")
    expect(text(_uid(page, "Noted"))).to_have_css("visibility", "visible")
    # Keyboard: Tab from the name field to the note button. A name is needed to export
    # (UI-40): the nameless row's "Needs a name to export." mark is a focus stop in between.
    page.locator(f'tr[data-uid="{bare}"] .name-in').focus()
    expect(text(bare)).to_have_css("visibility", "hidden")
    page.keyboard.press("Tab")
    expect(page.locator(f'tr[data-uid="{bare}"] .name-caution')).to_be_focused()
    page.keyboard.press("Tab")
    btn = page.locator(f'tr[data-uid="{bare}"] .note-btn')
    expect(btn).to_be_focused()
    expect(text(bare)).to_have_css("visibility", "visible")
    # DEVIATION (A11Y-11, round 4): the name starts with the words shown, "Add a note".
    expect(page.locator(f'tr[data-uid="{bare}"]').get_by_role(
        "button", name="Add a note for Untitled", exact=True)).to_have_count(1)


# =====================================================================================
# Cairn sets no name length limit
# =====================================================================================


def _long_name(n: int) -> str:
    """n characters, no outer whitespace, nothing the name rule would change."""
    return ("Long " + "abcdefghij" * (n // 10 + 1))[: n - 1] + "Z"


@pytest.mark.parametrize("route", ["name-field", "bulk-rename"])
def test_a_1000_and_a_3000_character_name_are_stored_and_exported_whole(fresh_page: Page, route):
    page = fresh_page
    _map(page, [("w", "One", ""), ("l", "Two", "")])
    targets = {_uid(page, "One"): _long_name(1000), _uid(page, "Two"): _long_name(3000)}
    assert [len(n) for n in targets.values()] == [1000, 3000]
    for uid, name in targets.items():
        if route == "name-field":
            assert _name_field(page, uid).get_attribute("maxlength") is None
            _type_name(page, uid, name)
            expect(_name_field(page, uid)).to_have_value(name)
        else:
            _clear_selection(page)
            _tick(page, [uid])
            _open_bulk(page, "rename")
            _set_mode(page, "replace")
            for sel in ("#bulk-find", "#bulk-repl"):
                assert page.locator(sel).get_attribute("maxlength") is None
            _type_spec(page, find="", repl=name)
            assert [a for _u, _b, a, _f in _preview_rows(page)] == [name]
            _save_bulk(page)
        assert _item(page, uid)["name"] == name
        assert _edits(page)[uid]["name"] == name
    names = [n for n, _d in _gpx_items(_export_zip(page))]
    assert sorted(names, key=len) == sorted(targets.values(), key=len)


# =====================================================================================
# Find and replace changes every occurrence in a field
# =====================================================================================

_FAR = "Trail" + ", then switchbacks, meadow and scree" * 8 + " to the far Trail"


@pytest.mark.parametrize("find,match_case,mixed", [
    pytest.param("trail", False, "Path Path Path", id="match-case-off-changes-every-case"),
    pytest.param("Trail", True, "Path trail TRAIL", id="match-case-on-changes-only-the-exact-one"),
])
def test_find_and_replace_changes_every_match_in_a_name_and_the_export_carries_them(
        fresh_page: Page, find, match_case, mixed):
    page = fresh_page
    before = ["Ridge Trail Trail Trail", _FAR, "Trail trail TRAIL", "Camp"]
    _map(page, [("w", n, "") for n in before])
    uids = [_uid(page, n) for n in before]
    want = {
        "Ridge Trail Trail Trail": "Ridge Path Path Path",     # three in one name
        _FAR: _FAR.replace("Trail", "Path"),                   # far apart
        "Trail trail TRAIL": mixed,
        "Camp": "Camp",
    }
    rows = _bulk_replace_all(page, uids, "rename", find, "Path", match_case)
    after = {u: a for u, _b, a, _f in rows}
    assert [after[u] for u in uids] == [want[n] for n in before]
    assert [_item(page, u)["name"] for u in uids] == [want[n] for n in before]
    assert sorted(n for n, _d in _gpx_items(_export_zip(page))) == sorted(want.values())


def test_find_changes_adjacent_and_overlapping_words_left_to_right_and_exports_it(fresh_page: Page):
    """Whole-word Find (UI-39): was test_find_aa_changes_adjacent_and_overlapping_text_
    left_to_right_and_exports_it, "aa" in "aaaa" / "aaa" / "aaaaa", which Find no longer
    touches ("aaaa" stays, pinned here). Same intent with whole words."""
    page = fresh_page
    # Find "aa aa": overlapping in "aa aa aa" (left to right), adjacent twice in the five.
    want = {"aa aa": "b", "aa aa aa": "b aa", "aa aa aa aa aa": "b b aa", "aaaa": "aaaa"}
    _map(page, [("w", n, "") for n in want])
    uids = [_uid(page, n) for n in want]
    rows = _bulk_replace_all(page, uids, "rename", "aa aa", "b")
    assert {u: a for u, _b, a, _f in rows} == dict(zip(uids, want.values()))
    assert [_item(page, u)["name"] for u in uids] == list(want.values())
    assert sorted(n for n, _d in _gpx_items(_export_zip(page))) == sorted(want.values())


def test_find_and_replace_changes_every_match_on_every_line_of_a_note_and_exports_it(fresh_page: Page):
    page = fresh_page
    note = "Trail at the top\nthen the Trail down\n\nTRAIL again, trail"
    _map(page, [("w", "Camp", note), ("w", "Lake", "no match here")])
    camp, lake = _uid(page, "Camp"), _uid(page, "Lake")
    rows = _bulk_replace_all(page, [camp, lake], "note", "trail", "Path")
    want = "Path at the top\nthen the Path down\n\nPath again, Path"
    assert {u: a for u, _b, a, _f in rows}[camp] == want
    assert _item(page, camp)["desc"] == want and _item(page, lake)["desc"] == "no match here"
    assert dict(_gpx_items(_export_zip(page)))["Camp"] == want


def test_a_note_loaded_with_crlf_line_ends_matches_a_find_typed_across_lines(fresh_page: Page):
    """A Find typed in a textarea only ever holds "\\n". Every reader makes a loaded note's
    CRLF and CR "\\n" (ParsedFeature's clean_notes), so a Find across a line break matches a
    note that came from a CRLF file. This pins that: if a reader ever kept the CR, the
    Find would silently match nothing."""
    page = fresh_page
    _map(page, [("w", "Camp", "up top\r\nTrail down\rup top\r\nTrail down\r\n")])
    uid = _uid(page, "Camp")
    assert _item(page, uid)["desc"] == "up top\nTrail down\nup top\nTrail down"
    rows = _bulk_replace_all(page, [uid], "note", "top\nTrail", "Path")
    assert [a for _u, _b, a, _f in rows] == ["up Path down\nup Path down"]
    assert _item(page, uid)["desc"] == "up Path down\nup Path down"


# =====================================================================================
# Leading and trailing whitespace is trimmed, on every edit path (UI-39, one rule set)
# =====================================================================================


@pytest.mark.parametrize("typed,stored,commit", [
    pytest.param("  \tRidge camp \t ", "Ridge camp", "enter", id="outer-spaces-and-tabs-by-enter"),
    pytest.param("  Ridge camp  ", "Ridge camp", "tab", id="outer-spaces-by-leaving-the-field"),
    pytest.param("Ridge\t\tcamp", "Ridge camp", "enter", id="inner-tabs-become-one-space"),
    pytest.param("Ridge  camp", "Ridge  camp", "enter", id="inner-double-space-is-kept"),
])
def test_the_name_field_trims_what_it_saves_and_shows_what_it_stored(fresh_page: Page, typed, stored, commit):
    page = fresh_page
    _map(page, [("w", "Old name", "")])
    uid = _uid(page, "Old name")
    _type_name(page, uid, typed, commit)
    assert _item(page, uid)["name"] == stored
    assert _edits(page)[uid] == {"name": stored}
    expect(_name_field(page, uid)).to_have_value(stored)


def test_a_line_break_pasted_into_the_name_field_becomes_a_space_and_the_ends_are_trimmed(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Old name", "")])
    uid = _uid(page, "Old name")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE_URL)
    page.evaluate("t => navigator.clipboard.writeText(t)", "\r\n Ridge\r\ncamp \n")
    field = _name_field(page, uid)
    field.click()
    field.press("ControlOrMeta+a")
    field.press("ControlOrMeta+v")
    field.press("Enter")
    assert _item(page, uid)["name"] == "Ridge camp"
    expect(field).to_have_value("Ridge camp")


def test_the_note_editor_trims_outer_blank_lines_and_spaces_and_keeps_inner_ones(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp", "old note")])
    uid = _uid(page, "Camp")
    _save_note(page, uid, "\n\n  first line\n\n  second line, indented  \n \n")
    want = "first line\n\n  second line, indented"
    assert _item(page, uid)["desc"] == want
    assert _edits(page)[uid] == {"desc": want}
    expect(page.locator(f'tr[data-uid="{uid}"] .note-text')).to_have_text("first line")
    # Opened again, the editor shows what was stored.
    assert _open_note(page, uid).input_value() == want
    page.keyboard.press("Escape")
    assert dict(_gpx_items(_export_zip(page)))["Camp"] == want


def test_use_note_as_name_cleans_the_note_like_a_name(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "A", "will be set below"), ("w", "B", "\x01Camp\x02 site"), ("w", "C", ""),
                ("w", "Same", "Same")])
    a, b, c, same = (_uid(page, n) for n in ("A", "B", "C", "Same"))
    _set(page, a, desc="  Line one \n\tLine two\t\n")
    _tick(page, [a, b, c, same])
    _menu_action(page, "#bulk-desc")
    assert [_item(page, u)["name"] for u in (a, b, c, same)] == ["Line one Line two", "Camp site", "C", "Same"]
    edits = _edits(page)
    assert edits[a]["name"] == "Line one Line two" and edits[b] == {"name": "Camp site"}
    # A blank note leaves its row alone, and so does a name that is the note already: no edit.
    assert c not in edits and same not in edits
    assert _changes(page) == 2


def test_bulk_rename_trims_what_it_saves(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp", ""), ("l", "Lake", "")])
    uids = [_uid(page, "Camp"), _uid(page, "Lake")]
    rows = _bulk_replace_all(page, uids, "rename", "", "  Ridge\t camp \t ")
    assert [a for _u, _b, a, _f in rows] == ["Ridge camp", "Ridge camp"]
    assert [_item(page, u)["name"] for u in uids] == ["Ridge camp", "Ridge camp"]
    assert [n for n, _d in _gpx_items(_export_zip(page))] == ["Ridge camp", "Ridge camp"]


def test_change_note_trims_outer_whitespace_and_keeps_inner_line_breaks(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp", "old"), ("l", "Lake", "")])
    uids = [_uid(page, "Camp"), _uid(page, "Lake")]
    _tick(page, uids)
    _open_bulk(page, "note")
    _set_mode(page, "set")
    _type_spec(page, text="\n\n  Hello\n\n  world  \n \n")
    want = "Hello\n\n  world"
    assert [a for _u, _b, a, _f in _preview_rows(page)] == [want, want]
    _save_bulk(page)
    assert [_item(page, u)["desc"] for u in uids] == [want, want]
    assert [d for _n, d in _gpx_items(_export_zip(page))] == [want, want]


# --- the no-op rule: an untouched value is never cleaned --------------------------------


@pytest.mark.parametrize("dirty", [
    pytest.param("\x01Camp", id="a-forbidden-character-as-loaded"),
    pytest.param("  Padded  ", id="outer-spaces"),
])
def test_focus_enter_and_blur_on_an_untouched_dirty_name_is_no_edit(fresh_page: Page, dirty):
    page = fresh_page
    _map(page, [("w", "\x01Camp" if dirty.startswith("\x01") else "Plain", ""), ("w", "Next", "")])
    uid = page.evaluate("allItems()[0].uid")
    if not dirty.startswith("\x01"):
        _store_raw(page, uid, name=dirty)
    field = _name_field(page, uid)
    expect(field).to_have_value(dirty)
    field.click()
    field.press("Enter")
    field.press("Tab")
    field.focus()
    page.locator("#filter").click()
    assert _item(page, uid)["name"] == dirty
    assert _edits(page) == {} and _changes(page) == 0
    expect(field).to_have_value(dirty)


def test_a_name_edit_that_cleans_back_to_the_stored_name_is_no_edit(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp", "")])
    uid = _uid(page, "Camp")
    _type_name(page, uid, " Camp \t")
    expect(_name_field(page, uid)).to_have_value("Camp")
    assert _item(page, uid)["name"] == "Camp"
    assert _edits(page) == {} and _changes(page) == 0


@pytest.mark.parametrize("dirty", [
    pytest.param("\x01Note", id="a-forbidden-character-as-loaded"),
    pytest.param("  Note \n\n", id="outer-spaces-and-blank-lines"),
])
@pytest.mark.parametrize("how", ["save-button", "ctrl-enter"])
def test_saving_an_untouched_dirty_note_is_no_edit(fresh_page: Page, dirty, how):
    page = fresh_page
    _map(page, [("w", "Camp", "\x01Note" if dirty.startswith("\x01") else "Note")])
    uid = _uid(page, "Camp")
    if not dirty.startswith("\x01"):
        _store_raw(page, uid, desc=dirty)
    ta = _open_note(page, uid)
    assert ta.input_value() == dirty
    if how == "save-button":
        page.locator(f'tr[data-uid="{uid}"] .note-apply').click()
    else:
        ta.press("ControlOrMeta+Enter")
    expect(page.locator(".desc-in")).to_have_count(0)
    assert _item(page, uid)["desc"] == dirty
    assert _edits(page) == {} and _changes(page) == 0


def test_a_note_draft_that_only_adds_outer_whitespace_is_no_edit_and_export_does_not_ask(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp", "Note")])
    uid = _uid(page, "Camp")
    _open_note(page, uid).fill("\n  Note  \n\n")
    assert _changes(page) == 0
    names = [n for n, _d in _gpx_items(_export_zip(page))]   # no "Save your note?" first
    assert names == ["Camp"]
    expect(page.locator("#confirm")).to_be_hidden()
    assert _item(page, uid)["desc"] == "Note" and _edits(page) == {}


# --- characters XML forbids, typed: dropped, nothing said -------------------------------


def test_a_forbidden_character_typed_in_the_name_field_is_dropped_silently(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Old", "")])
    uid = _uid(page, "Old")
    _quiet_status(page)
    _type_name(page, uid, "Ca\x01mp\x1f site￾")
    assert _item(page, uid)["name"] == "Camp site"
    expect(_name_field(page, uid)).to_have_value("Camp site")
    expect(page.locator("#status")).to_have_text("")


def test_a_forbidden_character_typed_in_the_note_editor_is_dropped_silently(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp", "old")])
    uid = _uid(page, "Camp")
    _quiet_status(page)
    _save_note(page, uid, "Ca\x01mp\nline\x0b two￾")
    assert _item(page, uid)["desc"] == "Camp\nline two"
    expect(page.locator("#status")).to_have_text("")


# =====================================================================================
# Cairn never cuts a note; the four places agree on which are over 512 bytes
# =====================================================================================

LONG_NOTES = {
    "N512": "a" * 512,
    "N513": "a" * 513,
    "N600": "a" * 600,
    "E512": "a" * 508 + "\U0001F600",      # ends in a 4-byte emoji: 512 bytes
    "E513": "a" * 509 + "\U0001F600",      # 513 bytes, the emoji straddles the cut
}
OVER = {"N513", "N600", "E513"}


@pytest.mark.parametrize("route", ["note-editor", "change-note"])
def test_notes_over_512_bytes_export_whole_and_every_place_marks_the_same_ones(fresh_page: Page, route):
    assert {n: len(v.encode("utf-8")) for n, v in LONG_NOTES.items()} == {
        "N512": 512, "N513": 513, "N600": 600, "E512": 512, "E513": 513}
    page = fresh_page
    _map(page, [("w", n, "x") for n in LONG_NOTES])
    uids = {n: _uid(page, n) for n in LONG_NOTES}
    flagged = set()
    for name, note in LONG_NOTES.items():
        uid = uids[name]
        if route == "note-editor":
            _save_note(page, uid, note)
        else:
            _clear_selection(page)
            _tick(page, [uid])
            _open_bulk(page, "note")
            _set_mode(page, "set")
            _type_spec(page, text=note)
            ((_u, _b, after, flags),) = _preview_rows(page)
            assert after == note
            if "note-over-limit" in flags:
                flagged.add(name)
            _save_bulk(page)
        assert _item(page, uid)["desc"] == note
    if route == "change-note":
        assert flagged == OVER
    marked = {n for n, u in uids.items() if page.locator(f'tr[data-uid="{u}"] .caution').count()}
    assert marked == OVER
    zf = _export_zip(page)
    assert dict(_gpx_items(zf)) == LONG_NOTES                    # every note whole
    warn = page.locator("#runbook .note.warn", has_text="over the length limit")
    for name in LONG_NOTES:
        (expect(warn).to_contain_text if name in OVER else expect(warn).not_to_contain_text)(f"“{name}”")
    marks = _instruction_marks(zf)
    assert {n for n, m in marks.items() if CUT in m} == OVER
    assert set(marks) >= set(LONG_NOTES)
