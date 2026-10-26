"""Render the README's "How Cairn gets a map into onX Backcountry" diagram to
docs/images/how-cairn-works.png, at 2x.

    uv run python scripts/make_readme_diagram.py

The diagram is drawn as one SVG here (no external files), then screenshotted
by headless Chromium. Wording and layout were settled with the owner on
2026-10-25; change the text below, not the PNG.
"""
import pathlib
from html import escape
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/images/how-cairn-works.png"
FONT = '"Helvetica Neue", Helvetica, Arial, sans-serif'


C = {'ink': '#1F2933', 'sub': '#5B6775', 'faint': '#9AA5B1', 'line': '#8B97A6', 'g': '#2F8A55', 'gl': '#EAF6EF', 'gll': '#F4FAF6', 'a': '#C98A12', 'al': '#FFF6E0', 'all': '#FFFBF2', 'b': '#3B6FD8', 'bl': '#EAF1FB', 'bll': '#F5F8FD', 'r': '#C2413A', 'rl': '#FDEDEC'}


def T(x, y, s, size=15, fill="ink", w=400, anchor="middle", italic=False, strike=False):
    st = (' font-style="italic"' if italic else "") + (' text-decoration="line-through"' if strike else "")
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" text-anchor="{anchor}" fill="{C.get(fill, fill)}"{st}>{escape(s)}</text>'


def rect(x, y, w, h, stroke, fill="#fff", dash=False, rx=10, sw=1.8):
    d = ' stroke-dasharray="7 5"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{C.get(fill, fill)}" stroke="{C.get(stroke, stroke)}" stroke-width="{sw}"{d}/>'


def step(x, y, w, h, label, sub=None, kind="out", color="g", dash=False, white=False):
    """filled (Cairn) or outlined (you) box with label + sub."""
    if kind == "fill":
        s = rect(x, y, w, h, color, color, dash)
        lc, sc = "#FFFFFF", "#E6F4EC" if color == "g" else "#FFFFFF"
    else:
        s = rect(x, y, w, h, color, "#FFFFFF", dash)
        lc, sc = C["ink"], C["sub"]
    cx = x + w / 2
    if sub:
        s += T(cx, y + h / 2 - 3, label, 17, lc, 700) + T(cx, y + h / 2 + 17, sub, 13.5, sc)
    else:
        s += T(cx, y + h / 2 + 6, label, 17, lc, 700)
    return s


def arrow(pts, color="line", dash=False, w=1.8, head=True):
    d = "M" + " L".join(f"{a} {b}" for a, b in pts)
    da = ' stroke-dasharray="7 5"' if dash else ""
    mk = f' marker-end="url(#h{color})"' if head else ""
    return f'<path d="{d}" fill="none" stroke="{C.get(color, color)}" stroke-width="{w}" stroke-linejoin="round"{da}{mk}/>'


def pin(x, y, s=1.0, color="ink"):
    c = C.get(color, color)
    return (f'<g transform="translate({x},{y}) scale({s})"><path d="M0 9 C-6 2 -7 -2 -7 -4 A7 7 0 0 1 7 -4 C7 -2 6 2 0 9 Z" fill="{c}"/>'
            f'<circle cx="0" cy="-4" r="2.6" fill="#fff"/></g>')


def poly(x, y, s=1.0, color="ink"):
    c = C.get(color, color)
    return (f'<g transform="translate({x},{y}) scale({s})"><path d="M-10 6 L-4 -4 L3 3 L10 -6" fill="none" stroke="{c}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'
            + "".join(f'<circle cx="{a}" cy="{b}" r="2" fill="{c}"/>' for a, b in ((-10, 6), (-4, -4), (3, 3), (10, -6))) + "</g>")


def area(x, y, s=1.0, color="ink"):
    c = C.get(color, color)
    return (f'<g transform="translate({x},{y}) scale({s})"><path d="M-9 -5 L2 -8 L10 -1 L6 8 L-7 6 Z" fill="{c}" fill-opacity="0.18" stroke="{c}" stroke-width="2" stroke-linejoin="round"/></g>')


def folder(x, y, w, h, label=None, color="a", fill="#fff", size=14, sub=None, sub_strike=False):
    c, f = C.get(color, color), C.get(fill, fill)
    s = (f'<path d="M{x} {y+8} V{y+h} H{x+w} V{y+8} H{x+w*0.45} L{x+w*0.38} {y} H{x+6} Q{x} {y} {x} {y+6} Z" '
         f'fill="{f}" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/>')
    if label:
        s += T(x + w / 2, y + 8 + (h - 8) / 2 + 5 - (8 if sub else 0), label, size, "ink", 700)
    if sub:
        s += T(x + w / 2, y + 8 + (h - 8) / 2 + 14, sub, 11.5, "faint", 400, strike=sub_strike)
    return s


