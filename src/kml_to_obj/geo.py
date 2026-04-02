from __future__ import annotations

import math
from typing import Tuple


def lonlatalt_to_local_meters(
    lon: float,
    lat: float,
    alt: float,
    origin_lon: float,
    origin_lat: float,
    up_axis: str = "z",
) -> Tuple[float, float, float]:
    # Equirectangular local tangent approximation in local ENU meters.
    earth_radius = 6378137.0
    dlon = math.radians(lon - origin_lon)
    dlat = math.radians(lat - origin_lat)
    mean_lat = math.radians((lat + origin_lat) * 0.5)

    east = earth_radius * dlon * math.cos(mean_lat)
    north = earth_radius * dlat
    up = alt

    axis = up_axis.lower()
    if axis == "z":
        # X=east, Y=north, Z=up
        return (east, north, up)
    if axis == "y":
        # X=east, Y=up, Z=north
        return (east, up, north)
    if axis == "x":
        # X=up, Y=east, Z=north
        return (up, east, north)
    raise ValueError(f"Unsupported up axis: {up_axis}")
