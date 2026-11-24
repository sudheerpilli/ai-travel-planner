# TripWise — AI Travel Planning Chatbot (Upgraded v2.0)

A comprehensive, production-grade travel planning platform built with **Python, Flask, Leaflet Maps, SQLite, HTML5, CSS3, and JavaScript**.

TripWise generates realistic, un-capped travel budgets, compares 5 modes of intercity transport, provides verified destination attractions with coordinates, calculates road distances and travel times, displays live weather forecasts, offers an interactive route map, answers travel questions with an AI assistant, and allows users to save, share, and export itineraries as PDF.

---

## 🚀 Key Upgrades & Features (Phases 1 – 15)

### 1. Accurate Travel Budget Calculator (Phase 2)
- **Independent Expense Engine**: Calculates trip expenses based on actual room nights, travelers, daily meal rates, local transit, intercity travel, and sightseeing tickets.
- **No Artificial Capping**: Expenses are never reduced artificially to force-fit the user's budget.
- **Budget Reconciliation**: All component totals mathematically reconcile with the grand total:
  $$\text{Total} = \text{Transit} + \text{Accommodation} + \text{Food} + \text{Sightseeing} + \text{Emergency Buffer}$$
- **Mode Flexibility**: Supports both **Total Group Budget** and **Per-Person Budget** modes.
- **Transparent Basis**: Shows calculation formula for each line item (e.g. *1 room × ₹2,000/night × 3 nights*).
- **Intelligent Sufficiency Checker**: Classifies as **Sufficient**, **Shortfall**, or **Exact Match** with actionable savings recommendations.

### 2. 5-Way Transportation Comparison (Phase 6 & 7)
- Compares **Flights**, **Trains**, **Buses**, **Outstation Cabs**, and **Private Car** between origin and destination.
- Calculates journey duration, road distance, air distance, per-person fares, and group round-trip costs.
- Identifies **Cheapest Option**, **Fastest Option**, and **Best Balance (Time & Cost)**.
- Direct booking and search links (Google Flights, IRCTC, redBus, MakeMyTrip Cabs, Google Maps).

### 3. Real Tourist Attractions with Details (Phase 3)
- Genuine tourist landmarks for popular destinations (Goa, Visakhapatnam, Paris, Tokyo, Bali, Hyderabad, etc.).
- Categories: **Beaches**, **Historical Places**, **Temples**, **Museums**, **Nature**, **Adventure**, **Shopping**, **Food**, and **Family**.
- Full details per place: GPS coordinates, opening hours, estimated visit duration, ticket fees, and recommended local dining spots.
- Dynamic fallback via Wikipedia Landmark Discovery for uncatalogued cities.

### 4. Road Distance & Travel-Time Routing (Phase 4 & 5)
- Road distance (km) and driving/walking time between consecutive attractions using OSRM and Haversine road models.
- Interstitial route cards between morning, afternoon, and evening slots with direct **Google Maps Directions** links.
- Geographically clustered activities to minimize zig-zag driving across cities.

### 5. Interactive Route Maps (Phase 8)
- Embedded Leaflet.js interactive map with OpenStreetMap tiles (100% free, zero API key required).
- Color-coded destination markers with popups displaying ticket fees, visit times, and descriptions.
- Polyline connecting consecutive daily attractions.

### 6. AI Travel Chatbot (Phase 9)
- Conversational travel guide knowing your active trip context (destination, origin, dates, budget, travelers).
- Answers questions on budget cuts, packing checklists, local food specialities, family tips, and rainy-day alternatives.
- Supports **Google Gemini 1.5 Flash** or **OpenAI GPT-4o-mini** when keys are configured in `.env`.
- Includes a built-in offline expert knowledge engine that works with zero API keys.

### 7. Live Weather & Packing Tips (Phase 10)
- Real-time weather and 5-day forecasts via Open-Meteo (100% free, no key required).
- Temperature, condition, humidity, wind speed, and rain probability.
- Weather-based travel and packing checklists.

### 8. Save, Share & Server-Side PDF Export (Phase 11 & Bug 3)
- Persistent SQLite storage (`trips.db`).
- Unique shareable URLs (`/trip/<trip_id>`).
- 1-click clipboard summary copy.
- **Dedicated ReportLab PDF Export** (`POST /api/trips/export-pdf`): Generates a publication-quality, multi-page PDF with custom branding, complete day-by-day itineraries (supporting 1–30 days), full budget breakdowns, transport comparisons, weather forecasts, and dynamic "Page X of Y" pagination.

---

## 📁 Final Project Architecture

```text
ai_travel_planning_chatbot/
├── app.py                      # Flask routes, API endpoints, request validation
├── planner.py                  # Core itinerary orchestration & scheduling
├── services/                   # Modular service layer
│   ├── budget_service.py       # Accurate independent budget & reconciliation
│   ├── attractions_service.py  # Verified attraction catalogue & Wikipedia search
│   ├── transport_service.py    # 5-way transport comparison (Flight/Train/Bus/Cab/Car)
│   ├── routing_service.py      # OSRM / Google road distance & geocoding
│   ├── weather_service.py      # Open-Meteo live weather & packing tips
│   ├── chatbot_service.py      # AI assistant (Gemini/OpenAI + offline engine)
│   ├── pdf_service.py          # Server-side multi-page ReportLab PDF export
│   ├── storage_service.py      # SQLite persistent trip storage & sharing
│   └── currency_service.py     # Multi-currency conversions (INR, USD, EUR, GBP)
├── templates/
│   └── index.html              # Modern 3D glassmorphic user interface & Leaflet maps
├── static/
│   ├── app.js                  # Frontend controller, geolocation, modals & chat
│   └── style.css               # Design system, responsive cards, print stylesheet
├── tests/
│   └── test_tripwise.py        # Automated test suite covering all phases
├── trips.db                    # SQLite database (auto-created on startup)
├── requirements.txt            # Python dependencies
├── .env.example                # Example environment configuration
├── run_windows.bat             # Windows one-click launcher
└── README.md                   # Documentation
```

---

## 🔑 API Keys & Configuration

### Features that work 100% FREE without ANY API key:
| Feature | Engine / Provider |
|---|---|
| **Budget Calculator** | Independent internal rates engine |
| **Transport Comparison** | Real routing + distance fare model |
| **Attractions** | Curated catalogue + Wikipedia Search |
| **Interactive Map** | Leaflet.js + OpenStreetMap |
| **Road Distances** | OSRM / Haversine road model |
| **Live Weather** | Open-Meteo API |
| **Currency Conversion** | Open Exchange Rates API |
| **AI Travel Assistant** | Built-in offline travel intelligence engine |
| **Trip Storage & Sharing** | Embedded SQLite database |

### Optional API Keys (configured in `.env`):
- `GOOGLE_MAPS_API_KEY`: For official Google Geocoding & Routes.
- `GEMINI_API_KEY`: For live Google Gemini 1.5 Flash LLM chat.
- `OPENAI_API_KEY`: For live OpenAI GPT-4o-mini LLM chat.
- `OPENWEATHERMAP_API_KEY`: For OpenWeatherMap data.

---

## 💻 Quick Start on Windows

### 1. Prerequisites
- Python 3.10 or newer installed.

### 2. Setup Virtual Environment & Install Dependencies
Open Command Prompt / PowerShell in this directory:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the Application
```powershell
python app.py
```

Open your browser at:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🧪 Running Automated Tests

Run the automated test suite covering budget accuracy, routing, attractions, weather, chatbot, and storage:

```powershell
.\venv\Scripts\python.exe -m unittest -v tests/test_tripwise.py
```
