# Cairn FAQ

## The problem

### Why can't I just import my CalTopo map into onX?

onX Backcountry imports only GPX and KML. It doesn't take GeoJSON (per project docs, Aug 2026). GeoJSON is also the only CalTopo export that keeps your styling. CalTopo calls it "a full back-up for CalTopo including line and marker styles, and folder organization." CalTopo's GPX and KML exports drop the styles and the folders. With GPX you also have to choose Track or Route for each line when you export. So the one file that has everything is the one file onX won't open.

### What gets lost if I move CalTopo GPX or KML into onX myself?

CalTopo's own export page says its GPX and KML exports lose line and marker styles and folder organization. The CalTopo GPX in the project's test data carries only waypoint names and coordinates: no icons, colors, descriptions or folders.

This matters more than it sounds. Per project docs (Aug 2026), the onX Web Map filters markups by icon and color, the phone app filters by icon only, and search covers names only, not notes. If 300 waypoints arrive without their icons and colors, you can't filter them or tell them apart at a glance, and you end up fixing them one at a time. (What onX shows for a GPX waypoint that has no onX icon hasn't been tested. It's an open probe in the project docs.)

## What Cairn does

### What does Cairn actually do?

It runs in your browser and takes a CalTopo GeoJSON export. It sorts every feature it recognizes into waypoints (Marker points), lines (Line or Shape linestrings) and areas (Shape polygons). Any other kind of feature is skipped without a message and isn't counted. It picks an onX icon and color for each item. You can review and edit the results, including bulk edits. Then it downloads one zip, `onx_ready.zip`, with files ready for onX:

- One numbered directory per CalTopo folder (`01_Name/`, `02_Name/`, …). `Name` is the folder name with punctuation removed and spaces turned into underscores.
- In each directory, up to three kinds of file: `Name_Waypoints.gpx`, `Name_Tracks.gpx` and `Name_Areas.kml`. A large GPX may be split into numbered parts (see below).
- A `RUNBOOK.md` at the top that walks you through the imports.

Waypoints become GPX `<wpt>` with onX's own `<onx:icon>` and `<onx:color>` extensions. Lines become GPX `<trk>` with `<onx:color>`, `<onx:style>` and `<onx:weight>`. Polygons become KML Polygon placemarks.

### How does Cairn pick an onX icon?

It checks in this order for each waypoint and stops at the first hit:

1. **Your CalTopo symbol, exact match.** For example, `cabin` maps to `Shelter`.
2. **Your CalTopo symbol, partial match.** The longest mapping key found inside the symbol name wins.
3. **Keywords in the name and description.** Single-word keywords such as "hut", "camp" or "spring" must match a whole word. Keywords that contain a space, such as "trail head", match anywhere in the text. Each matching keyword scores a point. The highest score wins, and a tie goes to whichever icon comes first in the mapping list. The folder name is never scanned. A known gap: digits stuck to a word stop it matching, so "Camp 2" matches `camp` but "Camp2" doesn't.
4. **The default pin, `Location`.**

Generic CalTopo symbols (`point`, `marker`, `pin`, `dot`, `circle`) carry no meaning, so Cairn skips steps 1 and 2 for them and goes straight to keywords. A waypoint called "Elk Hut" with a plain `point` symbol still ends up as `Shelter`. A symbol that matches always beats the keywords.

The shipped tables, as the web app loads them, have 152 symbol mappings and keyword lists for 30 icons. Cairn's list of valid onX icons has 95 names, not the "~40" the README mentions. Only waypoints get icons. Tracks and areas don't take an icon in onX.

### What's the "Default pin" / "needs attention" thing?

Any waypoint that ends up as `Location` is marked "Default pin" so you can spot it and choose a real icon. Choosing any icon clears the flag, including choosing `Location` on purpose. One quirk: a symbol that is deliberately mapped to `Location` (such as `flag-1`) also gets flagged, but its explanation reads "Your CalTopo symbol maps to this icon."

Two things here are unverified:
- That `Location` shows up in onX as onX's default pin is Cairn's assumption.
- What onX does with an icon name it doesn't recognize isn't settled by any onX source the project cites. The README's "the default will be used" comes from the owner's own observation, and the project's decision-surface doc says the same thing without citing a test.

There was a real bug of this kind. Cabins, huts and yurts used to map to `Cabin`, which isn't a valid onX icon. As of 2026-10-22 they map to `Shelter`.

### How are colors matched?

