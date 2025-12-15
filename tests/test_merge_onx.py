from cairn.core.merge import merge_onx_gpx_and_kml
from cairn.model import MapDocument, Shape, Style, Track


def test_merge_prefers_polygon_for_same_OnX_id_and_transfers_metadata():
    # Base GPX doc has a Track with style/notes.
    gpx = MapDocument(metadata={"path": "gpx"})
    gpx.ensure_folder("OnX_tracks", "Tracks")
    trk = Track(
        id="t1",
        folder_id="OnX_tracks",
        name="SameId",
        points=[(-120.0, 45.0, None, None), (-120.1, 45.1, None, None)],
        notes="trk notes",
        style=Style(OnX_id="OID", OnX_color_rgba="rgba(8,122,255,1)", OnX_style="dash", OnX_weight="6.0"),
    )
    gpx.add_item(trk)

    # KML doc has a Shape with the same OnX_id but missing notes/style details.
    kml = MapDocument(metadata={"path": "kml"})
    kml.ensure_folder("OnX_shapes", "Areas")
    shp = Shape(
        id="s1",
        folder_id="OnX_shapes",
        name="SameId",
        rings=[[(-120.0, 45.0), (-120.1, 45.0), (-120.1, 45.1), (-120.0, 45.0)]],
        notes="",
        style=Style(OnX_id="OID"),
    )
    kml.add_item(shp)

    merged = merge_onx_gpx_and_kml(gpx, kml)

    assert merged.tracks() == []
    shapes = merged.shapes()
    assert len(shapes) == 1
    kept = shapes[0]
    assert kept.style.OnX_id == "OID"
    assert kept.notes == "trk notes"
    assert kept.style.OnX_color_rgba == "rgba(8,122,255,1)"
    assert kept.style.OnX_style == "dash"
    assert kept.style.OnX_weight == "6.0"
    assert kept.extra.get("merge_decisions")
