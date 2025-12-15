import json
from pathlib import Path

from cairn.core.dedup import apply_waypoint_dedup
from cairn.core.trace import TraceReader, TraceWriter
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.io.caltopo_geojson import write_caltopo_geojson
from cairn.io.onx_gpx import read_OnX_gpx
from cairn.io.onx_kml import read_onx_kml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fixture_gpx() -> Path:
    return _repo_root() / "docs" / "caltopo-refactor" / "text-OnX-export-caltopo-import.gpx"

def _demo_OnX_export_dir() -> Path:
    return _repo_root() / "demo" / "onx-to-caltopo" / "onx-export"


def _demo_OnX_gpx() -> Path:
    return _demo_OnX_export_dir() / "onx-export.gpx"


def _demo_OnX_kml() -> Path:
    return _demo_OnX_export_dir() / "onx-export.kml"


def test_read_OnX_gpx_parses_waypoints_and_extensions():
    doc = read_OnX_gpx(_fixture_gpx())
    assert len(doc.waypoints()) > 0

    # At least one waypoint should have OnX metadata preserved.
    assert any((wp.style.OnX_icon or "").strip() for wp in doc.waypoints())
    assert any((wp.style.OnX_color_rgba or "").strip() for wp in doc.waypoints())


def test_read_OnX_gpx_normalizes_double_escaped_entities():
    doc = read_OnX_gpx(_fixture_gpx())
    names = [wp.name for wp in doc.waypoints()]

    # We observed '&amp;apos;' in raw GPX exports; normalize should decode to a plain apostrophe.
    assert any("Joseph's" in n for n in names)
    assert not any("&apos;" in n or "&amp;" in n for n in names)


def test_dedup_drops_duplicate_waypoints():
    doc = read_OnX_gpx(_fixture_gpx())
    before = len(doc.waypoints())
    report = apply_waypoint_dedup(doc)
    after = len(doc.waypoints())

    assert report.dropped_count > 0
    assert before - after == report.dropped_count


def test_write_caltopo_geojson_includes_folders_and_OnX_metadata(tmp_path: Path):
    doc = read_OnX_gpx(_fixture_gpx())
    apply_waypoint_dedup(doc)

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["type"] == "FeatureCollection"
    feats = data["features"]
    assert len(feats) > 0

    folder_feats = [f for f in feats if f.get("properties", {}).get("class") == "Folder"]
    marker_feats = [f for f in feats if f.get("properties", {}).get("class") == "Marker"]
    shape_feats = [f for f in feats if f.get("properties", {}).get("class") == "Shape"]

    assert len(folder_feats) >= 1
    assert len(marker_feats) >= 1

    # Validate marker fields are CalTopo-like and preserve OnX details in description.
    m = marker_feats[0]
    props = m["properties"]
    assert props["marker-color"].startswith("#")
    assert "marker-symbol" in props
    assert "folderId" in props
    desc = props.get("description", "")
    assert "cairn:source=" in desc
    assert "OnX:color=" in desc or "OnX:icon=" in desc


def test_trace_log_emits_expected_events(tmp_path: Path):
    trace_path = tmp_path / "trace.jsonl"
    out = tmp_path / "out.json"

    with TraceWriter(trace_path) as trace:
        doc = read_OnX_gpx(_fixture_gpx(), trace=trace)
        apply_waypoint_dedup(doc, trace=trace)
        write_caltopo_geojson(doc, out, trace=trace)

    events = list(TraceReader(trace_path))
    event_types = {e.get("event") for e in events}
    assert "input.wpt" in event_types
    # Dedup is data-dependent but our fixture has duplicates, so expect a group event.
    assert "dedup.group" in event_types
    assert "output.feature" in event_types


def test_read_OnX_kml_parses_polygons():
    doc = read_onx_kml(_demo_OnX_kml())
    assert len(doc.shapes()) > 0


def test_merge_OnX_gpx_and_kml_sets_metadata_and_preserves_polygons():
    gpx_doc = read_OnX_gpx(_demo_OnX_gpx())
    kml_doc = read_onx_kml(_demo_OnX_kml())
    merged = merge_onx_gpx_and_kml(gpx_doc, kml_doc)

    assert merged.metadata.get("merged_kml") is True
    assert merged.metadata.get("kml_path")
    assert len(merged.shapes()) >= len(kml_doc.shapes()) > 0
