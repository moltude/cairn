# Final Refactoring Plan: Decomposing `app.py`

**Date:** December 21, 2025
**Status:** 🚧 In Progress (Phases 0-4 Complete)
**Synthesized From:** REFACTORING_PLAN.md, gpt52-suggestions.md, composer.md
**Current File Size:** ~2,332 lines (down from 4,087 originally)
**Target:** Main file < 500 lines, no module > 800 lines

---

## 📊 Current State Analysis

### Quantified Complexity

| Metric | Current Value | Risk Level |
|--------|---------------|------------|
| `app.py` total lines | 4,087 | 🔴 Critical |
| Total methods in `CairnTuiApp` | 104 | 🔴 High |
| Private methods (`_*`) | 49+ | 🟡 Medium |
| `on_key()` method lines | ~400 | 🔴 Critical |
| Test files using private API (`app._`) | 9 files, 188 usages | 🔴 High |
| Imports from `cairn.tui.app` | 61 locations | 🟡 Medium |
| Circular import pressure | `edit_screens.py` → `app.py` | 🟡 Medium |
| Duplicated code (`_agent_log`) | 2 identical copies | 🟢 Low |

### Critical Constraints (from gpt52-suggestions.md)

1. **Test Coupling**: 188 usages of private API across 9 test files
2. **Circular Imports**: `edit_screens.py` imports `FilteredDirectoryTree` from `app.py`
3. **Widget ID Stability**: Tests rely on stable widget IDs (`#routes_table`, `#file_browser`, etc.)
4. **Reactive Properties**: `step: reactive[str]` triggers UI updates; state must stay on App
5. **Threading Semantics**: Export has specific synchronous/async error paths tests depend on

---

## 🏗️ Final Module Architecture

```
cairn/tui/
├── __init__.py                 # Public API exports (compatibility layer)
├── app.py                      # Main coordinator (~400 lines) ⭐
├── models.py                   # Data models, constants, widget IDs (~100 lines)
├── widgets.py                  # Custom Textual widgets (~200 lines)
├── debug.py                    # Centralized debug logging (~150 lines)
├── tables.py                   # DataTable operations (~400 lines)
├── file_browser.py             # File/directory browsing (~500 lines)
├── state.py                    # State management, navigation (~400 lines)
├── events.py                   # Event routing, focus management (~300 lines)
├── editing.py                  # Feature editing operations (~500 lines)
├── export.py                   # Export operations, threading (~300 lines)
├── rendering.py                # UI rendering and layout (~700 lines)
├── edit_screens.py             # (existing) Modal screens and overlays
└── theme.tcss                  # (existing) CSS styling
```

### Import Direction Rules (CRITICAL)

```
models.py     → core types only (no Textual, no app, no managers)
widgets.py    → Textual + models.py (no app, no managers)
debug.py      → stdlib only (json, threading, time, os)
tables.py     → Textual + models.py + debug.py
file_browser.py → Textual + models.py + widgets.py + debug.py
state.py      → models.py + debug.py (no widgets, no Textual containers)
events.py     → models.py + debug.py (delegates to app for widget queries)
editing.py    → models.py + debug.py + edit_screens.py
export.py     → models.py + debug.py + cairn.commands.convert_cmd
rendering.py  → Textual + models.py + widgets.py + debug.py
edit_screens.py → Textual + models.py + widgets.py (NEVER imports from app.py)
app.py        → imports ALL modules (coordinator)
```

---

## 🚀 Phased Migration Strategy

Phases ordered by **cost/benefit ratio** (highest value + lowest risk first):

### Phase 0: Foundation & Constraints
**Duration:** 0.5 days | **Risk:** 🟢 Very Low | **ROI:** 🟢 High

**Purpose:** Establish guardrails before any extraction.

**Tasks:**
1. Create `models.py` with widget ID constants (stable test API)
2. Create import sanity test to detect circular imports early
3. Document state ownership matrix
4. Set up performance profiling baseline

**Agent Instructions:**
```markdown
## Phase 0: Foundation & Constraints

### Goal
Create foundational infrastructure to prevent regressions during refactoring.

### Steps
1. Create `cairn/tui/models.py` with:
   - `class WidgetIds` containing all widget ID constants as class attributes
   - `STEPS` list (extract from app.py line 121-128)
   - `STEP_LABELS` dict (extract from app.py line 130-138)
   - `TuiModel` dataclass (extract from app.py line 141-146)
   - `_VISIBLE_INPUT_EXTS`, `_PARSEABLE_INPUT_EXTS` (extract from app.py line 78-79)

2. Create `tests/test_import_sanity.py`:
   ```python
   def test_no_circular_imports():
       """Detect circular imports between TUI modules."""
       import cairn.tui.app
       import cairn.tui.edit_screens
       import cairn.tui.models
       # Add new modules as they're created
   ```

3. Update `app.py` to import from `models.py` instead of defining locally

4. Run full test suite to verify no regressions

### Verification
- [ ] Import sanity test passes
- [ ] All existing tests pass
- [ ] No behavior changes
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Forgotten import update | Medium | Grep for moved constants |
| Tests break due to import path | Low | Keep re-exports in app.py initially |

**Testing:**
- Run: `uv run pytest tests/ -x -q`
- Verify: Import sanity test passes

---

### Phase 1: Extract Widgets (Unblocks Everything)
**Duration:** 0.5 days | **Risk:** 🟢 Low | **ROI:** 🟢 Very High

**Purpose:** Remove circular import pressure between `app.py` and `edit_screens.py`.

**Tasks:**
1. Create `widgets.py` with `FilteredFileTree`, `FilteredDirectoryTree`, `Stepper`, `StepAwareFooter`
2. Update `edit_screens.py` to import from `widgets.py` instead of `app.py`
3. Add re-exports in `app.py` for backward compatibility

**Agent Instructions:**
```markdown
## Phase 1: Extract Widgets

