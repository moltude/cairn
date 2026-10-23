# Input Formats by Standard — Index and Shared Harness

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read KMZ and generic GPX (routes included) according to each format's published schema, so that a file from any conforming exporter (Gaia, AllTrails, Garmin, Google Earth, Komoot, …) works without testing each app separately.

**Architecture:** One hand-built **conformance fixture** per schema. It exercises every element that schema defines and that Cairn has a use for, and is **validated against the vendored XSD in the test suite**, so "it follows the standard" is checked by a machine, not asserted. Each reader is then specified as a table: schema element → what Cairn does with it (kept / mapped / ignored-and-documented). Exporter quirks that break the spec go in separate **tolerance fixtures**, never in the conformance ones.

**Tech Stack:** Python stdlib in Pyodide 0.29.5 at runtime; `lxml` as a **dev-only** extra, used only for XSD validation in tests.

**Spec:** the request of 2026-10-23: "rely on standard prescribed implementations that are generalizable and not tied to specific implementations"; test individual apps only where a standard leaves no choice.

This file holds the standards survey, the decisions, and the shared tasks S1–S2. The format work is in two plans that can run independently once S1–S2 are merged:

| Plan | Standard(s) | Depends on |
|---|---|---|
| [`2026-10-23-kml-kmz.md`](2026-10-23-kml-kmz.md) | OGC KML 2.2 (07-147r2) / 2.3 (12-007r2), Google `gx:` extensions 2.2, Google's KMZ rules | S1, S2 |
| [`2026-10-23-gpx.md`](2026-10-23-gpx.md) | GPX 1.0, GPX 1.1, Garmin GpxExtensions v3, Topografix gpx_style 0/2 | S1, S2 |

Recommended order: KML/KMZ, then GPX.

CSV was dropped from scope on 2026-10-23 (no geospatial CSV standard exists, and it carries no styling). The research for it is kept in the survey table below in case it returns.

## Standards survey (2026-10-23)

