# onX round trip: markup identity at the data level

Run **id1**, 2026-10-23, the owner's onX Backcountry account (Web Map), 13:58–14:10 UTC.
Raw files: `tests/fixtures/roundtrip/id1/` (gitignored, kept locally; sha256 below).
Earlier rounds: `tests/fixtures/roundtrip/r1/`, `r2/`, `docs/ONX_TESTING.md`,
`docs/research/ONX_REIMPORT_AND_SHARING_2026-10-22.md` §1.

## 1. Answer

**An import into onX always creates new markups with new uuids. onX does not read the onX id
in a GPX or a KML file, and an import did not change any existing markup.** This holds even
when the file carries the exact uuids of markups that exist in the account. id1 checked it
four ways:

1. **The originals' re-export is unchanged.** The KML is byte-identical (same sha256). The
   GPX differs only in `<trkpt><time>`, which onX stamps with the time of the export.
2. **onX's API has the same record for each original after all three imports.** The
   waypoint's and the area's records are identical field for field, including `updated_at`.
   The line's `updated_at` still equals its `created_at`.
3. **Account-wide, no existing waypoint, area or line changed.** The API lists from before
   and after the run differ only by the 9 new id1 markups.
4. **The importer reads none of the id fields.** In the same-id GPX (V2), onX stored the
   whole `<desc>` as the note, `id=<original uuid>` line included, and gave each markup a
   new uuid. In the same-id KML (V2k), onX ignored `<ExtendedData>` completely: the notes are
   empty and the colours and icon are onX's defaults.

Confidence: **high for onX's behaviour on 2026-10-23**. §10 lists the limits.

## 2. Scope and questions

| # | Question | Answered in |
|---|---|---|
| Q1 | What was attempted (r1, r2, id1)? | §3, §4 |
| Q2 | Which elements and attributes in onX's GPX and KML exports could carry identity? | §6 |
| Q3 | Exactly how did Cairn change the data? | §5, §7 (V1) |
| Q4 | Exactly what was sent back to onX? | §5, §9.1 |
| Q5 | Is it proved that a re-import creates a new markup and does not overwrite or update the existing one? Can that safely be assumed? | §8, §9, §10 |
| Q6 | Should Cairn strip onX ids on export, and does it already? | §11 |

Icons and colours appear below only where they show which code path onX used.

## 3. What r1 and r2 proved about identity, and the gap

r1 and r2 (2026-10-22) each ran two stages: **i1** (CalTopo → Cairn → onX) and **i2** (onX
export → Cairn edits → onX, imported into new folders). Their verify step matched items by
(kind, name) and compared names, notes, icons, colours, styles and points.

