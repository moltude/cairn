"""Replay a run to action N, instrument the next leave_field_by_click."""
import json, random, sys
sys.path.insert(0, __file__.rsplit("/", 2)[0])   # scripts/qa
import fuzz_ui as F
from playwright.sync_api import sync_playwright
rec = json.load(open(sys.argv[1])); N = int(sys.argv[2])
maps = F.build_maps()
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True, accept_downloads=True, viewport={"width": 1440, "height": 900})
    s = F.Session(ctx, rec["map"], maps[rec["map"]], None); s.open()
    for a in rec["actions"][:N]:
        s.act(a); s.check("x")
    p = s.page
    p.evaluate("""() => { window.__log = [];
      for (const t of ['pointerdown','mousedown','focusout','pointerup','mouseup','click'])
        document.addEventListener(t, e => __log.push([t, (e.target.closest && (e.target.closest('[data-fk]')||{}).dataset?.fk) || e.target.id || e.target.tagName,
           document.querySelector('.rail').scrollTop, FILTERS.folder]), true);
      const rr = renderRail; window.renderRail = (...a) => { __log.push(['renderRail', new Error().stack.split('\\n')[2].trim()]); return rr(...a); };
      const rf = renderFolders; window.renderFolders = (...a) => { __log.push(['renderFolders', new Error().stack.split('\\n')[2].trim()]); return rf(...a); };
    }""")
    a = rec["actions"][N]
    try:
        print(s.act(a))
    except F.Violation as v:
        print("VIOLATION", v)
    for l in p.evaluate("__log"): print(l)
    print("status", p.locator("#status").inner_text())
    br.close()
