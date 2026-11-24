"""
Routing and Geocoding Service for TripWise.
Calculates road distance and travel time using OSRM / Google Routes API with reliable Haversine fallbacks.
"""

from __future__ import annotations
import math
import os
import requests

_geocode_cache: dict[str, tuple[float, float] | None] = {}
_route_cache: dict[str, dict | None] = {}

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight line distance on Earth in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


KNOWN_COORDINATES = {
    "visakhapatnam": (17.6868, 83.2185),
    "vizag": (17.6868, 83.2185),
    "goa": (15.2993, 74.1240),
    "hyderabad": (17.3850, 78.4867),
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "jaipur": (26.9124, 75.7873),
    "agra": (27.1767, 78.0081),
    "kochi": (9.9312, 76.2673),
    "varanasi": (25.3176, 82.9739),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "paris": (48.8566, 2.3522),
    "tokyo": (35.6762, 139.6503),
    "bali": (-8.4095, 115.1889),
    "new york": (40.7128, -74.0060),
    "london": (51.5074, -0.1278),
    "dubai": (25.2048, 55.2708),
    "singapore": (1.3521, 103.8198),
    "rome": (41.9028, 12.4964),
    "bangkok": (13.7563, 100.5018)
}


def geocode_place(name: str, context: str = "") -> tuple[float, float] | None:
    """Geocode a place name into (lat, lon)."""
    query = f"{name}, {context}".strip(" ,").lower()
    if not query:
        return None

    # Check known cities
    for k, v in KNOWN_COORDINATES.items():
        if k in query:
            return v

    if query in _geocode_cache:
        return _geocode_cache[query]

    # 1. Try Google Geocoding if key is present
    if GOOGLE_MAPS_API_KEY:
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            resp = requests.get(url, params={"address": query, "key": GOOGLE_MAPS_API_KEY}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "OK" and data.get("results"):
                    loc = data["results"][0]["geometry"]["location"]
                    coords = (float(loc["lat"]), float(loc["lng"]))
                    _geocode_cache[query.lower()] = coords
                    return coords
        except Exception:
            pass

    # 2. Try Nominatim (OpenStreetMap)
    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "TripWiseTravelApp/2.0 (student-project)"}
        resp = requests.get(url, params={"q": query, "format": "json", "limit": 1}, headers=headers, timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                coords = (float(data[0]["lat"]), float(data[0]["lon"]))
                _geocode_cache[query.lower()] = coords
                return coords
    except Exception:
        pass

    _geocode_cache[query.lower()] = None
    return None


def calculate_route(
    start_coords: tuple[float, float],
    end_coords: tuple[float, float],
    mode: str = "driving"
) -> dict:
    """
    Calculate route distance and travel duration between two coordinates.
    Returns:
    {
        "distance_km": float,
        "duration_minutes": int,
        "duration_formatted": str,
        "mode": str,
        "is_estimate": bool,
        "provider": str
    }
    """
    lat1, lon1 = start_coords
    lat2, lon2 = end_coords
    cache_key = f"{lat1:.4f},{lon1:.4f}->{lat2:.4f},{lon2:.4f}:{mode}"

    if cache_key in _route_cache and _route_cache[cache_key]:
        return _route_cache[cache_key]

    # Specialized Marine & Waterway routing for boats and passenger ferries
    if mode in ("boat", "ferry"):
        crow_km = haversine_distance(lat1, lon1, lat2, lon2)
        marine_multiplier = 1.15
        dist_km = max(1.5, round(crow_km * marine_multiplier, 1))
        if mode == "ferry":
            speed_kmh = 24.0
            boarding_buffer = 20
            provider = "Marine passenger ferry route (waterway channel)"
        else:
            speed_kmh = 28.0
            boarding_buffer = 15
            provider = "Coastal boat / long-tail boat transfer"

        duration_mins = max(15, round((dist_km / speed_kmh) * 60) + boarding_buffer)
        res = {
            "distance_km": dist_km,
            "duration_minutes": duration_mins,
            "duration_formatted": format_duration(duration_mins),
            "mode": mode,
            "is_estimate": True,
            "provider": provider
        }
        _route_cache[cache_key] = res
        return res

    # 1. Try Google Directions API if key configured
    if GOOGLE_MAPS_API_KEY:
        try:
            url = "https://maps.googleapis.com/maps/api/directions/json"
            gmode = "walking" if mode == "walking" else "driving"
            params = {
                "origin": f"{lat1},{lon1}",
                "destination": f"{lat2},{lon2}",
                "mode": gmode,
                "key": GOOGLE_MAPS_API_KEY
            }
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "OK" and data.get("routes"):
                    leg = data["routes"][0]["legs"][0]
                    dist_km = round(leg["distance"]["value"] / 1000.0, 1)
                    duration_mins = max(1, round(leg["duration"]["value"] / 60.0))
                    res = {
                        "distance_km": dist_km,
                        "duration_minutes": duration_mins,
                        "duration_formatted": format_duration(duration_mins),
                        "mode": mode,
                        "is_estimate": False,
                        "provider": "Google Maps Directions API"
                    }
                    _route_cache[cache_key] = res
                    return res
        except Exception:
            pass

    # 2. Try OSRM (Open Source Routing Machine) free public API
    try:
        osrm_profile = "foot" if mode == "walking" else "driving"
        url = f"https://router.project-osrm.org/route/v1/{osrm_profile}/{lon1},{lat1};{lon2},{lat2}?overview=false"
        resp = requests.get(url, timeout=1.5, headers={"User-Agent": "TripWiseTravelApp/2.0"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "Ok" and data.get("routes"):
                r = data["routes"][0]
                dist_km = round(r["distance"] / 1000.0, 1)
                duration_mins = max(1, round(r["duration"] / 60.0))
                res = {
                    "distance_km": dist_km,
                    "duration_minutes": duration_mins,
                    "duration_formatted": format_duration(duration_mins),
                    "mode": mode,
                    "is_estimate": False,
                    "provider": "OSRM (OpenStreetMap road routing)"
                }
                _route_cache[cache_key] = res
                return res
    except Exception:
        pass

    # 3. Fallback: Haversine with empirical road curvature factor
    crow_km = haversine_distance(lat1, lon1, lat2, lon2)
    road_multiplier = 1.35 if crow_km > 30 else 1.25
    dist_km = round(crow_km * road_multiplier, 1)

    # Average speed assumptions
    if mode == "walking":
        avg_speed = 4.5  # km/h
    elif dist_km < 20:
        avg_speed = 25.0  # city traffic km/h
    elif dist_km < 100:
        avg_speed = 45.0  # suburban km/h
    else:
        avg_speed = 65.0  # highway km/h

    duration_mins = max(1, round((dist_km / avg_speed) * 60))
    res = {
        "distance_km": dist_km,
        "duration_minutes": duration_mins,
        "duration_formatted": format_duration(duration_mins),
        "mode": mode,
        "is_estimate": True,
        "provider": "Estimated road distance (Haversine road-network model)"
    }
    _route_cache[cache_key] = res
    return res


def format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    hrs = minutes // 60
    rem = minutes % 60
    if rem == 0:
        return f"{hrs} hr" if hrs == 1 else f"{hrs} hrs"
    return f"{hrs}h {rem}m"


def get_google_maps_directions_url(origin: str, destination: str, mode: str = "driving") -> str:
    from urllib.parse import quote
    return f"https://www.google.com/maps/dir/?api=1&origin={quote(origin)}&destination={quote(destination)}&travelmode={mode}"
