"""Targeted probes for suspicions read from web/app.js."""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[3]
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8765/").rstrip("/") + "/"
FIX = ROOT / "tests/fixtures/bitterroots/Bitterroots__Complete_.json"

def boot(ctx, files=(FIX,)):
    p = ctx.new_page(); p.set_viewport_size({"width": 1440, "height": 900})
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: m.type == "error" and errs.append(m.text))
    p.goto(BASE + "index.html")
    p.wait_for_selector('body[data-engine="ready"]', state="attached", timeout=120000)
    p.set_input_files("#file", [str(f) for f in files])
    p.wait_for_function("window.__cairnLoaded === true")
    return p, errs

def press_click(p, loc, hold=80):
    loc.scroll_into_view_if_needed()
    b = loc.bounding_box()
    p.mouse.move(b["x"] + b["width"]/2, b["y"] + b["height"]/2)
    p.mouse.down(); p.wait_for_timeout(hold); p.mouse.up()
    p.wait_for_timeout(100)

if __name__ == '__main__':
  with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True)
    # A: row name edit, then a human-speed click on another row's checkbox
    p, errs = boot(ctx)
    rows = p.locator("#folders tbody tr[data-uid]")
    n0 = rows.nth(0).locator(".name-in"); n0.click(); p.keyboard.type(" X")
    target = rows.nth(3).locator(".sel-box")
    press_click(p, target)
    print("A row-name then tick other row: SEL =", p.evaluate("[...SEL]"), "checked:", target.is_checked())
    # B: folder header rename, then a human-speed click on a row checkbox
    p.evaluate("SEL.clear(); renderFolders()")
    p.locator("#folders .folder-name").nth(1).click(); p.keyboard.type("Renamed B")
    target = p.locator("#folders tbody tr[data-uid]").nth(2).locator(".sel-box")
    press_click(p, target)
    print("B header rename then tick: SEL =", p.evaluate("[...SEL]"), "names:", p.evaluate("DATA.groups.map(g=>g.name).slice(0,3)"))
    # C: header rename then click a rail folder filter
    p.locator("#folders .folder-name").nth(2).click(); p.keyboard.type("Renamed C")
    press_click(p, p.locator("#folder-facets .facet-btn").nth(4))
    print("C header rename then rail filter: FILTERS.folder =", p.evaluate("FILTERS.folder"))
    # D: header rename then click the collapse of another folder
    p.evaluate("FILTERS.folder=null; renderEdit()")
    p.locator("#folders .folder-name").nth(0).click(); p.keyboard.type("Renamed D")
    press_click(p, p.locator("#folders .collapse").nth(3))
    print("D header rename then collapse: COLLAPSED =", p.evaluate("[...COLLAPSED]"))
    print("errors", errs)
    br.close()
