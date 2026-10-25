"""Layer E: More > Rename... and Change note... end to end, in the real app.

docs/plans/BULK_RENAME.md section 5 (every E and E-csp id) against the frozen DOM
contract of docs/plans/BULK_RENAME_PROGRESS.md section 2: #bulk-rename / #bulk-note,
#mark-dialog[data-bulk][data-preview-seq], .mode-tog[data-mode], #bulk-text, #bulk-find,
#bulk-repl, #bulk-match-case, .na-row[data-uid][data-flags] with .na-before / .na-after
(.is-placeholder for a greyed "Untitled") and .na-flag, #bulk-summary, #bulk-apply,
.bulk-cancel, and #status "Changed N items.".

Waits are on data-preview-seq (tests/web/helpers.py _type_spec, _set_mode), never on a
fixed sleep; the status is read within its 8 s. Flags compare as sets (>=) unless a
test is about exclusivity. Maps are generated at test time (bulk_rename_vectors.item_map).

Until the dialog exists (Track B), every test here skips: the module fixture below
looks for #bulk-rename in the served index.html.
"""
from __future__ import annotations

import base64
import io
import re
import urllib.request
import zipfile
from collections import Counter

import pytest
from playwright.sync_api import Page, expect

from tests.bulk_rename_vectors import CAMPSITES, item_map
from tests.naughty_strings import NAUGHTY_TEXTS
from tests.web.helpers import (
    BASE_URL, FIXTURE, ROW, _export_zip, _gpx_descs, _gpx_names, _load_text, _open_bulk,
    _open_changed_waypoint_note, _preview_rows, _preview_seq, _save_bulk, _select_all_shown,
    _set, _set_mode, _status_count, _tick, _type_slowly, _type_spec, _wait_preview_past,
)

GPX = "{http://www.topografix.com/GPX/1/1}"
TAG_KIND = {"wpt": "waypoints", "trk": "tracks", "rte": "shapes"}


def _long_note_sentence(n_cut: int) -> str:
    word = "character" if n_cut == 1 else "characters"
    return f"onX imports only the first 512 bytes of a note. About {n_cut:,} {word} will be cut."


@pytest.fixture(scope="module", autouse=True)
def _rename_dialog_is_built(_require_server):
    with urllib.request.urlopen(f"{BASE_URL}/index.html", timeout=5) as r:
        html = r.read().decode("utf-8")
    if not re.search(r"""id=["']bulk-rename["']""", html):
        pytest.skip("Rename... is not built yet (Track B): no #bulk-rename in index.html")


# --- helpers ------------------------------------------------------------------------


def _map(page: Page, rows, folder: str = "Bulk") -> None:
    _load_text(page, item_map(rows, folder), "bulk.json")
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)


def _uids(page: Page, *names) -> list:
    """The uid of the one item with each name (a missing or repeated name throws)."""
    return page.evaluate("""ns => ns.map(n => {
        const m = allItems().filter(i => i.name === n);
        if (m.length !== 1) throw new Error(`${m.length} items named ${JSON.stringify(n)}`);
        return m[0].uid; })""", list(names))


def _all_uids(page: Page) -> list:
    return page.evaluate("allItems().map(i => i.uid)")


def _names(page: Page, uids) -> list:
    return page.evaluate("us => us.map(u => allItems().find(i => i.uid === u).name)", list(uids))


def _descs(page: Page, uids) -> list:
    return page.evaluate("us => us.map(u => allItems().find(i => i.uid === u).desc)", list(uids))


def _edits(page: Page) -> dict:
    return page.evaluate("JSON.parse(JSON.stringify(EDITS))")


def _summary(page: Page) -> str:
    return page.locator("#bulk-summary").text_content().strip()


def _title(page: Page) -> str:
    return page.locator("#mark-dialog h2").text_content().strip()


def _row_order(page: Page) -> list:
    """Item names in the order the list shows them."""
    return page.locator(ROW).evaluate_all("rs => rs.map(r => r.querySelector('.name-in').value)")


def _sort_folder(page: Page, folder: str = "Bulk") -> None:
    sec = page.locator("section.folder", has=page.locator(
        ".folder-name", has_text=re.compile(rf"^{re.escape(folder)}$")))
    sec.locator(".sort-btn").click()
    expect(sec.locator("th.name-th")).to_have_attribute("aria-sort", "ascending")


def _dialog_open(page: Page) -> bool:
    return page.locator("#mark-dialog[data-bulk]").count() == 1 and page.locator("#mark-modal").is_visible()


def _zip_now(page: Page) -> zipfile.ZipFile:
    """The ZIP the app holds now (after a programmatic doExport)."""
    b64 = page.evaluate("async () => { const u = new Uint8Array(await ZIP.arrayBuffer());"
                        " let s=''; for (let i=0;i<u.length;i++) s += String.fromCharCode(u[i]); return btoa(s); }")
    return zipfile.ZipFile(io.BytesIO(base64.b64decode(b64)))


def _gpx_items(zf) -> list:
    """(kind, name, desc) per item element of every GPX member."""
    import xml.etree.ElementTree as ET
    out = []
    for n in zf.namelist():
        if n.endswith(".gpx"):
            root = ET.fromstring(zf.read(n))
            for tag, kind in TAG_KIND.items():
                for el in root.iter(GPX + tag):
                    out.append((kind, el.findtext(GPX + "name") or "", el.findtext(GPX + "desc") or ""))
    return out


def _bitterroots_rows(page: Page, n: int) -> list:
    """The first n rows the list shows, ticked."""
    uids = page.locator(ROW).evaluate_all(f"rs => rs.slice(0, {n}).map(r => r.dataset.uid)")
    _tick(page, uids)
    return uids


def _placeholders(page: Page, cell: str) -> int:
    return page.locator(f"#mark-dialog .na-row {cell}.is-placeholder, #mark-dialog .na-row {cell} .is-placeholder").count()


# =====================================================================================
# 5.1 Length and limits
# =====================================================================================


def test_note_prefix_pushes_a_511_byte_note_over_the_limit_and_flags_it(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Long", "a" * 511)])
    (u,) = _uids(page, "Long")
    _tick(page, [u])
    _open_bulk(page, "note")
    _type_spec(page, text="x")
    ((uid, _before, after, flags),) = _preview_rows(page)
    assert uid == u and after == "x\n" + "a" * 511 and flags >= {"note-over-limit"}
    sentence = _long_note_sentence(1)
    expect(page.locator(f'#mark-dialog .na-row[data-uid="{u}"] .na-flag')).to_contain_text(sentence)
    expect(page.locator("#bulk-apply")).to_be_enabled()
    assert _save_bulk(page) == "Changed 1 item."
    expect(page.locator(f'tr[data-uid="{u}"] .caution')).to_have_attribute("aria-label", sentence)


# =====================================================================================
# 5.2 Non-English and Unicode
# =====================================================================================


def test_cjk_names_survive_prefix_and_find_replace(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "日本語の山", "")])
    (u,) = _uids(page, "日本語の山")
    _tick(page, [u])
    _open_bulk(page, "rename")
    _type_spec(page, text="東")
    assert _preview_rows(page)[0][2] == "東日本語の山"
    _set_mode(page, "replace")
    _type_spec(page, find="山", repl="岳")
    assert _preview_rows(page) == [(u, "日本語の山", "日本語の岳", frozenset())]
    _save_bulk(page)
    assert _names(page, [u]) == ["日本語の岳"]


def test_a_name_of_only_combining_marks_is_kept_not_shown_as_untitled(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "x\u0301", "")])
    (u,) = _uids(page, "x\u0301")
    _tick(page, [u])
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="x", repl="")
    assert _preview_rows(page) == [(u, "x\u0301", "\u0301", frozenset())]
    assert _placeholders(page, ".na-after") == 0
    _save_bulk(page)
    assert _names(page, [u]) == ["\u0301"]


