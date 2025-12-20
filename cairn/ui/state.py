from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


STATE_VERSION = 1


def _user_state_dir(app_name: str = "cairn") -> Path:
    """
    Return an OS-appropriate user data directory.

    - macOS: ~/Library/Application Support/<app_name>/
    - Linux/Unix: ~/.config/<app_name>/
    - Windows: %APPDATA%\\<app_name>\\  (best-effort; not primary target)
    """
    home = Path.home()
    plat = sys.platform.lower()

    if plat == "darwin":
        return home / "Library" / "Application Support" / app_name

    if plat.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / app_name
        return home / app_name

    # Linux / other POSIX
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else (home / ".config")
    return base / app_name


def default_state_path() -> Path:
    return _user_state_dir("cairn") / "state.json"


@dataclass
class UIState:
    version: int = STATE_VERSION
    favorites: List[str] = field(default_factory=list)
    recent_paths: List[str] = field(default_factory=list)
    default_root: Optional[str] = None

    # Extension hook: we may add per-path metadata later without breaking schema.
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": int(self.version),
            "favorites": list(self.favorites),
            "recent_paths": list(self.recent_paths),
            "default_root": self.default_root,
            "meta": dict(self.meta),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "UIState":
        s = UIState()
        s.version = int(d.get("version") or STATE_VERSION)
        s.favorites = [str(p) for p in (d.get("favorites") or []) if p]
        s.recent_paths = [str(p) for p in (d.get("recent_paths") or []) if p]
        s.default_root = d.get("default_root") or None
        s.meta = dict(d.get("meta") or {})
        return s


def load_state(path: Optional[Path] = None) -> UIState:
    p = Path(path) if path is not None else default_state_path()
    if not p.exists():
        return UIState()
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return UIState()
        return UIState.from_dict(data)
    except Exception:
        return UIState()


def save_state(state: UIState, path: Optional[Path] = None) -> None:
    p = Path(path) if path is not None else default_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalize_path_str(p: Path) -> str:
    try:
        return str(p.expanduser().resolve())
    except Exception:
        return str(Path(p).expanduser())


def add_recent(state: UIState, p: Path, *, limit: int = 20) -> UIState:
    s = state
    ps = _normalize_path_str(p)
    s.recent_paths = [x for x in s.recent_paths if x != ps]
    s.recent_paths.insert(0, ps)
    if limit > 0:
        s.recent_paths = s.recent_paths[:limit]
    return s


def add_favorite(state: UIState, p: Path) -> UIState:
    s = state
    ps = _normalize_path_str(p)
    if ps not in s.favorites:
        s.favorites.append(ps)
    return s


def remove_favorite(state: UIState, p: Path) -> UIState:
    s = state
    ps = _normalize_path_str(p)
    s.favorites = [x for x in s.favorites if x != ps]
    return s


def set_default_root(state: UIState, p: Optional[Path]) -> UIState:
    s = state
    s.default_root = _normalize_path_str(p) if p is not None else None
    return s
