"""Full-screen Textual TUI for Cairn (opt-in).

Architecture Overview
---------------------

The TUI is structured as a set of specialized modules, each with a clear responsibility:

- **app.py**: Main CairnTuiApp class. Orchestrates widgets, composes the UI,
  and delegates to managers. Contains Textual-specific code (reactive
  properties, widget queries, focus management).

- **models.py**: Data models and constants (STEPS, TuiModel, etc.). Pure Python
  dataclasses with no Textual dependencies.

- **state.py**: StateManager handles workflow state, step transitions, and
  selection tracking. Owns `_done_steps`, selection sets, and mode flags.

- **tables.py**: TableManager handles DataTable creation, population, cursor
  management, and row operations. Centralizes all table logic.

- **file_browser.py**: FileBrowserManager handles file/directory tree widgets
  for input selection and export target selection.

- **events.py**: EventRouter handles keyboard/mouse event dispatching and
  routing based on current step and context.

- **export.py**: ExportManager handles export orchestration, manifest generation,
  and file writing.

- **editing.py**: EditManager handles inline editing, overlays, and item
  modification flows.

- **rendering.py**: Pure helper functions for sidebar text, shortcuts formatting,
  and filename suggestions. No Textual dependencies.

- **widgets.py**: Custom Textual widgets (FilteredFileTree, Stepper, etc.).

- **edit_screens.py**: Modal/overlay Screen subclasses for editing flows.

- **debug.py**: Debug logging utilities.

Import Direction Rules
----------------------

To avoid circular imports:

1. models.py is foundational - imported by all others, imports nothing from TUI
2. Pure helpers (rendering.py) import only from core/utils
3. Managers import from models.py and pure helpers
4. app.py imports from all managers and widgets
5. Widgets can import from models.py but not from app.py

See ARCHITECTURE.md for the full module diagram.
"""
