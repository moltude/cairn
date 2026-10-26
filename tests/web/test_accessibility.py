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


# --- shared: one node of the accessibility tree ------------------------------------------


def _ax(page: Page, selector: str) -> dict:
    """Role, name and description of the first element matching selector, from Chrome's
    accessibility tree (CDP)."""
    cdp = page.context.new_cdp_session(page)
    try:
        root = cdp.send("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
        nid = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})["nodeId"]
        node = cdp.send("Accessibility.getPartialAXTree", {"nodeId": nid, "fetchRelatives": False})["nodes"][0]
    finally:
        cdp.detach()
    val = lambda k: (node.get(k) or {}).get("value", "")   # noqa: E731
    return {"role": val("role"), "name": val("name"), "description": val("description")}


SMALL = [("w", "Camp", "Water here\nsecond line"), ("w", "Lake", ""), ("l", "Trail", ""), ("a", "Zone", "")]


def _select_all(page: Page) -> None:
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.keyboard.press("ControlOrMeta+a")
    expect(page.locator("#selbar")).to_be_visible()


# --- A11Y-03: the Icon & color… dialog's Now → After, in words ---------------------------


def test_icon_and_color_dialog_rows_say_now_and_after_in_hidden_words(fresh_page: Page):
    """A11Y-03: each Now → After row carries hidden words for its two marks ("Now Camp,
    Red. After Summit, Blue."; a line "Line, Blue, Solid, Thin"), updated as choices are
    picked; the drawing and its three grid cells per row are unchanged."""
    page = fresh_page
    _map(page, SMALL)
    _select_all(page)
    page.click("#bulk-icon")
    words = page.locator("#mark-dialog .na-rows .sr-only")
    expect(words).to_have_text([
        ". Now Camp, Red. After Camp, Red.", ". Now Camp, Red. After Camp, Red.",
        ". Now Line, Blue, Solid, Thin. After Line, Blue, Solid, Thin.",
        ". Now Area, Red, Solid, Thin. After Area, Red, Solid, Thin."])
    pin = page.get_by_role("group", name="Waypoint color")
    pin.get_by_role("button", name="Blue", exact=True).click()
    page.locator('#mark-dialog .icon-pick[data-icon="Summit"]').click()
    line = page.get_by_role("group", name="Line color")
    line.get_by_role("button", name="Purple", exact=True).click()
    page.get_by_role("group", name="Style").get_by_role("button", name="Dashed").click()
    page.get_by_role("group", name="Weight").get_by_role("button", name="Thick").click()
    expect(words).to_have_text([
        ". Now Camp, Red. After Summit, Blue.", ". Now Camp, Red. After Summit, Blue.",
        ". Now Line, Blue, Solid, Thin. After Line, Purple, Dashed, Thick.",
        ". Now Area, Red, Solid, Thin. After Area, Purple, Dashed, Thick."])
    # Visually hidden, inside the first cell: still three grid cells per row.
    assert page.locator("#mark-dialog .na-rows > *").count() == 3 * 4
    assert words.first.evaluate("e => [getComputedStyle(e).position, e.getBoundingClientRect().width]") == ["absolute", 1]
    snap = page.locator("#mark-dialog .now-after").aria_snapshot()
    assert "Camp . Now Camp, Red. After Summit, Blue." in snap, snap


def test_default_pin_rows_say_default_pin(loaded: Page):
    """A11Y-03: a waypoint on onX's default pin reads "Default pin", as its row does."""
    page = loaded
    uid = page.evaluate("allItems().find(i => i.needs_attention).uid")
    _tick(page, [uid])
    page.click("#bulk-icon")
    expect(page.locator("#mark-dialog .na-rows .sr-only")).to_have_text(
        re.compile(r"^\. Now Default pin, [\w-]+\. After Default pin, [\w-]+\.$"))


# --- A11Y-05 (verified, fixed before this round): nameless rows --------------------------


