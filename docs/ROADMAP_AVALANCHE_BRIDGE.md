# Roadmap: the Avalanche Bridge — local field reports onto the onX map (2026-10-22)

**Status:** draft. Nothing in this file is built, agreed with anyone, or committed to. It
combines one day of investigation into a single feature proposal. It replaces the earlier
working note `docs/research/AVALANCHE_OBS_OVERLAY_2026-10-22.md`.

**Evidence tags:**

- **VERIFIED**: fetched or run on 2026-10-22, and quoted.
- **INFERRED**: my reasoning, shown.
- **UNKNOWN**: needs a person to answer it.

---

## 0. The feature in one paragraph

onX Backcountry already shows the **zone-level** avalanche picture: daily danger ratings by
forecast zone, from the American Avalanche Association (A3), plus avalanche *incident* reports.
It doesn't show the **point-level field evidence** behind those ratings. That evidence is:

- forecaster field days and snowpack notes;
- professional and public reports of cracking and collapsing;
- the hundreds of avalanches observed each season.

For the Missoula area, all of that lives on missoulaavalanche.org. The Avalanche Bridge puts
those reports on the onX map as **lightweight points**: location, date, aspect, elevation, size
and type. Each point carries a **deep link back to the full report**, so the avalanche center
stays the source of truth. A rider planning a tour in onX, with slope-angle, aspect and ATES
layers already turned on, would also see *"three D2 wind slabs on NE aspects near here last
week"*. One tap opens the forecaster's or observer's full report.

```
            NATIONAL PLATFORM (avalanche.org / NAC, A3)          onX Backcountry
            ───────────────────────────────────────────          ──────────────────────────
 zone level   danger ratings by zone (v2 products/map-layer) ──► Avalanche Forecast layer  ✅ exists
              incident / accident reports                    ──► skull icons (Ski Tour)    ✅ exists

 point level  forecaster field obs (observer_type=forecaster)  ─┐
              professional obs                                  ├─► (nothing)              ❌ the gap
              public obs: cracking, collapsing, snowpack        │      ↑
              avalanche events (D-size, aspect, trigger)       ─┘   Avalanche Bridge
            ───────────────────────────────────────────
            authored locally by WCMAC forecasters and Missoula-area riders
```

---

## 1. Findings

### 1.1 Where WCMAC's data actually lives (VERIFIED)

**missoulaavalanche.org is not the backend.** It's a WordPress site (the WooCommerce shop,
memberships, events and pages). It embeds the National Avalanche Center's shared widgets, and
those widgets read from and write to **api.avalanche.org**.

| What a visitor sees | The page's embed | Where the data lives |
|---|---|---|
| `/observations/`, which shows observations and the map | `nac-widget-loader.min.js` with `data-widget="observations" data-center="WCMAC"` | `api.avalanche.org/obs/v1/public/…` |
| `/submit-an-observation/` | Redirects (301) to `/observations/#/form`, the same widget's form | The form does `POST /obs/v1/public/observation/` to api.avalanche.org |
| `/forecasts/`, `/avalanche-forecasts/` | `data-widget="forecast" data-center="WCMAC"` | `api.avalanche.org/v2/public/product…` |
| Photos on observations | n/a | The `avalanche-org-media` S3 bucket (`avalanche-org-media.s3.us-west-2.amazonaws.com`) |

**How a public report flows** (VERIFIED from the widget code and the center config):

1. A rider fills in the form on missoulaavalanche.org.
2. The browser POSTs it **straight to api.avalanche.org**. The report is stored as `draft`,
   because WCMAC's widget config has `require_approval: true`.
3. A WCMAC forecaster reviews it and publishes it. 117 of 134 avalanche records last season are
   `forecaster_verified: true`.
4. Published reports are served from api.avalanche.org to the widget on missoulaavalanche.org,
   and to any other page that embeds the widget.

