"""Re-importing an onX export through Cairn: notes unwrap, and no onX id leaks out.

The fixture pair is a real onX web app export after three GPX round trips
(docs/ONX_ROUND_TRIP.md, multi-step-cycle-gpx). Every round trip makes onX store
the uploaded <desc> block as the new markup's note, so the notes nest. onX
never matches on ids (docs/ONX_ROUND_TRIP.md), so an id in Cairn's output
could only end up as visible note text.
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

from cairn.io.onx_gpx import read_onx_gpx
from cairn.io.onx_kml import read_onx_kml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402

FX = Path(__file__).parent / "fixtures" / "onx_exports"
GPX = FX / "three-round-trips.gpx"
KML = FX / "three-round-trips.kml"

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# The markups' current onX ids (the last id= in each GPX <desc>, the KML id field)
# and the user's own notes (the innermost notes=).
CURRENT = {
    "Waypoint": ("5396e8c2-051c-4a8c-a6e7-761af2835c02", "edited-2 waypoint note"),
    "Track": ("69d7fc78-feab-417d-93d5-29dbe12af124", "edited-2 line note"),
    "Shape": ("0b54c7db-1da4-484a-bf0b-c3d40e5bce33", "edited-2 area note"),
}


@pytest.mark.parametrize("reader,path", [(read_onx_gpx, GPX), (read_onx_kml, KML)],
                         ids=["gpx", "kml"])
def test_reader_takes_the_innermost_note_and_the_current_id(reader, path):
    got = {type(i).__name__: (i.id, i.notes) for i in reader(path).items}
    assert got == CURRENT


def test_kml_note_that_is_not_an_onx_block_is_kept_as_is(tmp_path):
    note = "Approach from the north.\nid=not-a-key-line, just text"
    kml = tmp_path / "plain.kml"
    kml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2">'
        "<Document><Placemark><name>P</name><ExtendedData>"
        f'<Data name="notes"><value>{note}</value></Data>'
        '<Data name="id"><value>11111111-2222-3333-4444-555555555555</value></Data>'
        "</ExtendedData><Point><coordinates>-121.5,46.4,0</coordinates></Point>"
        "</Placemark></Document></kml>",
        encoding="utf-8",
    )
    [wp] = read_onx_kml(kml).items
    assert wp.notes == note


def _source_uuids() -> set[str]:
    return set(UUID_RE.findall(GPX.read_text(encoding="utf-8"))) | set(
        UUID_RE.findall(KML.read_text(encoding="utf-8"))
    )


@pytest.mark.parametrize("paths", [[GPX], [KML], [GPX, KML]], ids=["gpx", "kml", "gpx+kml"])
def test_export_of_an_onx_export_carries_no_onx_id(paths):
    files = [{"name": p.name, "text": p.read_text(encoding="utf-8")} for p in paths]
    json.loads(bridge.load_files(json.dumps(files)))
    z = zipfile.ZipFile(io.BytesIO(bridge.export_zip()))
    out = "\n".join(
        z.read(n).decode("utf-8") for n in z.namelist() if n.endswith((".gpx", ".kml"))
    )
    assert out, "the export wrote no map files"
    leaked = _source_uuids() & set(UUID_RE.findall(out))
    assert not leaked, f"onX ids in Cairn's output: {sorted(leaked)}"
    assert "id=" not in out
    for _, note in CURRENT.values():
        assert note in out
    # Older exports' blocks must not come back as note text either.
    assert "notes=name=" not in out and "name=ZZTEST" not in out
