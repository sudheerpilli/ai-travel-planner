"""
Accurate Travel Budget Calculator for TripWise.
Calculates realistic trip costs independently of user budget, distinguishing per-person and group expenses.
"""

from __future__ import annotations
import math
from services.currency_service import convert_from_inr, convert_to_inr, format_money

# Configurable standard daily rates in INR
ACCOMMODATION_RATES_PER_ROOM_NIGHT = {
    "hostel": 800,           # per bed/dorm room
    "budget_hotel": 2000,    # standard budget hotel / guesthouse
    "standard_hotel": 4200,  # 3-star comfortable hotel
    "luxury_resort": 9500    # 4/5-star luxury resort
}

FOOD_RATES_PER_PERSON_DAY = {
    "street_food": 450,      # budget local street food, thalis, local tea stalls
    "casual": 900,           # standard cafes, family restaurants, multi-cuisine
    "fine_dining": 2200      # upscale dining, beachfront bistros, specialty bars
}

LOCAL_TRANSPORT_RATES_PER_PERSON_DAY = {
    "budget": 250,           # metro, public buses, shared autos
    "standard": 550,         # app cabs (Uber/Ola/auto), rented scooters
    "luxury": 1400           # dedicated private chauffeur AC car rental
}

TRAVELERS_PER_ROOM = 2  # standard double-occupancy room sharing


