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

# BASE_URL is read from the environment so this suite can be pointed at a
# live deployment (e.g. `BASE_URL=https://quietmarch.to/cairn/ pytest ...`)
# as well as the local dev server. When the caller explicitly set BASE_URL,
# an unreachable server is a hard failure, not a skip -- a silent skip
# against a mistyped or down deployment URL would report green for nothing.
_EXPLICIT_BASE_URL = "BASE_URL" in os.environ
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8765").rstrip("/")
FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "bitterroots"
    / "Bitterroots__Complete_.json"
)

# Ground truth for the fixture, established by loading it through the real
# engine (both via the CLI and via this exact app) and reading DATA.totals.
ROW = ".folder tbody tr"  # scoped: the help panel also contains a <table>
EXPECTED_TOTALS = {"folders": 10, "items": 177, "attention": 25}
# attention was 26 until the web app began loading the user's
# cairn_config.yaml explicitly. Without it the browser silently used 144
# built-in symbol mappings while the CLI used 152, so `circle-p` did not
# resolve to Parking and one extra waypoint fell back to the generic pin.
# See web/bridge.py:_config().


def _server_reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/index.html", timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_server():
    """Skip if the local dev server isn't up; fail if an explicit BASE_URL is unreachable.

    A skip is the right call for "you forgot to start the dev server" -- but
    if BASE_URL was set on purpose (pointing at a deployment), an unreachable
    URL must fail the run. Otherwise a mistyped or down URL reports a clean
    green skip, which is worse than no test at all.
    """
    if not _server_reachable():
        if _EXPLICIT_BASE_URL:
            pytest.fail(f"explicit BASE_URL={BASE_URL} is not reachable")
        pytest.skip(
            f"web dev server not reachable at {BASE_URL} "
            "(start it with: uv run python web/serve.py)"
        )


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(scope="session")
def context(browser):
    """A single browser context, reused across tests so the CDN-fetched
    Pyodide/wheel assets stay in the HTTP cache: the first test pays a cold
    boot, every later test's boot is warm (see perf numbers in the report).
    """
    # bypass_csp: the page now ships a strict Content-Security-Policy (see
    # web/vercel.json, mirrored by serve.py) with no 'unsafe-eval'; Playwright's
    # string-evaluating helpers (wait_for_function etc.) are eval-based and
    # would be blocked by it. The CSP itself is verified by
    # test_page_boots_under_enforced_csp, which uses a non-bypassing context.
    ctx = browser.new_context(bypass_csp=True)
    yield ctx
    ctx.close()


@pytest.fixture()
def fresh_page(context) -> Page:
    """A brand-new page/tab, booted but with nothing loaded yet.

    Each test gets its own page (not a shared one reloaded with the same
    file) because Chromium/Playwright does not fire a `change` event on
    `<input type=file>` when `set_input_files` is called twice with the
    identical path -- confirmed by direct repro. A fresh page sidesteps that
    entirely and is also the more realistic "user opens the app" scenario.
    """
    page = context.new_page()
    page.goto(f"{BASE_URL}/index.html")
    page.wait_for_function("window.__cairnReady === true", timeout=60000)
    yield page
    page.close()


@pytest.fixture()
def loaded(fresh_page: Page) -> Page:
    """fresh_page with the real fixture loaded (no edits, no selection)."""
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    return fresh_page


def export_zip_bytes(page: Page, confirm: str | None = None) -> bytes:
    """Trigger export and pull the resulting Blob back into Python as bytes.

    `confirm` names the button to press in the unsaved-note prompt when one is
    expected; without it, a prompt would hang the wait below (as it should).
    """
    page.evaluate("window.__cairnExported = false")
    page.click("#export")
    if confirm:
        page.click(f"#confirm .confirm-actions button:text-is('{confirm}')")
    page.wait_for_function("window.__cairnExported === true", timeout=60000)
    b64 = page.evaluate(
        """
        (async () => {
            const buf = await ZIP.arrayBuffer();
            let binary = '';
            const bytes = new Uint8Array(buf);
            const chunk = 0x8000;
            for (let i = 0; i < bytes.length; i += chunk) {
                binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
            }
            return btoa(binary);
        })()
        """
    )
    return base64.b64decode(b64)


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------


