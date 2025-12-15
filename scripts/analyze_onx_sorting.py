#!/usr/bin/env python3
"""
Analyze OnX sorting behavior by comparing original GPX with exported GPX and UI display order.

This script helps identify how OnX re-sorts waypoints for display vs storage.
"""

from pathlib import Path
import xml.etree.ElementTree as ET
from rich.console import Console
from rich.table import Table

console = Console()


def read_gpx_waypoints(gpx_path: Path):
    """Read waypoints from GPX file with their icons."""
    tree = ET.parse(gpx_path)
    root = tree.getroot()
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
    OnX_ns = {'OnX': 'https://wwww.OnXmaps.com/'}

    waypoints = []
    for wpt in root.findall('.//gpx:wpt', ns):
        name_elem = wpt.find('gpx:name', ns)
        icon_elem = wpt.find('.//OnX:icon', OnX_ns)

        if name_elem is not None and name_elem.text:
            name = name_elem.text.strip()
            icon = icon_elem.text if icon_elem is not None else 'Unknown'
            waypoints.append((name, icon))

    return waypoints


def analyze_sorting(original_gpx: Path, exported_gpx: Path, ui_order: list):
    """
    Analyze sorting differences between original, exported, and UI display.

    Args:
        original_gpx: Path to original GPX file we created
        exported_gpx: Path to GPX file exported from OnX
        ui_order: List of waypoint names in order shown in OnX UI (from screenshot)
    """
    console.print("\n[bold cyan]OnX Sorting Analysis[/]\n")

    # Read waypoints from both GPX files
    original_waypoints = read_gpx_waypoints(original_gpx)
    exported_waypoints = read_gpx_waypoints(exported_gpx)

    # Extract just names for comparison
    original_names = [name for name, _ in original_waypoints]
    exported_names = [name for name, _ in exported_waypoints]

    # Create a mapping of name to icon
    name_to_icon = {name: icon for name, icon in original_waypoints}

    console.print(f"[green]✓[/] Original GPX: {len(original_names)} waypoints")
    console.print(f"[green]✓[/] Exported GPX: {len(exported_names)} waypoints")
    console.print(f"[green]✓[/] UI Display: {len(ui_order)} waypoints\n")

    # Compare original vs exported (should match)
    if original_names == exported_names:
        console.print("[bold green]✓ STORAGE ORDER MATCHES[/]")
        console.print("   OnX preserves GPX element order in storage.\n")
    else:
        console.print("[bold yellow]⚠ STORAGE ORDER DIFFERS[/]")
        console.print("   OnX may have modified the order during import.\n")

    # Compare original vs UI display
    console.print("[bold]UI Display Order Analysis:[/]\n")

    # Group by icon type
    icon_groups = {}
    for name in original_names:
        icon = name_to_icon.get(name, 'Unknown')
        if icon not in icon_groups:
            icon_groups[icon] = []
        icon_groups[icon].append(name)

    console.print("[cyan]Waypoints grouped by icon type:[/]")
    for icon, names in sorted(icon_groups.items()):
        console.print(f"  {icon}: {len(names)} waypoints")
        for name in names[:3]:
            console.print(f"    - {name}")
        if len(names) > 3:
            console.print(f"    ... and {len(names) - 3} more")

    # Analyze UI order
    console.print(f"\n[cyan]UI Display Order (from screenshot):[/]")
    for i, name in enumerate(ui_order, 1):
        icon = name_to_icon.get(name, 'Unknown')
        console.print(f"  {i:2}. [{icon:12}] {name}")

    # Check if UI groups by icon
    console.print(f"\n[cyan]UI Order Analysis:[/]")

    # Group UI order by icon
    ui_icon_groups = {}
    for name in ui_order:
        icon = name_to_icon.get(name, 'Unknown')
        if icon not in ui_icon_groups:
            ui_icon_groups[icon] = []
        ui_icon_groups[icon].append(name)

    console.print("UI groups waypoints by icon type:")
    for icon, names in ui_icon_groups.items():
        console.print(f"  {icon}: {len(names)} waypoints")

    # Check sorting within icon groups
    console.print("\n[cyan]Sorting within icon groups:[/]")
    for icon, names in ui_icon_groups.items():
        console.print(f"\n  {icon} group:")
        for name in names:
            console.print(f"    - {name}")

        # Check if sorted alphabetically
        sorted_names = sorted(names)
        if names == sorted_names:
            console.print(f"    → [green]Sorted alphabetically[/]")
        else:
            console.print(f"    → [yellow]Not sorted alphabetically[/]")
            console.print(f"    → Expected alphabetical: {sorted_names[:3]}...")


if __name__ == "__main__":
    # Based on screenshot analysis
    ui_order = [
        "Deadfall",  # Hazard (4-5 entries)
        "Deadfall",
        "Deadfall",
        "Deadfall",
        "Deadfall",
        "#06 Sunlight Mile 63.3",  # Location
        "#07 Crandall Mile 70.4",
        "#08 Forest Lake Mile 78.3",
        "#09 Honey Trail Mile 85.4",
        "#10 Hunting Camp Mile 92.8",
        "CONICAL PASS CUTOFF 12:45 AM",
        "Dead fall",  # Hazard (singular)
        "#0 Start Line",  # Location
        "#01 Porcupine Mile 6.1",
        # Note: Screenshot may not show all waypoints
    ]

    original_gpx = Path("onx_ready/Crazy_Mountain_100M_Waypoints.gpx")
    exported_gpx = Path("/Users/scott/downloads/OnX-markups-12132025 (1).gpx")

    if not original_gpx.exists():
        console.print(f"[red]Error: {original_gpx} not found[/]")
        exit(1)

    if not exported_gpx.exists():
        console.print(f"[red]Error: {exported_gpx} not found[/]")
        exit(1)

    analyze_sorting(original_gpx, exported_gpx, ui_order)
