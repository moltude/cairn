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
const NO_MATCH = "\u0000none", NO_ICONS = "\u0000none";   // _key of "Nothing matches" / "No waypoints"

const $ = s => document.querySelector(s);
/* A "ready" line ("Moved 2 items to …") is a receipt, not state: it clears itself
   after STATUS_LINGER_MS if nothing else has replaced it. Errors and in-progress
   lines stay until something supersedes them. */
let STATUS_LINGER_MS = 8000;
let STATUS_TIMER = null;
const setStatus = (t, cls = "") => {
  const e = $("#status"); e.textContent = t; e.className = "status " + cls;
  clearTimeout(STATUS_TIMER); STATUS_TIMER = null;
  if (t && cls === "ready") STATUS_TIMER = setTimeout(() => {
    if (e.textContent === t) { e.textContent = ""; e.className = "status "; }
  }, STATUS_LINGER_MS);
};
/** An error that a later success has made stale ("A folder needs a name."). */
const clearError = () => { if ($("#status").classList.contains("err")) setStatus(""); };

/* ---------- keyed, in-place rendering ----------
   The rail and the list are not rebuilt. Each render builds what it wants with
   the builders below, off screen, then patches the live nodes to match: a
   node that is still wanted is KEPT and only its attributes, text, form state
   and on* handlers change (morph); nodes are added, moved and removed so the
   order matches (place). Rows are keyed by their item object, folder sections
   by their group object -- both stable: edit() changes items in place and
   applyLayout() reuses groups and items, a new file brings new ones -- and
   rail entries by their facet key. So an edit, move, rename, sort or filter
   leaves the control under the pointer, and the one with focus, where it is.
   A row whose markup is unchanged since the last render isn't touched at all.
   Two rules for every builder, since its output may end up only as a pattern
   for the live twin:
   - an on* handler must not close over the element it is built on (it is
     copied onto the live twin): use e.currentTarget / e.target;
   - an addEventListener listener stays with the node it was added to (the
     fresh twin's is dropped when the live node is kept), so it may close only
     over what is the same for that node's whole life: its item, its folder key. */
const HANDLERS = ["onclick", "onchange", "oninput", "onkeydown"];
/* Attributes a builder never writes, set at run time: the name field's value
   at focus (wireTextField) and the tip's link (showTip). A morph leaves them. */
const RUNTIME_ATTRS = new Set(["data-orig", "aria-describedby"]);
const isField = n => n.nodeName === "INPUT" || n.nodeName === "TEXTAREA";
/** Whether live node a can be patched into fresh node b (else b replaces it). */
const sameNode = (a, b) => a.nodeType === b.nodeType && a.nodeName === b.nodeName &&
  a._key === b._key && (!isField(a) || a.className === b.className);
/** Make live node a look like fresh node b, keeping a and every child of a
    that has a twin in b at the same place. */
function morph(a, b) {
  if (a.nodeType !== 1) { if (a.nodeValue !== b.nodeValue) a.nodeValue = b.nodeValue; return; }
  for (const { name } of [...a.attributes])
    if (!b.hasAttribute(name) && !RUNTIME_ATTRS.has(name)) a.removeAttribute(name);
  for (const { name, value, namespaceURI } of b.attributes)
    if (a.getAttribute(name) !== value) namespaceURI ? a.setAttributeNS(namespaceURI, name, value) : a.setAttribute(name, value);
  for (const h of HANDLERS) if (a[h] !== b[h]) a[h] = b[h];
  if (isField(a) && a.value !== b.value) {
    a.value = b.value;
    // Changed under the focus: its value-at-focus follows (wireTextField's Esc and change).
    if (a === document.activeElement && "orig" in a.dataset) a.dataset.orig = b.value;
  }
  if (a.nodeName === "INPUT") {
    if (a.checked !== b.checked) a.checked = b.checked;
    if (a.indeterminate !== b.indeterminate) a.indeterminate = b.indeterminate;
  }
  if (b._own) return;              // its children are placed by their own pass (a tbody's rows)
  const bs = [...b.childNodes];
  bs.forEach((y, i) => {
    const x = a.childNodes[i];
    if (!x) a.appendChild(y);
    else if (sameNode(x, y)) morph(x, y);
    else a.replaceChild(y, x);
  });
  while (a.childNodes.length > bs.length) a.lastChild.remove();
}
/** The live node `old`, patched to look like `fresh`; or `fresh` when there is
    none or it can't be. */
function adopt(old, fresh) {
  if (old && sameNode(old, fresh)) { morph(old, fresh); return old; }
  return fresh;
}
/** Make host's children exactly `want`, in order, moving only the nodes that
    are out of place (each move of a node takes focus out of it). */
function place(host, want) {
  const keep = new Set(want);
  for (const n of [...host.childNodes]) if (!keep.has(n)) n.remove();
  want.forEach((n, i) => { const at = host.childNodes[i]; if (at !== n) host.insertBefore(n, at || null); });
}
/** Live entries of host by their _key. */
const byKey = host => new Map([...host.children].filter(c => c._key !== undefined).map(c => [c._key, c]));

/* Focus across a patch. The node with focus is normally kept and keeps it.
   Two cases lose it, and are put back here: a kept node that had to move (a
   rename that reorders a sorted folder, a folder rename that reorders the
   folders) -- focus it again; and a control replaced by design by another
   with the same data-fk key (row uid / folder key / facet key plus which
   control): a row's note button and its open editor share one, so
   Save/Cancel land back on the note button; a folder's name button and its
   name field share one. A key that no longer exists is a silent no-op.
   PATCHING is set while the DOM changes: the focused folder-name field,
   moved or replaced by a patch, fires a blur that isn't the user leaving it
   (wireFolderName). */
const focusedKey = () => document.activeElement?.dataset?.fk || null;
const fkEl = k => [...document.querySelectorAll("[data-fk]")].find(e => e.dataset.fk === k) || null;
const focusFk = k => fkEl(k)?.focus({ preventScroll: true });
function refocus(k) {
  if (!k || focusedKey() === k) return;
  focusFk(k);
}
let PATCHING = false;
function patch(fn) {
  const a = document.activeElement, k = focusedKey();
  PATCHING = true;
  try { fn(); } finally { PATCHING = false; }
  if (document.activeElement === a) return;
  if (a && a !== document.body && a.isConnected) a.focus({ preventScroll: true });
  else refocus(k);
}

/* A render that follows leaving a field (Tab, or a click elsewhere) runs on
   the next task, once focus has landed. With a mouse button down it waits for
   the release. A patch keeps the button being pressed, but not where it is: a
   folder rename re-sorts the folders, a row rename re-sorts a sorted folder,
   and the button moves out from under the pointer between pointerdown and
   pointerup, so the click is lost; and a taken name's merge offer, opened
   mid-press, would take the click itself. Queued from pointerup, it runs
   after that click. */
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
    NOTE_LIMIT = py.runPython("bridge.ONX_IMPORT_NOTE_LIMIT");
    NAME_LIMIT = py.runPython("bridge.ONX_IMPORT_NAME_LIMIT");
    FOLDER_NAME_LIMIT = py.runPython("bridge.ONX_FOLDER_NAME_LIMIT");
    ONX_DEFAULT_FILL = py.runPython("bridge.ColorMapper.DEFAULT_AREA_FILL");
    window.__cairnReady = true;
    // The same signal as a DOM attribute, for tests that run under the
    // enforced CSP, where Playwright can't evaluate window.__cairnReady.
    document.body.dataset.engine = "ready";
    // A file chosen or dropped while the engine was still booting waits here.
    if (PENDING_FILES) { const f = PENDING_FILES; PENDING_FILES = null; handleFiles(f); }
  } catch (e) {
    PENDING_FILES = null; showDropWait(false);
    setStatus("Failed: " + humanError(e), "err");
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
  syncUnloadGuard();
}

/* ---------- browser Back and Forward (UI-37) ----------
   Each stage is a history entry: drop (replaced in at boot), edit (pushed on
   load), done (pushed on export), so the entries are always drop, edit, done
   in that order and a stage's depth is its index. The app's own buttons stay
   synchronous: Back (done -> edit) and Start over move the screen at once and
   step history to match, ignoring the popstate that causes (HIST_SKIP).
   popstate (the browser's Back / Forward):
   - done -> edit: nothing lost, no prompt;
   - edit -> drop: with unexported changes, "Leave this map?" [Stay] [Leave];
     Stay steps forward again, Leave clears the map like Start over; with
     none, straight to drop;
   - Forward only to a stage that is still valid (edit: a loaded map; done: an
     export that is current, no change since); otherwise history steps back to
     where the screen is and nothing changes.
   A popstate with no state of ours (a hash link, "#help") is left alone. */
const STAGE_DEPTH = { drop: 0, edit: 1, done: 2 };
let HIST_SKIP = 0;                     // popstates our own history.go() will fire
function pushStage(name) {
  showStage(name);
  history.pushState({ cairn: name }, "");
}
/** Step history by n entries without reacting to the popstate it fires. */
function stepHistory(n) {
  if (!n) return;
  HIST_SKIP++;
  history.go(n);
}
const stageValid = name => name === "drop" || (name === "edit" && !!DATA) ||
  (name === "done" && !!DATA && !!ZIP && unexportedChanges() === 0);
function onPopState(e) {
  if (HIST_SKIP) { HIST_SKIP--; return; }
  const want = e.state && e.state.cairn;
  const now = document.body.dataset.stage;
  if (!want || !(want in STAGE_DEPTH) || want === now) return;
  if (!stageValid(want)) { stepHistory(STAGE_DEPTH[now] - STAGE_DEPTH[want]); return; }
  if (want === "drop") return leaveMap(now);
  // done -> edit (Back), or edit -> done (Forward to a current export).
  closePop(); closeBulk(); closeMove(false); hideTip();
  if (CONFIRM) closeConfirm(false);
  showStage(want);
  setStatus("");
}
/** Back to the drop screen from `from` (history is already there). */
function leaveMap(from) {
  flushDeferred();
  closeBulk();                     // an open dialog never outlives its screen (nothing saved)
  if (CONFIRM) closeConfirm(false);
  const n = unexportedChanges();
  if (!n) { resetAll({ history: false }); return; }
  openConfirm({
    title: "Leave this map?",
    body: "Changes will be lost.",
    buttons: [
      { label: "Stay", initial: true, cancel: true, run: () => {
          closeConfirm(); stepHistory(STAGE_DEPTH[from]); } },
      { label: "Leave", cls: "danger", run: () => { closeConfirm(false); resetAll({ history: false }); } },
    ],
  });
}
/* The browser's own "Leave site?" prompt on reload, tab close or leaving the
   site, only while there are unexported changes: the listener is added then
   and removed otherwise. */
const onBeforeUnload = e => { e.preventDefault(); e.returnValue = ""; };
let UNLOAD_ON = false;
function syncUnloadGuard() {
  const on = typeof unexportedChanges === "function" && unexportedChanges() > 0;
  if (on === UNLOAD_ON) return;
  UNLOAD_ON = on;
  (on ? addEventListener : removeEventListener)("beforeunload", onBeforeUnload);
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
    SORT.clear(); hideTip();
    resetFolderState();
    $("#runbook").replaceChildren();
    SAVED = savedState();
    $("#map-title").textContent = mapTitle(DATA);
    $("#map-label").textContent = mapLabel(DATA);
    renderEdit();
    pushStage("edit");
    setStatus("");   // the screen says it; the status line is for messages (moves, errors)
    window.__cairnLoaded = true;
    warnFillLoss();
  } catch (e) {
    // Pyodide surfaces the whole Python traceback. The last line is the actual
    // message and the engine's messages are already user-friendly ("No features
    // found... make sure this is a CalTopo export"); the stack above it is noise
    // to a hiker. Keep the full thing in the console for us.
    { const why = humanError(e);
      setStatus(why.startsWith("Failed:") ? why
        : (files.length === 1 ? "Couldn't read that file — " : "Couldn't read those files — ") + why, "err"); }
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
  const shown = g.items.filter(i =>
    (!q || i.name.toLowerCase().includes(q) || (i.desc || "").toLowerCase().includes(q)) &&
    (!FILTERS.kind || i.kind === FILTERS.kind) &&
    (!keys.size || (i.kind === "waypoints" && keys.has(iconKey(i)))));
  const dir = SORT.get(g.key);
  return dir ? sortByName(shown, dir) : shown;
}

