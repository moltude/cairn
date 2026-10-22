"""onx_kml lowercases ExtendedData keys, so the `OnX:id` fallback must be looked
up lowercased; `kv.get("OnX:id")` could never match."""

from __future__ import annotations

from cairn.io.onx_kml import read_onx_kml

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <Placemark>
    <name>Spring</name>
    <ExtendedData><Data name="OnX:id"><value>abc-123</value></Data></ExtendedData>
    <Point><coordinates>-114.1,46.2,0</coordinates></Point>
  </Placemark>
</Document></kml>
"""


def test_onx_prefixed_id_key_is_read(tmp_path):
    p = tmp_path / "onx.kml"
    p.write_text(KML, encoding="utf-8")
    doc = read_onx_kml(p)
    (wp,) = doc.waypoints()
    assert wp.style.OnX_id == "abc-123"
