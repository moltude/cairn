# onX re-import identity and public sharing — research, 2026-10-22

> **Archived references (2026-10-25).** The `docs/*_2026-08-29.md` and `docs/ROADMAP_ONX_ROUND_TRIP.md` files
> cited below are no longer tracked; read them with `git show cdd25f3:docs/<name>`.

Two questions, answered only from public sources plus this repo. No onX account was used.

Evidence tags:

- **VERIFIED**: a primary source, quoted, with a URL or a repo `file:line`. For onX's help
  center that means the Zendesk API JSON fetched today
  (`https://onxbackcountry.zendesk.com/api/v2/help_center/en-us/articles/<id>.json`). The HTML
  pages sit behind Cloudflare. For onX's code it means the Web Map JavaScript fetched today from
  `https://backcountry.onxmaps.com/` (the old `webmap.onxmaps.com` now 302-redirects there).
  Bundle hashes change on every onX deploy, so the relevant code is quoted verbatim below.
- **INFERRED**: my reasoning from verified facts. The reasoning is shown.
- **UNKNOWN**: public sources don't settle it.

## Summary

| Question | Verdict | Confidence |
|---|---|---|
| Q1. Does re-importing an edited onX export **update** the existing markups or **create** new ones? | **UNKNOWN** from public evidence. The one indirect signal points to *create* (duplicates). | The deciding logic runs on onX's server, which can't be read. A 10-minute test (§1.4) settles it. |
| Q2. Can onX Backcountry markups or folders be shared **publicly**, like a CalTopo public map? | **No.** Every share needs the recipient to have an onX Backcountry account. | VERIFIED from onX's help center (updated 2026-10-19) and the Collaborative Folders page. |
| Q2b. Can a CalTopo map be viewed by anyone with no login? | **Yes**, if the map is set to **URL** (the default) or **Public** and shared as a plain URL with no access code. | VERIFIED: CalTopo blog plus an official CalTopo staff reply. |

New findings outside the two questions. These are flagged for the owner; I edited no other file.

1. **The account limit is now 3,000, not 1,500.** VERIFIED: help article 360052239052
   (updated 2026-09-16) says *"Note: Your onX account is limited to 3,000 Markups."* The
   Aug 2026 docs quoted *"currently limited to 1,500 Markups"* from the same article. Stale
   copies of 1,500:
   - `web/app.js:844`: the warning fires at `total > 1500` and says "an onX account holds 1,500".
   - `web/index.html:199`
   - `docs/FAQ.md:126,157` and `web/faq.html` (the "Keep you under the account limit" answer and the round-trip answer)
   - `docs/FIDELITY_MODEL_2026-08-29.md:29,89,143,155,281`
2. **The per-import limits haven't changed.** VERIFIED: 360057195972 says *"You can import up
   to 3000 individual markups."* 5022588722317 says *"Import files must be GPX or KML format,
   4 MB or less, and contain no more than 3,000 Markups."*
3. **onX's help is wrong about its own export format.** Help 360057195972 says *"Only the
   location and name of the Markup will be saved. onX customizations like icons and colors are
   not saved"* and *"KML and GPX file formats … do not save onX customizations like colors,
   icons, and notes."* onX's current export code writes `notes` into `<desc>` and
   `onx:color`/`icon`/`style`/`weight`/`fill_color` extensions (§1.1). The code wins for
   Web Map exports. Treat that help text as stale, not as evidence.
4. **The "export then re-import" advice now sits in a different article.** `docs/FAQ.md:157`
   (via FIDELITY:88-89) says onX suggests export-then-reimport "to manage the 1,500 limit".
   Today the advice is in the *performance* article 4402358311053 (quoted in §1.2), and it says
   to export and then **delete** before re-importing.

---

## Q1. Round trip: update in place, or duplicate?

### 1.1 What onX's code shows (VERIFIED, fetched 2026-10-22)

These are the same mechanisms FIDELITY_MODEL decoded on 2026-08-29, in rotated bundles. The
logic is unchanged.

