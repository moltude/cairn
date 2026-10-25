"""Playwright test suite for the Cairn web prototype.

The prototype's whole premise is "the browser reuses the Python engine
unmodified" (see web/bridge.py's module docstring). These tests drive the
real app in a real headless browser against a dev server that must already
be running at BASE_URL (start it with `uv run python web/serve.py`).

Run:
    uv run pytest --no-cov -p no:cacheprovider tests/web/test_web_app.py

If the dev server isn't reachable, every test in this module skips cleanly
(see `_require_server` below) so it never breaks the main suite.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect, sync_playwright

from tests.web.helpers import (  # noqa: F401  (moved out on 2026-10-25)
    BASE_URL, FIXTURE, FX_DIR, ROW, _ONX_GPX_HEAD,
    export_zip_bytes, _select_all_shown, _clear_selection, _set_type, _menu_action, _export_zip,
    _load_files, _set, _tick, _is_marked, _open_changed_waypoint_note, _row, _gpx_blob,
    _onx_wpt, _gpx_payload,
)


EXPECTED_TOTALS = {"folders": 10, "items": 177, "attention": 25}
# attention was 26 until the web app began loading the user's
# cairn_config.yaml explicitly. Without it the browser silently used 144
# built-in symbol mappings while the CLI used 152, so `circle-p` did not
# resolve to Parking and one extra waypoint fell back to the generic pin.
# See web/bridge.py:_config().
















# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------












def test_no_loading_or_version_text_after_boot(fresh_page: Page):
    body = fresh_page.inner_text("body")
    for text in ("Loading", "Starting", "Ready", "engine v", "Python runtime"):
        assert text not in body, text
    assert fresh_page.text_content("#status").strip() == ""
    assert fresh_page.is_enabled("#pick")


NAV_LINKS = ["App", "Help", "FAQ", "Walkthrough", "GitHub"]
NAV_CURRENT = {"index.html": "App", "faq.html": "FAQ", "walkthrough.html": "Walkthrough"}


def _navs(page: Page) -> list:
    """Each site nav on the page: its labels, targets and which is current."""
    return page.locator("nav.site-nav").evaluate_all("""ns => ns.map(n => ({
        top: !n.closest('footer'),
        labels: [...n.querySelectorAll('a, button')].map(e => e.textContent.trim()),
        hrefs: [...n.querySelectorAll('a, button')].map(e => e.getAttribute('href')),
        current: [...n.querySelectorAll('[aria-current=page]')].map(e => e.textContent.trim())}))""")


@pytest.mark.parametrize("path", ["index.html", "faq.html", "walkthrough.html"])
def test_one_site_nav_at_the_top_of_every_page(context, path):
    """Owner feedback 2026-10-24 (UI-38): App · Help · FAQ · Walkthrough ·
    GitHub in the sticky top bar of every page, the current page marked; no
    bottom copy, no "Back to the app" or other inline duplicates."""
    page = context.new_page()
    page.goto(f"{BASE_URL}/{path}")
    navs = _navs(page)
    assert [n["top"] for n in navs].count(False) == 0          # no footer nav
    assert any(n["top"] for n in navs)
    for n in navs:
        assert n["labels"] == NAV_LINKS, n
        assert n["current"] == [NAV_CURRENT[path]], n
        assert n["hrefs"][0] == "./" and n["hrefs"][2:] == ["faq.html", "walkthrough.html",
                                                           "https://github.com/moltude/cairn"]
    assert page.locator("footer").count() == 0
    body = page.locator("body").inner_text().lower()
    assert "back to the app" not in body and "read the faq" not in body and "see the walkthrough" not in body
    assert page.locator(".topnav, .doc-foot").count() == 0
    page.close()


@pytest.mark.parametrize("path", ["faq.html", "walkthrough.html"])
def test_doc_pages_have_no_head_text_and_sit_on_a_paper_panel(context, path):
    """Owner feedback 2026-10-24: no "HELP" kicker or big title on the doc
    pages (the h1 stays for screen readers only); the content sits on the
    landing page's paper panel, so no contour line runs behind the text."""
    page = context.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{BASE_URL}/{path}")
    assert page.locator(".doc-main > .kicker").count() == 0
    h1 = page.locator("h1")
    expect(h1).to_have_count(1)
    assert h1.evaluate("e => e.getBoundingClientRect().width <= 1")      # visually hidden
    panel = page.evaluate("""() => { const m = getComputedStyle(document.querySelector('.doc-main'));
        return {bg: m.backgroundColor, shadow: m.boxShadow}; }""")
    paper = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert panel["bg"] == paper and "18px" in panel["shadow"], panel
    page.close()


@pytest.mark.parametrize("path", ["index.html", "faq.html", "walkthrough.html"])
def test_nav_links_use_the_small_caps_kicker_style(context, path):
    """The nav looks like the "EXPORT" kicker (uppercase, letter-spaced,
    small, brown), not underlined body links; the current page is underlined,
    and hover and keyboard focus underline the others."""
    page = context.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{BASE_URL}/{path}")
    links = page.locator("nav.site-nav a:visible, nav.site-nav button:visible")
    assert links.count() == 5
    kicker = page.evaluate("""() => { const k = document.createElement('span'); k.className = 'kicker';
        document.body.appendChild(k); const c = getComputedStyle(k);
        const r = {color: c.color, tt: c.textTransform}; k.remove(); return r; }""")
    for k in range(links.count()):
        st = links.nth(k).evaluate("""e => { const c = getComputedStyle(e);
            return {tt: c.textTransform, ls: parseFloat(c.letterSpacing), fs: parseFloat(c.fontSize),
                    deco: c.textDecorationLine, color: c.color}; }""")
        current = links.nth(k).get_attribute("aria-current") == "page"
        assert st["tt"] == "uppercase" and st["ls"] > 1 and st["fs"] <= 12 and st["color"] == kicker["color"], st
        assert st["deco"] == ("underline" if current else "none"), st
    other = links.nth(1)                                   # Help: never the current page
    other.hover()
    assert other.evaluate("e => getComputedStyle(e).textDecorationLine") == "underline"
    page.mouse.move(1, 1)
    links.nth(2).focus()
    page.keyboard.press("Shift+Tab")                                   # keyboard focus (focus-visible)
    assert other.evaluate("e => getComputedStyle(e).textDecorationLine") == "underline"
    _shot(page, f"fb-15-nav-{path.split('.')[0]}-top")
    page.close()


def test_every_help_in_the_app_opens_the_help_dialog(loaded: Page):
    page = loaded
    _wide(page)
    # The edit stage has no top bar: its nav sits at the right of the search row.
    top = page.locator(".toolbar nav.site-nav")
    expect(top).to_be_visible()
    expect(page.locator("#topbar")).to_be_hidden()
    _shot(page, "fb-15-nav-edit-stage")
    for btn in (top.locator(".help-open"),):
        btn.click()
        expect(page.locator("#help")).to_be_visible()
        page.click("#help-close")
        expect(page.locator("#help")).to_be_hidden()


def test_top_bar_help_opens_help_from_the_app(fresh_page: Page):
    expect(fresh_page.locator("#help")).to_be_hidden()
    fresh_page.click("#topbar >> text=Help")
    expect(fresh_page.locator("#help")).to_be_visible()


def test_the_app_chrome_has_only_the_site_nav(fresh_page: Page):
    """The old Help / FAQ / Walkthrough links in the top bar and the rail are
    gone; the top bar carries the site nav and nothing else clickable."""
    extra = fresh_page.locator("#topbar a:not(.site-nav *), #topbar button:not(.site-nav *), "
                               ".rail-head a, .rail-head button")
    assert extra.count() == 0
    assert fresh_page.locator("#topbar nav.site-nav").count() == 1


@pytest.mark.parametrize("path", ["faq.html", "walkthrough.html"])
def test_top_help_on_doc_pages_links_to_the_app_help(context, path):
    page = context.new_page()
    page.goto(f"{BASE_URL}/{path}")
    assert page.get_attribute("header.topbar >> text=Help", "href") == "./#help"
    page.close()


def test_hash_help_opens_the_help_modal(context):
    page = context.new_page()
    page.goto(f"{BASE_URL}/index.html#help")
    expect(page.locator("#help")).to_be_visible()
    page.close()


def test_file_chosen_before_ready_is_processed_once_ready(context):
    page = context.new_page()
    held = []
    page.route("**/dist/*.whl", lambda route: held.append(route))
    page.goto(f"{BASE_URL}/index.html")
    page.wait_for_function("document.body.dataset.stage === 'drop'")
    page.set_input_files("#file", str(FIXTURE))
    expect(page.locator("#drop-wait")).to_have_text("Getting ready…")
    assert page.evaluate("window.__cairnReady") is not True
    # The wheel request is held; wait until it arrives, then release it.
    for _ in range(600):
        if held:
            break
        page.wait_for_timeout(100)
    assert held, "wheel request never arrived"
    assert page.evaluate("window.__cairnLoaded") is not True
    held[0].continue_()
    page.wait_for_function("window.__cairnLoaded === true", timeout=120_000)
    assert page.evaluate("document.body.dataset.stage") == "edit"
    assert page.evaluate("DATA.totals") == EXPECTED_TOTALS
    page.close()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_loading_fixture_yields_expected_folder_and_markup_counts(loaded: Page):
    totals = loaded.evaluate("DATA.totals")
    assert totals == EXPECTED_TOTALS


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_attention_only_filter_reduces_row_count_to_match_totals(loaded: Page):
    totals = loaded.evaluate("DATA.totals")
    all_rows = loaded.locator("#folders tbody tr").count()
    assert all_rows == totals["items"]

    loaded.check("#only-attention")
    loaded.wait_for_timeout(100)
    filtered_rows = loaded.locator("#folders tbody tr").count()

    assert filtered_rows == totals["attention"]
    assert filtered_rows < all_rows

    loaded.uncheck("#only-attention")


# ---------------------------------------------------------------------------
# Selection + bulk edit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_select,new_icon", [(1, "Parking"), (3, "Camp")])
def test_bulk_icon_change_reduces_attention_by_exactly_n(
    loaded: Page, n_select: int, new_icon: str
):
    loaded.check("#only-attention")
    loaded.wait_for_timeout(100)

    boxes = loaded.locator(f"{ROW} .sel-box")
    assert boxes.count() >= n_select, "fixture doesn't have enough attention rows"

    # The selection bar (with the one "Icon & color…" button) only appears
    # once rows are ticked; at rest its tools are hidden AND disabled.
    assert loaded.locator("#bulk-icon").is_disabled()
    assert loaded.locator("#more-btn").is_disabled()
    assert loaded.locator("#selcount").is_hidden()

    for i in range(n_select):
        boxes.nth(i).check()

    # the label also carries a "clear" link, so assert on the count itself
    assert loaded.evaluate("SEL.size") == n_select
    assert f"{n_select} selected" in loaded.text_content("#selcount")
    assert loaded.locator("#selcount").is_visible()
    assert loaded.locator("#bulk-icon").is_enabled()

    before_attention = loaded.evaluate("DATA.totals.attention")

    loaded.click("#bulk-icon")
    loaded.click(f'#mark-dialog .icon-pick[data-icon="{new_icon}"]')
    # Nothing is applied until Apply.
    assert loaded.evaluate("DATA.totals.attention") == before_attention
    loaded.click("#bulk-apply")
    loaded.wait_for_timeout(100)

    after_attention = loaded.evaluate("DATA.totals.attention")
    assert after_attention == before_attention - n_select
    assert loaded.locator("#mark-modal").is_hidden()

    loaded.uncheck("#only-attention")


# ---------------------------------------------------------------------------
# Name edits survive to export
# ---------------------------------------------------------------------------


def test_name_edit_persists_into_data_and_exported_gpx(loaded: Page):
    first_row = loaded.locator("#folders tbody tr").first
    uid = first_row.get_attribute("data-uid")
    new_name = "ZZZ_PLAYWRIGHT_RENAME_TEST"

    name_input = first_row.locator(".name-in")
    name_input.fill(new_name)
    name_input.dispatch_event("change")
    loaded.wait_for_timeout(100)

    item = loaded.evaluate(f"DATA.groups.flatMap(g => g.items).find(i => i.uid === {uid!r})")
    assert item is not None
    assert item["name"] == new_name

    zip_bytes = export_zip_bytes(loaded)
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

    found_in = [
        name
        for name in zf.namelist()
        if name.endswith(".gpx") and f"<name>{new_name}</name>" in zf.read(name).decode()
    ]
    assert found_in, f"{new_name!r} not found in any exported GPX file"


# ---------------------------------------------------------------------------
# Export manifest
# ---------------------------------------------------------------------------


def test_export_manifest_batch_and_markup_counts_match_totals(loaded: Page):
    totals = loaded.evaluate("DATA.totals")

    export_zip_bytes(loaded)
    manifest = loaded.evaluate("MANIFEST")

    assert len(manifest) == totals["folders"]
    assert sum(entry["count"] for entry in manifest) == totals["items"]


def test_export_produces_a_readable_zip_of_gpx_with_areas_as_gpx(loaded: Page):
    zip_bytes = export_zip_bytes(loaded)
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

    names = zf.namelist()
    assert any(n.endswith(".gpx") for n in names)
    # Areas are onX Area routes in GPX (ENG-05): onX ignores KML area colours.
    assert any(n.endswith("_Areas.gpx") for n in names)
    assert not [n for n in names if n.endswith(".kml")]
    assert names[-1] == "instructions.txt"
    # Every member must actually be readable/valid (CRC checks out).
    assert zf.testzip() is None


# ---------------------------------------------------------------------------
# Runbook
# ---------------------------------------------------------------------------


def test_instructions_name_each_folder_and_have_no_kml_warning(loaded: Page):
    zip_bytes = export_zip_bytes(loaded)
    manifest = loaded.evaluate("MANIFEST")
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    text = zf.read("instructions.txt").decode("utf-8")
    lines = text.split("\r\n")

    for entry in manifest:
        line = f"{entry['dir']}/    rename to: {entry['folder']}"
        assert line in lines, f"missing folder line: {line!r}"
        for f in entry["files"]:
            assert "    " + f["path"].split("/")[-1] in lines
    assert "**" not in text and "#" not in text.split("\r\n\r\n", 1)[0]

    # Areas no longer go out as KML (ENG-05), so there is no KML flag in the
    # manifest and no KML warning, in instructions.txt or on screen.
    assert not any("kml" in f for e in manifest for f in e["files"])
    assert "KML" not in text
    assert "KML" not in loaded.locator("#runbook").inner_text()


# ---------------------------------------------------------------------------
# Export screen (UI-31): one box per folder, Download all / this folder
# ---------------------------------------------------------------------------


def _done(page: Page) -> None:
    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)


def test_export_screen_is_one_box_per_folder_name_download_and_files(loaded: Page):
    _done(loaded)
    manifest = loaded.evaluate("MANIFEST")
    done = loaded.locator("#done-stage")
    # The tick boxes (which only greyed a row) and the boxed explanation are gone.
    expect(done.locator("input")).to_have_count(0)
    expect(done.locator(".runbook-intro")).to_have_count(0)
    expect(done.get_by_role("button", name="Copy")).to_have_count(0)
    expect(loaded.locator("#download")).to_have_text("Download all")
    expect(done.locator(".done-hint")).to_have_text("One zip with every folder and instructions.txt")
    expect(done.locator(".rb-intro")).to_have_text(
        "Import each folder into onX on a computer; onX will use a default datetime stamp for the folder name. Importing needs onX Premium or Elite.")
    boxes = done.locator(".rb-step")
    expect(boxes).to_have_count(len(manifest))
    # Round 4 (owner's ExportScreen mockup): each box is the folder name as its
    # heading, a Download button and the file chips. No counts, no steps.
    expect(done.locator(".rb-dl")).to_have_text(["Download"] * len(manifest))
    for i, e in enumerate(manifest):
        box = boxes.nth(i)
        expect(box.locator("h2")).to_have_text(e["folder"])
        expect(box.locator(".rb-dl")).to_have_attribute("aria-label", f"Download {e['folder']}")
        expect(box.get_by_role("button", name=f"Download {e['folder']}", exact=True)).to_have_count(1)
        expect(box.locator(".rb-file")).to_have_text([f["path"].split("/")[-1] for f in e["files"]])
        expect(box.locator(":scope > *")).to_have_count(2)        # the head and the chips
        expect(box.locator("ol, li")).to_have_count(0)
    # Bitterroots has both kinds: Paddling writes one file, Unorganized three.
    assert {len(e["files"]) for e in manifest} >= {1, 3}
    for gone in ("markup", "Rename it to", "Import map data", "Download this folder", "Import all"):
        expect(done).not_to_contain_text(gone)


def test_download_all_and_each_folder_download(loaded: Page):
    _done(loaded)
    manifest = loaded.evaluate("MANIFEST")
    with loaded.expect_download() as dl:
        loaded.click("#download")
    assert dl.value.suggested_filename == "onx_ready.zip"
    full = zipfile.ZipFile(dl.value.path())
    # Download all's layout: NN_Name/ per folder in screen order, then instructions.txt.
    assert full.namelist() == [f["path"] for e in manifest for f in e["files"]] + ["instructions.txt"]
    btns = loaded.locator(".rb-dl")
    for i, e in enumerate(manifest):
        # Chromium drops an 11th download started within half a second of the
        # first ten (measured); a person never clicks that fast.
        loaded.wait_for_timeout(300)
        with loaded.expect_download() as dl:
            btns.nth(i).click()
        # Named after its NN_Name/ directory, so "A/B" and "A_B" can't both be A_B.zip.
        nn_dir = e["files"][0]["path"].split("/")[0]
        assert dl.value.suggested_filename == f"{nn_dir}.zip"
        one = zipfile.ZipFile(dl.value.path())
        assert one.namelist() == [f["path"] for f in e["files"]]
        for name in one.namelist():
            assert one.read(name) == full.read(name), name
    expect(loaded.locator("#status")).not_to_have_class(re.compile(r"\berr\b"))


def test_export_screen_warnings_sit_above_the_folder_boxes(fresh_page, tmp_path):
    """Dropped items, long notes and the account limit still warn, above the boxes."""
    square = [[-114.0, 45.0], [-114.1, 45.0], [-114.1, 45.1], [-114.0, 45.0]]
    feats = [{"type": "Feature", "id": "f1", "geometry": None,
              "properties": {"class": "Folder", "title": "Big"}},
             {"type": "Feature", "id": "b", "geometry": {"type": "Polygon", "coordinates": []},
              "properties": {"class": "Shape", "title": "Broken", "folderId": "f1"}},
             {"type": "Feature", "id": "a", "geometry": {"type": "Polygon", "coordinates": [square]},
              "properties": {"class": "Shape", "title": "Long", "folderId": "f1",
                             "description": "x" * 600}}]
    feats += [{"type": "Feature", "id": f"w{k}",
               "geometry": {"type": "Point", "coordinates": [-114 + k / 1e4, 45.0]},
               "properties": {"class": "Marker", "title": f"P{k}", "folderId": "f1"}}
              for k in range(3000)]
    path = tmp_path / "big.json"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    fresh_page.set_input_files("#file", str(path))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=60000)
    _done(fresh_page)
    host = fresh_page.locator("#runbook")
    warns = host.locator(".note.warn")
    expect(warns).to_have_count(3)
    expect(warns.nth(0)).to_contain_text("1 item wasn't exported: it has no coordinates.")
    expect(warns.nth(1)).to_have_text("Item \u201cLong\u201d is over the length limit and will be truncated by onX.")
    expect(warns.nth(2)).to_contain_text("onX accounts hold at most 3,000 markups; this map has 3,002.")
    # Every warning comes before the first folder box.
    order = host.locator(":scope > *").evaluate_all("els => els.map(e => e.className)")
    assert order[:3] == ["note warn"] * 3 and order[3:] == ["rb-step"]
    expect(host.locator(".rb-step h2")).to_have_text("Big")
    _wide(fresh_page)
    _shot(fresh_page, "fb-2b-export-long-note-warning")


def test_export_screen_back_and_start_over(loaded: Page):
    _done(loaded)
    loaded.click("#back")
    expect(loaded.locator("body")).to_have_attribute("data-stage", "edit")
    assert loaded.locator(ROW).count() > 0
    _done(loaded)
    loaded.locator("#done-stage .newmap").click()
    loaded.click("#confirm .confirm-actions button:text-is('Start over')")
    expect(loaded.locator("body")).to_have_attribute("data-stage", "drop")
    assert loaded.evaluate("DATA === null && ZIP === null")
    assert loaded.evaluate("document.querySelector('#runbook').childElementCount") == 0


def test_loading_a_map_leaves_no_status_line_above_export(loaded: Page):
    """Owner feedback 2026-10-24: no "Map loaded" over Export; the line is for
    real messages (a move, an error), and the "Reading …" line is cleared."""
    _wide(loaded)
    st = loaded.locator("#status")
    expect(st).to_have_text("")
    assert "Map loaded" not in loaded.inner_text("body")
    _shot(loaded, "fb-3-no-map-loaded")
    # Real messages still show there.
    _drag(loaded, _first_row(loaded, "Lost Trail Pass").locator(".note-btn"), _rail(loaded, "Paddling"))
    expect(st).to_have_text(re.compile(r"^Moved 1 item to Paddling\."))


def test_a_ready_status_line_clears_itself_but_keeps_its_announcement_first(loaded: Page):
    st = loaded.locator("#status")
    loaded.evaluate("STATUS_LINGER_MS = 2500; setStatus('Moved 1 item to X.', 'ready')")
    loaded.wait_for_timeout(1700)
    assert st.text_content() == "Moved 1 item to X."
    expect(st).to_have_text("", timeout=4000)
    # An error is not a receipt: it stays.
    loaded.evaluate("setStatus('Boom', 'err')")
    loaded.wait_for_timeout(3000)
    assert st.text_content() == "Boom"


# ---------------------------------------------------------------------------
# Negative: malformed input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_content,case_id",
    [
        ("this is not json at all { [ garbage", "invalid_json_syntax"),
        ("", "empty_file"),
    ],
)
def test_malformed_file_surfaces_error_without_breaking_app(
    fresh_page: Page, tmp_path: Path, bad_content: str, case_id: str
):
    bad_file = tmp_path / f"{case_id}.json"
    bad_file.write_text(bad_content)

    fresh_page.set_input_files("#file", str(bad_file))
    fresh_page.wait_for_timeout(1000)

    status_text = fresh_page.text_content("#status")
    status_class = fresh_page.get_attribute("#status", "class")

    assert "err" in (status_class or "")
    assert status_text is not None and len(status_text) > 0

    # The app must NOT have advanced to the edit stage.
    drop_class = fresh_page.get_attribute("#drop-stage", "class") or ""
    edit_class = fresh_page.get_attribute("#edit-stage", "class") or ""
    assert "hidden" not in drop_class
    assert "hidden" in edit_class
    assert fresh_page.evaluate("window.__cairnLoaded") is not True

    # Recovery: the SAME page must still be able to load a real file afterward.
    fresh_page.evaluate("window.__cairnLoaded = false")
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=30000)

    totals = fresh_page.evaluate("DATA.totals")
    assert totals == EXPECTED_TOTALS


def test_every_onx_icon_has_a_glyph(fresh_page):
    """The picker must never fall back to the default pin for a real onX icon.

    Guards against onX's vocabulary growing past web/icons.js.
    """
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)
    missing = fresh_page.evaluate(
        "DATA.icons.filter(i => !(i in ONX_GLYPHS))"
    )
    assert missing == [], f"onX icons with no glyph defined: {missing}"
    # ...and every one is a drawing, not a two-letter abbreviation (UI-29).
    lettered = fresh_page.evaluate("DATA.icons.filter(i => !ONX_GLYPHS[i].path)")
    assert lettered == [], f"onX icons drawn as letters: {lettered}"


def test_select_all_respects_the_active_filter(fresh_page):
    """Select-all must select what is SHOWN, not the whole file.

    Filtering to 'creek' then selecting all should select the creek items --
    selecting all 177 would silently apply a bulk edit to items the user
    filtered away.
    """
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    _select_all_shown(fresh_page)
    fresh_page.wait_for_timeout(300)
    assert fresh_page.evaluate("SEL.size") == EXPECTED_TOTALS["items"]

    _clear_selection(fresh_page)
    fresh_page.wait_for_timeout(300)
    assert fresh_page.evaluate("SEL.size") == 0

    fresh_page.fill("#filter", "creek")
    fresh_page.wait_for_timeout(400)
    shown = fresh_page.locator(ROW).count()
    assert 0 < shown < EXPECTED_TOTALS["items"]

    _select_all_shown(fresh_page)
    fresh_page.wait_for_timeout(300)
    assert fresh_page.evaluate("SEL.size") == shown


def test_folder_checkbox_selects_only_that_folder(fresh_page):
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    first_count = fresh_page.evaluate("DATA.groups[0].items.length")
    fresh_page.locator(".folder-all").first.check()
    fresh_page.wait_for_timeout(300)
    assert fresh_page.evaluate("SEL.size") == first_count
    assert fresh_page.evaluate("SEL.size") < EXPECTED_TOTALS["items"]


def test_every_waypoint_explains_its_icon(fresh_page):
    """Every row must be able to answer "why this icon?".

    The engine has always computed this (IconResolver.IconDecision.reasons,
    icon_resolver.py:24-32) and every caller discarded it, so the UI could only
    say "needs attention" without saying why.
    """
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    missing = fresh_page.evaluate(
        "DATA.groups.flatMap(g => g.items).filter(i => !i.why || !i.why.trim())"
        ".map(i => i.name)"
    )
    assert missing == [], f"items with no explanation: {missing[:5]}"

    # every icon chip carries it as a tooltip
    chips = fresh_page.locator(".icon-btn[title]").count()
    waypoints = fresh_page.evaluate(
        "DATA.groups.flatMap(g => g.items).filter(i => i.kind === 'waypoints').length"
    )
    assert chips == waypoints

    # and the flagged ones get an explicit '?' affordance
    marks = fresh_page.locator(".whymark").count()
    assert marks == fresh_page.evaluate("DATA.totals.attention")


def test_explanations_distinguish_why_an_icon_was_chosen(fresh_page):
    """The reason must be specific, not one generic string for everything."""
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    reasons = fresh_page.evaluate(
        "[...new Set(DATA.groups.flatMap(g => g.items)"
        ".filter(i => i.kind === 'waypoints').map(i => i.why))]"
    )
    assert len(reasons) >= 3, f"explanations are not specific enough: {reasons}"
    joined = " ".join(reasons)
    assert "CalTopo symbol" in joined  # resolved via the source symbol
    assert "in the name" in joined     # resolved via a name keyword
    assert "default pin" in joined     # fell through


def test_setting_an_icon_updates_its_explanation(fresh_page):
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)
    fresh_page.evaluate(
        "(() => { const it = DATA.groups.flatMap(g=>g.items)"
        ".find(i => i.needs_attention); window.__u = it.uid; edit(it, {icon:'Camp'}); })()"
    )
    fresh_page.wait_for_timeout(300)
    why = fresh_page.evaluate(
        "DATA.groups.flatMap(g=>g.items).find(i => i.uid === window.__u).why"
    )
    assert why == "You set this icon."


def test_deliberately_choosing_the_default_pin_marks_it_resolved(fresh_page):
    """Agreeing with the tool is an answer, not an outstanding question."""
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    before = fresh_page.evaluate("DATA.totals.attention")
    fresh_page.evaluate(
        "(() => { const it = DATA.groups.flatMap(g=>g.items).find(i=>i.needs_attention);"
        "  window.__u = it.uid; edit(it, {icon:'Location'}); })()"
    )
    fresh_page.wait_for_timeout(300)

    it = fresh_page.evaluate(
        "DATA.groups.flatMap(g=>g.items).find(i => i.uid === window.__u)"
    )
    assert it["icon"] == "Location"
    assert it["confirmed"] is True
    assert it["needs_attention"] is False
    assert it["why"] == "You chose the default pin."
    assert fresh_page.evaluate("DATA.totals.attention") == before - 1


@pytest.mark.parametrize("kind", ["waypoints", "tracks", "shapes"])
def test_type_filter_shows_only_that_kind(fresh_page, kind):
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    _set_type(fresh_page, kind)
    fresh_page.wait_for_timeout(400)

    expected = fresh_page.evaluate(
        f"DATA.groups.flatMap(g=>g.items).filter(i => i.kind === '{kind}').length"
    )
    assert fresh_page.locator(ROW).count() == expected
    assert expected > 0


def test_uids_are_opaque_and_unique(fresh_page):
    """Each item's uid is an opaque id that says nothing about its folder or
    position (ENG-07), so the UI can never decode one back to a place.

    It replaces a regression test for the old `<folder>::<kind>::<index>` uid,
    whose index was once a running total across kinds and made the export's
    exclusion filter drop the wrong features.
    """
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    uids = fresh_page.evaluate("DATA.groups.flatMap(g=>g.items).map(i=>i.uid)")
    assert uids and len(uids) == len(set(uids))
    keys = fresh_page.evaluate("DATA.groups.map(g=>g.key)")
    assert not [u for u in uids if "::" in u or any(k in u for k in keys)]


