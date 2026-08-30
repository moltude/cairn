# Cairn Web Prototype Follow-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close out the work items left open from the 2026-08-30 web-prototype UX session — two need investigation/design before any code, two are small concrete fixes — and hand a clean, accurate baseline to whatever session does the actual Vercel deploy work.

**Architecture:** No architectural change. This plan touches `web/` (a static Pyodide-based prototype — plain HTML/CSS/JS, no build tooling, no framework) and two docs files (`web/README.md`, `AGENTS.md`). Tasks 1 and 2 are investigation-then-design work (they may end in a design decision and a follow-up plan of their own, not shipped code) — do not skip ahead to implementation on those without an approved design, per `superpowers:brainstorming`'s approval gate.

**Tech Stack:** Python 3.14, Pyodide (client-side Python-in-browser), Playwright for browser tests, `uv` for the Python side. No Node/npm anywhere in this repo.

**Spec:** `docs/VERCEL_DEPLOY_PLAN_2026-08-30.md` (handoff notes this plan implements) and this file's own Task sections (no separate design doc exists yet for Tasks 1–2; producing that design *is* Task 1/2's deliverable).

## Global Constraints

- Test command for everything under `web/`: `.venv/bin/python -m pytest tests/web/test_web_app.py -q --no-cov` — run from the repo root (`/Users/scott/_code/cairn`). Currently 35/35 passing; treat any drop from that as a regression to fix before committing.
- The web app must be running locally to manually verify anything in a browser: `uv run python web/serve.py` (serves `http://127.0.0.1:8765`). If the wheel is stale: `uv build --no-sources && cp dist/*.whl web/dist/`.
- Do not run `git push`. Commit locally only, one commit per task, and stop — pushing is the user's call.
- Stage files by exact name (`git add web/index.html web/app.js ...`), never `git add -A` or `git add .` — this repo currently has a large amount of unrelated untracked/modified work sitting in the tree from other sessions; do not touch or stage anything outside the files each task lists.
- Follow `AGENTS.md` at the repo root for anything not covered here (env setup, testing conventions, known traps) — read it before starting.
- No new comments in code beyond what's already there unless a step below shows one explicitly — this repo's convention is comments only for non-obvious "why," never "what."

## File Structure

Files this plan creates or touches, and why:

