# Cairn FAQ

![Diagram: different starting points, one clean import. A CalTopo map can be exported three ways. GeoJSON keeps it all: names, notes, folders, icons, colors, line style and areas. KML keeps the same except dashed lines, so line style survives only partly. GPX keeps names and notes, colors only partly, and loses folders, icons, line style and areas. Any of the three, or any other GeoJSON, KML or GPX file, goes into Cairn, which starts from what the export kept and lets you set icons, colors and line styles on everything at once and check every name and note. Cairn always writes GPX, one standard format, which onX Backcountry imports the same way every time. Notes too long for onX are truncated and area fill cannot be imported; both are flagged before you export.](../web/faq/how-cairn-works.webp)

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

## Your files

### Which file should I export?

Whichever you pick, you get the same thing out: onX-ready GPX files (waypoints, tracks, and areas as onX areas) and `instructions.txt`, a plain-text import guide. What differs is how much comes in.

- **GeoJSON (best).** Brings in everything: folders, icons, colors, line style and width, areas and notes. Goes out with all of it.
- **KML.** Brings in folders, icons, colors, line width, areas and notes, but not dashed lines (every line comes in solid). Goes out with what came in.
- **GPX.** Brings in only names, notes and most line colors: no folders, no icons, no waypoint colors, no areas. Goes out with what came in, plus any icons and colors you add in Cairn first.

## What Cairn does

### What does Cairn actually do?

It runs in your browser and takes a CalTopo GeoJSON export. It also opens a CalTopo KML (folders, icons, colors and notes, like the GeoJSON), a CalTopo GPX (names, notes and line colors, with no folders or icons; Help says the GeoJSON or KML keeps them), or the GPX and KML you export from onX (see the round-trip question below). Drop several files at once and each becomes a folder named after the file; an onX GPX and KML from the same export become one folder. It sorts every feature it recognizes into waypoints (Marker points), lines (Line or Shape linestrings) and areas (Shape polygons). Any other kind of feature is skipped without a message and isn't counted. It picks an onX icon and color for each item. You review and edit the results, one at a time or in bulk, and sort items into folders. Then the export screen hands you the files:

- **Download all** gets one zip, `onx_ready.zip`, with one numbered directory per folder (`01_Name/`, `02_Name/`, …). `Name` is the folder name with punctuation removed and spaces turned into underscores.
- Each folder's **Download** gets just that directory, as `01_Name.zip`. Its files are byte for byte the ones in Download all.
- In each directory, up to three kinds of file: `Name_Waypoints.gpx`, `Name_Tracks.gpx` and `Name_Areas.gpx`. A large GPX may be split into numbered parts (see below).
- `instructions.txt`, at the top of Download all: how to import, then each numbered directory with the folder name to give it in onX, its files, and the name of every waypoint, line and area in each file. It's plain text, so it opens in Notepad or TextEdit.

Waypoints become GPX `<wpt>` with onX's own `<onx:icon>` and `<onx:color>` extensions. Lines become GPX `<trk>` with `<onx:color>`, `<onx:style>` and `<onx:weight>`. Polygons become GPX `<rte>` routes marked `<type>Area</type>` with `<onx:color>`, `<onx:style>`, `<onx:weight>` and `<onx:fill_color>`, the way onX's own GPX export writes an area (see "Why are areas in a GPX file, not KML?" below). Every file is GPX, so nothing needs the KML importer.

### How does Cairn pick an onX icon?

It checks in this order for each waypoint and stops at the first hit:

1. **Your CalTopo symbol, exact match.** For example, `cabin` maps to `Shelter`.
2. **Your CalTopo symbol, partial match.** The longest mapping key found inside the symbol name wins.
3. **Keywords in the name and description.** Single-word keywords such as "hut", "camp" or "spring" must match a whole word. Keywords that contain a space, such as "trail head", match anywhere in the text. Each matching keyword scores a point. The highest score wins, and a tie goes to whichever icon comes first in the mapping list. The folder name is never scanned. A known gap: digits stuck to a word stop it matching, so "Camp 2" matches `camp` but "Camp2" doesn't.
4. **The default pin, `Location`.**

Generic CalTopo symbols (`point`, `marker`, `pin`, `dot`, `circle`) carry no meaning, so Cairn skips steps 1 and 2 for them and goes straight to keywords. A waypoint called "Elk Hut" with a plain `point` symbol still ends up as `Shelter`. A symbol that matches always beats the keywords.

The shipped tables, as the web app loads them, have 152 symbol mappings and keyword lists for 30 icons. Cairn's list of valid onX icons has 95 names. Only waypoints get icons. Tracks and areas don't take an icon in onX.

### What's the "Default pin" / "needs attention" thing?