def test_folder_primitives_run_in_pyodide_and_an_edit_follows_a_moved_item(fresh_page):
    """ENG-07: bridge.move_items works in the browser engine, and an edit the UI
    keyed by uid before the move lands in the item's NEW folder on export.
    (No folder UI yet: PR-C adds it. This drives the bridge directly.)"""
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)
    res = fresh_page.evaluate("""() => {
        const it = DATA.groups[1].items.find(i => i.kind === 'waypoints');
        edit(it, {name: 'Moved by uid'});
        py.globals.set('_t_uids', JSON.stringify([it.uid]));
        return JSON.parse(py.runPython("bridge.move_items(_t_uids, None, 'Moved here')"));
    }""")
    fresh_page.wait_for_timeout(300)
    assert res["ok"] and res["created"] and res["moved"] == 1
    zf = _export_zip(fresh_page)
    n = [f["name"] for f in res["folders"] if f["uids"]].index("Moved here") + 1   # by name
    moved = zf.read(f"{n:02d}_Moved_here/Moved_here_Waypoints.gpx").decode()
    assert moved.count("<wpt ") == 1 and "<name>Moved by uid</name>" in moved
    blob = "".join(zf.read(m).decode() for m in zf.namelist() if m.endswith(".gpx"))
    assert blob.count("<name>Moved by uid</name>") == 1


def test_excluded_items_are_left_out_of_the_export(fresh_page):
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    _set_type(fresh_page, "shapes")
    fresh_page.wait_for_timeout(400)
    _select_all_shown(fresh_page)
    fresh_page.wait_for_timeout(300)
    n_areas = fresh_page.evaluate("SEL.size")
    assert n_areas > 0

    _menu_action(fresh_page, "#bulk-exclude")
    fresh_page.wait_for_timeout(400)
    assert fresh_page.evaluate("DATA.totals.excluded") == n_areas

    _set_type(fresh_page, "")
    fresh_page.wait_for_timeout(300)
    zf = _export_zip(fresh_page)
    areas = [n for n in zf.namelist() if n.endswith((".kml", "_Areas.gpx"))]
    assert areas == [], f"excluded areas still exported: {areas}"


def test_description_edit_reaches_the_exported_gpx(fresh_page):
    """onX shows <desc> as the markup's Notes, so this is a real user-visible field."""
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    marker = "Reliable spring, 200m below the col"
    fresh_page.evaluate(
        "(m) => { const it = DATA.groups.flatMap(g=>g.items)"
        ".find(i => i.kind === 'waypoints'); edit(it, {desc: m}); }", marker
    )
    fresh_page.wait_for_timeout(300)

    zf = _export_zip(fresh_page)
    blob = "".join(
        zf.read(n).decode("utf-8", "replace") for n in zf.namelist() if n.endswith(".gpx")
    )
    assert f"<desc>{marker}</desc>" in blob


@pytest.mark.parametrize("field,cls", [("name", ".name-in"), ("desc", ".desc-in")])
def test_escape_reverts_an_edit_instead_of_committing_it(fresh_page, field, cls):
    """Escape blurs, and blur commits -- so Escape used to SAVE the edit.

    Emptying a name and changing your mind must not persist an empty string.
    The note is edited in an inline textarea opened from the row's note button.
    """
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    original = fresh_page.evaluate(f"DATA.groups[0].items[0].{field}")
    if field == "desc":
        fresh_page.locator(f"{ROW} .note-btn").first.click()
    box = fresh_page.locator(cls).first
    box.click()
    box.fill("")
    box.press("Escape")
    fresh_page.wait_for_timeout(300)

    assert fresh_page.evaluate(f"DATA.groups[0].items[0].{field}") == original
    if field == "desc":
        # Escape closed the editor; reopening shows the untouched note.
        assert fresh_page.locator(".desc-in").count() == 0
        fresh_page.locator(f"{ROW} .note-btn").first.click()
    assert fresh_page.locator(cls).first.input_value() == original


def test_note_editor_keeps_line_breaks_and_applies_with_ctrl_enter(loaded: Page):
    """Enter is a newline in the note editor; Ctrl/Cmd+Enter applies."""
    uid = loaded.locator(ROW).first.get_attribute("data-uid")
    loaded.locator(f"{ROW} .note-btn").first.click()
    box = loaded.locator(".desc-in").first
    box.fill("first line")
    box.press("End")
    box.press("Enter")
    box.type("second line")
    box.press("ControlOrMeta+Enter")
    loaded.wait_for_timeout(200)

    desc = loaded.evaluate(f"DATA.groups.flatMap(g=>g.items).find(i=>i.uid==={uid!r}).desc")
    assert desc == "first line\nsecond line"
    assert loaded.locator(".desc-in").count() == 0
    # The preview shows the first line only (round 4); the rest is on hover.
    clipped = loaded.locator(f'tr[data-uid="{uid}"] .note-text').inner_text()
    assert clipped == "first line"


def test_note_editor_apply_and_cancel_buttons(loaded: Page):
    uid = loaded.locator(ROW).first.get_attribute("data-uid")
    get = f"DATA.groups.flatMap(g=>g.items).find(i=>i.uid==={uid!r}).desc"
    original = loaded.evaluate(get)

    loaded.locator(f"{ROW} .note-btn").first.click()
    loaded.locator(".desc-in").first.fill("discard me")
    loaded.click(".note-cancel")
    assert loaded.evaluate(get) == original

    loaded.locator(f"{ROW} .note-btn").first.click()
    loaded.locator(".desc-in").first.fill("keep me")
    loaded.click(".note-apply")
    assert loaded.evaluate(get) == "keep me"
    assert loaded.evaluate(f"EDITS[{uid!r}].desc") == "keep me"


def test_note_editor_opens_at_the_start_of_a_long_note(loaded: Page):
    long_note = "\n".join(f"line {i} of a long note" for i in range(60))
    uid = loaded.locator(ROW).first.get_attribute("data-uid")
    loaded.evaluate(
        "([u, v]) => { DATA.groups.flatMap(g=>g.items).find(i=>i.uid===u).desc = v; renderFolders(); }",
        [uid, long_note],
    )
    loaded.locator(f"{ROW} .note-btn").first.click()
    ta = loaded.locator(".desc-in").first
    expect(ta).to_be_focused()
    assert loaded.evaluate(
        "(() => { const t = document.querySelector('.desc-in');"
        " return [t.selectionStart, t.selectionEnd, t.scrollTop, t.scrollHeight > t.clientHeight]; })()"
    ) == [0, 0, 0, True]


def test_note_editor_has_no_line_break_hint_and_buttons_say_save(loaded: Page):
    loaded.locator(f"{ROW} .note-btn").first.click()
    assert "Line breaks kept" not in loaded.inner_text(".note-ed")
    assert loaded.locator(".note-apply").inner_text() == "Save"
    loaded.click(".note-cancel")
    loaded.locator(f"{ROW} .icon-btn, {ROW} .line-btn").first.click()
    assert loaded.locator("#pop-apply").inner_text() == "Save"
    loaded.keyboard.press("Escape")


def test_icon_color_dialog_says_save(loaded: Page):
    loaded.locator(f"{ROW} .sel-box").first.check()
    loaded.click("#bulk-icon")
    assert loaded.locator("#bulk-apply").inner_text() == "Save"
    loaded.click(".bulk-cancel")


def test_marker_popover_changes_one_items_icon_and_color(loaded: Page):
    """Clicking a row's marker opens the single-item editor; previews are live
    and nothing changes until Apply."""
    loaded.check("#only-attention")
    loaded.wait_for_timeout(100)
    row = loaded.locator(ROW).first
    uid = row.get_attribute("data-uid")
    get = f"DATA.groups.flatMap(g=>g.items).find(i=>i.uid==={uid!r})"
    before = loaded.evaluate(get)

    row.locator(".icon-btn").click()
    pop = loaded.locator("#mark-pop")
    assert pop.is_visible()
    # every onX icon is offered, not just a shortlist
    assert pop.locator(".icon-pick").count() == loaded.evaluate("DATA.icons.length")
    pop.locator('.swatch-btn[aria-label="Blue"]').click()
    pop.locator(".icon-search").fill("summ")
    # The filter hides the other buttons rather than removing them (UI-29).
    assert pop.locator(".icon-pick:visible").count() == 1
    assert pop.locator(".icon-pick").count() == loaded.evaluate("DATA.icons.length")
    pop.locator('.icon-pick[data-icon="Summit"]').click()
    # The header shows the picked marker, not words for it (UI-26).
    assert pop.locator(".pop-desc").count() == 0
    assert pop.locator(".pop-preview svg.marker path").first.get_attribute("fill") == "#087AFF"
    assert loaded.evaluate(get)["icon"] == before["icon"]  # not yet applied

    loaded.click("#pop-apply")
    loaded.wait_for_timeout(150)
    after = loaded.evaluate(get)
    assert after["icon"] == "Summit"
    assert after["color"] == "rgba(8,122,255,1)"
    assert after["needs_attention"] is False
    assert pop.is_hidden()


def test_icon_grids_stay_neutral_when_a_color_is_picked(loaded: Page):
    """The icon choices are drawn in ink outline on paper; picking a color recolors
    only the item being edited (the popover's preview, the dialog's Now -> After),
    never the grid of choices."""
    grid_fills = ("els => [...new Set(els.map(e => e.querySelector('svg.marker path')"
                  ".getAttribute('fill')))]")
    _set_type(loaded, "waypoints")
    loaded.locator(f"{ROW} .icon-btn").first.click()
    pop = loaded.locator("#mark-pop")
    pop.locator('.swatch-btn[aria-label="Purple"]').click()
    assert pop.locator(".icon-pick").evaluate_all(grid_fills) == ["#FFFDF7"]
    assert pop.locator(".pop-preview svg.marker path").first.get_attribute("fill") == "#800080"
    pop.locator(".pop-cancel").click()

    loaded.locator(f"{ROW} .sel-box").nth(0).check()
    loaded.locator(f"{ROW} .sel-box").nth(1).check()
    loaded.click("#bulk-icon")
    d = loaded.locator("#mark-dialog")
    d.locator('.swatch-btn[aria-label="Lime"]').click()
    assert d.locator(".icon-pick").evaluate_all(grid_fills) == ["#FFFDF7"]
    # Now keeps each item's color; After shows the picked one
    preview = d.locator(".na-rows svg.marker > path").evaluate_all("els => els.map(e => e.getAttribute('fill'))")
    assert preview[1::2] == ["#84D400"] * 2 and "#84D400" not in preview[0::2]


_STASH_PICKS = "sel => { window.__picks = [...document.querySelector(sel).children]; }"
_SAME_PICKS = ("sel => { const now = [...document.querySelector(sel).children];"
               " return now.length === window.__picks.length && now.every((e, i) => e === window.__picks[i]); }")
_FOCUSED_ICON = "() => document.activeElement.dataset ? document.activeElement.dataset.icon || null : null"


def _assert_list_is_static(page: Page, scope: str):
    """Pick by click, by keyboard and then a colour: the icon list is never rebuilt,
    focus stays on the picked button, and only aria-pressed moves (UI-29)."""
    grid = f"{scope} .icon-grid"
    page.evaluate(_STASH_PICKS, grid)
    picks = page.locator(f"{grid} .icon-pick")

    picks.nth(3).click()
    first = picks.nth(3).get_attribute("data-icon")
    assert page.evaluate(_FOCUSED_ICON) == first
    assert picks.nth(3).get_attribute("aria-pressed") == "true"
    assert page.locator(f'{grid} .icon-pick[aria-pressed="true"]').count() == 1
    assert page.evaluate(_SAME_PICKS, grid)

    picks.nth(3).press("Tab")   # keyboard to the next option, then pick it with Enter
    second = picks.nth(4).get_attribute("data-icon")
    assert page.evaluate(_FOCUSED_ICON) == second
    page.keyboard.press("Enter")
    assert page.evaluate(_FOCUSED_ICON) == second
    assert picks.nth(4).get_attribute("aria-pressed") == "true"
    assert picks.nth(3).get_attribute("aria-pressed") == "false"
    page.keyboard.press("Space")
    assert page.evaluate(_FOCUSED_ICON) == second
    assert page.evaluate(_SAME_PICKS, grid)

    page.locator(f'{scope} .swatch-btn[aria-label="Red"]').click()
    assert page.evaluate(_SAME_PICKS, grid)

    page.locator(f"{scope} .icon-search").fill("camp")
    assert page.evaluate(_SAME_PICKS, grid)
    assert page.locator(f"{grid} .icon-pick:visible").count() == 4
    page.locator(f"{scope} .icon-search").fill("zzzz")
    expect(page.locator(f"{grid} .grid-empty")).to_have_text("No icon matches “zzzz”.")
    page.locator(f"{scope} .icon-search").fill("")
    assert page.locator(f"{grid} .icon-pick:visible").count() == page.evaluate("DATA.icons.length")
    assert page.evaluate(_SAME_PICKS, grid)


def test_icon_list_is_built_once_and_keeps_focus_on_a_pick(loaded: Page):
    """Choosing an icon used to rebuild the grid via innerHTML, so keyboard focus
    fell to <body>. The list is now built once per open (UI-29)."""
    _set_type(loaded, "waypoints")
    loaded.locator(f"{ROW} .icon-btn").first.click()
    _assert_list_is_static(loaded, "#mark-pop")
    loaded.locator("#mark-pop .pop-cancel").click()

    loaded.locator(f"{ROW} .sel-box").nth(0).check()
    loaded.locator(f"{ROW} .sel-box").nth(1).check()
    loaded.click("#bulk-icon")
    _assert_list_is_static(loaded, "#mark-dialog")
    loaded.click(".bulk-cancel")


def test_icon_list_rows_are_two_columns_with_the_marker_centred(loaded: Page):
    """Option C (UI-29): two columns, marker left of the name, at least 44px rows,
    names wrap only between words and the marker sits on the row's centre line."""
    _set_type(loaded, "waypoints")
    loaded.locator(f"{ROW} .icon-btn").first.click()
    m = loaded.evaluate("""() => {
      const picks = [...document.querySelectorAll('#mark-pop .icon-pick')];
      const lefts = new Set(picks.map(p => Math.round(p.getBoundingClientRect().left)));
      const off = picks.map(p => {
        const r = p.getBoundingClientRect(), s = p.querySelector('svg').getBoundingClientRect();
        return Math.abs((s.top + s.height / 2) - (r.top + r.height / 2));
      });
      const span = picks[0].querySelector('span');
      const cs = getComputedStyle(span);
      return { cols: lefts.size, minH: Math.min(...picks.map(p => p.getBoundingClientRect().height)),
               drift: Math.max(...off), wrap: cs.overflowWrap, brk: cs.wordBreak,
               svgLeftOfName: picks.every(p => p.querySelector('svg').getBoundingClientRect().right
                                                 <= p.querySelector('span').getBoundingClientRect().left) };
    }""")
    assert m["cols"] == 2, m
    assert m["minH"] >= 44, m
    assert m["drift"] <= 1, m
    assert m["svgLeftOfName"], m
    assert (m["wrap"], m["brk"]) == ("normal", "normal"), m
    assert loaded.locator("#mark-pop").bounding_box()["width"] == 440


_LINE = "DATA.groups.flatMap(g=>g.items).find(i=>i.uid==={uid!r})"


def test_line_rows_draw_their_own_style(loaded: Page):
    """A dashed line's mark is drawn dashed; a solid one is not."""
    styles = loaded.evaluate("DATA.groups.flatMap(g=>g.items).filter(i=>i.kind==='tracks').map(i=>i.style)")
    assert styles.count("dash") == 6 and "solid" in styles   # Bitterroots: 6 dashed lines
    _set_type(loaded, "tracks")
    dashed = loaded.locator(f"{ROW} .line-btn svg path[stroke-dasharray]")
    assert dashed.count() == 6 * 2   # underlay + line, per dashed row