| Claim | Evidence in r1/r2 | Verdict |
|---|---|---|
| i2 created new markups | The i2 export's uuids differ from the i1 export's. Example, r1 random-kml: i1 waypoint `blerg` = `531b7bfe-…`, i2 = a new uuid among `81c60b5d…`, `b0bdc197…`, … | Proven. But it is **not an id test**: see the next row |
| The i2 upload files carried onX ids | **No.** `grep 'id='` over every i2 upload file finds nothing. Cairn writes only the note into `<desc>` (`cairn/core/writers.py:_desc_text`) and no id into KML. The i2 uploads were id-free, so onX had nothing to match on | The gap: i2 never tested id matching |
| The i1 originals were still present and unchanged after i2 | **Never checked.** Nothing re-exported an i1 folder after its i2 import | Gap. Closed after the fact by id1 (next row) |
| (Retrospective, from id1's API capture) The i1 originals were untouched by i2 | On 2026-10-23, every `[r1i1]`, `[r1i2]`, `[r2i1]` and `[r2i2]` waypoint and area in the account has `updated_at == created_at` (waypoints `[r1i1]` 49, `[r1i2]` 49, `[r2i1]` 47, `[r2i2]` 36; areas 3 per tag). So do the 27 `[r1i1]` and 18 `[r1i2]` tracks on the first page of the track list, the only page checked. The uneven counts were not investigated | Cairn's i2 import did not modify the i1 markups. It still says nothing about ids, because i2 carried none |
| Re-importing an onX export **with** ids duplicates it | Research §1.7: one unchanged onX GPX (2 waypoints, `id=` present) re-imported, giving +2 markups | Proves only that ids do not prevent creation. It did not re-export the originals, edit the file, or try KML. `ONX_TESTING.md`'s "ids ignored" ran ahead of this evidence |

So before id1 the open questions were: (a) does an edited file that keeps the same ids update
the originals? (b) does the KML `<Data name="id">` path behave like GPX? (c) did any import
modify an original at all?

## 4. id1 design

One waypoint, one line and one area: `[id1] ZZTEST Alpha` (waypoint), `[id1] ZZTEST Bravo`
(line, written as a GPX `<trk>`) and `[id1] ZZTEST Charlie` (area, written as a GPX
`<rte><type>Area`). They sit in a ZZTEST-only spot near Mt Adams, WA.

| Stage | Action | onX folder (renamed from `Import mm/dd/yy H:MM`) |
|---|---|---|
| a | Import the originals, then export the folder as GPX and KML | `ZZTEST · id1 · originals` |
| b-V1 | Cairn's normal path: the onX GPX+KML export goes through `web/bridge.py` (`load_files`, `apply_edits`, `export_zip`), which renames each item to `… · V1` and recolours it | — |
| b-V2 | Adversarial: onX's own GPX export, byte for byte, except `<name>` and the `name=` desc line get ` · V2`. Every `id=` is left in | — |
| b-V2k | The same with onX's KML export: `<name>` and `<Data name="name">` get ` · V2k`. Every `<Data name="id">` is left in | — |
| c | Import V1, V2 and V2k, each with "Import map data to a new folder" ticked | `… · v1 cairn`, `… · v2 same-ids gpx`, `… · v2k same-ids kml` |
| d | Re-export the originals folder (GPX and KML) and each new folder (GPX) | — |
| e | Read-only: the Web Map's own API traffic, through Chrome DevTools | — |

The rename suffix makes an overwrite visible: if onX had matched on id, an original's name
would have become `… · V2`.

**Method notes.** Claude in Chrome was not available in this session. The Web Map was driven
through the chrome-devtools MCP attached to the owner's Chrome, already logged in (no
credentials entered). Claude's only changes in onX were 4 imports and 4 renames of the
folders those imports had just created (ONX_TESTING rule 3). Claude sent no API request of
its own. The page itself issued its usual `PUT /v1/preferences` and
`PUT /layer-management/v1/layer-settings` on load. API bodies were saved from requests the
page had already made. Each download was taken only if it was under 3 minutes old and was
moved out of `~/Downloads` at once.

## 5. Stages

All files are under `tests/fixtures/roundtrip/id1/`.

