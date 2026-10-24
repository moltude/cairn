"""Replay a run up to action N, then diagnose the next exclude action's click."""
import json, random, sys
sys.path.insert(0, __file__.rsplit("/", 2)[0])   # scripts/qa
import fuzz_ui as F
from playwright.sync_api import sync_playwright
rec = json.load(open(sys.argv[1])); N = int(sys.argv[2])
F.KNOWN.update(["click_lost_after_field", "move_list_stale", "drag_under_modal", "dialog_over_export"])
maps = F.build_maps()
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(bypass_csp=True, accept_downloads=True)
    s = F.Session(ctx, rec["map"], maps[rec["map"]], None); s.open()
    for a in rec["actions"][:N]:
        try: s.act(a)
        except F.Violation as v: s.page.mouse.up(); print("known", v.sig)
        except Exception as e: print("harness", str(e)[:80])
    p = s.page
    st = s.snap(); print("sel", len(st["sel"]), "vis", st["vis"], "drag", st["drag"], "rename", st["rename"], "stage", st["stage"])
    rng = random.Random(rec["actions"][N]["s"])
    if not st["sel"]:
        uids = s.visible_uids()
        for u in rng.sample(uids, min(len(uids), rng.randint(1, 4))):
            box = p.locator(f'tr[data-uid="{u}"] .sel-box'); box.scroll_into_view_if_needed(); box.click()
    print("more disabled", p.locator("#more-btn").is_disabled(), "SEL", p.evaluate("SEL.size"))
    p.click("#more-btn"); p.wait_for_timeout(100)
    which = "#bulk-exclude" if rng.random() < 0.65 else "#bulk-include"
    info = p.evaluate(f"""() => {{ const b = document.querySelector('{which}'); const r = b.getBoundingClientRect();
        const top = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
        return {{which: '{which}', menuHidden: document.querySelector('#more-menu').classList.contains('hidden'),
                 rect: [r.x, r.y, r.width, r.height], vh: innerHeight, scrollY, onTop: top && (top.id || top.className || top.tagName)}}; }}""")
    print(info)
    br.close()
