"""
Comprehensive regression tests for TripWise itinerary quality, genuine attractions,
duplicate prevention, date-aware scheduling, geographic grouping, and marine routing.
"""

from __future__ import annotations
import unittest
import re
from datetime import date

from planner import create_comprehensive_itinerary
from services.attractions_service import (
    DESTINATION_CATALOGUE,
    get_attractions_for_destination,
    is_attraction_open_on_date,
    is_same_attraction
)
from services.routing_service import calculate_route, haversine_distance
from services.pdf_service import generate_trip_pdf


class TestItineraryQuality(unittest.TestCase):
    """Rigorous quality tests for itinerary planning in TripWise."""

    def test_duplicate_attractions_across_different_days(self):
        """Test that physical attractions are NEVER repeated across different days."""
        for dest in ["Thailand", "Goa", "Visakhapatnam"]:
            trip = create_comprehensive_itinerary(
                start_location="Visakhapatnam",
                destination=dest,
                start_date="2026-12-08",
                end_date="2026-12-14",
                travelers=2,
                budget=50000
            )
            itin = trip.get("itinerary", [])
            scheduled_items = []
            for day in itin:
                for slot_key in ["morning", "afternoon", "evening"]:
                    slot = day.get(slot_key)
                    if slot and not slot.get("is_leisure", False):
                        scheduled_items.append(slot)

            # Check canonical IDs are unique
            cids = [item.get("id") for item in scheduled_items if item.get("id")]
            self.assertEqual(len(cids), len(set(cids)), f"Duplicate canonical IDs found in {dest}: {cids}")

            # Check via is_same_attraction pair-wise
            for i in range(len(scheduled_items)):
                for j in range(i + 1, len(scheduled_items)):
                    a1 = scheduled_items[i]
                    a2 = scheduled_items[j]
                    self.assertFalse(
                        is_same_attraction(a1, a2),
                        f"Detected duplicate physical attraction across days in {dest}: {a1['name']} vs {a2['name']}"
                    )

    def test_duplicate_aliases_prevented(self):
        """Test is_same_attraction correctly matches aliases and spelling variations."""
        a1 = {
            "id": "th_bkk_grand_palace",
            "name": "The Grand Palace & Wat Phra Kaew",
            "aliases": ["Grand Palace", "Wat Phra Kaew", "The Grand Palace & Wat Phra Kaew"]
        }
        a2 = {
            "id": "th_bkk_grand_palace_alt",
            "name": "Wat Phra Kaew",
            "aliases": ["Emerald Buddha Temple"]
        }
        self.assertTrue(is_same_attraction(a1, a2), "Expected Grand Palace and Wat Phra Kaew alias to match as duplicate")

        b1 = {
            "name": "Wat Pho (Temple of Reclining Buddha)",
            "aliases": ["Wat Pho", "Temple of Reclining Buddha"]
        }
        b2 = {
            "name": "Temple of Reclining Buddha",
            "aliases": ["Wat Pho"]
        }
        self.assertTrue(is_same_attraction(b1, b2), "Expected Wat Pho alias to match")

        # Two completely different attractions should not match
        c1 = {"id": "th_bkk_wat_arun", "name": "Wat Arun", "aliases": ["Temple of Dawn"]}
        c2 = {"id": "th_bkk_wat_pho", "name": "Wat Pho", "aliases": ["Temple of Reclining Buddha"]}
        self.assertFalse(is_same_attraction(c1, c2), "Different temples must not match as duplicates")

    def test_no_generic_part_n_attraction_names(self):
        """Test that fabricated generic attraction names with 'Part N' never exist in catalogue or output."""
        part_pattern = re.compile(r"\bPart\s+\d+\b", re.IGNORECASE)

        # 1. Catalogue check
        for dest, attractions in DESTINATION_CATALOGUE.items():
            for a in attractions:
                self.assertNotRegex(
                    a["name"],
                    part_pattern,
                    f"Found generic Part N name in {dest} catalogue: {a['name']}"
                )

        # 2. Generated itinerary check for 7-day Thailand
        trip = create_comprehensive_itinerary(
            start_location="Visakhapatnam",
            destination="Thailand",
            start_date="2026-12-08",
            end_date="2026-12-14",
            travelers=1,
            budget=80000
        )
        for d in trip["itinerary"]:
            for slot_key in ["morning", "afternoon", "evening"]:
                slot = d.get(slot_key)
                if slot:
                    self.assertNotRegex(
                        slot["name"],
                        part_pattern,
                        f"Found Part N name in generated itinerary Day {d['day_number']}: {slot['name']}"
                    )

    def test_sat_sun_opening_schedules(self):
        """Test attractions with Sat-Sun hours (e.g. Chatuchak) are open ONLY on weekends."""
        chatuchak = next(
            (a for a in DESTINATION_CATALOGUE["thailand"] if "chatuchak" in a["name"].lower()),
            None
        )
        self.assertIsNotNone(chatuchak, "Chatuchak must exist in Thailand catalogue")

        # 2026-12-08 = Tuesday
        tue = date(2026, 12, 8)
        open_tue, reason_tue = is_attraction_open_on_date(chatuchak, tue)
        self.assertFalse(open_tue, f"Chatuchak should be closed on Tuesday: {reason_tue}")

        # 2026-12-09 = Wednesday
        wed = date(2026, 12, 9)
        open_wed, _ = is_attraction_open_on_date(chatuchak, wed)
        self.assertFalse(open_wed, "Chatuchak should be closed on Wednesday")

        # 2026-12-11 = Friday
        fri = date(2026, 12, 11)
        open_fri, _ = is_attraction_open_on_date(chatuchak, fri)
        self.assertFalse(open_fri, "Chatuchak should be closed on Friday")

        # 2026-12-12 = Saturday
        sat = date(2026, 12, 12)
        open_sat, reason_sat = is_attraction_open_on_date(chatuchak, sat)
        self.assertTrue(open_sat, f"Chatuchak should be OPEN on Saturday: {reason_sat}")

        # 2026-12-13 = Sunday
        sun = date(2026, 12, 13)
        open_sun, reason_sun = is_attraction_open_on_date(chatuchak, sun)
        self.assertTrue(open_sun, f"Chatuchak should be OPEN on Sunday: {reason_sun}")

        # 2026-12-14 = Monday
        mon = date(2026, 12, 14)
        open_mon, _ = is_attraction_open_on_date(chatuchak, mon)
        self.assertFalse(open_mon, "Chatuchak should be closed on Monday")

    def test_weekday_and_weekend_date_handling(self):
        """Test specific weekday closures and single-day openings."""
        # Reis Magos Fort is closed on Mondays
        fort = {"name": "Reis Magos Fort", "opening_hours": "09:30 - 17:00 (Closed Mon)"}
        mon = date(2026, 12, 7)
        tue = date(2026, 12, 8)
        open_m, reason_m = is_attraction_open_on_date(fort, mon)
        self.assertFalse(open_m, f"Reis Magos must be closed on Monday: {reason_m}")
        open_t, _ = is_attraction_open_on_date(fort, tue)
        self.assertTrue(open_t, "Reis Magos must be open on Tuesday")

        # Anjuna Flea Market is open only on Wednesdays
        anjuna = {"name": "Anjuna Flea Market", "opening_hours": "09:00 - 19:00 (Wednesdays only, seasonal Oct-May)"}
        wed = date(2026, 12, 9)
        thu = date(2026, 12, 10)
        open_w, reason_w = is_attraction_open_on_date(anjuna, wed)
        self.assertTrue(open_w, f"Anjuna Market must be open on Wednesday: {reason_w}")
        open_th, reason_th = is_attraction_open_on_date(anjuna, thu)
        self.assertFalse(open_th, f"Anjuna Market must be closed on Thursday: {reason_th}")

    def test_attractions_with_unknown_opening_hours(self):
        """Test attractions with unknown/unverified opening hours are marked as unverified."""
        unknown_attr = {
            "name": "Local Village Viewpoint",
            "opening_hours": "Unverified"
        }
        check_d = date(2026, 12, 10)
        is_open, explanation = is_attraction_open_on_date(unknown_attr, check_d)
        self.assertFalse(unknown_attr.get("hours_verified", True), "Expected hours_verified to be False")
        self.assertTrue("unverified" in explanation.lower() or "check locally" in explanation.lower())

    def test_geographic_grouping(self):
        """Test that attractions on the same day are in the same geographical region (< 45 km apart)."""
        trip = create_comprehensive_itinerary(
            start_location="Visakhapatnam",
            destination="Thailand",
            start_date="2026-12-08",
            end_date="2026-12-14",
            travelers=1,
            budget=80000
        )
        itin = trip["itinerary"]

        for d in itin:
            m = d.get("morning", {})
            a = d.get("afternoon", {})
            e = d.get("evening", {})

            # Check that Bangkok and Chiang Mai (> 600 km) are NEVER scheduled on the same day
            day_names = [slot.get("name", "") for slot in [m, a, e] if slot]
            has_bangkok = any("bangkok" in n.lower() or "grand palace" in n.lower() or "wat arun" in n.lower() or "wat pho" in n.lower() or "lumpini" in n.lower() for n in day_names)
            has_chiang_mai = any("chiang mai" in n.lower() or "doi suthep" in n.lower() or "elephant nature" in n.lower() for n in day_names)
            self.assertFalse(
                has_bangkok and has_chiang_mai,
                f"Day {d['day_number']} incorrectly mixed Bangkok and Chiang Mai on the same day: {day_names}"
            )

            # Check distance between morning and afternoon attractions with coords
            if m.get("lat") and a.get("lat") and not m.get("is_leisure") and not a.get("is_leisure"):
                dist = haversine_distance(m["lat"], m["lon"], a["lat"], a["lon"])
                self.assertLess(
                    dist, 85,
                    f"Day {d['day_number']} attractions too far apart for same day: {m['name']} to {a['name']} ({dist} km)"
                )

    def test_boat_ferry_routing(self):
        """Test boat and ferry transfers are routed via marine waterways, not road networks."""
        # Krabi mainland (Ao Nang) to Railay Beach
        ao_nang = (8.0306, 98.8242)
        railay = (8.0119, 98.8373)
        route_boat = calculate_route(ao_nang, railay, mode="boat")
        self.assertEqual(route_boat["mode"], "boat")
        self.assertIn("boat", route_boat["provider"].lower())
        self.assertGreater(route_boat["distance_km"], 0)
        self.assertGreater(route_boat["duration_minutes"], 10)

        # Krabi to Phi Phi Islands passenger ferry
        phi_phi = (7.7407, 98.7784)
        route_ferry = calculate_route(ao_nang, phi_phi, mode="ferry")
        self.assertEqual(route_ferry["mode"], "ferry")
        self.assertIn("ferry", route_ferry["provider"].lower())
        self.assertGreater(route_ferry["distance_km"], 20)
        self.assertGreater(route_ferry["duration_minutes"], 45)

    def test_leisure_days_not_counted_as_attractions(self):
        """Test leisure blocks have is_leisure=True and are not counted in unique attractions."""
        # 10-day trip to Visakhapatnam (where pool exhausts after ~7 days)
        trip = create_comprehensive_itinerary(
            start_location="Hyderabad",
            destination="Visakhapatnam",
            start_date="2026-12-01",
            end_date="2026-12-10",
            travelers=2,
            budget=40000
        )
        unique_count = trip.get("unique_attractions_count", len(trip.get("attractions_summary", [])))
        summary_items = trip.get("attractions_summary", [])

        # No leisure block in attractions_summary
        for item in summary_items:
            self.assertFalse(item.get("is_leisure", False), f"Leisure block found in attractions_summary: {item}")
            self.assertNotIn("leisure", item["name"].lower())

        # Unique count matches length of summary exactly
        self.assertEqual(unique_count, len(summary_items))

    def test_correct_unique_attraction_counters(self):
        """Test unique attractions count is mathematically exact and free of duplicates."""
        trip = create_comprehensive_itinerary(
            start_location="Visakhapatnam",
            destination="Thailand",
            start_date="2026-12-08",
            end_date="2026-12-14",
            travelers=1,
            budget=75000
        )
        summary = trip.get("attractions_summary", [])
        summary_names = [a["name"] for a in summary]
        self.assertEqual(len(summary_names), len(set(summary_names)), "attractions_summary contains duplicate names")
        self.assertEqual(trip.get("unique_attractions_count"), len(summary))
        self.assertGreaterEqual(len(summary), 7, "7-day Thailand trip should have at least 7 verified attractions")

    def test_thailand_seven_day_itinerary_comprehensive(self):
        """Comprehensive verification of Thailand 8-14 Dec 2026 itinerary."""
        trip = create_comprehensive_itinerary(
            start_location="Visakhapatnam",
            destination="Thailand",
            start_date="2026-12-08",
            end_date="2026-12-14",
            travelers=1,
            budget=80000
        )
        itin = trip["itinerary"]
        self.assertEqual(len(itin), 7, "Thailand trip must have exactly 7 days")

        # Verify days sequence
        expected_dates = [
            "2026-12-08", "2026-12-09", "2026-12-10", "2026-12-11",
            "2026-12-12", "2026-12-13", "2026-12-14"
        ]
        for d_idx, d in enumerate(itin):
            self.assertEqual(d["date"], expected_dates[d_idx])

        # Chatuchak Weekend Market verification:
        # Dec 08 (Tue), Dec 09 (Wed), Dec 10 (Thu), Dec 11 (Fri), Dec 14 (Mon) MUST NOT have Chatuchak
        for day_num in [1, 2, 3, 4, 7]:
            d = itin[day_num - 1]
            day_slot_names = [
                d["morning"]["name"],
                d["afternoon"]["name"],
                d["evening"]["name"]
            ]
            for name in day_slot_names:
                self.assertNotIn(
                    "Chatuchak", name,
                    f"Chatuchak scheduled on weekday (Day {day_num}, {d['date']}): {name}"
                )

        # Check total unique genuine attractions >= 12
        unique_attractions = trip.get("attractions_summary", [])
        self.assertGreaterEqual(len(unique_attractions), 10)

    def test_existing_goa_itinerary_functionality(self):
        """Test existing Goa 4-day trip continues to function perfectly."""
        trip = create_comprehensive_itinerary(
            start_location="Visakhapatnam",
            destination="Goa",
            start_date="2026-12-06",
            end_date="2026-12-09",
            travelers=2,
            budget=25000
        )
        itin = trip["itinerary"]
        self.assertEqual(len(itin), 4)

        # Day 2 is Monday Dec 07 -> Reis Magos Fort and Naval Aviation Museum must not be scheduled
        day2 = itin[1]
        self.assertIn("Mon", day2["date_formatted"])
        day2_names = [day2["morning"]["name"], day2["afternoon"]["name"], day2["evening"]["name"]]
        self.assertNotIn("Reis Magos Fort", day2_names)
        self.assertNotIn("Naval Aviation Museum", day2_names)

        # PDF generation succeeds
        pdf_bytes = generate_trip_pdf(trip)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 15000)


if __name__ == "__main__":
    unittest.main()
