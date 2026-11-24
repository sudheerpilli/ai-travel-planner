import sys, os, re
sys.path.insert(0, r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")
from datetime import date, timedelta
from planner import create_comprehensive_itinerary
from services.pdf_service import generate_trip_pdf

def count_pages(pdf_bytes):
    return len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))

def check_pdf_text_elements(pdf_bytes, expected_strings):
    found = []
    missing = []
    for s in expected_strings:
        if s.encode("latin-1") in pdf_bytes or s.encode("utf-8") in pdf_bytes:
            found.append(s)
        else:
            missing.append(s)
    return found, missing

trips = [
    (1, "1-Day Goa Trip", "2026-12-06", "2026-12-06"),
    (3, "3-Day Goa Trip", "2026-12-06", "2026-12-08"),
    (4, "4-Day Goa Trip", "2026-12-06", "2026-12-09"),
    (7, "7-Day Goa Trip", "2026-12-06", "2026-12-12"),
]

for days, label, start, end in trips:
    trip = create_comprehensive_itinerary("Visakhapatnam", "Goa", start, end, 2, 35000)
    pdf = generate_trip_pdf(trip)
    pages = count_pages(pdf)
    
    # Save to disk for inspection
    pdf_path = f"scratch/test_{days}day.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf)
    
    print(f"\n{'='*60}")
    print(f"{label}: {len(pdf):,} bytes | Pages: {pages}")
    print(f"Saved: {pdf_path}")
    
    # Verify all days present
    itin = trip.get("itinerary", [])
    print(f"Days in itinerary object: {len(itin)}")
    for d in itin:
        dn = d["day_number"]
        m = d["morning"]["name"]
        a = d["afternoon"]["name"]
        e = d["evening"]["name"]
        print(f"  Day {dn}: {m} ({d['morning']['time']}) | {a} ({d['afternoon']['time']}) | {e} ({d['evening']['time']})")
    
    # Verify transport options in trip
    tc = trip.get("transportation_comparison", {})
    zero_prices = [o["mode"] for o in tc.get("options", []) if o.get("available") and (o.get("one_way_total", 0) == 0 or o.get("return_total", 0) == 0)]
    if zero_prices:
        print(f"  ❌ ERROR: Zero price found in available transport: {zero_prices}")
    else:
        print(f"  ✅ Transport prices verified (no ₹0)")

    # Verify no closed attractions scheduled
    closed_found = []
    for d in itin:
        cur_date = date.fromisoformat(d["date"])
        for slot in ["morning", "afternoon", "evening"]:
            act = d.get(slot)
            if act:
                hrs = act.get("opening_hours", "")
                if cur_date.weekday() == 0 and ("closed mon" in hrs.lower() or "closed monday" in hrs.lower()):
                    closed_found.append((d["day_number"], act["name"], hrs))
                if cur_date.weekday() != 2 and "wednesday" in hrs.lower() and "seasonal" in hrs.lower():
                    closed_found.append((d["day_number"], act["name"], hrs))
    if closed_found:
        print(f"  ❌ ERROR: Closed attractions scheduled: {closed_found}")
    else:
        print(f"  ✅ No closed attractions scheduled on any day")
