"""The bulk rename core, web/rename.js, run in a real browser.

The rules tested here are in docs/design/DECISIONS.md (UI-39, ENG-09). There is no
Node toolchain in the repo, so the JS runs in headless Chromium: one module-scoped
about:blank page in the bypass-CSP context, rename.js injected with add_script_tag
(the worktree's own copy, found from this file), no Pyodide and no app.js. The file
lives under tests/web, so it inherits the session's dev-server check although it never
loads a URL; the skip keeps the other CI jobs green, as only web-e2e installs Chromium.

Transport. Every string crosses the protocol as a list of UTF-16 code units and is
rebuilt on the other side, so lone surrogates, NUL and U+FFFE arrive exactly (the
protocol would turn a lone surrogate into U+FFFD). One evaluate runs a batch of up to
100 vectors and returns {ok, error, result} per vector, so one throw never hides the
rest of the batch.

Properties use seeded random.Random generators, 300 vectors each (no Hypothesis: a new
dependency, and batched evaluate calls defeat its shrinking). A vector that breaks a
property is pinned by name in tests/bulk_rename_vectors.py.

The Python mirrors of the helpers below are the properties' oracle; the first test
checks them against the JS, and the writer-parity tests check the JS against the writer.
"""
from __future__ import annotations

import random
import re
import struct
import sys
from pathlib import Path

import pytest

from tests.bulk_rename_vectors import (
    CAMPSITES, PINNED, ROUND_TRIP_NAMES, ROUND_TRIP_NOTES, TWINS, spec,
    JS_TRIM as _JS_TRIM, XML_INVALID_RE as _XML_INVALID_RE,
    py_clean_name, py_clean_note, py_written_note, py_xml_safe,
)
from tests.naughty_strings import NAUGHTY, NAUGHTY_TEXTS

REPO = Path(__file__).resolve().parents[2]
RENAME_JS = REPO / "web" / "rename.js"
LIMIT = 512
FLAGS = {"unchanged", "note-over-limit", "chars-removed"}

sys.path.insert(0, str(REPO))
from cairn.core.writers import xml_safe as writer_xml_safe  # noqa: E402
from cairn.utils.utils import clean_notes  # noqa: E402

# --- transport -----------------------------------------------------------------------

_HARNESS = r"""
(batch) => {
  const R = window.CairnRename;
  const S = v => {
    if (!v || typeof v !== "object" || !Array.isArray(v.$u)) return v;
    let s = "";
    for (let i = 0; i < v.$u.length; i += 8192) s += String.fromCharCode.apply(null, v.$u.slice(i, i + 8192));
    return s;
  };
  const U = s => {
    if (typeof s !== "string") return s === undefined ? {$undef: true} : s;
    const a = new Array(s.length);
    for (let i = 0; i < s.length; i++) a[i] = s.charCodeAt(i);
    return {$u: a};
  };
  const obj = o => {
    if (!o || typeof o !== "object") return o;
    const out = {};
    for (const k of Object.keys(o)) out[k] = S(o[k]);
    return out;
  };
  return batch.map(v => {
    try {
      if (v.fn) {
        const r = R[v.fn](S(v.arg));
        return { ok: true, result: U(r) };
      }
      const rows = Array.isArray(v.rows) ? v.rows.map(obj) : v.rows;
      const t0 = performance.now();
      const out = R.transform(rows, obj(v.spec), v.ctx);
      const ms = performance.now() - t0;
      return { ok: true, ms, result: {
        changed: out.changed,
        rows: out.rows.map(r => ({ uid: r.uid, before: U(r.before), after: U(r.after), flags: r.flags })),
      } };
    } catch (e) {
      return { ok: false, error: String((e && e.stack) || e) };
    }
  });
}
"""


def _enc(v):
    """A str as its UTF-16 code units (surrogatepass keeps a lone surrogate)."""
    if isinstance(v, str):
        b = v.encode("utf-16-le", "surrogatepass")
        return {"$u": list(struct.unpack(f"<{len(b) // 2}H", b))}
    return v


def _dec(v):
    if isinstance(v, dict) and "$u" in v:
        u = v["$u"]
        return struct.pack(f"<{len(u)}H", *u).decode("utf-16-le", "surrogatepass")
    if isinstance(v, dict) and v.get("$undef"):
        return "<undefined>"
    return v


def _enc_obj(o):
    return {k: _enc(x) for k, x in o.items()} if isinstance(o, dict) else o


def _run(page, vectors):
    """Run vectors (dicts: rows/spec/ctx, or fn/arg) in batches of 100; decoded results."""
    out = []
    for i in range(0, len(vectors), 100):
        batch = []
        for v in vectors[i:i + 100]:
            if "fn" in v:
                batch.append({"fn": v["fn"], "arg": _enc(v["arg"])})
            else:
                rows = v["rows"]
                batch.append({
                    "rows": [_enc_obj(r) for r in rows] if isinstance(rows, list) else rows,
                    "spec": _enc_obj(v["spec"]),
                    "ctx": v.get("ctx", {"noteLimit": LIMIT}),
                })
        out += page.evaluate(_HARNESS, batch)
    for r in out:
        if r["ok"] and isinstance(r["result"], dict) and "rows" in r["result"]:
            for row in r["result"]["rows"]:
                row["before"], row["after"] = _dec(row["before"]), _dec(row["after"])
                row["flags"] = list(row["flags"]) if isinstance(row["flags"], list) else row["flags"]
        elif r["ok"]:
            r["result"] = _dec(r["result"])
    return out


def _row(name="", desc="", uid=None, kind="waypoints", **extra):
    r = {"uid": uid, "name": name, "desc": desc, "kind": kind, **extra}
    return r


def _rows(values, field="name"):
    """Rows whose `field` holds each value; uids u0, u1, ..."""
    return [_row(uid=f"u{i}", **{field: v}) for i, v in enumerate(values)]


def transform(page, rows, sp, ctx=None):
    (r,) = _run(page, [{"rows": rows, "spec": sp, "ctx": ctx or {"noteLimit": LIMIT}}])
    assert r["ok"], r["error"]
    return r["result"]


def one(page, before, sp, field=None):
    """(after, flags as a set, changed) for one row."""
    field = field or sp["field"]
    res = transform(page, [_row(uid="u0", **{field: before})], sp)
    (row,) = res["rows"]
    return row["after"], set(row["flags"]), res["changed"]


def helper(page, fn, *args):
    res = _run(page, [{"fn": fn, "arg": a} for a in args])
    for r in res:
        assert r["ok"], r["error"]
    return [r["result"] for r in res]


