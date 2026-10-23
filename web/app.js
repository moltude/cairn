/* Cairn web app — UI shell.
   All map logic is the existing Python engine, running in Pyodide. */
let py = null, DATA = null, EDITS = {}, SEL = new Set(), ZIP = null, MANIFEST = null;
let ANCHOR = null;   // last row clicked without shift -- the pivot for range select

/* Every filter lives here; the rail facets (Type, Folders, Icon), the chips and
   #only-attention all render FROM this object, and visibleItems() reads only
   it -- so select-all and shift-range automatically respect every filter. */
const FILTERS = { q: "", kind: "", folder: null, icons: new Set(), attention: false };
const DEFAULT_PIN = "\u0000default";   // facet key for "fell back to the default pin"
const COLLAPSED = new Set();           // folder sections the user folded away
const RAIL_FOLDED = new Set();         // rail filter sections folded away (UI-28); view only
let NOTE_EDIT = null;                  // {uid, draft} -- the one note open for editing
let POP = null;                        // single-item icon & color popover state
let BULK = null;                       // several-items dialog state

const $ = s => document.querySelector(s);
const setStatus = (t, cls = "") => { const e = $("#status"); e.textContent = t; e.className = "status " + cls; };

/* Keyboard focus across re-renders. The rail and the list are rebuilt with
   innerHTML, which drops focus to <body>. Every control they rebuild carries a
   data-fk key that is stable across renders (row uid / folder key / facet key
   plus which control); capture it BEFORE rebuilding -- once the node is gone,
   activeElement is already <body> -- and focus the same key afterwards. A row's
   note button and its open editor share one key, so Save/Cancel land back on
   the note button. A key that no longer exists is a silent no-op. */
const focusedKey = () => document.activeElement?.dataset?.fk || null;
function refocus(k) {
  if (!k || focusedKey() === k) return;
  const el = [...document.querySelectorAll("[data-fk]")].find(e => e.dataset.fk === k);
  if (el) el.focus({ preventScroll: true });
}

/* Modals keep Tab and Shift+Tab inside their card. Computed at keydown time:
   the bulk dialog rebuilds its icon grid on every pick. */
const FOCUSABLE = 'button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])';
function trapTab(e, card) {
  const els = [...card.querySelectorAll(FOCUSABLE)].filter(el => el.getClientRects().length);
  if (!els.length) return;
  const first = els[0], last = els.at(-1), a = document.activeElement;
  if (!card.contains(a)) { e.preventDefault(); first.focus(); }
  else if (e.shiftKey && a === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && a === last) { e.preventDefault(); first.focus(); }
}

let PENDING_FILES = null;
async function boot() {
  try {
    // Everything starts at once: Pyodide (whose big files index.html already
    // preloads) alongside our three files, instead of one after another.
    //
    // The engine wheel, bridge.py and the config are fetched with cache
    // "no-cache": browsers that saw the old "immutable, 1 year" header on the
    // wheel (ENG-01) kept serving their old copy -- even after a hard reload --
    // next to a new bridge.py: "cannot import name 'input_check'". "no-cache"
    // always asks the server (a 304 when unchanged), so they always match.
    // URLs are built against document.baseURI, not location.origin, so the app
    // works served from a subpath (e.g. quietmarch.to/cairn/).
    //
    // No micropip: pyyaml (the engine's only dependency) comes from the
    // Pyodide lockfile on jsdelivr, and the wheel is unpacked straight into
    // site-packages, so nothing can ever resolve from PyPI (the CSP blocks it).
    const fresh = { cache: "no-cache" };
    const name = "cairn_maps-1.0.0-py3-none-any.whl";
    const ours = async (path, read) => {
      const res = await fetch(new URL(path, document.baseURI), fresh);
      if (!res.ok) throw new Error(`Couldn't load the map engine (HTTP ${res.status}).`);
      return read(res);
    };
    // Carry the user's symbol mappings into the sandbox. Without this the
    // engine falls back to built-in defaults only (a fine fallback).
    const config = fetch(new URL("cairn_config.yaml", document.baseURI), fresh)
      .then((r) => (r.ok ? r.text() : null)).catch(() => null);
    // Promise.all, not one await after another: a fetch that fails while
    // Pyodide is still loading must not surface as an unhandled rejection.
    let wheel, bridge, cfg;
    [py, wheel, bridge, cfg] = await Promise.all([
      loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/", packages: ["pyyaml"] }),
      ours(`dist/${name}`, (r) => r.arrayBuffer()),
      ours("bridge.py", (r) => r.text()),
      config,
    ]);
    const site = py.runPython("import sysconfig; sysconfig.get_path('purelib')");
    py.unpackArchive(wheel, "wheel", { extractDir: site });
    py.FS.writeFile("/bridge.py", bridge);
    if (cfg !== null) py.FS.writeFile("/cairn_config.yaml", cfg);
    await py.runPythonAsync("import sys; sys.path.insert(0,'/'); import bridge");
    window.__cairnReady = true;
    // The same signal as a DOM attribute, for tests that run under the
    // enforced CSP, where Playwright can't evaluate window.__cairnReady.
    document.body.dataset.engine = "ready";
    // A file chosen or dropped while the engine was still booting waits here.
    if (PENDING_FILES) { const f = PENDING_FILES; PENDING_FILES = null; handleFiles(f); }
  } catch (e) {
    PENDING_FILES = null; $("#drop-wait").classList.add("hidden");
    setStatus("Failed: " + e.message, "err");
    window.__cairnError = String(e);
    console.error(e);
  }
}

/* ---------- stages ---------- */
/** Show one of drop / edit / done, and move the single #status node into
    that screen's slot (the top bar on drop/done, the rail on edit). */
function showStage(name) {
  ["drop", "edit", "done"].forEach(s => $(`#${s}-stage`).classList.toggle("hidden", s !== name));
  document.body.dataset.stage = name;
  const slot = name === "edit" ? $("#status-rail") : $("#status-top");
  if ($("#status").parentNode !== slot) slot.appendChild($("#status"));
  window.scrollTo(0, 0);
}

/* ---------- file intake ---------- */
function wireDrop() {
  const dz = $("#dropzone"), fi = $("#file");
  $("#pick").onclick = () => fi.click();
  fi.onchange = () => fi.files.length && handleFiles([...fi.files]);
  ["dragenter", "dragover"].forEach(ev => dz.addEventListener(ev, e => {
    e.preventDefault(); dz.classList.add("over");
  }));
  ["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => {
    e.preventDefault(); dz.classList.remove("over");
  }));
  // Several files at once (an onX GPX + KML pair, or one export per folder)
  // go to the bridge TOGETHER, so a pair merges. This is the first load only:
  // the drop zone exists on the drop screen, and "Start over" clears the map
  // rather than adding to it (UI-12).
  dz.addEventListener("drop", e => {
    const fs = [...e.dataTransfer.files]; if (fs.length) handleFiles(fs);
  });
  // A drop that misses the drop zone must not navigate the tab to the file.
  ["dragover", "drop"].forEach(ev => window.addEventListener(ev, e => e.preventDefault()));
}

