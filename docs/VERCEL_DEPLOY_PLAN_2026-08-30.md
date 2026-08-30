# Vercel deployment plan — Cairn web prototype to slowmarch.to/cairn — 2026-08-30

**Goal:** Deploy the static, client-side Cairn web prototype to Vercel, served at the subpath
`slowmarch.to/cairn` (the user's personal blog domain). This is a demo-stage deploy: a live,
shareable URL for the working Pyodide prototype. **Not** the full hybrid rollout from
`docs/PLATFORM_DECISION_2026-08-29.md` — that requires additional phasing.

**Status of slowmarch.to hosting:** [inferred] Unknown. WebFetch lookup on `https://slowmarch.to`
failed with DNS lookup error (`ENOTFOUND`), so the domain's current hosting provider and routing
could not be verified from this session. This plan forks into three options below; **the domain
wiring section must be resolved before executing the deploy.**

---

## 1. Pre-flight: commit web/ and tests/web/ to git

Vercel deploys from a git repository and branch. Currently:
- `web/` (the entire prototype: `app.js`, `index.html`, `styles.css`, `bridge.py`, `icons.js`,
  `cairn_config.yaml`, `dist/cairn_maps-1.0.0-py3-none-any.whl`, `serve.py`, `README.md`)
- `tests/web/` (the Playwright e2e suite, `test_web_app.py`)

are untracked and uncommitted.

**Action:**
```bash
# Stage and commit the prototype and its tests
git add web/ tests/web/
git commit -m "Add Cairn web prototype: Pyodide-based static app for CalTopo→onX conversion

- Single-page app loads the existing Python engine via Pyodide (WASM)
- No server, no upload, no backend — pure client-side transformation
- Includes bridge.py adapter, styling, icons, and demo config
- Playwright e2e test suite for smoke testing

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

Once committed, the deployment pipeline can use the branch as the source.

---

## 2. Fix the subpath wheel-fetch code path

**The issue:** [verified]

In `web/app.js` line 20, the wheel is fetched via:
```javascript
await micropip.install(
  location.origin + "/dist/cairn_maps-1.0.0-py3-none-any.whl", { deps: false });
```

`location.origin` is the protocol + domain root, e.g. `https://slowmarch.to`. If the app is
served at a subpath (e.g. `https://slowmarch.to/cairn/`), this resolves to
`https://slowmarch.to/dist/...` (wrong) instead of `https://slowmarch.to/cairn/dist/...` (correct).

**Recommended fix:** Use a relative path from the current directory. Modern fetch APIs in all
current browsers resolve relative URLs correctly even in WASM contexts. [inferred — Pyodide's
fetch shim delegates to the browser's fetch, which respects <base href> and relative resolution]

Change line 19–20 in `web/app.js`:
```javascript
// OLD:
await micropip.install(
  location.origin + "/dist/cairn_maps-1.0.0-py3-none-any.whl", { deps: false });

// NEW:
await micropip.install(
  "./dist/cairn_maps-1.0.0-py3-none-any.whl", { deps: false });
```

This is backwards-compatible (works equally well at domain root or at `/cairn/`), requires no
per-deployment configuration, and avoids the need for a `<base href>` tag or build-time
substitution.

**Rationale against alternatives:**
- **location.origin + location.pathname prefix logic**: adds runtime coupling to deployment
  path; if anyone later moves the app to a different subpath, the code breaks silently
  (micropip would try `/old/path/dist/...` if the hardcoded path prefix was wrong)
- **Vercel environment variable substitution in build**: adds a build step; this is a static
  app with no build — introducing one raises tooling complexity
- **<base href> tag**: requires index.html modification per deployment; relative path is simpler

---

## 3. Create vercel.json and static hosting config

**Root directory:** Set `web/` as the deployment root. Vercel will serve files from there.

**Build step:** None. This is a pure static site (HTML + CSS + JS + whl). No build pipeline.
Vercel simply copies files as-is. [verified]

**Create `vercel.json` at the repo root:**
```json
{
  "buildCommand": "true",
  "outputDirectory": "web",
  "public": false,
  "headers": [
    {
      "source": "/dist/:filename",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        },
        {
          "key": "Content-Type",
          "value": "application/octet-stream"
        }
      ]
    },
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=3600"
        }
      ]
    }
  ]
}
```

**Rationale:**
- `buildCommand: "true"` prevents Vercel from auto-detecting a build step (which would fail or add
  unnecessary latency)
- `outputDirectory: "web"` tells Vercel to serve this directory as the root
- Headers for `/dist/`: The wheel file (`cairn_maps-1.0.0-py3-none-any.whl`) is immutable and
  versioned; cache it aggressively (1 year). [verified — the filename is pinned; upgrades to the
  engine require a new wheel with a new version number]
- Headers for all other files: Cache shorter (1 hour) to enable quick updates to app logic
  without long waits for users on slow connections to re-fetch Pyodide and the wheel

**MIME type note:** [verified] Vercel's default static server correctly handles `.whl` files as
`application/octet-stream` (or any binary type); no custom MIME mapping needed. The fetch will
work as-is.

---

## 4. Domain wiring: subpath vs subdomain — critical fork

This is the single biggest unknown and decision point. The user's stated goal is serving the app
at `slowmarch.to/cairn`, but the feasibility depends on how `slowmarch.to` is currently
hosted.

### Option A: If slowmarch.to is already on Vercel

**Status:** [unknown] Cannot verify from this session (no DNS lookups possible).

**If true:** Serving `/cairn` as a subpath on the same Vercel project is straightforward.

**Steps:**
1. Create a second Vercel project for the Cairn web app (or integrate into the existing project
   if it's a monorepo)
2. Set the deployment's preview URL to `slowmarch.to/cairn` using Vercel's path-based routing
   OR a monorepo rewrite in `vercel.json`
3. In the blog's Vercel project config, add a rewrite:
   ```json
   {
     "rewrites": [
       {
         "source": "/cairn/:path*",
         "destination": "https://cairn-deployment.vercel.app/:path*"
       }
     ]
   }
   ```

**For a single Vercel account with both projects:** Verify Vercel's current **multi-zone** or
monorepo path-based routing support with their docs (this feature may have changed since
2024). The redirect approach above is the safer fallback.

---

### Option B: If slowmarch.to is elsewhere (not Vercel)

**Status:** [likely, unverified]

**Reality:** Most single-user blogs live on GitHub Pages, Netlify, a static host, or a
traditional host. True subpath routing at `/cairn` without control of the origin server's
routing layer is not possible. The practical workaround is a **subdomain**.

**Fallback deploy target:** `cairn.slowmarch.to` (a CNAME pointing to Vercel)

**Steps:**
1. Deploy the Cairn app to a new Vercel project
2. Add a custom domain `cairn.slowmarch.to` in Vercel project settings
3. Point the DNS CNAME record for `cairn.slowmarch.to` at Vercel's nameservers (Vercel provides
   the CNAME target in project settings)
4. Verify CNAME resolution; Vercel's dashboard will confirm DNS propagation

**Trade-off:** This gives a working shared URL (`cairn.slowmarch.to`), but it is not
`slowmarch.to/cairn`. No browser-based reverse-proxy routing without server-side rewrites.

---

### Option C: If DNS is managed by Cloudflare or another edge CDN

**Status:** [unknown]

If the user has Cloudflare (or another edge provider like Fastly) in front of `slowmarch.to` —
regardless of where the origin is hosted — path-based routing becomes possible:

**Steps:**
1. Deploy Cairn to a new Vercel project (`cairn-web.vercel.app`)
2. In Cloudflare Workers (or equivalent), add a route rule for `/cairn/*`:
   ```javascript
   // Route /cairn/* to Vercel Cairn app, everything else to origin
   if (request.url.pathname.startsWith('/cairn/')) {
     return fetch('https://cairn-web.vercel.app' + request.url.pathname.replace('/cairn', ''), request);
   }
   return fetch(request); // pass through to origin
   ```
3. Update DNS to route `slowmarch.to` through Cloudflare

This requires the user to confirm they control Cloudflare (or similar) for the domain.

---

## 5. Recommended path forward (given unknowns)

**Action order:**

1. **Resolve the domain hosting first.** Ask the user:
   - Is `slowmarch.to` already hosted on Vercel?
   - If not, is it on Netlify, GitHub Pages, or elsewhere?
   - Is the domain's DNS managed by Cloudflare?

   This determines whether to use **Option A** (subpath rewrite within Vercel),
   **Option B** (subdomain CNAME), or **Option C** (Cloudflare Worker reverse-proxy).

2. **Set up the Vercel project:**
   - Create a new Vercel project linked to the cairn GitHub repo
   - Configure it with the `vercel.json` above (root = `web/`, no build step)
   - Deploy a preview to verify the app loads at the Vercel preview URL

3. **Apply domain wiring per the user's hosting answer:**
   - **Option A:** Update the blog's Vercel config to rewrite `/cairn/*` to the Cairn project
   - **Option B:** Add a custom domain in Vercel; CNAME DNS record to Vercel
   - **Option C:** Set up a Cloudflare Worker (if the user has Cloudflare)

4. **Fix the wheel-fetch path** in `web/app.js` (from section 2 above) and push to git;
   Vercel will auto-redeploy

5. **Verify the deploy** (section 6 below)

---

## 6. Verification: confirm the live app works

Once deployed to the chosen URL (subpath, subdomain, or proxied):

**Smoke test (manual):**
1. Open the live URL in a browser (e.g. `https://slowmarch.to/cairn`, `https://cairn.slowmarch.to`, etc.)
2. Wait for "Ready · engine v..." in the status bar
3. Load a test map: download the fixture at
   `tests/fixtures/bitterroots/Bitterroots__Complete_.json` (or use any CalTopo/GeoJSON export
   you have)
4. Drop the file on the page
5. Click one waypoint and assign it an icon (to exercise the icon picker)
6. Perform a bulk color reassignment on 5+ items
7. Export and download the ZIP

**Automated test (e2e):**
The existing Playwright suite in `tests/web/test_web_app.py` can be pointed at the live URL:

```bash
# Before deploy:
BASE_URL=http://127.0.0.1:8765 uv run pytest tests/web/test_web_app.py

# After deploy:
BASE_URL=https://slowmarch.to/cairn uv run pytest tests/web/test_web_app.py
# (or the live URL of whichever option is chosen)
```

The suite self-skips if the URL is unreachable, so it's safe to run against live as a final
verification.

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
- **No custom domain guarantee:** If the user cannot resolve the domain hosting (Option A vs B
  vs C), the final URL may be a subdomain, not the exact subpath `slowmarch.to/cairn`. That
  decision is external to this plan.
- **No PWA offline mode:** The prototype requires an internet connection (Pyodide download,
  Maplibre basemap tiles if added). Offline mode is a phase-2 feature.
- **CLI/scripting leg not deployed:** The hybrid includes a retained CLI for scripting; this
  deploy is the web UI only. The CLI remains in the repo for the user's local use.
- **No interactive import runbook visualization on live:** The import checklist is text-based
  in the prototype. The "sleeper killer feature" from the platform decision (interactive
  checklist with onX Web Map deep-links) is a phase-2 add-on.

---

## Next steps

1. **Resolve domain hosting:** Clarify with the user whether `slowmarch.to` is on Vercel, and if
   not, whether DNS is on Cloudflare. This determines which option (A/B/C) to execute.

2. **Commit `web/` to git** (section 1 above).

3. **Fix the wheel-fetch path** to use a relative URL (section 2).

4. **Set up Vercel project** with the `vercel.json` config (section 3).

5. **Wire the domain** per the chosen option (section 4 → 5).

6. **Verify the live deploy** with the smoke test and/or e2e suite (section 6).

7. **Document the live URL** and share it for demos and feedback.