def test_line_popover_sets_style_and_weight(loaded: Page):
    """One line: Style and Weight toggles under the color row, a map-strip
    preview, nothing changed until Apply, and the export carries the result."""
    _set_type(loaded, "tracks")
    row = loaded.locator(ROW).filter(has=loaded.locator('.line-btn')).first
    uid = row.get_attribute("data-uid")
    get = _LINE.format(uid=uid)
    before = loaded.evaluate(get)
    assert before["style"] == "solid" or before["style"] == "dash"
    row.locator(".line-btn").click()
    pop = loaded.locator("#mark-pop")
    assert pop.locator(".pop-map svg").count() == 1
    assert pop.locator(".tog").count() == 4
    assert pop.get_by_text("Lines take the color only").count() == 0
    target = "dash" if before["style"] == "solid" else "solid"
    pop.locator(f'.tog[data-style="{target}"]').click()
    pop.locator('.tog[data-weight="6.0"]').click()
    assert pop.locator(f'.tog[data-style="{target}"]').get_attribute("aria-pressed") == "true"
    assert (pop.locator(".pop-map path").last.get_attribute("stroke-dasharray") is not None) == (target == "dash")
    assert loaded.evaluate(get)["style"] == before["style"]   # not yet applied
    loaded.click("#pop-apply")
    after = loaded.evaluate(get)
    assert (after["style"], after["weight"]) == (target, "6.0")

    loaded.click("#export")
    expect(loaded.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    with loaded.expect_download() as dl:
        loaded.click("#download")
    zf = zipfile.ZipFile(dl.value.path())
    gpx = "".join(zf.read(n).decode() for n in zf.namelist() if n.endswith("_Tracks.gpx"))
    import html
    blocks = [b for b in re.findall(r"<trk>.*?</trk>", gpx, flags=re.S)
              if html.unescape(re.search(r"<name>(.*?)</name>", b, flags=re.S).group(1)) == after["name"]]
    assert blocks and all(f"<onx:style>{target}</onx:style>" in b and "<onx:weight>6.0</onx:weight>" in b for b in blocks)


def test_one_dialog_sets_the_style_of_several_lines(loaded: Page):
    """UI-36: one button and one dialog for lines and areas (no separate Line
    style…): Color, then Style and Weight side by side, each starting on
    "Leave as is"; a pick applies to every selected line, a second click on the
    picked toggle (or its "Leave as is") un-picks it."""
    expect(loaded.locator("#bulk-line")).to_have_count(0)
    _set_type(loaded, "tracks")
    rows = loaded.locator(ROW)
    uids = [rows.nth(i).get_attribute("data-uid") for i in range(2)]
    for i in range(2):
        rows.nth(i).locator(".sel-box").check()
    expect(loaded.locator("#bulk-icon")).to_have_text("Color & style…")
    before = [loaded.evaluate(_LINE.format(uid=u)) for u in uids]
    loaded.click("#bulk-icon")
    d = loaded.locator("#mark-dialog")
    expect(d.locator("h2")).to_have_text("Change 2 items")
    expect(d.locator(".sec-row .label")).to_have_text(["Color", "Style", "Weight"])
    expect(d.locator(".reset-chip")).to_have_text(["Leave as is"] * 3)
    expect(d.locator('.reset-chip[aria-pressed="true"]')).to_have_count(3)
    expect(d.locator(".fill-sec, .icons")).to_have_count(0)      # no areas, no waypoints
    d.locator('.tog[data-weight="6.0"]').click()
    expect(d.locator(".weight-reset")).to_have_attribute("aria-pressed", "false")
    d.locator('.tog[data-weight="6.0"]').click()          # un-pick: weights stay as they are
    assert d.locator('.tog[aria-pressed="true"]').count() == 0
    d.locator('.tog[data-style="dot"], .tog[data-style="dash"]').last.click()
    d.locator(".style-reset").click()                     # "Leave as is" un-picks too
    assert d.locator('.tog[aria-pressed="true"]').count() == 0
    d.locator('.tog[data-style="dash"]').click()
    loaded.click("#bulk-apply")
    expect(loaded.locator("#mark-modal")).to_be_hidden()
    after = [loaded.evaluate(_LINE.format(uid=u)) for u in uids]
    assert [a["style"] for a in after] == ["dash", "dash"]
    assert [a["weight"] for a in after] == [b["weight"] for b in before]


def test_area_popover_sets_style_and_weight(loaded: Page):
    """One area: the same Style and Weight toggles as a line (UI-25), its mark
    redrawn in them, and the export's <onx:style>/<onx:weight> carry the pick."""
    _set_type(loaded, "shapes")
    row = loaded.locator(ROW).first
    uid = row.get_attribute("data-uid")
    get = _LINE.format(uid=uid)
    before = loaded.evaluate(get)
    assert (before["style"], before["weight"]) == ("solid", "4.0")   # Bitterroots: CalTopo width 2
    assert before["fill"].startswith("rgba(")
    row.locator(".line-btn").click()
    pop = loaded.locator("#mark-pop")
    assert pop.locator(".tog").count() == 4
    assert pop.locator(".pop-map").count() == 0            # areas keep their patch preview
    pop.locator('.tog[data-style="dash"]').click()
    pop.locator('.tog[data-weight="6.0"]').click()
    assert pop.locator(".pop-preview path[stroke-dasharray]").count() == 2
    assert loaded.evaluate(get)["style"] == "solid"        # not yet saved
    loaded.click("#pop-apply")
    after = loaded.evaluate(get)
    assert (after["style"], after["weight"], after["fill"]) == ("dash", "6.0", before["fill"])
    expect(row.locator(".line-btn")).to_have_attribute("aria-label", re.compile(r"Dashed, Thick"))

    loaded.click("#export")
    expect(loaded.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    with loaded.expect_download() as dl:
        loaded.click("#download")
    zf = zipfile.ZipFile(dl.value.path())
    gpx = "".join(zf.read(n).decode() for n in zf.namelist() if n.endswith("_Areas.gpx"))
    import html
    blocks = [b for b in re.findall(r"<rte>.*?</rte>", gpx, flags=re.S)
              if html.unescape(re.search(r"<name>(.*?)</name>", b, flags=re.S).group(1)) == after["name"]]
    # Two Bitterroots areas share this name; exactly the edited one is dashed and thick.
    assert sum("<onx:style>dash</onx:style>" in b and "<onx:weight>6.0</onx:weight>" in b
               and "<onx:fill_color>" in b for b in blocks) == 1
    # (The fill is written as onX's nearest swatch, so the exact value isn't
    # the item's; the item's own fill is unchanged by the style edit, above.)


def test_the_dialog_takes_areas_too_with_a_fill_row(loaded: Page):
    """Several areas: the same dialog, with a Fill row after Style and Weight."""
    _set_type(loaded, "shapes")
    rows = loaded.locator(ROW)
    uids = [rows.nth(i).get_attribute("data-uid") for i in range(2)]
    for i in range(2):
        rows.nth(i).locator(".sel-box").check()
    loaded.click("#bulk-icon")
    d = loaded.locator("#mark-dialog")
    expect(d.locator(".sec-row .label")).to_have_text(["Color", "Style", "Weight", "Fill"])
    expect(d.locator(".fill-btn")).to_have_text("Blue")
    d.locator('.tog[data-style="dash"]').click()
    loaded.click("#bulk-apply")
    expect(loaded.locator("#mark-modal")).to_be_hidden()
    assert [loaded.evaluate(_LINE.format(uid=u))["style"] for u in uids] == ["dash", "dash"]
    expect(loaded.locator("#status")).to_have_text("Changed 2 areas.")


def _keep_fills(page: Page) -> None:
    """Dismiss the load-time area-fill warning (onX files with non-default fills)."""
    page.click("#confirm .confirm-actions button:text-matches('^Keep')")
    expect(page.locator("#confirm")).to_be_hidden()


def test_onx_areas_with_a_fill_warn_and_can_be_left_out(fresh_page: Page):
    """onX resets an imported area's fill to its default blue, so an onX export
    whose areas have another fill (or none) warns once on load, and "Leave these
    out" unticks exactly those areas."""
    fx = FX_DIR / "onx_exports"
    fresh_page.set_input_files("#file", [str(fx / "areas-after-edit.gpx"), str(fx / "areas-after-edit.kml")])
    expect(fresh_page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    dlg = fresh_page.locator("#confirm")
    expect(dlg).to_be_visible()
    expect(fresh_page.locator("#confirm-title")).to_have_text("4 areas will lose their fill")
    expect(fresh_page.locator("#confirm-body")).to_have_text("onX resets area fills to blue on import.")
    fresh_page.click("#confirm .confirm-actions button:text-is('Leave these 4 out')")
    expect(dlg).to_be_hidden()
    expect(fresh_page.locator(f"{ROW}.excluded")).to_have_count(4)


def test_onx_areas_keep_them_changes_nothing(fresh_page: Page):
    fx = FX_DIR / "onx_exports"
    fresh_page.set_input_files("#file", [str(fx / "areas-after-edit.gpx"), str(fx / "areas-after-edit.kml")])
    expect(fresh_page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    _keep_fills(fresh_page)
    expect(fresh_page.locator(f"{ROW}.excluded")).to_have_count(0)
    assert fresh_page.evaluate("Object.keys(EDITS).length") == 0


@pytest.mark.parametrize("files", [["onx_exports/three-round-trips.gpx", "onx_exports/three-round-trips.kml"],
                                   ["bitterroots/Bitterroots__Complete_.json"]],
                         ids=["onx-default-fill", "caltopo"])
def test_no_fill_warning_when_nothing_would_change(fresh_page: Page, files):
    fresh_page.set_input_files("#file", [str(FX_DIR / f) for f in files])
    expect(fresh_page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    fresh_page.wait_for_timeout(300)
    expect(fresh_page.locator("#confirm")).to_be_hidden()


def test_clear_area_fill_is_not_a_fill_change(fresh_page: Page):
    """A transparent fill is deliberate: the load dialog skips it, as the caution mark does."""
    r = fresh_page.evaluate("""() => [
      fillChanges({kind: "shapes", onx_id: "a", fill: "rgba(1,2,3,0)"}),
      fillChanges({kind: "shapes", onx_id: "a", fill: "rgba(1,2,3,0.1)"}),
      fillChanges({kind: "shapes", onx_id: "a", fill: "rgba(74,144,226,0.1)"})]""")
    assert r == [False, True, False]


def test_onx_area_dot_and_extra_thin_are_shown_and_kept(fresh_page: Page):
    """An onX file's dotted and 2.0 areas are drawn and named as such; neither is
    offered as a choice, so no toggle is pressed for them."""
    fx = FX_DIR / "onx_exports"
    fresh_page.set_input_files("#file", [str(fx / "areas-after-edit.gpx"), str(fx / "areas-after-edit.kml")])
    expect(fresh_page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    _keep_fills(fresh_page)
    marks = fresh_page.locator(f"{ROW} .line-btn")
    expect(marks).to_have_count(4)
    labels = [marks.nth(i).get_attribute("aria-label") for i in range(4)]
    assert "Area, Yellow, Solid, Extra thin. Change area" in labels
    assert "Area, Lime, Dotted, Thin. Change area" in labels
    fresh_page.locator(f'{ROW}:has(input[value="test 4"]) .line-btn').click()
    pop = fresh_page.locator("#mark-pop")
    assert pop.locator('.tog[data-style][aria-pressed="true"]').count() == 0
    assert pop.locator('.tog[data-weight="4.0"]').get_attribute("aria-pressed") == "true"


def test_marker_popover_cancel_changes_nothing(loaded: Page):
    row = loaded.locator(ROW).first
    uid = row.get_attribute("data-uid")
    get = f"DATA.groups.flatMap(g=>g.items).find(i=>i.uid==={uid!r})"
    before = loaded.evaluate(get)
    row.locator(".icon-btn, .line-btn").click()
    loaded.locator('#mark-pop .swatch-btn[aria-label="Yellow"]').click()
    loaded.locator("#mark-pop .pop-cancel").click()
    assert loaded.evaluate(get) == before
    assert loaded.evaluate("Object.keys(EDITS).length") == 0


def test_bulk_dialog_palette_follows_the_selection(loaded: Page):
    """Waypoints-only and mixed selections get onX's 10 colors; lines-only get
    the 11-color line palette (adds Fuchsia) when the engine provides it."""
    _set_type(loaded, "waypoints")
    loaded.locator(f"{ROW} .sel-box").nth(0).check()
    loaded.click("#bulk-icon")
    assert loaded.locator("#mark-dialog .swatch-btn").count() == 10
    loaded.click("#mark-dialog .bulk-cancel")
    _clear_selection(loaded)

    _set_type(loaded, "tracks")
    loaded.locator(f"{ROW} .sel-box").nth(0).check()
    loaded.locator(f"{ROW} .sel-box").nth(1).check()
    loaded.click("#bulk-icon")
    n_line_colors = loaded.evaluate("(DATA.line_colors || DATA.colors).length")
    assert loaded.locator("#mark-dialog .swatch-btn").count() == n_line_colors
    assert loaded.locator("#mark-dialog .icon-pick").count() == 0  # lines take no icon
    # live Now -> After preview
    loaded.locator('#mark-dialog .swatch-btn[aria-label="Purple"]').click()
    assert loaded.locator("#mark-dialog .na-after").count() == 0   # marks only, no "Line · Purple"
    after = loaded.locator("#mark-dialog .na-rows .na-cell:nth-child(3n) svg path").evaluate_all(
        "els => [...new Set(els.map(e => e.getAttribute('stroke')).filter(c => c !== '#2A241C'))]")
    assert after == ["#800080"], after
    loaded.click("#bulk-apply")
    colors = loaded.evaluate(
        "DATA.groups.flatMap(g=>g.items).filter(i=>SEL.has(i.uid)).map(i=>i.color)"
    )
    assert colors == ["rgba(128,0,128,1)"] * 2


def test_folder_facet_filters_and_chip_clears_it(loaded: Page):
    g = loaded.evaluate("({key: DATA.groups[1].key, name: DATA.groups[1].name, n: DATA.groups[1].items.length})")
    loaded.locator("#folder-facets .facet-btn").nth(2).click()  # 0 is "All"
    loaded.wait_for_timeout(150)
    assert loaded.locator(ROW).count() == g["n"]
    assert loaded.locator(".folder").count() == 1
    assert f"Folder: {g['name']}" in loaded.inner_text("#chips")

    _select_all_shown(loaded)
    assert loaded.evaluate("SEL.size") == g["n"]

    loaded.click("#chips .linkbtn")  # Clear all
    loaded.wait_for_timeout(150)
    assert loaded.locator(ROW).count() == EXPECTED_TOTALS["items"]
    assert loaded.locator("#chips").is_hidden()


# ---------------------------------------------------------------------------
# UI-28: filters live in the rail as folding sections; applied ones are chips
# ---------------------------------------------------------------------------

SECTIONS = ["type", "folders", "icon"]


def _sec(page, name):
    return page.locator(f'.rail .facet[data-sec="{name}"]')


def test_type_filter_lives_in_the_rail_with_counts(loaded: Page):
    assert loaded.locator(".toolbar #type-filter, .toolbar [data-kind]").count() == 0
    assert _sec(loaded, "type").locator("#type-filter").count() == 1
    counts = loaded.evaluate("""Object.fromEntries([...document.querySelectorAll('#type-filter [data-kind]')]
        .map(b => [b.dataset.kind, b.querySelector('.facet-count').textContent]))""")
    assert counts == {"": "177", "waypoints": "68", "tracks": "92", "shapes": "17"}
    names = loaded.locator("#type-filter .facet-name").all_inner_texts()
    assert names == ["All", "Areas", "Lines", "Waypoints"]   # All, then alphabetical


def test_rail_groupings_are_all_first_then_alphabetical(loaded: Page):
    """Owner feedback 2026-10-24: TYPE is All, then Areas, Lines, Waypoints
    (only those present); FOLDERS is All, then folder order; ICON is Default
    pin, then the icons alphabetically."""
    page = loaded
    _wide(page)
    expect(page.locator("#type-filter .facet-btn:visible .facet-name")).to_have_text(
        ["All", "Areas", "Lines", "Waypoints"])
    folders = page.locator("#folder-facets .facet-btn .facet-name").all_inner_texts()
    assert folders[0] == "All" and folders[1:] == [n for n, _ in _layout(page)]
    icons = page.locator("#icon-facets .facet-name").all_inner_texts()
    assert icons[0] == "Default pin"
    assert icons[1:] == page.evaluate("ns => [...ns].sort((a, b) => NAME_ORDER.compare(a, b))", icons[1:])
    assert icons[1:] == sorted(icons[1:], key=str.casefold)
    page.locator(".rail").evaluate("e => e.scrollTop = 1e6")
    _shot(page, "fb-7-rail-groupings")


def test_type_lists_only_the_kinds_the_map_has(fresh_page: Page):
    page = fresh_page
    page.set_input_files("#file", str(FIXTURE.parent / "bitterroots_subet.gpx"))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    expect(page.locator("#type-filter .facet-btn:visible .facet-name")).to_have_text(["All", "Waypoints"])


def test_rail_sections_fold_and_unfold(loaded: Page):
    rows = loaded.locator(ROW).count()
    for name in SECTIONS:
        head, body = _sec(loaded, name).locator(".sec-h"), _sec(loaded, name).locator(".facet-list")
        assert head.get_attribute("aria-expanded") == "true"
        assert body.is_visible()
        head.click()
        assert head.get_attribute("aria-expanded") == "false"
        assert body.is_hidden()
        # folding is view only: no filter changes, no rows hidden
        assert loaded.locator(ROW).count() == rows
        assert loaded.locator("#chips").is_hidden()
        head.click()
        assert head.get_attribute("aria-expanded") == "true"
        assert body.is_visible()
        assert head.locator(".sec-sum").inner_text() == ""


def test_a_folded_section_summarises_what_is_picked_in_it(loaded: Page):
    g = loaded.evaluate("DATA.groups[0].name")
    _set_type(loaded, "waypoints")
    loaded.locator("#folder-facets .facet-btn").nth(1).click()
    for name in SECTIONS:
        _sec(loaded, name).locator(".sec-h").click()
    sums = {n: _sec(loaded, n).locator(".sec-sum").inner_text() for n in SECTIONS}
    assert sums == {"type": "Waypoints", "folders": g, "icon": "Any"}
    # a filter changed while its section is folded updates the summary
    loaded.locator('#chips button[aria-label="Remove filter Type: Waypoints"]').click()
    assert _sec(loaded, "type").locator(".sec-sum").inner_text() == "All"
    _sec(loaded, "icon").locator(".sec-h").click()
    loaded.check("#only-attention")
    _sec(loaded, "icon").locator(".sec-h").click()
    assert _sec(loaded, "icon").locator(".sec-sum").inner_text() == "Default pin"


def test_each_chip_removes_exactly_its_own_filter(loaded: Page):
    g = loaded.evaluate("({key: DATA.groups[0].key, name: DATA.groups[0].name})")
    _set_type(loaded, "waypoints")
    loaded.locator("#folder-facets .facet-btn").nth(1).click()
    loaded.check("#only-attention")
    loaded.wait_for_timeout(150)

    def chip_labels():
        return [s.strip() for s in loaded.locator("#chips .chip > span").all_inner_texts()]

    def expected(kind, folder, attention):
        return loaded.evaluate(
            """([kind, folder, attention]) => DATA.groups.filter(g => !folder || g.key === folder)
                 .flatMap(g => g.items).filter(i => (!kind || i.kind === kind) &&
                   (!attention || (i.kind === 'waypoints' && i.needs_attention))).length""",
            [kind, folder, attention],
        )

    assert chip_labels() == ["Type: Waypoints", f"Folder: {g['name']}", "Icon: Default pin"]
    assert loaded.locator("#chips .linkbtn").inner_text() == "Clear all"
    assert loaded.locator(ROW).count() == expected("waypoints", g["key"], True)

    loaded.locator('#chips button[aria-label="Remove filter Type: Waypoints"]').click()
    assert chip_labels() == [f"Folder: {g['name']}", "Icon: Default pin"]
    assert loaded.get_attribute('#type-filter [data-kind=""]', "aria-pressed") == "true"
    assert loaded.locator("#only-attention").is_checked()
    assert loaded.locator(ROW).count() == expected("", g["key"], True)

    loaded.locator('#chips button[aria-label="Remove filter Icon: Default pin"]').click()
    assert chip_labels() == [f"Folder: {g['name']}"]
    assert not loaded.locator("#only-attention").is_checked()
    assert loaded.locator(ROW).count() == expected("", g["key"], False)

    _set_type(loaded, "tracks")
    loaded.click("#chips .linkbtn")
    assert loaded.locator("#chips").is_hidden()
    assert loaded.locator(ROW).count() == EXPECTED_TOTALS["items"]
    assert loaded.get_attribute('#type-filter [data-kind=""]', "aria-pressed") == "true"
    assert loaded.get_attribute("#folder-facets .facet-btn >> nth=0", "aria-pressed") == "true"


def test_edit_stage_is_scaled_down_but_the_popover_is_not(loaded: Page):
    loaded.set_viewport_size({"width": 1440, "height": 900})
    loaded.wait_for_timeout(150)
    m = loaded.evaluate("""() => ({
        body: getComputedStyle(document.body).fontSize,
        row: document.querySelector('.folder tbody tr').getBoundingClientRect().height,
        rail: document.querySelector('.rail').getBoundingClientRect().width,
        search: document.querySelector('.search').getBoundingClientRect().height,
        title: getComputedStyle(document.querySelector('#map-title')).fontSize })""")
    assert m["body"] == "13px"
    assert 40 <= m["row"] <= 44, m
    assert m["rail"] == 248
    assert m["search"] == 34
    assert m["title"] == "21px"
    loaded.locator("#folders .icon-btn").first.click()
    pop = loaded.locator("#mark-pop")
    expect(pop).to_be_visible()
    assert pop.bounding_box()["width"] == 440
    assert loaded.evaluate("getComputedStyle(document.querySelector('#mark-pop')).fontSize") == "15px"


def test_an_empty_name_is_allowed_and_shows_untitled(fresh_page):
    # Names are optional (owner, 2026-10-25): an empty name is kept and the
    # field shows "Untitled" in its place, with no error.
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    box = fresh_page.locator(".name-in").first
    box.click()
    box.fill("")
    box.press("Enter")
    fresh_page.wait_for_timeout(300)

    assert fresh_page.evaluate("DATA.groups[0].items[0].name") == ""
    expect(fresh_page.locator(".name-in").first).to_have_attribute("placeholder", "Untitled")
    assert "name" not in fresh_page.inner_text("#status").lower()


def test_help_panel_opens_and_closes(fresh_page):
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    hidden = "document.querySelector('#help').classList.contains('hidden')"
    assert fresh_page.evaluate(hidden) is True
    fresh_page.click("#help-link")
    fresh_page.wait_for_timeout(250)
    assert fresh_page.evaluate(hidden) is False
    body = fresh_page.inner_text("#help")
    assert "GeoJSON" in body and "one folder per import" in body
    fresh_page.keyboard.press("Escape")
    fresh_page.wait_for_timeout(250)
    assert fresh_page.evaluate(hidden) is True


# ---------------------------------------------------------------------------
# Standard multi-select conventions
# ---------------------------------------------------------------------------


def test_shift_click_selects_the_range_between_two_rows(loaded: Page):
    boxes = loaded.locator(f"{ROW} .sel-box")
    boxes.nth(2).check()
    loaded.wait_for_timeout(150)
    assert loaded.evaluate("SEL.size") == 1

    boxes.nth(7).click(modifiers=["Shift"])
    loaded.wait_for_timeout(300)
    assert loaded.evaluate("SEL.size") == 6, "shift+click should select rows 2..7 inclusive"


def test_shift_click_works_upward_too(loaded: Page):
    boxes = loaded.locator(f"{ROW} .sel-box")
    boxes.nth(9).check()
    loaded.wait_for_timeout(150)
    boxes.nth(4).click(modifiers=["Shift"])
    loaded.wait_for_timeout(300)
    assert loaded.evaluate("SEL.size") == 6


def test_shift_click_range_follows_the_filter_not_the_file(loaded: Page):
    """The range must span what is DISPLAYED, so it can't reach filtered-out rows."""
    _set_type(loaded, "shapes")
    loaded.wait_for_timeout(400)
    shown = loaded.locator(ROW).count()

    boxes = loaded.locator(f"{ROW} .sel-box")
    boxes.nth(0).check()
    loaded.wait_for_timeout(150)
    boxes.nth(shown - 1).click(modifiers=["Shift"])
    loaded.wait_for_timeout(300)

    assert loaded.evaluate("SEL.size") == shown
    kinds = loaded.evaluate(
        "[...new Set(DATA.groups.flatMap(g=>g.items)"
        ".filter(i => SEL.has(i.uid)).map(i => i.kind))]"
    )
    assert kinds == ["shapes"], f"range leaked past the filter: {kinds}"


def test_ctrl_a_selects_all_shown_and_escape_clears(loaded: Page):
    loaded.keyboard.press("ControlOrMeta+a")
    loaded.wait_for_timeout(400)
    assert loaded.evaluate("SEL.size") == EXPECTED_TOTALS["items"]

    loaded.keyboard.press("Escape")
    loaded.wait_for_timeout(300)
    assert loaded.evaluate("SEL.size") == 0


def test_ctrl_a_respects_the_active_filter(loaded: Page):
    _set_type(loaded, "shapes")
    loaded.wait_for_timeout(400)
    shown = loaded.locator(ROW).count()

    loaded.keyboard.press("ControlOrMeta+a")
    loaded.wait_for_timeout(400)
    assert loaded.evaluate("SEL.size") == shown
    assert shown < EXPECTED_TOTALS["items"]


def test_escape_in_a_text_field_reverts_without_clearing_selection(loaded: Page):
    """Escape is overloaded; it must do the nearest thing, not everything."""
    loaded.locator(f"{ROW} .sel-box").nth(0).check()
    loaded.locator(f"{ROW} .sel-box").nth(1).check()
    loaded.wait_for_timeout(200)
    assert loaded.evaluate("SEL.size") == 2

    box = loaded.locator(".name-in").first
    original = box.input_value()
    box.click()
    box.fill("")
    box.press("Escape")
    loaded.wait_for_timeout(300)

    assert loaded.locator(".name-in").first.input_value() == original
    assert loaded.evaluate("SEL.size") == 2, "Escape in a field must not clear the selection"


def test_clear_link_empties_the_selection(loaded: Page):
    loaded.locator(f"{ROW} .sel-box").nth(0).check()
    loaded.wait_for_timeout(200)
    loaded.click("#clear-sel")
    loaded.wait_for_timeout(300)
    assert loaded.evaluate("SEL.size") == 0


def test_page_boots_under_enforced_csp(browser):
    """Boot the app in a context that does NOT bypass CSP.

    Every other test bypasses CSP so Playwright's eval-based helpers work;
    this one proves the strict policy in web/vercel.json (mirrored by
    serve.py) actually lets Pyodide boot: CDN script + SRI hash, WASM
    compilation under 'wasm-unsafe-eval', jsdelivr fetches under connect-src.
    Only CSP-safe waits are used (no evaluate/wait_for_function).
    """
    ctx = browser.new_context()  # deliberately no bypass_csp
    page = ctx.new_page()
    violations = []
    page.on(
        "console",
        lambda m: violations.append(m.text)
        if "Content Security Policy" in m.text
        else None,
    )
    try:
        page.goto(f"{BASE_URL}/index.html")
        expect(page.locator("body")).to_have_attribute("data-engine", "ready", timeout=60000)
        assert not violations, f"CSP violations during boot: {violations}"
    finally:
        ctx.close()


@pytest.mark.parametrize("width,height", [(1280, 720), (1280, 600), (1024, 560)])
def test_icon_popover_and_dialog_stay_inside_short_windows(loaded: Page, width, height):
    """Regression: the icon & color popover (~640px tall) was positioned below
    its marker even when that ran past the bottom of a 720px window, cutting
    off the icon grid and Apply. Both editors must fit the viewport with Apply
    reachable, for markers at the top, middle and bottom of the visible list."""
    loaded.set_viewport_size({"width": width, "height": height})
    fits = """(sel) => {
      const box = document.querySelector(sel).getBoundingClientRect();
      const apply = [...document.querySelector(sel).querySelectorAll('button')]
        .find(b => b.textContent.trim() === 'Save').getBoundingClientRect();
      return box.top >= 0 && box.bottom <= innerHeight
        && apply.top >= box.top && apply.bottom <= Math.min(innerHeight, box.bottom) + 1;
    }"""
    visible = loaded.evaluate("""() => [...document.querySelectorAll('#folders .icon-btn')]
      .map((e, i) => [i, e.getBoundingClientRect()])
      .filter(([, r]) => r.top >= 0 && r.bottom <= innerHeight).map(([i]) => i)""")
    assert visible, "no marker visible in the viewport"
    for i in (visible[0], visible[len(visible) // 2], visible[-1]):
        loaded.locator("#folders .icon-btn").nth(i).click()
        assert loaded.evaluate(fits, "#mark-pop"), f"popover clipped for marker {i} at {width}x{height}"
        loaded.keyboard.press("Escape")

    boxes = loaded.locator("#folders tbody input[type=checkbox]")
    for k in range(3):
        boxes.nth(k).check()
    loaded.click("#bulk-icon")
    dialog = loaded.evaluate("""() => { const d = [...document.querySelectorAll('.modal-card')]
      .find(e => e.offsetParent && e.getBoundingClientRect().height > 0); d.id ||= 'bulk-dialog-under-test';
      return '#' + d.id; }""")
    assert loaded.evaluate(fits, dialog), f"bulk dialog clipped at {width}x{height}"


def test_map_content_is_rendered_as_text_not_html(fresh_page: Page, tmp_path):
    """A CalTopo file is untrusted input. Names, notes and folder titles full of
    markup must show up as literal text everywhere the UI renders them (rows,
    rail facets, filter chips, the icon editor), never as live elements."""
    payload = '<img src=x id=pwn onerror="window.__pwned=1">'
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "f1", "geometry": None,
         "properties": {"class": "Folder", "title": "Folder " + payload}},
        {"type": "Feature", "id": "w1", "geometry": {"type": "Point", "coordinates": [-114.1, 46.2]},
         "properties": {"class": "Marker", "title": "Name " + payload, "description": "Note " + payload,
                        "marker-symbol": "<b>sym</b>", "marker-color": "#FF0000", "folderId": "f1"}},
    ]}
    src = tmp_path / "evil.json"
    src.write_text(json.dumps(doc), encoding="utf-8")
    fresh_page.set_input_files("#file", str(src))
    fresh_page.wait_for_selector("#folders .icon-btn")
    fresh_page.locator(".facet-btn, #rail button", has_text="Folder").first.click()
    fresh_page.locator("#folders .icon-btn").first.click()
    assert fresh_page.locator("#pwn").count() == 0
    assert fresh_page.evaluate("() => window.__pwned === undefined")
    assert payload in fresh_page.locator("#folders").inner_text()


# ---------------------------------------------------------------------------
# Keyboard focus
# ---------------------------------------------------------------------------


def test_popover_apply_returns_focus_to_the_rows_marker(loaded: Page):
    """Apply re-renders the list; focus must land on the SAME row's new marker
    button, not drop to <body> (which strands a keyboard user at the top)."""
    # No attention filter here: picking an icon resolves the row, and that
    # filter would then hide it.
    row = loaded.locator(ROW, has=loaded.locator(".icon-btn")).first
    uid = row.get_attribute("data-uid")
    row.locator(".icon-btn").click()
    # An icon pick always yields a patch, so Apply really does re-render.
    loaded.locator('#mark-pop .icon-pick[data-icon="Summit"]').click()
    loaded.click("#pop-apply")
    expect(loaded.locator("#mark-pop")).to_be_hidden()
    assert loaded.evaluate(
        "uid => document.activeElement === document.querySelector("
        "`tr[data-uid=\"${CSS.escape(uid)}\"] .icon-btn`)",
        uid,
    ), loaded.evaluate("document.activeElement.outerHTML.slice(0, 120)")


def test_help_traps_tab_and_returns_focus_on_escape(loaded: Page):
    loaded.focus("#help-link")
    loaded.keyboard.press("Enter")
    expect(loaded.locator("#help")).to_be_visible()
    inside = "document.querySelector('#help .modal-card').contains(document.activeElement)"
    assert loaded.evaluate("document.activeElement.id") == "help-close"
    for key in ("Tab", "Tab", "Shift+Tab", "Shift+Tab"):
        loaded.keyboard.press(key)
        assert loaded.evaluate(inside), f"{key} left the help dialog"
    loaded.keyboard.press("Escape")
    expect(loaded.locator("#help")).to_be_hidden()
    assert loaded.evaluate("document.activeElement.id") == "help-link"


def test_export_with_everything_excluded_stays_on_the_edit_stage(loaded: Page):
    _select_all_shown(loaded)
    assert loaded.evaluate("SEL.size") == EXPECTED_TOTALS["items"]
    _menu_action(loaded, "#bulk-exclude")
    assert loaded.evaluate("DATA.totals.excluded") == EXPECTED_TOTALS["items"]
    loaded.click("#export")
    expect(loaded.locator("#status")).to_have_text(
        "Everything is excluded — include at least one item to export."
    )
    expect(loaded.locator("#status")).to_have_class(re.compile(r"\berr\b"))
    assert loaded.evaluate("document.body.dataset.stage") == "edit"
    assert loaded.evaluate("window.__cairnExported") is not True


# ---------------------------------------------------------------------------
# Confirmations: Start over, unsaved note on Export
# ---------------------------------------------------------------------------


def test_start_over_without_edits_asks_first(loaded: Page):
    loaded.locator(".newmap").first.click()
    dlg = loaded.locator("#confirm")
    expect(dlg).to_be_visible()
    expect(dlg.locator("#confirm-title")).to_have_text("Start over?")
    expect(dlg.locator("#confirm-body")).to_have_text("This clears the current map.")
    assert loaded.evaluate("document.activeElement.textContent") == "Cancel"

    dlg.get_by_role("button", name="Cancel").click()
    expect(dlg).to_be_hidden()
    assert loaded.evaluate("document.body.dataset.stage") == "edit"
    assert loaded.evaluate("DATA !== null")

    loaded.locator(".newmap").first.click()
    dlg.get_by_role("button", name="Start over").click()
    expect(dlg).to_be_hidden()
    assert loaded.evaluate("document.body.dataset.stage") == "drop"
    assert loaded.evaluate("DATA === null")


def test_start_over_counts_unexported_changes_and_escape_cancels(loaded: Page):
    name_input = loaded.locator("#folders tbody tr").first.locator(".name-in")
    name_input.fill("ZZZ_RENAMED")
    name_input.dispatch_event("change")
    loaded.wait_for_timeout(100)
    assert loaded.evaluate("Object.keys(EDITS).length") == 1

    loaded.locator(".newmap").first.click()
    body = loaded.locator("#confirm-body")
    expect(body).to_have_text(
        "This discards 1 unexported change."
    )
    loaded.keyboard.press("Escape")
    expect(loaded.locator("#confirm")).to_be_hidden()
    assert loaded.evaluate("Object.keys(EDITS).length") == 1
    assert loaded.evaluate("document.body.dataset.stage") == "edit"






def test_export_with_unapplied_note_prompts_and_apply_exports_it(loaded: Page):
    marker = "UNAPPLIED_DRAFT_APPLY"
    _open_changed_waypoint_note(loaded, marker)
    loaded.evaluate("window.__cairnExported = false")
    loaded.click("#export")
    dlg = loaded.locator("#confirm")
    expect(dlg).to_be_visible()
    expect(dlg.locator("#confirm-title")).to_have_text("Save your note?")
    assert "hasn't been saved" in loaded.inner_text("#confirm-body")
    assert loaded.evaluate("document.activeElement.textContent") == "Save"
    assert loaded.evaluate("window.__cairnExported") is False  # nothing exported yet
    loaded.keyboard.press("Escape")  # Esc == Cancel
    expect(dlg).to_be_hidden()

    assert f"<desc>{marker}</desc>" in _gpx_blob(export_zip_bytes(loaded, confirm="Save"))


def test_export_with_unapplied_note_discard_leaves_draft_out(loaded: Page):
    marker = "UNAPPLIED_DRAFT_DISCARD"
    _open_changed_waypoint_note(loaded, marker)
    blob = _gpx_blob(export_zip_bytes(loaded, confirm="Discard"))
    assert marker not in blob
    assert loaded.evaluate("NOTE_EDIT") is None


def test_export_with_unapplied_note_cancel_returns_to_the_editor(loaded: Page):
    marker = "UNAPPLIED_DRAFT_CANCEL"
    _open_changed_waypoint_note(loaded, marker)
    loaded.evaluate("window.__cairnExported = false")
    loaded.click("#export")
    loaded.locator("#confirm").get_by_role("button", name="Keep editing").click()
    expect(loaded.locator("#confirm")).to_be_hidden()
    assert loaded.evaluate("document.body.dataset.stage") == "edit"
    assert loaded.evaluate("window.__cairnExported") is False
    box = loaded.locator(".desc-in").first
    assert box.input_value() == marker
    assert loaded.evaluate("document.activeElement.classList.contains('desc-in')")


def test_export_with_unchanged_open_note_just_exports(loaded: Page):
    uid = loaded.evaluate(
        "DATA.groups.flatMap(g=>g.items).find(i => i.kind === 'waypoints').uid"
    )
    loaded.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    export_zip_bytes(loaded)  # no confirm button pressed: must not prompt
    expect(loaded.locator("#confirm")).to_be_hidden()
    assert loaded.evaluate("NOTE_EDIT") is None


def test_selection_is_limited_to_rows_in_expanded_folders(loaded: Page):
    """Select-all and shift-range must only reach rows the user can see. Rows in
    a collapsed folder are not selected, and collapsing a folder drops its rows
    from an existing selection, so a bulk edit never changes hidden items."""
    first = loaded.evaluate("DATA.groups[0].key")
    in_first = f"DATA.groups[0].items.filter(i => SEL.has(i.uid)).length"

    # Collapse the first folder, then select all: nothing inside it is selected.
    loaded.locator(f'.collapse[data-fk="collapse|{first}"]').click()
    _select_all_shown(loaded)
    assert loaded.evaluate(in_first) == 0
    expected = loaded.evaluate(
        "DATA.groups.slice(1).reduce((n, g) => n + visibleItems(g).length, 0)")
    assert loaded.evaluate("SEL.size") == expected

    # Expand, select all, then collapse: the folder's rows leave the selection.
    _clear_selection(loaded)
    loaded.locator(f'.collapse[data-fk="collapse|{first}"]').click()
    _select_all_shown(loaded)
    assert loaded.evaluate(in_first) == loaded.evaluate("DATA.groups[0].items.length")
    loaded.locator(f'.collapse[data-fk="collapse|{first}"]').click()
    loaded.wait_for_timeout(250)
    assert loaded.evaluate(in_first) == 0


def test_site_files_always_revalidate():
    """Every file the site serves (bridge.py, app.js and the engine wheel, whose
    filename never changes) must be revalidated on each visit. A long-lived or
    "immutable" cache let a browser keep an old wheel next to a new bridge.py and
    fail to boot with "cannot import name 'input_check'" (ENG-01, reversed)."""
    rules = json.loads((Path(__file__).resolve().parents[2] / "web" / "vercel.json").read_text())["headers"]
    cache = [(r["source"], h["value"]) for r in rules for h in r["headers"] if h["key"].lower() == "cache-control"]
    assert cache == [("/(.*)", "no-cache")]


def test_boot_survives_a_stale_immutable_wheel_in_the_browser_cache(browser):
    """Browsers that saw the old wheel under "public, max-age=31536000, immutable"
    (ENG-01, reversed) kept it: micropip's own download (micropip is gone since)
    obeyed that cache even after a hard reload, so the new bridge.py met an old engine and failed with "cannot
    import name 'input_check'" (owner, 2026-10-23). The app now fetches the wheel
    itself with cache "no-cache". This primes the browser cache with a stale wheel
    under the old header, then serves the real one: an ordinary reload must boot."""
    import http.server, io, socketserver, threading
    web = Path(__file__).resolve().parents[2] / "web"
    real = (web / "dist" / "cairn_maps-1.0.0-py3-none-any.whl").read_bytes()
    stale = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(real)) as src, zipfile.ZipFile(stale, "w") as dst:
        for info in src.infolist():
            if info.filename != "cairn/io/input_check.py":
                dst.writestr(info, src.read(info))
    state = {"wheel": stale.getvalue()}

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(web), **kw)
        def log_message(self, *a):
            pass
        def end_headers(self):
            if not self.path.endswith(".whl"):
                self.send_header("Cache-Control", "no-cache")
            super().end_headers()
        def do_GET(self):
            if self.path.split("?")[0].endswith(".whl"):
                body = state["wheel"]
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ctx = browser.new_context(bypass_csp=True)
    try:
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{srv.server_address[1]}/index.html")
        page.wait_for_function("document.body.innerText.includes(\"cannot import name 'input_check'\")",
                               timeout=90000)   # stale engine: the owner's error, now cached for "a year"
        state["wheel"] = real
        page.reload()
        page.wait_for_function("window.__cairnReady === true", timeout=90000)
        assert "cannot import name" not in page.inner_text("body")
    finally:
        ctx.close()
        srv.shutdown()


def test_csp_cdn_allowance_is_pinned_to_the_pyodide_version_in_use():
    """The CSP allows jsdelivr only under the exact Pyodide folder the app
    loads (not all of cdn.jsdelivr.net). A Pyodide bump must update every
    copy of the version together, or the production page fails to boot."""
    web = Path(__file__).resolve().parents[2] / "web"
    index_url = re.search(r'indexURL:\s*"([^"]+)"', (web / "app.js").read_text()).group(1)
    script = re.search(r'<script src="(https://cdn\.jsdelivr\.net/[^"]+)"', (web / "index.html").read_text()).group(1)
    policy = next(h["value"] for rule in json.loads((web / "vercel.json").read_text())["headers"]
                  for h in rule["headers"] if h["key"] == "Content-Security-Policy")
    directives = dict(d.strip().split(" ", 1) for d in policy.split(";") if d.strip())
    for name in ("script-src", "connect-src"):
        sources = directives[name].split()
        jsdelivr = [s for s in sources if "jsdelivr" in s]
        assert jsdelivr == [index_url], f"{name} should allow only {index_url}, got {jsdelivr}"
    assert script.startswith(index_url)
    # Every jsdelivr URL in the page -- the script tag and the <head> preload
    # hints -- must sit under the same pinned folder: a stale preload is a
    # wasted multi-MB download, and the CSP blocks anything outside it.
    html = (web / "index.html").read_text()
    for url in re.findall(r'https://cdn\.jsdelivr\.net/[^"\'\s>]+', html):
        assert url.startswith(index_url), f"{url} is not under the pinned {index_url}"
    # Pyodide fetch()es these in CORS mode; a preload without crossorigin
    # doesn't match that request, so the browser downloads the file twice.
    for name in ("pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"):
        assert re.search(rf'<link rel="preload" href="{re.escape(index_url + name)}" as="fetch" crossorigin>',
                         html), f"missing CORS preload for {name}"


def test_dev_server_mirrors_the_production_csp():
    """serve.py must send every header vercel.json sets on "/(.*)", the CSP
    included. It used to stop at the first such rule -- the Cache-Control one
    -- so the dev site, and test_page_boots_under_enforced_csp, ran with no
    CSP at all."""
    req = urllib.request.Request(f"{BASE_URL}/index.html", method="HEAD")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert "jsdelivr" in (resp.headers.get("Content-Security-Policy") or "")


def test_pyodide_preloads_are_used_not_fetched_twice(browser):
    """The <head> preload hints only help if Pyodide's own requests reuse
    them. A mismatched hint (wrong crossorigin / as) makes Chrome download
    the file a second time and warn that the preload was not used."""
    ctx = browser.new_context(bypass_csp=True)
    try:
        page = ctx.new_page()
        warnings = []
        page.on("console", lambda m: warnings.append(m.text) if "preload" in m.text else None)
        page.goto(f"{BASE_URL}/index.html")
        page.wait_for_function("window.__cairnReady === true", timeout=60000)
        names = page.evaluate("performance.getEntriesByType('resource').map(r => r.name)")
        for name in ("pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json", "pyodide.asm.js"):
            hits = [n for n in names if n.endswith("/" + name)]
            assert len(hits) == 1, f"{name} requested {len(hits)} times: {hits}"
        assert not warnings, warnings
    finally:
        ctx.close()


def test_on_screen_runbook_reports_dropped_areas(fresh_page, tmp_path):
    """renderRunbook reads bridge.runbook_summary_json, so the on-screen
    runbook reports a polygon with no usable coordinates as dropped -- the
    same summary instructions.txt's manifest gives -- instead of silently
    counting it. (instructions.txt lists only what was written.)"""
    square = [[-114.0, 45.0], [-114.1, 45.0], [-114.1, 45.1], [-114.0, 45.0]]
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "f1", "geometry": None,
         "properties": {"class": "Folder", "title": "Zones"}},
        {"type": "Feature", "id": "a", "geometry": {"type": "Polygon", "coordinates": [square]},
         "properties": {"class": "Shape", "title": "Good", "folderId": "f1"}},
        {"type": "Feature", "id": "b", "geometry": {"type": "Polygon", "coordinates": []},
         "properties": {"class": "Shape", "title": "Broken", "folderId": "f1"}},
    ]}
    path = tmp_path / "zones.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    fresh_page.set_input_files("#file", str(path))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    zf = zipfile.ZipFile(io.BytesIO(export_zip_bytes(fresh_page)))
    assert "Broken" not in zf.read("instructions.txt").decode("utf-8")
    text = fresh_page.locator("#runbook").inner_text()
    assert "1 item wasn't exported: it has no coordinates." in text
    assert "1 of 2 were written" in text


