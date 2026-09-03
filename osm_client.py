"""Thin client for Nominatim (geocoding) and Overpass (venue search).

Be a good citizen of the free OSM infrastructure:
- always send a descriptive User-Agent (required by Nominatim usage policy);
- avoid sending repeated identical requests while testing;
- keep request volume modest (this app only queries on demand).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# The free public Overpass instances are shared, volunteer-run infrastructure
# and regularly return 504/502 under load. Try a short list of known public
# mirrors in order and fall back to the next one on server errors/timeouts.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

# Required by OSM usage policy: identify your application and give a way
# to contact you. Update the contact info if you plan to use this beyond
# this assignment.
HEADERS = {
    "User-Agent": "horeca-competition-lens/0.1 (student assignment @ The Hague University; contact: srlamalkin@gmail.com)"
}

# category -> Overpass tag filter (key=value)
CATEGORY_TAGS = {
    "cafe": '"amenity"="cafe"',
    "restaurant": '"amenity"="restaurant"',
    "hotel": '"tourism"="hotel"',
}


class GeocodeError(RuntimeError):
    pass


@dataclass
class Place:
    name: str
    place_type: str
    website: Optional[str]
    lat: float
    lon: float
    distance_m: float


def geocode(address: str) -> tuple[float, float]:
    """Look up an address via Nominatim. Returns (lat, lon)."""
    params = {"q": address, "format": "json", "limit": 1}
    resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise GeocodeError(f"No location found for address: {address!r}")
    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])
    return lat, lon


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line ('as the crow flies') distance in metres."""
    r = 6371000  # Earth radius in metres
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


class OverpassError(RuntimeError):
    pass


def _query_overpass_with_fallback(query: str) -> list[dict]:
    """POST the Overpass QL query, trying each mirror in turn.

    Retries a mirror once after a short backoff on 502/503/504 before
    moving on to the next mirror. Raises OverpassError only if every
    mirror fails.
    """
    last_error: Optional[Exception] = None

    for url in OVERPASS_URLS:
        for attempt in (1, 2):
            try:
                resp = requests.post(
                    url, data={"data": query}, headers=HEADERS, timeout=30
                )
                if resp.status_code in (502, 503, 504):
                    last_error = requests.exceptions.HTTPError(
                        f"{resp.status_code} from {url}"
                    )
                    time.sleep(2 * attempt)  # brief backoff, then retry/move on
                    continue
                resp.raise_for_status()
                return resp.json().get("elements", [])
            except requests.exceptions.RequestException as exc:
                last_error = exc
                time.sleep(2 * attempt)
                continue
        # exhausted retries on this mirror, try the next one

    raise OverpassError(
        "All Overpass endpoints failed (public servers may be overloaded). "
        f"Last error: {last_error}"
    )


def find_establishments(
    lat: float, lon: float, category: str, radius_m: int = 1000
) -> list[Place]:
    """Query Overpass for a category within radius_m of (lat, lon)."""
    if category not in CATEGORY_TAGS:
        raise ValueError(f"Unknown category: {category!r}")

    tag_filter = CATEGORY_TAGS[category]
    query = f"""
    [out:json][timeout:25];
    (
      node[{tag_filter}](around:{radius_m},{lat},{lon});
      way[{tag_filter}](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """

    elements = _query_overpass_with_fallback(query)

    places: list[Place] = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "Unnamed")
        website = tags.get("website") or tags.get("contact:website")

        if el["type"] == "node":
            el_lat, el_lon = el["lat"], el["lon"]
        else:  # way / relation -> Overpass gives a computed center
            center = el.get("center")
            if not center:
                continue
            el_lat, el_lon = center["lat"], center["lon"]

        dist = haversine_m(lat, lon, el_lat, el_lon)
        places.append(
            Place(
                name=name,
                place_type=category,
                website=website,
                lat=el_lat,
                lon=el_lon,
                distance_m=dist,
            )
        )

    places.sort(key=lambda p: p.distance_m)
    return places


def polite_pause(seconds: float = 1.0) -> None:
    """Small delay helper if you loop over multiple test addresses."""
    time.sleep(seconds)
