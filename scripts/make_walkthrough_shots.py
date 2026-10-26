"""Regenerate web/walkthrough/*.webp and walkthrough_numbers.json from the real
Bitterroots fixture, driving the real app in headless Chromium at 1440x900.

Needs the dev server:  uv run python web/serve.py
Run:                   uv run --with pillow python scripts/make_walkthrough_shots.py
BASE_URL points it at another server (default http://127.0.0.1:8765); SHOTS_PNG, if
set, is a directory that also gets each shot as a PNG, to look at.
bypass_csp is fine here; CSP behaviour is checked separately (see tests/web).
"""
import io, json, os, pathlib
from collections import Counter
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/bitterroots/Bitterroots__Complete_.json"
OUT = ROOT / "web/walkthrough"
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8765").rstrip("/")
PNG_DIR = os.environ.get("SHOTS_PNG")

def save(page, name):
    png = page.screenshot()
    if PNG_DIR:
        pathlib.Path(PNG_DIR, f"{name}.png").write_bytes(png)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im.save(OUT / f"{name}.webp", "WEBP", quality=82, method=6)

def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(bypass_csp=True, viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.goto(f"{BASE}/index.html")
        pg.wait_for_selector('body[data-engine="ready"]', state="attached", timeout=90000)
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
        # A name is required to export (N1, 2026-10-25): Bitterroots' 7 nameless
        # items are named "Untitled" in the confirm that asks first.
        if pg.locator("#confirm").is_visible():
            pg.click("#confirm-actions button:text-is('Name them Untitled')")
        pg.wait_for_function("window.__cairnExported === true", timeout=120000)
        pg.wait_for_timeout(600)
        save(pg, "08-export")

        # Folders, on a fresh load (the export above keeps the map's 10):
        # tick the six Sheafman rows and drag them onto + New folder.
        pg = ctx.new_page()
        pg.goto(f"{BASE}/index.html")
        pg.wait_for_selector('body[data-engine="ready"]', state="attached", timeout=90000)
        pg.set_input_files("#file", str(FIXTURE))
        pg.wait_for_function("window.__cairnLoaded === true", timeout=60000)
        pg.fill("#filter", "Sheafman")
        pg.wait_for_timeout(400)
        pg.evaluate("document.activeElement && document.activeElement.blur()")
        pg.keyboard.press("ControlOrMeta+a")
        pg.wait_for_timeout(300)
        src = pg.locator(".folder tbody tr .name-in").first.bounding_box()
        dst = pg.locator("#folder-facets .new-folder").bounding_box()
        x, y = src["x"] + 20, src["y"] + src["height"] / 2
        pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x + 10, y + 10, steps=3)
        pg.mouse.move(dst["x"] + dst["width"] / 2, dst["y"] + dst["height"] / 2, steps=8)
        pg.wait_for_timeout(300)
        save(pg, "06-folders-drag")
        pg.mouse.up()
        pg.wait_for_timeout(300)
        pg.keyboard.press("ControlOrMeta+a")
        pg.keyboard.type("Sheafman day trip")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(500)
        nums["new_folder_items"] = len(pg.evaluate(
            "DATA.groups.find(g => g.name === 'Sheafman day trip').items"))
        save(pg, "07-folders-named")
        (OUT / "numbers.json").write_text(json.dumps(nums, indent=1))
        print(json.dumps(nums, indent=1))
        b.close()

if __name__ == "__main__":
    main()
