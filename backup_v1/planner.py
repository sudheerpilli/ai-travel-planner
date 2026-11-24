"""
TripWise — upgraded travel planner.

Key improvements over v1
------------------------
* Expense-based budget engine (not % of user budget).
* Realistic per-night accommodation, per-day food and per-person activity costs.
* Real currency conversion via exchangerate.host (free, no key required).
* Hardcoded fallback rates so the app works offline.
* Wikipedia result filtering (drops list/disambiguation articles).
* Curated destination-specific attraction catalogue.
* Free OSRM routing for distance/travel-time between consecutive attractions.
* Nominatim geocoding (OpenStreetMap, no API key required).
* Budget-sufficiency assessment with actionable suggestions.
* All costs scale correctly with trip duration and traveller count.
"""

from __future__ import annotations

import math
import os
import re
import time
from datetime import date, timedelta
from html import unescape
from typing import Optional

import requests

# ─────────────────────────────────────────────────────────────
# RATE CONFIGURATION  (all values in INR; easily adjustable)
# ─────────────────────────────────────────────────────────────
RATES_INR: dict = {
    # Nightly hotel cost per ROOM (budget tier)
    "accommodation_per_room_night": 2_500,
    # Daily food cost per PERSON
    "food_per_person_day": 800,
    # One-way local transport per PERSON per DAY (metro/bus/taxi)
    "local_transport_per_person_day": 400,
    # Intercity transport per PERSON (one return trip assumed)
    "intercity_transport_per_person": 3_000,
    # Default entrance fee per PERSON per ATTRACTION
    "attraction_default_cost_per_person": 300,
    # Emergency contingency — fraction of total estimated cost
    "contingency_fraction": 0.08,
    # Assumed travellers per room (sharing)
    "travelers_per_room": 2,
}

# Supported currencies and hardcoded fallback exchange rates (1 INR → X)
# These are approximate and are only used when the live API is unavailable.
_FALLBACK_RATES_FROM_INR: dict[str, float] = {
    "INR": 1.0,
    "USD": 0.012,
    "EUR": 0.011,
    "GBP": 0.0095,
}

