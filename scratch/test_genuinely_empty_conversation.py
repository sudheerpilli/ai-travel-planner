"""
Validation of Genuinely Empty Conversation
Starting from trip_context = {} (no destination, no itinerary, no saved data)
Runs the exact 7 turns and asserts outputs and context updates.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

client = app.test_client()

print("=" * 80)
print("RUNNING GENUINELY EMPTY CONVERSATION VALIDATION (trip_context = {})")
print("=" * 80)

history = []
# Strictly empty starting context
trip_context = {}

turns = [
    ("hii", "Initial greeting with empty context"),
    ("Plan a trip to Goa.", "Set initial destination to Goa"),
    ("Actually, I want Thailand instead.", "Switch destination to Thailand & clear Goa"),
    ("What places should I visit?", "Genuine Thailand attractions"),
    ("Make it cheaper.", "Budget optimization for Thailand"),
    ("What about Day 2?", "Day 2 highlight schedule for Thailand"),
    ("For 3 people.", "Update group size to 3 for Thailand"),
]

for idx, (msg, desc) in enumerate(turns, 1):
    print(f"\n[Turn {idx}] User: \"{msg}\" ({desc})")
    print(f"  Pre-Call Context: {trip_context}")
    
    res = client.post("/api/chat", json={
        "message": msg,
        "history": history,
        "trip_context": trip_context
    })
    assert res.status_code == 200, f"Status code {res.status_code}"
    
    data = res.get_json()
    reply = data["reply"]
    provider = data["provider"]
    source_ind = data["source_indicator"]
    updated_ctx = data.get("updated_context", {})
    
    # Mirror client-side app.js state update
    if updated_ctx:
        trip_context = dict(updated_ctx)
        
    history.append({"sender": "user", "text": msg})
    history.append({"sender": "assistant", "text": reply})
    
    print(f"  Bot Provider: {provider} [{source_ind}]")
    print(f"  Bot Reply:\n{reply}\n")
    print(f"  Post-Call Context: {trip_context}")
    
    # Specific assertions per turn:
    if idx == 1:
        assert "TripWise AI" in reply
        assert "Where are you thinking of travelling?" in reply
        # Verify no destination assumed
        assert "destination" not in trip_context or not trip_context["destination"]
    elif idx == 2:
        assert "Goa" in reply
        assert trip_context.get("destination") == "Goa"
    elif idx == 3:
        assert "Thailand" in reply
        assert trip_context.get("destination") == "Thailand"
        # Verify no stale Goa keys
        for stale in ["itinerary", "attractions_summary", "weather", "budget_analysis"]:
            assert stale not in trip_context, f"Stale key {stale} remained in context!"
    elif idx == 4:
        assert "Thailand" in reply
        assert any(attr in reply for attr in ["Grand Palace", "Wat Arun", "Wat Pho", "Chatuchak"])
        assert "Official published" in reply or "ticket" in reply or "tariff" in reply
    elif idx == 5:
        assert any(w in reply.lower() for w in ["budget", "cheaper", "cost", "save", "market", "transit"])
        assert "estimate" in reply.lower()
    elif idx == 6:
        assert "Day 2" in reply
        assert any(attr in reply for attr in ["Grand Palace", "Wat Pho", "Wat Arun", "Bangkok"])
        assert "estimate" in reply.lower()
    elif idx == 7:
        assert "3 travellers" in reply
        assert trip_context.get("travelers") == 3
        assert trip_context.get("destination") == "Thailand"

print("\n" + "=" * 80)
print("ALL 7 TURNS VERIFIED WITH ZERO ERRORS")
print("=" * 80)
