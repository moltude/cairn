/* Cairn web app — UI shell.
   All map logic is the existing Python engine, running in Pyodide. */
let py = null, DATA = null, EDITS = {}, SEL = new Set(), ZIP = null, MANIFEST = null;
let ANCHOR = null;   // last row clicked without shift -- the pivot for range select
/* EDITS, SEL, ANCHOR, NOTE_EDIT, POP and BULK all key items by uid. A uid is
   an opaque id from bridge.py ("i0", "i1", ...) that stays the same when the
   item moves to another folder (ENG-07): never parse it for a folder or
   position -- read the item's group from DATA instead. */

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
/* Folders (UI-32). The bridge owns membership and names (ENG-07); after each
   move, rename or merge DATA.groups is rebuilt from the layout it returns,
   keeping the same JS item objects (they carry the unexported edits). */
let RENAME = null;                     // {key, draft, where: "head"|"rail", declined?} -- the one folder name being edited
let DRAG = null;                       // row drag in progress (pointer events)
let MOVE = null;                       // More ▸ Move to… list state
let SAVED = null;                      // {home, names, edits} as loaded or at the last export (Start over)
let PENDING_MERGE = null;              // a taken name, waiting for its deferred render to offer the merge
const NEW_TARGET = "\u0000new";        // drop key of the rail's "+ New folder"

const $ = s => document.querySelector(s);
const setStatus = (t, cls = "") => { const e = $("#status"); e.textContent = t; e.className = "status " + cls; };
/** An error that a later success has made stale ("A folder needs a name."). */
const clearError = () => { if ($("#status").classList.contains("err")) setStatus(""); };

/* Keyboard focus across re-renders. The rail and the list are rebuilt with
   innerHTML, which drops focus to <body>. Every control they rebuild carries a
   data-fk key that is stable across renders (row uid / folder key / facet key
   plus which control); capture it BEFORE rebuilding -- once the node is gone,
   activeElement is already <body> -- and focus the same key afterwards. A row's
   note button and its open editor share one key, so Save/Cancel land back on
   the note button. A key that no longer exists is a silent no-op. */
const focusedKey = () => document.activeElement?.dataset?.fk || null;
const fkEl = k => [...document.querySelectorAll("[data-fk]")].find(e => e.dataset.fk === k) || null;
function refocus(k) {
  if (!k || focusedKey() === k) return;
  fkEl(k)?.focus({ preventScroll: true });
}

/* A render that follows leaving a field (Tab, or a click elsewhere) runs on
   the next task, once focus has landed, so the control being focused isn't
   rebuilt under it. With a mouse button down it waits for the release: a
   rebuild between a button's pointerdown and pointerup replaces the button,
   and the click is lost. Queued from pointerup, it runs after that click. */
let POINTER_HELD = false, FLUSH_T = null;
const DEFERRED = [];
function deferRender(fn) {
  DEFERRED.push(fn);
  if (!POINTER_HELD) scheduleFlush();
}
function scheduleFlush() {
  if (FLUSH_T === null && DEFERRED.length) FLUSH_T = setTimeout(flushDeferred);
}
/** Run whatever is waiting now (Export and Start over must see its result). */
function flushDeferred() {
  clearTimeout(FLUSH_T); FLUSH_T = null;
  DEFERRED.splice(0).forEach(fn => fn());
}
function wirePointerHeld() {
  document.addEventListener("pointerdown", () => { POINTER_HELD = true; }, true);
  const up = () => { POINTER_HELD = false; scheduleFlush(); };
  document.addEventListener("pointerup", up, true);
  document.addEventListener("pointercancel", up, true);
  window.addEventListener("blur", up);
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
    PENDING_FILES = null; showDropWait(false);
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
    showDropWait(true);
    return;
  }
  showDropWait(false);
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
    resetFolderState();
    SAVED = savedState();
    $("#map-title").textContent = mapTitle(DATA);
    $("#map-label").textContent = mapLabel(DATA);
    renderSourceNotice(DATA);
    renderEdit();
    showStage("edit");
    setStatus("Map loaded", "ready");
    window.__cairnLoaded = true;
    warnFillLoss();
  } catch (e) {
    // Pyodide surfaces the whole Python traceback. The last line is the actual
    // message and the engine's messages are already user-friendly ("No features
    // found... make sure this is a CalTopo export"); the stack above it is noise
    // to a hiker. Keep the full thing in the console for us.
    setStatus("Couldn't read that file — " + humanError(e), "err");
    console.error(e);
  }
}

/** The "Getting ready…" line is a status region: empty it when hidden, or a
    screen reader's view of the page says it all session. */
