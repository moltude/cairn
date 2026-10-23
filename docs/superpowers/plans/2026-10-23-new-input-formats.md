# New Input Formats (KMZ, generic GPX routes, CSV) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open Google Earth / My Maps KMZ files, read generic GPX routes faithfully, and (if approved) open CSV waypoint lists, all through the existing guard → detect → route → reader chain.

**Architecture:** No format-specific branches in the middle. KMZ is an *unwrapping* step in front of `guard_input`, not a reader: it yields KML text that then takes the normal path. The value of KMZ depends on a prerequisite this investigation found: generic KML currently loses all folders and colours, so Task 1 routes it through the folder- and style-aware reader that already exists. GPX route work is fixes inside `onx_gpx.py`. CSV is one new reader producing `ParsedData`.

**Tech Stack:** Python stdlib only (`zipfile`, `csv`, `base64`, `xml.etree`), run in Pyodide 0.29.5; `web/app.js` for the binary file read.

**Spec:** the request of 2026-10-23 (the three-row table: KMZ "strongest candidate", GPX routes "needs checking against real files rather than new code", CSV "if at all"). Investigation findings are in the next section; they are the spec's evidence.

## Findings (investigation, 2026-10-23)

All runs went through the real `web/bridge.py:load_files` on hand-written files that mimic each exporter. **They are synthetic**; Task 0 replaces them with real exports.

