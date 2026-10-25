# Bulk rename: build progress and coordination

The live tracker for building docs/plans/BULK_RENAME.md (revision 4). The plan is the spec; this file
is the shared state. **Every agent reads all of this file before starting and appends to its own log
(section 5) as it works**: what it built, every decision it had to make that the plan didn't settle
(with the alternative it rejected), every deviation from the plan, and anything another track must know.
The orchestrator merges tracks and keeps sections 3 and 4 current.

**The live copy is `/Users/scott/_code/cairn/docs/plans/BULK_RENAME_PROGRESS.md`** (the main checkout,
by absolute path). The copy inside a worktree is a read-only snapshot of the Phase 1 commit: never edit
it and never commit it, or the track merges conflict on it. Write only inside your own track's
subsection of section 5. Three agents write here at once: Read the live file right before every Edit,
and if an Edit is refused because the file changed, Read again and retry. If you cannot write the live
file at all, log in your worktree copy instead (uncommitted) and say so in your final report.

Started 2026-10-25 by the orchestrator (Opus 5.5). Owner away; decisions not settled by the plan are made
here with an alternative noted, to revisit with the owner.

---

## 1. How to work (every track)

- **Branch**: the feature branch is `feat/bulk-rename` (Phase 1 is committed on it). In your worktree:
  `git checkout -b bulk/<track> feat/bulk-rename` before anything else, and work only there.
- **Python**: there is no venv in a worktree. From the worktree root use
  `/Users/scott/_code/cairn/.venv/bin/python -m pytest …` (the worktree's `cairn/`, `web/` and `tests/`
  are what get imported). Never bare `python` or `pytest`. `--no-cov -p no:cacheprovider` on narrow runs.
- **Dev server**: your own, serving your worktree's `web/`, on your track's port, started in the
  background: `PORT=<port> /Users/scott/_code/cairn/.venv/bin/python web/serve.py`. Run the web tests
  with `BASE_URL=http://127.0.0.1:<port>/`. Ports: **A 8781 · B 8782 · C 8783 · D 8784**. Port 8779 is
  the orchestrator's (main checkout); 8765 may be taken by something else on this machine. Stop your
  server when done.
