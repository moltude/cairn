from cairn.core.diagnostics import check_data_quality
from cairn.model import MapDocument, Style, Track, Waypoint


def test_check_data_quality_detects_empty_names_duplicates_and_suspicious_coords_and_empty_tracks():
    doc = MapDocument(metadata={})
    doc.ensure_folder("f", "F")

    doc.add_item(Waypoint(id="w1", folder_id="f", name="Dup", lon=0.0, lat=0.0, style=Style()))
    doc.add_item(Waypoint(id="w2", folder_id="f", name="Dup", lon=-200.0, lat=95.0, style=Style()))
    doc.add_item(Waypoint(id="w3", folder_id="f", name="Untitled", lon=1.0, lat=2.0, style=Style()))
    doc.add_item(Track(id="t1", folder_id="f", name="EmptyTrack", points=[], style=Style()))

    warnings = check_data_quality(doc)

    assert warnings["empty_names"]  # includes Untitled
    assert any(name == "Dup" for (name, _count, _items) in warnings["duplicate_names"])
    # null island + out-of-range should both show up
    reasons = [r[-1] for r in warnings["suspicious_coords"]]
    assert any("Near (0,0)" in r for r in reasons)
    assert any("Out of valid range" in r for r in reasons)
    assert ("t1", "EmptyTrack") in warnings["empty_tracks"]
