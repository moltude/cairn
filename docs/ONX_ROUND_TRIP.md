# onX round trip: can an import ever update a markup in place?

Live runs on 2026-10-23, 14:30–15:16 UTC, in the owner's onX Backcountry account, through the
Web Map (`backcountry.onxmaps.com`) in the owner's logged-in Chrome. Raw files are gitignored
and kept locally under `tests/fixtures/roundtrip/<test-id>/`. Each test folder has a tracked
`README.md`. This doc replaces `docs/ONX_ROUND_TRIP_IDENTITY.md` (run id1), whose findings are
folded in below as [`new-folder-gpx-with-ids`](#new-folder-gpx-with-ids),
[`new-folder-kml-with-ids`](#new-folder-kml-with-ids) and
[`new-folder-cairn-output`](#new-folder-cairn-output).

Contents: [Summary](#summary) · [Test index](#test-index) · [Method](#method) ·
[What the Web Map offers](#import-paths) · [Tests](#tests) · [Export format](#format-inventory) ·
[Confidence and limits](#confidence) · [Implications for Cairn](#implications) ·
[Created in onX](#created) · [Re-running](#rerun) · [Appendix](#appendix)

<a id="summary"></a>
## Summary of conclusions

1. **No import path updated an existing markup in place.** Every import created new markups
   with new uuids, and every existing markup's server record stayed identical field for field,
   `updatedAt` included. This held for each of these cases:
   - importing without a new folder, as GPX ([`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids))
     and as KML ([`no-folder-kml-with-ids`](#no-folder-kml-with-ids));
   - putting the imported copy into the originals' own folder
     ([`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids)) or into another
     folder ([`another-folder-gpx-with-ids`](#another-folder-gpx-with-ids));
   - importing into a new folder, which run id1 tested
     ([`new-folder-gpx-with-ids`](#new-folder-gpx-with-ids),
     [`new-folder-kml-with-ids`](#new-folder-kml-with-ids),
     [`new-folder-cairn-output`](#new-folder-cairn-output));
   - re-importing an unmodified export, GPX ([`reimport-unmodified-gpx`](#reimport-unmodified-gpx))
     or KML ([`reimport-unmodified-kml`](#reimport-unmodified-kml));
   - a copy with the same name, coordinates, note and style but no onX id
     ([`same-name-coords-no-ids`](#same-name-coords-no-ids));
   - re-importing an older export after the original was edited in onX: the edit was **not**
     reverted ([`onx-edit-then-reimport`](#onx-edit-then-reimport));
   - two full export → modify → import cycles
     ([`multi-step-cycle-gpx`](#multi-step-cycle-gpx)).
2. **There is no way to import into an existing folder.** The import dialog has one option, the
   "Import map data to a new folder" checkbox, which is unticked by default. Unticked, the
   markups land in no folder; ticked, onX creates a folder named `Import mm/dd/yy H:MM`. The
   client code sends a folder id only in the ticked case, and only for the folder it has just
   created. To get imported markups into an existing folder you must import and then use the
   folder's **Add Content**, which only adds membership. See [What the Web Map offers](#import-paths).
3. **onX reads no identity from the file.** In GPX, the `<desc>` `id=` line is stored as note
   text ([`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids)). KML `<ExtendedData>` is ignored
   completely: the note, icon and colour all come back as onX defaults
   ([`no-folder-kml-with-ids`](#no-folder-kml-with-ids),
   [`reimport-unmodified-kml`](#reimport-unmodified-kml)). onX does not dedupe on content either
   ([`same-name-coords-no-ids`](#same-name-coords-no-ids)).
4. **The method can see a real change.** Editing a waypoint in onX set its `updatedAt` and
   `lastSyncedAt` to 15:08:50.225Z, a minute after its `createdAt` of 15:07:47.803Z. Its next
   export showed the new name and note
   ([`onx-edit-then-reimport`](#onx-edit-then-reimport)). No import ever caused such a change.
5. **Each GPX round trip nests another `<desc>` block into the note.** Each cycle adds about
   150–180 bytes and one more `id=` line ([`multi-step-cycle-gpx`](#multi-step-cycle-gpx)).
6. **An onX export is not stable byte for byte, even for an unchanged folder.** `<trkpt><time>`
   is the moment of export. Element order follows the folder's internal list, so two exports of
   the same unchanged folder can list the same markups in a different order
   ([`multi-step-cycle-gpx`](#multi-step-cycle-gpx), [Export format](#format-inventory)).
   Comparing exports needs to key on the markup id, not on file position or bytes.
7. **An imported track's `createdAt` comes from the file's point times**, and that survives
   repeated cycles. A second-generation copy still claimed to have been created at the moment
   of the first export ([`multi-step-cycle-gpx`](#multi-step-cycle-gpx)).

In short: an onX import adds and never updates. The only way to "replace" a markup is to
delete it and import the new version.

<a id="test-index"></a>
## Test index

"Unticked" means "Import map data to a new folder" was not ticked. Every test used one
waypoint, one line and one area.

| ID | Title | Import path | File kind | Result |
|---|---|---|---|---|
| [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids) | Edited onX GPX, ids kept, imported without a folder | unticked | GPX | 3 new markups, unfiled; originals untouched |
| [`no-folder-kml-with-ids`](#no-folder-kml-with-ids) | Edited onX KML, ids kept, imported without a folder | unticked | KML | 3 new (the line becomes an onX *Line*); originals untouched; ExtendedData ignored |
| [`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids) | Edited GPX copy added to the originals' own folder | unticked, then Add Content into the originals' folder | GPX | Folder holds both copies (6 items); originals untouched |
| [`another-folder-gpx-with-ids`](#another-folder-gpx-with-ids) | Edited GPX copy added to another existing folder | unticked, then Add Content into another folder | GPX | 3 new in the other folder; originals untouched |
| [`reimport-unmodified-gpx`](#reimport-unmodified-gpx) | onX's own GPX export re-imported byte for byte | unticked | GPX | 3 duplicates with identical names; originals untouched |
| [`reimport-unmodified-kml`](#reimport-unmodified-kml) | onX's own KML export re-imported byte for byte | unticked | KML | 3 duplicates, styling lost; originals untouched |
| [`same-name-coords-no-ids`](#same-name-coords-no-ids) | Content-identical copy with no onX id | unticked | GPX | 3 duplicates indistinguishable except by uuid; originals untouched |
| [`onx-edit-then-reimport`](#onx-edit-then-reimport) | Edit in onX, then import the older export | unticked | GPX | 3 new; the in-onX edit is kept, not reverted |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | export → modify → import → export → modify → import → export | unticked, then Add Content into a new folder each cycle | GPX | 3 new per cycle; nothing in place at either step; notes nest |
| [`new-folder-gpx-with-ids`](#new-folder-gpx-with-ids) | (run id1) Edited GPX, ids kept, new folder | ticked | GPX | 3 new; originals untouched |
| [`new-folder-kml-with-ids`](#new-folder-kml-with-ids) | (run id1) Edited KML, ids kept, new folder | ticked | KML | 3 new; ExtendedData ignored |
| [`new-folder-cairn-output`](#new-folder-cairn-output) | (run id1) Cairn's own output (no ids), new folder | ticked | GPX ×3 | 3 new; originals untouched |

<a id="method"></a>
## Method

**Naming.** Each test has a word ID, used everywhere:

- onX folders are named `ZZTEST · <test-id> · <stage>`;
- markup names are `ZZTEST <test-id> · <kind>` plus ` · <stage>` once edited;
- raw files are `<test-id>.<stage>.<gpx|kml>`.

The stages are words: `original` (the hand-written upload), `export-1`, `edited` (or
`stripped`), `reimported-export`, `export-2`, `edited-2`, `export-3`. Re-exports of a different
folder within the same test say so: `original-folder.export-2`, `reimported-folder.export-3`.
Each test sits on its own patch of map north of Mt Adams, WA (latitude 46.24 + 0.02 × the
test's position in the index), clear of id1 and of any non-test content.

**Steps common to every test.**

1. Import `<test-id>.original.gpx` with the box ticked, then rename the new
   `Import 10/23/26 H:MM` folder to `ZZTEST · <test-id> · original`.
2. Export that folder as GPX and as KML (`export-1`). Export uses the folder's
   "…" → **Export Folder Contents** → GPX/KML → **Save**.
3. Derive the test file from `export-1` by text replacement only (scripted; each replacement
   and its count is logged).
4. Import the test file. "Unticked" means the box was verifiably unchecked
   (`input.checked === false`) at the moment Import was clicked.
5. Snapshot the store, then re-export the originals' folder (`export-2`) and diff it against
   `export-1`.

**Evidence, all read-only.**

- *Exports*: every GPX and KML export is kept. It was taken from `~/Downloads` only if it was
  under 2 minutes old, and was moved out at once (the `scripts/onx_fetch_export.sh` rule).
- *The import call*: `POST /v1/markups/import`, sent by the page. For
  [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids) the request and response bodies are saved
  under `net/`. For every test the response's uuid list was read from the importer's own state
  (`bVmq` module, `_markupIds`), which is that same response.
- *Markup records*: after each import the page re-fetches the whole account
  (`GET /v1/markups/{waypoints,tracks,shapes,lines}`, the page's own requests). The in-memory
  store those responses fill was read with a script, which made no request of its own. Each
  snapshot (`net/snap.*.json`) holds, for every test markup, the uuid, name, notes,
  `createdAt`, `updatedAt`, `lastSyncedAt`, colour, properties and geometry. It also holds a
  SHA-256 digest over `[uuid, type, updatedAt, name, notes, geometry]` of every *other* markup
  in the account, plus the folder list with members. Unlike id1, raw API bodies were saved per
  step only for the baseline (`account-baseline/net/*.json`, the page-load lists at 14:35:18Z)
  and for test 1. The other steps rely on the store snapshots.
- No API request of Claude's own was sent. The page's own writes were the imports, folder
  creations, renames and Add Content that the steps above caused, plus its usual
  `PUT /v1/preferences` and `PUT /layer-management/v1/layer-settings` on load.

**Diff normalisation.** onX writes each file on one line. Every diff below inserts a newline
between each `><` pair and changes nothing else. Text whitespace, attribute order, number
formatting and element order are all compared as is.

**Account totals.** At baseline (14:35Z) the account held 445 waypoints, 188 tracks, 12 areas,
1 line, 2 routes (648) and 14 folders: 13 of the owner's, plus the empty probe folder created a
minute earlier to inspect folder menus. At the end (15:16Z, after a fresh reload) it held 464,
205, 31, 3 and 2 (705), and 27 folders. That is exactly +57 markups from 19 imports of 3
markups each, and +13 folders. The digest over the 648 non-test markups was
`1d114774e8ec2acf…` at the first snapshot (14:40Z) and at the last one, and at every snapshot
in between.

**Disclosures.**

- The account still holds `[r1i1]`, `[r1i2]`, `[r2i1]` and `[r2i2]` ZZTEST markups from the
  2026-10-22 runs (for example `[r1i1] ZZTEST blank lines`). The owner believed they had been
  deleted. This run did not touch them. They are inside the unchanged 648-markup digest.
- **Near miss.** In [`no-folder-kml-with-ids`](#no-folder-kml-with-ids), the first version of
  the Add Content selection script also ticked the owner's line "Route 10/22/26 13:47". Its
  row-matching walked up into a container that held two rows. The extra tick was seen and
  removed **before** Done was pressed. The folder's members were then read back and are
  exactly the three test markups. The script was fixed to match only a row's own text, and to
  refuse any row whose name does not start with `ZZTEST`. The owner's line was never added to
  any folder or changed: its record is inside the unchanged digest.
- Chrome blocks a second download that a script click starts, because there is no user
  gesture. One `export-2.kml` attempt failed this way and was redone. From then on, Save was
  focused by script and pressed with a real Enter key. One navigation hit a transient
  `ERR_CONNECTION_CLOSED`, and was retried.
- In [`reimport-unmodified-gpx`](#reimport-unmodified-gpx),
  [`reimport-unmodified-kml`](#reimport-unmodified-kml),
  [`same-name-coords-no-ids`](#same-name-coords-no-ids) and
  [`onx-edit-then-reimport`](#onx-edit-then-reimport), the new copies have the same names as
  the originals. Add Content lists rows by name only, so they could not be told apart there
  and were left unfiled. [Created in onX](#created) lists their uuids.

<a id="import-paths"></a>
## What the Web Map offers

What the UI shows, observed on 2026-10-23:

| Where | What it offers |
|---|---|
| My Content → **Import** (also under "more actions") | "Import files" card: a drop zone ("Drag your KML or GPX file(s) here"), **Select from computer** (`accept=".gpx,.kml"`, multiple files), "Maximum file size 4 MB", the checkbox **Import map data to a new folder** (unticked by default), Import / Cancel. **No folder picker. No merge or replace option.** |
| Import Complete card | "N Items Imported Successfully", lists per kind, **Show on Map**, one unlabelled button (not identified) |
| My Content → "more actions" | Hide All, Select, Export, Import |
| Folder tile → Open Menu | Hide Folder on Map, Share, Delete |
| Folder page | **Share**; "…" → Manage Access, Rename Folder, Export Folder Contents (only when the folder is not empty), Delete Folder; "Hide folder on map"; "Only show this folder on the map"; Notes (512 characters); **Add Content** (pick existing markups to add) |
| Folder page → a markup's menu | Edit waypoint (or line, area), Hide on map, **Export** (one markup), Remove from folder |
| Export dialog | "Please choose a file type": GPX (default) / KML, then "Save (N)". It warns that "some information, including photos and content shared with you, cannot be exported." |

What the client code shows. The bundles were fetched as static files from the page:
`50657.87e3701dffd2f41a9e91.js` (the importer, the same hash as on 2026-10-22) and
`98770.bf04e6cb10482fd61f4c.js` (the import card).

```js
f=async(_,l=!1,w="")=>{ …
  const n=l?await r.A.addCollection({name:"Import"+(0,E.Ay)(new Date," mm/dd/yy H:MM")}):null, …
  c.append("type",a.type), c.append("file",a.rawData), n&&c.append("collection-id",n);
  const s=await(0,k.hu)("/v1/markups/import",c,{},!1); …
  l&&(await r.A.requestCollections(), r.A.isCollectionEmpty(n)&&(r.A.deleteCollection(n),…))
```

```js
pt=async()=>{ … await(0,m.lD)(l.value,v.value,tt.meta.fromRoute) … }   // import card: files, checkbox, route
```

- The importer has exactly one caller, the import card. Its arguments are the file list, the
  checkbox value and `fromRoute`, which is only used for analytics (`origin`).
- `collection-id` is attached only when the checkbox is ticked, and it is always the folder the
  client has just created. No code path can target an existing folder.
- When ticked, the client deletes the new folder again if the import left it empty.
- The import card's own drop area (`data-test="import-drop-area"`) is the only drop handler that
  feeds the importer. A generic drop-zone helper exists in a shared bundle, but its users were
  not traced. Dropping a file onto a folder or onto the map was therefore not exercised.
- Observed on the wire ([`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids)): the unticked
  import is one multipart `POST /v1/markups/import` with only `type` and `file`. There is no
  `collection-id` and no `create_content_collection` call. The ticked import sends
  `collection-id` after a `POST /v1/content-collections/create_content_collection`.
- **Sharing** is a different mechanism. Code in `28452.82d4fd468f694a173259.js` shows
  `POST /v1/sharing/shares?link=webmap` with `entities` and a link role (view-only by
  default), grants under `/v1/sharing/grants`, and a 409 "requesting user created this share"
  when you open your own link. It shares the live entities by reference, and no file is
  involved. It was not exercised, because creating a share is a server write this run had no
  need for.

<a id="tests"></a>
## Tests

<a id="no-folder-gpx-with-ids"></a>
### `no-folder-gpx-with-ids`: edited onX GPX, ids kept, imported without a folder

**Question.** Does an import that names no folder update the markups whose ids it carries?

**Steps.**

1. 14:39Z: imported `original.gpx` (ticked). Folder
   `d8fd6867-202e-4fea-9157-e9ad50362ccc` was renamed `ZZTEST · no-folder-gpx-with-ids · original`.
2. 14:41Z: `export-1` (GPX and KML).
3. `edited.gpx` = `export-1.gpx` with 13 replacements. The three names and their `name=` lines
   gained ` · edited`, each note `original <kind> note` became `edited <kind> note`, and the
   waypoint's colour (`color=` and `<onx:color>`) went from `rgba(255, 51, 0, 1)` to
   `rgba(8, 122, 255, 1)` and its icon (`icon=` and `<onx:icon>`) from `Summit` to `Camp`.
   All three `id=` lines were left in.
4. 14:42:27Z: imported `edited.gpx`, unticked.
5. 14:43Z: `export-2` of the originals' folder. The three new markups were then put into a new
   folder `ZZTEST · no-folder-gpx-with-ids · reimported` (`1ee20f00-ec53-44fb-8560-f436e5c7d6ea`)
   and exported (`reimported-export`).

**On the wire** (`net/reimported.import-request.json`, `net/reimported.import-response.json`):
`content-length: 2427` = multipart overhead + the 2112-byte file. The parts were `type=gpx`
and `file`, with no `collection-id`. No `create_content_collection` call was made. The
response listed only new uuids:
`{"markups":["519df497-cfae-4e03-ad14-b9b7fea3e794","e8a6d257-1843-4fd2-9aef-92ba3362ca09","bb0f9c00-79e5-4a55-8243-b3512988355f"]}`.
By comparison, the ticked original import (`net/original.create-folder-request.json`) created
folder `d8fd6867-…` named `Import 10/23/26 8:39` and sent `collection-id=d8fd6867-…`.

**Records.**

Store snapshots `net/snap.after-original-import.json` (14:40:42.453Z) → `net/snap.after-reimport.json` (14:42:57.504Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST no-folder-gpx-with-ids · waypoint` | waypoint | `47872e75-1406-44f1-8275-73979705847a` | 14:39:25.865Z | 14:39:26.226Z | 14:39:26.226Z | no (identical) |
| existing | `ZZTEST no-folder-gpx-with-ids · line` | track | `52efaa65-c386-4060-b3a5-3384d82cd917` | 14:39:25.865Z | 14:39:25.865Z | 14:39:25.865Z | no (identical) |
| existing | `ZZTEST no-folder-gpx-with-ids · area` | area | `28b5bfba-8279-4844-94b1-78c15b022e6f` | 14:39:25.865Z | 14:39:25.865Z | 14:39:25.865Z | no (identical) |
| **new** | `ZZTEST no-folder-gpx-with-ids · waypoint · edited` | waypoint | `519df497-cfae-4e03-ad14-b9b7fea3e794` | 14:42:27.023Z | — | 14:42:27.419Z | created |
| **new** | `ZZTEST no-folder-gpx-with-ids · line · edited` | track | `bb0f9c00-79e5-4a55-8243-b3512988355f` | 14:41:24.746Z | — | 14:42:27.024Z | created |
| **new** | `ZZTEST no-folder-gpx-with-ids · area · edited` | area | `e8a6d257-1843-4fd2-9aef-92ba3362ca09` | 14:42:27.023Z | — | 14:42:27.023Z | created |


The new track's `createdAt` (14:41:24.746Z) is `export-1`'s `<trkpt><time>`, which is a moment
before the track existed.

**Full-file diffs.** `export-1` → `export-2` for the originals: the KML is byte-identical, and
the GPX differs only in the four `<trkpt><time>` values:

```diff
--- no-folder-gpx-with-ids.export-1.gpx
+++ no-folder-gpx-with-ids.export-2.gpx
@@ -51,3 +51,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:41:24.746Z</time>
+<time>2026-10-23T14:43:55.822Z</time>
 </trkpt>
@@ -55,3 +55,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:41:24.746Z</time>
+<time>2026-10-23T14:43:55.822Z</time>
 </trkpt>
@@ -59,3 +59,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:41:24.746Z</time>
+<time>2026-10-23T14:43:55.822Z</time>
 </trkpt>
@@ -63,3 +63,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:41:24.746Z</time>
+<time>2026-10-23T14:43:55.822Z</time>
 </trkpt>
```

`edited.gpx` → `reimported-export.gpx`. This is what onX made of the upload: the whole
uploaded `<desc>` became the new note, and onX wrote its own block after it. The `<rte>` and
`<trk>` also swap places:

```diff
--- no-folder-gpx-with-ids.edited.gpx
+++ no-folder-gpx-with-ids.reimported-export.gpx
@@ -5,4 +5,8 @@
 <desc>name=ZZTEST no-folder-gpx-with-ids · waypoint · edited
+notes=name=ZZTEST no-folder-gpx-with-ids · waypoint · edited
 notes=edited waypoint note
 id=47872e75-1406-44f1-8275-73979705847a
+color=rgba(8, 122, 255, 1)
+icon=Camp
+id=519df497-cfae-4e03-ad14-b9b7fea3e794
 color=rgba(8, 122, 255, 1)
@@ -14,23 +18,2 @@
 </wpt>
-<rte>
-<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST no-folder-gpx-with-ids · area · edited</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST no-folder-gpx-with-ids · area · edited
-notes=edited area note
-id=28b5bfba-8279-4844-94b1-78c15b022e6f
-type=Area
-color=rgba(132,212,0,1)
-weight=4.0
-fill_color=rgba(74,144,226,0.1)</desc>
-<type>Area</type>
-<extensions>
-<onx:color>rgba(132,212,0,1)</onx:color>
-<onx:weight>4.0</onx:weight>
-<onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
-</extensions>
-<rtept lat="46.25" lon="-121.5"/>
-<rtept lat="46.25" lon="-121.49"/>
-<rtept lat="46.255" lon="-121.49"/>
-<rtept lat="46.255" lon="-121.5"/>
-<rtept lat="46.25" lon="-121.5"/>
-</rte>
 <trk>
@@ -38,4 +21,9 @@
 <desc>name=ZZTEST no-folder-gpx-with-ids · line · edited
+notes=name=ZZTEST no-folder-gpx-with-ids · line · edited
 notes=edited line note
 id=52efaa65-c386-4060-b3a5-3384d82cd917
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0
+id=bb0f9c00-79e5-4a55-8243-b3512988355f
 color=rgba(8,122,255,1)
@@ -67,2 +55,29 @@
 </trk>
+<rte>
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST no-folder-gpx-with-ids · area · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST no-folder-gpx-with-ids · area · edited
+notes=name=ZZTEST no-folder-gpx-with-ids · area · edited
+notes=edited area note
+id=28b5bfba-8279-4844-94b1-78c15b022e6f
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)
+id=e8a6d257-1843-4fd2-9aef-92ba3362ca09
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)</desc>
+<type>Area</type>
+<extensions>
+<onx:color>rgba(132,212,0,1)</onx:color>
+<onx:weight>4.0</onx:weight>
+<onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
+</extensions>
+<rtept lat="46.25" lon="-121.5"/>
+<rtept lat="46.25" lon="-121.49"/>
+<rtept lat="46.255" lon="-121.49"/>
+<rtept lat="46.255" lon="-121.5"/>
+<rtept lat="46.25" lon="-121.5"/>
+</rte>
 </gpx>
```

GPX styling was taken from `<extensions>`: the new waypoint is `Camp` and
`rgba(8, 122, 255, 1)`. The area's uploaded `onx:fill_color` was ignored, as on every import:
see [Export format](#format-inventory).

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `no-folder-gpx-with-ids.edited.gpx` | 2112 | `85f2ca180bdb8cd7ca0680acc1aff9014824b47622068b12faacb06977784153` |
| `no-folder-gpx-with-ids.export-1.gpx` | 2060 | `c3be6f4bec8f49dade3401646e27c8246c2786b31b5009023d5ea3e1e4299149` |
| `no-folder-gpx-with-ids.export-1.kml` | 1902 | `2b5c6bdd9d0fe560d73185562d4dcda75cbc5b7933755a81a3e21e6f5f716625` |
| `no-folder-gpx-with-ids.export-2.gpx` | 2060 | `c2fac014c6d95ebecaf30e30ce14271b64729612fd037d03c1b095848ee3703a` |
| `no-folder-gpx-with-ids.export-2.kml` | 1902 | `2b5c6bdd9d0fe560d73185562d4dcda75cbc5b7933755a81a3e21e6f5f716625` |
| `no-folder-gpx-with-ids.original.gpx` | 1491 | `bf69d34d83cef142bec02fa2f18d43ff8431b05c086fbdfcb69f562eff77643e` |
| `no-folder-gpx-with-ids.reimported-export.gpx` | 2574 | `3e3ffec91275c5a9ce9923c58550a7de74831664c244cc48cb2b11a0c42b61f8` |
| `no-folder-gpx-with-ids.reimported-export.kml` | 2417 | `241a5041c4efe06ea599171ff766b56f04a049da39f9825bf0c9c7c47c802b11` |

<a id="no-folder-kml-with-ids"></a>
### `no-folder-kml-with-ids`: edited onX KML, ids kept, imported without a folder

**Question.** The same as [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids), but with onX's
KML, whose id is in `<ExtendedData><Data name="id">`.

**Steps.**

1. 14:48Z: imported `original.gpx` (ticked) into folder `b0c8aac1-e84c-4f61-80c1-8c240af26612`,
   renamed `ZZTEST · no-folder-kml-with-ids · original`.
2. `export-1`.
3. `edited.kml` = `export-1.kml` with 8 replacements: each name (in `<name>` and in
   `<Data name="name">`) gained ` · edited`, each note `original` → `edited`, the waypoint colour
   `<value>rgba(255, 51, 0, 1)</value>` → `<value>rgba(8, 122, 255, 1)</value>`, and the icon
   `<value>Summit</value>` → `<value>Camp</value>`. All three `<Data name="id">` values were
   kept.
4. 14:49:16Z: imported `edited.kml`, unticked.
5. `export-2`. The new copies went into `ZZTEST · no-folder-kml-with-ids · reimported`
   (`1bb0cb4a-2a76-4bbc-ac40-832692a7298b`) and were exported.

**Records.**

Store snapshots `net/snap.before-reimport.json` (14:49:08.467Z) → `net/snap.after-reimport.json` (14:49:29.069Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST no-folder-kml-with-ids · waypoint` | waypoint | `a324b93f-4c81-4019-9dfa-cc0b63820733` | 14:48:08.901Z | 14:48:09.249Z | 14:48:09.249Z | no (identical) |
| existing | `ZZTEST no-folder-kml-with-ids · line` | track | `682b8b22-6769-442e-8b1c-6a59037f44fb` | 14:48:08.901Z | 14:48:08.901Z | 14:48:08.901Z | no (identical) |
| existing | `ZZTEST no-folder-kml-with-ids · area` | area | `409039e4-9d20-4d28-918f-3ced1e0a641f` | 14:48:08.901Z | 14:48:08.901Z | 14:48:08.901Z | no (identical) |
| **new** | `ZZTEST no-folder-kml-with-ids · waypoint · edited` | waypoint | `2a43ffc5-dec2-48f5-ac40-ce352d363473` | 14:49:16.741Z | — | 14:49:17.289Z | created |
| **new** | `ZZTEST no-folder-kml-with-ids · area · edited` | area | `a1ad493e-416a-47b2-b39a-44c1dfb5f409` | 14:49:16.741Z | — | 14:49:16.741Z | created |
| **new** | `ZZTEST no-folder-kml-with-ids · line · edited` | line | `7f6aaea3-1474-4a78-94bd-fd19abf1cd81` | 14:49:16.741Z | — | 14:49:16.741Z | created |


The KML copies have empty notes, the icon `Location`, and onX's default colours: blue for the
waypoint, `rgba(255,51,0,1)` for the line and the area. The KML `LineString` became a *Line*
(`type: line`), not a track. One caveat: the edited waypoint colour `rgba(8, 122, 255, 1)`
happens to be onX's default, so in this test colour proves nothing. The icon (`Camp` sent,
`Location` stored) and the empty note do. [`reimport-unmodified-kml`](#reimport-unmodified-kml)
is the clean colour test.

**Full-file diffs.** `export-1.kml` → `export-2.kml` is byte-identical. `export-1.gpx` →
`export-2.gpx` differs only in the 4 `<trkpt><time>` values. `edited.kml` →
`reimported-export.kml`:

```diff
--- no-folder-kml-with-ids.edited.kml
+++ no-folder-kml-with-ids.reimported-export.kml
@@ -3,2 +3,26 @@
 <Document>
+<Placemark>
+<name>ZZTEST no-folder-kml-with-ids · waypoint · edited</name>
+<ExtendedData>
+<Data name="name">
+<value>ZZTEST no-folder-kml-with-ids · waypoint · edited</value>
+</Data>
+<Data name="notes">
+<value>
+</value>
+</Data>
+<Data name="id">
+<value>2a43ffc5-dec2-48f5-ac40-ce352d363473</value>
+</Data>
+<Data name="color">
+<value>rgba(8, 122, 255, 1)</value>
+</Data>
+<Data name="icon">
+<value>Location</value>
+</Data>
+</ExtendedData>
+<Point>
+<coordinates>-121.4911,46.2652,1800.800048828</coordinates>
+</Point>
+</Placemark>
 <Placemark>
@@ -10,6 +34,7 @@
 <Data name="notes">
-<value>edited area note</value>
+<value>
+</value>
 </Data>
 <Data name="id">
-<value>409039e4-9d20-4d28-918f-3ced1e0a641f</value>
+<value>a1ad493e-416a-47b2-b39a-44c1dfb5f409</value>
 </Data>
@@ -19,6 +44,3 @@
 <Data name="color">
-<value>rgba(132,212,0,1)</value>
-</Data>
-<Data name="weight">
-<value>4.0</value>
+<value>rgba(255,51,0,1)</value>
 </Data>
@@ -43,15 +65,13 @@
 <Data name="notes">
-<value>edited line note</value>
+<value>
+</value>
 </Data>
 <Data name="id">
-<value>682b8b22-6769-442e-8b1c-6a59037f44fb</value>
+<value>7f6aaea3-1474-4a78-94bd-fd19abf1cd81</value>
+</Data>
+<Data name="type">
+<value>Line</value>
 </Data>
 <Data name="color">
-<value>rgba(8,122,255,1)</value>
-</Data>
-<Data name="style">
-<value>solid</value>
-</Data>
-<Data name="weight">
-<value>4.0</value>
+<value>rgba(255,51,0,1)</value>
 </Data>
@@ -62,25 +82,2 @@
 </Placemark>
-<Placemark>
-<name>ZZTEST no-folder-kml-with-ids · waypoint · edited</name>
-<ExtendedData>
-<Data name="name">
-<value>ZZTEST no-folder-kml-with-ids · waypoint · edited</value>
-</Data>
-<Data name="notes">
-<value>edited waypoint note</value>
-</Data>
-<Data name="id">
-<value>a324b93f-4c81-4019-9dfa-cc0b63820733</value>
-</Data>
-<Data name="color">
-<value>rgba(8, 122, 255, 1)</value>
-</Data>
-<Data name="icon">
-<value>Camp</value>
-</Data>
-</ExtendedData>
-<Point>
-<coordinates>-121.4911,46.2652,1800.800048828</coordinates>
-</Point>
-</Placemark>
 </Document>
```

An empty note exports as `<value>` + newline + `</value>`, not as an empty element.

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `no-folder-kml-with-ids.edited.kml` | 1955 | `4a483f661cb772fde7555d2c3aea7b0407d2ea6b6ffce1be8f1a44eee2d7d694` |
| `no-folder-kml-with-ids.export-1.gpx` | 2060 | `6e7070bf435dc2ee0d8e59ccbcb2a7458a032cc8334a3cf07d2b89b4826e4d74` |
| `no-folder-kml-with-ids.export-1.kml` | 1902 | `40c31371e33d640db7310a0bc5614d8ac1732ee490ab6b3b7348e4c4aaeaec23` |
| `no-folder-kml-with-ids.export-2.gpx` | 2060 | `d99c45b05f7699aa6017720663b1b8524aa7c0f2c4494611ab7f5e8dac323a12` |
| `no-folder-kml-with-ids.export-2.kml` | 1902 | `40c31371e33d640db7310a0bc5614d8ac1732ee490ab6b3b7348e4c4aaeaec23` |
| `no-folder-kml-with-ids.original.gpx` | 1491 | `abde8b4749ecae5d5d4bface0762d6983caba464da2e9b1f7edc2b449a2e8be7` |
| `no-folder-kml-with-ids.reimported-export.gpx` | 1816 | `d5067500f763716ebafa6605081870f6b55b10f3b544236b0f7064cd71512155` |
| `no-folder-kml-with-ids.reimported-export.kml` | 1813 | `44c4491db1b01d17036f5b08549fd74d152c70e92af95fedade3697a32b10041` |

<a id="originals-folder-gpx-with-ids"></a>
### `originals-folder-gpx-with-ids`: edited GPX copy put into the originals' own folder

**Question.** The import dialog cannot target a folder ([What the Web Map offers](#import-paths)).
The closest available route is to import unticked and then add the copies to the folder that
holds the originals. Does that bring the two copies together?

**Steps.**

1. 14:52Z: originals into `26670ea2-6b1a-40b3-8be6-5f1401767b86`, renamed
   `ZZTEST · originals-folder-gpx-with-ids · original`.
2. `export-1`. `edited.gpx` was made as in [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids),
   ids kept.
3. 14:53:25Z: imported, unticked.
4. On the originals' folder page, **Add Content**, ticking the three ` · edited` rows. The list did
   not pre-tick the folder's existing members (whether it lists them was not checked).
5. Reloaded the page, then snapshot and `export-2` of the folder (now "Save (6)").

**Records.**

Store snapshots `net/snap.before-reimport.json` (14:53:16.803Z) → `net/snap.after-add-to-originals-folder.json` (14:54:22.981Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST originals-folder-gpx-with-ids · waypoint` | waypoint | `3546736f-8934-49de-b12a-55be8a880bec` | 14:52:15.648Z | 14:52:15.885Z | 14:52:15.885Z | no (identical) |
| existing | `ZZTEST originals-folder-gpx-with-ids · line` | track | `4d5eed1d-4818-4619-a4cc-68eeb73f2bba` | 14:52:15.648Z | 14:52:15.648Z | 14:52:15.648Z | no (identical) |
| existing | `ZZTEST originals-folder-gpx-with-ids · area` | area | `2e584928-963d-485e-9ce8-ad5f45f86930` | 14:52:15.648Z | 14:52:15.648Z | 14:52:15.648Z | no (identical) |
| **new** | `ZZTEST originals-folder-gpx-with-ids · waypoint · edited` | waypoint | `041c7d22-fa60-405f-8c28-d58f0d0d3c3c` | 14:53:25.482Z | — | 14:53:25.768Z | created |
| **new** | `ZZTEST originals-folder-gpx-with-ids · line · edited` | track | `79719427-ecdf-4fc0-a5e1-1c9c93fce69c` | 14:52:54.472Z | — | 14:53:25.483Z | created |
| **new** | `ZZTEST originals-folder-gpx-with-ids · area · edited` | area | `10d1ae24-b8c3-4c77-8a04-76e1d17a6c86` | 14:53:25.483Z | — | 14:53:25.483Z | created |


**Full-file diffs.** Per markup, keyed by id, `export-1` → `export-2` (GPX and KML): the
folder gained three markups, and the three originals are identical except for `<trkpt><time>`.
Checked programmatically, not by eye. The GPX diff:

```diff
--- originals-folder-gpx-with-ids.export-1.gpx
+++ originals-folder-gpx-with-ids.export-2.gpx
@@ -2,2 +2,18 @@
 <metadata/>
+<wpt lat="46.2852" lon="-121.4911">
+<name>ZZTEST originals-folder-gpx-with-ids · waypoint · edited</name>
+<desc>name=ZZTEST originals-folder-gpx-with-ids · waypoint · edited
+notes=name=ZZTEST originals-folder-gpx-with-ids · waypoint · edited
+notes=edited waypoint note
+id=3546736f-8934-49de-b12a-55be8a880bec
+color=rgba(8, 122, 255, 1)
+icon=Camp
+id=041c7d22-fa60-405f-8c28-d58f0d0d3c3c
+color=rgba(8, 122, 255, 1)
+icon=Camp</desc>
+<extensions>
+<onx:color>rgba(8, 122, 255, 1)</onx:color>
+<onx:icon>Camp</onx:icon>
+</extensions>
+</wpt>
 <wpt lat="46.2852" lon="-121.4911">
@@ -14,2 +30,29 @@
 </wpt>
+<rte>
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST originals-folder-gpx-with-ids · area · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST originals-folder-gpx-with-ids · area · edited
+notes=name=ZZTEST originals-folder-gpx-with-ids · area · edited
+notes=edited area note
+id=2e584928-963d-485e-9ce8-ad5f45f86930
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)
+id=10d1ae24-b8c3-4c77-8a04-76e1d17a6c86
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)</desc>
+<type>Area</type>
+<extensions>
+<onx:color>rgba(132,212,0,1)</onx:color>
+<onx:weight>4.0</onx:weight>
+<onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
+</extensions>
+<rtept lat="46.29" lon="-121.5"/>
+<rtept lat="46.29" lon="-121.49"/>
+<rtept lat="46.295" lon="-121.49"/>
+<rtept lat="46.295" lon="-121.5"/>
+<rtept lat="46.29" lon="-121.5"/>
+</rte>
 <rte>
@@ -51,2 +94,39 @@
 <ele>0</ele>
+<time>2026-10-23T14:54:24.776Z</time>
+</trkpt>
+<trkpt lat="46.281" lon="-121.495">
+<ele>0</ele>
+<time>2026-10-23T14:54:24.776Z</time>
+</trkpt>
+<trkpt lat="46.283" lon="-121.492">
+<ele>0</ele>
+<time>2026-10-23T14:54:24.776Z</time>
+</trkpt>
+<trkpt lat="46.285" lon="-121.49">
+<ele>0</ele>
+<time>2026-10-23T14:54:24.776Z</time>
+</trkpt>
+</trkseg>
+</trk>
+<trk>
+<name>ZZTEST originals-folder-gpx-with-ids · line · edited</name>
+<desc>name=ZZTEST originals-folder-gpx-with-ids · line · edited
+notes=name=ZZTEST originals-folder-gpx-with-ids · line · edited
+notes=edited line note
+id=4d5eed1d-4818-4619-a4cc-68eeb73f2bba
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0
+id=79719427-ecdf-4fc0-a5e1-1c9c93fce69c
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0</desc>
+<extensions>
+<onx:color>rgba(8,122,255,1)</onx:color>
+<onx:style>solid</onx:style>
+<onx:weight>4.0</onx:weight>
+</extensions>
+<trkseg>
+<trkpt lat="46.28" lon="-121.5">
+<ele>0</ele>
 <time>2026-10-23T14:52:54.472Z</time>
```

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `originals-folder-gpx-with-ids.edited.gpx` | 2154 | `13bc126b58aab9f93b697ad6bc8faaf74bc5753a9df24be788db7b2eb7a58443` |
| `originals-folder-gpx-with-ids.export-1.gpx` | 2102 | `4cda700876f487e673cfd25ef482a1c3e5889282b99f71065ee3381deca693c7` |
| `originals-folder-gpx-with-ids.export-1.kml` | 1944 | `dcfa0c1f6b4a9571bb96f0c4bbbdd0744af84a443bc45984007463b3166faed4` |
| `originals-folder-gpx-with-ids.export-2.gpx` | 4438 | `8e63f4cb52e4d4cbe4270423ecdbde4253474194a3425d8901ea0057d7001d01` |
| `originals-folder-gpx-with-ids.export-2.kml` | 4315 | `6872ac5f473db148a85f7e904ad101356921675fa7f6ae2097069cffbc327a0d` |
| `originals-folder-gpx-with-ids.original.gpx` | 1519 | `c67ff4ab20e028400a3d26033aa60670f3905240c4df261f6cd81f3455e3856c` |

<a id="another-folder-gpx-with-ids"></a>
### `another-folder-gpx-with-ids`: edited GPX copy put into a different existing folder

**Steps.**

1. 14:54Z: originals into `a6d3c060-bd1c-4dfe-821e-291a1eb6d57b`, renamed
   `ZZTEST · another-folder-gpx-with-ids · original`.
2. `export-1`, then `edited.gpx`, ids kept.
3. 14:56Z: imported, unticked.
4. The empty probe folder `fe79dbb9-91cb-47bd-96ee-f00a59025e7b` was renamed
   `ZZTEST · another-folder-gpx-with-ids · target`. **Add Content** put the three new markups
   in it.
5. Exports of the target folder (`reimported-export`) and of the originals' folder (`export-2`).

**Records.**

Store snapshots `net/snap.before-reimport.json` (14:55:52.386Z) → `net/snap.after-add-to-target.json` (14:57:44.481Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST another-folder-gpx-with-ids · waypoint` | waypoint | `987e04fc-24a2-440e-afcc-b9892fc01a02` | 14:54:57.227Z | 14:54:57.909Z | 14:54:57.909Z | no (identical) |
| existing | `ZZTEST another-folder-gpx-with-ids · line` | track | `c272da8a-d93d-4fa1-8f86-27c7b6fa83de` | 14:54:57.228Z | 14:54:57.228Z | 14:54:57.228Z | no (identical) |
| existing | `ZZTEST another-folder-gpx-with-ids · area` | area | `81a06c29-783f-498c-b177-1d73bfa9a6ee` | 14:54:57.228Z | 14:54:57.228Z | 14:54:57.228Z | no (identical) |
| **new** | `ZZTEST another-folder-gpx-with-ids · waypoint · edited` | waypoint | `f0e7ba5f-ce84-408a-b7ea-06bfbf6d828a` | 14:56:00.648Z | — | 14:56:00.901Z | created |
| **new** | `ZZTEST another-folder-gpx-with-ids · line · edited` | track | `4471b2b4-98c3-40cc-a972-ee46e6b3a919` | 14:55:29.896Z | — | 14:56:00.649Z | created |
| **new** | `ZZTEST another-folder-gpx-with-ids · area · edited` | area | `b4906c36-d9a9-4b5d-afa4-57dccd1e86de` | 14:56:00.648Z | — | 14:56:00.649Z | created |


**Full-file diffs.** `export-1.kml` → `export-2.kml` is byte-identical. `export-1.gpx` →
`export-2.gpx` differs only in the 4 `<trkpt><time>` values. `reimported-export` has the same
shape as in [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids): nested notes, new ids, and
the track before the area.

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `another-folder-gpx-with-ids.edited.gpx` | 2141 | `f2770004b499e38465dfef70c9ef0a47d4651b138c634c65a56f6f869c312f77` |
| `another-folder-gpx-with-ids.export-1.gpx` | 2089 | `3f189ef4482e87a8af70d1ea3a021a92578c3477cdd56bb3872057e693c5ab2a` |
| `another-folder-gpx-with-ids.export-1.kml` | 1931 | `a2c195760444c1e1fa588592491f75d529fa6c91a268ce6e68ab6c43f3ff6b9e` |
| `another-folder-gpx-with-ids.export-2.gpx` | 2089 | `133544f89a6f49d093d72a5cede5c3e1494f7004372dfbef86104e58081c277b` |
| `another-folder-gpx-with-ids.export-2.kml` | 1931 | `a2c195760444c1e1fa588592491f75d529fa6c91a268ce6e68ab6c43f3ff6b9e` |
| `another-folder-gpx-with-ids.original.gpx` | 1511 | `89f885c932161bcb93d84701e5c5ef651fcfa09a34323d3512ee7b5652769205` |
| `another-folder-gpx-with-ids.reimported-export.gpx` | 2618 | `51b50f4c0125912ffacbe4d7f92d8dd4a342a4e00bbc8f6ad736611a79bf084c` |
| `another-folder-gpx-with-ids.reimported-export.kml` | 2461 | `a0dce04278a4ae1a1266e659e5e41efe6446b10a390049bb4391ddac05c49734` |

<a id="reimport-unmodified-gpx"></a>
### `reimport-unmodified-gpx`: onX's own GPX export re-imported byte for byte

**Steps.**

1. 14:58Z: originals into `e4ad9411-ba6f-407a-9d36-8c17b90d678b`, renamed
   `ZZTEST · reimport-unmodified-gpx · original`.
2. `export-1`.
3. 14:59:18Z: imported `export-1.gpx` itself, unticked.
4. `export-2`.

**Records.**

Store snapshots `net/snap.before-reimport.json` (14:59:09.221Z) → `net/snap.after-reimport.json` (14:59:31.581Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST reimport-unmodified-gpx · waypoint` | waypoint | `b3a3b230-ccb0-4e3f-bea5-ed7370e9bd17` | 14:58:16.724Z | 14:58:17.038Z | 14:58:17.038Z | no (identical) |
| existing | `ZZTEST reimport-unmodified-gpx · line` | track | `6af3b7f4-ceeb-4da6-85c1-59b4e1dfadec` | 14:58:16.724Z | 14:58:16.724Z | 14:58:16.724Z | no (identical) |
| existing | `ZZTEST reimport-unmodified-gpx · area` | area | `e0d779ba-3471-4cd6-ad38-c6c0ff24ec52` | 14:58:16.725Z | 14:58:16.725Z | 14:58:16.725Z | no (identical) |
| **new** | `ZZTEST reimport-unmodified-gpx · waypoint` | waypoint | `fc69d893-cfc2-48a1-b67b-4ee771b5a433` | 14:59:18.690Z | — | 14:59:19.013Z | created |
| **new** | `ZZTEST reimport-unmodified-gpx · line` | track | `4601258a-96a8-4c29-ae67-84202ae0d52e` | 14:58:49.438Z | — | 14:59:18.691Z | created |
| **new** | `ZZTEST reimport-unmodified-gpx · area` | area | `42cfdc7f-09ca-4fc7-9945-04ffd86fa9e5` | 14:59:18.691Z | — | 14:59:18.691Z | created |


The duplicates carry the same names as the originals. Their notes are the full uploaded
`<desc>` (`name=…\nnotes=original waypoint note\nid=b3a3b230-…\n…`).

**Full-file diffs.** `export-1.kml` → `export-2.kml` is byte-identical. `export-1.gpx` →
`export-2.gpx` differs only in the 4 `<trkpt><time>` values (14:58:49.438Z → 14:59:50.630Z).

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `reimport-unmodified-gpx.export-1.gpx` | 2066 | `91819a6668ac0abbc67e95b6dce3eee6ce3484c5000d8e3917c44ece82d18a46` |
| `reimport-unmodified-gpx.export-1.kml` | 1908 | `50d08be93611eb23b1c9ceaa90300443d87e98fb1c3038bb4cdd251d8c54fa74` |
| `reimport-unmodified-gpx.export-2.gpx` | 2066 | `fddf46c173112e1ea8f877cc26b88da1b106a202fa706e8bb8b3bb2e908972f3` |
| `reimport-unmodified-gpx.export-2.kml` | 1908 | `50d08be93611eb23b1c9ceaa90300443d87e98fb1c3038bb4cdd251d8c54fa74` |
| `reimport-unmodified-gpx.original.gpx` | 1495 | `614eb649a98c1685e591d20add3502afed2d875d868f5d1b747bbf18e13ef19a` |

<a id="reimport-unmodified-kml"></a>
### `reimport-unmodified-kml`: onX's own KML export re-imported byte for byte

**Steps.**

1. 15:00Z: originals into `bb136579-ca69-4e28-864a-efc85ba69dec`, renamed
   `ZZTEST · reimport-unmodified-kml · original`.
2. `export-1`.
3. 15:01:37Z: imported `export-1.kml` itself, unticked.
4. `export-2`.

**Records.**

Store snapshots `net/snap.before-reimport.json` (15:01:22.479Z) → `net/snap.after-reimport.json` (15:01:44.674Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST reimport-unmodified-kml · waypoint` | waypoint | `9c7c4d56-847a-4e88-92cb-31bad51d2c99` | 15:00:28.942Z | 15:00:29.229Z | 15:00:29.229Z | no (identical) |
| existing | `ZZTEST reimport-unmodified-kml · line` | track | `679fcae0-7340-4d53-a6fb-e5ff38c5d982` | 15:00:28.942Z | 15:00:28.942Z | 15:00:28.942Z | no (identical) |
| existing | `ZZTEST reimport-unmodified-kml · area` | area | `7b3263e5-7845-4419-a659-7b0dc3404d5a` | 15:00:28.942Z | 15:00:28.942Z | 15:00:28.942Z | no (identical) |
| **new** | `ZZTEST reimport-unmodified-kml · waypoint` | waypoint | `ad2c2df4-d4b4-4c2d-b057-f6e455c37de4` | 15:01:37.322Z | — | 15:01:37.643Z | created |
| **new** | `ZZTEST reimport-unmodified-kml · area` | area | `a332a9e1-c301-402f-8b88-f0c9520c70df` | 15:01:37.322Z | — | 15:01:37.322Z | created |
| **new** | `ZZTEST reimport-unmodified-kml · line` | line | `0beda38c-6f3e-4d3e-b02a-9c8bf2ebaef5` | 15:01:37.322Z | — | 15:01:37.322Z | created |


This is the clean colour test for KML. The original waypoint is red `Summit`
(`rgba(255,51,0,1)`), and the KML file says so in `<Data name="color">` and
`<Data name="icon">`. The copy is blue `Location` with an empty note. The line came back as a
*Line*, coloured `rgba(255,51,0,1)`, not as a blue track.

**Full-file diffs.** `export-1.kml` → `export-2.kml` is byte-identical. `export-1.gpx` →
`export-2.gpx` differs only in the 4 `<trkpt><time>` values.

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `reimport-unmodified-kml.export-1.gpx` | 2066 | `b26e6d1dfd5689478ec88dac560905a3b8ff0a0fe9872597ff5b528dfe5b9a7a` |
| `reimport-unmodified-kml.export-1.kml` | 1908 | `b60db0e3a1c620962ed8e1d18dc93f989900d1c79663f3e27c7e4fc3bb1161f7` |
| `reimport-unmodified-kml.export-2.gpx` | 2066 | `6903db8befd6b1c56ecdad8bdfcf881748b5d2ca4893ce515070ce0182bb5d76` |
| `reimport-unmodified-kml.export-2.kml` | 1908 | `b60db0e3a1c620962ed8e1d18dc93f989900d1c79663f3e27c7e4fc3bb1161f7` |
| `reimport-unmodified-kml.original.gpx` | 1495 | `495f409f38a9cadbb81e8b9cebb5bb77d034795c738f9395c56632aee7290fec` |

<a id="same-name-coords-no-ids"></a>
### `same-name-coords-no-ids`: a content-identical copy with no onX id

**Question.** Does onX match on content (name, coordinates, note, style) when there is no id?

**Steps.**

1. 15:04Z: originals into `08b27940-6ac7-4adf-8e51-0d68a21c9c32`, renamed
   `ZZTEST · same-name-coords-no-ids · original`.
2. `export-1`.
3. `stripped.gpx` = `export-1.gpx` with each `<desc>` key=value block replaced by the note alone,
   as the original upload had it. No `id=` remains, and names, coordinates, styles and
   extensions are untouched:

```diff
--- same-name-coords-no-ids.export-1.gpx
+++ same-name-coords-no-ids.stripped.gpx
@@ -4,7 +4,3 @@
 <name>ZZTEST same-name-coords-no-ids · waypoint</name>
-<desc>name=ZZTEST same-name-coords-no-ids · waypoint
-notes=original waypoint note
-id=fe639101-a5bd-4d28-b177-931a49d6a74e
-color=rgba(255, 51, 0, 1)
-icon=Summit</desc>
+<desc>original waypoint note</desc>
 <extensions>
@@ -16,9 +12,3 @@
 <name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST same-name-coords-no-ids · area</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST same-name-coords-no-ids · area
-notes=original area note
-id=5c0ccf3b-94bf-441e-8e0c-b379c07e9c1f
-type=Area
-color=rgba(132,212,0,1)
-weight=4.0
-fill_color=rgba(74,144,226,0.1)</desc>
+<desc xmlns="http://www.topografix.com/GPX/1/1">original area note</desc>
 <type>Area</type>
@@ -37,8 +27,3 @@
 <name>ZZTEST same-name-coords-no-ids · line</name>
-<desc>name=ZZTEST same-name-coords-no-ids · line
-notes=original line note
-id=e3530460-8580-42c2-ae45-2b4c8a83eecc
-color=rgba(8,122,255,1)
-style=solid
-weight=4.0</desc>
+<desc>original line note</desc>
 <extensions>
```

4. 15:06:53Z: imported `stripped.gpx`, unticked.
5. `export-2`.

**Records.**

Store snapshots `net/snap.before-reimport.json` (15:06:42.399Z) → `net/snap.after-reimport.json` (15:07:01.905Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST same-name-coords-no-ids · waypoint` | waypoint | `fe639101-a5bd-4d28-b177-931a49d6a74e` | 15:04:47.635Z | 15:04:48.032Z | 15:04:48.032Z | no (identical) |
| existing | `ZZTEST same-name-coords-no-ids · line` | track | `e3530460-8580-42c2-ae45-2b4c8a83eecc` | 15:04:47.635Z | 15:04:47.635Z | 15:04:47.635Z | no (identical) |
| existing | `ZZTEST same-name-coords-no-ids · area` | area | `5c0ccf3b-94bf-441e-8e0c-b379c07e9c1f` | 15:04:47.635Z | 15:04:47.635Z | 15:04:47.635Z | no (identical) |
| **new** | `ZZTEST same-name-coords-no-ids · waypoint` | waypoint | `ff1b05d8-8238-4b95-ac38-10c78a447fa3` | 15:06:53.507Z | — | 15:06:53.815Z | created |
| **new** | `ZZTEST same-name-coords-no-ids · line` | track | `46bcf1ec-0992-450e-8789-858705cabe7c` | 15:06:09.199Z | — | 15:06:53.508Z | created |
| **new** | `ZZTEST same-name-coords-no-ids · area` | area | `744e7c3a-c727-4ced-9865-0d0e639b7fbf` | 15:06:53.508Z | — | 15:06:53.508Z | created |


The copies match the originals in name, note, icon, colour and geometry. Only the uuid and the
timestamps differ (and the track's `createdAt`, which comes from `export-1`'s point times).

**Full-file diffs.** `export-1.kml` → `export-2.kml` is byte-identical. `export-1.gpx` →
`export-2.gpx` differs only in the 4 `<trkpt><time>` values.

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `same-name-coords-no-ids.export-1.gpx` | 2066 | `0f9c42b670c13e9bba3624d92e12560cf3767acbbf3b8a69acb904617199f535` |
| `same-name-coords-no-ids.export-1.kml` | 1908 | `f988aec335347141045d0783e97f01b4ffaea5c9b1ec7073a96dfeef7e14999b` |
| `same-name-coords-no-ids.export-2.gpx` | 2066 | `971810e3a0f2089aa74cc4ad69c78cdebbff41e4eb8ac645fb7a0d4fdc556737` |
| `same-name-coords-no-ids.export-2.kml` | 1908 | `f988aec335347141045d0783e97f01b4ffaea5c9b1ec7073a96dfeef7e14999b` |
| `same-name-coords-no-ids.original.gpx` | 1495 | `dbd9c8529a8d38b60bfe20cf47282ee39a5cd28ec442cdbb6c89ff7a4fe83db8` |
| `same-name-coords-no-ids.stripped.gpx` | 1630 | `5f50f9d97ec85612b9e7ba989c0ae878bb8368ae210d6d292a9cebdc54a5af94` |

<a id="onx-edit-then-reimport"></a>
### `onx-edit-then-reimport`: edit in onX, then import the older export

**Question.** If a markup is changed in onX and an export from *before* the change is imported,
does the import overwrite (revert) the change?

**Steps.**

1. 15:07:47Z: originals into `78df97a5-7f1f-4a70-89bb-1ad7ae969858`, renamed
   `ZZTEST · onx-edit-then-reimport · original`.
2. 15:08:19Z: `export-1`.
3. 15:08:50Z: in onX (folder → waypoint menu → **Edit waypoint**), renamed the waypoint to
   `ZZTEST onx-edit-then-reimport · waypoint · edited-in-onx`, changed its note to
   `edited-in-onx waypoint note`, and pressed Save.
4. 15:09:13Z: imported the stale `export-1.gpx` (the original's `id=`, old name and old note),
   unticked.
5. `export-2`.

**Records.** After the in-onX edit, the waypoint's `updatedAt` = `lastSyncedAt` =
15:08:50.225Z (`createdAt` 15:07:47.803Z). This is the positive control: a real in-place change
shows in these fields. Across the import:

Store snapshots `net/snap.after-onx-edit.json` (15:08:55.460Z) → `net/snap.after-reimport.json` (15:09:21.419Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST onx-edit-then-reimport · waypoint · edited-in-onx` | waypoint | `3adcc6cb-db9c-48ae-9d4e-eb3d5b800dc0` | 15:07:47.803Z | 15:08:50.225Z | 15:08:50.225Z | no (identical) |
| existing | `ZZTEST onx-edit-then-reimport · line` | track | `24eba6da-961b-43ce-b99f-6873a24972a8` | 15:07:47.804Z | 15:07:47.804Z | 15:07:47.804Z | no (identical) |
| existing | `ZZTEST onx-edit-then-reimport · area` | area | `0ec68d98-dc72-45b5-a3ec-38b6c5d2e313` | 15:07:47.804Z | 15:07:47.804Z | 15:07:47.804Z | no (identical) |
| **new** | `ZZTEST onx-edit-then-reimport · waypoint` | waypoint | `6da8d8f7-1cdd-4a77-804c-e08a44f881ab` | 15:09:13.517Z | — | 15:09:13.802Z | created |
| **new** | `ZZTEST onx-edit-then-reimport · line` | track | `eb082454-475e-4654-82cb-defab99c2129` | 15:08:19.644Z | — | 15:09:13.517Z | created |
| **new** | `ZZTEST onx-edit-then-reimport · area` | area | `15294750-e348-476d-b079-f1f861372ee3` | 15:09:13.517Z | — | 15:09:13.517Z | created |


**Full-file diffs.** `export-1` → `export-2`. Checked per id, the only differences are the
in-onX edit and `<trkpt><time>`. The import reverted nothing:

```diff
--- onx-edit-then-reimport.export-1.kml
+++ onx-edit-then-reimport.export-2.kml
@@ -63,9 +63,9 @@
 <Placemark>
-<name>ZZTEST onx-edit-then-reimport · waypoint</name>
+<name>ZZTEST onx-edit-then-reimport · waypoint · edited-in-onx</name>
 <ExtendedData>
 <Data name="name">
-<value>ZZTEST onx-edit-then-reimport · waypoint</value>
+<value>ZZTEST onx-edit-then-reimport · waypoint · edited-in-onx</value>
 </Data>
 <Data name="notes">
-<value>original waypoint note</value>
+<value>edited-in-onx waypoint note</value>
 </Data>
```

```diff
--- onx-edit-then-reimport.export-1.gpx
+++ onx-edit-then-reimport.export-2.gpx
@@ -3,5 +3,5 @@
 <wpt lat="46.3852" lon="-121.4911">
-<name>ZZTEST onx-edit-then-reimport · waypoint</name>
-<desc>name=ZZTEST onx-edit-then-reimport · waypoint
-notes=original waypoint note
+<name>ZZTEST onx-edit-then-reimport · waypoint · edited-in-onx</name>
+<desc>name=ZZTEST onx-edit-then-reimport · waypoint · edited-in-onx
+notes=edited-in-onx waypoint note
 id=3adcc6cb-db9c-48ae-9d4e-eb3d5b800dc0
@@ -51,3 +51,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:08:19.644Z</time>
+<time>2026-10-23T15:09:39.324Z</time>
 </trkpt>
@@ -55,3 +55,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:08:19.644Z</time>
+<time>2026-10-23T15:09:39.324Z</time>
 </trkpt>
@@ -59,3 +59,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:08:19.644Z</time>
+<time>2026-10-23T15:09:39.324Z</time>
 </trkpt>
@@ -63,3 +63,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:08:19.644Z</time>
+<time>2026-10-23T15:09:39.324Z</time>
 </trkpt>
```

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `onx-edit-then-reimport.export-1.gpx` | 2060 | `a663cf201c9c650bb65dc57ea1e7f8d7dd4bf0f60bbe6bdf9083946e8be2fdc2` |
| `onx-edit-then-reimport.export-1.kml` | 1895 | `d96f1b797c22b86f9b71dc1fb549760f912cd38b9e5a37901ba0f5478f35dff8` |
| `onx-edit-then-reimport.export-2.gpx` | 2099 | `074bb8b56c0d4031c13538d8de889bfe11b5eb8b92564f87b3a44fb8ac09d7d0` |
| `onx-edit-then-reimport.export-2.kml` | 1934 | `5490e8f0dc49b37a502afb0423ca639af94e17a2b3f2ef0ca03814ae6ada24e2` |
| `onx-edit-then-reimport.original.gpx` | 1491 | `c9b5e6630cc0731ed560fb09a3934a4a9239baeeec3894014d5ca929a18f5948` |

<a id="multi-step-cycle-gpx"></a>
### `multi-step-cycle-gpx`: export → modify → import → export → modify → import → export

**Steps.**

1. 15:10:13Z: originals into `e767832f-2081-4550-b443-35e34cf9376a`, renamed
   `ZZTEST · multi-step-cycle-gpx · original`.
2. 15:10:46Z: `export-1` (GPX and KML).
3. `edited.gpx` was made from `export-1.gpx` as in the other tests, ids kept. 15:11:21Z:
   imported, unticked. The copies went into `ZZTEST · multi-step-cycle-gpx · reimported`
   (`2fac9d28-4f09-41fd-abaf-f2bed4060ec5`).
4. 15:12:18Z: `export-2` = that `reimported` folder (GPX and KML). 15:12:54Z: the originals'
   folder re-exported as GPX (`original-folder.export-2.gpx`).
5. `edited-2.gpx` = `export-2.gpx` with ` · edited` → ` · edited-2` (in `<name>` and in **both**
   nested `name=` lines) and `edited <kind> note` → `edited-2 <kind> note`. Each `<desc>` in this
   file now carries **two** onX ids: the original's and the first copy's.
6. 15:13:17Z: imported, unticked. The copies went into
   `ZZTEST · multi-step-cycle-gpx · reimported-2` (`ad5d9fc6-8f47-4a4e-96ae-324be9948416`).
7. 15:14:13Z: `export-3` = the `reimported-2` folder (GPX and KML). Then 15:14:47Z re-exported
   the `reimported` folder as KML (`reimported-folder.export-3.kml`), and 15:15:10Z the
   originals' folder as KML (`original-folder.export-3.kml`).

**Records, cycle 1 and cycle 2.**

Store snapshots `net/snap.before-reimport.json` (15:11:07.784Z) → `net/snap.after-reimport.json` (15:11:29.251Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST multi-step-cycle-gpx · waypoint` | waypoint | `a218c42b-6c46-419e-a1fe-a713aff5d767` | 15:10:13.254Z | 15:10:13.541Z | 15:10:13.541Z | no (identical) |
| existing | `ZZTEST multi-step-cycle-gpx · line` | track | `bf3a774b-9ed1-44e7-8909-6c675772a748` | 15:10:13.255Z | 15:10:13.255Z | 15:10:13.255Z | no (identical) |
| existing | `ZZTEST multi-step-cycle-gpx · area` | area | `ac601e74-6398-490f-828c-c60d634997e2` | 15:10:13.255Z | 15:10:13.255Z | 15:10:13.255Z | no (identical) |
| **new** | `ZZTEST multi-step-cycle-gpx · waypoint · edited` | waypoint | `4b1c36f0-6fab-4162-a345-9ad6b2785dee` | 15:11:21.102Z | — | 15:11:21.386Z | created |
| **new** | `ZZTEST multi-step-cycle-gpx · line · edited` | track | `897270bc-0ec0-4ef1-9279-dfeaa84890a9` | 15:10:46.123Z | — | 15:11:21.104Z | created |
| **new** | `ZZTEST multi-step-cycle-gpx · area · edited` | area | `5d4bb89a-03bf-404b-bbea-ae928a1a9bc9` | 15:11:21.103Z | — | 15:11:21.104Z | created |

Store snapshots `net/snap.before-reimport-2.json` (15:13:05.023Z) → `net/snap.after-reimport-2.json` (15:13:25.452Z). The other 648 markups in the account: digest unchanged (`1d114774e8ec…`).

| | Markup | Kind | uuid | `createdAt` | `updatedAt` before | `updatedAt` after | Record changed? |
|---|---|---|---|---|---|---|---|
| existing | `ZZTEST multi-step-cycle-gpx · waypoint` | waypoint | `a218c42b-6c46-419e-a1fe-a713aff5d767` | 15:10:13.254Z | 15:10:13.541Z | 15:10:13.541Z | no (identical) |
| existing | `ZZTEST multi-step-cycle-gpx · waypoint · edited` | waypoint | `4b1c36f0-6fab-4162-a345-9ad6b2785dee` | 15:11:21.102Z | 15:11:21.386Z | 15:11:21.386Z | no (identical) |
| existing | `ZZTEST multi-step-cycle-gpx · line` | track | `bf3a774b-9ed1-44e7-8909-6c675772a748` | 15:10:13.255Z | 15:10:13.255Z | 15:10:13.255Z | no (identical) |
| existing | `ZZTEST multi-step-cycle-gpx · line · edited` | track | `897270bc-0ec0-4ef1-9279-dfeaa84890a9` | 15:10:46.123Z | 15:11:21.104Z | 15:11:21.104Z | no (identical) |
| existing | `ZZTEST multi-step-cycle-gpx · area` | area | `ac601e74-6398-490f-828c-c60d634997e2` | 15:10:13.255Z | 15:10:13.255Z | 15:10:13.255Z | no (identical) |
| existing | `ZZTEST multi-step-cycle-gpx · area · edited` | area | `5d4bb89a-03bf-404b-bbea-ae928a1a9bc9` | 15:11:21.103Z | 15:11:21.104Z | 15:11:21.104Z | no (identical) |
| **new** | `ZZTEST multi-step-cycle-gpx · waypoint · edited-2` | waypoint | `5396e8c2-051c-4a8c-a6e7-761af2835c02` | 15:13:17.157Z | — | 15:13:17.533Z | created |
| **new** | `ZZTEST multi-step-cycle-gpx · line · edited-2` | track | `69d7fc78-feab-417d-93d5-29dbe12af124` | 15:10:46.123Z | — | 15:13:17.158Z | created |
| **new** | `ZZTEST multi-step-cycle-gpx · area · edited-2` | area | `0b54c7db-1da4-484a-bf0b-c3d40e5bce33` | 15:13:17.158Z | — | 15:13:17.158Z | created |


The second-generation track `69d7fc78-…` has `createdAt` 15:10:46.123Z, which is `export-1`'s
point time, carried through two imports.

**In place at each step?**

| Check | Result |
|---|---|
| Originals after cycle 1: `export-1.gpx` → `original-folder.export-2.gpx` | Per id: waypoint and area identical; track differs only in `<trkpt><time>`; order unchanged |
| Originals after cycle 2: `export-1.kml` → `original-folder.export-3.kml` | Byte-identical |
| First copies after cycle 2: `export-2.kml` → `reimported-folder.export-3.kml` | Same 3 ids, each Placemark **byte-identical**, header identical; **only the order differs** (line moved from second to last) |
| Store: all six existing records across the cycle-2 import | Identical (table above) |

**Notes grow each cycle.** These are the stored note sizes in UTF-8 bytes, each with its count
of `id=` lines:

| Generation | Waypoint | Line | Area |
|---|---|---|---|
| original | 22 B, 0 ids | 18 B, 0 | 18 B, 0 |
| `· edited` | 158 B, 1 | 160 B, 1 | 190 B, 1 |
| `· edited-2` | 302 B, 2 | 310 B, 2 | 370 B, 2 |

At about +150–180 B per cycle, the area's note would pass onX's 512-byte import cap
(`docs/ONX_TESTING.md`) on a third cycle and be truncated. That is an extrapolation and was
not tested.

**Full-file diffs.** The cycle-2 upload as onX stored it (`edited-2.gpx` → `export-3.gpx`):

```diff
--- multi-step-cycle-gpx.edited-2.gpx
+++ multi-step-cycle-gpx.export-3.gpx
@@ -6,2 +6,3 @@
 notes=name=ZZTEST multi-step-cycle-gpx · waypoint · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · waypoint · edited-2
 notes=edited-2 waypoint note
@@ -11,2 +12,5 @@
 id=4b1c36f0-6fab-4162-a345-9ad6b2785dee
+color=rgba(8, 122, 255, 1)
+icon=Camp
+id=5396e8c2-051c-4a8c-a6e7-761af2835c02
 color=rgba(8, 122, 255, 1)
@@ -22,2 +26,3 @@
 notes=name=ZZTEST multi-step-cycle-gpx · line · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · line · edited-2
 notes=edited-2 line note
@@ -28,2 +33,6 @@
 id=897270bc-0ec0-4ef1-9279-dfeaa84890a9
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0
+id=69d7fc78-feab-417d-93d5-29dbe12af124
 color=rgba(8,122,255,1)
@@ -59,2 +68,3 @@
 notes=name=ZZTEST multi-step-cycle-gpx · area · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · area · edited-2
 notes=edited-2 area note
@@ -66,2 +76,7 @@
 id=5d4bb89a-03bf-404b-bbea-ae928a1a9bc9
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)
+id=0b54c7db-1da4-484a-bf0b-c3d40e5bce33
 type=Area
```

The reorder of an unchanged folder (`export-2.kml` → `reimported-folder.export-3.kml`):

```diff
--- multi-step-cycle-gpx.export-2.kml
+++ multi-step-cycle-gpx.reimported-folder.export-3.kml
@@ -30,31 +29,0 @@
-</Placemark>
-<Placemark>
-<name>ZZTEST multi-step-cycle-gpx · line · edited</name>
-<ExtendedData>
-<Data name="name">
-<value>ZZTEST multi-step-cycle-gpx · line · edited</value>
-</Data>
-<Data name="notes">
-<value>name=ZZTEST multi-step-cycle-gpx · line · edited
-notes=edited line note
-id=bf3a774b-9ed1-44e7-8909-6c675772a748
-color=rgba(8,122,255,1)
-style=solid
-weight=4.0</value>
-</Data>
-<Data name="id">
-<value>897270bc-0ec0-4ef1-9279-dfeaa84890a9</value>
-</Data>
-<Data name="color">
-<value>rgba(8,122,255,1)</value>
-</Data>
-<Data name="style">
-<value>solid</value>
-</Data>
-<Data name="weight">
-<value>4.0</value>
-</Data>
-</ExtendedData>
-<LineString>
-<coordinates>-121.5,46.4,0 -121.495,46.401,0 -121.492,46.403,0 -121.49,46.405,0</coordinates>
-</LineString>
@@ -100,0 +70,31 @@
+<Placemark>
+<name>ZZTEST multi-step-cycle-gpx · line · edited</name>
+<ExtendedData>
+<Data name="name">
+<value>ZZTEST multi-step-cycle-gpx · line · edited</value>
+</Data>
+<Data name="notes">
+<value>name=ZZTEST multi-step-cycle-gpx · line · edited
+notes=edited line note
+id=bf3a774b-9ed1-44e7-8909-6c675772a748
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0</value>
+</Data>
+<Data name="id">
+<value>897270bc-0ec0-4ef1-9279-dfeaa84890a9</value>
+</Data>
+<Data name="color">
+<value>rgba(8,122,255,1)</value>
+</Data>
+<Data name="style">
+<value>solid</value>
+</Data>
+<Data name="weight">
+<value>4.0</value>
+</Data>
+</ExtendedData>
+<LineString>
+<coordinates>-121.5,46.4,0 -121.495,46.401,0 -121.492,46.403,0 -121.49,46.405,0</coordinates>
+</LineString>
+</Placemark>
```

**Files.**

| File | Bytes | sha256 |
|---|---|---|
| `multi-step-cycle-gpx.edited-2.gpx` | 2579 | `f8554df00fbe213ebc5b23cf1b9ec63c1d298c691a687f7849400d9552a16d20` |
| `multi-step-cycle-gpx.edited.gpx` | 2099 | `18444a9f75dcfc62ad5305023777022e32b5884118d18b2f264f12418da53f81` |
| `multi-step-cycle-gpx.export-1.gpx` | 2047 | `61fdcc3d709ae0064057f3896757ad8b2fe3be57b65eb8b3716f392dc927a337` |
| `multi-step-cycle-gpx.export-1.kml` | 1879 | `2528385e47eed01b0d1e8979f2a9dbadcdaf8a29d65bf39883080cc590a6b056` |
| `multi-step-cycle-gpx.export-2.gpx` | 2555 | `95173bab44786a75db198e816f9bc207d75bc7c9d05f1670d723deaec04bd197` |
| `multi-step-cycle-gpx.export-2.kml` | 2388 | `b80983974de00b868f03f2dfaedd82abe63559f04dd9c5a3747868f2a9e7b62d` |
| `multi-step-cycle-gpx.export-3.gpx` | 3041 | `0abd631a95930052665cdaa67f4cdf002407a4f5db782e33698a145f58d30a70` |
| `multi-step-cycle-gpx.export-3.kml` | 2874 | `9625a739894f4f9238f582ff94a33559eded0971343795170ff31fbf2c29e4a2` |
| `multi-step-cycle-gpx.original-folder.export-2.gpx` | 2047 | `3122aec371edec7ffe1d0e9234adc8206f5e0f92837ee27a85521a58bca9688e` |
| `multi-step-cycle-gpx.original-folder.export-3.kml` | 1879 | `2528385e47eed01b0d1e8979f2a9dbadcdaf8a29d65bf39883080cc590a6b056` |
| `multi-step-cycle-gpx.original.gpx` | 1483 | `830ed311256da5b91415ee05a744622ac30db1528ae67d0b33a424340ee06b1f` |
| `multi-step-cycle-gpx.reimported-folder.export-3.kml` | 2388 | `21001f2310009bfd27d01b2f467ea00904245ecf8040fc1b7cf48f3099bc6d17` |

<a id="new-folder-gpx-with-ids"></a>
### `new-folder-gpx-with-ids` (run id1): edited GPX, ids kept, imported into a new folder

Run id1, 13:58–14:10 UTC the same day. Raw files are in `tests/fixtures/roundtrip/id1/`:

| Role | File |
|---|---|
| Original upload | `a_originals/id1_originals.gpx` |
| Originals' export | `a_originals/a1_export_originals.{gpx,kml}` |
| Edited copy, ids kept | `b_v2/id1_v2_same_ids.gpx` |
| Re-export of the originals after all imports | `d_reexport/d1_originals.{gpx,kml}` |
| Export of the copy | `d_reexport/d3_v2_same_ids_gpx.gpx` |

The markup names carry the old `[id1]` prefix. The edited copy is onX's GPX export with only
the names changed (` · V2`), every `id=` kept, imported ticked. Result: 3 new uuids. The
originals' KML re-export was byte-identical. The GPX re-export differed only in
`<trkpt><time>`. The waypoint's and area's API records were identical field for field.
Account-wide, nothing else changed. The uploaded `<desc>`, `id=` line included, became the new
markup's note. sha256 values are in `tests/fixtures/roundtrip/id1/` (for example
`id1_v2_same_ids.gpx` `98d9d08f…`, `d1_originals.kml` = `a1_export_originals.kml` =
`f54809d5…`).

<a id="new-folder-kml-with-ids"></a>
### `new-folder-kml-with-ids` (run id1): edited KML, ids kept, imported into a new folder

The edited copy is `b_v2/id1_v2k_same_ids.kml` (names ` · V2k`, every `<Data name="id">` kept),
imported ticked. Result: 3 new uuids. The notes were empty, the icon and colours were onX
defaults, and the line became a *Line* (`d_reexport/d4_v2k_same_ids_kml.gpx`). The originals
were untouched. This run reproduced the same behaviour without a folder: see
[`no-folder-kml-with-ids`](#no-folder-kml-with-ids).

<a id="new-folder-cairn-output"></a>
### `new-folder-cairn-output` (run id1): Cairn's normal output, imported into a new folder

The originals' GPX and KML exports went through `web/bridge.py` (`load_files` → `apply_edits` →
`export_zip`), with each name gaining ` · V1` and new colours. The result was three files
(`b_v1/*_{Waypoints,Tracks,Areas}.gpx`) with **no onX id** (`grep -c "id=" b_v1/*.gpx` gives
0, 0, 0). They were imported ticked, as 3 POSTs. Result: 3 new uuids, and the originals were
untouched. Cairn's `<time>` pass-through gave the new track a `createdAt` equal to the export
moment, the same effect seen in every GPX test here.

<a id="format-inventory"></a>
## Export format: complete inventory, and what was missed before

Every normalised file was compared, not just the fields known to matter. Across all nine
tests, `export-1.gpx` is the same document once the test id, uuids, times, latitudes and DEM
elevation are masked, except for element order: 7 files list `wpt, rte, trk` and 2 list
`wpt, trk, rte`. The KMLs likewise differ only in Placemark order. This was checked by script
(`norm_check.py`, described under [Re-running](#rerun)).

**What onX does to the hand-written upload** (`original.gpx` → `export-1.gpx`, verbatim in the
[appendix](#appendix-original-to-export)):

| Aspect | Upload | onX export | Noted before? |
|---|---|---|---|
| XML declaration | `<?xml version="1.0" encoding="UTF-8"?>` | **none** in GPX; the KML has one | No |
| Root attributes | `xmlns`, `xmlns:onx`, `version`, `creator="Cairn…"` | `xmlns:onx` first, then `xmlns`, **`xmlns:xsi` and `xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"`**, `version="1.1"`, `creator="onXmaps backcountry web"` | creator yes; xsi no |
| `<metadata>` | `<name>…</name>` | `<metadata/>`, empty | Yes |
| Whitespace | indented | one line | Yes |
| Order | wpt, trk, rte | wpt, then rte/trk in **varying** order | No |
| `xmlns` on children | — | `<name xmlns="http://www.topografix.com/GPX/1/1">` and the same on `<desc>`, **inside `<rte>` only** | Shown in id1 excerpts, never called out |
| `<desc>` | the note | `name=`, `notes=`, `id=`, then per kind `color=`/`icon=` (wpt), `color=`/`style=`/`weight=` (trk), `type=Area`/`color=`/`weight=`/`fill_color=` (area) | Yes |
| Number format | `46.2400`, `-121.5000` | `46.24`, `-121.5`: trailing zeros trimmed | No |
| Waypoint colour | `rgba(255,51,0,1)` | `rgba(255, 51, 0, 1)`, **with spaces**; lines and areas keep `rgba(8,122,255,1)` without spaces | No |
| Waypoint `<ele>`/`<time>` | none | none in GPX; KML `<coordinates>` third value = DEM elevation (e.g. `2136.199951172`) | Partly (KML DEM yes) |
| Track points | `<trkpt/>` | `<ele>0</ele><time>EXPORT-MOMENT</time>` on every point | Yes |
| Track extensions | color, style, weight | the same | — |
| Area fill | `onx:fill_color rgba(132,212,0,0.1)` | **`rgba(74,144,226,0.1)`**: the uploaded fill is ignored and onX's default stored | id1 said "default fill", not that the upload was ignored |
| Area weight | none | `weight=4.0` / `<onx:weight>4.0</onx:weight>` added | No |
| KML line / area coordinates | — | third value `0` | No |
| KML empty note | — | `<value>` + newline + `</value>` | No |
| KML Placemark order | — | follows the folder's internal list: uuid-ascending after a fresh page load, insertion order right after Add Content | No |
| Folder identity | — | none in either format | Yes |

**What was missed or wrong in earlier docs.**

- id1 said "only `<trkpt><time>` differs" between exports of an unchanged folder. That is true
  of its pair, but not in general: **element order can also change**
  ([`multi-step-cycle-gpx`](#multi-step-cycle-gpx)). The byte-identical KML results in id1 and
  here hold because no Add Content happened in between.
- id1 tested only the ticked path and assumed the unticked path was different. The client
  code shows the only difference is whether a new folder is created. Nothing targets an
  existing folder ([What the Web Map offers](#import-paths)).
- The GPX root's `xsi` namespace and `schemaLocation`, trailing-zero trimming, spaced waypoint
  colours, the ignored uploaded fill, the added area weight, and the newline in empty KML
  notes were never recorded.
- `docs/ONX_TESTING.md` says "Re-import of an onX export … originals left untouched". That
  stays true, and is now shown for the unticked path and for two cycles too.

<a id="confidence"></a>
## Confidence and limits

**Confidence: high** that on 2026-10-23 the Web Map importer is create-only on every path it
offers. Four independent kinds of evidence agree in every test: the full-file export diffs
(checked per id), the page's own re-fetched records (field for field, `updatedAt` included),
the import response (which lists only new uuids), and the account-wide digest and counts. The
positive control in [`onx-edit-then-reimport`](#onx-edit-then-reimport) shows the method does
detect a real in-place change.

**Limits.**

- Server behaviour can change at any time, and parsing is server-side. Re-run before anything
  depends on this.
- Only the Web Map was tested. The phone apps' import was not.
- Not exercised: dropping a file outside the import card (code says nothing else feeds the
  importer), the per-markup Export, Share and Manage Access, and the unlabelled button on the
  Import Complete card.
- Only ids of live markups in this account were used. Ids of deleted markups, of another
  account's markups, or of markups shared into this account were not tried. Neither were other
  placements (`<wpt id>`, `<onx:id>`, `Placemark@id`), which onX's exports do not use.
- Tracks: the account-wide digest covers every track (the store held all 4 pages). Raw API
  bodies were saved only at baseline and for test 1. The other steps rely on the store.
- KML was round-tripped without a folder and unmodified, not through a multi-step cycle.
  KML imports drop all styling and notes, so a KML cycle cannot carry anything to compare
  beyond names and geometry.
- The 512-byte projection in [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) is extrapolated.
- One waypoint, one line and one area per test.

<a id="implications"></a>
## Implications for Cairn

- **Round trip = replace.** Cairn cannot make onX update a markup. "Edit and send back" must
  stay "delete the originals in onX, then import". This matches DECISIONS/ROADMAP (Phase 6
  dropped, "replace" wording). The UI should keep saying it, because a user who imports into
  the originals' folder ([`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids)) or
  re-imports unchanged ([`reimport-unmodified-gpx`](#reimport-unmodified-gpx)) gets silent
  duplicates with identical names.
- **Keep not writing onX ids.** `cairn/core/writers.py:_desc_text` writes only the note unless
  `debug_desc=True`, which `web/bridge.py` never passes. The readers keep the id in memory
  only (`cairn/io/document_adapter.py` `ONX_ID_KEY = "cairn_onx_id"`). An `id=` in `<desc>`
  could never update anything, and onX would store it as visible note text that nests again on
  every cycle ([`multi-step-cycle-gpx`](#multi-step-cycle-gpx)). The `debug_desc` path, which
  writes `id=` with a fresh `uuid4` when the source has none, must stay unreachable from the
  web UI.
- **Cairn's reader already copes with nested exports.** On
  `multi-step-cycle-gpx.export-3.gpx`, whose waypoint `<desc>` holds three `name=` lines, four
  `notes=` and three `id=` lines, `cairn/io/onx_gpx.read_onx_gpx` returned the innermost note
  (`edited-2 waypoint note`) and the **last** `id=` (`5396e8c2-…`), which is the markup's real
  current uuid. A test pinning this would protect it.
- **Suggested guard (not done here).** A test that loads an onX export through
  `bridge.load_files` → `export_zip` and asserts that no source uuid appears in the output.
  Today only a CalTopo-sourced case asserts `"id=" not in gpx`
  (`tests/test_writers_waypoints.py:81`).
- **Track times.** Cairn passes onX's `<trkpt><time>` through. Those times are the moment of
  the export, so every re-imported track claims to have been created then, across cycles too.
  Dropping times that are identical across the whole track would avoid it. That is a product
  decision.
- **Comparing exports** (any future verify step) must key on the markup id. It must ignore
  `<trkpt><time>` and element order, and must not compare files by sha.
- **Area fill.** onX ignores `onx:fill_color` on import and always stores
  `rgba(74,144,226,0.1)`. Cairn's area fill colour does not survive into onX.
  `docs/ONX_TESTING.md` "Area color / fill: Only via GPX `<rte>` … `onx:fill_color`" should be
  re-checked against this.

<a id="created"></a>
## Created in onX (the owner deletes: markups first, then folders)

onX keeps a folder's markups when the folder is deleted, so delete the markups first. Searching
All Content for each test id finds both copies, including the unfiled ones. After cleanup the
account should be back to 445 waypoints, 188 tracks, 12 areas, 1 line, 2 routes (648) and 13
folders.

**Folders (14).**

| Folder | uuid |
|---|---|
| `ZZTEST · no-folder-gpx-with-ids · original` | `d8fd6867-202e-4fea-9157-e9ad50362ccc` |
| `ZZTEST · no-folder-gpx-with-ids · reimported` | `1ee20f00-ec53-44fb-8560-f436e5c7d6ea` |
| `ZZTEST · no-folder-kml-with-ids · original` | `b0c8aac1-e84c-4f61-80c1-8c240af26612` |
| `ZZTEST · no-folder-kml-with-ids · reimported` | `1bb0cb4a-2a76-4bbc-ac40-832692a7298b` |
| `ZZTEST · originals-folder-gpx-with-ids · original` (6 markups) | `26670ea2-6b1a-40b3-8be6-5f1401767b86` |
| `ZZTEST · another-folder-gpx-with-ids · original` | `a6d3c060-bd1c-4dfe-821e-291a1eb6d57b` |
| `ZZTEST · another-folder-gpx-with-ids · target` (was the probe folder `ZZTEST · folder-menu-probe · empty`) | `fe79dbb9-91cb-47bd-96ee-f00a59025e7b` |
| `ZZTEST · reimport-unmodified-gpx · original` | `e4ad9411-ba6f-407a-9d36-8c17b90d678b` |
| `ZZTEST · reimport-unmodified-kml · original` | `bb136579-ca69-4e28-864a-efc85ba69dec` |
| `ZZTEST · same-name-coords-no-ids · original` | `08b27940-6ac7-4adf-8e51-0d68a21c9c32` |
| `ZZTEST · onx-edit-then-reimport · original` | `78df97a5-7f1f-4a70-89bb-1ad7ae969858` |
| `ZZTEST · multi-step-cycle-gpx · original` | `e767832f-2081-4550-b443-35e34cf9376a` |
| `ZZTEST · multi-step-cycle-gpx · reimported` | `2fac9d28-4f09-41fd-abaf-f2bed4060ec5` |
| `ZZTEST · multi-step-cycle-gpx · reimported-2` | `ad5d9fc6-8f47-4a4e-96ae-324be9948416` |

**Markups (57: 19 waypoints, 17 tracks, 2 lines, 19 areas).**

| Test | Markup | Kind | uuid | Folder |
|---|---|---|---|---|
| [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids) | `ZZTEST no-folder-gpx-with-ids · area` | area | `28b5bfba-8279-4844-94b1-78c15b022e6f` | ZZTEST · no-folder-gpx-with-ids · original |
| [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids) | `ZZTEST no-folder-gpx-with-ids · line` | track | `52efaa65-c386-4060-b3a5-3384d82cd917` | ZZTEST · no-folder-gpx-with-ids · original |
| [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids) | `ZZTEST no-folder-gpx-with-ids · waypoint` | waypoint | `47872e75-1406-44f1-8275-73979705847a` | ZZTEST · no-folder-gpx-with-ids · original |
| [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids) | `ZZTEST no-folder-gpx-with-ids · area · edited` | area | `e8a6d257-1843-4fd2-9aef-92ba3362ca09` | ZZTEST · no-folder-gpx-with-ids · reimported |
| [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids) | `ZZTEST no-folder-gpx-with-ids · line · edited` | track | `bb0f9c00-79e5-4a55-8243-b3512988355f` | ZZTEST · no-folder-gpx-with-ids · reimported |
| [`no-folder-gpx-with-ids`](#no-folder-gpx-with-ids) | `ZZTEST no-folder-gpx-with-ids · waypoint · edited` | waypoint | `519df497-cfae-4e03-ad14-b9b7fea3e794` | ZZTEST · no-folder-gpx-with-ids · reimported |
| [`no-folder-kml-with-ids`](#no-folder-kml-with-ids) | `ZZTEST no-folder-kml-with-ids · area` | area | `409039e4-9d20-4d28-918f-3ced1e0a641f` | ZZTEST · no-folder-kml-with-ids · original |
| [`no-folder-kml-with-ids`](#no-folder-kml-with-ids) | `ZZTEST no-folder-kml-with-ids · line` | track | `682b8b22-6769-442e-8b1c-6a59037f44fb` | ZZTEST · no-folder-kml-with-ids · original |
| [`no-folder-kml-with-ids`](#no-folder-kml-with-ids) | `ZZTEST no-folder-kml-with-ids · waypoint` | waypoint | `a324b93f-4c81-4019-9dfa-cc0b63820733` | ZZTEST · no-folder-kml-with-ids · original |
| [`no-folder-kml-with-ids`](#no-folder-kml-with-ids) | `ZZTEST no-folder-kml-with-ids · area · edited` | area | `a1ad493e-416a-47b2-b39a-44c1dfb5f409` | ZZTEST · no-folder-kml-with-ids · reimported |
| [`no-folder-kml-with-ids`](#no-folder-kml-with-ids) | `ZZTEST no-folder-kml-with-ids · line · edited` | line | `7f6aaea3-1474-4a78-94bd-fd19abf1cd81` | ZZTEST · no-folder-kml-with-ids · reimported |
| [`no-folder-kml-with-ids`](#no-folder-kml-with-ids) | `ZZTEST no-folder-kml-with-ids · waypoint · edited` | waypoint | `2a43ffc5-dec2-48f5-ac40-ce352d363473` | ZZTEST · no-folder-kml-with-ids · reimported |
| [`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids) | `ZZTEST originals-folder-gpx-with-ids · area` | area | `2e584928-963d-485e-9ce8-ad5f45f86930` | ZZTEST · originals-folder-gpx-with-ids · original |
| [`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids) | `ZZTEST originals-folder-gpx-with-ids · line` | track | `4d5eed1d-4818-4619-a4cc-68eeb73f2bba` | ZZTEST · originals-folder-gpx-with-ids · original |
| [`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids) | `ZZTEST originals-folder-gpx-with-ids · waypoint` | waypoint | `3546736f-8934-49de-b12a-55be8a880bec` | ZZTEST · originals-folder-gpx-with-ids · original |
| [`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids) | `ZZTEST originals-folder-gpx-with-ids · area · edited` | area | `10d1ae24-b8c3-4c77-8a04-76e1d17a6c86` | ZZTEST · originals-folder-gpx-with-ids · original |
| [`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids) | `ZZTEST originals-folder-gpx-with-ids · line · edited` | track | `79719427-ecdf-4fc0-a5e1-1c9c93fce69c` | ZZTEST · originals-folder-gpx-with-ids · original |
| [`originals-folder-gpx-with-ids`](#originals-folder-gpx-with-ids) | `ZZTEST originals-folder-gpx-with-ids · waypoint · edited` | waypoint | `041c7d22-fa60-405f-8c28-d58f0d0d3c3c` | ZZTEST · originals-folder-gpx-with-ids · original |
| [`another-folder-gpx-with-ids`](#another-folder-gpx-with-ids) | `ZZTEST another-folder-gpx-with-ids · area` | area | `81a06c29-783f-498c-b177-1d73bfa9a6ee` | ZZTEST · another-folder-gpx-with-ids · original |
| [`another-folder-gpx-with-ids`](#another-folder-gpx-with-ids) | `ZZTEST another-folder-gpx-with-ids · line` | track | `c272da8a-d93d-4fa1-8f86-27c7b6fa83de` | ZZTEST · another-folder-gpx-with-ids · original |
| [`another-folder-gpx-with-ids`](#another-folder-gpx-with-ids) | `ZZTEST another-folder-gpx-with-ids · waypoint` | waypoint | `987e04fc-24a2-440e-afcc-b9892fc01a02` | ZZTEST · another-folder-gpx-with-ids · original |
| [`another-folder-gpx-with-ids`](#another-folder-gpx-with-ids) | `ZZTEST another-folder-gpx-with-ids · area · edited` | area | `b4906c36-d9a9-4b5d-afa4-57dccd1e86de` | ZZTEST · another-folder-gpx-with-ids · target |
| [`another-folder-gpx-with-ids`](#another-folder-gpx-with-ids) | `ZZTEST another-folder-gpx-with-ids · line · edited` | track | `4471b2b4-98c3-40cc-a972-ee46e6b3a919` | ZZTEST · another-folder-gpx-with-ids · target |
| [`another-folder-gpx-with-ids`](#another-folder-gpx-with-ids) | `ZZTEST another-folder-gpx-with-ids · waypoint · edited` | waypoint | `f0e7ba5f-ce84-408a-b7ea-06bfbf6d828a` | ZZTEST · another-folder-gpx-with-ids · target |
| [`reimport-unmodified-gpx`](#reimport-unmodified-gpx) | `ZZTEST reimport-unmodified-gpx · area` | area | `e0d779ba-3471-4cd6-ad38-c6c0ff24ec52` | ZZTEST · reimport-unmodified-gpx · original |
| [`reimport-unmodified-gpx`](#reimport-unmodified-gpx) | `ZZTEST reimport-unmodified-gpx · area` | area | `42cfdc7f-09ca-4fc7-9945-04ffd86fa9e5` | **no folder** |
| [`reimport-unmodified-gpx`](#reimport-unmodified-gpx) | `ZZTEST reimport-unmodified-gpx · line` | track | `6af3b7f4-ceeb-4da6-85c1-59b4e1dfadec` | ZZTEST · reimport-unmodified-gpx · original |
| [`reimport-unmodified-gpx`](#reimport-unmodified-gpx) | `ZZTEST reimport-unmodified-gpx · line` | track | `4601258a-96a8-4c29-ae67-84202ae0d52e` | **no folder** |
| [`reimport-unmodified-gpx`](#reimport-unmodified-gpx) | `ZZTEST reimport-unmodified-gpx · waypoint` | waypoint | `b3a3b230-ccb0-4e3f-bea5-ed7370e9bd17` | ZZTEST · reimport-unmodified-gpx · original |
| [`reimport-unmodified-gpx`](#reimport-unmodified-gpx) | `ZZTEST reimport-unmodified-gpx · waypoint` | waypoint | `fc69d893-cfc2-48a1-b67b-4ee771b5a433` | **no folder** |
| [`reimport-unmodified-kml`](#reimport-unmodified-kml) | `ZZTEST reimport-unmodified-kml · area` | area | `7b3263e5-7845-4419-a659-7b0dc3404d5a` | ZZTEST · reimport-unmodified-kml · original |
| [`reimport-unmodified-kml`](#reimport-unmodified-kml) | `ZZTEST reimport-unmodified-kml · area` | area | `a332a9e1-c301-402f-8b88-f0c9520c70df` | **no folder** |
| [`reimport-unmodified-kml`](#reimport-unmodified-kml) | `ZZTEST reimport-unmodified-kml · line` | track | `679fcae0-7340-4d53-a6fb-e5ff38c5d982` | ZZTEST · reimport-unmodified-kml · original |
| [`reimport-unmodified-kml`](#reimport-unmodified-kml) | `ZZTEST reimport-unmodified-kml · line` | line | `0beda38c-6f3e-4d3e-b02a-9c8bf2ebaef5` | **no folder** |
| [`reimport-unmodified-kml`](#reimport-unmodified-kml) | `ZZTEST reimport-unmodified-kml · waypoint` | waypoint | `9c7c4d56-847a-4e88-92cb-31bad51d2c99` | ZZTEST · reimport-unmodified-kml · original |
| [`reimport-unmodified-kml`](#reimport-unmodified-kml) | `ZZTEST reimport-unmodified-kml · waypoint` | waypoint | `ad2c2df4-d4b4-4c2d-b057-f6e455c37de4` | **no folder** |
| [`same-name-coords-no-ids`](#same-name-coords-no-ids) | `ZZTEST same-name-coords-no-ids · area` | area | `5c0ccf3b-94bf-441e-8e0c-b379c07e9c1f` | ZZTEST · same-name-coords-no-ids · original |
| [`same-name-coords-no-ids`](#same-name-coords-no-ids) | `ZZTEST same-name-coords-no-ids · area` | area | `744e7c3a-c727-4ced-9865-0d0e639b7fbf` | **no folder** |
| [`same-name-coords-no-ids`](#same-name-coords-no-ids) | `ZZTEST same-name-coords-no-ids · line` | track | `e3530460-8580-42c2-ae45-2b4c8a83eecc` | ZZTEST · same-name-coords-no-ids · original |
| [`same-name-coords-no-ids`](#same-name-coords-no-ids) | `ZZTEST same-name-coords-no-ids · line` | track | `46bcf1ec-0992-450e-8789-858705cabe7c` | **no folder** |
| [`same-name-coords-no-ids`](#same-name-coords-no-ids) | `ZZTEST same-name-coords-no-ids · waypoint` | waypoint | `fe639101-a5bd-4d28-b177-931a49d6a74e` | ZZTEST · same-name-coords-no-ids · original |
| [`same-name-coords-no-ids`](#same-name-coords-no-ids) | `ZZTEST same-name-coords-no-ids · waypoint` | waypoint | `ff1b05d8-8238-4b95-ac38-10c78a447fa3` | **no folder** |
| [`onx-edit-then-reimport`](#onx-edit-then-reimport) | `ZZTEST onx-edit-then-reimport · area` | area | `0ec68d98-dc72-45b5-a3ec-38b6c5d2e313` | ZZTEST · onx-edit-then-reimport · original |
| [`onx-edit-then-reimport`](#onx-edit-then-reimport) | `ZZTEST onx-edit-then-reimport · area` | area | `15294750-e348-476d-b079-f1f861372ee3` | **no folder** |
| [`onx-edit-then-reimport`](#onx-edit-then-reimport) | `ZZTEST onx-edit-then-reimport · line` | track | `24eba6da-961b-43ce-b99f-6873a24972a8` | ZZTEST · onx-edit-then-reimport · original |
| [`onx-edit-then-reimport`](#onx-edit-then-reimport) | `ZZTEST onx-edit-then-reimport · line` | track | `eb082454-475e-4654-82cb-defab99c2129` | **no folder** |
| [`onx-edit-then-reimport`](#onx-edit-then-reimport) | `ZZTEST onx-edit-then-reimport · waypoint` | waypoint | `6da8d8f7-1cdd-4a77-804c-e08a44f881ab` | **no folder** |
| [`onx-edit-then-reimport`](#onx-edit-then-reimport) | `ZZTEST onx-edit-then-reimport · waypoint · edited-in-onx` | waypoint | `3adcc6cb-db9c-48ae-9d4e-eb3d5b800dc0` | ZZTEST · onx-edit-then-reimport · original |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · area` | area | `ac601e74-6398-490f-828c-c60d634997e2` | ZZTEST · multi-step-cycle-gpx · original |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · line` | track | `bf3a774b-9ed1-44e7-8909-6c675772a748` | ZZTEST · multi-step-cycle-gpx · original |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · waypoint` | waypoint | `a218c42b-6c46-419e-a1fe-a713aff5d767` | ZZTEST · multi-step-cycle-gpx · original |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · area · edited` | area | `5d4bb89a-03bf-404b-bbea-ae928a1a9bc9` | ZZTEST · multi-step-cycle-gpx · reimported |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · area · edited-2` | area | `0b54c7db-1da4-484a-bf0b-c3d40e5bce33` | ZZTEST · multi-step-cycle-gpx · reimported-2 |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · line · edited` | track | `897270bc-0ec0-4ef1-9279-dfeaa84890a9` | ZZTEST · multi-step-cycle-gpx · reimported |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · line · edited-2` | track | `69d7fc78-feab-417d-93d5-29dbe12af124` | ZZTEST · multi-step-cycle-gpx · reimported-2 |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · waypoint · edited` | waypoint | `4b1c36f0-6fab-4162-a345-9ad6b2785dee` | ZZTEST · multi-step-cycle-gpx · reimported |
| [`multi-step-cycle-gpx`](#multi-step-cycle-gpx) | `ZZTEST multi-step-cycle-gpx · waypoint · edited-2` | waypoint | `5396e8c2-051c-4a8c-a6e7-761af2835c02` | ZZTEST · multi-step-cycle-gpx · reimported-2 |

<a id="rerun"></a>
## Re-running

About 5 minutes per test, by hand or by driving the Web Map:

1. Write `<test-id>.original.gpx`: one waypoint, one `<trk>` and one `<rte><type>Area`, in
   Cairn's GPX dialect, on an empty patch of map.
2. Import it ticked, rename the folder `ZZTEST · <test-id> · original`, export GPX and KML.
3. Make the variant by text replacement only, and log every replacement.
4. Import it with the box verifiably unticked.
5. Compare: (a) re-export the originals' folder and diff it per markup id, ignoring
   `<trkpt><time>` and order; (b) the page's re-fetched `GET /v1/markups/*` records for the
   originals (`updatedAt`); (c) the import response's uuid list.

The helper scripts used for this run were not committed. They did: originals generation; the
edit-by-replacement; a store snapshot (the page's in-memory markup store via its webpack
require: uuid, timestamps, notes, colour, geometry, plus a digest of all other markups); the
`><`-split diff; the per-id export comparison; and the export-1 normalisation check. Each is
small enough to rewrite from this description.

<a id="appendix"></a>
## Appendix: full-file diffs

All diffs below use the one normalisation stated in [Method](#method). Every pair not shown in
full was listed above with its result: byte-identical, or `<trkpt><time>` only, confirmed per
id.

<a id="appendix-original-to-export"></a>
### What onX does to an upload: `original.gpx` → `export-1.gpx` (`no-folder-gpx-with-ids`)

The other eight tests give the same diff once test id, uuids, times and coordinates are
masked, apart from the `rte`/`trk` order ([Export format](#format-inventory)).

```diff
--- no-folder-gpx-with-ids.original.gpx
+++ no-folder-gpx-with-ids.export-1.gpx
@@ -1,43 +1,68 @@
-<?xml version="1.0" encoding="UTF-8"?>
-<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1" creator="Cairn - CalTopo to OnX Migration Tool">
-  <metadata>
-    <name>ZZTEST no-folder-gpx-with-ids original</name>
-  </metadata>
-  <wpt lat="46.2452" lon="-121.4911">
-    <name>ZZTEST no-folder-gpx-with-ids · waypoint</name>
-    <desc>original waypoint note</desc>
-    <extensions>
-      <onx:icon>Summit</onx:icon>
-      <onx:color>rgba(255,51,0,1)</onx:color>
-    </extensions>
-  </wpt>
-  <trk>
-    <name>ZZTEST no-folder-gpx-with-ids · line</name>
-    <desc>original line note</desc>
-    <extensions>
-      <onx:color>rgba(8,122,255,1)</onx:color>
-      <onx:style>solid</onx:style>
-      <onx:weight>4.0</onx:weight>
-    </extensions>
-    <trkseg>
-      <trkpt lat="46.2400" lon="-121.5000"/>
-      <trkpt lat="46.2410" lon="-121.4950"/>
-      <trkpt lat="46.2430" lon="-121.4920"/>
-      <trkpt lat="46.2450" lon="-121.4900"/>
-    </trkseg>
-  </trk>
-  <rte>
-    <name>ZZTEST no-folder-gpx-with-ids · area</name>
-    <desc>original area note</desc>
-    <type>Area</type>
-    <extensions>
-      <onx:color>rgba(132,212,0,1)</onx:color>
-      <onx:fill_color>rgba(132,212,0,0.1)</onx:fill_color>
-    </extensions>
-    <rtept lat="46.2500" lon="-121.5000"/>
-    <rtept lat="46.2500" lon="-121.4900"/>
-    <rtept lat="46.2550" lon="-121.4900"/>
-    <rtept lat="46.2550" lon="-121.5000"/>
-    <rtept lat="46.2500" lon="-121.5000"/>
-  </rte>
+<gpx xmlns:onx="https://wwww.onxmaps.com/" xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd" version="1.1" creator="onXmaps backcountry web">
+<metadata/>
+<wpt lat="46.2452" lon="-121.4911">
+<name>ZZTEST no-folder-gpx-with-ids · waypoint</name>
+<desc>name=ZZTEST no-folder-gpx-with-ids · waypoint
+notes=original waypoint note
+id=47872e75-1406-44f1-8275-73979705847a
+color=rgba(255, 51, 0, 1)
+icon=Summit</desc>
+<extensions>
+<onx:color>rgba(255, 51, 0, 1)</onx:color>
+<onx:icon>Summit</onx:icon>
+</extensions>
+</wpt>
+<rte>
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST no-folder-gpx-with-ids · area</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST no-folder-gpx-with-ids · area
+notes=original area note
+id=28b5bfba-8279-4844-94b1-78c15b022e6f
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)</desc>
+<type>Area</type>
+<extensions>
+<onx:color>rgba(132,212,0,1)</onx:color>
+<onx:weight>4.0</onx:weight>
+<onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
+</extensions>
+<rtept lat="46.25" lon="-121.5"/>
+<rtept lat="46.25" lon="-121.49"/>
+<rtept lat="46.255" lon="-121.49"/>
+<rtept lat="46.255" lon="-121.5"/>
+<rtept lat="46.25" lon="-121.5"/>
+</rte>
+<trk>
+<name>ZZTEST no-folder-gpx-with-ids · line</name>
+<desc>name=ZZTEST no-folder-gpx-with-ids · line
+notes=original line note
+id=52efaa65-c386-4060-b3a5-3384d82cd917
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0</desc>
+<extensions>
+<onx:color>rgba(8,122,255,1)</onx:color>
+<onx:style>solid</onx:style>
+<onx:weight>4.0</onx:weight>
+</extensions>
+<trkseg>
+<trkpt lat="46.24" lon="-121.5">
+<ele>0</ele>
+<time>2026-10-23T14:41:24.746Z</time>
+</trkpt>
+<trkpt lat="46.241" lon="-121.495">
+<ele>0</ele>
+<time>2026-10-23T14:41:24.746Z</time>
+</trkpt>
+<trkpt lat="46.243" lon="-121.492">
+<ele>0</ele>
+<time>2026-10-23T14:41:24.746Z</time>
+</trkpt>
+<trkpt lat="46.245" lon="-121.49">
+<ele>0</ele>
+<time>2026-10-23T14:41:24.746Z</time>
+</trkpt>
+</trkseg>
+</trk>
 </gpx>
```

<a id="appendix-kml-export"></a>
### The matching KML export: `export-1.kml` → `export-2.kml` (`no-folder-gpx-with-ids`)

Byte-identical. For reference, the KML export in full, split at `><`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
<Placemark>
<name>ZZTEST no-folder-gpx-with-ids · area</name>
<ExtendedData>
<Data name="name">
<value>ZZTEST no-folder-gpx-with-ids · area</value>
</Data>
<Data name="notes">
<value>original area note</value>
</Data>
<Data name="id">
<value>28b5bfba-8279-4844-94b1-78c15b022e6f</value>
</Data>
<Data name="type">
<value>Area</value>
</Data>
<Data name="color">
<value>rgba(132,212,0,1)</value>
</Data>
<Data name="weight">
<value>4.0</value>
</Data>
<Data name="fill_color">
<value>rgba(74,144,226,0.1)</value>
</Data>
</ExtendedData>
<Polygon>
<outerBoundaryIs>
<LinearRing>
<coordinates>-121.5,46.25,0 -121.49,46.25,0 -121.49,46.255,0 -121.5,46.255,0 -121.5,46.25,0</coordinates>
</LinearRing>
</outerBoundaryIs>
</Polygon>
</Placemark>
<Placemark>
<name>ZZTEST no-folder-gpx-with-ids · waypoint</name>
<ExtendedData>
<Data name="name">
<value>ZZTEST no-folder-gpx-with-ids · waypoint</value>
</Data>
<Data name="notes">
<value>original waypoint note</value>
</Data>
<Data name="id">
<value>47872e75-1406-44f1-8275-73979705847a</value>
</Data>
<Data name="color">
<value>rgba(255, 51, 0, 1)</value>
</Data>
<Data name="icon">
<value>Summit</value>
</Data>
</ExtendedData>
<Point>
<coordinates>-121.4911,46.2452,2136.199951172</coordinates>
</Point>
</Placemark>
<Placemark>
<name>ZZTEST no-folder-gpx-with-ids · line</name>
<ExtendedData>
<Data name="name">
<value>ZZTEST no-folder-gpx-with-ids · line</value>
</Data>
<Data name="notes">
<value>original line note</value>
</Data>
<Data name="id">
<value>52efaa65-c386-4060-b3a5-3384d82cd917</value>
</Data>
<Data name="color">
<value>rgba(8,122,255,1)</value>
</Data>
<Data name="style">
<value>solid</value>
</Data>
<Data name="weight">
<value>4.0</value>
</Data>
</ExtendedData>
<LineString>
<coordinates>-121.5,46.24,0 -121.495,46.241,0 -121.492,46.243,0 -121.49,46.245,0</coordinates>
</LineString>
</Placemark>
</Document>
</kml>
```

<a id="appendix-kml-reimport"></a>
### What a KML re-import keeps: `export-1.kml` → `reimported-export.kml` (`no-folder-gpx-with-ids`)

```diff
--- no-folder-gpx-with-ids.export-1.kml
+++ no-folder-gpx-with-ids.reimported-export.kml
@@ -4,12 +4,76 @@
 <Placemark>
-<name>ZZTEST no-folder-gpx-with-ids · area</name>
+<name>ZZTEST no-folder-gpx-with-ids · waypoint · edited</name>
 <ExtendedData>
 <Data name="name">
-<value>ZZTEST no-folder-gpx-with-ids · area</value>
+<value>ZZTEST no-folder-gpx-with-ids · waypoint · edited</value>
 </Data>
 <Data name="notes">
-<value>original area note</value>
+<value>name=ZZTEST no-folder-gpx-with-ids · waypoint · edited
+notes=edited waypoint note
+id=47872e75-1406-44f1-8275-73979705847a
+color=rgba(8, 122, 255, 1)
+icon=Camp</value>
 </Data>
 <Data name="id">
-<value>28b5bfba-8279-4844-94b1-78c15b022e6f</value>
+<value>519df497-cfae-4e03-ad14-b9b7fea3e794</value>
+</Data>
+<Data name="color">
+<value>rgba(8, 122, 255, 1)</value>
+</Data>
+<Data name="icon">
+<value>Camp</value>
+</Data>
+</ExtendedData>
+<Point>
+<coordinates>-121.4911,46.2452,2136.199951172</coordinates>
+</Point>
+</Placemark>
+<Placemark>
+<name>ZZTEST no-folder-gpx-with-ids · line · edited</name>
+<ExtendedData>
+<Data name="name">
+<value>ZZTEST no-folder-gpx-with-ids · line · edited</value>
+</Data>
+<Data name="notes">
+<value>name=ZZTEST no-folder-gpx-with-ids · line · edited
+notes=edited line note
+id=52efaa65-c386-4060-b3a5-3384d82cd917
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0</value>
+</Data>
+<Data name="id">
+<value>bb0f9c00-79e5-4a55-8243-b3512988355f</value>
+</Data>
+<Data name="color">
+<value>rgba(8,122,255,1)</value>
+</Data>
+<Data name="style">
+<value>solid</value>
+</Data>
+<Data name="weight">
+<value>4.0</value>
+</Data>
+</ExtendedData>
+<LineString>
+<coordinates>-121.5,46.24,0 -121.495,46.241,0 -121.492,46.243,0 -121.49,46.245,0</coordinates>
+</LineString>
+</Placemark>
+<Placemark>
+<name>ZZTEST no-folder-gpx-with-ids · area · edited</name>
+<ExtendedData>
+<Data name="name">
+<value>ZZTEST no-folder-gpx-with-ids · area · edited</value>
+</Data>
+<Data name="notes">
+<value>name=ZZTEST no-folder-gpx-with-ids · area · edited
+notes=edited area note
+id=28b5bfba-8279-4844-94b1-78c15b022e6f
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)</value>
+</Data>
+<Data name="id">
+<value>e8a6d257-1843-4fd2-9aef-92ba3362ca09</value>
 </Data>
@@ -36,51 +100,2 @@
 </Placemark>
-<Placemark>
-<name>ZZTEST no-folder-gpx-with-ids · waypoint</name>
-<ExtendedData>
-<Data name="name">
-<value>ZZTEST no-folder-gpx-with-ids · waypoint</value>
-</Data>
-<Data name="notes">
-<value>original waypoint note</value>
-</Data>
-<Data name="id">
-<value>47872e75-1406-44f1-8275-73979705847a</value>
-</Data>
-<Data name="color">
-<value>rgba(255, 51, 0, 1)</value>
-</Data>
-<Data name="icon">
-<value>Summit</value>
-</Data>
-</ExtendedData>
-<Point>
-<coordinates>-121.4911,46.2452,2136.199951172</coordinates>
-</Point>
-</Placemark>
-<Placemark>
-<name>ZZTEST no-folder-gpx-with-ids · line</name>
-<ExtendedData>
-<Data name="name">
-<value>ZZTEST no-folder-gpx-with-ids · line</value>
-</Data>
-<Data name="notes">
-<value>original line note</value>
-</Data>
-<Data name="id">
-<value>52efaa65-c386-4060-b3a5-3384d82cd917</value>
-</Data>
-<Data name="color">
-<value>rgba(8,122,255,1)</value>
-</Data>
-<Data name="style">
-<value>solid</value>
-</Data>
-<Data name="weight">
-<value>4.0</value>
-</Data>
-</ExtendedData>
-<LineString>
-<coordinates>-121.5,46.24,0 -121.495,46.241,0 -121.492,46.243,0 -121.49,46.245,0</coordinates>
-</LineString>
-</Placemark>
 </Document>
```

<a id="appendix-cycle"></a>
### `multi-step-cycle-gpx`, every stage

`export-1.gpx` → `edited.gpx` (the cycle-1 edit):

```diff
--- multi-step-cycle-gpx.export-1.gpx
+++ multi-step-cycle-gpx.edited.gpx
@@ -3,11 +3,11 @@
 <wpt lat="46.4052" lon="-121.4911">
-<name>ZZTEST multi-step-cycle-gpx · waypoint</name>
-<desc>name=ZZTEST multi-step-cycle-gpx · waypoint
-notes=original waypoint note
+<name>ZZTEST multi-step-cycle-gpx · waypoint · edited</name>
+<desc>name=ZZTEST multi-step-cycle-gpx · waypoint · edited
+notes=edited waypoint note
 id=a218c42b-6c46-419e-a1fe-a713aff5d767
-color=rgba(255, 51, 0, 1)
-icon=Summit</desc>
+color=rgba(8, 122, 255, 1)
+icon=Camp</desc>
 <extensions>
-<onx:color>rgba(255, 51, 0, 1)</onx:color>
-<onx:icon>Summit</onx:icon>
+<onx:color>rgba(8, 122, 255, 1)</onx:color>
+<onx:icon>Camp</onx:icon>
 </extensions>
@@ -15,5 +15,5 @@
 <rte>
-<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST multi-step-cycle-gpx · area</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST multi-step-cycle-gpx · area
-notes=original area note
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST multi-step-cycle-gpx · area · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST multi-step-cycle-gpx · area · edited
+notes=edited area note
 id=ac601e74-6398-490f-828c-c60d634997e2
@@ -36,5 +36,5 @@
 <trk>
-<name>ZZTEST multi-step-cycle-gpx · line</name>
-<desc>name=ZZTEST multi-step-cycle-gpx · line
-notes=original line note
+<name>ZZTEST multi-step-cycle-gpx · line · edited</name>
+<desc>name=ZZTEST multi-step-cycle-gpx · line · edited
+notes=edited line note
 id=bf3a774b-9ed1-44e7-8909-6c675772a748
```

`edited.gpx` → `export-2.gpx` (what onX stored from it):

```diff
--- multi-step-cycle-gpx.edited.gpx
+++ multi-step-cycle-gpx.export-2.gpx
@@ -5,4 +5,8 @@
 <desc>name=ZZTEST multi-step-cycle-gpx · waypoint · edited
+notes=name=ZZTEST multi-step-cycle-gpx · waypoint · edited
 notes=edited waypoint note
 id=a218c42b-6c46-419e-a1fe-a713aff5d767
+color=rgba(8, 122, 255, 1)
+icon=Camp
+id=4b1c36f0-6fab-4162-a345-9ad6b2785dee
 color=rgba(8, 122, 255, 1)
@@ -14,23 +18,2 @@
 </wpt>
-<rte>
-<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST multi-step-cycle-gpx · area · edited</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST multi-step-cycle-gpx · area · edited
-notes=edited area note
-id=ac601e74-6398-490f-828c-c60d634997e2
-type=Area
-color=rgba(132,212,0,1)
-weight=4.0
-fill_color=rgba(74,144,226,0.1)</desc>
-<type>Area</type>
-<extensions>
-<onx:color>rgba(132,212,0,1)</onx:color>
-<onx:weight>4.0</onx:weight>
-<onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
-</extensions>
-<rtept lat="46.41" lon="-121.5"/>
-<rtept lat="46.41" lon="-121.49"/>
-<rtept lat="46.415" lon="-121.49"/>
-<rtept lat="46.415" lon="-121.5"/>
-<rtept lat="46.41" lon="-121.5"/>
-</rte>
 <trk>
@@ -38,4 +21,9 @@
 <desc>name=ZZTEST multi-step-cycle-gpx · line · edited
+notes=name=ZZTEST multi-step-cycle-gpx · line · edited
 notes=edited line note
 id=bf3a774b-9ed1-44e7-8909-6c675772a748
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0
+id=897270bc-0ec0-4ef1-9279-dfeaa84890a9
 color=rgba(8,122,255,1)
@@ -67,2 +55,29 @@
 </trk>
+<rte>
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST multi-step-cycle-gpx · area · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST multi-step-cycle-gpx · area · edited
+notes=name=ZZTEST multi-step-cycle-gpx · area · edited
+notes=edited area note
+id=ac601e74-6398-490f-828c-c60d634997e2
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)
+id=5d4bb89a-03bf-404b-bbea-ae928a1a9bc9
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)</desc>
+<type>Area</type>
+<extensions>
+<onx:color>rgba(132,212,0,1)</onx:color>
+<onx:weight>4.0</onx:weight>
+<onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
+</extensions>
+<rtept lat="46.41" lon="-121.5"/>
+<rtept lat="46.41" lon="-121.49"/>
+<rtept lat="46.415" lon="-121.49"/>
+<rtept lat="46.415" lon="-121.5"/>
+<rtept lat="46.41" lon="-121.5"/>
+</rte>
 </gpx>
```

`export-2.gpx` → `edited-2.gpx` (the cycle-2 edit):

```diff
--- multi-step-cycle-gpx.export-2.gpx
+++ multi-step-cycle-gpx.edited-2.gpx
@@ -3,6 +3,6 @@
 <wpt lat="46.4052" lon="-121.4911">
-<name>ZZTEST multi-step-cycle-gpx · waypoint · edited</name>
-<desc>name=ZZTEST multi-step-cycle-gpx · waypoint · edited
-notes=name=ZZTEST multi-step-cycle-gpx · waypoint · edited
-notes=edited waypoint note
+<name>ZZTEST multi-step-cycle-gpx · waypoint · edited-2</name>
+<desc>name=ZZTEST multi-step-cycle-gpx · waypoint · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · waypoint · edited-2
+notes=edited-2 waypoint note
 id=a218c42b-6c46-419e-a1fe-a713aff5d767
@@ -19,6 +19,6 @@
 <trk>
-<name>ZZTEST multi-step-cycle-gpx · line · edited</name>
-<desc>name=ZZTEST multi-step-cycle-gpx · line · edited
-notes=name=ZZTEST multi-step-cycle-gpx · line · edited
-notes=edited line note
+<name>ZZTEST multi-step-cycle-gpx · line · edited-2</name>
+<desc>name=ZZTEST multi-step-cycle-gpx · line · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · line · edited-2
+notes=edited-2 line note
 id=bf3a774b-9ed1-44e7-8909-6c675772a748
@@ -56,6 +56,6 @@
 <rte>
-<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST multi-step-cycle-gpx · area · edited</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST multi-step-cycle-gpx · area · edited
-notes=name=ZZTEST multi-step-cycle-gpx · area · edited
-notes=edited area note
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST multi-step-cycle-gpx · area · edited-2</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST multi-step-cycle-gpx · area · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · area · edited-2
+notes=edited-2 area note
 id=ac601e74-6398-490f-828c-c60d634997e2
```

`export-2.kml` → `export-3.kml`:

```diff
--- multi-step-cycle-gpx.export-2.kml
+++ multi-step-cycle-gpx.export-3.kml
@@ -4,11 +4,15 @@
 <Placemark>
-<name>ZZTEST multi-step-cycle-gpx · waypoint · edited</name>
+<name>ZZTEST multi-step-cycle-gpx · waypoint · edited-2</name>
 <ExtendedData>
 <Data name="name">
-<value>ZZTEST multi-step-cycle-gpx · waypoint · edited</value>
+<value>ZZTEST multi-step-cycle-gpx · waypoint · edited-2</value>
 </Data>
 <Data name="notes">
-<value>name=ZZTEST multi-step-cycle-gpx · waypoint · edited
-notes=edited waypoint note
+<value>name=ZZTEST multi-step-cycle-gpx · waypoint · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · waypoint · edited-2
+notes=edited-2 waypoint note
 id=a218c42b-6c46-419e-a1fe-a713aff5d767
+color=rgba(8, 122, 255, 1)
+icon=Camp
+id=4b1c36f0-6fab-4162-a345-9ad6b2785dee
 color=rgba(8, 122, 255, 1)
@@ -17,3 +21,3 @@
 <Data name="id">
-<value>4b1c36f0-6fab-4162-a345-9ad6b2785dee</value>
+<value>5396e8c2-051c-4a8c-a6e7-761af2835c02</value>
 </Data>
@@ -31,11 +35,16 @@
 <Placemark>
-<name>ZZTEST multi-step-cycle-gpx · line · edited</name>
+<name>ZZTEST multi-step-cycle-gpx · line · edited-2</name>
 <ExtendedData>
 <Data name="name">
-<value>ZZTEST multi-step-cycle-gpx · line · edited</value>
+<value>ZZTEST multi-step-cycle-gpx · line · edited-2</value>
 </Data>
 <Data name="notes">
-<value>name=ZZTEST multi-step-cycle-gpx · line · edited
-notes=edited line note
+<value>name=ZZTEST multi-step-cycle-gpx · line · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · line · edited-2
+notes=edited-2 line note
 id=bf3a774b-9ed1-44e7-8909-6c675772a748
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0
+id=897270bc-0ec0-4ef1-9279-dfeaa84890a9
 color=rgba(8,122,255,1)
@@ -45,3 +54,3 @@
 <Data name="id">
-<value>897270bc-0ec0-4ef1-9279-dfeaa84890a9</value>
+<value>69d7fc78-feab-417d-93d5-29dbe12af124</value>
 </Data>
@@ -62,11 +71,17 @@
 <Placemark>
-<name>ZZTEST multi-step-cycle-gpx · area · edited</name>
+<name>ZZTEST multi-step-cycle-gpx · area · edited-2</name>
 <ExtendedData>
 <Data name="name">
-<value>ZZTEST multi-step-cycle-gpx · area · edited</value>
+<value>ZZTEST multi-step-cycle-gpx · area · edited-2</value>
 </Data>
 <Data name="notes">
-<value>name=ZZTEST multi-step-cycle-gpx · area · edited
-notes=edited area note
+<value>name=ZZTEST multi-step-cycle-gpx · area · edited-2
+notes=name=ZZTEST multi-step-cycle-gpx · area · edited-2
+notes=edited-2 area note
 id=ac601e74-6398-490f-828c-c60d634997e2
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)
+id=5d4bb89a-03bf-404b-bbea-ae928a1a9bc9
 type=Area
@@ -77,3 +92,3 @@
 <Data name="id">
-<value>5d4bb89a-03bf-404b-bbea-ae928a1a9bc9</value>
+<value>0b54c7db-1da4-484a-bf0b-c3d40e5bce33</value>
 </Data>
```

`export-1.gpx` → `original-folder.export-2.gpx` (the originals after cycle 1):

```diff
--- multi-step-cycle-gpx.export-1.gpx
+++ multi-step-cycle-gpx.original-folder.export-2.gpx
@@ -51,3 +51,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:10:46.123Z</time>
+<time>2026-10-23T15:12:54.557Z</time>
 </trkpt>
@@ -55,3 +55,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:10:46.123Z</time>
+<time>2026-10-23T15:12:54.557Z</time>
 </trkpt>
@@ -59,3 +59,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:10:46.123Z</time>
+<time>2026-10-23T15:12:54.557Z</time>
 </trkpt>
@@ -63,3 +63,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:10:46.123Z</time>
+<time>2026-10-23T15:12:54.557Z</time>
 </trkpt>
```

`export-1.kml` → `original-folder.export-3.kml` (the originals after cycle 2):

```
(byte-identical: multi-step-cycle-gpx.export-1.kml == multi-step-cycle-gpx.original-folder.export-3.kml)
```

<a id="appendix-edits"></a>
### The test inputs: each derived file against its source

```diff
--- originals-folder-gpx-with-ids.export-1.gpx
+++ originals-folder-gpx-with-ids.edited.gpx
@@ -3,11 +3,11 @@
 <wpt lat="46.2852" lon="-121.4911">
-<name>ZZTEST originals-folder-gpx-with-ids · waypoint</name>
-<desc>name=ZZTEST originals-folder-gpx-with-ids · waypoint
-notes=original waypoint note
+<name>ZZTEST originals-folder-gpx-with-ids · waypoint · edited</name>
+<desc>name=ZZTEST originals-folder-gpx-with-ids · waypoint · edited
+notes=edited waypoint note
 id=3546736f-8934-49de-b12a-55be8a880bec
-color=rgba(255, 51, 0, 1)
-icon=Summit</desc>
+color=rgba(8, 122, 255, 1)
+icon=Camp</desc>
 <extensions>
-<onx:color>rgba(255, 51, 0, 1)</onx:color>
-<onx:icon>Summit</onx:icon>
+<onx:color>rgba(8, 122, 255, 1)</onx:color>
+<onx:icon>Camp</onx:icon>
 </extensions>
@@ -15,5 +15,5 @@
 <rte>
-<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST originals-folder-gpx-with-ids · area</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST originals-folder-gpx-with-ids · area
-notes=original area note
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST originals-folder-gpx-with-ids · area · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST originals-folder-gpx-with-ids · area · edited
+notes=edited area note
 id=2e584928-963d-485e-9ce8-ad5f45f86930
@@ -36,5 +36,5 @@
 <trk>
-<name>ZZTEST originals-folder-gpx-with-ids · line</name>
-<desc>name=ZZTEST originals-folder-gpx-with-ids · line
-notes=original line note
+<name>ZZTEST originals-folder-gpx-with-ids · line · edited</name>
+<desc>name=ZZTEST originals-folder-gpx-with-ids · line · edited
+notes=edited line note
 id=4d5eed1d-4818-4619-a4cc-68eeb73f2bba
```

```diff
--- another-folder-gpx-with-ids.export-1.gpx
+++ another-folder-gpx-with-ids.edited.gpx
@@ -3,11 +3,11 @@
 <wpt lat="46.3052" lon="-121.4911">
-<name>ZZTEST another-folder-gpx-with-ids · waypoint</name>
-<desc>name=ZZTEST another-folder-gpx-with-ids · waypoint
-notes=original waypoint note
+<name>ZZTEST another-folder-gpx-with-ids · waypoint · edited</name>
+<desc>name=ZZTEST another-folder-gpx-with-ids · waypoint · edited
+notes=edited waypoint note
 id=987e04fc-24a2-440e-afcc-b9892fc01a02
-color=rgba(255, 51, 0, 1)
-icon=Summit</desc>
+color=rgba(8, 122, 255, 1)
+icon=Camp</desc>
 <extensions>
-<onx:color>rgba(255, 51, 0, 1)</onx:color>
-<onx:icon>Summit</onx:icon>
+<onx:color>rgba(8, 122, 255, 1)</onx:color>
+<onx:icon>Camp</onx:icon>
 </extensions>
@@ -15,5 +15,5 @@
 <rte>
-<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST another-folder-gpx-with-ids · area</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST another-folder-gpx-with-ids · area
-notes=original area note
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST another-folder-gpx-with-ids · area · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST another-folder-gpx-with-ids · area · edited
+notes=edited area note
 id=81a06c29-783f-498c-b177-1d73bfa9a6ee
@@ -36,5 +36,5 @@
 <trk>
-<name>ZZTEST another-folder-gpx-with-ids · line</name>
-<desc>name=ZZTEST another-folder-gpx-with-ids · line
-notes=original line note
+<name>ZZTEST another-folder-gpx-with-ids · line · edited</name>
+<desc>name=ZZTEST another-folder-gpx-with-ids · line · edited
+notes=edited line note
 id=c272da8a-d93d-4fa1-8f86-27c7b6fa83de
```

```diff
--- no-folder-kml-with-ids.export-1.kml
+++ no-folder-kml-with-ids.edited.kml
@@ -4,9 +4,9 @@
 <Placemark>
-<name>ZZTEST no-folder-kml-with-ids · area</name>
+<name>ZZTEST no-folder-kml-with-ids · area · edited</name>
 <ExtendedData>
 <Data name="name">
-<value>ZZTEST no-folder-kml-with-ids · area</value>
+<value>ZZTEST no-folder-kml-with-ids · area · edited</value>
 </Data>
 <Data name="notes">
-<value>original area note</value>
+<value>edited area note</value>
 </Data>
@@ -37,9 +37,9 @@
 <Placemark>
-<name>ZZTEST no-folder-kml-with-ids · line</name>
+<name>ZZTEST no-folder-kml-with-ids · line · edited</name>
 <ExtendedData>
 <Data name="name">
-<value>ZZTEST no-folder-kml-with-ids · line</value>
+<value>ZZTEST no-folder-kml-with-ids · line · edited</value>
 </Data>
 <Data name="notes">
-<value>original line note</value>
+<value>edited line note</value>
 </Data>
@@ -63,9 +63,9 @@
 <Placemark>
-<name>ZZTEST no-folder-kml-with-ids · waypoint</name>
+<name>ZZTEST no-folder-kml-with-ids · waypoint · edited</name>
 <ExtendedData>
 <Data name="name">
-<value>ZZTEST no-folder-kml-with-ids · waypoint</value>
+<value>ZZTEST no-folder-kml-with-ids · waypoint · edited</value>
 </Data>
 <Data name="notes">
-<value>original waypoint note</value>
+<value>edited waypoint note</value>
 </Data>
@@ -75,6 +75,6 @@
 <Data name="color">
-<value>rgba(255, 51, 0, 1)</value>
+<value>rgba(8, 122, 255, 1)</value>
 </Data>
 <Data name="icon">
-<value>Summit</value>
+<value>Camp</value>
 </Data>
```

<a id="appendix-export2"></a>
### Every `export-1` → `export-2` of an originals' folder

```diff
--- no-folder-kml-with-ids.export-1.gpx
+++ no-folder-kml-with-ids.export-2.gpx
@@ -51,3 +51,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:48:46.317Z</time>
+<time>2026-10-23T14:49:57.170Z</time>
 </trkpt>
@@ -55,3 +55,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:48:46.317Z</time>
+<time>2026-10-23T14:49:57.170Z</time>
 </trkpt>
@@ -59,3 +59,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:48:46.317Z</time>
+<time>2026-10-23T14:49:57.170Z</time>
 </trkpt>
@@ -63,3 +63,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:48:46.317Z</time>
+<time>2026-10-23T14:49:57.170Z</time>
 </trkpt>
```

```diff
--- another-folder-gpx-with-ids.export-1.gpx
+++ another-folder-gpx-with-ids.export-2.gpx
@@ -51,3 +51,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:55:29.896Z</time>
+<time>2026-10-23T14:57:27.615Z</time>
 </trkpt>
@@ -55,3 +55,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:55:29.896Z</time>
+<time>2026-10-23T14:57:27.615Z</time>
 </trkpt>
@@ -59,3 +59,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:55:29.896Z</time>
+<time>2026-10-23T14:57:27.615Z</time>
 </trkpt>
@@ -63,3 +63,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:55:29.896Z</time>
+<time>2026-10-23T14:57:27.615Z</time>
 </trkpt>
```

```
(byte-identical: another-folder-gpx-with-ids.export-1.kml == another-folder-gpx-with-ids.export-2.kml)
```

```diff
--- reimport-unmodified-gpx.export-1.gpx
+++ reimport-unmodified-gpx.export-2.gpx
@@ -30,3 +30,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:58:49.438Z</time>
+<time>2026-10-23T14:59:50.630Z</time>
 </trkpt>
@@ -34,3 +34,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:58:49.438Z</time>
+<time>2026-10-23T14:59:50.630Z</time>
 </trkpt>
@@ -38,3 +38,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:58:49.438Z</time>
+<time>2026-10-23T14:59:50.630Z</time>
 </trkpt>
@@ -42,3 +42,3 @@
 <ele>0</ele>
-<time>2026-10-23T14:58:49.438Z</time>
+<time>2026-10-23T14:59:50.630Z</time>
 </trkpt>
```

```
(byte-identical: reimport-unmodified-gpx.export-1.kml == reimport-unmodified-gpx.export-2.kml)
```

```diff
--- reimport-unmodified-kml.export-1.gpx
+++ reimport-unmodified-kml.export-2.gpx
@@ -30,3 +30,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:01:01.268Z</time>
+<time>2026-10-23T15:02:03.061Z</time>
 </trkpt>
@@ -34,3 +34,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:01:01.268Z</time>
+<time>2026-10-23T15:02:03.061Z</time>
 </trkpt>
@@ -38,3 +38,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:01:01.268Z</time>
+<time>2026-10-23T15:02:03.061Z</time>
 </trkpt>
@@ -42,3 +42,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:01:01.268Z</time>
+<time>2026-10-23T15:02:03.061Z</time>
 </trkpt>
```

```
(byte-identical: reimport-unmodified-kml.export-1.kml == reimport-unmodified-kml.export-2.kml)
```

```diff
--- same-name-coords-no-ids.export-1.gpx
+++ same-name-coords-no-ids.export-2.gpx
@@ -51,3 +51,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:06:09.199Z</time>
+<time>2026-10-23T15:07:18.720Z</time>
 </trkpt>
@@ -55,3 +55,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:06:09.199Z</time>
+<time>2026-10-23T15:07:18.720Z</time>
 </trkpt>
@@ -59,3 +59,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:06:09.199Z</time>
+<time>2026-10-23T15:07:18.720Z</time>
 </trkpt>
@@ -63,3 +63,3 @@
 <ele>0</ele>
-<time>2026-10-23T15:06:09.199Z</time>
+<time>2026-10-23T15:07:18.720Z</time>
 </trkpt>
```

```
(byte-identical: same-name-coords-no-ids.export-1.kml == same-name-coords-no-ids.export-2.kml)
```

```
(byte-identical: no-folder-kml-with-ids.export-1.kml == no-folder-kml-with-ids.export-2.kml)
```

```
(byte-identical: no-folder-gpx-with-ids.export-1.kml == no-folder-gpx-with-ids.export-2.kml)
```

```diff
--- originals-folder-gpx-with-ids.export-1.kml
+++ originals-folder-gpx-with-ids.export-2.kml
@@ -3,2 +3,68 @@
 <Document>
+<Placemark>
+<name>ZZTEST originals-folder-gpx-with-ids · waypoint · edited</name>
+<ExtendedData>
+<Data name="name">
+<value>ZZTEST originals-folder-gpx-with-ids · waypoint · edited</value>
+</Data>
+<Data name="notes">
+<value>name=ZZTEST originals-folder-gpx-with-ids · waypoint · edited
+notes=edited waypoint note
+id=3546736f-8934-49de-b12a-55be8a880bec
+color=rgba(8, 122, 255, 1)
+icon=Camp</value>
+</Data>
+<Data name="id">
+<value>041c7d22-fa60-405f-8c28-d58f0d0d3c3c</value>
+</Data>
+<Data name="color">
+<value>rgba(8, 122, 255, 1)</value>
+</Data>
+<Data name="icon">
+<value>Camp</value>
+</Data>
+</ExtendedData>
+<Point>
+<coordinates>-121.4911,46.2852,1636.300048828</coordinates>
+</Point>
+</Placemark>
+<Placemark>
+<name>ZZTEST originals-folder-gpx-with-ids · area · edited</name>
+<ExtendedData>
+<Data name="name">
+<value>ZZTEST originals-folder-gpx-with-ids · area · edited</value>
+</Data>
+<Data name="notes">
+<value>name=ZZTEST originals-folder-gpx-with-ids · area · edited
+notes=edited area note
+id=2e584928-963d-485e-9ce8-ad5f45f86930
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)</value>
+</Data>
+<Data name="id">
+<value>10d1ae24-b8c3-4c77-8a04-76e1d17a6c86</value>
+</Data>
+<Data name="type">
+<value>Area</value>
+</Data>
+<Data name="color">
+<value>rgba(132,212,0,1)</value>
+</Data>
+<Data name="weight">
+<value>4.0</value>
+</Data>
+<Data name="fill_color">
+<value>rgba(74,144,226,0.1)</value>
+</Data>
+</ExtendedData>
+<Polygon>
+<outerBoundaryIs>
+<LinearRing>
+<coordinates>-121.5,46.29,0 -121.49,46.29,0 -121.49,46.295,0 -121.5,46.295,0 -121.5,46.29,0</coordinates>
+</LinearRing>
+</outerBoundaryIs>
+</Polygon>
+</Placemark>
 <Placemark>
@@ -85,2 +151,33 @@
 </Placemark>
+<Placemark>
+<name>ZZTEST originals-folder-gpx-with-ids · line · edited</name>
+<ExtendedData>
+<Data name="name">
+<value>ZZTEST originals-folder-gpx-with-ids · line · edited</value>
+</Data>
+<Data name="notes">
+<value>name=ZZTEST originals-folder-gpx-with-ids · line · edited
+notes=edited line note
+id=4d5eed1d-4818-4619-a4cc-68eeb73f2bba
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0</value>
+</Data>
+<Data name="id">
+<value>79719427-ecdf-4fc0-a5e1-1c9c93fce69c</value>
+</Data>
+<Data name="color">
+<value>rgba(8,122,255,1)</value>
+</Data>
+<Data name="style">
+<value>solid</value>
+</Data>
+<Data name="weight">
+<value>4.0</value>
+</Data>
+</ExtendedData>
+<LineString>
+<coordinates>-121.5,46.28,0 -121.495,46.281,0 -121.492,46.283,0 -121.49,46.285,0</coordinates>
+</LineString>
+</Placemark>
 </Document>
```

<a id="appendix-reimported"></a>
### Exports of the re-imported copies

```diff
--- no-folder-kml-with-ids.export-1.gpx
+++ no-folder-kml-with-ids.reimported-export.gpx
@@ -3,11 +3,11 @@
 <wpt lat="46.2652" lon="-121.4911">
-<name>ZZTEST no-folder-kml-with-ids · waypoint</name>
-<desc>name=ZZTEST no-folder-kml-with-ids · waypoint
-notes=original waypoint note
-id=a324b93f-4c81-4019-9dfa-cc0b63820733
-color=rgba(255, 51, 0, 1)
-icon=Summit</desc>
+<name>ZZTEST no-folder-kml-with-ids · waypoint · edited</name>
+<desc>name=ZZTEST no-folder-kml-with-ids · waypoint · edited
+notes=
+id=2a43ffc5-dec2-48f5-ac40-ce352d363473
+color=rgba(8, 122, 255, 1)
+icon=Location</desc>
 <extensions>
-<onx:color>rgba(255, 51, 0, 1)</onx:color>
-<onx:icon>Summit</onx:icon>
+<onx:color>rgba(8, 122, 255, 1)</onx:color>
+<onx:icon>Location</onx:icon>
 </extensions>
@@ -15,9 +15,8 @@
 <rte>
-<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST no-folder-kml-with-ids · area</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST no-folder-kml-with-ids · area
-notes=original area note
-id=409039e4-9d20-4d28-918f-3ced1e0a641f
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST no-folder-kml-with-ids · area · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST no-folder-kml-with-ids · area · edited
+notes=
+id=a1ad493e-416a-47b2-b39a-44c1dfb5f409
 type=Area
-color=rgba(132,212,0,1)
-weight=4.0
+color=rgba(255,51,0,1)
 fill_color=rgba(74,144,226,0.1)</desc>
@@ -25,4 +24,3 @@
 <extensions>
-<onx:color>rgba(132,212,0,1)</onx:color>
-<onx:weight>4.0</onx:weight>
+<onx:color>rgba(255,51,0,1)</onx:color>
 <onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
@@ -35,34 +33,18 @@
 </rte>
-<trk>
-<name>ZZTEST no-folder-kml-with-ids · line</name>
-<desc>name=ZZTEST no-folder-kml-with-ids · line
-notes=original line note
-id=682b8b22-6769-442e-8b1c-6a59037f44fb
-color=rgba(8,122,255,1)
-style=solid
-weight=4.0</desc>
+<rte>
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST no-folder-kml-with-ids · line · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST no-folder-kml-with-ids · line · edited
+notes=
+id=7f6aaea3-1474-4a78-94bd-fd19abf1cd81
+type=Line
+color=rgba(255,51,0,1)</desc>
+<type>Line</type>
 <extensions>
-<onx:color>rgba(8,122,255,1)</onx:color>
-<onx:style>solid</onx:style>
-<onx:weight>4.0</onx:weight>
+<onx:color>rgba(255,51,0,1)</onx:color>
 </extensions>
-<trkseg>
-<trkpt lat="46.26" lon="-121.5">
-<ele>0</ele>
-<time>2026-10-23T14:48:46.317Z</time>
-</trkpt>
-<trkpt lat="46.261" lon="-121.495">
-<ele>0</ele>
-<time>2026-10-23T14:48:46.317Z</time>
-</trkpt>
-<trkpt lat="46.263" lon="-121.492">
-<ele>0</ele>
-<time>2026-10-23T14:48:46.317Z</time>
-</trkpt>
-<trkpt lat="46.265" lon="-121.49">
-<ele>0</ele>
-<time>2026-10-23T14:48:46.317Z</time>
-</trkpt>
-</trkseg>
-</trk>
+<rtept lat="46.26" lon="-121.5"/>
+<rtept lat="46.261" lon="-121.495"/>
+<rtept lat="46.263" lon="-121.492"/>
+<rtept lat="46.265" lon="-121.49"/>
+</rte>
 </gpx>
```

```diff
--- another-folder-gpx-with-ids.edited.gpx
+++ another-folder-gpx-with-ids.reimported-export.gpx
@@ -5,4 +5,8 @@
 <desc>name=ZZTEST another-folder-gpx-with-ids · waypoint · edited
+notes=name=ZZTEST another-folder-gpx-with-ids · waypoint · edited
 notes=edited waypoint note
 id=987e04fc-24a2-440e-afcc-b9892fc01a02
+color=rgba(8, 122, 255, 1)
+icon=Camp
+id=f0e7ba5f-ce84-408a-b7ea-06bfbf6d828a
 color=rgba(8, 122, 255, 1)
@@ -14,23 +18,2 @@
 </wpt>
-<rte>
-<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST another-folder-gpx-with-ids · area · edited</name>
-<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST another-folder-gpx-with-ids · area · edited
-notes=edited area note
-id=81a06c29-783f-498c-b177-1d73bfa9a6ee
-type=Area
-color=rgba(132,212,0,1)
-weight=4.0
-fill_color=rgba(74,144,226,0.1)</desc>
-<type>Area</type>
-<extensions>
-<onx:color>rgba(132,212,0,1)</onx:color>
-<onx:weight>4.0</onx:weight>
-<onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
-</extensions>
-<rtept lat="46.31" lon="-121.5"/>
-<rtept lat="46.31" lon="-121.49"/>
-<rtept lat="46.315" lon="-121.49"/>
-<rtept lat="46.315" lon="-121.5"/>
-<rtept lat="46.31" lon="-121.5"/>
-</rte>
 <trk>
@@ -38,4 +21,9 @@
 <desc>name=ZZTEST another-folder-gpx-with-ids · line · edited
+notes=name=ZZTEST another-folder-gpx-with-ids · line · edited
 notes=edited line note
 id=c272da8a-d93d-4fa1-8f86-27c7b6fa83de
+color=rgba(8,122,255,1)
+style=solid
+weight=4.0
+id=4471b2b4-98c3-40cc-a972-ee46e6b3a919
 color=rgba(8,122,255,1)
@@ -67,2 +55,29 @@
 </trk>
+<rte>
+<name xmlns="http://www.topografix.com/GPX/1/1">ZZTEST another-folder-gpx-with-ids · area · edited</name>
+<desc xmlns="http://www.topografix.com/GPX/1/1">name=ZZTEST another-folder-gpx-with-ids · area · edited
+notes=name=ZZTEST another-folder-gpx-with-ids · area · edited
+notes=edited area note
+id=81a06c29-783f-498c-b177-1d73bfa9a6ee
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)
+id=b4906c36-d9a9-4b5d-afa4-57dccd1e86de
+type=Area
+color=rgba(132,212,0,1)
+weight=4.0
+fill_color=rgba(74,144,226,0.1)</desc>
+<type>Area</type>
+<extensions>
+<onx:color>rgba(132,212,0,1)</onx:color>
+<onx:weight>4.0</onx:weight>
+<onx:fill_color>rgba(74,144,226,0.1)</onx:fill_color>
+</extensions>
+<rtept lat="46.31" lon="-121.5"/>
+<rtept lat="46.31" lon="-121.49"/>
+<rtept lat="46.315" lon="-121.49"/>
+<rtept lat="46.315" lon="-121.5"/>
+<rtept lat="46.31" lon="-121.5"/>
+</rte>
 </gpx>
```