def names_spec(mode, **kw):
    return spec(mode, field="name", **kw)


def notes_spec(mode, **kw):
    return spec(mode, field="desc", **kw)


# --- Python mirrors of the helpers (tests/bulk_rename_vectors.py), checked below ------

def utf8_len(s):
    return len(s.encode("utf-8", "surrogatepass"))


def _combine(s):
    """A decoded string with every valid surrogate pair as one code point (it is
    already, from utf-16 decoding; this is for strings built in Python)."""
    return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")


# --- the page ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def core(context):
    """about:blank with the worktree's web/rename.js injected (no app, no CSP)."""
    page = context.new_page()
    page.goto("about:blank")
    page.add_script_tag(path=str(RENAME_JS))
    assert page.evaluate("() => typeof window.CairnRename.transform") == "function"
    yield page
    page.close()


# =====================================================================================
# The helpers
# =====================================================================================

ALPHABET = (
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    + list(".,;:!?-_()[]{}<>/|@#%^*+=~\"'`") + ["$", "&", "\\", "$&", "$1", "$$", "$`", "$'"]
    + ["€", "©", "°", "é", "ü"]
    + [" ", "  ", "\t", "\n", "\r\n", "\r", "\u00a0", "\u3000", "\u2028", "\x0b", "\x0c"]
    + ["\u0301", "\u0308", "\u0323"]
    + ["\u200b", "\u200d", "\u202e", "\ufeff"]
    + ["\x00", "\x01", "\x08", "\x1f", "\x7f", "\x85", "\x9f"]
    + ["İ", "ı", "ß", "ẞ", "Σ", "σ", "ς", "\u212a", "\u017f"]
    + ["\ufffe", "\uffff", "\ud800", "\udc00", "\U0010ffff"]
    + ["日", "本", "山", "🔥", "👨\u200d👩\u200d👧", "🇺🇸", "عربي", "Untitled"]
)


def gen_text(rnd: random.Random, maxlen=10, alphabet=ALPHABET) -> str:
    if rnd.random() < 0.15:
        return rnd.choice(NAUGHTY_TEXTS)[:60]
    return "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, maxlen)))


def test_property_the_python_mirror_of_the_clean_helpers_matches_the_js(core):
    """The mirrors below are the properties' oracle, so they are checked first: 300
    random strings through xmlSafe, cleanName, writtenNote and cleanNote in both."""
    rnd = random.Random(1)
    texts = [gen_text(rnd, 16) for _ in range(300)]
    for fn, mirror in (("xmlSafe", py_xml_safe), ("cleanName", py_clean_name),
                       ("writtenNote", py_written_note), ("cleanNote", py_clean_note)):
        got = helper(core, fn, *texts)
        for t, g in zip(texts, got):
            assert g == mirror(_combine(t)), (fn, t)


def test_property_clean_name_and_clean_note_are_idempotent(core):
    """Property 3."""
    rnd = random.Random(3)
    texts = [gen_text(rnd, 16) for _ in range(300)]
    for fn in ("cleanName", "cleanNote"):
        once = helper(core, fn, *texts)
        twice = helper(core, fn, *once)
        assert once == twice, fn


def test_property_note_bytes_is_the_utf8_length_instructions_txt_counts(core):
    """noteBytes is the measure bridge._written_items uses: len(desc.encode("utf-8"))."""
    rnd = random.Random(13)
    texts = [t for t in (gen_text(rnd, 40) for _ in range(400))
             if not re.search("[\ud800-\udfff]", _combine(t))][:300]
    assert len(texts) == 300
    for t, n in zip(texts, helper(core, "noteBytes", *texts)):
        assert n == len(_combine(t).encode("utf-8")), t


def test_the_xml_forbidden_set_is_the_writers_set(core):
    """One literal shared with cairn/core/writers.py (ENG-09): every code unit in the
    BMP that the writer drops, the core drops, and nothing else."""
    # Surrogates are probed one at a time between letters: side by side, a high one
    # followed by a low one would be a valid pair, which both keep.
    probe = "".join(chr(c) for c in range(0x10000) if not 0xD800 <= c <= 0xDFFF)
    (js,) = helper(core, "xmlSafe", probe)
    kept_by_js = set(map(ord, js))
    kept_by_writer = set(map(ord, writer_xml_safe(probe)))
    assert kept_by_js == kept_by_writer
    assert {0x09, 0x0A, 0x0D, 0x85, 0x200B, 0xFEFF, 0xA0, 0x7F} <= kept_by_js
    assert not {0x00, 0x01, 0x1F, 0xFFFE, 0xFFFF} & kept_by_js
    lone = [f"a{chr(c)}b" for c in (0xD800, 0xDBFF, 0xDC00, 0xDFFF)]
    assert helper(core, "xmlSafe", *lone) == ["ab"] * 4
    assert helper(core, "xmlSafe", "a\U0001f525b") == ["a\U0001f525b"]


def test_a_trailing_bom_or_nbsp_in_a_name_is_trimmed_like_a_space(core):
    """JS trim() counts U+FEFF and NBSP as whitespace, so cleanName drops them at the
    ends of a name (silently, like a space) and keeps them inside. A first draft of
    test_zero_width_space_and_bom_are_kept_in_names put the BOM last ("Camp\\u200b\\ufeff"),
    where cleanName trims it; the keep-inside case is that test's job now."""
    got = helper(core, "cleanName", "xCamp\u200b\ufeff", "\u00a0Camp\u00a0", "Ca\ufeffmp", "\ufeff")
    assert got == ["xCamp\u200b", "Camp", "Ca\ufeffmp", ""]


def test_the_writer_leaves_a_cleaned_note_alone(core):
    """The headline invariant for notes: the <desc> the writer emits equals the core's
    after. The writer runs clean_notes(plain=True) (Python str.strip) and xml_safe on
    what Save stored, so cleanNote's output must be a fixed point of both. Property over
    300 generated notes."""
    rnd = random.Random(17)
    texts = [gen_text(rnd, 16) for _ in range(300)]
    for t, got in zip(texts, helper(core, "cleanNote", *texts)):
        assert clean_notes(writer_xml_safe(got), plain=True) == got, t


def test_a_note_ending_in_next_line_exports_as_the_core_stores_it(core):
    """Regression: JS trim() keeps U+0085 (NEL) and Python's str.strip() in the writer's
    clean_notes removes it, so a note with an outer NEL was previewed and stored with it
    and exported without it. writtenNote now trims it too; a NEL inside a
    note stays (test_c1_controls_are_kept_in_names_and_notes)."""
    got = helper(core, "cleanNote", "abc\n\x85", "\x85 abc", "a\x85b")
    assert got == ["abc", "abc", "a\x85b"]
    for g in got:
        assert clean_notes(writer_xml_safe(g), plain=True) == g


