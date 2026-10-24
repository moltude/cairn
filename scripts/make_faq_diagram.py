"""Render docs/faq/how-cairn-works.html to web/faq/how-cairn-works.webp, the
FAQ's "How Cairn bridges CalTopo and onX" diagram, at 2x.

    uv run --with pillow python scripts/make_faq_diagram.py

Headless Chromium opens the HTML from disk (it uses the app's own woff2 files
by relative path, hence --allow-file-access-from-files) and waits for the fonts.
"""
import io, pathlib
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/faq/how-cairn-works.html"
OUT = ROOT / "web/faq/how-cairn-works.webp"
W, H = 1600, 900


def main():
    OUT.parent.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        page.goto(SRC.as_uri())
        page.evaluate("document.fonts.ready")
        loaded = page.evaluate("[...document.fonts].filter(f => f.status === 'loaded').length")
        assert loaded == 3, f"{loaded} of 3 fonts loaded"
        png = page.locator(".canvas").screenshot()
        b.close()
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert im.size == (2 * W, 2 * H), im.size
    im.save(OUT, "WEBP", quality=80, method=6)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes, {im.size[0]}x{im.size[1]})")


if __name__ == "__main__":
    main()