function showDropWait(on) {
  const w = $("#drop-wait");
  w.textContent = on ? "Getting ready…" : "";
  w.classList.toggle("hidden", !on);
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

/* The items outside any folder of the file. The bridge says which folder that
   is (by where its items came from, not its name) and clears it on a rename
   (UI-32): a CalTopo folder called "Unorganized" is an ordinary folder. */
const isUnorganized = g => !!g.unorganized;
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
  const fl = $("#folder-facets"); rebuild(fl);
  const facetBtn = (label, count, key, italic) => {
    const fkey = "folder|" + (key === null ? "\u0000all" : key);
    if (key !== null && RENAME && RENAME.where === "rail" && RENAME.key === key) {
      // A new folder's name, edited in place (NameNewFolder mockup).
      const d = document.createElement("div");
      d.className = "facet-btn naming";
      d.innerHTML = `<input class="folder-name-in" data-fk="${esc(fkey)}" aria-label="Folder name" maxlength="${FOLDER_NAME_MAX}" autocomplete="off"><span class="facet-count">${count}</span>`;
      wireFolderName(d.querySelector("input"));
      fl.appendChild(d);
      return;
    }
    const b = document.createElement("button");
    b.type = "button"; b.className = "facet-btn" + (italic ? " unorg" : "");
    b.setAttribute("aria-pressed", String(FILTERS.folder === key));
    b.dataset.fk = fkey;
    const here = key !== null && DRAG && DRAG.active && DRAG.here === key;
    if (key !== null) b.dataset.drop = key;
    if (here) b.classList.add("here-now");
    b.innerHTML = `<span class="facet-name"${key !== null ? ` title="${esc(label)}"` : ""}>${esc(label)}</span><span class="facet-count">${here ? "here now" : count ?? ""}</span>`;
    b.onclick = () => {
      FILTERS.folder = FILTERS.folder === key && key !== null ? null : key;
      renderRail(); renderFolders();
    };
    if (key !== null && count === 0) {
      // An empty folder (made with + New folder, or loaded empty) can be
      // removed: an × beside it, shown on hover and focus (round 4). A
      // wrapper, since a button can't hold another button.
      const row = document.createElement("div");
      row.className = "facet-row empty";
      const x = document.createElement("button");
      x.type = "button"; x.className = "facet-x"; x.dataset.fk = "remove|" + key;
      x.setAttribute("aria-label", `Remove empty folder ${label}`);
      x.title = "Remove empty folder";
      x.innerHTML = UI_ICON.close;
      x.onclick = e => { e.stopPropagation(); removeEmptyFolder(key); };
      row.append(b, x);
      fl.appendChild(row);
      return;
    }
    fl.appendChild(b);
  };
  facetBtn("All", "", null, false);
  DATA.groups.forEach(g => facetBtn(g.name, g.items.length, g.key, isUnorganized(g)));
  // + New folder: a drop target for dragged rows, and a button (round 4):
  // clicked, it moves the ticked rows into a new folder, or with nothing
  // ticked makes an empty one, ready to drop rows on.
  const nf = document.createElement("button");
  nf.type = "button"; nf.className = "new-folder"; nf.textContent = "+ New folder";
  nf.dataset.fk = "newfolder";
  nf.dataset.drop = NEW_TARGET;   // set as a property: an HTML parser turns the NUL into U+FFFD
  nf.onclick = newFolderClicked;
  fl.appendChild(nf);

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
  hideTip();                       // its control is about to be replaced
  const shownUids = new Set(shownItems().map(i => i.uid));
  const selectableUids = new Set(selectableItems().map(i => i.uid));
  for (const uid of SEL) if (!selectableUids.has(uid)) SEL.delete(uid);
  if (NOTE_EDIT && !shownUids.has(NOTE_EDIT.uid)) NOTE_EDIT = null;
  renderChips();

  const host = $("#folders"); rebuild(host);
  DATA.groups.forEach(g => {
    const items = visibleItems(g);
    if (!items.length) {
      if (!g.items.length && showsEmptyFolders(g)) host.appendChild(emptyFolderSection(g));
      return;
    }
    const el = document.createElement("section");
    el.className = "folder";
    el.setAttribute("aria-label", g.name);
    const collapsed = COLLAPSED.has(g.key);
    const sub = isUnorganized(g) ? "Not in any CalTopo folder"
      : items.length === g.items.length ? `${g.items.length} item${g.items.length === 1 ? "" : "s"}`
      : `${items.length} of ${g.items.length} shown`;
    const naming = RENAME && RENAME.where === "head" && RENAME.key === g.key;
    el.innerHTML = `
      <div class="folder-head">
        <h2>${naming
          ? `<input class="folder-name-in" data-fk="fname|${esc(g.key)}" aria-label="Folder name" maxlength="${FOLDER_NAME_MAX}" autocomplete="off">`
          : `<button type="button" class="folder-name" data-fk="fname|${esc(g.key)}" title="${esc(g.name)}">${esc(g.name)}</button>`}</h2>
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
    if (naming) wireFolderName(el.querySelector(".folder-name-in"));
    else el.querySelector(".folder-name").onclick = () => startRename(g.key, "head");
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

/** An empty folder shows as a header only (so it can be renamed there), when
    no search, type or icon filter would hide it anyway. */
const showsEmptyFolders = g => !FILTERS.q && !FILTERS.kind && !FILTERS.icons.size && !FILTERS.attention &&
  (FILTERS.folder === null || FILTERS.folder === g.key);
function emptyFolderSection(g) {
  const el = document.createElement("section");
  el.className = "folder empty-folder";
  el.setAttribute("aria-label", g.name);
  const naming = RENAME && RENAME.where === "head" && RENAME.key === g.key;
  el.innerHTML = `<div class="folder-head">
      <h2>${naming
        ? `<input class="folder-name-in" data-fk="fname|${esc(g.key)}" aria-label="Folder name" maxlength="${FOLDER_NAME_MAX}" autocomplete="off">`
        : `<button type="button" class="folder-name" data-fk="fname|${esc(g.key)}" title="${esc(g.name)}">${esc(g.name)}</button>`}</h2>
      <span class="folder-sub">Empty</span></div>`;
  if (naming) wireFolderName(el.querySelector(".folder-name-in"));
  else el.querySelector(".folder-name").onclick = () => startRename(g.key, "head");
  return el;
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
/** A note's preview in the list: its first line that isn't blank (round 4).
    The rest shows on hover (the tip below). "Use note as name" still joins
    every line (oneLine). */
const firstLine = s => String(s || "").split("\n").map(l => l.trim()).find(Boolean) || "";

/* ---------- the hover tip (round 4) ----------
   One styled popup (#tip) for a row name or note preview that hides text,
   and for a row's caution mark: shown after a short hover or on keyboard
   focus, with line breaks kept, inside the window, selectable and copyable
   (the pointer may move onto it), and gone on Esc. Not the native `title`:
   it drops line breaks on some platforms and can't be styled. */
const TIP_SRC = ".name-in, .note-btn, .caution";
const TIP = { src: null, showT: null, hideT: null, over: false };
let LAST_POINTER = 0;   // when the last press happened: focus right after it isn't keyboard focus
const cut = el => !!el && el.scrollWidth > el.clientWidth + 1;
function tipText(src, viaKey = false) {
  const tr = src.closest("tr[data-uid]");
  const it = tr && allItems().find(i => i.uid === tr.dataset.uid);
  if (!it) return null;
  if (src.classList.contains("caution")) return cautionText(it);
  if (src.classList.contains("name-in")) {
    // Not while typing in it (the field shows what is typed), unless it was
    // just reached by keyboard.
    return (viaKey || src !== document.activeElement) && cut(src) ? src.value : null;
  }
  const desc = String(it.desc || "").trim();
  if (!desc) return null;
  return desc !== firstLine(desc) || cut(src.querySelector(".note-text")) ? desc : null;
}
function scheduleTip(src, ms, viaKey = false) {
  clearTimeout(TIP.showT); clearTimeout(TIP.hideT);
  if (TIP.src === src && tipShown()) return;
  TIP.showT = setTimeout(() => showTip(src, viaKey), ms);
}
const tipShown = () => !$("#tip").classList.contains("hidden");
function showTip(src, viaKey = false) {
  if (!src.isConnected || DRAG || CONFIRM || BULK || POP || MOVE) return;
  // Still pointed at or focused (a scroll may have moved it from under the pointer).
  if (!src.matches(":hover") && !src.contains(document.activeElement)) return;
  const text = tipText(src, viaKey);
  if (!text) { hideTip(); return; }
  hideTip();
  const tip = $("#tip");
  tip.textContent = text;
  tip.classList.remove("hidden");
  TIP.src = src;
  src.setAttribute("aria-describedby", "tip");
  // Below the control, else above it; never over it (that would block the
  // click it is waiting for), and always inside the window.
  const r = src.getBoundingClientRect();
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  const left = Math.max(8, Math.min(r.left, vw - w - 8));
  let top = r.bottom + 6;
  if (top + h > vh - 8) top = r.top - h - 6 >= 8 ? r.top - h - 6 : Math.max(8, vh - h - 8);
  tip.style.left = `${left}px`; tip.style.top = `${top}px`;
}
function hideTip() {
  clearTimeout(TIP.showT); clearTimeout(TIP.hideT);
  TIP.over = false;
  if (TIP.src) { TIP.src.removeAttribute("aria-describedby"); TIP.src = null; }
  const tip = $("#tip");
  if (tip && !tip.classList.contains("hidden")) { tip.classList.add("hidden"); tip.textContent = ""; }
}
/** Leaving the control or the tip: a short grace, so the pointer can cross
    from one to the other (to select the text). */
function laterHideTip() {
  clearTimeout(TIP.showT); clearTimeout(TIP.hideT);
  TIP.hideT = setTimeout(() => { if (!TIP.over) hideTip(); }, 200);
}
function wireTip() {
  const host = $("#folders"), tip = $("#tip");
  host.addEventListener("pointerover", e => {
    if (e.pointerType === "touch" || DRAG) return;
    const src = e.target.closest(TIP_SRC);
    if (src) scheduleTip(src, 450);
  });
  host.addEventListener("pointerout", e => {
    const src = e.target.closest(TIP_SRC);
    if (!src || src.contains(e.relatedTarget)) return;
    if (TIP.src === src || !tipShown()) laterHideTip();
  });
  host.addEventListener("focusin", e => {
    const src = e.target.closest(TIP_SRC);
    if (src && Date.now() - LAST_POINTER > 300) scheduleTip(src, 150, true);   // keyboard focus
  });
  host.addEventListener("focusout", e => { if (TIP.src && TIP.src.contains(e.target)) hideTip(); });
  // Typing in a name it describes: the field shows the text now.
  host.addEventListener("input", e => { if (TIP.src && TIP.src === e.target) hideTip(); });
  tip.addEventListener("pointerenter", () => { TIP.over = true; clearTimeout(TIP.hideT); });
  tip.addEventListener("pointerleave", () => { TIP.over = false; laterHideTip(); });
  document.addEventListener("pointerdown", e => {
    LAST_POINTER = Date.now();
    if (!tip.contains(e.target)) hideTip();
  }, true);
  // Esc dismisses the tip and nothing else (not a name's revert, not the
  // selection): capture, ahead of every other Esc handler.
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && tipShown()) { e.preventDefault(); e.stopPropagation(); hideTip(); }
  }, true);
  // A scroll moves the control from under its tip (not one that is waiting:
  // scrolling a row into view is how a hover often starts).
  window.addEventListener("scroll", e => { if (e.target !== tip && tipShown()) hideTip(); }, true);
  window.addEventListener("resize", hideTip);
}
/** What won't carry over to onX for this item, one plain line each (item 4). */
function cautionText(it) { return null; }

function row(it) {
  const tr = document.createElement("tr");
  tr.dataset.uid = it.uid;
  const isWp = it.kind === "waypoints";
  if (it.needs_attention) tr.classList.add("attention");
  if (SEL.has(it.uid)) tr.classList.add("sel");
  if (!it.included) tr.classList.add("excluded");
  if (POP && POP.uid === it.uid) tr.classList.add("editing");
  if (DRAG && DRAG.active && DRAG.uidSet.has(it.uid)) tr.classList.add("dragging");
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
        <span class="note-text${firstLine(it.desc) ? "" : " empty"}">${esc(firstLine(it.desc) || "Add a note")}</span>${UI_ICON.pencil}</button>`}</td>
    <td class="iconcol">${isWp
      ? `<button type="button" class="icon-btn" data-fk="${fk}mark" title="${esc(it.why)}" aria-label="${esc(iconLabel)}, ${esc(cname)}. Change icon or color">${markerSVG(it.icon, it.hex, 22, 28)}${it.needs_attention
          ? `<span class="whymark" title="${esc(it.why)}">Default pin</span>`
          // An icon an onX file named that isn't in onX's list (Phase 2 flags
          // it): kept and exported as is, but marked so it gets a look.
          : `<span class="icon-name${it.unknown_icon ? " unknown-icon" : ""}">${esc(it.icon)}</span>`}</button>`
      : `<button type="button" class="line-btn" data-fk="${fk}mark" title="${esc(cname)} — ${esc(it.why)}" aria-label="${rowKindWord(it)}, ${esc(cname)}, ${styleLabel(it.style)}, ${weightLabel(it.weight)}. Change ${it.kind === "tracks" ? "line" : "area"}">${lineSVG(it.hex, it.kind, 22, 19, it.style, it.weight)}<span class="icon-name kind">${rowKindWord(it)}</span></button>`}</td>`;
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
  const commit = now => {
    const v = el.value;
    if (required && !v.trim()) {
      el.value = el.dataset.orig ?? "";
      setStatus("A name is required — onX can only search by name.", "err");
      return;
    }
    if (v === el.dataset.orig) return;
    el.dataset.orig = v;
    edit(it, { [key]: v }, { render: false });
    // Enter keeps focus in the field: render now (refocus finds it again).
    // `change` fires on blur BEFORE focus lands on the next control; a
    // synchronous re-render would destroy that control mid-Tab, so leaving
    // the field renders later (deferRender).
    if (now) refreshAfterEdit();
    else deferRender(() => DATA && refreshAfterEdit());
  };
  // Enter saves and Esc reverts, both staying in the field (focus never drops
  // to the page): Esc's restored value means the blur that follows sees no change.
  el.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      e.preventDefault();
      el.value = el.dataset.orig ?? "";
    } else if (e.key === "Enter") {
      e.preventDefault();
      commit(true);
    }
  });
  el.addEventListener("change", () => commit(false));
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
  clearError();
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
  $("#bulk-line").classList.toggle("hidden", !selectedItems().some(hasLineStyle));
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
/* Lines and areas both have a line style and weight (UI-25). The two of each
   above are the choices; onX's dot and 2.0 from an onX file are shown and kept. */
const hasLineStyle = it => it.kind === "tracks" || it.kind === "shapes";
const styleLabel = s => STYLE_NAMES[s] || (s === "dot" ? "Dotted" : "Solid");
const weightLabel = w => WEIGHT_NAMES[w] || (w === "2.0" ? "Extra thin" : "Thin");
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
          fk: anchor.dataset.fk, style: it.style, weight: it.weight };
  const isWp = it.kind === "waypoints";
  const isLine = it.kind === "tracks";
  const styled = hasLineStyle(it);   // a line or an area: Style and Weight below the colors
  const pop = $("#mark-pop");
  pop.classList.toggle("line", isLine);
  pop.setAttribute("aria-label", `Change ${isWp ? "icon and color" : isLine ? "line" : "area"} for ${it.name}`);
  pop.innerHTML = `
    <div class="pop-head">
      <span class="pop-preview"></span>
      <div class="pop-title"><span class="pop-name">${esc(it.name || "Untitled")}</span></div>
    </div>
    ${isLine ? `<div class="pop-map"></div>` : ""}
    <div class="pop-sec">
      <span class="label">Color</span>
      <div class="palette${styled ? " spread" : ""}">${paletteHTML(paletteFor([it]), POP.color)}</div>
    </div>
    ${isWp ? `<div class="pop-sec icons">
      <div class="sec-row"><span class="label">Icon</span><span class="sec-count">${DATA.icons.length} icons</span></div>
      <input type="search" class="icon-search" aria-label="Find an icon" placeholder="Find an icon" autocomplete="off">
      <div class="icon-grid" role="group" aria-label="Icons"></div>
    </div>` : styled ? lineOptsHTML(POP.style, POP.weight) : ""}
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
/** The marker the popover belongs to. A re-render while it is open (one that
    waited for the click that opened it, say) replaces the row: find the new
    marker by its focus key. */
function popAnchor() {
  if (!POP) return null;
  if (!POP.anchor.isConnected) POP.anchor = fkEl(POP.fk) || POP.anchor;
  return POP.anchor.isConnected ? POP.anchor : null;
}

function drawPop() {
  const it = popItem(); if (!it) return;
  const pop = $("#mark-pop");
  const hex = (colorOf(POP.color) || {}).hex || it.hex;
  const isWp = it.kind === "waypoints";
  const isLine = it.kind === "tracks";
  // A line is previewed on the map strip, so its header carries no second drawing.
  pop.querySelector(".pop-preview").innerHTML = isWp ? markerSVG(POP.icon, hex, 52, 64) : isLine ? "" : lineSVG(hex, it.kind, 52, 44, POP.style, POP.weight);
  pop.querySelectorAll(".swatch-btn").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.rgba === POP.color)));
  if (isLine) pop.querySelector(".pop-map").innerHTML = lineMapSVG(hex, POP.style, POP.weight);
  if (hasLineStyle(it)) syncLineOpts(pop, POP.style, POP.weight);
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
  if (hasLineStyle(it)) {
    if (POP.style !== it.style) patch.style = POP.style;
    if (POP.weight !== it.weight) patch.weight = POP.weight;
  }
  closePop();
  if (Object.keys(patch).length) edit(it, patch);
}