def test_emoji_only_names_show_as_themselves_and_sort_stably(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp A", ""), ("w", "Camp B", ""), ("w", "Lake", "")])
    _sort_folder(page)
    a, b = _uids(page, "Camp A", "Camp B")
    _tick(page, [a, b])
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, repl="🔥")
    assert [r[2] for r in _preview_rows(page)] == ["🔥", "🔥"]
    assert _placeholders(page, ".na-after") == 0
    _save_bulk(page)
    order = page.locator(ROW).evaluate_all("rs => rs.map(r => r.dataset.uid)")
    assert _names(page, order).count("🔥") == 2
    page.evaluate("renderFolders()")
    assert page.locator(ROW).evaluate_all("rs => rs.map(r => r.dataset.uid)") == order


@pytest.mark.parametrize("typed", ["Untitled", "(no name)"])
def test_a_name_typed_as_untitled_or_no_name_is_an_ordinary_name(fresh_page: Page, typed):
    page = fresh_page
    _map(page, [("w", "Camp", ""), ("w", "Lake", "")])
    (u,) = _uids(page, "Camp")
    _tick(page, [u])
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, repl=typed)
    assert _preview_rows(page) == [(u, "Camp", typed, frozenset())]
    assert _placeholders(page, ".na-after") == 0
    _save_bulk(page)
    assert _names(page, [u]) == [typed]
    assert typed in _gpx_names(_export_zip(page))


def test_unicode_names_render_as_text_in_the_preview_not_html(fresh_page: Page):
    page = fresh_page
    name = "<b>&amp;</b>"
    _map(page, [("w", name, "")])
    (u,) = _uids(page, name)
    _tick(page, [u])
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    assert _preview_rows(page) == [(u, name, "x" + name, frozenset())]
    assert page.locator("#mark-dialog .na-row b").count() == 0


# =====================================================================================
# 5.4 Replacement-pattern and find traps
# =====================================================================================


def test_empty_find_and_empty_replace_is_a_noop(fresh_page: Page):
    """On a hostile map: every naughty string as a name. No change at open, and none
    the instant Find and replace is chosen with nothing typed."""
    page = fresh_page
    _map(page, [("w", t, "") for t in NAUGHTY_TEXTS])
    _select_all_shown(page)
    n = page.evaluate("SEL.size")
    assert n == len(NAUGHTY_TEXTS)
    _open_bulk(page, "rename")
    for mode in ("prefix", "replace"):
        _set_mode(page, mode)
        rows = _preview_rows(page)
        assert len(rows) == n and all(f == {"unchanged"} for *_x, f in rows), mode
        assert all(b == a for _u, b, a, _f in rows), mode
        assert _summary(page) == f"0 will change · {n} unchanged"
        expect(page.locator("#bulk-apply")).to_be_disabled()


@pytest.mark.parametrize("match_case", [False, True])
def test_empty_find_replaces_the_whole_name(fresh_page: Page, match_case):
    page = fresh_page
    _map(page, [("w", n, "") for n in CAMPSITES + ["Campsite"]])
    uids = _uids(page, *CAMPSITES, "Campsite")
    _tick(page, uids)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, repl="Campsite", match_case=match_case)
    rows = {u: (a, f) for u, _b, a, f in _preview_rows(page)}
    assert all(a == "Campsite" for a, _f in rows.values())
    assert [rows[u][1] for u in uids] == [frozenset()] * 3 + [frozenset({"unchanged"})]
    assert _summary(page) == "3 will change · 1 unchanged"
    assert _save_bulk(page) == "Changed 3 items."
    assert _names(page, uids) == ["Campsite"] * 4


def test_empty_find_with_a_whitespace_only_replacement_saves_blank_names(fresh_page: Page):
    page = fresh_page
    names = ["Camp A", "Camp B", "Lake", "Trail 1", "Peak"]
    _map(page, [("w", n, "") for n in names])
    uids = _uids(page, *names)
    _tick(page, uids)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, repl="  ")
    rows = _preview_rows(page)
    assert [(a, f) for _u, _b, a, f in rows] == [("", frozenset())] * 5
    assert _placeholders(page, ".na-after") == 5
    expect(page.locator("#mark-dialog .na-row .na-after.is-placeholder, "
                        "#mark-dialog .na-row .na-after .is-placeholder").first).to_have_text("Untitled")
    assert _summary(page) == "5 will change · 0 unchanged"
    expect(page.locator("#bulk-apply")).to_be_enabled()
    assert _save_bulk(page) == "Changed 5 items."
    assert _names(page, uids) == [""] * 5


def test_empty_find_replaces_the_whole_note_like_replace_the_note(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "A", "old note"), ("w", "B", "line1\nline2"), ("w", "C", "")])
    uids = _uids(page, "A", "B", "C")
    _tick(page, uids)
    _open_bulk(page, "note")
    _set_mode(page, "replace")
    _type_spec(page, repl="see north")
    by_find = sorted(_preview_rows(page))
    assert [a for _u, _b, a, _f in by_find] == ["see north"] * 3
    _set_mode(page, "set")
    _type_spec(page, text="see north")
    assert sorted(_preview_rows(page)) == by_find
    _set_mode(page, "replace")
    _type_spec(page, repl="")
    assert all(f == {"unchanged"} for *_x, f in _preview_rows(page))
    expect(page.locator("#bulk-apply")).to_be_disabled()


def test_find_with_no_matches_marks_every_row_unchanged(loaded: Page):
    page = loaded
    _bitterroots_rows(page, 5)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="zzz", repl="x")
    assert all(f == {"unchanged"} for *_x, f in _preview_rows(page))
    assert _summary(page) == "0 will change · 5 unchanged"
    expect(page.locator("#bulk-apply")).to_be_disabled()


def test_find_equal_to_replace_counts_zero(fresh_page: Page):
    """On rows with no other-case match, and with Match case on (tracker 5.0: with it
    off, "Camp A" becomes "Camp a", a real change)."""
    page = fresh_page
    _map(page, [("w", "Camp", ""), ("w", "Lake", ""), ("w", "Trail", ""), ("w", "Camp A", "")])
    lower = _uids(page, "Camp", "Lake", "Trail")
    _tick(page, lower)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="a", repl="a")
    assert _summary(page) == "0 will change · 3 unchanged"
    expect(page.locator("#bulk-apply")).to_be_disabled()
    page.keyboard.press("Escape")
    _tick(page, _uids(page, "Camp A"))
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="a", repl="a", match_case=True)
    assert _summary(page) == "0 will change · 4 unchanged"
    expect(page.locator("#bulk-apply")).to_be_disabled()


def test_set_mode_with_a_blank_note_on_a_row_with_no_note_is_unchanged(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "NoNote", ""), ("w", "HasNote", "a real note")])
    none, has = _uids(page, "NoNote", "HasNote")
    _tick(page, [none, has])
    _open_bulk(page, "note")
    _set_mode(page, "set")
    _type_spec(page, text="  \n ")
    rows = {u: (b, a, f) for u, b, a, f in _preview_rows(page)}
    assert rows[none] == ("", "", frozenset({"unchanged"}))
    assert rows[has] == ("a real note", "", frozenset())
    expect(page.locator(f'#mark-dialog .na-row[data-uid="{none}"] .na-flag')).to_have_text("No change")
    assert _placeholders(page, ".na-after") == 0 and _placeholders(page, ".na-before") == 0
    assert _summary(page) == "1 will change · 1 unchanged"
    assert _save_bulk(page) == "Changed 1 item."
    assert _descs(page, [none, has]) == ["", ""]


