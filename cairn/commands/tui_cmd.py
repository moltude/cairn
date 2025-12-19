"""
Textual full-screen TUI entrypoint.

This is intentionally separate from the main CLI flows so users can opt into a
full-screen UI mode without changing existing scripts.
"""

from __future__ import annotations

import typer


def tui() -> None:
    """Launch the Cairn Textual TUI (CalTopo → OnX v1)."""
    try:
        from cairn.tui.app import CairnTuiApp
    except Exception as e:  # pragma: no cover
        raise typer.Exit(f"Failed to import TUI dependencies: {e}")

    CairnTuiApp().run()
