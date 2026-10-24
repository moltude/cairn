# AGENTS.md — Cairn

Instructions for AI agents working in this repo.

**Cairn is web-only (since 2026-10), and desktop-only:** mobile is out of scope (`docs/design/DECISIONS.md` ENG-02) — don't add phone layouts or tests.

**Cairn is web-only (since 2026-10).** `web/` is the sole interface; `cairn/` is the conversion
engine it runs in the browser via Pyodide. The typer CLI (`cairn/cli.py`, `cairn/commands/`), the
legacy prompt-toolkit UI (`cairn/ui/`) and the Textual TUI (`cairn/tui/`) were deleted — their
last state is git tag `cli-final`. Do not reintroduce a terminal interface or a typer/rich/
textual dependency. The human-facing doc is `README.md` — what/why,
icon/color mapping tables (`TECH_DETAIILS.md` was merged into it 2026-08-30); onX quirks are in `docs/FAQ.md`.

## Environment: read this first

**`uv run pytest` fails on a cold checkout.** Without a synced venv it falls back to a system
Python and dies with ~36 collection errors (`ModuleNotFoundError: No module named 'yaml'`).
Always run this once per fresh clone / after dependency changes:

```bash
uv sync --all-extras     # dev extras (pytest, pytest-cov) live in [project.optional-dependencies]
```

Then the normal loop works:

```bash
uv run pytest                              # full suite (~2.5min with the web e2e tests)
uv run pytest tests/test_writers_tracks.py # single file — preferred while iterating
uv run pytest tests/test_x.py::test_name   # single test
```

Never invoke `pytest` / `python` bare — always `uv run`. See `.cursor/rules/uv-run-tests.mdc`.

`pyproject.toml` sets `addopts = "--cov=cairn --cov-report=term-missing"`, so **every** run prints a
coverage table. On a narrow run that table is meaningless (it reports the whole package as mostly
uncovered). Add `--no-cov` for narrow runs, and only trust coverage numbers from a full-suite run.

Baseline as of 2026-10-24 (folders release: PR-A stable ids ENG-07, PR-B export screen UI-31, hardening, PR-C folders UI UI-32, round-2, round-3 and round-4 fixes, round-4 edit-screen follow-ups UI-33..35, round-5 QA fixes, cleanup, owner feedback 2026-10-24 UI-36..38, public copy cleanup and sticky top bar): **1357 passed** with the web dev server up; without
it the `tests/web` tests skip. (Copy cleanup and sticky bar took it from 1349. Owner feedback 2026-10-24 added 32; before it 1317. The final batch added one test; before it 1316. The cleanup removed one test of a test-only fallback; before it 1317; before round 5 it was 1301; before the edit-screen follow-ups 1265; before round 4, export screen v2 + instructions.txt, 1258; before the round-3 fixes 1229, before round 2 1179; 2026-10-22 was 892; 2026-10-21 was 568; the
drop from 686 before that was the CLI/TUI test removal.) (`web/bridge.py` writes to `/tmp`, so its tests need that writable.)
If you see a different pass count, something changed — find out what before proceeding.

## Architecture

Everything flows through one canonical in-memory model. Readers normalize into it, writers
render out of it. Add a format by adding a reader/writer pair — do not add format-specific
branches to the middle.

