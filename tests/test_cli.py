"""Integration tests for cairn CLI."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cairn.cli import app


runner = CliRunner()


class TestCLI:
    """Integration tests for CLI commands."""

    def test_help(self):
        """--help works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "CalTopo" in result.stdout or "caltopo" in result.stdout.lower()

    def test_convert_help(self):
        """convert --help works."""
        result = runner.invoke(app, ["convert", "--help"])
        assert result.exit_code == 0
        assert "INPUT_FILE" in result.stdout or "input" in result.stdout.lower()
        # Default output directory should be lowercase for portability/consistency.
        assert "./onx_ready" in result.stdout

    def test_migrate_help(self):
        """migrate --help works."""
        result = runner.invoke(app, ["migrate", "--help"])
        assert result.exit_code == 0
        # Canonical commands are lowercase.
        assert "onx-to-caltopo" in result.stdout
        assert "caltopo-to-onx" in result.stdout
        # Deprecated aliases should be hidden from the command list.
        assert "OnX-to-caltopo" not in result.stdout
        assert "caltopo-to-OnX" not in result.stdout

    def test_migrate_OnX_to_caltopo_help(self):
        """migrate onx-to-caltopo --help works."""
        result = runner.invoke(app, ["migrate", "onx-to-caltopo", "--help"])
        assert result.exit_code == 0
        out = result.stdout.lower()
        assert "onx" in out and "caltopo" in out
        assert "OnX_ready" not in result.stdout

    def test_migrate_OnX_to_caltopo_help_deprecated_alias(self):
        result = runner.invoke(app, ["migrate", "OnX-to-caltopo", "--help"])
        assert result.exit_code == 0
        assert "(deprecated)" in result.stdout

    def test_migrate_caltopo_to_onx_help(self):
        result = runner.invoke(app, ["migrate", "caltopo-to-onx", "--help"])
        assert result.exit_code == 0
        assert "onx_ready" in result.stdout
        assert "OnX_ready" not in result.stdout

    def test_migrate_caltopo_to_onx_help_deprecated_alias(self):
        result = runner.invoke(app, ["migrate", "caltopo-to-OnX", "--help"])
        assert result.exit_code == 0
        assert "(deprecated)" in result.stdout

    def test_config_help(self):
        """config --help works."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_convert_missing_file(self):
        """convert with missing file shows error."""
        result = runner.invoke(app, ["convert", "nonexistent_file.json"])
        assert result.exit_code != 0 or "error" in result.stdout.lower() or "not found" in result.stdout.lower()

    def test_migrate_caltopo_to_onx_default_output_dir_is_lowercase(self, tmp_path: Path):
        """
        Regression test: default output directory should be <input-dir>/onx_ready (lowercase).
        """
        # Build a minimal CalTopo-ish export with at least one marker feature.
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
        (tmp_path / "export.json").write_text(json.dumps(fc), encoding="utf-8")

        # Interactive prompts:
        # - Select file number (default 1) -> blank line
        # - Proceed with migration? (default yes) -> blank line
        result = runner.invoke(app, ["migrate", "caltopo-to-onx", str(tmp_path)], input="\n\n")
        assert result.exit_code == 0, result.stdout

        out_dir = tmp_path / "onx_ready"
        assert out_dir.exists()
        assert list(out_dir.glob("*.gpx")), "Expected GPX output in onx_ready/"

    def test_migrate_onx_to_caltopo_happy_path_writes_outputs(self, tmp_path: Path):
        """
        Exercise the interactive onx-to-caltopo flow (file selection + confirm) to improve
        coverage over migrate_cmd's main path.
        """
        # Copy demo fixtures into a temp input directory so the command can discover them.
        repo_root = Path(__file__).resolve().parents[1]
        demo_dir = repo_root / "demo" / "onx-to-caltopo" / "onx-export"
        gpx_src = demo_dir / "onx-export.gpx"
        kml_src = demo_dir / "onx-export.kml"

        input_dir = tmp_path / "exports"
        input_dir.mkdir(parents=True, exist_ok=True)
        (input_dir / gpx_src.name).write_text(gpx_src.read_text(encoding="utf-8"), encoding="utf-8")
        (input_dir / kml_src.name).write_text(kml_src.read_text(encoding="utf-8"), encoding="utf-8")

        # Prompts:
        # - Select GPX file number (default 1) -> blank
        # - Select KML file number (default 1) -> blank
        # - Proceed with migration? (default yes) -> blank
        result = runner.invoke(app, ["migrate", "onx-to-caltopo", str(input_dir)], input="\n\n\n")
        assert result.exit_code == 0, result.stdout

        out_dir = input_dir / "caltopo_ready"
        assert out_dir.exists()
        assert list(out_dir.glob("*.json")), "Expected GeoJSON outputs in caltopo_ready/"

    def test_convert_onx_to_caltopo_writes_geojson_and_respects_flags(self, tmp_path: Path):
        """
        Exercise the non-interactive convert OnX_gpx -> caltopo_geojson path to improve coverage
        over convert_cmd's OnX→CalTopo fast path (and our new flags).
        """
        repo_root = Path(__file__).resolve().parents[1]
        gpx_src = repo_root / "demo" / "onx-to-caltopo" / "onx-export" / "onx-training.gpx"

        input_gpx = tmp_path / "input.gpx"
        input_gpx.write_text(gpx_src.read_text(encoding="utf-8"), encoding="utf-8")

        out_json = tmp_path / "out.json"
        result = runner.invoke(
            app,
            [
                "convert",
                str(input_gpx),
                "--from",
                "OnX_gpx",
                "--to",
                "caltopo_geojson",
                "--output",
                str(out_json),
                "--no-dedupe",
                "--no-dedupe-shapes",
                "--description-mode",
                "debug",
                "--route-color-strategy",
                "none",
            ],
        )
        assert result.exit_code == 0, result.stdout
        assert out_json.exists()

        data = json.loads(out_json.read_text(encoding="utf-8"))
        markers = [f for f in data["features"] if f.get("properties", {}).get("class") == "Marker"]
        assert markers, "expected at least one marker"
        assert "cairn:source=" in (markers[0]["properties"].get("description") or "")

        # With route-color-strategy=none and no OnX line colors in this sample, lines should omit stroke.
        shapes = [f for f in data["features"] if f.get("properties", {}).get("class") == "Shape"]
        assert shapes, "expected at least one line"
        assert all("stroke" not in f["properties"] for f in shapes)
