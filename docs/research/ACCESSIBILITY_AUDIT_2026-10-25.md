# Accessibility audit: WCAG 2.2, levels A and AA (2026-10-25)

Scope: the whole Cairn site on branch `feat/bulk-rename` (audit branch `audit/a11y`): the landing
screen, the edit screen with every popover, menu, dialog and confirm (the new **Rename…** and
**Change note…** dialogs in every mode included), the export screen, Help, `faq.html` and
`walkthrough.html`, and the same flows under the production CSP. Desktop only, at 1440×900
(ENG-02). Nothing in the product was changed; this file is the only output.

Method: a manual review against WCAG 2.2 A and AA, with evidence from Playwright 1.64 driving
headless Chromium against the dev server (`web/serve.py`, which sends the production CSP). No
third-party audit tools. Every number below was measured in the page unless the row says
"code read". No screen reader was run (see "What was not tested").

---

## 1. Summary

| Severity | Count | Meaning here |
|---|---|---|
| Blocker | 0 | A task that a group of users cannot finish at all |
| Serious | 3 | A task that works, but a group of users loses track of where they are or what will change |
| Moderate | 12 | A real WCAG A or AA failure with a workaround, or one that hits a common path |
| Minor | 14 | A narrow failure, an advisory that passes the letter of WCAG, or a code-read risk |

No blockers: every action can be reached and done from the keyboard (drag has **Move to…** and
**+ New folder**; shift ranges work with Shift + Space; Ctrl / ⌘ + A works), every dialog has a
name and returns focus, and the CSP run builds the same accessibility tree as the dev run.

**Top five fixes** (all small):

1. **Keep keyboard focus out from under the sticky bars** (A11Y-01). Up to 1 in 5 focus stops
   on the edit screen is fully hidden under the search row and the selection bar when tabbing
   backwards; the FAQ's top bar does the same. One `scroll-padding-top` rule per page and a larger
   `scroll-padding-bottom` on the rail fix it.
2. **Move focus to the new screen's heading on every stage change** (A11Y-02). Today focus drops to
   `<body>` after Export, Back, Start over and a file load, and the page title never changes.
3. **Give the Now → After lists words for screen readers** (A11Y-03, A11Y-06). The Icon & color…
   preview is pictures with no text; the Rename… and Change note… preview is one run-on line.
   Visually hidden text keeps UI-26's "no words in the dialog" look.
4. **One polite live region for result and selection counts** (A11Y-04). Typing in the search,
   picking a filter, Ctrl / ⌘ + A and a shift range change "Showing N" and "N selected" silently.
5. **Make focus and selection tell apart** (A11Y-09, A11Y-10). The More menu's focus is a 1.15:1
   tint, and a focused swatch's ring looks like the selected swatch's ring.

A quick win next to these: controls on a nameless row are named "Select " and "Open note for "
(A11Y-05), new since names became optional (UI-39).

---

## 2. Findings

Severity order. "Effort": S is under an hour with its test, M a few hours, L a day or more.
Line numbers are on `feat/bulk-rename` as of this audit. Every fix that changes how something
looks says so, because AGENTS.md asks for the owner's eye on visible changes; none contradicts a
decision in `docs/design/DECISIONS.md` unless the row says so. A fix that adds or changes a
user-facing string also needs its line in `docs/design/LABELS.md` in the same commit
(`tests/test_labels_inventory.py`).

