"""Accessibility fixes from docs/research/ACCESSIBILITY_AUDIT_2026-10-25.md (round 4,
track W). One or more tests per finding, named for what they check; the finding's id is
in each docstring. Measured the way the audit measured (its section 5): contrast from
computed colours composited over the first opaque background, focus against the sticky
bars by sampling points, names and roles from the accessibility tree.

Held for the owner, so not tested here: A11Y-10 (swatch focus vs selection), A11Y-16
(the After highlight), A11Y-18 (roving tabindex), A11Y-21 (the chips row on contours)."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.bulk_rename_vectors import item_map
from tests.web.helpers import (
    BASE_URL, FIXTURE, ROW, _load_text, _menu_action, _open_bulk, _set, _set_mode, _tick,
    _type_spec,
)

# --- helpers ----------------------------------------------------------------------------

# WCAG contrast of an element's text (or a pseudo-element's, e.g. "::placeholder"): its
# colour times the opacity of it and its ancestors, over the first opaque background up
# the tree (lighter layers composited on it), as the audit measured (section 5).
_CONTRAST_JS = """([el, pseudo]) => {
  const rgba = c => { const p = c.match(/[\\d.]+/g).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const over = (top, bot) => [0, 1, 2].map(i => top[i] * top[3] + bot[i] * (1 - top[3])).concat(1);
  let fg = rgba(getComputedStyle(el, pseudo || null).color);
  let op = 1;
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) op *= Number(getComputedStyle(n).opacity);
  fg = [fg[0], fg[1], fg[2], fg[3] * op];
  const layers = [];
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    const b = rgba(getComputedStyle(n).backgroundColor);
    if (b[3] > 0) layers.push(b);
    if (b[3] >= 1) break;
  }
  let bg = [255, 255, 255, 1];
  for (const l of layers.reverse()) bg = over(l, bg);
  const text = over(fg, bg);
  const lum = c => { const v = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const [a, b] = [lum(text), lum(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}"""


def _contrast(loc, pseudo: str = "") -> float:
    return loc.evaluate(f"(el, pseudo) => ({_CONTRAST_JS})([el, pseudo])", pseudo)


# The contrast of two :root tokens (a ring against a background).
_TOKEN_RATIO_JS = """([a, b]) => {
  const s = getComputedStyle(document.documentElement);
  const hex = t => { const h = s.getPropertyValue(t).trim().slice(1); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };
  const lum = c => { const v = c.map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const [x, y] = [lum(hex(a)), lum(hex(b))].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}"""


def _map(page: Page, rows, folder: str = "Trip") -> None:
    """A small CalTopo map (tests.bulk_rename_vectors.item_map rows: (kind, name, note))."""
    _load_text(page, item_map(rows, folder), "a11y.json")
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)


def _uid(page: Page, name: str) -> str:
    return page.evaluate("n => allItems().find(i => i.name === n).uid", name)


def _wide(page: Page) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})


@pytest.fixture()
def page_on(context):
    """Open a static page of the site (faq.html, walkthrough.html) at 1440x900."""
    pages = []

    def go(path: str) -> Page:
        p = context.new_page()
        p.set_viewport_size({"width": 1440, "height": 900})
        p.goto(f"{BASE_URL}/{path}")
        pages.append(p)
        return p
    yield go
    for p in pages:
        p.close()


# --- A11Y-09: the More menu's keyboard focus ---------------------------------------------


def test_more_menu_items_show_the_focus_ring_on_keyboard_focus(loaded: Page):
    """A11Y-09: keyboard focus on a More item draws the global 2px --link ring inside it,
    not only the 1.15:1 tint."""
    page = loaded
    page.locator(f"{ROW} .sel-box").first.check()
    page.locator("#more-btn").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#more-menu")).to_be_visible()
    page.keyboard.press("ArrowDown")
    item = page.locator("#bulk-rename")
    expect(item).to_be_focused()
    style = item.evaluate("e => { const s = getComputedStyle(e); return [s.outlineStyle, s.outlineWidth, s.outlineOffset, s.outlineColor]; }")
    assert style[:3] == ["solid", "2px", "-2px"], style
    link = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--link').trim()")
    assert style[3] == "rgb(122, 78, 37)" and link.upper() == "#7A4E25", (style, link)
    assert page.evaluate(f"({_TOKEN_RATIO_JS})(['--link', '--sheet'])") >= 3
    # Hover (an item without focus) keeps its tint and draws no ring.
    hovered = page.locator("#bulk-desc")
    hovered.hover()
    assert hovered.evaluate("e => [getComputedStyle(e).outlineStyle, getComputedStyle(e).backgroundColor]") == [
        "none", "rgb(233, 239, 223)"]


# --- A11Y-13: the "Untitled" placeholder -------------------------------------------------


def test_untitled_placeholder_meets_text_contrast_on_every_row_background(fresh_page: Page):
    """A11Y-13: the name field's "Untitled" is --muted, italic, at least 4.5:1 on a plain,
    a ticked and a hovered row."""
    page = fresh_page
    _map(page, [("w", "", ""), ("w", "Named", "")])
    blank = page.locator(f"{ROW} .name-in").first
    expect(blank).to_have_attribute("placeholder", "Untitled")
    style = blank.evaluate("e => { const s = getComputedStyle(e, '::placeholder'); return [s.color, s.fontStyle, s.opacity]; }")
    assert style == ["rgb(92, 82, 66)", "italic", "1"], style
    page.mouse.move(0, 0)
    assert _contrast(blank, "::placeholder") >= 4.5
    page.locator(f"{ROW} .sel-box").first.check()
    assert _contrast(blank, "::placeholder") >= 4.5
    page.locator(f"{ROW} .sel-box").first.uncheck()
    page.locator(f"{ROW} .note-btn").first.hover()
    assert _contrast(blank, "::placeholder") >= 4.5


# --- A11Y-14: excluded rows --------------------------------------------------------------


def test_an_excluded_rows_words_keep_text_contrast_and_only_its_marks_fade(loaded: Page):
    """A11Y-14: an excluded row's note, icon name and Default pin are --muted (not 55%
    opacity), at least 4.5:1; the marker and the line swatch keep the fade."""
    page = loaded
    page.mouse.move(0, 0)
    noted = page.evaluate("allItems().find(i => i.kind === 'waypoints' && i.desc && !i.needs_attention).uid")
    pin = page.evaluate("allItems().find(i => i.kind === 'waypoints' && i.needs_attention).uid")
    blank = page.evaluate("allItems().find(i => i.kind === 'waypoints' && !i.desc).uid")
    line = page.evaluate("allItems().find(i => i.kind === 'tracks').uid")
    for u in (noted, pin, blank, line):
        _set(page, u, included=False)
    for u, sel in ((noted, ".note-text"), (noted, ".icon-name"), (pin, ".whymark"), (line, ".icon-name")):
        loc = page.locator(f'tr[data-uid="{u}"] {sel}')
        assert loc.evaluate("e => getComputedStyle(e).color") == "rgb(92, 82, 66)", (u, sel)
        assert _contrast(loc) >= 4.5, (u, sel, _contrast(loc))
    # "Add a note" shows on hover; it is --muted too.
    page.locator(f'tr[data-uid="{blank}"] .name-in').hover()
    assert _contrast(page.locator(f'tr[data-uid="{blank}"] .note-text')) >= 4.5
    for u, sel in ((noted, ".icon-btn"), (noted, ".note-btn"), (line, ".line-btn")):
        assert page.locator(f'tr[data-uid="{u}"] {sel}').evaluate("e => getComputedStyle(e).opacity") == "1"
    assert page.locator(f'tr[data-uid="{noted}"] .marker').evaluate("e => getComputedStyle(e).opacity") == "0.55"
    assert page.locator(f'tr[data-uid="{line}"] .lineswatch').evaluate("e => getComputedStyle(e).opacity") == "0.55"
    # An included row is untouched.
    _set(page, noted, included=True)
    assert page.locator(f'tr[data-uid="{noted}"] .marker').evaluate("e => getComputedStyle(e).opacity") == "1"
    assert page.locator(f'tr[data-uid="{noted}"] .note-text').evaluate("e => getComputedStyle(e).color") == "rgb(42, 36, 28)"


# --- A11Y-15: the popover at 200% zoom ---------------------------------------------------


@pytest.fixture()
def zoomed_page(browser):
    """1440x900 at 200%: a 720x450 CSS-pixel viewport at device scale 2."""
    ctx = browser.new_context(bypass_csp=True, viewport={"width": 720, "height": 450}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(f"{BASE_URL}/index.html")
    page.wait_for_function("window.__cairnReady === true", timeout=60000)
    yield page
    ctx.close()


def test_at_200_percent_the_popovers_footer_never_covers_the_icon_list(zoomed_page: Page):
    """A11Y-15: the icon section clips and scrolls its own list; nothing of it is drawn
    under Cancel and Save, which stay inside the window."""
    page = zoomed_page
    page.set_input_files("#file", str(FIXTURE))
    page.wait_for_function("window.__cairnLoaded === true", timeout=30000)
    page.locator(f"{ROW} .icon-btn").first.click()
    pop = page.locator("#mark-pop")
    expect(pop).to_be_visible()
    geo = page.evaluate("""() => {
      const r = e => e.getBoundingClientRect();
      const sec = document.querySelector('#mark-pop .pop-sec.icons'), foot = document.querySelector('#mark-pop .pop-foot');
      return { sec: [r(sec).top, r(sec).bottom], foot: [r(foot).top, r(foot).bottom], vh: innerHeight,
               overflow: getComputedStyle(sec).overflow,
               save: document.elementFromPoint(r(document.querySelector('#pop-apply')).left + 8, r(document.querySelector('#pop-apply')).top + 8).id }; }""")
    assert geo["overflow"] == "hidden"
    assert geo["sec"][1] <= geo["foot"][0] + 0.5, geo           # the section ends where the footer starts
    assert geo["foot"][1] <= geo["vh"] and geo["save"] == "pop-apply", geo
    # Every icon pick inside the section's box is clipped to it: none is painted on the footer.
    painted_over = page.evaluate("""() => {
      const f = document.querySelector('#mark-pop .pop-foot').getBoundingClientRect();
      const hit = document.elementFromPoint(f.left + f.width / 2, f.top + 4);
      return !!hit.closest('.icon-pick'); }""")
    assert not painted_over
    # The list still scrolls to its last icon.
    grid = page.locator("#mark-pop .icon-grid")
    assert grid.evaluate("g => g.scrollHeight > g.clientHeight")


def test_at_100_percent_the_popover_does_not_scroll(loaded: Page):
    """A11Y-15: no change at 100%: the popover fits, so it has nothing to scroll."""
    page = loaded
    _wide(page)
    page.locator(f"{ROW} .icon-btn").first.click()
    pop = page.locator("#mark-pop")
    expect(pop).to_be_visible()
    assert pop.evaluate("p => p.scrollHeight <= p.clientHeight")
    assert page.locator("#mark-pop .icon-grid").evaluate("g => g.getBoundingClientRect().height") >= 260


# --- A11Y-19: target sizes ---------------------------------------------------------------


def test_an_empty_folders_remove_button_is_a_24px_target(loaded: Page):
    """A11Y-19: the × on an empty folder is 24 by 24."""
    page = loaded
    page.locator(".new-folder").click()
    page.keyboard.press("Enter")
    x = page.locator("#folder-facets .facet-x")
    expect(x).to_have_count(1)
    box = x.bounding_box()
    assert box["width"] >= 24 and box["height"] >= 24, box


def test_faq_group_links_are_24px_targets(page_on):
    """A11Y-19: the FAQ's group links ("The problem", …) are at least 24px tall."""
    page = page_on("faq.html")
    heights = page.locator(".doc-toc .toc-sec").evaluate_all("els => els.map(e => e.getBoundingClientRect().height)")
    assert heights and min(heights) >= 24, heights


# --- A11Y-20: the FAQ's # anchors and "here now" -----------------------------------------


def test_faq_question_anchors_meet_text_contrast(page_on):
    """A11Y-20: the # before each FAQ question is --muted, at least 4.5:1 on paper."""
    page = page_on("faq.html")
    page.mouse.move(0, 0)
    anchor = page.locator(".faq-q .anchor").first
    assert anchor.evaluate("e => getComputedStyle(e).color") == "rgb(92, 82, 66)"
    assert _contrast(anchor) >= 4.5


def test_here_now_during_a_drag_meets_text_contrast(loaded: Page):
    """A11Y-20: "here now" on the dragged rows' own folder is --muted (italic), at least
    4.5:1 on the rail."""
    page = loaded
    _wide(page)
    row = page.locator(f"{ROW}").first
    src = row.locator(".note-btn")
    b = src.bounding_box()
    page.mouse.move(b["x"] + 20, b["y"] + b["height"] / 2)
    page.mouse.down()
    page.mouse.move(b["x"] + 40, b["y"] + 30, steps=4)
    here = page.locator("#folder-facets .facet-btn.here-now")
    expect(here).to_have_count(1)
    count = here.locator(".facet-count")
    expect(count).to_have_text("here now")
    assert count.evaluate("e => [getComputedStyle(e).color, getComputedStyle(e).fontStyle]") == ["rgb(92, 82, 66)", "italic"]
    assert _contrast(count) >= 4.5 and _contrast(here.locator(".facet-name")) >= 4.5
    page.keyboard.press("Escape")
    page.mouse.up()


# --- A11Y-29: the walkthrough's landing shot ---------------------------------------------


def test_walkthrough_landing_shot_alt_says_what_the_picture_shows(page_on):
    """A11Y-29: the landing screenshot has a heading, a paragraph and the drop zone; its
    alt no longer promises three steps."""
    page = page_on("walkthrough.html")
    alt = page.locator('img[src="walkthrough/01-landing.webp"]').get_attribute("alt")
    assert alt == "Cairn's landing page: what it does, and a drop zone for a CalTopo export"