/* Name sort, per folder (owner feedback 2026-10-24): each folder's Name header
   cycles ITS rows through the map's order, A to Z, Z to A; sorting one folder
   leaves the others as they are. The state is keyed by folder key, so a
   rename keeps it, a merge's target keeps its own, items moved in show in the
   target's state, and a removed folder's state goes with it; a new folder
   starts in the map's order. View only: DATA.groups (and so the export) keeps
   the map's order. Everything that reads visibleItems -- the rows,
   shift-click ranges, select-all -- follows the sorted order. Natural and
   case-insensitive, so "01 - …", "02 - …", "10 - …" come out in order. */
const SORT = new Map();                // folder key -> "asc" | "desc" (absent: the map's order)
const NAME_ORDER = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
function sortByName(items, how) {
  const dir = how === "desc" ? -1 : 1;
  // Array.prototype.sort is stable: equal names keep the map's order.
  return [...items].sort((a, b) => dir * NAME_ORDER.compare(a.name.trim(), b.name.trim()));
}
/** Up and down arrows; the one in use is dark (.on), both are faint in map order. */
function sortIcon(s) {
  return `<svg class="sort-icon" width="8" height="12" viewBox="0 0 8 12" aria-hidden="true">` +
    `<path d="M4 0.5 7.5 4.5H0.5Z"${s === "asc" ? ` class="on"` : ""}/>` +
    `<path d="M4 11.5 0.5 7.5H7.5Z"${s === "desc" ? ` class="on"` : ""}/></svg>`;
}
const SORT_NEXT = { null: "asc", asc: "desc", desc: null };
const ARIA_SORT = { null: "none", asc: "ascending", desc: "descending" };
function toggleSort(key) {
  const next = SORT_NEXT[SORT.get(key) || null];
  next ? SORT.set(key, next) : SORT.delete(key);
  renderFolders();
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

function renderRail() { patch(patchRail); }
function patchRail() {
  // Type: "All", then each kind the map has (Areas, Lines, Waypoints: alphabetical,
  // fixed in index.html) with its count. A kind with none is hidden, unless it is
  // the filter in use (so it can be seen and cleared).
  const byKind = { "": 0, waypoints: 0, tracks: 0, shapes: 0 };
  allItems().forEach(i => { byKind[""]++; byKind[i.kind] = (byKind[i.kind] || 0) + 1; });
  document.querySelectorAll("#type-filter [data-kind]").forEach(b => {
    b.querySelector(".facet-count").textContent = byKind[b.dataset.kind] || 0;
    const k = b.dataset.kind;
    if (k) b.classList.toggle("hidden", !byKind[k] && FILTERS.kind !== k);
  });
  syncTypeFacet();

  // Folders: "All" first, then each folder with its item count.
  const fl = $("#folder-facets"), liveFolders = byKey(fl), wantFolders = [];
  const put = el => wantFolders.push(adopt(liveFolders.get(el._key), el));
  const facetBtn = (label, count, key, italic) => {
    const fkey = "folder|" + (key === null ? "\u0000all" : key);
    if (key !== null && naming(key, "rail")) {
      // A new folder's name, edited in place (NameNewFolder mockup).
      const d = document.createElement("div");
      d.className = "facet-btn naming";
      d.innerHTML = `${folderNameInput(fkey)}<span class="facet-count">${count}</span>`;
      wireFolderName(d.querySelector("input"));
      d._key = fkey; put(d);
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
      // removed: an × beside it, shown on hover and focus. A
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
      row._key = fkey; put(row);
      return;
    }
    b._key = fkey; put(b);
  };
  facetBtn("All", "", null, false);
  DATA.groups.forEach(g => facetBtn(g.name, g.items.length, g.key, isUnorganized(g)));
  // + New folder: a drop target for dragged rows, and a button:
  // clicked, it moves the ticked rows into a new folder, or with nothing
  // ticked makes an empty one, ready to drop rows on.
  const nf = document.createElement("button");
  nf.type = "button"; nf.className = "new-folder"; nf.textContent = "+ New folder";
  nf.dataset.fk = "newfolder";
  nf.dataset.drop = NEW_TARGET;   // set as a property: an HTML parser turns the NUL into U+FFFD
  nf.onclick = newFolderClicked;
  nf._key = "newfolder"; put(nf);
  place(fl, wantFolders);

  // Icons present in the map: "Default pin" first (owner, 2026-10-24), then the
  // icons alphabetically (natural, any case).
  const counts = new Map();
  allItems().filter(i => i.kind === "waypoints").forEach(i => {
    const k = iconKey(i); counts.set(k, (counts.get(k) || 0) + 1);
  });
  // Keep an icon you're filtering on visible even after its last item changed.
  const keys = [...new Set([...counts.keys(), ...FILTERS.icons])].filter(k => k !== DEFAULT_PIN)
    .sort((a, b) => NAME_ORDER.compare(a, b));
  if (counts.has(DEFAULT_PIN) || FILTERS.attention) keys.unshift(DEFAULT_PIN);
  const il = $("#icon-facets"), liveIcons = byKey(il);
  const wantIcons = keys.map(k => {
    const def = k === DEFAULT_PIN;
    const lab = document.createElement("label");
    lab.className = "icon-facet" + (def ? " default-pin" : "");
    lab.title = def ? "Waypoints that fell back to onX's default pin" : "";
    lab.innerHTML = `<input type="checkbox"${def ? ' id="only-attention"' : ""} data-icon="${esc(k)}" data-fk="icon|${esc(k)}">` +
      glyphSVG(def ? "Location" : k, 15) + `<span class="facet-name">${def ? "Default pin" : esc(k)}</span><span class="facet-count">${counts.get(k) || 0}</span>`;
    const box = lab.querySelector("input");
    box.checked = def ? FILTERS.attention : FILTERS.icons.has(k);
    box.onchange = e => {
      const on = e.target.checked;
      if (def) FILTERS.attention = on;
      else on ? FILTERS.icons.add(k) : FILTERS.icons.delete(k);
      renderFolders();
    };
    lab._key = k;
    return adopt(liveIcons.get(k), lab);
  });
  if (!keys.length) {
    const none = document.createElement("span");
    none.className = "facet-empty"; none.textContent = "No waypoints"; none._key = NO_ICONS;
    wantIcons.push(adopt(liveIcons.get(NO_ICONS), none));
  }
  place(il, wantIcons);
  renderRailHeads();
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
  hideTip();                       // what it says may have changed with the row
  const shownUids = new Set(shownItems().map(i => i.uid));
  const selectableUids = new Set(selectableItems().map(i => i.uid));
  for (const uid of SEL) if (!selectableUids.has(uid)) SEL.delete(uid);
  if (NOTE_EDIT && !shownUids.has(NOTE_EDIT.uid)) NOTE_EDIT = null;
  renderChips();
  patch(patchFolders);
  updateSel();
  syncUnloadGuard();               // every edit, move and rename redraws the list
}

function patchFolders() {
  const host = $("#folders"), live = byKey(host);
  // Rows by item, from every section: a row moved to another folder is moved, not rebuilt.
  const rows = new Map([...host.querySelectorAll("tr[data-uid]")].map(tr => [tr._key, tr]));
  const want = [], fill = [];
  DATA.groups.forEach(g => {
    const items = visibleItems(g);
    if (!items.length) {
      if (!g.items.length && showsEmptyFolders(g)) want.push(adopt(live.get(g), emptyFolderSection(g)));
      return;
    }
    const el = adopt(live.get(g), folderSection(g, items));
    want.push(el);
    fill.push([el.querySelector("tbody"), items]);
  });
  if (!want.length) {
    const none = document.createElement("div");
    none.className = "note"; none.textContent = "Nothing matches these filters."; none._key = NO_MATCH;
    want.push(adopt(live.get(NO_MATCH), none));
  }
  place(host, want);
  fill.forEach(([tb, items]) => place(tb, items.map(it => row(it, rows.get(it)))));
}

/** A folder's section: its header and an empty tbody (patchFolders places
    the rows). */
function folderSection(g, items) {
  const el = document.createElement("section");
  el.className = "folder";
  el.setAttribute("aria-label", g.name);
  el._key = g;
  const collapsed = COLLAPSED.has(g.key);
  const sort = SORT.get(g.key) || null;
  const sub = isUnorganized(g) ? "Not in any folder"
    : items.length === g.items.length ? `${g.items.length} item${g.items.length === 1 ? "" : "s"}`
    : `${items.length} of ${g.items.length} shown`;
  const fmark = folderCaution(g);
  el.innerHTML = `
    <div class="folder-head">
      ${folderTitleHTML(g)}${fmark ? cautionMark(`fcaution|${esc(g.key)}`, fmark, " folder-caution") : ""}
      <span class="folder-sub">${esc(sub)}</span>
      <button type="button" class="collapse" data-fk="collapse|${esc(g.key)}" aria-expanded="${!collapsed}" aria-label="${collapsed ? "Expand" : "Collapse"} ${esc(g.name)}">${UI_ICON.chevron}</button>
    </div>
    <div class="table-wrap${collapsed ? " hidden" : ""}"><table>
      <colgroup><col class="c-sel"><col class="c-name"><col class="c-note"><col class="c-icon"></colgroup>
      <thead><tr>
        <th class="selcol"><input type="checkbox" class="folder-all" data-fk="all|${esc(g.key)}" aria-label="Select all shown in ${esc(g.name)}"></th>
        <th class="name-th" aria-sort="${ARIA_SORT[sort]}"><button type="button" class="sort-btn" data-fk="sort|${esc(g.key)}" data-sort="${sort || "none"}" aria-label="Sort ${esc(g.name)} by name">Name${sortIcon(sort)}</button></th><th class="note-th"><span>Note</span></th><th>Icon</th>
      </tr></thead><tbody></tbody></table></div>`;
  el.querySelector("tbody")._own = true;
  const fbox = el.querySelector(".folder-all");
  const nsel = items.filter(i => SEL.has(i.uid)).length;
  fbox.checked = nsel === items.length;
  fbox.indeterminate = nsel > 0 && nsel < items.length;
  fbox.onchange = e => {
    items.forEach(i => e.target.checked ? SEL.add(i.uid) : SEL.delete(i.uid));
    renderFolders();
  };
  wireFolderTitle(el, g);
  el.querySelector(".sort-btn").onclick = () => toggleSort(g.key);
  el.querySelector(".collapse").onclick = () => {
    COLLAPSED.has(g.key) ? COLLAPSED.delete(g.key) : COLLAPSED.add(g.key);
    renderFolders();
  };
  return el;
}

/** An empty folder shows as a header only (so it can be renamed there), when
    no search, type or icon filter would hide it anyway. */
const showsEmptyFolders = g => !FILTERS.q && !FILTERS.kind && !FILTERS.icons.size && !FILTERS.attention &&
  (FILTERS.folder === null || FILTERS.folder === g.key);
function emptyFolderSection(g) {
  const el = document.createElement("section");
  el.className = "folder empty-folder";
  el.setAttribute("aria-label", g.name);
  el._key = g;
  el.innerHTML = `<div class="folder-head">
      ${folderTitleHTML(g)}
      <span class="folder-sub">Empty</span></div>`;
  wireFolderTitle(el, g);
  return el;
}

/** Whether folder `key`'s name is open for editing in its table header
    ("head") or in the rail ("rail"). */
const naming = (key, where) => !!RENAME && RENAME.key === key && RENAME.where === where;
const folderNameInput = fk =>
  `<input class="folder-name-in" data-fk="${esc(fk)}" aria-label="Folder name" maxlength="${FOLDER_NAME_MAX}" autocomplete="off">`;
/** A folder header's title: its name as a button (click to rename), or the open name field. */
function folderTitleHTML(g) {
  const fk = "fname|" + g.key;
  return `<h2>${naming(g.key, "head") ? folderNameInput(fk)
    : `<button type="button" class="folder-name" data-fk="${esc(fk)}" title="${esc(g.name)}">${esc(g.name)}</button>`}</h2>`;
}
function wireFolderTitle(el, g) {
  const inp = el.querySelector(".folder-head .folder-name-in");
  if (inp) wireFolderName(inp);
  else el.querySelector(".folder-name").onclick = () => startRename(g.key, "head");
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
/** A note's preview in the list: its first line that isn't blank.
    The rest shows on hover (the tip below). "Use note as name" still joins
    every line (CairnRename.cleanName). */
const firstLine = s => String(s || "").split("\n").map(l => l.trim()).find(Boolean) || "";

/* ---------- the hover tip ----------
   One styled popup (#tip) for a row name or note preview that hides text,
   and for a row's caution mark: shown after a short hover or on keyboard
   focus, with line breaks kept, inside the window, selectable and copyable
   (the pointer may move onto it), and gone on Esc. Not the native `title`:
   it drops line breaks on some platforms and can't be styled. */
const TIP_SRC = ".name-in, .note-btn, .caution";
const TIP_HOVER_MS = 450, TIP_FOCUS_MS = 150;   // how long a hover / keyboard focus waits for the tip
const TIP_GRACE_MS = 200;      // leaving the control or the tip: time to cross from one to the other
const PRESS_FOCUS_MS = 300;    // focus this soon after a press came from the pointer, not the keyboard
const TIP = { src: null, showT: null, hideT: null, over: false };
let LAST_POINTER = 0;   // when the last press happened: focus right after it isn't keyboard focus
const cut = el => !!el && el.scrollWidth > el.clientWidth + 1;
function tipText(src, viaKey = false) {
  // Each mark its own, a row's or a folder header's (which has no row).
  if (src.classList.contains("caution")) return src.getAttribute("aria-label");
  const tr = src.closest("tr[data-uid]");
  const it = tr && allItems().find(i => i.uid === tr.dataset.uid);
  if (!it) return null;
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
  clearTimeout(TIP.showT);
  // Back on the control whose tip is up: keep it. Any other control leaves a
  // pending hide alone (crossing another row's name on the way out must not
  // keep this tip up).
  if (TIP.src === src && tipShown()) { clearTimeout(TIP.hideT); return; }
  TIP.showT = setTimeout(() => showTip(src, viaKey), ms);
}
const tipShown = () => !$("#tip").classList.contains("hidden");
/** The left edge nearest x that keeps a w-wide popup 8px inside the window. */
const leftInWindow = (x, w) => Math.max(8, Math.min(x, document.documentElement.clientWidth - w - 8));
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
  // Longer than fits: end on a whole line (never half of one) and say there is more.
  tip.style.maxHeight = "";
  const scrolls = tip.scrollHeight > tip.clientHeight + 1;
  tip.classList.toggle("scrolls", scrolls);
  if (scrolls) {
    const lh = parseFloat(getComputedStyle(tip).lineHeight), pad = tip.offsetHeight - tip.clientHeight + 16;
    const room = parseFloat(getComputedStyle(tip).maxHeight) - pad;   // styles.css .tip max-height
    tip.style.maxHeight = `${Math.max(1, Math.floor(room / lh)) * lh + pad}px`;
  }
  TIP.src = src;
  src.setAttribute("aria-describedby", "tip");
  // Below the control, else above it; never over it (that would block the
  // click it is waiting for), and always inside the window.
  const r = src.getBoundingClientRect();
  const vh = window.innerHeight, h = tip.offsetHeight;
  const left = leftInWindow(r.left, tip.offsetWidth);
  let top = r.bottom + 6;
  if (top + h > vh - 8) top = r.top - h - 6 >= 8 ? r.top - h - 6 : Math.max(8, vh - h - 8);
  tip.style.left = `${left}px`; tip.style.top = `${top}px`;
}
/** keepPending: a delayed hide takes down the tip that is up, but not a
    show that is waiting for another control the pointer has moved onto. */
function hideTip(keepPending = false) {
  if (!keepPending) clearTimeout(TIP.showT);
  clearTimeout(TIP.hideT);
  TIP.over = false;
  if (TIP.src) { TIP.src.removeAttribute("aria-describedby"); TIP.src = null; }
  const tip = $("#tip");
  if (tip && !tip.classList.contains("hidden")) { tip.classList.add("hidden"); tip.textContent = ""; }
}
/** Leaving the control or the tip: a short grace, so the pointer can cross
    from one to the other (to select the text). */
function laterHideTip(cancelShow = true) {
  if (cancelShow) clearTimeout(TIP.showT);
  clearTimeout(TIP.hideT);
  TIP.hideT = setTimeout(() => { if (!TIP.over) hideTip(true); }, TIP_GRACE_MS);
}
function wireTip() {
  const host = $("#folders"), tip = $("#tip");
  host.addEventListener("pointerover", e => {
    if (e.pointerType === "touch" || DRAG) return;
    const src = e.target.closest(TIP_SRC);
    if (src) scheduleTip(src, TIP_HOVER_MS);
  });
  host.addEventListener("pointerout", e => {
    const src = e.target.closest(TIP_SRC);
    if (!src || src.contains(e.relatedTarget)) return;
    if (TIP.src === src || !tipShown()) laterHideTip();
  });
  host.addEventListener("focusin", e => {
    const src = e.target.closest(TIP_SRC);
    if (src && Date.now() - LAST_POINTER > PRESS_FOCUS_MS) scheduleTip(src, TIP_FOCUS_MS, true);   // keyboard focus
  });
  host.addEventListener("focusout", e => { if (TIP.src && TIP.src.contains(e.target)) hideTip(); });
  // Typing in a name it describes: the field shows the text now.
  host.addEventListener("input", e => { if (TIP.src && TIP.src === e.target) hideTip(); });
  tip.addEventListener("pointerenter", () => { TIP.over = true; clearTimeout(TIP.hideT); });
  tip.addEventListener("pointerleave", () => { TIP.over = false; laterHideTip(false); });
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
/* ---------- what won't carry over ----------
   A caution mark beside a row's note, before export, for what onX will
   change on import: a note over its byte limit (the export's long_notes rule)
   and an onX area whose fill onX will reset (UI-30's rule, except a
   transparent / none fill). One plain line each; the tip shows them. An
   excluded row isn't exported, so it has none. Rows re-render after every
   edit, so the mark follows the note. */
let NOTE_LIMIT = null;                 // bridge.ONX_IMPORT_NOTE_LIMIT (512), read at boot
// onX's limits on names (L1, measured live 2026-10-25), read at boot like
// NOTE_LIMIT: the first 255 UTF-8 bytes of an imported name are kept, and its
// folder rename dialog stops at 50 characters (UTF-16 units, as maxlength
// counts). The bulk dialog's name flag reads NAME_LIMIT too.
let NAME_LIMIT = null;                 // bridge.ONX_IMPORT_NAME_LIMIT (255)
let FOLDER_NAME_LIMIT = null;          // bridge.ONX_FOLDER_NAME_LIMIT (50)
/** [size, characters past the limit] of text measured by size(): the
    characters (code points) after the longest start that fits in limit. */
function overflow(text, limit, size) {
  const total = size(text);
  if (total <= limit) return [total, 0];
  let upTo = 0, kept = 0, chars = 0;
  for (const ch of text) {
    upTo += size(ch); chars++;
    if (upTo <= limit) kept++;
  }
  return [total, chars - kept];
}
/** [bytes, characters past the limit] of a note, by UTF-8 bytes, measured
    on the note as the export writes it to the GPX <desc> (line endings made
    "\n", outer whitespace trimmed: writers.clean_notes for plain notes), the
    same measure instructions.txt uses, so the screen and the file agree.
    Both helpers are web/rename.js's, so the row's mark and the Change note…
    dialog's flag (UI-39) measure alike. */
const writtenNote = d => CairnRename.writtenNote(d);
const noteOverflow = desc => overflow(writtenNote(desc), NOTE_LIMIT, CairnRename.noteBytes);
/** The long-note sentence (UI-34), or null for a note onX keeps whole. */
function longNoteSentence(desc) {
  const [bytes, cutN] = noteOverflow(desc);
  return bytes > NOTE_LIMIT
    ? `onX imports only the first ${NOTE_LIMIT} bytes of a note. About ${plural(Math.max(cutN, 1), "character")} will be cut.`
    : null;
}
/** A name as the export writes it to <name> and onX reads it back: the
    characters XML forbids dropped (the writers' rule), a line break read as
    "\n". Measured in UTF-8 bytes, as instructions.txt measures it. */
const writtenName = n => CairnRename.xmlSafe(n).replace(/\r\n?/g, "\n");
/** The long-name sentence (L1), or null for a name onX keeps whole. */
function longNameSentence(name) {
  const [bytes, cutN] = overflow(writtenName(name), NAME_LIMIT, CairnRename.noteBytes);
  return bytes > NAME_LIMIT
    ? `onX imports only the first ${NAME_LIMIT} bytes of a name. About ${plural(Math.max(cutN, 1), "character")} will be cut.`
    : null;
}
/** The long folder name sentence (L1), or null for one onX's rename dialog
    takes whole. Characters as maxlength counts them: an emoji is two. */
function longFolderSentence(name) {
  const [units, cutN] = overflow(String(name ?? ""), FOLDER_NAME_LIMIT, s => s.length);
  return units > FOLDER_NAME_LIMIT
    ? `onX keeps only the first ${FOLDER_NAME_LIMIT} characters of a folder name. About ${plural(Math.max(cutN, 1), "character")} will be cut.`
    : null;
}
/** Blank as the export would write it (N1): nothing left once the characters
    XML forbids are dropped and the ends trimmed (cleanNote trims U+0085 too, as
    the bridge's Python strip() does), so this and bridge._blank_name agree. */
const nameIsBlank = name => CairnRename.cleanNote(name ?? "") === "";
/** An item Export would write with a blank name: it needs one first (N1). */
const needsName = it => it.included && !it.no_coords && nameIsBlank(it.name);
const NEEDS_NAME = "Needs a name to export.";
/** The mark beside the name: a name the export needs, or one onX will cut. */
function nameCaution(it) {
  if (!it.included || it.no_coords) return null;
  return nameIsBlank(it.name) ? NEEDS_NAME : longNameSentence(it.name);
}
/** The mark beside a folder's name in its header: a name onX's rename dialog
    will cut. Only for a folder the export writes (it has an included item). */
function folderCaution(g) {
  return g.items.some(i => i.included) ? longFolderSentence(g.name) : null;
}
const fillAlpha = f => { const m = /rgba\([^)]*,\s*([\d.]+)\s*\)/.exec(f || ""); return m ? parseFloat(m[1]) : 1; };
/** The mark beside the note: a note onX will cut, or an item that won't export. */
function noteCaution(it) {
  if (!it.included) return null;
  if (it.no_coords) return "Won't export: it has no coordinates.";
  return longNoteSentence(it.desc);
}
/** The mark at the far right of an area's Icon cell, after "Area" (owner
    feedback 2026-10-24): onX will reset its fill. Not for an item that won't
    export (its one mark says so). */
function fillCaution(it) {
  return it.included && !it.no_coords && fillChanges(it) ? "onX will reset this area's fill to its default blue." : null;
}
const cautionMark = (fk, text, cls = "") =>
  `<span class="caution${cls}" tabindex="0" role="img" data-fk="${fk}" aria-label="${esc(text)}">${UI_ICON.caution}</span>`;

/** The row for item `it`: `old` (its live row, if it has one) when that is
    still right or can be patched to be, else a new one. */
function row(it, old = null) {
  const isWp = it.kind === "waypoints";
  const noteOpen = NOTE_EDIT && NOTE_EDIT.uid === it.uid;
  const cls = [it.needs_attention && "attention", SEL.has(it.uid) && "sel", !it.included && "excluded",
    POP && POP.uid === it.uid && "editing", DRAG && DRAG.active && DRAG.uidSet.has(it.uid) && "dragging",
    noteOpen && "note-open"].filter(Boolean).join(" ");
  const cname = colorName(it.color);
  const iconLabel = it.needs_attention ? "Default pin" : it.icon;
  const fk = esc(it.uid) + "|";
  const caution = noteCaution(it);
  const fillMark = fillCaution(it);
  const nameMark = nameCaution(it);
  const html = `
    <td class="selcol"><input type="checkbox" class="sel-box" data-fk="${fk}sel" aria-label="Select ${esc(it.name || "Untitled")}" ${SEL.has(it.uid) ? "checked" : ""}></td>
    <td class="namecol"><div class="name-cell"><input class="name-in" data-fk="${fk}name" aria-label="Name of ${esc(it.name || "Untitled")}" placeholder="Untitled" value="${esc(it.name)}">${nameMark ? cautionMark(`${fk}namecaution`, nameMark, " name-caution") : ""}</div>${it.included ? ""
      : `<span class="exc-label">Excluded</span><button type="button" class="exc-chip" data-fk="${fk}include" aria-label="Include ${esc(it.name || "Untitled")}" title="Left out of the export. Click to put it back.">Include</button>`}</td>
    <td class="notecol">${noteOpen ? noteEditor(it) :
      `<div class="note-cell">${caution ? cautionMark(`${fk}caution`, caution) : `<span class="caution-slot" aria-hidden="true"></span>`}<button type="button" class="note-btn" data-fk="${fk}note" aria-label="Open note for ${esc(it.name || "Untitled")}">
        <span class="note-text${firstLine(it.desc) ? "" : " empty"}">${esc(firstLine(it.desc) || "Add a note")}</span>${UI_ICON.pencil}</button></div>`}</td>
    <td class="iconcol">${isWp
      ? `<button type="button" class="icon-btn" data-fk="${fk}mark" title="${esc(it.why)}" aria-label="${esc(iconLabel)}, ${esc(cname)}. Change icon or color">${markerSVG(it.icon, it.hex, 22, 28)}${it.needs_attention
          ? `<span class="whymark" title="${esc(it.why)}">Default pin</span>`
          // An icon an onX file named that isn't in onX's list (Phase 2 flags
          // it): kept and exported as is, but marked so it gets a look.
          : `<span class="icon-name${it.unknown_icon ? " unknown-icon" : ""}">${esc(it.icon)}</span>`}</button>`
      : `<div class="icon-cell"><button type="button" class="line-btn" data-fk="${fk}mark" title="${esc(cname)} — ${esc(it.why)}" aria-label="${rowKindWord(it)}, ${esc(cname)}, ${styleLabel(it.style)}, ${weightLabel(it.weight)}. Change ${it.kind === "tracks" ? "line" : "area"}">${lineSVG(it.hex, it.kind, 22, 19, it.style, it.weight)}<span class="icon-name kind">${rowKindWord(it)}</span></button>${fillMark ? cautionMark(`${fk}fillcaution`, fillMark, " fill-caution") : ""}</div>`}</td>`;
  // Unchanged since it was last drawn: leave it be. (Its classes are checked
  // too: openPop, a tick and a drag set some directly.)
  if (old && old._html === html && old.className === cls) return old;
  const tr = document.createElement("tr");
  tr.dataset.uid = it.uid;
  if (cls) tr.className = cls;
  tr.innerHTML = html;
  tr._key = it;
  const selBox = tr.querySelector(".sel-box");
  selBox.onclick = e => {
    if (e.shiftKey && ANCHOR && ANCHOR !== it.uid) {
      // Range-select between the anchor and this row, in the order rows are
      // currently displayed -- so it follows the active filter and sort rather
      // than the underlying file order. Not prevented: the box keeps the
      // state its click gave it, which is `on` (a prevented click would put
      // the live box back after the render has set it).
      const order = selectableItems().map(i => i.uid);
      const a = order.indexOf(ANCHOR), b = order.indexOf(it.uid);
      if (a !== -1 && b !== -1) {
        const [lo, hi] = a < b ? [a, b] : [b, a];
        const on = !SEL.has(it.uid);
        for (let k = lo; k <= hi; k++) on ? SEL.add(order[k]) : SEL.delete(order[k]);
        renderFolders();
        return;
      }
      e.preventDefault();          // the anchor isn't on screen: the click does nothing but move it
    }
    ANCHOR = it.uid;
  };
  selBox.onchange = e => {
    const tr = e.target.closest("tr");
    e.target.checked ? SEL.add(it.uid) : SEL.delete(it.uid);
    tr.classList.toggle("sel", e.target.checked); updateSel();
    syncFolderBox(tr);
  };
  wireTextField(tr.querySelector(".name-in"), it, "name");
  if (noteOpen) wireNoteEditor(tr, it);
  else tr.querySelector(".note-btn").onclick = () => openNote(it);
  const chip = tr.querySelector(".exc-chip");
  if (chip) chip.onclick = () => edit(it, { included: true });
  tr.querySelector(".icon-btn, .line-btn").onclick = e => { e.stopPropagation(); openPop(it, e.currentTarget); };
  if (!old) { tr._html = html; return tr; }
  morph(old, tr);
  old._html = html;
  return old;
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
 *  An edited name is cleaned like a bulk Rename… (one rule set for every text
 *  edit, owner 2026-10-25): CairnRename.cleanName drops the characters XML
 *  forbids, turns a run of whitespace holding a tab or line break into one
 *  space and trims, silently. The field then shows what is stored. A value
 *  left untouched is never cleaned (a dirty loaded name stays as loaded), and
 *  one that cleans back to the stored name is no edit.
 *
 *  `required` fields refuse to commit empty. No field uses it since names became
 *  optional (owner, 2026-10-25): an empty name shows as "Untitled".
 */
function wireTextField(el, it, key, { required = false } = {}) {
  el.addEventListener("focus", () => { el.dataset.orig = el.value; });
  const commit = now => {
    if (el.value === el.dataset.orig) return;     // untouched: never cleaned
    const v = CairnRename.cleanName(el.value);
    if (required && !v) {
      el.value = el.dataset.orig ?? "";
      setStatus("An item needs a name.", "err");
      return;
    }
    el.value = v;                                 // what's on screen is what's stored
    el.dataset.orig = v;
    if (v === (it[key] ?? "")) return;            // cleans back to the stored value: no edit
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
  if (BULK) return;                // the several-items dialog owns the screen
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

/** The note the editor saves for draft, or null when saving it is no edit.
    An edited note is cleaned like a bulk Change note… (one rule set for every
    text edit, owner 2026-10-25): CairnRename.cleanNote drops the characters
    XML forbids, makes line endings "\n" and trims the outside, silently; inner
    line breaks stay. A draft left as the note was is never cleaned, and one
    that cleans back to the note as the file writes it is no edit. */
function noteToSave(it, draft) {
  const was = it.desc || "";
  if (draft === was) return null;
  const v = CairnRename.cleanNote(draft);
  return v === writtenNote(was) ? null : v;
}

function closeNote(it, apply) {
  if (!NOTE_EDIT) return;
  const v = apply && it ? noteToSave(it, NOTE_EDIT.draft) : null;
  NOTE_EDIT = null;
  if (v !== null) edit(it, { desc: v });
  else renderFolders();
}

function wireNoteEditor(tr, it) {
  const ta = tr.querySelector(".desc-in");
  ta.addEventListener("input", () => { NOTE_EDIT.draft = ta.value; syncUnloadGuard(); });
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
      ? "You chose the default pin."
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
  selectedItems().forEach(it => {
    const p = typeof patch === "function" ? patch(it) : patch;
    // An empty patch is no edit: it must not leave an empty EDITS entry, which
    // Start over and the leave prompts would count as a change.
    if (Object.keys(p).length) edit(it, p, { render: false });
  });
  refreshAfterEdit();
}

function updateSel() {
  const n = SEL.size;
  $("#selcount").textContent = `${n} selected`;
  $("#selbar").classList.toggle("hidden", n === 0);
  ["#bulk-icon", "#more-btn"].forEach(sel => {
    const el = $(sel);
    el.disabled = n === 0;
    el.title = n === 0 ? "Select items first" : "";
  });
  const sel = selectedItems();
  // One button, one dialog (UI-36). Lines and areas take a colour and a line
  // style, not an icon: say what it does.
  $("#bulk-icon").textContent = !n || sel.some(i => i.kind === "waypoints") ? "Icon & color…" : "Color & style…";
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
/* Every row of the popover and the dialog has one shape (owner feedback
   2026-10-24, UI-36): a label line with, in a dialog for several items, the
   "Leave as is" chip at its right end; the choices below it on one line. */
const LEAVE = "Leave as is";
const leaveChip = (cls, on, row = "") =>
  `<button type="button" class="reset-chip ${cls}"${row ? ` data-row="${row}"` : ""} aria-pressed="${on}">${LEAVE}</button>`;
const secHead = (label, chip = "") => `<div class="sec-row"><span class="label">${label}</span>${chip}</div>`;
/** A colour row: `leave` adds the chip (several items), `current` presses a swatch (one item). */
function colorRowHTML(row, label, colors, { leave = false, current = null, spread = false } = {}) {
  return `<div class="pop-sec color-sec" data-row="${row}">
      ${secHead(label, leave ? leaveChip("color-reset", true, row) : "")}
      <div class="palette${spread ? " spread" : ""}" data-row="${row}">${paletteHTML(colors, current)}</div>
    </div>`;
}
/** Style and Weight side by side, each its drawn-line toggles; `leave` adds
    each group's chip (several items). */
function lineOptsHTML(style, weight, leave = false) {
  const tog = (attr, k, name, glyph, on) =>
    `<button type="button" class="tog" data-${attr}="${k}" aria-label="${name}" title="${name}" aria-pressed="${on}">${glyph}</button>`;
  return `<div class="pop-sec line-opts">
      <div class="opt-group">${secHead("Style", leave ? leaveChip("style-reset", !style) : "")}<div class="toggles" role="group" aria-label="Style">${
        Object.keys(STYLE_NAMES).map(k => tog("style", k, STYLE_NAMES[k], lineGlyphSVG(k), k === style)).join("")}</div></div>
      <div class="opt-group">${secHead("Weight", leave ? leaveChip("weight-reset", !weight) : "")}<div class="toggles" role="group" aria-label="Weight">${
        Object.keys(WEIGHT_NAMES).map(k => tog("weight", k, WEIGHT_NAMES[k], lineGlyphSVG("solid", k), k === weight)).join("")}</div></div>
    </div>`;
}
function syncLineOpts(root, style, weight) {
  root.querySelectorAll(".tog[data-style]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.style === style)));
  root.querySelectorAll(".tog[data-weight]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.weight === weight)));
  root.querySelector(".style-reset")?.setAttribute("aria-pressed", String(!style));
  root.querySelector(".weight-reset")?.setAttribute("aria-pressed", String(!weight));
}
/* Fill (owner feedback 2026-10-24, UI-30/UI-36): onX gives every imported area
   its default blue, whatever the file says, so the one fill on offer is that
   blue ("Leave as is" or it). Picking it clears the area's fill caution and is
   what the export writes; the bridge refuses any other fill. */
const FILL_LABEL = "Blue";
function fillRowHTML() {
  return `<div class="pop-sec fill-sec" data-row="fill">
      ${secHead("Fill", leaveChip("fill-reset", true))}
      <div class="palette"><button type="button" class="fill-btn" aria-pressed="false"><span class="fill-swatch" aria-hidden="true"></span>${FILL_LABEL}</button></div>
    </div>`;
}
function syncFill(root, fill) {
  root.querySelector(".fill-reset")?.setAttribute("aria-pressed", String(!fill));
  root.querySelector(".fill-btn")?.setAttribute("aria-pressed", String(!!fill));
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
  if (BULK) return;                // a click queued behind the several-items dialog
  closeMenu(); closeBulk();
  POP = { uid: it.uid, color: it.color, icon: it.icon, iconPicked: false, q: "", anchor,
          style: it.style, weight: it.weight, fill: null };
  const isWp = it.kind === "waypoints";
  const isLine = it.kind === "tracks";
  const styled = hasLineStyle(it);   // a line or an area: Style and Weight below the colors
  const pop = $("#mark-pop");
  pop.classList.toggle("line", isLine);
  pop.setAttribute("aria-label", `Change ${isWp ? "icon and color" : isLine ? "line" : "area"} for ${it.name || "Untitled"}`);
  pop.innerHTML = `
    <div class="pop-head">
      <span class="pop-preview"></span>
      <div class="pop-title"><span class="pop-name">${esc(it.name || "Untitled")}</span></div>
    </div>
    ${isLine ? `<div class="pop-map"></div>` : ""}
    ${colorRowHTML("color", "Color", paletteFor([it]), { current: POP.color, spread: styled })}
    ${isWp ? `<div class="pop-sec icons">
      ${secHead("Icon", `<span class="sec-count">${DATA.icons.length} icons</span>`)}
      <input type="search" class="icon-search" aria-label="Find an icon" placeholder="Find an icon" autocomplete="off">
      <div class="icon-grid" role="group" aria-label="Icons"></div>
    </div>` : styled ? lineOptsHTML(POP.style, POP.weight) : ""}
    ${it.kind === "shapes" ? fillRowHTML() : ""}
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
  const fb = pop.querySelector(".fill-btn");
  if (fb) {
    fb.onclick = () => { POP.fill = ONX_DEFAULT_FILL; drawPop(); };
    pop.querySelector(".fill-reset").onclick = () => { POP.fill = null; drawPop(); };
  }
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
/** The marker the popover belongs to: a re-render while it is open keeps
    it, unless its row has left the screen. */
const popAnchor = () => POP && POP.anchor.isConnected ? POP.anchor : null;

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
  syncFill(pop, POP.fill);
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
  if (it.kind === "shapes" && POP.fill && POP.fill !== it.fill) patch.fill = POP.fill;
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

/* ---------- several items: ONE dialog from the selection bar (UI-36) ----------
   Waypoints get Waypoint color and Icon; lines and areas get Color, Style and
   Weight, and Fill when there are areas. Every row starts on "Leave as is",
   which leaves each item its own value. A mixed selection gets both sets, the
   pin and line colours apart (onX's 10 and 11). */
function openBulk() {
  // Already open (Rename… or Change note…): a #bulk-icon click queued by
  // deferRender must not open a second dialog over it.
  if (BULK) return;
  const items = selectedItems();
  if (!items.length) return;
  const ret = document.activeElement;
  closeMenu(); closePop();
  BULK = { uids: new Set(items.map(i => i.uid)), pinColor: null, lineColor: null, icon: null,
           style: null, weight: null, fill: null, q: "", ret };
  const hasWp = items.some(i => i.kind === "waypoints");
  const hasLn = items.some(hasLineStyle);
  const hasArea = items.some(i => i.kind === "shapes");
  const mixed = hasWp && hasLn;
  const d = $("#mark-dialog");
  d.setAttribute("aria-label", `Change ${hasWp ? "icon and color" : "color and style"} for ${items.length} items`);
  d.innerHTML = `
    <div class="bulk-head">
      <div class="modal-head plain"><h2>Change ${plural(items.length, "item")}</h2>
        <button type="button" class="x bulk-x" aria-label="Close">${UI_ICON.close}</button></div>
      <div class="now-after">
        <span class="label">Now</span><span></span><span class="label">After</span>
        <div class="na-rows"></div>
      </div>
    </div>
    ${hasWp ? colorRowHTML("pin", mixed ? "Waypoint color" : "Color", DATA.colors, { leave: true }) + `<div class="pop-sec icons">
      ${secHead("Icon", leaveChip("icon-reset", true))}
      <input type="search" class="icon-search" aria-label="Find an icon for all selected waypoints" placeholder="Find an icon" autocomplete="off">
      <div class="icon-grid" role="group" aria-label="Icons"></div>
    </div>` : ""}
    ${hasLn ? colorRowHTML("line", mixed ? "Line color" : "Color", colorList(), { leave: true }) + lineOptsHTML(null, null, true) : ""}
    ${hasArea ? fillRowHTML() : ""}
    <div class="pop-foot">
      <button type="button" class="btn bulk-cancel">Cancel</button>
      <button type="button" id="bulk-apply" class="btn primary">Save</button>
    </div>`;
  const key = row => row === "pin" ? "pinColor" : "lineColor";
  d.querySelectorAll(".color-reset").forEach(c => c.onclick = () => { BULK[key(c.dataset.row)] = null; drawBulk(); });
  d.querySelectorAll(".palette[data-row] .swatch-btn").forEach(b => b.onclick = () => {
    BULK[key(b.closest(".palette").dataset.row)] = b.dataset.rgba; drawBulk(); });
  if (hasWp) {
    d.querySelector(".icon-reset").onclick = () => { BULK.icon = null; drawBulk(); };
    const grid = d.querySelector(".icon-grid");
    buildIconGrid(grid, BULK.icon, n => { BULK.icon = n; drawBulk(); });
    const s = d.querySelector(".icon-search");
    s.oninput = () => { BULK.q = s.value; filterIconGrid(grid, BULK.q); };
  }
  if (hasLn) {
    // Picking the chosen toggle again un-picks it, like its "Leave as is".
    d.querySelectorAll(".tog[data-style]").forEach(b => b.onclick = () => {
      BULK.style = BULK.style === b.dataset.style ? null : b.dataset.style; drawBulk(); });
    d.querySelectorAll(".tog[data-weight]").forEach(b => b.onclick = () => {
      BULK.weight = BULK.weight === b.dataset.weight ? null : b.dataset.weight; drawBulk(); });
    d.querySelector(".style-reset").onclick = () => { BULK.style = null; drawBulk(); };
    d.querySelector(".weight-reset").onclick = () => { BULK.weight = null; drawBulk(); };
  }
  if (hasArea) {
    d.querySelector(".fill-btn").onclick = () => { BULK.fill = ONX_DEFAULT_FILL; drawBulk(); };
    d.querySelector(".fill-reset").onclick = () => { BULK.fill = null; drawBulk(); };
  }
  d.querySelector(".bulk-x").onclick = closeBulk;
  d.querySelector(".bulk-cancel").onclick = closeBulk;
  d.querySelector("#bulk-apply").onclick = applyBulk;
  $("#mark-modal").classList.remove("hidden");
  drawBulk();
  d.querySelector(".reset-chip").focus();
}

function drawBulk() {
  const d = $("#mark-dialog");
  const items = allItems().filter(i => BULK.uids.has(i.uid));
  const hexOf = rgba => (colorOf(rgba) || {}).hex;
  d.querySelector(".na-rows").innerHTML = items.map(it => {
    const isWp = it.kind === "waypoints";
    const toColor = (isWp ? BULK.pinColor : BULK.lineColor) || it.color;
    const toIcon = isWp ? (BULK.icon || it.icon) : null;
    const nowMark = isWp ? markerSVG(it.icon, it.hex, 22, 28) : lineSVG(it.hex, it.kind, 22, 20, it.style, it.weight);
    const afterMark = isWp ? markerSVG(toIcon, hexOf(toColor) || it.hex, 22, 28)
      : lineSVG(hexOf(toColor) || it.hex, it.kind, 22, 20, BULK.style || it.style, BULK.weight || it.weight);
    // The drawn marks show the change; no "Camp · Blue" words beside them (UI-26).
    return `<span class="na-cell">${nowMark}<span class="na-name" title="${esc(it.name || "Untitled")}">${esc(it.name || "Untitled")}</span></span>${UI_ICON.arrow}` +
      `<span class="na-cell">${afterMark}</span>`;
  }).join("");
  d.querySelectorAll(".palette[data-row]").forEach(p => {
    const v = p.dataset.row === "pin" ? BULK.pinColor : BULK.lineColor;
    p.closest(".pop-sec").querySelector(".color-reset").setAttribute("aria-pressed", String(!v));
    p.querySelectorAll(".swatch-btn").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.rgba === v)));
  });
  const ir = d.querySelector(".icon-reset");
  if (ir) ir.setAttribute("aria-pressed", String(!BULK.icon));
  syncIconGrid(d.querySelector(".icon-grid"), BULK.icon);
  syncLineOpts(d, BULK.style, BULK.weight);
  syncFill(d, BULK.fill);
}

function applyBulk() {
  const { pinColor, lineColor, icon, style, weight, fill, uids } = BULK;
  const items = allItems().filter(i => uids.has(i.uid));
  closeBulk();
  const changed = [];
  items.forEach(it => {
    const patch = {};
    const color = it.kind === "waypoints" ? pinColor : lineColor;
    if (color) patch.color = color;
    if (icon && it.kind === "waypoints") patch.icon = icon;
    if (hasLineStyle(it)) {
      if (style && style !== it.style) patch.style = style;
      if (weight && weight !== it.weight) patch.weight = weight;
    }
    if (fill && it.kind === "shapes" && fill !== it.fill) patch.fill = fill;
    if (Object.keys(patch).length) { edit(it, patch, { render: false }); changed.push(it); }
  });
  if (!changed.length) return;
  refreshAfterEdit();
  const n = changed.length;
  const word = changed.every(i => i.kind === "shapes") ? "area" : changed.every(i => i.kind === "tracks") ? "line" : "item";
  setStatus(`Changed ${plural(n, word)}.`, "ready");
}

function closeBulk() {
  if (!BULK) return;
  const { ret, text } = BULK;
  if (text) clearTimeout(text.timer);
  BULK = null;
  $("#mark-modal").classList.add("hidden");
  const d = $("#mark-dialog");
  d.innerHTML = "";
  // What the text mode set, so the next dialog (and a test waiting on
  // [data-bulk]) never sees a closed one's.
  ["data-bulk", "data-preview-seq", "aria-labelledby"].forEach(a => d.removeAttribute(a));
  const to = ret && ret !== document.body && ret.isConnected && !ret.disabled ? ret : $("#bulk-icon");
  if (!to.disabled) to.focus({ preventScroll: true });
}

/* ---------- several items: Rename… and Change note… (UI-39) ----------
   A text mode of the same dialog (BULK.text): a mode (Add before, Add after,
   Find and replace, and for notes Replace the note), its fields, and the
   selection's names or notes Now → After. The change itself is
   CairnRename.transform (web/rename.js), run by the list and again by Save,
   so the list shows what Save stores and the export writes. BULK being set
   is what every guard of the dialog reads (Esc, Tab, the backdrop, Ctrl+A,
   row drags, the menus and popovers, Export, Start over). */
const TEXT_MODES = {
  name: [["prefix", "Add before"], ["suffix", "Add after"], ["replace", "Find and replace"]],
  desc: [["prefix", "Add before"], ["suffix", "Add after"], ["replace", "Find and replace"], ["set", "Replace the note"]],
};
const TEXT_FIELDS = { "bulk-text": "text", "bulk-find": "find", "bulk-repl": "repl" };
const PREVIEW_ROWS = 200;              // rows drawn Now → After; "and N more" for the rest
const PREVIEW_WAIT_MS = 60;            // typing changes the spec at once, the list this much later
/* Timings of the last preview and Save (performance.now(), ms), for the
   perf test and scripts/qa/fuzz_ui.py. */
window.__cairnPerf = { lastTransformMs: null, lastPreviewMs: null, lastSaveMs: null };

const openRename = () => openTextBulk("name");
const openChangeNote = () => openTextBulk("desc");

/** field: "name" (Rename…) or "desc" (Change note…). */
function openTextBulk(field) {
  if (BULK || !DATA) return;
  flushDeferred();                 // a name just left: its rename, or its merge offer, first
  if (CONFIRM) return;             // and never this dialog over that offer
  const items = selectedItems();
  if (!items.length) return;
  // A note open on a selected row: closed first, asking if it changed (UI-22).
  if (NOTE_EDIT && items.some(i => i.uid === NOTE_EDIT.uid)) {
    const again = () => openTextBulk(field);
    if (noteIsChanged()) { askToSaveNote(again, $("#more-btn")); return; }
    closeNote(allItems().find(i => i.uid === NOTE_EDIT.uid), false);
    again();
    return;
  }
  closeMenu(); closePop(); closeMove(false); hideTip();
  const rows = items.map(i => ({ uid: i.uid, name: i.name, desc: i.desc, kind: i.kind }));
  BULK = {
    uids: new Set(rows.map(r => r.uid)), rows, byUid: new Map(rows.map(r => [r.uid, r])),
    // NAME_LIMIT (onX's 255-byte name cut) is read at boot like NOTE_LIMIT; 255 until then.
    ctx: { noteLimit: NOTE_LIMIT, nameLimit: typeof NAME_LIMIT === "number" ? NAME_LIMIT : 255 }, ret: $("#more-btn"),
    text: { field, timer: null, spec: { field, mode: "prefix", text: "", find: "", repl: "", matchCase: false } },
  };
  const d = $("#mark-dialog");
  d.removeAttribute("aria-label");
  d.dataset.bulk = field === "name" ? "rename" : "note";
  d.dataset.previewSeq = "0";
  d.setAttribute("aria-labelledby", "bulk-title");
  d.innerHTML = `
    <div class="bulk-head">
      <div class="modal-head plain"><h2 id="bulk-title">${field === "name" ? "Rename" : "Change the note on"} ${plural(rows.length, "item")}</h2>
        <button type="button" class="x bulk-x" aria-label="Close">${UI_ICON.close}</button></div>
      <div class="mode-row">${TEXT_MODES[field].map(([m, label]) =>
        `<button type="button" class="tog mode-tog" data-mode="${m}" aria-pressed="false">${label}</button>`).join("")}</div>
      <div class="text-fields"></div>
    </div>
    <div class="pop-sec text-preview">
      <div class="now-after">
        <span class="label">Now</span><span></span><span class="label">After</span>
        <div class="na-rows"></div>
      </div>
    </div>
    <div class="pop-foot">
      <span id="bulk-summary" aria-live="polite"></span>
      <button type="button" class="btn bulk-cancel">Cancel</button>
      <button type="button" id="bulk-apply" class="btn primary" disabled>Save</button>
    </div>`;
  d.querySelectorAll(".mode-tog").forEach(b => b.onclick = () => setTextMode(b.dataset.mode));
  d.querySelector(".bulk-x").onclick = closeBulk;
  d.querySelector(".bulk-cancel").onclick = closeBulk;
  d.querySelector("#bulk-apply").onclick = applyTextBulk;
  $("#mark-modal").classList.remove("hidden");
  drawTextFields();
  drawTextBulk();
  d.querySelector(".text-fields textarea, .text-fields input").focus();
}

/** Show the fields of the chosen mode. What was typed stays in the spec, so
    going back to a mode finds its text again. */
function setTextMode(mode) {
  if (!BULK || !BULK.text) return;
  readTextFields();
  BULK.text.spec.mode = mode;
  drawTextFields();
  drawTextBulk();
}

function drawTextFields() {
  const { field, spec } = BULK.text;
  const d = $("#mark-dialog");
  d.querySelectorAll(".mode-tog").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === spec.mode)));
  // Names take one line; a note's fields are multi-line, like the note editor.
  const box = (id, label) => `<div class="text-field"><label class="label" for="${id}">${label}</label>${field === "name"
    ? `<input id="${id}" type="text" autocomplete="off" spellcheck="false">`
    : `<textarea id="${id}" rows="3" spellcheck="false"></textarea>`}</div>`;
  const host = d.querySelector(".text-fields");
  const find = spec.mode === "replace";
  host.classList.toggle("find", find);
  host.innerHTML = find
    ? box("bulk-find", "Find") + box("bulk-repl", "Replace with") +
      `<button type="button" id="bulk-match-case" aria-pressed="${spec.matchCase}">Match case</button>`
    : box("bulk-text", "Text");
  // Values set as values: in markup, a textarea drops a leading line break.
  host.querySelectorAll("input, textarea").forEach(el => { el.value = spec[TEXT_FIELDS[el.id]]; wireTextBulkField(el); });
  const mc = host.querySelector("#bulk-match-case");
  if (mc) mc.onclick = () => {
    spec.matchCase = !spec.matchCase;
    mc.setAttribute("aria-pressed", String(spec.matchCase));
    drawTextBulk();
  };
}

/** Every keystroke changes the spec at once; the list follows PREVIEW_WAIT_MS
    later. Enter saves (Ctrl / Cmd + Enter in a note's fields, where Enter
    starts a new line), never while an input method is composing. */
function wireTextBulkField(el) {
  const typed = () => {
    if (!BULK || !BULK.text) return;
    BULK.text.spec[TEXT_FIELDS[el.id]] = el.value;
    clearTimeout(BULK.text.timer);
    BULK.text.timer = setTimeout(drawTextBulk, PREVIEW_WAIT_MS);
  };
  el.addEventListener("input", typed);
  el.addEventListener("compositionend", typed);
  el.addEventListener("keydown", e => {
    if (e.key !== "Enter" || e.isComposing || e.keyCode === 229) return;
    if (el.nodeName === "TEXTAREA" && !(e.metaKey || e.ctrlKey)) return;   // a new line
    e.preventDefault();
    applyTextBulk();               // which saves nothing when nothing changes
  });
}

/** The fields as they are now, into the spec (Save never trusts the list). */
function readTextFields() {
  const { spec } = BULK.text;
  for (const [id, k] of Object.entries(TEXT_FIELDS)) {
    const el = document.getElementById(id);
    if (el) spec[k] = el.value;
  }
  return spec;
}

/** One preview cell. A name that is empty shows the placeholder "Untitled"
    (display only: an empty name is stored and exported empty); a missing
    note is blank. */
function textCell(cls, v, names) {
  if (names && !v) return `<span class="${cls} is-placeholder">Untitled</span>`;
  return `<span class="${cls}"${v ? ` title="${esc(v)}"` : ""}>${esc(v)}</span>`;
}
/** after as HTML with each of the core's marks highlighted (.hit, the
    mockups' green): every replaced match, the text Add before / Add after
    added, or the whole new value (UI-39; web/rename.js decides what was
    inserted, the dialog only draws it). A mark's edges widen so a combining
    mark, a variation selector, a skin tone, a ZWJ sequence, a flag or a
    surrogate pair is never split; marks that then touch are drawn as one.
    No marks (a pure deletion, or cleaning the ranges can't follow) is plain
    text. The text is after's, exactly. */
const JOINS = /[\p{M}\u200D\uFE00-\uFE0F\u{1F3FB}-\u{1F3FF}\u{E0020}-\u{E007F}]/u;
const isRI = c => c >= "\u{1F1E6}" && c <= "\u{1F1FF}";
function markRanges(after, marks) {
  if (!marks || !marks.length) return esc(after);
  const b = Array.from(after);
  // Code point of each UTF-16 offset: a start inside a pair moves to the pair, an end past it.
  const cp = new Array(after.length + 1);
  let u = 0;
  b.forEach((ch, i) => { for (let k = 0; k < ch.length; k++) cp[u++] = i + (k ? 0.5 : 0); });
  cp[u] = b.length;
  const odd = i => { let k = 0; while (b[i] && isRI(b[i])) { k++; i--; } return k % 2 === 1; };
  const joined = i => i > 0 && i < b.length &&
    (JOINS.test(b[i]) || b[i - 1] === "\u200D" || (isRI(b[i]) && odd(i - 1)));
  const spans = [];
  for (const [ms, me] of marks) {
    let s = Math.floor(cp[ms]), t = Math.ceil(cp[me]);
    if (!(t > s)) continue;
    while (joined(s)) s--;
    while (joined(t)) t++;
    const last = spans[spans.length - 1];
    if (last && s <= last[1]) last[1] = Math.max(last[1], t);
    else spans.push([s, t]);
  }
  let html = "", at = 0;
  for (const [s, t] of spans) {
    html += esc(b.slice(at, s).join("")) + `<span class="hit">${esc(b.slice(s, t).join(""))}</span>`;
    at = t;
  }
  return html + esc(b.slice(at).join(""));
}
/** A changed row's After cell, its marks highlighted; an empty name is the
    "Untitled" placeholder. */
function afterCell(r, names) {
  if (!r.after) return textCell("na-after", r.after, names);
  return `<span class="na-after" title="${esc(r.after)}">${markRanges(r.after, r.marks)}</span>`;
}
/** The name twin of the long-note sentence (tracker 7.4 L1): onX's importer
    keeps the first nameLimit UTF-8 bytes of a name; N counts the characters
    past them, as noteOverflow does for notes. */
function bulkNameSentence(name, limit) {
  let upTo = 0, cut = 0;
  for (const ch of name) { upTo += CairnRename.noteBytes(ch); if (upTo > limit) cut++; }
  return `onX imports only the first ${limit} bytes of a name. About ${plural(Math.max(cut, 1), "character")} will be cut.`;
}
/** The sentence under a row: "No change", the long-note caution (UI-34), or a
    name onX will cut or can't import without (tracker 7.4 L1, N1). All warn;
    none blocks Save. */
function textFlag(r) {
  if (r.flags.includes("unchanged")) return "No change";
  if (r.flags.includes("note-over-limit")) return longNoteSentence(r.after) || "";
  if (r.flags.includes("name-over-limit")) return bulkNameSentence(r.after, BULK.ctx.nameLimit);
  if (r.flags.includes("name-empty")) return "Needs a name to export.";
  return "";
}

/** The Now → After list, the summary and Save, from the spec as it is. Changed
    rows first; at most PREVIEW_ROWS rows. */
function drawTextBulk() {
  if (!BULK || !BULK.text) return;
  const t = BULK.text, names = t.field === "name";
  clearTimeout(t.timer); t.timer = null;
  const t0 = performance.now();
  const res = CairnRename.transform(BULK.rows, t.spec, BULK.ctx);
  const t1 = performance.now();
  const same = r => r.flags.includes("unchanged");
  const changed = res.rows.filter(r => !same(r)), unchanged = res.rows.filter(same);
  const shown = changed.slice(0, PREVIEW_ROWS);
  shown.push(...unchanged.slice(0, PREVIEW_ROWS - shown.length));
  const more = res.rows.length - shown.length;
  const html = shown.map(r => {
    const before = textCell("na-before", r.before, names);
    let src = before;
    if (!names) {
      // A note's row says whose note it is.
      const name = (BULK.byUid.get(r.uid) || {}).name || "";
      src = `<div class="na-src"><span class="na-name${name ? "" : " untitled"}"${name ? ` title="${esc(name)}"` : ""}>${esc(name || "Untitled")}</span>${before}</div>`;
    }
    const flag = textFlag(r);
    return `<div class="na-row" data-uid="${esc(r.uid)}" data-flags="${esc(r.flags.join(" "))}">${src}${UI_ICON.arrow}` +
      `${same(r) ? textCell("na-after", r.after, names) : afterCell(r, names)}<span class="na-flag">${flag && !same(r) ? UI_ICON.caution : ""}${esc(flag)}</span></div>`;
  }).join("") + (more > 0 ? `<div class="na-more">and ${more.toLocaleString("en-US")} more</div>` : "");
  const d = $("#mark-dialog");
  d.querySelector(".na-rows").innerHTML = html;
  const summary = `${res.changed.toLocaleString("en-US")} will change · ${unchanged.length.toLocaleString("en-US")} unchanged`;
  const sum = $("#bulk-summary");
  if (sum.textContent !== summary) sum.textContent = summary;   // announced once per change
  $("#bulk-apply").disabled = !(res.changed > 0);
  d.dataset.previewSeq = String((Number(d.dataset.previewSeq) || 0) + 1);
  window.__cairnPerf.lastTransformMs = t1 - t0;
  window.__cairnPerf.lastPreviewMs = performance.now() - t0;
}

/** Save: the fields read again and the change worked out again on the items
    as they are now (the list may be a keystroke behind), nothing when nothing
    changes; then each changed item through edit(), like a single edit. */
function applyTextBulk() {
  if (!BULK || !BULK.text) return;
  const t0 = performance.now();
  const { field } = BULK.text;
  const spec = readTextFields();
  const byUid = new Map(allItems().map(i => [i.uid, i]));   // one lookup per row, not a find()
  const rows = BULK.rows.map(r => byUid.get(r.uid)).filter(Boolean)
    .map(it => ({ uid: it.uid, name: it.name, desc: it.desc, kind: it.kind }));
  const res = CairnRename.transform(rows, spec, BULK.ctx);
  if (!(res.changed > 0)) { drawTextBulk(); return; }
  closeBulk();
  let n = 0;
  res.rows.forEach(r => {
    const it = byUid.get(r.uid);
    if (!it || r.flags.includes("unchanged")) return;
    edit(it, { [field]: r.after }, { render: false });
    n++;
  });
  refreshAfterEdit();
  // The search may have dropped every changed row from the selection: then the
  // next shift-click starts afresh, as after a move (afterMove).
  if (!SEL.size) ANCHOR = null;
  setStatus(`Changed ${plural(n, "item")}.`, "ready");
  // An emptied selection also disables More: focus would be lost to the page,
  // so it goes to the search.
  const a = document.activeElement;
  if (!a || a === document.body || a.disabled) $("#filter").focus({ preventScroll: true });
  window.__cairnPerf.lastSaveMs = performance.now() - t0;
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
  endDrag(); closeMove(false);
  RENAME = null; PENDING_MERGE = null; SAVED = null;
}

const groupByKey = key => DATA.groups.find(g => g.key === key) || null;
/** Two folder names are the same name when these match: trimmed, any case
    (the bridge's _name_taken rule, which decides). */
const nameKey = s => s.trim().toLowerCase();
/** uid -> the key of the folder it is in. */
function homeOf() {
  const m = new Map();
  DATA.groups.forEach(g => g.items.forEach(i => m.set(i.uid, g.key)));
  return m;
}
/** The folder every one of these items is already in, or null when they come
    from several. Moving them there would do nothing, so it reads "here now"
    and isn't offered; a folder holding only SOME of them is a real target. */
function hereKey(uids) {
  const m = homeOf();
  const keys = new Set(uids.map(u => m.get(u)));
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
  [...SORT.keys()].forEach(k => { if (!live.has(k)) SORT.delete(k); });
  let gone = null;
  if (FILTERS.folder !== null && !live.has(FILTERS.folder)) {
    gone = old.get(FILTERS.folder)?.name ?? null;
    FILTERS.folder = null;
  }
  if (RENAME && !live.has(RENAME.key)) RENAME = null;
  DATA.totals.folders = groups.length;   // nothing on screen reads it; the e2e tests do
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

/** One folder action on the bridge: run it and show the layout it returns.
    On a failure (a taken name included) say so and show the bridge's own
    layout instead, and return null. */
function folderAction(verb, src, vars) {
  try {
    const res = pyJSON(src, vars);
    if (!res.ok) throw new Error("That folder name is taken.");
    return { res, gone: syncLayout(res) };
  } catch (e) {
    setStatus(`Couldn't ${verb} — ` + humanError(e), "err"); console.error(e);
    resyncAfterFailure();
    return null;
  }
}

/** A new folder's name, open for editing in the rail. fresh (made empty by
    + New folder): Esc on its name takes the folder back (finishRename). */
function openNewFolderName(key, fresh = false) {
  RENAME = { key, draft: groupByKey(key).name, where: "rail", fresh };
  RAIL_FOLDED.delete("folders");
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
  const v = it ? noteToSave(it, NOTE_EDIT.draft) : null;
  NOTE_EDIT = null;
  if (v !== null) edit(it, { desc: v }, { render: false });
}

/** A folder name in a status line: at most SHORT_NAME characters. */
const SHORT_NAME = 48;
const shortName = s => { const c = [...s]; return c.length > SHORT_NAME ? c.slice(0, SHORT_NAME - 1).join("").trimEnd() + "…" : s; };

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
  const u = JSON.stringify(uids);
  const done = key === NEW_TARGET
    ? folderAction("move", "bridge.move_to_new_folder(_cairn_uids)", { _cairn_uids: u })
    : folderAction("move", "bridge.move_items(_cairn_uids, _cairn_key)", { _cairn_uids: u, _cairn_key: key });
  if (!done) return null;
  const { res, gone } = done;
  if (res.created) openNewFolderName(res.key);
  afterMove(res, uids, gone);
  if (res.created) focusRename();
  return res;
}

/** A click (or Enter / Space) on the rail's + New folder: the
    ticked rows go into a new folder, as if dropped there; with nothing
    ticked, an empty folder is made, to drop rows on. Either way its name
    opens for editing in the rail. */
function newFolderClicked() {
  if (!DATA) return;
  const uids = selectedItems().map(i => i.uid);
  if (uids.length) { moveTo(uids, NEW_TARGET); return; }
  closePop();
  const done = folderAction("make a folder", "bridge.create_folder()", {});
  if (!done) return;
  openNewFolderName(done.res.key, true);
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
  if (!folderAction("remove", "bridge.remove_empty_folder(_cairn_key)", { _cairn_key: key })) return;
  refreshAfterEdit();
  setStatus(`Removed the empty folder “${shortName(g.name)}”.`, "ready");
  focusFk(next);
}

function startRename(key, where, draft = null, declined = null) {
  if (BULK) return;                // the several-items dialog owns the screen
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
  const checkAdded = added => {
    const kept = inp.value.length - (inp.selectionEnd - inp.selectionStart);
    if (kept + added.length > FOLDER_NAME_MAX) setStatus(tooLong, "err");
  };
  inp.addEventListener("beforeinput", e => {
    if (!e.inputType.startsWith("insert")) return;
    checkAdded(e.data ?? e.dataTransfer?.getData("text/plain") ?? "");
  });
  // Some browsers give a paste no text in beforeinput: read it from the paste itself.
  inp.addEventListener("paste", e => checkAdded((e.clipboardData?.getData("text/plain") ?? "").replace(/[\r\n]+/g, " ")));
  inp.addEventListener("input", () => {
    if (RENAME && RENAME.key === key) RENAME.draft = inp.value;
    if (inp.value.length < FOLDER_NAME_MAX && $("#status").textContent === tooLong) setStatus("");
  });
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); finishRename(key, true); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finishRename(key, false); }
  });
  // A patch that moves or replaces the input is not the user leaving it
  // (Chrome fires blur on a focused element as it is moved or removed).
  inp.addEventListener("blur", () => { if (!PATCHING && inp.isConnected) finishRename(key, true, { defer: true }); });
}

function finishRename(key, save, { defer = false } = {}) {
  if (!RENAME || RENAME.key !== key || !DATA) return;
  const { draft, where, declined, fresh } = RENAME;
  RENAME = null;
  const g = groupByKey(key);
  if (!save && fresh && g && !g.items.length) { removeEmptyFolder(key); return; }
  let reopen = false, failed = false;
  // Left unchanged after Cancel on its merge offer: keep the name it has,
  // don't ask again (or Cancel, reopen, leave, ask... would never end).
  if (declined && nameKey(draft) === nameKey(declined)) save = false;
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
      { label: "Cancel", initial: true, cancel: true, run: cancel },
      { label: "Move them", run: () => { closeConfirm(false); mergeInto(src.key, dup.key, where); } },
    ],
  });
}

