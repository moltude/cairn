"""
Canonical in-memory data model for Cairn.

This is the shared representation used to convert between:
- CalTopo GeoJSON exports/imports
- OnX Backcountry GPX exports/imports

The model is intentionally lossy only when a source format cannot represent
some fields. We preserve source-specific metadata in `Style` and `metadata`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, Union


GeometryType = Literal["Point", "LineString", "Polygon"]


@dataclass
class Style:
    """
    Shared styling/metadata container.

    - OnX fields are preserved even if the destination can't render them.
    - CalTopo fields represent fields we can express directly in CalTopo GeoJSON.
    """

    # OnX-specific
    OnX_icon: Optional[str] = None
    OnX_color_rgba: Optional[str] = None
    OnX_style: Optional[str] = None  # solid|dash|dot (tracks)
    OnX_weight: Optional[str] = None  # "4.0"|"6.0"|etc (tracks)
    OnX_id: Optional[str] = None  # OnX UUID when present

    # CalTopo-ish
    caltopo_marker_symbol: Optional[str] = None
    caltopo_marker_color: Optional[str] = None  # "#RRGGBB"
    caltopo_stroke: Optional[str] = None  # "#RRGGBB"
    caltopo_stroke_width: Optional[float] = None
    caltopo_pattern: Optional[str] = None  # "solid"|"dash"|"dot"|...

    # Extra, unstructured
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Folder:
    id: str
    name: str
    parent_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Waypoint:
    id: str
    folder_id: Optional[str]
    name: str
    lon: float
    lat: float
    notes: str = ""
    style: Style = field(default_factory=Style)
    source_ids: List[str] = field(default_factory=list)  # additional ids merged via dedup
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def geometry_type(self) -> GeometryType:
        return "Point"


TrackPoint = Tuple[float, float, Optional[float], Optional[int]]
"""
TrackPoint: (lon, lat, ele_m, epoch_ms)

We intentionally keep epoch time in ms when available because CalTopo’s exported GeoJSON
can embed `[lon, lat, ele, epoch_ms]` in coordinates arrays.
"""


@dataclass
class Track:
    id: str
    folder_id: Optional[str]
    name: str
    points: List[TrackPoint]
    notes: str = ""
    style: Style = field(default_factory=Style)
    source_ids: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def geometry_type(self) -> GeometryType:
        return "LineString"


PolygonRing = List[Tuple[float, float]]


@dataclass
class Shape:
    id: str
    folder_id: Optional[str]
    name: str
    rings: List[PolygonRing]
    notes: str = ""
    style: Style = field(default_factory=Style)
    source_ids: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def geometry_type(self) -> GeometryType:
        return "Polygon"


Item = Union[Waypoint, Track, Shape]


@dataclass
class MapDocument:
    """
    Canonical representation of a user map, with optional folder structure.
    """

    folders: List[Folder] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_folder(self, folder_id: str) -> Optional[Folder]:
        for f in self.folders:
            if f.id == folder_id:
                return f
        return None

    def ensure_folder(self, folder_id: str, name: str, parent_id: Optional[str] = None) -> Folder:
        existing = self.get_folder(folder_id)
        if existing is not None:
            return existing
        f = Folder(id=folder_id, name=name, parent_id=parent_id)
        self.folders.append(f)
        return f

    def add_item(self, item: Item) -> None:
        self.items.append(item)

    def waypoints(self) -> List[Waypoint]:
        return [i for i in self.items if isinstance(i, Waypoint)]

    def tracks(self) -> List[Track]:
        return [i for i in self.items if isinstance(i, Track)]

    def shapes(self) -> List[Shape]:
        return [i for i in self.items if isinstance(i, Shape)]
