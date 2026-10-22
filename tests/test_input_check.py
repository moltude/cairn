"""Roadmap Phase 0: input safety and format detection (cairn/io/input_check.py).

- guard_input rejects DTD-bearing and oversized XML before any reader runs;
- detect classifies every tracked fixture by content (content beats extension);
- Cairn's own KML carries a marker so detect can tell it from CalTopo/Google Earth KML.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cairn.core import writers as W
from cairn.core.parser import ParsedFeature
from cairn.io import input_check as IC
from cairn.io.input_check import (
    CAIRN, CALTOPO, EMPTY, GENERIC, GEOJSON, GPX, INVALID, KML, NOT_A_MAP, ONX, ONX_LIKE,
    UNKNOWN, detect, extension_mismatch, guard_input,
)
from cairn.io.onx_kml import read_onx_kml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
ATTACKS = FIXTURES / "attacks"

sys.path.insert(0, str(ROOT / "web"))
import bridge  # noqa: E402

ATTACK_FILES = [
    "billion_laughs.gpx",
    "quadratic_blowup.kml",
    "external_entity.gpx",
    "external_parameter_entity.kml",
]

# Every tracked file under tests/fixtures/, with the (kind, dialect) it must sniff as.
# Adding a fixture without classifying it here fails test_expected_covers_every_fixture.
EXPECTED = {
    "attacks/README.md": (UNKNOWN, NOT_A_MAP),
    "attacks/billion_laughs.gpx": (GPX, CALTOPO),        # guard_input is what rejects these
    "attacks/external_entity.gpx": (GPX, ONX),
    "attacks/external_parameter_entity.kml": (KML, GENERIC),
    "attacks/quadratic_blowup.kml": (KML, GENERIC),
    "bitterroots/Bitterroots__Complete_.json": (GEOJSON, CALTOPO),
    "bitterroots/bitterroots_subet.gpx": (GPX, CALTOPO),  # the one real CalTopo GPX
    "bitterroots/bitterroots_subset.json": (GEOJSON, CALTOPO),
    # Digests of the Phase 2 baseline export: JSON, but not a map.
    "bitterroots/export_zip_sha256_e927aa9.json": (GEOJSON, GENERIC),
    "edge_cases/README.md": (UNKNOWN, NOT_A_MAP),
    "edge_cases/colors.gpx": (GPX, CAIRN),
    "edge_cases/dateline.gpx": (GPX, CAIRN),
    "edge_cases/duplicates.gpx": (GPX, CAIRN),
    "edge_cases/elevations.gpx": (GPX, CAIRN),
    "edge_cases/empty.gpx": (GPX, CAIRN),
    "edge_cases/empty.json": (GEOJSON, GENERIC),
    "edge_cases/empty_names.gpx": (GPX, CAIRN),
    "edge_cases/equator.gpx": (GPX, CAIRN),
    "edge_cases/long_name.gpx": (GPX, CAIRN),
    "edge_cases/long_track_1000.gpx": (GPX, CAIRN),
    "edge_cases/long_track_10000.gpx": (GPX, CAIRN),
    "edge_cases/malformed.gpx": (GPX, GENERIC),          # sniffed, not parsed: the reader reports it
    "edge_cases/malformed.json": (GEOJSON, INVALID),
    "edge_cases/many_waypoints_1000.gpx": (GPX, CAIRN),
    "edge_cases/many_waypoints_10000.gpx": (GPX, CAIRN),
    "edge_cases/mixed_features.json": (GEOJSON, CALTOPO),
    "edge_cases/multipolygon.json": (GEOJSON, CALTOPO),
    "edge_cases/poles.gpx": (GPX, CAIRN),
    "edge_cases/prime_meridian.gpx": (GPX, CAIRN),
    "edge_cases/quotes.gpx": (GPX, CAIRN),
    "edge_cases/single_marker.json": (GEOJSON, CALTOPO),
    "edge_cases/single_point_track.gpx": (GPX, CAIRN),
    "edge_cases/single_waypoint.gpx": (GPX, CAIRN),
    "edge_cases/unicode.gpx": (GPX, CAIRN),
    "edge_cases/xml_chars.gpx": (GPX, CAIRN),
    "onx_dialect/README.md": (UNKNOWN, NOT_A_MAP),
    "onx_real/README.md": (UNKNOWN, NOT_A_MAP),
    "onx_real/onx_web_export_2_waypoints.gpx": (GPX, ONX),   # REAL onX Web Map export, 2026-10-22
    "onx_real/onx_web_export_2_waypoints.kml": (KML, ONX),   # REAL onX Web Map export, 2026-10-22
    "onx_dialect/onx_dialect.gpx": (GPX, ONX),            # synthetic, modelled on onX's export code
    "onx_dialect/onx_dialect.kml": (KML, ONX),
    "onx_export_with_tracks.gpx": (GPX, ONX_LIKE),       # synthetic, creator="OnX Backcountry"
    "onx_export_with_tracks.kml": (KML, GENERIC),        # synthetic, has <Folder>, no Data id
    "onx_waypoint_color_test.gpx": (GPX, CAIRN),
    "rattlesnake_test_tracks.gpx": (GPX, CAIRN),
    "rattlesnake_test_waypoints.gpx": (GPX, CAIRN),
    "test_sort_order_tracks.gpx": (GPX, CAIRN),
    "test_sort_order_waypoints.gpx": (GPX, CAIRN),
    "test_sort_trk_az_random_in_file.gpx": (GPX, CAIRN),
    "test_sort_trk_az_sequential_in_file.gpx": (GPX, CAIRN),
    "test_sort_trk_time_random.gpx": (GPX, CAIRN),
    "test_sort_trk_time_sequential.gpx": (GPX, CAIRN),
    "test_sort_wp_az_random_in_file.gpx": (GPX, CAIRN),
    "test_sort_wp_az_sequential_in_file.gpx": (GPX, CAIRN),
    "test_sort_wp_time_random.gpx": (GPX, CAIRN),
    "test_sort_wp_time_sequential.gpx": (GPX, CAIRN),
    "tui/two_waypoints.json": (GEOJSON, CALTOPO),
}


def _fixture_files() -> set[str]:
    """Fixture files as git sees them, plus any new untracked ones (never .DS_Store
    and friends, which exist on some machines and not in CI)."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "tests/fixtures"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return {Path(p).relative_to("tests/fixtures").as_posix() for p in out.split()}


