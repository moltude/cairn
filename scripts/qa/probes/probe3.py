import sys; sys.path.insert(0, __file__.rsplit("/",1)[0])
from probe1 import boot, press_click
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True)
    # P3: open a header name, change nothing, click a checkbox like a person
    p, errs = boot(ctx)
    p.locator("#folders .folder-name").nth(1).click()
    t = p.locator("#folders tbody tr[data-uid]").nth(5).locator(".sel-box")
    press_click(p, t, 80)
    print("P3 unchanged header name then tick: landed =", p.evaluate("SEL.size") == 1)
    # P4: rename to a taken name, then press on a row and drag to a folder
    p.locator("#folders .folder-name").nth(2).click()      # North Roots
    p.keyboard.press("ControlOrMeta+a"); p.keyboard.type("Paddling")
    row = p.locator("#folders tbody tr[data-uid]").nth(0).locator(".note-btn")
    row.scroll_into_view_if_needed(); b = row.bounding_box()
    x, y = b["x"] + 20, b["y"] + b["height"]/2
    p.mouse.move(x, y); p.mouse.down(); p.wait_for_timeout(60)
    p.mouse.move(x + 10, y + 10, steps=3)
    st = p.evaluate("({confirm: !!CONFIRM, drag: DRAG && DRAG.active, ghost: !!document.querySelector('#drag-ghost')})")
    print("P4 mid-drag:", st)
    tgt = p.locator("#folder-facets > *").nth(5); tgt.scroll_into_view_if_needed(); bb = tgt.bounding_box()
    p.mouse.move(bb["x"] + bb["width"]/2, bb["y"] + bb["height"]/2, steps=5)
    hit = p.evaluate(f"(document.elementFromPoint({bb['x']+bb['width']/2},{bb['y']+bb['height']/2})||{{}}).className")
    p.mouse.up(); p.wait_for_timeout(100)
    print("P4 after drop: element under pointer:", hit, "| status:", p.locator("#status").inner_text(),
          "| confirm open:", p.evaluate("!!CONFIRM"), "| focus:", p.evaluate("document.activeElement.textContent"))
    print("errors", errs)
    br.close()