- **Commits**: early and often, in your worktree, staging files by name. **Never `git add -A`** (scratch
  files sit untracked at the repo root). Messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_019BuYxNAfXvJtTFx663jVwh`. Do not push. Do not merge
  your branch anywhere: the orchestrator merges tracks into `feat/bulk-rename`. When the orchestrator
  tells you to, run `git merge feat/bulk-rename` in your worktree to pick up merged tracks; that is the
  only merge you do.
- **Never run `uv run` or `uv sync` in a worktree** (it would build a second venv); use the main venv's
  python as below. If a command fails with a sandbox error (`Operation not permitted`, EPERM on a port,
  Chromium failing to launch), retry it with the sandbox disabled.
- **Files**: only the files your track owns (plan section 4). Need a change elsewhere? Write it in the
  log as a request to the owning track or the orchestrator; don't make it.
- **No nested agents.** No onX account, no imports into onX, ever.
- **Style** (AGENTS.md "Style and design"; docs/design/LABELS.md section 16 is the vocabulary):
  reuse existing labels; straight apostrophes; "You will", not "You'll"; status sentences end with a
  period ("Changed 3 items."), titles don't; curly quotes around user names in UI text; never "Web Map"
  (say "onX on a computer"); a missing name shows "Untitled" (display only), a missing note is blank;
  confirm buttons: safe choice first, action last; Save / Cancel; modals don't narrate (UI-26).
- **Tests**: descriptive ids (no r1/i2 codes); never `try/except` around assertions; no test reads a
  gitignored path; anything under `tests/fixtures/` must be added to `tests/test_input_check.EXPECTED`
  (so prefer generating maps at test time with `tests/hardening_maps.make_map`).
- **Labels**: any new user-visible string goes into docs/design/LABELS.md in the same commit
  (`tests/test_labels_inventory.py` fails otherwise for strings in web/index.html).

## 2. The frozen contract (Phase 1)

**Core** — `web/rename.js` exposes `window.CairnRename = { transform, xmlSafe, cleanName, cleanNote,
writtenNote, noteBytes, XML_INVALID }`. Signature and rules: plan section 3.1. The helpers are final in
the Phase 1 commit; `transform` is a stub (every row `unchanged`) for Track A to implement.
Flags: exactly `unchanged`, `note-over-limit`, `chars-removed`. No `empty`, no `duplicate`, no `blocked`.
`XML_INVALID` carries the `g` flag, so `XML_INVALID.test(s)` is stateful (`lastIndex` persists between
calls) and gives intermittent answers: detect removed characters with `xmlSafe(s) !== s`, never `.test()`.

**DOM** (Track B builds it; C and D test against it; nobody renames these):

| selector | what |
|---|---|
| `#bulk-rename` | More menu item "Rename…" (`role=menuitem`, `aria-haspopup=dialog`), after `#bulk-move` |
| `#bulk-note` | More menu item "Change note…" |
| `#mark-dialog[data-bulk="rename"\|"note"]` | the reused bulk dialog in text mode; also `aria-labelledby` its `<h2>` |
| `#mark-dialog[data-preview-seq]` | integer, +1 after every preview render (tests wait on it) |
| `#mark-dialog h2` | "Rename N items" / "Change the note on N items" (no period) |
| `.mode-tog[data-mode="prefix"\|"suffix"\|"replace"\|"set"]` | the mode toggles (`.tog` look, `aria-pressed`), in the decided order |
| `#bulk-text` | the "Text" field (Add before / Add after / Replace the note); `<input>` for names, `<textarea>` for notes |
| `#bulk-find`, `#bulk-repl` | "Find" / "Replace with" (inputs for names, textareas for notes) |
| `#bulk-match-case` | "Match case" toggle (`aria-pressed`) |
| `.na-row[data-uid][data-flags]` | one preview row; `data-flags` space-separated, "" when changed with no flag |
| `.na-before`, `.na-after` | the row's cells; `.is-placeholder` on a cell showing "Untitled" (names only) |
| `.na-flag` | the row's flag sentence ("No change", or the long-note caution sentence) |
| `#bulk-summary` | "N will change · M unchanged", `aria-live=polite` |
| `#bulk-apply` | Save (reused id); disabled when nothing changes |
| `.bulk-cancel` | Cancel |
| `#status` | after Save: "Changed N items." |

**Test infrastructure** (Phase 1): `tests/web/conftest.py` (fixtures: `_require_server`, `browser`,
`context`, `fresh_page`, `loaded`, `csp_page`), `tests/web/helpers.py` (constants `BASE_URL`, `FIXTURE`,
`FX_DIR`, `ROW` and the shared helpers: `export_zip_bytes`, `_export_zip`, `_menu_action`, `_tick`, `_set`,
`_select_all_shown`, `_clear_selection`, `_set_type`, `_load_files`, `_row`, `_is_marked`, …), and
`tests/web/__init__.py`. New test files import from `tests.web.helpers`. `tests/naughty_strings.py` is the
naughty-strings module (Track C creates it).

## 3. Tracks

| track | owner | files | model | state | branch | notes |
|---|---|---|---|---|---|---|
| Phase 1 | orchestrator | tests/web/{conftest,helpers,__init__}.py, web/rename.js skeleton, this file | Opus 5.5 | in progress | feat/bulk-rename | |
| A core | agent | web/rename.js | Opus 5.5 xhigh | not started | bulk/a-core | wave 1 |
| B dialog UI | agent | web/app.js, web/index.html, web/styles.css, docs/FAQ.md, web/faq.html, docs/design/DECISIONS.md, docs/design/LABELS.md | Opus 5.5 xhigh | not started | bulk/b-ui | wave 1; transform is a stub until A merges |
| C tests | agent | tests/naughty_strings.py, tests/bulk_rename_vectors.py, tests/web/test_rename_core.py, tests/web/test_bulk_text.py, tests/test_bulk_round_trip.py, tests/test_bulk_prereqs.py | Opus 5.5 xhigh | not started | bulk/c-tests | wave 1 |
| D fuzz + perf | agent | scripts/qa/fuzz_ui.py, tests/web/test_bulk_perf.py | Opus 5.5 xhigh | not started | bulk/d-fuzz | wave 2: starts in the first freed slot |
| Integration | orchestrator | merges, full suite, Chrome click-through, screenshots, DoD | Opus 5.5 | not started | feat/bulk-rename | merge order A → C → B → D |