| FIDELITY (Aug) | Today | Role |
|---|---|---|
| `87571.…js` module `z1zK` | `50657.87e3701dffd2f41a9e91.js` module `bVmq` | import executor |
| `40439.…js` | `33209.792d376b438ff1099263.js` | GPX export post-processor and property builder |
| `58175.64658723954c9057d989.js` | `58175.9a598488596098369e34.js` | togpx/tokml libraries |

**(a) Exports carry each markup's onX UUID.** In `33209.…js`, function `G` builds each feature's
properties from the markup:

```js
const n={name:e.name,notes:e.notes??"",id:e.uuid};
```

togpx's default `featureDescription` (`58175.…js`) then writes every non-object property into
`<desc>` as `key=value` lines:

```js
function E(c){ … var s=""; for(var f in c) typeof c[f]!="object"&&(s+=f+"="+c[f]+`\n`); return s.substr(0,s.length-1)}
```

So every Web Map **GPX** export has `id=<onX markup uuid>` in each element's `<desc>`, next to
`name=` and `notes=` and, depending on type, `color=`, `style=`, `weight=`, `type=Line|Area`.
The same properties are also used as the timestamp key
(`featureCoordTimes:o=>t.timestamps[o.properties.id]`, and timestamps are keyed by `i.uuid`).
That confirms `id` really is the UUID. Routes use `id:e.id` (function `$`).

- KML exports go through tokml with the same feature objects (`function S(e){const t=x(e,"kml"),n=A()(t.markups)…}`).
  tokml normally writes properties as `<ExtendedData>`, so a KML export probably carries `id` too.
  **INFERRED.** I didn't inspect tokml's options in the bundle.
- The phone app's GPX export is a different code path and wasn't inspected. **UNKNOWN** whether
  it writes `id=`.

**(b) The importer sends the raw file, and only three fields, to the server.** All of
`50657.…js`, module `bVmq`, abridged only by removing analytics:

```js
f=async(_,l=!1,w="")=>{ …
  const n=l?await r.A.addCollection({name:"Import"+(0,E.Ay)(new Date," mm/dd/yy H:MM")}):null,
  y=_.map(async a=>{
    const c=new FormData;
    c.append("type",a.type), c.append("file",a.rawData), n&&c.append("collection-id",n);
    try{
      const s=await(0,k.hu)("/v1/markups/import",c,{},!1);
      s?.markups?.length&&t._markupIds.push(...s.markups),
      await p.Ay.requestAllMarkups(!1);
      … s?.markups?.forEach(v=>{switch(p.Ay.getMarkupByID(v).type){ … counts … }}),
      publish("x-marketing-event",{name:"content_import_complete", … markup_count:s?.markups?.length, …})
    }catch(s){ … "content_import_failed" … }
  }),
  …
  await Promise.all([...y,D]),
  l&&(await r.A.requestCollections(), r.A.isCollectionEmpty(n)&&(r.A.deleteCollection(n),…))
```

What this settles:

- **VERIFIED:** the client never parses the file. Whether `id=` in `<desc>` is honoured is
  decided entirely on onX's server, which this research can't see. That's the whole question,
  so the honest answer is UNKNOWN.
- **VERIFIED:** the server returns a list of markup ids (`s.markups`). The client counts all of
  them as "imported" and then re-fetches the whole account (`requestAllMarkups`). The response
  handling has no separate created and updated paths.
- **INFERRED (weak):** if the server upserted by id, the client would probably have no reason
  to re-fetch everything, and the analytics would probably tell apart "updated" from "created".
  Neither is the case. This is a soft hint, not proof. A server could upsert and return the same
  shape.

### 1.2 What onX's help says (VERIFIED, all fetched 2026-10-22)

- **4402358311053** "How to improve performance in the Backcountry App" (updated 2026-07-20):
  *"If you want to keep a set of Markups but don't need them in the App right now, export them
  as a GPX or KML file and delete them from your account. You can re-import them later when you
  need them."* This is onX's only described round trip, and it deletes the originals first.
- **360052607232** "My Waypoints … are missing" (updated 2026-07-20): *"Instead of deleting
  Markups you might need later, export them as a GPX or KML file for future reference."* This is
  backup and restore again, with no mention of merging.
- **360057195972** "Importing and Exporting Markups" (updated 2026-04-01): *"The uploaded file
  is listed in the My Content Menu along with all of your other Markups."* The article never
  mentions updating, merging, replacing or skipping duplicates.
