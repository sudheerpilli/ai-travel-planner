"""
TripWise — Master Travel Itinerary Planner.
Orchestrates destination attractions, routing, transportation comparisons, budget analysis, and weather.
"""

from __future__ import annotations
import math
import re
from datetime import date, timedelta
from services.currency_service import format_money, convert_from_inr
from services.routing_service import (
    geocode_place,
    calculate_route,
    get_google_maps_directions_url,
    format_duration,
    haversine_distance
)
from services.attractions_service import (
    get_attractions_for_destination,
    is_attraction_open_on_date,
    is_attraction_suitable_for_slot,
    is_same_attraction
)
from services.transport_service import compare_transportation_modes
from services.budget_service import calculate_comprehensive_budget
from services.weather_service import get_weather_for_destination


def parse_duration_minutes(dur_str: str) -> int:
    """Parses visit duration strings like '1.5 hours', '2 hours', '45 min' into integer minutes."""
    if not dur_str:
        return 120
    s = str(dur_str).lower().strip()
    m_hours = re.search(r"([\d.]+)\s*(?:hour|hr)", s)
    if m_hours:
        try:
            return max(30, int(float(m_hours.group(1)) * 60))
        except ValueError:
            pass
    m_mins = re.search(r"(\d+)\s*(?:min)", s)
    if m_mins:
        try:
            return max(30, int(m_mins.group(1)))
        except ValueError:
            pass
    return 120


def calculate_day_schedule(
    m_item: dict,
    a_item: dict,
    e_item: dict,
    route_m_to_a_mins: int = 15,
    route_a_to_e_mins: int = 15
) -> dict:
    """
    Computes realistic, duration-matched start and end times for morning, afternoon,
    and evening activities, accounting for travel times and meal breaks.
    """
    # 1. Morning start: default 09:00, or later if opening hours dictate
    m_hours = m_item.get("opening_hours", "")
    m_start_mins = 9 * 60
    match_start = re.search(r"^(\d{1,2}):(\d{2})", m_hours)
    if match_start:
        h, m = int(match_start.group(1)), int(match_start.group(2))
        if h * 60 + m > m_start_mins:
            m_start_mins = h * 60 + m

    m_dur_mins = min(parse_duration_minutes(m_item.get("visit_duration", "2 hours")), 180)
    m_end_mins = m_start_mins + m_dur_mins

    # 2. Travel to lunch & afternoon spot
    travel_1 = max(10, min(60, int(route_m_to_a_mins)))
    arrival_afternoon_mins = m_end_mins + travel_1

    # Meal break (45-60 min). Afternoon activity starts after meal or at earliest 12:30
    a_start_mins = max(arrival_afternoon_mins + 45, 12 * 60 + 30)
    a_hours = a_item.get("opening_hours", "")
    match_a_start = re.search(r"^(\d{1,2}):(\d{2})", a_hours)
    if match_a_start:
        ah, am = int(match_a_start.group(1)), int(match_a_start.group(2))
        if ah * 60 + am > a_start_mins:
            a_start_mins = ah * 60 + am

    a_dur_mins = min(parse_duration_minutes(a_item.get("visit_duration", "2 hours")), 180)
    a_end_mins = a_start_mins + a_dur_mins

    # 3. Afternoon to Evening travel & tea/rest gap
    travel_2 = max(10, min(60, int(route_a_to_e_mins)))
    arrival_evening_mins = a_end_mins + travel_2
    e_start_mins = max(arrival_evening_mins + 30, 16 * 60 + 30)

    e_hours = e_item.get("opening_hours", "")
    match_e_start = re.search(r"^(\d{1,2}):(\d{2})", e_hours)
    if match_e_start:
        eh, em = int(match_e_start.group(1)), int(match_e_start.group(2))
        if eh * 60 + em > e_start_mins:
            e_start_mins = eh * 60 + em

    e_dur_mins = min(parse_duration_minutes(e_item.get("visit_duration", "2 hours")), 180)
    e_end_mins = e_start_mins + e_dur_mins

    def fmt(mins: int) -> str:
        return f"{mins // 60:02d}:{mins % 60:02d}"

    def dur_label(dur_mins: int) -> str:
        if dur_mins % 60 == 0:
            hrs = dur_mins // 60
            return f"{hrs} hr" if hrs == 1 else f"{hrs} hrs"
        else:
            return f"{dur_mins / 60:.1f} hrs"

    return {
        "morning_time": f"{fmt(m_start_mins)} – {fmt(m_end_mins)}",
        "morning_duration": dur_label(m_dur_mins),
        "lunch_time": f"{fmt(arrival_afternoon_mins)} – {fmt(a_start_mins)}",
        "afternoon_time": f"{fmt(a_start_mins)} – {fmt(a_end_mins)}",
        "afternoon_duration": dur_label(a_dur_mins),
        "evening_time": f"{fmt(e_start_mins)} – {fmt(e_end_mins)}",
        "evening_duration": dur_label(e_dur_mins)
    }


