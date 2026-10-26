"""A name is required to export (owner decision N1, 2026-10-25).

bridge.export_zip refuses ("An item needs a name.") while an included item that
the writers would write has a blank name; the app first offers "Name them
Untitled", which stores "Untitled" as each such name through apply_edits. A
bridge-level test that exports a map with blank names (Bitterroots has 7: 6
lines and an area, all in Unorganized) does the same here before exporting.
"""
from __future__ import annotations

import json

UNTITLED = "Untitled"


def blank_uids(bridge) -> list[str]:
    """The items the app's "N items need a name" confirm counts: included, with
    coordinates, and a blank name as written (bridge._blank_name)."""
    return [i["uid"] for g in bridge._STATE["groups"] for i in g["items"]
            if i.get("included", True) and not i.get("no_coords") and bridge._blank_name(i.get("name"))]


def name_blanks(bridge, name: str = UNTITLED) -> list[str]:
    """Name every blank-named item `name`, as "Name them Untitled" does; their uids."""
    uids = blank_uids(bridge)
    if uids:
        bridge.apply_edits(json.dumps({u: {"name": name} for u in uids}))
    return uids


def export_named(bridge) -> bytes:
    """bridge.export_zip() after name_blanks: what the app's Export writes."""
    name_blanks(bridge)
    return bridge.export_zip()