So the data is reported up: it's **stored nationally from the moment it's submitted**. WCMAC is
one tenant (`center_id=wcmac`) of a shared national database. **There's no separate WCMAC
database to integrate with.**

**Ownership is split (INFERRED):**

- A3 / NAC operate the platform and control **access**.
- WCMAC and its observers author the **content**.

The About page says this explicitly about WCMAC itself:

> *"Unlike most Avalanche Centers, we are a locally operated nonprofit organization."*

That is, it isn't a Forest Service unit. Even so, WCMAC runs on the same national platform as the
Forest Service centers.

**There's no data or sharing policy on the site.** The About page and the FAQ (FAQ updated
2025-12-12) cover the mission, courses and donations. Neither says anything about observation
data, licensing, redistribution or APIs. **UNKNOWN:** WCMAC's position. This has to be asked
directly.

### 1.2 The WordPress era: history before January 2023 (VERIFIED)

Before the national widget, WCMAC kept observations and advisories **in WordPress itself**.
That archive is still online and is server-rendered:

| Data | Where | Range | Notes |
|---|---|---|---|
| Public and pro observations | `/observations-archive/?season=YYYY`: an HTML table linking to `/public-obs/<yyyymmdd>_<slug>/` and `/pro-obs/<yyyymmdd>_<slug>/` | 2021/22: 108 public + 114 pro. 2022/23: 26 rows, **Nov 6 – Dec 9, 2022 only** | Seasons from 2023/24 on show empty tables. A linked "Archived Public Observations (Prior to 2021/22)" page has older data. |
| Avalanche advisories | WordPress post type `advisory`: `/wp-json/wp/v2/advisory`, 677 posts | Latest dated **2021-04-08** | Replaced by the NAC forecast widget |
| Snow-profile galleries | WordPress post type `gallery`, 33 posts | Up to 2020/21 | Photos of pit profiles |
| Pro observer form | `/wcmac_pro_observer_form/` (Gravity Forms, 2021) | Legacy | Its entries aren't public (`/wp-json/gf/v2/entries` → 404) |

The current `/observations/` page was created on **2023-01-12**, and the widget config says
`obs_start_year: 2023`. That's the cutover.

**What this means:**

- **Everything from roughly mid-December 2022 onward is only on api.avalanche.org.**
- **Before that, it's only in WordPress.**
- A historical backfill would mean scraping old WordPress pages. That's possible, since the
  pages are server-rendered and robots.txt allows it with `Crawl-delay: 10`. But it's old data
  of little value for planning tours. **It's out of scope** for anything except a one-off
  history layer, and then only with WCMAC's blessing.

### 1.3 The `#/…` URLs, and why there's nothing to scrape page by page (VERIFIED)

You asked whether you could skip the dashboard and just pull individual event pages regularly.
**You can't. The individual pages hold no data.**

- **The server never sees the `#` part.** In
  `https://missoulaavalanche.org/observations/#/observation/e69b22d4-…`, everything after `#`
  is a URL *fragment*. Browsers don't send fragments to the server. So every observation URL,
  and the date-filtered dashboard URL too, downloads the **same** 156 KB WordPress shell. The
  widget's JavaScript then reads the fragment (Vue Router hash mode, with routes
  `/observation/:id`, `/avalanche/:id`, `/view/observations`, `/view/avalanches`, `/form`, …)
  and calls the API from your browser. Scraping the page with curl gets nothing. Scraping it
  with a headless browser just makes the same gated API call the long way round.
- **The ids can't be guessed.** `e69b22d4-00b6-497b-9d1f-78cf140ad1dc` is a **version-4
  (random) UUID**: the `4` in `497b` is the version marker, and 122 of its bits are random. So
  is the avalanche id `e6653340-fbf5-4574-…`. You can't count through them or predict the next
  one. The only way to *discover* ids is the list endpoint, which is the same gated API.
