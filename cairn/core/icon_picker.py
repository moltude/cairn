"""
Interactive helpers for selecting OnX icons (used by preview/edit flows).

This is intentionally not part of the CLI surface area; it is used by interactive
flows that need an icon picker.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from cairn.core.config import normalize_onx_icon_name


console = Console()


def browse_all_icons() -> Optional[str]:
    """Show categorized list of all OnX icons for selection."""
    # Group icons by category
    categories = {
        "Camping": ["Camp", "Camp Area", "Camp Backcountry", "Campground", "Campsite"],
        "Water": [
            "Water Source",
            "Water Crossing",
            "Waterfall",
            "Hot Spring",
            "Geyser",
            "Rapids",
            "Wetland",
            "Potable Water",
        ],
        "Winter": [
            "Ski",
            "XC Skiing",
            "Ski Touring",
            "Ski Areas",
            "Skin Track",
            "Snowboarder",
            "Snowmobile",
            "Snowpark",
            "Snow Pit",
        ],
        "Vehicles": [
            "4x4",
            "ATV",
            "Bike",
            "Dirt Bike",
            "Overland",
            "Parking",
            "RV",
            "SUV",
            "Truck",
        ],
        "Hiking": ["Backpacker", "Hike", "Mountaineer", "Trailhead"],
        "Climbing": ["Climbing", "Rappel", "Cave", "Caving"],
        "Terrain": [
            "Summit",
            "Cornice",
            "Couloir",
            "Slide Path",
            "Steep Trail",
            "Log Obstacle",
        ],
        "Hazards": ["Hazard", "Barrier", "Road Barrier"],
        "Observation": [
            "View",
            "Photo",
            "Lookout",
            "Observation Towers",
            "Webcam",
            "Lighthouses",
        ],
        "Facilities": [
            "Cabin",
            "Shelter",
            "House",
            "Fuel",
            "Food Source",
            "Food Storage",
            "Picnic Area",
            "Kennels",
            "Visitor Center",
            "Gear",
        ],
        "Water Activities": [
            "Canoe",
            "Kayak",
            "Raft",
            "Swimming",
            "Windsurfing",
            "Hand Launch",
            "Put In",
            "Take Out",
            "Marina",
        ],
        "Infrastructure": [
            "Gate",
            "Closed Gate",
            "Open Gate",
            "Footbridge",
            "Crossing",
            "Access Point",
        ],
        "Wildlife": [
            "Eagle",
            "Fish",
            "Mushroom",
            "Wildflower",
            "Feeding Area",
            "Dog Sledding",
        ],
        "Activities": [
            "Horseback",
            "Mountain Biking",
            "Foraging",
            "Surfing Area",
            "Hang Gliding",
        ],
        "Misc": [
            "Location",
            "Emergency Phone",
            "Ruins",
            "Stock Tank",
            "Washout",
            "Sasquatch",
        ],
    }

    table = Table(
        title="OnX Backcountry Icons", show_header=True, header_style="bold cyan"
    )
    table.add_column("Category", style="cyan", width=20)
    table.add_column("Icons", style="white")

    for category, icon_list in categories.items():
        # Text-only list (emoji are not part of OnX and add clutter in the picker).
        table.add_row(category, ", ".join(icon_list))

    console.print(table)

    while True:
        try:
            icon_name = Prompt.ask(
                "\nEnter icon name (or press Enter to cancel)", default=""
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if not icon_name:
            return None
        canon = normalize_onx_icon_name(icon_name)
        if canon is not None:
            return canon
        console.print(
            f"[red]Invalid icon:[/] {icon_name} [dim](try again, or press Enter to cancel)[/]"
        )