def _generate_date_list(start_iso: str, end_iso: str) -> list[date]:
    first = date.fromisoformat(start_iso)
    last = date.fromisoformat(end_iso)
    if last < first:
        raise ValueError("Return date must be on or after departure date.")
    delta_days = (last - first).days
    if delta_days > 30:
        last = first + timedelta(days=30)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _cluster_by_proximity(attractions: list[dict]) -> list[dict]:
    """
    Groups attractions by region first, then by geographical proximity using nearest-neighbor clustering.
    Minimizes intra-city travel between consecutive attractions and keeps regional blocks cohesive.
    """
    if len(attractions) <= 2:
        return list(attractions)

    regions: dict[str, list[dict]] = {}
    for a in attractions:
        reg = a.get("region") or "default"
        regions.setdefault(reg, []).append(a)

    ordered_all = []
    for reg, reg_items in regions.items():
        with_coords = [a for a in reg_items if a.get("lat") and a.get("lon")]
        without_coords = [a for a in reg_items if not (a.get("lat") and a.get("lon"))]

        if not with_coords:
            ordered_all.extend(reg_items)
            continue

        ordered = [with_coords[0]]
        remaining = list(with_coords[1:])

        while remaining:
            curr = ordered[-1]
            c_lat, c_lon = curr["lat"], curr["lon"]
            best_idx = 0
            best_dist = float("inf")
            for idx, item in enumerate(remaining):
                dlat = item["lat"] - c_lat
                dlon = item["lon"] - c_lon
                dist = dlat * dlat + dlon * dlon
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            ordered.append(remaining.pop(best_idx))

        ordered_all.extend(ordered + without_coords)

    return ordered_all


