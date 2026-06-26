"""
Geospatial helpers (§13.1 location privacy, §9.5 nearby discovery).

The production stack is PostgreSQL + PostGIS: ``location`` is a
``geography(Point, 4326)``, ``location_fuzzed`` is a jittered point with a GiST
index, and nearby queries use ``ST_DWithin`` / ``ST_Distance``. To keep this
scaffold runnable without GDAL/GEOS, the same semantics are implemented in pure
Python over lat/lng decimals:

* ``fuzz_point`` jitters the exact point by the configured fuzz radius so the
  stored "fuzzed" coordinate never pinpoints a home (±300–500 m).
* ``haversine_km`` is the great-circle distance used to filter/order by radius.
* ``distance_band`` rounds distance so the client can show a band, never a pin.

Swapping in PostGIS is a localized change in apps.listings — the API contract
(fuzzed point + banded distance, exact point withheld) does not change.
"""
import math
import random

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in kilometres between two WGS-84 points."""
    lat1, lng1, lat2, lng2 = map(float, (lat1, lng1, lat2, lng2))
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def fuzz_point(lat, lng, radius_m=400):
    """Return a point randomly displaced within ``radius_m`` metres of the input.

    Used once at write time to derive ``location_fuzzed`` from the exact point
    (§13.1). The exact point is kept private; only this jittered one is exposed.
    """
    lat, lng = float(lat), float(lng)
    # Random distance (sqrt for uniform area distribution) and bearing.
    distance = radius_m * math.sqrt(random.random())
    bearing = random.uniform(0, 2 * math.pi)
    dlat = (distance * math.cos(bearing)) / 111_320.0
    cos_lat = math.cos(math.radians(lat)) or 1e-6
    dlng = (distance * math.sin(bearing)) / (111_320.0 * cos_lat)
    return round(lat + dlat, 6), round(lng + dlng, 6)


def distance_band(distance_km):
    """Round distance so the UI shows a band, not a pinpoint (§9.5, §13.1)."""
    if distance_km < 1:
        return round(distance_km * 2) / 2  # nearest 0.5 km under 1 km
    if distance_km < 10:
        return round(distance_km)
    return round(distance_km / 5) * 5  # nearest 5 km beyond 10 km
