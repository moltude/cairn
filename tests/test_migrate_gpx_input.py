"""Regression tests for CalTopo GPX input to `migrate onx`.

The CLI historically hard-rejected non-JSON input in the CalTopo -> OnX
direction even though the README documents GPX. `parse_caltopo_gpx` is now
routed from `_validate_geojson_file`, and `_find_geojson_files` includes
`.gpx`. These tests pin:

- the happy path (a real CalTopo GPX export produces OnX-ready GPX output)
- the lossiness advisory fires for GPX and ONLY for GPX
- the extension error names all three accepted types
- the OTHER direction (`migrate caltopo`, OnX -> CalTopo) still routes `.gpx`
  through the OnX reader, not the CalTopo GPX reader
- a directory holding both a `.json` and a `.gpx` defaults the picker to the
  lossless GeoJSON, not the GPX that happens to sort first alphabetically
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from cairn.cli import app
from cairn.commands.migrate_cmd import _find_geojson_files

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
CALTOPO_GPX = FIXTURES / "bitterroots" / "bitterroots_subet.gpx"

ADVISORY_FRAGMENT = "GPX carries only coordinates and names"


def _minimal_geojson(tmp_path: Path, name: str = "export.json") -> Path:
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "w1",
                "geometry": {"type": "Point", "coordinates": [-120.0, 45.0]},
                "properties": {
                    "class": "Marker",
                    "title": "JsonWaypoint",
                    "marker-color": "#FF0000",
                    "marker-symbol": "campsite",
                },
            }
        ],
    }
    p = tmp_path / name
    p.write_text(json.dumps(fc), encoding="utf-8")
    return p


def test_migrate_onx_accepts_caltopo_gpx_file(tmp_path: Path):
    """A CalTopo GPX export is now a first-class input to `migrate onx`."""
    in_file = tmp_path / CALTOPO_GPX.name
    in_file.write_text(CALTOPO_GPX.read_text(encoding="utf-8"), encoding="utf-8")

    # One prompt: the final "Ready to generate new map?" gate (default yes).
    result = runner.invoke(app, ["migrate", "onx", str(in_file)], input="\n")
    assert result.exit_code == 0, result.stdout

    out_dir = tmp_path / "onx_ready"
    assert out_dir.exists()
    gpx_outputs = list(out_dir.glob("*.gpx"))
    assert gpx_outputs, "Expected a waypoints GPX in onx_ready/"

    # The fixture's waypoints must survive the round trip.
    written = gpx_outputs[0].read_text(encoding="utf-8")
    assert "Camp spot" in written
    assert "<wpt " in written


def test_gpx_input_prints_lossiness_advisory(tmp_path: Path):
    in_file = tmp_path / CALTOPO_GPX.name
    in_file.write_text(CALTOPO_GPX.read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(app, ["migrate", "onx", str(in_file)], input="\n")
    assert result.exit_code == 0, result.stdout
    assert ADVISORY_FRAGMENT in result.stdout


def test_geojson_input_does_not_print_gpx_advisory(tmp_path: Path):
    in_file = _minimal_geojson(tmp_path)

    result = runner.invoke(app, ["migrate", "onx", str(in_file)], input="\n")
    assert result.exit_code == 0, result.stdout
    assert ADVISORY_FRAGMENT not in result.stdout


def test_unsupported_extension_error_names_all_three_types(tmp_path: Path):
    bad = tmp_path / "export.kml"
    bad.write_text("<kml/>", encoding="utf-8")

    result = runner.invoke(app, ["migrate", "onx", str(bad)], input="\n")
    assert result.exit_code == 1
    out = result.stdout
    assert "Expected one of" in out
    assert ".json" in out
    assert ".geojson" in out
    assert ".gpx" in out


def test_onx_to_caltopo_still_routes_gpx_to_onx_reader(tmp_path: Path):
    """The OnX -> CalTopo direction must NOT pick up the CalTopo GPX reader.

    The OnX reader preserves onx:icon / onx:color extensions; the CalTopo GPX
    reader drops them and synthesizes `caltopo_gpx_*` feature ids. If routing
    ever regresses, both assertions below catch it.
    """
    gpx_src = FIXTURES / "onx_export_with_tracks.gpx"
    kml_src = FIXTURES / "onx_export_with_tracks.kml"
    in_file = tmp_path / gpx_src.name
    in_file.write_text(gpx_src.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / kml_src.name).write_text(
        kml_src.read_text(encoding="utf-8"), encoding="utf-8"
    )

    # Prompts: select GPX, select KML, final confirm — all defaults.
    result = runner.invoke(app, ["migrate", "caltopo", str(in_file)], input="\n\n\n")
    assert result.exit_code == 0, result.stdout

    out_dir = tmp_path / "caltopo_ready"
    json_outputs = list(out_dir.glob("*.json"))
    assert json_outputs, "Expected GeoJSON output in caltopo_ready/"

    combined = "\n".join(p.read_text(encoding="utf-8") for p in json_outputs)
    # OnX reader kept the icon/color data the CalTopo GPX reader would drop.
    assert "Test Campsite" in combined
    assert "marker-symbol" in combined
    # CalTopo-GPX-reader fingerprint must be absent.
    assert "caltopo_gpx_wpt_" not in combined
    assert "caltopo_gpx_trk_" not in combined


def test_directory_picker_defaults_to_geojson_over_gpx(tmp_path: Path):
    """Mixed directory: Enter must still select the lossless GeoJSON.

    `.gpx` files sort alphabetically ahead of `.json` (e.g. `aaa.gpx` before
    `bbb.json`), so a plain alphabetical sort silently flips a long-standing
    default from the full-fidelity export to the lossy one. `_find_geojson_files`
    therefore orders .json/.geojson before .gpx.
    """
    gpx_file = tmp_path / "aaa_export.gpx"
    gpx_file.write_text(CALTOPO_GPX.read_text(encoding="utf-8"), encoding="utf-8")
    _minimal_geojson(tmp_path, name="bbb_export.json")

    found = _find_geojson_files(tmp_path)
    assert [p.name for p in found] == ["bbb_export.json", "aaa_export.gpx"]

    # End-to-end: default selection ("1") + final gate.
    result = runner.invoke(app, ["migrate", "onx", str(tmp_path)], input="\n\n")
    assert result.exit_code == 0, result.stdout
    # The GeoJSON was processed (its waypoint shows up in the preview) and the
    # GPX advisory did not fire.
    assert "JsonWaypoint" in result.stdout
    assert ADVISORY_FRAGMENT not in result.stdout


def test_find_geojson_files_orders_within_groups_alphabetically(tmp_path: Path):
    for name in ("z.geojson", "a.gpx", "m.json", "b.gpx"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    found = [p.name for p in _find_geojson_files(tmp_path)]
    assert found == ["m.json", "z.geojson", "a.gpx", "b.gpx"]
