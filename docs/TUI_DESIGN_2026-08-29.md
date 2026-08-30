# TUI design direction — 2026-08-29

Companion to `UX_AUDIT_2026-08-29.md` (what using Cairn is like today). This one is about where
the interface should go. Version and API claims were checked against Textual's `CHANGELOG.md`
and the linked primary sources; inferences are marked as such.

---

## The headline: this is not a framework problem

Cairn pins `textual>=0.58.0` (April 2024) and resolves to **6.11.0**. Latest is **8.2.8**.
It would be easy to read the symptom list — dead search box, Esc traps, 5.8-second lag, no undo —
as "Textual is holding us back." It isn't. Every one of those is an application-level bug or an
unused native feature:

| Symptom | Reality |
|---|---|
| Three disagreeing help systems | Textual has shipped a contextual help panel (`DOMNode.HELP` + a built-in "Show keys" command) since **0.77.0** (2024-08-22). Cairn built three competing systems instead of using it. |
| 5.8s per selection toggle | Not a `DataTable` limit. Harlequin — also Python/Textual/`DataTable` — handles thousands of rows comfortably. Cairn calls a **full table rebuild on every single space-press**. |
| Bulk select is clumsy | Textual ships `SelectionList`, whose `select_all()`/`toggle_all()` fire **one** message regardless of item count. Cairn's toggle path does the opposite. |
| Search box unusable | It's an `Input` bolted onto a table that steals its own focus. Every surveyed tool makes search a modal overlay instead. |
| `NO_COLOR` ignored | Textual has had a `nocolor` pseudoclass and `App.ansi_color` since **0.80.0** (2024-09-23) — already available at 6.11.0. |

**The fix is "use more of Textual, correctly," not "leave Textual."** Assessed honestly against
the alternatives: Rich-only means rebuilding widgets/layout/focus from scratch; prompt-toolkit is
built for REPL line-editing, not multi-pane data tables; urwid lacks the `DataTable`/CSS/testing
ecosystem; Bubble Tea or ratatui mean a full rewrite in another language, discarding 3,700 lines
and the test suite. For a solo maintainer with a working-if-buggy app, staying is correct.

### One thing to fix immediately: the version pin is a false claim

`textual>=0.58.0` declares support for a range (0.58 → 8.2.8) that has never been tested. A grep
for every removed/renamed API across those versions (`.dark`, `renderable=`, `ClassicFooter`,
`Select.BLANK`, `namespace_bindings`, `Widget.anchor(`, …) found **zero hits** in `cairn/` and
`tests/` — the app was already written against Theme-era conventions. So the upgrade is
mechanically low-risk (about half a day, mostly re-running tests), and the pin should say what is
actually verified: `>=6.11,<9`.

Worth noting for later: `ansi-dark`/`ansi-light` themes landed in **8.2.5** (2026-04-30), which is
the concrete payoff for bumping. Kitty keyboard protocol support landed in **8.2.7**.

---

## What the good terminal apps actually do

Eight widely-used TUIs were surveyed for transferable mechanics. The single most striking result:
**none of lazygit, k9s, yazi, btop, gh-dash, atuin, harlequin, or posting uses a linear wizard for
its core loop.** All are persistent workspaces; modals are reserved for rare or destructive
actions. That convergence across eight independently-built tools is the strongest available
argument about Cairn's shape.

The patterns worth stealing, in order of fit:

**yazi's cross-directory selection** — selection *persists as you navigate*. Select items in
folder 1, move to folder 2, select more; the working set accumulates until you act. This fixes
two of Cairn's worst problems at once: the multi-folder loop with no orientation, and the
one-folder-at-a-time editing model.

**yazi's editor-based bulk rename** — dump the selected items' names into `$EDITOR`, let the user
edit freely (including their own find/replace), diff old against new, apply. This is the direct
answer to Cairn's "bulk rename means giving 40 waypoints the same literal string." It supports
arbitrary per-item edits without Cairn having to build a rename mini-language.

**lazygit's undo** — one global key (`z`), one stack, not per-screen. Cairn has no undo at all.

**lazygit's graduated destructive confirmation** — `shift+D` opens a *menu of named options*
rather than a blind y/n. Fits Cairn's backwards risk model, where renaming 2 items prompts but
re-icon-ing 500 doesn't.

**k9s's `:resource` jump and `?` context-scoped help** — `?` shows the *currently active*
bindings, not a static cheat sheet. That is the fix for three help systems that disagree.

**atuin's search** — a full-screen modal on one key, where the same key cycles filter scope.
Cairn's search should become this rather than be patched.

**posting's discovery model** — footer shows only 4–5 truly global keys; everything else lives in
the command palette. Cairn currently renders the same shortcut list twice on every screen, eating
25% of the width, and a third copy disagrees with both.

---

## Wizard → workspace

Cairn's six-step wizard is fighting itself, and the evidence is in its own source: `Folder` is
conditionally skipped, `Waypoints` is skipped but still check-marked, and `Routes` is
*deliberately never skipped* — with a comment saying tests rely on deterministic Enter
progression. **The state machine is currently shaped by the test suite rather than by the user.**

