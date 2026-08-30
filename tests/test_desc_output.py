"""Tests for GPX <desc> content policy.

Default: <desc> is user-facing and carries ONLY the user's own note text; a
feature with no note gets no <desc> element at all. Machine state (id, color,
icon, style, weight) travels in the <onx:*> extension elements.

Debug (--debug on `migrate onx`, --description-mode debug on `convert`):
restores the legacy key=value block for troubleshooting.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from typer.testing import CliRunner

from cairn.cli import app
from cairn.core.parser import ParsedFeature
from cairn.core.writers import (
    write_gpx_tracks,
    write_gpx_tracks_maybe_split,
    write_gpx_waypoints,
    write_gpx_waypoints_maybe_split,
)
from cairn.io.onx_gpx import read_onx_gpx

_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}

runner = CliRunner()


def _waypoint(title: str, description: str, wp_id: str = "wp-1") -> ParsedFeature:
    return ParsedFeature(
        {
            "id": wp_id,
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-114.5, 45.5]},
            "properties": {
                "class": "Marker",
                "title": title,
                "description": description,
                "marker-color": "FF0000",
                "marker-symbol": "campsite",
            },
        }
    )


def _track(title: str, description: str, trk_id: str = "trk-1") -> ParsedFeature:
    return ParsedFeature(
        {
            "id": trk_id,
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[-114.5, 45.5], [-114.6, 45.6]],
            },
            "properties": {
                "class": "Shape",
                "title": title,
                "description": description,
                "stroke": "#FF00FF",
                "stroke-width": 4,
                "pattern": "solid",
            },
        }
    )


def _desc_texts(gpx_path: Path, elem: str) -> list:
    """Return the <desc> text (or None when absent) for each wpt/trk element."""
    root = ET.parse(gpx_path).getroot()
    out = []
    for item in root.findall(f"gpx:{elem}", _NS):
        d = item.find("gpx:desc", _NS)
        out.append(d.text if d is not None else None)
    return out


DEBUG_MARKERS = ("name=", "notes=", "id=", "color=", "icon=", "style=", "weight=")


# ---------------------------------------------------------------------------
# Default mode: notes only
# ---------------------------------------------------------------------------


def test_waypoint_desc_is_note_only_by_default(tmp_path):
    out = tmp_path / "wp.gpx"
    write_gpx_waypoints([_waypoint("Camp spot", "Water 100m east")], out, "F", sort=False)

    descs = _desc_texts(out, "wpt")
    assert descs == ["Water 100m east"]
    for marker in DEBUG_MARKERS:
        assert marker not in descs[0]


def test_waypoint_without_note_has_no_desc_element(tmp_path):
    out = tmp_path / "wp.gpx"
    write_gpx_waypoints([_waypoint("Camp spot", "")], out, "F", sort=False)

    assert _desc_texts(out, "wpt") == [None]
    text = out.read_text(encoding="utf-8")
    assert "<desc>" not in text
    # No stray debug text anywhere in the file.
    for marker in ("notes=", "id=", "icon=", "color=rgba"):
        assert marker not in text
    # Extensions still carry the machine state.
    assert "<onx:icon>" in text and "<onx:color>" in text


def test_track_desc_is_note_only_by_default(tmp_path):
    out = tmp_path / "trk.gpx"
    write_gpx_tracks([_track("Ridge line", "Steep after the saddle")], out, "F", sort=False)

    descs = _desc_texts(out, "trk")
    assert descs == ["Steep after the saddle"]
    for marker in DEBUG_MARKERS:
        assert marker not in descs[0]


def test_track_without_note_has_no_desc_element(tmp_path):
    out = tmp_path / "trk.gpx"
    write_gpx_tracks([_track("Ridge line", "")], out, "F", sort=False)

    assert _desc_texts(out, "trk") == [None]
    text = out.read_text(encoding="utf-8")
    assert "<desc>" not in text
    assert "<onx:color>" in text and "<onx:style>" in text and "<onx:weight>" in text


def test_maybe_split_writers_follow_same_default_policy(tmp_path):
    wp_out = tmp_path / "wp.gpx"
    trk_out = tmp_path / "trk.gpx"
    write_gpx_waypoints_maybe_split(
        [_waypoint("A", "note a"), _waypoint("B", "", wp_id="wp-2")],
        wp_out,
        "F",
        sort=False,
    )
    write_gpx_tracks_maybe_split(
        [_track("T1", "note t"), _track("T2", "", trk_id="trk-2")],
        trk_out,
        "F",
        sort=False,
    )

    assert _desc_texts(wp_out, "wpt") == ["note a", None]
    assert _desc_texts(trk_out, "trk") == ["note t", None]


# ---------------------------------------------------------------------------
# Debug mode: legacy key=value block preserved verbatim
# ---------------------------------------------------------------------------


def test_debug_restores_full_kv_block_for_waypoints(tmp_path):
    out = tmp_path / "wp.gpx"
    write_gpx_waypoints(
        [_waypoint("Camp spot", "Water 100m east", wp_id="wp-42")],
        out,
        "F",
        sort=False,
        debug_desc=True,
    )

    (desc,) = _desc_texts(out, "wpt")
    lines = desc.splitlines()
    assert lines[0] == "name=Camp spot"
    assert lines[1] == "notes=Water 100m east"
    assert lines[2] == "id=wp-42"
    assert lines[3].startswith("color=rgba(")
    assert lines[4].startswith("icon=")


def test_debug_restores_full_kv_block_for_tracks(tmp_path):
    out = tmp_path / "trk.gpx"
    write_gpx_tracks(
        [_track("Ridge line", "Steep", trk_id="trk-42")],
        out,
        "F",
        sort=False,
        debug_desc=True,
    )

    (desc,) = _desc_texts(out, "trk")
    lines = desc.splitlines()
    assert lines[0] == "name=Ridge line"
    assert lines[1] == "notes=Steep"
    assert lines[2] == "id=trk-42"
    assert lines[3].startswith("color=rgba(")
    assert lines[4] == "style=solid"
    assert lines[5] == "weight=4.0"


def test_debug_kv_block_even_when_note_empty(tmp_path):
    out = tmp_path / "wp.gpx"
    write_gpx_waypoints(
        [_waypoint("Camp spot", "")], out, "F", sort=False, debug_desc=True
    )
    (desc,) = _desc_texts(out, "wpt")
    assert "name=Camp spot" in desc
    assert "notes=" in desc


# ---------------------------------------------------------------------------
# Round trip: Cairn's own onX reader loses nothing Cairn depends on
# ---------------------------------------------------------------------------


def test_round_trip_default_output_preserves_judgement_layer(tmp_path):
    """Export (default mode) then re-read with Cairn's onX GPX reader.

    Name, note, icon, and color must survive. The only field that previously
    lived exclusively in the <desc> kv block is the internal id; the reader
    falls back to a fresh UUID for it, and nothing in the pipeline requires a
    stable id from a Cairn-generated file (real onX exports carry onX's own
    ids, written by onX itself).
    """
    wp_out = tmp_path / "wp.gpx"
    trk_out = tmp_path / "trk.gpx"
    write_gpx_waypoints(
        [_waypoint("Camp spot", "Water 100m east")], wp_out, "F", sort=False
    )
    write_gpx_tracks(
        [_track("Ridge line", "Steep after the saddle")], trk_out, "F", sort=False
    )

    wdoc = read_onx_gpx(wp_out)
    (wp,) = wdoc.waypoints()
    assert wp.name == "Camp spot"
    assert wp.notes == "Water 100m east"
    assert wp.style.OnX_icon  # from <onx:icon>
    assert wp.style.OnX_color_rgba and wp.style.OnX_color_rgba.startswith("rgba(")
    assert wp.id  # UUID fallback is fine; must simply exist

    tdoc = read_onx_gpx(trk_out)
    (trk,) = tdoc.tracks()
    assert trk.name == "Ridge line"
    assert trk.notes == "Steep after the saddle"
    assert trk.style.OnX_color_rgba and trk.style.OnX_color_rgba.startswith("rgba(")
    assert trk.style.OnX_style == "solid"
    assert trk.style.OnX_weight == "4.0"
    assert len(trk.points) == 2


def test_round_trip_no_note_yields_empty_notes(tmp_path):
    out = tmp_path / "wp.gpx"
    write_gpx_waypoints([_waypoint("Camp spot", "")], out, "F", sort=False)
    doc = read_onx_gpx(out)
    (wp,) = doc.waypoints()
    assert wp.notes == ""
    assert wp.name == "Camp spot"


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def _small_caltopo_geojson(tmp_path: Path) -> Path:
    import json

    doc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "folder-1",
                "geometry": None,
                "properties": {"class": "Folder", "title": "Demo"},
            },
            {
                "type": "Feature",
                "id": "wp-note",
                "geometry": {"type": "Point", "coordinates": [-114.5, 45.5]},
                "properties": {
                    "class": "Marker",
                    "title": "Camp spot",
                    "description": "Water 100m east",
                    "marker-symbol": "campsite",
                    "marker-color": "#FF0000",
                    "folderId": "folder-1",
                },
            },
            {
                "type": "Feature",
                "id": "wp-plain",
                "geometry": {"type": "Point", "coordinates": [-114.6, 45.6]},
                "properties": {
                    "class": "Marker",
                    "title": "Plain spot",
                    "description": "",
                    "marker-symbol": "campsite",
                    "marker-color": "#FF0000",
                    "folderId": "folder-1",
                },
            },
        ],
    }
    p = tmp_path / "demo.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_migrate_onx_help_documents_debug_flag():
    result = runner.invoke(app, ["migrate", "onx", "--help"])
    assert result.exit_code == 0
    # Rich styles "--debug" as two separately-escaped runs ("-" + "-debug"),
    # so the raw stdout may not contain the literal substring.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "--debug" in plain


def test_migrate_onx_cli_default_writes_notes_only(tmp_path):
    src = _small_caltopo_geojson(tmp_path)
    outdir = tmp_path / "out"
    result = runner.invoke(
        app,
        ["migrate", "onx", str(src), "-o", str(outdir), "--no-interactive"],
        input="y\n",
    )
    assert result.exit_code == 0, result.output

    gpx_files = list(outdir.glob("*Waypoints*.gpx"))
    assert gpx_files, f"no waypoint GPX written in {list(outdir.iterdir())}"
    descs = _desc_texts(gpx_files[0], "wpt")
    assert "Water 100m east" in descs
    assert None in descs  # the note-less waypoint has no <desc> at all
    text = gpx_files[0].read_text(encoding="utf-8")
    for marker in ("notes=", "id=", "icon=", "color=rgba"):
        assert marker not in text


def test_migrate_onx_cli_debug_writes_kv_block(tmp_path):
    src = _small_caltopo_geojson(tmp_path)
    outdir = tmp_path / "out"
    result = runner.invoke(
        app,
        ["migrate", "onx", str(src), "-o", str(outdir), "--no-interactive", "--debug"],
        input="y\n",
    )
    assert result.exit_code == 0, result.output

    gpx_files = list(outdir.glob("*Waypoints*.gpx"))
    assert gpx_files
    descs = [d for d in _desc_texts(gpx_files[0], "wpt") if d]
    assert len(descs) == 2  # debug mode emits <desc> even without a note
    joined = "\n".join(descs)
    assert "name=Camp spot" in joined
    assert "notes=Water 100m east" in joined
    assert "id=wp-note" in joined
    assert "color=rgba(" in joined
    assert "icon=" in joined
