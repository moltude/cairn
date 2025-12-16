"""
Comprehensive tests for waypoint deduplication logic.

Tests cover:
- Identical waypoint deduplication
- Near-duplicate detection within coordinate tolerance
- Duplicate handling across folders
- Preserving first occurrence metadata
- Empty name handling
- Folder statistics in reports
"""

import pytest
from cairn.core.dedup import (
    dedupe_waypoints,
    apply_waypoint_dedup,
    waypoint_dedup_key,
    DedupKey,
)
from cairn.model import MapDocument, Waypoint, Style, Folder


def test_identical_waypoints_deduped():
    """Test that waypoints with identical names and locations are deduplicated."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Camp",
        lon=-120.5,
        lat=45.5,
        notes="First camp",
        style=Style(OnX_icon="camp", OnX_color_rgba="rgba(255,0,0,1)"),
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Camp",
        lon=-120.5,
        lat=45.5,
        notes="",
        style=Style(),
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    assert len(kept) == 1
    assert len(dropped) == 1
    assert kept[0].id == "wp1"  # First one with more metadata
    assert dropped[0].id == "wp2"
    assert report.dropped_count == 1
    assert report.group_count == 1


def test_near_duplicates_within_tolerance():
    """Test that waypoints within ~0.1m tolerance are considered duplicates."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Trailhead",
        lon=-120.123456,
        lat=45.654321,
        notes="Main parking",
        style=Style(OnX_icon="trailhead"),
    )
    # Slightly different coordinates (within 6 decimal tolerance)
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Trailhead",
        lon=-120.123456,  # Same when rounded to 6 decimals
        lat=45.654321,
        notes="",
        style=Style(),
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    assert len(kept) == 1
    assert len(dropped) == 1
    assert kept[0].id == "wp1"  # Prefer one with metadata
    assert "wp2" in kept[0].source_ids  # Source ID merged


def test_near_duplicates_outside_tolerance():
    """Test that waypoints outside tolerance are NOT deduplicated."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Camp",
        lon=-120.123456,
        lat=45.654321,
    )
    # Differs at 6th decimal place (different when rounded to 6 decimals)
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Camp",
        lon=-120.123457,  # Different after rounding
        lat=45.654321,
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    # Should NOT be deduplicated
    assert len(kept) == 2
    assert len(dropped) == 0
    assert report.dropped_count == 0


def test_duplicates_across_folders():
    """Test that duplicates are found regardless of folder assignment."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder_a",
        name="Summit",
        lon=-120.5,
        lat=45.5,
        style=Style(OnX_icon="peak"),
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder_b",  # Different folder
        name="Summit",
        lon=-120.5,
        lat=45.5,
        style=Style(),
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    assert len(kept) == 1
    assert len(dropped) == 1
    assert kept[0].id == "wp1"  # Has OnX_icon


def test_dedup_preserves_first_occurrence():
    """Test that the 'best' waypoint is kept based on metadata quality."""
    # wp1: No metadata
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Water Source",
        lon=-120.0,
        lat=45.0,
        notes="",
        style=Style(),
    )
    # wp2: Has icon but no color
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Water Source",
        lon=-120.0,
        lat=45.0,
        notes="",
        style=Style(OnX_icon="water"),
    )
    # wp3: Has both icon and color (best)
    wp3 = Waypoint(
        id="wp3",
        folder_id="folder1",
        name="Water Source",
        lon=-120.0,
        lat=45.0,
        notes="",
        style=Style(OnX_icon="water", OnX_color_rgba="rgba(0,0,255,1)"),
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2, wp3])

    assert len(kept) == 1
    assert kept[0].id == "wp3"  # Best metadata wins
    assert len(dropped) == 2
    assert "wp1" in kept[0].source_ids
    assert "wp2" in kept[0].source_ids


