# Claude Code configuration

This project uses **Claude Code** as its default coding agent (migrated from Cursor,
2026-08-29).

| File | Purpose |
|---|---|
| `../AGENTS.md` | Auto-loaded project context: environment setup, architecture, traps |
| `skills/cairn-tests/SKILL.md` | How to run, debug, and write tests here |
| `settings.json` | Permission allowlist for common read-only + `uv` commands |

## What moved from Cursor

- `.cursor/rules/uv-run-tests.mdc` → folded into `AGENTS.md` and the `cairn-tests` skill.
  The old rule was retired rather than converted: it said "just use `uv run pytest`", omitting
  the `uv sync --all-extras` prerequisite, so following it produced 36 collection errors.
- `.cursor/docs/*.md` — 12 planning/status documents from Dec 2025 Cursor sessions. Left on
  disk (the whole `.cursor/` directory is gitignored) but no longer referenced by anything.
  They describe work that is done, abandoned, or superseded; treat them as archive, not spec.
- Debug logging no longer writes to `~/.cursor/debug.log`. It is opt-in via `CAIRN_DEBUG_LOG`.

## Conventions

- Always `uv run` — never bare `python` or `pytest`.
- `uv sync --all-extras` before the first test run in a fresh clone.
- Baseline: 650 passed, 2 skipped. A different number means something changed.
