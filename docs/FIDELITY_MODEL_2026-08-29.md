# The fidelity model, re-thought — 2026-08-29

A holistic re-evaluation of Cairn's core transformation model: what "preserving the judgement
layer" actually requires, measured against what onX can verifiably hold. This supersedes the
framing that onX "has no grouping model." **It does — we just never found the door.**

Everything below is tiered by evidence quality:

- **[CODE]** — read directly from onX's shipped web-app JavaScript (fetched 2026-08-29 from
  `webmap.onxmaps.com`; chunk filenames cited, content hashes will rotate on their next deploy).
  This is onX's actual behavior, not their documentation's description of it.
- **[HELP]** — onX Zendesk help center, fetched in full via the Zendesk API 2026-08-29
  (the HTML pages 403 behind Cloudflare; `/api/v2/help_center/en-us/articles/<id>.json` does not).
  Vendor intent; usually but not always accurate.
- **[OWNER]** — behavior the project owner observed with a real onX account (repo screenshots,
  code comments describing real exports).
- **[INFER]** — my inference, with the reasoning shown. Each one has a cheap confirmation probe
  in Appendix B.

---

## 1. The discovery that reframes everything

### onX has folders. Import creates them. We verified how, from onX's own code.

**[HELP]** onX Backcountry's My Content has **custom Folders**: flat (no nesting), a markup can
belong to **multiple** folders, folders can be renamed, shared, hidden as a unit, and exported as
a unit. Filtering in the Web Map is by icon **and color**; the app filters by icon; search is
**by name only**. Account limit: *"Your onX account is currently limited to 1,500 Markups."*
— [Editing and organizing Markups](https://onxbackcountry.zendesk.com/hc/en-us/articles/360052239052)
(updated 2026-04-01).

**[HELP]** The Web Map import dialog has a checkbox: *"To create a new Folder for your imported
Markups, click the checkbox next to 'Import map data to a new folder.'"*
— [Importing and Exporting Markups](https://onxbackcountry.zendesk.com/hc/en-us/articles/360057195972).
Limits: GPX/KML only, 4 MB/file, 3,000 markups/import, Premium/Elite required. KML is
Web-Map-only. *"GeoJSON format isn't supported."*
— [CalTopo transfer article](https://onxbackcountry.zendesk.com/hc/en-us/articles/4446611009165).

**[CODE]** I pulled the Web Map's import implementation (webpack chunks
`74948.49185269795af2c4380d.js` — the import card — and `87571.508e26e7268ebf678595.js`,
module `z1zK` — the import executor). Deciphered, the flow is:

```
files  = <input type="file" multiple accept=".gpx,.kml">      // MULTIPLE files per batch
if (newFolderCheckbox)
    collection = addCollection({ name: "Import" + fmt(now, " mm/dd/yy H:MM") })  // ONCE
for each file (parallel):
    POST /v1/markups/import   FormData{ type: "gpx"|"kml", file, collection-id? }  // same id
if (collection is empty after import) delete it
```

Four consequences, each load-bearing:

1. **One import batch = one folder.** The collection is created once per click of "Import" and
   every file in the batch — GPX and KML mixed — gets the same `collection-id`. A CalTopo folder
   that needs both a GPX and a KML can land in **one** onX folder in **one** drag-and-drop.
2. **The folder is named `"Import 08/29/26 14:07"`** — a timestamp. Not the filename, not the GPX
   `<metadata><name>`. Cairn's careful metadata naming (`writers.py:373`) and its careful
   filenames are **both invisible** to onX's folder creation. The user must rename the folder;
   Cairn must tell them what to rename it to.
3. **File parsing happens server-side** (the raw file is POSTed), so file-content questions
   (KML `<Folder>`, GPX `<sym>`) can't be read from client code. But **collection creation is
   client-side only**: the client mints the collection UUID, names it, and passes the id. The
   client also only refreshes its collection list when the checkbox was used — if the server
   created collections from KML `<Folder>` elements, they would not even render without a page
   reload. **[INFER, high confidence]: onX does not honor KML `<Folder>` structure.** The
   flat-collection model and this protocol leave it nowhere to go. (Probe B1 confirms in 5 min.)
4. **Collections are flat and renameable** [CODE: module `H0bz`, `54966.…js`]: objects carry
   `{uuid, name, notes, entities[], type}` — no parent pointer, so no nesting, ever. They also
   carry a **notes** field of their own (unused by import — a free channel if onX ever exposes it).

### onX's own GPX dialect, fully decoded

**[CODE]** Chunks `58175.…js` (togpx/tokml libraries) and `40439.…js` (onX's post-processor)
are the Web Map's *export* pipeline. It explains every quirk in Cairn's fixtures:

| Observation in Cairn's code/fixtures | Now explained by onX's code |
|---|---|
| `<desc>` key=value block (`name=…\nnotes=…\nid=…`) that `onx_gpx.py:parse_onx_desc_kv` parses | togpx's `featureDescription` dumps **all** feature properties as `key=value` lines |
| `xmlns:onx="https://wwww.onxmaps.com/"` — the `wwww` typo `onx_gpx.py:26` guards | Verbatim in onX's source: `t.replace("<gpx",'<gpx xmlns:onx="https://wwww.onxmaps.com/"')` |
| `<onx:color>`, `<onx:icon>`, `<onx:style>`, `<onx:weight>` extensions | Appended per-element: waypoints get `[color, icon]`; tracks `[color, style, weight]` |
| "similar linework can export as `<trk>` vs `<rte>`" (TECH_DETAIILS.md:85) | Deliberate: onX **Tracks** export as `<trk>`; onX **Lines** and **Routes** export as `<rte>` with a `type=Line` kv and a literal `<type>Line</type>` element |
| Areas "often only appear as polygons in KML" | In **GPX**, onX exports an Area as `<rte>` with `type=Area` + extensions `[color, style, weight, fill_color]` — a ring of `rtept`s |
| `weight` values `"2.0"/"4.0"/"6.0"` | onX vocabulary: thin=2.0, normal=4.0, thick=6.0 |
| Real export creator string | `` creator=`onXmaps ${app} web` `` → `onXmaps backcountry web` |

The export dialect exists so onX's own backup/re-import cycle works ([HELP] explicitly suggests
export-then-reimport to manage the 1,500 limit). **[INFER, high confidence]: the import parser
reads this same dialect** — desc kv, `onx:` extensions, and `<rte>`+`type=Area`. Two independent
owner observations support the first two: the repo's before/after screenshots
(`docs/screenshots/bitterroot-subset-final-onx.png` — Cairn-written `onx:icon`/`onx:color`
arriving styled in onX) and the `<desc>` debug-dump bug ("it is what the user actually sees in
onX", `docs/UX_AUDIT_2026-08-29.md` §2.2 — i.e., imported `<desc>` lands **verbatim** as the
markup's Notes; onX does not parse foreign kv into fields). The `<rte type="Area">` piece is
unverified — Probe B2, and the design degrades cleanly if it fails (§5).

### Fixture provenance — who actually wrote what

| File | Claims | Actually |
|---|---|---|
| `tests/fixtures/bitterroots/Bitterroots__Complete_.json` | — | **Real CalTopo export** (CalTopo GeoJSON dialect: `geometry:null` folders, `folderId`, 4-tuple coords) |
| `tests/fixtures/bitterroots/bitterroots_subet.gpx` | `creator="CALTOPO"` | Real CalTopo GPX export — names + coords only, confirming the README's fidelity table |
| `tests/fixtures/onx_export_with_tracks.gpx` | `creator="OnX Backcountry"` | **Synthetic.** Real web exports say `onXmaps backcountry web`, and real desc blocks are kv (`name=…`), not prose. Extension usage is faithful; provenance is not |
| `tests/fixtures/onx_export_with_tracks.kml` | — | **Synthetic.** Contains a KML `<Folder>` — onX's tokml writer never emits `<Folder>`. A real onX KML has flat Placemarks + ExtendedData |
| `tests/fixtures/rattlesnake_test_*.gpx`, `onx_waypoint_color_test.gpx`, `test_sort_*` | `creator="Cairn Test Suite"` | Synthetic, honestly labeled |
| `demo/bitterroots/lost_horse_canyon_gpx.gpx` | `creator="Cairn - CalTopo to OnX Migration Tool"` | Cairn's own output |
| `tests/fixtures/edge_cases/*` | — | Hand-made (per its README) |

The repo has **no genuine onX export file**. The `wwww` namespace and desc-kv parser prove the
owner *has seen* real ones; none was committed. Worth fixing (workplan, W6).

---

## 2. The fidelity model, quantified

### What exists in CalTopo (source alphabet)

Measured on the real map, `tests/fixtures/bitterroots/Bitterroots__Complete_.json`
(189 features):

| Dimension | Values in the wild | Bitterroots usage |
|---|---|---|
| Folder membership | 1 folder or none; folders are **flat** in CalTopo too | 9 folders + **43 unfiled items** (23 markers, 17 lines, 3 polygons) — the "10th folder" is implicit |
| Title | free text | median 16 chars, p90 32, max 47 |
| Description | free text | sparse |
| marker-symbol | CalTopo's set (hundreds) | 45/68 carry a real symbol; 23 are CalTopo's own generic `point` |
| marker-color / stroke | 24-bit hex | effectively 3 used: `#FF0000` (81), `#000000` (22), `#0000FF` (30) |
| stroke-width, pattern | numeric, solid/dash/dot | defaults dominate |
| Geometry class | Marker / LineString / Polygon | 68 / 92 / 17 |

### What onX can hold (channel alphabet)

| Channel | Capacity | Filterable? | Searchable? | Set at import? | Evidence |
|---|---|---|---|---|---|
| **Folder** | flat, effectively unbounded count; item may be in several | groups the list; hide/share/export per folder | by scrolling | **Yes — 1 per import batch**, name forced to `"Import <timestamp>"`, rename after | [CODE] z1zK, [HELP] 360052239052 |
| **Name** | free text | no | **yes — the only searchable field** | yes | [HELP] |
| **Notes** | free text, arrives verbatim from `<desc>` | no | no | yes | [OWNER] desc-dump bug |
| **Color** | **10** waypoint / **11** track | **yes** (web: color+icon; app: icon) | — | yes, via `onx:color` | [HELP], [OWNER] screenshots |
| **Icon** | **95** | **yes** | — | yes, via `onx:icon` | [CODE] vocabulary, [OWNER] |
| **Line style/weight** | solid/dash/dot × 3 weights | no | no | yes, via `onx:style/weight` | [CODE] |
| **Object type** | waypoint/track/line/shape/route | list is grouped by type | — | forced by format: GPX line→Track, KML line→Line, KML poly→Area; onX's own dialect: `<rte>`+`type=` | [HELP] + [CODE] |
| Account ceiling | **1,500 markups total** | — | — | — | [HELP], verbatim |

### Provably unrepresentable (accept and say so)

- **Nothing hierarchical is lost** — CalTopo folders are flat, onX folders are flat. This is a
  clean structural match. The old assumption ("onX has no grouping model") was simply wrong.
- **24-bit color → 10 buckets.** Quantization is inherent; Bitterroots uses 3 colors, so zero
  practical loss here, but a rainbow map degrades.
- **CalTopo symbol set → 95 icons.** The measured floor: 42/68 map cleanly, 23 carry no intent
  to preserve, 3 need one standing decision (`docs/DECISION_SURFACE_2026-08-29.md`).
- **Per-import folder naming.** onX will not take a folder name from any file content. The name
  must transit through the *user's hands*. This is the single hardest constraint in the system.
- **>1,500 markups.** Not a Cairn problem to solve; a Cairn problem to warn about (the
  `many_waypoints_10000.gpx` edge-case fixture describes a map onX cannot hold at all).

### Is "channel capacity" the right reframe? Attack on the brief itself

Mostly right, but incomplete in one decisive way: **the brief's channel list contains only
file-content channels** (name, desc, color, icon, format elements). The verified reality is that
the highest-bandwidth channel — folder assignment — is **not in the file at all**. It rides on
the *import protocol*: which files the user drags together, whether they tick a box, what they
type into a rename dialog. The last hop of this channel is executed by a human.

So the correct model is: **Cairn is designing a transmission, and the user is part of the
codec.** The product artifact that's missing isn't a cleverer byte encoding — it's the
*instruction stream* for the human half of the decoder. That artifact is cheap, needs no onX
cooperation, and no encoding trick below beats it. The reframe survives, amended: *think channel
capacity, but count the protocol channels, not just the file channels.*

---

## 3. Encoding strategies, compared honestly

Scored against: survives import → visible as *grouping* in onX → filterable → reversible on
round-trip → graceful degradation → visual noise cost.

| Strategy | Survives | Groups in onX | Filterable | Reversible | Degrades | Noise | Verdict |
|---|---|---|---|---|---|---|---|
| **A. File-per-folder, no guidance** (today) | file yes, grouping **no** — dies at the picker | no | no | no | — | none | Grouping exists only in filenames the user never sees again |
| **B. Batch-per-folder + runbook + rename list** | **yes** | **yes — real folders** | folder-scoped browse; hide/share/export per folder | yes (with C) | if user skips steps → status quo A | none in-map | **Primary. The only scheme yielding real onX folders** |
| **C. `folder=` line in `<desc>`** | yes — lands verbatim in Notes | no | no | **yes — machine-readable on re-export** | always works | one line in every Notes field | **Secondary. The reversibility + recovery layer** |
| D. Name prefix `[LHC] Camp spot` | yes | sorts adjacently; searchable per group | no | yes (parse+strip) | works | **high — every name, every label, forever** | Rejected as default; offer as opt-in for app-only users |
| E. Color = folder | yes | color-sort groups | **yes** | only via sidecar | works | **destroys semantic color** (blue=water becomes blue=folder 2) | Rejected as default; §4 |
| F. Icon = folder | yes | icon-sort groups | yes | only via sidecar | works | destroys the 42/68 icons that carry meaning | Rejected outright — icons are the highest-value semantic channel |
| G. KML `<Folder>` elements | file imports; folders don't | no | no | no | — | none | Dead: [INFER-high] flat collection model + client-only creation. Probe B1 |
| H. GPX `<sym>`/`<cmt>`/`<type>` | unknown server-side | no | — | — | — | none | onX's own dialect uses none of them for grouping; not worth betting on. `<type>` **is** used — but for object type (Line/Area), not grouping |

**The composite design: B + C, with D and E as explicit user policies, never defaults.**

---

## 4. The semantic-vs-structural collision, head on

Color and icon are the only *filterable* axes, and they already carry meaning: the project's own
thesis waypoint is "blue = water." Spending them on folder identity overwrites judgement with
bookkeeping — the exact inversion of Cairn's purpose.

The discovery that folders are real **dissolves most of this tension**: structure rides the
folder channel, semantics keep color and icon. That is the principled allocation, and it is the
default.

What remains is a genuine *user choice*, not a design failure, in two situations:

1. **App-first users.** The mobile app filters by icon only (no color filter [HELP]); folders
   exist in the app too, so structure still doesn't need color. No collision.
2. **Users who want at-a-glance folder identity on the map canvas** (all of Lost Horse glows
   red). That is legitimately what color-as-group buys, and nothing else buys it.

So: a **policy flag**, `--group-encoding`:

- `folders` (default): folders = structure; color/icon = semantics, exactly as mapped today.
- `color`: assign each folder a color from the 10-slot palette (largest folders first; >10
  folders → the smallest share an "overflow" color and Cairn says so). Semantic colors are
  overridden **with a printed diff** ("3 water waypoints lose blue → folder color"), and the
  original semantic color is recorded in the `folder=`/`color=` desc lines so it is restorable.
- `prefix`: name prefixes for people who live in search. Same reversibility rule: what the
  encoder adds, the decoder (Cairn, on round-trip) must strip.

Quantified check on the default against real data: Bitterroots' 9 folders + unfiled all fit the
folder channel with zero color/icon spend. Its 3 source colors (red/black/blue) map losslessly
into onX's 10. The collision is real only under `color` policy with >10 folders — and Cairn can
compute and report exactly that before export.

---

## 5. The concrete design

### 5.1 Output layout (replaces the flat pile of files)

```
onx_ready/
  RUNBOOK.md                     ← also rendered to terminal at export end
  01_Lost_Horse_Canyon/
     Lost_Horse_Canyon.gpx       ← waypoints + tracks merged (one file, one folder, why not)
     Lost_Horse_Canyon_Areas.kml ← only if the folder has polygons
  02_Lost_Trail_Pass/
     ...
  10_Unfiled/                    ← the 43 items with folderId == null get a real home
     Unfiled.gpx
```

Waypoints and tracks merge into one GPX per folder: both are GPX-representable, and the
historical reason to split them ("so they can be imported separately", README) is obsolete —
files that should land together should *ship* together. Measured on Bitterroots:

| Packaging | Files | Import batches |
|---|---|---|
| Today (wp/trk/kml split, flat dir, no guidance) | 24 | user doesn't know batches exist |
| Merged GPX + KML areas, dir-per-folder | **16** | **10** |
| Single GPX per folder (Areas as `<rte type="Area">`, if Probe B2 passes) | **10** | 10 |

Size splitting (`--max-gpx-mb`) is unchanged; `_Part2` files stay in the same directory and the
same batch — parts of one folder never change the batch count.

### 5.2 The runbook (the missing artifact)

Generated per export, one numbered step per folder, written for a non-developer:

```
Import checklist — Bitterroots (Complete)          10 folders → 10 imports, ~15 min
Prereqs: onX Premium/Elite; use webmap.onxmaps.com on a computer
         (KML files and folder creation are web-only).

□ 1. Lost Horse Canyon  (18 items, 2 files)
     • My Content → Import → drag BOTH files from 01_Lost_Horse_Canyon/
     • Tick "Import map data to a new folder" → Import
     • The new folder appears at the TOP of My Content named "Import <today's date>".
       Rename it now:  Lost Horse Canyon
□ 2. ...
After all steps: My Content should show 10 folders / 177 markups. If a folder is
missing items, re-import just that folder's files into it ("Add to existing" is not
needed — onX skips nothing, so delete the folder and redo the one batch).
```

Design rules baked in: rename **immediately** after each batch (two un-renamed
"Import 08/29/26 …" folders are ambiguous); the newest collection sorts to the top
[CODE: `_sortByUpdatedDesc`], so "top of the list" is a reliable pointer; never hardcode the
timestamp format in instructions (onX may change it); warn up front when total markups + import
would exceed 1,500.

### 5.3 In-band layer: the `folder=` desc line

Appended as the **last line** of `<desc>`, in onX's own kv grammar:

```xml
<desc>Fill up here before the ridge — last water for 6mi
folder=Lost Horse Canyon</desc>
```

- In onX it reads as one trailing line in Notes — visible but honest (it *is* information about
  the waypoint).
- On onX → Cairn round-trip it comes back verbatim inside `notes` (togpx dumps all properties
  [CODE]); `parse_onx_desc_kv` already handles kv-with-continuations — add `"folder"` to
  `_DESC_KV_KEYS` (`cairn/io/onx_gpx.py:33-43`) and `read_onx_gpx` can rebuild real folders
  instead of today's hardcoded `OnX Import/Waypoints|Tracks` scaffold (`onx_gpx.py:157-160`).
- Under `--group-encoding color|prefix`, the same block records the *displaced* semantics
  (`color=rgba(8,122,255,1)` original), keeping every policy reversible.
- Opt-out: `--no-folder-tags`. Debug mode keeps its full dump.

This makes **round-trip folder recovery automatic and user-effort-free**, independent of whether
the user ever renames anything in onX — the two layers are redundant by design: B carries the
structure into onX's UI; C carries it back out of onX's files.

### 5.4 The Areas-as-GPX probe (opportunistic upgrade)

If onX's import accepts its own export dialect for areas (`<rte>` + desc `type=Area` +
`onx:fill_color` — Probe B2), every folder becomes a single GPX and KML disappears from the
CalTopo→onX direction entirely. Until proven, the KML path stays the default and the probe file
ships in the export directory as `_probe_area.gpx` (2 tiny markups, documented in the runbook as
optional: "import this into a scratch folder; tell us / set `areas_as_gpx: true` if a filled
area appears"). Cost of being wrong: two junk markups in a scratch folder, deleted in one tap.

### 5.5 Algorithm, end to end

```
INPUT   MapDocument (folders[], items[], each item: folder_id|None, name, notes,
        style{icon,color,...}, geometry), config, policy{group_encoding, folder_tags,
        areas_as_gpx, max_gpx_mb}

1  PARTITION  groups = items by folder_id; None → synthetic folder "Unfiled"
              (name collision with a real folder → "Unfiled (2)")
2  ORDER      groups by descending item count (big folders first — the user quits late,
              not early); assign 01..NN prefixes
3  ENCODE     per item: icon/color via existing mapper; then policy:
                folders → nothing extra
                color   → folder_color = palette[rank]; record displaced color in kv
                prefix  → name = "[abbrev] " + name; abbrev = unique 2-4 char code, table
                          printed in runbook
              if folder_tags: desc += "\nfolder=<folder name>"   (after user notes)
4  PACKAGE    per group, into out_dir/NN_<safe_name>/:
                waypoints+tracks → <safe_name>.gpx   (split by max_gpx_mb → _PartK)
                polygons         → areas_as_gpx ? same gpx as <rte>+type=Area+fill_color
                                                 : <safe_name>_Areas.kml
5  VERIFY     every emitted onx:icon ∈ canonical 95 (closes the "Cabin" bug class);
              every color ∈ the 10/11; total markups ≤ 3000/file, files ≤ 4MB;
              warn if Σ markups > 1500 (account ceiling) or > remaining capacity if known
6  RUNBOOK    emit RUNBOOK.md + terminal rendering: per-group step (file list, item count,
              tick-box, exact rename string), prereqs, ceiling warnings, verification line
              ("onX should now show N folders / M markups")

FALLBACKS  user skips all runbook steps → items still import styled (status quo, plus
           notes carry folder=); Basic member → runbook's first line says imports need
           Premium/Elite before they burn time; >10 folders under color policy →
           overflow color + printed table; app-only user → runbook variant: GPX files
           importable one-per-batch in app, folder assignment via app "Add to Folder"
           after each import, KML/areas web-only.
```

### 5.6 Round-trip integrity (onX → CalTopo)

- Real onX exports carry `name/notes/id/color/icon/style/weight/type` in desc kv +
  `onx:` extensions [CODE] — Cairn already reads these (`onx_gpx.py`, `onx_kml.py`).
- **Folder identity does not exist in onX's export files** (web filenames are
  `onx-markups-<date>.gpx` [CODE]; content has no folder field). Three recovery paths, best
  first: (1) `folder=` kv from §5.3 — automatic for anything Cairn originally exported;
  (2) per-folder export files (app folder-export or web select-by-folder) — Cairn should accept
  a *directory* of onX exports and offer file→folder mapping with the filename as the suggested
  name; (3) nothing — land in "onX Import" as today.
- New lossiness introduced: an onX markup in **multiple** folders can only occupy one CalTopo
  folder. Rule: first folder tag wins, remainder recorded as `folders_other=` in the CalTopo
  description. Symmetric caveat documented.
- `<rte>` handling gains the type dispatch onX itself uses: `type=Area` → Shape (ring),
  `type=Line` → Track/Line, plain `<rte>` → route — this also fixes the existing
  "polygons often only appear in KML" asymmetry when Probe B2 lands.

---

## 6. Red team

*Written after drafting §§1–5, attacking it as an adversary. Revisions follow each attack and
are folded back into the design above where marked.*

**R1 — "The runbook is just outsourced labor. Ten manual imports, ten renames — you moved the
gap into a checklist and called it design."**
Partly true and worth saying plainly: the rename step exists because onX gives file content no
say in folder naming — that is a hard wall, not a Cairn failure. The honest comparison is
against alternatives: today = the same ten imports *plus* zero folders *plus* no instructions;
one-batch-import = one import, one folder, structure gone. Ten folders cost ten batches in
*every possible design*; the runbook is the minimum-labor path to them, ~90 seconds per folder.
**Revision adopted:** (a) big-folders-first ordering so early abandonment loses least (§5.5
step 2); (b) a `--single-folder` mode for users who decide the structure isn't worth ten
minutes — one batch, one folder, `folder=` tags still present so the structure is recoverable
later; (c) the runbook states its own total cost up front ("10 imports, ~15 min") so the user
chooses informed, instead of discovering the cost at step 7.

**R2 — "Scheme fitted to the fixture. 9 folders is cute; 30 folders is 30 imports, and 500
waypoints in one folder breaks something else."**
Checked at the limits: 500 waypoints ≈ 100 KB of GPX — one file, one batch, fine (4 MB and
3,000/import are far away; the binding constraint is onX's **1,500-markup account ceiling**,
which kills the import regardless of encoding — Cairn must warn, §5.5 step 5, W2). Thirty
folders → thirty batches is real pain with no workaround inside onX's protocol. **Revision
adopted:** `--consolidate-below N` merges folders with fewer than N items into a `Misc` batch
(each item keeps its true `folder=` tag, so consolidation is reversible later); the runbook
already showed per-folder counts, which is the information needed to choose N. At Bitterroots
scale nothing consolidates; at 30-folders scale the user decides where the labor/structure
trade sits. Attack partially stands: **above ~15 folders this design degrades from "smooth" to
"tedious but possible," and no file format changes that.**

**R3 — "Your two central bets — desc→Notes verbatim, and one-collection-per-batch — are a bug
report and minified JS. onX changes either, silently, next Tuesday."**
Fair on fragility, wrong on footing: one-collection-per-batch is read from the *currently
shipped* client, which is strictly better evidence than any help article; desc→Notes is
owner-observed in production. But both are unowned behaviors. **Revision adopted:** the runbook
carries a per-step verification line ("the new folder appears at the top — if no folder
appeared, the checkbox didn't take") so a behavior change fails *loudly at step 1*, not
silently at step 10; and W6 adds a `docs/ONX_BEHAVIOR.md` ledger recording each dependency,
its evidence tier, and its last-confirmed date, so future breakage has a diff target. The
`folder=` layer is deliberately unaffected by any protocol change — that redundancy is the
hedge, not an accident.

**R4 — "`folder=Lost Horse Canyon` in every Notes field is the desc-debug-dump bug you just
fixed, re-shipped with better branding."**
The sharpest attack here, because the project's own TODO celebrates removing kv noise from
`<desc>`. Differences that matter: one line, not five; information the *user* recognizes as
theirs (their folder name), not UUIDs and rgba strings; and load-bearing (it is the only
channel that survives an onX round trip). But the attack lands on defaults: some users will
still see it as clutter on every single waypoint. **Revision adopted:** keep it default-on
*because silent structure loss is the worse default*, but (a) put it after a blank line, last,
so the user's own note reads first; (b) `--no-folder-tags` opt-out surfaced in the export
summary, not buried in `--help`; (c) never write it when the item has no folder (the Unfiled
group gets no tag — absence of a tag *is* the encoding).

**R5 — "Areas-as-GPX is an unverified fantasy that could ship broken imports."**
Correct as charged, which is why it's not in the default path: KML remains the shipped
behavior; the `<rte type="Area">` writer activates only behind `areas_as_gpx: true`, and the
probe artifact is opt-in and self-cleaning (§5.4). Cost of the bet failing: one config flag
nobody turns on. Cost of not trying: a permanent extra file + web-only import for 5 of 10
Bitterroots folders. Bet stays, fenced. Which branch would I bet on? **Pass** — onX built that
dialect precisely so its own exports re-import; a parser that writes `type=Area` and can't read
it would break onX's advertised backup loop.

**R6 — "Multi-membership: CalTopo item in one folder, onX markup in many. Your round trip
invents data or drops it."**
It drops it, knowingly: first tag wins, others preserved as text (`folders_other=`), asymmetry
documented (§5.6). Inventing CalTopo structure (duplicating the item into both folders) would
create the duplicate-explosion problem the dedup machinery exists to fight. No revision;
recorded as an accepted, visible loss.

**R7 — "What can't the user undo?"**
Walked the full flow: a botched import → delete the folder (markups too, if selected) and redo
one batch — recoverable, and the runbook now says so explicitly (§5.2 footer, revision from
this attack). Renames — trivially undoable. `folder=` tags — strippable by re-running Cairn
(W5 adds a `strip-tags` utility for files already generated). The one genuinely sticky case:
`--group-encoding color` *after* import, where original semantic colors exist only in the desc
kv record — restoring them means editing markups one-by-one in onX or re-importing. **Revision
adopted:** `color` policy prints a red warning that it is effectively one-way inside onX, and
requires interactive confirmation.

**R8 — "You never verified GPX `<sym>`, and you dismissed it in one row."**
Guilty, with cause: onX's own dialect ignores `<sym>` in both directions [CODE], so even if the
server tolerates it, betting styling on an element onX's writer doesn't use means betting on
undocumented tolerance instead of observed symmetry. `onx:icon` is observed working [OWNER].
Probe B3 exists for completeness; nothing in the design depends on its outcome.

---

## 7. Workplan

Sequenced; each step lands independently. "Offline-verifiable" = provable with tests against
fixtures, no onX account.

| # | Work | Verifiable how |
|---|---|---|
| **W1** | **Packaging change**: dir-per-folder, merged waypoints+tracks GPX, `NN_` ordering, Unfiled group (touches `core/preview.py:1490-1560`, `core/writers.py`, `tui/app.py:3490-3545`) | Offline: golden-file tests on Bitterroots — 10 dirs, 16 files, every item present exactly once |
| **W2** | **RUNBOOK.md generator** + terminal rendering + ceiling warnings (1,500 / 3,000 / 4 MB) | Offline: snapshot test; counts must reconcile with W1 output |
| **W3** | **`folder=` desc line** (writer) + `"folder"` in `_DESC_KV_KEYS` + folder reconstruction in `read_onx_gpx`/`read_onx_kml` (reader) | Offline: property test — export→re-import round-trips folder structure bit-perfectly through Cairn's own dialect |
| **W4** | **Policy flags**: `--group-encoding folders\|color\|prefix`, `--single-folder`, `--consolidate-below N`, `--no-folder-tags`; color-policy confirmation gate | Offline: unit tests incl. >10-folder overflow and displaced-semantics recording |
| **W5** | onX→CalTopo: directory-of-exports intake with file→folder mapping; multi-folder `folders_other=`; `strip-tags` utility | Offline against synthetic onX-dialect fixtures |
| **W6** | Evidence upkeep: commit one **real** onX GPX + KML export as fixtures (replacing the pseudo-real ones); create `docs/ONX_BEHAVIOR.md` dependency ledger | Needs one real export (owner, 5 min) |
| **W7** | Probe pack: `_probe_area.gpx` + `_probe_kml_folder.kml` generation and the config plumbing for `areas_as_gpx` | Offline to build; Appendix B to confirm |
| **W8** | `<rte>` type dispatch on the read path (`type=Area`→Shape, `type=Line`→Line) — correct regardless of B2's outcome, since real onX exports already contain these | Offline once W6's real fixtures exist |

Deliberately *not* in the plan: any use of KML `<Folder>` (dead, §3.G), color-as-group as a
default (§4), and any attempt to name onX folders from file content (impossible, §1).

## Appendix A — Primary evidence index

- onX import card UI: `webmap.onxmaps.com/74948.49185269795af2c4380d.js` (multi-file input,
  4 MB check `size>4096e3`, checkbox wiring) — fetched 2026-08-29
- onX import executor: `.../87571.508e26e7268ebf678595.js` module `z1zK`
  (`addCollection({name:"Import"+date})`, shared `collection-id`, `POST /v1/markups/import`,
  empty-collection cleanup)
- onX collections service: `.../54966.23f9146ba05879b1904b.js` module `H0bz` (flat schema,
  rename/notes, `_sortByUpdatedDesc`, 1,000-entity POST chunking)
- onX export pipeline: `.../58175.64658723954c9057d989.js` (togpx/tokml) +
  `.../40439.24fef7c09402d2f95f1e.js` (desc kv, `onx:` extensions, `wwww` namespace,
  `<rte>`+`type=Line|Area`+`fill_color`, weight map, creator string)
- Help center (Zendesk API, all fetched 2026-08-29): articles 360052239052 (folders, filters,
  1,500 limit), 360057195972 (import/export, checkbox), 4446611009165 (CalTopo transfer, format
  →type rules, "GeoJSON isn't supported"), 5022588722317 (import errors), 4402358311053
  (performance), 5013855682445 (markup options); onX Hunt 115002196452 + 360035518051 and
  onX Offroad 360057279192 corroborate identical behavior across products
- CalTopo export: https://training.caltopo.com/all_users/import-export/export (GeoJSON = only
  full-fidelity export incl. folders; GPX/KML lose styles + folders)
- Comparative note: Gaia GPS *does* name import folders after the file
  (https://help.gaiagps.com/hc/en-us/articles/360052763513) — evidence such UX is buildable;
  onX simply didn't
- Repo: `cairn/io/onx_gpx.py:26,33-43,157-160` · `cairn/io/onx_kml.py:1-12` ·
  `cairn/core/writers.py:373` · `cairn/core/preview.py:1490-1560` · `cairn/tui/app.py:3490-3545`
  · `TECH_DETAIILS.md:8,65-79,85` · `docs/DECISION_SURFACE_2026-08-29.md` ·
  `docs/UX_AUDIT_2026-08-29.md`

## Appendix B — Residual owner probes (confirmations, not dependencies)

The design works under either outcome of each; these convert [INFER] rows to [OWNER] rows in
the W6 ledger. Total: ~15 minutes with a Premium account.

1. **B1 (5 min):** import a 3-waypoint KML containing two nested `<Folder>` elements, checkbox
   *off*. Expected: waypoints appear, zero folders created → confirms §3.G.
2. **B2 (5 min):** import `_probe_area.gpx` (a `<rte>` with desc `type=Area` +
   `onx:fill_color`). Filled polygon appears → set `areas_as_gpx: true` (§5.4); a stray track
   appears → delete it, KML path stays default.
3. **B3 (3 min):** import one waypoint with `<sym>Campground</sym>` and no `onx:icon`.
   Icon appears → free bonus channel for foreign GPX; default pin → confirms §6.R8.
4. **B4 (2 min):** one batch, two files, checkbox on. Both files' markups in one folder →
   confirms the §1 protocol readout end-to-end on the server side.