- **What the hash URLs are good for:** they are **stable, shareable deep links**. That's exactly
  what the Bridge needs for its "full report" link. They're useless for *collecting* data and
  perfect for *pointing at* it.

The pre-2023 WordPress URLs (`/public-obs/20220430_sugarloaf-peak/`) are the opposite: readable,
server-rendered and scrapable. They stopped in December 2022.

### 1.4 The API surface and who can reach it (VERIFIED)

I read the widget code (`observations.js`, 3.4 MB, version `20261014`) and avalanche.org's map
app (`ndm-app/dist/build.js`). I then made plain `curl` GETs with **no `Origin` header**:

| Endpoint | Content | Plain GET |
|---|---|---|
| `api.avalanche.org/v2/public/products/map-layer[/WCMAC]` | Forecast-zone polygons with today's danger, travel advice and link | **200 (open)** |
| `api.avalanche.org/v2/public/products?avalanche_center_id=WCMAC` | All WCMAC products: 960 since 2019-11-26 (514 forecasts, 286 weather, 160 summaries) | **200 (open)** |
| `api.avalanche.org/v2/public/product/<id>` | One forecast: bottom line, danger, `forecast_avalanche_problems`, hazard discussion | **200 (open)** |
| `api.avalanche.org/v2/public/avalanche-center/WCMAC` | Center metadata, `off_season`, widget config | 200 |
| `api.avalanche.org/obs/v1/public/observation/<id>` | One observation and its nested avalanches | **401 `unauthorized`** |
| `…/obs/v1/public/observation/list/`, `…/avalanche_observation/list/` | Paginated lists. Params: `start_date[gte]`/`[lte]` or `date[gte]`/`[lte]`, `center_id[eq]`, `bbox`, `page`, `page_size`, `sort_by`, `sort_order` | **401** |
| `…/obs/v1/public/graphql`, `…/observation/tiles/{z}/{x}/{y}.mvt` | Slim map fields and vector tiles | Same gate (INFERRED) |
| `api.avalanche.org/` | *"Avalanche.org API — Please contact avalanche.org / American Avalanche Associat[ion] for permission"* | 200 |

The **observations** API returns 401 unless the request carries
`Origin: https://missoulaavalanche.org`. Browsers add that header automatically on WCMAC's page.
The API then answers with `access-control-allow-origin: https://missoulaavalanche.org` and
`vary: Origin`. The widget also has a signed-in mode (`data-auth`): it sends
`Authorization: Bearer <token>` to `/obs/v1`, without `/public`. That's what a granted
credential would look like.

The **forecast** endpoints answer anyone. That's almost certainly how onX's Avalanche Forecast
layer is fed (INFERRED, see §1.6). **Reachable isn't the same as licensed**, though. The root
page's "contact for permission" covers the whole API.

**Method disclosure.** To learn the data's shape, I sent the observation requests **once, with
the `Origin: https://missoulaavalanche.org` header**. That made them look like they came from
WCMAC's own page. That was acceptable for a one-time requirements probe and is **not acceptable
for production**: it gets around an access check the operator put there on purpose, and it
ignores their explicit request on their own root page. Nothing in this roadmap depends on doing
it again. The sampled responses are kept outside the repo at `/private/tmp/claude-501/mac/`,
because they contain observers' names (§1.5).

### 1.5 What the data looks like: WCMAC, 2025/26 season (VERIFIED)

**Volume:**

| | |
|---|---|
| Observations | 254, all published |
| Avalanche records | 134 rows, totalling 248 avalanches (`number` can be >1) |
| Payload | about 6.5 KB per observation |
| By month | Oct 1 · Nov 6 · **Dec 48 · Jan 69 · Feb 65 · Mar 56** · Apr 9 |

**Who reports, and where:**

