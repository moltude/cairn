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
| Select {name} (Untitled when it has none) | checkbox aria-label | app:976 | `.sel-box` |
| Name of {name} | aria-label of the name field | app:977 | `.name-in` |
| Excluded | state label | app:978 | `.exc-label` |
| Include / Include {name} (Untitled when it has none) | button / aria-label on an excluded row | app:978 | `.exc-chip` |
| Left out of the export. Click to put it back. | tooltip | app:978 | `.exc-chip` |
| Add a note | empty-note button text | app:981 | `.note-text.empty` |
| {first line of note} · Open note for {name} (Untitled when it has none) | button text · aria-label | app:980-981 | `.note-btn` |
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
| Rename… | menu item; opens the Rename dialog (§5.1) | idx:120 | `#bulk-rename` |
| Change note… | menu item; opens the Change note dialog (§5.1) | idx:121 | `#bulk-note` |
| Use note as name | menu item | idx:122 | `#bulk-desc` |
| Exclude · Include | menu items | idx:123-124 | `#bulk-exclude`, `#bulk-include` |
| Clear | link button; clears the selection | idx:125 | `#clear-sel` |

---

## 4. Icon & color popover (one item)

| Text | Kind | Source | Selector |
|---|---|---|---|
| Change icon and color for {name} / Change line for {name} / Change area for {name} ({name}: Untitled when it has none) | dialog aria-label | app:1310 | `#mark-pop` |
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

### 5.1 Rename… and Change note… (the same dialog in text mode, UI-39)

Built in app.js `openTextBulk` / `drawTextFields` / `drawTextBulk` (owner-approved wording,
docs/plans/BULK_RENAME.md section 2 decision 4).

