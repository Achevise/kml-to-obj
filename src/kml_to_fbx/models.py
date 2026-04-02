from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


LonLatAlt = Tuple[float, float, float]
RGBAlpha = Tuple[float, float, float, float]


@dataclass
class StyleDef:
    rgba: RGBAlpha


@dataclass
class Shape:
    name: str
    hierarchy: List[str]
    geometry_type: str
    # point: [coord], linestring: [coord], polygon: [[ring_coords], ...]
    coordinates: object
    rgba: RGBAlpha
    material_source: str = ""


@dataclass
class SceneData:
    shapes: List[Shape]
    origin_lon: float
    origin_lat: float