def zipg(x, y):
    return (f'<g transform="translate({x},{y})"><rect x="-8" y="-10" width="16" height="20" rx="2" fill="none" stroke="#fff" stroke-width="1.6"/>'
            + "".join(f'<path d="M-2 {v} H2" stroke="#fff" stroke-width="1.6"/>' for v in (-7, -3, 1)) + "</g>")


def filerow(x, y, glyph, name, color="ink", size=13):
    g = {"pin": pin(x + 8, y - 4, 0.8, color), "poly": poly(x + 8, y - 4, 0.75, color),
         "area": area(x + 8, y - 4, 0.75, color), "txt": f'<path d="M{x+3} {y-12} H{x+11} L{x+14} {y-9} V{y+3} H{x+3} Z" fill="none" stroke="{C.get(color,color)}" stroke-width="1.4"/>'}[glyph]
    return g + T(x + 24, y + 1, name, size, "ink", 400, "start")


def defs():
    return "<defs>" + "".join(
        f'<marker id="h{k}" orient="auto" markerWidth="9" markerHeight="9" refX="6.5" refY="4.5"><path d="M0 0.5 L8 4.5 L0 8.5 Z" fill="{C[k]}"/></marker>'
        for k in ("line", "g", "b", "a", "r")) + "</defs>"


def svg(W, H, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family=\'{FONT}\'>'
            f'{defs()}<rect width="{W}" height="{H}" fill="#fff"/>{body}</svg>')


def key(x, y, items):
    s = ""
    for kind, label in items:
        if kind == "fill":
            s += rect(x, y - 13, 26, 18, "g", "g", rx=4)
        elif kind == "out":
            s += rect(x, y - 13, 26, 18, "ink", "#fff", rx=4)
        elif kind == "dash":
            s += f'<path d="M{x} {y-4} H{x+26}" stroke="{C["line"]}" stroke-width="2" stroke-dasharray="6 4"/>'
        elif kind == "solid":
            s += f'<path d="M{x} {y-4} H{x+26}" stroke="{C["line"]}" stroke-width="2"/>'
        elif kind == "lost":
            s += rect(x, y - 13, 26, 18, "r", "rl", dash=True, rx=4, sw=1.4)
        s += T(x + 34, y, label, 14, "sub", 700, "start")
        x += 60 + len(label) * 8
    return s


def notes(x, y, lines, gap=22):
    s = ""
    for i, (head, body) in enumerate(lines):
        s += (f'<text x="{x}" y="{y+i*gap}" font-size="13.5" fill="{C["sub"]}">'
              f'<tspan font-weight="700" fill="{C["ink"]}">{escape(head)}</tspan>  {escape(body)}</text>')
    return s


FILES = (("pin", "Waypoints.gpx"), ("poly", "Lines.gpx"), ("area", "Areas.gpx"))


def tag(x, y, text, color="b", w=None):
    w = w or (len(text) * 6.6 + 16)
    return f'<rect x="{x}" y="{y}" width="{w}" height="18" rx="9" fill="{C[color]}"/>' + T(x + w / 2, y + 13, text, 11.5, "#fff", 700)


def lost(x, y, w=210):
    return (rect(x, y, w, 66, "r", "rl", dash=True, rx=8, sw=1.4)
            + T(x + w / 2, y + 21, "Cairn warns you about", 13, "ink", 700)
            + T(x + w / 2, y + 38, "what the onX import loses:", 13, "ink", 700)
            + T(x + w / 2, y + 56, "Area fill · long names and notes", 12, "sub"))


def export_box(x, y, w, h, sub=None, rows_gap=22, card_h=None):
    s = rect(x, y, w, h, "g", "g")
    s += T(x + w / 2, y + 30, "Export", 17, "#fff", 700) + zipg(x + w - 22, y + 22)
    top = y + 44
    if sub:
        s += T(x + w / 2, y + 52, sub, 13, "#E6F4EC")
        top = y + 68
    ch = card_h or (h - (top - y) - 40)
    # a second folder behind, then the open one in front
    s += folder(x + 70, top, w - 84, ch, color="g", fill="#fff")
    s += T(x + 84, top + 20, "Wind River", 12, "g", 700, "start")
    top += 30
    s += folder(x + 14, top, w - 34, ch - 30, color="g")
    s += T(x + 30, top + 24, "Chinese Wall", 12.5, "g", 700, "start")
    for i, (gl, n) in enumerate(FILES):
        s += filerow(x + 26, top + 56 + i * rows_gap, gl, n, size=12.5)
    s += T(x + w / 2, y + h - 14, "Splits files over onX's import limit", 12, "#fff")
    return s