- **360052209311** "Sharing Markups with other onX Backcountry users" (updated 2026-10-19):
  *"Note: If you click a share link you created yourself, you'll get an error message, since
  the Markups are already in your account."*
- **Search:** a Zendesk search for "duplicate" (`/api/v2/help_center/articles/search.json?query=duplicate`)
  returned one unrelated article, about Elite upgrades. **No onX help article discusses
  duplicate imports.**

INFERRED from the above:

- The share-link note shows onX's **sharing** system tracks markup identity and refuses to
  re-add markups you already own. That's a different endpoint (`/v1/sharing/shares`) and a
  different mechanism (server-side entity references). It doesn't show the **file import** path
  does the same.
- onX documents only export → delete → re-import. If import matched by id, "export, edit,
  re-import to update" would be an obvious feature to document, and it isn't. This is the main
  reason to lean toward duplicates. It's an argument from silence, so the verdict stays UNKNOWN.

### 1.3 Community evidence

- Web searches for onX re-import duplicates found **nothing relevant**. The queries were
  `onX Backcountry re-import GPX duplicate waypoints` and
  `onX maps import gpx creates duplicates reddit onxmaps`. Every result was about MyRouteApp,
  Suunto, ExplorOz or OSM.
- Reddit couldn't be searched. The search tool refuses `reddit.com`
  (*"domains are not accessible to our user agent"*). **UNKNOWN** what r/onXmaps says. The
  owner can search r/onXmaps for "import duplicate" by hand in about 2 minutes. If anything
  turns up, it's anecdote and the test in §1.4 is still the answer.

### 1.4 What this means for Cairn (repo, VERIFIED)

- Cairn's writer doesn't put any ids in `<desc>` by default: `cairn/core/writers.py:77-93`,
  `_desc_text` returns only the user's notes unless debug mode is on. So **today, a Cairn-written
  file can't update anything in onX**, whatever the server does. With no id there's nothing to
  match on. *Note:* `docs/UX_AUDIT_2026-08-29.md:95-105` shows that earlier, debug-style Cairn
  output put a CalTopo UUID in `id=`. That isn't an onX UUID either.
- Cairn's onX GPX reader already parses `id` out of the desc key=value lines
  (`cairn/io/onx_gpx.py:33-43`, `_DESC_KV_KEYS`). An onX → Cairn → onX tool could keep onX's
  UUID **if** the test shows onX honours it.
- The repo has **no genuine onX export file** (`docs/FIDELITY_MODEL_2026-08-29.md:104-111`). The
  test below produces one. Keep it as a fixture (FIDELITY workplan item W6).

### 1.5 Verdict

**ANSWERED 2026-10-22: re-import creates duplicates (VERIFIED by test, see 1.7).** The text below
was written before the test and is kept for its reasoning.

**UNKNOWN. INFERRED lean: re-import creates new markups (duplicates).** Don't build or promise
"update in place" until the test below has been run. If the result is duplicates, the onX → Cairn
→ onX workflow must be "export, delete the originals in onX, re-import the cleaned file". That
loses anything onX keeps outside the file: photos, share grants, folder membership and Track
timestamps beyond what's in the file. So the cleanup tool would need to warn about that up front.

### 1.6 Ten-minute test (the owner runs it, and it leaves nothing behind)

**Prerequisites:** an onX Backcountry **Premium or Elite** account (importing requires it,
VERIFIED 360057195972), the **Web Map** on a computer, and a text editor. Allow about 10 minutes.

**Why it's safe:** two waypoints with an unmistakable name prefix, in a folder of their own.
My Content search is by name only (VERIFIED, 360052239052), so the prefix makes every test
markup findable. Cleanup is listed explicitly because of one trap:

> ⚠️ **Deleting a folder doesn't delete its markups.** VERIFIED, 360052239052:
> *"Delete: Delete the Folder. Markups inside it aren't deleted."* Delete the markups first,
> then the folder.

**Steps:**

1. **Set up.** My Content → Create New Folder, named `ZZ Cairn Test`. Drop two waypoints
   anywhere, named `ZZTEST Alpha` (leave it Blue) and `ZZTEST Bravo`. Add both to `ZZ Cairn Test`.
   - *Record:* the total markup count in My Content (All Content) before and after. Expect +2.