# ─────────────────────────────────────────────────────────────
# CURATED DESTINATION ATTRACTIONS
# (name, description, category, cost_inr_per_person, lat, lon)
# ─────────────────────────────────────────────────────────────
_DEST_ATTRACTIONS: dict[str, list[dict]] = {
    "paris": [
        {"name": "Eiffel Tower", "desc": "Iconic iron lattice tower on the Champ de Mars", "cat": "culture", "cost": 700, "lat": 48.8584, "lon": 2.2945},
        {"name": "Louvre Museum", "desc": "World's largest art museum and historic monument", "cat": "culture", "cost": 1_000, "lat": 48.8606, "lon": 2.3376},
        {"name": "Notre-Dame Cathedral", "desc": "Medieval Catholic cathedral on the Île de la Cité", "cat": "culture", "cost": 0, "lat": 48.8530, "lon": 2.3499},
        {"name": "Montmartre Quarter", "desc": "Bohemian hilltop neighbourhood with the Sacré-Cœur basilica", "cat": "culture", "cost": 0, "lat": 48.8867, "lon": 2.3431},
        {"name": "Seine River Cruise", "desc": "Scenic boat tour along the Seine past major landmarks", "cat": "nature", "cost": 900, "lat": 48.8566, "lon": 2.3522},
        {"name": "Musée d'Orsay", "desc": "Impressionist art museum in a former railway station", "cat": "culture", "cost": 800, "lat": 48.8600, "lon": 2.3266},
        {"name": "Marché d'Aligre", "desc": "Lively open-air food and flea market", "cat": "food", "cost": 200, "lat": 48.8499, "lon": 2.3745},
        {"name": "Champs-Élysées", "desc": "Famous boulevard lined with shops, cafés and theatres", "cat": "shopping", "cost": 0, "lat": 48.8698, "lon": 2.3078},
        {"name": "Luxembourg Gardens", "desc": "Beautiful public garden with fountains and sculptures", "cat": "nature", "cost": 0, "lat": 48.8462, "lon": 2.3372},
        {"name": "Moulin Rouge Show", "desc": "World-famous cabaret show in Pigalle", "cat": "culture", "cost": 5_000, "lat": 48.8841, "lon": 2.3322},
    ],
    "tokyo": [
        {"name": "Senso-ji Temple", "desc": "Tokyo's oldest and most famous Buddhist temple in Asakusa", "cat": "culture", "cost": 0, "lat": 35.7148, "lon": 139.7967},
        {"name": "Shibuya Crossing", "desc": "World's busiest pedestrian crossing surrounded by neon lights", "cat": "culture", "cost": 0, "lat": 35.6595, "lon": 139.7004},
        {"name": "teamLab Borderless", "desc": "Immersive digital art museum with interactive installations", "cat": "culture", "cost": 2_000, "lat": 35.6248, "lon": 139.7803},
        {"name": "Tsukiji Outer Market", "desc": "Famous market for fresh seafood, sushi and Japanese snacks", "cat": "food", "cost": 600, "lat": 35.6654, "lon": 139.7707},
        {"name": "Shinjuku Gyoen Garden", "desc": "Large national garden with Japanese, French and English sections", "cat": "nature", "cost": 250, "lat": 35.6851, "lon": 139.7100},
        {"name": "Akihabara District", "desc": "Electronics and anime shopping hub in central Tokyo", "cat": "shopping", "cost": 0, "lat": 35.7023, "lon": 139.7745},
        {"name": "Meiji Shrine", "desc": "Shinto shrine set in a forested area in Harajuku", "cat": "culture", "cost": 0, "lat": 35.6763, "lon": 139.6993},
        {"name": "Tokyo Skytree", "desc": "Broadcasting tower with observation decks and city panoramas", "cat": "culture", "cost": 1_800, "lat": 35.7101, "lon": 139.8107},
        {"name": "Harajuku Takeshita Street", "desc": "Colourful pedestrian street famous for youth fashion", "cat": "shopping", "cost": 0, "lat": 35.6703, "lon": 139.7027},
        {"name": "Ueno Park & Museums", "desc": "Large public park with museums, a zoo and cherry blossoms", "cat": "nature", "cost": 300, "lat": 35.7156, "lon": 139.7731},
    ],
    "bali": [
        {"name": "Uluwatu Temple", "desc": "Sea temple perched on a 70-metre cliff above the Indian Ocean", "cat": "culture", "cost": 300, "lat": -8.8291, "lon": 115.0849},
        {"name": "Tegallalang Rice Terraces", "desc": "Stunning terraced rice paddies north of Ubud", "cat": "nature", "cost": 150, "lat": -8.4318, "lon": 115.2790},
        {"name": "Tanah Lot Temple", "desc": "Offshore temple on a rocky outcrop, famous at sunset", "cat": "culture", "cost": 350, "lat": -8.6215, "lon": 115.0868},
        {"name": "Kuta Beach", "desc": "Famous beach known for surfing, sunsets and nightlife", "cat": "adventure", "cost": 0, "lat": -8.7215, "lon": 115.1685},
        {"name": "Sacred Monkey Forest Ubud", "desc": "Nature reserve and Hindu temple complex with wild macaques", "cat": "nature", "cost": 350, "lat": -8.5190, "lon": 115.2588},
        {"name": "Ubud Art Market", "desc": "Traditional market selling handmade crafts, textiles and souvenirs", "cat": "shopping", "cost": 200, "lat": -8.5066, "lon": 115.2637},
        {"name": "Mount Batur Sunrise Trek", "desc": "Guided sunrise hike to the active volcano crater at 1717m", "cat": "adventure", "cost": 800, "lat": -8.2420, "lon": 115.3750},
        {"name": "Seminyak Beach Dining", "desc": "Trendy beach clubs and seafood restaurants on the west coast", "cat": "food", "cost": 700, "lat": -8.6911, "lon": 115.1618},
    ],
    "goa": [
        {"name": "Baga Beach", "desc": "Popular beach known for water sports, shacks and nightlife", "cat": "adventure", "cost": 0, "lat": 15.5523, "lon": 73.7517},
        {"name": "Basilica of Bom Jesus", "desc": "UNESCO World Heritage baroque church in Old Goa", "cat": "culture", "cost": 0, "lat": 15.5009, "lon": 73.9116},
        {"name": "Dudhsagar Falls", "desc": "Spectacular four-tiered waterfall on the Goa-Karnataka border", "cat": "nature", "cost": 500, "lat": 15.3148, "lon": 74.3143},
        {"name": "Anjuna Flea Market", "desc": "Famous Wednesday flea market with handicrafts and clothes", "cat": "shopping", "cost": 0, "lat": 15.5757, "lon": 73.7419},
        {"name": "Calangute Beach", "desc": "Largest beach in North Goa, known as the Queen of Beaches", "cat": "nature", "cost": 0, "lat": 15.5438, "lon": 73.7547},
        {"name": "Fort Aguada", "desc": "17th-century Portuguese fort with lighthouse and sea views", "cat": "culture", "cost": 0, "lat": 15.4921, "lon": 73.7730},
        {"name": "Palolem Beach", "desc": "Crescent-shaped beach in South Goa, quieter and scenic", "cat": "nature", "cost": 0, "lat": 15.0100, "lon": 74.0232},
        {"name": "Goan Seafood Trail", "desc": "Local seafood restaurants serving prawn curry, fish thali and more", "cat": "food", "cost": 600, "lat": 15.4909, "lon": 73.8278},
        {"name": "Casino Cruise", "desc": "Evening casino cruise on the Mandovi River in Panaji", "cat": "adventure", "cost": 1_200, "lat": 15.4989, "lon": 73.8278},
    ],
    "hyderabad": [
        {"name": "Charminar", "desc": "Iconic 16th-century mosque and monument in the old city", "cat": "culture", "cost": 25, "lat": 17.3616, "lon": 78.4747},
        {"name": "Golconda Fort", "desc": "Ruined fort with palaces, mosques and acoustic marvels", "cat": "culture", "cost": 25, "lat": 17.3833, "lon": 78.4011},
        {"name": "Ramoji Film City", "desc": "World's largest integrated film studio complex", "cat": "family", "cost": 1_000, "lat": 17.2543, "lon": 78.6808},
        {"name": "Salar Jung Museum", "desc": "Museum of one of the largest one-man art collections in the world", "cat": "culture", "cost": 20, "lat": 17.3710, "lon": 78.4803},
        {"name": "Hussain Sagar Lake", "desc": "Large artificial lake with a giant Buddha statue on a rock island", "cat": "nature", "cost": 50, "lat": 17.4239, "lon": 78.4738},
        {"name": "Laad Bazaar", "desc": "Historic market famous for bangles, jewellery and bridal wear", "cat": "shopping", "cost": 0, "lat": 17.3612, "lon": 78.4733},
        {"name": "Biryani at Paradise Restaurant", "desc": "Legendary Hyderabadi dum biryani institution since 1953", "cat": "food", "cost": 400, "lat": 17.4450, "lon": 78.4952},
        {"name": "Nehru Zoological Park", "desc": "Large zoo with over 1,500 animals across 380 acres", "cat": "family", "cost": 80, "lat": 17.3491, "lon": 78.4506},
    ],
    "new york": [
        {"name": "Statue of Liberty & Ellis Island", "desc": "Iconic copper statue on Liberty Island with ferry access", "cat": "culture", "cost": 2_000, "lat": 40.6892, "lon": -74.0445},
        {"name": "Central Park", "desc": "Vast urban park with trails, lakes, the Met and more", "cat": "nature", "cost": 0, "lat": 40.7851, "lon": -73.9683},
        {"name": "Metropolitan Museum of Art", "desc": "One of the world's largest and most visited art museums", "cat": "culture", "cost": 1_500, "lat": 40.7794, "lon": -73.9632},
        {"name": "Times Square", "desc": "Commercial intersection known for Broadway, lights and crowds", "cat": "culture", "cost": 0, "lat": 40.7580, "lon": -73.9855},
        {"name": "Brooklyn Bridge Walk", "desc": "Scenic pedestrian walkway across the East River", "cat": "nature", "cost": 0, "lat": 40.7061, "lon": -73.9969},
        {"name": "9/11 Memorial & Museum", "desc": "Memorial pools and museum at the former World Trade Center site", "cat": "culture", "cost": 1_800, "lat": 40.7115, "lon": -74.0134},
        {"name": "Chelsea Market Food Hall", "desc": "Indoor urban food market with 35+ eateries in a historic factory", "cat": "food", "cost": 700, "lat": 40.7421, "lon": -74.0065},
        {"name": "Fifth Avenue Shopping", "desc": "World-famous shopping street with flagship luxury stores", "cat": "shopping", "cost": 0, "lat": 40.7549, "lon": -73.9840},
        {"name": "High Line Park", "desc": "Elevated linear park on a historic freight rail line", "cat": "nature", "cost": 0, "lat": 40.7480, "lon": -74.0048},
    ],
    "london": [
        {"name": "British Museum", "desc": "World-renowned museum of human history and culture", "cat": "culture", "cost": 0, "lat": 51.5194, "lon": -0.1269},
        {"name": "Tower of London", "desc": "Historic castle and former royal palace on the River Thames", "cat": "culture", "cost": 2_000, "lat": 51.5081, "lon": -0.0759},
        {"name": "Buckingham Palace", "desc": "Official residence of the UK monarch, famous for the Changing of the Guard", "cat": "culture", "cost": 0, "lat": 51.5014, "lon": -0.1419},
        {"name": "Hyde Park", "desc": "Royal park with the Serpentine Lake, Speaker's Corner and open lawns", "cat": "nature", "cost": 0, "lat": 51.5074, "lon": -0.1657},
        {"name": "Borough Market", "desc": "One of London's oldest and most famous food markets", "cat": "food", "cost": 500, "lat": 51.5055, "lon": -0.0910},
        {"name": "The Shard Viewing Gallery", "desc": "Panoramic views of London from the 72nd floor", "cat": "culture", "cost": 2_200, "lat": 51.5045, "lon": -0.0865},
        {"name": "Oxford Street Shopping", "desc": "Europe's busiest shopping street with 300+ shops", "cat": "shopping", "cost": 0, "lat": 51.5154, "lon": -0.1410},
        {"name": "Warner Bros. Studio Tour — Harry Potter", "desc": "Behind-the-scenes tour of the making of the Harry Potter films", "cat": "family", "cost": 3_000, "lat": 51.6904, "lon": -0.4171},
        {"name": "Thames River Cruise", "desc": "Boat trip from Westminster to Greenwich passing Tower Bridge", "cat": "nature", "cost": 1_200, "lat": 51.5033, "lon": -0.1195},
    ],
    "dubai": [
        {"name": "Burj Khalifa Observation Deck", "desc": "View from the world's tallest building at 828m", "cat": "culture", "cost": 2_500, "lat": 25.1972, "lon": 55.2744},
        {"name": "Dubai Mall", "desc": "Mega-mall with an aquarium, ice rink and 1,200 stores", "cat": "shopping", "cost": 0, "lat": 25.1972, "lon": 55.2797},
        {"name": "Palm Jumeirah", "desc": "Artificial archipelago island with luxury hotels and beaches", "cat": "nature", "cost": 0, "lat": 25.1124, "lon": 55.1390},
        {"name": "Dubai Creek & Gold Souk", "desc": "Historic waterway and traditional market for gold and jewellery", "cat": "shopping", "cost": 0, "lat": 25.2631, "lon": 55.2997},
        {"name": "Dubai Desert Safari", "desc": "Evening desert adventure with dune bashing, camel rides and BBQ", "cat": "adventure", "cost": 2_200, "lat": 24.9900, "lon": 55.5080},
        {"name": "Dubai Frame", "desc": "Picture-frame-shaped skyscraper bridging old and new Dubai", "cat": "culture", "cost": 1_200, "lat": 25.2353, "lon": 55.3001},
        {"name": "Global Village", "desc": "Cultural and entertainment festival park (Oct–Apr)", "cat": "family", "cost": 400, "lat": 25.0703, "lon": 55.3047},
        {"name": "Jumeirah Beach", "desc": "White sand beach with views of the Burj Al Arab", "cat": "nature", "cost": 0, "lat": 25.2048, "lon": 55.2386},
    ],
    "singapore": [
        {"name": "Marina Bay Sands SkyPark", "desc": "Rooftop observation deck on the three-tower hotel complex", "cat": "culture", "cost": 1_500, "lat": 1.2834, "lon": 103.8607},
        {"name": "Gardens by the Bay", "desc": "Futuristic nature park with Supertrees and Climate Domes", "cat": "nature", "cost": 1_200, "lat": 1.2816, "lon": 103.8636},
        {"name": "Hawker Centre Food Tour", "desc": "Singapore's famous street-food hawker centres — Maxwell, Lau Pa Sat", "cat": "food", "cost": 600, "lat": 1.2804, "lon": 103.8459},
        {"name": "Universal Studios Singapore", "desc": "Theme park on Sentosa Island with themed rides and shows", "cat": "family", "cost": 4_000, "lat": 1.2540, "lon": 103.8238},
        {"name": "Little India & Chinatown", "desc": "Vibrant ethnic enclaves with temples, street food and markets", "cat": "culture", "cost": 0, "lat": 1.3066, "lon": 103.8518},
        {"name": "Orchard Road Shopping", "desc": "Singapore's premier shopping and dining boulevard", "cat": "shopping", "cost": 0, "lat": 1.3035, "lon": 103.8318},
        {"name": "Night Safari at Singapore Zoo", "desc": "World's first nocturnal zoo with guided tram rides", "cat": "family", "cost": 2_500, "lat": 1.4043, "lon": 103.7930},
        {"name": "Sentosa Island", "desc": "Beach resort island with Adventure Cove, beaches and cable car", "cat": "adventure", "cost": 500, "lat": 1.2494, "lon": 103.8303},
    ],
    "mumbai": [
        {"name": "Gateway of India", "desc": "Iconic arch monument on the Mumbai harbour waterfront", "cat": "culture", "cost": 0, "lat": 18.9220, "lon": 72.8347},
        {"name": "Elephanta Caves", "desc": "UNESCO rock-cut cave temples with sculptures of Shiva on an island", "cat": "culture", "cost": 600, "lat": 18.9633, "lon": 72.9315},
        {"name": "Chhatrapati Shivaji Maharaj Terminus", "desc": "Historic Victorian-era railway station and UNESCO World Heritage Site", "cat": "culture", "cost": 0, "lat": 18.9400, "lon": 72.8347},
        {"name": "Marine Drive", "desc": "3.6 km boulevard along the Arabian Sea, the Queen's Necklace at night", "cat": "nature", "cost": 0, "lat": 18.9438, "lon": 72.8235},
        {"name": "Dharavi Slum Tour", "desc": "Guided community tour of Asia's largest slum and cottage industry hub", "cat": "culture", "cost": 500, "lat": 19.0378, "lon": 72.8534},
        {"name": "Colaba Causeway Market", "desc": "Street market for handicrafts, antiques, fashion and street food", "cat": "shopping", "cost": 0, "lat": 18.9162, "lon": 72.8308},
        {"name": "Sanjay Gandhi National Park", "desc": "Large national park with leopards, ancient caves and a lake", "cat": "nature", "cost": 80, "lat": 19.2140, "lon": 72.9103},
        {"name": "Vada Pav & Street Food Trail", "desc": "Tasting tour of Mumbai's iconic street food — vada pav, pav bhaji, bhel puri", "cat": "food", "cost": 300, "lat": 18.9387, "lon": 72.8353},
    ],
}