def _select_all_shown(page):
    """Ctrl/Cmd+A is now the select-all-shown control (the checkbox was removed
    when bulk selection moved to per-row checkboxes plus this shortcut).

    Blur first: inside a text field Ctrl+A means select-the-text, and the app
    deliberately ignores it there.
    """
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.keyboard.press("ControlOrMeta+a")
    page.wait_for_timeout(350)


def _clear_selection(page):
    page.evaluate("SEL.clear(); ANCHOR = null; renderFolders()")
    page.wait_for_timeout(250)


def _set_type(page, kind):
    """The type filter is the rail's Type section (All / Waypoints / Lines /
    Areas, UI-28); "" is All."""
    page.click(f'#type-filter [data-kind="{kind}"]')
    page.wait_for_timeout(150)
    assert page.get_attribute(f'#type-filter [data-kind="{kind}"]', "aria-pressed") == "true"


def _menu_action(page, selector):
    """Bulk actions beyond icon/color now live behind the More menu."""
    page.click("#more-btn")
    page.wait_for_timeout(200)
    page.click(selector)
    page.wait_for_timeout(350)


def _export_zip(page):
    """Export in the browser and return the downloaded zip as a ZipFile."""
    import base64, io, zipfile
    page.click("#export")
    page.wait_for_function("window.__cairnExported === true", timeout=180_000)
    b64 = page.evaluate(
        "async () => { const u = new Uint8Array(await ZIP.arrayBuffer());"
        " let s=''; for (let i=0;i<u.length;i++) s += String.fromCharCode(u[i]);"
        " return btoa(s); }"
    )
    return zipfile.ZipFile(io.BytesIO(base64.b64decode(b64)))


def test_no_loading_or_version_text_after_boot(fresh_page: Page):
    body = fresh_page.inner_text("body")
    for text in ("Loading", "Starting", "Ready", "engine v", "Python runtime"):
        assert text not in body, text
    assert fresh_page.text_content("#status").strip() == ""
    assert fresh_page.is_enabled("#pick")


FOOTER_LINKS = ["Help", "FAQ", "Walkthrough", "GitHub"]


@pytest.mark.parametrize("path", ["index.html", "faq.html", "walkthrough.html"])
def test_footer_has_the_four_links_on_every_page(context, path):
    page = context.new_page()
    page.goto(f"{BASE_URL}/{path}")
    foot = page.locator("footer.site-foot")
    expect(foot).to_have_count(1)
    labels = foot.locator("a, button").all_inner_texts()
    assert labels == FOOTER_LINKS
    assert "·" in foot.inner_text()
    assert foot.locator("a[href='https://github.com/moltude/cairn']").count() == 1
    page.close()


def test_footer_help_opens_help_from_the_app(fresh_page: Page):
    expect(fresh_page.locator("#help")).to_be_hidden()
    fresh_page.click("footer.site-foot >> text=Help")
    expect(fresh_page.locator("#help")).to_be_visible()


def test_old_help_links_are_gone_from_the_app_chrome(fresh_page: Page):
    assert fresh_page.locator("#topbar a, #topbar button, .rail-head a, .rail-head button").count() == 0


@pytest.mark.parametrize("path", ["faq.html", "walkthrough.html"])
def test_footer_help_on_doc_pages_links_to_the_app_help(context, path):
    page = context.new_page()
    page.goto(f"{BASE_URL}/{path}")
    assert page.get_attribute("footer.site-foot >> text=Help", "href") == "./#help"
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
    assert "RUNBOOK.md" in names
    # Every member must actually be readable/valid (CRC checks out).
    assert zf.testzip() is None


