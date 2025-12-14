"""Integration tests for cairn CLI."""

import pytest
from typer.testing import CliRunner
from cairn.cli import app


runner = CliRunner()


class TestCLI:
    """Integration tests for CLI commands."""

    def test_help(self):
        """--help works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "CalTopo" in result.stdout or "caltopo" in result.stdout.lower()

    def test_convert_help(self):
        """convert --help works."""
        result = runner.invoke(app, ["convert", "--help"])
        assert result.exit_code == 0
        assert "INPUT_FILE" in result.stdout or "input" in result.stdout.lower()

    def test_migrate_help(self):
        """migrate --help works."""
        result = runner.invoke(app, ["migrate", "--help"])
        assert result.exit_code == 0

    def test_migrate_onx_to_caltopo_help(self):
        """migrate onx-to-caltopo --help works."""
        result = runner.invoke(app, ["migrate", "onx-to-caltopo", "--help"])
        assert result.exit_code == 0
        out = result.stdout.lower()
        assert "onx" in out and "caltopo" in out

    def test_config_help(self):
        """config --help works."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0

    def test_icon_help(self):
        """icon --help works."""
        result = runner.invoke(app, ["icon", "--help"])
        assert result.exit_code == 0

    def test_icon_list(self):
        """icon list shows available icons."""
        result = runner.invoke(app, ["icon", "list"])
        assert result.exit_code == 0
        # Should contain some common icon names
        output_lower = result.stdout.lower()
        assert "campsite" in output_lower or "waypoint" in output_lower or "location" in output_lower

    def test_convert_missing_file(self):
        """convert with missing file shows error."""
        result = runner.invoke(app, ["convert", "nonexistent_file.json"])
        assert result.exit_code != 0 or "error" in result.stdout.lower() or "not found" in result.stdout.lower()
