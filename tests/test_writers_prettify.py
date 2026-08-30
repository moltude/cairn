"""Pin `prettify_xml` output to the minidom implementation it replaced.

`prettify_xml` feeds the KML that onX imports (cairn/core/writers.py:write_kml_shapes).
It used to be `minidom.parseString(...).toprettyxml(indent="  ")`, which built a second
full DOM — ~2x slower and ~10x the peak memory on a large export. It is now
`ET.indent` + `ET.tostring`.

Because the output goes to a third-party importer, "faster" is only acceptable if it is
also byte-identical. These tests compare the live implementation against the old one
directly rather than against hand-written expected strings, so they keep holding if the
implementation is rewritten again.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pytest

from cairn.core.writers import prettify_xml


def _legacy_prettify(elem: ET.Element) -> str:
    """The exact implementation that shipped before ET.indent."""
    rough_string = ET.tostring(elem, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def _build(n_children: int = 3, *, text: str = "Waypoint") -> ET.Element:
    root = ET.Element("gpx", {"version": "1.1", "creator": "cairn"})
    for i in range(n_children):
        wpt = ET.SubElement(root, "wpt", {"lat": "46.1234567", "lon": "-114.1234567"})
        ET.SubElement(wpt, "name").text = f"{text} {i}"
        ET.SubElement(wpt, "desc").text = "notes=\nicon=Campground\ncolor=rgba(8,122,255,1)"
    return root


@pytest.mark.parametrize("n", [1, 3, 50])
def test_matches_legacy_minidom_output_exactly(n: int) -> None:
    """Byte-for-byte equality with the replaced implementation."""
    assert prettify_xml(_build(n)) == _legacy_prettify(_build(n))


def test_known_divergence_is_limited_to_childless_elements() -> None:
    """The one place ET.indent and minidom disagree, pinned deliberately.

    ElementTree renders a childless element as `<tag />`; minidom renders it as
    `<tag/>`. That is the same XML to any conforming parser, and it is the ONLY
    difference between the two implementations. This test exists so that if the
    divergence ever widens, it fails here instead of silently in an onX import.
    """
    ours = prettify_xml(_build(0))
    legacy = _legacy_prettify(_build(0))

    assert ours != legacy, "divergence gone — simplify this test and the comment in writers.py"
    assert ours.replace(" />", "/>") == legacy
    assert ours.rstrip().endswith(" />")
    assert legacy.rstrip().endswith('"/>')


def test_real_kml_output_contains_no_self_closing_tags(tmp_path) -> None:
    """...and the divergence above is unreachable from the actual writer.

    Guards the claim in `prettify_xml`'s comment. If a future change to
    `write_kml_shapes` starts emitting an empty element, this fails and tells us
    the equivalence argument needs revisiting.
    """
    from cairn.core.parser import ParsedFeature
    from cairn.core.writers import write_kml_shapes

    features = [
        ParsedFeature(
            {
                "properties": {"title": "Area 1", "stroke": "#FF0000", "description": ""},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-114.0, 45.0],
                            [-114.1, 45.0],
                            [-114.1, 45.1],
                            [-114.0, 45.1],
                            [-114.0, 45.0],
                        ]
                    ],
                },
            }
        )
    ]
    out = tmp_path / "shapes.kml"
    write_kml_shapes(features, out, "Bitterroots")

    produced = out.read_text(encoding="utf-8")
    self_closing = re.findall(r"<([A-Za-z:]+)[^>]*/>", produced)
    assert self_closing == [], f"KML now emits self-closing tags: {set(self_closing)}"


@pytest.mark.parametrize(
    "text",
    [
        "Ampersand & angle < brackets >",
        'Quotes "double" and \'single\'',
        "Unicode: Sébastien — Bitterroots ✅ 🏔",
        "Trapper Peak\nsecond line",
    ],
)
def test_matches_legacy_on_characters_that_need_escaping(text: str) -> None:
    """XML escaping and unicode must survive the swap identically.

    This is the case that would actually break an onX import if it regressed.

    Python 3.13 changed minidom to stop escaping quotes in *text* nodes
    (they were never required to be escaped there); `prettify_xml` matches the
    3.13+ form. On older interpreters the legacy serializer over-escapes text
    quotes, so byte equality is only a meaningful claim on 3.13+; canonical
    XML equality is the invariant on every version.
    """
    ours = prettify_xml(_build(2, text=text))
    legacy = _legacy_prettify(_build(2, text=text))
    assert ET.canonicalize(ours) == ET.canonicalize(legacy)
    if sys.version_info >= (3, 13):
        assert ours == legacy


def test_declaration_and_trailing_newline_are_preserved() -> None:
    """The two details easiest to get wrong when hand-rolling the declaration.

    minidom emits `<?xml version="1.0" ?>` with a space before `?>`, and
    toprettyxml ends the document with a newline. ET.tostring does neither.
    """
    out = prettify_xml(_build(1))
    assert out.startswith('<?xml version="1.0" ?>\n')
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_output_is_still_parseable_xml() -> None:
    """Guard against producing something pretty but malformed."""
    out = prettify_xml(_build(4))
    reparsed = ET.fromstring(out)
    assert reparsed.tag == "gpx"
    assert len(reparsed.findall("wpt")) == 4


def test_indentation_is_two_spaces() -> None:
    lines = prettify_xml(_build(1)).splitlines()
    assert lines[1] == '<gpx version="1.1" creator="cairn">'
    assert lines[2].startswith("  <wpt ")
    assert lines[3].startswith("    <name>")


def test_prettify_is_idempotent_on_same_element() -> None:
    """Calling prettify_xml twice on one element must not double-indent.

    ET.indent mutates the element in place: the first call writes indentation
    into text/tail. A second call must overwrite that whitespace, not stack
    more on top of it (minidom never had this hazard — it worked on a copy).
    """
    elem = _build(3)
    first = prettify_xml(elem)
    second = prettify_xml(elem)
    assert first == second


def test_prettify_is_idempotent_on_reparsed_output() -> None:
    """Prettifying already-pretty XML must reproduce it exactly.

    (The old minidom implementation actually FAILED this property — re-feeding
    its own output doubled blank lines. ET.indent normalizes whitespace-only
    text/tail, so the new implementation is strictly better here.)
    """
    first = prettify_xml(_build(3))
    reparsed = ET.fromstring(first)
    assert prettify_xml(reparsed) == first


def test_prettify_mutates_element_whitespace_in_place() -> None:
    """Document the in-place mutation the swap introduced.

    Any caller that serializes the element again after prettify_xml now gets
    indented output, where the minidom version left the element untouched.
    Today the only caller (write_kml_shapes) discards the element immediately;
    this test exists so a future caller that reuses the element learns about
    the mutation from a named test instead of a diff in their output.
    """
    elem = _build(1)
    before = ET.tostring(elem, encoding="unicode")
    prettify_xml(elem)
    after = ET.tostring(elem, encoding="unicode")

    assert before != after, "prettify_xml no longer mutates — update its docs and this test"
    assert elem.text == "\n  ", "root text should now hold the child indentation"
    assert elem[0].tail == "\n", "last child's tail should now hold the closing newline"


def test_does_not_mutate_caller_visible_structure() -> None:
    """ET.indent formats in place — confirm it only adds whitespace.

    minidom worked on a copy, so the swap introduced in-place mutation of the
    caller's element. Tag/attribute/text content must be unaffected.
    """
    elem = _build(2)
    prettify_xml(elem)
    assert elem.tag == "gpx"
    assert [w.find("name").text for w in elem.findall("wpt")] == [
        "Waypoint 0",
        "Waypoint 1",
    ]
    assert elem.findall("wpt")[0].get("lat") == "46.1234567"


def test_gpx_time_element_format_is_pinned(tmp_path) -> None:
    """GPX <time> must stay `YYYY-MM-DDTHH:MM:SSZ` — onX parses this on import.

    Pins the datetime.utcnow() -> datetime.now(timezone.utc) swap: strftime with
    this format string is byte-identical for both (no %z/%Z involved), and this
    test keeps it that way through any future datetime refactor.
    """
    from cairn.core.parser import ParsedFeature
    from cairn.core.writers import write_gpx_waypoints

    features = [
        ParsedFeature(
            {
                "id": "w1",
                "geometry": {"type": "Point", "coordinates": [-114.0, 46.0]},
                "properties": {
                    "class": "Marker",
                    "title": "Timestamped",
                    "marker-symbol": "point",
                    "marker-color": "#FF0000",
                },
            }
        )
    ]
    out = tmp_path / "wpts.gpx"
    write_gpx_waypoints(features, out, "TimeTest", add_timestamps=True)

    content = out.read_text(encoding="utf-8")
    times = re.findall(r"<time>(.*?)</time>", content)
    assert times, "add_timestamps=True produced no <time> element"
    for t in times:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", t), t