# ---------------------------------------------------------------------------
# Runbook
# ---------------------------------------------------------------------------


def test_runbook_names_each_folder_and_has_no_kml_warning(loaded: Page):
    zip_bytes = export_zip_bytes(loaded)
    manifest = loaded.evaluate("MANIFEST")
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    runbook = zf.read("RUNBOOK.md").decode()

    for entry in manifest:
        heading = f"### {entry['n']}. {entry['folder']}"
        assert heading in runbook, f"missing runbook heading: {heading!r}"

    # Areas no longer go out as KML (ENG-05), so nothing triggers the
    # Web-Map-only KML warning, in RUNBOOK.md or on screen.
    assert not any(f["kml"] for e in manifest for f in e["files"])
    assert "KML" not in runbook
    assert "KML" not in loaded.locator("#runbook").inner_text()


# ---------------------------------------------------------------------------
# Export screen (UI-31): one box per folder, Download all / this folder
# ---------------------------------------------------------------------------


def _done(page: Page) -> None:
    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)


def test_export_screen_is_one_box_per_folder_with_three_steps(loaded: Page):
    _done(loaded)
    manifest = loaded.evaluate("MANIFEST")
    done = loaded.locator("#done-stage")
    # The tick boxes (which only greyed a row) and the boxed explanation are gone.
    expect(done.locator("input")).to_have_count(0)
    expect(done.locator(".runbook-intro")).to_have_count(0)
    expect(done.get_by_role("button", name="Copy")).to_have_count(0)
    expect(loaded.locator("#download")).to_have_text("Download all")
    expect(done.locator(".done-hint")).to_have_text("One zip, one folder inside it per onX folder")
    expect(done.locator(".rb-intro")).to_have_text(
        "Import each folder into onX's Web Map, one at a time. Importing needs onX Premium or Elite.")
    boxes = done.locator(".rb-step")
    expect(boxes).to_have_count(len(manifest))
    expect(done.locator(".rb-dl")).to_have_text(["Download this folder"] * len(manifest))
    for i, e in enumerate(manifest):
        box, nf = boxes.nth(i), len(e["files"])
        files = f"{nf} file" + ("" if nf == 1 else "s")
        marks = f"{e['count']} markup" + ("" if e["count"] == 1 else "s")
        expect(box.locator("h2")).to_have_text(f"{e['folder']} · {marks} · {files}")
        expect(box.locator(".rb-file")).to_have_text([f["path"].split("/")[-1] for f in e["files"]])
        add = "add this file." if nf == 1 else f"add these {nf} files together."
        expect(box.locator(".rb-do li")).to_have_text([
            f"In onX, choose Import and {add}",
            "Tick Import map data to a new folder.",
            f"onX names the folder by date. Rename it to {e['folder']}.",
        ])
    # Bitterroots has both kinds: Paddling writes one file, Unorganized three.
    assert {len(e["files"]) for e in manifest} >= {1, 3}
    expect(done).not_to_contain_text("Import all")
    expect(done).not_to_contain_text("1 files")


def test_download_all_and_each_folder_download(loaded: Page):
    _done(loaded)
    manifest = loaded.evaluate("MANIFEST")
    with loaded.expect_download() as dl:
        loaded.click("#download")
    assert dl.value.suggested_filename == "onx_ready.zip"
    full = zipfile.ZipFile(dl.value.path())
    # Download all's layout is unchanged: NN_Name/ per folder in screen order, then RUNBOOK.md.
    assert full.namelist() == [f["path"] for e in manifest for f in e["files"]] + ["RUNBOOK.md"]
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
    expect(warns.nth(0)).to_contain_text("1 item could not be exported")
    expect(warns.nth(1)).to_contain_text("1 note is longer than 512 bytes")
    expect(warns.nth(2)).to_contain_text("onX accounts hold at most 3,000 markups; this map has 3,002.")
    # Every warning comes before the first folder box.
    order = host.locator(":scope > *").evaluate_all("els => els.map(e => e.className)")
    assert order[:3] == ["note warn"] * 3 and order[3:] == ["rb-step"]
    expect(host.locator(".rb-step h2")).to_have_text("Big · 3,001 markups · 2 files")


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
    assert it["why"] == "You chose the default pin for this one."
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
    n = len(res["folders"])
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
    # The clipped one-line view shows the newline as a space.
    clipped = loaded.locator(f'tr[data-uid="{uid}"] .note-text').inner_text()
    assert clipped == "first line second line"


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


