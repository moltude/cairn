"""Guards the boundary between the web app and the engine package.

web/bridge.py is the only consumer of `cairn` (the CLI and TUI were removed;
see git tag `cli-final`). WEB_ENGINE below is the set of modules it actually
reaches, and each of them carries a "Web engine" header comment. Since roadmap
Phase 2 that includes the GPX/KML readers (CalTopo GPX, onX GPX and KML), the
onX GPX+KML merge and the MapDocument->ParsedData adapter. Everything else in
cairn/ is engine code not yet wired into the web app (dedup, ...) -- kept as
the base for future web features.

If this test fails because bridge.py started importing something new, add the
module here AND give it the header comment, so the marking stays truthful.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WEB_ENGINE = {
    "cairn/core/color_mapper.py",
    "cairn/core/config.py",
    "cairn/core/icon_resolver.py",
    "cairn/core/mapper.py",
    "cairn/core/merge.py",
    "cairn/core/normalization.py",
    "cairn/core/parser.py",
    "cairn/core/writers.py",
    "cairn/io/caltopo_gpx.py",
    "cairn/io/caltopo_kml.py",
    "cairn/io/document_adapter.py",
    "cairn/io/input_check.py",
    "cairn/io/onx_gpx.py",
    "cairn/io/onx_kml.py",
    "cairn/model.py",
    "cairn/utils/utils.py",
}

# Never importable from the browser bundle (and no longer dependencies at all).
FORBIDDEN = {"typer", "rich", "textual", "prompt_toolkit", "click"}

HEADER = "# Web engine:"


def _module_path(name: str) -> str | None:
    base = ROOT.joinpath(*name.split("."))
    for cand in (base.with_suffix(".py"), base / "__init__.py"):
        if cand.exists():
            return cand.relative_to(ROOT).as_posix()
    return None


def _imports(path: str) -> tuple[set[str], set[str]]:
    """Return (cairn module paths, top-level third-party names) imported by path."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    local, external = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        else:
            continue
        for name in names:
            if not name.startswith("cairn"):
                external.add(name.split(".")[0])
                continue
            parts = name.split(".")
            for i in range(1, len(parts) + 1):
                p = _module_path(".".join(parts[:i]))
                if p:
                    local.add(p)
    return local, external


def _reachable_from_bridge() -> tuple[set[str], set[str]]:
    seen, external, stack = set(), set(), ["web/bridge.py"]
    while stack:
        path = stack.pop()
        if path in seen:
            continue
        seen.add(path)
        local, ext = _imports(path)
        external |= ext
        stack.extend(local - seen)
    modules = {p for p in seen if p.startswith("cairn/") and not p.endswith("__init__.py")}
    return modules, external


def test_web_engine_set_matches_what_bridge_imports():
    modules, _ = _reachable_from_bridge()
    assert modules == WEB_ENGINE


def test_web_engine_has_no_terminal_ui_imports():
    _, external = _reachable_from_bridge()
    assert not (external & FORBIDDEN)


def test_every_web_engine_module_is_marked():
    for path in sorted(WEB_ENGINE):
        assert (ROOT / path).read_text(encoding="utf-8").startswith(HEADER), path


def test_no_other_module_claims_to_be_web_engine():
    for path in sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "cairn").rglob("*.py")):
        if path not in WEB_ENGINE:
            assert not (ROOT / path).read_text(encoding="utf-8").startswith(HEADER), path
