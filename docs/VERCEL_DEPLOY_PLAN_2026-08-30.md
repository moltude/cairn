# Deployment plan — Cairn web prototype to quietmarch.to/cairn — 2026-08-30

_(Originally titled "Vercel deployment plan" — corrected 2026-08-30: quietmarch.to turned out to
be on Cloudflare Pages, not Vercel. See the corrected status note and §4 below.)_

**Goal:** Deploy the static, client-side Cairn web prototype to Vercel, served at the subpath
`quietmarch.to/cairn` (the user's personal blog domain). This is a demo-stage deploy: a live,
shareable URL for the working Pyodide prototype. **Not** the full hybrid rollout from
`docs/PLATFORM_DECISION_2026-08-29.md` — that requires additional phasing.

**Status of quietmarch.to hosting:** [CORRECTED — 2026-08-30, supersedes the "confirmed by user"
line below] The earlier note that quietmarch.to is "already on Vercel" was **wrong**. Verified
directly against the live site: DNS resolves to Cloudflare IPs/nameservers, the response carries
no Vercel or GitHub Pages fingerprint (`server: cloudflare` only), and
`https://quietmarch-to.pages.dev` — the default hostname Cloudflare Pages assigns a project named
`quietmarch-to` — serves byte-for-byte the same HTML as the apex domain. So the origin is a
**Cloudflare Pages project** (git-integrated with `github.com/moltude/quietmarch.to`, a Jekyll
site; there's no deploy config in that repo — an empty `.github/workflows/`, no `wrangler.toml` —
because the build/deploy lives entirely in the Cloudflare dashboard's Pages git integration, not
in the repo). Vercel is not in the request path for this domain at all.

**This means Option A (a Vercel-side rewrite) cannot work** — quietmarch.to's routing isn't
controlled by Vercel, so there's nothing on the Vercel side to add a rewrite to. The fix has to
live on the Cloudflare side, in front of the Pages project:

- **A Cloudflare Worker bound to a Route on the zone** (`quietmarch.to/cairn*`) that proxies to
  the Vercel production URL. This is the only viable path-based mechanism — Cloudflare Pages'
  `_redirects` file supports a same-site "rewrite" via status 200, but its own docs are explicit
  that "proxying will only support relative URLs on your site — you cannot proxy external
  domains," which rules out using it to reach a separate Vercel deployment.
- Worker Routes are documented to take precedence over a Pages/Custom Domain binding on the same
  hostname, which is what makes this work — **verify this in the dashboard** (Workers & Pages →
  Routes for this zone) before relying on it, and check there's no existing Route/Page Rule
  already claiming `/cairn*`.
- The Worker needs to: redirect bare `/cairn` (no trailing slash) to `/cairn/` (the app's relative
  asset paths resolve against the URL's directory, so without the slash every asset 404s); strip
  the `/cairn` prefix and proxy the remainder to the Vercel production URL; and **rewrite the
  `Location` header on any 3xx response back under `/cairn`** — `web/vercel.json` sets
  `cleanUrls: true`, so Vercel does emit redirects (e.g. `Location: /index`), and forwarded
  verbatim that would send the browser out of `/cairn/` into the blog's own `/index`.
- Do **not** attach `quietmarch.to` as a custom domain on the Vercel project — DNS is already
  pointed at Cloudflare Pages, and adding it would fight that. Keep Vercel's own stable production
  alias (e.g. `cairn-web.vercel.app`) as the Worker's proxy target, and confirm Vercel's
  Deployment Protection is off for production (a 401 forwarded through the proxy just fails the
  page silently).
- This needs no changes to the `moltude/quietmarch.to` repo at all — Worker Routes are configured
  at the zone level (Cloudflare dashboard or `wrangler`), independent of the Pages project's own
  build.

**Security review:** [verified — 2026-08-30] A dedicated security-review pass (OWASP-category
scan: XSS, path traversal, injection, unsafe deserialization, code execution) was run against the
full `web/` + `tests/web/` diff. Result: **no high-confidence vulnerabilities.** Every
`innerHTML` site in `app.js` that touches user-file-derived content (names, descriptions, folder
names) is routed through the `esc()` escaping helper; `bridge.py`'s `_safe()` strips path
separators before any filename reaches a filesystem write; there is no `eval`/`exec`/unsafe YAML
load of untrusted content. Two hardening (not vulnerability) items were folded into this plan
regardless, since the app is about to go public-facing: `micropip.install("pyyaml")` is now
version-pinned (`pyyaml==6.0.2`), and the SRI hash for the Pyodide CDN `<script>` tag was
**added by the capstone session** (sha384, computed from the pinned v0.28.3 file), along with a
strict CSP + security headers in `web/vercel.json` that the dev server mirrors and the e2e suite
enforces (`test_page_boots_under_enforced_csp`).

**Post-review correctness pass:** [verified — 2026-08-30] A second pass (not a security review —
a plain "would this actually work" check) caught four issues in the first draft of this plan, all
fixed in this session: the engine wheel was silently excluded from git by a blanket `dist/` rule
in `.gitignore` (§1); a relative-path fetch breaks at `/cairn` without a trailing slash, since
relative URLs resolve against the *directory* of the current page, and `/cairn` (no slash) has
`/` as its directory, not `/cairn/` (§4 now requires a redirect, not just the rewrite); the
original `vercel.json` set `"buildCommand": false`, a boolean where Vercel's schema wants
`string | null` (§3, now restructured); and the documented `BASE_URL=... pytest` verification
command was a no-op because the test hardcoded `BASE_URL` as a Python constant that never read
the environment (§6, now fixed in `tests/web/test_web_app.py`).

**Merge note (2026-08-30 capstone session):** this file now combines two same-day efforts that
each wrote to this path in different checkouts: the deploy plan below (from the
`worktree-vercel-deploy-plan` branch) and the web-UX session's staging notes (Appendix A).
Everything the worktree branch shipped has been ported onto `main`: `web/vercel.json` (now with
security headers), the `.gitignore` wheel negation with the wheel committed at `web/dist/`, the
`app.js` subpath-safe wheel fetch + pyyaml pin, and the `BASE_URL` env fix in the e2e suite.
The port went further than the branch: the capstone session's enforced-CSP boot test exposed
that `micropip.install(url, { deps: false })` — in both the branch's and main's `app.js` — never
actually passed `deps=False` (a plain JS object lands as the second *positional* arg), so every
boot silently resolved typer/rich/textual from PyPI; fixed with `install.callKwargs`.
**The worktree branch is superseded** — its `web/` predates `main`'s
control-bar redesign (`9c4e14a`); do not merge it. Section 1's pre-flight is therefore done on
`main`, and the "Needs the user" steps at the end are the live to-do list.

---

## 1. Pre-flight: commit web/ and tests/web/ to git

Vercel deploys from a git repository and branch. `web/` and `tests/web/` were untracked in the
main checkout; **done in this session** — committed on branch `worktree-vercel-deploy-plan`
alongside the fix in §2 and the `vercel.json` in §3.

**Caught and fixed:** the repo's `.gitignore` has a blanket `dist/` rule (for `uv build` output at
the repo root), which also matched `web/dist/` and silently excluded
`cairn_maps-1.0.0-py3-none-any.whl` from the first commit — `git add web/` staged everything
except the one file the app actually needs at runtime. Fixed with a targeted negation:
```
dist/
!web/dist/
!web/dist/*.whl
```
Verify before trusting any future commit here: `git ls-files web/dist/` must list the `.whl`.

Still needed: push the branch and open a PR against `moltude/cairn` (public repo) so the change
is reviewable before it goes live — confirm with the user before pushing/opening the PR, since
this is the first time this prototype code becomes part of the public repo's history.

---

## 2. Fix the subpath wheel-fetch code path — done

**The issue:** [verified]

`web/app.js` fetched the engine wheel via `location.origin + "/dist/..."` — an absolute,
from-domain-root URL. `location.origin` is protocol + domain root only, e.g.
`https://quietmarch.to`; served at `/cairn/`, that resolved to `https://quietmarch.to/dist/...`
(wrong) instead of `https://quietmarch.to/cairn/dist/...` (correct).

**Fix applied** (this session): changed to a relative path —
```javascript
await micropip.install("./dist/cairn_maps-1.0.0-py3-none-any.whl", { deps: false });
```
Works identically at domain root or at `/cairn/`, no per-deployment config, no `<base href>` or
build-time substitution needed. Same edit also pinned the previously-unpinned `pyyaml` install to
`pyyaml==6.0.2` (a hardening item surfaced by the security review, not a functional bug).

**Rationale against alternatives:**
- **location.origin + location.pathname prefix logic**: adds runtime coupling to deployment
  path; if anyone later moves the app to a different subpath, the code breaks silently
  (micropip would try `/old/path/dist/...` if the hardcoded path prefix was wrong)
- **Vercel environment variable substitution in build**: adds a build step; this is a static
  app with no build — introducing one raises tooling complexity
- **<base href> tag**: requires index.html modification per deployment; relative path is simpler

---

## 3. vercel.json and static hosting config — done

**Root directory:** set `web/` as the Vercel **Project Setting** "Root Directory" when creating
the project (dashboard, or `vercel link` then adjust in project settings) — not via a
`vercel.json` key. Build step: none — pure static site (HTML + CSS + JS + whl); with no
`package.json` or other framework manifest present, Vercel's auto-detection lands on "Other"
(static passthrough, zero build) on its own, so there's nothing to override.

**`web/vercel.json`** (this session — placed inside `web/` because that becomes the project root
once Root Directory is set, and Vercel looks for `vercel.json` at the project root):
```json
{
  "cleanUrls": true,
  "headers": [
    {
      "source": "/dist/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }
      ]
    },
    {
      "source": "/((?!dist/).*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=3600, must-revalidate" }
      ]
    }
  ]
}
```
Deliberately has no `buildCommand`/`outputDirectory` keys — an earlier draft set
`"buildCommand": false`, which is the wrong type (Vercel's schema wants `string | null`) and would
likely fail schema validation at deploy time. Letting Root Directory + auto-detection handle it
avoids the type risk entirely; `vercel build` (once logged in) will validate this file locally
before the first real deploy.

- `/dist/` (the wheel) gets a 1-year immutable cache since the filename is version-pinned; every
  other file gets a 1-hour cache with revalidation so app.js/index.html fixes propagate quickly
- No custom MIME mapping needed — Vercel serves `.whl` as a generic binary type by default and
  micropip reads it as raw bytes regardless of the declared content-type. [verified]

---

## 4. Domain wiring: a Cloudflare Worker route, not a Vercel rewrite

[CORRECTED — 2026-08-30] The section below (a same-account Vercel rewrite) assumed
`quietmarch.to` was itself a Vercel project. It isn't — see the corrected status note above. There
is no quietmarch.to-side Vercel project to add a rewrite to, so this whole approach is void. The
routing has to happen on the Cloudflare side instead, since that's what's actually in front of the
domain (a Cloudflare Pages project serving the Jekyll blog).

**Steps:**
1. Create a **new, separate Vercel project** for cairn's `web/` (don't fold it into anything else
   — different repo, different deploy cadence). `vercel link` from the cairn repo root, or import
   `moltude/cairn` in the Vercel dashboard. Root Directory = `web/`.
2. Deploy it (`vercel --prod` or a dashboard-triggered deploy from the PR branch) and note the
   stable production alias — e.g. `cairn-web.vercel.app` (exact name depends on what Vercel
   assigns). Do **not** add `quietmarch.to` as a custom domain on this project — its DNS is
   already pointed at Cloudflare Pages, and this would conflict with that. Confirm Deployment
   Protection is off for production, or a forwarded 401 will silently break the page.
3. Add a **Cloudflare Worker** with a **Route** bound to the `quietmarch.to` zone
   (`quietmarch.to/cairn*` — the broad pattern; `/cairn/*` alone misses the bare `/cairn` request).
   Configured in the Cloudflare dashboard (Workers & Pages → Routes) or via `wrangler` — this
   needs **no changes to the `moltude/quietmarch.to` repo**, since Routes live at the zone level,
   independent of the Pages project's build. The worker logic:
   - Bare `/cairn` (no trailing slash) → 301/308 redirect to `/cairn/`. Same reason as the old
     Vercel-rewrite draft had this: the app's relative asset paths (`./dist/...`) resolve against
     the URL's *directory*, and `/cairn` (no slash) has `/` as that directory, not `/cairn/`.
   - Otherwise: strip the `/cairn` prefix and `fetch()` the remainder from
     `https://cairn-web.vercel.app/...`, streaming the response back.
   - **Rewrite the `Location` header on any 3xx response back under `/cairn`.**
     `web/vercel.json` sets `cleanUrls: true`, so Vercel does emit redirects (e.g.
     `Location: /index`); forwarded unmodified, that sends the browser out of `/cairn/` into the
     blog's own `/index` — a silent, intermittent break rather than an obvious one.
4. This is new infrastructure attached to a **separate, live, production zone**
   (`quietmarch.to`), configured via the Cloudflare dashboard/API — confirm with the user before
   creating the Route or (if going the `wrangler` route) deploying the Worker.

**Cloudflare Route-vs-Pages precedence:** Worker Routes are documented to take precedence over a
Pages project's binding on the same hostname (the same rule Cloudflare documents for Routes vs.
Custom Domains generally). This is the assumption the whole plan rests on — **verify it in the
dashboard** (Workers & Pages → Routes for this zone) as part of setup, and check there's no
existing Route or Page Rule already claiming `/cairn*` that would need to be reconciled first.

