"""
Validation of TripWise Chatbot lifecycle across page refresh and session reload.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from services.storage_service import get_trip

client = app.test_client()

print("=" * 80)
print("TESTING TRIPWISE REFRESH & STATE SYNCHRONIZATION LIFECYCLE")
print("=" * 80)

# 1. Fresh page load: GET /
print("\n1. Fresh page load: GET /")
res_home = client.get("/")
assert res_home.status_code == 200, f"Expected 200, got {res_home.status_code}"
assert b"id=\"chatbot-drawer\"" in res_home.data
assert b"id=\"floating-chat-trigger\"" in res_home.data
print("   Page loaded successfully with chat drawer and floating trigger present.")

# 2. First chat session on fresh page (no itinerary generated yet)
print("\n2. First chat session (no itinerary generated yet):")
res_chat1 = client.post("/api/chat", json={
    "message": "hii",
    "history": [],
    "trip_context": {"destination": "Goa", "start_location": "Visakhapatnam", "travelers": 2, "currency": "INR"}
})
assert res_chat1.status_code == 200
data1 = res_chat1.get_json()
print("   Bot reply:", data1["reply"][:150], "...")
print("   Provider:", data1["provider"])
assert data1["source_indicator"] == "offline_intelligence"
assert "TripWise AI" in data1["reply"]

# 3. Simulate page refresh: GET / (new session state)
print("\n3. Simulating page refresh: GET / (resets in-memory JS state)")
res_refresh = client.get("/")
assert res_refresh.status_code == 200
print("   Refreshed page loaded cleanly.")

# 4. Chat works after refresh
print("\n4. Chat message sent after page refresh:")
res_chat_after_refresh = client.post("/api/chat", json={
    "message": "Plan a trip to Thailand.",
    "history": [], # Fresh history on refresh
    "trip_context": {"destination": "Goa", "travelers": 2, "currency": "INR"}
})
assert res_chat_after_refresh.status_code == 200
data_refresh = res_chat_after_refresh.get_json()
print("   Bot reply:", data_refresh["reply"][:150], "...")
print("   New destination in updated_context:", data_refresh["updated_context"]["destination"])
assert data_refresh["updated_context"]["destination"] == "Thailand"

# 5. Load a saved trip route: GET /trip/e043393f (the Thailand trip in trips.db)
print("\n5. Testing shared/saved trip route: GET /trip/e043393f")
res_saved_trip = client.get("/trip/e043393f")
assert res_saved_trip.status_code == 200
assert b"INITIAL_SHARED_TRIP" in res_saved_trip.data
print("   Saved Thailand trip restored via INITIAL_SHARED_TRIP!")

# 6. Chat with restored saved trip context
saved_trip_obj = get_trip("e043393f")
print("\n6. Chat query with restored saved Thailand trip:")
res_saved_chat = client.post("/api/chat", json={
    "message": "What is on Day 1?",
    "history": [],
    "trip_context": saved_trip_obj
})
assert res_saved_chat.status_code == 200
data_saved_chat = res_saved_chat.get_json()
print("   Bot reply:", data_saved_chat["reply"][:150], "...")
assert "Day 1" in data_saved_chat["reply"]

print("\n" + "=" * 80)
print("REFRESH LIFECYCLE AND CONTEXT RESTORATION FULLY VERIFIED")
print("=" * 80)
