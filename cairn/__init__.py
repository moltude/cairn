"""Cairn - CalTopo to onX Backcountry Migration Tool."""

__version__ = "1.0.0"
__author__ = "Scott"
__description__ = "Convert CalTopo exports to onX Backcountry format"

__all__ = ["app", "main", "__version__"]


def __getattr__(name):
    """Load the CLI lazily.

    This used to be an eager `from cairn.cli import app, main`, which meant
    importing ANY submodule (e.g. cairn.core.writers) executed this file and
    pulled in typer/rich/textual. That made the transformation engine
    impossible to use without the whole CLI stack -- and impossible to run in
    environments that don't have it, such as Pyodide in a browser.

    PEP 562 module __getattr__ keeps `from cairn import app, main` working for
    the CLI entry point while leaving `import cairn.core.writers` dependency-free.
    """
    if name in ("app", "main"):
        from cairn import cli

        return getattr(cli, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