async function handleFiles(files) {
  // The drop zone accepts files before the engine has finished booting
  // (Choose file… stays disabled until then, a drop can't be).
  // Quiet loading: nothing is shown while the engine boots. A file that
  // arrives first is queued and processed by boot() the moment it is ready.
  if (!window.__cairnReady) {
    PENDING_FILES = files;
    $("#drop-wait").classList.remove("hidden");
    return;
  }
  $("#drop-wait").classList.add("hidden");
  setStatus("Reading " + (files.length === 1 ? files[0].name : `${files.length} files`) + "…");
  try {
    const payload = await Promise.all(files.map(async f => ({ name: f.name, text: await f.text() })));
    // Data crosses into Python via globals, never by interpolating user
    // content into Python source — JSON escaping happening to be valid
    // Python-literal escaping is not a contract worth betting on.
    py.globals.set("_cairn_files", JSON.stringify(payload));
    const raw = py.runPython("bridge.load_files(_cairn_files)");
    DATA = JSON.parse(raw); EDITS = {}; SEL.clear(); ANCHOR = null;
    resetFilters(); COLLAPSED.clear(); RAIL_FOLDED.clear(); NOTE_EDIT = null; closePop(); closeBulk();
    $("#map-title").textContent = mapTitle(DATA);
    $("#map-label").textContent = mapLabel(DATA);
    renderSourceNotice(DATA);
    renderEdit();
    showStage("edit");
    setStatus("Map loaded", "ready");
    window.__cairnLoaded = true;
  } catch (e) {
    // Pyodide surfaces the whole Python traceback. The last line is the actual
    // message and the engine's messages are already user-friendly ("No features
    // found... make sure this is a CalTopo export"); the stack above it is noise
    // to a hiker. Keep the full thing in the console for us.
    setStatus("Couldn't read that file — " + humanError(e), "err");
    console.error(e);
  }
}

function humanError(e) {
  const lines = String(e.message || e).trim().split("\n").filter(Boolean);
  const last = lines.reverse().find(l => !/^\s*(File |\s{2,}|Traceback)/.test(l)) || lines[0] || "";
  return last.replace(/^\w*(Error|Exception):\s*/, "").trim().slice(0, 180);
}

/** The map's title. The engine doesn't hand one over, and a CalTopo
    GeoJSON export carries none; its download filename does, with spaces and
    brackets turned into underscores ("Bitterroots__Complete_.json" for
    "Bitterroots (Complete)"). Undo that. Several files: the first file's
    title, plus how many others came with it -- except the two halves of one
    onX export (same name, .gpx and .kml), which are one map. */
function fileTitle(name) {
  let s = String(name || "").replace(/\.((geo)?json|gpx|kml)$/i, "");
  s = s.replace(/__([^_]+(?:_[^_]+)*)_$/, " ($1)").replace(/_/g, " ").replace(/\s+/g, " ").trim();
  return s;
}
function mapTitle(data) {
  if (data.title || data.map_title) return data.title || data.map_title;
  const titles = [...new Set((data.filenames || [data.filename]).map(fileTitle))];
  const first = titles[0] || "Untitled map";
  const more = titles.length - 1;
  return more ? `${first} +\u00a0${more}\u00a0more` : first;   // "+ 2 more" never splits
}

/** The small label over the title: whose map this is. */
function mapLabel(data) {
  const src = data.sources || [];
  const caltopo = src.length && src.every(s => s.dialect === "caltopo");
  const onx = src.length && src.every(s => s.dialect === "onx" || s.dialect === "onx-like");
  return caltopo ? "CalTopo map" : onx ? "onX map" : "Map";
}

/** CalTopo's GPX has no folders, waypoint icons or waypoint colors (only line
    colors, as Garmin color names): say that its GeoJSON or KML would have
    brought them. CalTopo KML keeps them (roadmap Phase 7), so it gets no notice. */
const CALTOPO_GPX_NOTICE = "CalTopo's GPX has no folders, icons or waypoint colors. Its GeoJSON or KML export keeps them.";
function renderSourceNotice(data) {
  const el = $("#source-notice");
  const show = (data.sources || []).some(s => s.dialect === "caltopo" && s.kind === "gpx");
  el.textContent = show ? CALTOPO_GPX_NOTICE : "";
  el.classList.toggle("hidden", !show);
}

/* ---------- filters ---------- */
function resetFilters() {
  FILTERS.q = ""; FILTERS.kind = ""; FILTERS.folder = null;
  FILTERS.icons.clear(); FILTERS.attention = false;
  $("#filter").value = "";
  syncTypeFacet();
}

const isUnorganized = g => g.key === "orphaned_features" || /^(Unorganized|Uncategorized)$/.test(g.name);
const iconKey = it => it.needs_attention ? DEFAULT_PIN : it.icon;

function visibleItems(g) {
  if (FILTERS.folder !== null && g.key !== FILTERS.folder) return [];
  const q = FILTERS.q.toLowerCase();
  const keys = new Set(FILTERS.icons);
  if (FILTERS.attention) keys.add(DEFAULT_PIN);
  return g.items.filter(i =>
    (!q || i.name.toLowerCase().includes(q) || (i.desc || "").toLowerCase().includes(q)) &&
    (!FILTERS.kind || i.kind === FILTERS.kind) &&
    (!keys.size || (i.kind === "waypoints" && keys.has(iconKey(i)))));
}

function syncTypeFacet() {
  document.querySelectorAll("#type-filter [data-kind]").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.kind === FILTERS.kind)));
}

function setKind(kind) {
  FILTERS.kind = kind;
  syncTypeFacet();
  renderFolders();
}

const KIND_LABEL = { "": "All", waypoints: "Waypoints", tracks: "Lines", shapes: "Areas" };

/* The rail's three filter sections fold (UI-28). Folding only hides the list;
   whatever is picked in it stays applied, and the header says what that is. */
function renderRailHeads() {
  const icons = [...FILTERS.icons];
  if (FILTERS.attention) icons.push("Default pin");
  const g = FILTERS.folder !== null && DATA.groups.find(g => g.key === FILTERS.folder);
  const sums = {
    type: KIND_LABEL[FILTERS.kind] || "All",
    folders: g ? g.name : "All",
    icon: !icons.length ? "Any" : icons.length === 1 ? icons[0] : `${icons.length} icons`,
  };
  document.querySelectorAll(".rail .facet[data-sec]").forEach(sec => {
    const k = sec.dataset.sec, folded = RAIL_FOLDED.has(k);
    const h = sec.querySelector(".sec-h");
    h.setAttribute("aria-expanded", String(!folded));
    h.querySelector(".sec-sum").textContent = folded ? sums[k] : "";
    h.querySelector(".caret").textContent = folded ? "\u25B8" : "\u25BE";
    sec.querySelector(".facet-list").classList.toggle("hidden", folded);
  });
}

function toggleRailSection(k) {
  RAIL_FOLDED.has(k) ? RAIL_FOLDED.delete(k) : RAIL_FOLDED.add(k);
  renderRailHeads();
}

/* ---------- edit stage ---------- */
function renderEdit() {
  renderRail();
  renderFolders();
}

