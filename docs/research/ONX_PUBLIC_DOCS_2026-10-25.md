# What onX publishes about maps and markups — research, 2026-10-25

The owner asked to read everything onX publishes about its mapping: help articles, how-tos, FAQ
and blog pages, plus onX's public web-app code where the docs say nothing. Two questions get a
direct answer: **E1**, the longest name onX takes, and **E4**, onX's note cut on import
(`docs/plans/BULK_RENAME_PROGRESS.md` section 7.2).

The bulk rename plan and build log cited here are archived: `git show
archive/feat-bulk-rename-pre-squash:docs/plans/<name>`.

Public sources only. No onX login was used, nothing on any account was read, and nothing was
imported, uploaded or submitted. Everything was read on 2026-10-25 unless a claim says otherwise.

Evidence tags:

- **[DOC]**: onX's public help-centre article, blog or product page. Help articles were read as
  JSON through Zendesk's public Help Center API (`/api/v2/help_center/en-us/articles.json`), the
  route the 2026-10-22 research used. The title and `updated_at` date are as the API returned them.
- **[CODE]**: onX's public web-app JavaScript, fetched as static files from
  `https://backcountry.onxmaps.com/`: runtime `runtime.0870c5a50beedb21608c.js` and all 805
  files it and the entry page list. Chunk names are content-hashed and rotate on each onX deploy.
- **[OBSERVED]**: what Cairn's own live imports into the owner's account showed (2026-10-22 and
  -23), cited by repo file or commit. These were not re-run here.
- **[UNVERIFIED]**: not settled by any of the above.
- **[INFER]**: my reasoning from tagged facts; the reasoning is shown.

## Summary

1. **onX documents no length limit for a markup name or note anywhere.** I read all 77
   Backcountry help articles, all 118 onX Hunt articles and all 47 onX Fish articles. None
   mentions a name or note length. **[DOC]**
2. **onX's web app caps what you can type** **[CODE]**:
   - waypoint, line, track and area names: 255 characters;
   - route names (Route Builder): 100;
   - folder names: 50;
   - waypoint, line, track, area and folder notes: 512 characters;
   - route notes: no cap.

   A blank name is refused with "Name cannot be blank."
3. **The import is a black box.** The browser posts the raw file to `/v1/markups/import` and the
   server parses it. No name or note rule for imports is visible in public code. **[CODE]**
4. **E1: the longest name onX takes on import is unknown.** The longest imported name Cairn has
   seen survive is 66 characters. Typed names stop at 255 (100 for routes).
5. **E4: onX's docs are silent on the 512-byte note cut, and its code neither confirms nor
   contradicts it.** The cut is Cairn's own measurement (512 UTF-8 bytes, commit `a07f14a`,
   the two round-trip test rounds of 2026-10-22). The web app's 512 cap on typed notes uses the same number but counts
   characters (UTF-16 code units), not bytes.
6. **The 3,303-character "line" note in Cairn's fixtures is an onX Route.** Its name is the Route
   Builder's default, and onX's export writes a Route as `type=Line`. The Route Builder is the
   one editor with no note cap. That explains how a note typed in onX got past 512.
7. **Folder names: onX takes 50 characters, Cairn allows 100.** `instructions.txt` tells the user
   to give each import folder Cairn's folder name, so a name of 51 to 100 characters can't be
   typed in full in onX. This is the main actionable difference.
8. **onX's help still says GPX and KML carry only names and positions.** That contradicts
   Cairn's live imports, where notes, icons, colours and line styles came through GPX. Some
   help text also says GPX turns areas into tracks, while Cairn relies on GPX areas importing
   as areas (ENG-05). Treat that help text as stale, as the 2026-10-22 research already did.

---

## E1. The longest name onX takes

| Kind | Typed in onX on a computer | Blank name | Arriving by import |
|---|---|---|---|
| Waypoint | **255** (`WaypointEditCard`: `nameMaxLength: re`, `const re=255`) | refused: "Name cannot be blank." | unknown |
| Line | **255** (`LineEditCard`, `maxlength:255`) | refused | unknown |
| Track | **255** (the same `LineEditCard`: `isTrackType` routes the save to `updateTrack`) | refused | unknown |
| Area | **255** (`ShapeEditCard`, `maxlength:255`) | refused | unknown |
| Route (Route Builder) | **100** (`RouteBuilderCard`, `maxlength:100`) | refused (the route class validates with the same check) | unknown |
| Folder | **50** (the new-folder and Rename Folder dialog: `maxLength(){return 50}`) | Save off while empty | n/a: an import names its folder `Import mm/dd/yy H:MM` |

