# CalTopo ↔ onX: the verified constraint system

Platform facts, researched 2026-08-29. This is the reference the transformation design has to
satisfy. Separated from any proposal so it stays useful when proposals change.

**Sourcing note:** the onX Zendesk help centres return HTTP 403 to direct fetches, so onX facts
below come from search-result extraction, corroborated across the onX Backcountry, onX Hunt, and
onX Offroad help centres (which document the same import subsystem). The CalTopo page fetched
directly and is quoted verbatim.

---

## What CalTopo can export

From [CalTopo Training — Exporting Objects](https://training.caltopo.com/all_users/import-export/export):

| Format | Line/marker style | Folder organization |
|---|---|---|
| **GeoJSON** | ✅ | ✅ — *"a full back-up for CalTopo including line and marker styles, and folder organization"* |
| **KML** | ❌ | ❌ |
| **GPX** | ❌ | ❌ — and you must choose Track vs Route per line at export time |

GeoJSON is the only full-fidelity source. Everything Cairn does depends on that.

## What onX can import

From the onX Backcountry Zendesk (articles 360057195972 and 4446611009165):

- **GeoJSON is not supported.** This is precisely why a converter has to exist.
- **Under 4 MB per file; up to 3,000 markups per import.** Cairn splits at 3.75 MB — correct.
- **KML import is Web-Map-only.** Not available in the mobile app. The app exports GPX only.

### The rule that decides object type

Verbatim from onX's CalTopo-transfer article:

> *"Export Tracks as GPX—exporting as KML will convert them into Lines. Export Lines and Areas as
> KML—exporting as GPX will convert them into Tracks."*

So **the file format you choose determines what the object BECOMES in onX**:

| To get this in onX | Emit | Caveat |
|---|---|---|
| Waypoint | GPX `<wpt>` | — |
| Track | GPX `<trk>` | — |
| Line | KML LineString | Web Map only |
| Area / polygon | KML Polygon | Web Map only |

This means Cairn's `Waypoints.gpx` / `Tracks.gpx` / `Shapes.kml` split is **semantically
required**, not a workaround for the size cap.

### How folders actually work

onX *does* have folders — the earlier assumption that it has no grouping model was wrong. What's
true is narrower: **no file format carries folder assignment.** Folders are created at import
time:

- **Web Map:** a checkbox — *"Import map data to a new folder"* — creating one new folder for the
  whole file.
- **Mobile app:** after import, *"Add to Folder"* → select an existing folder or create a new one.

> **CORRECTED 2026-08-29 (later the same day):** it is **1 import *batch* = 1 onX folder**, and a
> batch may contain **several files at once**. Verified by reading onX's shipped web-app code, not
> its documentation — see "What the source actually says" below. This materially reduces the work.

---

## The collision at the heart of the problem

Two constraints fight each other:

- **Object type is set by file format** (GPX vs KML)
- **Folder membership is set by file boundary** (1 file = 1 folder)

A CalTopo folder holding waypoints + tracks + areas needs **three files** to get the object types
right, but should land in **one** onX folder. That is only achievable by importing them in a
specific order with a specific new-vs-existing choice each time.

### Measured on the real map

`tests/fixtures/bitterroots/Bitterroots__Complete_.json` — 9 folders (plus 43 unfiled items),
68 waypoints, 92 lines, 17 polygons — currently exports to **24 files** (18 `.gpx` + 6 `.kml`).

**~~24 separate imports~~ → 10 import batches.** Because one batch takes multiple files and
mixed formats, the user drags each folder's files in together: 10 folders = 10 batches, not 24
imports. Merging waypoints+tracks into one GPX per folder further cuts 24 files to 16.

Done naively — one file per import, ticking "new folder" each time, which is the obvious reading
of the UI — the user still gets **24 folders instead of 10**, all named `Import 08/29/26 14:07`.

**Cairn produces those 24 files and says nothing about any of this.** No order, no folder names, no
new-vs-existing guidance, no warning about the phone. That is the logical gap: the missing artifact
is not a cleverer encoding, it is the **import plan**.

---

## Open questions

Neither is resolvable from public documentation; both change the design if answered.

1. **How does onX name the new folder?** User-typed, derived from the filename, or generic
   ("Imported Data")? If it is filename-derived, Cairn's filenames are user-facing folder names and
   should read `Lost Horse Canyon`, not `Bitterroots_Complete_copy_Lost_Horse_Canyon_Waypoints`.
2. **Does onX honour native KML `<Folder>` elements?** KML has real hierarchy; GPX has none. If
   onX honours it, a single KML could carry the entire folder structure and collapse 24 imports
   into 1 — but at the cost of turning every Track into a Line, per the format rule above. That
   trade may or may not be worth it, and it is testable in one import.

Both are answerable in about ten minutes by anyone with an onX account, and until then any design
should work under either outcome.

---

## The import plan is cheap to build — the scaffolding already exists

Everything a runbook needs is already computed and already has somewhere to go:

- `cairn/core/writers.py:361,612` — the writers already return
  `(path, size_bytes, written_count)` tuples, and the docstrings literally say
  *"for manifest"*.
- `cairn/tui/app.py:191` — `_export_manifest` already exists, holding
  `(path, kind, count, size)` per written file.
- `cairn/core/icon_registry.py:543` — `write_icon_report_markdown()` already writes a
  per-run markdown report next to the outputs, called from four places.

So the per-file facts, the folder each file came from, and a markdown writer to emit them are all
in place. What's missing is only the *ordering and instruction* layer on top.

**And there is a neat reframe available.** `TODO.md` currently asks to *"Do not create a SUMMARY
file anymore, that was only used for debugging"* — the generated `ICON_REPORT.md` is seen as dead
weight. It shouldn't be deleted; it should be **replaced by the import runbook**. The file that
exists and isn't useful becomes the file that was missing:

```markdown
# Import plan — Bitterroots (9 folders, 24 files)

6 of these must be imported on the onX **Web Map**; KML is not supported in the app.

## 1. Lost Horse Canyon        (8 waypoints, 8 tracks, 2 areas)
   1. Lost_Horse_Canyon_Waypoints.gpx   -> Import, CHECK "Import map data to a new folder",
                                           name it: Lost Horse Canyon
   2. Lost_Horse_Canyon_Tracks.gpx      -> Import, add to EXISTING folder "Lost Horse Canyon"
   3. Lost_Horse_Canyon_Shapes.kml      -> WEB MAP ONLY. Import, add to EXISTING folder
                                           "Lost Horse Canyon"
...
```

That single artifact converts "24 files and good luck" into a checklist, costs no refactor, and
is independent of how the two open questions above resolve.
