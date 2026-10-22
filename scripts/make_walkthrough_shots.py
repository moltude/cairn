"""Regenerate web/walkthrough/*.webp and walkthrough_numbers.json from the real
Bitterroots fixture, driving the real app in headless Chromium at 1440x900.

Needs the dev server:  uv run python web/serve.py
Run:                   uv run --with pillow python scripts/make_walkthrough_shots.py
bypass_csp is fine here; CSP behaviour is checked separately (see tests/web).
"""
import io, json, pathlib
from collections import Counter
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/bitterroots/Bitterroots__Complete_.json"
OUT = ROOT / "web/walkthrough"
BASE = "http://127.0.0.1:8765"

def save(page, name):
    png = page.screenshot()
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im.save(OUT / f"{name}.webp", "WEBP", quality=82, method=6)

def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(bypass_csp=True, viewport={"width": 1440, "height": 900}).new_page()
        pg.goto(f"{BASE}/index.html")
        pg.wait_for_function("window.__cairnReady === true", timeout=90000)
        pg.wait_for_timeout(400)
        save(pg, "01-landing")

        pg.set_input_files("#file", str(FIXTURE))
        pg.wait_for_function("window.__cairnLoaded === true", timeout=60000)
        pg.wait_for_timeout(600)
        d = pg.evaluate("DATA")
        items = [i for g in d["groups"] for i in g["items"]]
        wp = [i for i in items if i["kind"] == "waypoints"]
        nums = {
            "folders": len(d["groups"]),
            "items": len(items),
            "waypoints": len(wp),
            "lines": sum(i["kind"] == "tracks" for i in items),
            "areas": sum(i["kind"] == "shapes" for i in items),
            "default_pins": sum(i["needs_attention"] for i in wp),
            "specific_icons": sum(not i["needs_attention"] for i in wp),
            "distinct_icons": len({i["icon"] for i in wp}),
            "distinct_caltopo_symbols": len({i["symbol"] for i in wp}),
            "default_pin_by_symbol": dict(Counter(i["symbol"] for i in wp if i["needs_attention"])),
            "top_icons": Counter(i["icon"] for i in wp).most_common(6),
        }
        save(pg, "02-loaded")

        pg.click("#only-attention")
        pg.wait_for_timeout(500)
        save(pg, "03-default-pins")

        pg.locator(".folder tbody tr .icon-btn").first.click()
        pg.wait_for_timeout(500)
        save(pg, "04-popover")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        if pg.locator("#mark-pop:not(.hidden)").count():
            pg.click("#mark-pop .pop-cancel")

        pg.fill("#filter", "Sheafman")
        pg.wait_for_timeout(400)
        pg.evaluate("document.activeElement && document.activeElement.blur()")
        pg.keyboard.press("ControlOrMeta+a")
        pg.wait_for_timeout(400)
        pg.click("#bulk-icon")
        pg.wait_for_timeout(400)
        pg.fill("#mark-dialog .icon-search", "summit")
        pg.wait_for_timeout(300)
        pg.locator("#mark-dialog .icon-pick[data-icon='Summit']").click()
        pg.wait_for_timeout(400)
        save(pg, "05-bulk-dialog")
        pg.click("#bulk-apply")
        pg.wait_for_timeout(600)
        d2 = pg.evaluate("DATA")
        nums["default_pins_after_demo_edit"] = sum(
            i["needs_attention"] for g in d2["groups"] for i in g["items"] if i["kind"] == "waypoints")

        pg.click("#export")
        pg.wait_for_function("window.__cairnExported === true", timeout=120000)
        pg.wait_for_timeout(600)
        save(pg, "06-export")
        (OUT / "numbers.json").write_text(json.dumps(nums, indent=1))
        print(json.dumps(nums, indent=1))
        b.close()

if __name__ == "__main__":
    main()
