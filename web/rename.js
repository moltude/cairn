/* Bulk rename and note change: the one pure transform behind the dialog's
   preview and its Save (docs/plans/BULK_RENAME.md section 3.1).

   No DOM, no globals read, no side effects. Loaded before app.js by its own
   <script src="rename.js"> tag (the CSP allows only same-origin files) and
   exposed as window.CairnRename. Tests load it on about:blank with
   page.add_script_tag and call it through page.evaluate.

   Phase 1 skeleton (2026-10-25): the helpers below are final; transform() is
   Track A's to implement against the contract in its comment. */
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
      whitespace trimmed (app.js writtenNote, writers.clean_notes for plain notes). */
  const writtenNote = s => String(s ?? "").replace(/\r\n?/g, "\n").trim();

  /** A name as Cairn stores it after a bulk change: XML-safe, every whitespace
      run holding a line break or tab turned into one space, trimmed. Pure
      space runs are left alone ("Camp  A" is user data). May return "": names
      are optional (decision 17). */
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
   * The rules (no-op rule, empty Find = replace the whole value, cleaning per field, function
   * replacer, never throws) are in docs/plans/BULK_RENAME.md section 3.1.
   * TODO(Track A): implement. This stub reports every row unchanged.
   */
  function transform(rows, spec, ctx) {
    const field = spec && spec.field === "desc" ? "desc" : "name";
    const out = (rows || []).map(r => {
      const before = String((r && r[field]) ?? "");
      return { uid: r && r.uid, before, after: before, flags: ["unchanged"] };
    });
    return { rows: out, changed: 0 };
  }

  root.CairnRename = Object.freeze({
    transform, xmlSafe, cleanName, cleanNote, writtenNote, noteBytes, XML_INVALID,
  });
})(typeof window !== "undefined" ? window : globalThis);