# Generic fallback attractions (used when destination not in curated list)
_GENERIC_ATTRACTIONS: dict[str, list[dict]] = {
    "culture": [
        {"name": "City Heritage Museum", "desc": "Explore local history, art and cultural artefacts", "cat": "culture", "cost": 250},
        {"name": "Historic Old Town Walk", "desc": "Guided walk through historic streets, temples and monuments", "cat": "culture", "cost": 150},
        {"name": "Traditional Performing Arts", "desc": "Local music, dance or theatrical performance", "cat": "culture", "cost": 400},
        {"name": "Religious & Spiritual Sites", "desc": "Visit the city's iconic temples, mosques or churches", "cat": "culture", "cost": 0},
    ],
    "nature": [
        {"name": "Botanical Garden", "desc": "Stroll through curated gardens and green spaces", "cat": "nature", "cost": 150},
        {"name": "Scenic Viewpoint Hike", "desc": "Trek to a panoramic viewpoint overlooking the city or landscape", "cat": "nature", "cost": 100},
        {"name": "Riverside or Lakeside Walk", "desc": "Relaxing walk along the waterfront with scenic views", "cat": "nature", "cost": 0},
        {"name": "City Park & Picnic", "desc": "Spend time in a well-known local park", "cat": "nature", "cost": 0},
    ],
    "food": [
        {"name": "Local Street Food Market", "desc": "Sample regional snacks, street food and beverages", "cat": "food", "cost": 400},
        {"name": "Regional Cuisine Restaurant", "desc": "Authentic sit-down meal at a celebrated local restaurant", "cat": "food", "cost": 600},
        {"name": "Food Tasting Experience", "desc": "Guided tasting tour of the city's speciality dishes", "cat": "food", "cost": 700},
        {"name": "Breakfast at a Local Café", "desc": "Start the day at a popular local café with regional breakfast", "cat": "food", "cost": 250},
    ],
    "adventure": [
        {"name": "Outdoor Activity Centre", "desc": "Choose from zipline, rock climbing, kayaking or cycling", "cat": "adventure", "cost": 800},
        {"name": "Cycling Tour of the City", "desc": "Guided bicycle tour covering major landmarks", "cat": "adventure", "cost": 350},
        {"name": "Day Trip to Nearby Destination", "desc": "Excursion to a scenic spot within 2 hours of the city", "cat": "adventure", "cost": 1_200},
    ],
    "shopping": [
        {"name": "Local Handicraft Market", "desc": "Browse locally made crafts, textiles and souvenirs", "cat": "shopping", "cost": 400},
        {"name": "Main Shopping District", "desc": "Explore the city's primary retail and shopping area", "cat": "shopping", "cost": 300},
        {"name": "Artisan & Antique Stores", "desc": "Discover unique handmade products and vintage items", "cat": "shopping", "cost": 250},
    ],
    "family": [
        {"name": "Science or Discovery Centre", "desc": "Interactive exhibits for children and adults alike", "cat": "family", "cost": 350},
        {"name": "Zoo or Wildlife Park", "desc": "Visit a local zoo or wildlife sanctuary", "cat": "family", "cost": 300},
        {"name": "Amusement or Theme Park", "desc": "A fun day at a local theme or amusement park", "cat": "family", "cost": 500},
    ],
}