function mergeInto(srcKey, dstKey, where = "head") {
  const src = groupByKey(srcKey);
  if (!src || srcKey === dstKey) return;
  const uids = src.items.map(i => i.uid);
  const done = folderAction("move", "bridge.merge_folders(_cairn_key, _cairn_key2)",
                            { _cairn_key: srcKey, _cairn_key2: dstKey });
  if (!done) return;
  afterMove(done.res, uids, done.gone);
  const to = (where === "head" && fkEl("fname|" + dstKey)) || fkEl("folder|" + dstKey);
  if (to) to.focus({ preventScroll: true });
}

/* ---------- More ▸ Move to… (the keyboard route) ---------- */
function openMoveTo() {
  if (BULK) return;                // the several-items dialog owns the screen
  const uids = selectedItems().map(i => i.uid);
  if (!uids.length) return;
  closeMenu(); closePop();
  const here = hereKey(uids);
  MOVE = { uids, ret: $("#more-btn") };   // uids: for scripts/qa/fuzz_ui.py (the buttons close over theirs)
  const p = $("#move-pop");
  p.innerHTML = `<div class="move-h" id="move-h">Move ${plural(uids.length, "item")} to</div>
    <div class="move-list" role="group" aria-labelledby="move-h">${DATA.groups.map(g => {
      const h = g.key === here;
      return `<button type="button" class="move-opt${isUnorganized(g) ? " unorg" : ""}" data-key="${esc(g.key)}"${h ? " disabled" : ""}>` +
        `<span class="facet-name">${esc(g.name)}${h ? " · here now" : ""}</span>` +
        // The count tells apart two folders a file named alike ("Camp", "camp").
        `<span class="facet-count">${h ? "" : g.items.length}</span></button>`;
    }).join("")}<button type="button" class="move-opt move-new">+ New folder</button></div>`;
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
  const vh = window.innerHeight;
  const top = Math.min(r.bottom + 6, vh - 160);
  p.style.top = `${top}px`;
  p.style.maxHeight = `${vh - top - 12}px`;
  p.style.left = `${leftInWindow(r.left, p.offsetWidth)}px`;
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
const SCROLL_EDGE_PX = 36, SCROLL_MAX_PX = 48;   // the rail's auto-scroll band, and its top speed per frame
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
  // A cancelled-but-held DRAG left here blocked the next press, text
  // selection, Esc and a click.
  document.addEventListener("pointercancel", () => endDrag());
  window.addEventListener("blur", () => endDrag());
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
  ghost.innerHTML = `${UI_ICON.move}<span>Move ${plural(d.uids.length, "item")}</span>`;
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
  if (d.x >= r.left && d.x <= r.right) {
    let dy = 0;
    // Faster the deeper in: over the footer it races (200 folders is ~5000px).
    const speed = depth => Math.min(SCROLL_MAX_PX, Math.ceil(depth / 2));
    if (d.y < r.top + SCROLL_EDGE_PX) dy = -speed(r.top + SCROLL_EDGE_PX - d.y);
    else if (d.y > bottom - SCROLL_EDGE_PX) dy = speed(d.y - (bottom - SCROLL_EDGE_PX));
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
    pushStage("done");
    setStatus("");   // the screen says it: no "Built N folders" up top
    window.__cairnExported = true;
  } catch (e) {
    setStatus("Export failed: " + humanError(e), "err"); console.error(e);
  }
}

