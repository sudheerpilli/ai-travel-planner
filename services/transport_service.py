"""
Transportation Comparison Service for TripWise.
Compares Flights, Trains, Buses, Outstation Cabs, and Private Car between Origin and Destination.
"""

from __future__ import annotations
from urllib.parse import quote
from services.routing_service import geocode_place, calculate_route, haversine_distance, format_duration


def compare_transportation_modes(
    start_location: str,
    destination: str,
    travelers: int,
    currency: str = "INR"
) -> dict:
    """
    Returns a comprehensive transportation comparison:
    options: list of 5 modes with distance, duration, costs, booking links, and highlight badges
    """
    travelers = max(1, int(travelers))
    start_clean = start_location.strip()
    dest_clean = destination.strip()

    # Geocode both points
    start_coords = geocode_place(start_clean)
    dest_coords = geocode_place(dest_clean)

    if start_coords and dest_coords:
        route_info = calculate_route(start_coords, dest_coords, mode="driving")
        road_distance_km = route_info["distance_km"]
        road_driving_mins = route_info["duration_minutes"]
        air_distance_km = round(haversine_distance(start_coords[0], start_coords[1], dest_coords[0], dest_coords[1]), 1)
    else:
        # Fallback approximate distance
        road_distance_km = 650.0
        road_driving_mins = 600
        air_distance_km = 520.0

    # 1. Flights
    # Flight takes ~1h 15m min + 2h airport buffer; available practically if distance > 180 km
    has_commercial_flight = road_distance_km >= 180
    if has_commercial_flight:
        flight_air_mins = max(45, round((air_distance_km / 750.0) * 60))
        flight_total_mins = flight_air_mins + 120  # +2h check-in/security/boarding
        # Base fare estimation model: base ₹2500 + ~₹4.2 per km
        flight_fare_per_person = round(2500 + (air_distance_km * 4.2))
        flight_total_cost = flight_fare_per_person * travelers
        flight_return_cost = flight_total_cost * 2
        flight_return_per_person = flight_fare_per_person * 2
        flight_booking_url = f"https://www.google.com/travel/flights?q=flights+from+{quote(start_clean)}+to+{quote(dest_clean)}"
        flight_option = {
            "mode": "Flights",
            "icon": "✈️",
            "available": True,
            "pricing_type": "per_person",
            "distance_km": air_distance_km,
            "duration_formatted": format_duration(flight_total_mins),
            "duration_minutes": flight_total_mins,
            "fare_per_person_inr": flight_fare_per_person,
            "return_fare_per_person_inr": flight_return_per_person,
            "one_way_total_inr": flight_total_cost,
            "return_total_inr": flight_return_cost,
            "cost_per_person_inr": flight_fare_per_person,
            "details": f"Air travel (~{format_duration(flight_air_mins)} flight time + airport check-in).",
            "booking_link": flight_booking_url,
            "booking_provider": "Google Flights / Airline Aggregators",
            "notes": f"Direct or 1-stop schedule. Baggage allowances apply. Pricing is per person (₹{flight_fare_per_person:,} one-way × {travelers} travellers)."
        }
    else:
        flight_option = {
            "mode": "Flights",
            "icon": "✈️",
            "available": False,
            "pricing_type": "per_person",
            "distance_km": air_distance_km,
            "duration_formatted": "N/A",
            "duration_minutes": 99999,
            "fare_per_person_inr": 0,
            "return_fare_per_person_inr": 0,
            "one_way_total_inr": 0,
            "return_total_inr": 0,
            "cost_per_person_inr": 0,
            "details": "Direct commercial flights are not practical for trips under 180 km. Road or rail is recommended.",
            "booking_link": "",
            "booking_provider": "N/A",
            "notes": "Distance too short for scheduled air routes."
        }

    # 2. Trains
    # Rail speed averages ~60 km/h with station stops
    train_mins = max(60, round((road_distance_km / 58.0) * 60))
    # Sleeper/3AC mix: ~₹1.45 per km + ₹150 reservation
    train_fare_per_person = round(max(200, 150 + (road_distance_km * 1.45)))
    train_total_cost = train_fare_per_person * travelers
    train_return_cost = train_total_cost * 2
    train_return_per_person = train_fare_per_person * 2
    train_booking_url = f"https://www.irctc.co.in/nget/train-search"
    train_option = {
        "mode": "Trains",
        "icon": "🚆",
        "available": True,
        "pricing_type": "per_person",
        "distance_km": round(road_distance_km * 1.05, 1),
        "duration_formatted": format_duration(train_mins),
        "duration_minutes": train_mins,
        "fare_per_person_inr": train_fare_per_person,
        "return_fare_per_person_inr": train_return_per_person,
        "one_way_total_inr": train_total_cost,
        "return_total_inr": train_return_cost,
        "cost_per_person_inr": train_fare_per_person,
        "details": f"Express/Superfast train service (AC 3-Tier / Chair Car estimate).",
        "booking_link": train_booking_url,
        "booking_provider": "IRCTC / Indian Railways",
        "notes": f"Comfortable, scenic and economical. Pricing is per person (₹{train_fare_per_person:,} one-way × {travelers} travellers)."
    }

    # 3. Intercity Buses (Volvo / AC Sleeper)
    bus_mins = max(60, round(road_driving_mins * 1.25))
    bus_fare_per_person = round(max(250, 180 + (road_distance_km * 1.85)))
    bus_total_cost = bus_fare_per_person * travelers
    bus_return_cost = bus_total_cost * 2
    bus_return_per_person = bus_fare_per_person * 2
    bus_booking_url = f"https://www.redbus.in/bus-tickets/{quote(start_clean)}-to-{quote(dest_clean)}"
    bus_option = {
        "mode": "Buses",
        "icon": "🚌",
        "available": True,
        "pricing_type": "per_person",
        "distance_km": road_distance_km,
        "duration_formatted": format_duration(bus_mins),
        "duration_minutes": bus_mins,
        "fare_per_person_inr": bus_fare_per_person,
        "return_fare_per_person_inr": bus_return_per_person,
        "one_way_total_inr": bus_total_cost,
        "return_total_inr": bus_return_cost,
        "cost_per_person_inr": bus_fare_per_person,
        "details": "AC Multi-Axle / Sleeper intercity bus with frequent departures.",
        "booking_link": bus_booking_url,
        "booking_provider": "redBus / State RTCs",
        "notes": f"Overnight journeys available. Pricing is per person (₹{bus_fare_per_person:,} one-way × {travelers} travellers)."
    }

    # 4. Outstation Cab / Taxi
    # Sedan or SUV outstation cab (~₹14/km for sedan, ₹18 for SUV + ₹400 driver daily batta/allowance)
    # Return pricing model: Unlike per-seat tickets (2.0x), Indian commercial cab aggregators (MakeMyTrip, Savaari)
    # price round-trip packages at ~1.85x one-way tariff because passenger occupies vehicle both ways (no empty deadheading).
    cab_rate_per_km = 14.0 if travelers <= 4 else 18.0
    cab_vehicle_type = "Sedan (up to 4 seats)" if travelers <= 4 else "Innova/SUV (up to 6-7 seats)"
    cab_fuel_fare = round(road_distance_km * cab_rate_per_km)
    cab_tolls = round(road_distance_km * 1.2)
    cab_driver_batta = 400
    cab_total_one_way = cab_fuel_fare + cab_tolls + cab_driver_batta
    cab_return_cost = round(cab_total_one_way * 1.85)  # Round-trip commercial package (15% discount; avoids empty deadhead)
    cab_per_person_one_way = round(cab_total_one_way / travelers)
    cab_per_person_return = round(cab_return_cost / travelers)
    cab_booking_url = f"https://www.makemytrip.com/cabs/"
    cab_option = {
        "mode": "Outstation Taxi",
        "icon": "🚕",
        "available": True,
        "pricing_type": "per_vehicle",
        "vehicle_type": cab_vehicle_type,
        "distance_km": road_distance_km,
        "duration_formatted": format_duration(road_driving_mins),
        "duration_minutes": road_driving_mins,
        "fare_per_person_inr": cab_per_person_one_way,
        "return_fare_per_person_inr": cab_per_person_return,
        "one_way_total_inr": cab_total_one_way,
        "return_total_inr": cab_return_cost,
        "cost_per_person_inr": cab_per_person_one_way,
        "tolls_included_inr": cab_tolls,
        "driver_allowance_inr": cab_driver_batta,
        "details": f"Private door-to-door chauffeur-driven {cab_vehicle_type}.",
        "booking_link": cab_booking_url,
        "booking_provider": "MakeMyTrip Cabs / Savaari",
        "notes": (
            f"Whole vehicle hire ({cab_vehicle_type}). Includes fuel (₹{cab_fuel_fare:,}), tolls (₹{cab_tolls:,}), "
            f"and driver allowance (₹{cab_driver_batta:,}). Round-trip features standard 1.85x package pricing "
            f"(15% discount over separate one-way drops by eliminating return deadhead surcharges)."
        )
    }

    # 5. Private Car / Self-Drive
    # Whole-vehicle private car fuel (14.5 km/l @ ₹102/litre) + highway tolls (₹1.2/km)
    fuel_cost = round((road_distance_km / 14.5) * 102)
    tolls_cost = round(road_distance_km * 1.2)
    car_one_way = fuel_cost + tolls_cost
    car_return = car_one_way * 2
    car_per_person_one_way = round(car_one_way / travelers)
    car_per_person_return = round(car_return / travelers)
    car_option = {
        "mode": "Private Car",
        "icon": "🚗",
        "available": True,
        "pricing_type": "per_vehicle",
        "vehicle_type": "Self-Drive Car (Group)",
        "distance_km": road_distance_km,
        "duration_formatted": format_duration(road_driving_mins),
        "duration_minutes": road_driving_mins,
        "fare_per_person_inr": car_per_person_one_way,
        "return_fare_per_person_inr": car_per_person_return,
        "one_way_total_inr": car_one_way,
        "return_total_inr": car_return,
        "cost_per_person_inr": car_per_person_one_way,
        "tolls_included_inr": tolls_cost,
        "details": f"Estimated fuel (₹{fuel_cost:,}) + highway tolls (₹{tolls_cost:,}) based on petrol @ ₹102/L.",
        "booking_link": f"https://www.google.com/maps/dir/?api=1&origin={quote(start_clean)}&destination={quote(dest_clean)}",
        "booking_provider": "Google Maps Navigation",
        "notes": (
            f"Whole vehicle cost (fuel + highway tolls for both legs). "
            f"Cost is shared among all {travelers} travellers (₹{car_per_person_one_way:,}/person one-way, ₹{car_per_person_return:,}/person return)."
        )
    }

    options = [flight_option, train_option, bus_option, cab_option, car_option]
    available_options = [o for o in options if o["available"]]

    # Identify Cheapest, Fastest, Best Balance
    if available_options:
        cheapest = min(available_options, key=lambda x: x["one_way_total_inr"])
        fastest = min(available_options, key=lambda x: x["duration_minutes"])

        # Best balance: lowest score of (norm_cost + norm_duration)
        min_cost = min(o["one_way_total_inr"] for o in available_options)
        max_cost = max(o["one_way_total_inr"] for o in available_options) or 1
        min_dur = min(o["duration_minutes"] for o in available_options)
        max_dur = max(o["duration_minutes"] for o in available_options) or 1

        def balance_score(o):
            cost_norm = (o["one_way_total_inr"] - min_cost) / (max_cost - min_cost + 1e-5)
            dur_norm = (o["duration_minutes"] - min_dur) / (max_dur - min_dur + 1e-5)
            return cost_norm * 0.5 + dur_norm * 0.5

        best_balance = min(available_options, key=balance_score)

        for o in options:
            tags = []
            if o is cheapest:
                tags.append("Cheapest Option")
            if o is fastest:
                tags.append("Fastest Option")
            if o is best_balance and o is not cheapest and o is not fastest:
                tags.append("Best Balance (Time & Price)")
            o["badges"] = tags

    return {
        "start_location": start_clean,
        "destination": dest_clean,
        "road_distance_km": road_distance_km,
        "air_distance_km": air_distance_km,
        "travelers": travelers,
        "options": options
    }

