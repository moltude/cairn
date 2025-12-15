#!/usr/bin/env python3
"""
Cairn - OnX ↔ CalTopo migration tool
Main CLI entry point
"""

import typer

# Import command modules
from cairn.commands import convert_cmd, config_cmd, icon_cmd, migrate_cmd

app = typer.Typer(
    name="cairn",
    help="Migrate map data between OnX Backcountry and CalTopo",
    no_args_is_help=True,
    add_completion=True
)

# Register the convert command directly (not as a sub-app)
app.command(name="convert", help="Convert between supported formats (advanced)")(convert_cmd.convert)

# Register command groups for config and icon
app.add_typer(config_cmd.app, name="config", help="Manage configuration settings")
app.add_typer(icon_cmd.app, name="icon", help="Manage icon mappings")
app.add_typer(migrate_cmd.app, name="migrate", help="Migration helpers (OnX ↔ CalTopo)")

@app.callback()
def callback():
    """
    Cairn - OnX ↔ CalTopo migration tool

    Primary workflow:
      migrate OnX-to-caltopo  - Convert OnX GPX (+ optional KML) into CalTopo-importable GeoJSON

    Advanced workflow:
      convert                 - Convert between supported formats using --from/--to

    Utilities:
      config                  - Manage configuration settings
      icon                    - Manage icon mappings
    """
    pass

def main():
    """Entry point for the CLI."""
    app()

if __name__ == "__main__":
    main()
