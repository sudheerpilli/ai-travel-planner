"""
Full audit: itinerary variety after interest-fix, DB check, chatbot handler spot-check.
"""
import sys, os
sys.path.insert(0, r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")
os.chdir(r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")

from services.attractions_service import get_attractions_for_destination
from planner import create_comprehensive_itinerary
from services.chatbot_service import generate_chat_response
from services.storage_service import init_db, list_saved_trips

# 1. DB check
print("=== DB CHECK ===")
init_db()
trips = list_saved_trips()
thailand = [t for t in trips if t.get("destination", "").lower() == "thailand"]
print(f"Total saved trips: {len(trips)}")
print(f"Thailand trip present: {len(thailand) > 0}")
if thailand:
    print(f"  ID: {thailand[0]['id']}, destination: {thailand[0]['destination']}")

# 2. Attractions pool size check with expanded defaults
print("\n=== ATTRACTIONS POOL (Goa, no interests) ===")
attractions, source = get_attractions_for_destination("Goa", interests=[])
print(f"Source: {source}")
print(f"Total attractions returned: {len(attractions)}")
cats = {}
for a in attractions:
    c = a.get("category", "unknown")
    cats[c] = cats.get(c, 0) + 1
for c, n in sorted(cats.items()):
    print(f"  {c}: {n}")

# 3. 7-day itinerary — check no filler days
print("\n=== 7-DAY GOA ITINERARY (checking Day 5 is real) ===")
trip7 = create_comprehensive_itinerary("Hyderabad", "Goa", "2026-12-01", "2026-12-07", 2, 35000)
itinerary = trip7.get("itinerary", [])
for day in itinerary:
    dn = day.get("day_number")
    is_rest = day.get("is_rest_day", False)
    m = day.get("morning", {}).get("name", "N/A")
    a = day.get("afternoon", {}).get("name", "N/A")
    e = day.get("evening", {}).get("name", "N/A")
    filler = "Artisans" in m or "Bazaars" in m
    print(f"  Day {dn}: {'[REST]' if is_rest else '[PLAN]'}  M={m} | filler={filler}")
    if not is_rest:
        print(f"           A={a} | E={e}")

# 4. Sightseeing cost with expanded attractions
print("\n=== BUDGET - 3-day Goa solo ===")
trip3 = create_comprehensive_itinerary("Hyderabad", "Goa", "2026-12-01", "2026-12-03", 1, 20000)
ba = trip3.get("budget_analysis", {})
cats_budget = ba.get("categories", {})
sight = cats_budget.get("sightseeing", {})
print(f"Sightseeing total: ₹{sight.get('total', 0):.0f} (was ₹75)")
print(f"Accommodation: ₹{cats_budget.get('accommodation', {}).get('total', 0):.0f}")
print(f"Total estimated: ₹{ba.get('total_estimated_trip_cost', 0):.0f}")

# 5. Chatbot spot-checks
print("\n=== CHATBOT SPOT CHECKS ===")
ctx_basic = {"destination": "Goa", "travelers": 2, "currency": "INR"}
ctx_full = trip3
ctx_full["destination"] = "Goa"

tests = [
    ("Best time to visit Goa?", ctx_basic, "peak"),
    ("What transport options do I have?", ctx_basic, "train"),
    ("Give me tips for visiting Goa", ctx_basic, "tip"),
    ("Hello", ctx_basic, "TripWise"),
    ("What food should I try?", ctx_basic, "fish"),
    ("Can you reduce my trip budget?", ctx_basic, "Accommodation"),
    ("What should I pack?", ctx_basic, "sunscreen"),
]

for msg, ctx, expected_kw in tests:
    r = generate_chat_response(msg, trip_context=ctx)
    reply = r.get("reply", "")
    ok = expected_kw.lower() in reply.lower()
    print(f"  {'✅' if ok else '❌'} '{msg[:45]}' -> contains '{expected_kw}': {ok}")
    if not ok:
        print(f"     GOT: {reply[:150]}")
