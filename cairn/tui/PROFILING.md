# TUI Performance Profiling

This document describes the performance profiling infrastructure for the TUI module.

## Overview

The profiling infrastructure allows you to measure and analyze performance characteristics of the TUI, including:
- App initialization and startup
- Step transitions
- Table refresh operations
- Event routing (key handlers, message handlers)
- File browser operations

## Enabling Profiling

Profiling is disabled by default to avoid performance overhead. To enable it, set the `CAIRN_PROFILE` environment variable:

```bash
export CAIRN_PROFILE=1
cairn tui
```

## Configuration

### Threshold for Slow Operations

By default, operations taking longer than 50ms are logged. You can adjust this threshold:

```bash
export CAIRN_PROFILE_THRESHOLD_MS=100  # Log operations > 100ms
cairn tui
```

## Profiled Operations

The following operations are automatically profiled:

### Startup
- `app_init` - Overall app initialization
- `app_init_model` - Model initialization
- `app_init_state` - State loading
- `app_init_config` - Config loading
- `app_init_debug_logger` - Debug logger setup
- `app_init_table_manager` - Table manager initialization
- `app_init_file_browser_manager` - File browser manager initialization
- `app_init_state_manager` - State manager initialization
- `compose` - Widget composition
- `on_mount` - App mounting

### Step Transitions
- `step_transition_{step_name}` - Navigation to each step (e.g., `step_transition_Select_file`)

### Table Operations
- `table_refresh_folder` - Folder table refresh
- `table_refresh_waypoints` - Waypoints table refresh
- `table_refresh_routes` - Routes table refresh

### Event Routing
- `action_export` - Export action handler
- `file_browser_refresh` - File browser refresh
- `file_browser_enter` - File browser enter handler

## Viewing Profiling Data

### During Runtime

When profiling is enabled, slow operations (> threshold) are automatically logged to stderr:

```
[PROFILE] Slow operation: table_refresh_waypoints took 87.23ms
```

### Programmatic Access

You can access profiling data programmatically:

```python
from cairn.tui.profiling import get_profiling_data, get_operation_stats, print_profiling_summary

# Get all profiling data
data = get_profiling_data()

# Get stats for a specific operation
stats = get_operation_stats("table_refresh_waypoints")
# Returns: {"count": 5, "total_ms": 250.0, "avg_ms": 50.0, "min_ms": 30.0, "max_ms": 87.0}

# Print summary of all operations
print_profiling_summary()
```

## Baseline Measurements

To establish baseline measurements:

1. Enable profiling:
   ```bash
   export CAIRN_PROFILE=1
   export CAIRN_PROFILE_THRESHOLD_MS=0  # Log all operations
   ```

2. Run the TUI through a typical workflow:
   - Start the app
   - Navigate through steps
   - Refresh tables
   - Perform file operations

3. Review the profiling output or use `print_profiling_summary()` to see statistics.

## Expected Performance Characteristics

Typical performance characteristics (may vary by system):

- **App initialization**: < 100ms
- **Step transitions**: < 50ms
- **Table refresh (small datasets)**: < 50ms
- **Table refresh (large datasets)**: 50-200ms
- **File browser operations**: < 100ms

## Optimization Targets

If profiling reveals slow operations (> 100ms), consider:

1. **Lazy loading**: Defer expensive operations until needed
2. **Caching**: Cache computed values that don't change frequently
3. **Batch operations**: Group multiple updates together
4. **Deferred UI updates**: Use `call_after_refresh()` for non-critical updates

## Implementation Details

The profiling infrastructure uses:
- `time.perf_counter()` for high-resolution timing
- Context managers (`profile_operation`) for automatic timing
- Decorators (`profile_method`) for method-level profiling
- Minimal overhead when disabled (single environment variable check)

## Example Usage in Code

```python
from cairn.tui.profiling import profile_operation

def my_expensive_operation():
    with profile_operation("my_operation"):
        # ... do work ...
        pass
```

Or using the decorator:

```python
from cairn.tui.profiling import profile_method

@profile_method("my_method")
def my_method(self):
    # ... do work ...
    pass
```