---

## 6. Verification: confirm the live app works

Once deployed to the chosen URL (subpath, subdomain, or proxied):

**Smoke test (manual):**
1. Open the live URL in a browser (e.g. `https://quietmarch.to/cairn`, `https://cairn.quietmarch.to`, etc.)
2. Wait for "Ready · engine v..." in the status bar
3. Load a test map: download the fixture at
   `tests/fixtures/bitterroots/Bitterroots__Complete_.json` (or use any CalTopo/GeoJSON export
   you have)
4. Drop the file on the page
5. Click one waypoint and assign it an icon (to exercise the icon picker)
6. Perform a bulk color reassignment on 5+ items
7. Export and download the ZIP

**Automated test (e2e):**
`tests/web/test_web_app.py` now reads `BASE_URL` from the environment (fixed this session — it
was previously a hardcoded constant that silently ignored the variable, making this command a
no-op):

```bash
# Local dev server (default, no BASE_URL needed):
uv run pytest --no-cov -p no:cacheprovider tests/web/test_web_app.py

# Against the live deploy — note the trailing slash, required per §4:
BASE_URL=https://quietmarch.to/cairn/ uv run pytest --no-cov -p no:cacheprovider tests/web/test_web_app.py
```

When `BASE_URL` is left unset, an unreachable local server still skips cleanly. When `BASE_URL`
is set explicitly (the live-deploy case), an unreachable URL now **fails** the run instead of
skipping — a skip would report green for a broken or mistyped deployment URL, which is worse than
no test at all.

