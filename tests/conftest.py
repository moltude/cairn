"""Shared test setup.

The browser writes web/cairn_config.yaml to /cairn_config.yaml before it loads a
map (web/app.js), so web/bridge.py always runs with that config there. Python
tests have no /cairn_config.yaml, and since load_config(None) stopped reading
./cairn_config.yaml (2026-10-25) the bridge fell back to the built-in defaults
-- unless an earlier test had pointed bridge.CONFIG_PATH at the web config and
left it there. That made the Bitterroots byte pin pass or fail by test order.
Every test now sees the browser's config, set and restored per test; a test
that wants another config monkeypatches CONFIG_PATH itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB_CONFIG = ROOT / "web" / "cairn_config.yaml"


@pytest.fixture(autouse=True)
def _bridge_uses_the_browsers_config(monkeypatch):
    bridge = sys.modules.get("bridge")
    if bridge is None:
        if str(ROOT / "web") not in sys.path:
            sys.path.insert(0, str(ROOT / "web"))
        import bridge  # noqa: PLC0415  (web/bridge.py, as the tests import it)
    monkeypatch.setattr(bridge, "CONFIG_PATH", WEB_CONFIG)
    yield