### Goal
Move custom widgets to dedicated module to eliminate circular import risk.

### Steps
1. Create `cairn/tui/widgets.py`:
   - Move `FilteredFileTree` (app.py lines 82-102)
   - Move `FilteredDirectoryTree` (app.py lines 105-118)
   - Move `Stepper` (app.py lines 149-176, approximately)
   - Move `StepAwareFooter` (find in app.py, class that extends Footer)
   - Import `_VISIBLE_INPUT_EXTS` from models.py

2. Update `cairn/tui/edit_screens.py`:
   - Change: `from cairn.tui.app import FilteredDirectoryTree`
   - To: `from cairn.tui.widgets import FilteredDirectoryTree`

3. Update `cairn/tui/app.py`:
   - Remove moved classes
   - Add compatibility re-exports:
     ```python
     from cairn.tui.widgets import (
         FilteredFileTree,
         FilteredDirectoryTree,
         Stepper,
         StepAwareFooter,
     )
     ```

4. Update `tests/test_tui_file_browser.py`:
   - Keep existing imports (they use `from cairn.tui.app import`)
   - Compatibility re-exports handle this

### Verification
- [ ] Import sanity test still passes
- [ ] `uv run pytest tests/test_tui_file_browser.py -v` passes
- [ ] No circular import errors
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Circular import in edit_screens | High without fix | This phase fixes it |
| Test import breaks | Low | Re-exports maintain compatibility |

**Testing:**
- Run: `uv run pytest tests/test_tui_file_browser.py tests/test_import_sanity.py -v`
- Verify: Tree browser A/B test still works

---

### Phase 2: Extract Debug Utilities (Dead Code Cleanup)
**Duration:** 0.5 days | **Risk:** 🟢 Very Low | **ROI:** 🟢 Medium

**Purpose:** Consolidate duplicated debug logging and remove dead code.

**Tasks:**
1. Create `debug.py` with unified `_agent_log` and `DebugLogger` class
2. Remove duplicate `_agent_log` from `app.py` and `edit_screens.py`
3. Centralize `_dbg` method logic

**Agent Instructions:**
```markdown
## Phase 2: Extract Debug Utilities

### Goal
Consolidate duplicated debug logging into single module.

### Dead Code Identified
- `_agent_log` duplicated in app.py (line 57) and edit_screens.py (line 24)
- Both are identical - merge into one

### Steps
1. Create `cairn/tui/debug.py`:
   ```python
   """Centralized debug logging for TUI."""
   import json
   import os
   import threading
   import time
   from typing import Optional, TextIO

   _AGENT_DEBUG_LOG_PATH = "/Users/scott/_code/cairn/.cursor/debug.log"

   def agent_log(*, hypothesisId: str, location: str, message: str, data: dict) -> None:
       """Log structured debug events for agent analysis."""
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
           return  # Never let debug logging break the app

   class DebugLogger:
       """Thread-safe debug event logger with optional file streaming."""
       # ... (extract _dbg, _close_debug_file, _emit_snapshot logic)
   ```

2. Update `cairn/tui/app.py`:
   - Remove `_agent_log` function (lines 53-72)
   - Remove `_dbg` method internals, delegate to `DebugLogger`
   - Keep `_dbg` as thin wrapper for compatibility

3. Update `cairn/tui/edit_screens.py`:
   - Remove `_agent_log` function (lines 17-35)
   - Import: `from cairn.tui.debug import agent_log`
   - Replace calls: `_agent_log(...)` → `agent_log(...)`

### Verification
- [ ] Debug logging still works (set CAIRN_TUI_DEBUG=1)
- [ ] All tests pass
- [ ] No duplicate code remains
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Debug logging breaks app | Very Low | All debug code is already best-effort |
| Thread safety issues | Low | Current code already thread-safe |

**Testing:**
- Run: `CAIRN_TUI_DEBUG=1 uv run python -c "from cairn.tui.app import CairnTuiApp; print('OK')"`
- Verify: No errors, debug file created

---

### Phase 3: Extract Table Operations
**Duration:** 1 day | **Risk:** 🟡 Medium | **ROI:** 🟢 High

**Purpose:** Extract DataTable operations for testability and reuse.

**Tasks:**
1. Create `tables.py` with `TableManager` class
2. Extract `_refresh_*_table`, `_datatable_clear_rows`, `_table_cursor_row_key`
3. Keep compatibility methods on App

**Agent Instructions:**
```markdown
## Phase 3: Extract Table Operations

### Goal
Isolate DataTable operations for independent testing.

### Methods to Extract
- `_refresh_folder_table()` (line 675)
- `_refresh_waypoints_table()` (line 742)
- `_refresh_routes_table()` (line 784)
- `_datatable_clear_rows()` (line 644)
- `_table_cursor_row_key()` (line 622)
- `_color_chip()` (line 591)
- `_resolved_waypoint_icon()` (line 598)
- `_resolved_waypoint_color()` (line 612)

### Steps
1. Create `cairn/tui/tables.py`:
   ```python
   from textual.widgets import DataTable
   from textual.coordinate import Coordinate
   from rich.text import Text
   from typing import Optional
   from cairn.tui.debug import agent_log

   class TableManager:
       """Manages DataTable operations for the TUI."""

       def __init__(self, app):
           self.app = app

       @staticmethod
       def cursor_row_key(table: DataTable) -> Optional[str]:
           """Get row key at cursor position."""
           # ... extract from app.py _table_cursor_row_key

       @staticmethod
       def clear_rows(table: DataTable) -> None:
           """Clear all rows from a DataTable."""
           # ... extract from app.py _datatable_clear_rows

       def refresh_folder_table(self) -> Optional[int]:
           # ... extract logic, use self.app.model, self.app.query_one

       # etc.
   ```