Nielsen Norman's criteria for when a wizard is the wrong pattern name three failure conditions;
Cairn meets all three: it is run repeatedly (every export), users need to compare state across
steps while editing, and the workflow wants arbitrary sequencing rather than enforced order.

**Recommendation:** keep a thin wizard for `Select_file` — that genuinely is a one-time setup
step, which is exactly what wizards are for. Convert `Folder → Routes → Waypoints → Preview` into
an addressable workspace (Textual `TabbedContent` or `Screen` `MODES`, both long-stable),
reachable in any order, with a persistent orientation indicator.

**The blocker is the test suite, and it must be cleared first.** The wizard shape is held in place
by brittle keystroke-order tests, and this project already knows those tests can't be trusted (35
of them swallow exceptions and assert nothing). Any workspace conversion has to be preceded by
replacing them with state-keyed `Pilot` tests — assert on `app.state.X` after an interaction, not
on a fixed keypress sequence — plus `pytest-textual-snapshot` for visual regressions. Skipping
that means the refactor looks done and silently regresses.

So: **the orientation bar ships now; the conversion is its own project, gated on test work.**

---

## Bulk editing — the anchor feature

This is the most-requested item in the project's own backlog and the stated reason the tool
exists. It needs four things Cairn doesn't have:

1. **Selection that survives navigation** (yazi's model) — so a multi-folder edit is one pass.
2. **Arbitrary per-item rename**, not one shared string. Editor round-trip is the cheapest path;
   prefix/suffix and find-replace already exist in the legacy CLI (`core/preview.py:67`) and
   simply never made it into the TUI.
3. **Preview-diff before commit**, scoped to the edit: *"This will rename 12 waypoints to
   'Camp' — Enter to confirm, Esc to cancel."* Cairn has a Preview *step*, but by then you are
   five screens from the editor.
4. **Undo.** The snapshot machinery already exists at `app.py:995-1145`; no key reaches it.

On typed range syntax (`1,3,5-9`, `all`) from the backlog: no surveyed terminal tool uses that
grammar — the real precedents are `vim`'s `:5,10d` and print-dialog page ranges. It is a
reasonable power-user fast path, but it should be added *alongside* visual selection, not instead
of it, because visual selection is what every one of these tools actually ships.

---

## Accessibility — the honest version

Two things worth separating.

**What's real and cheap:** Textual has supported `NO_COLOR` since 0.80.0 — but **Cairn does not
use it.** Verified: `cairn/tui/theme.tcss` contains **zero** uses of the `nocolor` pseudoclass and
**75 hardcoded color literals**, and there is no `NO_COLOR` handling anywhere in the Python
either. So the "NO_COLOR not respected" item that has sat on the known-issues list since December
2025 is confirmed, and now has a cause: the framework offers the hook, the theme bypasses it.
Fixing it means routing those 75 literals through theme tokens — which is also what the TODO's
"use color labels to ensure theme migration" note is asking for, so the two jobs are one job.
Mouse-optional operation is already true by default — preserve it as a non-regression.

**What not to over-promise:** Textual's marketing page claims screen-reader integration; that is
vendor copy I could not verify against the changelog. There is a documented argument that TUI
frameworks redrawing a 2D grid break screen readers because the cursor jumps unpredictably on
repaint. That article names Ink, Bubble Tea, and tcell — **not Textual** — so extending it to
Textual is inference, not established fact.

The honest position: the accessibility work that actually pays off here is (a) fixing the Esc trap
and the dead search box — those *are* the accessibility bugs that matter most — and (b) a properly
scriptable non-interactive CLI, which is trivially screen-reader- and automation-friendly in a way
no amount of TUI polish achieves. That makes fixing `--no-interactive` (currently broken: it
prompts anyway and aborts) an accessibility fix, not just a scripting one.

---

## Ranked plan

Ordered by user value per unit of effort. Items 1–2 are in flight in this session.

| # | Change | Value | Effort |
|---|---|---|---|
| 1 | **Fix Esc** — quits the app after export; can't close modals, and silently rewinds a step per press | High (data loss, trust) | Low |
| 2 | **Fix per-toggle lag** — stop full-table rebuild on every space-press; update the one changed row | High (blocks real datasets) | Low–med |
| 3 | **Delete the three help systems**, use Textual's native help panel + "Show keys" | High | Low (delete, don't build) |
| 4 | **Search becomes a modal overlay** instead of a focus-stealing inline `Input` | High | Medium |
| 5 | **Bounded undo stack** around the existing mutation call sites; one global key | High (biggest trust gap) | Medium |
| 6 | **Real bulk edit** — persistent selection, per-item rename, preview-diff | Highest strategic | High |
| 7 | **Orientation bar** in the multi-folder loop ("Folder 2 of 5 — 3 done") | Medium | Low |

Deliberately *not* in the list: bumping the Textual pin. The help panel, `SelectionList`, command
palette, and `NO_COLOR` support are all already available at the resolved 6.11.0, so the bump
blocks nothing. Do it anyway to make the declared range honest — just don't expect it to fix
anything.