| Text | Kind | Source | Selector |
|---|---|---|---|
| Rename N item(s) / Change the note on N item(s) | dialog heading (no period); names the dialog (`aria-labelledby`) | app `openTextBulk` | `#bulk-title` |
| Close | aria-label of × | app `openTextBulk` | `.bulk-x` |
| Add before · Add after · Find and replace (names); the same plus Replace the note (notes) | mode toggles, in this order | app `TEXT_MODES` | `.mode-tog[data-mode]` |
| Text | field label (Add before, Add after, Replace the note) | app `drawTextFields` | `#bulk-text` |
| Find · Replace with | field labels (Find and replace) | app `drawTextFields` | `#bulk-find`, `#bulk-repl` |
| Match case | toggle (off by default) | app `drawTextFields` | `#bulk-match-case` |
| Now / After | column labels | app `openTextBulk` | `.now-after` |
| {item name} or Untitled | whose note it is, above each note (Change note…) | app `drawTextBulk` | `.na-src .na-name` |
| Untitled | an empty name, Before or After, greyed (display only; stored and exported empty) | app `textCell` | `.is-placeholder` |
| (blank) | a missing note, Before or After | app `textCell` | `.na-before`, `.na-after` |
| No change | row sentence for an unchanged row (in place of its After) | app `textFlag` | `.na-flag` |
| onX imports only the first 512 bytes of a note. About N character(s) will be cut. | row sentence for a note over the limit (the caution's, §3.4) | app `longNoteSentence` | `.na-flag` |
| and N more | under a list cut at 200 rows (the export warning's "and N more", §10) | app `drawTextBulk` | `.na-more` |
| N will change · M unchanged | summary, `aria-live=polite` | app `drawTextBulk` | `#bulk-summary` |
| Cancel · Save | buttons; Save disabled while nothing changes | app `openTextBulk` | `.bulk-cancel`, `#bulk-apply` |
| Changed N item(s). | status after Save (§12.1) | app `applyTextBulk` | `#status` |

An open note on a selected row asks "Save your note?" first (§9). The new part of each After value is
highlighted (`.na-after .hit`, no text of its own).

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
| “{name}” already exists / Move the N item(s) in “{src}” into it? / Cancel · Move them | merge confirm | app:1869-1874 |
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
| Save your note? | Your note for “{name}” (or “Untitled”) hasn't been saved. (on Export, Rename… and Change note…, when the open note changed) | Keep editing, Discard, **Save** | app `askToSaveNote` |
| “{name}” already exists | (merge, §7) | **Cancel**, Move them | app:1869-1874 |
| 1 area will lose its fill / N areas will lose their fill | onX resets area fills to blue on import. | **Keep it / Keep them**, Leave this out / Leave these N out | app:2256-2264 |

## 10. Export screen

| Text | Kind | Source | Selector |
|---|---|---|---|
| Export | kicker | idx:135 | `.kicker` |
| Your files are ready | h1 | idx:136 | — |
| Download all | primary button (`onx_ready.zip`) | idx:138 | `#download` |
| One zip with every folder and instructions.txt | hint | idx:139 | `.done-hint` |
| Back · Start over | buttons | idx:141-142 | `#back`, `.newmap` |
| Import each folder into onX on a computer; onX will use a default datetime stamp for the folder name. Importing needs onX Premium or Elite. | intro | idx:145 | `.rb-intro` |
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
| More has Move to…, Rename…, Change note…, Use note as name, Exclude and Include. Rename… changes many names at once; Change note… does the same for notes. | prose in 3 · Edit in bulk |

## 12. Status line and bridge messages

### 12.1 Status line (setStatus; "ready" lines clear after 8 s, app:35)

| Text | Class | Source |
|---|---|---|
| Reading {name} … / Reading N files… | info | app:360 |
| Couldn't read that file — {reason} / Couldn't read those files — {reason} | err | app:386 |
| Failed: {reason} (engine boot) | err | app:239 |
| Couldn't load the map engine (HTTP N). | err | app:208 |
| Changed N item(s). / line(s). / area(s). (Rename… and Change note…: always item(s)) | ready | app:1541-1542, app `applyTextBulk` |
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
| Import each folder below into onX on a computer (webmap.onxmaps.com), one at a time. / In onX, choose Import and add all of that folder's files together. / Tick "Import map data to a new folder". / onX names the new folder with a datetime stamp. / Rename it to the name shown for that folder below. / Importing needs onX Premium or Elite. | always |
| {NN_Name}/    rename to: {folder name} · {file} · Waypoints / Lines / Areas · {item name} | per folder, file, item |
| (over the length limit; onX will cut this note) · (its hole is not kept: an onX area has one outline) · Untitled (a nameless item) | under an item |

## 14. FAQ and walkthrough headings

FAQ (source docs/FAQ.md; web/faq.html is generated) group headings: The problem, Your files, What Cairn
does, Limits and trade-offs, Round trip. Walkthrough step tags: Before, Step 1, What Cairn finds, What
Cairn flags, What you fix, Your folders, What you import, Good to know. Controls named in their prose:
Default pin, Icon & color…, Save, Download all, + New folder, More → Move to…. FAQ question "Can I rename many items at once?" (answer: "Yes. Tick them, then More → Rename…. Find and replace changes part of each name; Add before and Add after add text to every name.").

---

## 15. Audit of 2026-10-25: what was decided

The owner's answers, by topic (this table, not the numbers used in conversation, is the record):

| Topic | Decision | State |
|---|---|---|
| Apply vs Save | **Save** (DECISIONS UI-16/UI-18 text fixed) | done |
| Exclude vs leave out | **Exclude** in menus, buttons, states; "leave out" where a sentence reads better | rule recorded |
| "Select rows first", "Pin color" | **Select items first**, **Waypoint color** | done |
| "+ New folder…" in Move to… | **+ New folder** (no ellipsis) | done |
| Periods | no period on titles; a period on status sentences ("Changed 3 items.") | done |
| Quotes | “…” around names; straight apostrophes everywhere; **You will**, not You'll | done |
| "Use onX's blue fill" | **Blue** (in the Fill row) | done |
| Error-message prefixes | review every variant together | follow-up (TODO.md) |
| "A name is required…" | names are **optional**: no error, an empty name shows **Untitled** | done |
| "Changes will be lost." vs "This discards N unexported changes." | suggested the counted sentence in both | **open: waiting for the owner** |
| Confirm button order | safe choice first, action last (merge and fill confirms flipped) | done |
| Cancel in "Save your note?" | **Keep editing** | done |
| Nameless items | **Untitled** everywhere; a missing note is blank | done |
| Date stamp | **datetime stamp** | done |
| "Web Map" | removed everywhere; "onX on a computer" where the sentence needs it | done |
| FAQ heading "Default pin / needs attention" | **What's the "Default pin"?** | done |
| GeoJSON errors with /tmp paths | **Failed: Could not load file** | done |
| Arrows in Help ("More → Move to…") | keep: they are directions, not labels | kept |
| Line vs Track | keep (onX-file tracks show "Track") | kept |

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
| Bulk text edits (new, 2026-10-25) | **Rename…**, **Change note…**; modes **Add before**, **Add after**, **Find and replace**, **Replace the note**; fields **Find**, **Replace with**, **Text**; **Match case**; row **No change**; summary **N will change · M unchanged**; an empty result shows **Untitled** | Name can't be empty (names are optional) |
| onX's own objects | **markup**, **onX on a computer** (where importing works), **Premium or Elite**, **Import map data to a new folder** | Web Map (owner, 2026-10-25) |
| Errors | **Couldn't X — reason** | Failed: … |
| Quotes | “…” around names in the app; **straight apostrophes** (') everywhere; straight quotes in instructions.txt | ’ |
| Contractions | write **You will**, not You'll | |
| Date stamp | **datetime stamp** | date and time stamp |
| Sentences | short and direct; no period on titles, a period on status sentences | narrating modals (UI-26) |
| A missing name | **Untitled** (names are optional, owner 2026-10-25) | (no name), Name can't be empty |
| A missing note | nothing: blank space | No note, (none) |
| Confirm buttons | the safe choice first (and default), the action last | |