2. Update `cairn/tui/app.py`:
   - Add: `self.tables = TableManager(self)` in `__init__`
   - Keep old methods as thin delegators:
     ```python
     def _table_cursor_row_key(self, table: DataTable) -> Optional[str]:
         return TableManager.cursor_row_key(table)

     def _refresh_routes_table(self) -> None:
         return self.tables.refresh_routes_table()
     ```

### Verification
- [ ] Routes table populates correctly
- [ ] Waypoints table populates correctly
- [ ] Cursor navigation works
- [ ] Selection tracking works
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Table refresh timing | Medium | Keep exact refresh semantics |
| Selection state desync | Medium | State stays on App, manager just operates |
| Test assertions on `_refresh_routes_table` | High | Keep delegator methods |

**Testing:**
- Run: `uv run pytest tests/test_tui_filter_search.py tests/test_tui_editing_comprehensive.py -v`
- Verify: Table filtering and editing work correctly

---

### Phase 4: Extract File Browser
**Duration:** 1 day | **Risk:** 🟡 Medium | **ROI:** 🟢 High

**Purpose:** Consolidate filesystem browsing logic, fix SaveTargetOverlay ownership.

**Tasks:**
1. Create `file_browser.py` with `FileBrowserManager`
2. Consolidate 3 duplicate directory listing locations
3. Support both tree and table browser modes

**Agent Instructions:**
```markdown
## Phase 4: Extract File Browser

### Goal
Consolidate all file browsing logic into one manager.

### Duplicate Locations Identified
1. Select_file browser (table mode in app.py, tree mode via FilteredFileTree)
2. Export dir selection table in app.py
3. SaveTargetOverlay browser in edit_screens.py

### Methods to Extract
- `_refresh_file_browser()` (line 1107)
- `_file_browser_enter()` (line 1173)
- `_refresh_export_dir_table()` (line 1216)
- `_export_dir_table_enter()` (line 1244)
- `_refresh_save_browser()` (line 1266)
- `_save_browser_enter()` (line 1353)
- `_file_browser_dir` state variable

### Steps
1. Create `cairn/tui/file_browser.py`:
   ```python
   from pathlib import Path
   from typing import Optional
   from textual.widgets import DataTable
   from cairn.tui.models import _VISIBLE_INPUT_EXTS, _PARSEABLE_INPUT_EXTS
   from cairn.tui.debug import agent_log

   class FileBrowserManager:
       """Handles all file/directory browsing operations."""

       def __init__(self, app):
           self.app = app
           self._file_browser_dir: Optional[Path] = None
           self._save_browser_dir: Optional[Path] = None

       def use_tree_browser(self) -> bool:
           """Check if tree browser A/B test is enabled."""
           return self.app._use_tree_browser()

       def refresh_file_browser(self) -> None:
           """Refresh input file browser (tree or table mode)."""
           # ... extract logic

       # etc.
   ```

2. Update `app.py`:
   - Add: `self.files = FileBrowserManager(self)` in `__init__`
   - Remove `_file_browser_dir` (now in manager)
   - Keep delegator methods for test compatibility

### Important: default_path config
The config now supports `default_path` for TUI tree browser starting directory.
Route this through FileBrowserManager:
```python
def get_initial_directory(self) -> Path:
    if self.app._config.default_path:
        p = Path(self.app._config.default_path).expanduser()
        if p.exists() and p.is_dir():
            return p
    return Path.home()
```

### Verification
- [ ] Table mode file browser works
- [ ] Tree mode file browser works (CAIRN_USE_TREE_BROWSER=1)
- [ ] Save browser works
- [ ] default_path config respected
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Browser mode switch breaks | Medium | Test both modes explicitly |
| Path state inconsistency | Medium | Keep state in manager, not split |
| SaveTargetOverlay coordination | High | Keep overlay in edit_screens, manager handles listing |

**Testing:**
- Run: `uv run pytest tests/test_tui_file_browser.py tests/test_tui_save_flow_e2e.py -v`
- Run with tree mode: `CAIRN_USE_TREE_BROWSER=1 uv run pytest tests/test_tui_file_browser.py -v`

---

### Phase 5: Extract State Management
**Duration:** 1.5 days | **Risk:** 🟡 Medium | **ROI:** 🟢 High

**Purpose:** Centralize navigation and state transitions.

**Tasks:**
1. Create `state.py` with `StateManager`
2. Extract `_goto`, `_reset_focus_for_step`, selection tracking
3. Document state ownership matrix

**Agent Instructions:**
```markdown
## Phase 5: Extract State Management

### Goal
Centralize navigation and workflow state, keeping reactive properties on App.

### Key Constraint
Textual's `step: reactive[str]` MUST stay on CairnTuiApp for automatic UI updates.
StateManager handles logic; App holds the reactive property.

### Methods to Extract
- `_goto()` (line 1423)
- `_reset_focus_for_step()` (line 1078)
- `_update_footer()` (line 1441)
- `_infer_folder_selection()` (line 1558)
- `_get_next_step_after_folder()` (line 1592)
- `_has_real_folders()` (line 1611)
- Selection state: `_selected_route_keys`, `_selected_waypoint_keys`, `_selected_folders`
- Done state: `_done_steps`

