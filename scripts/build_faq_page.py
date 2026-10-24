"""Generate web/faq.html from docs/FAQ.md (the source of truth).

    uv run python scripts/build_faq_page.py            # rewrite web/faq.html
    uv run python scripts/build_faq_page.py --check    # exit 1 if web/faq.html is stale

Deterministic: same FAQ.md in, byte-identical HTML out. Handles only the Markdown
subset FAQ.md uses (#/##/### headings, paragraphs, - and 1. lists, one pipe
table, **bold**, *italic*, `code`, and an image alone on its line,
![alt](../web/<path>), which may come before the first ## as the page's lead). Anything else raises rather than rendering
wrongly, so a new construct in the FAQ is noticed here.
"""
import html, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "FAQ.md"
DST = ROOT / "web" / "faq.html"

CAIRN_MARK = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="1.6" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M5 20h14M7 20l2-5h6l2 5M9 15l1.5-4h3L15 15M10.5 11 12 7l1.5 4"/></svg>')


def inline(text: str) -> str:
    if text.count("`") % 2:
        raise ValueError(f"unbalanced backtick: {text!r}")
    codes = []

    def stash(m):
        codes.append("<code>" + html.escape(m.group(1), quote=False) + "</code>")
        return f"\x00{len(codes) - 1}\x00"

    s = re.sub(r"`([^`]*)`", stash, text)
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)


IMG = re.compile(r"^!\[([^\]]+)\]\((\.\./web/[^)\s]+)\)$")


def image_size(path: pathlib.Path) -> tuple:
    """(width, height) of a WebP or PNG, from its header (no image library)."""
    b = path.read_bytes()[:40]
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        kind = b[12:16]
        if kind == b"VP8 ":
            return (int.from_bytes(b[26:28], "little") & 0x3FFF,
                    int.from_bytes(b[28:30], "little") & 0x3FFF)
        if kind == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
        if kind == b"VP8X":
            return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    raise ValueError(f"not a PNG or WebP: {path}")


def figure(alt: str, src: str) -> str:
    """docs/FAQ.md links ../web/<path> (renders on GitHub); web/faq.html, <path>.
    Click to open it full size: the diagram is wider than the column."""
    path = ROOT / "web" / src[len("../web/"):]
    w, h = image_size(path)
    rel = html.escape(src[len("../web/"):])
    return (f'<figure class="doc-fig"><a href="{rel}"><img src="{rel}" alt="{html.escape(alt)}" '
            f'width="{w}" height="{h}"></a></figure>')


def slug(text: str, used: set) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-") or "section"
    base, n = s, 2
    while s in used:
        s, n = f"{base}-{n}", n + 1
    used.add(s)
    return s


def cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(md: str):
    """-> (title, lead, [(h2 text, [(h3 text or None, [block...])])]) with blocks
    as HTML strings; lead is the images between the title and the first ##."""
    lines = md.split("\n")
    title, sections, lead = None, [], []
    para, i = [], 0

    def cur_blocks():
        if not sections:
            raise ValueError("content before first ## heading")
        if not sections[-1][1]:
            sections[-1][1].append((None, []))
        return sections[-1][1][-1][1]

    def flush():
        nonlocal para
        if para:
            cur_blocks().append("<p>" + inline(" ".join(p.strip() for p in para)) + "</p>")
            para = []

    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            flush(); i += 1; continue
        if ln.startswith("# "):
            flush(); title = ln[2:].strip(); i += 1; continue
        if ln.startswith("## "):
            flush(); sections.append((ln[3:].strip(), [])); i += 1; continue
        if ln.startswith("### "):
            flush()
            if not sections:
                raise ValueError("### before any ##")
            sections[-1][1].append((ln[4:].strip(), [])); i += 1; continue
        if ln.startswith("#"):
            raise ValueError(f"unsupported heading: {ln!r}")
        m = IMG.match(ln)
        if m:
            flush()
            (cur_blocks() if sections else lead).append(figure(m.group(1), m.group(2)))
            i += 1; continue
        if ln.startswith("!["):
            raise ValueError(f"unsupported image (alt text and a ../web/ path, alone on a line): {ln!r}")
        m = re.match(r"^(-|\d+\.) ", ln)
        if m:
            flush()
            ordered = m.group(1) != "-"
            items = []
            while i < len(lines) and lines[i].strip():
                mm = re.match(r"^(-|\d+\.) (.*)", lines[i])
                if mm:
                    items.append(mm.group(2))
                elif lines[i].startswith("  "):
                    items[-1] += " " + lines[i].strip()
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            cur_blocks().append(f"<{tag}>" + "".join(f"<li>{inline(t)}</li>" for t in items) + f"</{tag}>")
            continue
        if ln.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            head, rule, body = cells(rows[0]), rows[1], [cells(r) for r in rows[2:]]
            if not re.fullmatch(r"[|\s:-]+", rule):
                raise ValueError("table without header rule")
            t = ('<div class="tbl-wrap"><table class="tbl"><thead><tr>'
                 + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                 + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
                 + "</tbody></table></div>")
            cur_blocks().append(t)
            continue
        if ln.startswith((">", "```", "    ")):
            raise ValueError(f"unsupported construct: {ln!r}")
        para.append(ln); i += 1
    flush()
    return title, lead, sections


