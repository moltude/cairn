"""Random-action UI fuzzer for Cairn's folders feature (UI-32 / ENG-07 / UI-31).

Drives the real Pyodide app in headless Chromium and, after every action,
checks invariants against the app's own state (DATA, FILTERS, DRAG, ... via
page.evaluate) and the DOM. Periodically exports and verifies the export
screen, Download all and every per-folder zip.

Usage (from the repo root, dev server up; see scripts/qa/README.md):
  uv run python scripts/qa/fuzz_ui.py --seeds 1-10 --actions 200
  uv run python scripts/qa/fuzz_ui.py --replay archive/qa-fuzz/runs/<file>.json
  uv run python scripts/qa/fuzz_ui.py --seeds 7 --shrink

Generated maps and run records go to archive/qa-fuzz/ (gitignored; --out or
CAIRN_QA_OUT to change it). Nothing under tests/ may import this file.

Each session is (map, seed). Actions are {"t": kind, "s": subseed}: the
subseed resolves the concrete target against the CURRENT state, so a list of
actions can be replayed and shrunk (delta debugging) deterministically.
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import random
import re
import sys
import time
import traceback
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from playwright.sync_api import Error as PWError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def set_out(path) -> None:
    """Where generated maps (maps/) and run records (runs/) go."""
    global OUT, RUNS, MAPS
    OUT = Path(path).resolve()
    RUNS, MAPS = OUT / "runs", OUT / "maps"


set_out(os.environ.get("CAIRN_QA_OUT") or ROOT / "archive/qa-fuzz")
sys.path.insert(0, str(ROOT / "tests"))
from hardening_maps import make_map  # noqa: E402

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8765/").rstrip("/") + "/"
FX = ROOT / "tests/fixtures"


# --------------------------------------------------------------------------- maps
def build_maps() -> dict:
    MAPS.mkdir(parents=True, exist_ok=True)
    gen = {
        "hostile": make_map(34, seed=1, empty=3),
        "big200": make_map(200, seed=2, per=(2, 6)),
        "twins": make_map(12, seed=3, per=(1, 5), names=[
            "Camp", "camp", "CAMP", " Camp ", "A/B", "A_B", "Peak 🏔️", "日本語",
            "New folder", "new folder 2", "Unorganized", "x" * 150]),
    }
    maps = {}
    for k, text in gen.items():
        p = MAPS / f"{k}.json"
        p.write_text(text, encoding="utf-8")
        maps[k] = [p]
    maps["bitterroots"] = [FX / "bitterroots/Bitterroots__Complete_.json"]
    maps["onx_areas"] = [FX / "onx_exports/areas-after-edit.gpx", FX / "onx_exports/areas-after-edit.kml"]
    maps["onx_trips"] = [FX / "onx_exports/three-round-trips.gpx", FX / "onx_exports/three-round-trips.kml"]
    return maps


MAP_ORDER = ["bitterroots", "hostile", "twins", "big200", "onx_areas", "onx_trips"]


# --------------------------------------------------------------------------- state probes
SNAP_JS = r"""
() => {
  const out = {};
  out.stage = document.body.dataset.stage;
  if (!DATA) { out.data = null; return out; }
  out.groups = DATA.groups.map(g => ({key: g.key, name: g.name, safe: g.safe,
     uids: g.items.map(i => i.uid)}));
  out.items = {};
  DATA.groups.forEach(g => g.items.forEach(i => { out.items[i.uid] = {
     name: i.name, kind: i.kind, included: i.included !== false, desc: i.desc || ""}; }));
  try { out.bridge = JSON.parse(py.runPython('import json; json.dumps(bridge._layout())')); }
  catch (e) { out.bridge = 'ERR ' + e; }
  out.totals_folders = DATA.totals.folders;
  out.filters = {q: FILTERS.q, kind: FILTERS.kind, folder: FILTERS.folder,
                 icons: [...FILTERS.icons], attention: FILTERS.attention};
  out.collapsed = [...COLLAPSED];
  out.sel = [...SEL];
  out.drag = DRAG ? {active: !!DRAG.active, cancelled: !!DRAG.cancelled} : null;
  out.rename = RENAME ? {key: RENAME.key, where: RENAME.where} : null;
  out.move = !!MOVE; out.pop = !!POP; out.bulk = !!BULK; out.confirm = !!CONFIRM;
  out.note = NOTE_EDIT ? NOTE_EDIT.uid : null;
  const vis = s => { const e = document.querySelector(s); return !!e && !e.classList.contains('hidden'); };
  out.vis = {confirm: vis('#confirm'), move: vis('#move-pop'), pop: vis('#mark-pop'),
             bulk: vis('#mark-modal'), menu: vis('#more-menu'), help: vis('#help')};
  out.ghost = document.querySelectorAll('#drag-ghost, .drag-ghost').length;
  out.bodyDragging = document.body.classList.contains('dragging-rows');
  out.dropOver = document.querySelectorAll('.drop-over').length;
  out.trDragging = document.querySelectorAll('tr.dragging').length;
  out.hereNow = document.querySelectorAll('.here-now').length;
  out.rail = [...document.querySelectorAll('#folder-facets > *')].map(e => ({
     cls: e.className, fk: e.dataset.fk || (e.querySelector('[data-fk]') || {}).dataset?.fk || null,
     drop: e.dataset.drop ?? null,
     name: (e.querySelector('.facet-name') || {}).textContent ?? null,
     input: e.querySelector('input') ? e.querySelector('input').value : null,
     count: (e.querySelector('.facet-count') || {}).textContent ?? null}));
  // Round 4: an empty folder shows as a header only (section.empty-folder).
  out.emptySections = [...document.querySelectorAll('#folders section.folder.empty-folder')].map(s => s.getAttribute('aria-label'));
  out.expectEmpty = DATA.groups.filter(g => !g.items.length && showsEmptyFolders(g)).map(g => g.name);
  out.facetX = [...document.querySelectorAll('#folder-facets .facet-x')].map(x => x.dataset.fk.slice(7));
  out.sections = [...document.querySelectorAll('#folders section.folder:not(.empty-folder)')].map(s => ({
     label: s.getAttribute('aria-label'),
     head: (s.querySelector('.folder-name') || {}).textContent ?? null,
     headInput: !!s.querySelector('.folder-name-in'),
     collapsed: s.querySelector('.table-wrap').classList.contains('hidden'),
     rows: [...s.querySelectorAll('tbody tr[data-uid]')].map(r => r.dataset.uid)}));
  // What the app itself says should be on screen.
  out.expectVisible = DATA.groups.map(g => ({key: g.key, uids: visibleItems(g).map(i => i.uid)}));
  out.status = {text: document.querySelector('#status').textContent,
                cls: document.querySelector('#status').className};
  const a = document.activeElement;
  out.focus = a === document.body ? 'BODY' : (a ? (a.id || a.dataset?.fk || a.className || a.tagName) : null);
  out.selcount = document.querySelector('#selcount').textContent;
  return out;
}
"""


def norm(s: str) -> str:
    return (s or "").strip().casefold()


class Violation(Exception):
    def __init__(self, sig, detail):
        super().__init__(f"{sig}: {detail}")
        self.sig, self.detail = sig, detail


# --------------------------------------------------------------------------- session
class Session:
    def __init__(self, ctx, map_name, files, log):
        self.ctx, self.map_name, self.files, self.log = ctx, map_name, files, log
        self.errors = []
        self.page = None
        self.exports = 0
        self.checks = 0

    # ---- lifecycle
    def open(self):
        p = self.ctx.new_page()
        p.set_default_timeout(5000)
        p.set_viewport_size({"width": 1440, "height": 900})
        p.on("pageerror", lambda e: self.errors.append(("pageerror", str(e))))
        p.on("console", lambda m: m.type == "error" and self.errors.append(("console", m.text)))
        p.goto(BASE + "index.html")
        p.wait_for_selector('body[data-engine="ready"]', timeout=120000, state="attached")
        p.set_input_files("#file", [str(f) for f in self.files])
        p.wait_for_function("window.__cairnLoaded === true", timeout=60000)
        self.page = p
        self.settle()
        s = self.snap()
        self.total = len(s["items"])
        self.all_uids = set(s["items"])
        self.empty_at_load = {g["key"] for g in s["groups"] if not g["uids"]}
        # Round 4: folders made empty with a click on + New folder may stay
        # empty until something is moved in. A key first seen empty was made so
        # (a move can't make a new empty folder); once filled, the usual rule.
        self.seen_keys = {g["key"] for g in s["groups"]}
        self.created_empty = set()
        self.dup_names_at_load = self._dups(s)
        # onX fill warning on load: answer it like a user would.
        if s["confirm"]:
            self.answer_confirm(random.Random(0))
        self.check("load")

    def close(self):
        try:
            self.page.close()
        except Exception:
            pass

    def settle(self, ms=0):
        p = self.page
        # Two macrotask turns: finishRename / wireTextField defer their render.
        p.evaluate("() => new Promise(r => setTimeout(() => setTimeout(r, 0), 0))")
        if ms:
            p.wait_for_timeout(ms)

    def snap(self):
        return self.page.evaluate(SNAP_JS)

    @staticmethod
    def _dups(s):
        c = collections.Counter(norm(g["name"]) for g in s["groups"])
        return sum(v - 1 for v in c.values() if v > 1)

    # ---- invariants
    def check(self, label, keyboard=False):
        self.checks += 1
        if self.errors:
            kind, msg = self.errors[0]
            first = msg.strip().splitlines()[0][:160] if msg.strip() else msg
            raise Violation(f"{kind}", f"{first} || after {label} || all={self.errors[:3]}")
        s = self.snap()
        if s["stage"] == "done":
            return s
        if s.get("data") is None and "groups" not in s:
            raise Violation("data_gone", f"DATA is null after {label}")
        groups = s["groups"]
        # 1. every uid exactly once
        flat = [u for g in groups for u in g["uids"]]
        dup = [u for u, n in collections.Counter(flat).items() if n > 1]
        if dup:
            raise Violation("uid_duplicated", f"{dup[:5]} after {label}")
        if len(flat) != self.total or set(flat) != self.all_uids:
            raise Violation("item_count_changed", f"{len(flat)} vs {self.total}; missing "
                            f"{sorted(self.all_uids - set(flat))[:5]} after {label}")
        # 2. UI layout == bridge layout
        b = s["bridge"]
        if isinstance(b, str):
            raise Violation("bridge_layout_error", b)
        ui = [(g["key"], g["name"], g["uids"]) for g in groups]
        br = [(f["key"], f["name"], f["uids"]) for f in b]
        if ui != br:
            diff = [(x, y) for x, y in zip(ui, br) if x != y][:2]
            raise Violation("ui_bridge_layout_differ", f"{len(ui)} vs {len(br)} folders; {diff} after {label}")
        safes = {f["key"]: f["safe"] for f in b}
        if any(g["safe"] != safes[g["key"]] for g in groups):
            raise Violation("safe_name_stale", f"after {label}")
        # 3. no empty folder unless it loaded empty or was made empty (round 4)
        #    and has had nothing in it since
        for g in groups:
            if g["key"] not in self.seen_keys and not g["uids"]:
                self.created_empty.add(g["key"])
            if g["uids"]:
                self.created_empty.discard(g["key"]); self.empty_at_load.discard(g["key"])
        self.seen_keys |= {g["key"] for g in groups}
        allowed = self.empty_at_load | self.created_empty
        empties = [g["key"] for g in groups if not g["uids"] and g["key"] not in allowed]
        if empties:
            raise Violation("empty_folder_left", f"{empties} after {label}")
        # Every empty folder (and only those) has its x in the rail, and shows
        # as a header-only section when no filter hides it.
        # (A folder whose name is open in the rail is an input there, with no x.)
        naming = s["rename"]["key"] if s["rename"] and s["rename"]["where"] == "rail" else None
        if not s["drag"] and sorted(s["facetX"]) != sorted(g["key"] for g in groups
                                                           if not g["uids"] and g["key"] != naming):
            raise Violation("empty_folder_x", f"x on {s['facetX']} after {label}")
        if s["emptySections"] != s["expectEmpty"]:
            raise Violation("empty_folder_section", f"{s['emptySections']} vs {s['expectEmpty']} after {label}")
        # 4. totals and duplicate names
        if s["totals_folders"] != len(groups):
            raise Violation("totals_folders_stale", f"{s['totals_folders']} vs {len(groups)} after {label}")
        if self._dups(s) > self.dup_names_at_load:
            raise Violation("duplicate_folder_name", f"{[g['name'] for g in groups]} after {label}")
        # 5. rail list == DATA.groups (when no drag is live)
        rail = s["rail"]
        if not s["drag"]:
            if not rail or rail[0]["fk"] != "folder|\u0000all":
                raise Violation("rail_bad_all", f"{rail[:1]} after {label}")
            if "new-folder" not in (rail[-1]["cls"] or ""):
                raise Violation("rail_no_new_folder", f"{rail[-1:]} after {label}")
            mid = rail[1:-1]
            if len(mid) != len(groups):
                raise Violation("rail_folder_count", f"rail {len(mid)} vs {len(groups)} after {label}")
            for r, g in zip(mid, groups):
                if r["fk"] != "folder|" + g["key"]:
                    raise Violation("rail_order", f"{r['fk']} vs {g['key']} after {label}")
                if r["input"] is None:
                    if r["name"] != g["name"]:
                        raise Violation("rail_name", f"{r['name']!r} vs {g['name']!r} after {label}")
                    if r["count"] != str(len(g["uids"])):
                        raise Violation("rail_count", f"{g['name']!r}: {r['count']} vs {len(g['uids'])} after {label}")
                elif not (s["rename"] and s["rename"]["where"] == "rail" and s["rename"]["key"] == g["key"]):
                    raise Violation("rail_stray_input", f"{g['key']} after {label}")
        # 6. visible rows: DOM == visibleItems for expanded folders, and the
        #    filters hold independently of the app's own filter function.
        f = s["filters"]
        exp = [(e["key"], e["uids"]) for e in s["expectVisible"] if e["uids"]]
        secs = s["sections"]
        if len(secs) != len(exp):
            raise Violation("sections_mismatch", f"{len(secs)} sections vs {len(exp)} expected after {label}")
        gname = {g["key"]: g["name"] for g in groups}
        for sec, (key, uids) in zip(secs, exp):
            if sec["label"] != gname[key]:
                raise Violation("section_order", f"{sec['label']!r} vs {gname[key]!r} after {label}")
            if not sec["headInput"] and sec["head"] != gname[key]:
                raise Violation("section_head_name", f"{sec['head']!r} vs {gname[key]!r} after {label}")
            if sec["rows"] != uids:
                raise Violation("rows_mismatch", f"{gname[key]!r}: {len(sec['rows'])} rows vs {len(uids)} after {label}")
            if sec["collapsed"] != (key in s["collapsed"]):
                raise Violation("collapse_state", f"{gname[key]!r}: hidden={sec['collapsed']} after {label}")
        owner = {u: g["key"] for g in groups for u in g["uids"]}
        for sec in secs:
            for u in sec["rows"]:
                it = s["items"][u]
                if f["folder"] is not None and owner[u] != f["folder"]:
                    raise Violation("row_in_filtered_out_folder", f"{u} after {label}")
                if f["kind"] and it["kind"] != f["kind"]:
                    raise Violation("row_wrong_kind", f"{u} after {label}")
                q = f["q"].lower()
                if q and q not in it["name"].lower() and q not in it["desc"].lower():
                    raise Violation("row_fails_search", f"{u} after {label}")
        if f["folder"] is not None and f["folder"] not in owner.values() and f["folder"] not in gname:
            raise Violation("stale_folder_filter", f"{f['folder']} after {label}")
        if any(k not in gname for k in s["collapsed"]):
            raise Violation("stale_collapsed", f"{s['collapsed']} after {label}")
        if any(u not in s["items"] for u in s["sel"]):
            raise Violation("stale_selection", f"after {label}")
        # 7. no stuck drag / overlays out of step with state
        if not s["drag"]:
            if s["ghost"] or s["bodyDragging"] or s["dropOver"] or s["trDragging"] or s["hereNow"]:
                raise Violation("stuck_drag_ui", f"ghost={s['ghost']} body={s['bodyDragging']} over={s['dropOver']} "
                                f"tr={s['trDragging']} here={s['hereNow']} after {label}")
        else:
            raise Violation("drag_left_live", f"{s['drag']} after {label} (mouse is up)")
        for k in ("confirm", "move", "pop", "bulk"):
            if s["vis"][k] != s[k]:
                raise Violation("overlay_out_of_step", f"{k}: visible={s['vis'][k]} state={s[k]} after {label}")
        # 8. status line
        if re.search(r"Couldn't|failed|Lost track|no longer add up", s["status"]["text"]):
            raise Violation("error_status", f"{s['status']['text']!r} after {label}")
        # 9. focus after keyboard actions
        if keyboard and s["focus"] == "BODY":
            raise Violation("focus_lost_to_body", f"after {label}")
        sc = f"{len(s['sel'])} selected"
        if s["selcount"] != sc:
            raise Violation("selcount_stale", f"{s['selcount']} vs {sc} after {label}")
        return s

    # ---- helpers
    def rows(self):
        return self.page.locator("#folders tbody tr[data-uid]")

    def visible_uids(self):
        # Rows a person can see: not inside a collapsed folder.
        return self.page.evaluate("() => [...document.querySelectorAll('#folders tbody tr[data-uid]')]"
                                  ".filter(r => r.getClientRects().length).map(r => r.dataset.uid)")

    def name_pool(self, rng, s):
        names = [g["name"] for g in s["groups"]] or ["X"]
        pick = rng.choice(names)
        choices = [
            lambda: pick, lambda: pick.upper(), lambda: pick.lower(), lambda: "  " + pick + "  ",
            lambda: "", lambda: "   ", lambda: "x" * 150, lambda: "🏔️ Peak 🔥",
            lambda: "🏔️", lambda: "New folder", lambda: "new FOLDER", lambda: "New folder 2",
            lambda: "Zürich Café", lambda: "a/b", lambda: "..", lambda: "Unorganized",
            lambda: "Trip " + str(rng.randint(1, 5)), lambda: "עברית",
            lambda: 'q"uo<te>&', lambda: "Camp", lambda: "camp",
        ]
        return rng.choice(choices)()

    def type_into_focused(self, rng, name):
        p = self.page
        p.keyboard.press("ControlOrMeta+a")
        if name == "":
            p.keyboard.press("Backspace")
        else:
            p.keyboard.insert_text(name) if rng.random() < 0.5 else p.keyboard.type(name, delay=0)

    def finish_field(self, rng):
        """Leave a focused folder-name field: Enter, Esc, Tab or a click away."""
        p = self.page
        r = rng.random()
        if r < 0.5:
            p.keyboard.press("Enter"); how = "Enter"
        elif r < 0.65:
            p.keyboard.press("Escape"); how = "Escape"
        elif r < 0.8:
            p.keyboard.press("Tab"); how = "Tab"
        else:
            p.mouse.click(700, 60); how = "click-away"
        self.settle()
        return how

    def answer_confirm(self, rng):
        p = self.page
        btns = p.locator("#confirm-actions button")
        labels = btns.all_inner_texts()
        r = rng.random()
        if r < 0.15:
            p.keyboard.press("Escape"); how = "Escape"
        elif r < 0.3:
            p.keyboard.press("Enter"); how = "Enter(default)"
        else:
            i = rng.randrange(len(labels)); btns.nth(i).click(); how = labels[i]
        self.settle()
        return how

    def mouse_to(self, loc):
        loc.evaluate("e => e.scrollIntoView({block: 'center'})")
        b = loc.bounding_box()
        if not b:
            return False
        self.page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=5)
        return True

    # ---- actions
    def act(self, a):
        rng = random.Random(a["s"])
        p = self.page
        s = self.snap()
        if s["stage"] == "done":
            return self.a_back(rng)
        if s["confirm"]:
            return ("answer_confirm", self.answer_confirm(rng)), False
        fn = getattr(self, "a_" + a["t"])
        return fn(rng, s)

    def a_back(self, rng, s=None):
        self.page.click("#back"); self.settle()
        return ("back",), False

    def a_tick(self, rng, s):
        uids = self.visible_uids()
        if not uids:
            return ("tick", "none"), False
        u = rng.choice(uids)
        box = self.page.locator(f'tr[data-uid="{u}"] .sel-box')
        box.scroll_into_view_if_needed()
        mods = ["Shift"] if rng.random() < 0.2 else []
        box.click(modifiers=mods)
        self.settle()
        return ("tick", u, mods), False

    def a_tick_folder(self, rng, s):
        boxes = self.page.locator("#folders .folder-all")
        n = boxes.count()
        if not n:
            return ("tick_folder", "none"), False
        i = rng.randrange(n)
        if not boxes.nth(i).is_visible():
            return ("tick_folder", "hidden"), False
        boxes.nth(i).click(); self.settle()
        return ("tick_folder", i), False

    def a_select_all(self, rng, s):
        self.page.mouse.click(700, 60)
        self.page.keyboard.press("ControlOrMeta+a"); self.settle()
        return ("select_all",), False

    def a_escape(self, rng, s):
        self.page.keyboard.press("Escape"); self.settle()
        return ("escape",), False

    def _drag_source(self, rng, s):
        uids = self.visible_uids()
        if not uids:
            return None, None
        sel_vis = [u for u in uids if u in set(s["sel"])]
        u = rng.choice(sel_vis) if sel_vis and rng.random() < 0.6 else rng.choice(uids)
        ctl = rng.choice([".note-btn", ".icon-btn, .line-btn", ".name-in", "td.iconcol"])
        loc = self.page.locator(f'tr[data-uid="{u}"]').locator(ctl).first
        return u, loc

    def a_drag(self, rng, s):
        p = self.page
        u, src = self._drag_source(rng, s)
        if not u:
            return ("drag", "none"), False
        groups = s["groups"]
        own = next(g["key"] for g in groups if u in g["uids"])
        r = rng.random()
        if r < 0.45:
            tkind, tkey = "folder", rng.choice(groups)["key"]
        elif r < 0.65:
            tkind, tkey = "new", None
        elif r < 0.75:
            tkind, tkey = "own", own
        elif r < 0.85:
            tkind, tkey = "all", None
        else:
            tkind, tkey = "nowhere", rng.choice(["#filter", "#map-title", "#folders .folder-head", "#chips", "#export"])
        esc = rng.random() < 0.12
        src.scroll_into_view_if_needed()
        b = src.bounding_box()
        if not b:
            return ("drag", "nobox"), False
        x, y = b["x"] + min(20, b["width"] / 2), b["y"] + b["height"] / 2
        desc = ["drag", u, tkind, tkey, "esc" if esc else ""]
        p.mouse.move(x, y)
        p.mouse.down()
        try:
            p.mouse.move(x + 10, y + 10, steps=3)
            if tkind in ("folder", "own"):
                # Rail children: All, one per folder (in order), + New folder.
                tgt = p.locator("#folder-facets > *").nth([g["key"] for g in groups].index(tkey) + 1)
            elif tkind == "new":
                tgt = p.locator("#folder-facets .new-folder")
            elif tkind == "all":
                tgt = p.locator("#folder-facets .facet-btn").first
            else:
                tgt = p.locator(tkey).first
            if tgt.count() and tgt.is_visible():
                self.mouse_to(tgt)
            else:
                p.mouse.move(900, 500, steps=4)
            if esc:
                p.keyboard.press("Escape")
                if rng.random() < 0.5:
                    p.keyboard.press("Escape")
                    desc.append("esc2")
                p.mouse.move(x + 30, y + 40, steps=2)
                if tgt.count() and tgt.is_visible():
                    self.mouse_to(tgt)
        finally:
            p.mouse.up()
        self.settle()
        # A drop on + New folder opens its name in the rail.
        named = None
        if tkind == "new" and not esc:
            st = self.snap()
            if st.get("rename") and st["rename"]["where"] == "rail":
                name = self.name_pool(rng, st)
                if rng.random() < 0.85:
                    self.type_into_focused(rng, name)
                how = self.finish_field(rng)
                named = (name, how)
                st = self.snap()
                if st["confirm"]:
                    named += ("confirm:" + self.answer_confirm(rng),)
        desc.append(named)
        return tuple(desc), False

    def a_rename(self, rng, s):
        p = self.page
        heads = p.locator("#folders .folder-name")
        n = heads.count()
        if not n:
            return ("rename", "none"), False
        i = rng.randrange(n)
        h = heads.nth(i)
        old = h.inner_text()
        h.scroll_into_view_if_needed(); h.click(); self.settle()
        st = self.snap()
        name = self.name_pool(rng, st)
        if rng.random() < 0.9:
            self.type_into_focused(rng, name)
        how = self.finish_field(rng)
        st = self.snap()
        ans = None
        if st["confirm"]:
            ans = self.answer_confirm(rng)
        return ("rename", old, name, how, ans), how in ("Enter", "Escape", "Tab")

    def a_move_to(self, rng, s):
        p = self.page
        if not s["sel"]:
            uids = self.visible_uids()
            if not uids:
                return ("move_to", "none"), False
            for u in rng.sample(uids, min(len(uids), rng.randint(1, 3))):
                box = p.locator(f'tr[data-uid="{u}"] .sel-box')
                box.scroll_into_view_if_needed(); box.click()
            self.settle()
        more = p.locator("#more-btn")
        if more.is_disabled():
            return ("move_to", "more disabled"), False
        more.focus(); p.keyboard.press("Enter"); self.settle()
        p.keyboard.press("Enter")   # "Move to…" is first in More
        self.settle()
        if not self.snap()["move"]:
            return ("move_to", "pop did not open"), True
        keys = []
        if rng.random() < 0.15:
            # Ctrl+A while the list is open: the list must not keep a stale count.
            p.keyboard.press("ControlOrMeta+a"); self.settle(); keys.append("Ctrl+A")
            st = p.evaluate("() => ({open: !!MOVE, n: MOVE ? MOVE.uids.length : 0, sel: SEL.size,"
                            " head: (document.querySelector('#move-h') || {}).textContent})")
            if st["open"] and st["n"] != st["sel"]:
                raise Violation("move_list_stale", f"list says {st['head']!r} but {st['sel']} rows are ticked")
        for _ in range(rng.randint(0, 6)):
            k = rng.choice(["ArrowDown", "ArrowDown", "ArrowUp", "Home", "End"])
            p.keyboard.press(k); keys.append(k)
        fin = "Escape" if rng.random() < 0.15 else "Enter"
        target = p.evaluate("() => document.activeElement && document.activeElement.textContent")
        p.keyboard.press(fin); self.settle()
        named = None
        st = self.snap()
        if st.get("rename") and st["rename"]["where"] == "rail":
            name = self.name_pool(rng, st)
            if rng.random() < 0.85:
                self.type_into_focused(rng, name)
            how = self.finish_field(rng)
            named = (name, how)
            st = self.snap()
            if st["confirm"]:
                named += ("confirm:" + self.answer_confirm(rng),)
        return ("move_to", keys, fin, target, named), named is None or named[1] != "click-away"

    def a_filter_type(self, rng, s):
        btns = self.page.locator("#type-filter [data-kind]:visible")
        n = btns.count()
        if not n:
            return ("filter_type", "none"), False
        i = rng.randrange(n); btns.nth(i).click(); self.settle()
        return ("filter_type", i), False

    def a_filter_folder(self, rng, s):
        btns = self.page.locator("#folder-facets .facet-btn[data-fk]")
        n = btns.count()
        if not n:
            return ("filter_folder", "none"), False
        i = rng.randrange(n)
        b = btns.nth(i)
        if b.evaluate("e => e.tagName") != "BUTTON":
            return ("filter_folder", "naming"), False
        b.scroll_into_view_if_needed(); b.click(); self.settle()
        return ("filter_folder", i), False

    def a_search(self, rng, s):
        names = [it["name"] for it in s["items"].values()]
        r = rng.random()
        if r < 0.5 and names:
            n = rng.choice(names); a = rng.randrange(max(1, len(n))); q = n[a:a + rng.randint(1, 5)]
        elif r < 0.75:
            q = ""
        else:
            q = rng.choice(["zzz", "WP 1", "line", "Area", "🔥", "  ", "camp"])
        self.page.fill("#filter", q); self.settle()
        return ("search", q), False

    def a_clear_filters(self, rng, s):
        c = self.page.locator("#chips .linkbtn")
        if c.count() and c.is_visible():
            c.click(); self.settle()
            return ("clear_filters",), False
        x = self.page.locator("#chips .chip button")
        if x.count():
            x.nth(rng.randrange(x.count())).click(); self.settle()
            return ("remove_chip",), False
        return ("clear_filters", "none"), False

    def a_collapse(self, rng, s):
        c = self.page.locator("#folders .collapse")
        n = c.count()
        if not n:
            return ("collapse", "none"), False
        i = rng.randrange(n); c.nth(i).scroll_into_view_if_needed(); c.nth(i).click(); self.settle()
        return ("collapse", i), False

    def _row_ctl(self, rng, sel):
        uids = self.visible_uids()
        if not uids:
            return None, None
        u = rng.choice(uids)
        loc = self.page.locator(f'tr[data-uid="{u}"]').locator(sel)
        return (u, loc.first) if loc.count() else (u, None)

    def a_edit_name(self, rng, s):
        u, inp = self._row_ctl(rng, ".name-in")
        if not inp:
            return ("edit_name", "none"), False
        inp.scroll_into_view_if_needed(); inp.click()
        self.page.keyboard.press("ControlOrMeta+a")
        name = rng.choice(["Renamed " + str(rng.randint(1, 99)), "", "🔥 hot", 'a<b>&"c', "  pad  ", "Zürich"])
        if name:
            self.page.keyboard.insert_text(name)
        else:
            self.page.keyboard.press("Backspace")
        k = rng.choice(["Enter", "Tab", "Escape"])
        self.page.keyboard.press(k); self.settle()
        # Round 2 (F7): Enter / Esc keep focus in the field, so focus is
        # checked after all three keys.
        still = u in self.visible_uids()   # a rename can take the row out of a search
        return ("edit_name", u, name, k), still

    def a_edit_note(self, rng, s):
        u, btn = self._row_ctl(rng, ".note-btn")
        if not btn:
            return ("edit_note", "none"), False
        btn.scroll_into_view_if_needed(); btn.click(); self.settle()
        ta = self.page.locator(f'tr[data-uid="{u}"] .desc-in')
        if not ta.count():
            return ("edit_note", u, "no editor"), False
        self.page.keyboard.insert_text(rng.choice(["note ", "多言語 ", "line\nbreak ", "🔥"]))
        r = rng.random()
        if r < 0.4:
            self.page.locator(f'tr[data-uid="{u}"] .note-apply').click(); how = "Save"
        elif r < 0.6:
            self.page.keyboard.press("ControlOrMeta+Enter"); how = "Ctrl+Enter"
        elif r < 0.75:
            self.page.locator(f'tr[data-uid="{u}"] .note-cancel').click(); how = "Cancel"
        elif r < 0.85:
            self.page.keyboard.press("Escape"); how = "Escape"
        else:
            how = "left-open"     # leave it open: later moves / export must cope
        self.settle()
        return ("edit_note", u, how), how in ("Ctrl+Enter", "Escape")

    def a_edit_mark(self, rng, s):
        u, btn = self._row_ctl(rng, ".icon-btn, .line-btn")
        if not btn:
            return ("edit_mark", "none"), False
        btn.scroll_into_view_if_needed(); btn.click(); self.settle()
        pop = self.page.locator("#mark-pop")
        sw = pop.locator(".swatch-btn")
        if sw.count():
            sw.nth(rng.randrange(sw.count())).click()
        ic = pop.locator(".icon-pick")
        if ic.count() and rng.random() < 0.6:
            b = ic.nth(rng.randrange(ic.count())); b.scroll_into_view_if_needed(); b.click()
        tg = pop.locator(".tog")
        if tg.count() and rng.random() < 0.7:
            tg.nth(rng.randrange(tg.count())).click()
        if rng.random() < 0.8:
            pop.locator(".pop-apply").click(); how = "Save"
        else:
            self.page.keyboard.press("Escape"); how = "Escape"
        self.settle()
        return ("edit_mark", u, how), True

    def a_edit_line_bulk(self, rng, s):
        b = self.page.locator("#bulk-line")
        if not b.is_visible():
            return ("line_bulk", "hidden"), False
        b.click(); self.settle()
        tg = self.page.locator("#mark-dialog .tog")
        for _ in range(rng.randint(1, 2)):
            tg.nth(rng.randrange(tg.count())).click()
        self.page.locator("#line-apply").click(); self.settle()
        return ("line_bulk",), True

    def a_bulk_icon(self, rng, s):
        b = self.page.locator("#bulk-icon")
        if b.is_disabled():
            return ("bulk_icon", "disabled"), False
        b.click(); self.settle()
        sw = self.page.locator("#mark-dialog .swatch-btn")
        if sw.count():
            sw.nth(rng.randrange(sw.count())).click()
        if rng.random() < 0.8:
            self.page.locator("#bulk-apply").click(); how = "Save"
        else:
            self.page.keyboard.press("Escape"); how = "Escape"
        self.settle()
        return ("bulk_icon", how), True

    def a_exclude(self, rng, s):
        p = self.page
        if not s["sel"]:
            uids = self.visible_uids()
            if not uids:
                return ("exclude", "none"), False
            for u in rng.sample(uids, min(len(uids), rng.randint(1, 4))):
                box = p.locator(f'tr[data-uid="{u}"] .sel-box'); box.scroll_into_view_if_needed(); box.click()
        if p.locator("#more-btn").is_disabled():
            return ("exclude", "no sel"), False
        p.click("#more-btn")
        which = "#bulk-exclude" if rng.random() < 0.65 else "#bulk-include"
        p.click(which); self.settle()
        return ("exclude", which), False

    # ---- human-timing actions (a real click holds the button ~50-150 ms)
    def human_press(self, loc, hold):
        # Centred, as a person would look at it: scroll_into_view_if_needed can
        # leave a low rail entry under the rail's sticky footer (Export), and
        # the press then lands there (round 2: a harness false positive).
        loc.evaluate("e => e.scrollIntoView({block: 'center'})")
        b = loc.bounding_box()
        if not b:
            return False
        p = self.page
        x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        if not loc.evaluate(f"e => e.contains(document.elementFromPoint({x}, {y}))"):
            return False   # covered: not a press on this control at all
        p.mouse.move(x, y)
        p.mouse.down(); p.wait_for_timeout(hold); p.mouse.up()
        self.settle(30)
        return True

    def _open_some_field(self, rng):
        """Open a folder name in its header (or a row name) and maybe type."""
        p = self.page
        if rng.random() < 0.7:
            heads = p.locator("#folders .folder-name:visible")
            if not heads.count():
                return None
            h = heads.nth(rng.randrange(heads.count())); h.scroll_into_view_if_needed(); h.click()
            self.settle()
            if rng.random() < 0.7:
                self.type_into_focused(rng, self.name_pool(rng, self.snap()))
            return "folder-name"
        u, inp = self._row_ctl(rng, ".name-in")
        if not inp:
            return None
        inp.scroll_into_view_if_needed(); inp.click()
        p.keyboard.insert_text(" e" if rng.random() < 0.8 else "")
        return "row-name"

    def a_leave_field_by_click(self, rng, s):
        """Leave an open name by pressing another control like a person does,
        then check that press did what it should."""
        p = self.page
        field = self._open_some_field(rng)
        if not field:
            return ("leave_field", "none"), False
        hold = rng.choice([0, 40, 80, 150])
        what = rng.choice(["tick", "tick", "rail", "collapse"])
        before = self.page.evaluate("() => ({sel: [...SEL], folder: FILTERS.folder, col: [...COLLAPSED]})")
        if what == "tick":
            uids = self.visible_uids()
            if not uids:
                return ("leave_field", field, "no rows"), False
            u = rng.choice(uids)
            ok = self.human_press(p.locator(f'tr[data-uid="{u}"] .sel-box'), hold)
            after = self.snap()
            if after["confirm"]:   # a taken name: the merge offer came up first
                return ("leave_field", field, what, hold, "confirm:" + self.answer_confirm(rng)), False
            if ok and (u in before["sel"]) == (u in after["sel"]) and u in self.visible_uids():
                raise Violation("click_lost_after_field",
                                f"{field} open, {hold} ms press on a row checkbox did not toggle it")
        elif what == "rail":
            btns = p.locator("#folder-facets .facet-btn[data-fk]:visible")
            i = rng.randrange(btns.count())
            b = btns.nth(i)
            if b.evaluate("e => e.tagName") != "BUTTON":
                return ("leave_field", field, "naming"), False
            key = b.get_attribute("data-drop")
            ok = self.human_press(b, hold)
            after = self.snap()
            if after["confirm"]:
                return ("leave_field", field, what, hold, "confirm:" + self.answer_confirm(rng)), False
            want = None if before["folder"] == key else key
            if ok and after["filters"]["folder"] != want and (want is None or want in {g["key"] for g in after["groups"]}):
                raise Violation("click_lost_after_field",
                                f"{field} open, {hold} ms press on a rail folder: filter {after['filters']['folder']!r}, want {want!r}")
        else:
            c = p.locator("#folders .collapse:visible")
            if not c.count():
                return ("leave_field", field, "no collapse"), False
            i = rng.randrange(c.count())
            key = c.nth(i).get_attribute("data-fk").split("|", 1)[1]
            ok = self.human_press(c.nth(i), hold)
            after = self.snap()
            if after["confirm"]:
                return ("leave_field", field, what, hold, "confirm:" + self.answer_confirm(rng)), False
            if ok and (key in before["col"]) == (key in after["collapsed"]) and key in {g["key"] for g in after["groups"]}:
                raise Violation("click_lost_after_field",
                                f"{field} open, {hold} ms press on a folder's collapse button did nothing")
        return ("leave_field", field, what, hold), False

    def a_rename_then_drag(self, rng, s):
        """Rename a folder (often to a taken name), then press straight on a row and drag."""
        p = self.page
        heads = p.locator("#folders .folder-name:visible")
        if heads.count() < 2:
            return ("rename_then_drag", "none"), False
        names = [g["name"] for g in s["groups"]]
        h = heads.nth(rng.randrange(heads.count())); h.scroll_into_view_if_needed(); h.click(); self.settle()
        self.type_into_focused(rng, rng.choice(names) if rng.random() < 0.7 else self.name_pool(rng, s))
        uids = self.visible_uids()
        if not uids:
            p.keyboard.press("Escape"); self.settle()
            return ("rename_then_drag", "no rows"), False
        src = p.locator(f'tr[data-uid="{rng.choice(uids)}"] .note-btn')
        src.scroll_into_view_if_needed(); b = src.bounding_box()
        x, y = b["x"] + 20, b["y"] + b["height"] / 2
        p.mouse.move(x, y); p.mouse.down()
        try:
            p.wait_for_timeout(rng.choice([0, 60]))
            p.mouse.move(x + 10, y + 10, steps=3)
            st = p.evaluate("() => ({confirm: !!CONFIRM, drag: !!(DRAG && DRAG.active)})")
            if st["confirm"] and st["drag"]:
                raise Violation("drag_under_modal", "a row drag started while the merge offer dialog was open")
            tgt = p.locator("#folder-facets > *").nth(rng.randrange(1, len(s["groups"]) + 2))
            self.mouse_to(tgt)
        finally:
            p.mouse.up()
        self.settle()
        ans = self.answer_confirm(rng) if self.snap()["confirm"] else None
        return ("rename_then_drag", ans), False

    def a_rename_then_export(self, rng, s):
        """Rename a folder (often to a taken name) and click Export straight away."""
        p = self.page
        heads = p.locator("#folders .folder-name:visible")
        if heads.count() < 2:
            return ("rename_then_export", "none"), False
        names = [g["name"] for g in s["groups"]]
        h = heads.nth(rng.randrange(heads.count())); h.scroll_into_view_if_needed(); h.click(); self.settle()
        self.type_into_focused(rng, rng.choice(names) if rng.random() < 0.7 else self.name_pool(rng, s))
        p.click("#export"); self.settle(80)
        st = self.snap()
        if st["stage"] == "done" and st["confirm"]:
            title = p.locator("#confirm-title").inner_text()
            raise Violation("dialog_over_export", f"export screen shown with {title!r} on top")
        if st["confirm"]:
            self.answer_confirm(rng)
        if self.snap()["stage"] == "done":
            p.click("#back"); self.settle()
        return ("rename_then_export",), False

    def a_include_chip(self, rng, s):
        c = self.page.locator("#folders .exc-chip:visible")
        if not c.count():
            return ("include_chip", "none"), False
        b = c.nth(rng.randrange(c.count())); b.scroll_into_view_if_needed(); b.click(); self.settle()
        return ("include_chip",), False

    # ---- round 4 actions
    def a_click_new_folder(self, rng, s):
        """Click (or Enter / Space on) + New folder: the ticked rows go into a
        new folder, or with none ticked an empty one is made. Then name it."""
        p = self.page
        if rng.random() < 0.4:
            uids = self.visible_uids()
            for u in rng.sample(uids, min(len(uids), rng.randint(1, 3))):
                box = p.locator(f'tr[data-uid="{u}"] .sel-box'); box.scroll_into_view_if_needed(); box.click()
            self.settle()
        before = self.snap()
        nf = p.locator("#folder-facets .new-folder")
        how = rng.choice(["click", "click", "Enter", "Space"])
        if how == "click":
            if not self.human_press(nf, rng.choice([0, 60])):
                return ("click_new_folder", "covered"), False
        else:
            nf.evaluate("e => e.scrollIntoView({block: 'center'})")
            nf.focus(); p.keyboard.press("Enter" if how == "Enter" else " ")
        self.settle()
        st = self.snap()
        sel = len(before["sel"])
        if st["confirm"]:   # a name left by this click was taken: its offer came first
            return ("click_new_folder", how, sel, "confirm:" + self.answer_confirm(rng)), False
        if len(st["groups"]) <= len(before["groups"]) - 0 and not sel:
            raise Violation("new_folder_click_lost", f"{how}: {len(before['groups'])} -> {len(st['groups'])} folders")
        named = None
        if st.get("rename") and st["rename"]["where"] == "rail":
            if not sel and st["groups"][-1]["uids"]:
                raise Violation("new_folder_not_empty", f"{st['groups'][-1]}")
            name = self.name_pool(rng, st)
            if rng.random() < 0.85:
                self.type_into_focused(rng, name)
            fin = self.finish_field(rng)
            named = (name, fin)
            if self.snap()["confirm"]:
                named += ("confirm:" + self.answer_confirm(rng),)
        elif not st["rename"]:
            raise Violation("new_folder_not_named", f"{how} with {sel} ticked: no name box opened")
        return ("click_new_folder", how, sel, named), named is not None and named[1] != "click-away"

    def a_remove_empty_folder(self, rng, s):
        """The x beside an empty folder in the rail, by mouse or keyboard."""
        p = self.page
        xs = p.locator("#folder-facets .facet-x")
        if not xs.count():
            return ("remove_empty", "none"), False
        i = rng.randrange(xs.count())
        key = xs.nth(i).get_attribute("data-fk")[7:]
        kb = rng.random() < 0.4
        if kb:
            xs.nth(i).evaluate("e => e.scrollIntoView({block: 'center'})")
            xs.nth(i).focus(); p.keyboard.press("Enter")
        else:
            row = xs.nth(i).locator("xpath=..")
            if not self.mouse_to(row):
                return ("remove_empty", "nobox"), False
            if not self.human_press(xs.nth(i), rng.choice([0, 60])):
                return ("remove_empty", "covered"), False
        self.settle()
        if key in {g["key"] for g in self.snap()["groups"]}:
            raise Violation("empty_folder_not_removed", f"{key} still there after its x ({'key' if kb else 'mouse'})")
        return ("remove_empty", key, "kb" if kb else "mouse"), kb

    def a_sort_toggle(self, rng, s):
        """Click (or Enter on) a folder's Name header: map order -> A to Z ->
        Z to A -> map order, the same in every header. The row invariant
        (rows == visibleItems) checks the order itself."""
        p = self.page
        # Visible ones only: a collapsed folder's header row is hidden.
        btns = p.locator("#folders .sort-btn:visible")
        if not btns.count():
            return ("sort", "none"), False
        before = p.evaluate("SORT")
        b = btns.nth(rng.randrange(btns.count()))
        kb = rng.random() < 0.4
        if kb:
            b.evaluate("e => e.scrollIntoView({block: 'center'})"); b.focus(); p.keyboard.press("Enter")
        else:
            if not self.human_press(b, rng.choice([0, 60])):
                return ("sort", "covered"), False
        self.settle()
        want = {None: "asc", "asc": "desc", "desc": None}[before]
        st = p.evaluate("() => ({sort: SORT, aria: [...document.querySelectorAll('th.name-th')].map(t => t.getAttribute('aria-sort'))})")
        if st["sort"] != want:
            raise Violation("sort_state", f"{before} -> {st['sort']}, want {want}")
        aria = {None: "none", "asc": "ascending", "desc": "descending"}[want]
        if any(a != aria for a in st["aria"]):
            raise Violation("sort_aria", f"{st['aria']} vs {aria}")
        # Map order underneath is untouched (the bridge's layout check also holds).
        return ("sort", before, want, "kb" if kb else "mouse"), kb

    def a_hover(self, rng, s):
        """Hover a row's name or note (round 4): the tip shows exactly when the
        preview hides text, with the whole value; Esc or leaving hides it, and
        nothing else changes."""
        p = self.page
        u, ctl = self._row_ctl(rng, rng.choice([".note-btn", ".name-in", ".caution"]))
        if not ctl:
            return ("hover", "none"), False
        ctl.evaluate("e => e.scrollIntoView({block: 'center'})")
        if not self.mouse_to(ctl):
            return ("hover", "nobox"), False
        p.wait_for_timeout(650)
        st = p.evaluate("""([u, cls]) => {
          const tr = document.querySelector(`tr[data-uid="${u}"]`);
          const el = tr && tr.querySelector(cls);
          const it = allItems().find(i => i.uid === u);
          const tip = document.querySelector('#tip');
          const cutw = e => !!e && e.scrollWidth > e.clientWidth + 1;
          const desc = String(it.desc || '').trim();
          let want = null;
          if (!el) return {gone: true};
          if (el.classList.contains('name-in')) want = el !== document.activeElement && cutw(el) ? el.value : null;
          else if (el.classList.contains('caution')) want = cautionText(it);
          else want = desc && (desc !== firstLine(desc) || cutw(el.querySelector('.note-text'))) ? desc : null;
          const r = tip.getBoundingClientRect();
          return {want, shown: !tip.classList.contains('hidden'), text: tip.textContent,
                  inside: r.top >= 0 && r.left >= 0 && r.bottom <= innerHeight + 1 && r.right <= innerWidth + 1,
                  hovered: el.matches(':hover')};
        }""", [u, ctl.evaluate("e => '.' + e.classList[0]")])
        if st.get("gone") or not st["hovered"]:
            return ("hover", u, "moved"), False
        if bool(st["want"]) != st["shown"] or (st["shown"] and st["text"] != st["want"]):
            raise Violation("hover_tip", f"{u}: want {st['want']!r:.80} shown={st['shown']} text={st['text']!r:.80}")
        if st["shown"] and not st["inside"]:
            raise Violation("hover_tip_outside", f"{u}: the tip is outside the window")
        how = "away"
        if st["shown"] and rng.random() < 0.5:
            sel = s["sel"]
            p.keyboard.press("Escape"); how = "Escape"
            if p.evaluate("() => !document.querySelector('#tip').classList.contains('hidden')"):
                raise Violation("hover_tip_escape", f"{u}: Esc left the tip up")
            if sorted(p.evaluate("[...SEL]")) != sorted(sel):
                raise Violation("hover_tip_escape", "Esc on the tip changed the selection")
        p.mouse.move(120, 60, steps=2); p.wait_for_timeout(260)
        if p.evaluate("() => !document.querySelector('#tip').classList.contains('hidden')"):
            raise Violation("hover_tip_stuck", f"{u}: still up after the pointer left")
        return ("hover", u, bool(st["want"]), how), False

    def a_export(self, rng, s):
        return self.export_and_verify(rng, s), False

    # ---- export verification
    def export_and_verify(self, rng, s):
        p = self.page
        included = [u for u, it in s["items"].items() if it["included"]]
        p.click("#export"); self.settle(50)
        st = self.snap()
        if st["confirm"]:   # unsaved note prompt
            self.answer_confirm(rng)
            st = self.snap()
        if st["stage"] != "done":
            if not included and "excluded" in st["status"]["text"]:
                return ("export", "all excluded")
            if st.get("note") or st["confirm"]:
                return ("export", "stayed (note cancel)")
            raise Violation("export_did_not_finish", f"{st['status']} included={len(included)}")
        self.exports += 1
        # Round 3: an export writes every change so far, so Start over has none to count.
        left = p.evaluate("unexportedChanges()")
        if left:
            raise Violation("changes_after_export", f"Start over counts {left} right after an export")
        res = self.verify_export(rng)
        p.wait_for_timeout(300)
        p.click("#back"); self.settle()
        return ("export", res)

    def verify_export(self, rng):
        p = self.page
        info = p.evaluate("""() => ({manifest: MANIFEST,
          groups: DATA.groups.map(g => ({key: g.key, name: g.name, safe: g.safe,
             items: g.items.map(i => ({uid: i.uid, name: i.name, kind: i.kind, included: i.included !== false}))})),
          boxes: [...document.querySelectorAll('#runbook .rb-step')].map(b => ({
             title: b.querySelector('.rb-name').textContent.trim(),
             num: b.querySelector('.rb-num') && b.querySelector('.rb-num').textContent,
             label: b.querySelector('.rb-dl').getAttribute('aria-label'),
             chips: [...b.querySelectorAll('.rb-file')].map(c => c.textContent)}))})""")
        man, groups, boxes = info["manifest"], info["groups"], info["boxes"]
        # expected boxes: folders with any included item, at their position
        exp = []
        # Round 4: a folder with no items takes no number.
        numbered = [g for g in groups if g["items"]]
        for n, g in enumerate(numbered, 1):
            inc = [i for i in g["items"] if i["included"]]
            if inc:
                exp.append((n, g, inc))
        if [e["n"] for e in man] != [n for n, _, _ in exp]:
            raise Violation("export_folder_set", f"manifest n={[e['n'] for e in man]} expected {[n for n, _, _ in exp]}")
        if len(boxes) != len(man):
            raise Violation("export_box_count", f"{len(boxes)} boxes vs {len(man)}")
        for e, (n, g, inc), b in zip(man, exp, boxes):
            if e["folder"] != g["name"] or b["title"] != g["name"]:
                raise Violation("export_box_name", f"{n}: manifest {e['folder']!r} box {b['title']!r} vs {g['name']!r}")
            if e["count"] != len(inc):
                raise Violation("export_box_count_items", f"{g['name']!r}: {e['count']} vs {len(inc)} included")
            if e["safe"] != g["safe"]:
                raise Violation("export_safe", f"{e['safe']} vs {g['safe']}")
            # Round 3: a box whose name another box shares (any case) shows its
            # number; a box whose file names collide shows its chips' NN_ folder.
            twin = sum(x["folder"].strip().lower() == e["folder"].strip().lower() for x in man) > 1
            file_twin = sum(x["safe"].lower() == e["safe"].lower() for x in man) > 1
            want_num = f"{e['dir'].split('_')[0]} ·" if twin else None
            if b["num"] != want_num:
                raise Violation("export_box_number", f"{g['name']!r}: {b['num']!r} vs {want_num!r}")
            want_label = f"Download {want_num + ' ' if want_num else ''}{g['name']}"
            if b["label"] != want_label:
                raise Violation("export_box_label", f"{b['label']!r} vs {want_label!r}")
            if b["chips"] != [f["path"] if file_twin else f["path"].split("/")[-1] for f in e["files"]]:
                raise Violation("export_chips", f"{b['chips']}")
        # Download all
        with p.expect_download(timeout=20000) as dl:
            p.click("#download")
        d = dl.value
        if d.suggested_filename != "onx_ready.zip":
            raise Violation("download_all_name", d.suggested_filename)
        allz = zipfile.ZipFile(io.BytesIO(Path(d.path()).read_bytes()))
        members = {n: allz.read(n) for n in allz.namelist()}
        if "instructions.txt" not in members:
            raise Violation("zip_no_instructions", str(list(members)[:5]))
        guide = members["instructions.txt"].decode("utf-8").split("\r\n")
        for e in man:
            if f"{e['dir']}/    rename to: {e['folder']}" not in guide:
                raise Violation("instructions_folder_line", f"{e['dir']!r} {e['folder']!r}")
        want_members = {f["path"] for e in man for f in e["files"]} | {"instructions.txt"}
        if set(members) != want_members:
            raise Violation("zip_members", f"extra {sorted(set(members) - want_members)[:3]} missing {sorted(want_members - set(members))[:3]}")
        # items exactly once across all files; excluded absent
        seen_total = 0
        for e, (n, g, inc) in zip(man, exp):
            # L1: NN_ is 2 digits, or 3+ once there are 100+ folders.
            width = max(2, len(str(len(numbered))))
            prefix = f"{n:0{width}d}_{g['safe']}/"
            if e.get("dir") != prefix[:-1]:
                raise Violation("zip_dir", f"{e.get('dir')} vs {prefix[:-1]}")
            names = []
            cnt = 0
            for f in e["files"]:
                if not f["path"].startswith(prefix):
                    raise Violation("zip_prefix", f"{f['path']} vs {prefix}")
                root = ET.fromstring(members[f["path"]])
                md = next((c for c in root if c.tag.split("}")[-1] == "metadata"), None)
                mdname = next((x.text or "" for x in (md if md is not None else []) if x.tag.split("}")[-1] == "name"), None)
                if mdname != g["name"]:
                    raise Violation("gpx_folder_name", f"{f['path']}: metadata name {mdname!r} vs folder {g['name']!r}")
                els =[c for c in root if c.tag.split("}")[-1] in ("wpt", "trk", "rte")]
                if len(els) != f["count"]:
                    raise Violation("zip_file_count", f"{f['path']}: {len(els)} elements vs manifest {f['count']}")
                cnt += len(els)
                for c in els:
                    nm = next((x.text or "" for x in c if x.tag.split("}")[-1] == "name"), "")
                    names.append(nm)
            if cnt != len(inc):
                raise Violation("zip_folder_items", f"{g['name']!r}: {cnt} in files vs {len(inc)} included")
            want = collections.Counter(i["name"] for i in inc)
            for orig, new in e.get("renamed") or []:
                if want[orig]:
                    want[orig] -= 1; want[new] += 1
            got = collections.Counter(names)
            if +want != +got:
                miss = list((want - got).elements())[:3]; extra = list((got - want).elements())[:3]
                raise Violation("zip_folder_names", f"{g['name']!r}: missing {miss} extra {extra}")
            seen_total += cnt
        n_inc = sum(len(inc) for _, _, inc in exp)
        if seen_total != n_inc:
            raise Violation("zip_total", f"{seen_total} vs {n_inc}")
        # every per-folder zip (paced: Chromium drops rapid downloads)
        btns = p.locator("#runbook .rb-dl")
        k = btns.count()
        order = list(range(k))
        if k > 12:   # 200-folder maps: a sample, first and last always
            order = sorted({0, k - 1, *rng.sample(range(k), 10)})
        for i in order:
            e = man[i]
            p.wait_for_timeout(300)
            btns.nth(i).scroll_into_view_if_needed()
            with p.expect_download(timeout=20000) as dl:
                btns.nth(i).click()
            d = dl.value
            want_name = f"{e['n']:0{max(2, len(str(len([g for g in groups if g['items']]))))}d}_{e['safe']}.zip"
            if d.suggested_filename != want_name:
                raise Violation("folder_zip_name", f"{d.suggested_filename!r} vs {want_name!r}")
            z = zipfile.ZipFile(io.BytesIO(Path(d.path()).read_bytes()))
            fm = {n: z.read(n) for n in z.namelist()}
            if set(fm) != {f["path"] for f in e["files"]}:
                raise Violation("folder_zip_members", f"{want_name}: {sorted(fm)[:3]}")
            for n_, b_ in fm.items():
                if members[n_] != b_:
                    raise Violation("folder_zip_bytes", f"{n_} differs from Download all")
        return f"{len(man)} folders, {n_inc} items, {len(order)} folder zips"


# --------------------------------------------------------------------------- driver
WEIGHTS = {
    "tick": 18, "tick_folder": 3, "select_all": 2, "escape": 2, "drag": 26, "rename": 9,
    "move_to": 9, "filter_type": 3, "filter_folder": 5, "search": 4, "clear_filters": 4,
    "collapse": 4, "edit_name": 3, "edit_note": 3, "edit_mark": 3, "edit_line_bulk": 1,
    "bulk_icon": 1, "exclude": 5, "include_chip": 2, "export": 2,
    # Round 4: + New folder clicked, the x on an empty folder.
    "click_new_folder": 5, "remove_empty_folder": 3, "hover": 4, "sort_toggle": 3,
}
# Second wave: the human-timing / interleaving actions (--wave 2).
WEIGHTS2 = dict(WEIGHTS, leave_field_by_click=6, rename_then_drag=3, rename_then_export=2)


def gen_actions(seed, n, wave=1):
    rng = random.Random(seed * 7919 + 13)
    kinds, w = zip(*(WEIGHTS2 if wave == 2 else WEIGHTS).items())
    acts = []
    for i in range(n):
        t = "export" if i and i % 60 == 59 else rng.choices(kinds, w)[0]
        acts.append({"t": t, "s": rng.randrange(1 << 30)})
    acts.append({"t": "export", "s": rng.randrange(1 << 30)})
    return acts


KNOWN = set()   # signatures counted and stepped over (--known), so a session can go deeper


def run(ctx, map_name, files, actions, *, verbose=False, stop_on_fail=True):
    """Run one session. Returns (failure | None, n_done, trace, stats)."""
    known = collections.Counter()
    sess = Session(ctx, map_name, files, None)
    trace = []
    try:
        sess.open()
    except Violation as v:
        sess.close()
        return {"sig": v.sig, "detail": v.detail, "at": -1}, 0, trace, {}
    harness = 0
    for i, a in enumerate(actions):
        desc, kb = None, False
        try:
            desc, kb = sess.act(a)
        except Violation as v:
            if v.sig in KNOWN:
                known[v.sig] += 1
                desc = ("known", v.sig)
                try:
                    sess.page.mouse.up(); sess.settle(30)
                    if sess.snap()["confirm"]:
                        sess.answer_confirm(random.Random(i))
                except PWError:
                    pass
            else:
                trace.append((i, a, "VIOLATION"))
                sess.close()
                return {"sig": v.sig, "detail": v.detail, "at": i}, i, trace, {"exports": sess.exports}
        except PWError as e:
            harness += 1
            desc = ("harness-error", a["t"], str(e).splitlines()[0][:120])
            try:
                sess.page.mouse.up()
                sess.page.keyboard.press("Escape")
                sess.settle(50)
            except PWError:
                pass
        trace.append((i, a, desc))
        if verbose:
            print(i, a["t"], desc, flush=True)
        try:
            sess.check(f"#{i} {a['t']}", keyboard=kb)
        except Violation as v:
            sess.close()
            return {"sig": v.sig, "detail": v.detail, "at": i, "desc": repr(desc)}, i + 1, trace, \
                {"exports": sess.exports, "harness": harness}
    stats = {"exports": sess.exports, "harness": harness, "checks": sess.checks, "known": dict(known)}
    sess.close()
    return None, len(actions), trace, stats


def shrink(ctx, map_name, files, actions, sig, budget=50):
    """ddmin-lite: drop chunks while the same failure signature reproduces."""
    cur = list(actions)
    tries = 0

    def fails(lst):
        nonlocal tries
        tries += 1
        f, *_ = run(ctx, map_name, files, lst)
        return f is not None and f["sig"] == sig, f

    ok, f = fails(cur)
    if not ok:
        return None, tries, f
    chunk = max(1, len(cur) // 2)
    while chunk >= 1 and tries < budget:
        i, changed = 0, False
        while i < len(cur) and tries < budget:
            cand = cur[:i] + cur[i + chunk:]
            if cand:
                ok, _ = fails(cand)
                if ok:
                    cur, changed = cand, True
                    continue
            i += chunk
        if not changed:
            chunk //= 2
    _, f = fails(cur)
    return cur, tries, f


def parse_seeds(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-"); out += range(int(a), int(b) + 1)
        else:
            out.append(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--actions", type=int, default=200)
    ap.add_argument("--maps", default=",".join(MAP_ORDER))
    ap.add_argument("--replay")
    ap.add_argument("--shrink", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--wave", type=int, default=1)
    ap.add_argument("--known", default="", help="comma-separated signatures to count and step over")
    ap.add_argument("--out", help="maps and run records (default archive/qa-fuzz, or CAIRN_QA_OUT)")
    args = ap.parse_args()
    if args.out:
        set_out(args.out)
    KNOWN.update(x for x in args.known.split(",") if x)
    maps = build_maps()
    RUNS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(bypass_csp=True, accept_downloads=True, viewport={"width": 1440, "height": 900})
        if args.replay:
            rec = json.loads(Path(args.replay).read_text())
            f, n, trace, st = run(ctx, rec["map"], maps[rec["map"]], rec["actions"], verbose=True)
            print("REPLAY:", f, n, st)
            return
        summary = []
        for seed in parse_seeds(args.seeds):
            mlist = args.maps.split(",")
            map_name = mlist[seed % len(mlist)]
            actions = gen_actions(seed, args.actions, args.wave)
            t0 = time.time()
            f, n, trace, st = run(ctx, map_name, maps[map_name], actions, verbose=args.verbose)
            dt = time.time() - t0
            rec = {"seed": seed, "wave": args.wave, "map": map_name, "n_actions": len(actions), "done": n,
                   "failure": f, "stats": st, "secs": round(dt, 1),
                   "trace": [(i, a["t"], repr(d)[:300]) for i, a, d in trace]}
            if f:
                rec["actions"] = actions[: (f["at"] + 1) if f["at"] >= 0 else 0]
                if args.shrink and f["at"] >= 0:
                    mini, tries, f2 = shrink(ctx, map_name, maps[map_name], rec["actions"], f["sig"])
                    rec["shrunk"] = {"actions": mini, "tries": tries, "failure": f2}
                    if mini:
                        _, _, tr2, _ = run(ctx, map_name, maps[map_name], mini)
                        rec["shrunk"]["trace"] = [(i, a["t"], repr(d)[:400]) for i, a, d in tr2]
            else:
                rec["actions"] = actions
            (RUNS / f"w{args.wave}_seed{seed:04d}_{map_name}{args.tag}.json").write_text(
                json.dumps(rec, indent=1, ensure_ascii=False))
            line = f"wave={args.wave} seed={seed} map={map_name} done={n}/{len(actions)} {dt:.0f}s " + \
                (f"FAIL {f['sig']}: {f['detail'][:200]}" if f else f"ok {st}")
            print(line, flush=True)
            summary.append(line)
        br.close()


if __name__ == "__main__":
    main()
