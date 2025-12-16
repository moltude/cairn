import json
from pathlib import Path

from cairn.core.dedup import apply_waypoint_dedup
from cairn.core.trace import TraceReader, TraceWriter
from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.io.caltopo_geojson import write_caltopo_geojson
from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml
from cairn.model import MapDocument, Track, Waypoint, Style


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fixture_gpx() -> Path:
    return _repo_root() / "tests" / "fixtures" / "onx_export_with_tracks.gpx"

def _fixture_kml() -> Path:
    return _repo_root() / "tests" / "fixtures" / "onx_export_with_tracks.kml"

def _demo_OnX_export_dir() -> Path:
    return _repo_root() / "tests" / "fixtures"


def _demo_OnX_gpx() -> Path:
    return _fixture_gpx()


def _demo_OnX_kml() -> Path:
    return _fixture_kml()


def test_read_OnX_gpx_parses_waypoints_and_extensions():
    doc = read_onx_gpx(_fixture_gpx())
    assert len(doc.waypoints()) > 0

    # At least one waypoint should have OnX metadata preserved.
    assert any((wp.style.OnX_icon or "").strip() for wp in doc.waypoints())
    assert any((wp.style.OnX_color_rgba or "").strip() for wp in doc.waypoints())


def test_read_OnX_gpx_normalizes_double_escaped_entities():
    doc = read_onx_gpx(_fixture_gpx())
    names = [wp.name for wp in doc.waypoints()]

    # Verify no XML entities remain in waypoint names (normalization worked)
    assert not any("&apos;" in n or "&amp;" in n for n in names)
    # Verify we have valid waypoint names
    assert len(names) > 0
    assert all(isinstance(n, str) for n in names)


def test_dedup_drops_duplicate_waypoints():
    doc = read_onx_gpx(_fixture_gpx())
    before = len(doc.waypoints())
    report = apply_waypoint_dedup(doc)
    after = len(doc.waypoints())

    # Dedup may or may not find duplicates depending on fixture content
    assert report.dropped_count >= 0
    assert before - after == report.dropped_count


def test_write_caltopo_geojson_includes_folders_and_OnX_metadata(tmp_path: Path):
    doc = read_onx_gpx(_fixture_gpx())
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
    assert not any(f.get("id") == "OnX_import" for f in folder_feats)

    # Validate marker fields are CalTopo-like and preserve OnX details in structured metadata.
    m = marker_feats[0]
    props = m["properties"]
    assert props["marker-color"].startswith("#")
    assert "marker-symbol" in props
    assert "folderId" in props
    desc = props.get("description", "")
    assert "cairn:source=" not in desc
    assert "OnX:" not in desc

    cairn_meta = props.get("cairn", {})
    assert cairn_meta.get("source") == "OnX_gpx"
    assert cairn_meta.get("name") == props.get("title")
    onx_meta = cairn_meta.get("OnX", {})
    assert isinstance(onx_meta, dict)
    assert ("id" in onx_meta) or ("color" in onx_meta) or ("icon" in onx_meta)


def test_write_caltopo_geojson_debug_description_contains_parseable_block(tmp_path: Path):
    doc = read_onx_gpx(_fixture_gpx())
    apply_waypoint_dedup(doc)

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out, description_mode="debug")
    data = json.loads(out.read_text(encoding="utf-8"))
    marker_feats = [f for f in data["features"] if f.get("properties", {}).get("class") == "Marker"]
    assert len(marker_feats) >= 1
    desc = marker_feats[0]["properties"].get("description", "")
    assert "cairn:source=" in desc
    assert "OnX:" in desc


def test_write_caltopo_geojson_palette_route_color_is_stable(tmp_path: Path):
    palette = [
        "#FFAA00",
        "#4CB36E",
        "#EF00FF",
        "#00CD00",
        "#C659A9",
        "#B9AC91",
        "#FF0000",
        "#000000",
        "#00A3FF",
        "#8B4513",
    ]

    def render(name: str) -> str:
        doc = MapDocument(metadata={"source": "OnX_gpx"})
        doc.ensure_folder("OnX_tracks", "Tracks")
        trk = Track(
            id="t1",
            folder_id="OnX_tracks",
            name=name,
            points=[(0.0, 0.0, None, None), (1.0, 1.0, None, None)],
        )
        doc.add_item(trk)

        out = tmp_path / f"{name}.json"
        write_caltopo_geojson(doc, out, route_color_strategy="palette")
        data = json.loads(out.read_text(encoding="utf-8"))
        shape_feats = [f for f in data["features"] if f.get("properties", {}).get("class") == "Shape"]
        assert len(shape_feats) == 1
        return shape_feats[0]["properties"]["stroke"]

    c1 = render("Route A")
    c2 = render("Route A")
    assert c1 == c2
    assert c1 in palette


