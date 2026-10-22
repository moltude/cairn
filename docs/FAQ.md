# Cairn FAQ

## The problem

### Why can't I just import my CalTopo map into onX?

onX Backcountry imports only GPX and KML. It doesn't take GeoJSON (per project docs, Aug 2026). GeoJSON is also CalTopo's most complete export. CalTopo calls it "a full back-up for CalTopo including line and marker styles, and folder organization." CalTopo's KML keeps less than that, and its GPX keeps much less (see the next question). With GPX you also have to choose Track or Route for each line when you export. So the one file that has everything is the one file onX won't open.

### Does this work with onX Hunt, Fish, Offroad or other onX apps?

Only **onX Backcountry** is supported for now. onX makes several apps (Hunt, Fish, Offroad and
others) that may share the same import, but Cairn has only been built and checked against
Backcountry's icons, colors and import behavior. Use it with the others at your own risk.

### What gets lost if I move CalTopo GPX or KML into onX myself?

CalTopo's own export page says its GPX and KML exports lose line and marker styles and folder organization. Real exports of one map in all three formats (the Dark Divide 100 course, October 2026) show the detail:

| | GeoJSON | KML | GPX |
|---|---|---|---|
| Names and notes (multi-line) | yes | yes | yes |
| Folders | yes | yes | no (one folder) |
| Marker icon (CalTopo symbol) | yes | yes | no |
| Marker color | yes | yes, for built-in symbols; not for a custom icon | no |
| Line color | yes | yes | yes, as one of Garmin's 16 color names, and not always |
| Line width | yes | yes | no |
| Line pattern (dashes, arrows) | yes | no | no |
| Areas | yes | yes, with fill | none seen |