| Input | What happens today |
|---|---|
| GPX 1.1 `<rte>` (Gaia-style) | Opens. Becomes one line, `<desc>` kept as notes, elevation kept. Each `<rtept><name>` ("Turn L at junction") is silently dropped. |
| Garmin BaseCamp `<rte>` | Opens, but **the routed shape is lost**: the road-following points live in `<gpxx:RoutePointExtension><gpxx:rpt>`, which nothing reads, so a 5-point route came out as 2 points (a straight line between via points). `<gpxx:DisplayColor>Magenta` ignored, line exported default blue. |
| GPX 1.0 (GPSBabel's default, older tools) | **Refused**: "Cairn found no waypoints, lines or areas". Detection is fine; `onx_gpx.py` only looks in the 1.1 namespace. Affects 1.0 waypoints and tracks too, not just routes. Pinned as refused by `tests/test_web_bridge_input_dispatch.py::test_a_gpx_or_kml_with_nothing_readable_is_refused_by_name` (`old.gpx`). |
| Google My Maps KML (folders, `StyleMap`s) | Opens **flat**: one folder named after the file, every line and area default blue. Generic KML goes to `onx_kml.py`, which ignores `<Folder>` and `styleUrl`. The same file with only its `<name>` changed to "CalTopo Export" goes to `caltopo_kml.py` and comes out with both folders and colours (orange line → onX red, blue pin → blue), because that reader already resolves shared `<Style>`/`<StyleMap>` and walks nested folders. |
| KMZ | Not accepted (`accept=".json,.geojson,.gpx,.kml"`), and could not be: `app.js` reads every file with `f.text()`, which mangles a zip before Python sees it. |
| CSV | Falls to `(UNKNOWN, NOT_A_MAP)` → "This isn't a map file Cairn can read." |
| Excel `.xlsx` | `openpyxl` is **not** in the Pyodide 0.29.5 lockfile (checked `pyodide-lock.json`); only `xlrd` (legacy `.xls`) and `pandas` are. So the brief is right: `.xlsx` would mean vendoring openpyxl + et-xmlfile into `web/dist/` beside the cairn wheel (no CSP change, same `unpackArchive` route). Out of scope here. |

Two side findings that change the plan:
- The icon "why" text in `web/bridge.py:_explain` always says "Your CalTopo symbol …". Once generic KML (Task 1) and CSV (Task 4) use the CalTopo icon rules, that sentence is wrong for them.
- `tests/fixtures/onx_export_with_tracks.kml` is detected **generic** and is paired with an onX-like GPX in the dispatch test (`[("gpx","onx-like"),("kml","generic")]`, line 175). Moving generic KML to another reader must not break that pairing.

## Decisions needed from Scott before Tasks 3–4

1. **Real files (Task 0).** I can't produce real exports from Gaia, Garmin BaseCamp/Connect, Komoot, RideWithGPS, GPSBabel or Google Earth/My Maps. Task 3 is gated on at least BaseCamp + one other; Task 2 on at least one Google Earth and one My Maps KMZ.
2. **CSV at all?** Recommendation: yes, but only after Tasks 1–3 ship, and auto-detect only (no column-mapping UI). A file whose columns can't be recognised gets an error naming the accepted headers. Build the mapping UI only if someone hits that error with a real file.
3. **Route turn-point names** (`<rtept><name>`). Recommendation: drop them, as today, and say so in the FAQ. onX lines carry no per-vertex labels; turning each into a waypoint would bury a route under dozens of "Turn L" pins.

## Global Constraints

- Every XML entry point calls `cairn/io/input_check.py:guard_input` before parsing; KMZ's extracted KML is no exception (AGENTS.md "Known traps").
- No new runtime dependency. stdlib only; anything else would have to be added to `loadPyodide({ packages: [...] })` in `web/app.js` and exist in the 0.29.5 lock.
- Any module `web/bridge.py` newly imports carries the `# Web engine:` header (`tests/test_web_engine_surface.py`).
- Every new fixture under `tests/fixtures/` gets a row in `tests/test_input_check.py:EXPECTED`.
- Errors are one `ValueError` sentence a hiker can read; `humanError` shows only the last line, max 180 chars.
- Hostile fixtures live in `tests/fixtures/attacks/`, never in an "every fixture parses" glob. Zip bombs are built inside the test, not committed.
- Desktop only; no phone layouts or tests (DECISIONS.md ENG-02).
- `uv run pytest ... --no-cov` while iterating; full `uv run pytest` before each merge. Baseline: 1028 passed (dev server up) / 933 passed, 95 skipped.

## Review Focus

1. **A KMZ whose `doc.kml` is a zip bomb or lies about its size in the header** → refused with the size sentence, without decompressing more than 16 MB + 1 byte. (Task 2, `test_kmz_entry_bigger_than_its_header_says_is_stopped_at_the_cap`.)
2. **An onX GPX dropped together with a folder-bearing KML that has no onX ids** → still merged into one folder as today. (Task 1, `test_generic_kml_paired_with_an_onx_gpx_stays_on_the_onx_path`.)
3. **A KMZ with no `doc.kml` but one `.kml` in a subfolder, or with two KMLs** → the rule picks one deterministically, or refuses with a sentence; never silently opens the wrong one. (Task 2, `test_kmz_entry_choice`.)
4. **A CSV from European Excel** (`;` delimiter, decimal comma, UTF-8 BOM) → `;` and BOM handled; decimal comma refused with a sentence rather than reading `46,1` as two columns. (Task 4, `test_csv_semicolon_bom_and_decimal_comma`.)
5. **An `.xlsx` dropped on the page** → "Save it as CSV" sentence, not "isn't a map file". (Task 2, `test_xlsx_is_refused_with_save_as_csv`.)

---

### Task 0: Collect real exports (gate, no code)

**Files:**
- Create: `tests/fixtures/generic_gpx/README.md`, `tests/fixtures/kmz/README.md` (provenance: app, version, date, what was drawn)
- Create: the files themselves, small (a handful of items each)

- [ ] **Step 1:** Scott exports, at minimum: Garmin BaseCamp route GPX; Gaia GPS route GPX; one of Komoot / RideWithGPS / Garmin Connect course GPX; a GPSBabel GPX 1.0 file; a Google Earth Pro KMZ (folders + coloured line + polygon); a Google My Maps KMZ (two layers, custom colours).
- [ ] **Step 2:** Run each through `bridge.load_files` (as in the investigation) and add a "today" row per file to the README. Any file whose behaviour differs from the Findings table becomes a test in Task 1–3 before code changes.
- [ ] **Step 3:** Add every file to `tests/test_input_check.py:EXPECTED` with its current classification; run `uv run pytest tests/test_input_check.py --no-cov`; commit.

### Task 1: Generic KML keeps its folders and colours

**Files:**
- Modify: `web/bridge.py` (`_route`, `_pair`, `load_files`, `_explain`, new `_ROUTE_GENERIC_KML`)
- Test: `tests/test_web_bridge_input_dispatch.py`; new fixture `tests/fixtures/google_earth/my_maps_layers.kml` (the investigation's My Maps file)

**Interfaces:**
- Produces: `_ROUTE_GENERIC_KML = "generic-kml"`, read by `parse_caltopo_kml` (origin `None`, so the CalTopo symbol/keyword icon rules and colour rules apply). Task 2 relies on generic KML text taking this route.
- `_explain(decision, symbol, default_icon="Location", source="CalTopo")`: `source` names whose symbol it is; generic files pass `source=""` and read "The file's symbol “…” …".

Rules this task decides:
- `_route`: KML with dialect `GENERIC` → `_ROUTE_GENERIC_KML`. `CAIRN` and `ONX` KML unchanged (onX reader).
- `_pair` treats `_ROUTE_GENERIC_KML` as a pairing candidate exactly as it treats `_ROUTE_ONX_KML` today. A generic KML that ends up **paired with a GPX** is re-routed to `_ROUTE_ONX_KML` and merged as today; an unpaired one is read by `parse_caltopo_kml`.
- Generic KML with no `<Folder>` gets one folder named after the file (`parse_caltopo_kml`'s existing rule).

- [ ] **Step 1: Failing tests**
  - `test_generic_kml_keeps_folders_and_colours`: load `my_maps_layers.kml`; group names == `{"Camps", "Areas"}`; the line's `color` != default blue `rgba(8,122,255,1)`; the waypoint's `color` == onX blue.
  - `test_generic_kml_paired_with_an_onx_gpx_stays_on_the_onx_path`: the existing line-175 case still yields one folder with counts `(2, 2, 1)`.
  - `test_generic_kml_icon_why_does_not_say_caltopo`: every waypoint `why` in the My Maps load lacks "CalTopo".
- [ ] **Step 2:** `uv run pytest tests/test_web_bridge_input_dispatch.py --no-cov` → the three fail.
- [ ] **Step 3:** Implement the rules above.
- [ ] **Step 4:** Same command → pass; then `uv run pytest tests/test_caltopo_kml_reader.py tests/test_input_check.py tests/test_caltopo_format_parity.py --no-cov` → pass.
- [ ] **Step 5:** README "Known quirks": Google Earth / My Maps KML now keeps folders and line/area colours; their icon images do not map to onX icons (names still do, via keywords). Add a `DECISIONS.md` entry ("generic KML is read by the CalTopo KML reader; paired with an onX GPX, by the onX reader"). Commit.

### Task 2: KMZ (and an `.xlsx` refusal)

**Files:**
- Create: `cairn/io/kmz.py` (`# Web engine:` header)
- Modify: `cairn/io/input_check.py` (`_EXTENSIONS[KML]` gains `".kmz"`), `web/bridge.py` (`load_files` entry shape), `web/app.js` (`handleFiles`, `fileTitle` regex), `web/index.html` (`accept`, drop-sub text "… .gpx, .kml or .kmz")
- Test: `tests/test_kmz.py`, `tests/test_web_bridge_input_dispatch.py`, `tests/web/test_web_app.py`

**Interfaces:**
- Consumes: Task 1's `_ROUTE_GENERIC_KML` (by way of `detect` on the extracted text).
- Produces:
  - `kmz.MAX_KMZ_BYTES = 64 * 1024 * 1024` (the archive; photos inside a KMZ are skipped but still arrive in memory).
  - `kmz.is_zip(data: bytes) -> bool` — starts with `b"PK\x03\x04"`.
  - `kmz.kml_from_kmz(data: bytes, filename: str) -> str` — the KML text, UTF-8 decoded; `ValueError` sentences for every refusal.
  - `load_files` entries are `{"name", "text"}` **or** `{"name", "b64"}`. A `b64` entry is decoded, and if `is_zip`, unwrapped by `kml_from_kmz`; the resulting text then goes through `guard_input → detect → _route` unchanged. The entry's display name and stem stay the `.kmz` filename.

Rules `kml_from_kmz` decides:
- Archive over `MAX_KMZ_BYTES` → refused.
- Entry choice: `doc.kml` at the root; else the only root-level `*.kml`; else the only `*.kml` anywhere; otherwise refused ("… has N KML files and no doc.kml; Cairn can't tell which is the map").
- Read through `zf.open(entry)` in 1 MiB chunks, stopping at `input_check.MAX_XML_INPUT_BYTES + 1`; **never** trust `ZipInfo.file_size`. Over the cap → the same size sentence `guard_input` gives.
- Encrypted entry, `BadZipFile`, a `.kmz` inside a `.kmz`, invalid UTF-8 → one sentence each.
- A zip containing `[Content_Types].xml` and `xl/workbook.xml` → "This is an Excel workbook. Save it as CSV (or export the map from the app as GPX/KML) and open that." (Task 4 makes the CSV half true; until then the sentence omits CSV.)
- All other entries (images, overlays) ignored.

JS side: `handleFiles` reads `await f.arrayBuffer()`, checks the first 4 bytes for `PK\x03\x04`, and sends `{name, b64}` for those, `{name, text}` otherwise (decide by magic, not extension). Base64 is built chunkwise (no single `String.fromCharCode(...bigArray)`).

- [ ] **Step 1: Failing tests** in `tests/test_kmz.py`, archives built with `zipfile` in the test:
  - `test_kmz_doc_kml_is_read`: zip of `doc.kml` (Task 1's My Maps text) + `images/icon-1.png` → `load_files([{"name":"Trip.kmz","b64":...}])` groups `{"Camps","Areas"}`, `filenames == ["Trip.kmz"]`.
  - `test_kmz_entry_choice`: root `doc.kml` wins over `a.kml`; lone `files/x.kml` is used; `a.kml` + `b.kml` without `doc.kml` → `ValueError` matching `"no doc.kml"`.
  - `test_kmz_entry_bigger_than_its_header_says_is_stopped_at_the_cap`: a deflated 20 MB `doc.kml` of spaces → `ValueError` matching `"up to 16 MB"`; also assert the read stopped (monkeypatch the chunk reader to count bytes ≤ 16 MiB + 1 MiB).
  - `test_kmz_with_dtd_is_refused_by_guard`: `doc.kml` = `tests/fixtures/attacks/external_parameter_entity.kml` → the DOCTYPE sentence.
  - `test_kmz_refusals`: not-a-zip `b64`, encrypted entry, nested `.kmz`, latin-1 bytes → each a one-line `ValueError`.
  - `test_xlsx_is_refused_with_save_as_csv`: minimal zip with `[Content_Types].xml` + `xl/workbook.xml` → matches `"Excel workbook"`.
- [ ] **Step 2:** `uv run pytest tests/test_kmz.py --no-cov` → fail (module missing).
- [ ] **Step 3:** Implement `cairn/io/kmz.py` and the `load_files` entry shape.
- [ ] **Step 4:** `uv run pytest tests/test_kmz.py tests/test_web_engine_surface.py tests/test_input_check.py --no-cov` → pass.
- [ ] **Step 5:** JS + HTML changes; add `test_kmz_drop_opens_folders` to `tests/web/test_web_app.py` (drop a generated KMZ, wait for `body[data-engine="ready"]`, assert the two folder names in the rail). Run with the dev server up: `uv run pytest tests/web --no-cov` → pass, including `test_page_boots_under_enforced_csp`.
- [ ] **Step 6:** If Task 0 supplied real KMZs, add them under `tests/fixtures/kmz/` + `EXPECTED` rows (`detect` is run on the extracted text; `test_every_fixture_classifies_as_expected` needs to unwrap `.kmz` via `kml_from_kmz` first). Rebuild the wheel (`uv build --no-sources && cp dist/*.whl web/dist/`). README + FAQ: KMZ accepted; icons/images inside it are not used. Commit.

### Task 3: Generic GPX routes keep their shape and colour

Gated on Task 0's real BaseCamp file; if its structure differs from the Findings, adjust the tests first.

**Files:**
- Modify: `cairn/io/onx_gpx.py` (namespace choice, `read_track_like` route branch, colour), `web/bridge.py` (`_require_items` sentence: drop "GPX 1.1 and" once 1.0 reads)
- Test: `tests/test_onx_gpx_generic_routes.py` (new), `tests/test_web_bridge_input_dispatch.py` (move `old.gpx` out of the refused list)

**Interfaces:**
- Consumes: `cairn.io.caltopo_gpx.GARMIN_DISPLAY_COLORS` (name → `#RRGGBB`). Import it; do not copy the table.
- Produces: no new public names.

Rules:
- Namespace: use the root element's namespace if it is `http://www.topografix.com/GPX/1/0` or `/1/1`; all `gpx:` lookups use it. (GPX 1.0 has no `<extensions>`; onX lookups simply find nothing.)
- Route points: for each `<rtept>`, emit the rtept, then each `gpxx:rpt` (namespace `http://www.garmin.com/xmlschemas/GpxExtensions/v3`) inside its `RoutePointExtension`, in order. Skip an `rpt` equal to the next `rtept`.
- Colour: when there is no onX colour, a `gpxx:DisplayColor` (route or track extension) becomes the track's colour via `GARMIN_DISPLAY_COLORS` (onX nearest-colour rule then applies). `Transparent` → none.
- `<rtept><name>` stays dropped (Decision 3).

- [ ] **Step 1: Failing tests**
  - `test_basecamp_route_keeps_routed_shape`: the investigation's `basecamp.gpx` → one track, 5 coordinates in order `A, rpt1, rpt2, rpt3, B`.
  - `test_basecamp_route_display_color`: same file → item `color` is the onX colour nearest Magenta (not default blue).
  - `test_gpx10_waypoints_tracks_routes_read`: a 1.0 file with one `wpt`, `trk`, `rte` → 1 waypoint, 2 lines.
  - `test_onx_route_unchanged`: `tests/fixtures/onx_real/onx_web_line_solid.gpx` → same item JSON as before the change (snapshot taken in Step 2).
- [ ] **Step 2:** `uv run pytest tests/test_onx_gpx_generic_routes.py --no-cov` → fail.
- [ ] **Step 3:** Implement the rules.
- [ ] **Step 4:** Same + `tests/test_web_bridge_input_dispatch.py tests/test_input_check.py` → pass.
- [ ] **Step 5:** Full `uv run pytest`; pass count = baseline + new tests. FAQ: generic routes import as lines; turn-point names are not kept. Rebuild wheel. Commit.

### Task 4: CSV waypoints (only if Decision 2 is yes)

**Files:**
- Create: `cairn/io/csv_waypoints.py` (`# Web engine:` header)
- Modify: `cairn/io/input_check.py` (kind `CSV = "csv"`, `_EXTENSIONS[CSV] = (".csv", ".txt")`, `detect` branch), `web/bridge.py` (`_EXT`, `_route` → `_ROUTE_CSV`, `_read_one`, `_route`'s not-a-map sentence lists CSV), `web/index.html` (`accept`, drop-sub), `web/app.js` (`fileTitle` regex), Task 2's Excel sentence gains "Save it as CSV"
- Test: `tests/test_csv_waypoints.py`, fixtures `tests/fixtures/csv/` (+ `EXPECTED` rows)

**Interfaces:**
- Produces:
  - `HEADER_ALIASES: dict[str, tuple[str, ...]]` — `lat: (lat, latitude, y)`, `lon: (lon, lng, long, longitude, x)`, `name: (name, title, label)`, `notes: (notes, note, description, desc, comment)`, `symbol: (symbol, sym, icon)`, `color: (color, colour)`, `ele: (ele, elevation, alt, altitude)`. Case-, space- and BOM-insensitive.
  - `looks_like_csv(text: str) -> bool` — first non-blank line, after `csv.Sniffer` picks `,` `;` or tab, contains a `lat` and a `lon` alias. `detect` calls it **only** when the content is not JSON/XML, so it can't steal a map file.
  - `parse_csv_waypoints(text: str, folder_name: str) -> ParsedData` — one folder named after the file; one waypoint feature per row (`title`, `description`, `marker-symbol`, `marker-color`); origin `None` in the bridge, so the CalTopo icon/colour rules apply and `_explain(..., source="")` from Task 1 words the "why".
  - `MAX_CSV_ROWS = 3000` (the "account of up to 3,000 markups" figure `input_check.py`'s size comment already uses).

Refusals (one sentence each): no recognisable lat/lon columns (sentence lists the accepted header names); decimal comma (`46,1` under a `;` delimiter); over `MAX_CSV_ROWS`; zero valid rows. Rows with out-of-range or blank coordinates are skipped and counted; the count is reported in the load's JSON as `"skipped_rows"` and shown by `renderSourceNotice`.

- [ ] **Step 1: Failing tests**: `test_csv_basic_columns`, `test_csv_header_aliases_and_case`, `test_csv_semicolon_bom_and_decimal_comma`, `test_csv_without_lat_lon_names_accepted_headers`, `test_csv_out_of_range_rows_skipped_and_counted`, `test_csv_row_cap`, `test_csv_detect_does_not_claim_json_or_xml`, `test_csv_symbol_column_drives_icon` (`symbol=campground` → `Camp`).
- [ ] **Step 2:** `uv run pytest tests/test_csv_waypoints.py --no-cov` → fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Same + `tests/test_input_check.py tests/test_web_engine_surface.py tests/test_web_bridge_input_dispatch.py` → pass; `tests/web` with the dev server (add `test_csv_drop_opens_waypoints`).
- [ ] **Step 5:** Full suite, wheel rebuild, README/FAQ (CSV columns accepted, no styling beyond icon/colour columns). Commit.

## Not in this plan

- `.xlsx` reading (vendor openpyxl into `web/dist/` if CSV proves popular; ~a few hundred KB more on first load).
- A CSV column-mapping UI.
- Mapping Google Earth icon image URLs (`…/shapes/campground.png`) to onX icons. Cheap follow-up once real KMZs show which hrefs occur: basename → symbol, then a few `icon_mappings.yaml` entries.
- GPX 1.0 for CalTopo (CalTopo writes 1.1).