# =====================================================================================
# Length and limits
# =====================================================================================


def test_note_prefix_pushes_a_511_byte_note_over_the_limit_and_flags_it(core):
    note = "a" * 511
    after, flags, changed = one(core, note, notes_spec("prefix", text="x"))
    assert after == "x\n" + note and utf8_len(after) == 513
    assert "note-over-limit" in flags and "unchanged" not in flags and changed == 1


def test_multibyte_note_bytes_are_counted_not_characters(core):
    """600 bytes in 200 characters: flagged. app.js noteOverflow would say "About 30
    characters will be cut" (170 three-byte characters fit in 512); that sentence is
    the dialog's, tested end to end."""
    text = "日" * 200
    after, flags, _ = one(core, "", notes_spec("set", text=text))
    assert after == text and "note-over-limit" in flags
    (n,) = helper(core, "noteBytes", after)
    assert n == 600
    kept = len(text.encode("utf-8")[:LIMIT].decode("utf-8", "ignore"))
    assert len(text) - kept == 30


def test_a_four_byte_emoji_straddling_512_is_reported_not_split(core):
    text = "a" * 510 + "🔥"
    after, flags, _ = one(core, "", notes_spec("set", text=text))
    assert after == text and after.endswith("🔥") and utf8_len(after) == 514
    assert "note-over-limit" in flags and "chars-removed" not in flags


def test_note_exactly_512_bytes_is_not_flagged(core):
    after, flags, changed = one(core, "", notes_spec("set", text="a" * 512))
    assert after == "a" * 512 and flags == set() and changed == 1
    _, flags513, _ = one(core, "", notes_spec("set", text="a" * 513))
    assert flags513 == {"note-over-limit"}


def test_crlf_and_lone_cr_in_a_note_become_lf_before_measure(core):
    """700 bytes as typed, 500 as written: measured after the line endings are made "\\n",
    so no flag (instructions.txt counts the written <desc>, the twin of this test in
    tests/test_bulk_prereqs.py)."""
    after, flags, _ = one(core, "", notes_spec("set", text="a\r\nb\rc" * 100))
    assert after == "a\nb\nc" * 100 and "\r" not in after
    assert utf8_len(after) == 500 and "note-over-limit" not in flags


def test_note_bytes_in_the_dialog_match_instructions_txt(core):
    """512 bytes with the tags kept: no flag; one byte more: flagged. The twin in
    tests/test_bulk_prereqs.py checks instructions.txt's cut line at the same two sizes."""
    at = "a" * 505 + "<b></b>"
    after, flags, _ = one(core, "", notes_spec("set", text=at))
    assert after == at and utf8_len(after) == 512 and flags == set()
    _, flags2, _ = one(core, "", notes_spec("set", text=at + "a"))
    assert "note-over-limit" in flags2


def test_a_3000_character_name_is_stored_whole_and_exported_whole(core):
    after, flags, _ = one(core, "Camp", names_spec("prefix", text="x" * 3000))
    assert after == "x" * 3000 + "Camp" and flags == set()


def test_a_find_string_longer_than_10k_characters_does_not_hang(core):
    rows = [_row(uid=f"u{i}", name=f"Camp {i} " + "a" * (i % 50)) for i in range(1500)]
    (r,) = _run(core, [{"rows": rows, "spec": names_spec("replace", find="a" * 10_000, repl="b")}])
    assert r["ok"], r["error"]
    assert r["result"]["changed"] == 0
    assert all(row["flags"] == ["unchanged"] for row in r["result"]["rows"])
    assert r["ms"] < 1000, f"transform took {r['ms']:.0f} ms"


# =====================================================================================
# Non-English and Unicode
# =====================================================================================


def test_cjk_names_survive_prefix_and_find_replace(core):
    assert one(core, "日本語の山", names_spec("replace", find="山", repl="岳"))[0] == "日本語の岳"
    assert one(core, "日本語の山", names_spec("prefix", text="東"))[0] == "東日本語の山"


def test_rtl_names_keep_their_characters_and_order(core):
    after, flags, _ = one(core, "مجلد عربي", names_spec("suffix", text=" 2"))
    assert after == "مجلد عربي 2" and flags == set()


def test_bidi_override_is_kept_and_never_breaks_xml(core):
    after, flags, changed = one(core, "a\u202eb", names_spec("prefix", text=""))
    assert flags == {"unchanged"} and after == "a\u202eb" and changed == 0
    after, flags, _ = one(core, "a\u202eb", names_spec("prefix", text="x"))
    assert after == "xa\u202eb" and "chars-removed" not in flags


@pytest.mark.parametrize("match_case", [False, True])
def test_nfd_find_does_not_match_nfc_text_and_does_not_crash(core, match_case):
    after, flags, changed = one(core, "Zürich",
                                names_spec("replace", find="u\u0308", repl="ue", match_case=match_case))
    assert flags == {"unchanged"} and changed == 0 and after == "Zürich"


def test_combining_marks_stay_attached_after_a_prefix(core):
    assert one(core, "e\u0301", names_spec("prefix", text="A"))[0] == "Ae\u0301"
    assert one(core, "é", names_spec("prefix", text="A"))[0] == "Aé"


@pytest.mark.parametrize("emoji", ["👨\u200d👩\u200d👧", "🇺🇸", "👍🏽"], ids=["zwj_family", "flag", "skin_tone"])
def test_emoji_zwj_families_and_flags_are_not_broken(core, emoji):
    after, flags, _ = one(core, emoji, names_spec("prefix", text="x"))
    assert after == "x" + emoji and flags == set()


def test_a_paired_emoji_survives_the_surrogate_strip(core):
    after, flags, _ = one(core, "a🔥b", names_spec("prefix", text="x"))
    assert after == "xa🔥b" and "chars-removed" not in flags


def test_turkish_dotted_i_does_not_cross_match_case_insensitively(core):
    _, flags, changed = one(core, "İstanbul", names_spec("replace", find="istanbul", repl="X"))
    assert flags == {"unchanged"} and changed == 0
    after, _, changed = one(core, "İstanbul", names_spec("replace", find="İ", repl="I"))
    assert after == "Istanbul" and changed == 1


def test_eszett_does_not_match_ss(core):
    for find in ("ss", "SS"):
        _, flags, changed = one(core, "Straße", names_spec("replace", find=find, repl="x"))
        assert flags == {"unchanged"} and changed == 0, find


