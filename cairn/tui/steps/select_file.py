"""Select_file step rendering.

Handles file selection UI with support for both tree and table browsers.
"""

from pathlib import Path
import os

from textual.widgets import DataTable, Static

from cairn.tui.widgets import FilteredFileTree


def render_step(app, title, subtitle, body) -> None:
    """Render the Select_file step.

    Args:
        app: The CairnTuiApp instance
        title: Static widget for the main title
        subtitle: Static widget for the subtitle
        body: Container for the main body content
    """
    title.update("Select file")
    subtitle.update("Choose an input file (.json/.geojson/.kml/.gpx)")

    # Initialize file browser directory once per visit.
    if app.files.get_file_browser_dir() is None:
        # For table mode, use state.default_root or cwd
        default_root = Path(app._state.default_root).expanduser() if app._state.default_root else Path.cwd()
        try:
            app.files.set_file_browser_dir(default_root.resolve())
        except Exception:
            app.files.set_file_browser_dir(default_root)

    # A/B test: Choose implementation based on feature flag
    if app._use_tree_browser():
        # NEW: DirectoryTree implementation
        # Start from home directory by default, but use default_path from config if set.
        # Users can navigate up to parent directories to reach any location.
        tree_root = app.files.get_initial_directory()
        warning_message = None

        # Check if default_path was invalid (get_initial_directory returns home on error)
        # We need to detect this to show a warning
        default_path_str = getattr(app._config, 'default_path', None)
        if default_path_str:
            try:
                default_path = Path(default_path_str).expanduser().resolve()
                # If get_initial_directory returned home but we had a default_path, it means validation failed
                if tree_root == Path.home() and default_path != Path.home():
                    # Determine which validation failed
                    if not default_path.exists():
                        warning_message = f"default_path does not exist: {default_path_str}"
                    elif not default_path.is_dir():
                        warning_message = f"default_path is not a directory: {default_path_str}"
                    elif not os.access(default_path, os.R_OK):
                        warning_message = f"default_path is not readable (permission denied): {default_path_str}"
                    else:
                        # Must be a listability issue
                        warning_message = f"default_path cannot be accessed: {default_path_str}"
            except Exception as e:
                warning_message = f"Invalid default_path: {default_path_str} ({type(e).__name__}: {e})"

        try:
            # Check if tree already exists (to avoid recreating on re-render)
            tree = app.query_one("#file_browser", FilteredFileTree)
            # DirectoryTree doesn't support changing root path after creation
            # So we only update if the tree doesn't exist yet
        except Exception:
            # Create new tree starting from configured/default directory
            tree = FilteredFileTree(str(tree_root), id="file_browser")
            body.mount(tree)

        # Show temporary warning above tree if default_path was invalid
        if warning_message:
            warning_widget = Static(
                f"⚠ {warning_message}. Using home directory.",
                classes="warn",
                id="default_path_warning"
            )
            body.mount(warning_widget)
            # Schedule warning dismissal after 8 seconds
            try:
                app.set_timer(8.0, lambda: app._dismiss_warning("default_path_warning"))
            except Exception:
                pass

        body.mount(Static("Enter: open/select  Space: expand/collapse", classes="muted"))

        # Focus the tree
        try:
            app.call_after_refresh(tree.focus)
        except Exception:
            pass
    else:
        # EXISTING: DataTable implementation (default)
        body.mount(Static("Pick a file:", classes="muted"))
        table = DataTable(id="file_browser")
        table.add_columns("Name", "Type")
        body.mount(table)
        app._refresh_file_browser()
        body.mount(Static("Enter: open/select", classes="muted"))
        try:
            app.call_after_refresh(table.focus)
        except Exception:
            pass