# The shared site nav (owner feedback 2026-10-24, UI-38): the same five links,
# in the same order and markup, at the top and the bottom of every page.
# web/index.html and web/walkthrough.html carry the identical markup by hand
# (no JS includes: the CSP allows no inline script, and the doc pages have none);
# tests/web/test_web_app.py checks the three pages agree.
def site_nav(current: str, label: str) -> str:
    def cur(name):
        return ' aria-current="page"' if name == current else ""
    return (f'<nav class="site-nav" aria-label="{label}">\n'
            f'    <a href="./"{cur("app")}>App</a> &middot;\n'
            f'    <a href="./#help">Help</a> &middot;\n'
            f'    <a href="faq.html"{cur("faq")}>FAQ</a> &middot;\n'
            f'    <a href="walkthrough.html"{cur("walkthrough")}>Walkthrough</a> &middot;\n'
            f'    <a href="https://github.com/moltude/cairn" target="_blank" rel="noopener noreferrer">GitHub</a>\n'
            f'  </nav>')


def render(md: str) -> str:
    title, lead, sections = parse(md)
    used: set = set()
    toc, body = [], []
    for h2, subs in sections:
        sid = slug(h2, used)
        toc_sub = []
        parts = [f'<section class="faq-sec" id="{sid}"><h2>{inline(h2)}</h2>']
        for h3, blocks in subs:
            if h3 is None:
                parts.extend(blocks)
                continue
            qid = slug(h3, used)
            toc_sub.append(f'<li><a href="#{qid}">{inline(h3)}</a></li>')
            parts.append(f'<article class="faq-q" id="{qid}"><h3><a class="anchor" href="#{qid}" '
                         f'aria-label="Link to this question">#</a>{inline(h3)}</h3>' + "".join(blocks) + "</article>")
        parts.append("</section>")
        body.append("".join(parts))
        toc.append(f'<li><a class="toc-sec" href="#{sid}">{inline(h2)}</a><ul>' + "".join(toc_sub) + "</ul></li>")
    toc_html = "<ol>" + "".join(toc) + "</ol>"
    return f"""<!doctype html>
<!-- GENERATED FILE. Do not edit by hand.
     Source of truth: docs/FAQ.md
     Regenerate:      uv run python scripts/build_faq_page.py
     Check staleness: uv run python scripts/build_faq_page.py --check -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cairn FAQ</title>
<meta name="description" content="Answers about what Cairn does, what it can't do, and what is still unverified about the CalTopo to onX move.">
<link rel="preload" href="fonts/libre-caslon-text-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="styles.css">
</head>
<body class="docpage">
<header class="topbar">
  <a class="wordmark wordmark-link" href="./"><span class="cairn-mark">{CAIRN_MARK}</span><span>Cairn</span></a>
  {site_nav("faq", "Site")}
</header>
<div class="doc doc-faq">
  <main class="doc-main">
    <h1 class="sr-only">{inline(title)}</h1>
    {"".join(lead)}
    <nav class="doc-toc" aria-label="On this page"><span class="label">On this page</span>{toc_html}</nav>
    {"".join(body)}
  </main>
</div>
<footer class="site-foot">
  {site_nav("faq", "Site links")}
</footer>
</body>
</html>
"""


def main(argv):
    out = render(SRC.read_text(encoding="utf-8"))
    if "--check" in argv:
        if not DST.exists() or DST.read_text(encoding="utf-8") != out:
            print("web/faq.html is stale; run scripts/build_faq_page.py"); return 1
        return 0
    DST.write_text(out, encoding="utf-8")
    print(f"wrote {DST.relative_to(ROOT)} ({len(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
