"""Cairn - the CalTopo -> onX conversion engine behind the Cairn web app.

The web app (web/) is the only interface. It runs this package unmodified in
the browser via Pyodide, so nothing here may import a terminal/UI library.
The former typer CLI and Textual TUI were removed; see git tag `cli-final`.
"""

__version__ = "1.0.0"
__author__ = "Scott"
__description__ = "Convert CalTopo exports to onX Backcountry format"