function renderRail() {
  const fk = focusedKey();
  // Type: each kind with its count; "Areas" only when the map has any.
  const byKind = { "": 0, waypoints: 0, tracks: 0, shapes: 0 };
  allItems().forEach(i => { byKind[""]++; byKind[i.kind] = (byKind[i.kind] || 0) + 1; });
  document.querySelectorAll("#type-filter [data-kind]").forEach(b => {
    b.querySelector(".facet-count").textContent = byKind[b.dataset.kind] || 0;
    if (b.dataset.kind === "shapes") b.classList.toggle("hidden", !byKind.shapes && FILTERS.kind !== "shapes");
  });
  syncTypeFacet();

  // Folders: "All" first, then each folder with its item count.
  const fl = $("#folder-facets"); fl.innerHTML = "";
  const facetBtn = (label, count, key, italic) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "facet-btn" + (italic ? " unorg" : "");
    b.setAttribute("aria-pressed", String(FILTERS.folder === key));
    b.dataset.fk = "folder|" + (key === null ? "\u0000all" : key);
    b.innerHTML = `<span class="facet-name">${esc(label)}</span><span class="facet-count">${count ?? ""}</span>`;
    b.onclick = () => {
      FILTERS.folder = FILTERS.folder === key && key !== null ? null : key;
      renderRail(); renderFolders();
    };
    fl.appendChild(b);
  };
  facetBtn("All", "", null, false);
  DATA.groups.forEach(g => facetBtn(g.name, g.items.length, g.key, isUnorganized(g)));

  // Icons present in the map, most common first; "Default pin" last.
  const counts = new Map();
  allItems().filter(i => i.kind === "waypoints").forEach(i => {
    const k = iconKey(i); counts.set(k, (counts.get(k) || 0) + 1);
  });
  const keys = [...counts.keys()].filter(k => k !== DEFAULT_PIN)
    .sort((a, b) => counts.get(b) - counts.get(a) || a.localeCompare(b));
  if (counts.has(DEFAULT_PIN) || FILTERS.attention) keys.push(DEFAULT_PIN);
  // keep an icon you're filtering on visible even after its last item changed
  FILTERS.icons.forEach(k => { if (!keys.includes(k)) keys.splice(keys.length - (keys.at(-1) === DEFAULT_PIN), 0, k); });
  const il = $("#icon-facets"); il.innerHTML = "";
  keys.forEach(k => {
    const def = k === DEFAULT_PIN;
    const lab = document.createElement("label");
    lab.className = "icon-facet" + (def ? " default-pin" : "");
    lab.title = def ? "Waypoints that fell back to onX's default pin" : "";
    lab.innerHTML = `<input type="checkbox"${def ? ' id="only-attention"' : ""} data-icon="${esc(k)}" data-fk="icon|${esc(k)}">` +
      glyphSVG(def ? "Location" : k, 15) + `<span class="facet-name">${def ? "Default pin" : esc(k)}</span><span class="facet-count">${counts.get(k) || 0}</span>`;
    const box = lab.querySelector("input");
    box.checked = def ? FILTERS.attention : FILTERS.icons.has(k);
    box.onchange = () => {
      if (def) FILTERS.attention = box.checked;
      else box.checked ? FILTERS.icons.add(k) : FILTERS.icons.delete(k);
      renderFolders();
    };
    il.appendChild(lab);
  });
  if (!keys.length) il.innerHTML = `<span class="facet-empty">No waypoints</span>`;
  renderRailHeads();
  refocus(fk);
}

function renderChips() {
  renderRailHeads();
  const host = $("#chips"); host.innerHTML = "";
  const chips = [];
  if (FILTERS.q) chips.push([`Search: “${FILTERS.q}”`, () => { FILTERS.q = ""; $("#filter").value = ""; }]);
  if (FILTERS.kind) chips.push([`Type: ${KIND_LABEL[FILTERS.kind]}`, () => { FILTERS.kind = ""; syncTypeFacet(); }]);
  if (FILTERS.folder !== null) {
    const g = DATA.groups.find(g => g.key === FILTERS.folder);
    chips.push([`Folder: ${g ? g.name : "?"}`, () => { FILTERS.folder = null; }]);
  }
  FILTERS.icons.forEach(k => chips.push([`Icon: ${k}`, () => FILTERS.icons.delete(k)]));
  if (FILTERS.attention) chips.push(["Icon: Default pin", () => { FILTERS.attention = false; }]);
  host.classList.toggle("hidden", !chips.length);
  if (!chips.length) return;
  const n = shownItems().length;
  host.insertAdjacentHTML("beforeend", `<span class="chips-label">Showing ${n}</span>`);
  chips.forEach(([label, remove]) => {
    const c = document.createElement("span");
    c.className = "chip";
    c.innerHTML = `<span>${esc(label)}</span><button type="button" aria-label="Remove filter ${esc(label)}">${UI_ICON.close}</button>`;
    c.querySelector("button").onclick = () => { remove(); renderRail(); renderFolders(); };
    host.appendChild(c);
  });
  const clear = document.createElement("button");
  clear.type = "button"; clear.className = "linkbtn"; clear.textContent = "Clear all";
  clear.onclick = () => { resetFilters(); renderRail(); renderFolders(); };
  host.appendChild(clear);
}

function renderFolders() {
  // Selection always follows what's on screen -- if a filter change hides a
  // selected row, it drops out of the selection rather than staying an
  // invisible target for the next bulk edit.
  const fk = focusedKey();
  const shownUids = new Set(shownItems().map(i => i.uid));
  const selectableUids = new Set(selectableItems().map(i => i.uid));
  for (const uid of SEL) if (!selectableUids.has(uid)) SEL.delete(uid);
  if (NOTE_EDIT && !shownUids.has(NOTE_EDIT.uid)) NOTE_EDIT = null;
  renderChips();

  const host = $("#folders"); host.innerHTML = "";
  DATA.groups.forEach(g => {
    const items = visibleItems(g);
    if (!items.length) return;
    const el = document.createElement("section");
    el.className = "folder";
    el.setAttribute("aria-label", g.name);
    const collapsed = COLLAPSED.has(g.key);
    const sub = isUnorganized(g) ? "Not in any CalTopo folder"
      : items.length === g.items.length ? `${g.items.length} item${g.items.length === 1 ? "" : "s"}`
      : `${items.length} of ${g.items.length} shown`;
    el.innerHTML = `
      <div class="folder-head">
        <h2>${esc(g.name)}</h2>
        <span class="folder-sub">${esc(sub)}</span>
        <button type="button" class="collapse" data-fk="collapse|${esc(g.key)}" aria-expanded="${!collapsed}" aria-label="${collapsed ? "Expand" : "Collapse"} ${esc(g.name)}">${UI_ICON.chevron}</button>
      </div>
      <div class="table-wrap${collapsed ? " hidden" : ""}"><table>
        <colgroup><col class="c-sel"><col class="c-name"><col class="c-note"><col class="c-icon"></colgroup>
        <thead><tr>
          <th class="selcol"><input type="checkbox" class="folder-all" data-fk="all|${esc(g.key)}" aria-label="Select all shown in ${esc(g.name)}"></th>
          <th>Name</th><th>Note</th><th>Icon</th>
        </tr></thead><tbody></tbody></table></div>`;
    const tb = el.querySelector("tbody");
    items.forEach(it => tb.appendChild(row(it)));
    const fbox = el.querySelector(".folder-all");
    const nsel = items.filter(i => SEL.has(i.uid)).length;
    fbox.checked = nsel === items.length;
    fbox.indeterminate = nsel > 0 && nsel < items.length;
    fbox.onchange = e => {
      items.forEach(i => e.target.checked ? SEL.add(i.uid) : SEL.delete(i.uid));
      renderFolders();
    };
    el.querySelector(".collapse").onclick = () => {
      COLLAPSED.has(g.key) ? COLLAPSED.delete(g.key) : COLLAPSED.add(g.key);
      renderFolders();
    };
    host.appendChild(el);
  });
  if (!host.children.length)
    host.innerHTML = `<div class="note">Nothing matches these filters.</div>`;
  updateSel();
  refocus(fk);
}

const colorList = () => DATA.line_colors || DATA.colors;
const colorOf = rgba => colorList().find(c => c.rgba === rgba) || DATA.colors.find(c => c.rgba === rgba);
const colorName = rgba => (colorOf(rgba) || { name: "—" }).name;
const kindWord = k => k === "shapes" ? "Area" : "Line";
/** A row's type label. An onX file says whether a line is a Line or a recorded
    Track, so its rows say so too; everything else is "Line" or "Area" (UI-18:
    the type filter keeps the one word "Lines"). */
const SUBKIND_WORD = { line: "Line", track: "Track", area: "Area" };
const rowKindWord = it => SUBKIND_WORD[it.subkind] || kindWord(it.kind);
const oneLine = s => String(s || "").replace(/\s*\n\s*/g, " ").trim();

