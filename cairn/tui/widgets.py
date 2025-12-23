"""Custom Textual widgets for the TUI module.

This module contains reusable UI widgets extracted from app.py to eliminate
circular import dependencies.
"""

from typing import Iterable
from pathlib import Path

from textual.widgets import DirectoryTree, Static

from cairn.tui.models import STEP_LABELS, _VISIBLE_INPUT_EXTS


class FilteredFileTree(DirectoryTree):
    """DirectoryTree that filters to show only allowed file extensions.

    This is used for the A/B test of tree-based file browser vs. table-based.
    Filters out hidden directories and shows only files with allowed extensions.
    """

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter paths to show only directories and allowed file extensions."""
        allowed_extensions = _VISIBLE_INPUT_EXTS
        filtered = []
        for path in paths:
            # Always show directories
            if path.is_dir():
                # Skip hidden directories (starting with .)
                if not path.name.startswith("."):
                    filtered.append(path)
            # Show files with allowed extensions (but hide dotfiles - hide always wins)
            elif path.is_file() and not path.name.startswith(".") and path.suffix.lower() in allowed_extensions:
                filtered.append(path)
        return filtered


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree that shows only directories (no files).

    Used for the A/B test of tree-based save directory browser.
    Filters out hidden directories.
    """

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter paths to show only non-hidden directories."""
        filtered = []
        for path in paths:
            if path.is_dir() and not path.name.startswith("."):
                filtered.append(path)
        return filtered


class Stepper(Static):
    """Left-side stepper with current step highlighted."""

    def __init__(self, *, steps: list[str], **kwargs) -> None:
        # Accept standard Textual widget kwargs (id, classes, name, etc.).
        super().__init__(**kwargs)
        self.steps = steps
        self.current: str = steps[0]
        self.done: set[str] = set()

    def set_state(self, *, current: str, done: set[str]) -> None:
        self.current = current
        self.done = set(done)
        self.refresh()

    def render(self) -> str:
        lines: list[str] = []
        for s in self.steps:
            label = STEP_LABELS.get(s, s)
            if s == self.current:
                lines.append(f" ▸ {label}")
            elif s in self.done:
                lines.append(f" ✓ {label}")
            else:
                lines.append(f"   {label}")
        return "\n".join(lines)


class StepAwareFooter(Static):
    """Dynamic footer showing step-specific keyboard shortcuts."""

    # Define shortcuts for each step
    STEP_SHORTCUTS = {
        "Select_file": [
            ("↑↓", "Navigate"),
            ("Enter", "Select"),
            ("Tab", "Next field"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "List_data": [
            ("m", "Map unmapped"),
            ("Enter", "Continue"),
            ("Tab", "Next field"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Folder": [
            ("↑↓", "Navigate"),
            ("Space", "Toggle (multi-folder)"),
            ("Enter", "Select"),
            ("Tab", "Next field"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Routes": [
            ("↑↓", "Navigate"),
            ("Space", "Toggle"),
            ("Ctrl+A", "Toggle all"),
            ("/", "Search"),
            ("Tab", "Next field"),
            ("a", "Edit"),
            ("x", "Clear"),
            ("Enter", "Continue"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Waypoints": [
            ("↑↓", "Navigate"),
            ("Space", "Toggle"),
            ("Ctrl+A", "Toggle all"),
            ("/", "Search"),
            ("Tab", "Next field"),
            ("a", "Edit"),
            ("x", "Clear"),
            ("Enter", "Continue"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
        "Preview": [
            ("↑↓", "Navigate"),
            ("Enter", "Export"),
            ("Ctrl+N", "New folder"),
            ("r", "Apply names"),
            ("Tab", "Next field"),
            ("Esc", "Back"),
            ("?", "Help"),
            ("q", "Quit"),
        ],
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_step: str = "Select_file"

    def set_step(self, step: str) -> None:
        self.current_step = step
        self.refresh()

    def render(self) -> str:
        shortcuts = self.STEP_SHORTCUTS.get(self.current_step, [])
        parts = [f"[bold]{key}[/] {desc}" for key, desc in shortcuts]
        return "  ".join(parts)


__all__ = [
    "FilteredFileTree",
    "FilteredDirectoryTree",
    "Stepper",
    "StepAwareFooter",
]





