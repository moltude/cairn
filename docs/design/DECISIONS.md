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
`docs/design/baseline-2026-10-21/`.

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
Status: decided

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
Status: proposed (2026-10-21) — except "Reset", decided

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
| Selection bar | ✕ Clear selection | **Deselect** | "Clear selection" (also standard) |
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
