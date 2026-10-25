# GPX and KML as input to the web app — research, 2026-10-22

> **Archived references (2026-10-25).** The `docs/*_2026-08-29.md` and `docs/ROADMAP_ONX_ROUND_TRIP.md` files
> cited below are no longer tracked; read them with `git show cdd25f3:docs/<name>`.

What it would take for the web app to accept **GPX and KML** (today: CalTopo GeoJSON only) from
two sources: **(A) CalTopo's GPX/KML exports** and **(B) onX Backcountry's GPX/KML exports**. (B)
is what an onX → Cairn → onX cleanup round trip needs.

All engine numbers are pinned to **HEAD `174f146`**, extracted with `git archive` into a scratch
snapshot. Other agents are editing `cairn/core/writers.py`, `web/bridge.py`,
`cairn/io/onx_kml.py` and `cairn/core/parser.py` in the working tree right now. Their diff adds
`write_kml_shapes_maybe_split`, `kml_area_color`, area fill/opacity on `ParsedFeature`, and a
fix to the `onx:id` key lookup in `onx_kml.py`. Any KML numbers below may already be stale
against that work, so re-run the prototype (§6) after it lands.

Evidence tags:

- **[RUN]**: I executed it this session; the output is quoted.
- **[CODE]**: read from onX's live Web Map JavaScript, fetched 2026-10-22 (chunk names below).
- **[HELP]**: onX Zendesk article text, fetched 2026-10-22 via `/api/v2/help_center/...json`.
- **[DOC]**: earlier project docs (`FIDELITY_MODEL_2026-08-29.md`, `PLATFORM_CONSTRAINTS_2026-08-29.md`).
- **[INFER]**: my inference. **[KNOW]**: background knowledge, not fetched this session.

---

## 1. Summary

1. **Most of the engine work is already done, but none of it is connected.** The wheel the web
   app ships (`web/dist/cairn_maps-1.0.0-py3-none-any.whl`) already contains
   `cairn/io/caltopo_gpx.py`, `onx_gpx.py`, `onx_kml.py`, `core/merge.py`, `dedup.py` and
   `shape_dedup.py`. **[RUN]** in real Pyodide 0.29.5, all three XML readers parse the three
   fixtures I ran there correctly (`onx_export_with_tracks.gpx`, `onx_export_with_tracks.kml`,
   `bitterroots/bitterroots_subet.gpx`). `bridge.load_document` imports only `parse_geojson`, and the file input
   accepts `.json,.geojson` only.
2. **The real integration problem is a model mismatch, not parsing.** The bridge and writers
   work on `ParsedData`/`ParsedFeature`. The onX readers return `MapDocument`. A roughly 40-line
   adapter (`to_parsed()`, §6) bridges them, and with it the existing writers emit onX-ready
   files from onX input.
3. **Cairn's own output reads back cleanly.** **[RUN]** Bitterroots (the real CalTopo GeoJSON)
   went through the bridge to the zip, and the onX readers re-read **177/177 items** (68
   waypoints, 92 tracks, 17 areas) with **66/66 waypoint icons identical** to what the UI showed.
   Two names were rewritten by the writer's sanitizer. That is the precondition for
   onX → Cairn → onX.
4. **On an onX-dialect fixture the round trip keeps 54/66 fields; 6 of the 12 losses are the
   onX id.** **[RUN]** Items are matched by name after the writer's sanitizer, and one name
   changed ("Camp & water" → "Camp water"). The fixture is
   modelled on onX's live export code, because the repo has no real onX export. The losses are
   specific engine defects, each fixable (§2, §3.5): the onX id is never written, thin line
   weight collapses to normal, track timestamps are dropped, Cairn's KML writer and reader use
   different dialects, `<rte type=Area>` is read as a Track, and KML holes and MultiGeometry
   parts are dropped.
5. **Round trip = create, not update, today. Whether onX can update at all is unknown.** Cairn
   never writes an onX id (only under `debug_desc=True`). onX's import is a server-side
   `POST /v1/markups/import` that returns new markup ids **[CODE]**, and nothing client-side says
   whether it matches on `id=`. **Settling this needs one probe with a real account (§8, P1).**
   Until then, the plan must assume that re-import duplicates, so the workflow is: export from
   onX → clean in Cairn → **delete the originals in onX** → import.
6. **onX's help center contradicts onX's shipped code.** **[HELP]** (article 360057195972,
   updated 2026-04-01) says: *"Only the location and name of the Markup will be saved. onX
   customizations like icons and colors are not saved."* **[CODE]** The live Web Map export
   writes `onx:color`, `onx:icon`, `onx:style`, `onx:weight`, `onx:fill_color` and a `key=value`
   `<desc>` that includes `notes` and `id`. I trust the code for the **Web Map** export. The
   **iOS app's** GPX export is a separate code path and genuinely unverified.
