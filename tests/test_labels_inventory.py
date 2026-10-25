"""docs/design/LABELS.md lists every label the app shows (owner, 2026-10-25).

This pins the static half: every button, link, heading, field label, menu
item, placeholder and aria-label in web/index.html must appear in LABELS.md,
so a new or renamed control fails here until the inventory is updated in the
same commit. Labels built in app.js and bridge.py are listed in LABELS.md by
hand; review them there when those files change.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "web" / "index.html"
LABELS = ROOT / "docs" / "design" / "LABELS.md"

TEXT_TAGS = {"button", "a", "h1", "h2", "h3", "label", "summary", "th"}
ATTRS = ("aria-label", "placeholder", "title")


class _Labels(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found: set[str] = set()
        self._stack: list[list] = []      # [tag, text parts] for open text tags
        self._skip = 0                    # inside <script>/<style>/<svg>

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "svg"):
            self._skip += 1
        for k in ATTRS:
            if a.get(k):
                self.found.add(a[k])
        if tag in TEXT_TAGS or a.get("role") == "menuitem":
            self._stack.append([tag, []])

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg"):
            self._skip = max(0, self._skip - 1)
        if self._stack and self._stack[-1][0] == tag:
            _, parts = self._stack.pop()
            text = " ".join("".join(parts).split())
            if text:
                self.found.add(text)
            if self._stack:              # a label's text also belongs to its parent
                self._stack[-1][1].extend(parts)

    def handle_data(self, data):
        if self._stack and not self._skip:
            self._stack[-1][1].append(data)


def _norm(s: str) -> str:
    return " ".join(s.replace("…", "...").replace(" ", " ").split()).lower()


def static_labels() -> set[str]:
    p = _Labels()
    p.feed(INDEX.read_text(encoding="utf-8"))
    # Help prose sits in <p>/<li>, not collected; long sentences in collected
    # tags (a heading of 80+ chars) are prose too.
    return {s for s in p.found if len(s) <= 80}


def test_every_static_label_in_index_html_is_in_the_inventory():
    inventory = _norm(LABELS.read_text(encoding="utf-8"))
    missing = sorted(s for s in static_labels() if _norm(s) not in inventory)
    assert not missing, (
        "Labels in web/index.html missing from docs/design/LABELS.md "
        "(add them in the same commit):\n  " + "\n  ".join(missing))


def test_the_collector_sees_the_main_controls():
    # Guards the parser itself: if these vanish the check above is vacuous.
    found = static_labels()
    for must in ("Choose file…", "Export", "Start over", "Move to…", "Use note as name",
                 "Download all", "Name or note"):
        assert must in found, must
