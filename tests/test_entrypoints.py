import runpy
import sys

import pytest


def test_cli_main_calls_app(monkeypatch):
    import cairn.cli as cli

    called = {"ok": False}

    def _fake_app():
        called["ok"] = True

    monkeypatch.setattr(cli, "app", _fake_app)
    cli.main()
    assert called["ok"] is True


def test_python_m_cairn_invokes_cli_main(monkeypatch):
    import cairn.cli as cli

    called = {"ok": False}

    def _fake_main():
        called["ok"] = True

    monkeypatch.setattr(cli, "main", _fake_main)

    # Ensure we re-execute the module body.
    sys.modules.pop("cairn.__main__", None)
    runpy.run_module("cairn.__main__", run_name="__main__")
    assert called["ok"] is True


def test_cairn_cli_module_guard_runs(monkeypatch):
    """
    Cover cairn/cli.py's `if __name__ == "__main__": main()` branch.
    Run it with `--help` so it exits quickly.
    """
    monkeypatch.setattr(sys, "argv", ["cairn", "--help"])
    # Ensure we re-execute the module body.
    sys.modules.pop("cairn.cli", None)
    with pytest.raises(SystemExit) as e:
        runpy.run_module("cairn.cli", run_name="__main__")
    assert e.value.code == 0
