from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


BITTERROOTS_COMPLETE_FIXTURE_REL = Path("tests/fixtures/bitterroots/Bitterroots__Complete_.json")


def repo_root() -> Path:
    # tests/ -> repo root
    return Path(__file__).resolve().parents[1]


def artifacts_enabled() -> bool:
    v = (os.getenv("CAIRN_TUI_ARTIFACTS") or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def get_bitterroots_complete_fixture(*, min_bytes: int = 1_000_000) -> Path:
    """
    Canonical large CalTopo dataset fixture for TUI regression tests.

    We keep it under tests/fixtures so it's part of the test contract and less
    likely to be accidentally deleted than demo assets.
    """
    p = repo_root() / BITTERROOTS_COMPLETE_FIXTURE_REL
    assert p.exists(), f"Missing fixture: {p}"
    assert p.is_file(), f"Fixture path is not a file: {p}"
    sz = p.stat().st_size
    assert sz >= min_bytes, f"Fixture too small ({sz} bytes): {p}"
    return p


def copy_fixture_to_tmp(tmp_path: Path, *, min_bytes: int = 1_000_000) -> Path:
    src = get_bitterroots_complete_fixture(min_bytes=min_bytes)
    dst = tmp_path / "Bitterroots__Complete__copy.json"
    shutil.copy2(src, dst)
    return dst


def _renderable_to_str(obj: Any) -> str:
    if obj is None:
        return ""
    plain = getattr(obj, "plain", None)
    if isinstance(plain, str):
        return plain
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def _safe_query(app: Any, selector: str) -> Optional[Any]:
    try:
        return app.query_one(selector)
    except Exception:
        return None


def _dump_datatable(table: Any, *, max_rows: int = 25) -> dict[str, Any]:
    """
    Best-effort extraction of a DataTable for artifacts.

    We intentionally cap rows to keep artifacts small even for Bitterroots Complete.
    """
    out: dict[str, Any] = {"row_count": None, "columns": [], "rows": [], "truncated": None}

    try:
        row_count = int(getattr(table, "row_count", 0) or 0)
    except Exception:
        row_count = None
    out["row_count"] = row_count

    # Column labels (best effort)
    try:
        cols = getattr(table, "columns", None) or []
        out["columns"] = [str(getattr(c, "label", None) or getattr(c, "key", None) or c) for c in cols]
    except Exception:
        out["columns"] = []

    # Rows (best effort; APIs vary across Textual versions)
    rows: list[list[str]] = []
    try:
        if row_count is None:
            row_count = len(getattr(table, "rows", {}) or {})
        take = min(int(row_count or 0), max_rows)

        if hasattr(table, "get_row_at"):
            for i in range(take):
                r = table.get_row_at(i)  # type: ignore[misc]
                rows.append([_renderable_to_str(x) for x in (r or [])])
        else:
            row_keys = list((getattr(table, "rows", {}) or {}).keys())[:take]
            for rk in row_keys:
                if hasattr(table, "get_row"):
                    r = table.get_row(rk)  # type: ignore[misc]
                    rows.append([_renderable_to_str(x) for x in (r or [])])
    except Exception:
        pass

    out["rows"] = rows
    if row_count is not None and isinstance(row_count, int):
        out["truncated"] = row_count > len(rows)

    return out


@dataclass
class ArtifactRecorder:
    scenario: str
    enabled: bool = field(default_factory=artifacts_enabled)
    base_dir: Optional[Path] = None
    snapshots: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.enabled:
            return
        self.base_dir = repo_root() / "artifacts" / "tui" / self.scenario
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self, app: Any, *, label: str, extra: Optional[dict[str, Any]] = None) -> None:
        if not self.enabled or self.base_dir is None:
            return

        title_w = _safe_query(app, "#main_title")
        subtitle_w = _safe_query(app, "#main_subtitle")
        status_w = _safe_query(app, "#status")

        def _render_widget(w: Any) -> str:
            if w is None:
                return ""
            try:
                if hasattr(w, "render"):
                    return _renderable_to_str(w.render())
                return _renderable_to_str(getattr(w, "renderable", w))
            except Exception:
                return _renderable_to_str(w)

        data: dict[str, Any] = {
            "label": label,
            "step": getattr(app, "step", None),
            "done_steps": sorted(list(getattr(app, "_done_steps", set()) or [])),
            "main_title": _render_widget(title_w),
            "main_subtitle": _render_widget(subtitle_w),
            "status_text": _render_widget(status_w),
            "selected_folder_id": getattr(getattr(app, "model", None), "selected_folder_id", None),
            "selected_route_keys": sorted(list(getattr(app, "_selected_route_keys", set()) or [])),
            "selected_waypoint_keys": sorted(list(getattr(app, "_selected_waypoint_keys", set()) or [])),
            "export_in_progress": bool(getattr(app, "_export_in_progress", False)),
            "export_error": getattr(app, "_export_error", None),
            "export_manifest": getattr(app, "_export_manifest", None),
            "debug_events": getattr(app, "_debug_events", None),
            "focused": {
                "type": type(getattr(app, "focused", None)).__name__ if getattr(app, "focused", None) else None,
                "id": getattr(getattr(app, "focused", None), "id", None) if getattr(app, "focused", None) else None,
            },
        }
        if extra:
            data["extra"] = extra

        tables: dict[str, Any] = {}
        for tid in (
            "folder_table",
            "routes_table",
            "waypoints_table",
            "preview_waypoints",
            "preview_routes",
            "manifest",
            # Modals (editing)
            "actions_table",
            "palette_table",
            "icon_table",
        ):
            tbl = _safe_query(app, f"#{tid}")
            if tbl is None:
                continue
            if type(tbl).__name__ != "DataTable":
                continue
            tables[tid] = _dump_datatable(tbl)
        if tables:
            data["tables"] = tables

        fn = f"{len(self.snapshots):03d}_{label}.json"
        (self.base_dir / fn).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        self.snapshots.append(fn)

    def write_index(self) -> None:
        if not self.enabled or self.base_dir is None:
            return
        lines = [f"# TUI artifacts: {self.scenario}", ""]
        for s in self.snapshots:
            lines.append(f"- `{s}`")
        (self.base_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
