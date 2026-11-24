"""Quick spot check of the new distance handler and re-verify Q7."""
import sys, os
sys.path.insert(0, r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")
os.chdir(r"c:\Users\sudhe\Downloads\ai_travel_planning_chatbot")

from planner import create_comprehensive_itinerary
from services.chatbot_service import generate_chat_response

trip = create_comprehensive_itinerary("Visakhapatnam", "Goa", "2026-12-10", "2026-12-12", 1, 25000)
trip["destination"] = "Goa"
trip["start_location"] = "Visakhapatnam"

questions = [
    "What is the distance between Baga Beach and Fort Aguada?",
    "How far is Anjuna Flea Market from Calangute Beach?",
    "Is ₹10,000 enough for a three-day solo Goa trip?",
]
for q in questions:
    r = generate_chat_response(q, trip_context=trip)
    print(f"\nQ: {q}")
    print(f"Reply: {r['reply'][:300]}")
    print(f"Source: {r.get('source_indicator')}")
