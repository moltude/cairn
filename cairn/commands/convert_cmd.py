"""Convert command for Cairn CLI."""

from pathlib import Path
from typing import Optional, List, Tuple
import typer
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
import time

from cairn.core.parser import parse_geojson, get_file_summary, ParsedData
from cairn.core.writers import write_gpx_waypoints, write_gpx_tracks, write_kml_shapes, generate_summary_file
from cairn.utils.utils import (
    chunk_data, sanitize_filename, format_file_size,
    ensure_output_dir, should_split
)
from cairn.core.mapper import get_icon_emoji, map_icon
from cairn.core.config import load_config, IconMappingConfig, get_use_icon_name_prefix, get_all_onx_icons, save_user_mapping
from cairn.core.matcher import FuzzyIconMatcher
from cairn.core.color_mapper import ColorMapper
from cairn.core.preview import generate_dry_run_report, display_dry_run_report, interactive_review

app = typer.Typer()
console = Console()

VERSION = "1.0.0"


def print_header():
    """Print the Cairn header."""
    console.print(Panel.fit(
        f"[bold yellow]CAIRN[/] v{VERSION}\n[italic]The CalTopo → onX Bridge[/]",
        border_style="yellow",
        padding=(0, 4)
    ))


def print_file_detection(input_file: Path):
    """Print file detection message."""
    console.print(f"\n[bold cyan]📂[/] Input file: [green]{input_file.name}[/]")
    file_size = input_file.stat().st_size
    console.print(f"[dim]   Size: {format_file_size(file_size)}[/]")


def parse_with_progress(input_file: Path) -> ParsedData:
    """Parse the GeoJSON file with a progress indicator."""
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        task1 = progress.add_task("[cyan]Parsing GeoJSON...", total=100)
        task2 = progress.add_task("[magenta]Mapping Icons...", total=100)

        # Simulate parsing progress
        for i in range(100):
            time.sleep(0.005)
            progress.update(task1, advance=1)
            if i > 30:
                progress.update(task2, advance=1.5)

        # Actually parse the file
        parsed_data = parse_geojson(input_file)

    return parsed_data


def display_folder_tree(parsed_data: ParsedData, config: IconMappingConfig):
    """Display a tree view of found folders and features."""
    summary = get_file_summary(parsed_data)

    console.print(f"\n[bold white]Found {summary['folder_count']} Folder(s):[/]")

    tree = Tree("📂 [bold]CalTopo Export[/]")

    for folder_id, folder_data in parsed_data.folders.items():
        folder_name = folder_data["name"]
        stats = parsed_data.get_folder_stats(folder_id)

        # Create folder node
        folder_label = f"📂 [cyan]{folder_name}[/]"
        if stats["total"] > 0:
            parts = []
            if stats["waypoints"] > 0:
                parts.append(f"📍 {stats['waypoints']} Waypoint{'s' if stats['waypoints'] != 1 else ''}")
            if stats["tracks"] > 0:
                parts.append(f"〰️  {stats['tracks']} Track{'s' if stats['tracks'] != 1 else ''}")
            if stats["shapes"] > 0:
                parts.append(f"⬠ {stats['shapes']} Shape{'s' if stats['shapes'] != 1 else ''}")
            folder_label += f" ({', '.join(parts)})"

        folder_node = tree.add(folder_label)

        # Show sample waypoints with mapped icons
        if folder_data["waypoints"]:
            sample_count = min(3, len(folder_data["waypoints"]))
            for waypoint in folder_data["waypoints"][:sample_count]:
                mapped = map_icon(waypoint.title, waypoint.description, waypoint.symbol, config)
                emoji = get_icon_emoji(mapped)
                folder_node.add(f"{emoji} [blue]{waypoint.title}[/] → [green]'{mapped}'[/]")

            if len(folder_data["waypoints"]) > sample_count:
                folder_node.add(f"[dim]... and {len(folder_data['waypoints']) - sample_count} more waypoints[/]")

        # Show tracks
        if folder_data["tracks"]:
            for track in folder_data["tracks"][:2]:
                folder_node.add(f"〰️  [blue]{track.title}[/] → [italic]GPX Track[/]")

            if len(folder_data["tracks"]) > 2:
                folder_node.add(f"[dim]... and {len(folder_data['tracks']) - 2} more tracks[/]")

        # Show shapes
        if folder_data["shapes"]:
            for shape in folder_data["shapes"][:2]:
                folder_node.add(f"⬠ [magenta]{shape.title}[/] → [italic]KML Polygon[/]")

            if len(folder_data["shapes"]) > 2:
                folder_node.add(f"[dim]... and {len(folder_data['shapes']) - 2} more shapes[/]")

    console.print(tree)
    console.print()


