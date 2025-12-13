"""
Preview and review system for Cairn.

This module provides dry-run reporting and interactive review functionality
to help users verify icon mappings before creating import files.
"""

from typing import Dict, List, Any, Optional
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from cairn.core.parser import ParsedData, ParsedFeature
from cairn.core.mapper import map_icon
from cairn.core.config import IconMappingConfig, get_all_onx_icons
from cairn.core.matcher import FuzzyIconMatcher

console = Console()


def generate_dry_run_report(parsed_data: ParsedData, config: IconMappingConfig) -> Dict[str, Any]:
    """
    Generate dry-run report without creating files.

    Args:
        parsed_data: Parsed GeoJSON data
        config: Icon mapping configuration

    Returns:
        Dictionary with report data
    """
    icon_counts = defaultdict(int)
    total_waypoints = 0
    total_tracks = 0
    total_shapes = 0
    files_to_create = []

    for folder_id, folder_data in parsed_data.folders.items():
        folder_name = folder_data["name"]

        # Count waypoints by icon
        for waypoint in folder_data["waypoints"]:
            icon = map_icon(waypoint.title, waypoint.description or "", waypoint.symbol, config)
            icon_counts[icon] += 1
            total_waypoints += 1

        # Count tracks and shapes
        total_tracks += len(folder_data["tracks"])
        total_shapes += len(folder_data["shapes"])

        # Determine what files would be created
        if folder_data["waypoints"]:
            files_to_create.append({
                "name": f"{folder_name}_Waypoints.gpx",
                "type": "GPX (Waypoints)",
                "count": len(folder_data["waypoints"])
            })

        if folder_data["tracks"]:
            files_to_create.append({
                "name": f"{folder_name}_Tracks.gpx",
                "type": "GPX (Tracks)",
                "count": len(folder_data["tracks"])
            })

        if folder_data["shapes"]:
            files_to_create.append({
                "name": f"{folder_name}_Shapes.kml",
                "type": "KML (Shapes)",
                "count": len(folder_data["shapes"])
            })

    return {
        "icon_counts": dict(sorted(icon_counts.items(), key=lambda x: x[1], reverse=True)),
        "unmapped": config.get_unmapped_report(),
        "total_waypoints": total_waypoints,
        "total_tracks": total_tracks,
        "total_shapes": total_shapes,
        "files_to_create": files_to_create
    }


def display_dry_run_report(report: Dict[str, Any]):
    """
    Display dry-run report to console.

    Args:
        report: Report data from generate_dry_run_report
    """
    console.print("\n")
    console.print(Panel.fit(
        "[bold yellow]DRY RUN REPORT[/]\n[dim]No files will be created[/]",
        border_style="yellow"
    ))

    # Summary statistics
    console.print(f"\n[bold]Summary:[/]")
    console.print(f"  Waypoints: [cyan]{report['total_waypoints']}[/]")
    console.print(f"  Tracks:    [cyan]{report['total_tracks']}[/]")
    console.print(f"  Shapes:    [cyan]{report['total_shapes']}[/]")

    # Icon distribution
    if report['icon_counts']:
        console.print(f"\n[bold]Waypoint Icon Distribution:[/]")

        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Icon", style="white")
        table.add_column("Count", justify="right", style="cyan")
        table.add_column("Percentage", justify="right", style="dim")

        total = report['total_waypoints']
        for icon, count in report['icon_counts'].items():
            percentage = (count / total * 100) if total > 0 else 0
            table.add_row(icon, str(count), f"{percentage:.1f}%")

        console.print(table)

    # Unmapped symbols
    if report['unmapped']:
        console.print(f"\n[yellow]⚠️  Unmapped Symbols:[/] [bold]{len(report['unmapped'])}[/]")

        table = Table(show_header=True, header_style="bold yellow", box=None)
        table.add_column("Symbol", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Example", style="dim")

        for symbol, info in report['unmapped'].items():
            example = info['examples'][0] if info['examples'] else "N/A"
            if len(example) > 40:
                example = example[:37] + "..."
            table.add_row(symbol, str(info['count']), example)

        console.print(table)

    # Files that would be created
    if report['files_to_create']:
        console.print(f"\n[bold]Would create {len(report['files_to_create'])} file(s):[/]")

        table = Table(show_header=True, header_style="bold green", box=None)
        table.add_column("Filename", style="yellow")
        table.add_column("Type", style="white")
        table.add_column("Items", justify="right", style="cyan")

        for file_info in report['files_to_create']:
            table.add_row(file_info['name'], file_info['type'], str(file_info['count']))

        console.print(table)

    console.print(f"\n[dim]Run without --dry-run to create files.[/]\n")


def interactive_review(parsed_data: ParsedData, config: IconMappingConfig) -> tuple[ParsedData, bool]:
    """
    Interactive review of icon mappings before export.

    Args:
        parsed_data: Parsed GeoJSON data
        config: Icon mapping configuration

    Returns:
        Tuple of (possibly modified ParsedData, whether changes were made)
    """
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]INTERACTIVE REVIEW[/]\n[dim]Review and adjust icon mappings[/]",
        border_style="cyan"
    ))

    # Group waypoints by icon across all folders
    icon_groups = defaultdict(list)

    for folder_id, folder_data in parsed_data.folders.items():
        for waypoint in folder_data["waypoints"]:
            icon = map_icon(waypoint.title, waypoint.description or "", waypoint.symbol, config)
            icon_groups[icon].append({
                "feature": waypoint,
                "folder_id": folder_id
            })

    changes_made = False

    # Review each icon group
    for icon, waypoints in sorted(icon_groups.items(), key=lambda x: len(x[1]), reverse=True):
        console.print(f"\n[bold cyan]{icon}[/] ([yellow]{len(waypoints)}[/] waypoints)")

        # Show sample waypoints
        sample_count = min(5, len(waypoints))
        for i, wp_info in enumerate(waypoints[:sample_count]):
            console.print(f"  • {wp_info['feature'].title}")

        if len(waypoints) > sample_count:
            console.print(f"  [dim]... and {len(waypoints) - sample_count} more[/]")

        # Prompt for action
        console.print("\n  [K]eep  [C]hange icon  [S]kip to next  [Q]uit review")

        try:
            action = Prompt.ask(
                "Action",
                choices=["k", "c", "s", "q"],
                default="k",
                show_choices=False
            ).lower()

            if action == "q":
                break
            elif action == "c":
                # Prompt for new icon
                new_icon = prompt_for_new_icon(icon)
                if new_icon and new_icon != icon:
                    # Update config for this mapping
                    # Find the most common symbol for this icon
                    symbols = [wp['feature'].symbol for wp in waypoints if wp['feature'].symbol]
                    if symbols:
                        most_common = max(set(symbols), key=symbols.count)
                        config_manager = __import__('config_manager').ConfigManager()
                        config_manager.add_mapping(most_common, new_icon)
                        console.print(f"[green]✓[/] Updated mapping: {most_common} → {new_icon}")
                        changes_made = True
            elif action == "s":
                continue

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Review cancelled[/]")
            break

    if changes_made:
        console.print("\n[green]✓[/] Changes saved to configuration")
        console.print("[dim]Reloading data with new mappings...[/]")

    return parsed_data, changes_made


