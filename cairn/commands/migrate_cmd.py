"""\
Migration-focused CLI commands.

These are thin wrappers around the conversion pipeline that prioritize:
- clear intent (one command per migration direction)
- sensible defaults (dedupe on, polygon preference)
- predictable output locations and filenames

This module is intentionally UX-focused: interactive prompting, progress output,
and a clean summary of generated artifacts.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from cairn.core.dedup import apply_waypoint_dedup
from cairn.core.diagnostics import check_data_quality, dedup_inventory, document_inventory
from cairn.core.icon_registry import IconRegistry, write_icon_report_markdown
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.core.shape_dedup import apply_shape_dedup
from cairn.core.trace import TraceWriter
from cairn.io.caltopo_geojson import write_caltopo_geojson
from cairn.io.onx_gpx import read_OnX_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.model import MapDocument
from cairn.utils.utils import ensure_output_dir, format_file_size


app = typer.Typer(
    no_args_is_help=True,
    help="""
Migration helpers for OnX Backcountry ↔ CalTopo.

Currently supported:
  onx-to-caltopo      Migrate OnX exports to CalTopo GeoJSON
  caltopo-to-onx      Migrate CalTopo GeoJSON to OnX GPX/KML

The migration workflow is designed to preserve all map customization
(icons, colors, notes, organization) - not just raw shapes.
    """.strip()
)
console = Console()


def _display_path(p: Path) -> str:
    """Prefer a relative path; fall back to filename."""
    try:
        return str(p.resolve().relative_to(Path.cwd().resolve()))
    except Exception:
        return p.name


def _prompt_existing_path(label: str, *, expected_suffix: str) -> Path:
    """Prompt until the user enters an existing path with the expected suffix."""
    while True:
        entered = typer.prompt(label).strip()
        p = Path(entered).expanduser()
        if p.suffix.lower() != expected_suffix.lower():
            console.print(f"[bold red]Expected a {expected_suffix} file:[/] {p}")
            continue
        if not p.exists():
            console.print(f"[bold red]File not found:[/] {p}")
            continue
        return p


def _validate_existing_file(value: Optional[Path], *, expected_suffix: str, label: str) -> Optional[Path]:
    if value is None:
        return None
    p = value.expanduser()
    if p.suffix.lower() != expected_suffix.lower():
        raise typer.BadParameter(f"Expected a {expected_suffix} file: {p}")
    if not p.exists():
        raise typer.BadParameter(f"{label} file not found: {p}")
    return p


def _find_export_files(directory: Path) -> Tuple[List[Path], List[Path]]:
    """
    Find GPX and KML files in directory.

    Returns:
        (gpx_files, kml_files) - sorted by modification time (newest first)
    """
    gpx_files = sorted(
        directory.glob("*.gpx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    kml_files = sorted(
        directory.glob("*.kml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return gpx_files, kml_files


def _select_files_interactive(
    gpx_files: List[Path],
    kml_files: List[Path]
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Display available files and prompt user to select.

    Returns:
        (selected_gpx, selected_kml) or (None, None) if cancelled
    """
    console.print("\n[bold]Found export files:[/]")

    # Display GPX files
    if not gpx_files:
        console.print("[red]No GPX files found[/]")
        return None, None

    console.print("\n[bold cyan]GPX files:[/]")
    for i, gpx in enumerate(gpx_files, 1):
        size = gpx.stat().st_size
        mtime = datetime.fromtimestamp(gpx.stat().st_mtime)
        console.print(f"  {i}. {gpx.name} [dim]({format_file_size(size)}, {mtime:%Y-%m-%d %H:%M})[/]")

    # Display KML files
    if not kml_files:
        console.print("\n[yellow]⚠️  No KML files found (optional but recommended)[/]")
        selected_kml = None
    else:
        console.print("\n[bold cyan]KML files:[/]")
        for i, kml in enumerate(kml_files, 1):
            size = kml.stat().st_size
            mtime = datetime.fromtimestamp(kml.stat().st_mtime)
            console.print(f"  {i}. {kml.name} [dim]({format_file_size(size)}, {mtime:%Y-%m-%d %H:%M})[/]")

    # Prompt for selection
    console.print()
    try:
        gpx_choice = typer.prompt("Select GPX file number", default="1")
        selected_gpx = gpx_files[int(gpx_choice) - 1]
    except (ValueError, IndexError):
        console.print("[red]Invalid selection[/]")
        return None, None

    if kml_files:
        try:
            kml_choice = typer.prompt("Select KML file number", default="1")
            selected_kml = kml_files[int(kml_choice) - 1]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection[/]")
            return None, None
    else:
        selected_kml = None

    return selected_gpx, selected_kml


