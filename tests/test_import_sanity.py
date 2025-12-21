"""Import sanity test to detect circular imports between TUI modules."""

def test_no_circular_imports():
    """Detect circular imports between TUI modules."""
    # Test that all TUI modules can be imported without circular dependencies
    # Order matters - import lower-level modules first
    import cairn.tui.models
    import cairn.tui.widgets
    import cairn.tui.debug
    import cairn.tui.tables
    import cairn.tui.file_browser
    import cairn.tui.state
    # Phase 6-8 modules
    import cairn.tui.events
    import cairn.tui.export
    import cairn.tui.editing
    # Higher-level modules
    import cairn.tui.app
    import cairn.tui.edit_screens

    # If we get here, no circular import was detected
    assert True