def prompt_for_new_icon(current_icon: str) -> Optional[str]:
    """
    Prompt user to select a new icon.

    Args:
        current_icon: Current icon name

    Returns:
        New icon name or None if cancelled
    """
    console.print(f"\n[bold]Change from '[cyan]{current_icon}[/]' to:[/]")
    console.print("[dim]Enter icon name, or 'browse' to see all options, or Enter to cancel[/]")

    try:
        choice = Prompt.ask("New icon", default="")

        if not choice:
            return None

        if choice.lower() == "browse":
            # Show all icons
            from main import browse_all_icons
            return browse_all_icons()

        # Validate icon name
        valid_icons = get_all_onx_icons()
        if choice in valid_icons:
            return choice

        # Try fuzzy matching
        matcher = FuzzyIconMatcher(valid_icons)
        matches = matcher.find_best_matches(choice, top_n=3)

        if matches and matches[0][1] > 0.8:
            console.print(f"\n[yellow]Did you mean:[/]")
            for i, (icon, confidence) in enumerate(matches, 1):
                console.print(f"  {i}. {icon} ({int(confidence*100)}% match)")

            selection = Prompt.ask("Select", choices=[str(i) for i in range(1, len(matches)+1)] + [""], default="")

            if selection:
                return matches[int(selection)-1][0]
        else:
            console.print(f"[red]Invalid icon name:[/] {choice}")

        return None

    except (KeyboardInterrupt, EOFError):
        return None


def show_mapping_preview(parsed_data: ParsedData, config: IconMappingConfig):
    """
    Show a preview of how waypoints will be mapped.

    Args:
        parsed_data: Parsed GeoJSON data
        config: Icon mapping configuration
    """
    console.print("\n[bold]Icon Mapping Preview:[/]\n")

    # Sample waypoints from each folder
    for folder_id, folder_data in parsed_data.folders.items():
        if not folder_data["waypoints"]:
            continue

        folder_name = folder_data["name"]
        console.print(f"[cyan]📂 {folder_name}[/]")

        # Show up to 10 waypoints
        for waypoint in folder_data["waypoints"][:10]:
            icon = map_icon(waypoint.title, waypoint.description or "", waypoint.symbol, config)
            from mapper import get_icon_emoji
            emoji = get_icon_emoji(icon)
            console.print(f"  {emoji} {waypoint.title[:50]} → [yellow]{icon}[/]")

        if len(folder_data["waypoints"]) > 10:
            console.print(f"  [dim]... and {len(folder_data['waypoints']) - 10} more[/]")

        console.print()
