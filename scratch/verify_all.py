"""
Master verification script — Tasks 2-8 (no browser required).
Runs entirely via Flask test client and direct Python calls.
"""
import sys, os, io, json, sqlite3, re
from datetime import date, timedelta

sys.path.insert(0, r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")
os.chdir(r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")

# ─── Imports ───
from app import app as flask_app
from planner import create_comprehensive_itinerary
from services.chatbot_service import generate_chat_response
from services.budget_service import calculate_comprehensive_budget
from services.transport_service import compare_transportation_modes
from services.pdf_service import generate_trip_pdf
from services.storage_service import init_db, list_saved_trips, get_trip, save_trip, delete_trip

SECTION = lambda title: print(f"\n{'='*70}\n  {title}\n{'='*70}")
OK  = lambda msg: print(f"  ✅  {msg}")
ERR = lambda msg: print(f"  ❌  {msg}")
INF = lambda msg: print(f"  ℹ️   {msg}")

client = flask_app.test_client()

# ════════════════════════════════════════════════════════════════════════
# TASK 2 — Backend HTTP Verification
# ════════════════════════════════════════════════════════════════════════
SECTION("TASK 2 — Backend HTTP Verification")

plan_payload = {
    "start_location": "Visakhapatnam",
    "destination": "Goa",
    "start_date": "2026-12-10",
    "end_date": "2026-12-12",
    "travelers": 1,
    "budget": 25000,
    "currency": "INR",
    "interests": []
}

# 2a. Homepage
r = client.get("/")
code = r.status_code
INF(f"GET /  → {code}")
if code == 200 and b"TripWise" in r.data:
    OK("Homepage loads, TripWise branding present")
else:
    ERR(f"Homepage issue: status={code}, TripWise={'yes' if b'TripWise' in r.data else 'no'}")

# 2b. Trip generation
r = client.post("/api/plan", json=plan_payload)
INF(f"POST /api/plan → {r.status_code}")
plan_data = json.loads(r.data)
if r.status_code == 200 and "itinerary" in plan_data:
    OK(f"Trip generation → {len(plan_data['itinerary'])} days itinerary")
    TRIP_CTX = plan_data
else:
    ERR(f"Trip generation failed: {str(plan_data)[:300]}")
    TRIP_CTX = {}

# 2c. Chat endpoint
chat_payload = {
    "message": "What is the best time to visit Goa?",
    "trip_context": {"destination": "Goa", "travelers": 1, "currency": "INR"}
}
r = client.post("/api/chat", json=chat_payload, content_type="application/json")
INF(f"POST /api/chat → {r.status_code}")
chat_data = json.loads(r.data)
if r.status_code == 200 and "reply" in chat_data:
    OK(f"Chat endpoint works; source={chat_data.get('source_indicator', '?')}")
    INF(f"  reply preview: {chat_data['reply'][:120]}")
else:
    ERR(f"Chat endpoint issue: {str(chat_data)[:200]}")

# 2d. Weather endpoint
r = client.get("/api/weather?destination=Goa")
INF(f"GET /api/weather?destination=Goa → {r.status_code}")
w = json.loads(r.data)
if r.status_code == 200 and w.get("available"):
    OK(f"Weather endpoint: {w.get('condition', '?')}, {w.get('temperature', '?')}°C")
else:
    ERR(f"Weather endpoint issue: {str(w)[:200]}")

# 2e. Saved trips list
r = client.get("/api/trips")
INF(f"GET /api/trips → {r.status_code}")
trips_list = json.loads(r.data)
if r.status_code == 200:
    n = len(trips_list.get("trips", []))
    OK(f"Trips list endpoint: {n} saved trips")
else:
    ERR(f"Trips list issue: {str(trips_list)[:200]}")

# 2f. Save and retrieve a test trip
save_payload = dict(plan_payload)
save_payload.update(TRIP_CTX)
r = client.post("/api/trips/save", json=save_payload)
INF(f"POST /api/trips/save → {r.status_code}")
save_resp = json.loads(r.data)
test_trip_id = save_resp.get("trip_id")
if r.status_code == 200 and test_trip_id:
    OK(f"Save trip: id={test_trip_id}")
    r2 = client.get(f"/api/trips/{test_trip_id}")
    if r2.status_code == 200:
        OK(f"Retrieve saved trip: {r2.status_code}")
    else:
        ERR(f"Retrieve trip failed: {r2.status_code}")
    # Clean up test trip
    client.delete(f"/api/trips/{test_trip_id}")
    OK("Test trip cleaned up")
else:
    ERR(f"Save trip failed: {str(save_resp)[:200]}")

# 2g. PDF endpoint
if TRIP_CTX:
    r = client.post("/api/trips/export-pdf", json=TRIP_CTX)
    INF(f"POST /api/trips/export-pdf → {r.status_code}, mime={r.mimetype}")
    if r.status_code == 200 and r.data[:4] == b"%PDF":
        OK(f"PDF endpoint: valid PDF, size={len(r.data):,} bytes")
    else:
        ERR(f"PDF endpoint issue: {r.status_code}, data start: {r.data[:30]}")

# 2h. Validation errors
r_bad1 = client.post("/api/plan", json={})
r_bad2 = client.post("/api/trips/export-pdf", json={})
r_bad3 = client.post("/api/plan", json={"destination": "Goa"})  # missing fields
INF(f"Validation — empty plan body → {r_bad1.status_code}")
INF(f"Validation — empty PDF body → {r_bad2.status_code}")
if r_bad1.status_code in (400, 422):
    OK("Empty plan body → correct 4xx error")
else:
    ERR(f"Empty plan body returned {r_bad1.status_code} not 4xx")
if r_bad2.status_code in (400, 422):
    OK("Empty PDF body → correct 4xx error")
else:
    ERR(f"Empty PDF body returned {r_bad2.status_code}")

# ════════════════════════════════════════════════════════════════════════
# TASK 3 — Chatbot Response Verification
# ════════════════════════════════════════════════════════════════════════
SECTION("TASK 3 — Chatbot Response Verification (7 questions)")

TRIP_CTX_FOR_CHAT = TRIP_CTX.copy() if TRIP_CTX else {"destination": "Goa", "travelers": 1, "currency": "INR"}
TRIP_CTX_FOR_CHAT["destination"] = "Goa"
TRIP_CTX_FOR_CHAT["start_location"] = "Visakhapatnam"

questions = [
    ("What are the best places to visit in Goa?",           ["baga", "fort aguada", "palolem", "basilica", "vagator", "anjuna", "calangute"]),
    ("What is the best time to visit Goa?",                 ["october", "november", "december", "january", "peak", "season"]),
    ("What transport options do I have?",                   ["train", "bus", "flight", "taxi", "car"]),
    ("How can I travel from Visakhapatnam to Goa?",         ["train", "bus", "flight", "km", "hour"]),
    ("Is ₹10,000 enough for a three-day solo Goa trip?",   ["accommodation", "transport", "budget", "₹"]),
    ("What should I visit on the second day?",              ["day 2", "morning", "afternoon", "evening"]),
    ("What is the distance between Baga Beach and Fort Aguada?", ["km", "baga", "fort aguada", "distance"]),
]

for q, kws in questions:
    r = generate_chat_response(q, trip_context=TRIP_CTX_FOR_CHAT)
    reply = r.get("reply", "")
    hits = [kw for kw in kws if kw.lower() in reply.lower()]
    ok = len(hits) >= 1
    status = "✅" if ok else "❌"
    print(f"\n  {status} Q: {q[:60]}")
    print(f"      Matched keywords: {hits}")
    print(f"      Source: {r.get('source_indicator', '?')}")
    print(f"      Reply: {reply[:200]}")

# ════════════════════════════════════════════════════════════════════════
# TASK 4 — Budget Verification (3-day solo Goa from Vizag)
# ════════════════════════════════════════════════════════════════════════
SECTION("TASK 4 — Budget Verification (3-day solo Goa, start=Visakhapatnam)")

trip3_solo = create_comprehensive_itinerary("Visakhapatnam", "Goa", "2026-12-10", "2026-12-12", 1, 999999)
ba = trip3_solo.get("budget_analysis", {})
cats = ba.get("categories", {})

accom    = cats.get("accommodation", {})
trans    = cats.get("transportation", {})
food     = cats.get("food", {})
sight    = cats.get("sightseeing", {})
misc     = cats.get("miscellaneous", {})

INF(f"Transport breakdown:")
INF(f"  Intercity one-way: ₹{trans.get('intercity_one_way_cost_inr', 0):,.0f}")
INF(f"  Intercity mode: {trans.get('intercity_mode', '?')}")
INF(f"  Local daily: ₹{trans.get('local_daily', 0):,.0f}")

print(f"\n  {'Category':<25} {'Per Person':>12} {'Total':>12}")
print(f"  {'-'*50}")
for label, cat in [
    ("Transportation", trans),
    ("Accommodation", accom),
    ("Food & Dining", food),
    ("Sightseeing", sight),
    ("Miscellaneous (7%)", misc),
]:
    pp = cat.get("per_person", cat.get("total", 0))
    tot = cat.get("total", 0)
    print(f"  {label:<25} {pp:>12,.0f} {tot:>12,.0f}")
print(f"  {'-'*50}")
est = ba.get("total_estimated_trip_cost", 0)
pp_est = ba.get("total_estimated_per_person", est)
print(f"  {'TOTAL ESTIMATED':<25} {pp_est:>12,.0f} {est:>12,.0f}")

avail = ba.get("available_budget_total", 0)
shortfall = ba.get("shortfall", 0)
INF(f"\n  Status: {ba.get('status_label', '?')}")
INF(f"  Is ₹10,000 enough for solo 3-day Goa? {'YES' if est <= 10000 else 'NO — estimated ₹' + f'{est:,.0f}'}")

# Double-counting check: add up cats manually vs ba.total
manual_sum = sum(cats.get(k, {}).get("total", 0) for k in ["accommodation", "transportation", "food", "sightseeing"])
misc_pct = misc.get("total", 0)
reconstructed = manual_sum + misc_pct
print(f"\n  Manual sum (excl misc): ₹{manual_sum:,.0f}")
print(f"  + Misc 7% buffer:       ₹{misc_pct:,.0f}")
print(f"  Reconstructed total:    ₹{reconstructed:,.0f}")
print(f"  Reported total:         ₹{est:,.0f}")
if abs(reconstructed - est) < 50:
    OK("No double-counting — totals match within ₹50")
else:
    ERR(f"Totals mismatch by ₹{abs(reconstructed - est):,.0f} — may indicate double-counting")

# ════════════════════════════════════════════════════════════════════════
# TASK 5 — Itinerary Verification (1, 3, 5, 7 days)
# ════════════════════════════════════════════════════════════════════════
SECTION("TASK 5 — Itinerary Verification")

for n_days in [1, 3, 5, 7]:
    start = "2026-12-10"
    end = (date.fromisoformat(start) + timedelta(days=n_days-1)).isoformat()
    trip = create_comprehensive_itinerary("Visakhapatnam", "Goa", start, end, 2, 50000)
    itin = trip.get("itinerary", [])

    print(f"\n  ── {n_days}-day Goa trip ──")
    if len(itin) != n_days:
        ERR(f"Expected {n_days} days, got {len(itin)}")
    else:
        OK(f"Day count correct: {n_days}")

    all_names = []
    filler_days = 0
    for d in itin:
        m = d.get("morning", {}).get("name", "")
        a = d.get("afternoon", {}).get("name", "")
        e = d.get("evening", {}).get("name", "")
        is_rest = d.get("is_rest_day", False)
        is_filler = any("Artisans" in x or "Bazaars" in x or "Cultural" in x and "Generic" in x for x in [m, a, e])
        if is_filler:
            filler_days += 1
        all_names.extend([m, a, e])
        flag = " [REST]" if is_rest else (" [FILLER?]" if is_filler else "")
        print(f"    Day {d.get('day_number')}{flag}: {m[:30]} / {a[:30]} / {e[:30]}")

    # Deduplication check
    dups = [n for n in all_names if all_names.count(n) > 1 and n]
    if dups:
        ERR(f"Duplicate attractions: {set(dups)}")
    else:
        OK("No duplicate attractions")

    if filler_days:
        ERR(f"{filler_days} filler day(s) detected")
    else:
        OK("No generic filler activities")

# ════════════════════════════════════════════════════════════════════════
# TASK 6 — PDF Verification
# ════════════════════════════════════════════════════════════════════════
SECTION("TASK 6 — PDF Verification")

try:
    from reportlab.lib.pagesizes import A4
    from io import BytesIO
    HAS_RL = True
except ImportError:
    HAS_RL = False

def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Count pages via /Page objects in raw PDF."""
    # Rough count using /Type /Page pattern
    pages = re.findall(rb"/Type\s*/Page\b", pdf_bytes)
    return len(pages)

def extract_pdf_text_sample(pdf_bytes: bytes, max_chars=2000) -> str:
    """Extract readable strings from PDF (BT/ET text blocks)."""
    # Very rough extraction — finds parenthetical strings in PDF streams
    strings = re.findall(rb"\(([^\)\\]{3,80})\)", pdf_bytes)
    decoded = []
    for s in strings[:100]:
        try:
            decoded.append(s.decode("latin-1"))
        except Exception:
            pass
    return " | ".join(decoded[:50])[:max_chars]

for n_days, label in [(1, "1-day"), (3, "3-day"), (7, "7-day"), (15, "15-day")]:
    start = "2026-12-10"
    end = (date.fromisoformat(start) + timedelta(days=n_days-1)).isoformat()
    trip = create_comprehensive_itinerary("Visakhapatnam", "Goa", start, end, 2, 50000)
    pdf_bytes = generate_trip_pdf(trip)
    page_count = count_pdf_pages(pdf_bytes)
    text_sample = extract_pdf_text_sample(pdf_bytes)
    is_valid = pdf_bytes[:4] == b"%PDF"
    has_days = all(f"Day {i}" in text_sample or f"Day {i}".encode() in pdf_bytes for i in range(1, min(n_days+1, 4)))

    print(f"\n  {label} PDF:")
    print(f"    Size: {len(pdf_bytes):,} bytes")
    print(f"    Valid PDF header: {'yes' if is_valid else 'NO'}")
    print(f"    Page objects found: {page_count}")
    print(f"    Text sample: {text_sample[:300]}")

    if is_valid:
        OK(f"{label}: valid PDF, ~{page_count} pages")
    else:
        ERR(f"{label}: INVALID PDF")

    if page_count > 1 or n_days == 1:
        OK(f"{label}: multi-page OK (pages={page_count})")
    else:
        ERR(f"{label}: only 1 page for {n_days} days — may be truncated")

# ════════════════════════════════════════════════════════════════════════
# TASK 7 — Database Verification
# ════════════════════════════════════════════════════════════════════════
SECTION("TASK 7 — Database Verification")

init_db()
all_trips = list_saved_trips()
thailand = [t for t in all_trips if t.get("destination", "").lower() == "thailand"]
INF(f"Total saved trips: {len(all_trips)}")
if thailand:
    t = thailand[0]
    OK(f"Thailand trip preserved: id={t['id']}, destination={t['destination']}")
else:
    ERR("Thailand trip MISSING!")

# Save a new test trip
test_trip_data = {
    "destination": "Mumbai", "start_location": "Pune",
    "start_date": "2027-01-10", "end_date": "2027-01-12",
    "travelers": 2, "currency": "INR",
    "budget_analysis": {"total_estimated_trip_cost": 8000}
}
new_id = save_trip(test_trip_data)
if new_id:
    OK(f"New test trip saved: id={new_id}")
    retrieved = get_trip(new_id)
    if retrieved and retrieved.get("destination") == "Mumbai":
        OK(f"Test trip retrieved correctly: destination={retrieved['destination']}")
    else:
        ERR("Test trip retrieval failed")
    delete_trip(new_id)
    confirm = get_trip(new_id)
    if confirm is None:
        OK("Test trip cleaned up (deleted)")
    else:
        ERR("Test trip delete failed")
else:
    ERR("Failed to save new test trip")

# Confirm Thailand still there after test operations
all_trips_after = list_saved_trips()
thailand_after = [t for t in all_trips_after if t.get("destination", "").lower() == "thailand"]
if thailand_after:
    OK("Thailand trip still intact after test operations")
else:
    ERR("Thailand trip was lost during test operations!")

# ════════════════════════════════════════════════════════════════════════
# TASK 8 — Frontend Static Analysis
# ════════════════════════════════════════════════════════════════════════
SECTION("TASK 8 — Frontend Static Analysis")

import pathlib

HTML_PATH  = pathlib.Path(r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot\templates\index.html")
JS_PATH    = pathlib.Path(r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot\static\app.js")
CSS_PATH   = pathlib.Path(r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot\static\style.css")

html = HTML_PATH.read_text(encoding="utf-8")
js   = JS_PATH.read_text(encoding="utf-8")
css  = CSS_PATH.read_text(encoding="utf-8")

# CSS/JS references
for asset, tag in [("app.js", 'src='), ("style.css", 'href=')]:
    if asset in html:
        OK(f"HTML references {asset}")
    else:
        ERR(f"HTML does NOT reference {asset}")

# API endpoint alignment
backend_routes = [
    ("/api/plan", "POST", "fetch.*api/plan"),
    ("/api/chat", "POST", "fetch.*api/chat"),
    ("/api/weather", "GET", "fetch.*api/weather"),
    ("/api/trips/save", "POST", "fetch.*api/trips/save"),
    ("/api/trips/export-pdf", "POST", "fetch.*export-pdf"),
]
for route, method, pattern in backend_routes:
    if re.search(pattern, js):
        OK(f"JS calls {method} {route}")
    else:
        ERR(f"JS does NOT call {method} {route} — pattern '{pattern}' not found")

# JavaScript null guard on renderActivitySlot
if "if (!slot) return '';" in js:
    OK("JS null guard on renderActivitySlot: present")
else:
    ERR("JS null guard on renderActivitySlot: MISSING")

# IntersectionObserver present (for feature/how-it-works card reveal)
if "IntersectionObserver" in js:
    OK("IntersectionObserver present in app.js")
else:
    ERR("IntersectionObserver missing from app.js")

# Check data-reveal attributes in HTML
if 'data-reveal' in html:
    count_reveal = html.count('data-reveal')
    OK(f"data-reveal attributes in HTML: {count_reveal}")
else:
    ERR("No data-reveal attributes in HTML")

# Check form fields exist
for field in ["start_location", "destination", "start_date", "end_date", "travelers", "budget"]:
    if field in html:
        OK(f"Form field '{field}' in HTML")
    else:
        ERR(f"Form field '{field}' MISSING from HTML")

# Check chatbot drawer
for kw in ["chatbot", "chat-drawer", "chatInput", "sendChat"]:
    if kw in html or kw in js:
        OK(f"Chatbot element '{kw}' present")
    else:
        ERR(f"Chatbot element '{kw}' missing")

# Check PDF download JS
if "export-pdf" in js:
    OK("PDF export JS present")
else:
    ERR("PDF export JS MISSING")

print("\n")
INF("All verification tasks complete.")
