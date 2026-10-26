"""Shared constants and helpers for the web e2e tests (moved out of
test_web_app.py on 2026-10-25 so several test files can use them; see
docs/plans/BULK_RENAME.md, Phase 1). Plain functions only; the fixtures are in
conftest.py."""
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

from playwright.sync_api import Page, expect

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
FX_DIR = Path(__file__).resolve().parent.parent / "fixtures"
_ONX_GPX_HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx xmlns:onx="https://wwww.onxmaps.com/" '
                 'xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="onXmaps backcountry web">\n')


def _server_reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/index.html", timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


# A name is required to export (N1, 2026-10-25): with blank-named items to write,
# Export first opens "N items need a name" (Cancel · Name them Untitled). Bitterroots
# has 7, so the export helpers below press NAME_THEM there unless a test passes
# names=None (leave the confirm up) or another button label.
NAME_THEM = "Name them Untitled"
NEEDS_NAME_TITLE = re.compile(r"^(1 item needs|[\d,]+ items need) a name$")


def _names_confirm_open(page: Page) -> bool:
    """Whether the "N items need a name" confirm is up. DOM only (works under the CSP)."""
    return page.locator("#confirm").is_visible() and bool(
        NEEDS_NAME_TITLE.match(page.locator("#confirm-title").text_content() or ""))


def _answer_names(page: Page, names: str | None = NAME_THEM) -> bool:
    """Press `names` in the "N items need a name" confirm if it is up (None: leave
    it); whether it was. Export runs in the click's own handler, so the confirm is
    either up or not by the time the click returns."""
    if names and _names_confirm_open(page):
        page.click(f"#confirm-actions button:text-is('{names}')")
        return True
    return False


def _click_export(page: Page, names: str | None = NAME_THEM) -> None:
    """Click Export and answer the names confirm (N1) the way `names` says."""
    page.click("#export")
    _answer_names(page, names)


def export_zip_bytes(page: Page, confirm: str | None = None, names: str | None = NAME_THEM) -> bytes:
    """Trigger export and pull the resulting Blob back into Python as bytes.

    `confirm` names the button to press in the unsaved-note prompt when one is
    expected; without it, a prompt would hang the wait below (as it should).
    `names` is the button for the "N items need a name" confirm that may follow
    (N1): "Name them Untitled" by default.
    """
    page.evaluate("window.__cairnExported = false")
    page.click("#export")
    if confirm:
        page.click(f"#confirm .confirm-actions button:text-is('{confirm}')")
    _answer_names(page, names)
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


def _export_zip(page, names: str | None = NAME_THEM):
    """Export in the browser and return the downloaded zip as a ZipFile. `names`:
    the button for the "N items need a name" confirm (N1), as export_zip_bytes."""
    import base64, io, zipfile
    page.click("#export")
    _answer_names(page, names)
    page.wait_for_function("window.__cairnExported === true", timeout=180_000)
    b64 = page.evaluate(
        "async () => { const u = new Uint8Array(await ZIP.arrayBuffer());"
        " let s=''; for (let i=0;i<u.length;i++) s += String.fromCharCode(u[i]);"
        " return btoa(s); }"
    )
    return zipfile.ZipFile(io.BytesIO(base64.b64decode(b64)))


def _load_files(page: Page, paths) -> None:
    page.set_input_files("#file", [str(p) for p in paths])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)


def _set(page: Page, uid: str, **patch) -> None:
    page.evaluate("([u, p]) => edit(allItems().find(i => i.uid === u), p)", [uid, patch])


def _tick(page: Page, uids) -> None:
    for u in uids:
        page.locator(f'tr[data-uid="{u}"] .sel-box').check()


def _is_marked(loc, tag: str = "keep") -> bool:
    return loc.evaluate("(e, t) => e.__cairnMark === t", tag)


def _open_changed_waypoint_note(page: Page, text: str):
    """Open the note editor on a waypoint and type a draft (not applied)."""
    uid = page.evaluate(
        "DATA.groups.flatMap(g=>g.items).find(i => i.kind === 'waypoints').uid"
    )
    page.locator(f'tr[data-uid="{uid}"] .note-btn').click()
    page.locator(".desc-in").first.fill(text)
    return uid


def _row(page: Page, name: str):
    box = page.get_by_role("checkbox", name=f"Select {name}", exact=True)
    return page.locator(ROW, has=box)


def _gpx_blob(zb: bytes) -> str:
    zf = zipfile.ZipFile(io.BytesIO(zb))
    return "".join(
        zf.read(n).decode("utf-8", "replace") for n in zf.namelist() if n.endswith(".gpx")
    )


def _onx_wpt(i: int, name: str, icon: str, notes: str = "") -> str:
    return (f'<wpt lat="46.{i}" lon="-114.{i}"><name>{name}</name><desc>name={name}\nnotes={notes}\n'
            f'id=id-{i}\ncolor=rgba(255,51,0,1)\nicon={icon}</desc><extensions>'
            f'<onx:color>rgba(255,51,0,1)</onx:color><onx:icon>{icon}</onx:icon></extensions></wpt>\n')


def _gpx_payload(name: str, wpts: str) -> dict:
    return {"name": name, "mimeType": "application/gpx+xml",
            "buffer": (_ONX_GPX_HEAD + wpts + "</gpx>\n").encode("utf-8")}


# ---------------------------------------------------------------------------
# Bulk rename and note change (docs/plans/BULK_RENAME.md 6.3). DOM only where
# a test may run under the enforced CSP (csp=True): no wait_for_function or
# string evaluate there. Function-form evaluate_all works under the CSP.
# ---------------------------------------------------------------------------

