"""
Migration-focused CLI commands.

These are thin wrappers around the conversion pipeline that prioritize:
- clear intent (one command per migration direction)
- sensible defaults (dedupe on, polygon preference)
- predictable output locations and filenames
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from cairn.core.dedup import apply_waypoint_dedup
from cairn.core.diagnostics import dedup_inventory, document_inventory
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.core.shape_dedup import apply_shape_dedup
from cairn.core.shape_dedup_summary import write_shape_dedup_summary
from cairn.core.trace import TraceWriter
from cairn.io.caltopo_geojson import write_caltopo_geojson
from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.model import MapDocument
from cairn.utils.utils import ensure_output_dir


app = typer.Typer(no_args_is_help=True)
console = Console()


def _prompt_existing_path(
    label: str,
    *,
    default: Optional[Path] = None,
    expected_suffix: Optional[str] = None,
) -> Path:
    while True:
        entered = typer.prompt(label, default=str(default) if default is not None else None)
        p = Path(str(entered)).expanduser()
        if expected_suffix is not None and p.suffix.lower() != expected_suffix.lower():
            console.print(f"[bold red]Expected a {expected_suffix} file:[/] {p}")
            continue
        if p.exists():
            return p
        console.print(f"[bold red]File not found:[/] {p}")


def _display_path(p: Path) -> str:
    """
    Display-friendly path for CLI output.

    Preference order:
    - relative path from CWD when possible
    - otherwise just the basename
    """
    try:
        rel = p.resolve().relative_to(Path.cwd().resolve())
        return str(rel)
    except Exception:
        return p.name


@app.command("onx-to-caltopo")
def onx_to_caltopo(
    gpx_arg: Optional[Path] = typer.Argument(
        None,
        help="onX GPX export (.gpx) (deprecated: pass as --gpx)",
    ),
    gpx_file: Optional[Path] = typer.Option(
        None,
        "--gpx",
        help="onX GPX export (.gpx)",
    ),
    kml: Optional[Path] = typer.Option(
        None,
        "--kml",
        help="onX KML export (.kml). Required for best fidelity (polygons/areas).",
    ),
    output_dir: Path = typer.Option(
        Path("./caltopo_ready"),
        "--output-dir",
        "-o",
        help="Output directory to write CalTopo-importable GeoJSON and reports",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Base filename (without extension) for outputs. Defaults to GPX stem.",
    ),
    dedupe_waypoints: bool = typer.Option(
        True,
        "--dedupe-waypoints/--no-dedupe-waypoints",
        help="Deduplicate waypoints by fuzzy (name + rounded lat/lon) match (default: enabled)",
    ),
    dedupe_shapes: bool = typer.Option(
        True,
        "--dedupe-shapes/--no-dedupe-shapes",
        help="Deduplicate shapes (polygons/lines) by fuzzy geometry match (default: enabled)",
    ),
    trace: bool = typer.Option(
        True,
        "--trace/--no-trace",
        help="Write JSONL trace log into the output directory (default: enabled)",
    ),
    trace_path: Optional[Path] = typer.Option(
        None,
        "--trace-path",
        help="Optional explicit path for the trace log (overrides default output-dir location)",
    ),
):
    """
    Migrate an onX Backcountry export into a CalTopo-importable GeoJSON.

    Outputs:
    - <name>.json (primary, deduped by default)
    - <name>_dropped_shapes.json (secondary, dropped duplicates)
    - <name>_SUMMARY.md (human-readable explanation of dedup choices)
    - <name>_trace.jsonl (trace log; default enabled)
    """
    if gpx_arg is not None and gpx_file is not None and gpx_arg != gpx_file:
        raise typer.BadParameter("Provide GPX via positional argument OR --gpx (not both).")

    interactive = (gpx_file is None and gpx_arg is None)

    # Interactive prompts when not provided.
    gpx = gpx_file or gpx_arg
    if gpx is None:
        gpx = _prompt_existing_path("Path to onX GPX export", expected_suffix=".gpx")
    else:
        gpx = gpx.expanduser()
        if gpx.suffix.lower() != ".gpx":
            raise typer.BadParameter(f"Expected a .gpx file: {gpx}")
        if not gpx.exists():
            raise typer.BadParameter(f"GPX file not found: {gpx}")

    # KML is required (for polygons/areas). Prompt if missing.
    if kml is None:
        kml = _prompt_existing_path("Path to onX KML export", expected_suffix=".kml")
    kml = kml.expanduser()
    if kml.suffix.lower() != ".kml":
        raise typer.BadParameter(f"Expected a .kml file: {kml}")
    if not kml.exists():
        raise typer.BadParameter(f"KML file not found: {kml}")

    # Prompt for outputs (with sensible defaults) when running interactively.
    if interactive:
        output_dir = Path(typer.prompt("Output directory", default=str(output_dir))).expanduser()

    output_dir = output_dir.expanduser()
    out_dir = ensure_output_dir(output_dir)

    default_name = gpx.stem
    if name is None and interactive:
        name = typer.prompt("Output base filename, no extension", default=default_name).strip() or default_name
    elif name is None:
        name = default_name

    base = (name or gpx.stem).strip() or gpx.stem

    primary_path = out_dir / f"{base}.json"
    dropped_shapes_path = out_dir / f"{base}_dropped_shapes.json"
    summary_path = out_dir / f"{base}_SUMMARY.md"

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
            trace_ctx.emit({"event": "run.start", "command": "migrate.onx-to-caltopo"})
        steps_total = 7
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Migrating onX → CalTopo", total=steps_total)

            progress.update(task, description="Reading GPX")
            doc = read_onx_gpx(gpx, trace=trace_ctx)
            progress.advance(task)

            progress.update(task, description="Reading KML")
            kml_doc = read_onx_kml(kml, trace=trace_ctx)
            progress.advance(task)

            progress.update(task, description="Merging GPX + KML (prefer polygons)")
            doc = merge_onx_gpx_and_kml(doc, kml_doc, trace=trace_ctx)
            progress.advance(task)

            if trace_ctx:
                trace_ctx.emit({"event": "inventory.before_dedup", **document_inventory(doc)})

            wp_report = None
            if dedupe_waypoints:
                progress.update(task, description="Deduplicating waypoints")
                wp_report = apply_waypoint_dedup(doc, trace=trace_ctx)
                if trace_ctx and wp_report is not None:
                    trace_ctx.emit({"event": "dedup.report", **dedup_inventory(wp_report)})
                progress.advance(task)
            else:
                progress.update(task, description="Skipping waypoint dedup")
                progress.advance(task)

            shape_report = None
            dropped_items = []
            progress.update(task, description="Deduplicating shapes")
            if dedupe_shapes:
                shape_report, dropped_items = apply_shape_dedup(doc, trace=trace_ctx)
            progress.advance(task)

            progress.update(task, description="Writing CalTopo GeoJSON")
            write_caltopo_geojson(doc, primary_path, trace=trace_ctx)
            progress.advance(task)

            progress.update(task, description="Writing dropped-duplicates GeoJSON + summary")
            dropped_doc = MapDocument(
                folders=list(doc.folders),
                items=list(dropped_items),
                metadata={"source": "cairn_shape_dedup_dropped", "primary": str(primary_path)},
            )
            write_caltopo_geojson(dropped_doc, dropped_shapes_path, trace=trace_ctx)

            write_shape_dedup_summary(
                summary_path,
                report=(shape_report or type("Empty", (), {"groups": [], "dropped_count": 0})()),
                primary_geojson_path=primary_path,
                dropped_geojson_path=dropped_shapes_path,
                gpx_path=gpx,
                kml_path=(kml or ""),
                waypoint_dedup_dropped=(wp_report.dropped_count if wp_report is not None else 0),
            )
            progress.advance(task)

        console.print("\n[bold green]Done.[/]")
        console.print("\n[bold]Created files:[/]")

        console.print("\nPrimary CalTopo-importable GeoJSON (deduped by default):")
        console.print(f"- [cyan]{_display_path(primary_path)}[/]")

        console.print("\nDropped duplicate shapes preserved as GeoJSON:")
        console.print(f"- [cyan]{_display_path(dropped_shapes_path)}[/]")

        console.print("\nHuman-readable explanation of dedup decisions:")
        console.print(f"- [cyan]{_display_path(summary_path)}[/]")

        if resolved_trace_path is not None:
            console.print("\nMachine-parseable trace log (JSON Lines) for debugging/replay:")
            console.print(f"- [cyan]{_display_path(resolved_trace_path)}[/]")
    finally:
        if trace_ctx:
            trace_ctx.emit({"event": "run.end"})
            trace_ctx.close()