function closePop() {
  if (!POP) return;
  const anchor = popAnchor();
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
      <div class="modal-head plain"><h2>Change ${plural(items.length, "item")}</h2>
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
    const nowMark = isWp ? markerSVG(it.icon, it.hex, 22, 28) : lineSVG(it.hex, it.kind, 22, 20, it.style, it.weight);
    const afterMark = isWp ? markerSVG(toIcon, hexOf(toColor) || it.hex, 22, 28) : lineSVG(hexOf(toColor) || it.hex, it.kind, 22, 20, it.style, it.weight);
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
  setStatus(`Changed ${plural(n, "item")}`, "ready");
}

/* ---------- several lines or areas: the Line style dialog ---------- */
function openLineBulk() {
  const lines = selectedItems().filter(hasLineStyle);
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
  const word = lines.every(i => i.kind === "shapes") ? "area" : lines.every(i => i.kind === "tracks") ? "line" : "item";
  setStatus(`Changed ${n} ${word}${n === 1 ? "" : "s"}`, "ready");
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

/* ---------- folders: move, rename, merge (UI-32) ---------- */
/* Every route ends in moveTo / finishRename / mergeInto, which call the bridge
   (ENG-07) and then rebuild DATA.groups from the layout it returns. Export
   needs nothing more: export_zip walks the bridge's own groups. */
const FOLDER_NAME_MAX = 100;

function resetFolderState() {
  abandonDrag(); closeMove(false);
  RENAME = null; PENDING_MERGE = null; SAVED = null;
}

const groupByKey = key => DATA.groups.find(g => g.key === key) || null;
/** uid -> its folder (or the folder's key, with `keys`). */
function groupOfUid(keys = false) {
  const m = new Map();
  DATA.groups.forEach(g => g.items.forEach(i => m.set(i.uid, keys ? g.key : g)));
  return m;
}
/** The folder every one of these items is already in, or null when they come
    from several. Moving them there would do nothing, so it reads "here now"
    and isn't offered; a folder holding only SOME of them is a real target. */
function hereKey(uids) {
  const m = groupOfUid();
  const keys = new Set(uids.map(u => m.get(u)?.key));
  return keys.size === 1 ? [...keys][0] : null;
}

/** Arguments cross into Python as globals, never inside the source (as for
    load_files and apply_edits). */
function pyJSON(src, vars) {
  for (const [k, v] of Object.entries(vars)) py.globals.set(k, v);
  return JSON.parse(py.runPython(src));
}

/** Rebuild DATA.groups from the bridge's layout ({key, name, safe,
    unorganized, uids} per folder, in order), reusing the item objects, and
    forget filters and folds that point at a folder that is gone. Checks
    everything before changing anything: a throw leaves DATA as it was.
    Returns the name of the folder the folder filter was on, if it is gone. */
function applyLayout(res) {
  const byUid = new Map(allItems().map(i => [i.uid, i]));
  const old = new Map(DATA.groups.map(g => [g.key, g]));
  const plan = res.folders.map(f => ({ f, items: f.uids.map(u => {
    const it = byUid.get(u);
    if (!it) throw new Error(`Lost track of item ${u}.`);
    return it;
  }) }));
  if (plan.reduce((n, p) => n + p.items.length, 0) !== byUid.size)
    throw new Error("The folders no longer add up.");
  const groups = plan.map(({ f, items }) => {
    const g = old.get(f.key) || { key: f.key };
    g.name = f.name; g.safe = f.safe; g.unorganized = !!f.unorganized; g.items = items;
    return g;
  });
  DATA.groups = groups;
  const live = new Set(groups.map(g => g.key));
  [...COLLAPSED].forEach(k => { if (!live.has(k)) COLLAPSED.delete(k); });
  let gone = null;
  if (FILTERS.folder !== null && !live.has(FILTERS.folder)) {
    gone = old.get(FILTERS.folder)?.name ?? null;
    FILTERS.folder = null;
  }
  if (RENAME && !live.has(RENAME.key)) RENAME = null;
  DATA.totals.folders = groups.length;
  return gone;
}

/** applyLayout(res), or, should that fail, the bridge's own layout: the bridge
    may already have moved the items, and what the screen shows must be what
    export writes. Throws only if even that can't be shown. */
function syncLayout(res) {
  try { return applyLayout(res); }
  catch (e) {
    console.error(e);
    return applyLayout(JSON.parse(py.runPython("bridge.layout_json()")));
  }
}

/** After a failed folder action: show the bridge's layout, whatever it is. */
function resyncAfterFailure() {
  try { syncLayout(JSON.parse(py.runPython("bridge.layout_json()"))); }
  catch (e) { console.error(e); }
  renderEdit();
}

/** An open note whose row a move takes off screen (a folder filter, say)
    would be closed by the next render and its draft lost: save it instead. */
function keepNoteDraft() {
  if (!NOTE_EDIT) return;
  if (shownItems().some(i => i.uid === NOTE_EDIT.uid)) return;
  const it = allItems().find(i => i.uid === NOTE_EDIT.uid);
  const v = NOTE_EDIT.draft;
  NOTE_EDIT = null;
  if (it && v !== (it.desc || "")) edit(it, { desc: v }, { render: false });
}

const shortName = s => { const c = [...s]; return c.length > 48 ? c.slice(0, 47).join("").trimEnd() + "…" : s; };

/** After a move or merge: re-render and say what happened, and why the view
    changed when the folder it was filtered to is gone. */
function afterMove(res, uids, gone) {
  // The ticks did their job: moved rows are unticked, so the next drag of one
  // of them doesn't drag the whole old selection along. Other ticks stay.
  uids.forEach(u => SEL.delete(u));
  if (!SEL.size) ANCHOR = null;
  keepNoteDraft();
  refreshAfterEdit();
  const target = groupByKey(res.key);
  setStatus(`Moved ${plural(res.moved, "item")} to ${res.created ? "a new folder" : target ? shortName(target.name) : "the folder"}.` +
    (gone !== null ? ` “${shortName(gone)}” is empty now, so it was removed.` : ""), "ready");
}

/** Move items into the folder `key`, or into a new folder (NEW_TARGET; the
    bridge picks its default name), whose name is then open for editing in the
    rail. Returns the bridge's answer. */
function moveTo(uids, key) {
  if (!DATA || !uids.length) return null;
  closePop();
  let res, gone;
  try {
    const u = JSON.stringify(uids);
    res = key === NEW_TARGET
      ? pyJSON("bridge.move_to_new_folder(_cairn_uids)", { _cairn_uids: u })
      : pyJSON("bridge.move_items(_cairn_uids, _cairn_key)", { _cairn_uids: u, _cairn_key: key });
    if (!res.ok) throw new Error("That folder name is taken.");
    gone = syncLayout(res);
  } catch (e) {
    setStatus("Couldn't move — " + humanError(e), "err"); console.error(e);
    resyncAfterFailure();
    return null;
  }
  if (res.created) {
    RENAME = { key: res.key, draft: res.folders.find(f => f.key === res.key).name, where: "rail" };
    RAIL_FOLDED.delete("folders");
  }
  afterMove(res, uids, gone);
  if (res.created) focusRename();
  return res;
}

/** A click (or Enter / Space) on the rail's + New folder (round 4): the
    ticked rows go into a new folder, as if dropped there; with nothing
    ticked, an empty folder is made, to drop rows on. Either way its name
    opens for editing in the rail. */
function newFolderClicked() {
  if (!DATA) return;
  const uids = selectedItems().map(i => i.uid);
  if (uids.length) { moveTo(uids, NEW_TARGET); return; }
  closePop();
  let res;
  try {
    res = pyJSON("bridge.create_folder()", {});
    if (!res.ok) throw new Error("That folder name is taken.");
    syncLayout(res);
  } catch (e) {
    setStatus("Couldn't make a folder — " + humanError(e), "err"); console.error(e);
    resyncAfterFailure();
    return;
  }
  RENAME = { key: res.key, draft: res.folders.find(f => f.key === res.key).name, where: "rail" };
  RAIL_FOLDED.delete("folders");
  refreshAfterEdit();
  setStatus("Made an empty folder.", "ready");
  focusRename();
}

/** The × beside an empty folder in the rail. Focus goes to the next entry
    (the folder below, else + New folder): the × itself is gone. */
function removeEmptyFolder(key) {
  const g = groupByKey(key);
  if (!g || g.items.length) return;
  const i = DATA.groups.indexOf(g);
  const next = DATA.groups[i + 1] ? "folder|" + DATA.groups[i + 1].key : "newfolder";
  let res;
  try {
    res = pyJSON("bridge.remove_empty_folder(_cairn_key)", { _cairn_key: key });
    syncLayout(res);
  } catch (e) {
    setStatus("Couldn't remove — " + humanError(e), "err"); console.error(e);
    resyncAfterFailure();
    return;
  }
  refreshAfterEdit();
  setStatus(`Removed the empty folder “${shortName(g.name)}”.`, "ready");
  fkEl(next)?.focus({ preventScroll: true });
}

function startRename(key, where, draft = null, declined = null) {
  const g = groupByKey(key); if (!g) return;
  clearError();
  RENAME = { key, draft: draft ?? g.name, where, declined };
  if (where === "rail") RAIL_FOLDED.delete("folders");
  where === "head" ? renderFolders() : renderRail();
  focusRename();
}

function focusRename() {
  const inp = document.querySelector(".folder-name-in");
  if (!inp) return;
  inp.focus({ preventScroll: true });
  inp.scrollIntoView({ block: "nearest" });
  inp.select();
}

/** The folder-name input (a table header, or a new folder's rail entry).
    Enter or leaving it saves, Esc keeps the name it had. */
function wireFolderName(inp) {
  const key = RENAME.key;
  inp.value = RENAME.draft;
  inp.title = `Up to ${FOLDER_NAME_MAX} characters`;
  // maxlength cuts typing or a paste silently: say so, but only when it
  // actually cut something (not at exactly 100, not when deleting in a longer
  // name loaded from the file), and take it back once the name is under again.
  const tooLong = `A folder name can be up to ${FOLDER_NAME_MAX} characters.`;
  inp.addEventListener("beforeinput", e => {
    if (!e.inputType.startsWith("insert")) return;
    const added = e.data ?? e.dataTransfer?.getData("text/plain") ?? "";
    const kept = inp.value.length - (inp.selectionEnd - inp.selectionStart);
    if (kept + added.length > FOLDER_NAME_MAX) setStatus(tooLong, "err");
  });
  inp.addEventListener("input", () => {
    if (RENAME && RENAME.key === key) RENAME.draft = inp.value;
    if (inp.value.length < FOLDER_NAME_MAX && $("#status").textContent === tooLong) setStatus("");
  });
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); finishRename(key, true); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finishRename(key, false); }
  });
  // A re-render that replaces the input is not the user leaving it (Chrome
  // fires blur on a focused element as it is removed).
  inp.addEventListener("blur", () => { if (!REBUILDING && inp.isConnected) finishRename(key, true, { defer: true }); });
}