function row(it) {
  const tr = document.createElement("tr");
  tr.dataset.uid = it.uid;
  const isWp = it.kind === "waypoints";
  if (it.needs_attention) tr.classList.add("attention");
  if (SEL.has(it.uid)) tr.classList.add("sel");
  if (!it.included) tr.classList.add("excluded");
  if (POP && POP.uid === it.uid) tr.classList.add("editing");
  const noteOpen = NOTE_EDIT && NOTE_EDIT.uid === it.uid;
  if (noteOpen) tr.classList.add("note-open");
  const cname = colorName(it.color);
  const iconLabel = it.needs_attention ? "Default pin" : it.icon;
  const fk = esc(it.uid) + "|";
  tr.innerHTML = `
    <td class="selcol"><input type="checkbox" class="sel-box" data-fk="${fk}sel" aria-label="Select ${esc(it.name)}" ${SEL.has(it.uid) ? "checked" : ""}></td>
    <td class="namecol"><input class="name-in" data-fk="${fk}name" aria-label="Name of ${esc(it.name)}" value="${esc(it.name)}">${it.included ? ""
      : `<span class="exc-label">Excluded</span><button type="button" class="exc-chip" data-fk="${fk}include" aria-label="Include ${esc(it.name)}" title="This row will not be exported. Click to put it back.">Include</button>`}</td>
    <td class="notecol">${noteOpen ? noteEditor(it) :
      `<button type="button" class="note-btn" data-fk="${fk}note" aria-label="Open note for ${esc(it.name)}">
        <span class="note-text${it.desc ? "" : " empty"}">${esc(oneLine(it.desc) || "Add a note")}</span>${UI_ICON.pencil}</button>`}</td>
    <td class="iconcol">${isWp
      ? `<button type="button" class="icon-btn" data-fk="${fk}mark" title="${esc(it.why)}" aria-label="${esc(iconLabel)}, ${esc(cname)}. Change icon or color">${markerSVG(it.icon, it.hex, 22, 28)}${it.needs_attention
          ? `<span class="whymark" title="${esc(it.why)}">Default pin</span>`
          // An icon an onX file named that isn't in onX's list (Phase 2 flags
          // it): kept and exported as is, but marked so it gets a look.
          : `<span class="icon-name${it.unknown_icon ? " unknown-icon" : ""}">${esc(it.icon)}</span>`}</button>`
      : `<button type="button" class="line-btn" data-fk="${fk}mark" title="${esc(cname)} — ${esc(it.why)}" aria-label="${rowKindWord(it)}, ${esc(cname)}${it.kind === "tracks" ? `, ${STYLE_NAMES[it.style] || "Dotted"}, ${WEIGHT_NAMES[it.weight] || ""}. Change line` : ". Change color"}">${lineSVG(it.hex, it.kind, 22, 19, it.style, it.weight)}<span class="icon-name kind">${rowKindWord(it)}</span></button>`}</td>`;
  const selBox = tr.querySelector(".sel-box");
  selBox.onclick = e => {
    if (e.shiftKey && ANCHOR && ANCHOR !== it.uid) {
      // Range-select between the anchor and this row, in the order rows are
      // currently displayed -- so it follows the active filter and sort rather
      // than the underlying file order.
      e.preventDefault();
      const order = selectableItems().map(i => i.uid);
      const a = order.indexOf(ANCHOR), b = order.indexOf(it.uid);
      if (a !== -1 && b !== -1) {
        const [lo, hi] = a < b ? [a, b] : [b, a];
        const on = !SEL.has(it.uid);
        for (let k = lo; k <= hi; k++) on ? SEL.add(order[k]) : SEL.delete(order[k]);
        renderFolders();
        return;
      }
    }
    ANCHOR = it.uid;
  };
  selBox.onchange = e => {
    e.target.checked ? SEL.add(it.uid) : SEL.delete(it.uid);
    tr.classList.toggle("sel", e.target.checked); updateSel();
    syncFolderBox(tr);
  };
  wireTextField(tr.querySelector(".name-in"), it, "name", { required: true });
  if (noteOpen) wireNoteEditor(tr, it);
  else tr.querySelector(".note-btn").onclick = () => openNote(it);
  const chip = tr.querySelector(".exc-chip");
  if (chip) chip.onclick = () => edit(it, { included: true });
  const mark = tr.querySelector(".icon-btn, .line-btn");
  mark.onclick = e => { e.stopPropagation(); openPop(it, mark); };
  return tr;
}

/** Keep the folder's header checkbox in step after a single-row toggle
    (which deliberately doesn't re-render the whole list). */
function syncFolderBox(tr) {
  const sec = tr.closest(".folder"); if (!sec) return;
  const boxes = [...sec.querySelectorAll(".sel-box")];
  const n = boxes.filter(b => b.checked).length;
  const fbox = sec.querySelector(".folder-all");
  fbox.checked = n === boxes.length; fbox.indeterminate = n > 0 && n < boxes.length;
}

/** Text input with Escape-to-revert.
 *
 *  `change` fires on blur, and Escape blurs -- so pressing Escape mid-edit used
 *  to COMMIT whatever was in the box, including an empty one. Restoring the
 *  original value before blurring means the browser sees no change at all, so no
 *  commit happens.
 *
 *  `required` fields (the name) also refuse to commit empty: a nameless markup
 *  is unusable in onX, where the name is the only searchable field.
 */
function wireTextField(el, it, key, { required = false } = {}) {
  el.addEventListener("focus", () => { el.dataset.orig = el.value; });
  el.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      e.preventDefault();
      el.value = el.dataset.orig ?? "";   // no diff => no change event => no commit
      el.blur();
    } else if (e.key === "Enter") {
      e.preventDefault();
      el.blur();                          // commit
    }
  });
  el.addEventListener("change", () => {
    const v = el.value;
    if (required && !v.trim()) {
      el.value = el.dataset.orig ?? "";
      setStatus("A name is required — onX can only search by name.", "err");
      return;
    }
    // `change` fires on blur BEFORE focus lands on the next control; a
    // synchronous re-render would destroy that control mid-Tab. Update the data
    // now, re-render on the next task, when focus has arrived and can be kept.
    edit(it, { [key]: v }, { render: false });
    setTimeout(() => DATA && refreshAfterEdit());
  });
}

/* ---------- notes: inline multi-line editor ---------- */
function noteEditor(it) {
  const id = "note-" + it.uid.replace(/[^\w-]/g, "_");
  const fk = esc(it.uid) + "|note";   // shared with the note button it replaces
  return `<div class="note-ed">
    <label class="label" for="${id}">Note</label>
    <textarea id="${id}" class="desc-in" data-fk="${fk}" rows="5">${esc(NOTE_EDIT.draft)}</textarea>
    <div class="note-actions">
      <button type="button" class="btn primary small note-apply" data-fk="${fk}">Save</button>
      <button type="button" class="btn small note-cancel" data-fk="${fk}">Cancel</button>
    </div></div>`;
}

function openNote(it) {
  NOTE_EDIT = { uid: it.uid, draft: it.desc || "" };
  renderFolders();
  const ta = document.querySelector(`tr[data-uid="${CSS.escape(it.uid)}"] .desc-in`);
  if (ta) {
    // Caret at the start, scrolled to the top: a long note is read from its
    // beginning, not dropped at the bottom.
    ta.focus({ preventScroll: true });
    ta.setSelectionRange(0, 0);
    ta.scrollTop = 0;
  }
}

function closeNote(it, apply) {
  if (!NOTE_EDIT) return;
  const v = NOTE_EDIT.draft;
  NOTE_EDIT = null;
  if (apply && it && v !== (it.desc || "")) edit(it, { desc: v });
  else renderFolders();
}

function wireNoteEditor(tr, it) {
  const ta = tr.querySelector(".desc-in");
  ta.addEventListener("input", () => { NOTE_EDIT.draft = ta.value; });
  ta.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      e.preventDefault(); e.stopPropagation();
      closeNote(it, false);
    } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      closeNote(it, true);
    }   // plain Enter: the textarea's own newline
  });
  tr.querySelector(".note-apply").onclick = () => closeNote(it, true);
  tr.querySelector(".note-cancel").onclick = () => closeNote(it, false);
}

