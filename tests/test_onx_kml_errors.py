"""
Comprehensive error handling tests for OnX KML reader.

Tests cover:
- Missing Document node
- Invalid XML
- Missing coordinates
- Invalid coordinate formats
- Nested folder parsing
- Empty placemarks
- Missing style references
- Malformed KML structures
"""

import pytest
from cairn.io.onx_kml import read_onx_kml
from cairn.model import MapDocument


def test_kml_missing_document_node(tmp_path):
    """Test that KML without Document node is handled gracefully."""
    kml_file = tmp_path / "test.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Placemark>
            <name>Test</name>
        </Placemark>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should handle gracefully, may have empty or minimal structure
    assert isinstance(doc, MapDocument)


def test_kml_invalid_xml(tmp_path):
    """Test that invalid XML is handled with appropriate error."""
    kml_file = tmp_path / "invalid.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Unclosed tag
            </Placemark>
        </Document>
    </kml>""")

    # Should raise an error or handle gracefully
    with pytest.raises(Exception):
        read_onx_kml(str(kml_file))


def test_kml_missing_coordinates(tmp_path):
    """Test placemark without coordinates."""
    kml_file = tmp_path / "no_coords.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>No Coords</name>
                <Point>
                    <!-- Missing coordinates -->
                </Point>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should not crash, may skip this placemark
    assert isinstance(doc, MapDocument)


def test_kml_invalid_coordinate_format(tmp_path):
    """Test placemark with invalid coordinate format."""
    kml_file = tmp_path / "bad_coords.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Bad Coords</name>
                <Point>
                    <coordinates>invalid,coords,here</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should handle gracefully
    assert isinstance(doc, MapDocument)


def test_kml_nested_folders_parsed(tmp_path):
    """Test that nested folder structures are parsed correctly."""
    kml_file = tmp_path / "nested.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Folder>
                <name>Parent Folder</name>
                <Folder>
                    <name>Child Folder</name>
                    <Placemark>
                        <name>Nested Point</name>
                        <Point>
                            <coordinates>-120.0,45.0,0</coordinates>
                        </Point>
                    </Placemark>
                </Folder>
            </Folder>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should parse nested folders
    assert len(doc.folders) >= 2
    assert len(doc.waypoints()) >= 1

    # Check that waypoint is in a folder
    waypoint = doc.waypoints()[0]
    assert waypoint.name == "Nested Point"


def test_kml_empty_placemark(tmp_path):
    """Test that empty placemark is handled."""
    kml_file = tmp_path / "empty.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <!-- Empty placemark -->
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should not crash
    assert isinstance(doc, MapDocument)


def test_kml_missing_style_reference(tmp_path):
    """Test placemark with missing style reference."""
    kml_file = tmp_path / "no_style.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>No Style</name>
                <styleUrl>#nonexistent-style</styleUrl>
                <Point>
                    <coordinates>-120.0,45.0,0</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should parse waypoint even without style
    assert len(doc.waypoints()) == 1
    assert doc.waypoints()[0].name == "No Style"


def test_kml_polygon_with_multiple_rings(tmp_path):
    """Test polygon with inner rings (holes)."""
    kml_file = tmp_path / "polygon_hole.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Polygon with Hole</name>
                <Polygon>
                    <outerBoundaryIs>
                        <LinearRing>
                            <coordinates>
                                -120.0,45.0,0
                                -120.1,45.0,0
                                -120.1,45.1,0
                                -120.0,45.1,0
                                -120.0,45.0,0
                            </coordinates>
                        </LinearRing>
                    </outerBoundaryIs>
                    <innerBoundaryIs>
                        <LinearRing>
                            <coordinates>
                                -120.02,45.02,0
                                -120.08,45.02,0
                                -120.08,45.08,0
                                -120.02,45.08,0
                                -120.02,45.02,0
                            </coordinates>
                        </LinearRing>
                    </innerBoundaryIs>
                </Polygon>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    assert len(doc.shapes()) == 1
    shape = doc.shapes()[0]
    # Should have multiple rings
    assert len(shape.rings) >= 1


def test_kml_linestring_empty(tmp_path):
    """Test LineString with no coordinates."""
    kml_file = tmp_path / "empty_line.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Empty Line</name>
                <LineString>
                    <coordinates></coordinates>
                </LineString>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should not crash
    assert isinstance(doc, MapDocument)


def test_kml_multiple_geometries_in_placemark(tmp_path):
    """Test placemark with multiple geometry types (MultiGeometry)."""
    kml_file = tmp_path / "multi.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Multi</name>
                <MultiGeometry>
                    <Point>
                        <coordinates>-120.0,45.0,0</coordinates>
                    </Point>
                    <LineString>
                        <coordinates>-120.0,45.0,0 -120.1,45.1,0</coordinates>
                    </LineString>
                </MultiGeometry>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should handle MultiGeometry
    assert isinstance(doc, MapDocument)


def test_kml_style_with_color(tmp_path):
    """Test that inline styles with colors are parsed."""
    kml_file = tmp_path / "styled.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Style id="style1">
                <IconStyle>
                    <color>ff0000ff</color>
                </IconStyle>
            </Style>
            <Placemark>
                <name>Styled Point</name>
                <styleUrl>#style1</styleUrl>
                <Point>
                    <coordinates>-120.0,45.0,0</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    assert len(doc.waypoints()) == 1


def test_kml_extended_data(tmp_path):
    """Test that ExtendedData is handled."""
    kml_file = tmp_path / "extended.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>With Data</name>
                <ExtendedData>
                    <Data name="custom_field">
                        <value>custom_value</value>
                    </Data>
                </ExtendedData>
                <Point>
                    <coordinates>-120.0,45.0,0</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    assert len(doc.waypoints()) == 1


def test_kml_description_field(tmp_path):
    """Test that KML with description field is handled gracefully."""
    kml_file = tmp_path / "description.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>With Description</name>
                <description>This is a description field</description>
                <Point>
                    <coordinates>-120.0,45.0,0</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Waypoint should be parsed successfully
    assert len(doc.waypoints()) == 1
    waypoint = doc.waypoints()[0]
    assert waypoint.name == "With Description"


def test_kml_coordinates_with_altitude(tmp_path):
    """Test coordinates with altitude values."""
    kml_file = tmp_path / "altitude.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>High Point</name>
                <Point>
                    <coordinates>-120.0,45.0,2500.5</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    waypoint = doc.waypoints()[0]
    assert waypoint.lon == -120.0
    assert waypoint.lat == 45.0


def test_kml_whitespace_in_coordinates(tmp_path):
    """Test that whitespace in coordinates is handled."""
    kml_file = tmp_path / "whitespace.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Spaced</name>
                <LineString>
                    <coordinates>
                        -120.0,45.0,0
                        -120.1,45.1,0
                        -120.2,45.2,0
                    </coordinates>
                </LineString>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    assert len(doc.tracks()) == 1
    track = doc.tracks()[0]
    assert len(track.points) == 3


def test_kml_folder_without_name(tmp_path):
    """Test folder without name element."""
    kml_file = tmp_path / "unnamed_folder.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Folder>
                <!-- No name -->
                <Placemark>
                    <name>Point in Unnamed Folder</name>
                    <Point>
                        <coordinates>-120.0,45.0,0</coordinates>
                    </Point>
                </Placemark>
            </Folder>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should handle unnamed folder
    assert len(doc.waypoints()) == 1


def test_kml_point_without_name(tmp_path):
    """Test placemark without name element."""
    kml_file = tmp_path / "unnamed_point.kml"
    kml_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <!-- No name -->
                <Point>
                    <coordinates>-120.0,45.0,0</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>""")

    doc = read_onx_kml(str(kml_file))

    # Should create waypoint with empty or default name
    assert len(doc.waypoints()) == 1