### Steps
1. Create `cairn/tui/state.py`:
   ```python
   from typing import Optional, Set
   from cairn.tui.models import STEPS
   from cairn.tui.debug import agent_log

   class StateManager:
       """Manages workflow state and navigation."""

       def __init__(self, app):
           self.app = app
           self._done_steps: Set[str] = set()
           self._selected_route_keys: Set[str] = set()
           self._selected_waypoint_keys: Set[str] = set()
           self._selected_folders: Set[str] = set()

       def goto(self, step: str) -> None:
           """Navigate to a step. Updates app.step reactive property."""
           if step not in STEPS:
               return

           # Mark current as done
           if self.app.step in STEPS:
               self._done_steps.add(self.app.step)

           # Update reactive (triggers UI refresh)
           self.app.step = step

           # Sync UI
           self.reset_focus_for_step()
           self.update_footer()

       def reset_focus_for_step(self) -> None:
           """Set focus to appropriate widget for current step."""
           # ... extract from _reset_focus_for_step

       @property
       def selected_route_keys(self) -> Set[str]:
           return self._selected_route_keys

       # etc.
   ```

2. Update `app.py`:
   - Add: `self.state = StateManager(self)` in `__init__`
   - Remove moved state variables
   - Keep `_goto` as delegator:
     ```python
     def _goto(self, step: str) -> None:
         self.state.goto(step)
     ```
   - Add compatibility properties:
     ```python
     @property
     def _selected_route_keys(self) -> Set[str]:
         return self.state.selected_route_keys

     @_selected_route_keys.setter
     def _selected_route_keys(self, value: Set[str]) -> None:
         self.state._selected_route_keys = value
     ```

### State Ownership Matrix
| State | Owner | Mutators |
|-------|-------|----------|
| `step: reactive[str]` | App | StateManager.goto() |
| `_done_steps` | StateManager | StateManager.goto() |
| `_selected_route_keys` | StateManager | App event handlers |
| `_selected_waypoint_keys` | StateManager | App event handlers |
| `model.parsed` | App.model | App._set_input_path() |
| `_export_manifest` | ExportManager | ExportManager.on_done() |

### Verification
- [ ] Step navigation works (Enter to continue, Esc to go back)
- [ ] Focus restored correctly on step change
- [ ] Selection state preserved across navigation
- [ ] Multi-folder workflow works
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Reactive property desync | High | Reactive stays on App, manager calls setter |
| Focus timing changes | Medium | Keep exact focus restoration logic |
| Test assertions on `_goto` | High | Keep delegator method |

**Testing:**
- Run: `uv run pytest tests/test_tui_navigation_smoke.py tests/test_tui_focus_regressions.py -v`
- Verify: All navigation and focus tests pass

---

### Phase 6: Extract Event Routing
**Duration:** 1.5 days | **Risk:** 🔴 High | **ROI:** 🟡 Medium

**Purpose:** Decompose the 400-line `on_key()` method.

**Tasks:**
1. Create `events.py` with `EventRouter`
2. Extract overlay priority handling
3. Centralize focus management

**Agent Instructions:**
```markdown
## Phase 6: Extract Event Routing

### Goal
Decompose the massive on_key() method into manageable event routing.

### Current Complexity
- `on_key()` is ~400 lines (lines 3455-3853+)
- Handles: overlay routing, focus management, step-specific shortcuts
- Contains inline helper `_overlay_open()` duplicating class method

### Steps
1. Create `cairn/tui/events.py`:
   ```python
   from typing import Optional
   from cairn.tui.models import WidgetIds
   from cairn.tui.debug import agent_log

   class EventRouter:
       """Centralized keyboard event routing and focus management."""

       # Overlay priority order (highest first)
       OVERLAY_PRIORITY = [
           "#icon_picker_overlay",
           "#color_picker_overlay",
           "#inline_edit_overlay",
           "#save_target_overlay",
           "#rename_overlay",
           "#description_overlay",
           "#confirm_overlay",
       ]

       def __init__(self, app):
           self.app = app

       def route_key(self, event) -> bool:
           """Route key event. Returns True if handled."""
           # Check if modal screen is active
           if self._is_modal_screen_active():
               return False  # Let modal handle it

           # Check overlays in priority order
           for overlay_id in self.OVERLAY_PRIORITY:
               if self._is_overlay_open(overlay_id):
                   return self._handle_overlay_key(overlay_id, event)

           # Global shortcuts
           if self._handle_global_shortcut(event):
               return True

           # Step-specific shortcuts
           return self._handle_step_shortcut(event)

       def _is_overlay_open(self, selector: str) -> bool:
           try:
               w = self.app.query_one(selector)
               return bool(getattr(w, "has_class", lambda _: False)("open"))
           except Exception:
               return False

       def _handle_overlay_key(self, overlay_id: str, event) -> bool:
           """Handle key for specific overlay."""
           key = str(getattr(event, "key", "") or "")

           if overlay_id == "#icon_picker_overlay":
               return self._handle_icon_picker_key(event, key)
           elif overlay_id == "#color_picker_overlay":
               return self._handle_color_picker_key(event, key)
           # ... etc

       # Extract each overlay's key handling as separate method
   ```

2. Update `app.py`:
   - Add: `self.events = EventRouter(self)` in `__init__`
   - Simplify `on_key()`:
     ```python
     def on_key(self, event) -> None:
         # Debug logging
         self._dbg(event="key", data={...})

         # Delegate to event router
         if self.events.route_key(event):
             try:
                 event.stop()
             except Exception:
                 pass
     ```

### Key Behavior to Preserve
- Overlay events must be handled before step navigation
- ModalScreen must be detected and bypassed
- Icon/color picker table cursor sync (when focus is on filter input)
- Exact Escape behavior per overlay type

### Verification
- [ ] All keyboard shortcuts work
- [ ] Icon picker navigation works
- [ ] Color picker navigation works
- [ ] Escape closes overlays correctly
- [ ] Enter confirms selections
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Event routing order change | High | Preserve exact overlay priority |
| Focus timing change | High | Don't change when event.stop() is called |
| Picker table cursor desync | Medium | Keep cursor sync logic intact |

**Testing:**
- Run: `uv run pytest tests/test_tui_inline_edit_modal.py tests/test_tui_editing_e2e.py -v`
- Manual: Test icon picker, color picker, inline edit overlay keyboard navigation

---

### Phase 7: Extract Export Operations
**Duration:** 1 day | **Risk:** 🟡 Medium | **ROI:** 🟡 Medium

**Purpose:** Isolate threading and export state machine.

**Tasks:**
1. Create `export.py` with `ExportManager`
2. Preserve synchronous error semantics (critical for tests)
3. Keep threading boundary unchanged

**Agent Instructions:**
```markdown
## Phase 7: Extract Export Operations