def test_replace_with_empty_can_empty_a_name_and_saves_it_blank(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp", ""), ("w", "Lake", "")])
    (u,) = _uids(page, "Camp")
    _tick(page, [u])
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="Camp", repl="")
    assert _preview_rows(page) == [(u, "Camp", "", frozenset())]
    expect(page.locator(f'#mark-dialog .na-row[data-uid="{u}"] .na-after')).to_have_text("Untitled")
    assert _placeholders(page, ".na-after") == 1
    expect(page.locator("#bulk-apply")).to_be_enabled()
    _save_bulk(page)
    assert _names(page, [u]) == [""]
    assert sorted(_gpx_names(_export_zip(page))) == ["", "Lake"]


def test_match_case_toggle_changes_the_count_live(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp camp", ""), ("w", "CAMP", "")])
    a, b = _uids(page, "Camp camp", "CAMP")
    _tick(page, [a, b])
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="camp", repl="x")
    assert dict((u, af) for u, _b, af, _f in _preview_rows(page)) == {a: "x x", b: "x"}
    assert _summary(page) == "2 will change · 0 unchanged"
    seq = _preview_seq(page)
    _type_spec(page, match_case=True)
    assert _preview_seq(page) > seq
    assert dict((u, af) for u, _b, af, _f in _preview_rows(page)) == {a: "Camp x", b: "CAMP"}
    assert _summary(page) == "1 will change · 1 unchanged"


