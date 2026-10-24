# Design decision log

Every design choice made through a multiple-choice Q&A is recorded here with **all** the options
that were offered, not just the winner. When a decision is revisited, start from this file: the
options not chosen are the first alternatives to try, and the context explains why the question
was asked at all.

Rules for this file:

- Append; don't rewrite history. To change a decision, add a new entry that names the one it
  supersedes (`Supersedes: UI-03`) and update the old entry's status to `superseded by UI-xx`.
- Record options verbatim as they were presented, including the descriptions. The descriptions
  are part of what was decided against.
- Mark the chosen option with **✔ chosen**. Note anything the user added in their own words.
- Mockups and artifacts produced for a decision get linked under it.

---

## Round 0 — Scope of the web-only cleanup (2026-10-21)

Context: the user decided Cairn is web-only (quietmarch.to/cairn) and asked to remove the CLI it
started as. The web app imports only 7 engine modules (`config`, `color_mapper`,
`icon_resolver`, `mapper`, `parser`, `writers`, `utils`). Implemented in branch
`chore/web-only-cleanup`; the removed code is preserved at git tag `cli-final`.

### SCOPE-01 — Does removing the CLI include the Textual TUI?
Status: decided

- **Remove TUI too** — ✔ chosen. Web-only: delete `cli.py`, `commands/`, `ui/`, `tui/`,
  `preview.py`, `icon_picker.py`, their tests; drop typer/rich/textual/prompt-toolkit deps.
- **Keep TUI for now** — Remove only the typer CLI + legacy prompt-toolkit UI; the TUI stays as
  the secondary local runner.

### SCOPE-02 — Engine code the web app doesn't call yet
Status: decided

Context: onX readers (`onx_gpx`, `onx_kml`), `caltopo_gpx`, dedup/merge/shape_dedup,
normalization, matcher. These power onX→CalTopo and GPX input, which the web could adopt later.

- **Keep, mark not-yet-web** — ✔ chosen. Keep with their tests; annotate as engine-but-not-wired
  into the web, as candidates for future web features.
- **Delete them** — Strict: only what the web app calls today survives. Recoverable from git.

### SCOPE-03 — How to express "deprecated" when the code is removed
Status: decided

- **Delete + tag + docs** — ✔ chosen. Tag the last CLI commit (`cli-final`), remove the code on a
  branch, note the removal in README/AGENTS, no PyPI release.
- **Also ship a final PyPI release** — Publish a last `cairn-maps` version with a deprecation
  warning before deletion.

---

## Round 1 — Web UI redesign: direction (2026-10-21)

Context: the user finds the current web UI generic and "Claude-generated looking": a dark
dashboard with gray cards, pill badges, an amber accent and emoji icons. The overall flow (drop
file → review → fix → export) is acceptable; the design is not. Process agreed: Q&A first, then
mockups/artifacts, then CSS — no ad hoc restyling. Baseline screenshots of the pre-redesign UI:
`docs/design/baseline-2026-10-21/` (since 2026-10-22 kept locally under `archive/`, not in the repo).

### UI-01 — What should Cairn feel like?
Status: decided

- **Field-guide / topo** — ✔ chosen. Paper and contour-map feel: warm off-white, ink lines, a
  serif or condensed type face, map-legend style. Feels like an outdoor tool, not a SaaS app.
- **Utilitarian instrument** — Dense and precise like a GIS or spreadsheet tool: monospace
  numbers, hairline rules, very little decoration, color reserved for onX colors.
- **Quiet editorial** — Lots of whitespace, strong typography, a single column, explanation
  alongside the data. Reads like a well-made document.
- **Match onX/CalTopo** — Borrow the visual language of the two apps it bridges so it feels native
  to that ecosystem.

### UI-02 — Which part of the current UI bothers you most? (multi-select)
Status: decided

- **Header + stats card** — ✔ chosen. The title bar, the 4-number stat card, and the floating
  buttons beside it.
- **Toolbar / filters** — ✔ chosen. The search box (rendering unstyled at the time), type
  dropdown, and Set icon / Set color / Advanced buttons.
- **Item table** — not selected. Folder groups, rows, the pill badges for icon/color, the WPT tags.
- **Empty / drop state** — ✔ chosen. The dashed drop zone with the map emoji.

Note: the item table wasn't flagged, so it gets restyled to match but its structure is the
lowest priority to change.

### UI-03 — Light vs dark
Status: superseded by UI-19

Context: twilight (dark) was the default, with a light toggle (commit `48ae876`).

- **Light-first, dark optional** — ✔ chosen. Design the light theme as the primary identity;
  keep dark as a follow-on.
- **Dark-first, light optional** — Keep twilight as the default identity and redesign it properly.
- **Follow the OS** — Design both equally and use the system setting, with a manual override.

### UI-04 — How far can the layout change?
Status: decided

- **Restyle + rearrange** — ✔ chosen (was the recommended option). Same steps (drop file, review,
  fix, export), but components can move, e.g. a sticky export bar or a folder sidebar.
- **Restyle only** — Keep every element where it is and change only type, color, spacing and
  components.

---

## Round 2 — Web UI redesign: specifics (2026-10-21)

Context: follows UI-01 (field-guide / topo).

### UI-05 — Type pairing
Status: decided

- **Serif heads + grotesk body** — e.g. a sturdy old-style serif for headings (like a USGS quad
  title) with a plain sans for the table. Classic field-guide.
- **Condensed sans + mono** — Map-legend / survey-marker feel: condensed caps for labels,
  monospace for counts and coordinates.
- **All serif** — ✔ chosen. Book-like throughout, including the table. Most distinctive, least
  dense.

Open risk to check in mockups: an all-serif table at 177+ rows may hurt scanability. If it does,
"Serif heads + grotesk body" is the first fallback.

### UI-06 — Accent palette (on warm paper)
Status: decided

- **Topo brown + contour green** — ✔ chosen. USGS map colors: brown contour ink, forest-green
  vegetation tint, blue for water/links.
- **Ink + one signal color** — Near-black ink on paper, with one blaze color (safety orange) only
  for actions and warnings.
- **Faded trail-map** — Muted sage, ochre and slate, like an old National Forest map.

Constraint to respect: the onX color swatches (red, blue, cyan, lime…) are data, not decoration,
and must stay exact regardless of palette.

### UI-07 — What replaces the header + stats card?
Status: decided

- **Map title block** — ✔ chosen. Like a topo map's corner legend: map name, folder/markup counts,
  scale-bar-style detail, with Export as the main action in a sticky bar.
- **Slim header + summary line** — Small wordmark, one sentence of counts ("177 markups in 10
  folders, 25 need an icon"), and a sticky Export bar.
- **Sidebar** — Map name, counts and folder list in a left rail; the table fills the rest.

### UI-08 — Replace emoji and pill badges?
Status: decided

- **Yes, custom line icons** — ✔ chosen (was the recommended option). Simple stroke icons and
  map-legend swatches; keep the real onX icon images where they exist.
- **Keep as-is** — Only change type, color and layout.

---

## Round 3 — Mockups (2026-10-21)

Canvas: https://claude.ai/artifact/PJBrycMk8uXHfeDr1DitKu (private). Source is versioned
in `docs/design/mockups/project/`. All three variants share UI-01…UI-08: warm paper, topo
brown + contour green, blue links, serif throughout, drawn stroke icons, exact onX color swatches,
the real Bitterroots fixture data. Where they differ is the question.

### UI-09 — Which layout for the loaded map?
Status: decided 2026-10-21 — **B, with the round-4 changes below** (see `CollarV2.dc.html`)

- **A · Quad sheet** (`Main.dc.html`, Source Serif 4) — A boxed title block across the top
  like a USGS quad's corner (map name, file, scale-bar ornament, a 2×2 count grid with
  default-pin highlighted). Labelled search/filter row. Folders as headed sections with a
  brown rule. Export lives in a dark sticky bar along the bottom with a one-line summary.
- **B · Map collar sidebar** (`Collar.dc.html`, Libre Caslon Text) — A left rail styled as
  the map collar: title between double rules, counts as sentences, a folder index you can jump
  through, Export + Load at the rail's foot. Segmented type filter including "Default pin · 25";
  a selection bar appears above the table when rows are ticked.
- **C · Legend band** (`Legend.dc.html`, Alegreya + Alegreya SC) — A full-width header band
  with faint contour lines, big map title, Export in the band. Find / Show / Change-selected
  as a three-cell legend box. Symbol-first table columns; colors drawn as line swatches;
  remaining folders as a dotted-leader index.

