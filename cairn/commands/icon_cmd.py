"""Icon management commands for Cairn CLI."""

from typing import Optional
from pathlib import Path
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
import yaml

from cairn.core.config import get_all_OnX_icons, load_config, save_user_mapping, remove_user_mapping
from cairn.core.mapper import get_icon_emoji
from cairn.core.icon_registry import IconRegistry, default_mappings_path

app = typer.Typer(
    help=(
        "Manage icon mappings and inspect how Cairn transfers icons between CalTopo and OnX.\n\n"
        "Key commands:\n"
        "- show-mappings: human-friendly summary of repo mappings\n"
        "- validate-mappings: validate mapping file structure\n"
        "- map/unmap: map CalTopo symbol → OnX icon (local cairn_config.yaml)\n"
        "- map-onx-to-caltopo: map OnX icon → CalTopo symbol (repo icon_mappings.yaml)\n"
    )
)
console = Console()


def browse_all_icons() -> Optional[str]:
    """Show categorized list of all OnX icons for selection."""
    # Group icons by category
    categories = {
        "Camping": ["Camp", "Camp Area", "Camp Backcountry", "Campground", "Campsite"],
        "Water": ["Water Source", "Water Crossing", "Waterfall", "Hot Spring", "Geyser", "Rapids", "Wetland", "Potable Water"],
        "Winter": ["Ski", "XC Skiing", "Ski Touring", "Ski Areas", "Skin Track", "Snowboarder", "Snowmobile", "Snowpark", "Snow Pit"],
        "Vehicles": ["4x4", "ATV", "Bike", "Dirt Bike", "Overland", "Parking", "RV", "SUV", "Truck"],
        "Hiking": ["Backpacker", "Hike", "Mountaineer", "Trailhead"],
        "Climbing": ["Climbing", "Rappel", "Cave", "Caving"],
        "Terrain": ["Summit", "Cornice", "Couloir", "Slide Path", "Steep Trail", "Log Obstacle"],
        "Hazards": ["Hazard", "Barrier", "Road Barrier"],
        "Observation": ["View", "Photo", "Lookout", "Observation Towers", "Webcam", "Lighthouses"],
        "Facilities": ["Cabin", "Shelter", "House", "Fuel", "Food Source", "Food Storage", "Picnic Area", "Kennels", "Visitor Center", "Gear"],
        "Water Activities": ["Canoe", "Kayak", "Raft", "Swimming", "Windsurfing", "Hand Launch", "Put In", "Take Out", "Marina"],
        "Infrastructure": ["Gate", "Closed Gate", "Open Gate", "Footbridge", "Crossing", "Access Point"],
        "Wildlife": ["Eagle", "Fish", "Mushroom", "Wildflower", "Feeding Area", "Dog Sledding"],
        "Activities": ["Horseback", "Mountain Biking", "Foraging", "Surfing Area", "Hang Gliding"],
        "Misc": ["Location", "Emergency Phone", "Ruins", "Stock Tank", "Washout", "Sasquatch"],
    }

    # Display with rich Table
    table = Table(title="OnX Backcountry Icons", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="cyan", width=20)
    table.add_column("Icons", style="white")

    for category, icon_list in categories.items():
        # Get emojis for icons
        icons_with_emoji = [f"{get_icon_emoji(icon)} {icon}" for icon in icon_list]
        table.add_row(category, ", ".join(icons_with_emoji))

    console.print(table)

    try:
        icon_name = Prompt.ask("\nEnter icon name (or press Enter to skip)", default="")
        return icon_name if icon_name else None
    except (KeyboardInterrupt, EOFError):
        return None


@app.command("list")
def list_icons():
    """List all available OnX Backcountry icons."""
    browse_all_icons()


@app.command("map")
def map_symbol(
    symbol: str = typer.Argument(..., help="CalTopo symbol"),
    icon: str = typer.Argument(..., help="OnX icon name")
):
    """Map a CalTopo symbol to an OnX icon."""
    valid_icons = get_all_OnX_icons()
    if icon not in valid_icons:
        console.print(f"[red]✗[/] Invalid icon: {icon}")
        console.print("[dim]Run 'cairn icon list' to see all available icons[/]")
        raise typer.Exit(1)
    try:
        save_user_mapping(symbol, icon)
        emoji = get_icon_emoji(icon)
        console.print(f"[green]✓[/] Mapped '[cyan]{symbol}[/]' → {emoji} '[green]{icon}[/]'")
    except ValueError as e:
        console.print(f"[red]✗[/] {e}")
        raise typer.Exit(1)