def test_line_style_dialog_for_several_lines(loaded: Page):
    """Line style… appears only when lines are selected; its dialog is titled
    "Line style", picks apply to every selected line, and a second click on the
    picked toggle un-picks it (each line keeps its own value)."""
    _set_type(loaded, "waypoints")
    loaded.locator(f"{ROW} .sel-box").nth(0).check()
    expect(loaded.locator("#bulk-line")).to_be_hidden()
    _clear_selection(loaded)

    _set_type(loaded, "tracks")
    rows = loaded.locator(ROW)
    uids = [rows.nth(i).get_attribute("data-uid") for i in range(2)]
    for i in range(2):
        rows.nth(i).locator(".sel-box").check()
    expect(loaded.locator("#bulk-line")).to_be_visible()
    before = [loaded.evaluate(_LINE.format(uid=u)) for u in uids]
    loaded.click("#bulk-line")
    d = loaded.locator("#mark-dialog")
    expect(d.locator("h2")).to_have_text("Line style")
    assert d.locator(".line-rows .lr-name").count() == 2
    d.locator('.tog[data-weight="6.0"]').click()
    d.locator('.tog[data-weight="6.0"]').click()          # un-pick: weights stay as they are
    assert d.locator('.tog[aria-pressed="true"]').count() == 0
    d.locator('.tog[data-style="dash"]').click()
    loaded.click("#line-apply")
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
    assert blocks and all("<onx:style>dash</onx:style>" in b and "<onx:weight>6.0</onx:weight>" in b
                          and f"<onx:fill_color>{before['fill']}</onx:fill_color>" in b for b in blocks)


def test_line_style_dialog_takes_areas_too(loaded: Page):
    """Line style… is offered for a selection of areas and sets their style."""
    _set_type(loaded, "shapes")
    rows = loaded.locator(ROW)
    uids = [rows.nth(i).get_attribute("data-uid") for i in range(2)]
    for i in range(2):
        rows.nth(i).locator(".sel-box").check()
    expect(loaded.locator("#bulk-line")).to_be_visible()
    loaded.click("#bulk-line")
    d = loaded.locator("#mark-dialog")
    expect(d.locator("h2")).to_have_text("Line style")
    assert d.locator(".line-rows .lr-name").count() == 2
    d.locator('.tog[data-style="dash"]').click()
    loaded.click("#line-apply")
    expect(loaded.locator("#mark-modal")).to_be_hidden()
    assert [loaded.evaluate(_LINE.format(uid=u))["style"] for u in uids] == ["dash", "dash"]
    expect(loaded.locator("#status")).to_have_text("Changed 2 areas")


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
    expect(fresh_page.locator("#confirm-title")).to_have_text("4 areas will lose their fill.")
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
    assert names == ["All", "Waypoints", "Lines", "Areas"]


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


def test_a_name_cannot_be_committed_empty(fresh_page):
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    original = fresh_page.evaluate("DATA.groups[0].items[0].name")
    box = fresh_page.locator(".name-in").first
    box.click()
    box.fill("")
    box.press("Enter")
    fresh_page.wait_for_timeout(300)

    assert fresh_page.evaluate("DATA.groups[0].items[0].name") == original
    assert "name is required" in fresh_page.inner_text("#status").lower()


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
        "You have 1 unexported change to this map. Starting over discards it."
    )
    loaded.keyboard.press("Escape")
    expect(loaded.locator("#confirm")).to_be_hidden()
    assert loaded.evaluate("Object.keys(EDITS).length") == 1
    assert loaded.evaluate("document.body.dataset.stage") == "edit"