/* ---------- edits ---------- */
function edit(it, patch, { render = true } = {}) {
  Object.assign(it, patch);
  if (patch.color) it.hex = (colorOf(patch.color) || {}).hex || it.hex;
  if (patch.icon !== undefined) {
    // Picking an icon is a decision -- including deliberately picking the default
    // pin. Marking that "still needs attention" would nag the user for agreeing
    // with the tool.
    it.confirmed = true;
    it.needs_attention = false;
    it.why = patch.icon === "Location"
      ? "You chose the default pin for this one."
      : "You set this icon.";
  }
  EDITS[it.uid] = Object.assign(EDITS[it.uid] || {}, patch);
  if (render) refreshAfterEdit();
}

function refreshAfterEdit() {
  DATA.totals.attention = DATA.groups.reduce(
    (n, g) => n + g.items.filter(i => i.needs_attention).length, 0);
  DATA.totals.excluded = DATA.groups.reduce(
    (n, g) => n + g.items.filter(i => !i.included).length, 0);
  renderEdit();
}

function allItems() { return DATA.groups.flatMap(g => g.items); }

/** Items currently on screen, i.e. passing every active filter.
    Select-all deliberately operates on THESE, not on everything in the file --
    "select all" after filtering to `water` should select the water, not 177 items. */
function shownItems() { return DATA.groups.flatMap(g => visibleItems(g)); }
/** Rows the user can actually see: shown items minus folders they collapsed.
    Selection (select-all, shift-range, pruning) works on THESE, so a bulk edit
    never reaches a row hidden inside a collapsed folder. */
function selectableItems() { return DATA.groups.flatMap(g => COLLAPSED.has(g.key) ? [] : visibleItems(g)); }
const selectedItems = () => allItems().filter(i => SEL.has(i.uid));

function setSelectAll(on) {
  const shown = selectableItems();
  shown.forEach(i => on ? SEL.add(i.uid) : SEL.delete(i.uid));
  if (!on) ANCHOR = null;
  renderFolders();
}

function bulk(patch) {
  selectedItems().forEach(it => edit(it, typeof patch === "function" ? patch(it) : patch, { render: false }));
  refreshAfterEdit();
}

function updateSel() {
  const n = SEL.size;
  $("#selcount").textContent = `${n} selected`;
  $("#selbar").classList.toggle("hidden", n === 0);
  ["#bulk-icon", "#more-btn"].forEach(sel => {
    const el = $(sel);
    el.disabled = n === 0;
    el.title = n === 0 ? "Select rows first" : "";
  });
  $("#bulk-line").classList.toggle("hidden", !selectedItems().some(i => i.kind === "tracks"));
  closeMenu();
}

/* ---------- icon & color: palettes ---------- */
/** Which colors a set of items can take: waypoints get onX's 10, lines and
    areas its 11 (adds Fuchsia), a mix only the 10 they share. */
function paletteFor(items) {
  const wp = items.some(i => i.kind === "waypoints");
  const ln = items.some(i => i.kind !== "waypoints");
  return !wp && ln ? (DATA.line_colors || DATA.colors) : DATA.colors;
}

function paletteHTML(colors, current) {
  return colors.map(c => `<button type="button" class="swatch-btn" data-rgba="${esc(c.rgba)}" aria-label="${esc(c.name)}" title="${esc(c.name)}" aria-pressed="${c.rgba === current}" style="background:${esc(c.hex)}"></button>`).join("");
}
/* ---------- line style and weight ---------- */
const STYLE_NAMES = { solid: "Solid", dash: "Dashed" };
const WEIGHT_NAMES = { "4.0": "Thin", "6.0": "Thick" };
/** Two titled groups of drawn-line toggles; the drawing is the label. */
function lineOptsHTML(style, weight) {
  const tog = (attr, k, name, glyph, on) =>
    `<button type="button" class="tog" data-${attr}="${k}" aria-label="${name}" title="${name}" aria-pressed="${on}">${glyph}</button>`;
  return `<div class="pop-sec line-opts">
      <div class="opt-group"><span class="label">Style</span><div class="toggles" role="group" aria-label="Style">${
        Object.keys(STYLE_NAMES).map(k => tog("style", k, STYLE_NAMES[k], lineGlyphSVG(k), k === style)).join("")}</div></div>
      <div class="opt-group"><span class="label">Weight</span><div class="toggles" role="group" aria-label="Weight">${
        Object.keys(WEIGHT_NAMES).map(k => tog("weight", k, WEIGHT_NAMES[k], lineGlyphSVG("solid", k), k === weight)).join("")}</div></div>
    </div>`;
}
function syncLineOpts(root, style, weight) {
  root.querySelectorAll(".tog[data-style]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.style === style)));
  root.querySelectorAll(".tog[data-weight]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.weight === weight)));
}

/* The icon list (UI-29) is built once per open of the popover or dialog. After
   that the filter only toggles `hidden` and a pick only flips aria-pressed, so
   the buttons are never replaced and keyboard focus stays where it was. */
function buildIconGrid(grid, selected, onPick) {
  grid.innerHTML = DATA.icons.map(n =>
    `<button type="button" class="icon-pick" data-icon="${esc(n)}" aria-pressed="${n === selected}">` +
    `${markerOutlineSVG(n, 24, 30)}<span>${esc(n)}</span></button>`).join("") +
    `<span class="grid-empty" hidden></span>`;
  grid.querySelectorAll(".icon-pick").forEach(b => b.onclick = () => onPick(b.dataset.icon));
}
function filterIconGrid(grid, q) {
  const s = q.trim().toLowerCase();
  let shown = 0;
  grid.querySelectorAll(".icon-pick").forEach(b => {
    b.hidden = !!s && !b.dataset.icon.toLowerCase().includes(s);
    if (!b.hidden) shown++;
  });
  const empty = grid.querySelector(".grid-empty");
  empty.hidden = shown > 0;
  empty.textContent = shown ? "" : `No icon matches “${q}”.`;
}
function syncIconGrid(grid, selected) {
  if (!grid) return;
  grid.querySelectorAll(".icon-pick").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.icon === selected)));
}

/* ---------- single item: popover anchored to the marker ---------- */
function openPop(it, anchor) {
  closeMenu(); closeBulk();
  POP = { uid: it.uid, color: it.color, icon: it.icon, iconPicked: false, q: "", anchor,
          style: it.style, weight: it.weight };
  const isWp = it.kind === "waypoints";
  const isLine = it.kind === "tracks";
  const pop = $("#mark-pop");
  pop.classList.toggle("line", isLine);
  pop.setAttribute("aria-label", `Change ${isWp ? "icon and color" : isLine ? "line" : "color"} for ${it.name}`);
  pop.innerHTML = `
    <div class="pop-head">
      <span class="pop-preview"></span>
      <div class="pop-title"><span class="pop-name">${esc(it.name || "Untitled")}</span></div>
    </div>
    ${isLine ? `<div class="pop-map"></div>` : ""}
    <div class="pop-sec">
      <span class="label">Color</span>
      <div class="palette${isLine ? " spread" : ""}">${paletteHTML(paletteFor([it]), POP.color)}</div>
    </div>
    ${isWp ? `<div class="pop-sec icons">
      <div class="sec-row"><span class="label">Icon</span><span class="sec-count">${DATA.icons.length} icons</span></div>
      <input type="search" class="icon-search" aria-label="Find an icon" placeholder="Find an icon" autocomplete="off">
      <div class="icon-grid" role="group" aria-label="Icons"></div>
    </div>` : isLine ? lineOptsHTML(POP.style, POP.weight) : ""}
    <div class="pop-foot">
      <button type="button" class="btn pop-cancel">Cancel</button>
      <button type="button" id="pop-apply" class="btn primary pop-apply">Save</button>
    </div>`;
  pop.querySelectorAll(".swatch-btn").forEach(b => b.onclick = () => {
    POP.color = b.dataset.rgba; drawPop();
  });
  if (isWp) {
    const grid = pop.querySelector(".icon-grid");
    buildIconGrid(grid, POP.icon, n => { POP.icon = n; POP.iconPicked = true; drawPop(); });
    const s = pop.querySelector(".icon-search");
    s.oninput = () => { POP.q = s.value; filterIconGrid(grid, POP.q); };
  }
  pop.querySelectorAll(".tog[data-style]").forEach(b => b.onclick = () => { POP.style = b.dataset.style; drawPop(); });
  pop.querySelectorAll(".tog[data-weight]").forEach(b => b.onclick = () => { POP.weight = b.dataset.weight; drawPop(); });
  pop.querySelector(".pop-cancel").onclick = closePop;
  pop.querySelector(".pop-apply").onclick = applyPop;
  pop.classList.remove("hidden");
  drawPop();
  placePop(anchor);
  document.querySelectorAll("tr.editing").forEach(r => r.classList.remove("editing"));
  anchor.closest("tr")?.classList.add("editing");
  const cur = pop.querySelector('.icon-pick[aria-pressed="true"]');
  if (cur) cur.scrollIntoView({ block: "nearest" });
  (pop.querySelector('.swatch-btn[aria-pressed="true"]') || pop.querySelector(".swatch-btn")).focus({ preventScroll: true });
}