Empty state (`Empty.dc.html`): one proposal, two columns — what Cairn does + 3 numbered steps
on the left, a framed drop target with contour lines and a map glyph on the right. Not yet a
decision; revisit once UI-09 is picked so it shares that variant's type and header.

User's reasons for B: the folder list works as **facets** (a filter), which A and C lack.
Graft from C: the faint contour lines, used as background in a few places in B.

---

## Round 4 — Feedback on B (2026-10-21)

Revised mockup: `CollarV2.dc.html`. Treatment study: `IconColor.dc.html`. The user's feedback,
condensed but complete:

| # | Feedback | Resolution |
|---|---|---|
| F1 | Folder facets need an "All" option and a way to clear filters | Added "All folders" + "Clear" in the rail and a filter chip row with "Clear all filters" (B v2) |
| F2 | "Uncategorized" is wrong; those items simply aren't in a CalTopo folder. Wants language suggestions | Open → UI-10 |
| F3 | Use C's light contour lines as background in a few places | Done in B v2 (title block of the rail) |
| F4 | "25 waypoints will use onX's default pin" sentence is text taking up space | Removed; the default pin stays visible per row and as an icon facet |
| F5 | "10 batches" means nothing on this screen (confused even the user) | Removed from this screen; explain imports at export time / in the runbook |
| F6 | Total markup count isn't relevant here | Removed the map-level totals (per-folder counts stay in the facets) |
| F7 | Don't show the file name, only the CalTopo map title | Done: "Bitterroots (Complete)" only |
| F8 | B was missing the "More" action that A and C have | Added "More ▾" to the selection bar |
| F9 | Color column: just show the color, no label | Swatch only (name in tooltip / aria-label) |
| F10 | Could icon and color be one mark (red camp → blue camp)? Wants renderings; may be overkill | Open → UI-11 |
| F11 | Notes: clicking should open the full note for reading/editing, multi-line | Mocked as an inline expanding textarea; current behavior investigated → UI-13 |
| F12 | How do multi-line notes carry into onX — plain text or HTML? Don't assume | **Unverified.** No onX doc or repo evidence settles it; only indirect evidence that multi-line `<desc>` lands verbatim. Needs a manual import probe (see `TODO.md`) |
| F13 | 100 items in a folder: paginated or one long list? | One long list: every row is built, no paging; collapse only hides. Measured locally: 1,500 rows load+render 0.21 s, ~70 ms per filter keystroke; 5,000 rows 0.69 s / ~190 ms. No pagination needed within onX's 1,500-markup limit |
| F14 | Filter / select by icon type | Added "onX icon" facet in B v2; not built in the app yet → `TODO.md` |
| F15 | "Load another map" is unclear; user assumed it merges maps | Investigated: it **clears** the current map. → UI-12 |
| F16 | Counts are ambiguous (items vs waypoints vs lines) — clarify in docs, not on the site | `web/README.md` "What the numbers mean" |
| F17 | "Export for onX" → "Export" | Applied in the app |

### UI-10 — Label for items that aren't in any CalTopo folder
Status: **provisional — "Unorganized"** (user's suggestion, 2026-10-21; explicitly not final —
the user is still unpacking how folder filtering should work). Mocked in B v2 with the subtitle
"Not in any CalTopo folder". The candidates below stay live alternatives.

Context: the app shows "Uncategorized". It comes from `cairn/core/parser.py:245` (items with no
or a dangling `folderId`, only when the map has at least one folder) and is re-applied in
`web/bridge.py:127`. The same string becomes the export folder (`NN_Uncategorized`) and the
runbook's "rename the onX import folder to …" line — so this label is also what the user types
into onX. Whatever is chosen should live in one shared constant. Mocked placeholder in B v2:
"Not in a folder", italic in the rail to set it apart from real folders.

Candidates (researched by a subagent; judged on clarity to a CalTopo user / fitness as an onX
folder name / sidebar length):

- **Not in a folder** — clearest for someone who sees these at the map's top level in CalTopo;
  a bit long, reads as a phrase rather than a name.
- **No folder** — very short and unambiguous; can read like an error.
- **Unfiled** — short, familiar from mail/file apps; slightly jargon-y as an onX folder name.
- **Map top level** — exactly describes CalTopo's structure; technical for onX users.
- **Loose items** — plain and easy to picture; informal.
- **Ungrouped** — standard in software; jargon for many people.
- *(variant)* **"<Map title> — not in a folder"** — e.g. "Bitterroots (Complete) — not in a
  folder"; self-explanatory as an onX folder name once imported, long in the sidebar. Could use
  the short label in Cairn and this long form only for the onX folder/runbook.

### UI-11 — Icon and color as one mark?
Status: decided 2026-10-21 — **3 · onX-style map marker**, accepting taller rows. User's reason:
it's closest to how onX renders the waypoint, so it shows what Cairn will actually export.
Applied in B v2: the separate Color column is gone; the marker is the icon cell and the click
target for changing both.

Options (rendered in `IconColor.dc.html`, each shown in Red / Blue / Yellow / White / Black):

- **1 · Tinted line icon** — icon stroke drawn in the onX color, over a dark outline so yellow
  and white survive on paper. Lightest; thin colored strokes are hard to tell apart.
- **2 · Color disc, icon knocked out** — a filled circle in the onX color with the icon in
  black or white for contrast. Compact; color reads first.
- **3 · onX-style map marker** — a teardrop pin in the color with the icon inside; previews the
  map. Most literal, tallest, and a stand-in for onX's own artwork.
- **4 · Ink icon on a color field** — icon chip with a color tab attached; one click target but
  icon and color stay separable.
- **Keep them separate** — current B v2: icon + name, then a color swatch column.

Also mocked: clicking the mark opens one popover holding both the color palette and the icon
search.

### UI-12 — "Load another map"
Status: decided (copy); merge feature deferred