2. **Export.** Open the `ZZ Cairn Test` folder → Export (GPX). Or use Select → tick both → Export → GPX.
   - *Record:* the file name. Open the file and copy each `<wpt>`'s `<desc>` block, in particular
     the `id=` value. This is the first real onX export captured for the repo. Save it as
     `tests/fixtures/onx_real/export_baseline.gpx` (this sets up W6).
3. **Test A: re-import the unmodified file.** My Content → Import → select the same file → tick
   **"Import map data to a new folder"** → Import. Refresh the browser if the markups don't show,
   as onX's help advises (see also memory note: "stale Web Map").
   - *Record:* the total count. **+0** means the server matched by id and skipped or replaced.
     **+2** means it duplicates.
   - Search `ZZTEST` and record how many `Alpha`/`Bravo` entries there are.
   - If you got **+2, stop here. The question is answered: import creates new markups.** Go to
     step 6.
4. **Test B: re-import an edited file (only if A gave +0).** In a copy of the file, change
   `ZZTEST Bravo`'s name to `ZZTEST Bravo EDITED`, both in `<name>` and in the `name=` line. Change
   Alpha's color in both the `color=` line and `<onx:color>` (for example
   `rgba(255,0,0,1)` / red). Import the copy, again into a new folder.
   - *Record:* the total count, and whether the original Bravo now shows the new name and Alpha
     the new color. **Changed in place** means import upserts by id. **Unchanged** means it skips
     known ids.
5. **Test C: compare ids.** Select all `ZZTEST` markups → Export GPX. Diff the `id=` values
   against step 2.
   - *Record:* whether the new markups got **new UUIDs**, which confirms they're copies, or kept
     the originals' UUIDs. Also record whether onX shows the `<desc>` key=value text verbatim in a
     markup's Notes. That would show the importer ignores desc key=value lines, and would explain
     the owner's earlier observation in FIDELITY:88-96.
6. **Clean up. Order matters.**
   1. My Content → search `ZZTEST` → Select → tick **every** result → Delete.
   2. Delete the folder `ZZ Cairn Test` and each `Import mm/dd/yy H:MM` folder the test created.
      Any folder still holding markups is just a label. Step 6.1 is what removes the markups.
   3. Check that the total markup count is back to the number from step 1.

**Report back:** the counts at steps 1, 3, 4 and 5, the id diff, whether Notes showed key=value
text, and the saved export files.

---

### 1.7 Test result (run 2026-10-22, owner's account, Web Map)

Run by Claude driving the owner's Chrome, with approval for each import; the owner deleted
the test data afterwards (account back to 266 markups, 13 folders).

| Step | Result | Account total |
|---|---|---|
| Baseline | 13 folders | 266 |
| Import a Cairn GPX with 2 waypoints ("ZZTEST A" Summit/red, "ZZTEST B" Camp/blue), "new folder" ticked | New folder "Import 10/22/26 9:07". The GPX `<metadata><name>` was ignored. Icons and colors kept. Cairn's `<desc>` became the onX notes | 268 |
| Export that folder as GPX and as KML | `onx-markups-10222026.gpx` / `.kml`, now in `tests/fixtures/onx_real/`. Each markup's `id=<uuid>` is in the file | 268 |
| Re-import the **unchanged** onX GPX (ids included), "new folder" ticked | **2 new markups** in a new folder "Import 10/22/26 9:09" | **270** |

**Verdict: onX import does not match on `id=`; it always creates new markups.** Steps B/C of
1.6 (edited re-import, id diff) were not needed to answer the question and were not run.
Consequences: Roadmap Phase 6 (update in place) is dropped; Phase 5's runbook uses "replace"
wording (back up, delete the originals, import).

Also observed: onX's My Content **Select** mode offers only Add to Folder, Share, Export and
Delete in bulk — no bulk icon, color or rename.

## Q2. Public sharing

### 2.1 onX Backcountry (VERIFIED)