# ---------------------------------------------------------------------------
# Roadmap Phase 3: GPX/KML input. Every test here runs under the ENFORCED CSP
# (no bypass_csp), so only CSP-safe waits are used -- no evaluate, no
# wait_for_function, no window.__cairn* flags -- and any CSP console message
# fails the test.
# ---------------------------------------------------------------------------

ONX_PAIR = [FX_DIR / "onx_dialect" / "onx_dialect.gpx", FX_DIR / "onx_dialect" / "onx_dialect.kml"]
CALTOPO_GPX = FX_DIR / "bitterroots" / "bitterroots_subet.gpx"
CALTOPO_GPX_HELP = "CalTopo's GPX has no folders, icons or pin colors. Export GeoJSON (or KML) to keep them."






def test_file_input_accepts_gpx_kml_and_several_files(csp_page: Page):
    inp = csp_page.locator("#file")
    assert inp.get_attribute("accept") == ".json,.geojson,.gpx,.kml"
    assert inp.get_attribute("multiple") is not None
    expect(csp_page.locator(".drop-sub")).to_have_text(".json, .geojson, .gpx or .kml")


def test_onx_gpx_kml_pair_loads_as_one_folder_with_its_icons_kept(csp_page: Page):
    page = csp_page
    _load_files(page, ONX_PAIR)
    _keep_fills(page)  # onx_dialect's area has a non-default fill
    # The pair merged: ONE folder, named from the file, in the rail and the list.
    expect(page.locator(".folder")).to_have_count(1)
    expect(page.locator(".folder h2")).to_have_text("onx dialect")
    expect(page.locator("#folder-facets .facet-btn")).to_have_text(["All", "onx dialect8"])
    # Title loses .gpx; the label says whose map it is.
    expect(page.locator("#map-title")).to_have_text("onx dialect")
    expect(page.locator("#map-label")).to_have_text("onX map")
    # 3 waypoints, 2 lines (a Track and a Line), 3 areas (a hole-y one + 2 parts).
    expect(page.locator(f"{ROW} .icon-btn")).to_have_count(3)
    expect(page.locator(f"{ROW} .line-btn .icon-name")).to_have_text(
        ["Track", "Line", "Area", "Area", "Area"])
    # onX's own icons, shown unchanged, explained, and none needing attention.
    expect(page.locator(f"{ROW} .icon-btn .icon-name")).to_have_text(
        ["Climbing", "Campsite", "Hazard"])
    for i in (0, 2):
        expect(page.locator(f"{ROW} .icon-btn").nth(i)).to_have_attribute(
            "title", "Kept from your onX file.")
    expect(page.locator(f"{ROW}.attention")).to_have_count(0)
    # The fixture's "Campsite" isn't in onX's icon list: kept, but marked and explained.
    expect(page.locator(f"{ROW} .icon-name.unknown-icon")).to_have_text(["Campsite"])
    expect(page.locator(f"{ROW} .icon-btn").nth(1)).to_have_attribute(
        "title", re.compile(r"^Your onX file uses the icon “Campsite”, which Cairn doesn't know"))
    # The lines' color came from the file too.
    expect(page.locator(f"{ROW} .line-btn").first).to_have_attribute(
        "title", re.compile(r"Kept from your onX file\.$"))
    # The type filter keeps the one word "Lines" (UI-18) and still finds the Track.
    page.click('#type-filter [data-kind="tracks"]')
    expect(page.locator(ROW)).to_have_count(2)


def test_onx_pair_export_downloads_a_zip_with_the_kept_icons(csp_page: Page):
    page = csp_page
    _load_files(page, ONX_PAIR)
    _keep_fills(page)  # onx_dialect's area has a non-default fill
    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    expect(page.locator(".rb-step")).to_have_count(1)
    expect(page.locator(".rb-step h2")).to_have_text("onx dialect")
    expect(page.locator(".rb-file")).to_have_count(3)
    expect(page.locator("#done-stage input")).to_have_count(0)
    with page.expect_download() as dl:
        page.click("#download")
    zf = zipfile.ZipFile(dl.value.path())
    assert sorted(zf.namelist()) == [
        "01_onx_dialect/onx_dialect_Areas.gpx",
        "01_onx_dialect/onx_dialect_Tracks.gpx",
        "01_onx_dialect/onx_dialect_Waypoints.gpx",
        "instructions.txt",
    ]
    # Download, under the enforced CSP: the same three files, no instructions.
    with page.expect_download() as dl1:
        page.click(".rb-dl")
    assert dl1.value.suggested_filename == "01_onx_dialect.zip"
    one = zipfile.ZipFile(dl1.value.path())
    assert sorted(one.namelist()) == sorted(n for n in zf.namelist() if n != "instructions.txt")
    assert all(one.read(n) == zf.read(n) for n in one.namelist())
    wpts = zf.read("01_onx_dialect/onx_dialect_Waypoints.gpx").decode()
    # The writer sorts by name (Camp & water, Main Wall, Slide obs).
    assert re.findall(r"<onx:icon>([^<]*)</onx:icon>", wpts) == ["Campsite", "Climbing", "Hazard"]
    assert zf.read("01_onx_dialect/onx_dialect_Tracks.gpx").decode().count("<trk>") == 2
    areas = zf.read("01_onx_dialect/onx_dialect_Areas.gpx").decode()
    assert areas.count("<rte>") == 3 and areas.count("<type>Area</type>") == 3
    lines = zf.read("instructions.txt").decode("utf-8").split("\r\n")
    assert "01_onx_dialect/    rename to: onx dialect" in lines
    # The KML's holed polygon can't be an onX area with its hole: marked under it.
    at = lines.index("            Hunt unit")
    assert lines[at + 1] == "                (its hole is not kept: an onX area has one outline)"


def test_caltopo_gpx_has_no_banner_and_help_says_what_its_gpx_lacks(csp_page: Page):
    """Owner feedback 2026-10-24: no persistent notice on the edit screen for a
    CalTopo GPX; Help says it once, under exporting from CalTopo."""
    page = csp_page
    _load_files(page, [CALTOPO_GPX])
    expect(page.locator("#source-notice")).to_have_count(0)
    expect(page.locator(".content")).not_to_contain_text("CalTopo's GPX")
    expect(page.locator("#map-title")).to_have_text("bitterroots subet")
    expect(page.locator("#map-label")).to_have_text("CalTopo map")
    expect(page.locator(".folder h2")).to_have_text("bitterroots subet")
    expect(page.locator(ROW)).to_have_count(10)
    _shot(page, "fb-1a-caltopo-gpx-no-banner")
    # Help: one short line right under the paragraph on exporting from CalTopo.
    page.locator("#help-link").click()
    first = page.locator(".help-body h3").first
    expect(first).to_have_text("1 · Export from CalTopo")
    line = page.locator(".help-body h3:first-child + p + p")
    expect(line).to_have_text(CALTOPO_GPX_HELP)
    expect(page.locator(".help-body")).to_contain_text(CALTOPO_GPX_HELP)
    _shot(page, "fb-1b-help-caltopo-gpx-line")


def test_several_files_become_one_folder_each_and_start_over_clears_them(csp_page: Page):
    page = csp_page
    rattlesnake = FX_DIR / "rattlesnake_test_waypoints.gpx"
    _load_files(page, [*ONX_PAIR, CALTOPO_GPX, rattlesnake])
    _keep_fills(page)  # onx_dialect's area has a non-default fill
    expect(page.locator(".folder h2")).to_have_text(
        ["bitterroots subet", "onx dialect", "rattlesnake test waypoints"])   # by name
    expect(page.locator("#map-title")).to_have_text("onx dialect + 2 more")
    expect(page.locator("#map-label")).to_have_text("Map")
    # Start over goes back to an empty drop screen; it never adds (UI-12, UI-21).
    page.locator("#edit-stage .newmap").click()
    page.click("#confirm .confirm-actions button:text-is('Start over')")
    expect(page.locator("body")).to_have_attribute("data-stage", "drop")
    _load_files(page, ONX_PAIR)
    _keep_fills(page)  # onx_dialect's area has a non-default fill
    expect(page.locator(".folder")).to_have_count(1)


def test_bitterroots_geojson_still_reads_as_a_caltopo_map(csp_page: Page):
    page = csp_page
    _load_files(page, [FIXTURE])
    expect(page.locator("#map-title")).to_have_text("Bitterroots (Complete)")
    expect(page.locator("#map-label")).to_have_text("CalTopo map")
    expect(page.locator(".folder")).to_have_count(EXPECTED_TOTALS["folders"])


# --- review fixes: an input file's icon names and markup are data, not code ---------







def test_icon_names_that_are_object_prototype_keys_still_render(csp_page: Page):
    """icons.js looked glyphs up with ONX_GLYPHS[icon]: an onX file whose icon was
    "constructor" or "toString" found Object.prototype's function, and the render
    threw -- the whole file failed to open ("Cannot read properties of undefined")."""
    page = csp_page
    names = ["constructor", "toString", "__proto__", "hasOwnProperty"]
    page.set_input_files("#file", files=[_gpx_payload(
        "proto.gpx", "".join(_onx_wpt(i + 1, f"P{i}", n) for i, n in enumerate(names)))])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    expect(page.locator(f"{ROW} .icon-btn .icon-name")).to_have_text(names)


def test_gpx_names_notes_icons_and_filename_render_as_text_not_html(fresh_page: Page):
    """The GPX twin of test_map_content_is_rendered_as_text_not_html: markup in a
    GPX <name>, its notes, its onX icon and the file's own name stays literal text
    in the rows, the folder heading, the title, the rail and the icon editor."""
    page = fresh_page
    payload = '<img src=x id=pwn onerror="window.__pwned=1">'
    xml = payload.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    page.set_input_files("#file", files=[_gpx_payload(
        payload + ".gpx", _onx_wpt(1, "Name " + xml, xml, notes="Note " + xml))])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    page.locator("#folders .icon-btn").first.click()
    assert page.locator("#pwn").count() == 0
    assert page.evaluate("() => window.__pwned === undefined")
    # (The note goes in too, as a sink to exercise; its tags are stripped by
    # strip_html on the way in, so its text isn't asserted.)
    assert page.locator(f"{ROW} .icon-name").inner_text() == payload
    assert page.locator(f"{ROW} .name-in").input_value() == "Name " + payload
    # The title undoes CalTopo's filename underscores, so "__pwned" reads " pwned".
    assert page.locator("#map-title").inner_text().startswith("<img src=x id=pwn onerror=")
    assert payload in page.locator("#icon-facets").inner_text()
    assert payload in page.locator("#mark-pop").inner_text()


# ---------------------------------------------------------------------------
# CalTopo KML and GPX (roadmap Phase 7)
# ---------------------------------------------------------------------------

CALTOPO_SYN = FX_DIR / "caltopo_synthetic"




def _wpts(gpx: str) -> dict:
    """name -> (onx:icon, onx:color) for every <wpt> in a Cairn GPX."""
    import html
    out = {}
    for block in re.findall(r"<wpt\b.*?</wpt>", gpx, flags=re.S):
        name = html.unescape(re.search(r"<name>(.*?)</name>", block, flags=re.S).group(1))
        icon = re.search(r"<onx:icon>(.*?)</onx:icon>", block)
        color = re.search(r"<onx:color>(.*?)</onx:color>", block)
        out[name] = (icon and icon.group(1), color and color.group(1))
    return out


def test_caltopo_kml_loads_with_its_folders(csp_page: Page):
    page = csp_page
    _load_files(page, [CALTOPO_SYN / "caltopo_synthetic.kml"])
    expect(page.locator("#map-label")).to_have_text("CalTopo map")
    expect(page.locator(".folder h2")).to_have_text(
        ["Areas", "Camps & Water #1", "Routes", "Routes / Spur lines"])   # by name
    # The CalTopo symbol mapped to an onX icon, as it does from the GeoJSON.
    expect(_row(page, "Trailhead lot").locator(".icon-btn .icon-name")).to_have_text("Parking")


def test_caltopo_gpx_icons_and_colors_set_in_cairn_reach_the_exported_gpx(csp_page: Page):
    """Additive icons: a CalTopo GPX carries no icons or waypoint colors, so its
    waypoints arrive as name guesses or the default pin. Icons and colors set in
    Cairn -- one waypoint through the marker popover, two through the bulk
    dialog -- are written to the export as onx:icon / onx:color."""
    page = csp_page
    _load_files(page, [CALTOPO_SYN / "caltopo_synthetic.gpx"])
    expect(page.locator(".folder h2")).to_have_text(["caltopo synthetic"])
    # Nothing in the GPX said "danger" or "camping": one is a default pin, the
    # other a guess from "spring" in its name.
    expect(_row(page, "Cornice").locator(".icon-btn")).to_have_text("Default pin")
    expect(_row(page, "Camp #3 & <Lake> spring").locator(".icon-btn")).to_have_text("Water Source")

    # One waypoint, through the marker popover.
    _row(page, "Cornice").locator(".icon-btn").click()
    pop = page.locator("#mark-pop")
    pop.locator(".icon-search").fill("hazard")
    pop.locator('.icon-pick[data-icon="Hazard"]').click()
    pop.locator('.swatch-btn[aria-label="Red-Orange"]').click()
    page.click("#pop-apply")
    expect(pop).to_be_hidden()
    expect(_row(page, "Cornice").locator(".icon-btn .icon-name")).to_have_text("Hazard")

    # Two waypoints, through the bulk dialog.
    for name in ("Camp #3 & <Lake> spring", "Plain red point"):
        _row(page, name).locator(".sel-box").check()
    page.click("#bulk-icon")
    page.click('#mark-dialog .icon-pick[data-icon="Camp Backcountry"]')
    page.locator('#mark-dialog .swatch-btn[aria-label="Yellow"]').click()
    page.click("#bulk-apply")
    expect(page.locator("#mark-modal")).to_be_hidden()

    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    with page.expect_download() as dl:
        page.click("#download")
    zf = zipfile.ZipFile(dl.value.path())
    (wpt_file,) = [n for n in zf.namelist() if n.endswith("_Waypoints.gpx")]
    got = _wpts(zf.read(wpt_file).decode())
    assert got["Cornice"] == ("Hazard", "rgba(255,51,0,1)")
    # Names reach onX unchanged, # & < > included (ENG-06; onX verified, round r1).
    assert got["Camp #3 & <Lake> spring"] == ("Camp Backcountry", "rgba(255,255,0,1)")
    assert got["Plain red point"] == ("Camp Backcountry", "rgba(255,255,0,1)")
    # The rest keep what Cairn chose at load, still written as onX styling.
    assert got["Point with no colour"][0] == "Location"
    assert all(icon and color for icon, color in got.values())


# ---------------------------------------------------------------------------
# Folders UI (UI-32): drag rows to a rail folder, + New folder, rename in the
# header (and merge on a taken name), More ▸ Move to…
# Bitterroots at load: Unorganized 43, Lost Trail Pass 31, North Roots 22,
# Trapper area 21, Lost Horse Canyon 18, Blodgett 17, Central roots 10,
# Sheafman ridge 9, Paddling 5, Mill Creek Canyon 1.
# ---------------------------------------------------------------------------


def _layout(page: Page) -> list:
    """[(name, count)] as the UI has it, after checking the bridge agrees."""
    ui = page.evaluate("DATA.groups.map(g => [g.key, g.name, g.items.map(i => i.uid)])")
    py = page.evaluate(
        "JSON.parse(py.runPython('import json; json.dumps(bridge._layout())'))"
    )
    assert [[f["key"], f["name"], f["uids"]] for f in py] == ui
    # Folder order (owner feedback 2026-10-24): by name, natural and any case,
    # the loose items last; the rail lists them in the same order.
    keys = [(bool(f["unorganized"]), _natural(f["name"])) for f in py]
    assert keys == sorted(keys), [f["name"] for f in py]
    rail = page.evaluate("[...document.querySelectorAll('#folder-facets [data-fk^=\"folder|\"]')]"
                         ".map(e => e.dataset.fk.slice(7)).filter(k => k !== '\\u0000all')")
    if not page.evaluate("!!DRAG"):
        assert rail == [f["key"] for f in py], rail
    return [(name, len(uids)) for _key, name, uids in ui]


def _natural(name: str) -> list:
    """Folder order's name key, written independently of the bridge's."""
    return [(0, int(c)) if c.isdecimal() else (1, c)
            for c in re.findall(r"\d+|\D+", name.strip().casefold())]


def _rail(page: Page, name: str):
    return page.locator("#folder-facets .facet-btn", has=page.locator(
        ".facet-name", has_text=re.compile(rf"^{re.escape(name)}$")))


def _section(page: Page, name: str):
    return page.locator("section.folder", has=page.locator(
        ".folder-name", has_text=re.compile(rf"^{re.escape(name)}$")))


def _press(page: Page, source):
    """Mouse down on a control in a row, then move past the 6px threshold."""
    source.scroll_into_view_if_needed()
    b = source.bounding_box()
    x, y = b["x"] + min(20, b["width"] / 2), b["y"] + b["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 10, y + 10, steps=3)


def _hover_to(page: Page, target):
    # Centre it in its scroller first: a rail entry low in the list can sit
    # under the rail's sticky footer (auto-scroll has its own test).
    target.evaluate("e => e.scrollIntoView({block: 'center'})")
    b = target.bounding_box()
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=6)


def _drag(page: Page, source, target):
    _press(page, source)
    _hover_to(page, target)
    page.mouse.up()


def _first_row(page: Page, folder: str):
    return _section(page, folder).locator("tbody tr").first


def test_drag_one_row_to_a_rail_folder(loaded: Page):
    page = loaded
    row = _first_row(page, "Lost Trail Pass")
    uid = row.get_attribute("data-uid")
    _press(page, row.locator(".note-btn"))
    _hover_to(page, _rail(page, "North Roots"))
    expect(page.locator("#drag-ghost")).to_have_text("Move 1 item")
    expect(_rail(page, "Lost Trail Pass")).to_have_class(re.compile(r"\bhere-now\b"))
    expect(_rail(page, "Lost Trail Pass").locator(".facet-count")).to_have_text("here now")
    expect(_rail(page, "North Roots")).to_have_class(re.compile(r"\bdrop-over\b"))
    expect(page.locator(f'tr[data-uid="{uid}"]')).to_have_class(re.compile(r"\bdragging\b"))
    page.mouse.up()
    expect(page.locator("#drag-ghost")).to_have_count(0)
    expect(page.locator("#status")).to_have_text("Moved 1 item to North Roots.")
    lay = dict(_layout(page))
    assert lay["Lost Trail Pass"] == 30 and lay["North Roots"] == 23
    expect(_section(page, "North Roots").locator(f'tr[data-uid="{uid}"]')).to_have_count(1)
    expect(_rail(page, "North Roots").locator(".facet-count")).to_have_text("23")
    expect(page.locator(".here-now, .drop-over, tr.dragging")).to_have_count(0)


def test_drag_several_ticked_rows_moves_them_all(loaded: Page):
    page = loaded
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    uids = [rows.nth(i).get_attribute("data-uid") for i in (0, 2, 4)]
    for u in uids:
        page.locator(f'tr[data-uid="{u}"] .sel-box').check()
    _press(page, page.locator(f'tr[data-uid="{uids[1]}"] .icon-btn, tr[data-uid="{uids[1]}"] .line-btn'))
    _hover_to(page, _rail(page, "Paddling"))
    expect(page.locator("#drag-ghost")).to_have_text("Move 3 items")
    expect(page.locator("tr.dragging")).to_have_count(3)
    page.mouse.up()
    expect(page.locator("#status")).to_have_text("Moved 3 items to Paddling.")
    paddling = page.evaluate("DATA.groups.find(g => g.name === 'Paddling').items.map(i => i.uid)")
    assert set(uids) <= set(paddling) and len(paddling) == 8
    # Moved rows are unticked (their ticks did their job).
    assert page.evaluate("SEL.size") == 0
    expect(page.locator("#selbar")).to_be_hidden()

    # Dragging an unticked row moves only that row, and leaves other ticks alone.
    keep = _first_row(page, "Trapper area").get_attribute("data-uid")
    page.locator(f'tr[data-uid="{keep}"] .sel-box').check()
    other = _first_row(page, "North Roots")
    ouid = other.get_attribute("data-uid")
    _drag(page, other.locator(".note-btn"), _rail(page, "Blodgett"))
    expect(page.locator("#status")).to_have_text("Moved 1 item to Blodgett.")
    assert dict(_layout(page))["Blodgett"] == 18
    assert page.evaluate("[...SEL]") == [keep]
    expect(page.locator("#selcount")).to_have_text("1 selected")


def test_drag_from_an_unfocused_name_but_not_a_focused_one(loaded: Page):
    page = loaded
    row = _first_row(page, "Trapper area")
    uid = row.get_attribute("data-uid")
    name = row.locator(".name-in")
    before = name.input_value()
    _drag(page, name, _rail(page, "Paddling"))
    expect(page.locator("#status")).to_have_text("Moved 1 item to Paddling.")
    assert page.evaluate("Object.keys(EDITS).length") == 0
    moved = page.locator(f'tr[data-uid="{uid}"] .name-in')
    expect(moved).to_have_value(before)

    # In a name field you are already typing in, a press-and-drag selects text.
    field = _first_row(page, "Blodgett").locator(".name-in")
    field.click()
    _press(page, field)
    _hover_to(page, _rail(page, "Paddling"))
    expect(page.locator("#drag-ghost")).to_have_count(0)
    page.mouse.up()
    assert dict(_layout(page))["Blodgett"] == 17


def test_drag_onto_new_folder_then_name_it(loaded: Page):
    page = loaded
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    uids = [rows.nth(i).get_attribute("data-uid") for i in (0, 1, 2)]
    for u in uids:
        page.locator(f'tr[data-uid="{u}"] .sel-box').check()
    _press(page, page.locator(f'tr[data-uid="{uids[0]}"] .note-btn'))
    _hover_to(page, page.locator(".new-folder"))
    expect(page.locator(".new-folder")).to_have_class(re.compile(r"\bdrop-over\b"))
    page.mouse.up()
    expect(page.locator("#status")).to_have_text("Moved 3 items to a new folder.")
    inp = page.locator("#folder-facets .folder-name-in")
    expect(inp).to_be_focused()
    expect(inp).to_have_value("New folder")
    assert page.evaluate("[document.activeElement.selectionStart, document.activeElement.selectionEnd]") == [0, 10]
    page.keyboard.type("Camps")
    page.keyboard.press("Enter")
    expect(_rail(page, "Camps")).to_be_focused()
    lay = _layout(page)
    assert ("Camps", 3) in lay and dict(lay)["Lost Trail Pass"] == 28
    expect(_section(page, "Camps").locator("tbody tr")).to_have_count(3)

    # A second one: "New folder" is free again, so it is taken; Esc keeps it.
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    expect(page.locator("#folder-facets .folder-name-in")).to_have_value("New folder")
    page.keyboard.press("Escape")
    assert ("New folder", 1) in _layout(page)
    # The default is never a name that's taken: the third is "New folder 2".
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    expect(page.locator("#folder-facets .folder-name-in")).to_have_value("New folder 2")
    page.locator("#filter").click()   # leaving the field keeps the name
    expect(page.locator("#folder-facets .folder-name-in")).to_have_count(0)
    assert ("New folder 2", 1) in _layout(page)


def test_drag_onto_its_own_folder_or_nowhere_does_nothing(loaded: Page):
    page = loaded
    before = _layout(page)
    row = _first_row(page, "Lost Trail Pass")
    _drag(page, row.locator(".note-btn"), _rail(page, "Lost Trail Pass"))
    assert _layout(page) == before
    expect(page.locator("#status")).to_have_text("")
    # Dropped on the list, the search box, the rail's "All": nothing.
    for target in (page.locator("#folders tbody tr").nth(5), page.locator("#filter"),
                   page.locator("#folder-facets .facet-btn").first):
        _drag(page, row.locator(".note-btn"), target)
        assert _layout(page) == before
    expect(page.locator("#status")).to_have_text("")
    # The drop's click didn't land as a click on what was under it.
    assert page.evaluate("FILTERS.folder") is None
    assert page.evaluate("POP") is None and page.evaluate("NOTE_EDIT") is None


def test_escape_cancels_a_drag(loaded: Page):
    page = loaded
    before = _layout(page)
    _first_row(page, "Paddling").locator(".sel-box").check()   # a tick the drag must not clear
    _press(page, _first_row(page, "Lost Trail Pass").locator(".note-btn"))
    target = _rail(page, "North Roots")
    _hover_to(page, target)
    expect(target).to_have_class(re.compile(r"\bdrop-over\b"))
    page.keyboard.press("Escape")
    expect(page.locator("#drag-ghost")).to_have_count(0)
    expect(page.locator(".drop-over, .here-now, tr.dragging")).to_have_count(0)
    page.keyboard.press("Escape")   # again, still holding: not the selection's Esc
    page.mouse.move(10, 10)
    _hover_to(page, target)
    page.mouse.up()
    assert _layout(page) == before
    # Releasing over North Roots after Esc didn't filter to it either.
    assert page.evaluate("FILTERS.folder") is None
    expect(target).to_have_attribute("aria-pressed", "false")
    assert page.evaluate("SEL.size") == 1


def test_rename_a_folder_in_its_header(loaded: Page):
    page = loaded
    btn = _section(page, "North Roots").locator(".folder-name")
    btn.click()
    inp = page.locator(".folder-head .folder-name-in")
    expect(inp).to_be_focused()
    expect(inp).to_have_value("North Roots")

    # Empty: refused, the old name kept.
    inp.fill("   ")
    page.keyboard.press("Enter")
    expect(page.locator("#status")).to_have_text("A folder needs a name.")
    expect(_section(page, "North Roots")).to_have_count(1)
    expect(_section(page, "North Roots").locator(".folder-name")).to_be_focused()

    # The same name: nothing happens and it isn't a change.
    _section(page, "North Roots").locator(".folder-name").click()
    page.keyboard.press("Enter")
    assert page.evaluate("unexportedChanges()") == 0

    # Esc keeps the old name.
    _section(page, "North Roots").locator(".folder-name").click()
    page.keyboard.type("Nope")
    page.keyboard.press("Escape")
    expect(_section(page, "North Roots")).to_have_count(1)

    # Another case of its own name is a rename.
    _section(page, "North Roots").locator(".folder-name").click()
    page.keyboard.type("north roots")
    page.keyboard.press("Enter")
    expect(_section(page, "north roots")).to_have_count(1)
    expect(_rail(page, "north roots")).to_have_count(1)
    assert ("north roots", 22) in _layout(page)

    # A new name, by leaving the field.
    _section(page, "north roots").locator(".folder-name").click()
    page.keyboard.type("High Roots")
    page.locator("#filter").click()
    expect(_section(page, "High Roots")).to_have_count(1)
    assert ("High Roots", 22) in _layout(page)