def test_a_nameless_rows_controls_are_all_named_untitled(fresh_page: Page):
    """A11Y-05: no control on a nameless row has a name that ends where the item's name
    should be ("Select ", "Open note for ")."""
    page = fresh_page
    _map(page, [("w", "", "a note"), ("l", "", "")])
    names = page.locator(f"{ROW} [aria-label]").evaluate_all("els => els.map(e => e.getAttribute('aria-label'))")
    assert names and not [n for n in names if n != n.strip() or re.search(r"\b(for|Select|of|Include)$", n)], names
    assert "Select Untitled" in names and "Name of Untitled" in names
    assert "a note, note for Untitled" in names and "Add a note for Untitled" in names


# --- A11Y-06: the Rename… and Change note… preview --------------------------------------


def test_rename_preview_is_a_list_read_as_now_and_after(fresh_page: Page):
    """A11Y-06: the rows are a list; each reads "Now X, after Y" (an unchanged row "Now X,
    No change") in hidden words where the arrow is drawn; the cells keep their text."""
    page = fresh_page
    _map(page, [("w", "Camp", ""), ("w", "Lake", "")])
    _select_all(page)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    _type_spec(page, find="Camp", repl="Base")
    rows = page.locator("#mark-dialog .na-rows")
    assert rows.get_attribute("role") == "list"
    assert page.locator('#mark-dialog .na-row[role="listitem"]').count() == 2
    snap = rows.aria_snapshot()
    assert re.search(r"listitem: Now Camp ?, after Base", snap) and re.search(r"listitem: Now Lake ?, No change", snap), snap
    # The cells themselves hold only the values (what the tests and the eye read).
    assert page.locator("#mark-dialog .na-row .na-before").all_text_contents() == ["Camp", "Lake"]
    assert page.locator("#mark-dialog .na-row .na-after").first.text_content() == "Base"
    # The hidden words don't take a grid cell: the After value is still in column 3.
    geo = page.locator("#mark-dialog .na-row").first.evaluate("""r => {
      const x = s => r.querySelector(s).getBoundingClientRect().left;
      return [x('.na-before'), x(':scope > svg'), x('.na-after')]; }""")
    assert geo[0] < geo[1] < geo[2], geo


def test_change_note_preview_says_whose_note_each_row_is(fresh_page: Page):
    """A11Y-06: a note's row reads "Note for Camp, now <note>, after <note>"."""
    page = fresh_page
    _map(page, [("w", "Camp", "old"), ("w", "Lake", "")])
    _select_all(page)
    _open_bulk(page, "note")
    _type_spec(page, text="new")
    snap = page.locator("#mark-dialog .na-rows").aria_snapshot()
    assert re.search(r"listitem: Note for Camp ?, now old ?, after new old", snap), snap
    assert re.search(r"listitem: Note for Lake ?, now ?, after new", snap), snap
    expect(page.locator("#mark-dialog .na-src .na-name")).to_have_text(["Camp", "Lake"])


def test_a_long_preview_ends_with_and_n_more_as_a_list_item(fresh_page: Page):
    """A11Y-06: "and N more" under a cut list is an item of that list, so the list holds
    only items."""
    page = fresh_page
    _map(page, [("w", f"P{k}", "") for k in range(203)])
    _select_all(page)
    _open_bulk(page, "rename")
    _type_spec(page, text="x")
    more = page.locator("#mark-dialog .na-rows > .na-more")
    expect(more).to_have_text("and 3 more")
    assert more.get_attribute("role") == "listitem"
    assert page.locator("#mark-dialog .na-rows > :not([role=listitem])").count() == 0


# --- A11Y-07: each row of the popover and the dialog is a named group --------------------


def test_an_areas_popover_tells_its_two_blues_apart(fresh_page: Page):
    """A11Y-07: the area popover's Color and Fill rows are groups named by their labels,
    so each of its two "Blue" buttons is in a named group."""
    page = fresh_page
    _map(page, SMALL)
    page.locator(f'tr[data-uid="{_uid(page, "Zone")}"] .line-btn').click()
    pop = page.locator("#mark-pop")
    for g in ("Color", "Style", "Weight", "Fill"):
        expect(pop.get_by_role("group", name=g, exact=True)).to_have_count(1)
    expect(pop.get_by_role("group", name="Color", exact=True).get_by_role("button", name="Blue", exact=True)).to_have_count(1)
    expect(pop.get_by_role("group", name="Fill", exact=True).get_by_role("button", name="Blue", exact=True)).to_have_count(1)