Finding: the button resets everything (`web/app.js` `.newmap` handler: `DATA = null; EDITS =
{}` …) and returns to the drop screen. It does **not** merge maps. The user expected (or wanted)
merging several CalTopo exports (e.g. three people's Bitterroots maps) into one onX export.

- **Relabel to "Start over with a different map" + tooltip** — ✔ chosen for now; tooltip says
  combining maps isn't supported yet.
- **Build merge ("Add another map")** — deferred to `TODO.md` as a feature; the engine has
  dedup/merge code (`cairn/core/merge.py`, `dedup.py`) not yet wired into the web app.

### UI-13 — Reading and editing notes
Status: proposed (B v2)

Finding: today's note cell is a single-line `<input>` (`web/app.js` `desc-in`); long notes are
cut off and Enter commits, so there is no way to type a line break. Worse, line breaks never
reach the UI: `strip_html` (`cairn/utils/utils.py`) collapses all whitespace at parse time, so
multi-line CalTopo notes are flattened before Cairn shows or exports them (7 of 189 notes in the
Bitterroots fixture).

- **Inline expand to a textarea** — proposed in B v2: click the note (pencil affordance) and the
  row grows into a multi-line editor with Done/Cancel.
- **Side panel / drawer** — not mocked; an alternative if inline growth disturbs the table.
- **Modal** — not mocked; heaviest.

---

## Round 5 — Wording and the combined marker (2026-10-21)

### UI-14 — Name of the "everything" folder facet
Status: **provisional — "All"** (user's suggestion; not final, same open question as UI-10).
Previously mocked as "All folders".

### UI-15 — Drop "onX" from field labels
Status: decided 2026-10-21. "onX icon" → **Icon**, "Notes for onX" → **Note**, "onX default
pin" → **Default pin**. Rationale: the whole tool is about onX; repeating it on every label is
noise. ("Export for onX" → "Export" in F17 was the same call.)

### UI-16 — Changing icon + color now that they're one marker
Status: proposed — `EditMark.dc.html`

- **One item:** click the row's marker → a popover with a large live preview of the marker
  (name, "Icon · Color", and what it was before), the 10 onX waypoint colors, an icon search with
  icons suggested from the item's name, every icon drawn as a marker in the chosen color,
  "Browse all 95", Cancel / Apply.
- **Several items:** "Change icon & color" in the selection bar → a dialog with a Now → After
  list per item, color and icon each defaulting to "Keep each one's", and a note that lines take
  only the color (lines have no icon). Apply names the count ("Apply to 4").
- Not yet mocked: lines use onX's 11-color track palette (adds Fuchsia) — the bulk dialog will
  need to reconcile the two palettes when waypoints and lines are mixed.

### UI-16 revisions (2026-10-21, user feedback on `EditMark.dc.html`)
Status: accepted with changes ("look okay")

- "Keep each one's" → **"Use existing"** (color and icon) — then → **"Reset"**, see UI-18.
- Removed the "Was: Default pin · Red" line from the single-item preview; Cancel is enough to
  signal you can revert.
- Every confirm button reads **"Apply"** (was "Apply to 4") — consistent button language.
- Previews are **live**: the artboard is now interactive. Picking a color or icon re-renders the
  big preview, the icon grid, and every Now → After row in the bulk dialog; "Use existing"
  restores each item's own value; Cancel resets. The real build must do the same.
- Icon picks in the bulk dialog are drawn in the chosen color (or a neutral red when color is
  "Use existing").

### UI-17 — What's in "More"
Status: proposed

Finding (`web/index.html:67-72`, `web/app.js:447-452`): today's menu (labelled "Advanced") has
exactly three actions — **Use description as name**, **Leave out of the onX export**, **Put back
in the export**. It does **not** batch-rename or batch-change notes. The only bulk rename in
the web app is "use the note as the name".

- Mocked in `EditMark.dc.html`: the three existing actions (reworded: "Use note as name",
  "Leave out of export", "Put back in export") plus **Rename…** and **Change note…**, flagged
  "not built". Rename would cover prefix/suffix and find/replace with a preview (the old TUI
  backlog asked for the same).

### UI-18 — Button and label language review
Status: **decided 2026-10-21** — all suggestions accepted, with one change: "✕ Clear selection"
becomes **"Clear"** (not "Deselect"). Applied to the mockups and the live app. In the live app,
"Set icon…" / "Set color…" stay separate until the combined Icon & color editor (UI-16) is built.

User: "Use existing" → **"Reset"** (more natural; decided). Then: button language across the
project isn't standard UI/UX — review it and simplify.

Rules proposed for every label:

1. **Short verb (+ object only when needed):** 1–2 words. "Export", "Apply", "Rename".
2. **Sentence case**, no emoji, no arrows, no "✕ " prefixes in text (icon-only close buttons
   keep an `aria-label`).
3. **Ellipsis (…) only when the command opens a dialog for more input** (Rename…, Choose
   file…), never on buttons that act immediately.
4. **One pair for confirm/dismiss everywhere: Apply / Cancel.** No "Done", no "Apply to 4".
5. **Explanations go in tooltips or help, not in the label** ("Start over with a different map"
   carries its meaning in the tooltip).
6. **One name per thing:** Note (not description), Icon (not onX icon), Lines (one term for
   tracks/lines).

Current label inventory with suggestions (alternatives kept for later rounds):

| Where | Current | Suggested | Alternatives / note |
|---|---|---|---|
| Rail / summary | Start over with a different map | **Start over** | "New map"; tooltip keeps the explanation |
| Rail / summary | Export | **Export** | — (already simplified, F17) |
| Done screen | Download .zip | **Download** | "Download files" |
| Done screen | ← Back to editing | **Back** | "Edit more" |
| Drop zone | Choose a file… | **Choose file…** | "Browse…" |
| Header | ☀️ Light | **Dark mode** toggle (light is now default) | icon-only with aria-label "Theme" |
| Header | Help | **Help** | — |
| Selection bar | Set icon… / Set color… (app), Set icon / Set color (B v1) | **Icon & color…** (one button, since they're one marker) | "Edit marker…" |
| Selection bar | ✕ Clear selection | ~~Deselect~~ → **Clear** ✔ (user's choice) | "Deselect", "Clear selection" |
| Selection bar | Advanced ▾ (app) / More (mockups) | **More** | — |
| More menu | Use description as name | **Use note as name** | "Name from note" |
| More menu | Leave out of the onX export | **Exclude** | "Don't export" |
| More menu | Put back in the export | **Include** | — |
| More menu (new) | Rename… / Change note… | **Rename… / Edit note…** | — |
| Row (excluded) | excluded · restore | **Excluded** label + **Include** action | — |
| Filters | Clear (rail) + Clear all filters (chip row) | **Clear filters** (one, in the chip row; rail "All" already resets folders) | — |
| Filters | All types / Waypoints / Lines & tracks / Areas (app); All / Waypoints / Lines (mockup) | **All / Waypoints / Lines / Areas** | keep "Areas" only if the map has any |
| Filters | Needs an icon (checkbox) | **Default pin only** (matches the icon facet) | — |
| Search | Search names and descriptions… | **Search** (placeholder "Name or note") | — |
| Note editor | Done / Cancel | **Apply / Cancel** | — |
| Icon editor | Apply / Cancel | **Apply / Cancel** | — |
| Bulk editor chips | Use existing | **Reset** ✔ decided | — |
| Modals | ✕ (text) | icon-only close, aria-label "Close" | — |

### UI-19 — One theme only
Status: decided 2026-10-21. Supersedes UI-03.

User: set aside dark/light themes; Cairn has a single theme. That theme is the light,
field-guide look (UI-01, UI-06). No toggle, no `prefers-color-scheme` variant.

Applied now: the theme toggle, `web/theme-init.js`, `setTheme()` and the light-variant CSS were
removed from the live app, which keeps its current (twilight) colors until the CSS rebuild
replaces them with the field-guide theme. The options UI-03 offered (dark-first, follow the OS)
stay recorded there if this is ever reopened.

### UI-20 — Where the contour lines go
Status: decided 2026-10-21. Revises F3 / round 4.

User: the contour lines made the text hard to read; they belong in the center frame, behind
all the text boxes — "sent to back". Applied: removed the inline contour SVGs (rail title
block, drop target, icon popover header). One contour layer is now the page background; the
rail and every card, field and dialog are opaque, so lines only show in the gaps. Text not
already in a box (the empty screen's intro, the done screen) sits on a paper panel.

---

## Engineering decisions from the PR #20 red-team review (2026-10-21)

### ENG-01 — Engine wheel cached as "immutable" under an unchanged filename
Status: **reversed 2026-10-22** — every site file is now served `Cache-Control: no-cache`.

Reversal: the owner hit it on the live site — "cannot import name 'input_check'" after a deploy, because the browser kept the year-cached old wheel while `bridge.py` (1-hour cache) updated. Every returning visitor hits this on every engine-changing deploy, which was not the impact the original call assumed. `web/vercel.json` now sends one rule, `no-cache`, for all of `web/`: the browser keeps its copy but revalidates (ETag, a 304 when unchanged), so the wheel, `bridge.py` and `app.js` always arrive as a matching set. Pyodide from jsDelivr is unaffected (versioned URL). `test_site_files_always_revalidate` guards it. The original decision follows.

Original status: decided — **accept the risk**.

Finding: `web/dist/cairn_maps-1.0.0-py3-none-any.whl` changed content but kept its name, and
`/dist/*` is served `public, max-age=31536000, immutable`. A visitor whose browser cached the old
wheel gets an import error ("Failed: …") after deploy until their cache clears.

Options considered: bump the package version so the wheel gets a new URL; serve it from a
content-hashed path; drop `immutable`/long max-age for the wheel; plus a CI check that the
committed wheel matches the source. **User's call:** breaking previous visitors is acceptable —
the site has no serious production users — so none of these were done. Revisit before the site
has real users: any later change to `cairn/` re-creates the same failure.

### ENG-02 — Mobile is out of scope
Status: decided 2026-10-21.

User: no optimization for mobile — it's outside the project's scope, and importing/exporting
map data on a phone is not a use case Cairn will encourage or support. Cairn is a desktop
browser tool.

Consequences:
- Closes the red-team item "On phones, Export sits at the foot of a long filter rail" as
  **won't fix** (options were a collapsible Filters disclosure or a sticky Export bar).
- Don't add phone-specific layouts, mockups, screenshots or tests going forward. The narrow-width
  CSS already in the app stays as harmless fallback but is not maintained as a target; it may be
  removed if it ever gets in the way.

### UI-21 — Confirm before "Start over"
Status: decided 2026-10-21. Closes the red-team item "Start over discards all edits".

User: show a pop-up confirmation when someone clicks Start over. Built as an in-page dialog
(not a browser `confirm()`): "Start over?" with Cancel (initial focus) and a destructive
"Start over". When edits exist it states how many unexported changes will be lost.

Other options considered: an undo toast after the reset; moving the button away from Export.

### UI-22 — Prompt to save an open note on Export
Status: decided 2026-10-21. Closes the red-team item "A note left open is dropped on Export".

User: if anything is unsaved when Export is clicked, prompt to save. Dialog "Save your note?"
with Apply (save, then export; initial focus), Discard (export without it) and Cancel (back
to the editor). An open but unchanged note just closes.

Other options considered: silently apply the draft; block Export while a note is open.

### UI-23 — Selection is limited to visible rows
Status: decided 2026-10-21. Closes the red-team item "Select-all includes collapsed folders".

User: select-all should be limited to visible rows. Select-all (Ctrl/Cmd+A), shift-range and the
"selection follows the screen" pruning now skip folders the user collapsed; collapsing a folder
drops its rows from the selection. The "Showing N" chip still counts every filter match.

Other option considered: keep hidden rows selected and show a "N hidden rows selected" notice.

### ENG-03 — Narrow the CSP's CDN allowance
Status: decided 2026-10-21 (user approved the narrow option).

`script-src` and `connect-src` now allow `https://cdn.jsdelivr.net/pyodide/v0.29.5/full/`
instead of all of `cdn.jsdelivr.net`, so no other jsdelivr content can run in the page. Verified:
boot, load, export and download under the enforced CSP with zero violations; a test pins the
CSP path to the Pyodide version the app loads.

Not done (still open): self-hosting Pyodide and the pinned packages so every engine file is
served from our own origin with integrity — about 10–15 MB more per deploy.

### UI-24 — Landing tagline and product scope
Status: decided 2026-10-22.

- Tagline: **"CalTopo to onX, with icons and colors that still mean something."** Chosen over
  "Move your CalTopo map to onX and keep it filterable." (jumps to the solution without naming
  the problem), "Fix your map before it lands in onX." and "Your CalTopo map, still organized
  in onX." Shown in italics under the kicker and used as the page's meta description.
- The kicker stays **"CalTopo → onX Backcountry"**, and step 3 says "onX Backcountry": onX also
  ships Hunt, Fish, Offroad and other products that Cairn has not been tested against, so Cairn
  states it supports **onX Backcountry only** for now.

### ENG-04 — CalTopo KML/GPX input decisions (2026-10-22)
Status: decided.

- **CalTopo's dashed line** (GeoJSON `pattern` `M0 -1 L0 1,,8,F`) exports as onX `dash`. This
  changes 6 Bitterroots lines from solid to dash. Accepted.
- **CalTopo KML type folders** ("Points", "LineStrings", "Polygons"; 2016 "Markers", "Lines and
  Polygons") at the top level mean "no folder" and become **Unorganized**, matching GeoJSON. A
  user folder with one of those exact names is folded in too; accepted.
- **6-digit KML colors** (`BBGGRR`, no alpha; CalTopo never writes them) are read as the color at
  full opacity — a solid line — instead of invalid/default blue. (Revised by the owner the same day.)
- **Left as is** (CalTopo never writes it): a placemark inside `Folder > Document` is dropped.
- **Multi-part KML lines** (one placemark, several separate `<LineString>`s) become several onX
  tracks with the same name. **Provisional, subject to revision on user feedback.** Alternative to
  test: one GPX `<trk>` with one `<trkseg>` per part — a single entity in the GPX format; whether
  onX keeps it as one Track with gaps, joins the gaps, or splits it is unknown. Include one in the
  onX import test before deciding.

### ENG-05 — Areas are exported as GPX onX Area routes, not KML (2026-10-22)
Status: decided; the holes trade-off is **provisional**.

Evidence, from a real onX Web Map import on the owner's account (2026-10-22):

- **onX ignores area color and fill in KML.** Cairn's `Areas.kml` (KML `Style` with `LineStyle`
  / `PolyStyle`, plus onX-style `ExtendedData` `color` / `fill_color`) imported with onX's
  defaults: outline `rgba(255,51,0,1)`, fill `rgba(74,144,226,0.1)`. Probes with the
  `ExtendedData` colors written with spaces, an inline KML `Style` only, and a shared `styleUrl`
  style all came in as the default red.
- **A GPX `<rte>` with `<type>Area</type>`** and `<extensions><onx:color>rgba(255,255,0,1)
  </onx:color><onx:fill_color>rgba(255,255,0,0.3)</onx:fill_color></extensions>` imported as a
  real onX Area (acreage shown) **with its yellow color**. *Correction 2026-10-23
  (`docs/ONX_ROUND_TRIP.md#area-fidelity`):* onX's importer keeps `<onx:color>`, `<onx:style>`
  (solid / dash / dot) and `<onx:weight>` (2.0 / 4.0 / 6.0), and never reads the fill. Not
  onX's own swatch values re-imported byte for byte, not `rgba(0,0,0,0)` ("None"), not six
  other encodings: every imported area stores no fill and exports the default
  `rgba(74,144,226,0.1)`. PR #41 had the conclusion right but guessed the reason (non-swatch
  values); it is not the value, the field is ignored.
- **onX does not parse a key=value `<desc>` on import**: a desc of `name=…\nnotes=…\ntype=Area\n
  color=…` became the Notes verbatim. So `<desc>` carries only the user's note text, as the
  waypoint and track writers already did.
- onX's own GPX export of an area
  (`tests/fixtures/caltopo-random/onx_roundtrip/from_geojson/onx_export.gpx`) is
  `<rte><name/><desc>key=value…</desc><type>Area</type><extensions><onx:color/><onx:style/>
  <onx:weight/><onx:fill_color/></extensions><rtept/>…</rte>` (`<onx:style>` is absent when
  the area has none stored). onX areas have a line palette (the 11 track colors) and a separate
  **fill palette**: 10 swatches at alpha 0.1 plus None (`AREA_FILL_PALETTE`). Tracks (color, dash style, weight 6.0, multi-line notes) and
  waypoints round-tripped from Cairn's GPX in the same import.

Decision:

- `cairn/core/writers.py:write_gpx_areas_maybe_split` writes each area as that `<rte>`: `<name>`
  (sanitized like every other name), `<desc>` = note only (omitted when empty), `<type>Area</type>`,
  then `<onx:color>`, `<onx:style>`, `<onx:weight>`, `<onx:fill_color>` in onX's order, all from
  `writers.area_onx_style` (2026-10-23): an onX file's values pass through exactly (dot, 2.0 and
  None included) unless the user edits them; a CalTopo area's style and weight map from its
  `pattern` and `stroke-width` as a track's do, and its fill is the nearest onX fill swatch to
  CalTopo's `fill` (to the line colour when there is none), or None for `fill-opacity` 0. Then
  the closed outer ring as bare `<rtept lat lon/>`. Size-split at 3.75 MiB like the other GPX
  writers. File: `<Folder>_Areas.gpx`. The KML area writer writes the same four values as
  ExtendedData (and the fill as its PolyStyle).
- The web export (`web/bridge.py:export_zip`) uses it; no web export writes KML any more, so the
  runbook's "contains KML, Web Map only" warning is no longer triggered. The KML area writer is
  kept for its other callers and tests.
- Area line style and weight are written and edited like a line's (UI-25). (Until 2026-10-23
  they were not, on the mistaken belief that onX's area export carried only color and fill.)
- The fill is written for format fidelity only. Cairn shows it but offers no fill choice: onX
  would discard it on import.
- **Holes — provisional, subject to revision.** An onX area is single-ring, so a polygon with
  holes is written as its outer ring only (the hole is filled in) and listed in RUNBOOK.md under
  "Holes not kept in onX" (since UI-31 round 4: one line under the area in instructions.txt). Not tested: whether onX can keep a hole through any import path (e.g.
  KML `innerBoundaryIs` — which would bring back the default-color problem), or whether writing
  each hole as a separate area would serve users better.
- Bitterroots' export changed only in its 6 area files (`*_Areas.kml` → `*_Areas.gpx`, 17 areas;
  names, notes, colors, fills and outer rings identical to what the KML carried; no holes) and
  RUNBOOK.md (those file names, and no KML sentence).

### ENG-06 — Names pass through unchanged (onX verified 2026-10-22 r1 probe)
Status: decided; revisitable if onX sorting issues are ever reproduced.

Cairn used to drop `! @ # $ % ^ * &` from waypoint, track and area names
(`sanitize_name_for_onx`), citing "onX sorting issues" that nothing in the project's sources
ever confirmed. On a real onX account (round r1 of the round-trip harness) onX imported and
re-exported these names unchanged: `ZZTEST r1 hash #2 & amp`,
`ZZTEST r1 bang! at@ dollar$ pct% caret^ star*`, `ZZTEST r1 quote's "dq" (paren) <lt>`.
Stripping therefore altered user data on every onX -> Cairn -> onX pass, the primary use case.

Options considered:
- **Keep stripping** (and report it under "Renamed for onX"). Rejected: no evidence of benefit,
  proven harm to round trips.
- **Pass names through unchanged.** Chosen.
- **Make stripping optional.** Rejected for now: a setting for a problem nobody has reproduced.

Decision: pass-through. `sanitize_name_for_onx` is now an identity returning `(name, False)`;
XML escaping stays in the writers and whitespace trimming at load time. The "Renamed for onX"
tracker and RUNBOOK section are kept but are always empty (they stay as the place to report a
rename if one is ever needed again). Dark Divide `cairn_output` baselines and `PARITY.md`
changed only in the five `#1` / `#2` track names (now identical to the review screen).

### ENG-07 — Stable item ids and folder primitives (2026-10-23, folders PR-A)
Status: decided. Engine half of the approved folders feature (rename, merge on a duplicate
name, drag to a folder, + New folder, More ▸ Move to…); the UI is PR-C.

**Item ids.** An item's `uid` used to be `<folder key>::<kind>::<index within kind>`, and that
position was load-bearing: `export_zip` dropped excluded items by decoding the index, and pushed
edits onto features by zipping items with the folder's feature list. Moving an item would have
pointed every edit and exclusion at the wrong feature. Now:
- `uid` (name unchanged, so web/app.js needed no logic change) is an opaque id, `i0`, `i1`, …,
  numbered in load order across every folder and file. It never changes while the map is open
  and encodes no folder or position. The same file loads with the same ids.
- `_STATE["features"]` maps uid → the ParsedFeature the writers read. The groups (in order, and
  each group's `items` in order) are the only record of where an item is; `export_zip` iterates
  them and reaches each feature by uid. `doc.folders` stays as parsed (the folders as loaded);
  the tests derive the current folders from the groups (`_doc_folders`), and export reads neither (round 3: the copy kept in step by every move was a second record).
- A map with no moves or renames exports byte for byte as before (Bitterroots sha pin). The
  pinned load-JSON hash in that test is compared after rebuilding the old uid strings, the only
  change to that baseline check.
- Nothing may parse a uid. EDITS, SEL, ANCHOR, NOTE_EDIT, POP and BULK key by it as before.

**Primitives** (web/bridge.py; JSON in/out like `apply_edits`; no UI yet):
- `rename_folder(key, name)` → `{"ok": true, "key", "name", "safe"}`, or when another folder
  has that name `{"ok": false, "name", "duplicate": {"key", "name", "count"}}` with nothing
  changed, so the UI can offer "Move the N items into it?" → `merge_folders`.
- `move_items(uids_json, target_key=None, new_name=None)` (exactly one target) →
  `{"ok": true, "key", "created", "moved", "removed": [emptied keys], "folders": layout}`, or
  the duplicate report when `new_name` is taken. `layout` is every folder in order as
  `{"key", "name", "safe", "uids"}`: the UI rearranges its own copies of the items from it.
- `merge_folders(source_key, target_key)` → the same success shape; the target keeps its name
  and place.

**Rules.** An item is in exactly one folder. A folder a move or merge leaves with no items is
removed, and `removed` names exactly those; a folder that loaded empty (a CalTopo folder with no
members) or whose items are all excluded stays. Names are trimmed and must be non-empty (else ValueError);
inner spacing and case are kept. Two folders may not share a name compared trimmed and
case-insensitively (`casefold`); renaming a folder to its own name in another case is allowed.
A clash is reported, never merged silently. New folders get a fresh key (`new:N`) and take
their sorted place (folder order, below; they went at the end until 2026-10-24). Moving an item to the folder it is in does nothing. Moved items keep the map's
order (not the order given) and go to the end of their kind's run in the target, so a folder
is still waypoints, then lines, then areas. Unknown uids or keys, an empty list or both/neither
targets raise ValueError and change nothing. "Unorganized" is a folder like any other: it can
be renamed, emptied (and so removed) and moved into.

**Round 5: duplicate names at load.** The one-name-per-folder rule above covers rename, + New
folder and Move to… only. A loaded map can already have two folders with the same name (CalTopo
allows it); both load as they are, and export tells the twins apart by their `NN_` zip folder
(UI-32). Nothing merges them unasked.

**Round 4 (2026-10-23): an empty folder up front (UI-32).**
- `create_folder(name=None)` → `move_items`' success shape with `"created": true, "moved": 0`:
  an empty folder (in its sorted place since 2026-10-24), named `default_folder_name()` unless a name is given; a taken
  name gives the duplicate report with nothing changed; an empty name raises.
- `remove_empty_folder(key)` → `{"ok": true, "removed": [key], "folders": layout}`; a folder
  with items, or an unknown key, raises ValueError and changes nothing.
- So the rule above becomes: a folder a move or merge EMPTIES is removed; one made empty, or
  loaded empty, stays until then (or until `remove_empty_folder`).
- `export_zip` numbers only folders with items: an empty folder writes nothing and takes no
  `NN_` number (the width counts numbered folders), so the ones after it close up. A folder
  whose items are all excluded keeps its number, as before.

**Round 2 (2026-10-23).**
- Each group (and each layout entry) carries `unorganized`: true only for the items outside every
  folder of the file (the reader's `orphaned_features`, or a nameless folder), decided at load by
  where they came from, never by name, so a real CalTopo folder called "Unorganized" is ordinary.
  `rename_folder` clears it, and renaming those loose items back to "Unorganized" sets it again.
- `rename_folder` success also returns `unorganized` and `folders` (the layout), so the UI
  rebuilds from it like after a move. `layout_json()` returns `{"folders": layout}`: the UI
  re-syncs from it whenever applying an answer fails.
- `default_folder_name()` is the first free one of "New folder", "New folder 2", … by the same
  trimmed, casefolded rule; `move_to_new_folder(uids_json)` is `move_items` into it. The UI no
  longer picks the name and retries.
- Folder names lose control characters (newline, tab, NUL, …: each run becomes one space) on load
  and on rename. RUNBOOK.md's code spans were fenced with one more backtick than the longest run in
  the text, so "Rename it to:" showed a name with backticks exactly; instructions.txt (UI-31
  round 4) is plain text and writes the name as is.
- `_safe` cuts to 80 UTF-8 bytes in one slice (the old char-at-a-time loop was quadratic); the
  result is the same.

**Folder order (owner feedback 2026-10-24; replaces "sorted by size once at load").** Folders
are sorted by name: natural (digit runs compare as numbers, so "1 - …", "2 - …", "10 - …"),
case-insensitive (`casefold`), stable (twins, "Camp" and "camp" from a file, keep their load
order). The loose items (`unorganized`, by the flag, not by name) come last: they are not a
real folder. Loading sorts; a new folder (`move_items` with `new_name`, `create_folder`) and a
renamed one take their sorted place; a move or merge doesn't reorder (names don't change).
Renamed away from "Unorganized" the loose items are an ordinary folder and sort by their new
name; renamed back, they are last again. `bridge._sort_folders` is the one place the order is
made, and the UI only follows the layout, so the table, the rail, the Move to… list and the
export agree. The old order read as unnatural (Dark Divide: "3 - …, 2 - …, 1 - …").
Re-pinned: the Bitterroots export pin (NN_ names and instructions.txt only; every GPX member's
bytes unchanged) and the Dark Divide cairn_output folders (renumbered, same bytes).

**Export numbering and the runbook.** Export's `NN_` prefix and the runbook's step
number are each folder's current position (1-based, folder order) at export time, so removing
a folder closes the gap. `NN_` is two digits, or as many as the folder
count needs from 100 folders on (`001_` … `120_`), so a file list still sorts in order; maps
under 100 folders are unchanged (Bitterroots pin). Each manifest entry names its directory
(`dir`). The last export keeps the zip itself (not a second copy of every file);
`export_folder_zip(n)` copies that folder's members out of it as stored (compressed bytes,
not recompressed), and the page names the download `<dir>.zip` from the manifest. The runbook's
heading and "Rename it to:" line use the current display name, shown exactly (backslash escapes
in the heading and "(folder)" notes, a code span in "Rename it to:"). As before, a folder whose items are all excluded still
takes a number but writes no files and gets no runbook step.

**File names for a renamed folder.** `safe` is recomputed with the existing `_safe()` (strip
everything but word characters, spaces and hyphens; spaces/hyphen runs → `_`; empty →
`Unnamed`) and names the folder's directory and file stems (`02_Trip_1_AB/Trip_1_AB_Tracks.gpx`).
The GPX's own folder name is the display name, unchanged. Two names with the same `safe` form
("Trip 1" and "Trip-1") can't collide in the zip: the `NN_` directory differs.

Options not taken: uuid4 ids (nondeterministic, unhashable load JSON); keeping the old uid
string as an opaque value (it would still read as a position and invite parsing); auto-merging
on a duplicate name (the owner wants the merge offered, RenameMerge mockup); re-sorting folders
by size after each move; sorting folders in the UI only (two collators could disagree with the
export's numbers).

### UI-25 — Line style and weight editing
Status: decided 2026-10-23 (from the line-style option canvas: 2C, and the Style / Weight
dialog). Engine support already existed (`apply_edits` `style`, `weight`).

- **One line** (2C): the row's line mark opens the popover with the line drawn on a strip of
  contour paper, the color row spread to full width, and below it two titled groups,
  **Style** (solid, dashed) and **Weight** (thin, thick), whose four toggles line up with the
  palette. The toggles show only the drawn line, no words (screen readers and hover still name
  them).
- **Several lines**: a **Line style…** button in the selection bar, shown only when the selection
  has lines, opens a dialog titled **Line style**: the selected lines drawn long in their own
  colors, then the same Style and Weight groups. Picking the selected toggle again un-picks it,
  and an un-picked group leaves each line as it is. Color stays in Icon & color….
- The list draws every line's mark in its real style and weight; the row label stays "Line".
- Dotted (and weight 2.0) are not offered as choices, though onX has all three styles and weights
  (2026-10-23: `dot` and `2.0` appear in onX exports). A dotted or 2.0 line or area outline from
  an onX file is drawn as such and exported exactly as it came in unless changed (tracks:
  `writers.line_onx_style_weight`; areas: `writers.area_onx_style`). Editing it offers only the two
  styles and two weights, and dot / 2.0 are refused as edit values. A CalTopo line still maps to
  4.0 / 6.0 by stroke width.
- **Areas too (2026-10-23):** an area's outline takes the same Style and Weight (popover and
  Line style… dialog), solid / dashed and 4.0 / 6.0 only. An onX area's dotted or 2.0
  ("Extra thin") outline is drawn and kept unless changed. No fill choice is offered: onX's
  importer ignores area fills (ENG-05).
- Options not taken (canvas): style rows with word labels (2A), one 2×2 sample grid (2B), Style
  and Weight inside Icon & color… (3A/3D), toggles in the selection bar with no dialog (3F).

### UI-26 — Modals don't over-explain
Status: decided 2026-10-23 (owner, as a rule).

A popover or dialog shows what is being changed, not instructions about it: section titles and
the controls themselves, no explanatory sentences or example-laden placeholders. Applied now:
"Lines take the color only." removed (three places); the icon search placeholder is "Find an
icon" (no "— try “climb”, “water”, “camp”"). Confirmations that say what will be lost (Start
over, unsaved note) stay. Help is documentation and is exempt.

Also removed (2026-10-23, owner's example "Line · Brown"): the words under the name in the
single-item popover ("Summit · Red", "Line · Brown") and beside each After mark in the
several-items dialog ("Camp · Blue"). The drawn marker or line already shows the choice.


Audit of the whole app page (2026-10-23): removed the note editor's "Line breaks kept" hint, the
Start over tooltip ("Clears this map and your edits. To combine several files, drop them
together at the start." -- the confirmation already says what is lost), the note button's
tooltip ("Becomes the markup's Notes in onX") and the folder checkbox tooltip ("Select every row
shown in this folder", which repeated its label). Kept: the Excluded row tooltip, the CalTopo GPX
source notice (2026-10-24: now a line in Help, not a banner), the note-over-limit, dropped-item and markup-limit warnings, and the runbook
text. Edit commits now read "Save", not "Apply" (note editor, icon & color popover and dialog,
Line style dialog, "Save your note?"). The note editor opens with the caret and scroll at the
start of the note.

### UI-27 — Page footer; no loading or version text; quiet loading
Status: decided 2026-10-23 (owner).

- Every page carries one persistent footer line, small (12px), links separated by middle dots:
  **Help · FAQ · Walkthrough · GitHub**. Links only, no contact info. It is on `index.html` (all
  stages), `faq.html` (generated by `scripts/build_faq_page.py`) and `walkthrough.html`. Help is
  the in-app modal; from the doc pages it links to `./#help`, and the app opens Help when loaded
  with that hash.
- The Help / FAQ / Walkthrough links at the top of the page and in the left rail are removed.
- The engine's loading status ("Loading Python runtime…", "Loading map engine…") and the
  "Ready · engine vX on GitHub" line are gone. The status area shows only real messages after
  load ("Changed 3 lines", errors). A boot failure is still shown. `window.__cairnReady` and
  `__cairnLoaded` stay.
- Quiet loading: nothing is shown while the engine boots. A file dropped or chosen before it is
  ready shows a brief "Getting ready…" on the drop area and is processed automatically when the
  engine is ready (queued, not rejected).

### UI-28 — Filters in the rail as folding sections; a smaller edit screen
Status: decided 2026-10-23 (owner, from the layout mockups; option C chosen).

- **All filtering lives in the left rail**, in three sections that fold: **Type** (All /
  Waypoints / Lines / Areas, each with its count — moved from the segmented control at the top
  right, which is gone), **Folders** (with counts) and **Icon** (checkboxes with counts, incl.
  *Default pin*). Each section has a header button (▾ open / ▸ folded, `aria-expanded`). Folding
  only hides the list: what is picked in it stays applied, and the folded header shows a short
  summary of it ("Waypoints", the folder name, "Default pin", "3 icons"; "All"/"Any" when nothing
  is picked). Fold state is not saved; a new map starts with every section open.
- **Applied filters show above the list as chips** (search, type, folder, each icon); × removes
  that one filter, "Clear all" removes them all. The search box stays at the top of the list
  column, now full width.
- Every filtering behaviour is unchanged: selection follows the visible rows (UI-23), Ctrl/⌘+A,
  shift-click ranges, collapsed folders, the Default-pin facet, counts.
- Rail head: Cairn wordmark with the map's source label ("CalTopo map") beside it, then the map
  title. Rail foot: status, Export, Start over (Help/FAQ/Walkthrough/GitHub stay in the page
  footer, UI-27).
- **The edit screen is scaled down; the pop-ups are not.** Body text 15→13px; small-caps labels
  11→10px; map title 30→21px; folder headings 22→17px; table rows 60→42px; row markers 30×38→22×28
  (line/area swatches 30×26→22×19); rail 300→248px; buttons and the search box 42→34px tall;
  Export 48→40px; rail paddings 26→18px. Fonts, colours and rules are unchanged. The single-item
  icon & color / line popover, the Icon & color… and Line style dialogs, the confirmations and
  Help keep today's sizes (the owner prefers the larger pop-up). The drop and done screens are
  unchanged. At 1440×900 the list shows 18 full rows (was 11).
- **Order (owner feedback 2026-10-24).** Each section is "All" first, then alphabetical:
  Type is All, Areas, Lines, Waypoints, listing only the kinds the map has (a kind with none
  shows only while it is the filter in use); Folders is All, then the folder order (ENG-07: by
  name, Unorganized last); Icon is *Default pin* pinned at the top, then the icons
  alphabetically (natural, any case). It was Waypoints / Lines / Areas, and icons most common
  first with Default pin last.
- Options not taken (layout canvas): A, every filter in the rail as flat lists that don't fold;
  B, one filter bar over the list with no facet rail. D (the icon popover at the smaller scale)
  was declined: the pop-ups stay at today's size.

### UI-29 — The icon picker is a list; glyphs travel left to right
Status: decided 2026-10-23 (owner, from the W5 icon study; option C chosen).

- **The icon picker is a two-column list** in both the single-item popover and the Icon & color…
  dialog: the neutral outline marker (24×30) on the left, onX's icon name on the right, 14px text,
  rows at least 44px tall, 4px row / 6px column gaps; the chosen icon has the green 2px border
  and the selected-row tint. A name wraps only between words, never inside one, and the marker
  stays vertically centred on its row. The popover stays 440px wide at 15px text (UI-28). The
  markers stay neutral ink outlines: picking a colour recolours only the item being edited.
- **The list is built once per open.** "Find an icon" toggles `hidden` on the buttons; a pick
  only moves `aria-pressed` and the selected styling; a colour click does not touch the list.
  Rebuilding it (as the old grid did via `innerHTML` on every pick) dropped keyboard focus to
  `<body>`; the e2e suite now checks focus and DOM identity across picks.
- Options not taken (icon canvas): **A** (marker band over two balanced lines, W5's
  recommendation), **B** and **E** are tabled. The feature is complete with C.
- **Follow-up held open: option D** (five columns of tiles). The owner kept it as a fallback while
  they use C in production. Two variants are drawn on the icon canvas
  (https://claude.ai/artifact/3RfqgwoQHBGdUYf9rzGsL9, row "Option D, iterated"):
  - **D1** centres a one-line name vertically in the two-line label band, so it sits level with
    the middle of a two-line neighbour. The text stays 12px, so "Snowboarder", "Campground" and
    "Mountaineer" still touch the cell edges.
  - **D2** shrinks the label font to 10px, the first size at which every name clears both cell
    edges by at least 4px. At 10.5px only "Visitor Center" falls short, with 3px.
  - The undrawn combination is D1's centring at 10.5px.
  - Revisit only if C doesn't hold up in use. The decision is then D1, D2 or that combination.
- **Every onX icon is drawn**; the two-letter abbreviations are gone. The 22 W5 glyphs were
  adopted except the skiing ones, which were redrawn.
- **Direction rule for glyphs:** anything that shows travel faces left to right; anything going
  down a slope descends left to right (high on the left, low on the right). Applied 2026-10-23:
  Ski Areas (a downhill skier, replacing the chairlift) and Snowboarder redrawn; RV (hitch on the
  right), Fish, Windsurfing (mast leading), Surfing Area (wave breaks to the right) mirrored;
  Kayak's paddle mirrored to lean like Canoe's; Snowmobile's windshield now rakes back. Ski
  Touring climbs left to right, which is still travel to the right; Skin Track (switchbacks), Ski, XC
  Skiing and Snowpark show no rider and are unchanged.

### UI-30 — Warn when an onX export's area fills will change
Status: decided 2026-10-23 (owner; wording option A).

onX gives every imported area its default blue fill (`rgba(74,144,226,0.1)`), whatever the
file says (docs/ONX_ROUND_TRIP.md #area-fidelity). When a loaded map has areas from an onX
export (they carry an onX id) whose fill is anything else, a transparent ("none") fill excepted (round 5: deliberate, and the
caution mark skips it too), a dialog shows once
on load:

> **N areas will lose their fill.** onX resets area fills to blue on import.
> [Leave these N out] · [Keep them]

- "Leave these N out" unticks exactly those areas, which leaves their originals in onX untouched.
  They stay in the list and can be included again.
- "Keep them" is the default focus, and so is Escape; it changes nothing.
- No dialog for CalTopo maps, or for onX areas that already have the default fill.
- The broader "This map came from onX" notice and the import-checklist steps (delete the
  originals; except the ones left out) are still to be worded.


### UI-31 — The export screen: one box per folder
Status: decided 2026-10-23 (owner, from the `ExportScreen.dc.html` mockup); revised the same day
in round 4 from the owner's edited mockup (export screen v2, and instructions.txt in place of
RUNBOOK.md). Release log: docs/testing/FOLDERS_RELEASE.md "Round 4".

The old screen confused the owner: an unlabelled tick box per folder looked like include/exclude
but only greyed the row, "Import all 1 file together" was ungrammatical, and a boxed explanation
sat at the top. Now:

- **Header:** "Export", "Your files are ready", then **Download all** (the zip: one `NN_Name/`
  folder per onX folder, in screen order, plus `instructions.txt`) with the italic hint "One
  zip, one folder inside it per onX folder". Back and Start over sit on the right.
- **One intro line**, the owner's wording with its comma splice made a semicolon: "Import each
  folder into onX's Web Map; onX will use a default datetime stamp for the folder name.
  Importing needs onX Premium or Elite." The warnings that apply (dropped items, long notes, over
  the account limit, KML) follow it, above the boxes.
- **One box per folder, and only:** the folder name as its heading (no counts), a **Download**
  button, and the file names as chips. The button's accessible name says which folder
  ("Download Lost Trail Pass"; "Download 02 · Camp" for a same-named twin, whose heading also
  shows "02 ·", UI-32). The three numbered steps of the first version are gone from the boxes:
  the intro line and instructions.txt carry them.
- **Download** is a zip of that folder's `NN_Name/` directory only, named after that directory
  (`02_Lost_Trail_Pass.zip`). Its files are the same bytes as in Download all:
  `bridge.export_folder_zip(n)` reads the last export, nothing is exported again.
- **Removed:** the tick box and its done state, the boxed paragraph, and no Copy button. The
  screen keeps no "imported" state.
- **instructions.txt** (round 4; it was RUNBOOK.md, Markdown): plain text with no Markdown
  syntax, UTF-8 without a BOM, CRLF line endings (Windows' own; every Notepad shows the lines,
  TextEdit and the rest read CRLF too; `.gitattributes` keeps the committed copies byte-exact).
  The general steps once at the top (import each folder's files together in the Web Map, tick
  "Import map data to a new folder", rename the date-named folder to the name shown, Premium or
  Elite needed), then each folder nested: `NN_Name/    rename to: <folder>`, each file, its item
  kind (Waypoints / Lines / Areas), and every item's name as written in that file, indented
  4 spaces a level. An item with no name shows "(no name)". Only two warnings stay, each one
  line under its item: a note onX will cut (its written `<desc>` is over 512 bytes) and an area
  whose hole is not kept. No area-fill line (round 5, owner: keep it basic; the row's caution
  mark covers fills, UI-34). Totals, dropped items, the account limit and the "Renamed" list (empty
  since ENG-06) are not in it; the screen shows the first three.

### UI-32 — Folders: drag to move, + New folder, rename and merge, Move to…
Status: decided 2026-10-23 (owner, from the DragToFolder, DragToNewFolder, NameNewFolder,
RenameMerge and KeyboardMove mockups). Engine: ENG-07. Release log: docs/testing/FOLDERS_RELEASE.md PR-C.

Owner rules: an item is in exactly one folder; a folder that empties disappears; no drag to
reorder folders, no item in two folders. (Round 4, 2026-10-23: an empty folder CAN be made up
front, by clicking + New folder with nothing ticked; see "+ New folder" below.)

- **Drag rows to a folder.** Press on a row and move 6px. If that row is ticked, every ticked
  row comes along, else just that row. A dark label follows the pointer: "Move 3 items" ("Move 1
  item"); the dragged rows dim. The drop targets are the folders in the rail's Folders list:
  the one under the pointer gets the green fill and dashed outline; the folder every dragged item
  is already in reads "here now" and isn't a target (a folder holding only some of them is).
  "+ New folder" sits at the end of the list. Dropping anywhere else, or Esc, does nothing.
  Excluded rows move like any other. The status line says "Moved 3 items to North Roots." or
  "…to a new folder."
- **Built on pointer events, not HTML5 drag and drop.** A row is mostly controls, the label must
  be our own element (styled, and visible in screenshots), and Esc must cancel and be testable.
  A drag doesn't start from a checkbox, from an open note, or from a name field you are already
  typing in (there a press-and-drag selects text). It does start from a name you haven't clicked
  into: the row's name is the obvious thing to grab, and the field is left unchanged. The click
  that ends a drag is swallowed. If the Folders section is folded, a drag opens it and folds it
  again after. The drop target is the one under the pointer where the button comes up. If the
  window loses focus or the browser cancels the pointer mid-drag, the drag is simply gone (no
  release will come, so nothing waits for one); a dialog that opens after the press stops a
  drag from starting.
- **Long rails.** The rail scrolls on its own, so with many folders "+ New folder" can be below
  its fold: holding the pointer near the rail's top edge, or near or over its footer, scrolls it,
  faster the deeper in.
- **+ New folder** takes the first free name of "New folder", "New folder 2", … (the bridge
  picks it) and opens it for naming in the rail with the text selected: type, then Enter or click
  away to keep; Esc keeps the default. Enter on an empty name says "A folder needs a name." and
  keeps the box open (leaving it keeps the default). A taken name opens the merge offer below;
  its Cancel returns to the name box with what was typed, to pick another; leaving the box with
  that same name keeps the folder's default name and doesn't ask again.
  **Round 4 (2026-10-23, owner): it is also a button.** A click, or Enter / Space when it is
  focused, moves the ticked rows into a new folder (exactly as dropping them there), or, with
  nothing ticked, makes an EMPTY folder ("Made an empty folder."), ready as a drop target;
  either way its name opens in the rail as above. An empty folder:
  - stays, with count 0, until items are moved in; a move that later empties it removes it,
    as before (bridge `create_folder`, ENG-07);
  - shows in the list as its header only ("Empty"), so it can be renamed there, unless a
    search, type or icon filter is on;
  - has a small × in its rail entry, shown on hover and focus ("Remove empty folder"); after
    it, focus goes to the next rail entry (bridge `remove_empty_folder`; a folder that loaded
    empty gets the × too);
  - is skipped at export: no box, no files and no number, so the folders after it are
    numbered as if it weren't there (a folder whose items are all excluded still takes its
    number, as before);
  - has no items to merge, so a taken name for it says "“X” already exists." and keeps its
    name, with no merge offer;
  - counts once in Start over's changes when made (or a loaded empty one removed) since the
    last export.
- **Rename:** click a folder's name in its table header (the one primary control; the rail entry
  stays the folder filter). Enter or leaving the field saves, Esc cancels, an empty name is
  refused with "A folder needs a name." and the old one kept, the same name does nothing, another
  case of its own name is a rename. A name another folder has (compared trimmed, any case) opens
  **"“X” already exists" / "Move the N items in “Y” into it?" [Move them] [Cancel]**; Cancel is the
  default (and Esc) and keeps the old name; Move them merges Y into X, which keeps its name and
  place. Leaving a name by clicking elsewhere saves it at once; the screen redraws only after
  that click has landed (redrawing between press and release ate the click). Clicking Export or
  Start over with a taken name just left shows the merge offer on the edit screen instead. New-folder naming happens in the rail because the new folder's rows may not be on screen
  (a folder filter); renaming happens in the header.
- **Long names** (up to 100 characters can be typed; typing or pasting past that says "A folder
  name can be up to 100 characters.", which goes once the name is under 100 again; reaching
  exactly 100, or deleting in a longer name from the file, says nothing) are cut with an ellipsis in the rail, the folder header and the export box,
  with the whole name as a tooltip. The export box's "Rename it to" step always shows it whole.
- **More ▸ Move to…** is first in More. It opens "Move N items to": every folder with its count
  (the count tells apart folders a file named alike, "Camp" and "camp"), the current one greyed
  "· here now", and "+ New folder…" (then the same rail naming). Arrow keys (skipping "here now"),
  Home/End and Enter pick; Esc closes and returns focus to More. After a pick the moved rows are
  unticked, so More is off and focus goes to the destination's rail entry. Pressing More again
  closes the list. Ctrl+A does nothing while Move to…, a dialog or Help is in front.
- **Selection after a move:** moved rows are unticked; other ticks stay. Keeping the ticks meant
  the next drag of one moved row dragged the whole old selection out again (found in testing),
  and the mockup shows no selection bar after a move.
- **State kept in step:** DATA.groups is rebuilt from the bridge's layout after every move,
  rename or merge, keeping the item objects (and so every edit and exclusion); rail counts,
  DATA.totals, a folder filter or collapsed fold naming a removed folder are cleared. If applying
  an answer fails, the UI shows the bridge's own layout (`layout_json`), so the screen is always
  what export writes. When the folder the view is filtered to empties, the view goes back to All
  and the status line says why: "Moved 1 item to Paddling. “Mill Creek Canyon” is empty now, so
  it was removed." An open note whose row a move takes off screen saves its draft rather than
  losing it. The italics and "Not in any CalTopo folder" go with the bridge's `unorganized`
  flag (ENG-07): the loose items only, not a CalTopo folder that happens to be called
  "Unorganized"; renamed, they are an ordinary folder, and renamed back, the loose items again.
  The merge offer for renaming another folder to "Unorganized" keeps its plain wording: the
  loose items export as an onX folder called Unorganized, so "Move them into it" is what happens.
- **Start over** counts changes since the last export (or, before any, since load): each item
  edited or moved since then once (moved back is not moved) and each folder of then whose name
  differs now. A merged-away or new folder's name isn't counted; its items are. Right after an
  export it says "This clears the current map." (round 3). A new folder that is still empty,
  or an empty folder of then that was removed, counts once (round 4).
- **Export** follows the bridge (names, numbering, per-folder zips). A per-folder download is now
  named after its `NN_` directory (`02_A_B.zip`, `002_A_B.zip` with 100+ folders), since "A/B"
  and "A_B" sanitize alike. Where two boxes would look alike, they say which is which (round 3): a
  folder whose name another box shares (any case: "Camp", "camp") shows its number before
  the name ("01 · Camp"), and a box whose file names another box shares ("A B", "A_B") shows
  its chips with their `NN_` folder. Every other box is unchanged.

Options not taken: HTML5 drag and drop (above); renaming from the rail entry (it is the filter);
keeping the selection after a move. (A click on "+ New folder" making an empty folder was not
taken at first; the owner asked for it in round 4.)

**Round 5 (C5, C4).** Esc on the name of a folder just made empty by + New folder takes that empty
folder back (bridge `remove_empty_folder`); once rows are in it, Esc keeps the default name as
before. A pasted name over 100 characters shows the same "up to 100 characters" status as typing.

### UI-33 — Whole names and notes on hover; a note's preview is its first line
Status: decided 2026-10-23 (owner, round 4 follow-ups). Release log: FOLDERS_RELEASE.md "Round 4".

- A note's preview in the list is its first non-blank line, cut with an ellipsis (it used to
  run every line together). "Use note as name" still joins every line.
- Hovering a row name that is cut, or a note whose preview hides text (more lines, or a cut
  line), shows the whole value in a styled popup, never the native `title` (it drops line
  breaks on some platforms and can't be styled). It shows after ~0.45 s, below its control
  (above it near the window's bottom), inside the window, never over the control; line breaks
  are kept; the pointer can move onto it to select and copy (it has a short grace period); it
  scrolls when long. It also shows on keyboard focus (not on a click's focus, nor while typing
  in the name), and Esc closes it and does nothing else. A press anywhere else, a scroll, a
  drag or a re-render closes it. The note editor and dragging work as before.
- The same popup carries the caution mark's text (UI-34).

### UI-34 — A caution mark for what won't carry over to onX
Status: decided 2026-10-23 (owner, round 4).

- Before export, a small caution triangle sits just before a row's note when onX will change
  something on import, with one plain line each in its popup (UI-33, hover or focus; its
  `aria-label` says the same):
  - "onX imports only the first 512 bytes of a note. About N characters will be cut."
    (owner feedback 2026-10-24: say that onX imports no more than 512 bytes; it was "Cut at 512
    bytes (about N characters lost)."). The export screen says, in the owner's words
    (2026-10-24), "Item 'temp' is over the length limit and will be truncated by onX." / "Items
    'temp', 'example 2', 'example 3' are over the length limit and will be truncated by onX."
    (straight single quotes; up to 8 names, then "and N more"). The bytes
    are measured on the note as written to the GPX (line endings made "\n", trimmed: the
    measure instructions.txt uses), so the mark and the file agree.
  - "onX will reset this area's fill to its default blue." UI-30's rule (an onX area, from an
    onX export, whose fill isn't onX's default), except that a transparent or none fill is not
    flagged (owner).
- Round 5: an item with no usable coordinates (the writers skip it; the export counts it as
  dropped) has one mark: "Won't export: it has no coordinates." (`no_coords` on the load item).
- An excluded row has no mark (it isn't exported). The mark follows every edit: shortening a
  note removes it.
- Owner feedback 2026-10-24: the NOTE header starts where the note text does (past the mark's
  slot). Every row keeps the slot, an excluded one too, so all notes start in line.
- The export screen's long-note warning names the items (up to 8, then "and N more").
- Round 5: UI-30's load dialog now skips a transparent fill too, matching the mark (owner).

### UI-35 — Sort by name; pin colour apart from line colour
Status: decided 2026-10-23 (owner, round 4); the dialog awaits the owner's look at
screenshots 5a / 5b.

- **Sort.** Each folder's Name header is a button with up/down arrows: the map's order (the
  default, nothing pre-sorted) → A to Z → Z to A → the map's order. **Per folder** (owner
  feedback 2026-10-24; it was one sort for every folder): a header sorts its own folder only,
  shown in that header and its `aria-sort`, and each folder keeps its own state. The state
  belongs to the folder (keyed by its key): a rename keeps it; items moved in show in the
  target's state (an unsorted target keeps the map's order); a merge's target keeps its own and
  the merged-away folder's state goes; a removed folder's state goes; a new folder starts in
  the map's order; loading a map or Start over clears all of it. Natural, numeric-aware and
  case-insensitive (`Intl.Collator`, numeric, base sensitivity), so "01 - …", "02 - …",
  "10 - …" (Dark Divide aid stations) come out in order; equal names keep the map's order. It
  sorts across waypoints, lines and areas together. View only: export keeps the map's order.
  Shift-click ranges and select-all follow the sorted rows; drag and Move to… are unchanged.
  A new map starts unsorted. Option not taken at first: a sort per folder (one state was
  simpler to read); the owner asked for it on 2026-10-24, since sorting one folder sorted
  every other one too.
- **Icon & color… / Color….** The selection bar's button reads "Icon & color…" when waypoints
  are ticked and "Color…" when only lines and areas are. In a mixed selection the dialog shows
  a **Pin color** row (onX's 10) and a **Line color** row (11, with Fuchsia), each starting on
  "Leave as is"; one pick no longer recolours both. One kind keeps a single "Color" row. The
  chips that used to read "Reset" (colour and icon) now read "Leave as is", which is what they
  do. The single-item popover is unchanged: one item, no coupling.