```
cairn/model.py            MapDocument{folders, waypoints, tracks, shapes} + Style
                          `Item = Waypoint | Track | Shape` (PEP 604 alias, line 119)

cairn/io/                 READERS (file -> MapDocument)
  caltopo_geojson.py        CalTopo-flavored GeoJSON: geometry:null folder features,
                            4-element [lon,lat,ele,time] positions, folderId links
  caltopo_gpx.py            CalTopo GPX -> ParsedData: names, multi-line <desc>, Garmin
                            gpxx:DisplayColor (16 names) as stroke, <sym> if present; no
                            folders / waypoint colours / areas in CalTopo's GPX
  caltopo_kml.py            CalTopo KML -> the SAME ParsedData parse_geojson builds (folders,
                            icon href cfg -> marker-symbol/colour, LineStyle/PolyStyle,
                            MultiGeometry, holes). Parity with GeoJSON is pinned by
                            tests/test_caltopo_format_parity.py and dark_divide_100/PARITY.md
  onx_gpx.py                OnX GPX incl. onX extensions + double-escaped entity repair
  onx_kml.py                OnX KML (this is where polygons survive); any non-CalTopo KML
  input_check.py            guard_input (reject DTD / >16 MB XML) + detect(filename, text)
                            -> (kind, dialect) by content sniffing; runs before any reader

cairn/core/
  writers.py                GPX/KML output; auto-splits at DEFAULT_MAX_GPX_BYTES (3.75 MiB)
                            to stay under onX's documented import cap
  color_mapper.py           arbitrary rgba -> nearest of onX's 10 (waypoint) / 11 (track) colors
  icon_registry.py          catalog of valid onX icons  (data: cairn/data/icon_catalog.yaml)
  icon_resolver.py          CalTopo symbol -> onX icon  (data: cairn/data/icon_mappings.yaml)
  mapper.py                 thin map_icon/map_color facade over the two above
  config.py                 cairn_config.yaml load/merge/validate (user symbol_mappings)
  dedup.py / shape_dedup.py / merge.py
                            rotation- and direction-tolerant fuzzy geometry dedup; prefers
                            KML polygons over GPX track representations of the same object
  edit_session.py           edit state (formerly shared by the TUIs; unused by web today)

web/                      THE INTERFACE. index.html + app.js + styles.css; bridge.py is the
                          only Python consumer of cairn/. It ships cairn as a wheel in web/dist/
                          (rebuild: `uv build --no-sources && cp dist/*.whl web/dist/`).
```

Modules web/bridge.py reaches carry a `# Web engine:` header; `tests/test_web_engine_surface.py`
fails if that marking drifts from bridge.py's real import graph. bridge.py routes by
`input_check.detect()`: CalTopo GeoJSON / GPX / KML go to parse_geojson / caltopo_gpx /
caltopo_kml (the CalTopo icon and colour rules); onX, Cairn and generic GPX/KML go to the onX
readers via document_adapter.

## Testing conventions

- Fixtures live in `tests/fixtures/`. `tests/fixtures/bitterroots/Bitterroots__Complete_.json`
  is the canonical large dataset; `tests/fixtures/edge_cases/` covers poles, dateline, unicode,
  malformed input, and 10k-feature stress files.
- **Do not add `try/except Exception` around assertions in tests.** The deleted TUI suite had 35
  tests that swallowed exceptions and asserted nothing. A flaky interaction should be fixed or
  `pytest.skip`ped explicitly.
- `tests/output/` (gitignored) is local scratch: stale edge-case output, review notes,
  screenshots. It is not a fixture, not an expectation baseline, and a tracked doc must not cite
  it as evidence. The folders UI fuzzer and its repro probes are tracked in `scripts/qa/` (how to
  run: its README) and write to `archive/qa-fuzz/`; nothing under `tests/` imports them.
- `tests/web/test_web_app.py` drives the Pyodide web app in headless Chromium (needs the dev
  server: `uv run python web/serve.py`, and once per machine `uv run playwright install
  chromium`). The main fixture context sets `bypass_csp=True` because the page ships a strict
  CSP with no `unsafe-eval`, which blocks Playwright's string-evaluating helpers;
  `test_page_boots_under_enforced_csp` is the one test that boots without the bypass and is the
  only thing standing between a CSP change and a silently broken production boot. `BASE_URL` in
  the environment points the suite at a live deployment (unreachable explicit URL = failure,
  not skip).

## Known traps

- **`.gitignore` used to contain `tests/fixtures/*.gpx`**, which hid 14 GPX fixtures that tests
  import — a fresh clone failed 12 tests while the suite passed locally. Fixed and tracked on
  2026-08-29, along with `uv.lock`. The `fresh-clone` CI job now fails if any test dependency is
  ever untracked again, so don't re-add a broad ignore pattern under `tests/`.
- CI lives in `.github/workflows/ci.yml`: `test` (Python 3.10–3.14 on Linux + one macOS cell),
  `import-floor`, `fresh-clone`, `web-e2e` (Playwright against the Pyodide app under the
  production CSP), `build-check`. `release.yml` publishes to PyPI on a version tag via Trusted
  Publishing. `codeql.yml` scans python/javascript/actions weekly and on PRs;
  `.github/dependabot.yml` bumps uv deps and action SHAs weekly. Action refs are pinned to
  SHAs — note `astral-sh/setup-uv` has **no floating `v10` tag**, so it must be pinned by SHA.
- **The distribution is named `cairn-maps`**, not `cairn` — that name is taken on PyPI by an
  unrelated 2019 project. There is no console script any more (web-only).
  `release.yml`'s tag-guard asserts the git tag matches `pyproject`'s version; PyPI filenames are
  immutable, so a mismatched publish is permanent.
- **Local-only data stays out of git.** Round-trip run payloads (`tests/fixtures/roundtrip/**` GPX/KML/JSON) and anything under `archive/` are gitignored; only findings (README, SUMMARY, verify_report.md) are tracked. Screenshots and captures belong in `archive/` unless a tracked doc embeds them. A test must never read an ignored path -- the `fresh-clone` CI job would fail.
- **Nothing under `cairn/` may write to its own package directory.** `icon_catalog.yaml` used to
  be appended to on every run — dirtying the working tree, leaking test fixture names into shipped
  data, and targeting a path that is read-only in a real install. Recording is now opt-in via
  `CAIRN_ICON_CATALOG`; `tests/test_icon_catalog_optin.py` guards it.
- Debug logging (`core/writers.py:_agent_ndjson_log`) is **opt-in via
  `CAIRN_DEBUG_LOG`** as of 2026-08-29. It previously wrote to `~/.cursor/debug.log`
  unconditionally and had grown to 12 MB. Don't reintroduce a default path — a path that exists
  on every machine turns the logging back on for everyone.
- The onX format is not fully standard: the same linework exports as `<trk>` or `<rte>`; areas
  usually only survive as KML polygons; onX reorders items after import. See
  `docs/FAQ.md` ("Why do my CalTopo lines show up as onX Tracks, not Lines?" and "Why are areas
  in a GPX file, not KML?").
- **The CSP allows jsdelivr only under the pinned Pyodide folder** (`web/vercel.json`,
  e.g. `https://cdn.jsdelivr.net/pyodide/v0.29.5/full/`). A Pyodide bump must change the version
  in `web/index.html` (plus its SRI hash), `web/app.js` `indexURL`, and `web/vercel.json` together;
  `test_csp_cdn_allowance_is_pinned_to_the_pyodide_version_in_use` fails if they drift.
- **A JS object is not keyword arguments to a Python function.** Calling a Pyodide proxy
  of a Python function with `fn(x, { kw: v })` passes the object as the next *positional*
  parameter; use `fn.callKwargs(x, { kw: v })`. (It once made `micropip.install(url,
  { deps: false })` leave `deps=True`, so every boot fetched typer/rich/textual from PyPI.)
  The enforced-CSP e2e test is what caught it; keep that test passing. It also caught an
  inline `<script>` (a since-removed theme-init snippet) that production's CSP silently
  blocked — all JS must live in files under `web/`.
- **Boot has no micropip (since 2026-10-23).** `web/app.js` starts `loadPyodide({ packages:
  ["pyyaml"] })` and the no-cache fetches of the wheel, bridge.py and cairn_config.yaml at
  once, then `unpackArchive`s the wheel into site-packages. The engine's dependencies are
  therefore whatever the Pyodide lockfile provides by name: a new runtime dependency must be
  added to that `packages` list (and exist in the lock), it is never resolved from PyPI.
  `web/index.html` preloads pyodide.asm.wasm / python_stdlib.zip / pyodide-lock.json
  (`as="fetch" crossorigin`, matching Pyodide's CORS `fetch()`) and pyodide.asm.js
  (`modulepreload`, matching its `import()`); a mismatched hint downloads the file twice,
  which `test_pyodide_preloads_are_used_not_fetched_twice` catches.
- **Tests under the enforced CSP can't evaluate page JS** (no `'unsafe-eval'`, so no
  `wait_for_function` / `evaluate`). They wait on `body[data-engine="ready"]`, the DOM twin
  of `window.__cairnReady`. `web/serve.py` must mirror *every* `"/(.*)"` header rule in
  `vercel.json`; until 2026-10-23 it stopped at the first (Cache-Control) one, so the dev
  server and CI ran without any CSP and the enforced-CSP tests proved nothing.
- **XML parsing uses stock `xml.etree.ElementTree`, behind a pre-parse guard.** XML is
  reachable from the web bridge (GPX/KML input, roadmap `docs/ROADMAP_ONX_ROUND_TRIP.md`
  Phase 2: `web/bridge.py:load_files` dispatches every file on `detect()`), so the old "only
  files the user chose, in the CLI" premise is gone. What protects it now, in order:
  1. `cairn/io/input_check.py:guard_input`, called on every file first thing in
     `web/bridge.py:load_files` (`load_document` is its one-file wrapper),
     rejects any XML whose prolog declares a DTD (`<!DOCTYPE`, and so any `<!ENTITY`) and any
     XML over 16 MB, with a one-sentence `ValueError` the UI shows as-is. No exporter of
     interest (onX, CalTopo, Google Earth, Cairn) emits a DTD. The scan is prolog-only on
     purpose: pasted HTML in CDATA notes must not trip it, and a fake tag inside a comment must
     not end the scan early. JSON input is not size-capped (pre-existing path, no amplification).
  2. Behind it, expat >= 2.4's amplification limit (Pyodide 0.29.5 bundles 2.6.4) and
     ElementTree's refusal to resolve external entities, both verified in KG section 4.
  Every new XML entry point must call `guard_input` before parsing -- don't add a reader path
  that skips it. `defusedxml` was evaluated twice (2026-08-30, 2026-10-22) and not adopted:
  runtime install is blocked by the production CSP, so it would have to be vendored into
  `web/dist/`; the guard gives the same fail-fast behaviour without the dependency. Hostile
  fixtures live in `tests/fixtures/attacks/` (never glob them into "every fixture parses"
  tests), and `tests/test_input_check.py` pins both the guard and `detect()`'s classification
  of every file under `tests/fixtures/` -- a new fixture must be added to its `EXPECTED` table.
- **A subagent-built feature with no commits has no history.** `web/` was built by a subagent via
  Bash/heredoc rather than tracked `Edit`/`Write` calls, across an uncommitted session spanning
  roughly two days (built 2026-08-29, first committed 2026-08-30 as `9c4e14a`). A later session
  needing to know what changed and why had nothing to diff against — no git history, no
  recoverable tool-call trail, only the final file. Commit working prototype code early and often,
  even before it's "done" — an ugly commit history beats an unrecoverable one.

## Scope discipline

`TODO.md` is an idea dump, not a work queue — it says so at the top. (`cairn/Instructions for
agent.md`, a stale Dec 2025 status doc citing six `docs/*.md` files that no longer existed, was
deleted on 2026-08-29 and its live backlog folded into `TODO.md`.)

Current findings, all verified by running the tool:
- `docs/CODEBASE_AUDIT_2026-08-29.md` — code health, dead code, testing gaps
- `docs/UX_AUDIT_2026-08-29.md` — what the project is for, and what using it is actually like
- `docs/DISTRIBUTION_2026-08-29.md` — packaging and install friction (note: the PyPI name
  `cairn` is already taken by an unrelated project)
