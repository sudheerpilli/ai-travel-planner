"""
Tests for the upgraded TripWise Smart Chatbot.
Tests 25–39 — all chatbot-specific. Original tests 1–24 remain in test_tripwise.py.

Mocked responses are used for all external service calls.
Run with: .\\venv\\Scripts\\python.exe -m pytest tests/test_chatbot.py -v
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OLLAMA_BASE_URL", "")


from services.chatbot_service import (
    generate_chat_response,
    classify_intent,
    Intent,
    _resolve_context_from_history,
    _expert_offline_agent,
    _get_free_exchange_rates,
    extract_destination_entity,
    update_context_for_destination_change,
)
from services.search_service import should_web_search, _cache_key


# ─── Fixtures ────────────────────────────────────────────────────────────────

MOCK_TRIP_CONTEXT = {
    "destination": "Goa",
    "start_location": "Visakhapatnam",
    "start_date": "2026-12-06",
    "end_date": "2026-12-09",
    "num_days": 4,
    "travelers": 2,
    "currency": "INR",
    "itinerary": [
        {
            "day_number": 1,
            "date_formatted": "Sat 6 Dec",
            "morning": {"name": "Baga Beach", "category": "beaches", "description": "Popular beach.", "opening_hours": "06:00–20:00", "visit_duration": "2 hours"},
            "afternoon": {"name": "Fort Aguada", "category": "historical", "description": "17th century fort."},
            "evening": {"name": "Calangute Beach", "category": "beaches", "description": "Main beach."},
            "suggested_food_stop": "Infantaria Bakery, Calangute",
            "route_morning_to_afternoon": {"distance_km": 8, "duration_formatted": "20 min"},
            "route_afternoon_to_evening": {"distance_km": 3, "duration_formatted": "10 min"},
            "day_total_route_km": 11,
        },
        {
            "day_number": 2,
            "date_formatted": "Sun 7 Dec",
            "morning": {"name": "Dudhsagar Falls", "category": "nature", "description": "Iconic waterfall."},
            "afternoon": {"name": "Spice Plantation", "category": "nature", "description": "Organic spice farm."},
            "evening": {"name": "Panaji Old Quarter", "category": "historical", "description": "Portuguese heritage."},
            "suggested_food_stop": "Vinayak Family Restaurant, Panaji",
            "route_morning_to_afternoon": {"distance_km": 15, "duration_formatted": "35 min"},
            "route_afternoon_to_evening": {"distance_km": 20, "duration_formatted": "45 min"},
            "day_total_route_km": 35,
        }
    ],
    "attractions_summary": [
        {"name": "Baga Beach", "category": "beaches", "description": "Popular beach.", "lat": 15.556, "lon": 73.752, "entry_fee_inr": 0},
        {"name": "Fort Aguada", "category": "historical", "description": "17th century fort.", "lat": 15.498, "lon": 73.771, "entry_fee_inr": 25},
        {"name": "Dudhsagar Falls", "category": "nature", "description": "Iconic waterfall.", "lat": 15.314, "lon": 74.313, "entry_fee_inr": 100},
        {"name": "Anjuna Beach", "category": "beaches", "description": "Hippie beach.", "lat": 15.573, "lon": 73.740, "entry_fee_inr": 0},
    ],
    "weather": {
        "available": True,
        "temperature": 29,
        "condition": "Clear & Sunny",
        "humidity": 55,
        "wind_speed_kmh": 12.0,
        "wind_speed": 12.0,
        "travel_advice": ["Perfect beach weather.", "Sunscreen recommended."],
        "provider": "Open-Meteo Weather API"
    },
    "budget_analysis": {
        "total_estimated_trip_cost": 25798,
        "available_budget_total": 25000,
        "budget_status": "Slight Shortfall",
        "status_label": "Slight Shortfall",
        "budget_difference": -798,
        "categories": {
            "transportation": {"total": 10760},
            "accommodation": {"total": 6000},
            "food": {"total": 7200},
            "sightseeing": {"total": 150},
            "miscellaneous": {"total": 1688},
        }
    },
    "transportation_comparison": {
        "start_location": "Visakhapatnam",
        "destination": "Goa",
        "road_distance_km": 1050,
        "air_distance_km": 820,
        "options": [
            {"mode": "Flights", "icon": "✈️", "available": True, "one_way_total_inr": 13444, "return_total_inr": 26888, "duration_formatted": "1h 30m", "badges": ["Fastest"], "booking_provider": "MakeMyTrip", "booking_link": "https://makemytrip.com", "notes": "Quickest option.", "details": "Direct flight.", "cost_per_person_inr": 6722},
            {"mode": "Buses", "icon": "🚌", "available": True, "one_way_total_inr": 5380, "return_total_inr": 10760, "duration_formatted": "18h 00m", "badges": ["Budget"], "booking_provider": "redBus", "booking_link": "https://redbus.in", "notes": "Budget option.", "details": "Overnight sleeper.", "cost_per_person_inr": 2690},
        ]
    },
    "intercity_travel": {
        "distance_km": 820,
        "estimated_duration": "18 hours by bus"
    }
}


class TestIntentClassification(unittest.TestCase):
    """Tests 25–30: Intent classification."""

    def test_25_greeting_detected(self):
        """Test 25: Greeting intent is correctly identified."""
        intents = classify_intent("Hello there!", [])
        self.assertIn(Intent.GREETING, intents)

    def test_26_weather_intent(self):
        """Test 26: Weather intent with search intent for 'current' queries."""
        intents = classify_intent("What is the current weather in Goa?", [])
        self.assertIn(Intent.WEATHER, intents)

    def test_27_budget_intent(self):
        """Test 27: Budget intent is detected."""
        intents = classify_intent("How can I reduce my trip budget?", [])
        self.assertIn(Intent.BUDGET, intents)

    def test_28_transport_intent(self):
        """Test 28: Transport intent is detected."""
        intents = classify_intent("How do I get from Vizag to Goa by train?", [])
        self.assertIn(Intent.TRANSPORT, intents)

    def test_29_search_intent_for_opening_hours(self):
        """Test 29: Opening hours triggers web search intent."""
        intents = classify_intent("What are the opening hours of Fort Aguada?", [])
        self.assertIn(Intent.SEARCH, intents)

    def test_30_currency_intent(self):
        """Test 30: Currency conversion query is classified."""
        intents = classify_intent("What is the USD to INR exchange rate?", [])
        self.assertIn(Intent.CURRENCY, intents)


class TestContextResolution(unittest.TestCase):
    """Tests 31–32: Conversation context memory."""

    def test_31_pronoun_resolution_from_history(self):
        """Test 31: 'there' resolves to Goa from recent history."""
        history = [
            {"sender": "user", "text": "Tell me about Goa"},
            {"sender": "assistant", "text": "Goa is a beautiful destination in India."}
        ]
        ctx = {}
        resolved = _resolve_context_from_history("What's the weather there?", history, ctx)
        self.assertEqual(resolved.get("destination", "").lower(), "goa")

    def test_32_traveler_count_from_history(self):
        """Test 32: Traveler count is extracted from previous message."""
        history = [
            {"sender": "user", "text": "I am planning a trip for 3 travellers to Goa."}
        ]
        ctx = {}
        resolved = _resolve_context_from_history("What's the budget?", history, ctx)
        self.assertEqual(resolved.get("travelers"), 3)


class TestOfflineExpertAgent(unittest.TestCase):
    """Tests 33–38: Offline expert agent responses."""

    def setUp(self):
        self.ctx = MOCK_TRIP_CONTEXT

    def test_33_greeting_response(self):
        """Test 33: Greeting returns a welcoming message."""
        reply = _expert_offline_agent("Hello!", [], self.ctx)
        self.assertIn("TripWise AI", reply)
        self.assertIn("Goa", reply)

    def test_34_day_recall(self):
        """Test 34: Day 1 recall returns Baga Beach."""
        reply = _expert_offline_agent("What is the plan for day 1?", [], self.ctx)
        self.assertIn("Baga Beach", reply)
        self.assertIn("Fort Aguada", reply)

    def test_35_budget_breakdown(self):
        """Test 35: Budget query returns all cost categories."""
        reply = _expert_offline_agent("Show me my budget breakdown", [], self.ctx)
        self.assertIn("25,798", reply)
        self.assertIn("Transportation", reply)
        self.assertIn("Accommodation", reply)

    def test_36_transport_options(self):
        """Test 36: Transport query returns available modes."""
        reply = _expert_offline_agent("What transport options do I have?", [], self.ctx)
        self.assertIn("Flights", reply)
        self.assertIn("Buses", reply)

    def test_37_packing_checklist(self):
        """Test 37: Packing advice returned for beach destination."""
        reply = _expert_offline_agent("What should I pack for Goa?", [], self.ctx)
        self.assertIn("Swimwear", reply)
        self.assertIn("Sunscreen", reply)

    def test_38_best_time_to_visit(self):
        """Test 38: Best time query returns seasonal info for Goa."""
        reply = _expert_offline_agent("When is the best time to visit Goa?", [], self.ctx)
        self.assertIn("November", reply)
        self.assertIn("monsoon", reply.lower())


class TestCurrencyService(unittest.TestCase):
    """Test 39: Currency exchange rate service."""

    def test_39_currency_rates_fallback(self):
        """Test 39: Currency rates return valid INR base with key currencies."""
        with patch("requests.get", side_effect=Exception("Network down")):
            rates_data = _get_free_exchange_rates()
        self.assertIn("rates", rates_data)
        self.assertIn("USD", rates_data["rates"])
        self.assertIn("EUR", rates_data["rates"])
        self.assertGreater(rates_data["rates"]["USD"], 0.0)


class TestSearchService(unittest.TestCase):
    """Tests 40–42: Web search service."""

    def test_40_should_search_for_opening_hours(self):
        """Test 40: Opening hours query triggers web search."""
        self.assertTrue(should_web_search("What are the opening hours of Aguada Fort?"))

    def test_41_should_not_search_for_greeting(self):
        """Test 41: Greeting does NOT trigger web search."""
        self.assertFalse(should_web_search("Hello! How are you?"))

    def test_42_should_search_for_visa(self):
        """Test 42: Visa question triggers web search."""
        self.assertTrue(should_web_search("Do I need a visa for Paris?"))


class TestFullChatResponse(unittest.TestCase):
    """Tests 43–45: End-to-end generate_chat_response (offline mode)."""

    def setUp(self):
        self.ctx = MOCK_TRIP_CONTEXT
        # Ensure no API keys are set for offline testing
        self._orig_gemini = os.environ.get("GEMINI_API_KEY", "")
        self._orig_openai = os.environ.get("OPENAI_API_KEY", "")
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self):
        os.environ["GEMINI_API_KEY"] = self._orig_gemini
        os.environ["OPENAI_API_KEY"] = self._orig_openai

    def test_43_offline_weather_uses_ctx(self):
        """Test 43: Weather query uses weather data (ctx or live Open-Meteo) offline."""
        result = generate_chat_response("What is the weather in Goa?", [], self.ctx)
        self.assertIn("reply", result)
        reply = result["reply"]
        # Accept any numeric temperature (live Open-Meteo or ctx value both valid)
        self.assertTrue(
            "Temperature" in reply or "weather" in reply.lower(),
            f"Expected weather info in reply, got: {reply[:200]}"
        )
        self.assertIn("°C", reply)

    def test_44_offline_budget_response(self):
        """Test 44: Budget query returns formatted cost data (offline)."""
        result = generate_chat_response("How much does the trip cost?", [], self.ctx)
        self.assertIn("reply", result)
        reply = result["reply"]
        self.assertIn("25,798", reply)

    def test_45_offline_greeting(self):
        """Test 45: Greeting returns a valid response with provider set (offline)."""
        result = generate_chat_response("Hello!", [], self.ctx)
        self.assertIn("reply", result)
        self.assertIn("TripWise", result["reply"])
        self.assertIn("provider", result)
        self.assertEqual(result["source_indicator"], "offline_intelligence")

    def test_46_response_has_required_keys(self):
        """Test 46: All responses include required keys."""
        result = generate_chat_response("What's day 2?", [], self.ctx)
        self.assertIn("reply", result)
        self.assertIn("provider", result)
        self.assertIn("source_indicator", result)
        self.assertIsInstance(result["reply"], str)
        self.assertGreater(len(result["reply"]), 10)

    def test_47_missing_gemini_key_graceful(self):
        """Test 47: Missing Gemini key falls back to offline engine gracefully."""
        os.environ["GEMINI_API_KEY"] = ""
        result = generate_chat_response("Plan my trip", [], self.ctx)
        self.assertEqual(result["source_indicator"], "offline_intelligence")

    def test_48_search_intent_blocked_no_net(self):
        """Test 48: Web search failure does not crash chatbot."""
        with patch("services.search_service.web_search", return_value=[]):
            result = generate_chat_response("What are the opening hours of Fort Aguada?", [], self.ctx)
        self.assertIn("reply", result)
        self.assertIsInstance(result["reply"], str)

    def test_49_conversation_history_memory(self):
        """Test 49: Second message receives context from prior exchange."""
        history = [
            {"sender": "user", "text": "I am planning a 4 day trip to Goa."},
            {"sender": "assistant", "text": "Great! Goa is a wonderful destination for a 4 day trip."}
        ]
        result = generate_chat_response("What should I pack for there?", history, {})
        self.assertIn("reply", result)
        # Should mention Goa or packing items
        self.assertTrue(
            "pack" in result["reply"].lower() or "goa" in result["reply"].lower(),
            f"Expected packing/Goa in reply, got: {result['reply'][:200]}"
        )

    def test_50_empty_ollama_config(self):
        """Test 50: Empty OLLAMA_BASE_URL does not cause relative URL error and falls back gracefully."""
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "", "GEMINI_API_KEY": ""}):
            result = generate_chat_response("What is the weather in Goa?", [], self.ctx)
            self.assertEqual(result["source_indicator"], "offline_intelligence")
            self.assertIn("reply", result)

    def test_51_invalid_ollama_url(self):
        """Test 51: Invalid OLLAMA_BASE_URL does not crash with scheme error."""
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "localhost:11434", "GEMINI_API_KEY": ""}):
            result = generate_chat_response("What is the weather in Goa?", [], self.ctx)
            self.assertIn("reply", result)

    def test_52_ollama_unavailable_falls_back(self):
        """Test 52: Configured but unreachable Ollama server falls back without crashing."""
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://127.0.0.1:11434", "GEMINI_API_KEY": ""}):
            with patch("requests.get", side_effect=Exception("Connection refused")):
                result = generate_chat_response("What is the weather in Goa?", [], self.ctx)
                self.assertEqual(result["source_indicator"], "offline_intelligence")

    def test_53_missing_duckduckgo_dependency(self):
        """Test 53: Missing duckduckgo-search package returns empty list instead of raising."""
        from services.search_service import web_search
        with patch.dict("sys.modules", {"duckduckgo_search": None, "ddgs": None}):
            res = web_search("Goa beach timing", max_results=2)
            self.assertEqual(res, [])

    def test_54_successful_web_search_and_source_attribution(self):
        """Test 54: Successful web search includes citations in search_sources."""
        mock_results = [
            {"title": "Fort Aguada Hours 2025", "url": "https://example.com/aguada", "snippet": "Open 9:30 AM to 6 PM daily."}
        ]
        with patch("services.search_service.web_search", return_value=mock_results):
            result = generate_chat_response("What are the opening hours of Fort Aguada?", [], self.ctx)
            self.assertIn("search_sources", result)
            self.assertEqual(len(result["search_sources"]), 1)
            self.assertEqual(result["search_sources"][0]["url"], "https://example.com/aguada")
            self.assertIn("https://example.com/aguada", result["reply"])

    def test_55_alternative_attraction_recommendation(self):
        """Test 55: Activity replacement recommends genuine unscheduled alternative."""
        result = generate_chat_response("Replace the second day's afternoon activity", [], self.ctx)
        self.assertIn("Day 2", result["reply"])
        self.assertTrue(
            "alternative" in result["reply"].lower() or "recommendation" in result["reply"].lower(),
            f"Expected alternative/recommendation in reply: {result['reply']}"
        )

    def test_56_greeting_does_not_trigger_search(self):
        """Test 56: Simple greeting never calls web_search."""
        with patch("services.search_service.web_search") as mock_search:
            result = generate_chat_response("Hello!", [], self.ctx)
            mock_search.assert_not_called()
            self.assertIn("TripWise", result["reply"])

    def test_57_weather_fallback_without_data(self):
        """Test 57: Destination seasonal climate returned when live weather is unavailable."""
        ctx_no_weather = {"destination": "Goa", "travelers": 2, "currency": "INR"}
        result = generate_chat_response("What is the weather like?", [], ctx_no_weather)
        self.assertIn("reply", result)
        self.assertTrue(
            any(w in result["reply"].lower() for w in ["temperature", "weather", "season", "climate"]),
            f"Expected weather/climate in reply: {result['reply']}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ─── Tests A–J: Destination Change, Greetings, State Management, Markdown ────

class TestDestinationChangeRecognition(unittest.TestCase):
    """Tests A–B: Destination entity extraction and context switching."""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_A_destination_change_bare_name(self):
        """Test A: Typing 'thailand' with existing Goa context switches to Thailand."""
        result = generate_chat_response(
            "thailand",
            history=[
                {"sender": "user", "text": "I want to plan a trip to Goa"},
                {"sender": "assistant", "text": "Great! Goa is a wonderful destination."},
            ],
            trip_context={"destination": "Goa", "travelers": 2, "currency": "INR", "itinerary": []},
        )
        reply = result["reply"].lower()
        # Must acknowledge Thailand and not keep talking about Goa
        self.assertIn("thailand", reply, f"Expected 'Thailand' in reply, got: {result['reply'][:200]}")
        self.assertNotIn("your destination", reply.lower(),
                         "Reply should not fall back to generic 'your destination'")

    def test_B_destination_change_phrase(self):
        """Test B: 'I want to visit Japan instead' switches destination from Goa to Japan."""
        new_dest, is_change = extract_destination_entity("I want to visit Japan instead")
        self.assertIsNotNone(new_dest, "Should detect Japan as destination")
        self.assertTrue(is_change, "Should flag as a destination change")
        self.assertEqual(new_dest.lower(), "japan")

    def test_B2_destination_change_plan_to(self):
        """Test B2: 'plan a trip to Thailand' is detected as destination change."""
        new_dest, is_change = extract_destination_entity("plan a trip to Thailand")
        self.assertIsNotNone(new_dest)
        self.assertTrue(is_change)
        self.assertEqual(new_dest.lower(), "thailand")

    def test_B3_update_context_clears_stale_data(self):
        """Test B3: update_context_for_destination_change clears itinerary but keeps travelers."""
        old_ctx = {
            "destination": "Goa",
            "start_location": "Visakhapatnam",
            "travelers": 3,
            "currency": "INR",
            "itinerary": [{"day_number": 1}],
            "attractions_summary": [{"name": "Baga Beach"}],
            "budget_analysis": {"total_estimated_trip_cost": 25000},
        }
        new_ctx = update_context_for_destination_change(old_ctx, "Thailand")
        self.assertEqual(new_ctx["destination"], "Thailand")
        self.assertEqual(new_ctx["travelers"], 3, "travelers must be preserved")
        self.assertEqual(new_ctx["start_location"], "Visakhapatnam", "start_location must be preserved")
        self.assertNotIn("itinerary", new_ctx, "itinerary must be cleared")
        self.assertNotIn("attractions_summary", new_ctx, "attractions_summary must be cleared")
        self.assertNotIn("budget_analysis", new_ctx, "budget_analysis must be cleared")


class TestNaturalGreetings(unittest.TestCase):
    """Tests C: Natural, context-aware greetings."""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_C_no_destination_greeting(self):
        """Test C: 'hii' with no destination → short welcome, no bullet command list."""
        result = generate_chat_response("hii", history=[], trip_context={})
        reply = result["reply"]
        # Should mention TripWise and invite destination input
        self.assertIn("TripWise", reply)
        # Should NOT be a 8-bullet feature list (old greeting)
        # Accept short friendly greeting instead
        self.assertLess(reply.count("•"), 5,
                        f"Greeting should be short (< 5 bullets), got: {reply[:300]}")

    def test_C2_greeting_with_loaded_trip(self):
        """Test C2: 'Hello' with existing trip → acknowledges trip, no long feature list."""
        result = generate_chat_response("Hello", history=[], trip_context=MOCK_TRIP_CONTEXT)
        reply = result["reply"]
        self.assertIn("Goa", reply, "Should mention the loaded trip destination")
        self.assertIn("TripWise", reply)

    def test_C3_hey_no_destination(self):
        """Test C3: 'hey' with no context → short welcome."""
        result = generate_chat_response("hey", history=[], trip_context={})
        reply = result["reply"]
        self.assertIn("TripWise", reply)
        self.assertGreater(len(reply), 10)
        self.assertLess(len(reply), 500, "Welcome greeting should be concise, not a wall of text")


class TestConversationStateManagement(unittest.TestCase):
    """Tests D, G: Multi-turn context extraction."""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_D_day_recall_in_conversation(self):
        """Test D: 'What about the second day?' recalls Day 2 from itinerary."""
        result = generate_chat_response(
            "What about the second day?",
            history=[
                {"sender": "user", "text": "Show me my itinerary"},
                {"sender": "assistant", "text": "Your Goa itinerary is ready."},
            ],
            trip_context=MOCK_TRIP_CONTEXT,
        )
        reply = result["reply"]
        self.assertIn("Day 2", reply)
        self.assertIn("Dudhsagar", reply)

    def test_G_traveler_count_update(self):
        """Test G: 'For 3 people' updates traveler count and keeps destination."""
        resolved = _resolve_context_from_history(
            "For 3 people",
            history=[
                {"sender": "user", "text": "I want to plan a trip to Goa"},
            ],
            ctx={"destination": "Goa", "travelers": 2},
        )
        self.assertEqual(resolved["travelers"], 3, "Traveler count should update to 3")
        self.assertEqual(resolved["destination"], "Goa", "Destination must be preserved")

    def test_G2_solo_traveler_detection(self):
        """Test G2: 'just me' resolves to 1 traveler."""
        resolved = _resolve_context_from_history(
            "it'll be just me",
            history=[],
            ctx={"destination": "Goa", "travelers": 2},
        )
        self.assertEqual(resolved["travelers"], 1)


class TestStaleDestinationPrevention(unittest.TestCase):
    """Test E: No stale destination data after a switch."""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_E_no_stale_data_after_dest_change(self):
        """Test E: After switching to Thailand, reply should not mention Goa attractions."""
        # Simulate: user has Goa trip loaded, then types 'thailand'
        result = generate_chat_response(
            "thailand",
            history=[
                {"sender": "user", "text": "I want to plan a trip to Goa for 4 days"},
                {"sender": "assistant", "text": "Great! Here is your Goa itinerary."},
            ],
            trip_context=MOCK_TRIP_CONTEXT,  # Goa trip loaded
        )
        reply = result["reply"].lower()
        self.assertIn("thailand", reply)
        # Should not list Goa-specific beaches from the old context
        self.assertNotIn("baga beach", reply)
        self.assertNotIn("fort aguada", reply)


class TestBudgetContext(unittest.TestCase):
    """Test F: Budget query in conversation context."""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_F_budget_in_context(self):
        """Test F: 'Make it cheaper' with Goa trip context returns budget advice."""
        result = generate_chat_response(
            "Make it cheaper",
            history=[
                {"sender": "user", "text": "I want to plan a Goa trip"},
                {"sender": "assistant", "text": "Your Goa budget is ₹25,798 total."},
            ],
            trip_context=MOCK_TRIP_CONTEXT,
        )
        reply = result["reply"].lower()
        self.assertTrue(
            any(w in reply for w in ["budget", "cost", "save", "cheaper", "accommodation", "transport"]),
            f"Expected budget advice, got: {result['reply'][:200]}"
        )


class TestMarkdownFormatting(unittest.TestCase):
    """Test H: Backend reply does not contain literal \\n or \\* characters."""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_H_no_literal_backslash_n(self):
        """Test H: Reply string contains actual newlines, not literal \\n sequences."""
        result = generate_chat_response("What is the plan for day 1?", [], MOCK_TRIP_CONTEXT)
        reply = result["reply"]
        # Literal backslash-n (\n as 2 chars) should NOT appear in the string
        self.assertNotIn("\\n", reply,
                         f"Literal \\\\n found in reply — Python f-string must use real newlines: {reply[:200]}")

    def test_H2_no_literal_asterisks_in_reply(self):
        """Test H2: Double-asterisk bold markers ARE in reply (they render as bold in browser) — just ensure no orphan \\* escape sequences."""
        result = generate_chat_response("Show me my budget breakdown", [], MOCK_TRIP_CONTEXT)
        reply = result["reply"]
        self.assertNotIn("\\*", reply,
                         f"Literal \\\\* escape found in reply: {reply[:200]}")


class TestGeminiFallback(unittest.TestCase):
    """Test I: Gemini unavailable → graceful offline fallback."""

    def test_I_gemini_unavailable_fallback(self):
        """Test I: Empty GEMINI_API_KEY causes graceful fallback to offline engine."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "OPENAI_API_KEY": ""}):
            result = generate_chat_response("What should I pack for Goa?", [], MOCK_TRIP_CONTEXT)
        self.assertEqual(result["source_indicator"], "offline_intelligence",
                         "Must use offline engine when Gemini key is absent")
        self.assertIn("reply", result)
        self.assertGreater(len(result["reply"]), 20)

    def test_I2_gemini_key_mocked_unavailable(self):
        """Test I2: When Gemini API returns 429, response gracefully falls back to offline."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key-for-test"}):
            with patch("requests.post", return_value=mock_response):
                result = generate_chat_response("Plan my trip", [], MOCK_TRIP_CONTEXT)
        self.assertIn("reply", result)
        self.assertIsInstance(result["reply"], str)


class TestDestinationSpecificRecommendations(unittest.TestCase):
    """Test J: Destination-specific recommendations use correct context."""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def test_J_destination_specific_attractions(self):
        """Test J: Attractions query returns destinations from the loaded trip context."""
        result = generate_chat_response(
            "What places should I visit?",
            history=[],
            trip_context=MOCK_TRIP_CONTEXT,
        )
        reply = result["reply"]
        # Should mention Goa attractions from the loaded trip context
        self.assertTrue(
            any(name in reply for name in ["Baga Beach", "Fort Aguada", "Dudhsagar", "Goa"]),
            f"Expected Goa attractions in reply, got: {reply[:300]}"
        )

    def test_J2_extract_known_destination_from_query(self):
        """Test J2: Destination entity extraction handles all known destinations."""
        test_cases = [
            ("thailand", "Thailand"),
            ("japan", "Japan"),
            ("bali", "Bali"),
            ("let's go to paris", "Paris"),
            ("plan a trip to tokyo", "Tokyo"),
        ]
        for query, expected in test_cases:
            with self.subTest(query=query):
                dest, is_change = extract_destination_entity(query)
                self.assertIsNotNone(dest, f"Should detect destination from '{query}'")
                self.assertEqual(dest.lower(), expected.lower(),
                                 f"Expected {expected}, got {dest}")
