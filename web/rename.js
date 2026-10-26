/* Bulk rename and note change: the one pure transform behind the dialog's
   preview and its Save (docs/plans/BULK_RENAME.md section 3.1).

   No DOM, no globals read, no side effects. Loaded before app.js by its own
   <script src="rename.js"> tag (the CSP allows only same-origin files) and
   exposed as window.CairnRename. Tests load it on about:blank with
   page.add_script_tag and call it through page.evaluate.

   transform() turns one spec (a mode and its text) into a per-row Now ->
   After list with flags and the ranges the preview highlights; the dialog's
   preview and its Save both call it, so the preview is what gets stored and
   exported, and the dialog never builds a pattern of its own. Built
   2026-10-25; whole-word Find, highlight ranges and the name flags the same
   evening (tracker 7.4 W1, W2, L1, N1). */
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

  /** onX's note cut in UTF-8 bytes (app.js NOTE_LIMIT), used when ctx carries none. */
  const NOTE_LIMIT = 512;
  /** onX's name cut in UTF-8 bytes on import (measured live 2026-10-25, docs/testing/
      ONX_LIMITS_2026-10-25.md; app.js NAME_LIMIT), used when ctx carries none. */
  const NAME_LIMIT = 255;

  /* Find matches whole words only (owner, 2026-10-25, tracker 7.4 W1): a match never
     starts or ends inside a word. Word characters are letters with their marks and
     digits; spaces, punctuation and symbols are boundaries, so "TH." matches "TH"
     and keeps its full stop and "Bob's" matches "Bob". Each Han, hiragana or katakana
     character (Script_Extensions, so the prolonged sound mark and kana voicing marks
     count) is a word of its own and needs no boundary: "山" still matches inside
     "日本語の山", and "A" next to "山" is a word. Hangul is an ordinary word
     character (Korean uses spaces). Thai, Lao, Khmer, Myanmar and other scripts
     written without spaces are ordinary word characters too, so a Find matches only a
     whole unspaced run there: a known limit, kept simple on purpose. A boundary is
     checked only at an edge of the Find that is a word character, so "(rainy)" and
     " - " match wherever they occur. */
  const WORD = "\\p{L}\\p{M}\\p{N}";
  const OWN_WORD = "\\p{Script_Extensions=Han}\\p{Script_Extensions=Hiragana}\\p{Script_Extensions=Katakana}";
  const IS_WORD = new RegExp(`^[${WORD}]$`, "u");
  const IS_OWN_WORD = new RegExp(`^[${OWN_WORD}]$`, "u");
  /** Before a Find that starts with such a character: no word character that would
      join it (a Han or kana character never does). After one, the same. */
  const WORD_START = `(?:(?<![${WORD}])|(?<=[${OWN_WORD}]))`;
  const WORD_END = `(?:(?![${WORD}])|(?=[${OWN_WORD}]))`;
  /** True when c (one code point) needs a boundary beside it as a Find's edge. */
  const joins = c => IS_WORD.test(c) && !IS_OWN_WORD.test(c);

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

  /** Find as a whole-word pattern (see WORD): the literal, with a boundary check on
      each edge that is a word character. find is not "". */
  function findPattern(find, matchCase) {
    const cps = Array.from(find);
    const head = joins(cps[0]) ? WORD_START : "", tail = joins(cps[cps.length - 1]) ? WORD_END : "";
    return new RegExp(head + escapeFind(find) + tail, matchCase ? "gu" : "giu");
  }

  /** The spec as a function from a stored value to { raw, ins }, or null when it
      changes no row (a bad mode, set on names, empty text, Find and Replace with both
      empty). ins lists where the inserted text sits in raw, as flat [start, end]
      pairs of UTF-16 offsets: each replacement, the added text, or the whole value. */
  function editFor(spec, note) {
    const mode = pick(spec, "mode");
    if (mode === "prefix" || mode === "suffix") {
      const text = str(pick(spec, "text"));
      if (text === "") return null;    // no joiner either: an empty spec is a no-op
      const join = note ? "\n" : "";
      return mode === "prefix"
        ? v => ({ raw: text + join + v, ins: [0, text.length] })
        : v => { const raw = v + join + text; return { raw, ins: [raw.length - text.length, raw.length] }; };
    }
    if (mode === "set") {
      if (!note) return null;
      const text = str(pick(spec, "text"));
      return () => ({ raw: text, ins: [0, text.length] });
    }
    if (mode === "replace") {
      const find = str(pick(spec, "find")), repl = str(pick(spec, "repl"));
      if (find === "") return repl === "" ? null : () => ({ raw: repl, ins: [0, repl.length] });   // Match case moot
      // Built once per call; replace() resets the g flag's lastIndex, so reuse is safe.
      const re = findPattern(find, pick(spec, "matchCase") === true);
      return v => {
        const ins = [];
        let shift = 0;
        // A function, so $& $1 $$ $` $' stay literal. The pattern has no groups, so
        // the second argument is the match's offset in v.
        const raw = v.replace(re, (m, at) => {
          ins.push(at + shift, at + shift + repl.length);
          shift += repl.length - m.length;
          return repl;
        });
        return { raw, ins };
      };
    }
    return null;
  }

  /** The inserted ranges of raw as [start, end] pairs into after (UTF-16 offsets, end
      excluded; empty ones left out), or [] when cleaning changed raw in a way the
      ranges can't follow: a line break or tab collapsed inside the value, a character
      dropped from its middle, or an edge trimmed into an inserted range. Cleaning that
      only takes characters off raw's ends is followed. Never a wrong range. */
  function marksFor(raw, after, ins, clean) {
    if (after === "") return [];
    let k = 0;
    if (after !== raw) {
      k = raw.indexOf(after);
      if (k < 0 || clean(raw.slice(0, k)) !== "" || clean(raw.slice(k + after.length)) !== "") return [];
    }
    const out = [];
    for (let j = 0; j < ins.length; j += 2) {
      const s = ins[j], e = ins[j + 1];
      if (s === e) continue;
      if (s < k || e > k + after.length) return [];
      out.push([s - k, e - k]);
    }
    return out;
  }

  /** The rows through edit (null: every row unchanged), by section 3.1's no-op rule. */
  function run(list, field, edit, limits) {
    const note = field === "desc";
    const limit = note ? limits.note : limits.name;
    const clean = note ? cleanNote : cleanName;
    const out = new Array(list.length);
    let changed = 0;
    for (let i = 0; i < list.length; i++) {
      const r = list[i];
      const isRow = r !== null && typeof r === "object";
      const uid = isRow ? pick(r, "uid") : undefined;
      const before = isRow ? str(pick(r, field)) : "";
      const ed = edit && isRow ? edit(before) : null;
      const raw = ed ? ed.raw : before;
      if (raw === before) {
        out[i] = { uid, before, after: before, flags: ["unchanged"], marks: [] };
        continue;
      }
      const after = clean(raw);
      if (after === (note ? writtenNote(before) : before)) {
        out[i] = { uid, before, after: before, flags: ["unchanged"], marks: [] };
        continue;
      }
      const flags = [];
      // Each UTF-16 unit is 1 to 3 UTF-8 bytes (a pair is 4 for 2), so only a value
      // between limit / 3 and limit units long needs counting. Names and notes alike:
      // onX cuts both on import by UTF-8 bytes (names 255, notes 512).
      const len = after.length;
      const over = len * 3 > limit && (len > limit || noteBytes(after) > limit);
      if (note) {
        if (over) flags.push("note-over-limit");
      } else if (over) {
        flags.push("name-over-limit");
      } else if (after === "") {
        flags.push("name-empty");      // onX needs a name to import it (tracker 7.4 N1); warn only
      }
      if (xmlSafe(raw) !== raw) flags.push("chars-removed");
      changed++;
      out[i] = { uid, before, after, flags, marks: marksFor(raw, after, ed.ins, clean) };
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
   * @param {{ noteLimit:number, nameLimit:number }} ctx // 512 and 255 (app.js NOTE_LIMIT, NAME_LIMIT)
   * @returns {{ rows: Array<{uid:string, before:string, after:string, flags:string[],
   *                          marks:Array<[number, number]>}>, changed:number }}
   *
   * flags is a subset of {"unchanged", "note-over-limit", "name-over-limit", "name-empty",
   * "chars-removed"}; nothing blocks Save. The rules (no-op rule, empty Find = replace the
   * whole value, cleaning per field, function replacer, never throws) are in
   * docs/plans/BULK_RENAME.md section 3.1; Find matches whole words only (WORD above,
   * tracker 7.4 W1). In short:
   *  - raw is the edit of the stored value: prefix / suffix join with nothing for names and
   *    "\n" for notes (no joiner when the text is empty); set (notes only) is the text; replace
   *    with an empty Find is the whole Replace with, and a no-op while both are empty;
   *    otherwise each whole-word match of Find, left to right, without overlaps.
   *  - raw === before: "unchanged", nothing cleaned (an empty spec never strips a dirty value).
   *  - otherwise after = cleanName / cleanNote(raw); when that equals the value (for a note,
   *    its written form) the row is "unchanged" too. An unchanged row's after is its before.
   *  - a changed row may carry "chars-removed" (raw held characters XML forbids); a note
   *    "note-over-limit" (after is over ctx.noteLimit UTF-8 bytes); a name "name-over-limit"
   *    (over ctx.nameLimit UTF-8 bytes) or "name-empty" (after is ""). All warn only: an
   *    empty name is still saved, and the dialog shows "Untitled".
   *  - marks (tracker 7.4 W2): where after holds inserted text, as [start, end] UTF-16
   *    offsets, end excluded, in order, never empty: each replaced match, the text Add
   *    before / Add after added (not the note's joining line break), or the whole value
   *    for an empty Find and Replace the note. [] on an unchanged row, for a pure deletion,
   *    and when cleaning moved text in a way the ranges can't follow (marksFor).
   * A spec that isn't an object, a field other than "name" / "desc", or a mode the field
   * doesn't have (set on names) leaves every row unchanged. Rows and spec values that aren't
   * strings are read as String(x ?? ""); a row that isn't an object is unchanged, before "".
   */
  function transform(rows, spec, ctx) {
    const list = Array.isArray(rows) ? rows : [];
    const f = pick(spec, "field");
    const field = f === "desc" ? "desc" : "name";
    const lim = (key, dflt) => { const v = pick(ctx, key); return typeof v === "number" && v >= 0 ? v : dflt; };
    const limits = { note: lim("noteLimit", NOTE_LIMIT), name: lim("nameLimit", NAME_LIMIT) };
    try {
      const edit = f === "name" || f === "desc" ? editFor(spec, field === "desc") : null;
      return run(list, field, edit, limits);
    } catch (e) {
      // Never throws (a result past the engine's string length, a hostile row): every
      // row unchanged instead, or no rows when even reading them fails.
      try { return run(list, field, null, limits); } catch (e2) { return { rows: [], changed: 0 }; }
    }
  }

  root.CairnRename = Object.freeze({
    transform, xmlSafe, cleanName, cleanNote, writtenNote, noteBytes, XML_INVALID,
  });
})(typeof window !== "undefined" ? window : globalThis);