### Goal
Extract export workflow while preserving exact state machine semantics.

### Critical Constraint (from gpt52-suggestions.md)
Tests assert specific export behavior:
- Some failures are **synchronous** (mkdir fails → _export_error set immediately)
- Success/failure observed by polling `_export_in_progress` then checking `_export_manifest`/`_export_error`

DO NOT change when flags are set or exception handling order.

### Methods to Extract
- `_on_export_confirmed()` (line 1785)
- Export worker thread logic
- `_export_in_progress`, `_export_manifest`, `_export_error` state

### Steps
1. Create `cairn/tui/export.py`:
   ```python
   import threading
   from pathlib import Path
   from typing import Optional, List
   from cairn.commands.convert_cmd import process_and_write_files
   from cairn.tui.debug import agent_log

   class ExportManager:
       """Manages export operations and threading."""

       def __init__(self, app):
           self.app = app
           self._export_in_progress = False
           self._export_manifest: Optional[List] = None
           self._export_error: Optional[str] = None

       def start_export(self, output_dir: Path, ...) -> None:
           """Start export. Some errors are synchronous!"""
           if self._export_in_progress:
               return

           # SYNCHRONOUS validation (tests depend on this)
           try:
               output_dir.mkdir(parents=True, exist_ok=True)
           except Exception as e:
               # Set error SYNCHRONOUSLY - do not defer to thread
               self._export_error = str(e)
               return

           self._export_in_progress = True
           self._export_manifest = None
           self._export_error = None

           # Start worker thread
           thread = threading.Thread(
               target=self._export_worker,
               args=(output_dir, ...),
               daemon=True
           )
           thread.start()

       def _export_worker(self, output_dir: Path, ...) -> None:
           """Background worker. Marshal UI updates via call_from_thread."""
           try:
               manifest = process_and_write_files(...)
               self.app.call_from_thread(self._on_done, manifest, None)
           except Exception as e:
               self.app.call_from_thread(self._on_done, None, str(e))

       def _on_done(self, manifest, error) -> None:
           """Completion handler (runs on main thread)."""
           self._export_in_progress = False
           self._export_manifest = manifest
           self._export_error = error
           # Trigger UI update...
   ```

2. Update `app.py`:
   - Add: `self.exports = ExportManager(self)` in `__init__`
   - Add compatibility properties:
     ```python
     @property
     def _export_in_progress(self) -> bool:
         return self.exports._export_in_progress

     @property
     def _export_manifest(self):
         return self.exports._export_manifest

     @property
     def _export_error(self):
         return self.exports._export_error
     ```

### Verification
- [ ] Export success flow works
- [ ] Export error flow works (synchronous errors)
- [ ] Export error flow works (async errors in worker)
- [ ] Progress tracking works
- [ ] Tests can poll _export_in_progress reliably
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Synchronous error becomes async | Critical | Preserve exact error paths |
| Thread race condition | Medium | Keep same thread boundary |
| Test flakiness | Medium | Don't change flag ordering |

**Testing:**
- Run: `uv run pytest tests/test_tui_save_flow_e2e.py -v`
- Verify: Both success and error exports work, test polling is stable

---

### Phase 8: Extract Editing Operations
**Duration:** 1.5 days | **Risk:** 🟡 Medium | **ROI:** 🟡 Medium

**Purpose:** Consolidate feature editing logic.

**Tasks:**
1. Create `editing.py` with `EditManager`
2. Extract inline edit, icon/color picking, rename flows
3. Keep edit context tracking

**Agent Instructions:**
```markdown
## Phase 8: Extract Editing Operations

### Goal
Consolidate all feature editing (waypoints/routes) into one manager.

### Methods to Extract
- `_show_inline_overlay()` (line 930)
- `_on_inline_edit_action()` (line 2125)
- `_apply_edit_payload()` (line 2256)
- `_apply_edit_and_return_to_inline()` (line 2223)
- `_apply_rename_confirmed()` (line 2383)
- `_selected_features()` (line 2073)
- `_selected_keys_for_step()` (line 2062)
- Edit state: `_in_single_item_edit`, `_in_inline_edit`, `_edit_context`

### Steps
1. Create `cairn/tui/editing.py`:
   ```python
   from typing import Optional, List
   from cairn.tui.edit_screens import EditContext, InlineEditOverlay
   from cairn.tui.debug import agent_log

   class EditManager:
       """Manages feature editing operations."""

       def __init__(self, app):
           self.app = app
           self._in_single_item_edit = False
           self._in_inline_edit = False
           self._edit_context: Optional[EditContext] = None

       def show_inline_overlay(self, ctx: EditContext, feats: List) -> None:
           """Show inline edit overlay for selected features."""
           # ... extract from _show_inline_overlay

       def apply_edit_payload(self, payload) -> None:
           """Apply edit changes to features."""
           # ... extract from _apply_edit_payload

       def selected_features(self, ctx: EditContext) -> List:
           """Get selected features for context."""
           # ... extract from _selected_features
   ```

2. Update `app.py`:
   - Add: `self.edits = EditManager(self)` in `__init__`
   - Delegate methods

### Verification
- [ ] Inline edit overlay opens correctly
- [ ] Icon editing works
- [ ] Color editing works
- [ ] Name/description editing works
- [ ] Multi-item editing works
- [ ] Changes persist correctly
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Edit context lost between overlays | Medium | Keep context in manager |
| Overlay close timing | Medium | Don't change event flow |

**Testing:**
- Run: `uv run pytest tests/test_tui_editing_comprehensive.py tests/test_tui_editing_e2e.py -v`

---

### Phase 9: Extract Rendering
**Duration:** 2 days | **Risk:** 🔴 High | **ROI:** 🟡 Medium

**Purpose:** Isolate UI rendering from business logic.

**Tasks:**
1. Create `rendering.py` with `RenderManager`
2. Extract compose, sidebar, step-specific rendering
3. Keep reactive update semantics

**Agent Instructions:**
```markdown
## Phase 9: Extract Rendering

