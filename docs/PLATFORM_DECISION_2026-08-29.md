# Platform decision: should Cairn be a web app? — 2026-08-29

**Decision: yes — move. Adopt Option G (hybrid), implemented via Option B mechanics: a static,
client-side web app on GitHub Pages that runs the existing Python engine in the browser via
Pyodide, with the CLI retained for scripting and the TUI frozen and eventually removed.**
No server. No upload. The map data never leaves the user's machine.

This document gives the reasoning, the quantified cost, the sequencing, the red-team attack on
the recommendation, and the revision that attack forced. Claims are marked **[verified]**
(checked this session, in-repo or via cited URL) or **[inferred]** (standard knowledge or
estimate, not re-verified today).

---

## 1. The two facts that decide it

**Fact 1 — the terminal is a detour in the middle of a browser workflow.** [verified —
`docs/PLATFORM_CONSTRAINTS_2026-08-29.md`] The end-to-end job is: export from CalTopo (browser)
→ run Cairn (terminal, the only non-browser step) → import to onX (browser, mandatorily so for
the 6 KML files of the 24-file real-map export, since onX accepts KML only via its Web Map).
The user starts in a browser and must end in a browser. Cairn is the one step that makes a
non-developer audience — hikers, hunters, SAR volunteers — leave it for
`git clone && uv sync && uv run cairn tui`, which `docs/DISTRIBUTION_2026-08-29.md` correctly
calls a Tier-0 adoption wall.

**Fact 2 — 65% of the codebase is interface for the platform that is the adoption blocker.**
[verified — measured this session] Of 20,155 lines:

| Category | Lines | Share | Fate under a web move |
|---|---|---|---|
| **Engine** (parsers, writers, model, mapping, dedup, merge, config) | **7,130** | 35% | **Reused as-is** (Pyodide) |
| **Interface** (TUI, `core/preview.py`, typer commands, rich prompts) | **13,025** | 65% | Discarded / frozen |

The single largest file in the repo (`cairn/tui/app.py`, 3,841 lines) is interface. So is
`core/preview.py` (1,946 lines, 129 console/prompt call sites — it lives in `core/` but is
interface). The thing Cairn is *for* — the transformation, the judgement-layer preservation —
is 7,130 lines of pure Python with stdlib-only imports (`xml.etree`, `json`, `hashlib`,
`pathlib`) plus `pyyaml` for the two mapping catalogs [verified — grep of
`cairn/core/writers.py`, `cairn/io/caltopo_geojson.py`; only `config.py` and
`icon_registry.py` import yaml]. It is pure data transformation: no OS calls, no network, no
long compute. It runs in a browser tab.

When 65% of your code serves the platform that blocks 100% of your target users, the platform
is the bug.

## 2. Verdict on the four theses

- **T1 (client-side-only is strictly better)** — **substantially true, not "strictly."**
  Client-side does simultaneously kill the privacy objection (hunting spots, SAR data, cabins
  stay on-device), the hosting-cost objection (GitHub Pages, $0), and the install objection
  (click a link). What it does *not* strictly dominate is scriptability (see T4) and a ~10 MB
  first-load download (see §4B).