| Stage | File | Source | sha256 | What changed |
|---|---|---|---|---|
| a0 | `a_originals/id1_originals.gpx` (1411 B) | Hand-written in Cairn's GPX dialect | `be84e937e5fbc070c12380c194007502bcbffd49f4906a5a350867dc831a1115` | None. No id anywhere |
| a1 | `a_originals/a1_export_originals.gpx` (1938 B) | onX export of `originals`, 13:59:58Z | `2a9bd0ed6d9e4360521ad8e2a122b14249563e8cf7d32b664050356853c664cd` | onX added `id=` / `name=` / `notes=` desc blocks, `<trkpt><ele>0</ele><time>`, and its default area `fill_color` |
| a1k | `a_originals/a1_export_originals.kml` (1780 B) | onX export of `originals`, KML | `f54809d5d684b2456978012b201859d89608993c4f582d1a68d8991cd6ad6c05` | `<Data name="id">` per Placemark; waypoint `ele` filled from a DEM (3680.55) |
| b-V1 | `b_v1/…_Waypoints.gpx` (501 B), `…_Tracks.gpx` (1029 B), `…_Areas.gpx` (710 B) | Cairn `web/bridge.py` on a1 + a1k | Waypoints `136c3ab3088ae96222bc791a4c019df13a1ae209a872f9b7fc5b1a8af0d4e237`; Tracks `b6ff5bff93352322e9b3805c741adea27ac1ee2d50f2d817c01deafdf04d2208`; Areas `8b733a4c3c0b29842e9c250585d0962588f21c8759c95e9a4b6b4e94e37cba4e` | Names `+ · V1`; colours changed (waypoint `rgba(128,0,128,1)`, line and area `rgba(255,0,255,1)`). **All ids dropped**: Cairn rebuilt `<desc>` as the note only. Track `<time>` values kept from a1 |
| b-V2 | `b_v2/id1_v2_same_ids.gpx` (1974 B) | a1 with 6 string replacements | `98d9d08fa0d66ecbe7ce7716031ba7b668396588c9a578589155cab2899069a3` | `<name>` and `name=` only. **All three `id=` uuids unchanged** |
| b-V2k | `b_v2/id1_v2k_same_ids.kml` (1822 B) | a1k with 6 string replacements | `09cfbb13e42872ede9b11c27d40739c9a4064935fe69d7db0e2fc4d53af289f4` | `<name>` and `<Data name="name">` only. **All three `<Data name="id">` unchanged** |
| d1 | `d_reexport/d1_originals.gpx` (1938 B) | onX re-export of `originals`, 14:07:28Z, after all imports | `1e7e3855ea699f350f7c0a0300b8bcd1e1e4d82652271bb842968f0eab93a119` | Only `<trkpt><time>` differs from a1 (§8.1) |
| d1k | `d_reexport/d1_originals.kml` (1780 B) | The same, KML | `f54809d5d684b2456978012b201859d89608993c4f582d1a68d8991cd6ad6c05` | **Byte-identical to a1k** |
| d2 | `d_reexport/d2_v1_cairn.gpx` (1976 B) | onX export of `v1 cairn` | `fe92470f50bd7c0c15d4766e2f28080c67eb60e9ed97a90b7cdf35dcccb0afee` | 3 new uuids |
| d3 | `d_reexport/d3_v2_same_ids_gpx.gpx` (2366 B) | onX export of `v2 same-ids gpx` | `64a08ced939311f88cad69ce028f43dc2b96de1b827a61651cd2637aae21e98a` | 3 new uuids. The old uuid survives only as text inside the note |
| d4 | `d_reexport/d4_v2k_same_ids_kml.gpx` (1679 B) | onX export of `v2k same-ids kml` | `120bf6d84d06542b8ca7a133edb92233f3b140314d81ac2f81586956465f8af8` | 3 new uuids. Notes empty; defaults for icon and colour; the line is a `Line` (`<rte><type>Line`), not a Track |
| e | `net_id1/*.json` | Saved Web Map API responses, filtered to id1 records (the full responses hold the whole account and were not kept) | — | §9 |

## 6. Where identity could live in onX's exports (inventory, a1 / a1k)

**GPX** (`creator="onXmaps backcountry web"`, one line, no XML declaration):

| Element / attribute | Present? | Identity role |
|---|---|---|
| `<metadata/>` | Empty | No folder name, folder uuid, export time or account |
| `<wpt>` / `<trk>` / `<rte>` attributes | Only `lat`/`lon` on points | No `id` attribute anywhere |
| `<name>` | Yes | Display name only |
| `<desc>` | `name=` / `notes=` / **`id=<markup uuid>`** / `color=` / `icon=` (waypoint), `style=` / `weight=` (track), `type=Area` / `fill_color=` (area) | **The only markup id in the file**, as free text |
| `<type>` on `<rte>` | `Area` (or `Line` for a drawn line) | Kind, not identity |
| `<extensions>` | `onx:color`, `onx:icon` (wpt), `onx:style`, `onx:weight`, `onx:fill_color` | Styling. No `onx:id` |
| `<trkpt><time>` | Every point | When the track has no stored point times, all points get the **time of the export** (a1 `13:59:58.486Z`, d1 `14:07:28.603Z`). Stored times come back as stored (d2, d3) |
| `<trkpt><ele>` | `0` | — |
| `<wpt><time>`, `<cmt>`, `<src>`, `<link>`, `<number>` | Absent | — |

**KML** (one `<Document>`, no `<name>`, no `<Folder>`):

| Element / attribute | Present? | Identity role |
|---|---|---|
| `Placemark@id`, `<styleUrl>`, `<Style>`, `<TimeStamp>` | Absent | — |
| `<ExtendedData><Data name="id">` | Yes, the same uuid as GPX `id=` | **The only markup id in the file** |
| Other `<Data>` | `name`, `notes`, `color`, `icon` / `style`, `weight` / `type`, `fill_color` | Styling and content |
| `Point` coordinates | Third value = DEM elevation (`3680.550048828`) | — |