- **360052209311** "Sharing Markups with other onX Backcountry users" (updated 2026-10-19):
  - *"Shared Markups sync automatically to the recipient's account as view-only. Recipients
    need an onX Backcountry account to receive shared Markups, but can't edit or re-share them."*
  - *"The recipient taps the link to import the Markups into their onX Backcountry account with
    view-only access."*
  - Limits: *"To select multiple Markups (up to 100)…"*. Folders: *"Use Folders to quickly share
    up to 100 Markups … set the sharing permission to View-only or Contribute."*
  - Nearby Sharing is App-only, and both people need the same OS.
- **Collaborative Folders page**, https://www.onxmaps.com/backcountry/app/collaborative-folders:
  *"You need a Premium or Elite Membership to share a Folder."* and *"Anyone with an onX account
  can be invited to contribute."* and *"They will only see what you add to the Folder you shared
  with them."*
- **Code** (`28452.d0cbe84440ea4b4f2a08.js`): share links are created with
  `POST /v1/sharing/shares?link=webmap` and a body of `{entities, link:{role}}`, where the role
  defaults to `VIEW_ONLY`. A received link is handled inside the Web Map app through a `link_id`
  query parameter, which fires the `share_link_received` event. That handling runs inside the
  logged-in map, which fits "log in, then the markups are added to your account". **INFERRED**
  for the logged-out experience.
- `onxmaps.com/backcountry/app/features` and onX's search results describe no public or
  anonymous map gallery comparable to CalTopo's Shared Maps.

**UNKNOWN:** what a logged-out person sees when they click an onX share link. It could be a
preview, a "get the app" landing page, or a straight login wall. An anonymous fetch of the Web
Map returns only a 3 KB app shell, which tells us nothing either way. The help text says
recipients *need an account to receive*, so at best a logged-out person sees a sign-up prompt.
Checking takes 1 minute: open a share link in a private window.

### 2.2 Verdict for onX

**There are no public onX maps.** Sharing goes from one onX account to another and requires an
account. Sharing a folder requires Premium or Elite. A shared item is copied into the
recipient's account as view-only. So:

- A walkthrough **can't link to a live onX map** that readers open without an account. Even
  with an account, opening the link adds markups to the reader's account. That's the opposite of
  "without creating a mess".
- A walkthrough **can** use screenshots the owner takes in their own account. The test-folder
  discipline from §1.6 keeps the mess contained: a `ZZ`-prefixed folder, with markups deleted
  before the folder.

### 2.3 CalTopo (VERIFIED)

- CalTopo blog, "Map Sharing and Visibility" (2024-01-14),
  https://blog.caltopo.com/2024/01/14/map-sharing-and-visibility/. It defines four base
  permissions:
  - *Public*: "Public maps are not only visible to anyone on the web, they will show up in search engine results."
  - *URL*: "The URL permission setting makes it easy to share a map for others to view."
  - *Secret*: "Secret maps require a special code, which we call a shareable link, for anyone besides the map owner to view the map."
  - *Private*: "Private maps can only be viewed by the map owner, no exceptions."

  It also says: *"The default setting is URL."* A blog comment adds that several maps can be
  changed at once with "Set Sharing on All".
- CalTopo staff reply (marked `official: true`, 2025-07-01) on help.caltopo.com community post
  38508472560155 (read through `/api/v2/community/posts/38508472560155/comments.json`): *"A Map
  must be URL or Public, and shared without an access code (ie. just the URL) to work without log
  in. Giving someone access to edit/add to a map requires a log in. Giving someone access to a
  secret map requires log in."*
- CalTopo's training page https://training.caltopo.com/all_users/share/permissions returned
  **HTTP 503 twice** and wasn't read. Its exact menu path for changing a map's permission is
  therefore **UNKNOWN** here.

**Recommendation for the walkthrough's starting point:** set the source CalTopo map (for
example a Bitterroots subset) to **URL**, not Public. URL is enough for anyone with the link to
view it without logging in. Public also puts the map on CalTopo's Shared Maps layer and in
search engines, which a personal scouting map may not want. Whether an anonymous viewer can
*export* the GeoJSON from a URL map is **UNKNOWN**. A CalTopo community request, "Offer option
to block data export when using Secret map sharing" (help.caltopo.com post 26313430463003, seen
only as a search-result title), suggests viewers can export. The owner can check in a private
window.

