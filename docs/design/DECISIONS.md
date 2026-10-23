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
  real onX Area (acreage shown) **with its yellow color**. *Correction 2026-10-23:* only the
  outline color was kept. Every import in `docs/ONX_ROUND_TRIP.md` stored onX's default fill
  `rgba(74,144,226,0.1)` whatever `onx:fill_color` said, so the fill is never carried.
- **onX does not parse a key=value `<desc>` on import**: a desc of `name=…\nnotes=…\ntype=Area\n
  color=…` became the Notes verbatim. So `<desc>` carries only the user's note text, as the
  waypoint and track writers already did.
- onX's own GPX export of an area
  (`tests/fixtures/caltopo-random/onx_roundtrip/from_geojson/onx_export.gpx`) is
  `<rte><name/><desc>key=value…</desc><type>Area</type><extensions><onx:color/><onx:fill_color/>
  </extensions><rtept/>…</rte>`. Tracks (color, dash style, weight 6.0, multi-line notes) and
  waypoints round-tripped from Cairn's GPX in the same import.

Decision:

- `cairn/core/writers.py:write_gpx_areas_maybe_split` writes each area as that `<rte>`: `<name>`
  (sanitized like every other name), `<desc>` = note only (omitted when empty), `<type>Area</type>`,
  `<onx:color>` = `kml_area_color` (the 11-color line palette value the UI shows) and
  `<onx:fill_color>` = the same RGB at CalTopo's `fill-opacity`, else 0.5 (the old KML fill
  semantics), then the closed outer ring as bare `<rtept lat lon/>`. Size-split at 3.75 MiB like
  the other GPX writers. File: `<Folder>_Areas.gpx`.
- The web export (`web/bridge.py:export_zip`) uses it; no web export writes KML any more, so the
  runbook's "contains KML, Web Map only" warning is no longer triggered. The KML area writer is
  kept for its other callers and tests.
- Area line style and weight are not written: onX's own area export carries only color and fill,
  and that is what was verified.
- **Holes — provisional, subject to revision.** An onX area is single-ring, so a polygon with
  holes is written as its outer ring only (the hole is filled in) and listed in RUNBOOK.md under
  "Holes not kept in onX". Not tested: whether onX can keep a hole through any import path (e.g.
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
- Dotted is not offered: onX has only ever exported `solid` and `dash` in our tests. A dotted
  line from a file is drawn dotted and kept unless changed.
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
source notice, the note-over-limit, dropped-item and markup-limit warnings, and the runbook
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
