"""Characters XML 1.0 forbids (C0 controls other than tab/LF/CR, U+FFFE/U+FFFF,
lone surrogates) never reach a written file, so one bad name can't make a whole
GPX unparseable (2026-10-25). Everything XML allows, including line breaks in
notes and emoji, passes through unchanged."""
import xml.etree.ElementTree as ET

from cairn.core.parser import ParsedFeature
from cairn.core.writers import write_gpx_waypoints, write_gpx_tracks, xml_text

HOSTILE = "A\x00B\x01C\x08D\x0bE\x0cF\x1fG￾H￿I\ud800J"


def test_xml_text_drops_only_what_xml_forbids():
    assert xml_text(HOSTILE) == "ABCDEFGHIJ"
    keep = "Tab\there\nline\r\n& <b> \"q\" 'a' — 雪山 🏔️ 👨‍👩‍👧 é"
    assert xml_text(keep) == keep.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pt(title, desc):
    return ParsedFeature({"type": "Feature", "id": "p", "geometry": {"type": "Point", "coordinates": [-114, 46]},
                          "properties": {"class": "Marker", "title": title, "description": desc}})


def _line(title, desc):
    return ParsedFeature({"type": "Feature", "id": "l", "geometry": {"type": "LineString",
                          "coordinates": [[-114, 46], [-114.1, 46.1]]},
                          "properties": {"class": "Line", "title": title, "description": desc}})


def test_written_waypoints_and_lines_parse_with_hostile_names_and_notes(tmp_path):
    w = tmp_path / "w.gpx"
    write_gpx_waypoints([_pt(HOSTILE, HOSTILE)], w, "F & G" + "\x01")
    t = tmp_path / "t.gpx"
    write_gpx_tracks([_line(HOSTILE, HOSTILE)], t, "F")
    for path in (w, t):
        root = ET.parse(path).getroot()          # would raise on an invalid character
        names = [e.text for e in root.iter() if e.tag.endswith("}name")]
        assert "ABCDEFGHIJ" in names