def test_whitespace_only_results_are_trimmed_to_blank_and_shown_untitled(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp", ""), ("w", "", "a nameless item")])
    camp, blank = _uids(page, "Camp", "")
    _tick(page, [camp, blank])
    _open_bulk(page, "rename")
    _type_spec(page, text="  ")
    rows = {u: (b, a, f) for u, b, a, f in _preview_rows(page)}
    assert rows[blank] == ("", "", frozenset({"unchanged"}))
    expect(page.locator(f'#mark-dialog .na-row[data-uid="{blank}"] .na-before')).to_have_text("Untitled")
    assert _placeholders(page, ".na-before") == 1
    expect(page.locator("#bulk-apply")).to_be_disabled()
    _set_mode(page, "replace")
    _type_spec(page, find="Camp", repl=" \t\n ")
    rows = {u: (b, a, f) for u, b, a, f in _preview_rows(page)}
    assert rows[camp] == ("Camp", "", frozenset())
    expect(page.locator(f'#mark-dialog .na-row[data-uid="{camp}"] .na-after')).to_have_text("Untitled")
    expect(page.locator("#bulk-apply")).to_be_enabled()
    _save_bulk(page)
    assert _names(page, [camp, blank]) == ["", ""]


def test_missing_notes_show_as_blank_never_no_note(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Undef", ""), ("w", "Empty", ""), ("w", "Real", "a note")])
    undef, empty, real = _uids(page, "Undef", "Empty", "Real")
    page.evaluate("u => { delete allItems().find(i => i.uid === u).desc; }", undef)
    _tick(page, [undef, empty, real])
    _open_bulk(page, "note")
    cells = "#mark-dialog .na-row .na-before, #mark-dialog .na-row .na-after"
    for mode, typed in (("prefix", {}), ("suffix", {}), ("replace", {"find": "zzz"}), ("set", {})):
        _set_mode(page, mode)
        _type_spec(page, **typed)
        rows = {u: (b, a) for u, b, a, _f in _preview_rows(page)}
        assert rows[undef] == ("", "") and rows[empty] == ("", ""), mode
        for u in (undef, empty):
            row = page.locator(f'#mark-dialog .na-row[data-uid="{u}"]')
            expect(row.locator(".na-before")).to_have_text("")
            expect(row.locator(".na-after")).to_have_text("")
        assert _placeholders(page, ".na-before") == 0 and _placeholders(page, ".na-after") == 0
        texts = page.locator(cells).all_text_contents()
        assert not any(t.strip() in {"No note", "(none)", "Untitled"} for t in texts), mode


# =====================================================================================
# 5.5 Incompatible and conflicting bulk operations
# =====================================================================================


def test_campsite_normalisation_makes_three_identical_names_and_exports_three_items(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", n, "") for n in CAMPSITES])
    uids = _uids(page, *CAMPSITES)
    _tick(page, uids)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, repl="Campsite")
    rows = _preview_rows(page)
    assert [(a, f) for _u, _b, a, f in rows] == [("Campsite", frozenset())] * 3
    for u in uids:   # exclusivity: no flag at all
        expect(page.locator(f'#mark-dialog .na-row[data-uid="{u}"]')).to_have_attribute("data-flags", "")
    assert _summary(page) == "3 will change · 0 unchanged"
    expect(page.locator("#bulk-apply")).to_be_enabled()
    assert _save_bulk(page) == "Changed 3 items."
    assert _names(page, uids) == ["Campsite"] * 3
    zf = _export_zip(page)
    assert _gpx_names(zf) == ["Campsite"] * 3
    raw = b"".join(zf.read(n) for n in zf.namelist() if n.endswith(".gpx"))
    assert raw.count(b"<name>Campsite</name>") == 3


def test_renaming_existing_twins_together_keeps_them_twins(fresh_page: Page):
    """Camp, camp, CAMP and " Camp " (which loads as a second "Camp")."""
    page = fresh_page
    _map(page, [("w", n, "") for n in ["Camp", "camp", "CAMP", " Camp "]])
    _select_all_shown(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="Base ")
    rows = _preview_rows(page)
    assert sorted(a for _u, _b, a, _f in rows) == sorted(["Base Camp", "Base camp", "Base CAMP", "Base Camp"])
    assert all(f == frozenset() for *_x, f in rows)
    expect(page.locator("#bulk-apply")).to_be_enabled()
    assert _save_bulk(page) == "Changed 4 items."
    assert Counter(_gpx_names(_export_zip(page))) == Counter(
        ["Base Camp", "Base camp", "Base CAMP", "Base Camp"])


def test_find_in_turkish_locale_matches_the_same_rows(browser, fresh_page: Page):
    """Case folding is the RegExp's, not the locale's: the same rows change under
    tr-TR as under the default locale."""
    names = ["Istanbul", "istanbul", "İstanbul", "ıstanbul", "Kit", "KIT"]

    def changed_names(page: Page) -> list:
        _map(page, [("w", n, "") for n in names])
        _select_all_shown(page)
        _open_bulk(page, "rename")
        _set_mode(page, "replace")
        _type_spec(page, find="i", repl="_")
        return sorted(b for _u, b, _a, f in _preview_rows(page) if "unchanged" not in f)

    default = changed_names(fresh_page)
    ctx = browser.new_context(bypass_csp=True, locale="tr-TR")
    page = ctx.new_page()
    page.goto(f"{BASE_URL}/index.html")
    page.wait_for_function("window.__cairnReady === true", timeout=120000)
    assert page.evaluate("navigator.language") == "tr-TR"
    turkish = changed_names(page)
    ctx.close()
    assert turkish == default
    assert default == sorted(["Istanbul", "istanbul", "Kit", "KIT"])


def test_a_rename_producing_a_blank_name_for_one_row_does_not_block_save(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", n, "") for n in ["Camp", "Camp B", "Camp C"]])
    uids = _uids(page, "Camp", "Camp B", "Camp C")
    _tick(page, uids)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="Camp", repl="")
    rows = {u: (a, f) for u, _b, a, f in _preview_rows(page)}
    assert [rows[u] for u in uids] == [("", frozenset()), ("B", frozenset()), ("C", frozenset())]
    expect(page.locator(f'#mark-dialog .na-row[data-uid="{uids[0]}"] .na-after')).to_have_text("Untitled")
    assert _placeholders(page, ".na-after") == 1
    assert _summary(page) == "3 will change · 0 unchanged"
    expect(page.locator("#bulk-apply")).to_be_enabled()
    assert _save_bulk(page) == "Changed 3 items."
    assert _names(page, uids) == ["", "B", "C"]


def test_mixed_waypoints_lines_and_areas_rename_alike(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Wp", ""), ("l", "Line", ""), ("a", "Area", "")])
    _select_all_shown(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    assert _save_bulk(page) == "Changed 3 items."
    got = {(k, n) for k, n, _d in _gpx_items(_export_zip(page))}
    assert got == {("waypoints", "xWp"), ("tracks", "xLine"), ("shapes", "xArea")}


def test_excluded_rows_in_the_selection_are_renamed_too(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Keep", ""), ("w", "Out", "")])
    keep, out = _uids(page, "Keep", "Out")
    _set(page, out, included=False)
    _tick(page, [keep, out])
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    assert len(_preview_rows(page)) == 2
    assert _save_bulk(page) == "Changed 2 items."
    assert _names(page, [keep, out]) == ["xKeep", "xOut"]
    assert page.evaluate("u => allItems().find(i => i.uid === u).included", out) is False
    assert _gpx_names(_export_zip(page)) == ["xKeep"]


def test_exclude_then_rename_then_include_exports_the_new_name(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Keep", ""), ("w", "Out", "")])
    keep, out = _uids(page, "Keep", "Out")
    _set(page, out, included=False)
    _tick(page, [out])
    _open_bulk(page, "rename")
    _type_spec(page, text="New ")
    _save_bulk(page)
    _set(page, out, included=True)
    assert sorted(_gpx_names(_export_zip(page))) == ["Keep", "New Out"]


def test_rows_in_a_collapsed_folder_are_not_in_the_dialog(loaded: Page):
    page = loaded
    g0, g1 = page.evaluate("DATA.groups.slice(0, 2).map(g => g.key)")
    in0 = page.evaluate("k => visibleItems(DATA.groups.find(g => g.key === k)).slice(0, 2).map(i => i.uid)", g0)
    in1 = page.evaluate("k => visibleItems(DATA.groups.find(g => g.key === k)).slice(0, 3).map(i => i.uid)", g1)
    _tick(page, in0 + in1)
    page.locator(f'.collapse[data-fk="collapse|{g0}"]').click()
    expect(page.locator(f'.collapse[data-fk="collapse|{g0}"]')).to_have_attribute("aria-expanded", "false")
    _open_bulk(page, "rename")
    assert _title(page) == "Rename 3 items"
    assert sorted(u for u, *_x in _preview_rows(page)) == sorted(in1)


def test_rows_hidden_by_a_filter_are_not_in_the_dialog(loaded: Page):
    page = loaded
    _select_all_shown(page)
    page.fill("#filter", "Trail")
    shown = page.locator(ROW).evaluate_all("rs => rs.map(r => r.dataset.uid)")
    assert 0 < len(shown) < 177
    _open_bulk(page, "rename")
    assert sorted(u for u, *_x in _preview_rows(page)) == sorted(shown)
    assert _title(page) == f"Rename {len(shown)} items"


def test_one_row_and_1500_rows_both_work(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", f"Wp {k:04d}", "") for k in range(1500)])
    _tick(page, _uids(page, "Wp 0000"))
    _open_bulk(page, "rename")
    assert _title(page) == "Rename 1 item"
    page.keyboard.press("Escape")
    _select_all_shown(page)
    _open_bulk(page, "rename")
    assert _title(page) == "Rename 1,500 items"
    assert page.locator("#mark-dialog .na-row").count() == 200
    expect(page.locator("#mark-dialog .na-more")).to_be_visible()
    assert _summary(page) == "0 will change · 1,500 unchanged"
    _type_spec(page, text="x")
    assert _summary(page) == "1,500 will change · 0 unchanged"
    assert _status_count(_save_bulk(page)) == 1500


def test_a_rename_that_drops_rows_from_the_search_prunes_the_selection_and_says_changed_n(loaded: Page):
    page = loaded
    page.fill("#filter", "Trail")
    _select_all_shown(page)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="Trail", repl="Tr")
    changed = [u for u, b, a, f in _preview_rows(page) if "unchanged" not in f]
    assert all(b != a for u, b, a, f in _preview_rows(page) if u in changed)
    n = _status_count(_save_bulk(page))
    assert n == len(changed) > 0
    assert page.input_value("#filter") == "Trail"
    still = page.evaluate("""() => [...SEL].every(u => { const i = allItems().find(x => x.uid === u);
        return (i.name + ' ' + (i.desc || '')).toLowerCase().includes('trail'); })""")
    assert still
    shown = set(page.locator(ROW).evaluate_all("rs => rs.map(r => r.dataset.uid)"))
    gone = [u for u, d in zip(changed, _descs(page, changed)) if "trail" not in (d or "").lower()]
    assert gone and not shown & set(gone)
    assert page.evaluate("unexportedChanges()") == n


def test_a_note_change_that_removes_the_search_term_prunes_the_row(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "A", "zebra one"), ("w", "B", "zebra two"), ("w", "C", "zebra three"),
                ("w", "D", "horse")])
    page.fill("#filter", "zebra")
    expect(page.locator(ROW)).to_have_count(3)
    _select_all_shown(page)
    _open_bulk(page, "note")
    _set_mode(page, "replace")
    _type_spec(page, find="zebra", repl="horse")
    assert _save_bulk(page) == "Changed 3 items."
    expect(page.locator(ROW)).to_have_count(0)
    assert page.evaluate("SEL.size") == 0


def test_a_rename_that_empties_the_selection_moves_focus_to_the_search_field(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Alpha 1", ""), ("w", "Alpha 2", ""), ("w", "Other", "")])
    page.fill("#filter", "Alpha")
    _select_all_shown(page)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="Alpha", repl="Beta")
    assert _save_bulk(page) == "Changed 2 items."
    assert page.evaluate("SEL.size") == 0
    expect(page.locator("#more-btn")).to_be_disabled()
    assert page.evaluate("document.activeElement.id") == "filter"


def test_a_rename_reorders_a_sorted_folder_and_keeps_focus_on_more(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", n, "") for n in ["Camp A", "Camp B", "Lake", "Peak"]])
    _sort_folder(page)
    assert _row_order(page) == ["Camp A", "Camp B", "Lake", "Peak"]
    _tick(page, _uids(page, "Camp A", "Camp B"))
    _open_bulk(page, "rename")
    _type_spec(page, text="zz ")
    _save_bulk(page)
    assert _row_order(page) == ["Lake", "Peak", "zz Camp A", "zz Camp B"]
    assert page.evaluate("document.activeElement.id") == "more-btn"


def test_prefix_keeps_natural_sort_order(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Camp 10", ""), ("w", "Camp 2", "")])
    _sort_folder(page)
    assert _row_order(page) == ["Camp 2", "Camp 10"]
    _select_all_shown(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x ")
    _save_bulk(page)
    assert _row_order(page) == ["x Camp 2", "x Camp 10"]


def test_prefix_that_ends_in_a_digit_changes_natural_order(fresh_page: Page):
    """Pinned as expected: "1" + "0 A" is "10 A", and 10 sorts before 19."""
    page = fresh_page
    _map(page, [("w", "9 B", ""), ("w", "0 A", "")])
    _sort_folder(page)
    assert _row_order(page) == ["0 A", "9 B"]
    _select_all_shown(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="1")
    _save_bulk(page)
    assert _row_order(page) == ["10 A", "19 B"]


def test_rename_then_change_note_then_export_agree(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "Wp", "note w"), ("l", "Line", "note l"), ("a", "Area", "note a")])
    _select_all_shown(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="Base ")
    _save_bulk(page)
    _open_bulk(page, "note")
    _set_mode(page, "suffix")
    _type_spec(page, text="end")
    _save_bulk(page)
    rows = page.evaluate("allItems().map(i => [i.kind, i.name, i.desc])")
    assert sorted(map(tuple, rows)) == sorted(_gpx_items(_export_zip(page)))
    assert sorted(n for _k, n, _d in rows) == ["Base Area", "Base Line", "Base Wp"]


def test_two_bulk_renames_compose(loaded: Page):
    page = loaded
    uids = _bitterroots_rows(page, 10)
    before = _names(page, uids)
    _open_bulk(page, "rename")
    _type_spec(page, text="⟦")
    _save_bulk(page)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="⟦", repl="⟧")
    _save_bulk(page)
    assert _names(page, uids) == ["⟧" + n for n in before]


def test_rename_after_an_export_counts_as_new_unexported_changes(loaded: Page):
    page = loaded
    _export_zip(page)
    page.click("#back")
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")
    _bitterroots_rows(page, 2)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    _save_bulk(page)
    assert page.evaluate("unexportedChanges()") == 2
    assert page.evaluate("stageValid('done')") is False
    page.go_back()
    expect(page.locator("#confirm")).to_be_visible()
    expect(page.locator("#confirm-title")).to_have_text("Leave this map?")
    page.locator("#confirm-actions button", has_text="Stay").click()
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")


def _members(zf) -> dict:
    return {n: zf.read(n) for n in zf.namelist()}


def test_rename_then_rename_back_still_counts_as_edits_and_exports_identically(loaded: Page):
    page = loaded
    baseline = _members(_export_zip(page))
    page.click("#back")
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")
    _select_all_shown(page)
    n = page.evaluate("SEL.size")
    assert n == 177
    _open_bulk(page, "rename")
    _type_spec(page, text="⟦")
    _save_bulk(page)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="⟦", repl="")
    assert _status_count(_save_bulk(page)) == n
    assert page.evaluate("unexportedChanges()") == n
    assert _members(_export_zip(page)) == baseline


def test_change_note_set_mode_on_rows_with_empty_notes_adds_them(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "A", ""), ("w", "B", "")])
    uids = _uids(page, "A", "B")
    _tick(page, uids)
    _open_bulk(page, "note")
    _set_mode(page, "set")
    _type_spec(page, text="see north")
    _save_bulk(page)
    assert _descs(page, uids) == ["see north"] * 2
    _open_bulk(page, "note")
    _set_mode(page, "set")
    _type_spec(page, text="x" * 600)
    _save_bulk(page)
    for u in uids:
        expect(page.locator(f'tr[data-uid="{u}"] .caution')).to_have_attribute(
            "aria-label", _long_note_sentence(88))


def test_rename_then_shift_click_range_after_save_uses_a_fresh_anchor(fresh_page: Page):
    page = fresh_page
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _map(page, [("w", n, "") for n in ["Alpha 1", "Alpha 2", "Beta 1", "Beta 2", "Beta 3"]])
    page.fill("#filter", "Alpha")
    a1, a2 = _uids(page, "Alpha 1", "Alpha 2")
    _tick(page, [a1, a2])
    assert page.evaluate("ANCHOR") is not None
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="Alpha", repl="Gamma")
    _save_bulk(page)
    assert page.evaluate("ANCHOR") is None and page.evaluate("SEL.size") == 0
    page.fill("#filter", "")
    expect(page.locator(ROW)).to_have_count(5)
    page.locator(f"{ROW} .sel-box").nth(3).click(modifiers=["Shift"])
    expect(page.locator("#selcount")).to_have_text("1 selected")
    assert not errors