def _read(rel: str) -> str:
    return (FIXTURES / rel).read_text(encoding="utf-8")


# --- detect over every fixture --------------------------------------------------------


def test_expected_covers_every_fixture():
    assert _fixture_files() == set(EXPECTED)


@pytest.mark.parametrize("rel", sorted(EXPECTED))
def test_every_fixture_classifies_as_expected(rel):
    assert detect(Path(rel).name, _read(rel)) == EXPECTED[rel]


# --- detect: dialect rules not covered by a real fixture ------------------------------

ONX_WEB_GPX = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<gpx xmlns:onx="https://wwww.onxmaps.com/" xmlns="http://www.topografix.com/GPX/1/1" '
    'version="1.1" creator="onXmaps hunt web"><wpt lat="1" lon="1"><name>a</name></wpt></gpx>'
)
ONX_KML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
    '<Placemark><name>a</name><ExtendedData><Data name="id"><value>u-1</value></Data>'
    '</ExtendedData><Point><coordinates>1,1</coordinates></Point></Placemark></Document></kml>'
)


def test_onx_web_gpx_by_creator():
    assert detect("onx-markups-2026-10-22.gpx", ONX_WEB_GPX) == (GPX, ONX)


def test_onx_kml_by_placemark_id():
    assert detect("onx-markups.kml", ONX_KML) == (KML, ONX)


def test_generic_gpx_without_creator_or_onx_namespace():
    text = '<gpx xmlns="http://www.topografix.com/GPX/1/1" creator="Garmin Desktop App"></gpx>'
    assert detect("x.gpx", text) == (GPX, GENERIC)


def test_single_quoted_creator_is_read():
    assert detect("x.gpx", "<gpx creator='CALTOPO' version='1.1'></gpx>") == (GPX, CALTOPO)


def test_root_after_a_long_prolog_comment_is_found():
    # A 4 KB window from byte 0 would miss this root and call the file not-a-map.
    text = '<?xml version="1.0"?>\n<!-- ' + "x" * 8000 + ' -->\n' + ONX_WEB_GPX.split("\n", 1)[1]
    assert detect("x.gpx", text) == (GPX, ONX)