# Wikipedia article patterns to filter out (not real attractions)
_WIKI_FILTER_PATTERNS = [
    r"^list of",
    r"^lists of",
    r"^index of",
    r"tourism in ",
    r"transport in ",
    r"economy of ",
    r"history of ",
    r"culture of ",
    r"geography of ",
    r"politics of ",
    r"government of ",
    r" district$",
    r" province$",
    r" state$",
    r" country$",
    r" region$",
    r" county$",
    r" municipality$",
    r" prefecture$",
    r"^administrative",
]


# ─────────────────────────────────────────────────────────────
# EXCHANGE RATE HELPERS
# ─────────────────────────────────────────────────────────────

_rate_cache: dict = {}          # {currency: (rate_inr_to_currency, timestamp)}
_RATE_CACHE_SECONDS = 3_600     # refresh every hour


def _get_exchange_rate(currency: str) -> tuple[float, str]:
    """
    Return (multiplier, source_note) where multiplier converts INR → currency.

    Tries exchangerate.host (free, no key) first, then falls back to
    hardcoded approximate rates.
    """
    currency = currency.upper()
    if currency == "INR":
        return 1.0, "no conversion needed"

    now = time.time()
    cached = _rate_cache.get(currency)
    if cached and (now - cached[1]) < _RATE_CACHE_SECONDS:
        return cached[0], "live rate (cached)"

    try:
        resp = requests.get(
            "https://api.exchangerate-api.com/v4/latest/INR",
            timeout=6,
            headers={"User-Agent": "TripWisePlanner/2.0"},
        )
        resp.raise_for_status()
        rates = resp.json().get("rates", {})
        rate = rates.get(currency)
        if rate:
            _rate_cache[currency] = (rate, now)
            return rate, "live rate"
    except Exception:
        pass

    # Fallback
    rate = _FALLBACK_RATES_FROM_INR.get(currency, 1.0)
    return rate, "approximate fallback rate"


