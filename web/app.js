/* Cairn web prototype — UI shell.
   All map logic is the existing Python engine, running in Pyodide. */
let py = null, DATA = null, EDITS = {}, SEL = new Set(), ZIP = null, MANIFEST = null;
let ANCHOR = null;   // last row clicked without shift -- the pivot for range select
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
    // deps:false -- the engine needs only pyyaml (installed above). Letting
    // micropip resolve the declared dependencies drags in typer, rich, textual
    // and pygments (~2.6 MB) from PyPI that never execute in the browser.
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
    DATA = JSON.parse(raw); EDITS = {}; SEL.clear();
    renderEdit();
    $("#drop-stage").classList.add("hidden");
    $("#edit-stage").classList.remove("hidden");
    setStatus(`Loaded ${file.name}`, "ready");
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

/* ---------- edit stage ---------- */
function renderEdit() {
  const t = DATA.totals;
  $("#summary").innerHTML = `
    <div class="stat"><b>${t.folders}</b><span>Folders</span></div>
    <div class="stat"><b>${t.items}</b><span>Markups</span></div>
    <div class="stat"><b>${t.folders}</b><span>onX imports</span></div>
    ${t.attention ? `<div class="stat warn" title="These waypoints fell back to onX's default pin, because your CalTopo symbol had no onX equivalent and nothing in the name matched. That is fine for generic markers like mile splits \u2014 set an icon only where the meaning matters."><b>${t.attention}</b><span>Using default pin</span></div>` : ""}`;
  renderFolders();
}

function visibleItems(g) {
  const q = ($("#filter").value || "").toLowerCase();
  const only = $("#only-attention").checked;
  const kind = $("#type-filter").value;
  return g.items.filter(i =>
    (!q || i.name.toLowerCase().includes(q) || (i.desc || "").toLowerCase().includes(q)) &&
    (!only || i.needs_attention) &&
    (!kind || i.kind === kind));
}

function renderFolders() {
  // Selection always follows what's on screen -- if a filter change hides a
  // selected row, it drops out of the selection rather than staying an
  // invisible target for the next bulk edit.
  const shownUids = new Set(shownItems().map(i => i.uid));
  for (const uid of SEL) if (!shownUids.has(uid)) SEL.delete(uid);

  const host = $("#folders"); host.innerHTML = "";
  DATA.groups.forEach((g, gi) => {
    const items = visibleItems(g);
    if (!items.length) return;
    const att = items.filter(i => i.needs_attention).length;
    const el = document.createElement("div");
    el.className = "folder";
    el.innerHTML = `
      <div class="folder-head" data-g="${gi}">
        <span class="caret">▾</span><h3>${esc(g.name)}</h3>
        <span class="pill">${items.length} items</span>
        ${att ? `<span class="pill warn" title="${att} of these fell back to onX's default pin. Hover any icon to see why.">${att} default pin</span>` : ""}
      </div>
      <table><thead><tr>
        <th style="width:34px" class="selcol">
          <input type="checkbox" class="folder-all" title="Select every row in this folder">
        </th>
        <th>Name</th>
        <th style="width:26%">Description <span class="th-note">→ onX Notes</span></th>
        <th style="width:54px">Type</th>
        <th style="width:180px">onX icon</th><th style="width:132px">Color</th>
      </tr></thead><tbody></tbody></table>`;
    const tb = el.querySelector("tbody");
    items.forEach(it => tb.appendChild(row(it)));
    const fbox = el.querySelector(".folder-all");
    const nsel = items.filter(i => SEL.has(i.uid)).length;
    fbox.checked = nsel === items.length;
    fbox.indeterminate = nsel > 0 && nsel < items.length;
    fbox.onclick = e => e.stopPropagation();
    fbox.onchange = e => {
      items.forEach(i => e.target.checked ? SEL.add(i.uid) : SEL.delete(i.uid));
      renderFolders();
    };
    el.querySelector(".folder-head").onclick = e => {
      if (e.target.tagName === "INPUT") return;
      const tbl = el.querySelector("table");
      const hid = tbl.classList.toggle("hidden");
      el.querySelector(".caret").textContent = hid ? "▸" : "▾";
    };
    host.appendChild(el);
  });
  if (!host.children.length)
    host.innerHTML = `<div class="note">Nothing matches that filter.</div>`;
  updateSel();
}

