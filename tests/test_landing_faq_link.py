"""Landing names the three formats without a round-trip pitch; the FAQ keeps the how-to section."""
import pathlib

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"


def _drop_stage() -> str:
    index = (WEB / "index.html").read_text(encoding="utf-8")
    return index[index.index('id="drop-stage"'):index.index('id="edit-stage"')]


def test_landing_names_all_three_formats():
    drop = _drop_stage()
    for fmt in ("GeoJSON", "KML", "GPX"):
        assert fmt in drop


def test_landing_does_not_pitch_the_round_trip():
    drop = _drop_stage().lower()
    assert "round-trip" not in drop and "faq.html" not in drop


def test_faq_has_format_and_round_trip_sections():
    faq = (WEB / "faq.html").read_text(encoding="utf-8")
    assert "Which file should I export?" in faq
    assert "Round-tripping onX data (batch edits)" in faq