def test_final_sigma_matches_sigma_without_match_case_and_only_itself_with_it(core):
    """Final sigma matches sigma: the core uses the browser's own RegExp "iu" folding
    (no folding table of its own), and Unicode simple case folding maps
    final sigma to sigma. So with Match case off "σ" matches σ, σ and ς (3); with it on,
    only the two σ."""
    off, _, _ = one(core, "Οδυσσεύς", names_spec("replace", find="σ", repl="x"))
    on, _, _ = one(core, "Οδυσσεύς", names_spec("replace", find="σ", repl="x", match_case=True))
    assert off == "Οδυxxεύx" and off.count("x") == 3
    assert on == "Οδυxxεύς" and on.count("x") == 2


def test_zero_width_space_and_bom_are_kept_in_names(core):
    """Inside a name both are user data. A BOM at the very end is trimmed like a space
    (test_a_trailing_bom_or_nbsp_in_a_name_is_trimmed_like_a_space), so the BOM sits inside."""
    after, flags, _ = one(core, "Ca\ufeffmp\u200b!", names_spec("prefix", text="x"))
    assert after == "xCa\ufeffmp\u200b!" and flags == set()
    after, flags, _ = one(core, "Ca\ufeffmp\u200b X", names_spec("prefix", text="x"))
    assert after == "xCa\ufeffmp\u200b X" and flags == set()
    after, flags, _ = one(core, "Camp\u200b", names_spec("prefix", text="x"))
    assert after == "xCamp\u200b" and "chars-removed" not in flags


def test_c1_controls_are_kept_in_names_and_notes(core):
    after, flags, _ = one(core, "a\x85b", names_spec("prefix", text="x"))
    assert after == "xa\x85b" and "chars-removed" not in flags
    after, flags, _ = one(core, "a\x85b", notes_spec("suffix", text="!"))
    assert after == "a\x85b\n!" and "chars-removed" not in flags


def test_nbsp_is_kept_in_names(core):
    after, flags, _ = one(core, "Camp\u00a0A", names_spec("prefix", text="x"))
    assert after == "xCamp\u00a0A" and "chars-removed" not in flags


def test_nbsp_find_does_not_match_a_space(core):
    _, flags, changed = one(core, "a\u00a0b", names_spec("replace", find=" ", repl="_"))
    assert flags == {"unchanged"} and changed == 0


def test_fullwidth_and_halfwidth_are_different_characters(core):
    for before, find in (("Ａ", "A"), ("A", "Ａ"), ("ａ", "a")):
        _, flags, changed = one(core, before, names_spec("replace", find=find, repl="x"))
        assert flags == {"unchanged"} and changed == 0, (before, find)


def test_a_name_of_only_combining_marks_is_kept_not_shown_as_untitled(core):
    after, flags, changed = one(core, "x\u0301", names_spec("replace", find="x", repl=""))
    assert after == "\u0301" and flags == set() and changed == 1


def test_emoji_only_names_show_as_themselves_and_sort_stably(core):
    after, flags, _ = one(core, "Camp", names_spec("replace", find="", repl="🔥"))
    assert after == "🔥" and flags == set()


@pytest.mark.parametrize("typed", ["Untitled", "(no name)"])
def test_a_name_typed_as_untitled_or_no_name_is_an_ordinary_name(core, typed):
    after, flags, changed = one(core, "Camp", names_spec("replace", find="", repl=typed))
    assert after == typed and flags == set() and changed == 1


# =====================================================================================
# XML-hostile
# =====================================================================================


def test_control_characters_are_stripped_from_names_and_flagged(core):
    after, flags, _ = one(core, "\x00Camp\x01\x1f", names_spec("prefix", text="x"))
    assert after == "xCamp" and flags == {"chars-removed"}


def test_a_dirty_stored_name_is_left_alone_by_an_empty_spec(core):
    """No-op rule: nothing is cleaned without a change (the writer is the net)."""
    for sp in (names_spec("prefix"), names_spec("suffix"), names_spec("replace")):
        after, flags, changed = one(core, "\x01Camp", sp)
        assert flags == {"unchanged"} and changed == 0 and after == "\x01Camp", sp["mode"]


def test_an_empty_add_before_or_after_leaves_a_dirty_note_alone(core):
    """The notes twin of the test above. Taken literally, the note join (UI-39) makes an empty
    Add before raw = "" + "\\n" + before, which differs from before, so a dirty note
    would be cleaned (and flagged) by a spec that types nothing. Property 4 says an
    empty spec changes no row."""
    for sp in (notes_spec("prefix"), notes_spec("suffix")):
        after, flags, changed = one(core, "\x01abc ", sp)
        assert flags == {"unchanged"} and changed == 0 and after == "\x01abc ", sp["mode"]


def test_tab_and_newline_in_a_name_become_one_space(core):
    after, flags, _ = one(core, "Camp\tA \n B", names_spec("prefix", text="x"))
    assert after == "xCamp A B" and flags == set()


def test_pure_space_runs_in_a_name_are_kept(core):
    assert one(core, "Camp  A", names_spec("prefix", text="x"))[0] == "xCamp  A"


def test_tab_and_newline_in_a_note_are_kept(core):
    after, flags, _ = one(core, "line1\n\tline2", notes_spec("suffix", text="!"))
    assert after == "line1\n\tline2\n!" and flags == set()


_LONE = r"""
(units) => {
  const R = window.CairnRename;
  const name = String.fromCharCode(...units);
  const out = R.transform([{ uid: "u0", name, desc: "", kind: "waypoints" }],
    { field: "name", mode: "prefix", text: "x", find: "", repl: "", matchCase: false }, { noteLimit: 512 });
  const after = out.rows[0].after;
  return { isWellFormed: after.isWellFormed(), length: after.length,
           flagged: out.rows[0].flags.includes("chars-removed"), changed: out.changed };
}
"""


@pytest.mark.parametrize("units", [[0x61, 0xD800, 0x62], [0x61, 0xDC00, 0x62], [0x61, 0xDC00, 0xD800, 0x62]],
                         ids=["high", "low", "reversed_pair"])
def test_lone_surrogates_are_removed(core, units):
    """Built with String.fromCharCode inside evaluate; only booleans and lengths come
    back ("xab"), never the string."""
    got = core.evaluate(_LONE, units)
    assert got == {"isWellFormed": True, "length": 3, "flagged": True, "changed": 1}


