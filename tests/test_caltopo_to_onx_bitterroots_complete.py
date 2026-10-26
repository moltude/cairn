from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import yaml

# Drive the web app's bridge -- the same Python the browser runs -- so this
# regression covers the shipped export path, not a CLI helper.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import bridge  # noqa: E402
from tests.blank_names import export_named  # noqa: E402


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "bitterroots"
    / "Bitterroots__Complete_.json"
)


def _read_all_gpx_texts(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = sorted(n for n in zf.namelist() if n.endswith(".gpx"))
        return "\n".join(zf.read(n).decode("utf-8", errors="replace") for n in names)


def _assert_contains_near(haystack: str, needle: str, expected_near: str, *, window: int = 8000) -> None:
    """
    Assert `expected_near` appears within `window` chars of the first occurrence of `needle`.
    Keeps the integration test lightweight (no full XML parsing) while still coupling
    attributes to a specific named feature.
    """
    i = haystack.find(needle)
    assert i != -1, f"Expected to find {needle!r} in export"
    start = max(0, i - window)
    end = min(len(haystack), i + window)
    chunk = haystack[start:end]
    assert expected_near in chunk, f"Expected to find {expected_near!r} near {needle!r}"


def test_bitterroots_complete_caltopo_to_onx_export_standardizes_icons_and_track_colors(
    tmp_path: Path, monkeypatch
) -> None:
    """
    Large, realistic CalTopo→OnX regression test.

    This fixture includes many folders, marker symbols, and styled tracks. We define an
    explicit “standardization contract” via a test config and then assert the exported
    OnX GPX reflects it.

    Standardization choices (v1):
    - CalTopo marker-symbol → OnX icon
      - climbing-2 → Climbing
      - circle-p   → Parking
      - peak       → Summit
      - hut        → Shelter
      - danger     → Hazard   (used for “Avy hazard area”)
    - Track colors are quantized to the official OnX palette:
      - #0000FF → rgba(8,122,255,1)  (OnX Blue)
      - #FF0000 → rgba(255,0,0,1)   (OnX Red)
    """
    assert FIXTURE.exists(), f"Missing fixture: {FIXTURE}"

    # Write a config used only for this test so expectations are explicit.
    cfg_path = tmp_path / "cairn_config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "symbol_mappings": {
                    "climbing-2": "Climbing",
                    "circle-p": "Parking",
                    "peak": "Summit",
                    "hut": "Shelter",
                    "danger": "Hazard",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bridge, "CONFIG_PATH", cfg_path)

    bridge.load_document(FIXTURE.read_text(encoding="utf-8"), FIXTURE.name)
    zip_bytes = export_named(bridge)

    gpx = _read_all_gpx_texts(zip_bytes)
    # Sanity: should produce GPX artifacts for a dataset this size.
    assert gpx, "No GPX files were produced"

    # Icon standardization assertions.
    for icon in ("Climbing", "Parking", "Summit", "Shelter", "Hazard"):
        assert (
            f"<onx:icon>{icon}</onx:icon>" in gpx
        ), f"Expected OnX icon {icon} to appear in export"

    # Track color standardization assertions (quantized to official OnX palette).
    assert "<onx:color>rgba(8,122,255,1)</onx:color>" in gpx  # blue
    assert "<onx:color>rgba(255,0,0,1)</onx:color>" in gpx  # red

    # Couple color expectations to a couple of known track names in the fixture.
    _assert_contains_near(
        gpx,
        "<name>Yurt Drop to North Fork Salmon River</name>",
        "<onx:color>rgba(8,122,255,1)</onx:color>",
    )
    _assert_contains_near(
        gpx,
        "<name>Lost horse main wall approach</name>",
        "<onx:color>rgba(255,0,0,1)</onx:color>",
    )

    # Couple icon expectation to a known hazard waypoint in the fixture.
    _assert_contains_near(
        gpx,
        "<name>Avy hazard area</name>",
        "<onx:icon>Hazard</onx:icon>",
    )
