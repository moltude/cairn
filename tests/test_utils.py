"""Unit tests for cairn.utils.utils module."""

import pytest
from pathlib import Path
from cairn.utils.utils import (
    chunk_data,
    strip_html,
    sanitize_filename,
    estimate_file_size,
    format_file_size,
    get_geometry_type_name,
    should_split,
)


class TestChunkData:
    """Tests for chunk_data function."""

    def test_empty_list(self):
        """Empty list yields nothing."""
        result = list(chunk_data([]))
        assert result == []

    def test_list_smaller_than_limit(self):
        """List smaller than limit yields single chunk."""
        items = [1, 2, 3, 4, 5]
        result = list(chunk_data(items, limit=10))
        assert len(result) == 1
        assert result[0] == [1, 2, 3, 4, 5]

    def test_list_equal_to_limit(self):
        """List equal to limit yields single chunk."""
        items = list(range(10))
        result = list(chunk_data(items, limit=10))
        assert len(result) == 1
        assert len(result[0]) == 10

    def test_list_larger_than_limit(self):
        """List larger than limit yields multiple chunks."""
        items = list(range(25))
        result = list(chunk_data(items, limit=10))
        assert len(result) == 3
        assert len(result[0]) == 10
        assert len(result[1]) == 10
        assert len(result[2]) == 5

    def test_default_limit(self):
        """Default limit is 2500."""
        items = list(range(5000))
        result = list(chunk_data(items))
        assert len(result) == 2
        assert len(result[0]) == 2500
        assert len(result[1]) == 2500


class TestStripHtml:
    """Tests for strip_html function."""

    def test_empty_string(self):
        """Empty string returns empty."""
        assert strip_html("") == ""

    def test_none_input(self):
        """None input returns empty string."""
        assert strip_html(None) == ""

    def test_plain_text(self):
        """Plain text returned unchanged."""
        assert strip_html("Hello World") == "Hello World"

    def test_simple_tags(self):
        """Simple HTML tags are removed."""
        assert strip_html("<b>Bold</b>") == "Bold"
        assert strip_html("<i>Italic</i>") == "Italic"

    def test_nested_tags(self):
        """Nested tags are removed."""
        assert strip_html("<div><p><b>Text</b></p></div>") == "Text"

    def test_html_entities(self):
        """HTML entities are decoded."""
        assert strip_html("&amp;") == "&"
        assert strip_html("&lt;") == "<"
        assert strip_html("&gt;") == ">"
        assert strip_html("&quot;") == '"'
        # &nbsp; becomes space which gets stripped when alone
        assert strip_html("Hello&nbsp;World") == "Hello World"

    def test_mixed_content(self):
        """Mixed HTML and text processed correctly."""
        result = strip_html("<b>Camp</b> at <i>lake</i>")
        assert result == "Camp at lake"

    def test_whitespace_cleanup(self):
        """Multiple whitespace collapsed."""
        result = strip_html("  Hello    World  ")
        assert result == "Hello World"


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_empty_string(self):
        """Empty string returns 'Untitled'."""
        assert sanitize_filename("") == "Untitled"

    def test_none_input(self):
        """None input returns 'Untitled'."""
        assert sanitize_filename(None) == "Untitled"

    def test_simple_name(self):
        """Simple name with spaces converted."""
        assert sanitize_filename("My File") == "My_File"

    def test_special_characters(self):
        """Special characters replaced."""
        result = sanitize_filename("File/Name:Test?Query")
        assert "/" not in result
        assert ":" not in result
        assert "?" not in result

    def test_multiple_underscores_collapsed(self):
        """Multiple underscores collapsed to one."""
        result = sanitize_filename("File___Name")
        assert "___" not in result

    def test_leading_trailing_underscores_removed(self):
        """Leading/trailing underscores stripped."""
        result = sanitize_filename("_FileName_")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_long_name_truncated(self):
        """Names over 200 chars are truncated."""
        long_name = "A" * 250
        result = sanitize_filename(long_name)
        assert len(result) <= 200


class TestEstimateFileSize:
    """Tests for estimate_file_size function."""

    def test_empty_string(self):
        """Empty string is 0 bytes."""
        assert estimate_file_size("") == 0

    def test_ascii_string(self):
        """ASCII string size is character count."""
        assert estimate_file_size("hello") == 5

    def test_unicode_string(self):
        """Unicode characters take more bytes."""
        # Emoji takes 4 bytes in UTF-8
        result = estimate_file_size("🏔️")
        assert result > 1


class TestFormatFileSize:
    """Tests for format_file_size function."""

    def test_bytes(self):
        """Small sizes in bytes."""
        assert format_file_size(100) == "100 B"
        assert format_file_size(0) == "0 B"

    def test_kilobytes(self):
        """Sizes in kilobytes."""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(2048) == "2.0 KB"

    def test_megabytes(self):
        """Sizes in megabytes."""
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(2 * 1024 * 1024) == "2.0 MB"


class TestGetGeometryTypeName:
    """Tests for get_geometry_type_name function."""

    def test_point(self):
        assert get_geometry_type_name("Point") == "Waypoint"

    def test_linestring(self):
        assert get_geometry_type_name("LineString") == "Track"

    def test_polygon(self):
        assert get_geometry_type_name("Polygon") == "Shape"

    def test_unknown(self):
        """Unknown types returned as-is."""
        assert get_geometry_type_name("Unknown") == "Unknown"


class TestShouldSplit:
    """Tests for should_split function."""

    def test_below_limits(self):
        """Below limits should not split."""
        assert should_split(100, 1000) is False

    def test_exceeds_item_limit(self):
        """Exceeds item limit should split."""
        assert should_split(5000, 1000) is True

    def test_exceeds_size_limit(self):
        """Exceeds size limit should split."""
        assert should_split(100, 5 * 1024 * 1024) is True

    def test_custom_limits(self):
        """Custom limits respected."""
        assert should_split(50, 100, max_items=25) is True
        assert should_split(10, 100, max_items=25) is False