def prompt_for_icon_mapping(symbol: str, waypoint_title: str,
                           suggestions: List[Tuple[str, float]]) -> Optional[str]:
    """Prompt user to manually map an unmapped symbol."""
    console.print(f"\n[yellow]⚠️  Unmapped symbol:[/] [cyan]{symbol}[/]")
    console.print(f"[dim]   Example: {waypoint_title}[/]")
    console.print("\n[bold]Suggested onX icons:[/]")

    for i, (icon, confidence) in enumerate(suggestions, 1):
        confidence_pct = int(confidence * 100)
        emoji = get_icon_emoji(icon)
        console.print(f"  {i}. {emoji} {icon} [dim]({confidence_pct}% match)[/]")

    console.print(f"  {len(suggestions) + 1}. [dim]Browse all icons[/]")
    console.print(f"  {len(suggestions) + 2}. [dim]Skip (use default 'Location')[/]")

    try:
        choice = Prompt.ask(
            "\nSelect an option",
            choices=[str(i) for i in range(1, len(suggestions) + 3)],
            default=str(len(suggestions) + 2)
        )

        choice_num = int(choice)

        if choice_num <= len(suggestions):
            return suggestions[choice_num - 1][0]
        elif choice_num == len(suggestions) + 1:
            from cairn.commands.icon_cmd import browse_all_icons
            return browse_all_icons()
        else:
            return None
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Skipping...[/]")
        return None


def handle_unmapped_symbols(config: IconMappingConfig, interactive: bool = True) -> bool:
    """Handle unmapped symbols with interactive prompts or reporting."""
    unmapped = config.get_unmapped_report()

    if not unmapped or len(unmapped) == 0:
        return False

    if not interactive:
        return False

    console.print("\n[yellow]⚠️  Found unmapped symbols. Let's map them![/]")
    console.print("[dim]You can map these now or skip to use the default 'Location' icon.[/]\n")

    matcher = FuzzyIconMatcher(get_all_onx_icons())
    mappings_added = False

    for symbol, info in unmapped.items():
        suggestions = matcher.find_best_matches(symbol, top_n=3)
        selected_icon = prompt_for_icon_mapping(symbol, info['examples'][0], suggestions)

        if selected_icon:
            save_user_mapping(symbol, selected_icon)
            console.print(f"[green]✓[/] Mapped '[cyan]{symbol}[/]' → '[green]{selected_icon}[/]'")
            mappings_added = True
        else:
            console.print(f"[dim]Skipped '{symbol}' (will use 'Location')[/]")

    return mappings_added