# =====================================================================================
# 5.6 Click and keyboard behaviour
# =====================================================================================


def _two_rows(page: Page) -> list:
    _map(page, [("w", "Camp", "camp note"), ("w", "Lake", "lake note"), ("w", "Other", "")])
    uids = _uids(page, "Camp", "Lake")
    _tick(page, uids)
    return uids


def test_double_clicking_save_applies_once(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    page.dblclick("#bulk-apply")
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert _names(page, uids) == ["xCamp", "xLake"]
    edits = _edits(page)
    assert [edits[u]["name"] for u in uids] == ["xCamp", "xLake"]


def test_escape_mid_preview_discards_everything(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    page.keyboard.press("Escape")
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert _edits(page) == {} and _names(page, uids) == ["Camp", "Lake"]
    assert page.evaluate("document.activeElement.id") == "more-btn"


def test_enter_in_a_name_field_saves_when_enabled_and_does_nothing_when_disabled(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    page.locator("#bulk-text").press("Enter")
    assert _dialog_open(page) and _edits(page) == {}
    _type_spec(page, text="x")
    page.locator("#bulk-text").press("Enter")
    expect(page.locator("#mark-modal")).to_be_hidden()
    expect(page.locator("#status")).to_have_text("Changed 2 items.", timeout=8000)
    assert _names(page, uids) == ["xCamp", "xLake"]


def test_enter_right_after_deleting_the_text_does_not_save(fresh_page: Page):
    """The preview still shows a change and Save is enabled when Enter comes, inside
    the debounce: Save works the change out again from the fields, finds none, and
    saves nothing."""
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    expect(page.locator("#bulk-apply")).to_be_enabled()
    field = page.locator("#bulk-text")
    field.fill("")
    field.press("Enter")
    assert _edits(page) == {} and _names(page, uids) == ["Camp", "Lake"]
    assert _dialog_open(page)


def test_save_clicked_inside_the_debounce_window_uses_the_final_text(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="a")
    expect(page.locator("#bulk-apply")).to_be_enabled()
    page.locator("#bulk-text").fill("ab")
    page.click("#bulk-apply")
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert _names(page, uids) == ["abCamp", "abLake"]


def test_enter_in_a_note_field_inserts_a_newline_and_ctrl_enter_saves(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "note")
    field = page.locator("#bulk-text")
    assert field.evaluate("e => e.tagName") == "TEXTAREA"
    field.press("Enter")
    assert field.input_value() == "\n" and _dialog_open(page)
    field.press_sequentially("x")
    field.press("ControlOrMeta+Enter")
    expect(page.locator("#mark-modal")).to_be_hidden()
    expect(page.locator("#status")).to_have_text("Changed 2 items.", timeout=8000)
    assert _descs(page, uids) == ["x\ncamp note", "x\nlake note"]
    _open_bulk(page, "note")
    _set_mode(page, "replace")
    for sel in ("#bulk-find", "#bulk-repl"):
        f = page.locator(sel)
        assert f.evaluate("e => e.tagName") == "TEXTAREA", sel
        f.press("Enter")
        assert f.input_value() == "\n" and _dialog_open(page), sel


def test_ctrl_a_while_open_does_not_change_the_selection(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    page.locator("#bulk-text").press("ControlOrMeta+a")
    assert page.evaluate("SEL.size") == 2
    page.locator("#mark-dialog h2").click()
    page.keyboard.press("ControlOrMeta+a")
    assert page.evaluate("SEL.size") == 2 and _dialog_open(page)


def test_a_drag_cannot_start_while_the_dialog_is_open(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    page.evaluate("""u => {
        const el = document.querySelector(`tr[data-uid="${u}"] .name-in`);
        const r = el.getBoundingClientRect();
        const at = (type, dx) => el.dispatchEvent(new PointerEvent(type, { bubbles: true, button: 0,
            pointerId: 1, isPrimary: true, clientX: r.left + 5 + dx, clientY: r.top + 5 }));
        at('pointerdown', 0); at('pointermove', 20); at('pointermove', 40);
    }""", uids[0])
    assert page.evaluate("DRAG") is None
    page.evaluate("document.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }))")


def test_tab_stays_inside_the_dialog(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    for k in range(14):
        page.keyboard.press("Tab")
        assert page.evaluate("!!document.activeElement.closest('#mark-dialog')"), k
    for k in range(6):
        page.keyboard.press("Shift+Tab")
        assert page.evaluate("!!document.activeElement.closest('#mark-dialog')"), k


def test_browser_back_while_open_closes_it_and_runs_the_leave_prompt(fresh_page: Page):
    page = fresh_page
    camp, lake = _two_rows(page)
    _set(page, camp, name="Changed")
    page.evaluate("SEL.clear(); renderFolders()")
    _tick(page, [lake])
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    page.go_back()
    expect(page.locator("#mark-modal")).to_be_hidden()
    expect(page.locator("#confirm-title")).to_have_text("Leave this map?")
    page.locator("#confirm-actions button", has_text="Stay").click()
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert page.evaluate("BULK") is None
    assert set(_edits(page)) == {camp} and _names(page, [lake]) == ["Lake"]


def test_export_and_start_over_requests_bail_while_open(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    page.evaluate("window.__cairnExported = false; requestExport()")
    assert _dialog_open(page)
    assert page.evaluate("window.__cairnExported") is False
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")
    page.evaluate("requestStartOver()")
    expect(page.locator("#confirm")).to_be_hidden()
    assert _dialog_open(page)


def test_a_programmatic_export_closes_the_dialog_and_applies_nothing(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    page.evaluate("window.__cairnExported = false")
    page.evaluate("doExport()")
    page.wait_for_function("window.__cairnExported === true", timeout=60000)
    assert page.evaluate("BULK") is None
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert _names(page, uids) == ["Camp", "Lake"]
    assert sorted(_gpx_names(_zip_now(page))) == ["Camp", "Lake", "Other"]


def test_opening_rename_with_a_pending_folder_merge_offer_flushes_it_first(loaded: Page):
    """Leaving a folder name for a taken one queues its merge offer (deferRender, run
    on a timer). Opening Rename... in the same task, before the timer, runs the queue
    first, and the offer's confirm stops the dialog from opening: never a confirm over
    the dialog. One synchronous evaluate, so the queue is still pending (real clicks
    would let the timer run first)."""
    page = loaded
    _bitterroots_rows(page, 1)
    sec = page.locator("section.folder", has=page.locator(".folder-name", has_text=re.compile(r"^Lost Trail Pass$")))
    sec.locator(".folder-name").click()
    page.keyboard.type("north ROOTS")
    page.evaluate("() => { document.activeElement.blur(); document.querySelector('#bulk-rename').click(); }")
    expect(page.locator("#confirm")).to_be_visible()
    expect(page.locator("#confirm-title")).to_have_text("“North Roots” already exists")
    assert page.evaluate("BULK") is None and page.evaluate("CONFIRM") is not None
    assert page.locator("#mark-dialog[data-bulk]").count() == 0
    expect(page.locator("#mark-modal")).to_be_hidden()


def test_a_queued_bulk_icon_click_does_not_open_over_the_text_dialog(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    box = page.locator("#bulk-icon").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.focus("#more-btn")
    page.keyboard.press("Enter")
    page.locator("#bulk-rename").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#mark-dialog")).to_have_attribute("data-bulk", "rename")
    page.mouse.up()
    page.evaluate("document.querySelector('#bulk-icon').click()")
    expect(page.locator("#mark-dialog")).to_have_attribute("data-bulk", "rename")
    assert page.locator("#mark-dialog #bulk-text").count() == 1
    assert page.locator("#mark-dialog .icon-grid").count() == 0
    assert page.evaluate("!!(BULK && BULK.text)")


def _note_then_rename(page: Page, draft: str | None):
    """Open the note editor on a waypoint (with a typed draft, or none), tick that row,
    then More > Rename...; the row's uid."""
    if draft is None:
        uid = page.evaluate("DATA.groups.flatMap(g=>g.items).find(i => i.kind === 'waypoints').uid")
        page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
        expect(page.locator(".desc-in")).to_have_count(1)
    else:
        uid = _open_changed_waypoint_note(page, draft)
    _tick(page, [uid])
    page.click("#more-btn")
    page.locator("#bulk-rename").click()
    return uid


def test_opening_rename_with_a_changed_open_note_on_a_selected_row_asks_first(loaded: Page):
    page = loaded
    buttons = page.locator("#confirm-actions button")
    # Keep editing: back to the note, no dialog.
    uid = _note_then_rename(page, "DRAFT ONE")
    before = page.evaluate("u => allItems().find(i => i.uid === u).desc", uid)
    expect(page.locator("#confirm-title")).to_have_text("Save your note?")
    expect(buttons).to_have_text(["Keep editing", "Discard", "Save"])
    buttons.filter(has_text="Keep editing").click()
    expect(page.locator("#confirm")).to_be_hidden()
    assert page.evaluate("document.activeElement.classList.contains('desc-in')")
    assert page.locator("#mark-dialog[data-bulk]").count() == 0
    # Discard: the draft is dropped, the dialog opens.
    page.click("#more-btn")
    page.locator("#bulk-rename").click()
    buttons.filter(has_text="Discard").click()
    expect(page.locator("#mark-dialog")).to_have_attribute("data-bulk", "rename")
    assert page.evaluate("u => allItems().find(i => i.uid === u).desc", uid) == before
    assert page.evaluate("NOTE_EDIT") is None
    page.keyboard.press("Escape")
    # Save: the note is kept, the dialog opens.
    page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    page.locator(".desc-in").first.fill("DRAFT TWO")
    page.click("#more-btn")
    page.locator("#bulk-rename").click()
    buttons.filter(has_text=re.compile(r"^Save$")).click()
    expect(page.locator("#mark-dialog")).to_have_attribute("data-bulk", "rename")
    assert page.evaluate("u => allItems().find(i => i.uid === u).desc", uid) == "DRAFT TWO"


def test_opening_rename_with_an_unchanged_open_note_just_closes_it(loaded: Page):
    page = loaded
    _note_then_rename(page, None)
    expect(page.locator("#mark-dialog")).to_have_attribute("data-bulk", "rename")
    expect(page.locator("#confirm")).to_be_hidden()
    assert page.evaluate("NOTE_EDIT") is None


def test_an_open_note_on_an_unselected_row_stays_open(loaded: Page):
    page = loaded
    uid = _open_changed_waypoint_note(page, "DRAFT")
    other = page.locator(ROW).evaluate_all("(rs, u) => rs.map(r => r.dataset.uid).find(x => x !== u)", uid)
    _tick(page, [other])
    _open_bulk(page, "rename")
    expect(page.locator("#confirm")).to_be_hidden()
    page.locator("#mark-dialog .bulk-cancel").click()
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert page.evaluate("NOTE_EDIT && NOTE_EDIT.uid") == uid
    expect(page.locator(".desc-in")).to_have_count(1)


def test_focus_returns_to_the_more_button_after_save_and_after_cancel(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    _save_bulk(page)
    assert page.evaluate("document.activeElement.id") == "more-btn"
    _open_bulk(page, "rename")
    page.locator("#mark-dialog .bulk-cancel").click()
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert page.evaluate("document.activeElement.id") == "more-btn"


_PREVIEW_MATCHES_FIELD = """() => [...document.querySelectorAll('#mark-dialog .na-row')].every(r =>
    r.querySelector('.na-after').textContent === document.querySelector('#bulk-text').value
        + r.querySelector('.na-before').textContent)"""


def test_rapid_typing_leaves_the_preview_equal_to_the_final_text(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", n, "") for n in ["Camp", "Lake", "Peak"]])
    _select_all_shown(page)
    _open_bulk(page, "rename")
    text = "abcdefghij" * 4
    _type_slowly(page, "#bulk-text", text, 5)
    page.wait_for_function(_PREVIEW_MATCHES_FIELD, timeout=5000)
    assert page.input_value("#bulk-text") == text
    assert all(a == text + b for _u, b, a, _f in _preview_rows(page))
    # Slower than the debounce: every keystroke renders, and each render matches its text.
    page.locator("#bulk-text").fill("")
    page.wait_for_function(_PREVIEW_MATCHES_FIELD, timeout=5000)
    typed = ""
    for ch in "slowtype":
        seq = _preview_seq(page)
        page.locator("#bulk-text").press(ch)
        typed += ch
        _wait_preview_past(page, seq)
        assert all(a == typed + b for _u, b, a, _f in _preview_rows(page)), typed


def test_backdrop_click_cancels(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    page.locator("#mark-modal").click(position={"x": 5, "y": 5})
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert _edits(page) == {} and _names(page, uids) == ["Camp", "Lake"]


def test_the_menu_items_are_disabled_with_nothing_selected(loaded: Page):
    page = loaded
    expect(page.locator("#more-btn")).to_be_disabled()
    expect(page.locator("#bulk-rename")).to_be_hidden()
    expect(page.locator("#bulk-note")).to_be_hidden()


def test_switching_mode_keeps_typed_text_per_field(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="abc")
    _set_mode(page, "replace")
    _type_spec(page, find="q", repl="r")
    _set_mode(page, "prefix")
    assert page.input_value("#bulk-text") == "abc"
    _set_mode(page, "replace")
    assert page.input_value("#bulk-find") == "q" and page.input_value("#bulk-repl") == "r"


def test_the_dialog_works_under_the_enforced_csp(csp_page: Page):
    """DOM-only waits (no wait_for_function, no string evaluate): data-stage, the
    preview's data-preview-seq, the rows and the status line."""
    page = csp_page
    page.set_input_files("#file", str(FIXTURE))
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    for k in range(3):
        page.locator(f"{ROW} .sel-box").nth(k).check()
    expect(page.locator("#selcount")).to_have_text("3 selected")
    _open_bulk(page, "rename")
    expect(page.locator("#mark-dialog h2")).to_have_text("Rename 3 items")
    expect(page.locator("#mark-dialog .na-row")).to_have_count(3)
    _type_spec(page, csp=True, text="x")
    expect(page.locator("#bulk-summary")).to_have_text("3 will change · 0 unchanged")
    assert _save_bulk(page) == "Changed 3 items."


# =====================================================================================
# 5.7 Validation and review
# =====================================================================================


def _uid_tagged(page: Page, n: int) -> list:
    """n Bitterroots rows, each renamed (one edit) to start with its own uid, ticked."""
    uids = _bitterroots_rows(page, n)
    for u, name in zip(uids, _names(page, uids)):
        _set(page, u, name=f"⟦{u}⟧ {name}")
    return uids


def _gpx_by_tag(zf, uids) -> dict:
    """uid -> (name, desc) of the GPX item whose name starts with "⟦uid⟧"."""
    out = {}
    for _k, name, desc in _gpx_items(zf):
        for u in uids:
            if name.startswith(f"⟦{u}⟧"):
                out[u] = (name, desc)
    return out


def test_preview_equals_saved_equals_exported_for_names(loaded: Page):
    page = loaded
    uids = _uid_tagged(page, 12)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="a", repl="4")
    preview = {u: a for u, _b, a, _f in _preview_rows(page)}
    _save_bulk(page)
    assert dict(zip(uids, _names(page, uids))) == preview
    zf = _export_zip(page)
    assert {u: v[0] for u, v in _gpx_by_tag(zf, uids).items()} == preview
    # Second pass: three rows blanked.
    page.click("#back")
    page.evaluate("SEL.clear(); renderFolders()")
    _tick(page, uids[:3])
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="", repl=" ")
    assert [a for _u, _b, a, _f in _preview_rows(page)] == ["", "", ""]
    _save_bulk(page)
    assert _names(page, uids[:3]) == ["", "", ""]
    blanks = page.evaluate("allItems().filter(i => i.included && i.name === '').length")
    assert _gpx_names(_export_zip(page)).count("") == blanks >= 3


def test_preview_equals_saved_equals_exported_for_notes(loaded: Page):
    page = loaded
    uids = _uid_tagged(page, 12)
    _open_bulk(page, "note")
    _set_mode(page, "suffix")
    _type_spec(page, text="line two\r\nline three")
    preview = {u: a for u, _b, a, _f in _preview_rows(page)}
    assert all("\r" not in a and a.endswith("line two\nline three") for a in preview.values())
    _save_bulk(page)
    assert dict(zip(uids, _descs(page, uids))) == preview
    zf = _export_zip(page)
    assert {u: v[1] for u, v in _gpx_by_tag(zf, uids).items()} == preview


def test_changed_count_in_status_equals_rows_that_differ(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", n, "") for n in ["Camp A", "Camp B", "Lake"]])
    _select_all_shown(page)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="Camp", repl="Site")
    differ = sum(b != a for _u, b, a, _f in _preview_rows(page))
    status = _save_bulk(page)
    assert status == f"Changed {differ} items." and differ == 2
    page.evaluate("SEL.clear(); renderFolders()")
    _tick(page, _uids(page, "Lake"))
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="L", repl="l")
    assert _save_bulk(page) == "Changed 1 item."


def _rename_7_then_note_3(page: Page) -> list:
    uids = _bitterroots_rows(page, 7)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    _save_bulk(page)
    page.evaluate("SEL.clear(); renderFolders()")
    _tick(page, uids[:3])
    _open_bulk(page, "note")
    _set_mode(page, "suffix")
    _type_spec(page, text="more")
    _save_bulk(page)
    return uids


def test_unexported_changes_counts_each_renamed_row_once(loaded: Page):
    _rename_7_then_note_3(loaded)
    assert loaded.evaluate("unexportedChanges()") == 7


def test_start_over_names_the_bulk_changes_count(loaded: Page):
    page = loaded
    _rename_7_then_note_3(page)
    page.locator(".newmap").first.click()
    expect(page.locator("#confirm-body")).to_have_text("This discards 7 unexported changes.")


def test_the_caution_marks_match_the_dialogs_note_flags(fresh_page: Page):
    page = fresh_page
    _map(page, [("w", "N300", "a" * 300), ("w", "N500", "a" * 500), ("w", "Short", "short"),
                ("w", "N511", "a" * 511)])
    _select_all_shown(page)
    _open_bulk(page, "note")
    _set_mode(page, "suffix")
    _type_spec(page, text="b" * 100)
    flagged = {u for u, _b, _a, f in _preview_rows(page) if "note-over-limit" in f}
    assert flagged == set(_uids(page, "N500", "N511"))
    _save_bulk(page)
    marked = set(page.locator(f"{ROW}:has(.caution)").evaluate_all("rs => rs.map(r => r.dataset.uid)"))
    assert marked == flagged
    _export_zip(page)
    warn = page.locator(".note.warn", has_text="over the length limit")
    expect(warn).to_contain_text("“N500”")
    expect(warn).to_contain_text("“N511”")
    expect(warn).not_to_contain_text("“N300”")


def test_a_bulk_rename_does_not_touch_icons_colors_or_exclusions(loaded: Page):
    page = loaded
    uids = _bitterroots_rows(page, 5)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    _save_bulk(page)
    edits = _edits(page)
    assert set(edits) == set(uids) and all(list(edits[u]) == ["name"] for u in uids)


def test_every_dialog_state_has_the_expected_accessibility_tree(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    for which, title, modes in (("rename", "Rename 2 items", ["Add before", "Add after", "Find and replace"]),
                                ("note", "Change the note on 2 items",
                                 ["Add before", "Add after", "Find and replace", "Replace the note"])):
        _open_bulk(page, which)
        dialog = page.get_by_role("dialog", name=title)
        expect(dialog).to_be_visible()
        expect(page.locator("#mark-dialog .mode-tog")).to_have_text(modes)
        for m in modes:
            expect(dialog.get_by_role("button", name=m, exact=True)).to_have_attribute(
                "aria-pressed", "true" if m == "Add before" else "false")
        expect(dialog.get_by_role("textbox", name="Text", exact=True)).to_be_focused()
        expect(page.locator("#bulk-summary")).to_have_attribute("aria-live", "polite")
        expect(dialog.get_by_role("button", name="Save", exact=True)).to_be_disabled()
        _type_spec(page, text="x")
        expect(dialog.get_by_role("button", name="Save", exact=True)).to_be_enabled()
        _set_mode(page, "replace")
        expect(dialog.get_by_role("textbox", name="Find", exact=True)).to_be_visible()
        expect(dialog.get_by_role("textbox", name="Replace with", exact=True)).to_be_visible()
        expect(dialog.get_by_role("button", name="Match case", exact=True)).to_have_attribute("aria-pressed", "false")
        expect(dialog.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#mark-modal")).to_be_hidden()


# =====================================================================================
# 5.8 Input methods and accessibility
# =====================================================================================


def test_enter_during_ime_composition_does_not_save(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    page.evaluate("""() => {
        const el = document.querySelector('#bulk-text');
        el.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
        el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true, isComposing: true }));
        el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true, keyCode: 229 }));
    }""")
    assert _dialog_open(page) and _edits(page) == {} and _names(page, uids) == ["Camp", "Lake"]
    seq = _preview_seq(page)
    page.evaluate("""() => document.querySelector('#bulk-text').dispatchEvent(
        new CompositionEvent('compositionend', { bubbles: true, data: 'x' }))""")
    _wait_preview_past(page, seq)


def test_input_events_mid_composition_preview_the_partial_text_without_saving(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    seq = _preview_seq(page)
    page.evaluate("""vals => {
        const el = document.querySelector('#bulk-text');
        el.focus();
        el.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
        for (const v of vals) {
            el.value = v;
            el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertCompositionText',
                                                       data: v, isComposing: true }));
        }
    }""", ["k", "ka", "kan"])
    _wait_preview_past(page, seq)
    page.wait_for_function(_PREVIEW_MATCHES_FIELD, timeout=5000)
    assert sorted(a for _u, _b, a, _f in _preview_rows(page)) == ["kanCamp", "kanLake"]
    assert _edits(page) == {} and _dialog_open(page)


def test_ctrl_z_in_the_field_reruns_the_preview(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    field = page.locator("#bulk-text")
    field.press_sequentially("abc")
    page.wait_for_function(_PREVIEW_MATCHES_FIELD, timeout=5000)
    seq = _preview_seq(page)
    field.press("ControlOrMeta+z")
    _wait_preview_past(page, seq)
    assert field.input_value() != "abc"
    page.wait_for_function(_PREVIEW_MATCHES_FIELD, timeout=5000)


def _paste(page: Page, sel: str, *, text: str | None = None, html: str | None = None) -> None:
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE_URL)
    if html is None:
        page.evaluate("t => navigator.clipboard.writeText(t)", text)
    else:
        page.evaluate("""([t, h]) => navigator.clipboard.write([new ClipboardItem({
            'text/plain': new Blob([t], { type: 'text/plain' }),
            'text/html': new Blob([h], { type: 'text/html' })})])""", [text, html])
    seq = _preview_seq(page)
    page.locator(sel).focus()
    page.keyboard.press("ControlOrMeta+v")
    _wait_preview_past(page, seq)


def test_pasting_multiline_text_into_the_name_prefix_field(fresh_page: Page):
    """The browser, not the core, deals with the line break: Chromium turns it into a
    space in an <input> (the plan expected it dropped, "AB"). No chars-removed."""
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    _paste(page, "#bulk-text", text="A\r\nB")
    assert page.input_value("#bulk-text") == "A B"
    rows = _preview_rows(page)
    assert sorted(a for _u, _b, a, _f in rows) == ["A BCamp", "A BLake"]
    assert not any("chars-removed" in f for *_x, f in rows)


def test_pasting_multiline_text_into_the_note_prefix_field_keeps_it(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "note")
    _paste(page, "#bulk-text", text="A\r\nB")
    assert page.input_value("#bulk-text") == "A\nB"
    assert sorted(a for _u, _b, a, _f in _preview_rows(page)) == ["A\nB\ncamp note", "A\nB\nlake note"]


def test_pasting_rich_text_keeps_only_plain_text(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    _paste(page, "#bulk-text", text="Bold text", html="<b>Bold</b> text")
    assert page.input_value("#bulk-text") == "Bold text"
    assert sorted(a for _u, _b, a, _f in _preview_rows(page)) == ["Bold textCamp", "Bold textLake"]
    assert page.locator("#mark-dialog b").count() == 0


def test_browser_zoom_200_keeps_save_reachable(fresh_page: Page):
    """200% browser zoom on a 1440x900 window is a 720x450 CSS viewport."""
    page = fresh_page
    page.set_viewport_size({"width": 720, "height": 450})
    uids = _two_rows(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    save = page.locator("#bulk-apply")
    save.scroll_into_view_if_needed()
    box = save.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 720
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    save.click()
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert _names(page, uids) == ["xCamp", "xLake"]


def test_summary_is_announced_to_assistive_tech(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    expect(page.locator("#bulk-summary")).to_have_attribute("aria-live", "polite")
    label = page.get_attribute("#mark-dialog", "aria-labelledby")
    assert label
    expect(page.locator(f"#{label}")).to_have_text("Rename 2 items")
    expect(page.locator("#bulk-summary")).to_have_text("0 will change · 2 unchanged")


def test_keyboard_only_flow(fresh_page: Page):
    page = fresh_page
    uids = _two_rows(page)
    page.focus("#more-btn")
    page.keyboard.press("Enter")
    expect(page.locator("#more-menu")).to_be_visible()
    for _ in range(6):
        if page.evaluate("document.activeElement.id") == "bulk-rename":
            break
        page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "bulk-rename"
    page.keyboard.press("Enter")
    expect(page.locator("#mark-dialog")).to_have_attribute("data-bulk", "rename")
    expect(page.locator("#bulk-text")).to_be_focused()
    seq = _preview_seq(page)
    page.keyboard.type("x")
    _wait_preview_past(page, seq)
    page.keyboard.press("Enter")
    expect(page.locator("#mark-modal")).to_be_hidden()
    assert _names(page, uids) == ["xCamp", "xLake"]
    assert page.evaluate("document.activeElement.id") == "more-btn"


def test_every_control_has_a_visible_focus_ring(fresh_page: Page):
    page = fresh_page
    _two_rows(page)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="a", repl="b")
    seen = {}
    for _ in range(14):
        page.keyboard.press("Tab")
        info = page.evaluate("""() => { const e = document.activeElement; const s = getComputedStyle(e);
            return [e.id || e.className || e.tagName, s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow]; }""")
        key, style, width, color, shadow = info
        ring = (style != "none" and width != "0px" and not color.endswith(", 0)")) or shadow != "none"
        seen[key] = ring
    assert len(seen) >= 6 and all(seen.values()), seen
