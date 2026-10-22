**A dumping ground for ideas, known bugs and functionality I need to implement**

> Consolidated 2026-08-29. Absorbed the live backlog from `cairn/Instructions for agent.md`
> (a Dec 2025 document whose status header said "ALL PHASES COMPLETED / Production ready!"
> and which linked six `docs/*.md` files that no longer exist). Verified findings live in
> `docs/CODEBASE_AUDIT_2026-08-29.md` and `docs/UX_AUDIT_2026-08-29.md`; this file stays a
> dumping ground.

> Reorganized 2026-08-30 around the web app as the primary interface (see `README.md`).

> 2026-10-21: Cairn is now **web-only**. The CLI and TUI were deleted (git tag `cli-final`), and
> with them every item that only concerned them — the CLI-shape list, the whole TUI/styling
> backlog, `--no-interactive`, the duplicated summary output, `set-default-color` help, and
> `core/preview.py` test coverage.

---

## Core engine (used by the web app)

* **2026-10-22 review fixes (areas + runbook).** Fixed and tested
  (`tests/test_polygons_end_to_end.py`, `tests/test_web_bridge_review_fixes.py`): area colours
  quantized to onX's 11-colour track palette (missing/malformed → Blue in UI and KML alike);
  holes written as `<innerBoundaryIs>`; CalTopo `stroke-width`, `stroke-opacity` and
  `fill-opacity` carried; unusable polygons counted as dropped; KML size-split like GPX; area
  names sanitized like waypoints/tracks and every rename listed in RUNBOOK.md; colourless
  waypoints show and export the same colour; the 1,500 warning says "remove", not "split".
  Still open from that pass:
  * **How onX renders KML `<width>` and `PolyStyle` fill is unverified.** Needs one real
    Web Map import of an area with `fill-opacity` 0.1 and 0 to see whether onX honours them.
  * **The KML size cap is assumed.** onX documents 4 MB for GPX; areas now split at the same
    3.75 MiB without a source saying KML shares that limit.
  * **`MultiPolygon` and other non-LineString/Polygon `Shape`s are silently ignored at parse
    time** (`core/parser.py:add_feature_to_folder`), so they never reach the dropped count.
    No CalTopo export seen so far contains one (Bitterroots: 17 single-ring Polygons).
  * **CalTopo `pattern` on areas is not carried** — KML 2.2 has no dash style.
  * **The `! @ # $ % ^ * &` name rule has no cited onX reason** (utils.py says "sorting
    issues"). Verify against a real import, then keep or drop it.
  * `docs/FAQ.md:123` ("Area names are left alone", "the app doesn't tell you") is now stale.

* **`load_config(None)` still reads `cairn_config.yaml` from the current directory**
  (`core/config.py`). The web app is safe because `web/bridge.py:_config` passes an explicit
  path, but the ambient fallback is a trap for any future caller — make the path mandatory, or
  drop the CWD lookup.
* ~~**Cairn ships an icon onX does not accept.**~~ **Fixed 2026-10-22**: cabin/hut/yurt (and CalTopo's `hut` symbol) now map to `Shelter`; `Cabin` is gone from every table and config, and `tests/test_mapper.py::test_every_default_mapping_targets_a_real_onx_icon` guards the vocabulary.
* **Numbered waypoints defeat keyword matching.** `_TOKEN_RE = r"[a-z0-9]+"`
  (`core/icon_resolver.py:35`) merges trailing digits: `Chute1` → `chute1`, which never matches
  the keyword `chute`. `Camp 2` resolves; `Camp2` doesn't. Strip trailing digits before tokenizing.
* **Two dead config entries.** `ICON_COLOR_MAP` and `DEFAULT_KEYWORD_MAP` each define `"Camp"`
  twice (AST-verified); Python keeps the last silently.
* ~~**`<desc>` is a debug dump in every exported waypoint.**~~ **Fixed 2026-08-29.**
  `<desc>` now carries only the user's own note (omitted entirely when there is no note);
  icons/colors/styles still travel in the `<onx:>` extensions. The old key=value block is
  still available from the writers via `description_mode="debug"` (not exposed in the web app). Covered by `tests/test_desc_output.py`.
* ~~**Running the tool wrote into its own installed package.**~~ **Fixed 2026-08-29**: every
  `migrate` run — and every test run — used to append to the version-controlled
  `cairn/data/icon_catalog.yaml`, leaking test fixture names ("Test Waypoint", "JsonWaypoint")
  into shipped data and dirtying the git tree. Recording is now opt-in via `CAIRN_ICON_CATALOG`;
  the data is write-only telemetry that nothing reads back.
* ~~**The import gap.**~~ **Now fully characterised and built.** onX *does* have folders; they
  are created at import time, one per import *batch*, and a batch accepts multiple files of
  mixed format. The folder is named `"Import mm/dd/yy H:MM"` — a timestamp — so no filename or
  metadata Cairn writes can ever set it; the user must rename after import. Verified by reading
  onX's shipped Web Map JS (`multiple:""`, `accept=".gpx,.kml"`,
  `addCollection({name:"Import"+...})`) plus the Zendesk API. The missing artifact — a generated
  RUNBOOK telling the user the batches, the order, and the exact name to type — is now built
  (`web/bridge.py:build_runbook`, shipped in every web export). See
  `docs/FIDELITY_MODEL_2026-08-29.md` and `docs/PLATFORM_CONSTRAINTS_2026-08-29.md`.
* **FIXED (2026-10-21): Multi-line notes were flattened at parse time.** `strip_html` (`cairn/utils/utils.py`) ends
  with `re.sub(r"\s+", " ", text)`, and `cairn/core/parser.py` applies it to every description —
  so line breaks in CalTopo notes are gone before the web app shows them or the writers export
  them (7 of 189 notes in the Bitterroots fixture). `strip_html` now keeps `\n` (br/p/div/li/CRLF -> newline, max one blank line); tests added. Prerequisite for the notes editor below. (Found 2026-10-21.)
* **Investigate: do line breaks / formatting survive into onX notes?** Unknown whether onX keeps
  newlines from GPX `<desc>` (or KML `<description>`), needs HTML, or flattens. Do not assume —
  settle it with a real import test. See `docs/design/DECISIONS.md` round 4 (F12). Probe:
  one GPX with waypoints whose `<desc>` is (A1) literal newlines, (A2) `&#10;` newlines,
  (B) escaped `&lt;br&gt;`, (C) blank line + indented line; import into a fresh onX collection,
  check Notes on web and mobile; then type a two-line note in onX, export it as GPX, and read the
  raw `<desc>`. Optionally repeat as KML `<description>` (plain, CDATA+`<br>`) — Cairn writes no
  KML descriptions today.
* Add a feature to include the CalTopo Folder name in either the Name or Description for all elements.
* Support for polygons/areas at the engine/writer level.
* **Move the unmapped-symbol warning to the START of the process**, not the end. Right now you
  learn which icons failed to map only after the files are already written.
* Investigate line styling in onX.
* Investigate: can onX data be exported, modified, and re-imported so it *updates* the same
  objects rather than creating duplicates? (Skeptical this is possible — worth 30 minutes to
  find out, not more.)

### General / process

* Workflow redesign — `docs/WORKFLOW_REDESIGN_2026-08-29.md` reconciles three design proposals
  against `docs/DECISION_SURFACE_2026-08-29.md`, which measures that the tool makes users walk
  68 waypoints to answer ~24 questions. (Written against the since-deleted TUI's flow; re-check
  what still applies to the web app.)

---

## Web app

Feature backlog from the 2026-10-21 redesign review (`docs/design/DECISIONS.md`, round 4):

* **Multi-line notes editor.** Note cell is a one-line `<input>`; Enter commits, so no line
  breaks can be typed and long notes are truncated. Proposed: click to expand into a textarea
  (UI-13). Needs the engine newline fix above first.
* **Bulk rename and bulk note edit** (UI-17). "More" today only offers use-note-as-name and
  exclude/include. Add Rename… (prefix/suffix, find/replace, with preview) and Change note….
* **Filter / select by onX icon** (F14). Today's filters are search, type, and "needs an icon".
  Mocked as an "onX icon" facet in the sidebar.
* **Folder facets with "All folders" + clear** (F1) — part of the B-layout rebuild.
* **Merge several CalTopo maps into one export** (UI-12). "Load another map" currently resets;
  users read it as "add". Engine has dedup/merge code (`core/merge.py`, `core/dedup.py`) not
  wired into the web app yet.
* **Large folders** (F13): every item renders as a table row and every edit/keystroke rebuilds
  the whole table. Measured 2026-10-21: 1,500 rows 0.21 s load, ~70 ms per filter keystroke;
  5,000 rows 0.69 s / ~190 ms. Fine within onX's 1,500 limit — no pagination now. If it ever
  matters: debounce the filter, re-render only the edited row, lazily build collapsed folders.

The web app's own known-bugs table lives in [`web/README.md`](web/README.md#bugs-this-prototype-exposed)
rather than here, since most of what it's surfaced turned out to be engine bugs (folded into
"Core engine" above). Add new web-only findings there.

