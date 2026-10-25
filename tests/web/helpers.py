"""Shared constants and helpers for the web e2e tests (moved out of
test_web_app.py on 2026-10-25 so several test files can use them). Plain
functions only; the fixtures are in conftest.py."""
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