def test_every_leave_as_is_in_a_mixed_dialog_is_in_a_named_group(fresh_page: Page):
    """A11Y-07: in a mixed Icon & color… dialog each "Leave as is" sits in the group of its
    row: Waypoint color, Icon, Line color, Style, Weight, Fill."""
    page = fresh_page
    _map(page, SMALL)
    _select_all(page)
    page.click("#bulk-icon")
    d = page.locator("#mark-dialog")
    rows = ["Waypoint color", "Icon", "Line color", "Style", "Weight", "Fill"]
    for g in rows:
        expect(d.get_by_role("group", name=g, exact=True).get_by_role("button", name="Leave as is")).to_have_count(1)
    expect(d.get_by_role("button", name="Leave as is")).to_have_count(len(rows))
    # Unique ids: every label a group points at exists once.
    ids = d.locator("[aria-labelledby]").evaluate_all("els => els.map(e => e.getAttribute('aria-labelledby'))")
    assert len(ids) == len(set(ids)) and all(page.locator(f"#{i}").count() == 1 for i in ids)


def test_rename_modes_are_a_group_named_change(fresh_page: Page):
    """A11Y-07: the mode toggles of Rename… are a group, "Change"."""
    page = fresh_page
    _map(page, [("w", "Camp", "")])
    _select_all(page)
    _open_bulk(page, "rename")
    grp = page.locator("#mark-dialog").get_by_role("group", name="Change", exact=True)
    expect(grp.get_by_role("button")).to_have_text(["Add before", "Add after", "Find and replace"])


# --- A11Y-08: Tab stays in the single-item popover ---------------------------------------


def test_tab_and_shift_tab_stay_inside_the_single_item_popover(loaded: Page):
    """A11Y-08: Shift+Tab from the popover's first control goes to its last (Save), Tab
    from Save to the first; it never leaves for the list while the popover is open."""
    page = loaded
    page.locator(f"{ROW} .icon-btn").first.click()
    pop = page.locator("#mark-pop")
    expect(pop).to_be_visible()
    first = pop.locator(".swatch-btn").first
    first.focus()
    page.keyboard.press("Shift+Tab")
    expect(page.locator("#pop-apply")).to_be_focused()
    page.keyboard.press("Tab")
    expect(first).to_be_focused()
    for _ in range(30):
        page.keyboard.press("Shift+Tab")
        assert page.evaluate("document.querySelector('#mark-pop').contains(document.activeElement)")
    expect(pop).to_be_visible()


# --- A11Y-11: the note button's name starts with its words -------------------------------


def test_a_note_buttons_name_starts_with_the_words_it_shows(fresh_page: Page):
    """A11Y-11: "Water here, note for Camp" (the first line, then whose); a missing note
    "Add a note for Lake"."""
    page = fresh_page
    _map(page, SMALL)
    camp = page.locator(f'tr[data-uid="{_uid(page, "Camp")}"]')
    expect(camp.get_by_role("button", name="Water here, note for Camp", exact=True)).to_have_count(1)
    expect(camp.locator(".note-text")).to_have_text("Water here")
    lake = page.locator(f'tr[data-uid="{_uid(page, "Lake")}"]')
    expect(lake.get_by_role("button", name="Add a note for Lake", exact=True)).to_have_count(1)


# --- A11Y-12: why a marker is what it is, on keyboard focus too --------------------------