| | |
|---|---|
| Observer type | public 150 · forecaster 86 · professional 13 · intern 4 · observer 1 |
| Submitted through | NAC widget 157 · forecaster dashboard 96 · avy app 1 |
| Zones | Bitterroot 145 · Rattlesnake 48 · Seeley Lake 33 · none 28 |
| Activity | skiing/snowboarding 226 · snowmobiling 44 · other 8 |

**Timing:**

| | |
|---|---|
| Delay from observation to posting | median **1 day** |
| Edited after posting | 110 of 254 (43%) |

**Locations:**

| | |
|---|---|
| Points | 254 / 254 observations and 134 / 134 avalanche records have `{lat,lng}` |
| Extent | about −114.97, 45.62 → −112.73, 47.53 |

**What observations report:**

| | |
|---|---|
| Instability | cracking 57 · collapsing 31 · avalanches observed 92 · triggered 24 · caught 2 |
| Snowpack text | 77 observations have a snowpack summary; 50 have avalanche-problem notes |

**What the avalanche records report:**

| | |
|---|---|
| Aspect | NE 36 · E 35 · SE 25 · N 14 · S 14 · W 5 · NW 3 · SW 2 |
| Elevation | present on all 134 |
| Size (`d_size`) | 1: 42 · 1.5: 34 · 2: 37 · 2.5: 15 · 3: 6 |
| Trigger | natural 82 · skier 25 · unknown 10 · … |
| Avalanche problem | Wind Slab 28 · Wet Loose 19 · Persistent Slab 17 · none recorded 45 · … |

**Personal data in the "public" payload:**

- **Names:** `name` is filled and `show_name: true` on 166 of 254 observations.
- **Photographers:** `media[].taken_by` holds a full name on **302 photos**. That includes
  reports where the observer chose *not* to be named: the sample report has `name: null` and
  `show_name: false`, but its photos carry the photographer's name.
- **Free text:** summaries average 615 characters and can mention parties and people.

Opting in to be named on WCMAC's site isn't consent to be named in someone else's onX folder.

### 1.6 What onX already has (VERIFIED, with inferences marked)

- **The onX logo on avalanche.org is a sponsor credit.** It sits under `Sponsored by` and is one
  of seven rotating logos: BCA, Wyssen, Austin Powder, MND, onX, Snowbound and Alpine
  Solutions. avalanche.org's danger map is its own Google Maps app, not onX.
- **onX help article 360056221571**, "Viewing Avalanche Forecasts and Incident Reports"
  (2026-09-16):
  - *"Avalanche Forecast zones in onX Backcountry are color-coded by danger level … based on
    data from the American Avalanche Association."*
  - *"Avalanche Incidents are marked on the map with a skull-and-mountain icon when Ski Tour is
    selected as your activity."*
- **INFERRED:**
  - The forecast layer reads the same open `v2 … map-layer` product that avalanche.org's own map
    uses. That's why clicking a zone in either place shows the same thing.
  - "Incidents" are most likely avalanche.org's accident records (involvements and fatalities),
    which are rare. They're not field observations.
- **No onX page found mentions field observations, snowpack reports or non-incident avalanche
  observations.** That's the gap.

### 1.7 onX's distribution constraints (VERIFIED in `docs/research/ONX_REIMPORT_AND_SHARING_2026-10-22.md`)

- **No public maps.** A recipient needs an onX account, and shared markups are *copied* into it
  as view-only. Sharing a folder needs Premium or Elite. **One share holds at most 100
  markups.**
- An account holds at most 3,000 markups. One import file holds at most 3,000 markups and 4 MB,
  in GPX or KML.
- Re-importing a file probably **duplicates** rather than updates (UNKNOWN, leaning duplicate).
- There's **no public upload API**. Markup import (`/v1/markups/import`) is internal to onX's
  web app.
- *"Shared Markups sync automatically to the recipient's account."* So adding markups to a
  folder that's already shared may reach existing recipients. That needs testing.

A full WCMAC season is about 390 markups if avalanches are separate points. That's **13% of a
rider's 3,000-markup cap** for one center and one season, so filtering or windowing is
mandatory.

