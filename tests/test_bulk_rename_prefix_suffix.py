from __future__ import annotations

from cairn.core.preview import _apply_rename_prefix_suffix, _rename_preview_samples


class _Feat:
    def __init__(self, title: str) -> None:
        self.title = title


def test_rename_preview_samples_trim() -> None:
    rows = _rename_preview_samples(
        [_Feat("  A  "), _Feat("B")], prefix="pre-", suffix="-suf", trim=True, max_samples=8
    )
    assert rows[0] == ("  A  ", "pre-A-suf")
    assert rows[1] == ("B", "pre-B-suf")


def test_apply_rename_prefix_suffix_updates_titles() -> None:
    a = _Feat("  A  ")
    b = _Feat("B")
    _apply_rename_prefix_suffix([a, b], prefix="X", suffix="Y", trim=True)
    assert a.title == "XAY"
    assert b.title == "XBY"