function finishRename(key, save, { defer = false } = {}) {
  if (!RENAME || RENAME.key !== key || !DATA) return;
  const { draft, where, declined } = RENAME;
  RENAME = null;
  const g = groupByKey(key);
  let reopen = false, failed = false;
  // Left unchanged after Cancel on its merge offer: keep the name it has,
  // don't ask again (or Cancel, reopen, leave, ask... would never end).
  if (declined && draft.trim().toLowerCase() === declined.toLowerCase()) save = false;
  if (save && g) {
    const name = draft.trim();
    if (!name) {
      setStatus("A folder needs a name.", "err");
      // A new folder's name (Enter on an empty box) stays open for another
      // try; leaving it keeps the default it has.
      reopen = where === "rail" && !defer;
    } else if (name !== g.name) {
      // The bridge is asked NOW, even when the render waits (deferRender):
      // Export and Start over then see the new name or the pending offer.
      try {
        const res = pyJSON("bridge.rename_folder(_cairn_key, _cairn_name)", { _cairn_key: key, _cairn_name: name });
        if (res.ok) { syncLayout(res); clearError(); }
        else PENDING_MERGE = { key, dup: res.duplicate, where, draft: name };
      } catch (e) {
        setStatus("Couldn't rename — " + humanError(e), "err"); console.error(e);
        failed = true;
      }
    }
  }
  const done = () => {
    if (!DATA) return;
    if (failed) { resyncAfterFailure(); return; }
    if (reopen) { startRename(key, "rail"); setStatus("A folder needs a name.", "err"); return; }
    // Leaving one name for another folder's: keep the new field's selection.
    const a = document.activeElement;
    const sel = a && a.classList.contains("folder-name-in") ? [a.selectionStart, a.selectionEnd] : null;
    renderEdit();
    const now = document.activeElement;
    if (sel && now && now.classList.contains("folder-name-in")) now.setSelectionRange(...sel);
    offerPendingMerge();
  };
  defer ? deferRender(done) : done();
}

