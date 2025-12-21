"""Tests for folder name validation."""

from cairn.tui.edit_screens import validate_folder_name


def test_validate_folder_name_accepts_valid_names():
    """Test that valid folder names are accepted."""
    valid_names = [
        "maps",
        "data",
        "output_2024",
        "My Folder",
        "test-folder",
        "folder_with_underscores",
    ]

    for name in valid_names:
        is_valid, error = validate_folder_name(name)
        assert is_valid, f"'{name}' should be valid but got error: {error}"
        assert error is None, f"'{name}' should have no error message"


def test_validate_folder_name_rejects_empty():
    """Test that empty names are rejected."""
    invalid_names = ["", "   ", "\t", "\n"]

    for name in invalid_names:
        is_valid, error = validate_folder_name(name)
        assert not is_valid, f"'{repr(name)}' should be invalid"
        assert "empty" in error.lower(), f"Error should mention 'empty': {error}"


def test_validate_folder_name_rejects_path_traversal():
    """Test that path traversal attempts are rejected."""
    # Note: ".." and "..hidden" are caught by the leading dot check
    # "folder/../etc" is caught by the ".." check
    # All are rejected, which is what matters for security
    invalid_names = [
        "..",
        "../etc",
        "folder/../etc",
        "..hidden",
    ]

    for name in invalid_names:
        is_valid, error = validate_folder_name(name)
        assert not is_valid, f"'{name}' should be invalid (path traversal)"
        # Error should mention either ".." or "dot" (both indicate path traversal risk)
        assert (".." in error or "dot" in error.lower()), f"Error should mention '..' or 'dot': {error}"


def test_validate_folder_name_rejects_path_separators():
    """Test that path separators are rejected."""
    invalid_names = [
        "folder/subfolder",
        "folder\\subfolder",
        "/etc/passwd",
        "C:\\Windows",
    ]

    for name in invalid_names:
        is_valid, error = validate_folder_name(name)
        assert not is_valid, f"'{name}' should be invalid (path separator)"
        assert ("/" in error or "\\" in error), f"Error should mention path separator: {error}"


def test_validate_folder_name_rejects_invalid_characters():
    """Test that invalid characters are rejected."""
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*']

    for char in invalid_chars:
        name = f"folder{char}name"
        is_valid, error = validate_folder_name(name)
        assert not is_valid, f"'{name}' should be invalid (contains {char})"
        assert char in error, f"Error should mention '{char}': {error}"


def test_validate_folder_name_rejects_reserved_windows_names():
    """Test that Windows reserved names are rejected."""
    reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1", "con", "prn"]

    for name in reserved_names:
        is_valid, error = validate_folder_name(name)
        assert not is_valid, f"'{name}' should be invalid (Windows reserved)"
        assert "reserved" in error.lower(), f"Error should mention 'reserved': {error}"


def test_validate_folder_name_rejects_leading_trailing_dots_spaces():
    """Test that names with leading/trailing dots or spaces are rejected."""
    invalid_names = [
        ".hidden",
        "folder.",
        " folder",
        "folder ",
        "  folder  ",
    ]

    for name in invalid_names:
        is_valid, error = validate_folder_name(name)
        assert not is_valid, f"'{repr(name)}' should be invalid (leading/trailing)"
        # Error should mention spaces or dots
        assert any(word in error.lower() for word in ["space", "dot", "start", "end"]), \
            f"Error should mention leading/trailing issue: {error}"