def test_a_markers_why_shows_in_the_styled_tip_on_keyboard_focus(loaded: Page):
    """A11Y-12: Tab onto a marker shows its "why" in the styled tip (no native title, so
    no second tooltip); screen readers get it as the marker's description."""
    page = loaded
    _wide(page)
    page.mouse.move(0, 0)
    it = page.evaluate("(() => { const i = allItems().find(i => i.kind === 'waypoints' && i.needs_attention); return {uid: i.uid, why: i.why}; })()")
    row = page.locator(f'tr[data-uid="{it["uid"]}"]')
    row.locator(".note-btn").focus()
    page.keyboard.press("Tab")
    btn = row.locator(".icon-btn")
    expect(btn).to_be_focused()
    tip = page.locator("#tip")
    expect(tip).to_be_visible()
    expect(tip).to_have_text(it["why"])
    expect(btn).to_have_attribute("aria-describedby", "tip")
    assert page.locator(".icon-btn[title], .line-btn[title], .whymark[title]").count() == 0
    assert _ax(page, f'tr[data-uid="{it["uid"]}"] .icon-btn')["description"] == it["why"]
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()


def test_a_lines_tip_names_its_colour_and_why(fresh_page: Page):
    """A11Y-12: a line's tip (and description) is "{Color} — {why}", the old title's words."""
    page = fresh_page
    _map(page, SMALL)
    sel = f'tr[data-uid="{_uid(page, "Trail")}"] .line-btn'
    page.locator(sel).hover()
    expect(page.locator("#tip")).to_have_text(re.compile(r"^Blue — .+"))
    assert _ax(page, sel)["description"].startswith("Blue — ")


def test_help_says_hover_or_focus_a_marker(loaded: Page):
    """A11Y-12: Help's line reads "Hover or focus a marker to see why"."""
    expect(loaded.locator("#help .help-body")).to_contain_text("Hover or focus a marker to see why.")


# --- A11Y-17: Tab leaves the More menu ---------------------------------------------------


def test_tab_closes_the_more_menu_and_goes_on_from_more(loaded: Page):
    """A11Y-17: the items aren't Tab stops; Tab closes the menu and goes on to Clear,
    Shift+Tab to Icon & color…; the arrows still move between items."""
    page = loaded
    page.locator(f"{ROW} .sel-box").first.check()
    items = page.locator("#more-menu [role=menuitem]")
    assert set(items.evaluate_all("els => els.map(e => e.getAttribute('tabindex'))")) == {"-1"}
    more = page.locator("#more-btn")
    more.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#bulk-move")).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(page.locator("#bulk-rename")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#more-menu")).to_be_hidden()
    expect(more).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#clear-sel")).to_be_focused()
    more.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#bulk-move")).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(page.locator("#more-menu")).to_be_hidden()
    expect(page.locator("#bulk-icon")).to_be_focused()


# --- A11Y-25: Exclude, Include and Use note as name leave a receipt ----------------------


def test_exclude_include_and_use_note_as_name_leave_a_receipt(fresh_page: Page):
    """A11Y-25: "Excluded 2 items.", "Included 2 items.", "Renamed 1 item from their
    notes." (a row whose note is blank is left alone and not counted)."""
    page = fresh_page
    _map(page, [("w", "A", "North camp"), ("w", "B", "")])
    _tick(page, [_uid(page, "A"), _uid(page, "B")])
    st = page.locator("#status")
    _menu_action(page, "#bulk-exclude")
    expect(st).to_have_text("Excluded 2 items.")
    _menu_action(page, "#bulk-include")
    expect(st).to_have_text("Included 2 items.")
    _menu_action(page, "#bulk-desc")
    expect(st).to_have_text("Renamed 1 item from their notes.")
    # Nothing left to rename: no receipt.
    page.evaluate("setStatus('')")
    _menu_action(page, "#bulk-desc")
    expect(st).to_have_text("")


# --- A11Y-26: the Name column header -----------------------------------------------------


def test_name_column_header_is_named_name_and_keeps_its_sort_state(loaded: Page):
    """A11Y-26: the header and its sort button are named "Name", not "Sort X by name";
    the order is the header's aria-sort."""
    page = loaded
    n = page.locator("section.folder").count()
    expect(page.get_by_role("columnheader", name="Name", exact=True)).to_have_count(n)
    expect(page.get_by_role("button", name=re.compile(r"^Sort "))).to_have_count(0)
    th = page.locator("th.name-th").first
    th.get_by_role("button", name="Name", exact=True).click()
    expect(th).to_have_attribute("aria-sort", "ascending")