**Expected results:**
- Page loads, no JavaScript errors (check browser console)
- Status shows engine version, not "Failed"
- File loads, folders and items render
- Export produces a ZIP with GPX/KML files matching the test fixture's expected output
  (exact byte-for-byte match is not guaranteed across browser/Pyodide versions, but structure
  and content must match the CLI's output for the same input)

---

## 7. Rollback and iteration

**Updates:** Once the initial deploy is live, any changes to `web/` files trigger automatic
redeployment via Vercel's git webhook. Simply push to the repo:

```bash
# Fix app.js or any file in web/
git add web/
git commit -m "Fix: improve icon loading UX"
git push
# Vercel redeploys automatically within 30 seconds
```

**Engine updates:** When `cairn/core/` or the engine logic changes:
1. Rebuild the wheel (`uv build --wheel` from the repo root, output to `web/dist/`)
2. **Bump the version number in the wheel filename** (e.g. `cairn_maps-1.0.1-py3-none-any.whl`)
3. Update the fetch URL in `app.js` to match the new version
4. Push to git; Vercel redeploys

This versioning prevents the browser from caching an outdated wheel; new users get the latest
version automatically.

**Current limitation:** [inferred] There is no CI-driven wheel rebuild. The wheel is currently
committed to git at `web/dist/`. A production setup would build the wheel in CI on every push
to `cairn/core/` and commit the updated wheel to the `web/dist/` path, or build it on-the-fly
during Vercel deploy. This is out of scope for the demo phase; document it as a follow-up.

---

## 8. What this deploy does NOT solve

This plan deploys a working prototype. It is **not** the full hybrid rollout from
`docs/PLATFORM_DECISION_2026-08-29.md`. Limitations:

- **No CI-driven wheel rebuild:** The wheel is manually built and committed; engine changes
  don't auto-trigger a new wheel. Phase 2 will add this.
- **Not yet live:** the domain wiring in §4 depends on adding a rewrite to a separate production
  repo (`quietmarch.to`) and on confirming Cloudflare isn't intercepting the route first — both
  require the user's direct involvement (see Next steps).
- **No PWA offline mode:** The prototype requires an internet connection (Pyodide download,
  Maplibre basemap tiles if added). Offline mode is a phase-2 feature.
- **CLI/scripting leg not deployed:** The hybrid includes a retained CLI for scripting; this
  deploy is the web UI only. The CLI remains in the repo for the user's local use.
- **No interactive import runbook visualization on live:** The import checklist is text-based
  in the prototype. The "sleeper killer feature" from the platform decision (interactive
  checklist with onX Web Map deep-links) is a phase-2 add-on.

---

## Next steps

**Done this session** (branch `worktree-vercel-deploy-plan`, not yet pushed):
- Committed `web/` and `tests/web/` to git
- Fixed the subpath wheel-fetch bug and pinned `pyyaml` (§2)
- Added `web/vercel.json` for the cairn deploy (§3)
- Ran a dedicated security review — no vulnerabilities found (see header)
- Post-review correctness pass caught and fixed 4 deploy-blocking/false-confidence issues:
  the wheel was silently gitignored (§1), the subpath needs a trailing-slash redirect not just
  the rewrite (§4), `vercel.json`'s `buildCommand` had the wrong type (§3), and the e2e suite's
  `BASE_URL` override was a no-op (§6)

**Needs the user** (live-account steps this session can't do unattended):
1. Confirm pushing this branch and opening a PR against `moltude/cairn` (public repo).
2. Run `vercel login` interactively (CLI is installed but not authenticated in this
   environment) and link/create the cairn Vercel project with **Root Directory = `web/`**, or do
   it via the Vercel dashboard. Confirm Deployment Protection is off for production.
3. Get the resulting stable production alias (e.g. `cairn-web.vercel.app`).
4. In the Cloudflare dashboard for the `quietmarch.to` zone (Workers & Pages → Routes), in one
   sitting: check for any existing Worker Route or Page Rule already claiming `/cairn*`; confirm a
   Worker Route does take precedence over the Pages binding here; then create the Route
   (`quietmarch.to/cairn*`) and the Worker that proxies to the alias from step 3, handling the
   trailing-slash redirect and `Location`-header rewrite described in §4 — this needs no changes
   to the `moltude/quietmarch.to` repo.
5. Verify the live deploy with the smoke test and/or e2e suite (§6).

---

# Appendix A: web/ UX session staging notes (2026-08-30)

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
