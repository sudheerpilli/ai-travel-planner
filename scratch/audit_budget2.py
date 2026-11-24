"""Deep audit of budget calculation for realistic Indian travel."""
import sys
sys.path.insert(0, r'c:\Users\sudhe\Downloads\ai_travel_planning_chatbot')

from services.budget_service import calculate_comprehensive_budget
from services.transport_service import compare_transportation_modes

# Test: 3-day Goa solo trip from Visakhapatnam
print("=== Budget Calculation Detailed Audit: 3-day Goa Solo from Vizag ===")
result = calculate_comprehensive_budget(
    start_location='Visakhapatnam',
    destination='Goa',
    num_days=3,
    num_nights=2,
    travelers=1,
    travel_preference='standard',
    accommodation_preference='budget_hotel',
    food_preference='casual',
    budget_input=20000,
    budget_type='total_group',
    currency='INR',
    intercity_one_way_cost_inr=None,
    distance_km=650
)
print(f"Available Budget: INR {result['available_budget_total']:,.0f}")
print(f"Estimated Total:  INR {result['total_estimated_trip_cost']:,.0f}")
print(f"Status: {result['budget_status']}")
cats = result['categories']
for k, v in cats.items():
    print(f"  {k}: INR {v['total']:,.0f} | Per person: INR {v['per_person']:,.0f}")
    print(f"    Basis: {v['basis']}")

# Check transport comparison
print()
print("=== Transport Comparison: Vizag -> Goa ===")
tc = compare_transportation_modes('Visakhapatnam', 'Goa', travelers=1)
print(f"Road distance: {tc['road_distance_km']} km")
print(f"Air distance: {tc['air_distance_km']} km")
for opt in tc['options']:
    if opt['available']:
        print(f"  {opt['mode']}: One-way INR {opt['one_way_total_inr']:,.0f} | Round-trip INR {opt['return_total_inr']:,.0f} | {opt['duration_formatted']} | Badges: {opt.get('badges', [])}")

# Test: 3-day Goa solo using default interests (no interest filter)
print()
print("=== Attractions pulled for Goa (no interests) ===")
from services.attractions_service import get_attractions_for_destination
attrs, source = get_attractions_for_destination('Goa', [])
print(f"Source: {source}")
print(f"Count: {len(attrs)}")
for a in attrs:
    print(f"  {a['name']} ({a['category']}) - fee: ₹{a.get('entry_fee_inr', 0)}")
