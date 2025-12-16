from pathlib import Path

from cairn.core.edit_session import EditRecord, EditSession, feature_key
from cairn.core.parser import ParsedData, ParsedFeature


def _mk_feature(*, fid: str, cls: str, gtype: str, coords, title: str = "T", desc: str = "D"):
    return ParsedFeature(
        {
            "id": fid,
            "type": "Feature",
            "geometry": {"type": gtype, "coordinates": coords},
            "properties": {"class": cls, "title": title, "description": desc},
        }
    )


def test_feature_key_prefers_geojson_id():
    f = _mk_feature(fid="abc", cls="Marker", gtype="Point", coords=[-120.0, 45.0])
    k = feature_key(kind="waypoint", folder_id="folder1", feature=f)
    assert k == "folder1:waypoint:abc"


def test_session_records_and_applies_waypoint_edits():
    pd = ParsedData()
    pd.add_folder("f1", "Folder 1")
    wp = _mk_feature(fid="w1", cls="Marker", gtype="Point", coords=[-120.0, 45.0], title="Old", desc="OldD")
    pd.add_feature_to_folder("f1", wp)

    sess = EditSession(input_fingerprint="dummy")
    key = feature_key(kind="waypoint", folder_id="f1", feature=wp)
    sess.record(key=key, record=EditRecord(title="New", description="NewD", color="FF3300", onx_icon_override="Parking"))

    updated = sess.apply_to_parsed_data(pd)
    assert updated == 1
    assert wp.title == "New"
    assert wp.description == "NewD"
    assert wp.color == "FF3300"
    assert wp.properties.get("cairn_onx_icon_override") == "Parking"


def test_session_applies_track_stroke():
    pd = ParsedData()
    pd.add_folder("f1", "Folder 1")
    trk = _mk_feature(
        fid="t1",
        cls="Line",
        gtype="LineString",
        coords=[[-120.0, 45.0], [-120.1, 45.1]],
        title="Old",
        desc="OldD",
    )
    pd.add_feature_to_folder("f1", trk)

    sess = EditSession(input_fingerprint="dummy")
    key = feature_key(kind="track", folder_id="f1", feature=trk)
    sess.record(key=key, record=EditRecord(title="New", stroke="#00FF00"))

    updated = sess.apply_to_parsed_data(pd)
    assert updated == 1
    assert trk.title == "New"
    assert trk.stroke == "#00FF00"