function row(it) {
  const tr = document.createElement("tr");
  tr.dataset.uid = it.uid;
  if (it.needs_attention) { tr.classList.add("attention"); tr.title = it.why; }
  if (SEL.has(it.uid)) tr.classList.add("sel");
  const isWp = it.kind === "waypoints";
  if (!it.included) tr.classList.add("excluded");
  tr.innerHTML = `
    <td><input type="checkbox" class="sel-box" ${SEL.has(it.uid) ? "checked" : ""}></td>
    <td><input class="name-in" value="${esc(it.name)}">${it.included ? ""
      : `<button class="exc-chip" title="This row will not be exported. Click to put it back.">excluded · restore</button>`}</td>
    <td><input class="desc-in" placeholder="—" title="Becomes the markup's Notes in onX" value="${esc(it.desc || "")}"></td>
    <td><span class="kindtag">${it.kind === "waypoints" ? "wpt" : it.kind === "tracks" ? "line" : "area"}</span></td>
    <td>${isWp
      ? `<button class="chipbtn icon-btn${it.needs_attention ? " unresolved" : ""}" title="${esc(it.why)}"><span class="glyph">${glyph(it.icon)}</span>${esc(it.icon)}</button>${it.needs_attention ? `<span class="whymark" title="${esc(it.why)}">?</span>` : ""}`
      : `<span class="dim" title="${esc(it.why)}">—</span>`}</td>
    <td><button class="chipbtn color-btn">
          <span class="swatch" style="background:${it.hex}"></span>${colorName(it.color)}
        </button></td>`;
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
  };
  wireTextField(tr.querySelector(".name-in"), it, "name", { required: true });
  wireTextField(tr.querySelector(".desc-in"), it, "desc");
  const chip = tr.querySelector(".exc-chip");
  if (chip) chip.onclick = () => edit(it, { included: true });
  if (isWp) tr.querySelector(".icon-btn").onclick = () => pickIcon([it.uid]);
  tr.querySelector(".color-btn").onclick = () => pickColor([it.uid]);
  return tr;
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

function edit(it, patch) {
  Object.assign(it, patch);
  if (patch.color) it.hex = (DATA.colors.find(c => c.rgba === patch.color) || {}).hex || it.hex;
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
  DATA.totals.attention = DATA.groups.reduce(
    (n, g) => n + g.items.filter(i => i.needs_attention).length, 0);
  DATA.totals.excluded = DATA.groups.reduce(
    (n, g) => n + g.items.filter(i => !i.included).length, 0);
  renderEdit();
}

function allItems() { return DATA.groups.flatMap(g => g.items); }

/** Items currently on screen, i.e. passing the name filter and attention toggle.
    Select-all deliberately operates on THESE, not on everything in the file --
    "select all" after filtering to `water` should select the water, not 177 items. */
function shownItems() { return DATA.groups.flatMap(g => visibleItems(g)); }

function setSelectAll(on) {
  const shown = shownItems();
  shown.forEach(i => on ? SEL.add(i.uid) : SEL.delete(i.uid));
  if (!on) ANCHOR = null;
  renderFolders();
}

function syncSelectAllBox() { /* per-folder boxes are set during render */ }
function bulk(patch) {
  const items = allItems().filter(i => SEL.has(i.uid));
  items.forEach(it => edit(it, typeof patch === "function" ? patch(it) : patch));
}

function updateSel() {
  const n = SEL.size;
  $("#selcount").textContent = `${n} selected`;
  $("#selcount").classList.toggle("hidden", n === 0);
  $("#clear-sel").classList.toggle("hidden", n === 0);
  const total = DATA ? DATA.totals.items : 0;
  const shownN = DATA ? shownItems().length : 0;
  $("#shown-count").textContent =
    DATA && shownN !== total ? `Showing ${shownN} of ${total}` : "";
  // Set icon/color and Advanced are always visible -- disabled, not hidden,
  // until there's a selection to apply them to.
  ["#bulk-icon", "#bulk-color", "#more-btn"].forEach(sel => {
    const el = $(sel);
    el.disabled = n === 0;
    el.title = n === 0 ? "Select rows first" : "";
  });
  $("#more-menu").classList.add("hidden");
  syncSelectAllBox();
}

/* ---------- pickers ---------- */
function openModal(title, opts, cur, onPick) {
  $("#modal-title").textContent = title;
  $("#modal-filter").value = "";
  const body = $("#modal-body");
  const draw = q => {
    body.innerHTML = "";
    opts.filter(o => !q || o.label.toLowerCase().includes(q.toLowerCase())).forEach(o => {
      const b = document.createElement("div");
      b.className = "opt" + (o.value === cur ? " cur" : "");
      b.innerHTML =
        (o.hex ? `<span class="swatch" style="background:${o.hex}"></span>` : "") +
        (o.glyph ? `<span class="glyph">${o.glyph}</span>` : "") +
        esc(o.label);
      b.onclick = () => { closeModal(); onPick(o.value); };
      body.appendChild(b);
    });
  };
  draw(""); $("#modal-filter").oninput = e => draw(e.target.value);
  $("#modal").classList.remove("hidden"); $("#modal-filter").focus();
}
const closeModal = () => $("#modal").classList.add("hidden");