Waves (a deviation from plan section 4's "A + C + D, then B", logged in 5.0): B is the critical path
and only needs the frozen contract, so it starts with A and C; D's real runs need B anyway. The
orchestrator merges each finished track into `feat/bulk-rename` and then tells the running tracks to
`git merge feat/bulk-rename`.

## 4. Decision status

Plan section 2 numbers. **Implemented** = in code on a branch with a test; **pending** = assigned, not
built yet; **shipped earlier** = already on main; **superseded** = no longer valid; **deferred** = out of v1.

| # | decision | status |
|---|---|---|
| 1 | Rename modes: Add before · Add after · Find and replace; empty Find replaces the whole name | pending (A core, B UI) |
| 2 | Change note modes: Add before · Add after · Find and replace · Replace the note; same Find layout | pending (A, B) |
| 3 | No duplicate flag | pending (A: no flag; C: Campsite test) |
| 4 | Wording (approved strings) | pending (B, with LABELS.md) |
| 5 | One "Match case", off by default | pending (B) |
| 6 | Transform in JS (web/rename.js) | in progress (Phase 1 skeleton) |
| 7 | Empty result allowed, never blocks Save | pending (A, B); amended by 17 |
| 8 | No long-name flag | pending (A: none) |
| 9 | Notes over 512 bytes: warn, never cut | pending (A flag, B sentence) |
| 10 | Rows leaving the search filter: leave the filter, status is the receipt | pending (B, C e2e) |
| 11 | Open note editor on a selected row: "Save your note?" first | pending (B) |
| 12 | "Use note as name" unchanged | **shipped earlier** (2f92e4b) |
| 13 | No selection cap; preview capped at 200 rows | pending (B); perf measured and accepted by the owner |
| 14 | Modal while open; focus returns to More, or to search when the selection emptied | pending (B) |
| 15 | XML-forbidden characters dropped in core and writer, same set | writer **shipped earlier** (edc284b, translate table since 667684b); core pending (A) |
| 16 | Opens on Add before, empty: all "No change", Save disabled | pending (B) |
| 17 | Names optional everywhere | single field, display and export **shipped** (f429558); bulk pending (A, B) |
| 18 | Missing note shows blank | pending (B) |
| 19 | "Changed N items." with a period; no period on titles; straight apostrophes; "You will" | status string **shipped** (f429558); new strings pending (B) |
| 20 | Confirms: safe first, action last | **shipped** for existing confirms (f429558); "Save your note?" reuse pending (B) |
| 21 | No "Web Map" | **shipped** (f429558) |
| 22 | Owner-run onX probe for an empty `<name>` | open (owner) |
| rev 1–3 | `duplicate` flag, `empty` flag / blocked Save, "find '' = no-op", uid-keyed instructions | **superseded** |
| — | regex, numbering, case conversion, undo stack, NFC matching, preview checkboxes | **deferred** (plan section 1) |

## 5. Log (append to your own subsection; newest last)

Line format: `- HH:MM <what>` (local time). Mark decisions `DECISION:` (with the rejected alternative),
deviations from the plan `DEVIATION:`, and anything another track must act on `FOR <track>:`.

### 5.0 Orchestrator

- 2026-10-25 branch `feat/bulk-rename` from `docs/bulk-rename-phase0` (f429558). Phase 1: fixtures and
  helpers moved out of test_web_app.py (collection unchanged at 239), rename.js skeleton, this file.
- DEVIATION: wave 1 is A + B + C, not A + C + D (section 3 says why). Alternative kept: if B stalls on
  the stub, B pauses and D takes its slot.
- DECISION: agents run on Opus 5.5 at xhigh effort (owner, 2026-10-25, later than the "scale models
  down" note). Alternative: Sonnet for C and D.

### 5.A Track A (core)

### 5.B Track B (dialog UI)

### 5.C Track C (tests)

### 5.D Track D (fuzz and perf)

## 6. Open questions for the owner (not blocking)

- Wording #10 from the label audit: should "Leave this map?" say "This discards N unexported changes."
  like Start over? (pending owner)
- An empty note's row button reads "Add a note"; keep it, or make the cell blank? (pending owner)
