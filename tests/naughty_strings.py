"""Naughty strings for the bulk rename and note change tests.

A Python module, like tests/hardening_maps.py, and deliberately not a file under
tests/fixtures/: anything there has to be listed in tests/test_input_check.EXPECTED and
is swept by its every-fixture checks. Each entry is (label, text); the label is the
pytest id, so a failure reads ``[rtl_arabic]`` or ``[zwj_family]``.

No entry holds a lone surrogate. A Python str can, but it can't be encoded as UTF-8, so
it can't reach the bridge (json.dumps, /tmp writes) or cross Playwright's protocol as a
string. The core tests build lone surrogates in JS or send UTF-16 code units instead.
"""
from __future__ import annotations

NAUGHTY: list[tuple[str, str]] = [
    # Blank and whitespace
    ("empty", ""),
    ("one_space", " "),
    ("spaces_only", "     "),
    ("tab_only", "\t"),
    ("newlines_only", "\n\r\n\r"),
    ("nbsp_only", "\u00a0"),
    ("ideographic_space", "\u3000"),
    ("line_and_paragraph_separators", "a\u2028b\u2029c"),
    ("outer_spaces", "  Camp  "),
    ("inner_space_run", "Camp  A"),
    ("tab_inside", "Camp\tA"),
    ("crlf_inside", "line1\r\nline2"),
    ("lone_cr_inside", "line1\rline2"),
    # Characters XML 1.0 forbids (the writer and the core drop them)
    ("nul", "a\x00b"),
    ("c0_controls", "\x01\x02\x03Camp\x1e\x1f"),
    ("backspace_and_form_feed", "a\x08b\x0cc"),
    ("vertical_tab", "a\x0bb"),
    ("fffe_and_ffff", "a\ufffeb\uffff"),
    # Legal XML that looks dangerous (kept as user data, ENG-06)
    ("del", "a\x7fb"),
    ("c1_next_line", "a\x85b"),
    ("c1_range", "\x80\x9f"),
    ("zero_width_space", "Camp\u200bA"),
    ("bom_inside", "Ca\ufeffmp"),
    ("zwnj_and_zwj", "a\u200cb\u200dc"),
    ("lrm_rlm", "a\u200eb\u200fc"),
    ("rtl_override", "a\u202eb"),
    ("bidi_isolates", "\u2066a\u2069\u2067b\u2069"),
    ("noncharacter_fdd0", "a\ufdd0b"),
    ("private_use", "\ue000\uf8ff"),
    ("max_code_point", "a\U0010ffffb"),
    ("variation_selector_alone", "\ufe0f"),
    ("skin_tone_alone", "\U0001f3fd"),
    # Scripts
    ("rtl_arabic", "مجلد عربي"),
    ("rtl_hebrew", "עברית"),
    ("mixed_direction", "Camp مخيم 2"),
    ("cjk", "日本語の山"),
    ("korean", "한국어 캠프"),
    ("thai", "ภาษาไทย"),
    ("devanagari", "हिन\u094dदी"),
    ("greek_sigmas", "Οδυσσεύς ΣΑΣ"),
    ("turkish_i", "İstanbul ılık"),
    ("eszett", "Straße STRASSE ẞ"),
    ("kelvin_and_long_s", "\u212a \u017f"),
    ("fullwidth", "Ｃａｍｐ\u3000Ａ"),
    ("halfwidth_katakana", "ｶﾀｶﾅ"),
    ("math_alphanumeric", "\U0001d54f\U0001d550"),
    # Combining marks and normal forms
    ("nfc_umlaut", "Zürich"),
    ("nfd_umlaut", "Zu\u0308rich"),
    ("combining_only", "\u0301\u0308"),
    ("zalgo", "C\u0336\u0353a\u0337\u0359m\u0338\u031cp\u0335\u0347"),
    # Emoji
    ("emoji", "Peak 🏔\ufe0f🔥"),
    ("emoji_only", "🔥"),
    ("zwj_family", "👨\u200d👩\u200d👧"),
    ("flag", "🇺🇸"),
    ("skin_tone", "👍🏽"),
    ("keycap", "1\ufe0f\u20e3"),
    # XML and HTML specials
    ("xml_specials", "<>&\"'"),
    ("cdata_terminator", "]]>"),
    ("cdata_section", "<![CDATA[x]]>"),
    ("entity_text", "&amp; &lt;b&gt; &#0; &#x1F525;"),
    ("doctype_text", "<!DOCTYPE x [<!ENTITY y \"z\">]>"),
    ("processing_instruction", "<?xml version=\"1.0\"?>"),
    ("html_bold", "see <b>north</b> of <Lake>"),
    ("script_tag", "<script>alert(1)</script>"),
    ("img_onerror", "<img src=x onerror=alert(1)>"),
    # Regex and replacement patterns
    ("regex_specials", ".*+?^$()[]{}|\\"),
    ("dollar_patterns", "$&$1$$$`$'"),
    ("backslashes", "\\\\n\\t\\"),
    # Code-looking text
    ("format_strings", "%s %d {0} {name} ${x}"),
    ("sql", "'; DROP TABLE markups; --"),
    ("path_traversal", "../../etc/passwd"),
    ("windows_reserved", "CON"),
    ("json_text", "{\"a\": [1, null]}"),
    ("prototype_key", "__proto__"),
    ("constructor_key", "constructor"),
    ("number_like", "1e309"),
    ("onx_desc_block", "name=evil\nnotes=x\nid=1"),
    ("markdown", "# Title **bold** - [ ] item"),
    ("curly_quotes", "“Camp” ‘A’"),
    # The app's own words
    ("untitled_word", "Untitled"),
    ("no_name_word", "(no name)"),
    ("no_change_word", "No change"),
    # Length
    ("long_ascii_300", "x" * 300),
    ("note_exactly_512_bytes", "a" * 512),
    ("cjk_600_bytes", "日" * 200),
    ("emoji_520_bytes", "🔥" * 130),
]

NAUGHTY_TEXTS: list[str] = [text for _label, text in NAUGHTY]
NAUGHTY_IDS: list[str] = [label for label, _text in NAUGHTY]

assert len(set(NAUGHTY_IDS)) == len(NAUGHTY_IDS), "duplicate naughty label"
assert not any(0xD800 <= ord(c) <= 0xDFFF for t in NAUGHTY_TEXTS for c in t), "lone surrogate"