def _confirm_migration(
    gpx_path: Path,
    kml_path: Optional[Path],
    output_dir: Path,
    base_name: str,
    dedupe_waypoints: bool,
    dedupe_shapes: bool,
) -> bool:
    """
    Display migration summary and prompt for confirmation.

    Returns:
        True if user confirms, False to cancel
    """
    console.print("\n[bold]Migration Summary:[/]")
    console.print("─" * 60)

    # Input files
    console.print("\n[bold cyan]Input Files:[/]")
    console.print(f"  GPX: [green]{gpx_path.name}[/]")
    if kml_path:
        console.print(f"  KML: [green]{kml_path.name}[/]")
    else:
        console.print(f"  KML: [dim]None (areas may not be preserved)[/]")

    # Output files
    console.print(f"\n[bold cyan]Output Directory:[/]")
    console.print(f"  {_display_path(output_dir)}")

    console.print(f"\n[bold cyan]Output Files (will be created):[/]")
    console.print(f"  • {base_name}.json [dim](primary GeoJSON)[/]")
    console.print(f"  • {base_name}_dropped_shapes.json [dim](duplicates)[/]")
    console.print(f"  • {base_name}_trace.jsonl [dim](debug log)[/]")

    # Options
    console.print(f"\n[bold cyan]Processing Options:[/]")
    console.print(f"  Dedupe waypoints: {'[green]Yes[/]' if dedupe_waypoints else '[dim]No[/]'}")
    console.print(f"  Dedupe shapes: {'[green]Yes[/]' if dedupe_shapes else '[dim]No[/]'}")

    console.print("\n" + "─" * 60)

    # Prompt for confirmation
    confirm = typer.confirm("\nProceed with migration?", default=True)
    return confirm


def _find_geojson_files(directory: Path) -> List[Path]:
    """
    Find GeoJSON files in directory.

    Returns:
        List of .json and .geojson files sorted alphabetically
    """
    json_files = list(directory.glob("*.json")) + list(directory.glob("*.geojson"))
    # Sort alphabetically by filename
    json_files.sort(key=lambda p: p.name.lower())
    return json_files


def _select_geojson_interactive(json_files: List[Path]) -> Optional[Path]:
    """
    Display available GeoJSON files and prompt user to select.

    Returns:
        Selected Path or None if cancelled
    """
    console.print("\n[bold]Found GeoJSON files:[/]")

    if not json_files:
        console.print("[red]No JSON/GeoJSON files found[/]")
        return None

    console.print("\n[bold cyan]Available files:[/]")
    for i, json_file in enumerate(json_files, 1):
        size = json_file.stat().st_size
        mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
        console.print(f"  {i}. {json_file.name} [dim]({format_file_size(size)}, {mtime:%Y-%m-%d %H:%M})[/]")

    # Prompt for selection
    console.print()
    try:
        choice = typer.prompt("Select file number", default="1")
        selected_file = json_files[int(choice) - 1]
        return selected_file
    except (ValueError, IndexError):
        console.print("[red]Invalid selection[/]")
        return None


def _validate_geojson_file(file_path: Path):
    """
    Validate GeoJSON file and parse it.

    Returns:
        Tuple of (success: bool, parsed_data: Optional[ParsedData])
    """
    from cairn.core.parser import parse_geojson

    # Check extension
    if file_path.suffix.lower() not in ['.json', '.geojson']:
        console.print(f"[red]Expected a .json or .geojson file: {file_path}[/]")
        return False, None

    # Try to parse
    try:
        parsed_data = parse_geojson(file_path)
        return True, parsed_data
    except Exception as e:
        console.print(f"[bold red]❌ Error parsing GeoJSON:[/]")
        console.print(f"[red]{e}[/]")
        return False, None