function popItem() { return POP && allItems().find(i => i.uid === POP.uid); }

function drawPop() {
  const it = popItem(); if (!it) return;
  const pop = $("#mark-pop");
  const hex = (colorOf(POP.color) || {}).hex || it.hex;
  const isWp = it.kind === "waypoints";
  const isLine = it.kind === "tracks";
  // A line is previewed on the map strip, so its header carries no second drawing.
  pop.querySelector(".pop-preview").innerHTML = isWp ? markerSVG(POP.icon, hex, 52, 64) : isLine ? "" : lineSVG(hex, it.kind, 52, 44);
  pop.querySelectorAll(".swatch-btn").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.rgba === POP.color)));
  if (isLine) {
    pop.querySelector(".pop-map").innerHTML = lineMapSVG(hex, POP.style, POP.weight);
    syncLineOpts(pop, POP.style, POP.weight);
  }
  // The icon list keeps its neutral outline markers; only the pressed state moves.
  if (isWp) syncIconGrid(pop.querySelector(".icon-grid"), POP.icon);
}

function placePop(anchor) {
  const pop = $("#mark-pop");
  const vw = document.documentElement.clientWidth;
  if (vw < 640) {   // phones: a centered sheet instead of an anchored popover
    pop.classList.add("sheet");
    pop.style.left = ""; pop.style.top = "";
    return;
  }
  pop.classList.remove("sheet");
  const r = anchor.getBoundingClientRect();
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let left = Math.min(Math.max(8, r.right - w), vw - w - 8);
  // Prefer below the marker, then above; if it fits neither way, clamp it inside
  // the window (CSS caps its height at 100vh - 16px) so it is never cut off.
  const vh = window.innerHeight;
  let top;
  if (vh - r.bottom - 14 >= h) top = r.bottom + 6;
  else if (r.top - 14 >= h) top = r.top - h - 6;
  else top = Math.max(8, Math.min(r.bottom + 6, vh - h - 8));
  pop.style.left = `${left + window.scrollX}px`;
  pop.style.top = `${top + window.scrollY}px`;
}

function applyPop() {
  const it = popItem(); if (!it) return closePop();
  const patch = {};
  if (POP.color !== it.color) patch.color = POP.color;
  if (it.kind === "waypoints" && POP.iconPicked) patch.icon = POP.icon;
  if (it.kind === "tracks") {
    if (POP.style !== it.style) patch.style = POP.style;
    if (POP.weight !== it.weight) patch.weight = POP.weight;
  }
  closePop();
  if (Object.keys(patch).length) edit(it, patch);
}

function closePop() {
  if (!POP) return;
  const anchor = POP.anchor;
  POP = null;
  $("#mark-pop").classList.add("hidden");
  $("#mark-pop").innerHTML = "";
  document.querySelectorAll("tr.editing").forEach(r => r.classList.remove("editing"));
  if (anchor && anchor.isConnected) anchor.focus({ preventScroll: true });
}

/* ---------- several items: dialog from the selection bar ---------- */
function openBulk() {
  const items = selectedItems();
  if (!items.length) return;
  const ret = document.activeElement;
  closeMenu(); closePop();
  BULK = { mode: "mark", uids: new Set(items.map(i => i.uid)), color: null, icon: null, q: "", ret };
  const hasWp = items.some(i => i.kind === "waypoints");
  const d = $("#mark-dialog");
  d.setAttribute("aria-label", `Change icon and color for ${items.length} items`);
  d.innerHTML = `
    <div class="bulk-head">
      <div class="modal-head plain"><h2>Change ${items.length} item${items.length === 1 ? "" : "s"}</h2>
        <button type="button" class="x bulk-x" aria-label="Close">${UI_ICON.close}</button></div>
      <div class="now-after">
        <span class="label">Now</span><span></span><span class="label">After</span>
        <div class="na-rows"></div>
      </div>
    </div>
    <div class="pop-sec">
      <span class="label">Color</span>
      <div class="palette"><button type="button" class="reset-chip color-reset" aria-pressed="true">Reset</button>${paletteHTML(paletteFor(items), null)}</div>
    </div>
    ${hasWp ? `<div class="pop-sec icons">
      <span class="label">Icon</span>
      <div class="bulk-icon-row"><button type="button" class="reset-chip icon-reset" aria-pressed="true">Reset</button>
        <input type="search" class="icon-search" aria-label="Find an icon for all selected waypoints" placeholder="Find an icon" autocomplete="off"></div>
      <div class="icon-grid" role="group" aria-label="Icons"></div>
    </div>` : ""}
    <div class="pop-foot">
      <button type="button" class="btn bulk-cancel">Cancel</button>
      <button type="button" id="bulk-apply" class="btn primary">Save</button>
    </div>`;
  d.querySelector(".color-reset").onclick = () => { BULK.color = null; drawBulk(); };
  d.querySelectorAll(".swatch-btn").forEach(b => b.onclick = () => { BULK.color = b.dataset.rgba; drawBulk(); });
  if (hasWp) {
    d.querySelector(".icon-reset").onclick = () => { BULK.icon = null; drawBulk(); };
    const grid = d.querySelector(".icon-grid");
    buildIconGrid(grid, BULK.icon, n => { BULK.icon = n; drawBulk(); });
    const s = d.querySelector(".icon-search");
    s.oninput = () => { BULK.q = s.value; filterIconGrid(grid, BULK.q); };
  }
  d.querySelector(".bulk-x").onclick = closeBulk;
  d.querySelector(".bulk-cancel").onclick = closeBulk;
  d.querySelector("#bulk-apply").onclick = applyBulk;
  $("#mark-modal").classList.remove("hidden");
  drawBulk();
  d.querySelector(".color-reset").focus();
}

function drawBulk() {
  const d = $("#mark-dialog");
  const items = allItems().filter(i => BULK.uids.has(i.uid));
  const hexOf = rgba => (colorOf(rgba) || {}).hex;
  d.querySelector(".na-rows").innerHTML = items.map(it => {
    const isWp = it.kind === "waypoints";
    const toColor = BULK.color || it.color;
    const toIcon = isWp ? (BULK.icon || it.icon) : null;
    const nowMark = isWp ? markerSVG(it.icon, it.hex, 22, 28) : lineSVG(it.hex, it.kind, 22, 20);
    const afterMark = isWp ? markerSVG(toIcon, hexOf(toColor) || it.hex, 22, 28) : lineSVG(hexOf(toColor) || it.hex, it.kind, 22, 20);
    // The drawn marks show the change; no "Camp · Blue" words beside them (UI-26).
    return `<span class="na-cell">${nowMark}<span class="na-name">${esc(it.name || "Untitled")}</span></span>${UI_ICON.arrow}` +
      `<span class="na-cell">${afterMark}</span>`;
  }).join("");
  d.querySelector(".color-reset").setAttribute("aria-pressed", String(!BULK.color));
  d.querySelectorAll(".swatch-btn").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.rgba === BULK.color)));
  const ir = d.querySelector(".icon-reset");
  if (ir) ir.setAttribute("aria-pressed", String(!BULK.icon));
  syncIconGrid(d.querySelector(".icon-grid"), BULK.icon);
}

