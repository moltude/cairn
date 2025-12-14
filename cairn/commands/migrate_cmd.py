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


@app.command("onx-to-caltopo")
def onx_to_caltopo(
    gpx: Path = typer.Argument(..., help="onX GPX export (.gpx)"),
    kml: Optional[Path] = typer.Option(
        None,
        "--kml",
        help="Optional onX KML export (.kml). Strongly recommended for areas/polygons.",
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
    trace: Optional[Path] = typer.Option(
        None,
        "--trace",
        help="Write JSONL trace log for debugging/replay",
    ),
):
    """
    Migrate an onX Backcountry export into a CalTopo-importable GeoJSON.

    Outputs:
    - <name>.json (primary, deduped by default)
    - <name>_dropped_shapes.json (secondary, dropped duplicates)
    - <name>_SUMMARY.md (human-readable explanation of dedup choices)
    - optional trace JSONL
    """
    if not gpx.exists():
        raise typer.BadParameter(f"GPX file not found: {gpx}")
    if kml is not None and not kml.exists():
        raise typer.BadParameter(f"KML file not found: {kml}")

    out_dir = ensure_output_dir(output_dir)
    base = (name or gpx.stem).strip()
    if not base:
        base = gpx.stem

    primary_path = out_dir / f"{base}.json"
    dropped_shapes_path = out_dir / f"{base}_dropped_shapes.json"
    summary_path = out_dir / f"{base}_SUMMARY.md"

    trace_ctx = TraceWriter(trace) if trace else None
    try:
        if trace_ctx:
            trace_ctx.emit({"event": "run.start", "command": "migrate.onx-to-caltopo"})

        doc = read_onx_gpx(gpx, trace=trace_ctx)
        if kml is not None:
            kml_doc = read_onx_kml(kml, trace=trace_ctx)
            doc = merge_onx_gpx_and_kml(doc, kml_doc, trace=trace_ctx)

        if trace_ctx:
            trace_ctx.emit({"event": "inventory.before_dedup", **document_inventory(doc)})

        wp_report = None
        if dedupe_waypoints:
            wp_report = apply_waypoint_dedup(doc, trace=trace_ctx)
            if trace_ctx and wp_report is not None:
                trace_ctx.emit({"event": "dedup.report", **dedup_inventory(wp_report)})

        shape_report = None
        dropped_items = []
        if dedupe_shapes:
            shape_report, dropped_items = apply_shape_dedup(doc, trace=trace_ctx)

        write_caltopo_geojson(doc, primary_path, trace=trace_ctx)

        # Preserve dropped shapes in a separate file even if empty for predictability.
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
    finally:
        if trace_ctx:
            trace_ctx.emit({"event": "run.end"})
            trace_ctx.close()
