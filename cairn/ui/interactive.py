from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple, TypeVar

from rich.console import Console
from rich.table import Table

from cairn.ui.state import (
    UIState,
    add_recent,
    default_state_path,
    load_state,
    save_state,
)


T = TypeVar("T")


def is_interactive_tty(*, force: Optional[bool] = None) -> bool:
    """
    Best-effort interactive check.

    Note: command modules may already provide their own `--interactive/--no-interactive`
    flag. Pass it through `force` to override TTY detection.
    """
    if force is not None:
        return bool(force)
    try:
        import sys

        return sys.stdin is not None and getattr(sys.stdin, "isatty", lambda: False)()
    except Exception:
        return False


@dataclass(frozen=True)
class UIChoice(Sequence[str]):
    """
    A simple label/value pair for list selection UIs.
    """

    value: str
    label: str

    # Provide Sequence-ish behavior so prompt-toolkit doesn't choke on custom objects in edge cases.
    def __len__(self) -> int:  # pragma: no cover
        return 2

    def __getitem__(self, idx: int) -> str:  # pragma: no cover
        return (self.value, self.label)[idx]


class InteractiveUI:
    """
    Thin wrapper around prompt-toolkit dialogs, with graceful fallback.

    This is intentionally not a full-screen TUI; it provides better pickers and
    checkbox multi-select while keeping non-interactive behavior unchanged.
    """

    def __init__(
        self,
        *,
        console: Optional[Console] = None,
        state_path: Optional[Path] = None,
    ) -> None:
        self.console = console or Console()
        self.state_path = state_path or default_state_path()

    # -----------------------------
    # State helpers
    # -----------------------------
    def load_state(self) -> UIState:
        return load_state(self.state_path)

    def save_state(self, state: UIState) -> None:
        save_state(state, self.state_path)

    # -----------------------------
    # prompt-toolkit availability
    # -----------------------------
    def has_prompt_toolkit(self) -> bool:
        try:
            import prompt_toolkit  # noqa: F401

            return True
        except Exception:
            return False

    # -----------------------------
    # Core UI primitives
    # -----------------------------
    def confirm(self, title: str, *, default: bool = True) -> bool:
        if self.has_prompt_toolkit():
            try:
                from prompt_toolkit.shortcuts import yes_no_dialog

                return bool(yes_no_dialog(title=title, text="").run())
            except Exception:
                pass
        # Fallback: Rich/Typer-like (but without importing typer here).
        return default

    def choose_one(
        self,
        *,
        title: str,
        choices: Sequence[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Choose one from (value, label) tuples. Returns value or None on cancel.
        """
        if not choices:
            return None
        if self.has_prompt_toolkit():
            try:
                from prompt_toolkit.shortcuts import radiolist_dialog

                # prompt-toolkit wants list[tuple[value, label]]
                out = radiolist_dialog(
                    title=title,
                    text="",
                    values=list(choices),
                    default=default,
                ).run()
                return str(out) if out is not None else None
            except Exception:
                pass

        # Fallback (non-interactive / no PTK): just pick default or first.
        if default is not None:
            return default
        return choices[0][0]

    def choose_many(
        self,
        *,
        title: str,
        choices: Sequence[Tuple[str, str]],
        default_selected: Optional[Sequence[str]] = None,
        require_filter_over: int = 500,
        page_hint: Optional[int] = None,
    ) -> List[str]:
        """
        Choose many from (value, label) tuples. Returns list of values.

        For very large choice sets, we ask the user for a filter query first to
        avoid rendering huge checkbox lists. No hard caps; this is a warning/degraded mode.
        """
        if not choices:
            return []

        defaults = set(default_selected or [])

        if not self.has_prompt_toolkit():
            # Fallback: select all defaults, or nothing.
            return [v for v, _ in choices if v in defaults]

        from prompt_toolkit.shortcuts import checkboxlist_dialog, input_dialog, message_dialog

        items = list(choices)

        if len(items) >= require_filter_over:
            try:
                message_dialog(
                    title="Large selection",
                    text=(
                        f"You are selecting from {len(items)} items.\n\n"
                        "To keep the UI responsive, you'll filter the list first.\n"
                        "Tip: narrow by a unique word or number in the name."
                    ),
                ).run()
            except Exception:
                pass

            while True:
                q = input_dialog(
                    title="Filter items",
                    text="Enter a filter (leave blank to cancel):",
                ).run()
                q = (q or "").strip()
                if not q:
                    return []
                ql = q.lower()
                filtered = [(v, lbl) for (v, lbl) in items if ql in (lbl or "").lower()]
                if not filtered:
                    message_dialog(
                        title="No matches",
                        text=f"No items matched '{q}'. Try a different filter.",
                    ).run()
                    continue
                items = filtered
                break

        # Note: checkboxlist_dialog isn't searchable; above filter-first covers large lists.
        try:
            selected = checkboxlist_dialog(
                title=title,
                text=(
                    f"Select items ({len(items)} shown)"
                    + (f"\n(page hint: {page_hint})" if page_hint else "")
                ),
                values=items,
            ).run()
            if not selected:
                return []
            return [str(x) for x in selected]
        except Exception:
            return []

    # -----------------------------
    # File/directory picking
    # -----------------------------
    def pick_directory(
        self,
        *,
        title: str,
        state: Optional[UIState] = None,
        must_exist: bool = True,
    ) -> Optional[Path]:
        """
        Pick a directory, encouraging favorites/default root. Stores the result in recents.
        """
        st = state or self.load_state()

        entries: List[Tuple[str, str]] = []
        if st.default_root:
            entries.append((st.default_root, f"Default root: {st.default_root}"))
        for p in st.favorites:
            entries.append((p, f"Favorite: {p}"))
        for p in st.recent_paths:
            entries.append((p, f"Recent: {p}"))
        entries.append(("__enter__", "Enter a path…"))

        pick = self.choose_one(title=title, choices=entries, default=entries[0][0])
        if pick is None:
            return None

        if pick == "__enter__":
            if not self.has_prompt_toolkit():
                return None
            try:
                from prompt_toolkit.completion import PathCompleter
                from prompt_toolkit.shortcuts import prompt

                raw = prompt(
                    "Directory: ",
                    completer=PathCompleter(expanduser=True, only_directories=True),
                )
                pick = (raw or "").strip()
            except Exception:
                return None

        p = Path(pick).expanduser()
        try:
            p = p.resolve()
        except Exception:
            pass

        if must_exist and (not p.exists() or not p.is_dir()):
            self.console.print(f"[red]Directory not found:[/] {p}")
            return None

        st = add_recent(st, p)
        self.save_state(st)
        return p

    def pick_from_paths(
        self,
        *,
        title: str,
        paths: Sequence[Path],
        default_index: int = 0,
        labeler: Optional[Callable[[Path], str]] = None,
        record_recent: bool = True,
    ) -> Optional[Path]:
        """
        Pick a file from a known list of paths (e.g., discovered in a directory).
        """
        if not paths:
            return None
        lab = labeler or (lambda p: p.name)
        values: List[Tuple[str, str]] = []
        for p in paths:
            values.append((str(p), lab(p)))
        default_index = max(0, min(default_index, len(values) - 1))
        chosen = self.choose_one(title=title, choices=values, default=values[default_index][0])
        if chosen is None:
            return None
        pth = Path(chosen)
        if record_recent:
            st = self.load_state()
            st = add_recent(st, pth)
            self.save_state(st)
        return pth


def render_change_preview(
    *,
    console: Console,
    title: str,
    total_selected: int,
    sample_rows: Sequence[Tuple[str, str]],
    note: Optional[str] = None,
) -> None:
    """
    Render a lightweight preview of bulk changes (before -> after).

    This is intentionally minimal and easy to extend later (e.g., add per-field diffs,
    counts by folder, etc.).
    """
    console.print()
    console.print(f"[bold]{title}[/] [dim](selected: {total_selected})[/]")
    if note:
        console.print(f"[dim]{note}[/]")

    if not sample_rows:
        console.print("[dim](no sample rows)[/]")
        return

    tbl = Table(show_header=True, header_style="bold cyan", box=None)
    tbl.add_column("Before", style="white")
    tbl.add_column("After", style="green")
    for before, after in sample_rows:
        tbl.add_row(before, after)
    console.print(tbl)
