"""Pinned vectors and round-trip data for the bulk rename and note change tests.

Python literals only (docs/plans/BULK_RENAME.md 6.1 and 6.6), never a file under
tests/fixtures/. Three kinds of data live here:

* ``item_map``: a CalTopo GeoJSON map whose items carry the names and notes a test
  wants (tests/hardening_maps.make_map names folders, not items). Generated at test
  time, so no fixture file joins tests/test_input_check.EXPECTED.
* ``ROUND_TRIP_NAMES`` / ``ROUND_TRIP_NOTES``: (label, before, spec, after) where
  ``after`` was derived by hand from the core's rules (plan 3.1). The bridge tests
  store these ``after`` values with apply_edits and follow them through the writer and
  the onX reader; tests/web/test_rename_core.py checks every one against the real
  core, so the hand derivation can't drift from the code.
* ``PINNED``: named regressions. A vector that once broke a property, or an edge the
  plan got wrong, is kept here by name with what it must give.
"""
from __future__ import annotations

import json
import re

from tests.hardening_maps import _folder, _line, _poly, _pt


# The core's cleaning rules in Python (web/rename.js: xmlSafe, writtenNote, cleanName,
# cleanNote). tests/web/test_rename_core.py checks them against the JS on 300 random
# strings; the bridge tests use them to say what the core stores for a given input.
XML_INVALID_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff\ud800-\udfff]")
# What JS String.prototype.trim removes: WhiteSpace and LineTerminator. It includes
# U+FEFF and NBSP and excludes U+0085, unlike Python's str.strip(); writtenNote also
# trims an outer U+0085 so a note is stored as the writer writes it (Track A).
JS_TRIM = ("\t\n\x0b\x0c\r \u00a0\u1680" + "".join(map(chr, range(0x2000, 0x200b)))
            + "\u2028\u2029\u202f\u205f\u3000\ufeff")


def py_xml_safe(s):
    return XML_INVALID_RE.sub("", s)


def py_written_note(s):
    return re.sub(r"\r\n?", "\n", s).strip(JS_TRIM + "\x85")


def py_clean_name(s):
    return re.sub(r"[ \t]*[\r\n\t][ \t\r\n]*", " ", py_xml_safe(s)).strip(JS_TRIM)


def py_clean_note(s):
    return py_written_note(py_xml_safe(s))


def spec(mode: str, text: str = "", find: str = "", repl: str = "", match_case: bool = False,
         field: str = "name") -> dict:
    """The core's spec (plan 3.1) as a dict, with every key present."""
    return {"field": field, "mode": mode, "text": text, "find": find, "repl": repl,
            "matchCase": match_case}


def item_map(rows, folder: str = "Bulk") -> str:
    """A CalTopo GeoJSON map: one folder holding one item per row.

    rows: iterable of (kind, name, note) with kind "w" (waypoint), "l" (line) or "a"
    (area). Coordinates differ per item, so nothing is a geometry duplicate.
    """
    feats = [_folder("f0", folder)]
    for i, (kind, name, note) in enumerate(rows, 1):
        if kind == "w":
            f = _pt(i, "f0", title=name, desc=note)
        elif kind == "l":
            f = _line(i, "f0", desc=note)
        elif kind == "a":
            f = _poly(i, "f0", holes=0)
        else:
            raise ValueError(f"unknown kind {kind!r}")
        f["properties"]["title"] = name
        f["properties"]["description"] = note
        feats.append(f)
    return json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False)


# The Campsite normalisation (plan 2, decision 1): Find "" + Replace with "Campsite".
CAMPSITES = ["Campsite - Oct 9th (rainy)", "Campsite - Oct 10th",
             "Campsite - Oct 11th-12th (stay two days)"]

# Twins that differ only in case or outer space (hardening_maps.NASTY_NAMES' first four).
TWINS = ["Camp", "camp", "CAMP", " Camp "]


