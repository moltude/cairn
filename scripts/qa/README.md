# scripts/qa: folders UI fuzzer and repro probes

Manual QA tools for the folders feature (UI-31, UI-32, ENG-07). They are not part of the test
suite: pytest only collects `tests/`, and nothing under `tests/` may import from here. The
regression tests for what they found live in `tests/web/test_web_app.py` and
`tests/test_web_bridge_*.py`.

## Setup

```bash
uv sync --all-extras
uv run playwright install chromium        # once per machine
uv run python web/serve.py                # dev server; or point BASE_URL at another one
```

Both tools read `BASE_URL` (default `http://127.0.0.1:8790/`) and run from the repo root.

## fuzz_ui.py

Drives the real Pyodide app in headless Chromium (1440x900) with random actions: ticks, drags
to folders, to "+ New folder" and to nowhere, Esc mid-drag, renames from a pool of hostile
names, Move to..., filters, search, collapse, row name / note / icon edits, exclude / include,
exports. Wave 2 adds human-timed presses that leave a name field, rename-then-drag and
rename-then-export. After every action it checks the invariants (every item exactly once, UI
layout == bridge layout, no empty folder, rail == folders, visible rows == filters, no stuck
drag, overlays in step, no error status, focus kept). Every export is verified: the export
screen, Download all, and every per-folder zip (12 sampled on 200 folders).

Six maps, picked by `seed % 6`: `bitterroots`, `hostile` (34 nasty names, 3 empty folders),
`twins` (case and safe-name twins, a CalTopo folder called "Unorganized", a 150-character
name), `big200` (200 folders), `onx_areas` and `onx_trips` (onX GPX + KML pairs). The generated
ones are built from `tests/hardening_maps.py`.

```bash
# The release run: 12 seeds x 2 waves = 24 sessions, 4 per map, 250 actions each.
uv run python scripts/qa/fuzz_ui.py --seeds 1-12 --actions 250 --wave 1
uv run python scripts/qa/fuzz_ui.py --seeds 1-12 --actions 250 --wave 2

uv run python scripts/qa/fuzz_ui.py --replay archive/qa-fuzz/runs/<record>.json   # replay a failure
uv run python scripts/qa/fuzz_ui.py --seeds 7 --shrink                            # and shrink it
```

One line per session: `ok {...}` or `FAIL <signature>: <detail>`. `--known a,b` counts and steps
over known signatures (a release run uses none). `--maps`, `--tag`, `--verbose` as named.
Generated maps and run records go to `archive/qa-fuzz/` (gitignored), or `--out` /
`CAIRN_QA_OUT`. A "harness" count is a Playwright timeout in the fuzzer itself, stepped over.

## probes/

Small scripts that reproduced one finding each before it was fixed (round 2): `probe1`-`probe3`
a click lost after leaving a name field, `probe4` the merge offer over the export screen,
`probe5` the CalTopo "Unorganized" folder, `probe6` focus after Enter/Esc in a row name,
`probe8` More under Move to..., `probe7` and `probe9` replay a fuzzer record to action N and
instrument the next one:

```bash
uv run python scripts/qa/probes/probe9.py archive/qa-fuzz/runs/<record>.json <N>
```

They print what they see; they don't assert. On the fixed code they show the fixed behaviour.