/** The merge offer for a taken name, if one is waiting -- only on the edit
    screen, and only while both folders still exist. */
function offerPendingMerge() {
  const m = PENDING_MERGE; PENDING_MERGE = null;
  if (!m || !DATA || document.body.dataset.stage !== "edit" || CONFIRM) return;
  const src = groupByKey(m.key), dst = groupByKey(m.dup.key);
  if (src && dst) offerMerge(src, { key: dst.key, name: dst.name }, m.where, m.draft);
}

/** Empty a host before re-rendering it. Removing a focused folder-name field
    fires its blur; REBUILDING tells that apart from the user leaving it, so a
    re-render while a name is open keeps it open (RENAME draws it again). */
let REBUILDING = false;
function rebuild(host) {
  REBUILDING = true;
  try { host.innerHTML = ""; } finally { REBUILDING = false; }
}

/** The name is taken: offer to move this folder's items into that one.
    Cancel (the default) keeps the old name -- except for a folder just made
    by + New folder, whose name opens again with what was typed, to pick
    another (its items stay in it either way). */
function offerMerge(src, dup, where, draft = null) {
  const ret = fkEl(where === "head" ? "fname|" + src.key : "folder|" + src.key);
  if (!src.items.length) {
    // An empty folder has nothing to move: "Move the 0 items" would offer
    // nothing. Say the name is taken; the folder keeps the name it has.
    setStatus(`“${shortName(dup.name)}” already exists.`, "err");
    return;
  }
  const cancel = where === "rail"
    ? () => { closeConfirm(false); startRename(src.key, "rail", draft, draft); }
    : () => closeConfirm();
  openConfirm({
    title: `“${dup.name}” already exists`,
    body: `Move the ${plural(src.items.length, "item")} in “${src.name}” into it?`,
    ret,
    buttons: [
      { label: "Move them", run: () => { closeConfirm(false); mergeInto(src.key, dup.key, where); } },
      { label: "Cancel", initial: true, cancel: true, run: cancel },
    ],
  });
}

