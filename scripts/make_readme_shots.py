"""Regenerate the seven README walkthrough screenshots in docs/screenshots/
(web-01-drop ... web-07-export) from tests/fixtures/dark_divide_100, driving the
real app in headless Chromium at 1440x900.

Needs the dev server:  uv run python web/serve.py
Run:                   uv run python scripts/make_readme_shots.py
BASE_URL points it at another server (default http://127.0.0.1:8765).
Sibling of make_walkthrough_shots.py (web/walkthrough/*.webp, Bitterroots).
bypass_csp is fine here; CSP behaviour is checked separately (see tests/web).
"""
import os, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/dark_divide_100/caltopo/2027_Dark_Divide_100_Mile_Endurance_Run.json"
OUT = ROOT / "docs/screenshots"
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8765").rstrip("/")


def shot(page, name):
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("wrote", OUT / f"{name}.png")


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(bypass_csp=True, viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.goto(f"{BASE}/index.html")
        pg.wait_for_selector('body[data-engine="ready"]', state="attached", timeout=90000)
        shot(pg, "web-01-drop")

        pg.set_input_files("#file", str(FIXTURE))
        pg.wait_for_function("window.__cairnLoaded === true", timeout=60000)
        shot(pg, "web-02-loaded")

        pg.click("#only-attention")                      # the Default pin filter
        shot(pg, "web-03-default-pin-filter")

        pg.evaluate("document.activeElement && document.activeElement.blur()")
        pg.keyboard.press("ControlOrMeta+a")             # tick every shown row
        shot(pg, "web-04-selected-rows")

        pg.click("#bulk-icon")
        pg.fill("#mark-dialog .icon-search", "food")
        pg.locator("#mark-dialog .icon-pick[data-icon='Food Source']").click()
        shot(pg, "web-05-bulk-icon-picker")

        pg.click("#bulk-apply")
        pg.wait_for_timeout(600)
        pg.locator("#only-attention").uncheck()  # show the whole map again
        pg.evaluate("document.activeElement && document.activeElement.blur()")
        shot(pg, "web-06-after-bulk-edit")

        pg.click("#export")
        pg.wait_for_function("window.__cairnExported === true", timeout=120000)
        shot(pg, "web-07-export")
        b.close()


if __name__ == "__main__":
    main()
