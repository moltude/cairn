# Cairn codebase audit — 2026-08-29

Resuming after ~8 months (last commit Dec 2025). Every claim below was verified by running
something, not by reading alone; the verification command is given with each finding.

**Baseline:** `uv sync --all-extras && uv run pytest` → 609 passed, 2 skipped, 58% coverage,
Python 3.14.6, 83s. ~20,400 LOC across 55 Python files, 62 test files.

Headline: the **conversion core is in good shape** (io/ 86–94%, writers 92%, color_mapper 96%,
normalization 100%, dedup 97%). The problems are all around it — repo hygiene, a false
compatibility claim, and a TUI layer that hides its own failures from you and from the tests.

---

## P0 — Fresh clone is broken

### 1. `.gitignore` excludes 15 GPX fixtures the tests import

`.gitignore:41` has `tests/fixtures/*.gpx`. That pattern hides fixtures that are hard test
dependencies. They exist only on this machine.

Verified by moving them aside and re-running:

```
12 failed, 24 passed
FAILED tests/test_onx_to_caltopo_geojson.py  (7 tests)
FAILED tests/test_cli.py::test_migrate_onx_to_caltopo_happy_path_writes_outputs
FAILED tests/test_cli.py::test_convert_onx_to_caltopo_writes_geojson_and_respects_flags
FAILED tests/test_migrate_aliases.py::test_migrate_caltopo_accepts_gpx_file
FAILED tests/test_onx_gpx_reader.py::test_read_OnX_gpx_reads_onx_extensions_from_fixture
FAILED tests/test_sort_fixtures_generated.py::test_generated_OnX_sort_fixtures_shape_and_order
```

The 15 files, and whether anything imports them:

| Fixture | Used by |
|---|---|
| `onx_export_with_tracks.gpx` | test_cli, test_migrate_aliases, test_onx_to_caltopo_geojson |
| `onx_waypoint_color_test.gpx` | test_onx_gpx_reader |
| `test_sort_{trk,wp}_{az,time}_{random,sequential}*.gpx` (8) | test_sort_fixtures_generated |
| `test_sort_order_{tracks,waypoints}.gpx` (2) | nothing — genuinely orphaned |
| `rattlesnake_test_{tracks,waypoints}.gpx` (2) | nothing — genuinely orphaned |

**Fix:** drop the pattern (done, see Applied below), then `git add tests/fixtures/*.gpx`.
Delete the 4 orphans if you don't want them.

### 2. No CI

`.github/` does not exist. Nothing would have caught #1, #3, or a regression in the 609 tests.
A ~15-line workflow (`uv sync --all-extras && uv run pytest`) on push/PR is the single highest
value change in this document — it is what makes every other finding stay fixed.

### 3. `requires-python = ">=3.9"` is false