def test_fffe_and_ffff_are_removed(core):
    after, flags, _ = one(core, "a\ufffeb\uffff", names_spec("prefix", text="x"))
    assert after == "xab" and flags == {"chars-removed"}


def test_cdata_terminator_and_entities_survive_as_text(core):
    after, flags, _ = one(core, "]]> & < > \" '", names_spec("prefix", text="x"))
    assert after == "x]]> & < > \" '" and flags == set()


# =====================================================================================
# Replacement-pattern and find traps
# =====================================================================================


def test_dollar_patterns_in_the_replacement_are_literal(core):
    repl = "$&$1$$$`$'"
    assert one(core, "a", names_spec("replace", find="a", repl=repl))[0] == repl
    assert one(core, "bab", names_spec("replace", find="a", repl=repl))[0] == "b" + repl + "b"


def test_backslashes_in_find_and_replace_are_literal(core):
    assert one(core, "a\\b\\c", names_spec("replace", find="\\", repl="\\\\"))[0] == "a\\\\b\\\\c"


def test_regex_specials_in_find_are_literal(core):
    after, _, changed = one(core, "x.*+?^$()[]{}|y", names_spec("replace", find=".*+?^$()[]{}|", repl="-"))
    assert after == "x-y" and changed == 1
    _, flags, _ = one(core, "xy", names_spec("replace", find=".", repl="-"))
    assert flags == {"unchanged"}


# Find and replace changes every occurrence in a field, not the first (UI-39), a check the
# owner asked for. The dialog's side is tests/web/test_text_rules.py.
_FAR = "Trail" + ", then switchbacks, meadow and scree" * 20 + " to the far Trail"
EVERY_MATCH = [
    pytest.param("name", "Ridge Trail Trail Trail", "Trail", False, "Ridge Path Path Path",
                 id="three-matches-in-one-name"),
    pytest.param("name", _FAR, "Trail", False, _FAR.replace("Trail", "Path"), id="matches-far-apart"),
    pytest.param("name", "Trail trail TRAIL", "trail", False, "Path Path Path",
                 id="mixed-case-with-match-case-off-changes-all-three"),
    pytest.param("name", "Trail trail TRAIL", "trail", True, "Trail Path TRAIL",
                 id="mixed-case-with-match-case-on-changes-only-the-exact-one"),
    pytest.param("desc", "Trail at the top\nthen the Trail down", "Trail", False,
                 "Path at the top\nthen the Path down", id="matches-on-two-lines-of-a-note"),
    pytest.param("desc", "up top\nTrail down\nup top\nTrail down", "top\nTrail", False,
                 "up Path down\nup Path down", id="a-find-across-a-line-break-matches-twice-in-a-note"),
]


@pytest.mark.parametrize("field,before,find,match_case,after", EVERY_MATCH)
def test_find_and_replace_changes_every_occurrence_in_a_field(core, field, before, find, match_case, after):
    sp = spec("replace", field=field, find=find, repl="Path", match_case=match_case)
    assert one(core, before, sp) == (after, set(), 1)


@pytest.mark.parametrize("before,after", [
    pytest.param("aaaa", "bb", id="adjacent-matches-aaaa-to-bb"),
    pytest.param("aaa", "ba", id="overlapping-aaa-goes-left-to-right"),
    pytest.param("aaaaa", "bba", id="overlapping-aaaaa-goes-left-to-right"),
])
def test_find_aa_replaces_adjacent_and_overlapping_text_left_to_right(core, before, after):
    got, flags, changed = one(core, before, names_spec("replace", find="aa", repl="b"))
    assert (got, flags, changed) == (after, set(), 1)


@pytest.mark.parametrize("field", ["name", "desc"])
def test_empty_find_and_empty_replace_is_a_noop(core, field):
    """On hostile values too: no cleaning without a change."""
    res = transform(core, _rows(NAUGHTY_TEXTS, field), spec("replace", field=field))
    assert res["changed"] == 0
    for row, before in zip(res["rows"], NAUGHTY_TEXTS):
        assert row["flags"] == ["unchanged"] and row["after"] == before


@pytest.mark.parametrize("match_case", [False, True])
def test_empty_find_replaces_the_whole_name(core, match_case):
    res = transform(core, _rows(CAMPSITES + ["Campsite"]),
                    names_spec("replace", find="", repl="Campsite", match_case=match_case))
    assert [r["after"] for r in res["rows"]] == ["Campsite"] * 4
    assert [set(r["flags"]) for r in res["rows"]] == [set(), set(), set(), {"unchanged"}]
    assert res["changed"] == 3


def test_empty_find_with_a_whitespace_only_replacement_saves_blank_names(core):
    res = transform(core, _rows(["Camp A", "Camp B", "Lake", "Trail 1", "Peak"]),
                    names_spec("replace", find="", repl="  "))
    assert [r["after"] for r in res["rows"]] == [""] * 5
    assert all(r["flags"] == [] for r in res["rows"]) and res["changed"] == 5


def test_empty_find_replaces_the_whole_note_like_replace_the_note(core):
    notes = ["old note", "", "line1\nline2", "see north"]
    a = transform(core, _rows(notes, "desc"), notes_spec("replace", find="", repl="see north"))
    b = transform(core, _rows(notes, "desc"), notes_spec("set", text="see north"))
    assert a == b
    assert [r["after"] for r in a["rows"]] == ["see north"] * 4
    assert a["changed"] == 3 and a["rows"][3]["flags"] == ["unchanged"]
    c = transform(core, _rows(notes, "desc"), notes_spec("replace", find="", repl=""))
    assert c["changed"] == 0


def test_find_with_no_matches_marks_every_row_unchanged(core):
    res = transform(core, _rows(["Camp A", "Lake", "Trail"]), names_spec("replace", find="zzz", repl="x"))
    assert res["changed"] == 0 and all(r["flags"] == ["unchanged"] for r in res["rows"])


def test_find_equal_to_replace_counts_zero(core):
    """On rows with no other-case "a". With Match case off a capital "A" IS matched and
    replaced by "a", which is a real change, not a no-op: pinned too."""
    res = transform(core, _rows(["Camp", "Lake", "Trail"]), names_spec("replace", find="a", repl="a"))
    assert res["changed"] == 0
    after, _, changed = one(core, "Camp A", names_spec("replace", find="a", repl="a"))
    assert after == "Camp a" and changed == 1
    _, flags, _ = one(core, "Camp A", names_spec("replace", find="a", repl="a", match_case=True))
    assert flags == {"unchanged"}


