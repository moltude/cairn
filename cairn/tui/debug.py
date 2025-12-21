"""Centralized debug logging for TUI.

This module provides unified debug logging functionality extracted from app.py
and edit_screens.py to eliminate code duplication.
"""

import json
import os
import threading
import time
from typing import Optional, TextIO


_AGENT_DEBUG_LOG_PATH = "/Users/scott/_code/cairn/.cursor/debug.log"


def agent_log(*, hypothesisId: str, location: str, message: str, data: dict) -> None:
    """Log structured debug events for agent analysis.

    This is a best-effort function that never raises exceptions.
    Used for debugging and analysis purposes.

    Args:
        hypothesisId: Identifier for the hypothesis being tested
        location: Code location (e.g., "cairn/tui/app.py:on_key")
        message: Brief message describing the event
        data: Additional data dictionary
    """
    try:
        payload = {
            "timestamp": int(time.time() * 1000),
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": hypothesisId,
            "location": location,
            "message": message,
            "data": data,
        }
        with open(_AGENT_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Silently fail debug logging - never let it break the app
        return


class DebugLogger:
    """Thread-safe debug event logger with optional file streaming.

    Manages debug event logging for the TUI application. Handles in-memory
    event storage and optional file-based logging for reproducible traces.
    """

    def __init__(self, app) -> None:
        """Initialize debug logger.

        Args:
            app: The CairnTuiApp instance (used for accessing step state, etc.)
        """
        self.app = app
        self._debug_events: list[dict[str, object]] = []
        self._debug_file_path: Optional[str] = None
        self._debug_file: Optional[TextIO] = None
        self._debug_file_lock = threading.Lock()

    def log(self, *, event: str, data: Optional[dict[str, object]] = None) -> None:
        """Log a debug event.

        Best-effort debug event sink. Never crashes the UI if debug logging
        isn't configured or encounters errors.

        Args:
            event: Event name/type
            data: Optional event data dictionary
        """
        try:
            enabled = os.getenv("CAIRN_TUI_DEBUG") or os.getenv("CAIRN_TUI_ARTIFACTS")
            if not enabled:
                return
            payload: dict[str, object] = {
                "t": float(time.time()),
                "event": str(event),
                "step": str(getattr(self.app, "step", "")),
                "data": data or {},
            }
            self._debug_events.append(payload)
            # Prevent unbounded growth during long sessions/tests.
            if len(self._debug_events) > 500:
                self._debug_events = self._debug_events[-250:]

            # Optional: also stream each event as NDJSON for reproducible traces.
            debug_file_path = os.getenv("CAIRN_TUI_DEBUG_FILE")
            if debug_file_path:
                with self._debug_file_lock:
                    try:
                        if self._debug_file is None or self._debug_file_path != debug_file_path:
                            # Close any prior file handle first (best-effort).
                            try:
                                if self._debug_file is not None:
                                    self._debug_file.flush()
                                    self._debug_file.close()
                            except Exception:
                                pass
                            self._debug_file_path = debug_file_path
                            # Line-buffered append; still flush explicitly below for durability.
                            self._debug_file = open(debug_file_path, "a", encoding="utf-8", buffering=1)
                        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                        self._debug_file.write(line + "\n")
                        # Best-effort: flush so crashes / terminal corruption still preserve logs.
                        try:
                            self._debug_file.flush()
                        except Exception:
                            pass
                    except Exception:
                        # Never let debug logging break the UI.
                        return
        except Exception:
            return

    def close_debug_file(self) -> None:
        """Best-effort: flush/close debug file handle (if open)."""
        try:
            with self._debug_file_lock:
                try:
                    if self._debug_file is not None:
                        try:
                            self._debug_file.flush()
                        except Exception:
                            pass
                        try:
                            self._debug_file.close()
                        except Exception:
                            pass
                finally:
                    self._debug_file = None
                    self._debug_file_path = None
        except Exception:
            return

    @property
    def debug_events(self) -> list[dict[str, object]]:
        """Get the list of debug events (read-only)."""
        return self._debug_events.copy()


__all__ = ["agent_log", "DebugLogger"]
