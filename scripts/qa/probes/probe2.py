import sys; sys.path.insert(0, __file__.rsplit("/",1)[0])
from probe1 import boot, press_click  # noqa  (probe1 runs at import; guard below)
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True)
    p, errs = boot(ctx)
    for hold in (0, 5, 20, 50, 120):
        for kind in ("row-name", "folder-rename"):
            p.evaluate("SEL.clear(); renderFolders()")
            if kind == "row-name":
                f = p.locator("#folders tbody tr[data-uid]").nth(0).locator(".name-in"); f.click(); p.keyboard.type("y")
            else:
                p.locator("#folders .folder-name").nth(1).click(); p.keyboard.type(f"R{hold}")
            t = p.locator("#folders tbody tr[data-uid]").nth(5).locator(".sel-box")
            press_click(p, t, hold)
            print(kind, "hold", hold, "ms -> tick landed:", p.evaluate("SEL.size") == 1)
    br.close()