def test_rename_onto_a_taken_name_offers_to_merge(loaded: Page):
    page = loaded
    before = dict(_layout(page))
    _section(page, "Lost Trail Pass").locator(".folder-name").click()
    page.keyboard.type("north ROOTS ")
    page.keyboard.press("Enter")
    dlg = page.locator("#confirm")
    expect(dlg).to_be_visible()
    expect(page.locator("#confirm-title")).to_have_text("“North Roots” already exists")
    expect(page.locator("#confirm-body")).to_have_text(
        "Move the 31 items in “Lost Trail Pass” into it?")
    expect(page.locator("#confirm-actions button")).to_have_text(["Cancel", "Move them"])
    expect(page.locator("#confirm-actions button", has_text="Cancel")).to_be_focused()

    # Cancel (Enter on the default) keeps the old name and both folders.
    page.keyboard.press("Enter")
    expect(dlg).to_be_hidden()
    assert dict(_layout(page)) == before
    expect(_section(page, "Lost Trail Pass").locator(".folder-name")).to_be_focused()
    # Esc is Cancel too.
    _section(page, "Lost Trail Pass").locator(".folder-name").click()
    page.keyboard.type("North Roots")
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    assert dict(_layout(page)) == before

    # Move them: everything goes into North Roots, which keeps its name and place.
    _section(page, "Lost Trail Pass").locator(".folder-name").click()
    page.keyboard.type("North Roots")
    page.keyboard.press("Enter")
    page.click("#confirm-actions button:text-is('Move them')")
    lay = _layout(page)
    names = [n for n, _ in lay]
    assert "Lost Trail Pass" not in names
    assert names.index("North Roots") == 4 and dict(lay)["North Roots"] == 53
    expect(page.locator("#status")).to_have_text("Moved 31 items to North Roots.")
    expect(_rail(page, "Lost Trail Pass")).to_have_count(0)
    assert page.evaluate("DATA.totals.folders") == 9


def test_keyboard_move_to_end_to_end(loaded: Page):
    page = loaded
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    uids = [rows.nth(i).get_attribute("data-uid") for i in (0, 1)]
    page.locator(f'tr[data-uid="{uids[0]}"] .sel-box').focus()
    page.keyboard.press("Space")
    page.locator(f'tr[data-uid="{uids[1]}"] .sel-box').focus()
    page.keyboard.press("Space")
    expect(page.locator("#selcount")).to_have_text("2 selected")

    page.locator("#more-btn").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#bulk-move")).to_be_focused()
    expect(page.locator("#more-menu button").first).to_have_text("Move to…")
    page.keyboard.press("Enter")
    pop = page.locator("#move-pop")
    expect(pop).to_be_visible()
    expect(pop.locator(".move-h")).to_have_text("Move 2 items to")
    here = pop.locator(".move-opt", has_text="Lost Trail Pass")
    expect(here).to_be_disabled()
    expect(here).to_contain_text("here now")
    expect(pop.locator(".move-opt").last).to_have_text("+ New folder")
    expect(pop.locator(".move-opt").first).to_be_focused()   # Blodgett (folders by name)

    # Esc closes it and gives focus back to More.
    page.keyboard.press("Escape")
    expect(pop).to_be_hidden()
    expect(page.locator("#more-btn")).to_be_focused()
    expect(page.locator("#selcount")).to_have_text("2 selected")

    # Arrow keys skip "here now": Down from Lost Horse Canyon lands on Mill
    # Creek Canyon (Blodgett, Central roots, Lost Horse Canyon, [Lost Trail Pass], …).
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    for _ in range(3):
        page.keyboard.press("ArrowDown")
    expect(pop.locator(".move-opt", has_text="Mill Creek Canyon")).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(pop.locator(".move-opt", has_text="North Roots")).to_be_focused()
    page.keyboard.press("Home")
    page.keyboard.press("ArrowUp")          # wraps to the end
    expect(pop.locator(".move-new")).to_be_focused()
    page.keyboard.press("Home")
    for _ in range(4):
        page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(pop).to_be_hidden()
    expect(page.locator("#status")).to_have_text("Moved 2 items to North Roots.")
    # The moved rows are unticked, so More is off: focus goes to where they went.
    expect(_rail(page, "North Roots")).to_be_focused()
    expect(page.locator("#selbar")).to_be_hidden()
    lay = dict(_layout(page))
    assert lay["North Roots"] == 24 and lay["Lost Trail Pass"] == 29

    # + New folder…: the folder is made, its name is open in the rail.
    for u in uids:
        page.locator(f'tr[data-uid="{u}"] .sel-box').focus()
        page.keyboard.press("Space")
    page.locator("#more-btn").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    page.keyboard.press("End")
    page.keyboard.press("Enter")
    inp = page.locator("#folder-facets .folder-name-in")
    expect(inp).to_be_focused()
    page.keyboard.type("Yurts")
    page.keyboard.press("Enter")
    expect(_rail(page, "Yurts")).to_be_focused()
    lay = _layout(page)
    assert ("Yurts", 2) in lay and dict(lay)["North Roots"] == 22


def test_move_to_opens_the_folded_folders_section_for_the_new_name(loaded: Page):
    page = loaded
    page.click('.facet[data-sec="folders"] .sec-h')
    expect(page.locator("#folder-facets")).to_be_hidden()
    _first_row(page, "Paddling").locator(".sel-box").check()
    page.click("#more-btn")
    page.click("#bulk-move")
    page.click("#move-pop .move-new")
    expect(page.locator("#folder-facets .folder-name-in")).to_be_focused()
    page.keyboard.press("Enter")
    assert ("New folder", 1) in _layout(page)


def test_an_emptied_folder_disappears_with_its_filter(loaded: Page):
    page = loaded
    _rail(page, "Mill Creek Canyon").click()
    expect(page.locator("#chips")).to_contain_text("Folder: Mill Creek Canyon")
    row = _first_row(page, "Mill Creek Canyon")
    key = page.evaluate("DATA.groups.find(g => g.name === 'Mill Creek Canyon').key")
    _drag(page, row.locator(".note-btn, .icon-btn, .line-btn").first, _rail(page, "Paddling"))
    # H4: the view goes back to All, and the status line says why.
    expect(page.locator("#status")).to_have_text(
        "Moved 1 item to Paddling. “Mill Creek Canyon” is empty now, so it was removed.")
    expect(_rail(page, "Mill Creek Canyon")).to_have_count(0)
    assert page.evaluate("FILTERS.folder") is None
    expect(page.locator("#chips")).to_be_hidden()
    expect(page.locator(ROW)).to_have_count(177)
    assert dict(_layout(page))["Paddling"] == 6
    assert page.evaluate("DATA.totals.folders") == 9


def test_a_collapsed_folder_that_is_merged_away_is_forgotten(loaded: Page):
    page = loaded
    _section(page, "Paddling").locator(".collapse").click()
    key = page.evaluate("DATA.groups.find(g => g.name === 'Paddling').key")
    assert page.evaluate(f"COLLAPSED.has({json.dumps(key)})")
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.type("Blodgett")
    page.keyboard.press("Enter")
    page.click("#confirm-actions button:text-is('Move them')")
    assert page.evaluate(f"COLLAPSED.has({json.dumps(key)})") is False
    assert dict(_layout(page))["Blodgett"] == 22


def test_moved_items_keep_their_edits_and_exclusion(loaded: Page):
    page = loaded
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    a, b = rows.nth(0).get_attribute("data-uid"), rows.nth(1).get_attribute("data-uid")
    name = page.locator(f'tr[data-uid="{a}"] .name-in')
    name.fill("Renamed before the move")
    name.press("Enter")
    page.locator(f'tr[data-uid="{b}"] .sel-box').check()
    _menu_action(page, "#bulk-exclude")
    _clear_selection(page)
    for u in (a, b):
        page.locator(f'tr[data-uid="{u}"] .sel-box').check()
    page.click("#more-btn")
    page.click("#bulk-move")
    page.click('#move-pop .move-opt:has-text("Paddling")')
    sec = _section(page, "Paddling")
    expect(sec.locator(f'tr[data-uid="{a}"] .name-in')).to_have_value("Renamed before the move")
    expect(sec.locator(f'tr[data-uid="{b}"]')).to_have_class(re.compile(r"\bexcluded\b"))
    excluded_name = page.evaluate(f"DATA.groups.flatMap(g => g.items).find(i => i.uid === '{b}').name")
    zf = zipfile.ZipFile(io.BytesIO(export_zip_bytes(page)))
    pad = "".join(zf.read(n).decode() for n in zf.namelist() if "_Paddling/" in n)
    lost = "".join(zf.read(n).decode() for n in zf.namelist() if "_Lost_Trail_Pass/" in n)
    assert "Renamed before the move" in pad and "Renamed before the move" not in lost
    assert f"<name>{excluded_name}</name>" not in pad + lost


def test_export_after_moves_and_renames(loaded: Page):
    page = loaded
    # Empty Mill Creek Canyon into Paddling, rename Blodgett, make a new folder.
    _drag(page, _first_row(page, "Mill Creek Canyon").locator(".note-btn"), _rail(page, "Paddling"))
    _section(page, "Blodgett").locator(".folder-name").click()
    page.keyboard.type("Blodgett / Big Creek")
    page.keyboard.press("Enter")
    rows = _section(page, "Unorganized").locator("tbody tr")
    for i in (0, 1, 2, 3):
        rows.nth(i).locator(".sel-box").check()
    _press(page, rows.nth(0).locator(".note-btn"))
    _hover_to(page, page.locator(".new-folder"))
    page.mouse.up()
    page.keyboard.type("Ski lines")
    page.keyboard.press("Enter")
    lay = _layout(page)
    _done(page)
    boxes = page.locator("#runbook .rb-step")
    expect(boxes).to_have_count(10)
    manifest = page.evaluate("MANIFEST")
    assert [e["folder"] for e in manifest] == [n for n, _ in lay]
    assert [e["count"] for e in manifest] == [c for _, c in lay]
    # Folders by name, the loose items last: the new and renamed ones take their place.
    assert [e["folder"] for e in manifest] == [
        "Blodgett / Big Creek", "Central roots", "Lost Horse Canyon", "Lost Trail Pass",
        "North Roots", "Paddling", "Sheafman ridge", "Ski lines", "Trapper area", "Unorganized"]
    assert manifest[7]["folder"] == "Ski lines" and manifest[7]["count"] == 4
    expect(boxes.nth(7).locator("h2")).to_have_text("Ski lines")
    expect(boxes.nth(7).locator(".rb-file")).to_have_count(1)
    big = boxes.filter(has_text="Blodgett / Big Creek")
    expect(big.locator(".rb-dl")).to_have_attribute("aria-label", "Download Blodgett / Big Creek")
    for i, e in enumerate(manifest):
        page.wait_for_timeout(300)
        with page.expect_download() as dl:
            boxes.nth(i).locator(".rb-dl").click()
        nn = f"{i + 1:02d}_{e['safe']}"
        assert dl.value.suggested_filename == f"{nn}.zip"
        names = zipfile.ZipFile(dl.value.path()).namelist()
        assert names == [f["path"] for f in e["files"]] and all(n.startswith(nn + "/") for n in names)
    assert manifest[0]["safe"] == "Blodgett_Big_Creek"
    assert manifest[7]["files"][0]["path"].startswith("08_Ski_lines/Ski_lines_")
    # Back, move more, export again: the screen follows.
    page.click("#back")
    _drag(page, _first_row(page, "Ski lines").locator(".note-btn"), _rail(page, "Paddling"))
    _done(page)
    manifest = page.evaluate("MANIFEST")
    assert manifest[7]["count"] == 3
    assert [e["count"] for e in manifest] == [c for _, c in _layout(page)]


def test_start_over_counts_moves_and_renames(loaded: Page):
    page = loaded
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    rows.nth(0).locator(".sel-box").check()
    rows.nth(1).locator(".sel-box").check()
    _drag(page, rows.nth(0).locator(".note-btn"), _rail(page, "Paddling"))
    _section(page, "Blodgett").locator(".folder-name").click()
    page.keyboard.type("Blodgett 2")
    page.keyboard.press("Enter")
    page.locator(".newmap").first.click()
    expect(page.locator("#confirm-body")).to_have_text(
        "This discards 3 unexported changes.")
    page.click("#confirm-actions button:text-is('Start over')")
    expect(page.locator("body")).to_have_attribute("data-stage", "drop")
    assert page.evaluate("SAVED") is None and page.evaluate("unexportedChanges()") == 0
    assert page.evaluate("window.__cairnLoaded") is False


def test_leaving_one_folder_name_for_another_keeps_the_second_open(loaded: Page):
    """Regression: the deferred render after the first name saved removed the
    second, focused name field; Chrome fires blur on removal, which closed it."""
    page = loaded
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.type("Pad")
    _section(page, "Blodgett").locator(".folder-name").click()
    page.wait_for_timeout(150)
    inp = page.locator(".folder-head .folder-name-in")
    expect(inp).to_be_focused()
    expect(inp).to_have_value("Blodgett")
    assert page.evaluate("[document.activeElement.selectionStart, document.activeElement.selectionEnd]") == [0, 8]
    assert ("Pad", 5) in _layout(page)
    # A re-render for another reason (a filter) doesn't close it either.
    page.keyboard.type("Blodgett Creek")
    page.evaluate("renderEdit()")
    expect(page.locator(".folder-head .folder-name-in")).to_have_value("Blodgett Creek")
    page.keyboard.press("Enter")
    assert ("Blodgett Creek", 17) in _layout(page)


def test_an_open_note_moved_out_of_view_keeps_its_draft(loaded: Page):
    page = loaded
    _rail(page, "Lost Trail Pass").click()
    row = _first_row(page, "Lost Trail Pass")
    uid = row.get_attribute("data-uid")
    row.locator(".note-btn").click()
    page.locator(".desc-in").fill("draft that must survive")
    _drag(page, page.locator(f'tr[data-uid="{uid}"] .icon-btn, tr[data-uid="{uid}"] .line-btn'),
          _rail(page, "North Roots"))
    expect(page.locator("#status")).to_have_text("Moved 1 item to North Roots.")
    assert page.evaluate(f"EDITS[{json.dumps(uid)}].desc") == "draft that must survive"


def test_a_renamed_unorganized_is_an_ordinary_folder(loaded: Page):
    page = loaded
    _section(page, "Unorganized").locator(".folder-name").click()
    page.keyboard.type("Loose ends")
    page.keyboard.press("Enter")
    expect(_rail(page, "Loose ends")).not_to_have_class(re.compile(r"\bunorg\b"))
    expect(_section(page, "Loose ends").locator(".folder-sub")).to_have_text("43 items")
    # ...and a folder renamed TO "Unorganized" doesn't become the loose items.
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.type("Unorganized")
    page.keyboard.press("Enter")
    expect(_rail(page, "Unorganized")).not_to_have_class(re.compile(r"\bunorg\b"))
    expect(_section(page, "Unorganized").locator(".folder-sub")).to_have_text("5 items")


def _many_folders_map(n: int) -> str:
    feats = []
    for f in range(n):
        feats.append({"type": "Feature", "id": f"f{f}", "geometry": None,
                      "properties": {"class": "Folder", "title": f"Folder {f:03d}"}})
        for k in range(2):
            feats.append({"type": "Feature", "id": f"m{f}-{k}",
                          "geometry": {"type": "Point", "coordinates": [-114 + f * 1e-3, 46 + k * 1e-3]},
                          "properties": {"class": "Marker", "title": f"WP {f}-{k}", "folderId": f"f{f}"}})
    return json.dumps({"type": "FeatureCollection", "features": feats})


def test_a_long_rail_scrolls_while_dragging_to_new_folder(fresh_page: Page, tmp_path):
    """With 60 folders "+ New folder" is far below the rail's fold: holding the
    pointer over the rail's bottom edge scrolls it there."""
    page = fresh_page
    page.set_viewport_size({"width": 1440, "height": 900})
    f = tmp_path / "many.json"
    f.write_text(_many_folders_map(60))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    assert page.evaluate("DATA.groups.length") == 60
    foot = page.locator(".rail-foot").bounding_box()
    nf = page.locator(".new-folder")
    assert nf.bounding_box()["y"] > foot["y"]          # out of reach at first
    _press(page, page.locator("#folders tbody tr").first.locator(".note-btn"))
    page.mouse.move(120, foot["y"] + 40, steps=4)
    page.wait_for_function(
        "document.querySelector('.new-folder').getBoundingClientRect().bottom"
        f" < {foot['y'] - 40}", timeout=10000)
    page.mouse.move(120, 400)                          # out of the edge: scrolling stops
    page.wait_for_timeout(100)
    b = nf.bounding_box()
    page.mouse.move(b["x"] + 40, b["y"] + b["height"] / 2, steps=3)
    page.mouse.up()
    expect(page.locator("#status")).to_have_text("Moved 1 item to a new folder.")
    expect(page.locator("#folder-facets .folder-name-in")).to_be_focused()
    page.keyboard.press("Enter")
    assert page.evaluate("DATA.groups.length") == 61


# ---------------------------------------------------------------------------
# Folders, round 2 (2026-10-23): code review items and QA / fuzzer findings.
# Each test names the finding it pins (docs/testing/FOLDERS_RELEASE.md, "Round 2 fixes").
# ---------------------------------------------------------------------------


def _human_press(page: Page, loc, hold: int = 80) -> None:
    """Press and release like a person: the button is down for `hold` ms."""
    loc.scroll_into_view_if_needed()
    b = loc.bounding_box()
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(hold)
    page.mouse.up()
    page.wait_for_timeout(50)


def _stuck_free(page: Page) -> None:
    assert page.evaluate("DRAG") is None
    expect(page.locator("#drag-ghost, .here-now, .drop-over, tr.dragging")).to_have_count(0)
    expect(page.locator("body")).not_to_have_class(re.compile(r"\bdragging-rows\b"))


@pytest.mark.parametrize("how", ["window-blur", "pointercancel"])
def test_a_drag_the_window_loses_leaves_nothing_held(loaded: Page, how):
    """Review #1: blur / pointercancel used to leave DRAG cancelled-but-held,
    waiting for a pointerup that never comes: the next press, text selection,
    Esc and click were all swallowed."""
    page = loaded
    before = _layout(page)
    _press(page, _first_row(page, "Lost Trail Pass").locator(".note-btn"))
    _hover_to(page, _rail(page, "North Roots"))
    expect(page.locator("#drag-ghost")).to_have_count(1)
    page.evaluate("window.dispatchEvent(new Event('blur'))" if how == "window-blur" else
                  "document.dispatchEvent(new PointerEvent('pointercancel', {pointerId: DRAG.pointerId, bubbles: true}))")
    _stuck_free(page)
    # The release happened elsewhere: what follows is a fresh start.
    page.mouse.up()
    assert _layout(page) == before
    box = _first_row(page, "Paddling").locator(".sel-box")
    box.click()
    expect(box).to_be_checked()
    page.evaluate("document.activeElement.blur()")   # (Esc in a focused checkbox is the field's)
    page.keyboard.press("Escape")            # the selection's Esc, not swallowed
    assert page.evaluate("SEL.size") == 0
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), _rail(page, "Blodgett"))
    expect(page.locator("#status")).to_have_text("Moved 1 item to Blodgett.")


def test_a_failed_layout_apply_shows_the_bridges_layout(loaded: Page):
    """Review #2: the bridge moves first; if the UI then fails to apply the
    answer it must re-sync from the bridge, or export writes a layout the
    screen never showed."""
    page = loaded
    page.evaluate("""() => { const real = applyLayout;
        window.applyLayout = r => { window.applyLayout = real; throw new Error('boom'); }; }""")
    uid = _first_row(page, "Lost Trail Pass").get_attribute("data-uid")
    _drag(page, _first_row(page, "Lost Trail Pass").locator(".note-btn"), _rail(page, "North Roots"))
    lay = dict(_layout(page))                # asserts UI == bridge
    assert lay["Lost Trail Pass"] == 30 and lay["North Roots"] == 23
    expect(_section(page, "North Roots").locator(f'tr[data-uid="{uid}"]')).to_have_count(1)
    expect(_rail(page, "North Roots").locator(".facet-count")).to_have_text("23")
    # A bridge call that raises changes nothing, and the screen still agrees.
    page.evaluate("""() => { const real = pyJSON;
        window.pyJSON = (src, v) => { window.pyJSON = real; throw new Error('bridge down'); }; }""")
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), _rail(page, "Blodgett"))
    expect(page.locator("#status")).to_contain_text("Couldn't move")
    assert dict(_layout(page))["Paddling"] == 5


@pytest.mark.parametrize("field", ["folder-name", "row-name"])
@pytest.mark.parametrize("hold", [0, 20, 80, 150])
def test_a_click_that_leaves_a_name_field_lands(loaded: Page, field, hold):
    """F1: leaving a name by pressing a checkbox lost the click: the deferred
    render rebuilt the list between pointerdown and pointerup."""
    page = loaded
    if field == "folder-name":
        _section(page, "Paddling").locator(".folder-name").click()
        page.keyboard.type("Boats")
    else:
        name = _first_row(page, "Paddling").locator(".name-in")
        name.click()
        name.evaluate("e => e.setSelectionRange(e.value.length, e.value.length)")
        page.keyboard.type(" X")
    box = _first_row(page, "Blodgett").locator(".sel-box")
    _human_press(page, box, hold)
    expect(box).to_be_checked()
    assert page.evaluate("SEL.size") == 1
    if field == "folder-name":
        assert ("Boats", 5) in _layout(page)
    else:
        assert any(v.get("name", "").endswith(" X") for v in page.evaluate("Object.values(EDITS)"))


def test_a_rail_filter_or_collapse_click_that_leaves_a_folder_name_lands(loaded: Page):
    page = loaded
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.type("Boats")
    _human_press(page, _rail(page, "Blodgett"))
    key = page.evaluate("DATA.groups.find(g => g.name === 'Blodgett').key")
    assert page.evaluate("FILTERS.folder") == key
    page.click("#chips .linkbtn")
    _section(page, "Boats").locator(".folder-name").click()
    page.keyboard.type("Boats 2")
    _human_press(page, _section(page, "North Roots").locator(".collapse"))
    nkey = page.evaluate("DATA.groups.find(g => g.name === 'North Roots').key")
    assert page.evaluate(f"COLLAPSED.has({json.dumps(nkey)})")
    assert ("Boats 2", 5) in _layout(page)


def test_leaving_a_taken_name_by_clicking_export_offers_the_merge_first(loaded: Page):
    """F2: the export ran with the old name and the merge offer opened over the
    export screen; "Move them" then changed a hidden edit screen."""
    page = loaded
    _section(page, "North Roots").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Paddling")
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("“Paddling” already exists")
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")
    assert page.evaluate("MANIFEST") is None
    page.click("#confirm-actions button:text-is('Move them')")
    lay = dict(_layout(page))
    assert "North Roots" not in lay and lay["Paddling"] == 27
    _done(page)
    assert [e["folder"] for e in page.evaluate("MANIFEST")] == [n for n, _ in _layout(page)]
    expect(page.locator("#confirm")).to_be_hidden()


def test_leaving_a_new_folders_taken_name_by_clicking_export_offers_the_merge(loaded: Page):
    page = loaded
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    expect(page.locator("#folder-facets .folder-name-in")).to_be_focused()
    page.keyboard.type("blodgett")
    page.click("#export")
    expect(page.locator("#confirm-title")).to_have_text("“Blodgett” already exists")
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")
    page.keyboard.press("Escape")
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")


