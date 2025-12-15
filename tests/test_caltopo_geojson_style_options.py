import json
from pathlib import Path

from cairn.io.caltopo_geojson import write_caltopo_geojson
from cairn.model import MapDocument, Shape, Track


def test_route_color_strategy_none_omits_stroke_for_tracks(tmp_path: Path):
    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_tracks", "Tracks")
    doc.add_item(
        Track(
            id="t1",
            folder_id="OnX_tracks",
            name="NoColorTrack",
            points=[(0.0, 0.0, None, None), (1.0, 1.0, None, None)],
        )
    )

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out, route_color_strategy="none")
    data = json.loads(out.read_text(encoding="utf-8"))
    shapes = [f for f in data["features"] if f.get("properties", {}).get("class") == "Shape"]
    assert len(shapes) == 1
    assert "stroke" not in shapes[0]["properties"]


def test_route_color_strategy_default_blue_sets_stroke_for_tracks(tmp_path: Path):
    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_tracks", "Tracks")
    doc.add_item(
        Track(
            id="t1",
            folder_id="OnX_tracks",
            name="NoColorTrack",
            points=[(0.0, 0.0, None, None), (1.0, 1.0, None, None)],
        )
    )

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out, route_color_strategy="default_blue")
    data = json.loads(out.read_text(encoding="utf-8"))
    shapes = [f for f in data["features"] if f.get("properties", {}).get("class") == "Shape"]
    assert len(shapes) == 1
    assert shapes[0]["properties"]["stroke"] == "#0000FF"


def test_route_color_strategy_none_omits_stroke_for_polygons(tmp_path: Path):
    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_shapes", "Areas")
    doc.add_item(
        Shape(
            id="s1",
            folder_id="OnX_shapes",
            name="NoColorPoly",
            rings=[[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]],
        )
    )

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out, route_color_strategy="none")
    data = json.loads(out.read_text(encoding="utf-8"))
    shapes = [f for f in data["features"] if f.get("properties", {}).get("class") == "Shape"]
    assert len(shapes) == 1
    assert "stroke" not in shapes[0]["properties"]


def test_route_color_strategy_palette_empty_name_uses_first_palette_color(tmp_path: Path):
    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_tracks", "Tracks")
    doc.add_item(
        Track(
            id="t1",
            folder_id="OnX_tracks",
            name="",
            points=[(0.0, 0.0, None, None), (1.0, 1.0, None, None)],
        )
    )

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out, route_color_strategy="palette")
    data = json.loads(out.read_text(encoding="utf-8"))
    shapes = [f for f in data["features"] if f.get("properties", {}).get("class") == "Shape"]
    assert len(shapes) == 1
    assert shapes[0]["properties"]["stroke"] == "#FFAA00"


def test_route_color_strategy_default_blue_sets_stroke_for_polygons(tmp_path: Path):
    doc = MapDocument(metadata={"source": "OnX_gpx"})
    doc.ensure_folder("OnX_shapes", "Areas")
    doc.add_item(
        Shape(
            id="s1",
            folder_id="OnX_shapes",
            name="NoColorPoly",
            rings=[[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]],
        )
    )

    out = tmp_path / "out.json"
    write_caltopo_geojson(doc, out, route_color_strategy="default_blue")
    data = json.loads(out.read_text(encoding="utf-8"))
    shapes = [f for f in data["features"] if f.get("properties", {}).get("class") == "Shape"]
    assert len(shapes) == 1
    assert shapes[0]["properties"]["stroke"] == "#0000FF"