---

## 2. What the feature is

### 2.1 Requirements

| # | Requirement | Why |
|---|---|---|
| R1 | Every point **links to the canonical report**: `…/observations/#/observation/<id>` or `#/avalanche/<id>` | The avalanche center stays the source of truth. onX is the index, not the record. |
| R2 | **Structured facts only**: date, point, zone, observer *type*, verified flag, aspect, elevation, D-size, trigger, avalanche problem, and instability flags | Enough to filter a map at a glance. Anything more belongs to the source. |
| R3 | **No names, photos, URLs, routes or free text** | Privacy (§1.5). Also keeps markups small. |
| R4 | **Attribution and a disclaimer on every point**, in wording WCMAC approves | It isn't a forecast, and it may be stale. |
| R5 | **Data access only through a sanctioned credential** granted by A3 | §1.4 |
| R6 | **Season-aware, low-frequency refresh**: weekly in season, keyed on `last_updated`, and nothing when `off_season` is true | Median posting delay is 1 day and 43% of reports get edited. About 5 requests cover a whole season. |
| R7 | **Bounded size**: rolling windows or filtered folders, ≤ 100 markups per shared folder | onX limits (§1.7) |
| R8 | **Center-agnostic code**: `center_id` is a parameter | The same API serves every center that uses the NAC widget (INFERRED). Each center still needs its own permission. |
| R9 | **No forecast danger ratings in markups** | onX already has them live. A stale copy is worse than none. |

### 2.2 Delivery paths

| Path | What it is | Reach | Automation | Recommendation |
|---|---|---|---|---|
| **A. Downloadable file** | The pipeline publishes `wcmac-obs-<window>.kml/.gpx`, and riders import it | Anyone. It also works in CalTopo, Gaia and others | Automatic up to the download | **Build first.** It's exactly what Cairn produces today. |
| **B. Curated shared folder** | One account imports a rolling "last 14 days" file and shares a view-only link | onX account holders. The curator needs Premium/Elite | Manual import per release | **Second**, after testing whether additions propagate to recipients |
| **C. Native onX layer** | onX ingests the observations feed next to its forecast layer | Every onX user | onX's job | **The real goal.** Pitch it as *"extend your existing A3 feed from zones to points"* |
| **D. CalTopo companion map** | The same file on a CalTopo map with URL or Public sharing | Anyone, with no login | Manual or CalTopo API | Optional, as a no-account preview |

### 2.3 Architecture (for Paths A, B and D)

```
 GitHub Action (cron, weekly Nov–Apr; skip when center.off_season)
   │  GET obs/v1/…/observation/list + avalanche_observation/list   ← A3-issued token, never Origin spoofing
   │  incremental: fetch since last run; re-fetch rows with newer last_updated
   ▼
 cairn/io/nac_observations.py      NEW READER: NAC JSON → MapDocument
   │  privacy filter (R3) · avalanche ⊂ observation dedup by id · window/filter (R7)
   ▼
 MapDocument{folders, waypoints}   unchanged model
   ▼
 existing onX writers              icon/colour mapping · 3.75 MiB auto-split · folder runbook
   ▼
 wcmac-obs-<window>.kml/.gpx + manifest.json {generated_at, source, counts, attribution}
   ▼
 static hosting next to the Vercel site → web/ "Avalanche Bridge" page with download + import steps
```

**Why it's shaped this way:**

- **Reader/writer rule.** AGENTS.md says to add a format by adding a reader. The reader is pure,
  so it's testable against a small **synthetic** fixture. Never use real observations as test
  data.
- **It has to be a server-side job.** The observations API's CORS allows only
  `https://missoulaavalanche.org`. Cairn's Pyodide app can't call it from the browser, and
  shouldn't. This is **Cairn's first server-side component**, so it needs a decision record.