7. **Security: stock `xml.etree` is safe enough in Pyodide, verified rather than assumed.**
   **[RUN]** Pyodide 0.29.5 runs Python 3.13.2 with **expat 2.6.4**. A billion-laughs file and a
   quadratic-blowup file are both rejected with *"limit on input amplification factor ...
   breached"*. An external `SYSTEM` entity gives *"undefined entity"*, and an external parameter
   entity is ignored. defusedxml 0.7.1 is pure Python (16 files, 68.6 KB installed). It
   **cannot** be installed at runtime under the production CSP (`connect-src` allows only `'self'`
   and the pinned Pyodide folder), so it would have to be vendored. It is recommended as defence
   in depth, not as a blocker.
8. **CalTopo KML has no reader and no fixture.** `read_onx_kml` on a Google-Earth-style KML drops
   `<Folder>`, `<description>` and every `<Style>`. CalTopo's export page returned 503 twice this
   session, so CalTopo's KML structure is **unverified**.

**Is this worth an announcement?** Yes, for **onX GPX + KML input** ("bring your messy onX
account in, fix icons, colours and folders, send it back"). That is a capability no one else
offers. CalTopo GPX/KML input matters less: CalTopo's GeoJSON is strictly richer, so the honest
message there is "we accept it, but export GeoJSON if you can."

---

## 2. Fidelity matrix

Rows: input format. Columns: what the **engine at HEAD** can carry from that input to the
onX-ready output.

- ✅ supported today in the engine
- 🟡 needs work (cause noted)
- ⛔ impossible: the format does not carry it
- ❓ unknown until a real export file is available

| Field | CalTopo GPX | CalTopo KML | onX GPX (Web Map) | onX KML (Web Map) |
|---|---|---|---|---|
| **Name** | ✅ | 🟡 no reader; `read_onx_kml` reads `<name>` | ✅ (`&`, `#`, `!` etc. stripped by `sanitize_name_for_onx` on write) | ✅ (same sanitizer) |
| **Note** | ✅ `<desc>`/`<cmt>`, HTML stripped (fixtures have none) | 🟡 `<description>` ignored: the reader reads notes only from ExtendedData (`onx_kml.py:124`) | ✅ desc kv `notes=` incl. multiline; **[RUN]** `a=b` inside notes survives | ✅ ExtendedData `notes` |
| **Icon** | ⛔ CalTopo writes no `<sym>` **[DOC]**; keyword guess only | ❓ possibly `<IconStyle><href>`; no sample | ✅ `onx:icon`, preserved verbatim **when the adapter passes `cairn_onx_icon_override`** | ✅ ExtendedData `icon` |
| **Color** | ⛔ none in file **[DOC]** | 🟡 if `<Style>` carries one: needs `styleUrl` resolution + AABBGGRR parsing | ✅ `onx:color` (exact palette rgba round-trips) | ✅ ExtendedData `color` |
| **Line style** (solid/dash/dot) | ⛔ | 🟡 KML has no dash; ⛔ in practice | ✅ `onx:style` | 🟡 read into `extra` only, not `Style.OnX_style` |
| **Line weight** | ⛔ | 🟡 `<LineStyle><width>` | 🟡 `"2.0"` (thin) → `"4.0"`: `stroke_width_to_weight` can only return 4.0/6.0 (`color_mapper.py:80-85`) | 🟡 as GPX, and read into `extra` only |
| **Folder** | ⛔ one folder per file **[DOC]**; reader names it after the file | ❓ `<Folder>` may exist; reader ignores it | ⛔ export files carry no folder **[DOC][CODE]**; reader hardcodes `OnX Import/Waypoints/Tracks` (`onx_gpx.py:158-160`). Recoverable only via a `folder=` kv Cairn wrote earlier (FIDELITY W3) or one export file per folder | ⛔ same; onX's tokml writes no `<Folder>` **[DOC]** |
| **Area** (polygon) | ⛔ CalTopo GPX has no polygon | 🟡 Polygon read via `read_onx_kml` | 🟡 onX writes Areas as `<rte>` + `<type>Area</type>` + `onx:fill_color` **[CODE]**. **The reader turns it into a Track** (no type dispatch, FIDELITY W8). Only merging with the KML rescues it | ✅ Polygon → Shape; merge prefers it over the GPX track with the same id (`merge.py`) |
| **Holes** (inner rings) | ⛔ | 🟡 | ⛔ an `<rte>` ring has no holes | 🟡 onX's tokml writes `innerBoundaryIs` **[CODE]**, but the reader reads `outerBoundaryIs` only (`onx_kml.py:196`). **The KML writer also writes ring 0 only** (`writers.py:1148`). MultiGeometry: first polygon only (**[RUN]** 2 parts → 1) |
| **Line vs Track type** | n/a (all → Track) | LineString → Track | 🟡 `<rte type=Line>` (an onX *Line*) is written back as `<trk>`, so **it becomes a Track in onX** | 🟡 KML LineString → Track; onX would re-import a KML line as a Line, but Cairn writes GPX |
| **Elevation** | 🟡 tracks ✅; waypoint `<ele>` dropped; a missing `<ele>` becomes **0**, then written as `<ele>0</ele>` (`caltopo_gpx.py:100`) | ❓ | ✅ track `<ele>`; ⛔ onX writes waypoints with 2D coords in GPX **[CODE]** `(0,g.zx)([e[0],e[1]],t)` | waypoint alt is in the file, but `Waypoint` has no `ele` field (model gap) |
| **Timestamps** | 🟡 reader discards them (hardcodes `0`) | ❓ | 🟡 reader keeps them (**[RUN]** 3/3), **the track writer drops them** (**[RUN]** 3 → 0) | ⛔ LineString has no time |
| **onX id** | ⛔ | ⛔ | 🟡 read ✅ (desc kv `id=`); **never written** (only under `debug_desc`) | 🟡 read ✅ (ExtendedData `id`; HEAD looks up `OnX:id` against lowercased keys, which the working tree fixes); never written |

Ceiling imposed by onX itself **[CODE]**: on export, lines with **more than 300 vertices are
simplified** (`const v=300`, tolerance `x.Kr` from module `vOPT`, value not resolved).
MultiLineStrings are flattened. A `<trk>` that has a `type` kv is rewritten as `<rte>` and loses
its `<ele>`/`<time>` (function `J`). No Cairn round trip can be more faithful than onX's own
export.

---

## 3. Per-format findings with evidence

### 3.1 Inventory **[RUN]**

| Module | Returns | Notes |
|---|---|---|
| `cairn/io/caltopo_gpx.py` `parse_caltopo_gpx` | `ParsedData` (bridge-native) | One folder named after the file stem, `id="default"`. Waypoints/tracks/routes. Empty symbol/color, so the bridge's keyword resolver runs. Raises on 0 features |
| `cairn/io/onx_gpx.py` `read_onx_gpx` | `MapDocument` | desc kv parser + `onx:` extensions (both `wwww.onxmaps.com` casings). `<trk>` and `<rte>`. Track times kept |
| `cairn/io/onx_kml.py` `read_onx_kml` | `MapDocument` | Flat Placemarks, ExtendedData. Point/LineString/Polygon (outer ring only). Ignores `<description>`, `<Style>`, `<Folder>` |
| `cairn/core/merge.py` `merge_onx_gpx_and_kml` | `MapDocument` | Joins on onX id. On a Track-vs-Shape clash it keeps the Shape and copies the Track's color/style/weight/notes onto it |
| `cairn/core/dedup.py`, `shape_dedup.py` | `MapDocument` | Fuzzy dedup; not exercised here |
| **CalTopo KML reader** | — | **Does not exist** |

`read_onx_gpx` on every GPX fixture: all parse except `malformed.gpx` (a clean `ValueError`).
`empty.gpx` yields 0 items. `parse_caltopo_gpx` raises on `empty.gpx`. Per-fixture survival
(counts of items carrying each field):

| Fixture | Items | icon | color | style/weight | notes | ele | time | onX id |
|---|---|---|---|---|---|---|---|---|
| `bitterroots/bitterroots_subet.gpx` (**real CalTopo**) | 10 wpt | 0 | 0 | — | 0 | — | — | 0 |
| `onx_export_with_tracks.gpx` (synthetic) | 2 wpt + 2 trk | 2 | 4 | 0 | 4 | 2 | 0 | 0 |
| `onx_export_with_tracks.kml` (synthetic, has `<Folder>`) | 1 Shape | 0 | 0 | 0 | **0** (its `<description>` is dropped) | — | — | 0 |
| `rattlesnake_test_tracks.gpx` | 10 trk | — | 10 | 10 | 10 | 10 | 0 | 0 |
| `rattlesnake_test_waypoints.gpx` | 34 wpt | 34 | 34 | — | 34 | — | — | 0 |
| `test_sort_trk_time_*.gpx` | 5 trk | — | 5 | 0 | 0 | 0 | **5** | 0 |
| `edge_cases/*` (hand-made) | 1–10 000 | 0 | 0 | 0 | varies | long_track ✅ | 0 | 0 |

**No fixture carries an onX id or a desc kv block**, so the id/kv code paths have no real-file
coverage. FIDELITY's provenance table stands: no genuine onX export is in the repo.

### 3.2 CalTopo GPX

> **Corrected 2026-10-22.** The sample below has no tracks and no notes. The Dark Divide export
> and 60 public CalTopo GPX files show that CalTopo's GPX does carry `<desc>`, multi-line and
> verbatim. Tracks carry Garmin `<gpxx:DisplayColor>`, which `caltopo_gpx.py` now reads. There
> is still no `<sym>`, no waypoint color and no folders.

- **Verified [RUN]**: `creator="CALTOPO"`, Garmin `gpxx` namespace declared, names in plain or
  CDATA form, `<wpt>` only in the one real sample. Names and coordinates only. That matches
  [DOC] and the CalTopo training page as quoted by search: *"GPX: ... you lose line and marker
  style, and folder organization."*
- **Gaps**: waypoint `<ele>` is not read. Track `<time>` is discarded (`[lon,lat,ele,0]`). A
  missing `<ele>` becomes `0` and is then written as `<ele>0</ele>`, inventing sea-level
  elevation. The sample has no tracks, so whether CalTopo writes `<ele>`/`<time>` on tracks is
  unverified.
- **Product read**: every icon is a keyword guess, every colour is the default, and there is one
  folder. That is still useful (the review UI is the point), but GeoJSON is strictly better.
  The UI should say so when it detects `creator="CALTOPO"`.

### 3.3 CalTopo KML

> **Superseded 2026-10-22 (roadmap Phase 7).** Real CalTopo KMLs were read: the owner's Dark
> Divide 100 export, and nine public files. They have flat `<Folder>`s, inline `<Style>`s,
> icon hrefs `caltopo.com/icon.png?cfg=<symbol>[,RRGGBB]#1.0`, and plain-text descriptions. A
> polygon is written as a `MultiGeometry` with a label Point. `cairn/io/caltopo_kml.py` reads
> it. The dialect is in `tests/fixtures/caltopo_synthetic/README.md`, and the parity results
> are in `tests/fixtures/dark_divide_100/PARITY.md`. The original notes follow.

- **Unverified.** No sample in the repo. `training.caltopo.com/.../export` returned 503 twice.
  **Discrepancy:** `PLATFORM_CONSTRAINTS` marks KML as losing both styles and folders, but the
  only CalTopo text recovered this session describes GeoJSON and GPX, not KML.
- **[RUN]** on a hypothetical Google-Earth-style file (`<Folder>`, shared `<Style>` +
  `styleUrl`, HTML `<description>`), `read_onx_kml` returned 3 items with **folder lost, notes
  lost, colour lost**.
- **Needed**: a `caltopo_kml.py` reader (or a generic KML mode in `onx_kml.py`) that walks
  `<Folder>` into folders, reads `<description>` (stripping HTML), resolves
  `styleUrl` → `Style`/`StyleMap` → `IconStyle`/`LineStyle`/`PolyStyle` colours (KML colour is
  `aabbggrr`), and reads `MultiGeometry` and inner rings. Build it only after one real CalTopo
  KML export is in hand (P6).

### 3.4 onX GPX (Web Map export), decoded from live code **[CODE]**

Chunk `37299.498db4a8175bf385c00b.js` (fetched 2026-10-22; the hash will rotate):

- Every feature gets `{name, notes, id: uuid}`. Tracks add `color` (`rgba(...)`), `style` and
  `weight` (`thin→"2.0"`, `normal→"4.0"`, `thick→"6.0"`). Lines add `type:"Line"`. Shapes add
  `type:"Area"` and `fill_color`. Waypoints add `color` and `icon`.
- Serialised by togpx with `creator: "onXmaps ${app} web"` and `featureCoordTimes` (so track
  `<time>` comes from `point_intervals`). The properties are dumped into `<desc>` as `key=value`
  lines.
- Post-processor `y()`: if a `<trk>` has a `type` kv, it is rebuilt as `<rte>` (losing
  ele/time). It adds `<extensions>` with `onx:color, onx:icon` (wpt), `onx:color, onx:style,
  onx:weight` (trk/Line) and `+ onx:fill_color` (Area), plus a literal `<type>` on `<rte>`. It
  finally does `n.replace("<gpx", '<gpx xmlns:onx="https://wwww.onxmaps.com/"')`, which is the
  `wwww` typo, confirmed still live.
- The default filename is `onx-markups-<date>.gpx`. No folder name appears anywhere in the file.
- **What the reader still gets wrong**:
  - `<type>`/`type=` is ignored, so Areas and Lines both become Tracks.
  - `"folder"` is not in `_DESC_KV_KEYS` (needed for FIDELITY W3).
  - The folder scaffold is hardcoded.

### 3.5 onX KML (Web Map export) **[CODE]**

Chunk `58175.0d9ed1037d6326f4bb0b.js` is mapbox's tokml, called with no options
(`B()(e.markups)`):

- Each feature becomes a flat `<Placemark>` with `<name>` and `<ExtendedData><Data name=…>` for
  **every** property (`name, notes, id, color, icon, type, style, weight, fill_color`).
- `<Style>` is emitted only for `marker-*` simplestyle props, which onX never sets. Inferred
  from the code paths: **no `<Style>` in onX KML**.
- Polygons are written with `innerBoundaryIs`. Multi-geometries become `MultiGeometry`.
- `<description>` is written only from a `description` property, which onX doesn't set, so the
  notes live in ExtendedData only.

**Cairn's own KML is a different dialect.** `write_kml_shapes` writes notes into
`<description>` and colour into `<Style>`, and writes no ExtendedData. **[RUN]** Re-reading
Cairn's KML with `read_onx_kml` loses notes, colour, style and weight. Because onX is the
import target, Cairn's KML **output** should add onX-style ExtendedData (`notes, color, style,
weight, fill_color`) alongside the KML Style, so that one reader handles onX files and Cairn
files alike. ⚠ `writers.py` is being edited in parallel, so coordinate before touching it.

### 3.6 Update vs create (the round-trip identity question)

- **[CODE]** Import executor (chunk `87571.b2fabb456fd0688670ed.js`, module `z1zK`): one
  `FormData{type, file, collection-id?}` per file → `POST /v1/markups/import`. The response
  carries `markups: [ids]`, after which the client calls `requestAllMarkups()` and counts the
  types of the returned ids for telemetry. No client-side code refers to an existing markup's
  id.
- **[INFER, medium]**: onX creates new markups. A server-side upsert on `id=` is possible but
  nothing hints at it. Note that today's Cairn output contains no id at all, so even an upserting
  server would create duplicates.
- **Implication for the roadmap**: until P1 says otherwise, the onX → Cairn → onX flow must tell
  the user to delete the source markups (or the source folder) in onX before importing the
  cleaned files. The 1,500-markup account ceiling makes "import, then delete the old ones"
  impossible for large accounts, so the order matters: delete first, then import. That is
  scary, so keep the original export file as the backup.

---

## 4. Security

| Test | Native (Python 3.15.0, expat 2.7.4) **[RUN]** | Pyodide 0.29.5 (Python 3.13.2, **expat 2.6.4**) **[RUN]** in headless Chromium |
|---|---|---|
| Billion laughs (10×10 nested, `bl.gpx`) | `ParseError: limit on input amplification factor (from DTD and entities) breached`, 0.09 s, RSS 71 MB | same message, 0.096 s |
| Quadratic blowup (20 KB entity × 20 000 refs, `quad.kml`) | same message, 0.01 s | same message, 0.009 s |
| External general entity `SYSTEM "file://…secret.txt"` | `undefined entity &xxe;`, nothing read | same |
| External parameter entity `%p;` | parses; entity ignored; secret not read | (not repeated) |

- The protection comes from expat's amplification limit (added in expat 2.4.0, 2021 **[KNOW]**).
  Pyodide's bundled expat 2.6.4 has it, and ElementTree does not resolve external entities.
- There is no network or filesystem secret in the browser sandbox anyway. The remaining risk is
  a crash or hang in one tab on a file the user picked themselves, and expat's limits already
  cover the known amplification classes.
- **defusedxml**: 0.7.1 installs into Pyodide via micropip (pure Python, 16 files, 68 651
  bytes). It turns any DTD entity into `EntitiesForbidden` (**[RUN]** on `bl.gpx`). But the
  production CSP is `connect-src 'self' https://cdn.jsdelivr.net/pyodide/v0.29.5/full/`, and
  defusedxml is not in Pyodide 0.29.5's `pyodide-lock.json` (**[RUN]** grep of the 122 KB lockfile
  found `lxml`, not `defusedxml`), so `micropip.install("defusedxml")` would hit PyPI
  and be **blocked in production**. That path is untested under CSP, and the probe page had no
  CSP. The only deployable route is to **vendor the wheel into `web/dist/`** and install it from
  `'self'`, as is done for `cairn_maps`.
