# Roadmap: GPX/KML input and the onX round trip (2026-10-22)

**Status:** draft. Nothing in this file is built or decided. It plans two features:

1. **GPX and KML as input** to the web app, in both CalTopo and onX dialects. Today the app
   reads CalTopo GeoJSON only.
2. **A fast onX → Cairn cleanup → onX round trip.** You export your messy onX account, fix
   icons, colours, names and folders in Cairn, and send it back.

**Sources.** Every claim here comes from one of these, and the tags they use carry over:

- `docs/research/KML_GPX_INPUT_2026-10-22.md` (cited as **KG**, with § numbers)
- `docs/research/ONX_REIMPORT_AND_SHARING_2026-10-22.md` (cited as **RS**)
- `docs/FIDELITY_MODEL_2026-08-29.md` (cited as **FM**: workplan W1–W8, probes B1–B4)
- `docs/design/DECISIONS.md`
- `TODO.md`
- `docs/FAQ.md`

Anything that is my own inference is marked **[ASSUMPTION]**.

**Ordering rule.** Work that needs no onX account comes first (Phases 0–3). Work that waits on
the owner's real files or test imports comes after (Phases 4–7). The owner's tasks are gathered
in one place, [§2](#2-what-the-owner-must-provide), so they can be done in a single sitting
while Phases 0–3 are being built.

---

## 1. Where things stand

Already true. Each item was verified by the research agents unless marked otherwise.

- **The readers exist and run in the browser, but nothing calls them.**
  - The web wheel already contains `cairn/io/caltopo_gpx.py`, `onx_gpx.py`, `onx_kml.py`,
    `core/merge.py`, `dedup.py` and `shape_dedup.py`.
  - All three XML readers parsed the three fixtures they were tried on in real Pyodide 0.29.5
    (KG §1.1).
  - `web/bridge.py:load_document` imports only `parse_geojson`, and the file input accepts
    `.json,.geojson` only (`web/index.html:45`).
  - This matches decision SCOPE-02: keep these modules and mark them "not yet web".
- **The real gap is the data model, not parsing.**
  - The bridge and writers work on `ParsedData`/`ParsedFeature`. The onX readers return
    `MapDocument`.
  - A scratch adapter of about 40 lines connects the two (KG §6). It is not committed; the
    scratch copy is in `/tmp/claude-501/kmlgpx/`.
- **Cairn's own output reads back cleanly.** Bitterroots went through the bridge, the zip and
  the onX readers and came back with 177 of 177 items. All 66 waypoint icons were identical
  (KG §6).
- **Fidelity on an onX-style file is 54 of 66 fields.**
  - Six of the misses are the onX id.
  - The other six are fixable engine bugs (KG §5.4).
  - The fixture is synthetic, modelled on onX's live export code. **No real onX export exists
    in the repo** (KG §3.1, FM W6).
- **Areas work end to end on CalTopo GeoJSON input.**
  - This covers `class == "Shape"` features with Polygon geometry.
  - The working tree on this branch, uncommitted at the time of writing, adds: inner rings
    written as `<innerBoundaryIs>`, KML size-splitting, colours snapped to the palette, and
    counts of dropped areas.
  - **Not covered:** `MultiPolygon` is still silently ignored by the parser (TODO.md), and the
    *readers* still drop holes and MultiGeometry parts (KG §5.4.2).
- **Re-import creates new items today, by construction.**
  - Cairn writes no onX id (`writers.py:_desc_text`).
  - Whether onX *would* update an item if the id were present is **UNKNOWN**. The evidence
    leans toward "it duplicates" (RS §1.5).
- **onX's limits.**
  - The **account** limit is now **3,000** markups (help article 360052239052, updated
    2026-09-16; RS finding 1).
  - Stale "1,500" copies remain in `web/app.js`, `web/index.html`, `docs/FAQ.md` and
    `web/faq.html`. The new runbook text added on this branch also says 1,500.
  - Per import: 3,000 markups and 4 MB per file (RS finding 2).
- **onX can't share maps publicly.** Recipients need an onX account, and opening a share link
  copies the markups into their account (RS §2.2). Nothing in this roadmap can rely on a public
  onX map.

---

## 2. What the owner must provide

These are the questions that block work, and exactly what to do to answer each one. Probe IDs
are KG §8's. The steps are RS §1.6's ten-minute test, extended to capture fixtures.

**Prerequisites:**

- an onX Backcountry **Premium or Elite** account (importing requires one);
- the **Web Map** on a computer;
- a text editor;
- about 25 minutes.

**Safety rules:**

- Give every test markup a name starting `ZZTEST` and keep them in a folder named
  `ZZ Cairn Test`.
- Clean up by deleting the **markups first, then the folder**. Deleting a folder doesn't delete
  its markups (RS §1.6).

| # | Question | What to do | What to hand back | Unblocks |
|---|---|---|---|---|
| **P1 ✅ answered 2026-10-22: duplicates** | **Does re-import update a markup with a matching `id=`, or duplicate it?** (Re-importing an unchanged onX GPX export added 2 new markups; see the research doc §1.7.) | RS §1.6 Tests A, B and C:<br>• Export 2 waypoints.<br>• Re-import the file unchanged and note the count change: +0 or +2.<br>• If +0, re-import with one name and one colour edited.<br>• Export again and diff the ids. Repeat once with KML. | The counts at each step, the id diff, and whether Notes shows `key=value` text | Phase 5 (wording) and Phase 6 (whether it exists at all) |
| **P2** | Does a real Web Map export match the decoded format: `<desc>` key/value lines with `id`/`notes`, `onx:` extensions, Areas as `<rte><type>Area`? | Put **1 waypoint, 1 track, 1 Line and 1 Area** in `ZZ Cairn Test`. If you can, give the Area a hole and the waypoint a two-line note with `&` and `#` in its name. Export the folder as **GPX** and again as **KML**. | Both files, unedited, to commit as `tests/fixtures/onx_real/` (FM W6) | Phase 4. Replaces every synthetic onX fixture |
| **P3** | Does onX import an `<rte>` with `type=Area` as an Area? (FM probe B2) | Import the P2 GPX by itself into a new folder | Whether you get a filled Area or a stray Line/Track | Whether a GPX-only onX export keeps its areas (Phase 1 reader fix stays either way) |
| **P4** | Does the **iOS app's** GPX export carry the extensions and `<desc>` lines, or only name and location, as the help centre claims? | Export the same 4 markups from the phone app | The file | Whether phone users can round trip at all. If not, the feature is Web Map only |
| **P5** | Does onX accept `& # ! @` in names? | Import one waypoint named `ZZTEST A & B #1` (a hand-written GPX is fine) | The name as onX shows it | Whether `sanitize_name_for_onx` keeps stripping these, which is silent data loss on every round trip |
| **P6** | What is the real structure of a CalTopo KML: Folders? Styles? HTML descriptions? | Export one small CalTopo map as KML | The file, for `tests/fixtures/caltopo_real/` | Phase 7 |
| **P7** | Does onX read track `<time>` and waypoint elevation on import? | Import a 3-point track with times | Whether times or elevation appear | The priority of the time-writer fix in Phase 1 |
| **S1** | What does a logged-out visitor see on an onX share link? | Open a share link in a private window | A screenshot | The walkthrough page, not this roadmap. Listed because it fits the same sitting |

**Cleanup after the sitting:**

1. Search `ZZTEST`, select all, delete.
2. Delete `ZZ Cairn Test` and every `Import mm/dd/yy H:MM` folder the test created.
3. Check the total markup count is back to its starting value.

**[ASSUMPTION]** The Web Map can create a *Track* without recording one on the phone. If it
can't, record a few seconds of track on the phone and let it sync. A drawn Line is still
needed separately.

---

## 3. Phases

Effort sizes:

- **S** ≈ half a day
- **M** ≈ 1–2 days
- **L** ≈ 3 or more days

The sizes are KG §7's estimates, regrouped.

### Phase 0: Input safety and format detection

*Can start now, offline.*

- **Goal:** the bridge can safely accept XML and say what a file is, before any reader runs.
- **User-visible outcome:** none yet, because the file picker is unchanged.
  - Internally, a hostile or non-map XML file gets a friendly error instead of a hang.
  - A wrong extension is reported.
- **Engine and web work:**
  - **Pre-parse guard in `web/bridge.py`:**
    - Reject any input containing `<!DOCTYPE` or `<!ENTITY`. No exporter of interest emits a
      DTD (KG §4).
    - Cap the input size. onX's own cap is 4 MB. **[ASSUMPTION]** Allow some headroom above
      that for input, since a messy account is the point.
  - **`detect(filename, text)` sniffer,** returning `(kind, dialect)` per KG §5.1:
    - JSON: CalTopo GeoJSON.
    - GPX: `creator` says `onxmaps`, `CALTOPO` or `Cairn`; otherwise an onX namespace;
      otherwise generic.
    - KML: `<Data name="id">` means onX; anything else is CalTopo, Google Earth or Cairn.
    - The content wins over the extension.
  - **A marker in Cairn's own KML,** e.g. `<Snippet>` or ExtendedData, so it can be told apart
    from CalTopo or Google Earth KML (KG §5.1 gap). This touches `writers.py`, so coordinate
    with its owner.
  - **Rewrite the AGENTS.md "XML parsing" trap.** Its premise ("XML is not reachable from the
    web bridge") stops being true in Phase 2.
  - **Optional:** vendor defusedxml into `web/dist/` as defence in depth (KG §4). Runtime
    install is blocked by the CSP.
- **Tests:**
  - billion-laughs and quadratic-blowup files as fixtures, both rejected;
  - an external-entity file, rejected;
  - the sniffer run over every file in `tests/fixtures/`, with the expected dialect per file;
  - a test that the Cairn KML marker is present.
- **Exit criteria:**
  - Every fixture classifies as expected.
  - The attack files fail fast with a user-facing message.
  - The AGENTS.md trap is updated.
- **Effort:** S–M (1 day).
- **Depends on:** nothing.
- **Open questions:** none blocking.

### Phase 1: Reader and writer fidelity fixes

*Can start now, offline, against synthetic fixtures.*

- **Goal:** close the six non-id losses in the 54/66 round trip (KG §5.4), so that once
  Phase 2 connects the readers, what reaches the user is faithful.
- **User-visible outcome:** none directly. These are the reasons Phase 3's output would
  otherwise be wrong.
- **Engine work:**
  1. **`read_onx_gpx` dispatches on `<type>`/`type=`** (FM W8).
     - `Area` becomes a Shape whose ring is the `rtept`s.
     - `Line` becomes a Track tagged `extra["onx_kind"]="line"`.
     - This is correct whatever P3 shows, because real exports contain these (FM W8).
  2. **`read_onx_kml`:**
     - reads inner rings and every `MultiGeometry` part;
     - uses `<description>` as a fallback for notes;
     - maps the `style`/`weight` ExtendedData into `Style.OnX_style`/`OnX_weight`.
  3. **Cairn's KML output also writes onX-style ExtendedData** (`notes`, `color`, `style`,
     `weight`, `fill_color`) alongside the KML `<Style>`, so one reader handles onX files and
     Cairn files alike (KG §3.5).
  4. **The track writer emits `<time>`** when the points have it. P7 decides how much this
     matters in onX. The fix is cheap and correct either way.
  5. **Add a "thin" bucket to `stroke_width_to_weight`** (≤2 → `"2.0"`).
     - **This is a decision, not just a bug fix:** it also changes CalTopo output, where widths
       of 1–2 currently become "normal" (KG §5.3). Record it in DECISIONS.md.
  6. **`parse_caltopo_gpx` stops inventing `ele=0`** when `<ele>` is missing, and the writer
     omits `<ele>` in that case.
  7. **`parser.py` handles CalTopo `MultiPolygon`:** one area per part, or at least counted as
     dropped. It is in TODO.md and has no fixture yet.
- **Already done on this branch (uncommitted):**
  - the KML writer writes every ring;
  - KML is size-split like GPX;
  - area colours are snapped to the palette.

  Phase 1 builds on those changes, so commit them first.
- **Tests:**
  - extend the KG §6 synthetic dialect fixtures (desc key/value lines, a `<rte>` Line and Area,
    a polygon with a hole, a two-part MultiGeometry) into `tests/fixtures/onx_dialect/`;
  - a round-trip test that asserts per-field agreement and fails on any regression below the
    new figure;
  - a test that re-reading Cairn's KML keeps notes, colour, style and weight.
- **Exit criteria:** on the synthetic dialect fixtures, the round trip loses **only** the onX id
  and the fields onX itself can't carry (folder; waypoint elevation in GPX). Every other field
  in KG §6's diff agrees.
- **Effort:** M–L (2 days). `writers.py` is shared, so coordinate.
- **Depends on:** this branch's uncommitted writer and parser changes landing.
- **Open questions:**
  - P2 may reveal that the synthetic fixtures are wrong about the dialect. Phase 4 re-checks.
  - P5 decides whether the `&`/`#` stripping in `sanitize_name_for_onx` is a bug. **Don't change
    it before P5.**

### Phase 2: Bridge adapter and input dispatch

*Can start now, offline.*

- **Goal:** `bridge.load_document` accepts onX GPX, onX KML, an onX GPX + KML pair, and CalTopo
  GPX, and hands the existing UI the same `ParsedData` shape it already renders.
- **User-visible outcome:** none until Phase 3 opens the file picker, but the bridge contract is
  complete.
- **Engine and web work:**
  - **`to_parsed_data(doc, folder_name)`:** the KG §6 adapter plus folder handling (KG §5.2).
    - Ignore the readers' hard-coded `OnX Import/Waypoints/Tracks/Areas` folders. Use **one
      folder per input file, named from the file's stem**, as `caltopo_gpx` already does.
    - Keep `uid = f"{fkey}::{kind}::{index}"` unchanged, because the include/exclude filter in
      `export_zip` decodes it.
    - Map Track → `tracks` and Shape → `shapes`. Carry a sub-kind (`line`/`track`/`area`) from
      Phase 1.
  - **Dispatch in `load_document`** on Phase 0's `detect()`:
    - CalTopo GeoJSON → `parse_geojson`, unchanged;
    - CalTopo GPX → `parse_caltopo_gpx`;
    - onX or Cairn GPX/KML → reader, then adapter;
    - a GPX + KML pair → `merge_onx_gpx_and_kml` first, which keeps the KML polygon over the
      GPX `<rte>` of the same id.
  - **Preserve onX styling instead of re-guessing it** (KG §5.3).
    - Set `cairn_onx_icon_override` from the file. The item is `confirmed=True` and
      `needs_attention=False`.
    - Skip `IconResolver.resolve` and `resolve_waypoint_color`'s icon fallback for these items.
    - Flag an icon that isn't in `get_all_onx_icons()`.
    - Add a source branch to `_explain`: "Kept from your onX file."
  - **Keep the onX id** on every item in memory, even though nothing writes it yet. Phase 6
    needs it, and it's free now.
  - **Add the readers to `WEB_ENGINE`** in `tests/test_web_engine_surface.py`.
- **Tests:**
  - for each dialect fixture, `load_document` gives the expected counts by kind and folder;
  - every onX icon and colour is shown unchanged and marked confirmed;
  - `export_zip` on an onX input re-reads to the same items;
  - Bitterroots GeoJSON output is byte-identical to before, so there is no regression.
- **Exit criteria:**
  - All four input dialects load through the bridge in Python tests.
  - Exporting an onX input gives a zip whose re-read matches Phase 1's fidelity figure.
- **Effort:** M (1–2 days).
- **Depends on:** Phase 0 (detection). Phase 1 should land first, or the adapter will carry
  Phase 1's losses.
- **Open questions:** none blocking. The folder-per-file rule is an inference about how users
  will export. See Phase 3.

### Phase 3: Web UI for GPX/KML input

*Can start now, offline, with Playwright.*

- **Goal:** a user can drop onX or CalTopo GPX/KML files on the page and get the normal review
  screen.
- **User-visible outcome:**
  - The file picker accepts `.json,.geojson,.gpx,.kml`. You can pick several files, or drop a
    second file to add it.
  - Each file becomes one folder in the sidebar, named after the file.
  - onX-sourced items carry a "from your onX file" explanation.
  - A CalTopo GPX/KML shows the notice "CalTopo's GeoJSON keeps icons, colours and folders.
    Export that if you can." (KG §3.2).
  - The map title strips `.gpx` and `.kml` as well.
- **Web work** (`web/index.html`, `web/app.js`, `web/styles.css`):
  - `accept=` and `multiple` on the input;
  - multi-file read, passing the files to the bridge together so a GPX + KML pair merges;
  - title stripping;
  - the explanation text and the CalTopo notice;
  - an optional Line/Track/Area label from the sub-kind.
  - **Don't let this become "Load another map = add".** UI-12 relabelled that button "Start
    over" on purpose. Multi-file belongs to the *first* drop. Merging later loads is a separate
    deferred feature.
- **Folder recovery:** onX files carry no folder (FM, KG §2). The cheapest way to get folders
  back is for the user to **export one onX folder at a time** (per `docs/FAQ.md` and RS §1.6)
  and drop all the files at once, so each filename becomes a folder.
  - **[ASSUMPTION]** Users will tolerate one export per folder. The alternative is FM W3's
    `folder=` line in `<desc>`, which only helps files *Cairn* wrote earlier.
  - Whether onX lets you rename the export file, or always names it `onx-markups-<date>.gpx`
    (KG §3.4), affects how usable this is. Users may need to rename files before dropping them.
    The UI should let them rename a folder in Cairn instead. The UI already supports editing;
    check that folder rename exists.
- **Tests:** Playwright under the enforced CSP:
  - drop an onX GPX + KML pair and see the expected counts and preserved icons;
  - export and check the zip contents;
  - drop a CalTopo GPX and see the notice.

  Keep `test_page_boots_under_enforced_csp` green.
- **Exit criteria:** the e2e tests pass for each dialect, and no new CSP violations appear.
- **Effort:** M (1–2 days).
- **Depends on:** Phase 2.
- **Open questions:** whether onX's export dialog allows per-folder export with a meaningful
  filename. `docs/FAQ.md` (citing project docs) says onX can export one folder at a time, and
  RS §1.6 step 2 exports a single folder; the filename behaviour is unverified.
  The owner can see this during the P2 sitting.

### Phase 4: Validate against real onX files

*Blocked on P2. S once the files arrive.*

- **Goal:** replace every synthetic onX fixture with the owner's real exports, and fix whatever
  differs.
- **User-visible outcome:** none directly. This is what makes the announcement honest.
- **Work:**
  - commit P2's files to `tests/fixtures/onx_real/`;
  - point the Phase 1 and 2 tests at them;
  - create the `docs/ONX_BEHAVIOR.md` ledger (FM W6), recording each probe result with its date;
  - if the format differs from the decoded one, change the readers.
- **Tests:** the Phase 1–3 fidelity and e2e tests, re-run on the real files.
- **Exit criteria:**
  - Real onX GPX and KML exports load.
  - The round-trip diff on them loses only id and folder (or whatever P1 decides).
  - The ledger lists P1–P5 and P7 with results.
- **Effort:** S. M if the real format surprises us.
- **Depends on:** P2. P3, P5 and P7 should come from the same sitting.
- **Open questions:** P4 (iOS export). If phone exports carry only name and location, as onX's
  help says, document the feature as **Web Map export only**.

### Phase 5: Round-trip runbook ("replace" mode)

*P1 is answered (duplicates), so the wording is "replace": back up, delete the originals, import. Ready to build.*

- **Goal:** turn an exported onX account back into onX without duplicates, safely.
- **User-visible outcome:** when the input came from onX, the zip's RUNBOOK.md and the in-app
  runbook switch to a replace flow:
  1. **Keep the file you exported from onX. It is your backup.**
  2. In onX, **delete the original markups first, then their folders.** Deleting a folder
     doesn't delete its markups.
  3. Import the cleaned files, one batch per folder, with "Import map data to a new folder"
     ticked.
  4. Rename each `Import mm/dd/yy H:MM` folder, as the CalTopo runbook already says.

  The runbook also covers:
  - **Limits:** 3,000 markups per account and per import, 4 MB per file. "Delete first" is
    required, not just tidier, when the account is near the cap (KG §3.6).
  - **What is lost:** photos, share grants, and anything else onX keeps outside the file. Shared
    folders' recipients lose access to the deleted originals (RS §1.5). **[ASSUMPTION]** Shares
    are attached to the original markup ids.
- **Web and engine work:** a runbook variant in `web/bridge.py:build_runbook` and
  `web/app.js:renderRunbook`, selected by the input dialect. Fix the stale 1,500 figures
  everywhere to 3,000 in the same change.
- **Tests:**
  - snapshot tests of both runbook variants;
  - the warning fires at the right threshold;
  - the onX-input e2e test shows the replace wording.
- **Exit criteria:**
  - The wording matches P1's result.
  - The owner has followed the runbook once on the `ZZ Cairn Test` folder and ended with no
    duplicates.
- **Effort:** S.
- **Depends on:** Phase 2. **P1 decides the wording**: "replace" if imports duplicate, or
  Phase 6's "update" flow if they don't.
- **Open questions:**
  - P1.
  - Whether onX's bulk delete is practical for hundreds of markups. RS confirms bulk select in
    My Content; the bulk select caps at 100 for sharing (RS §2.1). Whether delete has a cap is
    **unknown**.

### Phase 6: Update in place (id write-back)

*Dropped 2026-10-22: P1 showed onX duplicates on re-import, even with matching ids.*

*Conditional. Exists only if P1 shows onX upserts by id.*

- **Goal:** a round trip edits the existing markups, so no delete step is needed and photos and
  shares survive.
- **User-visible outcome:** the runbook says "import; your existing markups are updated."
- **Work:** write the source onX id back, as `id=` in the GPX `<desc>` and as KML ExtendedData
  `id`. Phase 2 kept the ids in memory.
  - Decide what happens to items the user excluded in Cairn. They aren't in the file, so onX
    leaves them as they are. Say so.
- **Tests:**
  - the ids round-trip byte-exact;
  - excluded items are absent;
  - CalTopo-sourced output still writes **no** id.
- **Exit criteria:** the owner re-runs RS Test B with a Cairn-written file and sees the edits
  applied in place.
- **Effort:** S if P1 says upsert. **Drop the phase** if P1 says duplicate: a stale id is
  harmless at best and confusing at worst (KG §5.3).
- **Depends on:** P1 and Phase 4.

### Phase 7: CalTopo KML reader

*Blocked on P6. Lowest priority.*

- **Goal:** accept CalTopo KML for users who don't have the GeoJSON.
- **Work:** a `caltopo_kml.py`, or a generic-KML mode in `onx_kml.py`, per KG §3.3:
  - walk `<Folder>` into folders;
  - read `<description>`, stripping the HTML;
  - resolve `styleUrl` → `Style`/`StyleMap` colours (KML colour is `aabbggrr`);
  - read MultiGeometry and inner rings.
- **Exit criteria:** the P6 file loads with its folders and colours, and the CalTopo GeoJSON of
  the same map gives the same items.
- **Effort:** M.
- **Depends on:** P6 and Phase 2.
- **Open question:** whether CalTopo KML keeps folders and styles at all. The research found
  conflicting statements (KG §3.3). If it keeps neither, ship it as "accepted, but export
  GeoJSON".

---

## 4. Sequencing at a glance

| Phase | Needs onX access? | Effort | Can start |
|---|---|---|---|
| 0 Safety + detection | no | S–M | now |
| 1 Reader/writer fidelity | no | M–L | now, after this branch's writer and parser changes are committed |
| 2 Bridge adapter | no | M | after 0; ideally after 1 |
| 3 Web UI input | no | M | after 2 |
| 4 Real-file validation | **P2** (plus P3, P5, P7) | S | when files arrive |
| 5 Replace-mode runbook | **P1** for wording | S | draft now; ship after P1 |
| 6 Update in place | **P1 = upsert** | S or dropped | after P1 and 4 |
| 7 CalTopo KML | **P6** | M | when the file arrives |

**Total:**

- **Offline, Phases 0–3:** about 5–7 days.
- **With the owner's files, Phases 4–5:** about 1 more day.
- **Phase 6:** a day or nothing, depending on P1.

**Critical path to the announcement:** 0 → 1 → 2 → 3, with the owner's one sitting running in
parallel, then 4 → 5.

---

## 5. Announcement-worthy milestone

**Announce "Cairn now reads GPX and KML, including your onX exports"** only when all of these
are true:

1. **Real files, not synthetic ones.** A real onX **Web Map** GPX and KML export (P2) is
   committed as a fixture, and the e2e suite loads both under the production CSP.
2. **Faithful by the numbers.** onX GPX + KML → Cairn → onX output loses nothing but what onX
   itself can't carry:
   - the folder, unless one export was made per folder;
   - waypoint elevation in GPX;
   - the onX id, unless Phase 6 ships.

   Icons, colours, notes, line style and weight, Line/Track/Area type and area holes all
   survive. A test asserts this on the real fixture.
3. **Safe to follow.** The round-trip runbook's wording matches P1's actual result. The owner
   has done one full round trip on a `ZZTEST` folder and ended with the right markup count and
   no duplicates.
4. **Honest about scope.**
   - Web Map exports only, unless P4 shows the iOS app's exports work too.
   - onX Backcountry only (UI-24).
   - CalTopo GPX is accepted, with the "prefer GeoJSON" notice.
   - CalTopo KML is stated as supported **only** if Phase 7 shipped.
5. **The numbers are current.** No "1,500" remains anywhere. The account and per-import limits
   are both 3,000, as onX's help centre says.

Hold the announcement if **any** of these is missing:

- P1 has not been answered;
- the round trip has only been proven on synthetic files.

**Don't claim:** "update your onX markups in place" unless Phase 6 shipped and was verified.

---

## 6. Assumptions and risks

- **[ASSUMPTION]** onX's Web Map export format stays as decoded on 2026-10-22. Bundle hashes
  rotate on every onX deploy (RS), and the help centre already contradicts the code (KG §1.6).
  Phase 4 is the guard against this. Re-check the format whenever an import breaks.
- **[ASSUMPTION]** Most users' "messy onX account" is under 4 MB per export. onX simplifies any
  line over 300 vertices on export (KG §2), so a round trip can never be more faithful than
  onX's own export. Say that in the FAQ.
- **Risk:** "delete first" is the riskiest step we would ever ask a user to take. The backup
  export file is the mitigation. **[ASSUMPTION]** Re-importing that backup restores the
  original state, minus photos and shares. It is not tested.
- **Risk:** `writers.py` and `web/bridge.py` are being edited in parallel on this branch.
  Phases 0–2 all touch them, so commit the current branch work before starting.
- **Not in this roadmap:**
  - any use of KML `<Folder>` to create onX folders (FM rules it out);
  - onX products other than Backcountry;
  - mobile (ENG-02);
  - merging several CalTopo maps (UI-12, deferred separately).
