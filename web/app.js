/* Cairn web app — UI shell.
   All map logic is the existing Python engine, running in Pyodide. */
let py = null, DATA = null, EDITS = {}, SEL = new Set(), ZIP = null, MANIFEST = null;
let ANCHOR = null;   // last row clicked without shift -- the pivot for range select

/* Every filter lives here; the rail facets, the chips, the type buttons and
   #only-attention all render FROM this object, and visibleItems() reads only
   it -- so select-all and shift-range automatically respect every filter. */
const FILTERS = { q: "", kind: "", folder: null, icons: new Set(), attention: false };
const DEFAULT_PIN = "\u0000default";   // facet key for "fell back to the default pin"
const COLLAPSED = new Set();           // folder sections the user folded away
let NOTE_EDIT = null;                  // {uid, draft} -- the one note open for editing
let POP = null;                        // single-item icon & color popover state
let BULK = null;                       // several-items dialog state

const $ = s => document.querySelector(s);
const setStatus = (t, cls = "") => { const e = $("#status"); e.textContent = t; e.className = "status " + cls; };

async function boot() {
  try {
    setStatus("Loading Python runtime…");
    py = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/" });
    setStatus("Loading map engine…");
    await py.loadPackage("micropip");
    const micropip = py.pyimport("micropip");
    // Pinned; resolves from the Pyodide lockfile on jsdelivr, not PyPI.
    await micropip.install("pyyaml==6.0.2");
    // deps:false -- the engine needs only pyyaml (installed above), and with
    // the CLI gone that is all it declares. Kept anyway so a future dependency
    // can never make the browser silently fetch from PyPI (the CSP blocks it).
    // callKwargs is load-bearing: a plain JS object argument is NOT keyword
    // args to a Python function -- it lands as the second positional
    // (keep_going), silently leaving deps=True. Caught by
    // test_page_boots_under_enforced_csp when the CSP blocked pypi.org.
    // The URL is built against document.baseURI, not location.origin, so the
    // app works served from a subpath (e.g. quietmarch.to/cairn/).
    const wheel = new URL("dist/cairn_maps-1.0.0-py3-none-any.whl", document.baseURI).href;
    await micropip.install.callKwargs(wheel, { deps: false });
    const bridge = await (await fetch("bridge.py")).text();
    py.FS.writeFile("/bridge.py", bridge);
    // Carry the user's symbol mappings into the sandbox. Without this the
    // engine falls back to built-in defaults only, and the browser produces
    // different icons than the CLI for the same map.
    try {
      const cfg = await fetch("cairn_config.yaml");
      if (cfg.ok) py.FS.writeFile("/cairn_config.yaml", await cfg.text());
    } catch (_) { /* defaults are a fine fallback */ }
    await py.runPythonAsync("import sys; sys.path.insert(0,'/'); import bridge");
    const v = py.runPython("import cairn; cairn.__version__");
    setStatus(`Ready · engine v${v}`, "ready");
    $("#pick").disabled = false;
    window.__cairnReady = true;
  } catch (e) {
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
  fi.onchange = () => fi.files[0] && handleFile(fi.files[0]);
  ["dragenter", "dragover"].forEach(ev => dz.addEventListener(ev, e => {
    e.preventDefault(); dz.classList.add("over");
  }));
  ["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => {
    e.preventDefault(); dz.classList.remove("over");
  }));
  dz.addEventListener("drop", e => {
    const f = e.dataTransfer.files[0]; if (f) handleFile(f);
  });
}

async function handleFile(file) {
  setStatus("Reading " + file.name + "…");
  try {
    const text = await file.text();
    // Data crosses into Python via globals, never by interpolating user
    // content into Python source — JSON escaping happening to be valid
    // Python-literal escaping is not a contract worth betting on.
    py.globals.set("_cairn_text", text);
    py.globals.set("_cairn_fname", file.name);
    const raw = py.runPython("bridge.load_document(_cairn_text, _cairn_fname)");
    DATA = JSON.parse(raw); EDITS = {}; SEL.clear(); ANCHOR = null;
    resetFilters(); COLLAPSED.clear(); NOTE_EDIT = null; closePop(); closeBulk();
    $("#map-title").textContent = mapTitle(DATA);
    // "Areas" only when the map has any.
    const hasAreas = allItems().some(i => i.kind === "shapes");
    $('#type-filter [data-kind="shapes"]').classList.toggle("hidden", !hasAreas);
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

/** The CalTopo map's title. The engine doesn't hand one over, and a CalTopo
    GeoJSON export carries none; its download filename does, with spaces and
    brackets turned into underscores ("Bitterroots__Complete_.json" for
    "Bitterroots (Complete)"). Undo that. */
function mapTitle(data) {
  if (data.title || data.map_title) return data.title || data.map_title;
  let s = String(data.filename || "").replace(/\.(geo)?json$/i, "");
  s = s.replace(/__([^_]+(?:_[^_]+)*)_$/, " ($1)").replace(/_/g, " ").replace(/\s+/g, " ").trim();
  return s || "Untitled map";
}

/* ---------- filters ---------- */
function resetFilters() {
  FILTERS.q = ""; FILTERS.kind = ""; FILTERS.folder = null;
  FILTERS.icons.clear(); FILTERS.attention = false;
  $("#filter").value = "";
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

function setKind(kind) {
  FILTERS.kind = kind;
  document.querySelectorAll("#type-filter button").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.kind === kind)));
  renderFolders();
}