def step3(x, y, w, h, label, subs, kind, color):
    s = step(x, y, w, h, label, None, kind, color)
    s = s[:s.rfind("<text")]
    lc, sc = ("#FFFFFF", "#E6F4EC") if kind == "fill" else (C["ink"], C["sub"])
    n = len(subs)
    y0 = y + h / 2 - n * 9.5 + 3
    s += T(x + w / 2, y0, label, 17, lc, 700)
    for i, line in enumerate(subs):
        s += T(x + w / 2, y0 + 20 * (i + 1), line, 13.5, sc)
    return s


def final2():
    W, H = 1600, 556
    L = []
    L.append(f'<rect x="450" y="88" width="890" height="26" rx="13" fill="{C["gl"]}"/>' + T(895, 106, "Cairn (in your browser)", 14, "g", 700))
    cy = 270
    for y, t, st, c, dash in ((146, "CalTopo", "GeoJSON (best), KML or GPX", "a", False),
                              (236, "onX Backcountry", "GPX and/or KML, one folder", "b", True),
                              (326, "Any other app", "GeoJSON, KML or GPX", "a", False)):
        L.append(step(40, y, 260, 70, t, st, "out", c, dash=dash))
        L.append(arrow([(300, y + 35), (370, y + 35), (370, cy)], head=False))
    L.append(tag(52, 227, "onX round trip only"))
    L.append(arrow([(370, cy), (446, cy)]))
    # Load: two separate things, as bullets
    L.append(rect(450, cy - 50, 260, 100, "g", "g") + T(580, cy - 18, "Load", 17, "#fff", 700))
    for i, line in enumerate(("Best-effort glyph and color match", "onX files come in 1:1")):
        y = cy + 8 + i * 22
        L.append(f'<circle cx="474" cy="{y - 4.5}" r="2.6" fill="#E6F4EC"/>' + T(484, y, line, 13.5, "#E6F4EC", 400, "start"))
    L.append(step3(735, cy - 55, 180, 110, "Edit", ["Waypoint · line · area", "Color, style and glyph", "Name and notes"], "out", "g"))
    L.append(pin(785, 350) + poly(825, 350) + area(865, 350))
    L.append(step3(940, cy - 50, 170, 100, "Group into folders", ["Drag and drop"], "out", "g"))
    L.append(f'<circle cx="1102" cy="{cy-42}" r="10" fill="{C["g"]}"/>' + T(1102, cy - 37, "1", 12, "#fff", 700))
    L.append(folder(988, 338, 34, 24, color="g") + folder(1040, 338, 34, 24, color="g") + arrow([(1020, 332), (1038, 332)], "g", w=1.4))
    for a, b in ((710, 731), (915, 936), (1110, 1126)):
        L.append(arrow([(a, cy), (b, cy)], "g"))
    L.append(export_box(1130, 140, 210, 330, sub="One zip, every folder inside", rows_gap=40))
    L.append(arrow([(1340, cy), (1406, cy)], "b", w=2.4) + T(1373, cy - 14, "GPX files", 12, "sub", 700))
    L.append(step(1410, cy - 45, 160, 90, "Import", None, "out", "b"))
    L.append(lost(1362, 130, 210))
    L.append(step(1360, 424, 220, 66, "Delete originals", "onX adds copies, never updates", "out", "b", dash=True))
    L.append(f'<circle cx="1570" cy="432" r="10" fill="{C["b"]}"/>' + T(1570, 437, "2", 12, "#fff", 700))
    L.append(arrow([(1340, 457), (1356, 457)], dash=True))
    L.append(arrow([(1490, 424), (1490, cy + 49)], dash=True))
    L.append(notes(30, 548, [("1", "Each Cairn folder becomes one onX folder. onX names it by date; rename it to the name in instructions.txt."),
                             ("2", "onX round trip only: clean up what's already in onX. Keep the onX export as a backup before deleting.")]))
    L.append(key(1200, 600, [("solid", "Every map"), ("dash", "onX round trip only")]))
    # no title: shift everything up into the space it took
    return svg(W, H, '<g transform="translate(0,-62)">' + "".join(L) + "</g>"), W, H


def main():
    s, W, H = final2()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        pg.set_content(f"<!doctype html><body style='margin:0'>{s}</body>")
        pg.locator("svg").screenshot(path=str(OUT))
        b.close()
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