function mergeInto(srcKey, dstKey, where = "head") {
  const src = groupByKey(srcKey);
  if (!src || srcKey === dstKey) return;
  const uids = src.items.map(i => i.uid);
  let res, gone;
  try {
    res = pyJSON("bridge.merge_folders(_cairn_key, _cairn_key2)", { _cairn_key: srcKey, _cairn_key2: dstKey });
    gone = syncLayout(res);
  } catch (e) {
    setStatus("Couldn't move — " + humanError(e), "err"); console.error(e);
    resyncAfterFailure();
    return;
  }
  afterMove(res, uids, gone);
  const to = (where === "head" && fkEl("fname|" + dstKey)) || fkEl("folder|" + dstKey);
  if (to) to.focus({ preventScroll: true });
}

/* ---------- More ▸ Move to… (the keyboard route) ---------- */
function openMoveTo() {
  const uids = selectedItems().map(i => i.uid);
  if (!uids.length) return;
  closeMenu(); closePop();
  const here = hereKey(uids);
  MOVE = { uids, ret: $("#more-btn") };
  const p = $("#move-pop");
  p.innerHTML = `<div class="move-h" id="move-h">Move ${plural(uids.length, "item")} to</div>
    <div class="move-list" role="group" aria-labelledby="move-h">${DATA.groups.map(g => {
      const h = g.key === here;
      return `<button type="button" class="move-opt${isUnorganized(g) ? " unorg" : ""}" data-key="${esc(g.key)}"${h ? " disabled" : ""}>` +
        `<span class="facet-name">${esc(g.name)}${h ? " · here now" : ""}</span>` +
        // The count tells apart two folders a file named alike ("Camp", "camp").
        `<span class="facet-count">${h ? "" : g.items.length}</span></button>`;
    }).join("")}<button type="button" class="move-opt move-new">+ New folder…</button></div>`;
  p.querySelectorAll(".move-opt[data-key]").forEach(b => b.onclick = () => {
    const k = b.dataset.key; closeMove(false);
    moveTo(uids, k);
    const more = $("#more-btn");
    (more.disabled ? fkEl("folder|" + k) : more)?.focus({ preventScroll: true });
  });
  p.querySelector(".move-new").onclick = () => { closeMove(false); moveTo(uids, NEW_TARGET); };
  p.onkeydown = e => {
    const opts = [...p.querySelectorAll(".move-opt:not([disabled])")];
    const i = opts.indexOf(document.activeElement);
    const go = j => { e.preventDefault(); opts[(j + opts.length) % opts.length].focus(); };
    if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i < 0 ? -1 : i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(-1);
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeMove(true); }
    else if (e.key === "Tab") trapTab(e, p);
  };
  p.classList.remove("hidden");
  const r = $("#more-btn").getBoundingClientRect();
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const top = Math.min(r.bottom + 6, vh - 160);
  p.style.top = `${top}px`;
  p.style.maxHeight = `${vh - top - 12}px`;
  p.style.left = `${Math.max(8, Math.min(r.left, vw - p.offsetWidth - 8))}px`;
  const first = p.querySelector(".move-opt:not([disabled])");
  first.focus({ preventScroll: true });
}

function closeMove(focusRet) {
  if (!MOVE) return;
  const { ret } = MOVE;
  MOVE = null;
  $("#move-pop").classList.add("hidden");
  $("#move-pop").innerHTML = "";
  if (focusRet && ret && ret.isConnected && !ret.disabled) ret.focus({ preventScroll: true });
}

/* ---------- drag rows onto a rail folder ----------
   Pointer events rather than HTML5 drag and drop: a row is mostly controls
   (name field, note and marker buttons), the preview must say "Move N items",
   and Esc has to cancel. Press on a row and move 6px to start; the ticked rows
   come along if the pressed row is ticked, else just that row. Not from a
   checkbox, an open note, or a field you are already typing in (that press
   selects text). Drop on a folder in the rail, or "+ New folder". */
const DRAG_START_PX = 6;
let SWALLOW_CLICK = false;

function wireRowDrag() {
  $("#folders").addEventListener("pointerdown", e => {
    if (e.button !== 0 || DRAG || CONFIRM || BULK || !DATA) return;
    const tr = e.target.closest("tbody tr[data-uid]");
    if (!tr) return;
    const t = e.target;
    if (t.closest(".note-ed, input[type=checkbox]")) return;
    if (t.matches("input, textarea") && t === document.activeElement) return;
    DRAG = { uid: tr.dataset.uid, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY,
             pointerId: e.pointerId, active: false, over: null };
  });
  document.addEventListener("pointermove", e => {
    if (!DRAG || e.pointerId !== DRAG.pointerId || DRAG.cancelled) return;
    DRAG.x = e.clientX; DRAG.y = e.clientY;
    if (!DRAG.active) {
      if (Math.hypot(e.clientX - DRAG.x0, e.clientY - DRAG.y0) < DRAG_START_PX) return;
      // A dialog that opened after the press (a merge offer) owns the screen.
      if (CONFIRM || BULK) { DRAG = null; return; }
      startDrag();
    }
    e.preventDefault();
    trackDrag();
  });
  document.addEventListener("pointerup", e => {
    if (!DRAG || e.pointerId !== DRAG.pointerId) return;
    const d = DRAG;
    if (d.active || d.cancelled) swallowClick();
    if (d.active && !d.cancelled) {
      // Where the button came up, not the last pointermove: the rail may
      // have auto-scrolled, or the release moved, since then.
      d.x = e.clientX; d.y = e.clientY;
      hitTest();
      const to = d.over;
      endDrag();
      if (to) moveTo(d.uids, to);
    } else endDrag();
  });
  // No pointerup follows these (the release happened in another window, or
  // the browser took the pointer): drop the drag outright, keep nothing held.
  document.addEventListener("pointercancel", () => abandonDrag());
  window.addEventListener("blur", () => abandonDrag());
  // While a press may become a drag, the browser mustn't start selecting text.
  document.addEventListener("selectstart", e => { if (DRAG && (DRAG.active || DRAG.cancelled)) e.preventDefault(); });
  // The click that follows a drag lands on whatever is under the pointer.
  window.addEventListener("click", e => {
    if (SWALLOW_CLICK) { SWALLOW_CLICK = false; e.stopPropagation(); e.preventDefault(); }
  }, true);
}

function swallowClick() {
  SWALLOW_CLICK = true;
  setTimeout(() => { SWALLOW_CLICK = false; });
}

function startDrag() {
  const d = DRAG;
  d.uids = SEL.has(d.uid) ? selectedItems().map(i => i.uid) : [d.uid];
  d.uidSet = new Set(d.uids);
  d.here = hereKey(d.uids);
  d.active = true;
  // A press in an unfocused name field focused it: leave it without a change.
  const a = document.activeElement;
  if (a && a.matches && a.matches("input, textarea") && a.closest("#folders")) a.blur();
  window.getSelection()?.removeAllRanges();
  closePop(); closeMenu(); closeMove(false); hideTip();
  if (RAIL_FOLDED.has("folders")) { d.unfolded = true; RAIL_FOLDED.delete("folders"); }
  document.body.classList.add("dragging-rows");
  document.querySelectorAll("#folders tbody tr[data-uid]").forEach(tr => {
    if (d.uidSet.has(tr.dataset.uid)) tr.classList.add("dragging");
  });
  const ghost = document.createElement("div");
  ghost.id = "drag-ghost";
  ghost.className = "drag-ghost";
  ghost.setAttribute("aria-hidden", "true");
  ghost.innerHTML = `${UI_ICON.move || ""}<span>Move ${plural(d.uids.length, "item")}</span>`;
  document.body.appendChild(ghost);
  d.ghost = ghost;
  renderRail();
  d.raf = requestAnimationFrame(autoScroll);
}