### Goal
Isolate UI rendering for cleaner separation of concerns.

### Warning
This is the highest-risk phase. Rendering changes affect:
- Widget composition order
- Focus timing
- Reactive update triggers

### Methods to Extract
- `compose()`
- `_render_sidebar()`  (line 2436)
- Step-specific render methods (find all `_render_*` or render logic in watch_step)
- `sidebar_instructions()`, `sidebar_shortcuts()` per step

### Steps
1. Create `cairn/tui/rendering.py`:
   ```python
   from textual.app import ComposeResult
   from textual.containers import Container, Horizontal, Vertical
   from textual.widgets import DataTable, Header, Input, Static
   from cairn.tui.widgets import Stepper, StepAwareFooter
   from cairn.tui.models import STEPS, STEP_LABELS, WidgetIds

   class RenderManager:
       """Manages UI rendering and layout."""

       def __init__(self, app):
           self.app = app

       def compose(self) -> ComposeResult:
           """Compose initial app layout."""
           yield Header()
           with Horizontal():
               yield Stepper(steps=STEPS, id="stepper")
               with Vertical(id="sidebar"):
                   yield Static("", id="sidebar_instructions")
                   yield Static("", id="sidebar_shortcuts")
               yield Container(id="main_body")
           yield StepAwareFooter(id="footer")
           # ... yield overlays

       def render_main(self) -> None:
           """Render main content for current step."""
           step = self.app.step
           # Clear and render based on step...

       def render_sidebar(self) -> None:
           """Update sidebar content."""
           # ... extract from _render_sidebar
   ```

2. Update `app.py`:
   - Add: `self.renderer = RenderManager(self)` in `__init__`
   - Delegate compose:
     ```python
     def compose(self) -> ComposeResult:
         return self.renderer.compose()
     ```

### Verification
- [ ] All steps render correctly
- [ ] Sidebar updates on step change
- [ ] Overlays render correctly
- [ ] Focus works after render
```

**Threats & Mitigations:**
| Threat | Probability | Mitigation |
|--------|-------------|------------|
| Composition order change | High | Match exact yield order |
| Reactive update broken | High | Call render from watch_step |
| Widget ID change | Low | Use WidgetIds constants |

**Testing:**
- Run: `uv run pytest tests/test_tui_scenarios.py -v`
- Manual: Navigate through all steps visually

---

### Phase 10: Test Migration & Cleanup
**Duration:** 1.5 days | **Risk:** 🟢 Low | **ROI:** 🟡 Medium

**Purpose:** Migrate tests to use new APIs, remove compatibility shims.

**Tasks:**
1. Create test harness/fixture for common patterns
2. Migrate tests to use managers directly (optional)
3. Remove compatibility properties/methods
4. Final cleanup and documentation

**Agent Instructions:**
```markdown
## Phase 10: Test Migration & Cleanup

### Goal
Clean up compatibility layer and document new architecture.

### Test Harness
Create `tests/conftest.py` additions:
```python
import pytest
from cairn.tui.app import CairnTuiApp

@pytest.fixture
def tui_app():
    """Create a TUI app for testing."""
    app = CairnTuiApp()
    return app

@pytest.fixture
def tui_state(tui_app):
    """Access state manager directly."""
    return tui_app.state

@pytest.fixture
def tui_tables(tui_app):
    """Access table manager directly."""
    return tui_app.tables
```

### Compatibility Removal (Optional)
If all tests pass, consider removing:
- Property proxies like `@property def _selected_route_keys`
- Delegator methods like `def _goto(self, step): self.state.goto(step)`

**Recommendation:** Keep delegators for now. Remove in future cleanup.

### Documentation Updates
1. Update `cairn/tui/__init__.py`:
   ```python
   """Full-screen Textual TUI for Cairn.

   Architecture:
   - app.py: Main coordinator
   - models.py: Data models and constants
   - widgets.py: Custom Textual widgets
   - state.py: Navigation and state management
   - events.py: Keyboard event routing
   - tables.py: DataTable operations
   - file_browser.py: File system browsing
   - editing.py: Feature editing
   - export.py: Export operations
   - rendering.py: UI layout
   - debug.py: Debug logging
   - edit_screens.py: Modal overlays
   """
   from cairn.tui.app import CairnTuiApp
   ```

2. Create `cairn/tui/ARCHITECTURE.md` with module diagram

