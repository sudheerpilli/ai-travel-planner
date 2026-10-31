# TripWise — AI Travel Planning Chatbot

A ready-to-run travel itinerary web app built with **Python, Flask, HTML, CSS and JavaScript**. It creates a daily schedule based on destination, dates, budget, number of travelers and interests.

## Features
- Responsive travel-planning form.
- Day-by-day morning, afternoon and evening itinerary.
- Interest-based recommendations: culture, nature, food, adventure, shopping and family.
- Indicative budget breakdown for transport, accommodation, food and attractions.
- Google Maps search links for each suggested attraction.
- Print or save itinerary as PDF using the browser.
- Optional OpenTripMap lookup for real attraction names when an API key is configured.
- Input validation and helpful error messages.

## Requirements
- Python 3.10 or newer
- Internet connection for package installation; optional API key for attraction lookup

## Run on Windows
Open Command Prompt in this folder and run:

```bat
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

If `py` is not recognized, try `python` instead. If activation is blocked by PowerShell policy, use Command Prompt or run `venv\\Scripts\\python.exe -m pip install -r requirements.txt`.

## Optional live attraction lookup
The app works without an API key using its built-in recommendation catalogue. To retrieve attraction names from OpenTripMap:
1. Obtain an API key from OpenTripMap.
2. Open `.env` and set `OPENTRIPMAP_API_KEY=your_key`.
3. Install/load environment variables. The simplest way is to add this near the top of `app.py`:

```python
from dotenv import load_dotenv
load_dotenv()
```

Restart the server. API responses can be incomplete and should be checked before travel.

## Project structure
```text
ai_travel_planning_chatbot/
├── app.py
├── planner.py
├── requirements.txt
├── .env.example
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── app.js
    └── style.css
```

## Important notes
- This is a complete runnable **demo project**, not a production booking platform.
- Recommendations use a rule-based planner, not an LLM. An LLM API can be added for natural-language planning.
- Budget figures are illustrative allocation estimates, not live prices or travel quotes. Currency changes the displayed symbol only; the budget number is not converted.
- OpenTripMap integration is optional and needs a valid key. Google Maps links open searches; they do not provide guaranteed routing or ticket prices.
- Before deploying publicly, disable Flask debug mode, add rate limiting, protect API keys, validate date ranges, and add automated tests.