/* ---------- edit stage ---------- */
function renderEdit() {
  renderRail();
  renderFolders();
}

function renderRail() {
  // Folders: "All" first, then each folder with its item count.
  const fl = $("#folder-facets"); fl.innerHTML = "";
  const facetBtn = (label, count, key, italic) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "facet-btn" + (italic ? " unorg" : "");
    b.setAttribute("aria-pressed", String(FILTERS.folder === key));
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
    lab.innerHTML = `<input type="checkbox"${def ? ' id="only-attention"' : ""} data-icon="${esc(k)}">` +
      glyphSVG(def ? "Location" : k) + `<span>${def ? "Default pin" : esc(k)}</span>`;
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
}

function renderChips() {
  const host = $("#chips"); host.innerHTML = "";
  const chips = [];
  if (FILTERS.q) chips.push([`Search: “${FILTERS.q}”`, () => { FILTERS.q = ""; $("#filter").value = ""; }]);
  if (FILTERS.kind) chips.push([`Type: ${$(`#type-filter [data-kind="${FILTERS.kind}"]`).textContent}`, () => setKind("")]);
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
  clear.type = "button"; clear.className = "linkbtn"; clear.textContent = "Clear filters";
  clear.onclick = () => { resetFilters(); setKind(""); renderRail(); renderFolders(); };
  host.appendChild(clear);
}

function renderFolders() {
  // Selection always follows what's on screen -- if a filter change hides a
  // selected row, it drops out of the selection rather than staying an
  // invisible target for the next bulk edit.
  const shownUids = new Set(shownItems().map(i => i.uid));
  for (const uid of SEL) if (!shownUids.has(uid)) SEL.delete(uid);
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
        <button type="button" class="collapse" aria-expanded="${!collapsed}" aria-label="${collapsed ? "Expand" : "Collapse"} ${esc(g.name)}">${UI_ICON.chevron}</button>
      </div>
      <div class="table-wrap${collapsed ? " hidden" : ""}"><table>
        <colgroup><col class="c-sel"><col class="c-name"><col class="c-note"><col class="c-icon"></colgroup>
        <thead><tr>
          <th class="selcol"><input type="checkbox" class="folder-all" aria-label="Select all shown in ${esc(g.name)}" title="Select every row shown in this folder"></th>
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
}

const colorList = () => DATA.line_colors || DATA.colors;
const colorOf = rgba => colorList().find(c => c.rgba === rgba) || DATA.colors.find(c => c.rgba === rgba);
const colorName = rgba => (colorOf(rgba) || { name: "—" }).name;
const kindWord = k => k === "shapes" ? "Area" : "Line";
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
  tr.innerHTML = `
    <td class="selcol"><input type="checkbox" class="sel-box" aria-label="Select ${esc(it.name)}" ${SEL.has(it.uid) ? "checked" : ""}></td>
    <td class="namecol"><input class="name-in" aria-label="Name" value="${esc(it.name)}">${it.included ? ""
      : `<span class="exc-label">Excluded</span><button type="button" class="exc-chip" title="This row will not be exported. Click to put it back.">Include</button>`}</td>
    <td class="notecol">${noteOpen ? noteEditor(it) :
      `<button type="button" class="note-btn" aria-label="Open note for ${esc(it.name)}" title="Becomes the markup's Notes in onX">
        <span class="note-text${it.desc ? "" : " empty"}">${esc(oneLine(it.desc) || "Add a note")}</span>${UI_ICON.pencil}</button>`}</td>
    <td class="iconcol">${isWp
      ? `<button type="button" class="icon-btn" title="${esc(it.why)}" aria-label="${esc(iconLabel)}, ${esc(cname)}. Change icon or color">${markerSVG(it.icon, it.hex)}${it.needs_attention
          ? `<span class="whymark" title="${esc(it.why)}">Default pin</span>` : `<span class="icon-name">${esc(it.icon)}</span>`}</button>`
      : `<button type="button" class="line-btn" title="${esc(cname)} — ${esc(it.why)}" aria-label="${kindWord(it.kind)}, ${esc(cname)}. Change color">${lineSVG(it.hex, it.kind)}<span class="icon-name kind">${kindWord(it.kind)}</span></button>`}</td>`;
  const selBox = tr.querySelector(".sel-box");
  selBox.onclick = e => {
    if (e.shiftKey && ANCHOR && ANCHOR !== it.uid) {
      // Range-select between the anchor and this row, in the order rows are
      // currently displayed -- so it follows the active filter and sort rather
      // than the underlying file order.
      e.preventDefault();
      const order = shownItems().map(i => i.uid);
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
    edit(it, { [key]: v });
  });
}

/* ---------- notes: inline multi-line editor ---------- */
function noteEditor(it) {
  const id = "note-" + it.uid.replace(/[^\w-]/g, "_");
  return `<div class="note-ed">
    <label class="label" for="${id}">Note</label>
    <textarea id="${id}" class="desc-in" rows="5">${esc(NOTE_EDIT.draft)}</textarea>
    <div class="note-actions">
      <button type="button" class="btn primary small note-apply">Apply</button>
      <button type="button" class="btn small note-cancel">Cancel</button>
      <span class="hint">Line breaks kept</span>
    </div></div>`;
}

function openNote(it) {
  NOTE_EDIT = { uid: it.uid, draft: it.desc || "" };
  renderFolders();
  const ta = document.querySelector(`tr[data-uid="${CSS.escape(it.uid)}"] .desc-in`);
  if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
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
const selectedItems = () => allItems().filter(i => SEL.has(i.uid));

function setSelectAll(on) {
  const shown = shownItems();
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
const NEUTRAL_HEX = "#FF0000";

function paletteHTML(colors, current) {
  return colors.map(c => `<button type="button" class="swatch-btn" data-rgba="${esc(c.rgba)}" aria-label="${esc(c.name)}" title="${esc(c.name)}" aria-pressed="${c.rgba === current}" style="background:${esc(c.hex)}"></button>`).join("");
}
function iconMatches(q) {
  const s = q.trim().toLowerCase();
  return DATA.icons.filter(n => !s || n.toLowerCase().includes(s));
}

/* ---------- single item: popover anchored to the marker ---------- */
function openPop(it, anchor) {
  closeMenu(); closeBulk();
  POP = { uid: it.uid, color: it.color, icon: it.icon, iconPicked: false, q: "", anchor };
  const isWp = it.kind === "waypoints";
  const pop = $("#mark-pop");
  pop.setAttribute("aria-label", `Change ${isWp ? "icon and color" : "color"} for ${it.name}`);
  pop.innerHTML = `
    <div class="pop-head">
      <svg class="contours" viewBox="0 0 600 110" preserveAspectRatio="none" fill="none" stroke="#DCCFB2" stroke-width="1" aria-hidden="true">
        <path d="M-10 95 C 120 60, 220 110, 340 75 S 520 40, 610 60"/>
        <path d="M-10 70 C 130 35, 230 85, 350 50 S 530 15, 610 35"/>
        <path d="M-10 45 C 140 10, 240 60, 360 25 S 540 -10, 610 10"/></svg>
      <span class="pop-preview"></span>
      <div class="pop-title"><span class="pop-name">${esc(it.name || "Untitled")}</span><span class="pop-desc"></span></div>
    </div>
    <div class="pop-sec">
      <span class="label">Color</span>
      <div class="palette">${paletteHTML(paletteFor([it]), POP.color)}</div>
    </div>
    ${isWp ? `<div class="pop-sec icons">
      <div class="sec-row"><span class="label">Icon</span><span class="sec-count">${DATA.icons.length} icons</span></div>
      <input type="search" class="icon-search" aria-label="Find an icon" placeholder="${document.documentElement.clientWidth < 640 ? "Find an icon" : "Find an icon — try “climb”, “water”, “camp”"}" autocomplete="off">
      <div class="icon-grid" role="group" aria-label="Icons"></div>
    </div>` : `<p class="pop-hint">Lines take the color only.</p>`}
    <div class="pop-foot">
      <button type="button" class="btn pop-cancel">Cancel</button>
      <button type="button" id="pop-apply" class="btn primary pop-apply">Apply</button>
    </div>`;
  pop.querySelectorAll(".swatch-btn").forEach(b => b.onclick = () => {
    POP.color = b.dataset.rgba; drawPop();
  });
  if (isWp) {
    const s = pop.querySelector(".icon-search");
    s.oninput = () => { POP.q = s.value; drawPopGrid(); };
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

function drawPop() {
  const it = popItem(); if (!it) return;
  const pop = $("#mark-pop");
  const hex = (colorOf(POP.color) || {}).hex || it.hex;
  const isWp = it.kind === "waypoints";
  const showIcon = isWp && (POP.iconPicked || !it.needs_attention) ? POP.icon : "Default pin";
  pop.querySelector(".pop-preview").innerHTML = isWp ? markerSVG(POP.icon, hex, 52, 64) : lineSVG(hex, it.kind, 52, 44);
  pop.querySelector(".pop-desc").textContent = `${isWp ? showIcon : kindWord(it.kind)} · ${colorName(POP.color)}`;
  pop.querySelectorAll(".swatch-btn").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.rgba === POP.color)));
  if (isWp) drawPopGrid();
}

function drawPopGrid() {
  const it = popItem(); if (!it) return;
  const grid = $("#mark-pop .icon-grid"); if (!grid) return;
  const hex = (colorOf(POP.color) || {}).hex || it.hex;
  const top = grid.scrollTop;
  const list = iconMatches(POP.q);
  grid.innerHTML = list.length ? list.map(n =>
    `<button type="button" class="icon-pick" data-icon="${esc(n)}" aria-pressed="${n === POP.icon}">${markerSVG(n, hex, 28, 35)}<span>${esc(n)}</span></button>`).join("")
    : `<span class="grid-empty">No icon matches “${esc(POP.q)}”.</span>`;
  grid.scrollTop = top;
  grid.querySelectorAll(".icon-pick").forEach(b => b.onclick = () => {
    POP.icon = b.dataset.icon; POP.iconPicked = true; drawPop();
  });
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
  closeMenu(); closePop();
  BULK = { uids: items.map(i => i.uid), color: null, icon: null, q: "" };
  const hasWp = items.some(i => i.kind === "waypoints");
  const hasLines = items.some(i => i.kind !== "waypoints");
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
      <div class="icon-grid compact" role="group" aria-label="Icons"></div>
      ${hasLines ? `<span class="hint">Lines take the color only.</span>` : ""}
    </div>` : `<div class="pop-sec"><span class="hint">Lines take the color only.</span></div>`}
    <div class="pop-foot">
      <button type="button" class="btn bulk-cancel">Cancel</button>
      <button type="button" id="bulk-apply" class="btn primary">Apply</button>
    </div>`;
  d.querySelector(".color-reset").onclick = () => { BULK.color = null; drawBulk(); };
  d.querySelectorAll(".swatch-btn").forEach(b => b.onclick = () => { BULK.color = b.dataset.rgba; drawBulk(); });
  if (hasWp) {
    d.querySelector(".icon-reset").onclick = () => { BULK.icon = null; drawBulk(); };
    const s = d.querySelector(".icon-search");
    s.oninput = () => { BULK.q = s.value; drawBulkGrid(); };
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
  const items = allItems().filter(i => BULK.uids.includes(i.uid));
  const hexOf = rgba => (colorOf(rgba) || {}).hex;
  d.querySelector(".na-rows").innerHTML = items.map(it => {
    const isWp = it.kind === "waypoints";
    const toColor = BULK.color || it.color;
    const toIcon = isWp ? (BULK.icon || it.icon) : null;
    const nowMark = isWp ? markerSVG(it.icon, it.hex, 22, 28) : lineSVG(it.hex, it.kind, 22, 20);
    const afterMark = isWp ? markerSVG(toIcon, hexOf(toColor) || it.hex, 22, 28) : lineSVG(hexOf(toColor) || it.hex, it.kind, 22, 20);
    const afterIcon = isWp ? (BULK.icon || (it.needs_attention ? "Default pin" : it.icon)) : kindWord(it.kind);
    return `<span class="na-cell">${nowMark}<span class="na-name">${esc(it.name || "Untitled")}</span></span>${UI_ICON.arrow}` +
      `<span class="na-cell">${afterMark}<span class="na-after">${esc(afterIcon)} · ${esc(colorName(toColor))}</span></span>`;
  }).join("");
  d.querySelector(".color-reset").setAttribute("aria-pressed", String(!BULK.color));
  d.querySelectorAll(".swatch-btn").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.rgba === BULK.color)));
  const ir = d.querySelector(".icon-reset");
  if (ir) ir.setAttribute("aria-pressed", String(!BULK.icon));
  drawBulkGrid();
}