onX has a fixed palette, per project docs (Aug 2026): 10 colors for waypoints and 11 for lines. The extra line color is Fuchsia. CalTopo allows any color, so Cairn snaps each waypoint and line color to the nearest onX color by straight RGB distance. That means close shades merge into one color. Fuchsia on a waypoint becomes Purple.

Some edge cases:

- **Waypoint with no color:** Cairn writes the icon's usual color, for example Brown for `Shelter`. It uses Blue only when the icon has no usual color. This is not "onX's default blue", as the README says, because Cairn always writes an explicit color. The on-screen preview still shows such a waypoint as blue while the export uses the icon's color. If it matters to you, set the color yourself.
- **Line with no color, or a color Cairn can't read:** it gets Blue. Short hex like `#abc` is treated as unreadable.
- **Areas are not snapped to the palette.** The KML gets the raw CalTopo hex, or white if the color is missing or isn't 6 hex characters (an `rgb()`/`rgba()` value also becomes white). Line width is fixed at 2. The fill is the line color at 50% transparency, and CalTopo's separate fill color isn't read. The swatch on screen shows the nearest palette color, so an area you haven't edited can export in a slightly different color than it previews. If you set an area's color, the preview and the export agree.
- **Line style:** the CalTopo pattern becomes `solid`, `dash` or `dot`. Width collapses to two weights, 4.0 or 6.0 (6.0 when the CalTopo width is over 4).

### Can I bulk-edit before export?

Yes. Select rows and set a color for all of them at once. A bulk icon applies to the selected waypoints, since lines and areas have no icon. The "More" menu can also exclude or re-include the selection, and can rename each selected item to its own note ("use note as name"). Excluded items are left out of the export, and your source file is never changed. You can edit names and notes one item at a time. Bulk rename with prefix/suffix or find/replace, and bulk note editing, aren't built yet.

The reason for doing this before import is the owner's own experience: "Making bulk updates in onX is either not possible or very difficult." None of the onX help articles the project cites covers bulk editing, so treat that as unverified.

### Do my notes come across?

Yes. Each waypoint's or line's notes go into the GPX `<desc>`. HTML is stripped, and an empty note means no `<desc>` at all. Area notes go into the KML `<description>`. Multi-line notes are kept: `<br>`, paragraphs, `<div>`s and list items become real line breaks.

Two things are unverified:
- That onX shows `<desc>` as the markup's Notes. This is only the owner's observation.
- **Whether onX keeps those line breaks is unknown.** It's an open item in the project's to-do list, and nobody has run that test import yet. Whether onX reads KML descriptions on areas is also unverified.

### How do folders work? Why is there a runbook?

Per project docs (Aug 2026), from reading onX's Web Map code: when you tick "Import map data to a new folder", each import batch (one click of Import, any number of GPX and KML files) creates exactly one new folder named like `Import mm/dd/yy H:MM`. If you leave the box unticked, no folder is created. Filenames and GPX metadata don't change that name. onX folders are flat, with no nesting. Whether onX's server builds folders from KML `<Folder>` elements hasn't been tested. The docs rate "it doesn't" as a high-confidence inference.

So Cairn gives you one numbered import per CalTopo folder, and `RUNBOOK.md` tells you for each step:

1. Open the onX Web Map on a computer and go to My Content → Import.
2. Drag in all the files in that folder's directory at once.
3. Tick "Import map data to a new folder" and click Import. This is the step that creates the folder.
4. Rename the new folder to your CalTopo folder's name.

Some details:
- Steps are ordered by folder size, largest first.
- Items that weren't in any CalTopo folder get their own folder called "Unorganized" (that label may still change).
- If your map has no folders at all, everything goes into one folder named after your file.
- The runbook ends with the totals you should see. If a folder comes up short, delete it in onX and redo just that step.

### Why are there several files per folder? Will big files be split?

There are up to three kinds of file per folder, one each for waypoints, tracks and areas. They all go into the same import, so they should land in one onX folder. That comes from onX's Web Map code (per project docs, Aug 2026). A real two-file import that would confirm it hasn't been run yet.

onX's limit is under 4 MB per file (per project docs, Aug 2026). Cairn splits any waypoint or track GPX over 3.75 MiB into `_1.gpx`, `_2.gpx` and so on, without ever cutting an item in half. If a single item is bigger than the cap, it's written on its own anyway, and the app doesn't warn you. **KML area files are never split**, so a huge areas file could go over the limit.

### Why do my CalTopo lines show up as onX Tracks, not Lines?

In onX the file format decides the object type, per project docs (Aug 2026):