Sources **[CODE]**:
- `51366.8e385a444bcd59ff149c.js` (waypoint card);
- `51814.dd2da6a67a31d60aded8.js` (line and track card);
- `80937.9ee849fc5e818fd88f89.js` (area card);
- `75079.4bf3b7ca66c4c6f116ad.js` (route builder);
- `19882.612a0ca0261e4086da67.js`, module `3uFe` (folder name dialog). `7272.8a087709ef027488187c.js` opens it with the label "Rename" plus onX's word for a folder.
- The name check is function `De` in `93023.c712564fe21c8e5d3795.js`. It checks only that a
  name isn't blank and never checks length. The Waypoint, Line, Track, Area and Route classes all
  call it.

How these limits behave **[CODE]**, with one **[INFER]**:

- They are HTML `maxlength` attributes on the input (the shared `XTextInput` component,
  `57235.85d49fc066345d0b91d1.js`). They stop typing and pasting at the limit. Nothing shows an
  error.
- **[INFER]** A `maxlength` attribute doesn't shorten a value the page set itself. A longer name
  that arrived by import would therefore show in full in the editor, and only typing would be
  blocked. Not tried.
- The component's own counter is `maxlength - value.length`, so it counts UTF-16 code units, and
  an emoji counts as 2. The HTML standard measures `maxlength` in the same unit. That wasn't
  tried in a browser here.
- The folder dialog also disables Save over 255, which typing can't reach. It trims the name
  (`v-model` `trim`).
- On Save, the markup cards store `sanitize(name).trim()` and `sanitize(notes).trim()`.
  `sanitize` is DOMPurify 3.4.14 followed by HTML entity decoding (module `LJH7`). So a name or
  note typed in onX on a computer loses leading and trailing whitespace. **[INFER]** It also
  loses any tag-shaped text DOMPurify removes, such as `<Lake>`.

Arriving by import **[CODE]** + **[OBSERVED]** + **[UNVERIFIED]**:

- The importer posts the file unchanged to `POST /v1/markups/import`, and the server parses it
  (`50657.87e3701dffd2f41a9e91.js`, module `bVmq`, the same file as on 2026-10-22). No client
  code checks names. What onX does with a 256- or 300-character imported name (keep, cut or
  reject) can't be read from public code.