def process_and_write_files(parsed_data: ParsedData, output_dir: Path) -> list:
    """Process folders and write output files."""
    output_files = []

    for folder_id, folder_data in parsed_data.folders.items():
        folder_name = folder_data["name"]
        safe_name = sanitize_filename(folder_name)

        waypoints = folder_data["waypoints"]
        tracks = folder_data["tracks"]
        shapes = folder_data["shapes"]

        # Handle waypoints
        if waypoints:
            total_waypoints = len(waypoints)

            if total_waypoints > 2500:
                console.print(f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_waypoints} waypoints)...")
                console.print(f"   [yellow]⚠️  Exceeds onX limit (3,000).[/]")
                console.print(f"   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(waypoints, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Waypoints_Part{i}"
                    output_path = output_dir / f"{part_name}.gpx"
                    file_size = write_gpx_waypoints(chunk, output_path, f"{folder_name} - Part {i}")
                    output_files.append((f"{part_name}.gpx", "GPX (Waypoints)", len(chunk), file_size))
                    console.print(f"       ├── 📄 [green]{part_name}.gpx[/] ({len(chunk)} items)")

                    if get_use_icon_name_prefix():
                        summary_path = generate_summary_file(chunk, output_path, f"{folder_name} - Part {i}")
                        summary_size = summary_path.stat().st_size
                        output_files.append((summary_path.name, "Summary (Text)", len(chunk), summary_size))
                        console.print(f"       └── 📋 [blue]{summary_path.name}[/] (Icon reference)")
            else:
                output_path = output_dir / f"{safe_name}_Waypoints.gpx"
                file_size = write_gpx_waypoints(waypoints, output_path, folder_name)
                output_files.append((f"{safe_name}_Waypoints.gpx", "GPX (Waypoints)", len(waypoints), file_size))

                if get_use_icon_name_prefix():
                    summary_path = generate_summary_file(waypoints, output_path, folder_name)
                    summary_size = summary_path.stat().st_size
                    output_files.append((summary_path.name, "Summary (Text)", len(waypoints), summary_size))

        # Handle tracks
        if tracks:
            total_tracks = len(tracks)

            if total_tracks > 2500:
                console.print(f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_tracks} tracks)...")
                console.print(f"   [yellow]⚠️  Exceeds onX limit (3,000).[/]")
                console.print(f"   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(tracks, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Tracks_Part{i}"
                    output_path = output_dir / f"{part_name}.gpx"
                    file_size = write_gpx_tracks(chunk, output_path, f"{folder_name} - Part {i}")
                    output_files.append((f"{part_name}.gpx", "GPX (Tracks)", len(chunk), file_size))
                    console.print(f"       ├── 📄 [green]{part_name}.gpx[/] ({len(chunk)} items)")
            else:
                output_path = output_dir / f"{safe_name}_Tracks.gpx"
                file_size = write_gpx_tracks(tracks, output_path, folder_name)
                output_files.append((f"{safe_name}_Tracks.gpx", "GPX (Tracks)", len(tracks), file_size))

        # Handle shapes (KML)
        if shapes:
            total_shapes = len(shapes)

            if total_shapes > 2500:
                console.print(f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_shapes} shapes)...")
                console.print(f"   [yellow]⚠️  Exceeds onX limit (3,000).[/]")
                console.print(f"   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(shapes, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Shapes_Part{i}"
                    output_path = output_dir / f"{part_name}.kml"
                    file_size = write_kml_shapes(chunk, output_path, f"{folder_name} - Part {i}")
                    output_files.append((f"{part_name}.kml", "KML (Shapes)", len(chunk), file_size))
                    console.print(f"       ├── 📄 [green]{part_name}.kml[/] ({len(chunk)} items)")
            else:
                output_path = output_dir / f"{safe_name}_Shapes.kml"
                file_size = write_kml_shapes(shapes, output_path, folder_name)
                output_files.append((f"{safe_name}_Shapes.kml", "KML (Shapes)", len(shapes), file_size))

    return output_files


def display_manifest(output_files: list):
    """Display a table of created files."""
    table = Table(title="Export Manifest", border_style="green")
    table.add_column("Filename", style="yellow")
    table.add_column("Format", style="white")
    table.add_column("Items", justify="right")
    table.add_column("Size", justify="right")

    for filename, format_type, item_count, file_size in output_files:
        table.add_row(
            filename,
            format_type,
            str(item_count),
            format_file_size(file_size)
        )

    console.print(table)


def display_unmapped_symbols(config: IconMappingConfig):
    """Display a report of unmapped CalTopo symbols found."""
    if not config.has_unmapped_symbols():
        return

    unmapped_report = config.get_unmapped_report()

    console.print(f"\n[yellow]⚠️  Found {len(unmapped_report)} unmapped CalTopo symbol(s):[/]")

    table = Table(border_style="yellow")
    table.add_column("Symbol", style="cyan")
    table.add_column("Count", justify="right", style="white")
    table.add_column("Example Waypoint", style="dim")

    for symbol, stats in sorted(unmapped_report.items(), key=lambda x: x[1]["count"], reverse=True):
        example = stats["examples"][0] if stats["examples"] else "N/A"
        table.add_row(
            symbol,
            str(stats["count"]),
            example[:40] + "..." if len(example) > 40 else example
        )

    console.print(table)
    console.print("\n[dim]💡 Add these to cairn_config.json to map them to onX icons[/]")
    console.print("[dim]   Run 'cairn config --export' to create a template[/]")


def convert(
    input_file: Path = typer.Argument(..., help="CalTopo GeoJSON export file"),
    output: Optional[Path] = typer.Option(
        "./onx_ready",
        "--output", "-o",
        help="Output directory for converted files"
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Custom icon mapping configuration file"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview conversion without creating files"
    ),
    review: bool = typer.Option(
        False,
        "--review",
        help="Interactive review of icon mappings before conversion"
    )
):
    """
    Convert a CalTopo GeoJSON export to onX Backcountry format.

    This tool will:
    - Parse your CalTopo GeoJSON export
    - Map CalTopo symbols and keywords to onX Backcountry icons
    - Split large datasets to respect onX's 3,000 item limit
    - Generate GPX files for waypoints and tracks
    - Generate KML files for shapes/polygons
    - Report unmapped symbols for future configuration
    """
    # Load configuration
    config = load_config(config_file)

    # Print header
    print_header()

    # Validate input file
    if not input_file.exists():
        console.print(f"\n[bold red]❌ Error:[/] File not found: {input_file}")
        raise typer.Exit(1)

    # Print file detection
    print_file_detection(input_file)

    # Parse with progress
    try:
        parsed_data = parse_with_progress(input_file)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error parsing file:[/] {e}")
        raise typer.Exit(1)

    # Display folder tree (with config for icon mapping)
    display_folder_tree(parsed_data, config)

    # DRY RUN MODE: Generate and display report without creating files
    if dry_run:
        report = generate_dry_run_report(parsed_data, config)
        display_dry_run_report(report)

        # Still show unmapped symbols for awareness
        if config.has_unmapped_symbols():
            display_unmapped_symbols(config)

        return

    # REVIEW MODE: Interactive review before conversion
    if review:
        parsed_data, changes_made = interactive_review(parsed_data, config)

        if changes_made:
            # Reload config with new mappings
            console.print("\n[green]✓[/] Reloading configuration with new mappings...\n")
            config = load_config(config_file)
            # Re-parse to apply new mappings
            parsed_data = parse_geojson(input_file)

    # Handle unmapped symbols interactively (if not in review mode)
    if not review and config.has_unmapped_symbols():
        mappings_added = handle_unmapped_symbols(config, interactive=True)

        if mappings_added:
            # Reload config with new mappings
            console.print("\n[green]✓[/] Reloading configuration with new mappings...\n")
            config = load_config(config_file)

            # Re-parse to apply new mappings
            parsed_data = parse_geojson(input_file)

    # Ensure output directory exists
    output_dir = ensure_output_dir(output)

    # Process and write files
    console.print(f"[bold white]Writing files to[/] [underline]{output_dir}[/]...\n")
    output_files = process_and_write_files(parsed_data, output_dir)

    # Display manifest
    console.print()
    display_manifest(output_files)

    # Display any remaining unmapped symbols report
    display_unmapped_symbols(config)

    # Success footer
    console.print(f"\n[bold green]✔ SUCCESS[/] {len(output_files)} file(s) written to [underline]{output_dir}[/]")
    console.print("[dim]Next: Drag these files into onX Web Map → Import[/]\n")