- `web/index.html`, `web/app.js`, `web/styles.css` — only touched by Task 2, and only *after* a design is approved (Task 2's first half is investigation/brainstorming, not editing).
- `web/README.md` — Task 3 corrects one stale line in the "Bugs this prototype exposed" table.
- `AGENTS.md` — Task 4 adds one bullet to the existing "Known traps" section.
- `tests/web/test_web_app.py` — only touched if Task 2's eventual design changes rendered markup/ids in a way that breaks an existing assertion; not expected to change for Tasks 1, 3, 4.
- No new files are created by Tasks 3–4. Task 1 and Task 2 may produce a short design writeup (path specified in each task) if their investigation reaches a concrete direction.

---

### Task 1: Locate and resolve the "Empty" / "In" header complaint

This is a loose end from *before* the 2026-08-30 session's own context began: the user's original round-1 feedback mentioned table headers labeled "Empty" and "In" being unclear. Nobody has since located what screen that refers to — it does not match any header in the current `web/index.html`/`app.js` (whose table headers are Name / Description / Type / onX icon / Color). It may be the TUI, a discarded earlier iteration, or something else. **Do not guess a fix — find the actual referent first.**

**Files:**
- Read: `web/index.html`, `web/app.js`, `cairn/tui/tables.py`
- Possible output: a short note appended to `docs/VERCEL_DEPLOY_PLAN_2026-08-30.md` under a new `## Task 1 resolution` heading, OR a design produced via `superpowers:brainstorming` if it turns out to need a UI change

**Interfaces:** None — this is investigation, not a code interface change.

- [ ] **Step 1: Search the web prototype for the literal strings**

Run:
```bash
grep -rni "empty\|\"in\"\|>in<" web/index.html web/app.js web/styles.css
```
Expected: no match that reads as a column header (there may be incidental matches like "included" or the word "in" inside a sentence — those don't count).

- [ ] **Step 2: Search the TUI for the same strings**

Run:
```bash
grep -n "Empty\|\"In\"" cairn/tui/tables.py
```
Look specifically for `table.add_columns(...)` calls (there are three in that file, one per markup type) — check whether any column is literally labeled `"Empty"` or `"In"`, or something that could be misread as such at a narrow terminal width (e.g. a truncated "Included" header).

- [ ] **Step 3: If no match anywhere, ask the user directly**

Do not invent an interpretation. Ask (in chat, not `AskUserQuestion` — this is a single factual question, not a decision with options): *"I couldn't find headers called 'Empty' or 'In' in either the web prototype or the TUI. Can you send a fresh screenshot of the screen you meant, or tell me which app (web or TUI) it was in?"* Wait for the reply before doing anything else in this task.

- [ ] **Step 4: Once located, classify the fix**

If it's a one-word label change (e.g. rename a truncated header to something clearer): that's a **bounded** task — use `superpowers:brainstorming`'s bounded path (ask 1-2 clarifying questions, present a one-paragraph design in chat, get a yes, implement directly — no separate plan needed for a single label change).

If it's part of a larger layout confusion (e.g. it turns out to be the same "top area is cluttered" complaint from round 1 that Task 2 already covers): fold it into Task 2 instead of doing it separately.

- [ ] **Step 5: Record the resolution**

Append a `## Task 1 resolution (YYYY-MM-DD)` section to `docs/VERCEL_DEPLOY_PLAN_2026-08-30.md` stating what it turned out to be and what was done (or a pointer to the commit that fixed it).

- [ ] **Step 6: Commit if code changed**

```bash
git add <exact files changed>
git commit -m "fix: clarify <whatever the header turned out to be>"
```
If only the doc note was added (no code fix needed, or fix deferred into Task 2), commit just the doc:
```bash
git add docs/VERCEL_DEPLOY_PLAN_2026-08-30.md
git commit -m "docs: record resolution of Empty/In header investigation"
```

---

### Task 2: Brainstorm and (if approved) implement the OnX icon column redesign

Explicitly deferred by the user during the 2026-08-30 session ("Separate pass"). Every waypoint row in `web/index.html`'s table shows a resolved OnX icon by default (e.g. "Location"), even for rows the engine only guessed at — this reads as "already reviewed" when it isn't. The user's own suggestion was to hide it behind a different kind of selector or toggle, but explicitly said *"I'm not sure what kind but flag this for further investigation."* **There is no approved design. Do not implement a redesign without running brainstorming first and getting an explicit yes**, per `superpowers:brainstorming`'s hard gate (this applies even though a human partner already flagged the problem — the *solution* is still unapproved).

**Files:**
- Read first: `web/app.js` (the `row()` function, `web/app.js:155-204`, builds the icon cell; `resolved_waypoint_color`-equivalent logic for icons lives in the `bridge.py`/`icons.js` glyph lookup) and `web/index.html:126-130` (the `<th>onX icon</th>` column header)
- Read: `web/styles.css` (`.chipbtn`, `.whymark`, `.unresolved` classes — the existing "needs attention" visual language this redesign will likely reuse or replace)
- Modify (only after design approval): `web/index.html`, `web/app.js`, `web/styles.css`
- Test: `tests/web/test_web_app.py` (specifically `test_bulk_icon_change_reduces_attention_by_exactly_n`, which depends on the `.icon-btn` and `.whymark` selectors — check it still passes after any markup change, update its selectors if the redesign renames them)

**Interfaces:**
- Consumes: `it.icon` (string, resolved icon name), `it.needs_attention` (bool), `it.why` (string, tooltip explanation) — all set by `web/bridge.py`'s `load_document`/`edit` bridge calls, already stable, do not need to change for a purely front-end redesign.
- Produces: whatever new DOM structure/classes the approved design calls for. Record the actual selector names in the design writeup (Step 2 below) so this doc doesn't grow stale placeholders.

- [ ] **Step 1: Reproduce the current behavior in a running browser**

```bash
uv run python web/serve.py &
```
Open `http://127.0.0.1:8765`, load `demo/bitterroots/bitterroots_geojson.json` (or `demo/caltopo_small.json` for a quick look), and screenshot the waypoint rows' onX-icon column. Confirm: every waypoint shows a filled-in icon chip regardless of whether `needs_attention` is true, with the only difference being the amber "?" `whymark` badge next to attention-needed rows. This is the concrete "problem" the design must address.

- [ ] **Step 2: Run brainstorming on the redesign**

Invoke `superpowers:brainstorming` with a prompt that includes: the screenshot/description from Step 1, the user's original wording ("different kind of selector or toggle... hide the column for now"), and the constraint that the fix must not regress `test_bulk_icon_change_reduces_attention_by_exactly_n` (i.e. bulk-setting an icon must still be reachable and must still flip `needs_attention` off). This is almost certainly a **bounded** task (existing screen, existing flow) — follow that path: a few clarifying questions, then a short in-chat design, then wait for an explicit yes before touching any file.

- [ ] **Step 3: Only after approval — write the failing/changed test first**

Whatever the design turns out to be, `tests/web/test_web_app.py`'s existing bulk-icon test must keep passing. If the design changes selectors, update the test's selectors in the same commit as the markup change — do not leave it broken. Example of the kind of assertion to preserve (adapt selector names to match the actual approved design):

```python
def test_bulk_icon_change_reduces_attention_by_exactly_n(loaded, n_select, new_icon):
    ...
    before_attention = loaded.evaluate("DATA.totals.attention")
    loaded.click("#bulk-icon")
    loaded.click(f"#modal-body .opt >> text={new_icon}")
    loaded.wait_for_timeout(100)
    after_attention = loaded.evaluate("DATA.totals.attention")
    assert after_attention == before_attention - n_select
```

- [ ] **Step 4: Implement the approved design**

Edit `web/index.html` / `web/app.js` / `web/styles.css` per the design from Step 2. Keep the existing pattern this session established: filters and edit tools stay in one persistent bar (`#control-bar`), disabled-not-hidden for anything selection-gated (see `web/app.js`'s `updateSel()` for the existing pattern to extend, not replace).

- [ ] **Step 5: Run the full web test suite**

```bash
.venv/bin/python -m pytest tests/web/test_web_app.py -q --no-cov
```
Expected: all tests pass (35, or more if this task added new ones).

- [ ] **Step 6: Manually verify in the browser**

Reload `http://127.0.0.1:8765`, repeat Step 1's load, and screenshot the new icon column behavior. Confirm it matches the approved design and that bulk icon editing (`Set icon…`) still works end to end.

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/app.js web/styles.css tests/web/test_web_app.py
git commit -m "redesign: <one line matching the approved design's own description>"
```

---

### Task 3: Correct the stale bug entry in `web/README.md`

`web/README.md`'s "Bugs this prototype exposed" table lists "Colour edits were silently discarded" as a bug in `web/bridge.py`. It is already fixed — `web/bridge.py:257-272` writes the picked color onto `feature.color` directly for user-edited items, with a comment explaining exactly why. The table is misleading as-is: a future reader will think this is still broken.

**Files:**
- Modify: `web/README.md` (the table row under `## Bugs this prototype exposed`, currently reading `| Colour edits were silently discarded | \`web/bridge.py\` | No writer reads \`cairn_onx_color_override\`; \`writers.py:429\` recomputes colour from \`feature.color\`. The picker looked like it worked and changed nothing. |`)

**Interfaces:** None — documentation only.

- [ ] **Step 1: Confirm the fix is still in place**

```bash
sed -n '250,275p' web/bridge.py
```
Expected: see the `if item["uid"] in _STATE.get("edited", ()):` block setting `feat.color = hex_`. If this block is gone or looks different, stop — the bug may have regressed, and this task becomes "re-fix the bug," not "correct the doc." In that case, re-read `web/README.md`'s original bug description for the expected behavior and restore it, using the same "only for edited items" guard (see the existing code comment for why: applying it unconditionally invented colors for untouched shapes).

- [ ] **Step 2: Edit the README table row**

In `web/README.md`, change:
```
| Colour edits were silently discarded | `web/bridge.py` | No writer reads `cairn_onx_color_override`; `writers.py:429` recomputes colour from `feature.color`. The picker looked like it worked and changed nothing. |
```
to:
```
| Colour edits were silently discarded *(fixed)* | `web/bridge.py` | No writer reads `cairn_onx_color_override`; `writers.py:429` recomputes colour from `feature.color`. Fixed by writing the picked color onto `feature.color` directly for edited items (`bridge.py:257-272`). |
```

- [ ] **Step 3: Also fix the American-spelling miss in the same file**

The 2026-08-30 session fixed "Colour"→"Color" in the *user-facing* UI (`web/index.html`, `web/app.js`) but deliberately left `web/README.md` alone since it's a developer doc, not UI copy. Leave `web/README.md`'s remaining "colour" spellings (there are three: line 18, line 76's own new text from Step 2, and line 97 context) as-is — this was already decided this session, don't re-litigate it. Skip this step; it's here only so a fresh reader doesn't "fix" something that was an intentional decision.

- [ ] **Step 4: Commit**

```bash
git add web/README.md
git commit -m "docs: correct web/README bug table — colour override is already fixed"
```

---

### Task 4: Add a "commit incrementally" trap note to `AGENTS.md`

The `web/` prototype was originally built by a subagent via Bash/heredoc rather than tracked `Edit`/`Write` tool calls, across a session that ran uncommitted for roughly two days (built ~2026-08-29 20:30, first committed 2026-08-30 as `9c4e14a`). When later work needed to understand what changed and why, there was no git history and no recoverable tool-call trail to diff against — only the final on-disk state. This is a cheap, generalizable trap worth recording so it doesn't repeat.

**Files:**
- Modify: `AGENTS.md` (append one bullet to the existing `## Known traps` section, which currently ends with the "onX format is not fully standard" bullet, just before `## Scope discipline`)

**Interfaces:** None — documentation only.

- [ ] **Step 1: Add the bullet**

In `AGENTS.md`, in the `## Known traps` section, after the last existing bullet (the one ending "...See `TECH_DETAIILS.md`.") and before the `## Scope discipline` heading, add:

```markdown
- **A subagent-built feature with no commits has no history.** `web/` was built by a subagent via
  Bash/heredoc rather than tracked `Edit`/`Write` calls, across an uncommitted session spanning
  roughly two days (built 2026-08-29, first committed 2026-08-30 as `9c4e14a`). A later session
  needing to know what changed and why had nothing to diff against — no git history, no
  recoverable tool-call trail, only the final file. Commit working prototype code early and often,
  even before it's "done" — an ugly commit history beats an unrecoverable one.
```

- [ ] **Step 2: Verify placement**

```bash
grep -n "## Known traps\|## Scope discipline\|subagent-built feature" AGENTS.md
```
Expected: the new bullet's line number falls between the two heading line numbers.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: record the uncommitted-subagent-work trap in AGENTS.md"
```

---

## Not a task: open questions for whoever does the actual Vercel deploy work

These are facts observed during the 2026-08-30 session, not actionable here — they need a live Vercel account/CLI to resolve and are called out in `docs/VERCEL_DEPLOY_PLAN_2026-08-30.md` for that separate effort to pick up:

- `web/dist/*.whl` is gitignored with no build step producing it before deploy.
- No `vercel.json` or build/output directory convention chosen yet.
- Whether Vercel's default response headers (CSP in particular) block Pyodide's `cdn.jsdelivr.net` script load has never been checked against a real deployment.

Do not attempt to solve these as part of this plan — they belong to the parallel Vercel-deploy-planning work the user referenced, which this plan's output is meant to be combined with, not duplicate.

## Self-Review

- **Spec coverage:** All four numbered open items from `docs/VERCEL_DEPLOY_PLAN_2026-08-30.md`'s "Explicitly deferred" / "Loose end" / "Facts relevant to a Vercel deploy" / "Process note" sections map onto Tasks 1–4 above, or (for the Vercel-specific facts) the explicit non-task callout — nothing silently dropped.
- **Placeholder scan:** No "TBD"/"fill in details"/bare "add error handling" — Tasks 1 and 2 are honestly investigation-first because no design exists yet, and their steps say exactly what to search, run, and ask rather than what to conclude.
- **Type/name consistency:** Selectors and function names referenced (`#control-bar`, `updateSel()`, `.icon-btn`, `.whymark`, `it.icon`/`it.needs_attention`/`it.why`, `SEL`) all match current `web/app.js`/`web/index.html` as of commit `9c4e14a` — verified by reading those files this session, not assumed.
