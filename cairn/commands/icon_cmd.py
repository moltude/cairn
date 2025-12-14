"""Icon management commands for Cairn CLI."""

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from cairn.core.config import get_all_onx_icons, load_config, save_user_mapping, remove_user_mapping
from cairn.core.mapper import get_icon_emoji

app = typer.Typer()
console = Console()


def browse_all_icons() -> Optional[str]:
    """Show categorized list of all onX icons for selection."""
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
    table = Table(title="onX Backcountry Icons", show_header=True, header_style="bold cyan")
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
    """List all available onX Backcountry icons."""
    browse_all_icons()


@app.command("map")
def map_symbol(
    symbol: str = typer.Argument(..., help="CalTopo symbol"),
    icon: str = typer.Argument(..., help="onX icon name")
):
    """Map a CalTopo symbol to an onX icon."""
    valid_icons = get_all_onx_icons()
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
