# AGENTS.md — Cairn

Instructions for AI agents working in this repo. Human-facing docs are `README.md` (what/why)
and `TECH_DETAIILS.md` (icon/color mapping tables, known quirks — note the typo in the filename).

## Environment: read this first

**`uv run pytest` fails on a cold checkout.** Without a synced venv it falls back to a system
Python and dies with ~36 collection errors (`ModuleNotFoundError: No module named 'yaml'`).
Always run this once per fresh clone / after dependency changes:

```bash
uv sync --all-extras     # dev extras (pytest, pytest-cov) live in [project.optional-dependencies]
```

Then the normal loop works:

```bash
uv run pytest                              # full suite (~85s, 609 pass / 2 skip)
uv run pytest tests/test_writers_tracks.py # single file — preferred while iterating
uv run pytest tests/test_x.py::test_name   # single test
```

Never invoke `pytest` / `python` bare — always `uv run`. See `.cursor/rules/uv-run-tests.mdc`.

`pyproject.toml` sets `addopts = "--cov=cairn --cov-report=term-missing"`, so **every** run prints a
coverage table. On a narrow run that table is meaningless (it reports the whole package as mostly
uncovered). Add `--no-cov` for narrow runs, and only trust coverage numbers from a full-suite run.

Baseline as of 2026-08-29: **650 passed, 2 skipped, Python 3.14.**
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
  preview.py                1946 lines — the non-TUI interactive preview/edit flow
  edit_session.py           edit state shared by both UIs

cairn/commands/           typer subcommands: migrate (primary), convert (hidden/advanced),
                          config, tui
cairn/cli.py              entry point -> `cairn` console script

cairn/ui/                 LEGACY prompt-toolkit interactive UI. Still live — imported by
                          core/preview.py and commands/migrate_cmd.py. Do not assume it's dead.
cairn/tui/                CURRENT Textual UI. app.py is 3698 lines; edit_screens/ holds the
                          modals and overlays.
```

Two UI stacks coexist on purpose (mid-migration). `prompt-toolkit` is still a hard dependency
because of `cairn/ui/`.

## Testing conventions

- TUI tests drive the real Textual app through `tests/tui_harness.py` + textual's `Pilot`.
- Fixtures live in `tests/fixtures/`. `tests/fixtures/bitterroots/Bitterroots__Complete_.json`
  is the canonical large dataset; `tests/fixtures/edge_cases/` covers poles, dateline, unicode,
  malformed input, and 10k-feature stress files.
- **Do not add `try/except Exception` around assertions or key presses in tests.** 35 existing TUI
  tests already swallow exceptions and then assert nothing — they pass unconditionally. Don't add
  to that pile; a flaky interaction should be fixed or `pytest.skip`ped explicitly.
- `tests/output/` holds committed generated output from `scripts/test_edge_cases.py`. It is not
  produced by pytest and is not a fixture. Don't treat it as an expectation baseline.

## Known traps

- **`.gitignore` used to contain `tests/fixtures/*.gpx`**, which hid 14 GPX fixtures that tests
  import — a fresh clone failed 12 tests while the suite passed locally. Fixed and tracked on
  2026-08-29, along with `uv.lock`. The `fresh-clone` CI job now fails if any test dependency is
  ever untracked again, so don't re-add a broad ignore pattern under `tests/`.
- CI lives in `.github/workflows/ci.yml`: `test` (Python 3.10–3.14 on Linux + one macOS cell),
  `import-floor`, `fresh-clone`, `build-check`. `release.yml` publishes to PyPI on a version tag
  via Trusted Publishing. Action refs are pinned to SHAs — note `astral-sh/setup-uv` has **no
  floating `v10` tag**, so it must be pinned by SHA.
- **The distribution is named `cairn-maps`**, not `cairn` — that name is taken on PyPI by an
  unrelated 2019 project. The installed command is still `cairn` via `[project.scripts]`.
  `release.yml`'s tag-guard asserts the git tag matches `pyproject`'s version; PyPI filenames are
  immutable, so a mismatched publish is permanent.
- **Nothing under `cairn/` may write to its own package directory.** `icon_catalog.yaml` used to
  be appended to on every run — dirtying the working tree, leaking test fixture names into shipped
  data, and targeting a path that is read-only in a real install. Recording is now opt-in via
  `CAIRN_ICON_CATALOG`; `tests/test_icon_catalog_optin.py` guards it.
- `pyproject.toml` claims `requires-python = ">=3.9"`. That is false — `cairn/model.py:119` uses a
  PEP 604 union at runtime, so `import cairn` raises `TypeError` on 3.9. The real floor is 3.10.
- Debug logging (`tui/debug.py:agent_log`, `core/writers.py:_agent_ndjson_log`) is **opt-in via
  `CAIRN_DEBUG_LOG`** as of 2026-08-29. It previously wrote to `~/.cursor/debug.log`
  unconditionally and had grown to 12 MB. Don't reintroduce a default path — a path that exists
  on every machine turns the logging back on for everyone.
- The onX format is not fully standard: the same linework exports as `<trk>` or `<rte>`; areas
  usually only survive as KML polygons; onX reorders items after import. See `TECH_DETAIILS.md`.
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
