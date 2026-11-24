import sys, os, re
sys.path.insert(0, r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")
from planner import create_comprehensive_itinerary
from services.pdf_service import generate_trip_pdf

trip = create_comprehensive_itinerary(
    start_location="Visakhapatnam",
    destination="Goa",
    start_date="2026-12-06",
    end_date="2026-12-09",
    travelers=2,
    budget=25000,
    currency="INR"
)

print("=== 1. TRANSPORTATION OPTIONS ===")
tc = trip.get("transportation_comparison", {})
for opt in tc.get("options", []):
    mode = opt["mode"]
    one_way = opt.get("one_way_total")
    ret = opt.get("return_total")
    dur = opt.get("duration")
    avail = opt.get("available")
    basis = " [BUDGET BASIS]" if opt.get("is_budget_basis") else ""
    print(f"  {mode:<16}: One-way=₹{one_way:,.0f} | Round-trip=₹{ret:,.0f} | Duration={dur} | Avail={avail}{basis}")

print("\n=== 2. ITINERARY DAYS & OPENING HOURS ===")
for day in trip.get("itinerary", []):
    dn = day["day_number"]
    df = day["date_formatted"]
    sched = day.get("schedule", {})
    print(f"\nDay {dn} ({df}):")
    for slot in ["morning", "afternoon", "evening"]:
        act = day.get(slot)
        if act:
            t = act.get("time")
            name = act.get("name")
            dur = act.get("visit_duration")
            hrs = act.get("opening_hours")
            print(f"  {slot:<10} [{t}]: {name} | dur={dur} | hrs={hrs}")

print("\n=== 3. BUDGET RECONCILIATION ===")
ba = trip.get("budget_analysis", {})
cats = ba.get("categories", {})
subtotal = 0
for k, c in cats.items():
    tot = c.get("total", 0)
    pp = c.get("per_person", 0)
    if k != "miscellaneous":
        subtotal += tot
    print(f"  {k:<16}: Total=₹{tot:,.0f} | Per Person=₹{pp:,.0f}")
misc = cats.get("miscellaneous", {}).get("total", 0)
calc_tot = subtotal + misc
rep_tot = ba.get("total_estimated_trip_cost", 0)
print(f"  Subtotal (excl misc): ₹{subtotal:,.0f}")
print(f"  Misc (7%):            ₹{misc:,.0f}")
print(f"  Calculated Total:     ₹{calc_tot:,.0f}")
print(f"  Reported Total:       ₹{rep_tot:,.0f}")
print(f"  Difference:           ₹{calc_tot - rep_tot:,.0f}")

print("\n=== 4. PDF GENERATION ===")
pdf_bytes = generate_trip_pdf(trip)
print(f"PDF Size: {len(pdf_bytes):,} bytes | Starts with: {pdf_bytes[:4]}")