### 2.4 What the walkthrough can and can't show without a real onX account

| Part of the story | Can it be shown publicly? | How |
|---|---|---|
| The source map in CalTopo | **Yes, live** | A CalTopo map shared as URL, plus a screenshot |
| The CalTopo GeoJSON export | **Yes** | Ship a sample `.json`. `tests/fixtures/bitterroots/Bitterroots__Complete_.json` is real CalTopo data, but check it holds nothing private before publishing |
| Cairn's preview, edits and runbook | **Yes, live** | The web app itself. Screenshots already exist: `docs/screenshots/web-01-drop.png` … `web-07-runbook.png` |
| "Without Cairn": CalTopo GPX/KML imported straight into onX | **Screenshots only** (owner's account) | Already captured in Dec 2025: `export-from-caltopo-into-onx-poor.png` (local `archive/docs/screenshots/`, too large for the repo), `bitterroots-subset-onx-raw.png` |
| "With Cairn": styled markups and folders in onX | **Screenshots only** (owner's account) | Already captured: `docs/screenshots/bitterroot-subset-final-onx.png`, `hd-onx.png`. Compare with `bitterroots-subset-caltopo.png`, `hd-caltopo.png` |
| A live onX map readers can click into | **No** | Not possible: onX sharing needs an account and copies the markups into it |
| Folder renaming and runbook steps inside onX | **Screenshots only** | New captures needed. The Dec 2025 shots predate the runbook and folder flow |

The Dec 2025 screenshots predate the web app and the folder runbook. Before reusing any of them,
check that they still show current Cairn behaviour: today's icon mapping (cabin → Shelter as of
2026-10-22) and today's folder flow. Use a `ZZ`-prefixed folder for any new onX captures, and
clean up as in §1.6 step 6.

---

## Sources fetched 2026-10-22

onX help center, via the Zendesk API (`…/api/v2/help_center/en-us/articles/<id>.json`). The
title and `updated_at` are as returned:

- 360057195972: Importing and Exporting Markups (Waypoints, Routes, Lines, Shapes, and Tracks), 2026-04-01
- 360052239052: Editing and organizing Markups, 2026-09-16
- 360052209311: Sharing Markups with other onX Backcountry users, 2026-10-19
- 5013855682445: How to Manage Saved Markups, 2026-09-15
- 4446611009165: How to transfer Markups from CalTopo to onX Backcountry, 2026-07-14
- 5022588722317: There was an error when I imported Markups, 2026-07-20
- 360052607232: My Waypoints, Routes, Lines, Tracks, or Shapes are missing, 2026-07-20
- 4402358311053: How to improve performance in the Backcountry App, 2026-07-20
- 4422125175309: Using your Markups across onX Hunt, Offroad, Backcountry, and Fish, 2026-07-14

onX Web Map code, from `https://backcountry.onxmaps.com/`. The entry page's script tags plus all
792 lazy chunks were listed in `runtime.a789a7595c5c72acd102.js`:

- `50657.87e3701dffd2f41a9e91.js`: import executor (`/v1/markups/import`)
- `33209.792d376b438ff1099263.js`: export property builder (`id:e.uuid`) and GPX post-processor (`wwww.onxmaps.com` namespace)
- `58175.9a598488596098369e34.js`: togpx `featureDescription`
- `28452.d0cbe84440ea4b4f2a08.js`: sharing API (`/v1/sharing/shares`, `link_id` handling)
- Source maps aren't public (`50657….js.map` → 404).

Other:

- https://www.onxmaps.com/backcountry/app/collaborative-folders
- https://blog.caltopo.com/2024/01/14/map-sharing-and-visibility/
- help.caltopo.com community post 38508472560155 and its comments (API)
- Not reachable: training.caltopo.com (503) and reddit.com (blocked for the search tool).

Repo: `docs/FIDELITY_MODEL_2026-08-29.md:24-96,104-111,350-366,478-489`;
`docs/UX_AUDIT_2026-08-29.md:95-105`; `cairn/core/writers.py:77-93`;
`cairn/io/onx_gpx.py:25-43`; `web/app.js:844`; `web/index.html:199`; `docs/FAQ.md:126,157`;
`TODO.md:65-67`.