function applyBulk() {
  const { color, icon, uids } = BULK;
  const items = allItems().filter(i => uids.has(i.uid));
  closeBulk();
  if (!color && !icon) return;
  let n = 0;
  items.forEach(it => {
    const patch = {};
    if (color) patch.color = color;
    if (icon && it.kind === "waypoints") patch.icon = icon;
    if (Object.keys(patch).length) { edit(it, patch, { render: false }); n++; }
  });
  refreshAfterEdit();
  setStatus(`Changed ${n} item${n === 1 ? "" : "s"}`, "ready");
}

/* ---------- several lines: the Line style dialog ---------- */
function openLineBulk() {
  const lines = selectedItems().filter(i => i.kind === "tracks");
  if (!lines.length) return;
  const ret = document.activeElement;
  closeMenu(); closePop();
  BULK = { mode: "line", uids: new Set(lines.map(i => i.uid)), style: null, weight: null, ret };
  const d = $("#mark-dialog");
  d.setAttribute("aria-label", "Line style");
  d.innerHTML = `
    <div class="bulk-head">
      <div class="modal-head plain"><h2>Line style</h2>
        <button type="button" class="x bulk-x" aria-label="Close">${UI_ICON.close}</button></div>
      <div class="line-rows"></div>
    </div>
    ${lineOptsHTML(null, null)}
    <div class="pop-foot">
      <button type="button" class="btn bulk-cancel">Cancel</button>
      <button type="button" id="line-apply" class="btn primary">Save</button>
    </div>`;
  // Picking the chosen toggle again un-picks it: that line keeps its own value.
  d.querySelectorAll(".tog[data-style]").forEach(b => b.onclick = () => {
    BULK.style = BULK.style === b.dataset.style ? null : b.dataset.style; drawLineBulk(); });
  d.querySelectorAll(".tog[data-weight]").forEach(b => b.onclick = () => {
    BULK.weight = BULK.weight === b.dataset.weight ? null : b.dataset.weight; drawLineBulk(); });
  d.querySelector(".bulk-x").onclick = closeBulk;
  d.querySelector(".bulk-cancel").onclick = closeBulk;
  d.querySelector("#line-apply").onclick = applyLineBulk;
  $("#mark-modal").classList.remove("hidden");
  drawLineBulk();
  d.querySelector(".tog").focus();
}

function drawLineBulk() {
  const d = $("#mark-dialog");
  const lines = allItems().filter(i => BULK.uids.has(i.uid));
  d.querySelector(".line-rows").innerHTML = lines.map(it =>
    `<span class="lr-name">${esc(it.name || "Untitled")}</span>` +
    `<span class="lr-line">${lineStripSVG(it.hex, BULK.style || it.style, BULK.weight || it.weight)}</span>`).join("");
  syncLineOpts(d, BULK.style, BULK.weight);
}

function applyLineBulk() {
  const { style, weight, uids } = BULK;
  const lines = allItems().filter(i => uids.has(i.uid));
  closeBulk();
  let n = 0;
  lines.forEach(it => {
    const patch = {};
    if (style && style !== it.style) patch.style = style;
    if (weight && weight !== it.weight) patch.weight = weight;
    if (Object.keys(patch).length) { edit(it, patch, { render: false }); n++; }
  });
  if (!n) return;
  refreshAfterEdit();
  setStatus(`Changed ${n} line${n === 1 ? "" : "s"}`, "ready");
}

function closeBulk() {
  if (!BULK) return;
  const { ret } = BULK;
  BULK = null;
  $("#mark-modal").classList.add("hidden");
  $("#mark-dialog").innerHTML = "";
  const to = ret && ret !== document.body && ret.isConnected && !ret.disabled ? ret : $("#bulk-icon");
  if (!to.disabled) to.focus({ preventScroll: true });
}

/* ---------- More menu ---------- */
function closeMenu() {
  $("#more-menu").classList.add("hidden");
  $("#more-btn").setAttribute("aria-expanded", "false");
}

/* ---------- export ---------- */
async function doExport() {
  if (!allItems().some(i => i.included)) {
    setStatus("Everything is excluded — include at least one item to export.", "err");
    return;
  }
  setStatus("Building onX files…");
  try {
    closePop(); closeBulk();
    py.globals.set("_cairn_edits", JSON.stringify(EDITS));
    py.runPython("bridge.apply_edits(_cairn_edits)");
    const bytes = py.runPython("bridge.export_zip()").toJs();
    ZIP = new Blob([bytes], { type: "application/zip" });
    MANIFEST = JSON.parse(py.runPython("import json; json.dumps(bridge._STATE['manifest'])"));
    renderRunbook();
    showStage("done");
    setStatus(`Built ${MANIFEST.length} import batches`, "ready");
    window.__cairnExported = true;
  } catch (e) {
    setStatus("Export failed: " + e.message, "err"); console.error(e);
  }
}