/** The export screen's long-note warning (owner's wording, 2026-10-24): the
    items whose notes onX will cut, by name as written in straight single
    quotes, up to LONG_NOTES_SHOWN, then "and N more". */
const LONG_NOTES_SHOWN = 8;
/** Up to LONG_NOTES_SHOWN quoted names, then "and N more". */
function nameList(quoted) {
  const n = LONG_NOTES_SHOWN;
  return quoted.length > n ? `${quoted.slice(0, n).join(", ")} and ${quoted.length - n} more` : quoted.join(", ");
}
function longNoteWarning() {
  const names = MANIFEST.flatMap(e => (e.long_notes || []).map(([n]) => `\u201c${shortName(n || "Untitled")}\u201d`));
  const list = nameList(names);
  return names.length === 1 ? `Item ${list} is over the length limit and will be truncated by onX.`
    : `Items ${list} are over the length limit and will be truncated by onX.`;
}
/** The same warning for names over onX's 255 bytes and folder names over its
    50 characters (L1). Every list shortens a name past 48 characters (shortName):
    these names are long by definition. */
function longNameWarning() {
  const names = MANIFEST.flatMap(e => (e.long_names || []).map(([n]) => `\u201c${shortName(n)}\u201d`));
  const list = nameList(names);
  return names.length === 1 ? `Name ${list} is over the length limit and will be truncated by onX.`
    : `Names ${list} are over the length limit and will be truncated by onX.`;
}
function longFolderWarning() {
  const names = MANIFEST.filter(e => e.long_folder).map(e => `\u201c${shortName(e.folder)}\u201d`);
  const list = nameList(names);
  return names.length === 1 ? `Folder name ${list} is over the length limit and will be truncated by onX.`
    : `Folder names ${list} are over the length limit and will be truncated by onX.`;
}