| In the file | In onX |
|---|---|
| GPX `<wpt>` | Waypoint |
| GPX `<trk>` | Track |
| KML LineString | Line |
| KML Polygon | Area |

Cairn writes every CalTopo line, including a CalTopo Shape drawn as an open line, as a GPX `<trk>`. That's the only path where Cairn writes onX color, style and weight. So all your lines arrive as **Tracks**, and Cairn never creates onX "Lines". Only closed polygons go to KML and become Areas. Polygon holes (inner rings) are dropped, and an area's CalTopo line width and pattern aren't carried over.

## Limits and trade-offs

### What can't Cairn do?

- **Recreate your folders automatically.** You rename each one in onX after import, as described above. Nesting isn't lost: per project docs, CalTopo and onX folders are both flat.
- **Keep exact colors.** Waypoint and track colors snap to onX's palette, and line widths collapse to two weights.
- **Keep every character in names.** Waypoint and track names lose `! @ # $ % ^ * &`, so `#01 Porcupine` becomes `01 Porcupine`, and the app doesn't tell you. Area names are left alone.
- **Control order in onX.** Within each file, items are sorted naturally ("Camp 2" before "Camp 10"). How onX orders them after import hasn't been checked against any onX source.
- **Check onX's per-import cap.** onX allows up to 3,000 markups per import (per project docs, Aug 2026), and Cairn doesn't check that.
- **Keep you under the account limit.** onX says your account is "currently limited to 1,500 Markups" (per project docs, Aug 2026). Cairn warns when *this map* is over 1,500, but it can't see what's already in your account. Splitting into more imports doesn't get around an account-wide cap. What onX actually does when you go over isn't in any cited onX source. The runbook's "The import will fail" and the design doc's "kills the import" are the project's own assertions.
- **Support phone-only importing.** The runbook is written for the Web Map. KML import works only on the Web Map (per project docs, Aug 2026), and so does the new-folder checkbox. The phone app can import GPX, then file it with "Add to Folder".
- **Import without a paid plan.** Importing requires onX Premium or Elite (per project docs, Aug 2026).
- **Read anything other than CalTopo GeoJSON.** See the round-trip question below.

## Privacy

### Where does my map data go?

It stays in your browser. Cairn runs entirely client-side: the conversion is Python running in the page through Pyodide. Your file is read in the page, the zip is built in the browser and downloaded from there, and no code path uploads your map.

The page loads only a few things:
- Its own files: the page, its scripts, the Python bridge, the Cairn engine package, its config and its fonts.
- The Pyodide runtime and its `micropip` and `pyyaml` packages, from one pinned folder on `cdn.jsdelivr.net`.

The site's Content Security Policy only lets the page's scripts load code from, or connect to, its own origin and that one jsdelivr folder. The host (Vercel, possibly behind a Cloudflare proxy that passes the same security headers through) and jsdelivr see ordinary request metadata, such as your IP and that you loaded the page, but never your file. Whether hosting-level analytics are turned on can't be determined from the code.

## The onX round trip

### Can I export from onX, clean it up in Cairn, and import it back?

Not today. Here's what's known and what isn't.

**In the web app: no.** It only accepts CalTopo `.json`/`.geojson` files, and there's no onX → Cairn direction.

**In the engine underneath: partly.** Cairn has readers for onX GPX and KML. A test run went onX files → CalTopo GeoJSON → back through Cairn, and the waypoints, tracks and area survived. The gaps:
- **No real onX export file has ever been tested.** The test files are synthetic. They match onX's extension tags but not its description format or its flat KML layout, per project docs (Aug 2026).
- **Areas break in GPX.** onX's GPX export writes areas as `<rte>` with `type=Area` (per project docs, Aug 2026), and Cairn's reader turns every `<rte>` into a track.
- **Folders aren't recovered.** onX export files carry no folder information (per project docs, Aug 2026). Cairn's readers put everything into fixed "Waypoints", "Tracks" and "Areas" folders, so you'd be renaming folders by hand again. The project docs note that onX can export one folder at a time, which could carry folder names through filenames, but Cairn doesn't support that.
- **Reading XML would reopen a security decision.** The project chose stock XML parsing because XML isn't reachable from the browser. Making it reachable is the stated trigger for revisiting that.

**Re-importing: unknown.** Nobody knows whether re-importing updates your existing markups or creates duplicates. The project owner is "skeptical" that in-place updates are possible. Per project docs (Aug 2026), onX's own help suggests exporting and re-importing to manage the 1,500 limit, but that doesn't settle whether a re-import matches existing markups. Cairn's exports don't include onX's IDs, so there would be nothing to match on, if onX matches by ID at all. If re-import does duplicate, you'd need to delete the originals first, or the copies count against the 1,500-markup limit.