def test_a_dialog_that_opens_after_a_press_stops_the_drag(loaded: Page):
    """F3: the merge offer could open between pointerdown and the 6px move, and
    a drag then ran under it."""
    page = loaded
    src = _first_row(page, "Lost Trail Pass").locator(".note-btn")
    src.scroll_into_view_if_needed()
    b = src.bounding_box()
    x, y = b["x"] + 20, b["y"] + b["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.evaluate("openConfirm({title: 'T', body: 'B', buttons: [{label: 'OK', initial: true, cancel: true, run: () => closeConfirm()}]})")
    page.mouse.move(x + 20, y + 20, steps=4)
    _stuck_free(page)
    page.mouse.up()
    page.keyboard.press("Escape")
    expect(page.locator("#confirm")).to_be_hidden()


@pytest.mark.parametrize("front", ["move-to", "merge-offer", "help"])
def test_ctrl_a_does_nothing_behind_what_is_in_front(loaded: Page, front):
    """F4: Ctrl+A under Move to…, the merge offer or Help changed the selection
    behind it (Move to… then said "Move 1 item" for 177 ticked)."""
    page = loaded
    _first_row(page, "Paddling").locator(".sel-box").check()
    if front == "move-to":
        page.click("#more-btn")
        page.click("#bulk-move")
        expect(page.locator("#move-pop")).to_be_visible()
    elif front == "merge-offer":
        _section(page, "Blodgett").locator(".folder-name").click()
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.type("Paddling")
        page.keyboard.press("Enter")
        expect(page.locator("#confirm")).to_be_visible()
    else:
        page.click("#help-link")
        expect(page.locator("#help")).to_be_visible()
    page.keyboard.press("ControlOrMeta+a")
    assert page.evaluate("SEL.size") == 1
    if front == "move-to":
        expect(page.locator("#move-h")).to_have_text("Move 1 item to")


def test_more_closes_an_open_move_to_list(loaded: Page):
    """F5: More while Move to… was open opened its menu under the list."""
    page = loaded
    _first_row(page, "Paddling").locator(".sel-box").check()
    page.click("#more-btn")
    page.click("#bulk-move")
    expect(page.locator("#move-pop")).to_be_visible()
    page.click("#more-btn")
    expect(page.locator("#move-pop")).to_be_hidden()
    expect(page.locator("#more-menu")).to_be_visible()
    page.locator("#bulk-exclude").click(timeout=3000)
    expect(_first_row(page, "Paddling")).to_have_class(re.compile(r"\bexcluded\b"))


def test_a_caltopo_folder_named_unorganized_is_an_ordinary_folder(fresh_page: Page, tmp_path):
    """F6: only the items outside every folder get the loose-items styling."""
    from tests.hardening_maps import make_map
    page = fresh_page
    doc = json.loads(make_map(2, seed=5, names=["Unorganized", "Trips"]))
    doc["features"].append({"type": "Feature", "id": "loose", "properties": {"title": "Loose", "class": "Marker"},
                            "geometry": {"type": "Point", "coordinates": [-114, 46]}})
    f = tmp_path / "twins.json"
    f.write_text(json.dumps(doc))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    expect(page.locator("#folder-facets .facet-btn.unorg")).to_have_count(1)
    flags = page.evaluate("DATA.groups.map(g => [g.key, isUnorganized(g)])")
    assert dict(flags) == {"f0": False, "f1": False, "orphaned_features": True}
    subs = page.evaluate("[...document.querySelectorAll('#folders .folder-sub')].map(e => e.textContent)")
    assert subs.count("Not in any folder") == 1


@pytest.mark.parametrize("key", ["Enter", "Escape"])
def test_enter_and_escape_in_a_row_name_keep_focus_there(loaded: Page, key):
    """F7: both blurred the field, dropping focus to the page."""
    page = loaded
    row = _first_row(page, "Paddling")
    uid = row.get_attribute("data-uid")
    name = row.locator(".name-in")
    before = name.input_value()
    name.click()
    name.evaluate("e => e.setSelectionRange(e.value.length, e.value.length)")
    page.keyboard.type(" kept")
    page.keyboard.press(key)
    field = page.locator(f'tr[data-uid="{uid}"] .name-in')
    expect(field).to_be_focused()
    expect(field).to_have_value(before + " kept" if key == "Enter" else before)
    assert (page.evaluate(f"(EDITS[{json.dumps(uid)}] || {{}}).name") ==
            (before + " kept" if key == "Enter" else None))


def test_cancel_on_a_new_folders_taken_name_reopens_its_name(loaded: Page):
    """H1: Cancel left a folder called "New folder"; it now returns to naming it."""
    page = loaded
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    page.keyboard.type("Blodgett")
    page.keyboard.press("Enter")
    expect(page.locator("#confirm-title")).to_have_text("“Blodgett” already exists")
    page.keyboard.press("Escape")                         # Cancel
    inp = page.locator("#folder-facets .folder-name-in")
    expect(inp).to_be_focused()
    expect(inp).to_have_value("Blodgett")
    # Leaving it unchanged keeps "New folder" and doesn't ask again (else
    # Cancel, reopen, leave, ask... never ends; the fuzzer found it via Export).
    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    expect(page.locator("#confirm")).to_be_hidden()
    assert ("New folder", 1) in _layout(page)
    page.click("#back")
    _drag(page, _first_row(page, "New folder").locator(".note-btn"), page.locator(".new-folder"))
    page.keyboard.type("Blodgett")
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    expect(inp).to_have_value("Blodgett")
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Kayaks")
    page.keyboard.press("Enter")
    assert ("Kayaks", 1) in _layout(page)
    # A header rename's Cancel still just keeps the old name.
    _section(page, "Kayaks").locator(".folder-name").click()
    page.keyboard.type("Blodgett")
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    expect(page.locator(".folder-name-in")).to_have_count(0)
    assert ("Kayaks", 1) in _layout(page)


def test_an_empty_name_for_a_new_folder_keeps_its_box_open(loaded: Page):
    """H5: Enter on an empty new-folder name kept "New folder" and closed the box."""
    page = loaded
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    page.keyboard.press("Backspace")
    page.keyboard.press("Enter")
    expect(page.locator("#status")).to_have_text("A folder needs a name.")
    inp = page.locator("#folder-facets .folder-name-in")
    expect(inp).to_be_focused()
    expect(inp).to_have_value("New folder")
    page.keyboard.type("Rafts")
    page.keyboard.press("Enter")
    assert ("Rafts", 1) in _layout(page)
    # H3: the error doesn't outlive the next success.
    expect(page.locator("#status")).to_have_text("")


def test_long_folder_names_are_cut_with_an_ellipsis_and_titled(loaded: Page):
    """H2: a 100-character name wrapped badly in the rail, header and export card;
    a longer paste was cut at 100 without a word."""
    page = loaded
    long = "x" * 100
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text("x" * 150)
    inp = page.locator(".folder-head .folder-name-in")
    expect(inp).to_have_value(long)
    expect(page.locator("#status")).to_have_text("A folder name can be up to 100 characters.")
    page.keyboard.press("Enter")
    cut = "e => [e.scrollWidth > e.clientWidth, getComputedStyle(e).textOverflow, e.title]"
    assert _rail(page, long).locator(".facet-name").evaluate(cut) == [True, "ellipsis", long]
    assert _section(page, long).locator(".folder-name").evaluate(cut) == [True, "ellipsis", long]
    head = _section(page, long).locator(".folder-head").bounding_box()
    sub = _section(page, long).locator(".folder-sub").bounding_box()
    assert sub["height"] < 24 and sub["y"] < head["y"] + head["height"]   # "5 items" on one line
    _done(page)
    card = page.locator("#runbook .rb-step", has=page.locator(".rb-name", has_text=long))
    assert card.locator(".rb-name").evaluate(cut) == [True, "ellipsis", long]
    expect(card.locator(".rb-dl")).to_have_attribute("aria-label", f"Download {long}")   # whole


def test_stale_status_lines_are_cleared(loaded: Page):
    """H3: "A folder needs a name." outlived later successes; "Built N folders"
    stayed after Back; the hidden "Getting ready…" status said so all session."""
    page = loaded
    assert page.locator("#drop-wait").text_content() == ""
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    page.keyboard.press("Enter")
    expect(page.locator("#status")).to_have_text("A folder needs a name.")
    _section(page, "Paddling").locator(".folder-name").click()
    expect(page.locator("#status")).to_have_text("")      # starting a rename clears it
    page.keyboard.type("Boats")
    page.keyboard.press("Enter")
    _done(page)
    expect(page.locator("#status")).to_have_text("")      # round 5: no "Built N folders" on the export screen
    page.click("#back")
    expect(page.locator("#status")).to_have_text("")


def test_the_drop_target_is_where_the_button_comes_up(loaded: Page):
    """H6: the hit test at release used the last pointermove's position."""
    page = loaded
    _press(page, _first_row(page, "Lost Trail Pass").locator(".note-btn"))
    _hover_to(page, _rail(page, "North Roots"))
    b = _rail(page, "Paddling").bounding_box()
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    page.evaluate(f"document.dispatchEvent(new PointerEvent('pointerup', "
                  f"{{pointerId: DRAG.pointerId, clientX: {x}, clientY: {y}, bubbles: true}}))")
    page.mouse.move(5, 5)
    page.mouse.up()
    expect(page.locator("#status")).to_have_text("Moved 1 item to Paddling.")
    assert dict(_layout(page))["Paddling"] == 6


def test_start_over_counts_changes_against_the_map_as_loaded(loaded: Page):
    """Review #9: moves back, renames back and merged-away folders used to count."""
    page = loaded
    row = _first_row(page, "Paddling")
    uid = row.get_attribute("data-uid")
    _drag(page, row.locator(".note-btn"), _rail(page, "Blodgett"))
    _drag(page, page.locator(f'tr[data-uid="{uid}"] .note-btn'), _rail(page, "Paddling"))
    for name in ("Boats", "Paddling"):
        _section(page, "Paddling" if name == "Boats" else "Boats").locator(".folder-name").click()
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.type(name)
        page.keyboard.press("Enter")
    assert page.evaluate("unexportedChanges()") == 0
    page.locator(".newmap").first.click()
    expect(page.locator("#confirm-body")).to_have_text("This clears the current map.")
    page.keyboard.press("Escape")
    # A merge: its 1 item moved, the merged-away folder's name is not counted.
    _section(page, "Mill Creek Canyon").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Paddling")
    page.keyboard.press("Enter")
    page.click("#confirm-actions button:text-is('Move them')")
    assert page.evaluate("unexportedChanges()") == 1


def test_with_100_or_more_folders_a_folder_zip_is_numbered_with_three_digits(fresh_page: Page, tmp_path):
    """L1 (and review #10: the download no longer builds Python source)."""
    page = fresh_page
    f = tmp_path / "many.json"
    f.write_text(_many_folders_map(105))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    _done(page)
    manifest = page.evaluate("MANIFEST")
    assert manifest[0]["files"][0]["path"].startswith("001_") and manifest[-1]["dir"].startswith("105_")
    with page.expect_download() as dl:
        page.locator("#runbook .rb-dl").first.click()
    assert dl.value.suggested_filename == manifest[0]["dir"] + ".zip"
    assert zipfile.ZipFile(dl.value.path()).namelist() == [x["path"] for x in manifest[0]["files"]]


def test_a_popover_opened_by_the_click_that_left_a_name_returns_focus_to_its_marker(loaded: Page):
    """Fuzzer re-run (round 2): the render that waits for that click replaced
    the row under the open popover; closing it then dropped focus to the page."""
    page = loaded
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.type("Boats")
    row = _first_row(page, "Blodgett")
    uid = row.get_attribute("data-uid")
    _human_press(page, row.locator(".icon-btn, .line-btn"))
    expect(page.locator("#mark-pop")).to_be_visible()
    assert ("Boats", 5) in _layout(page)           # the render ran under the popover
    page.locator("#mark-pop .swatch-btn").nth(2).click()
    page.click("#pop-apply")
    expect(page.locator("#mark-pop")).to_be_hidden()
    expect(page.locator(f'tr[data-uid="{uid}"] .icon-btn, tr[data-uid="{uid}"] .line-btn')).to_be_focused()


DARK_DIVIDE = FIXTURE.parent.parent / "dark_divide_100" / "caltopo" / "2027_Dark_Divide_100_Mile_Endurance_Run.json"
_UNCUT = "e => [e.scrollWidth <= e.clientWidth, e.scrollWidth, e.clientWidth, e.textContent]"


def _header_uncut(page: Page, name: str) -> None:
    btn = _section(page, name).locator(".folder-name")
    expect(btn).to_have_text(name)
    fits, sw, cw, text = btn.evaluate(_UNCUT)
    assert fits, f"header {text!r} is cut: scrollWidth {sw} > clientWidth {cw}"


def test_a_short_folder_name_is_never_cut_in_its_header(fresh_page: Page, tmp_path):
    """Owner, live (round 2): a new folder "Crew" with 3 items showed "Cr…" in
    its table header. Every header was clipped by 7px: the name button's -7px
    margin made its h2 that much narrower, and max-width:100% then cut it."""
    page = fresh_page
    page.set_viewport_size({"width": 1440, "height": 900})
    page.set_input_files("#file", str(DARK_DIVIDE))
    page.wait_for_function("window.__cairnLoaded === true", timeout=60000)
    for name in page.evaluate("DATA.groups.map(g => g.name)"):
        if _section(page, name).count():
            btn = _section(page, name).locator(".folder-name")
            if btn.evaluate("e => [...e.textContent].length") <= 40:
                _header_uncut(page, name)
    # A new folder named in the rail, with 3 items, made while the type filter is Lines.
    _set_type(page, "tracks")
    rows = page.locator("#folders tbody tr")
    uids = [rows.nth(i).get_attribute("data-uid") for i in range(3)]
    for u in uids:
        page.locator(f'tr[data-uid="{u}"] .sel-box').check()
    _drag(page, page.locator(f'tr[data-uid="{uids[0]}"] .line-btn'), page.locator(".new-folder"))
    expect(page.locator("#folder-facets .folder-name-in")).to_be_focused()
    page.keyboard.type("Crew")
    page.keyboard.press("Enter")
    expect(_rail(page, "Crew").locator(".facet-count")).to_have_text("3")
    _header_uncut(page, "Crew")
    assert _section(page, "Crew").locator(".folder-name").evaluate(
        "e => getComputedStyle(e).textOverflow") == "ellipsis"   # still cut when it must be
    _set_type(page, "")
    _header_uncut(page, "Crew")
    # Renamed in the header, to 1-5 characters and back to a longer name.
    for name in ("C", "Cr", "Cre", "Crew", "Crews", "Crew members"):
        _section(page, page.evaluate("DATA.groups.at(-1).name")).locator(".folder-name").click()
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.type(name)
        page.keyboard.press("Enter")
        _header_uncut(page, name)


# ---------------------------------------------------------------------------
# Round 3 (final review) fixes
# ---------------------------------------------------------------------------


def test_start_over_counts_only_changes_since_the_last_export(loaded: Page):
    """Round 3 #1: Start over compared with the map as loaded, so right after a
    successful export it still warned about every change that export wrote."""
    page = loaded
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), _rail(page, "Blodgett"))
    name = _first_row(page, "Lost Trail Pass").locator(".name-in")
    name.fill("Renamed once")
    name.dispatch_event("change")
    _section(page, "North Roots").locator(".folder-name").click()
    page.keyboard.type("South Roots")
    page.keyboard.press("Enter")
    assert page.evaluate("unexportedChanges()") == 3
    _done(page)
    page.click("#back")
    assert page.evaluate("unexportedChanges()") == 0
    page.locator(".newmap").first.click()
    expect(page.locator("#confirm-body")).to_have_text("This clears the current map.")
    page.keyboard.press("Escape")
    # After the export: a new move, a second edit of the same item, a rename.
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), _rail(page, "Blodgett"))
    assert page.evaluate("unexportedChanges()") == 1
    name = _first_row(page, "Lost Trail Pass").locator(".name-in")
    name.fill("Renamed twice")
    name.dispatch_event("change")
    assert page.evaluate("unexportedChanges()") == 2
    _section(page, "South Roots").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("North Roots")
    page.keyboard.press("Enter")
    assert page.evaluate("unexportedChanges()") == 3
    page.locator(".newmap").first.click()
    expect(page.locator("#confirm-body")).to_have_text(
        "This discards 3 unexported changes.")


def test_the_100_character_message_shows_only_when_typing_was_cut(fresh_page: Page, tmp_path):
    """Round 3 #5: the message showed at exactly 100 characters, and on every
    keystroke (deletions too) in a longer name loaded from the file."""
    from tests.hardening_maps import make_map
    page = fresh_page
    long = "L" * 150
    f = tmp_path / "long.json"
    f.write_text(make_map(2, seed=5, names=[long, "Trips"], per=(2, 2)))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    status = page.locator("#status")
    msg = "A folder name can be up to 100 characters."
    # A loaded 150-character name: deleting is not cut.
    _section(page, long).locator(".folder-name").click()
    page.keyboard.press("ArrowRight")      # off the selection, to the end
    page.keyboard.press("Backspace")
    expect(page.locator(".folder-head .folder-name-in")).to_have_value("L" * 149)
    expect(status).not_to_have_text(msg)
    page.keyboard.press("Escape")
    # Typing up to exactly 100 is fine; the 101st character is cut and said so.
    _section(page, "Trips").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text("x" * 99)
    page.keyboard.type("y")
    inp = page.locator(".folder-head .folder-name-in")
    expect(inp).to_have_value("x" * 99 + "y")
    expect(status).not_to_have_text(msg)
    page.keyboard.type("z")
    expect(inp).to_have_value("x" * 99 + "y")
    expect(status).to_have_text(msg)
    # Under the limit again: the message goes.
    page.keyboard.press("Backspace")
    expect(status).not_to_have_text(msg)


def test_export_boxes_of_folders_with_the_same_name_show_their_numbers(fresh_page: Page, tmp_path):
    """Round 3 #3: two folders called "Camp" (CalTopo allows it) had identical
    export boxes, while their downloads were 01_Camp.zip and 02_Camp.zip. Only
    where names (or file names) collide, the box shows its number and its
    chips their NN_ path; every other box is unchanged."""
    from tests.hardening_maps import make_map
    page = fresh_page
    f = tmp_path / "twins.json"
    f.write_text(make_map(5, seed=3, names=["Camp", "camp ", "A B", "A_B", "Trips"], per=(2, 2), kinds="w"))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    _done(page)
    manifest = page.evaluate("MANIFEST")
    boxes = page.locator("#runbook .rb-step")
    for i, e in enumerate(manifest):
        box, num = boxes.nth(i), e["dir"].split("_")[0]
        twin = e["folder"].strip().lower() == "camp"
        file_twin = twin or e["folder"] in ("A B", "A_B")
        expect(box.locator(".rb-name")).to_have_text(e["folder"])
        if twin:
            expect(box.locator(".rb-num")).to_have_text(f"{num} ·")
            # Round 4: the button's accessible name carries the number too.
            expect(box.locator(".rb-dl")).to_have_attribute("aria-label", f"Download {num} · {e['folder']}")
        else:
            expect(box.locator(".rb-num")).to_have_count(0)
            expect(box.locator(".rb-dl")).to_have_attribute("aria-label", f"Download {e['folder']}")
        expect(box.locator(".rb-file")).to_have_text(
            [f["path"] if file_twin else f["path"].split("/")[-1] for f in e["files"]])
    assert page.locator("#runbook .rb-num").count() == 2
    # Downloads stay numbered like the box says.
    with page.expect_download() as dl:
        boxes.nth(0).locator(".rb-dl").click()
    assert dl.value.suggested_filename == manifest[0]["dir"] + ".zip"


# ---------------------------------------------------------------------------
# Round 4: edit-screen follow-ups (docs/testing/FOLDERS_RELEASE.md "Round 4")
# ---------------------------------------------------------------------------

FOLLOWUPS = Path(__file__).resolve().parents[1] / "output" / "followups"


def _shot(page: Page, name: str) -> None:
    """A 1440x900 screenshot for the owner (tests/output is local scratch)."""
    FOLLOWUPS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(FOLLOWUPS / f"{name}.png"))


def _wide(page: Page) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})


# --- 1. + New folder is a button; an empty folder up front -------------------


def test_clicking_new_folder_with_nothing_ticked_makes_an_empty_folder(loaded: Page):
    page = loaded
    _wide(page)
    before = _layout(page)
    nf = page.locator("#folder-facets .new-folder")
    expect(nf).to_have_js_property("tagName", "BUTTON")
    nf.click()
    inp = page.locator("#folder-facets .folder-name-in")
    expect(inp).to_be_focused()
    expect(inp).to_have_value("New folder")
    expect(page.locator("#status")).to_have_text("Made an empty folder.")
    page.keyboard.type("Water")
    page.keyboard.press("Enter")
    lay = _layout(page)
    assert [x for x in lay if x != ("Water", 0)] == before and ("Water", 0) in lay
    # In the rail with count 0; in the list as a header only, renamable there.
    expect(_rail(page, "Water").locator(".facet-count")).to_have_text("0")
    sec = page.locator("section.folder.empty-folder")
    expect(sec).to_have_count(1)
    expect(sec.locator(".folder-name")).to_have_text("Water")
    expect(sec.locator(".folder-sub")).to_have_text("Empty")
    expect(sec.locator("tbody tr")).to_have_count(0)
    sec.scroll_into_view_if_needed()
    _shot(page, "1a-empty-folder-made")
    # It is a drop target like any other.
    row = _first_row(page, "Paddling")
    uid = row.get_attribute("data-uid")
    _drag(page, row.locator(".note-btn"), _rail(page, "Water"))
    expect(page.locator("#status")).to_have_text("Moved 1 item to Water.")
    assert dict(_layout(page))["Water"] == 1
    expect(page.locator("section.folder.empty-folder")).to_have_count(0)
    # Emptied again by a move, it goes, as before.
    _drag(page, page.locator(f'tr[data-uid="{uid}"] .note-btn'), _rail(page, "Paddling"))
    assert "Water" not in dict(_layout(page))


def test_new_folder_responds_to_enter_and_space(loaded: Page):
    page = loaded
    nf = page.locator("#folder-facets .new-folder")
    nf.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#folder-facets .folder-name-in")).to_be_focused()
    page.keyboard.press("Escape")                     # round 5: takes the empty folder back
    assert "New folder" not in [n for n, c in _layout(page)]
    page.locator("#folder-facets .new-folder").focus()
    page.keyboard.press(" ")
    expect(page.locator("#folder-facets .folder-name-in")).to_have_value("New folder")
    page.keyboard.press("Enter")
    assert ("New folder", 0) in _layout(page)


def test_clicking_new_folder_with_rows_ticked_moves_them_into_it(loaded: Page):
    page = loaded
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    uids = [rows.nth(i).get_attribute("data-uid") for i in (0, 3)]
    for u in uids:
        page.locator(f'tr[data-uid="{u}"] .sel-box').check()
    page.locator("#folder-facets .new-folder").click()
    expect(page.locator("#status")).to_have_text("Moved 2 items to a new folder.")
    expect(page.locator("#folder-facets .folder-name-in")).to_be_focused()
    page.keyboard.type("Picked")
    page.keyboard.press("Enter")
    lay = _layout(page)
    assert ("Picked", 2) in lay and dict(lay)["Lost Trail Pass"] == 29
    assert page.evaluate("SEL.size") == 0
    # A drop on + New folder is still a drop, not also a click (no second folder).
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    page.keyboard.press("Enter")
    assert [n for n, _ in _layout(page)].count("New folder") == 1
    assert len(_layout(page)) == 12


def test_an_empty_folder_can_be_removed_with_its_x(loaded: Page):
    page = loaded
    _wide(page)
    page.locator("#folder-facets .new-folder").click()
    page.keyboard.press("Enter")
    row = page.locator("#folder-facets .facet-row.empty")
    expect(row).to_have_count(1)
    x = row.locator(".facet-x")
    expect(x).to_have_attribute("aria-label", "Remove empty folder New folder")
    # Shown on hover or focus within the entry (Enter left focus on it).
    expect(x).to_have_css("opacity", "1")
    page.locator("#filter").focus()
    page.mouse.move(900, 600)
    expect(x).to_have_css("opacity", "0")
    row.hover()
    expect(x).to_have_css("opacity", "1")
    _shot(page, "1b-remove-empty-folder")
    # Folders with items have no ×.
    expect(page.locator("#folder-facets .facet-x")).to_have_count(1)
    # Keyboard: Tab from the entry reaches the ×; Enter removes; focus lands
    # on the next entry: "New folder" sorts before North Roots.
    _rail(page, "New folder").focus()
    page.keyboard.press("Tab")
    expect(x).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#status")).to_have_text("Removed the empty folder “New folder”.")
    expect(_rail(page, "North Roots")).to_be_focused()
    assert len(_layout(page)) == 10
    expect(page.locator("section.folder.empty-folder")).to_have_count(0)
    # A removed folder filter goes back to All.
    page.locator("#folder-facets .new-folder").click()
    page.keyboard.press("Enter")
    _rail(page, "New folder").click()
    assert page.evaluate("FILTERS.folder") is not None
    expect(page.locator("section.folder")).to_have_count(1)    # just the empty header
    page.locator("#folder-facets .facet-x").click()
    assert page.evaluate("FILTERS.folder") is None
    expect(page.locator("section.folder")).to_have_count(10)


def test_an_empty_folder_is_not_exported_and_numbers_close_up(loaded: Page):
    page = loaded
    page.locator("#folder-facets .new-folder").click()
    page.keyboard.type("Nothing yet")
    page.keyboard.press("Enter")
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    page.keyboard.type("Boat")
    page.keyboard.press("Enter")
    zf = _export_zip(page)
    manifest = page.evaluate("MANIFEST")
    # "Boat" sorts after Blodgett; the empty "Nothing yet" (between North Roots
    # and Paddling) takes no number, so the numbers close up around it.
    assert [e["folder"] for e in manifest][1] == "Boat" and len(manifest) == 11
    assert manifest[1]["dir"] == "02_Boat"
    assert [e["dir"][:2] for e in manifest] == [f"{k:02d}" for k in range(1, 12)]
    assert not [n for n in zf.namelist() if "Nothing" in n]
    boxes = page.locator("#runbook .rb-step .rb-name")
    expect(boxes).to_have_count(11)
    assert "Nothing yet" not in boxes.all_inner_texts()
    # Start over after the export: no change left to count.
    page.click("#back")
    assert page.evaluate("unexportedChanges()") == 0


def test_start_over_counts_a_new_empty_folder_and_a_removed_one(loaded: Page):
    page = loaded
    page.locator("#folder-facets .new-folder").click()
    page.keyboard.press("Enter")
    assert page.evaluate("unexportedChanges()") == 1
    page.locator("#folder-facets .facet-x").click()
    assert page.evaluate("unexportedChanges()") == 0


def test_an_empty_folders_taken_name_is_refused_without_a_merge_offer(loaded: Page):
    page = loaded
    page.locator("#folder-facets .new-folder").click()
    page.keyboard.type("paddling")
    page.keyboard.press("Enter")
    expect(page.locator("#confirm")).to_be_hidden()
    expect(page.locator("#status")).to_have_text("“Paddling” already exists.")
    assert ("New folder", 0) in _layout(page)
    # The same from its header.
    page.locator("section.folder.empty-folder .folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Blodgett")
    page.keyboard.press("Enter")
    expect(page.locator("#confirm")).to_be_hidden()
    expect(page.locator("#status")).to_have_text("“Blodgett” already exists.")
    assert ("New folder", 0) in _layout(page)


# --- 2. Full names and notes on hover ----------------------------------------

LONG_NOTE = "Water at the spring\nBring a filter: it runs low by August.\n\nCamp 200 m north."




def _tip(page: Page):
    return page.locator("#tip")


def test_a_notes_preview_is_its_first_line_and_hover_shows_all_of_it(loaded: Page):
    page = loaded
    _wide(page)
    row = _first_row(page, "Lost Trail Pass")
    uid = row.get_attribute("data-uid")
    _set(page, uid, desc="\n" + LONG_NOTE)
    note = page.locator(f'tr[data-uid="{uid}"] .note-btn')
    expect(note.locator(".note-text")).to_have_text("Water at the spring")
    # Not the native title (it loses line breaks and can't be styled).
    assert note.get_attribute("title") is None and note.locator(".note-text").get_attribute("title") is None
    note.hover()
    page.wait_for_timeout(150)
    expect(_tip(page)).to_be_hidden()                  # a short delay first
    expect(_tip(page)).to_be_visible()
    assert _tip(page).inner_text() == LONG_NOTE        # whole, with its line breaks
    expect(_tip(page)).to_have_css("white-space", "pre-wrap")
    expect(note).to_have_attribute("aria-describedby", "tip")
    _shot(page, "2a-note-on-hover")
    # The pointer can move onto the tip, and its text can be selected.
    tb = _tip(page).bounding_box()
    nb = note.bounding_box()
    assert tb["y"] >= nb["y"] + nb["height"]           # below the note, not over it
    page.mouse.move(tb["x"] + 10, tb["y"] + 8, steps=4)
    page.wait_for_timeout(400)
    expect(_tip(page)).to_be_visible()
    page.mouse.dblclick(tb["x"] + 20, tb["y"] + 16)    # a word on its first line
    picked = page.evaluate("getSelection().toString()").strip()
    assert picked and picked in LONG_NOTE
    expect(_tip(page)).to_be_visible()
    assert page.evaluate("SEL.size") == 0              # the click there selected no row
    # Esc closes the tip and nothing else.
    page.keyboard.press("Escape")
    expect(_tip(page)).to_be_hidden()
    assert note.get_attribute("aria-describedby") is None
    # Leaving both hides it too.
    note.hover()
    expect(_tip(page)).to_be_visible()
    page.mouse.move(700, 880)
    expect(_tip(page)).to_be_hidden()


def test_leaving_across_another_rows_name_still_hides_the_tip(loaded: Page):
    """Fuzzer, round 4: leaving a note's tip by crossing another row's name
    (one with no tip of its own) cancelled the hide, and the tip stayed up."""
    page = loaded
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    uid = rows.nth(1).get_attribute("data-uid")
    _set(page, uid, desc=LONG_NOTE)
    page.locator(f'tr[data-uid="{uid}"] .note-btn').hover()
    expect(_tip(page)).to_be_visible()
    name = rows.nth(0).locator(".name-in").bounding_box()
    page.mouse.move(name["x"] + 20, name["y"] + name["height"] / 2, steps=3)
    page.mouse.move(120, 60, steps=3)
    page.wait_for_timeout(700)
    expect(_tip(page)).to_be_hidden()


def test_a_short_note_or_name_shows_no_tip(loaded: Page):
    page = loaded
    row = _first_row(page, "Paddling")
    uid = row.get_attribute("data-uid")
    _set(page, uid, desc="Short.")
    page.locator(f'tr[data-uid="{uid}"] .note-btn').hover()
    page.locator(f'tr[data-uid="{uid}"] .name-in').hover()
    page.wait_for_timeout(800)
    expect(_tip(page)).to_be_hidden()


def test_a_cut_name_or_one_long_line_shows_whole_on_hover(loaded: Page):
    page = loaded
    _wide(page)
    row = _first_row(page, "North Roots")
    uid = row.get_attribute("data-uid")
    long_name = "Upper North Roots saddle camp below the third false summit, east side"
    long_line = "A single line of note that is far too long to fit in its column " * 3
    _set(page, uid, name=long_name, desc=long_line.strip())
    name = page.locator(f'tr[data-uid="{uid}"] .name-in')
    name.hover()
    expect(_tip(page)).to_be_visible()
    assert _tip(page).inner_text() == long_name
    page.mouse.move(700, 880)
    expect(_tip(page)).to_be_hidden()
    page.locator(f'tr[data-uid="{uid}"] .note-btn').hover()
    expect(_tip(page)).to_have_text(long_line.strip())


def test_the_tip_shows_on_keyboard_focus_and_not_on_a_click(loaded: Page):
    page = loaded
    row = _first_row(page, "Lost Trail Pass")
    uid = row.get_attribute("data-uid")
    _set(page, uid, desc=LONG_NOTE)
    page.locator(f'tr[data-uid="{uid}"] .name-in').focus()
    page.keyboard.press("Tab")                         # name -> note button
    expect(page.locator(f'tr[data-uid="{uid}"] .note-btn')).to_be_focused()
    expect(_tip(page)).to_be_visible()
    assert _tip(page).inner_text() == LONG_NOTE
    page.keyboard.press("Escape")
    expect(_tip(page)).to_be_hidden()
    expect(page.locator(f'tr[data-uid="{uid}"] .note-btn')).to_be_focused()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(_tip(page)).to_be_visible()
    page.keyboard.press("Tab")                         # leaving it hides it
    expect(_tip(page)).to_be_hidden()
    # A click opens the note editor, with no tip in the way.
    page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    expect(page.locator(f'tr[data-uid="{uid}"] .desc-in')).to_be_focused()
    page.wait_for_timeout(600)
    expect(_tip(page)).to_be_hidden()


def test_the_tip_stays_inside_the_window_and_off_its_control(loaded: Page):
    page = loaded
    _wide(page)
    rows = page.locator(f"{ROW}")
    # The last row visible at the bottom of the window: the tip goes above it.
    uid = page.evaluate("""() => { const vh = innerHeight;
        const r = [...document.querySelectorAll('.folder tbody tr')].filter(t => {
          const b = t.getBoundingClientRect(); return b.bottom < vh && b.bottom > vh - 60; });
        return r.at(-1).dataset.uid; }""")
    _set(page, uid, desc=("Line\n" * 12).strip())
    note = page.locator(f'tr[data-uid="{uid}"] .note-btn')
    note.hover()
    expect(_tip(page)).to_be_visible()
    tb, nb = _tip(page).bounding_box(), note.bounding_box()
    assert tb["y"] >= 0 and tb["y"] + tb["height"] <= 900 and tb["x"] + tb["width"] <= 1440
    assert tb["y"] + tb["height"] <= nb["y"]           # above it
    _shot(page, "2b-note-tip-above")
    assert rows.count() > 0


def test_a_drag_still_starts_from_a_note_with_its_tip_showing(loaded: Page):
    page = loaded
    row = _first_row(page, "Lost Trail Pass")
    uid = row.get_attribute("data-uid")
    _set(page, uid, desc=LONG_NOTE)
    note = page.locator(f'tr[data-uid="{uid}"] .note-btn')
    note.hover()
    expect(_tip(page)).to_be_visible()
    _drag(page, note, _rail(page, "Paddling"))
    expect(page.locator("#status")).to_have_text("Moved 1 item to Paddling.")
    expect(_tip(page)).to_be_hidden()
    assert page.evaluate("NOTE_EDIT") is None


# --- 3. Sortable Name column --------------------------------------------------

AID = "2 - Aid Stations Dark Divide 100 Miler"
SEGMENTS = "3 - Course Segments Dark Divide 100 Miler"


def _dark_divide(page: Page) -> Page:
    _wide(page)
    page.set_input_files("#file", str(DARK_DIVIDE))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    return page


def _names(page: Page, folder: str) -> list:
    return _section(page, folder).locator("tbody .name-in").evaluate_all("els => els.map(e => e.value)")


def _sort_states(page: Page) -> list:
    return page.locator("th.name-th").evaluate_all("els => els.map(e => e.getAttribute('aria-sort'))")


def _sort_of(page: Page, folder: str) -> str:
    return _section(page, folder).locator("th.name-th").get_attribute("aria-sort")


