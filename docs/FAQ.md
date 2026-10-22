# Cairn FAQ

## The problem

### Why can't I just import my CalTopo map into onX?

onX Backcountry imports only GPX and KML. It doesn't take GeoJSON (per project docs, Aug 2026). GeoJSON is also the only CalTopo export that keeps your styling. CalTopo calls it "a full back-up for CalTopo including line and marker styles, and folder organization." CalTopo's GPX and KML exports drop the styles and the folders. With GPX you also have to choose Track or Route for each line when you export. So the one file that has everything is the one file onX won't open.

### Does this work with onX Hunt, Fish, Offroad or other onX apps?

Only **onX Backcountry** is supported for now. onX makes several apps (Hunt, Fish, Offroad and
others) that may share the same import, but Cairn has only been built and checked against
Backcountry's icons, colors and import behavior. Use it with the others at your own risk.

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