function renderRunbook() {
  // Same numbers as RUNBOOK.md: both come from bridge.runbook_summary, so the
  // over-limit check uses max(written, expected) and dropped items are reported.
  const S = JSON.parse(py.runPython("bridge.runbook_summary_json()"));
  const kml = S.kml_batches;
  const host = $("#runbook");
  host.innerHTML =
    `<div class="note">onX Premium or Elite is required to import.${kml
      ? ` <b>${kml}</b> of these batches contain a KML file, which the phone app can't import — use the Web Map on a computer.`
      : ""}</div>` +
    (S.dropped ? `<div class="note warn"><b>${S.dropped}</b> item${S.dropped === 1 ? "" : "s"} could not be exported because ${S.dropped === 1 ? "it has" : "they have"} no usable coordinates. ${S.written} of ${S.expected} were written.</div>` : "") +
    (S.long_notes ? `<div class="note warn"><b>${S.long_notes}</b> note${S.long_notes === 1 ? " is" : "s are"} longer than ${S.note_limit} bytes (about ${S.note_limit} characters; accented letters, dashes and emoji take 2–4). onX keeps only the first ${S.note_limit} bytes of an imported note; RUNBOOK.md lists ${S.long_notes === 1 ? "it" : "them"}.</div>` : "") +
    (S.over_limit ? `<div class="note warn">onX accounts hold at most ${S.limit.toLocaleString("en-US")} markups; this map has ${S.markups.toLocaleString("en-US")}. Remove or exclude some before importing.</div>` : "");
  MANIFEST.forEach(e => {
    const d = document.createElement("div");
    d.className = "rb-step";
    d.innerHTML = `
      <label class="rb-title"><input type="checkbox"> <span>${e.n}. ${esc(e.folder)}</span>
        <span class="rb-count">${e.count} markups</span></label>
      <div class="rb-files">${e.files.map(f =>
        `<span class="rb-file ${f.kml ? "kml" : ""}">${esc(f.path.split("/").pop())}</span>`).join("")}</div>
      <p class="rb-do">Import <b>all ${e.files.length} file${e.files.length > 1 ? "s" : ""} together</b>,
         tick “Import map data to a new folder”, then:</p>
      <div class="rb-rename">Rename the new folder to <code>${esc(e.folder)}</code></div>`;
    d.querySelector("input").onchange = ev => d.classList.toggle("done", ev.target.checked);
    host.appendChild(d);
  });
}

const esc = s => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let HELP_RETURN = null;   // what had focus when Help opened
function openHelp() {
  HELP_RETURN = document.activeElement;
  $("#help").classList.remove("hidden");
  $("#help-close").focus();
}
function closeHelp() {
  $("#help").classList.add("hidden");
  const r = HELP_RETURN; HELP_RETURN = null;
  if (r && r.isConnected) r.focus({ preventScroll: true });
}

/* ---------- confirmations ---------- */
/* One in-page dialog (#confirm) serves Start over and the unsaved-note prompt.
   Never window.confirm: it blocks automation and doesn't match the design. */
let CONFIRM = null;   // {ret, cancel}
function openConfirm({ title, body, buttons, ret }) {
  CONFIRM = { ret: ret || document.activeElement, cancel: buttons.find(b => b.cancel) };
  $("#confirm-title").textContent = title;
  $("#confirm-body").textContent = body;
  const host = $("#confirm-actions");
  host.textContent = "";
  let initial = null;
  for (const b of buttons) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "btn small " + (b.cls || "");
    el.textContent = b.label;
    el.onclick = b.run;
    host.appendChild(el);
    if (b.initial) initial = el;
  }
  $("#confirm").classList.remove("hidden");
  (initial || host.firstChild).focus();
}
function closeConfirm(focusRet = true) {
  $("#confirm").classList.add("hidden");
  const r = CONFIRM && CONFIRM.ret; CONFIRM = null;
  if (focusRet && r && r.isConnected) r.focus({ preventScroll: true });
}
function cancelConfirm() { if (CONFIRM && CONFIRM.cancel) CONFIRM.cancel.run(); else closeConfirm(); }

function noteIsChanged() {
  if (!NOTE_EDIT || !DATA) return false;
  const it = allItems().find(i => i.uid === NOTE_EDIT.uid);
  return !!it && NOTE_EDIT.draft !== (it.desc || "");
}

function resetAll() {
  closePop(); closeBulk();
  DATA = null; EDITS = {}; SEL.clear(); ANCHOR = null; ZIP = null; MANIFEST = null; NOTE_EDIT = null;
  resetFilters();
  renderSourceNotice({});
  $("#file").value = "";
  showStage("drop");
  setStatus("");
  window.__cairnLoaded = false; window.__cairnExported = false;
}

function requestStartOver() {
  const ret = document.activeElement;
  const uids = new Set(Object.keys(EDITS));
  if (noteIsChanged()) uids.add(NOTE_EDIT.uid);
  const n = uids.size;
  openConfirm({
    title: "Start over?",
    body: n
      ? `You have ${n} unexported change${n === 1 ? "" : "s"} to this map. Starting over discards ${n === 1 ? "it" : "them"}.`
      : "This clears the current map.",
    ret,
    buttons: [
      { label: "Cancel", initial: true, cancel: true, run: () => closeConfirm() },
      { label: "Start over", cls: "danger", run: () => { closeConfirm(false); resetAll(); } },
    ],
  });
}

function requestExport() {
  const ret = document.activeElement;
  if (!NOTE_EDIT) { doExport(); return; }
  const it = allItems().find(i => i.uid === NOTE_EDIT.uid);
  if (!noteIsChanged()) { closeNote(it, false); doExport(); return; }
  const uid = NOTE_EDIT.uid;
  openConfirm({
    title: "Save your note?",
    body: `Your note for \u201c${it.name}\u201d hasn't been saved.`,
    ret,
    buttons: [
      { label: "Cancel", cancel: true, run: () => {
          closeConfirm(false);
          const ta = document.querySelector(`tr[data-uid="${CSS.escape(uid)}"] .desc-in`);
          if (ta) ta.focus({ preventScroll: true });
        } },
      { label: "Discard", run: () => { closeConfirm(false); closeNote(it, false); doExport(); } },
      { label: "Save", cls: "primary", initial: true, run: () => { closeConfirm(false); closeNote(it, true); doExport(); } },
    ],
  });
}

/* ---------- wire ---------- */
window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-ui-icon]").forEach(el => {
    el.insertAdjacentHTML("beforeend", UI_ICON[el.dataset.uiIcon] || "");
  });
  wireDrop();
  $("#filter").oninput = e => { FILTERS.q = e.target.value; renderFolders(); };
  document.querySelectorAll("#type-filter [data-kind]").forEach(b => b.onclick = () => setKind(b.dataset.kind));
  document.querySelectorAll(".rail .facet[data-sec] .sec-h").forEach(h =>
    h.onclick = () => toggleRailSection(h.closest(".facet").dataset.sec));
  $("#clear-sel").onclick = () => { SEL.clear(); ANCHOR = null; renderFolders(); };
  $("#more-btn").onclick = e => {
    e.stopPropagation();
    const open = $("#more-menu").classList.toggle("hidden") === false;
    $("#more-btn").setAttribute("aria-expanded", String(open));
    if (open) $("#more-menu button").focus();
  };
  $("#more-menu").onclick = e => e.stopPropagation();
  const menuAct = (id, fn) => $(id).onclick = () => { closeMenu(); fn(); };
  menuAct("#bulk-desc", () => bulk(it => it.desc ? { name: oneLine(it.desc) } : {}));
  menuAct("#bulk-exclude", () => bulk({ included: false }));
  menuAct("#bulk-include", () => bulk({ included: true }));
  $("#help-link").onclick = openHelp;
  // faq.html / walkthrough.html link here as "./#help".
  if (location.hash === "#help") openHelp();
  $("#help-close").onclick = closeHelp;
  $("#help").addEventListener("click", e => { if (e.target === $("#help")) closeHelp(); });
  $("#mark-modal").addEventListener("click", e => { if (e.target === $("#mark-modal")) closeBulk(); });
  // Clicks inside the popover stay there: its icon grid re-renders under the
  // pointer, so the document-level "outside click" test can't be trusted.
  $("#mark-pop").addEventListener("click", e => e.stopPropagation());
  $("#bulk-icon").onclick = openBulk;
  $("#bulk-line").onclick = openLineBulk;
  $("#export").onclick = requestExport;
  $("#back").onclick = () => showStage("edit");
  document.querySelectorAll(".newmap").forEach(b => b.onclick = requestStartOver);
  $("#confirm").addEventListener("click", e => { if (e.target === $("#confirm")) cancelConfirm(); });
  $("#download").onclick = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(ZIP); a.download = "onx_ready.zip"; a.click();
  };
  // Outside click closes the menu and the popover (Cancel semantics).
  document.addEventListener("click", e => {
    closeMenu();
    if (POP && !$("#mark-pop").contains(e.target)) closePop();
  });
  window.addEventListener("resize", () => { if (POP && POP.anchor.isConnected) placePop(POP.anchor); });
  document.addEventListener("keydown", e => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || ""));
    if (e.key === "Tab") {
      if (CONFIRM) trapTab(e, $("#confirm .modal-card"));
      else if (!$("#help").classList.contains("hidden")) trapTab(e, $("#help .modal-card"));
      else if (BULK) trapTab(e, $("#mark-dialog"));
      return;
    }
    if (e.key === "Escape") {
      // Priority: close what's in front, then an open note, then let a focused
      // field revert its own edit, else clear the selection.
      if (CONFIRM) { e.preventDefault(); cancelConfirm(); return; }
      if (!$("#help").classList.contains("hidden")) { closeHelp(); return; }
      if (BULK) { closeBulk(); return; }
      if (POP) { closePop(); return; }
      if (!$("#more-menu").classList.contains("hidden")) { closeMenu(); $("#more-btn").focus(); return; }
      if (typing) return;                       // wireTextField handles the revert
      if (NOTE_EDIT) { closeNote(null, false); return; }
      if (SEL.size) { SEL.clear(); ANCHOR = null; renderFolders(); }
      return;
    }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a" && !typing && DATA &&
        document.body.dataset.stage === "edit" && !BULK && !POP) {
      e.preventDefault();
      setSelectAll(!(SEL.size && SEL.size === selectableItems().length));
    }
  });
  boot();
});
