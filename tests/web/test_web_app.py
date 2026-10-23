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
    """The type filter is a segmented button group (All / Waypoints / Lines /
    Areas); "" is All."""
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


def test_pyodide_boots_and_reports_engine_version(fresh_page: Page):
    status_text = fresh_page.text_content("#status")
    status_class = fresh_page.get_attribute("#status", "class")

    assert status_text is not None
    assert "Ready" in status_text
    assert re.search(r"engine v\d+\.\d+\.\d+", status_text), status_text
    assert "ready" in (status_class or "")


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


def test_uids_encode_a_per_kind_index(fresh_page):
    """Regression: the index used to be a running total across kinds.

    Tracks were numbered from 23 and shapes from 40, so the export's exclusion
    filter -- which decodes the uid back to a position -- dropped the wrong
    features, or indexed past the end of the list entirely.
    """
    fresh_page.set_input_files("#file", str(FIXTURE))
    fresh_page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)

    bad = fresh_page.evaluate("""
        DATA.groups.flatMap(g => {
          const byKind = {};
          g.items.forEach(i => (byKind[i.kind] = byKind[i.kind] || []).push(
              parseInt(i.uid.split('::').pop(), 10)));
          return Object.entries(byKind)
            .filter(([k, idx]) => Math.min(...idx) !== 0 ||
                                  Math.max(...idx) !== idx.length - 1)
            .map(([k]) => g.name + '/' + k);
        })
    """)
    assert bad == [], f"uid indices are not per-kind for: {bad}"

    uids = fresh_page.evaluate("DATA.groups.flatMap(g=>g.items).map(i=>i.uid)")
    assert len(uids) == len(set(uids))


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
    assert pop.locator(".icon-pick").count() >= 1
    pop.locator('.icon-pick[data-icon="Summit"]').click()
    assert "Summit · Blue" in pop.locator(".pop-desc").inner_text()
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
    after = loaded.locator("#mark-dialog .na-after").all_inner_texts()
    assert after and all(t.endswith("· Purple") for t in after), after
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

    loaded.click("#chips .linkbtn")  # Clear filters
    loaded.wait_for_timeout(150)
    assert loaded.locator(ROW).count() == EXPECTED_TOTALS["items"]
    assert loaded.locator("#chips").is_hidden()


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
    fresh_page.click("#help-btn")
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
        expect(page.locator("#status")).to_contain_text("Ready", timeout=60000)
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
        .find(b => b.textContent.trim() === 'Apply').getBoundingClientRect();
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
    loaded.focus("#help-btn")
    loaded.keyboard.press("Enter")
    expect(loaded.locator("#help")).to_be_visible()
    inside = "document.querySelector('#help .modal-card').contains(document.activeElement)"
    assert loaded.evaluate("document.activeElement.id") == "help-close"
    for key in ("Tab", "Tab", "Shift+Tab", "Shift+Tab"):
        loaded.keyboard.press(key)
        assert loaded.evaluate(inside), f"{key} left the help dialog"
    loaded.keyboard.press("Escape")
    expect(loaded.locator("#help")).to_be_hidden()
    assert loaded.evaluate("document.activeElement.id") == "help-btn"


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
    assert "hasn't been applied" in loaded.inner_text("#confirm-body")
    assert loaded.evaluate("document.activeElement.textContent") == "Apply"
    assert loaded.evaluate("window.__cairnExported") is False  # nothing exported yet
    loaded.keyboard.press("Escape")  # Esc == Cancel
    expect(dlg).to_be_hidden()

    assert f"<desc>{marker}</desc>" in _gpx_blob(export_zip_bytes(loaded, confirm="Apply"))


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
    expect(page.locator("#status")).to_contain_text("Ready", timeout=60000)
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
    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done", timeout=60000)
    expect(page.locator(".rb-step")).to_have_count(1)
    expect(page.locator(".rb-count")).to_have_text("8 markups")
    with page.expect_download() as dl:
        page.click("#download")
    zf = zipfile.ZipFile(dl.value.path())
    assert sorted(zf.namelist()) == [
        "01_onx_dialect/onx_dialect_Areas.gpx",
        "01_onx_dialect/onx_dialect_Tracks.gpx",
        "01_onx_dialect/onx_dialect_Waypoints.gpx",
        "RUNBOOK.md",
    ]
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