def create_comprehensive_itinerary(
    start_location: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int,
    budget: float,
    budget_type: str = "total_group",
    currency: str = "INR",
    travel_preference: str = "standard",
    accommodation_preference: str = "budget_hotel",
    food_preference: str = "casual",
    interests: list[str] | None = None,
    transport_mode: str | None = None
) -> dict:
    """
    Main entry point for generating a complete, realistic, un-capped travel plan.
    """
    start_clean = str(start_location or "Home City").strip()
    dest_clean = str(destination or "").strip()

    if not dest_clean:
        raise ValueError("Please enter a travel destination.")

    travelers = int(travelers)
    if travelers < 1 or travelers > 30:
        raise ValueError("Number of travellers must be between 1 and 30.")

    budget = float(budget)
    if budget <= 0:
        raise ValueError("Budget must be greater than zero.")

    dates = _generate_date_list(start_date, end_date)
    num_days = len(dates)
    num_nights = max(0, num_days - 1)

    # 1. Geocoding & Distance from Starting Location to Destination
    start_coords = geocode_place(start_clean)
    dest_coords = geocode_place(dest_clean)

    if start_coords and dest_coords:
        intercity_route = calculate_route(start_coords, dest_coords, mode="driving")
        intercity_distance_km = intercity_route["distance_km"]
        intercity_duration_formatted = intercity_route["duration_formatted"]
        intercity_provider = intercity_route["provider"]
    else:
        intercity_distance_km = 450.0
        intercity_duration_formatted = "7 hrs"
        intercity_provider = "Estimated regional distance"

    # 2. Transportation Comparison (Flights, Trains, Buses, Cabs, Car)
    transport_comparison = compare_transportation_modes(
        start_location=start_clean,
        destination=dest_clean,
        travelers=travelers,
        currency=currency
    )

    # Ensure all transport options have currency-converted values, aliases, and explicit availability labels
    for opt in transport_comparison.get("options", []):
        opt["one_way_total"] = convert_from_inr(opt.get("one_way_total_inr", 0), currency)
        opt["return_total"] = convert_from_inr(opt.get("return_total_inr", 0), currency)
        opt["total_cost"] = opt["return_total"]
        opt["cost_per_person"] = convert_from_inr(opt.get("fare_per_person_inr", 0), currency)
        opt["return_cost_per_person"] = convert_from_inr(opt.get("return_fare_per_person_inr", 0), currency)
        opt["duration"] = opt.get("duration_formatted", "N/A")
        opt["pricing_type"] = opt.get("pricing_type", "per_person")
        opt["is_budget_basis"] = False
        if not opt.get("available"):
            opt["unavailable_reason"] = opt.get("details", "Not recommended or feasible for this distance.")

    # Select mode for budget inclusion:
    # 1. Match explicit transport_mode if requested
    # 2. Or match travel_preference:
    #    budget -> Buses (if available, else Trains)
    #    standard -> Trains (if available, else Buses)
    #    luxury -> Flights (if available, else Outstation Taxi)
    selected_transport = None
    options = transport_comparison.get("options", [])
    if transport_mode:
        t_clean = transport_mode.lower().strip()
        for opt in options:
            if opt["available"] and (t_clean in opt["mode"].lower() or opt["mode"].lower() in t_clean):
                selected_transport = opt
                break

    if not selected_transport:
        pref = travel_preference.lower()
        if pref == "budget":
            for m in ("Buses", "Trains", "Private Car"):
                match = next((o for o in options if o["available"] and o["mode"] == m), None)
                if match:
                    selected_transport = match
                    break
        elif pref == "luxury":
            for m in ("Flights", "Outstation Taxi", "Private Car"):
                match = next((o for o in options if o["available"] and o["mode"] == m), None)
                if match:
                    selected_transport = match
                    break
        else:  # standard
            for m in ("Trains", "Buses", "Private Car"):
                match = next((o for o in options if o["available"] and o["mode"] == m), None)
                if match:
                    selected_transport = match
                    break

    if not selected_transport and options:
        selected_transport = next((o for o in options if o["available"]), options[0])

    if selected_transport:
        selected_transport["is_budget_basis"] = True
        one_way_transport_cost_inr = selected_transport.get("one_way_total_inr", 1500 * travelers)
    else:
        one_way_transport_cost_inr = 1500 * travelers

    # 3. Real Tourist Attractions with Details & Categories
    attractions_pool, attraction_source = get_attractions_for_destination(dest_clean, interests)
    clustered_pool = _cluster_by_proximity(attractions_pool)

    # 4. Logical Day-by-Day Deduplicated & Proximity-Clustered Scheduling
    daily_itinerary = []
    total_sightseeing_fees_inr = 0
    scheduled_names: set[str] = set()
    scheduled_ids: set[str] = set()
    scheduled_attraction_items: list[dict] = []

    for day_idx, day_date in enumerate(dates):
        # Attractions not yet scheduled (checking canonical ID, exact name, aliases, and physical proximity)
        def is_cand_dup(c: dict) -> bool:
            cid = c.get("id")
            if cid and cid in scheduled_ids:
                return True
            cname = c.get("name", "").strip().lower()
            if cname in scheduled_names:
                return True
            for prev in scheduled_attraction_items:
                if is_same_attraction(c, prev):
                    return True
            return False

        remaining = [a for a in clustered_pool if not is_cand_dup(a)]

        # Filter remaining attractions that are open on this calendar date
        open_today = [a for a in remaining if is_attraction_open_on_date(a, day_date)[0]]

        if len(open_today) >= 3:
            # 1. Pick morning candidate suitable for morning
            m_candidates = [a for a in open_today if is_attraction_suitable_for_slot(a, "morning", day_date)[0]]
            m_item = m_candidates[0] if m_candidates else open_today[0]
            day_region = m_item.get("region")

            # 2. Pick afternoon candidate: prioritize same region or nearby (< 45 km)
            rest_open_a = [
                a for a in open_today 
                if a.get("id") != m_item.get("id") 
                and a["name"] != m_item["name"] 
                and not is_same_attraction(a, m_item)
            ]
            if day_region:
                same_reg_a = [a for a in rest_open_a if a.get("region") == day_region]
                if same_reg_a:
                    rest_open_a = same_reg_a
                elif m_item.get("lat"):
                    # Only allow attractions within 80 km (day-trip proximity)
                    rest_open_a = [
                        a for a in rest_open_a
                        if not a.get("lat") or haversine_distance(m_item["lat"], m_item["lon"], a["lat"], a["lon"]) <= 80
                    ]

            a_candidates = [a for a in rest_open_a if is_attraction_suitable_for_slot(a, "afternoon", day_date)[0]]
            if not a_candidates:
                a_candidates = rest_open_a

            def dist_to_m(item):
                if m_item.get("lat") and item.get("lat"):
                    dlat = item["lat"] - m_item["lat"]
                    dlon = item["lon"] - m_item["lon"]
                    return dlat * dlat + dlon * dlon
                return 999.0

            # Filter candidates to ensure geographic proximity (< 80 km)
            if m_item.get("lat"):
                a_candidates = [
                    a for a in a_candidates
                    if not a.get("lat") or haversine_distance(m_item["lat"], m_item["lon"], a["lat"], a["lon"]) <= 80
                ]

            if a_candidates:
                a_candidates.sort(key=dist_to_m)
                a_item = a_candidates[0]
            else:
                a_item = {
                    "is_leisure": True,
                    "id": f"leisure_day_{day_idx + 1}_a",
                    "name": f"{day_region.title() if day_region else dest_clean} Local Crafts & Street Food Discovery (Day {day_idx + 1})",
                    "desc": f"Explore regional craft shops, spice markets, and authentic local food stalls in {day_region.title() if day_region else dest_clean}.",
                    "category": "Leisure",
                    "opening_hours": "Flexible",
                    "visit_duration": "2 hours",
                    "entry_fee_inr": 0,
                    "food_nearby": f"Traditional eateries and street food stalls in {dest_clean}",
                    "lat": m_item.get("lat"),
                    "lon": m_item.get("lon"),
                    "travel_mode": "walking"
                }

            # 3. Pick evening candidate: prioritize same region or nearby (< 80 km)
            rest_open_e = [
                a for a in rest_open_a 
                if a.get("id") != a_item.get("id") 
                and a["name"] != a_item["name"] 
                and not is_same_attraction(a, a_item)
            ]
            if day_region:
                same_reg_e = [a for a in rest_open_e if a.get("region") == day_region]
                if same_reg_e:
                    rest_open_e = same_reg_e
                elif m_item.get("lat"):
                    rest_open_e = [
                        a for a in rest_open_e
                        if not a.get("lat") or haversine_distance(m_item["lat"], m_item["lon"], a["lat"], a["lon"]) <= 80
                    ]

            e_candidates = [a for a in rest_open_e if is_attraction_suitable_for_slot(a, "evening", day_date)[0]]
            if not e_candidates:
                e_candidates = rest_open_e

            def dist_to_a(item):
                ref = a_item if a_item.get("lat") else m_item
                if ref.get("lat") and item.get("lat"):
                    dlat = item["lat"] - ref["lat"]
                    dlon = item["lon"] - ref["lon"]
                    return dlat * dlat + dlon * dlon
                return 999.0

            ref_point = a_item if a_item.get("lat") else m_item
            if ref_point.get("lat"):
                e_candidates = [
                    a for a in e_candidates
                    if not a.get("lat") or haversine_distance(ref_point["lat"], ref_point["lon"], a["lat"], a["lon"]) <= 80
                ]

            if e_candidates:
                e_candidates.sort(key=dist_to_a)
                e_item = e_candidates[0]
            else:
                e_item = {
                    "is_leisure": True,
                    "id": f"leisure_day_{day_idx + 1}_e",
                    "name": f"{day_region.title() if day_region else dest_clean} Sunset Promenade & Leisure Dining (Day {day_idx + 1})",
                    "desc": f"Enjoy sunset views and a relaxed dinner at an authentic restaurant in {day_region.title() if day_region else dest_clean}.",
                    "category": "Leisure",
                    "opening_hours": "Flexible",
                    "visit_duration": "2 hours",
                    "entry_fee_inr": 0,
                    "food_nearby": f"Sunset view lounge and local dinner diner",
                    "lat": m_item.get("lat"),
                    "lon": m_item.get("lon"),
                    "travel_mode": "walking"
                }

            slot_items = [m_item, a_item, e_item]
            is_rest_day = False
            rest_day_note = ""

        elif 1 <= len(open_today) < 3:
            m_item = open_today[0]
            day_region = m_item.get("region")
            rest_same = [a for a in open_today[1:] if not day_region or a.get("region") == day_region]

            if rest_same:
                a_item = rest_same[0]
            else:
                a_item = {
                    "is_leisure": True,
                    "id": f"leisure_day_{day_idx + 1}_a",
                    "name": f"{day_region.title() if day_region else dest_clean} Cultural Artisans & Bazaars (Day {day_idx + 1})",
                    "desc": f"Explore regional craft shops, spice stalls, and authentic handicraft emporiums in {day_region.title() if day_region else dest_clean}.",
                    "category": "Leisure",
                    "opening_hours": "Flexible",
                    "visit_duration": "2 hours",
                    "entry_fee_inr": 0,
                    "food_nearby": f"Traditional tea houses and regional snacks in {dest_clean}",
                    "lat": m_item.get("lat"),
                    "lon": m_item.get("lon"),
                    "travel_mode": "walking"
                }

            e_item = {
                "is_leisure": True,
                "id": f"leisure_day_{day_idx + 1}_e",
                "name": f"{day_region.title() if day_region else dest_clean} Scenic Promenade & Sunset Vista (Day {day_idx + 1})",
                "desc": f"Unwind along the scenic waterfront, city promenade, or panoramic viewpoint at golden hour.",
                "category": "Leisure",
                "opening_hours": "Flexible",
                "visit_duration": "2 hours",
                "entry_fee_inr": 0,
                "food_nearby": f"Sunset view lounge and local dinner spot",
                "lat": m_item.get("lat"),
                "lon": m_item.get("lon"),
                "travel_mode": "walking"
            }
            slot_items = [m_item, a_item, e_item]
            is_rest_day = False
            rest_day_note = f"Primary attractions open on this day in {dest_clean} are complemented with local cultural leisure experiences."

        else:
            # Pool exhausted or no remaining attractions open on this day:
            # Dedicated Rest / Leisure / Personal Exploration day
            is_rest_day = True
            rest_day_note = (
                f"All {len(scheduled_attraction_items)} verified primary tourist attractions for {dest_clean} have been scheduled in earlier days. "
                f"Day {day_idx + 1} is reserved for leisure, revisiting personal favorites, local cafe hopping, or an optional nearby excursion."
            )
            m_item = {
                "is_leisure": True,
                "id": f"leisure_day_{day_idx + 1}_m",
                "name": f"{dest_clean} Leisurely Breakfast & Heritage Walk (Day {day_idx + 1})",
                "desc": f"Enjoy a relaxed morning exploring hidden alleys, historic cafes, and local bakeries in {dest_clean}.",
                "category": "Leisure",
                "opening_hours": "Flexible",
                "visit_duration": "2 hours",
                "entry_fee_inr": 0,
                "food_nearby": f"Iconic morning tiffin and artisan coffee roasters",
                "lat": None, "lon": None,
                "travel_mode": "walking"
            }
            a_item = {
                "is_leisure": True,
                "id": f"leisure_day_{day_idx + 1}_a",
                "name": f"{dest_clean} Regional Markets & Souvenir Discovery (Day {day_idx + 1})",
                "desc": f"Spend the afternoon discovering authentic regional spices, textiles, and handcrafted gifts at local bazaars.",
                "category": "Leisure",
                "opening_hours": "Flexible",
                "visit_duration": "2 hours",
                "entry_fee_inr": 0,
                "food_nearby": f"Historic local lunch thali or regional diner",
                "lat": None, "lon": None,
                "travel_mode": "walking"
            }
            e_item = {
                "is_leisure": True,
                "id": f"leisure_day_{day_idx + 1}_e",
                "name": f"{dest_clean} Sunset Promenade & Special Dinner (Day {day_idx + 1})",
                "desc": f"Celebrate your trip with panoramic twilight views followed by an authentic regional dining experience.",
                "category": "Leisure",
                "opening_hours": "Flexible",
                "visit_duration": "2 hours",
                "entry_fee_inr": 0,
                "food_nearby": f"Celebrated local heritage restaurant",
                "lat": None, "lon": None,
                "travel_mode": "walking"
            }
            slot_items = [m_item, a_item, e_item]

        # Record scheduled items
        for item in slot_items:
            scheduled_names.add(item["name"].strip().lower())
            if item.get("id"):
                scheduled_ids.add(item["id"])
            if not item.get("is_leisure", False):
                scheduled_attraction_items.append(item)

        m_coords = (m_item.get("lat"), m_item.get("lon")) if m_item.get("lat") else None
        a_coords = (a_item.get("lat"), a_item.get("lon")) if a_item.get("lat") else None
        e_coords = (e_item.get("lat"), e_item.get("lon")) if e_item.get("lat") else None

        # Determine travel modes (boat / ferry vs driving)
        mode_m_to_a = "ferry" if (m_item.get("travel_mode") == "ferry" or a_item.get("travel_mode") == "ferry") else ("boat" if (m_item.get("travel_mode") == "boat" or a_item.get("travel_mode") == "boat") else "driving")
        mode_a_to_e = "ferry" if (a_item.get("travel_mode") == "ferry" or e_item.get("travel_mode") == "ferry") else ("boat" if (a_item.get("travel_mode") == "boat" or e_item.get("travel_mode") == "boat") else "driving")

        if m_coords and a_coords:
            route_m_to_a = calculate_route(m_coords, a_coords, mode=mode_m_to_a)
        else:
            route_m_to_a = {
                "distance_km": 3.8,
                "duration_minutes": 15,
                "duration_formatted": "15 min",
                "mode": mode_m_to_a,
                "is_estimate": True,
                "provider": "Estimated local transfer"
            }

        if a_coords and e_coords:
            route_a_to_e = calculate_route(a_coords, e_coords, mode=mode_a_to_e)
        else:
            route_a_to_e = {
                "distance_km": 3.2,
                "duration_minutes": 12,
                "duration_formatted": "12 min",
                "mode": mode_a_to_e,
                "is_estimate": True,
                "provider": "Estimated local transfer"
            }

        suggested_lunch = a_item.get("food_nearby", f"Local cafe and lunch diner near {a_item['name']}")
        suggested_rest = (
            "Afternoon tea & rest break at a shaded cafe or hotel lounge (14:30 - 15:30) to avoid peak heat."
            if day_idx % 2 == 0 else
            "Midday relaxation and photo break before proceeding to afternoon activities."
        )

        m_fee_inr = m_item.get("entry_fee_inr", 0) * travelers
        a_fee_inr = a_item.get("entry_fee_inr", 0) * travelers
        e_fee_inr = e_item.get("entry_fee_inr", 0) * travelers
        day_entrance_inr = m_fee_inr + a_fee_inr + e_fee_inr
        total_sightseeing_fees_inr += day_entrance_inr

        # Calculate exact duration-matched schedule for this day
        day_sched = calculate_day_schedule(
            m_item, a_item, e_item,
            route_m_to_a_mins=route_m_to_a.get("duration_minutes", 15),
            route_a_to_e_mins=route_a_to_e.get("duration_minutes", 12)
        )

        def build_activity_slot(item, time_range):
            fee_inr = item.get("entry_fee_inr", 0)
            is_leis = item.get("is_leisure", False)
            cat = "Leisure" if is_leis else item.get("category", "historical").title()
            maps_url = "" if is_leis else get_google_maps_directions_url(dest_clean, item.get("name"))
            return {
                "id": item.get("id"),
                "time": time_range,
                "name": item.get("name"),
                "description": item.get("desc"),
                "category": cat,
                "is_leisure": is_leis,
                "region": item.get("region"),
                "travel_mode": item.get("travel_mode", "road"),
                "opening_hours": item.get("opening_hours", "09:00 - 18:00"),
                "visit_duration": item.get("visit_duration", "2 hours"),
                "entry_fee_per_person": convert_from_inr(fee_inr, currency),
                "entry_fee_total": convert_from_inr(fee_inr * travelers, currency),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "google_maps_url": maps_url,
                "food_nearby": item.get("food_nearby", "")
            }

        daily_itinerary.append({
            "day_number": day_idx + 1,
            "date": day_date.isoformat(),
            "date_formatted": day_date.strftime("%a, %d %b %Y"),
            "is_rest_day": is_rest_day,
            "rest_day_note": rest_day_note,
            "schedule": day_sched,
            "morning": build_activity_slot(m_item, day_sched["morning_time"]),
            "route_morning_to_afternoon": {
                "distance_km": route_m_to_a["distance_km"],
                "duration_formatted": route_m_to_a["duration_formatted"],
                "mode": route_m_to_a.get("mode", "driving"),
                "provider": route_m_to_a.get("provider", "Estimated transfer"),
                "from_name": m_item.get("name"),
                "to_name": a_item.get("name"),
                "maps_directions_url": get_google_maps_directions_url(m_item.get("name"), a_item.get("name"))
            },
            "lunch_break": day_sched["lunch_time"],
            "afternoon": build_activity_slot(a_item, day_sched["afternoon_time"]),
            "suggested_food_stop": suggested_lunch,
            "suggested_rest_period": suggested_rest,
            "route_afternoon_to_evening": {
                "distance_km": route_a_to_e["distance_km"],
                "duration_formatted": route_a_to_e["duration_formatted"],
                "mode": route_a_to_e.get("mode", "driving"),
                "provider": route_a_to_e.get("provider", "Estimated transfer"),
                "from_name": a_item.get("name"),
                "to_name": e_item.get("name"),
                "maps_directions_url": get_google_maps_directions_url(a_item.get("name"), e_item.get("name"))
            },
            "evening": build_activity_slot(e_item, day_sched["evening_time"]),
            "day_total_route_km": round(route_m_to_a["distance_km"] + route_a_to_e["distance_km"], 1)
        })

    # 5. Accurate Travel Budget Calculation (Independent & Reconciled)
    budget_analysis = calculate_comprehensive_budget(
        start_location=start_clean,
        destination=dest_clean,
        num_days=num_days,
        num_nights=num_nights,
        travelers=travelers,
        travel_preference=travel_preference,
        accommodation_preference=accommodation_preference,
        food_preference=food_preference,
        budget_input=budget,
        budget_type=budget_type,
        currency=currency,
        attractions_list=scheduled_attraction_items or attractions_pool,
        intercity_one_way_cost_inr=one_way_transport_cost_inr,
        distance_km=intercity_distance_km,
        selected_transport_option=selected_transport
    )

    # 6. Live Weather Information & Packing Advice
    weather_info = get_weather_for_destination(
        destination=dest_clean,
        start_date=start_date,
        end_date=end_date
    )

    # Build unique summary of genuine attractions only (excluding leisure blocks)
    seen_summary = set()
    unique_attractions_summary = []
    for a in scheduled_attraction_items:
        if a.get("is_leisure", False):
            continue
        cid = a.get("id") or a["name"].lower()
        if a.get("lat") and a.get("lon") and cid not in seen_summary:
            seen_summary.add(cid)
            unique_attractions_summary.append({
                "id": a.get("id", cid),
                "name": a["name"],
                "category": a.get("category", "historical"),
                "region": a.get("region", dest_clean.lower()),
                "travel_mode": a.get("travel_mode", "road"),
                "lat": a.get("lat"),
                "lon": a.get("lon"),
                "description": a.get("desc", ""),
                "entry_fee_inr": a.get("entry_fee_inr", 0)
            })

    if not unique_attractions_summary:
        for a in attractions_pool:
            if not a.get("is_leisure", False) and a.get("lat") and a.get("lon") and a["name"] not in seen_summary:
                seen_summary.add(a["name"])
                unique_attractions_summary.append({
                    "id": a.get("id"),
                    "name": a["name"],
                    "category": a.get("category", "historical"),
                    "region": a.get("region", dest_clean.lower()),
                    "travel_mode": a.get("travel_mode", "road"),
                    "lat": a.get("lat"),
                    "lon": a.get("lon"),
                    "description": a.get("desc", ""),
                    "entry_fee_inr": a.get("entry_fee_inr", 0)
                })

    return {
        "destination": dest_clean,
        "start_location": start_clean,
        "start_date": start_date,
        "end_date": end_date,
        "num_days": num_days,
        "num_nights": num_nights,
        "travelers": travelers,
        "currency": currency,
        "budget_type": budget_type,
        "travel_preference": travel_preference,
        "accommodation_preference": accommodation_preference,
        "food_preference": food_preference,
        "interests": interests or [],
        # Starting Location -> Destination Distance
        "intercity_travel": {
            "origin": start_clean,
            "destination": dest_clean,
            "distance_km": intercity_distance_km,
            "estimated_duration": intercity_duration_formatted,
            "provider": intercity_provider,
            "directions_url": get_google_maps_directions_url(start_clean, dest_clean)
        },
        # Transportation Comparison
        "transportation_comparison": transport_comparison,
        # Day-by-Day Itinerary with routes and food stops
        "itinerary": daily_itinerary,
        # Attractions summary for maps
        "attractions_summary": unique_attractions_summary,
        "unique_attractions_count": len(unique_attractions_summary),
        "attraction_source": attraction_source,
        # Budget Analysis
        "budget_analysis": budget_analysis,
        # Weather Information
        "weather": weather_info,
        # General Notes & Disclaimers
        "notes": [
            "All expenses are calculated independently based on actual trip length, travellers and activities.",
            "Weather forecasts are real-time via Open-Meteo API.",
            "Click on any 'Directions' link to open Google Maps on your mobile or desktop."
        ]
    }


# Backwards compatibility alias
def create_itinerary(
    destination,
    start_date,
    end_date,
    budget,
    interests,
    travelers,
    currency="INR"
):
    return create_comprehensive_itinerary(
        start_location="Home City",
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        travelers=travelers,
        budget=budget,
        budget_type="total_group",
        currency=currency,
        travel_preference="standard",
        accommodation_preference="budget_hotel",
        food_preference="casual",
        interests=interests
    )
