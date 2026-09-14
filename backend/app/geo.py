"""
"Geospatial" search, kept deliberately simple.

There's no Postgres/PostGIS (or any real DB) yet, so proximity search is
done in plain Python: compute the great-circle (Haversine) distance between
the shop's lat/lng and the query point, then filter/sort in memory. Swap
this for a real `ST_DWithin` / `ST_Distance` PostGIS query (or MongoDB's
`$geoNear`) once a real database is available — routers/shops.py only needs
a (shop, distance_km) pair per result, so nothing downstream has to change.
"""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_KM * c
