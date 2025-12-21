# TUI Architecture

## Module Diagram

```
                    ┌─────────────────────────────────────┐
                    │             app.py                  │
                    │   (CairnTuiApp - main orchestrator) │
                    └───────────────────┬─────────────────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         │                              │                              │
         ▼                              ▼                              ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│    state.py     │          │   tables.py     │          │ file_browser.py │
│ (StateManager)  │          │ (TableManager)  │          │(FileBrowserMgr) │
└─────────────────┘          └─────────────────┘          └─────────────────┘
         │                              │                              │
         │                              │                              │
         ▼                              ▼                              ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│   events.py     │          │   export.py     │          │   editing.py    │
│ (EventRouter)   │          │ (ExportManager) │          │ (EditManager)   │
└─────────────────┘          └─────────────────┘          └─────────────────┘
         │                              │                              │
         └──────────────────────────────┴──────────────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────┐
                    │            models.py                │
                    │   (TuiModel, STEPS, constants)      │
                    └─────────────────────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────┐
                    │          rendering.py               │
                    │   (pure helper functions)           │
                    └─────────────────────────────────────┘

    ┌─────────────────┐          ┌─────────────────┐
    │   widgets.py    │          │ edit_screens.py │
    │ (custom widgets)│          │ (modal screens) │
    └─────────────────┘          └─────────────────┘
```

## Module Responsibilities

| Module | Responsibility | Textual-Dependent |
|--------|---------------|-------------------|
| `app.py` | Main App class, widget orchestration, reactive properties | Yes |
| `models.py` | Data models, constants, type definitions | No |
| `state.py` | Workflow state, step transitions, selection tracking | No |
| `tables.py` | DataTable creation, population, cursor management | Yes |
| `file_browser.py` | File/directory tree widgets | Yes |
| `events.py` | Keyboard/mouse event dispatching | Yes |
| `export.py` | Export orchestration, manifest generation | Partial |
| `editing.py` | Inline editing, overlay management | Yes |
| `rendering.py` | Sidebar text, shortcuts, filename helpers | No |
| `widgets.py` | Custom Textual widgets (Stepper, FilteredFileTree) | Yes |
| `edit_screens.py` | Modal/overlay Screen subclasses | Yes |
| `debug.py` | Debug logging utilities | No |

## Import Direction Rules

To avoid circular imports, follow these rules:

1. **models.py** is foundational - imported by all others, imports nothing from TUI
2. **rendering.py** imports only from `cairn.core` and `cairn.utils`
3. **Managers** (state, tables, etc.) import from models.py and pure helpers
4. **app.py** imports from all managers and widgets
5. **widgets.py** can import from models.py but NOT from app.py

```
models.py ◀─── state.py, tables.py, events.py, export.py, editing.py
     ▲
     │
rendering.py (pure helpers, no TUI imports)
     │
     ▼
cairn.core, cairn.utils
```

## State Ownership

| State | Owner | Notes |
|-------|-------|-------|
| `step` (current workflow step) | `app.py` (reactive) | Drives re-rendering |
| `_done_steps` | `StateManager` | Delegated from app |
| `_selected_route_keys` | `StateManager` | Delegated from app |
| `_selected_waypoint_keys` | `StateManager` | Delegated from app |
| `_selected_folders` | `StateManager` | Delegated from app |
| `model` (TuiModel) | `app.py` | Shared with managers |
| `_file_browser_dir` | `FileBrowserManager` | Delegated from app |
| `_save_browser_dir` | `FileBrowserManager` | Delegated from app |

## Compatibility Layer

For backward compatibility with tests (188+ usages), `app.py` maintains delegator
properties that forward to the appropriate manager:

```python
@property
def _done_steps(self) -> set:
    return self.state._done_steps

@_done_steps.setter
def _done_steps(self, value: set) -> None:
    self.state._done_steps = value
```

These are intentionally preserved for stability. Future cleanup may consolidate
access patterns, but this is deferred to avoid breaking tests.

## Testing Strategy

- **Unit tests** for pure functions in `rendering.py`, `models.py`
- **Integration tests** using the TUI harness (`tests/tui_harness.py`)
- **E2E tests** with `pytest-textual-snapshot` for visual regression

Test fixtures available:

```python
@pytest.fixture
def tui_state(tui_app):
    return tui_app.state

@pytest.fixture
def tui_tables(tui_app):
    return tui_app.tables
```
