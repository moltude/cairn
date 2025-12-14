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


@app.command("onx-to-caltopo")
def onx_to_caltopo(
    gpx: Optional[Path] = typer.Option(
        None,
        "--gpx",
        help="onX GPX export (.gpx). If omitted, Cairn will prompt.",
    ),
    kml: Optional[Path] = typer.Option(
        None,
        "--kml",
        help="onX KML export (.kml). Required. If omitted, Cairn will prompt.",
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

    # Only prompt for the full set of inputs when the user runs the command "bare".
    interactive = gpx is None and kml is None and name is None

    gpx = _validate_existing_file(gpx, expected_suffix=".gpx", label="GPX")
    kml = _validate_existing_file(kml, expected_suffix=".kml", label="KML")

    if interactive:
        console.print("\n[bold]onX → CalTopo migration[/]\n")
        gpx = _prompt_existing_path("Path to onX GPX export", expected_suffix=".gpx")
        kml = _prompt_existing_path("Path to onX KML export", expected_suffix=".kml")
        output_dir = Path(typer.prompt("Output directory", default=str(output_dir))).expanduser()
        name = typer.prompt("Output base filename, no extension", default=gpx.stem).strip() or gpx.stem
    else:
        # In non-interactive mode, enforce required inputs.
        if gpx is None:
            raise typer.BadParameter("Missing --gpx (path/to/export.gpx)")
        if kml is None:
            raise typer.BadParameter("Missing --kml (path/to/export.kml)")

    out_dir = ensure_output_dir(output_dir)
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

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Migrating onX → CalTopo", total=7)

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
                kml_path=kml,
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