def _confirm_caltopo_migration(
    input_file: Path,
    parsed_data,
    output_dir: Path,
    sort_enabled: bool,
) -> bool:
    """
    Display CalTopo migration summary and prompt for confirmation.

    Returns:
        True if user confirms, False to cancel
    """
    from cairn.core.parser import get_file_summary

    console.print("\n[bold]Migration Summary:[/]")
    console.print("─" * 60)

    # Input file
    console.print("\n[bold cyan]Input File:[/]")
    size = input_file.stat().st_size
    console.print(f"  {input_file.name} [dim]({format_file_size(size)})[/]")

    # File summary
    summary = get_file_summary(parsed_data)
    console.print(f"\n[bold cyan]Content:[/]")
    console.print(f"  Folders: {summary['folder_count']}")
    console.print(f"  Waypoints: {summary['total_waypoints']}")
    console.print(f"  Tracks: {summary['total_tracks']}")
    console.print(f"  Shapes: {summary['total_shapes']}")

    # Output directory
    console.print(f"\n[bold cyan]Output Directory:[/]")
    console.print(f"  {_display_path(output_dir)}")

    # Output files (estimate)
    console.print(f"\n[bold cyan]Output Files (will be created):[/]")
    console.print(f"  • GPX files for waypoints and tracks")
    console.print(f"  • KML files for shapes/polygons")

    # Options
    console.print(f"\n[bold cyan]Processing Options:[/]")
    console.print(f"  Natural sorting: {'[green]Yes[/]' if sort_enabled else '[dim]No[/]'}")

    console.print("\n" + "─" * 60)

    # Prompt for confirmation
    confirm = typer.confirm("\nProceed with migration?", default=True)
    return confirm