function drawBulkGrid() {
  const grid = $("#mark-dialog .icon-grid"); if (!grid) return;
  const hex = (BULK.color && (colorOf(BULK.color) || {}).hex) || NEUTRAL_HEX;
  const top = grid.scrollTop;
  const list = iconMatches(BULK.q);
  grid.innerHTML = list.length ? list.map(n =>
    `<button type="button" class="icon-pick" data-icon="${esc(n)}" title="${esc(n)}" aria-label="${esc(n)}" aria-pressed="${n === BULK.icon}">${markerSVG(n, hex, 24, 30)}</button>`).join("")
    : `<span class="grid-empty">No icon matches “${esc(BULK.q)}”.</span>`;
  grid.scrollTop = top;
  grid.querySelectorAll(".icon-pick").forEach(b => b.onclick = () => { BULK.icon = b.dataset.icon; drawBulk(); });
}

function applyBulk() {
  const { color, icon, uids } = BULK;
  const items = allItems().filter(i => uids.includes(i.uid));
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

function closeBulk() {
  if (!BULK) return;
  BULK = null;
  $("#mark-modal").classList.add("hidden");
  $("#mark-dialog").innerHTML = "";
  if (!$("#bulk-icon").disabled) $("#bulk-icon").focus({ preventScroll: true });
}

/* ---------- More menu ---------- */
function closeMenu() {
  $("#more-menu").classList.add("hidden");
  $("#more-btn").setAttribute("aria-expanded", "false");
}

/* ---------- export ---------- */
async function doExport() {
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
  const total = MANIFEST.reduce((n, e) => n + e.count, 0);
  const kml = MANIFEST.filter(e => e.files.some(f => f.kml)).length;
  const host = $("#runbook");
  host.innerHTML =
    `<div class="note">onX Premium or Elite is required to import.${kml
      ? ` <b>${kml}</b> of these batches contain a KML file, which the phone app can't import — use the Web Map on a computer.`
      : ""}</div>` +
    (total > 1500 ? `<div class="note warn">This map has ${total} markups; an onX account holds 1,500.</div>` : "");
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

const openHelp = () => $("#help").classList.remove("hidden");
const closeHelp = () => $("#help").classList.add("hidden");

/* ---------- wire ---------- */
window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-ui-icon]").forEach(el => {
    el.insertAdjacentHTML("beforeend", UI_ICON[el.dataset.uiIcon] || "");
  });
  wireDrop();
  $("#filter").oninput = e => { FILTERS.q = e.target.value; renderFolders(); };
  document.querySelectorAll("#type-filter button").forEach(b => b.onclick = () => setKind(b.dataset.kind));
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
  document.querySelectorAll(".help-link").forEach(b => b.onclick = openHelp);
  $("#help-close").onclick = closeHelp;
  $("#help").addEventListener("click", e => { if (e.target === $("#help")) closeHelp(); });
  $("#mark-modal").addEventListener("click", e => { if (e.target === $("#mark-modal")) closeBulk(); });
  // Clicks inside the popover stay there: its icon grid re-renders under the
  // pointer, so the document-level "outside click" test can't be trusted.
  $("#mark-pop").addEventListener("click", e => e.stopPropagation());
  $("#bulk-icon").onclick = openBulk;
  $("#export").onclick = doExport;
  $("#back").onclick = () => showStage("edit");
  document.querySelectorAll(".newmap").forEach(b => b.onclick = () => {
    closePop(); closeBulk();
    DATA = null; EDITS = {}; SEL.clear(); ANCHOR = null; ZIP = null; MANIFEST = null; NOTE_EDIT = null;
    resetFilters();
    $("#file").value = "";
    showStage("drop");
    setStatus("Ready", "ready");
    window.__cairnLoaded = false; window.__cairnExported = false;
  });
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
    if (e.key === "Escape") {
      // Priority: close what's in front, then an open note, then let a focused
      // field revert its own edit, else clear the selection.
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
      setSelectAll(!(SEL.size && SEL.size === shownItems().length));
    }
  });
  boot();
});
