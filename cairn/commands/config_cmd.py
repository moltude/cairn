"""Config command for Cairn CLI."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
import re
import yaml

from cairn.core.config import load_config, normalize_onx_icon_name, get_icon_emoji
from cairn.core.color_mapper import ColorMapper

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
    console.print(f"  Unique OnX icons: [cyan]{summary['unique_OnX_icons']}[/]")
    console.print(f"  Unmapped detection: [cyan]{'Enabled' if summary['unmapped_detection_enabled'] else 'Disabled'}[/]")
    console.print(f"  Icon name prefixes: [cyan]{'Enabled' if summary.get('use_icon_name_prefix') else 'Disabled'}[/]")
    console.print(f"  Default icon: [cyan]{summary.get('default_icon', 'Location')}[/]")
    console.print(f"  Default color: [cyan]{summary.get('default_color', 'rgba(8,122,255,1)')}[/]")

    console.print("\n[bold]Available OnX Icons:[/]")
    unique_icons = sorted(set(cfg.symbol_map.values()))
    for icon in unique_icons:
        emoji = get_icon_emoji(icon)
        console.print(f"  {emoji} {icon}")
    console.print()


@app.command("export")
def export():
    """Export configuration template."""
    output_path = Path("cairn_config.yaml")
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
    icon_canon = normalize_onx_icon_name(icon)
    if icon_canon is None:
        console.print(f"[bold red]❌ Error:[/] '{icon}' is not a valid OnX icon")
        console.print("[dim]Run 'cairn icon list' to see all available icons[/]")
        raise typer.Exit(1)

    config_path = Path("cairn_config.yaml")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    data["default_icon"] = icon_canon
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    console.print(f"[bold green]✔[/] Default icon set to: [cyan]{icon_canon}[/] (saved to {config_path})")


@app.command("set-default-color")
def set_default_color(color: str = typer.Argument(..., help="Color in rgba format")):
    """Set default color."""
    # Keep the old rgba(...) hint, but accept hex/rgb/etc and quantize to an official waypoint color.
    if not (color.startswith("#") or color.lower().startswith(("rgb", "rgba")) or re.fullmatch(r"[0-9a-fA-F]{6}", color or "")):
        console.print(f"[bold red]❌ Error:[/] Invalid color format")
        console.print("[dim]Expected rgba(r,g,b,a) or #RRGGBB or RRGGBB[/]")
        raise typer.Exit(1)

    OnX_color = ColorMapper.map_waypoint_color(color)

    config_path = Path("cairn_config.yaml")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data["default_color"] = OnX_color
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    console.print(f"[bold green]✔[/] Default color set to: [cyan]{OnX_color}[/] (saved to {config_path})")