Any waypoint that ends up as `Location` is marked "Default pin" so you can spot it and choose a real icon. Choosing any icon clears the flag, including choosing `Location` on purpose. One quirk: a symbol that is deliberately mapped to `Location` (such as `flag-1`) also gets flagged, but its explanation reads "Your CalTopo symbol maps to this icon."

Two things here are unverified:
- That `Location` shows up in onX as onX's default pin is Cairn's assumption.
- What onX does with an icon name it doesn't recognize isn't settled by any onX source the project cites. That it falls back to its default pin is the owner's own observation, and the project's decision-surface doc says the same without citing a test.

There was a real bug of this kind. Cabins, huts and yurts used to map to `Cabin`, which isn't a valid onX icon. As of 2026-10-22 they map to `Shelter`.

### How are colors matched?

onX has a fixed palette, per project docs (Aug 2026): 10 colors for waypoints and 11 for lines. The extra line color is Fuchsia. CalTopo allows any color, so Cairn snaps each waypoint and line color to the nearest onX color by straight RGB distance. That means close shades merge into one color. Fuchsia on a waypoint becomes Purple.

Some edge cases:

- **Waypoint with no color:** Cairn writes the icon's usual color, for example Brown for `Shelter`. It uses Blue only when the icon has no usual color. Cairn always writes an explicit color, so onX's own default never applies. The on-screen preview still shows such a waypoint as blue while the export uses the icon's color. If it matters to you, set the color yourself.
- **Line with no color, or a color Cairn can't read:** it gets Blue. Short hex like `#abc` is treated as unreadable.
- **Areas snap to the 11-color line palette**, like lines, and export in exactly the color the screen shows (Blue when the CalTopo color is missing or unreadable). Their outline also gets a style and weight, by the same rules as a line (dashed, and 6.0 when the CalTopo width is over 4); you can change both in Cairn. The fill is written as the nearest of onX's 10 area fill colors to CalTopo's fill color (or to the outline color when CalTopo gives none), or as no fill when CalTopo's fill opacity is 0. **onX ignores it on import**: every imported area gets onX's default light blue fill, whatever the file says, even onX's own fill values (checked 2026-10-23 with eight different encodings). onX keeps the outline color, style and weight. An area from an onX export keeps its own values, including a dotted or extra-thin (2.0) outline.
- **Line style:** see "Do dashed and dotted lines come across?" below. Width collapses to two weights, 4.0 or 6.0 (6.0 when the CalTopo width is over 4).
- **From a CalTopo GPX:** a line's color is read from its Garmin color name (`Red`, `Magenta`, `DarkBlue` and so on) and then snapped like any other. A line with no name gets Blue, and a waypoint never has a color in a GPX, so it gets its icon's usual color.

### Do dashed and dotted lines come across?

Only a dashed line, and only from the GeoJSON or an onX export. Line styles in onX are `solid`, `dash` and `dot`, written as `<onx:style>` on a track. All three appear in real onX exports: `solid` and `dash` on lines, `dot` on an area outline (`tests/fixtures/onx_real/`, `tests/fixtures/onx_exports/`). onX's code shows no arrow style.

CalTopo writes a line's style in the GeoJSON `pattern` property:
- `solid` is solid.
- `M0 -1 L0 1,,8,F` is CalTopo's dashed line. It's a short stroke repeated every 8 pixels, written as an SVG path. This value appears in real exports, and Cairn exports it as `dash`.
- CalTopo's dotted and arrow styles exist, but nobody has seen what they write yet, so Cairn exports them as `solid` for now. Once a CalTopo export with each style turns up, mapping them takes one line each. A directional arrow can only become `solid` or `dash`.

CalTopo's KML and GPX don't carry a pattern at all, so every line read from them is solid. An onX export does carry its line style, and Cairn keeps it.

### Can I bulk-edit before export?

Yes. Tick rows, then:

- **Icon & color…** sets one icon and color on all of them. The icon applies to waypoints only, since lines and areas have none. With only lines and areas ticked, the button reads **Color…**. With both, pins and lines each get their own color row, since onX gives lines one more color (Fuchsia).
- **Line style…** sets the style (solid or dashed) and weight of the ticked lines and areas.
- **More** moves the rows to another folder (**Move to…**), renames each to its own note (**Use note as name**), or leaves them out of the export (**Exclude**, undone by **Include**). Excluded rows stay in the list, struck through. Your source file is never changed.

The search box and the **Type**, **Folders** and **Icon** lists narrow what's shown, and select-all only takes the rows you can see. You edit names and notes one item at a time. Bulk rename (prefix, suffix, find and replace) and bulk note editing aren't built yet.

The reason for doing this before import: onX's own bulk tools are limited. In the onX Web Map (checked 2026-10-22), My Content's **Select** mode offers only Add to Folder, Share, Export and Delete for a selection. There is no bulk icon, color or rename, so in onX those changes are one markup at a time.

### What do the marks in the list mean?

