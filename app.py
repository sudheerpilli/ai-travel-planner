"""
TripWise — AI Travel Planning Chatbot (Production Backend).
Flask routes, request handling, input validation, and modular service integrations.
"""

from __future__ import annotations
import os
import json
from datetime import date
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

from planner import create_comprehensive_itinerary
from services.chatbot_service import generate_chat_response
from services.weather_service import get_weather_for_destination
from services.storage_service import (
    init_db, save_trip, get_trip, list_saved_trips, delete_trip, update_trip
)
from services.pdf_service import generate_trip_pdf

app = Flask(__name__)
app_debug = os.getenv("FLASK_DEBUG", "0") == "1"

# Initialize SQLite database on startup
init_db()


@app.route("/")
def index():
    """Main application landing and trip planner page."""
    return render_template("index.html")


@app.route("/trip/<trip_id>")
def view_shared_trip(trip_id: str):
    """View a shared or saved trip by ID."""
    trip = get_trip(trip_id)
    if not trip:
        return render_template("index.html", error_message="Shared trip not found or expired."), 404
    return render_template("index.html", shared_trip_data=json.dumps(trip), shared_trip_id=trip_id)


@app.route("/api/plan", methods=["POST"])
def plan():
    """
    Generate an intelligent, comprehensive, un-capped travel plan.
    """
    data = request.get_json(silent=True) or {}

    start_location = str(data.get("start_location", "")).strip() or "Home City"
    destination = str(data.get("destination", "")).strip()
    start_date = str(data.get("start_date", "")).strip()
    end_date = str(data.get("end_date", "")).strip()
    currency = str(data.get("currency", "INR")).strip().upper()
    budget_type = str(data.get("budget_type", "total_group")).strip()
    travel_preference = str(data.get("travel_preference", "standard")).strip()
    accommodation_preference = str(data.get("accommodation_preference", "budget_hotel")).strip()
    food_preference = str(data.get("food_preference", "casual")).strip()
    interests = data.get("interests", [])
    budget = data.get("budget", 25000)
    travelers = data.get("travelers", 2)
    transport_mode = data.get("transport_mode")

    # Validations
    if not destination:
        return jsonify({"error": "Please enter a destination city or region."}), 400

    if not start_date or not end_date:
        return jsonify({"error": "Please select both departure and return dates."}), 400

    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD."}), 400

    if e_date < s_date:
        return jsonify({"error": "Return date must be on or after the departure date."}), 400

    try:
        budget = float(budget)
        travelers = int(travelers)
    except (ValueError, TypeError):
        return jsonify({"error": "Budget and traveller count must be valid numbers."}), 400

    if budget <= 0:
        return jsonify({"error": "Budget must be greater than zero."}), 400

    if travelers < 1 or travelers > 30:
        return jsonify({"error": "Number of travellers must be between 1 and 30."}), 400

    allowed_currencies = {"INR", "USD", "EUR", "GBP"}
    if currency not in allowed_currencies:
        return jsonify({"error": "Please select a supported currency: INR, USD, EUR, or GBP."}), 400

    if not isinstance(interests, list):
        interests = ["historical", "beaches", "nature", "food"]

    try:
        result = create_comprehensive_itinerary(
            start_location=start_location,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            travelers=travelers,
            budget=budget,
            budget_type=budget_type,
            currency=currency,
            travel_preference=travel_preference,
            accommodation_preference=accommodation_preference,
            food_preference=food_preference,
            interests=interests,
            transport_mode=transport_mode
        )
        return jsonify(result), 200

    except (ValueError, TypeError) as err:
        return jsonify({"error": str(err)}), 400
    except Exception as exc:
        app.logger.exception("Failed to generate itinerary: %s", exc)
        return jsonify({"error": "Unable to create itinerary at this moment. Please check inputs and try again."}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Conversational AI travel assistant endpoint with trip context.
    """
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Please provide a question or message."}), 400

    history = data.get("history", [])
    trip_context = data.get("trip_context", {})

    try:
        response = generate_chat_response(
            message=message,
            conversation_history=history,
            trip_context=trip_context
        )
        return jsonify(response), 200
    except Exception as exc:
        app.logger.exception("Chatbot error: %s", exc)
        return jsonify({
            "reply": "I'm having trouble processing that right now. Feel free to ask about budget savings, packing, or local food!",
            "provider": "TripWise Fallback"
        }), 200


@app.route("/api/weather", methods=["GET"])
def weather():
    """Destination weather endpoint."""
    destination = request.args.get("destination", "").strip()
    if not destination:
        return jsonify({"error": "Destination parameter required"}), 400

    res = get_weather_for_destination(destination)
    return jsonify(res), 200


# ─── Save, Load, Edit, Share Trips (Phase 11) ───

@app.route("/api/trips/save", methods=["POST"])
def save_trip_endpoint():
    """Save an itinerary to SQLite database and get shareable ID."""
    data = request.get_json(silent=True) or {}
    if not data or "destination" not in data:
        return jsonify({"error": "Invalid trip data payload."}), 400

    trip_id = save_trip(data)
    share_url = f"{request.host_url.rstrip('/')}/trip/{trip_id}"
    return jsonify({
        "success": True,
        "trip_id": trip_id,
        "share_url": share_url,
        "message": "Trip successfully saved!"
    }), 200


@app.route("/api/trips", methods=["GET"])
def list_trips_endpoint():
    """List all previously saved trips."""
    trips = list_saved_trips()
    return jsonify({"trips": trips}), 200


@app.route("/api/trips/<trip_id>", methods=["GET"])
def get_trip_endpoint(trip_id: str):
    """Retrieve full data for a saved trip."""
    trip = get_trip(trip_id)
    if not trip:
        return jsonify({"error": "Trip not found."}), 404
    return jsonify(trip), 200


@app.route("/api/trips/<trip_id>", methods=["DELETE"])
def delete_trip_endpoint(trip_id: str):
    """Delete a saved trip."""
    success = delete_trip(trip_id)
    if not success:
        return jsonify({"error": "Trip not found or could not be deleted."}), 404
    return jsonify({"success": True, "message": "Trip deleted successfully."}), 200


@app.route("/api/trips/<trip_id>/edit", methods=["POST"])
def edit_trip_endpoint(trip_id: str):
    """Update a previously saved trip."""
    data = request.get_json(silent=True) or {}
    success = update_trip(trip_id, data)
    if not success:
        return jsonify({"error": "Failed to update trip."}), 404
    return jsonify({"success": True, "message": "Trip updated successfully."}), 200


@app.route("/api/trips/export-pdf", methods=["POST"])
def export_pdf_endpoint():
    """
    Generate and download a comprehensive multi-page PDF report for the trip.
    """
    data = request.get_json(silent=True) or {}
    if not data or not data.get("destination"):
        return jsonify({"error": "Invalid trip data. 'destination' field is required."}), 400

    if "itinerary" not in data or not isinstance(data.get("itinerary"), list):
        return jsonify({"error": "Trip data must include an itinerary list."}), 400

    try:
        pdf_bytes = generate_trip_pdf(data)
        dest_clean = str(data.get("destination", "Trip")).replace(" ", "_").replace("/", "_")
        filename = f"TripWise_{dest_clean}_Itinerary.pdf"

        from flask import Response
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/pdf"
            }
        )
    except Exception as exc:
        app.logger.exception("PDF generation error: %s", exc)
        return jsonify({"error": f"Failed to generate PDF: {str(exc)}"}), 500


if __name__ == "__main__":
    app.run(
        debug=app_debug,
        host="127.0.0.1",
        port=5000
    )
