"""Pure helper functions for TUI rendering.

This module contains rendering logic that doesn't require Textual widget
access, extracted from app.py to keep the main App class focused on
widget orchestration.

All functions here are pure (or nearly pure) and can be unit-tested
without the full Textual machinery.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from cairn.utils.utils import sanitize_filename

if TYPE_CHECKING:
    from typing import Sequence, Tuple


def sidebar_instructions(step: str) -> str:
    """
    Concise, process-oriented guidance shown in the left column per step.

    Args:
        step: Current workflow step name.

    Returns:
        Instructional text for the sidebar.
    """
    step = str(step or "")
    if step == "Select_file":
        return (
            "Choose the CalTopo export you want to migrate to onX.\n"
            "GeoJSON preserves the most detail, but GPX/KML are also supported."
        )
    if step == "List_data":
        return (
            "Review everything found in your export: folders, routes, waypoints, tracks, "
            "shapes, and unmapped symbols.\n\n\n"
            "onX does not support folders, so this is a good time to bake folder structure "
            "into names/descriptions so you can find items via onX search."
        )
    if step == "Folder":
        return (
            "Pick what you want to edit next.\n"
            "If multiple folders exist, select the ones you want to process."
        )
    if step in {"Routes", "Waypoints"}:
        return (
            "Update the name, description, and color so it's meaningful once imported.\n"
            "Use selection shortcuts to bulk-update or quickly scan large sets."
        )
    if step == "Preview":
        return (
            "Review export contents and select the destination directory.\n\n\n"
            "Navigate the directory browser, enter a file name prefix, then press Enter to export.\n"
            "Press [bold]Ctrl+N[/] to create a new folder (tree mode)."
        )
    return ""


def sidebar_shortcuts(step: str, shortcuts_map: "dict[str, Sequence[Tuple[str, str]]]") -> str:
    """
    Format keyboard shortcuts for the sidebar display.

    Args:
        step: Current workflow step name.
        shortcuts_map: Mapping from step names to (key, description) tuples.
            Typically StepAwareFooter.STEP_SHORTCUTS.

    Returns:
        Formatted shortcuts text, one per line.
    """
    shortcuts = shortcuts_map.get(step, [])
    if not shortcuts:
        return ""
    return "\n".join([f"{key}: {desc}" for key, desc in shortcuts])


def suggest_output_name(original_filename: str, output_prefix: str) -> str:
    """
    Suggest a rename target for an output file based on an output prefix.

    Intentionally conservative: same extension, no directory components.

    Args:
        original_filename: The original filename to base the suggestion on.
        output_prefix: User-provided prefix for output files.

    Returns:
        Suggested filename with prefix applied.
    """
    fn = str(original_filename or "").strip()
    if not fn:
        return fn
    prefix = sanitize_filename(str(output_prefix or "").strip())
    if not prefix:
        return Path(fn).name
    p = Path(fn)
    stem = p.stem or "output"
    ext = p.suffix
    return f"{prefix}_{stem}{ext}"