def test_the_name_header_cycles_ascending_descending_and_map_order(fresh_page: Page):
    """Per folder (owner feedback 2026-10-24): sorting one folder leaves the
    others as they are; each keeps its own state."""
    page = _dark_divide(fresh_page)
    as_loaded = _names(page, AID)
    assert as_loaded[:3] == ["04 - Dark Creek AS", "05 - Wilderness Crossing AS", "06 - Wright Meadow AS"]
    seg_loaded = _names(page, SEGMENTS)
    assert set(_sort_states(page)) == {"none"}
    _section(page, AID).locator(".sort-btn").click()
    assert _sort_of(page, AID) == "ascending" and _sort_of(page, SEGMENTS) == "none"
    assert _names(page, AID) == sorted(as_loaded)
    assert _names(page, SEGMENTS) == seg_loaded            # not sorted with it
    expect(_section(page, AID).locator(".sort-btn")).to_be_focused()
    _shot(page, "3a-sorted-ascending")
    _shot(page, "fb-5a-one-folder-sorted")
    page.keyboard.press("Enter")                       # the focused header again
    assert _sort_of(page, AID) == "descending" and _sort_of(page, SEGMENTS) == "none"
    assert _names(page, AID) == sorted(as_loaded, reverse=True)
    # The other folder sorts on its own; AID keeps its state.
    _section(page, SEGMENTS).locator(".sort-btn").click()
    assert _sort_of(page, SEGMENTS) == "ascending" and _sort_of(page, AID) == "descending"
    assert [n[:2] for n in _names(page, SEGMENTS)] == [f"{i:02d}" for i in range(1, 12)]
    assert _names(page, AID) == sorted(as_loaded, reverse=True)
    _section(page, SEGMENTS).evaluate("e => e.scrollIntoView()")
    _shot(page, "fb-5b-two-folders-two-sorts")
    _section(page, AID).locator(".sort-btn").click()
    assert _sort_of(page, AID) == "none" and _sort_of(page, SEGMENTS) == "ascending"
    assert _names(page, AID) == as_loaded
    _section(page, SEGMENTS).locator(".sort-btn").click()
    _section(page, SEGMENTS).locator(".sort-btn").click()
    assert set(_sort_states(page)) == {"none"}
    assert _names(page, AID) == as_loaded and _names(page, SEGMENTS) == seg_loaded
    # View only: the map's order underneath never changed.
    assert page.evaluate(f"DATA.groups.find(g => g.name === {AID!r}).items.map(i => i.name)") == as_loaded


def test_the_name_sort_is_natural_and_case_insensitive(loaded: Page):
    page = loaded
    uids = _section(page, "Paddling").locator("tbody tr").evaluate_all("els => els.map(e => e.dataset.uid)")
    for u, n in zip(uids, ["camp 10", "Camp 2", "beach", "CAMP 1", "Apple"]):
        _set(page, u, name=n)
    _section(page, "Paddling").locator(".sort-btn").click()
    assert _names(page, "Paddling") == ["Apple", "beach", "CAMP 1", "Camp 2", "camp 10"]


def test_sorting_does_not_change_the_export(fresh_page: Page):
    page = _dark_divide(fresh_page)
    plain = _export_zip(page)
    page.click("#back")
    _section(page, AID).locator(".sort-btn").click()
    sorted_zip = _export_zip(page)
    assert sorted_zip.namelist() == plain.namelist()
    for n in plain.namelist():
        assert sorted_zip.read(n) == plain.read(n), n


def test_shift_click_drag_and_move_to_follow_the_sorted_rows(fresh_page: Page):
    page = _dark_divide(fresh_page)
    _section(page, SEGMENTS).locator(".sort-btn").click()
    _section(page, AID).locator(".sort-btn").click()
    rows = _section(page, AID).locator("tbody tr")
    shown = rows.evaluate_all("els => els.map(e => e.dataset.uid)")
    rows.nth(1).locator(".sel-box").click()
    rows.nth(4).locator(".sel-box").click(modifiers=["Shift"])
    # The range is the four rows on screen between them, not the map's order.
    assert sorted(page.evaluate("[...SEL]")) == sorted(shown[1:5])
    # Drag them (sorted) to another folder.
    _drag(page, rows.nth(2).locator(".note-btn"), _rail(page, SEGMENTS))
    expect(page.locator("#status")).to_have_text(f"Moved 4 items to {SEGMENTS}.")
    assert set(shown[1:5]) <= set(page.evaluate(
        f"DATA.groups.find(g => g.name === {SEGMENTS!r}).items.map(i => i.uid)"))
    # Shown in their new folder's sort (it is sorted A to Z too; waypoints and
    # lines together by name).
    names = _names(page, SEGMENTS)
    assert names == page.evaluate("ns => [...ns].sort((a, b) => NAME_ORDER.compare(a, b))", names)
    # Move to… from the keyboard with the sort on.
    first = _section(page, AID).locator("tbody tr").first
    u = first.get_attribute("data-uid")
    first.locator(".sel-box").click()
    page.locator("#more-btn").click()
    page.locator("#bulk-move").click()
    page.locator(f"#move-pop .move-opt[data-key]:not([disabled])", has_text=SEGMENTS).click()
    assert u in page.evaluate(f"DATA.groups.find(g => g.name === {SEGMENTS!r}).items.map(i => i.uid)")
    assert _sort_of(page, AID) == "ascending" and _sort_of(page, SEGMENTS) == "ascending"


def test_a_folders_sort_follows_its_key_through_moves_renames_and_merges(loaded: Page):
    """Owner feedback 2026-10-24 (UI-35): the state belongs to the folder.
    Rename keeps it; items moved in show in the target's state (an unsorted
    target keeps the map's order); a merge's target keeps its own and the
    merged-away folder's state goes; a new folder starts unsorted."""
    page = loaded
    _section(page, "Paddling").locator(".sort-btn").click()
    _section(page, "Blodgett").locator(".sort-btn").click()
    _section(page, "Blodgett").locator(".sort-btn").click()          # Z to A
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Kayaks")
    page.keyboard.press("Enter")
    assert _sort_of(page, "Kayaks") == "ascending" and _sort_of(page, "Blodgett") == "descending"
    # Moved into an unsorted folder: the map's order there.
    _drag(page, _first_row(page, "Kayaks").locator(".note-btn"), _rail(page, "North Roots"))
    assert _sort_of(page, "North Roots") == "none"
    assert _names(page, "North Roots") == page.evaluate(
        "DATA.groups.find(g => g.name === 'North Roots').items.map(i => i.name)")
    # A new folder starts unsorted.
    _drag(page, _first_row(page, "Kayaks").locator(".note-btn"), page.locator(".new-folder"))
    page.keyboard.type("Boats")
    page.keyboard.press("Enter")
    assert _sort_of(page, "Boats") == "none"
    # Merge Kayaks into Blodgett: Blodgett keeps Z to A, Kayaks' state is gone.
    _section(page, "Kayaks").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Blodgett")
    page.keyboard.press("Enter")
    page.click("#confirm-actions button:text-is('Move them')")
    assert _sort_of(page, "Blodgett") == "descending"
    names = _names(page, "Blodgett")
    assert names == page.evaluate("ns => [...ns].sort((a, b) => NAME_ORDER.compare(b.trim(), a.trim()))", names)
    keys = page.evaluate("[...SORT.keys()]")
    assert keys == [page.evaluate("DATA.groups.find(g => g.name === 'Blodgett').key")]


# --- 4. Per-item caution: what won't carry over --------------------------------


def _caution(page: Page, uid: str):
    return page.locator(f'tr[data-uid="{uid}"] .caution')


def test_a_note_over_onxs_limit_gets_a_caution_that_goes_when_it_is_shortened(loaded: Page):
    page = loaded
    _wide(page)
    uid = _first_row(page, "Lost Trail Pass").get_attribute("data-uid")
    expect(_caution(page, uid)).to_have_count(0)
    _set(page, uid, desc="x" * 600)
    msg = "onX imports only the first 512 bytes of a note. About 88 characters will be cut."
    expect(_caution(page, uid)).to_have_attribute("aria-label", msg)
    _caution(page, uid).hover()
    expect(_tip(page)).to_have_text(msg)
    _shot(page, "4a-long-note-caution")
    _shot(page, "fb-2a-long-note-caution")
    # Bytes, not characters: 300 "é" are 600 bytes, of which 256 fit.
    _set(page, uid, desc="é" * 300)
    expect(_caution(page, uid)).to_have_attribute(
        "aria-label", "onX imports only the first 512 bytes of a note. About 44 characters will be cut.")
    # Exactly 512 bytes: no caution. Shortened in the note editor: gone at once.
    _set(page, uid, desc="x" * 512)
    expect(_caution(page, uid)).to_have_count(0)
    # Measured as written to the GPX (outer whitespace trimmed), like instructions.txt.
    _set(page, uid, desc="   " + "x" * 512 + "\r\n\n  ")
    expect(_caution(page, uid)).to_have_count(0)
    _set(page, uid, desc="x" * 513)
    expect(_caution(page, uid)).to_have_count(1)
    page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    page.locator(".desc-in").fill("x" * 400)
    page.click(".note-apply")
    expect(_caution(page, uid)).to_have_count(0)
    # Keyboard: the mark is a focus stop with its tip.
    _set(page, uid, desc="y" * 700)
    page.wait_for_timeout(350)                         # not right after a click (pointer focus)
    _caution(page, uid).focus()
    expect(_tip(page)).to_have_text(
        "onX imports only the first 512 bytes of a note. About 188 characters will be cut.")
    page.keyboard.press("Escape")
    # An excluded row isn't exported: no caution.
    _set(page, uid, included=False)
    expect(_caution(page, uid)).to_have_count(0)


def test_the_caution_marks_the_same_notes_the_export_lists(fresh_page: Page, tmp_path):
    from tests.hardening_maps import make_map
    page = fresh_page
    f = tmp_path / "notes.json"
    f.write_text(make_map(3, seed=4, per=(4, 6), long_notes=True))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    marked = page.locator("tr[data-uid]:has(.caution)").evaluate_all(
        "els => els.map(e => e.querySelector('.name-in').value)")
    assert marked
    _done(page)
    listed = [n for e in page.evaluate("MANIFEST") for n, _bytes in e["long_notes"]]
    assert sorted(marked) == sorted(listed)
    # Several: "Items “a”, “b” are over …" (owner's wording, 2026-10-24; curly quotes and
    # "Untitled" for a nameless item since 2026-10-25), up to 8 names.
    assert len(listed) >= 2
    quoted = [f"\u201c{n or 'Untitled'}\u201d" for n in listed]
    shown = ", ".join(quoted) if len(quoted) <= 8 else f"{', '.join(quoted[:8])} and {len(quoted) - 8} more"
    expect(page.locator("#runbook .note.warn", has_text="length limit")).to_have_text(
        f"Items {shown} are over the length limit and will be truncated by onX.")
    _wide(page)
    _shot(page, "fb-12-export-long-notes-warning")


def test_the_long_note_warning_names_eight_then_says_how_many_more(fresh_page: Page, tmp_path):
    page = fresh_page
    feats = [{"type": "Feature", "id": f"w{k}", "geometry": {"type": "Point", "coordinates": [-114 + k / 1e3, 45.0]},
              "properties": {"class": "Marker", "title": f"temp {k}", "description": "x" * 600}}
             for k in range(1, 12)]
    f = tmp_path / "many.json"
    f.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    _done(page)
    names = ", ".join(f"\u201ctemp {k}\u201d" for k in range(1, 9))
    expect(page.locator("#runbook .note.warn")).to_have_text(
        f"Items {names} and 3 more are over the length limit and will be truncated by onX.")


def test_an_onx_area_whose_fill_onx_resets_gets_a_caution(fresh_page: Page):
    page = fresh_page
    _wide(page)
    fx = FX_DIR / "onx_exports"
    page.set_input_files("#file", [str(fx / "areas-after-edit.gpx"), str(fx / "areas-after-edit.kml")])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    _keep_fills(page)
    msg = "onX will reset this area's fill to its default blue."
    areas = page.evaluate("allItems().filter(i => i.kind === 'shapes').map(i => [i.uid, i.fill])")
    assert len(areas) == 4
    for uid, fill in areas:
        expect(_caution(page, uid)).to_have_attribute("aria-label", msg)
        # Owner feedback 2026-10-24: in the Icon cell, after "Area", at its far
        # right; nothing beside the note.
        row = page.locator(f'tr[data-uid="{uid}"]')
        expect(row.locator("td.iconcol .caution.fill-caution")).to_have_count(1)
        expect(row.locator("td.notecol .caution")).to_have_count(0)
        geo = row.evaluate("""tr => { const td = tr.querySelector('td.iconcol').getBoundingClientRect();
            const m = tr.querySelector('.fill-caution').getBoundingClientRect();
            const b = tr.querySelector('.line-btn').getBoundingClientRect();
            return {gap: td.right - m.right, after: m.left >= b.right, mid: Math.abs((m.top + m.bottom) - (b.top + b.bottom)) / 2}; }""")
        assert geo["after"] and geo["gap"] <= 20 and geo["mid"] <= 2, geo
    _caution(page, areas[0][0]).hover()
    expect(_tip(page)).to_have_text(msg)
    _shot(page, "4b-area-fill-caution")
    _shot(page, "fb-8-area-fill-caution-in-icon-cell")
    # A long note on the same area: its own mark beside the note, each with its own tip.
    _set(page, areas[2][0], desc="x" * 600)
    row = page.locator(f'tr[data-uid="{areas[2][0]}"]')
    expect(row.locator(".caution")).to_have_count(2)
    expect(row.locator("td.notecol .caution")).to_have_attribute("aria-label", re.compile(r"^onX imports only the first 512 bytes"))
    page.mouse.move(5, 5)
    row.locator("td.notecol .caution").hover()
    expect(_tip(page)).to_have_text(re.compile(r"^onX imports only the first 512 bytes"))
    page.mouse.move(5, 5)
    row.locator(".fill-caution").hover()
    expect(_tip(page)).to_have_text(msg)
    # A transparent ("none") or default fill: no caution.
    page.evaluate("([u, v]) => { const it = allItems().find(i => i.uid === u); it.fill = v; renderFolders(); }",
                  [areas[0][0], "rgba(0,0,0,0)"])
    expect(_caution(page, areas[0][0])).to_have_count(0)
    page.evaluate("([u, v]) => { const it = allItems().find(i => i.uid === u); it.fill = v; renderFolders(); }",
                  [areas[1][0], "rgba(74,144,226,0.1)"])
    expect(_caution(page, areas[1][0])).to_have_count(0)
    # Waypoints and lines of the same onX map: none.
    expect(page.locator("tr:has(.icon-btn) .caution")).to_have_count(0)


def test_an_item_with_no_coordinates_says_it_will_not_export(fresh_page: Page, tmp_path):
    from tests.hardening_maps import make_map
    page = fresh_page
    f = tmp_path / "nc.json"
    f.write_text(make_map(2, seed=1, no_coords=True))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    uids = page.evaluate("allItems().filter(i => i.no_coords).map(i => i.uid)")
    assert len(uids) == 2
    for u in uids:
        expect(_caution(page, u)).to_have_attribute("aria-label", "Won't export: it has no coordinates.")
    expect(page.locator(".caution")).to_have_count(2)


def test_no_caution_on_a_plain_caltopo_map(loaded: Page):
    long_notes = loaded.evaluate("allItems().filter(i => new TextEncoder().encode(i.desc || '').length > 512).length")
    expect(loaded.locator(".caution")).to_have_count(long_notes)


# --- 5. Pin colour apart from line colour in the several-items dialog ---------


def _items_of(page: Page, kind: str, folder: str = "Lost Trail Pass", n: int = 2) -> list:
    return page.evaluate(
        "([f, k, n]) => DATA.groups.find(g => g.name === f).items.filter(i => i.kind === k).slice(0, n).map(i => i.uid)",
        [folder, kind, n])




def _color(page: Page, uid: str) -> str:
    return page.evaluate("u => allItems().find(i => i.uid === u).color", uid)


def test_the_bulk_button_says_color_and_style_for_lines_and_areas_only(loaded: Page):
    page = loaded
    _wide(page)
    btn = page.locator("#bulk-icon")
    lines = _items_of(page, "tracks")
    _tick(page, lines)
    expect(btn).to_have_text("Color & style…")
    _shot(page, "5a-color-button-lines-only")
    btn.click()
    d = page.locator("#mark-dialog")
    expect(d).to_have_attribute("aria-label", "Change color and style for 2 items")
    expect(d.locator(".sec-row > .label")).to_have_text(["Color", "Style", "Weight"])
    expect(d.locator(".swatch-btn")).to_have_count(11)
    page.click("#mark-dialog .bulk-cancel")
    _clear_selection(page)
    area = page.evaluate("allItems().find(i => i.kind === 'shapes').uid")
    _tick(page, [area])
    expect(btn).to_have_text("Color & style…")
    _clear_selection(page)
    wps = _items_of(page, "waypoints")
    _tick(page, wps)
    expect(btn).to_have_text("Icon & color…")
    _tick(page, lines)                                  # mixed
    expect(btn).to_have_text("Icon & color…")
    _clear_selection(page)
    expect(btn).to_have_text("Icon & color…")


def test_a_mixed_selection_picks_pin_and_line_colors_apart(loaded: Page):
    page = loaded
    _wide(page)
    wps, lines = _items_of(page, "waypoints"), _items_of(page, "tracks")
    before = {u: _color(page, u) for u in wps + lines}
    _tick(page, wps + lines)
    page.click("#bulk-icon")
    d = page.locator("#mark-dialog")
    expect(d.locator(".sec-row > .label")).to_have_text(["Waypoint color", "Icon", "Line color", "Style", "Weight"])
    pin, line = d.locator('.pop-sec[data-row="pin"]'), d.locator('.pop-sec[data-row="line"]')
    expect(pin.locator(".swatch-btn")).to_have_count(10)
    expect(line.locator(".swatch-btn")).to_have_count(11)
    for row in (pin, line):
        expect(row.locator(".color-reset")).to_have_text("Leave as is")
        expect(row.locator(".color-reset")).to_have_attribute("aria-pressed", "true")
    # Pick a pin colour only: the lines' After marks don't change.
    pin.locator('.swatch-btn[aria-label="Red"]').click()
    expect(pin.locator(".color-reset")).to_have_attribute("aria-pressed", "false")
    expect(line.locator(".color-reset")).to_have_attribute("aria-pressed", "true")
    _shot(page, "5b-mixed-dialog-pin-and-line")
    page.click("#bulk-apply")
    expect(page.locator("#status")).to_have_text("Changed 2 items.")
    assert [_color(page, u) for u in wps] == ["rgba(255,0,0,1)"] * 2
    assert [_color(page, u) for u in lines] == [before[u] for u in lines]
    # Now a line colour only (Fuchsia exists only for lines).
    _tick(page, wps + lines)
    page.click("#bulk-icon")
    d.locator('.palette[data-row="line"] .swatch-btn[aria-label="Fuchsia"]').click()
    page.click("#bulk-apply")
    assert [_color(page, u) for u in lines] == ["rgba(255,0,255,1)"] * 2
    assert [_color(page, u) for u in wps] == ["rgba(255,0,0,1)"] * 2
    # Both at once, then "Leave as is" undoes a pick before saving.
    _tick(page, wps + lines)
    page.click("#bulk-icon")
    d.locator('.palette[data-row="pin"] .swatch-btn[aria-label="Blue"]').click()
    d.locator('.palette[data-row="line"] .swatch-btn[aria-label="Lime"]').click()
    d.locator('.pop-sec[data-row="line"] .color-reset').click()
    expect(d.locator('.palette[data-row="line"] .swatch-btn[aria-pressed="true"]')).to_have_count(0)
    page.click("#bulk-apply")
    assert [_color(page, u) for u in wps] == ["rgba(8,122,255,1)"] * 2
    assert [_color(page, u) for u in lines] == ["rgba(255,0,255,1)"] * 2
    # The export writes what the list shows.
    zf = _export_zip(page)
    tracks = [n for n in zf.namelist() if n.endswith("_Tracks.gpx") and "Lost_Trail_Pass" in n]
    assert tracks and "<onx:color>rgba(255,0,255,1)</onx:color>" in zf.read(tracks[0]).decode()


def test_waypoints_only_dialog_keeps_one_color_row(loaded: Page):
    page = loaded
    _tick(page, _items_of(page, "waypoints"))
    page.click("#bulk-icon")
    d = page.locator("#mark-dialog")
    expect(d).to_have_attribute("aria-label", "Change icon and color for 2 items")
    expect(d.locator(".sec-row > .label")).to_have_text(["Color", "Icon"])
    expect(d.locator(".swatch-btn")).to_have_count(10)
    expect(d.locator(".tog, .fill-sec")).to_have_count(0)


# --- Round 5: design QA ------------------------------------------------------

LONGNAME = "Z" * 140


def _long_name_map(tmp_path) -> str:
    from tests.hardening_maps import _folder, _line, _pt
    feats = [_folder("f0", "Stuff"), _pt(1, "f0", title=LONGNAME), _pt(2, "f0", title="Short"),
             _line(3, "f0"), _line(4, "f0")]
    feats[3]["properties"]["title"] = LONGNAME
    f = tmp_path / "long.json"
    f.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return str(f)


def test_long_names_are_cut_with_an_ellipsis_in_rows_and_the_dialog(fresh_page: Page, tmp_path):
    page = fresh_page
    _wide(page)
    page.set_input_files("#file", _long_name_map(tmp_path))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    name = page.locator(f'{ROW} .name-in[value="{LONGNAME}"]').first
    assert name.evaluate("e => getComputedStyle(e).textOverflow") == "ellipsis"
    assert name.evaluate("e => e.scrollWidth > e.clientWidth")
    _set_type(page, "tracks")
    page.locator(f"{ROW} .sel-box").nth(0).check()
    page.locator(f"{ROW} .sel-box").nth(1).check()
    page.click("#bulk-icon")
    lr = page.locator("#mark-dialog .na-name")
    assert lr.count() == 2
    long_one = page.locator(f'#mark-dialog .na-name[title="{LONGNAME}"]')
    assert long_one.evaluate("e => e.scrollWidth > e.clientWidth && getComputedStyle(e).textOverflow === 'ellipsis'")
    assert page.locator("#mark-dialog .na-rows").evaluate("e => e.scrollWidth <= e.clientWidth")


def test_the_caution_slot_keeps_every_notes_text_in_line(fresh_page: Page, tmp_path):
    page = fresh_page
    _wide(page)
    f = tmp_path / "c.json"
    from tests.hardening_maps import _folder, _pt
    feats = [_folder("f0", "S"), _pt(1, "f0", desc="x" * 600), _pt(2, "f0", desc="short")]
    f.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    assert page.locator(".caution").count() == 1
    xs = page.locator(f"{ROW} .note-text").evaluate_all("els => els.map(e => Math.round(e.getBoundingClientRect().x))")
    assert len(xs) == 2 and xs[0] == xs[1]


def test_a_tall_note_tip_ends_on_a_whole_line_and_says_there_is_more(loaded: Page):
    page = loaded
    _wide(page)
    uid = _first_row(page, "Lost Trail Pass").get_attribute("data-uid")
    _set(page, uid, desc="\n".join(f"Line {i}: lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem" for i in range(40)))
    note = page.locator(f'tr[data-uid="{uid}"] .note-btn')
    note.hover()
    expect(_tip(page)).to_be_visible()
    expect(_tip(page)).to_have_class(re.compile(r"\bscrolls\b"))
    left = _tip(page).evaluate("""e => { const lh = parseFloat(getComputedStyle(e).lineHeight);
        const n = (e.clientHeight - 16) / lh; return Math.abs(n - Math.round(n)) * lh }""")
    assert left < 1
    assert _tip(page).evaluate("e => getComputedStyle(e, '::after').content").endswith('scroll for more"')
    # A short one has no hint.
    _set(page, uid, desc="a\nb")
    page.mouse.move(0, 0)
    expect(_tip(page)).to_be_hidden()
    page.locator(f'tr[data-uid="{uid}"] .note-btn').hover()
    expect(_tip(page)).to_be_visible()
    assert "scrolls" not in (_tip(page).get_attribute("class") or "")


def test_rail_counts_share_one_right_edge_even_for_an_empty_folder(fresh_page: Page, tmp_path):
    from tests.hardening_maps import make_map
    page = fresh_page
    _wide(page)
    f = tmp_path / "e.json"
    f.write_text(make_map(3, seed=2, empty=1, names=["Empty one", "B", "C"]))
    page.set_input_files("#file", str(f))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    edges = page.locator("#folder-facets .facet-count, #type-filter .facet-count").evaluate_all(
        "els => els.filter(e => e.textContent && e.offsetWidth).map(e => Math.round(e.getBoundingClientRect().right))")
    assert len(edges) >= 6 and len(set(edges)) == 1, edges
    assert page.locator("#folder-facets .facet-row.empty").count() == 1


def test_the_rails_last_row_clears_the_footer_when_scrolled_to_the_end(loaded: Page):
    page = loaded
    page.set_viewport_size({"width": 1280, "height": 560})
    page.evaluate("document.querySelector('.rail').scrollTop = 1e6")
    gap = page.evaluate("""document.querySelector('.rail-foot').getBoundingClientRect().top
        - [...document.querySelectorAll('#icon-facets .icon-facet')].pop().getBoundingClientRect().bottom""")
    assert gap >= 8, gap
    # Keyboard focus on the last icon filter scrolls it clear of the footer too.
    page.evaluate("document.querySelector('.rail').scrollTop = 0")
    page.locator("#icon-facets .icon-facet input").last.focus()
    gap = page.evaluate("""document.querySelector('.rail-foot').getBoundingClientRect().top
        - [...document.querySelectorAll('#icon-facets .icon-facet')].pop().getBoundingClientRect().bottom""")
    assert gap >= 0, gap


def test_folders_are_in_name_order_in_the_list_and_the_rail_with_unorganized_last(fresh_page: Page):
    """Owner feedback 2026-10-24: folders by name, natural and any case
    ("1 - …" before "2 - …" and "10 - …"), the same in the list, the rail and
    the export's numbers; the loose items last; a new or renamed folder takes
    its sorted place."""
    page = _dark_divide(fresh_page)
    _wide(page)
    names = ["1 - Course GPX Dark Divide 100 Miler", AID, "3 - Course Segments Dark Divide 100 Miler"]
    expect(page.locator(".folder h2")).to_have_text(names)
    expect(page.locator("#folder-facets .facet-btn .facet-name")).to_have_text(["All", *names])
    _shot(page, "fb-6a-dark-divide-folders-in-order")
    assert [e["folder"] for e in (_export_zip(page), page.evaluate("MANIFEST"))[1]] == names
    page.click("#back")
    # A new folder named "10 - Finish" goes after "3 - …"; renamed "0 - Start", first.
    page.locator("#folder-facets .new-folder").click()
    page.keyboard.type("10 - Finish")
    page.keyboard.press("Enter")
    expect(page.locator("#folder-facets .facet-btn .facet-name")).to_have_text(["All", *names, "10 - Finish"])
    _layout(page)
    _section(page, AID).locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("0 - Start")
    page.keyboard.press("Enter")
    expect(page.locator(".folder h2").first).to_have_text("0 - Start")
    _layout(page)


def test_bitterroots_folders_by_name_with_unorganized_last(loaded: Page):
    page = loaded
    _wide(page)
    order = ["Blodgett", "Central roots", "Lost Horse Canyon", "Lost Trail Pass", "Mill Creek Canyon",
             "North Roots", "Paddling", "Sheafman ridge", "Trapper area", "Unorganized"]
    assert [n for n, _ in _layout(page)] == order
    expect(page.locator("#folders .folder-name")).to_have_text(order)
    _shot(page, "fb-6b-bitterroots-folders-in-order")


def test_the_note_header_lines_up_with_the_note_text_with_or_without_a_caution(loaded: Page):
    """Owner feedback 2026-10-24: the NOTE header's text starts where every
    row's note text starts, with a caution mark, without one, and excluded."""
    page = loaded
    _wide(page)
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    uids = [rows.nth(k).get_attribute("data-uid") for k in range(3)]
    _set(page, uids[0], desc="x" * 600)        # a caution mark
    _set(page, uids[2], included=False)        # excluded: no mark, same slot
    expect(_caution(page, uids[0])).to_have_count(1)
    lefts = page.evaluate("""uids => {
      const sec = document.querySelector(`tr[data-uid="${uids[0]}"]`).closest('section');
      const head = sec.querySelector('th.note-th span').getBoundingClientRect().left;
      return [head, ...uids.map(u => document.querySelector(`tr[data-uid="${u}"] .note-text`).getBoundingClientRect().left)];
    }""", uids)
    head, *notes = lefts
    for x in notes:
        assert abs(x - head) <= 1, lefts
    _section(page, "Lost Trail Pass").evaluate("e => e.scrollIntoView()")
    _shot(page, "fb-4-note-header-aligned")


def test_the_sort_button_keeps_no_pill_once_the_pointer_has_left(loaded: Page):
    page = loaded
    _wide(page)
    btn = page.locator(".sort-btn").first
    btn.click()
    page.mouse.move(5, 5)
    page.wait_for_timeout(150)
    bg = page.evaluate("""() => [...document.querySelectorAll('.sort-btn')].map(b => getComputedStyle(b).backgroundColor)""")
    assert set(bg) == {"rgba(0, 0, 0, 0)"}, bg
    btn.hover()
    assert btn.evaluate("e => getComputedStyle(e).backgroundColor") != "rgba(0, 0, 0, 0)"