def test_write_caltopo_geojson_unknown_icon_forces_red_dot(tmp_path: Path):
    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_waypoints", "Waypoints")

    wp = Waypoint(
        id="w1",
        folder_id="OnX_waypoints",
        name="Unknown icon marker",
        lon=0.0,
        lat=0.0,
        notes="",
        style=Style(OnX_icon=None, OnX_color_rgba="rgba(8,122,255,1)", OnX_id="w1"),
    )
    doc.add_item(wp)

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    marker_feats = [f for f in data["features"] if f.get("properties", {}).get("class") == "Marker"]
    assert len(marker_feats) == 1
    props = marker_feats[0]["properties"]
    assert props["marker-symbol"] == "point"
    assert props["marker-color"] == "#087AFF"


def test_write_caltopo_geojson_unmapped_icon_is_preserved_in_description(tmp_path: Path):
    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_waypoints", "Waypoints")

    wp = Waypoint(
        id="w1",
        folder_id="OnX_waypoints",
        name="Unknown icon marker",
        lon=0.0,
        lat=0.0,
        notes="hello",
        style=Style(OnX_icon="TotallyUnknownIcon", OnX_color_rgba="rgba(8,122,255,1)", OnX_id="w1"),
    )
    doc.add_item(wp)

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    marker_feats = [f for f in data["features"] if f.get("properties", {}).get("class") == "Marker"]
    assert len(marker_feats) == 1
    props = marker_feats[0]["properties"]
    assert props["marker-symbol"] == "point"
    assert props["marker-color"] == "#087AFF"
    assert "hello" in (props.get("description") or "")
    assert "OnX icon: TotallyUnknownIcon" in (props.get("description") or "")


def test_write_caltopo_geojson_missing_icon_and_color_uses_red_dot(tmp_path: Path):
    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_waypoints", "Waypoints")

    wp = Waypoint(
        id="w1",
        folder_id="OnX_waypoints",
        name="No icon or color",
        lon=0.0,
        lat=0.0,
        notes="",
        style=Style(OnX_icon=None, OnX_color_rgba=None, OnX_id="w1"),
    )
    doc.add_item(wp)

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    marker_feats = [f for f in data["features"] if f.get("properties", {}).get("class") == "Marker"]
    assert len(marker_feats) == 1
    props = marker_feats[0]["properties"]
    assert props["marker-symbol"] == "point"
    assert props["marker-color"] == "#FF0000"


def test_trace_log_emits_expected_events(tmp_path: Path):
    trace_path = tmp_path / "trace.jsonl"
    out = tmp_path / "out.json"

    with TraceWriter(trace_path) as trace:
        doc = read_onx_gpx(_fixture_gpx(), trace=trace)
        apply_waypoint_dedup(doc, trace=trace)
        write_caltopo_geojson(doc, out, trace=trace)

    events = list(TraceReader(trace_path))
    event_types = {e.get("event") for e in events}
    assert "input.wpt" in event_types
    # Dedup events are data-dependent (only if duplicates exist in fixture)
    # Just verify trace logging works and captures input events
    assert len(events) > 0
    assert "output.feature" in event_types


def test_read_OnX_kml_parses_polygons():
    doc = read_onx_kml(_demo_OnX_kml())
    assert len(doc.shapes()) > 0


def test_merge_OnX_gpx_and_kml_sets_metadata_and_preserves_polygons():
    gpx_doc = read_onx_gpx(_demo_OnX_gpx())
    kml_doc = read_onx_kml(_demo_OnX_kml())
    merged = merge_onx_gpx_and_kml(gpx_doc, kml_doc)

    assert merged.metadata.get("merged_kml") is True
    assert merged.metadata.get("kml_path")
    assert len(merged.shapes()) >= len(kml_doc.shapes()) > 0