function renderRunbook() {
  // The warnings' numbers come from bridge.runbook_summary (the manifest that
  // instructions.txt is built from), so the over-limit check uses
  // max(written, expected) and dropped items are reported. One box per folder
  // (UI-31: its name, Download, the file chips); the warnings sit above them.
  const S = JSON.parse(py.runPython("bridge.runbook_summary_json()"));
  const host = $("#runbook");
  host.innerHTML =
    (S.dropped ? `<div class="note warn"><b>${S.dropped}</b> item${S.dropped === 1 ? " wasn't" : "s weren't"} exported: ${S.dropped === 1 ? "it has" : "they have"} no coordinates. ${S.written} of ${S.expected} were written.</div>` : "") +
    (S.long_notes ? `<div class="note warn">${esc(longNoteWarning())}</div>` : "") +
    (S.long_names ? `<div class="note warn">${esc(longNameWarning())}</div>` : "") +
    (S.long_folders ? `<div class="note warn">${esc(longFolderWarning())}</div>` : "") +
    (S.over_limit ? `<div class="note warn">onX accounts hold at most ${S.limit.toLocaleString("en-US")} markups; this map has ${S.markups.toLocaleString("en-US")}. Remove or exclude some before importing.</div>` : "");
  // Two folders may share a name ("Camp" twice, from the file), or two names
  // sanitize alike ("A B", "A_B"): only then does a box show its number, and
  // its file chips their NN_ folder, as its download is named.
  const tally = f => MANIFEST.reduce((m, e) => m.set(f(e), (m.get(f(e)) || 0) + 1), new Map());
  const byName = tally(e => nameKey(e.folder)), bySafe = tally(e => e.safe.toLowerCase());
  MANIFEST.forEach(e => {
    const twin = byName.get(nameKey(e.folder)) > 1;
    const fileTwin = bySafe.get(e.safe.toLowerCase()) > 1;
    const num = e.dir.split("_")[0];
    // The visible label is just "Download"; its accessible name says which
    // folder (and, for a twin, its number), so every one is distinct.
    const label = `Download ${twin ? num + " · " : ""}${e.folder}`;
    const d = document.createElement("section");
    d.className = "rb-step";
    d.innerHTML = `
      <div class="rb-head">
        <h2 class="rb-title">${twin ? `<span class="rb-num">${esc(num)} ·</span>` : ""}<span class="rb-name" title="${esc(e.folder)}">${esc(e.folder)}</span></h2>
        <button type="button" class="btn rb-dl" aria-label="${esc(label)}">Download</button>
      </div>
      <div class="rb-files">${e.files.map(f =>
        `<span class="rb-file">${esc(fileTwin ? f.path : f.path.split("/").pop())}</span>`).join("")}</div>`;
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
    setStatus("Download failed: " + humanError(err), "err"); console.error(err);
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
   an onX id) with any other fill, a clear one excepted, would change, so say so once
   on load and offer to leave them out of the export. */
let ONX_DEFAULT_FILL = null;           // bridge.ColorMapper.DEFAULT_AREA_FILL, read at boot
const fillChanges = i => i.kind === "shapes" && !!i.onx_id && !!i.fill && i.fill !== ONX_DEFAULT_FILL
  && fillAlpha(i.fill) > 0;   // a clear fill is deliberate (UI-30): not flagged
function fillLossItems() {
  return allItems().filter(fillChanges);
}
function warnFillLoss() {
  const hit = fillLossItems();
  const n = hit.length;
  if (!n) return;
  openConfirm({
    title: n === 1 ? "1 area will lose its fill" : `${n} areas will lose their fill`,
    body: "onX resets area fills to blue on import.",
    buttons: [
      { label: n === 1 ? "Keep it" : "Keep them", initial: true, cancel: true, run: () => closeConfirm() },
      { label: n === 1 ? "Leave this out" : `Leave these ${n} out`, run: () => {
          closeConfirm();
          hit.forEach(it => edit(it, { included: false }, { render: false }));
          refreshAfterEdit();
        } },
    ],
  });
}

/** Whether Save in the open note editor would change its note (noteToSave). */
function noteIsChanged() {
  if (!NOTE_EDIT || !DATA) return false;
  const it = allItems().find(i => i.uid === NOTE_EDIT.uid);
  return !!it && noteToSave(it, NOTE_EDIT.draft) !== null;
}

function resetAll({ history: stepBack = true } = {}) {
  // Start over steps history back to the drop entry, so Back from there
  // leaves the site; a Leave from the browser's Back is already there.
  const depth = STAGE_DEPTH[document.body.dataset.stage] || 0;
  closePop(); closeBulk(); resetFolderState();
  $("#runbook").replaceChildren();
  DATA = null; EDITS = {}; SEL.clear(); ANCHOR = null; ZIP = null; MANIFEST = null; NOTE_EDIT = null;
  SORT.clear(); hideTip();
  resetFilters();
  $("#file").value = "";
  showStage("drop");
  setStatus("");
  window.__cairnLoaded = false; window.__cairnExported = false;
  if (stepBack) stepHistory(-depth);
}

/** What Start over compares with: each item's folder, each folder's name and
    each item's edits, as loaded or as the last export wrote them. The edits
    are kept as JSON (edit() changes EDITS' objects in place). */
function savedState() {
  return { home: homeOf(), names: new Map(DATA.groups.map(g => [g.key, g.name])),
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
    // An empty folder made since then: no item says so.
    if (!SAVED.names.has(g.key) && !g.items.length) empties++;
  });
  // An empty folder of then that was removed.
  SAVED.empty.forEach(k => { if (!groupByKey(k)) empties++; });
  return uids.size + renamed + empties;
}

function requestStartOver() {
  if (BULK) return;                // behind the several-items dialog: not reachable
  const ret = document.activeElement;
  flushDeferred();                 // a name just left: its rename, or its merge offer, first
  if (CONFIRM) return;
  openConfirm({
    title: "Start over?",
    // No count, as in "Leave this map?" (owner, 2026-10-25: keep it simple).
    body: unexportedChanges() ? "Changes will be lost." : "This clears the current map.",
    ret,
    buttons: [
      { label: "Cancel", initial: true, cancel: true, run: () => closeConfirm() },
      { label: "Start over", cls: "danger", run: () => { closeConfirm(false); resetAll(); } },
    ],
  });
}

function requestExport() {
  if (BULK) return;                // behind the several-items dialog: not reachable
  const ret = document.activeElement;
  // A folder name left by clicking Export: its rename happened, its render
  // (and a taken name's merge offer) is waiting. Show it here, on the edit
  // screen, and don't export the old name.
  if (RENAME) finishRename(RENAME.key, true);
  flushDeferred();
  if (CONFIRM) return;
  // In order: a taken folder name's merge offer (above: it stops the export,
  // as before), then "Save your note?", then the items that need a name (N1),
  // then the export.
  const go = () => exportOrAskForNames(ret);
  if (!NOTE_EDIT) { go(); return; }
  const it = allItems().find(i => i.uid === NOTE_EDIT.uid);
  if (!noteIsChanged()) { closeNote(it, false); go(); return; }
  askToSaveNote(go, ret);
}

/** A name is required to export (N1, owner 2026-10-25): onX would make one up
    ("Imported waypoint markup <timestamp>"). With blank-named items to write,
    ask first. Name them Untitled names each one "Untitled", as an ordinary
    edit (an unexported change until this export writes it), then exports;
    Cancel says how many and goes to the first one. */
function exportOrAskForNames(ret) {
  const blank = allItems().filter(needsName);
  if (!blank.length) { doExport(); return; }
  const n = blank.length;
  openConfirm({
    title: n === 1 ? "1 item needs a name" : `${plural(n, "item")} need a name`,
    body: "",
    ret,
    buttons: [
      { label: "Cancel", initial: true, cancel: true, run: () => { closeConfirm(false); showBlankNames(blank); } },
      { label: "Name them Untitled", run: () => {
          closeConfirm(false);
          blank.forEach(it => edit(it, { name: "Untitled" }, { render: false }));
          refreshAfterEdit();
          doExport();
        } },
    ],
  });
}

/** After Cancel: the status says how many need a name, and focus goes to the
    first such name field on screen. When a filter or a collapsed folder hides
    every one, the filters are cleared and the first one's folder opened. */
function showBlankNames(blank) {
  const uids = new Set(blank.map(i => i.uid));
  const onScreen = () => [...document.querySelectorAll("#folders tr[data-uid] .name-in")]
    .find(el => uids.has(el.closest("tr").dataset.uid) && el.getClientRects().length);
  let field = onScreen();
  if (!field) {
    const first = blank[0];
    const g = DATA.groups.find(g => g.items.includes(first));
    if (!shownItems().includes(first)) resetFilters();
    if (g) COLLAPSED.delete(g.key);
    renderRail(); renderFolders();
    field = onScreen();
  }
  const n = blank.length;
  setStatus(n === 1 ? "1 item needs a name." : `${plural(n, "item")} need a name.`, "err");
  if (field) {
    field.focus({ preventScroll: true });
    field.scrollIntoView({ block: "nearest" });
  }
}

/** The open note has unsaved changes and something needs it closed (Export,
    Rename\u2026, Change note\u2026): "Save your note?" (UI-22). Save or Discard closes
    it and then runs go; Keep editing goes back to it. Safe choice first, the
    action last (Save, the default). */
function askToSaveNote(go, ret) {
  const uid = NOTE_EDIT.uid;
  const it = allItems().find(i => i.uid === uid);
  openConfirm({
    title: "Save your note?",
    body: `Your note for \u201c${it.name || "Untitled"}\u201d hasn't been saved.`,
    ret,
    buttons: [
      { label: "Keep editing", cancel: true, run: () => {
          closeConfirm(false);
          const ta = document.querySelector(`tr[data-uid="${CSS.escape(uid)}"] .desc-in`);
          if (ta) ta.focus({ preventScroll: true });
        } },
      { label: "Discard", run: () => { closeConfirm(false); closeNote(it, false); go(); } },
      { label: "Save", cls: "primary", initial: true, run: () => { closeConfirm(false); closeNote(it, true); go(); } },
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
  // The menu's arrow keys (role=menu): Down / Up move through its items,
  // wrapping; Home and End jump to its ends, as in the Move to… list. Esc
  // and Tab keep their own handling.
  $("#more-menu").onkeydown = e => {
    const items = [...$("#more-menu").querySelectorAll("[role=menuitem]:not([disabled])")];
    if (!items.length) return;
    const i = items.indexOf(document.activeElement);
    const go = j => { e.preventDefault(); items[(j + items.length) % items.length].focus(); };
    if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i < 0 ? -1 : i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(-1);
  };
  const menuAct = (id, fn) => $(id).onclick = () => { closeMenu(); fn(); };
  menuAct("#bulk-move", openMoveTo);
  menuAct("#bulk-rename", openRename);
  menuAct("#bulk-note", openChangeNote);
  wireRowDrag();
  wirePointerHeld();
  wireTip();
  // The note cleaned as a name (CairnRename.cleanName, the rule of every name
  // edit): its lines joined by a space, trimmed. A note of only spaces and line
  // breaks would blank the name: that row is left alone (2026-10-25), as is
  // one whose name is that already.
  menuAct("#bulk-desc", () => bulk(it => {
    const n = CairnRename.cleanName(it.desc || "");
    return n && n !== it.name ? { name: n } : {};
  }));
  menuAct("#bulk-exclude", () => bulk({ included: false }));
  menuAct("#bulk-include", () => bulk({ included: true }));
  // Every nav's Help (top bar, search row, footer) opens the dialog here.
  document.querySelectorAll(".help-open").forEach(b => b.onclick = openHelp);
  // faq.html / walkthrough.html link here as "./#help".
  if (location.hash === "#help") openHelp();
  $("#help-close").onclick = closeHelp;
  $("#help").addEventListener("click", e => { if (e.target === $("#help")) closeHelp(); });
  $("#mark-modal").addEventListener("click", e => { if (e.target === $("#mark-modal")) closeBulk(); });
  // Clicks inside the popover stay there: its icon grid re-renders under the
  // pointer, so the document-level "outside click" test can't be trusted.
  $("#mark-pop").addEventListener("click", e => e.stopPropagation());
  $("#bulk-icon").onclick = openBulk;
  $("#export").onclick = requestExport;
  // Back (done -> edit) is the browser's Back too: history steps with it.
  $("#back").onclick = () => { showStage("edit"); setStatus(""); stepHistory(-1); };
  history.replaceState({ cairn: "drop" }, "");
  addEventListener("popstate", onPopState);
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
