# Cairn backlog

The one list of what's open, what waits on the owner, and what shipped. It is not a work queue:
the owner picks what gets built. Decisions and their reasons live in `docs/design/DECISIONS.md`
(UI-NN / ENG-NN); live onX results in `docs/ONX_ROUND_TRIP.md`.

Consolidated 2026-10-25 from the old TODO, the GPX/KML input roadmap and the folders release
log's follow-ups. Every open item below was re-checked against the code that day. The old
roadmap and the 2026-08-29 audits are archived (`git show cdd25f3:docs/<name>`).

---

## Open: can be built now

Small engine fixes: none open (the last ones shipped 2026-10-25, below).

Wording follow-up (owner, 2026-10-25; LABELS.md §15 #8):

* **Error and failure messages: one pattern.** Today's variants, all to review together:
  * Status-line prefixes (app.js): `Failed: {reason}` (engine boot, :239) · `Export failed: {reason}`
    (:2120) · `Download failed: {reason}` (:2193) · `Couldn't read that file — {reason}` /
    `Couldn't read those files — {reason}` (:386) · `Couldn't move / make a folder / remove — {reason}`
    (:1654) · `Couldn't rename — {reason}` (:1826) · `Failed: Could not load file` (unreadable GeoJSON,
    shown alone).
  * Plain error sentences (app.js): `An item needs a name.` · `A folder needs a name.` ·
    `A folder name can be up to 100 characters.` · `“{name}” already exists.` ·
    `Everything is excluded — include at least one item to export.`
  * Thrown inside app.js, shown after a prefix: `Couldn't load the map engine (HTTP N).` ·
    `Lost track of item {uid}.` · `The folders no longer add up.` · `That folder name is taken.`
  * bridge.py, shown after "Couldn't read that file —": `{file} couldn’t be read: {reader's first
    line}` (the reader lines are `Invalid GPX file (XML parse error): …`, `GPX file is empty`,
    `Invalid KML file (XML parse error): …`, `File does not appear to be a KML file (root element: …)`,
    `No placemarks found in KML file`, `Failed to read GPX/KML file: …`) · `This isn't a map file
    Cairn can read. …` · `Cairn found no waypoints, lines or areas in {names}. …` · `No file was
    given to open.` · the input guard's 16 MB and `<!DOCTYPE>` sentences.
  * bridge.py folder/move errors: `There is no folder '{key}' in this map.` · `No items were given
    to move.` · `Move items to one folder: give a folder or a new folder name.` · `Unknown item(s):
    …` · `“{name}” isn’t empty, so it can’t be removed.` · `No exported folder N. Export again.`
  * Developer-only (shouldn't reach a user): `Unknown line style / line weight / Unsupported area
    fill … for {uid}`.
  Decide one prefix pattern ("Failed: …" vs "Couldn't X — …"), whether reader details are shown, and
  curly vs straight apostrophes (bridge uses ’, app.js uses '), then apply in one pass.

Web app features:

* **Add another map** (UI-12): load a second CalTopo map into the one open, deduped. The engine
  has `core/merge.py` / `dedup.py`; the web app doesn't call them. Today "Start over" resets.
* **Folder name in item names or notes**, as an export option.
* **Load time.** Watch it; the ideas so far are running Pyodide in a Web Worker and a memory
  snapshot.

## Open: needs the owner's account or a file

Each needs one sitting in onX or CalTopo. Never delete onX data without the owner.

* **onX phone app exports** (old roadmap P4): does the iOS app's GPX carry the `onx:`
  extensions and `<desc>` lines, or only name and location? Decides whether the round trip
  works from a phone or only from the Web Map.
* **Track times and waypoint elevation** (P7): does onX read `<time>` and `<ele>` on import?
* **One styled CalTopo export** (GeoJSON + KML + GPX of one small map with a dotted line, an
  arrow line, an unfoldered marker, a multi-part area and an area with a hole). Answers:
  * CalTopo's `pattern` values for dotted and arrow lines (only solid and one dash are known;
    the rest export as solid);
  * what CalTopo's GPX does with an area, and whether its `DisplayColor` is exact or nearest;
  * how CalTopo's KML writes a multi-part area and a hole;
  * what the `#1.0` at the end of every icon `cfg` means (not marker size);
  * whether to map the KML's "Points" / "LineStrings" / "Polygons" folders for unfoldered items
    to "Unorganized", as the GeoJSON gets.
* **Can onX keep a hole in an area?** An area with a cutout (an inner ring) is written as its
  outer ring only, because a GPX onX Area route has one outline (ENG-05, provisional). Untested
  in onX: whether any import path keeps the hole, or whether writing each hole as its own area
  is better. No real map so far has had one.
* **Do line breaks in notes survive into onX?** Probe: a GPX whose `<desc>` has literal
  newlines, `&#10;`, escaped `<br>`, and a blank line; import, read Notes on web and phone, then
  type a two-line note in onX and export it.

## Next feature: bulk rename and note change

* **Rename… and Change note…** in More (UI-17), with a live before/after preview. Phased,
  red-teamed plan for parallel implementation agents: [`docs/plans/BULK_RENAME.md`](docs/plans/BULK_RENAME.md).
  Phase 0 needs the owner: pick the dialog mockup, say yes/no to the duplicate-name flag, approve
  the wording.

## Major feature: investigate, then build

* **Avalanche Bridge** — put local avalanche-center field observations (point-level evidence
  behind the zone ratings onX already shows) onto the onX map as importable markups. Draft
  proposal: `docs/ROADMAP_AVALANCHE_BRIDGE.md` (2026-10-22, not yet committed; another session
  wrote it). Next step: settle its UNKNOWNs (data sources and their terms, refresh cadence,
  how a user re-imports updates without duplicates), then plan the build.


## Ideas, not planned

* **KMZ input and generic GPX routes.** Plans written 2026-10-23 on branch
  `worktree-input-formats-plan` (never merged; copies in `docs/archive/2026-10-23-*.md`).
* **Name for the no-folder group and the "everything" facet** — "Unorganized" and "All" are
  marked provisional (UI-10, UI-14).

---

## Done

Newest first. Details are in DECISIONS and `docs/testing/FOLDERS_RELEASE.md`.

* **2026-10-25 leftovers:** `MultiPoint`, `MultiLineString` and `GeometryCollection` split into
  one markup per part instead of being dropped; characters XML forbids are dropped from every
  written name and note (one control character used to break a whole GPX); `instructions.txt`
  marks long notes and lost holes on the very item, not every item with that name; "Use note
  as name" leaves a blank-note row alone; `save_user_mapping` needs an explicit path; boot,
  export and download errors show a plain message, not a traceback.
* **2026-10-25 maintenance:** `Camp2`-style numbered names find their icon; the duplicate
  `Camp` config entries are gone; `load_config(None)` no longer reads the current directory; the
  dead KML warning is removed; `<Lake>` survives in notes; `instructions.txt` gives onX-sourced
  maps the delete-then-import steps, and the FAQ now says delete first; error and long-note
  wording made consistent; `web/serve.py` takes `PORT`. Docs: one backlog here, expired docs
  archived, `docs/DEPLOY.md`, a trimmed README with a how-it-works diagram.
* **PR #45 (2026-10-24):** keyed in-place rendering of the rail and folder list; icon keywords
  read the name before the note and a tie goes to the later word, "AS" reads as aid station
  (ENG-08); AGENTS.md style guide.
* **PR #44 (2026-10-24), the folders release:** stable item ids (ENG-07); folders made,
  renamed, merged and filled by drag or Move to… (UI-32); export screen with one box per folder
  and `instructions.txt` (UI-31); hover for whole names and notes, caution marks, sort by name,
  one editing panel, Back/Forward, sticky nav (UI-33..38); FAQ and walkthrough pages.
* **PR #42 (2026-10-23):** onX area and track style/weight pass through; area-fill warning
  with an option to leave those areas out (UI-30); solid/dash and 4.0/6.0 line editing (UI-25).
* **onX round-trip testing (2026-10-22..23):** re-import duplicates, ids or not, so "update in
  place" was dropped; areas export as GPX onX Area routes because onX ignores KML area colours
  (ENG-05); onX keeps area style and weight, never the fill; names pass through unchanged, the
  `! @ # $ % ^ * &` stripping is gone (ENG-06); notes over 512 bytes are cut by onX and flagged.
* **GPX and KML input (2026-10-22):** input guard and format detection (`input_check`), onX
  GPX/KML readers wired into the bridge, CalTopo KML and GPX readers with parity tests, GPX/KML
  in the web UI. Real onX exports are fixtures (`tests/fixtures/onx_real/`, `onx_exports/`).
* **2026-10-22 review fixes:** area colours on onX's palette, holes, stroke and fill opacity,
  `MultiPolygon` split, area names sanitized like the rest, the account limit at 3,000 (was
  1,500), cabin/hut/yurt map to Shelter, `strip_html` only strips tag-shaped text.
* **Web-only (2026-10-21):** CLI and TUI deleted (git tag `cli-final`); redesign rounds 1–5
  (UI-01..UI-24): one light theme, onX-style markers, multi-line notes editor (UI-13),
  icon filter (UI-28), list icon picker (UI-29), folder facets.
* **Earlier (2026-08-29..30):** `<desc>` carries only the user's note; the engine no longer
  writes into its own package; multi-line notes kept at parse time; the import-batch
  instructions (now `instructions.txt`); the web app deployed at quietmarch.to/cairn.

### Dropped

* "Move the unmapped-symbol warning to the start": the web app shows Default pin as soon as a
  map loads.
* "Investigate whether onX re-import can update in place": it can't (ONX_ROUND_TRIP.md).
* "Workflow redesign" (2026-08-29): written for the TUI; the web redesign replaced it.
* "How onX renders KML `<width>` and PolyStyle fill" and "is the KML size cap 4 MB": areas
  export as GPX now (ENG-05), and no export file is KML.
* "CalTopo `pattern` on areas is not carried": it is now, as the GPX Area route's `onx:style`
  (ENG-05), and the editor sets solid or dash (UI-36).
