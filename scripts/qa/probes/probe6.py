import sys; sys.path.insert(0, __file__.rsplit("/",1)[0])
from probe1 import boot
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True)
    p, errs = boot(ctx)
    p.locator("#folders .folder-name").nth(2).click(); p.keyboard.press("ControlOrMeta+a"); p.keyboard.type("Paddling"); p.keyboard.press("Enter")
    p.wait_for_timeout(100)
    print("merge dialog open:", p.evaluate("!!CONFIRM"), "focus:", p.evaluate("document.activeElement.textContent"))
    p.keyboard.press("ControlOrMeta+a"); p.wait_for_timeout(100)
    print("Ctrl+A under the dialog -> SEL:", p.evaluate("SEL.size"), "| selbar visible:", p.locator("#selbar").is_visible())
    p.keyboard.press("Escape"); p.keyboard.press("Escape")
    f = p.locator("#folders tbody tr[data-uid]").nth(0).locator(".name-in"); f.click(); p.keyboard.type("z"); p.keyboard.press("Enter"); p.wait_for_timeout(100)
    print("Enter in a row name -> focus:", p.evaluate("document.activeElement === document.body ? 'BODY' : document.activeElement.outerHTML.slice(0,60)"))
    f = p.locator("#folders tbody tr[data-uid]").nth(1).locator(".name-in"); f.click(); p.keyboard.press("Escape"); p.wait_for_timeout(100)
    print("Esc in a row name -> focus:", p.evaluate("document.activeElement === document.body ? 'BODY' : document.activeElement.outerHTML.slice(0,60)"))
    print("errors", errs); br.close()