@app.command("unmap")
def unmap_symbol(symbol: str = typer.Argument(..., help="CalTopo symbol")):
    """Remove a symbol mapping."""
    removed = remove_user_mapping(symbol)
    if removed:
        console.print(f"[green]✓[/] Removed mapping for '[cyan]{symbol}[/]'")
    else:
        console.print(f"[yellow]No user mapping found for '[cyan]{symbol}[/]'[/]")


@app.command("show")
def show_mapping(symbol: str = typer.Argument(..., help="CalTopo symbol")):
    """Show current mapping for a symbol."""
    cfg = load_config()
    mapping = cfg.symbol_map.get(symbol.lower())
    if mapping:
        emoji = get_icon_emoji(mapping)
        console.print(f"'[cyan]{symbol}[/]' → {emoji} '[green]{mapping}[/]'")
    else:
        console.print(f"[yellow]No mapping found for '[cyan]{symbol}[/]'[/]")
        console.print("[dim]Will use default 'Location' icon[/]")


def _validate_choice(value: str, *, allowed: set[str], label: str) -> str:
    v = (value or "").strip().lower()
    if v not in allowed:
        raise typer.BadParameter(f"Invalid {label}: {value!r}. Expected one of: {', '.join(sorted(allowed))}")
    return v


def _direction_to_title(direction: str) -> str:
    if direction == "caltopo-to-onx":
        return "CalTopo → OnX"
    if direction == "onx-to-caltopo":
        return "OnX → CalTopo"
    return "Both directions"


def _print_legend() -> None:
    console.print("\n[bold]Legend[/]")
    console.print("- [bold]Incoming label[/]: what we see in the exported data")
    console.print("- [bold]Mapped to[/]: what Cairn will write into the destination format")
    console.print("- [bold]Why[/]: which rule set is used (symbol_map/keyword_map/direct/default)")


def _table_sample_rows(mapping: dict, *, limit: int, full: bool) -> list[tuple[str, str]]:
    items = sorted(((str(k), str(v)) for k, v in mapping.items()), key=lambda kv: kv[0].lower())
    if full:
        return items
    return items[: max(0, limit)]


def _print_caltopo_to_onx_tables(reg: IconRegistry, *, full: bool, limit: int) -> None:
    console.print("\n[bold]CalTopo → OnX[/] ([dim]CalTopo marker-symbol → OnX waypoint icon[/])")
    console.print(f"- Default OnX icon: [cyan]{reg.caltopo_default_icon}[/]")
    console.print(f"- Generic symbols (treated as no explicit icon): [dim]{', '.join(reg.caltopo_generic_symbols)}[/]")
    console.print(f"- symbol_map entries: [cyan]{len(reg.caltopo_symbol_map)}[/]")
    console.print(f"- keyword_map entries: [cyan]{len(reg.caltopo_keyword_map)}[/]")

    # Build an icon-centric view so the flow is obvious:
    # If CalTopo marker-symbol is one of the symbols -> that OnX icon.
    # Else if waypoint title/description matches keywords -> that OnX icon.
    icon_to_symbols: dict[str, list[str]] = {}
    for sym, icon in reg.caltopo_symbol_map.items():
        icon_to_symbols.setdefault(icon, []).append(sym)
    for icon, syms in icon_to_symbols.items():
        syms.sort(key=lambda s: s.lower())

    all_icons = sorted(
        set(icon_to_symbols.keys()) | set(reg.caltopo_keyword_map.keys()),
        key=lambda s: s.lower(),
    )

    rows: list[tuple[str, str, str]] = []
    for icon in all_icons:
        syms = icon_to_symbols.get(icon, [])
        kws = reg.caltopo_keyword_map.get(icon, []) or []
        syms_cell = ", ".join(syms) if syms else ""
        kws_cell = ", ".join(kws) if kws else ""
        rows.append((icon, syms_cell, kws_cell))

    if not full:
        rows = rows[: max(0, limit)]

    console.print(f"\n[bold]Sample[/]: CalTopo→OnX rules by target OnX icon (alphabetical){' (full)' if full else ''}")
    t = Table(show_header=True, header_style="bold cyan")
    t.add_column("Target OnX icon", style="green", no_wrap=True)
    t.add_column("If CalTopo marker-symbol is…", style="cyan")
    t.add_column("Else if name/notes contains…", style="white")
    for icon, syms_cell, kws_cell in rows:
        t.add_row(icon, syms_cell, kws_cell)
    console.print(t)
    if not full and len(all_icons) > limit:
        console.print(f"[dim]Showing first {limit} rows. Use --full to show all.[/]")


