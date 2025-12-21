"""
Preview and review system for Cairn.

This module provides dry-run reporting and interactive review functionality
to help users verify icon mappings before creating import files.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional, Sequence
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from cairn.ui.interactive import InteractiveUI, is_interactive_tty, render_change_preview

from cairn.core.parser import ParsedData, ParsedFeature
from cairn.core.mapper import map_icon
from cairn.core.config import (
    IconMappingConfig,
    get_all_onx_icons,
    normalize_onx_icon_name,
    save_user_mapping,
    get_icon_color,
)
from cairn.core.matcher import FuzzyIconMatcher
from cairn.core.color_mapper import ColorMapper
from cairn.utils.utils import natural_sort_key
import re

console = Console()

_ONX_ICON_OVERRIDE_KEY = "cairn_onx_icon_override"


def _ptk_ui() -> InteractiveUI:
    # Keep a single Console instance for consistent output styling.
    return InteractiveUI(console=console)


def _ptk_available(*, force_interactive: Optional[bool] = None) -> bool:
    ui = _ptk_ui()
    return is_interactive_tty(force=force_interactive) and ui.has_prompt_toolkit()


def _rename_preview_samples(
    features: Sequence[ParsedFeature],
    *,
    prefix: str,
    suffix: str,
    trim: bool,
    max_samples: int = 8,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for feat in features[:max_samples]:
        before = feat.title or "Untitled"
        base = before.strip() if trim else before
        after = f"{prefix}{base}{suffix}"
        rows.append((before, after))
    return rows


def _apply_rename_prefix_suffix(
    features: Sequence[ParsedFeature],
    *,
    prefix: str,
    suffix: str,
    trim: bool,
) -> list[tuple[ParsedFeature, str]]:
    out: list[tuple[ParsedFeature, str]] = []
    for feat in features:
        before = feat.title or ""
        base = before.strip() if trim else before
        feat.title = f"{prefix}{base}{suffix}"
        out.append((feat, feat.title))
    return out


def _parse_bulk_selection(raw: str, *, max_index: int) -> list[int]:
    """
    Parse a user selection string into 1-based indices.

    Supports:
      - "1,2,3" (commas, whitespace ok)
      - "1-4" (inclusive ranges)
      - "all" (select everything)

    Returns sorted unique indices (1..max_index). Raises ValueError on invalid input.
    """
    if max_index <= 0:
        raise ValueError("No items available to select.")

    s = (raw or "").strip().lower()
    if not s:
        raise ValueError("Empty selection.")
    if s in ("all", "*"):
        return list(range(1, max_index + 1))

    indices: set[int] = set()
    parts = [p.strip() for p in s.split(",")]
    for part in parts:
        if not part:
            continue

        if "-" in part:
            left, right = part.split("-", 1)
            left = left.strip()
            right = right.strip()
            if not left.isdigit() or not right.isdigit():
                raise ValueError("Invalid range syntax. Use e.g. 1-4.")
            start = int(left)
            end = int(right)
            if start < 1 or end < 1:
                raise ValueError("Selection indices must be >= 1.")
            if end < start:
                raise ValueError("Invalid range: end must be >= start (e.g. 1-4).")
            for i in range(start, end + 1):
                indices.add(i)
        else:
            if not part.isdigit():
                raise ValueError("Invalid selection. Use e.g. 1,2,3 or 1-4 or all.")
            indices.add(int(part))

    if not indices:
        raise ValueError("No valid indices found. Use e.g. 1,2,3 or 1-4 or all.")

    bad = sorted([i for i in indices if i < 1 or i > max_index])
    if bad:
        if len(bad) == 1:
            raise ValueError(f"Index {bad[0]} is out of range (1-{max_index}).")
        raise ValueError(
            f"Indices {', '.join(map(str, bad))} are out of range (1-{max_index})."
        )

    return sorted(indices)


def _match_palette_color_choice(raw: str, palette: tuple) -> Optional[str]:
    """
    Match a user-provided color choice against an OnX palette.

    Supports common inputs like: "BLUE", "red-orange", "red orange", "RedOrange", "1".
    Returns the palette RGBA on match, otherwise None.
    """

    def _norm_name(s: str) -> str:
        s1 = (s or "").strip().upper()
        s1 = re.sub(r"[\s\-_]+", "", s1)
        return s1

    by_name: dict[str, str] = {}
    for p in palette:
        key = _norm_name(getattr(p, "name", ""))
        if key:
            by_name[key] = getattr(p, "rgba", "")

    # Common user-friendly aliases.
    if "ORANGE" in by_name:
        by_name.setdefault("REDORANGE", by_name["ORANGE"])
    # Back-compat: older docs/UI used "LIME" for the OnX green swatch.
    if "GREEN" in by_name:
        by_name.setdefault("LIME", by_name["GREEN"])

    key = _norm_name(raw)
    rgba = by_name.get(key)
    return rgba or None


def _color_square_from_rgb(r: int, g: int, b: int) -> str:
    """
    Render a small color indicator for terminal UIs.

    Historically we used a background-filled block (`on rgb(...)`), but on some terminal
    fonts/themes that reads as a big vertical bar and looks noisy. Prefer a foreground
    dot for all colors.
    """
    return f"[rgb({r},{g},{b})]●[/]"


def _clear_screen() -> None:
    try:
        console.clear()
    except Exception:
        # Best-effort; some non-interactive environments may not support clear.
        pass


def _is_select_all(raw: str) -> bool:
    s = (raw or "").strip().lower()
    return s in ("all", "*")


def _print_track_edit_context(
    *, idx: int, folder_name: str, trk: ParsedFeature
) -> None:
    rgba = _resolved_track_color(trk)
    r, g, b = ColorMapper.parse_color(rgba)
    square = _color_square_from_rgb(r, g, b)
    nm = _onx_color_name_upper(rgba)
    title = trk.title or "Untitled"
    console.print(Panel.fit(f"[bold]Editing route {idx}[/]", border_style="cyan"))
    console.print(f"{square} {title} [dim]({folder_name})[/]")
    console.print(
        f"[dim]Current description:[/]\n{(trk.description or '').strip() or '(none)'}\n"
    )
    console.print(f"[dim]Current color:[/] [bold]{nm}[/]\n")


def _print_waypoint_edit_context(
    *,
    idx: int,
    folder_name: str,
    wp: ParsedFeature,
    config: Optional[IconMappingConfig],
) -> None:
    icon = _resolved_waypoint_icon(wp, config)
    rgba = _resolved_waypoint_color(wp, icon, config)
    r, g, b = ColorMapper.parse_color(rgba)
    square = _color_square_from_rgb(r, g, b)
    title = wp.title or "Untitled"
    console.print(Panel.fit(f"[bold]Editing waypoint {idx}[/]", border_style="cyan"))
    console.print(f"{square} {title} [{icon}] [dim]({folder_name})[/]")
    console.print(
        f"[dim]Current description:[/]\n{(wp.description or '').strip() or '(none)'}\n"
    )


def _onx_color_name_upper(rgba: str) -> str:
    name = (ColorMapper.get_color_name(rgba) or "custom").replace("-", " ").upper()
    return name


def _desc_snippet(desc: str, *, max_len: int = 90) -> str:
    d = (desc or "").strip()
    if not d:
        return "[dim](no description)[/]"
    d1 = d.replace("\r\n", "\n").replace("\r", "\n").split("\n", 1)[0].strip()
    if len(d1) > max_len:
        return d1[: max_len - 3] + "..."
    return d1


def _prompt_multiline_hint(value: str) -> str:
    # Let users enter "\n" to represent line breaks (Prompt is single-line).
    return (value or "").replace("\\n", "\n")


def _palette_choice(
    *,
    title: str,
    palette: tuple,
    current_rgba: str,
) -> Optional[str]:
    """
    Prompt user to select a color from a controlled palette.
    Returns chosen RGBA string, or None to keep current.
    """
    console.print(f"\n[bold]{title}[/]")
    for i, p in enumerate(palette, 1):
        square = _color_square_from_rgb(p.r, p.g, p.b)
        nm = (p.name or "").replace("-", " ").upper()
        suffix = " [dim](current)[/]" if p.rgba == current_rgba else ""
        console.print(f"  [dim]{i}.[/] {square} {nm}{suffix}")

    while True:
        choice = Prompt.ask("Color (enter to keep)", default="").strip()
        if not choice:
            return None

        # Numeric selection
        try:
            idx = int(choice)
            if 1 <= idx <= len(palette):
                return palette[idx - 1].rgba
            console.print("[red]Invalid selection[/] (number out of range)")
            continue
        except ValueError:
            pass

        # Name selection (BLUE, RED, etc.)
        picked = _match_palette_color_choice(choice, palette)
        if picked:
            return picked

        console.print(
            "[red]Invalid selection[/] (enter a number or a color name like BLUE)"
        )


def _rgba_to_hex_nohash(rgba: str) -> str:
    r, g, b = ColorMapper.parse_color(rgba)
    return f"{r:02X}{g:02X}{b:02X}"


def _rgba_to_hex_hash(rgba: str) -> str:
    return "#" + _rgba_to_hex_nohash(rgba)


def _resolved_waypoint_icon(
    feature: ParsedFeature, config: Optional[IconMappingConfig]
) -> str:
    override = None
    if isinstance(getattr(feature, "properties", None), dict):
        override = (feature.properties.get(_ONX_ICON_OVERRIDE_KEY) or "").strip()
    if override:
        return override
    return map_icon(feature.title, feature.description or "", feature.symbol, config)


def _resolved_waypoint_color(
    feature: ParsedFeature, icon: str, config: Optional[IconMappingConfig]
) -> str:
    # Mirror cairn/core/writers.py waypoint policy.
    if getattr(feature, "color", ""):
        return ColorMapper.map_waypoint_color(feature.color)
    return get_icon_color(
        icon,
        default=(
            config.default_color if config else ColorMapper.DEFAULT_WAYPOINT_COLOR
        ),
    )


def _resolved_track_color(feature: ParsedFeature) -> str:
    # Mirror cairn/core/writers.py track policy.
    stroke = (getattr(feature, "stroke", "") or "").strip()
    return (
        ColorMapper.transform_color(stroke)
        if stroke
        else ColorMapper.DEFAULT_TRACK_COLOR
    )


def _prompt_icon_choice(
    *,
    current_icon: str,
) -> Optional[str]:
    """
    Prompt user to choose an OnX icon. Returns icon string, or None to keep current.
    Supports:
      - enter: keep
      - 'clear': clear override (caller decides)
      - exact icon name
      - 'browse': browse_all_icons()
      - fuzzy search with numbered pick
    """
    valid = list(get_all_onx_icons())
    prompt = "Icon (enter to keep, 'clear' to remove override, 'browse' to list all)"

    while True:
        raw = Prompt.ask(prompt, default="").strip()
        if not raw:
            return None
        if raw.lower() == "browse":
            from cairn.core.icon_picker import browse_all_icons

            picked = browse_all_icons()
            if not picked:
                return None
            icon_canon = normalize_onx_icon_name(picked)
            if icon_canon is not None:
                return icon_canon
            console.print("[red]Invalid icon[/] (not in OnX icon set)")
            continue
        if raw.lower() == "clear":
            return "CLEAR"

        icon_canon = normalize_onx_icon_name(raw)
        if icon_canon is not None:
            return icon_canon

        matcher = FuzzyIconMatcher(valid)
        matches = matcher.find_best_matches(raw, top_n=8)
        if not matches:
            console.print("[red]No icon matches found[/]. Try again or type 'browse'.")
            continue

        console.print("\n[bold]Did you mean:[/]")
        for i, (icon, confidence) in enumerate(matches, 1):
            console.print(
                f"  [dim]{i}.[/] {icon} [dim]({int(confidence * 100)}% match)[/]"
            )

        while True:
            picked = Prompt.ask("Select (enter to cancel)", default="").strip()
            if not picked:
                return None
            try:
                idx = int(picked)
            except ValueError:
                console.print("[red]Invalid selection[/]")
                continue
            if idx < 1 or idx > len(matches):
                console.print("[red]Invalid selection[/]")
                continue
            return matches[idx - 1][0]


def interactive_edit_before_export(
    parsed_data: ParsedData,
    config: Optional[IconMappingConfig],
    *,
    edit_tracks: bool = True,
    edit_waypoints: bool = True,
    session: Optional[object] = None,
    session_path: Optional[Path] = None,
    autosave_session: bool = True,
) -> bool:
    """
    Global pre-export preview + edit loop for CalTopo → OnX.

    Output-only: mutates ParsedFeature objects in-memory (titles/descriptions/colors/icon overrides)
    but does not write back to the source GeoJSON.
    """
    # Optional: persist edits to a session file so the workflow is resumable.
    # We intentionally type session loosely to avoid import cycles; call sites pass EditSession.
    try:
        from cairn.core.edit_session import (
            feature_key as _sess_key,
            EditRecord as _EditRecord,
            save_session as _save_session,
        )  # type: ignore
    except Exception:  # pragma: no cover
        _sess_key = None  # type: ignore
        _EditRecord = None  # type: ignore  # noqa: N806
        _save_session = None  # type: ignore

    def _maybe_record(
        *, kind: str, folder_id: str, feat: ParsedFeature, **kwargs
    ) -> None:
        if session is None or _sess_key is None or _EditRecord is None:
            return
        try:
            key = _sess_key(kind=kind, folder_id=folder_id, feature=feat)
            session.record(key=key, record=_EditRecord(**kwargs))  # type: ignore[attr-defined]
            if (
                autosave_session
                and session_path is not None
                and _save_session is not None
            ):
                _save_session(session_path, session)  # type: ignore[arg-type]
        except Exception:
            # Best-effort; never block editing UX.
            return

    # Build global lists
    tracks_index: List[tuple[str, str, ParsedFeature]] = []
    waypoints_index: List[tuple[str, str, ParsedFeature]] = []

    for folder_id, folder in (getattr(parsed_data, "folders", {}) or {}).items():
        folder_name = str(folder.get("name") or "")
        for trk in folder.get("tracks", []) or []:
            tracks_index.append((folder_id, folder_name, trk))
        for wp in folder.get("waypoints", []) or []:
            waypoints_index.append((folder_id, folder_name, wp))

    # Stable, predictable order for review (global).
    tracks_index.sort(
        key=lambda t: (natural_sort_key(t[1]), natural_sort_key(t[2].title))
    )
    waypoints_index.sort(
        key=lambda t: (natural_sort_key(t[1]), natural_sort_key(t[2].title))
    )

    changes_made = False

    def print_tracks() -> None:
        console.print()
        console.print(Panel.fit("[bold]ROUTES / TRACKS[/]", border_style="cyan"))
        console.print(f"There are {len(tracks_index)} routes\n")
        for i, (_folder_id, folder_name, trk) in enumerate(tracks_index, 1):
            rgba = _resolved_track_color(trk)
            r, g, b = ColorMapper.parse_color(rgba)
            square = _color_square_from_rgb(r, g, b)
            nm = _onx_color_name_upper(rgba)
            title = trk.title or "Untitled"
            console.print(
                f"{i}. {square} {title} - [bold]{nm}[/] [dim]({folder_name})[/]"
            )
            console.print(f"   {_desc_snippet(trk.description)}")
            console.print()

    def print_waypoints() -> None:
        console.print()
        console.print(Panel.fit("[bold]WAYPOINTS[/]", border_style="cyan"))
        console.print(f"There are {len(waypoints_index)} waypoints\n")
        for i, (_folder_id, folder_name, wp) in enumerate(waypoints_index, 1):
            icon = _resolved_waypoint_icon(wp, config)
            rgba = _resolved_waypoint_color(wp, icon, config)
            r, g, b = ColorMapper.parse_color(rgba)
            square = _color_square_from_rgb(r, g, b)
            title = wp.title or "Untitled"
            console.print(f"{i}. {square} {title} [{icon}] [dim]({folder_name})[/]")
            console.print(f"   {_desc_snippet(wp.description)}")
            console.print()

    if edit_tracks and tracks_index:
        while True:
            _clear_screen()
            print_tracks()

            if Confirm.ask(
                "Are there any routes you would like to change?", default=False
            ):
                while True:
                    sel = Prompt.ask(
                        "Select route number(s) (e.g. 1,2,3 or 1-4 or all; enter to finish)",
                        default="",
                    ).strip()
                    if not sel:
                        break
                    if _is_select_all(sel) and not Confirm.ask(
                        f"Apply edits to ALL {len(tracks_index)} routes?", default=False
                    ):
                        continue
                    try:
                        idxs = _parse_bulk_selection(sel, max_index=len(tracks_index))
                    except ValueError as e:
                        console.print(f"[red]{e}[/]")
                        continue

                    selected = [tracks_index[i - 1] for i in idxs]
                    if len(selected) == 1:
                        folder_id, folder_name, trk = selected[0]
                        _clear_screen()
                        _print_track_edit_context(
                            idx=idxs[0], folder_name=folder_name, trk=trk
                        )
                    else:
                        console.print(
                            f"\n[bold]Editing {len(selected)} routes[/] [dim]({idxs[0]}..{idxs[-1]})[/]"
                        )

                    new_name = Prompt.ask(
                        "Name (press enter to keep existing value)", default=""
                    ).strip()
                    if new_name:
                        for folder_id, _, trk in selected:
                            trk.title = new_name
                            _maybe_record(
                                kind="track",
                                folder_id=folder_id,
                                feat=trk,
                                title=new_name,
                            )
                        changes_made = True

                    new_desc = Prompt.ask(
                        "Description (press enter to keep existing value)", default=""
                    ).strip()
                    if new_desc:
                        new_desc = _prompt_multiline_hint(new_desc)
                        for folder_id, _, trk in selected:
                            trk.description = new_desc
                            _maybe_record(
                                kind="track",
                                folder_id=folder_id,
                                feat=trk,
                                description=new_desc,
                            )
                        changes_made = True

                    cur_rgba = _resolved_track_color(selected[0][2])
                    chosen = _palette_choice(
                        title="Select route color",
                        palette=ColorMapper.TRACK_PALETTE,
                        current_rgba=cur_rgba,
                    )
                    if chosen:
                        hex_color = _rgba_to_hex_hash(chosen)
                        for folder_id, _, trk in selected:
                            trk.stroke = hex_color
                            _maybe_record(
                                kind="track",
                                folder_id=folder_id,
                                feat=trk,
                                stroke=hex_color,
                            )
                        changes_made = True

                    # Re-render the section after each edit iteration.
                    _clear_screen()
                    print_tracks()

                    if not Confirm.ask(
                        "Would you like to change another route?", default=False
                    ):
                        break

            # Gate: preview then proceed to next section.
            if Confirm.ask("Continue to the next section (Waypoints)?", default=True):
                break

    if edit_waypoints and waypoints_index:
        _clear_screen()
        print_waypoints()
        if Confirm.ask(
            "Are there any waypoints you would like to change?", default=False
        ):
            while True:
                sel = Prompt.ask(
                    "Select waypoint number(s) (e.g. 1,2,3 or 1-4 or all; enter to finish)",
                    default="",
                ).strip()
                if not sel:
                    break
                if _is_select_all(sel) and not Confirm.ask(
                    f"Apply edits to ALL {len(waypoints_index)} waypoints?",
                    default=False,
                ):
                    continue
                try:
                    idxs = _parse_bulk_selection(sel, max_index=len(waypoints_index))
                except ValueError as e:
                    console.print(f"[red]{e}[/]")
                    continue

                selected = [waypoints_index[i - 1] for i in idxs]
                if len(selected) == 1:
                    folder_id, folder_name, wp = selected[0]
                    _clear_screen()
                    _print_waypoint_edit_context(
                        idx=idxs[0], folder_name=folder_name, wp=wp, config=config
                    )
                else:
                    console.print(
                        f"\n[bold]Editing {len(selected)} waypoints[/] [dim]({idxs[0]}..{idxs[-1]})[/]"
                    )

                new_name = Prompt.ask(
                    "Name (press enter to keep existing value)", default=""
                ).strip()
                if new_name:
                    for folder_id, _, wp in selected:
                        wp.title = new_name
                        _maybe_record(
                            kind="waypoint",
                            folder_id=folder_id,
                            feat=wp,
                            title=new_name,
                        )
                    changes_made = True

                new_desc = Prompt.ask(
                    "Description (press enter to keep existing value)", default=""
                ).strip()
                if new_desc:
                    new_desc = _prompt_multiline_hint(new_desc)
                    for folder_id, _, wp in selected:
                        wp.description = new_desc
                        _maybe_record(
                            kind="waypoint",
                            folder_id=folder_id,
                            feat=wp,
                            description=new_desc,
                        )
                    changes_made = True

                cur_icon = _resolved_waypoint_icon(selected[0][2], config)
                icon_choice = _prompt_icon_choice(current_icon=cur_icon)
                if icon_choice == "CLEAR":
                    for folder_id, _, wp in selected:
                        if (
                            isinstance(getattr(wp, "properties", None), dict)
                            and _ONX_ICON_OVERRIDE_KEY in wp.properties
                        ):
                            del wp.properties[_ONX_ICON_OVERRIDE_KEY]
                            _maybe_record(
                                kind="waypoint",
                                folder_id=folder_id,
                                feat=wp,
                                onx_icon_override="",
                            )
                            changes_made = True
                elif icon_choice:
                    for folder_id, _, wp in selected:
                        if isinstance(getattr(wp, "properties", None), dict):
                            wp.properties[_ONX_ICON_OVERRIDE_KEY] = icon_choice
                            _maybe_record(
                                kind="waypoint",
                                folder_id=folder_id,
                                feat=wp,
                                onx_icon_override=icon_choice,
                            )
                            changes_made = True

                final_icon = _resolved_waypoint_icon(selected[0][2], config)
                cur_rgba = _resolved_waypoint_color(selected[0][2], final_icon, config)
                chosen = _palette_choice(
                    title="Select waypoint color",
                    palette=ColorMapper.WAYPOINT_PALETTE,
                    current_rgba=cur_rgba,
                )
                if chosen:
                    hex_nohash = _rgba_to_hex_nohash(chosen)
                    for folder_id, _, wp in selected:
                        wp.color = hex_nohash
                        _maybe_record(
                            kind="waypoint",
                            folder_id=folder_id,
                            feat=wp,
                            color=hex_nohash,
                        )
                    changes_made = True

                # Re-render the section after each edit iteration.
                _clear_screen()
                print_waypoints()

                if not Confirm.ask(
                    "Would you like to change another waypoint?", default=False
                ):
                    break
            _clear_screen()
            print_waypoints()

    return changes_made


def interactive_edit_before_export_per_folder(
    parsed_data: ParsedData,
    config: Optional[IconMappingConfig],
    *,
    sort_enabled: bool = True,
    session: Optional[object] = None,
    session_path: Optional[Path] = None,
    autosave_session: bool = True,
) -> bool:
    """
    Per-folder pre-export preview + edit loop for CalTopo → OnX.

    Output-only: mutates ParsedFeature objects in-memory (titles/descriptions/colors/icon overrides)
    but does not write back to the source GeoJSON.
    """
    folders = list((getattr(parsed_data, "folders", {}) or {}).items())
    folders.sort(
        key=lambda kv: natural_sort_key(str((kv[1] or {}).get("name") or kv[0]))
    )

    changes_made = False

    # Optional session persistence (best-effort).
    try:
        from cairn.core.edit_session import (
            feature_key as _sess_key,
            EditRecord as _EditRecord,
            save_session as _save_session,
        )  # type: ignore
    except Exception:  # pragma: no cover
        _sess_key = None  # type: ignore
        _EditRecord = None  # type: ignore  # noqa: N806
        _save_session = None  # type: ignore

    def _maybe_record(
        *, kind: str, folder_id: str, feat: ParsedFeature, **kwargs
    ) -> None:
        if session is None or _sess_key is None or _EditRecord is None:
            return
        try:
            key = _sess_key(kind=kind, folder_id=folder_id, feature=feat)
            session.record(key=key, record=_EditRecord(**kwargs))  # type: ignore[attr-defined]
            if (
                autosave_session
                and session_path is not None
                and _save_session is not None
            ):
                _save_session(session_path, session)  # type: ignore[arg-type]
        except Exception:
            return

    for folder_idx, (folder_id, folder) in enumerate(folders):
        is_last_folder = folder_idx == (len(folders) - 1)
        folder_name = str((folder or {}).get("name") or folder_id)
        tracks: List[ParsedFeature] = list((folder or {}).get("tracks", []) or [])
        waypoints: List[ParsedFeature] = list((folder or {}).get("waypoints", []) or [])

        if sort_enabled:
            tracks.sort(key=lambda f: natural_sort_key(f.title))
            waypoints.sort(key=lambda f: natural_sort_key(f.title))

        if not tracks and not waypoints:
            continue

        def _print_folder_header() -> None:
            console.print()
            console.print(
                Panel.fit(f"[bold cyan]{folder_name}[/]", border_style="cyan")
            )

        def _print_tracks_list() -> None:
            console.print(f"\n[bold]Routes / Tracks[/] ({len(tracks)})\n")
            for i, trk in enumerate(tracks, 1):
                rgba = _resolved_track_color(trk)
                r, g, b = ColorMapper.parse_color(rgba)
                square = _color_square_from_rgb(r, g, b)
                nm = _onx_color_name_upper(rgba)
                title = trk.title or "Untitled"
                console.print(f"{i}. {square} {title} - [bold]{nm}[/]")
                console.print(f"   {_desc_snippet(trk.description)}")

        def _print_waypoints_list() -> None:
            console.print(f"\n[bold]Waypoints[/] ({len(waypoints)})\n")
            for i, wp in enumerate(waypoints, 1):
                icon = _resolved_waypoint_icon(wp, config)
                rgba = _resolved_waypoint_color(wp, icon, config)
                r, g, b = ColorMapper.parse_color(rgba)
                square = _color_square_from_rgb(r, g, b)
                title = wp.title or "Untitled"
                console.print(f"{i}. {square} {title} [{icon}]")
                console.print(f"   {_desc_snippet(wp.description)}")

        # Tracks editor
        if tracks:
            while True:
                _clear_screen()
                _print_folder_header()
                _print_tracks_list()

                if Confirm.ask(
                    "\nWould you like to edit any routes in this folder?", default=False
                ):
                    # prompt-toolkit enhanced bulk edit (non-full-screen, but richer selection).
                    if _ptk_available():
                        ui = _ptk_ui()
                        try:
                            from prompt_toolkit.shortcuts import (
                                input_dialog,
                                message_dialog,
                                yes_no_dialog,
                            )
                        except Exception:
                            input_dialog = None  # type: ignore[assignment]
                            message_dialog = None  # type: ignore[assignment]
                            yes_no_dialog = None  # type: ignore[assignment]

                        def _route_label(trk: ParsedFeature) -> str:
                            title = (trk.title or "Untitled").strip() or "Untitled"
                            nm = _onx_color_name_upper(_resolved_track_color(trk))
                            return f"{title} [{nm}]"

                        while True:
                            choices = [(str(i), _route_label(trk)) for i, trk in enumerate(tracks)]
                            selected_ids = ui.choose_many(
                                title=f"{folder_name}: select routes",
                                choices=choices,
                                require_filter_over=400,
                            )
                            if not selected_ids:
                                break

                            idxs = sorted({int(s) for s in selected_ids if str(s).isdigit()})
                            selected = [tracks[i] for i in idxs if 0 <= i < len(tracks)]
                            if not selected:
                                break

                            action = ui.choose_one(
                                title="Bulk edit routes",
                                choices=[
                                    ("rename", "Rename: prefix/suffix"),
                                    ("color", "Set route color"),
                                    ("cancel", "Cancel"),
                                ],
                                default="rename",
                            )
                            if action in (None, "cancel"):
                                break

                            if action == "rename":
                                if input_dialog is None or yes_no_dialog is None:
                                    break
                                prefix = input_dialog(
                                    title="Prefix", text="Prefix to add (empty allowed):"
                                ).run()
                                if prefix is None:
                                    continue
                                suffix = input_dialog(
                                    title="Suffix", text="Suffix to add (empty allowed):"
                                ).run()
                                if suffix is None:
                                    continue
                                trim = bool(
                                    yes_no_dialog(
                                        title="Trim whitespace?",
                                        text="Trim leading/trailing whitespace before adding prefix/suffix?",
                                    ).run()
                                )

                                render_change_preview(
                                    console=console,
                                    title="Preview: rename routes",
                                    total_selected=len(selected),
                                    sample_rows=_rename_preview_samples(
                                        selected,
                                        prefix=str(prefix),
                                        suffix=str(suffix),
                                        trim=trim,
                                    ),
                                )
                                if not bool(
                                    yes_no_dialog(
                                        title="Apply changes?",
                                        text="Apply these rename changes?",
                                    ).run()
                                ):
                                    continue

                                applied = _apply_rename_prefix_suffix(
                                    selected,
                                    prefix=str(prefix),
                                    suffix=str(suffix),
                                    trim=trim,
                                )
                                for trk, new_title in applied:
                                    _maybe_record(
                                        kind="track",
                                        folder_id=folder_id,
                                        feat=trk,
                                        title=new_title,
                                    )
                                changes_made = True

                            elif action == "color":
                                if yes_no_dialog is None:
                                    break
                                # Choose a palette RGBA, then apply as track stroke (#RRGGBB).
                                palette_choices = [
                                    (p.rgba, (p.name or "").replace("-", " ").upper())
                                    for p in ColorMapper.TRACK_PALETTE
                                ]
                                chosen_rgba = ui.choose_one(
                                    title="Select route color",
                                    choices=[(rgba, name) for rgba, name in palette_choices],
                                    default=palette_choices[0][0],
                                )
                                if not chosen_rgba:
                                    continue

                                before_after = []
                                for trk in selected[:8]:
                                    before_nm = _onx_color_name_upper(_resolved_track_color(trk))
                                    after_nm = _onx_color_name_upper(str(chosen_rgba))
                                    before_after.append(
                                        ((trk.title or "Untitled"), f"{before_nm} → {after_nm}")
                                    )
                                render_change_preview(
                                    console=console,
                                    title="Preview: route color",
                                    total_selected=len(selected),
                                    sample_rows=before_after,
                                )
                                if not bool(
                                    yes_no_dialog(
                                        title="Apply changes?",
                                        text="Apply this color to the selected routes?",
                                    ).run()
                                ):
                                    continue

                                hex_color = _rgba_to_hex_hash(str(chosen_rgba))
                                for trk in selected:
                                    trk.stroke = hex_color
                                    _maybe_record(
                                        kind="track",
                                        folder_id=folder_id,
                                        feat=trk,
                                        stroke=hex_color,
                                    )
                                changes_made = True

                            if not bool(
                                yes_no_dialog(
                                    title="Continue?",
                                    text="Edit more routes in this folder?",
                                ).run()
                            ):
                                break

                        # Re-render after prompt-toolkit flow.
                        _clear_screen()
                        _print_folder_header()
                        _print_tracks_list()
                    else:
                        while True:
                            sel = Prompt.ask(
                                "Select route number(s) (e.g. 1,2,3 or 1-4 or all; enter to finish)",
                                default="",
                            ).strip()
                            if not sel:
                                break
                            if _is_select_all(sel) and not Confirm.ask(
                                f"Apply edits to ALL {len(tracks)} routes in this folder?",
                                default=False,
                            ):
                                continue
                            try:
                                idxs = _parse_bulk_selection(sel, max_index=len(tracks))
                            except ValueError as e:
                                console.print(f"[red]{e}[/]")
                                continue

                            selected = [tracks[i - 1] for i in idxs]
                            if len(selected) == 1:
                                trk = selected[0]
                                _clear_screen()
                                _print_folder_header()
                                _print_track_edit_context(
                                    idx=idxs[0], folder_name=folder_name, trk=trk
                                )
                            else:
                                console.print(
                                    f"\n[bold]Editing {len(selected)} routes[/] [dim]({idxs[0]}..{idxs[-1]})[/]"
                                )

                            new_name = Prompt.ask(
                                "Name (press enter to keep existing value)", default=""
                            ).strip()
                            if new_name:
                                for trk in selected:
                                    trk.title = new_name
                                    _maybe_record(
                                        kind="track",
                                        folder_id=folder_id,
                                        feat=trk,
                                        title=new_name,
                                    )
                                changes_made = True

                            new_desc = Prompt.ask(
                                "Description (press enter to keep existing value)",
                                default="",
                            ).strip()
                            if new_desc:
                                new_desc = _prompt_multiline_hint(new_desc)
                                for trk in selected:
                                    trk.description = new_desc
                                    _maybe_record(
                                        kind="track",
                                        folder_id=folder_id,
                                        feat=trk,
                                        description=new_desc,
                                    )
                                changes_made = True

                            cur_rgba = _resolved_track_color(selected[0])
                            chosen = _palette_choice(
                                title="Select route color",
                                palette=ColorMapper.TRACK_PALETTE,
                                current_rgba=cur_rgba,
                            )
                            if chosen:
                                hex_color = _rgba_to_hex_hash(chosen)
                                for trk in selected:
                                    trk.stroke = hex_color
                                    _maybe_record(
                                        kind="track",
                                        folder_id=folder_id,
                                        feat=trk,
                                        stroke=hex_color,
                                    )
                                changes_made = True

                            # Re-render after each edit iteration.
                            _clear_screen()
                            _print_folder_header()
                            _print_tracks_list()

                            if not Confirm.ask(
                                "Would you like to change another route in this folder?",
                                default=False,
                            ):
                                break

                # Gate: proceed to next section/folder.
                if waypoints:
                    if Confirm.ask(
                        "Continue to waypoints in this folder?", default=True
                    ):
                        break
                    continue
                next_label = (
                    "Finish editing?" if is_last_folder else "Continue to next folder?"
                )
                if Confirm.ask(next_label, default=True):
                    break
                # else: repeat the tracks section
                continue

        # Waypoints editor
        if waypoints:
            while True:
                _clear_screen()
                _print_folder_header()
                _print_waypoints_list()

                if Confirm.ask(
                    "\nWould you like to edit any waypoints in this folder?",
                    default=False,
                ):
                    if _ptk_available():
                        ui = _ptk_ui()
                        try:
                            from prompt_toolkit.shortcuts import (
                                input_dialog,
                                message_dialog,
                                yes_no_dialog,
                            )
                        except Exception:
                            input_dialog = None  # type: ignore[assignment]
                            message_dialog = None  # type: ignore[assignment]
                            yes_no_dialog = None  # type: ignore[assignment]

                        def _wp_label(wp: ParsedFeature) -> str:
                            title = (wp.title or "Untitled").strip() or "Untitled"
                            icon = _resolved_waypoint_icon(wp, config)
                            return f"{title} [{icon}]"

                        while True:
                            choices = [
                                (str(i), _wp_label(wp)) for i, wp in enumerate(waypoints)
                            ]
                            selected_ids = ui.choose_many(
                                title=f"{folder_name}: select waypoints",
                                choices=choices,
                                require_filter_over=600,
                            )
                            if not selected_ids:
                                break

                            idxs = sorted({int(s) for s in selected_ids if str(s).isdigit()})
                            selected = [
                                waypoints[i] for i in idxs if 0 <= i < len(waypoints)
                            ]
                            if not selected:
                                break

                            action = ui.choose_one(
                                title="Bulk edit waypoints",
                                choices=[
                                    ("rename", "Rename: prefix/suffix"),
                                    ("icon", "Set/clear OnX icon override"),
                                    ("color", "Set waypoint color"),
                                    ("cancel", "Cancel"),
                                ],
                                default="rename",
                            )
                            if action in (None, "cancel"):
                                break

                            if action == "rename":
                                if input_dialog is None or yes_no_dialog is None:
                                    break
                                prefix = input_dialog(
                                    title="Prefix", text="Prefix to add (empty allowed):"
                                ).run()
                                if prefix is None:
                                    continue
                                suffix = input_dialog(
                                    title="Suffix", text="Suffix to add (empty allowed):"
                                ).run()
                                if suffix is None:
                                    continue
                                trim = bool(
                                    yes_no_dialog(
                                        title="Trim whitespace?",
                                        text="Trim leading/trailing whitespace before adding prefix/suffix?",
                                    ).run()
                                )

                                render_change_preview(
                                    console=console,
                                    title="Preview: rename waypoints",
                                    total_selected=len(selected),
                                    sample_rows=_rename_preview_samples(
                                        selected,
                                        prefix=str(prefix),
                                        suffix=str(suffix),
                                        trim=trim,
                                    ),
                                )
                                if not bool(
                                    yes_no_dialog(
                                        title="Apply changes?",
                                        text="Apply these rename changes?",
                                    ).run()
                                ):
                                    continue

                                applied = _apply_rename_prefix_suffix(
                                    selected,
                                    prefix=str(prefix),
                                    suffix=str(suffix),
                                    trim=trim,
                                )
                                for wp, new_title in applied:
                                    _maybe_record(
                                        kind="waypoint",
                                        folder_id=folder_id,
                                        feat=wp,
                                        title=new_title,
                                    )
                                changes_made = True

                            elif action == "icon":
                                if input_dialog is None or yes_no_dialog is None:
                                    break
                                raw = input_dialog(
                                    title="OnX icon override",
                                    text=(
                                        "Enter an OnX icon name (exact) to override.\n"
                                        "Enter 'clear' to remove the override.\n"
                                        "Leave blank to cancel."
                                    ),
                                ).run()
                                raw = (raw or "").strip()
                                if not raw:
                                    continue
                                if raw.lower() == "clear":
                                    sample_rows = []
                                    for wp in selected[:8]:
                                        before = _resolved_waypoint_icon(wp, config)
                                        sample_rows.append((wp.title or "Untitled", f"{before} → (cleared)"))
                                    render_change_preview(
                                        console=console,
                                        title="Preview: clear icon override",
                                        total_selected=len(selected),
                                        sample_rows=sample_rows,
                                    )
                                    if not bool(
                                        yes_no_dialog(
                                            title="Apply changes?",
                                            text="Clear icon overrides for the selected waypoints?",
                                        ).run()
                                    ):
                                        continue
                                    for wp in selected:
                                        if isinstance(getattr(wp, "properties", None), dict):
                                            wp.properties.pop(_ONX_ICON_OVERRIDE_KEY, None)
                                        _maybe_record(
                                            kind="waypoint",
                                            folder_id=folder_id,
                                            feat=wp,
                                            onx_icon_override="",
                                        )
                                    changes_made = True
                                else:
                                    canon = normalize_onx_icon_name(raw)
                                    if canon is None:
                                        if message_dialog is not None:
                                            message_dialog(
                                                title="Invalid icon",
                                                text="That icon name is not a valid OnX icon.",
                                            ).run()
                                        continue
                                    sample_rows = []
                                    for wp in selected[:8]:
                                        before = _resolved_waypoint_icon(wp, config)
                                        sample_rows.append((wp.title or "Untitled", f"{before} → {canon}"))
                                    render_change_preview(
                                        console=console,
                                        title="Preview: set icon override",
                                        total_selected=len(selected),
                                        sample_rows=sample_rows,
                                    )
                                    if not bool(
                                        yes_no_dialog(
                                            title="Apply changes?",
                                            text="Set this icon override for the selected waypoints?",
                                        ).run()
                                    ):
                                        continue
                                    for wp in selected:
                                        if isinstance(getattr(wp, "properties", None), dict):
                                            wp.properties[_ONX_ICON_OVERRIDE_KEY] = canon
                                        _maybe_record(
                                            kind="waypoint",
                                            folder_id=folder_id,
                                            feat=wp,
                                            onx_icon_override=canon,
                                        )
                                    changes_made = True

                            elif action == "color":
                                if yes_no_dialog is None:
                                    break
                                palette_choices = [
                                    (p.rgba, (p.name or "").replace("-", " ").upper())
                                    for p in ColorMapper.WAYPOINT_PALETTE
                                ]
                                chosen_rgba = ui.choose_one(
                                    title="Select waypoint color",
                                    choices=[(rgba, name) for rgba, name in palette_choices],
                                    default=palette_choices[0][0],
                                )
                                if not chosen_rgba:
                                    continue
                                before_after = []
                                for wp in selected[:8]:
                                    icon = _resolved_waypoint_icon(wp, config)
                                    before_nm = _onx_color_name_upper(
                                        _resolved_waypoint_color(wp, icon, config)
                                    )
                                    after_nm = _onx_color_name_upper(str(chosen_rgba))
                                    before_after.append(
                                        ((wp.title or "Untitled"), f"{before_nm} → {after_nm}")
                                    )
                                render_change_preview(
                                    console=console,
                                    title="Preview: waypoint color",
                                    total_selected=len(selected),
                                    sample_rows=before_after,
                                )
                                if not bool(
                                    yes_no_dialog(
                                        title="Apply changes?",
                                        text="Apply this color to the selected waypoints?",
                                    ).run()
                                ):
                                    continue

                                hex_nohash = _rgba_to_hex_nohash(str(chosen_rgba))
                                for wp in selected:
                                    wp.color = hex_nohash
                                    _maybe_record(
                                        kind="waypoint",
                                        folder_id=folder_id,
                                        feat=wp,
                                        color=hex_nohash,
                                    )
                                changes_made = True

                            if not bool(
                                yes_no_dialog(
                                    title="Continue?",
                                    text="Edit more waypoints in this folder?",
                                ).run()
                            ):
                                break

                        _clear_screen()
                        _print_folder_header()
                        _print_waypoints_list()
                    else:
                        while True:
                            sel = Prompt.ask(
                                "Select waypoint number(s) (e.g. 1,2,3 or 1-4 or all; enter to finish)",
                                default="",
                            ).strip()
                            if not sel:
                                break
                            if _is_select_all(sel) and not Confirm.ask(
                                f"Apply edits to ALL {len(waypoints)} waypoints in this folder?",
                                default=False,
                            ):
                                continue
                            try:
                                idxs = _parse_bulk_selection(sel, max_index=len(waypoints))
                            except ValueError as e:
                                console.print(f"[red]{e}[/]")
                                continue

                            selected = [waypoints[i - 1] for i in idxs]
                            if len(selected) == 1:
                                wp = selected[0]
                                _clear_screen()
                                _print_folder_header()
                                _print_waypoint_edit_context(
                                    idx=idxs[0],
                                    folder_name=folder_name,
                                    wp=wp,
                                    config=config,
                                )
                            else:
                                console.print(
                                    f"\n[bold]Editing {len(selected)} waypoints[/] [dim]({idxs[0]}..{idxs[-1]})[/]"
                                )

                            new_name = Prompt.ask(
                                "Name (press enter to keep existing value)", default=""
                            ).strip()
                            if new_name:
                                for wp in selected:
                                    wp.title = new_name
                                    _maybe_record(
                                        kind="waypoint",
                                        folder_id=folder_id,
                                        feat=wp,
                                        title=new_name,
                                    )
                                changes_made = True

                            new_desc = Prompt.ask(
                                "Description (press enter to keep existing value)",
                                default="",
                            ).strip()
                            if new_desc:
                                new_desc = _prompt_multiline_hint(new_desc)
                                for wp in selected:
                                    wp.description = new_desc
                                    _maybe_record(
                                        kind="waypoint",
                                        folder_id=folder_id,
                                        feat=wp,
                                        description=new_desc,
                                    )
                                changes_made = True

                            cur_icon = _resolved_waypoint_icon(selected[0], config)
                            icon_choice = _prompt_icon_choice(current_icon=cur_icon)
                            if icon_choice == "CLEAR":
                                for wp in selected:
                                    if (
                                        isinstance(getattr(wp, "properties", None), dict)
                                        and _ONX_ICON_OVERRIDE_KEY in wp.properties
                                    ):
                                        del wp.properties[_ONX_ICON_OVERRIDE_KEY]
                                        _maybe_record(
                                            kind="waypoint",
                                            folder_id=folder_id,
                                            feat=wp,
                                            onx_icon_override="",
                                        )
                                        changes_made = True
                            elif icon_choice:
                                for wp in selected:
                                    if isinstance(getattr(wp, "properties", None), dict):
                                        wp.properties[_ONX_ICON_OVERRIDE_KEY] = icon_choice
                                        _maybe_record(
                                            kind="waypoint",
                                            folder_id=folder_id,
                                            feat=wp,
                                            onx_icon_override=icon_choice,
                                        )
                                        changes_made = True

                            final_icon = _resolved_waypoint_icon(selected[0], config)
                            cur_rgba = _resolved_waypoint_color(
                                selected[0], final_icon, config
                            )
                            chosen = _palette_choice(
                                title="Select waypoint color",
                                palette=ColorMapper.WAYPOINT_PALETTE,
                                current_rgba=cur_rgba,
                            )
                            if chosen:
                                hex_nohash = _rgba_to_hex_nohash(chosen)
                                for wp in selected:
                                    wp.color = hex_nohash
                                    _maybe_record(
                                        kind="waypoint",
                                        folder_id=folder_id,
                                        feat=wp,
                                        color=hex_nohash,
                                    )
                                changes_made = True

                            # Re-render after each edit iteration.
                            _clear_screen()
                            _print_folder_header()
                            _print_waypoints_list()

                            if not Confirm.ask(
                                "Would you like to change another waypoint in this folder?",
                                default=False,
                            ):
                                break

                next_label = (
                    "Finish editing?" if is_last_folder else "Continue to next folder?"
                )
                if Confirm.ask(next_label, default=True):
                    break
                # else: repeat waypoints section
                continue

    return changes_made


def generate_dry_run_report(
    parsed_data: ParsedData, config: IconMappingConfig
) -> Dict[str, Any]:
    """
    Generate dry-run report without creating files.

    Args:
        parsed_data: Parsed GeoJSON data
        config: Icon mapping configuration

    Returns:
        Dictionary with report data
    """
    icon_counts = defaultdict(int)
    total_waypoints = 0
    total_tracks = 0
    total_shapes = 0
    files_to_create = []

    for folder_id, folder_data in parsed_data.folders.items():
        folder_name = folder_data["name"]

        # Count waypoints by icon
        for waypoint in folder_data["waypoints"]:
            icon = map_icon(
                waypoint.title, waypoint.description or "", waypoint.symbol, config
            )
            icon_counts[icon] += 1
            total_waypoints += 1

        # Count tracks and shapes
        total_tracks += len(folder_data["tracks"])
        total_shapes += len(folder_data["shapes"])

        # Determine what files would be created
        if folder_data["waypoints"]:
            files_to_create.append(
                {
                    "name": f"{folder_name}_Waypoints.gpx",
                    "type": "GPX (Waypoints)",
                    "count": len(folder_data["waypoints"]),
                }
            )

        if folder_data["tracks"]:
            files_to_create.append(
                {
                    "name": f"{folder_name}_Tracks.gpx",
                    "type": "GPX (Tracks)",
                    "count": len(folder_data["tracks"]),
                }
            )

        if folder_data["shapes"]:
            files_to_create.append(
                {
                    "name": f"{folder_name}_Shapes.kml",
                    "type": "KML (Shapes)",
                    "count": len(folder_data["shapes"]),
                }
            )

    return {
        "icon_counts": dict(
            sorted(icon_counts.items(), key=lambda x: x[1], reverse=True)
        ),
        "unmapped": config.get_unmapped_report(),
        "total_waypoints": total_waypoints,
        "total_tracks": total_tracks,
        "total_shapes": total_shapes,
        "files_to_create": files_to_create,
    }


def display_dry_run_report(report: Dict[str, Any]) -> None:
    """
    Display dry-run report to console.

    Args:
        report: Report data from generate_dry_run_report
    """
    console.print("\n")
    console.print(
        Panel.fit(
            "[bold yellow]DRY RUN REPORT[/]\n[dim]No files will be created[/]",
            border_style="yellow",
        )
    )

    # Summary statistics
    console.print("\n[bold]Summary:[/]")
    console.print(f"  Waypoints: [cyan]{report['total_waypoints']}[/]")
    console.print(f"  Tracks:    [cyan]{report['total_tracks']}[/]")
    console.print(f"  Shapes:    [cyan]{report['total_shapes']}[/]")

    # Icon distribution
    if report["icon_counts"]:
        console.print("\n[bold]Waypoint Icon Distribution:[/]")

        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Icon", style="white")
        table.add_column("Count", justify="right", style="cyan")
        table.add_column("Percentage", justify="right", style="dim")

        total = report["total_waypoints"]
        for icon, count in report["icon_counts"].items():
            percentage = (count / total * 100) if total > 0 else 0
            table.add_row(icon, str(count), f"{percentage:.1f}%")

        console.print(table)

    # Unmapped symbols
    if report["unmapped"]:
        console.print(
            f"\n[yellow]⚠️  Unmapped Symbols:[/] [bold]{len(report['unmapped'])}[/]"
        )

        table = Table(show_header=True, header_style="bold yellow", box=None)
        table.add_column("Symbol", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Example", style="dim")

        for symbol, info in report["unmapped"].items():
            example = info["examples"][0] if info["examples"] else "N/A"
            if len(example) > 40:
                example = example[:37] + "..."
            table.add_row(symbol, str(info["count"]), example)

        console.print(table)

    # Files that would be created
    if report["files_to_create"]:
        console.print(
            f"\n[bold]Would create {len(report['files_to_create'])} file(s):[/]"
        )

        table = Table(show_header=True, header_style="bold green", box=None)
        table.add_column("Filename", style="yellow")
        table.add_column("Type", style="white")
        table.add_column("Items", justify="right", style="cyan")

        for file_info in report["files_to_create"]:
            table.add_row(file_info["name"], file_info["type"], str(file_info["count"]))

        console.print(table)

    console.print("\n[dim]Run without --dry-run to create files.[/]\n")


def interactive_review(
    parsed_data: ParsedData, config: IconMappingConfig
) -> tuple[ParsedData, bool]:
    """
    Interactive review of icon mappings before export.

    Args:
        parsed_data: Parsed GeoJSON data
        config: Icon mapping configuration

    Returns:
        Tuple of (possibly modified ParsedData, whether changes were made)
    """
    console.print("\n")
    console.print(
        Panel.fit(
            "[bold cyan]INTERACTIVE REVIEW[/]\n[dim]Review and adjust icon mappings[/]",
            border_style="cyan",
        )
    )

    # Group waypoints by icon across all folders
    icon_groups = defaultdict(list)

    for folder_id, folder_data in parsed_data.folders.items():
        for waypoint in folder_data["waypoints"]:
            icon = map_icon(
                waypoint.title, waypoint.description or "", waypoint.symbol, config
            )
            icon_groups[icon].append({"feature": waypoint, "folder_id": folder_id})

    changes_made = False

    # Review each icon group
    for icon, waypoints in sorted(
        icon_groups.items(), key=lambda x: len(x[1]), reverse=True
    ):
        console.print(f"\n[bold cyan]{icon}[/] ([yellow]{len(waypoints)}[/] waypoints)")

        # Show sample waypoints
        sample_count = min(5, len(waypoints))
        for i, wp_info in enumerate(waypoints[:sample_count]):
            console.print(f"  • {wp_info['feature'].title}")

        if len(waypoints) > sample_count:
            console.print(f"  [dim]... and {len(waypoints) - sample_count} more[/]")

        # Prompt for action
        console.print("\n  [K]eep  [C]hange icon  [S]kip to next  [Q]uit review")

        try:
            action = Prompt.ask(
                "Action", choices=["k", "c", "s", "q"], default="k", show_choices=False
            ).lower()

            if action == "q":
                break
            elif action == "c":
                # Prompt for new icon
                new_icon = prompt_for_new_icon(icon)
                if new_icon and new_icon != icon:
                    # Update config for this mapping
                    # Find the most common symbol for this icon
                    symbols = [
                        wp["feature"].symbol for wp in waypoints if wp["feature"].symbol
                    ]
                    if symbols:
                        most_common = max(set(symbols), key=symbols.count)
                        save_user_mapping(most_common, new_icon)
                        console.print(
                            f"[green]✓[/] Updated mapping: {most_common} → {new_icon}"
                        )
                        changes_made = True
            elif action == "s":
                continue

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Review cancelled[/]")
            break

    if changes_made:
        console.print("\n[green]✓[/] Changes saved to configuration")
        console.print("[dim]Reloading data with new mappings...[/]")

    return parsed_data, changes_made


def prompt_for_new_icon(current_icon: str) -> Optional[str]:
    """
    Prompt user to select a new icon.

    Args:
        current_icon: Current icon name

    Returns:
        New icon name or None if cancelled
    """
    console.print(f"\n[bold]Change from '[cyan]{current_icon}[/]' to:[/]")
    console.print(
        "[dim]Enter icon name, or 'browse' to see all options, or Enter to cancel[/]"
    )

    valid_icons = get_all_onx_icons()
    matcher = FuzzyIconMatcher(valid_icons)

    while True:
        try:
            choice = Prompt.ask("New icon", default="").strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if not choice:
            return None

        if choice.lower() == "browse":
            from cairn.core.icon_picker import browse_all_icons

            picked = browse_all_icons()
            if not picked:
                return None
            icon_canon = normalize_onx_icon_name(picked)
            if icon_canon is not None:
                return icon_canon
            console.print(f"[red]Invalid icon name:[/] {picked}")
            continue

        icon_canon = normalize_onx_icon_name(choice)
        if icon_canon is not None:
            return icon_canon

        matches = matcher.find_best_matches(choice, top_n=3)
        if matches and matches[0][1] > 0.8:
            console.print("\n[yellow]Did you mean:[/]")
            for i, (icon, confidence) in enumerate(matches, 1):
                console.print(f"  {i}. {icon} ({int(confidence * 100)}% match)")

            while True:
                selection = Prompt.ask(
                    "Select (enter to cancel)",
                    choices=[str(i) for i in range(1, len(matches) + 1)] + [""],
                    default="",
                )
                if not selection:
                    break
                try:
                    return matches[int(selection) - 1][0]
                except Exception:
                    console.print("[red]Invalid selection[/]")
                    continue
        else:
            console.print(f"[red]Invalid icon name:[/] {choice}")
        # Reprompt


def show_mapping_preview(parsed_data: ParsedData, config: IconMappingConfig) -> None:
    """
    Show a preview of how waypoints will be mapped.

    Args:
        parsed_data: Parsed GeoJSON data
        config: Icon mapping configuration
    """
    console.print("\n[bold]Icon Mapping Preview:[/]\n")

    # Sample waypoints from each folder
    for folder_id, folder_data in parsed_data.folders.items():
        if not folder_data["waypoints"]:
            continue

        folder_name = folder_data["name"]
        console.print(f"[cyan]{folder_name}[/]")

        # Show up to 10 waypoints
        for waypoint in folder_data["waypoints"][:10]:
            icon = map_icon(
                waypoint.title, waypoint.description or "", waypoint.symbol, config
            )
            console.print(f"  {waypoint.title[:50]} → [yellow]{icon}[/]")

        if len(folder_data["waypoints"]) > 10:
            console.print(
                f"  [dim]... and {len(folder_data['waypoints']) - 10} more[/]"
            )

        console.print()


def get_color_square(feature: ParsedFeature) -> str:
    """
    Get a colored square indicator for a track based on its stroke color.

    Uses Rich markup to display a colored square character.

    Args:
        feature: The track feature with stroke color

    Returns:
        Rich-formatted string with a colored indicator glyph, e.g., "[rgb(255,0,0)]●[/]"
    """
    # Get the stroke color (hex format like "#FF0000")
    stroke = getattr(feature, "stroke", "") or ""

    if not stroke:
        # Default to blue if no color
        return _color_square_from_rgb(8, 122, 255)

    # Parse the color to RGB
    r, g, b = ColorMapper.parse_color(stroke)

    return _color_square_from_rgb(r, g, b)


def get_waypoint_icon_preview(
    feature: ParsedFeature, config: Optional[IconMappingConfig] = None
) -> str:
    """
    Get an icon preview for a waypoint.

    Args:
        feature: The waypoint feature
        config: Optional config for keyword/symbol mappings

    Returns:
        Icon label like "[Location]"
    """
    from cairn.core.mapper import map_icon

    mapped_icon = map_icon(
        feature.title, feature.description or "", feature.symbol, config
    )
    return f"[{mapped_icon}]"


def preview_sorted_order(
    features: List[ParsedFeature],
    feature_type: str,
    folder_name: str = "",
    skip_confirmation: bool = False,
    config: Optional[IconMappingConfig] = None,
) -> bool:
    """
    Display sorted order preview and get user confirmation.

    Shows the order items will appear in OnX after import (since OnX
    doesn't allow reordering). Asks user to confirm before proceeding.

    For tracks: Shows colored squares matching the line color
    For waypoints: Shows color + mapped icon name in brackets (e.g. "Start [● Location]")

    Args:
        features: List of features (already sorted)
        feature_type: "waypoints", "tracks", or "shapes"
        folder_name: Name of the folder being processed
        skip_confirmation: If True, show preview but don't ask for confirmation
        config: Optional icon mapping config for waypoint icon lookups

    Returns:
        True if user confirms (or skip_confirmation is True), False to abort
    """
    if not features:
        return True

    # Build the header
    type_label = feature_type.capitalize()
    count = len(features)

    if folder_name:
        header = f"[bold cyan]{folder_name}[/] - Sorted {type_label} ({count})"
    else:
        header = f"[bold]Sorted {type_label} Order ({count} items)[/]"

    console.print(f"\n{header}")
    console.print("─" * 60)

    # Show all items (or truncate for very long lists)
    max_display = 20
    for i, feature in enumerate(features[:max_display], 1):
        # Truncate long titles
        title = feature.title
        if len(title) > 50:
            title = title[:47] + "..."

        # Get visual indicator based on feature type
        if feature_type == "tracks":
            indicator = get_color_square(feature)
            console.print(f"  [dim]{i:3}.[/] {indicator} {title}")
        elif feature_type == "waypoints":
            icon = _resolved_waypoint_icon(feature, config)
            rgba = _resolved_waypoint_color(feature, icon, config)
            r, g, b = ColorMapper.parse_color(rgba)
            square = _color_square_from_rgb(r, g, b)
            console.print(f"  [dim]{i:3}.[/] {square} {title} [{icon}]")
        else:
            # Shapes or other types - no special indicator
            console.print(f"  [dim]{i:3}.[/] {title}")

    if count > max_display:
        remaining = count - max_display
        console.print(f"  [dim]... and {remaining} more items[/]")

    console.print("─" * 60)

    # If skip_confirmation is True, just return True without prompting
    if skip_confirmation:
        console.print("[dim]Order confirmed (--yes flag)[/]")
        return True

    # Ask for confirmation
    console.print("\n[yellow]OnX does not allow reordering after import.[/]")

    try:
        proceed = Confirm.ask("Proceed with this order?", default=True)
        return proceed
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled[/]")
        return False
