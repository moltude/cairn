import sys; sys.path.insert(0, __file__.rsplit("/",1)[0])
from pathlib import Path
from probe1 import boot
from playwright.sync_api import sync_playwright
sys.path.insert(0, __file__.rsplit("/", 2)[0])   # scripts/qa
import fuzz_ui as F  # noqa: E402
M = F.build_maps()["twins"][0]
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True)
    p, errs = boot(ctx, (M,))
    print(p.evaluate("""DATA.groups.map(g => [g.key, g.name, g.items.length, isUnorganized(g)])"""))
    print(p.evaluate("""[...document.querySelectorAll('#folders section.folder')].map(s => [s.getAttribute('aria-label'), s.querySelector('.folder-sub').textContent])"""))
    print(p.evaluate("""[...document.querySelectorAll('#folder-facets .facet-btn.unorg')].map(b => b.textContent)"""))
    br.close()