Neither format carries the folder's uuid. An export cannot point back at its folder.

## 7. Verbatim excerpts per stage

### 7.1 Waypoint

a0, uploaded (Cairn dialect):
```xml
<wpt lat="46.2052" lon="-121.4911">
  <name>[id1] ZZTEST Alpha</name>
  <desc>id1 original waypoint</desc>
  <extensions><onx:icon>Summit</onx:icon><onx:color>rgba(255,51,0,1)</onx:color></extensions>
</wpt>
```
a1, onX's GPX export (and d1, unchanged):
```xml
<wpt lat="46.2052" lon="-121.4911"><name>[id1] ZZTEST Alpha</name><desc>name=[id1] ZZTEST Alpha
notes=id1 original waypoint
id=ec19268b-31fc-4e51-9615-d361194f8503
color=rgba(255, 51, 0, 1)
icon=Summit</desc><extensions><onx:color>rgba(255, 51, 0, 1)</onx:color><onx:icon>Summit</onx:icon></extensions></wpt>
```
a1k, onX's KML export (and d1k, byte-identical):
```xml
<Placemark><name>[id1] ZZTEST Alpha</name><ExtendedData><Data name="name"><value>[id1] ZZTEST Alpha</value></Data><Data name="notes"><value>id1 original waypoint</value></Data><Data name="id"><value>ec19268b-31fc-4e51-9615-d361194f8503</value></Data><Data name="color"><value>rgba(255, 51, 0, 1)</value></Data><Data name="icon"><value>Summit</value></Data></ExtendedData><Point><coordinates>-121.4911,46.2052,3680.550048828</coordinates></Point></Placemark>
```
b-V1, Cairn's upload (no id):
```xml
<wpt lat="46.2052" lon="-121.4911">
  <name>[id1] ZZTEST Alpha · V1</name>
  <desc>id1 original waypoint</desc>
  <extensions><onx:icon>Summit</onx:icon><onx:color>rgba(128,0,128,1)</onx:color></extensions>
</wpt>
```
b-V2, the adversarial upload (the original's id kept):
```xml
<wpt lat="46.2052" lon="-121.4911"><name>[id1] ZZTEST Alpha · V2</name><desc>name=[id1] ZZTEST Alpha · V2
notes=id1 original waypoint
id=ec19268b-31fc-4e51-9615-d361194f8503
color=rgba(255, 51, 0, 1)
icon=Summit</desc>…</wpt>
```
d3, onX's export of what V2 created. **This is the key evidence:**
```xml
<wpt lat="46.2052" lon="-121.4911"><name>[id1] ZZTEST Alpha · V2</name><desc>name=[id1] ZZTEST Alpha · V2
notes=name=[id1] ZZTEST Alpha · V2
notes=id1 original waypoint
id=ec19268b-31fc-4e51-9615-d361194f8503
color=rgba(255, 51, 0, 1)
icon=Summit
id=5f937f55-f9c8-4185-a62a-f56ebe4c6fb7
color=rgba(255, 51, 0, 1)
icon=Summit</desc>…</wpt>
```
The uploaded `<desc>`, `id=` line included, became the new markup's `notes`. The markup's real
id is the new `5f937f55-…`.

d4, onX's export of what V2k created (KML ExtendedData ignored):
```xml
<wpt lat="46.2052" lon="-121.4911"><name>[id1] ZZTEST Alpha · V2k</name><desc>name=[id1] ZZTEST Alpha · V2k
notes=
id=94c94e67-b6ac-491b-9794-c1c8398a01e8
color=rgba(8, 122, 255, 1)
icon=Location</desc>…</wpt>
```

### 7.2 Line

a0: `<trk><name>[id1] ZZTEST Bravo</name><desc>id1 original line</desc>…<onx:style>solid</onx:style><onx:weight>4.0</onx:weight>…<trkpt lat="46.2000" lon="-121.5000"/>…` (4 points, no `<time>`)

a1 / d1 (identical except `<time>`):
```xml
<trk><name>[id1] ZZTEST Bravo</name><desc>name=[id1] ZZTEST Bravo
notes=id1 original line
id=3e2847f9-456c-4604-b36a-e9a364b2af67
color=rgba(8,122,255,1)
style=solid
weight=4.0</desc>…<trkpt lat="46.2" lon="-121.5"><ele>0</ele><time>2026-10-23T13:59:58.486Z</time></trkpt>…
```
a1k / d1k: `<Placemark><name>[id1] ZZTEST Bravo</name><ExtendedData>…<Data name="id"><value>3e2847f9-456c-4604-b36a-e9a364b2af67</value></Data>…</ExtendedData><LineString>…`

b-V1 (Cairn): `<trk><name>[id1] ZZTEST Bravo · V1</name><desc>id1 original line</desc>…<onx:color>rgba(255,0,255,1)</onx:color>…<time>2026-10-23T13:59:58.486Z</time>…` (no id; Cairn carried a1's `<time>` through)

d2: `<trk><name>[id1] ZZTEST Bravo · V1</name><desc>…id=ac997c3a-fc23-4677-9280-1acc4e2d0cda…`

d3: `<trk><name>[id1] ZZTEST Bravo · V2</name><desc>…notes=…id=3e2847f9-456c-4604-b36a-e9a364b2af67…\nid=e25b5897-8e2f-4137-b2da-b00139018c17…`

d4: `<rte><name>[id1] ZZTEST Bravo · V2k</name><desc>…notes=\nid=ee34b9aa-cca7-4cc1-8253-9225c17700c1\ntype=Line\ncolor=rgba(255,51,0,1)</desc><type>Line</type>…` (a KML LineString imports as an onX *Line*, not a Track)

### 7.3 Area

a0: `<rte><name>[id1] ZZTEST Charlie</name><desc>id1 original area</desc><type>Area</type><extensions><onx:color>rgba(132,212,0,1)</onx:color><onx:fill_color>rgba(132,212,0,0.1)</onx:fill_color></extensions>…`

a1 / d1:
```xml
<rte><name xmlns="http://www.topografix.com/GPX/1/1">[id1] ZZTEST Charlie</name><desc xmlns="http://www.topografix.com/GPX/1/1">name=[id1] ZZTEST Charlie
notes=id1 original area
id=cfc27a79-9da6-4895-9f81-61120f773c61
type=Area
color=rgba(132,212,0,1)
weight=4.0
fill_color=rgba(74,144,226,0.1)</desc><type>Area</type>…
```
b-V1: `<rte><name>[id1] ZZTEST Charlie · V1</name><desc>id1 original area</desc><type>Area</type><extensions><onx:color>rgba(255,0,255,1)</onx:color><onx:fill_color>rgba(255,0,255,0.1)</onx:fill_color></extensions>…`

d2: `…[id1] ZZTEST Charlie · V1…id=f42c78f1-a3e4-4d8a-9d67-fc1f60d3b348…`
d3: `…notes=name=[id1] ZZTEST Charlie · V2\nnotes=id1 original area\nid=cfc27a79-9da6-4895-9f81-61120f773c61…\nid=d8323b74-e1db-47d7-b624-63126671be47…`
d4: `…[id1] ZZTEST Charlie · V2k…notes=\nid=dd58a5be-abff-4981-a056-04ec274bbd4c\ntype=Area\ncolor=rgba(255,51,0,1)…`

### 7.4 uuid map

| Markup | Original (a) | V1 (Cairn) | V2 (GPX, same ids) | V2k (KML, same ids) |
|---|---|---|---|---|
| Alpha (waypoint) | `ec19268b-31fc-4e51-9615-d361194f8503` | `4e0578bc-2a8c-4593-8691-727a9f79c742` | `5f937f55-f9c8-4185-a62a-f56ebe4c6fb7` | `94c94e67-b6ac-491b-9794-c1c8398a01e8` |
| Bravo (line) | `3e2847f9-456c-4604-b36a-e9a364b2af67` (track) | `ac997c3a-fc23-4677-9280-1acc4e2d0cda` (track) | `e25b5897-8e2f-4137-b2da-b00139018c17` (track) | `ee34b9aa-cca7-4cc1-8253-9225c17700c1` (**line**) |
| Charlie (area) | `cfc27a79-9da6-4895-9f81-61120f773c61` | `f42c78f1-a3e4-4d8a-9d67-fc1f60d3b348` | `d8323b74-e1db-47d7-b624-63126671be47` | `dd58a5be-abff-4981-a056-04ec274bbd4c` |

12 distinct uuids, no reuse.

## 8. Diffs

### 8.1 Originals before and after the imports (a1 → d1)

```
$ cmp a_originals/a1_export_originals.kml d_reexport/d1_originals.kml && echo KML-IDENTICAL
KML-IDENTICAL
$ diff a_originals/a1_export_originals.gpx d_reexport/d1_originals.gpx   # line 10, trimmed
< …<trkpt lat="46.2" lon="-121.5"><ele>0</ele><time>2026-10-23T13:59:58.486Z</time></trkpt>… (×4)
> …<trkpt lat="46.2" lon="-121.5"><ele>0</ele><time>2026-10-23T14:07:28.603Z</time></trkpt>… (×4)
```
Nothing else differs: names, notes, ids, colours, icon, style, weight and coordinates all match.
The `<time>` values are the moment of each export, not stored data (§6). The API confirms it:
the track's `created_at` is `13:58:37.090059Z` and has not changed (§9.2).

### 8.2 What the adversarial uploads changed (a1 → b-V2, a1k → b-V2k)

Exactly 6 replacements in each file (`make_v2.py` reported `replacements: 6`). In GPX, each
item's `<name>X</name>` became `<name>X · V2</name>` and its `name=X` line became
`name=X · V2`. In KML, each `<name>` and `<Data name="name"><value>` gained ` · V2k`. Every
`id=` and `<Data name="id">` is the original uuid.

### 8.3 What Cairn changed (a1 + a1k → b-V1)

The `<desc>` block went from 5–7 `key=value` lines to the note alone (the `id=` line is gone),
`<onx:color>` changed, and ` · V1` was appended to the name. Cairn also normalised
whitespace, split the output into one file per kind, added the XML declaration, set
`creator="Cairn - CalTopo to OnX Migration Tool"`, wrote `<ele>0.0</ele>` and kept every
`<time>`. Cairn's `load_files` read the ids (`onx_id= ec19268b…`, `3e2847f9…`, `cfc27a79…` in
the run log) and kept them in memory only (`properties["cairn_onx_id"]`).

## 9. onX's own API traffic (read-only)

### 9.1 What the browser sends on import

Each file is one `POST https://api.production.onxmaps.com/v1/markups/import`, a multipart form
with three parts: `type` (`gpx` / `kml`), `file` (the raw file) and `collection-id` (the new
folder's uuid, created just before by `POST /v1/content-collections/create_content_collection`).
The response lists only the uuids it created:

| Import | Request `content-length` | = multipart overhead + file bytes | Response |
|---|---|---|---|
| a0 | 1846 | 435 + 1411 | `{"markups":["ec19268b-…","3e2847f9-…","cfc27a79-…"]}` |
| V1 (3 POSTs) | 976 / 1501 / 1181 | 475+501 / 472+1029 / 471+710 | `["4e0578bc-…"]`, `["ac997c3a-…"]`, `["f42c78f1-…"]` |
| V2 | 2411 | 437 + 1974 | `["5f937f55-…","e25b5897-…","d8323b74-…"]` |
| V2k | 2260 | 438 + 1822 | `["dd58a5be-…","ee34b9aa-…","94c94e67-…"]` |

The byte counts add up exactly, so the server received each file unmodified and did the
parsing itself. This matches the decoded client code (research §1.1(b)). The response has no
"updated" list. In every case the uuids returned were new.

### 9.2 The originals' records, before and after

From the page's own `GET /v1/markups/{waypoints,shapes,lines,tracks}` and
`GET /v1/content-collections?includeEntities=true`:

| Original | `created_at` | `updated_at` after a (13:58) | `updated_at` after V2 (14:04) | after V2k (14:05) | final (14:10) |
|---|---|---|---|---|---|
| Alpha `ec19268b` | 13:58:37.089746Z | 13:58:37.089746Z | 13:58:37.089746Z | 13:58:37.089746Z | 13:58:37.089746Z |
| Charlie `cfc27a79` | 13:58:37.090358Z | 13:58:37.090358Z | 13:58:37.090358Z | 13:58:37.090358Z | 13:58:37.090358Z |
| Bravo `3e2847f9` | 13:58:37.090059Z | — (on a later API page, not captured) | — | — | 13:58:37.090059Z |

For Alpha and Charlie, the record saved after stage a equals the final one field for field
(`A == B` over every key, including `geo_json`, `notes`, `color` and `last_synced_at`). Folder
membership of `ZZTEST · id1 · originals` (`a8512ffe-0430-4880-ad81-8e14b72d166c`) at the end
is still exactly `ec19268b`, `3e2847f9` and `cfc27a79`, each `inserted_at 13:58:37Z`. The
folder's own `updated_at` (13:59:37Z) is Claude's rename.

**Account-wide check, from before the run to after it:**

| List | Before | After | New | Gone | Changed (name, notes, `updated_at` or geometry) |
|---|---|---|---|---|---|
| waypoints | 445 | 449 | the 4 id1 Alphas | 0 | 0 |
| shapes (areas) | 12 | 16 | the 4 id1 Charlies | 0 | 0 |
| lines | 1 | 2 | Bravo · V2k | 0 | 0 |
| folders | 13 | 17 | the 4 id1 folders | 0 | — |

Tracks are paged 50 at a time (about 2 MB per page). The whole list was not compared before
and after, only the id1 records.

### 9.3 A timestamp trap: a track's `created_at` comes from its `<time>`

| Track | `created_at` | `last_synced_at` (real arrival) |
|---|---|---|
| Bravo (original, no `<time>` in a0) | 13:58:37.090059Z | 13:58:37.090206Z |
| Bravo · V1 (Cairn kept a1's `<time>`) | **13:59:58.486000Z** | 14:03:16.193228Z |
| Bravo · V2 | **13:59:58.486000Z** | (imported 14:04:43) |

onX sets an imported track's `created_at` from the file's point times. The new tracks
therefore look as if they were created at the moment of a1's export, before they existed. An
identity check cannot rely on a track's `created_at`. Use the uuid, `updated_at` and
`last_synced_at`.

## 10. Conclusion, confidence and limits

**Conclusion.** On 2026-10-23, onX's Web Map import is create-only:

- It does not match on the GPX `<desc>` `id=` line, which it treats as note text.
- It does not match on KML `<ExtendedData><Data name="id">`, which it ignores along with all
  other ExtendedData.
- It does not match on position or geometry. V1, V2 and V2k sit on exactly the originals'
  coordinates. id1 always changed the name. The identical-name case is covered by research
  §1.7: an unchanged file, same names and ids, re-imported for +2.
- It never modified an existing markup.

Re-importing an edited onX export (Cairn's path, or a hand-edited file that keeps the ids)
gives a second, independent copy. The original is untouched.

**Is there an id-based merge?** None was observed on any path. The import endpoint takes only
`type`, `file` and `collection-id` and returns only created uuids. The client has no
update branch (research §1.1(b)).

**Confidence: high** for current Web Map behaviour, because four independent lines of
evidence agree: the byte-level re-export diff, the API records, the account-wide counts and
the uuid map.

**Limits. Do not over-assume:**

- **onX can change server behaviour at any time.** Parsing is server-side, so a deploy could
  start honouring `id=` without any change in the web client. Re-run id1 (≈15 minutes, §12) if
  anything ever depends on it.
- **Only the Web Map importer was tested.** The phone apps' import may be a different path.
- **Only "Import map data to a new folder" was tested.** Importing without a new folder was not
  tried.
- **The ids were the account's own live markups.** Not tested: ids of deleted markups, ids
  from another account, or markups shared with this one.
- **No other id placement was tried.** For example a `<wpt id="…">` attribute, `<onx:id>`,
  `<link>` or KML `Placemark@id`. onX's exports use none of these.
- **Tracks were not checked account-wide** (§9.2). The original track was checked through
  its re-export and its final API record.
- **One run, three markups.**

**Safe to assume?** Yes for planning and wording: "import always adds; it never updates".
That is already in DECISIONS/ROADMAP (Phase 6 dropped, "replace" wording). The safety
argument for Cairn does not depend on it holding forever, because Cairn sends no ids (§11).
Even if onX began honouring ids, a Cairn upload could not match anything.

## 11. Implications for Cairn

- **Cairn already does not write onX ids.** The writers put only the note into GPX `<desc>`
  (`cairn/core/writers.py:_desc_text`). The `id=` key=value block is written only when
  `debug_desc=True`, and `web/bridge.py` never passes it. The KML area writer's
  `<ExtendedData>` carries `notes`, `color`, `style`, `weight` and `fill_color`, with no id
  (`writers.py`, the `onx_data` list). The readers keep the id in memory only
  (`cairn/io/document_adapter.py` `ONX_ID_KEY = "cairn_onx_id"`, bridge `item["onx_id"]`).
  id1's V1 files confirm it: `grep -c "id=" b_v1/*.gpx` gives 0, 0, 0.
- **Keep it that way. "Stripping" is the right behaviour, not a loss.**
  - Writing the id back could not update anything (§10).
  - Writing it into `<desc>` would be actively harmful. V2 shows onX would store the whole
    key=value block as the user's visible note, and each round trip would nest another
    `name=` / `notes=` / `id=` layer into it (d3).
  - KML ExtendedData is ignored, so an id there would be inert but pointless.
- **Suggested guard, not done here.** `tests/test_writers_waypoints.py:81` asserts `"id=" not
  in gpx` only for a CalTopo-sourced feature. A test that loads an onX export (with ids)
  through `bridge.load_files` → `export_zip` and asserts that no source uuid appears in the
  output would pin the behaviour id1 relies on.
- **Side effect worth knowing.** Cairn passes onX's `<trkpt><time>` through. Those times are
  the moment of the onX export (§6), so a re-imported track gets that moment as its
  `created_at` (§9.3). This is harmless for identity but misleading in onX's "date created"
  sorting. Dropping times that are all one value across a track would avoid it. That is a
  product decision, not part of this doc.
- **The `debug_desc` path writes `id=`, with a fresh `uuid4` when the source has none.** Given
  V2, a debug-mode file imported into onX would put that block into users' notes. It should
  never become reachable from the web UI.

## 12. Created in onX by id1 (the owner deletes: markups first, then the folder)

| Folder (uuid) | Markups (uuid) |
|---|---|
| `ZZTEST · id1 · originals` (`a8512ffe-0430-4880-ad81-8e14b72d166c`) | `[id1] ZZTEST Alpha` (`ec19268b-…`), `[id1] ZZTEST Bravo` track (`3e2847f9-…`), `[id1] ZZTEST Charlie` area (`cfc27a79-…`) |
| `ZZTEST · id1 · v1 cairn` (`70b6d4f0-9cc4-4913-b890-a85b146529df`) | `… Alpha · V1` (`4e0578bc-…`), `… Bravo · V1` track (`ac997c3a-…`), `… Charlie · V1` area (`f42c78f1-…`) |
| `ZZTEST · id1 · v2 same-ids gpx` (`6a0d30de-f275-4df5-b9ea-de6fced8252f`) | `… Alpha · V2` (`5f937f55-…`), `… Bravo · V2` track (`e25b5897-…`), `… Charlie · V2` area (`d8323b74-…`) |
| `ZZTEST · id1 · v2k same-ids kml` (`d8606d25-d613-4393-8e92-4139b4b57159`) | `… Alpha · V2k` (`94c94e67-…`), `… Bravo · V2k` **line** (`ee34b9aa-…`), `… Charlie · V2k` area (`dd58a5be-…`) |

4 folders and 12 markups (4 waypoints, 3 tracks, 1 line, 4 areas). Search All Content for
`[id1]` to find any leftovers. After cleanup the API lists return to 445 waypoints, 12
areas, 1 line and 13 folders.

**To re-run** (about 15 minutes), follow §4's table:

1. Import a0 into a new folder, then export that folder as GPX and as KML.
2. Build V1 and the two V2 files:
   - V1 is `bridge.load_files([gpx, kml])`, then `apply_edits({uid: {"name": name + " · V1",
     "color": …}})`, then `export_zip()`. Run it with `.venv/bin/python` and the sandbox off,
     because the bridge writes to `/tmp`.
   - V2 and V2k replace `>X<` with `>X · V2<` and `name=X\n` with `name=X · V2\n` for each of
     the three names in onX's own files. Nothing else changes.
3. Import V1, V2 and V2k, each into its own new folder.
4. Re-export every folder, then compare with `cmp`/`diff` and against the API records.

To read the API without making requests, use the Web Map's own
`GET /v1/markups/{waypoints,shapes,lines,tracks}` and
`/v1/content-collections?includeEntities=true` responses from DevTools.