def test_whitespace_only_prefix_is_a_noop_after_trim(core):
    res = transform(core, _rows(["Camp", "Lake"]), names_spec("prefix", text="  "))
    assert res["changed"] == 0 and all(r["flags"] == ["unchanged"] for r in res["rows"])


def test_whitespace_only_suffix_on_notes_is_a_noop_after_writtennote(core):
    res = transform(core, _rows(["abc", "abc "], "desc"), notes_spec("suffix", text="\n "))
    assert res["changed"] == 0 and all(r["flags"] == ["unchanged"] for r in res["rows"])


def test_set_mode_with_a_blank_note_on_a_row_with_no_note_is_unchanged(core):
    rows = [_row(uid="empty", desc=""), {"uid": "missing", "name": "x", "kind": "waypoints"},
            _row(uid="real", desc="a real note")]
    res = transform(core, rows, notes_spec("set", text="  \n "))
    by = {r["uid"]: r for r in res["rows"]}
    assert by["empty"]["flags"] == ["unchanged"] and by["missing"]["flags"] == ["unchanged"]
    assert by["missing"]["before"] == ""
    assert by["real"]["after"] == "" and by["real"]["flags"] == [] and res["changed"] == 1


def test_overlapping_matches_replace_left_to_right(core):
    assert one(core, "aaa", names_spec("replace", find="aa", repl="b"))[0] == "ba"


def test_replace_with_empty_can_empty_a_name_and_saves_it_blank(core):
    after, flags, changed = one(core, "Camp", names_spec("replace", find="Camp", repl=""))
    assert after == "" and flags == set() and changed == 1


def test_match_case_toggle_changes_the_count_live(core):
    off = one(core, "Camp camp", names_spec("replace", find="camp", repl="x"))[0]
    on = one(core, "Camp camp", names_spec("replace", find="camp", repl="x", match_case=True))[0]
    assert off == "x x" and on == "Camp x"


def test_find_whitespace_only_is_a_real_find(core):
    assert one(core, "Camp A B", names_spec("replace", find=" ", repl="_"))[0] == "Camp_A_B"


def test_find_longer_than_the_name_matches_nothing(core):
    _, flags, changed = one(core, "Camp", names_spec("replace", find="Campground", repl="x"))
    assert flags == {"unchanged"} and changed == 0


def test_replace_result_is_trimmed_but_inner_spaces_are_kept_for_names(core):
    assert one(core, "Camp A", names_spec("replace", find="Camp", repl="  "))[0] == "A"
    assert one(core, "X Camp A", names_spec("replace", find="Camp", repl="  "))[0] == "X    A"


def test_whitespace_only_results_are_trimmed_to_blank_and_shown_untitled(core):
    after, flags, changed = one(core, "Camp", names_spec("replace", find="Camp", repl=" \t\n "))
    assert after == "" and flags == set() and changed == 1
    after, flags, changed = one(core, "", names_spec("prefix", text="  "))
    assert flags == {"unchanged"} and changed == 0 and after == ""


def test_an_unknown_mode_leaves_every_row_unchanged(core):
    """Also Replace the note on names: names have no such mode (UI-39)."""
    for sp in (names_spec("bogus", text="x"), names_spec("set", text="x")):
        res = transform(core, _rows(["Camp", "Lake"]), sp)
        assert res["changed"] == 0 and all(r["flags"] == ["unchanged"] for r in res["rows"]), sp


def test_a_lone_surrogate_find_never_splits_a_paired_emoji(core):
    """With the u flag a lone high surrogate matches only a lone one, never half of a
    pair: here it is the lone one that goes, and raw then holds none, so no flag."""
    after, flags, changed = one(core, "a\U0001f525\ud83db", names_spec("replace", find="\ud83d", repl="Z"))
    assert after == "a\U0001f525Zb" and flags == set() and changed == 1


# =====================================================================================
# Incompatible and conflicting bulk operations
# =====================================================================================


def test_campsite_normalisation_makes_three_identical_names_and_exports_three_items(core):
    res = transform(core, _rows(CAMPSITES), names_spec("replace", find="", repl="Campsite"))
    assert [r["after"] for r in res["rows"]] == ["Campsite"] * 3
    assert [r["flags"] for r in res["rows"]] == [[], [], []]   # exclusivity: no flag at all
    assert res["changed"] == 3


def test_renaming_existing_twins_together_keeps_them_twins(core):
    res = transform(core, _rows(TWINS), names_spec("prefix", text="Base "))
    assert [r["after"] for r in res["rows"]] == ["Base Camp", "Base camp", "Base CAMP", "Base  Camp"]
    assert [r["flags"] for r in res["rows"]] == [[], [], [], []] and res["changed"] == 4


def test_a_rename_that_collides_with_an_unselected_name_is_an_ordinary_change(core):
    after, flags, changed = one(core, "Camp A", names_spec("replace", find=" A", repl=""))
    assert after == "Camp" and flags == set() and changed == 1


# =====================================================================================
# Pinned vectors and the round-trip data
# =====================================================================================


@pytest.mark.parametrize("label", list(PINNED))
def test_pinned_vectors_give_what_they_were_pinned_at(core, label):
    rows, sp, expected = PINNED[label]
    res = transform(core, [_row(uid=f"u{i}", name=n, desc=d) for i, (n, d) in enumerate(rows)], sp)
    assert [(r["after"], set(r["flags"])) for r in res["rows"]] == expected


def test_match_case_on_can_change_a_row_that_match_case_off_leaves_alone(core):
    """Left-to-right matching means Match case off is not a superset of on: "Aaa" find
    "aa" replace "Aa" changes with Match case on ("AAa") and not with it off (its "Aa"
    match at 0 blocks the one at 1). Why property 9's generator rules out self-overlapping
    finds."""
    on = PINNED["match_case_overlap_on"]
    off = PINNED["match_case_overlap_off"]
    r_on = transform(core, [_row(uid="u0", name="Aaa")], on[1])
    r_off = transform(core, [_row(uid="u0", name="Aaa")], off[1])
    assert r_on["changed"] == 1 and r_off["changed"] == 0


@pytest.mark.parametrize("label,before,sp,after", ROUND_TRIP_NAMES + ROUND_TRIP_NOTES,
                         ids=[v[0] for v in ROUND_TRIP_NAMES + ROUND_TRIP_NOTES])
def test_the_round_trip_vectors_are_what_the_core_returns(core, label, before, sp, after):
    """The bridge tests store these hand-derived results; this keeps them honest."""
    got, flags, changed = one(core, before, sp)
    assert got == after and changed == 1 and "unchanged" not in flags


# =====================================================================================
# Properties, 300 seeded vectors each
# =====================================================================================