### Verification
- [ ] All 188 private API usages still work (or are migrated)
- [ ] No compat shims are orphaned
- [ ] Documentation is complete
```

**Testing:**
- Run: `uv run pytest tests/ -v --tb=short`
- Verify: 100% test pass rate

---

## 📋 Dead Code & Cleanup Opportunities

### Identified Dead Code

| Location | Issue | Action |
|----------|-------|--------|
| `_agent_log` in app.py | Duplicate of edit_screens.py | Consolidate in Phase 2 |
| `_agent_log` in edit_screens.py | Duplicate of app.py | Consolidate in Phase 2 |
| `_AGENT_DEBUG_LOG_PATH` | Hardcoded path, duplicated | Consolidate in Phase 2 |
| Inline `_overlay_open` in `on_key()` | Duplicates class method `_overlay_open()` | Remove in Phase 6 |

### Cleanup Opportunities

| Item | Benefit | Phase |
|------|---------|-------|
| Consolidate debug logging | Remove ~50 duplicate lines | Phase 2 |
| Extract widget IDs to constants | Prevent test breakage | Phase 0 |
| Centralize directory listing | Remove 3 duplicate implementations | Phase 4 |
| Event routing centralization | Reduce on_key() from 400 to <50 lines | Phase 6 |

---

## 📚 New Documentation Required

1. **`cairn/tui/ARCHITECTURE.md`** - Module diagram, import rules, state ownership
2. **`docs/tui_testing.md`** - How to test TUI components in isolation
3. **Update `cairn/tui/__init__.py`** - Module docstrings explaining architecture
4. **`refactoring-plans/POST_REFACTOR_SUMMARY.md`** - What changed, migration notes

---

## ✅ Success Criteria

### Quantitative

| Metric | Target | Verification |
|--------|--------|--------------|
| `app.py` lines | < 500 | `wc -l cairn/tui/app.py` |
| Max file size | < 800 lines | `wc -l cairn/tui/*.py` |
| Test pass rate | 100% | `uv run pytest tests/` |
| Private API usages working | 188/188 | Run full test suite |
| Circular imports | 0 | Import sanity test |

### Qualitative

- [ ] Clear module boundaries
- [ ] Widget IDs are stable (documented constants)
- [ ] Explicit state ownership
- [ ] Import direction rules enforced
- [ ] New developer can understand architecture in < 1 day

---

## 📅 Timeline Summary

| Phase | Duration | Risk | Cumulative Days |
|-------|----------|------|-----------------|
| 0: Foundation | 0.5 days | 🟢 Very Low | 0.5 |
| 1: Widgets | 0.5 days | 🟢 Low | 1.0 |
| 2: Debug | 0.5 days | 🟢 Very Low | 1.5 |
| 3: Tables | 1 day | 🟡 Medium | 2.5 |
| 4: File Browser | 1 day | 🟡 Medium | 3.5 |
| 5: State | 1.5 days | 🟡 Medium | 5.0 |
| 6: Events | 1.5 days | 🔴 High | 6.5 |
| 7: Export | 1 day | 🟡 Medium | 7.5 |
| 8: Editing | 1.5 days | 🟡 Medium | 9.0 |
| 9: Rendering | 2 days | 🔴 High | 11.0 |
| 10: Cleanup | 1.5 days | 🟢 Low | **12.5 days** |

**Total Estimated Duration:** 12-15 working days

---

## 🔄 Rollback Strategy

Each phase can be rolled back independently:

1. **Git Strategy:** Create branch per phase
2. **Compatibility:** Keep delegator methods until phase 10
3. **Testing:** Run full suite after each phase
4. **Abort Criteria:** If >5% tests fail, investigate before continuing

---

**Document Version:** 1.2
**Last Updated:** January 2025
**Status:** In Progress (Phases 0-4 Complete)

---

## 📝 Progress Log

### Phase 0: Foundation & Constraints ✅ COMPLETED
**Date Completed:** January 2025

**What Was Done:**
- ✅ Created `cairn/tui/models.py` with:
  - `WidgetIds` class containing all widget ID constants
  - `STEPS` list and `STEP_LABELS` dict
  - `TuiModel` dataclass
  - `_VISIBLE_INPUT_EXTS` and `_PARSEABLE_INPUT_EXTS` constants
- ✅ Created `tests/test_import_sanity.py` to detect circular imports
- ✅ Updated `app.py` to import constants from `models.py`
- ✅ All tests pass, no regressions

**Notes:**
- Widget IDs are now stable constants, preventing test breakage
- Import sanity test successfully detects circular dependencies
- Models.py is a clean, dependency-free module (only core types)

---

### Phase 1: Extract Widgets ✅ COMPLETED
**Date Completed:** January 2025

**What Was Done:**
- ✅ Created `cairn/tui/widgets.py` with:
  - `FilteredFileTree`
  - `FilteredDirectoryTree`
  - `Stepper`
  - `StepAwareFooter`
- ✅ Added re-exports in `app.py` for backward compatibility
- ✅ All tests pass, no regressions

**Notes:**
- Eliminates circular import risk between `app.py` and `edit_screens.py`
- Widgets can now be imported independently
- Re-exports maintain backward compatibility for existing tests

---

### Phase 2: Extract Debug Utilities ✅ COMPLETED
**Date Completed:** January 2025

**What Was Done:**
- ✅ Created `cairn/tui/debug.py` with:
  - Unified `agent_log()` function (removed duplicate from app.py and edit_screens.py)
  - `DebugLogger` class encapsulating `_dbg` method logic
- ✅ Updated `app.py` to use `DebugLogger` instance
- ✅ Updated `edit_screens.py` to import `agent_log` from `debug.py`
- ✅ All tests pass, no regressions

**Notes:**
- Eliminated ~50 lines of duplicate code
- Debug logging is now centralized and easier to maintain
- `DebugLogger` handles thread-safe file operations and event storage
- `_dbg` method in app.py is now a thin wrapper delegating to DebugLogger

---

### Phase 3: Extract Table Operations ✅ COMPLETED
**Date Completed:** January 2025

**What Was Done:**
- ✅ Created `cairn/tui/tables.py` with `TableManager` class:
  - `cursor_row_key()` - Get row key at cursor position (static method)
  - `clear_rows()` - Clear all rows from DataTable (static method)
  - `color_chip()` - Create color chip widget for display
  - `resolved_waypoint_icon()` - Resolve OnX icon for waypoint
  - `resolved_waypoint_color()` - Resolve OnX color for waypoint
  - `_feature_row_key()` - Generate stable row key for features (helper)
  - `refresh_folder_table()` - Refresh folder table with selection state
  - `refresh_waypoints_table()` - Refresh waypoints table with filters
  - `refresh_routes_table()` - Refresh routes table with filters
- ✅ Updated `app.py` to initialize `TableManager` and delegate methods
- ✅ Kept compatibility delegator methods on App for backward compatibility
- ✅ All tests pass, no regressions

**Notes:**
- Extracted ~340 lines from app.py to tables.py
- Table operations are now isolated for better testability
- `_feature_row_key` helper was added (was referenced but not previously defined)
- All table refresh logic consolidated in TableManager
- Delegator methods maintain backward compatibility with existing code

**File Size Progress:**
- `app.py`: 3,638 lines (down from ~4,087 originally, ~3,839 after Phase 2)
- `tables.py`: 343 lines (new module)

---

### Phase 4: Extract File Browser ✅ COMPLETED
**Date Completed:** January 2025

**What Was Done:**
- ✅ Created `cairn/tui/file_browser.py` with `FileBrowserManager` class:
  - `get_initial_directory()` - Get initial directory respecting `default_path` config
  - `get_file_browser_dir()` / `set_file_browser_dir()` - File browser directory state
  - `get_save_browser_dir()` / `set_save_browser_dir()` - Save browser directory state
  - `refresh_file_browser()` - Populate Select_file file browser table
  - `file_browser_enter()` - Handle Enter on file browser
  - `refresh_export_dir_table()` - Populate export directory table
  - `export_dir_table_enter()` - Handle Enter on export directory table
  - `refresh_save_browser()` - Populate Save output directory browser
  - `save_browser_enter()` - Handle Enter on save browser
  - `use_tree_browser()` - Check if tree browser A/B test is enabled
- ✅ Updated `app.py` to initialize `FileBrowserManager` and delegate methods
- ✅ Added compatibility properties (`_file_browser_dir`, `_save_browser_dir`) for backward compatibility with tests
- ✅ Updated file browser initialization to use manager's `get_initial_directory()` method
- ✅ Updated `test_import_sanity.py` to include `file_browser` module
- ✅ All tests pass, no regressions

**Notes:**
- Extracted ~280 lines from app.py to file_browser.py
- Consolidated file/directory browsing logic into single manager
- `get_initial_directory()` method handles `default_path` config validation with proper error handling
- Compatibility properties maintain backward compatibility with existing tests (13 test usages)
- All file browser methods now delegate to FileBrowserManager
- Manager uses `TableManager` static methods for table operations (proper separation of concerns)

**Issues Identified:**
- None - implementation followed plan exactly

**Deviations from Plan:**
- None - implementation matched the plan specifications

**File Size Progress:**
- `app.py`: ~2,332 lines (down from ~3,638 after Phase 3)
- `file_browser.py`: 282 lines (new module)

**Verification:**
- ✅ Table mode file browser works (all 9 tests pass)
- ✅ Tree mode file browser works (tested via FilteredFileTree tests)
- ✅ Save browser works (tested via save flow tests)
- ✅ `default_path` config respected (handled in `get_initial_directory()`)
- ✅ Import sanity test passes (no circular imports)

**Remaining Work:**
- Phase 5: Extract State Management (IN PROGRESS - see below)
- Phase 6-10: Remaining phases as outlined in plan

---

### Phase 5: Extract State Management 🚧 IN PROGRESS
**Date Started:** January 2025

**What Was Done:**
- ✅ Created `cairn/tui/state.py` with `StateManager` class:
  - `goto()` - Navigate to a step (updates app.step reactive property)
  - `reset_focus_for_step()` - Set focus to appropriate widget for current step
  - `update_footer()` - Update step-aware footer
  - `infer_folder_selection()` - Infer folder selection from table cursor
  - `get_next_step_after_folder()` - Determine next step after Folder
  - `has_real_folders()` - Check if there are real folders
  - State variables: `_done_steps`, `_selected_route_keys`, `_selected_waypoint_keys`, `_selected_folders`
- ✅ Updated `app.py` to:
  - Import and initialize `StateManager`
  - Remove state variables from `__init__` (moved to StateManager)
  - Add compatibility properties for backward compatibility with tests
  - Delegate methods to StateManager (`_goto`, `_reset_focus_for_step`, `_update_footer`, etc.)
- ✅ Updated `test_import_sanity.py` to include `state` module
- ✅ Import sanity test passes

**Issues Identified:**
- ⚠️ Test failure in `test_tui_navigation_smoke.py::test_tui_routes_enter_advances_to_waypoints`
  - Issue: When `action_continue()` is called from Folder step, it's not advancing to Routes
  - Root cause: `_infer_folder_selection()` returns None when folder table doesn't exist or cursor isn't set
  - Attempted fix: Added auto-select logic for single folder case, but test still failing
  - Status: Needs further investigation - may be related to test setup or timing issue

**Deviations from Plan:**
- None - implementation followed plan specifications

**File Size Progress:**
- `app.py`: ~2,279 lines (down from ~2,332 after Phase 4)
- `state.py`: 151 lines (new module)

**Verification:**
- ✅ Import sanity test passes (no circular imports)
- ⚠️ Navigation smoke test failing (needs investigation)
- ⏳ Full test suite not yet run

**Next Steps:**
1. Debug test failure - investigate why folder selection isn't working in test
2. Run full test suite to identify any other regressions
3. Fix any issues found
4. Mark phase as complete once all tests pass
