"""
Human-readable summary writer for shape dedup runs.

User explicitly requested a SUMMARY.md that explains each dedup decision.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from cairn.core.shape_dedup import ShapeDedupReport


def write_shape_dedup_summary(
    output_path: str | Path,
    *,
    report: ShapeDedupReport,
    primary_geojson_path: str | Path,
    dropped_geojson_path: str | Path,
    gpx_path: str | Path,
    kml_path: str | Path,
    waypoint_dedup_dropped: int = 0,
) -> Path:
    out = Path(output_path)
    primary_geojson_path = Path(primary_geojson_path)
    dropped_geojson_path = Path(dropped_geojson_path)

    lines = []
    lines.append("## Cairn shape dedup summary")
    lines.append("")
    lines.append("This file explains why some shapes were removed from the primary CalTopo import file.")
    lines.append("Nothing is deleted permanently: every dropped feature is preserved in the secondary GeoJSON.")
    lines.append("")
    lines.append("### Inputs")
    lines.append(f"- **GPX**: `{gpx_path}`")
    lines.append(f"- **KML**: `{kml_path}`")
    lines.append("")
    lines.append("### Outputs")
    lines.append(f"- **Primary (deduped)**: `{primary_geojson_path}`")
    lines.append(f"- **Secondary (dropped duplicates)**: `{dropped_geojson_path}`")
    lines.append("")
    lines.append("### Dedup policy")
    lines.append("- **Polygon preference**: when the same onX id exists as both a route/track (GPX) and a polygon (KML), we keep the polygon and drop the line to avoid CalTopo id collisions.")
    lines.append("- **Shape dedup default**: enabled (can be disabled via `--no-dedupe-shapes`).")
    lines.append("- **Fuzzy match definition**:")
    lines.append("  - **Polygons**: round coordinates to 6 decimals; ignore ring start index; ignore ring direction.")
    lines.append("  - **Lines**: round coordinates to 6 decimals; treat reversed line as equivalent.")
    lines.append("")
    lines.append("### Dedup results")
    lines.append(f"- **Waypoint dedup dropped**: {waypoint_dedup_dropped}")
    lines.append(f"- **Shape dedup groups**: {len(report.groups)}")
    lines.append(f"- **Shape dedup dropped features**: {report.dropped_count}")
    lines.append("")
    lines.append("### Per-group decisions")
    lines.append("")
    if not report.groups:
        lines.append("_No shape duplicates were detected under the fuzzy-match policy._")
    else:
        for g in report.groups:
            lines.append(f"- **{g.kind}** `{g.title}`")
            lines.append(f"  - **kept**: `{g.kept_id}`")
            lines.append(f"  - **dropped ({len(g.dropped_ids)})**: " + ", ".join(f"`{x}`" for x in g.dropped_ids))
            lines.append(f"  - **reason**: {g.reason}")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out
