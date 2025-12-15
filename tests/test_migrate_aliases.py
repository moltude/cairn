import json
from pathlib import Path

from typer.testing import CliRunner

from cairn.cli import app


runner = CliRunner()


def test_migrate_help_mentions_aliases():
    result = runner.invoke(app, ["migrate", "--help"])
    assert result.exit_code == 0
    out = result.stdout
    assert "onx" in out
    assert "caltopo" in out


def test_migrate_onx_accepts_geojson_file(tmp_path: Path):
    # Minimal CalTopo-ish export with one marker feature.
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "w1",
                "geometry": {"type": "Point", "coordinates": [-120.0, 45.0]},
                "properties": {
                    "class": "Marker",
                    "title": "Test Waypoint",
                    "marker-color": "#FF0000",
                    "marker-symbol": "campsite",
                },
            }
        ],
    }
    in_file = tmp_path / "export.json"
    in_file.write_text(json.dumps(fc), encoding="utf-8")

    # Prompts:
    # - Proceed via final gate (default yes) -> blank line
    result = runner.invoke(app, ["migrate", "onx", str(in_file)], input="\n")
    assert result.exit_code == 0, result.stdout

    out_dir = tmp_path / "onx_ready"
    assert out_dir.exists()
    assert list(out_dir.glob("*.gpx")), "Expected GPX output in onx_ready/"


def test_migrate_caltopo_accepts_gpx_file(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    demo_dir = repo_root / "demo" / "onx-to-caltopo" / "onx-export"
    gpx_src = demo_dir / "onx-export.gpx"
    kml_src = demo_dir / "onx-to-caltopo" / "onx-export" / "onx-export.kml"
    # Some repos name the KML alongside; tolerate missing KML.
    if not kml_src.exists():
        kml_src = demo_dir / "onx-export.kml"

    in_file = tmp_path / gpx_src.name
    in_file.write_text(gpx_src.read_text(encoding="utf-8"), encoding="utf-8")
    if kml_src.exists():
        (tmp_path / kml_src.name).write_text(kml_src.read_text(encoding="utf-8"), encoding="utf-8")

    # Prompts:
    # - Select GPX (default 1) -> blank
    # - Select KML (default 1) -> blank (if present)
    # - Ready to generate new map? (default yes) -> blank
    inputs = "\n\n\n" if kml_src.exists() else "\n\n"
    result = runner.invoke(app, ["migrate", "caltopo", str(in_file)], input=inputs)
    assert result.exit_code == 0, result.stdout

    out_dir = tmp_path / "caltopo_ready"
    assert out_dir.exists()
    assert list(out_dir.glob("*.json")), "Expected GeoJSON outputs in caltopo_ready/"
