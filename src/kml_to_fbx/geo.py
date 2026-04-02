from __future__ import annotations

import math
from typing import Tuple


def lonlatalt_to_local_meters(
    lon: float,
    lat: float,
    alt: float,
    origin_lon: float,
    origin_lat: float,
) -> Tuple[float, float, float]:
    # Equirectangular local tangent approximation.
    # FBX scene is Y-up, so we map:
    #   X = east-west, Y = altitude, Z = north-south
    earth_radius = 6378137.0
    dlon = math.radians(lon - origin_lon)
    dlat = math.radians(lat - origin_lat)
    mean_lat = math.radians((lat + origin_lat) * 0.5)

    x = earth_radius * dlon * math.cos(mean_lat)
    y = alt
    z = earth_radius * dlat
    return (x, y, z)