- **Default pin** under a marker: Cairn found no icon for it (see above).
- **A caution mark:** onX won't keep something as is. Before a note: the note is over onX's 512-byte import limit (onX imports only the first 512 bytes of a note) and will be cut, or the item has no coordinates and won't export. At the right end of an area's Icon cell, after "Area": onX will reset this area's fill to its default blue. Hover it, or tab to it, for the details.
- **A name or note cut short:** hover it, or tab to it, to read all of it. The tip keeps the note's line breaks, and you can select text in it. Esc closes it.
- **The arrow in a Name header** sorts by name: A–Z, then Z–A, then back to map order. Each folder sorts on its own, and numbers sort naturally ("Camp 2" before "Camp 10"). Sorting changes only the view, never the export.

### Do my notes come across?

Yes. Each waypoint's or line's notes go into the GPX `<desc>`. HTML is stripped, and an empty note means no `<desc>` at all. Area notes go into the area's GPX `<desc>` the same way. Multi-line notes are kept: `<br>`, paragraphs, `<div>`s and list items become real line breaks. This is true whether the map came in as CalTopo GeoJSON, KML or GPX: all three carry the same note text.

Only real HTML tags are removed (CalTopo descriptions can contain HTML), so plain-text angle brackets such as `< 2 mi to camp, > 1 mi to water` or `Bring <2L water>` survive. One caveat: a note that contains something tag-shaped, like `<Lake>`, is still treated as a tag. More than one blank line in a row becomes one.

Two things are unverified:
- That onX shows `<desc>` as the markup's Notes. This is only the owner's observation.
- **Whether onX keeps those line breaks is unknown.** It's an open item in the project's to-do list. In a real import on 2026-10-22, multi-line track notes came through intact, but onX also showed a `<desc>` written as `key=value` lines verbatim as the note, which is why Cairn's `<desc>` holds only your note text.

### Can I change the folders in Cairn?

Yes. The **Folders** list on the left shows each folder and its count; each folder becomes one onX folder.

- **Move rows:** drag a row onto a folder in the list. Tick several first to drag them together. **More → Move to…** does the same from the keyboard.
- **New folder:** drop rows on **+ New folder**, then type its name. Clicking it does the same for the ticked rows. With nothing ticked it makes an empty folder to drop rows on; its **×** removes it.
- **Rename:** click a folder's name above its rows. Names are up to 100 characters.
- **Merge:** rename a folder to a name that's taken, and Cairn offers to move its items into the other folder.
- **Empty folders:** a folder you empty by moving its rows goes away. One you made empty stays until you fill or remove it. Empty folders aren't exported.

Moved items keep their edits and exclusions. Start over counts moves and renames as changes, and asks first.

### How do folders work in onX? Why is there an instructions file?

Per project docs (Aug 2026), from reading onX's Web Map code: when you tick "Import map data to a new folder", each import batch (one click of Import, any number of GPX and KML files) creates exactly one new folder named like `Import mm/dd/yy H:MM`. If you leave the box unticked, no folder is created. Filenames and GPX metadata don't change that name. onX folders are flat, with no nesting. Whether onX's server builds folders from KML `<Folder>` elements hasn't been tested. The docs rate "it doesn't" as a high-confidence inference.

So Cairn gives you one numbered import per folder. On the onX Web Map, under My Content → Import, add all of one folder's files at once, tick "Import map data to a new folder", click Import, and rename the new folder. `instructions.txt` says the same and gives the name for each folder.