def _convert(amount_inr: float, currency: str) -> float:
    """Convert an INR amount to the target currency."""
    rate, _ = _get_exchange_rate(currency)
    return amount_inr * rate


def _currency_note(currency: str) -> str:
    _, note = _get_exchange_rate(currency)
    return note


# ─────────────────────────────────────────────────────────────
# DATE HELPERS
# ─────────────────────────────────────────────────────────────

def _dates(start: str, end: str) -> list[date]:
    """Generate trip dates, capped at 31 days."""
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if last < first:
        raise ValueError("End date must not be before start date.")
    if (last - first).days > 30:
        last = first + timedelta(days=30)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


# ─────────────────────────────────────────────────────────────
# GEOCODING  (Nominatim, no key required)
# ─────────────────────────────────────────────────────────────

_geocode_cache: dict[str, Optional[tuple[float, float]]] = {}

def _geocode(name: str, destination: str) -> Optional[tuple[float, float]]:
    """Return (lat, lon) for a place name, or None if not found."""
    query = f"{name}, {destination}"
    if query in _geocode_cache:
        return _geocode_cache[query]

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "TripWisePlanner/2.0"},
            timeout=6,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            coords = (float(results[0]["lat"]), float(results[0]["lon"]))
            _geocode_cache[query] = coords
            return coords
    except Exception:
        pass

    _geocode_cache[query] = None
    return None


# ─────────────────────────────────────────────────────────────
# ROUTING  (OSRM public demo server, no key required)
# ─────────────────────────────────────────────────────────────

_route_cache: dict[str, Optional[dict]] = {}

def _route_between(
    a: tuple[float, float],
    b: tuple[float, float],
    profile: str = "driving",
) -> Optional[dict]:
    """
    Return {distance_km, duration_min} for the road route from a to b,
    or None on failure.  Uses the public OSRM demo endpoint.
    """
    key = f"{a[0]:.4f},{a[1]:.4f}|{b[0]:.4f},{b[1]:.4f}|{profile}"
    if key in _route_cache:
        return _route_cache[key]

    try:
        url = (
            f"http://router.project-osrm.org/route/v1/{profile}/"
            f"{a[1]},{a[0]};{b[1]},{b[0]}"
            f"?overview=false"
        )
        resp = requests.get(url, timeout=6, headers={"User-Agent": "TripWisePlanner/2.0"})
        resp.raise_for_status()
        routes = resp.json().get("routes", [])
        if routes:
            r = routes[0]
            result = {
                "distance_km": round(r["distance"] / 1000, 1),
                "duration_min": round(r["duration"] / 60),
            }
            _route_cache[key] = result
            return result
    except Exception:
        pass

    _route_cache[key] = None
    return None


# ─────────────────────────────────────────────────────────────
# ATTRACTION DISCOVERY
# ─────────────────────────────────────────────────────────────

def _normalise_dest(destination: str) -> str:
    return destination.strip().lower()


