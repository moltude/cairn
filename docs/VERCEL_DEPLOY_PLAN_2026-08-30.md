# Staging notes: web/ UX session → Vercel deploy plan

This file is a handoff, not a deploy plan. This session worked on the `web/`
prototype's top control bar; it did not touch deployment. Written so the next
session can fold this into the actual Vercel deploy plan without re-deriving
it from scratch.

## What shipped this session

Committed at `9c4e14a` ("Add web prototype; redesign top control bar for
discoverability") — this was also the **first commit of `web/` and
`tests/web/` at all**; neither had ever been in git before.

- Merged the selection-only bulk-action bar into the persistent filter bar.
  `Set icon…` / `Set color…` are now always visible, disabled until a row is
  selected — previously they only existed once you'd already ticked a box,
  which made them hard to find.
- `Clear selection` restyled from a near-invisible ghost button to a visibly
  bordered one; the action cluster now wraps as a unit on narrow viewports
  instead of stranding a single button alone.
- Selection now always matches what's on screen: `renderFolders()` prunes
  `SEL` to the currently-visible set on every render, so changing a filter
  can no longer leave a bulk edit silently targeting off-screen rows. (Found
  via a Playwright diagnostic pass — see `tests/web/test_web_app.py`.)
- "Colour" → "Color" (American spelling) in help text and picker titles.
- `tests/web/test_web_app.py` updated for the merged bar; 35/35 passing.

## Explicitly deferred (user asked for a separate pass)

- **OnX icon column default-selection concern.** Every waypoint row shows a
  resolved icon by default (e.g. "Location"), which reads as "already
  selected/reviewed" even when the engine just guessed. Flagged in this
  session's first round of feedback as confusing; user's suggestion was to
  hide the column behind a different selector/toggle pending investigation.
  **Not designed or implemented — needs its own brainstorming pass.**

## Loose end, not yet located

- Original feedback (round 1, before this file's session context began)
  mentioned headers labeled **"Empty" and "In"** being unclear. Nothing in
  the current `web/index.html` / `app.js` has headers by those names — this
  may refer to a different screen, an earlier discarded iteration, or the
  TUI (`cairn/tui/tables.py`) rather than the web prototype. Never resolved
  or even identified this session; re-ask before assuming it's stale.

## Facts relevant to a Vercel deploy (observed, not acted on)

- `web/dist/*.whl` (the built engine wheel `app.js` fetches at
  `location.origin + "/dist/..."`) is **gitignored** (`.gitignore:51`). A
  Vercel deploy needs a build step that runs
  `uv build --no-sources && cp dist/*.whl web/dist/` before serving —
  there's currently no `vercel.json` or CI step that does this.
- All asset fetches in `app.js`/`index.html` are relative
  (`fetch("bridge.py")`, `fetch("cairn_config.yaml")`, the wheel path above)
  — no hardcoded `localhost`, so static hosting should work once the wheel
  build step exists.
- `web/README.md`'s "Bugs this prototype exposed" table lists the colour
  override bug as open; it's actually already fixed in `web/bridge.py:257-272`
  (writes the picked color onto `feature.color` directly, only for
  user-edited items). That table wasn't re-verified against current code
  this session — treat it as possibly stale rather than current status.
- No `vercel.json`, no build/output directory convention chosen, no check
  that Pyodide's CDN script tag (`cdn.jsdelivr.net/pyodide`) survives
  whatever CSP Vercel's default headers would impose — none of this was
  investigated this session.

## Task 1 resolution (2026-08-30)

Searched for headers labeled "Empty" / "In" per the follow-up plan: no match in
`web/index.html` / `web/app.js` / `web/styles.css` (only prose uses of "empty"),
and none in `cairn/tui/tables.py` — all eight `add_columns` calls use
Selected / Folder / Waypoints / Routes / Shapes / Name / OnX icon / OnX color /
Color / Pattern / Width. A repo-wide grep for `"Empty"` / `"In"` as labels also
found nothing. The complaint has no locatable referent in current code — it
likely refers to a discarded earlier iteration. **Needs a fresh screenshot or a
pointer from the user (web or TUI, which screen) before anything can be fixed.**

## Process note

`web/` was originally built by a subagent (Bash/heredoc, not tracked
Edit/Write calls), so there's no session-log or git history for its
pre-this-session state — if a future session needs "what did it look like
before," there isn't one short of asking the user for a screenshot.
