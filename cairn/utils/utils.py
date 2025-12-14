"""
Utility functions for Cairn: chunking, HTML stripping, sorting, and file helpers.

This module provides helper functions for handling onX import limits,
cleaning data, natural sorting, and managing file operations.
"""

from typing import List, Iterator, Any, Union
import re
from pathlib import Path


def natural_sort_key(text: str) -> List[Union[str, int]]:
    """
    Generate a sort key for natural/human sorting.

    Natural sorting handles mixed alphanumeric strings correctly,
    sorting "Item 2" before "Item 10" (unlike lexicographic sorting).

    Handles:
    - Zero-padded numbers: 01, 02, ... 10, 11
    - Non-padded numbers: 1, 2, 3, ... 10, 11
    - Alphabetical: A, B, C, ... Z
    - Mixed: "Section 2", "Section 10"

    Args:
        text: The string to generate a sort key for

    Returns:
        A list of string and integer parts for comparison

    Examples:
        >>> natural_sort_key("Item 2")
        ['item ', 2, '']
        >>> natural_sort_key("Item 10")
        ['item ', 10, '']
        >>> sorted(["Item 10", "Item 2", "Item 1"], key=natural_sort_key)
        ['Item 1', 'Item 2', 'Item 10']
        >>> sorted(["02 - B", "01 - A", "10 - C"], key=natural_sort_key)
        ['01 - A', '02 - B', '10 - C']
    """
    if not text:
        return ['']

    def convert(part: str) -> Union[str, int]:
        """Convert numeric strings to int, lowercase text otherwise."""
        return int(part) if part.isdigit() else part.lower()

    # Split on digit boundaries, keeping the digits
    # e.g., "Item 10" -> ['Item ', '10', '']
    parts = re.split(r'(\d+)', text)

    return [convert(part) for part in parts]


def chunk_data(items: List[Any], limit: int = 2500) -> Iterator[List[Any]]:
    """
    Split a list into chunks to respect onX import limits.

    onX Backcountry crashes with >3000 items, so we use a conservative
    limit of 2500 by default.

    Args:
        items: List of items to chunk
        limit: Maximum items per chunk (default: 2500)

    Yields:
        Lists of items, each with at most 'limit' items

    Example:
        >>> data = list(range(5000))
        >>> chunks = list(chunk_data(data, limit=2500))
        >>> len(chunks)
        2
        >>> len(chunks[0])
        2500
        >>> len(chunks[1])
        2500
    """
    for i in range(0, len(items), limit):
        yield items[i:i + limit]


def strip_html(text: str) -> str:
    """
    Remove HTML tags from text.

    CalTopo exports often contain HTML formatting in descriptions,
    but onX Backcountry expects plain text.

    Args:
        text: Text potentially containing HTML tags

    Returns:
        Plain text with HTML tags removed

    Example:
        >>> strip_html("<b>Camp</b> at <i>lake</i>")
        'Camp at lake'
    """
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode common HTML entities
    html_entities = {
        '&nbsp;': ' ',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&apos;': "'",
    }

    for entity, char in html_entities.items():
        text = text.replace(entity, char)

    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def sanitize_filename(name: str) -> str:
    """
    Clean a string to be safe for use as a filename.

    Removes or replaces characters that are problematic in filenames
    across different operating systems.

    Args:
        name: The original name/title

    Returns:
        A filesystem-safe filename

    Example:
        >>> sanitize_filename("Lost Horse Canyon / Trail")
        'Lost_Horse_Canyon_Trail'
    """
    if not name:
        return "Untitled"

    # Replace problematic characters with underscores
    name = re.sub(r'[<>:"/\\|?*]', '_', name)

    # Replace spaces with underscores
    name = name.replace(' ', '_')

    # Remove multiple consecutive underscores
    name = re.sub(r'_+', '_', name)

    # Remove leading/trailing underscores
    name = name.strip('_')

    # Limit length (255 is common filesystem limit, leave room for extensions)
    if len(name) > 200:
        name = name[:200]

    return name or "Untitled"


def estimate_file_size(content: str) -> int:
    """
    Estimate the file size in bytes for a string content.

    Args:
        content: The file content as a string

    Returns:
        Estimated size in bytes
    """
    return len(content.encode('utf-8'))


def format_file_size(size_bytes: int) -> str:
    """
    Format a file size in bytes to a human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "2.4 MB", "156 KB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def ensure_output_dir(output_path: Path) -> Path:
    """
    Ensure the output directory exists, creating it if necessary.

    Args:
        output_path: Path to the output directory

    Returns:
        The resolved absolute path
    """
    output_path = Path(output_path).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def get_geometry_type_name(geometry_type: str) -> str:
    """
    Get a friendly name for a GeoJSON geometry type.

    Args:
        geometry_type: GeoJSON geometry type (e.g., "Point", "LineString")

    Returns:
        Friendly name (e.g., "Waypoint", "Track")
    """
    type_map = {
        "Point": "Waypoint",
        "LineString": "Track",
        "Polygon": "Shape",
        "MultiPoint": "Waypoints",
        "MultiLineString": "Tracks",
        "MultiPolygon": "Shapes",
    }
    return type_map.get(geometry_type, geometry_type)


def should_split(item_count: int, estimated_size: int,
                 max_items: int = 3000, max_size: int = 4 * 1024 * 1024) -> bool:
    """
    Determine if a dataset should be split based on onX limits.

    Args:
        item_count: Number of items in the dataset
        estimated_size: Estimated file size in bytes
        max_items: Maximum items allowed (default: 3000)
        max_size: Maximum file size in bytes (default: 4MB)

    Returns:
        True if the dataset exceeds limits and should be split
    """
    return item_count > max_items or estimated_size > max_size
