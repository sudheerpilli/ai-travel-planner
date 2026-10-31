
"""Travel planner with optional Wikipedia attraction search."""

from datetime import date, timedelta
import requests
import re
from html import unescape


# Built-in attraction suggestions
ATTRACTIONS = {
    "culture": [
        ("Local heritage museum", "Explore regional history and exhibits", 250),
        ("Historic district walk", "Explore historic streets and landmarks", 150),
        ("Traditional arts centre", "Discover local crafts and performances", 300),
    ],
    "nature": [
        ("Botanical garden", "Relax among gardens and green spaces", 200),
        ("Scenic viewpoint", "Enjoy panoramic views", 100),
        ("Lake or riverside trail", "Enjoy an outdoor walk", 100),
    ],
    "food": [
        ("Local food market", "Sample regional snacks and street food", 400),
        ("Regional cuisine restaurant", "Try local cuisine", 500),
        ("Food tasting experience", "Discover local flavours", 700),
    ],
    "adventure": [
        ("Outdoor activity centre", "Explore outdoor activities", 800),
        ("Cycling or walking tour", "Explore the area actively", 350),
        ("Nearby day trip", "Explore nearby destinations", 1000),
    ],
    "shopping": [
        ("Local handicraft market", "Browse crafts and souvenirs", 400),
        ("Main shopping street", "Explore local shops", 300),
        ("Artisan stores", "Discover locally made products", 250),
    ],
    "family": [
        ("Science or discovery centre", "Enjoy interactive activities", 350),
        ("Public park", "Relax and enjoy outdoor activities", 100),
        ("Family-friendly attraction", "Enjoy an activity for the family", 300),
    ],
}


def _dates(start, end):
    """Generate trip dates, limited to 31 days."""
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)

    if last < first:
        raise ValueError("End date must not be before start date.")

    if (last - first).days > 30:
        last = first + timedelta(days=30)

    return [
        first + timedelta(days=i)
        for i in range((last - first).days + 1)
    ]


def _live_attractions(destination):
    """Search Wikipedia without requiring an API key."""
    try:
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"tourist attractions in {destination}",
                "format": "json",
                "srlimit": 10,
            },
            headers={
                "User-Agent": "TripWiseTravelPlanner/1.0"
            },
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()

        results = data.get("query", {}).get("search", [])
        attractions = []

        for item in results:
            name = item.get("title", "").strip()

            # Remove HTML tags from the Wikipedia search snippet.
            snippet = re.sub(
                r"<[^>]*>",
                "",
                item.get("snippet", ""),
            )
            description = unescape(snippet)

            if name:
                attractions.append(
                    (
                        name,
                        description or "Explore this destination.",
                        300,
                    )
                )

        return attractions

    except (
        requests.RequestException,
        ValueError,
        TypeError,
        KeyError,
    ):
        print(
            "Wikipedia search unavailable. "
            "Using built-in attraction suggestions."
        )
        return []


def create_itinerary(
    destination,
    start_date,
    end_date,
    budget,
    interests,
    travelers,
    currency="INR",
):
    """Create a daily itinerary and estimated budget."""

    destination = str(destination).strip()

    if not destination:
        raise ValueError("Please enter a destination.")

    budget = float(budget)
    travelers = int(travelers)

    if budget <= 0:
        raise ValueError("Budget must be greater than zero.")

    if travelers < 1:
        raise ValueError("At least one traveler is required.")

    days = _dates(start_date, end_date)

    # Validate selected interests.
    interests = interests or []

    selected = [
        str(item).lower()
        for item in interests
        if str(item).lower() in ATTRACTIONS
    ]

    if not selected:
        selected = ["culture", "food", "nature"]

    # Get online attraction suggestions.
    live = _live_attractions(destination)

    # Combine online suggestions and built-in recommendations.
    pool = list(live)

    for interest in selected:
        pool.extend(ATTRACTIONS[interest])

    # Remove duplicate attraction names.
    unique = []
    seen = set()

    for item in pool:
        if item[0].lower() not in seen:
            unique.append(item)
            seen.add(item[0].lower())

    if not unique:
        raise ValueError("No attraction suggestions are available.")

    # Create three activity slots per day.
    daily = []
    total_attractions = 0

    for idx, day in enumerate(days):
        items = [
            unique[(idx * 3 + j) % len(unique)]
            for j in range(3)
        ]

        def make_activity(item, time):
            name, description, estimated_cost = item

            return {
                "time": time,
                "name": name,
                "description": description,
                "cost": estimated_cost * travelers,
            }

        daily.append({
            "date": day.isoformat(),
            "day": idx + 1,
            "morning": make_activity(
                items[0], "09:00–11:30"
            ),
            "afternoon": make_activity(
                items[1], "12:30–16:00"
            ),
            "evening": make_activity(
                items[2], "17:00–19:00"
            ),
        })

        total_attractions += sum(
            item[2] * travelers for item in items
        )

    # Indicative budget estimates, not live travel prices.
    transport = round(budget * 0.18)
    lodging = round(budget * 0.38)
    food = round(budget * 0.22)
    attractions_cost = min(
        total_attractions,
        round(budget * 0.17),
    )

    estimated = (
        transport
        + lodging
        + food
        + attractions_cost
    )

    contingency = max(0, round(budget - estimated))

    return {
        "destination": destination,
        "start_date": days[0].isoformat(),
        "end_date": days[-1].isoformat(),
        "days": daily,
        "budget": budget,
        "currency": currency,
        "travelers": travelers,
        "costs": {
            "transport": transport,
            "accommodation": lodging,
            "food": food,
            "attractions": attractions_cost,
            "contingency": contingency,
            "estimated_total": estimated,
            "per_person": round(estimated / travelers),
        },
        "budget_status": (
            "within" if estimated <= budget else "over"
        ),
        "live_data_used": bool(live),
        "notes": [
            (
                "Costs are estimates, not live quotes. "
                "Verify hotel prices, transport, entry fees "
                "and opening hours."
            ),
            (
                "Wikipedia search results may not all be "
                "tourist attractions. Check the locations "
                "before visiting."
            ),
            (
                "The schedule is a suggested outline. "
                "Allow enough travel time between places."
            ),
        ],
    }
