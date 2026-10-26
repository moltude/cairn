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
| `window.__cairnPerf` | `{ lastTransformMs, lastPreviewMs, lastSaveMs }`, set by `drawTextBulk` / `applyTextBulk` with `performance.now()` (plan 6.5; D reads it) |
| `.na-more` | the line under a preview capped at 200 rows, worded like the app's existing "and N more" line (B picks the exact existing string and logs it) |

**Test infrastructure** (Phase 1): `tests/web/conftest.py` (fixtures: `_require_server`, `browser`,
`context`, `fresh_page`, `loaded`, `csp_page`), `tests/web/helpers.py` (constants `BASE_URL`, `FIXTURE`,
`FX_DIR`, `ROW` and the shared helpers: `export_zip_bytes`, `_export_zip`, `_menu_action`, `_tick`, `_set`,
`_select_all_shown`, `_clear_selection`, `_set_type`, `_load_files`, `_row`, `_is_marked`, …), and
`tests/web/__init__.py`. New test files import from `tests.web.helpers`. `tests/naughty_strings.py` is the
naughty-strings module (Track C creates it). **The bulk helpers of plan 6.3** (`_open_bulk`, `_set_mode`,
`_type_spec`, `_type_slowly`, `_preview_rows`, `_save_bulk`, `_status_count`, `_gpx_names`, `_gpx_descs`)
are **Track C's**, appended to `tests/web/helpers.py`; C is the only track that edits helpers.py. D uses
them once C is merged, and until then keeps private copies inside its own file.

## 3. Tracks

| track | owner | files | model | state | branch | notes |
|---|---|---|---|---|---|---|
| Phase 1 | orchestrator | tests/web/{conftest,helpers,__init__}.py, web/rename.js skeleton, this file | Opus 5.5 | **done** `dc99726` | feat/bulk-rename | 1389 passed, 239 web collected |
| A core | agent | web/rename.js | Opus 5.5 xhigh | **done** `30f9a7c` | bulk/a-core | wave 1; log copied from its worktree (the live file refused the Edit) |
| B dialog UI | agent | web/app.js, web/index.html, web/styles.css, docs/FAQ.md, web/faq.html, docs/design/DECISIONS.md, docs/design/LABELS.md | Opus 5.5 xhigh | **done** `de93ae8`, merged | bulk/b-ui | highlight, Untitled confirm, FAQ verbatim, menu arrows; log copied from its worktree |
| C tests | agent | tests/naughty_strings.py, tests/bulk_rename_vectors.py, tests/web/test_rename_core.py, tests/web/test_bulk_text.py, tests/test_bulk_round_trip.py, tests/test_bulk_prereqs.py, tests/web/helpers.py (bulk helpers) | Opus 5.5 xhigh | **done** `f32d280`, merged | bulk/c-tests | U 135, W 206, E 83 (1 strict xfail: ANCHOR, fixed at integration); log copied from its worktree |
| D fuzz + perf | agent | scripts/qa/fuzz_ui.py, tests/web/test_bulk_perf.py | Opus 5.5 xhigh | **done** `0229b30`, merged | bulk/d-fuzz | fuzz 12/12 green at `548421a` (3,612 actions, 136 exports); perf 3,002 rows: 0.6 / 2.5 / 227 ms; log copied from its worktree |
| Integration | orchestrator | merges, full suite, Chrome click-through, screenshots, DoD | Opus 5.5 | **done** pending owner review | feat/bulk-rename | A → B → C → D merged (B before C, 5.0); 1816 passed |

