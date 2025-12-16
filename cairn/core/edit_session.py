"""
Edit session persistence for CalTopo → OnX interactive editing.

Goal: make the interactive editing step resumable and non-fragile by saving
user edits (names/descriptions/colors/icon overrides) to a small JSON file.

The session is keyed by a stable identifier per feature:
  (folder_id, kind, feature_id)

If a feature has no id (rare), we fall back to a fingerprint based on geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Dict, Optional

from cairn.core.parser import ParsedData, ParsedFeature


SESSION_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_str(v: Any) -> str:
    return (v or "").strip()


def feature_key(*, kind: str, folder_id: str, feature: ParsedFeature) -> str:
    """
    Compute a stable key for a ParsedFeature.

    Prefer GeoJSON feature.id when present. Otherwise fall back to a geometry-based
    fingerprint that should remain stable across reruns of the same input file.
    """
    kind_n = _norm_str(kind).lower()
    folder_n = _norm_str(folder_id)
    fid = _norm_str(getattr(feature, "id", ""))
    if fid:
        return f"{folder_n}:{kind_n}:{fid}"

    # Fallback: fingerprint on geometry + title (title is last-resort; geometry dominates).
    geom = getattr(feature, "geometry", None) or {}
    gtype = _norm_str(getattr(feature, "geometry_type", None) or geom.get("type"))
    coords = getattr(feature, "coordinates", None)
    title = _norm_str(getattr(feature, "title", ""))
    payload = json.dumps(
        {
            "folder": folder_n,
            "kind": kind_n,
            "gtype": gtype,
            "coords": coords,
            "title": title,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{folder_n}:{kind_n}:fp:{digest}"


def _input_fingerprint(path: Path) -> str:
    """
    Best-effort input fingerprint used to detect mismatch (different file/run).
    """
    p = Path(path)
    try:
        st = p.stat()
        return f"{p.name}:{int(st.st_size)}:{int(st.st_mtime)}"
    except Exception:
        return p.name


@dataclass
class EditRecord:
    """
    Minimal persisted delta for a feature. All fields are optional; only set when edited.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    # For waypoints: marker color in the existing ParsedFeature field format (e.g. "FF3300").
    color: Optional[str] = None
    # For tracks: hex stroke with '#', e.g. "#FF0000".
    stroke: Optional[str] = None
    # Optional override icon (stored in ParsedFeature.properties under cairn_onx_icon_override).
    onx_icon_override: Optional[str] = None


@dataclass
class EditSession:
    """
    Session container written as JSON.
    """

    version: int = SESSION_VERSION
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    input_fingerprint: Optional[str] = None
    edits: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # key -> record dict

    def touch(self) -> None:
        self.updated_at = _now_iso()

    def record(self, *, key: str, record: EditRecord) -> None:
        d: Dict[str, Any] = {}
        if record.title is not None:
            d["title"] = record.title
        if record.description is not None:
            d["description"] = record.description
        if record.color is not None:
            d["color"] = record.color
        if record.stroke is not None:
            d["stroke"] = record.stroke
        if record.onx_icon_override is not None:
            d["onx_icon_override"] = record.onx_icon_override
        if not d:
            return
        self.edits[key] = d
        self.touch()

    def apply_to_parsed_data(self, parsed_data: ParsedData) -> int:
        """
        Apply saved edits to ParsedData in-place.

        Returns number of features updated.
        """
        updated = 0
        folders = getattr(parsed_data, "folders", {}) or {}
        for folder_id, folder in folders.items():
            for wp in folder.get("waypoints", []) or []:
                updated += _apply_one(
                    self, kind="waypoint", folder_id=folder_id, feature=wp
                )
            for trk in folder.get("tracks", []) or []:
                updated += _apply_one(
                    self, kind="track", folder_id=folder_id, feature=trk
                )
            # Shapes are not edited in the current interactive editor.
        return updated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": int(self.version),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "input_fingerprint": self.input_fingerprint,
            "edits": self.edits,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "EditSession":
        s = EditSession()
        s.version = int(d.get("version") or SESSION_VERSION)
        s.created_at = str(d.get("created_at") or _now_iso())
        s.updated_at = str(d.get("updated_at") or s.created_at)
        s.input_fingerprint = d.get("input_fingerprint") or None
        s.edits = dict(d.get("edits") or {})
        return s


def _apply_one(
    session: EditSession, *, kind: str, folder_id: str, feature: ParsedFeature
) -> int:
    key = feature_key(kind=kind, folder_id=folder_id, feature=feature)
    rec = session.edits.get(key)
    if not isinstance(rec, dict) or not rec:
        return 0

    changed = False
    if "title" in rec and rec["title"] is not None:
        feature.title = str(rec["title"])
        changed = True
    if "description" in rec and rec["description"] is not None:
        feature.description = str(rec["description"])
        changed = True

    if kind.lower() == "waypoint":
        if "color" in rec and rec["color"] is not None:
            feature.color = str(rec["color"])
            changed = True
        if "onx_icon_override" in rec:
            ov = (rec.get("onx_icon_override") or "").strip()
            if isinstance(getattr(feature, "properties", None), dict):
                if ov:
                    feature.properties["cairn_onx_icon_override"] = ov
                else:
                    feature.properties.pop("cairn_onx_icon_override", None)
                changed = True
    elif kind.lower() == "track":
        if "stroke" in rec and rec["stroke"] is not None:
            feature.stroke = str(rec["stroke"])
            changed = True

    return 1 if changed else 0


def load_session(path: Path) -> Optional[EditSession]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return EditSession.from_dict(data)
    except Exception:
        return None


def save_session(path: Path, session: EditSession) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(session.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def init_or_load_session(*, path: Path, input_path: Path) -> EditSession:
    sess = load_session(path)
    if sess is None:
        sess = EditSession()
    # Always refresh input fingerprint; used for mismatch warnings in the caller.
    sess.input_fingerprint = _input_fingerprint(Path(input_path))
    sess.touch()
    return sess