def _print_onx_to_caltopo_tables(reg: IconRegistry, *, full: bool, limit: int) -> None:
    console.print("\n[bold]OnX → CalTopo[/] ([dim]OnX waypoint icon → CalTopo marker-symbol[/])")
    console.print(f"- Default CalTopo symbol: [cyan]{reg.onx_default_symbol}[/]")
    console.print(f"- icon_map entries: [cyan]{len(reg.onx_icon_map)}[/]")

    console.print(f"\n[bold]Sample[/]: OnX→CalTopo icon_map (alphabetical){' (full)' if full else ''}")
    t = Table(show_header=True, header_style="bold cyan")
    t.add_column("Incoming OnX icon", style="cyan", no_wrap=True)
    t.add_column("Mapped to CalTopo symbol", style="green")
    t.add_column("Rule", style="white", no_wrap=True)
    for k, v in _table_sample_rows(reg.onx_icon_map, limit=limit, full=full):
        t.add_row(k, v, "direct")
    console.print(t)
    if not full and len(reg.onx_icon_map) > limit:
        console.print(f"[dim]Showing first {limit} rows. Use --full to show all.[/]")


def _emit_yaml(reg: IconRegistry, direction: str) -> None:
    # Emit a direction-scoped YAML structure (comments stripped).
    out: dict = {"version": 1, "policies": dict(reg.policies)}
    if direction in ("both", "caltopo-to-onx"):
        out["caltopo_to_onx"] = {
            "default_icon": reg.caltopo_default_icon,
            "generic_symbols": list(reg.caltopo_generic_symbols),
            "symbol_map": dict(reg.caltopo_symbol_map),
            "keyword_map": dict(reg.caltopo_keyword_map),
        }
    if direction in ("both", "onx-to-caltopo"):
        out["onx_to_caltopo"] = {
            "default_symbol": reg.onx_default_symbol,
            "icon_map": dict(reg.onx_icon_map),
        }
    console.print(yaml.dump(out, sort_keys=False, allow_unicode=True))


def _emit_json(reg: IconRegistry, direction: str) -> None:
    out: dict = {"version": 1, "policies": dict(reg.policies)}
    if direction in ("both", "caltopo-to-onx"):
        out["caltopo_to_onx"] = {
            "default_icon": reg.caltopo_default_icon,
            "generic_symbols": list(reg.caltopo_generic_symbols),
            "symbol_map": dict(reg.caltopo_symbol_map),
            "keyword_map": dict(reg.caltopo_keyword_map),
        }
    if direction in ("both", "onx-to-caltopo"):
        out["onx_to_caltopo"] = {
            "default_symbol": reg.onx_default_symbol,
            "icon_map": dict(reg.onx_icon_map),
        }
    console.print(json.dumps(out, indent=2, ensure_ascii=False))


def _emit_markdown(reg: IconRegistry, direction: str, *, full: bool, limit: int) -> None:
    lines: list[str] = []
    lines.append("## Icon mappings summary")
    lines.append("")
    lines.append(f"- Mappings file: `{reg.mappings_path}`")
    lines.append(f"- Catalog file: `{reg.catalog_path}`")
    lines.append(f"- Policy: `unknown_icon_handling={reg.policies.get('unknown_icon_handling')}`")
    lines.append("")

    if direction in ("both", "caltopo-to-onx"):
        lines.append("### CalTopo → OnX")
        lines.append("")
        lines.append(f"- Default icon: `{reg.caltopo_default_icon}`")
        lines.append(f"- Generic symbols: `{', '.join(reg.caltopo_generic_symbols)}`")
        lines.append(f"- symbol_map entries: {len(reg.caltopo_symbol_map)}")
        lines.append(f"- keyword_map entries: {len(reg.caltopo_keyword_map)}")
        lines.append("")
        # Icon-centric sample: one row per target icon, showing both symbol and keyword triggers.
        icon_to_symbols: dict[str, list[str]] = {}
        for sym, icon in reg.caltopo_symbol_map.items():
            icon_to_symbols.setdefault(icon, []).append(sym)
        for icon, syms in icon_to_symbols.items():
            syms.sort(key=lambda s: s.lower())

        all_icons = sorted(
            set(icon_to_symbols.keys()) | set(reg.caltopo_keyword_map.keys()),
            key=lambda s: s.lower(),
        )
        if not full:
            all_icons = all_icons[: max(0, limit)]

        lines.append("#### Sample: rules by target OnX icon")
        lines.append("")
        lines.append("| Target OnX icon | If CalTopo marker-symbol is… | Else if name/notes contains… |")
        lines.append("|---|---|---|")
        for icon in all_icons:
            syms = ", ".join(icon_to_symbols.get(icon, []) or [])
            kws = ", ".join(reg.caltopo_keyword_map.get(icon, []) or [])
            lines.append(f"| `{icon}` | {syms} | {kws} |")
        lines.append("")

    if direction in ("both", "onx-to-caltopo"):
        lines.append("### OnX → CalTopo")
        lines.append("")
        lines.append(f"- Default symbol: `{reg.onx_default_symbol}`")
        lines.append(f"- icon_map entries: {len(reg.onx_icon_map)}")
        lines.append("")
        sample = _table_sample_rows(reg.onx_icon_map, limit=limit, full=full)
        lines.append("#### Sample: icon_map")
        lines.append("")
        lines.append("| Incoming OnX icon | Mapped to CalTopo symbol | Rule |")
        lines.append("|---|---|---|")
        for k, v in sample:
            lines.append(f"| `{k}` | `{v}` | `direct` |")
        lines.append("")

    console.print("\n".join(lines).rstrip() + "\n")