So this round trip is a real possible use case that hasn't been built.

## Sources (internal, remove before publishing)

- **Why can't I just import:** docs/PLATFORM_CONSTRAINTS_2026-08-29.md "What onX can import" and "What CalTopo can export"; docs/FIDELITY_MODEL_2026-08-29.md:36-38 (Zendesk 4446611009165, "GeoJSON format isn't supported"), :45 (Web Map `accept=".gpx,.kml"`), per project docs, Aug 2026; README.md:139 and ref [7].
- **What gets lost:** PLATFORM_CONSTRAINTS "What CalTopo can export"; FIDELITY_MODEL:103 (CalTopo GPX names and coordinates only); tests/fixtures/bitterroots/bitterroots_subet.gpx (only `wpt`/`name`/`metadata` elements); FIDELITY_MODEL:28-29, :139 (web filters by icon and color, app by icon, search by name only); FIDELITY_MODEL:515-516 (probe B3: foreign-GPX icon display untested), per project docs, Aug 2026.
- **What Cairn does:** cairn/core/parser.py:65-78, 106-116 (only Marker/Point, Line|Shape/LineString, Shape/Polygon are stored); web/README.md:36; web/bridge.py:69-71 (`_safe`), 288-340 (export_zip, dirs, file names); web/app.js:996 (onx_ready.zip); cairn/core/writers.py:480-490 (wpt), 700-713 (trk), 1083-1164 (KML Polygon).
- **Icon matching:** cairn/core/icon_resolver.py:85-116 (symbol steps gated by the generic check at :88), 118-174 (keyword scoring; phrase substring at :134-138, token match at :140-143; ties at :168-171), 177-182 (default); cairn/core/config.py:21-29 (GENERIC_SYMBOLS), 33+ (95 names); load_config(web/cairn_config.yaml) run gives 152 symbols / 30 keyword icons; web/bridge.py:117-122, 143-146; TODO.md:25-27 (Camp2 gap).
- **Default pin / needs attention:** web/bridge.py:78-104 (_explain), 176-179, 224-238; web/app.js:187, 364, 504-518; web/cairn_config.yaml (flag-1: Location); TODO.md:24 (Cabin fix 2026-10-22); README.md:105 (owner's default-pin claim); docs/DECISION_SURFACE_2026-08-29.md:88-113.
- **Colors:** cairn/core/color_mapper.py (pattern_to_style, stroke_width_to_weight, palettes, squared-RGB nearest, parse_color fallback to Blue); writers.py:430-440 (waypoint icon-color fallback), 658-662 (track stroke or Blue), 1127-1137 (KML raw hex, width 2, '7f' fill); cairn/core/mapper.py map_color (white if missing or not 6 characters); cairn/core/parser.py:38-50 (no `fill` read); config.py ICON_COLOR_MAP (Shelter → Brown), default_color Blue (config.py:509); web/bridge.py:153-157 (preview colors), 276-282 (color_edited); onX palette per project docs, Aug 2026 (FIDELITY_MODEL:139, :149).
- **Bulk edits:** README.md walkthrough steps 4-5; web/app.js:504-518 (edit), 781-795 (applyBulk; icon only on waypoints at :790), 979-981 (use note as name, exclude, include); web/bridge.py:208-240, 297-307; docs/UX_AUDIT_2026-08-29.md §4.3 (owner quote); TODO.md:85-86 and docs/design/DECISIONS.md UI-17 (bulk rename/notes not built).
- **Notes:** cairn/core/writers.py:77-93 (_desc_text), 484-485, 708-709, 1119-1121; cairn/utils/utils.py:88-139 (strip_html); cairn/core/parser.py:37; web/bridge.py:163-164, 221, 258; TODO.md:52-59 (line-break probe unrun); FIDELITY_MODEL:93-95, :138 ([OWNER] desc→Notes); docs/design/DECISIONS.md F12.
- **Folders / runbook:** FIDELITY_MODEL:44-71 ([CODE]: checkbox-gated addCollection, Import mm/dd/yy H:MM, one folder per batch, flat; KML `<Folder>` [INFER]), :510-511 (probe B1), per project docs, Aug 2026; PLATFORM_CONSTRAINTS "How folders actually work" / "CORRECTED 2026-08-29"; web/bridge.py:107-115, 130-132, 186, 347-404; cairn/core/parser.py:19, 218-255.
- **File splitting:** cairn/core/writers.py:73-74, 247-341 (split, oversized single item logged only); KML has no size check (writers.py:1083-1164); FIDELITY_MODEL:55-57 and :517-518 (one batch = one folder; probe B4 unrun); onX 4 MB per project docs, Aug 2026 (PLATFORM_CONSTRAINTS; FIDELITY_MODEL Appendix A `size>4096e3`).
- **Tracks vs Lines:** PLATFORM_CONSTRAINTS "The rule that decides object type" (Zendesk 4446611009165), per project docs, Aug 2026; cairn/core/parser.py:72-80, 106-116; web/bridge.py:305-323; writers.py:1139-1158 (outer ring only).
- **What Cairn can't do:** cairn/utils/utils.py:146-190 and writers.py:171-201, 654 (name sanitizing); utils.py:17-56 and writers.py:367, 620, web/bridge.py:320 (natural sort); grep showing no 3,000 check in web/ or the writers; web/bridge.py:376-383 and web/app.js:844 (1,500 warnings); FIDELITY_MODEL:26-29, 36-38 (flat folders, 1,500, 3,000, Premium/Elite, KML Web-Map-only), :124, :147 (CalTopo folders flat), :391-392 (the project's uncited "kills the import"); PLATFORM_CONSTRAINTS "How folders actually work" (mobile "Add to Folder"), per project docs, Aug 2026.
- **Privacy:** web/index.html:43, 203-207; web/app.js:48-72, 133, 996; web/styles.css:1-20; web/fonts/; web/vercel.json (CSP); web/cloudflare-worker/proxy.js (copies upstream headers; analytics undetermined).
- **Round trip:** web/index.html:43; web/bridge.py:17-28 (only parse_geojson); web/README.md:96-100; cairn/io/onx_gpx.py:32-41, 157-160, 352-369; cairn/io/onx_kml.py:110-113; cairn/core/merge.py:17-36; cairn/io/caltopo_geojson.py:213-240; round trip reproduced 2026-10-22 on tests/fixtures/onx_export_with_tracks.{gpx,kml} (2 waypoints, 2 tracks, 1 shape, in folders Waypoints/Tracks/Areas); FIDELITY_MODEL:83-96, 104-111, 355-366 (onX dialect, no folder identity, per-folder export, synthetic fixtures), :88-89 (onX suggests export-then-reimport), per project docs, Aug 2026; TODO.md:65-67 ("Skeptical this is possible"); writers.py:77-93 (no IDs written by default); AGENTS.md "XML parsing uses stock xml.etree.ElementTree" (defusedxml revisit condition; outside the priority source list).