def test_dedup_prefers_longer_notes():
    """Test that waypoints with longer notes are preferred."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Camp",
        lon=-120.0,
        lat=45.0,
        notes="",
        style=Style(OnX_icon="camp"),
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Camp",
        lon=-120.0,
        lat=45.0,
        notes="This is a great camping spot with water nearby and flat ground.",
        style=Style(OnX_icon="camp"),
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    assert len(kept) == 1
    assert kept[0].id == "wp2"  # Longer notes wins
    assert len(kept[0].notes) > 0


def test_empty_names_not_deduped():
    """Test that waypoints with empty names are not deduplicated."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="",
        lon=-120.0,
        lat=45.0,
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="",
        lon=-120.0,
        lat=45.0,
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    # Empty names should create same key and be deduplicated
    assert len(kept) == 1
    assert len(dropped) == 1


def test_dedup_with_conflicting_icons():
    """Test that conflicting icons are tracked in the report."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Camp",
        lon=-120.0,
        lat=45.0,
        style=Style(OnX_icon="camp"),
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Camp",
        lon=-120.0,
        lat=45.0,
        style=Style(OnX_icon="campground"),  # Different icon
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    assert len(kept) == 1
    assert report.group_count == 1
    group = report.groups[0]
    assert "OnX_icons" in group.conflicts
    assert set(group.conflicts["OnX_icons"]) == {"camp", "campground"}


def test_dedup_with_conflicting_colors():
    """Test that conflicting colors are tracked in the report."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Peak",
        lon=-120.0,
        lat=45.0,
        style=Style(OnX_icon="peak", OnX_color_rgba="rgba(255,0,0,1)"),
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Peak",
        lon=-120.0,
        lat=45.0,
        style=Style(OnX_icon="peak", OnX_color_rgba="rgba(0,255,0,1)"),  # Different color
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    assert len(kept) == 1
    assert report.group_count == 1
    group = report.groups[0]
    assert "OnX_colors" in group.conflicts


def test_dedup_conflicts_stored_in_waypoint_extra():
    """Test that conflicts are stored in the kept waypoint's extra field."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Camp",
        lon=-120.0,
        lat=45.0,
        style=Style(OnX_icon="camp", OnX_color_rgba="rgba(255,0,0,1)"),
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Camp",
        lon=-120.0,
        lat=45.0,
        style=Style(OnX_icon="campground", OnX_color_rgba="rgba(0,255,0,1)"),
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    assert "dedup_conflicts" in kept[0].extra
    conflicts = kept[0].extra["dedup_conflicts"]
    assert "OnX_icons" in conflicts
    assert "OnX_colors" in conflicts


def test_apply_waypoint_dedup_modifies_document():
    """Test that apply_waypoint_dedup modifies the MapDocument in-place."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Camp",
        lon=-120.0,
        lat=45.0,
        style=Style(OnX_icon="camp"),
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Camp",
        lon=-120.0,
        lat=45.0,
        style=Style(),
    )

    doc = MapDocument(items=[wp1, wp2])
    assert len(doc.waypoints()) == 2

    report = apply_waypoint_dedup(doc)

    assert len(doc.waypoints()) == 1
    assert report.dropped_count == 1
    assert doc.waypoints()[0].id == "wp1"


def test_waypoint_dedup_key_generation():
    """Test that waypoint_dedup_key generates correct keys."""
    wp = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Test Camp",
        lon=-120.123456789,
        lat=45.987654321,
    )

    key = waypoint_dedup_key(wp)

    assert isinstance(key, DedupKey)
    assert key.lat6 == round(45.987654321, 6)
    assert key.lon6 == round(-120.123456789, 6)
    # Name should be normalized (lowercase, collapsed whitespace)
    assert key.name_key == "test camp"


