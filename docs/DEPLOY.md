# How Cairn is deployed

The site is static: `web/` is served as-is, and the browser runs the engine (a wheel in
`web/dist/`) under Pyodide. There is no server-side code.

## The pieces

- **Vercel project `cairn`**, Root Directory `web/`, production alias
  `https://cairn-five-blue.vercel.app/`. A merge to `main` deploys it. Headers (the CSP and
  `Cache-Control: no-cache` on every file, DECISIONS ENG-01 and ENG-03) live in
  `web/vercel.json`; `web/serve.py` mirrors every `"/(.*)"` header rule so the dev server
  matches production.
- **Cloudflare Worker `cairn`** (`web/cloudflare-worker/proxy.js`) on the `quietmarch.to` zone,
  bound to two Routes: `quietmarch.to/cairn` and `quietmarch.to/cairn/*`. It redirects bare
  `/cairn` to `/cairn/` (temporary, so relative asset paths resolve), strips the prefix,
  fetches from the Vercel alias, and rewrites any 3xx `Location` back under `/cairn`. The
  blog itself is a separate Cloudflare Pages project; the Worker Routes take precedence over
  it. Worker changes are deployed by hand (paste into the dashboard's Quick Edit, or
  `wrangler deploy`), not by a merge.

## Shipping an engine change

When anything under `cairn/` changes, rebuild the wheel and commit it with the change:

```bash
uv build --no-sources && cp dist/*.whl web/dist/
```

The filename stays `cairn_maps-1.0.0-py3-none-any.whl`. Every file is served `no-cache`, so
browsers revalidate and the wheel, `bridge.py` and `app.js` always arrive as a matching set.

A Pyodide bump changes `web/index.html` (and its SRI hash), `web/app.js` `indexURL` and the
CSP in `web/vercel.json` together; see AGENTS.md "Known traps".

## Checking a deploy

Run the e2e suite against the Vercel alias, not quietmarch.to (Cloudflare answers Python's
urllib with 403). The trailing slash matters:

```bash
BASE_URL=https://cairn-five-blue.vercel.app/ uv run pytest --no-cov -p no:cacheprovider tests/web/test_web_app.py
```

An explicit `BASE_URL` that can't be reached fails the run rather than skipping it. Then open
quietmarch.to/cairn, `/cairn/faq` and `/cairn/walkthrough` in a browser.

## Rolling back

Promote the previous deployment in the Vercel dashboard, or revert the merge on `main`.

The original 2026-08-30 deployment plan, with the reasoning behind the Worker approach, is in
git history: `git show cdd25f3:docs/VERCEL_DEPLOY_PLAN_2026-08-30.md`.
