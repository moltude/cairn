# Bulk rename and bulk note change — implementation and red-team plan

Revision 4, 2026-10-25, against HEAD `2f92e4b` (file:line references re-verified in that tree for revision 2),
after the owner's Phase 0 decisions and a second round the same day (§2, decisions 17–22: names are optional,
so an empty result never blocks Save). Scope: **More ▸ Rename…** (names) and **More ▸ Change note…** (notes)
on the selected rows (UI-17). Three of the four engine prerequisites of revision 1 have since shipped (§3.7),
so Track A is now `web/rename.js` only. Phase 0 is done; the mockups are on the Phase 0 canvas
(https://claude.ai/artifact/5F9oPZLuGRuqU2TaNY8rCN). Agent rules are in §4.

**Status 2026-10-25: built** on branch `feat/bulk-rename` (Phases 1–3 and Track D; Phase 4 waits for the
owner's review on localhost). Where the build departed from this plan, and why, is logged in
`docs/plans/BULK_RENAME_PROGRESS.md` (sections 4 and 5); that file wins where the two disagree.

---

## 1. Goal and non-goals

**v1 ships**

- **Rename…**: one dialog, three modes on the selected rows, in this order — *Add before* (prefix), *Add
  after* (suffix), *Find and replace* (plain text, "Match case" toggle, all occurrences; **an empty Find
  replaces the whole name**, so Find "" + Replace with "Campsite" normalises "Campsite - Oct 9th (rainy)",
  "Campsite - Oct 10th" and "Campsite - Oct 11th-12th (stay two days)" to three "Campsite"s). A live Now →
  After list with a per-row flag; Save applies through `edit()`; status reads "Changed N items." Names are
  optional: a result that is empty is saved as an empty name and shown as "Untitled"; no row blocks Save.
- **Change note…**: the same dialog shape for notes, four modes in this order — *Add before* / *Add after*
  (joined with a line break), *Find and replace* (identical layout and rules to names, multi-line fields),
  *Replace the note* (set every selected note to the text). Per-row 512-byte flag (warn, never cut: UI-34's
  rule). Duplicate names are allowed and never flagged (onX imports them). A missing note is simply blank
  (decision 18).
- One pure transform core (`web/rename.js`) used by preview and Save. **Headline invariant: the preview's
  After column == the value stored by Save == the GPX `<name>` / `<desc>` Cairn exports** (scoped in §3.1
  "Invariant scope"; the greyed "Untitled" shown for an empty name is display only, never stored or exported).
- Tests: unit/property on the core (seeded generators from Python, the browser runs the function), bridge,
  e2e under both CSP contexts, fuzz actions and invariants, a naughty-strings module, an accessibility
  snapshot per dialog state.

**Deferred (the FAQ says so in one line, public-copy style: "No regex yet.")**

- Regex find, capture groups, counters / numbering (`{n}`), case conversion, date tokens.
- An undo stack. v1's "undo" is Cancel before Save, and Start over / Back (UI-21, UI-37) after.
- NFC/NFD-normalised matching (v1 matches code points as stored; tested as "no match, no crash").
- Unicode case folding beyond `RegExp` `iu` (`İ`, `ß`, final sigma don't cross-match; documented).
- Per-row checkboxes inside the preview. Selection *is* the per-row choice.
- Mobile layouts (ENG-02).

---

## 2. Decisions (owner, 2026-10-25)

**Decided by the owner on the Phase 0 canvas** (https://claude.ai/artifact/5F9oPZLuGRuqU2TaNY8rCN):

1. **Modes in Rename…: option A** — three `.tog` toggles (the Style/Weight component) in this order:
   **Add before · Add after · Find and replace**, with one shared field row that changes per mode. Not tabs,
   not a token builder. **An empty Find (the default) means "replace the whole value"**: Find "" + Replace
   with "Campsite" turns "Campsite - Oct 9th (rainy)", "Campsite - Oct 10th", "Campsite - Oct 11th-12th
   (stay two days)" into "Campsite" (normalising someone else's map to your own standards). This replaces
   revision 2's "find === '' → no-op" rule. Consequences, all pinned in §3.1 and §5.4: while **both** Find
   and Replace with are empty the spec is a no-op (every row "No change", Save disabled) — so the mode
   opened with nothing typed shows no change, not a page of blank names; as soon as Replace with has text
   and Find is empty, every row's After is the Replace with text (a row already equal to it reads "No
   change"); Find "" + Replace with whitespace-only cleans to "" ⇒ every row's After is blank and shown
   "Untitled", Save enabled (names are optional, decision 17). Match case has no effect while Find is empty
   (the toggle stays as it is). The no-op rule raw === before ⇒ `unchanged` stays.
2. **Modes in Change note…: option A** — four toggles in this order: **Add before · Add after · Find and
   replace · Replace the note**. Add before/after join with a line break (notes are multi-line, UI-13).
   **Parity with names**: the Find and replace layout is identical to the names one (Find and Replace with
   side by side, Match case below, the same rules including empty Find = replace the whole note), except the
   note fields are multi-line textareas (Enter adds a line, Ctrl/Cmd+Enter saves). Replace the note stays as
   its own toggle. Empty Find + empty Replace with: the same no-op rule while both are empty. Replace the
   note with empty text clears every selected note (allowed; previewed as blank cells; nothing is blocked on
   empty, names included, decision 17).
3. **Duplicate names: option B, no warning.** No `duplicate` flag, no `ctx.otherNames`, no twin detection
   anywhere in the dialog. Twins are common in the owner's maps and onX imports them (ENG-06 probe). The
   Campsite normalisation above is the positive test: three identical names, no flag, Save enabled, three
   items exported (§5.5).
4. **Wording**: existing labels across the app are the default (Cancel, Save, "Untitled", "Changed N
   items.", the long-note caution sentence); new labels use these approved values —
   menu **"Rename…"** / **"Change note…"**; titles **"Rename N items"** / **"Change the note on N items"**;
   modes **"Add before"**, **"Add after"**, **"Find and replace"**, **"Replace the note"**; fields
   **"Find"**, **"Replace with"**, **"Text"**; toggle **"Match case"**; row sentence **"No change"**
   (and no sentence for an empty result: its After cell shows the existing placeholder **"Untitled"**,
   decision 17); long-note row: the app's existing caution-mark sentence (app.js:950, "onX
   imports only the first 512 bytes of a note. About N characters will be cut."); summary **"N will change ·
   M unchanged"**; status after Save: **"Changed N items."** (with a period, decision 19); buttons: the
   existing **"Cancel"** / **"Save"**; Help line **"Rename… changes many names at once; Change note… does the same for notes."**;
   FAQ Q **"Can I rename many items at once?"** A **"Yes. Tick them, then More → Rename…. Find and replace
   changes part of each name; Add before and Add after add text to every name."** A persistent inventory of
   every label and action is being created as `docs/design/LABELS.md` with a drift test; every new string
   from this feature is added to it **in the same commit** that introduces it (Track B, DoD 6).

**Stated defaults (not asked; default 7 is amended by decision 17, the rest are unchanged):**

5. One "Match case" toggle, off by default, in Find and replace only.
6. The transform lives in JavaScript (`web/rename.js`); Python keeps only the writer-side drop (§3.7(a)).
7. **An empty result name is allowed, never blocked** (amended by decision 17; revision 3 blocked it). The
   core returns `after === ""` as an ordinary changed row with no flag of its own; the dialog shows the
   placeholder "Untitled" (greyed, like the single field's placeholder) in the After cell; Save is enabled
   whenever at least one row changes. The summary stays "N will change · M unchanged" (decision 4), where N =
   `changed` and M = rows flagged `unchanged`; every row is counted by exactly one of the two (so Find "" +
   Replace with "  " on five named rows reads "5 will change · 0 unchanged" over five "Untitled" cells).
   Same rule as the single editor, which accepts an empty name too (app.js:1056-1063: no field uses
   `required` any more).
8. **No long-name flag.** No onX limit is known, and UI-26 forbids a warning with no consequence. The
   owner may run a 300-char name probe on their onX account — **owner-run only, never an agent** (§7).
9. Notes over 512 bytes: warn per row with the existing caution sentence (UI-34), never truncate; Save
   stays enabled.
10. Rows that leave the search filter after Save: leave the filter alone; `renderFolders()` prunes them from
    SEL as for a single rename (app.js:677-679); the status "Changed N items." is the receipt. Pinned by e2e.
11. An open note editor on a selected row with changes: UI-22's "Save your note?" first (§3.5).
12. "Use note as name" **shipped** in `2f92e4b` (app.js:2390-2392, `oneLine`, blank note → row left alone,
    pinned by `test_use_note_as_name_leaves_a_blank_note_row_alone`). Not routed through the core: `oneLine`
    collapses `\s*\n\s*` to one space, the core keeps internal runs; changing it is out of scope. Owner
    2026-10-25: it stays as shipped, so a blank note still leaves its row alone (names being optional does
    not turn a blank note into a blank name).
13. No selection-size cap; the preview renders changed rows first, then the rest, and caps the list at 200
    rows (§6.5).
14. Search/sort while open: unreachable (modal); uids are captured at open. After Save a sorted folder
    reorders (UI-35); focus returns to the More button, or to the search field when the selection emptied.
15. XML-forbidden characters are dropped in the core **and** in the writer, with exactly the same set (§3.1).
    Compatible with ENG-06 (printable punctuation untouched); ENG-09 records it.
16. The dialog opens on the first toggle (Add before) with an empty field: every row "No change", summary
    "0 will change · N unchanged", Save disabled. Switching to Find and replace with both fields empty shows
    the same.

**Decided by the owner later on 2026-10-25 (revision 4).** These amend decisions 1 and 4 and default 7:

17. **Names are optional, everywhere.** An empty name is legal: the single name field accepts it, the app
    shows "Untitled" as that field's placeholder and wherever a name is displayed, and the export writes an
    empty `<name>`. In bulk rename an empty result is therefore **not** blocked: there is no `empty` flag, no
    "can't be empty" sentence and no `blocked` count; Save is enabled whenever at least one row changes. A
    row whose result is empty shows "Untitled" in the After column, greyed like a placeholder (a display rule
    of the dialog; the core returns `""`, and "Untitled" is never stored or exported). Whitespace-only
    results are still trimmed to `""`, so they show "Untitled" too. Find "" + Replace with "" stays a no-op
    while both are empty (raw === before ⇒ `unchanged`). "Use note as name" keeps leaving blank-note rows
    alone (shipped behaviour, default 12).
18. **A missing note shows as blank**, never "No note": the Before and After cells of Change note… are empty
    for a row with no note, and nothing is put in their place (no "Untitled", no "(none)").
19. **Strings**: the status after Save is **"Changed N items."** (with a period); title text has no period
    ("Rename N items"); every new string uses straight apostrophes (') and says "You will", never "You'll".
20. **Confirm dialogs: the safe choice first, the action last.** The one confirm this plan opens is the
    reused "Save your note?" (§3.5), in its existing order Keep editing · Discard · Save; the dialogs'
    own footers read Cancel · Save. Any other confirm B adds follows the same order.
21. **"Web Map" is not used anywhere** (code, copy, docs, tests, new comments). Where the destination has to
    be named, say "onX on a computer".
22. **Owner-run onX probe**: how onX shows an imported markup with an empty `<name>` joins the
    "untestable locally" list (§7). Until the owner runs it, what a bulk blank-out does to an onX import is
    unverified, and UI-39 says so.

---

## 3. Architecture

### 3.1 One pure core, in JavaScript: `web/rename.js`

**Superseded in part by the progress tracker's section 7.4** (owner, round 3, 2026-10-25): Find
matches whole words only; each replaced match is highlighted; the core has two more flags,
`name-over-limit` and `name-empty`, and its context takes `nameLimit` as well as `noteLimit`
(DECISIONS UI-39 and UI-40). The text below is the plan as built in round 1.

**Why JS, not Python.** (a) Preview latency: every keystroke re-runs the transform over up to 1,500 rows;
a `py.runPython` hop plus JSON both ways is 5–20 ms on warm Pyodide and spikes under GC; JS does it in
< 2 ms. (b) The bridge is not called per edit today: `EDITS` go to `apply_edits` once, at export
(app.js:2106-2108 → bridge.py:631); keeping Save UI-side preserves that. (c) One implementation means no
Python-vs-JS drift (`re` vs `RegExp`, `str.casefold`, surrogates). (d) Testability: no Node toolchain in
the repo (Playwright is the Python package), so the JS is tested from Python through a browser page:
`page.add_script_tag(path="web/rename.js")` on `about:blank` in the bypass-CSP context (no Pyodide boot,
no dev server, no CSP), then `page.evaluate` runs `CairnRename.transform` on generated vectors. In the
app it loads from its own `<script src="rename.js">` tag before `app.js` (same-origin; CSP `script-src
'self'`, web/vercel.json:27; no inline JS).

**Contract** (frozen in Phase 1 before any parallel work starts):

```js
// web/rename.js — no DOM, no globals read, no side effects. Exposed as window.CairnRename.
/**
 * @param {Array<{uid:string, name:string, desc:string, kind:"waypoints"|"tracks"|"shapes"}>} rows
 *        the selected items as captured at open (name/desc are the CURRENT values incl. EDITS)
 * @param {{ field:"name"|"desc",
 *           mode:"prefix"|"suffix"|"replace"|"set",      // "set" is notes-only (Replace the note)
 *           text:string,                                 // prefix/suffix/set text
 *           find:string, repl:string, matchCase:boolean  // replace mode
 *        }} spec
 * @param {{ noteLimit:number }} ctx                      // bridge.ONX_IMPORT_NOTE_LIMIT (512), app.js NOTE_LIMIT
 * @returns {{ rows: Array<{uid, before:string, after:string, flags:string[]}>,
 *             changed:number }}                          // no `blocked`: no result ever blocks Save (decision 17)
 */
function transform(rows, spec, ctx) {...}
// Also exported: xmlSafe(s), cleanName(s), cleanNote(s), noteBytes(s), XML_INVALID (the RegExp).
// No name-collision input: duplicate names are allowed and never flagged (decision 3).
// A name's `before`/`after` may be "" (names are optional, decision 17). "Untitled" is a display placeholder
// added by the dialog; the core never returns it, and it is never stored or exported.
```

**The drop set — one literal, shared with the writer.** `cairn/core/writers.py:28`:
`_XML_INVALID = "[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]"` (C0 minus `\t\n\r`, U+FFFE/FFFF,
lone surrogates). JS: `XML_INVALID = /[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿\uD800-\uDFFF]/gu`
— with the `u` flag the surrogate range matches only *lone* surrogates (a paired emoji is one code point and
survives; `test_a_paired_emoji_survives_the_surrogate_strip` pins it). **Nothing else is dropped**: no
U+200B/U+FEFF, no C1 (`\x7F-\x9F`), no NBSP — all legal XML 1.0, all user data (ENG-06). Revision 1's ZWSP/BOM
removal and C1 collapse are gone; `test_zero_width_space_and_bom_are_kept_in_names` replaces the old test.

**Cleaning per field** (applied only to a value the operation changed; see the no-op rule):

- `cleanName(s)` = `xmlSafe(s)` → every run of whitespace that contains a `\r`, `\n` or `\t`
  (`/[ \t]*[\r\n\t][ \t\r\n]*/g`) becomes one space → `trim()`. Pure space runs are left alone ("Camp  A" is
  user data). Mirrors the folder rule's intent (bridge.py:148-158) without its C1 class.
- `cleanNote(s)` = `writtenNote(xmlSafe(s))` where `writtenNote` is app.js:934 (`\r\n?` → `\n`, outer
  whitespace trimmed). So a bulk-saved note is stored exactly as the file will carry it.

**No-op rule** (settles "empty spec", "whitespace-only prefix", "find == replace", "empty Find", "set to
blank"). This block is the single source of the empty-Find semantics (decision 1); every other section
points here:

```
raw   = mode === "prefix"  ? text + before            // names: no joiner; notes: text + "\n" + before
      : mode === "suffix"  ? before + text            // notes: before + "\n" + text
      : mode === "set"     ? text                     // notes only (Replace the note)
      : /* replace */ find === "" ? (repl === "" ? before : repl)   // empty Find = replace the WHOLE value;
                                                                    // both empty = no-op
                                  : replaceAll(before, find, repl, matchCase)
if raw === before        → flags ["unchanged"]            (nothing cleaned: a dirty loaded value is never
                                                           silently stripped by an empty spec; the writer is the net;
                                                           covers both-empty Find/Replace with, and a row already
                                                           equal to Replace with)
after = clean(raw)                       // cleanName or cleanNote
same  = field === "name" ? after === before : after === writtenNote(before)
                                         // notes: the single editor stores drafts untrimmed (app.js:1119);
                                         // compare against the written form so nothing is saved when the
                                         // file would not differ, and the stored whitespace stays
if same                  → flags ["unchanged"]
else                     → changed++; flags += "chars-removed" iff xmlSafe(raw) !== raw
                                         // after === "" is an ordinary result for a name (names are optional,
                                         // decision 17): reached by Find "" + Replace with "  " (whitespace-only)
                                         // on every named row, and by a find that consumes the whole name. It is
                                         // a changed row with no flag of its own; the dialog shows "Untitled".
```

For notes, Find "" + Replace with text is the same operation as Replace the note with that text (both set
`raw = text`); Replace the note with "" clears a note (`after === ""`, changed; nothing is blocked on
empty) and is `unchanged` on a row whose note is already blank.

Per-row `flags` (string enum; the dialog maps each to one approved sentence and a CSS class):

| flag | when | effect |
|---|---|---|
| `unchanged` | by the rule above | row greyed, not counted in `changed` |
| `note-over-limit` | notes: `noteBytes(after) > ctx.noteLimit` (UTF-8 bytes of `after`, which is already in written form) | warn; Save enabled |
| `chars-removed` | `xmlSafe(raw) !== raw` (exactly the writer's drop set; line-break collapse and trim are silent, the preview shows them) | warn |

The enum is exactly {`unchanged`, `note-over-limit`, `chars-removed`}: there is **no `empty` flag**
(decision 17; revision 3 had one that blocked Save) and **no duplicate flag** (decision 3), so no result can
block Save. The dialog never reads other items' names, `nameKey`
(app.js:1575) stays a folder-only helper, and the bridge has no item-name rule either (`_name_taken`,
bridge.py:754-758, is folders only). Twins created by a rename are ordinary changed rows.

Rules inside `transform` (each is a unit/property test in §5):

- **Find**: `find === ""` → **replace the whole value** with `repl` (decision 1): `raw = repl`, except that
  `find === "" && repl === ""` is a no-op (`raw = before`). Never "insert everywhere". Non-empty find:
  plain text, escape regex specials, `new RegExp(escaped, matchCase ? "gu" : "giu")` on the **original**
  string; never lowercase-then-offset. Replacement is a **function replacer** so `$&`, `$1`, `$$`, `` $` ``,
  `$'` stay literal. Matches are left-to-right non-overlapping (`replaceAll` semantics). `matchCase` is
  ignored when `find === ""`.
- **Names**: `cleanName` as above. No length cut, no collapsing of pure space runs. An empty result is
  legal: a result that is whitespace-only (or control-only) trims to `""` and is returned as `""`.
- **Notes**: `cleanNote` as above; line breaks kept (UI-13); **no truncation** (flag instead). Prefix/suffix
  join with `"\n"`; a whitespace-only prefix/suffix is a no-op after `writtenNote`.
- **Idempotence** holds for `cleanName` / `cleanNote` (property); prefix/suffix are not idempotent and no
  test claims so.
- `ctx` carries only `noteLimit`; `transform` reads nothing about items outside `rows`.
- `transform` never throws; a bad `spec.mode` returns every row `unchanged`.

**Invariant scope.** Names: `after` == `it.name` after Save == GPX `<name>` text == the onX reader's title
(the writer's `xml_text` drop is a no-op on core output; `apply_edits` copies `name` verbatim,
bridge.py:665-667; `sanitize_name_for_onx` is still called at writers.py:261/731/1093/1326/1584 but has been
an identity since ENG-06, writers.py:154). For `after === ""` the GPX `<name>` is empty (decision 17), and
the reader's title for an empty `<name>` is whatever the reader makes of it: the round-trip test records it,
nothing assumes it. Notes: `after` == `it.desc` after Save
== GPX `<desc>` text. This holds on **every** map, CalTopo-origin included: `strip_html` runs at **load**
(cairn/core/parser.py:40 `clean_notes(plain=False)`; caltopo_gpx.py:140), and `export_zip` sets
`PLAIN_NOTES_KEY = True` on every feature (bridge.py:959-960, "Already cleaned at load (or typed by the
user): plain text now") so the writers call `clean_notes(plain=True)` = CRLF/CR → LF + strip = `writtenNote`.
Revision 1's reviews feared `strip_html` at export; it does not run there. A bulk note of
`"see <b>north</b> of <Lake>"` on Bitterroots exports as that text, escaped, `<b>` kept
(`test_a_bulk_note_with_html_looking_text_on_a_caltopo_map_exports_verbatim`). The one place HTML-looking
text *is* changed is a re-import: `onx_gpx` → `ParsedFeature` → `clean_notes(plain=False)` → `strip_html`
removes known tag names and keeps `<Lake>` (utils.py:94-118), so §6.6's reader-side equality is "after
`strip_html`". The single note editor stores its draft untrimmed (app.js:1119); only bulk-saved notes are
stored in written form; the before column may therefore show outer whitespace the file won't.

**Shared helpers**: `writtenNote` / `utf8Len` / `noteOverflow` live in app.js:929-942. `rename.js` exports
`noteBytes(s)` with the same measure; B makes `noteOverflow` call it so the caution mark, the dialog flag
and instructions.txt (bridge.py:1194-1204 counts `len(desc.encode("utf-8"))` on the written `<desc>`) agree
by construction.

### 3.2 Preview and Save both call it

- **Spec is synchronous, render is debounced.** Every `input` event (not `change`: Playwright `fill()` and
  real typing both fire `input`) writes `BULK.text.spec` from the fields immediately; `drawTextBulk()`
  (new, sibling of `drawBulk` app.js:1494) runs ~60 ms later, runs `transform(BULK.rows, BULK.text.spec,
  BULK.ctx)`, rebuilds the Now → After rows (changed rows first, then "No change"; cell text per §3.3), the
  summary line ("N will change · M unchanged", decision 4), sets Save `disabled = !(changed > 0)` (no result
  ever blocks it, decision 17), and increments
  `#mark-dialog[data-preview-seq]` (tests wait on it, §6.3). `input` events with `isComposing` re-render
  only; `compositionend` re-renders.
- `applyTextBulk()` (sibling of `applyBulk` app.js:1521) **re-reads the fields**, runs `transform` once more
  on the rows as they are at Save time (re-read `it.name`/`it.desc` by uid), and **refuses when
  `changed === 0`** (so Enter right after the text was deleted back to nothing, inside the debounce
  window, saves nothing; and Save clicked inside the window uses the final text). Then `closeBulk()`, then
  for each row not `unchanged`: `edit(it, { [field]: after }, { render: false })` (an empty `after` is
  stored as `""`, never as "Untitled"); `refreshAfterEdit()`; `setStatus(\`Changed ${plural(n, "item")}.\`,
  "ready")` (a period, decision 19); then the focus fallback (§3.4).
- Going through `edit()` (app.js:1140-1155) means `EDITS[uid]`, `unexportedChanges()` (2304-2318), the
  leave prompt and beforeunload (UI-37), Start over's count (UI-21), `stageValid` and the caution marks all
  follow for free. `doExport` (2099-2110) sends EDITS to `apply_edits` (bridge.py:631), which copies
  `name`/`desc` verbatim (665-667); the writer's `xml_text` (writers.py:36, used at 434/694/956/1072/1565)
  is the net under it.
- **Rename back is still an edit.** `edit()` does `Object.assign(it, patch)`; the original is gone, and
  `unexportedChanges` compares `EDITS[uid]` against `SAVED.edits` (set at load 373 and after export 2112),
  which has no entry for an unedited row. Prefix "⟦" then find "⟦" → "" therefore counts N unexported
  changes while the export is byte-identical to the baseline (same strings, verbatim copy). Chosen over a
  drop-no-op-edits rule, which needs stored originals (a model change touching `edit`, `savedState` and
  UI-32's counting). Pinned by `test_rename_then_rename_back_still_counts_as_edits_and_exports_identically`.

### 3.3 Dialog state: a mode of BULK, not a fourth state

`openRename()` / `openChangeNote()` set
`BULK = { text: { field, mode, spec }, rows, ctx, uids: new Set(...), ret: $("#more-btn") }` and render
into the **same** `#mark-modal` / `#mark-dialog` (index.html:158) with the same head (`.modal-head.plain`,
`.now-after`, `.na-rows`), `.pop-sec` rows, `.tog` toggles and `.pop-foot` (Cancel / Save). `#mark-dialog`
gains `data-bulk="rename"|"note"` and `aria-labelledby` pointing at its `<h2>`; `#bulk-summary` is
`aria-live="polite"`. `closeBulk` (app.js:1545-1553) is reused unchanged; `drawBulk`'s callers are all
inside `openBulk`'s wiring (1463-1490), so they are unreachable in text mode and the zero-edits claim
holds. First focus: `#bulk-text` (or `#bulk-find`), not `.reset-chip` (1491). Because `BULK` is truthy,
every existing guard applies with zero edits:

| guard | where | behaviour with a text-mode BULK |
|---|---|---|
| Ctrl/Cmd+A | app.js:2449-2450 (`!BULK`) | ignored (test: selection unchanged) |
| row drag start | app.js:1958 (`BULK` in the bail list) | no drag |
| Tab trap | app.js:2426 (`else if (BULK) trapTab`) | stays in the card |
| Esc chain | app.js:2429-2447: DRAG → CONFIRM → Help → MOVE → **BULK** → POP → menu | Esc closes the dialog, discards the preview, restores focus to `ret` |
| backdrop click | app.js:2401 (`#mark-modal` click → closeBulk) | same |
| `resetAll` | app.js:2279 (`closeBulk()`) | dialog gone with the map |
| load path | app.js:369 (`closeBulk()`) | same |
| `doExport` | app.js:2106 (`closeBulk()`) — **after** the everything-excluded early return at 2100-2103 | unreachable by click; a programmatic `doExport()` with items included closes it first and applies nothing; with everything excluded it returns before `closeBulk` and the dialog stays (acceptable: the modal still covers the page) |
| `onPopState` | app.js:286 | Back while open: the leave-prompt / `resetAll` path closes it — **e2e test**; the dialog must never survive a stage change |
| fuzz `SNAP_JS` | fuzz_ui.py:82 (`out.bulk = !!BULK` at 101) | invariant "no modal open after Save/Esc" already readable |

New guards to add (B): `openBulk`, `openPop`, `openMoveTo`, `openNote`, `startRename` early-return when
`BULK` is set (a queued `#bulk-icon` click can arrive through `deferRender`, app.js:155-170).
`requestExport` / `requestStartOver` already `flushDeferred()` and bail on `CONFIRM`; add `if (BULK)
return;`. `openRename` / `openChangeNote` call `flushDeferred()` first so a pending folder-merge offer runs
before the dialog, never a CONFIRM over a BULK.

**Selection capture at open.** `rows` and `uids` are snapshotted from `selectedItems()` (app.js:1177) at
open, as `openBulk` does (1429-1434). `applyTextBulk` iterates `BULK.rows`, not `SEL`.

**Mixed kinds.** Names and notes exist on every kind; no per-kind branching. Excluded rows that are ticked
are renamed too ("fix it, then Include").

**Before and After cells.** Each `.na-row` holds a `.na-before` and a `.na-after` cell. Names: an empty
name, in either cell, renders the existing placeholder "Untitled" (the `it.name || "Untitled"` pattern of
app.js:1508) in a greyed `.is-placeholder` span; a real name typed as "Untitled" is plain text and not greyed.
Notes: an empty or missing note renders a **blank** cell, never "No note", "Untitled" or "(none)"
(decision 18). Text always goes in as text (`esc`), never HTML.

**Modes and fields.** The mode row is `.tog` toggles in the decided order: Rename… = Add before · Add
after · Find and replace; Change note… = Add before · Add after · Find and replace · Replace the note. The
first toggle is selected at open (default 16). Add before / Add after / Replace the note show one field
labelled "Text" (`#bulk-text`); Find and replace shows "Find" (`#bulk-find`) and "Replace with"
(`#bulk-repl`) side by side with the "Match case" toggle (`#bulk-match-case`) below — the same layout in
both dialogs (decision 2). Rename…: `<input>`s; Enter saves when Save is enabled, does nothing when
disabled. Change note…: `<textarea>`s for every field including Find and Replace with (a prefix or a
replacement may hold a line break); Enter inserts a newline, **Ctrl/Cmd+Enter saves** (the note editor's
rule, app.js:1126-1133). Every Enter handler bails on `e.isComposing || e.keyCode === 229` (app.js has no
IME handling today; this is new). Paste is plain text (the browser's default for `<input>`/`<textarea>`; a
multi-line paste into an `<input>` loses its line breaks in the browser, before the core sees it, so no
flag).

### 3.4 Search, sort, collapsed folders, focus

- Only `selectableItems()` (app.js:1175: shown minus collapsed, UI-23) can be selected, so rows in
  collapsed folders or hidden by a filter are never in `rows`.
- After Save, `renderFolders()` (677-679) prunes SEL to what still matches the search (names **and** notes:
  the filter reads `desc` too, app.js:452); the dialog's `rows` are already consumed. A sorted folder
  reorders (UI-35). The "Showing N" chip and the rail counts update through the normal render.
- **Focus after Save**: `closeBulk` focuses `ret` (`#more-btn`); if the prune left SEL empty, `updateSel`
  disables `#more-btn` and `#bulk-icon` (1193-1197) and the browser drops focus to `body`. `applyTextBulk`
  therefore ends with: if `document.activeElement` is `body` or disabled, focus `#filter` (index.html:98).
  Cancel/Esc never prunes, so focus lands on `#more-btn`.

### 3.5 Open NOTE_EDIT conflict

At open: if `NOTE_EDIT` and `NOTE_EDIT.uid ∈ uids`: `noteIsChanged()` (app.js:2269) → `openConfirm`
(2215) titled "Save your note?", with the buttons in the order of the export-time confirm of the same title
(safe choice first, action last, decision 20): **Keep editing** (the cancel: focus the textarea) ·
**Discard** (`closeNote(it, false)` then open) · **Save** (`closeNote(it, true)` then open; the primary,
initially focused button). It is the only confirm this feature opens. Not changed → `closeNote(it, false)`
and open. `NOTE_EDIT` on an unselected row stays open under the modal (`keepNoteDraft` 1674 is not involved).

### 3.6 Menu and markup

`index.html:119-122` (inside `.menu-wrap` 116-124) gains two `role="menuitem"` buttons after `#bulk-move`:
`#bulk-rename` "Rename…" and `#bulk-note` "Change note…" (`aria-haspopup="dialog"`); `menuAct` wiring at
app.js:2385-2393. `<script src="rename.js">` goes before `app.js` (index.html:259-260). Help's "More has …"
sentence (index.html:196) and FAQ.md:114 lose "aren't built yet" and gain the approved lines (decision 4):
Help "Rename… changes many names at once; Change note… does the same for notes."; FAQ Q "Can I rename many
items at once?" A "Yes. Tick them, then More → Rename…. Find and replace changes part of each name; Add
before and Add after add text to every name." Every new string also goes into `docs/design/LABELS.md` in
the same commit.

### 3.7 Prerequisites: shipped vs remaining

| # | item | status | where / what remains |
|---|---|---|---|
| (a) | XML-forbidden characters dropped by the writers for every name, note and the waypoint file's folder name | **DONE** `edc284b` | `writers.py:28-37` (`_XML_INVALID`, `xml_safe`, `xml_text`); GPX `escape = xml_text` at 434/694/956/1072/1565, folder name at 916; KML via `xml_safe`. Writer-level test `tests/test_xml_invalid_chars.py`. **Remains (C):** a bridge-level test — `apply_edits` with name `"\x01Camp\x00"` and a note `"a\x02b"` → `export_zip` → every GPX parses, `_written_items` doesn't raise, name `"Camp"`, note `"ab"`. |
| (b) | instructions.txt marks long notes and lost holes on the very item, not on every item with that name | **DONE** `a192c34` (differently from rev 1's uid design) | `_written_items` returns `[name, nbytes]` per item in file order (bridge.py:1194-1204); `build_instructions` (1249-1267) reads `nbytes` per item and holes by `hole_positions` (writers.py:1522-1589 `_area_hole_positions`, bridge.py:1073). No uid keying, no `sort=False` dance. Tests `tests/test_gpx_areas.py:279,289`. **Remains (optional, C):** a split-parts test that hole positions and note bytes stay aligned per part (monkeypatch `max_bytes` as `tests/test_export_instructions.py:138-141` does). |
| (c) | "Use note as name" leaves a blank-note row alone | **DONE** `2f92e4b` | app.js:2390-2392; `test_use_note_as_name_leaves_a_blank_note_row_alone` (test_web_app.py:5135). Nothing remains; default 12 closed. |
| (d) | legacy `write_gpx_waypoints` folder name unescaped | **DONE** `edc284b` | writers.py:916 `xml_text(folder_name)`. |
| (e) | the single name editor doesn't trim (app.js:1056-1066); the core trims | **open, out of scope** | note in DECISIONS UI-39 only. |
| (f) | names are optional (decision 17): the single name field accepts an empty name; "Untitled" is its placeholder and the display text for a nameless item; the export writes an empty `<name>`; instructions.txt prints "Untitled" (`_plain`); the status after a bulk mark reads "Changed N items."; "onX on a computer" replaces the retired name | **decided 2026-10-25; in the working tree, uncommitted when this revision was written** | app.js:979/1056/1508/1544, bridge.py:1217 (`_plain`), LABELS.md:315-359. A dependency, not one of this plan's tracks: B and C start from the commit that lands it (checked at the Phase 1 branch point). **Remains (C):** a bridge-level test — `apply_edits` with name `""` → `export_zip` → every GPX parses, the item's `<name>` is empty, `_written_items` doesn't raise, instructions.txt prints "Untitled" for it. |
| — | DOM twin for "loaded" under the enforced CSP | **already exists** | `body[data-stage]` is set at app.js:250; tests already use `to_have_attribute("data-stage", "edit")`. |

Net: **no `cairn/` change, no wheel rebuild**. ENG-09 records what shipped (§7 DoD 5).

---

## 4. Phases

Tracks after Phase 1: **A** core, **B** dialog UI, **C** every test file, **D** fuzzer + perf harness.
File ownership (no overlaps): A: `web/rename.js` only. B: `web/app.js`, `web/index.html`, `web/styles.css`,
`docs/FAQ.md`, `web/faq.html` (via `scripts/build_faq_page.py`), `docs/design/DECISIONS.md`,
`docs/design/LABELS.md` (new strings, same commit as the code that adds them). C:
`tests/naughty_strings.py`, `tests/bulk_rename_vectors.py`, `tests/web/test_rename_core.py`,
`tests/web/test_bulk_text.py`, `tests/test_bulk_round_trip.py`, `tests/test_bulk_prereqs.py`. D:
`scripts/qa/fuzz_ui.py`, `tests/web/test_bulk_perf.py`. Nobody edits `tests/web/test_web_app.py` after the
Phase 1 move. Order: Phase 1 → **A + C + D-harness** (3 concurrent) → **B** (Phase 0 is done, so B waits only
for Phase 1 and the concurrency cap) → D's real fuzz and perf runs after B. Merge: Phase 1 → A → C → B → D.
Rules for every agent: never `git add -A`
(four scratch files sit untracked at the repo root: `basecamp.gpx`, `gpx10.gpx`, `plain11.gpx`, `run.py`);
commit early and often in your own worktree; model set explicitly; no nested spawning; ≤ 3 agents concurrent.
Every new string (UI, docs, tests): straight apostrophes, "You will" not "You'll", the status "Changed N
items." with its period, titles without one, never "Web Map" (say "onX on a computer"), never "No note"
(a missing note is blank), and no confirm that puts its action before its safe choice (decisions 18–21).

### Phase 0 — Owner decisions and mockups (orchestrator) — **DONE 2026-10-25**

- Done: the owner decided modes, empty-Find semantics, no duplicate warning and every string (§2) on the
  Phase 0 canvas, https://claude.ai/artifact/5F9oPZLuGRuqU2TaNY8rCN (the two dialogs over real Bitterroots
  rows in the field-guide theme using the existing `.mark-dialog` look: prefix, find "Trail"→"Tr.", the
  Campsite normalisation, a 600-byte note, an empty result, a removed control character). Revision 4:
  the canvas's blocked empty-result state is superseded by decision 17 (the After cell shows a greyed
  "Untitled" and Save stays enabled); the mockup is not redrawn, the localhost build is the check.
- Remaining: only the owner's review of the localhost build, which is Phase 4. The `DECISIONS.md` UI-39
  entry is written by B (it owns that file) from §2, status "decided 2026-10-25".
- A, C, D start on §3.1 alone; B is no longer gated on this phase.

### Phase 1 — Freeze the contract (orchestrator, ≤ 1 hour, before fan-out)

- Deliverable 1: **`tests/web/conftest.py` + `tests/web/helpers.py` + an empty `tests/web/__init__.py`**.
  Today everything lives inside the 5,145-line `tests/web/test_web_app.py`: fixtures `_require_server`
  (63-79, autouse, session), `browser` (81), `context` (89), `fresh_page` (105), `loaded` (122), `csp_page`
  (2148), constants `BASE_URL` (36), `FIXTURE`, `ROW`; helpers at the top (`export_zip_bytes` 130,
  `_select_all_shown` 163, `_clear_selection` 175, `_set_type` 180, `_menu_action` 188, `_export_zip` 196)
  and mid-file (`_open_changed_waypoint_note` 1895, `_gpx_blob` 1905, `_load_files` 2164, `_onx_wpt` 2303,
  `_gpx_payload` 2309, `_set` 3784, `_tick` 4246, `_is_marked` 4988, …). A new file in `tests/web/` would
  see no fixtures and **fail** without the dev server instead of skipping. Layout: `conftest.py` = fixtures
  and constants only; `helpers.py` = plain functions; `test_web_app.py` imports them (`from tests.web.helpers
  import …`). `tests/__init__.py` already exists, so the new package is `tests.web`, not a top-level `web`;
  the bridge tests load the bridge by `sys.path.insert(…/"web")` + `import bridge`
  (test_export_instructions.py:18, test_web_bridge_input_dispatch.py:40), never `import web`, so nothing is
  shadowed. Zero behaviour change: `uv run pytest tests/web --co -q` count and the pass count identical
  before and after, and the full suite's count unchanged (the bridge/engine tests still import).
- Deliverable 2: `web/rename.js` skeleton with the exact signature, flag enum, `XML_INVALID`, `cleanName`,
  `cleanNote`, `noteBytes`; the DOM selector contract: `#bulk-rename`, `#bulk-note`,
  `#mark-dialog[data-bulk="rename"|"note"][data-preview-seq]`, `.mode-tog[data-mode]`, `#bulk-text`,
  `#bulk-find`, `#bulk-repl`, `#bulk-match-case`, `.na-row[data-uid][data-flags="…"]` (space-separated),
  `.na-before` / `.na-after` (the cells; a cell showing the "Untitled" placeholder also carries
  `.is-placeholder`, and notes never do, §3.3), `.na-flag` (text), `#bulk-summary[aria-live=polite]`,
  `#bulk-apply` (reused id), `.bulk-cancel`; the status string ("Changed N items."); the
  `tests/naughty_strings.py` module name.
- Precondition: the optional-names change (§3.7(f): empty names accepted and shown as "Untitled", empty
  `<name>` exported, "Changed N items.") is committed on the branch the tracks start from; Phase 1 checks it.
- Port: the dev server and the tests default to **8765** (serve.py:36, test_web_app.py:36). Only when 8765
  is busy: `PORT=8779 uv run python web/serve.py` **and** `BASE_URL=http://127.0.0.1:8779` on every pytest
  and fuzz run, together.
- Exit: committed on the feature branch; tracks branch from it.

### Phase 2 — Track A: the core (agent A)

- Files: `web/rename.js` full implementation. No `cairn/` change, no wheel rebuild.
- Gating: C's `tests/web/test_rename_core.py` (§6.1) green; `tests/test_xml_invalid_chars.py` untouched.
- Exit: every §5 U case passes; `transform` never throws on any `NAUGHTY` string.

### Phase 2 — Track C: red-team tests written against the contract (agent C, parallel with A)

- Files: all of C's list. Property bodies run as soon as A merges.
- Until B lands the e2e tests **skip** on `page.locator("#bulk-rename").count() == 0` (a module-level
  helper), not `xfail(strict=True)` (an xfail waits out a Playwright timeout per test). Remove the skip in
  the commit that flips them green.
- Every string is approved (§2 decisions 4, 17, 19), so C asserts on the sentences from the start ("No
  change", "Untitled", "N will change · M unchanged", "Rename N items", "Change the note on N items",
  "Changed N items.") as well as on structure: `data-flags`, `.na-row` counts, `.is-placeholder`, Save's
  `disabled`, `EDITS`, GPX text. No test expects a "can't be empty" sentence or a disabled Save for an empty
  name.
- Exit: every §5 case has a test id and a body.

### Phase 2 — Track D: fuzzer and perf harness (agent D, parallel)

- Files: `scripts/qa/fuzz_ui.py` (`a_bulk_rename`, `a_bulk_note`, `a_bulk_rename_hostile`, weights,
  invariants §6.4), `tests/web/test_bulk_perf.py` (§6.5), a 1,500-row map via
  `tests/hardening_maps.make_map(10, per=(150, 150))` (signature `make_map(n_folders, *, seed, names, empty,
  kinds, per, …)`, hardening_maps.py:54).
- Exit: harness runs green against the current app with the new actions returning
  `("bulk_rename", "not built")` until B lands; then 3 seeds × 300 actions × 4 maps with no Violation.

### Phase 3 — Track B: dialog UI (agent B, after Phase 1)

- Files: `web/app.js` (`openRename`, `openChangeNote`, `drawTextBulk`, `applyTextBulk`, guards §3.3,
  NOTE_EDIT conflict §3.5, focus fallback §3.4, `noteOverflow` → `CairnRename.noteBytes`, IME bail),
  `web/index.html` (menu items, script tag, aria), `web/styles.css` (reuse tokens; new classes only
  `.na-row`, `.na-flag`, `.mode-row`, plus the placeholder grey for `.is-placeholder`, reusing the field
  placeholder token), Help line, FAQ line + rebuilt `faq.html`, DECISIONS UI-39/ENG-09 (and the older
  "(no name)" wording at DECISIONS.md:918, if the optional-names commit has not already corrected it),
  **`docs/design/LABELS.md`**: every new label and action from §2 decision 4 added in the same commit as
  the code that introduces it, so the LABELS.md drift test passes at every commit ("Untitled" and "Changed
  N items." are already there).
- Gating: C's e2e cases flip from skip to pass; `test_page_boots_under_enforced_csp` still passes; the
  LABELS.md drift test passes; screenshots and a11y snapshots of every state (§7).
- Exit: all §5 e2e green; D's fuzz green; perf budget met.

### Phase 4 — Integration, review, owner pass (orchestrator)

- Merge A → C → B → D onto the feature branch; `uv sync --all-extras`; full suite with the dev server up;
  expected count = baseline **1387** (AGENTS.md:40) + new tests; record the new number in AGENTS.md.
- `scripts/make_walkthrough_shots.py` rerun if any visible page changed; cross-page visual review at
  1440×900.
- Owner tests on localhost. PR only when the owner says publish.

---

## 5. Red-team test catalogue

Layers: **U** = unit/property on the core (Python → `page.evaluate` on an `about:blank` page with
`rename.js` injected), **W** = writer/bridge pytest, **E** = Playwright e2e (bypass-CSP context unless
marked **E-csp**), **F** = fuzz_ui, **P** = perf. Ids are the test function names. Inputs use Python escapes.
Flags are a set: assert `⊇`, never `==`, unless the test is about exclusivity.

### 5.1 Length and limits

| id | input | expected | layer |
|---|---|---|---|
| `test_note_prefix_pushes_a_511_byte_note_over_the_limit_and_flags_it` | note of 511 ASCII bytes, Add before "x" | after is "x\n" + note, 513 B, `note-over-limit`, Save enabled; the row's caution mark appears after Save with UI-34's sentence | U, E |
| `test_multibyte_note_bytes_are_counted_not_characters` | 200 × "日" (600 B) as Replace the note | flagged; sentence "About 30 characters will be cut" (same as `noteOverflow`) | U |
| `test_a_four_byte_emoji_straddling_512_is_reported_not_split` | 510 ASCII + "🔥" | 514 B, flagged, "About 1 character will be cut"; after export the GPX `<desc>` holds the whole emoji | U, W |
| `test_note_exactly_512_bytes_is_not_flagged` | 512 ASCII | no flag | U |
| `test_crlf_and_lone_cr_in_a_note_become_lf_before_measure` | "a\r\nb\rc" × 100 as the note | after holds only `\n`; bytes match instructions.txt's count | U, W |
| `test_note_bytes_in_the_dialog_match_instructions_txt` | 505 ASCII + "<b></b>" (512 B exactly, tags kept) | no flag; instructions.txt has no cut line; 513 B does both | U, W |
| `test_a_3000_character_name_is_stored_whole_and_exported_whole` | prefix of 3,000 "x" | no flag (no long-name flag), name stored whole, GPX `<name>` holds all 3,000 | U, W |
| `test_a_find_string_longer_than_10k_characters_does_not_hang` | find of 10,000 "a" on 1,500 rows | within budget, 0 matches | U, P |
| `test_a_prefix_on_1500_rows_stays_under_the_preview_budget` | big1500 map, select all, type 8 chars | each render ≤ budget (§6.5) | P |
| `test_set_note_on_1500_rows_with_512_bytes_splits_the_gpx` | 1,500 rows, Replace the note with 512 B | parts under `DEFAULT_MAX_GPX_BYTES` (writers.py:99); nothing lost; `_written_items` per part sums to 1,500 | W |

### 5.2 Non-English and Unicode

| id | input | expected | layer |
|---|---|---|---|
| `test_cjk_names_survive_prefix_and_find_replace` | "日本語の山" find "山" repl "岳" | "日本語の岳" | U, E |
| `test_rtl_names_keep_their_characters_and_order` | "مجلد عربي", suffix " 2" | code points appended at the logical end; GPX round trip identical | U, W |
| `test_bidi_override_is_kept_and_never_breaks_xml` | "a‮b" | unchanged under an empty spec; prefixed it keeps U+202E; export parses | U, W |
| `test_nfd_find_does_not_match_nfc_text_and_does_not_crash` | stored "Zürich" (NFC), find "ü" | 0 matches, `unchanged` | U |
| `test_combining_marks_stay_attached_after_a_prefix` | "é" prefix "A" | "Aé" | U |
| `test_emoji_zwj_families_and_flags_are_not_broken` | "👨‍👩‍👧", "🇺🇸", "👍🏽" prefix "x" | ZWJ kept, flags kept, skin tone kept | U |
| `test_a_paired_emoji_survives_the_surrogate_strip` | "a🔥b" prefix "x" | "xa🔥b", no `chars-removed`; writer keeps it too | U, W |
| `test_turkish_dotted_i_does_not_cross_match_case_insensitively` | "İstanbul" find "istanbul" case off | 0 matches; find "İ" matches | U |
| `test_eszett_does_not_match_ss` | "Straße" find "ss" | 0 matches | U |
| `test_final_sigma_matches_only_itself` | "Οδυσσεύς" find "σ" case off | both medial σ, not ς | U |
| `test_zero_width_space_and_bom_are_kept_in_names` | "Camp​﻿" prefix "x" | "xCamp​﻿", no `chars-removed`; export parses | U, W |
| `test_c1_controls_are_kept_in_names_and_notes` | "a\x85b" prefix "x" | kept (legal XML); export parses; reader returns it | U, W |
| `test_nbsp_is_kept_in_names` | "Camp A" prefix "x" | "xCamp A", no `chars-removed` | U |
| `test_nbsp_find_does_not_match_a_space` | find " " repl "_" on "a b" | 0 matches | U |
| `test_fullwidth_and_halfwidth_are_different_characters` | "Ａ" vs "A" | no cross-match | U |
| `test_a_name_of_only_combining_marks_is_kept_not_shown_as_untitled` | "x́" find "x" repl "" | after "́" (a non-space character is never trimmed to blank), stored as is; the After cell shows the mark, no `.is-placeholder` | U, E |
| `test_emoji_only_names_show_as_themselves_and_sort_stably` | rename to "🔥" | After shows "🔥" (no placeholder); sorted folder renders without error; order stable | U, E |
| `test_a_name_typed_as_untitled_or_no_name_is_an_ordinary_name` | rename to "Untitled", and to "(no name)" | plain changed rows (not greyed, no `.is-placeholder`), stored and exported verbatim; instructions.txt prints them as typed, and prints "Untitled" for a truly blank name (`_plain`, bridge.py:1217), so those two read alike there — documented | U, E, W |
| `test_unicode_names_render_as_text_in_the_preview_not_html` | "<b>&amp;</b>" | `.na-row` text equals the string (cf. test_web_app.py:2326) | E |

### 5.3 XML-hostile

| id | input | expected | layer |
|---|---|---|---|
| `test_control_characters_are_stripped_from_names_and_flagged` | "\x00Camp\x01\x1f" prefix "x" | "xCamp", `chars-removed` | U |
| `test_a_dirty_stored_name_is_left_alone_by_an_empty_spec` | stored "\x01Camp", prefix "" | `unchanged`; the writer drops it at export | U, W |
| `test_tab_and_newline_in_a_name_become_one_space` | "Camp\tA \n B" prefix "x" | "xCamp A B"; no `chars-removed` (collapse is silent) | U |
| `test_pure_space_runs_in_a_name_are_kept` | "Camp  A" prefix "x" | "xCamp  A" | U |
| `test_tab_and_newline_in_a_note_are_kept` | "line1\n\tline2" suffix "!" | "line1\n\tline2\n!" | U |
| `test_lone_surrogates_are_removed` | "a\ud800b" built via `String.fromCharCode` inside `evaluate`, prefix "x" | returns `{isWellFormed:true, length:3, flagged:true}` ("xab") — booleans and lengths, never the string (CDP may replace lone surrogates in transit) | U |
| `test_fffe_and_ffff_are_removed` | "a￾b￿" prefix "x" | "xab", `chars-removed` | U |
| `test_cdata_terminator_and_entities_survive_as_text` | "]]> & < > \" '" prefix "x" | after "x]]> & < > \" '", no `chars-removed`; GPX `<name>` holds `x]]&gt; &amp; &lt; …`; reader returns the string | U, W |
| `test_the_writer_strips_what_the_core_missed` | `apply_edits` with "\x02Camp" and note "a\x02b" directly | export parses; name "Camp", note "ab"; `_written_items` fine | W |
| `test_every_naughty_string_exports_and_reparses` | each `NAUGHTY` entry as name and as note | no exception, every GPX parses, `_written_items` succeeds | W |
| `test_a_naughty_note_round_trips_through_the_onx_reader` | same, export → `onx_gpx` reader | note equal after `strip_html`; "no crash", not "unchanged" | W |
| `test_a_bulk_note_with_html_looking_text_on_a_caltopo_map_exports_verbatim` | Bitterroots, Replace the note "see <b>north</b> of <Lake>" | GPX `<desc>` is that text escaped, `<b>` kept (bridge.py:960 → `clean_notes(plain=True)`); preview == stored == exported | E, W |
| `test_a_bulk_note_on_an_onx_map_exports_verbatim` | same on an onX GPX fixture | same | W |

### 5.4 Replacement-pattern and find traps

| id | input | expected | layer |
|---|---|---|---|
| `test_dollar_patterns_in_the_replacement_are_literal` | find "a" repl "$&$1$$$`$'" | the literal string inserted | U |
| `test_backslashes_in_find_and_replace_are_literal` | find "\\" repl "\\\\" | each backslash doubled | U |
| `test_regex_specials_in_find_are_literal` | find ".*+?^$()[]{}|" on a name containing it | one match | U |
| `test_empty_find_and_empty_replace_is_a_noop` | find "" repl "" | every row `unchanged`, summary "0 will change · N unchanged", Save disabled — on a hostile map too (no-op rule: no cleaning without a change); the same the instant Find and replace is chosen with nothing typed | U, E |
| `test_empty_find_replaces_the_whole_name` | the Campsite rows, find "" repl "Campsite" | every After is "Campsite"; a row already named "Campsite" is `unchanged`; Match case on or off gives the same result (decision 1; export side in §5.5) | U, E |
| `test_empty_find_with_a_whitespace_only_replacement_saves_blank_names` | find "" repl "  " on 5 named rows | every After is `""`, shown as a greyed "Untitled"; no flag; summary "5 will change · 0 unchanged"; Save enabled; after Save the 5 names are `""` and the status is "Changed 5 items." | U, E |
| `test_empty_find_replaces_the_whole_note_like_replace_the_note` | notes, find "" repl "see north" | every note "see north"; identical result to Replace the note "see north"; find "" repl "" is `unchanged` | U, E |
| `test_find_with_no_matches_marks_every_row_unchanged` | find "zzz" | changed 0, summary "0 will change", Save disabled | U, E |
| `test_find_equal_to_replace_counts_zero` | find "a" repl "a" | `unchanged`, Save disabled | U, E |
| `test_whitespace_only_prefix_is_a_noop_after_trim` | prefix "  " on names | `unchanged`, Save disabled | U |
| `test_whitespace_only_suffix_on_notes_is_a_noop_after_writtennote` | suffix "\n " on notes, including a stored note with a trailing space ("abc ") | `unchanged`; the stored value is not touched | U |
| `test_set_mode_with_a_blank_note_on_a_row_with_no_note_is_unchanged` | Replace the note "  \n " on rows with `desc` "" or undefined | `unchanged`; on a row with a note: after "" , changed (the note is cleared; its After cell is blank) | U, E |
| `test_overlapping_matches_replace_left_to_right` | "aaa" find "aa" repl "b" | "ba" | U |
| `test_replace_with_empty_can_empty_a_name_and_saves_it_blank` | "Camp" find "Camp" repl "" | `after === ""`, flags == [] (changed); After cell greyed "Untitled"; Save enabled; stored `it.name === ""` (never "Untitled"); the export's GPX has an empty `<name>`, every GPX parses, `_written_items` doesn't raise | U, E, W |
| `test_match_case_toggle_changes_the_count_live` | "Camp camp" find "camp" | off: 2 matches; on: 1; `data-preview-seq` advances | U, E |
| `test_find_whitespace_only_is_a_real_find` | find " " repl "_" | spaces replaced | U |
| `test_find_longer_than_the_name_matches_nothing` | — | `unchanged` | U |
| `test_replace_result_is_trimmed_but_inner_spaces_are_kept_for_names` | find "Camp" repl "  " on "Camp A" → "A"; on "X Camp A" → "X    A" | trim only, never collapse | U |
| `test_whitespace_only_results_are_trimmed_to_blank_and_shown_untitled` | find "Camp" repl " \t\n " on "Camp"; also Add before "  " on a row whose name is already `""` | the first: `after === ""` exactly (never whitespace), changed, After cell greyed "Untitled" (`.is-placeholder`), Save enabled, stored name `""`; the second: `unchanged` (raw ≠ before, but cleaned equals it), and that row's Before cell is a greyed "Untitled" | U, E |
| `test_missing_notes_show_as_blank_never_no_note` | Change note… in every mode on rows whose `desc` is undefined, `""` and a real note | the Before and After cells of a row with no note are empty text with no `.is-placeholder`; "No note", "(none)" and "Untitled" appear in no note cell | E |

### 5.5 Incompatible and conflicting bulk operations

| id | input | expected | layer |
|---|---|---|---|
| `test_campsite_normalisation_makes_three_identical_names_and_exports_three_items` | "Campsite - Oct 9th (rainy)", "Campsite - Oct 10th", "Campsite - Oct 11th-12th (stay two days)" selected, Find and replace with Find "" and Replace with "Campsite" | all three change to "Campsite"; `data-flags` carries no warning on any row (flags == [] — exclusivity is the point); summary "3 will change · 0 unchanged"; Save enabled; after Save three items named "Campsite"; the export's GPX holds three `<name>Campsite</name>` and `_written_items` lists three (decision 3: twins allowed) | U, E, W |
| `test_renaming_existing_twins_together_keeps_them_twins` | twins map: select "Camp", "camp", "CAMP", " Camp ", Add before "Base " | all four change, no flag on any; Save enabled; export lists four `<name>`s | U, E, W |
| `test_a_rename_that_collides_with_an_unselected_name_is_an_ordinary_change` | select "Camp A", find " A" repl "" when "Camp" exists elsewhere | changed, flags == []; both items export | U, W |
| `test_find_in_turkish_locale_matches_the_same_rows` | `iu` find "i" under `tr-TR` | same rows as `en-US` | E |
| `test_a_rename_producing_a_blank_name_for_one_row_does_not_block_save` | rows "Camp", "Camp B", "Camp C"; find "Camp" repl "" | rows become "", "B", "C"; the first After cell is a greyed "Untitled", the others plain; no row carries a flag; summary "3 will change · 0 unchanged"; Save enabled; after Save the status is "Changed 3 items." and the first item's name is `""` | E |
| `test_mixed_waypoints_lines_and_areas_rename_alike` | select one of each | all three change; export GPX `<wpt>`, `<trk>`, `<rte>` names updated | E, W |
| `test_excluded_rows_in_the_selection_are_renamed_too` | tick an excluded row | renamed, still excluded, not exported | E |
| `test_exclude_then_rename_then_include_exports_the_new_name` | — | GPX has the new name | E, W |
| `test_rows_in_a_collapsed_folder_are_not_in_the_dialog` | tick, collapse, open | count excludes them (UI-23) | E |
| `test_rows_hidden_by_a_filter_are_not_in_the_dialog` | select all, then search | only matches in the dialog | E |
| `test_one_row_and_1500_rows_both_work` | — | title "Rename 1 item" / "Rename 1,500 items" | E |
| `test_a_rename_that_drops_rows_from_the_search_prunes_the_selection_and_says_changed_n` | search "Trail", select all, find "Trail" repl "Tr" | rows vanish, SEL pruned, status "Changed N items.", filter unchanged, `unexportedChanges()` == N | E |
| `test_a_note_change_that_removes_the_search_term_prunes_the_row` | search on a note word, Change note… removes it | pruned (the filter reads `desc`, app.js:452); receipt shown | E |
| `test_a_rename_that_empties_the_selection_moves_focus_to_the_search_field` | the case above, every row pruned | `#more-btn` disabled; `document.activeElement.id == "filter"` | E |
| `test_a_rename_reorders_a_sorted_folder_and_keeps_focus_on_more` | sort A→Z, prefix "zz " | rows move to the bottom, focus on `#more-btn` | E |
| `test_prefix_keeps_natural_sort_order` | "Camp 2", "Camp 10" prefix "x " | order unchanged | E |
| `test_prefix_that_ends_in_a_digit_changes_natural_order` | prefix "1" on "0 A", "9 B" | "10 A" before "19 B" (natural); pinned as expected behaviour | E |
| `test_rename_then_change_note_then_export_agree` | both dialogs then export | GPX names and descs equal the rows | E, W |
| `test_two_bulk_renames_compose` | prefix "⟦" then find "⟦" repl "⟧" | every name starts "⟧" (an impossible prefix: "A " would hit "Camp A Lake") | E |
| `test_rename_after_an_export_counts_as_new_unexported_changes` | export, rename, Back | leave prompt (UI-37), `stageValid("done")` false | E |
| `test_rename_then_rename_back_still_counts_as_edits_and_exports_identically` | prefix "⟦" then find "⟦" repl "" | `unexportedChanges()` == N (EDITS holds the original strings, §3.2); export zip sha == the Bitterroots baseline (`tests/test_web_bridge_input_dispatch.py:88`) | E, W |
| `test_change_note_set_mode_on_rows_with_empty_notes_adds_them` | Replace the note on rows with no note | desc set; caution if > 512 | E |
| `test_rename_then_shift_click_range_after_save_uses_a_fresh_anchor` | rename prunes ANCHOR's row, then shift-click | no crash; `ANCHOR` reset (app.js:1181, 1693) | E |

### 5.6 Click and keyboard behaviour

| id | input | expected | layer |
|---|---|---|---|
| `test_double_clicking_save_applies_once` | `dblclick` on `#bulk-apply` | `applyTextBulk` closes first (1524 pattern), the second click lands on the page; `EDITS[uid].name` has one prefix; one `edit` per row | E |
| `test_escape_mid_preview_discards_everything` | type, Esc | no EDITS, modal hidden, focus on `#more-btn` | E |
| `test_enter_in_a_name_field_saves_when_enabled_and_does_nothing_when_disabled` | Enter in `#bulk-text` | saves / nothing | E |
| `test_enter_right_after_deleting_the_text_does_not_save` | Add before: type "x" (the stale preview shows one change and Save enabled), delete it back to "", Enter within 60 ms | nothing saved (`changed === 0` at Save time); `applyTextBulk` recomputed from the fields, not from the stale preview | E |
| `test_save_clicked_inside_the_debounce_window_uses_the_final_text` | `fill("ab")`, click Save at once | EDITS reflect "ab" | E |
| `test_enter_in_a_note_field_inserts_a_newline_and_ctrl_enter_saves` | Change note… `#bulk-text`, and `#bulk-find` / `#bulk-repl` in Find and replace (all textareas, decision 2) | Enter → "\n" in the textarea; Ctrl/Cmd+Enter saves | E |
| `test_ctrl_a_while_open_does_not_change_the_selection` | Ctrl+A with focus in a field and on the card | SEL unchanged (app.js:2449) | E |
| `test_a_drag_cannot_start_while_the_dialog_is_open` | pointerdown on a row behind the modal | `DRAG` null (1958); modal covers it anyway | E |
| `test_tab_stays_inside_the_dialog` | Tab from the last control | first control (app.js:178) | E |
| `test_browser_back_while_open_closes_it_and_runs_the_leave_prompt` | `page.go_back()` with the dialog open | dialog hidden; UI-37 prompt; Stay → edit screen, no dialog, no EDITS | E |
| `test_export_and_start_over_requests_bail_while_open` | `requestExport()` / `requestStartOver()` via evaluate | return early (new guard); dialog still open | E |
| `test_a_programmatic_export_closes_the_dialog_and_applies_nothing` | `doExport()` via evaluate with items included | `closeBulk` ran; export has no rename | E |
| `test_opening_rename_with_a_pending_folder_merge_offer_flushes_it_first` | type a taken folder name, then More → Rename… | the merge CONFIRM runs first; never CONFIRM over BULK | E |
| `test_a_queued_bulk_icon_click_does_not_open_over_the_text_dialog` | pointerdown `#bulk-icon`, open Rename… by keyboard, pointerup | one modal (`deferRender` 155-170; `openBulk` guard) | E |
| `test_opening_rename_with_a_changed_open_note_on_a_selected_row_asks_first` | §3.5 | "Save your note?" with the buttons in DOM order Keep editing · Discard · Save (safe choice first, action last); Save → note kept and dialog opens; Discard → draft dropped and dialog opens; Keep editing → textarea focused, no dialog | E |
| `test_opening_rename_with_an_unchanged_open_note_just_closes_it` | — | no prompt | E |
| `test_an_open_note_on_an_unselected_row_stays_open` | — | still open after Cancel | E |
| `test_focus_returns_to_the_more_button_after_save_and_after_cancel` | selection survives | `document.activeElement.id == "more-btn"` | E |
| `test_rapid_typing_leaves_the_preview_equal_to_the_final_text` | `press_sequentially` 40 chars at 5 ms, then wait for `data-preview-seq` to stop advancing | every `.na-row` after-text == transform of the final spec; also at 100 ms delay (> debounce) each intermediate render matches its text | E |
| `test_backdrop_click_cancels` | click `#mark-modal` outside the card | hidden, nothing applied | E |
| `test_the_menu_items_are_disabled_with_nothing_selected` | — | `#more-btn` disabled (existing), items unreachable | E |
| `test_switching_mode_keeps_typed_text_per_field` | type prefix, switch to replace, back | prefix text still there (state in `BULK.text.spec`) | E |
| `test_the_dialog_works_under_the_enforced_csp` | fresh non-bypass context: open, type, Save | DOM-only: `body[data-engine=ready]`, `.na-row` count, `data-preview-seq`, status text | E-csp |

### 5.7 Validation and review

| id | input | expected | layer |
|---|---|---|---|
| `test_preview_equals_saved_equals_exported_for_names` | the test prefixes each selected name with its own uid ("⟦i12⟧ ") so names are unique, then random find/replace | per uid: `.na-row[data-uid]` after-text (a `.is-placeholder` cell counts as `""`) == `it.name` after Save == the GPX `<name>` whose text starts with that uid == reader title; a second pass renames some rows to blank, where the blank rows are checked as `""` == `""` == empty `<name>` (no uid prefix to match on, so by position within the folder) | E, W |
| `test_preview_equals_saved_equals_exported_for_notes` | same, notes; line breaks kept | == GPX `<desc>` (CRLF→LF, trimmed) | E, W |
| `test_changed_count_in_status_equals_rows_that_differ` | mix of changed/unchanged | status text is exactly "Changed N items." (a period; "Changed 1 item." for one) and N == rows whose after != before; read within `STATUS_LINGER_MS` (8 s, app.js:35); strip "," from the number (`plural` writes "1,500", app.js:2171) | E |
| `test_unexported_changes_counts_each_renamed_row_once` | rename 7, change note on 3 of them | `unexportedChanges()` == 7 | E |
| `test_start_over_names_the_bulk_changes_count` | — | "This discards 7 unexported changes." | E |
| `test_instructions_txt_lists_the_new_names_and_flags_the_right_long_note` | twins + one long note | one cut line under the right item (by position, §3.7(b)) | W |
| `test_the_caution_marks_match_the_dialogs_note_flags` | rows flagged `note-over-limit` | the same rows carry `.caution` after Save; the export warning names them (UI-34) | E |
| `test_a_bulk_rename_does_not_touch_icons_colors_or_exclusions` | — | `EDITS[uid]` has only `name` | E |
| `test_round_trip_writer_reader_keeps_every_renamed_name` | §6.6 | — | W |
| `test_every_dialog_state_has_the_expected_accessibility_tree` | each §7 screenshot state | `page.accessibility.snapshot()` (or role queries): dialog named by its `<h2>`, `#bulk-summary` live region, every field labelled, Save's disabled state announced | E |

### 5.8 Input methods and accessibility

| id | input | expected | layer |
|---|---|---|---|
| `test_enter_during_ime_composition_does_not_save` | `compositionstart`, Enter with `isComposing`/`keyCode 229` | no Save; preview re-runs on `compositionend` | E |
| `test_input_events_mid_composition_preview_the_partial_text_without_saving` | three `insertCompositionText` inputs | preview tracks the partial text; EDITS untouched | E |
| `test_ctrl_z_in_the_field_reruns_the_preview` | type, Ctrl+Z (`historyUndo` input event) | preview matches the field | E |
| `test_pasting_multiline_text_into_the_name_prefix_field` | paste "A\r\nB" into `#bulk-text` (input) | the browser drops the line break; preview shows "AB…"; no `chars-removed` | E |
| `test_pasting_multiline_text_into_the_note_prefix_field_keeps_it` | same into the note textarea | line break kept in the preview | E |
| `test_pasting_rich_text_keeps_only_plain_text` | `text/html` clipboard | plain text only | E |
| `test_browser_zoom_200_keeps_save_reachable` | `page.emulate_media` / CSS zoom 2 at 1440×900 | Save visible and clickable without horizontal scroll | E |
| `test_summary_is_announced_to_assistive_tech` | — | `#bulk-summary[aria-live=polite]`; `#mark-dialog[aria-labelledby]` names the title (today index.html:158 has only `role=dialog aria-modal`) | E |
| `test_keyboard_only_flow` | Tab/Enter/arrows only from `#more-btn` | menu → dialog → typed → saved; focus back on `#more-btn` | E |
| `test_every_control_has_a_visible_focus_ring` | Tab through the dialog | each focused control's outline is non-transparent (computed style) | E |

---

## 6. Test infrastructure

### 6.1 Property tests (seeded generators → browser)

- **No Hypothesis.** It would touch `uv.lock`, the `fresh-clone` job and five Pythons, and batching
  `evaluate` calls defeats shrinking. Instead `tests/web/test_rename_core.py` uses `random.Random(seed)`
  generators (seed fixed per property, 300 vectors each) over an alphabet of letters, digits, punctuation,
  symbols, spaces, combining marks, format chars (`​ ‍ ‮ ﻿`), controls, `İıßΣς$&\\`,
  plus `NAUGHTY` samples and surrogate-bearing strings built in JS. Any failing vector is **pinned** in
  `tests/bulk_rename_vectors.py` as a named regression. Hypothesis stays an owner opt-in.
- One `page.evaluate` per batch of 100 vectors; the JS side returns **per-input `{ok, error, result}`** so
  one throw never loses the batch; results carry booleans and lengths for surrogate cases, never the raw
  string.
- Page: module-scoped, `about:blank` in the bypass context, `page.add_script_tag(path=REPO/"web/rename.js")`.
  Lives under `tests/web/`, so it inherits the autouse `_require_server` skip although it needs no server —
  accepted (CI installs chromium only in `web-e2e`, ci.yml:108).
- Properties: (1) `after` never contains an `XML_INVALID` match; (2) name `after` has no `\r\n\t`, no
  leading/trailing space; (3) `cleanName`/`cleanNote` idempotent; (4) **empty spec ⇒ every row
  `unchanged`** (prefix/suffix "" and find "" + repl ""); (5) **find "" ⇒ whole-value replace**: with
  `repl !== ""`, every row's `after` is `clean(repl)` or the row is `unchanged` (already equal), and
  `matchCase` makes no difference; (6) `$`-patterns literal: with `find !== ""`, `repl !== ""`, `find ∉
  repl` and `repl ∉ find`, `after.count(repl) >= before.count(find)` (find "" is excluded by the
  generator; it is property 5); (7) `changed == |rows not flagged unchanged|` (for names: `after !== before`;
  an empty `after` counts like any other); (8)
  `noteBytes(after) > 512 ⇔ note-over-limit`; (9) rows changed with Match case on ⊆ rows changed with it
  off, **for inputs without `İ`/`ı`/`K`/`ſ`** (the `iu` folding exceptions, excluded by the generator and
  documented); (10) `transform` never throws; (11) a name's `after` is `""` only when `cleanName(raw)` is
  `""` (raw empty, whitespace-only or control-only); such a row is `unchanged` iff `before === ""` and
  otherwise counts in `changed` with no flag of its own (names are optional, decision 17); the core never
  returns the text "Untitled" unless the input held it; (12) the flag set of any row ⊆ {`unchanged`, `note-over-limit`, `chars-removed`} — nothing
  else exists (no `empty`, decision 17; no duplicate flag, decision 3).

### 6.2 Naughty strings

- `tests/naughty_strings.py` (a Python module like `tests/hardening_maps.py`, **not** a file under
  `tests/fixtures/` — anything there must be added to `test_input_check.EXPECTED` and is swept by
  `_fixture_files()`, tests/test_input_check.py:162-172). ~80 `(label, text)` entries so ids read
  `[rtl_arabic]`, `[zwj_family]`.
- `hardening_maps.make_map(..., names=NAUGHTY_TEXTS)` generates maps into `tmp_path` at test time.

### 6.3 Playwright helpers (`tests/web/helpers.py`)

- `_open_bulk(page, which)`: `_menu_action(page, "#bulk-rename" | "#bulk-note")`, waits for
  `#mark-dialog[data-bulk]`.
- `_set_mode(page, mode)`; `_type_spec(page, **fields)` reads `data-preview-seq`, fills, then waits for the
  attribute to exceed the value read (never `wait_for_timeout`); `_type_slowly(page, sel, text, delay)` uses
  `press_sequentially`; `_preview_rows(page)` → `[(uid, before, after, flags)]` from the DOM only (CSP-safe;
  a `.is-placeholder` cell is returned as `""`, never as its "Untitled" text, so rows compare equal to
  `it.name`); `_save_bulk(page)` → status text read at once; `_status_count(text)` strips commas and the
  closing period; `_gpx_names(zip)` / `_gpx_descs(zip)` via `ET` over every GPX member (an empty `<name>`
  reads back as `""`, not `None`).
- `ROW`, `_select_all_shown`, `_clear_selection`, `_menu_action` as moved in Phase 1.

### 6.4 fuzz_ui.py additions (track D)

- Actions: `a_bulk_rename` (random mode, text from a pool incl. NAUGHTY, Save 70 % / Esc 20 % / backdrop
  10 %), `a_bulk_note` (same for notes incl. 600-byte and `\n`-bearing text), `a_bulk_rename_hostile`
  (blank-producing find, empty Find + text (whole-value replace, makes twins on purpose), empty Find +
  whitespace-only replacement (blank names on purpose), `$&`, control chars). Weights 3/3/1 in `WEIGHTS`
  (fuzz_ui.py:1246).
- `SNAP_JS` (82) additions: `out.bulkKind = BULK && BULK.text ? BULK.text.field : null`, `out.saveDisabled`,
  `out.naRows`, `out.previewSeq`, `out.edits = EDITS`, `out.names = {uid: name}`.
- Invariants in `check()` (208): every item name is a string and an empty one is legal (decision 17; any
  existing invariant that treats an empty name as a Violation is retired by the optional-names change,
  §3.7(f)); no name matches `XML_INVALID`; `#mark-modal` hidden ⇔ `BULK` null; `saveDisabled` ⇔ every
  `.na-row` carries `unchanged` (no row, whatever its result, blocks Save); the status after a Save matches
  `^Changed [\d,]+ items?\.$` with N ≤ selection size at open; a row the preview showed as a
  `.is-placeholder` is stored as `""`, not as "Untitled"; after each export in the run, every GPX
  `<name>` text (an empty one counting as `""`) is in the multiset of item names (the `EDITS[uid].name ===
  item.name` check of revision 1 was true by construction and is dropped). Duplicate item names and blank
  names are never a Violation (decisions 3, 17); the `twins` map and the hostile action produce them on
  purpose.
- Run: `BASE_URL=http://127.0.0.1:8765 uv run python scripts/qa/fuzz_ui.py --maps
  bitterroots,hostile,twins,big1500 --seeds 1,2,3 --n 300`.

### 6.5 Performance budget (tests/web/test_bulk_perf.py)

- Map: `make_map(10, per=(150, 150))` → 1,500 rows. Select all, open Rename…, `press_sequentially` 8 chars.
- Measure inside `evaluate` with `performance.now()` around the render (expose
  `window.__cairnPerf.lastPreviewMs` and `lastTransformMs` from `drawTextBulk`). Budget: **transform ≤ 10
  ms**, **render ≤ 50 ms per keystroke**, **Save ≤ 500 ms** including `refreshAfterEdit`. **Gating:** the
  assertion multiplies the budget by 3 when `CI` is set in the environment; the raw numbers are printed
  either way.
- To meet it: render changed rows first, cap `.na-rows` at 200 rows with "and N more" (`.na-rows` is
  already a capped scroll box, styles.css:330-331), build one `innerHTML` string, debounce the render at
  ~60 ms (spec updates synchronously, §3.2).

- **Measured 2026-10-25** (owner accepted; `archive/perf/bench_bulk.py`, local only, headless Chromium
  on the owner's Mac, generated maps in folders of 100). The cost driver is the keyed re-render of every
  *changed* row (~80 µs per row); an unchanged render is cheap. Linear, no cliff, nothing broke up to
  20,000 items:

  | items | select all | bulk edit of every row (edit() + refresh) | preview, all rows | preview, 200 rows | transform | export |
  |---|---|---|---|---|---|---|
  | 1,500 | 119 ms | 129 ms | 18 ms | 4 ms | <1 ms | 80 ms |
  | 3,000 (onX's account and import cap) | 237 ms | 255 ms | 36 ms | 6 ms | <1 ms | 150 ms |
  | 10,000 | 759 ms | 906 ms | 116 ms | 15 ms | 1 ms | 479 ms |
  | 20,000 | 1.6 s | 2.1 s | 268 ms | 30 ms | 2 ms | 923 ms |

- **Decision (owner): no cap on the selection.** onX's own 3,000 limit is lower than anything that hurts,
  and Cairn already warns above it. No progress indicator.
- **Required: look rows up by uid through a `Map`** built once at Save (`new Map(allItems().map(i =>
  [i.uid, i]))`). `allItems().find()` per row is O(n²): 136 ms at 20,000 rows against 2.7 ms with the map.
- **Perf test at 3,000 rows** as well as 1,500: Save ≤ 500 ms, preview ≤ 50 ms per keystroke (×3 on CI).
- **After merge:** rerun `archive/perf/bench_bulk.py` against the Vercel deployment
  (`BASE_URL=https://cairn-five-blue.vercel.app/`) at 1,500 / 3,000 / 10,000 and record the numbers here.

### 6.6 Round trip writer → reader

- `tests/test_bulk_round_trip.py`: load a naughty map through `bridge.load_files`, `apply_edits` with the
  core's outputs (captured once from the browser and stored as Python data in
  `tests/bulk_rename_vectors.py` — never under `tests/fixtures/`), `export_zip`, parse each GPX with
  `cairn/io/onx_gpx.py`, assert every name equals the core's `after` exactly and every desc equals it
  after `strip_html` (the reader's own cleaning, §3.1), count equal, and `instructions.txt` names equal
  (a blank name prints as "Untitled" there, `_plain`). Blank names (the vectors include whitespace-only
  results trimmed to `""`): assert the raw `<name>` text is empty, then pin whatever title the reader
  returns for it today as the recorded behaviour; nothing assumes it equals `""`.
- Per-uid chains in W: the GPX carries no uid (ENG-07's sha pin forbids an extension), so W compares
  **multisets** per folder and kind; the per-uid chain is E's job with uid-prefixed names (§5.7).

---

## 7. Risks and mitigations; definition of done

| risk | mitigation |
|---|---|
| The core and the writer disagree on what is dropped | one literal (`_XML_INVALID` / `XML_INVALID`, §3.1); `test_the_writer_strips_what_the_core_missed`; the paired-emoji, ZWSP/BOM-kept and C1-kept tests on both layers |
| Preview lag on 1,500 rows | §6.5 budget test, synchronous spec + debounced render, capped list |
| A rename makes the search list "lose" rows and the owner reads it as data loss | default 10 + e2e pins (names and notes) + the status receipt + the focus fallback; one Help line |
| A bulk rename makes twins (the Campsite normalisation does so on purpose) | allowed, no warning (decision 3): onX imports duplicate names (ENG-06 probe); `test_campsite_normalisation_makes_three_identical_names_and_exports_three_items` pins that all of them export |
| A bulk rename can blank many names at once (names are optional, decision 17) and onX's handling of an empty `<name>` is unknown | the preview shows every blank as a greyed "Untitled" before Save and the status counts them; the export writes a valid empty `<name>` (bridge test, §3.7(f)); the owner-run probe below (decision 22) says how onX shows one; if onX drops or mangles such items, the owner decides then whether a warning earns its place (UI-26: no warning without a consequence) |
| Empty Find is read as "nothing to find" and surprises with a whole-value replace | the both-empty no-op (§3.1): nothing changes until Replace with has text, and the live preview shows every After before Save; `test_empty_find_and_empty_replace_is_a_noop` / `test_empty_find_replaces_the_whole_name` |
| Parallel agents collide in `app.js` | ownership in §4; only B touches `app.js`; A ships `CairnRename` in its own file |
| ENG-06 reviewers read the drop as "sanitising names again" | ENG-09: XML-forbidden characters only; printable punctuation, ZWSP, BOM, NBSP, C1 untouched; test names say so |
| The new `<script>` tag breaks the enforced CSP boot | `test_page_boots_under_enforced_csp` + `test_the_dialog_works_under_the_enforced_csp` |
| Flaky waits | `data-preview-seq` everywhere; no `wait_for_timeout`; status read within 8 s |
| **What cannot be tested locally: onX itself** | every expectation is against Cairn's model of onX (512-byte notes, no name limit known, twins allowed, NBSP/ZWJ/RTL rendering unknown, how onX shows an empty name unknown). Said here and in UI-39. The owner may run, **owner-run only, never an agent, never without approval**, this probe list on their account: a 300-char name; a 513-byte note ending in a 4-byte emoji; an RTL name; two identical names; an emoji-only name; a name with NBSP and ZWSP; **an imported markup with an empty `<name>` (does it import at all, and how does onX list and show it)**. Results go to DECISIONS. |
| Owner's onX account | no agent imports anything |

**Definition of done**

1. Owner decisions (§2, 2026-10-25, decisions 1–4 and 17–22) applied as written: mode order, empty Find =
   whole-value replace, no duplicate warning, names optional (an empty result is never blocked, shows
   "Untitled", saves as `""`), blank notes, "Changed N items.", confirm order, approved strings; nothing in
   the build contradicts them.
2. `uv run pytest` green on localhost with the dev server up on 8765; new baseline count recorded in
   AGENTS.md (from 1387); `--no-cov` narrow runs used only while iterating.
3. Every §5 test present, green, descriptive ids; 300 vectors per property with failures pinned; fuzz 3
   seeds × 300 actions × 4 maps clean; perf budget met locally.
4. Screenshots at 1440×900 **and** an accessibility snapshot of: Rename… each mode (nothing typed, typed,
   with a greyed "Untitled" After cell and Save enabled, with chars-removed; the Campsite whole-value
   replace), Change note… each mode (Find and replace with multi-line fields; blank Before/After cells for
   rows with no note; with the 512 flag), the "Save your note?" conflict, the status line after Save
   ("Changed N items."), the export screen's long-note warning after a bulk note change; side-by-side drift
   check.
5. `docs/design/DECISIONS.md` **UI-39** (bulk rename and note change: modes and their order, empty Find =
   whole-value replace, flags, no duplicate warning, names optional so an empty result is never blocked,
   warn-don't-block, no undo, rows leaving the filter, focus fallback, what onX behaviour is unverified
   including an import with an empty `<name>`; status decided 2026-10-25) and **ENG-09** (what
   shipped: the writers drop XML-forbidden characters, `edc284b`; instructions.txt marks by item position,
   `a192c34`; the core applies the same drop so preview = file; names otherwise untouched per ENG-06).
6. Help line and FAQ line as approved (§2 decision 4) and rebuilt (`scripts/build_faq_page.py --check`
   passes), with straight apostrophes and no retired wording (decisions 19, 21); every new label and action in `docs/design/LABELS.md`, added in the same commit as the code,
   with the LABELS.md drift test green; TODO.md's "On hold" entry (TODO.md:58-61) moved to done.
7. Owner review on localhost; PR opened only when the owner says publish; no onX import without approval.

---

## Changes in revision 4

- **Names are optional** (decisions 17, 22): the `empty` flag, `blocked`, the "can't be empty" row sentence
  and "Save disabled for an empty name" are gone; an empty result is a changed row shown as a greyed
  "Untitled", stored as `""`, exported as an empty `<name>`; Save is enabled whenever one row changes. The
  flag enum is {`unchanged`, `note-over-limit`, `chars-removed`}; properties (7), (11), (12), the fuzz
  invariants, §3.2, §3.7(f) and every affected test (§5.2, §5.4, §5.5, §5.6, §5.7) are rewritten, with a
  kept test that whitespace-only results trim to `""` and show "Untitled".
- **Missing notes are blank**, never "No note" (decision 18), with a test; "Use note as name" still leaves
  blank-note rows alone (default 12).
- **Strings** (decisions 19, 21): status "Changed N items." with a period, straight apostrophes, "You will",
  and no "Web Map" (say "onX on a computer"); applied to §2, §3.2, §4 and the tests that assert them.
- **Confirm order** (decision 20): the one confirm this feature opens, "Save your note?", reads Keep editing ·
  Discard · Save (§3.5), pinned by a test.
- **Owner-run onX probe** for an imported markup with an empty `<name>` added to the untestable-locally
  list, a risk row, and UI-39's unverified-behaviour note (§7).
- Contract and selectors: `transform` no longer returns `blocked`; `.na-before` / `.na-after` and
  `.is-placeholder` join the selector contract; `_preview_rows` reads a placeholder cell as `""`.

## Changes in revision 3

- Phase 0 is done (owner decisions 2026-10-25, mockups on the Phase 0 canvas); §2 is now "Decisions
  (owner, 2026-10-25)" plus renumbered stated defaults (5–16); B is gated on Phase 1 only; UI-39 is written
  by B from §2.
- Rename… modes fixed in order Add before · Add after · Find and replace; Change note… adds Replace the
  note as the fourth; the note Find and replace is the names layout with textareas.
- **Empty Find = replace the whole value** (the Campsite normalisation). The old "find === '' → no-op"
  rule is gone; the no-op block in §3.1 is the single source: both fields empty ⇒ `unchanged`; Find "" +
  text ⇒ every After is the text; Find "" + whitespace-only ⇒ every row `empty`, Save disabled (superseded
  in revision 4: blank names are allowed); Match case ignored while Find is empty.
- Duplicate names: no warning. The `duplicate` flag, `ctx.otherNames`, the `nameKey` export, the
  normalisation paragraph, the duplicate tests and property (12) are removed; property (12) now pins the
  flag enum; a positive Campsite test (three identical names, no flag, three items exported) and a risk
  line replace them.
- Approved strings listed in §2 decision 4 and applied to §3.2/§3.3/§3.6/§5; the summary is two-part
  ("N will change · M unchanged"), blocked rows carried a "can't be empty" sentence and rendered first
  (superseded in revision 4: nothing is blocked); the long-note row reuses the caution-mark sentence
  (app.js:950).
- `docs/design/LABELS.md` added to B's ownership, Phase 3 deliverables and DoD 6: new strings land in the
  same commit as the code, drift test green.
- §5.4 gains the four empty-Find tests; §5.5's empty-row test asserted the row sentence, not a summary count
  (both rewritten in revision 4, nothing is blocked);
  fuzz's hostile action adds empty Find + text / + whitespace; properties (4)–(6) restated.
- Cross-references renumbered (decision 11 → default 12, default 9 → default 10); "Phase 0 approval" and
  "four questions" wording removed everywhere.

## Changes in revision 2

- Header re-pinned to HEAD `2f92e4b`; baseline 1387; every file:line re-verified (Esc chain 2429, SNAP_JS
  82, FAQ.md:114, `xml_safe` in writers.py not utils.py, test file 5,145 lines, no `tests/web/__init__.py`).
- §3.7 is now a shipped/remaining table: (a) `edc284b`, (b) `a192c34` by position (uid design deleted
  everywhere), (c) `2f92e4b`, (d) done; Track A = `web/rename.js` only; no wheel rebuild.
- Core drop set = exactly `_XML_INVALID`; ZWSP/BOM/C1 kept; "same literal in both" is now true.
- No-op rule: an unchanged `raw` is `unchanged`, nothing cleaned; empty spec ⇒ all unchanged (property 4).
- Duplicate rule = `nameKey` (`trim().toLowerCase()`), created twins only; ß/İ differences documented;
  the bridge has no item-name rule to mirror.
- Long-name flag dropped (UI-26); 300-char probe stays owner-run.
- Rename-back: expectation changed (still N edits; export byte-identical) rather than a model change.
- Focus fallback to `#filter` when Save empties the selection.
- Notes: `strip_html` runs at load, export is verbatim (bridge.py:960); the headline invariant holds on
  CalTopo maps and is pinned; note fields are textareas with Ctrl/Cmd+Enter.
- Spec synchronous, render debounced, `data-preview-seq`; Save recomputes and refuses when blocked (since
  revision 4: when nothing changed).
- Hypothesis replaced by seeded generators with pinned vectors; per-input `{ok,error}`; properties (6) and
  (9) narrowed; surrogates reported as booleans; perf gated ×3 on CI.
- Core tests run on `about:blank` with `add_script_tag`; Phase 1 adds `conftest.py` + `helpers.py` +
  `__init__.py` (incl. `csp_page`); port is 8765 unless both `PORT` and `BASE_URL` move.
- §5 merged the QA attack cases; new §5.8 input methods and accessibility; a11y snapshot per state.
- §7 and the DoD say what is untestable locally (onX) and list the owner-run probes.
- Phase 0 asks four questions; the rest are defaults; phantom "RESEARCH §n" / "CODEMAP" citations removed.
