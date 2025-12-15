"""
Debug utilities for verifying GPX file order and comparing with expected order.

This module provides tools to help debug OnX sorting behavior by comparing
the order of waypoints in GPX files with expected order.
"""

from typing import List, Tuple, Optional
from pathlib import Path
import xml.etree.ElementTree as ET
from rich.console import Console
from rich.table import Table

console = Console()


def read_gpx_waypoint_order(gpx_path: Path, *, console: Optional[Console] = None) -> List[str]:
    """
    Read waypoint names from a GPX file in the order they appear.

    Args:
        gpx_path: Path to the GPX file

    Returns:
        List of waypoint names in GPX file order
    """
    c = console or globals()["console"]
    try:
        tree = ET.parse(gpx_path)
        root = tree.getroot()

        # Handle namespace
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}

        waypoint_names = []
        for wpt in root.findall('.//gpx:wpt', ns):
            name_elem = wpt.find('gpx:name', ns)
            if name_elem is not None and name_elem.text:
                waypoint_names.append(name_elem.text)

        return waypoint_names
    except Exception as e:
        c.print(f"[red]Error reading GPX file: {e}[/]")
        return []


def compare_orders(expected: List[str], actual: List[str],
                   max_display: int = 20,
                   *,
                   console: Optional[Console] = None) -> Tuple[bool, List[Tuple[int, str, Optional[str]]]]:
    """
    Compare expected order with actual order and identify differences.

    Args:
        expected: List of waypoint names in expected order
        actual: List of waypoint names in actual order
        max_display: Maximum number of differences to report

    Returns:
        Tuple of (is_match: bool, differences: List of (index, expected_name, actual_name))
    """
    differences = []
    is_match = True

    # Check if lengths match
    if len(expected) != len(actual):
        is_match = False
        c = console or globals()["console"]
        c.print(f"[yellow]Warning: Length mismatch - Expected {len(expected)}, got {len(actual)}[/]")

    # Compare up to the minimum length
    max_len = min(len(expected), len(actual), max_display)

    for i in range(max_len):
        expected_name = expected[i] if i < len(expected) else None
        actual_name = actual[i] if i < len(actual) else None

        if expected_name != actual_name:
            is_match = False
            differences.append((i + 1, expected_name, actual_name))

    return is_match, differences


def display_order_comparison(expected: List[str], actual: List[str],
                             title: str = "Order Comparison",
                             *,
                             console: Optional[Console] = None) -> None:
    """
    Display a formatted comparison of expected vs actual waypoint order.

    Args:
        expected: List of waypoint names in expected order
        actual: List of waypoint names in actual order
        title: Title for the comparison table
    """
    c = console or globals()["console"]
    is_match, differences = compare_orders(expected, actual, console=c)

    if is_match:
        c.print(f"[green]✓[/] {title}: Orders match!")
        return

    c.print(f"\n[bold]{title}[/]")
    c.print(f"[yellow]⚠️  Orders differ - {len(differences)} difference(s) found[/]\n")

    # Create comparison table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Position", justify="right", style="dim")
    table.add_column("Expected", style="green")
    table.add_column("Actual", style="red")
    table.add_column("Match", justify="center")

    max_len = max(len(expected), len(actual))
    max_display = min(max_len, 30)  # Show up to 30 items

    for i in range(max_display):
        expected_name = expected[i] if i < len(expected) else "[dim]N/A[/]"
        actual_name = actual[i] if i < len(actual) else "[dim]N/A[/]"

        match_symbol = "✓" if expected_name == actual_name else "✗"
        match_style = "green" if expected_name == actual_name else "red"

        table.add_row(
            str(i + 1),
            str(expected_name),
            str(actual_name),
            f"[{match_style}]{match_symbol}[/]"
        )

    c.print(table)

    if max_len > max_display:
        c.print(f"\n[dim]... showing first {max_display} of {max_len} waypoints[/]")


def analyze_gpx_order(gpx_path: Path, expected_order: Optional[List[str]] = None, *, console: Optional[Console] = None) -> None:
    """
    Analyze and display the order of waypoints in a GPX file.

    Args:
        gpx_path: Path to the GPX file to analyze
        expected_order: Optional list of expected waypoint names in order
    """
    c = console or globals()["console"]
    c.print(f"\n[bold]Analyzing GPX file:[/] [cyan]{gpx_path.name}[/]")

    actual_order = read_gpx_waypoint_order(gpx_path, console=c)

    if not actual_order:
        c.print("[red]No waypoints found in GPX file[/]")
        return

    c.print(f"[green]Found {len(actual_order)} waypoint(s)[/]\n")

    # Display actual order
    c.print("[bold]Waypoint order in GPX file:[/]")
    for i, name in enumerate(actual_order[:20], 1):
        c.print(f"  {i}. {name}")

    if len(actual_order) > 20:
        c.print(f"  [dim]... and {len(actual_order) - 20} more waypoints[/]")

    # Compare with expected order if provided
    if expected_order:
        c.print()
        display_order_comparison(
            expected_order,
            actual_order,
            f"Expected vs Actual Order ({gpx_path.name})",
            console=c,
        )


def find_order_mismatches(gpx_path: Path, expected_order: List[str]) -> List[int]:
    """
    Find positions where GPX order doesn't match expected order.

    Args:
        gpx_path: Path to the GPX file
        expected_order: List of expected waypoint names in order

    Returns:
        List of position indices (1-based) where order differs
    """
    actual_order = read_gpx_waypoint_order(gpx_path)
    _, differences = compare_orders(expected_order, actual_order)

    return [pos for pos, _, _ in differences]
