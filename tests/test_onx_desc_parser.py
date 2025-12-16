from cairn.io.onx_gpx import parse_onx_desc_kv


def test_parse_OnX_desc_kv_multiline_notes_and_known_keys():
    desc = "\n".join(
        [
            "name=Foo",
            "notes=Line1",
            "Line2",
            "id=abc-123",
            "color=rgba(1,2,3,1)",
            "icon=Hazard",
        ]
    )
    kv, notes = parse_onx_desc_kv(desc)

    assert kv["name"] == "Foo"
    assert kv["id"] == "abc-123"
    assert kv["color"] == "rgba(1,2,3,1)"
    assert kv["icon"] == "Hazard"
    assert notes == "Line1\nLine2"


def test_parse_OnX_desc_kv_non_kv_first_line_treated_as_notes():
    desc = "Just some notes\nSecond line"
    kv, notes = parse_onx_desc_kv(desc)
    assert kv.get("notes") == "Just some notes\nSecond line"
    assert notes == "Just some notes\nSecond line"


def test_parse_OnX_desc_kv_unknown_key_value_is_preserved_as_notes():
    desc = "unknown_key=hello\nstill notes"
    kv, notes = parse_onx_desc_kv(desc)
    assert "unknown_key=hello" in notes
    assert "still notes" in notes
