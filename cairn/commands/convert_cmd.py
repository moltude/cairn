"""Convert command for Cairn CLI."""

from pathlib import Path
from typing import Optional, List, Tuple
import typer
import logging
from enum import Enum
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
import time

from cairn.core.parser import parse_geojson, get_file_summary, ParsedData
from cairn.core.writers import write_gpx_waypoints, write_gpx_tracks, write_kml_shapes, generate_summary_file, verify_gpx_waypoint_order, get_name_changes, clear_name_changes
from cairn.utils.utils import (
    chunk_data, sanitize_filename, format_file_size,
    ensure_output_dir, should_split, natural_sort_key
)
from cairn.core.mapper import get_icon_emoji, map_icon
from cairn.core.config import load_config, IconMappingConfig, get_all_onx_icons, save_user_mapping
from cairn.core.matcher import FuzzyIconMatcher
from cairn.core.color_mapper import ColorMapper
from cairn.core.preview import generate_dry_run_report, display_dry_run_report, interactive_review, preview_sorted_order

# New bidirectional adapters (onX → CalTopo)
from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.core.dedup import apply_waypoint_dedup
from cairn.core.shape_dedup import apply_shape_dedup
from cairn.io.caltopo_geojson import write_caltopo_geojson
from cairn.core.trace import TraceWriter
from cairn.core.diagnostics import document_inventory, dedup_inventory
from cairn.core.shape_dedup_summary import write_shape_dedup_summary

app = typer.Typer()
console = Console()

# Set up logger for debug output
logger = logging.getLogger(__name__)

VERSION = "1.0.0"


class FromFormat(str, Enum):
    caltopo_geojson = "caltopo_geojson"
    onx_gpx = "onx_gpx"


class ToFormat(str, Enum):
    onx = "onx"
    caltopo_geojson = "caltopo_geojson"


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
                emoji = config.get_icon_emoji(mapped)
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