- **Recommendation**: keep stock ElementTree, but add a cheap pre-parse guard in the bridge.
  Reject any input containing `<!DOCTYPE` or `<!ENTITY` with a friendly message, since no GPX or
  KML exporter of interest emits a DTD, and cap the input size (onX's own cap is 4 MB). That
  gives defusedxml's fail-fast behaviour in about 5 lines with no new dependency. Update the
  AGENTS.md "XML parsing" trap when XML becomes reachable from the bridge, because that note's
  premise changes on that day. Add both attack files as test fixtures.

---

## 5. Proposed design for web input

### 5.1 Format detection (by extension, then by content sniffing) **[RUN] prototype**

The detection rule:

1. Strip the BOM and leading whitespace.
2. A first byte of `{` or `[` means JSON. CalTopo GeoJSON is recognised when any feature has
   `properties.class ∈ {Folder, Marker, Shape}`.
3. A first byte of `<` means XML: regex the first 4 KB for the root `gpx|kml`, then classify the
   dialect.
   - **GPX**: `creator` containing `onxmaps` → onX web; `CALTOPO` → CalTopo; `Cairn…` → Cairn's
     own output; otherwise an `onxmaps.com` namespace → onX-like; otherwise generic.
   - **KML**: `<Data name="id">` → onX-like; `<Folder>`/`<Style>` → CalTopo, Google Earth or
     Cairn.
4. The content wins over the extension; report a mismatch.

Results over all 53 fixture, scratch and output files:

- Real CalTopo GPX → `caltopo`.
- onX-dialect fixture → `onx-web`.
- Old synthetic onX GPX → `onx-ns (creator='OnX Backcountry')`.
- 15 test-fixture GPXs (`creator="Cairn …"`) plus the 18 Cairn-written Bitterroots GPXs → `cairn`.
- Malformed JSON/GPX → detected as unparseable before any reader runs.

**Gap**: Cairn's own KML has no marker, so it sniffs like a CalTopo/Google Earth KML. The KML
writer should stamp one (e.g. `<Document><Snippet>Cairn</Snippet>` or ExtendedData).

### 5.2 `bridge.load_document` changes

```
load_document(text, filename):
    guard: size cap, reject <!DOCTYPE/<!ENTITY
    kind, dialect = detect(filename, text)
    write to /tmp/<stem>.<ext>          # stem matters: folder fallback name (bridge.py:107-114)
    caltopo geojson -> parse_geojson               (unchanged)
    caltopo gpx     -> parse_caltopo_gpx           (already ParsedData)
    onx/cairn gpx   -> read_onx_gpx  -> to_parsed_data(doc, folder_name=<stem>)
    onx/cairn kml   -> read_onx_kml  -> to_parsed_data(...)
    caltopo kml     -> NEW reader (after a real sample, P6)
    multi-file (gpx+kml from the same onX export) -> merge_onx_gpx_and_kml first
```

`to_parsed_data` is the §6 `to_parsed()` adapter plus folder handling:

- Ignore the hardcoded `OnX Import/Waypoints/Tracks/Areas` scaffold. For the web, use **one
  group named from the filename**, as `caltopo_gpx` does. If W3's `folder=` kv is present, group
  by it.
- Keep `uid = f"{fkey}::{kind}::{index}"` unchanged. `export_zip`'s include/exclude filter
  decodes positions from it.
- Map `Track` → `kind="tracks"` and `Shape` → `kind="shapes"`. Once the reader dispatches on
  `type`, carry a sub-kind `line|track|area` so the UI and the writer can keep an onX *Line* a
  Line (KML LineString) instead of silently turning it into a Track.
- The file input needs `accept=".json,.geojson,.gpx,.kml"` (web/index.html:43, owned by another
  agent), and `mapTitle()` must strip `.gpx`/`.kml` too.
- Multi-select or a second drop lets a user give the GPX and KML from the same onX export
  together.

### 5.3 Icon and colour decisions when the source is already onX

The source styling is the user's own prior choice, so it must be **preserved, not re-guessed**:

- **Icon**: set `properties.cairn_onx_icon_override = style.OnX_icon` (`writers.py` reads it
  first), and in the bridge item set `icon=OnX_icon`, `confirmed=True` and
  `needs_attention=False`. Exception: if the icon is not in the canonical catalog
  (`get_all_onx_icons()`), flag it. Do **not** call `IconResolver.resolve` for these items.
- **Colour**: the source `rgba(...)` is already an exact palette value. Pass it as
  `marker-color`/`stroke`. `ColorMapper` maps an exact palette rgba to itself (**[RUN]** every waypoint and
  track colour round-tripped in §6; the area colour was lost only because of the KML dialect
  mismatch in §3.5). Show it as is, and don't run `resolve_waypoint_color`'s
  icon-convention fallback.
- **`why` text**: add a source branch to `_explain`, e.g. *"Kept from your onX file."* Otherwise
  the UI claims a keyword match it never made.
- **Line style/weight**: carry `OnX_style` → `pattern` and `OnX_weight` → `stroke-width`. This
  needs `stroke_width_to_weight` to support thin (≤2 → `"2.0"`). Today it can't, and that
  changes CalTopo output too (CalTopo widths of 1–2 currently become normal), so decide
  deliberately.
- **Notes**: exported desc is notes-only by default, which is correct. If W3 lands, append
  `folder=`.
- **Ids**: decide after P1. If onX upserts on `id=`, write the source id back (desc kv or
  ExtendedData) so a round trip **updates**. If not, never write it, because a stale id is
  harmless at best and confusing at worst.

### 5.4 Engine fixes this research surfaced (for the bug-fix agents; I changed no code)

1. **`read_onx_gpx`**: dispatch on `<type>`/`type=`. `Area` → `Shape` (ring from `rtept`), and
   `Line` → Track with `extra["onx_kind"]="line"` (FIDELITY W8).
2. **`read_onx_kml`**:
   - read `<description>` as a notes fallback;
   - read `innerBoundaryIs` rings;
   - iterate every geometry in `MultiGeometry`;
   - map `style`/`weight` ExtendedData into `Style.OnX_style/OnX_weight`.
3. **`write_kml_shapes`** writes `coordinates[0]` only, so holes are dropped. Write all rings.
   Bitterroots has 0 holes **[RUN]**, so this is low priority.
4. **Track writer** emits no `<time>`, even when the points have it.
5. **`stroke_width_to_weight`** has no thin bucket.
6. **`parse_caltopo_gpx`** invents `ele=0` when `<ele>` is absent, and the writer then emits
   `<ele>0</ele>`.
7. **`sanitize_name_for_onx`** deliberately strips `! @ # $ % ^ * &` (`utils.py:151`).
   "Camp & water" becomes "Camp water". `&amp;` is legal XML, and onX's own export carries
   whatever the user typed, so verify whether onX rejects these characters at all. If it
   doesn't, this is silent data loss on every round trip.

---

## 6. Prototype and numbers **[RUN]**

The scratch scripts live in `$TMPDIR/kmlgpx/` (`/tmp/claude-501/kmlgpx/`) and are not
committed.

- **`inventory.py`**: every reader × every fixture (§3.1).
- **`roundtrip.py`**: `onx_dialect.gpx` + `onx_dialect.kml` → `read_onx_gpx`/`read_onx_kml` →
  `merge_onx_gpx_and_kml` → `to_parsed()` → `write_gpx_waypoints_maybe_split`,
  `write_gpx_tracks_maybe_split`, `write_kml_shapes` → re-read → per-field diff. The fixtures are
  synthetic but follow the §3.4/§3.5 code readout: desc kv, `onx:` extensions, `<rte>` Line and
  Area, a KML polygon with a hole, and a two-part MultiGeometry.

  ```
  merged items: 6 (2 Waypoint, 2 Track, 2 Shape)   -- the KML polygon replaced the GPX <rte type=Area> track
  DIFF  'Main Wall'      {'id': (uuid, None)}
  DIFF  'Camp water'     {'id': (uuid, None)}          -- name was 'Camp & water' (sanitizer); icon/color/notes intact
  DIFF  'Recorded hike'  {'weight': ('2.0','4.0'), 'id': (uuid, None), 'time': (3, 0)}
  DIFF  'Ridge line'     {'id': (uuid, None)}          -- also onX Line -> Track (type not modelled)
  DIFF  'Hunt unit'      {'notes','color','style','weight','id' lost}  -- Cairn KML dialect ≠ reader
                         rings: 1 -> 1 (the hole was already lost at read)
  DIFF  'Two-part area'  {'id'}                        -- second polygon lost at read
  field agreement: 54/66 (6 of the 12 misses are the id); items 6 -> 6
  (the first scoring pass matched raw names and reported 44/66, counting the renamed waypoint as
  lost even though its icon, colour and notes had survived)
  ```

  Every icon, every waypoint colour and every multi-line note survived. Every loss maps to a
  §5.4 item or to the id decision.
- **`bitter_rt.py`**: Bitterroots GeoJSON → HEAD `bridge.load_document` + `export_zip` → each
  zip file re-read by the onX readers. Result: **177/177 items**, kinds exact (68/92/17),
  **66/66 waypoint icons equal the UI's icon**, 2 names changed by the sanitizer.
- **`sniff.py`**: §5.1. **`sec_test.py`, `pyodide_probe.py`**: §4. `pyodide_probe.py` installs the
  real `web/dist` wheel into Pyodide 0.29.5 and runs all three readers on the three fixtures listed in §1, and all
  succeed.
- **Not done**: no real onX or CalTopo KML file, no import into a real onX account, no UI wiring,
  no test under the production CSP.

---

## 7. Effort estimate per step

| # | Step | Size | Verifiable offline? |
|---|---|---|---|
| 1 | Pre-parse guard (DOCTYPE/ENTITY reject, size cap) + attack-file tests; update the AGENTS.md trap | S (½ day) | yes |
| 2 | `detect()` sniffer in the bridge + tests over all fixtures; Cairn KML marker | S (½ day) | yes |
| 3 | `to_parsed_data` adapter + `load_document` dispatch for onX GPX/KML and CalTopo GPX; icon/colour preservation (`confirmed`, `_explain` source); add the readers to `WEB_ENGINE` in `tests/test_web_engine_surface.py` with header comments | M (1–2 days) | yes |
| 4 | Reader fixes §5.4.1–2 (type dispatch, description, holes, MultiGeometry, style/weight) | M (1 day) | yes, against synthetic dialect fixtures |
| 5 | Writer fixes §5.4.3–6 (all rings, `<time>`, thin weight, no fake ele) + KML ExtendedData dialect | M (1 day), coordinate with the writers.py owner | yes |
| 6 | UI: accept `.gpx,.kml`, multi-file drop (GPX + KML pair), title stripping, "from onX" badge/explanation, Line/Track/Area sub-kind | M (1–2 days) | e2e (Playwright) |
| 7 | Runbook variant for round trip: "delete originals first, keep this export as your backup", 1,500-ceiling arithmetic | S | yes |
| 8 | Vendor defusedxml (optional) | S | e2e under CSP |
| 9 | CalTopo KML reader | M (1 day) | **needs a real CalTopo KML (P6)** |
| 10 | Id write-back for update-in-place | S if P1 = yes; drop if no | **needs P1** |

Steps 1–5 are about 4–5 days and fully offline. Shipping "onX GPX/KML in" credibly needs steps
1–7 plus P1–P3 answered.

---

## 8. Open questions that need a real export file or a real account

| # | Question | Cheapest probe | Changes |
|---|---|---|---|
| **P1** | **Does onX import update a markup whose `id=` matches an existing one, or create a duplicate?** | Export 1 waypoint from the Web Map as GPX, change its name in the file, re-import: 1 markup or 2? Repeat with KML | Whether a round trip is "update" or "replace"; whether to write ids (§5.3) |
| P2 | Does a real Web Map GPX export match §3.4 (desc kv with `id`/`notes`, `onx:` extensions, `<rte><type>Area`)? The help center says icons and colours aren't saved | Export 1 waypoint, 1 track, 1 line and 1 area as GPX **and** KML; commit them as fixtures (FIDELITY W6) | Replaces all synthetic onX fixtures |
| P3 | Does onX import `<rte>` + `type=Area` as an Area? | Import the P2 GPX back into a scratch folder | Whether GPX-only round trips keep areas (FIDELITY B2) |
| P4 | Does the **iOS app's** GPX export carry extensions/kv, or only name + location as the help center says? | Export the same 4 markups from the app | Whether app users can round trip at all |
| P5 | Does onX accept `& # ! @` in names on import? | Import one waypoint named `A & B #1` | Whether `sanitize_name_for_onx` should stop stripping them |
| P6 | Real CalTopo KML structure (Folders? Styles? description HTML?) | Export one small map from CalTopo as KML | Whether a CalTopo KML reader is worth building (step 9) |
| P7 | Does onX read `<time>` on import, and elevation on waypoints? | Import a 3-point track with times | Whether fixing the time writer matters for onX |
| P8 | The simplify tolerance `x.Kr` (module `vOPT`) | Grep the entry bundles (not fetched; only lazy chunks were) | How much geometry onX's own export destroys on long tracks |

> **Answered later on 2026-10-22, in a real Web Map import (design decision ENG-05).**
> **P2:** a real Web Map GPX export matches §3.4 (`tests/fixtures/caltopo-random/onx_roundtrip/
> from_geojson/onx_export.gpx`): `<desc>` key=value with `id`/`notes`/`type`, `onx:` extensions,
> areas as `<rte><type>Area</type>` with `onx:color` + `onx:fill_color`. **P3: yes** — a GPX
> `<rte>` with `<type>Area</type>` and those two extensions imports as an Area with its color,
> while onX **ignores** area color and fill in KML (`Style`, `styleUrl` and `ExtendedData` all
> came in as onX's default red). onX also does **not** parse a key=value `<desc>` on import; it
> becomes the Notes verbatim. Cairn now exports areas as GPX `<rte>` (outer ring only: onX
> areas have no holes; RUNBOOK.md lists the affected areas).

---

## Sources

- onX Web Map JS, fetched 2026-10-22 from `webmap.onxmaps.com`. Runtime
  `runtime.9d513607b1b8bc66d666.js` (1,171 chunks). Export post-processor
  `37299.498db4a8175bf385c00b.js`. tokml/togpx `58175.0d9ed1037d6326f4bb0b.js`. Import executor
  `87571.b2fabb456fd0688670ed.js` (`z1zK`).
- onX help center (Zendesk API, fetched 2026-10-22):
  [360057195972 Importing and Exporting Markups](https://onxbackcountry.zendesk.com/hc/en-us/articles/360057195972)
  (updated 2026-04-01),
  [4446611009165 CalTopo transfer](https://onxbackcountry.zendesk.com/hc/en-us/articles/4446611009165)
  (updated 2026-07-14),
  [5022588722317 Import errors](https://onxbackcountry.zendesk.com/hc/en-us/articles/5022588722317)
  (updated 2026-07-20).
- [CalTopo — Exporting Objects](https://training.caltopo.com/all_users/import-export/export):
  HTTP 503 on both attempts. The text was quoted only from search-result extraction, together
  with [Import and Export Functions](https://training.caltopo.com/all_users/import-export).
- GPX 1.1 (`http://www.topografix.com/GPX/1/1`) and KML 2.2 (`http://www.opengis.net/kml/2.2`)
  element semantics: **[KNOW]**, not fetched this session.
- Project docs: `docs/FIDELITY_MODEL_2026-08-29.md` (§1 dialect readout, W3/W6/W8, probes
  B1–B4), `docs/PLATFORM_CONSTRAINTS_2026-08-29.md`.
