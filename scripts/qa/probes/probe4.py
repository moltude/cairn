import sys; sys.path.insert(0, __file__.rsplit("/",1)[0])
from probe1 import boot, press_click
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True)
    p, errs = boot(ctx)
    # P37: rename North Roots -> "Paddling" (taken), then click Export directly
    p.locator("#folders .folder-name").nth(2).click()
    p.keyboard.press("ControlOrMeta+a"); p.keyboard.type("Paddling")
    p.click("#export"); p.wait_for_timeout(400)
    print("P37 stage:", p.evaluate("document.body.dataset.stage"), "| confirm open:", p.evaluate("!!CONFIRM"),
          "| confirm title:", p.locator("#confirm-title").inner_text() if p.evaluate("!!CONFIRM") else None)
    boxes = p.locator("#runbook .rb-title").all_inner_texts()
    if p.evaluate("!!CONFIRM"):
        p.locator("#confirm-actions button", has_text="Move them").click(); p.wait_for_timeout(200)
    print("  after Move them: stage", p.evaluate("document.body.dataset.stage"),
          "| folders now:", p.evaluate("DATA.groups.length"), "| export boxes:", len(boxes),
          "| 'North Roots' box still shown:", any(b.startswith("North Roots") for b in p.locator('#runbook .rb-title').all_inner_texts()),
          "| manifest names include North Roots:", p.evaluate("MANIFEST.some(e => e.folder === 'North Roots')"),
          "| bridge has North Roots:", p.evaluate("JSON.parse(py.runPython('import json; json.dumps(bridge._layout())')).some(f=>f.name==='North Roots')"))
    p.close()
    # P5: Ctrl+A while the Move to list is open
    p, errs2 = boot(ctx)
    p.locator("#folders tbody tr[data-uid]").nth(0).locator(".sel-box").click()
    p.locator("#more-btn").focus(); p.keyboard.press("Enter"); p.keyboard.press("Enter")
    print("P5 move open:", p.evaluate("!!MOVE"), "heading:", p.locator("#move-h").inner_text())
    p.keyboard.press("ControlOrMeta+a"); p.wait_for_timeout(100)
    print("  after Ctrl+A: SEL", p.evaluate("SEL.size"), "| move still open:", p.evaluate("!!MOVE"),
          "| heading:", p.locator("#move-h").inner_text() if p.evaluate("!!MOVE") else None,
          "| focus:", p.evaluate("document.activeElement.className || document.activeElement.tagName"))
    if p.evaluate("!!MOVE"):
        p.keyboard.press("ArrowDown"); p.keyboard.press("Enter"); p.wait_for_timeout(100)
        print("  picked: status:", p.locator("#status").inner_text(), "| SEL left:", p.evaluate("SEL.size"))
    print("errors", errs, errs2)
    br.close()
