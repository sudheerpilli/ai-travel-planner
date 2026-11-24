import sys, os, re
sys.path.insert(0, r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")
from datetime import date, timedelta
from services.attractions_service import DESTINATION_CATALOGUE, get_attractions_for_destination
from services.routing_service import calculate_route

# Import the helpers we defined
# Let's test scheduling 4 days from 2026-12-06 to 2026-12-09
dates = [
    date(2026, 12, 6), # Sunday
    date(2026, 12, 7), # Monday
    date(2026, 12, 8), # Tuesday
    date(2026, 12, 9)  # Wednesday
]

def is_attraction_open_on_date(attraction: dict, check_date: date) -> tuple[bool, str]:
    hours_raw = attraction.get("opening_hours", "")
    if not hours_raw:
        return True, "Hours unspecified (assumed open)"
    h_lower = hours_raw.lower()
    weekday = check_date.weekday()
    weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    current_day_name = weekday_names[weekday]

    closed_patterns = {
        0: ["closed mon", "closed monday"],
        1: ["closed tue", "closed tuesday"],
        2: ["closed wed", "closed wednesday"],
        3: ["closed thu", "closed thursday"],
        4: ["closed fri", "closed friday"],
        5: ["closed sat", "closed saturday"],
        6: ["closed sun", "closed sunday"],
    }
    for pat in closed_patterns.get(weekday, []):
        if pat in h_lower:
            return False, f"Closed on {current_day_name.capitalize()}s ({hours_raw})"

    if "wednesday" in h_lower and ("only" in h_lower or "seasonal" in h_lower or h_lower.startswith("09:00 - 19:00 (wednesdays")):
        if weekday != 2:
            return False, f"Open only on Wednesdays ({hours_raw})"

    if "weekends" in h_lower and "only" in h_lower:
        if weekday not in (5, 6):
            return False, f"Open only on weekends ({hours_raw})"
    return True, "Open"

def is_attraction_suitable_for_slot(attraction: dict, slot_name: str, check_date: date) -> tuple[bool, str]:
    is_open, reason = is_attraction_open_on_date(attraction, check_date)
    if not is_open:
        return False, reason
    hours_raw = attraction.get("opening_hours", "")
    h_lower = hours_raw.lower()
    if "open 24 hours" in h_lower:
        return True, "Open 24 hours"

    times = re.findall(r"(\d{1,2}):(\d{2})", hours_raw)
    if times:
        try:
            start_hour = int(times[0][0])
            start_min = int(times[0][1])
            start_total = start_hour * 60 + start_min
            end_hour = int(times[-1][0])
            end_min = int(times[-1][1])
            end_total = end_hour * 60 + end_min

            if slot_name == "morning":
                if start_total >= 12 * 60:
                    return False, f"Opens at {start_hour:02d}:{start_min:02d} (afternoon/evening only)"
                if end_total < 10 * 60 + 30 and end_total > start_total:
                    return False, f"Closes at {end_hour:02d}:{end_min:02d} (early morning only)"
            elif slot_name == "afternoon":
                if start_total >= 17 * 60:
                    return False, f"Opens at {start_hour:02d}:{start_min:02d} (evening only)"
                if end_total <= 14 * 60 and end_total > start_total:
                    return False, f"Closes at {end_hour:02d}:{end_min:02d} (morning only)"
            elif slot_name == "evening":
                if end_total <= 17 * 60 and end_total > start_total:
                    return False, f"Closes at {end_hour:02d}:{end_min:02d} (closes before evening)"
                if start_total >= 20 * 60:
                    return False, f"Opens late at {start_hour:02d}:{start_min:02d}"
        except Exception:
            pass
    return True, "Suitable"

attractions_pool, _ = get_attractions_for_destination("Goa")
scheduled_names = set()

for day_idx, day_date in enumerate(dates):
    day_name = day_date.strftime("%a, %d %b %Y")
    # Remaining attractions
    available = [a for a in attractions_pool if a["name"] not in scheduled_names]

    # Find suitable morning
    m_candidates = [a for a in available if is_attraction_suitable_for_slot(a, "morning", day_date)[0]]
    if not m_candidates:
        m_candidates = [a for a in available if is_attraction_open_on_date(a, day_date)[0]]
    m_item = m_candidates[0]
    scheduled_names.add(m_item["name"])

    # Find suitable afternoon closest to morning
    available_a = [a for a in attractions_pool if a["name"] not in scheduled_names]
    a_candidates = [a for a in available_a if is_attraction_suitable_for_slot(a, "afternoon", day_date)[0]]
    if not a_candidates:
        a_candidates = [a for a in available_a if is_attraction_open_on_date(a, day_date)[0]]
    
    def dist_to_m(item):
        if m_item.get("lat") and item.get("lat"):
            dlat = item["lat"] - m_item["lat"]
            dlon = item["lon"] - m_item["lon"]
            return dlat * dlat + dlon * dlon
        return 999.0
    
    a_candidates.sort(key=dist_to_m)
    a_item = a_candidates[0]
    scheduled_names.add(a_item["name"])

    # Find suitable evening closest to afternoon/morning
    available_e = [a for a in attractions_pool if a["name"] not in scheduled_names]
    e_candidates = [a for a in available_e if is_attraction_suitable_for_slot(a, "evening", day_date)[0]]
    if not e_candidates:
        e_candidates = [a for a in available_e if is_attraction_open_on_date(a, day_date)[0]]
    
    def dist_to_a(item):
        if a_item.get("lat") and item.get("lat"):
            dlat = item["lat"] - a_item["lat"]
            dlon = item["lon"] - a_item["lon"]
            return dlat * dlat + dlon * dlon
        return 999.0
    
    e_candidates.sort(key=dist_to_a)
    e_item = e_candidates[0]
    scheduled_names.add(e_item["name"])

    print(f"\n{day_name}:")
    print(f"  Morning:   {m_item['name']} ({m_item['opening_hours']})")
    print(f"  Afternoon: {a_item['name']} ({a_item['opening_hours']})")
    print(f"  Evening:   {e_item['name']} ({e_item['opening_hours']})")

    # Verify none closed on this day
    for item in [m_item, a_item, e_item]:
        is_open, why = is_attraction_open_on_date(item, day_date)
        assert is_open, f"ERROR: {item['name']} scheduled on {day_name} but {why}!"
print("\nALL DAYS PASSED OPENING HOURS CHECK!")
