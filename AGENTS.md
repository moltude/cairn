# AGENTS.md — Cairn

Instructions for AI agents working in this repo.

**Cairn is web-only (since 2026-10), and desktop-only:** mobile is out of scope (`docs/design/DECISIONS.md` ENG-02) — don't add phone layouts or tests.

**Cairn is web-only (since 2026-10).** `web/` is the sole interface; `cairn/` is the conversion
engine it runs in the browser via Pyodide. The typer CLI (`cairn/cli.py`, `cairn/commands/`), the
legacy prompt-toolkit UI (`cairn/ui/`) and the Textual TUI (`cairn/tui/`) were deleted — their
last state is git tag `cli-final`. Do not reintroduce a terminal interface or a typer/rich/
textual dependency. The human-facing doc is `README.md` — what/why,
icon/color mapping tables, known quirks (`TECH_DETAIILS.md` was merged into it 2026-08-30).

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

Baseline as of 2026-10-21: **560 passed, Python 3.15** with the web dev server up; without it
the 49 `tests/web` tests skip, giving **511 passed, 49 skipped**. The drop from 686 is the
CLI/TUI test removal. (`web/bridge.py` writes to `/tmp`, so its tests need that writable.)
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
  caltopo_gpx.py            CalTopo GPX (coordinates + names only — no icons/colors/folders)
  onx_gpx.py                OnX GPX incl. onX extensions + double-escaped entity repair
  onx_kml.py                OnX KML (this is where polygons survive)

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
fails if that marking drifts from bridge.py's real import graph. Everything else in cairn/ (onX
readers, caltopo_gpx, dedup/merge) is engine code not yet wired into the web app.

## Testing conventions

- Fixtures live in `tests/fixtures/`. `tests/fixtures/bitterroots/Bitterroots__Complete_.json`
  is the canonical large dataset; `tests/fixtures/edge_cases/` covers poles, dateline, unicode,
  malformed input, and 10k-feature stress files.
- **Do not add `try/except Exception` around assertions in tests.** The deleted TUI suite had 35
  tests that swallowed exceptions and asserted nothing. A flaky interaction should be fixed or
  `pytest.skip`ped explicitly.
- `tests/output/` (gitignored) holds stale generated output from an edge-case runner script that
  has since been deleted. Nothing produces it any more, it is not a fixture, and it is not an
  expectation baseline.
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
  `README.md`'s "Known quirks" section.
- **A JS object is not keyword arguments to a Python function.** In `web/app.js`,
  `micropip.install(url, { deps: false })` silently passed the object as the second
  *positional* parameter (`keep_going`), leaving `deps=True` — every boot fetched
  typer/rich/textual from PyPI. Pyodide requires `fn.callKwargs(args, { kw: v })` for kwargs.
  The enforced-CSP e2e test is what caught it; keep that test passing. It also caught an
  inline `<script>` (a since-removed theme-init snippet) that production's CSP silently
  blocked — all JS must live in files under `web/`.
- **XML parsing uses stock `xml.etree.ElementTree`, deliberately.** The XML readers aren't
  reachable from the web app at all (the web app is JSON/GeoJSON-only — `web/bridge.py` imports
  just `parse_geojson`). Stock ElementTree doesn't resolve external entities (no classic XXE)
  and modern expat caps entity amplification, so `defusedxml` was evaluated (2026-08-30) and
  skipped as a dependency not worth its cost. Revisit only if XML parsing ever becomes reachable
  from the web bridge.
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