# Canonical name is lowercase `onx` (CLI-friendly).
@app.command("OnX-to-caltopo", hidden=True, deprecated=True)
@app.command("onx-to-caltopo")
def OnX_to_caltopo(
    input_dir: Optional[Path] = typer.Argument(
        None,
        help="Directory containing OnX GPX and KML exports",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory (defaults to <input-dir>/caltopo_ready)",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Base filename (without extension) for outputs. Defaults to GPX stem.",
    ),
    dedupe_waypoints: bool = typer.Option(
        True,
        "--dedupe-waypoints/--no-dedupe-waypoints",
        help="Remove duplicate waypoints with same name and location",
    ),
    dedupe_shapes: bool = typer.Option(
        True,
        "--dedupe-shapes/--no-dedupe-shapes",
        help="Remove duplicate shapes (lines/polygons) with identical geometry",
    ),
    trace: bool = typer.Option(
        True,
        "--trace/--no-trace",
        help="Write JSONL trace log for debugging (default: enabled)",
    ),
    trace_path: Optional[Path] = typer.Option(
        None,
        "--trace-path",
        help="Custom path for trace log (overrides default location)",
    ),
    description_mode: str = typer.Option(
        "notes-only",
        "--description-mode",
        help="CalTopo description content: notes-only (default) or debug",
    ),
    route_color_strategy: str = typer.Option(
        "palette",
        "--route-color-strategy",
        help="Route stroke color when OnX line color is missing: palette (default), default-blue, or none",
    ),
):
    """Migrate OnX Backcountry exports to CalTopo GeoJSON format.

    Interactive workflow to select files, review, and confirm.
    Removes duplicate waypoints and shapes automatically.

    \b
    Examples:
      cairn migrate onx-to-caltopo
      cairn migrate onx-to-caltopo ~/Downloads/OnX-exports
      cairn migrate onx-to-caltopo ~/Downloads/OnX-exports -o ./output

    \b
    Input: Directory with GPX (waypoints) and KML (polygons).
    Output: <name>.json for CalTopo import, plus dedup reports.

    \b
    Use --no-dedupe-waypoints or --no-dedupe-shapes to keep duplicates.
    """

    # 1. Validate input directory
    if input_dir is None:
        input_dir_str = typer.prompt("Path to directory with OnX exports")
        input_dir = Path(input_dir_str).expanduser()

    input_dir = input_dir.expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        console.print(f"[red]Directory not found: {input_dir}[/]")
        raise typer.Exit(1)

    # 2. Find export files
    gpx_files, kml_files = _find_export_files(input_dir)

    # 3. Interactive file selection
    gpx, kml = _select_files_interactive(gpx_files, kml_files)
    if gpx is None:
        console.print("[yellow]Migration cancelled[/]")
        raise typer.Exit(0)

    # 4. Determine output directory and base name
    if output_dir is None:
        output_dir = input_dir / "caltopo_ready"

    out_dir = ensure_output_dir(output_dir)
    base = (name or gpx.stem).strip() or gpx.stem

    # 5. Show confirmation summary
    if not _confirm_migration(gpx, kml, out_dir, base, dedupe_waypoints, dedupe_shapes):
        console.print("[yellow]Migration cancelled[/]")
        raise typer.Exit(0)

    primary_path = out_dir / f"{base}.json"
    dropped_shapes_path = out_dir / f"{base}_dropped_shapes.json"

    resolved_trace_path: Optional[Path]
    if not trace:
        resolved_trace_path = None
    elif trace_path is not None:
        resolved_trace_path = trace_path.expanduser()
        resolved_trace_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        resolved_trace_path = out_dir / f"{base}_trace.jsonl"

    trace_ctx = TraceWriter(resolved_trace_path) if resolved_trace_path else None
    try:
        if trace_ctx:
            trace_ctx.emit({"event": "run.start", "command": "migrate.OnX-to-caltopo"})

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Migrating OnX → CalTopo", total=7)

            progress.update(task, description="Reading GPX")
            try:
                doc = read_OnX_gpx(gpx, trace=trace_ctx)
            except ValueError as e:
                progress.stop()
                console.print(f"\n[bold red]❌ Error reading GPX file:[/]")
                console.print(f"[red]{e}[/]")
                raise typer.Exit(1)
            progress.advance(task)

            progress.update(task, description="Reading KML")
            try:
                kml_doc = read_onx_kml(kml, trace=trace_ctx)
            except ValueError as e:
                progress.stop()
                console.print(f"\n[bold red]❌ Error reading KML file:[/]")
                console.print(f"[red]{e}[/]")
                raise typer.Exit(1)
            progress.advance(task)

            progress.update(task, description="Merging GPX + KML (prefer polygons)")
            doc = merge_onx_gpx_and_kml(doc, kml_doc, trace=trace_ctx)
            progress.advance(task)

            # Icon inventory + mapping report (before dedup so it reflects incoming data)
            try:
                registry = IconRegistry()
                onx_icon_inventory = registry.collect_onx_icon_inventory(doc)
                onx_icon_rows = registry.collect_onx_icon_mapping_rows(doc)

                # Append to repo catalog (policy: append catalog only; no auto-mapping)
                registry.append_onx_icon_inventory_to_catalog(onx_icon_inventory)

                icon_report_path = out_dir / f"{base}_ICON_REPORT.md"
                write_icon_report_markdown(
                    output_path=icon_report_path,
                    title="OnX → CalTopo icon report",
                    rows=onx_icon_rows,
                    inventories=onx_icon_inventory,
                    notes=(
                        f"Mappings source: `{registry.mappings_path}`",
                        f"Catalog updated: `{registry.catalog_path}`",
                        "Counts reflect input after GPX+KML merge and before dedup.",
                    ),
                )
                if trace_ctx:
                    trace_ctx.emit(
                        {
                            "event": "icons.report",
                            "direction": "onx_to_caltopo",
                            "report_path": str(icon_report_path),
                            "unique_icons": len(onx_icon_inventory),
                        }
                    )
            except Exception as e:
                # Non-fatal: migration output should not depend on report/catalog.
                if trace_ctx:
                    trace_ctx.emit({"event": "icons.report.error", "error": str(e)})

            if trace_ctx:
                trace_ctx.emit({"event": "inventory.before_dedup", **document_inventory(doc)})

            # Check data quality and show warnings
            progress.update(task, description="Checking data quality")
            quality_warnings = check_data_quality(doc)
            if trace_ctx:
                trace_ctx.emit({"event": "data_quality.check", **quality_warnings})

            wp_report = None
            if dedupe_waypoints:
                progress.update(task, description="Deduplicating waypoints")
                wp_report = apply_waypoint_dedup(doc, trace=trace_ctx)
                if trace_ctx and wp_report is not None:
                    trace_ctx.emit({"event": "dedup.report", **dedup_inventory(wp_report)})
            else:
                progress.update(task, description="Skipping waypoint dedup")
            progress.advance(task)

            progress.update(task, description="Deduplicating shapes")
            shape_report = None
            dropped_items = []
            if dedupe_shapes:
                shape_report, dropped_items = apply_shape_dedup(doc, trace=trace_ctx)
            progress.advance(task)

            progress.update(task, description="Writing CalTopo GeoJSON")
            desc_mode_norm = (description_mode or "").strip().lower().replace("-", "_")
            if desc_mode_norm in ("notes_only", "notes"):
                desc_mode_norm = "notes_only"
            elif desc_mode_norm != "debug":
                raise typer.BadParameter("--description-mode must be one of: notes-only, debug")

            route_color_norm = (route_color_strategy or "").strip().lower().replace("-", "_")
            if route_color_norm == "defaultblue":
                route_color_norm = "default_blue"
            if route_color_norm not in ("palette", "default_blue", "none"):
                raise typer.BadParameter("--route-color-strategy must be one of: palette, default-blue, none")

            # Icon report + catalog (best-effort; never fails the migration)
            try:
                reg = IconRegistry()
                inventory = reg.collect_onx_icon_inventory(doc)
                rows = reg.collect_onx_icon_mapping_rows(doc)
                icon_report_path = out_dir / f"{base}_ICON_REPORT.md"
                write_icon_report_markdown(
                    output_path=icon_report_path,
                    title="OnX → CalTopo icon mapping report",
                    inventories=inventory,
                    rows=rows,
                    notes=(
                        [
                            f"Input GPX: `{gpx.name}`",
                            f"Input KML: `{kml.name if kml else 'None'}`",
                            f"Output GeoJSON: `{primary_path.name}`",
                        ]
                    ),
                )
                reg.append_onx_icon_inventory_to_catalog(inventory)
            except Exception as e:
                if trace_ctx:
                    trace_ctx.emit({"event": "icon_report.error", "error": str(e)})

            write_caltopo_geojson(
                doc,
                primary_path,
                trace=trace_ctx,
                description_mode=desc_mode_norm,  # type: ignore[arg-type]
                route_color_strategy=route_color_norm,  # type: ignore[arg-type]
            )

            # Validate output file was written successfully
            if not primary_path.exists():
                progress.stop()
                console.print(f"\n[bold red]❌ Error:[/] Failed to write primary output file")
                raise typer.Exit(1)

            primary_size = primary_path.stat().st_size
            if primary_size < 100:  # Suspiciously small file
                progress.stop()
                console.print(f"\n[yellow]⚠️  Warning:[/] Output file is very small ({primary_size} bytes)")
                console.print(f"[yellow]This may indicate data loss. Please verify the output.[/]")

            progress.advance(task)

            progress.update(task, description="Writing dropped-duplicates GeoJSON")
            dropped_doc = MapDocument(
                folders=list(doc.folders),
                items=list(dropped_items),
                metadata={"source": "cairn_shape_dedup_dropped", "primary": str(primary_path)},
            )
            write_caltopo_geojson(
                dropped_doc,
                dropped_shapes_path,
                trace=trace_ctx,
                description_mode=desc_mode_norm,  # type: ignore[arg-type]
                route_color_strategy=route_color_norm,  # type: ignore[arg-type]
            )

            # Validate secondary files were written
            if not dropped_shapes_path.exists():
                progress.stop()
                console.print(f"\n[yellow]⚠️  Warning:[/] Some output files may not have been written correctly")

            progress.advance(task)

        console.print("\n[bold green]Done.[/]")

        # Show data quality warnings if any
        if quality_warnings:
            if quality_warnings["empty_names"]:
                console.print(f"\n[yellow]⚠️  Found {len(quality_warnings['empty_names'])} item(s) with empty/default names[/]")
            if quality_warnings["duplicate_names"]:
                console.print(f"\n[yellow]⚠️  Found {len(quality_warnings['duplicate_names'])} duplicate name(s) (will be deduplicated if enabled)[/]")
            if quality_warnings["suspicious_coords"]:
                console.print(f"\n[yellow]⚠️  Found {len(quality_warnings['suspicious_coords'])} waypoint(s) with suspicious coordinates near (0,0)[/]")

        console.print("\n[bold]Created files:[/]")

        console.print("\nPrimary CalTopo-importable GeoJSON (deduped by default):")
        console.print(f"- [cyan]{_display_path(primary_path)}[/] [dim]({primary_size:,} bytes)[/]")

        dropped_size = dropped_shapes_path.stat().st_size if dropped_shapes_path.exists() else 0
        console.print("\nDropped duplicate shapes preserved as GeoJSON:")
        console.print(f"- [cyan]{_display_path(dropped_shapes_path)}[/] [dim]({dropped_size:,} bytes)[/]")

        if resolved_trace_path is not None:
            console.print("\nMachine-parseable trace log (JSON Lines) for debugging/replay:")
            console.print(f"- [cyan]{_display_path(resolved_trace_path)}[/]")

        icon_report_path = out_dir / f"{base}_ICON_REPORT.md"
        if icon_report_path.exists():
            console.print("\nIcon mapping report (incoming icons → mapped symbols + colors):")
            console.print(f"- [cyan]{_display_path(icon_report_path)}[/]")
    finally:
        if trace_ctx:
            trace_ctx.emit({"event": "run.end"})
            trace_ctx.close()


