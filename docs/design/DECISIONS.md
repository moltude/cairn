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

## Next

Mockups for the loaded screen and the empty state, built from UI-01…UI-08. Link them here when
they exist, and record the pick as UI-09.