def _curated_attractions(destination: str, interests: list[str]) -> list[dict]:
    """Return curated attractions for the destination filtered by interests."""
    key = _normalise_dest(destination)
    # Try exact match, then partial match
    pool = _DEST_ATTRACTIONS.get(key)
    if not pool:
        for k, v in _DEST_ATTRACTIONS.items():
            if k in key or key in k:
                pool = v
                break
    if not pool:
        return []

    if not interests:
        return pool

    # Filter to matching interests, falling back to all if none match
    filtered = [a for a in pool if a["cat"] in interests]
    return filtered if filtered else pool


def _generic_attractions(interests: list[str]) -> list[dict]:
    """Return generic (non-destination-specific) attractions for given interests."""
    out = []
    for interest in interests:
        out.extend(_GENERIC_ATTRACTIONS.get(interest, []))
    if not out:
        for v in _GENERIC_ATTRACTIONS.values():
            out.extend(v)
    return out


def _wiki_attractions(destination: str) -> list[dict]:
    """
    Fetch Wikipedia search results and filter to plausible attraction names.
    Returns list of dicts with name, desc, cat="culture", cost=0.
    """
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"tourist attraction {destination}",
                "format": "json",
                "srlimit": 15,
            },
            headers={"User-Agent": "TripWisePlanner/2.0"},
            timeout=8,
        )
        resp.raise_for_status()
        results = resp.json().get("query", {}).get("search", [])
    except Exception:
        return []

    out = []
    for item in results:
        title = item.get("title", "").strip()
        if not title:
            continue
        # Apply filter patterns
        lower_title = title.lower()
        if any(re.search(p, lower_title) for p in _WIKI_FILTER_PATTERNS):
            continue
        # Filter out destination-name-only articles
        if lower_title == _normalise_dest(destination):
            continue
        snippet = re.sub(r"<[^>]*>", "", item.get("snippet", ""))
        desc = unescape(snippet).strip() or "A notable landmark or attraction."
        out.append({"name": title, "desc": desc, "cat": "culture", "cost": 300})

    return out


def _build_attraction_pool(
    destination: str, interests: list[str]
) -> list[dict]:
    """
    Build a deduplicated, ordered pool of attractions.
    Priority: curated > Wikipedia-filtered > generic fallback
    """
    curated = _curated_attractions(destination, interests)
    wiki = _wiki_attractions(destination) if not curated else []
    generic = _generic_attractions(interests)

    pool: list[dict] = []
    seen: set[str] = set()

    for a in [*curated, *wiki, *generic]:
        key = a["name"].lower()
        if key not in seen:
            pool.append(a)
            seen.add(key)

    return pool


# ─────────────────────────────────────────────────────────────
# BUDGET ENGINE  (expense-based)
# ─────────────────────────────────────────────────────────────

def _estimate_costs_inr(
    destination: str,
    num_days: int,
    num_nights: int,
    travelers: int,
    activity_pool: list[dict],
    activities_per_day: int = 3,
) -> dict:
    """
    Calculate a realistic expense-based trip cost in INR.

    Returns a dict with individual line items and the total.
    All arithmetic is transparent and documented in `basis` fields.
    """
    r = RATES_INR
    rooms = math.ceil(travelers / r["travelers_per_room"])

    # Accommodation
    accommodation = r["accommodation_per_room_night"] * rooms * num_nights
    accommodation_basis = (
        f"{rooms} room(s) × ₹{r['accommodation_per_room_night']:,}/night × {num_nights} night(s)"
    )

    # Food
    food = r["food_per_person_day"] * travelers * num_days
    food_basis = (
        f"₹{r['food_per_person_day']:,}/person/day × {travelers} traveller(s) × {num_days} day(s)"
    )

    # Local transport
    local_transport = r["local_transport_per_person_day"] * travelers * num_days
    local_transport_basis = (
        f"₹{r['local_transport_per_person_day']:,}/person/day × {travelers} traveller(s) × {num_days} day(s)"
    )

    # Intercity transport (one return trip assumed)
    intercity_transport = r["intercity_transport_per_person"] * travelers
    intercity_basis = (
        f"₹{r['intercity_transport_per_person']:,}/person (return) × {travelers} traveller(s)"
    )

    # Attractions
    total_activities = num_days * activities_per_day
    # Use actual costs from pool where available; fall back to default
    activity_costs = []
    for i in range(total_activities):
        a = activity_pool[i % len(activity_pool)]
        cost_pp = a.get("cost", r["attraction_default_cost_per_person"])
        activity_costs.append(cost_pp * travelers)

    attractions = sum(activity_costs)
    attractions_basis = (
        f"{total_activities} activities across {num_days} day(s), "
        f"avg ₹{round(attractions / max(total_activities, 1)):,}/activity"
    )

    subtotal = (
        accommodation
        + food
        + local_transport
        + intercity_transport
        + attractions
    )

    contingency = round(subtotal * r["contingency_fraction"])
    contingency_basis = f"{int(r['contingency_fraction'] * 100)}% of subtotal"

    estimated_total = subtotal + contingency

    return {
        "accommodation": round(accommodation),
        "accommodation_basis": accommodation_basis,
        "food": round(food),
        "food_basis": food_basis,
        "local_transport": round(local_transport),
        "local_transport_basis": local_transport_basis,
        "intercity_transport": round(intercity_transport),
        "intercity_transport_basis": intercity_basis,
        "attractions": round(attractions),
        "attractions_basis": attractions_basis,
        "subtotal": round(subtotal),
        "contingency": round(contingency),
        "contingency_basis": contingency_basis,
        "estimated_total": round(estimated_total),
        "per_person": round(estimated_total / travelers),
    }


