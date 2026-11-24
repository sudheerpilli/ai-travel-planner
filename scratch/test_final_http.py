import sys, os, json, re
sys.path.insert(0, r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")
from app import app
from services.storage_service import get_trip, list_saved_trips

client = app.test_client()

# 1. Test POST /api/plan for 4-day Goa trip
plan_req = {
    "start_location": "Visakhapatnam",
    "destination": "Goa",
    "start_date": "2026-12-06",
    "end_date": "2026-12-09",
    "travelers": 2,
    "budget": 25000,
    "currency": "INR"
}
r_plan = client.post("/api/plan", json=plan_req)
assert r_plan.status_code == 200, f"Plan failed: {r_plan.status_code}"
plan_data = json.loads(r_plan.data)
print("1. Plan generation HTTP 200 OK")

# 2. Check transport options in plan response
options = plan_data.get("transportation_comparison", {}).get("options", [])
for opt in options:
    print(f"   {opt['mode']}: one_way={opt.get('one_way_total')} | return={opt.get('return_total')} | duration={opt.get('duration')}")
    if opt.get("available"):
        assert opt.get("one_way_total", 0) > 0, f"Zero one_way_total for {opt['mode']}"
        assert opt.get("return_total", 0) > 0, f"Zero return_total for {opt['mode']}"
print("2. Transport options in API response verified: NO zero prices")

# 3. Check itinerary days: Day 2 Monday must not have closed attractions
itin = plan_data.get("itinerary", [])
day2 = itin[1]
print(f"3. Day 2: {day2['date_formatted']}")
for slot in ["morning", "afternoon", "evening"]:
    act = day2[slot]
    print(f"   {slot}: {act['name']} ({act['time']}) | duration: {act['visit_duration']}")
    assert "Reis Magos" not in act['name'], "Reis Magos scheduled on Monday!"
    assert "Naval Aviation" not in act['name'], "Naval Aviation Museum scheduled on Monday!"

# 4. Check POST /api/trips/export-pdf
r_pdf = client.post("/api/trips/export-pdf", json=plan_data)
assert r_pdf.status_code == 200, f"PDF export failed: {r_pdf.status_code}"
assert r_pdf.data.startswith(b"%PDF"), "Response is not PDF"
page_count = len(re.findall(rb"/Type\s*/Page\b", r_pdf.data))
print(f"4. PDF Export HTTP 200 OK: {len(r_pdf.data):,} bytes | Pages: {page_count}")
assert page_count >= 3, f"Expected at least 3 pages, got {page_count}"

# 5. Check database: Thailand record intact
all_trips = list_saved_trips()
thailand = [t for t in all_trips if t.get("destination", "").lower() == "thailand"]
assert len(thailand) > 0, "Thailand trip missing!"
print(f"5. Database preserved: Thailand trip id={thailand[0]['id']} present")

print("\nALL HTTP & ENDPOINT CHECKS PASSED SUCCESSFULLY!")