MODES = {"name": ["prefix", "suffix", "replace"], "desc": ["prefix", "suffix", "replace", "set"]}


def gen_vector(rnd: random.Random, *, field=None, mode=None, maxrows=6):
    field = field or rnd.choice(["name", "desc"])
    mode = mode or rnd.choice(MODES[field])
    rows = []
    for i in range(rnd.randint(1, maxrows)):
        r = {"uid": f"u{i}", "kind": rnd.choice(["waypoints", "tracks", "shapes"]),
             "name": gen_text(rnd), "desc": gen_text(rnd, 14)}
        if rnd.random() < 0.1:
            del r["desc"]
        if rnd.random() < 0.1:
            r["name"] = ""
        rows.append(r)
    text = gen_text(rnd, 6) if rnd.random() < 0.85 else ""
    find = ""
    if mode == "replace" and rnd.random() < 0.8:
        src = rnd.choice(rows).get(field) or ""
        if src and rnd.random() < 0.7:
            a = rnd.randrange(len(src))
            find = src[a:a + rnd.randint(1, 3)]
        else:
            find = gen_text(rnd, 3)
    repl = gen_text(rnd, 5) if rnd.random() < 0.8 else ""
    ctx = {"noteLimit": rnd.choice([LIMIT, 8, 16, 40])}
    return {"rows": rows, "spec": spec(mode, text=text, find=find, repl=repl,
                                        match_case=rnd.random() < 0.5, field=field), "ctx": ctx}


def _results(page, vectors):
    out = _run(page, vectors)
    for v, r in zip(vectors, out):
        assert r["ok"], (v, r["error"])
    return [r["result"] for r in out]


def _before(row, field):
    return row.get(field) or ""


def test_property_1_changed_values_hold_no_xml_forbidden_character(core):
    rnd = random.Random(101)
    vs = [gen_vector(rnd) for _ in range(300)]
    for v, res in zip(vs, _results(core, vs)):
        for r in res["rows"]:
            if "unchanged" not in r["flags"]:
                assert not _XML_INVALID_RE.search(r["after"]), (v, r)


def test_property_2_a_changed_name_has_no_line_break_or_tab_and_no_outer_whitespace(core):
    rnd = random.Random(102)
    vs = [gen_vector(rnd, field="name") for _ in range(300)]
    for v, res in zip(vs, _results(core, vs)):
        for r in res["rows"]:
            if "unchanged" not in r["flags"]:
                a = r["after"]
                assert not re.search("[\r\n\t]", a) and a == a.strip(_JS_TRIM), (v, r)


def test_property_4_an_empty_spec_changes_no_row(core):
    rnd = random.Random(104)
    vs = []
    for _ in range(300):
        v = gen_vector(rnd)
        field = v["spec"]["field"]
        mode = rnd.choice(["prefix", "suffix", "replace"])
        v["spec"] = spec(mode, field=field, match_case=rnd.random() < 0.5)
        vs.append(v)
    for v, res in zip(vs, _results(core, vs)):
        assert res["changed"] == 0, v
        for r, row in zip(res["rows"], v["rows"]):
            assert r["flags"] == ["unchanged"] and r["after"] == _before(row, v["spec"]["field"]), (v, r)


def test_property_5_an_empty_find_replaces_the_whole_value_whatever_match_case(core):
    rnd = random.Random(105)
    vs, mirror = [], []
    for _ in range(300):
        v = gen_vector(rnd, mode="replace")
        v["spec"]["find"] = ""
        v["spec"]["repl"] = v["spec"]["repl"] or "x"
        w = {**v, "spec": {**v["spec"], "matchCase": not v["spec"]["matchCase"]}}
        vs += [v, w]
    res = _results(core, vs)
    for i in range(0, len(vs), 2):
        v, a, b = vs[i], res[i], res[i + 1]
        assert a == b, ("Match case changed an empty-Find result", v)
        field, repl = v["spec"]["field"], _combine(v["spec"]["repl"])
        clean = py_clean_name(repl) if field == "name" else py_clean_note(repl)
        for r, row in zip(a["rows"], v["rows"]):
            before = _combine(_before(row, field))
            if "unchanged" in r["flags"]:
                same = before if field == "name" else py_written_note(before)
                assert repl == before or clean == same, (v, r)
            else:
                assert r["after"] == clean, (v, r)


_PLAIN = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,;:!?-_()[]{}<>/|@#%^*+=~\"`'") \
    + ["$&", "$1", "$$", "$`", "$'", "é", "日", "🔥", "&"]


def test_property_6_dollar_patterns_stay_literal(core):
    """With find and repl non-empty and neither inside the other, the replacement shows
    up at least as often as find did. repl is drawn from non-space printables (and the
    $ patterns): cleaning collapses tabs and line breaks and trims outer whitespace, which
    would change a repl holding them and break the count for a reason that isn't $."""
    rnd = random.Random(106)
    vs = []
    while len(vs) < 300:
        v = gen_vector(rnd, mode="replace")
        find = v["spec"]["find"]
        repl = "".join(rnd.choice(_PLAIN) for _ in range(rnd.randint(1, 4)))
        if not find or find in repl or repl in find:
            continue
        v["spec"]["repl"] = repl
        vs.append(v)
    for v, res in zip(vs, _results(core, vs)):
        field, find, repl = v["spec"]["field"], v["spec"]["find"], v["spec"]["repl"]
        for r, row in zip(res["rows"], v["rows"]):
            before = _combine(_before(row, field))
            assert _combine(r["after"]).count(repl) >= before.count(_combine(find)), (v, r)


def test_property_7_changed_counts_the_rows_not_flagged_unchanged(core):
    rnd = random.Random(107)
    vs = [gen_vector(rnd) for _ in range(300)]
    for v, res in zip(vs, _results(core, vs)):
        field = v["spec"]["field"]
        assert res["changed"] == sum("unchanged" not in r["flags"] for r in res["rows"]), v
        for r, row in zip(res["rows"], v["rows"]):
            before = _combine(_before(row, field))
            if "unchanged" not in r["flags"]:
                same = before if field == "name" else py_written_note(before)
                assert r["after"] != same and r["after"] != before, (v, r)
            else:
                assert r["after"] == before, (v, r)    # verbatim, dirty or not