function hitTest() {
  const d = DRAG;
  const el = document.elementFromPoint(d.x, d.y);
  const t = el && el.closest("[data-drop]");
  const key = t ? t.dataset.drop : null;
  d.over = key !== null && key !== d.here ? key : null;
  document.querySelectorAll(".drop-over").forEach(x => { if (x !== t || !d.over) x.classList.remove("drop-over"); });
  if (d.over) t.classList.add("drop-over");
}

function trackDrag() {
  const d = DRAG;
  d.ghost.style.transform = `translate(${d.x + 14}px, ${d.y + 12}px)`;
  hitTest();
}

/* The rail scrolls on its own (sticky, 100vh): with many folders "+ New folder"
   can be below its fold. Hold the pointer near the rail's top or bottom edge
   (above its sticky footer) to scroll it. */
function autoScroll() {
  const d = DRAG;
  if (!d || !d.active) return;
  const rail = $(".rail"), r = rail.getBoundingClientRect();
  const bottom = Math.min(r.bottom, $(".rail-foot").getBoundingClientRect().top);
  const EDGE = 36;
  if (d.x >= r.left && d.x <= r.right) {
    let dy = 0;
    // Faster the deeper in: over the footer it races (200 folders is ~5000px).
    const speed = depth => Math.min(48, Math.ceil(depth / 2));
    if (d.y < r.top + EDGE) dy = -speed(r.top + EDGE - d.y);
    else if (d.y > bottom - EDGE) dy = speed(d.y - (bottom - EDGE));
    if (dy) { const was = rail.scrollTop; rail.scrollTop += dy; if (rail.scrollTop !== was) hitTest(); }
  }
  d.raf = requestAnimationFrame(autoScroll);
}

function endDrag() {
  const d = DRAG;
  DRAG = null;
  if (!d) return;
  if (d.raf) cancelAnimationFrame(d.raf);
  if (!d.active) return;
  d.ghost?.remove();
  document.body.classList.remove("dragging-rows");
  document.querySelectorAll("tr.dragging").forEach(tr => tr.classList.remove("dragging"));
  if (d.unfolded) RAIL_FOLDED.add("folders");
  if (DATA) renderRail();
}

/** Esc mid-drag: put everything back. The press is still held, so DRAG stays
    (cancelled) until it is released and the click that follows can be
    swallowed. */
function cancelDrag() {
  if (!DRAG || DRAG.cancelled) return;   // a second Esc while still held
  if (!DRAG.active) { DRAG = null; return; }
  const id = DRAG.pointerId;
  endDrag();
  DRAG = { pointerId: id, cancelled: true, active: false };
}

/** The window lost focus or the browser cancelled the pointer: no pointerup
    is coming, so nothing may wait for one. A cancelled-but-held DRAG left
    here blocked the next press, text selection, Esc and a click. */
function abandonDrag() {
  if (DRAG) endDrag();
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
    SAVED = savedState();          // this export wrote every change so far
    renderRunbook();
    showStage("done");
    setStatus(`Built ${plural(MANIFEST.length, "folder")}`, "ready");
    window.__cairnExported = true;
  } catch (e) {
    setStatus("Export failed: " + e.message, "err"); console.error(e);
  }
}

function renderRunbook() {
  // Same numbers as RUNBOOK.md: both come from bridge.runbook_summary, so the
  // over-limit check uses max(written, expected) and dropped items are reported.
  // One box per folder (UI-31); the warnings sit above them.
  const S = JSON.parse(py.runPython("bridge.runbook_summary_json()"));
  const kml = S.kml_batches;
  const host = $("#runbook");
  host.innerHTML =
    (kml ? `<div class="note warn"><b>${kml}</b> of these folders contain a KML file, which the phone app can't import. Use the Web Map on a computer.</div>` : "") +
    (S.dropped ? `<div class="note warn"><b>${S.dropped}</b> item${S.dropped === 1 ? "" : "s"} could not be exported because ${S.dropped === 1 ? "it has" : "they have"} no usable coordinates. ${S.written} of ${S.expected} were written.</div>` : "") +
    (S.long_notes ? `<div class="note warn"><b>${S.long_notes}</b> note${S.long_notes === 1 ? " is" : "s are"} longer than ${S.note_limit} bytes (about ${S.note_limit} characters; accented letters, dashes and emoji take 2–4). onX keeps only the first ${S.note_limit} bytes of an imported note; RUNBOOK.md lists ${S.long_notes === 1 ? "it" : "them"}.</div>` : "") +
    (S.over_limit ? `<div class="note warn">onX accounts hold at most ${S.limit.toLocaleString("en-US")} markups; this map has ${S.markups.toLocaleString("en-US")}. Remove or exclude some before importing.</div>` : "");
  // Two folders may share a name ("Camp" twice, from the file), or two names
  // sanitize alike ("A B", "A_B"): only then does a box show its number, and
  // its file chips their NN_ folder, as its download is named.
  const tally = f => MANIFEST.reduce((m, e) => m.set(f(e), (m.get(f(e)) || 0) + 1), new Map());
  const byName = tally(e => e.folder.trim().toLowerCase()), bySafe = tally(e => e.safe.toLowerCase());
  MANIFEST.forEach(e => {
    const nf = e.files.length;
    const twin = byName.get(e.folder.trim().toLowerCase()) > 1;
    const fileTwin = bySafe.get(e.safe.toLowerCase()) > 1;
    const d = document.createElement("section");
    d.className = "rb-step";
    d.innerHTML = `
      <div class="rb-head">
        <h2 class="rb-title">${twin ? `<span class="rb-num">${esc(e.dir.split("_")[0])} ·</span>` : ""}<span class="rb-name" title="${esc(e.folder)}">${esc(e.folder)}</span> <span class="rb-meta">· <span class="rb-count">${plural(e.count, "markup")}</span> · <span class="rb-nfiles">${plural(nf, "file")}</span></span></h2>
        <button type="button" class="btn rb-dl" data-n="${e.n}">Download this folder</button>
      </div>
      <div class="rb-files">${e.files.map(f =>
        `<span class="rb-file ${f.kml ? "kml" : ""}">${esc(fileTwin ? f.path : f.path.split("/").pop())}</span>`).join("")}</div>
      <ol class="rb-do">
        <li>In onX, choose <b>Import</b> and ${nf === 1 ? "add this file" : `add these ${nf} files together`}.</li>
        <li>Tick <b>Import map data to a new folder</b>.</li>
        <li>onX names the folder by date. Rename it to <b>${esc(e.folder)}</b>.</li>
      </ol>`;
    d.querySelector(".rb-dl").onclick = () => downloadFolder(e);
    host.appendChild(d);
  });
}

const plural = (n, word) => `${n.toLocaleString("en-US")} ${word}${n === 1 ? "" : "s"}`;

function downloadBlob(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
}

/* One folder's NN_Name/ directory, the same bytes as inside Download all:
   bridge.export_folder_zip reads the last export, nothing is exported again. */