def _open_changed_waypoint_note(page: Page, text: str):
    """Open the note editor on a waypoint and type a draft (not applied)."""
    uid = page.evaluate(
        "DATA.groups.flatMap(g=>g.items).find(i => i.kind === 'waypoints').uid"
    )
    page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    page.locator(".desc-in").first.fill(text)
    return uid


def _gpx_blob(zb: bytes) -> str:
    zf = zipfile.ZipFile(io.BytesIO(zb))
    return "".join(
        zf.read(n).decode("utf-8", "replace") for n in zf.namelist() if n.endswith(".gpx")
    )


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
    loaded.locator("#confirm").get_by_role("button", name="Cancel").click()
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
    same numbers RUNBOOK.md gives -- instead of silently counting it."""
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
    assert "**1 item(s) could not be exported**" in zf.read("RUNBOOK.md").decode()
    text = fresh_page.locator("#runbook").inner_text()
    assert "1 item could not be exported" in text
    assert "1 of 2 were written" in text


# ---------------------------------------------------------------------------
# Roadmap Phase 3: GPX/KML input. Every test here runs under the ENFORCED CSP
# (no bypass_csp), so only CSP-safe waits are used -- no evaluate, no
# wait_for_function, no window.__cairn* flags -- and any CSP console message
# fails the test.
# ---------------------------------------------------------------------------

FX_DIR = Path(__file__).resolve().parent.parent / "fixtures"
ONX_PAIR = [FX_DIR / "onx_dialect" / "onx_dialect.gpx", FX_DIR / "onx_dialect" / "onx_dialect.kml"]
CALTOPO_GPX = FX_DIR / "bitterroots" / "bitterroots_subet.gpx"
CALTOPO_NOTICE = ("CalTopo's GPX has no folders, icons or waypoint colors. "
                  "Its GeoJSON or KML export keeps them.")


@pytest.fixture()
def csp_page(browser):
    """A booted page in a context that enforces the production CSP."""
    ctx = browser.new_context(accept_downloads=True)  # deliberately no bypass_csp
    page = ctx.new_page()
    violations = []
    page.on("console", lambda m: violations.append(m.text)
            if "Content Security Policy" in m.text else None)
    page.goto(f"{BASE_URL}/index.html")
    # Not wait_for_function: under the enforced CSP Playwright cannot evaluate
    # page JS (no 'unsafe-eval'), so readiness is read from the DOM.
    expect(page.locator("body")).to_have_attribute("data-engine", "ready", timeout=60000)
    yield page
    ctx.close()
    assert not violations, f"CSP violations: {violations}"


def _load_files(page: Page, paths) -> None:
    page.set_input_files("#file", [str(p) for p in paths])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)


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
    # Title loses .gpx; the label says whose map it is; no CalTopo notice.
    expect(page.locator("#map-title")).to_have_text("onx dialect")
    expect(page.locator("#map-label")).to_have_text("onX map")
    expect(page.locator("#source-notice")).to_be_hidden()
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
        "title", re.compile(r"^Your onX file uses the icon “Campsite”, which isn’t in"))
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
    expect(page.locator(".rb-count")).to_have_text("8 markups")
    expect(page.locator(".rb-step h2")).to_have_text("onx dialect · 8 markups · 3 files")
    expect(page.locator(".rb-do li").first).to_have_text(
        "In onX, choose Import and add these 3 files together.")
    expect(page.locator("#done-stage input")).to_have_count(0)
    with page.expect_download() as dl:
        page.click("#download")
    zf = zipfile.ZipFile(dl.value.path())
    assert sorted(zf.namelist()) == [
        "01_onx_dialect/onx_dialect_Areas.gpx",
        "01_onx_dialect/onx_dialect_Tracks.gpx",
        "01_onx_dialect/onx_dialect_Waypoints.gpx",
        "RUNBOOK.md",
    ]
    # Download this folder, under the enforced CSP: the same three files, no runbook.
    with page.expect_download() as dl1:
        page.click(".rb-dl")
    assert dl1.value.suggested_filename == "01_onx_dialect.zip"
    one = zipfile.ZipFile(dl1.value.path())
    assert sorted(one.namelist()) == sorted(n for n in zf.namelist() if n != "RUNBOOK.md")
    assert all(one.read(n) == zf.read(n) for n in one.namelist())
    wpts = zf.read("01_onx_dialect/onx_dialect_Waypoints.gpx").decode()
    # The writer sorts by name (Camp & water, Main Wall, Slide obs).
    assert re.findall(r"<onx:icon>([^<]*)</onx:icon>", wpts) == ["Campsite", "Climbing", "Hazard"]
    assert zf.read("01_onx_dialect/onx_dialect_Tracks.gpx").decode().count("<trk>") == 2
    areas = zf.read("01_onx_dialect/onx_dialect_Areas.gpx").decode()
    assert areas.count("<rte>") == 3 and areas.count("<type>Area</type>") == 3
    runbook = zf.read("RUNBOOK.md").decode()
    assert "Rename it to:** `onx dialect`" in runbook
    # The KML's holed polygon can't be an onX area with its hole: reported.
    assert "### Holes not kept in onX" in runbook and "- `Hunt unit`  (onx dialect)" in runbook


def test_caltopo_gpx_shows_the_geojson_notice(csp_page: Page):
    page = csp_page
    _load_files(page, [CALTOPO_GPX])
    expect(page.locator("#source-notice")).to_be_visible()
    expect(page.locator("#source-notice")).to_have_text(CALTOPO_NOTICE)
    expect(page.locator("#map-title")).to_have_text("bitterroots subet")
    expect(page.locator("#map-label")).to_have_text("CalTopo map")
    expect(page.locator(".folder h2")).to_have_text("bitterroots subet")
    expect(page.locator(ROW)).to_have_count(10)


def test_several_files_become_one_folder_each_and_start_over_clears_the_notice(csp_page: Page):
    page = csp_page
    rattlesnake = FX_DIR / "rattlesnake_test_waypoints.gpx"
    _load_files(page, [*ONX_PAIR, CALTOPO_GPX, rattlesnake])
    _keep_fills(page)  # onx_dialect's area has a non-default fill
    expect(page.locator(".folder h2")).to_have_text(
        ["rattlesnake test waypoints", "bitterroots subet", "onx dialect"])
    expect(page.locator("#map-title")).to_have_text("onx dialect + 2 more")
    expect(page.locator("#map-label")).to_have_text("Map")
    expect(page.locator("#source-notice")).to_have_text(CALTOPO_NOTICE)
    # Start over goes back to an empty drop screen; it never adds (UI-12, UI-21).
    page.locator("#edit-stage .newmap").click()
    page.click("#confirm .confirm-actions button:text-is('Start over')")
    expect(page.locator("body")).to_have_attribute("data-stage", "drop")
    expect(page.locator("#source-notice")).to_be_hidden()
    _load_files(page, ONX_PAIR)
    _keep_fills(page)  # onx_dialect's area has a non-default fill
    expect(page.locator(".folder")).to_have_count(1)
    expect(page.locator("#source-notice")).to_be_hidden()


def test_bitterroots_geojson_still_reads_as_a_caltopo_map_without_the_notice(csp_page: Page):
    page = csp_page
    _load_files(page, [FIXTURE])
    expect(page.locator("#map-title")).to_have_text("Bitterroots (Complete)")
    expect(page.locator("#map-label")).to_have_text("CalTopo map")
    expect(page.locator("#source-notice")).to_be_hidden()
    expect(page.locator(".folder")).to_have_count(EXPECTED_TOTALS["folders"])


# --- review fixes: an input file's icon names and markup are data, not code ---------

_ONX_GPX_HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx xmlns:onx="https://wwww.onxmaps.com/" '
                 'xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="onXmaps backcountry web">\n')


def _onx_wpt(i: int, name: str, icon: str, notes: str = "") -> str:
    return (f'<wpt lat="46.{i}" lon="-114.{i}"><name>{name}</name><desc>name={name}\nnotes={notes}\n'
            f'id=id-{i}\ncolor=rgba(255,51,0,1)\nicon={icon}</desc><extensions>'
            f'<onx:color>rgba(255,51,0,1)</onx:color><onx:icon>{icon}</onx:icon></extensions></wpt>\n')


def _gpx_payload(name: str, wpts: str) -> dict:
    return {"name": name, "mimeType": "application/gpx+xml",
            "buffer": (_ONX_GPX_HEAD + wpts + "</gpx>\n").encode("utf-8")}


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


def _row(page: Page, name: str):
    box = page.get_by_role("checkbox", name=f"Select {name}", exact=True)
    return page.locator(ROW, has=box)


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


def test_caltopo_kml_loads_with_its_folders_and_no_notice(csp_page: Page):
    page = csp_page
    _load_files(page, [CALTOPO_SYN / "caltopo_synthetic.kml"])
    expect(page.locator("#map-label")).to_have_text("CalTopo map")
    expect(page.locator("#source-notice")).to_be_hidden()
    expect(page.locator(".folder h2")).to_have_text(
        ["Camps & Water #1", "Routes", "Areas", "Routes / Spur lines"])
    # The CalTopo symbol mapped to an onX icon, as it does from the GeoJSON.
    expect(_row(page, "Trailhead lot").locator(".icon-btn .icon-name")).to_have_text("Parking")


def test_caltopo_gpx_icons_and_colors_set_in_cairn_reach_the_exported_gpx(csp_page: Page):
    """Additive icons: a CalTopo GPX carries no icons or waypoint colors, so its
    waypoints arrive as name guesses or the default pin. Icons and colors set in
    Cairn -- one waypoint through the marker popover, two through the bulk
    dialog -- are written to the export as onx:icon / onx:color."""
    page = csp_page
    _load_files(page, [CALTOPO_SYN / "caltopo_synthetic.gpx"])
    expect(page.locator("#source-notice")).to_have_text(CALTOPO_NOTICE)
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
    return [(name, len(uids)) for _key, name, uids in ui]


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
    assert lay[-1] == ("Camps", 3) and dict(lay)["Lost Trail Pass"] == 28
    expect(_section(page, "Camps").locator("tbody tr")).to_have_count(3)

    # A second one: "New folder" is free again, so it is taken; Esc keeps it.
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    expect(page.locator("#folder-facets .folder-name-in")).to_have_value("New folder")
    page.keyboard.press("Escape")
    assert _layout(page)[-1] == ("New folder", 1)
    # The default is never a name that's taken: the third is "New folder 2".
    _drag(page, _first_row(page, "Paddling").locator(".note-btn"), page.locator(".new-folder"))
    expect(page.locator("#folder-facets .folder-name-in")).to_have_value("New folder 2")
    page.locator("#filter").click()   # leaving the field keeps the name
    expect(page.locator("#folder-facets .folder-name-in")).to_have_count(0)
    assert _layout(page)[-1] == ("New folder 2", 1)


def test_drag_onto_its_own_folder_or_nowhere_does_nothing(loaded: Page):
    page = loaded
    before = _layout(page)
    row = _first_row(page, "Lost Trail Pass")
    _drag(page, row.locator(".note-btn"), _rail(page, "Lost Trail Pass"))
    assert _layout(page) == before
    expect(page.locator("#status")).to_have_text("Map loaded")
    # Dropped on the list, the search box, the rail's "All": nothing.
    for target in (page.locator("#folders tbody tr").nth(5), page.locator("#filter"),
                   page.locator("#folder-facets .facet-btn").first):
        _drag(page, row.locator(".note-btn"), target)
        assert _layout(page) == before
    expect(page.locator("#status")).to_have_text("Map loaded")
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
    expect(page.locator("#confirm-actions button")).to_have_text(["Move them", "Cancel"])
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
    assert names.index("North Roots") == 1 and dict(lay)["North Roots"] == 53
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
    expect(pop.locator(".move-opt").last).to_have_text("+ New folder…")
    expect(pop.locator(".move-opt").first).to_be_focused()   # Unorganized

    # Esc closes it and gives focus back to More.
    page.keyboard.press("Escape")
    expect(pop).to_be_hidden()
    expect(page.locator("#more-btn")).to_be_focused()
    expect(page.locator("#selcount")).to_have_text("2 selected")

    # Arrow keys skip "here now": Down from Unorganized lands on North Roots.
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    expect(pop.locator(".move-opt", has_text="North Roots")).to_be_focused()
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowUp")          # wraps to the end
    expect(pop.locator(".move-new")).to_be_focused()
    page.keyboard.press("Home")
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
    assert lay[-1] == ("Yurts", 2) and dict(lay)["North Roots"] == 22


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
    assert _layout(page)[-1] == ("New folder", 1)


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
    assert manifest[-1]["folder"] == "Ski lines" and manifest[-1]["count"] == 4
    expect(boxes.last.locator("h2")).to_have_text("Ski lines · 4 markups · 1 file")
    expect(boxes.last.locator(".rb-do li").last).to_have_text("onX names the folder by date. Rename it to Ski lines.")
    big = boxes.filter(has_text="Blodgett / Big Creek")
    expect(big.locator(".rb-do li").last).to_contain_text("Rename it to Blodgett / Big Creek.")
    for i, e in enumerate(manifest):
        page.wait_for_timeout(300)
        with page.expect_download() as dl:
            boxes.nth(i).locator(".rb-dl").click()
        nn = f"{i + 1:02d}_{e['safe']}"
        assert dl.value.suggested_filename == f"{nn}.zip"
        names = zipfile.ZipFile(dl.value.path()).namelist()
        assert names == [f["path"] for f in e["files"]] and all(n.startswith(nn + "/") for n in names)
    assert manifest[5]["safe"] == "Blodgett_Big_Creek"
    assert manifest[-1]["files"][0]["path"].startswith("10_Ski_lines/Ski_lines_")
    # Back, move more, export again: the screen follows.
    page.click("#back")
    _drag(page, _first_row(page, "Ski lines").locator(".note-btn"), _rail(page, "Paddling"))
    _done(page)
    manifest = page.evaluate("MANIFEST")
    assert manifest[-1]["count"] == 3
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
        "You have 3 unexported changes to this map. Starting over discards them.")
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
# Each test names the finding it pins (tests/output/round2-findings.md).
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
    assert subs.count("Not in any CalTopo folder") == 1


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
    assert _layout(page)[-1] == ("New folder", 1)
    page.click("#back")
    _drag(page, _first_row(page, "New folder").locator(".note-btn"), page.locator(".new-folder"))
    page.keyboard.type("Blodgett")
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    expect(inp).to_have_value("Blodgett")
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("Kayaks")
    page.keyboard.press("Enter")
    assert _layout(page)[-1] == ("Kayaks", 1)
    # A header rename's Cancel still just keeps the old name.
    _section(page, "Kayaks").locator(".folder-name").click()
    page.keyboard.type("Blodgett")
    page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    expect(page.locator(".folder-name-in")).to_have_count(0)
    assert _layout(page)[-1] == ("Kayaks", 1)


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
    assert _layout(page)[-1] == ("Rafts", 1)
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
    expect(card.locator(".rb-do b").last).to_have_text(long)   # the instruction stays whole


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
    expect(page.locator("#status")).to_contain_text("Built")
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
        "You have 3 unexported changes to this map. Starting over discards them.")
