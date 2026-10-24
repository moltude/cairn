import sys; sys.path.insert(0, __file__.rsplit("/",1)[0])
from probe1 import boot
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True)
    p, errs = boot(ctx)
    p.locator("#folders tbody tr[data-uid]").nth(0).locator(".sel-box").click()
    p.click("#more-btn"); p.click("#bulk-move"); p.wait_for_timeout(100)
    print("Move to open:", p.evaluate("!!MOVE"))
    p.click("#more-btn"); p.wait_for_timeout(100)
    r = p.evaluate("""() => { const b = document.querySelector('#bulk-exclude').getBoundingClientRect();
      const t = document.elementFromPoint(b.x + b.width/2, b.y + b.height/2);
      return {move: !!MOVE, menu: !document.querySelector('#more-menu').classList.contains('hidden'),
              excludeCoveredBy: t.closest('#move-pop') ? 'move-pop' : (t.id || t.className)}; }""")
    print("after clicking More again:", r)
    p.locator("#bulk-exclude").click(force=True) if False else None
    try:
        p.locator("#bulk-exclude").click(timeout=2000); print("exclude clickable")
    except Exception as e:
        print("Leave out of export not clickable:", str(e).splitlines()[0][:90])
    print("errors", errs); br.close()