| Format | Normative source | What it settles for Cairn |
|---|---|---|
| GPX 1.1 | https://www.topografix.com/GPX/1/1/gpx.xsd | Namespace `http://www.topografix.com/GPX/1/1`. `wpt`/`rtept`/`trkpt` share `wptType`: `ele, time, …, name, cmt, desc, src, link*, sym, type, …, extensions`. `desc` is "intended for the user, not the GPS"; `cmt` is "sent to GPS as comment". `sym` = "exact spelling of the symbol as displayed on the GPS". `rte` = `name, cmt, desc, src, link*, number, type, extensions, rtept*`. `trk` has `trkseg*`; a segment is a run of points "logically connected in order", split where reception was lost. `extensions` = `xsd:any ##other lax`. lat ∈ [-90, 90], lon ∈ [-180, 180). |
| GPX 1.0 | https://www.topografix.com/GPX/1/0/gpx.xsd | Namespace `…/GPX/1/0`. Same element names except `url`/`urlname` instead of `link`. **No `<extensions>` element**: foreign-namespace elements sit directly at the end of `wpt`/`rtept`/`trkpt`/`gpx`, and after `number` in `rte`/`trk`. Not allowed in `trkseg`. |
| Garmin GpxExtensions v3 | https://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd | Namespace `http://www.garmin.com/xmlschemas/GpxExtensions/v3`. `RouteExtension(IsAutoNamed, DisplayColor?)`, `RoutePointExtension(Subclass?, rpt*)` where `rpt` carries `lat`/`lon` (the routed shape between via points), `TrackExtension(DisplayColor?)`, `WaypointExtension(Proximity, …, DisplayMode, Categories, Address, PhoneNumber)`. `DisplayColor_t` = 16 colours + `Transparent` (already in `cairn/io/caltopo_gpx.py:GARMIN_DISPLAY_COLORS`). The de-facto extension most GPX writers use. |
| gpx_style 0/2 | https://www.topografix.com/GPX/gpx_style/0/2/gpx_style.xsd | Namespace `http://www.topografix.com/GPX/gpx_style/0/2`. `line(color?, opacity?, width?, pattern?, …)`; `color` is 3-octet hexBinary (`FF0000`, no `#`); `opacity` 0–1; `width` in **millimetres**; `pattern` a free string. The XSD does not say where `line` sits; in practice it is in `trk`/`rte` `<extensions>`. |
| KML 2.2 / 2.3 | OGC 07-147r2; OGC 12-007r2 (https://docs.ogc.org/is/12-007r2/12-007r2.html) | 2.3 keeps the 2.2 namespace `http://www.opengis.net/kml/2.2` and adopts `Track`/`MultiTrack` into it. Colours are `aabbggrr`. `styleUrl` is `#id` (same file) or `file.kml#id` (external). `StyleMap` → `Pair(key normal\|highlight, styleUrl \| Style)`. Shared styles live in `Document`; an inline `Style` overrides a shared one. Geometry: `Point, LineString, LinearRing, Polygon, MultiGeometry, Model, gx:Track, gx:MultiTrack`. |
| Google `gx:` 2.2 | https://developers.google.com/kml/documentation/kmlreference | Namespace `http://www.google.com/kml/ext/2.2`. `gx:Track` = parallel lists of `when` and `gx:coord` ("lon lat alt", **space**-separated), equal counts required; `gx:MultiTrack` holds `gx:Track`s. "Unsupported extensions should be ignored". |
| KMZ | https://developers.google.com/kml/documentation/kmzarchives | A zip. Google Earth reads "the first .kml file" it finds; `doc.kml` at the root is the convention. With several `.kml` files "you cannot be sure which one will be found first". Relative references resolve against the root KML. |
| CSV (out of scope) | RFC 4180; GPSBabel unicsv (https://www.gpsbabel.org/htmldoc-development/fmt_unicsv.html) | **There is no geospatial CSV standard.** RFC 4180 fixes quoting/structure only. The most widely used column vocabulary is GPSBabel's `unicsv`: `lat`/`y`/`y_pos`, `lon`/`x`/`x_pos` (fuller spellings like `latitude`/`longitude` accepted; spaces for underscores), `name`, `desc`, `notes`/`comment`, `icon`/`symb`, `ele`/`alt`/`height`/`z`, hemisphere columns `n/s` and `e/w`; tab-separated if the header has a tab, else comma. GDAL's CSV driver handles BOM and `;`/tab separators and treats a column named `WKT` as geometry, but its X/Y name lists are opt-in with no defaults, so it is not a naming standard. Neither source covers decimal commas. |
| Excel `.xlsx` | — | `openpyxl` is not in the Pyodide 0.29.5 lock (`xlrd`, which reads `.xls` only, is). Refused with a sentence (kml-kmz Task 2). Out of scope. |

## What the readers do today vs the standards

Checked by running `web/bridge.py:load_files` on synthetic files and reading the code.

- **Generic KML** goes to `cairn/io/onx_kml.py`, which ignores `Folder`, `Style`, `StyleMap` and `styleUrl`, so files open flat and default blue. `cairn/io/caltopo_kml.py` already resolves shared styles and walks nested folders, and it is namespace-agnostic (`_ln` drops the namespace). Its own gaps against the spec: a `Pair` holding an inline `<Style>`; `gx:Track`/`gx:MultiTrack`; a standalone `LinearRing`. (`kml-kmz.md`)
- **Generic GPX** goes to `cairn/io/onx_gpx.py`. Against the XSDs it: reads 1.1 only (1.0 is refused as empty); never reads `<sym>` (`cairn/io/document_adapter.py:77` hard-codes `marker-symbol: ""`, the biggest icon gap); never falls back from `desc` to `cmt`; drops `gpxx:rpt`; ignores `gpxx:DisplayColor` and `gpx_style:line`; joins `trkseg`s into one line. (`gpx.md`)
- **The icon explanation** (`web/bridge.py:_explain`) says "Your CalTopo symbol …" for every non-onX file. (S2)
- **CSV** is refused as not a map, and stays that way.

## Decisions for Scott

Real exports: answered, none available. Plans are standards-first; an app-specific test is added only when a real file contradicts a standard.

1. **`<rtept>` names/symbols** (turn points). Recommendation: drop, document. onX lines have no per-vertex labels.
2. **`trkseg` gaps.** The spec says segments mark lost reception. Recommendation: keep joining them into one line (onX lines are single LineStrings, and a separate line per GPS dropout would clutter the map), and document it.

## Global Constraints (all four plans)

- Every XML entry point calls `cairn/io/input_check.py:guard_input` before parsing (AGENTS.md "Known traps").
- No new **runtime** dependency. `lxml` is added to `[project.optional-dependencies].dev` only and is never imported under `cairn/` or `web/`.
- Any module `web/bridge.py` newly imports carries the `# Web engine:` header (`tests/test_web_engine_surface.py`).
- Every new file under `tests/fixtures/` gets a row in `tests/test_input_check.py:EXPECTED`.
- Conformance fixtures must validate against their XSD. Tolerance fixtures (spec-breaking on purpose) live in `tests/fixtures/standards/tolerance/` and are excluded from validation.
- User-facing errors are one `ValueError` sentence (`humanError` shows the last line, ≤180 chars).
- Desktop only (DECISIONS.md ENG-02). `uv run` always; `--no-cov` for narrow runs; full `uv run pytest` before merge (baseline 1028 passed with the dev server up / 933 + 95 skipped without).

## Review Focus

1. **A conformance fixture that only validates because the extension XSD wasn't loaded.** `xsd:any processContents="lax"` skips unknown namespaces, so Garmin/gpx_style elements are checked only if their XSDs are in the validation set. (S1 `test_extension_elements_are_actually_validated`.)
2. **A file that uses an older KML namespace (`http://earth.google.com/kml/2.1`)** → read the same as 2.2. (kml-kmz Task 1.)
3. **An exporter that writes `-121.5, 46.1` (space after the comma) in `<coordinates>`** → points kept, not silently dropped. (kml-kmz Task 1 tolerance test.)
4. **A GPX whose `<sym>` is a Garmin name with a comma (`Flag, Blue`)** → resolved, or flagged for attention; never a crash or a wrong icon. (gpx Task 2.)
5. **An `.xlsx` or a `.kmz` holding two KMLs** → a one-sentence refusal. (kml-kmz Task 2.)

---

### Task S1: Vendored schemas and the conformance harness

**Files:**
- Create: `tests/schemas/` holding `gpx10.xsd`, `gpx11.xsd`, `GpxExtensionsv3.xsd`, `gpx_style_0_2.xsd`, `ogckml22.xsd`, `atom-author-link.xsd`, `xAL.xsd`, `kml22gx.xsd`, and `README.md` listing each file's source URL and fetch date. `schemaLocation` imports are rewritten to local relative paths, and the README records that edit.
- Create: `tests/fixtures/standards/README.md` (one row per fixture: the schema, and which elements it exercises)
- Create: `tests/test_standards_conformance.py`
- Modify: `pyproject.toml` (`lxml>=5` in `dev`), `uv.lock`

**Interfaces:**
- Produces: `CONFORMANCE: dict[str, list[str]]` in `tests/test_standards_conformance.py`, mapping fixture path (relative to `tests/fixtures/standards/`) → XSD filenames to load together. The format plans add their fixtures to it.

- [ ] **Step 1: Fetch and vendor the XSDs**; rewrite imports to local paths; note the edits in the README.
- [ ] **Step 2: Write the tests**
  - `test_conformance_fixture_validates[<fixture>]` (parametrized over `CONFORMANCE`): `lxml.etree.XMLSchema` built from the listed XSDs (a small wrapper XSD importing several namespaces when there is more than one) → `schema.assertValid(doc)`.
  - `test_every_standards_fixture_is_listed`: every file under `tests/fixtures/standards/` except `tolerance/` and `README.md` is a key of `CONFORMANCE`.
  - `test_extension_elements_are_actually_validated`: a copy of a GPX 1.1 string with `<gpxx:DisplayColor>Mauve</gpxx:DisplayColor>`, validated against gpx11 + GpxExtensionsv3, raises `DocumentInvalid` (proves the lax wildcard isn't hiding extension errors).
- [ ] **Step 3:** `uv sync --all-extras && uv run pytest tests/test_standards_conformance.py --no-cov`. With an empty `CONFORMANCE`, the third test passes and the parametrized one collects zero cases.
- [ ] **Step 4:** Commit (`test: vendored GPX/KML schemas and conformance harness`).

### Task S2: Neutral icon explanations for non-CalTopo files

**Files:**
- Modify: `web/bridge.py` (`_explain`, its callers in `_item`)
- Test: `tests/test_web_bridge_input_dispatch.py`

**Interfaces:**
- Produces: `_explain(decision, symbol: str, default_icon: str = "Location", source: str = "CalTopo") -> str`. `source=""` gives neutral wording ("The file's symbol “X” maps to this icon."; "No icon was set and nothing in the name matched."). `_item` passes `source="CalTopo"` only for sources whose dialect is `caltopo`. That means `load_files` keeps each source's dialect next to its origin in `sources`, as a third tuple element.

- [ ] **Step 1: Failing test** `test_non_caltopo_icon_why_does_not_say_caltopo`: load a generic GPX (`<wpt>` named "Spot", no sym) → its `why` contains no "CalTopo"; the CalTopo synthetic GPX's `why` still does.
- [ ] **Step 2:** Run `uv run pytest tests/test_web_bridge_input_dispatch.py --no-cov` → fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Same command plus `tests/test_web_bridge_review_fixes.py` → pass.
- [ ] **Step 5:** Commit.

## Not in these plans

CSV and `.xlsx` input; external `styleUrl` resolution; KML `NetworkLink`, `GroundOverlay`, `Model`, `ScreenOverlay` (ignored, as the gx reference says unsupported elements should be); icon images inside KMZ.
