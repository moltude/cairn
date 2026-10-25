/* Bulk rename and note change: the one pure transform behind the dialog's
   preview and its Save (UI-39).

   No DOM, no globals read, no side effects. Loaded before app.js by its own
   <script src="rename.js"> tag (the CSP allows only same-origin files) and
   exposed as window.CairnRename. Tests load it on about:blank with
   page.add_script_tag and call it through page.evaluate.

   transform() turns one spec (a mode and its text) into a per-row Now ->
   After list with flags; the dialog's preview and its Save both call it, so
   the preview is what gets stored and exported. Built 2026-10-25. */
(function (root) {
  "use strict";

  /** The characters XML 1.0 forbids: C0 controls other than tab, LF and CR,
      U+FFFE, U+FFFF and lone surrogates (with the u flag the surrogate range
      only matches a lone one, so a paired emoji survives). Exactly the set
      cairn/core/writers.py drops (_XML_INVALID), so the preview and the file
      agree. Nothing else is dropped: ZWSP, BOM, C1 and NBSP are user data. */
  const XML_INVALID = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF\uD800-\uDFFF]/gu;

  /** s without the characters XML 1.0 forbids. */
  const xmlSafe = s => String(s ?? "").replace(XML_INVALID, "");

  /** A note as the export writes it to <desc>: line endings made "\n", outer
      whitespace trimmed (app.js writtenNote, writers.clean_notes for plain notes).
      Python's strip() there also takes U+0085 (NEL), which JS's trim() keeps, so
      an outer NEL goes too: the preview's note is the file's. */
  const writtenNote = s => {
    let t = String(s ?? "").replace(/\r\n?/g, "\n").trim();
    while (t.charCodeAt(0) === 0x85) t = t.slice(1).trim();
    while (t.charCodeAt(t.length - 1) === 0x85) t = t.slice(0, -1).trim();
    return t;
  };

  /** A name as Cairn stores it after a bulk change: XML-safe, every whitespace
      run holding a line break or tab turned into one space, trimmed. Pure
      space runs are left alone ("Camp  A" is user data). May return "": names
      are optional (UI-39). */
  const cleanName = s => xmlSafe(s).replace(/[ \t]*[\r\n\t][ \t\r\n]*/g, " ").trim();

  /** A note as Cairn stores it after a bulk change: XML-safe, then written form. */
  const cleanNote = s => writtenNote(xmlSafe(s));

  /** UTF-8 bytes of s, the measure onX cuts notes by (512). */
  const noteBytes = s => {
    let n = 0;
    for (const ch of String(s ?? "")) {
      const cp = ch.codePointAt(0);
      n += cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4;
    }
    return n;
  };

  /** onX's note cut in UTF-8 bytes (app.js NOTE_LIMIT), used when ctx carries none. */
  const NOTE_LIMIT = 512;

  /** x as text: "" for null or undefined, String(x) otherwise, "" if even that throws. */
  function str(x) {
    if (typeof x === "string") return x;
    if (x == null) return "";
    try { return String(x); } catch (e) { return ""; }
  }

  /** o[key], or undefined when o is not an object or reading it throws. */
  function pick(o, key) {
    if (o === null || (typeof o !== "object" && typeof o !== "function")) return undefined;
    try { return o[key]; } catch (e) { return undefined; }
  }

  /** Find as a literal: every regex syntax character escaped and nothing else (under
      the u flag an escape of anything else, "\-" say, is a SyntaxError). */
  const escapeFind = s => s.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&");

  /** The spec as a function from a stored value to raw, or null when it changes no
      row (a bad mode, set on names, empty text, Find and Replace with both empty). */
  function editFor(spec, note) {
    const mode = pick(spec, "mode");
    if (mode === "prefix" || mode === "suffix") {
      const text = str(pick(spec, "text"));
      if (text === "") return null;    // no joiner either: an empty spec is a no-op
      const join = note ? "\n" : "";
      return mode === "prefix" ? v => text + join + v : v => v + join + text;
    }
    if (mode === "set") {
      if (!note) return null;
      const text = str(pick(spec, "text"));
      return () => text;
    }
    if (mode === "replace") {
      const find = str(pick(spec, "find")), repl = str(pick(spec, "repl"));
      if (find === "") return repl === "" ? null : () => repl;   // the whole value; Match case moot
      // Built once per call; replace() resets the g flag's lastIndex, so reuse is safe.
      const re = new RegExp(escapeFind(find), pick(spec, "matchCase") === true ? "gu" : "giu");
      const put = () => repl;          // a function, so $& $1 $$ $` $' stay literal
      return v => v.replace(re, put);
    }
    return null;
  }

  /** The rows through edit (null: every row unchanged), by the no-op rule in transform's doc. */
  function run(list, field, edit, limit) {
    const note = field === "desc";
    const out = new Array(list.length);
    let changed = 0;
    for (let i = 0; i < list.length; i++) {
      const r = list[i];
      const isRow = r !== null && typeof r === "object";
      const uid = isRow ? pick(r, "uid") : undefined;
      const before = isRow ? str(pick(r, field)) : "";
      const raw = edit && isRow ? edit(before) : before;
      if (raw === before) {
        out[i] = { uid, before, after: before, flags: ["unchanged"] };
        continue;
      }
      const after = note ? cleanNote(raw) : cleanName(raw);
      if (after === (note ? writtenNote(before) : before)) {
        out[i] = { uid, before, after: before, flags: ["unchanged"] };
        continue;
      }
      const flags = [];
      // Each UTF-16 unit is 1 to 3 UTF-8 bytes (a pair is 4 for 2), so only a note
      // between limit / 3 and limit units long needs counting.
      const len = after.length;
      if (note && len * 3 > limit && (len > limit || noteBytes(after) > limit)) flags.push("note-over-limit");
      if (xmlSafe(raw) !== raw) flags.push("chars-removed");
      changed++;
      out[i] = { uid, before, after, flags };
    }
    return { rows: out, changed };
  }

  /**
   * @param {Array<{uid:string, name:string, desc:string, kind:"waypoints"|"tracks"|"shapes"}>} rows
   *        the selected items as captured at open (name/desc are the current values, edits included)
   * @param {{ field:"name"|"desc",
   *           mode:"prefix"|"suffix"|"replace"|"set",   // "set" is notes only (Replace the note)
   *           text:string,                              // prefix / suffix / set text
   *           find:string, repl:string, matchCase:boolean // replace mode
   *        }} spec
   * @param {{ noteLimit:number }} ctx                   // 512 (app.js NOTE_LIMIT)
   * @returns {{ rows: Array<{uid:string, before:string, after:string, flags:string[]}>, changed:number }}
   *
   * flags is a subset of {"unchanged", "note-over-limit", "chars-removed"}; nothing blocks Save.
   * The rules (no-op rule, empty Find = replace the whole value, cleaning per field, $ and \
   * literal) follow UI-39; transform also never throws (its catch). In short:
   *  - raw is the edit of the stored value: prefix / suffix join with nothing for names and
   *    "\n" for notes (no joiner when the text is empty); set (notes only) is the text; replace
   *    with an empty Find is the whole Replace with, and a no-op while both are empty.
   *  - raw === before: "unchanged", nothing cleaned (an empty spec never strips a dirty value).
   *  - otherwise after = cleanName / cleanNote(raw); when that equals the value (for a note,
   *    its written form) the row is "unchanged" too. An unchanged row's after is its before.
   *  - a changed row may carry "chars-removed" (raw held characters XML forbids) and, for a
   *    note, "note-over-limit" (after is over ctx.noteLimit UTF-8 bytes). An empty after is an
   *    ordinary change: names are optional and the dialog shows "Untitled".
   * A spec that isn't an object, a field other than "name" / "desc", or a mode the field
   * doesn't have (set on names) leaves every row unchanged. Rows and spec values that aren't
   * strings are read as String(x ?? ""); a row that isn't an object is unchanged, before "".
   */
  function transform(rows, spec, ctx) {
    const list = Array.isArray(rows) ? rows : [];
    const f = pick(spec, "field");
    const field = f === "desc" ? "desc" : "name";
    const lim = pick(ctx, "noteLimit");
    const limit = typeof lim === "number" && lim >= 0 ? lim : NOTE_LIMIT;
    try {
      const edit = f === "name" || f === "desc" ? editFor(spec, field === "desc") : null;
      return run(list, field, edit, limit);
    } catch (e) {
      // Never throws (a result past the engine's string length, a hostile row): every
      // row unchanged instead, or no rows when even reading them fails.
      try { return run(list, field, null, limit); } catch (e2) { return { rows: [], changed: 0 }; }
    }
  }

  root.CairnRename = Object.freeze({
    transform, xmlSafe, cleanName, cleanNote, writtenNote, noteBytes, XML_INVALID,
  });
})(typeof window !== "undefined" ? window : globalThis);