- The longest name Cairn has seen survive an import is 66 characters:
  `[r2i1] 11 - Juniper Ridge #2 AS to Cispus Learning Center (FINISH)`. That is Dark Divide's
  longest name (59) plus the test's tag. The second round-trip round of 2026-10-22 had 0 FAIL in
  all 14 runs, so every name came back as sent (`tests/fixtures/roundtrip/r2/README.md`; the name
  is in `r2/i1/dd100-gpx/verify_report.md`). Accents, an em dash and an emoji came through too
  (that round's edge-case set). **[OBSERVED]**
- onX's docs say nothing about name length. **[DOC]**

**Answer.** Typed in onX on a computer, a waypoint, line, track or area name stops at 255
characters. A route name stops at 100 and a folder name at 50. A blank name is refused. Nothing is
cut and no error is shown: the field stops taking text. **Confidence: high** for the web app. The
phone apps' editors are **[UNVERIFIED]**; no public code or doc covers them. **On import, the
limit and what happens over it are unknown.** **Confidence: low.** Nothing public covers it, and
66 characters is the longest name tested. The owner-run probe already listed in
`docs/plans/BULK_RENAME.md` (section 7) and UI-39 (a 300-character name) would settle it. A 255
/ 256 pair, plus a multibyte name, would also tell bytes from characters.

---

## E4. onX's note cut on import

### What Cairn already verified on a real import [OBSERVED]

- **First round-trip round, 2026-10-22** (`tests/fixtures/roundtrip/r1/`, commit `a07f14a`).
  ASCII notes of 513, 600, 1,000 and 3,000 characters, on waypoints and lines, arrived cut to
  512. A 512-character note ending in a 3-byte em dash (514 bytes) arrived as 510 characters.
- **Second round, the same day** (`tests/fixtures/roundtrip/r2/README.md`). Accented and
  em-dash notes of 511 and 512 bytes arrived whole, and a 513-byte note was cut to 512. A cut
  landing inside an `é` drops the partial character.
- **Conclusion so far:** onX keeps the first 512 UTF-8 bytes of an imported note, cut on a
  character boundary (`web/bridge.py` `ONX_IMPORT_NOTE_LIMIT`, `docs/ONX_TESTING.md`).
- **One open case.** A 3,000+ character note from an onX export came back with no note at all
  when re-imported (`tests/fixtures/onx_real/README.md`). Its cause is still unknown; see below.
- **Cairn never cuts a note.** It flags notes over 512 bytes on the row, on the export screen and
  in `instructions.txt`, and writes them whole. Track T tests this, not this doc.

### What onX's docs say [DOC]

They say nothing about any note length, typed or imported. Several articles say instead that
GPX and KML files don't carry notes at all:

- 360057195972 (Backcountry, importing and exporting, updated 2026-04-01): only a markup's
  location and name are saved, and the two formats don't keep "colors, icons, and notes".
- 4472785894285 (moving from AllTrails, updated 2026-07-14): importing doesn't transfer colour,
  line style, line weight, **notes** or photos.
- 4422125175309 (Backcountry, updated 2026-07-14) and Hunt 4422141473037 (updated 2026-07-21):
  "only the position and name" transfer between onX apps.
- onX Hunt's blog post on import and export (modified 2025-07-21) says notes and customizations
  are lost when you export or import on a computer.

Cairn's imports contradict all four: notes arrive from GPX `<desc>`, cut at 512 bytes. So the
docs **disagree** with the observed behaviour and are **silent** on the 512 limit.

### What onX's code says [CODE]

- **The import cut isn't in public code.** The browser sends the raw file, and the cut happens on
  onX's server. The code neither confirms nor contradicts 512 bytes.
- **Typed notes are capped in the editors**, in UTF-16 code units, with a "characters remaining"
  counter:

  | Where | Typed note cap |
  |---|---|
  | Waypoint, line, track, area (their edit cards) | **512** (`notesMaxLength: ae`, `const ae=512`; `maxlength:512` on the line, track and area cards) |
  | Folder notes (folder card, `7272.8a087709ef027488187c.js`, placeholder "Enter folder notes") | **512**, as `docs/ONX_ROUND_TRIP.md` saw in onX on 2026-10-23 |
  | Route (Route Builder, `data-test="notes-input"`) | **none**: no `maxlength`, so no counter |
  | Offline map notes (not a markup) | 255 |

- **The same number, but different units.** The editors count UTF-16 code units; the import
  keeps 512 UTF-8 bytes. A note typed to the full 512 in onX with accents, dashes or emoji can be
  700 to 1,500 bytes. **[INFER]** Such a note survives in onX, but exporting it and importing it
  again (onX's own round trip, or one through Cairn) cuts it. Cairn's byte-based warning already
  catches this case.
- **onX can store notes far longer than 512** **[OBSERVED]** + **[CODE]**. The fixture
  `tests/fixtures/onx_real/onx_web_line_long_note.gpx` holds a 3,303-character note (3,309
  bytes) that onX kept and exported in full. The note sits on an onX **Route**:
  - its name, `Route 10/22/26 13:47`, is the Route class's default name pattern (`Route <date>
    <time>`, `93023.c712564fe21c8e5d3795.js`);
  - onX's GPX export writes a Route with `type=Line`, as it writes a Line (`case"route"` in
    `33209.792d376b438ff1099263.js`).

  The Route Builder's notes field has no cap, so the owner could paste 3,303 characters there.
  The 512-capped line card wasn't involved. **[INFER]** The 512-byte cut therefore belongs to the
  import path, not to how onX stores a note.
- **The code didn't change in between.** The runtime the 2026-10-22 research recorded
  (`runtime.a789a7595c5c72acd102.js`) is still served. 781 of its 792 lazy chunks are
  byte-identical to today's. The waypoint, line, area and route editors, the folder name dialog,
  the import card, the importer and the export builder are all among the unchanged files. Of the
  files this doc cites, only the folder card (`7272`) changed. So these caps were live when the
  long note was typed and during both round-trip rounds.

### The dropped 3,000+ character note [UNVERIFIED]

Public code can't explain it, because the import parse is server-side. Two hypotheses fit the
repo's evidence; neither is tested:

1. The re-imported file was the **KML**. onX ignores KML `<ExtendedData>` entirely
   (`docs/ONX_ROUND_TRIP.md` finding 3), and that is the only place onX's KML export puts notes.
   This fixture's KML has no `<description>`.
2. The re-imported file was the **GPX**. Its `<desc>` holds onX's key=value block, about 3.4 KB.
   onX has a further rule for very long `<desc>` text, between the first round's 3,000 bytes (cut) and this
   size (dropped).

The fixture README doesn't say which file was used. Re-importing the GPX alone would separate
the two; that is an owner-run probe.

### Answer

- **Cairn's own evidence (high confidence):** onX's import keeps the first 512 UTF-8 bytes of a
  note, cut on a character boundary.
- **onX's docs: silent** on any length. They even claim notes aren't carried at all, which
  Cairn's imports disprove.
- **onX's code: neither confirms nor contradicts** the import cut, because it runs on the server.
  It does show that typed notes on waypoints, lines, tracks, areas and folders stop at 512
  characters. Route notes typed in the Route Builder have no cap.
- **Confidence:**
  - high for the typed caps;
  - high that the docs say nothing;
  - medium that nothing public covers the import rule (I read every chunk's text for length
    checks and found none for markups).

---

## Findings by topic

### Import and export

- **Formats and limits.**
  - Import takes GPX or KML only, 4 MB or less, at most 3,000 markups per file, and needs Premium
    or Elite. Sources: Backcountry 5022588722317 (updated 2026-07-20) and 360057195972 (updated
    2026-04-01); Hunt 115002196452 (updated 2026-09-02); Fish 25357459498509. **[DOC]**
  - KMZ and shapefiles can't be imported (Hunt 115002196452; Fish 25357459498509). **[DOC]**
- **The browser's own checks** **[CODE]**, in `98770.bf04e6cb10482fd61f4c.js`:
  - the file must end in `.kml` or `.gpx` ("You may only upload a KML or GPX file.");
  - `size > 4096e3` is refused ("Your file must be under 4 MB."), so the true cap is 4,096,000
    bytes;
  - the same file can't be picked twice;
  - the picker takes several files at once.
- **Converting other files.** For a file onX won't take, the help suggests converting it to GPX
  in Garmin BaseCamp. For a KML that imports but doesn't appear, it suggests GPS Visualizer,
  blaming extra Google Earth data (5022588722317). **[DOC]**
- **What exports carry.**
  - The help says exports keep only location and name, Tracks exported as KML become Lines, and
    Lines and Areas exported as GPX become Tracks (360057195972; Hunt 115002196452). **[DOC]**
  - onX's GPX export code writes notes, colour, icon, style, weight and fill, and marks Lines,
    Routes and Areas with `type=` (`33209.792d376b438ff1099263.js`). **[CODE]**
  - Cairn's imports showed an Area exported as GPX coming back as an Area (ENG-05). **[OBSERVED]**
  - The help text is stale on these points.
- **Import Complete card.**
  - The card lists what arrived, by kind (Waypoints, Tracks, Areas, Lines, Routes). It also lists
    any file that failed, under "Unsuccessful". **[CODE]** (`36154.050f924b55b573a1a96d.js`)
  - The ellipsis button next to **Show on Map** opens a menu: **Add to** (onX's word for folder),
    **Share** and **Delete**. They act on everything the import created, so an import can be put
    into an **existing** folder straight from this card. **[CODE]**, not exercised.
  - This is the button `docs/ONX_ROUND_TRIP.md` recorded as "one unlabelled button (not
    identified)". onX Hunt's import blog describes the same **Add to Folder** step on the phone.
    **[DOC]**
- **The phone apps.**
  - The Backcountry app imports GPX only, one file at a time. KML import needs onX on a computer
    (360057195972). **[DOC]**
  - App export (GPX only) is iPhone and iPad only (360057195972). Hunt's folder export is iOS
    only (Hunt 115002196452). **[DOC]**

### Markups: names, defaults and edits

- **Default names.** A new markup is named `Waypoint`, `Line`, `Track`, `Area` or `Route`, plus
  the date and time. **[CODE]** (`buildDefaultName`, `93023.c712564fe21c8e5d3795.js`)
- **Name limits.** See E1: 255 for waypoints, lines, tracks and areas, 100 for routes. The name
  can't be blank. On Save, names and notes are trimmed and passed through DOMPurify. **[CODE]**
- **What each kind can edit.**
  - Every kind: name, folders and notes.
  - Waypoints add an icon ("Type"), a colour and photos.
  - Lines, tracks and routes add a colour, a style and a weight.
  - Areas add a fill colour plus a border colour, style and weight.
  - Sources: Hunt 360028500652 (updated 2026-08-04); Backcountry 360052239052 (updated
    2026-09-16) and 4417866009357 (updated 2026-07-21). **[DOC]**
  - Hunt's article lists only solid and dashed styles. onX's code and exports also have
    `dot` (`docs/ONX_ROUND_TRIP.md`). **[DOC]** vs **[OBSERVED]**
- **Lines and Tracks share one editor** in onX's web app (`LineEditCard`). Saving calls
  `updateTrack` or `updateLine` depending on the kind. A track's points can be trimmed but not
  split (360052239052). **[CODE]**, **[DOC]**
- **Routes are their own kind.** The Route Builder has its own card, and a paid plan is needed to
  build routes (22965175493133, updated 2026-09-09). **[DOC]** onX's GPX export writes a Route as
  `<rte>` with `type=Line`, the same as a Line. **[CODE]**

### Notes

- See E4. Typed notes are capped at 512 characters on waypoints, lines, tracks, areas and
  folders, and uncapped on routes. Offline map notes are capped at 255. **[CODE]**
- The help names the Notes field on every kind of markup, with no length given (360052239052,
  4417866009357, Hunt 360028500652). **[DOC]**
- An onX blog post says waypoint notes and photos are available offline (Backcountry blog,
  custom waypoints, modified 2023-01-09). **[DOC]**

### Folders

- **Naming.** Up to 50 characters, trimmed, not blank. The same dialog creates and renames.
  **[CODE]**
- **Folder notes.** Up to 512 characters. **[CODE]**
- **Deleting a folder** doesn't delete its markups (360052239052; Fish 22091202509197). **[DOC]**
- **Membership.** A markup can be in several folders (360052239052). Folder export writes a GPX
  (360052239052). **[DOC]**
- **Sharing a folder** needs Premium or Elite, and anyone with an onX account can be invited to
  contribute (Backcountry collaborative folders page, modified 2025-08-18). **[DOC]**
- **Import folders.** On import, the only folder option is the new-folder checkbox, which makes
  `Import mm/dd/yy H:MM` (unchanged since 2026-10-22, `50657.87e3701dffd2f41a9e91.js`).
  **[CODE]** The Import Complete card's **Add to** menu adds the imported markups to an existing
  folder afterwards (above).

### Colours and icons

- **What the help says.**
  - Exports and moves between onX apps don't keep colours, icons or line weights (360057195972,
    4422125175309; Hunt 4422141473037). **[DOC]**
  - Cairn's imports showed GPX `onx:icon`, `onx:color`, `onx:style` and `onx:weight` kept, with
    area fill the one exception (`docs/ONX_TESTING.md`). **[OBSERVED]**
- **Filtering.** onX filters waypoints by icon and by colour, and searches markups by name only
  (360052239052; Hunt 360028500652). **[DOC]** This matches `docs/FAQ.md`.

### Photos

- Photos go on waypoints only (360052239052). **[DOC]** The web app takes PNG or JPEG photos of up
  to 20 MB each (`7098.181abb35fec750425c21.js`, "Maximum file size 20 MB"). **[CODE]**
- Exports don't include photos (Hunt import blog; onX's own export dialog warning, seen in
  `docs/ONX_ROUND_TRIP.md`). **[DOC]**, **[OBSERVED]**

### Sharing

- A share sends up to 100 markups, by selection or by folder. Recipients need an account and get
  view-only copies that keep syncing. A folder can be shared as View-only or Contribute. Opening
  your own share link gives an error (360052209311, updated 2026-10-19; Hunt 115003218311).
  **[DOC]**
- Nearby Sharing is phone-only, and both phones must run the same system (360052209311). **[DOC]**

### Phone apps versus a computer

- onX says its web app "includes all the same features as the App" (360052239912, updated
  2026-10-08). **[DOC]** For markups, the help lists these exceptions:
  - KML import and export only on a computer;
  - phone import one GPX file at a time;
  - phone export on iOS only (Backcountry);
  - Free Draw for areas on a computer.

  Sources: 360057195972 and 4417866009357. **[DOC]**
- **Phone-to-phone export and import.** onX Hunt's import blog (modified 2025-07-21) says colour,
  line style and notes are kept only when you export and import in the phone app. **[DOC]** That
  bears on the open question of whether the iOS app's GPX export carries onX's extensions
  (`docs/research/KML_GPX_INPUT_2026-10-22.md`, open question P4). It is a Hunt blog claim, not
  tested. **[UNVERIFIED]**
- **Devices.** Up to two phones or tablets per account; computers are unlimited (360061056532,
  updated 2026-09-18). **[DOC]**
- **The phone apps' editors are not public code.** Whether they use the same 255 / 512 caps is
  **[UNVERIFIED]**.

### Account limits

- **The cap is per app.**
  - 3,000 markups per account (360052239052, updated 2026-09-16). **[DOC]**
  - onX Hunt's map tools article says 3,000 "per App", naming Hunt, Offroad, Backcountry and Fish
    (Hunt 360035554652, updated 2026-08-10). Fish says 3,000 per account (22091080062733).
    **[DOC]**
- **What happens over the limit is undocumented.** The Backcountry article's link to what to do
  at the limit (360034625932) is dead: the API returns `RecordNotFound`. **[DOC]**
- **A marketing page disagrees.** onX Offroad's waypoints page (modified 2026-07-10) advertises
  "unlimited custom Waypoints", which conflicts with the help centre's 3,000. **[DOC]**

### onX Hunt, Fish and Offroad

- **Separate stores.** Markups don't sync between onX apps; each app stores its own and needs its
  own membership (4422125175309, 16141286280717). **[DOC]**
- **Same import rules.** Hunt's and Fish's help give the same import rules: GPX or KML, 4 MB and
  3,000 markups. Fish's help and Hunt's import blog also describe the new-folder checkbox on a
  computer. **[DOC]**
- **No Offroad help centre was found.** `onxoffroad.zendesk.com` returns 404. The Hunt help
  centre at `support.onxmaps.com` carries the articles that name Offroad, such as 4422141473037.
- **Hunt's web app was not read.** Its limits may differ from Backcountry's. **[UNVERIFIED]**

---

## What this means for Cairn

Only differences from what Cairn's docs, FAQ, code or `docs/design/DECISIONS.md` assume.

1. **Folder names: onX takes 50 characters, Cairn allows 100.**
   - Cairn: `web/app.js:1846` (`FOLDER_NAME_MAX = 100`), DECISIONS.md lines 987-988 and 1030,
     `docs/FAQ.md:145` ("Names are up to 100 characters"), and `docs/design/LABELS.md:219`.
   - `instructions.txt` (`web/bridge.py:1255`) and `docs/FAQ.md:155` tell the user to rename the
     import folder to Cairn's name. A name of 51 to 100 characters stops at 50 when typed or
     pasted into onX's Rename Folder dialog, and no message appears.
   - Choices for the owner:
     - cap Cairn at 50;
     - keep 100 and mark names over 50;
     - leave it.
   - Folder names that come in from a file, not typed, may also exceed 50.
2. **"Notes typed in onX can be much longer" holds only for Routes.**
   - The claim is in `web/bridge.py:63` and `docs/ONX_TESTING.md:41` ("Notes typed in onX can be
     longer"). In onX's web app, waypoint, line, track and area notes stop at 512 characters;
     only the Route Builder's notes are uncapped.
   - `tests/fixtures/onx_real/README.md:28-31` calls the long-note item a "line". In onX it is a
     Route, which onX's export labels `type=Line`. Cairn reads it as a line sub-kind and writes
     it as a Track.
   - The unexplained drop of that note has two candidate causes (E4). Neither changes Cairn's
     512-byte rule.
3. **onX's own typed notes can exceed its import cut.** A 512-character note typed in onX with
   accents or emoji can be up to about 1.5 KB. Exporting it and importing it again cuts it.
   Cairn's byte-based flag already catches this. No code change; the FAQ's round-trip bullet
   ("Long notes are cut") already covers it in effect.
4. **Long item names: a typed limit now exists, but there's still no known import limit.**
   - `docs/plans/BULK_RENAME.md:104` says "No onX limit is known". Now it is known for typing
     (255, and 100 for routes) but still not for import.
   - UI-26's rule (no warning without a known consequence) still argues for no flag until the
     owner's probe shows what onX does with a 256- or 300-character imported name.
   - Probe pairs that would separate bytes from characters: 255 / 256 ASCII, plus a 128-character
     accented name (256 bytes).
5. **onX refuses a blank name when typed.** UI-39 and BULK_RENAME make Cairn's names optional and
   export an empty `<name>`.
   - onX on a computer can't create a blank-named markup, so an imported one would be a state
     onX's own UI never makes.
   - **[INFER]** Editing such a markup in onX would demand a name before Save would work.
   - What import does with an empty `<name>` is still the open owner-run probe (DECISIONS.md:1272).
6. **There is a post-import "Add to folder".**
   - `docs/ONX_ROUND_TRIP.md:41-46` (finding 2) and `:192` say the only way into an existing folder
     is the folder's Add Content, and that the Import Complete card's second button is
     unidentified.
   - That button is a menu with **Add to (folder)**, **Share** and **Delete** for everything just
     imported (`36154.050f924b55b573a1a96d.js`). **[CODE]**, not exercised.
   - Cairn's instructions (tick the new-folder box, then rename) stay valid. For a round trip back
     into an existing onX folder this is a shorter path, worth one live check before the FAQ
     mentions it.
7. **The phone imports one GPX file at a time** (360057195972). `docs/FAQ.md:200` ("Support
   phone-only importing") could say that a folder of up to three files (plus split parts) is
   then one import per file.
8. **onX's help contradicts ENG-05.**
   - The help says Lines and Areas exported as GPX "will be converted into Tracks" (360057195972,
     4446611009165, 10567936738829).
   - Cairn depends on a GPX `<rte>` with `<type>Area</type>` importing as an Area
     (DECISIONS.md ENG-05, `docs/FAQ.md` "Why are areas in a GPX file, not KML?"). That was
     observed on 2026-10-22 and -23.
   - The help is stale, not evidence, but onX doesn't promise the behaviour Cairn uses. Re-run
     the area probe before any release that leans on it.
9. **onX strips HTML from text typed in its editors (DOMPurify), and trims it.**
   - Cairn passes tag-like text through (ENG-06, ENG-09), and the first round's name probe showed onX's import keeps it.
   - **[INFER]** A name or note like `Camp <Lake>` survives the import but loses `<Lake>` the
     next time the user edits and saves that markup in onX on a computer.
   - The trimming matches Cairn's section 7.1 rule. No change suggested; noted for the FAQ's
     "Do my notes come across?" if it ever comes up.

No difference found for:
- the 4 MB file cap (Cairn splits at 3.75 MiB, 3,932,160 bytes; onX's browser check allows
  4,096,000);
- the 3,000-markup account and per-file limits (`web/bridge.py:57`, `docs/FAQ.md`);
- the per-import `Import mm/dd/yy H:MM` folder;
- folder notes at 512 (`docs/ONX_ROUND_TRIP.md:195`);
- sharing needing an onX account (`docs/research/ONX_REIMPORT_AND_SHARING_2026-10-22.md`).

---

## URLs read (all on 2026-10-25)

**onX Backcountry help centre** (`onxbackcountry.zendesk.com`, through the Help Center API).
All 77 en-us articles were fetched and searched (`/api/v2/help_center/en-us/articles.json`), and
the API search was run for "characters", "name", "notes", "limit", "length" and "truncated".
Read in full: `https://onxbackcountry.zendesk.com/hc/en-us/articles/<id>` for these ids:

- 360057195972 importing and exporting markups (2026-04-01)
- 360052239052 editing and organizing markups (2026-09-16)
- 5013855682445 managing saved markups (2026-09-15)
- 5022588722317 import errors (2026-07-20)
- 4446611009165 moving from CalTopo (2026-07-14)
- 10567936738829 moving from Gaia GPS (2026-07-14)
- 4472785894285 moving from AllTrails (2026-07-14)
- 360052209311 sharing markups (2026-10-19)
- 4422125175309 markups across onX apps (2026-07-14)
- 360052607232 missing markups (2026-07-20)
- 4417866009357 marking and measuring (2026-07-21)
- 360052210091 map tools (2026-05-21)
- 360051747892 routes and recording tracks (2026-10-07)
- 6655129695373 trimming a track (2024-08-22)
- 360052239912 the basics (2026-10-08)
- 16141286280717 the four onX apps compared (2026-10-20)
- 4402358311053 app performance (2026-07-20)
- 360061056532 phones and tablets (2026-09-18)
- 22965175493133 building routes (2026-09-09)
- 16137890897165 printing maps (2026-04-01)
- 360034625932: linked from 360052239052, returns `RecordNotFound`

**onX Hunt help centre** (`support.onxmaps.com`, through the API): all 118 en-us articles fetched
and searched. Read in full: `https://support.onxmaps.com/hc/en-us/articles/<id>` for these ids:

- 115002196452 import and export (2026-09-02)
- 4990049964045 markup options (2024-08-22)
- 360028807671 import errors (2026-07-21)
- 360028500652 editing and organizing (2026-08-04)
- 360035554652 map tools (2026-08-10)
- 4422141473037 markups across onX apps (2026-07-21)
- 115003218311 sharing (2026-08-04)

**onX Fish help centre** (`onxfish.zendesk.com`, through the API): all 47 en-us articles fetched
and searched. Read in full: `https://onxfish.zendesk.com/hc/en-us/articles/<id>` for these ids:

- 25357459498509 import and export (2025-05-21)
- 22091080062733 marking and measuring (2025-05-28)
- 22091202509197 editing and organizing (2025-05-21)

**onX product and blog pages:**

- https://www.onxmaps.com/hunt/blog/back-up-your-data-using-web-map-export-and-import-function (modified 2025-07-21)
- https://www.onxmaps.com/backcountry/blog/how-to-create-custom-waypoints (modified 2023-01-09)
- https://www.onxmaps.com/backcountry/app/collaborative-folders (modified 2025-08-18)
- https://www.onxmaps.com/hunt/blog/you-asked-us-how-do-i-organize-my-content-in-the-hunt-app (modified 2025-07-21)
- https://www.onxmaps.com/offroad/app/features/waypoints (modified 2026-07-10)

Also fetched, with nothing on markup limits:

- https://www.onxmaps.com/hunt/learn/capabilities/waypoints
- https://www.onxmaps.com/hunt/tutorials/introduction-to-map-tools
- https://www.onxmaps.com/backcountry/app/features
- https://www.onxmaps.com/hunt/app/features/waypoints

**onX's web-app code**, from `https://backcountry.onxmaps.com/`:

- The entry page, `runtime.0870c5a50beedb21608c.js`, and all 805 script files it and the page
  list.
- The previous runtime, `runtime.a789a7595c5c72acd102.js` (still served), for the comparison with
  2026-10-22.
- The chunks cited above:
  - `51366.8e385a444bcd59ff149c.js` (waypoint card)
  - `51814.dd2da6a67a31d60aded8.js` (line and track card)
  - `80937.9ee849fc5e818fd88f89.js` (area card)
  - `75079.4bf3b7ca66c4c6f116ad.js` (route builder)
  - `19882.612a0ca0261e4086da67.js` (folder name dialog)
  - `7272.8a087709ef027488187c.js` (folder card)
  - `57235.85d49fc066345d0b91d1.js` (text input)
  - `40138.f5160d24f7701fea5612.js` (sanitizer module `LJH7`)
  - `93023.c712564fe21c8e5d3795.js` (markup classes, name check, DOMPurify 3.4.14)
  - `98770.bf04e6cb10482fd61f4c.js` (import card)
  - `36154.050f924b55b573a1a96d.js` (Import Complete card)
  - `50657.87e3701dffd2f41a9e91.js` (importer)
  - `33209.792d376b438ff1099263.js` (export builder)
  - `90456.4316f555cb92e750b8f6.js` and `8066.150b87840150a3d5c070.js` (offline map name and notes)
  - `7098.181abb35fec750425c21.js` (photo upload)
- Source maps are referenced but weren't fetched.

## URLs blocked

None. No page was behind a login or a CAPTCHA, and no request was refused.

Not attempted:
- the help centres' HTML pages, which sat behind Cloudflare on 2026-10-22; the API was used
  instead;
- reddit;
- the phone apps.

These hosts are not blocks: they simply have no such help centre.
- `onxhunt.zendesk.com` and `onxoffroad.zendesk.com` return 404.
- `onxmaps.zendesk.com` lists 0 en-us articles.