def test_bom_and_leading_whitespace_are_ignored():
    assert detect("x.gpx", "﻿\n  " + ONX_WEB_GPX) == (GPX, ONX)
    assert detect("x.json", '﻿ {"features": [{"properties": {"class": "Marker"}}]}') == (
        GEOJSON, CALTOPO)


def test_non_map_inputs():
    assert detect("x.gpx", "") == (UNKNOWN, EMPTY)
    assert detect("x.gpx", "  \n ") == (UNKNOWN, EMPTY)
    assert detect("x.gpx", "hello") == (UNKNOWN, NOT_A_MAP)
    assert detect("x.xml", '<?xml version="1.0"?><html><body/></html>') == (UNKNOWN, NOT_A_MAP)


def test_content_wins_over_extension(caplog):
    # A GPX saved as .json, a GeoJSON saved as .kml, a KML saved as .txt.
    assert detect("map.json", ONX_WEB_GPX) == (GPX, ONX)
    assert detect("map.kml", _read("tui/two_waypoints.json")) == (GEOJSON, CALTOPO)
    with caplog.at_level("WARNING", logger=IC.__name__):
        assert detect("map.txt", ONX_KML) == (KML, ONX)
    assert "map.txt" in caplog.text and "KML" in caplog.text


def test_extension_mismatch_message():
    assert extension_mismatch("a.gpx", GPX) is None
    assert extension_mismatch("A.GPX", GPX) is None
    assert extension_mismatch("a.geojson", GEOJSON) is None
    assert extension_mismatch("a.json", GEOJSON) is None
    assert extension_mismatch("a.json", UNKNOWN) is None
    msg = extension_mismatch("export.json", GPX)
    assert msg and "“.json”" in msg and "GPX" in msg
    assert "no extension" in extension_mismatch("export", KML)


# --- Cairn's KML marker ---------------------------------------------------------------

SQUARE = [[-114.0, 45.0], [-114.1, 45.0], [-114.1, 45.1], [-114.0, 45.1], [-114.0, 45.0]]


def _shape(title="Area"):
    return ParsedFeature({"type": "Feature", "properties": {"class": "Shape", "title": title},
                          "geometry": {"type": "Polygon", "coordinates": [SQUARE]}})


def test_cairn_kml_carries_generator_marker(tmp_path):
    out = tmp_path / "areas.kml"
    W.write_kml_shapes([_shape()], out, "Test")
    text = out.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    data = root.findall("k:Document/k:ExtendedData/k:Data", ns)
    assert [(d.get("name"), d.findtext("k:value", namespaces=ns)) for d in data] == [
        (IC.CAIRN_KML_MARKER_NAME, IC.CAIRN_KML_MARKER_VALUE)]
    assert detect("areas.kml", text) == (KML, CAIRN)


def test_cairn_kml_marker_is_on_every_split_part(tmp_path):
    feats = [_shape(f"Area {i}") for i in range(6)]
    parts = W.write_kml_shapes_maybe_split(feats, tmp_path / "a.kml", "T", max_bytes=1500)
    assert len(parts) > 1
    for path, size, _count in parts:
        assert size <= 1500
        assert detect(path.name, path.read_text(encoding="utf-8")) == (KML, CAIRN)


def test_cairn_marker_does_not_leak_into_items(tmp_path):
    out = tmp_path / "areas.kml"
    W.write_kml_shapes([_shape("Only")], out, "Test")
    doc = read_onx_kml(out)
    assert [i.name for i in doc.items] == ["Only"]
    assert all("generator" not in str(getattr(i, "extra", {}) or {}) for i in doc.items)


def test_cairn_marker_beats_onx_id_in_kml():
    # Once Cairn writes onX ids back (Phase 6) its KML carries both; it is still Cairn's.
    text = ONX_KML.replace(
        "<Document>",
        '<Document><ExtendedData><Data name="generator"><value>Cairn</value></Data></ExtendedData>',
    )
    assert detect("x.kml", text) == (KML, CAIRN)


# --- guard_input ------------------------------------------------------------------------


