"""Import sanity test to detect circular imports between TUI modules."""

def test_no_circular_imports():
    """Detect circular imports between TUI modules."""
    # Test that all TUI modules can be imported without circular dependencies
    import cairn.tui.models
    import cairn.tui.widgets
    import cairn.tui.debug
    import cairn.tui.tables
    import cairn.tui.file_browser
    import cairn.tui.state
    import cairn.tui.app
    import cairn.tui.edit_screens
    # Add new modules as they're created (Phase 6+):
    # import cairn.tui.events
    # etc.

    # If we get here, no circular import was detected
    assert True