BULK_FIELDS = {"text": "#bulk-text", "find": "#bulk-find", "repl": "#bulk-repl"}
STATUS_CHANGED = re.compile(r"^Changed ([\d,]+) items?\.$")
_GPX_NS = "{http://www.topografix.com/GPX/1/1}"


def _load_text(page: Page, text: str, name: str = "map.json") -> None:
    """Load a generated map (e.g. tests.bulk_rename_vectors.item_map) without a file."""
    page.set_input_files("#file", files=[{"name": name, "mimeType": "application/json",
                                          "buffer": text.encode("utf-8")}])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)


def _preview_seq(page: Page) -> int:
    return int(page.get_attribute("#mark-dialog", "data-preview-seq") or 0)


def _wait_preview_past(page: Page, seq: int, *, csp: bool = False, timeout: float = 5000) -> None:
    """Wait until the preview has rendered since #mark-dialog[data-preview-seq] read seq."""
    if csp:
        expect(page.locator("#mark-dialog")).not_to_have_attribute(
            "data-preview-seq", str(seq), timeout=timeout)
    else:
        page.wait_for_function(
            "s => Number(document.querySelector('#mark-dialog').dataset.previewSeq) > s",
            arg=seq, timeout=timeout)


def _open_bulk(page: Page, which: str) -> None:
    """More > Rename... (which="rename") or Change note... ("note"), then wait for the
    dialog's first render. Waits on the DOM, not on _menu_action's fixed sleeps."""
    item = {"rename": "#bulk-rename", "note": "#bulk-note"}[which]
    page.click("#more-btn")
    page.locator(item).click()
    dlg = page.locator("#mark-dialog")
    expect(dlg).to_have_attribute("data-bulk", which)
    expect(dlg).to_have_attribute("data-preview-seq", re.compile(r"^[1-9]\d*$"))


def _set_mode(page: Page, mode: str, *, csp: bool = False) -> None:
    """Pick a mode toggle (prefix, suffix, replace, set) and wait for its render."""
    tog = page.locator(f'#mark-dialog .mode-tog[data-mode="{mode}"]')
    if tog.get_attribute("aria-pressed") == "true":
        return
    seq = _preview_seq(page)
    tog.click()
    expect(tog).to_have_attribute("aria-pressed", "true")
    _wait_preview_past(page, seq, csp=csp)


def _type_spec(page: Page, *, csp: bool = False, match_case: bool | None = None, **fields) -> None:
    """Fill text=, find=, repl= (in the call's order), waiting after each for the render
    it causes; match_case=True/False sets the toggle. A field already holding its value
    is left alone (filling it again would fire no render to wait for)."""
    for key, value in fields.items():
        loc = page.locator(BULK_FIELDS[key])
        if loc.input_value() == value:
            continue
        seq = _preview_seq(page)
        loc.fill(value)
        _wait_preview_past(page, seq, csp=csp)
    if match_case is not None:
        mc = page.locator("#bulk-match-case")
        if (mc.get_attribute("aria-pressed") == "true") != match_case:
            seq = _preview_seq(page)
            mc.click()
            _wait_preview_past(page, seq, csp=csp)


def _type_slowly(page: Page, sel: str, text: str, delay: float) -> None:
    page.locator(sel).press_sequentially(text, delay=delay)


_PREVIEW_ROWS_JS = """rows => rows.map(r => {
  const cell = sel => {
    const e = r.querySelector(sel);
    if (!e) return null;
    return e.classList.contains('is-placeholder') || e.querySelector('.is-placeholder') ? '' : e.textContent;
  };
  return [r.dataset.uid, cell('.na-before'), cell('.na-after'), r.dataset.flags || ''];
})"""


def _preview_rows(page: Page) -> list:
    """[(uid, before, after, flags)] from the DOM. A cell showing the "Untitled"
    placeholder (.is-placeholder) reads as "", so rows compare equal to it.name;
    flags is a frozenset of data-flags."""
    rows = page.locator("#mark-dialog .na-row").evaluate_all(_PREVIEW_ROWS_JS)
    return [(u, b, a, frozenset(f.split())) for u, b, a, f in rows]


def _save_bulk(page: Page) -> str:
    """Click Save; the status line as soon as it reads "Changed N item(s).", within
    the 8 s it stays up (STATUS_LINGER_MS)."""
    page.click("#bulk-apply")
    expect(page.locator("#mark-modal")).to_be_hidden()
    st = page.locator("#status")
    expect(st).to_have_text(STATUS_CHANGED, timeout=8000)
    return st.text_content().strip()


def _status_count(text: str) -> int:
    """N from "Changed N items." ("1,500" -> 1500)."""
    m = STATUS_CHANGED.match(text.strip())
    assert m, text
    return int(m.group(1).replace(",", ""))


def _gpx_texts(zf, child: str) -> list:
    import xml.etree.ElementTree as ET
    if isinstance(zf, (bytes, bytearray)):
        zf = zipfile.ZipFile(io.BytesIO(zf))
    out = []
    for n in zf.namelist():
        if n.endswith(".gpx"):
            root = ET.fromstring(zf.read(n))
            for tag in ("wpt", "trk", "rte"):
                for el in root.iter(_GPX_NS + tag):
                    out.append(el.findtext(_GPX_NS + child) or "")
    return out


def _gpx_names(zf) -> list:
    """Every item's <name> text in every GPX member of a zip (ZipFile or bytes); an
    empty <name> reads "", not None."""
    return _gpx_texts(zf, "name")


def _gpx_descs(zf) -> list:
    """Every item's <desc> text ("" when the element is empty or missing)."""
    return _gpx_texts(zf, "desc")