function downloadFolder(e) {
  try {
    // The number crosses as a global, like every other argument (pyJSON).
    py.globals.set("_cairn_n", e.n);
    const bytes = py.runPython("bridge.export_folder_zip(_cairn_n)").toJs();
    // Named like its directory inside Download all (the manifest's "dir":
    // "02_Trip_1.zip", or "002_..." with 100+ folders): two names can
    // sanitize alike, their numbers can't.
    downloadBlob(new Blob([bytes], { type: "application/zip" }), e.dir + ".zip");
  } catch (err) {
    setStatus("Download failed: " + err.message, "err"); console.error(err);
  }
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
/* One in-page dialog (#confirm) serves Start over, the unsaved-note prompt and
   the area-fill warning.
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

/* onX gives every imported area its default blue fill, whatever the file says
   (docs/ONX_ROUND_TRIP.md #area-fidelity). Areas from an onX export (they carry
   an onX id) with any other fill, "none" included, would change, so say so once
   on load and offer to leave them out of the export. */
const ONX_DEFAULT_FILL = "rgba(74,144,226,0.1)";
function fillLossItems() {
  return allItems().filter(i => i.kind === "shapes" && i.onx_id && i.fill && i.fill !== ONX_DEFAULT_FILL);
}
function warnFillLoss() {
  const hit = fillLossItems();
  const n = hit.length;
  if (!n) return;
  openConfirm({
    title: n === 1 ? "1 area will lose its fill." : `${n} areas will lose their fill.`,
    body: "onX resets area fills to blue on import.",
    buttons: [
      { label: n === 1 ? "Leave this out" : `Leave these ${n} out`, run: () => {
          closeConfirm();
          hit.forEach(it => edit(it, { included: false }, { render: false }));
          refreshAfterEdit();
        } },
      { label: n === 1 ? "Keep it" : "Keep them", initial: true, cancel: true, run: () => closeConfirm() },
    ],
  });
}

function noteIsChanged() {
  if (!NOTE_EDIT || !DATA) return false;
  const it = allItems().find(i => i.uid === NOTE_EDIT.uid);
  return !!it && NOTE_EDIT.draft !== (it.desc || "");
}

function resetAll() {
  closePop(); closeBulk(); resetFolderState();
  DATA = null; EDITS = {}; SEL.clear(); ANCHOR = null; ZIP = null; MANIFEST = null; NOTE_EDIT = null;
  resetFilters();
  renderSourceNotice({});
  $("#file").value = "";
  showStage("drop");
  setStatus("");
  window.__cairnLoaded = false; window.__cairnExported = false;
}

/** What Start over compares with: each item's folder, each folder's name and
    each item's edits, as loaded or as the last export wrote them. The edits
    are kept as JSON (edit() changes EDITS' objects in place). */
function savedState() {
  return { home: groupOfUid(true), names: new Map(DATA.groups.map(g => [g.key, g.name])),
           empty: new Set(DATA.groups.filter(g => !g.items.length).map(g => g.key)),
           edits: new Map(Object.entries(EDITS).map(([uid, e]) => [uid, JSON.stringify(e)])) };
}

/** Unexported changes, since the last export or (none yet) since load
    (UI-32): each item edited or moved since then once (an item moved back is
    not moved), and each folder of then whose name differs now. A merged-away
    or new folder's name isn't counted; its items are, as moved. */
function unexportedChanges() {
  if (!DATA || !SAVED) return 0;
  const uids = new Set(Object.keys(EDITS).filter(u => SAVED.edits.get(u) !== JSON.stringify(EDITS[u])));
  if (noteIsChanged()) uids.add(NOTE_EDIT.uid);
  let renamed = 0, empties = 0;
  DATA.groups.forEach(g => {
    g.items.forEach(i => { if (SAVED.home.get(i.uid) !== g.key) uids.add(i.uid); });
    if (SAVED.names.has(g.key) && SAVED.names.get(g.key) !== g.name) renamed++;
    // An empty folder made since then: no item says so (round 4).
    if (!SAVED.names.has(g.key) && !g.items.length) empties++;
  });
  // An empty folder of then that was removed.
  SAVED.empty.forEach(k => { if (!groupByKey(k)) empties++; });
  return uids.size + renamed + empties;
}

function requestStartOver() {
  const ret = document.activeElement;
  flushDeferred();                 // a name just left: its rename, or its merge offer, first
  if (CONFIRM) return;
  const n = unexportedChanges();
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
  // A folder name left by clicking Export: its rename happened, its render
  // (and a taken name's merge offer) is waiting. Show it here, on the edit
  // screen, and don't export the old name.
  if (RENAME) finishRename(RENAME.key, true);
  flushDeferred();
  if (CONFIRM) return;
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
    closeMove(false); closePop();   // never a menu under the Move to… list
    const open = $("#more-menu").classList.toggle("hidden") === false;
    $("#more-btn").setAttribute("aria-expanded", String(open));
    if (open) $("#more-menu button").focus();
  };
  $("#more-menu").onclick = e => e.stopPropagation();
  const menuAct = (id, fn) => $(id).onclick = () => { closeMenu(); fn(); };
  menuAct("#bulk-move", openMoveTo);
  wireRowDrag();
  wirePointerHeld();
  wireTip();
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
  $("#back").onclick = () => { showStage("edit"); setStatus(""); };
  document.querySelectorAll(".newmap").forEach(b => b.onclick = requestStartOver);
  $("#confirm").addEventListener("click", e => { if (e.target === $("#confirm")) cancelConfirm(); });
  $("#download").onclick = () => downloadBlob(ZIP, "onx_ready.zip");
  // Outside click closes the menu and the popover (Cancel semantics).
  document.addEventListener("click", e => {
    closeMenu();
    if (POP && !$("#mark-pop").contains(e.target)) closePop();
    if (MOVE && !$("#move-pop").contains(e.target)) closeMove(false);
  });
  window.addEventListener("resize", () => { const a = popAnchor(); if (a) placePop(a); });
  document.addEventListener("keydown", e => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || ""));
    if (e.key === "Tab") {
      if (CONFIRM) trapTab(e, $("#confirm .modal-card"));
      else if (!$("#help").classList.contains("hidden")) trapTab(e, $("#help .modal-card"));
      else if (BULK) trapTab(e, $("#mark-dialog"));
      return;
    }
    if (e.key === "Escape") {
      // Priority: a drag in progress, then what's in front, then an open note,
      // then let a focused field revert its own edit, else clear the selection.
      if (DRAG) {
        const held = DRAG.active || DRAG.cancelled;   // Esc again while still held: still the drag's
        cancelDrag();
        if (held) { e.preventDefault(); e.stopPropagation(); return; }
      }
      if (CONFIRM) { e.preventDefault(); cancelConfirm(); return; }
      if (!$("#help").classList.contains("hidden")) { closeHelp(); return; }
      if (MOVE) { closeMove(true); return; }
      if (BULK) { closeBulk(); return; }
      if (POP) { closePop(); return; }
      if (!$("#more-menu").classList.contains("hidden")) { closeMenu(); $("#more-btn").focus(); return; }
      if (typing) return;                       // wireTextField handles the revert
      if (NOTE_EDIT) { closeNote(null, false); return; }
      if (SEL.size) { SEL.clear(); ANCHOR = null; renderFolders(); }
      return;
    }
    // Not behind anything in front: a dialog, Move to… or Help.
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a" && !typing && DATA &&
        document.body.dataset.stage === "edit" && !BULK && !POP && !MOVE && !CONFIRM && !TIP.over &&
        $("#help").classList.contains("hidden")) {
      e.preventDefault();
      setSelectAll(!(SEL.size && SEL.size === selectableItems().length));
    }
  });
  boot();
});