Waves (a deviation from plan section 4's "A + C + D, then B", logged in 5.0): B is the critical path
and only needs the frozen contract, so it starts with A and C; D's real runs need B anyway. The
orchestrator merges each finished track into `feat/bulk-rename` and then tells the running tracks to
`git merge feat/bulk-rename`.

## 4. Decision status

Plan section 2 numbers. **Implemented** = in code on a branch with a test; **pending** = assigned, not
built yet; **shipped earlier** = already on main; **superseded** = no longer valid; **deferred** = out of v1.

| # | decision | status |
|---|---|---|
| 1 | Rename modes: Add before · Add after · Find and replace; empty Find replaces the whole name | **implemented** (A `30f9a7c`, B `cd0e166`; C: `test_empty_find_replaces_the_whole_name`, Campsite test) |
| 2 | Change note modes: Add before · Add after · Find and replace · Replace the note; same Find layout | **implemented** (A, B; C U and E) |
| 3 | No duplicate flag | **implemented** (no flag anywhere; C: Campsite and twins tests, three `<name>Campsite</name>` exported) |
| 4 | Wording (approved strings) | **implemented** (B, LABELS 5.1; FAQ answer verbatim after `a255978`) |
| 5 | One "Match case", off by default | **implemented** (B; C `test_match_case_toggle_changes_the_count_live`) |
| 6 | Transform in JS (web/rename.js) | **implemented** (A) |
| 7 | Empty result allowed, never blocks Save | **implemented** (A, B; C blank-name tests) |
| 8 | No long-name flag | **implemented** (none; C 3,000-character name test) |
| 9 | Notes over 512 bytes: warn, never cut | **implemented** (A flag on changed rows only, B reuses the caution sentence; C, and orchestrator click-through) |
| 10 | Rows leaving the search filter: leave the filter, status is the receipt | **implemented** (B; C e2e; click-through) |
| 11 | Open note editor on a selected row: "Save your note?" first | **implemented** (B `askToSaveNote`, shared with Export; C e2e) |
| 12 | "Use note as name" unchanged | **shipped earlier** (2f92e4b) |
| 13 | No selection cap; preview capped at 200 rows | **implemented** (B `.na-more`); perf met (D: 3,002 rows transform 0.6 ms, list 2.5 ms, Save 227 ms); Vercel rerun after merge pending |
| 14 | Modal while open; focus returns to More, or to search when the selection emptied | **implemented** (B; C e2e; click-through); shift-click anchor reset added `548421a` |
| 15 | XML-forbidden characters dropped in core and writer, same set | **implemented** (writer earlier; core A; C pins the sets equal) |
| 16 | Opens on Add before, empty: all "No change", Save disabled | **implemented** (B; click-through) |
| 17 | Names optional everywhere | **implemented** (single field f429558; bulk A, B; "Untitled" in the note confirm `a255978`) |
| 18 | Missing note shows blank | **implemented** (B; C `test_missing_notes_show_as_blank_never_no_note`) |
| 19 | "Changed N items." with a period; no period on titles; straight apostrophes; "You will" | **implemented** |
| 20 | Confirms: safe first, action last | **implemented** (the one reused confirm keeps Keep editing · Discard · Save) |
| 21 | No "Web Map" | **shipped for user-facing text** (f429558: app, Help, FAQ, instructions.txt; nothing new in this build uses it). About 60 internal lines still say it (dated research notes, DECISIONS evidence, code comments, fixture READMEs, real onX export files that can't change): owner question in section 6 |
| 22 | Owner-run onX probe for an empty `<name>` | **open (owner)** |
| — | Changed-part highlight (Phase 0 mockups' `.hit`) | **implemented** (B `a255978`, `de93ae8`); one span first-to-last change, owner question in section 6 |
| — | More menu arrow keys | **implemented** (B `de93ae8`) |
| rev 1–3 | `duplicate` flag, `empty` flag / blocked Save, "find '' = no-op", uid-keyed instructions | **superseded** (no longer valid) |
| — | plan's `test_final_sigma_matches_only_itself` ("not ς") | **superseded** by V8 folding (5.0) |
| — | regex, numbering, case conversion, undo stack, NFC matching, preview checkboxes | **deferred** (plan section 1) |

## 5. Log (append to your own subsection; newest last)

Line format: `- HH:MM <what>` (local time). Mark decisions `DECISION:` (with the rejected alternative),
deviations from the plan `DEVIATION:`, and anything another track must act on `FOR <track>:`.

### 5.0 Orchestrator

- 2026-10-25 branch `feat/bulk-rename` from `docs/bulk-rename-phase0` (f429558). Phase 1: fixtures and
  helpers moved out of test_web_app.py (collection unchanged at 239), rename.js skeleton, this file.
- DEVIATION: wave 1 is A + B + C, not A + C + D (section 3 says why). Alternative kept: if B stalls on
  the stub, B pauses and D takes its slot.
- Phase 1 committed: `dc99726` on `feat/bulk-rename`; full suite 1389 passed. Every track branches from it.
- Fan-out base `0ab2679` (Phase 1 plus this tracker). Wave 1 (A, B, C) launched; D waits for the first freed slot.
- DECISION (for A and C): case-insensitive matching is V8's `giu` folding, unmodified. Checked in node:
  "Οδυσσεύς" find "σ" with Match case off matches **3** (σ, σ and the final ς: Unicode simple case
  folding maps ς to σ); with Match case on, 2. The plan's `test_final_sigma_matches_only_itself` expects
  "not ς" and is wrong for JS; C pins the real behaviour under a new id,
  `test_final_sigma_matches_sigma_without_match_case_and_only_itself_with_it`. Also checked and as the plan
  says: "İstanbul" find "istanbul" 0, find "İ" 1; "Straße" find "ss" 0; "Ａ" vs "A" 0; NFD "ü" in NFC 0;
  NBSP vs space 0; Kelvin K and long s DO fold (the plan's property 9 already excludes them). Rejected:
  a custom folding table (more code, and it would disagree with the browser's own search behaviour).
- Merged Track A: `feat/bulk-rename` fast-forwarded to `30f9a7c`. Accepted A's `writtenNote` NEL fix after an
  oracle check: for 10 edge notes (outer NEL, BOM, U+2028, NBSP, U+3000, inner NEL), the note the core stores
  equals what `xml_safe(clean_notes(…, plain=True))` writes, 0 divergent.
- DECISION (for C, from A's evidence): `test_zero_width_space_and_bom_are_kept_in_names`: JS `trim()` counts
  U+FEFF as whitespace, so a BOM at a name's edge is trimmed (by the writer's `strip()` too, so preview ==
  file still holds). The test puts the BOM inside the name: "Ca\ufeffmp\u200b!" + Add before "x" →
  "xCa\ufeffmp\u200b!", flags []. Rejected: special-casing BOM in the trim.
- DECISION (for C, from A's evidence): `test_find_equal_to_replace_counts_zero` runs with Match case **on**
  (or on rows with no other-case match). With it off, find "a" repl "a" turns "Camp A" into "Camp a", a real
  change. Rejected: making a case-insensitive identical replacement a no-op (it isn't one).
- DECISION: the live tracker can't be written from a worktree (A's Edit was refused by isolation). Every
  track logs in its worktree copy, uncommitted; the orchestrator copies the logs here. The live file stays
  uncommitted until integration, so no track's `git merge feat/bulk-rename` conflicts on it.
- B and C told to `git merge feat/bulk-rename` (A's core); C to drop its stub skip and apply the two decisions
  above. Track D launched from `30f9a7c` in A's freed slot.
- DEVIATION: merged Track B before Track C (`feat/bulk-rename` fast-forwarded to `0235cc6`). B finished first,
  the two tracks touch disjoint files, and C's E layer and D's real runs both need the dialog. C and D told to
  `git merge feat/bulk-rename`.
- DECISION: the After cell highlights the changed part (`.hit`, light green), as the owner-approved RenameA and
  NoteA2 mockups do (`.hit{background:#E9EFDF}`). B had left it out (the core returns no match offsets); a
  common-start / common-end diff of before and after, by code point, is enough. Sent back to B. Text content of
  `.na-after` is unchanged, so no test contract moves. Rejected: shipping without it (a visible departure from
  the approved design).
- DECISION: the reused "Save your note?" body names a nameless item "Untitled" (names optional, decision 17;
  LABELS 16). Sent back to B.
- Click-through in Chrome (DevTools MCP, 1440×900) on `0235cc6`, maps generated under archive/bulk-rename/data:
  Campsite normalisation (3 change, 1 "No change", no flags, Enter saves, "Changed 3 items.", focus on More);
  search "trail" + select all (waypoints, a line, an area) + find "trail" → "" (all 6 leave the filter, focus
  to `#filter`, export carries every new name incl. "Old  cutoff"); Change note… Add after with an emoji on 20
  hostile rows (note-over-limit on exactly the 3 long notes = caution marks = export warning; CRLF → LF; a
  blank note gets the text alone; every stored note == its GPX `<desc>`; the only stored/file difference is
  a dirty loaded name "\x01Camp" the writer cleans, by design).
- DECISION: the More menu gets ArrowDown / ArrowUp / Home / End (it had Tab only; `role=menu` with six items
  now). Sent to B. Rejected: Tab only (plan 5.8 `test_keyboard_only_flow` expects arrows).
- Merged B's follow-ups: `feat/bulk-rename` fast-forwarded to `de93ae8`.
- Full suite on `de93ae8` (A + B merged, no new test files yet): **1389 passed**, unchanged from baseline.
- Merged Track C: `feat/bulk-rename` fast-forwarded to `f32d280` (tests only; no raw invisible characters in any file).
- `548421a` (orchestrator): `applyTextBulk` resets ANCHOR when Save empties the selection, as `afterMove` does;
  C's strict xfail removed. The 7 anchor/prune/focus E tests pass.
- Full suite on `548421a` (A + B + C + the anchor fix): **1813 passed** (1389 + 424 new: U 135, W 206, E 83), 0 failed, 0 xfail.
- Merged Track D: `feat/bulk-rename` fast-forwarded to `0229b30` (fuzz_ui.py and the perf test only).
- Final full suite on `0229b30` + integration docs: **1816 passed** (1389 + 427). AGENTS.md baseline updated;
  TODO.md says built, awaiting review, and lists the owner-run onX probe; scripts/qa/README.md covers the bulk
  fuzz actions; CodeQL comment names rename.js. Screenshots and aria snapshots: archive/bulk-rename/shots/.
- DECISION: agents run on Opus 5.5 at xhigh effort (owner, 2026-10-25, later than the "scale models
  down" note). Alternative: Sonnet for C and D.

### 5.A Track A (core)

- 15:21 started on bulk/a-core at 0ab2679
- 15:22 the live tracker refused Track A's Edit (worktree isolation); logging here in the worktree copy,
  uncommitted, per section 1's fallback
- 15:35 `transform` implemented in web/rename.js, committed `30f9a7c`. Helpers unchanged except `writtenNote`
  (DECISION below). The RegExp and its replacer are built once per call.
- DECISION: an empty prefix / suffix text on notes adds no `"\n"` joiner (raw === before), so the no-op rule
  and property 4 hold on a dirty stored note too. Rejected: 3.1's literal `text + "\n" + before`, which with
  text "" turns "\x01note" into a changed row with `chars-removed` under an empty spec.
- DECISION: an unchanged row's `after` is its `before`, verbatim, including a note whose cleaned form equals
  only its written form ("abc " + suffix "\n " → after "abc "). Rejected: returning `clean(raw)` there (the
  preview would show a value Save never stores).
- DECISION: `note-over-limit` is set on changed rows only; an unchanged row carries exactly `["unchanged"]`
  even when its stored note is over the limit (its caution mark in the list already says so). The 3.1
  pseudo-code gives `same → ["unchanged"]`, and the table's "after, which is already in written form" only
  holds for changed rows. Rejected: flagging untouched long notes in the dialog (UI-26).
- DECISION: `set` on names is a bad mode: every row unchanged. Rejected: treating it as Find "" + Replace
  with (names have no Replace the note toggle; a stray set would rename every row).
- DECISION: bad input. A spec that isn't an object, a field other than "name" / "desc" (missing included)
  or a mode the field doesn't have → every row unchanged. `rows` not an array → `{rows: [], changed: 0}`.
  A row entry that isn't an object → unchanged, before "", uid undefined (one output row per input row
  still). Values that aren't strings → `String(x ?? "")`, "" if String() throws. A throwing getter or a
  result past V8's string limit → every row unchanged. Rejected: the stub's default of field "name" when
  field is missing (a caller bug would rename names silently).
- DECISION: Match case is on only for `matchCase === true` (off by default, decision 5); "true" or 1 is off.
  Rejected: `!!matchCase`.
- DECISION: `ctx.noteLimit` missing or not a non-negative number (null, NaN, "512", -1) → 512. Rejected:
  `Number(ctx.noteLimit)`, which makes app.js's pre-boot `NOTE_LIMIT = null` a limit of 0 (every note flagged).
- DEVIATION + DECISION (helper fix, the one change to a Phase 1 "final" helper, so a shared surface):
  `writtenNote` also trims an outer U+0085 (NEL). After
  `xmlSafe`, JS `trim()` and Python `str.strip()` differ only on U+0085 (Python strips it, JS kept it) and
  U+FEFF (JS trims it, Python keeps it). The writer's `clean_notes(plain=True)` uses `strip()`, so a bulk
  note with an outer NEL was previewed and stored as "abc\x85" and exported as "abc". Measured: running
  every changed `after` through `writers.xml_safe(clean_notes(s, plain=True))` in Python, 694 of 42,157
  random notes differed with the old trim and 0 with the fix (and 0 of 30,727 names either way). BOM needs
  nothing: JS trims it, so the stored note has none. Rejected: changing `clean_notes` (not Track A's file)
  or leaving the headline invariant broken.
- FOR B: app.js's own `writtenNote` (app.js:936) has the same NEL gap in `noteOverflow`'s count (2 bytes,
  only for a note with an outer NEL); calling `CairnRename.writtenNote` there closes it. Optional.
- FOR B: pass `field` ("name" / "desc") explicitly and `matchCase` as a real boolean; anything else is a
  no-op by design.
- FOR C: `test_zero_width_space_and_bom_are_kept_in_names`: the plan's "xCamp​﻿" is wrong in JS.
  `String.prototype.trim` counts U+FEFF as whitespace, so Add before "x" on "Camp​﻿" gives
  "xCamp​", flags [] (preview == stored == exported still). Put the BOM inside the name instead:
  "Ca﻿mp​!" → "xCa﻿mp​!", flags []. NBSP, U+3000 and U+2028 at a name's edge are
  trimmed too (by JS and Python alike).
- FOR C: `test_find_equal_to_replace_counts_zero` (find "a" repl "a" → every row unchanged, Save disabled)
  holds only with Match case on, or on rows with no "A": with Match case off (the default) "Camp A" →
  "Camp a" is a real change (`["a", "banana", "A"]` gives changed 1, off; 0, on). On Bitterroots the E
  test would find Save enabled. Use Match case on, or pick rows without the other case.
- FOR C: properties 1 and 2 hold for rows not flagged `unchanged` only: an unchanged row returns
  `after === before` verbatim, dirty or not (that is the no-op rule). Property 8 likewise ranges over
  changed note rows. Property 7 holds as: `unchanged` ⇔ `after === before`, for names and notes.
- FOR C: property 6 needs two extra conditions: (a) `repl === clean(repl)` (`cleanName` for names,
  `cleanNote` for notes), or collapse, trim and the XML drop legitimately lower the count (283 of 4,000
  vectors); (b) code-point counting: a find holding a lone surrogate never matches half of a paired emoji
  (u flag), but a code-unit count (`str.split`, or Python `count` on a surrogate-split string) does find it
  (16 of 4,000). The generator can simply keep lone surrogates out of `find` for property 6.
- FOR C: case folding as found in node and Chromium 156: "Οδυσσεύς" find "σ" 3 off / 2 on; "İstanbul" find
  "istanbul" 0, find "İ" 1; "Straße" find "ss" 0; Kelvin "K" (U+212A) find "k" off 1; "ſ" find "s" off 1.
  A lone-surrogate find never throws and never splits a pair: "a🔥\uD83Db" find "\uD83D" repl "Z" →
  "a🔥Zb", flags [] (the lone half was the match, so raw holds none).
- 15:38 verified, no test files: section 5's 56 U cases by id (node), 15 extra contract checks (bad input,
  set on names, ctx defaults, throwing getters, regex reuse, `XML_INVALID.lastIndex` untouched), and the 12
  properties plus an independent oracle (own `\u{…}` escaping, `split().join()`) on 30,000 seeded vectors
  (134,624 rows; alphabet with `$&\\`, `\t\r\n`, combining, ZWSP/ZWJ/RLO/BOM, NBSP, C0, C1, lone surrogates,
  astral, `İıßΣσςKſ`; property 9 excludes İ/ı/K/ſ): 0 failures. Chromium 156 agrees exactly with node: the
  same FNV hash of the full JSON output over 4,000 vectors (18,039 rows) and the same named cases. Perf at
  20,000 rows: Chromium 3.4–4.6 ms, node 4–6 ms; an emoji in every row raises node to 10–15 ms (V8's
  u-flag regexes on astral text); 1,500 rows < 1 ms (budget 10 ms).

### 5.B Track B (dialog UI)

- 15:26 started on bulk/b-ui at 0ab2679
- 15:27 DEVIATION: the live tracker (main checkout) refused my Edit (this agent is isolated to its
  worktree), so per section 1's fallback I log here, in the worktree copy, uncommitted.
- 15:30 `f227327` menu items `#bulk-rename` / `#bulk-note` after `#bulk-move`, `<script src="rename.js">`
  before app.js, LABELS.md rows. Nothing else lists static web files (vercel.json's cache rule is
  `/(.*)`; serve.py serves the folder; no engine-surface or preload list names JS files).
- 15:38 `cd0e166` the dialogs (app.js, styles.css, LABELS.md section 5.1). Click-through with a
  throwaway stand-in core (in $TMPDIR, never committed): names and notes, every mode, blank result,
  control character, 600-byte note, Save, Esc. No console errors.
- DECISION: layout follows the approved mockups (RenameA, NoteA2): mode toggles and fields in the head,
  the Now → After list below, the summary at the left of the footer. Kept from the Icon & color dialog
  so the two read as one: the × close, the "Now" / "After" column labels, Cancel · Save. Rejected: the
  Icon & color order (list in the head, controls below), which buries the list under the fields.
- DECISION: an unchanged row keeps its value in `.na-after` (== before) but hides that cell; "No change"
  (`.na-flag`) takes its place in the After column, as the mockups draw it. Rejected: the value greyed
  beside "No change" (wordy, the mockups don't show it).
- FOR C: on an unchanged row `.na-after` is `display:none`; `inner_text()` and `text_content()` both
  return its value (innerText of an element that isn't rendered is its text content), so read cells by
  text, never by visibility.
- DECISION: no green highlight of the changed part (the mockups had one): the core returns no match
  offsets. Rejected for v1: a common-start/common-end diff in the dialog (display only). Open for the owner.
- DECISION: `chars-removed` has no row sentence: there is no approved string, and the removed characters
  are invisible anyway. The flag is in `data-flags` only. Rejected: a new sentence ("Characters onX can't
  read are removed."), which needs the owner's wording. Open for the owner.
- DECISION: "Match case" is a button with `aria-pressed` (the contract) drawn as the app's checkbox (the
  mockups' look). Rejected: a `.tog` box or the "Leave as is" pill.
- DECISION: `.na-more` reuses the export screen's long-note warning wording, "and N more" (number with
  thousands commas, like `plural`). Rejected: the map title's "+ N more".
- DECISION: the text-mode dialog is 680px wide (Icon & color renders 560px: `.modal-card`'s width wins over
  `.mark-dialog`'s 620px) so the four note modes fit on one line at 14px. Rejected: 13px toggles at 560px.
- DECISION: a note row shows whose note it is (NoteA2) above the note, outside `.na-before`; a nameless
  item's label reads "Untitled" greyed with class `untitled` (not `.is-placeholder`, which marks name
  cells only). Note cells keep line breaks (`pre-wrap`, clamped to three lines); name cells keep spaces
  (`pre`), so a cell's innerText is the stored value.
- DECISION: Enter (names) / Ctrl or Cmd+Enter (notes) always calls Save's function, which works the change
  out again and saves nothing when nothing changes, rather than reading Save's possibly stale `disabled`.
  Same result in the steady state, and a fast "type, Enter" inside the 60 ms window still saves.
- DECISION: mode and Match case clicks redraw at once (seq +1 before the click returns); only typing waits
  60 ms.
- DEVIATION: `closeBulk` is not unchanged: it also clears the text mode's timer and removes `data-bulk`,
  `data-preview-seq` and `aria-labelledby`, so no later dialog or wait sees a closed one's state.
- DEVIATION: the "Save your note?" confirm moved out of `requestExport` into `askToSaveNote(go, ret)`,
  shared by Export and the two dialogs (same title, body, buttons and order).
- FOR C: `data-preview-seq` restarts at "0" on every open and the first render makes it "1" before the
  menu click returns. Save with nothing to save leaves the dialog open and redraws (seq +1). After Save or
  Esc `#mark-dialog` carries no `data-bulk`.
- FOR D: `window.__cairnPerf` exists from page load (`null`s until the first preview); `lastPreviewMs`
  includes the transform; `lastSaveMs` covers re-read, transform, edits, refresh and status.
- 15:42 `0aa8ab1` Help line, FAQ entry (+ "No regex yet."), faq.html rebuilt, DECISIONS UI-39 and ENG-09,
  DECISIONS' "(no name)" → "Untitled", LABELS.md Help and FAQ rows.
- DECISION: Help keeps listing every More item, Rename… and Change note… included, then the approved line
  verbatim ("Rename… changes many names at once; Change note… does the same for notes."). Rejected: leaving
  them out of the list (the line wouldn't say where they are) or rewording the approved line to avoid
  naming them twice.
- DECISION: FAQ: besides the new question, the bulk-edit answer's More bullet names both items, its "you
  edit names and notes one item at a time … aren't built yet" sentences go, and the round trip's step 3
  loses "Names and notes are edited one item at a time." Step 3 does not add names and notes, so "the
  edits listed in step 3 all came back as made" claims nothing about bulk renames (untested in onX).
- 15:44 `b4ae60f` merged feat/bulk-rename (Track A's core, `30f9a7c`); a merge commit, not a fast-forward,
  since this branch had commits.
- A's notes FOR B, checked: `field` is always "name" / "desc" and `matchCase` a real boolean (the dialog's
  spec starts `matchCase: false` and the toggle flips it). app.js's `writtenNote` has been
  `CairnRename.writtenNote` since `cd0e166`, so `noteOverflow` (the row mark and the dialog flag) already
  trims the outer NEL as the writer does: the gap A found is closed, nothing more to do.
- 15:45 `0235cc6` Back to the drop screen (with unexported changes) closed the leave prompt's way but left
  the dialog open under "Leave this map?": `leaveMap` now closes it first.
- 15:45 click-through on the real core (throwaway script, 34 checks, all pass): "Save your note?" order
  and each choice; guards (requestExport, requestStartOver, openBulk, openMoveTo, openNote, Ctrl+A) leave
  the dialog as it is; Tab stays inside; Enter with nothing and Enter right after deleting save nothing;
  Save inside the debounce uses the final text; status, focus on More, attributes cleared; Enter adds a
  line and Ctrl/Cmd+Enter saves in notes; Esc, backdrop; Back → "Leave this map?" with the dialog gone,
  Stay; a rename that empties the selection focuses `#filter`; a pending merge offer opens and the dialog
  doesn't. 3,002 rows (make_map(20, per=(150, 150))): 8 keystrokes, preview 1.8 ms (transform 0.4 ms),
  200 rows drawn + "and 2,802 more", Save 220 ms.
- 15:54 tests at `0235cc6` (BASE_URL=http://127.0.0.1:8782/): tests/web/test_web_app.py 239 passed (6:29);
  `-k "csp or boots"` 3 passed; tests --ignore=tests/web 1150 passed (labels inventory and
  build_faq_page --check included; 1150 + 239 = the 1389 baseline). No existing assertion needed changing
  (the Help sentence has no test), so no DEVIATION there.
- Screenshots (1440×900, gitignored): `archive/bulk-rename/` in this worktree: r00–r10 (Rename: menu,
  each mode empty and typed, Match case on/off, blank → Untitled with Save on, chars-removed, Campsite,
  status), n01–n08 (Change note: each mode, multi-line Find, over 512 with the sentence, blank, status and
  caution marks), c01 (Save your note?), x01 (export screen's long-note warning after a bulk note change),
  m01/m02 (Icon & color beside Rename, same selection). `*.aria.txt` beside each dialog state: Playwright
  aria snapshots (dialog named by its h2, every field labelled, toggles pressed, Save disabled).
- FOR orchestrator: `.github/workflows/codeql.yml`'s comment lists `web/app.js, web/icons.js`; rename.js
  could join it (comment only). TODO.md's "On hold" line for bulk rename → Done (DoD 6) is not a B file.
- FOR orchestrator: walkthrough shots need no rerun for B (the Icon & color dialog is unchanged); the
  walkthrough doesn't mention renaming.
- Open for the owner (B): a green highlight of the changed part, as the mockups drew it; a row sentence for
  `chars-removed`.
- FOR C: `test_opening_rename_with_a_pending_folder_merge_offer_flushes_it_first` can't be driven by real
  clicks: after typing a taken name in a folder header, the click on More releases the pointer, the
  deferred render runs (`updateSel` → `closeMenu()`) and the merge confirm opens before Rename… can be
  clicked. By keyboard, Tab out of the name opens the confirm on the next task. The path that matters is
  reached programmatically: type the taken name in `.folder-name-in`, then
  `page.evaluate("document.activeElement.blur(); openRename()")` → `CONFIRM` set, `BULK === null`, the
  merge confirm's title visible, no `#mark-dialog[data-bulk]`. (Checked that way, passes.)
- 15:58 checked under the enforced CSP (plain context, no evaluate): tick 3 rows, More → Rename…, 3 rows,
  type, `data-preview-seq` moves, summary "3 will change · 0 unchanged", Save, status "Changed 3 items.",
  no console errors.
- Note: the merge commit `b4ae60f` carries git's default-less `-m` subject without the Co-Authored-By /
  Claude-Session trailers; it is not HEAD, so it was left as is rather than rewriting history.
- 16:00 `a255978` orchestrator follow-ups 1–3:
  - the After cell marks its new part (`.na-after .hit`, background `--sel-row`, which is the mockups'
    #E9EFDF exactly, so no new token);
  - "Save your note?" says "Untitled" for a nameless item (Export's confirm too, the same function);
  - "No regex yet." is out of the FAQ answer (faq.html rebuilt, `--check` passes). DECISIONS UI-39 and
    LABELS follow.
- DECISION (supersedes 15:38's "no highlight"): the highlight is the part of `after` between the start and
  the end it shares with `before` (a note's written form), counted by code point. Rejected: match offsets
  from the core (not in the contract). Details:
  - one span from the first change to the last (v1);
  - none for an empty result (the "Untitled" placeholder), a pure deletion (the Campsite case marks
    nothing) or an unchanged row;
  - the span widens so a combining mark, variation selector, skin tone, ZWJ sequence or flag isn't split;
  - the cell's text content is exactly `after`; every piece goes through `esc()`.
- 16:05 `de93ae8` (amended before anyone pulled it):
  - Add before matches the shared end first, so "BR · " before "Bass" is marked, not "R · B" (seen in
    r02);
  - no padding in the highlight: inside a word it read as a space; a 1px box-shadow widens the patch
    instead;
  - follow-up 4: arrow keys in `#more-menu`.
- DECISION: `#more-menu` (role=menu, six items) takes ArrowDown / ArrowUp over its enabled items, wrapping,
  plus Home and End, as the Move to… list does. Esc and Tab are unchanged. Rejected: Tab only. Checked:
  Enter on More focuses Move to…; Down, Down, Up, End, Down (wraps), Home, Up (wraps) land where expected;
  a keyboard-only Down, Enter, type, Enter renames and returns focus to More.
- Throwaway checks of `markChange`, 16 cases, all pass: prefix, mid-word replace, deletion, NFD "é", ZWJ
  family, flag, skin tone, paired emoji, HTML-looking text, two matches, a note's added line, empty before,
  and Add before's end-first case.
- 16:07 tests at `de93ae8` (BASE_URL=http://127.0.0.1:8782/):
  - test_labels_inventory 2 passed;
  - build_faq_page `--check` exit 0;
  - test_web_app `-k "csp or boots"` 3 passed;
  - test_web_app `-k "note or bulk or mark"` 76 passed.
  - Screenshots retaken, all of r00–r10, n01–n08, c01, x01 (r02, r06, r09 and n02 looked at: highlights
    right, Campsite unmarked, no console errors).
- Orchestrator's Chrome click-through on feat/bulk-rename, as reported to me:
  - Campsite: 3 changed, 1 "No change", no flags, Enter saved, "Changed 3 items.", focus on More;
  - search "trail", 6 rows of three kinds, find "trail" with an empty Replace with: all six left the
    filter, focus went to `#filter`, the export carried the new names ("Old  cutoff" with its double
    space);
  - Add after with an emoji on 20 hostile notes: `note-over-limit` matched the caution marks and the
    export warning, CRLF became LF, a blank note got the text with no leading line break, every stored
    note equals its GPX `<desc>`.

### 5.C Track C (tests)

- 15:22 started on bulk/c-tests at 0ab2679
- 15:23 the live tracker refused my Edit (the tool keeps this agent inside its worktree), so per
  section 1's fallback this log lives in the worktree copy, uncommitted; the final report says so.
- 16:05 `7a3efa5` naughty_strings.py (86 entries), bulk_rename_vectors.py, test_rename_core.py (U layer:
  every U id + properties 1-12 at 300 vectors, plus a few extras). Today: 6 helper tests pass, 127 transform
  tests skip on the stub, 1 strict xfail. Against a scratch by-the-rules reference transform (never committed)
  133 pass.
- DECISION: every string crosses Playwright as a list of UTF-16 code units (rebuilt with
  String.fromCharCode / decoded with surrogatepass), not only "booleans and lengths for surrogate cases".
  Exact for lone surrogates, NUL and U+FFFE, so every property can include them. Alternative (plan 6.1):
  booleans and lengths only; kept as written for `test_lone_surrogates_are_removed`.
- DECISION: two fixtures, `core` (helpers, runs now) and `live` (skips while transform is the stub), so the
  final helpers are tested today. Alternative: skip the whole module.
- DEVIATION: `test_zero_width_space_and_bom_are_kept_in_names` keeps the BOM inside the name. The plan's
  "Camp​﻿" puts it last, and the final cleanName uses JS trim(), which counts U+FEFF (and NBSP) as
  whitespace and trims it silently. Pinned as `test_a_trailing_bom_or_nbsp_in_a_name_is_trimmed_like_a_space`.
- DEVIATION: property 9 (Match case on ⊆ off) is false for self-overlapping finds under left-to-right
  matching: "Aaa" find "aa" repl "Aa" changes with Match case on ("AAa") and is unchanged with it off (its
  "Aa" match at 0 blocks the one at 1). The generator now draws finds of 1-4 ASCII letters/digits that are
  all different ignoring case (no border, so no overlap), on top of the plan's İ/ı/K/ſ exclusion; the
  counterexample is pinned (`PINNED["match_case_overlap_*"]`,
  `test_match_case_on_can_change_a_row_that_match_case_off_leaves_alone`).
- DEVIATION: property 6's repl is drawn from non-space printables plus the $ patterns: cleaning collapses
  tab/line-break runs and trims outer whitespace, which would break the count for reasons other than $.
- FOR A: an empty Add before / Add after on a NOTE must not join with "\n". Taken literally, 3.1 makes
  raw = "" + "\n" + before, which differs from before, so a dirty note ("\x01abc ") is cleaned and flagged
  by a spec that types nothing (breaks property 4 and the no-cleaning-without-a-change rule). Expected:
  `unchanged`. Caught by `test_an_empty_add_before_or_after_leaves_a_dirty_note_alone` and property 4
  (checked by swapping in the literal join in scratch).
- FOR A (and orchestrator): cleanNote/writtenNote trim with JS trim(), the writer with Python str.strip().
  They differ on U+0085 (Python strips it, JS keeps it) and U+FEFF (JS strips). U+FEFF is harmless (the core's
  output is already trimmed); U+0085 is not: Add after "\x85" on note "abc" gives after "abc\n\x85", stored as
  that, and the GPX <desc> is "abc" (preview != file). Pinned as a strict xfail,
  `test_a_note_ending_in_next_line_exports_as_the_core_stores_it`; property
  `test_the_writer_leaves_a_cleaned_note_alone` covers every other character. Fix options: writtenNote also
  trims U+0085 (and keeps the rest), or the writer keeps it (cairn/ change). Remove the xfail with the fix.
  (Superseded: A had found and fixed it in `writtenNote` before this note reached anyone; see below.)
- 16:40 merged `feat/bulk-rename` (A's core, 30f9a7c) as `0b543f6`; stub skip removed; `ffcdaff` U layer
  green against the real core: **135 passed**, 0 failed, nothing pinned as a core bug. Applied the two 5.0
  decisions (BOM inside the name: "Ca﻿mp​!" → "xCa﻿mp​!", flags []; find == replace runs on
  rows without the other case, and pins "Camp A" → "Camp a" with Match case off and unchanged with it on) and
  A's notes: Python mirror of writtenNote trims an outer U+0085 like A's fix; the NEL test is now a plain
  regression (no xfail); property 7 asserts unchanged ⇔ after === before for names and notes; new
  `test_a_lone_surrogate_find_never_splits_a_paired_emoji` ("a🔥\uD83Db" find "\uD83D" → "a🔥Zb", flags []);
  `set` on names joins the unknown-mode test. Properties 1, 2, 8 already ranged over changed rows; property 6
  already drew repl from clean printables and counts by code point (strings are combined before counting).
- DECISION: the Write tool turned some `\uXXXX` escapes in my test sources into raw invisible characters
  (BOM, ZWSP, RLO, NBSP, U+2028, U+FFFE); a scratch scanner now rewrites every Cc/Cf/Z*/M*/Co/Cn/Cs
  character in my files back to an escape before each commit (raw bidi controls in source are a review hazard).
- 16:55 `b866501` W layer: test_bulk_prereqs.py (113) + test_bulk_round_trip.py (93), **206 passed**, no
  browser. 3.7(a), (f) and the optional (b) (cut and hole marks per item across forced split parts) done.
- DEVIATION: `test_set_note_on_1500_rows_with_512_bytes_splits_the_gpx`: 1,500 waypoints with 512-byte notes
  make ~1.07 MB, under DEFAULT_MAX_GPX_BYTES (3.75 MiB), so there is no split at the real cap. The test checks
  that first, then forces the split (`max_bytes=200_000`, as test_export_instructions does) and checks every
  part, 1,500 items, 512 bytes each, no cut line.
- DEVIATION: plan 6.6's "reader title equals the core's after exactly" is not what the onX reader does, by its
  own design: `normalize_name` strips the ends and decodes entities again ("x&amp; &lt;b&gt;" typed as text
  comes back "x& <b>"), and a note opening with "name=…" is read as onX's desc block ("name=evil\nnotes=y\nx"
  → note "y\nx"). The exact check is on the GPX <name>/<desc> text (ElementTree); the reader is compared after
  its own cleaning, and the differences are pinned in `test_the_reader_side_differences_are_pinned`. A blank
  <name> reads back as "" (recorded, as 6.6 asks). An empty note writes no <desc> at all.
- DECISION: the Python mirrors of the core's cleaning (py_clean_note etc.) live in bulk_rename_vectors.py;
  `test_a_naughty_note_round_trips_through_the_onx_reader` stores py_clean_note(text) (what Replace the note
  stores) and asserts the GPX <desc> equals it exactly for all 86 naughty strings. The mirror is checked
  against the JS on 300 strings in test_rename_core. Alternative: store the raw naughty text (then the test
  only re-states the writer's own cleaning).
- DECISION: GeoJSON loading strips titles and eats U+0085 at edges (" Camp " → "Camp", "a\x85" → "a"), so
  W tests that need an exact starting value set it with apply_edits, and items are found by tag, not uid order.
- 17:30 `e82dbbb` plan 6.3 helpers appended to tests/web/helpers.py and test_bulk_text.py (82 E/E-csp tests),
  skipping while index.html had no #bulk-rename. Merged B (`d89e4d6`): first run **81 passed, 1 failed**.
- DECISION: `_open_bulk` waits on the DOM (`data-bulk`, `data-preview-seq` >= 1) instead of calling
  `_menu_action` with its fixed sleeps (plan 6.3 said `_menu_action`). `_type_spec` waits for a render after
  each field it fills (a field already holding the value is skipped, since no render would come).
  `_preview_rows` uses function-form `evaluate_all`, which works under the enforced CSP (checked).
- DECISION: the skip-until-B gate fetched the served index.html with urllib (no browser boot per test);
  removed in the commit that flips the E layer green, as plan 4 says.
- DEVIATION: `test_pasting_multiline_text_into_the_name_prefix_field`: Chromium turns a pasted line break in an
  `<input>` into a space ("A\r\nB" → "A B"), not nothing ("AB") as the plan says. The test pins "A B" and no
  `chars-removed`. Paste is a real clipboard paste (permissions granted on the context), not a synthetic event.
- DEVIATION: `test_browser_zoom_200_keeps_save_reachable` emulates 200% zoom at 1440×900 as a 720×450 CSS
  viewport (what the zoom gives the layout); Playwright has no browser-zoom call.
- DEVIATION: `test_opening_rename_with_a_pending_folder_merge_offer_flushes_it_first` runs the blur and the
  menu item's click in one synchronous evaluate (B's note: real clicks let the deferred timer run first).
- FOR B: `test_rename_then_shift_click_range_after_save_uses_a_fresh_anchor`. Repro: map "Alpha 1", "Alpha 2",
  "Beta 1..3"; search "Alpha"; tick both Alpha rows; Rename… Find "Alpha" Replace with "Gamma"; Save (the
  search prunes both, SEL is empty); clear the search; shift-click the 4th row. Expected: `ANCHOR` null after
  the Save (plan 5.5 cites the afterMove rule `if (!SEL.size) ANCHOR = null`), so the shift-click selects one
  row. Actual: `ANCHOR` is still "i1" (the pruned "Gamma 2"), and the shift-click ranges from it. Fix: the same
  line in `applyTextBulk` after `refreshAfterEdit()`. Pinned as a strict xfail; remove the mark with the fix.
  (The same stale anchor exists today when a plain search hides the selection; only the bulk path is pinned.)
  Checked in scratch: with `ANCHOR = null` set by hand after the Save, the rest of the test passes.
- 17:55 `b8670ab` E layer green, skip removed: 81 passed, 1 xfailed (the FOR B above). Merged B's follow-ups
  (`4e0ab2c`, de93ae8); `92cfd60`: `test_keyboard_only_flow` uses the More menu's ArrowDown/ArrowUp, and
  `.hit` is checked absent on unchanged rows and on the placeholder. E against de93ae8: 81 passed, 1 xfailed.
- 18:10 `f32d280` added the E side of `test_a_bulk_note_with_html_looking_text_on_a_caltopo_map_exports_verbatim`
  (a coverage script found it missing). Final runs at HEAD `f32d280`: U + E 217 passed + 1 xfailed (135 U,
  82 E, the FOR B xfail); W 206 passed; whole non-web suite 1356 passed (1,150 before Track C + 206 W).
  tests/web collects 457 (239 + 135 U + 83 E). Section 5 coverage: every U/W/E id has a test of that name in
  its layer file except `test_final_sigma_matches_only_itself` (renamed per 5.0). Dev server 8783 stopped.
- FOR D / integration: `test_a_find_string_longer_than_10k_characters_does_not_hang` (U) asserts the transform
  takes < 1000 ms on 1,500 rows (measured ~1 ms); generous, but it is a wall-clock check.

### 5.D Track D (fuzz and perf)

- 15:44 started on bulk/d-fuzz at 30f9a7c
- 15:47 logging here in the worktree copy, uncommitted (the live file can't be written from a worktree, 5.0)
- 15:58 `c4124db` fuzz_ui.py: `a_bulk_rename`, `a_bulk_note`, `a_bulk_rename_hostile` (WEIGHTS 3/3/1), the
  `big1500` map (`make_map(10, per=(150, 150))`: 1,502 items, the two loose ones included), the SNAP_JS
  fields of 6.4 (`bulkKind`, `saveDisabled`, `naRows`, `previewSeq`, `edits`, `names`) and the bulk
  invariants. Dry run before the dialog existed (bitterroots, big1500, 60 actions each): green, the three
  actions recorded `("bulk_rename", "not built")` and touched nothing.
- Nothing to retire: no existing fuzz invariant treated an empty item name as a Violation (`a_edit_name`
  already typed `""`; `verify_export` reads an empty `<name>` as `""`).
- DEVIATION: most bulk invariants run inside the actions, not in `check()`: `check()` runs after the
  action, when the dialog is closed again. The action checks the list once it has settled (open state,
  after typing) and the store after Save / Esc / backdrop (the `a_move_to` / `move_list_stale` pattern).
  `check()` holds the ones that hold at any time (names are strings; no stored XML-forbidden character
  that Cairn wrote; the list's invariants if a dialog is ever left open with no render pending; the
  modal in step with BULK was already check 7). Rejected: leaving the dialog open for `check()` to read
  (every following action would hit the modal).
- DECISION: invariants beyond the 6.4 list, each cheap and each a claim of the plan: the dialog opens on
  Add before with Save off and "0 will change" (default 16); the mode toggles in the decided order; the
  title's N equals the ticked rows; changed rows first and exactly min(N, 200) rows drawn (decision 13);
  summary N + M = rows; Save's status N equals the summary's N (not only ≤ the selection); every row the
  list showed is stored as shown (placeholder → `""`), a "No change" row is untouched, exactly N items
  differ and only ticked ones, the other field untouched; Esc / backdrop / a Save with nothing to change
  change nothing (EDITS included); empty Find + text gives every changed row `clean(text)`; empty Find
  and empty Replace with changes nothing; a prefix/suffix holding a forbidden character flags every
  changed row `chars-removed`; a `$&$1$$` replacement lands literally; a note cell never shows a placeholder
  (decision 18); no name or note that Cairn changed (in EDITS) holds an XML-forbidden character (notes
  too, not only names). Rejected: exactly the 6.4 list (it can't see a preview that differs from Save).
- DECISION: the GPX `<name>` multiset invariant of 6.4 is the existing `verify_export` per-folder check
  (`zip_folder_names`: per folder, included items' names == the GPX names, `""` for an empty one), which
  is stronger than "every GPX name is in the item names"; no second copy added.
- DECISION: a stored value with an XML-forbidden character is a Violation only when EDITS holds that
  field (Cairn wrote it); a value loaded that way and never touched is legal (the no-op rule leaves it,
  the writer drops it). Rejected: comparing with the values at load in Python (lone surrogates don't
  cross CDP intact; the JS side answers with uids only).
- DECISION: text goes into the fields with `fill()` (or `press_sequentially` for short printable ASCII,
  30 %), never `keyboard.type`: a `\n` typed into a name `<input>` is Enter, which saves mid-action.
  Expectations read the fields back, since a line break or NUL may not survive a field.
- DECISION: waits are on `data-preview-seq` (read before, wait for more) and then on no pending render
  (`BULK.text.timer`, B's internal; if it is ever renamed the wait passes at once and only the seq wait
  remains). A fill that leaves the field's value as it was expects no render.
- DECISION: a Save with nothing to change uses `click(force=True)` (Playwright won't click a disabled
  button) or the field's Enter / Ctrl+Enter; the dialog must stay and nothing change, then Esc.
- DECISION: `big1500` is not in MAP_ORDER: the default `--maps` and the `seed % 6` README text stay as
  they are, and the big map runs only when named. Rejected: adding it (every default release run would
  cycle onto the slowest map and the README would be wrong).
- DEVIATION (CLI): `--n` is an alias of `--actions`, and `--every-map` runs every seed on every listed map.
  Without it `--seeds 1,2,3` on four maps runs three sessions (seed % 4: hostile, twins, big1500) and never
  bitterroots, so the plan's "3 seeds × 300 actions × 4 maps" needs the flag. Rejected: `--seeds 1-12`
  (three seeds a map, but not the seeds 1, 2, 3 asked for).
- DECISION: naughty strings come from Track C's `tests/naughty_strings.py` (`NAUGHTY_TEXTS`) when present,
  else a 30-entry inline fallback of the same kinds (fuzz_ui already imports from tests/; nothing under
  tests/ imports fuzz_ui). No lone surrogates in either pool.
- 16:00 `82393a5` tests/web/test_bulk_perf.py: `test_a_prefix_on_1500_rows_stays_under_the_preview_budget`,
  `test_a_prefix_on_3000_rows_stays_under_the_preview_budget`,
  `test_a_find_string_longer_than_10k_characters_does_not_hang`. Before the dialog: 3 skipped
  ("not built yet"), in 0.3 s.
- DECISION: the skip is a module-scoped autouse fixture that depends on `_require_server` and looks for
  `id="bulk-rename"` in the served index.html (urllib). Rejected: a `skipif` marker, which runs before the
  server check and would call a down server "not built".
- DECISION: the 8 characters are typed one `press_sequentially` call per character, each followed by a
  wait for `data-preview-seq` to move, so there are exactly 8 renders and 8 readings of `__cairnPerf`.
  Rejected: one `press_sequentially(…, delay=120)` and a MutationObserver log (a slow machine coalesces
  two keys into one render and the count wobbles).
- DECISION: the assertion is on the worst keystroke (max), not the mean; the load dismisses the onX fill
  warning (generated areas are filled) with Esc and waits for "N selected" before opening.
- DEVIATION: C's bulk helpers (plan 6.3) aren't merged, so the perf file keeps private copies under C's
  names (`_open_bulk`, `_set_mode`, `_type_spec`, plus `_preview_seq`); BASE_URL, `_menu_action` and
  `_select_all_shown` come from tests/web/helpers.py. After C merges this is one import line.
- FOR C: `test_a_find_string_longer_than_10k_characters_does_not_hang` exists twice on purpose: the plan
  gives it layers U and P. Yours (test_rename_core.py) is the U one on the core; mine (test_bulk_perf.py)
  types the 10,000-character Find into the dialog of a 1,502-row map. Different modules, no clash.
- 16:01 `0a442f6` merged feat/bulk-rename at `0235cc6` (B's dialog).
- 16:02 perf, BASE_URL=http://127.0.0.1:8784/, local Mac, no CI factor, worst of 8 keystrokes:
  1,502 rows: transform 0.5 ms (budget 10), list 2.0 ms (50), Save 114 ms (500);
  3,002 rows: transform 0.7 ms, list 2.3 ms, Save 228 ms; 10,000-character Find on 1,502 rows: transform
  3.3 ms, list 4.5 ms, typed and drawn in 90 ms, "0 will change · 1,502 unchanged", Save off. 3 passed.
- 16:04 `4af6a0b` harness fix found by the first try run: after a Save with nothing to change and the Esc
  that followed, the action checked the status line as if it had saved (it read "Moved 1 item…").
- 16:05–16:31 fuzz run 1, against `0235cc6` (B's dialog, before its follow-ups): `--maps
  bitterroots,hostile,twins,big1500 --seeds 1,2,3 --n 300 --every-map`, 12 sessions, 11 green (3,442
  actions, 130 exports verified, 0 harness errors). One Violation, not in the bulk feature:
  `focus_lost_to_body` at seed 2 / twins / action #130, a folder rename by Tab
  (`('rename', 'New folder', 'Zürich Café', 'Tab', None)`; the actions before it: `#129
  click_new_folder` with nothing ticked, named "new FOLDER" + Enter). It replays deterministically on
  that code. B's diff touches no folder-rename or focus code; a Tab-out probe on a fresh twins map
  (empty and filled folders, three new names) keeps focus on both `0235cc6` and `30f9a7c`, and a replay of
  the record on `30f9a7c` diverges (its bulk actions are "not built"), so not yet reduced. Bulk actions
  in run 1: Rename… 72 (15 saved, 11 cancelled, 9 Save with nothing to change, 37 no row shown), Change
  note… 75 (33 / 9 / 4 / 29), hostile 8 (7 saved); every "no sel" had 0 rows shown (a search or folder
  filter), never a selection the action failed to make.
- 16:33 merged feat/bulk-rename at `548421a` (B's follow-ups `de93ae8`, C's tests, the ANCHOR fix) as
  `d831fdc`. `34a3cb5`: the perf test now imports C's helpers (`_open_bulk`, `_set_mode`, `_type_spec`,
  `_preview_seq`, `_wait_preview_past`, `_save_bulk`, `_status_count`); the private copies are gone.
- 16:34 perf at `548421a`, same machine, worst of 8 keystrokes: 1,502 rows transform 0.4 ms, list 2.2 ms,
  Save 116 ms; 3,002 rows transform 0.6 ms, list 2.5 ms, Save 227 ms; 10,000-character Find 3.3 ms /
  4.6 ms, 89 ms typed and drawn. 3 passed (9.8 s).
- 16:35–17:01 fuzz run 2 (final), against `548421a`, same command: **12 of 12 sessions green**, 3,612
  actions, 136 exports verified (Download all + every per-folder zip), 0 harness errors, 0 Violations.
  Bulk actions: Rename… 76 (18 saved, 10 cancelled, 8 Save with nothing to change, 40 no row shown),
  Change note… 76 (34 / 10 / 3 / 29), hostile 8 (7 saved, 1 no row). With C's `naughty_strings.py`
  merged the text pool is C's, so from the first pool pick on (seed 2 / twins: action #39) the sessions
  differ from run 1's; seed 2 / twins passed #130 in a different state.
- Run 1's `focus_lost_to_body` still reproduces at `548421a` when its record is replayed with run 1's
  pool (a local driver sets the old inline pool). Shrunk (ddmin, 51 replays) to 27 actions, one of them a
  Change note… Save. Replayed with that Save done by plain `edit()` calls instead of the dialog, it
  fails the same way on `548421a` **and on `30f9a7c` (no dialog at all)**: not the bulk feature.
  Cause, from a probe at the failing step: two folders, "camp" (34 items, collapsed) and an empty
  "New folder"; the empty folder's header name is the last tabbable control on the page, so Tab from it
  leaves the page (`document.activeElement` = body), as in any browser. A harness false positive:
  `0229b30` makes `finish_field` record such a Tab as "Tab-out" and the focus check skips it (no rng
  draw added, so every session's actions are unchanged). With it, run 1's record replays green, and the
  whole session (seed 2 / twins, run 1's pool) runs 301/301 green at `548421a`.
- Run 2's result stands for `0229b30`: the fix only relaxes the focus check for Tab-out, and run 2 had
  no Violation.
- DEVIATION: for that bisect a second, temporary server served `git archive 30f9a7c web` (pre-dialog) from
  `archive/qa-fuzz/pre_b/` on port 8786 (no track's port). Stopped with mine at the end.
- 17:20 extra run, bulk-weighted (a local driver in archive/qa-fuzz raises the three bulk weights to
  40/40/20), `548421a` + `0229b30`, seeds 4,5,6 × the 4 maps × 100 actions: 12/12 green, 0 harness errors;
  Rename… 196 (96 saved), Change note… 236 (92 saved), hostile 116 (69 saved): 257 bulk Saves, each
  checked row by row against the list it showed.
- No product bug found: no FOR B.
- FOR orchestrator: scripts/qa/README.md (not a D file) still describes the folders fuzzer only. It could
  say: the bulk actions (Rename… / Change note… / hostile), the `big1500` map (named in `--maps` only, not
  in the default rotation), `--n` as an alias of `--actions`, and `--every-map`; the bulk release run is
  `--maps bitterroots,hostile,twins,big1500 --seeds 1,2,3 --n 300 --every-map` (~20 min on this Mac).
- FOR orchestrator: the generated records, logs and the local drivers (`heavy.py`, `oldpool.py`,
  `nobulk.py`, probes) are in this worktree's `archive/qa-fuzz/` (gitignored).

## 6. Open questions for the owner (not blocking)

- Wording #10 from the label audit: should "Leave this map?" say "This discards N unexported changes."
  like Start over? (pending owner)
- An empty note's row button reads "Add a note"; keep it, or make the cell blank? (pending owner)
- `chars-removed` has no row sentence (no approved wording; the removed characters are invisible anyway). The
  flag is still in `data-flags`. Want one? A candidate: "Characters onX can't read will be removed." (B, 5.B)
- Decision 21 said "Web Map" goes from every context. User-facing text is done; about 60 internal lines
  remain (research notes, DECISIONS evidence, code comments, fixture READMEs; real export files can't
  change). Sweep the internal docs and comments too, or leave dated evidence as written? (orchestrator)
- The changed-part highlight marks one span from the first to the last change when Find matches several
  times in one value. Good enough, or highlight each match? (orchestrator, 5.0)

## 7. Follow-ups (owner, 2026-10-25, after the build)

Base for every follow-up track: the commit that adds this section on `feat/bulk-rename`. Same rules as
section 1 (worktree, own port, log in your worktree copy's subsection below, never commit this file).

### 7.1 Owner answers to section 6

| # | question | answer | status |
|---|---|---|---|
| 1 | a sentence for removed characters? | **No: drop them silently, and the same rules apply to every text edit** | decided; T builds the single-edit side |
| 2 | highlight: one span or each match? | show both in a rendered artifact | **artifact published** (https://claude.ai/artifact/S7br3nfPgn7tNU6KnsdpSw, board 2): real renders, built vs each match. Finding: the built common-start/end diff marks *characters*, not the replacement ("Bear Creek Trail" → "Bear Creek Tr." marks only the "."; "Sawtooth" mid-word marks "railhead…"). Recommendation: each match in Find and replace. **Owner (later 2026-10-25): Find matches whole words only** ("TH" never inside "Sawtooth"; punctuation is not part of a word). Rules restated to the owner for confirmation; core change waits on that |
| 3 | "Web Map" in internal text | **remove it everywhere** | S |
| 4 | "Leave this map?" count; "Add a note" cell | unsure: show the behaviour under several conditions | **artifact published** (same link, boards 4a and 4b): 1 and 5 changes now vs "This discards N unexported changes." (Start over's sentence) beside Start over; the empty note cell in three variants (now / blank / blank until hover or focus) × hover and keyboard focus, over a note row, a nameless selected row and an excluded row. **4a decided (owner, later 2026-10-25): no count.** "Leave this map?" keeps "Changes will be lost."; Start over? drops its count to match (orchestrator, for consistency; alternative: keep Start over's count). Sent to T. **4b decided (owner): variant C**, blank until hover or keyboard focus; sent to T |

**One rule set for every text edit** (answer 1). An *untouched* value is never cleaned (focus then blur
with no typing is a no-op; a dirty loaded value stays as loaded until edited; the writer stays the net).
After a commit the field shows the cleaned value, so what is on screen is what is stored.

| text | where it is edited | rule on an edited value |
|---|---|---|
| item name | single name field, bulk Rename…, Use note as name | `CairnRename.cleanName`: drop XML-forbidden characters, every whitespace run holding `\r \n \t` becomes one space, trim |
| note | note editor Save, bulk Change note… | `CairnRename.cleanNote`: drop XML-forbidden characters, CRLF / CR → LF, trim |
| folder name | folder rename (rail, header, + New folder) | **kept**: bridge `_clean_name` (control characters, C1 included, become one space; trim). DECISION (orchestrator): folder names also name the export's folders and files, so their stricter one-line rule stays. Alternative: the item-name rule. Owner to confirm. |

No row sentence and no warning for removed characters anywhere (the core's `chars-removed` flag stays as an
invisible `data-flags` value for tests). Plan section 3.1's "the single editor stores drafts untrimmed" and
3.7(e) "the single name editor doesn't trim" are **superseded** by this table.

### 7.2 Extra checks the owner asked for

| # | check | owner of the work |
|---|---|---|
| E1 | the longest name onX takes, for a waypoint, a track and an area | R (public docs and onX's public web-app code), T (Cairn: no limit, exported whole, test) |
| E2 | Find and replace changes every occurrence in a field | T (tests) |
| E3 | leading and trailing whitespace is trimmed | T (every path in 7.1's table) |
| E4 | double-confirm onX's note cut (512 UTF-8 bytes) and that Cairn never cuts | R (docs, code, the 2026-10-22 r1 evidence in commit `a07f14a`), T (tests) |
| E5 | read onX's public how-tos, docs and FAQ on mapping | R |

### 7.3 Follow-up tracks

| track | files | state |
|---|---|---|
| R research | `docs/research/ONX_PUBLIC_DOCS_2026-10-25.md` (new) | **done**, merged |
| S "Web Map" sweep (**done**, merged except the skill file) | docs, code comments, test comments and READMEs, TODO.md, LABELS.md section 16 (one internal phrase); **not** real export data under `tests/fixtures/` (`.gpx` / `.kml`), file names or URLs | not started |
| T text rules and tests (**done**, merged) | `web/app.js`, `tests/web/test_text_rules.py` (new), `tests/web/test_bulk_text.py` / `tests/web/test_rename_core.py` (additions), `tests/web/test_web_app.py` (only where an assertion pinned the old untrimmed behaviour; DEVIATION line each), `docs/design/DECISIONS.md` (UI-39 / UI-16 text rules), `docs/design/LABELS.md` if a label changes | not started |

S and T both touch `DECISIONS.md` and `LABELS.md`: S edits only lines holding "Web Map", T only the text-rule
lines; minimal hunks so the merge is clean.

Captures behind the artifact: archive/bulk-rename/choices/ (local). Also found in the capture and sent to T:
nameless rows' checkbox and note button are announced as "Select " / "Open note for " (should say Untitled).

### 7.4 Owner decisions, round 3 (2026-10-25, evening)

| # | decision | supersedes | status |
|---|---|---|---|
| W1 | **Find matches whole words only.** A match never starts or ends inside a word. Word characters: letters (with their accents) and digits; spaces and punctuation are boundaries, so "TH." matches "TH" and keeps its full stop. Each Chinese / Japanese / Korean character counts as its own word, so Find "山" still matches inside "日本語の山". A Find that starts or ends with punctuation or space only needs a boundary on its word-character edges ("(rainy)", " - "). Always on; no toggle. | plan 3.1 substring matching; C's tests that rely on matching inside words | to build (track U) |
| W2 | **The preview highlights each replaced match** (not one span) in Find and replace; Add before / Add after mark the added text | 7.1 #2 one span | to build (U) |
| L1 | **onX's limits, warned like notes:** item names over **255 characters** (onX's editor cap for waypoints, lines, tracks, areas; UTF-16 units, as onX counts) and folder names over **50 characters**: a caution mark, the dialog flag, the export screen's warning and an instructions.txt line, exactly as for notes over 512 bytes. Warn, never cut. Import behaviour is being verified live (L3). | decision 8 (no long-name flag) | to build (track V) |
| N1 | **A name is required to export.** An included item with an empty name (after trimming) blocks Export, with a status message and a caution mark on each such row; editing may leave a name empty for a moment, and bulk Rename… flags a result that would be empty but still saves it. Excluded items don't block. | decision 17 in part (names stay optional while editing, not at export) | to build (V) |
| E4b | the empty note cell: blank until hover or keyboard focus (variant C) | 7.1 #4b | T |
| L3 | **Verify the limits with live imports** into onX (the owner's logged-in browser; authorised 2026-10-25). Test data and a test plan either way. Never delete onX data; every probe markup is named ZZTEST. | plan section 7 "owner-run only" | **done**: names 255 UTF-8 bytes on import (all three kinds), notes 512 bytes, folder rename 50 characters, empty name → "Imported waypoint markup <timestamp>". `docs/testing/ONX_LIMITS_2026-10-25.md` |

**Strings for L1 / N1** (one set, used by U, V and the docs; parallel to the note sentence "onX imports only
the first 512 bytes of a note. About N characters will be cut."):
- name over **255 UTF-8 bytes** (L3 measured: onX's importer keeps the first 255 bytes of a name, on a character
  boundary, the same rule as notes): "onX imports only the first 255 bytes of a name. About N characters will be cut."
  (the note sentence's twin; measured with the same byte counter as notes, `CairnRename.noteBytes`)
- folder name over **50 characters** (onX's rename dialog stops typing at 50, `maxlength`; measured):
  "onX keeps only the first 50 characters of a folder name. About N characters will be cut."
- empty name, row caution and dialog flag: "Needs a name to export." (L3: onX would name it "Imported waypoint
  markup <timestamp>")
- Export blocked, status: "1 item needs a name." / "N items need a name."
The owner may reword.

### 7.R Track R log

- 17:46 started on followup/r-research at f3c3882
- 18:04 read all Backcountry (77), Hunt (118) and Fish (47) help articles via the Zendesk API, onX blog/product pages, and all 805 web-app chunks from backcountry.onxmaps.com. E1: typed name caps 255 (waypoint, line, track, area), 100 (route), 50 (folder); blank refused; import limit unknown (longest tested 66). E4: docs silent (and wrong: say notes aren't carried); code shows typed notes capped at 512 UTF-16 units (route notes uncapped), import cut server-side, not visible. The 3,303-char "line" fixture is an onX Route. Top diff: onX folder names cap at 50, Cairn allows 100. No URL blocked. Doc: docs/research/ONX_PUBLIC_DOCS_2026-10-25.md
- 18:08 committed efcf59f on followup/r-research (the research doc only); done
- (orchestrator) Cherry-picked onto `feat/bulk-rename`.

### 7.S Track S log

- 17:46 started on followup/s-webmap at f3c3882
- 17:54 sweep done in 5 commits (82 lines; the grep found 105 hit lines, not ~60):
  `073d265` code and test comments (cairn/ 6 lines in color_mapper, writers, input_check; tests 7
  lines in 5 files) · `2342850` fixture READMEs (25 lines in 15 READMEs) and one entry of
  `export_zip_sha256_e927aa9.json`'s `notes` list (no test reads `notes`; edited in place, not
  re-dumped) · `bb9d156` ONX_ROUND_TRIP.md (13) and the two 2026-10-22 research notes (19) ·
  `f198d25` DECISIONS.md (4 lines, only ENG-05 and UI-31 lines holding the name; the UI-31 quotes now
  carry the shipped "onX on a computer" wording), FOLDERS_RELEASE.md (3), TODO.md (1),
  ROADMAP_AVALANCHE_BRIDGE.md (1, tracked), LABELS.md section 16 +1 row ("onX's web app" for the
  thing, "onX on a computer" for where a person acts; its Don't-use cell points at the row above so
  it adds no new hit) · `d0e719e` `.claude/skills/cairn-tests/SKILL.md` line 58 (the Edit was
  accepted from the worktree; not refused).
- DECISION: "onX's web app" for the thing; "onX on a computer" where a person does something
  (DECISIONS UI-31 intro and instructions.txt steps, FOLDERS_RELEASE owner check, TODO phone-vs-
  computer line, research P1 probe step and prerequisites). Stacked possessives avoided ("the colour
  table in onX's web app", "onX's own page-load"). Alternative rejected: one blind substitution.
- Anchors: "## What onX's web app offers" keeps its explicit `<a id="import-paths">`; its 4 link
  texts renamed with it. No doc links to a heading slug holding the old name (checked
  `git grep "web-map"`: none; all cross-doc `.md#` anchors still resolve).
- Wheel: the cairn/ edits are comments only; `web/dist/` wheel NOT rebuilt (behaviour identical).
- Remaining `git grep -n -i -E "web ?map"` set (22 lines outside this tracker), each kept on purpose:
  URLs: `webmap.onxmaps.com` in web/bridge.py:1251, tests/test_export_instructions.py:28 (both are
  instructions.txt bytes behind the sha256 pin), LABELS.md:318, the 6 committed
  `cairn_output/*/instructions.txt`, KML_GPX_INPUT research :469, ONX_REIMPORT research :14; the
  `link=webmap` API parameter in ONX_ROUND_TRIP.md:228 and ONX_REIMPORT research :282.
  Real export data: `onx_real/onx_web_line_long_note.{gpx,kml}` (2 lines each, the owner's pasted note).
  Rule lines that name the retired term in order to ban it: LABELS.md:351 and :382, BULK_RENAME.md
  :144 / :440 / :895 (decision 21 itself), and every BULK_RENAME_PROGRESS.md hit (never committed).
- Tests: non-web suite 1356 passed; test_labels_inventory 2 passed; build_faq_page --check exit 0.
- 17:58 `e342c3f`: ENG-05's old KML warning paraphrase "(computer only)" became "(no phone import)",
  clearer; same line. Branch head e342c3f, 6 commits, 33 files, +82 / -81. Done.
- (orchestrator) Cherry-picked onto `feat/bulk-rename` as bedd5e7, 9fbe720, effd2da, bd59427, 03eaeff. **Not**
  `d0e719e` (`.claude/skills/cairn-tests/SKILL.md`): agent configuration, protected in the main checkout; left for
  the owner (one line: "real onX Web Map exports" → "real onX web app exports"). Kept on purpose: URLs
  (`webmap.onxmaps.com`, `link=webmap`), real export data, and the lines that state the ban (LABELS 16, the plan's
  decision 21): a rule has to name the word it retires.

### 7.T Track T log
- 17:46 started on followup/t-text-rules at f3c3882
- 18:20 Part 1 committed `5172831` (web/app.js, DECISIONS UI-39 + ENG-09, LABELS 3.4 + 4). Single name
  field: an edited value goes through `CairnRename.cleanName`, the field is set to the cleaned value, and a
  value that cleans back to the stored name is no edit; untouched (value === value at focus) returns first,
  so focus/blur or Enter on a dirty loaded name does nothing. Note editor: new `noteToSave(it, draft)` (the
  cleaned note, or null when the draft is the note as it was or cleans back to its written form), used by
  `closeNote`, `keepNoteDraft` and `noteIsChanged` (so "Save your note?", Start over's count and the leave
  prompt don't count a draft that only adds outer whitespace). Use note as name: `cleanName` instead of
  `oneLine`; a note cleaning to "" still leaves its row alone, and so does one equal to the name already.
  `oneLine` had no other caller (its definition, the `firstLine` comment, the one use): removed.
- CRLF: loaded notes can't hold `\r`. Checked with a probe (not committed) that injected CRLF / lone CR /
  trailing CR (raw in JSON, `&#13;&#10;` / `&#13;` char refs in XML, which survive the XML parser) into
  CalTopo GeoJSON, CalTopo GPX, CalTopo KML, onX GPX (two fixtures), onX KML (two), generic GPX, Cairn GPX
  and generic KML, then `bridge.load_document`: CR in a note = 0 on every path. Why: every reader builds a
  `ParsedFeature`, whose `clean_notes` makes CRLF/CR "\n" on both branches (`strip_html` and plain). So a
  Find typed in a textarea (only "\n") matches loaded notes across lines; no decision needed. Pinned anyway
  by an e2e (CRLF note in the file, Find typed across the line break).
- Side finding (no action): loaded **names** can hold a CR (CalTopo GeoJSON and GPX, onX GPX and KML;
  `ParsedFeature` only strips the title's ends). The untouched rule leaves such a name as loaded. Note that
  an `<input>`'s value sanitization drops CR/LF before the app sees it, so once the user edits such a name
  the stored value has the CR removed (by the browser), not turned into a space (cleanName's rule).
- DECISION: `bulk()` now skips an empty patch. Before, Use note as name on a row it leaves alone wrote
  `EDITS[uid] = {}`, which `unexportedChanges` counted (Start over said "1 unexported change" for nothing).
  Alternative: leave `bulk()` and accept an empty EDITS entry for a no-op row.
- DECISION: Use note as name skips a row whose name already equals the cleaned note ("an edit that cleans
  back to the stored value is not an edit"). Alternative: edit it anyway (an EDITS entry with the same name).
- DECISION: the note editor's no-edit test also gates `noteIsChanged()` (Export's "Save your note?", Start
  over's count, the leave prompt), not only Save. Alternative: keep the raw `draft !== desc` there, which
  asks "Save your note?" for a draft whose Save would save nothing.
- FOR orchestrator (coordinator item, done in `5172831`): a nameless row's checkbox, note button and
  Include chip now say "Select Untitled", "Open note for Untitled", "Include Untitled"; the popover's
  aria-label "Change icon and color / line / area for Untitled". No other aria-label or title in app.js
  interpolates an item name (the icon / line buttons and caution marks don't); `.na-src .na-name` and the
  popover title already showed "Untitled". LABELS 3.4 and 4 say "(Untitled when it has none)".
- 18:45 tests committed `3bd7a7e`: tests/web/test_text_rules.py (29) and tests/web/test_rename_core.py (+9).
- 18:55 DECISION (owner, 2026-10-25, via the coordinator): no change count in the discard confirms.
  "Start over?" with unexported changes says "Changes will be lost." (as "Leave this map?"), with nothing
  to lose still "This clears the current map."; buttons unchanged. commit `f491011`; DECISIONS
  UI-21, LABELS section 9 row and section 15's open row marked decided. Alternative it replaces: the
  counted sentence "This discards N unexported change(s)."
- DEVIATION: tests/web/test_web_app.py `test_start_over_counts_unexported_changes_and_escape_cancels`:
  body "This discards 1 unexported change." -> "Changes will be lost."; the count kept as
  `unexportedChanges() == 1`.
- DEVIATION: tests/web/test_web_app.py `test_start_over_counts_moves_and_renames`: body "This discards 3
  unexported changes." -> "Changes will be lost."; count kept as `unexportedChanges() == 3`.
- DEVIATION: tests/web/test_web_app.py `test_start_over_counts_only_changes_since_the_last_export`: final
  body "This discards 3 unexported changes." -> "Changes will be lost." (it already asserts
  `unexportedChanges() == 3` just before).
- DEVIATION: tests/web/test_bulk_text.py `test_start_over_names_the_bulk_changes_count` renamed
  `test_start_over_after_a_bulk_rename_warns_and_counts_seven_changes`; body "This discards 7 unexported
  changes." -> "Changes will be lost."; count kept as `unexportedChanges() == 7`.
- Tests per check (new ones in tests/web/test_text_rules.py unless named):
  - E1: `test_a_1000_and_a_3000_character_name_are_stored_and_exported_whole[name-field|bulk-rename]` (no
    `maxlength` on `.name-in`, `#bulk-find`, `#bulk-repl`; stored, in EDITS and in the GPX whole). Already
    there: core and writer 3,000-character tests (test_rename_core / test_bulk_prereqs
    `test_a_3000_character_name_is_stored_whole_and_exported_whole`).
  - E2: core `test_find_and_replace_changes_every_occurrence_in_a_field[6 ids]` and
    `test_find_aa_replaces_adjacent_and_overlapping_text_left_to_right[3 ids]` (test_rename_core.py); e2e
    `test_find_and_replace_changes_every_match_in_a_name_and_the_export_carries_them[match-case-off-changes-every-case|match-case-on-changes-only-the-exact-one]`,
    `test_find_aa_changes_adjacent_and_overlapping_text_left_to_right_and_exports_it`,
    `test_find_and_replace_changes_every_match_on_every_line_of_a_note_and_exports_it`,
    `test_a_note_loaded_with_crlf_line_ends_matches_a_find_typed_across_lines`.
  - E3: `test_the_name_field_trims_what_it_saves_and_shows_what_it_stored[4 ids]`,
    `test_a_line_break_pasted_into_the_name_field_becomes_a_space_and_the_ends_are_trimmed` (a real
    clipboard paste; Chromium makes the line breaks spaces), `test_the_note_editor_trims_outer_blank_lines_and_spaces_and_keeps_inner_ones`,
    `test_use_note_as_name_cleans_the_note_like_a_name`, `test_bulk_rename_trims_what_it_saves`,
    `test_change_note_trims_outer_whitespace_and_keeps_inner_line_breaks`; no-op:
    `test_focus_enter_and_blur_on_an_untouched_dirty_name_is_no_edit[2]`,
    `test_a_name_edit_that_cleans_back_to_the_stored_name_is_no_edit`,
    `test_saving_an_untouched_dirty_note_is_no_edit[4]`,
    `test_a_note_draft_that_only_adds_outer_whitespace_is_no_edit_and_export_does_not_ask`; forbidden
    characters: `test_a_forbidden_character_typed_in_the_name_field_is_dropped_silently`,
    `test_a_forbidden_character_typed_in_the_note_editor_is_dropped_silently` (status stays empty). A padded
    value can't be loaded (the readers trim), so the padded no-op cases put it in the model without an edit.
  - E4: `test_notes_over_512_bytes_export_whole_and_every_place_marks_the_same_ones[note-editor|change-note]`:
    512 / 513 / 600 bytes and 512 / 513 ending in a 4-byte emoji, every note whole in the GPX; caution
    marks, the dialog flag (Change note… route), the export screen warning and instructions.txt read from the
    browser's zip all mark the same three. Already covered before: caution = dialog flag = export warning
    (test_bulk_text `test_the_caution_marks_match_the_dialogs_note_flags`); caution = MANIFEST long_notes =
    export warning (test_web_app `test_the_caution_marks_the_same_notes_the_export_lists`); caution at
    600 / 512 / 513 bytes and in bytes, from the note editor (test_web_app
    `test_a_note_over_onxs_limit_gets_a_caution_that_goes_when_it_is_shortened`); the core's byte measure =
    instructions.txt's (test_rename_core and test_bulk_prereqs `test_note_bytes_in_the_dialog_match_instructions_txt`,
    `test_property_note_bytes_is_the_utf8_length_instructions_txt_counts`); emoji straddling 512 reported, not
    split (test_rename_core / test_bulk_prereqs `test_a_four_byte_emoji_straddling_512_is_reported_not_split`);
    exactly 512 not flagged (test_rename_core `test_note_exactly_512_bytes_is_not_flagged`); instructions.txt
    marks the very item (test_bulk_prereqs `test_instructions_txt_lists_the_new_names_and_flags_the_right_long_note`,
    test_gpx_areas `test_twin_names_only_the_item_with_the_long_note_is_marked`). Missing before, added: all four
    on one map from the real browser export, and "exported whole" for the editor and Change note… routes.
  - Coordinator item: `test_a_nameless_items_row_controls_and_popover_are_announced_as_untitled`.
- FOR orchestrator: scripts/qa/fuzz_ui.py types "  pad  " as a single name; it never compares a stored
  name with what it typed, so the trim doesn't trip it (read, not run).
- 19:20 whole web suite on `f491011`: **498 passed** (9 min 39 s, port 8785).
- 19:25 DECISION (owner, 2026-10-25, via the coordinator; variant C), commit `60ab28d`: an item with no
  note shows only the pencil in its note cell; "Add a note" appears while the row is hovered (`tr:hover`)
  or the note button has keyboard focus (`.note-btn:focus-visible`). CSS only (web/styles.css,
  `visibility`, so the row height and hit area stay); the button's accessible name stays its aria-label.
  Excluded and ticked rows behave the same (tested). Rejected: "Add a note" always (before), and always
  blank. DECISIONS UI-33 (one bullet), LABELS 3.4 "Add a note" row. Test
  `test_an_empty_note_cell_shows_add_a_note_only_on_hover_or_keyboard_focus`.
- FOR orchestrator: the empty note cells look different now; the walkthrough screenshots
  (scripts/make_walkthrough_shots.py) may want regenerating. Not done here.
- 19:50 final runs on `60ab28d`: web suite (tests/web, BASE_URL port 8785) **499 passed** (9 min 42 s);
  non-web (`--ignore=tests/web`) **1356 passed**. Total 1855 = 1816 + 39 (test_text_rules 30, core 9). A
  1440x900 screenshot of rows with and without notes, at rest and hovered, checked by eye (archive-free:
  scratch only). Dev server stopped.
- Unfinished: nothing in T's brief. Not done (not asked): walkthrough screenshots, the Chrome click-through.
- (orchestrator) Merged into `feat/bulk-rename` (no conflicts with S's and R's commits).

### 7.5 Round-3 tracks

| track | owns | state |
|---|---|---|
| U whole-word Find, per-match highlight, core flags | `web/rename.js` (whole-word matching; per-row match marks for the highlight; flags `name-over-limit` (UTF-8 bytes > `ctx.nameLimit`, default 255) and `name-empty` (a name result that is ""), both on changed rows only, warn-only); in `web/app.js` only the dialog: `openTextBulk` (ctx gets `nameLimit: NAME_LIMIT`), `drawTextBulk`, `afterCell` / `markChange`, `textFlag` (sentences from 7.4); tests in `tests/web/test_rename_core.py`, `tests/web/test_bulk_text.py`, `tests/web/test_text_rules.py`, `tests/bulk_rename_vectors.py`; DECISIONS UI-39 matching and highlight lines | running |
| V limits and name-required outside the dialog | `web/bridge.py` (`ONX_IMPORT_NAME_LIMIT = 255` bytes, `ONX_FOLDER_NAME_LIMIT = 50` characters, instructions.txt lines, an export guard), `web/app.js` everything outside the dialog (`NAME_LIMIT` / `FOLDER_NAME_LIMIT` read at boot like `NOTE_LIMIT`; row and folder caution marks; Export blocked with the 7.4 status; the export screen warning), `scripts/qa/fuzz_ui.py`, every test that exports a blank name or expects a long name unflagged outside the core, `docs/design/{DECISIONS,LABELS}.md`, `docs/FAQ.md` + `web/faq.html` | waits on the owner's answer about blank-named items in real maps (Bitterroots has 7) |

### 7.U Track U log

### 7.V Track V log
