
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from planner import create_itinerary
from datetime import date
import os

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Read debug mode from .env
app_debug = os.getenv("FLASK_DEBUG", "0") == "1"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/plan", methods=["POST"])
def plan():
    data = request.get_json(silent=True) or {}

    # Get form data
    destination = str(data.get("destination", "")).strip()
    start_date = str(data.get("start_date", "")).strip()
    end_date = str(data.get("end_date", "")).strip()
    currency = str(data.get("currency", "INR")).strip().upper()

    interests = data.get("interests", [])
    budget = data.get("budget", 0)
    travelers = data.get("travelers", 1)

    # Validate destination and dates
    if not destination:
        return jsonify({
            "error": "Please enter a destination."
        }), 400

    if not start_date or not end_date:
        return jsonify({
            "error": "Please select both travel dates."
        }), 400

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid date format. Please select valid dates."
        }), 400

    if end < start:
        return jsonify({
            "error": "End date must be on or after the start date."
        }), 400

    # Validate budget and traveler count
    try:
        budget = float(budget)
        travelers = int(travelers)
    except (ValueError, TypeError):
        return jsonify({
            "error": "Budget and traveler count must be valid numbers."
        }), 400

    if budget <= 0:
        return jsonify({
            "error": "Budget must be greater than zero."
        }), 400

    if travelers < 1 or travelers > 30:
        return jsonify({
            "error": "Travelers must be between 1 and 30."
        }), 400

    # Validate currency
    allowed_currencies = {"INR", "USD", "EUR", "GBP"}

    if currency not in allowed_currencies:
        return jsonify({
            "error": "Please select a supported currency."
        }), 400

    # Validate interests
    if not isinstance(interests, list):
        return jsonify({
            "error": "Interests must be provided as a list."
        }), 400

    try:
        result = create_itinerary(
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            interests=interests,
            travelers=travelers,
            currency=currency
        )

        return jsonify(result), 200

    except (ValueError, TypeError) as error:
        return jsonify({
            "error": str(error)
        }), 400

    except Exception:
        app.logger.exception("Failed to create travel itinerary")
        return jsonify({
            "error": "Unable to create the itinerary. Please try again."
        }), 500


if __name__ == "__main__":
    app.run(
        debug=app_debug,
        host="127.0.0.1",
        port=5000
    )