@app.command("show-mappings")
def show_mappings(
    mappings_path: Optional[Path] = typer.Option(
        None,
        "--mappings",
        help="Path to icon_mappings.yaml (default: repo cairn/data/icon_mappings.yaml)",
    ),
    direction: str = typer.Option(
        "both",
        "--direction",
        help="Which direction to display: caltopo-to-onx, onx-to-caltopo, or both.",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format: table (pretty), yaml, json, or markdown.",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Print full tables instead of a small sample.",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        min=0,
        help="Sample size for table/markdown output (ignored with --full).",
    ),
):
    """
    Show/summarize the repo-backed icon mappings.

    Default behavior (no flags):
    - Shows BOTH directions
    - Prints a short summary + a small alphabetical sample of each mapping table
    - Uses pretty Rich tables for readability

    Examples:
      cairn icon show-mappings
      cairn icon show-mappings --direction onx-to-caltopo --full
      cairn icon show-mappings --format markdown --direction caltopo-to-onx
    """
    dir_norm = _validate_choice(direction, allowed={"both", "caltopo-to-onx", "onx-to-caltopo"}, label="direction")
    fmt_norm = _validate_choice(format, allowed={"table", "yaml", "json", "markdown"}, label="format")

    reg = IconRegistry(mappings_path=mappings_path)

    if fmt_norm == "table":
        console.print("\n[bold]Icon mapping configuration[/] ([dim]how icons transfer between apps[/])")
        console.print(f"- Source file:  [cyan]{reg.mappings_path}[/]")
        console.print(f"- Catalog file: [cyan]{reg.catalog_path}[/] [dim](auto-updated by migrations)[/]")
        console.print(f"- Policy (unmapped OnX icons): [cyan]{reg.policies.get('unknown_icon_handling')}[/]")
        console.print(f"- Direction: [cyan]{_direction_to_title(dir_norm)}[/]")
        _print_legend()

        if dir_norm in ("both", "caltopo-to-onx"):
            _print_caltopo_to_onx_tables(reg, full=full, limit=limit)
        if dir_norm in ("both", "onx-to-caltopo"):
            _print_onx_to_caltopo_tables(reg, full=full, limit=limit)

        console.print("\n[dim]Tip: use --full for complete tables, or --format yaml|json|markdown for machine/copy-friendly output.[/]")
        return

    if fmt_norm == "yaml":
        _emit_yaml(reg, dir_norm)
        return
    if fmt_norm == "json":
        _emit_json(reg, dir_norm)
        return
    if fmt_norm == "markdown":
        _emit_markdown(reg, dir_norm, full=full, limit=limit)
        return


@app.command("validate-mappings")
def validate_mappings(
    mappings_path: Optional[Path] = typer.Option(
        None,
        "--mappings",
        help="Path to icon_mappings.yaml (defaults to cairn/data/icon_mappings.yaml)",
    )
):
    """Validate the repo-versioned CalTopo↔OnX mapping file."""
    try:
        reg = IconRegistry(mappings_path=mappings_path)
        console.print(f"[bold green]✔[/] Valid mappings: [underline]{reg.mappings_path}[/]")
        console.print(f"  CalTopo→OnX symbol_map: [cyan]{len(reg.caltopo_symbol_map)}[/]")
        console.print(f"  CalTopo→OnX keyword_map: [cyan]{len(reg.caltopo_keyword_map)}[/]")
        console.print(f"  OnX→CalTopo icon_map: [cyan]{len(reg.onx_icon_map)}[/]")
        console.print(f"  Policy unknown_icon_handling: [cyan]{reg.policies.get('unknown_icon_handling')}[/]")
    except Exception as e:
        console.print(f"[bold red]❌ Invalid mappings:[/] {e}")
        raise typer.Exit(1)


