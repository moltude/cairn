"""Performance profiling infrastructure for the TUI module.

This module provides context managers and decorators for timing operations
and identifying performance bottlenecks in the TUI.
"""

import time
import os
from contextlib import contextmanager
from typing import Optional, Callable, Any, Dict
from functools import wraps


# Global flag to enable/disable profiling
_PROFILING_ENABLED = os.getenv("CAIRN_PROFILE", "").lower() in ("1", "true", "yes")

# Threshold for logging slow operations (in milliseconds)
_SLOW_OPERATION_THRESHOLD_MS = float(os.getenv("CAIRN_PROFILE_THRESHOLD_MS", "50.0"))

# Storage for profiling data
_profiling_data: Dict[str, list[float]] = {}


def is_profiling_enabled() -> bool:
    """Check if profiling is enabled."""
    return _PROFILING_ENABLED


def set_profiling_enabled(enabled: bool) -> None:
    """Enable or disable profiling."""
    global _PROFILING_ENABLED
    _PROFILING_ENABLED = enabled


def get_profiling_data() -> Dict[str, list[float]]:
    """Get collected profiling data."""
    return _profiling_data.copy()


def clear_profiling_data() -> None:
    """Clear collected profiling data."""
    global _profiling_data
    _profiling_data = {}


@contextmanager
def profile_operation(name: str, threshold_ms: Optional[float] = None):
    """Context manager for profiling an operation.

    Args:
        name: Name of the operation being profiled
        threshold_ms: Optional threshold in milliseconds for logging slow operations.
                      If None, uses the global threshold.

    Example:
        with profile_operation("table_refresh"):
            table.refresh()
    """
    if not _PROFILING_ENABLED:
        yield
        return

    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000.0

        # Store profiling data
        if name not in _profiling_data:
            _profiling_data[name] = []
        _profiling_data[name].append(duration_ms)

        # Log slow operations
        threshold = threshold_ms if threshold_ms is not None else _SLOW_OPERATION_THRESHOLD_MS
        if duration_ms > threshold:
            _log_slow_operation(name, duration_ms)


def profile_method(name: Optional[str] = None, threshold_ms: Optional[float] = None):
    """Decorator for profiling method execution.

    Args:
        name: Optional name for the operation. If None, uses function name.
        threshold_ms: Optional threshold in milliseconds for logging slow operations.

    Example:
        @profile_method("step_transition")
        def goto(self, step: str):
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        operation_name = name or f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with profile_operation(operation_name, threshold_ms):
                return func(*args, **kwargs)

        return wrapper
    return decorator


def _log_slow_operation(name: str, duration_ms: float) -> None:
    """Log a slow operation (can be overridden for custom logging)."""
    # Default: print to stderr (can be redirected to a file)
    import sys
    print(f"[PROFILE] Slow operation: {name} took {duration_ms:.2f}ms", file=sys.stderr)


def get_operation_stats(name: str) -> Optional[Dict[str, float]]:
    """Get statistics for a profiled operation.

    Args:
        name: Name of the operation

    Returns:
        Dictionary with stats (count, total_ms, avg_ms, min_ms, max_ms) or None if not found
    """
    if name not in _profiling_data:
        return None

    durations = _profiling_data[name]
    if not durations:
        return None

    return {
        "count": len(durations),
        "total_ms": sum(durations),
        "avg_ms": sum(durations) / len(durations),
        "min_ms": min(durations),
        "max_ms": max(durations),
    }


def print_profiling_summary() -> None:
    """Print a summary of all profiled operations."""
    if not _profiling_data:
        print("No profiling data collected.")
        return

    print("\n=== Profiling Summary ===")
    for name, durations in sorted(_profiling_data.items()):
        stats = get_operation_stats(name)
        if stats:
            print(
                f"{name}: "
                f"count={stats['count']}, "
                f"avg={stats['avg_ms']:.2f}ms, "
                f"min={stats['min_ms']:.2f}ms, "
                f"max={stats['max_ms']:.2f}ms, "
                f"total={stats['total_ms']:.2f}ms"
            )
    print("=" * 25)


__all__ = [
    "is_profiling_enabled",
    "set_profiling_enabled",
    "get_profiling_data",
    "clear_profiling_data",
    "profile_operation",
    "profile_method",
    "get_operation_stats",
    "print_profiling_summary",
]