- **Forecast polygons are optional and on hold.** The three WCMAC zone polygons (Bitterroot
  1724, Rattlesnake 1723, Seeley Lake 1722) could ship as plain context shapes with no danger
  colour (R9). That's only useful if a rider's onX doesn't already show them, and it does.

### 2.4 Markup design (draft)

**Folders** per center and window:

- `WCMAC Avalanches (last 14 d)`
- `WCMAC Instability: cracking/collapsing`
- `WCMAC Field obs`

Split by zone if a share would go over 100 markups.

**Names** are short, because onX lists by name: `04-18 D2 N 8200' Gash`,
`01-12 Collapsing · Rattlesnake`.

**Icons** come from the existing catalog (`cairn/data/icon_catalog.yaml`: `Hazard`, `danger`,
`Avy hazard area`), one per folder.

**Colour encodes one dimension only**, out of onX's 10 waypoint colours. Pick one of:

- D-size
- age (fresher = hotter)
- observer type (forecaster / pro / public)

**Notes** are plain text:

```
Avalanche D2 · N · 8200 ft · trigger AS (skier, unintentional)
Problem: Wind Slab · Zone: Bitterroot · Forecaster-verified
Observed 2026-04-18 · reported by a public observer
Full report: https://missoulaavalanche.org/observations/#/avalanche/<id>
Source: West Central Montana Avalanche Center. Not a forecast — check today's
advisory at missoulaavalanche.org before you go.
```

**Open writer questions:**

- Does onX make the URL tappable? (UNKNOWN)
- Does onX render line breaks? (UNKNOWN)
- The URL contains `#`. The parallel GPX/KML roadmap session is adding a test that `#` and URLs
  survive in notes, `<desc>` and KML descriptions. Its `&`/`#` name-stripping fix is in Phase 1
  of `docs/ROADMAP_ONX_ROUND_TRIP.md`.

---

## 3. Phases

Each phase has a gate. Nothing after Phase 0 starts without a written yes.

### Phase 0: Permission and terms (people, about 2–6 weeks, no code)

- **WCMAC (content)**, starting with the contact page or a board member. Show them §0 and a
  mockup. Ask:
  - May published observations be redistributed as points with deep links?
  - What attribution and disclaimer text do they want?
  - Should anything be excluded, such as incidents, unverified public reports or a minimum age?
  - Would they rather host or own the file themselves?
- **avalanche.org / A3 (access).** Their API root asks for exactly this. Ask for a token or an
  allowlisted origin, rate expectations and terms, and whether other centers would be welcome
  later. Ideally WCMAC makes the introduction, since they're already a platform tenant.
- **onX (optional, for Path C).** onX already has an A3 data relationship and an onX logo in
  A3's sponsor bar. A three-way conversation is natural. Share nothing with onX before WCMAC and
  A3 agree.
- **Gate:** written permission from WCMAC and A3, including the attribution text. If either
  says no, **stop**. The only fallback is WCMAC producing its own export.

### Phase 1: Prototype file (about 1–2 days)

- `cairn/io/nac_observations.py`, plus a synthetic fixture and tests covering:
  - the privacy filter, asserting no `name` or `taken_by` reaches the output;
  - avalanche/observation dedup;
  - deep-link format.
- A script that fetches one season with the granted credential and writes KML/GPX.
- Hand-import into a `ZZ`-prefixed onX test folder. Check:
  - icons, colours and name lengths;
  - whether note line breaks are kept;
  - **whether the link can be tapped on mobile**.

  Then clean up.
- **Gate:** WCMAC reviews screenshots and the note wording.

### Phase 2: Published rolling file (about 2–3 days)

- A GitHub Action on an in-season cron, publishing a static file and `manifest.json`.
- A `web/` page with downloads, attribution and import steps. It's a static link: the browser
  never calls the API.
- Two-account test: does adding to an already-shared folder sync to recipients? Does
  re-importing duplicate?
