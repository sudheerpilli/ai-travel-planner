"""
E2E Multi-turn Chatbot Conversation Test for TripWise
Simulates the exact 7-turn conversation as executed by the frontend app.js against /api/chat.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from app import app

client = app.test_client()

conversation = [
    ("hii", "Step 1: Friendly greeting"),
    ("Plan a trip to Goa.", "Step 2: Plan trip to Goa"),
    ("Actually, I want Thailand instead.", "Step 3: Switch to Thailand & clear Goa"),
    ("What places should I visit?", "Step 4: Genuine Thailand attractions"),
    ("Make it cheaper.", "Step 5: Budget optimization for Thailand"),
    ("What about Day 2?", "Step 6: Day 2 Thailand itinerary or highlight"),
    ("For 3 people.", "Step 7: Update traveller count to 3"),
]

history = []
# Starting context matching empty frontend state
trip_context = {
    "destination": "Goa",
    "start_location": "Visakhapatnam",
    "travelers": 2,
    "currency": "INR"
}

print("=" * 80)
print("STARTING TRIPWISE END-TO-END 7-STEP CONVERSATION TEST")
print("=" * 80)

for idx, (user_msg, step_desc) in enumerate(conversation, 1):
    print(f"\n--- Turn {idx}: {step_desc} ---")
    print(f"User: {user_msg}")
    print(f"Pre-call context: destination='{trip_context.get('destination')}', travelers={trip_context.get('travelers')}")
    
    payload = {
        "message": user_msg,
        "history": history,
        "trip_context": trip_context
    }
    
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200, f"Status code was {response.status_code}"
    
    data = response.get_json()
    reply = data.get("reply", "")
    provider = data.get("provider", "")
    source_ind = data.get("source_indicator", "")
    updated_ctx = data.get("updated_context", {})
    
    # Update client-side state just as app.js does
    if updated_ctx:
        trip_context = updated_ctx
        
    history.append({"sender": "user", "text": user_msg})
    history.append({"sender": "assistant", "text": reply})
    
    print(f"Bot Provider: {provider} ({source_ind})")
    print(f"Bot Reply (first 250 chars):\n{reply[:250]}...")
    print(f"Post-call context: destination='{trip_context.get('destination')}', travelers={trip_context.get('travelers')}")
    print(f"Stale Goa keys in context: {[k for k in ['itinerary', 'attractions_summary', 'weather', 'budget_analysis'] if k in trip_context]}")

print("\n" + "=" * 80)
print("ALL 7 TURNS COMPLETED SUCCESSFULLY")
print("=" * 80)