def process_and_write_files(
    parsed_data: ParsedData,
    output_dir: Path,
    sort: bool = True,
    skip_confirmation: bool = False,
    config: IconMappingConfig = None
) -> list:
    """
    Process folders and write output files.

    Args:
        parsed_data: Parsed GeoJSON data
        output_dir: Output directory path
        sort: If True, sort items using natural sort order
        skip_confirmation: If True, skip the order confirmation prompt
        config: Icon mapping config for waypoint previews

    Returns:
        List of (filename, format, count, size) tuples for the manifest
    """
    output_files = []

    # Clear name changes tracker before processing
    clear_name_changes()

    for folder_id, folder_data in parsed_data.folders.items():
        folder_name = folder_data["name"]
        safe_name = sanitize_filename(folder_name)

        waypoints = folder_data["waypoints"]
        tracks = folder_data["tracks"]
        shapes = folder_data["shapes"]

        # Handle waypoints
        if waypoints:
            total_waypoints = len(waypoints)

            # Sort waypoints for preview if sorting is enabled
            if sort:
                sorted_waypoints = sorted(waypoints, key=lambda f: natural_sort_key(f.title))
            else:
                sorted_waypoints = waypoints

            # Show preview and get confirmation
            if not preview_sorted_order(sorted_waypoints, "waypoints", folder_name, skip_confirmation, config):
                console.print("[yellow]Export cancelled by user.[/]")
                return output_files

            # Write in sorted order - onX displays items in the same order as the GPX file
            write_order_waypoints = sorted_waypoints

            # Debug: Log order before write
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[DEBUG] Waypoint order before write ({folder_name}):")
                for i, wp in enumerate(write_order_waypoints[:20], 1):
                    logger.debug(f"  {i}. {wp.title}")
                if len(write_order_waypoints) > 20:
                    logger.debug(f"  ... and {len(write_order_waypoints) - 20} more waypoints")

            if total_waypoints > 2500:
                console.print(f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_waypoints} waypoints)...")
                console.print(f"   [yellow]⚠️  Exceeds onX limit (3,000).[/]")
                console.print(f"   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(write_order_waypoints, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Waypoints_Part{i}"
                    output_path = output_dir / f"{part_name}.gpx"
                    # Pass sort=False since we already sorted and reversed
                    file_size = write_gpx_waypoints(
                        chunk,
                        output_path,
                        f"{folder_name} - Part {i}",
                        sort=False,
                        config=config,
                    )
                    output_files.append((f"{part_name}.gpx", "GPX (Waypoints)", len(chunk), file_size))
                    console.print(f"       ├── 📄 [green]{part_name}.gpx[/] ({len(chunk)} items)")

                    if config and config.use_icon_name_prefix:
                        summary_path = generate_summary_file(chunk, output_path, f"{folder_name} - Part {i}", config=config)
                        summary_size = summary_path.stat().st_size
                        output_files.append((summary_path.name, "Summary (Text)", len(chunk), summary_size))
                        console.print(f"       └── 📋 [blue]{summary_path.name}[/] (Icon reference)")
            else:
                output_path = output_dir / f"{safe_name}_Waypoints.gpx"
                # Pass sort=False since we already sorted and reversed
                file_size = write_gpx_waypoints(
                    write_order_waypoints,
                    output_path,
                    folder_name,
                    sort=False,
                    config=config,
                )

                # Debug: Verify order after write
                if logger.isEnabledFor(logging.DEBUG):
                    gpx_order = verify_gpx_waypoint_order(output_path)
                    if gpx_order:
                        logger.debug(f"[DEBUG] Waypoint order in GPX file ({output_path.name}):")
                        for i, name in enumerate(gpx_order, 1):
                            logger.debug(f"  {i}. {name}")
                        # Compare with expected order
                        expected_names = [wp.title for wp in write_order_waypoints[:len(gpx_order)]]
                        if expected_names != gpx_order:
                            logger.warning("[DEBUG] WARNING: GPX order differs from expected order!")
                            logger.debug("Expected order:")
                            for i, name in enumerate(expected_names, 1):
                                logger.debug(f"  {i}. {name}")

                output_files.append((f"{safe_name}_Waypoints.gpx", "GPX (Waypoints)", len(write_order_waypoints), file_size))

                if config and config.use_icon_name_prefix:
                    summary_path = generate_summary_file(sorted_waypoints, output_path, folder_name, config=config)
                    summary_size = summary_path.stat().st_size
                    output_files.append((summary_path.name, "Summary (Text)", len(sorted_waypoints), summary_size))

        # Handle tracks
        if tracks:
            total_tracks = len(tracks)

            # Sort tracks for preview if sorting is enabled
            if sort:
                sorted_tracks = sorted(tracks, key=lambda f: natural_sort_key(f.title))
            else:
                sorted_tracks = tracks

            # Show preview and get confirmation
            if not preview_sorted_order(sorted_tracks, "tracks", folder_name, skip_confirmation):
                console.print("[yellow]Export cancelled by user.[/]")
                return output_files

            # Write in sorted order - onX displays items in the same order as the GPX file
            write_order_tracks = sorted_tracks

            if total_tracks > 2500:
                console.print(f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_tracks} tracks)...")
                console.print(f"   [yellow]⚠️  Exceeds onX limit (3,000).[/]")
                console.print(f"   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(write_order_tracks, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Tracks_Part{i}"
                    output_path = output_dir / f"{part_name}.gpx"
                    # Pass sort=False since we already sorted and reversed
                    file_size = write_gpx_tracks(chunk, output_path, f"{folder_name} - Part {i}", sort=False)
                    output_files.append((f"{part_name}.gpx", "GPX (Tracks)", len(chunk), file_size))
                    console.print(f"       ├── 📄 [green]{part_name}.gpx[/] ({len(chunk)} items)")
            else:
                output_path = output_dir / f"{safe_name}_Tracks.gpx"
                # Pass sort=False since we already sorted and reversed
                file_size = write_gpx_tracks(write_order_tracks, output_path, folder_name, sort=False)
                output_files.append((f"{safe_name}_Tracks.gpx", "GPX (Tracks)", len(write_order_tracks), file_size))

        # Handle shapes (KML)
        if shapes:
            total_shapes = len(shapes)

            # Sort shapes if sorting is enabled
            if sort:
                sorted_shapes = sorted(shapes, key=lambda f: natural_sort_key(f.title))
            else:
                sorted_shapes = shapes

            # Show preview and get confirmation for shapes
            if not preview_sorted_order(sorted_shapes, "shapes", folder_name, skip_confirmation):
                console.print("[yellow]Export cancelled by user.[/]")
                return output_files

            # Write in sorted order - onX displays items in the same order as the file
            write_order_shapes = sorted_shapes

            if total_shapes > 2500:
                console.print(f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_shapes} shapes)...")
                console.print(f"   [yellow]⚠️  Exceeds onX limit (3,000).[/]")
                console.print(f"   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(write_order_shapes, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Shapes_Part{i}"
                    output_path = output_dir / f"{part_name}.kml"
                    file_size = write_kml_shapes(chunk, output_path, f"{folder_name} - Part {i}")
                    output_files.append((f"{part_name}.kml", "KML (Shapes)", len(chunk), file_size))
                    console.print(f"       ├── 📄 [green]{part_name}.kml[/] ({len(chunk)} items)")
            else:
                output_path = output_dir / f"{safe_name}_Shapes.kml"
                file_size = write_kml_shapes(write_order_shapes, output_path, folder_name)
                output_files.append((f"{safe_name}_Shapes.kml", "KML (Shapes)", len(write_order_shapes), file_size))

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
    console.print("\n[dim]💡 Add these to cairn_config.yaml to map them to onX icons[/]")
    console.print("[dim]   Run 'cairn config --export' to create a template[/]")


def display_name_sanitization_warnings():
    """Display warnings about name sanitization for OnX sorting compatibility."""
    name_changes = get_name_changes()

    total_changes = len(name_changes.get('waypoints', [])) + len(name_changes.get('tracks', []))

    if total_changes == 0:
        return

    console.print(f"\n[yellow]⚠️  Name Sanitization Applied[/]")
    console.print("─" * 70)
    console.print("To improve OnX sorting compatibility, the following characters")
    console.print("were removed from names: [cyan]! @ # $ % ^ * &[/]")
    console.print()

    waypoint_changes = name_changes.get('waypoints', [])
    track_changes = name_changes.get('tracks', [])

    if waypoint_changes:
        console.print(f"[bold]Waypoints Modified:[/] [cyan]{len(waypoint_changes)}[/]")
    if track_changes:
        console.print(f"[bold]Tracks Modified:[/] [cyan]{len(track_changes)}[/]")

    console.print()
    console.print("[bold]Sample Changes:[/]")

    # Show up to 10 examples from each type
    max_examples = 10
    examples_shown = 0

    if waypoint_changes:
        console.print("\n[cyan]Waypoints:[/]")
        for original, sanitized in waypoint_changes[:max_examples]:
            console.print(f"  [dim]{original[:35]:<35}[/] → [green]{sanitized[:35]}[/]")
            examples_shown += 1
        if len(waypoint_changes) > max_examples:
            console.print(f"  [dim]... and {len(waypoint_changes) - max_examples} more waypoint changes[/]")

    if track_changes:
        console.print("\n[cyan]Tracks:[/]")
        for original, sanitized in track_changes[:max_examples]:
            console.print(f"  [dim]{original[:35]:<35}[/] → [green]{sanitized[:35]}[/]")
            examples_shown += 1
        if len(track_changes) > max_examples:
            console.print(f"  [dim]... and {len(track_changes) - max_examples} more track changes[/]")

    console.print()
    console.print("[dim]Note: Natural sort order is preserved. This is a test feature.[/]")
    console.print("─" * 70)


def convert(
    input_file: Path = typer.Argument(..., help="Input file (default: CalTopo GeoJSON)"),
    from_format: FromFormat = typer.Option(
        FromFormat.caltopo_geojson,
        "--from",
        help="Input format (default: caltopo_geojson)",
    ),
    to_format: ToFormat = typer.Option(
        ToFormat.onx,
        "--to",
        help="Output format (default: onx)",
    ),
    output: Optional[Path] = typer.Option(
        "./onx_ready",
        "--output", "-o",
        help="Output directory (onx) or output GeoJSON file/dir (caltopo_geojson)"
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
    ),
    no_sort: bool = typer.Option(
        False,
        "--no-sort",
        help="Preserve original order instead of sorting items"
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompts (auto-confirm sorted order)"
    ),
    kml_file: Optional[Path] = typer.Option(
        None,
        "--kml",
        help="Optional onX KML export to merge (improves polygon/area fidelity)",
    ),
    dedupe: bool = typer.Option(
        True,
        "--dedupe/--no-dedupe",
        help="Deduplicate waypoints during onx_gpx → caltopo_geojson",
    ),
    dedupe_shapes: bool = typer.Option(
        True,
        "--dedupe-shapes/--no-dedupe-shapes",
        help="Deduplicate shapes (polygons/lines) using fuzzy geometry match (default: enabled)",
    ),
    trace_path: Optional[Path] = typer.Option(
        None,
        "--trace",
        help="Write JSONL trace log of transformation steps",
    )
):
    """
    Convert between supported formats.

    For the onX → CalTopo migration workflow, prefer:

      cairn migrate onx-to-caltopo ...

    This tool will:

    - Parse your CalTopo GeoJSON export

    - Sort items in natural order (01, 02... 10, 11) for logical display in OnX

    - Show a preview of the sorted order with colors (tracks) and icons (waypoints)

    - Map CalTopo symbols and keywords to onX Backcountry icons

    - Preserve track colors and line styles from CalTopo

    - Split large datasets to respect onX's 3,000 item limit

    - Generate GPX files with onX extensions for waypoints and tracks

    - Generate KML files for shapes/polygons

    IMPORTANT: OnX does not allow reordering items after import! The preview
    shows exactly how items will appear in OnX. If you need a different order,
    you must rename items in CalTopo (or edit the GeoJSON) before converting.

    To change icons or colors before export, use:

      cairn icon map "symbol-name" "OnX-Icon"

      cairn config set-default-color "rgba(255,0,0,1)"

    Or edit the source GeoJSON file directly.
    """
    # ---------------------------------------------------------------------
    # New path: onX → CalTopo GeoJSON
    # ---------------------------------------------------------------------
    if from_format == FromFormat.onx_gpx and to_format == ToFormat.caltopo_geojson:
        if not input_file.exists():
            console.print(f"\n[bold red]❌ Error:[/] File not found: {input_file}")
            raise typer.Exit(1)

        # Determine output GeoJSON path.
        out_path: Path
        out_opt = output or Path(".")
        if out_opt.suffix.lower() == ".json":
            out_path = out_opt
        else:
            out_dir = ensure_output_dir(out_opt)
            out_path = out_dir / f"{input_file.stem}_caltopo.json"

        if trace_path:
            trace_path.parent.mkdir(parents=True, exist_ok=True)

        trace_ctx = TraceWriter(trace_path) if trace_path else None
        try:
            if trace_ctx:
                trace_ctx.emit({"event": "run.start", "from": from_format.value, "to": to_format.value})

            gpx_doc = read_onx_gpx(input_file, trace=trace_ctx)
            doc = gpx_doc

            if kml_file is not None:
                if not kml_file.exists():
                    console.print(f"\n[bold red]❌ Error:[/] KML file not found: {kml_file}")
                    raise typer.Exit(1)
                kml_doc = read_onx_kml(kml_file, trace=trace_ctx)
                doc = merge_onx_gpx_and_kml(doc, kml_doc, trace=trace_ctx)

            if trace_ctx:
                trace_ctx.emit({"event": "inventory.before_dedup", **document_inventory(doc)})

            report = None
            if dedupe:
                report = apply_waypoint_dedup(doc, trace=trace_ctx)

            if trace_ctx:
                trace_ctx.emit({"event": "inventory.after_dedup", **document_inventory(doc)})
                if report is not None:
                    trace_ctx.emit({"event": "dedup.report", **dedup_inventory(report)})

            # Shape dedup (default on): produce a primary usable dataset and preserve dropped duplicates separately.
            shape_report = None
            dropped_shapes_doc_path: Optional[Path] = None
            summary_path: Optional[Path] = None

            dropped_items: list = []
            if dedupe_shapes:
                shape_report, dropped_items = apply_shape_dedup(doc, trace=trace_ctx)

            out_path.parent.mkdir(parents=True, exist_ok=True)
            write_caltopo_geojson(doc, out_path, trace=trace_ctx)

            # If shape dedup ran, write the dropped features to a secondary GeoJSON file
            # and generate a SUMMARY.md documenting every group.
            if dedupe_shapes and shape_report is not None:
                dropped_shapes_doc_path = out_path.with_name(out_path.stem + "_dropped_shapes.json")
                from cairn.model import MapDocument as _MapDocument

                dropped_doc = _MapDocument(
                    folders=list(doc.folders),
                    items=list(dropped_items),
                    metadata={
                        "source": "cairn_shape_dedup_dropped",
                        "primary": str(out_path),
                    },
                )
                write_caltopo_geojson(dropped_doc, dropped_shapes_doc_path, trace=trace_ctx)

                summary_path = out_path.with_name(out_path.stem + "_SUMMARY.md")
                write_shape_dedup_summary(
                    summary_path,
                    report=shape_report,
                    primary_geojson_path=out_path,
                    dropped_geojson_path=dropped_shapes_doc_path,
                    gpx_path=input_file,
                    kml_path=(kml_file or ""),
                    waypoint_dedup_dropped=(report.dropped_count if report is not None else 0),
                )

            console.print(f"\n[bold green]✔ SUCCESS[/] Wrote CalTopo GeoJSON: [underline]{out_path}[/]")
            console.print(
                f"[dim]Items:[/] {len(doc.waypoints())} waypoints, {len(doc.tracks())} lines, {len(doc.shapes())} areas"
            )
            if report is not None and report.dropped_count:
                console.print(f"[yellow]⚠️  Dedup dropped {report.dropped_count} duplicate waypoint(s).[/]")
            if dedupe_shapes and shape_report is not None and shape_report.dropped_count:
                console.print(f"[yellow]⚠️  Shape dedup dropped {shape_report.dropped_count} duplicate shape(s).[/]")
                console.print(f"[dim]Dropped shapes:[/] {dropped_shapes_doc_path}")
                console.print(f"[dim]Summary:[/] {summary_path}")
            if trace_path:
                console.print(f"[dim]Trace log:[/] {trace_path}")
            return
        finally:
            if trace_ctx:
                trace_ctx.emit({"event": "run.end"})
                trace_ctx.close()

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

    # Process and write files with sorting and confirmation
    sort_enabled = not no_sort
    console.print(f"[bold white]Writing files to[/] [underline]{output_dir}[/]...\n")
    output_files = process_and_write_files(
        parsed_data,
        output_dir,
        sort=sort_enabled,
        skip_confirmation=yes,
        config=config
    )

    # Display manifest
    console.print()
    display_manifest(output_files)

    # Display any remaining unmapped symbols report
    display_unmapped_symbols(config)

    # Display name sanitization warnings
    display_name_sanitization_warnings()

    # Success footer
    console.print(f"\n[bold green]✔ SUCCESS[/] {len(output_files)} file(s) written to [underline]{output_dir}[/]")
    console.print("[dim]Next: Drag these files into onX Web Map → Import[/]\n")