def test_property_8_note_over_limit_iff_the_note_bytes_exceed_the_limit(core):
    rnd = random.Random(108)
    vs = [gen_vector(rnd, field="desc") for _ in range(300)]
    for v, res in zip(vs, _results(core, vs)):
        limit = v["ctx"]["noteLimit"]
        for r in res["rows"]:
            over = "unchanged" not in r["flags"] and utf8_len(r["after"]) > limit
            assert ("note-over-limit" in r["flags"]) == over, (v, r)
    rnd = random.Random(1080)
    vs = [gen_vector(rnd, field="name") for _ in range(100)]
    for v, res in zip(vs, _results(core, vs)):
        assert not any("note-over-limit" in r["flags"] for r in res["rows"]), v


_FOLD_EXCLUDED = set("İı\u212a\u017f")


def test_property_9_match_case_on_changes_a_subset_of_the_rows_it_changes_off(core):
    """For finds that can't overlap themselves: 1 to 4 ASCII letters and digits, all
    different ignoring case (no İ, ı, Kelvin K or long s either: the odd cases of "iu"
    folding). A self-overlapping find breaks the subset by left-to-right matching
    (test_match_case_on_can_change_a_row_that_match_case_off_leaves_alone)."""
    rnd = random.Random(109)
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    pairs = []
    while len(pairs) < 300:
        v = gen_vector(rnd, mode="replace")
        n = rnd.randint(1, 4)
        chars = rnd.sample("abcdefghijklmnopqrstuvwxyz0123456789", n)
        find = "".join(c.upper() if rnd.random() < 0.5 else c for c in chars)
        field = v["spec"]["field"]
        if rnd.random() < 0.7:    # plant a case variant so there is something to match
            r0 = rnd.choice(v["rows"])
            variant = "".join(rnd.choice([c.lower(), c.upper()]) for c in find)
            r0[field] = (r0.get(field) or "") + rnd.choice(["", " "]) + variant
        if any(c in _FOLD_EXCLUDED for row in v["rows"] for c in (row.get(field) or "")):
            continue
        repl = "".join(rnd.choice(letters) for _ in range(rnd.randint(0, 3)))
        on = {**v, "spec": {**v["spec"], "find": find, "repl": repl, "matchCase": True}}
        off = {**v, "spec": {**v["spec"], "find": find, "repl": repl, "matchCase": False}}
        pairs += [on, off]
    res = _results(core, pairs)
    for i in range(0, len(pairs), 2):
        on_changed = {r["uid"] for r in res[i]["rows"] if "unchanged" not in r["flags"]}
        off_changed = {r["uid"] for r in res[i + 1]["rows"] if "unchanged" not in r["flags"]}
        assert on_changed <= off_changed, pairs[i]


def test_property_10_transform_never_throws(core):
    rnd = random.Random(110)
    vs = [gen_vector(rnd) for _ in range(280)]
    odd_rows = [None, [], [{"uid": "u0"}], [{"uid": "u0", "name": None, "desc": None}],
                [{"uid": "u0", "name": 42, "desc": 7}], [{"uid": "u0", "name": "Camp"}]]
    odd_specs = [None, {}, {"field": "name", "mode": "bogus"}, {"field": "desc", "mode": "set"},
                 {"field": "name", "mode": "replace", "find": "a"},
                 {"field": "other", "mode": "prefix", "text": "x"},
                 spec("set", text="x"), spec("replace", find="(", repl="$")]
    for rows in odd_rows:
        for sp in odd_specs[:4]:
            vs.append({"rows": rows, "spec": sp, "ctx": {"noteLimit": LIMIT}})
    for sp in odd_specs[4:]:
        vs.append({"rows": [_row(uid="u0", name="Camp (a)")], "spec": sp, "ctx": {"noteLimit": LIMIT}})
    for (label, text) in NAUGHTY:
        vs.append({"rows": [_row(uid="u0", name=text, desc=text)],
                   "spec": spec("replace", find=text, repl=text[::-1]), "ctx": {"noteLimit": LIMIT}})
    out = _run(core, vs)
    bad = [(v, r["error"]) for v, r in zip(vs, out) if not r["ok"]]
    assert not bad, bad[:3]


def test_property_11_a_blank_name_comes_only_from_a_blank_cleaned_result(core):
    rnd = random.Random(111)
    vs = []
    for _ in range(300):
        v = gen_vector(rnd, field="name")
        if rnd.random() < 0.3:     # steer toward blank results
            v["spec"] = spec("replace", find="", repl=rnd.choice([" ", "\t", "\n \n", "\x01", "\u3000 "]),
                             field="name")
        vs.append(v)
    for v, res in zip(vs, _results(core, vs)):
        sp = v["spec"]
        typed = sp["text"] + sp["find"] + sp["repl"]
        for r, row in zip(res["rows"], v["rows"]):
            before = _before(row, "name")
            if r["after"] == "":
                assert ("unchanged" in r["flags"]) == (before == ""), (v, r)
                assert "note-over-limit" not in r["flags"]
            if "Untitled" in r["after"]:
                assert "Untitled" in before or "Untitled" in typed, (v, r)


def test_property_12_flags_are_only_the_three_known_ones(core):
    """No "empty" (UI-39, names optional), no duplicate flag (UI-39); "unchanged" stands alone."""
    rnd = random.Random(112)
    vs = [gen_vector(rnd) for _ in range(300)]
    for v, res in zip(vs, _results(core, vs)):
        for r in res["rows"]:
            assert set(r["flags"]) <= FLAGS and len(r["flags"]) == len(set(r["flags"])), (v, r)
            if "unchanged" in r["flags"]:
                assert r["flags"] == ["unchanged"], (v, r)


def test_property_chars_removed_iff_the_raw_value_held_a_forbidden_character(core):
    """For Add before, Add after and Replace the note, where the raw value is known:
    chars-removed is set on a changed row exactly when the text or the value held a
    character XML forbids (ENG-09)."""
    rnd = random.Random(113)
    vs = [gen_vector(rnd, mode=rnd.choice(["prefix", "suffix", "set"])) for _ in range(330)]
    vs = [v for v in vs if not (v["spec"]["mode"] == "set" and v["spec"]["field"] == "name")][:300]
    for v, res in zip(vs, _results(core, vs)):
        sp = v["spec"]
        field, mode, text = sp["field"], sp["mode"], sp["text"]
        join = "" if field == "name" else "\n"
        for r, row in zip(res["rows"], v["rows"]):
            before = _before(row, field)
            raw = (text + join + before if mode == "prefix" else before + join + text if mode == "suffix"
                   else text)
            if "unchanged" in r["flags"]:
                assert "chars-removed" not in r["flags"]
            else:
                dirty = bool(_XML_INVALID_RE.search(_combine(raw)))
                assert ("chars-removed" in r["flags"]) == dirty, (v, r)
