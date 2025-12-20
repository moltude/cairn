from __future__ import annotations

from pathlib import Path

import yaml

from cairn.commands.convert_cmd import process_and_write_files
from cairn.core.config import load_config
from cairn.core.parser import parse_geojson


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "bitterroots"
    / "Bitterroots__Complete_.json"
)


def _read_all_gpx_texts(out_dir: Path) -> str:
    chunks = []
    for p in sorted(out_dir.glob("*.gpx")):
        chunks.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


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
    tmp_path: Path,
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
      - hut        → Cabin
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
                    "hut": "Cabin",
                    "danger": "Hazard",
                }
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)

    parsed = parse_geojson(FIXTURE)

    # Export using the same helper used by the CLI, but without interactive prompts.
    out_dir = tmp_path / "onx_ready"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_files = process_and_write_files(
        parsed,
        out_dir,
        sort=True,
        skip_confirmation=True,
        config=cfg,
        split_gpx=True,
        max_gpx_bytes=4 * 1024 * 1024,
    )

    # Sanity: should produce multiple artifacts for a dataset this size.
    assert output_files, "No export files were produced"
    assert any(n.endswith(".gpx") for (n, _fmt, _cnt, _sz) in output_files)

    gpx = _read_all_gpx_texts(out_dir)

    # Icon standardization assertions.
    for icon in ("Climbing", "Parking", "Summit", "Cabin", "Hazard"):
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