def test_dedup_with_special_characters_in_name():
    """Test deduplication with special characters in names."""
    wp1 = Waypoint(
        id="wp1",
        folder_id="folder1",
        name="Joe's Camp",
        lon=-120.0,
        lat=45.0,
    )
    wp2 = Waypoint(
        id="wp2",
        folder_id="folder1",
        name="Joe's  Camp",  # Extra space, but should normalize to same
        lon=-120.0,
        lat=45.0,
    )

    kept, dropped, report = dedupe_waypoints([wp1, wp2])

    # After normalization (lowercase + whitespace collapse), these should match
    assert len(kept) == 1
    assert len(dropped) == 1


def test_dedup_multiple_groups():
    """Test deduplication with multiple distinct duplicate groups."""
    waypoints = [
        # Group 1: Camp duplicates
        Waypoint(id="wp1", folder_id="f1", name="Camp A", lon=-120.0, lat=45.0),
        Waypoint(id="wp2", folder_id="f1", name="Camp A", lon=-120.0, lat=45.0),
        # Group 2: Peak duplicates
        Waypoint(id="wp3", folder_id="f1", name="Peak B", lon=-121.0, lat=46.0),
        Waypoint(id="wp4", folder_id="f1", name="Peak B", lon=-121.0, lat=46.0),
        # Group 3: No duplicates
        Waypoint(id="wp5", folder_id="f1", name="Unique", lon=-122.0, lat=47.0),
    ]

    kept, dropped, report = dedupe_waypoints(waypoints)

    assert len(kept) == 3  # One from each group
    assert len(dropped) == 2  # Two dropped
    assert report.group_count == 2  # Two dedup groups (not counting single items)
    assert report.dropped_count == 2


def test_dedup_preserves_order():
    """Test that deduplication preserves the original order of kept waypoints."""
    waypoints = [
        Waypoint(id="wp1", folder_id="f1", name="A", lon=-120.0, lat=45.0),
        Waypoint(id="wp2", folder_id="f1", name="B", lon=-121.0, lat=46.0),
        Waypoint(id="wp3", folder_id="f1", name="B", lon=-121.0, lat=46.0),  # Duplicate
        Waypoint(id="wp4", folder_id="f1", name="C", lon=-122.0, lat=47.0),
    ]

    kept, dropped, report = dedupe_waypoints(waypoints)

    # Check order is preserved
    kept_ids = [wp.id for wp in kept]
    assert kept_ids == ["wp1", "wp2", "wp4"]


def test_apply_dedup_preserves_non_waypoint_items():
    """Test that apply_waypoint_dedup doesn't affect tracks/shapes."""
    from cairn.model import Track

    wp1 = Waypoint(id="wp1", folder_id="f1", name="Camp", lon=-120.0, lat=45.0)
    wp2 = Waypoint(id="wp2", folder_id="f1", name="Camp", lon=-120.0, lat=45.0)
    track = Track(
        id="t1",
        folder_id="f1",
        name="Trail",
        points=[(-120.0, 45.0, None, None), (-120.1, 45.1, None, None)],
    )

    doc = MapDocument(items=[wp1, track, wp2])

    report = apply_waypoint_dedup(doc)

    assert len(doc.waypoints()) == 1
    assert len(doc.tracks()) == 1  # Track unchanged
    assert report.dropped_count == 1


def test_dedup_no_duplicates():
    """Test deduplication when there are no duplicates."""
    waypoints = [
        Waypoint(id="wp1", folder_id="f1", name="A", lon=-120.0, lat=45.0),
        Waypoint(id="wp2", folder_id="f1", name="B", lon=-121.0, lat=46.0),
        Waypoint(id="wp3", folder_id="f1", name="C", lon=-122.0, lat=47.0),
    ]

    kept, dropped, report = dedupe_waypoints(waypoints)

    assert len(kept) == 3
    assert len(dropped) == 0
    assert report.dropped_count == 0
    assert report.group_count == 0


def test_dedup_empty_list():
    """Test deduplication with empty waypoint list."""
    kept, dropped, report = dedupe_waypoints([])

    assert len(kept) == 0
    assert len(dropped) == 0
    assert report.dropped_count == 0
    assert report.group_count == 0