Notes are carried in all three: the Dark Divide export has 21 multi-line notes, and each format has every one of them, word for word. (An older project note said CalTopo's GPX has no descriptions; that was a GPX with no notes in it.)

Cairn reads all three and treats them the same way. When you start from the KML or the GPX, the only differences are the gaps in the table. Each difference is listed with its reason in `tests/fixtures/dark_divide_100/PARITY.md`.

This matters more than it sounds. Per project docs (Aug 2026), the onX Web Map filters markups by icon and color, the phone app filters by icon only, and search covers names only, not notes. If 300 waypoints arrive without their icons and colors, you can't filter them or tell them apart at a glance, and you end up fixing them one at a time. (What onX shows for a GPX waypoint that has no onX icon hasn't been tested. It's an open probe in the project docs.)

## What Cairn does

### What does Cairn actually do?

It runs in your browser and takes a CalTopo GeoJSON export. It also opens a CalTopo KML (folders, icons, colors and notes, like the GeoJSON), a CalTopo GPX (names, notes and line colors, with no folders or icons, so it says the GeoJSON or KML would be better), or the GPX and KML you export from onX (see the round-trip question below). You can drop several files at once; each becomes one folder named after the file, and an onX GPX and KML from the same export become one folder together. It sorts every feature it recognizes into waypoints (Marker points), lines (Line or Shape linestrings) and areas (Shape polygons). Any other kind of feature is skipped without a message and isn't counted. It picks an onX icon and color for each item. You can review and edit the results, including bulk edits. Then it downloads one zip, `onx_ready.zip`, with files ready for onX:

- One numbered directory per CalTopo folder (`01_Name/`, `02_Name/`, …). `Name` is the folder name with punctuation removed and spaces turned into underscores.
- In each directory, up to three kinds of file: `Name_Waypoints.gpx`, `Name_Tracks.gpx` and `Name_Areas.gpx`. A large GPX may be split into numbered parts (see below).
- A `RUNBOOK.md` at the top that walks you through the imports.

Waypoints become GPX `<wpt>` with onX's own `<onx:icon>` and `<onx:color>` extensions. Lines become GPX `<trk>` with `<onx:color>`, `<onx:style>` and `<onx:weight>`. Polygons become GPX `<rte>` routes marked `<type>Area</type>` with `<onx:color>` and `<onx:fill_color>`, the way onX's own GPX export writes an area (see "Why are areas in a GPX file, not KML?" below). Every file is GPX, so nothing needs the KML importer.

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
- **Areas snap to the 11-color line palette**, like lines, and export in exactly the color the screen shows (Blue when the CalTopo color is missing or unreadable). The fill is the same color, at CalTopo's fill opacity when the map has one and 50% otherwise; CalTopo's separate fill color isn't read. onX's area import takes the outline and fill color from the GPX (checked in a real import, 2026-10-22). Area line width and dash aren't written: onX's own area export doesn't carry them.
- **Line style:** see "Do dashed and dotted lines come across?" below. Width collapses to two weights, 4.0 or 6.0 (6.0 when the CalTopo width is over 4).
- **From a CalTopo GPX:** a line's color is read from its Garmin color name (`Red`, `Magenta`, `DarkBlue` and so on) and then snapped like any other. A line with no name gets Blue, and a waypoint never has a color in a GPX, so it gets its icon's usual color.

### Do dashed and dotted lines come across?

Only a dashed line, and only from the GeoJSON. Line styles in onX are `solid`, `dash` and `dot`, written as `<onx:style>` on a track. These three values come from the project's reading of onX's Web Map code. No real onX export containing a line has been inspected yet, so none of them is confirmed from a real file. onX's code shows no arrow style.

CalTopo writes a line's style in the GeoJSON `pattern` property:
- `solid` is solid.
- `M0 -1 L0 1,,8,F` is CalTopo's dashed line. It's a short stroke repeated every 8 pixels, written as an SVG path. This value appears in real exports, and Cairn exports it as `dash`.
- CalTopo's dotted and arrow styles exist, but nobody has seen what they write yet, so Cairn exports them as `solid` for now. Once a CalTopo export with each style turns up, mapping them takes one line each. A directional arrow can only become `solid` or `dash`.

CalTopo's KML and GPX don't carry a pattern at all, so every line read from them is solid.

### Can I bulk-edit before export?

Yes. Select rows and set a color for all of them at once. A bulk icon applies to the selected waypoints, since lines and areas have no icon. The "More" menu can also exclude or re-include the selection, and can rename each selected item to its own note ("use note as name"). Excluded items are left out of the export, and your source file is never changed. You can edit names and notes one item at a time. Bulk rename with prefix/suffix or find/replace, and bulk note editing, aren't built yet.

The reason for doing this before import: onX's own bulk tools are limited. In the onX Web Map (checked 2026-10-22), My Content's **Select** mode offers only Add to Folder, Share, Export and Delete for a selection. There is no bulk icon, color or rename, so in onX those changes are one markup at a time.

### Do my notes come across?

Yes. Each waypoint's or line's notes go into the GPX `<desc>`. HTML is stripped, and an empty note means no `<desc>` at all. Area notes go into the area's GPX `<desc>` the same way. Multi-line notes are kept: `<br>`, paragraphs, `<div>`s and list items become real line breaks. This is true whether the map came in as CalTopo GeoJSON, KML or GPX: all three carry the same note text.

Only real HTML tags are removed (CalTopo descriptions can contain HTML), so plain-text angle brackets such as `< 2 mi to camp, > 1 mi to water` or `Bring <2L water>` survive. One caveat: a note that contains something tag-shaped, like `<Lake>`, is still treated as a tag. More than one blank line in a row becomes one.

Two things are unverified:
- That onX shows `<desc>` as the markup's Notes. This is only the owner's observation.
- **Whether onX keeps those line breaks is unknown.** It's an open item in the project's to-do list. In a real import on 2026-10-22, multi-line track notes came through intact, but onX also showed a `<desc>` written as `key=value` lines verbatim as the note, which is why Cairn's `<desc>` holds only your note text.

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

onX's limit is under 4 MB per file (per project docs, Aug 2026). Cairn splits any waypoint or track GPX over 3.75 MiB into `_1.gpx`, `_2.gpx` and so on, without ever cutting an item in half. Area GPX files are split the same way. If a single item is bigger than the cap, it's written on its own anyway, and the app doesn't warn you.

### Why do my CalTopo lines show up as onX Tracks, not Lines?

In onX the file format decides the object type, per project docs (Aug 2026):

| In the file | In onX |
|---|---|
| GPX `<wpt>` | Waypoint |
| GPX `<trk>` | Track |
| GPX `<rte>` with `<type>Area</type>` | Area |
| KML LineString | Line |
| KML Polygon | Area |

Cairn writes every CalTopo line, including a CalTopo Shape drawn as an open line, as a GPX `<trk>`. That's the only path where Cairn writes onX color, style and weight. So all your lines arrive as **Tracks**, and Cairn never creates onX "Lines". Closed polygons go to an Areas GPX as onX Area routes and become Areas, with their color and fill. A multi-part area (MultiPolygon) becomes one onX Area per part, each with the same name, color and notes.

### Why are areas in a GPX file, not KML?

Because onX ignores an area's color in KML. Checked in a real onX Web Map import on 2026-10-22: Cairn's old `Areas.kml` (a KML `<Style>` with line and fill colors, plus onX-style `ExtendedData` color and fill fields) came in with onX's default red outline and light blue fill. Variations on the KML (the colors written with spaces, an inline style only, a shared `styleUrl` style) all came in red too. A GPX `<rte>` with `<type>Area</type>` and `<onx:color>` / `<onx:fill_color>` extensions, the shape onX's own GPX export uses for an area, imported as a real onX Area (acreage shown) in its color. So Cairn writes areas that way.

The trade-off: **holes aren't kept.** An onX area has one outline, so a polygon with a hole (a donut) is exported as its outer boundary only, with the hole filled in. The runbook lists every such area under "Holes not kept in onX". This is a provisional choice (design decision ENG-05); whether onX can hold a hole in any import format hasn't been tested.

A side effect: every file Cairn writes is now GPX, so the runbook no longer warns that a batch contains KML.

## Limits and trade-offs

### What can't Cairn do?

- **Recreate your folders automatically.** You rename each one in onX after import, as described above. Nesting isn't lost: per project docs, CalTopo and onX folders are both flat.
- **Keep exact colors.** Waypoint and track colors snap to onX's palette, and line widths collapse to two weights.
- **Keep every character in names.** Waypoint, track and area names lose `! @ # $ % ^ * &`, so `#01 Porcupine` becomes `01 Porcupine`. The runbook lists every renamed item under "Renamed for onX". Nothing in the project's onX sources says onX rejects those characters; the rule is kept as a precaution.
- **Control order in onX.** Within each file, items are sorted naturally ("Camp 2" before "Camp 10"). How onX orders them after import hasn't been checked against any onX source.
- **Check onX's per-import cap separately.** onX allows up to 3,000 markups per import file; since that equals the account limit, Cairn's account warning covers it.
- **Keep you under the account limit.** onX says "Your onX account is limited to 3,000 Markups" (help article updated 2026-09-16; it was 1,500 in August). Cairn warns when *this map* is over 3,000, but it can't see what's already in your account. Splitting into more imports doesn't get around an account-wide cap, so the warning tells you to remove or exclude items. What onX actually does when you go over isn't in any cited onX source.
- **Support phone-only importing.** The runbook is written for the Web Map, where the new-folder checkbox lives (per project docs, Aug 2026). Cairn writes only GPX, but importing it on the phone hasn't been tested. The phone app can import GPX, then file it with "Add to Folder".
- **Import without a paid plan.** Importing requires onX Premium or Elite (per project docs, Aug 2026).
- **Get icons, waypoint colors or folders out of a CalTopo GPX.** The GPX doesn't have them. You can still add icons and colors in Cairn before you export, and they go into the files Cairn writes. Folders come from the GeoJSON or KML.

## Privacy

### Where does my map data go?

It stays in your browser. Cairn runs entirely client-side: the conversion is Python running in the page through Pyodide. Your file is read in the page, the zip is built in the browser and downloaded from there, and no code path uploads your map.

The page loads only a few things:
- Its own files: the page, its scripts, the Python bridge, the Cairn engine package, its config and its fonts.
- The Pyodide runtime and its `micropip` and `pyyaml` packages, from one pinned folder on `cdn.jsdelivr.net`.

The site's Content Security Policy only lets the page's scripts load code from, or connect to, its own origin and that one jsdelivr folder. The host (Vercel, possibly behind a Cloudflare proxy that passes the same security headers through) and jsdelivr see ordinary request metadata, such as your IP and that you loaded the page, but never your file. Whether hosting-level analytics are turned on can't be determined from the code.

## The onX round trip

### Can I export from onX, clean it up in Cairn, and import it back?

Partly. The first half works; the second half is untested.

**Into Cairn: yes.** The web app opens the GPX and KML files onX exports. Drop the GPX and the KML of one export together and they become one folder: the KML keeps areas' holes, the GPX keeps tracks' times. onX icons and colors are kept as they are, not re-guessed, and each says "Kept from your onX file." An icon name that isn't in Cairn's list of onX icons is kept too, but marked so you check it. Rows say whether a line is an onX Line or a Track. The gaps:
- **No real onX export file has ever been tested.** The test files are synthetic, written to match onX's export code as decoded in the project's research (Oct 2026), not exported from a real account.
- **Folders aren't in the files.** onX export files carry no folder information (per project docs, Aug 2026). Each file you drop becomes one folder named after the file, so exporting one onX folder at a time and dropping all the files together brings your folders back. Whether onX lets you name those export files is untested; if it doesn't, rename the files before dropping them. Cairn can't rename a folder yet.
- **XML input is guarded.** Now that the browser reads XML, Cairn refuses any GPX or KML with a DTD and any XML file over 16 MB before parsing it.

**Re-importing creates duplicates. Tested on 2026-10-22.** We exported two waypoints from onX and re-imported that exact file, onX's own IDs included. onX added two *new* markups in a new folder instead of updating the originals. So a round trip today is: export from onX and keep that file as a backup, delete the originals in onX, then import the cleaned files from Cairn. Anything onX keeps outside the file (photos, shares, folder membership) is lost when you delete the originals, so back those up first. Otherwise every markup ends up twice and the copies count against the 3,000-markup limit.

So the cleanup half works today, and the way back into onX is "replace", not "update".
