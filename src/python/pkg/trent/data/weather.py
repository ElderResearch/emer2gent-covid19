#!/usr/bin/env python3
import io
from typing import NamedTuple, Union

import numpy as np
import pandas as pd
import requests

# ------- Constants ------- #
# Equitorial radius of earth.
# Source: https://en.wikipedia.org/wiki/Earth_radius#Equatorial_radius
EARTH_RADIUS: float = 6378.137


class BoundingBox(NamedTuple):
    minlat: float
    maxlat: float
    minlon: float
    maxlon: float


def get_icao_data() -> pd.DataFrame:
    """
    Download ICAO data from OpenFlights Github repository.
    Data dictionary: https://openflights.org/data.html
    """
    url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
    columns = [
        "id",
        "name",
        "city",
        "country",
        "iata",
        "icao",
        "latitude",
        "longitude",
        "altitude",
        "timezone",
        "dst",
        "dbtz",
        "type",
        "source",
    ]
    dtypes = [
        int,
        str,
        str,
        str,
        str,
        str,
        float,
        float,
        int,
        float,
        str,
        str,
        str,
        str,
    ]
    r = requests.get(url)
    if r.ok:
        return pd.read_csv(
            io.StringIO(r.content.decode(r.encoding)),
            names=columns,
            dtype=dict(zip(columns, dtypes)),
            na_values="\\N",
        )
    else:
        r.raise_for_status()


def degree2radian(d: Union[int, float]) -> float:
    """Convert degrees to radians"""
    return d * np.pi / 180


def radian2degree(r: Union[int, float]) -> float:
    """Convert radians to degrees"""
    return r * 180 / np.pi


def dist_btwn_points(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great circle distance (km) between two lat/lon decimal degree pairs"""
    global EARTH_RADIUS

    lat1 = degree2radian(lat1)
    lon1 = degree2radian(lon1)
    lat2 = degree2radian(lat2)
    lon2 = degree2radian(lon2)

    return EARTH_RADIUS * np.arccos(
        np.sin(lat1) * np.sin(lat2) + np.cos(lat1) * np.cos(lat2) * np.cos(lon1 - lon2)
    )


def bounding_box(lat: float, lon: float, radius: Union[int, float]) -> BoundingBox:
    """
    Compute bounding box from lat/lon decimal degree point and radius.
    Bounding box is composed of minimum latitude, maximum latitude, minumum longitude,
    and maximum longitude.
    """
    global EARTH_RADIUS

    global_min_lat = -np.pi / 2
    global_max_lat = np.pi / 2
    global_min_lon = -np.pi
    global_max_lon = np.pi

    lat = degree2radian(lat)
    lon = degree2radian(lon)

    # compute angular distance in radians
    angular_dist = radius / EARTH_RADIUS

    min_lat = lat - angular_dist
    max_lat = lat + angular_dist

    if min_lat > global_min_lat & max_lat < global_max_lat:
        delta_lon = np.arcsin(np.sin(angular_dist) / np.cos(lat))
        min_lon = lon - delta_lon
        max_lon = lon + delta_lon

        if min_lon < global_min_lon:
            min_lon = min_lon + 2 * np.pi

        if max_lon > global_max_lon:
            max_lon = max_lon - 2 * np.pi

    else:  # a pole is within the search radius
        min_lat = max(min_lat, global_min_lat)
        max_lat = min(max_lat, global_max_lat)
        min_lon = global_min_lon
        max_lon = global_max_lon

    return BoundingBox(minlat=min_lat, maxlat=max_lat, minlon=min_lon, maxlon=max_lon)
