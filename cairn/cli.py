#!/usr/bin/env python3
"""
Cairn - CalTopo to onX Backcountry Migration Tool
Main CLI entry point
"""

import typer

# Import command modules
from cairn.commands import convert_cmd, config_cmd, icon_cmd

app = typer.Typer(
    name="cairn",
    help="CalTopo to onX Backcountry Migration Tool - Convert CalTopo exports to onX format",
    no_args_is_help=True,
    add_completion=True
)

# Register the convert command directly (not as a sub-app)
app.command(name="convert", help="Convert CalTopo GeoJSON export to onX format")(convert_cmd.convert)

# Register command groups for config and icon
app.add_typer(config_cmd.app, name="config", help="Manage configuration settings")
app.add_typer(icon_cmd.app, name="icon", help="Manage icon mappings")

@app.callback()
def callback():
    """
    Cairn - The CalTopo to onX Bridge

    Convert CalTopo GeoJSON exports to onX Backcountry-compatible files.

    Commands:
      convert  - Convert CalTopo GeoJSON to onX format
      config   - Manage configuration settings
      icon     - Manage icon mappings
    """
    pass

def main():
    """Entry point for the CLI."""
    app()

if __name__ == "__main__":
    main()