- **T2 (the task is inherently visual)** — **true, with one fantasy trimmed.** Icon and color
  assignment in a browser shows the actual glyph and the actual swatch; the TUI shows the
  string `"c:target"` and a color name. That is a real fidelity gap in the product's core
  interaction. The map preview is *not* a fantasy requiring an API key and budget — MapLibre
  GL JS + a self-hosted PMTiles basemap is static-hostable with no tile server and no API key
  [verified — https://docs.protomaps.com/pmtiles/maplibre,
  https://maplibre.org/maplibre-gl-js/docs/examples/pmtiles-source-and-protocol/] — but a
  regional basemap file is tens-to-hundreds of MB and needs hosting thought, so it is a
  phase-3 feature, not a launch feature. A launch-viable middle ground: plot waypoints/tracks
  on a blank canvas or against OSM raster tiles fetched live (online-only, fine per §5.5).
- **T3 (interactive import runbook)** — **true and it is the sleeper killer feature.** The
  9-folder real map yields 24 files needing 24 ordered manual imports with a
  new-vs-existing-folder choice each time, 6 web-only; done naively the user gets 24 junk
  folders [verified — PLATFORM_CONSTRAINTS doc]. A web page can hold that state: check off
  imports, hand over one file at a time in order, deep-link the onX Web Map. A markdown
  runbook (already designed, near-zero cost) is the floor; the interactive checklist is the
  ceiling — and it is only reachable on the web platform.
- **T4 (the counter-case: CLI scriptability and 652 tests)** — **real but smaller than it
  looks, and the hybrid keeps most of it.** Quantified in §5.2: the 107 TUI tests are the
  *unreliable* ones (35 swallow exceptions and assert nothing — see
  `.claude/skills/cairn-tests/SKILL.md`); the 342 engine tests are the trustworthy ones and
  survive **unchanged** under Pyodide, because the shipped code *is* the tested Python.
  Scriptability survives because the CLI is retained (and `--no-interactive` finally fixed).

## 3. Options evaluated

### A. Static SPA, engine ported to TypeScript — *strong second, not now*
Full rewrite of the 7,130-line engine (~5–6k lines of TS [inferred]) plus a new UI. Best
runtime (no WASM download, instant load, mobile-friendly), best long-term home if the web wins.
Costs: months of solo porting; the 342 engine tests must be reimplemented or replaced by a
golden-file oracle (§5.2 — good but not free: the writers embed `uuid.uuid4()` and
`datetime.now()` for features lacking ids/timestamps [verified — `cairn/core/writers.py:51,
461,479,687,891,912,1026`], so byte-for-byte comparison requires injecting a deterministic
clock/uuid seam or normalizing output first). Every future fix lands twice if the CLI stays
Python. **Rejected as the first move; retained as the pre-planned fallback (§8).**

### B. Static SPA via Pyodide — *chosen mechanism*
Run the existing engine in-browser via WASM. **Zero logic rewrite; zero engine-test rewrite.**
- Runtime is ~10 MB; first load 5–30 s on typical connections, 2–4 s warm from cache
  [verified via secondary sources — https://pyodide.org/en/stable/usage/downloading-and-deploying.html,
  https://publishing-project.rivendellweb.net/running-python-data-science-libraries-in-the-browser-with-pyodide/;
  exact numbers to be re-measured in the Phase-1 spike].
- `pyyaml` ships as a prebuilt Pyodide package [verified —
  https://pyodide.org/en/stable/usage/packages-in-pyodide.html via search extraction];
  `xml.etree`, `json`, `hashlib` are stdlib and included [inferred — stdlib is bundled apart
  from a short unvendored list; the spike must confirm `xml.etree` specifically].
- The engine's other deps (typer/rich/textual/prompt-toolkit) are interface-only and simply
  not loaded [verified — import grep].
- Acceptability for this audience: this is a pre-trip task done at home on broadband (§5.5). A
  one-time 10 MB load behind a progress bar, cached by a service worker thereafter, is
  acceptable for a desktop planning tool. It would *not* be acceptable for a field/mobile
  tool — which this is not.

### C. Server-side web app (FastAPI + upload) — *rejected*
Head-on, as demanded: the privacy problem is not stylistic. This audience uploads hunting
spots, SAR operational data, and the coordinates of their own cabins. "We don't log uploads"
is a promise; "the data never leaves your machine, verifiable in DevTools' network tab" is a
property. Cost side: a solo maintainer signs up for a domain, TLS renewal, uptime, patching a
public upload endpoint (file-parsing services are a classic attack surface), abuse handling,
and a monthly bill — forever, for a tool with no revenue. Rejected without reservation; B
delivers the same UX with neither problem.

### D. `textual serve` — *rejected*
The README positions it for local/self-hosted use, spawns a subprocess per browser session,
offers no auth/HTTPS/scaling guidance, and points public deployments to textual-web
[verified — https://github.com/Textualize/textual-serve]. It is also the worst of both
worlds: server costs and privacy exposure of C, terminal UX of F, one OS process per visitor.
Demo-only. It would additionally inherit the TUI's file-browser model, which makes no sense
for a visitor whose file is on *their* machine, not the server's.

### E. Desktop app (Tauri/Electron) — *rejected*
Solves nothing C/F don't and adds the worst tax: per-platform builds, macOS notarization
($99/yr) *and* Windows code signing, auto-update infrastructure, 3-platform QA — for a UI
that would be web technology anyway. If the UI is HTML, ship the HTML. Tauri becomes
interesting only if an offline-required desktop artifact is ever demanded; a PWA covers most
of that for free (§5.5).

### F. Stay CLI/TUI, fix distribution — *partially adopted, insufficient alone*
Phases 1–2 of `docs/DISTRIBUTION_2026-08-29.md` (PyPI as `cairn-maps`, standalone binaries)
are cheap, already designed, and worth doing regardless — they serve the technical slice and
keep the CLI leg of the hybrid healthy. But that document itself concedes the ceiling: every
terminal option is scored "❌/⚠️ for a hiker," and only "hosted web version" scores ✅✅. A
signed binary still lands a non-developer in a terminal facing a keyboard-driven TUI to do a
visual task. Distribution fixes shrink the wall; they do not remove it.

### G. Hybrid: shared core, web for humans, CLI for scripts — *chosen*
"Shared core" is usually where hybrids die: an abstraction layer nobody wanted. Here it is
concrete and cheap, because **the shared core already exists as the 7,130-line engine, and
Pyodide lets the web app import it verbatim.** In practice it means one refactor with a knife,
not an architecture: `cairn-core` (model, io, core minus preview/icon_picker, the two YAML
catalogs) importable without typer/rich/textual, plus one new function —
`plan_import(export_result) -> ImportPlan` — used by both the CLI's markdown runbook and the
web checklist. The interface packages (`cairn/commands`, `cairn/tui`) depend on it downward;
nothing depends on them. The indirection cost is a `pyproject` workspace split and import-path
discipline. That's it. Worth it.

## 4. Required analysis

### 4.1 What is reused, rewritten, discarded [verified — measured]

| Asset | Size | Under G/B (chosen) | Under A (TS port) |
|---|---|---|---|
| Engine code | 7,130 LOC | **Reused verbatim** | Rewritten (~5–6k TS) |
| Mapping catalogs `cairn/data/*.yaml` | 566 lines | Reused (data) | Reused (data) |
| Interface code | 13,025 LOC | CLI kept (~2.7k), TUI+preview frozen→removed (~10.3k) | Discarded |
| Web UI | — | **New: ~3–5k LOC JS/HTML** [inferred] | New, similar |
| Fixtures (bitterroots 1.7 MB, edge_cases, etc.) | — | Reused | Reused as oracle inputs |

The new web UI is the irreducible cost of every web option — Pyodide saves the engine, not
the interface. But note what the web UI does *not* have to reimplement from the TUI's 7,907
lines: no file browser (the browser's file picker), no keyboard-focus management, no
DataTable cursor-preservation machinery, no overlay/modal framework — the DOM provides all
of it. The TUI's size is partly the cost of building UI primitives a browser gives away.

### 4.2 Testing

- **342 engine tests survive unchanged** and keep testing the exact bytes that ship — this is
  the decisive testing argument for Pyodide over a port. Add one CI job running the engine
  suite *under Pyodide in Node* to catch WASM-specific drift [inferred — standard Pyodide CI
  pattern; spike confirms].
- **107 TUI tests are discarded — and they are the bad ones.** 35 swallow exceptions and
  assert nothing; the repo's own test skill documents that green TUI tests cannot be trusted.
  Discarding them sheds liability, not coverage. The remaining ~200 CLI/config/session tests
  survive with the CLI.
- **The golden-file oracle (relevant if the A-fallback ever fires):** running the 342-test
  fixture corpus through the Python engine and diffing a TS port's output byte-for-byte is
  genuinely strong for parsers/writers — *after* fixing nondeterminism. `writers.py` calls
  `uuid.uuid4()` and `datetime.now()` when features lack ids/timestamps [verified — lines
  51, 461, 479, 687, 891, 912, 1026], so the oracle needs injected clock/uuid seams (a small,
  worthwhile refactor even today). Caveat honestly: the oracle validates transformation
  output, not error messages, warnings, or edit-session semantics — those need ported tests.
- **Web UI testing:** Playwright E2E against the static page, using the same fixtures
  (drag-in file → assert downloaded zip contents byte-equal to CLI output). Budget ~15–25
  E2E tests [inferred]. Compare honestly: Playwright tests real Chromium/WebKit and is
  industrial-grade; the current TUI harness is the thing the repo itself flags as
  untrustworthy. Web testing here is an *upgrade*, not a concession.

### 4.3 Deployment

- **Chosen (G/B):** GitHub Pages. CI = build step (bundle JS, vendor Pyodide runtime or pull
  from jsDelivr with SRI pins, package the engine as a wheel) + deploy on tag. No servers, no
  certificates, no uptime pager, no security surface beyond supply-chain pinning of ~3 JS
  deps (fflate for zip, MapLibre later) [inferred: fflate/JSZip client-side zip of 24 small
  files — total ≪4 MB each by onX's own cap — is trivially within browser limits]. This is
  *less* operational surface than the PyPI+binaries pipeline already designed in
  DISTRIBUTION doc (which involves a CI matrix and macOS signing), and both are one-shot
  setups.
- **Server option (C), for contrast:** domain, TLS, host bill, patch cadence, upload abuse —
  a permanent second job. This asymmetry is most of why C lost.

### 4.4 Ease of iteration

Web wins for reach-speed: `git push` → every user has the fix on next reload; no version
skew, no "please upgrade" support threads. The cut-both-ways honesty: users can't pin a known
-good version, and a bad deploy hits everyone instantly — mitigated by the engine suite + E2E
gate in CI, and by Pages serving from a branch you can revert in one command. The CLI leg
keeps pinning (`uv tool install cairn-maps==x.y.z`) for whoever needs it. Solo-maintainer
fix latency: edit Python engine → the *same file* ships to web and CLI. Under A, every engine
fix lands twice; that alone justifies B over A for a solo maintainer.

### 4.5 Offline

Judged from the actual workflow, not assumed: both endpoints of the job are browser tasks,
and the onX end is *mandatorily* a desktop Web Map for KML [verified — PLATFORM_CONSTRAINTS].
You cannot even *start* the workflow (CalTopo export) or *finish* it (onX import) without
connectivity. **This is a pre-trip, at-home, connected task. Offline support is close to
irrelevant to the core job.** Therefore: no PWA requirement at launch. Do the cheap version —
a service worker that caches the app shell and Pyodide runtime — because it also gives the
2–4 s warm start, and it incidentally makes the converter itself work offline. Do not build
offline basemaps, background sync, or installability beyond that. Any user who genuinely
needs fully-offline conversion is a terminal-capable outlier already served by the CLI.

## 5. Migration plan

**Phase 0 — ship the runbook (days, platform-independent).** Replace `ICON_REPORT.md` with
the generated import-plan markdown per PLATFORM_CONSTRAINTS §"cheap to build". Also resolve
the two open onX questions (folder naming; native KML `<Folder>` support — ten minutes with
an onX account) because they shape the web checklist. Also fix `--no-interactive` — the CLI
leg of the hybrid is broken without it.

**Phase 1 — spike (1–2 weeks, kill-or-commit gate).** A single static page: load Pyodide,
`import cairn` engine, drag in `Bitterroots__Complete_.json`, download the 24-file zip
byte-identical to CLI output (seeded uuid/clock). Measure: total transfer, cold and warm
start on a mid-range laptop and a phone, and confirm `xml.etree`+`pyyaml` under Pyodide.
**Gate: warm start ≤5 s desktop and total download ≤15 MB, or divert to the A-fallback.**

**Phase 2 — engine extraction (1–2 weeks).** Split `cairn-core` (engine + YAML + the new
`plan_import()`) from interfaces; move `preview.py`/`icon_picker.py` out of `core/`; add
clock/uuid seams; CI runs the 342 engine tests on CPython *and* Pyodide/Node. CLI and TUI
keep working throughout. This work is valuable under every option including F.

**Phase 3 — the web app MVP (4–8 weeks solo, part-time [inferred]).** Drag-in → folder tree →
edit names/icons (real glyphs)/colors (real swatches)/notes → export zip → **interactive
import checklist** with per-file "done" state and web-only badges on KML files. Playwright
E2E. Ship on Pages; README gains "Use Cairn in your browser" as the first line, CLI install
second. TUI enters freeze: bugfixes only, no new features.

**Phase 4 — map preview + polish (ongoing).** MapLibre + PMTiles regional basemap or
online-only raster tiles; visual diff between source and what onX will show.

**Point of no return:** end of Phase 3, when the README flips and the first web-only feature
(checklist state) exists. Phases 0–2 are no-regret under every option, including staying.
Explicitly *not* planned: deleting the CLI. Deleting the TUI happens one release after web
usage demonstrably exceeds TUI usage (a Pages hit counter vs. informal CLI feedback — accept
imprecision), reclaiming ~7,900 lines and the 107-test liability.

## 6. Red team — the case against the recommendation

*Switching sides. The strongest honest attack:*

1. **"Zero rewrite" is marketing.** Pyodide saves 7,130 lines, but the product's hard-won UX
   is the *other* 10,000 — three months of TUI editing interactions, cursor preservation,
   bulk-edit flows, filter/search. All of that is rebuilt in JS regardless. You are not
   porting an app; you are writing a second app that shares a library, and second systems
   balloon. The 4–8-week Phase 3 estimate is the classic underestimation: multiply by 2–3
   for a solo part-timer and it's a half-year before parity.
2. **You now maintain two platforms forever.** Every user-visible behavior needs a web
   implementation, a CLI story, and (until the freeze ends) a TUI answer. Solo maintainers
   die of surface area. F+runbook is one platform and the DISTRIBUTION doc already wrote its
   plan.
3. **Pyodide is a permanent weight vest.** 10 MB and a WASM boot forever, on every user, to
   avoid porting 7k lines *once*. Mobile Safari memory pressure and iPad users are unserved.
   Meanwhile the TS port (A) is smaller than it sounds: writers+parsers+mapper are
   mechanical, the YAML catalogs are data, and the oracle exists. Choosing B may be choosing
   comfort over the correct end-state — and doing the B UI first means the eventual port
   happens *anyway*, later, with more surface.
4. **"No install" may not convert.** The wall might not be the terminal; it might be that
   nobody knows Cairn exists. Zero-friction products with zero distribution still get zero
   users. You could ship the web app to the same silence.
5. **What breaks for existing users:** TUI freeze strands whoever actually likes it; web
   file-handling is real friction too (Safari lacks `showSaveFilePicker`, so it's a plain
   zip download [inferred]; drag-in of a 20 MB GeoJSON into WASM memory needs testing).
6. **The oracle over-promises.** Byte-for-byte only works after the determinism refactor, only
   covers happy-path transformation, and silently blesses ported *bugs* as correct behavior.

## 7. Revision in response

The attack changes the plan in four concrete ways; it does not flip the decision, because
attack #1–#3 all concede the central fact — the UI must be rebuilt for the web under *every*
web option, and no non-web option reaches the audience. What changes:

1. **(re: #1) Scope the MVP down and say the multiplier out loud.** Phase 3 MVP is
   *convert + rename + icon/color + checklist* — explicitly **not** parity with the TUI's
   filter/search/bulk-edit/A-B-preview features. Parity is not the goal; the TUI accreted
   features because the terminal made the basics hard. Budget honestly: 4–8 weeks is the MVP
   floor; plan for 3 months elapsed.
2. **(re: #3) Pre-commit the fallback and the tripwires.** The Phase-1 gate is now binding:
   if warm start >5 s or download >15 MB, or if within 6 months of launch mobile/tablet
   demand is real, execute Option A *for the engine only* — the Phase-2 seams and the oracle
   are built in advance precisely so this swap replaces the WASM engine under an unchanged
   UI. B is the fast door in; A remains the pre-paid exit.
3. **(re: #2) Cap the platforms at two, by calendar.** TUI freeze begins at Phase 3 launch
   and TUI *removal* is scheduled (not "eventually"): the second release after launch, ~-7,900
   LOC and -107 tests. End state is web (humans) + CLI (scripts) sharing one engine — the
   same count of maintained interfaces as today's TUI+CLI, with the unreliable half of the
   test suite deleted.
4. **(re: #4) Treat discovery as part of the migration.** The web app *is* the distribution
   fix (a URL is shareable in a way `uv sync` never was — forum posts, CalTopo community,
   r/CalTopo, SAR mailing lists), but Phase 3 now includes the unglamorous launch work:
   README rewrite, a 90-second demo GIF, and posting where the users are. #4 is right that
   friction removal without reach is silence.

Attacks #5 and #6 are absorbed as line items: plain-zip download as the universal path
(no File System Access API dependency), a 20 MB-input memory test in the Phase-1 spike, and
the oracle documented as necessary-not-sufficient (ported code also gets new unit tests for
error paths).

## 8. Bottom line

- **Do:** Phase 0 runbook now; Pyodide spike with a binding kill gate; engine extraction
  (no-regret); web MVP on GitHub Pages; PyPI `cairn-maps` in parallel (it's hours).
- **Don't:** rent a server, serve the TUI over HTTP, build a desktop app, build offline
  support beyond runtime caching, or chase TUI feature parity.
- **Cost:** ~3 months part-time to MVP; ~3–5k new LOC; 107 unreliable tests deleted; 342
  trustworthy tests retained against the shipping engine.
- **Payoff:** install friction goes from "git clone + uv + terminal" to a link; the two
  worst product gaps (icon/color fidelity, the 24-import minefield) become solvable only on
  this platform; privacy and hosting cost stay at zero by construction.

## Sources

- Pyodide size/start: https://pyodide.org/en/stable/usage/downloading-and-deploying.html · https://publishing-project.rivendellweb.net/running-python-data-science-libraries-in-the-browser-with-pyodide/ · https://www.npmjs.com/package/pyodide
- Pyodide packages (pyyaml): https://pyodide.org/en/stable/usage/packages-in-pyodide.html · https://pyodide.org/en/stable/usage/loading-packages.html
- textual-serve positioning: https://github.com/Textualize/textual-serve
- Keyless self-hosted maps: https://docs.protomaps.com/pmtiles/maplibre · https://maplibre.org/maplibre-gl-js/docs/examples/pmtiles-source-and-protocol/ · https://protomaps.com/api
- In-repo: `docs/PLATFORM_CONSTRAINTS_2026-08-29.md`, `docs/DISTRIBUTION_2026-08-29.md`, `.claude/skills/cairn-tests/SKILL.md`, LOC/import/test measurements dated 2026-08-29.

---

## Appendix — independent verification of the load-bearing claims

The recommendation above rests on "the engine runs standalone." That was asserted from an import
grep. A grep is not sufficient evidence for an import claim, so it was tested directly. Results
below; one claim was **wrong**, and the correction matters.

### ✗ CORRECTED — the engine does NOT currently import without the CLI stack

`cairn/__init__.py:7` is `from cairn.cli import app, main`. Because Python executes a package's
`__init__` before any submodule, importing *any* engine module drags in the entire CLI:

```
$ uv run --no-project --with pyyaml python -c "import cairn.core.writers"
ModuleNotFoundError: No module named 'typer'

engine modules importable without typer/rich/textual: 0/13
```

All 13 fail. So "zero rewrite, just import it" is **not true of the code as it stands** — Phase 2
(engine extraction) is a hard prerequisite for Pyodide, not an optional tidy-up.

### ✓ CONFIRMED — but the extraction is genuinely cheap

Simulating the split — engine packages copied out, `__init__.py` emptied, `preview.py` and
`icon_picker.py` (the two interface files inside `core/`) removed — everything imports:

```
imported OK: 19/19
```

No hidden coupling to typer, rich, textual, or prompt-toolkit anywhere in the engine. The eager
`__init__.py` was the only blocker.

### ✓ CONFIRMED — the extracted engine performs a real transformation

Not just imports — a full run against the 1.7 MB production fixture, with **pyyaml as the only
installed dependency**:

```
parsed: 10 folders
68 waypoints, 17 shapes
wrote GPX: 15,114 bytes, 68 <wpt>, 68 icons
wrote KML: 24,351 bytes, 17 placemarks
```

This is the empirical basis for the Pyodide recommendation: stdlib + pyyaml, no OS calls, no
network. It is the strongest single piece of evidence in this document, and it now exists.

### ✓ CONFIRMED with a caveat — output is already reproducible on the main path

The concern that `uuid.uuid4()` and `datetime.now()` block byte-for-byte oracle testing is
**overstated for the primary case**. The uuid calls are fallbacks — `(feature.id or "").strip() or
str(uuid.uuid4())` (`writers.py:461,687,912,1026`) — so they only fire for features lacking an id.
CalTopo GeoJSON carries ids, so two runs are already identical:

```
run1=1cc93a988254b825  run2=1cc93a988254b825   reproducible
```

The caveat stands for inputs whose features lack ids — notably onX GPX (`io/onx_gpx.py:47`) and
KML (`io/onx_kml.py:29`), which mint uuid4 on read. The determinism seam is therefore worth
building, but it is **not a blocker for the CalTopo → onX direction**, which is the direction the
web MVP serves. Timestamps are unaffected: they only appear when `add_timestamps=True`.

### Net effect on the plan

The recommendation survives, and its central technical premise is now demonstrated rather than
asserted. One sequencing change: **Phase 2 (engine extraction) must precede the Phase 1 spike**,
or the spike cannot import the engine at all. The extraction is small — empty the package
`__init__`, relocate two files — and it is worth doing regardless of platform, since an eager
`__init__` that imports typer also slows every CLI invocation and every test run.