# (label, before, spec, after): names. after is what the core returns, by hand from 3.1.
ROUND_TRIP_NAMES = [
    ("prefix_plain", "Camp A", spec("prefix", text="Base "), "Base Camp A"),
    ("suffix_rtl", "مجلد عربي", spec("suffix", text=" 2"), "مجلد عربي 2"),
    ("find_cjk", "日本語の山", spec("replace", find="山", repl="岳"), "日本語の岳"),
    ("prefix_keeps_rtl_override", "a\u202eb", spec("prefix", text="x"), "xa\u202eb"),
    ("prefix_keeps_paired_emoji", "a🔥b", spec("prefix", text="x"), "xa🔥b"),
    ("prefix_keeps_zwsp_and_inner_bom", "Ca\ufeffmp\u200b X", spec("prefix", text="x"),
     "xCa\ufeffmp\u200b X"),
    ("prefix_keeps_c1_inside", "a\x85b", spec("prefix", text="x"), "xa\x85b"),
    ("prefix_keeps_nbsp_inside", "Camp\u00a0A", spec("prefix", text="x"), "xCamp\u00a0A"),
    ("prefix_keeps_xml_specials", "]]> & < > \" '", spec("prefix", text="x"), "x]]> & < > \" '"),
    ("prefix_keeps_entity_text", "&amp; &lt;b&gt;", spec("prefix", text="x"), "x&amp; &lt;b&gt;"),
    ("prefix_strips_controls", "\x00Camp\x01\x1f", spec("prefix", text="x"), "xCamp"),
    ("prefix_collapses_tab_and_newline", "Camp\tA \n B", spec("prefix", text="x"), "xCamp A B"),
    ("prefix_keeps_space_runs", "Camp  A", spec("prefix", text="x"), "xCamp  A"),
    ("prefix_long_3000", "Camp", spec("prefix", text="x" * 3000), "x" * 3000 + "Camp"),
    # Find matches whole words only (tracker 7.4 W1), so the find stands alone in "b a b".
    ("dollar_patterns_literal", "b a b", spec("replace", find="a", repl="$&$1$$$`$'"),
     "b $&$1$$$`$' b"),
    ("backslashes_literal", "a\\b", spec("replace", find="\\", repl="\\\\"), "a\\\\b"),
    ("regex_specials_literal", "x.*+?^$()[]{}|y", spec("replace", find=".*+?^$()[]{}|", repl="-"),
     "x-y"),
    ("overlapping_left_to_right", "aa aa aa", spec("replace", find="aa aa", repl="b"), "b aa"),
    ("match_case_off_both", "Camp camp", spec("replace", find="camp", repl="Site"), "Site Site"),
    ("match_case_on_one", "Camp camp", spec("replace", find="camp", repl="Site", match_case=True),
     "Camp Site"),
    ("final_sigma_case_off", "σ σ ς", spec("replace", find="σ", repl="s"), "s s s"),
    ("turkish_dotted_i", "İstanbul", spec("replace", find="İSTANBUL", repl="Istanbul"), "Istanbul"),
    ("empty_find_whole_value", CAMPSITES[0], spec("replace", repl="Campsite"), "Campsite"),
    ("empty_find_whitespace_is_blank", "Camp B", spec("replace", repl="  "), ""),
    ("find_consumes_the_name", "Camp", spec("replace", find="Camp"), ""),
    ("whitespace_result_is_blank", "Camp", spec("replace", find="Camp", repl=" \t\n "), ""),
    ("trim_keeps_inner_spaces", "X Camp A", spec("replace", find="Camp", repl="  "), "X    A"),
    # "x" followed by its accent is one word, so the mark is a word of its own here.
    ("combining_mark_left_alone", "x \u0301", spec("replace", find="x"), "\u0301"),
    ("emoji_only", "Camp", spec("replace", repl="🔥"), "🔥"),
    ("typed_untitled", "Camp", spec("replace", repl="Untitled"), "Untitled"),
    ("typed_no_name", "Lake", spec("replace", repl="(no name)"), "(no name)"),
    ("twin_lower", "camp", spec("prefix", text="Base "), "Base camp"),
    ("twin_outer_spaces", " Camp ", spec("prefix", text="Base "), "Base  Camp"),
]

# (label, before, spec, after): notes. Prefix/suffix join with "\n" (plan 3.1).
ROUND_TRIP_NOTES = [
    ("note_prefix", "line1\nline2", spec("prefix", text="Top", field="desc"), "Top\nline1\nline2"),
    ("note_suffix_keeps_tab", "line1\n\tline2", spec("suffix", text="!", field="desc"),
     "line1\n\tline2\n!"),
    ("note_suffix_keeps_c1_inside", "a\x85b", spec("suffix", text="!", field="desc"), "a\x85b\n!"),
    ("note_set_html_looking", "old", spec("set", text="see <b>north</b> of <Lake>", field="desc"),
     "see <b>north</b> of <Lake>"),
    ("note_set_crlf_and_cr", "", spec("set", text="a\r\nb\rc", field="desc"), "a\nb\nc"),
    ("note_find_across_a_line_break", "see north\nof lake",
     spec("replace", find="north\nof", repl="south of", field="desc"), "see south of lake"),
    ("note_set_emoji_straddling_512", "", spec("set", text="a" * 510 + "🔥", field="desc"),
     "a" * 510 + "🔥"),
    ("note_empty_find_whole_value", "old note", spec("replace", repl="see north", field="desc"),
     "see north"),
    ("note_set_blank_clears", "abc", spec("set", text="  \n ", field="desc"), ""),
    ("note_prefix_strips_controls", "abc", spec("prefix", text="\x02x", field="desc"), "x\nabc"),
    ("note_dollar_literal", "a", spec("replace", find="a", repl="$'", field="desc"), "$'"),
    ("note_set_xml_specials", "", spec("set", text="]]> & < > \" '", field="desc"), "]]> & < > \" '"),
    ("note_prefix_onx_desc_block", "x", spec("prefix", text="name=evil\nnotes=y", field="desc"),
     "name=evil\nnotes=y\nx"),
]

# Named regressions: {label: (rows, spec, expected)}. rows are (name, note) pairs;
# expected is [(after, flags)] per row, flags as a set. Each has a test of its own in
# tests/web/test_rename_core.py that says why it is here.
PINNED = {
    # Left-to-right matching: with Match case off "Aa aa" matches at 0 and blocks the
    # match at 3, so the replacement rewrites "Aa aa" to itself and the row is unchanged;
    # with it on, "aa aa" matches at 3 and the row changes. So rows changed with Match case
    # on are NOT always a subset of those changed with it off (plan 6.1 property 9). Whole
    # words since tracker 7.4 W1 (it was "Aaa" find "aa", which no longer matches at all).
    "match_case_overlap_on": ([("Aa aa aa", "")], spec("replace", find="aa aa", repl="Aa aa", match_case=True),
                              [("Aa Aa aa", set())]),
    "match_case_overlap_off": ([("Aa aa aa", "")], spec("replace", find="aa aa", repl="Aa aa"),
                               [("Aa aa aa", {"unchanged"})]),
}