# ─────────────────────────────────────────────────────────────
# BUDGET ASSESSMENT
# ─────────────────────────────────────────────────────────────

def _budget_assessment(
    budget_inr: float,
    estimated_total_inr: float,
    num_days: int,
    travelers: int,
    currency: str,
) -> dict:
    """
    Return a budget assessment with status, difference, percentage used
    and actionable suggestions if the budget is insufficient.
    """
    diff = budget_inr - estimated_total_inr
    pct_used = round((estimated_total_inr / max(budget_inr, 1)) * 100)

    if diff > 0:
        status = "sufficient"
        status_label = "Budget Sufficient ✅"
        status_color = "green"
    elif diff == 0:
        status = "exact"
        status_label = "Exact Match ⚠️"
        status_color = "yellow"
    else:
        status = "insufficient"
        status_label = "Budget Insufficient ❌"
        status_color = "red"

    suggestions = []
    if status == "insufficient":
        shortfall = abs(diff)
        suggestions = [
            f"Increase your budget by ₹{round(shortfall):,} to cover the full estimated cost.",
            "Choose budget accommodation (shared dorms or guesthouses) to reduce lodging costs by 40–60%.",
            "Reduce trip duration — each day removed saves roughly "
            f"₹{round((estimated_total_inr - RATES_INR['intercity_transport_per_person'] * travelers) / max(num_days, 1)):,}.",
            "Focus on free attractions (public parks, beaches, historic streets) to cut activity costs.",
            "Use public transport instead of taxis to reduce local transport costs significantly.",
            f"Split the trip into {travelers} separate bookings to reduce per-person costs.",
        ]

    return {
        "status": status,
        "status_label": status_label,
        "status_color": status_color,
        "budget_inr": round(budget_inr),
        "estimated_inr": round(estimated_total_inr),
        "difference_inr": round(diff),
        "pct_used": pct_used,
        "suggestions": suggestions,
        "disclaimer": (
            "All figures are estimates based on average costs. "
            "Actual prices depend on season, booking timing and personal choices."
        ),
    }


# ─────────────────────────────────────────────────────────────
# ROUTING ENRICHMENT
# ─────────────────────────────────────────────────────────────

def _enrich_with_routes(daily: list[dict], destination: str) -> list[dict]:
    """
    For each day, attempt to calculate distances between consecutive
    morning → afternoon → evening activities.
    Adds a `travel_to_next` field to morning and afternoon slots.
    Also attempts to geocode each attraction for Google Maps links.
    """
    slot_keys = ["morning", "afternoon", "evening"]

    for day in daily:
        coords: list[Optional[tuple[float, float]]] = []

        for key in slot_keys:
            slot = day[key]
            # Use embedded coords if available
            if "lat" in slot and "lon" in slot:
                coords.append((slot["lat"], slot["lon"]))
            else:
                c = _geocode(slot["name"], destination)
                coords.append(c)
                if c:
                    slot["lat"] = c[0]
                    slot["lon"] = c[1]

        # Calculate routes between consecutive slots
        for i, key in enumerate(slot_keys[:-1]):
            a = coords[i]
            b = coords[i + 1]
            if a and b:
                route = _route_between(a, b)
                if route:
                    day[slot_keys[i]]["travel_to_next"] = route
                else:
                    day[slot_keys[i]]["travel_to_next"] = None
            else:
                day[slot_keys[i]]["travel_to_next"] = None

    return daily


# ─────────────────────────────────────────────────────────────
# MINIMUM BUDGET GUARD
# ─────────────────────────────────────────────────────────────

def _minimum_budget_inr(num_days: int, travelers: int) -> float:
    """Return the absolute minimum sensible budget in INR for this trip."""
    rooms = math.ceil(travelers / RATES_INR["travelers_per_room"])
    nights = max(num_days - 1, 0)
    return (
        RATES_INR["accommodation_per_room_night"] * rooms * max(nights, 1)
        + RATES_INR["food_per_person_day"] * travelers * num_days
        + RATES_INR["local_transport_per_person_day"] * travelers * num_days
    )


# ─────────────────────────────────────────────────────────────
# MAIN PUBLIC FUNCTION
# ─────────────────────────────────────────────────────────────

