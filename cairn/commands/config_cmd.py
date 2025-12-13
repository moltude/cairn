"""Config command for Cairn CLI."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
import re

from cairn.core.config import load_config, get_all_onx_icons
from cairn.core.config_manager import ConfigManager
from cairn.core.mapper import get_icon_emoji

app = typer.Typer()
console = Console()


@app.command("show")
def show():
    """Show current configuration."""
    cfg = load_config()
    summary = cfg.get_config_summary()

    console.print("\n[bold]Current Configuration:[/]")
    console.print(f"  Symbol mappings: [cyan]{summary['symbol_mappings_count']}[/]")
    console.print(f"  Keyword mappings: [cyan]{summary['keyword_mappings_count']}[/]")
    console.print(f"  Unique onX icons: [cyan]{summary['unique_onx_icons']}[/]")
    console.print(f"  Unmapped detection: [cyan]{'Enabled' if summary['unmapped_detection_enabled'] else 'Disabled'}[/]")

    console.print("\n[bold]Available onX Icons:[/]")
    unique_icons = sorted(set(cfg.symbol_map.values()))
    for icon in unique_icons:
        emoji = get_icon_emoji(icon)
        console.print(f"  {emoji} {icon}")
    console.print()


@app.command("export")
def export():
    """Export configuration template."""
    output_path = Path("cairn_config.json")
    cfg = load_config()
    cfg.export_template(output_path)
    console.print(f"[bold green]✔[/] Configuration template exported to [underline]{output_path}[/]")
    console.print("[dim]Edit this file to customize icon mappings[/]")


@app.command("validate")
def validate(config_file: Path = typer.Argument(..., help="Config file to validate")):
    """Validate a configuration file."""
    try:
        cfg = load_config(config_file)
        console.print(f"[bold green]✔[/] Configuration file is valid: [underline]{config_file}[/]")
        summary = cfg.get_config_summary()
        console.print(f"  Symbol mappings: {summary['symbol_mappings_count']}")
        console.print(f"  Keyword mappings: {summary['keyword_mappings_count']}")
    except Exception as e:
        console.print(f"[bold red]❌ Invalid configuration:[/] {e}")
        raise typer.Exit(1)


@app.command("set-default-icon")
def set_default_icon(icon: str = typer.Argument(..., help="Icon name")):
    """Set default icon for unmapped symbols."""
    valid_icons = get_all_onx_icons()
    if icon not in valid_icons:
        console.print(f"[bold red]❌ Error:[/] '{icon}' is not a valid onX icon")
        console.print("[dim]Run 'cairn icon list' to see all available icons[/]")
        raise typer.Exit(1)

    config_mgr = ConfigManager()
    config_mgr.set_default_icon(icon)
    console.print(f"[bold green]✔[/] Default icon set to: [cyan]{icon}[/]")


@app.command("set-default-color")
def set_default_color(color: str = typer.Argument(..., help="Color in rgba format")):
    """Set default color."""
    if not re.match(r'rgba\(\d+,\s*\d+,\s*\d+,\s*[\d.]+\)', color):
        console.print(f"[bold red]❌ Error:[/] Invalid color format")
        console.print("[dim]Expected format: rgba(r,g,b,a) e.g. rgba(255,0,0,1)[/]")
        raise typer.Exit(1)

    config_mgr = ConfigManager()
    config_mgr.set_default_color(color)
    console.print(f"[bold green]✔[/] Default color set to: [cyan]{color}[/]")
