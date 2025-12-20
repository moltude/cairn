from __future__ import annotations

import sys
from pathlib import Path

from cairn.ui.state import (
    UIState,
    add_favorite,
    add_recent,
    default_state_path,
    load_state,
    save_state,
    set_default_root,
)


def test_default_state_path_shape() -> None:
    p = default_state_path()
    assert isinstance(p, Path)
    # Cross-platform: always ends with cairn/state.json
    assert p.as_posix().endswith("cairn/state.json")

    plat = sys.platform.lower()
    if plat == "darwin":
        assert "Library/Application Support" in str(p)


def test_state_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    st = UIState()
    st = add_favorite(st, tmp_path / "fav1")
    st = add_recent(st, tmp_path / "recent1")
    st = set_default_root(st, tmp_path)
    save_state(st, p)

    st2 = load_state(p)
    assert st2.favorites == st.favorites
    assert st2.recent_paths == st.recent_paths
    assert st2.default_root == st.default_root


def test_add_recent_dedup_and_limit(tmp_path: Path) -> None:
    st = UIState()
    for i in range(30):
        st = add_recent(st, tmp_path / f"p{i}", limit=20)
    assert len(st.recent_paths) == 20

    # Adding an existing path moves it to the front
    st = add_recent(st, tmp_path / "p15", limit=20)
    assert st.recent_paths[0].endswith("p15")
    assert len(st.recent_paths) == 20