def create_itinerary(
    destination: str,
    start_date: str,
    end_date: str,
    budget: float,
    interests: list[str],
    travelers: int,
    currency: str = "INR",
) -> dict:
    """
    Create a fully costed day-by-day travel itinerary.

    Parameters
    ----------
    destination : str
        The city or region to visit.
    start_date : str
        ISO date string (YYYY-MM-DD).
    end_date : str
        ISO date string (YYYY-MM-DD).
    budget : float
        User's total available budget in the selected currency.
    interests : list[str]
        Travel interests from {"culture","nature","food","adventure","shopping","family"}.
    travelers : int
        Number of travellers (1–30).
    currency : str
        One of INR, USD, EUR, GBP.

    Returns
    -------
    dict
        Full itinerary, budget breakdown, assessment and metadata.
    """
    # ── Sanitise inputs ──────────────────────────────────────
    destination = str(destination).strip()
    if not destination:
        raise ValueError("Please enter a destination.")

    budget = float(budget)
    travelers = int(travelers)

    if budget <= 0:
        raise ValueError("Budget must be greater than zero.")
    if travelers < 1:
        raise ValueError("At least one traveller is required.")

    # ── Convert user budget to INR for all calculations ──────
    budget_inr: float
    if currency == "INR":
        budget_inr = budget
    else:
        # Convert user budget FROM their currency TO INR
        rate_to_display, _ = _get_exchange_rate(currency)
        if rate_to_display and rate_to_display > 0:
            budget_inr = budget / rate_to_display
        else:
            budget_inr = budget  # fallback — treat as INR

    # ── Dates ────────────────────────────────────────────────
    days = _dates(start_date, end_date)
    num_days = len(days)
    num_nights = num_days - 1  # last day no overnight stay

    # ── Minimum budget check ──────────────────────────────────
    min_budget = _minimum_budget_inr(num_days, travelers)
    min_budget_display = _convert(min_budget, currency)

    # ── Interests ────────────────────────────────────────────
    valid_interests = {"culture", "nature", "food", "adventure", "shopping", "family"}
    interests = [str(i).lower() for i in (interests or []) if str(i).lower() in valid_interests]
    if not interests:
        interests = ["culture", "food", "nature"]

    # ── Attraction pool ──────────────────────────────────────
    pool = _build_attraction_pool(destination, interests)
    if not pool:
        raise ValueError(
            f"No attraction data available for '{destination}'. "
            "Please try a different destination."
        )

    # ── Build daily schedule ─────────────────────────────────
    slot_times = ["09:00–11:30", "12:30–16:00", "17:00–19:30"]
    daily: list[dict] = []

    for idx, day in enumerate(days):
        # Rotate through pool to avoid repetition
        offset = idx * 3
        items = [pool[(offset + j) % len(pool)] for j in range(3)]

        def make_slot(item: dict, t: str) -> dict:
            slot: dict = {
                "time": t,
                "name": item["name"],
                "description": item["desc"],
                "cost_per_person_inr": item.get("cost", RATES_INR["attraction_default_cost_per_person"]),
                "cost": _convert(
                    item.get("cost", RATES_INR["attraction_default_cost_per_person"]) * travelers,
                    currency,
                ),
            }
            if "lat" in item:
                slot["lat"] = item["lat"]
                slot["lon"] = item["lon"]
            return slot

        daily.append({
            "date": day.isoformat(),
            "day": idx + 1,
            "morning":   make_slot(items[0], slot_times[0]),
            "afternoon": make_slot(items[1], slot_times[1]),
            "evening":   make_slot(items[2], slot_times[2]),
        })

    # ── Routing enrichment (best-effort, won't break if it fails) ──
    try:
        daily = _enrich_with_routes(daily, destination)
    except Exception:
        pass  # Routing is optional; never block itinerary generation

    # ── Expense-based cost calculation ───────────────────────
    costs_inr = _estimate_costs_inr(
        destination, num_days, max(num_nights, 1), travelers, pool
    )

    # Convert all cost fields to user currency
    def conv(x: float) -> float:
        return round(_convert(x, currency), 2)

    costs_display = {
        "accommodation":             conv(costs_inr["accommodation"]),
        "accommodation_basis":       costs_inr["accommodation_basis"],
        "food":                      conv(costs_inr["food"]),
        "food_basis":                costs_inr["food_basis"],
        "local_transport":           conv(costs_inr["local_transport"]),
        "local_transport_basis":     costs_inr["local_transport_basis"],
        "intercity_transport":       conv(costs_inr["intercity_transport"]),
        "intercity_transport_basis": costs_inr["intercity_transport_basis"],
        "attractions":               conv(costs_inr["attractions"]),
        "attractions_basis":         costs_inr["attractions_basis"],
        "contingency":               conv(costs_inr["contingency"]),
        "contingency_basis":         costs_inr["contingency_basis"],
        "estimated_total":           conv(costs_inr["estimated_total"]),
        "per_person":                conv(costs_inr["per_person"]),
        # Legacy key kept for frontend compatibility
        "transport":                 conv(costs_inr["local_transport"] + costs_inr["intercity_transport"]),
    }

    # ── Budget assessment ────────────────────────────────────
    assessment = _budget_assessment(
        budget_inr, costs_inr["estimated_total"], num_days, travelers, currency
    )
    # Convert assessment monetary values to display currency
    assessment["budget_display"] = conv(assessment["budget_inr"])
    assessment["estimated_display"] = conv(assessment["estimated_inr"])
    assessment["difference_display"] = conv(assessment["difference_inr"])

    # ── Currency metadata ─────────────────────────────────────
    _, cx_note = _get_exchange_rate(currency)

    # ── Notes ────────────────────────────────────────────────
    notes = [
        "All costs are estimates only. Actual prices depend on season, "
        "availability and your personal choices.",
        "Accommodation rate assumes budget hotels; luxury stays can cost 3–5× more.",
        "Activity costs are indicative entrance fees; some attractions may be free or cost more.",
        "Verify opening hours, entry fees and booking requirements before travel.",
    ]
    if currency != "INR":
        notes.insert(0, f"Currency conversion used {cx_note}. Exchange rates fluctuate.")

    source_note = "curated destination data" if _curated_attractions(destination, interests) else "Wikipedia + generic recommendations"

    return {
        # Trip metadata
        "destination":     destination,
        "start_date":      days[0].isoformat(),
        "end_date":        days[-1].isoformat(),
        "days":            daily,
        "num_days":        num_days,
        "num_nights":      max(num_nights, 1),
        "travelers":       travelers,
        "currency":        currency,
        # Budget (in user's selected currency)
        "budget":          round(budget, 2),
        "costs":           costs_display,
        # Budget assessment
        "assessment":      assessment,
        # Minimum recommended budget (in user currency)
        "min_budget_recommended": round(min_budget_display, 2),
        "budget_adequate":        budget_inr >= min_budget,
        # Metadata
        "live_data_used":  bool(_curated_attractions(destination, interests)),
        "attraction_source": source_note,
        "currency_note":   cx_note,
        "notes":           notes,
    }