| ID | WCAG SC | Where | What happens (evidence) | Who it affects | Severity | Proposed fix (effort) |
|---|---|---|---|---|---|---|
| A11Y-01 | 2.4.11 Focus Not Obscured (Minimum), AA | Edit screen: rows under the sticky `.toolbar` (styles.css:153) and `#selbar` (styles.css:174); rail entries above the sticky `.rail-foot` (styles.css:147); FAQ links under the sticky `.topbar` (styles.css:70) | Shift+Tab upward from row 60 of Bitterroots with two rows ticked: **16 of 80** focus stops were fully covered (9 of 9 sample points under `#selbar` or `.toolbar`), e.g. `i25`'s name field at top 55 to 89 px, all under the selection bar. With nothing ticked: **8 of 60** fully covered by the 51 px search row (rows are 42 px tall). Tab downward: none. Rail: `icon\|Climbing` and `icon\|Hazard` checkboxes fully under the rail footer (status, Export, Start over; about 140 px tall in the screenshot), although `.rail` has `scroll-padding-bottom:84px` (styles.css:130). FAQ: Shift+Tab from the bottom, 4 TOC links and `#` anchors fully under the top bar (top 0 to 55 px); `scroll-margin-top:72px` exists only on `.faq-sec` and `.faq-q`, not on the links that get focus. Walkthrough: none. | Sighted keyboard users; anyone using Shift+Tab or a screen magnifier | Serious | Pad the page scroller for the sticky bars. Edit screen: in `updateSel()` (app.js:1202) set `document.documentElement.style.setProperty("--sticky-h", toolbar.offsetHeight + (selbar visible ? selbar.offsetHeight : 0) + 8 + "px")` and add `html{scroll-padding-top:var(--sticky-h,0px)}`; set `--toolbar-h` from the same measure (the selection bar already reads it, styles.css:175, but nothing sets it). Rail: `.rail{scroll-padding-bottom:150px}` (or measure `.rail-foot` the same way). Doc pages: `html:has(body.docpage){scroll-padding-top:72px}`. No visible change. (S) |
| A11Y-02 | 2.4.3 Focus Order, A (also 2.4.2 Page Titled, advisory) | `showStage()` app.js:248, called by `handleFiles`, `doExport`, `#back`, `resetAll`, `onPopState` | After Export by keyboard: `document.activeElement` is `body` (Export is hidden with its stage). Same after the export screen's Back (measured). After Start over and after a file load the button that had focus is hidden the same way (code read: `closeConfirm(false)`, then `showStage`). A screen reader says nothing about the new screen; Tab restarts from the top. The title stays "Cairn — CalTopo to onX" on all three stages. | Screen reader and keyboard users | Serious | In `showStage(name)`, after the swap, focus the new stage's heading: give the landing `h1`, `#map-title` and the export `h1` `tabindex="-1"` and call `.focus({preventScroll:true})` (skip it when a dialog opens right after, e.g. the fill warning on load). Set `document.title` per stage ("Edit · Cairn", "Export · Cairn"; wording for the owner, LABELS.md). No visible change beyond the title; fits UI-27's quiet loading (no new text on screen) and UI-37 (popstate goes through `showStage` too). (S) |
| A11Y-03 | 1.1.1 Non-text Content, A; 1.3.1 Info and Relationships, A | Icon & color… / Color & style… dialog, `drawBulk()` app.js:1510 | The Now → After rows are an aria-hidden marker, the name, an aria-hidden arrow and an aria-hidden marker. Accessibility tree: `text: Now After Shoshone Spire Lower crossing option supposedly good bc skiing`. A screen reader user hears the names and nothing about the current or picked icon, colour, style or weight, so cannot check the change before Save. | Screen reader users | Serious | Keep the drawing (UI-26 removed the visible "Camp · Blue" words on purpose) and add visually hidden text per row with the existing `.sr-only` class: `<span class="sr-only">Now Default pin, Red. After Summit, Blue.</span>`; for a line or area use the row button's wording ("Line, Red, Solid, Thin"). Hide the visual cells from AT (`aria-hidden="true"` on the two `.na-cell` marks only). No visible change; does not contradict UI-26. (S) |
| A11Y-04 | 4.1.3 Status Messages, AA | Search and filters: `renderChips()` app.js:646 (`#chips`, index.html:111) and "Nothing matches these filters." (app.js:707); selection: `#selcount` (index.html:114) via `updateSel()` | Typing "water" in the search: `#status` stays empty; `#chips` ("Showing 2 …") and the "Nothing matches" note have no role and no `aria-live`. Ctrl / ⌘ + A: `#selcount` reads "177 selected" with no live region (`aria-live` null, `#selbar` has no role). Same for a shift range and a folder's header checkbox. | Screen reader users | Moderate | Add one visually hidden polite region next to `#status`, e.g. `<span id="sr-status" class="sr-only" role="status"></span>`, and write to it (debounced about 400 ms) from `renderChips()` ("2 shown", "Nothing matches") and from `setSelectAll()` / the range and header-checkbox paths ("177 selected", "Selection cleared"). Not visible, so UI-26 and UI-27 are not touched; the strings go in LABELS.md. Keep it separate from `#status`, whose receipts stay as they are. (S) |
| A11Y-05 | 4.1.2 Name, Role, Value, A; 2.4.6 Headings and Labels, AA | `row()` app.js:975 (`aria-label="Select ${it.name}"`, `"Open note for ${it.name}"`, `"Include ${it.name}"`); `openPop()` app.js:1323 (`Change … for ${it.name}`) | On the small test map, the three nameless rows (`i5`, `i6`, `i8`) expose `checkbox "Select "` and `button "Open note for "`; the popover's name is built the same way, "Change icon and color for " (code read, app.js:1323). Only the name field falls back (`Name of Untitled`). Names are optional since UI-39, so these rows are now normal. | Screen reader and voice-control users | Moderate | Use the same fallback everywhere a label takes the name: `const label = it.name \|\| "Untitled"` in `row()` and `openPop()` (and the drag ghost if it ever names items). Optionally add the folder for twins ("Select Untitled in Crew"). No visible change. (S) |
| A11Y-06 | 1.3.1 Info and Relationships, A | Rename… and Change note…, `drawTextBulk()` app.js:1768, `.na-rows` | The list reads as one line: `text: Now After Untitled BR · WP 9 BR · WP 9 Untitled BR · WP 12 BR · WP 12 …`. Nothing tells which value is before and which after, where one row ends, or which note belongs to which item; the 512-byte caution for a row runs into the next row's text. | Screen reader users | Moderate | Mark the rows up as a list: `role="list"` on `.na-rows`, `role="listitem"` on each `.na-row`, and replace the aria-hidden arrow's meaning with hidden words: `<span class="sr-only">Now</span>` before the before-cell and `<span class="sr-only">, after</span>` before the after-cell (for notes, `<span class="sr-only">Note for X: </span>`). "No change" and the caution already read as text. No visible change. (S) |
| A11Y-07 | 1.3.1 Info and Relationships, A; 2.4.6 Headings and Labels, AA | Popover and dialog rows: `colorRowHTML()` app.js:1246, `secHead()` app.js:1244, `lineOptsHTML()`, `fillRowHTML()`, the mode row in `openTextBulk()` | The visible row labels ("Color", "Waypoint color", "Line color", "Icon", "Fill") are plain `span.label`s not tied to their controls. The area popover has two buttons named "Blue" (the Color swatch and the Fill choice); the Icon & color… dialog has two or more "Leave as is" buttons and, for a mixed selection, two sets of "Red", "Blue" … with nothing to say which is the pin colour. The Rename… mode toggles ("Add before" …) have no group name. Style and Weight are already `role="group"` with a name. | Screen reader and voice-control users | Moderate | Give each row's label an id and wrap the row in `role="group" aria-labelledby="<that id>"` (Color, Waypoint color, Line color, Icon, Fill), as `lineOptsHTML()` already does for Style and Weight. Mode row: `role="group" aria-label="Change"` (or radio semantics, see A11Y-18). No visible change. (S) |
| A11Y-08 | 2.4.3 Focus Order, A | Single-item popover `#mark-pop` (index.html:152), `openPop()` | The popover is the last thing in the DOM and does not keep focus. Shift+Tab from its first swatch jumped to the last row's marker at the bottom of the list (`i176\|mark`, top 822 px) with the popover still open; Tab past Save went to `body` and out to the browser, popover still open. Esc and Cancel do return focus to the marker. | Keyboard and screen reader users | Moderate | Treat it like Move to…: in the document keydown handler (app.js:2730), `else if (POP) trapTab(e, $("#mark-pop"))`. Clicking outside already closes it, so a trap changes nothing for mouse users. (S) |
| A11Y-09 | 1.4.11 Non-text Contrast, AA (focus indicator); 2.4.7 Focus Visible, AA (borderline) | More menu items: `.menu button:hover,.menu button:focus-visible{background:var(--sel-row);outline:none}` styles.css:182 | Keyboard focus on "Rename…" shows only a tint: `--sel-row` #E9EFDF on `--sheet` #FFFDF7, **1.15:1**, no outline (computed `outline: none`). On screen it is a faint green band. | Sighted keyboard users, low-vision users | Moderate | Drop `outline:none` from the `:focus-visible` half of that rule and add `outline-offset:-2px`, so the global ring shows inside the menu (`--link` on `--sheet` is 7.01:1). Keep the tint for hover. Small visible change. (S) |
| A11Y-10 | 1.4.1 Use of Color, A; 2.4.7 Focus Visible, AA | Colour swatches in the popover and dialog: `.swatch-btn[aria-pressed=true]{outline:2px solid var(--ink)}` and `.swatch-btn:focus-visible{outline:2px solid var(--link)}` styles.css:298-299 | The selected swatch and the focused swatch both get a 2 px ring at 2 px offset, one ink (#2A241C) and one brown (#7A4E25). With focus on Lime and Black selected, the two rings look the same at normal size; the only difference is the ring's colour, so a keyboard user cannot tell which colour is picked and which is focused. | Sighted keyboard users, colour-blind users | Moderate | Mark "selected" with something other than a ring colour: a check glyph in the pressed swatch (white or ink by the swatch's lightness), or a double ring (`box-shadow:0 0 0 2px var(--sheet),0 0 0 4px var(--ink)`) with the focus outline moved out to `outline-offset:5px`. Visible change to the UI-36 row: show the owner first. (S) |
| A11Y-11 | 2.5.3 Label in Name, A | Note button in each row, `row()` app.js:991 | Visible text is the note's first line or "Add a note"; the accessible name is `aria-label="Open note for Shoshone Spire"`, which contains neither. A voice-control user who says "click Add a note" gets no match. (The icon, line, Include and Download buttons are fine: their names start with or contain their visible words.) | Voice-control users | Moderate | Remove the `aria-label` so the name is the button's own text, and add the item as hidden text inside the button: `<span class="sr-only">, note for Shoshone Spire</span>` (with the "Untitled" fallback from A11Y-05). The visible text then leads the name. No visible change. (S) |
| A11Y-12 | 2.1.1 Keyboard, A (information only on pointer hover) | Icon and line buttons, `title="${esc(it.why)}"` in `row()` app.js:994 and :999; Help step 2 "Hover a marker to see why" | Why an icon was chosen lives only in the native `title`. Chrome exposes it to screen readers as the description ("CalTopo's generic "point" pin carries no meaning to copy …"), but a sighted keyboard user cannot see it: native tooltips do not appear on focus. The styled tip (UI-33) already appears on keyboard focus for names, notes and caution marks. | Sighted keyboard users, switch users | Moderate | Add `.icon-btn, .line-btn` to `TIP_SRC` (app.js:810) and return `it.why` from `tipText()` for them, then drop their `title` (no double tooltip). Help's line becomes "Hover or focus a marker to see why" (LABELS.md, Help). Visible change: the why shows in the styled tip instead of the browser's. (S) |
| A11Y-13 | 1.4.3 Contrast (Minimum), AA | Name field placeholder "Untitled", `.name-in` (styles.css:220), no `::placeholder` rule | The browser default placeholder colour #757575 measures **4.12:1** on `--card`, **3.92:1** on a selected row (`--sel-row`), **3.88:1** on a hovered row, at 14 px. Since UI-39 a nameless row shows only this word. | Low-vision users | Moderate | `.name-in::placeholder{color:var(--muted);font-style:italic;opacity:1}`: 6.86:1 on `--card`, 6.52:1 on `--sel-row`, 6.46:1 on `--hover-row`, and the same look as the dialog's "Untitled" (`.is-placeholder`). Small visible change. (S) |
| A11Y-14 | 1.4.3 Contrast (Minimum), AA | Excluded rows: `tr.excluded .note-btn, tr.excluded .icon-btn, tr.excluded .line-btn{opacity:.55}` styles.css:249 | Measured on an excluded Bitterroots row: "Add a note" (muted at 55%) **2.45:1** and the icon name "Climbing" **3.42:1**; a written note (ink at 55%, from the tokens) is **3.48:1**; all at 13 to 14 px. The row is still active (name, note and Include all work), so the "inactive component" exception does not apply. | Low-vision users | Moderate | Dim with colour, not opacity: `tr.excluded .note-text, tr.excluded .icon-name{color:var(--muted)}` (6.86:1 on `--card`) and keep the opacity only on the drawn marks: `tr.excluded .marker, tr.excluded .lineswatch{opacity:.55}`. The struck-through name and the "Excluded" label already carry the state. Small visible change. (S) |
| A11Y-15 | 1.4.4 Resize Text, AA | Single-item popover at 200% zoom (1440×900 at 200% = a 720×450 CSS px viewport): `.pop` styles.css:256-263 | The popover caps at `100vh - 16px` (434 px). The icon section shrinks below its content and the footer is drawn over the icon list: Cancel and Save cover half of the "Closed Gate" row, and about 1.5 rows of icons show. Everything else at 200% passed (see section 3). | Low-vision users who zoom | Moderate | `.pop>.pop-sec.icons{overflow:hidden}` so the grid scrolls inside its section instead of overflowing it, and `.pop{overflow-y:auto}` as the fallback when even that does not fit. No change at 100%. (S) |
| A11Y-16 | 1.4.1 Use of Color, A | Rename… / Change note… "After" values, `.na-after .hit` (styles.css:371), `markChange()` app.js:1736 | The new part of each After value is shown only by a background tint, `--sel-row` on `--sheet`, **1.15:1**, in a plain `<span>` with no role. It is barely visible and not exposed to assistive technology. The full After text is still shown, so nothing is lost; the highlight is a helper. | Low-vision and colour-blind users | Minor | Keep the owner's highlight (UI-39 chose "the mockups' green") and add a non-colour cue: `.na-after .hit{text-decoration:underline 2px var(--green);text-underline-offset:2px}`, and use `<mark>` instead of `<span>` so it is exposed as a highlight. This adds to UI-39's look: show the owner. (S) |
| A11Y-17 | 2.4.3 Focus Order, A | More menu `#more-menu` (index.html:118), keydown handler app.js:2682 | Every menu item is a Tab stop, and Tab moves through "Rename…", "Change note…" … "Include", then out to "Clear" and the first folder's name, with the menu still open (`aria-expanded="true"`). Arrow keys, Home, End and Esc work. | Keyboard and screen reader users | Minor | Follow the ARIA menu pattern: `tabindex="-1"` on the menu items (arrows already move focus), and on Tab in the menu call `closeMenu()` and let focus continue from More. (S) |
| A11Y-18 | 2.1.1 Keyboard, A (passes; efficiency advisory); 4.1.2 (role advisory) | Icon picker and palettes: `buildIconGrid()`, `paletteHTML()`; mode toggles | From a swatch to Save in the single popover takes **99** Tab presses (10 swatches, the search, 95 icons); the Icon & color… dialog has **128** Tab stops. Every swatch, icon and mode is its own stop; arrow keys do nothing. Single-choice sets are announced as independent "toggle button"s. | Keyboard and switch users | Minor | Roving `tabindex` per set: one Tab stop for the palette, one for the icon list, one for the modes; arrows move within (two columns: Left / Right / Up / Down; Home / End). Expose single choices as `role="radiogroup"` / `role="radio"` with `aria-checked`. This keeps UI-29's rule (the list is built once; a pick only flips state, focus stays). (M) |
| A11Y-19 | 2.5.8 Target Size (Minimum), AA | Empty folder's ×, `.facet-x` 22×22 (styles.css:626); FAQ TOC group links `.doc-toc .toc-sec` (styles.css:540) | The × measures **22×22** and sits on top of its folder's button, so the spacing exception cannot apply; there is no other control that removes an empty folder (Esc only takes back one that was just made). The FAQ's group links ("The problem", "Your files" …) are **14.8 px** tall with the first question link less than 12 px away (the spacing test fails); a TOC is a list, not a sentence, so the inline exception does not apply. | Users with tremor or low pointer precision | Minor | `.facet-x{width:24px;height:24px}`; `.doc-toc .toc-sec{padding:5px 0}` (or `min-height:24px`). Both are tiny visible changes. (The excluded row's Include chip is 47×21 and also fails spacing, but More → Include is a full-size equivalent, so it passes; making it 24 px tall would still be kinder.) (S) |
| A11Y-20 | 1.4.3 Contrast (Minimum), AA | FAQ question anchors `.faq-q .anchor` (styles.css:547); the "here now" count during a drag, `.facet-btn.here-now` (styles.css:616) | The `#` before each FAQ question is link text in `--rule` on `--paper`: **1.91:1** (it darkens only on hover or focus). "here now", shown on the dragged rows' own folder while dragging, is `--faint` on `--rail`: **2.33:1** at 13 px. (The disabled "· here now" in Move to… is exempt: an inactive control.) | Low-vision users | Minor | Anchor: `color:var(--muted)` (6.28:1), brown on hover and focus as now. "here now": `color:var(--muted)` in italics (5.61:1). Small visible changes. (S) |
| A11Y-21 | 1.4.3 Contrast (Minimum), AA (where a line crosses); AGENTS.md and UI-20 ("text never sits on the contours") | The filter chips row `#chips` on the edit screen | `#chips` and `.content` have no background, so "Showing 2" and "Clear all" sit on the contour layer; a contour stroke runs through "Showing 2" in the screenshot. Where a stroke crosses, `--muted` on #C4AF85 is 3.58:1 and `--link` 3.33:1. | Low-vision users | Minor | Give the row the paper panel the rule asks for: `.chips{background:var(--paper);box-shadow:0 0 0 6px var(--paper)}`. Matches UI-20; small visible change. (S) |
| A11Y-22 | 2.4.1 Bypass Blocks, A (passes via landmarks; advisory) | Edit screen; FAQ | On Bitterroots the rail puts **34** Tab stops (3 section headers, 4 types, 11 folders and + New folder, 13 icons, Export, Start over) before the search box. Landmarks (`complementary "Map and filters"`, `main`, `navigation "Site"`, one `region` per folder) and headings make this a pass for screen reader users, but a keyboard-only user has no shortcut. The FAQ puts the TOC (about 25 links) before the first answer. | Keyboard-only users | Minor | A skip link as the first focusable element of `#edit-stage`, visible only on focus: "Skip to the list" → focuses `#filter`; on the doc pages "Skip to the content" → `main`. It shows only on focus, so the resting look is unchanged; the label goes in LABELS.md. (S) |
| A11Y-23 | 3.3.1 Error Identification, A (passes; advisory); 3.3.3 Error Suggestion, AA | Folder name errors, `wireFolderName()` / `finishRename()`; load errors, `handleFiles()` / `humanError()` | Errors are text in `#status` (`role="status"`, so announced): "A folder needs a name.", "A folder name can be up to 100 characters.". The name field gets no `aria-invalid` or `aria-describedby`, so a screen reader user who returns to the field hears nothing. A malformed JSON file says only "Failed: Could not load file", with no suggestion; the others suggest what to do (e.g. the empty GPX names what Cairn reads). | Screen reader users; everyone, for the JSON case | Minor | While a folder-name error stands, set `aria-invalid="true"` and `aria-describedby="status"` on `.folder-name-in`, and clear both on input. Map the JSON parse error to a sentence with a next step, in the style of the others ("Couldn't read that file — it isn't valid JSON. Export it from CalTopo again as GeoJSON."; wording for the owner, LABELS.md). (S) |
| A11Y-24 | 4.1.3 Status Messages, AA (risk; code read only) | `showStage()` app.js:248 moves the one `#status` node between `#status-top` and `#status-rail` with `appendChild` | A live region that is moved in the DOM is re-created in the accessibility tree; some browser and screen reader pairs stop announcing it until it changes again. Not verified with a screen reader (none was run). The status itself is right: `role="status"`, polite, atomic. | Screen reader users | Minor | Do not move it: keep a status region in each slot and have `setStatus()` write to the one whose stage is showing, or keep one fixed visually hidden `role="status"` region and mirror its text into the visible slot. (S) |
| A11Y-25 | 4.1.3 Status Messages, AA (advisory: consistency) | More → Exclude, Include, Use note as name: `bulk()` app.js:1197 | These three change rows and say nothing: `#status` stays empty (measured after Exclude). Every other bulk action ends with a receipt ("Changed 5 items.", "Moved 1 item to …"). A screen reader user gets no confirmation; focus returns to the page with the menu closed. | Screen reader users | Minor | End `bulk()` with a receipt, e.g. "Excluded 3 items.", "Included 3 items.", "Renamed 3 items from their notes." (wording for the owner; LABELS.md). Visible change: a status line where there was none. (S) |
| A11Y-26 | 1.3.1 Info and Relationships, A | Name column header, `folderSection()` app.js:736 (`aria-label="Sort ${g.name} by name"` on `.sort-btn`) | The button's label becomes the column header's name: the tree shows `columnheader "Sort Blodgett by name"`, so moving across cells announces "Sort Blodgett by name" instead of "Name". The sort state is already on the `th` (`aria-sort`, verified: ascending after one press). | Screen reader users | Minor | Drop the `aria-label`; the button's name becomes "Name" and the header reads "Name, button, sorted ascending", the usual sortable-table pattern. No visible change. (S) |
| A11Y-27 | 1.3.1 Info and Relationships, A (advisory); 2.4.6 | Rail filter sections, `.sec-h` (index.html:70, 80, 84) | "Type", "Folders" and "Icon" are disclosure buttons (with `aria-expanded` and `aria-controls`, which pass), not headings, so heading navigation on the edit screen offers only the map title and the folders. | Screen reader users | Minor | Wrap each `.sec-h` in a heading, `<h2 class="sec-wrap">` around the button (the accordion pattern), with the heading's margins reset. No visible change. (S) |
| A11Y-28 | 4.1.2 Name, Role, Value, A (HTML validity) | index.html:37, 94, 135 | The page has three `<main>` elements; the two not shown are hidden with `class="hidden"` (`display:none`), not the `hidden` attribute, which HTML requires for extra `main`s. Assistive technology ignores `display:none`, so the effect today is nil. No duplicate ids were found in any state scanned. | Nobody today; a validator flags it | Minor | Toggle the `hidden` attribute in `showStage()` (keep the class for the CSS), or make the three stages `<section>`s inside one `<main>`. (S) |
| A11Y-29 | 1.1.1 Non-text Content, A | walkthrough.html:62, `walkthrough/01-landing.webp` | The alt says "Cairn's landing page: three steps and a drop zone for a CalTopo export"; the screenshot shows a heading, one paragraph and the drop zone, with no steps. | Screen reader users reading the walkthrough | Minor | "Cairn's landing page: what it does, and a drop zone for a CalTopo export." Check every alt when `scripts/make_walkthrough_shots.py` regenerates the shots. (S) |

