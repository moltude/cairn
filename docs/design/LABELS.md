# Cairn labels and wording inventory

Every user-visible label, action, state and message, so wording stays consistent. Wording rules:
AGENTS.md "Style and design", and DECISIONS.md UI-15 (no "onX" in field labels), UI-18
(button language), UI-26 (modals don't over-explain; commits read "Save").

**Rule (owner, 2026-10-25):** reuse an existing label wherever one exists; a new label takes the
proposed wording only when nothing existing fits. Update this file in the same commit as any label
change. Built from an audit on 2026-10-25 (line numbers as of that day's `main`).

Source abbreviations: `idx` = web/index.html, `app` = web/app.js, `br` = web/bridge.py,
`wt` = web/walkthrough.html. Elements are given as `#id` or `.class`; `—` means no id.
`N` / `{x}` are placeholders. Plural helper: `plural(n, word)` gives "1 item" / "3 items" (app:2171).
Palette colour names and icon names are data (`DATA.colors`, `DATA.line_colors`, `DATA.icons`), not listed.

---

## 1. Global nav and footer

There is no footer nav (UI-38). Nav on every page: App · Help · FAQ · Walkthrough · GitHub.

| Text | Kind | Where | Source | Selector |
|---|---|---|---|---|
| Cairn | wordmark | Top bar (drop, export), rail (edit) | idx:25, idx:62 | `.wordmark` |
| App | nav link (current page underlined) | Top bar; edit-screen search row | idx:28, idx:103 | `nav.site-nav a[aria-current]` |
| Help | nav button, opens Help panel | same | idx:29, idx:104 | `.help-open`, `#help-link` |
| FAQ | nav link | same | idx:30, idx:105 | — |
| Walkthrough | nav link | same | idx:31, idx:106 | — |
| GitHub | nav link | same | idx:32, idx:107 | — |
| Site (aria-label) | nav label | nav | idx:27, idx:102 | — |
| `Cairn — CalTopo to onX` | page title | browser tab | idx:6 | `<title>` |
| `CalTopo to onX, with icons and colors that still mean something.` | meta description | head | idx:7 | — |
| `Cairn FAQ`, `Cairn Walkthrough` | page titles | tabs | faq.html:10, wt:10 | — |
| Status line (empty until a message) | status region | Top bar slot on drop/export; rail foot on edit | idx:26, idx:88 | `#status`, `#status-top`, `#status-rail` |

wt:19-23 repeats the nav with Help linking to `./#help`.

---

## 2. Landing / drop screen

| Text | Kind | Source | Selector |
|---|---|---|---|
| CalTopo → onX Backcountry | kicker | idx:39 | `.kicker` |
| CalTopo to onX, with icons and colors that still mean something. | tagline | idx:40 | `.tagline` |
| Move your map without losing its icons, colors or folders. | h1 | idx:41 | — |
| onX can't read CalTopo's full GeoJSON export, … It reads CalTopo GeoJSON (best), KML and GPX. | lede (prose) | idx:42-45 | `.lede` |
| Drop a CalTopo or onX export | drop-zone title | idx:49 | `.drop-title` |
| .json, .geojson, .gpx or .kml | drop-zone sub | idx:50 | `.drop-sub` |
| Choose file… | primary button, opens the file picker | idx:51 | `#pick` |
| Getting ready… | status on the drop zone while the engine boots | idx:52, app:395 | `#drop-wait` |
| Reading {file name} … / Reading N files… | status | app:360 | `#status` |

---

## 3. Edit screen

### 3.1 Rail head and filters

| Text | Kind | Source | Selector |
|---|---|---|---|
| CalTopo map / onX map / Map | label over map title; by source dialect | idx:63, app:429 | `#map-label` |
| {map title}; Untitled map; "{first} + N more" | h1 | app:419-421 | `#map-title` |
| Map and filters | aside aria-label | idx:59 | `.rail` |
| Type | section header (folds) | idx:70 | `[data-sec=type] .sec-h` |
| Filter by type | group aria-label | idx:71 | `#type-filter` |
| All | facet button | idx:72, app:500 | `data-kind=""` |
| Areas / Lines / Waypoints | facet buttons | idx:74-76 | `data-kind=…` |
| Folders | section header | idx:80 | `[data-sec=folders]` |
| Filter by folder | aria-label | idx:81 | `#folder-facets` |
| All | facet button (first in Folders) | app:592 | `.facet-btn` |
| {folder name} + count; "here now" while a drag is over its own folder | facet button | app:569 | `.facet-btn[data-drop]` |
| Remove empty folder / Remove empty folder {name} | tooltip / aria-label of × | app:582-584 | `.facet-x` |
| + New folder | button and drop target | app:598 | `.new-folder` |
| Folder name | aria-label of the name field | app:773 | `.folder-name-in` |
| Up to 100 characters | tooltip on the name field | app:1771 | `.folder-name-in` |
| Icon | section header | idx:84 | `[data-sec=icon]` |
| Filter by icon | aria-label | idx:85 | `#icon-facets` |
| Default pin | facet checkbox (first) | app:622 | `#only-attention` |
| Waypoints that fell back to onX's default pin | tooltip | app:620 | `label.default-pin` |
| {icon name} + count | facet checkboxes | app:622 | `[data-icon]` |
| No waypoints | empty state (Icon list) | app:636 | `.facet-empty` |
| All / Any / "N icons" / folder / kind / icon name | folded-header summaries | app:509-511 | `.sec-sum` |
| Export | primary button (rail foot) | idx:89 | `#export` |
| Start over | button (rail foot) | idx:90 | `.newmap` |

### 3.2 Search row, chips and empty state

| Text | Kind | Source | Selector |
|---|---|---|---|
| Name or note | placeholder | idx:98 | `#filter` |
| Search | aria-label | idx:98 | `#filter` |
| Search: “{q}” · Type: {kind} · Folder: {name} · Icon: {name} / Icon: Default pin | filter chips | app:647-654 | `.chip` |
| Showing N | label before the chips | app:658 | `.chips-label` |
| Remove filter {chip label} | aria-label of the chip × | app:662 | — |
| Clear all | link button | app:667 | `.linkbtn` |
| Nothing matches these filters. | empty state | app:704 | `.note` |

### 3.3 Folder section headers

| Text | Kind | Source | Selector |
|---|---|---|---|
| {folder name} (click renames) | h2 button | app:778 | `.folder-name` |
| Not in any folder | sub-line for the Unorganized folder | app:720 | `.folder-sub` |
| N item(s) / N of M shown / Empty | sub-line | app:721-722, app:764 | `.folder-sub` |
| Expand {folder} / Collapse {folder} | aria-label | app:727 | `.collapse` |
| Select all shown in {folder} | aria-label of header checkbox | app:732 | `.folder-all` |
| Name (sort button) / Sort {folder} by name | column header / aria-label | app:733 | `.sort-btn` |
| Note · Icon | column headers | app:733 | `.note-th` |
| New folder / New folder 2 … | default new-folder name | br:723, br:886 | — |
| Unorganized | folder for items outside any folder | parser.py:19, br:513 | `UNORGANIZED_FOLDER_NAME` |

### 3.4 Rows

| Text | Kind | Source | Selector |
|---|---|---|---|
| Select {name} | checkbox aria-label | app:976 | `.sel-box` |
| Name of {name} | aria-label of the name field | app:977 | `.name-in` |
| Excluded | state label | app:978 | `.exc-label` |
| Include / Include {name} | button / aria-label on an excluded row | app:978 | `.exc-chip` |
| Left out of the export. Click to put it back. | tooltip | app:978 | `.exc-chip` |
| Add a note | empty-note button text | app:981 | `.note-text.empty` |
| {first line of note} · Open note for {name} | button text · aria-label | app:980-981 | `.note-btn` |
| {icon name} or "Default pin" | text under the marker | app:984-987 | `.icon-name`, `.whymark` |
| {Icon}, {Color}. Change icon or color | marker aria-label | app:983 | `.icon-btn` |
| Line / Track / Area | text on line and area rows ("Track" for onX-file tracks) | app:793-794 | `.icon-name.kind` |
| {Line/Track/Area}, {Color}, {Style}, {Weight}. Change line / Change area | aria-label | app:988 | `.line-btn` |
| Won't export: it has no coordinates. | caution | app:947 | `.caution` |
| onX imports only the first 512 bytes of a note. About N character(s) will be cut. | caution | app:950 | `.caution` |
| onX will reset this area's fill to its default blue. | caution | app:957 | `.caution.fill-caution` |

### 3.5 Selection bar and More menu

| Text | Kind | Source | Selector |
|---|---|---|---|
| 0 selected / N selected | count | idx:114, app:1192 | `#selcount` |
| Icon & color… / Color & style… (only lines and areas selected) | button; opens the bulk dialog | idx:115, app:1202 | `#bulk-icon` |
| Select items first | tooltip when disabled | app:1197 | `#bulk-icon`, `#more-btn` |
| More | menu button | idx:117 | `#more-btn` |
| More actions | menu aria-label | idx:118 | `#more-menu` |
| Move to… | menu item | idx:119 | `#bulk-move` |
| Use note as name | menu item | idx:120 | `#bulk-desc` |
| Exclude · Include | menu items | idx:121-122 | `#bulk-exclude`, `#bulk-include` |
| Clear | link button; clears the selection | idx:125 | `#clear-sel` |

---

## 4. Icon & color popover (one item)

| Text | Kind | Source | Selector |
|---|---|---|---|
| Change icon and color for {name} / Change line for {name} / Change area for {name} | dialog aria-label | app:1310 | `#mark-pop` |
| {item name} or Untitled | popover title | app:1314 | `.pop-name` |
| Color · Icon · N icons | section labels / count | app:1317-1319 | — |
| Find an icon | search placeholder and aria-label | app:1320 | `.icon-search` |
| No icon matches “{q}”. | empty state | app:1293 | `.grid-empty` |
| Style: Solid / Dashed (Dotted from a file) · Weight: Thin / Thick (Extra thin from a file) | toggles | app:1219-1248 | `.tog` |
| Fill · Blue · Leave as is | area fill section | app:1229-1266 | `.fill-btn`, `.fill-reset` |
| Cancel · Save | buttons | app:1325-1326 | `.pop-cancel`, `#pop-apply` |

## 5. Color & style dialog (several items)

| Text | Kind | Source | Selector |
|---|---|---|---|
| Change N item(s) | dialog heading | app:1444 | `#mark-dialog h2` |
| Change icon and color for N items / Change color and style for N items | aria-label | app:1441 | `#mark-dialog` |
| Close | aria-label of × | app:1445 | `.bulk-x` |
| Now / After | column labels | app:1447 | `.now-after` |
| {name} or Untitled | row text | app:1506 | `.na-name` |
| Waypoint color / Line color (mixed) · Color | section labels | app:1451-1456 | `.color-sec` |
| Find an icon for all selected waypoints | search aria-label | app:1453 | `.icon-search` |
| Leave as is | chip on every section | app:1229 | `.reset-chip` |
| Cancel · Save | buttons | app:1459-1460 | `.bulk-cancel`, `#bulk-apply` |

## 6. Move to…

| Text | Kind | Source | Selector |
|---|---|---|---|
| Move N item(s) to | list heading | app:1899 | `#move-h` |
| Move to folder | aria-label | idx:155 | `#move-pop` |
| {folder} + count · {folder} · here now | options | app:1902-1905 | `.move-opt` |
| + New folder | option (makes a folder and opens its name) | app:1906 | `.move-new` |
| Move N item(s) | drag ghost | app:2032 | `#drag-ghost` |

## 7. Folder rename, merge, new folder

| Text | Kind | Source |
|---|---|---|
| A folder needs a name. | status (error) | app:1812, app:1832; br:750 |
| A folder name can be up to 100 characters. | status (error) | app:1775 |
| “{name}” already exists / Move the N item(s) in “{src}” into it? / Move them · Cancel | merge confirm | app:1869-1874 |
| “{name}” already exists. | status (error) | app:1862 |
| Made an empty folder. · Removed the empty folder “{name}”. | status | app:1732, app:1745 |
| Moved N item(s) to a new folder / to {name} / to the folder. (+ “{x}” is empty now, so it was removed.) | status | app:1697-1698 |

## 8. Note editor

| Text | Kind | Source | Selector |
|---|---|---|---|
| Note | field label | app:1094 | `.note-ed label` |
| Save (Ctrl/⌘+Enter) · Cancel (Esc) | buttons | app:1097-1098 | `.note-apply`, `.note-cancel` |

## 9. Confirmation dialogs (openConfirm, app:2215)

| Title | Body | Buttons (default focus in bold) | Source |
|---|---|---|---|
| Start over? | This discards N unexported change(s). / This clears the current map. | **Cancel**, Start over (danger) | app:2326-2333 |
| Leave this map? | Changes will be lost. | **Stay**, Leave (danger) | app:306-312 |
| Save your note? | Your note for “{name}” hasn't been saved. | Keep editing, Discard, **Save** | app:2351-2361 |
| “{name}” already exists | (merge, §7) | Move them, **Cancel** | app:1869-1874 |
| 1 area will lose its fill. / N areas will lose their fill. | onX resets area fills to blue on import. | Leave this out / Leave these N out, **Keep it / Keep them** | app:2256-2264 |

## 10. Export screen

| Text | Kind | Source | Selector |
|---|---|---|---|
| Export | kicker | idx:135 | `.kicker` |
| Your files are ready | h1 | idx:136 | — |
| Download all | primary button (`onx_ready.zip`) | idx:138 | `#download` |
| One zip with every folder and instructions.txt | hint | idx:139 | `.done-hint` |
| Back · Start over | buttons | idx:141-142 | `#back`, `.newmap` |
| Import each folder into onX's Web Map; onX will use a default datetime stamp for the folder name. Importing needs onX Premium or Elite. | intro | idx:145 | `.rb-intro` |
| N · {folder name} (number only when names repeat) | box title | app:2161 | `.rb-title` |
| Download / Download {N · }{folder} | per-folder button / aria-label | app:2156-2162 | `.rb-dl` |
| **N** item(s) wasn't / weren't exported: it has / they have no coordinates. X of Y were written. | warning | app:2142 | `.note.warn` |
| Item 'A' is over the length limit and will be truncated by onX. / Items 'A', 'B' and N more are over … | warning | app:2125-2131 | `.note.warn` |
| onX accounts hold at most 3,000 markups; this map has N. Remove or exclude some before importing. | warning | app:2144 | `.note.warn` |

## 11. Help panel (idx:166-253)

| Text | Kind |
|---|---|
| How to use Cairn | dialog title |
| 1 · Export from CalTopo · 2 · Review the icons · 3 · Edit in bulk · 4 · Folders · 5 · Leave things out · 6 · Export and import | headings |
| What carries across (Name, Note, Icon, Color, Line style, Folders, Lines vs areas) · Good to know | headings / table |
| Click a box / Shift + click / Ctrl / ⌘ + A / Header checkbox / Esc / Notes | shortcut rows |

## 12. Status line and bridge messages

### 12.1 Status line (setStatus; "ready" lines clear after 8 s, app:35)

| Text | Class | Source |
|---|---|---|
| Reading {name} … / Reading N files… | info | app:360 |
| Couldn't read that file — {reason} / Couldn't read those files — {reason} | err | app:386 |
| Failed: {reason} (engine boot) | err | app:239 |
| Couldn't load the map engine (HTTP N). | err | app:208 |
| Changed N item(s) / line(s) / area(s) | ready | app:1541-1542 |
| An item needs a name. | err | app:1062 |
| Couldn't move / make a folder / remove / rename — {reason} | err | app:1652, 1728, 1743, 1824 |
| Everything is excluded — include at least one item to export. | err | app:2101 |
| Building onX files… | info | app:2104 |
| Export failed: {reason} · Download failed: {reason} | err | app:2118, app:2191 |

### 12.2 Icon "why" text (marker tooltip; br)

| Text | Source |
|---|---|
| Kept from your onX file. · Kept from the file you loaded. | br:211-212 |
| Your CalTopo symbol “{sym}” maps to this icon. | br:191 |
| Matched “{terms}” in the name / note. · Matched a keyword in the {name/note}. | br:195-196 |
| Your mappings send CalTopo's “{sym}” symbol to onX's default pin, … | br:188-190 |
| Your CalTopo symbol “{sym}” has no onX equivalent, and nothing in the name matched. Using the default pin — pick an icon to keep the meaning. | br:199-201 |
| CalTopo's generic “{sym}” pin carries no meaning to copy, and nothing in the name matched. Using the default pin. | br:203-204 |
| No CalTopo icon was set and nothing in the name matched. Using the default pin — pick an icon if this should be something. | br:205-206 |
| Your onX file / The file you loaded uses the icon “{icon}”, which Cairn doesn't know. It goes out unchanged; pick one from the list if onX doesn't show it. | br:271-274 |
| Tracks and areas don't take an icon in onX. | br:557 |
| You chose the default pin (for this one). · You set this icon. | br:683-685, app:1150-1151 |

### 12.3 Errors from bridge.py and the readers (after "Couldn't read that file —")

| Text | Source |
|---|---|
| This isn't a map file Cairn can read. Cairn reads CalTopo GeoJSON, and GPX or KML exported from onX or CalTopo. | br:246-248 |
| Cairn found no waypoints, lines or areas in {names}. + the same sentence | br:342-344 |
| {file} couldn't be read: {reason} · {file}: {error} | br:296, br:381 |
| No file was given to open. | br:365 |
| This file is X.X MB, and Cairn opens GPX and KML files up to 16 MB. Export one folder at a time instead. | input_check.py:140-143 |
| This file contains a <!DOCTYPE> declaration, which map exports from onX, CalTopo and Google Earth never include, so Cairn won't open it. | input_check.py:146-149 |
| Failed: Could not load file (any unreadable GeoJSON; shown on its own, without “Couldn't read that file —”) | br `GEOJSON_FAILED` |
| There is no folder '{key}' in this map. · No items were given to move. · “{name}” isn't empty, so it can't be removed. · No exported folder N. Export again. | br:743, 864-869, 923, 1104 |

## 13. instructions.txt (fixed lines; CRLF; straight quotes; br:1212)

| Line | Condition |
|---|---|
| How to import these files into onX | always, first |
| These files came from onX. onX imports them as new markups; it doesn't update the originals. / Keep your onX export as a backup. / In onX, delete the original markups first, then their folders. Deleting a folder doesn't delete its markups. / Then import as below. | from an onX file |
| Import each folder below into onX's Web Map (webmap.onxmaps.com), one at a time. / In onX, choose Import and add all of that folder's files together. / Tick "Import map data to a new folder". / onX names the new folder with a datetime stamp. / Rename it to the name shown for that folder below. / Importing needs onX Premium or Elite. | always |
| {NN_Name}/    rename to: {folder name} · {file} · Waypoints / Lines / Areas · {item name} | per folder, file, item |
| (over the length limit; onX will cut this note) · (its hole is not kept: an onX area has one outline) · (no name) | under an item |

## 14. FAQ and walkthrough headings

FAQ (source docs/FAQ.md; web/faq.html is generated) group headings: The problem, Your files, What Cairn
does, Limits and trade-offs, Round trip. Walkthrough step tags: Before, Step 1, What Cairn finds, What
Cairn flags, What you fix, Your folders, What you import, Good to know. Controls named in their prose:
Default pin, Icon & color…, Save, Download all, + New folder, More → Move to….

---

## 15. Inconsistencies found (2026-10-25)

Owner's answers, 2026-10-25: **done** 1, 2 (rule above), 3, 4, 7 ("Blue"), 9, 12, 14 ("datetime"), 17 ("Failed: Could not load file"). **Follow-up**: 8 (TODO.md). **Open, explained to the owner**: 5, 6, 10, 11, 13, 15, 16, 18. **Kept**: 19.


1. **Apply vs Save.** Every visible label says Save; DECISIONS UI-16 and UI-18 rule 4 still say Apply. Fix the decision text (superseded by UI-26).
2. **Exclude vs "leave out".** Menu and state say Exclude / Excluded / Include; the fill confirm says "Leave this out / Leave these N out", the excluded-row tooltip "Left out of the export", Help's heading "5 · Leave things out". Suggest Exclude wording in controls; prose may keep "leave out".
3. **item / markup / row / pin.** "item" is the app word; "markup" is onX's word (keep for onX limits and import); "Select rows first" (app:1197) and "Pin color" (app:1451) drift. Suggest "Select items first" and "Waypoint color".
4. **Line vs Track.** Lines everywhere; onX-file tracks show "Track" on purpose. Keep; documented here.
5. **"+ New folder…"** in Move to… has an ellipsis but acts immediately (the rail's "+ New folder" has none). Suggest no ellipsis.
6. **Titles and periods.** The fill confirm title ends with a period ("1 area will lose its fill."); other titles don't. Status sentences mix: "Changed N items" (no period) vs "Moved N items to X." Suggest no period on titles, a period on status sentences.
7. **Quotes.** app.js uses straight apostrophes with curly double quotes; bridge.py mostly curly apostrophes; the long-note warning uses straight single quotes around names. Suggest curly “” around names and ’ in app text; straight only in instructions.txt.
8. **"onX" in a control.** "Use onX's blue fill" is the one button label naming onX (UI-15). Suggest "Use blue fill".
9. **Error prefixes.** "Failed: …", "Export failed: …", "Download failed: …" vs "Couldn't X — …" everywhere else. Suggest "Couldn't start — …", "Couldn't export — …", "Couldn't download — …".
10. **Name required.** "A name is required. onX searches by name only." vs "A folder needs a name." Suggest "An item needs a name." (UI-26: no explanation).
11. **Discard warnings.** "Changes will be lost." (Leave this map?) vs "This discards N unexported change(s)." (Start over). Suggest the counted form in both.
12. **Confirm button order.** Most put the safe choice first, the commit last; the merge confirm ("Move them, Cancel") and fill confirm ("Leave this out, Keep it") don't. Suggest safe first, commit last everywhere.
13. **Cancel meaning "keep editing".** In "Save your note?", Cancel returns to the note; elsewhere Cancel discards. Suggest "Keep editing".
14. **Nameless items.** "Untitled" in dialogs vs "(no name)" in the long-note warning and instructions.txt. Suggest "Untitled" in the app; "(no name)" may stay in instructions.txt.
15. **Date stamp.** "default datetime stamp" (export intro) vs "date and time stamp" (instructions.txt). Suggest "a date and time stamp".
16. **Web Map.** "Web Map" in the app vs "web map" in the FAQ. Suggest "Web Map" (onX's product name).
17. **Stale FAQ heading.** "What's the 'Default pin' / 'needs attention' thing?" names an internal field. Suggest dropping "/ 'needs attention'".
18. **Server paths in GeoJSON errors.** parser.py messages show `/tmp/…` paths and developer wording. Suggest one plain sentence via bridge.py, as the XML readers already get.
19. **Arrows in Help.** "More → Move to…" vs UI-18 rule 2 (no arrows in button labels). The rule is about labels; Help may keep it, or write "More, then Move to…".

## 16. Canonical vocabulary

| Concept | Use | Don't use |
|---|---|---|
| Thing in the list | **item** | markup (except onX's own objects), row (except keyboard help), entry |
| Types | **Waypoint**, **Line**, **Area** (Waypoints, Lines, Areas in filters) | Track (except onX-file tracks), Shape, Pin (except "Default pin") |
| Grouping | **folder** (loose items: **Unorganized**) | directory (except zip contents), group, layer |
| The marker choice | **Icon** | onX icon, symbol (except "CalTopo symbol") |
| The default icon | **Default pin** (engine name `Location`) | needs attention |
| Colour | **Color** | colour |
| Free text | **Note** | description, desc |
| Commit / dismiss | **Save** / **Cancel**; **Keep editing** when Cancel would mean going back to an edit | Apply, OK, Done |
| Leave out of the export | **Exclude** / **Include**, state **Excluded** in menus, buttons and states. **Leave out** is fine where a sentence reads better: dialogs, tooltips, Help, FAQ, README (owner, 2026-10-25) | Skip, Hide |
| Keep as is | **Leave as is** | Use existing, Reset |
| Reset a filter or selection | **Clear**, **Clear all** | Deselect, Reset |
| Remove one thing | **Remove** | Delete |
| Restart | **Start over** | New map, Reset |
| Back one screen | **Back** | Edit more |
| Make files | **Export**, **Download all**, **Download** | Export for onX |
| Open a file picker | **Choose file…** | Browse |
| Opens a dialog | label ends with **…** | ellipsis on actions that act immediately |
| Make a folder | **+ New folder** | New folder… |
| Move items | **Move to…**, **Move N items to** | Put in |
| Take a note as the name | **Use note as name** | Use description as name |
| Bulk text edits (new, 2026-10-25) | **Rename…**, **Change note…**; modes **Add before**, **Add after**, **Find and replace**, **Replace the note**; fields **Find**, **Replace with**, **Text**; **Match case**; rows **No change**, **Name can't be empty**; summary **N will change · M unchanged** | |
| onX's own objects | **markup**, **Web Map**, **Premium or Elite**, **Import map data to a new folder** | |
| Errors | **Couldn't X — reason** | Failed: … |
| Quotes | “…” around names in the app; ’ apostrophes; straight quotes only in instructions.txt | |
| Date stamp | **datetime stamp** | date and time stamp |
| Sentences | short and direct; no period on titles, a period on status sentences | narrating modals (UI-26) |
