# TUI regression workflow (headless + artifacts)

This repo includes a Textual TUI (`cairn tui`) and automated regression tests that drive it **headlessly**
via Textual's `App.run_test()` / `Pilot`.

The goal is to validate key navigation + behaviors **without manually stepping through the UI**, and to
optionally emit **reviewable artifacts** you can skim/diff when something changes.

## Canonical dataset

The TUI regression suite uses the committed fixture:

- `tests/fixtures/bitterroots/Bitterroots__Complete_.json`

Tests copy it into `tmp_path` before running so the fixture cannot be mutated.

## Run the tests

From repo root:

```bash
uv run --with pytest pytest -q tests/test_tui_*.py
```

## Enable artifacts (recommended when iterating on the TUI)

Artifacts are written under `artifacts/tui/<scenario>/` and ignored by git.

```bash
CAIRN_TUI_ARTIFACTS=1 uv run --with pytest pytest -q tests/test_tui_*.py
```

Each scenario directory contains:
- `index.md` (snapshot list)
- `000_<label>.json`, `001_<label>.json`, ... (step snapshots)

## What’s covered

- Stepper path: `List_data → Folder → Routes → Waypoints → Preview → Save`
- Back navigation and “Enter not swallowed” behavior
- Selection toggles in tables (Space)
- Real export to a temp output directory (assert output files + manifest)
- Negative export case when output path cannot be created

### TUI regression suite (headless, automated)

This repo includes automated regression tests for the Textual TUI in `cairn/tui/app.py`.

The goal is to **exercise the main stepper flow + key interaction branches** without requiring you to manually step through the TUI.

### What it tests

- **Stepper navigation**: `List_data → Folder → Routes → Waypoints → Preview → Save`
- **Filter/search behavior** (`/` focuses the search input)
- **Selection toggling**:
  - Space toggles selection when a table is focused
  - Space does *not* toggle selection when an Input is focused
- **Real export**: writes OnX-ready output files into a pytest temp directory and asserts:
  - non-empty export manifest
  - output directory exists
  - at least one non-empty `.gpx` was produced
- **Negative export**: exporting to a path that is a file should show a clear error

### Canonical dataset (protected fixture)

The TUI scenarios use the committed fixture:

- `tests/fixtures/bitterroots/Bitterroots__Complete_.json`

Tests operate on a **temp copy** of this file (`tmp_path`) so the fixture can’t be mutated.

### How to run

- **Run only TUI tests**:

```bash
uv run --with pytest pytest -q tests/test_tui_*.py
```

- **Run TUI tests and emit artifacts**:

```bash
CAIRN_TUI_ARTIFACTS=1 uv run --with pytest pytest -q tests/test_tui_*.py
```

Artifacts are written to:

- `artifacts/tui/<scenario>/`

Each scenario includes a small `index.md` and JSON snapshots of key steps (with table samples capped for size).
