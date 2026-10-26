---
name: cairn-tests
description: Use when running, debugging, or adding tests in the cairn repo. Covers the uv sync prerequisite, the coverage-flag gotcha, the web e2e suite and its dev server, the fixture set, and the pass-count baseline.
---

# Running and writing cairn's tests

## Before the first run

`uv run pytest` fails on a cold checkout — it falls back to a system Python and dies with
`ModuleNotFoundError: No module named 'yaml'` collection errors. pytest and pytest-cov live in
`[project.optional-dependencies].dev`, which plain `uv sync` does not install.

```bash
uv sync --all-extras
```

Do this once per fresh clone and after any dependency change. Always `uv run` — never bare
`pytest` or `python`.

## Running

```bash
uv run pytest                                          # full suite (~6 min with the web e2e tests)
uv run pytest --no-cov tests/test_writers_tracks.py    # single file
uv run pytest --no-cov tests/test_x.py::test_name      # single test
```

**Pass `--no-cov` on narrow runs.** `pyproject.toml` sets
`addopts = "--cov=cairn --cov-report=term-missing"`, so a narrow run prints a whole-package
coverage table that is noise. Only trust coverage from a full run.

## The web e2e suite

`tests/web/test_web_app.py` drives the Pyodide app in headless Chromium. It needs:

- the dev server: `uv run python web/serve.py` (port 8765), and once per machine
  `uv run playwright install chromium`;
- or `BASE_URL=http://127.0.0.1:<port>/` to point at another server. An explicit `BASE_URL`
  that can't be reached **fails**; an unset one with no server **skips** the web tests.
- Against production use `BASE_URL=https://cairn-five-blue.vercel.app/` (Cloudflare answers
  Python's urllib with 403 on quietmarch.to).

Tests that boot under the enforced CSP can't evaluate page JS; they wait on
`body[data-engine="ready"]`. If you change `cairn/`, rebuild the wheel the page loads
(`uv build --no-sources && cp dist/*.whl web/dist/`) or the e2e tests run the old engine.

## The healthy baseline

The current pass count is in `AGENTS.md` ("Baseline as of …"), with and without the dev
server. A different count means something changed — find out what before continuing.

## Fixtures

- `tests/fixtures/bitterroots/Bitterroots__Complete_.json` — canonical large CalTopo dataset.
- `tests/fixtures/dark_divide_100/` — one real CalTopo map exported as GeoJSON, KML and GPX;
  `PARITY.md` pins every difference.
- `tests/fixtures/onx_real/`, `onx_exports/` — real exports from onX's web app.
- `tests/fixtures/edge_cases/` — poles, dateline, unicode, malformed input, 10k-feature stress.
- `tests/fixtures/attacks/` — hostile XML. Never glob it into "every fixture parses" tests.
- A new fixture must be added to `tests/test_input_check.py`'s `EXPECTED` table.
- Never read a gitignored path from a test (`tests/fixtures/roundtrip/**` data, `archive/`,
  `tests/output/`): the `fresh-clone` CI job fails.

## Writing tests

- **Never wrap an interaction or assertion in `try/except Exception`.** The deleted TUI suite
  had 35 tests that swallowed exceptions and asserted nothing. Fix a flaky interaction or
  `pytest.skip` it with a reason.
- When a byte-pinned baseline must change, change the pin with a dated comment saying why.
  Don't regenerate it silently.
- Give e2e tests descriptive names; no `r1`/`i2` codes.