@pytest.mark.parametrize("name", ATTACK_FILES)
def test_attack_files_are_rejected(name):
    with pytest.raises(ValueError, match="DOCTYPE"):
        guard_input((ATTACKS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ATTACK_FILES)
def test_attack_files_are_rejected_by_the_bridge(name):
    # The bridge runs the guard before writing or parsing anything. Without it the
    # file reaches parse_geojson and fails with a JSON error instead.
    with pytest.raises(ValueError, match=r"<!DOCTYPE> declaration"):
        bridge.load_document((ATTACKS / name).read_text(encoding="utf-8"), name)


def test_rejection_message_is_short_plain_sentence():
    with pytest.raises(ValueError) as exc:
        guard_input(_read("attacks/billion_laughs.gpx"))
    msg = str(exc.value)
    # app.js humanError shows the last traceback line, cut at 180 characters.
    assert len(msg) <= 180 and "\n" not in msg and msg.endswith(".")


def test_dtd_hidden_behind_comment_and_pi_is_rejected():
    # A fake tag inside a comment must not end the prolog scan early.
    text = ('<?xml version="1.0"?>\n<!-- <gpx creator="x"> -->\n<?pi data?>\n'
            '<!DOCTYPE gpx [<!ENTITY a "b">]>\n<gpx><wpt lat="1" lon="1"/></gpx>')
    with pytest.raises(ValueError, match="DOCTYPE"):
        guard_input(text)


def test_dtd_after_bom_and_whitespace_is_rejected():
    with pytest.raises(ValueError, match="DOCTYPE"):
        guard_input("﻿\n  <!DOCTYPE kml><kml/>")


def test_html_doctype_inside_cdata_notes_is_allowed():
    # Pasted HTML in a note is data, not a DTD; whole-text search would refuse this file.
    text = ('<?xml version="1.0"?>\n<gpx creator="CALTOPO"><wpt lat="1" lon="1"><name>a</name>'
            '<desc><![CDATA[<!DOCTYPE html><p>notes</p>]]></desc></wpt></gpx>')
    guard_input(text)
    ET.fromstring(text)  # and it really is well-formed XML


def test_json_with_doctype_in_notes_is_allowed():
    guard_input('{"features": [{"properties": {"description": "<!DOCTYPE html><!ENTITY x>"}}]}')


def test_every_non_attack_fixture_passes_the_guard():
    for rel in sorted(EXPECTED):
        if not rel.startswith("attacks/"):
            guard_input(_read(rel))


def test_oversized_xml_is_rejected():
    head = '<?xml version="1.0"?><gpx creator="CALTOPO">'
    text = head + " " * (IC.MAX_XML_INPUT_BYTES - len(head) + 1)
    with pytest.raises(ValueError, match=r"up to 16 MB"):
        guard_input(text)


def test_size_cap_counts_utf8_bytes_not_characters():
    # 6M three-byte characters: 6M chars (under the cap) but 18 MB of UTF-8.
    text = "<gpx>" + "€" * (6 * 1024 * 1024) + "</gpx>"
    assert len(text) < IC.MAX_XML_INPUT_BYTES < len(text.encode("utf-8"))
    with pytest.raises(ValueError, match=r"up to 16 MB"):
        guard_input(text)


def test_xml_at_the_cap_is_allowed():
    head, tail = '<gpx creator="CALTOPO">', "</gpx>"
    text = head + " " * (IC.MAX_XML_INPUT_BYTES - len(head) - len(tail)) + tail
    assert len(text.encode("utf-8")) == IC.MAX_XML_INPUT_BYTES
    guard_input(text)


def test_large_json_is_not_capped():
    # The pre-existing GeoJSON path is unchanged: no size cap (see the module comment).
    guard_input('{"features": []' + " " * (IC.MAX_XML_INPUT_BYTES + 1) + "}")


def test_onx_like_needs_an_onx_namespace_not_just_the_text_onxmaps_com():
    """The ONX_LIKE sniff matches an xmlns whose whole value is an onxmaps.com
    origin, not any attribute that merely contains the text."""
    from cairn.io.input_check import detect

    ns = '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:onx="https://wwww.onxmaps.com/" version="1.1"></gpx>'
    fake = '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:x="https://evil.example/?u=onxmaps.com" version="1.1"></gpx>'
    assert detect("a.gpx", ns)[1] == ONX_LIKE
    assert detect("b.gpx", fake)[1] == GENERIC