# --- A11Y-27: the rail's filter sections are headings ------------------------------------


def test_rail_filter_sections_are_level_2_headings_that_look_unchanged(loaded: Page):
    """A11Y-27: Type, Folders and Icon are h2s around their fold buttons; the h2 adds no
    weight, size or margin (the labels stay 10px, regular)."""
    page = loaded
    for name in ("Type", "Folders", "Icon"):
        h = page.get_by_role("heading", name=name, level=2, exact=True)
        expect(h).to_have_count(1)
        expect(h.get_by_role("button", name=name, exact=True)).to_have_attribute("aria-expanded", "true")
    look = page.locator(".rail .sec-wrap").evaluate_all("""els => els.map(h => { const s = getComputedStyle(h), l = getComputedStyle(h.querySelector('.label'));
      return [s.fontWeight, s.fontSize, s.marginTop, s.marginBottom, l.fontWeight, l.fontSize,
              Math.round(h.getBoundingClientRect().height) === Math.round(h.querySelector('.sec-h').getBoundingClientRect().height)]; })""")
    assert look == [["400", "13px", "0px", "0px", "400", "10px", True]] * 3, look


# --- A11Y-28: one <main> not hidden ------------------------------------------------------


def test_only_the_screen_shown_is_free_of_the_hidden_attribute(fresh_page: Page):
    """A11Y-28: the two stages not shown carry the hidden attribute (HTML's rule for extra
    <main>s), on every stage."""
    page = fresh_page
    shown = lambda: page.evaluate("['drop', 'edit', 'done'].filter(s => !document.getElementById(s + '-stage').hidden)")   # noqa: E731
    assert shown() == ["drop"]
    _map(page, [("w", "Camp", "")])
    assert shown() == ["edit"]
    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done")
    assert shown() == ["done"]
    page.click("#back")
    assert shown() == ["edit"]


# --- A11Y-02: focus and the page title follow the screen ---------------------------------

LANDING_TITLE = "Cairn — CalTopo to onX"
FX = FIXTURE.parent.parent


def test_focus_moves_to_the_new_screens_heading_on_every_stage_change(fresh_page: Page):
    """A11Y-02: after a file load, Export, Back, the browser's Forward and Back, and Start
    over, focus is on the new screen's heading (not <body>), and the tab's title names the
    screen: "Cairn — Edit", "Cairn — Export", the landing page's own title again."""
    page = fresh_page
    expect(page).to_have_title(LANDING_TITLE)
    _map(page, [("w", "Camp", "")])
    expect(page.locator("#map-title")).to_be_focused()
    expect(page).to_have_title("Cairn — Edit")
    page.locator("#export").focus()
    page.keyboard.press("Enter")
    done_h1 = page.locator("#done-stage h1")
    expect(done_h1).to_be_focused()
    expect(page).to_have_title("Cairn — Export")
    page.locator("#back").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#map-title")).to_be_focused()
    expect(page).to_have_title("Cairn — Edit")
    page.go_forward()
    expect(done_h1).to_be_focused()
    expect(page).to_have_title("Cairn — Export")
    page.go_back()
    expect(page.locator("#map-title")).to_be_focused()
    page.locator("#edit-stage .newmap").focus()
    page.keyboard.press("Enter")
    page.click("#confirm-actions button:text-is('Start over')")
    expect(page.locator("#drop-stage h1")).to_be_focused()
    expect(page).to_have_title(LANDING_TITLE)


def test_a_focused_heading_draws_no_focus_ring(fresh_page: Page):
    """A11Y-02: the heading takes focus, not a control's look: no ring, even after a key."""
    page = fresh_page
    _map(page, [("w", "Camp", "")])
    page.locator("#export").focus()
    page.keyboard.press("Enter")
    h1 = page.locator("#done-stage h1")
    expect(h1).to_be_focused()
    assert h1.evaluate("e => getComputedStyle(e).outlineStyle") == "none"
    assert page.locator("#map-title").evaluate("e => getComputedStyle(e).outlineStyle") == "none"


