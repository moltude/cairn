"""The observed-icon catalog must never write into the installed package.

`observed_caltopo_symbols` / `observed_onx_icons` are write-only telemetry —
nothing in Cairn reads them back. They used to be merged into the *packaged*
`cairn/data/icon_catalog.yaml` on every run, which was wrong three ways:

1. it dirtied the git working tree on every `migrate` AND every test run;
2. it leaked test fixture names ("Test Waypoint", "JsonWaypoint") into data
   that ships to users;
3. on a real `pip`/`uv tool`/`brew` install the package lives in site-packages
   or a Cellar, which is not ours to write and may be read-only.

Recording is now opt-in via CAIRN_ICON_CATALOG. These tests pin that.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from cairn.core.icon_registry import (
    IconRegistry,
    InventoryEntry,
    catalog_write_path,
    default_catalog_path,
)


def _entry() -> InventoryEntry:
    return InventoryEntry(
        label="campsite",
        count=1,
        examples=("Fixture Waypoint",),
    )


def test_write_path_is_none_unless_opted_in(monkeypatch) -> None:
    monkeypatch.delenv("CAIRN_ICON_CATALOG", raising=False)
    assert catalog_write_path() is None


def test_write_path_honors_env_var(monkeypatch, tmp_path) -> None:
    target = tmp_path / "catalog.yaml"
    monkeypatch.setenv("CAIRN_ICON_CATALOG", str(target))
    assert catalog_write_path() == target


def test_write_path_expands_user(monkeypatch) -> None:
    monkeypatch.setenv("CAIRN_ICON_CATALOG", "~/somewhere/catalog.yaml")
    resolved = catalog_write_path()
    assert resolved is not None
    assert "~" not in str(resolved)


def test_packaged_catalog_is_not_modified_by_default(monkeypatch) -> None:
    """The regression that dirtied the repo on every run."""
    monkeypatch.delenv("CAIRN_ICON_CATALOG", raising=False)

    packaged = default_catalog_path()
    before = packaged.read_bytes() if packaged.exists() else None

    registry = IconRegistry()
    registry.append_symbol_inventory_to_catalog([_entry()])

    after = packaged.read_bytes() if packaged.exists() else None
    assert after == before, (
        "running the tool modified the packaged icon catalog; it must only "
        "record when CAIRN_ICON_CATALOG is set"
    )


def test_opt_in_records_to_the_named_file(monkeypatch, tmp_path) -> None:
    target = tmp_path / "nested" / "catalog.yaml"
    monkeypatch.setenv("CAIRN_ICON_CATALOG", str(target))

    registry = IconRegistry()
    registry.append_symbol_inventory_to_catalog([_entry()])

    assert target.exists(), "opt-in recording did not write the file"
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert data["observed_caltopo_symbols"]["campsite"]["count"] == 1
    assert "Fixture Waypoint" in data["observed_caltopo_symbols"]["campsite"]["examples"]


def test_explicit_catalog_path_still_writes(monkeypatch, tmp_path) -> None:
    """Tooling and tests that pass their own path keep working, opt-in or not."""
    monkeypatch.delenv("CAIRN_ICON_CATALOG", raising=False)
    target = tmp_path / "explicit.yaml"

    registry = IconRegistry(catalog_path=target)
    registry.append_symbol_inventory_to_catalog([_entry()])

    assert target.exists()
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert data["observed_caltopo_symbols"]["campsite"]["count"] == 1


def test_no_source_file_writes_into_the_package_dir() -> None:
    """Guard the general rule, not just this one path.

    The package directory is read-only in a real install. Nothing under
    cairn/ should compute a writable path inside cairn/data/.
    """
    registry_src = Path("cairn/core/icon_registry.py").read_text(encoding="utf-8")
    # default_catalog_path() may still POINT at the packaged file (it is read
    # as a seed); what must not happen is a write defaulting there.
    assert "def catalog_write_path()" in registry_src
    assert "CAIRN_ICON_CATALOG" in registry_src