def test_icon_color_dialog_caps_its_now_after_list(loaded: Page):
    page = loaded
    _wide(page)
    boxes = page.locator(f"{ROW} .sel-box")
    for i in range(10):
        boxes.nth(i).check()
    page.click("#bulk-icon")
    na = page.locator("#mark-dialog .na-rows")
    assert na.evaluate("e => e.clientHeight") <= 120
    assert na.evaluate("e => e.scrollHeight > e.clientHeight")


def test_a_pasted_folder_name_over_100_characters_says_it_was_cut(loaded: Page):
    page = loaded
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    # A paste whose text only the paste event carries (beforeinput has none).
    page.evaluate("""() => { const i = document.querySelector('.folder-head .folder-name-in');
        const dt = new DataTransfer(); dt.setData('text/plain', 'y'.repeat(150));
        i.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""")
    expect(page.locator("#status")).to_have_text("A folder name can be up to 100 characters.")
    # And a real paste, through the clipboard.
    page.evaluate("document.querySelector('.folder-head .folder-name-in').select()")
    page.evaluate("setStatus('')")
    page.keyboard.insert_text("z" * 150)
    expect(page.locator(".folder-head .folder-name-in")).to_have_value("z" * 100)
    expect(page.locator("#status")).to_have_text("A folder name can be up to 100 characters.")


def test_esc_on_a_just_made_empty_folder_takes_it_back(loaded: Page):
    page = loaded
    before = _layout(page)
    page.locator("#folder-facets .new-folder").click()
    assert len(_layout(page)) == len(before) + 1
    page.keyboard.press("Escape")
    assert _layout(page) == before
    expect(page.locator("#folder-facets .folder-name-in")).to_have_count(0)
    # Named and kept (Enter) stays; and Esc once rows are in keeps the default name.
    page.locator("#folder-facets .new-folder").click()
    page.keyboard.type("Keep me")
    page.keyboard.press("Enter")
    assert len(_layout(page)) == len(before) + 1
    uid = _first_row(page, "Lost Trail Pass").get_attribute("data-uid")
    page.evaluate("([u]) => moveTo([u], NEW_TARGET)", [uid])
    page.keyboard.press("Escape")
    lay = _layout(page)
    assert len(lay) == len(before) + 2 and ("New folder", 1) in lay


def test_the_header_rename_box_fills_the_header_and_esc_leaves_a_tight_ring(loaded: Page):
    page = loaded
    _wide(page)
    sec = _section(page, "Paddling")
    sec.locator(".folder-name").click()
    inp = page.locator(".folder-name-in")
    editing = page.locator(".folder-head:has(.folder-name-in)")
    head = editing.bounding_box()
    sub = editing.locator(".folder-sub").bounding_box()
    box = inp.bounding_box()
    assert box["x"] + box["width"] >= sub["x"] - 24, (box, sub)     # runs up to the item count
    assert box["width"] > head["width"] * 0.6
    page.keyboard.press("Escape")
    btn = _section(page, "Paddling").locator(".folder-name")
    expect(btn).to_be_focused()
    assert btn.bounding_box()["width"] < 200                         # the name, not the whole header
    assert btn.evaluate("e => getComputedStyle(e).outlineOffset") == "0px"


def test_the_merge_dialog_wraps_long_unbroken_names(loaded: Page):
    page = loaded
    _wide(page)
    big = "W" * 90
    _section(page, "Paddling").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text(big)
    page.keyboard.press("Enter")
    _section(page, "North Roots").locator(".folder-name").click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text(big)
    page.keyboard.press("Enter")
    card = page.locator("#confirm .confirm-card")
    expect(card).to_be_visible()
    assert card.evaluate("e => e.scrollWidth <= e.clientWidth")
    assert page.locator("#confirm-body").evaluate("e => e.scrollWidth <= e.clientWidth")
    assert page.locator("#confirm-title").evaluate("e => e.scrollWidth <= e.clientWidth")


def test_a_pointer_drag_move_stays_announced_in_the_status_line(loaded: Page):
    """C6: the status (role=status) says "Moved N items to …" and keeps saying it."""
    page = loaded
    _wide(page)
    st = page.locator("#status")
    assert st.get_attribute("role") == "status"
    _drag(page, _first_row(page, "Lost Trail Pass").locator(".note-btn"), _rail(page, "North Roots"))
    expect(st).to_have_text("Moved 1 item to North Roots.")
    for ms in (300, 400, 1500):
        page.wait_for_timeout(ms)
        assert st.text_content() == "Moved 1 item to North Roots."
    assert st.is_visible()
    # Several rows at once, and the multi-row ghost path.
    rows = _section(page, "Lost Trail Pass").locator("tbody tr")
    for i in (0, 1):
        rows.nth(i).locator(".sel-box").check()
    _drag(page, rows.nth(0).locator(".note-btn"), _rail(page, "North Roots"))
    expect(st).to_have_text("Moved 2 items to North Roots.")
    page.wait_for_timeout(700)
    assert st.text_content() == "Moved 2 items to North Roots."


# --- Owner feedback 2026-10-24: Fill row, one row per palette, one dialog (UI-36) ----


def _one_row(loc) -> bool:
    """Every swatch of every palette in `loc` sits on one line."""
    return loc.evaluate("""el => [...el.querySelectorAll('.palette')].every(p =>
        new Set([...p.children].map(c => Math.round(c.getBoundingClientRect().top))).size <= 1)""")


def test_picking_onxs_blue_fill_clears_the_area_caution_and_exports_it(fresh_page: Page):
    page = fresh_page
    _wide(page)
    fx = FX_DIR / "onx_exports"
    page.set_input_files("#file", [str(fx / "areas-after-edit.gpx"), str(fx / "areas-after-edit.kml")])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    _keep_fills(page)
    blue = page.evaluate("ONX_DEFAULT_FILL")
    assert blue == "rgba(74,144,226,0.1)"
    n0 = page.evaluate("fillLossItems().length")
    row = page.locator(ROW).first
    uid = row.get_attribute("data-uid")
    expect(row.locator(".fill-caution")).to_have_count(1)
    row.locator(".line-btn").click()
    pop = page.locator("#mark-pop")
    expect(pop.locator(".sec-row .label")).to_have_text(["Color", "Style", "Weight", "Fill"])
    expect(pop.locator(".fill-reset")).to_have_text("Leave as is")
    expect(pop.locator(".fill-reset")).to_have_attribute("aria-pressed", "true")
    expect(pop.locator(".swatch-btn")).to_have_count(11)
    assert _one_row(pop)
    _shot(page, "fb-9a-single-area-popover")
    pop.locator(".fill-btn").click()
    expect(pop.locator(".fill-btn")).to_have_attribute("aria-pressed", "true")
    expect(pop.locator(".fill-reset")).to_have_attribute("aria-pressed", "false")
    _shot(page, "fb-9b-single-area-blue-fill-picked")
    page.click("#pop-apply")
    assert page.evaluate(f"allItems().find(i => i.uid === {uid!r}).fill") == blue
    expect(row.locator(".fill-caution")).to_have_count(0)
    assert page.evaluate("fillLossItems().length") == n0 - 1
    assert page.evaluate("unexportedChanges()") >= 1
    # Several areas through the dialog: the rest go blue too, every mark is gone.
    rows = page.locator(ROW)
    for k in range(rows.count()):
        rows.nth(k).locator(".sel-box").check()
    page.click("#bulk-icon")
    d = page.locator("#mark-dialog")
    expect(d.locator(".sec-row .label")).to_have_text(["Color", "Style", "Weight", "Fill"])
    assert _one_row(d)
    _shot(page, "fb-9c-several-areas-dialog")
    d.locator(".fill-btn").click()
    page.click("#bulk-apply")
    expect(page.locator(".fill-caution")).to_have_count(0)
    assert page.evaluate("fillLossItems().length") == 0
    zf = _export_zip(page)
    gpx = "".join(zf.read(n).decode() for n in zf.namelist() if n.endswith("_Areas.gpx"))
    fills = re.findall(r"<onx:fill_color>(.*?)</onx:fill_color>", gpx)
    assert fills and set(fills) == {blue}


def test_leave_as_is_leaves_the_fill_alone(fresh_page: Page):
    page = fresh_page
    fx = FX_DIR / "onx_exports"
    page.set_input_files("#file", [str(fx / "areas-after-edit.gpx"), str(fx / "areas-after-edit.kml")])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    _keep_fills(page)
    before = page.evaluate("allItems().map(i => i.fill)")
    row = page.locator(ROW).first
    row.locator(".line-btn").click()
    pop = page.locator("#mark-pop")
    pop.locator(".fill-btn").click()
    pop.locator(".fill-reset").click()
    page.click("#pop-apply")
    assert page.evaluate("allItems().map(i => i.fill)") == before


def test_one_dialog_for_lines_and_areas_and_for_waypoints_and_areas(loaded: Page):
    """UI-36: lines + areas, and waypoints + areas, each get ONE dialog in the
    popover's row shape; every row starts on "Leave as is" and every palette
    is one line at 1440x900."""
    page = loaded
    _wide(page)
    lines, areas = _items_of(page, "tracks"), _items_of(page, "shapes")
    _tick(page, lines + areas)
    expect(page.locator("#bulk-icon")).to_have_text("Color & style…")
    page.click("#bulk-icon")
    d = page.locator("#mark-dialog")
    expect(d.locator(".sec-row .label")).to_have_text(["Color", "Style", "Weight", "Fill"])
    expect(d.locator(".reset-chip")).to_have_text(["Leave as is"] * 4)
    expect(d.locator('.reset-chip[aria-pressed="true"]')).to_have_count(4)
    assert _one_row(d)
    _shot(page, "fb-11a-lines-and-areas-dialog")
    d.locator('.tog[data-weight="6.0"]').click()
    page.click("#bulk-apply")
    expect(page.locator("#status")).to_have_text(re.compile(r"^Changed [1-4] items\.$"))  # only those not thick already
    assert {page.evaluate(_LINE.format(uid=u))["weight"] for u in lines + areas} == {"6.0"}
    _clear_selection(page)
    wps = _items_of(page, "waypoints")
    _tick(page, wps + areas)
    expect(page.locator("#bulk-icon")).to_have_text("Icon & color…")
    page.click("#bulk-icon")
    expect(d.locator(".sec-row .label")).to_have_text(
        ["Waypoint color", "Icon", "Line color", "Style", "Weight", "Fill"])
    expect(d.locator(".reset-chip")).to_have_text(["Leave as is"] * 6)
    assert _one_row(d)
    _shot(page, "fb-11b-waypoints-and-areas-dialog")
    d.locator('.pop-sec[data-row="line"] .swatch-btn[aria-label="Fuchsia"]').click()
    d.locator('.tog[data-style="dash"]').click()
    page.click("#bulk-apply")
    assert [page.evaluate(_LINE.format(uid=u))["style"] for u in areas] == ["dash"] * len(areas)
    assert [_color(page, u) for u in areas] == ["rgba(255,0,255,1)"] * len(areas)
    assert all(_color(page, u) != "rgba(255,0,255,1)" for u in wps)


def test_every_palette_is_one_line_in_the_popovers_and_dialogs(loaded: Page):
    """Owner feedback 2026-10-24: "Leave as is" moved to the label line, so the
    11 line colours (Fuchsia last) no longer wrap; same in every row."""
    page = loaded
    _wide(page)
    for kind in ("waypoints", "tracks", "shapes"):
        _set_type(page, kind)
        page.locator(f"{ROW} .icon-btn, {ROW} .line-btn").first.click()
        pop = page.locator("#mark-pop")
        expect(pop).to_be_visible()
        assert _one_row(pop), kind
        if kind == "tracks":
            _shot(page, "fb-10a-line-popover-one-row")
        page.click("#mark-pop .pop-cancel")
    _set_type(page, "")
    _tick(page, _items_of(page, "waypoints") + _items_of(page, "tracks"))
    page.click("#bulk-icon")
    d = page.locator("#mark-dialog")
    assert _one_row(d)
    fuchsia = d.locator('.pop-sec[data-row="line"] .swatch-btn').last
    expect(fuchsia).to_have_attribute("aria-label", "Fuchsia")
    _shot(page, "fb-10b-waypoints-and-lines-dialog")
    # "Leave as is" is the one wording for "no change", everywhere it appears.
    assert set(d.locator(".reset-chip").all_inner_texts()) == {"Leave as is"}


# --- UI-37: browser Back and Forward, and the leave-site prompt (2026-10-24) ---------


def _stage(page: Page) -> str:
    return page.get_attribute("body", "data-stage")


def _rename_first_row(page: Page, name: str = "Renamed here") -> None:
    box = page.locator(f"{ROW} .name-in").first
    box.click()
    box.fill(name)
    box.press("Enter")
    expect(page.locator(f"{ROW} .name-in").first).to_have_value(name)


def test_back_from_edit_with_no_changes_goes_to_drop_and_forward_does_nothing(loaded: Page):
    page = loaded
    assert _stage(page) == "edit"
    page.go_back()
    expect(page.locator("body")).to_have_attribute("data-stage", "drop")
    expect(page.locator("#confirm")).to_be_hidden()
    assert page.evaluate("DATA === null")
    # The map is gone, so Forward has no edit screen to go to.
    page.go_forward()
    page.wait_for_timeout(300)
    assert _stage(page) == "drop"
    expect(page.locator("#confirm")).to_be_hidden()


def test_back_from_edit_with_changes_asks_stay_or_leave(loaded: Page):
    page = loaded
    _wide(page)
    _rename_first_row(page)
    assert page.evaluate("unexportedChanges()") == 1
    page.go_back()
    c = page.locator("#confirm")
    expect(c).to_be_visible()
    expect(page.locator("#confirm-title")).to_have_text("Leave this map?")
    expect(page.locator("#confirm-body")).to_have_text("Changes will be lost.")
    expect(page.locator("#confirm-actions button")).to_have_text(["Stay", "Leave"])
    expect(page.locator("#confirm-actions button", has_text="Stay")).to_be_focused()   # the default
    _shot(page, "fb-14-leave-this-map")
    # Esc is Stay: still on the map, the change kept, and Back asks again.
    page.keyboard.press("Escape")
    expect(c).to_be_hidden()
    assert _stage(page) == "edit" and page.evaluate("unexportedChanges()") == 1
    page.wait_for_timeout(200)
    page.go_back()
    expect(c).to_be_visible()
    page.click("#confirm-actions button:text-is('Stay')")
    expect(c).to_be_hidden()
    assert _stage(page) == "edit"
    expect(page.locator(f"{ROW} .name-in").first).to_have_value("Renamed here")
    page.wait_for_timeout(200)
    # Leave: the drop screen, the map cleared as by Start over.
    page.go_back()
    page.click("#confirm-actions button:text-is('Leave')")
    expect(page.locator("body")).to_have_attribute("data-stage", "drop")
    assert page.evaluate("DATA === null && Object.keys(EDITS).length === 0")
    page.go_forward()
    page.wait_for_timeout(300)
    assert _stage(page) == "drop"


def test_back_from_done_returns_to_edit_and_forward_to_a_current_export(loaded: Page):
    page = loaded
    _rename_first_row(page)
    _done(page)
    page.go_back()
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")
    expect(page.locator("#confirm")).to_be_hidden()
    expect(page.locator(f"{ROW} .name-in").first).to_have_value("Renamed here")   # nothing lost
    page.go_forward()
    expect(page.locator("body")).to_have_attribute("data-stage", "done")
    # The app's Back button and the browser's agree.
    page.click("#back")
    assert _stage(page) == "edit"
    page.go_forward()
    expect(page.locator("body")).to_have_attribute("data-stage", "done")
    page.go_back()
    expect(page.locator("body")).to_have_attribute("data-stage", "edit")
    # A change since the export: that export is stale, Forward stays on the map.
    _rename_first_row(page, "Changed again")
    page.go_forward()
    page.wait_for_timeout(300)
    assert _stage(page) == "edit"
    # Back from the map now asks (one unexported change).
    page.go_back()
    expect(page.locator("#confirm-title")).to_have_text("Leave this map?")
    page.click("#confirm-actions button:text-is('Stay')")
    assert _stage(page) == "edit"


def test_back_from_drop_after_start_over_leaves_the_site(loaded: Page):
    page = loaded
    _done(page)
    page.locator("#done-stage .newmap").click()
    page.click("#confirm .confirm-actions button:text-is('Start over')")
    expect(page.locator("body")).to_have_attribute("data-stage", "drop")
    page.wait_for_timeout(300)
    page.go_back()
    page.wait_for_load_state()
    assert "index.html" not in page.url, page.url


def test_the_browser_prompts_before_unload_only_with_unexported_changes(context):
    def open_loaded():
        page = context.new_page()
        page.goto(f"{BASE_URL}/index.html")
        page.wait_for_function("window.__cairnReady === true", timeout=60000)
        page.set_input_files("#file", str(FIXTURE))
        page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
        return page

    page = open_loaded()
    seen = []
    page.on("dialog", lambda d: (seen.append(d.type), d.dismiss()))
    page.locator(f"{ROW} .sel-box").first.click()           # a gesture, but no change
    with page.expect_event("close", timeout=5000):
        page.close(run_before_unload=True)
    assert seen == [] and page.is_closed()

    page = open_loaded()
    seen = []
    page.on("dialog", lambda d: (seen.append(d.type), d.dismiss()))
    _rename_first_row(page)
    page.close(run_before_unload=True)
    page.wait_for_timeout(500)
    assert seen == ["beforeunload"]
    assert not page.is_closed()                              # dismissed: the tab stays
    # Exported: no more prompt.
    _done(page)
    seen.clear()
    with page.expect_event("close", timeout=5000):
        page.close(run_before_unload=True)
    assert seen == [] and page.is_closed()


# ---------------------------------------------------------------------------
# Walkthrough sample files (web/samples/): served by the site, and they load
# ---------------------------------------------------------------------------

SAMPLES = ["Bitterroots.json", "Bitterroots.gpx", "Bitterroots.kml"]


def test_walkthrough_sample_links_are_served_downloads():
    import re as _re
    import urllib.request
    page = urllib.request.urlopen(f"{BASE_URL}/walkthrough.html", timeout=10).read().decode()
    links = _re.findall(r'<a href="(samples/[^"]+)" download>', page)
    assert sorted(links) == sorted(f"samples/{n}" for n in SAMPLES)
    assert 'href="https://caltopo.com/m/1KLNT" target="_blank" rel="noopener noreferrer">Bitterroots<' in page
    # the footnote: a superscript link to it, its two source links, a back-link
    assert 'href="#fn-map"' in page and 'id="fn-map"' in page and 'href="#fnref-map"' in page
    for url in ("https://mt-adventures.blogspot.com/", "https://www.tenpeaksbeforelunch.com/"):
        assert f'href="{url}" target="_blank" rel="noopener noreferrer"' in page
    assert "Nate Bender" not in page and "never leaves" not in page and "177 markups" not in page
    for link in links:
        with urllib.request.urlopen(f"{BASE_URL}/{link}", timeout=10) as r:
            assert r.status == 200 and len(r.read()) > 100_000, link


@pytest.mark.parametrize("name", SAMPLES)
def test_walkthrough_sample_loads_in_cairn(fresh_page: Page, name: str):
    fresh_page.set_input_files("#file", str(Path(__file__).resolve().parents[2] / "web" / "samples" / name))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=60000)
    expect(fresh_page.locator("#status")).not_to_have_class(re.compile(r"\berr\b"))
    totals = fresh_page.evaluate("DATA.totals")
    print(name, totals)
    assert totals["items"] == 177, totals  # what the walkthrough says


@pytest.mark.parametrize("path", ["index.html", "faq.html", "walkthrough.html"])
def test_top_bar_is_sticky_and_anchors_clear_it(context, path):
    """Owner feedback 2026-10-24: the top bar stays put while the page scrolls
    (solid paper, bottom rule), and in-page anchors land below it."""
    page = context.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{BASE_URL}/{path}")
    bar = page.locator("header.topbar")
    st = bar.evaluate("e => { const c = getComputedStyle(e); return {p: c.position, t: c.top, bg: c.backgroundColor, b: c.borderBottomWidth}; }")
    paper = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert st["p"] == "sticky" and st["t"] == "0px" and st["bg"] == paper and st["b"] == "1px", st
    if path != "index.html":
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        assert bar.evaluate("e => e.getBoundingClientRect().top") == 0
        _shot(page, f"sticky-{path.split('.')[0]}-mid")
        target = "#fn-map" if path == "walkthrough.html" else page.locator(".doc-toc a").nth(3).get_attribute("href")
        page.evaluate("t => { location.hash = t }", target)
        page.wait_for_timeout(200)
        top = page.evaluate("t => document.querySelector(t).getBoundingClientRect().top", target)
        height = bar.evaluate("e => e.getBoundingClientRect().height")
        assert top >= height, (top, height)
    page.close()


def test_edit_search_row_and_export_top_bar_stay_put_on_scroll(loaded: Page):
    """Owner feedback 2026-10-24: the edit stage's search row (it carries the
    site nav) sticks to the top while the rows scroll, and the selection bar
    sits just under it; the export stage's top bar is sticky too."""
    page = loaded
    _wide(page)
    page.evaluate("window.scrollTo(0, 600)")
    bar = page.locator(".toolbar")
    box = bar.bounding_box()
    assert box["y"] == 0, box
    assert bar.evaluate("e => getComputedStyle(e).backgroundColor") == page.evaluate("getComputedStyle(document.body).backgroundColor")
    page.locator("tbody tr input[type=checkbox]").first.check()
    sel = page.locator(".selbar").bounding_box()
    assert sel["y"] >= box["height"] - 1, (sel, box)
    _shot(page, "sticky-edit-stage")
    _done(page)
    assert page.locator("#topbar").evaluate("e => getComputedStyle(e).position") == "sticky"
    page.evaluate("window.scrollTo(0, 300)")
    assert page.locator("#topbar").bounding_box()["y"] == 0
    _shot(page, "sticky-export-stage")


# --- Keyed in-place rendering (FOLDERS_RELEASE follow-up) --------------------
# A re-render updates the rows, folder sections and rail entries that are still
# there instead of replacing them: the node under the pointer and the focus
# survives an edit, a move, a rename, a sort or a filter. Each test marks live
# nodes with a JS property (it would not survive a rebuild) and checks that the
# same nodes are on screen afterwards.

def _mark(loc, tag: str = "keep") -> None:
    loc.evaluate("(e, t) => { e.__cairnMark = t; }", tag)




def test_filter_keystrokes_keep_the_rows_and_sections_still_shown(loaded: Page):
    page = loaded
    row = _first_row(page, "North Roots")
    uid = row.get_attribute("data-uid")
    name = row.locator(".name-in").input_value()
    _mark(row)
    _mark(_section(page, "North Roots"))
    _mark(_rail(page, "North Roots"))
    page.locator("#filter").click()
    page.keyboard.type(name[:4])
    row = page.locator(f'tr[data-uid="{uid}"]')
    expect(row).to_have_count(1)
    assert _is_marked(row)
    assert _is_marked(_section(page, "North Roots"))
    assert _is_marked(_rail(page, "North Roots"))
    expect(page.locator("#filter")).to_be_focused()
    # And back: the rows that were hidden come back, the marked one is still it.
    for _ in range(4):
        page.keyboard.press("Backspace")
    expect(page.locator(ROW)).to_have_count(177)
    assert _is_marked(page.locator(f'tr[data-uid="{uid}"]'))


def test_enter_in_a_row_name_keeps_the_same_field_row_and_rail(loaded: Page):
    page = loaded
    row = _first_row(page, "Paddling")
    uid = row.get_attribute("data-uid")
    field = row.locator(".name-in")
    for loc in (row, field, row.locator(".icon-btn, .line-btn"),
                _section(page, "Paddling"), _rail(page, "Paddling"), page.locator(".new-folder")):
        _mark(loc)
    field.click()
    field.evaluate("e => e.setSelectionRange(e.value.length, e.value.length)")
    page.keyboard.type(" renamed")
    page.keyboard.press("Enter")
    row = page.locator(f'tr[data-uid="{uid}"]')
    field = row.locator(".name-in")
    expect(field).to_be_focused()
    assert field.input_value().endswith(" renamed")
    for loc in (row, field, row.locator(".icon-btn, .line-btn"),
                _section(page, "Paddling"), _rail(page, "Paddling"), page.locator(".new-folder")):
        assert _is_marked(loc)
    # The aria-labels that carry the name follow it.
    expect(row.locator(".sel-box")).to_have_attribute("aria-label", "Select " + field.input_value())


def test_a_rename_that_reorders_a_sorted_folder_keeps_the_row_and_focus(loaded: Page):
    page = loaded
    sec = _section(page, "North Roots")
    sec.locator(".sort-btn").click()                    # A to Z
    expect(sec.locator(".sort-btn")).to_have_attribute("data-sort", "asc")
    row = sec.locator("tbody tr").first
    uid = row.get_attribute("data-uid")
    _mark(row)
    field = row.locator(".name-in")
    field.click()
    field.fill("zzzz last now")
    page.keyboard.press("Enter")
    row = page.locator(f'tr[data-uid="{uid}"]')
    expect(sec.locator("tbody tr").last).to_have_attribute("data-uid", uid)
    assert _is_marked(row)
    expect(row.locator(".name-in")).to_be_focused()


def test_sort_and_collapse_keep_the_section_its_rows_and_the_button(loaded: Page):
    page = loaded
    sec = _section(page, "North Roots")
    rows = sec.locator("tbody tr")
    uids = rows.evaluate_all("rs => rs.map(r => r.dataset.uid)")
    rows.evaluate_all("rs => rs.forEach(r => { r.__cairnMark = 'keep'; })")
    _mark(sec)
    sec.locator(".sort-btn").click()
    expect(sec.locator(".sort-btn")).to_be_focused()
    assert rows.evaluate_all("rs => rs.every(r => r.__cairnMark === 'keep')")
    assert sorted(rows.evaluate_all("rs => rs.map(r => r.dataset.uid)")) == sorted(uids)
    sec.locator(".collapse").click()
    expect(sec.locator(".table-wrap")).to_be_hidden()
    expect(sec.locator(".collapse")).to_be_focused()
    assert _is_marked(sec)


def test_a_header_rename_keeps_the_section_its_rows_and_the_rail(loaded: Page):
    page = loaded
    sec = _section(page, "North Roots")
    row = sec.locator("tbody tr").first
    uid = row.get_attribute("data-uid")
    _mark(sec)
    _mark(row)
    _mark(_rail(page, "North Roots"))
    _mark(_rail(page, "Paddling"))
    sec.locator(".folder-name").click()
    page.keyboard.type("High Roots")
    page.keyboard.press("Enter")
    sec = _section(page, "High Roots")
    expect(sec).to_have_count(1)
    assert _is_marked(sec)
    assert _is_marked(sec.locator(f'tr[data-uid="{uid}"]'))
    assert _is_marked(_rail(page, "High Roots"))
    assert _is_marked(_rail(page, "Paddling"))
    expect(sec.locator(".folder-name")).to_be_focused()
    expect(sec).to_have_attribute("aria-label", "High Roots")


def test_a_moved_row_is_the_same_node_in_its_new_folder(loaded: Page):
    page = loaded
    row = _first_row(page, "Lost Trail Pass")
    uid = row.get_attribute("data-uid")
    _mark(row)
    _mark(_rail(page, "North Roots"))
    _drag(page, row.locator(".note-btn"), _rail(page, "North Roots"))
    expect(page.locator("#status")).to_have_text("Moved 1 item to North Roots.")
    moved = _section(page, "North Roots").locator(f'tr[data-uid="{uid}"]')
    expect(moved).to_have_count(1)
    assert _is_marked(moved)
    assert _is_marked(_rail(page, "North Roots"))


def test_popover_and_note_edits_keep_the_row_and_its_controls(loaded: Page):
    page = loaded
    row = page.locator(ROW, has=page.locator(".icon-btn")).first
    uid = row.get_attribute("data-uid")
    mark = row.locator(".icon-btn")
    _mark(row)
    _mark(mark)
    mark.click()
    pop = page.locator("#mark-pop")
    expect(pop).to_be_visible()
    pop.locator(".swatch-btn[aria-pressed=false]").first.click()
    pop.locator(".pop-apply").click()
    row = page.locator(f'tr[data-uid="{uid}"]')
    assert _is_marked(row) and _is_marked(row.locator(".icon-btn"))
    expect(row.locator(".icon-btn")).to_be_focused()
    row.locator(".note-btn").click()
    ta = row.locator(".desc-in")
    expect(ta).to_be_focused()
    ta.fill("A new note")
    row.locator(".note-apply").click()
    # The editor's Save is gone with the editor: focus lands on the note button.
    expect(row.locator(".note-btn")).to_be_focused()
    expect(row.locator(".note-text")).to_have_text("A new note")
    assert _is_marked(row) and _is_marked(row.locator(".icon-btn"))


def test_use_note_as_name_leaves_a_blank_note_row_alone(loaded: Page):
    # "Use note as name" on a note of only spaces and line breaks gave the row an
    # empty name, which the name field itself refuses (2026-10-25).
    blank, real = page_uids = loaded.evaluate("allItems().slice(0, 2).map(i => i.uid)")
    before = loaded.evaluate("u => allItems().find(i => i.uid === u).name", blank)
    _set(loaded, blank, desc="   \n  ")
    _set(loaded, real, desc="Real note\nsecond line")
    _tick(loaded, page_uids)
    _menu_action(loaded, "#bulk-desc")
    names = loaded.evaluate("us => us.map(u => allItems().find(i => i.uid === u).name)", page_uids)
    assert names == [before, "Real note second line"]