`cairn/model.py:119` is `Item = Waypoint | Track | Shape` — a PEP 604 union evaluated at
**runtime** (a module-level alias, so `from __future__ import annotations` doesn't defer it).
`pip install cairn` on 3.9 succeeds and then every import fails.

```
$ uv run --python 3.9 ... python -c "import cairn.model"
  File "cairn/model.py", line 119, in <module>
    Item = Waypoint | Track | Shape
TypeError: unsupported operand type(s) for |: 'type' and 'type'
$ uv run --python 3.10 ... → OK cairn.cli / cairn.model / cairn.tui.app / cairn.commands.migrate_cmd
```

True floor is **3.10**. (Note: all 55 source files compile clean under 3.9 — this is purely a
runtime alias, so a syntax check would not have found it.)

### 4. `uv.lock` is gitignored

`.gitignore:24`. For an application this is backwards — the lockfile is what makes "it works on
my machine" reproducible, and this repo is 8 months stale against a moving dependency set.
Remove the ignore and commit the lock.

---

## P1 — Correctness and portability

### 5. Hardcoded author path in shipped library code

```python
# cairn/core/writers.py:52
with open("/Users/scott/_code/cairn/.cursor/debug.log", "a", encoding="utf-8") as f:
```

Wrapped in `except Exception: pass`, so on anyone else's machine it fails silently forever —
which means the hardcoded path was doubling as an accidental off-switch. It also ships your home
directory layout in the published wheel. Fixed below, opt-in only.

### 6. `datetime.utcnow()` — deprecated, and it lands in output files

3 call sites (`writers.py:49, 437, 840`). Two of them stamp the `<time>` element of generated
GPX. Scheduled for removal; it produced 2,607 deprecation warnings in one suite run. Fixed below.

### 7. Unbounded, ungated debug logging to the user's home directory

`cairn/tui/debug.py:14` — `agent_log()` appends JSON to `~/.cursor/debug.log` with **no enable
flag**. Contrast `DebugLogger` in the same file, which *is* gated on `CAIRN_TUI_DEBUG`.

Evidence it has been running unnoticed: `~/.cursor/debug.log` is **12 MB**, `./.cursor/debug.log`
is **4.3 MB**. The payloads contain file paths and waypoint data.

Only 10 call sites, all leftover instrumentation from a debugging session. **Recommend:**
gate on `CAIRN_TUI_DEBUG` like its neighbor, or delete the call sites. Not applied — you have
uncommitted edits in `cairn/tui/debug.py`.

### 8. XML parsing: *not* vulnerable, and here is the proof

I tested rather than assumed, because "stdlib ElementTree parses untrusted GPX" reads like a
finding and isn't one here.

- **XXE / file disclosure — safe.** `<!ENTITY xxe SYSTEM "file:///etc/passwd">` →
  `ValueError: Invalid GPX file (XML parse error): undefined entity &xxe;`. Python's expat
  binding never resolves external entities.
- **Billion laughs — safe on the Python you run.** A 9-level bomb →
  `limit on input amplification factor (from DTD and entities) breached`, 0.0s, 54 MB RSS.
  libexpat ≥2.4 caps amplification.

The caveat is finding #3: that cap does not exist on the older interpreters `pyproject.toml`
claims to support. Tightening `requires-python` to `>=3.10` is also the security fix here.
Adding `defusedxml` would be redundant on 3.11+.

`writers.py:186` (`minidom.parseString` for pretty-printing) is **your own** generated XML,
not attacker input. It's a memory finding on the 10k-waypoint path — minidom builds a second
full DOM — not a vulnerability. `ET.indent()` (3.9+) does the same job in place.

---

## P2 — Testing quality

609 green tests is a better number than the suite deserves, and the gap is concentrated in one place.

### 9. 35 TUI tests swallow the exception and then assert nothing

91 `except Exception` blocks across `tests/`, all in TUI files; 35 are immediately followed by
`pass` / `continue`. Pattern:

```python
try:
    await pilot.press("enter")
except Exception:
    pass          # test proceeds and passes regardless
```

Concentration: `test_tui_filter_search.py` (19), `test_tui_editing_comprehensive.py` (16),
`tui_harness.py` (15), `test_tui_save_flow_e2e.py` (9).

This is why `d93d7df "Fix hard bug (ended up tab issue) :/"` was hard: the suite could not tell
you the interaction had broken. Highest-leverage remediation is not "fix all 35" — it is to fix
`tui_harness.py`'s 15 first, since every TUI test inherits them.

### 10. Coverage is bimodal — the middle is fine, the edges are unexercised

| Area | Coverage | Read |
|---|---|---|
| `core/normalization.py`, `diagnostics.py`, `tui/models.py`, `tui/widgets.py` | 100% | good |
| `io/*`, `core/writers.py`, `color_mapper.py`, `dedup.py`, `shape_dedup.py` | 86–98% | good |
| `core/preview.py` | **16%** (780/933 missed) | 1946 lines of interactive flow, untested |
| `tui/edit_screens/modals.py` | **17%** | 863 lines |
| `tui/edit_screens/widgets.py` | **13%** | |
| `commands/convert_cmd.py` | **36%** | 1115 lines |
| `ui/interactive.py` | **20%** | live code, reachable from `migrate_cmd` |
| `core/icon_picker.py` | **0%** | live but lazily imported at `preview.py:359,1746` |
| `tui/protocols.py`, `tui/steps/*` | **0%** | dead, see #11 |

`core/preview.py` at 16% is the real gap: it is the largest non-TUI module and it sits directly
in the primary user path. `commands/convert_cmd.py` at 36% matters less — `convert` is registered
`hidden=True` and `Instructions for agent.md` §1a already proposes removing it.

### 11. Dead modules

Verified zero importers and zero string references across `cairn/`, `tests/`, `scripts/`:

- `cairn/tui/protocols.py` — 213 lines, 62 statements, 0%. Protocol definitions nothing implements
  or type-checks against (there's no mypy config either).
- `cairn/tui/steps/` — `__init__.py` + `select_file.py`, 122 lines, 0%. Superseded by
  `tui/app.py` + `tui/file_browser.py`.
- `cairn/utils/debug.py` — 204 lines, 100% "covered", **zero production callers**. Only
  `tests/test_debug_utils.py` imports it. That test is coverage theater: it inflates the number
  while testing nothing anyone runs.

Not dead, despite looking it: **`cairn/ui/` is live** (`interactive.py` ← `core/preview.py`,
`commands/migrate_cmd.py`; `state.py` ← `tui/app.py`). Leave it alone until `preview.py` is
retired, and keep `prompt-toolkit` in the dependency list.

Recommend deleting the three above (≈540 lines, zero functional impact). Not applied — deletions
are your call.

### 12. Smaller test items

- 3 tests contain no assertion at all: `test_config_comprehensive.py::test_remove_user_mapping_from_nonexistent_file`,
  `test_matcher_comprehensive.py::test_avalanche_synonym_matching`,
  `test_normalization_comprehensive.py::test_iso8601_partial_date`. They only assert "doesn't raise."
- 2 skips are disabled regressions, not environment skips:
  `test_tui_filter_search.py:661` ("'c' clear behavior changed") and
  `test_tui_keyboard_shortcuts_comprehensive.py:159` ("Tree widget not available"). Both mark real
  behavior that is now untested.
- No `tests/conftest.py`. 34 of 62 files use `tmp_path`; shared setup is duplicated instead.
- `tests/output/` — 63 committed generated files from `scripts/test_edge_cases.py`, stale since
  December, not read by any test. Delete and gitignore.
- `coverage.xml` (152 KB) is committed; `htmlcov/` is correctly ignored.

---

## P3 — Maintainability

### 13. 280 silently-swallowed exceptions in production code

485 broad `except Exception` blocks; 280 are followed directly by `pass`/`continue`/`...`.

| File | swallowed |
|---|---|
| `tui/app.py` | 134 |
| `tui/edit_screens/overlays.py` | 65 |
| `tui/edit_screens/modals.py` | 40 |
| `tui/tables.py` | 12 |
| everything else | 29 |

**251 of 280 are in the TUI**, and the conversion core is nearly clean (`writers.py` 6,
`config.py` 3, `normalization.py` 3, mostly with logging). So this is one localized habit, not a
codebase-wide one — which makes it fixable. Combined with #9, a TUI bug currently leaves no
trace anywhere: not in a log, not in a test.

Suggested increment, not a refactor: route them through one `_swallow(exc, where)` helper that
`pass`es in normal use and re-raises under `CAIRN_TUI_DEBUG`. Then a failing TUI test can be made
to actually fail.

### 14. `cairn/Instructions for agent.md` is stale and actively misleading

It opens "**Status: ✅ ALL PHASES COMPLETED**… Production ready! Ship it! 🚀" and cites six
`docs/*.md` files — `CLI_UX_TEST_RESULTS.md`, `CLI_UX_ISSUES_AND_FIXES.md`,
`CLI_UX_TESTING_SUMMARY.md`, `CLI_UX_COMPLETION_REPORT.md`, `QA_TEST_RESULTS.md`,
`follow-up-plan-final-qa.md` — **none of which exist** (`docs/` contains only screenshots).

Underneath the stale header is a live 11-item feature backlog (bulk edits, CLI simplification,
default map path, dropping SUMMARY files) that overlaps `TODO.md`. Any agent reading this file
will either chase dead links or believe the project is finished.

**Recommend:** move the live backlog into `TODO.md`, delete the file. Left in place — it's your
document.

### 15. `tui/app.py` is 3698 lines

18% of the codebase in one file, 58% covered, holding 134 of the 280 swallowed exceptions. Not
worth refactoring on its own, but it's the reason #9 and #13 are hard to fix incrementally. If
you do split it, the seams already exist: `state.py`, `tables.py`, `file_browser.py`,
`edit_screens/` are all separate modules that `app.py` orchestrates.

### 16. Minor

- `cairn/commands/__init__.py` re-exports `convert_cmd, config_cmd, migrate_cmd` but omits
  `tui_cmd`, which `cli.py` imports directly. Harmless inconsistency.
- No linter or formatter configured (no ruff/black config, no pre-commit). The `.cursor` rule
  references `uv run ruff` but ruff is not a dependency.
- No type checker configured, which is why `tui/protocols.py` could rot unnoticed.
- `TECH_DETAIILS.md` is misspelled (referenced correctly by that name in README).

---

## Applied in this pass

Three changes, each a factual bug, each verified by re-running the full suite (609 passed,
2 skipped — unchanged; deprecation warnings 2607 → 1):

1. `pyproject.toml` — `requires-python` `>=3.9` → `>=3.10`.
2. `.gitignore` — removed `tests/fixtures/*.gpx` and `uv.lock`; added `tests/output/` and
   `coverage.xml`.
3. `cairn/core/writers.py` —
   - replaced the hardcoded `/Users/scott/...` debug path with `AGENT_DEBUG_LOG_PATH`,
     **defaulting to disabled**. Subtlety worth recording: the hardcoded path was accidentally
     acting as an off-switch — its parent directory doesn't exist on anyone else's machine, so
     the write silently failed. Defaulting to `~/.cursor/debug.log` (which does exist everywhere)
     would have *switched on* unbounded logging for every user across the 8 `_agent_ndjson_log`
     call sites on the GPX export path — i.e. it would have shipped finding #7 rather than fixed
     it. It is now opt-in only.
   - replaced 3 × `datetime.utcnow()` with timezone-aware `datetime.now(timezone.utc)`. Note
     `utcnow().timestamp()` at line 49 was not merely deprecated — it interpreted a naive UTC
     datetime as local time, so that field was wrong by the local UTC offset. Debug-log field
     only, so no user-visible impact; the two `strftime` sites were correct already.

### Since resolved in this session

- `git add tests/fixtures/*.gpx uv.lock` — **done.** 14 fixtures and the lockfile are now tracked
  (the audit said 15; that was an off-by-one from a shell alias header line).
- `git rm --cached coverage.xml` and `git rm -r --cached tests/output` — **done**, files left on disk.
- **CI added** (#2): `.github/workflows/ci.yml` with `test` (5 Python versions × 2 OS),
  `import-floor` (proves the 3.10 claim), `fresh-clone` (fails if a test dependency is ever
  untracked again — the exact bug that shipped), and `build-check`.
- **Dead modules deleted** (#11): `tui/protocols.py`, `tui/steps/`, `utils/debug.py`, and
  `tests/test_debug_utils.py`. Suite 609 → 598 (the 11 deleted coverage-theater tests),
  coverage 58% → 59%.
- **TUI debug logging gated** (#7): `agent_log()` no longer writes to `~/.cursor/debug.log`
  unconditionally; it is opt-in via `CAIRN_DEBUG_LOG`, matching `writers.py`. The stale
  12 MB / 4.3 MB logs can now be deleted.
- **`minidom` → `ET.indent`** in `prettify_xml` (~2x faster, ~10x less peak memory on a
  10k-feature export), pinned by `tests/test_writers_prettify.py` against the old implementation.
- **The 3 assertion-free tests** (#12) now assert measured behavior. One docstring was actively
  wrong: it claimed partial ISO-8601 dates return `None`, but `"2021-01-01"` parses to midnight UTC.
- **Cursor → Claude Code migration**: `.claude/settings.json`, `.claude/README.md`, and the
  `cairn-tests` skill; `.cursor/rules/uv-run-tests.mdc` retired (its advice omitted
  `uv sync --all-extras`, so following it produced 36 collection errors).
- **`cairn/Instructions for agent.md` deleted** (#14), its live backlog folded into `TODO.md`.

### New findings from running the tool end to end

Full detail in `UX_AUDIT_2026-08-29.md` and `TUI_DESIGN_2026-08-29.md`. Code defects found and
their status:

| Finding | Status |
|---|---|
| **CalTopo GPX input documented but unreachable from the CLI.** `parse_caltopo_gpx` had one caller (`tui/app.py:2265`) while `migrate_cmd.py:613` rejected `.gpx`, despite `README.md:59` documenting it. | **Fixed** |
| **Adding `.gpx` made the picker default to the lossy format** — `.gpx` sorts before `.json`, so habitual Enter silently chose GPX over GeoJSON of the same map. Caught in review of the fix above. | **Fixed** (lossless sorts first) |
| **`<desc>` was a debug dump in every export** — `name=`/`id=`/`color=`/`icon=` around the user's note, while `color`/`icon` were already in the `<onx:>` extensions. | **Fixed** — notes only by default, full block behind `--debug` |
| **Running the tool wrote into its own package.** Every run, including every test run, appended to `cairn/data/icon_catalog.yaml`, leaking fixture names into shipped data and dirtying git. Read-only in a real install. | **Fixed** — opt-in via `CAIRN_ICON_CATALOG` |
| **Search box unusable** (one keystroke, then focus stolen). | **Fixed** |
| **`Esc` quit the app after export**; **`Esc` could not close modals** and silently rewound a step per press. | **Fixed** |
| **5.27s per selection toggle** at row 6000 of 10,000 — full table rebuild plus ~12,000 simulated cursor actions, scheduled twice. | **Fixed** — 0.52s, flat |
| **Export silently overwrote existing files.** | **Fixed** — confirmation lists them |
| **`Ctrl+N` discarded all edits with no confirmation**; **Folder-step `Enter` was silently inert.** | **Fixed** |
| **`NO_COLOR` ignored.** Textual has supported it since 0.80.0; `theme.tcss` has 75 hardcoded color literals and zero uses of the `nocolor` pseudoclass. | Open — see `TUI_DESIGN` |
| **`--no-interactive` prompts anyway, then aborts.** Cairn cannot be scripted or run in CI. | Open — highest remaining |
| **"Order confirmed (--yes flag)"** prints for a flag that does not exist, twice, around a summary printed twice. | Open |
| **Success message wraps the output path mid-character.** | Open |
| **`textual>=0.58.0`** claims a never-tested support range. | **Fixed** — `>=6.11,<9` |

## What's left, in order

1. **Fix `--no-interactive`.** It prompts anyway and aborts, so Cairn cannot be scripted or run
   in CI — which also blocks end-to-end coverage of the real migration path. Highest remaining.
2. **Fix `tui_harness.py`'s 15 swallowed exceptions.** Every TUI test inherits them, so a green
   TUI suite is currently weak evidence. This also gates the wizard→workspace work, whose fixed
   step order is held in place by keystroke-order tests rather than by product need.
3. **Publish to PyPI** (`cairn-maps`) — `release.yml` is ready; it needs the pending publisher
   configured and a `v1.0.0` tag. Biggest install-friction win per hour spent.
4. **Route `theme.tcss`'s 75 hardcoded colors through theme tokens** — fixes `NO_COLOR` and the
   TODO's "use color labels to ensure theme migration" in one pass.
5. **Cosmetic CLI output**: the phantom `--yes` message, the doubled summary, the wrapped path.
6. **Bulk edit** (`TUI_DESIGN` §"anchor feature") — the most-requested item, and the reason the
   tool exists. Depends on 2.
7. Then `core/preview.py` tests (16%, 1946 lines) and the exception-swallowing cleanup.