## Fact-check notes

**Changed claims about onX:**

1. **"Each import batch creates exactly one new folder."** The cited code (FIDELITY_MODEL:46) creates the folder only `if (newFolderCheckbox)`. I made it conditional on the box being ticked and said so in runbook step 3.
2. **"onX reorders things after import (per project docs)."** This is only in AGENTS.md:127. AGENTS.md points to a README "Known quirks" section that no longer exists (checked the README headings), and AGENTS.md isn't on the source list. I removed the claim and said onX's ordering is unchecked.
3. **"The indirect evidence points to duplicates."** Nothing in the code or docs supports it. Removed. I added the citable FIDELITY_MODEL:88-89 point that onX suggests export-then-reimport, and said it doesn't settle the question. "onX would have nothing to match against" became a conditional.
4. **"Work in the phone app alone."** This bullet mixed two facts. PLATFORM_CONSTRAINTS says the mobile app can import (then "Add to Folder"); only KML and the new-folder checkbox are Web-Map-only. Premium/Elite is a separate requirement. Split into two bullets.
5. **"Nest folders" listed as a limitation.** FIDELITY_MODEL:124 and :147 say CalTopo folders are flat too, so nothing is lost. Folded into the folders bullet as a non-issue.
6. **"onX can't take folder names from a file."** The timestamp name is [CODE]. Whether the server builds folders from KML `<Folder>` is [INFER, high confidence], and probe B1 hasn't run. Added that caveat.
7. **"They all go into the same import, so they still land in one onX folder."** This comes from reading client code. Server-side confirmation (probe B4) hasn't run. Softened to "should" and gave the evidence tier.
8. **Over-limit behavior source.** The draft cited "Appendix B / §3 rows G, H". Those rows are about KML `<Folder>` and GPX `<sym>`, not limits. Re-cited to FIDELITY_MODEL:391-392 (R2's uncited "kills the import") and said it's the project's own assertion.
9. **"300 waypoints arrive as the same blue pin."** How onX shows a GPX waypoint with no onX icon is untested (probe B3). Reworded to "without their icons and colors".
10. **"Round trip: test files don't match the dialect onX writes."** FIDELITY_MODEL:104 says the GPX extension usage is faithful. Narrowed to the description format and the KML `<Folder>` layout.
11. **"Folders can't be recovered."** Kept the substance and added the code evidence: readers use the fixed Waypoints/Tracks/Areas folders at onx_gpx.py:157-160. Added FIDELITY_MODEL:358's note that onX can export one folder at a time, which Cairn doesn't use.
12. **"Reading XML would need a security review."** AGENTS.md says to revisit the defusedxml decision if XML becomes reachable from the web bridge. Reworded to match that, and noted AGENTS.md is outside the priority list.

**Changed claims about Cairn's code:**

13. **Generic symbols "skip step 1".** icon_resolver.py:88 gates both the exact and the partial symbol match. Corrected to steps 1 and 2.
14. **Keywords "score whole-word matches".** Only single-word keywords are token-matched. Keywords with a space are substring-matched (icon_resolver.py:134-138). Added that, plus the Camp2 gap from TODO.md:25-27.
15. **"Sorts everything into waypoints, lines and areas."** parser.py stores only three class/geometry pairs. Other features are dropped without a message (web/README.md:36). Reworded.
16. **"Up to three files."** Splitting can produce more. Changed to "three kinds of file" and said the `Name` part is sanitized (bridge.py:69-71).
17. **Bulk edit.** A bulk icon applies only to waypoints (app.js:790). A bulk rename "use note as name" does exist (app.js:979; DECISIONS.md UI-17). Bulk exclude/include exists too. The "not built" sentence is narrowed to prefix/suffix/find-replace rename and bulk note edit.
18. **Areas bullet.** Added that the KML fill is the line color at 50% (writers.py:1135-1137) and that CalTopo's fill color isn't read. map_color only checks length, so "not a 6-digit hex" became "isn't 6 hex characters", with `rgb()`/`rgba()` going to white. "The preview may still show" became "still shows"; bridge.py:154 always uses the palette mapper.
19. **Notes.** Added `<div>` to the line-break list (utils.py:113). TODO.md:58-59 says "Cairn writes no KML descriptions today", but writers.py:1119-1121 does write `<description>`. The code wins, so the draft's claim stays and the TODO line is stale.
20. **"Guarantee order."** Became "Control order in onX". The natural sort is per file (writers.py:367, 620; bridge.py:320).

**Privacy:**

21. **Load list.** The page also loads `micropip` from jsdelivr (app.js:50), plus bridge.py and the engine package from its own origin (app.js:63-65). Added these.
22. **"Couldn't send your data elsewhere even if it tried."** CSP limits the page's scripts (connect-src/script-src). It doesn't cover top-level navigation. Narrowed to what the CSP actually limits, and kept "no code path uploads your map": the only `fetch` calls are for bridge.py and cairn_config.yaml (app.js:65, 71). proxy.js copies upstream headers, so the CSP survives the Cloudflare proxy. Whether the proxy is actually deployed in front is still unknown, so "possibly" stays.

**Other:**

23. **Sources section.** Line references were updated to the current files (bridge.py, app.js, writers.py). The palette citation is now FIDELITY_MODEL:139/149 (was :148-152).
24. **Checked and unchanged.** Re-run and confirmed: 152 symbols / 30 keyword icons / 95 icon names; cabin/hut/yurt → Shelter; `Cabin` not valid. Resolver results: "Elk Hut" + `point` → Shelter by keyword; `flag-1` → Location by symbol. Also confirmed: the waypoint icon-color fallback (Shelter → Brown, default Blue), the 3.75 MiB split and `_N` naming, the KML outer ring only, name sanitizing, and no 3,000 check. The round trip was reproduced on the synthetic fixtures (2 waypoints, 2 tracks, 1 shape survived).
25. **Unverified, kept and labeled.** `Location` as onX's default pin; onX's handling of unknown icons; `<desc>` → Notes ([OWNER]); line-break survival; KML descriptions read by onX; behavior over the 1,500 limit; re-import update vs duplicate; hosting analytics.
26. **Not added.** The on-screen 1,500 note (app.js:844) counts only exported items. The runbook (bridge.py:378) uses the larger of exported and expected. This is citable but wasn't in the draft.