Some details:
- Folders are listed and numbered by name, with numbers in order ("1 - …" before "2 - …" and "10 - …"), whatever the case. A new or renamed folder takes its place in that order. "Unorganized" (the items that weren't in any folder) always comes last.
- Items that weren't in any CalTopo folder go in a folder called "Unorganized". You can rename it.
- If your map has no folders at all, everything goes into one folder named after your file.
- `instructions.txt` names every item in each file, so you can check a folder in onX against it. If a folder comes up short, delete it in onX and redo just that import.

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

Cairn writes every CalTopo line, including a CalTopo Shape drawn as an open line, as a GPX `<trk>`. That's the only path where Cairn writes onX color, style and weight. So all your lines arrive as **Tracks**, and Cairn never creates onX "Lines". Closed polygons go to an Areas GPX as onX Area routes and become Areas, with their outline color, style and weight. onX gives each one its default fill. A multi-part area (MultiPolygon) becomes one onX Area per part, each with the same name, color and notes.

### Why are areas in a GPX file, not KML?

Because onX ignores an area's color in KML. Checked in a real onX Web Map import on 2026-10-22: Cairn's old `Areas.kml` (a KML `<Style>` with line and fill colors, plus onX-style `ExtendedData` color and fill fields) came in with onX's default red outline and light blue fill. Variations on the KML (the colors written with spaces, an inline style only, a shared `styleUrl` style) all came in red too. A GPX `<rte>` with `<type>Area</type>` and `<onx:color>` / `<onx:fill_color>` extensions, the shape onX's own GPX export uses for an area, imported as a real onX Area (acreage shown) in its outline color. So Cairn writes areas that way. The outline's style and weight come through too (checked 2026-10-23). The fill is never imported from either format, not even onX's own fill values: onX always uses its default light blue fill.

The trade-off: **holes aren't kept.** An onX area has one outline, so a polygon with a hole (a donut) is exported as its outer boundary only, with the hole filled in. `instructions.txt` marks every such area with a line under its name. This is a provisional choice (design decision ENG-05); whether onX can hold a hole in any import format hasn't been tested.

A side effect: every file Cairn writes is now GPX, so nothing warns any more that a batch contains KML.

## Limits and trade-offs

### What can't Cairn do?

- **Name your folders in onX for you.** You rename each one in onX after import, as described above. Nesting isn't lost: per project docs, CalTopo and onX folders are both flat.
- **Keep exact colors.** Waypoint and track colors snap to onX's palette, and line widths collapse to two weights.
- **Control order in onX.** Within each file, items are sorted naturally ("Camp 2" before "Camp 10"). How onX orders them after import hasn't been checked against any onX source.
- **Check onX's per-import cap separately.** onX allows up to 3,000 markups per import file; since that equals the account limit, Cairn's account warning covers it.
- **Keep you under the account limit.** onX says "Your onX account is limited to 3,000 Markups" (help article updated 2026-09-16; it was 1,500 in August). Cairn warns when *this map* is over 3,000, but it can't see what's already in your account. Splitting into more imports doesn't get around an account-wide cap, so the warning tells you to remove or exclude items. What onX actually does when you go over isn't in any cited onX source.
- **Support phone-only importing.** The import instructions are written for the Web Map, where the new-folder checkbox lives (per project docs, Aug 2026). Cairn writes only GPX, but importing it on the phone hasn't been tested. The phone app can import GPX, then file it with "Add to Folder".
- **Import without a paid plan.** Importing requires onX Premium or Elite (per project docs, Aug 2026).
- **Get icons, waypoint colors or folders out of a CalTopo GPX.** The GPX doesn't have them. You can still add icons and colors in Cairn before you export, and they go into the files Cairn writes. Folders come from the GeoJSON or KML.

## Privacy

### Where does my map data go?

It stays in your browser. Cairn runs entirely client-side: the conversion is Python running in the page through Pyodide. Your file is read in the page, the zip is built in the browser and downloaded from there, and no code path uploads your map.

The page loads only a few things:
- Its own files: the page, its scripts, the Python bridge, the Cairn engine package, its config and its fonts.
- The Pyodide runtime and its `pyyaml` package, from one pinned folder on `cdn.jsdelivr.net`.

The site's Content Security Policy only lets the page's scripts load code from, or connect to, its own origin and that one jsdelivr folder. The host (Vercel, possibly behind a Cloudflare proxy that passes the same security headers through) and jsdelivr see ordinary request metadata, such as your IP and that you loaded the page, but never your file. Whether hosting-level analytics are turned on can't be determined from the code.

## Round trip

### Round-tripping onX data (batch edits)

This is optional, and it takes some effort. onX's web map has no bulk editing, so if you want to change many icons, colors or line styles at once, you can send a folder through Cairn and back. The steps:

1. In the onX web map, put the markups you want to edit in one folder. Export that folder twice: once as **GPX** and once as **KML**.
2. Drop both files into Cairn together. They become one folder. Icons, colors, line style and weight, and notes arrive as they are in onX.
3. Edit. Icon, color, line style and weight can be changed for many rows at once. Names and notes are edited one item at a time.
4. Export from Cairn.
5. Import the files into onX, following the export screen (or `instructions.txt`).
6. Delete the originals in onX yourself.

Things to know:
- **onX imports everything as new markups.** It ignores the ids in the file, so it can't update the originals in place. Until you delete the originals you have every markup twice, and the copies count against the 3,000-markup limit.
- **Deleting a folder in onX does not delete the markups inside it.** Delete the markups, then the folder.
- **Keep your onX export as a backup.** Anything onX keeps outside the file (photos, shares) goes with the originals.
- **Long notes are cut.** onX keeps the first 512 bytes of a note. Plain English is one byte per letter; accents and dashes take two or three. Cairn warns about notes that are too long.
- **Long lines get thinner.** The first time a line goes into onX it drops about 15 to 25 percent of its points, keeping the ends.
- **Areas lose holes.** An onX area has one outline.
- **Folders aren't in the files.** Each file or pair you drop becomes one folder named after the file, so export one onX folder at a time.

In two rounds of tests in a real onX account (October 2026), the edits listed in step 3 all came back as made.
