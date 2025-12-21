"""Export operations for the TUI module.

This module manages export workflow, threading, and export state machine.

CRITICAL: Some errors must be synchronous (e.g., mkdir failure sets _export_error
immediately, not in thread callback). Tests depend on this behavior.
"""

import threading
from pathlib import Path
from typing import Optional, List, Tuple, Callable

from cairn.commands.convert_cmd import process_and_write_files
from cairn.tui.debug import agent_log as _agent_log


class ExportManager:
    """Manages export operations and threading.

    Preserves exact state machine semantics:
    - Some failures are SYNCHRONOUS (mkdir fails → _export_error set immediately)
    - Success/failure observed by polling _export_in_progress then checking
      _export_manifest/_export_error

    Note: State variables (_export_in_progress, _export_manifest, _export_error)
    are stored on app for backward compatibility. This manager provides methods
    to manipulate them consistently.
    """

    def __init__(self, app) -> None:
        """Initialize export manager.

        Args:
            app: The CairnTuiApp instance
        """
        self.app = app

    @property
    def export_in_progress(self) -> bool:
        """Check if export is in progress."""
        return self.app._export_in_progress

    @property
    def export_manifest(self) -> Optional[List[Tuple[str, str, int, int]]]:
        """Get export manifest (if export succeeded)."""
        return self.app._export_manifest

    @property
    def export_error(self) -> Optional[str]:
        """Get export error (if export failed)."""
        return self.app._export_error

    def start_export(self) -> None:
        """Start export process.

        Some errors are synchronous (set before return). This is critical
        for test assertions that check _export_error immediately after calling.
        """
        # Reset state (via app attributes for backward compatibility)
        self.app._export_error = None
        self.app._export_manifest = None
        self.app._export_in_progress = True
        self.app._render_main()

        # SYNCHRONOUS validation: check parsed data
        if self.app.model.parsed is None:
            self.app._export_error = "No parsed data. Go back."
            self.app._export_in_progress = False
            self.app._render_main()
            return

        # Determine output directory
        out_dir = self.app.model.output_dir or (Path.cwd() / "onx_ready")
        try:
            out_dir = out_dir.expanduser()
        except Exception:
            pass

        # SYNCHRONOUS validation: create output directory
        # This error must be set immediately, not deferred to thread
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.app._export_error = f"Failed to create output dir: {e}"
            self.app._export_in_progress = False
            self.app._render_main()
            return

        # Start worker thread
        t = threading.Thread(
            target=self._export_worker,
            args=(out_dir,),
            daemon=True,
        )
        t.start()

    def _export_worker(self, out_dir: Path) -> None:
        """Background worker. Marshal UI updates via call_from_thread.

        Args:
            out_dir: Output directory path
        """
        try:
            manifest = process_and_write_files(
                self.app.model.parsed,  # type: ignore[arg-type]
                out_dir,
                sort=True,
                skip_confirmation=True,
                config=self.app._config,
                split_gpx=True,
                max_gpx_bytes=4 * 1024 * 1024,
            )
            rows = [(a, b, int(c), int(d)) for (a, b, c, d) in manifest]
            self.app.call_from_thread(self._on_done, rows, None)
        except Exception as e:
            self.app.call_from_thread(self._on_done, None, f"Export error: {e}")

    def _on_done(
        self,
        manifest: Optional[List[Tuple[str, str, int, int]]],
        error: Optional[str],
    ) -> None:
        """Completion handler (runs on main thread).

        Args:
            manifest: Export manifest if successful
            error: Error message if failed
        """
        self.app._export_in_progress = False
        self.app._export_manifest = manifest
        self.app._export_error = error
        self.app._render_main()

        # After a successful export, prompt for next action (new file vs quit)
        self._show_post_export_prompt(error, manifest)

    def _show_post_export_prompt(
        self,
        error: Optional[str],
        manifest: Optional[List[Tuple[str, str, int, int]]],
    ) -> None:
        """Show post-export prompt if appropriate.

        Args:
            error: Error message if export failed
            manifest: Export manifest if successful
        """
        try:
            if error is None and manifest and not self.app._post_save_prompt_shown:
                self.app._post_save_prompt_shown = True
                from cairn.tui.edit_screens import ConfirmModal
                self.app.push_screen(
                    ConfirmModal(
                        "Export complete.\n\nMigrate another file?",
                        title="Export complete",
                    ),
                    self._on_post_save_choice,
                )
        except Exception:
            pass

    def _on_post_save_choice(self, confirmed: bool) -> None:
        """Handle post-export prompt response.

        Args:
            confirmed: True if user wants to migrate another file
        """
        if confirmed:
            self.app.action_new_file()
        else:
            try:
                self.app.exit()
            except Exception:
                pass


__all__ = ["ExportManager"]