# Canonical name is lowercase `onx` (CLI-friendly).
@app.command("caltopo-to-OnX", hidden=True, deprecated=True)
@app.command("caltopo-to-onx")
def caltopo_to_OnX(
    input_dir: Optional[Path] = typer.Argument(
        None,
        help="Directory containing CalTopo GeoJSON export(s)",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory (defaults to <input-dir>/onx_ready)",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Custom icon mapping configuration file",
    ),
    no_sort: bool = typer.Option(
        False,
        "--no-sort",
        help="Preserve original order instead of natural sorting",
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
):
    """Migrate CalTopo GeoJSON exports to OnX-importable GPX/KML format.

    Interactive workflow to select file, validate, review, and confirm.
    Maps CalTopo symbols to OnX icons and preserves colors/styles.

    \b
    Examples:
      cairn migrate caltopo-to-onx
      cairn migrate caltopo-to-onx ~/Downloads/caltopo-exports
      cairn migrate caltopo-to-onx ~/Downloads/caltopo-exports -o ./output

    \b
    Input: Directory with CalTopo GeoJSON export file(s).
    Output: GPX files (waypoints/tracks) and KML files (polygons).

    \b
    Use --no-sort to preserve original order instead of natural sorting.
    """
    from cairn.commands.convert_cmd import (
        display_manifest,
        display_name_sanitization_warnings,
        display_unmapped_symbols,
        process_and_write_files,
    )
    from cairn.core.config import load_config
    from cairn.core.preview import preview_sorted_order, interactive_edit_before_export_per_folder
    from rich.prompt import Confirm
    from cairn.utils.utils import natural_sort_key
    import sys

    # 1. Validate input directory
    if input_dir is None:
        input_dir_str = typer.prompt("Path to directory with CalTopo exports")
        input_dir = Path(input_dir_str).expanduser()

    input_dir = input_dir.expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        console.print(f"[red]Directory not found: {input_dir}[/]")
        raise typer.Exit(1)

    # 2. Find GeoJSON files
    json_files = _find_geojson_files(input_dir)
    if not json_files:
        console.print(f"[red]No .json or .geojson files found in: {input_dir}[/]")
        raise typer.Exit(1)

    # 3. Interactive file selection
    selected_file = _select_geojson_interactive(json_files)
    if selected_file is None:
        console.print("[yellow]Migration cancelled[/]")
        raise typer.Exit(0)

    # 4. Validate selected GeoJSON
    valid, parsed_data = _validate_geojson_file(selected_file)
    if not valid or parsed_data is None:
        raise typer.Exit(1)

    # 5. Determine output directory
    if output_dir is None:
        output_dir = input_dir / "onx_ready"

    out_dir = ensure_output_dir(output_dir)

    # 6. Load icon mapping config
    config = load_config(config_file)

    # 7. Preview (and optional edit) before final confirmation
    sort_enabled = not no_sort

    console.print("\n[bold]Preview (what will be written for OnX)[/]")
    console.print("[dim]This shows the per-folder sorted order. You can optionally edit items next.[/]\n")

    # Show per-folder previews (tracks then waypoints) before any output is written.
    folder_items = list((getattr(parsed_data, "folders", {}) or {}).items())
    folder_items.sort(key=lambda kv: natural_sort_key(str((kv[1] or {}).get("name") or kv[0])))
    for _, folder_data in folder_items:
        folder_name = str(folder_data.get("name") or "")
        tracks = list(folder_data.get("tracks", []) or [])
        waypoints = list(folder_data.get("waypoints", []) or [])
        if sort_enabled:
            tracks = sorted(tracks, key=lambda f: natural_sort_key(f.title))
            waypoints = sorted(waypoints, key=lambda f: natural_sort_key(f.title))

        if tracks:
            preview_sorted_order(tracks, "tracks", folder_name, skip_confirmation=True, config=None)
        if waypoints:
            preview_sorted_order(waypoints, "waypoints", folder_name, skip_confirmation=True, config=config)

    # Only prompt for edits in interactive terminals (prevents EOF issues in non-interactive runs/tests).
    if sys.stdin is not None and getattr(sys.stdin, "isatty", lambda: False)():
        if Confirm.ask("Would you like to edit anything before export?", default=False):
            interactive_edit_before_export_per_folder(parsed_data, config, sort_enabled=sort_enabled)

    # 8. Display final migration summary and confirm (after edits)
    if not _confirm_caltopo_migration(selected_file, parsed_data, out_dir, sort_enabled):
        console.print("[yellow]Migration cancelled[/]")
        raise typer.Exit(0)

    # 9. Process and write files
    console.print(f"\n[bold white]Processing...[/]\n")

    # Icon report + catalog for CalTopo → OnX (best-effort; never fails the migration)
    try:
        registry = IconRegistry()
        inventory = registry.collect_caltopo_symbol_inventory(parsed_data)
        rows = registry.collect_caltopo_to_onx_mapping_rows_using_config(parsed_data, config)

        # Append to repo catalog (policy: append catalog only; no auto-mapping)
        registry.append_symbol_inventory_to_catalog(inventory)

        icon_report_path = out_dir / f"{selected_file.stem}_ICON_REPORT.md"
        write_icon_report_markdown(
            output_path=icon_report_path,
            title="CalTopo → OnX icon report",
            inventories=inventory,
            rows=rows,
            notes=(
                f"Input GeoJSON: `{selected_file.name}`",
                *(tuple([f"Config: `{config_file}`"]) if config_file else ()),
                f"Mappings source: `{registry.mappings_path}` (conversion uses runtime config, including user overrides)",
                f"Catalog updated: `{registry.catalog_path}`",
            ),
        )
    except Exception:
        # Migration should still succeed even if reporting fails.
        pass

    output_files = process_and_write_files(
        parsed_data,
        out_dir,
        sort=sort_enabled,
        skip_confirmation=True,  # Already confirmed
        config=config,
        split_gpx=split_gpx,
        max_gpx_bytes=int(max(0.0, float(max_gpx_mb)) * 1024 * 1024),
    )

    # 10. Display results
    if not output_files:
        console.print("[yellow]No files were created[/]")
        raise typer.Exit(1)

    console.print()
    display_manifest(output_files)

    # Display any unmapped symbols report
    display_unmapped_symbols(config)

    # Display name sanitization warnings
    display_name_sanitization_warnings()

    # Success footer
    console.print(f"\n[bold green]✔ SUCCESS[/] {len(output_files)} file(s) written to [underline]{out_dir}[/]")
    console.print("[dim]Next: Import these files into OnX Backcountry[/]\n")
