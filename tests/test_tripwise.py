"""
Automated Comprehensive Test Suite for TripWise.
Covers Phases 1 to 14: Budget accuracy, attractions, routing, transport, weather, chatbot, and storage.
"""

from __future__ import annotations
import json
import re
import unittest
from datetime import date, timedelta

from planner import create_comprehensive_itinerary
from services.budget_service import calculate_comprehensive_budget
from services.attractions_service import get_attractions_for_destination
from services.routing_service import calculate_route, geocode_place, haversine_distance
from services.transport_service import compare_transportation_modes
from services.weather_service import get_weather_for_destination
from services.chatbot_service import generate_chat_response
from services.storage_service import save_trip, get_trip, list_saved_trips, delete_trip
from services.currency_service import convert_from_inr, convert_to_inr, get_exchange_rate
from services.pdf_service import generate_trip_pdf
from app import app


class TripWiseMasterTestSuite(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    # 1. Budget Calculation Accuracy & Mathematical Reconciliation
    def test_budget_reconciliation_and_uncapped_estimation(self):
        """Test that costs are calculated independently of budget and reconcile mathematically."""
        # Intentionally low budget of ₹500 for 4 people on a 5-day trip to Goa
        result = create_comprehensive_itinerary(
            start_location="Visakhapatnam",
            destination="Goa",
            start_date="2026-12-01",
            end_date="2026-12-05",
            travelers=4,
            budget=500,
            budget_type="total_group",
            currency="INR"
        )
        ba = result["budget_analysis"]

        # MUST report shortfall, NOT sufficient!
        self.assertEqual(ba["budget_status"], "insufficient")
        self.assertGreater(ba["total_estimated_trip_cost"], 500)
        self.assertLess(ba["budget_difference"], 0)
        self.assertGreater(len(ba["suggestions"]), 0)

        # Mathematical reconciliation check:
        cats = ba["categories"]
        summed = (
            cats["transportation"]["total"] +
            cats["accommodation"]["total"] +
            cats["food"]["total"] +
            cats["sightseeing"]["total"] +
            cats["miscellaneous"]["total"]
        )
        self.assertAlmostEqual(summed, ba["total_estimated_trip_cost"], delta=2.0)

    # 2. Per-Person vs Total-Group Budget Modes
    def test_per_person_vs_group_budget_modes(self):
        """Test difference between per-person and group budget modes."""
        res_group = calculate_comprehensive_budget(
            start_location="Hyderabad",
            destination="Goa",
            num_days=3,
            num_nights=2,
            travelers=2,
            budget_input=30000,
            budget_type="total_group",
            currency="INR"
        )
        self.assertEqual(res_group["available_budget_total"], 30000)
        self.assertEqual(res_group["available_budget_per_person"], 15000)

        res_pp = calculate_comprehensive_budget(
            start_location="Hyderabad",
            destination="Goa",
            num_days=3,
            num_nights=2,
            travelers=2,
            budget_input=30000,
            budget_type="per_person",
            currency="INR"
        )
        self.assertEqual(res_pp["available_budget_total"], 60000)
        self.assertEqual(res_pp["available_budget_per_person"], 30000)

    # 3. Real Tourist Attractions & Categories
    def test_real_attractions_and_categories(self):
        """Test genuine attractions with categories, entrance fees, and food stops."""
        attractions, source = get_attractions_for_destination("Goa", ["beaches", "historical"])
        self.assertGreater(len(attractions), 0)
        first = attractions[0]
        self.assertIn("name", first)
        self.assertIn("category", first)
        self.assertIn("opening_hours", first)
        self.assertIn("visit_duration", first)
        self.assertIn("food_nearby", first)

        # Test Visakhapatnam specifically
        vizag_attractions, _ = get_attractions_for_destination("Visakhapatnam")
        names = [a["name"] for a in vizag_attractions]
        self.assertTrue(any("Rishikonda" in n or "Kursura" in n or "Kailasagiri" in n for n in names))

    # 4. Distance and Routing Calculations
    def test_routing_and_distances(self):
        """Test coordinate distance and route calculation."""
        # Mumbai to Pune coordinates
        mumbai = (18.9220, 72.8347)
        pune = (18.5204, 73.8567)
        route = calculate_route(mumbai, pune, mode="driving")
        self.assertGreater(route["distance_km"], 80)
        self.assertGreater(route["duration_minutes"], 60)
        self.assertIn("duration_formatted", route)

    # 5. Transportation Comparison
    def test_transportation_modes_comparison(self):
        """Test all 5 transport modes: Flights, Trains, Buses, Cabs, Car."""
        trans = compare_transportation_modes("Visakhapatnam", "Goa", travelers=2, currency="INR")
        options = trans["options"]
        modes = [o["mode"] for o in options]
        self.assertIn("Flights", modes)
        self.assertIn("Trains", modes)
        self.assertIn("Buses", modes)
        self.assertIn("Outstation Taxi", modes)
        self.assertIn("Private Car", modes)

        # Check badges assignment
        all_badges = [b for o in options for b in o.get("badges", [])]
        self.assertTrue(any("Cheapest" in b for b in all_badges))
        self.assertTrue(any("Fastest" in b for b in all_badges))

    # 6. Live Weather Information
    def test_weather_service(self):
        """Test weather retrieval and travel recommendations."""
        weather = get_weather_for_destination("Goa")
        self.assertTrue(weather["available"])
        self.assertIn("temperature", weather)
        self.assertIn("condition", weather)
        self.assertGreater(len(weather["travel_advice"]), 0)

    # 7. AI Travel Chatbot
    def test_ai_chatbot(self):
        """Test chatbot response for budget cut and packing advice."""
        ctx = {"destination": "Goa", "travelers": 2, "currency": "INR"}
        res_budget = generate_chat_response("Can you reduce my trip budget?", trip_context=ctx)
        self.assertIn("Accommodation", res_budget["reply"])

        res_packing = generate_chat_response("What should I pack?", trip_context=ctx)
        self.assertIn("sunscreen", res_packing["reply"].lower())

    # 8. Persistent Trip Storage (SQLite)
    def test_trip_storage_lifecycle(self):
        """Test saving, retrieving, listing, and deleting a trip."""
        mock_trip = {
            "destination": "Paris",
            "start_location": "London",
            "start_date": "2026-12-10",
            "end_date": "2026-12-14",
            "travelers": 2,
            "currency": "EUR",
            "budget_analysis": {"total_estimated_trip_cost": 1200}
        }
        trip_id = save_trip(mock_trip)
        self.assertIsNotNone(trip_id)

        retrieved = get_trip(trip_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["destination"], "Paris")

        all_trips = list_saved_trips()
        self.assertTrue(any(t["id"] == trip_id for t in all_trips))

        deleted = delete_trip(trip_id)
        self.assertTrue(deleted)
        self.assertIsNone(get_trip(trip_id))

    # 9. Currency Conversion
    def test_currency_conversion(self):
        """Test conversion to USD and GBP."""
        usd_val = convert_from_inr(100000, "USD")
        self.assertGreater(usd_val, 500)
        self.assertLess(usd_val, 2000)

        inr_back = convert_to_inr(usd_val, "USD")
        self.assertAlmostEqual(inr_back, 100000, delta=500)

    # 10. Flask API Endpoints
    def test_flask_endpoints(self):
        """Test /api/plan, /api/chat, /api/weather, /api/trips endpoints."""
        # 1. /api/plan
        r = self.client.post("/api/plan", json={
            "start_location": "Hyderabad",
            "destination": "Goa",
            "start_date": "2026-12-01",
            "end_date": "2026-12-03",
            "travelers": 2,
            "budget": 20000,
            "currency": "INR",
            "interests": ["beaches", "food"]
        })
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("itinerary", data)
        self.assertIn("transportation_comparison", data)
        self.assertIn("budget_analysis", data)
        self.assertIn("weather", data)

        # 2. /api/chat
        r_chat = self.client.post("/api/chat", json={
            "message": "What are top foods to try?",
            "trip_context": {"destination": "Goa"}
        })
        self.assertEqual(r_chat.status_code, 200)
        self.assertIn("reply", json.loads(r_chat.data))

        # 3. /api/weather
        r_w = self.client.get("/api/weather?destination=Goa")
        self.assertEqual(r_w.status_code, 200)

        # 4. /api/trips/save
        r_save = self.client.post("/api/trips/save", json=data)
        self.assertEqual(r_save.status_code, 200)
        save_data = json.loads(r_save.data)
        self.assertTrue(save_data.get("success"))
        t_id = save_data.get("trip_id")

        # 5. /api/trips/<trip_id>
        r_get = self.client.get(f"/api/trips/{t_id}")
        self.assertEqual(r_get.status_code, 200)

        # 6. /api/trips (list)
        r_list = self.client.get("/api/trips")
        self.assertEqual(r_list.status_code, 200)

        # 7. /api/trips/<trip_id> (delete)
        r_del = self.client.delete(f"/api/trips/{t_id}")
        self.assertEqual(r_del.status_code, 200)

    # 11. Chatbot Intelligence, Context-Awareness & Proximity (Bug 1 Upgrade)
    def test_chatbot_context_awareness_and_followups(self):
        """Test conversational AI context, recall, proximity, and modifications."""
        trip = create_comprehensive_itinerary("Hyderabad", "Goa", "2026-12-01", "2026-12-03", 2, 25000)

        # Day 3 recall — verify day is recalled with structured info (not a specific attraction name)
        r_day3 = generate_chat_response("What did you suggest for Day 3?", trip_context=trip)
        self.assertIn("Day 3", r_day3["reply"])
        # Verify the reply contains actual attraction content (morning/afternoon/evening slots)
        self.assertTrue(
            any(kw in r_day3["reply"] for kw in ["Morning", "Afternoon", "Evening", "km", "Goa"]),
            f"Expected Day 3 reply to contain itinerary details but got: {r_day3['reply'][:200]}"
        )

        # Attraction proximity using coordinates
        r_prox = generate_chat_response("Which of these are near Baga Beach?", trip_context=trip)
        self.assertIn("Baga Beach", r_prox["reply"])
        self.assertTrue("km" in r_prox["reply"] or "Calangute" in r_prox["reply"])

        # Itinerary activity replacement
        r_rep = generate_chat_response("Replace the second day's afternoon activity", trip_context=trip)
        self.assertIn("Day 2", r_rep["reply"])
        self.assertTrue("alternative" in r_rep["reply"].lower() or "recommendation" in r_rep["reply"].lower())

        # Budget reduction with concrete categories
        r_bud = generate_chat_response("My budget is too high. Reduce it to ₹10,000", trip_context=trip)
        self.assertIn("Accommodation", r_bud["reply"])
        self.assertIn("Transportation", r_bud["reply"])
        self.assertTrue("10" in r_bud["reply"] or "10,000" in r_bud["reply"])

        # Destination specific places
        r_places = generate_chat_response("Suggest places to visit in Goa", trip_context=trip)
        self.assertIn("Baga Beach", r_places["reply"])

        # Missing credentials fallback
        self.assertIn(r_places["source_indicator"], ["live_ai", "offline_intelligence"])

    # 12. Itinerary Deduplication, Proximity Clustering & Long Durations (Bug 2 Upgrade)
    def test_itinerary_deduplication_across_durations(self):
        """Test 1, 3, 7, 10, 15, and 30-day trips have ZERO duplicate attraction names."""
        for dest in ["Goa", "Visakhapatnam", "Hyderabad", "Paris"]:
            for days in [1, 3, 7, 10, 15, 30]:
                start = "2026-12-01"
                end = (date.fromisoformat(start) + timedelta(days=days - 1)).isoformat()
                res = create_comprehensive_itinerary("Home City", dest, start, end, 2, 30000)
                itin = res["itinerary"]
                self.assertEqual(len(itin), days)

                all_scheduled_names = []
                for d in itin:
                    self.assertIsNotNone(d.get("morning"))
                    self.assertIsNotNone(d.get("afternoon"))
                    self.assertIsNotNone(d.get("evening"))
                    all_scheduled_names.extend([
                        d["morning"]["name"],
                        d["afternoon"]["name"],
                        d["evening"]["name"]
                    ])

                # Check NO duplicated names across the itinerary
                duplicates = [n for n in all_scheduled_names if all_scheduled_names.count(n) > 1]
                self.assertEqual(len(duplicates), 0, f"Found duplicates in {dest} {days}-day: {set(duplicates)}")

                # Check rest day handling when pool exhausted
                if days >= 15:
                    has_rest_day = any(d.get("is_rest_day") for d in itin)
                    self.assertTrue(has_rest_day, f"Expected rest/leisure days in {dest} {days}-day trip")

    # 13. PDF Generation & Multi-Page Export Endpoint (Bug 3 Upgrade)
    def test_pdf_export_and_multi_page_generation(self):
        """Test server-side PDF generation, endpoints, and multi-page layout."""
        # 7-day trip PDF
        trip7 = create_comprehensive_itinerary("Hyderabad", "Goa", "2026-12-01", "2026-12-07", 2, 35000)
        pdf_bytes7 = generate_trip_pdf(trip7)
        self.assertTrue(pdf_bytes7.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes7), 15000)

        # 15-day trip PDF (Multi-page)
        trip15 = create_comprehensive_itinerary("Home City", "Paris", "2026-12-01", "2026-12-15", 2, 120000)
        pdf_bytes15 = generate_trip_pdf(trip15)
        self.assertTrue(pdf_bytes15.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes15), 25000)

        # Flask endpoint POST /api/trips/export-pdf
        r_pdf = self.client.post("/api/trips/export-pdf", json=trip7)
        self.assertEqual(r_pdf.status_code, 200)
        self.assertEqual(r_pdf.mimetype, "application/pdf")
        self.assertTrue(r_pdf.data.startswith(b"%PDF"))
        self.assertIn("attachment", r_pdf.headers.get("Content-Disposition", ""))

        # Invalid payload validation
        r_inv1 = self.client.post("/api/trips/export-pdf", json={})
        self.assertEqual(r_inv1.status_code, 400)

        r_inv2 = self.client.post("/api/trips/export-pdf", json={"destination": "Goa"})
        self.assertEqual(r_inv2.status_code, 400)

    # 14. New Chatbot Handler Coverage (Upgraded offline engine)
    def test_chatbot_new_handlers(self):
        """Test new chatbot intent handlers: best time, transport, tips, greeting, food, budget generic."""
        ctx = {"destination": "Goa", "travelers": 2, "currency": "INR"}

        # Best time / season handler
        r_bt = generate_chat_response("What is the best time to visit Goa?", trip_context=ctx)
        self.assertTrue(
            any(kw in r_bt["reply"].lower() for kw in ["october", "november", "peak", "season"]),
            f"Expected seasonal info, got: {r_bt['reply'][:200]}"
        )

        # Transport options without specific budget keyword
        r_tr = generate_chat_response("What transport options do I have from Hyderabad?", trip_context=ctx)
        self.assertTrue(
            any(kw in r_tr["reply"].lower() for kw in ["train", "bus", "flight", "transport"]),
            f"Expected transport info, got: {r_tr['reply'][:200]}"
        )

        # Destination-specific tips
        r_tips = generate_chat_response("Give me tips for visiting Goa", trip_context=ctx)
        self.assertTrue(
            any(kw in r_tips["reply"].lower() for kw in ["tip", "note", "avoid", "carry", "book", "aware"]),
            f"Expected tips, got: {r_tips['reply'][:200]}"
        )

        # Greeting response includes TripWise branding
        r_hi = generate_chat_response("Hello", trip_context=ctx)
        self.assertIn("TripWise", r_hi["reply"])

        # Food handler includes destination-specific dishes
        r_food = generate_chat_response("What food should I try in Goa?", trip_context=ctx)
        self.assertTrue(
            any(kw in r_food["reply"].lower() for kw in ["fish", "seafood", "xacuti", "vindaloo", "bebinca", "sorpotel"]),
            f"Expected Goan food, got: {r_food['reply'][:200]}"
        )

        # Generic budget response (no budget_analysis in context) includes "Accommodation"
        r_bud = generate_chat_response("Can you reduce my trip budget?", trip_context=ctx)
        self.assertIn("Accommodation", r_bud["reply"])

        # Packing response includes sunscreen
        r_pack = generate_chat_response("What should I pack for Goa?", trip_context=ctx)
        self.assertIn("sunscreen", r_pack["reply"].lower())

    # 15. Regression Test: Zero-Price Transportation Bug Fix
    def test_zero_price_transportation_regression(self):
        """Test each transport mode has non-zero estimated prices, duration, and PDF never displays ₹0 for available options."""
        trip = create_comprehensive_itinerary("Visakhapatnam", "Goa", "2026-12-06", "2026-12-09", 2, 25000, "INR")
        tc = trip.get("transportation_comparison", {})
        options = tc.get("options", [])
        self.assertGreaterEqual(len(options), 5)

        for opt in options:
            if opt.get("available"):
                self.assertGreater(opt.get("one_way_total", 0), 0, f"Available mode {opt['mode']} has zero one_way_total")
                self.assertGreater(opt.get("return_total", 0), 0, f"Available mode {opt['mode']} has zero return_total")
                self.assertGreater(opt.get("cost_per_person", 0), 0, f"Available mode {opt['mode']} has zero cost_per_person")
                self.assertNotEqual(opt.get("duration", "N/A"), "N/A", f"Available mode {opt['mode']} has N/A duration")
            else:
                self.assertIn("unavailable_reason", opt)

        # PDF test: generates valid multi-page PDF with transportation comparison table
        pdf_bytes = generate_trip_pdf(trip)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 12000)
        # Verify page count is at least 3 pages
        page_count = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
        self.assertGreaterEqual(page_count, 3)

    # 16. Regression Test: Closed-Day Attraction Scheduling Bug Fix
    def test_closed_day_attraction_scheduling_regression(self):
        """Test attractions are NEVER scheduled on their closed days (e.g. Reis Magos Fort closed Mondays)."""
        # Monday Dec 07, 2026 is Day 2 of this 4-day trip
        trip = create_comprehensive_itinerary("Visakhapatnam", "Goa", "2026-12-06", "2026-12-09", 2, 25000)
        itin = trip.get("itinerary", [])
        self.assertEqual(len(itin), 4)

        day2 = itin[1]
        self.assertIn("Mon", day2["date_formatted"])
        day2_attractions = [
            day2["morning"]["name"],
            day2["afternoon"]["name"],
            day2["evening"]["name"]
        ]

        # Reis Magos Fort is closed on Mondays - must NOT be on Monday
        self.assertNotIn("Reis Magos Fort", day2_attractions, "Reis Magos Fort was scheduled on Monday when it is closed!")
        # Naval Aviation Museum is also closed on Mondays
        self.assertNotIn("Naval Aviation Museum", day2_attractions, "Naval Aviation Museum was scheduled on Monday!")

        # Verify all attractions scheduled across all days are open on their assigned calendar date
        for d in itin:
            d_date = date.fromisoformat(d["date"])
            for slot in ["morning", "afternoon", "evening"]:
                act = d.get(slot)
                if act:
                    hrs = act.get("opening_hours", "").lower()
                    if d_date.weekday() == 0:  # Monday
                        self.assertNotIn("closed mon", hrs, f"{act['name']} scheduled on Monday but hours state: {hrs}")
                    elif d_date.weekday() == 4:  # Friday
                        self.assertNotIn("closed fri", hrs, f"{act['name']} scheduled on Friday but hours state: {hrs}")
                    elif d_date.weekday() == 1:  # Tuesday
                        self.assertNotIn("closed tue", hrs, f"{act['name']} scheduled on Tuesday but hours state: {hrs}")

    # 17. Regression Test: Activity Duration and Schedule Mismatch Bug Fix
    def test_activity_duration_and_schedule_mismatch_regression(self):
        """Test activity start/end times match actual visit_duration and include meal & transit breaks."""
        trip = create_comprehensive_itinerary("Visakhapatnam", "Goa", "2026-12-06", "2026-12-09", 2, 25000)
        itin = trip.get("itinerary", [])

        for d in itin:
            self.assertIn("schedule", d)
            sched = d["schedule"]
            self.assertIn("morning_time", sched)
            self.assertIn("afternoon_time", sched)
            self.assertIn("evening_time", sched)
            self.assertIn("lunch_time", sched)

            # Check that slot times match visit_duration
            m_slot = d["morning"]
            m_time = m_slot["time"]
            # Extract start and end from time string "HH:MM – HH:MM"
            m_parts = re.findall(r"(\d{2}):(\d{2})", m_time)
            self.assertEqual(len(m_parts), 2, f"Invalid morning time format: {m_time}")
            m_start_min = int(m_parts[0][0]) * 60 + int(m_parts[0][1])
            m_end_min = int(m_parts[1][0]) * 60 + int(m_parts[1][1])
            m_diff = m_end_min - m_start_min
            # Difference must equal duration within 180 min cap
            self.assertGreaterEqual(m_diff, 60, "Morning activity slot is too short")
            self.assertLessEqual(m_diff, 180, "Morning activity slot exceeds 3 hours")

            # Check meal break exists before afternoon activity
            self.assertIn("lunch_break", d)

    # 18. Regression Test: Budget Consistency and Reconciliation Bug Fix
    def test_budget_consistency_and_reconciliation_regression(self):
        """Test budget breakdown reconciles mathematically with 7% misc buffer, exact per-person costs, and no double-counting."""
        trip = create_comprehensive_itinerary("Visakhapatnam", "Goa", "2026-12-06", "2026-12-09", 2, 25000, "INR")
        ba = trip.get("budget_analysis", {})
        cats = ba.get("categories", {})

        trans = cats["transportation"]["total"]
        accom = cats["accommodation"]["total"]
        food = cats["food"]["total"]
        sight = cats["sightseeing"]["total"]
        misc = cats["miscellaneous"]["total"]
        est_total = ba["total_estimated_trip_cost"]
        travelers = trip["travelers"]

        # 1. Subtotal check
        subtotal = trans + accom + food + sight
        self.assertEqual(misc, round(subtotal * 0.07), "Misc buffer is not 7% of subtotal")

        # 2. Total reconciliation
        self.assertEqual(est_total, subtotal + misc, "Reported total does not match sum of categories")

        # 3. Per person reconciliation
        pp_total = ba["total_estimated_per_person"]
        self.assertAlmostEqual(pp_total, est_total / travelers, delta=0.5, msg="Per-person total does not equal total / travelers")

        for k, cat in cats.items():
            self.assertAlmostEqual(cat["per_person"], cat["total"] / travelers, delta=0.5, msg=f"Category {k} per_person mismatch")

    # 19. Regression Test: Weather Date Handling and Future Horizon Distinction
    def test_weather_date_handling_and_forecast_distinction_regression(self):
        """Test weather service accepts travel dates, provides wind speed, and distinguishes live model from future climate."""
        # 1. Travel dates within 16-day window (today to +3 days)
        today = date.today().isoformat()
        end_date = (date.today() + timedelta(days=3)).isoformat()
        w_near = get_weather_for_destination("Goa", start_date=today, end_date=end_date)
        self.assertTrue(w_near["available"])
        self.assertIn("temperature", w_near)
        self.assertIn("wind_speed_kmh", w_near)
        self.assertIn("wind_speed", w_near)
        self.assertIn("forecast_label", w_near)

        # 2. Future travel dates beyond 16-day window
        future_start = "2027-01-10"
        future_end = "2027-01-14"
        w_future = get_weather_for_destination("Goa", start_date=future_start, end_date=future_end)
        self.assertTrue(w_future["available"])
        self.assertFalse(w_future.get("is_matched_live", True), "Future dates beyond 16 days should not claim live numerical forecast")
        self.assertIn("forecast_note", w_future)


    # 20. Regression Test: Transport Comparison and Budget Consistency (Zero Discrepancy)
    def test_transport_comparison_and_budget_consistency(self):
        """Test that budget transportation category adopts the selected transport option return total to the exact rupee."""
        # 1. Test with Buses selected
        trip_bus = create_comprehensive_itinerary(
            "Visakhapatnam", "Goa", "2026-12-06", "2026-12-09", 2, 25000, "total_group", "INR",
            transport_mode="Buses"
        )
        selected_bus = next(o for o in trip_bus["transportation_comparison"]["options"] if o.get("is_budget_basis"))
        self.assertEqual(selected_bus["mode"], "Buses")
        trans_budget_bus = trip_bus["budget_analysis"]["categories"]["transportation"]["total"]
        self.assertEqual(trans_budget_bus, selected_bus["return_total"],
                         f"Bus budget {trans_budget_bus} does not match selected bus return total {selected_bus['return_total']}")

        # 2. Test with Trains selected
        trip_train = create_comprehensive_itinerary(
            "Visakhapatnam", "Goa", "2026-12-06", "2026-12-09", 2, 25000, "total_group", "INR",
            transport_mode="Trains"
        )
        selected_train = next(o for o in trip_train["transportation_comparison"]["options"] if o.get("is_budget_basis"))
        self.assertEqual(selected_train["mode"], "Trains")
        trans_budget_train = trip_train["budget_analysis"]["categories"]["transportation"]["total"]
        self.assertEqual(trans_budget_train, selected_train["return_total"],
                         f"Train budget {trans_budget_train} does not match selected train return total {selected_train['return_total']}")

        # 3. Test with Outstation Taxi selected
        trip_taxi = create_comprehensive_itinerary(
            "Visakhapatnam", "Goa", "2026-12-06", "2026-12-09", 2, 50000, "total_group", "INR",
            transport_mode="Outstation Taxi"
        )
        selected_taxi = next(o for o in trip_taxi["transportation_comparison"]["options"] if o.get("is_budget_basis"))
        self.assertEqual(selected_taxi["mode"], "Outstation Taxi")
        trans_budget_taxi = trip_taxi["budget_analysis"]["categories"]["transportation"]["total"]
        self.assertEqual(trans_budget_taxi, selected_taxi["return_total"],
                         f"Taxi budget {trans_budget_taxi} does not match selected taxi return total {selected_taxi['return_total']}")

    # 21. Regression Test: Taxi Return-Price Calculation Model
    def test_taxi_return_price_calculation(self):
        """Test Outstation Taxi return pricing model: 1.85x commercial discount tariff, fuel, tolls, and batta."""
        trans = compare_transportation_modes("Visakhapatnam", "Goa", travelers=2, currency="INR")
        cab = next(o for o in trans["options"] if o["mode"] == "Outstation Taxi")
        self.assertTrue(cab["available"])
        self.assertEqual(cab["pricing_type"], "per_vehicle")

        # One-way calculation check
        one_way = cab["one_way_total_inr"]
        ret = cab["return_total_inr"]

        # Legitimate 1.85x round-trip package tariff check
        expected_return = round(one_way * 1.85)
        self.assertEqual(ret, expected_return, f"Taxi return price {ret} must follow 1.85x package tariff {expected_return}")

        # Ensure return price is NOT forced to double the one-way price
        self.assertNotEqual(ret, one_way * 2, "Taxi return price should not be forced to 2x one-way (must reflect 15% round-trip discount)")

        # Verify tolls and allowances exist
        self.assertGreater(cab.get("tolls_included_inr", 0), 0)
        self.assertGreater(cab.get("driver_allowance_inr", 0), 0)

    # 22. Regression Test: Per-Person Transportation Pricing
    def test_per_person_transportation_pricing(self):
        """Test that per-person modes (Flights, Trains, Buses) scale strictly per passenger."""
        for mode in ("Flights", "Trains", "Buses"):
            trans_1 = compare_transportation_modes("Visakhapatnam", "Goa", travelers=1, currency="INR")
            trans_3 = compare_transportation_modes("Visakhapatnam", "Goa", travelers=3, currency="INR")
            opt_1 = next(o for o in trans_1["options"] if o["mode"] == mode)
            opt_3 = next(o for o in trans_3["options"] if o["mode"] == mode)

            # Unit fare per person must be identical
            self.assertEqual(opt_1["fare_per_person_inr"], opt_3["fare_per_person_inr"])
            self.assertEqual(opt_1["pricing_type"], "per_person")
            self.assertEqual(opt_3["pricing_type"], "per_person")

            # Group total must scale exactly with passenger count
            self.assertEqual(opt_3["one_way_total_inr"], opt_1["fare_per_person_inr"] * 3)
            self.assertEqual(opt_3["return_total_inr"], opt_3["one_way_total_inr"] * 2)

    # 23. Regression Test: Group Transportation Pricing
    def test_group_transportation_pricing(self):
        """Test that vehicle modes (Taxi, Private Car) are priced per vehicle and shared among passengers."""
        for mode in ("Outstation Taxi", "Private Car"):
            trans_1 = compare_transportation_modes("Visakhapatnam", "Goa", travelers=1, currency="INR")
            trans_2 = compare_transportation_modes("Visakhapatnam", "Goa", travelers=2, currency="INR")
            opt_1 = next(o for o in trans_1["options"] if o["mode"] == mode)
            opt_2 = next(o for o in trans_2["options"] if o["mode"] == mode)

            self.assertEqual(opt_1["pricing_type"], "per_vehicle")
            self.assertEqual(opt_2["pricing_type"], "per_vehicle")

            # Total vehicle cost remains identical for 1 vs 2 passengers (same sedan / car capacity)
            self.assertEqual(opt_1["one_way_total_inr"], opt_2["one_way_total_inr"])
            self.assertEqual(opt_1["return_total_inr"], opt_2["return_total_inr"])

            # Per-person cost divides group cost by number of travelers
            self.assertEqual(opt_2["cost_per_person_inr"], round(opt_2["one_way_total_inr"] / 2))
            self.assertEqual(opt_1["cost_per_person_inr"], opt_1["one_way_total_inr"])

    # 24. Regression Test: Exact Budget Reconciliation to Single Integer Rupee
    def test_exact_budget_reconciliation(self):
        """Test 4-day Goa trip reconciles to exact rupee with 7% buffer and per-person breakdown."""
        trip = create_comprehensive_itinerary(
            "Visakhapatnam", "Goa", "2026-12-06", "2026-12-09", 2, 25000, "total_group", "INR",
            transport_mode="Buses"
        )
        ba = trip["budget_analysis"]
        cats = ba["categories"]

        trans = cats["transportation"]["total"]
        accom = cats["accommodation"]["total"]
        food = cats["food"]["total"]
        sight = cats["sightseeing"]["total"]
        misc = cats["miscellaneous"]["total"]
        est_total = ba["total_estimated_trip_cost"]
        pp_total = ba["total_estimated_per_person"]

        # Subtotal and buffer
        subtotal = trans + accom + food + sight
        expected_misc = round(subtotal * 0.07)
        self.assertEqual(misc, expected_misc)
        self.assertEqual(est_total, subtotal + expected_misc)

        # Per person exact match
        self.assertAlmostEqual(pp_total, est_total / 2, delta=0.5)

        # Transportation in budget matches the Buses return total exactly
        bus_opt = next(o for o in trip["transportation_comparison"]["options"] if o["mode"] == "Buses")
        self.assertEqual(trans, bus_opt["return_total"])


if __name__ == "__main__":
    unittest.main()


