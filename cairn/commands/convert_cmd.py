"""Convert command for Cairn CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Tuple
import typer
from enum import Enum
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from cairn.core.parser import parse_geojson, get_file_summary, ParsedData
from cairn.core.writers import write_kml_shapes, get_name_changes, clear_name_changes
from cairn.utils.utils import (
    chunk_data,
    sanitize_filename,
    format_file_size,
    ensure_output_dir,
    natural_sort_key,
)
from cairn.core.mapper import map_icon
from cairn.core.config import (
    load_config,
    IconMappingConfig,
    get_all_onx_icons,
    save_user_mapping,
)
from cairn.core.matcher import FuzzyIconMatcher
from cairn.core.preview import (
    generate_dry_run_report,
    display_dry_run_report,
    interactive_review,
    interactive_edit_before_export,
    preview_sorted_order,
)
from cairn.core.icon_registry import IconRegistry, write_icon_report_markdown

# New bidirectional adapters (OnX → CalTopo)
from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.core.dedup import apply_waypoint_dedup
from cairn.core.shape_dedup import apply_shape_dedup
from cairn.io.caltopo_geojson import write_caltopo_geojson
from cairn.core.trace import TraceWriter
from cairn.core.diagnostics import document_inventory, dedup_inventory

app = typer.Typer()
console = Console()

VERSION = "1.0.0"


class FromFormat(str, Enum):
    caltopo_geojson = "caltopo_geojson"
    OnX_gpx = "OnX_gpx"


class ToFormat(str, Enum):
    OnX = "OnX"
    caltopo_geojson = "caltopo_geojson"


def print_header() -> None:
    """Print the Cairn header."""
    console.print(
        Panel.fit(
            f"[bold yellow]CAIRN[/] v{VERSION}\n[italic]The CalTopo → OnX Bridge[/]",
            border_style="yellow",
            padding=(0, 4),
        )
    )


def print_file_detection(input_file: Path) -> None:
    """Print file detection message."""
    console.print(f"\n[bold cyan]📂[/] Input file: [green]{input_file.name}[/]")
    file_size = input_file.stat().st_size
    console.print(f"[dim]   Size: {format_file_size(file_size)}[/]")


def parse_with_progress(input_file: Path) -> ParsedData:
    """Parse the GeoJSON file with a progress indicator."""
    console.print()

    # Show spinner while parsing (no fake progress)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("[cyan]Parsing GeoJSON and mapping icons...", total=None)
        # Actually parse the file
        parsed_data = parse_geojson(input_file)

    return parsed_data


def display_folder_tree(parsed_data: ParsedData, config: IconMappingConfig) -> None:
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
                parts.append(
                    f"📍 {stats['waypoints']} Waypoint{'s' if stats['waypoints'] != 1 else ''}"
                )
            if stats["tracks"] > 0:
                parts.append(
                    f"〰️  {stats['tracks']} Track{'s' if stats['tracks'] != 1 else ''}"
                )
            if stats["shapes"] > 0:
                parts.append(
                    f"⬠ {stats['shapes']} Shape{'s' if stats['shapes'] != 1 else ''}"
                )
            folder_label += f" ({', '.join(parts)})"

        folder_node = tree.add(folder_label)

        # Show sample waypoints with mapped icons
        if folder_data["waypoints"]:
            sample_count = min(3, len(folder_data["waypoints"]))
            for waypoint in folder_data["waypoints"][:sample_count]:
                mapped = map_icon(
                    waypoint.title, waypoint.description, waypoint.symbol, config
                )
                folder_node.add(f"[blue]{waypoint.title}[/] → [green]'{mapped}'[/]")

            if len(folder_data["waypoints"]) > sample_count:
                folder_node.add(
                    f"[dim]... and {len(folder_data['waypoints']) - sample_count} more waypoints[/]"
                )

        # Show tracks
        if folder_data["tracks"]:
            for track in folder_data["tracks"][:2]:
                folder_node.add(f"〰️  [blue]{track.title}[/] → [italic]GPX Track[/]")

            if len(folder_data["tracks"]) > 2:
                folder_node.add(
                    f"[dim]... and {len(folder_data['tracks']) - 2} more tracks[/]"
                )

        # Show shapes
        if folder_data["shapes"]:
            for shape in folder_data["shapes"][:2]:
                folder_node.add(f"⬠ [magenta]{shape.title}[/] → [italic]KML Polygon[/]")

            if len(folder_data["shapes"]) > 2:
                folder_node.add(
                    f"[dim]... and {len(folder_data['shapes']) - 2} more shapes[/]"
                )

    console.print(tree)
    console.print()


def prompt_for_icon_mapping(
    symbol: str, waypoint_title: str, suggestions: List[Tuple[str, float]]
) -> Optional[str]:
    """Prompt user to manually map an unmapped symbol."""
    console.print(f"\n[yellow]⚠️  Unmapped symbol:[/] [cyan]{symbol}[/]")
    console.print(f"[dim]   Example: {waypoint_title}[/]")
    console.print("\n[bold]Suggested OnX icons:[/]")

    for i, (icon, confidence) in enumerate(suggestions, 1):
        confidence_pct = int(confidence * 100)
        console.print(f"  {i}. {icon} [dim]({confidence_pct}% match)[/]")

    console.print(f"  {len(suggestions) + 1}. [dim]Browse all icons[/]")
    console.print(f"  {len(suggestions) + 2}. [dim]Skip (use default 'Location')[/]")

    try:
        choice = Prompt.ask(
            "\nSelect an option",
            choices=[str(i) for i in range(1, len(suggestions) + 3)],
            default=str(len(suggestions) + 2),
        )

        choice_num = int(choice)

        if choice_num <= len(suggestions):
            return suggestions[choice_num - 1][0]
        elif choice_num == len(suggestions) + 1:
            from cairn.core.icon_picker import browse_all_icons

            return browse_all_icons()
        else:
            return None
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Skipping...[/]")
        return None


def handle_unmapped_symbols(
    config: IconMappingConfig,
    *,
    unmapped_report: Optional[dict[str, dict]] = None,
    interactive: bool = True,
    config_path: Optional[Path] = None,
) -> bool:
    """Handle unmapped symbols with interactive prompts or reporting."""
    unmapped = unmapped_report or config.get_unmapped_report()

    if not unmapped or len(unmapped) == 0:
        return False

    if not interactive:
        return False

    if config_path is None:
        config_path = Path("cairn_config.yaml")

    console.print("\n[yellow]⚠️  Found unmapped symbols. Let's map them![/]")
    console.print(
        "[dim]You can map these now or skip to use the default 'Location' icon.[/]\n"
    )

    matcher = FuzzyIconMatcher(get_all_onx_icons())
    mappings_added = False

    for symbol, info in unmapped.items():
        suggestions = matcher.find_best_matches(symbol, top_n=3)
        selected_icon = prompt_for_icon_mapping(
            symbol, info["examples"][0], suggestions
        )

        if selected_icon:
            save_user_mapping(symbol, selected_icon, config_path=config_path)
            console.print(
                f"[green]✓[/] Mapped '[cyan]{symbol}[/]' → '[green]{selected_icon}[/]'"
            )
            mappings_added = True
        else:
            console.print(f"[dim]Skipped '{symbol}' (will use 'Location')[/]")

    return mappings_added


def process_and_write_files(
    parsed_data: ParsedData,
    output_dir: Path,
    sort: bool = True,
    skip_confirmation: bool = False,
    config: IconMappingConfig = None,
    *,
    split_gpx: bool = True,
    max_gpx_bytes: Optional[int] = None,
    prefix: Optional[str] = None,
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

    from cairn.core.writers import DEFAULT_MAX_GPX_BYTES as _DEFAULT_MAX_GPX_BYTES
    from cairn.core.writers import (
        write_gpx_waypoints_maybe_split,
        write_gpx_tracks_maybe_split,
    )

    # Defensive: keep defaults even if caller didn't pass new args (older call sites).
    if max_gpx_bytes is None:
        max_gpx_bytes = _DEFAULT_MAX_GPX_BYTES

    for folder_id, folder_data in parsed_data.folders.items():
        folder_name = folder_data["name"]
        safe_name = sanitize_filename(folder_name)
        # Apply prefix if provided
        if prefix and prefix.strip():
            prefix_safe = sanitize_filename(prefix.strip())
            safe_name = f"{prefix_safe}_{safe_name}"

        waypoints = folder_data["waypoints"]
        tracks = folder_data["tracks"]
        shapes = folder_data["shapes"]

        # Handle waypoints
        if waypoints:
            total_waypoints = len(waypoints)

            # Sort waypoints for preview if sorting is enabled
            if sort:
                sorted_waypoints = sorted(
                    waypoints, key=lambda f: natural_sort_key(f.title)
                )
            else:
                sorted_waypoints = waypoints

            # Show preview and get confirmation
            if not preview_sorted_order(
                sorted_waypoints, "waypoints", folder_name, skip_confirmation, config
            ):
                console.print("[yellow]Export cancelled by user.[/]")
                return output_files

            # Write in sorted order - OnX displays items in the same order as the GPX file
            write_order_waypoints = sorted_waypoints

            # Debug logging disabled (logger not configured)
            # if logger.isEnabledFor(logging.DEBUG):
            #     logger.debug(f"[DEBUG] Waypoint order before write ({folder_name}):")
            #     for i, wp in enumerate(write_order_waypoints[:20], 1):
            #         logger.debug(f"  {i}. {wp.title}")
            #     if len(write_order_waypoints) > 20:
            #         logger.debug(f"  ... and {len(write_order_waypoints) - 20} more waypoints")

            if total_waypoints > 2500:
                console.print(
                    f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_waypoints} waypoints)..."
                )
                console.print("   [yellow]⚠️  Exceeds OnX limit (3,000).[/]")
                console.print("   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(write_order_waypoints, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Waypoints_Part{i}"
                    output_path = output_dir / f"{part_name}.gpx"
                    # Pass sort=False since we already sorted and reversed
                    written_parts = write_gpx_waypoints_maybe_split(
                        chunk,
                        output_path,
                        f"{folder_name} - Part {i}",
                        sort=False,
                        config=config,
                        split=split_gpx,
                        max_bytes=max_gpx_bytes,
                    )
                    for pth, sz, cnt in written_parts:
                        output_files.append((pth.name, "GPX (Waypoints)", cnt, sz))
                    console.print(
                        f"       ├── 📄 [green]{output_path.name}[/] ({len(chunk)} items)"
                    )
            else:
                output_path = output_dir / f"{safe_name}_Waypoints.gpx"
                # Pass sort=False since we already sorted and reversed
                written_parts = write_gpx_waypoints_maybe_split(
                    write_order_waypoints,
                    output_path,
                    folder_name,
                    sort=False,
                    config=config,
                    split=split_gpx,
                    max_bytes=max_gpx_bytes,
                )
                for pth, sz, cnt in written_parts:
                    output_files.append((pth.name, "GPX (Waypoints)", cnt, sz))

        # Handle tracks
        if tracks:
            total_tracks = len(tracks)

            # Sort tracks for preview if sorting is enabled
            if sort:
                sorted_tracks = sorted(tracks, key=lambda f: natural_sort_key(f.title))
            else:
                sorted_tracks = tracks

            # Show preview and get confirmation
            if not preview_sorted_order(
                sorted_tracks, "tracks", folder_name, skip_confirmation
            ):
                console.print("[yellow]Export cancelled by user.[/]")
                return output_files

            # Write in sorted order - OnX displays items in the same order as the GPX file
            write_order_tracks = sorted_tracks

            if total_tracks > 2500:
                console.print(
                    f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_tracks} tracks)..."
                )
                console.print("   [yellow]⚠️  Exceeds OnX limit (3,000).[/]")
                console.print("   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(write_order_tracks, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Tracks_Part{i}"
                    output_path = output_dir / f"{part_name}.gpx"
                    # Pass sort=False since we already sorted and reversed
                    written_parts = write_gpx_tracks_maybe_split(
                        chunk,
                        output_path,
                        f"{folder_name} - Part {i}",
                        sort=False,
                        split=split_gpx,
                        max_bytes=max_gpx_bytes,
                    )
                    for pth, sz, cnt in written_parts:
                        output_files.append((pth.name, "GPX (Tracks)", cnt, sz))
                    console.print(
                        f"       ├── 📄 [green]{output_path.name}[/] ({len(chunk)} items)"
                    )
            else:
                output_path = output_dir / f"{safe_name}_Tracks.gpx"
                # Pass sort=False since we already sorted and reversed
                written_parts = write_gpx_tracks_maybe_split(
                    write_order_tracks,
                    output_path,
                    folder_name,
                    sort=False,
                    split=split_gpx,
                    max_bytes=max_gpx_bytes,
                )
                for pth, sz, cnt in written_parts:
                    output_files.append((pth.name, "GPX (Tracks)", cnt, sz))

        # Handle shapes (KML)
        if shapes:
            total_shapes = len(shapes)

            # Sort shapes if sorting is enabled
            if sort:
                sorted_shapes = sorted(shapes, key=lambda f: natural_sort_key(f.title))
            else:
                sorted_shapes = shapes

            # Show preview and get confirmation for shapes
            if not preview_sorted_order(
                sorted_shapes, "shapes", folder_name, skip_confirmation
            ):
                console.print("[yellow]Export cancelled by user.[/]")
                return output_files

            # Write in sorted order - OnX displays items in the same order as the file
            write_order_shapes = sorted_shapes

            if total_shapes > 2500:
                console.print(
                    f"\n📂 Processing '[cyan]{folder_name}[/]' ({total_shapes} shapes)..."
                )
                console.print("   [yellow]⚠️  Exceeds OnX limit (3,000).[/]")
                console.print("   [yellow]✨  Auto-split into:[/]")

                chunks = list(chunk_data(write_order_shapes, limit=2500))
                for i, chunk in enumerate(chunks, 1):
                    part_name = f"{safe_name}_Shapes_Part{i}"
                    output_path = output_dir / f"{part_name}.kml"
                    file_size = write_kml_shapes(
                        chunk, output_path, f"{folder_name} - Part {i}"
                    )
                    output_files.append(
                        (f"{part_name}.kml", "KML (Shapes)", len(chunk), file_size)
                    )
                    console.print(
                        f"       ├── 📄 [green]{part_name}.kml[/] ({len(chunk)} items)"
                    )
            else:
                output_path = output_dir / f"{safe_name}_Shapes.kml"
                file_size = write_kml_shapes(
                    write_order_shapes, output_path, folder_name
                )
                output_files.append(
                    (
                        f"{safe_name}_Shapes.kml",
                        "KML (Shapes)",
                        len(write_order_shapes),
                        file_size,
                    )
                )

    return output_files


def display_manifest(output_files: list) -> None:
    """Display a table of created files."""
    table = Table(title="Export Manifest", border_style="green")
    table.add_column("Filename", style="yellow")
    table.add_column("Format", style="white")
    table.add_column("Items", justify="right")
    table.add_column("Size", justify="right")

    for filename, format_type, item_count, file_size in output_files:
        table.add_row(
            filename, format_type, str(item_count), format_file_size(file_size)
        )

    console.print(table)


def collect_unmapped_caltopo_symbols(
    parsed_data: ParsedData, config: IconMappingConfig
) -> dict[str, dict]:
    """
    Collect unmapped CalTopo marker-symbol values from the parsed dataset.

    This is computed without mutating `config.unmapped_symbols`, so it can be shown early
    without double-counting later when `map_icon(...)` is called during export.
    """
    from cairn.core.config import GENERIC_SYMBOLS

    by_symbol: dict[str, dict] = {}
    folders = getattr(parsed_data, "folders", {}) or {}
    for _, folder_data in folders.items():
        for wp in folder_data.get("waypoints", []) or []:
            sym = (getattr(wp, "symbol", "") or "").strip().lower()
            if not sym or sym in GENERIC_SYMBOLS:
                continue
            if sym in (config.symbol_map or {}):
                continue

            row = by_symbol.get(sym)
            if row is None:
                row = {"count": 0, "examples": []}
                by_symbol[sym] = row

            row["count"] += 1
            if len(row["examples"]) < 3:
                title = (getattr(wp, "title", "") or "").strip()
                if title:
                    row["examples"].append(title)

    return by_symbol


def display_unmapped_symbols(
    config: IconMappingConfig, unmapped_report: Optional[dict[str, dict]] = None
) -> None:
    """Display a report of unmapped CalTopo symbols found."""
    report = unmapped_report or (
        config.get_unmapped_report() if config.has_unmapped_symbols() else {}
    )
    if not report:
        return

    console.print(f"\n[yellow]⚠️  Found {len(report)} unmapped CalTopo symbol(s):[/]")

    table = Table(border_style="yellow")
    table.add_column("Symbol", style="cyan")
    table.add_column("Count", justify="right", style="white")
    table.add_column("Example Waypoint", style="dim")

    for symbol, stats in sorted(
        report.items(), key=lambda x: x[1]["count"], reverse=True
    ):
        example = stats["examples"][0] if stats["examples"] else "N/A"
        table.add_row(
            symbol,
            str(stats["count"]),
            example[:40] + "..." if len(example) > 40 else example,
        )

    console.print(table)
    console.print(
        "\n[dim]💡 Add these to your config (default: cairn_config.yaml) to map them to OnX icons[/]"
    )
    console.print("[dim]   Run 'cairn config export' to create a template[/]")
    console.print(
        "[dim]   Run 'cairn config show' to see valid OnX icons already used in your mappings[/]"
    )


def display_name_sanitization_warnings() -> None:
    """Display warnings about name sanitization for OnX sorting compatibility."""
    name_changes = get_name_changes()

    total_changes = len(name_changes.get("waypoints", [])) + len(
        name_changes.get("tracks", [])
    )

    if total_changes == 0:
        return

    console.print("\n[yellow]⚠️  Name Sanitization Applied[/]")
    console.print("─" * 70)
    console.print("To improve OnX sorting compatibility, the following characters")
    console.print("were removed from names: [cyan]! @ # $ % ^ * &[/]")
    console.print()

    waypoint_changes = name_changes.get("waypoints", [])
    track_changes = name_changes.get("tracks", [])

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
            console.print(
                f"  [dim]... and {len(waypoint_changes) - max_examples} more waypoint changes[/]"
            )

    if track_changes:
        console.print("\n[cyan]Tracks:[/]")
        for original, sanitized in track_changes[:max_examples]:
            console.print(f"  [dim]{original[:35]:<35}[/] → [green]{sanitized[:35]}[/]")
            examples_shown += 1
        if len(track_changes) > max_examples:
            console.print(
                f"  [dim]... and {len(track_changes) - max_examples} more track changes[/]"
            )

    console.print()
    console.print(
        "[dim]Note: Natural sort order is preserved. This is a test feature.[/]"
    )
    console.print("─" * 70)


def convert(
    input_file: Path = typer.Argument(
        ..., help="Input file (default: CalTopo GeoJSON)"
    ),
    from_format: FromFormat = typer.Option(
        FromFormat.caltopo_geojson,
        "--from",
        help="Input format (default: caltopo_geojson)",
    ),
    to_format: ToFormat = typer.Option(
        ToFormat.OnX,
        "--to",
        help="Output format (default: OnX)",
    ),
    output: Optional[Path] = typer.Option(
        "./onx_ready",
        "--output",
        "-o",
        help="Output directory (OnX) or output GeoJSON file/dir (caltopo_geojson)",
    ),
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Custom icon mapping configuration file"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview conversion without creating files"
    ),
    review: bool = typer.Option(
        False, "--review", help="Interactive review of icon mappings before conversion"
    ),
    edit: Optional[bool] = typer.Option(
        None,
        "--edit/--no-edit",
        help="Interactive global edit of tracks/waypoints (names/descriptions/icons/colors) before writing files (CalTopo → OnX only)",
    ),
    no_sort: bool = typer.Option(
        False, "--no-sort", help="Preserve original order instead of sorting items"
    ),
    max_gpx_mb: float = typer.Option(
        3.75,
        "--max-gpx-mb",
        help="Maximum GPX file size in MB before auto-splitting (OnX import limit is 4MB; default keeps a safety margin).",
    ),
    split_gpx: bool = typer.Option(
        True,
        "--split-gpx/--no-split-gpx",
        help="Automatically split GPX files that exceed the max size into multiple numbered parts.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts (auto-confirm sorted order)",
    ),
    kml_file: Optional[Path] = typer.Option(
        None,
        "--kml",
        help="Optional OnX KML export to merge (improves polygon/area fidelity)",
    ),
    dedupe: bool = typer.Option(
        True,
        "--dedupe/--no-dedupe",
        help="Deduplicate waypoints during OnX_gpx → caltopo_geojson",
    ),
    dedupe_shapes: bool = typer.Option(
        True,
        "--dedupe-shapes/--no-dedupe-shapes",
        help="Deduplicate shapes (polygons/lines) using fuzzy geometry match (default: enabled)",
    ),
    description_mode: str = typer.Option(
        "notes-only",
        "--description-mode",
        help="CalTopo description content when writing GeoJSON: notes-only (default) or debug",
    ),
    route_color_strategy: str = typer.Option(
        "palette",
        "--route-color-strategy",
        help="Route stroke color when OnX line color is missing: palette (default), default-blue, or none",
    ),
    trace_path: Optional[Path] = typer.Option(
        None,
        "--trace",
        help="Write JSONL trace log of transformation steps",
    ),
):
    """
    Convert between supported formats.

    For the OnX → CalTopo migration workflow, prefer:

      cairn migrate onx-to-caltopo ...

    This tool will:

    - Parse your CalTopo GeoJSON export

    - Sort items in natural order (01, 02... 10, 11) for logical display in OnX

    - Show a preview of the sorted order with colors (tracks) and icons (waypoints)

    - Map CalTopo symbols and keywords to OnX Backcountry icons

    - Preserve track colors and line styles from CalTopo

    - Split large datasets to respect OnX's 3,000 item limit

    - Generate GPX files with OnX extensions for waypoints and tracks

    - Generate KML files for shapes/polygons

    IMPORTANT: OnX does not allow reordering items after import! The preview
    shows exactly how items will appear in OnX. If you need a different order,
    you must rename items in CalTopo (or edit the GeoJSON) before converting.

    To change icons or colors before export, edit `cairn_config.yaml` (symbol_mappings)
    or adjust your config file passed via `--config`.

    Or edit the source GeoJSON file directly.
    """
    # ---------------------------------------------------------------------
    # New path: OnX → CalTopo GeoJSON
    # ---------------------------------------------------------------------
    if from_format == FromFormat.OnX_gpx and to_format == ToFormat.caltopo_geojson:
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
                trace_ctx.emit(
                    {
                        "event": "run.start",
                        "from": from_format.value,
                        "to": to_format.value,
                    }
                )

            try:
                gpx_doc = read_onx_gpx(input_file, trace=trace_ctx)
                doc = gpx_doc
            except ValueError as e:
                console.print("\n[bold red]❌ Error reading GPX file:[/]")
                console.print(f"[red]{e}[/]")
                raise typer.Exit(1)

            if kml_file is not None:
                if not kml_file.exists():
                    console.print(
                        f"\n[bold red]❌ Error:[/] KML file not found: {kml_file}"
                    )
                    raise typer.Exit(1)
                try:
                    kml_doc = read_onx_kml(kml_file, trace=trace_ctx)
                    doc = merge_onx_gpx_and_kml(doc, kml_doc, trace=trace_ctx)
                except ValueError as e:
                    console.print("\n[bold red]❌ Error reading KML file:[/]")
                    console.print(f"[red]{e}[/]")
                    raise typer.Exit(1)

            if trace_ctx:
                trace_ctx.emit(
                    {"event": "inventory.before_dedup", **document_inventory(doc)}
                )

            report = None
            if dedupe:
                report = apply_waypoint_dedup(doc, trace=trace_ctx)

            if trace_ctx:
                trace_ctx.emit(
                    {"event": "inventory.after_dedup", **document_inventory(doc)}
                )
                if report is not None:
                    trace_ctx.emit({"event": "dedup.report", **dedup_inventory(report)})

            # Shape dedup (default on): produce a primary usable dataset and preserve dropped duplicates separately.
            shape_report = None
            dropped_shapes_doc_path: Optional[Path] = None

            dropped_items: list = []
            if dedupe_shapes:
                shape_report, dropped_items = apply_shape_dedup(doc, trace=trace_ctx)

            out_path.parent.mkdir(parents=True, exist_ok=True)
            desc_mode_norm = (description_mode or "").strip().lower().replace("-", "_")
            if desc_mode_norm in ("notes_only", "notes"):
                desc_mode_norm = "notes_only"
            elif desc_mode_norm != "debug":
                raise typer.BadParameter(
                    "--description-mode must be one of: notes-only, debug"
                )

            route_color_norm = (
                (route_color_strategy or "").strip().lower().replace("-", "_")
            )
            if route_color_norm == "defaultblue":
                route_color_norm = "default_blue"
            if route_color_norm not in ("palette", "default_blue", "none"):
                raise typer.BadParameter(
                    "--route-color-strategy must be one of: palette, default-blue, none"
                )

            write_caltopo_geojson(
                doc,
                out_path,
                trace=trace_ctx,
                description_mode=desc_mode_norm,  # type: ignore[arg-type]
                route_color_strategy=route_color_norm,  # type: ignore[arg-type]
            )

            # Icon report + catalog (best-effort; never fails conversion)
            try:
                reg = IconRegistry()
                inv = reg.collect_onx_icon_inventory(doc)
                rows = reg.collect_onx_icon_mapping_rows(doc)
                icon_report_path = out_path.with_name(out_path.stem + "_ICON_REPORT.md")
                write_icon_report_markdown(
                    output_path=icon_report_path,
                    title="OnX → CalTopo icon mapping report",
                    inventories=inv,
                    rows=rows,
                    notes=(
                        [f"Input GPX: `{input_file.name}`"]
                        + ([f"Input KML: `{kml_file.name}`"] if kml_file else [])
                    ),
                )
                reg.append_onx_icon_inventory_to_catalog(inv)
            except Exception:
                pass

            # If shape dedup ran, write the dropped features to a secondary GeoJSON file.
            if dedupe_shapes and shape_report is not None:
                dropped_shapes_doc_path = out_path.with_name(
                    out_path.stem + "_dropped_shapes.json"
                )
                from cairn.model import MapDocument as _MapDocument

                dropped_doc = _MapDocument(
                    folders=list(doc.folders),
                    items=list(dropped_items),
                    metadata={
                        "source": "cairn_shape_dedup_dropped",
                        "primary": str(out_path),
                    },
                )
                write_caltopo_geojson(
                    dropped_doc,
                    dropped_shapes_doc_path,
                    trace=trace_ctx,
                    description_mode=desc_mode_norm,  # type: ignore[arg-type]
                    route_color_strategy=route_color_norm,  # type: ignore[arg-type]
                )

            console.print(
                f"\n[bold green]✔ SUCCESS[/] Wrote CalTopo GeoJSON: [underline]{out_path}[/]"
            )
            console.print(
                f"[dim]Items:[/] {len(doc.waypoints())} waypoints, {len(doc.tracks())} lines, {len(doc.shapes())} areas"
            )
            if report is not None and report.dropped_count:
                console.print(
                    f"[yellow]⚠️  Dedup dropped {report.dropped_count} duplicate waypoint(s).[/]"
                )
            if (
                dedupe_shapes
                and shape_report is not None
                and shape_report.dropped_count
            ):
                console.print(
                    f"[yellow]⚠️  Shape dedup dropped {shape_report.dropped_count} duplicate shape(s).[/]"
                )
                console.print(f"[dim]Dropped shapes:[/] {dropped_shapes_doc_path}")
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

    # Show unmapped-symbol warning early so users can map symbols before export.
    unmapped_report = collect_unmapped_caltopo_symbols(parsed_data, config)
    display_unmapped_symbols(config, unmapped_report=unmapped_report)

    # Display folder tree (with config for icon mapping)
    display_folder_tree(parsed_data, config)

    # DRY RUN MODE: Generate and display report without creating files
    if dry_run:
        report = generate_dry_run_report(parsed_data, config)
        display_dry_run_report(report)

        return

    # REVIEW MODE: Interactive review before conversion
    if review:
        parsed_data, changes_made = interactive_review(parsed_data, config)

        if changes_made:
            # Reload config with new mappings
            console.print(
                "\n[green]✓[/] Reloading configuration with new mappings...\n"
            )
            config = load_config(config_file)
            # Re-parse to apply new mappings
            parsed_data = parse_geojson(input_file)

    # Handle unmapped symbols interactively (if not in review mode)
    if not review and unmapped_report:
        mappings_added = handle_unmapped_symbols(
            config,
            unmapped_report=unmapped_report,
            interactive=True,
            config_path=(config_file or Path("cairn_config.yaml")),
        )

        if mappings_added:
            # Reload config with new mappings
            console.print(
                "\n[green]✓[/] Reloading configuration with new mappings...\n"
            )
            config = load_config(config_file)

            # Re-parse to apply new mappings
            parsed_data = parse_geojson(input_file)
            unmapped_report = collect_unmapped_caltopo_symbols(parsed_data, config)

    # Ensure output directory exists
    output_dir = ensure_output_dir(output)

    # Optional: global preview + edit loop before writing any OnX import files.
    # Default behavior: if edit is not specified, enable edit when interactive and disable when --yes is used.
    edit_enabled = (not yes) if edit is None else bool(edit)
    if edit_enabled:
        interactive_edit_before_export(
            parsed_data, config, edit_tracks=True, edit_waypoints=True
        )

    # Icon report + catalog for CalTopo → OnX (best-effort; never fails conversion)
    try:
        reg = IconRegistry()
        inventory = reg.collect_caltopo_symbol_inventory(parsed_data)

        from cairn.core.config import GENERIC_SYMBOLS
        from cairn.core.icon_resolver import IconResolver
        from cairn.core.icon_registry import IconReportRow

        resolver = IconResolver(
            symbol_map={
                str(k).strip().lower(): str(v).strip()
                for k, v in (config.symbol_map or {}).items()
            },
            keyword_map=config.keyword_map or {},
            default_icon=config.default_icon,
            generic_symbols=set(GENERIC_SYMBOLS),
        )

        mapping_counts = {}
        mapping_examples = {}
        mapping_colors = {}
        for folder in (getattr(parsed_data, "folders", {}) or {}).values():
            for feat in folder.get("waypoints", []) or []:
                title = getattr(feat, "title", "") or ""
                desc = getattr(feat, "description", "") or ""
                sym = (getattr(feat, "symbol", "") or "").strip().lower() or "(missing)"
                decision = resolver.resolve(
                    title, desc, "" if sym == "(missing)" else sym
                )
                key = (sym, decision.icon, decision.source)
                mapping_counts[key] = mapping_counts.get(key, 0) + 1
                if title and len(mapping_examples.get(key, [])) < 3:
                    mapping_examples.setdefault(key, []).append(title)
                c = (getattr(feat, "color", "") or "").strip()
                if c:
                    cur = mapping_colors.setdefault(key, [])
                    if c not in cur and len(cur) < 3:
                        cur.append(c)

        rows = []
        for (sym, icon, src), n in sorted(
            mapping_counts.items(),
            key=lambda kv: (-kv[1], kv[0][0], kv[0][1], kv[0][2]),
        ):
            rows.append(
                IconReportRow(
                    incoming=sym,
                    mapped=icon,
                    mapping_source=src,
                    count=n,
                    examples=tuple(mapping_examples.get((sym, icon, src), [])),
                    colors=tuple(mapping_colors.get((sym, icon, src), [])),
                )
            )

        icon_report_path = output_dir / f"{input_file.stem}_ICON_REPORT.md"
        write_icon_report_markdown(
            output_path=icon_report_path,
            title="CalTopo → OnX icon mapping report",
            inventories=inventory,
            rows=rows,
            notes=(
                [f"Input GeoJSON: `{input_file.name}`"]
                + ([f"Config: `{config_file}`"] if config_file else [])
            ),
        )
        reg.append_symbol_inventory_to_catalog(inventory)
    except Exception:
        pass

    # Process and write files with sorting and confirmation
    sort_enabled = not no_sort
    console.print(f"[bold white]Writing files to[/] [underline]{output_dir}[/]...\n")
    output_files = process_and_write_files(
        parsed_data,
        output_dir,
        sort=sort_enabled,
        skip_confirmation=yes,
        config=config,
        split_gpx=split_gpx,
        max_gpx_bytes=int(max(0.0, float(max_gpx_mb)) * 1024 * 1024),
    )

    # Display manifest
    console.print()
    display_manifest(output_files)

    # Display name sanitization warnings
    display_name_sanitization_warnings()

    # Success footer
    console.print(
        f"\n[bold green]✔ SUCCESS[/] {len(output_files)} file(s) written to [underline]{output_dir}[/]"
    )
    console.print("[dim]Next: Drag these files into OnX Web Map → Import[/]\n")
