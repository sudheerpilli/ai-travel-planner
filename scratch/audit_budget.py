"""Quick audit script for TripWise budget and itinerary."""
import sys
sys.path.insert(0, r'c:\Users\sudhe\Downloads\ai_travel_planning_chatbot')

from planner import create_comprehensive_itinerary

# Test 1: 3-day solo Goa trip (the user said ~19,000 was unreasonable)
print("=== 3-day Solo Goa Trip Budget ===")
result = create_comprehensive_itinerary(
    'Visakhapatnam', 'Goa', '2026-12-10', '2026-12-12', 1, 20000, 'total_group', 'INR'
)
ba = result['budget_analysis']
print(f"Total cost: INR {ba['total_estimated_trip_cost']:,.0f}")
print(f"Per person: INR {ba['total_estimated_per_person']:,.0f}")
print(f"Status: {ba['budget_status']}")
cats = ba['categories']
print(f"Transport:     INR {cats['transportation']['total']:,.0f} | Basis: {cats['transportation']['basis'][:80]}")
print(f"Accommodation: INR {cats['accommodation']['total']:,.0f} | Basis: {cats['accommodation']['basis'][:80]}")
print(f"Food:          INR {cats['food']['total']:,.0f} | Basis: {cats['food']['basis'][:80]}")
print(f"Sightseeing:   INR {cats['sightseeing']['total']:,.0f} | Basis: {cats['sightseeing']['basis'][:80]}")
print(f"Misc:          INR {cats['miscellaneous']['total']:,.0f}")

print()
itin = result['itinerary']
print(f"Days in itinerary: {len(itin)}")
for d in itin:
    print(f"  Day {d['day_number']} ({d['date_formatted']}):")
    print(f"    Morning:   {d['morning']['name']}")
    print(f"    Afternoon: {d['afternoon']['name']}")
    print(f"    Evening:   {d['evening']['name']}")

# Test 2: 7-day Goa trip for duplicates
print()
print("=== 7-day Goa Trip Duplicate Check ===")
result7 = create_comprehensive_itinerary(
    'Hyderabad', 'Goa', '2026-12-01', '2026-12-07', 2, 35000
)
itin7 = result7['itinerary']
all_names = []
for d in itin7:
    names = [d['morning']['name'], d['afternoon']['name'], d['evening']['name']]
    print(f"  Day {d['day_number']}: {names[0]} | {names[1]} | {names[2]}")
    all_names.extend(names)

dupes = [n for n in all_names if all_names.count(n) > 1]
print()
if dupes:
    print(f"DUPLICATES FOUND: {set(dupes)}")
else:
    print("No duplicates - PASS")

# Test 3: 1-day trip
print()
print("=== 1-day Hyderabad Trip ===")
result1 = create_comprehensive_itinerary(
    'Bengaluru', 'Hyderabad', '2026-12-10', '2026-12-10', 2, 10000
)
ba1 = result1['budget_analysis']
print(f"Total cost: INR {ba1['total_estimated_trip_cost']:,.0f}")
print(f"Days: {len(result1['itinerary'])}")
