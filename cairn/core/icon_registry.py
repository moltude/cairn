"""
Icon mapping registry + inventories.

Goals:
- Centralize CalTopo ↔ OnX icon mapping data in a repo-versioned YAML file
- Provide deterministic mapping decisions and inventories for per-run reporting
- Append observed icon labels to an append-only catalog (no auto-mapping)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from cairn.core.color_mapper import ColorMapper
from cairn.core.config import GENERIC_SYMBOLS, IconMappingConfig, get_icon_color
from cairn.core.icon_resolver import IconDecision, IconResolver
from cairn.core.matcher import FuzzyIconMatcher
from cairn.model import MapDocument


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_data_dir() -> Path:
    # cairn/core/icon_registry.py -> cairn/core -> cairn -> <repo>
    cairn_pkg = Path(__file__).resolve().parents[1]
    return cairn_pkg / "data"


def default_mappings_path() -> Path:
    return _repo_data_dir() / "icon_mappings.yaml"


def default_catalog_path() -> Path:
    return _repo_data_dir() / "icon_catalog.yaml"


def _as_dict(value: Any, *, label: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping/dict")
    return value


def _as_list(value: Any, *, label: str) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    raise ValueError(f"{label} must be a list")


def _norm_symbol(s: str) -> str:
    return (s or "").strip().lower()


@dataclass(frozen=True)
class InventoryEntry:
    label: str
    count: int
    examples: Tuple[str, ...] = ()


@dataclass(frozen=True)
class IconReportRow:
    incoming: str
    mapped: str
    mapping_source: str
    count: int
    examples: Tuple[str, ...] = ()
    colors: Tuple[str, ...] = ()


class IconRegistry:
    """
    Load icon mappings from YAML and provide mapping/inventory helpers.
    """

    def __init__(
        self,
        *,
        mappings_path: Optional[Path] = None,
        catalog_path: Optional[Path] = None,
    ):
        self.mappings_path = (mappings_path or default_mappings_path()).resolve()
        self.catalog_path = (catalog_path or default_catalog_path()).resolve()

        self._raw: Dict[str, Any] = {}
        self.policies: Dict[str, Any] = {}

        # CalTopo -> OnX
        self.caltopo_default_icon: str = "Location"
        self.caltopo_generic_symbols: Tuple[str, ...] = ()
        self.caltopo_symbol_map: Dict[str, str] = {}
        self.caltopo_keyword_map: Dict[str, List[str]] = {}

        # OnX -> CalTopo
        self.onx_default_symbol: str = "point"
        self.onx_icon_map: Dict[str, str] = {}

        # Lazy/cache
        self._caltopo_resolver: Optional[IconResolver] = None
        self._onx_matcher: Optional[FuzzyIconMatcher] = None

        self.load()

    def load(self) -> None:
        if not self.mappings_path.exists():
            raise ValueError(f"Icon mappings file not found: {self.mappings_path}")
        raw = yaml.safe_load(self.mappings_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("Icon mappings YAML must be a dict at the top level")
        self._raw = raw

        version = raw.get("version")
        if version != 1:
            raise ValueError(f"Unsupported icon mappings version: {version!r} (expected 1)")

        self.policies = _as_dict(raw.get("policies"), label="policies")
        unknown_policy = str(self.policies.get("unknown_icon_handling") or "").strip()
        if unknown_policy and unknown_policy not in ("keep_point_and_append_to_description",):
            raise ValueError(
                "policies.unknown_icon_handling must be one of: "
                "keep_point_and_append_to_description"
            )

        # CalTopo -> OnX section
        c2o = _as_dict(raw.get("caltopo_to_onx"), label="caltopo_to_onx")
        self.caltopo_default_icon = str(c2o.get("default_icon") or "Location").strip() or "Location"
        self.caltopo_generic_symbols = tuple(_norm_symbol(s) for s in _as_list(c2o.get("generic_symbols"), label="caltopo_to_onx.generic_symbols"))

        symbol_map_in = _as_dict(c2o.get("symbol_map"), label="caltopo_to_onx.symbol_map")
        self.caltopo_symbol_map = {_norm_symbol(k): str(v).strip() for k, v in symbol_map_in.items() if _norm_symbol(k) and str(v).strip()}

        keyword_map_in = _as_dict(c2o.get("keyword_map"), label="caltopo_to_onx.keyword_map")
        keyword_map: Dict[str, List[str]] = {}
        for icon, kws in keyword_map_in.items():
            icon_name = str(icon).strip()
            if not icon_name:
                continue
            kw_list = []
            for kw in _as_list(kws, label=f"caltopo_to_onx.keyword_map.{icon_name}"):
                kw_norm = str(kw).strip()
                if kw_norm:
                    kw_list.append(kw_norm)
            keyword_map[icon_name] = kw_list
        self.caltopo_keyword_map = keyword_map

        # OnX -> CalTopo section
        o2c = _as_dict(raw.get("onx_to_caltopo"), label="onx_to_caltopo")
        self.onx_default_symbol = _norm_symbol(str(o2c.get("default_symbol") or "point")) or "point"
        icon_map_in = _as_dict(o2c.get("icon_map"), label="onx_to_caltopo.icon_map")
        self.onx_icon_map = {str(k).strip(): _norm_symbol(str(v)) for k, v in icon_map_in.items() if str(k).strip() and _norm_symbol(str(v))}

        # Clear lazy caches if reload happens.
        self._caltopo_resolver = None
        self._onx_matcher = None

    def should_append_unknown_icon_to_description(self) -> bool:
        return (self.policies.get("unknown_icon_handling") or "").strip() == "keep_point_and_append_to_description"

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------
    def caltopo_to_onx_resolver(self) -> IconResolver:
        if self._caltopo_resolver is None:
            self._caltopo_resolver = IconResolver(
                symbol_map=self.caltopo_symbol_map,
                keyword_map=self.caltopo_keyword_map,
                default_icon=self.caltopo_default_icon,
                generic_symbols=set(self.caltopo_generic_symbols),
            )
        return self._caltopo_resolver

    def resolve_caltopo_to_onx(self, *, title: str, description: str = "", symbol: str = "") -> IconDecision:
        return self.caltopo_to_onx_resolver().resolve(title or "", description or "", symbol or "")

    def map_onx_icon_to_caltopo_symbol(self, OnX_icon: Optional[str]) -> Tuple[str, str]:
        """
        Returns: (symbol, mapping_source)
        mapping_source is one of: 'direct', 'default'
        """
        icon = (OnX_icon or "").strip()
        if not icon:
            return self.onx_default_symbol, "default"
        mapped = self.onx_icon_map.get(icon)
        if mapped:
            return mapped, "direct"
        return self.onx_default_symbol, "default"

    def onx_fuzzy_suggestions(self, OnX_icon: str, *, valid_caltopo_symbols: Sequence[str], top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Best-effort fuzzy suggestions for OnX icon -> CalTopo symbol.
        This is advisory only (we do not auto-map).
        """
        if self._onx_matcher is None:
            self._onx_matcher = FuzzyIconMatcher(list(valid_caltopo_symbols))
        return self._onx_matcher.find_best_matches(OnX_icon, top_n=top_n)

    # ------------------------------------------------------------------
    # Inventories (for reporting + catalog)
    # ------------------------------------------------------------------
    def collect_onx_icon_inventory(self, doc: MapDocument, *, example_limit: int = 3) -> List[InventoryEntry]:
        counts: Dict[str, int] = {}
        examples: Dict[str, List[str]] = {}
        for wp in doc.waypoints():
            icon = (wp.style.OnX_icon or "").strip() or "(missing)"
            counts[icon] = counts.get(icon, 0) + 1
            if wp.name and len(examples.get(icon, [])) < example_limit:
                examples.setdefault(icon, []).append(wp.name)

        return [
            InventoryEntry(label=k, count=v, examples=tuple(examples.get(k, [])))
            for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

    def collect_onx_icon_mapping_rows(
        self,
        doc: MapDocument,
        *,
        example_limit: int = 3,
        color_limit: int = 3,
    ) -> List[IconReportRow]:
        # Aggregate per incoming icon
        counts: Dict[str, int] = {}
        examples: Dict[str, List[str]] = {}
        colors: Dict[str, List[str]] = {}
        for wp in doc.waypoints():
            icon = (wp.style.OnX_icon or "").strip() or "(missing)"
            counts[icon] = counts.get(icon, 0) + 1
            if wp.name and len(examples.get(icon, [])) < example_limit:
                examples.setdefault(icon, []).append(wp.name)
            c = (wp.style.OnX_color_rgba or "").strip()
            if c:
                cur = colors.setdefault(icon, [])
                if c not in cur and len(cur) < color_limit:
                    cur.append(c)

        rows: List[IconReportRow] = []
        for icon, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            mapped, src = self.map_onx_icon_to_caltopo_symbol(None if icon == "(missing)" else icon)
            rows.append(
                IconReportRow(
                    incoming=icon,
                    mapped=mapped,
                    mapping_source=src,
                    count=n,
                    examples=tuple(examples.get(icon, [])),
                    colors=tuple(colors.get(icon, [])),
                )
            )
        return rows

    def collect_caltopo_symbol_inventory(self, parsed_data: Any, *, example_limit: int = 3) -> List[InventoryEntry]:
        # parsed_data is cairn.core.parser.ParsedData; keep this loosely typed to avoid import cycles.
        counts: Dict[str, int] = {}
        examples: Dict[str, List[str]] = {}
        for folder in (getattr(parsed_data, "folders", {}) or {}).values():
            for feat in folder.get("waypoints", []) or []:
                sym = _norm_symbol(getattr(feat, "symbol", "") or "") or "(missing)"
                counts[sym] = counts.get(sym, 0) + 1
                title = getattr(feat, "title", "") or ""
                if title and len(examples.get(sym, [])) < example_limit:
                    examples.setdefault(sym, []).append(title)
        return [
            InventoryEntry(label=k, count=v, examples=tuple(examples.get(k, [])))
            for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

    def collect_caltopo_to_onx_mapping_rows(
        self,
        parsed_data: Any,
        *,
        example_limit: int = 3,
        color_limit: int = 3,
    ) -> List[IconReportRow]:
        counts: Dict[Tuple[str, str, str], int] = {}
        examples: Dict[Tuple[str, str, str], List[str]] = {}
        colors: Dict[Tuple[str, str, str], List[str]] = {}

        resolver = self.caltopo_to_onx_resolver()
        for folder in (getattr(parsed_data, "folders", {}) or {}).values():
            for feat in folder.get("waypoints", []) or []:
                title = getattr(feat, "title", "") or ""
                desc = getattr(feat, "description", "") or ""
                sym = _norm_symbol(getattr(feat, "symbol", "") or "") or "(missing)"
                decision = resolver.resolve(title, desc, sym if sym != "(missing)" else "")
                key = (sym, decision.icon, decision.source)
                counts[key] = counts.get(key, 0) + 1
                if title and len(examples.get(key, [])) < example_limit:
                    examples.setdefault(key, []).append(title)
                # Mirror waypoint color policy from writers.py:
                # - If CalTopo marker-color is available, quantize to official OnX waypoint palette
                # - Else use a deterministic per-icon default color
                raw_c = (getattr(feat, "color", "") or "").strip()
                if raw_c:
                    OnX_color = ColorMapper.map_waypoint_color(raw_c)
                else:
                    OnX_color = get_icon_color(decision.icon)
                if OnX_color:
                    cur = colors.setdefault(key, [])
                    if OnX_color not in cur and len(cur) < color_limit:
                        cur.append(OnX_color)

        rows: List[IconReportRow] = []
        for (sym, icon, src), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1], kv[0][2])):
            rows.append(
                IconReportRow(
                    incoming=sym,
                    mapped=icon,
                    mapping_source=src,
                    count=n,
                    examples=tuple(examples.get((sym, icon, src), [])),
                    colors=tuple(colors.get((sym, icon, src), [])),
                )
            )
        return rows

    def collect_caltopo_to_onx_mapping_rows_using_config(
        self,
        parsed_data: Any,
        config: IconMappingConfig,
        *,
        example_limit: int = 3,
        color_limit: int = 3,
    ) -> List[IconReportRow]:
        """
        Produce mapping rows using the *effective* runtime config (including user overrides).

        This mirrors the conversion behavior in `cairn/core/mapper.py` and `cairn/core/writers.py`.
        """
        resolver = IconResolver(
            symbol_map=config.symbol_map,
            keyword_map=config.keyword_map,
            default_icon=config.default_icon,
            generic_symbols=set(GENERIC_SYMBOLS),
        )

        counts: Dict[Tuple[str, str, str], int] = {}
        examples: Dict[Tuple[str, str, str], List[str]] = {}
        colors: Dict[Tuple[str, str, str], List[str]] = {}

        for folder in (getattr(parsed_data, "folders", {}) or {}).values():
            for feat in folder.get("waypoints", []) or []:
                title = getattr(feat, "title", "") or ""
                desc = getattr(feat, "description", "") or ""
                sym = _norm_symbol(getattr(feat, "symbol", "") or "") or "(missing)"
                decision = resolver.resolve(title, desc, sym if sym != "(missing)" else "")
                key = (sym, decision.icon, decision.source)
                counts[key] = counts.get(key, 0) + 1

                if title and len(examples.get(key, [])) < example_limit:
                    examples.setdefault(key, []).append(title)

                raw_c = (getattr(feat, "color", "") or "").strip()
                if raw_c:
                    OnX_color = ColorMapper.map_waypoint_color(raw_c)
                else:
                    OnX_color = get_icon_color(decision.icon, default=config.default_color)
                if OnX_color:
                    cur = colors.setdefault(key, [])
                    if OnX_color not in cur and len(cur) < color_limit:
                        cur.append(OnX_color)

        rows: List[IconReportRow] = []
        for (sym, icon, src), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1], kv[0][2])):
            rows.append(
                IconReportRow(
                    incoming=sym,
                    mapped=icon,
                    mapping_source=src,
                    count=n,
                    examples=tuple(examples.get((sym, icon, src), [])),
                    colors=tuple(colors.get((sym, icon, src), [])),
                )
            )
        return rows

    # ------------------------------------------------------------------
    # Catalog persistence (append-only-ish merge)
    # ------------------------------------------------------------------
    def append_symbol_inventory_to_catalog(self, entries: Iterable[InventoryEntry]) -> None:
        self._merge_catalog_entries("observed_caltopo_symbols", entries)

    def append_onx_icon_inventory_to_catalog(self, entries: Iterable[InventoryEntry]) -> None:
        self._merge_catalog_entries("observed_onx_icons", entries)

    def _merge_catalog_entries(self, root_key: str, entries: Iterable[InventoryEntry], *, example_limit: int = 3) -> None:
        # Load existing
        if self.catalog_path.exists():
            raw = yaml.safe_load(self.catalog_path.read_text(encoding="utf-8")) or {}
        else:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}

        if raw.get("version") is None:
            raw["version"] = 1
        if raw.get("version") != 1:
            raise ValueError(f"Unsupported icon catalog version: {raw.get('version')!r} (expected 1)")

        raw.setdefault("updated_at", _utc_now_iso())
        raw[root_key] = _as_dict(raw.get(root_key), label=root_key)

        root = raw[root_key]
        for e in entries:
            label = str(e.label)
            if not label:
                continue
            prev = root.get(label) or {}
            if not isinstance(prev, dict):
                prev = {}
            prev_count = int(prev.get("count") or 0)
            prev_examples = prev.get("examples") if isinstance(prev.get("examples"), list) else []

            new_count = prev_count + int(e.count)
            merged_examples: List[str] = []
            for ex in (prev_examples or []):
                ex_s = str(ex).strip()
                if ex_s and ex_s not in merged_examples:
                    merged_examples.append(ex_s)
            for ex in (e.examples or ()):
                ex_s = str(ex).strip()
                if ex_s and ex_s not in merged_examples and len(merged_examples) < example_limit:
                    merged_examples.append(ex_s)

            root[label] = {"count": new_count, "examples": merged_examples}

        raw["updated_at"] = _utc_now_iso()
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(yaml.dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_icon_report_markdown(
    *,
    output_path: Path,
    title: str,
    rows: Sequence[IconReportRow],
    inventories: Optional[Sequence[InventoryEntry]] = None,
    notes: Optional[Sequence[str]] = None,
) -> Path:
    """
    Write a human-readable markdown report.
    """
    lines: List[str] = []
    lines.append(f"## {title}")
    lines.append("")
    lines.append(f"- Generated: `{_utc_now_iso()}`")
    lines.append("")

    if notes:
        lines.append("### Notes")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    if inventories:
        lines.append("### Incoming icons/symbols")
        lines.append("")
        lines.append("| label | count | examples |")
        lines.append("|---|---:|---|")
        for e in inventories:
            ex = ", ".join(e.examples) if e.examples else ""
            lines.append(f"| `{e.label}` | {e.count} | {ex} |")
        lines.append("")

    lines.append("### Mapping")
    lines.append("")
    lines.append("| incoming | mapped_to | source | count | colors | examples |")
    lines.append("|---|---|---|---:|---|---|")
    for r in rows:
        ex = ", ".join(r.examples) if r.examples else ""
        cols = ", ".join(r.colors) if r.colors else ""
        lines.append(f"| `{r.incoming}` | `{r.mapped}` | `{r.mapping_source}` | {r.count} | {cols} | {ex} |")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output_path
