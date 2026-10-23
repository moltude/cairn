"""An onX track's style and weight pass through Cairn exactly, as an area's do.

onX keeps all three styles (solid / dash / dot) and weights (2.0 / 4.0 / 6.0) on
import (docs/ONX_ROUND_TRIP.md #area-fidelity). Cairn offers solid / dash and
4.0 / 6.0 as edits (UI-25), and anything else from an onX file is kept unless
the user changes it.
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402

ONX_GPX = """<gpx xmlns:onx="https://wwww.onxmaps.com/" xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="onXmaps backcountry web"><metadata/>
<trk><name>thin dotted</name><desc>name=thin dotted
notes=
id=11111111-1111-1111-1111-111111111111
color=rgba(255,0,0,1)
style=dot
weight=2.0</desc><extensions><onx:color>rgba(255,0,0,1)</onx:color><onx:style>dot</onx:style><onx:weight>2.0</onx:weight></extensions><trkseg><trkpt lat="46.4" lon="-121.5"><ele>0</ele></trkpt><trkpt lat="46.41" lon="-121.49"><ele>0</ele></trkpt></trkseg></trk>
<trk><name>thick dashed</name><desc>name=thick dashed
notes=
id=22222222-2222-2222-2222-222222222222
color=rgba(8,122,255,1)
style=dash
weight=6.0</desc><extensions><onx:color>rgba(8,122,255,1)</onx:color><onx:style>dash</onx:style><onx:weight>6.0</onx:weight></extensions><trkseg><trkpt lat="46.5" lon="-121.5"><ele>0</ele></trkpt><trkpt lat="46.51" lon="-121.49"><ele>0</ele></trkpt></trkseg></trk>
</gpx>"""


def _load() -> dict:
    return json.loads(bridge.load_files(json.dumps([{"name": "onx.gpx", "text": ONX_GPX}])))


def _tracks(data: dict) -> dict:
    return {i["name"]: i for g in data["groups"] for i in g["items"] if i["kind"] == "tracks"}


def _exported() -> dict:
    z = zipfile.ZipFile(io.BytesIO(bridge.export_zip()))
    text = "".join(z.read(n).decode() for n in z.namelist() if n.endswith("_Tracks.gpx"))
    out = {}
    for block in re.findall(r"<trk>.*?</trk>", text, re.S):
        name = re.search(r"<name>(.*?)</name>", block).group(1)
        out[name] = (re.search(r"<onx:style>(.*?)<", block).group(1),
                     re.search(r"<onx:weight>(.*?)<", block).group(1))
    return out


def test_onx_track_style_and_weight_pass_through_unedited():
    items = _tracks(_load())
    assert (items["thin dotted"]["style"], items["thin dotted"]["weight"]) == ("dot", "2.0")
    assert _exported() == {"thin dotted": ("dot", "2.0"), "thick dashed": ("dash", "6.0")}


def test_editing_a_dotted_thin_track_replaces_it_with_a_cairn_choice():
    items = _tracks(_load())
    bridge.apply_edits(json.dumps({items["thin dotted"]["uid"]: {"style": "dash", "weight": "4.0"}}))
    assert _exported() == {"thin dotted": ("dash", "4.0"), "thick dashed": ("dash", "6.0")}


@pytest.mark.parametrize("edit", [{"style": "dot"}, {"weight": "2.0"}])
def test_dot_and_thin_are_not_edit_choices(edit):
    items = _tracks(_load())
    with pytest.raises(ValueError):
        bridge.apply_edits(json.dumps({items["thick dashed"]["uid"]: edit}))
    assert _exported()["thick dashed"] == ("dash", "6.0")
