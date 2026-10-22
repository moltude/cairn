"""CalTopo -> Cairn -> onX -> (onX export) -> Cairn edits -> onX round-trip harness.

The browser steps (import into onX, rename the import folder, export it) are done by
hand or by a browser-driving session; this script does everything between them,
offline and deterministically. Everything is written under
tests/fixtures/roundtrip/<run>/ (or --root).

    # 1. CalTopo -> Cairn: tag every item "[<run>i1] ", write onX upload files.
    uv run python scripts/onx_roundtrip.py stage1 --run r1 [--set random-geojson ...]

    # (browser) import each i1/<set>/ folder's GPX files as ONE import, rename the
    # import folder to the name stage1 printed, then export that folder (GPX + KML).

    # 2. Compare onX's export with what Cairn sent.
    uv run python scripts/onx_roundtrip.py verify --run r1 --stage i1 --set random-geojson \
        --onx ~/Downloads/onx-markups-*.gpx ~/Downloads/onx-markups-*.kml

    # 3. onX export -> Cairn edits: the deterministic edit plan, new upload files.
    uv run python scripts/onx_roundtrip.py stage2 --run r1 --set random-geojson --onx <files>

    # (browser) import i2/<set>/, rename, export; then verify --stage i2 the same way.

    # 4. One table over every set and stage that has a report.
    uv run python scripts/onx_roundtrip.py summary --run r1

Layout:
    <root>/<run>/i1/<dataset>-<fmt>/   upload GPX files (flat), RUNBOOK.md, expected.json,
                                       verify_report.{json,md} after verify
    <root>/<run>/i2/<dataset>-<fmt>/   the same for the edited state (stage2)
    <root>/<run>/SUMMARY.md            written by summary

expected.json is built by re-reading Cairn's own upload files with Cairn's readers (as
onX would be handed them), so it already reflects the writer's name sanitizing, note
cleaning and colour quantizing; verify then measures only what onX changed.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402
from cairn.core.color_mapper import pattern_to_style, stroke_width_to_weight  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
DEFAULT_ROOT = FIX / "roundtrip"

# dataset -> (directory, file stem). Formats that don't exist for a dataset are skipped.
DATASETS = {
    "random": (FIX / "caltopo-random", "onx-test-random"),
    "dd100": (FIX / "dark_divide_100" / "caltopo", "2027_Dark_Divide_100_Mile_Endurance_Run"),
    "edge": (FIX / "edge_cases_onx", "edge"),
}
FORMATS = {"geojson": ".json", "gpx": ".gpx", "kml": ".kml"}

NOTE_LIMIT = bridge.ONX_IMPORT_NOTE_LIMIT  # 512 UTF-8 bytes
COORD_TOL = 1e-5

PASS, KNOWN, FAIL = "PASS", "KNOWN_ONX_LIMIT", "FAIL"
_RANK = {PASS: 0, KNOWN: 1, FAIL: 2}

KIND = {"waypoints": "waypoint", "tracks": "track", "shapes": "area"}

# Stage-2 edit plan. Icons are exact names from Cairn's onX catalogue
# (cairn/data/icon_catalog.yaml via get_all_onx_icons); the test asserts it.
ICON_CYCLE = ("Summit", "Water Source", "Camp", "Trailhead", "Parking", "Hazard",
              "Photo", "Shelter", "View", "Lookout")
WAYPOINT_COLORS = tuple(rgba for _n, rgba, _h in bridge.ONX_COLORS)   # onX's 10
LINE_COLORS = tuple(rgba for _n, rgba, _h in bridge.LINE_COLORS)      # onX's 11


# --- names --------------------------------------------------------------------------------

def tag(run: str, stage: str) -> str:
    return f"[{run}{stage}] "


def set_name(dataset: str, fmt: str) -> str:
    return f"{dataset}-{fmt}"


def onx_folder_stage1(run: str, dataset: str, fmt: str) -> str:
    return f"ZZTEST · {run} · i1 · {dataset} · {fmt}"


def onx_folder_stage2(run: str, set_: str) -> str:
    return f"ZZTEST · {run} · i2 · {set_}"


def stage_dir(root: Path, run: str, stage: str, set_: str) -> Path:
    return Path(root) / run / stage / set_


# --- engine access ------------------------------------------------------------------------

def _load(paths: list[Path]) -> dict:
    bridge.CONFIG_PATH = ROOT / "web" / "cairn_config.yaml"
    payload = [{"name": Path(p).name, "text": Path(p).read_text(encoding="utf-8")} for p in paths]
    return json.loads(bridge.load_files(json.dumps(payload)))


def _feature(uid: str):
    fkey, kind, idx = uid.rsplit("::", 2)
    return bridge._STATE["doc"].folders[fkey][kind][int(idx)]


def _points(feat) -> tuple[list, int]:
    """(points of the line / outer ring / point, number of holes)."""
    g = feat.geometry or {}
    c = g.get("coordinates") or []
    if g.get("type") == "Point":
        return [c], 0
    if g.get("type") == "LineString":
        return list(c), 0
    rings = c or [[]]
    ring = list(rings[0])
    # A closing point repeats the first: count each corner once, however written.
    if len(ring) > 1 and _close(ring[0], ring[-1]):
        ring = ring[:-1]
    return ring, max(0, len(rings) - 1)


def _close(a, b, tol: float = COORD_TOL) -> bool:
    return a is not None and b is not None and abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _rgba(s: str) -> str:
    return "".join((s or "").split())


def snapshot() -> list[dict]:
    """Every included item of the loaded document, in the shape expected.json uses."""
    out = []
    for g in bridge._STATE["groups"]:
        for item in g["items"]:
            if not item.get("included", True):
                continue
            feat = _feature(item["uid"])
            pts, holes = _points(feat)
            kind = KIND[item["kind"]]
            rec = {
                "uid": item["uid"],
                "name": item["name"],
                "kind": kind,
                "notes": item.get("desc") or "",
                "icon": item["icon"] if kind == "waypoint" else "",
                "color": _rgba(item["color"]),
                "style": None,
                "weight": None,
                "points": len(pts),
                "first": [round(pts[0][0], 6), round(pts[0][1], 6)] if pts else None,
                "last": [round(pts[-1][0], 6), round(pts[-1][1], 6)] if pts else None,
                "holes": holes,
            }
            if kind == "track":
                rec["style"] = item.get("style") or pattern_to_style(feat.pattern or "")
                rec["weight"] = item.get("weight") or stroke_width_to_weight(feat.stroke_width)
            out.append(rec)
    out.sort(key=_sort_key)
    return out


def _sort_key(r: dict):
    return (r["kind"], r["name"], r["first"] or [0, 0])


def _export_flat(dest: Path) -> tuple[list[Path], list]:
    """export_zip, written flat into dest: <NN>_<file>.gpx per zip folder, plus RUNBOOK.md."""
    data = bytes(bridge.export_zip())
    manifest = bridge._STATE.get("manifest") or []
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    written = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in sorted(z.namelist()):
            if name.endswith("/"):
                continue
            parts = name.split("/")
            if len(parts) == 1:
                target = dest / parts[0]          # RUNBOOK.md
            else:
                num = parts[0].split("_", 1)[0]
                target = dest / f"{num}_{parts[-1]}"
            target.write_bytes(z.read(name))
            if target.suffix in (".gpx", ".kml"):
                written.append(target)
    return written, manifest


def _write_expected(dest: Path, meta: dict, uploads: list[Path], manifest: list) -> dict:
    """Re-read Cairn's own upload files and record them as the expected state."""
    holes = sorted({n for e in manifest for n in e.get("holes", ())})
    _load(uploads)
    items = snapshot()
    for r in items:
        r.pop("uid", None)
    exp = {
        **meta,
        "upload_files": [p.name for p in uploads],
        "known_dropped_holes": holes,
        "items": items,
    }
    (dest / "expected.json").write_text(
        json.dumps(exp, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return exp


# --- stage 1 ------------------------------------------------------------------------------

def available_sets(only: list[str] | None = None) -> list[tuple[str, str, Path]]:
    sets = []
    for ds, (d, stem) in DATASETS.items():
        for fmt, ext in FORMATS.items():
            src = d / f"{stem}{ext}"
            if src.exists() and (not only or set_name(ds, fmt) in only):
                sets.append((ds, fmt, src))
    return sets


def stage1(run: str, root: Path = DEFAULT_ROOT, only: list[str] | None = None) -> list[dict]:
    done = []
    for ds, fmt, src in available_sets(only):
        data = _load([src])
        prefix = tag(run, "i1")
        edits = {it["uid"]: {"name": prefix + it["name"]}
                 for g in data["groups"] for it in g["items"]}
        bridge.apply_edits(json.dumps(edits))
        dest = stage_dir(root, run, "i1", set_name(ds, fmt))
        uploads, manifest = _export_flat(dest)
        folder = onx_folder_stage1(run, ds, fmt)
        _write_expected(dest, {
            "run": run, "stage": "i1", "set": set_name(ds, fmt), "dataset": ds, "format": fmt,
            "source": str(src.relative_to(ROOT)), "onx_folder": folder, "plan": "rename",
        }, uploads, manifest)
        done.append({"set": set_name(ds, fmt), "dir": dest, "onx_folder": folder,
                     "files": [p.name for p in uploads]})
    return done


# --- stage 2 ------------------------------------------------------------------------------

def _pick(cycle: tuple, i: int, current: str) -> str:
    """cycle[i], or the next entry when that one is what the item already has."""
    for k in range(len(cycle)):
        v = cycle[(i + k) % len(cycle)]
        if _rgba(v) != _rgba(current):
            return v
    return cycle[i % len(cycle)]


def edit_plan(items: list[dict], run: str) -> tuple[dict, list[dict]]:
    """The deterministic stage-2 edits for snapshot() items.

    Returns ({uid: edit}, [plan rows]). Indices come from the sorted untagged name,
    never from load order (onX reorders on import and export).
    """
    old, new = tag(run, "i1"), tag(run, "i2")
    bad = [r["name"] for r in items if not r["name"].startswith(old)]
    if bad:
        raise ValueError(f"{len(bad)} item(s) lack the {old.strip()!r} tag, e.g. {bad[:3]}: "
                         "is this the right onX export?")
    suffix_body = f"— edited {run}i2"
    by_kind: dict[str, list[dict]] = {}
    for r in sorted(items, key=lambda r: (r["kind"], r["name"][len(old):], r["first"] or [0, 0])):
        by_kind.setdefault(r["kind"], []).append(r)
    edits, rows = {}, []
    for kind, rs in by_kind.items():
        for i, r in enumerate(rs):
            base = r["name"][len(old):]
            note = r["notes"]
            suffix = ("\n" + suffix_body) if note else suffix_body
            budget = NOTE_LIMIT - len(suffix.encode("utf-8"))
            truncated = len(note.encode("utf-8")) > budget
            if truncated:
                # onX's limit is 512 UTF-8 bytes; cut on a character boundary.
                note = note.encode("utf-8")[:budget].decode("utf-8", "ignore")
            e = {"name": new + base, "desc": note + suffix}
            row = {"kind": kind, "from": r["name"], "to": new + base,
                   "note_truncated_to_fit": truncated}
            if kind == "waypoint":
                e["icon"] = _pick(ICON_CYCLE, i, r["icon"])
                e["color"] = _pick(WAYPOINT_COLORS, i, r["color"])
                row.update(icon=[r["icon"], e["icon"]], color=[r["color"], e["color"]])
            elif kind == "track":
                e["style"] = "dash" if r["style"] == "solid" else "solid"
                e["weight"] = "4.0" if r["weight"] == "6.0" else "6.0"
                e["color"] = _pick(LINE_COLORS, i, r["color"])
                row.update(style=[r["style"], e["style"]], weight=[r["weight"], e["weight"]],
                           color=[r["color"], e["color"]])
            else:
                e["color"] = _pick(LINE_COLORS, i, r["color"])
                row.update(color=[r["color"], e["color"]])
            edits[r["uid"]] = e
            rows.append(row)
    return edits, rows


def stage2(run: str, set_: str, onx_files: list[Path], root: Path = DEFAULT_ROOT) -> dict:
    _load(onx_files)
    edits, rows = edit_plan(snapshot(), run)
    bridge.apply_edits(json.dumps(edits))
    dest = stage_dir(root, run, "i2", set_)
    uploads, manifest = _export_flat(dest)
    folder = onx_folder_stage2(run, set_)
    _write_expected(dest, {
        "run": run, "stage": "i2", "set": set_, "onx_folder": folder,
        "source": [Path(p).name for p in onx_files], "plan": "edit", "edits": rows,
    }, uploads, manifest)
    return {"set": set_, "dir": dest, "onx_folder": folder, "files": [p.name for p in uploads]}


# --- verify -------------------------------------------------------------------------------

def _norm_note(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _nbytes(s: str) -> int:
    return len(s.encode("utf-8"))


def classify(exp: dict, act: dict, known_holes: tuple = ()) -> list[tuple[str, str, str]]:
    """[(field, status, detail)] for one matched expected/actual pair. Pure."""
    out = []

    def eq(field, a, b):
        out.append((field, PASS, "") if a == b else (field, FAIL, f"expected {a!r}, got {b!r}"))

    eq("name", exp["name"], act["name"])
    en, an = _norm_note(exp["notes"]), _norm_note(act["notes"])
    if en == an:
        out.append(("notes", PASS, ""))
    elif _nbytes(en) > NOTE_LIMIT and an == "":
        out.append(("notes", KNOWN, f"{_nbytes(en)}-byte note dropped by onX import"))
    elif _nbytes(en) > NOTE_LIMIT and _nbytes(an) <= NOTE_LIMIT and en.startswith(an):
        out.append(("notes", KNOWN, f"{_nbytes(en)}-byte note cut to {_nbytes(an)} by onX import"))
    else:
        out.append(("notes", FAIL, f"expected {len(en)} chars {en[:60]!r}…, "
                                   f"got {len(an)} chars {an[:60]!r}…"))
    if exp["kind"] == "waypoint":
        eq("icon", exp["icon"], act["icon"])
    eq("color", _rgba(exp["color"]), _rgba(act["color"]))
    if exp["kind"] == "track":
        eq("style", exp["style"], act["style"])
        eq("weight", exp["weight"], act["weight"])
    ends = _close(exp["first"], act["first"]) and _close(exp["last"], act["last"])
    if exp["points"] == act["points"] and ends:
        out.append(("points", PASS, ""))
    elif act["points"] < exp["points"] and ends and exp["kind"] != "waypoint":
        out.append(("points", KNOWN, f"thinned by onX: {exp['points']} -> {act['points']} "
                                     "points, same end points"))
    else:
        out.append(("points", FAIL, f"expected {exp['points']} points {exp['first']}..{exp['last']}, "
                                    f"got {act['points']} {act['first']}..{act['last']}"))
    if exp["kind"] == "area" and exp["name"] in known_holes:
        out.append(("holes", KNOWN, "source area had holes; onX areas are single-ring"))
    return out


def status_of(fields: list[tuple[str, str, str]]) -> str:
    return max((s for _f, s, _d in fields), key=_RANK.get, default=PASS)


def match(expected: list[dict], actual: list[dict]) -> tuple[list, list, list]:
    """Pair items by (kind, name), duplicates in coordinate order; leftovers of the same
    kind pair by first point. Returns (pairs, missing, unexpected)."""
    def groups(items):
        g: dict = {}
        for r in sorted(items, key=_sort_key):
            g.setdefault((r["kind"], r["name"]), []).append(r)
        return g

    ge, ga = groups(expected), groups(actual)
    pairs, left_e, left_a = [], [], []
    for key in sorted(set(ge) | set(ga)):
        e, a = ge.get(key, []), ga.get(key, [])
        pairs += list(zip(e, a))
        left_e += e[len(a):]
        left_a += a[len(e):]
    missing = []
    for e in left_e:
        hit = next((a for a in left_a if a["kind"] == e["kind"] and _close(a["first"], e["first"], 1e-4)), None)
        if hit is None:
            missing.append(e)
        else:
            left_a.remove(hit)
            pairs.append((e, hit))
    return pairs, missing, left_a


def verify(run: str, stage: str, set_: str, onx_files: list[Path],
           root: Path = DEFAULT_ROOT) -> dict:
    d = stage_dir(root, run, stage, set_)
    exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
    _load(onx_files)
    actual = snapshot()
    pairs, missing, unexpected = match(exp["items"], actual)
    holes = tuple(exp.get("known_dropped_holes") or ())
    results = []
    for e, a in pairs:
        fields = classify(e, a, holes)
        results.append({"kind": e["kind"], "name": e["name"], "status": status_of(fields),
                        "fields": [{"field": f, "status": s, "detail": x}
                                   for f, s, x in fields if s != PASS]})
    for e in missing:
        results.append({"kind": e["kind"], "name": e["name"], "status": FAIL,
                        "fields": [{"field": "item", "status": FAIL,
                                    "detail": "missing from the onX export"}]})
    for a in unexpected:
        results.append({"kind": a["kind"], "name": a["name"], "status": FAIL,
                        "fields": [{"field": "item", "status": FAIL,
                                    "detail": "in the onX export but not expected"}]})
    results.sort(key=lambda r: (-_RANK[r["status"]], r["kind"], r["name"]))
    counts = {s: sum(r["status"] == s for r in results) for s in (PASS, KNOWN, FAIL)}
    report = {"run": run, "stage": stage, "set": set_, "onx_files": [Path(p).name for p in onx_files],
              "expected_items": len(exp["items"]), "actual_items": len(actual),
              "items": len(results), "counts": counts, "results": results}
    (d / "verify_report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (d / "verify_report.md").write_text(_report_md(report, exp), encoding="utf-8")
    return report


def _report_md(rep: dict, exp: dict) -> str:
    c = rep["counts"]
    L = [f"# Verify {rep['run']} · {rep['stage']} · {rep['set']}", "",
         f"onX folder: `{exp.get('onx_folder', '')}`  ",
         f"onX export read: {', '.join(rep['onx_files'])}  ",
         f"Expected {rep['expected_items']} items, onX export has {rep['actual_items']}.", "",
         f"**{c[PASS]} PASS · {c[KNOWN]} KNOWN_ONX_LIMIT · {c[FAIL]} FAIL**", ""]
    flagged = [r for r in rep["results"] if r["status"] != PASS]
    if flagged:
        L += ["| Status | Kind | Name | Field | Detail |", "|---|---|---|---|---|"]
        for r in flagged:
            for f in r["fields"]:
                detail = f["detail"].replace("|", "\\|").replace("\n", "⏎")
                L.append(f"| {f['status']} | {r['kind']} | {r['name']} | {f['field']} | {detail} |")
        L.append("")
    else:
        L += ["Every item matched on name, notes, icon, colour, style, weight and points.", ""]
    return "\n".join(L)


# --- summary ------------------------------------------------------------------------------

def summary(run: str, root: Path = DEFAULT_ROOT) -> str:
    base = Path(root) / run
    L = [f"# Round-trip summary: {run}", "",
         "| Stage | Set | Items | PASS | KNOWN_ONX_LIMIT | FAIL |", "|---|---|---|---|---|---|"]
    for stage in ("i1", "i2"):
        for d in sorted((base / stage).glob("*/")) if (base / stage).exists() else []:
            rp = d / "verify_report.json"
            if rp.exists():
                r = json.loads(rp.read_text(encoding="utf-8"))
                c = r["counts"]
                L.append(f"| {stage} | {d.name} | {r['items']} | {c[PASS]} | {c[KNOWN]} | {c[FAIL]} |")
            elif (d / "expected.json").exists():
                n = len(json.loads((d / "expected.json").read_text(encoding="utf-8"))["items"])
                L.append(f"| {stage} | {d.name} | {n} | not verified | | |")
    text = "\n".join(L) + "\n"
    if base.exists():
        (base / "SUMMARY.md").write_text(text, encoding="utf-8")
    return text


# --- CLI ----------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="output root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("stage1", help="CalTopo -> Cairn upload files, tagged [<run>i1]")
    s1.add_argument("--run", required=True)
    s1.add_argument("--set", action="append", help="limit to <dataset>-<fmt> (repeatable)")
    v = sub.add_parser("verify", help="compare an onX export with expected.json")
    v.add_argument("--run", required=True)
    v.add_argument("--stage", required=True, choices=("i1", "i2"))
    v.add_argument("--set", required=True)
    v.add_argument("--onx", required=True, nargs="+", type=Path)
    s2 = sub.add_parser("stage2", help="onX export -> edit plan -> upload files, tagged [<run>i2]")
    s2.add_argument("--run", required=True)
    s2.add_argument("--set", required=True)
    s2.add_argument("--onx", required=True, nargs="+", type=Path)
    sm = sub.add_parser("summary", help="table over every verified set")
    sm.add_argument("--run", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "stage1":
        for r in stage1(a.run, a.root, a.set):
            print(f"{r['dir'].relative_to(ROOT) if r['dir'].is_relative_to(ROOT) else r['dir']}")
            print(f"    files:  {', '.join(r['files'])}")
            print(f"    rename the onX import folder to:  {r['onx_folder']}")
        return 0
    if a.cmd == "stage2":
        r = stage2(a.run, a.set, a.onx, a.root)
        print(r["dir"])
        print(f"    files:  {', '.join(r['files'])}")
        print(f"    rename the onX import folder to:  {r['onx_folder']}")
        return 0
    if a.cmd == "verify":
        rep = verify(a.run, a.stage, a.set, a.onx, a.root)
        c = rep["counts"]
        print(f"{a.set} {a.stage}: {rep['items']} items: {c[PASS]} PASS, "
              f"{c[KNOWN]} KNOWN_ONX_LIMIT, {c[FAIL]} FAIL")
        print(f"    report: {stage_dir(a.root, a.run, a.stage, a.set) / 'verify_report.md'}")
        return 1 if c[FAIL] else 0
    print(summary(a.run, a.root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