@app.command("map-onx-to-caltopo")
def map_onx_to_caltopo(
    onx_icon: str = typer.Argument(..., help="OnX icon name (case-sensitive, e.g. 'Water Source')"),
    caltopo_symbol: str = typer.Argument(..., help="CalTopo marker-symbol (e.g. 'camping')"),
    mappings_path: Optional[Path] = typer.Option(
        None,
        "--mappings",
        help="Path to icon_mappings.yaml (defaults to cairn/data/icon_mappings.yaml)",
    ),
):
    """
    Add/update an OnX icon → CalTopo symbol mapping in the repo mapping file.

    This is an explicit command (no automatic mapping).
    """
    onx_icon = (onx_icon or "").strip()
    caltopo_symbol = (caltopo_symbol or "").strip().lower()
    if not onx_icon:
        raise typer.BadParameter("onx_icon must be non-empty")
    if not caltopo_symbol:
        raise typer.BadParameter("caltopo_symbol must be non-empty")

    path = (mappings_path or default_mappings_path()).resolve()
    if not path.exists():
        console.print(f"[bold red]❌ Error:[/] Mappings file not found: {path}")
        raise typer.Exit(1)

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        console.print(f"[bold red]❌ Error:[/] Invalid YAML (expected mapping at top level): {path}")
        raise typer.Exit(1)

    data.setdefault("version", 1)
    data.setdefault("onx_to_caltopo", {})
    if not isinstance(data["onx_to_caltopo"], dict):
        console.print(f"[bold red]❌ Error:[/] Invalid YAML: onx_to_caltopo must be a mapping")
        raise typer.Exit(1)
    o2c = data["onx_to_caltopo"]
    o2c.setdefault("default_symbol", "point")
    o2c.setdefault("icon_map", {})
    if not isinstance(o2c["icon_map"], dict):
        console.print(f"[bold red]❌ Error:[/] Invalid YAML: onx_to_caltopo.icon_map must be a mapping")
        raise typer.Exit(1)

    prev = o2c["icon_map"].get(onx_icon)
    o2c["icon_map"][onx_icon] = caltopo_symbol
    path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    if prev:
        console.print(f"[green]✓[/] Updated OnX→CalTopo mapping: '{onx_icon}' → '{caltopo_symbol}' (was '{prev}')")
    else:
        console.print(f"[green]✓[/] Added OnX→CalTopo mapping: '{onx_icon}' → '{caltopo_symbol}'")


@app.command("unmap-onx-to-caltopo")
def unmap_onx_to_caltopo(
    onx_icon: str = typer.Argument(..., help="OnX icon name (case-sensitive)"),
    mappings_path: Optional[Path] = typer.Option(
        None,
        "--mappings",
        help="Path to icon_mappings.yaml (defaults to cairn/data/icon_mappings.yaml)",
    ),
):
    """Remove an OnX icon → CalTopo symbol mapping from the repo mapping file."""
    onx_icon = (onx_icon or "").strip()
    if not onx_icon:
        raise typer.BadParameter("onx_icon must be non-empty")

    path = (mappings_path or default_mappings_path()).resolve()
    if not path.exists():
        console.print(f"[bold red]❌ Error:[/] Mappings file not found: {path}")
        raise typer.Exit(1)

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        console.print(f"[bold red]❌ Error:[/] Invalid YAML (expected mapping at top level): {path}")
        raise typer.Exit(1)

    o2c = data.get("onx_to_caltopo") or {}
    icon_map = o2c.get("icon_map") or {}
    if not isinstance(icon_map, dict):
        console.print(f"[bold red]❌ Error:[/] Invalid YAML: onx_to_caltopo.icon_map must be a mapping")
        raise typer.Exit(1)

    if onx_icon not in icon_map:
        console.print(f"[yellow]No mapping found for OnX icon '{onx_icon}'[/]")
        raise typer.Exit(0)

    prev = icon_map.pop(onx_icon)
    o2c["icon_map"] = icon_map
    data["onx_to_caltopo"] = o2c
    path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    console.print(f"[green]✓[/] Removed OnX→CalTopo mapping: '{onx_icon}' (was '{prev}')")