---

## 3. What passes

Checked and passing, so the owner knows the ground covered.

- **Names, roles, states (4.1.2).** Every dialog has a role and a name: Help (`dialog`, `aria-modal`,
  labelled by its heading), Icon & color… (`dialog`, "Change icon and color for 3 items"),
  Rename… and Change note… (`aria-labelledby="bulk-title"`), Move to… (`dialog` "Move to folder",
  its list a named group), the popover ("Change area for …"), and every confirm (`alertdialog`
  with `aria-labelledby` and `aria-describedby`: "Start over?", "Save your note?", "Leave this
  map?", "4 areas will lose their fill"; the merge offer uses the same component, code read). Toggles expose `aria-pressed` (type
  facets, swatches, Style, Weight, Fill, "Leave as is", modes, Match case); disclosures expose
  `aria-expanded` (rail sections with `aria-controls`, folder collapse, More); the Name header
  exposes `aria-sort`. Icons and markers are `aria-hidden` inside labelled buttons ("Climbing,
  Black. Change icon or color"; "Line, Red, Solid, Thin. Change line"). Caution marks are
  focusable `role="img"` with the sentence as their name. Per-folder Download buttons have distinct
  names ("Download Lost Trail Pass").
- **Keyboard (2.1.1, 2.1.2).** Everything is operable: Shift + Space on a row's checkbox makes a
  range (5 rows selected in the test); Ctrl / ⌘ + A selects the rows shown; **More → Move to…**
  works with arrows, Home, End, Enter and Esc and is the drag's alternative (status "Moved 2 items
  to Lost Trail Pass.", focus to that folder's rail entry); **+ New folder** works with Enter; an
  empty folder's × appears on focus; folder rename, collapse and sort work with Enter; the note
  editor takes Enter for a line, Ctrl / ⌘ + Enter to save and Esc to cancel, with focus back on the
  note button. Dialogs trap Tab on purpose and every one closes with Esc; there is no trap without
  an exit. Help lists "Shift + click" only; Shift + Space could be added there.
- **Focus return (2.4.3).** Help → its Help button; Start over → Start over; popover → its marker;
  Icon & color… → its button; Rename… and Change note… → More (measured after Esc and after Save;
  the search box when the selection empties, code read); Move to… → More; "Save your note?" → Keep editing → the note's text box.
- **Focus visible (2.4.7, 1.4.11).** The global ring is 2 px `--link`: 5.23:1 on `--rail`, 5.84:1 on
  `--paper`, 6.39:1 on `--card`, 7.01:1 on `--sheet`. Name fields show a 1 px brown border (6.39:1
  against the row) and a lighter background; the search box rings its whole field. Exceptions: A11Y-09, A11Y-10.
- **Text contrast (1.4.3).** Every other text measured passes. Lowest regular pairs: `--warning`
  "Default pin" on `--rail` 5.49:1, `--muted` counts on `--rail` 5.61:1, `--link` on `--paper`
  5.84:1, the green "ready" status on `--rail` 4.97:1 (12 px, passes), `.wt-part` 6.28:1. Search
  and icon-search placeholders (`--muted`) 6.86:1. White on the green primary button 6.78:1.
  Disabled controls (Save before a change, "· here now" in Move to…) are exempt.
- **Non-text contrast (1.4.11).** Button borders `--control` 3.68 to 4.02:1; pressed toggles' green
  border 6.67:1; chip border 5.77:1; swatch rims (ink) 15.1:1; caution icon 6.71:1; drop target
  during a drag (green dashed) 4.97:1. The light borders of `.tog` and `.icon-pick` (1.58:1) and
  "+ New folder" (2.02:1) pass because each control is identified by its own words or drawing,
  which WCAG accepts.
- **Use of colour (1.4.1).** "Default pin" is also italic and worded; excluded rows are struck
  through and say "Excluded"; selected rows have a ticked box; the FAQ and walkthrough tables say
  Yes / No / Partly in words. Exceptions: A11Y-10, A11Y-16.
- **Hover and focus content (1.4.13).** The styled tip (`#tip`, `role="tooltip"`, linked by
  `aria-describedby` while shown) opens on hover and on keyboard focus, stays while the pointer
  moves onto it, and Esc closes it and nothing else. Native `title` tooltips are the browser's and
  outside 1.4.13 (see A11Y-12 for the one that carries information).
- **Resize text (1.4.4), at 200% (720×450 CSS px).** No horizontal scroll on the landing, edit,
  export, FAQ or walkthrough pages. The Icon & color… dialog scrolls with Save kept in view (sticky
  footer); Rename… fits. Long names and notes are cut with an ellipsis as at 100%, with the whole
  value in the tip. Exception: A11Y-15.
- **Text spacing (1.4.12).** With line height 1.5, letter spacing 0.12em, word spacing 0.16em and
  paragraph spacing 2em forced on every element, no text overlaps or is lost on any page or dialog.
  New ellipses appear only where text is already cut by design (names, note previews, one icon
  facet name, "Water Crossing", which keeps its full name in `title`).
- **Target size (2.5.8).** Most targets are 24 px or more. Under 24 px but passing on spacing: row
  and header checkboxes (14×14), the Name sort button (61×18), caution marks (22×22), the site nav
  links (17.6 px tall). Inline links in sentences and the footnote links are exempt.
- **Dragging movements (2.5.7).** Drag has two single-pointer alternatives: tick and use
  **More → Move to…**, or tick and click **+ New folder**. The drag label is `aria-hidden`, and the
  result is announced through `#status`.
- **Status messages (4.1.3).** `#status` is `role="status"` (polite, atomic) and carries receipts and
  errors ("Changed 5 items.", "Couldn't read that file — …"). The Rename… summary
  ("5 will change · 0 unchanged") is `aria-live="polite"` and only updates when it changes. "Getting
  ready…" is a status region that is emptied when hidden. Exceptions: A11Y-04, A11Y-25.
- **Timing (2.2.1).** The receipt clears itself after 8 s (measured: gone at 8.8 s). It is not
  needed to finish a task and is announced at once, so this passes. Opinion: keep a receipt until the
  next action instead of on a timer; slow readers and magnifier users lose it today.
- **Pause, stop, hide (2.2.2) and flashing (2.3.1).** No motion that starts by itself; the only
  movement (the rail's auto-scroll) happens during the user's own drag.
- **Structure (1.3.1, 2.4.6).** The list is real tables with column headers; the Help and FAQ tables
  have row headers (`scope="row"` on the FAQ); each folder is a named region with an `h2`; the doc
  pages keep a visually hidden `h1` (UI-38) and a clean `h2` / `h3` outline.
- **Page titled, language, navigation (2.4.2, 3.1.1, 3.2.3, 3.2.4, 3.2.6, 2.4.4, 2.4.5).** Each page
  has a title; `lang="en"` on all three; the site nav is the same five items in the same order on
  every page with the current page marked `aria-current="page"`, and Help is in the same place
  everywhere; link texts make sense in context (the FAQ's `#` anchors are named "Link to this
  question" under their heading).
- **On input and on focus (3.2.1, 3.2.2).** Filters and the search change the list, not the context.
- **Labels and redundant entry (3.3.2, 3.3.7).** Every field has a label (Search, Text, Find,
  Replace with, Note, Folder name, Name of …); Rename… keeps what was typed in each mode's field
  when switching modes.
- **Production CSP.** With the CSP enforced (no bypass): boot reaches `body[data-engine="ready"]`, a
  file loads, Rename… opens and previews, Help opens, export works; the accessibility tree matches
  the dev run and the console shows no CSP violation.
- **New tabs.** In the app, FAQ, Walkthrough and GitHub open in a new tab (UI-38: leaving would drop
  the map). Warning about new tabs is AAA (3.2.5), so this passes; a visually hidden "(opens in a new
  tab)" in those three links would still help screen reader users.

---

## 4. Not applicable, or by decision

- **Reflow at 320 CSS px (1.4.10): not tested, by decision (ENG-02, desktop only).** Opinion: 1.4.10
  is not only about phones. A desktop user at 400% zoom on a 1280 px wide screen gets a 320 px
  viewport, and that is exactly the low-vision user the criterion protects. Today the site already
  does well at 720 px (200%) thanks to the narrow-screen CSS that ENG-02 keeps "as harmless
  fallback". I recommend keeping that fallback rather than removing it "if it ever gets in the way",
  and one manual look at 400% before each release, without adding phone layouts or tests.
- **One light theme (UI-19).** No dark mode is a design decision and not a WCAG requirement. Windows
  forced-colours (High Contrast) mode is outside WCAG and was not tested; the swatches and drawn
  markers would be worth one look there someday.
- **Audio and video (1.2.x), motion actuation (2.5.4), orientation (1.3.4), input purpose (1.3.5),
  error prevention for legal or financial data (3.3.4), accessible authentication (3.3.8).** Cairn
  has no media, no motion input, no orientation lock, no personal-data fields, no transactions and no
  sign-in.
- **Images of text (1.4.5).** The FAQ's diagram contains words, but it is a diagram and its alt
  carries the full text; the walkthrough's screenshots are pictures of the app. Both are allowed.
- **Language of parts (3.1.2).** Map names and notes in other languages are the user's data; Cairn
  cannot know their language.

---

## 5. How it was tested (to rerun)

Environment: the worktree on `audit/a11y` (from `feat/bulk-rename`), the repo venv's Python with
Playwright 1.64 and its Chromium. The dev server: `PORT=8787 .venv/bin/python web/serve.py` (it
sends the production CSP). Browsers headless at 1440×900, scale 1, `bypass_csp=True` for every run
that reads computed styles, plus one run without the bypass.

Data:
- `tests/fixtures/bitterroots/Bitterroots__Complete_.json` (177 items, 10 folders);
- a small map from `tests/hardening_maps.make_map(4, seed=3, names=["North Roots", "Crew",
  "Mill Creek Canyon", "Paddling"], long_notes=True, no_coords=True, per=(3, 6))`, with three titles
  blanked (`a2`, `m7`, `l10`) and two multi-line notes (`m13`, `l16`): nameless rows, long notes,
  items with no coordinates, the export warnings;
- `tests/fixtures/onx_exports/areas-after-edit.gpx` with its `.kml`: the "4 areas will lose their
  fill" alertdialog, the fill caution and the Fill row.

Checks and how each was measured:
- **Accessibility tree:** `locator(...).aria_snapshot()` per state (landing, Help, edit rail and
  list, selection bar and More, Move to…, each popover kind, Icon & color…, Rename… and Change note…
  in every mode, the note editor, each confirm, the export screen, FAQ, walkthrough). Names and
  descriptions of single controls through CDP `Accessibility.getPartialAXTree`.
- **Contrast:** for every visible element with its own text, the text colour composited over the
  first opaque background up the tree, times the opacity of the element and its ancestors, then the
  WCAG ratio (`(L1 + 0.05) / (L2 + 0.05)`, sRGB linearised at 0.03928). Placeholders through
  `getComputedStyle(el, "::placeholder")`. Token pairs (focus ring, tints, borders) computed the same
  way from the `:root` custom properties.
- **Keyboard:** scripted Tab, Shift+Tab, Enter, Space, arrows, Home, End, Esc and Ctrl+A, recording
  `document.activeElement`, its computed outline, and whether a dialog or menu is still open.
- **Focus Not Obscured:** after each keypress, nine points across the focused element's box; a point
  is covered when `document.elementFromPoint` there is neither the element nor inside it. "Fully
  covered" means all nine.
- **Target size:** the bounding box of every visible focusable target; for each under 24 px, a 24 px
  circle on its centre tested against every other target's box (nested targets count as overlap).
- **200% zoom:** a 720×450 viewport at device scale 2 (the CSS pixel size of 1440×900 at 200%):
  `scrollWidth` against `clientWidth`, plus screenshots of every stage and dialog.
- **Text spacing:** this stylesheet injected, then elements whose `overflow` clips (or that end in an
  ellipsis) compared before and after:
  `* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }`
- **Status messages:** text, `role` and `aria-live` of `#status`, `#chips`, `#selcount` and
  `#bulk-summary` after each action, and `#status` again after 8.8 s.
- **Production CSP:** a context without the bypass; only DOM waits (`body[data-engine="ready"]`),
  `set_input_files`, clicks, keys, `aria_snapshot()` and the console log, no page script.

The audit scripts and screenshots were kept outside the repo (scratch); the steps above are enough
to rebuild them.

## 6. What was not tested

- No HTML validator was run. Duplicate ids and the `<main>` count were checked by script; a code
  read of `patchRail()`'s `.facet-row` wrapper shows no control nested inside another.
- No screen reader (VoiceOver, NVDA or JAWS) was run. Announcements are inferred from the
  accessibility tree and the live-region attributes; A11Y-24 is a code-read risk for that reason.
- No voice control (A11Y-11 is reasoned from the accessible name against the visible text).
- Browsers other than Chromium, and Windows forced-colours mode.
- Reflow at 320 CSS px (by decision, section 4).
- Real file drag-and-drop from the desktop onto the drop zone (Choose file… is the keyboard path and
  was tested; the drop zone itself has no keyboard role, which is fine since the button does the
  same job).

---

## Status (round 4)

Branch `round4/w-a11y` (from `feat/bulk-rename` at `eae79bb`). The findings above are unchanged;
this is where each one stands. Tests: `tests/web/test_accessibility.py`, one or more per finding.

| ID | State |
|---|---|
| A11Y-01 | Fixed in `1893b26` (measured `scroll-padding` on the page and the rail; the doc pages' 72px replaces the sections' `scroll-margin-top`) |
| A11Y-02 | Fixed in `291a29e` (titles "Cairn — Edit" and "Cairn — Export"; the focused heading has no ring) |
| A11Y-03 | Fixed in `c85bf8d` |
| A11Y-04 | Fixed in `fb2e2b9` (reuses the words on screen: "Showing N", "Nothing matches these filters.", "N selected") |
| A11Y-05 | Already fixed before round 4; verified in `c85bf8d` |
| A11Y-06 | Fixed in `c85bf8d` |
| A11Y-07 | Fixed in `c85bf8d` (Style and Weight's group now holds its "Leave as is" too) |
| A11Y-08 | Fixed in `c85bf8d` |
| A11Y-09 | Fixed in `cab9351` |
| A11Y-10 | Fixed 2026-10-26 (owner: a check mark on the chosen swatch) |
| A11Y-11 | Fixed in `c85bf8d` (an aria-label that starts with the button's words, not hidden text: the empty note's words are hidden at rest) |
| A11Y-12 | Fixed in `c85bf8d` (the why is the styled tip and an `aria-description`) |
| A11Y-13 | Fixed in `cab9351` |
| A11Y-14 | Fixed in `cab9351` |
| A11Y-15 | Fixed in `cab9351` |
| A11Y-16 | Fixed 2026-10-26 (owner: an underline under the highlight) |
| A11Y-17 | Fixed in `c85bf8d` |
| A11Y-18 | Deferred by the owner 2026-10-26 |
| A11Y-19 | Fixed in `cab9351` |
| A11Y-20 | Fixed in `cab9351` |
| A11Y-21 | Held for the owner (a paper panel behind the chips, UI-20) |
| A11Y-22 | Fixed in `291a29e` (the edit screen's link is the first Tab stop after the map title, where focus lands) |
| A11Y-23 | Folder name half fixed in `1893b26`; load failures fixed 2026-10-26 (owner: a dialog whose OK returns to a clean home page) |
| A11Y-24 | Fixed in `fb2e2b9` (a fixed visually hidden region mirrors the line on screen) |
| A11Y-25 | Fixed in `c85bf8d` (wording as proposed, for the owner to confirm) |
| A11Y-26 | Fixed in `c85bf8d` |
| A11Y-27 | Fixed in `c85bf8d` |
| A11Y-28 | Fixed in `c85bf8d` |
| A11Y-29 | Fixed in `cab9351` |
