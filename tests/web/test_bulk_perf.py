"""Bulk rename: the performance budget.

Maps of 1,500 and 3,000 items (3,000 is onX's account and import cap), generated at test time
by tests/hardening_maps.make_map into tmp_path, never under tests/fixtures/. Every row selected,
Rename... opened, 8 characters typed one at a time, then Save. The app times itself with
performance.now() in window.__cairnPerf (lastTransformMs and lastPreviewMs from the list render,
lastSaveMs from Save, edits and refresh included).

Budgets: transform 10 ms, the list 50 ms per keystroke, Save 500 ms; three times that when CI is
set. The raw numbers are printed either way (pytest -s, or -rP, shows them).

The module skips while the served page has no Rename... menu item (#bulk-rename).
"""
from __future__ import annotations

import os
import time
import urllib.request

import pytest
from playwright.sync_api import Page, expect

from tests.hardening_maps import make_map
from tests.web.helpers import (
    BASE_URL, _open_bulk, _preview_seq, _save_bulk, _select_all_shown, _set_mode, _status_count,
    _type_spec, _wait_preview_past,
)

SCALE = 3 if os.environ.get("CI") else 1
TRANSFORM_MS, PREVIEW_MS, SAVE_MS = 10 * SCALE, 50 * SCALE, 500 * SCALE
TYPED = "Base 12 "   # 8 characters: one list render each


@pytest.fixture(scope="module", autouse=True)
def _require_rename_dialog(_require_server):
    """After the server check: skip until the page has Rename... (not a skipif
    marker, which would run before it and call a down server "not built")."""
    with urllib.request.urlopen(f"{BASE_URL}/index.html", timeout=5) as resp:
        html = resp.read().decode("utf-8")
    if 'id="bulk-rename"' not in html:
        pytest.skip("the bulk rename dialog (#bulk-rename) is not built yet")


def _perf(page: Page) -> dict:
    return page.evaluate("() => ({...window.__cairnPerf})")


def _load_generated_map(page: Page, tmp_path, n_folders: int) -> int:
    """make_map(n_folders, per=(150, 150)): 150 items a folder, plus two loose ones."""
    path = tmp_path / f"bulk_perf_{n_folders}.json"
    path.write_text(make_map(n_folders, per=(150, 150)), encoding="utf-8")
    page.set_input_files("#file", str(path))
    page.wait_for_function("window.__cairnLoaded === true", timeout=180_000)
    # The generated areas are filled, so the onX fill warning opens at load: keep them.
    if page.locator("#confirm").is_visible():
        page.keyboard.press("Escape")
    expect(page.locator("#confirm")).to_be_hidden()
    n = page.evaluate("allItems().length")
    _select_all_shown(page)
    expect(page.locator("#selcount")).to_have_text(f"{n} selected", timeout=10_000)
    return n


def _prefix_every_row(page: Page, tmp_path, n_folders: int):
    n = _load_generated_map(page, tmp_path, n_folders)
    _open_bulk(page, "rename")
    expect(page.locator("#mark-dialog h2")).to_have_text(f"Rename {n:,} items")
    field = page.locator("#bulk-text")
    transforms, previews = [], []
    for ch in TYPED:
        seq = _preview_seq(page)
        field.press_sequentially(ch)
        _wait_preview_past(page, seq)
        p = _perf(page)
        transforms.append(p["lastTransformMs"]); previews.append(p["lastPreviewMs"])
    expect(page.locator("#bulk-summary")).to_have_text(f"{n:,} will change · 0 unchanged")
    assert _status_count(_save_bulk(page)) == n
    save = _perf(page)["lastSaveMs"]
    print(f"\n[bulk perf] {n:,} rows, prefix {TYPED!r} typed a key at a time, then Save "
          f"(budgets: transform {TRANSFORM_MS} ms, list {PREVIEW_MS} ms, Save {SAVE_MS} ms)\n"
          f"  transform ms: {[round(x, 2) for x in transforms]}\n"
          f"  list ms:      {[round(x, 2) for x in previews]}\n"
          f"  Save ms:      {round(save, 2)}")
    return n, transforms, previews, save


def _assert_within_budget(n, transforms, previews, save):
    assert len(transforms) == len(previews) == len(TYPED)
    assert max(transforms) <= TRANSFORM_MS, f"{n:,} rows: transform {max(transforms):.2f} ms > {TRANSFORM_MS} ms"
    assert max(previews) <= PREVIEW_MS, f"{n:,} rows: list {max(previews):.2f} ms > {PREVIEW_MS} ms"
    assert 0 < save <= SAVE_MS, f"{n:,} rows: Save {save:.2f} ms > {SAVE_MS} ms"


def test_a_prefix_on_1500_rows_stays_under_the_preview_budget(fresh_page: Page, tmp_path):
    _assert_within_budget(*_prefix_every_row(fresh_page, tmp_path, 10))


def test_a_prefix_on_3000_rows_stays_under_the_preview_budget(fresh_page: Page, tmp_path):
    _assert_within_budget(*_prefix_every_row(fresh_page, tmp_path, 20))


def test_a_find_string_longer_than_10k_characters_does_not_hang(fresh_page: Page, tmp_path):
    page = fresh_page
    n = _load_generated_map(page, tmp_path, 10)
    _open_bulk(page, "rename")
    _set_mode(page, "replace")
    t0 = time.monotonic()
    _type_spec(page, find="a" * 10_000)
    find_wall = (time.monotonic() - t0) * 1000
    p1 = _perf(page)
    _type_spec(page, repl="b")
    p2 = _perf(page)
    print(f"\n[bulk perf] {n:,} rows, Find of 10,000 'a': typed and listed in {find_wall:.0f} ms; "
          f"transform {p1['lastTransformMs']:.2f} / {p2['lastTransformMs']:.2f} ms, "
          f"list {p1['lastPreviewMs']:.2f} / {p2['lastPreviewMs']:.2f} ms")
    assert max(p1["lastTransformMs"], p2["lastTransformMs"]) <= TRANSFORM_MS
    assert max(p1["lastPreviewMs"], p2["lastPreviewMs"]) <= PREVIEW_MS
    # Nothing matches: every row "No change", Save off.
    expect(page.locator("#bulk-summary")).to_have_text(f"0 will change · {n:,} unchanged")
    expect(page.locator("#bulk-apply")).to_be_disabled()
    flags = page.eval_on_selector_all("#mark-dialog .na-row", "rs => rs.map(r => r.dataset.flags)")
    assert flags and all("unchanged" in f.split() for f in flags)