def test_the_fill_warning_on_load_returns_focus_to_the_map_title(fresh_page: Page):
    """A11Y-02: a dialog that opens with the map (the area-fill warning) takes focus; closing
    it puts focus on the map's title, not the page."""
    page = fresh_page
    page.set_input_files("#file", [str(FX / "onx_exports" / "areas-after-edit.gpx"),
                                   str(FX / "onx_exports" / "areas-after-edit.kml")])
    expect(page.locator("#confirm")).to_be_visible(timeout=30000)
    page.keyboard.press("Escape")
    expect(page.locator("#confirm")).to_be_hidden()
    expect(page.locator("#map-title")).to_be_focused()


def test_focus_and_title_follow_the_screen_under_the_enforced_csp(csp_page: Page):
    """A11Y-02 under the production CSP (DOM waits only)."""
    page = csp_page
    page.set_input_files("#file", files=[{"name": "a11y.json", "mimeType": "application/json",
                                          "buffer": item_map([("w", "Camp", "")], "Trip").encode("utf-8")}])
    expect(page.locator("body")).to_have_attribute("data-stage", "edit", timeout=30000)
    expect(page.locator("#map-title")).to_be_focused()
    expect(page).to_have_title("Cairn — Edit")
    page.keyboard.press("Tab")
    expect(page.locator("#edit-stage .skip-link")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#filter")).to_be_focused()


# --- A11Y-22: skip links -----------------------------------------------------------------


def test_skip_to_the_list_is_the_first_tab_stop_after_the_map_title(fresh_page: Page):
    """A11Y-22: from the map title (where focus lands on load) Tab reaches "Skip to the
    list", shown only while focused; Enter goes to the search with no history entry."""
    page = fresh_page
    _wide(page)
    _map(page, [("w", "Camp", "")])
    link = page.locator("#edit-stage .skip-link")
    assert link.bounding_box()["width"] <= 1
    expect(link).to_have_text("Skip to the list")
    depth = page.evaluate("history.length")
    page.keyboard.press("Tab")
    expect(link).to_be_focused()
    box = link.bounding_box()
    assert box["width"] > 60 and box["height"] >= 24 and box["x"] >= 0 and box["y"] >= 0, box
    page.keyboard.press("Enter")
    expect(page.locator("#filter")).to_be_focused()
    assert page.evaluate("[history.length, location.hash]") == [depth, ""]
    assert link.bounding_box()["width"] <= 1


@pytest.mark.parametrize("path", ["faq.html", "walkthrough.html"])
def test_doc_pages_first_tab_stop_skips_to_the_content(page_on, path):
    """A11Y-22: on the FAQ and the walkthrough the first Tab stop is "Skip to the
    content"; Enter moves focus to the page's main content (no ring around it)."""
    page = page_on(path)
    page.keyboard.press("Tab")
    link = page.locator(".skip-link")
    expect(link).to_be_focused()
    expect(link).to_have_text("Skip to the content")
    assert link.bounding_box()["width"] > 60
    page.keyboard.press("Enter")
    main = page.locator("main#content")
    expect(main).to_be_focused()
    assert main.evaluate("e => getComputedStyle(e).outlineStyle") == "none"
    page.keyboard.press("Tab")
    assert page.evaluate("document.querySelector('main').contains(document.activeElement)")


# --- A11Y-04: result and selection counts, said politely ---------------------------------

SAID = 2000      # the region speaks 0.4 s after the last change; this is the wait's ceiling


def _said(page: Page):
    return page.locator("#count-live")


def _quiet_for(page: Page, ms: int = 700) -> None:
    """Empty the count region, wait past its delay, and check nothing was said."""
    page.wait_for_timeout(ms)
    expect(_said(page)).to_have_text("")


def test_search_and_filters_say_how_many_items_they_leave(loaded: Page):
    """A11Y-04: typing in the search, picking a type and clearing say "Showing N", or
    "Nothing matches these filters.", in a polite status region; loading a map and editing
    under a filter say nothing there."""
    page = loaded
    said = _said(page)
    assert said.get_attribute("role") == "status"
    _quiet_for(page)                                  # a map load says nothing
    page.locator("#filter").press_sequentially("water", delay=30)
    n = page.evaluate("shownItems().length")
    assert 0 < n < 177
    expect(said).to_have_text(f"Showing {n}", timeout=SAID)
    page.locator("#filter").fill("zzzz no such thing")
    expect(said).to_have_text("Nothing matches these filters.", timeout=SAID)
    page.locator("#filter").fill("")
    expect(said).to_have_text("Showing 177", timeout=SAID)
    page.click('#type-filter [data-kind="tracks"]')
    lines = page.evaluate("allItems().filter(i => i.kind === 'tracks').length")
    expect(said).to_have_text(f"Showing {lines}", timeout=SAID)
    # An edit redraws the list but changes no filter: nothing more is said.
    page.evaluate("document.querySelector('#count-live').textContent = ''")
    _set(page, page.evaluate("shownItems()[0].uid"), name="Renamed under a filter")
    _quiet_for(page)


def test_select_all_ranges_header_boxes_clear_and_esc_say_the_selection_count(loaded: Page):
    """A11Y-04: Ctrl / ⌘ + A, a shift range, a folder's header checkbox, Clear and Esc say
    "N selected"; ticking one row's own box (which says its state itself) says nothing."""
    page = loaded
    said = _said(page)
    _select_all(page)
    expect(said).to_have_text("177 selected", timeout=SAID)
    page.keyboard.press("ControlOrMeta+a")
    expect(said).to_have_text("0 selected", timeout=SAID)
    sec = page.locator("section.folder").first
    k = sec.locator("tbody tr").count()
    sec.locator(".folder-all").check()
    expect(said).to_have_text(f"{k} selected", timeout=SAID)
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("Escape")
    expect(said).to_have_text("0 selected", timeout=SAID)
    boxes = page.locator(f"{ROW} .sel-box")
    boxes.nth(0).click()
    boxes.nth(4).click(modifiers=["Shift"])
    expect(said).to_have_text("5 selected", timeout=SAID)
    page.click("#clear-sel")
    expect(said).to_have_text("0 selected", timeout=SAID)
    page.evaluate("document.querySelector('#count-live').textContent = ''")
    boxes.nth(2).check()
    _quiet_for(page)


# --- A11Y-24: the status line's words come from a region that never moves ----------------


def test_status_words_are_said_from_a_region_that_never_moves(fresh_page: Page):
    """A11Y-24: #status-live (role=status, visually hidden) is the same node, a child of
    <body> and never under a hidden stage, on every screen; it says what the visible line
    says and empties with it."""
    page = fresh_page
    live = page.locator("#status-live")
    live.evaluate("e => { e.__same = true; }")
    on_body = "e => e.__same === true && e.parentElement === document.body && !e.closest('.hidden, [hidden]')"
    assert live.evaluate(on_body) and live.get_attribute("role") == "status"
    assert page.locator("#status").get_attribute("role") is None
    _map(page, [("w", "Camp", ""), ("w", "Lake", "")])
    assert live.evaluate(on_body)
    _tick(page, [_uid(page, "Camp")])
    _menu_action(page, "#bulk-exclude")
    expect(page.locator("#status")).to_have_text("Excluded 1 item.")
    expect(live).to_have_text("Excluded 1 item.")
    page.click("#export")
    expect(page.locator("body")).to_have_attribute("data-stage", "done")
    assert live.evaluate(on_body)
    page.click("#back")
    assert live.evaluate(on_body)
    # A receipt that times out leaves both empty.
    page.evaluate("STATUS_LINGER_MS = 300; setStatus('Moved 1 item to Trip.', 'ready')")
    expect(live).to_have_text("Moved 1 item to Trip.")
    expect(page.locator("#status")).to_have_text("", timeout=3000)
    expect(live).to_have_text("")
    # An error stays, in both.
    page.evaluate("setStatus('A folder needs a name.', 'err')")
    expect(live).to_have_text("A folder needs a name.")

