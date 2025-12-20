#!/usr/bin/env python3
"""
Cairn - OnX ↔ CalTopo migration tool
Main CLI entry point
"""

from __future__ import annotations

import typer

# Import command modules
from cairn.commands import convert_cmd, config_cmd, migrate_cmd, tui_cmd

app = typer.Typer(
    name="cairn",
    help="Migrate map data between OnX Backcountry and CalTopo",
    no_args_is_help=True,
    add_completion=True,
)

# Register the convert command directly (not as a sub-app)
app.command(
    name="convert", help="Convert between supported formats (advanced)", hidden=True
)(convert_cmd.convert)

# Full-screen Textual TUI (opt-in)
app.command(name="tui", help="Launch full-screen TUI (CalTopo → OnX)")(tui_cmd.tui)

# Register command groups
app.add_typer(config_cmd.app, name="config", help="Manage configuration settings")
app.add_typer(migrate_cmd.app, name="migrate", help="Migration helpers (OnX ↔ CalTopo)")


@app.callback()
def callback() -> None:
    """
    Cairn - OnX ↔ CalTopo migration tool

    Primary workflow:
      migrate onx-to-caltopo  - Convert OnX GPX (+ optional KML) into CalTopo-importable GeoJSON

    Advanced workflow:
      convert                 - Convert between supported formats using --from/--to

    Utilities:
      config                  - Manage configuration settings
    """
    pass


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