def calculate_comprehensive_budget(
    start_location: str,
    destination: str,
    num_days: int,
    num_nights: int,
    travelers: int,
    travel_preference: str = "standard",
    accommodation_preference: str = "budget_hotel",
    food_preference: str = "casual",
    budget_input: float = 25000.0,
    budget_type: str = "total_group",  # 'per_person' or 'total_group'
    currency: str = "INR",
    attractions_list: list[dict] | None = None,
    intercity_one_way_cost_inr: float | None = None,
    intercity_return_cost_inr: float | None = None,
    distance_km: float = 500.0,
    selected_transport_option: dict | None = None
) -> dict:
    """
    Calculates transparent, realistic trip expenses in INR, then converts to target currency.
    Reconciles mathematically without capping.
    """
    num_days = max(1, int(num_days))
    num_nights = max(0, int(num_nights))
    travelers = max(1, int(travelers))
    budget_input = max(1.0, float(budget_input))

    # Room calculation: hostels are per-person, hotels are per room (standard 2 sharing)
    if accommodation_preference == "hostel":
        rooms_needed = travelers
        room_label = f"{travelers} dorm bed(s)"
    else:
        rooms_needed = math.ceil(travelers / TRAVELERS_PER_ROOM)
        room_label = f"{rooms_needed} room(s) (sharing {TRAVELERS_PER_ROOM}/room)"

    nightly_rate = ACCOMMODATION_RATES_PER_ROOM_NIGHT.get(
        accommodation_preference, ACCOMMODATION_RATES_PER_ROOM_NIGHT["budget_hotel"]
    )
    # If 1-day trip (0 nights), accommodation is 0
    total_accommodation_inr = nightly_rate * rooms_needed * num_nights
    accommodation_basis = (
        f"{room_label} × ₹{nightly_rate:,}/night × {num_nights} night(s)"
        if num_nights > 0 else "Day trip (0 nights accommodation)"
    )

    # Food calculation
    daily_food_rate = FOOD_RATES_PER_PERSON_DAY.get(food_preference, FOOD_RATES_PER_PERSON_DAY["casual"])
    total_food_inr = daily_food_rate * travelers * num_days
    food_basis = f"₹{daily_food_rate:,}/person/day × {travelers} traveller(s) × {num_days} day(s)"

    # Intercity transportation (strictly adopts the selected transport option's cost)
    if selected_transport_option:
        selected_mode = selected_transport_option.get("mode", "Transit")
        selected_icon = selected_transport_option.get("icon", "🚆")
        outbound_transport_inr = round(selected_transport_option.get("one_way_total_inr", 0))
        return_transport_inr = round(selected_transport_option.get("return_total_inr", 0))
        total_intercity_transport_inr = return_transport_inr
        intercity_basis = (
            f"{selected_mode} round-trip for {travelers} traveller(s) "
            f"(One-way: ₹{outbound_transport_inr:,}, Round-trip: ₹{return_transport_inr:,})"
        )
    elif intercity_return_cost_inr is not None and intercity_return_cost_inr > 0:
        selected_mode = "Transit"
        selected_icon = "🚆"
        return_transport_inr = round(intercity_return_cost_inr)
        outbound_transport_inr = round(intercity_one_way_cost_inr) if intercity_one_way_cost_inr else round(return_transport_inr / 2)
        total_intercity_transport_inr = return_transport_inr
        intercity_basis = (
            f"Outbound: ₹{outbound_transport_inr:,} + Return: ₹{return_transport_inr - outbound_transport_inr:,} "
            f"(Total Round-Trip: ₹{return_transport_inr:,} for {travelers} traveller(s))"
        )
    elif intercity_one_way_cost_inr is not None and intercity_one_way_cost_inr > 0:
        selected_mode = "Transit"
        selected_icon = "🚆"
        outbound_transport_inr = round(intercity_one_way_cost_inr)
        return_transport_inr = outbound_transport_inr * 2
        total_intercity_transport_inr = return_transport_inr
        intercity_basis = (
            f"Outbound: ₹{outbound_transport_inr:,} + Return: ₹{outbound_transport_inr:,} "
            f"(for {travelers} traveller(s) across ~{round(distance_km)} km)"
        )
    else:
        selected_mode = "Transit"
        selected_icon = "🚆"
        outbound_transport_inr = round(max(300, distance_km * 1.8) * travelers)
        return_transport_inr = outbound_transport_inr * 2
        total_intercity_transport_inr = return_transport_inr
        intercity_basis = (
            f"Outbound: ₹{outbound_transport_inr:,} + Return: ₹{outbound_transport_inr:,} "
            f"(for {travelers} traveller(s) across ~{round(distance_km)} km)"
        )

    # Sightseeing entrance fees & activities
    attractions_cost_inr = 0
    activities_cost_inr = 0
    if attractions_list:
        for a in attractions_list:
            fee = a.get("entry_fee_inr", 0)
            if a.get("category") == "adventure":
                activities_cost_inr += fee * travelers
            else:
                attractions_cost_inr += fee * travelers
    else:
        attractions_cost_inr = 300 * travelers * num_days

    sightseeing_basis = (
        f"Entrance tickets (₹{attractions_cost_inr:,}) + adventure activities (₹{activities_cost_inr:,}) for {travelers} person(s)"
    )

    # Miscellaneous / Contingency (7% of trip subtotal)
    # Total transportation aligns exactly with the selected option
    total_all_transportation_inr = total_intercity_transport_inr
    subtotal_inr = (
        total_all_transportation_inr +
        total_accommodation_inr +
        total_food_inr +
        attractions_cost_inr +
        activities_cost_inr
    )
    miscellaneous_inr = round(subtotal_inr * 0.07)
    miscellaneous_basis = "7% buffer for emergency, tips, bottled water, souvenirs & incidentals"

    # Total Estimated Cost
    total_estimated_trip_cost_inr = subtotal_inr + miscellaneous_inr
    total_estimated_per_person_inr = round(total_estimated_trip_cost_inr / travelers, 2)

    # Normalize user available budget
    # Check if user entered per_person or total_group budget
    if budget_type == "per_person":
        available_budget_per_person_foreign = budget_input
        available_budget_total_foreign = budget_input * travelers
    else:
        available_budget_total_foreign = budget_input
        available_budget_per_person_foreign = round(budget_input / travelers, 2)

    available_budget_total_inr = convert_to_inr(available_budget_total_foreign, currency)
    available_budget_per_person_inr = round(available_budget_total_inr / travelers, 2)

    # Budget Difference & Classification (Feature Two / Phase 2 Rules)
    # budget_difference = available_budget - estimated_total
    budget_difference_inr = available_budget_total_inr - total_estimated_trip_cost_inr
    budget_difference_per_person_inr = round(budget_difference_inr / travelers, 2)
    percentage_consumed = round((total_estimated_trip_cost_inr / max(1.0, available_budget_total_inr)) * 100, 1)

    if budget_difference_inr > 50:
        budget_status = "sufficient"
        status_label = "Budget Sufficient"
        status_color = "green"
        status_icon = "✅"
        status_message = (
            f"Your budget has a comfortable surplus of {format_money(convert_from_inr(budget_difference_inr, currency), currency)} "
            f"({format_money(convert_from_inr(budget_difference_per_person_inr, currency), currency)} per person)."
        )
        suggestions = [
            "Your planned trip is well within your budget.",
            "You can consider upgrading your accommodation or trying a specialty dining experience."
        ]
    elif abs(budget_difference_inr) <= 50:
        budget_status = "exact"
        status_label = "Exact Match"
        status_color = "yellow"
        status_icon = "⚖️"
        status_message = "Your budget matches the estimated trip expenses almost exactly. Keep spending closely monitored."
        suggestions = [
            "Your budget is balanced, but unexpected expenses could push you over.",
            "Consider keeping an emergency card handy."
        ]
    else:
        budget_status = "insufficient"
        status_label = "Budget Shortfall"
        status_color = "red"
        status_icon = "⚠️"
        shortfall_total_foreign = convert_from_inr(abs(budget_difference_inr), currency)
        shortfall_pp_foreign = convert_from_inr(abs(budget_difference_per_person_inr), currency)
        status_message = (
            f"Estimated expenses exceed your budget by {format_money(shortfall_total_foreign, currency)} "
            f"({format_money(shortfall_pp_foreign, currency)} per person). "
            f"You have consumed {percentage_consumed}% of your available budget."
        )
        suggestions = [
            f"Increase total budget by {format_money(shortfall_total_foreign, currency)} to cover standard trip expenses.",
            f"Switch accommodation preference from '{accommodation_preference.replace('_', ' ').title()}' to Budget Hotel or Hostel to save up to 40%.",
            "Opt for train or bus transport instead of flights or private cabs.",
            "Prioritize free public attractions (beaches, old towns, parks) over paid theme parks.",
            f"Reduce trip duration by 1 day to reduce accommodation & daily food expenses."
        ]

    # Convert all categories to target currency for display
    def c(amt_inr: float) -> float:
        return convert_from_inr(amt_inr, currency)

    return {
        "currency": currency,
        "travelers": travelers,
        "num_days": num_days,
        "num_nights": num_nights,
        "budget_type": budget_type,
        "available_budget_total": round(available_budget_total_foreign, 2),
        "available_budget_per_person": round(available_budget_per_person_foreign, 2),
        "total_estimated_trip_cost": c(total_estimated_trip_cost_inr),
        "total_estimated_per_person": c(total_estimated_per_person_inr),
        "budget_difference": c(budget_difference_inr),
        "budget_difference_per_person": c(budget_difference_per_person_inr),
        "percentage_consumed": percentage_consumed,
        "budget_status": budget_status,
        "status_label": status_label,
        "status_color": status_color,
        "status_icon": status_icon,
        "status_message": status_message,
        "suggestions": suggestions,
        # Component Breakdown
        "categories": {
            "transportation": {
                "label": f"Intercity Transportation ({selected_mode} Round-Trip)",
                "icon": selected_icon,
                "total": c(total_all_transportation_inr),
                "per_person": c(total_all_transportation_inr / travelers),
                "intercity_outbound": c(outbound_transport_inr),
                "intercity_return": c(return_transport_inr),
                "selected_mode": selected_mode,
                "basis": intercity_basis
            },
            "accommodation": {
                "label": "Accommodation",
                "icon": "🏨",
                "total": c(total_accommodation_inr),
                "per_person": c(total_accommodation_inr / travelers),
                "rooms": rooms_needed,
                "nights": num_nights,
                "tier": accommodation_preference.replace("_", " ").title(),
                "basis": accommodation_basis
            },
            "food": {
                "label": "Food & Beverages",
                "icon": "🍽️",
                "total": c(total_food_inr),
                "per_person": c(total_food_inr / travelers),
                "tier": food_preference.replace("_", " ").title(),
                "basis": food_basis
            },
            "sightseeing": {
                "label": "Sightseeing & Activities",
                "icon": "🎫",
                "total": c(attractions_cost_inr + activities_cost_inr),
                "per_person": c((attractions_cost_inr + activities_cost_inr) / travelers),
                "attraction_entry_fees": c(attractions_cost_inr),
                "adventure_activities": c(activities_cost_inr),
                "basis": sightseeing_basis
            },
            "miscellaneous": {
                "label": "Emergency Contingency & Other",
                "icon": "🛡️",
                "total": c(miscellaneous_inr),
                "per_person": c(miscellaneous_inr / travelers),
                "basis": miscellaneous_basis
            }
        },
        # Raw INR values for backend consistency
        "_inr": {
            "total_estimated": total_estimated_trip_cost_inr,
            "total_available": available_budget_total_inr,
            "difference": budget_difference_inr
        }
    }