- **Gate:** a month in season with no concerns from WCMAC, and feedback from a few riders.

### Phase 3: onX distribution

- **B:** a curated view-only folder with a rolling window of ≤ 100 markups.
- **C:** a pitch to onX with the prototype, usage numbers and WCMAC/A3 endorsements:
  *"you already show A3's zones and incidents; here's the point-level layer, same API, center
  by center."*

### Phase 4: Other centers (only on request)

- Change `center_id` and repeat Phase 0 with that center. Check first that the center actually
  uses the NAC observation widget.

---

## 4. Open questions

| # | Question | Who answers |
|---|---|---|
| 1 | Does WCMAC allow redistributing observation points and links? It has no published terms. | WCMAC |
| 2 | Will A3 issue a credential to a non-commercial third party, and on what terms? | A3 / avalanche.org |
| 3 | Do the open v2 forecast endpoints carry any usage terms? They answer anyone, but the API root says "contact for permission". | A3 |
| 4 | Include public reports, or only `forecaster_verified` and professional ones? | WCMAC |
| 5 | Are URLs in onX notes tappable? Are line breaks kept? | One test import |
| 6 | Do additions to a shared folder sync to existing recipients? | Two-account test |
| 7 | Does onX already plan an observations layer? | onX (Path C conversation) |
| 8 | Is a one-off history layer from the WordPress archive (≤ Dec 2022) worth it? | WCMAC. Probably not. |

## 5. Risks

- **Stale safety data shown as current.** The mitigations are R4, R6 and R9, plus a rolling
  window and the `generated_at` date in every folder name.
- **Platform drift.** The widget is versioned (`20261014`), and the API is undocumented, so
  field names can change. Mitigations: pin the parsing in reader tests, and fail loudly on
  schema change.
- **Privacy regression.** A future change could start emitting `taken_by` or summaries. A test
  must assert it never happens.
- **Markup budget.** One season is about 13% of a rider's cap. Windowing is required, not
  optional.
- **Cairn takes on a server.** The first non-Pyodide component needs a decision record in
  `docs/design/DECISIONS.md` before it's built.

## 6. Sources (all fetched 2026-10-22)

**missoulaavalanche.org:**

- `/observations/`, `/submit-an-observation/` (301 → `#/form`), `/forecasts/`,
  `/avalanche-forecasts/`, `/observations-archive/?season=2022|2023|2026`, `/robots.txt`
- WordPress REST: `/wp-json/wp/v2/pages` (pages 2 About, 9482 FAQ, 15, 13, 2929, 9606, 10544,
  21971), `/wp-json/wp/v2/types`, `/wp-json/wp/v2/advisory` (677), `/wp-json/wp/v2/gallery`
  (33)

**NAC widget:**

- `du6amfiq9m9h7.cloudfront.net/loader/nac-widget-loader.min.js`
- `…/public/v2/20261014/observations.js` (routes, API client, query builders)

**api.avalanche.org:**

- the root page
- `v2/public/products/map-layer[/WCMAC]`
- `v2/public/products?avalanche_center_id=WCMAC`
- `v2/public/product/184616`
- `v2/public/avalanche-center/WCMAC`
- `obs/v1/public/observation/<id>` and the list endpoints (Origin-header probe, §1.4)

**avalanche.org:**

- home page sponsor bar
- `wp-content/themes/avalanche.org-theme/includes/ndm-app/dist/build.js`

**onX:**

- help 360056221571 (Zendesk API)
- `onxmaps.com/backcountry/app/features/ski-splitboard`
- `docs/research/ONX_REIMPORT_AND_SHARING_2026-10-22.md` §2

**Repo:**

- AGENTS.md (the reader/writer architecture)
- `cairn/core/writers.py:77-93,505`
- `cairn/data/icon_catalog.yaml`
- `docs/ROADMAP_ONX_ROUND_TRIP.md`