function pickIcon(uids) {
  const items = allItems().filter(i => uids.includes(i.uid));
  openModal(uids.length > 1 ? `Set icon on ${uids.length} items` : "Choose an onX icon",
    DATA.icons.map(i => ({ label: i, value: i, glyph: glyph(i) })),
    items.length === 1 ? items[0].icon : null,
    v => items.forEach(it => edit(it, { icon: v })));
}
function pickColor(uids) {
  const items = allItems().filter(i => uids.includes(i.uid));
  openModal(uids.length > 1 ? `Set color on ${uids.length} items` : "Choose an onX color",
    DATA.colors.map(c => ({ label: c.name, value: c.rgba, hex: c.hex })),
    items.length === 1 ? items[0].color : null,
    v => items.forEach(it => edit(it, { color: v })));
}
const colorName = rgba => (DATA.colors.find(c => c.rgba === rgba) || { name: "—" }).name;

/* ---------- export ---------- */
async function doExport() {
  setStatus("Building onX files…");
  try {
    py.globals.set("_cairn_edits", JSON.stringify(EDITS));
    py.runPython("bridge.apply_edits(_cairn_edits)");
    const bytes = py.runPython("bridge.export_zip()").toJs();
    ZIP = new Blob([bytes], { type: "application/zip" });
    MANIFEST = JSON.parse(py.runPython("import json; json.dumps(bridge._STATE['manifest'])"));
    renderRunbook();
    $("#edit-stage").classList.add("hidden");
    $("#done-stage").classList.remove("hidden");
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
      <div class="rb-title"><input type="checkbox"> ${e.n}. ${esc(e.folder)}
        <span class="pill">${e.count} markups</span></div>
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

/* ---------- wire ---------- */
window.addEventListener("DOMContentLoaded", () => {
  wireDrop();
  $("#filter").oninput = renderFolders;
  $("#only-attention").onchange = renderFolders;
  $("#type-filter").onchange = renderFolders;
  $("#clear-sel").onclick = () => { SEL.clear(); ANCHOR = null; renderFolders(); };
  $("#more-btn").onclick = e => {
    e.stopPropagation();
    $("#more-menu").classList.toggle("hidden");
  };
  document.addEventListener("click", () => $("#more-menu").classList.add("hidden"));
  $("#more-menu").onclick = e => e.stopPropagation();
  const menuAct = (id, fn) => $(id).onclick = () => {
    $("#more-menu").classList.add("hidden"); fn();
  };
  menuAct("#bulk-desc", () => bulk(it => it.desc ? { name: it.desc } : {}));
  menuAct("#bulk-exclude", () => bulk({ included: false }));
  menuAct("#bulk-include", () => bulk({ included: true }));
  $("#help-btn").onclick = () => $("#help").classList.remove("hidden");
  $("#help-close").onclick = () => $("#help").classList.add("hidden");
  $("#bulk-icon").onclick = () => pickIcon([...SEL]);
  $("#bulk-color").onclick = () => pickColor([...SEL]);
  $("#export").onclick = doExport;
  $("#modal-close").onclick = closeModal;
  $("#back").onclick = () => {
    $("#done-stage").classList.add("hidden"); $("#edit-stage").classList.remove("hidden");
  };
  document.querySelectorAll(".newmap").forEach(b => b.onclick = () => {
    DATA = null; EDITS = {}; SEL.clear(); ZIP = null; MANIFEST = null;
    $("#file").value = "";
    $("#edit-stage").classList.add("hidden");
    $("#done-stage").classList.add("hidden");
    $("#drop-stage").classList.remove("hidden");
    setStatus("Ready", "ready");
    window.__cairnLoaded = false; window.__cairnExported = false;
  });
  $("#download").onclick = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(ZIP); a.download = "onx_ready.zip"; a.click();
  };
  document.addEventListener("keydown", e => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || ""));
    const modalOpen = !$("#modal").classList.contains("hidden") ||
                      !$("#help").classList.contains("hidden");

    if (e.key === "Escape") {
      // Priority: close what's in front, else let a focused field revert its own
      // edit, else clear the selection.
      if (modalOpen) { closeModal(); $("#help").classList.add("hidden"); return; }
      if (typing) return;                       // wireTextField handles the revert
      if (SEL.size) { SEL.clear(); ANCHOR = null; renderFolders(); }
      return;
    }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a" && !typing && DATA) {
      e.preventDefault();
      setSelectAll(!(SEL.size && SEL.size === shownItems().length));
    }
  });
  boot();
});
